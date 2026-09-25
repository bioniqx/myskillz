import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
GLM = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(GLM, "dev-team-glm", "scripts")
SKILL_DIR = os.path.join(GLM, "dev-team-glm")
STUB = os.path.join(HERE, "stub_opencode.py")
GUARD = os.path.join(SCRIPTS, "guard.py")
sys.path.insert(0, SCRIPTS)

import oc_harness  # noqa: E402  (the vendored copy next to devteam.py)


def load_devteam():
    spec = importlib.util.spec_from_file_location("devteam_oc", os.path.join(SCRIPTS, "devteam.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dt = load_devteam()

THROTTLE_EVENT = json.dumps({"type": "error", "error": {"name": "APIError", "data": {
    "message": json.dumps({"error": {"code": "1302", "message": "High concurrency"}})}}})
TEXT_EVENT = json.dumps({"type": "text", "part": {"type": "text", "text": "the docs mention 429 and rate limits"}})
EMPTY_SIG = {"throttle": [], "down": [], "spawn_fail": [], "spawned": {}}


class _LaneCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.lanes = self.root / ".claude" / "dev-team" / "lanes"
        now = int(time.time())
        self.st = {
            "created": now - 10, "provider": "glm",
            "reviews": {"r1": {"status": "dispatched", "shards": 2}},
            "slices": {
                "S1": {"status": "inflight", "mode": "slice", "dispatched": now - 5, "history": []},
                "R1": {"status": "inflight", "mode": "research", "dispatched": now - 5, "history": []},
            },
            "gov": dt.new_gov("glm", "pro"),
        }

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, name, text, mode="a"):
        self.lanes.mkdir(parents=True, exist_ok=True)
        with open(self.lanes / name, mode) as f:
            f.write(text)
        return self.lanes / name


class LaneSignalsTest(_LaneCase):
    def test_no_lanes_dir(self):
        self.assertEqual(dt.lane_signals(self.root, self.st), EMPTY_SIG)

    def test_throttle_counted_once(self):
        self.write("S1.jsonl", TEXT_EVENT + "\n" + THROTTLE_EVENT + "\n")
        self.assertEqual(len(dt.lane_signals(self.root, self.st)["throttle"]), 1)
        self.assertEqual(dt.lane_signals(self.root, self.st)["throttle"], [])
        self.write("S1.jsonl", THROTTLE_EVENT + "\n")
        self.assertEqual(len(dt.lane_signals(self.root, self.st)["throttle"]), 1)

    def test_old_lane_files_ignored(self):
        path = self.write("S1.jsonl", THROTTLE_EVENT + "\n")
        old = self.st["created"] - 600
        os.utime(path, (old, old))
        self.write("S1.done", json.dumps({"id": "S1", "status": "FAIL", "error": "old"}))
        os.utime(self.lanes / "S1.done", (old, old))
        sig = dt.lane_signals(self.root, self.st)
        self.assertEqual((sig["throttle"], sig["down"]), ([], []))
        self.write("S1.jsonl", THROTTLE_EVENT + "\n")
        self.assertEqual(len(dt.lane_signals(self.root, self.st)["throttle"]), 1)

    def test_failed_lanes_reported_once(self):
        self.write("S1.done", json.dumps({"id": "S1", "status": "FAIL", "exit": 3, "error": "boom"}))
        self.write("r1-2.done", json.dumps({"id": "r1-2", "status": "STALL", "error": "no event for 180s"}))
        self.write("R1.done", json.dumps({"id": "R1", "status": "TIMEOUT", "error": "timeout after 60s"}))
        sig = dt.lane_signals(self.root, self.st)
        self.assertEqual(sorted((k, n, t) for k, n, t, _, _ in sig["down"]), [
            ("research", "R1", "TIMEOUT: timeout after 60s"),
            ("review", "r1-2", "STALL: no event for 180s"),
            ("slice", "S1", "FAIL: boom"),
        ])
        self.assertEqual(dt.lane_signals(self.root, self.st)["down"], [])

    def test_ok_lane_not_down(self):
        self.write("S1.done", json.dumps({"id": "S1", "status": "OK", "exit": 0, "error": ""}))
        self.assertEqual(dt.lane_signals(self.root, self.st)["down"], [])


class GovernHarnessTest(_LaneCase):
    ENV = {"DEVTEAM_PEAK": "off", "DEVTEAM_GOVERNOR": "on",
           "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "20", "DEVTEAM_MAX_PARALLEL": ""}

    def test_opencode_reads_lane_files(self):
        self.write("S1.jsonl", THROTTLE_EVENT + "\n")
        self.write("S1.done", json.dumps({"id": "S1", "status": "FAIL", "exit": 3, "error": "boom"}))
        env = dict(self.ENV, DEVTEAM_HARNESS="opencode")
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(dt, "scan_transcripts", side_effect=AssertionError("transcripts read")):
            lines = dt.govern(self.root, self.st, 0)
        throttled = [ln for ln in lines if ln.startswith("THROTTLED: 1 ")]
        self.assertEqual(len(throttled), 1)
        self.assertIn("window 6 → 3", throttled[0])
        self.assertEqual(self.st["gov"]["cap"], 3)
        down = [ln for ln in lines if ln.startswith("LANE DOWN S1 (slice)")]
        self.assertEqual(len(down), 1)
        self.assertIn("FAIL: boom", down[0])
        self.assertIn("`retry S1`", down[0])
        self.assertNotIn("SendMessage", down[0])

    def test_claude_reads_transcripts(self):
        self.write("S1.jsonl", THROTTLE_EVENT + "\n")
        env = dict(self.ENV, DEVTEAM_HARNESS="claude")
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(dt, "scan_transcripts", return_value=dict(EMPTY_SIG, spawned={})) as scan, \
                mock.patch.object(dt, "lane_signals", side_effect=AssertionError("lane files read")):
            lines = dt.govern(self.root, self.st, 0)
        scan.assert_called_once()
        self.assertEqual(lines, [])
        self.assertEqual(self.st["gov"]["cap"], 6)


V1_PLUGIN = ('import { spawnSync } from "node:child_process";\n'
             'export const DevteamGuard = async ({ directory }) => ({\n'
             '  "tool.execute.before": async (input, output) => {\n'
             '    spawnSync("python3", ["%s", "oc"], { cwd: directory });\n'
             '  },\n'
             '});\n')
V2_PLUGIN = ('import { Plugin } from "@opencode/plugin";\n'
             'export default Plugin.define({ id: "devteam-guard", setup: (ctx) => ({\n'
             '  "tool.execute.before": async (input, output) => {},\n'
             '}) });\n'
             '// python3 %s oc\n')


class DoctorOpenCodeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.bin = os.path.join(self.tmp, "bin")
        self.repo = os.path.join(self.tmp, "repo")
        for d in (self.home, self.bin, self.repo):
            os.makedirs(d)
        opencode = os.path.join(self.bin, "opencode")
        with open(opencode, "w") as f:
            f.write('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, STUB))
        os.chmod(opencode, 0o755)
        for args in (["init", "-q"],
                     ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                      "commit", "-q", "--allow-empty", "-m", "init"]):
            subprocess.run(["git"] + args, cwd=self.repo, check=True, capture_output=True)
        self.old = os.getcwd()
        os.chdir(self.repo)
        self.env = mock.patch.dict(os.environ, {
            "HOME": self.home, "PATH": self.bin + os.pathsep + os.environ.get("PATH", ""),
            "DEVTEAM_HARNESS": "opencode", "STUB_OC_VERSION": "1.18.32", "STUB_OC_MISSING": ""})
        self.env.start()
        self.name = oc_harness.skill_name(SKILL_DIR)
        self.oc = os.path.join(self.home, ".config", "opencode")

    def tearDown(self):
        self.env.stop()
        os.chdir(self.old)
        shutil.rmtree(self.tmp)

    def doctor(self, fix=False, harness="opencode"):
        ns = argparse.Namespace(fix=fix) if harness is None else argparse.Namespace(fix=fix, harness=harness)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dt.cmd_doctor(ns)
        return buf.getvalue()

    def plugin(self, text):
        d = os.path.join(self.oc, "plugins")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "guard.js"), "w") as f:
            f.write(text)

    def test_reports_missing_install(self):
        out = self.doctor()
        self.assertIn("harness opencode", out)
        self.assertIn("DOCTOR found:", out)
        self.assertIn("MISSING: %s is not installed for OpenCode" % self.name, out)
        self.assertIn("agent programmer not installed", out)
        self.assertIn("agent team-leader not installed", out)
        self.assertIn("guard plugin not installed", out)
        self.assertIn("no opencode.json names the zai-coding-plan provider", out)
        self.assertIn("run `doctor --harness opencode --fix`", out)
        self.assertNotIn("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", out)

    def test_fix_installs_detected_major(self):
        out = self.doctor(fix=True)
        self.assertIn("harness opencode", out)
        self.assertIn("installed ", out)
        self.assertIn("updated git info/exclude", out)
        with open(os.path.join(self.oc, "skills", self.name, ".oc-major")) as f:
            self.assertEqual(f.read().strip(), "1")
        again = self.doctor()
        self.assertNotIn("MISSING: %s" % self.name, again)
        self.assertIn("INSTALLED: %s (major 1)" % self.name, again)

    def test_major_mismatch(self):
        d = os.path.join(self.oc, "skills", self.name)
        os.makedirs(d)
        with open(os.path.join(d, ".oc-major"), "w") as f:
            f.write("2")
        out = self.doctor()
        self.assertIn("installed major 2 != detected major 1, re-run install-opencode.sh", out)

    def test_opencode_missing(self):
        os.environ["STUB_OC_VERSION"] = "none"
        out = self.doctor()
        self.assertIn("harness opencode", out)
        self.assertIn("opencode not found on PATH", out)

    def test_plugin_wrong_dialect(self):
        self.plugin(V2_PLUGIN % GUARD)
        out = self.doctor()
        self.assertIn("plugin guard.js is written for OpenCode v2 but opencode is v1", out)
        self.assertIn("re-run install-opencode.sh", out)

    def test_plugin_ok(self):
        self.plugin(V1_PLUGIN % GUARD)
        out = self.doctor()
        self.assertIn("harness opencode", out)
        self.assertNotIn("guard plugin not installed", out)
        self.assertNotIn("plugin guard.js", out)

    def test_plugin_unresolved(self):
        self.plugin(V1_PLUGIN % "{{SKILL_DIR}}/scripts/guard.py")
        out = self.doctor()
        self.assertIn("plugin guard.js: its guard.py path does not resolve", out)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_plugin_load_error(self):
        self.plugin("export const DevteamGuard = async ({ directory }) => ({ // python3 %s oc\n" % GUARD)
        out = self.doctor()
        self.assertIn("plugin guard.js fails to load", out)

    def test_provider_config_found(self):
        os.makedirs(self.oc, exist_ok=True)
        with open(os.path.join(self.oc, "opencode.json"), "w") as f:
            json.dump({"provider": {"zai-coding-plan": {}}}, f)
        out = self.doctor()
        self.assertIn("harness opencode", out)
        self.assertNotIn("names the zai-coding-plan provider", out)

    def test_default_harness_from_env(self):
        self.assertIn("harness opencode", self.doctor(harness=None))
        os.environ["DEVTEAM_HARNESS"] = "claude"
        out = self.doctor(harness=None)
        self.assertNotIn("harness opencode", out)
        self.assertIn("run `doctor --fix`", out)

    def test_claude_harness_unchanged(self):
        out = self.doctor(harness="claude")
        self.assertNotIn("harness opencode", out)
        self.assertIn("DOCTOR found:", out)
        self.assertIn("run `doctor --fix`", out)


if __name__ == "__main__":
    unittest.main()
