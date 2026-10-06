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


class IsThrottleEventTest(unittest.TestCase):
    def test_v2_rate_limit_error_is_a_throttle(self):
        self.assertTrue(oc_harness.is_throttle_event(
            {"type": "error", "error": {"type": "provider.rate-limit", "status": 429}}))

    def test_v2_status_429_alone_is_a_throttle(self):
        self.assertTrue(oc_harness.is_throttle_event(
            {"type": "error", "error": {"type": "provider.unknown", "status": 429}}))

    def test_v1_api_error_429_is_a_throttle(self):
        self.assertTrue(oc_harness.is_throttle_event(
            {"type": "error", "error": {"name": "APIError", "data": {"statusCode": 429}}}))

    def test_v1_api_error_body_codes_are_throttles(self):
        for code in ("1302", "1305"):
            body = json.dumps({"error": {"code": code}})
            with self.subTest(code=code):
                self.assertTrue(oc_harness.is_throttle_event(
                    {"type": "error",
                     "error": {"name": "APIError", "data": {"statusCode": 500, "responseBody": body}}}))

    def test_v1_contract_shape_is_a_throttle(self):
        line = ('{"type":"error","error":{"name":"APIError","data":{"statusCode":429,'
                '"responseBody":"{\\"error\\":{\\"code\\":\\"1302\\"}}"}}}')
        self.assertTrue(oc_harness.is_throttle_event(json.loads(line)))

    def test_other_errors_are_not_throttles(self):
        for event in [
            {"type": "error", "error": {"type": "provider.auth", "status": 401}},
            {"type": "error", "error": {"name": "APIError",
                                        "data": {"statusCode": 500,
                                                 "responseBody": '{"error":{"code":"1301"}}'}}},
            {"type": "error", "error": {"name": "APIError", "data": {"statusCode": 500,
                                                                     "responseBody": "not json"}}},
            {"type": "error", "error": "429"},
            {"type": "error"},
        ]:
            with self.subTest(event=event):
                self.assertFalse(oc_harness.is_throttle_event(event))

    def test_tool_output_never_counts(self):
        for event in [
            {"type": "tool_use", "part": {"state": {"output": "HTTP 429 Too Many Requests"}}},
            {"type": "tool_use", "part": {"state": {"output": '{"code":"1302","status":429}'}}},
            {"type": "text", "part": {"type": "text", "text": "the API said 1305"}},
            {"type": "step_finish", "part": {"tokens": {"input": 429}}},
        ]:
            with self.subTest(event=event):
                self.assertFalse(oc_harness.is_throttle_event(event))

    def test_non_dict_is_not_a_throttle(self):
        for event in (None, [], "429", 429):
            self.assertFalse(oc_harness.is_throttle_event(event))


class ReadEventsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_events(self, lines):
        class FakeProc:
            stdout = lines
        state = {"proc": FakeProc(), "out": os.path.join(self.tmp, "x.jsonl"),
                 "last": 0, "last_event": "", "throttles": 0, "error": ""}
        oc_harness._read_events(state)
        return state

    def test_null_error_field_is_not_flagged(self):
        # {"error": null} must not be treated as an error event: only a truthy
        # `error` value (or type == "error") should set state["error"].
        state = self.run_events(['{"error": null}\n'])
        self.assertEqual(state["error"], "")

    def test_truthy_error_field_is_flagged(self):
        state = self.run_events(['{"error": "boom"}\n'])
        self.assertEqual(state["error"], '{"error": "boom"}')

    def test_tool_output_quoting_429_is_not_a_throttle(self):
        state = self.run_events([
            '{"type":"tool_use","part":{"state":{"output":"HTTP 429 Too Many Requests"}}}\n',
            '{"type":"tool_use","part":{"state":{"output":"{\\"code\\":\\"1302\\"}"}}}\n',
        ])
        self.assertEqual(state["throttles"], 0)
        self.assertEqual(state["error"], "")

    def test_error_event_throttle_is_counted(self):
        line = '{"type":"error","error":{"type":"provider.rate-limit","status":429}}'
        state = self.run_events([line + "\n"])
        self.assertEqual(state["throttles"], 1)
        self.assertEqual(state["error"], line)

    def test_aborted_event_is_recorded_as_the_lane_error(self):
        state = self.run_events(['{"type":"step_start"}\n', '{"type":"aborted"}\n'])
        self.assertEqual(state["error"], '{"type":"aborted"}')
        self.assertTrue(state["aborted"])
        self.assertEqual(state["throttles"], 0)


