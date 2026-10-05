import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import audit  # noqa: E402
import ha_dispatch  # noqa: E402

ROUTING = {
    "preset": "hybrid",
    "tiers": {
        "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "max_parallel": 6,
                "stall_s": 180, "timeout_s": 900},
        "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low", "max_parallel": 2,
                 "stall_s": 120, "timeout_s": 600},
    },
    "roles": {"investigator": "std", "verifier": "claude", "parser": "claude"},
    "max_roles": {"verifier": "std", "parser": "std"},
    "oc_batch_max": 4,
    "max_repairs": 2,
    "throttle_cooldown_s": 120,
}


class FakeCtx(object):
    """Mirrors the attributes of audit.Ctx that ha_dispatch reads."""

    def __init__(self, out, state, cap=4, routing=None):
        self.out = Path(out)
        self.state = state
        self.state.setdefault("cap", cap)
        self.cfg = {"scripts_dir": "/abs/skill/scripts", "routing": routing or ROUTING}


class FakeMerged(object):
    """Mirrors the attributes of audit.Merged that ha_dispatch reads."""

    def __init__(self, batch_done=(), vdone=(), failed=(), events=None, finding=None, batch_time=None):
        self.batch_done = {b: True for b in batch_done}
        self.vdone = {b: True for b in vdone}
        self.failed = set(failed)
        self.events = dict(events or {})
        self.finding = dict(finding or {})
        self.batch_time = dict(batch_time or {})


class OcLinesTest(unittest.TestCase):
    def test_oc_command_quotes_scripts_dir(self):
        c = FakeCtx("/tmp/out", {})
        self.assertEqual(ha_dispatch.oc_command(c, "batch-03"),
                         'python3 "/abs/skill/scripts/audit.py" oc-run batch-03')

    def test_oc_block_batches(self):
        rows = [("batch-01", "oc:std", 4, "cmd1"), ("batch-02", "oc:lite", 3, "cmd2")]
        self.assertEqual(ha_dispatch.oc_block(rows), [
            "OPENCODE 2 batches (7 items) | run each in the BACKGROUND (Bash run_in_background) in the SAME message:",
            "  batch-01 oc:std (4 items) → cmd1",
            "  batch-02 oc:lite (3 items) → cmd2",
            "After dispatching: run `audit.py status` on every completion notification (Agent or background Bash).",
        ])

    def test_oc_block_sections(self):
        out = ha_dispatch.oc_block([("section-01", "oc:std", 0, "cmd")], unit="sections")
        self.assertEqual(out[0], "OPENCODE 1 sections (0 items) | run each in the BACKGROUND "
                                 "(Bash run_in_background) in the SAME message:")
        self.assertEqual(out[1], "  section-01 oc:std (0 items) → cmd")


class SlotsTest(unittest.TestCase):
    def _ctx(self):
        state = {
            "batches": {
                "batch-01": {"ids": ["R1"], "backend": "oc:std", "dispatched": 10.0},
                "batch-02": {"ids": ["R2"], "backend": "oc:std", "dispatched": 10.0},
                "batch-03": {"ids": ["R3"], "backend": "claude", "dispatched": 10.0},
                "batch-04": {"ids": ["R4"], "backend": "claude", "dispatched": 10.0},
                "batch-05": {"ids": ["R5"], "backend": "oc:lite", "dispatched": 10.0},
                "batch-06": {"ids": ["R6"], "backend": "oc:std", "dispatched": None},
                "batch-07": {"ids": ["R7"], "backend": "oc:lite", "dispatched": 10.0},
                "batch-08": {"ids": ["R8"], "backend": "claude", "dispatched": 10.0},
            },
            "verify": {
                "batch-V01": {"ids": ["R1"], "backend": "claude", "dispatched": 20.0},
                "batch-V02": {"ids": ["R2"], "backend": "oc:std", "dispatched": 20.0},
            },
            "hedges": {"batch-02": 50.0, "batch-08": 50.0},
        }
        return FakeCtx("/tmp/out", state, cap=3)

    def _merged(self):
        return FakeMerged(batch_done={"batch-04"}, vdone={"batch-V02"}, failed={"batch-07"},
                          events={"batch-05": {"ok": True}})

    def test_backend_running(self):
        running = ha_dispatch.backend_running(self._ctx(), self._merged())
        self.assertEqual(running, {"claude": 5, "oc:std": 2, "oc:lite": 0})

    def test_free_slots(self):
        self.assertEqual(ha_dispatch.free_slots(self._ctx(), self._merged()),
                         {"claude": 0, "oc:std": 4, "oc:lite": 2, "oc": 6})

    def test_free_slots_clamp_each_tier_and_the_shared_pool_to_8(self):
        routing = json.loads(json.dumps(ROUTING))
        routing["tiers"]["std"]["max_parallel"] = 64
        routing["tiers"]["lite"]["max_parallel"] = 64
        free = ha_dispatch.free_slots(FakeCtx("/tmp/out", {}, routing=routing), FakeMerged())
        self.assertEqual((free["oc:std"], free["oc:lite"], free["oc"]), (8, 8, 8))
        for _ in range(8):
            self.assertTrue(ha_dispatch.has_slot(free, "oc:lite"))
            ha_dispatch.take_slot(free, "oc:lite")
        self.assertFalse(ha_dispatch.has_slot(free, "oc:std"))

    def test_free_slots_never_negative(self):
        c = self._ctx()
        c.state["cap"] = 1
        free = ha_dispatch.free_slots(c, FakeMerged())
        self.assertEqual(free["claude"], 0)
        self.assertEqual(free["oc:std"], 3)
        self.assertEqual(free["oc:lite"], 0)


class HarvestTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.out = self.tmp / "out"
        (self.out / "events").mkdir(parents=True)

    def _event(self, name, role, ok, reason, message=""):
        ev = {"batch": name, "ok": ok, "agent_type": "opencode:ha-%s" % role, "backend": "oc:std",
              "reason": reason, "message": message, "rounds": 1, "written": 0, "total": 2, "t": 500.0}
        (self.out / "events" / ("%s.json" % name)).write_text(json.dumps(ev), encoding="utf-8")
        return ev

    def test_auth_falls_back_and_keeps_the_message(self):
        ev = self._event("batch-01", "investigator", False, "auth", "401 Unauthorized")
        state = {"batches": {"batch-01": {"ids": ["R1", "R2"], "backend": "oc:std", "dispatched": 100.0}}}
        c = FakeCtx(self.out, state)
        m = FakeMerged(failed={"batch-01"}, events={"batch-01": ev}, finding={"R1": {"id": "R1"}})
        got = ha_dispatch.harvest_oc_events(c, m, 1000.0)
        self.assertEqual(got, [{"name": "batch-01", "role": "investigator", "reason": "auth",
                                "ids": ["R2"], "message": "401 Unauthorized"}])
        self.assertEqual(state["batches"]["batch-01"]["backend"], "claude")
        self.assertEqual(state["fallbacks"], {"batch-01": "auth"})
        self.assertNotIn("cooldown", state)
        self.assertNotIn("batch-01", m.events)
        self.assertNotIn("batch-01", m.failed)
        self.assertFalse((self.out / "events" / "batch-01.json").exists())
        self.assertTrue((self.out / "oc" / "batch-01.event.json").exists())

    def test_throttle_sets_cooldown_for_verifier(self):
        ev = self._event("batch-V01", "verifier", False, "throttle", "429")
        state = {"batches": {}, "verify": {"batch-V01": {"ids": ["R1", "R2"], "backend": "oc:std",
                                                         "dispatched": 100.0}}}
        c = FakeCtx(self.out, state)
        m = FakeMerged(failed={"batch-V01"}, events={"batch-V01": ev}, finding={"R1": {"id": "R1"}})
        got = ha_dispatch.harvest_oc_events(c, m, 1000.0)
        self.assertEqual(got, [{"name": "batch-V01", "role": "verifier", "reason": "throttle",
                                "ids": ["R1", "R2"], "message": "429"}])
        self.assertEqual(state["cooldown"], {"std": 1120.0})
        self.assertEqual(state["verify"]["batch-V01"]["backend"], "claude")

    def test_breaker_event_falls_back_without_a_cooldown(self):
        ev = self._event("batch-02", "investigator", False, "breaker", "circuit breaker open for tier std")
        state = {"batches": {"batch-02": {"ids": ["R3"], "backend": "oc:std", "dispatched": 100.0}}}
        c = FakeCtx(self.out, state)
        m = FakeMerged(events={"batch-02": ev})
        got = ha_dispatch.harvest_oc_events(c, m, 1000.0)
        self.assertEqual([(g["name"], g["reason"], g["ids"]) for g in got],
                         [("batch-02", "breaker", ["R3"])])
        self.assertNotIn("cooldown", state)
        self.assertEqual(state["batches"]["batch-02"]["backend"], "claude")

    def test_section_returns_no_ids(self):
        ev = self._event("section-02", "parser", False, "format")
        state = {"batches": {}, "parse": {"backends": {"section-02": "oc:std"}}}
        c = FakeCtx(self.out, state)
        m = FakeMerged(events={"section-02": ev})
        got = ha_dispatch.harvest_oc_events(c, m, 1000.0)
        self.assertEqual(got, [{"name": "section-02", "role": "parser", "reason": "format",
                                "ids": [], "message": ""}])
        self.assertEqual(state["parse"]["backends"]["section-02"], "claude")

    def test_ok_claude_and_known_events_are_ignored(self):
        ok = self._event("batch-01", "investigator", True, None)
        known = self._event("batch-02", "investigator", False, "stall")
        claude_ev = {"batch": "batch-03", "ok": False, "agent_type": "claude-req-audit:claude-rca-investigator"}
        state = {"batches": {
            "batch-01": {"ids": ["R1"], "backend": "oc:std", "dispatched": 1.0},
            "batch-02": {"ids": ["R2"], "backend": "claude", "dispatched": 1.0},
            "batch-03": {"ids": ["R3"], "backend": "claude", "dispatched": 1.0},
        }, "fallbacks": {"batch-02": "stall"}}
        c = FakeCtx(self.out, state)
        m = FakeMerged(events={"batch-01": ok, "batch-02": known, "batch-03": claude_ev})
        self.assertEqual(ha_dispatch.harvest_oc_events(c, m, 1000.0), [])
        self.assertIn("batch-01", m.events)
        self.assertIn("batch-03", m.events)
        self.assertTrue((self.out / "events" / "batch-01.json").exists())


