import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
STUB = os.path.join(HERE, "stub_opencode.py")

V1_THROTTLE = {"type": "error", "error": {"name": "APIError", "data": {
    "statusCode": 429, "responseBody": "{\"error\":{\"code\":\"1302\"}}"}}}
V2_THROTTLE = {"type": "error", "error": {"type": "provider.rate-limit", "status": 429}}
ABORTED = {"type": "aborted"}

V1_RUN = ["run", "--dir", HERE, "--agent", "worker", "-m", "zai-coding-plan/glm-5.3-flash",
          "--format", "json", "--auto"]
V2_RUN = ["run", "--standalone", "--agent", "worker", "--model", "zai-coding-plan/glm-5.3#high",
          "--format", "json", "--auto"]


class StubCase(unittest.TestCase):
    version = "1.18.33"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.log = os.path.join(self.tmp, "argv.log")

    def run_stub(self, args, stdin=""):
        env = dict(os.environ, STUB_OC_VERSION=self.version, STUB_OC_LOG=self.log)
        env.pop("STUB_OC_MISSING", None)
        return subprocess.run([sys.executable, STUB] + args, input=stdin, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=30)

    def events(self, proc):
        return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

    def logged(self):
        with open(self.log) as f:
            return [json.loads(line) for line in f]


class V1ModeTest(StubCase):
    version = "1.18.33"

    def test_version_prints_env_value(self):
        self.assertEqual(self.run_stub(["--version"]).stdout.strip(), "1.18.33")

    def test_accepts_dir_and_ends_with_step_finish(self):
        proc = self.run_stub(V1_RUN + ["one"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        events = self.events(proc)
        self.assertEqual([e["type"] for e in events], ["step_start", "text", "step_finish"])
        self.assertEqual(events[1]["part"]["text"], "done: one")
        self.assertNotIn("timestamp", events[0])

    def test_rejects_standalone(self):
        proc = self.run_stub(["run", "--standalone", "--format", "json", "one"])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--standalone", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_rejects_model_variant_suffix(self):
        args = ["run", "--dir", HERE, "-m", "zai-coding-plan/glm-5.3#high", "--format", "json", "one"]
        proc = self.run_stub(args)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("UnknownError", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_unknown_flag_is_rejected(self):
        proc = self.run_stub(["run", "--bogus", "one"])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--bogus", proc.stderr)

    def test_throttle_error_shape(self):
        proc = self.run_stub(V1_RUN + ["throttle"])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.events(proc)[-1], V1_THROTTLE)

    def test_aborted_event(self):
        proc = self.run_stub(V1_RUN + ["aborted"])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.events(proc)[-1], ABORTED)

    def test_reads_brief_from_stdin_when_no_message(self):
        brief = "-leading dash brief\n"
        proc = self.run_stub(V1_RUN, stdin=brief)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.events(proc)[1]["part"]["text"], "done: " + brief)
        self.assertEqual(self.logged(), [{"argv": V1_RUN, "stdin": brief}])

    def test_argv_message_is_logged_with_empty_stdin(self):
        proc = self.run_stub(V1_RUN + ["one two"])
        self.assertEqual(self.events(proc)[1]["part"]["text"], "done: one two")
        self.assertEqual(self.logged(), [{"argv": V1_RUN + ["one two"], "stdin": ""}])


class V2ModeTest(StubCase):
    version = "2.0.18"

    def test_version_prints_env_value(self):
        self.assertEqual(self.run_stub(["--version"]).stdout.strip(), "2.0.18")

    def test_events_carry_timestamp_and_session_and_final_text_has_no_step_finish(self):
        proc = self.run_stub(V2_RUN, stdin="look")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        events = self.events(proc)
        self.assertEqual([e["type"] for e in events],
                         ["step_start", "tool_use", "step_finish", "step_start", "text"])
        self.assertEqual(events[-1]["part"]["text"], "done: look")
        for event in events:
            self.assertIsInstance(event["timestamp"], int)
            self.assertTrue(event["sessionID"])

    def test_rejects_dir(self):
        proc = self.run_stub(V2_RUN + ["--dir", HERE], stdin="look")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--dir", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_requires_standalone(self):
        args = ["run", "--agent", "worker", "--model", "zai-coding-plan/glm-5.3", "--format", "json"]
        proc = self.run_stub(args, stdin="look")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--standalone", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_throttle_error_shape(self):
        proc = self.run_stub(V2_RUN, stdin="throttle")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.events(proc)[-1], V2_THROTTLE)

    def test_aborted_event(self):
        proc = self.run_stub(V2_RUN, stdin="aborted")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.events(proc)[-1], ABORTED)

    def test_argv_message_with_whitespace_arrives_quoted(self):
        proc = self.run_stub(V2_RUN + ["one two"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.events(proc)[-1]["part"]["text"], 'done: "one two"')

    def test_stdin_brief_is_verbatim_and_logged(self):
        brief = "line one\nline two\n"
        proc = self.run_stub(V2_RUN, stdin=brief)
        self.assertEqual(self.events(proc)[-1]["part"]["text"], "done: " + brief)
        self.assertEqual(self.logged(), [{"argv": V2_RUN, "stdin": brief}])


if __name__ == "__main__":
    unittest.main()
