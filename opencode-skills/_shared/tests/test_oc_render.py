import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import oc_harness


class TestOcHarnessRender(unittest.TestCase):
    def test_detect_returns_major_from_version_output(self):
        tmpdir = tempfile.mkdtemp()
        fake_bin = os.path.join(tmpdir, "opencode")
        with open(fake_bin, "w") as f:
            f.write("#!/bin/sh\necho '2.0.20'\n")
        os.chmod(fake_bin, 0o755)
        try:
            self.assertEqual(oc_harness.detect(fake_bin), 2)
        finally:
            import shutil
            shutil.rmtree(tmpdir)

    def test_detect_returns_none_for_missing_binary(self):
        self.assertEqual(oc_harness.detect("/nonexistent/path/opencode-missing"), 0)

    def test_detect_returns_zero_on_timeout_instead_of_raising(self):
        import subprocess
        with mock.patch("oc_harness.subprocess.run",
                        side_effect=subprocess.TimeoutExpired(cmd="opencode", timeout=10)):
            self.assertEqual(oc_harness.detect("opencode"), 0)

    def test_parse_frontmatter_extracts_fields_and_body(self):
        text = (
            "---\n"
            "description: Test agent\n"
            "bash: true\n"
            "web: false\n"
            "steps: 5\n"
            "---\n"
            "You are a test agent.\n"
        )
        fields, body = oc_harness.parse_frontmatter(text)
        self.assertEqual(fields["description"], "Test agent")
        self.assertIs(fields["bash"], True)
        self.assertIs(fields["web"], False)
        self.assertEqual(fields["steps"], 5)
        self.assertEqual(body, "You are a test agent.")

    def test_parse_frontmatter_unquotes_value_with_embedded_colon(self):
        fields, _ = oc_harness.parse_frontmatter('---\ndescription: "a: b"\n---\nbody\n')
        self.assertEqual(fields["description"], "a: b")


class TestRenderAgent(unittest.TestCase):
    SOURCE = (
        "---\n"
        "description: Test agent\n"
        "model: pro\n"
        "variant: max\n"
        "effort: max\n"
        "reasoningEffort: max\n"
        "access: read\n"
        "bash: false\n"
        "web: true\n"
        "steps: 2\n"
        "temperature: 0.2\n"
        "---\n"
        "Agent prompt body.\n"
    )

    def test_writes_no_model_variant_or_effort_line(self):
        out = oc_harness.render_agent(self.SOURCE, 2)
        for key in ("model:", "variant:", "effort:", "reasoningEffort", "reasoning_effort", "options:"):
            self.assertNotIn(key, out)

    def test_v2_dialect_fields(self):
        out = oc_harness.render_agent(self.SOURCE, 2)
        self.assertTrue(out.startswith("---\n"))
        self.assertIn('description: "Test agent"', out)
        self.assertIn("mode: subagent", out)
        self.assertIn("hidden: true", out)
        self.assertIn("steps: 2", out)
        self.assertIn("temperature: 0.2", out)
        self.assertNotIn("    temperature: 0.2", out)
        self.assertNotIn("mode: all", out)
        self.assertIn("permission:", out)
        self.assertNotIn("permissions:", out)
        self.assertIn("  edit: deny", out)
        self.assertIn("  bash: deny", out)
        self.assertIn("  webfetch: allow", out)
        self.assertIn("  websearch: allow", out)
        self.assertIn("  execute: deny", out)
        self.assertTrue(out.endswith("Agent prompt body."))

    def test_write_access_and_web_off(self):
        text = self.SOURCE.replace("access: read", "access: write").replace(
            "bash: false", "bash: true").replace("web: true", "web: false")
        out = oc_harness.render_agent(text, 2)
        self.assertIn("  edit: allow", out)
        self.assertIn("  bash: allow", out)
        self.assertIn("  webfetch: deny", out)
        self.assertIn("  websearch: deny", out)
        self.assertIn("  execute: deny", out)

    def test_rejects_every_major_but_two(self):
        for major in (0, 1, 3):
            with self.assertRaisesRegex(ValueError, "OpenCode v2 required"):
                oc_harness.render_agent(self.SOURCE, major)

    def test_quoted_description_keeps_its_colon(self):
        out = oc_harness.render_agent('---\ndescription: "a: b"\n---\nbody\n', 2)
        self.assertIn('description: "a: b"', out)
        self.assertNotIn('\\"a: b\\"', out)

    def test_write_paths_scopes_edit(self):
        text = (
            "---\n"
            "description: Scoped agent\n"
            "access: write\n"
            "write_paths: .oc-audit/**\n"
            "bash: false\n"
            "web: false\n"
            "---\n"
            "Agent prompt body.\n"
        )
        out = oc_harness.render_agent(text, 2)
        self.assertIn("  edit:\n", out)
        self.assertIn('    "*": deny\n', out)
        self.assertIn('    ".oc-audit/**": allow', out)
        self.assertIn("  task: deny", out)
        self.assertNotIn("edit: allow", out)

    def test_audit_agent_sources_scope_edit_and_deny_task(self):
        base = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "oc-requirements-code-audit", "opencode", "agents",
        )
        for fname in ("oc-rca-investigator.md", "oc-rca-verifier.md"):
            with open(os.path.join(base, fname)) as fh:
                text = fh.read()
            fields, _ = oc_harness.parse_frontmatter(text)
            self.assertEqual(fields.get("write_paths"), "**/.oc-audit/**")
            out = oc_harness.render_agent(text, 2)
            self.assertIn('    "**/.oc-audit/**": allow', out)
            self.assertIn('    "*": deny', out)
            self.assertIn("  task: deny", out)
            self.assertNotIn("edit: allow", out)
            self.assertNotIn("model:", out)


class TestRenderCommand(unittest.TestCase):
    def test_replaces_skill_dir_and_keeps_arguments(self):
        text = (
            "---\n"
            "description: Run the debug skill\n"
            "---\n"
            "!{{SKILL_DIR}}/scripts/oc-context.sh\n"
            "load skill with $ARGUMENTS\n"
        )
        rendered = oc_harness.render_command(
            text, 2, "/home/user/.config/opencode/skills/oc-systematic-debugging"
        )
        self.assertIn('description: "Run the debug skill"', rendered)
        self.assertIn(
            "/home/user/.config/opencode/skills/oc-systematic-debugging/scripts/oc-context.sh",
            rendered,
        )
        self.assertIn("$ARGUMENTS", rendered)
        self.assertNotIn("{{SKILL_DIR}}", rendered)

    def test_rejects_every_major_but_two(self):
        for major in (0, 1, 3):
            with self.assertRaisesRegex(ValueError, "OpenCode v2 required"):
                oc_harness.render_command("---\ndescription: d\n---\nbody\n", major, "/x")


class TestNoProviderMachinery(unittest.TestCase):
    def test_source_defines_none_of_the_removed_names(self):
        with open(oc_harness.__file__) as fh:
            source = fh.read()
        for name in ("PROVIDER", "MODELS", "EFFORTS", "config_snippet", "WEBSEARCH_NOTE",
                     "probe_effort", "PROBE_AGENT", "PROBE_BRIEF", "NON_OC_AGENTS", "DEVTEAM_HARNESS"):
            self.assertNotIn(name, source)
        for name in ("PROVIDER", "MODELS", "EFFORTS", "config_snippet", "probe_effort"):
            self.assertFalse(hasattr(oc_harness, name), name)


if __name__ == "__main__":
    unittest.main()
