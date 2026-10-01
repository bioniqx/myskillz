"""Tests for the vendored opencode runner (oc_run) and the fake opencode CLI."""
import importlib.util
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import oc_run  # noqa: E402
import hybrid_shared  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
FAKE = TESTS_DIR / "fake_opencode.py"


def _write_lines(path, items):
    lines = []
    for item in items:
        lines.append(item if isinstance(item, str) else json.dumps(item))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _tool_event(tool, status, inp, output="", error=""):
    state = {"status": status, "input": inp}
    if status == "error":
        state["error"] = error
    else:
        state["output"] = output
    return {
        "type": "tool_use",
        "sessionID": "ses_a",
        "part": {"type": "tool", "tool": tool, "state": state},
    }


def _pid_gone(pid, wait_s=5.0):
    """True once `pid` no longer exists (polls so an orphan can be reaped)."""
    deadline = time.monotonic() + wait_s
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)


class BuildCmdTest(unittest.TestCase):
    def test_variant_rides_on_model(self):
        cmd = oc_run.build_cmd("opencode", "hp-writer", "zai-coding-plan/glm-5.3", "high", "hello world")
        self.assertEqual(cmd, [
            "opencode", "run", "--standalone", "--agent", "hp-writer",
            "--model", "zai-coding-plan/glm-5.3#high", "--format", "json", "--auto",
            "--title", "hp-writer", "hello world",
        ])

    def test_empty_variant_and_no_optional_flags(self):
        cmd = oc_run.build_cmd("/bin/oc", "hp-writer", "p/m", "", "q")
        self.assertEqual(cmd[0], "/bin/oc")
        self.assertIn("p/m", cmd)
        for flag in ("--dir", "--variant", "-s", "--session", "-f"):
            self.assertNotIn(flag, cmd)
        self.assertEqual(cmd[-1], "q")

    def test_session_then_attach_then_message(self):
        cmd = oc_run.build_cmd("opencode", "hp-writer", "p/m", "low", "msg",
                               session="ses_1", attach="/abs/briefs/O01.oc.md")
        self.assertEqual(cmd, [
            "opencode", "run", "--standalone", "--agent", "hp-writer",
            "--model", "p/m#low", "--format", "json", "--auto", "--title", "hp-writer",
            "--session", "ses_1", "-f", "/abs/briefs/O01.oc.md", "msg",
        ])

    def test_session_only_and_attach_only(self):
        repair = oc_run.build_cmd("opencode", "hp-writer", "p/m", "", "fix", session="ses_2")
        self.assertEqual(repair[-3:], ["--session", "ses_2", "fix"])
        self.assertNotIn("-f", repair)
        first = oc_run.build_cmd("opencode", "hp-writer", "p/m", "", "go", attach="/abs/b.md")
        self.assertEqual(first[-3:], ["-f", "/abs/b.md", "go"])
        self.assertNotIn("--session", first)


class RegexTest(unittest.TestCase):
    def test_throttle_re(self):
        self.assertTrue(oc_run.THROTTLE_RE.search("HTTP 429 from provider"))
        self.assertTrue(oc_run.THROTTLE_RE.search("too many requests"))
        self.assertTrue(oc_run.THROTTLE_RE.search("Rate-Limit reached"))
        self.assertFalse(oc_run.THROTTLE_RE.search("used 4290 tokens"))

    def test_saved_re(self):
        match = oc_run.SAVED_RE.search("[Output truncated: full output saved to /tmp/x/tool_1.txt]")
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "/tmp/x/tool_1.txt")
        self.assertIsNone(oc_run.SAVED_RE.search("full output saved to relative/path.txt]"))


class ParseEventsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        home = self.tmp / "home"
        self.saved_dir = home / ".local" / "share" / "opencode" / "tool-output"
        self.saved_dir.mkdir(parents=True)
        patcher = mock.patch.dict(os.environ, {"HOME": str(home)})
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("XDG_DATA_HOME", None)

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_missing_file_gives_empty_result(self):
        result = oc_run.parse_events(self.tmp / "nope.jsonl")
        self.assertEqual(result, {
            "session": "",
            "text": "",
            "usage": {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0},
            "errors": [],
            "throttled": False,
            "finished": False,
            "events": 0,
            "tools": [],
        })

    def test_full_stream(self):
        saved = self.saved_dir / "tool_big.txt"
        saved.write_text("line one\nreleased 2024-12-06\n", encoding="utf-8")
        stream = self.tmp / "O01.1.jsonl"
        _write_lines(stream, [
            {"type": "step_start", "sessionID": "ses_a", "part": {"type": "step-start"}},
            {"type": "text", "sessionID": "ses_a", "part": {"type": "text", "text": "thinking"}},
            _tool_event("read", "completed", {"filePath": "/r/a.py"}, output="def foo():\n    pass\n"),
            _tool_event("webfetch", "completed", {"url": "https://example.com"},
                        output="[Output truncated: full output saved to %s]" % saved),
            _tool_event("grep", "error", {"pattern": "zzz"}, error="no matches"),
            {"type": "step_finish", "sessionID": "ses_a", "part": {
                "type": "step-finish",
                "tokens": {"input": 100, "output": 20, "reasoning": 5, "cache": {"read": 7, "write": 3}},
                "cost": 0.5,
            }},
            {"type": "step_finish", "sessionID": "ses_b", "part": {
                "type": "step-finish",
                "tokens": {"input": 10, "output": 2, "reasoning": 1, "cache": {"read": 1, "write": 0}},
                "cost": 0.25,
            }},
            {"type": "text", "sessionID": "ses_a", "part": {"type": "text", "text": "@@@ BEGIN T01\nbody\n@@@ END T01"}},
            "not json at all",
        ])
        result = oc_run.parse_events(stream)
        self.assertEqual(result["session"], "ses_a")
        self.assertEqual(result["text"], "@@@ BEGIN T01\nbody\n@@@ END T01")
        self.assertEqual(result["usage"], {
            "input": 110, "output": 22, "reasoning": 6, "cache_read": 8, "cache_write": 3, "cost": 0.75,
        })
        self.assertEqual(result["events"], 8)
        self.assertEqual(result["errors"], [])
        self.assertFalse(result["throttled"])
        self.assertEqual(len(result["tools"]), 3)
        self.assertEqual(result["tools"][0], {
            "tool": "read", "status": "completed", "input": {"filePath": "/r/a.py"},
            "output": "def foo():\n    pass\n",
        })
        self.assertEqual(result["tools"][1]["tool"], "webfetch")
        self.assertEqual(result["tools"][1]["output"], "line one\nreleased 2024-12-06\n")
        self.assertEqual(result["tools"][2], {
            "tool": "grep", "status": "error", "input": {"pattern": "zzz"}, "output": "",
        })

    def test_error_event_sets_errors_and_throttle(self):
        stream = self.tmp / "err.jsonl"
        _write_lines(stream, [
            {"type": "error", "sessionID": "ses_e",
             "error": {"type": "APIError", "message": "429 Too Many Requests"}},
        ])
        result = oc_run.parse_events(stream)
        self.assertEqual(result["errors"], ["APIError: 429 Too Many Requests"])
        self.assertTrue(result["throttled"])
        self.assertEqual(result["session"], "ses_e")

    def test_non_json_throttle_line(self):
        stream = self.tmp / "raw.jsonl"
        _write_lines(stream, ["provider says: rate limit exceeded"])
        result = oc_run.parse_events(stream)
        self.assertTrue(result["throttled"])
        self.assertEqual(result["events"], 0)

    def test_step_finish_stop_sets_finished(self):
        stream = self.tmp / "fin.jsonl"
        _write_lines(stream, [
            {"type": "step_finish", "sessionID": "ses_f",
             "part": {"type": "step-finish", "reason": "tool-calls", "tokens": {}}},
        ])
        self.assertFalse(oc_run.parse_events(stream)["finished"])
        _write_lines(stream, [
            {"type": "step_finish", "sessionID": "ses_f",
             "part": {"type": "step-finish", "reason": "tool-calls", "tokens": {}}},
            {"type": "step_finish", "sessionID": "ses_f",
             "part": {"type": "step-finish", "reason": "stop", "tokens": {}}},
        ])
        self.assertTrue(oc_run.parse_events(stream)["finished"])

    def test_missing_saved_file_keeps_marker(self):
        marker = "[Output truncated: full output saved to %s]" % (self.tmp / "gone.txt")
        stream = self.tmp / "gone.jsonl"
        _write_lines(stream, [_tool_event("webfetch", "completed", {"url": "https://x.test"}, output=marker)])
        result = oc_run.parse_events(stream)
        self.assertEqual(result["tools"][0]["output"], marker)

    def test_saved_output_is_capped(self):
        saved = self.saved_dir / "huge.txt"
        saved.write_bytes(b"a" * 2000100)
        stream = self.tmp / "huge.jsonl"
        _write_lines(stream, [_tool_event(
            "read", "completed", {"filePath": "/r/huge"},
            output="[Output truncated: full output saved to %s]" % saved,
        )])
        result = oc_run.parse_events(stream)
        self.assertEqual(len(result["tools"][0]["output"]), 2000000)

    def _output_for(self, output):
        stream = self.tmp / "confine.jsonl"
        _write_lines(stream, [_tool_event("webfetch", "completed", {"url": "https://x.test"}, output=output)])
        return oc_run.parse_events(stream)["tools"][0]["output"]

    def test_marker_outside_tool_output_dir_is_plain_text(self):
        outside = self.tmp / "secret.txt"
        outside.write_text("SECRET", encoding="utf-8")
        marker = "[Output truncated: full output saved to %s]" % outside
        self.assertEqual(self._output_for(marker), marker)

    def test_marker_escaping_tool_output_dir_is_plain_text(self):
        (self.tmp / "secret.txt").write_text("SECRET", encoding="utf-8")
        marker = "[Output truncated: full output saved to %s/../../../../../secret.txt]" % self.saved_dir
        self.assertEqual(self._output_for(marker), marker)

    def test_marker_not_at_end_is_plain_text(self):
        saved = self.saved_dir / "tool_mid.txt"
        saved.write_text("SAVED BODY", encoding="utf-8")
        output = "[Output truncated: full output saved to %s]\nmore text after" % saved
        self.assertEqual(self._output_for(output), output)

    def test_marker_at_end_inside_dir_is_resolved(self):
        saved = self.saved_dir / "tool_end.txt"
        saved.write_text("SAVED BODY", encoding="utf-8")
        output = "preview line\n[Output truncated: full output saved to %s]\n" % saved
        self.assertEqual(self._output_for(output), "SAVED BODY")


class ToolOutputRootXdgTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, str(self.tmp), ignore_errors=True)

    def test_uses_xdg_data_home_when_set(self):
        xdg = self.tmp / "xdg"
        saved_dir = xdg / "opencode" / "tool-output"
        saved_dir.mkdir(parents=True)
        saved = saved_dir / "tool_x.txt"
        saved.write_text("XDG BODY", encoding="utf-8")
        home = self.tmp / "home-unused"
        home.mkdir()
        with mock.patch.dict(os.environ, {"HOME": str(home), "XDG_DATA_HOME": str(xdg)}):
            self.assertEqual(oc_run._tool_output_root(), saved_dir)
            stream = self.tmp / "xdg.jsonl"
            _write_lines(stream, [_tool_event(
                "read", "completed", {"filePath": "/r/x"},
                output="[Output truncated: full output saved to %s]" % saved,
            )])
            result = oc_run.parse_events(stream)
        self.assertEqual(result["tools"][0]["output"], "XDG BODY")

    def test_falls_back_to_home_local_share_without_xdg_data_home(self):
        home = self.tmp / "home"
        saved_dir = home / ".local" / "share" / "opencode" / "tool-output"
        saved_dir.mkdir(parents=True)
        saved = saved_dir / "tool_y.txt"
        saved.write_text("DEFAULT BODY", encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": str(home)}):
            os.environ.pop("XDG_DATA_HOME", None)
            self.assertEqual(oc_run._tool_output_root(), saved_dir)
            stream = self.tmp / "default.jsonl"
            _write_lines(stream, [_tool_event(
                "read", "completed", {"filePath": "/r/y"},
                output="[Output truncated: full output saved to %s]" % saved,
            )])
            result = oc_run.parse_events(stream)
        self.assertEqual(result["tools"][0]["output"], "DEFAULT BODY")


def _load_fake():
    spec = importlib.util.spec_from_file_location("fake_opencode", str(FAKE))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.log = self.tmp / "log.jsonl"
        self.env = dict(os.environ, HOME=str(self.tmp / "home"), HYBRID_AUDIT_FAKE_LOG=str(self.log))
        self.env.pop("HYBRID_AUDIT_FAKE_SCRIPT", None)
        self.env.pop("OPENCODE_CONFIG_CONTENT", None)

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _call(self, argv):
        return subprocess.run(
            argv, cwd=str(self.tmp), env=self.env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False,
        )

    def _records(self):
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def test_constants(self):
        fake = _load_fake()
        self.assertEqual(fake.FAKE_SCRIPT_ENV, "HYBRID_AUDIT_FAKE_SCRIPT")
        self.assertEqual(fake.FAKE_LOG_ENV, "HYBRID_AUDIT_FAKE_LOG")

    def test_is_executable(self):
        self.assertTrue(os.access(str(FAKE), os.X_OK))
        first = FAKE.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first, "#!/usr/bin/env python3")

    def test_version_models_and_unsupported(self):
        proc = self._call([str(FAKE), "--version"])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "2.0.18")
        proc = self._call([str(FAKE), "models"])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.splitlines(), ["zai-coding-plan/glm-5.3", "zai-coding-plan/glm-5.3-flash"])
        proc = self._call([str(FAKE), "serve"])
        self.assertEqual(proc.returncode, 2)

    def test_script_list_replays_one_stream_per_round_and_logs(self):
        script = self.tmp / "script.json"
        script.write_text(json.dumps([{"text": "one"}, {"text": "two", "usage": {"input": 3}}]), encoding="utf-8")
        self.env["HYBRID_AUDIT_FAKE_SCRIPT"] = str(script)
        cmd = oc_run.build_cmd(str(FAKE), "hp-writer", "p/m", "low", "msg")
        out = self.tmp / "out.jsonl"
        texts = []
        for _ in range(3):
            proc = self._call(cmd)
            self.assertEqual(proc.returncode, 0)
            out.write_text(proc.stdout, encoding="utf-8")
            texts.append(oc_run.parse_events(out)["text"])
        self.assertEqual(texts, ["one", "two", "two"])
        records = self._records()
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["argv"], cmd[1:])
        self.assertEqual(records[0]["cwd"], str(self.tmp))
        self.assertEqual(records[0]["config"], "")
        self.assertEqual(records[0]["session"], "")
        self.assertEqual(records[0]["attach"], "")
        self.assertEqual(records[0]["attach_text"], "")

    def test_attach_and_session_are_logged_and_session_is_reused(self):
        brief = self.tmp / "O01.oc.md"
        brief.write_text("BRIEF BODY", encoding="utf-8")
        script = self.tmp / "script.json"
        script.write_text(json.dumps([{"text": "round one"}, {"text": "round two"}]), encoding="utf-8")
        self.env["HYBRID_AUDIT_FAKE_SCRIPT"] = str(script)
        out = self.tmp / "out.jsonl"
        proc = self._call(oc_run.build_cmd(str(FAKE), "hp-writer", "p/m", "", "go", attach=str(brief)))
        out.write_text(proc.stdout, encoding="utf-8")
        first = oc_run.parse_events(out)
        self.assertEqual(first["session"], "ses_fake0001")
        proc = self._call(oc_run.build_cmd(str(FAKE), "hp-writer", "p/m", "", "fix", session="ses_prev42"))
        out.write_text(proc.stdout, encoding="utf-8")
        second = oc_run.parse_events(out)
        self.assertEqual(second["session"], "ses_prev42")
        self.assertEqual(second["text"], "round two")
        records = self._records()
        self.assertEqual(records[0]["attach"], str(brief))
        self.assertEqual(records[0]["attach_text"], "BRIEF BODY")
        self.assertEqual(records[0]["session"], "")
        self.assertEqual(records[1]["session"], "ses_prev42")
        self.assertEqual(records[1]["attach"], "")

    def test_save_writes_file_before_events(self):
        saved = Path(self.env["HOME"]) / ".local/share/opencode/tool-output/tool_1.txt"
        marker = "[Output truncated: full output saved to %s]" % saved
        script = self.tmp / "script.json"
        script.write_text(json.dumps({
            "save": {str(saved): "big body"},
            "events": [{"type": "tool_use", "part": {"type": "tool", "tool": "read", "state": {
                "status": "completed", "input": {"filePath": "/r/x"}, "output": marker}}}],
            "text": "@@@ BEGIN T01\nok\n@@@ END T01",
        }), encoding="utf-8")
        self.env["HYBRID_AUDIT_FAKE_SCRIPT"] = str(script)
        proc = self._call(oc_run.build_cmd(str(FAKE), "hp-writer", "p/m", "", "msg"))
        out = self.tmp / "out.jsonl"
        out.write_text(proc.stdout, encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": self.env["HOME"]}):
            os.environ.pop("XDG_DATA_HOME", None)
            result = oc_run.parse_events(out)
        self.assertEqual(result["session"], "ses_fake0001")
        self.assertEqual(result["tools"][0]["output"], "big body")
        self.assertEqual(result["text"], "@@@ BEGIN T01\nok\n@@@ END T01")

    def test_error_step_exits_one(self):
        script = self.tmp / "script.json"
        script.write_text(json.dumps({"error": {"type": "ProviderAuthError", "message": "bad key"}}), encoding="utf-8")
        self.env["HYBRID_AUDIT_FAKE_SCRIPT"] = str(script)
        proc = self._call(oc_run.build_cmd(str(FAKE), "hp-writer", "p/m", "", "msg"))
        self.assertEqual(proc.returncode, 1)
        out = self.tmp / "out.jsonl"
        out.write_text(proc.stdout, encoding="utf-8")
        self.assertEqual(oc_run.parse_events(out)["errors"], ["ProviderAuthError: bad key"])

    def test_models_env_lists_nothing_or_a_custom_list(self):
        self.env["HYBRID_AUDIT_FAKE_MODELS"] = "none"
        proc = self._call([str(FAKE), "models"])
        self.assertEqual((proc.returncode, proc.stdout), (0, ""))
        self.env["HYBRID_AUDIT_FAKE_MODELS"] = "p/a,p/b"
        proc = self._call([str(FAKE), "models"])
        self.assertEqual(proc.stdout.splitlines(), ["p/a", "p/b"])

    def test_scenarios_expand_and_can_be_overridden(self):
        script = self.tmp / "script.json"
        script.write_text(json.dumps({"scenario": "recovered", "text": "mine"}), encoding="utf-8")
        self.env["HYBRID_AUDIT_FAKE_SCRIPT"] = str(script)
        proc = self._call(oc_run.build_cmd(str(FAKE), "hp-writer", "p/m", "", "msg"))
        self.assertEqual(proc.returncode, 1)
        out = self.tmp / "out.jsonl"
        out.write_text(proc.stdout, encoding="utf-8")
        parsed = oc_run.parse_events(out)
        self.assertEqual(parsed["text"], "mine")
        self.assertTrue(parsed["finished"])
        self.assertEqual(len(parsed["errors"]), 1)


class RunOnceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.root = self.tmp / "repo"
        self.root.mkdir()
        self.oc_dir = self.root / "docs" / "superpowers" / "plans" / ".work" / "p" / "oc"
        self.script = self.tmp / "script.json"
        self.log = self.tmp / "log.jsonl"
        self.env = dict(
            os.environ,
            HOME=str(self.tmp / "home"),
            HYBRID_AUDIT_FAKE_SCRIPT=str(self.script),
            HYBRID_AUDIT_FAKE_LOG=str(self.log),
        )
        self.env.pop("OPENCODE_CONFIG_CONTENT", None)

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _run(self, step, stall_s=30, timeout_s=60, binary=None, session="", attach=""):
        self.script.write_text(json.dumps(step), encoding="utf-8")
        cmd = oc_run.build_cmd(binary or str(FAKE), "hp-writer", "zai-coding-plan/glm-5.3-flash", "low", "Write.",
                               session=session, attach=attach)
        return oc_run.run_once(
            cmd, self.root, self.env, self.oc_dir / "O01.1.jsonl", self.oc_dir / "O01.1.err", stall_s, timeout_s,
        )

    def _record(self):
        return json.loads(self.log.read_text(encoding="utf-8").splitlines()[0])

    def test_success(self):
        result = self._run({
            "events": [_tool_event("read", "completed", {"filePath": "a.py"}, output="x = 1\n")],
            "usage": {"input": 12, "output": 4},
            "text": "@@@ BEGIN T01\nbody\n@@@ END T01",
        })
        for key in ("session", "text", "usage", "errors", "throttled", "finished", "events", "tools",
                    "rc", "reason", "note", "pid", "duration", "stderr_tail"):
            self.assertIn(key, result)
        self.assertEqual(result["rc"], 0)
        self.assertEqual(result["reason"], "")
        self.assertEqual(result["note"], "")
        self.assertGreater(result["pid"], 0)
        self.assertGreaterEqual(result["duration"], 0.0)
        self.assertEqual(result["text"], "@@@ BEGIN T01\nbody\n@@@ END T01")
        self.assertEqual(result["usage"]["input"], 12)
        self.assertEqual(result["tools"][0]["tool"], "read")
        self.assertTrue((self.oc_dir / "O01.1.jsonl").exists())
        self.assertTrue((self.oc_dir / "O01.1.err").exists())

    def test_cwd_and_pwd_are_repo_root(self):
        self.env["PWD"] = "/somewhere/else"
        self._run({"text": "ok"})
        record = self._record()
        self.assertEqual(record["cwd"], str(self.root))
        self.assertEqual(record["pwd"], str(self.root))
        self.assertEqual(record["argv"][:3], ["run", "--standalone", "--agent"])

    def test_first_turn_attaches_brief(self):
        brief = self.tmp / "O01.oc.md"
        brief.write_text("THE BRIEF", encoding="utf-8")
        result = self._run({"text": "ok"}, attach=str(brief))
        self.assertEqual(result["reason"], "")
        record = self._record()
        self.assertEqual(record["attach"], str(brief))
        self.assertEqual(record["attach_text"], "THE BRIEF")
        self.assertEqual(record["session"], "")
        self.assertEqual(record["argv"][-1], "Write.")

    def test_repair_turn_reuses_session_without_attach(self):
        result = self._run({"text": "fixed"}, session="ses_round1")
        self.assertEqual(result["session"], "ses_round1")
        record = self._record()
        self.assertEqual(record["session"], "ses_round1")
        self.assertEqual(record["attach"], "")
        self.assertNotIn("-f", record["argv"])

    def test_crash_on_nonzero_exit(self):
        result = self._run({"text": "partial", "exit": 3, "stderr": "boom"})
        self.assertEqual(result["rc"], 3)
        self.assertEqual(result["reason"], "crash")
        self.assertEqual(result["note"], "exit 3: boom")

    def test_error_event_is_auth_with_note(self):
        result = self._run({"error": {"type": "ProviderAuthError", "message": "bad key"}})
        self.assertEqual(result["rc"], 1)
        self.assertEqual(result["reason"], "auth")
        self.assertEqual(result["note"], "ProviderAuthError: bad key")

    def test_generic_error_event_is_still_crash(self):
        result = self._run({"error": {"type": "UnknownError", "message": "boom"}})
        self.assertEqual(result["rc"], 1)
        self.assertEqual(result["reason"], "crash")
        self.assertEqual(result["note"], "UnknownError: boom")

    def test_throttle_on_failed_run(self):
        result = self._run({"error": {"type": "APIError", "message": "429 Too Many Requests"}})
        self.assertEqual(result["reason"], "throttle")
        self.assertTrue(result["throttled"])
        self.assertEqual(result["note"], "APIError: 429 Too Many Requests")

    def test_stdout_throttle_line_on_failed_run_is_throttle(self):
        result = self._run({"raw": ["provider says: rate limit exceeded"], "exit": 1})
        self.assertEqual(result["rc"], 1)
        self.assertTrue(result["throttled"])
        self.assertEqual(result["reason"], "throttle")

    def test_auth_is_checked_before_throttle(self):
        message = "Your GLM Coding Plan package has expired and is temporarily unavailable"
        result = self._run({"error": {"type": "provider.rate-limit", "message": message}})
        self.assertEqual(result["rc"], 1)
        self.assertTrue(result["throttled"])
        self.assertEqual(result["reason"], "auth")
        self.assertEqual(result["note"], "provider.rate-limit: " + message)

    def test_auth_from_stderr_on_nonzero_exit(self):
        result = self._run({"exit": 1, "stderr": "401 Unauthorized"})
        self.assertEqual(result["reason"], "auth")
        self.assertEqual(result["note"], "401 Unauthorized")

    def test_scenario_auth(self):
        result = self._run({"scenario": "auth"})
        self.assertEqual((result["rc"], result["reason"]), (1, "auth"))
        self.assertEqual(result["note"], "ProviderAuthError: 401 Unauthorized")

    def test_scenario_model_not_found(self):
        result = self._run({"scenario": "model_not_found"})
        self.assertEqual(result["reason"], "model")
        self.assertIn("glm-9 not found", result["note"])

    def test_scenario_throttle(self):
        result = self._run({"scenario": "throttle"})
        self.assertEqual(result["reason"], "throttle")
        self.assertTrue(result["throttled"])

    def test_scenario_recovered_exit_one(self):
        result = self._run({"scenario": "recovered"})
        self.assertEqual(result["rc"], 1)
        self.assertTrue(result["finished"])
        self.assertEqual(result["reason"], "recovered")
        self.assertEqual(result["text"], "recovered answer")

    def test_scenario_empty_output(self):
        result = self._run({"scenario": "empty"})
        self.assertEqual((result["rc"], result["reason"], result["text"]), (0, "", ""))
        self.assertTrue(result["finished"])

    def test_stderr_tail_is_returned(self):
        result = self._run({"exit": 2, "stderr": "boom tail"})
        self.assertEqual(result["stderr_tail"], "boom tail")

    def test_unavailable_text_on_successful_run_is_not_a_failure(self):
        result = self._run({"text": "ok", "stderr": "token renew scheduled"})
        self.assertEqual(result["rc"], 0)
        self.assertEqual(result["reason"], "")

    def test_throttle_text_on_successful_run_is_not_a_failure(self):
        result = self._run({"text": "ok", "stderr": "retried after rate limit"})
        self.assertEqual(result["rc"], 0)
        self.assertEqual(result["reason"], "")
        self.assertTrue(result["throttled"])

    def test_spawn_error(self):
        result = self._run({"text": "ok"}, binary=str(self.tmp / "missing-opencode"))
        self.assertIsNone(result["rc"])
        self.assertEqual(result["reason"], "spawn")
        self.assertEqual(result["pid"], 0)
        self.assertTrue(result["note"].startswith("spawn failed:"))
        self.assertEqual(result["tools"], [])

    def _grandchild_pid(self, pid_file):
        return int(pid_file.read_text(encoding="utf-8"))

    def test_stall_kills_process(self):
        pid_file = self.tmp / "gc_stall.pid"
        result = self._run({"grandchild": str(pid_file), "sleep": 10}, stall_s=1, timeout_s=60)
        self.assertEqual(result["reason"], "stall")
        self.assertEqual(result["note"], "stall: no event for 1s")
        self.assertLess(result["duration"], 8.0)
        self.assertTrue(_pid_gone(self._grandchild_pid(pid_file)))

    def test_timeout_kills_process(self):
        pid_file = self.tmp / "gc_timeout.pid"
        result = self._run({"grandchild": str(pid_file), "ticks": 50, "tick_s": 0.1}, stall_s=30, timeout_s=1)
        self.assertEqual(result["reason"], "timeout")
        self.assertEqual(result["note"], "timeout: wall time over 1s")
        self.assertLess(result["duration"], 4.5)
        self.assertTrue(_pid_gone(self._grandchild_pid(pid_file)))

    def test_interrupt_kills_process_group(self):
        pid_file = self.tmp / "gc_interrupt.pid"

        def interrupt(_path):
            deadline = time.monotonic() + 10
            while not pid_file.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            raise KeyboardInterrupt

        with mock.patch.object(oc_run, "_size", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self._run({"grandchild": str(pid_file), "sleep": 30}, stall_s=60, timeout_s=120)
        self.assertTrue(_pid_gone(self._grandchild_pid(pid_file)))


def _v2(etype, **part):
    return {"type": etype, "sessionID": "ses_v2", "part": part}


def _done_text(text="ANSWER"):
    return _v2("text", type="text", text=text, time={"start": 1, "end": 2})


_PRINTER = "import sys; sys.stdout.write(open(sys.argv[1]).read()); sys.exit(int(sys.argv[2]))"


class V2StreamTest(unittest.TestCase):
    """opencode v2.0.20: no terminal step_finish; completion is a stream that ends in a fully streamed text part."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    @staticmethod
    def _result_kind(res):
        return res["reason"]

    def _parse(self, events):
        path = self.dir / "s.jsonl"
        path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        return oc_run.parse_events(path)

    def _run(self, events, rc):
        stream = self.dir / "stream.jsonl"
        stream.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        return oc_run.run_once([sys.executable, "-c", _PRINTER, str(stream), str(rc)], self.dir, dict(os.environ),
                            self.dir / "o.jsonl", self.dir / "e.txt", 30, 60)

    def test_step_start_plus_text_is_finished_with_zero_usage(self):
        res = self._parse([_v2("step_start", type="step-start"), _done_text("OK")])
        self.assertTrue(res["finished"])
        self.assertEqual(res["text"], "OK")
        self.assertEqual(res["usage"]["input"], 0)

    def test_tool_run_sums_the_tool_call_step_finish_only(self):
        res = self._parse([
            _v2("step_start", type="step-start"),
            _v2("tool_use", type="tool", tool="read", state={"status": "completed", "input": {}, "output": "x"}),
            _v2("step_finish", type="step-finish", reason="tool-calls", cost=0.5,
                tokens={"input": 100, "output": 6, "reasoning": 9, "cache": {"read": 1, "write": 2}}),
            _v2("step_start", type="step-start"),
            _done_text("42"),
        ])
        self.assertTrue(res["finished"])
        self.assertEqual(res["usage"], {"input": 100, "output": 6, "reasoning": 9, "cache_read": 1,
                                        "cache_write": 2, "cost": 0.5})

    def test_unfinished_shapes(self):
        streaming = _v2("text", type="text", text="par")
        cases = {
            "text without time.end": [_v2("step_start", type="step-start"), streaming],
            "narration then a tool call": [_done_text("I will read"), _v2("tool_use", type="tool", tool="read")],
            "narration then a new step": [_done_text("I will read"), _v2("step_start", type="step-start")],
            "error after the answer": [_done_text(), _v2("step_finish", type="step-finish", reason="tool-calls"),
                                       {"type": "error", "error": {"type": "unknown", "message": "late"}}],
            "no events": [],
        }
        for name, events in cases.items():
            self.assertFalse(self._parse(events)["finished"], name)

    def test_answer_after_an_error_is_finished(self):
        res = self._parse([{"type": "error", "error": {"type": "unknown", "message": "step hiccup"}},
                           _v2("step_start", type="step-start"), _done_text()])
        self.assertTrue(res["finished"])
        self.assertEqual(res["errors"], ["unknown: step hiccup"])

    def test_v1_stop_step_finish_still_finishes(self):
        res = self._parse([_v2("step_finish", type="step-finish", reason="stop"),
                           _v2("step_start", type="step-start")])
        self.assertTrue(res["finished"])

    def test_error_event_keeps_its_status(self):
        res = self._parse([{"type": "error", "error": {
            "type": "provider.auth", "status": 403, "message": "OpenCode's free tier can only be used from within OpenCode"}}])
        self.assertEqual(res["errors"], ["provider.auth (HTTP 403): OpenCode's free tier can only be used from within OpenCode"])
        self.assertEqual(hybrid_shared.classify(1, res["errors"], ""), "auth")

    def test_clean_v2_run_has_no_failure(self):
        res = self._run([_v2("step_start", type="step-start"), _done_text("OK")], 0)
        self.assertEqual(res["reason"], "")
        self.assertEqual(res["text"], "OK")

    def test_recovered_v2_run(self):
        events = [{"type": "error", "error": {"type": "unknown", "message": "step hiccup"}},
                  _v2("step_start", type="step-start"), _done_text("OK")]
        for rc in (0, 1):
            res = self._run(events, rc)
            self.assertEqual(self._result_kind(res), "recovered", rc)
            self.assertEqual(res["text"], "OK")

    def test_error_without_a_later_answer_is_not_recovered(self):
        res = self._run([{"type": "error", "error": {"type": "provider.auth", "status": 403, "message": "no"}}], 1)
        self.assertEqual(self._result_kind(res), "auth")

    def test_throttle_re_ignores_traceback_line_numbers(self):
        self.assertIsNone(oc_run.THROTTLE_RE.search('File "x.py", line 429, in main'))
        self.assertTrue(oc_run.THROTTLE_RE.search("provider.rate-limit (HTTP 429)"))
