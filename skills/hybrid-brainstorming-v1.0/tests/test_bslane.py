import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
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
if len(sys.argv) < 2 or sys.argv[1] != "run":
    sys.exit(0)
path = os.environ.get("HB_FAKE_SCRIPT")
script = json.load(open(path)) if path and os.path.exists(path) else {}
for ev in script.get("events", []):
    sys.stdout.write(json.dumps(ev) + "\n")
    sys.stdout.flush()
    time.sleep(script.get("delay", 0))
time.sleep(script.get("sleep", 0))
sys.stderr.write(script.get("stderr", ""))
sys.exit(script.get("rc", 0))
'''

DEFAULT_ROUTING = {
    "preset": "hybrid",
    "tiers": {
        "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "max_parallel": 6, "stall_s": 90,
                "timeout_s": 300},
        "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low", "max_parallel": 6, "stall_s": 60,
                 "timeout_s": 180},
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


def ev_text(text):
    return {"type": "text", "sessionID": "ses_1", "part": {"type": "text", "text": text}}


def ev_step():
    return {"type": "step_finish", "sessionID": "ses_1",
            "part": {"type": "step-finish",
                     "tokens": {"input": 120, "output": 30, "reasoning": 5, "cache": {"read": 10, "write": 0}},
                     "cost": 0}}


def ev_tool(tool, url, output):
    return {"type": "tool_use", "sessionID": "ses_1",
            "part": {"type": "tool", "tool": tool,
                     "state": {"status": "completed", "input": {"url": url}, "output": output}}}


def ev_error(etype, message):
    return {"type": "error", "sessionID": "ses_1", "error": {"type": etype, "message": message}}


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
        self.doctor_path = base / "doctor.json"
        self.lanes = self.root / ".superpowers" / "brainstorm" / "lanes"
        self.telemetry = self.root / ".superpowers" / "brainstorm" / "lanes.jsonl"
        self.write_routing()
        self.write_doctor()

    def tearDown(self):
        self.tmp.cleanup()

    def write_routing(self, lite=None, slot_wait_s=5):
        routing = json.loads(json.dumps(DEFAULT_ROUTING))
        routing["slot_wait_s"] = slot_wait_s
        if lite:
            routing["tiers"]["lite"].update(lite)
        self.routing_path.write_text(json.dumps(routing), encoding="utf-8")

    def write_doctor(self):
        tiers = {name: {"model": t["model"], "variant": t["variant"], "ok": True, "note": ""}
                 for name, t in DEFAULT_ROUTING["tiers"].items()}
        doctor = {"t": "2026-09-28T00:00:00Z", "ok": True, "version": "2.0.18", "binary": str(self.fake),
                  "tiers": tiers, "websearch": True,
                  "status_line": "opencode: v2.0.18 preset=hybrid locate=oc:lite explore=oc:std fact=oc:lite "
                                 "research=claude draft=claude websearch=on (doctor 2026-09-28)"}
        self.doctor_path.write_text(json.dumps(doctor), encoding="utf-8")

    def run_cli(self, *args, script=None, oc_bin=None, env_extra=None):
        if script is not None:
            self.script.write_text(json.dumps(script), encoding="utf-8")
        env = dict(os.environ, HOME=str(self.home), HB_ROUTING=str(self.routing_path),
                   HB_DOCTOR_CACHE=str(self.doctor_path), HB_OC_BIN=str(oc_bin or self.fake),
                   HB_FAKE_SCRIPT=str(self.script), HB_FAKE_LOG=str(self.log), PYTHONDONTWRITEBYTECODE="1")
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

    def assertFallback(self, rc, out, lane_id, reason):
        self.assertEqual(rc, 0)
        lines = out.strip().splitlines()
        self.assertTrue(lines[0].startswith("FALLBACK {} ({})".format(lane_id, reason)), out)
        self.assertTrue(lines[1].startswith("CLAUDE {} — Agent".format(lane_id)), out)
        rec = self.last_record()
        self.assertEqual((rec["outcome"], rec["reason"]), ("fallback", reason))

    def test_preset_claude_spawns_nothing_and_writes_prompt(self):
        rc, out = self.code_lane("c9", "--preset", "claude")
        self.assertEqual(rc, 0)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 1, out)
        self.assertTrue(lines[0].startswith("CLAUDE c9 — Agent"), out)
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

    def test_draft_lane_is_ungrounded_in_max(self):
        ctx = self.root / ".superpowers" / "drafts" / "ctx.md"
        ctx.parent.mkdir(parents=True)
        ctx.write_text("Constraints: stdlib only.\nFinding: app.py:2 handler.\n", encoding="utf-8")
        rc, out = self.run_cli("draft", "--id", "d1", "--lens", "reuse", "--task", "add login audit",
                               "--context-file", str(ctx), "--preset", "max",
                               script={"events": [ev_text("APPROACH: wrap handler with an audit decorator"),
                                                  ev_step()]})
        self.assertEqual(rc, 0)
        self.assertRegex(out.strip().splitlines()[0], r"^LANE d1 draft oc:std OK — ungrounded — \d+s$")
        self.assertIn("APPROACH", out)

    def test_fallback_spawn(self):
        rc, out = self.code_lane("s1", oc_bin=self.base / "no-such-opencode")
        self.assertFallback(rc, out, "s1", "spawn")

    def test_fallback_crash(self):
        rc, out = self.code_lane("k1", script={"events": [ev_error("ProviderAuthError", "invalid api key")],
                                               "rc": 1})
        self.assertFallback(rc, out, "k1", "crash")

    def test_fallback_stall(self):
        self.write_routing(lite={"stall_s": 1, "timeout_s": 30})
        rc, out = self.code_lane("st1", script={"events": [], "sleep": 8})
        self.assertFallback(rc, out, "st1", "stall")

    def test_fallback_timeout(self):
        self.write_routing(lite={"stall_s": 5, "timeout_s": 1})
        rc, out = self.code_lane("to1", script={"events": [ev_step() for _ in range(40)], "delay": 0.2})
        self.assertFallback(rc, out, "to1", "timeout")

    def test_fallback_throttle_starts_cooldown_then_cooldown_skips_spawn(self):
        script = {"events": [ev_error("APIError", "429 Too Many Requests: rate limit exceeded")], "rc": 1}
        rc, out = self.code_lane("t1", script=script)
        self.assertFallback(rc, out, "t1", "throttle")
        self.assertTrue((self.lanes / "cooldown-lite").exists())
        rc, out = self.code_lane("t2", script=script)
        self.assertFallback(rc, out, "t2", "cooldown")
        self.assertEqual(len(self.run_calls()), 1)

    def test_fallback_busy_when_all_slots_held(self):
        self.write_routing(lite={"max_parallel": 1}, slot_wait_s=0)
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
        self.assertFallback(rc, out, "f1", "format")

    def test_fallback_grounding(self):
        rc, out = self.code_lane("g1", script={"events": [ev_text(CODE_BAD), ev_step()]})
        self.assertFallback(rc, out, "g1", "grounding")
        self.assertIn("UNVERIFIED", out)

    def test_fallback_config_on_unreadable_context_file(self):
        rc, out = self.run_cli("draft", "--id", "cf1", "--lens", "smallest", "--task", "add login audit",
                               "--context-file", str(self.base / "missing.md"), "--preset", "max")
        self.assertFallback(rc, out, "cf1", "config")

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

    def test_doctor_creates_missing_user_routing_file_as_byte_copy(self):
        user_routing = self.base / "config" / "hybrid-brainstorming" / "routing.json"
        self.assertFalse(user_routing.exists())
        rc, out = self.run_cli("doctor", env_extra={"HB_ROUTING": str(user_routing)})
        self.assertEqual(rc, 0)
        self.assertTrue(user_routing.exists())
        defaults_path = bslane.SKILL_DIR / "routing.default.json"
        self.assertEqual(user_routing.read_bytes(), defaults_path.read_bytes())
        self.assertIn(str(user_routing), out)
        self.assertTrue(any("created" in line.lower() and str(user_routing) in line
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

    def test_doctor_prints_the_settings_allow_rule(self):
        rc, out = self.run_cli("doctor")
        self.assertEqual(rc, 0)
        skill_bslane = bslane.SKILL_DIR / "scripts" / "bslane.py"
        expected = 'Bash(python3 "{}":*)'.format(skill_bslane)
        self.assertIn(expected, out)

    def test_stats_empty_and_after_a_lane(self):
        rc, out = self.run_cli("stats")
        self.assertEqual(rc, 0)
        self.assertIn("no lanes recorded", out)
        self.code_lane("c2", script={"events": [ev_text(CODE_OK), ev_step()]})
        rc, out = self.run_cli("stats")
        self.assertEqual(rc, 0)
        self.assertTrue(re.search(r"^locate\s+lite\s+1\b", out, re.M), out)
