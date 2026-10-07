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
AGENTS_DIR = os.path.join(HERE, "..", "..", "glm-writing-plans", "opencode", "agents")
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


class TestFindCredentialsOpenCodeAuth(unittest.TestCase):
    def setUp(self):
        self.saved = dict(os.environ)
        self.home = tempfile.mkdtemp()
        self.cwd = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.cwd)
        keep = {k: v for k, v in os.environ.items()
                if k not in plan_tool.KEY_ENV
                and k not in ("ZAI_BASE_URL", "GLM_BASE_URL", "PLAN_BASE_URL", "ANTHROPIC_BASE_URL")}
        keep["HOME"] = self.home
        self.env = mock.patch.dict(os.environ, keep, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        os.chdir(self.old_cwd)
        os.environ.clear()
        os.environ.update(self.saved)
        shutil.rmtree(self.home, ignore_errors=True)
        shutil.rmtree(self.cwd, ignore_errors=True)

    def put(self, rel, obj):
        p = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f)
        return p

    def test_zai_coding_plan_entry_wins_over_leading_anthropic_entry(self):
        auth = self.put(".local/share/opencode/auth.json",
                        {"anthropic": {"type": "api", "key": "sk-ant-0123456789abcdef"},
                         "zai-coding-plan": {"type": "api", "key": "z" * 20}})
        key, base, proto, src = plan_tool.find_credentials()
        self.assertEqual(key, "z" * 20)
        self.assertEqual(src, auth)

    def test_non_zai_provider_only_is_not_returned(self):
        self.put(".local/share/opencode/auth.json",
                 {"anthropic": {"type": "api", "key": "sk-ant-0123456789abcdef"}})
        key, base, proto, src = plan_tool.find_credentials()
        self.assertIsNone(key)

    def test_plan_api_key_env_beats_opencode_auth_file(self):
        self.put(".local/share/opencode/auth.json",
                 {"zai-coding-plan": {"type": "api", "key": "z" * 20}})
        os.environ["PLAN_API_KEY"] = "p" * 20
        os.environ["ANTHROPIC_BASE_URL"] = "https://example.invalid/should-be-ignored"
        key, base, proto, src = plan_tool.find_credentials()
        self.assertEqual(key, "p" * 20)
        self.assertEqual(src, "env:PLAN_API_KEY")
        self.assertEqual(base, plan_tool.DEFAULT_BASE)


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


