"""Audit 2026-11-25: the idea-to-spec money gate accepts the skill's own template.

A bare count (10k users) is not a money figure. A price or a percentage still needs a source,
a label (ASSUMPTION, ESTIMATE, UNVERIFIED) or the TARGET marker."""
import importlib.util
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "..", "z-idea-to-spec", "scripts", "check_spec.py")
TEMPLATE = os.path.join(HERE, "..", "..", "z-idea-to-spec", "references", "spec-template.md")


def _load():
    spec = importlib.util.spec_from_file_location("idea_check_spec_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


check_spec = _load()
VERDICT = "## Verdict\nBUILD\n"


class MoneyGateTests(unittest.TestCase):
    def test_the_skill_own_template_passes_its_gate(self):
        proc = subprocess.run([sys.executable, SCRIPT, TEMPLATE], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("RESULT spec fail=0", proc.stdout)

    def test_a_bare_count_is_not_a_money_figure(self):
        text = VERDICT + "| Capacity | 10k users, 1.2M rows, 3 billion requests |\n"
        self.assertEqual(check_spec.lint(text), [])

    def test_an_unsourced_price_still_fails(self):
        fails = check_spec.lint(VERDICT + "- Price: $19/mo\n")
        self.assertEqual(len(fails), 1, fails)
        self.assertIn("FAIL money", fails[0])

    def test_an_unsourced_percentage_needs_a_source_or_the_target_marker(self):
        self.assertIn("FAIL money", check_spec.lint(VERDICT + "| Availability | 99.9% uptime |\n")[0])
        self.assertEqual(check_spec.lint(VERDICT + "| Availability | TARGET 99.9% uptime |\n"), [])
        self.assertEqual(check_spec.lint(VERDICT + "| Growth | 20% MoM (ASSUMPTION) |\n"), [])
        self.assertEqual(
            check_spec.lint(VERDICT + "| Growth | 20% MoM, see https://example.org/metrics |\n"), [])

    def test_a_missing_verdict_still_fails(self):
        fails = check_spec.lint("No verdict here.\n")
        self.assertTrue(fails and "FAIL verdict" in fails[0], fails)


if __name__ == "__main__":
    unittest.main()
