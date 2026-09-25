import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "dev-team-glm", "scripts")
sys.path.insert(0, SCRIPTS)

import devteam  # noqa: E402

DEVTEAM = os.path.join(SCRIPTS, "devteam.py")


class HarnessTest(unittest.TestCase):
    def test_is_opencode(self):
        cases = [({}, False), ({"OPENCODE": "1"}, True), ({"DEVTEAM_HARNESS": "opencode"}, True),
                 ({"DEVTEAM_HARNESS": "claude", "OPENCODE": "1"}, False), ({"OPENCODE": ""}, False)]
        for env, want in cases:
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(devteam.is_opencode(), want, env)

    def test_claude_line_is_unchanged(self):
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "claude"}):
            line = devteam.emit_agent(Path("/r"), {}, "programmer", "opus", "python3 x claim S1", "S1")
            bare = devteam.emit_agent(Path("/r"), {}, "investigator", "", "Read b.md and follow it exactly.", "S2")
        self.assertEqual(line, 'Agent → subagent_type: programmer, description: "S1", model: opus, '
                               'prompt: "python3 x claim S1"')
        self.assertEqual(bare, 'Agent → subagent_type: investigator, description: "S2", '
                               'prompt: "Read b.md and follow it exactly."')

    def test_opencode_launches_a_lane(self):
        st = {"provider": "glm"}
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "opencode"}), \
                mock.patch.object(devteam, "launch_lane", return_value=4242) as launch:
            line = devteam.emit_agent(Path("/r"), st, "code-reviewer", "", "Read r1.md", "review r1")
        launch.assert_called_once_with(Path("/r"), st, "review-r1", "code-reviewer", "", "Read r1.md")
        self.assertIn("LANE review-r1", line)
        self.assertIn("pid 4242", line)
        self.assertNotIn("Agent →", line)

    def test_model_aliases_map_to_neutral_models(self):
        st = {"provider": "glm"}
        self.assertEqual(devteam.oc_model(st, "programmer", ""), "flash")
        self.assertEqual(devteam.oc_model(st, "code-reviewer", ""), "pro")
        self.assertEqual(devteam.oc_model(st, "programmer", "opus"), "pro")
        self.assertEqual(devteam.oc_model(st, "programmer", "sonnet"), "pro")


FAKE_OC = '''#!/usr/bin/env python3
import json, os, sys, time
argv = sys.argv[1:]
if argv[:1] == ["--version"]:
    print("1.18.0")
    sys.exit(0)
if "--help" in argv:
    print("--dir --agent --model --format --auto")
    sys.exit(0)
if os.environ.get("FAKE_OC_SLEEP"):
    time.sleep(float(os.environ["FAKE_OC_SLEEP"]))
    sys.exit(0)
with open(os.environ["FAKE_OC_LOG"], "a") as f:
    f.write(json.dumps({"brief": argv[-1], "dir": argv[argv.index("--dir") + 1],
                        "agent": argv[argv.index("--agent") + 1], "model": argv[argv.index("-m") + 1],
                        "role": os.environ.get("DEVTEAM_ROLE"), "slice": os.environ.get("DEVTEAM_SLICE")}) + "\\n")
print(json.dumps({"type": "text", "part": {"type": "text", "text": os.environ.get("FAKE_OC_REPLY", "")}}))
'''