class AgentFileTests(unittest.TestCase):
    def test_opencode_agent_rendered_from_neutral_source(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        os.makedirs(os.path.join(tmp, "opencode", "agents"))
        with open(os.path.join(tmp, "opencode", "agents", "glm-plan-task-writer.md"), "w") as fh:
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


class OpenCodeAgentFileTests(unittest.TestCase):
    def test_writer_runs_24_steps_on_flash(self):
        fm, _ = _frontmatter("glm-plan-task-writer")
        self.assertEqual(fm["model"], "flash")
        self.assertEqual(fm["steps"], "24")

    def test_deep_writer_is_glm53_max_24_steps(self):
        fm, text = _frontmatter("glm-plan-task-writer-deep")
        self.assertEqual(fm["model"], "glm-5.3")
        self.assertEqual(fm["effort"], "max")
        self.assertEqual(fm["steps"], "24")
        self.assertEqual(fm["access"], "write")
        self.assertEqual(fm["bash"], "true")
        self.assertIn("T07 OK", text)

    def test_reviewer_is_glm53_high(self):
        fm, text = _frontmatter("glm-plan-reviewer")
        self.assertEqual(fm["model"], "glm-5.3")
        self.assertEqual(fm["effort"], "high")
        self.assertEqual(fm["access"], "write")
        self.assertIn("APPROVED", text)

    def test_render_uses_major_not_detect(self):
        real = plan_tool.oc_harness.render_agent
        with mock.patch.object(plan_tool.oc_harness, "major", return_value=2), \
             mock.patch.object(plan_tool.oc_harness, "detect", side_effect=AssertionError("detect() called")), \
             mock.patch.object(plan_tool.oc_harness, "render_agent", side_effect=real) as ren:
            text = plan_tool.agent_file("opencode", "glm-plan-task-writer-deep")
        self.assertEqual(ren.call_args[0][1], 2)
        self.assertIn("mode: subagent", text)
        self.assertIn("zai-coding-plan/glm-5.3", text)
        self.assertNotIn("glm-5.3-flash", text)


class OpenCodeSetupTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        for p in (mock.patch.dict(os.environ, {"HOME": self.home}),
                  mock.patch.object(plan_tool, "find_credentials", return_value=NO_KEY)):
            p.start()
            self.addCleanup(p.stop)

    def run_setup(self, major):
        buf = io.StringIO()
        with mock.patch.object(plan_tool.oc_harness, "major", return_value=major), \
             mock.patch.object(plan_tool.oc_harness, "detect", return_value=major), \
             contextlib.redirect_stdout(buf):
            rc = plan_tool.cmd_setup(argparse.Namespace(harness="opencode", apply=True))
        self.assertEqual(rc, 0, buf.getvalue())
        return buf.getvalue()

    def test_setup_installs_all_three_agents(self):
        self.run_setup(2)
        adir = os.path.join(self.home, ".config", "opencode", "agents")
        for name in ("glm-plan-task-writer", "glm-plan-task-writer-deep", "glm-plan-reviewer"):
            self.assertTrue(os.path.isfile(os.path.join(adir, name + ".md")), name)

    def test_v2_setup_drops_background_env_hint(self):
        self.assertNotIn("OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS", self.run_setup(2))

    def test_v1_setup_keeps_background_env_hint(self):
        self.assertIn("OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS", self.run_setup(1))


class WriterGroupingTests(unittest.TestCase):
    def test_group_count_on_lanes_is_ceil_of_quarter(self):
        for n, want in ((1, 1), (4, 1), (5, 2), (10, 3), (32, 8), (40, 10)):
            self.assertEqual(plan_tool.writer_group_count(n, True, 8), want, n)

    def test_group_count_elsewhere_is_one_per_task_up_to_cap(self):
        self.assertEqual(plan_tool.writer_group_count(5, False, 8), 5)
        self.assertEqual(plan_tool.writer_group_count(30, False, 8), 8)
        self.assertEqual(plan_tool.writer_group_count(100, False, 8), 25)
        self.assertEqual(plan_tool.writer_group_count(0, False, 8), 0)

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
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "", "OC_MAX_LANES": "7"}):
            self.assertEqual(plan_tool.lane_width(), 7)

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

    def test_on_opencode_asks_shared_harness_with_script_path(self):
        with mock.patch.object(plan_tool.oc_harness, "harness", return_value="opencode") as h:
            self.assertTrue(plan_tool.on_opencode())
        h.assert_called_once_with(plan_tool.TOOL)
        with mock.patch.object(plan_tool.oc_harness, "harness", return_value="claude"):
            self.assertFalse(plan_tool.on_opencode())
        with mock.patch.object(plan_tool.oc_harness, "harness", side_effect=OSError("boom")):
            self.assertFalse(plan_tool.on_opencode())


class OpenCodeDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.major = 2
        patches = [mock.patch.object(plan_tool, "on_opencode", return_value=True),
                   mock.patch.object(plan_tool, "agent_installed", return_value="/fake/agents"),
                   mock.patch.object(plan_tool, "find_credentials", return_value=NO_KEY),
                   mock.patch.object(plan_tool.oc_harness, "major", side_effect=lambda *a, **k: self.major),
                   mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "", "OC_MAX_LANES": ""})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.plan = os.path.join(self.tmp, "plan.md")

    def contracts(self, n, deep=()):
        with open(self.plan, "w", encoding="utf-8") as fh:
            fh.write(_plan_text(n, deep))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = plan_tool.cmd_contracts(argparse.Namespace(plan=self.plan, spec=None, allow=[], workers=None))
        out = buf.getvalue()
        self.assertEqual(rc, 0, out)
        work = plan_tool.default_work(self.plan)
        with open(os.path.join(work, "work.json"), encoding="utf-8") as fh:
            info = json.load(fh)
        return out, work, info

    def expected(self, agent, work, sub, gid, description):
        return plan_tool.oc_harness.dispatch_line(agent, os.path.join(work, sub, gid + ".md"),
                                                  description, self.major)

    def test_ten_tasks_make_three_groups_of_at_most_four(self):
        _, _, info = self.contracts(10)
        sizes = [len(v) for v in info["groups"].values()]
        self.assertEqual(len(sizes), 3)
        self.assertTrue(all(s <= 4 for s in sizes), sizes)
        self.assertEqual(info["groups"]["W01"], ["T01", "T02", "T03", "T04"])

    def test_v2_dispatch_uses_writer_agent_and_no_foreign_fallback(self):
        out, work, _ = self.contracts(10)
        self.assertIn(self.expected("glm-plan-task-writer", work, "briefs", "W01", "plan T01-T04"), out)
        self.assertIn(self.expected("glm-plan-task-writer", work, "briefs", "W03", "plan T09-T10"), out)
        self.assertNotIn("general-purpose", out)
        self.assertNotIn("subagent_type=", out)
        self.assertNotIn("haiku", out)
        self.assertNotIn("sonnet", out)

    def test_deep_group_goes_to_deep_writer(self):
        out, work, info = self.contracts(5, deep=("T05",))
        self.assertEqual(info["groups"]["W02"], ["T04", "T05"])
        self.assertIn(self.expected("glm-plan-task-writer-deep", work, "briefs", "W02", "plan T04-T05"), out)
        self.assertIn(self.expected("glm-plan-task-writer", work, "briefs", "W01", "plan T01-T03"), out)

    def test_deep_group_falls_back_to_writer_when_deep_agent_missing(self):
        only_writer = lambda repo, name="glm-plan-task-writer": None if name == "glm-plan-task-writer-deep" else "/fake/agents"
        with mock.patch.object(plan_tool, "agent_installed", side_effect=only_writer):
            out, work, _ = self.contracts(5, deep=("T05",))
        self.assertIn(self.expected("glm-plan-task-writer", work, "briefs", "W02", "plan T04-T05"), out)
        self.assertNotIn("glm-plan-task-writer-deep", out)
        self.assertNotIn(self.expected("general", work, "briefs", "W02", "plan T04-T05"), out)

    def test_missing_agents_fall_back_to_general(self):
        with mock.patch.object(plan_tool, "agent_installed", return_value=None):
            out, work, _ = self.contracts(10)
        self.assertIn(self.expected("general", work, "briefs", "W01", "plan T01-T04"), out)
        self.assertNotIn("general-purpose", out)

    def test_v1_dispatch_line_rendered_for_major_one(self):
        self.major = 1
        out, work, _ = self.contracts(10)
        self.assertIn(self.expected("glm-plan-task-writer", work, "briefs", "W01", "plan T01-T04"), out)

    def test_forty_tasks_split_into_messages_of_lane_width(self):
        out, work, info = self.contracts(40)
        self.assertEqual(len(info["groups"]), 10)
        self.assertTrue(all(len(v) == 4 for v in info["groups"].values()))
        self.assertIn("MESSAGE 1 (8 calls", out)
        self.assertIn("MESSAGE 2 (2 calls", out)
        self.assertIn(self.expected("glm-plan-task-writer", work, "briefs", "W10", "plan T37-T40"), out)

    def test_review_dispatches_plan_reviewer(self):
        _, work, _ = self.contracts(2, deep=("T01",))
        with open(os.path.join(work, "tasks", "T01.md"), "w", encoding="utf-8") as fh:
            fh.write("**Files:**\n- Create: `src/p01.py`\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = plan_tool.cmd_review(argparse.Namespace(plan=self.plan, all=False, size=None, agents=None))
        out = buf.getvalue()
        self.assertEqual(rc, 0, out)
        self.assertIn(self.expected("glm-plan-reviewer", work, "review-briefs", "R01", "review T01"), out)
        self.assertNotIn("general-purpose", out)
        self.assertNotIn("sonnet", out)


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
