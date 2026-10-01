"""Tests for oc_lane (opencode runner and event parser) and the fake opencode CLI."""
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(TESTS_DIR))

import oc_lane  # noqa: E402
import hybrid_shared  # noqa: E402

FAKE = TESTS_DIR / "fake_opencode.py"


class BuildCmdTest(unittest.TestCase):
    def test_fresh_run(self):
        cmd = oc_lane.build_cmd("opencode", "zai-coding-plan/glm-5.3", "high", "do the slice")
        self.assertEqual(
            cmd,
            [
                "opencode", "run", "--standalone", "--agent", "hybrid-team-programmer",
                "--model", "zai-coding-plan/glm-5.3#high",
                "--format", "json", "--auto", "do the slice",
            ],
        )

    def test_continuation_adds_session_before_message(self):
        cmd = oc_lane.build_cmd("/bin/oc", "m/x", "low", "fix the gate", session="ses_1")
        self.assertEqual(cmd[0], "/bin/oc")
        self.assertEqual(cmd[-3:], ["-s", "ses_1", "fix the gate"])
        self.assertNotIn("--variant", cmd)
        self.assertNotIn("--dir", cmd)

    def test_attached_brief_uses_file_flag_and_short_message(self):
        cmd = oc_lane.build_cmd("oc", "m/x", "low", oc_lane.ATTACH_MESSAGE, session="ses_1", attach="/tmp/b.md")
        self.assertEqual(cmd[cmd.index("-f") + 1], "/tmp/b.md")
        self.assertEqual(cmd[-1], oc_lane.ATTACH_MESSAGE)
        self.assertNotIn("brief text", " ".join(cmd))

    def test_empty_variant_omits_hash(self):
        cmd = oc_lane.build_cmd("oc", "m/x", "", "msg")
        self.assertEqual(cmd[cmd.index("--model") + 1], "m/x")
        self.assertNotIn("-s", cmd)

    def test_throttle_re(self):
        for text in ["HTTP 429", "Too Many Requests", "Rate limit exceeded", "rate-limit hit", "ratelimit"]:
            self.assertTrue(oc_lane.THROTTLE_RE.search(text), text)
        for text in ["exit 1429x", "all good"]:
            self.assertIsNone(oc_lane.THROTTLE_RE.search(text), text)


