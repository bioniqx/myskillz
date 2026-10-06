import fnmatch
import http.server
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "glm-requirements-code-audit", "scripts"))
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

    def test_non_zai_provider_in_auth_json_is_skipped_for_zai_coding_plan(self):
        a = self.put(".local/share/opencode/auth.json", {
            "openai": {"type": "api", "key": "sk-openai-0123456789ab"},
            "zai-coding-plan": {"type": "api", "key": "zai-0123456789abcdef"},
        })
        with self.env():
            self.assertEqual(audit.discover_key(), ("zai-0123456789abcdef", a))

    def test_falls_back_to_settings_json_when_auth_json_has_no_zai_provider(self):
        self.put(".local/share/opencode/auth.json",
                 {"openai": {"type": "api", "key": "sk-openai-0123456789ab"}})
        p = self.put(".claude/settings.json", {"env": {"ZAI_API_KEY": "settings-key-0123456789ab"}})
        with self.env():
            self.assertEqual(audit.discover_key(), ("settings-key-0123456789ab", p))

    def test_discover_key_is_zai_client_find_key(self):
        self.assertIs(audit.discover_key, audit.zai_client.find_key)
        self.assertFalse(hasattr(audit, "_walk_for_key"))


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

    def test_init_passes_route_to_base_init_so_url_is_not_stale(self):
        # base has no "/anthropic" in it, so an inferred route would say "openai";
        # the explicit route argument must still win for both self.route and self.url.
        with mock.patch.dict(os.environ, clean_env(NO_PROXY="127.0.0.1"), clear=True):
            cl = audit.Client(self.base, "test-key-0123456789abcdef", "anthropic")
        self.assertEqual(cl.route, "anthropic")
        self.assertEqual(cl.url, self.base.rstrip("/") + "/v1/messages")

    def test_call_forwards_temperature_to_the_wire(self):
        with mock.patch.dict(os.environ, clean_env(NO_PROXY="127.0.0.1"), clear=True):
            cl = audit.Client(self.base, "test-key-0123456789abcdef", audit.route_of(self.base))
            cl.call(audit.FLASH, "high", "SYSTEM PREFIX", "the task", 64, temperature=0.0)
        body = json.loads(FakeZai.seen[-1][2])
        self.assertEqual(body["temperature"], 0.0)

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
        self.assertIn("ZCode: invoke with  $glm-requirements-code-audit <spec file>", out)


class DocumentationConfigs(unittest.TestCase):
    def test_skill_md_r3_step_1_has_no_parallel_read(self):
        skill_path = os.path.join(os.path.dirname(__file__), "..", "..", "glm-requirements-code-audit", "SKILL.md")
        with open(skill_path, 'r') as f:
            content = f.read()
        r3_section = content.split('## R3')[1].split('## R4')[0]
        self.assertNotIn('in parallel: `Read`', r3_section, "R3 should not have parallel Read and run")
        self.assertIn('run\n`A brief', r3_section, "R3 should have run A brief without parallel Read")

    def test_skill_md_finalize_matches_code_behavior(self):
        skill_path = os.path.join(os.path.dirname(__file__), "..", "..", "glm-requirements-code-audit", "SKILL.md")
        with open(skill_path, 'r') as f:
            content = f.read()
        self.assertIn('an unplanned discrepancy', content)
        self.assertNotIn('a CONFLICT not planned at P0', content, "CONFLICT should not fail gate; doc must align with code behavior")

    def test_setup_md_paths_have_glm_prefix(self):
        setup_path = os.path.join(os.path.dirname(__file__), "..", "..", "glm-requirements-code-audit", "SETUP.md")
        with open(setup_path, 'r') as f:
            lines = f.readlines()
        setup_lines = [line for i, line in enumerate(lines, 1) if i in [10, 12, 28] and 'python3' in line and 'audit' in line]
        for line in setup_lines:
            self.assertIn('glm-', line, f"Setup paths must reference the glm- skill: {line}")

    def test_agent_investigator_write_paths(self):
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "glm-requirements-code-audit", "opencode", "agents", "glm-rca-investigator.md")
        with open(agent_path, 'r') as f:
            content = f.read()
        self.assertIn('write_paths: **/.audit/**', content, "glm-rca-investigator must have session-relative write_paths")

    def test_agent_investigator_steps(self):
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "glm-requirements-code-audit", "opencode", "agents", "glm-rca-investigator.md")
        with open(agent_path, 'r') as f:
            content = f.read()
        self.assertRegex(content, r'steps:\s*30', "glm-rca-investigator must have steps: 30")

    def test_agent_verifier_write_paths(self):
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "glm-requirements-code-audit", "opencode", "agents", "glm-rca-verifier.md")
        with open(agent_path, 'r') as f:
            content = f.read()
        self.assertIn('write_paths: **/.audit/**', content, "glm-rca-verifier must have session-relative write_paths")

    def test_agent_verifier_steps(self):
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "glm-requirements-code-audit", "opencode", "agents", "glm-rca-verifier.md")
        with open(agent_path, 'r') as f:
            content = f.read()
        self.assertRegex(content, r'steps:\s*25', "glm-rca-verifier must have steps: 25")


