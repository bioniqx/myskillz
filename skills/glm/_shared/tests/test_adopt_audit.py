import http.server
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "requirements-code-audit-glm", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import audit  # noqa: E402

ENV_NAMES = ["ZAI_API_KEY", "Z_AI_API_KEY", "GLM_API_KEY", "ZHIPUAI_API_KEY",
             "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "ZAI_BASE_URL",
             "GLM_BASE_URL", "ANTHROPIC_BASE_URL", "HTTP_PROXY", "http_proxy",
             "HTTPS_PROXY", "https_proxy"]


def clean_env(**extra):
    env = dict((k, v) for k, v in os.environ.items() if k not in ENV_NAMES)
    env.update(extra)
    return env


class IsolatedHome(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.cwd = os.getcwd()
        os.chdir(self.home)  # "./opencode.json" resolves here

    def tearDown(self):
        os.chdir(self.cwd)
        shutil.rmtree(self.home, ignore_errors=True)

    def put(self, rel, obj):
        p = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as fh:
            json.dump(obj, fh)
        return p

    def env(self, **extra):
        return mock.patch.dict(os.environ, clean_env(HOME=self.home, **extra), clear=True)


class KeyDiscovery(IsolatedHome):
    def test_env_order_prefers_glm_over_anthropic_token(self):
        with self.env(GLM_API_KEY="glm-key-0123456789abcdef",
                      ANTHROPIC_AUTH_TOKEN="anthropic-token-0123456789"):
            self.assertEqual(audit.discover_key(),
                             ("glm-key-0123456789abcdef", "env:GLM_API_KEY"))

    def test_env_z_ai_name_is_read(self):
        with self.env(Z_AI_API_KEY="zai-underscore-0123456789"):
            self.assertEqual(audit.discover_key(),
                             ("zai-underscore-0123456789", "env:Z_AI_API_KEY"))

    def test_opencode_data_auth_beats_zcode(self):
        a = self.put(".local/share/opencode/auth.json",
                     {"zai-coding-plan": {"type": "api", "key": "opencode-key-0123456789"}})
        self.put(".zcode/settings.json", {"apiKey": "zcode-key-0123456789abcd"})
        with self.env():
            self.assertEqual(audit.discover_key(), ("opencode-key-0123456789", a))

    def test_claude_settings_local_is_read(self):
        p = self.put(".claude/settings.local.json",
                     {"env": {"ZAI_API_KEY": "local-key-0123456789abcd"}})
        with self.env():
            self.assertEqual(audit.discover_key(), ("local-key-0123456789abcd", p))

    def test_project_opencode_json_is_read(self):
        self.put("opencode.json", {"provider": {"zai-coding-plan": {
            "options": {"apiKey": "project-key-0123456789ab"}}}})
        with self.env():
            self.assertEqual(audit.discover_key()[0], "project-key-0123456789ab")

    def test_token_field_and_short_values_are_ignored(self):
        self.put(".claude/settings.json", {"token": "token-field-0123456789", "apiKey": "short"})
        with self.env():
            self.assertEqual(audit.discover_key(), (None, None))


class BaseAndRoute(unittest.TestCase):
    def test_default_base_is_coding_openai(self):
        self.assertEqual(audit.DEFAULT_BASE, "https://api.z.ai/api/coding/paas/v4")
        with mock.patch.dict(os.environ, clean_env(), clear=True):
            self.assertEqual(audit.discover_base(), (audit.DEFAULT_BASE, "default"))
        self.assertEqual(audit.route_of(audit.DEFAULT_BASE), "openai")

    def test_anthropic_base_url_is_never_read(self):
        env = clean_env(ANTHROPIC_BASE_URL="https://api.z.ai/api/anthropic")
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(audit.discover_base(), (audit.DEFAULT_BASE, "default"))

    def test_zai_base_beats_glm_base_and_trailing_slash_is_dropped(self):
        env = clean_env(ZAI_BASE_URL="https://a.example/api/anthropic/",
                        GLM_BASE_URL="https://b.example/v4")
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(audit.discover_base(),
                             ("https://a.example/api/anthropic", "env:ZAI_BASE_URL"))
        with mock.patch.dict(os.environ, clean_env(GLM_BASE_URL="https://b.example/v4"),
                             clear=True):
            self.assertEqual(audit.discover_base(), ("https://b.example/v4", "env:GLM_BASE_URL"))

    def test_route_is_anthropic_only_for_anthropic_bases(self):
        self.assertEqual(audit.route_of("https://api.z.ai/api/anthropic"), "anthropic")
        self.assertEqual(audit.route_of("https://proxy.example/llm"), "openai")
        self.assertEqual(audit.route_of(""), "openai")


class FakeZai(http.server.BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode("utf-8")
        FakeZai.seen.append((self.path, self.headers.get("Authorization"), body))
        out = json.dumps({
            "id": "x", "object": "chat.completion", "model": "glm-5.3",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "ok"}}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9},
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *args):
        pass


