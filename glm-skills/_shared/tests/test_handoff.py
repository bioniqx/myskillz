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


class CallTests(unittest.TestCase):
    def test_doc_generator_can_call_debugging(self):
        rc, out = run(
            ["call", "--self", "glm-doc-generator", "--to", "glm-systematic-debugging",
             "--why", "the docs found a defect"],
            "")
        self.assertEqual(rc, 0)
        self.assertIn("HANDOFF glm-systematic-debugging", out)
        self.assertIn("TELL: $glm-systematic-debugging", out)
        self.assertIn("the docs found a defect", out)
        self.assertIn("RESULT call action=handoff name=glm-systematic-debugging", out)

    def test_call_outside_the_ring_stays(self):
        _rc, out = run(["call", "--self", "glm-dev-team", "--to", "glm-idea-to-spec"])
        self.assertIn("STAY glm-dev-team", out)
        self.assertIn("outside the seven-skill ring", out)
        self.assertIn("RESULT call action=stay", out)

    def test_call_respects_the_cap(self):
        _rc, out = run(
            ["call", "--self", "glm-doc-generator", "--to", "glm-dev-team"],
            "From: glm-brainstorming,glm-writing-plans\n")
        self.assertIn("STOP cap", out)

    def test_call_refuses_a_cycle(self):
        _rc, out = run(
            ["call", "--self", "glm-dev-team", "--to", "glm-brainstorming"],
            "From: glm-brainstorming\n")
        self.assertIn("STAY glm-dev-team", out)
        self.assertIn("already in this chain", out)

    def test_idea_to_spec_cannot_use_call(self):
        rc, out = run(["call", "--self", "glm-idea-to-spec", "--to", "glm-dev-team"])
        self.assertEqual(rc, 2)
        self.assertIn("RESULT call action=stop name=usage", out)


class BorrowTests(unittest.TestCase):
    def test_agents_lists_borrow_and_engine(self):
        rc, out = run(["agents"])
        self.assertEqual(rc, 0)
        self.assertIn("BORROW glm-explorer owner=glm-brainstorming", out)
        self.assertIn("ENGINE glm-programmer-lite owner=glm-dev-team", out)
        self.assertIn("RESULT agents borrow=", out)

    def test_borrow_prints_a_dispatch(self):
        rc, out = run(["borrow", "--self", "glm-writing-plans", "--agent", "glm-explorer"])
        self.assertEqual(rc, 0)
        self.assertIn("AGENT glm-explorer", out)
        self.assertIn("SUBAGENT_TYPE glm-explorer", out)
        self.assertIn("PROMPT:", out)
        self.assertIn("Question:", out)
        self.assertIn("RESULT borrow action=agent name=glm-explorer", out)
        self.assertFalse(any(line.startswith("HANDOFF ") for line in out.splitlines()))

    def test_engine_agent_hands_off_to_its_owner(self):
        rc, out = run(
            ["borrow", "--self", "glm-doc-generator", "--agent", "glm-programmer-strong"])
        self.assertEqual(rc, 0)
        self.assertIn("HANDOFF glm-dev-team", out)
        self.assertIn("RESULT borrow action=handoff name=glm-dev-team", out)
        self.assertNotIn("AGENT glm-programmer-strong", out)

    def test_owner_does_not_borrow_its_own_agent(self):
        _rc, out = run(["borrow", "--self", "glm-dev-team", "--agent", "glm-programmer-lite"])
        self.assertIn("STAY glm-dev-team", out)
        self.assertIn("you own glm-programmer-lite", out)

    def test_unknown_agent_lists_names(self):
        _rc, out = run(["borrow", "--self", "glm-brainstorming", "--agent", "glm-nope"])
        self.assertIn("unknown agent", out)
        self.assertIn("glm-rca-verifier", out)
        self.assertIn("RESULT borrow action=stay", out)


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
