import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import bslane  # noqa: E402


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def test_lanes_dir_is_created_under_superpowers(self):
        d = bslane.lanes_dir(self.root)
        self.assertEqual(d, self.root / ".superpowers" / "brainstorm" / "lanes")
        self.assertTrue(d.is_dir())

    def test_acquire_slot_caps_parallel_lanes(self):
        lanes = bslane.lanes_dir(self.root)
        a = bslane.acquire_slot(lanes, "lite", 2, 0)
        b = bslane.acquire_slot(lanes, "lite", 2, 0)
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertIsNone(bslane.acquire_slot(lanes, "lite", 2, 0))
        bslane.release_slot(a)
        c = bslane.acquire_slot(lanes, "lite", 2, 0)
        self.assertIsNotNone(c)
        bslane.release_slot(b)
        bslane.release_slot(c)
        self.assertTrue((lanes / "slots" / "lite.0.lock").exists())
        self.assertTrue((lanes / "slots" / "lite.1.lock").exists())

    def test_record_appends_and_stats_aggregate(self):
        base = {"t": "2026-09-28T00:00:00Z", "role": "locate", "backend": "oc:lite", "tier": "lite",
                "model": "zai-coding-plan/glm-5.3-flash", "variant": "low"}
        zero = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
        bslane.record(self.root, dict(base, id="a", outcome="ok", reason="", grounded=3, total=3, duration_s=10.0,
                                      tokens={"input": 100, "output": 10, "reasoning": 0, "cache_read": 5,
                                              "cache_write": 0}))
        bslane.record(self.root, dict(base, id="b", outcome="fallback", reason="grounding", grounded=1, total=3,
                                      duration_s=20.0,
                                      tokens={"input": 50, "output": 5, "reasoning": 0, "cache_read": 0,
                                              "cache_write": 0}))
        bslane.record(self.root, dict(base, id="c", outcome="fallback", reason="busy", grounded=0, total=0,
                                      duration_s=0.0, tokens=zero))
        path = self.root / ".superpowers" / "brainstorm" / "lanes.jsonl"
        self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 3)
        stats = bslane.lane_stats(path)
        self.assertEqual(len(stats), 1)
        s = stats[0]
        self.assertEqual((s["role"], s["tier"], s["lanes"], s["fallbacks"]), ("locate", "lite", 3, 2))
        self.assertEqual(s["reasons"], {"grounding": 1, "busy": 1})
        self.assertAlmostEqual(s["fallback_rate"], 0.667)
        self.assertAlmostEqual(s["grounding_pass_rate"], 0.5)
        self.assertAlmostEqual(s["median_s"], 10.0)
        self.assertEqual(s["tokens"]["input"], 150)
        self.assertEqual(s["tokens"]["output"], 15)
        self.assertEqual(s["tokens"]["cache_read"], 5)

    def test_lane_stats_missing_file_is_empty(self):
        self.assertEqual(bslane.lane_stats(self.root / "nope.jsonl"), [])


BSLANE = Path(__file__).resolve().parents[1] / "scripts" / "bslane.py"

FAKE_OPENCODE = r'''#!/usr/bin/env python3
import json, os, sys, time
log = os.environ.get("HB_FAKE_LOG")
if log:
    with open(log, "a") as fh:
        fh.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(), "pwd": os.environ.get("PWD", ""),
                             "config": bool(os.environ.get("OPENCODE_CONFIG_CONTENT"))}) + "\n")
if "--version" in sys.argv[1:]:
    print("2.0.18")
    sys.exit(0)
if sys.argv[1:2] == ["models"]:
    if os.environ.get("HB_FAKE_MODELS") != "none":
        print("zai-coding-plan/glm-5.3")
        print("zai-coding-plan/glm-5.3-flash")
    sys.exit(0)
if len(sys.argv) < 2 or sys.argv[1] != "run":
    sys.exit(0)
path = os.environ.get("HB_FAKE_SCRIPT")
script = json.load(open(path)) if path and os.path.exists(path) else {}
if isinstance(script, list):
    n = int(open(path + ".calls").read() or 0) if os.path.exists(path + ".calls") else 0
    open(path + ".calls", "w").write(str(n + 1))
    script = script[min(n, len(script) - 1)]
if script.get("switch_file"):
    with open(script["switch_file"], "w") as fh:
        json.dump({"unit": "other", "tier": "lite", "spec": "s", "kind": "crash", "detail": "d"}, fh)
for ev in script.get("events", []):
    sys.stdout.write(json.dumps(ev) + "\n")
    sys.stdout.flush()
    time.sleep(script.get("delay", 0))
time.sleep(script.get("sleep", 0))
sys.stderr.write(script.get("stderr", ""))
sys.exit(script.get("rc", 0))
'''

SHARED_MODELS = {
    "HYBRID_OPENCODE_STD": "zai-coding-plan/glm-5.3#high",
    "HYBRID_OPENCODE_LITE": "zai-coding-plan/glm-5.3-flash#low",
}

DEFAULT_ROUTING = {
    "preset": "hybrid",
    "tiers": {
        "std": {"max_parallel": 6, "stall_s": 90, "timeout_s": 300},
        "lite": {"max_parallel": 6, "stall_s": 60, "timeout_s": 180},
    },
    "roles": {"locate": "lite", "explore": "std", "fact": "lite", "research": "claude", "draft": "claude"},
    "max_roles": {"research": "std", "draft": "std"},
    "slot_wait_s": 60,
    "throttle_cooldown_s": 120,
}

CODE_OK = "FINDINGS:\n- app.py:2 `handler` takes the request\n- app.py:3 `getcwd` builds the response"
CODE_BAD = "FINDINGS:\n- missing.py:4 `ghost` does the work\n- nowhere.py:9 `phantom` is called"
WEB_OK = ('ANSWER: Version 2.0 shipped on 2024-12-06.\nCLAIMS:\n'
          '- "version 2.0 shipped on 2024-12-06" — https://example.com/releases')
AUTH_FAIL = {"events": [{"type": "error", "sessionID": "ses_1",
                         "error": {"type": "ProviderAuthError", "message": "401 Unauthorized: invalid api key"}}],
             "rc": 1}


def ev_text(text):
    return {"type": "text", "sessionID": "ses_1", "part": {"type": "text", "text": text}}


def ev_step(reason=None):
    part = {"type": "step-finish",
            "tokens": {"input": 120, "output": 30, "reasoning": 5, "cache": {"read": 10, "write": 0}},
            "cost": 0}
    if reason:
        part["reason"] = reason
    return {"type": "step_finish", "sessionID": "ses_1", "part": part}


def ev_tool(tool, url, output):
    return {"type": "tool_use", "sessionID": "ses_1",
            "part": {"type": "tool", "tool": tool,
                     "state": {"status": "completed", "input": {"url": url}, "output": output}}}


