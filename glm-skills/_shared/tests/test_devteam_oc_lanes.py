import contextlib
import io
import json
import os
import shutil
import signal
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
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "glm-dev-team", "scripts")
sys.path.insert(0, SCRIPTS)

import devteam  # noqa: E402
import oc_harness  # noqa: E402

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
            line = devteam.emit_agent(Path("/r"), {}, "glm-programmer", "opus", "python3 x claim S1", "S1")
            bare = devteam.emit_agent(Path("/r"), {}, "glm-investigator", "", "Read b.md and follow it exactly.", "S2")
        self.assertEqual(line, 'Agent → subagent_type: glm-programmer, description: "S1", model: opus, '
                               'prompt: "python3 x claim S1"')
        self.assertEqual(bare, 'Agent → subagent_type: glm-investigator, description: "S2", '
                               'prompt: "Read b.md and follow it exactly."')

    def test_opencode_launches_a_lane(self):
        st = {"provider": "glm"}
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "opencode"}), \
                mock.patch.object(devteam, "launch_lane", return_value=4242) as launch:
            line = devteam.emit_agent(Path("/r"), st, "glm-code-reviewer", "", "Read r1.md", "review r1")
        launch.assert_called_once_with(Path("/r"), st, "review-r1", "glm-code-reviewer", "", "Read r1.md")
        self.assertIn("LANE review-r1", line)
        self.assertIn("pid 4242", line)
        self.assertNotIn("Agent →", line)

    def test_model_aliases_map_to_neutral_models(self):
        st = {"provider": "glm"}
        self.assertEqual(devteam.oc_model(st, "glm-programmer", ""), "flash")
        self.assertEqual(devteam.oc_model(st, "glm-code-reviewer", ""), "pro")
        self.assertEqual(devteam.oc_model(st, "glm-programmer", "opus"), "pro")
        self.assertEqual(devteam.oc_model(st, "glm-programmer", "sonnet"), "pro")


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
    f.write(json.dumps({"brief": sys.stdin.read(), "dir": argv[argv.index("--dir") + 1],
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
        drop = ("OPENCODE", "OPENCODE_TERMINAL", "DEVTEAM_HARNESS", "ANTHROPIC_BASE_URL", "DEVTEAM_GLM_TIER",
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
        self.assertIn('Agent → subagent_type: glm-programmer, description: "S1"', out)
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
        self.assertEqual((calls[0]["agent"], calls[0]["model"]), ("glm-programmer", "zai-coding-plan/glm-5.3-flash"))
        self.assertEqual((calls[0]["role"], calls[0]["slice"]), ("glm-programmer", "S1"))

    def test_opencode_gate_block_reruns_lane(self):
        self.devteam("dispatch", "S1", DEVTEAM_HARNESS="opencode", FAKE_OC_REPLY="still working")
        self.assertTrue(self.wait_for(self.state("slices", "S1.done")), self.lane_log())
        calls = self.calls()
        self.assertEqual(len(calls), 3)
        self.assertNotIn("glm-dev-team gate", calls[0]["brief"])
        self.assertIn("glm-dev-team gate — you are not done yet", calls[1]["brief"])
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
        spec = {"id": "S1", "agent": "glm-programmer", "model": "flash", "prompt": "do it", "writer": True}
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
        self.assertIn("exited 0", note)
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
            devteam.launch_lane(Path(self.repo), st, "review-r9", "glm-code-reviewer", "", "read r9.md")
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
        spec = {"id": "S1", "agent": "glm-programmer", "model": "flash", "prompt": "do it", "writer": True}
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

    def test_lane_worktree_without_base_sha_raises_devteam_error(self):
        root = Path(self.repo)
        st = devteam.load_state(root)  # S1 was `init`ed but never dispatched: base_sha is still None
        with self.assertRaisesRegex(devteam.DevteamError, "S1"):
            devteam.lane_worktree(root, st, "S1")


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
            pid1 = devteam.launch_lane(Path(self.repo), st, "rev-r1", "glm-code-reviewer", "", "read r1.md")
            self.assertTrue(self.wait_for(self.state("lanes", "rev-r1.pid")))
            self.assertTrue(_alive(pid1))
            pid2 = devteam.launch_lane(Path(self.repo), st, "rev-r1", "glm-code-reviewer", "", "read again")
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
            pid2 = devteam.launch_lane(Path(self.repo), st, "rev-r1", "glm-code-reviewer", "", "read r1.md")
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


class OcEffortTest(unittest.TestCase):
    def test_role_effort_is_a_glm_value(self):
        st = {"provider": "glm"}
        self.assertEqual(devteam.oc_effort(st, "glm-programmer-lite"), "low")
        self.assertEqual(devteam.oc_effort(st, "glm-team-leader"), "max")
        # the anthropic table's `medium` is not a GLM effort (v2 rejects the `#medium` variant)
        self.assertEqual(devteam.oc_effort({"provider": "anthropic"}, "glm-programmer"), "high")


def _killpg_quiet(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def _reaped_pid():
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


class LaneLifecycleTest(RepoCase):
    def lanes(self):
        d = devteam.lanes_dir(Path(self.repo))
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_spec(self, lane_id, agent, writer):
        spec = {"id": lane_id, "agent": agent, "model": "flash", "effort": "high",
                "prompt": "do it", "writer": writer}
        (self.lanes() / f"{lane_id}.lane.json").write_text(json.dumps(spec))
        return spec

    def run_lane(self, lane_id, results, during=None, env=None):
        """Run cmd_lane_run in-process with oc_harness.run_lanes faked; return (lanes seen, gate calls).
        `during()` is called from inside the faked run_lanes, i.e. while the lane is running."""
        seen, gates = [], []
        real_run = subprocess.run

        def fake_run(cmd, *args, **kwargs):
            if any("guard.py" in str(c) for c in cmd):
                gates.append(cmd)
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return real_run(cmd, *args, **kwargs)

        def fake_run_lanes(lanes, out_dir, **kwargs):
            seen.append(dict(lanes[0]))
            if during:
                during()
            return [results[min(len(seen), len(results)) - 1]]

        old_cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            with mock.patch.dict(os.environ, env or self.env, clear=True), \
                    mock.patch.object(devteam.subprocess, "run", side_effect=fake_run), \
                    mock.patch.object(oc_harness, "run_lanes", side_effect=fake_run_lanes):
                devteam.cmd_lane_run(SimpleNamespace(lane_id=lane_id))
        finally:
            os.chdir(old_cwd)
        return seen, gates

    def ok(self, lane_id):
        return {"status": "OK", "exit": 0, "error": None, "out": str(self.lanes() / f"{lane_id}.jsonl")}

    def test_terminate_kills_the_recorded_opencode_group(self):
        d = self.lanes()
        oc = subprocess.Popen([self.env["DEVTEAM_OC_BIN"], "run"], env=dict(self.env, FAKE_OC_SLEEP="30"),
                              start_new_session=True)
        self.addCleanup(_killpg_quiet, oc.pid)
        (d / "rev-r1.pgid").write_text(str(oc.pid))
        with mock.patch.dict(os.environ, self.env, clear=True):
            devteam.terminate_lane_process(d, "rev-r1")
        self.assertEqual(oc.wait(timeout=10), -signal.SIGKILL)
        self.assertFalse((d / "rev-r1.pgid").exists())

    def test_terminate_leaves_a_reused_pgid_alone(self):
        d = self.lanes()
        unrelated = subprocess.Popen(["sleep", "30"], start_new_session=True)
        self.addCleanup(_killpg_quiet, unrelated.pid)
        (d / "rev-r1.pgid").write_text(str(unrelated.pid))
        with mock.patch.dict(os.environ, self.env, clear=True):
            devteam.terminate_lane_process(d, "rev-r1")
        self.assertIsNone(unrelated.poll())
        self.assertFalse((d / "rev-r1.pgid").exists())

    def test_reviewer_lane_gets_the_reviewer_stall(self):
        self.write_spec("review-r1", "glm-code-reviewer", False)
        seen, _ = self.run_lane("review-r1", [self.ok("review-r1")])
        self.assertEqual(seen[0]["stall"], oc_harness.STALL_BY_ROLE["glm-code-reviewer"])
        self.assertEqual(seen[0]["stall"], 600)

    def test_programmer_lane_gets_the_programmer_stall(self):
        self.devteam("dispatch", "S1")
        self.write_spec("S1", "glm-programmer", True)
        seen, _ = self.run_lane("S1", [self.ok("S1")])
        self.assertEqual(seen[0]["stall"], 900)

    def test_lane_error_line_formats_v2_and_v1_errors(self):
        v2 = {"status": "ERROR", "error": {"type": "provider.rate-limit", "message": "429 Too Many Requests"}}
        v1 = {"status": "FAIL", "error": {"name": "APIError", "data": {"message": "Rate limit", "statusCode": 429}}}
        self.assertEqual(devteam.lane_error_line("L1", v2), "LANE L1: ERROR provider.rate-limit 429 Too Many Requests")
        self.assertEqual(devteam.lane_error_line("L2", v1), "LANE L2: FAIL APIError Rate limit")
        self.assertEqual(devteam.lane_error_line("L3", {"status": "STALL", "error": "no output for 900s"}),
                         "LANE L3: STALL no output for 900s")

    def test_writer_error_without_commit_blocks_without_reruns(self):
        self.devteam("dispatch", "S1")
        self.write_spec("S1", "glm-programmer", True)
        err = {"status": "ERROR", "exit": 1, "out": str(self.lanes() / "S1.jsonl"),
               "error": {"type": "provider.rate-limit", "message": "429 Too Many Requests"}}
        seen, gates = self.run_lane("S1", [err])
        self.assertEqual(len(seen), 1)
        self.assertEqual(gates, [])
        note = json.loads(self.state("slices", "S1.blocked").read_text())["note"]
        self.assertIn("LANE S1: ERROR provider.rate-limit 429 Too Many Requests", note)
        self.assertFalse(self.state("slices", "S1.done").exists())

    def test_lane_run_clears_stale_results_before_running(self):
        d = self.lanes()
        self.write_spec("review-r1", "glm-code-reviewer", False)
        for ext, body in ((".done", '{"status": "FAIL"}'), (".end", "1"), (".pgid", "999999")):
            (d / f"review-r1{ext}").write_text(body)
        self.run_lane("review-r1", [self.ok("review-r1")])
        for ext in (".done", ".end", ".pgid", ".pid"):
            self.assertFalse((d / f"review-r1{ext}").exists(), ext)

    def test_relaunch_hint_is_a_detached_python3_command(self):
        root = Path(self.repo)
        sig = {"throttle": [], "down": [("review", "review-r1", "ERROR: boom", "1", time.time())],
               "spawn_fail": [], "spawned": {}}
        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(devteam, "is_opencode", return_value=True), \
                mock.patch.object(devteam, "lane_signals", return_value=sig):
            st = devteam.load_state(root)
            st["reviews"] = {"r1": {"status": "dispatched"}}
            text = "\n".join(devteam.govern(root, st, 0))
        self.assertIn("LANE DOWN review-r1", text)
        self.assertIn("nohup python3 ", text)
        self.assertIn("lane-run review-r1 > ", text)

    def test_signal_killed_lane_is_reported_down_once(self):
        d = self.lanes()
        self.write_spec("rev-r7", "glm-code-reviewer", False)
        (d / "rev-r7.pid").write_text(str(_reaped_pid()))
        with mock.patch.dict(os.environ, self.env, clear=True):
            st = devteam.load_state(Path(self.repo))
            first = devteam.lane_signals(Path(self.repo), st)["down"]
            second = devteam.lane_signals(Path(self.repo), st)["down"]
        self.assertEqual([(k, n) for k, n, *_ in first], [("review", "rev-r7")])
        self.assertIn("killed by a signal", first[0][2])
        self.assertEqual([n for _, n, *_ in second], [])
        self.assertTrue((d / "rev-r7.end").exists())

    def test_signal_killed_lane_drops_its_pid_and_kills_the_orphaned_opencode(self):
        d = self.lanes()
        self.write_spec("rev-r5", "glm-code-reviewer", False)
        (d / "rev-r5.pid").write_text(str(_reaped_pid()))
        oc = subprocess.Popen([self.env["DEVTEAM_OC_BIN"], "run"], env=dict(self.env, FAKE_OC_SLEEP="30"),
                              start_new_session=True)
        self.addCleanup(_killpg_quiet, oc.pid)
        (d / "rev-r5.pgid").write_text(str(oc.pid))
        with mock.patch.dict(os.environ, self.env, clear=True):
            down = devteam.lane_signals(Path(self.repo), devteam.load_state(Path(self.repo)))["down"]
        self.assertEqual([n for _, n, *_ in down], ["rev-r5"])
        self.assertFalse((d / "rev-r5.pid").exists())
        self.assertEqual(oc.wait(timeout=10), -signal.SIGKILL)

    def test_relaunched_lane_run_over_a_dead_pid_records_its_own(self):
        d = self.lanes()
        self.write_spec("rev-r6", "glm-code-reviewer", False)
        (d / "rev-r6.pid").write_text(str(_reaped_pid()))
        probe = {}

        def during():
            probe["dead"] = [lane_id for lane_id, _ in devteam.dead_lanes(d)]
            probe["live"] = devteam.live_lanes(d)

        self.run_lane("rev-r6", [self.ok("rev-r6")], during=during)
        self.assertNotIn("rev-r6", probe["dead"])
        self.assertIn("rev-r6", probe["live"])

    def test_wait_does_not_report_a_relaunched_running_lane_as_dead(self):
        d = self.lanes()
        self.write_spec("rev-r2", "glm-code-reviewer", False)
        (d / "rev-r2.pid").write_text(str(_reaped_pid()))
        buf = io.StringIO()

        def during():
            with contextlib.redirect_stdout(buf):
                devteam.cmd_wait(SimpleNamespace(timeout=0))

        self.run_lane("rev-r2", [self.ok("rev-r2")], during=during,
                      env=dict(self.env, DEVTEAM_HARNESS="opencode"))
        self.assertIn("NEXT: devteam next", buf.getvalue())
        self.assertNotIn("died without a result", buf.getvalue())
        self.assertNotIn("no lane is running", buf.getvalue())

    def test_lane_with_a_result_is_not_dead(self):
        d = self.lanes()
        self.write_spec("rev-r8", "glm-code-reviewer", False)
        (d / "rev-r8.pid").write_text(str(_reaped_pid()))
        (d / "rev-r8.done").write_text('{"status": "OK"}')
        self.assertEqual(devteam.dead_lanes(d), [])

    def test_wait_returns_at_once_when_no_lane_is_running(self):
        start = time.monotonic()
        out = self.devteam("wait", "--timeout", "30", DEVTEAM_HARNESS="opencode")
        self.assertLess(time.monotonic() - start, 10)
        self.assertIn("WAIT: no lane is running", out)
        self.assertIn("NEXT: devteam next", out)

    def test_wait_reports_a_dead_lane(self):
        d = self.lanes()
        self.write_spec("rev-r3", "glm-code-reviewer", False)
        (d / "rev-r3.pid").write_text(str(_reaped_pid()))
        start = time.monotonic()
        out = self.devteam("wait", "--timeout", "30", DEVTEAM_HARNESS="opencode")
        self.assertLess(time.monotonic() - start, 10)
        self.assertIn("rev-r3 died", out)
        self.assertIn("NEXT: devteam next", out)

    def test_wait_keeps_waiting_while_a_lane_is_alive(self):
        d = self.lanes()
        self.write_spec("rev-r4", "glm-code-reviewer", False)
        alive = subprocess.Popen(["sleep", "30"], start_new_session=True)
        self.addCleanup(_killpg_quiet, alive.pid)
        (d / "rev-r4.pid").write_text(str(alive.pid))
        start = time.monotonic()
        out = self.devteam("wait", "--timeout", "2", DEVTEAM_HARNESS="opencode")
        self.assertGreaterEqual(time.monotonic() - start, 2)
        self.assertIn("WAIT: nothing finished in 2s", out)


if __name__ == "__main__":
    unittest.main()