PLAN = {"request": "r", "commands": {"test": "true"},
        "slices": [{"id": "S1", "title": "one", "deps": [], "files": ["src/a.py", "tests/test_a.py"],
                    "risk": "low", "criteria": ["works"]}]}


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo, "src"))
        os.makedirs(os.path.join(self.tmp, "home"))
        fake = os.path.join(self.tmp, "fake_opencode")
        with open(fake, "w") as f:
            f.write(FAKE_OC)
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
        self.log = os.path.join(self.tmp, "oc.log")
        drop = ("OPENCODE", "DEVTEAM_HARNESS", "ANTHROPIC_BASE_URL", "DEVTEAM_GLM_TIER",
                "DEVTEAM_MAX_PARALLEL", "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS")
        self.env = {k: v for k, v in os.environ.items() if k not in drop}
        self.env.update({"DEVTEAM_PROVIDER": "glm", "DEVTEAM_GOVERNOR": "off", "DEVTEAM_PEAK": "off",
                         "DEVTEAM_TRANSCRIPTS_DIR": os.path.join(self.tmp, "none"),
                         "HOME": os.path.join(self.tmp, "home"), "DEVTEAM_OC_BIN": fake,
                         "FAKE_OC_LOG": self.log})
        for cmd in (["git", "init", "-q", "-b", "main"], ["git", "config", "user.email", "t@t"],
                    ["git", "config", "user.name", "t"], ["git", "config", "commit.gpgsign", "false"]):
            self.run_ok(cmd)
        Path(self.repo, "src", "a.py").write_text("x = 1\n")
        Path(self.tmp, "plan.json").write_text(json.dumps(PLAN))
        self.run_ok(["git", "add", "-A"])
        self.run_ok(["git", "commit", "-qm", "init"])
        self.devteam("init", os.path.join(self.tmp, "plan.json"))

    def run_ok(self, cmd, env=None):
        r = subprocess.run(cmd, cwd=self.repo, env=env or self.env, text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def devteam(self, *args, **env):
        return self.run_ok([sys.executable, DEVTEAM] + list(args), env=dict(self.env, **env))

    def state(self, *parts):
        return Path(self.repo, ".claude", "dev-team", *parts)

    def lane_log(self):
        p = self.state("lanes", "S1.log")
        return p.read_text() if p.exists() else "(no lane log)"

    def wait_for(self, path, limit=60):
        end = time.monotonic() + limit
        while time.monotonic() < end:
            if path.exists():
                return True
            time.sleep(0.2)
        return False

    def calls(self):
        with open(self.log) as f:
            return [json.loads(line) for line in f]


class LaneRunTest(RepoCase):
    def test_claude_dispatch_prints_agent_line(self):
        out = self.devteam("dispatch", "S1")
        self.assertIn('Agent → subagent_type: programmer, description: "S1"', out)
        self.assertIn("claim S1", out)
        self.assertFalse(self.state("lanes").exists())

    def test_opencode_blocked_lane_writes_marker(self):
        out = self.devteam("dispatch", "S1", DEVTEAM_HARNESS="opencode",
                           FAKE_OC_REPLY="## Status: Blocked\nneed the schema")
        self.assertIn("LANE S1", out)
        self.assertNotIn("Agent →", out)
        self.assertTrue(self.wait_for(self.state("slices", "S1.blocked")), self.lane_log())
        wt = self.state("wt", "S1")
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=wt,
                                text=True, capture_output=True).stdout.strip()
        self.assertEqual(branch, "devteam/S1")
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertIn("CLAIMED S1", calls[0]["brief"])
        self.assertEqual(os.path.realpath(calls[0]["dir"]), os.path.realpath(str(wt)))
        self.assertEqual((calls[0]["agent"], calls[0]["model"]), ("programmer", "zai-coding-plan/glm-5.3-flash"))
        self.assertEqual((calls[0]["role"], calls[0]["slice"]), ("programmer", "S1"))

    def test_opencode_gate_block_reruns_lane(self):
        self.devteam("dispatch", "S1", DEVTEAM_HARNESS="opencode", FAKE_OC_REPLY="still working")
        self.assertTrue(self.wait_for(self.state("slices", "S1.done")), self.lane_log())
        calls = self.calls()
        self.assertEqual(len(calls), 3)
        self.assertNotIn("dev-team gate", calls[0]["brief"])
        self.assertIn("dev-team gate — you are not done yet", calls[1]["brief"])
        note = json.loads(self.state("slices", "S1.done").read_text())["note"]
        self.assertIn("gave up", note)
        self.assertFalse(self.state("slices", "S1.blocked").exists())

    def test_pid_file_removed_after_lane_run_finishes(self):
        self.devteam("dispatch", "S1", DEVTEAM_HARNESS="opencode",
                     FAKE_OC_REPLY="## Status: Blocked\nneed the schema")
        self.assertTrue(self.wait_for(self.state("slices", "S1.blocked")), self.lane_log())
        self.assertTrue(self.wait_for(self.state("lanes", "S1.end")))
        self.assertFalse(self.state("lanes", "S1.pid").exists())

    def test_gate_exit_other_than_2_without_marker_writes_blocked_naming_the_code(self):
        self.devteam("dispatch", "S1")
        root = Path(self.repo)
        d = devteam.lanes_dir(root)
        d.mkdir(parents=True, exist_ok=True)
        spec = {"id": "S1", "agent": "programmer", "model": "flash", "prompt": "do it", "writer": True}
        (d / "S1.lane.json").write_text(json.dumps(spec))
        real_run = subprocess.run

        def fake_run(cmd, *args, **kwargs):
            if any("guard.py" in str(c) for c in cmd):
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return real_run(cmd, *args, **kwargs)

        old_cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            with mock.patch.dict(os.environ, self.env, clear=True), \
                    mock.patch.object(devteam.subprocess, "run", side_effect=fake_run):
                devteam.cmd_lane_run(SimpleNamespace(lane_id="S1"))
        finally:
            os.chdir(old_cwd)
        marker = self.state("slices", "S1.blocked")
        self.assertTrue(marker.exists())
        self.assertFalse(self.state("slices", "S1.done").exists())
        note = json.loads(marker.read_text())["note"]
        self.assertIn("0", note)
        self.assertFalse(self.state("lanes", "S1.pid").exists())

    def test_missing_binary_blocks_the_writer_slice(self):
        start = time.monotonic()
        out = self.devteam("dispatch", "S1", DEVTEAM_HARNESS="opencode",
                           DEVTEAM_OC_BIN="/no/such/opencode-binary-xyz")
        self.assertIn("LANE S1", out)
        self.assertTrue(self.wait_for(self.state("slices", "S1.blocked")), self.lane_log())
        note = json.loads(self.state("slices", "S1.blocked").read_text())["note"]
        self.assertIn("lane-run failed", note)
        wout = self.devteam("wait", "--timeout", "30")
        self.assertLess(time.monotonic() - start, 20)
        self.assertIn("NEXT: devteam next", wout)

    def test_non_writer_lane_error_writes_done_with_status_error(self):
        st = {"provider": "glm"}
        env = dict(self.env, DEVTEAM_OC_BIN="/no/such/opencode-binary-xyz")
        with mock.patch.dict(os.environ, env, clear=True):
            devteam.launch_lane(Path(self.repo), st, "review-r9", "code-reviewer", "", "read r9.md")
        done = self.state("lanes", "review-r9.done")
        self.assertTrue(self.wait_for(done))
        data = json.loads(done.read_text())
        self.assertEqual(data["status"], "ERROR")
        self.assertTrue(data.get("error"))

    def test_writer_loop_exhausts_without_marker_writes_blocked(self):
        self.devteam("dispatch", "S1")
        root = Path(self.repo)
        d = devteam.lanes_dir(root)
        d.mkdir(parents=True, exist_ok=True)
        spec = {"id": "S1", "agent": "programmer", "model": "flash", "prompt": "do it", "writer": True}
        (d / "S1.lane.json").write_text(json.dumps(spec))
        real_run = subprocess.run

        def fake_run(cmd, *args, **kwargs):
            if any("guard.py" in str(c) for c in cmd):
                return subprocess.CompletedProcess(cmd, 2, "", "blocked forever")
            return real_run(cmd, *args, **kwargs)

        old_cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            with mock.patch.dict(os.environ, self.env, clear=True), \
                    mock.patch.object(devteam.subprocess, "run", side_effect=fake_run):
                devteam.cmd_lane_run(SimpleNamespace(lane_id="S1"))
        finally:
            os.chdir(old_cwd)
        marker = self.state("slices", "S1.blocked")
        self.assertTrue(marker.exists())
        self.assertFalse(self.state("slices", "S1.done").exists())
        note = json.loads(marker.read_text())["note"]
        self.assertIn("exhausted", note)


