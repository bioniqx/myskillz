import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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

    def test_detect_returns_zero_on_timeout_instead_of_raising(self):
        # subprocess.TimeoutExpired is not an OSError, so a hung binary must be
        # caught explicitly rather than crashing detect().
        with mock.patch("oc_harness.subprocess.run",
                        side_effect=subprocess.TimeoutExpired(cmd="opencode", timeout=10)):
            self.assertEqual(oc_harness.detect("opencode"), 0)

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
        self.assertNotIn("permissions:", v2)
        self.assertIn("permission:", v2)
        self.assertIn("  edit: deny", v2)
        self.assertIn("  bash: deny", v2)
        self.assertIn("  webfetch: allow", v2)
        self.assertNotIn("action:", v2)
        self.assertNotIn("resource:", v2)
        self.assertNotIn("effect:", v2)
        self.assertIn('description: "Test agent"', v2)
        self.assertNotIn("request:", v2)
        self.assertIn("options:\n  reasoning_effort: max", v2)
        self.assertIn("temperature: 0.2", v2)
        self.assertNotIn("    temperature: 0.2", v2)

    def test_render_agent_v2_permission_matches_v1_nested_map_shape(self):
        text = (
            "---\n"
            "description: Shape agent\n"
            "model: flash\n"
            "effort: high\n"
            "access: write\n"
            "bash: true\n"
            "web: true\n"
            "---\n"
            "Agent prompt body.\n"
        )
        v1 = oc_harness.render_agent(text, 1)
        v2 = oc_harness.render_agent(text, 2)
        v1_perm_lines = [ln for ln in v1.splitlines() if ln == "permission:" or ln.startswith("  edit") or ln.startswith("  bash") or ln.startswith("  webfetch")]
        v2_perm_lines = [ln for ln in v2.splitlines() if ln == "permission:" or ln.startswith("  edit") or ln.startswith("  bash") or ln.startswith("  webfetch")]
        self.assertEqual(v1_perm_lines, v2_perm_lines)

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

    def test_parse_frontmatter_unquotes_value_with_embedded_colon(self):
        fields, _ = oc_harness.parse_frontmatter('---\ndescription: "a: b"\n---\nbody\n')
        self.assertEqual(fields["description"], "a: b")

    def test_parse_frontmatter_unquotes_model_value(self):
        fields, _ = oc_harness.parse_frontmatter('---\nmodel: "flash"\n---\nbody\n')
        self.assertEqual(fields["model"], "flash")

    def test_render_agent_quoted_description_and_model(self):
        text = (
            "---\n"
            'description: "a: b"\n'
            'model: "flash"\n'
            "---\n"
            "body\n"
        )
        rendered = oc_harness.render_agent(text, 1)
        self.assertIn('description: "a: b"', rendered)
        self.assertNotIn('\\"a: b\\"', rendered)
        self.assertIn("model: zai-coding-plan/glm-5.3-flash", rendered)

    def test_render_agent_write_paths_scopes_edit_v2(self):
        text = (
            "---\n"
            "description: Scoped agent\n"
            "model: flash\n"
            "effort: high\n"
            "access: write\n"
            "write_paths: .audit/**\n"
            "bash: false\n"
            "web: false\n"
            "---\n"
            "Agent prompt body.\n"
        )
        v2 = oc_harness.render_agent(text, 2)
        self.assertIn("  edit:\n", v2)
        self.assertIn('    "*": deny\n', v2)
        self.assertIn('    ".audit/**": allow', v2)
        self.assertNotIn("edit: allow", v2)

    def test_render_agent_write_paths_no_unrestricted_edit_allow_v1(self):
        text = (
            "---\n"
            "description: Scoped agent\n"
            "model: flash\n"
            "effort: high\n"
            "access: write\n"
            "write_paths: .audit/**\n"
            "bash: false\n"
            "web: false\n"
            "---\n"
            "Agent prompt body.\n"
        )
        v1 = oc_harness.render_agent(text, 1)
        self.assertNotIn("edit: allow", v1)
        self.assertIn("edit:", v1)
        self.assertIn('"*": deny', v1)
        self.assertIn('".audit/**": allow', v1)

    def test_rca_sources_scope_edit_and_deny_task_v1_and_v2(self):
        base = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "requirements-code-audit-glm", "opencode", "agents",
        )
        for fname in ("rca-investigator.md", "rca-verifier.md"):
            with open(os.path.join(base, fname)) as fh:
                text = fh.read()
            fields, _ = oc_harness.parse_frontmatter(text)
            self.assertEqual(fields.get("write_paths"), ".audit/**")
            v1 = oc_harness.render_agent(text, 1)
            self.assertNotIn("edit: allow", v1)
            self.assertIn('".audit/**": allow', v1)
            self.assertIn("task: deny", v1)
            v2 = oc_harness.render_agent(text, 2)
            self.assertIn('    ".audit/**": allow', v2)
            self.assertIn('    "*": deny', v2)
            self.assertIn("  task: deny", v2)
            self.assertNotIn("edit: allow", v2)

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