class ApiLane(unittest.TestCase):
    def setUp(self):
        FakeZai.seen = []
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeZai)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d/api/coding/paas/v4" % self.srv.server_address[1]

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()

    def test_client_is_the_shared_client(self):
        self.assertTrue(issubclass(audit.Client, audit.zai_client.Client))

    def test_call_uses_openai_route_with_native_effort(self):
        with mock.patch.dict(os.environ, clean_env(NO_PROXY="127.0.0.1"), clear=True):
            cl = audit.Client(self.base, "test-key-0123456789abcdef", audit.route_of(self.base))
            txt = cl.call(audit.FLASH, "high", "SYSTEM PREFIX", "the task", 64)
        self.assertEqual(txt, "ok")
        self.assertEqual(cl.calls, 1)
        path, auth, raw = FakeZai.seen[0]
        self.assertEqual(path, "/api/coding/paas/v4/chat/completions")
        self.assertEqual(auth, "Bearer test-key-0123456789abcdef")
        body = json.loads(raw)
        self.assertEqual(body["model"], "glm-5.3-flash")
        self.assertEqual(body["reasoning_effort"], "high")
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertEqual(body["messages"][0]["content"], "SYSTEM PREFIX")
        self.assertEqual(body["messages"][-1]["role"], "user")
        self.assertEqual(body["messages"][-1]["content"], "the task")
        self.assertNotIn("budget_tokens", raw)

    def test_doctor_ping_goes_through_zai_client(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        env = clean_env(HOME=home, NO_PROXY="127.0.0.1",
                        ZAI_API_KEY="test-key-0123456789abcdef", ZAI_BASE_URL=self.base)
        buf = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), redirect_stdout(buf):
            audit.main(["doctor", "--ping"])
        out = buf.getvalue()
        self.assertIn("route       openai -> %s/chat/completions" % self.base, out)
        self.assertRegex(out, r"ping glm-5\.3-flash\s+ok")
        self.assertRegex(out, r"ping glm-5\.3\s+ok")
        self.assertNotIn("request shape", out)


class Setup(unittest.TestCase):
    def run_setup(self, harness):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        buf = io.StringIO()
        with mock.patch.dict(os.environ, clean_env(HOME=home), clear=True), \
                redirect_stdout(buf):
            audit.main(["setup", "--harness", harness, "--dry-run"])
        return buf.getvalue()

    def test_opencode_env_names_only_the_zai_key(self):
        out = self.run_setup("opencode")
        self.assertIn("export ZAI_API_KEY=<your GLM Coding Plan key>", out)
        self.assertIn("https://api.z.ai/api/coding/paas/v4", out)
        self.assertNotIn("ANTHROPIC_BASE_URL", out)
        self.assertNotIn("ANTHROPIC_AUTH_TOKEN", out)
        self.assertIn("zai-coding-plan/glm-5.3-flash", out)

    def test_zcode_output_is_unchanged(self):
        out = self.run_setup("zcode")
        self.assertIn(audit.SETUP_ENV, out)
        self.assertIn("export ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic", out)
        self.assertIn("ZCode: invoke with  $requirements-code-audit <spec file>", out)
