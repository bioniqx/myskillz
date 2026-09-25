import json
import os
import shutil
import stat
import sys
import tempfile
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

    def test_v2_command_uses_long_model_flag(self):
        cmd = oc_harness.build_run_cmd(lane("a", "look", dir="/tmp/repo", model="pro"), 2, binary="oc2")
        self.assertEqual(cmd, [
            "oc2", "run", "--dir", "/tmp/repo", "--agent", "worker",
            "--model", "zai-coding-plan/glm-5.3", "--format", "json", "--auto", "look",
        ])

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
        with mock.patch.dict(os.environ, {"STUB_OC_MISSING": ""}):
            self.assertEqual(oc_harness.check_run_flags(2, binary=STUB), [])

    def test_v2_missing_flag_named(self):
        with mock.patch.dict(os.environ, {"STUB_OC_MISSING": "--auto"}):
            self.assertEqual(oc_harness.check_run_flags(2, binary=STUB), ["--auto"])


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

    def test_detects_major_when_not_given(self):
        log = os.path.join(self.out, "argv.log")
        env = {"STUB_OC_LOG": log, "STUB_OC_VERSION": "2.0.1", "STUB_OC_MISSING": ""}
        with mock.patch.dict(os.environ, env):
            results = oc_harness.run_lanes([lane("a", "one")], self.out, binary=STUB)
        self.assertEqual(results[0]["status"], "OK")
        self.assertIn("--model", self.read_argvs(log)[0])


if __name__ == "__main__":
    unittest.main()
