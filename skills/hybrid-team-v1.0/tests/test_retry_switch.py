"""Connection retries and the switch to Claude, driven through `devteam.py lane` and the fake opencode CLI.

A connection failure (spawn/stall/throttle/crash) is retried 3 times; then, in preset hybrid, the rest of the
run moves to Claude sonnet. auth/quota/model/config switch at once; timeout, context and gate kinds do neither.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from test_dispatch_flow import FlowBase, chore_slice, code_slice, plan_of  # noqa: E402

import devteam  # noqa: E402
import router  # noqa: E402

SWITCH = "oc-switched.json"
THROTTLE = {"scenario": "throttle"}
H1_DONE = {"write": {"conf/h1.cfg": "x\n"}, "commit": "chore(H1): add the config",
           "text": "## Slice: H1\n## Status: Done\n## Gate:\n$ test -f conf/h1.cfg\n"
                   "exit 0 - conf/h1.cfg is present\n## Notes:\nadded the config\n"}


class RetrySwitchBase(FlowBase):
    def setUp(self):
        super().setUp()
        self.env["HYBRID_OC_RETRY_DELAY_S"] = "0"     # never wait between tries

    def step(self, data):
        self.script.write_text(json.dumps(data))

    def runs(self):
        log = self.tmp / "fake_log.jsonl"
        recs = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()] if log.exists() else []
        return [r for r in recs if r["argv"][:1] == ["run"]]

    def lane(self, sid="H1"):
        return self.engine("lane", sid).stdout

    def marker(self, sid="H1", kind="blocked"):
        return json.loads((self.state_dir / "slices" / ("%s.%s" % (sid, kind))).read_text())

    def switched(self):
        return (self.state_dir / SWITCH).exists()

    @staticmethod
    def agent_line(text, sid):
        lines = text[text.index("=== DISPATCH %s " % sid):].splitlines()
        return lines[1]

    def start(self, *slices, route=None):
        self.init(plan_of(*slices), *(["--route", route] if route else []))
        self.assertIn("=== LANE H1 oc:std", self.engine("dispatch", "H1").stdout)


class RetryTest(RetrySwitchBase):
    def test_retry_then_success_does_not_switch(self):
        self.start(chore_slice("H1"))
        self.step([THROTTLE, THROTTLE, H1_DONE])
        out = self.lane()
        self.assertIn("LANE H1 DONE", out)
        self.assertIn("kind=throttle :: retry 1/3 in 0s: ", out)
        self.assertIn("kind=throttle :: retry 2/3 in 0s: ", out)
        self.assertNotIn("retry 3/3", out)
        self.assertEqual(out.count("OC-WARN hybrid-team H1 tier=std"), 2)
        self.assertNotIn("kind=switch", out)
        self.assertFalse(self.switched())
        runs = self.runs()
        self.assertEqual(len(runs), 3)
        self.assertTrue(all("-s" not in r["argv"] for r in runs), "a retry is a fresh run, not a continuation")
        self.assertEqual(self.marker(kind="done")["backend"], "oc:std")
        self.assertIn("retry 2/3", (self.state_dir / "oc-errors.jsonl").read_text())

    def test_three_retries_then_switch_and_the_failed_unit_falls_back_on_sonnet(self):
        self.start(chore_slice("H1"))
        self.step(THROTTLE)
        out = self.lane()
        self.assertEqual(len(self.runs()), 4)
        for n in (1, 2, 3):
            self.assertIn("kind=throttle :: retry %d/3 in 0s: " % n, out)
        self.assertEqual(out.count("kind=switch"), 1)
        self.assertIn("OC-ERROR hybrid-team H1 tier=std", out)
        self.assertIn("kind=switch :: opencode throttle: ", out)
        self.assertIn("the rest of this run uses Claude sonnet", out)
        self.assertLess(out.index("OC-ERROR hybrid-team H1 tier=std model=zai-coding-plan/glm-5.3#high kind=throttle"),
                        out.index("kind=switch"))
        self.assertTrue(self.switched())
        self.assertEqual(self.marker()["reason"], "throttle")
        self.assertEqual(json.loads((self.state_dir / SWITCH).read_text())["unit"], "H1")
        self.assertEqual((self.state_dir / "oc-errors.jsonl").read_text().count("kind=switch"), 1)
        r = self.engine("next", "--no-review").stdout
        self.assertIn("ESCALATE H1 oc:std -> claude (throttle)", r)
        self.assertIn("model: sonnet", self.agent_line(r, "H1"))
        self.assertEqual(len(self.runs()), 4)

    def test_auth_switches_at_once_without_retry(self):
        self.start(chore_slice("H1"))
        self.step({"scenario": "auth"})
        out = self.lane()
        self.assertEqual(len(self.runs()), 1)
        self.assertNotIn("retry", out)
        self.assertIn("kind=auth", out)
        self.assertEqual(out.count("kind=switch"), 1)
        self.assertIn("kind=switch :: opencode auth: ", out)
        self.assertTrue(self.switched())
        r = self.engine("next", "--no-review").stdout
        self.assertIn("model: sonnet", self.agent_line(r, "H1"))

    def test_timeout_neither_retries_nor_switches(self):
        self.set_routing({"tiers": {"std": {"timeout_s": 1}}})
        self.start(chore_slice("H1"))
        self.step({"sleep": 30, "text": "late"})
        out = self.lane()
        self.assertEqual(len(self.runs()), 1)
        self.assertIn("kind=timeout", out)
        self.assertNotIn("retry", out)
        self.assertNotIn("kind=switch", out)
        self.assertFalse(self.switched())
        r = self.engine("next", "--no-review").stdout
        self.assertIn("ESCALATE H1 oc:std -> claude (timeout)", r)
        self.assertNotIn("model:", self.agent_line(r, "H1"))

    def test_gate_failure_neither_retries_nor_switches(self):
        self.start(chore_slice("H1"))
        self.step({"text": "## Slice: H1\n## Status: Blocked\n## Notes:\nneeds network\n"})
        out = self.lane()
        self.assertEqual(len(self.runs()), 1)
        self.assertIn("kind=gate", out)
        self.assertNotIn("retry", out)
        self.assertFalse(self.switched())

    def test_a_switched_run_stops_retrying_and_announces_the_switch_once(self):
        self.start(chore_slice("H1"))
        self.assertTrue(devteam.hybrid_shared.switch_to_claude(
            self.state_dir, "H0", "std", "zai-coding-plan/glm-5.3#high", "auth", "invalid api key"))
        self.step(THROTTLE)
        out = self.lane()
        self.assertEqual(len(self.runs()), 1)
        self.assertNotIn("retry", out)
        self.assertNotIn("kind=switch", out)
        self.assertEqual(self.marker()["reason"], "throttle")


class SwitchRoutingTest(RetrySwitchBase):
    def test_after_the_switch_oc_routed_slices_go_to_claude_sonnet_and_opencode_never_spawns(self):
        risky = dict(code_slice("C2"), risk="high")
        self.start(chore_slice("H1"), chore_slice("H2"), code_slice("C1"), risky)
        self.step({"scenario": "auth"})
        self.lane()
        self.assertTrue(self.switched())
        before = len(self.runs())
        r = self.engine("dispatch", "H2", "C1", "C2").stdout
        self.assertNotIn("=== LANE", r)
        self.assertIn("=== DISPATCH H2 [CHORE/WORK]", r)
        self.assertIn("model: sonnet", self.agent_line(r, "H2"))
        self.assertIn("=== DISPATCH C1 [CODE/SLICE]", r)      # no RED-then-opencode split any more
        self.assertIn("model: sonnet", self.agent_line(r, "C1"))
        self.assertIn("=== DISPATCH C2 [CODE/RED]", r)         # Claude work all along: model untouched
        self.assertNotIn("model:", self.agent_line(r, "C2"))
        self.assertEqual(len(self.runs()), before)
        self.assertEqual(self.st()["backends"]["H2"], "claude")

    def test_a_new_run_starts_unswitched(self):
        self.start(chore_slice("H1"))
        self.assertTrue(devteam.hybrid_shared.switch_to_claude(
            self.state_dir, "H1", "std", "zai-coding-plan/glm-5.3#high", "throttle", "429"))
        self.init(plan_of(chore_slice("H1")), "--force")
        self.assertFalse(self.switched())
        self.assertIn("=== LANE H1 oc:std", self.engine("dispatch", "H1").stdout)


class RouterSwitchTest(unittest.TestCase):
    def test_a_switched_run_routes_nothing_to_opencode(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(tmp), True)
        s = {"id": "H1", "kind": "chore", "size": "small", "verify": "true"}

        def route(preset):
            routing = {"preset": preset, "tiers": {"std": {"model": "p/m"}}, "rows": {"chore": "std"}}
            return router.route(s, routing, True, tmp)

        self.assertEqual(route("hybrid"), "oc:std")
        self.assertTrue(devteam.hybrid_shared.switch_to_claude(tmp, "H1", "std", "p/m", "crash", "boom"))
        self.assertEqual(route("hybrid"), "claude")
        self.assertEqual(route("opencode"), "held")    # never reached: only a hybrid run writes the switch


class OpencodePresetTest(RetrySwitchBase):
    def test_retries_then_held_without_a_switch(self):
        self.start(chore_slice("H1"), route="opencode")
        self.step(THROTTLE)
        out = self.lane()
        self.assertEqual(len(self.runs()), 4)
        self.assertEqual(out.count("retry"), 3)
        self.assertIn("kind=throttle", out)
        self.assertNotIn("kind=switch", out)
        self.assertFalse(self.switched())
        r = self.engine("next", "--no-review").stdout
        self.assertIn("HELD H1 (throttle)", r)
        self.assertNotIn("ESCALATE", r)
        self.assertNotIn("=== DISPATCH H1", r)
        self.assertEqual(self.st()["slices"]["H1"]["status"], "failed")

    def test_auth_is_held_at_once_without_a_switch(self):
        self.start(chore_slice("H1"), route="opencode")
        self.step({"scenario": "auth"})
        out = self.lane()
        self.assertEqual(len(self.runs()), 1)
        self.assertNotIn("kind=switch", out)
        self.assertFalse(self.switched())
        self.assertIn("HELD H1 (auth)", self.engine("next", "--no-review").stdout)


if __name__ == "__main__":
    unittest.main()
