import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import zai_client  # noqa: E402


class TestBase(unittest.TestCase):
    def test_default_base(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(zai_client.find_base(), "https://api.z.ai/api/coding/paas/v4")
        self.assertEqual(zai_client.DEFAULT_BASE, "https://api.z.ai/api/coding/paas/v4")

    def test_base_order(self):
        env = {"ZAI_BASE_URL": "https://a.example/v4/",
               "GLM_BASE_URL": "https://b.example/v4",
               "ANTHROPIC_BASE_URL": "https://c.example/api/anthropic"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(zai_client.find_base("https://x.example/v4"), "https://x.example/v4")
            self.assertEqual(zai_client.find_base(), "https://a.example/v4")
            del os.environ["ZAI_BASE_URL"]
            self.assertEqual(zai_client.find_base(), "https://b.example/v4")
            del os.environ["GLM_BASE_URL"]
            self.assertEqual(zai_client.find_base(), zai_client.DEFAULT_BASE)

    def test_route(self):
        self.assertEqual(zai_client.route_of(zai_client.DEFAULT_BASE), "openai")
        self.assertEqual(zai_client.route_of("https://api.z.ai/api/anthropic"), "anthropic")
        self.assertEqual(zai_client.route_of("https://proxy.example/v4"), "openai")
        self.assertEqual(zai_client.route_of(""), "openai")

    def test_endpoint(self):
        base = zai_client.DEFAULT_BASE
        self.assertEqual(zai_client.endpoint_of(base, "openai"), base + "/chat/completions")
        self.assertEqual(zai_client.endpoint_of(base + "/chat/completions", "openai"),
                         base + "/chat/completions")
        self.assertEqual(zai_client.endpoint_of("https://api.z.ai/api/anthropic/", "anthropic"),
                         "https://api.z.ai/api/anthropic/v1/messages")


class TestFindKey(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.cwd = tempfile.mkdtemp()
        self.old = os.getcwd()
        os.chdir(self.cwd)
        self.env = mock.patch.dict(os.environ, {"HOME": self.home}, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        os.chdir(self.old)
        shutil.rmtree(self.home)
        shutil.rmtree(self.cwd)

    def put(self, rel, obj):
        p = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f)
        return p

    def test_env_order(self):
        os.environ["ANTHROPIC_API_KEY"] = "a" * 20
        os.environ["GLM_API_KEY"] = "g" * 20
        self.assertEqual(zai_client.find_key(), ("g" * 20, "env:GLM_API_KEY"))
        os.environ["Z_AI_API_KEY"] = "z" * 20
        self.assertEqual(zai_client.find_key(), ("z" * 20, "env:Z_AI_API_KEY"))

    def test_extra_env_first(self):
        os.environ["ZAI_API_KEY"] = "z" * 20
        os.environ["MY_KEY"] = "m" * 20
        self.assertEqual(zai_client.find_key(("MY_KEY",)), ("m" * 20, "env:MY_KEY"))
        self.assertEqual(zai_client.find_key(), ("z" * 20, "env:ZAI_API_KEY"))

    def test_file_order(self):
        self.put(".claude/settings.json", {"env": {"ANTHROPIC_AUTH_TOKEN": "c" * 20}})
        self.put(".zcode/auth.json", {"key": "y" * 20})
        auth = self.put(".local/share/opencode/auth.json",
                        {"zai-coding-plan": {"type": "api", "key": "o" * 20}})
        self.assertEqual(zai_client.find_key(), ("o" * 20, auth))

    def test_field_filter(self):
        self.put(".claude/settings.json",
                 {"env": {"token": "t" * 30,
                          "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic"},
                  "apiKey": "short"})
        self.put(".zcode/auth.json", {"key": "has spaces in this key value"})
        self.assertEqual(zai_client.find_key(), (None, None))

    def test_cwd_opencode_json(self):
        self.put(".claude/settings.json", {"env": {"ANTHROPIC_AUTH_TOKEN": "c" * 20}})
        with open("opencode.json", "w", encoding="utf-8") as f:
            json.dump({"provider": {"zai-coding-plan": {"options": {"apiKey": "p" * 20}}}}, f)
        self.assertEqual(zai_client.find_key(),
                         ("p" * 20, os.path.join(os.getcwd(), "opencode.json")))


class TestGate(unittest.TestCase):
    def test_halves_on_throttle(self):
        g = zai_client.Gate(8)
        self.assertEqual([g.throttled() for _ in range(4)], [4, 2, 1, 1])

    def test_grows_after_clean_window(self):
        g = zai_client.Gate(8)
        g.throttled()
        self.assertEqual([g.ok() for _ in range(3)], [4, 4, 4])
        self.assertEqual(g.ok(), 5)
        for _ in range(100):
            g.ok()
        self.assertEqual(g.width, 8)

    def run_six(self, g):
        live = [0]
        peak = [0]
        lock = threading.Lock()

        def work():
            with g:
                with lock:
                    live[0] += 1
                    peak[0] = max(peak[0], live[0])
                time.sleep(0.05)
                with lock:
                    live[0] -= 1

        ts = [threading.Thread(target=work) for _ in range(6)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        return peak[0]

    def test_caps_live_threads(self):
        g = zai_client.Gate(2)
        self.assertEqual(self.run_six(g), 2)
        g.throttled()
        self.assertEqual(self.run_six(g), 1)


from fakeapi import chat, fail, messages, start_fake  # noqa: E402

KEY = "k" * 24


class _FakeCase(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.fake = None

    def tearDown(self):
        if self.fake is not None:
            self.fake.stop()
        self.env.stop()

    def serve(self, *script):
        self.fake = start_fake(list(script))
        return self.fake


class TestClient(_FakeCase):
    def test_openai_call(self):
        fake = self.serve(chat("hello"))
        c = zai_client.Client(KEY, base=fake.base)
        self.assertEqual(c.route, "openai")
        self.assertEqual(c.call("glm-5.3-flash", "high", "SYS", "USER", 100), "hello")
        req = fake.requests[0]
        self.assertEqual(req["path"], "/api/coding/paas/v4/chat/completions")
        self.assertEqual(req["headers"]["authorization"], "Bearer " + KEY)
        self.assertEqual(req["headers"]["user-agent"], "glm-skill")
        body = req["body"]
        self.assertEqual(body["model"], "glm-5.3-flash")
        self.assertEqual(body["reasoning_effort"], "high")
        self.assertEqual(body["max_tokens"], 100)
        self.assertEqual(body["messages"], [{"role": "system", "content": "SYS"},
                                            {"role": "user", "content": "USER"}])
        self.assertNotIn("temperature", body)
        self.assertNotIn("thinking", body)
        st = c.stats()
        self.assertEqual((st["calls"], st["ok"], st["in_tok"], st["out_tok"]), (1, 1, 10, 5))

    def test_options(self):
        fake = self.serve(chat("x"))
        c = zai_client.Client(KEY, base=fake.base, user_agent="plan_tool/7")
        c.call("glm-5.3", "max", "SYS", "USER", 50, temperature=0.2)
        req = fake.requests[0]
        self.assertEqual(req["body"]["temperature"], 0.2)
        self.assertEqual(req["body"]["reasoning_effort"], "max")
        self.assertEqual(req["headers"]["user-agent"], "plan_tool/7")

    def test_anthropic_route(self):
        fake = self.serve(messages("hi"))
        c = zai_client.Client(KEY, base=fake.root + "/api/anthropic")
        self.assertEqual(c.route, "anthropic")
        self.assertEqual(c.call("glm-5.3", "low", "SYS", "USER", 100), "hi")
        req = fake.requests[0]
        self.assertEqual(req["path"], "/api/anthropic/v1/messages")
        self.assertEqual(req["headers"]["x-api-key"], KEY)
        self.assertEqual(req["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(req["body"]["system"], "SYS")
        self.assertEqual(req["body"]["messages"], [{"role": "user", "content": "USER"}])
        self.assertEqual(c.stats()["in_tok"], 10)

    def test_env_base(self):
        fake = self.serve(chat("x"))
        os.environ["ZAI_BASE_URL"] = fake.base
        c = zai_client.Client(KEY)
        self.assertEqual(c.url, fake.base + "/chat/completions")
        self.assertEqual(c.call("glm-5.3-flash", "low", "S", "U", 10), "x")

    def test_bad_effort(self):
        fake = self.serve(chat("x"))
        c = zai_client.Client(KEY, base=fake.base)
        with self.assertRaises(ValueError):
            c.call("glm-5.3", "medium", "S", "U", 10)
        self.assertEqual(fake.requests, [])

    def test_client_error(self):
        fake = self.serve(fail(400, "1214", "bad param"))
        c = zai_client.Client(KEY, base=fake.base)
        with self.assertRaises(zai_client.ApiError) as cm:
            c.call("glm-5.3", "high", "S", "U", 10)
        self.assertEqual(cm.exception.status, 400)
        self.assertEqual(cm.exception.code, "1214")
        for part in ("HTTP 400", "1214", "bad param"):
            self.assertIn(part, str(cm.exception))
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(c.stats()["errors"], 1)

    def test_gate_caps_requests(self):
        reply = dict(chat("x"), delay=0.1)
        fake = self.serve(reply)
        c = zai_client.Client(KEY, base=fake.base, gate=zai_client.Gate(2))
        out = []
        ts = [threading.Thread(target=lambda: out.append(c.call("glm-5.3-flash", "low", "S", "U", 10)))
              for _ in range(6)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        self.assertEqual(out, ["x"] * 6)
        self.assertEqual(len(fake.requests), 6)
        self.assertLessEqual(fake.peak, 2)


class TestRetry(_FakeCase):
    def test_retry_after_on_429(self):
        fake = self.serve(fail(429, "", "slow down", {"Retry-After": "0.3"}), chat("ok"))
        gate = zai_client.Gate(8)
        c = zai_client.Client(KEY, base=fake.base, gate=gate)
        with mock.patch("zai_client.time.sleep") as sleep:
            self.assertEqual(c.call("glm-5.3", "high", "S", "U", 10), "ok")
        sleep.assert_called_once_with(0.3)
        self.assertEqual(gate.width, 4)
        st = c.stats()
        self.assertEqual((st["calls"], st["ok"], st["retries"], st["throttles"]), (2, 1, 1, 1))

    def test_business_throttle_codes(self):
        fake = self.serve({"status": 200, "body": {"error": {"code": "1302", "message": "rate"}}},
                          fail(400, "1305", "busy"), chat("ok"))
        c = zai_client.Client(KEY, base=fake.base)
        with mock.patch("zai_client.time.sleep"):
            self.assertEqual(c.call("glm-5.3", "high", "S", "U", 10), "ok")
        self.assertEqual(len(fake.requests), 3)
        self.assertEqual(c.stats()["throttles"], 2)

    def test_server_error_retried(self):
        fake = self.serve(fail(503, "", "down"), chat("ok"))
        c = zai_client.Client(KEY, base=fake.base)
        with mock.patch("zai_client.time.sleep") as sleep:
            self.assertEqual(c.call("glm-5.3", "high", "S", "U", 10), "ok")
        self.assertEqual(sleep.call_count, 1)
        self.assertTrue(1.0 <= sleep.call_args[0][0] <= 3.0)
        st = c.stats()
        self.assertEqual((st["retries"], st["throttles"]), (1, 0))

    def test_gives_up_after_retries(self):
        fake = self.serve(fail(500, "", "boom"))
        c = zai_client.Client(KEY, base=fake.base)
        with mock.patch("zai_client.time.sleep") as sleep:
            with self.assertRaises(zai_client.ApiError) as cm:
                c.call("glm-5.3", "high", "S", "U", 10, retries=2)
        self.assertEqual(cm.exception.status, 500)
        self.assertEqual(len(fake.requests), 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(c.stats()["errors"], 1)

    def test_no_response(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        c = zai_client.Client(KEY, base="http://127.0.0.1:%d/api/coding/paas/v4" % port)
        with mock.patch("zai_client.time.sleep") as sleep:
            with self.assertRaises(zai_client.ApiError) as cm:
                c.call("glm-5.3", "high", "S", "U", 10, retries=1)
        self.assertEqual(cm.exception.status, 0)
        self.assertEqual(sleep.call_count, 1)


if __name__ == "__main__":
    unittest.main()
