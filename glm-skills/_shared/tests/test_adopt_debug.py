import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

DEBUG_TOOL = (Path(__file__).resolve().parents[2]
              / "glm-systematic-debugging" / "scripts" / "debug_tool.py")


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

    def test_api_call_reuses_a_given_client_instead_of_building_one(self):
        mod = load_debug_tool()
        seen = {}

        class ClientMustNotBeConstructed:
            def __init__(self, *a, **k):
                raise AssertionError("api_call built a new Client although one was passed in")

        class GivenClient:
            def call(self, model, effort, system, user, max_tokens):
                seen["model"] = model
                return "VERDICT: CONFIRMED"

        with self._no_network(mod), patch.object(mod.zai_client, "Client", ClientMustNotBeConstructed):
            out = mod.api_call("k", "https://api.z.ai/api/coding/paas/v4", "glm-5.3", "high",
                                "sys", "usr", 500, False, client=GivenClient())
        assert out == "VERDICT: CONFIRMED"
        assert seen["model"] == "glm-5.3"


class TestCmdScanSharesOneClientAcrossThePmap(unittest.TestCase):
    def test_scan_builds_exactly_one_client_for_all_workers(self):
        mod = load_debug_tool()
        created = []

        class FakeClient:
            def __init__(self, key, base="", route=""):
                created.append(route)

            def call(self, model, effort, system, user, max_tokens):
                return "VERDICT: CONFIRMED"

        tasks = [{"id": "t1", "prompt": "p1"}, {"id": "t2", "prompt": "p2"},
                 {"id": "t3", "prompt": "p3"}]
        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(tasks, tf)
        tf.close()
        self.addCleanup(lambda: Path(tf.name).unlink(missing_ok=True))

        a = mod.argparse.Namespace(
            tasks=tf.name, area=None, question=None, context_file=None, context=None,
            tier="light", model=None, effort=None, base="https://api.z.ai/api/coding/paas/v4",
            max_tokens=100, print_prompts=False, out=None, jobs=3, dir=".")

        with patch.object(mod, "find_key", lambda: ("k123456789012345", "env:ZAI_API_KEY")), \
                patch.object(mod.zai_client, "Client", FakeClient):
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = mod.cmd_scan(a)
        assert rc == 0
        assert len(created) == 1, "cmd_scan must share one Client (and its AIMD gate) across the pmap"


class TestCmdScanCapsApiWorkersAtEight(unittest.TestCase):
    def test_scan_peak_concurrency_never_exceeds_eight(self):
        import threading
        import time
        mod = load_debug_tool()
        lock, state = threading.Lock(), {"now": 0, "peak": 0}

        class FakeClient:
            def __init__(self, key, base="", route=""):
                pass

            def call(self, model, effort, system, user, max_tokens):
                with lock:
                    state["now"] += 1
                    state["peak"] = max(state["peak"], state["now"])
                time.sleep(0.05)
                with lock:
                    state["now"] -= 1
                return "VERDICT: CONFIRMED"

        tf = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump([{"id": "t%d" % i, "prompt": "p"} for i in range(20)], tf)
        tf.close()
        self.addCleanup(lambda: Path(tf.name).unlink(missing_ok=True))
        a = mod.argparse.Namespace(
            tasks=tf.name, area=None, question=None, context_file=None, context=None,
            tier="light", model=None, effort=None, base="https://api.z.ai/api/coding/paas/v4",
            max_tokens=100, print_prompts=False, out=None, jobs=64, dir=".")
        with patch.object(mod, "find_key", lambda: ("k123456789012345", "env:ZAI_API_KEY")), \
                patch.object(mod.zai_client, "Client", FakeClient), \
                redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            assert mod.cmd_scan(a) == 0
        assert state["peak"] == 8, state


class TestCmdSetupZcode(unittest.TestCase):
    def test_setup_zcode_prints_the_install_block(self):
        mod = load_debug_tool()
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mod.cmd_setup(mod.argparse.Namespace(harness="zcode"))
        out = buf.getvalue()
        assert rc == 0
        assert "install-zcode.sh" in out
        assert "oc_harness" not in out


