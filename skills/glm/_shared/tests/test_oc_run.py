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
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import oc_harness  # noqa: E402

STUB = os.path.join(HERE, "stub_opencode.py")


def setUpModule():
    mode = os.stat(STUB).st_mode
    os.chmod(STUB, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def lane(lane_id, brief, **extra):
    item = {"id": lane_id, "agent": "worker", "model": "flash", "dir": HERE, "brief": brief}
    item.update(extra)
    return item


class ThrottleReTest(unittest.TestCase):
    def test_matches_throttle_codes(self):
        for text in [
            '{"code":1302}',
            '{"code": "1305"}',
            '{"status": 429}',
            '{"statusCode":429}',
            '{"message":"{\\"error\\":{\\"code\\":\\"1302\\"}}"}',
            "HTTP 429 Too Many Requests",
        ]:
            self.assertTrue(oc_harness.THROTTLE_RE.search(text), text)

    def test_ignores_other_numbers(self):
        for text in ['{"tokens": 429}', '{"code":13020}', '{"code":"1301"}', '{"status":200}']:
            self.assertIsNone(oc_harness.THROTTLE_RE.search(text), text)


class BuildRunCmdTest(unittest.TestCase):
    def test_v1_command(self):
        cmd = oc_harness.build_run_cmd(lane("a", "look", dir="/tmp/repo"), 1)
        self.assertEqual(cmd, [
            "opencode", "run", "--dir", "/tmp/repo", "--agent", "worker",
            "-m", "zai-coding-plan/glm-5.3-flash", "--format", "json", "--auto", "look",
        ])

    def test_v2_command_uses_long_model_flag_and_no_dir(self):
        cmd = oc_harness.build_run_cmd(lane("a", "look", dir="/tmp/repo", model="pro"), 2, binary="oc2")
        self.assertEqual(cmd, [
            "oc2", "run", "--standalone", "--agent", "worker",
            "--model", "zai-coding-plan/glm-5.3", "--format", "json", "--auto", "look",
        ])
        self.assertNotIn("--dir", cmd)

    def test_v2_command_includes_standalone(self):
        # v2 talks to a managed background service by default, so plugins
        # (and our lane env) never run in the lane's own process unless
        # --standalone is passed.
        cmd = oc_harness.build_run_cmd(lane("a", "look"), 2)
        self.assertIn("--standalone", cmd)

    def test_v1_command_has_no_standalone(self):
        cmd = oc_harness.build_run_cmd(lane("a", "look", dir="/tmp/repo"), 1)
        self.assertNotIn("--standalone", cmd)

    def test_brief_file_is_read(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("brief from file")
        self.addCleanup(os.unlink, f.name)
        cmd = oc_harness.build_run_cmd(lane("a", f.name), 1)
        self.assertEqual(cmd[-1], "brief from file")


class CheckRunFlagsTest(unittest.TestCase):
    def test_v1_skips_check(self):
        self.assertEqual(oc_harness.check_run_flags(1, binary="/nonexistent/opencode"), [])

    def test_v2_all_flags_present(self):
        # stub_opencode.py's own FLAGS list predates --standalone, so it can
        # never print that flag; it is the one entry this stub always misses.
        with mock.patch.dict(os.environ, {"STUB_OC_MISSING": ""}):
            self.assertEqual(oc_harness.check_run_flags(2, binary=STUB), ["--standalone"])

    def test_v2_missing_flag_named(self):
        with mock.patch.dict(os.environ, {"STUB_OC_MISSING": "--auto"}):
            self.assertEqual(oc_harness.check_run_flags(2, binary=STUB), ["--auto", "--standalone"])

    def test_v2_missing_dir_flag_is_not_required(self):
        with mock.patch.dict(os.environ, {"STUB_OC_MISSING": "--dir"}):
            self.assertEqual(oc_harness.check_run_flags(2, binary=STUB), ["--standalone"])

    def test_v2_standalone_missing_when_absent_from_help(self):
        with mock.patch("oc_harness.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="--agent --model --format --auto", stderr=""
            )
            self.assertIn("--standalone", oc_harness.check_run_flags(2, binary="opencode"))

    def test_v2_standalone_satisfied_when_present_in_help(self):
        with mock.patch("oc_harness.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout="--agent --model --format --auto --standalone", stderr="",
            )
            self.assertNotIn("--standalone", oc_harness.check_run_flags(2, binary="opencode"))


class KillGroupTest(unittest.TestCase):
    def test_kills_via_killpg_on_pid_directly(self):
        proc = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
        proc.wait()  # leader already reaped: getpgid(proc.pid) would now fail
        with mock.patch("oc_harness.os.killpg") as killpg, \
             mock.patch("oc_harness.os.getpgid") as getpgid:
            oc_harness._kill_group(proc)
        killpg.assert_called_once_with(proc.pid, signal.SIGKILL)
        getpgid.assert_not_called()

    def test_survives_missing_process_group(self):
        proc = subprocess.Popen([sys.executable, "-c", "pass"])
        proc.wait()
        with mock.patch("oc_harness.os.killpg", side_effect=ProcessLookupError()):
            oc_harness._kill_group(proc)  # must not raise


class RunLanesTest(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out, True)

    def read_done(self, lane_id):
        with open(os.path.join(self.out, lane_id + ".done")) as f:
            return json.load(f)

    def read_argvs(self, log):
        with open(log) as f:
            return [json.loads(line) for line in f]

    def test_ok_lanes_write_results_and_done(self):
        log = os.path.join(self.out, "argv.log")
        with mock.patch.dict(os.environ, {"STUB_OC_LOG": log}):
            results = oc_harness.run_lanes([lane("a", "one"), lane("b", "two")], self.out,
                                           binary=STUB, major=1)
        self.assertEqual([r["id"] for r in results], ["a", "b"])
        self.assertEqual([r["status"] for r in results], ["OK", "OK"])
        self.assertEqual(self.read_done("a")["exit"], 0)
        self.assertEqual(self.read_done("b")["status"], "OK")
        with open(os.path.join(self.out, "b.jsonl")) as f:
            self.assertIn("done: two", f.read())
        argvs = self.read_argvs(log)
        self.assertEqual(len(argvs), 2)
        self.assertIn("-m", argvs[0])

    def test_failed_lane_reports_exit_and_stderr(self):
        results = oc_harness.run_lanes([lane("f", "fail")], self.out, binary=STUB, major=1)
        self.assertEqual(results[0]["status"], "FAIL")
        self.assertEqual(results[0]["exit"], 3)
        self.assertIn("stub failure", results[0]["error"])
        self.assertEqual(self.read_done("f")["exit"], 3)

    def test_throttle_halves_width(self):
        lanes = [lane("t", "throttle"), lane("s", "slow"), lane("c", "after")]
        results = oc_harness.run_lanes(lanes, self.out, width=2, binary=STUB, major=1)
        self.assertEqual(results[0]["status"], "FAIL")
        self.assertEqual(results[0]["throttles"], 1)
        self.assertIn("1302", results[0]["error"])
        self.assertEqual(results[0]["width"], 2)
        self.assertEqual(results[1]["width"], 2)
        self.assertEqual(results[2]["width"], 1)
        self.assertEqual(results[2]["status"], "OK")

    def test_width_is_capped_at_64(self):
        results = oc_harness.run_lanes([lane("a", "one")], self.out, width=500, binary=STUB, major=1)
        self.assertEqual(results[0]["width"], 64)

    def test_stall_kills_lane(self):
        start = time.monotonic()
        results = oc_harness.run_lanes([lane("z", "stall")], self.out, stall=1, binary=STUB, major=1)
        self.assertLess(time.monotonic() - start, 15)
        self.assertEqual(results[0]["status"], "STALL")
        self.assertIn("step_start", results[0]["error"])
        self.assertEqual(self.read_done("z")["status"], "STALL")

    def test_lane_timeout_kills_lane(self):
        results = oc_harness.run_lanes([lane("z", "stall", timeout=1)], self.out, stall=60,
                                       binary=STUB, major=1)
        self.assertEqual(results[0]["status"], "TIMEOUT")
        self.assertEqual(self.read_done("z")["status"], "TIMEOUT")

    def test_missing_v2_flag_stops_run(self):
        with mock.patch.dict(os.environ, {"STUB_OC_MISSING": "--format"}):
            with self.assertRaises(SystemExit) as ctx:
                oc_harness.run_lanes([lane("a", "one")], self.out, binary=STUB, major=2)
        self.assertIn("--format", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(self.out, "a.done")))

    def test_stall_kills_lane_and_its_child_process_group(self):
        pid_file = os.path.join(self.out, "child.pid")
        start = time.monotonic()
        with mock.patch.dict(os.environ, {"STUB_CHILD_PID_FILE": pid_file}):
            results = oc_harness.run_lanes([lane("z", "stall_child")], self.out, stall=1,
                                           binary=STUB, major=1)
        self.assertLess(time.monotonic() - start, 5)
        self.assertEqual(results[0]["status"], "STALL")
        for _ in range(50):
            if os.path.exists(pid_file):
                break
            time.sleep(0.05)
        with open(pid_file) as f:
            child_pid = int(f.read().strip())
        time.sleep(0.3)
        with self.assertRaises(OSError):
            os.kill(child_pid, 0)

    def test_exception_kills_running_lane_process_groups(self):
        pid_file = os.path.join(self.out, "child2.pid")

        def sleep_side_effect(*_a, **_kw):
            # Only blow up once the stub's grandchild actually exists, so the
            # kill below has a real process-group descendant to reap.
            if os.path.exists(pid_file):
                raise RuntimeError("boom")

        with mock.patch.dict(os.environ, {"STUB_CHILD_PID_FILE": pid_file}):
            with mock.patch("oc_harness.time.sleep", side_effect=sleep_side_effect):
                with self.assertRaises(RuntimeError):
                    oc_harness.run_lanes([lane("x", "stall_child")], self.out, binary=STUB, major=1)
        with open(pid_file) as f:
            child_pid = int(f.read().strip())
        time.sleep(0.3)
        with self.assertRaises(OSError):
            os.kill(child_pid, 0)

    def test_lane_that_exits_on_its_own_but_leaves_child_holding_stdout_still_returns_promptly(self):
        pid_file = os.path.join(self.out, "child3.pid")
        start = time.monotonic()
        with mock.patch.dict(os.environ, {"STUB_CHILD_PID_FILE": pid_file}):
            results = oc_harness.run_lanes([lane("e", "exit_child")], self.out, binary=STUB, major=1)
        self.assertLess(time.monotonic() - start, 5)
        self.assertEqual(results[0]["status"], "OK")
        with open(pid_file) as f:
            child_pid = int(f.read().strip())
        time.sleep(0.3)
        with self.assertRaises(OSError):
            os.kill(child_pid, 0)

    def test_reader_join_is_bounded(self):
        original_join = threading.Thread.join
        calls = []

        def fake_join(self, timeout=None):
            calls.append(timeout)
            return original_join(self, timeout)

        with mock.patch.object(threading.Thread, "join", fake_join):
            oc_harness.run_lanes([lane("a", "one")], self.out, binary=STUB, major=1)
        self.assertTrue(calls)
        self.assertTrue(all(t is not None for t in calls))

    def test_bounded_join_lets_scheduler_proceed_even_if_group_kill_is_a_no_op(self):
        # A descendant outside the group (or a kill that otherwise fails to
        # close the pipe) must not block the scheduler loop forever: the
        # bounded reader.join() has to let run_lanes return regardless.
        pid_file = os.path.join(self.out, "child4.pid")
        start = time.monotonic()
        try:
            with mock.patch.dict(os.environ, {"STUB_CHILD_PID_FILE": pid_file}):
                with mock.patch("oc_harness._kill_group"):
                    results = oc_harness.run_lanes([lane("e", "exit_child")], self.out,
                                                   binary=STUB, major=1)
            self.assertLess(time.monotonic() - start, 10)
            self.assertEqual(results[0]["status"], "OK")
        finally:
            if os.path.exists(pid_file):
                with open(pid_file) as f:
                    child_pid = int(f.read().strip())
                try:
                    os.kill(child_pid, signal.SIGKILL)
                except OSError:
                    pass

    def test_v2_lane_starts_with_cwd_set_to_lane_dir_and_no_dir_flag_in_argv(self):
        argv_log = os.path.join(self.out, "argv.log")
        lane_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, lane_dir, True)
        with mock.patch.dict(os.environ, {"STUB_OC_LOG": argv_log, "STUB_OC_MISSING": ""}):
            with mock.patch("oc_harness.subprocess.Popen", wraps=subprocess.Popen) as popen:
                results = oc_harness.run_lanes(
                    [lane("a", "one", dir=lane_dir)], self.out, binary=STUB, major=2
                )
        self.assertEqual(results[0]["status"], "OK")
        _, kwargs = popen.call_args
        self.assertEqual(kwargs.get("cwd"), lane_dir)
        self.assertNotIn("--dir", self.read_argvs(argv_log)[0])

    def test_v1_lane_also_starts_with_cwd_set_to_lane_dir(self):
        lane_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, lane_dir, True)
        with mock.patch("oc_harness.subprocess.Popen", wraps=subprocess.Popen) as popen:
            results = oc_harness.run_lanes(
                [lane("a", "one", dir=lane_dir)], self.out, binary=STUB, major=1
            )
        self.assertEqual(results[0]["status"], "OK")
        _, kwargs = popen.call_args
        self.assertEqual(kwargs.get("cwd"), lane_dir)

    def test_detects_major_when_not_given(self):
        log = os.path.join(self.out, "argv.log")
        env = {"STUB_OC_LOG": log, "STUB_OC_VERSION": "2.0.1", "STUB_OC_MISSING": ""}
        with mock.patch.dict(os.environ, env):
            results = oc_harness.run_lanes([lane("a", "one")], self.out, binary=STUB)
        self.assertEqual(results[0]["status"], "OK")
        self.assertIn("--model", self.read_argvs(log)[0])


if __name__ == "__main__":
    unittest.main()