class HedgeTest(unittest.TestCase):
    def _setup(self, n_done, took=10.0):
        batches, done, times = {}, set(), {}
        for i in range(1, 5):
            name = "batch-%02d" % i
            batches[name] = {"ids": ["R%d" % i], "backend": "oc:std", "dispatched": 1.0}
            if i <= n_done:
                done.add(name)
                times[name] = 1.0 + took
        batches["batch-05"] = {"ids": ["R5"], "backend": "claude", "dispatched": 1.0}
        c = FakeCtx("/tmp/out", {"batches": batches})
        m = FakeMerged(batch_done=done, batch_time=times)
        return c, m

    def test_hedges_after_half_done_and_past_threshold(self):
        c, m = self._setup(2)
        late = 1.0 + audit.HEDGE_MIN_SECONDS + 1.0
        self.assertTrue(ha_dispatch.should_hedge_oc(c, m, "batch-04", late))

    def test_not_before_threshold(self):
        c, m = self._setup(2)
        early = 1.0 + audit.HEDGE_MIN_SECONDS - 1.0
        self.assertFalse(ha_dispatch.should_hedge_oc(c, m, "batch-04", early))

    def test_not_before_half_done(self):
        c, m = self._setup(1)
        self.assertFalse(ha_dispatch.should_hedge_oc(c, m, "batch-04", 1.0e9))

    def test_median_doubles_threshold(self):
        slow = 4.0 * audit.HEDGE_MIN_SECONDS
        c, m = self._setup(2, took=slow)
        self.assertFalse(ha_dispatch.should_hedge_oc(c, m, "batch-04", 1.0 + 1.5 * slow))
        self.assertTrue(ha_dispatch.should_hedge_oc(c, m, "batch-04", 1.0 + 3.0 * slow))

    def test_queued_batch_waiting_for_a_slot_is_never_hedged(self):
        c, m = self._setup(2)
        c.state["batches"]["batch-04"]["dispatched"] = None  # planned on oc:std, no free slot yet
        self.assertFalse(ha_dispatch.should_hedge_oc(c, m, "batch-04", 1.0e9))
        c.state["batches"]["batch-04"]["dispatched"] = 1.0e9  # slot freed: the clock starts now
        self.assertFalse(ha_dispatch.should_hedge_oc(c, m, "batch-04", 1.0e9 + audit.HEDGE_MIN_SECONDS - 1.0))
        self.assertTrue(ha_dispatch.should_hedge_oc(c, m, "batch-04", 1.0e9 + audit.HEDGE_MIN_SECONDS + 1.0))

    def test_never_for_claude_done_or_hedged(self):
        c, m = self._setup(2)
        self.assertFalse(ha_dispatch.should_hedge_oc(c, m, "batch-05", 1.0e9))
        self.assertFalse(ha_dispatch.should_hedge_oc(c, m, "batch-01", 1.0e9))
        c.state["hedges"] = {"batch-04": 5.0}
        self.assertFalse(ha_dispatch.should_hedge_oc(c, m, "batch-04", 1.0e9))
        self.assertFalse(ha_dispatch.should_hedge_oc(c, m, "batch-99", 1.0e9))


if __name__ == "__main__":
    unittest.main()
