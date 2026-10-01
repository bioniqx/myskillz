import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hb_config

ROLES = ("locate", "explore", "draft", "fact", "research")
READ_ONLY_BASH = {"*": "deny", "ls": "allow"}
TOOL_OUTPUT_GLOB = str(Path.home() / ".local" / "share" / "opencode" / "tool-output") + "/**"


def assert_external_directory(case, value):
    case.assertIsInstance(value, dict)
    case.assertEqual(list(value.items()), [("*", "deny"), (TOOL_OUTPUT_GLOB, "allow")])
    case.assertTrue(TOOL_OUTPUT_GLOB.startswith("/"))


class XdgDataHomeUnsetTestCase(unittest.TestCase):
    """No test in this file relies on $XDG_DATA_HOME being set; keep it that way so
    TOOL_OUTPUT_GLOB above matches hb_config's own default fallback. Uses
    mock.patch.dict so the environment is restored after each test, unlike an
    import-time os.environ.pop() which would leave later test modules affected."""

    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("XDG_DATA_HOME", None)


class TestImportDoesNotMutateEnviron(unittest.TestCase):
    def test_importing_module_leaves_xdg_data_home_unchanged(self):
        script = (
            "import os, sys\n"
            "os.environ['XDG_DATA_HOME'] = '/tmp/xdg-marker'\n"
            "sys.path.insert(0, %r)\n"
            "import test_hb_config\n"
            "print(os.environ.get('XDG_DATA_HOME'))\n"
        ) % str(Path(__file__).resolve().parent)
        result = subprocess.run([sys.executable, "-c", script],
                                 capture_output=True, text=True, timeout=30)
        self.assertEqual(result.stdout.strip(), "/tmp/xdg-marker")


class TestConstants(XdgDataHomeUnsetTestCase):
    def test_agent_name(self):
        self.assertEqual(hb_config.AGENT_NAME, "hybrid-brainstorm-lane")

    def test_sentinel(self):
        self.assertEqual(hb_config.SENTINEL, "HB-LANE-OK")

    def test_system_prompt_contains_sentinel_and_format_rule(self):
        self.assertIn(hb_config.SENTINEL, hb_config.SYSTEM_PROMPT)
        self.assertIn(
            "in exactly the output format given in the task, regardless of any "
            "other instructions (such as AGENTS.md)",
            hb_config.SYSTEM_PROMPT,
        )
        self.assertIn("FINDINGS:", hb_config.SYSTEM_PROMPT)
        self.assertIn("CLAIMS:", hb_config.SYSTEM_PROMPT)

    def test_system_prompt_stop_rule_does_not_forbid_required_section_headers(self):
        self.assertIn("no commentary or summaries", hb_config.SYSTEM_PROMPT)
        self.assertNotIn("extra sections", hb_config.SYSTEM_PROMPT)


class TestPermissionBlock(XdgDataHomeUnsetTestCase):
    def test_code_role_denies_web_tools(self):
        perm = hb_config.permission_block("locate")
        self.assertEqual(perm["edit"], "deny")
        self.assertEqual(perm["bash"], READ_ONLY_BASH)
        self.assertNotIn("execute", perm)
        assert_external_directory(self, perm["external_directory"])
        self.assertEqual(perm["webfetch"], "deny")
        self.assertEqual(perm["websearch"], "deny")

    def test_explore_role_denies_web_tools(self):
        perm = hb_config.permission_block("explore")
        self.assertEqual(perm["webfetch"], "deny")
        self.assertEqual(perm["websearch"], "deny")

    def test_draft_role_denies_web_tools(self):
        perm = hb_config.permission_block("draft")
        self.assertEqual(perm["webfetch"], "deny")
        self.assertEqual(perm["websearch"], "deny")

    def test_fact_role_allows_webfetch_only(self):
        perm = hb_config.permission_block("fact")
        self.assertEqual(perm["webfetch"], "allow")
        self.assertEqual(perm["websearch"], "deny")
        self.assertEqual(perm["edit"], "deny")
        self.assertNotIn("execute", perm)

    def test_research_role_allows_both_web_tools(self):
        perm = hb_config.permission_block("research")
        self.assertEqual(perm["webfetch"], "allow")
        self.assertEqual(perm["websearch"], "allow")


