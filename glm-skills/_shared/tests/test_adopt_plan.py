import argparse
import contextlib
import importlib.util
import http.server
import io
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "glm-writing-plans", "scripts", "plan_tool.py")


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_under_test", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()
AGENTS_DIR = os.path.join(HERE, "..", "..", "glm-writing-plans", "agents")
NO_KEY = (None, "https://api.z.ai/api/coding/paas/v4", "openai", "-")


def _frontmatter(name):
    with open(os.path.join(AGENTS_DIR, name + ".md"), encoding="utf-8") as fh:
        text = fh.read()
    head = text.split("---\n")[1]
    fields = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, text


def _plan_text(n, deep=()):
    rows = ["# Demo Plan", "", "**Goal:** demo.", "", "## Global Constraints", "", "- none", "",
            "## Contracts", ""]
    for i in range(1, n + 1):
        tid = "T%02d" % i
        rows += ["#### %s: part %d" % (tid, i), "- Depends: none", "- Files: `src/p%02d.py`" % i,
                 "- Produces: `def f%02d() -> int`" % i, "- Spec: L1-1",
                 "- Tier: %s" % ("deep" if tid in deep else "std"), ""]
    return "\n".join(rows) + "\n"


class ThrottleThenOkHandler(http.server.BaseHTTPRequestHandler):
    calls = 0

    def do_POST(self):
        ThrottleThenOkHandler.calls += 1
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if ThrottleThenOkHandler.calls == 1:
            payload = json.dumps({"error": {"code": "1302"}}).encode()
            self.send_response(429)
            self.send_header("Content-Type", "application/json")
            self.send_header("Retry-After", "0")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        payload = json.dumps({"choices": [{"message": {"content": "ready"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        pass


class TestDefaultBaseAndProtocol(unittest.TestCase):
    def test_default_base_is_coding_endpoint(self):
        self.assertEqual(plan_tool.DEFAULT_BASE, "https://api.z.ai/api/coding/paas/v4")

    def test_protocol_for_defaults_to_openai(self):
        self.assertEqual(plan_tool.protocol_for("https://api.z.ai/api/coding/paas/v4"), "openai")
        self.assertEqual(plan_tool.protocol_for(""), "openai")

    def test_protocol_for_anthropic_is_opt_in(self):
        self.assertEqual(plan_tool.protocol_for("https://api.z.ai/api/anthropic"), "anthropic")


class TestFindCredentials(unittest.TestCase):
    def setUp(self):
        self.saved = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.saved)

    def test_reads_zai_api_key_and_ignores_anthropic_base_url(self):
        for k in list(os.environ):
            if k in plan_tool.KEY_ENV or k in ("ZAI_BASE_URL", "GLM_BASE_URL", "PLAN_BASE_URL", "ANTHROPIC_BASE_URL"):
                del os.environ[k]
        os.environ["ZAI_API_KEY"] = "sk-test-0123456789abcdef"
        os.environ["ANTHROPIC_BASE_URL"] = "https://example.invalid/should-be-ignored"
        key, base, proto, src = plan_tool.find_credentials()
        self.assertEqual(key, "sk-test-0123456789abcdef")
        self.assertEqual(base, plan_tool.DEFAULT_BASE)
        self.assertEqual(proto, "openai")
        self.assertEqual(src, "env:ZAI_API_KEY")

    def test_no_longer_defines_own_key_walk(self):
        self.assertFalse(hasattr(plan_tool, "_walk_for_key"))
        self.assertFalse(hasattr(plan_tool, "KEY_FILES"))


class TestCallModelRetriesThrottle(unittest.TestCase):
    def test_retries_after_1302_then_succeeds(self):
        ThrottleThenOkHandler.calls = 0
        server = http.server.HTTPServer(("127.0.0.1", 0), ThrottleThenOkHandler)
        port = server.server_address[1]
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            cfg = {"key": "sk-test-0123456789abcdef",
                   "base": "http://127.0.0.1:%d" % port, "protocol": "openai"}
            budget = plan_tool.Budget(limit=8)
            text, err = plan_tool.call_model(cfg, ["system"], "hello", "light", budget, max_tokens=64, timeout=10)
            self.assertEqual(err, "")
            self.assertEqual(text, "ready")
            self.assertEqual(ThrottleThenOkHandler.calls, 2)
        finally:
            server.shutdown()
            server.server_close()


class EmptyContentHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        payload = json.dumps({"choices": [{"message": {"content": ""}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        pass


class TestCallModelEmptyResponse(unittest.TestCase):
    def test_blank_completion_is_an_error_not_a_silent_success(self):
        server = http.server.HTTPServer(("127.0.0.1", 0), EmptyContentHandler)
        port = server.server_address[1]
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            cfg = {"key": "sk-test-0123456789abcdef",
                   "base": "http://127.0.0.1:%d" % port, "protocol": "openai"}
            budget = plan_tool.Budget(limit=8)
            text, err = plan_tool.call_model(cfg, ["system"], "hello", "light", budget, max_tokens=64, timeout=10)
            self.assertEqual(text, "")
            self.assertNotEqual(err, "")
        finally:
            server.shutdown()
            server.server_close()


class TestCmdSetupSignature(unittest.TestCase):
    def test_cmd_setup_takes_one_namespace_arg(self):
        import inspect
        self.assertTrue(callable(plan_tool.cmd_setup))
        self.assertEqual(list(inspect.signature(plan_tool.cmd_setup).parameters), ["a"])


class WriterGroupingTests(unittest.TestCase):
    def test_group_count_is_one_task_per_writer_up_to_cap(self):
        """ceil(n/4) groups at the floor, one task per writer up to the cap above it."""
        for n, want in ((0, 0), (1, 1), (4, 4), (5, 5), (8, 8), (10, 8), (30, 8)):
            self.assertEqual(plan_tool.writer_group_count(n, 8), want, n)

    def test_cap_groups_splits_oversized_groups(self):
        self.assertEqual(plan_tool.cap_groups([[1, 2, 3, 4, 5, 6], [7]]), [[1, 2, 3, 4], [5, 6], [7]])

    def test_lane_width_default_and_env(self):
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": ""}):
            self.assertEqual(plan_tool.lane_width(), 8)
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "3"}):
            self.assertEqual(plan_tool.lane_width(), 3)
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "x"}):
            self.assertEqual(plan_tool.lane_width(), 8)
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "0"}):
            self.assertEqual(plan_tool.lane_width(), 1)
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "64"}):
            self.assertEqual(plan_tool.lane_width(), 8)

    def test_model_call_concurrency_never_exceeds_eight(self):
        self.assertEqual(plan_tool.MAX_WORKERS, 8)
        with mock.patch.dict(os.environ, {"PLAN_MAX_WORKERS": "64"}):
            self.assertEqual(plan_tool.workers_cap(), 8)
        self.assertEqual(plan_tool.workers_cap(64), 8)
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "64"}):
            self.assertEqual(plan_tool.agent_cap()[0], 8)
        live, peak, lock = [0], [0], threading.Lock()

        def fn(_):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.01)
            with lock:
                live[0] -= 1
        plan_tool.pmap(fn, range(40), 64)
        self.assertLessEqual(peak[0], 8)