def help_text(text):
    """subprocess.run stand-in: check_run_flags reads `run --help` from the file passed as stdout."""
    def run(cmd, stdout=None, **kwargs):
        stdout.write(text.encode())
        return subprocess.CompletedProcess(cmd, 0)
    return run


class BuildRunCmdTest(unittest.TestCase):
    def test_v1_command(self):
        cmd = oc_harness.build_run_cmd(lane("a", "look", dir="/tmp/repo"), 1)
        self.assertEqual(cmd, [
            "opencode", "run", "--dir", "/tmp/repo", "--agent", "worker",
            "-m", "zai-coding-plan/glm-5.3-flash", "--format", "json", "--auto",
        ])

    def test_v2_command_uses_long_model_flag_and_no_dir(self):
        cmd = oc_harness.build_run_cmd(lane("a", "look", dir="/tmp/repo", model="pro"), 2, binary="oc2")
        self.assertEqual(cmd, [
            "oc2", "run", "--standalone", "--agent", "worker",
            "--model", "zai-coding-plan/glm-5.3", "--format", "json", "--auto",
        ])
        self.assertNotIn("--dir", cmd)

    def test_v2_command_includes_standalone(self):
        # v2 talks to a managed background service by default, so plugins
        # (and our lane env) never run in the lane's own process unless
        # --standalone is passed.
        cmd = oc_harness.build_run_cmd(lane("a", "look"), 2)
        self.assertIn("--standalone", cmd)

    def test_v2_effort_rides_on_the_model_variant(self):
        cmd = oc_harness.build_run_cmd(lane("a", "look", model="pro", effort="max"), 2)
        self.assertIn("zai-coding-plan/glm-5.3#max", cmd)

    def test_v2_invalid_or_missing_effort_adds_no_variant(self):
        for extra in ({}, {"effort": "medium"}):
            with self.subTest(extra=extra):
                cmd = oc_harness.build_run_cmd(lane("a", "look", **extra), 2)
                self.assertIn("zai-coding-plan/glm-5.3-flash", cmd)

    def test_v1_never_gets_a_variant_suffix(self):
        # v1.18 rejects `#variant`; it reads effort from the agent's reasoningEffort instead
        cmd = oc_harness.build_run_cmd(lane("a", "look", effort="high"), 1)
        self.assertIn("zai-coding-plan/glm-5.3-flash", cmd)

    def test_v1_command_has_no_standalone(self):
        cmd = oc_harness.build_run_cmd(lane("a", "look", dir="/tmp/repo"), 1)
        self.assertNotIn("--standalone", cmd)

    def test_brief_file_is_read(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("brief from file")
        self.addCleanup(os.unlink, f.name)
        self.assertEqual(oc_harness._lane_brief(lane("a", f.name)), "brief from file")
        self.assertNotIn("brief from file", oc_harness.build_run_cmd(lane("a", f.name), 1))

    def test_brief_is_never_in_argv(self):
        for major in (1, 2):
            with self.subTest(major=major):
                cmd = oc_harness.build_run_cmd(lane("a", "- look at  this"), major)
                self.assertNotIn("- look at  this", cmd)
                self.assertEqual(cmd[-1], "--auto")


class CheckRunFlagsTest(unittest.TestCase):
    def test_v1_skips_check(self):
        self.assertEqual(oc_harness.check_run_flags(1, binary="/nonexistent/opencode"), [])

    def test_v2_all_flags_present(self):
        with mock.patch.dict(os.environ, {"STUB_OC_MISSING": ""}):
            self.assertEqual(oc_harness.check_run_flags(2, binary=STUB), [])

    def test_v2_missing_flag_named(self):
        with mock.patch.dict(os.environ, {"STUB_OC_MISSING": "--auto"}):
            self.assertEqual(oc_harness.check_run_flags(2, binary=STUB), ["--auto"])

    def test_v2_missing_dir_flag_is_not_required(self):
        with mock.patch.dict(os.environ, {"STUB_OC_MISSING": "--dir"}):
            self.assertEqual(oc_harness.check_run_flags(2, binary=STUB), [])

    def test_v2_standalone_missing_when_absent_from_help(self):
        with mock.patch("oc_harness.subprocess.run", side_effect=help_text("--agent --model --format --auto")):
            self.assertIn("--standalone", oc_harness.check_run_flags(2, binary="opencode"))

    def test_v2_standalone_satisfied_when_present_in_help(self):
        with mock.patch("oc_harness.subprocess.run",
                        side_effect=help_text("--agent --model --format --auto --standalone")):
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


class LaneStallTest(unittest.TestCase):
    def test_stall_by_role_table(self):
        self.assertEqual(oc_harness.STALL_BY_ROLE, {
            "glm-programmer": 900, "glm-programmer-lite": 900, "glm-team-leader": 900,
            "glm-code-reviewer": 600, "glm-spot-reviewer": 600, "glm-investigator": 600,
        })

    def test_lane_stall_value_wins(self):
        self.assertEqual(oc_harness.lane_stall({"stall": 42, "role": "glm-programmer"}), 42)
        self.assertEqual(oc_harness.lane_stall({"stall": "42"}), 42)

    def test_role_defaults(self):
        for role, seconds in (("glm-programmer", 900), ("glm-programmer-lite", 900), ("glm-team-leader", 900),
                              ("glm-code-reviewer", 600), ("glm-spot-reviewer", 600), ("glm-investigator", 600)):
            with self.subTest(role=role):
                self.assertEqual(oc_harness.lane_stall({"role": role}), seconds)

    def test_role_from_env_then_agent(self):
        self.assertEqual(oc_harness.lane_stall({"env": {"DEVTEAM_ROLE": "glm-spot-reviewer"}}), 600)
        self.assertEqual(oc_harness.lane_stall({"agent": "glm-team-leader"}), 900)

    def test_unknown_role_uses_default(self):
        self.assertEqual(oc_harness.lane_stall({"agent": "worker"}), 180)
        self.assertEqual(oc_harness.lane_stall({"agent": "worker"}, default=30), 30)

    def test_invalid_stall_falls_through(self):
        self.assertEqual(oc_harness.lane_stall({"stall": "soon", "role": "glm-investigator"}), 600)
        self.assertEqual(oc_harness.lane_stall({"stall": 0}), 180)
        self.assertEqual(oc_harness.lane_stall({"stall": None}, default=7), 7)


class RunLanesTest(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out, True)

    def read_done(self, lane_id):
        with open(os.path.join(self.out, lane_id + ".done")) as f:
            return json.load(f)

    def read_log(self, log):
        """One stub log entry per run: {"argv": [...], "stdin": "..."}."""
        with open(log) as f:
            return [json.loads(line) for line in f if line.strip()]

    def read_argvs(self, log):
        return [entry["argv"] for entry in self.read_log(log)]

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

    def test_width_is_capped_at_8(self):
        results = oc_harness.run_lanes([lane("a", "one")], self.out, width=500, binary=STUB, major=1)
        self.assertEqual(results[0]["width"], oc_harness.MAX_PARALLEL)
        self.assertEqual(oc_harness.MAX_PARALLEL, 8)

    def test_default_width_is_6(self):
        results = oc_harness.run_lanes([lane("a", "one")], self.out, binary=STUB, major=1)
        self.assertEqual(results[0]["width"], oc_harness.DEFAULT_LANES)
        self.assertEqual(oc_harness.DEFAULT_LANES, 6)

    def test_env_lanes_clamps(self):
        for raw, want in (("", 6), ("abc", 6), ("0", 1), ("-3", 1), ("3", 3), ("8", 8), ("20", 8), (None, 6)):
            with mock.patch.dict(os.environ):
                os.environ.pop("OC_MAX_LANES", None)
                if raw is not None:
                    os.environ["OC_MAX_LANES"] = raw
                self.assertEqual(oc_harness.env_lanes(), want, raw)

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

    def test_missing_standalone_flag_stops_run(self):
        # No special case: --standalone missing from `opencode run --help`
        # blocks the whole wave just like any other RUN_FLAG.
        with mock.patch.dict(os.environ, {"STUB_OC_MISSING": "--standalone"}):
            with self.assertRaises(SystemExit) as ctx:
                oc_harness.run_lanes([lane("a", "one")], self.out, binary=STUB, major=2)
        self.assertIn("--standalone", str(ctx.exception))
        self.assertFalse(os.path.exists(os.path.join(self.out, "a.done")))

    def test_v1_relative_dir_resolves_once(self):
        log = os.path.join(self.out, "argv.log")
        lane_dir_abs = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, lane_dir_abs, True)
        rel_dir = os.path.relpath(lane_dir_abs, os.getcwd())
        with mock.patch.dict(os.environ, {"STUB_OC_LOG": log}):
            with mock.patch("oc_harness.subprocess.Popen", wraps=subprocess.Popen) as popen:
                results = oc_harness.run_lanes(
                    [lane("a", "one", dir=rel_dir)], self.out, binary=STUB, major=1
                )
        self.assertEqual(results[0]["status"], "OK")
        _, kwargs = popen.call_args
        self.assertEqual(kwargs.get("cwd"), lane_dir_abs)
        argv = self.read_argvs(log)[0]
        self.assertEqual(argv[argv.index("--dir") + 1], lane_dir_abs)

    def test_missing_lane_dir_fails_lane_not_whole_wave(self):
        results = oc_harness.run_lanes(
            [lane("bad", "one", dir="/nonexistent/lane/dir/xyz"), lane("good", "two")],
            self.out, binary=STUB, major=1,
        )
        by_id = {r["id"]: r for r in results}
        self.assertEqual(by_id["bad"]["status"], "FAIL")
        self.assertTrue(by_id["bad"]["error"])
        self.assertEqual(by_id["good"]["status"], "OK")

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
        env = {"STUB_OC_LOG": argv_log, "STUB_OC_VERSION": "2.0.18", "STUB_OC_MISSING": ""}
        with mock.patch.dict(os.environ, env):
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

    def test_v2_rate_limit_error_halves_width(self):
        env = {"STUB_OC_VERSION": "2.0.18", "STUB_OC_MISSING": ""}
        with mock.patch.dict(os.environ, env):
            results = oc_harness.run_lanes([lane("t", "throttle"), lane("c", "one")], self.out,
                                           width=2, binary=STUB, major=2)
        self.assertEqual(results[0]["status"], "FAIL")
        self.assertEqual(results[0]["throttles"], 1)
        self.assertIn("provider.rate-limit", results[0]["error"])

    def test_v2_aborted_event_fails_the_lane(self):
        env = {"STUB_OC_VERSION": "2.0.18", "STUB_OC_MISSING": ""}
        with mock.patch.dict(os.environ, env):
            results = oc_harness.run_lanes([lane("x", "aborted")], self.out, binary=STUB, major=2)
        self.assertEqual(results[0]["status"], "FAIL")
        self.assertIn("aborted", results[0]["error"])
        self.assertEqual(self.read_done("x")["status"], "FAIL")

    def test_brief_goes_to_stdin_not_argv(self):
        log = os.path.join(self.out, "argv.log")
        with mock.patch.dict(os.environ, {"STUB_OC_LOG": log}):
            results = oc_harness.run_lanes([lane("a", "one")], self.out, binary=STUB, major=1)
        self.assertEqual(results[0]["status"], "OK")
        entry = self.read_log(log)[0]
        self.assertEqual(entry["stdin"], "one")
        self.assertNotIn("one", entry["argv"])

    def test_brief_file_content_goes_to_stdin(self):
        log = os.path.join(self.out, "argv.log")
        brief_path = os.path.join(self.out, "brief.md")
        with open(brief_path, "w") as f:
            f.write("one")
        with mock.patch.dict(os.environ, {"STUB_OC_LOG": log}):
            results = oc_harness.run_lanes([lane("a", brief_path)], self.out, binary=STUB, major=1)
        self.assertEqual(results[0]["status"], "OK")
        entry = self.read_log(log)[0]
        self.assertEqual(entry["stdin"], "one")
        self.assertNotIn(brief_path, entry["argv"])

    def test_v2_dash_and_whitespace_brief_arrives_verbatim_and_stdin_is_closed(self):
        log = os.path.join(self.out, "argv.log")
        brief = "- starts with a dash\n  and has  spaces"
        env = {"STUB_OC_LOG": log, "STUB_OC_VERSION": "2.0.18", "STUB_OC_MISSING": ""}
        start = time.monotonic()
        with mock.patch.dict(os.environ, env):
            oc_harness.run_lanes([lane("d", brief)], self.out, stall=30, binary=STUB, major=2)
        self.assertLess(time.monotonic() - start, 15)
        entry = self.read_log(log)[0]
        self.assertEqual(entry["stdin"], brief)
        self.assertNotIn(brief, entry["argv"])

    def test_lane_stall_overrides_run_default(self):
        start = time.monotonic()
        results = oc_harness.run_lanes([lane("z", "stall", stall=1)], self.out, stall=60,
                                       binary=STUB, major=1)
        self.assertLess(time.monotonic() - start, 15)
        self.assertEqual(results[0]["status"], "STALL")
        self.assertIn("no event for 1s", results[0]["error"])


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out, True)

    def test_pgid_file_names_the_lane_process_group_while_it_runs(self):
        pgid_path = os.path.join(self.out, "p.pgid")
        seen = []

        def sleep_side_effect(*_a, **_kw):
            if os.path.exists(pgid_path):
                with open(pgid_path) as f:
                    seen.append(int(f.read().strip()))
                raise RuntimeError("stop")

        with mock.patch("oc_harness.time.sleep", side_effect=sleep_side_effect):
            with self.assertRaises(RuntimeError):
                oc_harness.run_lanes([lane("p", "stall")], self.out, stall=5, binary=STUB, major=1)
        self.assertEqual(len(seen), 1)
        self.assertGreater(seen[0], 0)
        self.assertFalse(os.path.exists(pgid_path))

    def test_pgid_file_removed_when_lane_finishes(self):
        results = oc_harness.run_lanes([lane("a", "one")], self.out, binary=STUB, major=1)
        self.assertEqual(results[0]["status"], "OK")
        self.assertTrue(os.path.exists(os.path.join(self.out, "a.done")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "a.pgid")))

    def test_signal_handlers_are_restored(self):
        before = signal.getsignal(signal.SIGTERM)
        oc_harness.run_lanes([lane("a", "one")], self.out, binary=STUB, major=1)
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)

    def test_sigterm_kills_every_lane_process_group(self):
        pid_file = os.path.join(self.out, "child.pid")
        script = (
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "import oc_harness\n"
            "oc_harness.run_lanes([%r], %r, binary=%r, major=1)\n"
        ) % (os.path.dirname(HERE), lane("x", "stall_child"), self.out, STUB)
        env = dict(os.environ, STUB_CHILD_PID_FILE=pid_file, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.Popen([sys.executable, "-c", script], env=env)

        def reap():
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        self.addCleanup(reap)
        for _ in range(200):
            if os.path.exists(pid_file) and os.path.getsize(pid_file):
                break
            time.sleep(0.05)
        with open(pid_file) as f:
            child_pid = int(f.read().strip())
        self.assertTrue(os.path.exists(os.path.join(self.out, "x.pgid")))
        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(10), 128 + signal.SIGTERM)
        time.sleep(0.3)
        with self.assertRaises(OSError):
            os.kill(child_pid, 0)
        self.assertFalse(os.path.exists(os.path.join(self.out, "x.pgid")))


