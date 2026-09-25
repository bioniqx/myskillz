import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import oc_harness

AUDIT_MD = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "requirements-code-audit-glm",
    "opencode",
    "commands",
    "audit.md",
)


class TestAuditCommand(unittest.TestCase):
    def _render(self):
        with open(AUDIT_MD, "r") as fh:
            text = fh.read()
        return oc_harness.render_command(text, 1, "/home/user/.config/opencode/skills/requirements-code-audit")

    def test_body_mentions_loading_the_skill_and_keeps_arguments(self):
        rendered = self._render()
        self.assertIn("Load the requirements-code-audit skill", rendered)
        self.assertIn("$ARGUMENTS", rendered)

    def test_first_step_is_audit_brief_spec_no_bare_arguments_line(self):
        rendered = self._render()
        body_lines = rendered.split("\n")
        step_lines = [line for line in body_lines if "audit.py" in line]
        self.assertTrue(step_lines, "expected at least one audit.py reference")
        self.assertIn("audit.py brief --spec", step_lines[0])
        for line in body_lines:
            stripped = line.strip()
            self.assertNotEqual(
                stripped,
                "python3 {}/scripts/audit.py $ARGUMENTS".format(
                    "/home/user/.config/opencode/skills/requirements-code-audit"
                ),
            )
            self.assertFalse(
                stripped.endswith("audit.py $ARGUMENTS"),
                "found bare 'audit.py $ARGUMENTS' line: {!r}".format(line),
            )

    def test_skill_dir_placeholder_fully_replaced(self):
        rendered = self._render()
        self.assertNotIn("{{SKILL_DIR}}", rendered)


if __name__ == "__main__":
    unittest.main()
