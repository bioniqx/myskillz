"""test_hp_config: tests for hp_config module."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hp_config


class TestHPConfig(unittest.TestCase):
    """Test hp_config module."""

    def test_agent_name(self):
        """AGENT_NAME is hybrid-plan-writer."""
        self.assertEqual(hp_config.AGENT_NAME, "hybrid-plan-writer")

    def test_sentinel(self):
        """SENTINEL is HP-WRITER-OK."""
        self.assertEqual(hp_config.SENTINEL, "HP-WRITER-OK")

    def test_system_prompt_is_string(self):
        """SYSTEM_PROMPT is a string."""
        self.assertIsInstance(hp_config.SYSTEM_PROMPT, str)

    def test_system_prompt_contains_sentinel(self):
        """SYSTEM_PROMPT ends with sentinel."""
        self.assertIn(hp_config.SENTINEL, hp_config.SYSTEM_PROMPT)

    def test_permission_block(self):
        """permission_block is read-only: bash only allows ls (free tier rejects a fully denied bash)."""
        perm = hp_config.permission_block()
        self.assertEqual(perm["edit"], "deny")
        self.assertEqual(perm["bash"], {"*": "deny", "ls": "allow"})
        self.assertNotIn("execute", perm)
        self.assertEqual(perm["*"], "deny")
        self.assertEqual(perm["task"], "deny")
        self.assertEqual(perm["skill"], "deny")
        for pat in ("*.env", "*.env.*", "*.ssh/*", "*.pem", "*.key", "*id_rsa*", "*id_ed25519*"):
            self.assertEqual(perm["read"][pat], "deny", pat)
        self.assertEqual(perm["webfetch"], "deny")
        self.assertEqual(perm["websearch"], "deny")
        self.assertEqual(perm["external_directory"], "deny")

    def test_build_config_structure(self):
        """build_config returns dict with agent and permission keys."""
        prompt = "test prompt content"
        config = hp_config.build_config(prompt)
        self.assertIsInstance(config, dict)
        self.assertIn("agent", config)
        self.assertIn("permission", config)

    def test_build_config_agent_name(self):
        """build_config agent key is AGENT_NAME."""
        prompt = "test prompt"
        config = hp_config.build_config(prompt)
        self.assertIn(hp_config.AGENT_NAME, config["agent"])

    def test_build_config_agent_fields(self):
        """build_config agent has description, mode, prompt, permission."""
        prompt = "test prompt"
        config = hp_config.build_config(prompt)
        agent = config["agent"][hp_config.AGENT_NAME]
        self.assertIn("description", agent)
        self.assertIn("mode", agent)
        self.assertIn("prompt", agent)
        self.assertIn("permission", agent)
        self.assertEqual(agent["mode"], "primary")

    def test_build_config_prompt_includes_system_and_input(self):
        """build_config prompt combines system prompt and input."""
        test_prompt = "custom task instruction"
        config = hp_config.build_config(test_prompt)
        full_prompt = config["agent"][hp_config.AGENT_NAME]["prompt"]
        self.assertIn(hp_config.SYSTEM_PROMPT, full_prompt)
        self.assertIn(test_prompt, full_prompt)

    def test_build_config_permission_equals_top_level(self):
        """build_config top-level permission matches agent permission."""
        prompt = "test"
        config = hp_config.build_config(prompt)
        agent_perm = config["agent"][hp_config.AGENT_NAME]["permission"]
        top_level_perm = config["permission"]
        self.assertEqual(agent_perm, top_level_perm)

    def test_config_env_returns_dict(self):
        """config_env returns dict."""
        env = hp_config.config_env("test prompt")
        self.assertIsInstance(env, dict)

    def test_config_env_has_opencode_config_content(self):
        """config_env has OPENCODE_CONFIG_CONTENT key."""
        env = hp_config.config_env("test prompt")
        self.assertIn("OPENCODE_CONFIG_CONTENT", env)
        self.assertEqual(env["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")

    def test_config_env_content_is_valid_json(self):
        """config_env OPENCODE_CONFIG_CONTENT is valid JSON."""
        env = hp_config.config_env("test prompt")
        content = env["OPENCODE_CONFIG_CONTENT"]
        parsed = json.loads(content)
        self.assertIsInstance(parsed, dict)

    def test_config_env_json_structure(self):
        """config_env JSON has agent and permission keys."""
        env = hp_config.config_env("test prompt")
        parsed = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        self.assertIn("agent", parsed)
        self.assertIn("permission", parsed)


class TestShellPermissionKey(unittest.TestCase):
    """opencode v2.0.22 names its shell tool "shell"; it must carry exactly the rules of "bash"."""

    def test_shell_block_equals_bash_block(self):
        perm = hp_config.permission_block()
        self.assertEqual(perm["shell"], {"*": "deny", "ls": "allow"})
        self.assertEqual(perm["shell"], perm["bash"])
        self.assertIsNot(perm["shell"], perm["bash"])
        config = hp_config.build_config("task")
        for block in (config["agent"][hp_config.AGENT_NAME]["permission"], config["permission"]):
            self.assertEqual(block["shell"], block["bash"])


if __name__ == "__main__":
    unittest.main()
