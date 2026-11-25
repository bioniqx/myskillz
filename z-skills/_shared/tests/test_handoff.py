"""Router shared by every glm skill. The script's lines are binding."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
HANDOFF = os.path.join(HERE, "..", "handoff.py")
CHECK_SPEC = os.path.join(HERE, "..", "..", "z-idea-to-spec", "scripts", "check_spec.py")


def run(args, stdin=""):
    proc = subprocess.run(
        [sys.executable, HANDOFF] + args,
        input=stdin, capture_output=True, text=True, timeout=30)
    return proc.returncode, proc.stdout


class RouteTests(unittest.TestCase):
    def test_feature_stays_in_brainstorming(self):
        rc, out = run(["route", "--self", "z-brainstorming"],
                      "add a login endpoint to the existing api")
        self.assertEqual(rc, 0)
        self.assertIn("STAY z-brainstorming", out)
        self.assertIn("RESULT route action=stay", out)
        self.assertIn("GUARD cite:", out)
        self.assertIn("GUARD flash:", out)
        self.assertIn("deepseek-flash", out)
        self.assertIn("GUARD schema:", out)

    def test_traceback_leaves_brainstorming(self):
        rc, out = run(["route", "--self", "z-brainstorming"],
                      "the login tests fail with a traceback")
        self.assertEqual(rc, 0)
        self.assertIn("HANDOFF z-systematic-debugging", out)
        self.assertIn("TELL: $z-systematic-debugging", out)
        self.assertIn("FROM-LINE: From: z-brainstorming,z-systematic-debugging", out)

    def test_same_bug_stays_in_debugging(self):
        _rc, out = run(["route", "--self", "z-systematic-debugging"],
                       "the login tests fail with a traceback")
        self.assertIn("STAY z-systematic-debugging", out)

    def test_dev_team_keeps_a_fix_and_hands_off_a_bare_failure(self):
        _rc, stay = run(["route", "--self", "z-dev-team"], "fix the failing test in login")
        self.assertIn("STAY z-dev-team", stay)
        _rc, go = run(["route", "--self", "z-dev-team"],
                      "the login tests fail with a traceback")
        self.assertIn("HANDOFF z-systematic-debugging", go)

    def test_docs_skill_bounces_a_feature(self):
        _rc, out = run(["route", "--self", "z-doc-generator"], "add a login endpoint")
        self.assertIn("HANDOFF z-brainstorming", out)

    def test_docs_skill_keeps_a_readme(self):
        _rc, out = run(["route", "--self", "z-doc-generator"], "please update the README")
        self.assertIn("STAY z-doc-generator", out)

    def test_readme_plus_feature_stays_in_brainstorming(self):
        _rc, out = run(["route", "--self", "z-brainstorming"],
                       "add a settings page and update the readme")
        self.assertIn("STAY z-brainstorming", out)

    def test_cycle_stays(self):
        _rc, out = run(
            ["route", "--self", "z-dev-team"],
            "From: z-brainstorming,z-systematic-debugging\n"
            "the login tests fail with a traceback")
        self.assertIn("STAY z-dev-team", out)
        self.assertIn("already in this chain", out)

    def test_third_skill_cannot_hand_off_again(self):
        _rc, out = run(
            ["route", "--self", "z-doc-generator"],
            "From: z-brainstorming,z-dev-team\nwrite a commit message")
        self.assertIn("STOP cap", out)
        self.assertIn("RESULT route action=stop name=cap", out)

    def test_no_bugs_stays(self):
        _rc, out = run(["route", "--self", "z-brainstorming"],
                       "confirm there are no bugs in the export")
        self.assertIn("STAY z-brainstorming", out)


class NextTests(unittest.TestCase):
    def test_plan_ready_goes_to_dev_team(self):
        rc, out = run(["next", "--self", "z-writing-plans", "--event", "plan-ready"])
        self.assertEqual(rc, 0)
        self.assertIn("HANDOFF z-dev-team", out)
        self.assertIn("RESULT next action=handoff name=z-dev-team", out)

    def test_unknown_event_stays_and_lists_events(self):
        _rc, out = run(["next", "--self", "z-writing-plans", "--event", "ship-it"])
        self.assertIn("STAY z-writing-plans", out)
        self.assertIn("plan-ready", out)
        self.assertIn("RESULT next action=stay", out)

    def test_exit_respects_the_cap(self):
        _rc, out = run(
            ["next", "--self", "z-writing-plans", "--event", "plan-ready"],
            "From: z-brainstorming,z-idea-to-spec\n")
        self.assertIn("STOP cap", out)


class CallTests(unittest.TestCase):
    def test_doc_generator_can_call_debugging(self):
        rc, out = run(
            ["call", "--self", "z-doc-generator", "--to", "z-systematic-debugging",
             "--why", "the docs found a defect"],
            "")
        self.assertEqual(rc, 0)
        self.assertIn("HANDOFF z-systematic-debugging", out)
        self.assertIn("TELL: $z-systematic-debugging", out)
        self.assertIn("the docs found a defect", out)
        self.assertIn("RESULT call action=handoff name=z-systematic-debugging", out)

    def test_call_outside_the_ring_stays(self):
        _rc, out = run(["call", "--self", "z-dev-team", "--to", "z-idea-to-spec"])
        self.assertIn("STAY z-dev-team", out)
        self.assertIn("outside the seven-skill ring", out)
        self.assertIn("RESULT call action=stay", out)

    def test_call_respects_the_cap(self):
        _rc, out = run(
            ["call", "--self", "z-doc-generator", "--to", "z-dev-team"],
            "From: z-brainstorming,z-writing-plans\n")
        self.assertIn("STOP cap", out)

    def test_call_refuses_a_cycle(self):
        _rc, out = run(
            ["call", "--self", "z-dev-team", "--to", "z-brainstorming"],
            "From: z-brainstorming\n")
        self.assertIn("STAY z-dev-team", out)
        self.assertIn("already in this chain", out)

    def test_idea_to_spec_cannot_use_call(self):
        rc, out = run(["call", "--self", "z-idea-to-spec", "--to", "z-dev-team"])
        self.assertEqual(rc, 2)
        self.assertIn("RESULT call action=stop name=usage", out)


class BorrowTests(unittest.TestCase):
    def test_agents_lists_borrow_and_engine(self):
        rc, out = run(["agents"])
        self.assertEqual(rc, 0)
        self.assertIn("BORROW z-explorer owner=z-brainstorming", out)
        self.assertIn("ENGINE z-programmer-lite owner=z-dev-team", out)
        self.assertIn("RESULT agents borrow=", out)

    def test_borrow_prints_a_dispatch(self):
        rc, out = run(["borrow", "--self", "z-writing-plans", "--agent", "z-explorer"])
        self.assertEqual(rc, 0)
        self.assertIn("AGENT z-explorer", out)
        self.assertIn("SUBAGENT_TYPE z-explorer", out)
        self.assertIn("PROMPT:", out)
        self.assertIn("Question:", out)
        self.assertIn("RESULT borrow action=agent name=z-explorer", out)
        self.assertFalse(any(line.startswith("HANDOFF ") for line in out.splitlines()))

    def test_engine_agent_hands_off_to_its_owner(self):
        rc, out = run(
            ["borrow", "--self", "z-doc-generator", "--agent", "z-programmer-strong"])
        self.assertEqual(rc, 0)
        self.assertIn("HANDOFF z-dev-team", out)
        self.assertIn("RESULT borrow action=handoff name=z-dev-team", out)
        self.assertNotIn("AGENT z-programmer-strong", out)

    def test_owner_does_not_borrow_its_own_agent(self):
        _rc, out = run(["borrow", "--self", "z-dev-team", "--agent", "z-programmer-lite"])
        self.assertIn("STAY z-dev-team", out)
        self.assertIn("you own z-programmer-lite", out)

    def test_unknown_agent_lists_names(self):
        _rc, out = run(["borrow", "--self", "z-brainstorming", "--agent", "z-nope"])
        self.assertIn("unknown agent", out)
        self.assertIn("z-rca-verifier", out)
        self.assertIn("RESULT borrow action=stay", out)


class OpenTests(unittest.TestCase):
    def run_at(self, args, stdin="", cwd=None, env=None):
        if cwd is None:
            # The prelude writes the mode stamp under the repo root; never in
            # this repository's own tree.
            cwd = tempfile.mkdtemp()
            self.addCleanup(shutil.rmtree, cwd, True)
        proc = subprocess.run(
            [sys.executable, HANDOFF] + args,
            input=stdin, capture_output=True, text=True, timeout=60,
            cwd=cwd, env=env)
        return proc.returncode, proc.stdout, proc.stderr

    def binding_next(self, out):
        found = ""
        for line in out.splitlines():
            if line.startswith("NEXT:"):
                found = line
        return found

    def test_handoff_does_not_run_the_prelude(self):
        rc, out, _err = self.run_at(
            ["open", "--self", "z-brainstorming"],
            "the login tests fail with a traceback")
        self.assertEqual(rc, 0)
        self.assertIn("HANDOFF z-systematic-debugging", out)
        self.assertIn("OPEN: routed", out)
        self.assertNotIn("=== PRELUDE ===", out)
        self.assertNotIn("MODE ", out)

    def test_brainstorm_full_without_a_mode_word_defaults_to_fast(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        rc, out, err = self.run_at(
            ["open", "--self", "z-brainstorming"],
            "add a login endpoint to the existing api", cwd=root)
        self.assertEqual(rc, 0, err)
        self.assertIn("STAY z-brainstorming", out)
        self.assertIn("=== PRELUDE ===", out)
        self.assertIn("skill_dir:", out)
        self.assertIn("MODE fast", out)
        self.assertIn("Do not launch a lane", out)
        self.assertNotIn("ASK", out)
        self.assertIn("OPEN: stay", out)
        # FAST merges pick, approval and the chain write into open itself.
        self.assertIn("DECISION pick=A auto=1", out)
        self.assertIn("RESULT approve yes", out)
        chain_json = os.path.join(root, ".brainstorm", "drafts", "chain.json")
        self.assertEqual(json.load(open(chain_json))["mode"], "fast")
        nxt = self.binding_next(out)
        self.assertIn("PACE fast", nxt)
        self.assertIn("ask.py fast already ran", nxt)
        mode_json = os.path.join(root, ".brainstorm", "drafts", "mode.json")
        self.assertEqual(json.load(open(mode_json))["mode"], "fast")

    def test_dev_team_stay_prints_scripts_dir(self):
        rc, out, _err = self.run_at(
            ["open", "--self", "z-dev-team"], "fix the failing test in login")
        self.assertEqual(rc, 0)
        self.assertIn("D=", out)
        self.assertIn("PACE: full", out)
        self.assertIn("z-dev-team/scripts", out.replace("\\", "/"))

    def test_pace_direct_is_one_file_and_login_stays_full(self):
        sys.path.insert(0, os.path.join(HERE, ".."))
        import handoff  # noqa: E402
        self.assertEqual(handoff.pace_of("fix the typo in src/app.py"), "direct")
        self.assertEqual(handoff.pace_of("make the empty state clearer"), "short")
        self.assertEqual(
            handoff.pace_of("add a login endpoint to the existing api"), "full")
        self.assertEqual(handoff.pace_of("please update the README"), "direct")
        self.assertEqual(handoff.pace_of("what does this function do?"), "full")
        self.assertEqual(handoff._doc_pace("document this repo"), "full")
        self.assertEqual(handoff._doc_pace("please update the README"), "direct")
        self.assertFalse(handoff._line_prefix(
            "MODE=INLINE\n+EMPTY_DIFF inside a file\n", "EMPTY_DIFF"))
        self.assertTrue(handoff._line_prefix("EMPTY_DIFF\n", "EMPTY_DIFF"))

    def test_brainstorm_direct_does_not_ask_or_chain(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        rc, out, err = self.run_at(
            ["open", "--self", "z-brainstorming"],
            "fix the typo in src/app.py", cwd=root)
        self.assertEqual(rc, 0, err)
        self.assertIn("PACE: direct", out)
        self.assertNotIn("MODE ask", out)
        self.assertIn("Do not write a spec", out)
        self.assertIn("fast-done", out)
        self.assertIn("After that test passes", out)
        self.assertIn("z-dev-team", out)
        self.assertIn("Do not launch a lane", out)

    def test_dev_team_short_writes_a_one_shot_pace_file(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        rc, out, err = self.run_at(
            ["open", "--self", "z-dev-team"],
            "make the empty state clearer", cwd=root)
        self.assertEqual(rc, 0, err)
        self.assertIn("PACE: short", out)
        self.assertIn("Do not launch z-team-leader", out)
        pace = os.path.join(root, ".claude", "dev-team", "pace")
        self.assertTrue(os.path.isfile(pace))
        with open(pace, encoding="utf-8") as fh:
            self.assertTrue(fh.read().startswith("short "))
        self.assertIn("one devteam start", out)
        self.assertNotIn("Do not call next until a lane has finished", out)

    def test_fast_chain_skips_lanes_and_marks_dev_team(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        rc, out, err = self.run_at(
            ["open", "--self", "z-brainstorming"],
            "FAST: build a new billing service", cwd=root)
        self.assertEqual(rc, 0, err)
        self.assertIn("PACE fast", out)
        self.assertNotIn("fact lanes", out)
        self.assertIn("Do not launch a lane", out)
        self.assertIn("Do not commit in this step", out)
        chain_dir = os.path.join(root, ".brainstorm", "drafts")
        os.makedirs(chain_dir, exist_ok=True)
        with open(os.path.join(chain_dir, "chain.json"), "w", encoding="utf-8") as fh:
            fh.write('{"continue": true, "mode": "fast"}\n')
        rc, out, err = self.run_at(
            ["open", "--self", "z-dev-team"],
            "build the settings page", cwd=root)
        self.assertEqual(rc, 0, err)
        self.assertIn("PACE: fast", out)
        self.assertIn("fast-done", out)
        self.assertIn("After devteam finish succeeds", out)
        pace = os.path.join(root, ".claude", "dev-team", "pace")
        with open(pace, encoding="utf-8") as fh:
            self.assertTrue(fh.read().startswith("fast "))

    def test_debug_stay_prints_s_and_does_not_probe(self):
        rc, out, _err = self.run_at(
            ["open", "--self", "z-systematic-debugging"],
            "the login tests fail with a traceback")
        self.assertEqual(rc, 0)
        self.assertIn("S=", out)
        self.assertIn("debug_tool.py probe", out)
        self.assertNotIn("LANE:", out)

    def test_plans_without_spec_does_not_brief(self):
        rc, out, _err = self.run_at(
            ["open", "--self", "z-writing-plans"],
            "write the implementation plan for the spec")
        self.assertEqual(rc, 0)
        self.assertIn("TOOL:", out)
        self.assertIn("plan_tool.py", out)
        self.assertIn("re-run open --spec", out)
        self.assertNotIn("=== SPEC", out)

    def test_bad_base_does_not_gather(self):
        rc, out, _err = self.run_at(
            ["open", "--self", "z-git-diff-summary", "--base=-evil"],
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
            ["open", "--self", "z-doc-generator"],
            "please update the README", cwd=root, env=env)
        self.assertEqual(rc, 0, err)
        self.assertIn("OPEN: stay", out)
        self.assertIn("HEAD:", out)
        self.assertIn("hello.py", out)
        self.assertIn("PACE: direct", out)
        self.assertIn("No writer agent", out)

    def test_empty_stdin_does_not_run_the_prelude(self):
        rc, out, _err = self.run_at(["open", "--self", "z-brainstorming"], "  \n")
        self.assertEqual(rc, 0)
        self.assertIn("OPEN: empty", out)
        self.assertNotIn("=== PRELUDE ===", out)
        self.assertNotIn("STAY ", out)

    def test_gather_not_a_repo_does_not_say_write_the_summary(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        rc, out, err = self.run_at(
            ["open", "--self", "z-git-diff-summary"],
            "summarize the branch", cwd=root)
        self.assertEqual(rc, 0, err)
        self.assertIn("NOT_A_REPO", out)
        self.assertIn("PACE: direct", out)
        self.assertIn("one line and stop", out)
        self.assertNotIn("write the summary", out)
        self.assertNotIn("Part 1", out)

    def test_audit_existing_dir_does_not_say_write_the_checklist(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        spec = os.path.join(root, "req.md")
        with open(spec, "w", encoding="utf-8") as fh:
            fh.write("The button must save.\n")
        os.makedirs(os.path.join(root, ".audit"))
        with open(os.path.join(root, ".audit", "config.json"), "w", encoding="utf-8") as fh:
            fh.write("{}\n")
        rc, out, err = self.run_at(
            ["open", "--self", "z-requirements-code-audit", "--spec", spec],
            "gaps between spec and code", cwd=root)
        self.assertEqual(rc, 0, err)
        self.assertIn("ERR:", out)
        self.assertIn("prelude failed", out)
        self.assertNotIn("write the checklist", out)

    def test_audit_short_spec_without_a_key_says_dispatch_the_batches(self):
        # audit 2026-11-25: the brief pads its lane label ("lane      agent"); the NEXT must
        # still take the agent-lane branch instead of the api-lane "do not dispatch" text.
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        spec = os.path.join(root, "req.md")
        with open(spec, "w", encoding="utf-8") as fh:
            fh.write("The button must save.\n")
        home = os.path.join(root, "home")
        os.makedirs(home)
        env = {"HOME": home, "PATH": os.environ.get("PATH", ""), "GLM_FLASH": "glm",
               "PYTHONDONTWRITEBYTECODE": "1"}
        rc, out, err = self.run_at(
            ["open", "--self", "z-requirements-code-audit", "--spec", spec],
            "find gaps between the spec and the code", cwd=root, env=env)
        self.assertEqual(rc, 0, err)
        self.assertRegex(out, r"(?m)^lane\s+agent\b")
        nxt = self.binding_next(out)
        self.assertIn("dispatch every printed batch in one message", nxt)
        self.assertNotIn("Do not dispatch a subagent", nxt)

    def test_unknown_self_is_usage(self):
        rc, out, _err = self.run_at(["open", "--self", "z-nope"], "hi")
        self.assertEqual(rc, 2)
        self.assertIn("RESULT open action=stop name=usage", out)


class SlowModeTests(unittest.TestCase):
    """A SLOW request takes the SLOW branch in every one of the seven skills."""

    def git_root(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
        for key, value in (
                ("user.email", "t@t"), ("user.name", "t"),
                ("commit.gpgsign", "false")):
            subprocess.run(["git", "config", key, value], cwd=root, check=True)
        return root

    def commit(self, root, name, body):
        with open(os.path.join(root, name), "w", encoding="utf-8") as fh:
            fh.write(body)
        subprocess.run(["git", "add", name], cwd=root, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "add %s" % name],
                       cwd=root, check=True)

    def run_at(self, root, args, stdin="", env=None):
        proc = subprocess.run(
            [sys.executable, HANDOFF] + args,
            input=stdin, capture_output=True, text=True, timeout=90,
            cwd=root, env=env)
        return proc.returncode, proc.stdout, proc.stderr

    def binding_next(self, out):
        found = ""
        for line in out.splitlines():
            if line.startswith("NEXT:"):
                found = line
        return found

    def assert_slow(self, root, out, err):
        nxt = self.binding_next(out)
        self.assertTrue(nxt.startswith("NEXT:"), err or out)
        self.assertIn("PACE: slow", nxt)
        self.assertNotIn("read fast.md", nxt)
        stamp = os.path.join(root, ".claude", "dev-team", "mode")
        with open(stamp, encoding="utf-8") as fh:
            self.assertTrue(fh.readline().startswith("slow "))
        pace = os.path.join(root, ".claude", "dev-team", "pace")
        self.assertFalse(os.path.exists(pace))

    def test_brainstorming_slow_full(self):
        root = self.git_root()
        rc, out, err = self.run_at(
            root, ["open", "--self", "z-brainstorming"],
            "SLOW add a login endpoint to the existing api")
        self.assertEqual(rc, 0, err)
        self.assertIn("MODE slow", out)
        self.assertIn("PACE: slow", out)
        self.assert_slow(root, out, err)
        self.assertIn("fact lanes", self.binding_next(out))
        mode_json = os.path.join(root, ".brainstorm", "drafts", "mode.json")
        self.assertEqual(json.load(open(mode_json))["mode"], "slow")

    def test_dev_team_slow_full_forces_the_engine_path(self):
        root = self.git_root()
        rc, out, err = self.run_at(
            root, ["open", "--self", "z-dev-team"],
            "SLOW fix the billing bug across the repo")
        self.assertEqual(rc, 0, err)
        self.assert_slow(root, out, err)
        self.assertIn("route-first rule", self.binding_next(out))
        self.assertIn("strict", self.binding_next(out))

    def test_dev_team_slow_direct_stays_in_session(self):
        root = self.git_root()
        rc, out, err = self.run_at(
            root, ["open", "--self", "z-dev-team"],
            "SLOW fix the typo in src/app.py")
        self.assertEqual(rc, 0, err)
        self.assert_slow(root, out, err)
        self.assertIn("Width direct", self.binding_next(out))
        self.assertIn("mutant", self.binding_next(out))
        self.assertNotIn("devteam start", self.binding_next(out))

    def test_writing_plans_slow_never_takes_the_inline_path(self):
        root = self.git_root()
        spec = os.path.join(root, "spec.md")
        with open(spec, "w", encoding="utf-8") as fh:
            fh.write("The button must save the form.\n")
        rc, out, err = self.run_at(
            root, ["open", "--self", "z-writing-plans", "--spec", spec],
            "SLOW write the implementation plan for the spec")
        self.assertEqual(rc, 0, err)
        self.assert_slow(root, out, err)
        self.assertIn("build", self.binding_next(out))
        self.assertNotIn("PACE: short", out)
        self.assertNotIn("inline path: one write", self.binding_next(out))

    def test_audit_slow_ignores_the_short_checklist_path(self):
        root = self.git_root()
        spec = os.path.join(root, "req.md")
        with open(spec, "w", encoding="utf-8") as fh:
            fh.write("The button must save.\n")
        rc, out, err = self.run_at(
            root, ["open", "--self", "z-requirements-code-audit",
                   "--spec", spec],
            "SLOW audit the code against the spec")
        self.assertEqual(rc, 0, err)
        self.assert_slow(root, out, err)
        self.assertIn("second judge", self.binding_next(out))
        self.assertNotIn("PACE: short", out)

    def test_debug_slow_without_cmd_names_the_slow_rules(self):
        root = self.git_root()
        rc, out, err = self.run_at(
            root, ["open", "--self", "z-systematic-debugging"],
            "SLOW the login tests fail with a traceback")
        self.assertEqual(rc, 0, err)
        self.assert_slow(root, out, err)
        self.assertIn("stress.sh -n 200", self.binding_next(out))
        self.assertIn("falsifier", self.binding_next(out))

    def test_doc_slow_always_recons_then_claims(self):
        root = self.git_root()
        self.commit(root, "hello.py", "print('hi')\n")
        env = os.environ.copy()
        env["DOCGEN_STATE_DIR"] = os.path.join(root, "state")
        rc, out, err = self.run_at(
            root, ["open", "--self", "z-doc-generator"],
            "SLOW document this repo", env=env)
        self.assertEqual(rc, 0, err)
        self.assertIn("HEAD:", out)
        self.assertIn("hello.py", out)
        self.assert_slow(root, out, err)
        self.assertIn("claims.py", self.binding_next(out))
        self.assertIn("z-doc-reviewer", self.binding_next(out))
        self.assertNotIn("No writer agent", self.binding_next(out))

    def test_diff_slow_inline_goes_through_claims(self):
        root = self.git_root()
        self.commit(root, "app.py", "def add(a, b):\n    return a + b\n")
        with open(os.path.join(root, "app.py"), "a", encoding="utf-8") as fh:
            fh.write("\n\ndef sub(a, b):\n    return a - b\n")
        rc, out, err = self.run_at(
            root, ["open", "--self", "z-git-diff-summary"],
            "SLOW summarize the branch")
        self.assertEqual(rc, 0, err)
        self.assert_slow(root, out, err)
        self.assertIn("claims.py", self.binding_next(out))
        self.assertNotIn("Zero more tool calls", self.binding_next(out))

    def test_a_later_fast_message_restamps_fast(self):
        root = self.git_root()
        rc, out, err = self.run_at(
            root, ["open", "--self", "z-dev-team"],
            "SLOW fix the billing bug across the repo")
        self.assertEqual(rc, 0, err)
        rc, out, err = self.run_at(
            root, ["open", "--self", "z-dev-team"],
            "FAST fix the billing bug across the repo")
        self.assertEqual(rc, 0, err)
        self.assertIn("PACE: full", out)
        self.assertIn("route-first rule", self.binding_next(out))
        self.assertNotIn("PACE: slow", out)
        stamp = os.path.join(root, ".claude", "dev-team", "mode")
        with open(stamp, encoding="utf-8") as fh:
            self.assertTrue(fh.readline().startswith("fast "))


def _note_files():
    msg = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
    note = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
    msg.write("Add the login retry limit\n\nCap retries at three.\n")
    note.write(
        "Cap login retries at three so a stuck client stops instead of looping.\n"
        "The new limit is covered by the login test.\n")
    msg.close()
    note.close()
    return msg.name, note.name


class FastDoneTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        for key, value in (
                ("user.email", "t@t"), ("user.name", "t"),
                ("commit.gpgsign", "false")):
            subprocess.run(
                ["git", "config", key, value], cwd=self.root, check=True)
        self.msg, self.note = _note_files()
        self.addCleanup(os.remove, self.msg)
        self.addCleanup(os.remove, self.note)

    def _done(self, paths):
        return run_at_cwd(
            ["fast-done", "--message-file", self.msg, "--gitlab-file", self.note,
             "--"] + paths,
            self.root)

    def test_commits_only_the_named_file(self):
        path = os.path.join(self.root, "app.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("print('hi')\n")
        rc, out, err = self._done(["app.py"])
        self.assertEqual(rc, 0, err)
        self.assertIn("FAST-DONE committed", out)
        self.assertIn("COMMIT:", out)
        self.assertIn("Add the login retry limit", out)
        self.assertIn("GITLAB:", out)
        self.assertIn("Cap login retries", out)
        self.assertIn("Do not push", out)
        log = subprocess.run(
            ["git", "log", "-1", "--format=%s"], cwd=self.root,
            capture_output=True, text=True, check=True)
        self.assertEqual(log.stdout.strip(), "Add the login retry limit")
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=self.root,
            capture_output=True, text=True, check=True)
        self.assertEqual(status.stdout.strip(), "")

    def test_second_run_does_not_commit_again(self):
        with open(os.path.join(self.root, "app.py"), "w", encoding="utf-8") as fh:
            fh.write("print('hi')\n")
        self.assertEqual(self._done(["app.py"])[0], 0)
        first = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.root,
            capture_output=True, text=True, check=True).stdout
        rc, out, err = self._done(["app.py"])
        self.assertEqual(rc, 0, err)
        self.assertIn("FAST-DONE already-committed", out)
        second = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.root,
            capture_output=True, text=True, check=True).stdout
        self.assertEqual(first, second)

    def test_trailer_and_secret_and_escape_do_not_commit(self):
        with open(self.msg, "w", encoding="utf-8") as fh:
            fh.write("Add the login retry limit\n\nCo-authored-by: Bot <b@b>\n")
        with open(os.path.join(self.root, "app.py"), "w", encoding="utf-8") as fh:
            fh.write("print('hi')\n")
        rc, out, _err = self._done(["app.py"])
        self.assertEqual(rc, 2)
        self.assertIn("trailer", out)
        log = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=self.root,
            capture_output=True, text=True)
        self.assertNotEqual(log.returncode, 0)
        with open(self.msg, "w", encoding="utf-8") as fh:
            fh.write("Add the login retry limit\n")
        with open(os.path.join(self.root, ".env"), "w", encoding="utf-8") as fh:
            fh.write("TOKEN=1\n")
        rc, out, _err = self._done([".env"])
        self.assertEqual(rc, 2)
        self.assertIn("secret", out)
        rc, out, _err = self._done(["../outside.py"])
        self.assertEqual(rc, 2)
        self.assertIn("FAIL path", out)

    def test_no_paths_prints_the_notes_and_does_not_commit(self):
        rc, out, err = self._done([])
        self.assertEqual(rc, 0, err)
        self.assertIn("FAST-DONE clean", out)
        self.assertIn("GITLAB:", out)
        log = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"], cwd=self.root,
            capture_output=True, text=True)
        self.assertNotEqual(log.returncode, 0)


def run_at_cwd(args, cwd):
    proc = subprocess.run(
        [sys.executable, HANDOFF] + args,
        capture_output=True, text=True, timeout=60, cwd=cwd)
    return proc.returncode, proc.stdout, proc.stderr


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
