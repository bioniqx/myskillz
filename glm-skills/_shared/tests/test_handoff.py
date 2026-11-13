"""Router shared by every glm skill. The script's lines are binding."""
import os
import shutil
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


class OpenTests(unittest.TestCase):
    def run_at(self, args, stdin="", cwd=None, env=None):
        proc = subprocess.run(
            [sys.executable, HANDOFF] + args,
            input=stdin, capture_output=True, text=True, timeout=60,
            cwd=cwd, env=env)
        return proc.returncode, proc.stdout, proc.stderr

    def test_handoff_does_not_run_the_prelude(self):
        rc, out, _err = self.run_at(
            ["open", "--self", "glm-brainstorming"],
            "the login tests fail with a traceback")
        self.assertEqual(rc, 0)
        self.assertIn("HANDOFF glm-systematic-debugging", out)
        self.assertIn("OPEN: routed", out)
        self.assertNotIn("=== PRELUDE ===", out)
        self.assertNotIn("MODE ", out)

    def test_brainstorm_stay_runs_context_and_asks_mode(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        rc, out, err = self.run_at(
            ["open", "--self", "glm-brainstorming"],
            "add a login endpoint to the existing api", cwd=root)
        self.assertEqual(rc, 0, err)
        self.assertIn("STAY glm-brainstorming", out)
        self.assertIn("=== PRELUDE ===", out)
        self.assertIn("skill_dir:", out)
        self.assertIn("MODE ask", out)
        self.assertIn("Do not launch lanes", out)
        self.assertIn("OPEN: stay", out)
        self.assertFalse(os.path.exists(os.path.join(root, ".brainstorm")))

    def test_dev_team_stay_prints_scripts_dir(self):
        rc, out, _err = self.run_at(
            ["open", "--self", "glm-dev-team"], "fix the failing test in login")
        self.assertEqual(rc, 0)
        self.assertIn("D=", out)
        self.assertIn("glm-dev-team/scripts", out.replace("\\", "/"))
        self.assertIn("one engine call", out)

    def test_debug_stay_prints_s_and_does_not_probe(self):
        rc, out, _err = self.run_at(
            ["open", "--self", "glm-systematic-debugging"],
            "the login tests fail with a traceback")
        self.assertEqual(rc, 0)
        self.assertIn("S=", out)
        self.assertIn("debug_tool.py probe", out)
        self.assertNotIn("LANE:", out)

    def test_plans_without_spec_does_not_brief(self):
        rc, out, _err = self.run_at(
            ["open", "--self", "glm-writing-plans"],
            "write the implementation plan for the spec")
        self.assertEqual(rc, 0)
        self.assertIn("TOOL:", out)
        self.assertIn("plan_tool.py", out)
        self.assertIn("re-run open --spec", out)
        self.assertNotIn("=== SPEC", out)

    def test_bad_base_does_not_gather(self):
        rc, out, _err = self.run_at(
            ["open", "--self", "glm-git-diff-summary", "--base=-evil"],
            "summarize my changes vs main")
        self.assertEqual(rc, 0)
        self.assertIn("WARN_BASE_ARG_IGNORED", out)
        self.assertNotIn("MODE=", out)

    def test_doc_stay_runs_recon_in_the_given_cwd(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        with open(os.path.join(root, "hello.py"), "w", encoding="utf-8") as fh:
            fh.write("print('hi')\n")
        subprocess.run(["git", "add", "hello.py"], cwd=root, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t",
             "-c", "commit.gpgsign=false", "commit", "-q", "-m", "init"],
            cwd=root, check=True)
        state = os.path.join(root, "state")
        env = os.environ.copy()
        env["DOCGEN_STATE_DIR"] = state
        rc, out, err = self.run_at(
            ["open", "--self", "glm-doc-generator"],
            "please update the README", cwd=root, env=env)
        self.assertEqual(rc, 0, err)
        self.assertIn("OPEN: stay", out)
        self.assertIn("HEAD:", out)
        self.assertIn("hello.py", out)
        self.assertIn("Turn 2", out)

    def test_unknown_self_is_usage(self):
        rc, out, _err = self.run_at(["open", "--self", "glm-nope"], "hi")
        self.assertEqual(rc, 2)
        self.assertIn("RESULT open action=stop name=usage", out)


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
