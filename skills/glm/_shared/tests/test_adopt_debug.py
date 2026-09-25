import contextlib
import importlib.util
import io
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

DEBUG_TOOL = (Path(__file__).resolve().parents[2]
              / "systematic-debugging-glm" / "scripts" / "debug_tool.py")


def load_debug_tool():
    spec = importlib.util.spec_from_file_location("debug_tool_under_test", DEBUG_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestFindKeyDelegatesToZaiClient(unittest.TestCase):
    def test_find_key_calls_zai_client(self):
        mod = load_debug_tool()
        with patch.object(mod.zai_client, "find_key",
                           lambda: ("k123456789012345", "env:ZAI_API_KEY")):
            assert mod.find_key() == ("k123456789012345", "env:ZAI_API_KEY")


class TestApiCallDelegatesToZaiClient(unittest.TestCase):
    @contextlib.contextmanager
    def _no_network(self, mod):
        def deny(*_a, **_k):
            raise urllib.error.URLError("network disabled for this test")
        with patch.object(mod.time, "sleep", lambda *_a, **_k: None), \
                patch.object(mod.urllib.request, "urlopen", deny):
            yield

    def test_api_call_forwards_openai_route(self):
        mod = load_debug_tool()
        seen = {}

        class FakeClient:
            def __init__(self, key, base="", route=""):
                seen.update(key=key, base=base, route=route)

            def call(self, model, effort, system, user, max_tokens):
                seen.update(model=model, effort=effort, system=system, user=user, max_tokens=max_tokens)
                return "VERDICT: CONFIRMED"

        with self._no_network(mod), patch.object(mod.zai_client, "Client", FakeClient):
            out = mod.api_call("k", "https://api.z.ai/api/coding/paas/v4", "glm-5.3", "high",
                                "sys", "usr", 500, False)
        assert out == "VERDICT: CONFIRMED"
        assert seen["route"] == "openai"

    def test_api_call_forwards_anthropic_route(self):
        mod = load_debug_tool()
        seen = {}

        class FakeClient:
            def __init__(self, key, base="", route=""):
                seen["route"] = route

            def call(self, model, effort, system, user, max_tokens):
                return "VERDICT: REFUTED"

        with self._no_network(mod), patch.object(mod.zai_client, "Client", FakeClient):
            out = mod.api_call("k", "https://api.z.ai/api/anthropic", "glm-5.3", "max",
                                "sys", "usr", 500, True)
        assert out == "VERDICT: REFUTED"
        assert seen["route"] == "anthropic"


class TestCmdSetupMentionsOcHarness(unittest.TestCase):
    def test_setup_opencode_mentions_oc_harness(self):
        mod = load_debug_tool()
        a = mod.argparse.Namespace(harness="opencode")
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mod.cmd_setup(a)
        assert rc == 0
        assert "oc_harness.py run" in buf.getvalue()


if __name__ == "__main__":
    unittest.main()