def _write_lines(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ParseEventsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_text_session_and_usage(self):
        path = self.dir / "a.jsonl"
        _write_lines(path, [
            json.dumps({"type": "step_start", "sessionID": "ses_A", "part": {}}),
            json.dumps({"type": "text", "sessionID": "ses_A", "part": {"type": "text", "text": "first"}}),
            json.dumps({"type": "step_finish", "sessionID": "ses_A", "part": {
                "tokens": {"input": 100, "output": 20, "reasoning": 5, "cache": {"read": 7, "write": 3}},
                "cost": 0.25}}),
            "not json at all",
            json.dumps({"type": "step_finish", "sessionID": "ses_A", "part": {
                "tokens": {"input": 1, "output": 2, "reasoning": 0, "cache": {"read": 0, "write": 1}},
                "cost": 0.5}}),
            json.dumps({"type": "text", "sessionID": "ses_A", "part": {"type": "text", "text": "final answer"}}),
        ])
        res = oc_lane.parse_events(path)
        self.assertEqual(res["session"], "ses_A")
        self.assertEqual(res["text"], "final answer")
        self.assertEqual(res["events"], 5)
        usage = res["usage"]
        self.assertEqual(
            (usage["input"], usage["output"], usage["reasoning"], usage["cache_read"], usage["cache_write"]),
            (101, 22, 5, 7, 4),
        )
        self.assertAlmostEqual(usage["cost"], 0.75)
        self.assertEqual(res["errors"], [])
        self.assertFalse(res["throttled"])

    def test_missing_file_and_toolless_run(self):
        res = oc_lane.parse_events(self.dir / "missing.jsonl")
        self.assertEqual(res["session"], "")
        self.assertEqual(res["text"], "")
        self.assertEqual(res["events"], 0)
        self.assertEqual(res["usage"]["input"], 0)
        self.assertEqual(res["usage"]["cost"], 0.0)
        path = self.dir / "b.jsonl"
        _write_lines(path, [json.dumps({"type": "text", "sessionID": "ses_B", "part": {"text": "hi"}})])
        res = oc_lane.parse_events(path)
        self.assertEqual(res["text"], "hi")
        self.assertEqual(res["usage"], {
            "input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0})

    def test_error_event(self):
        path = self.dir / "c.jsonl"
        _write_lines(path, [json.dumps({
            "type": "error", "sessionID": "ses_C",
            "error": {"type": "ProviderModelNotFoundError", "message": "Variant unavailable for m/x"}})])
        res = oc_lane.parse_events(path)
        self.assertEqual(res["session"], "ses_C")
        self.assertEqual(res["errors"], ["ProviderModelNotFoundError: Variant unavailable for m/x"])
        self.assertFalse(res["throttled"])

    def test_throttle_in_error_and_raw_line(self):
        path = self.dir / "d.jsonl"
        _write_lines(path, [json.dumps({
            "type": "error", "sessionID": "ses_D",
            "error": {"type": "APIError", "message": "Too Many Requests"}})])
        self.assertTrue(oc_lane.parse_events(path)["throttled"])
        path = self.dir / "e.jsonl"
        _write_lines(path, ["HTTP 429 from provider"])
        res = oc_lane.parse_events(path)
        self.assertTrue(res["throttled"])
        self.assertEqual(res["events"], 0)

    def test_finished_flag_needs_stop_reason(self):
        path = self.dir / "f.jsonl"
        _write_lines(path, [
            json.dumps({"type": "step_finish", "sessionID": "ses_F", "part": {"reason": "tool-calls"}}),
        ])
        self.assertFalse(oc_lane.parse_events(path)["finished"])
        _write_lines(path, [
            json.dumps({"type": "step_finish", "sessionID": "ses_F", "part": {"reason": "tool-calls"}}),
            json.dumps({"type": "step_finish", "sessionID": "ses_F", "part": {"reason": "stop"}}),
        ])
        self.assertTrue(oc_lane.parse_events(path)["finished"])
        self.assertFalse(oc_lane.parse_events(self.dir / "missing.jsonl")["finished"])


import fake_opencode  # noqa: E402


def _ensure_exec():
    mode = FAKE.stat().st_mode
    FAKE.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _fake_env(home, script=None, log=None):
    env = dict(os.environ)
    env["HOME"] = str(home)
    env.pop(fake_opencode.FAKE_SCRIPT_ENV, None)
    env.pop(fake_opencode.FAKE_LOG_ENV, None)
    if script is not None:
        env[fake_opencode.FAKE_SCRIPT_ENV] = str(script)
    if log is not None:
        env[fake_opencode.FAKE_LOG_ENV] = str(log)
    return env


def _read_log(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class FakeCliTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_exec()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.work = self.dir / "wt"
        self.work.mkdir()
        self.log = self.dir / "fake.log"
        self.script = None

    def _set_script(self, obj):
        self.script = self.dir / "script.json"
        self.script.write_text(json.dumps(obj), encoding="utf-8")

    def _run(self, args):
        return subprocess.run(
            [str(FAKE)] + args,
            cwd=str(self.work),
            env=_fake_env(self.dir, self.script, self.log),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=30,
        )

    def _events(self, proc):
        return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

    def test_default_run_emits_text_and_logs(self):
        proc = self._run(["run", "--format", "json", "hello"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        events = self._events(proc)
        self.assertEqual(events[-1]["type"], "text")
        self.assertEqual(events[-1]["part"]["text"], "done")
        self.assertEqual(events[-1]["sessionID"], fake_opencode.DEFAULT_SESSION)
        records = _read_log(self.log)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["argv"], ["run", "--format", "json", "hello"])
        self.assertEqual(Path(records[0]["cwd"]).resolve(), self.work.resolve())

    def test_scripted_usage_error_and_session(self):
        self._set_script({
            "usage": {"input": 10, "output": 4, "reasoning": 1, "cache_read": 2, "cache_write": 0, "cost": 0.01},
            "error": {"type": "APIError", "message": "429 Too Many Requests"},
        })
        proc = self._run(["run", "-s", "ses_keep", "msg"])
        self.assertEqual(proc.returncode, 1)
        events = self._events(proc)
        self.assertEqual([e["type"] for e in events], ["step_finish", "error"])
        self.assertTrue(all(e["sessionID"] == "ses_keep" for e in events))
        self.assertEqual(events[0]["part"]["tokens"]["cache"]["read"], 2)
        self.assertEqual(events[1]["error"]["message"], "429 Too Many Requests")

    def test_list_script_advances_per_call(self):
        self._set_script([{"text": "one"}, {"text": "two"}])
        texts = []
        for _ in range(3):
            proc = self._run(["run", "m"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            texts.append(self._events(proc)[-1]["part"]["text"])
        self.assertEqual(texts, ["one", "two", "two"])
        self.assertEqual(len(_read_log(self.log)), 3)

    def test_write_and_commit_in_cwd(self):
        subprocess.run(["git", "init", "-q"], cwd=str(self.work), check=True)
        self._set_script({"write": {"src/a.txt": "hi\n"}, "commit": "fake: add a", "text": "ok"})
        proc = self._run(["run", "m"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.work / "src" / "a.txt").read_text(encoding="utf-8"), "hi\n")
        out = subprocess.run(
            ["git", "log", "--oneline"], cwd=str(self.work),
            stdout=subprocess.PIPE, universal_newlines=True, check=True,
        ).stdout
        self.assertEqual(len(out.splitlines()), 1)
        self.assertIn("fake: add a", out)

    def test_version(self):
        proc = self._run(["--version"])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "2.0.18")

    def test_scenario_error_kinds(self):
        cases = [
            ("auth", "Unauthorized"),
            ("model_not_found", "model not found"),
            ("throttle", "Too Many Requests"),
        ]
        for name, needle in cases:
            self._set_script({"scenario": name})
            proc = self._run(["run", "m"])
            self.assertEqual(proc.returncode, 1, name)
            error = self._events(proc)[-1]
            self.assertEqual(error["type"], "error", name)
            self.assertIn(needle, error["error"]["message"], name)

    def test_scenario_recovered_exits_one_after_stop(self):
        self._set_script({"scenario": "recovered"})
        proc = self._run(["run", "m"])
        self.assertEqual(proc.returncode, 1)
        events = self._events(proc)
        self.assertEqual([e["type"] for e in events], ["step_finish", "text"])
        self.assertEqual(events[0]["part"]["reason"], "stop")
        self.assertEqual(events[1]["part"]["text"], "done")

    def test_scenario_empty_stops_without_text(self):
        self._set_script({"scenario": "empty"})
        proc = self._run(["run", "m"])
        self.assertEqual(proc.returncode, 0)
        events = self._events(proc)
        self.assertEqual([e["type"] for e in events], ["step_finish"])
        self.assertEqual(events[0]["part"]["reason"], "stop")

    def test_models_default_and_empty_listing(self):
        proc = self._run(["models"])
        self.assertEqual(proc.stdout.split(), ["zai-coding-plan/glm-5.3", "zai-coding-plan/glm-5.3-flash"])
        self._set_script({"models": []})
        proc = self._run(["models"])
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")


class RunOnceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_exec()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.work = self.dir / "wt"
        self.work.mkdir()
        self.log = self.dir / "fake.log"
        self.out = self.dir / "lanes" / "L1.jsonl"
        self.err = self.dir / "lanes" / "L1.err"

    def _go(self, step, stall_s=10, timeout_s=30, session="", binary=None):
        script = self.dir / "script.json"
        script.write_text(json.dumps(step), encoding="utf-8")
        env = _fake_env(self.dir, script, self.log)
        cmd = oc_lane.build_cmd(
            binary or str(FAKE), "zai-coding-plan/glm-5.3", "high", "brief text", session=session)
        return oc_lane.run_once(cmd, self.work, env, self.out, self.err, stall_s, timeout_s)

    def test_success(self):
        res = self._go({
            "usage": {"input": 10, "output": 3, "reasoning": 1, "cache_read": 0, "cache_write": 0, "cost": 0.02},
            "text": "all green",
        })
        self.assertEqual(res["rc"], 0)
        self.assertEqual(res["reason"], "")
        self.assertEqual(res["note"], "")
        self.assertEqual(res["text"], "all green")
        self.assertEqual(res["session"], fake_opencode.DEFAULT_SESSION)
        self.assertEqual(res["usage"]["input"], 10)
        self.assertGreater(res["pid"], 0)
        self.assertGreaterEqual(res["duration"], 0)
        self.assertTrue(self.out.is_file())
        self.assertTrue(self.err.is_file())
        rec = _read_log(self.log)[0]
        self.assertEqual(rec["pwd"], str(self.work))
        self.assertEqual(Path(rec["cwd"]).resolve(), self.work.resolve())
        self.assertIn("zai-coding-plan/glm-5.3#high", rec["argv"])
        self.assertEqual(rec["argv"][-1], "brief text")

    def test_continuation_passes_session(self):
        res = self._go({"text": "fixed"}, session="ses_prev")
        self.assertEqual(res["reason"], "")
        self.assertEqual(res["session"], "ses_prev")
        argv = _read_log(self.log)[0]["argv"]
        self.assertEqual(argv[argv.index("-s") + 1], "ses_prev")

    def test_error_event_is_crash(self):
        res = self._go({"error": {"type": "ProviderModelNotFoundError", "message": "Variant unavailable for x"}})
        self.assertEqual(res["rc"], 1)
        self.assertEqual(res["reason"], "crash")
        self.assertIn("Variant unavailable", res["note"])

    def test_nonzero_exit_without_events_is_crash(self):
        res = self._go({"exit": 3, "stderr": "boom\n"})
        self.assertEqual(res["rc"], 3)
        self.assertEqual(res["reason"], "crash")
        self.assertIn("boom", res["note"])

    def test_throttle_from_error_event(self):
        res = self._go({"error": {"type": "APIError", "message": "429 Too Many Requests"}})
        self.assertEqual(res["reason"], "throttle")
        self.assertTrue(res["throttled"])
        self.assertIn("Too Many Requests", res["note"])

    def test_throttle_from_stderr(self):
        res = self._go({"stderr": "rate limit reached\n", "exit": 1})
        self.assertEqual(res["reason"], "throttle")

    def test_stall_kills_group(self):
        started = time.monotonic()
        res = self._go({"sleep": 30}, stall_s=1, timeout_s=20)
        self.assertEqual(res["reason"], "stall")
        self.assertNotEqual(res["rc"], 0)
        self.assertLess(time.monotonic() - started, 10)

    def test_timeout_kills_group(self):
        started = time.monotonic()
        res = self._go({"ticks": 200, "tick_s": 0.2}, stall_s=5, timeout_s=1)
        self.assertEqual(res["reason"], "timeout")
        self.assertNotEqual(res["rc"], 0)
        self.assertGreater(res["events"], 0)
        self.assertLess(time.monotonic() - started, 10)

    def test_spawn_error(self):
        res = self._go({"text": "never"}, binary=str(self.dir / "no-such-opencode"))
        self.assertEqual(res["reason"], "spawn")
        self.assertIsNone(res["rc"])
        self.assertEqual(res["pid"], 0)
        self.assertIn("spawn", res["note"])
        self.assertEqual(res["text"], "")

    def test_success_with_throttle_looking_text_is_not_throttled(self):
        res = self._go({"raw": ["see HTTP 429 in the docs"], "text": "all good"})
        self.assertEqual(res["rc"], 0)
        self.assertEqual(res["reason"], "")
        self.assertEqual(res["text"], "all good")

    def test_failed_run_with_throttle_signal_stays_throttle(self):
        res = self._go({"raw": ["Too Many Requests"], "exit": 1})
        self.assertNotEqual(res["rc"], 0)
        self.assertEqual(res["reason"], "throttle")

    def test_nul_byte_in_message_is_spawn_error(self):
        script = self.dir / "script.json"
        script.write_text(json.dumps({"text": "never"}), encoding="utf-8")
        env = _fake_env(self.dir, script, self.log)
        cmd = oc_lane.build_cmd(str(FAKE), "zai-coding-plan/glm-5.3", "high", "bad\x00msg")
        res = oc_lane.run_once(cmd, self.work, env, self.out, self.err, 10, 30)
        self.assertEqual(res["reason"], "spawn")
        self.assertIsNone(res["rc"])
        self.assertEqual(res["pid"], 0)
        self.assertIn("spawn", res["note"])

    def test_clean_run_has_no_kind(self):
        res = self._go({"finish": "stop", "text": "all green"})
        self.assertEqual(res["rc"], 0)
        self.assertEqual(res["reason"], "")
        self.assertEqual(res["kind"], "")
        self.assertEqual(res["detail"], "")
        self.assertTrue(res["finished"])

    def test_exit_zero_without_text_is_empty(self):
        res = self._go({"scenario": "empty"})
        self.assertEqual(res["rc"], 0)
        self.assertEqual(res["reason"], "")
        self.assertEqual(res["note"], "")
        self.assertEqual(res["kind"], "empty")
        self.assertEqual(res["text"], "")
        self.assertIn("no text", res["detail"])

    def test_exit_one_after_terminal_stop_is_recovered(self):
        res = self._go({"scenario": "recovered"})
        self.assertEqual(res["rc"], 1)
        self.assertTrue(res["finished"])
        self.assertEqual(res["reason"], "")
        self.assertEqual(res["note"], "")
        self.assertEqual(res["kind"], "recovered")
        self.assertEqual(res["text"], "done")
        self.assertTrue(res["detail"])

    def test_exit_one_without_terminal_stop_is_crash(self):
        res = self._go({"text": "partial", "exit": 1, "stderr": "segfault\n"})
        self.assertFalse(res["finished"])
        self.assertEqual(res["reason"], "crash")
        self.assertEqual(res["kind"], "crash")
        self.assertIn("segfault", res["detail"])

    def test_auth_error_kind(self):
        res = self._go({"scenario": "auth"})
        self.assertEqual(res["rc"], 1)
        self.assertEqual(res["reason"], "crash")
        self.assertEqual(res["kind"], "auth")
        self.assertIn("Unauthorized", res["detail"])

    def test_model_not_found_kind(self):
        res = self._go({"scenario": "model_not_found"})
        self.assertEqual(res["reason"], "crash")
        self.assertEqual(res["kind"], "model")
        self.assertIn("model not found", res["detail"])

    def test_throttle_kind(self):
        res = self._go({"scenario": "throttle"})
        self.assertEqual(res["reason"], "throttle")
        self.assertEqual(res["kind"], "throttle")
        self.assertTrue(res["throttled"])

    def test_stall_timeout_and_spawn_kinds(self):
        self.assertEqual(self._go({"sleep": 30}, stall_s=1, timeout_s=20)["kind"], "stall")
        self.assertEqual(self._go({"ticks": 200, "tick_s": 0.2}, stall_s=5, timeout_s=1)["kind"], "timeout")
        res = self._go({"text": "never"}, binary=str(self.dir / "no-such-opencode"))
        self.assertEqual(res["kind"], "spawn")
        self.assertIn("spawn", res["detail"])


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
        return res["kind"]

    def _parse(self, events):
        path = self.dir / "s.jsonl"
        path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        return oc_lane.parse_events(path)

    def _run(self, events, rc):
        stream = self.dir / "stream.jsonl"
        stream.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        return oc_lane.run_once([sys.executable, "-c", _PRINTER, str(stream), str(rc)], self.dir, dict(os.environ),
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
        self.assertIsNone(oc_lane.THROTTLE_RE.search('File "x.py", line 429, in main'))
        self.assertTrue(oc_lane.THROTTLE_RE.search("provider.rate-limit (HTTP 429)"))


if __name__ == "__main__":
    unittest.main()
