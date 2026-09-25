import importlib.util
import http.server
import json
import os
import shutil
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "writing-plans-glm", "scripts", "plan_tool.py")


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_under_test", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()


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


class TestCallModelRetriesThrottle(unittest.TestCase):
    def test_retries_after_1302_then_succeeds(self):
        ThrottleThenOkHandler.calls = 0
        server = http.server.HTTPServer(("127.0.0.1", 0), ThrottleThenOkHandler)
        port = server.server_address[1]
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            cfg = {"key": "sk-test-0123456789abcdef",
                   "base": "http://127.0.0.1:%d" % port, "protocol": "openai", "thinking": True}
            budget = plan_tool.Budget(limit=8)
            text, err = plan_tool.call_model(cfg, ["system"], "hello", "light", budget, max_tokens=64, timeout=10)
            self.assertEqual(err, "")
            self.assertEqual(text, "ready")
            self.assertEqual(ThrottleThenOkHandler.calls, 2)
        finally:
            server.shutdown()
            server.server_close()


class TestCmdSetupSignature(unittest.TestCase):
    def test_cmd_setup_takes_one_namespace_arg(self):
        import inspect
        self.assertTrue(callable(plan_tool.cmd_setup))
        self.assertEqual(list(inspect.signature(plan_tool.cmd_setup).parameters), ["a"])


class AgentFileTests(unittest.TestCase):
    def test_opencode_agent_rendered_from_neutral_source(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "opencode", "agents"))
        with open(os.path.join(tmp, "opencode", "agents", "plan-task-writer.md"), "w") as fh:
            fh.write("---\ndescription: writes plan task bodies\nmodel: flash\neffort: high\n"
                     "access: write\nbash: true\nweb: false\nsteps: 16\n---\nBody.\n")
        old = plan_tool.SKILL_DIR
        plan_tool.SKILL_DIR = tmp
        self.addCleanup(setattr, plan_tool, "SKILL_DIR", old)
        text = plan_tool.agent_file("opencode")
        self.assertIn("mode: subagent", text)
        self.assertIn("zai-coding-plan/glm-5.3-flash", text)
        self.assertIn("Body.", text)
        self.assertNotIn("top_p", text)


if __name__ == "__main__":
    unittest.main()
