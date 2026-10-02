"""Text checks for the brainstorming files: hand-off, section references, round 1, commit, lane models."""
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent / "claude-brainstorming-6.3"


def read(name):
    return (SKILL_DIR / name).read_text(encoding="utf-8")


def norm(name):
    return " ".join(read(name).split())


class HandoffNameTests(unittest.TestCase):
    def test_skill_names_versioned_handoff(self):
        text = norm("SKILL.md")
        self.assertIn("The ONLY skill you invoke next is `claude-writing-plans-6.2` (fallback `claude-writing-plans`).", text)
        self.assertIn("review gate → claude-writing-plans-6.2.", text)

    def test_architectural_names_versioned_handoff_with_fallback(self):
        text = norm("architectural.md")
        self.assertIn("lane results to `claude-writing-plans-6.2`.", text)
        self.assertIn(
            "Invoke `claude-writing-plans-6.2`; if no skill with that exact name is installed, invoke `claude-writing-plans`.",
            text,
        )


class SectionReferenceTests(unittest.TestCase):
    def test_claim_verifier_is_cited_at_section_3(self):
        arch = read("architectural.md")
        section3 = arch[arch.index("## 3. "):arch.index("## 4. ")]
        self.assertIn("Claim verifier", section3)
        research = norm("research-playbook.md")
        self.assertIn("(`architectural.md` §3)", research)
        self.assertNotIn("(`architectural.md` §4)", research)


class RoundOneTests(unittest.TestCase):
    def test_round_one_loads_deferred_tools_before_calling_them(self):
        text = norm("SKILL.md")
        round1 = text[text.index("Round 1 = "):text.index("Round 2 = ")]
        self.assertIn("ToolSearch", round1)
        self.assertIn("only if those tools are already loaded", round1)
        self.assertNotIn("all web searches", round1)
        round2 = text[text.index("Round 2 = "):text.index("Round 3 = ")]
        self.assertIn("had to load first", round2)


class SpecCommitTests(unittest.TestCase):
    def test_architectural_commit_is_conditional(self):
        text = norm("architectural.md")
        self.assertIn(
            "only when neither the user nor a loaded project or user instruction file says not to commit",
            text,
        )
        self.assertIn("otherwise leave the spec untracked", text)
        self.assertIn("Spec written to `<path>` (not committed", text)
        self.assertIn("commit if committing", text)

    def test_skill_commit_is_conditional(self):
        text = norm("SKILL.md")
        self.assertIn("conditional commit", text)
        self.assertIn("+ commit if allowed (one turn)", text)


class LaneModelTests(unittest.TestCase):
    def test_code_lane_and_spec_predraft_name_a_model(self):
        skill = norm("SKILL.md")
        self.assertIn('**Code lane** (`subagent_type: "Explore"` with `model: "haiku"`', norm("lanes.md"))
        self.assertIn("Pass `model` explicitly: `sonnet` for lanes", skill)
        arch = norm("architectural.md")
        self.assertIn('otherwise `general-purpose` with `model: "sonnet"` and the design pasted.', arch)