class ZcodeDocSurface(unittest.TestCase):
    SKILL_DIR = os.path.normpath(os.path.join(SCRIPTS, ".."))
    SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
    TUNING = os.path.join(SKILL_DIR, "references", "glm-tuning.md")
    SETUP_MD = os.path.join(SKILL_DIR, "SETUP.md")

    def read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    @classmethod
    def folded_description(cls):
        with open(cls.SKILL_MD, encoding="utf-8") as fh:
            text = fh.read()
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
        d = re.search(r"^description:[ \t]*(.*?)(?=^\S|\Z)", m.group(1), re.S | re.M)
        desc = " ".join(l.strip() for l in d.group(1).splitlines())
        head, _, rest = desc.partition(" ")
        if head in (">-", ">", "|-", "|"):
            desc = rest
        return desc

    def test_description_when_clause_sits_up_front_under_1024(self):
        desc = self.folded_description()
        self.assertLessEqual(len(desc), 1024, "description is %d chars" % len(desc))
        first = desc.split(". ", 1)[0] + "."
        self.assertTrue(first.startswith("Use whenever"), "WHEN clause is not up front")
        self.assertLessEqual(len(first), 250, "WHEN clause is %d chars" % len(first))

    def test_skill_md_has_the_bootstrap_path_loop_with_zcode(self):
        flat = self.flat(self.read(self.SKILL_MD))
        self.assertIn("A=", flat)
        self.assertIn("$OPENCODE_CONFIG_DIR/skills/glm-requirements-code-audit", flat)
        self.assertIn("~/.zcode/skills/glm-requirements-code-audit", flat)

    def test_glm_tuning_char_count_matches_the_new_description(self):
        desc = self.folded_description()
        tuning = self.flat(self.read(self.TUNING))
        self.assertIn("description measured at %d chars" % len(desc), tuning)
        self.assertNotIn("description measured at 911 chars", tuning)

    def test_setup_md_key_paths_include_the_v2_credentials_file(self):
        self.assertIn("credentials.json", self.flat(self.read(self.SETUP_MD)))
        self.assertIn("~/.zcode/v2/credentials.json", self.flat(self.read(self.SETUP_MD)),
                      "SETUP.md must name the zcode v2 credentials path, not only the ~/.zcode/*.json glob")

    def test_setup_md_key_sentence_names_only_paths_zai_client_reads(self):
        flat = self.flat(self.read(self.SETUP_MD))
        sentence = flat.split("also reads the key from", 1)[1].split("only from", 1)[0]
        named = re.findall(r"`(~[^`]+)`", sentence)
        self.assertTrue(named, "no key paths found in the SETUP.md key-source sentence")
        for path in named:
            self.assertTrue(
                path in audit.zai_client.KEY_FILES
                or any(fnmatch.fnmatchcase(k, path) for k in audit.zai_client.KEY_FILES),
                "%s is claimed in SETUP.md but zai_client.KEY_FILES never reads it" % path)

    def test_glm_tuning_admits_user_level_zcode_hooks(self):
        tuning = self.flat(self.read(self.TUNING))
        self.assertNotIn("no Claude Code hook system", tuning)
        self.assertIn("user-level hooks", tuning)
        self.assertIn("~/.zcode/cli/config.json", tuning)

    def test_four_call_turn_budget_is_kept(self):
        # The api lane stays four lead calls (brief, checklist, run,
        # queue/adjudicate/finalize): the zcode doc edits must not touch R0.
        text = self.read(self.SKILL_MD)
        r0 = self.flat(text.split("## R0", 1)[1].split("## R1", 1)[0])
        self.assertIn("The whole audit is four calls", r0)
        for call in ("A brief", "A run", "A queue", "A adjudicate", "A finalize"):
            self.assertIn(call, r0, call)
        self.assertIn("Do not invent extra steps between them", r0)


class ZcodeAuditBehavior(unittest.TestCase):
    SKILL_DIR = os.path.normpath(os.path.join(SCRIPTS, ".."))

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    def test_zcode_agents_use_camelcase_tool_names(self):
        agents = os.path.join(self.SKILL_DIR, "agents", "zcode")
        for name in ("glm-rca-investigator.md", "glm-rca-verifier.md"):
            with open(os.path.join(agents, name), encoding="utf-8") as fh:
                fm = fh.read().split("\n---\n")[0]
            self.assertIn("tools: Read, Grep, Glob, Write", fm, name)
            self.assertNotIn("tools: read, grep, glob, write", fm, name)

    def test_zcode_dispatch_line_names_agents_with_real_ids(self):
        with open(os.path.join(SCRIPTS, "audit.py"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("ZCode: dispatch each worker as agent glm-rca-investigator", self.flat(text))
        self.assertNotIn("subagent_type", text)

    def test_setup_zcode_strips_opencode_and_setup_md_from_the_copy(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        buf = io.StringIO()
        with mock.patch.dict(os.environ, clean_env(HOME=home), clear=True), redirect_stdout(buf):
            audit.main(["setup", "--harness", "zcode"])
        skill = os.path.join(home, ".zcode", "skills", "glm-requirements-code-audit")
        self.assertTrue(os.path.isfile(os.path.join(skill, "SKILL.md")))
        self.assertTrue(os.path.isfile(os.path.join(skill, "scripts", "audit.py")))
        self.assertFalse(os.path.exists(os.path.join(skill, "opencode")))
        self.assertFalse(os.path.exists(os.path.join(skill, "SETUP.md")))
        self.assertTrue(os.path.isfile(os.path.join(home, ".zcode", "agents", "glm-rca-investigator.md")))
        self.assertTrue(os.path.isfile(os.path.join(home, ".zcode", "agents", "glm-rca-verifier.md")))