class TestQuestionKeywords(unittest.TestCase):
    def test_stopwords_dropped_and_order_kept(self):
        mod = load_debug_tool()
        assert mod.question_keywords("why does the parser drop the trailing token") == [
            "parser", "drop", "trailing", "token"]

    def test_limit_and_case_insensitive_dedupe(self):
        mod = load_debug_tool()
        assert mod.question_keywords("Parser parser alpha beta gamma delta", limit=3) == [
            "Parser", "alpha", "beta"]

    def test_no_question_gives_no_keywords(self):
        mod = load_debug_tool()
        assert mod.question_keywords(None) == []


class TestBuildTasksCodeWindows(unittest.TestCase):
    def test_area_prompt_carries_code_around_the_match(self):
        mod = load_debug_tool()
        root = tempfile.mkdtemp(prefix="sdscan_test.")
        self.addCleanup(mod.shutil.rmtree, root, True)
        pkg = Path(root) / "pkg"
        pkg.mkdir()
        (pkg / "parse.py").write_text(
            "def parse(text):\n"
            "    tokens = text.split()\n"
            "    return tokens[:-1]  # drops the trailing token\n")
        a = mod.argparse.Namespace(tasks=None, area=["pkg"],
                                   question="why does the parser drop the trailing token")
        tasks = mod.build_tasks(a, root)
        assert len(tasks) == 1
        prompt = tasks[0]["prompt"]
        assert "pkg/parse.py:3:" in prompt
        assert "CODE:" in prompt
        assert "return tokens[:-1]" in prompt.split("CODE:", 1)[1]


class TestBuildTasksGrepsAreaOnce(unittest.TestCase):
    def test_one_area_scoped_grep_per_area(self):
        mod = load_debug_tool()
        calls = []

        def fake_grep_area(root, area, words, cap):
            calls.append((area, list(words)))
            return ""

        def no_repo_wide_grep(*_a, **_k):
            raise AssertionError("build_tasks must not run a repo-wide grep per keyword")

        a = mod.argparse.Namespace(tasks=None, area=["src/a", "src/b"],
                                   question="why does the parser drop the trailing token")
        with patch.object(mod, "grep_area", fake_grep_area), \
                patch.object(mod, "grep", no_repo_wide_grep), \
                patch.object(mod, "sh", lambda *_a, **_k: (0, "x.py\n")):
            tasks = mod.build_tasks(a, ".")
        kw = ["parser", "drop", "trailing", "token"]
        assert calls == [("src/a", kw), ("src/b", kw)]
        assert [t["id"] for t in tasks] == ["src/a", "src/b"]


class TestScanAgentLane(unittest.TestCase):
    def _run(self, tier="light"):
        mod = load_debug_tool()
        root = tempfile.mkdtemp(prefix="sdlane_test.")
        self.addCleanup(mod.shutil.rmtree, root, True)
        tasks = Path(root) / "tasks.json"
        tasks.write_text(json.dumps([{"id": "t1", "prompt": "p1"}, {"id": "t2", "prompt": "p2"}]))
        a = mod.argparse.Namespace(
            tasks=str(tasks), area=None, question=None, context_file=None, context="shared ctx",
            tier=tier, model=None, effort=None, base=None, max_tokens=100,
            print_prompts=False, out=None, jobs=0, dir=root)
        buf = io.StringIO()
        with patch.object(mod, "find_key", lambda: (None, "none")), \
                redirect_stdout(buf):
            rc = mod.cmd_scan(a)
        return mod, rc, buf.getvalue(), Path(root) / ".debug" / "scan"

    def test_agent_lane_names_the_worker_without_a_lanes_file(self):
        mod, rc, out, d = self._run()
        assert rc == 0
        assert (d / "t1.txt").is_file() and (d / "t2.txt").is_file()
        assert not (d / "lanes.json").exists()
        assert "glm-debug-worker" in out
        assert "oc_harness" not in out

    def test_prompts_carry_scripts_dir_in_a_byte_identical_prefix(self):
        mod, rc, out, d = self._run()
        t1 = (d / "t1.txt").read_text()
        t2 = (d / "t2.txt").read_text()
        assert t1.startswith(mod.SYS_PROMPT)
        assert ("S=%s" % mod.SCRIPTS) in t1
        assert t1.split("\n---\nTASK: ")[0] == t2.split("\n---\nTASK: ")[0]
        assert t1.endswith("TASK: p1") and t2.endswith("TASK: p2")


if __name__ == "__main__":
    unittest.main()