def ev_error(etype, message):
    return {"type": "error", "sessionID": "ses_1", "error": {"type": etype, "message": message}}


class HeldStatsTests(unittest.TestCase):
    def test_held_lanes_count_as_fallbacks(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            zero = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
            base = {"role": "locate", "tier": "lite", "grounded": 0, "total": 0, "duration_s": 0.0, "tokens": zero}
            bslane.record(root, dict(base, id="h1", outcome="held", reason="auth"))
            bslane.record(root, dict(base, id="h2", outcome="ok", reason=""))
            stats = bslane.lane_stats(root / ".superpowers" / "brainstorm" / "lanes.jsonl")
            self.assertEqual((stats[0]["lanes"], stats[0]["fallbacks"]), (2, 1))
            self.assertEqual(stats[0]["reasons"], {"auth": 1})


class LaneCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.base = base
        self.root = base / "repo"
        self.root.mkdir()
        (self.root / "app.py").write_text("import os\ndef handler(request):\n    return os.getcwd()\n",
                                          encoding="utf-8")
        self.home = base / "home"
        self.home.mkdir()
        self.fake = base / "fake_opencode.py"
        self.fake.write_text(FAKE_OPENCODE, encoding="utf-8")
        self.fake.chmod(0o755)
        self.log = base / "fake.log"
        self.script = base / "script.json"
        self.routing_path = base / "routing.json"
        self.shared_env = dict(SHARED_MODELS)
        self.doctor_path = base / "doctor.json"
        self.lanes = self.root / ".superpowers" / "brainstorm" / "lanes"
        self.telemetry = self.root / ".superpowers" / "brainstorm" / "lanes.jsonl"
        self.write_config()

    def tearDown(self):
        self.tmp.cleanup()

    def write_config(self, routing_lite=None, slot_wait_s=5):
        routing = json.loads(json.dumps(DEFAULT_ROUTING))
        routing["slot_wait_s"] = slot_wait_s
        if routing_lite:
            routing["tiers"]["lite"].update(routing_lite)
        self.routing_path.write_text(json.dumps(routing), encoding="utf-8")
        rc, out = self.run_cli("doctor", env_extra={"HB_FAKE_LOG": ""})
        self.assertEqual(rc, 0, out)
        data = json.loads(self.doctor_path.read_text(encoding="utf-8"))
        data["websearch"] = True
        self.doctor_path.write_text(json.dumps(data), encoding="utf-8")

    def run_cli(self, *args, script=None, oc_bin=None, env_extra=None):
        if script is not None:
            self.script.write_text(json.dumps(script), encoding="utf-8")
            Path(str(self.script) + ".calls").unlink(missing_ok=True)
        env = dict(os.environ, HOME=str(self.home), XDG_DATA_HOME=str(self.home / "xdg"), HYBRID_OC_RETRY_DELAY_S="0",
                   HB_ROUTING=str(self.routing_path),
                   HB_DOCTOR_CACHE=str(self.doctor_path), HB_OC_BIN=str(oc_bin or self.fake),
                   HB_FAKE_SCRIPT=str(self.script), HB_FAKE_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")
        env.pop("HYBRID_OPENCODE_STD", None)
        env.pop("HYBRID_OPENCODE_LITE", None)
        env.update(self.shared_env)
        if env_extra:
            env.update(env_extra)
        proc = subprocess.run([sys.executable, str(BSLANE)] + list(args), cwd=str(self.root), env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                              timeout=90)
        return proc.returncode, proc.stdout

    def code_lane(self, lane_id, *extra, script=None, oc_bin=None):
        return self.run_cli("code", "--id", lane_id, "--role", "locate", "--task", "add login audit",
                            "--slice", "app.py", "--siblings", "none", "--question", "where is the handler?",
                            *extra, script=script, oc_bin=oc_bin)

    def run_calls(self):
        if not self.log.exists():
            return []
        calls = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [c for c in calls if c["argv"] and c["argv"][0] == "run"]

    def last_record(self):
        return json.loads(self.telemetry.read_text(encoding="utf-8").splitlines()[-1])

    def claude_text(self, lane_id, role="locate", model=""):
        return bslane.claude_line(lane_id, role, self.lanes / "{}.claude.md".format(lane_id), model)

    def assertFallback(self, rc, out, lane_id, reason, role="locate", model=""):
        self.assertEqual(rc, 3, out)
        lines = out.splitlines()
        oc_lines = [line for line in lines if line.startswith("OC-")]
        rest = [line for line in lines if not line.startswith("OC-")]
        self.assertTrue(rest[0].startswith("FALLBACK {} ({})".format(lane_id, reason)), out)
        self.assertEqual(rest[1], self.claude_text(lane_id, role, model), out)
        rec = self.last_record()
        self.assertEqual((rec["outcome"], rec["reason"]), ("fallback", reason))
        return oc_lines

    def assertRetriedThenSwitched(self, rc, out, lane_id, kind):
        """3 OC-WARN retry lines, the unit's OC-ERROR, one kind=switch line, then a sonnet fallback (4 runs)."""
        oc_lines = self.assertFallback(rc, out, lane_id, kind, model="sonnet")
        self.assertEqual(len(oc_lines), 5, out)
        for n, line in enumerate(oc_lines[:3], 1):
            self.assertRegex(line, r"^OC-WARN hybrid-brainstorming {} tier=lite .*kind={} :: retry {}/3 in 0s: "
                             .format(lane_id, kind, n))
        self.assertRegex(oc_lines[3], r"^OC-ERROR hybrid-brainstorming {} tier=lite .*kind={} :: ".format(lane_id, kind))
        self.assertRegex(oc_lines[4], r"^OC-ERROR hybrid-brainstorming {} tier=lite .*kind=switch :: opencode {}: .*; "
                                      r"the rest of this run uses Claude sonnet$".format(lane_id, kind))
        self.assertEqual(len(self.run_calls()), 4)
        self.assertTrue((self.lanes / "oc-switched.json").exists())
        logged = (self.lanes / "oc-errors.jsonl").read_text(encoding="utf-8")
        self.assertEqual(logged.count("kind=switch"), 1)
        self.assertEqual(logged.count("retry "), 3)
        return oc_lines

    def test_preset_claude_spawns_nothing_and_writes_prompt(self):
        rc, out = self.code_lane("c9", "--preset", "claude")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), self.claude_text("c9"))
        self.assertIn(str(self.lanes / "c9.claude.md"), out)
        self.assertTrue((self.lanes / "c9.claude.md").read_text(encoding="utf-8").strip())
        self.assertFalse(self.log.exists())
        self.assertEqual(self.last_record()["outcome"], "claude")

    def test_code_lane_ok_prints_grounded_result_and_records(self):
        rc, out = self.code_lane("c1", script={"events": [ev_text(CODE_OK), ev_step()]})
        self.assertEqual(rc, 0)
        first = out.strip().splitlines()[0]
        self.assertRegex(first, r"^LANE c1 locate oc:lite OK — grounded \d+/\d+ — \d+s$")
        self.assertIn("app.py:2", out)
        self.assertTrue((self.lanes / "c1.out.md").exists())
        calls = self.run_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["cwd"], str(self.root))
        self.assertEqual(calls[0]["pwd"], str(self.root))
        self.assertTrue(calls[0]["config"])
        rec = self.last_record()
        self.assertEqual((rec["outcome"], rec["backend"], rec["tier"]), ("ok", "oc:lite", "lite"))
        self.assertEqual(rec["model"], "zai-coding-plan/glm-5.3-flash")
        self.assertEqual(rec["tokens"]["input"], 120)
        self.assertGreater(rec["total"], 0)

    def test_web_fact_lane_ok(self):
        page = "Release notes: version 2.0 shipped on 2024-12-06 with streaming support."
        rc, out = self.run_cli("web", "--id", "w1", "--role", "fact", "--task", "add streaming",
                               "--stack", "python", "--angle", "release date", "--siblings", "none",
                               "--question", "when did 2.0 ship?",
                               script={"events": [ev_tool("webfetch", "https://example.com/releases", page),
                                                  ev_text(WEB_OK), ev_step()]})
        self.assertEqual(rc, 0)
        self.assertRegex(out.strip().splitlines()[0], r"^LANE w1 fact oc:lite OK — grounded \d+/\d+ — \d+s$")

    def make_context(self):
        ctx = self.root / ".superpowers" / "drafts" / "ctx.md"
        ctx.parent.mkdir(parents=True, exist_ok=True)
        ctx.write_text("Constraints: stdlib only.\nFinding: app.py:2 handler.\n", encoding="utf-8")
        return ctx

    def draft_lane(self, lane_id, preset, script=None):
        return self.run_cli("draft", "--id", lane_id, "--lens", "reuse", "--task", "add login audit",
                            "--context-file", str(self.make_context()), "--preset", preset, script=script)

    def test_draft_lane_is_ungrounded_in_opencode_preset(self):
        rc, out = self.draft_lane("d1", "opencode",
                                  script={"events": [ev_text("APPROACH: wrap handler with an audit decorator"),
                                                     ev_step()]})
        self.assertEqual(rc, 0)
        self.assertRegex(out.strip().splitlines()[0], r"^LANE d1 draft oc:std OK — ungrounded — \d+s$")
        self.assertIn("APPROACH", out)

    def test_draft_lane_strips_the_lane_sentinel(self):
        rc, out = self.draft_lane("d3", "opencode",
                                  script={"events": [ev_text("APPROACH: wrap handler\nHB-LANE-OK"), ev_step()]})
        self.assertEqual(rc, 0)
        self.assertIn("APPROACH: wrap handler", out)
        self.assertNotIn("HB-LANE-OK", out)
        self.assertNotIn("HB-LANE-OK", (self.lanes / "d3.out.md").read_text(encoding="utf-8"))

    def test_preset_max_maps_to_opencode_with_a_config_warning(self):
        rc, out = self.draft_lane("d2", "max",
                                  script={"events": [ev_text("APPROACH: wrap handler"), ev_step()]})
        self.assertEqual(rc, 0)
        lines = out.strip().splitlines()
        self.assertRegex(lines[0], r"^OC-WARN hybrid-brainstorming d2 .*kind=config")
        self.assertRegex(lines[1], r"^LANE d2 draft oc:std OK — ungrounded — \d+s$")

    def test_unknown_preset_is_a_config_error_and_never_becomes_claude(self):
        rc, out = self.code_lane("p1", "--preset", "turbo")
        self.assertEqual(rc, 3)
        lines = out.strip().splitlines()
        self.assertRegex(lines[0], r"^OC-ERROR hybrid-brainstorming p1 .*kind=config")
        self.assertTrue(lines[1].startswith("HELD p1"), out)
        self.assertNotIn(self.claude_text("p1"), out)
        self.assertEqual(self.run_calls(), [])

    def test_fallback_spawn(self):
        rc, out = self.code_lane("s1", oc_bin=self.base / "no-such-opencode")
        oc_lines = self.assertFallback(rc, out, "s1", "spawn", model="sonnet")
        self.assertRegex(oc_lines[3], r"^OC-ERROR hybrid-brainstorming s1 tier=lite .*kind=spawn :: spawn failed")
        self.assertRegex(oc_lines[4], r"kind=switch :: opencode spawn: ")

    def test_fallback_crash(self):
        rc, out = self.code_lane("k1", script={"events": [ev_error("UnknownError", "kaboom")], "rc": 1})
        oc_lines = self.assertRetriedThenSwitched(rc, out, "k1", "crash")
        self.assertRegex(oc_lines[3], r"^OC-ERROR hybrid-brainstorming k1 tier=lite .*kind=crash :: .*kaboom")

    def test_auth_failure_reports_the_error_and_trips_the_breaker(self):
        rc, out = self.code_lane("a1", script=AUTH_FAIL)
        oc_lines = self.assertFallback(rc, out, "a1", "auth", model="sonnet")
        self.assertEqual(len(oc_lines), 2)
        self.assertRegex(oc_lines[0], r"^OC-ERROR hybrid-brainstorming a1 tier=lite model=\S*glm-5\.3-flash\S* "
                                      r"kind=auth :: .*invalid api key")
        self.assertRegex(oc_lines[0], r" log=\S+a1\.(err|jsonl)$")
        self.assertRegex(oc_lines[1], r"kind=switch :: opencode auth: .*; the rest of this run uses Claude sonnet$")
        self.assertIn("kind=auth", (self.lanes / "oc-errors.jsonl").read_text(encoding="utf-8"))
        rc, out = self.code_lane("a2", script=AUTH_FAIL)
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), self.claude_text("a2", model="sonnet"))
        self.assertEqual(len(self.run_calls()), 1)

    def test_opencode_preset_holds_a_failed_lane_and_the_breaker_holds_the_next(self):
        rc, out = self.code_lane("h1", "--preset", "opencode", script=AUTH_FAIL)
        self.assertEqual(rc, 3)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 2, out)
        self.assertRegex(lines[0], r"^OC-ERROR hybrid-brainstorming h1 tier=lite .*kind=auth")
        self.assertTrue(lines[1].startswith("HELD h1 (auth)"), out)
        self.assertEqual(self.last_record()["outcome"], "held")
        rc, out = self.code_lane("h2", "--preset", "opencode", script=AUTH_FAIL)
        self.assertEqual(rc, 3)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 1, out)  # the trip already printed the root cause: no per-lane OC line
        self.assertTrue(lines[0].startswith("HELD h2 (breaker)"), out)
        self.assertEqual(len(self.run_calls()), 1)
        rc, out = self.run_cli("stats")
        self.assertRegex(out.splitlines()[0], r"^OC-ERROR hybrid-brainstorming breaker tier=lite .*kind=breaker :: "
                                              r"1 units skipped after kind=auth")

    def test_opencode_preset_holds_a_lane_whose_doctor_refresh_fails(self):
        self.doctor_path.unlink()
        rc, out = self.code_lane("u1", "--preset", "opencode", oc_bin=self.base / "no-such-opencode")
        self.assertEqual(rc, 3)
        lines = out.strip().splitlines()
        self.assertRegex(lines[0], r"^OC-ERROR hybrid-brainstorming u1 tier=lite .*kind=spawn")
        self.assertTrue(lines[1].startswith("HELD u1 (spawn)"), out)
        self.assertNotIn(self.claude_text("u1"), out)
        self.assertEqual(self.run_calls(), [])

    PING_OK = {"events": [ev_text("HB-LANE-OK"), ev_step("stop")]}

    def test_missing_doctor_cache_is_refreshed_with_a_ping_and_the_lane_runs_on_opencode(self):
        self.doctor_path.unlink()
        lane = {"events": [ev_text(CODE_OK), ev_step()]}
        rc, out = self.code_lane("dr1", script=[self.PING_OK, self.PING_OK, lane])
        self.assertEqual(rc, 0, out)
        self.assertRegex(out.strip().splitlines()[0], r"^LANE dr1 locate oc:lite OK")
        self.assertEqual(len(self.run_calls()), 3)  # ping lite, ping std (no web probe in hybrid), the lane
        data = json.loads(self.doctor_path.read_text(encoding="utf-8"))
        self.assertTrue(data["tiers"]["lite"]["ok"] and data["tiers"]["std"]["ok"])
        self.assertEqual(data["tiers"]["lite"]["detail"], "ping ok")

    def test_stale_doctor_entry_is_refreshed_once_for_parallel_lanes(self):
        data = json.loads(self.doctor_path.read_text(encoding="utf-8"))
        for entry in data["tiers"].values():
            entry["checked_at"] -= 3600
        self.doctor_path.write_text(json.dumps(data), encoding="utf-8")
        self.script.write_text(json.dumps([self.PING_OK, self.PING_OK, {"events": [ev_text(CODE_OK), ev_step()]}]),
                               encoding="utf-8")
        Path(str(self.script) + ".calls").unlink(missing_ok=True)
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(3) as pool:
            results = list(pool.map(lambda n: self.code_lane("pl%d" % n), range(3)))
        for rc, out in results:
            self.assertEqual(rc, 0, out)
            self.assertRegex(out.strip().splitlines()[0], r"^LANE pl\d locate oc:lite OK")
        argvs = [c["argv"] for c in self.run_calls()]
        self.assertEqual(len(argvs), 2 + 3)  # one refresh (two pings) under the lock, then three lanes

    def test_failed_doctor_ping_is_reported_and_the_hybrid_lane_falls_back(self):
        self.doctor_path.unlink()
        rc, out = self.code_lane("dr2", script=AUTH_FAIL)
        oc_lines = self.assertFallback(rc, out, "dr2", "auth")
        self.assertRegex(oc_lines[0], r"^OC-ERROR hybrid-brainstorming dr2 tier=lite .*kind=auth :: .*invalid api key")
        self.assertFalse((self.lanes / "oc-switched.json").exists())

    def test_doctor_refresh_failure_holds_or_falls_back_with_an_oc_line(self):
        self.doctor_path.unlink()
        rc, out = self.code_lane("dr3", oc_bin=self.base / "no-such-opencode")
        oc_lines = self.assertFallback(rc, out, "dr3", "spawn")
        self.assertRegex(oc_lines[0], r"^OC-ERROR hybrid-brainstorming dr3 tier=lite .*kind=spawn")

    def test_lane_pinned_to_claude_prints_no_oc_line_and_needs_no_doctor(self):
        self.doctor_path.unlink()
        rc, out = self.draft_lane("pc1", "hybrid")
        self.assertEqual((rc, out.strip()), (0, self.claude_text("pc1", "draft")))
        self.assertFalse(self.doctor_path.exists())
        rc, out = self.run_cli("web", "--id", "pc2", "--role", "research", "--task", "x", "--preset", "opencode",
                               "--backend", "claude")
        self.assertEqual((rc, out.strip()), (0, self.claude_text("pc2", "research")))

    def test_opencode_preset_routes_a_role_pinned_to_claude_to_claude(self):
        routing = json.loads(self.routing_path.read_text(encoding="utf-8"))
        routing["roles"]["fact"] = "claude"  # no max_roles entry for fact
        self.routing_path.write_text(json.dumps(routing), encoding="utf-8")
        rc, out = self.run_cli("web", "--id", "pc3", "--role", "fact", "--task", "t", "--preset", "opencode")
        self.assertEqual((rc, out.strip()), (0, self.claude_text("pc3", "fact")))

    def test_held_explicit_backend_reports_the_requested_tier(self):
        data = json.loads(self.doctor_path.read_text(encoding="utf-8"))
        data["tiers"]["std"].update(ok=False, kind="auth", detail="401 nope")
        self.doctor_path.write_text(json.dumps(data), encoding="utf-8")
        rc, out = self.code_lane("bk1", "--preset", "opencode", "--backend", "oc:std")
        self.assertEqual(rc, 3)
        self.assertRegex(out.splitlines()[0], r"^OC-ERROR hybrid-brainstorming bk1 tier=std .*kind=auth :: 401 nope")
        self.assertEqual(self.last_record()["tier"], "std")

    def test_hybrid_unserved_tier_prints_an_oc_error_then_falls_back(self):
        data = json.loads(self.doctor_path.read_text(encoding="utf-8"))
        data["tiers"]["lite"].update(ok=False, kind="model", detail="model gone")
        self.doctor_path.write_text(json.dumps(data), encoding="utf-8")
        rc, out = self.code_lane("hu1")
        oc_lines = self.assertFallback(rc, out, "hu1", "model")
        self.assertRegex(oc_lines[0], r"^OC-ERROR hybrid-brainstorming hu1 tier=lite .*kind=model :: model gone")
        self.assertEqual(self.run_calls(), [])

    def test_cooldown_and_busy_print_oc_errors_in_hybrid_too(self):
        self.lanes.mkdir(parents=True, exist_ok=True)
        (self.lanes / "cooldown-lite").write_text(str(time.time() + 600), encoding="utf-8")
        rc, out = self.code_lane("cd1")
        oc_lines = self.assertFallback(rc, out, "cd1", "cooldown")
        self.assertRegex(oc_lines[0], r"^OC-ERROR hybrid-brainstorming cd1 tier=lite .*kind=throttle")
        (self.lanes / "cooldown-lite").unlink()
        self.write_config(routing_lite={"max_parallel": 1}, slot_wait_s=0)
        slots = self.lanes / "slots"
        slots.mkdir(parents=True, exist_ok=True)
        held = open(slots / "lite.0.lock", "a+")
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            rc, out = self.code_lane("cd2")
        finally:
            held.close()
        oc_lines = self.assertFallback(rc, out, "cd2", "busy")
        self.assertRegex(oc_lines[0], r"^OC-ERROR hybrid-brainstorming cd2 tier=lite .*kind=timeout")

    def test_lane_queued_for_a_slot_rechecks_the_switch_after_the_wait(self):
        self.write_config(routing_lite={"max_parallel": 1}, slot_wait_s=20)
        lanes = bslane.lanes_dir(self.root)
        held = bslane.acquire_slot(lanes, "lite", 1, 0)
        env = dict(os.environ, HOME=str(self.home), XDG_DATA_HOME=str(self.home / "xdg"), HB_ROUTING=str(self.routing_path),
                   HB_DOCTOR_CACHE=str(self.doctor_path), HB_OC_BIN=str(self.fake), HB_FAKE_LOG=str(self.log),
                   HYBRID_OC_RETRY_DELAY_S="0", PYTHONDONTWRITEBYTECODE="1")
        env.pop("HYBRID_OPENCODE_STD", None)
        env.pop("HYBRID_OPENCODE_LITE", None)
        env.update(self.shared_env)
        proc = subprocess.Popen([sys.executable, str(BSLANE), "code", "--id", "q1", "--role", "locate", "--task", "t"],
                                cwd=str(self.root), env=env, stdout=subprocess.PIPE, universal_newlines=True)
        time.sleep(1.5)  # the lane is now waiting for the slot
        (lanes / "oc-switched.json").write_text(json.dumps({"unit": "other", "tier": "lite", "spec": "s",
                                                            "kind": "crash", "detail": "d"}), encoding="utf-8")
        bslane.release_slot(held)
        out, _ = proc.communicate(timeout=30)
        self.assertEqual(out.strip(), self.claude_text("q1", model="sonnet"))
        self.assertEqual(self.run_calls(), [])

    def test_lane_queued_for_a_slot_rechecks_the_breaker_after_the_wait(self):
        self.write_config(routing_lite={"max_parallel": 1}, slot_wait_s=20)
        lanes = bslane.lanes_dir(self.root)
        held = bslane.acquire_slot(lanes, "lite", 1, 0)
        env = dict(os.environ, HOME=str(self.home), XDG_DATA_HOME=str(self.home / "xdg"), HB_ROUTING=str(self.routing_path),
                   HB_DOCTOR_CACHE=str(self.doctor_path), HB_OC_BIN=str(self.fake), HB_FAKE_LOG=str(self.log),
                   HYBRID_OC_RETRY_DELAY_S="0", PYTHONDONTWRITEBYTECODE="1")
        env.pop("HYBRID_OPENCODE_STD", None)
        env.pop("HYBRID_OPENCODE_LITE", None)
        env.update(self.shared_env)
        proc = subprocess.Popen([sys.executable, str(BSLANE), "code", "--id", "q2", "--role", "locate", "--task", "t",
                                 "--preset", "opencode"],
                                cwd=str(self.root), env=env, stdout=subprocess.PIPE, universal_newlines=True)
        time.sleep(1.5)
        import hybrid_shared
        hybrid_shared.breaker_trip(lanes, "lite", "zai-coding-plan/glm-5.3-flash#low", "auth", "401")
        bslane.release_slot(held)
        out, _ = proc.communicate(timeout=30)
        self.assertTrue(out.startswith("HELD q2 (breaker)"), out)
        self.assertEqual(self.run_calls(), [])

    def test_doctor_ping_clears_the_breaker_and_cooldown_so_retry_on_opencode_works(self):
        rc, out = self.code_lane("rb1", "--preset", "opencode", script=AUTH_FAIL)
        self.assertEqual(rc, 3)
        self.lanes.mkdir(parents=True, exist_ok=True)
        (self.lanes / "cooldown-lite").write_text(str(time.time() + 600), encoding="utf-8")
        rc, out = self.code_lane("rb2", "--preset", "opencode", script=AUTH_FAIL)
        self.assertTrue(out.startswith("HELD rb2"), out)
        rc, out = self.run_cli("doctor", "--ping", "--preset", "opencode", script=self.PING_OK)
        self.assertEqual(rc, 0, out)
        self.assertIn("tier lite: breaker and cooldown cleared", out)
        self.assertFalse(list((self.lanes / "oc-breaker").glob("*.json")))
        self.assertFalse((self.lanes / "cooldown-lite").exists())
        rc, out = self.code_lane("rb3", "--preset", "opencode", script={"events": [ev_text(CODE_OK), ev_step()]})
        self.assertEqual(rc, 0, out)
        self.assertRegex(out.strip().splitlines()[0], r"^LANE rb3 locate oc:lite OK")

    def test_failed_doctor_ping_leaves_the_breaker_open(self):
        self.code_lane("rb4", "--preset", "opencode", script=AUTH_FAIL)
        rc, out = self.run_cli("doctor", "--ping", script=AUTH_FAIL)
        self.assertNotIn("breaker and cooldown cleared", out)
        self.assertTrue(list((self.lanes / "oc-breaker").glob("*.json")))

    def test_plain_doctor_keeps_websearch_found_by_a_ping(self):
        rc, out = self.run_cli("doctor", "--ping", "--preset", "opencode", script={
            "events": [ev_text("HB-LANE-OK"), ev_tool("websearch", "https://x.test", "hit"), ev_step("stop")]})
        self.assertIn("websearch: on", out)
        rc, out = self.run_cli("doctor")
        self.assertIn("websearch: on", out)
        self.assertTrue(json.loads(self.doctor_path.read_text(encoding="utf-8"))["websearch"])
        self.routing_path.write_text(json.dumps({"tiers": {"std": {"model": "zai-coding-plan/glm-5.3", "variant": "x"}}}),
                                     encoding="utf-8")  # a model edit drops the remembered answer
        rc, out = self.run_cli("doctor")
        self.assertIn("websearch: off", out)

    def test_init_stats_and_doctor_accept_and_ignore_preset(self):
        for cmd in ("init", "stats", "doctor"):
            rc, out = self.run_cli(cmd, "--preset", "opencode")
            self.assertEqual(rc, 0, (cmd, out))

    def test_init_clears_the_throttle_cooldown(self):
        self.lanes.mkdir(parents=True, exist_ok=True)
        (self.lanes / "cooldown-lite").write_text(str(time.time() + 600), encoding="utf-8")
        rc, out = self.run_cli("init")
        self.assertEqual(rc, 0, out)
        self.assertFalse((self.lanes / "cooldown-lite").exists())

    def test_wrong_typed_routing_keys_are_config_errors_not_crashes(self):
        for bad in ({"roles": [1]}, {"tiers": {"lite": {"max_parallel": "abc"}}}, {"slot_wait_s": "soon"},
                    {"tiers": {"lite": {"stall_s": None}}}, {"tiers": {"lite": "x"}}, {"preset": "turbo"}):
            routing = json.loads(json.dumps(DEFAULT_ROUTING))
            routing.update({k: v for k, v in bad.items() if k != "tiers"})
            if "tiers" in bad:
                routing["tiers"].update(bad["tiers"])
            self.routing_path.write_text(json.dumps(routing), encoding="utf-8")
            rc, out = self.code_lane("wt1")
            self.assertEqual(rc, 3, (bad, out))
            self.assertRegex(out.splitlines()[0], r"^OC-ERROR hybrid-brainstorming wt1 .*kind=config :: .*must be",
                             (bad, out))
            self.assertNotIn("kind=crash", out)
            rc, out = self.code_lane("wt2", "--preset", "opencode")
            self.assertTrue([line for line in out.splitlines() if line.startswith("HELD wt2 (config)")], (bad, out))
            rc, out = self.run_cli("doctor")
            self.assertEqual(rc, 0)
            self.assertNotIn("doctor failed", out)

    def test_unreadable_context_file_prints_an_oc_error_in_hybrid_and_opencode(self):
        for preset, head in (("hybrid", "FALLBACK"), ("opencode", "HELD")):
            rc, out = self.run_cli("draft", "--id", "cx" + preset, "--lens", "smallest", "--task", "t",
                                   "--context-file", str(self.base / "missing.md"), "--preset", preset)
            lines = out.splitlines()
            self.assertRegex(lines[0], r"^OC-ERROR hybrid-brainstorming cx\w+ .*kind=config :: cannot read context file")
            self.assertTrue(lines[1].startswith(head), out)

    def test_crash_in_opencode_mode_is_held_not_a_claude_fallback(self):
        from unittest import mock
        old = os.getcwd()
        os.chdir(str(self.root))
        try:
            for preset, head in (("opencode", "HELD"), ("hybrid", "FALLBACK")):
                with mock.patch.object(bslane, "run_lane", side_effect=RuntimeError("boom")), \
                        mock.patch("builtins.print") as printed:
                    bslane.main(["code", "--id", "cr" + preset, "--role", "locate", "--preset", preset])
                out = printed.call_args[0][0]
                self.assertRegex(out.splitlines()[0], r"^OC-ERROR .*kind=crash :: RuntimeError: boom")
                self.assertTrue(out.splitlines()[1].startswith(head + " cr"), out)
                if preset == "opencode":
                    self.assertNotIn("CLAUDE ", out)
        finally:
            os.chdir(old)
        self.assertIn("kind=crash", (self.lanes / "oc-errors.jsonl").read_text(encoding="utf-8"))

    def test_fallback_stall(self):
        self.write_config(routing_lite={"stall_s": 1, "timeout_s": 30})
        rc, out = self.code_lane("st1", script={"events": [], "sleep": 8})
        oc_lines = self.assertRetriedThenSwitched(rc, out, "st1", "stall")
        self.assertIn("kind=stall", oc_lines[3])

    def test_fallback_timeout(self):
        self.write_config(routing_lite={"stall_s": 5, "timeout_s": 1})
        rc, out = self.code_lane("to1", script={"events": [ev_step() for _ in range(40)], "delay": 0.2})
        oc_lines = self.assertFallback(rc, out, "to1", "timeout")
        self.assertEqual(len(oc_lines), 1)
        self.assertIn("kind=timeout", oc_lines[0])
        self.assertEqual(len(self.run_calls()), 1)
        self.assertFalse((self.lanes / "oc-switched.json").exists())

    def test_throttle_retries_then_switches_and_starts_cooldown(self):
        script = {"events": [ev_error("APIError", "429 Too Many Requests: rate limit exceeded")], "rc": 1}
        rc, out = self.code_lane("t1", script=script)
        oc_lines = self.assertRetriedThenSwitched(rc, out, "t1", "throttle")
        self.assertIn("kind=throttle", oc_lines[3])
        self.assertTrue((self.lanes / "cooldown-lite").exists())

    def test_cooldown_skips_spawn_and_falls_back_per_lane(self):
        self.lanes.mkdir(parents=True, exist_ok=True)
        (self.lanes / "cooldown-lite").write_text(str(time.time() + 600), encoding="utf-8")
        rc, out = self.code_lane("t2")
        self.assertFallback(rc, out, "t2", "cooldown")
        self.assertEqual(self.run_calls(), [])
        self.assertFalse((self.lanes / "oc-switched.json").exists())

    def test_fallback_busy_when_all_slots_held(self):
        self.write_config(routing_lite={"max_parallel": 1}, slot_wait_s=0)
        slots = self.lanes / "slots"
        slots.mkdir(parents=True)
        held = open(slots / "lite.0.lock", "a+")
        fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            rc, out = self.code_lane("b1", script={"events": [ev_text(CODE_OK)]})
        finally:
            fcntl.flock(held.fileno(), fcntl.LOCK_UN)
            held.close()
        self.assertFallback(rc, out, "b1", "busy")
        self.assertEqual(self.run_calls(), [])

    def test_fallback_format(self):
        rc, out = self.code_lane("f1", script={"events": [ev_text("I looked around and found nothing."),
                                                          ev_step()]})
        oc_lines = self.assertFallback(rc, out, "f1", "format")
        self.assertRegex(oc_lines[0], r"^OC-WARN hybrid-brainstorming f1 tier=lite .*kind=format")

    def test_fallback_grounding(self):
        rc, out = self.code_lane("g1", script={"events": [ev_text(CODE_BAD), ev_step()]})
        oc_lines = self.assertFallback(rc, out, "g1", "grounding")
        self.assertRegex(oc_lines[0], r"^OC-WARN hybrid-brainstorming g1 tier=lite .*kind=grounding")
        self.assertIn("UNVERIFIED", out)

    def test_empty_answer_is_a_warning_and_falls_back(self):
        rc, out = self.code_lane("e1", script={"events": [ev_step("stop")]})
        oc_lines = self.assertFallback(rc, out, "e1", "empty")
        self.assertRegex(oc_lines[0], r"^OC-WARN hybrid-brainstorming e1 tier=lite .*kind=empty")

    def test_exit_one_after_a_complete_answer_is_accepted_with_a_warning(self):
        rc, out = self.code_lane("r1", script={"events": [ev_text(CODE_OK), ev_step("stop")], "rc": 1})
        self.assertEqual(rc, 0)
        lines = out.strip().splitlines()
        self.assertRegex(lines[0], r"^OC-WARN hybrid-brainstorming r1 tier=lite .*kind=recovered")
        self.assertRegex(lines[1], r"^LANE r1 locate oc:lite OK — grounded \d+/\d+ — \d+s$")
        self.assertEqual(self.last_record()["outcome"], "ok")

    def test_exit_one_without_a_stop_finish_is_a_crash(self):
        rc, out = self.code_lane("r2", script={"events": [ev_text(CODE_OK), ev_step()], "rc": 1})
        self.assertRetriedThenSwitched(rc, out, "r2", "crash")

    CRASH = {"events": [ev_error("UnknownError", "kaboom")], "rc": 1}

    def test_retry_then_success_keeps_the_lane_on_opencode(self):
        rc, out = self.code_lane("rt1", script=[self.CRASH, {"events": [ev_text(CODE_OK), ev_step()]}])
        self.assertEqual(rc, 0, out)
        lines = out.strip().splitlines()
        self.assertEqual(len([line for line in lines if line.startswith("OC-")]), 1, out)
        self.assertRegex(lines[0], r"^OC-WARN hybrid-brainstorming rt1 tier=lite .*kind=crash :: retry 1/3 in 0s: "
                                   r".*kaboom")
        self.assertRegex(lines[1], r"^LANE rt1 locate oc:lite OK — grounded \d+/\d+ — \d+s$")
        self.assertEqual(len(self.run_calls()), 2)
        self.assertFalse((self.lanes / "oc-switched.json").exists())
        self.assertEqual(self.last_record()["outcome"], "ok")

    def test_retries_use_fresh_runs_never_a_session_continuation(self):
        self.code_lane("rt2", script=self.CRASH)
        calls = self.run_calls()
        self.assertEqual(len(calls), 4)
        self.assertTrue(all("--session" not in c["argv"] for c in calls))
        self.assertEqual(len({tuple(c["argv"]) for c in calls}), 1)

    def test_switched_run_sends_later_oc_lanes_to_claude_sonnet_without_spawning(self):
        rc, out = self.code_lane("sw1", script=self.CRASH)
        self.assertRetriedThenSwitched(rc, out, "sw1", "crash")
        rc, out = self.code_lane("sw2", script={"events": [ev_text(CODE_OK), ev_step()]})
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), self.claude_text("sw2", model="sonnet"))
        self.assertIn("subagent_type: Explore, model: sonnet", out)
        self.assertEqual(self.last_record()["outcome"], "claude")
        rc, out = self.run_cli("web", "--id", "sw3", "--role", "fact", "--task", "x", "--angle", "y",
                               "--question", "z", "--preset", "hybrid")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), self.claude_text("sw3", "fact", "sonnet"))
        self.assertIn("subagent_type: general-purpose, model: sonnet", out)
        self.assertEqual(len(self.run_calls()), 4)
        self.assertEqual((self.lanes / "oc-errors.jsonl").read_text(encoding="utf-8").count("kind=switch"), 1)

    def test_switched_run_leaves_claude_native_lanes_and_explicit_claude_backend_alone(self):
        self.code_lane("sw4", script=self.CRASH)
        rc, out = self.code_lane("sw5", "--backend", "claude")
        self.assertEqual((rc, out.strip()), (0, self.claude_text("sw5")))
        self.assertIn("model: haiku", out)
        rc, out = self.draft_lane("sw6", "hybrid")
        self.assertEqual((rc, out.strip()), (0, self.claude_text("sw6", "draft")))

    def test_switch_does_not_apply_in_preset_claude_or_opencode(self):
        self.code_lane("sw7", script=self.CRASH)
        self.assertEqual(len(self.run_calls()), 4)
        rc, out = self.code_lane("sw8", "--preset", "opencode", script={"events": [ev_text(CODE_OK), ev_step()]})
        self.assertEqual(rc, 0, out)
        self.assertRegex(out.strip().splitlines()[0], r"^LANE sw8 locate oc:lite OK")
        self.assertEqual(len(self.run_calls()), 5)

    def test_init_starts_a_new_run_unswitched_and_clears_the_breaker(self):
        self.code_lane("in1", script=AUTH_FAIL)
        self.assertTrue((self.lanes / "oc-switched.json").exists())
        self.assertTrue((self.lanes / "oc-breaker").is_dir())
        rc, out = self.run_cli("init")
        self.assertEqual(rc, 0, out)
        self.assertFalse((self.lanes / "oc-switched.json").exists())
        self.assertFalse((self.lanes / "oc-breaker").exists())
        rc, out = self.code_lane("in2", script={"events": [ev_text(CODE_OK), ev_step()]})
        self.assertEqual(rc, 0, out)
        self.assertRegex(out.strip().splitlines()[0], r"^LANE in2 locate oc:lite OK")
        self.assertEqual(len(self.run_calls()), 2)
        rc, out = self.run_cli("init")
        self.assertEqual(rc, 0, out)

    def test_lane_mid_retry_stops_spawning_once_another_lane_switched_the_run(self):
        step = dict(self.CRASH, switch_file=str(self.lanes / "oc-switched.json"))
        self.lanes.mkdir(parents=True, exist_ok=True)
        rc, out = self.code_lane("mr1", script=step)
        oc_lines = self.assertFallback(rc, out, "mr1", "crash", model="sonnet")
        self.assertEqual(len(oc_lines), 2, out)
        self.assertRegex(oc_lines[0], r"kind=crash :: retry 1/3 in 0s")
        self.assertRegex(oc_lines[1], r"^OC-ERROR hybrid-brainstorming mr1 tier=lite .*kind=crash :: ")
        self.assertNotIn("kind=switch", out)
        self.assertEqual(len(self.run_calls()), 1)

    def test_opencode_preset_retries_then_holds_without_switching(self):
        rc, out = self.code_lane("oh1", "--preset", "opencode", script=self.CRASH)
        self.assertEqual(rc, 3)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 5, out)
        for n, line in enumerate(lines[:3], 1):
            self.assertRegex(line, r"^OC-WARN hybrid-brainstorming oh1 tier=lite .*kind=crash :: retry {}/3 in 0s: "
                             .format(n))
        self.assertRegex(lines[3], r"^OC-ERROR hybrid-brainstorming oh1 tier=lite .*kind=crash :: ")
        self.assertTrue(lines[4].startswith("HELD oh1 (crash)"), out)
        self.assertNotIn("kind=switch", out)
        self.assertNotIn("CLAUDE oh1", out)
        self.assertEqual(len(self.run_calls()), 4)
        self.assertFalse((self.lanes / "oc-switched.json").exists())
        self.assertEqual(self.last_record()["outcome"], "held")

    def test_opencode_preset_auth_holds_at_once_with_no_retry_and_no_switch(self):
        rc, out = self.code_lane("oa1", "--preset", "opencode", script=AUTH_FAIL)
        self.assertEqual(rc, 3)
        self.assertEqual(len(out.strip().splitlines()), 2, out)
        self.assertEqual(len(self.run_calls()), 1)
        self.assertFalse((self.lanes / "oc-switched.json").exists())

    def test_gate_failures_never_retry_or_switch(self):
        rc, out = self.code_lane("gf1", script={"events": [ev_text(CODE_BAD), ev_step()]})
        self.assertFallback(rc, out, "gf1", "grounding")
        self.assertEqual(len(self.run_calls()), 1)
        self.assertFalse((self.lanes / "oc-switched.json").exists())

    def test_fallback_config_on_unreadable_context_file(self):
        rc, out = self.run_cli("draft", "--id", "cf1", "--lens", "smallest", "--task", "add login audit",
                               "--context-file", str(self.base / "missing.md"), "--preset", "hybrid")
        oc_lines = self.assertFallback(rc, out, "cf1", "config", role="draft")
        self.assertEqual(len(oc_lines), 1)
        self.assertRegex(oc_lines[0], r"^OC-ERROR hybrid-brainstorming cf1 .*kind=config :: cannot read context file")

    def test_invalid_shared_env_is_a_config_error_and_falls_back(self):
        self.shared_env["HYBRID_OPENCODE_STD"] = "not a spec"
        rc, out = self.code_lane("bad1")
        oc_lines = self.assertFallback(rc, out, "bad1", "config")
        self.assertRegex(oc_lines[0], r"^OC-ERROR hybrid-brainstorming bad1 .*kind=config")
        self.assertEqual(self.run_calls(), [])

    def test_unset_shared_env_is_a_config_error_and_falls_back(self):
        self.shared_env.clear()
        rc, out = self.code_lane("bad3")
        oc_lines = self.assertFallback(rc, out, "bad3", "config")
        self.assertRegex(oc_lines[0], r"^OC-ERROR hybrid-brainstorming bad3 .*kind=config")
        self.assertIn("HYBRID_OPENCODE_STD is not set", out)
        self.assertEqual(self.run_calls(), [])

    def test_invalid_shared_env_is_ignored_in_preset_claude(self):
        self.shared_env["HYBRID_OPENCODE_STD"] = "not a spec"
        rc, out = self.code_lane("bad2", "--preset", "claude")
        self.assertEqual(rc, 0)
        self.assertEqual(out.strip(), self.claude_text("bad2"))

    def test_model_in_the_user_routing_file_is_used_for_that_tier(self):
        self.write_config(routing_lite={"model": "zai-coding-plan/glm-5.3"})
        rc, out = self.code_lane("lk1", script={"events": [ev_text(CODE_OK), ev_step()]})
        self.assertEqual(rc, 0)
        self.assertRegex(out.strip().splitlines()[0], r"^LANE lk1 locate oc:lite OK")
        self.assertNotIn("OC-WARN", out)
        rec = self.last_record()
        self.assertEqual((rec["model"], rec["variant"]), ("zai-coding-plan/glm-5.3", ""))
        rc, out = self.run_cli("doctor")
        self.assertEqual(rc, 0)
        self.assertIn("tier lite: zai-coding-plan/glm-5.3 (skill) ok", out)

    def test_bad_lane_id_is_usage_error(self):
        rc, _ = self.run_cli("code", "--id", "bad/id", "--role", "locate")
        self.assertEqual(rc, 2)

    def test_doctor_writes_cache_and_prints_status_line(self):
        self.doctor_path.unlink()
        rc, out = self.run_cli("doctor")
        self.assertEqual(rc, 0)
        self.assertTrue(out.strip().splitlines()[0].startswith("opencode:"), out)
        self.assertTrue(self.doctor_path.exists())

    def test_doctor_ping_keeps_probe_streams_out_of_repo_root(self):
        self.doctor_path.unlink()
        rc, out = self.run_cli("doctor", "--ping",
                               script={"events": [ev_text("token"), ev_step()]})
        self.assertEqual(rc, 0)
        self.assertTrue(out.strip().splitlines()[0].startswith("opencode:"), out)
        self.assertEqual(list(self.root.glob("doctor-*")), [],
                         "doctor --ping must not write probe streams into the repo root")
        doctor_dir = self.lanes / "doctor"
        self.assertTrue(any(doctor_dir.glob("doctor-ping-*.out.jsonl")), out)
        self.assertTrue(any(doctor_dir.glob("doctor-ping-*.err")), out)

    def test_doctor_does_not_create_the_user_routing_file(self):
        user_routing = self.base / "config" / "hybrid-brainstorming" / "routing.json"
        rc, out = self.run_cli("doctor", env_extra={"HB_ROUTING": str(user_routing)})
        self.assertEqual(rc, 0)
        self.assertFalse(user_routing.exists())
        self.assertFalse(user_routing.parent.exists())
        self.assertFalse(any("created" in line.lower() and str(user_routing) in line
                             for line in out.splitlines()), out)

    def test_doctor_leaves_existing_user_routing_file_unchanged(self):
        user_routing = self.base / "config" / "hybrid-brainstorming" / "routing.json"
        user_routing.parent.mkdir(parents=True)
        original = b'{"preset": "claude", "custom": true}'
        user_routing.write_bytes(original)
        rc, out = self.run_cli("doctor", env_extra={"HB_ROUTING": str(user_routing)})
        self.assertEqual(rc, 0)
        self.assertEqual(user_routing.read_bytes(), original)
        self.assertFalse(any("created" in line.lower() and str(user_routing) in line
                             for line in out.splitlines()), out)

    def test_doctor_prints_a_failed_tier_as_an_oc_error(self):
        rc, out = self.run_cli("doctor", env_extra={"HB_FAKE_MODELS": "none"})
        self.assertEqual(rc, 0)
        errors = [line for line in out.splitlines() if line.startswith("OC-ERROR hybrid-brainstorming doctor")]
        self.assertTrue(errors, out)
        self.assertIn("kind=config", errors[0])
        self.assertIn("opencode models listed nothing", errors[0])

    def test_doctor_prints_shared_config_problems(self):
        self.shared_env["HYBRID_OPENCODE_STD"] = "not a spec"
        rc, out = self.run_cli("doctor")
        self.assertEqual(rc, 0)
        self.assertRegex(out, r"(?m)^OC-ERROR hybrid-brainstorming doctor .*kind=config")

    def test_doctor_prints_the_settings_allow_rule(self):
        rc, out = self.run_cli("doctor")
        self.assertEqual(rc, 0)
        expected = 'Bash(python3 "{}":*)'.format(BSLANE)
        self.assertIn(expected, out)

    def test_stats_empty_and_after_a_lane(self):
        rc, out = self.run_cli("stats")
        self.assertEqual(rc, 0)
        self.assertIn("no lanes recorded", out)
        self.code_lane("c2", script={"events": [ev_text(CODE_OK), ev_step()]})
        rc, out = self.run_cli("stats")
        self.assertEqual(rc, 0)
        self.assertTrue(re.search(r"^locate\s+lite\s+1\b", out, re.M), out)