def _alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


class LaneProcessGroupTest(RepoCase):
    def test_relaunching_same_lane_id_kills_the_previous_process_group(self):
        st = {"provider": "glm"}
        env = dict(self.env, FAKE_OC_SLEEP="20")
        with mock.patch.dict(os.environ, env, clear=True):
            pid1 = devteam.launch_lane(Path(self.repo), st, "rev-r1", "code-reviewer", "", "read r1.md")
            self.assertTrue(self.wait_for(self.state("lanes", "rev-r1.pid")))
            self.assertTrue(_alive(pid1))
            pid2 = devteam.launch_lane(Path(self.repo), st, "rev-r1", "code-reviewer", "", "read again")
        self.addCleanup(self._killpg_safe, pid2)
        self.assertNotEqual(pid1, pid2)
        deadline = time.monotonic() + 10
        while _alive(pid1) and time.monotonic() < deadline:
            time.sleep(0.2)
        self.assertFalse(_alive(pid1))

    def _killpg_safe(self, pid):
        try:
            os.killpg(pid, 9)
        except OSError:
            pass

    def test_launch_lane_does_not_kill_an_unrelated_process_group(self):
        st = {"provider": "glm"}
        d = devteam.lanes_dir(Path(self.repo))
        d.mkdir(parents=True, exist_ok=True)
        unrelated = subprocess.Popen(["sleep", "30"], start_new_session=True)
        self.addCleanup(self._killpg_safe, unrelated.pid)
        (d / "rev-r1.pid").write_text(str(unrelated.pid))
        env = dict(self.env, FAKE_OC_SLEEP="0")
        with mock.patch.dict(os.environ, env, clear=True):
            pid2 = devteam.launch_lane(Path(self.repo), st, "rev-r1", "code-reviewer", "", "read r1.md")
        self.addCleanup(self._killpg_safe, pid2)
        self.assertTrue(_alive(unrelated.pid))
        unrelated.terminate()
        unrelated.wait(timeout=5)


class WaitTest(RepoCase):
    def test_times_out_with_next_line(self):
        start = time.monotonic()
        out = self.devteam("wait", "--timeout", "1")
        self.assertGreaterEqual(time.monotonic() - start, 1)
        self.assertIn("NEXT: devteam next", out)

    def test_returns_when_a_marker_appears(self):
        marker = self.state("slices", "S9.done")
        timer = threading.Timer(0.5, marker.write_text, args=("{}",))
        timer.start()
        self.addCleanup(timer.cancel)
        start = time.monotonic()
        out = self.devteam("wait", "--timeout", "30")
        self.assertLess(time.monotonic() - start, 10)
        self.assertIn("NEXT: devteam next", out)

    def test_opencode_dispatch_then_wait(self):
        self.devteam("dispatch", "S1", DEVTEAM_HARNESS="opencode", FAKE_OC_REPLY="## Status: Blocked\nno schema")
        out = self.devteam("wait", "--timeout", "60")
        self.assertIn("NEXT: devteam next", out)
        self.assertTrue(self.state("slices", "S1.blocked").exists(), self.lane_log())


if __name__ == "__main__":
    unittest.main()
