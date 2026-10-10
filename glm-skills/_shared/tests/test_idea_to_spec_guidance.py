import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..", "..", "glm-idea-to-spec", "SKILL.md")


def _skill_text():
    with open(SKILL, encoding="utf-8") as fh:
        return fh.read()


class DetailedBriefCollapseTests(unittest.TestCase):
    """Rule (a): a detailed opening brief collapses the interview into one round."""

    def test_opening_brief_answers_phase_0_2_collapses_to_one_round(self):
        text = _skill_text()
        self.assertIn("already answers the Phase 0-2 questions", text)
        self.assertIn("target users, goal, success criteria", text)
        self.assertIn("collapse the remaining questions into ONE batched question round", text)
        self.assertIn("one numbered chat list", text)
        self.assertIn("then move to Phase 3", text)


class ResearchBatchingTests(unittest.TestCase):
    """Rule (b): query variants are batched in one message without a subagent tool."""

    def test_query_variants_batched_in_one_message_without_a_task_tool(self):
        text = _skill_text()
        self.assertIn("With no subagent tool", text)
        self.assertIn("query variants", text)
        self.assertIn("one message of web search and fetch calls", text)
        self.assertIn("never one query per turn", text)


class UnchangedGuidanceTests(unittest.TestCase):
    """Guards: verdict-before-spec order, fast mode and frontmatter stay unchanged."""

    def test_verdict_still_precedes_the_spec(self):
        text = _skill_text()
        self.assertIn("BEFORE writing the spec", text)
        self.assertLess(text.index("Verdict & path to money"), text.index("Write the spec"))

    def test_fast_mode_still_defined(self):
        text = _skill_text()
        self.assertIn("**Fast mode**", text)
        self.assertIn("one research sweep + one round", text)

    def test_frontmatter_name_and_description_limit(self):
        text = _skill_text()
        head = text.split("---\n")[1]
        fields = {}
        for line in head.splitlines():
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
        self.assertEqual(fields["name"], "glm-idea-to-spec")
        self.assertLessEqual(len(fields["description"]), 1024)


if __name__ == "__main__":
    unittest.main()
