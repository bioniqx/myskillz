import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import oc_harness

SKILL_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "brainstorming-glm"
)
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
EXPLORER_MD = os.path.join(SKILL_DIR, "opencode", "agents", "explorer.md")
RESEARCHER_MD = os.path.join(SKILL_DIR, "opencode", "agents", "researcher.md")
BRAINSTORM_MD = os.path.join(SKILL_DIR, "opencode", "commands", "brainstorm.md")

PLACEHOLDERS = ("[TASK", "[ROOT", "[SLICE", "[ONE precise question]")


def read(path):
    with open(path) as f:
        return f.read()


class TestBrainstormOcSkillMd(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL_MD)

    def test_gives_exact_run_command(self):
        self.assertRegex(self.text, r'oc_harness\.py"? run <lanes\.json>')

    def test_resolver_checks_for_oc_harness_script(self):
        self.assertIn("scripts/oc_harness.py", self.text)

    def test_gives_lane_fields(self):
        for field in ("id", "agent", "model", "dir", "brief"):
            self.assertIn("`%s`" % field, self.text)

    def test_states_what_brief_contains(self):
        self.assertIn("brief", self.text.lower())
        self.assertIn("task", self.text.lower())
        self.assertIn("question", self.text.lower())

    def test_states_where_and_how_lane_output_is_read(self):
        self.assertIn(".jsonl", self.text)
        self.assertIn(".oc-lanes", self.text)

    def test_states_task_tool_is_only_fallback(self):
        idx = self.text.find("`task`")
        self.assertNotEqual(idx, -1, "no `task` mention found")
        window = self.text[max(0, idx - 200):idx + 200]
        self.assertIn("fallback", window.lower())
        self.assertIn("unavailable", window.lower())

    def test_line_2_is_still_name_brainstorming(self):
        lines = self.text.split("\n")
        self.assertEqual(lines[1], "name: brainstorming")

    def test_allowed_tools_unchanged(self):
        expected = (
            "allowed-tools:\n"
            '  - Bash(sh "${CLAUDE_SKILL_DIR}/scripts/context.sh")\n'
            "  - Read\n"
            "  - Grep\n"
            "  - Glob\n"
            "  - WebSearch\n"
            "  - WebFetch\n"
        )
        self.assertIn(expected, self.text)

    def test_preload_line_unchanged(self):
        self.assertIn('!`sh "${CLAUDE_SKILL_DIR}/scripts/context.sh"`', self.text)


class TestBrainstormOcAgentBodies(unittest.TestCase):
    def test_explorer_body_has_no_placeholders(self):
        text = read(EXPLORER_MD)
        _, body = oc_harness.parse_frontmatter(text)
        for placeholder in PLACEHOLDERS:
            self.assertNotIn(placeholder, body)

    def test_explorer_body_keeps_output_labels(self):
        text = read(EXPLORER_MD)
        _, body = oc_harness.parse_frontmatter(text)
        self.assertIn("FINDINGS:", body)
        self.assertIn("PATTERNS:", body)
        self.assertIn("RISKS:", body)
        self.assertIn("UNKNOWN:", body)

    def test_researcher_body_has_no_placeholders(self):
        text = read(RESEARCHER_MD)
        _, body = oc_harness.parse_frontmatter(text)
        for placeholder in PLACEHOLDERS:
            self.assertNotIn(placeholder, body)

    def test_researcher_body_keeps_output_labels(self):
        text = read(RESEARCHER_MD)
        _, body = oc_harness.parse_frontmatter(text)
        self.assertIn("ANSWER:", body)
        self.assertIn("CLAIMS:", body)
        self.assertIn("CONFLICTS:", body)
        self.assertIn("VERSION_NOTES:", body)
        self.assertIn("UNVERIFIED:", body)


class TestBrainstormOcRenderedDescriptions(unittest.TestCase):
    def test_explorer_rendered_description_starts_with_letter(self):
        rendered = oc_harness.render_agent(read(EXPLORER_MD), 2)
        match = re.search(r'description: (".*")', rendered)
        self.assertIsNotNone(match)
        value = json.loads(match.group(1))
        self.assertRegex(value, r"^[A-Za-z]")
        self.assertFalse(value.startswith('\\"'))

    def test_researcher_rendered_description_starts_with_letter(self):
        rendered = oc_harness.render_agent(read(RESEARCHER_MD), 2)
        match = re.search(r'description: (".*")', rendered)
        self.assertIsNotNone(match)
        value = json.loads(match.group(1))
        self.assertRegex(value, r"^[A-Za-z]")
        self.assertFalse(value.startswith('\\"'))

    def test_brainstorm_command_rendered_description_starts_with_letter(self):
        rendered = oc_harness.render_command(read(BRAINSTORM_MD), 2, "/tmp/skill")
        match = re.search(r'description: (".*")', rendered)
        self.assertIsNotNone(match)
        value = json.loads(match.group(1))
        self.assertRegex(value, r"^[A-Za-z]")
        self.assertFalse(value.startswith('\\"'))


if __name__ == "__main__":
    unittest.main()