class ZcodeAgentAndDispatchTests(unittest.TestCase):
    """The zcode agent block and the dispatch headers inside plan_tool.py."""

    @staticmethod
    def _skill_root():
        import os
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    @classmethod
    def plan_tool_text(cls):
        import os
        with open(os.path.join(cls._skill_root(), "glm-writing-plans", "scripts", "plan_tool.py"),
                  encoding="utf-8") as fh:
            return fh.read()

    def test_zcode_agent_block_carries_maxturns_16(self):
        lines = self.plan_tool_text().split("\n")
        found = False
        for i, line in enumerate(lines):
            if "name: glm-plan-task-writer" in line:
                window = lines[i + 1:i + 9]
                if any("thoughtLevel:" in w for w in window):
                    found = True
                    self.assertTrue(any("maxTurns: 16" in w for w in window),
                                    "zcode agent block lacks maxTurns: 16")
        self.assertTrue(found, "no zcode agent block for glm-plan-task-writer")

    def test_dispatch_headers_carry_no_jargon(self):
        text = self.plan_tool_text()
        self.assertNotIn("sonnet", text, "plan_tool.py still names the sonnet alias")
        self.assertNotIn("subagent_type=", text, "dispatch headers still carry subagent_type= jargon")

    def test_r9_scopes_base_url_to_claude_compatible_harnesses(self):
        import os
        with open(os.path.join(self._skill_root(), "glm-writing-plans", "SKILL.md"),
                  encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("On a Claude-compatible harness, also export the z.ai Anthropic route",
                      text, "R9 does not scope ANTHROPIC_BASE_URL to Claude-compatible harnesses")
        self.assertEqual(text.count("export ANTHROPIC_BASE_URL="), 1,
                         "R9 must export ANTHROPIC_BASE_URL exactly once")


if __name__ == "__main__":
    unittest.main()
