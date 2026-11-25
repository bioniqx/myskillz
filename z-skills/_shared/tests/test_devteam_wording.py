"""Spec 2026-11-25: the dev-team engine's routing text follows the session model.

Source-text guards. No agent file pins a model, so the engine must neither
print nor document a pinned model. The behavior behind the text is covered by
the other dev-team modules and by scripts/selftest.sh."""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "..", "..", "z-dev-team", "scripts", "devteam.py")
SELFTEST = os.path.join(HERE, "..", "..", "z-dev-team", "scripts", "selftest.sh")
SKILL = os.path.join(HERE, "..", "..", "z-dev-team", "SKILL.md")
PLAN = os.path.join(HERE, "..", "..", "z-dev-team", "references", "plan.md")

STALE = (
    "tuned for ZCode on Z.ai GLM-5.3-Flash",
    "pinned in the agents' own frontmatter",
    "pinned in the agents' frontmatter",
    "effort is max on every agent",
    "thoughtLevel is ignored unless that model id is present",
    "(GLM-5.3-Flash, thoughtLevel max)",
    "frontmatter pins it",
    "Flash atom call",
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class EngineRoutingText(unittest.TestCase):
    def test_engine_carries_no_stale_pinned_model_wording(self):
        text = _read(ENGINE)
        for stale in STALE:
            with self.subTest(stale=stale):
                self.assertNotIn(stale, text)

    def test_provider_line_names_the_session_model_and_no_pinned_model(self):
        lines = _read(ENGINE).splitlines()
        starts = [i for i, ln in enumerate(lines) if 'out(f"PROVIDER {PROVIDERS[provider]' in ln]
        self.assertEqual(len(starts), 1, "expected exactly one PROVIDER line")
        statement = "\n".join(lines[starts[0]:starts[0] + 2])
        self.assertIn("every lane follows the session model", statement)
        self.assertIn("every RED dispatch", statement)
        self.assertNotIn("GLM-5.3-Flash", statement)
        self.assertNotIn("frontmatter", statement)


class SkillLaneText(unittest.TestCase):
    """The lane text says what dispatch_route does: RED, high-risk, large and
    retried dispatches take the strong lane, every other dispatch the lite lane."""

    def test_lite_row_covers_every_dispatch_the_engine_sends_there(self):
        rows = [line for line in _read(SKILL).splitlines()
                if line.lstrip().startswith("| `z-programmer-lite` |")]
        self.assertEqual(len(rows), 1, "expected one z-programmer-lite row")
        for words in ("neither RED nor strong", "first GREEN of a code slice",
                      "test, refactor, chore, docs or perf slice"):
            self.assertIn(words, rows[0])

    def test_docs_row_names_every_escalation_to_the_strong_lane(self):
        rows = [line for line in _read(PLAN).splitlines()
                if line.startswith("| `docs` |")]
        self.assertEqual(len(rows), 1, "expected one docs row")
        for words in ("`size: large`", "`risk: high`", "retried"):
            self.assertIn(words, rows[0])


class SelftestLabels(unittest.TestCase):
    def test_selftest_check_labels_name_no_pinned_model(self):
        text = _read(SELFTEST)
        self.assertNotIn("(GLM-5.3-Flash, thoughtLevel max)", text)
        self.assertNotIn("strong lane (GLM-5.3-Flash)", text)


if __name__ == "__main__":
    unittest.main()
