"""Router shared by every glm skill. The script's lines are binding."""
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HANDOFF = os.path.join(HERE, "..", "handoff.py")
CHECK_SPEC = os.path.join(HERE, "..", "..", "glm-idea-to-spec", "scripts", "check_spec.py")


def run(args, stdin=""):
    proc = subprocess.run(
        [sys.executable, HANDOFF] + args,
        input=stdin, capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stdout


class RouteTests(unittest.TestCase):
    def test_feature_stays_in_brainstorming(self):
        rc, out = run(["route", "--self", "glm-brainstorming"],
                      "add a login endpoint to the existing api")
        self.assertEqual(rc, 0)
        self.assertIn("STAY glm-brainstorming", out)
        self.assertIn("RESULT route action=stay", out)
        self.assertIn("GUARD cite:", out)

    def test_traceback_leaves_brainstorming(self):
        rc, out = run(["route", "--self", "glm-brainstorming"],
                      "the login tests fail with a traceback")
        self.assertEqual(rc, 0)
        self.assertIn("HANDOFF glm-systematic-debugging", out)
        self.assertIn("TELL: $glm-systematic-debugging", out)
        self.assertIn("FROM-LINE: From: glm-brainstorming,glm-systematic-debugging", out)

    def test_same_bug_stays_in_debugging(self):
        _rc, out = run(["route", "--self", "glm-systematic-debugging"],
                       "the login tests fail with a traceback")
        self.assertIn("STAY glm-systematic-debugging", out)

    def test_dev_team_keeps_a_fix_and_hands_off_a_bare_failure(self):
        _rc, stay = run(["route", "--self", "glm-dev-team"], "fix the failing test in login")
        self.assertIn("STAY glm-dev-team", stay)
        _rc, go = run(["route", "--self", "glm-dev-team"],
                      "the login tests fail with a traceback")
        self.assertIn("HANDOFF glm-systematic-debugging", go)

    def test_docs_skill_bounces_a_feature(self):
        _rc, out = run(["route", "--self", "glm-doc-generator"], "add a login endpoint")
        self.assertIn("HANDOFF glm-brainstorming", out)

    def test_docs_skill_keeps_a_readme(self):
        _rc, out = run(["route", "--self", "glm-doc-generator"], "please update the README")
        self.assertIn("STAY glm-doc-generator", out)

    def test_readme_plus_feature_stays_in_brainstorming(self):
        _rc, out = run(["route", "--self", "glm-brainstorming"],
                       "add a settings page and update the readme")
        self.assertIn("STAY glm-brainstorming", out)

    def test_cycle_stays(self):
        _rc, out = run(
            ["route", "--self", "glm-dev-team"],
            "From: glm-brainstorming,glm-systematic-debugging\n"
            "the login tests fail with a traceback")
        self.assertIn("STAY glm-dev-team", out)
        self.assertIn("already in this chain", out)

    def test_third_skill_cannot_hand_off_again(self):
        _rc, out = run(
            ["route", "--self", "glm-doc-generator"],
            "From: glm-brainstorming,glm-dev-team\nwrite a commit message")
        self.assertIn("STOP cap", out)
        self.assertIn("RESULT route action=stop name=cap", out)

    def test_no_bugs_stays(self):
        _rc, out = run(["route", "--self", "glm-brainstorming"],
                       "confirm there are no bugs in the export")
        self.assertIn("STAY glm-brainstorming", out)


class NextTests(unittest.TestCase):
    def test_plan_ready_goes_to_dev_team(self):
        rc, out = run(["next", "--self", "glm-writing-plans", "--event", "plan-ready"])
        self.assertEqual(rc, 0)
        self.assertIn("HANDOFF glm-dev-team", out)
        self.assertIn("RESULT next action=handoff name=glm-dev-team", out)

    def test_unknown_event_stays_and_lists_events(self):
        _rc, out = run(["next", "--self", "glm-writing-plans", "--event", "ship-it"])
        self.assertIn("STAY glm-writing-plans", out)
        self.assertIn("plan-ready", out)
        self.assertIn("RESULT next action=stay", out)

    def test_exit_respects_the_cap(self):
        _rc, out = run(
            ["next", "--self", "glm-writing-plans", "--event", "plan-ready"],
            "From: glm-brainstorming,glm-idea-to-spec\n")
        self.assertIn("STOP cap", out)


class SpecLintTests(unittest.TestCase):
    def write(self, text):
        fh = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        fh.write(textwrap.dedent(text))
        fh.close()
        self.addCleanup(os.remove, fh.name)
        return fh.name

    def lint(self, path):
        proc = subprocess.run(
            [sys.executable, CHECK_SPEC, path],
            capture_output=True, text=True, timeout=30)
        return proc.returncode, proc.stdout

    def test_sourced_price_passes(self):
        path = self.write("""
            Verdict: BUILD WITH CHANGES
            Competitors charge $19/mo - https://example.com/pricing (2026-10-01)
        """)
        rc, out = self.lint(path)
        self.assertEqual(rc, 0, out)

    def test_bare_price_fails(self):
        path = self.write("""
            Verdict: BUILD
            The market is $4 billion and growing 20% a year.
        """)
        rc, out = self.lint(path)
        self.assertEqual(rc, 1)
        self.assertIn("FAIL money", out)

    def test_labeled_estimate_passes(self):
        path = self.write("""
            DON'T BUILD AS-IS
            Revenue year one is $50k ESTIMATE (10 customers x $400).
        """)
        rc, out = self.lint(path)
        self.assertEqual(rc, 0, out)

    def test_missing_verdict_fails(self):
        path = self.write("A note with no decision.\n")
        rc, out = self.lint(path)
        self.assertEqual(rc, 1)
        self.assertIn("FAIL verdict", out)


if __name__ == "__main__":
    unittest.main()
