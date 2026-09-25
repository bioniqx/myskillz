import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import oc_harness


class TestOcHarnessRender(unittest.TestCase):
    def test_provider_and_models_constants(self):
        self.assertEqual(oc_harness.PROVIDER, "zai-coding-plan")
        self.assertEqual(oc_harness.MODELS, {"flash": "glm-5.3-flash", "pro": "glm-5.3"})
        assert oc_harness.PROVIDER == "zai-coding-plan"

    def test_detect_returns_major_from_version_output(self):
        tmpdir = tempfile.mkdtemp()
        fake_bin = os.path.join(tmpdir, "opencode")
        with open(fake_bin, "w") as f:
            f.write("#!/bin/sh\necho '1.18.3'\n")
        os.chmod(fake_bin, 0o755)
        try:
            major = oc_harness.detect(fake_bin)
            self.assertEqual(major, 1)
        finally:
            shutil.rmtree(tmpdir)

    def test_detect_returns_none_for_missing_binary(self):
        result = oc_harness.detect("/nonexistent/path/opencode-missing")
        self.assertEqual(result, 0)

    def test_parse_frontmatter_extracts_fields_and_body(self):
        text = (
            "---\n"
            "description: Test agent\n"
            "model: flash\n"
            "effort: high\n"
            "bash: true\n"
            "web: false\n"
            "steps: 5\n"
            "---\n"
            "You are a test agent.\n"
        )
        fields, body = oc_harness.parse_frontmatter(text)
        self.assertEqual(fields["description"], "Test agent")
        self.assertEqual(fields["model"], "flash")
        self.assertEqual(fields["effort"], "high")
        self.assertIs(fields["bash"], True)
        self.assertIs(fields["web"], False)
        self.assertEqual(fields["steps"], 5)
        self.assertEqual(body, "You are a test agent.")

    def test_render_agent_v1_and_v2_dialects(self):
        text_v1 = (
            "---\n"
            "description: Test agent\n"
            "model: flash\n"
            "effort: low\n"
            "access: write\n"
            "bash: true\n"
            "web: false\n"
            "steps: 3\n"
            "---\n"
            "Agent prompt body.\n"
        )
        v1 = oc_harness.render_agent(text_v1, 1)
        self.assertIn("mode: subagent", v1)
        self.assertIn("hidden: true", v1)
        self.assertIn("model: zai-coding-plan/glm-5.3-flash", v1)
        self.assertIn("reasoningEffort: low", v1)
        self.assertIn("permission:", v1)
        self.assertIn("edit: allow", v1)
        self.assertIn("bash: allow", v1)
        self.assertIn("webfetch: deny", v1)
        self.assertIn("steps: 3", v1)
        self.assertIn("Agent prompt body.", v1)

        text_v2 = (
            "---\n"
            "description: Test agent\n"
            "model: pro\n"
            "effort: max\n"
            "access: read\n"
            "bash: false\n"
            "web: true\n"
            "steps: 2\n"
            "temperature: 0.2\n"
            "---\n"
            "Agent prompt body.\n"
        )
        v2 = oc_harness.render_agent(text_v2, 2)
        self.assertIn("model: zai-coding-plan/glm-5.3", v2)
        self.assertNotIn("glm-5.3-flash", v2)
        self.assertIn("permissions:", v2)
        self.assertIn("  - action: edit\n    resource: \"*\"\n    effect: deny", v2)
        self.assertIn("  - action: bash\n    resource: \"*\"\n    effect: deny", v2)
        self.assertIn("  - action: webfetch\n    resource: \"*\"\n    effect: allow", v2)
        self.assertIn('description: "Test agent"', v2)
        self.assertIn("request:", v2)
        self.assertIn("reasoning_effort: max", v2)
        self.assertIn("temperature: 0.2", v2)

    def test_render_command_replaces_skill_dir_and_keeps_arguments(self):
        text = (
            "---\n"
            "description: Run the debug skill\n"
            "---\n"
            "!{{SKILL_DIR}}/scripts/context.sh\n"
            "load skill with $ARGUMENTS\n"
        )
        rendered = oc_harness.render_command(
            text, 1, "/home/user/.config/opencode/skills/systematic-debugging"
        )
        self.assertIn('description: "Run the debug skill"', rendered)
        self.assertIn(
            "/home/user/.config/opencode/skills/systematic-debugging/scripts/context.sh",
            rendered,
        )
        self.assertIn("$ARGUMENTS", rendered)
        self.assertNotIn("{{SKILL_DIR}}", rendered)

    def test_config_snippet_contains_provider_and_deny_list(self):
        snippet = oc_harness.config_snippet(1, ["systematic-debugging", "writing-plans"])
        data = json.loads(snippet)
        self.assertIn("zai-coding-plan", data["provider"])
        self.assertEqual(data["permission"]["skill"]["systematic-debugging"], "deny")
        self.assertEqual(data["permission"]["skill"]["writing-plans"], "deny")
        self.assertIn("web-search-prime", data["mcp"])
        self.assertNotIn("permission", json.loads(oc_harness.config_snippet(1, [])))


if __name__ == "__main__":
    unittest.main()