class LaneResultsTest(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out, True)

    def write_jsonl(self, lane_id, items):
        with open(os.path.join(self.out, lane_id + ".jsonl"), "w") as f:
            for item in items:
                f.write((item if isinstance(item, str) else json.dumps(item)) + "\n")

    def write_done(self, lane_id, status, error=""):
        with open(os.path.join(self.out, lane_id + ".done"), "w") as f:
            json.dump({"id": lane_id, "status": status, "error": error}, f)

    def test_final_text_is_the_last_step_with_text(self):
        self.write_jsonl("a", [
            {"type": "step_start", "part": {}},
            {"type": "text", "part": {"type": "text", "text": "thinking out loud"}},
            {"type": "tool_use", "part": {"state": {"output": "429 Too Many Requests"}}},
            {"type": "step_finish", "part": {}},
            {"type": "step_start", "part": {}},
            {"type": "text", "part": {"type": "text", "text": "FINAL ANSWER"}},
        ])
        self.write_done("a", "OK")
        self.assertEqual(oc_harness.lane_results(self.out),
                         [{"id": "a", "status": "OK", "error": "", "text": "FINAL ANSWER"}])

    def test_trailing_tool_only_step_keeps_the_earlier_text(self):
        self.write_jsonl("a", [
            {"type": "step_start"},
            {"type": "text", "text": "answer"},
            {"type": "step_finish"},
            {"type": "step_start"},
            {"type": "tool_use", "part": {"state": {"output": "ls"}}},
            "not json",
        ])
        self.write_done("a", "OK")
        self.assertEqual(oc_harness.lane_results(self.out)[0]["text"], "answer")

    def test_lane_without_done_is_running_and_rows_are_sorted(self):
        self.write_jsonl("b", [{"type": "text", "part": {"text": "partial"}}])
        self.write_jsonl("a", [])
        self.write_done("a", "FAIL", "boom")
        rows = oc_harness.lane_results(self.out)
        self.assertEqual([r["id"] for r in rows], ["a", "b"])
        self.assertEqual(rows[0], {"id": "a", "status": "FAIL", "error": "boom", "text": ""})
        self.assertEqual(rows[1]["status"], "RUNNING")
        self.assertEqual(rows[1]["text"], "partial")

    def test_missing_out_dir_is_empty(self):
        self.assertEqual(oc_harness.lane_results(os.path.join(self.out, "nope")), [])

    def test_result_cli_prints_each_lane_text(self):
        self.write_jsonl("a", [{"type": "text", "part": {"text": "answer a"}}])
        self.write_done("a", "OK")
        self.write_jsonl("b", [])
        self.write_done("b", "FAIL", "boom")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = oc_harness.main(["result", self.out])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("LANE a: OK\nanswer a\n", out)
        self.assertIn("LANE b: FAIL boom\n(no assistant text)\n", out)
        self.assertIn("NEXT: rerun only lanes b", out)

    def test_result_cli_empty_dir_exits_1(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = oc_harness.main(["result", self.out])
        self.assertEqual(code, 1)
        self.assertIn("NEXT:", buf.getvalue())

    def test_result_cli_as_script(self):
        self.write_jsonl("a", [{"type": "text", "part": {"text": "answer a"}}])
        self.write_done("a", "OK")
        script = os.path.join(os.path.dirname(HERE), "oc_harness.py")
        proc = subprocess.run([sys.executable, script, "result", self.out],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("LANE a: OK\nanswer a\n", proc.stdout)


class CheckHomeTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.other = tempfile.mkdtemp()
        self.skill = tempfile.mkdtemp()
        for path in (self.home, self.other, self.skill):
            self.addCleanup(shutil.rmtree, path, True)
        with open(os.path.join(self.skill, "SKILL.md"), "w") as f:
            f.write("---\nname: demo\ndescription: demo skill\n---\nbody\n")

    def install_marker(self, major):
        skill_dst = os.path.join(self.home, ".config", "opencode", "skills", "demo")
        os.makedirs(skill_dst)
        with open(os.path.join(skill_dst, ".oc-major"), "w") as f:
            f.write(str(major))

    def test_missing_under_given_home(self):
        self.assertEqual(oc_harness.check(self.skill, home=self.home),
                         ["MISSING: demo is not installed for OpenCode"])

    def test_installed_under_given_home_not_user_home(self):
        self.install_marker(1)
        with mock.patch.dict(os.environ, {"HOME": self.other}):
            with mock.patch("oc_harness.detect", return_value=1):
                lines = oc_harness.check(self.skill, home=self.home)
        self.assertEqual(lines, ["INSTALLED: demo (major 1)"])

    def test_check_cli_home_flag(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = oc_harness.main(["check", self.skill, "--home", self.home])
        self.assertEqual(code, 1)
        self.assertIn("MISSING: demo is not installed for OpenCode", buf.getvalue())


# Real opencode 1.18.33 stderr when two `run` lanes start together on a fresh data dir.
V1_DB_LOCKED_BIN = r"""#!/bin/sh
cat >/dev/null
echo x >> "$RACE_COUNT"
n=$(wc -l < "$RACE_COUNT" | tr -d ' ')
if [ "$n" -le "$RACE_FAILS" ]; then
  [ -n "$RACE_EVENT" ] && echo '{"type":"step_start","part":{"type":"step-start"}}'
  printf '\033[91m\033[1mError: \033[0mUnexpected error\n\n%s\n' "$RACE_MSG" >&2
  exit 1
fi
echo '{"type":"text","part":{"type":"text","text":"ok"}}'
"""


class V1DatabaseLockedRetryTest(unittest.TestCase):
    """v1 lanes started together race on SQLite migrations; a loser that emitted no event is
    retried up to three times."""

    def setUp(self):
        patcher = mock.patch.object(oc_harness, "RACE_RETRY_DELAY", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, fails, event="", msg="database is locked"):
        tmp = tempfile.mkdtemp(prefix="oc-v1-lock-")
        self.addCleanup(shutil.rmtree, tmp, True)
        binary = os.path.join(tmp, "opencode")
        with open(binary, "w") as fh:
            fh.write(V1_DB_LOCKED_BIN)
        os.chmod(binary, 0o755)
        count = os.path.join(tmp, "count")
        item = lane("lock", "hi", dir=tmp,
                    env={"RACE_COUNT": count, "RACE_FAILS": str(fails), "RACE_EVENT": event,
                         "RACE_MSG": msg})
        rows = oc_harness.run_lanes([item], os.path.join(tmp, "out"), width=2, stall=60,
                                    binary=binary, major=1)
        with open(count) as fh:
            return rows[0], len(fh.read().splitlines())

    def test_locked_retried_then_ok(self):
        row, attempts = self._run(2)
        self.assertEqual((row["status"], attempts), ("OK", 3), row)

    def test_failed_migration_query_retried(self):
        row, attempts = self._run(1, msg="Failed query: \n        CREATE TABLE `workspace` (")
        self.assertEqual((row["status"], attempts), ("OK", 2), row)

    def test_locked_retried_at_most_three_times(self):
        row, attempts = self._run(99)
        self.assertEqual((row["status"], attempts), ("FAIL", 4), row)
        self.assertIn("database is locked", row["error"])

    def test_other_v1_failure_not_retried(self):
        row, attempts = self._run(1, msg="something else")
        self.assertEqual((row["status"], attempts), ("FAIL", 1), row)

    def test_locked_after_an_event_not_retried(self):
        row, attempts = self._run(1, event="1")
        self.assertEqual((row["status"], attempts), ("FAIL", 1), row)

    def test_retry_waits_longer_after_each_attempt(self):
        oc_harness.RACE_RETRY_DELAY = 0.2
        start = time.monotonic()
        row, attempts = self._run(2)
        self.assertEqual((row["status"], attempts), ("OK", 3), row)
        self.assertGreaterEqual(time.monotonic() - start, 0.2 * 1 + 0.2 * 2)


if __name__ == "__main__":
    unittest.main()