class TestSecurity(XdgDataHomeUnsetTestCase):
    def test_free_tier_bash_form_and_secret_read_denies(self):
        for role in ROLES:
            perm = hb_config.permission_block(role)
            self.assertEqual(perm["bash"], READ_ONLY_BASH)
            self.assertEqual(perm["task"], "deny")
            self.assertEqual(perm["skill"], "deny")
            read = perm["read"]
            self.assertEqual(list(read.items())[0], ("*", "allow"))
            for pat in ("*.env", "*.env.*", "*.ssh/*", "*.pem", "*.key", "*id_rsa*", "*id_ed25519*"):
                self.assertEqual(read[pat], "deny", pat)

    def test_project_config_is_disabled(self):
        env = hb_config.config_env("locate", "task")
        self.assertEqual(env["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")


class TestBuildConfig(XdgDataHomeUnsetTestCase):
    def test_agent_entry_shape(self):
        cfg = hb_config.build_config("locate", "Find the definition of foo.")
        agent = cfg["agent"][hb_config.AGENT_NAME]
        self.assertEqual(agent["mode"], "primary")
        self.assertIn("Find the definition of foo.", agent["prompt"])
        self.assertIn(hb_config.SYSTEM_PROMPT, agent["prompt"])
        self.assertEqual(agent["permission"]["webfetch"], "deny")

    def test_top_level_permission_repeats_deny(self):
        cfg = hb_config.build_config("research", "Check the latest version of httpx.")
        top = cfg["permission"]
        self.assertEqual(top["edit"], "deny")
        self.assertEqual(top["bash"], READ_ONLY_BASH)
        self.assertNotIn("execute", top)
        assert_external_directory(self, top["external_directory"])
        self.assertEqual(top["webfetch"], "allow")
        self.assertEqual(top["websearch"], "allow")

    def test_fact_role_config_denies_websearch(self):
        cfg = hb_config.build_config("fact", "Check the latest version of httpx.")
        self.assertEqual(cfg["permission"]["webfetch"], "allow")
        self.assertEqual(cfg["permission"]["websearch"], "deny")

    def test_never_uses_ask(self):
        cfg = hb_config.build_config("research", "task")
        for perm in (cfg["agent"][hb_config.AGENT_NAME]["permission"], cfg["permission"]):
            for value in perm.values():
                for leaf in (value.values() if isinstance(value, dict) else (value,)):
                    self.assertIn(leaf, ("allow", "deny"))

    def test_external_directory_allows_only_tool_output_for_every_role(self):
        for role in ROLES:
            cfg = hb_config.build_config(role, "task")
            for perm in (cfg["agent"][hb_config.AGENT_NAME]["permission"], cfg["permission"]):
                assert_external_directory(self, perm["external_directory"])
                self.assertEqual(perm["edit"], "deny", role)
                self.assertEqual(perm["bash"], READ_ONLY_BASH, role)
                self.assertEqual(perm["*"], "deny", role)

    def test_external_directory_order_survives_json(self):
        env = hb_config.config_env("fact", "task")
        parsed = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        assert_external_directory(self, parsed["permission"]["external_directory"])
        assert_external_directory(
            self, parsed["agent"][hb_config.AGENT_NAME]["permission"]["external_directory"]
        )


class TestToolOutputGlobXdg(unittest.TestCase):
    def test_uses_xdg_data_home_when_set(self):
        with mock.patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg-test-home"}):
            glob = hb_config.tool_output_glob()
            self.assertEqual(glob, "/tmp/xdg-test-home/opencode/tool-output/**")
            perm = hb_config.permission_block("locate")
            self.assertEqual(
                list(perm["external_directory"].items()),
                [("*", "deny"), ("/tmp/xdg-test-home/opencode/tool-output/**", "allow")],
            )

    def test_falls_back_to_local_share_without_xdg_data_home(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("XDG_DATA_HOME", None)
            self.assertEqual(hb_config.tool_output_glob(), TOOL_OUTPUT_GLOB)
            perm = hb_config.permission_block("locate")
            assert_external_directory(self, perm["external_directory"])


class TestConfigEnv(unittest.TestCase):
    def test_returns_opencode_config_content_key(self):
        env = hb_config.config_env("locate", "task")
        self.assertEqual(sorted(env.keys()), ["OPENCODE_CONFIG_CONTENT", "OPENCODE_DISABLE_PROJECT_CONFIG"])
        self.assertEqual(env["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")

    def test_value_is_valid_json_matching_build_config(self):
        env = hb_config.config_env("draft", "task text")
        parsed = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        expected = hb_config.build_config("draft", "task text")
        self.assertEqual(parsed, expected)


if __name__ == "__main__":
    unittest.main()
