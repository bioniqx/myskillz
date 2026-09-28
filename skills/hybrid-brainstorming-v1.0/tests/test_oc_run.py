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
        cmd = oc_run.build_cmd("opencode", "hb-lane", "zai-coding-plan/glm-5.3", "high", "hello world")
        self.assertEqual(cmd, [
            "opencode", "run", "--standalone", "--agent", "hb-lane",
            "--model", "zai-coding-plan/glm-5.3#high", "--format", "json", "--auto", "hello world",
        ])

    def test_empty_variant_and_no_forbidden_flags(self):
        cmd = oc_run.build_cmd("/bin/oc", "hb-lane", "p/m", "", "q")
        self.assertEqual(cmd[0], "/bin/oc")
        self.assertIn("p/m", cmd)
        for flag in ("--dir", "--variant", "-s", "--session"):
            self.assertNotIn(flag, cmd)
        self.assertEqual(cmd[-1], "q")


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
            "events": 0,
            "tools": [],
        })

    def test_full_stream(self):
        saved = self.saved_dir / "tool_big.txt"
        saved.write_text("line one\nreleased 2024-12-06\n", encoding="utf-8")
        stream = self.tmp / "lane.jsonl"
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
            {"type": "text", "sessionID": "ses_a", "part": {"type": "text", "text": "FINDINGS\n- a.py:1 foo"}},
            "not json at all",
        ])
        result = oc_run.parse_events(stream)
        self.assertEqual(result["session"], "ses_a")
        self.assertEqual(result["text"], "FINDINGS\n- a.py:1 foo")
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
        self.env = dict(os.environ, HOME=str(self.tmp / "home"), HB_FAKE_LOG=str(self.log))
        self.env.pop("HB_FAKE_SCRIPT", None)
        self.env.pop("OPENCODE_CONFIG_CONTENT", None)

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _call(self, argv):
        return subprocess.run(
            argv, cwd=str(self.tmp), env=self.env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, check=False,
        )

    def test_constants(self):
        fake = _load_fake()
        self.assertEqual(fake.FAKE_SCRIPT_ENV, "HB_FAKE_SCRIPT")
        self.assertEqual(fake.FAKE_LOG_ENV, "HB_FAKE_LOG")

    def test_is_executable(self):
        self.assertTrue(os.access(str(FAKE), os.X_OK))
        first = FAKE.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(first, "#!/usr/bin/env python3")

    def test_version_and_unsupported(self):
        proc = self._call([str(FAKE), "--version"])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "2.0.18")
        proc = self._call([str(FAKE), "serve"])
        self.assertEqual(proc.returncode, 2)

    def test_script_list_replays_in_order_and_logs(self):
        script = self.tmp / "script.json"
        script.write_text(json.dumps([{"text": "one"}, {"text": "two", "usage": {"input": 3}}]), encoding="utf-8")
        self.env["HB_FAKE_SCRIPT"] = str(script)
        cmd = oc_run.build_cmd(str(FAKE), "hb-lane", "p/m", "low", "msg")
        out = self.tmp / "out.jsonl"
        texts = []
        for _ in range(3):
            proc = self._call(cmd)
            self.assertEqual(proc.returncode, 0)
            out.write_text(proc.stdout, encoding="utf-8")
            texts.append(oc_run.parse_events(out)["text"])
        self.assertEqual(texts, ["one", "two", "two"])
        records = [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0]["argv"], cmd[1:])
        self.assertEqual(records[0]["cwd"], str(self.tmp))
        self.assertEqual(records[0]["config"], "")

    def test_save_writes_file_before_events(self):
        saved = Path(self.env["HOME"]) / ".local/share/opencode/tool-output/tool_1.txt"
        marker = "[Output truncated: full output saved to %s]" % saved
        script = self.tmp / "script.json"
        script.write_text(json.dumps({
            "save": {str(saved): "big body"},
            "events": [{"type": "tool_use", "part": {"type": "tool", "tool": "webfetch", "state": {
                "status": "completed", "input": {"url": "https://x.test"}, "output": marker}}}],
            "text": "ANSWER\n- ok",
        }), encoding="utf-8")
        self.env["HB_FAKE_SCRIPT"] = str(script)
        proc = self._call(oc_run.build_cmd(str(FAKE), "hb-lane", "p/m", "", "msg"))
        out = self.tmp / "out.jsonl"
        out.write_text(proc.stdout, encoding="utf-8")
        with mock.patch.dict(os.environ, {"HOME": self.env["HOME"]}):
            result = oc_run.parse_events(out)
        self.assertEqual(result["session"], "ses_fake0001")
        self.assertEqual(result["tools"][0]["output"], "big body")
        self.assertEqual(result["text"], "ANSWER\n- ok")

    def test_error_step_exits_one(self):
        script = self.tmp / "script.json"
        script.write_text(json.dumps({"error": {"type": "ProviderAuthError", "message": "bad key"}}), encoding="utf-8")
        self.env["HB_FAKE_SCRIPT"] = str(script)
        proc = self._call(oc_run.build_cmd(str(FAKE), "hb-lane", "p/m", "", "msg"))
        self.assertEqual(proc.returncode, 1)
        out = self.tmp / "out.jsonl"
        out.write_text(proc.stdout, encoding="utf-8")
        self.assertEqual(oc_run.parse_events(out)["errors"], ["ProviderAuthError: bad key"])


class RunOnceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.root = self.tmp / "repo"
        self.root.mkdir()
        self.lanes = self.root / ".superpowers" / "brainstorm" / "lanes"
        self.script = self.tmp / "script.json"
        self.log = self.tmp / "log.jsonl"
        self.env = dict(
            os.environ,
            HOME=str(self.tmp / "home"),
            HB_FAKE_SCRIPT=str(self.script),
            HB_FAKE_LOG=str(self.log),
        )
        self.env.pop("OPENCODE_CONFIG_CONTENT", None)

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def _run(self, step, stall_s=30, timeout_s=60, binary=None):
        self.script.write_text(json.dumps(step), encoding="utf-8")
        cmd = oc_run.build_cmd(binary or str(FAKE), "hb-lane", "zai-coding-plan/glm-5.3-flash", "low", "Q?")
        return oc_run.run_once(
            cmd, self.root, self.env, self.lanes / "L1.jsonl", self.lanes / "L1.err", stall_s, timeout_s,
        )

    def test_success(self):
        result = self._run({
            "events": [_tool_event("read", "completed", {"filePath": "a.py"}, output="x = 1\n")],
            "usage": {"input": 12, "output": 4},
            "text": "FINDINGS\n- a.py:1 x",
        })
        for key in ("session", "text", "usage", "errors", "throttled", "events", "tools",
                    "rc", "reason", "note", "pid", "duration"):
            self.assertIn(key, result)
        self.assertEqual(result["rc"], 0)
        self.assertEqual(result["reason"], "")
        self.assertEqual(result["note"], "")
        self.assertGreater(result["pid"], 0)
        self.assertGreaterEqual(result["duration"], 0.0)
        self.assertEqual(result["text"], "FINDINGS\n- a.py:1 x")
        self.assertEqual(result["usage"]["input"], 12)
        self.assertEqual(result["tools"][0]["tool"], "read")
        self.assertTrue((self.lanes / "L1.jsonl").exists())
        self.assertTrue((self.lanes / "L1.err").exists())

    def test_cwd_and_pwd_are_repo_root(self):
        self.env["PWD"] = "/somewhere/else"
        self._run({"text": "ok"})
        record = json.loads(self.log.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(record["cwd"], str(self.root))
        self.assertEqual(record["pwd"], str(self.root))
        self.assertEqual(record["argv"][:3], ["run", "--standalone", "--agent"])

    def test_crash_on_nonzero_exit(self):
        result = self._run({"text": "partial", "exit": 3, "stderr": "boom"})
        self.assertEqual(result["rc"], 3)
        self.assertEqual(result["reason"], "crash")
        self.assertEqual(result["note"], "exit 3: boom")

    def test_error_event_is_crash_with_note(self):
        result = self._run({"error": {"type": "ProviderAuthError", "message": "bad key"}})
        self.assertEqual(result["rc"], 1)
        self.assertEqual(result["reason"], "crash")
        self.assertEqual(result["note"], "ProviderAuthError: bad key")

    def test_throttle_on_failed_run(self):
        result = self._run({"error": {"type": "APIError", "message": "429 Too Many Requests"}})
        self.assertEqual(result["reason"], "throttle")
        self.assertTrue(result["throttled"])
        self.assertEqual(result["note"], "APIError: 429 Too Many Requests")

    def test_throttle_text_on_successful_run_is_not_a_failure(self):
        result = self._run({"text": "ANSWER\n- ok", "stderr": "retried after rate limit"})
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
