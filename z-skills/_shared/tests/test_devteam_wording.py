"""Spec 2026-11-25: the dev-team engine's routing text follows the session model.

Source-text guards. No agent file pins a model, so the engine must neither
print nor document a pinned model. The behavior behind the text is covered by
the other dev-team modules and by scripts/selftest.sh."""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "..", "..", "z-dev-team", "scripts", "devteam.py")
SELFTEST = os.path.join(HERE, "..", "..", "z-dev-team", "scripts", "selftest.sh")

STALE = (
    "tuned for ZCode on Z.ai GLM-5.3-Flash",
    "pinned in the agents' own frontmatter",
    "pinned in the agents' frontmatter",
    "effort is max on every agent",
    "thoughtLevel is ignored unless that model id is present",
    "(GLM-5.3-Flash, thoughtLevel max)",
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
        self.assertNotIn("GLM-5.3-Flash", statement)
        self.assertNotIn("frontmatter", statement)


class SelftestLabels(unittest.TestCase):
    def test_selftest_check_labels_name_no_pinned_model(self):
        text = _read(SELFTEST)
        self.assertNotIn("(GLM-5.3-Flash, thoughtLevel max)", text)
        self.assertNotIn("strong lane (GLM-5.3-Flash)", text)


if __name__ == "__main__":
    unittest.main()
