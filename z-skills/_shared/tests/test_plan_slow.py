"""Spec 2026-11-17 (slow mode), Step 5: plan_tool under a slow mode stamp.
No network, no model calls: the build cases force the agent lane. The prelude-side
cases (a slow stamp never prints PACE short) live in test_handoff.py."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "z-writing-plans", "scripts", "plan_tool.py")
FENCE = "`" * 3
FILES = ["src/a.py", "tests/test_a.py"]
ATOM_ERR = "assertion-shaped token"


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_slow_under_test", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()


def make_spec(pad=0):
    """Spec with a quoted atom pair and the two-digit atom 42; pad grows Background."""
    lines = ["# Settings loader", "", "## Background"]
    lines += ["Context for the loader design."] * pad
    lines += ["", "## Behavior",
              'The loader "must ship" a dict and "must log" every key.',
              "Return value is plain and lock-free.",
              "The retry count is 42.",
              ""]
    text = "\n".join(lines)
    behavior = text.splitlines().index("## Behavior") + 1
    return text, "L%d-L%d" % (behavior + 1, behavior + 3)


def plan_text(spec_range):
    return "\n".join([
        "# Plan",
        "",
        "**Out of scope:** the `telemetry` sender",
        "",
        "## Contracts",
        "",
        "#### T01: settings",
        "- Files: `%s`, `%s`" % (FILES[0], FILES[1]),
        "- Produces: `load_settings()`",
        "- Spec: %s" % spec_range,
        "- Tier: light",
        "",
        "<!-- TASKS -->",
        "",
    ])


def task_body(code=("value = load_settings()",), prose=("The retry budget is 42 attempts.",),
              run_fence=None):
    """A body that lints clean against the T01 contract; prose quotes atom 42."""
    rows = ["**Files:**"] + ["- Create: `%s`" % f for f in FILES]
    rows += ["", "- [ ] **Step 1: Write the code**", "", FENCE + "python"]
    rows += list(code) + [FENCE, ""]
    if run_fence is None:
        rows += ["**Run:** python3 -m unittest tests.test_a", "",
                 "**Expected:** `load_settings()` returns the dict", ""]
    else:
        rows += ["**Run:**", "", FENCE + "bash", run_fence, FENCE, "",
                 "**Expected:** the command above passes", ""]
    if prose:
        rows += list(prose) + [""]
    rows += ["- [ ] **Step 2: Commit**", "", FENCE + "bash",
             "git add " + " ".join(FILES),
             'git commit -m "feat: settings"', FENCE, ""]
    return "\n".join(rows)


SPEC_TEXT, BEHAVIOR_RANGE = make_spec()
LONG_SPEC_TEXT, LONG_RANGE = make_spec(pad=90)   # 99 lines: long by the prelude's 80-line bar
assert len(LONG_SPEC_TEXT.splitlines()) > 80


def with_t01(body, spec_range=BEHAVIOR_RANGE):
    return plan_text(spec_range) + "### T01: settings\n\n" + body + "\n"


def stamp_slow(root, text="slow 123\n"):
    path = os.path.join(root, ".claude", "dev-team", "mode")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class TempRepo(unittest.TestCase):
    def repo(self, spec_text=SPEC_TEXT, spec_range=BEHAVIOR_RANGE, plan=None):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        with open(os.path.join(root, "spec.md"), "w", encoding="utf-8") as fh:
            fh.write(spec_text)
        plan_path = os.path.join(root, "plan.md")
        with open(plan_path, "w", encoding="utf-8") as fh:
            fh.write(plan if plan is not None else plan_text(spec_range))
        return root, os.path.join(root, "spec.md"), plan_path

    def run_tool(self, args, cwd):
        proc = subprocess.run([sys.executable, PLAN_TOOL] + args,
                              capture_output=True, text=True, timeout=120, cwd=cwd)
        return proc.returncode, proc.stdout


class SlowStampHelpers(TempRepo):
    def test_slow_mode_reads_the_first_field(self):
        root, _spec, _plan = self.repo()
        self.assertFalse(plan_tool.slow_mode(root))
        stamp_slow(root, "slow 123\n")
        self.assertTrue(plan_tool.slow_mode(root))
        stamp_slow(root, "fast 123\n")
        self.assertFalse(plan_tool.slow_mode(root))

    def test_spec_atoms_need_the_stamp_and_a_readable_spec(self):
        root, spec, _plan = self.repo()
        self.assertIsNone(plan_tool.spec_atoms(spec, root))
        stamp_slow(root)
        atoms = plan_tool.spec_atoms(spec, root)
        self.assertIn("42", atoms)
        self.assertIn("must ship", atoms)
        self.assertIsNone(plan_tool.spec_atoms(os.path.join(root, "nope.md"), root))

    def test_no_split_is_ignored_only_under_slow(self):
        self.assertTrue(plan_tool.split_enabled(True, True))
        self.assertFalse(plan_tool.split_enabled(True, False))
        self.assertTrue(plan_tool.split_enabled(False, False))


class AtomTokenLint(unittest.TestCase):
    def contract(self):
        return {"files": list(FILES), "produces": ["load_settings()"]}

    def errs(self, body, atoms):
        errs, _warns = plan_tool.lint_body(self.contract(), body, [], "T01", None, (), None,
                                           slow_atoms=atoms)
        return errs

    def test_atom_in_prose_only_is_err_under_slow_and_clean_without_it(self):
        atoms = ["42", "must ship", "telemetry"]
        slow = self.errs(task_body(), atoms)
        self.assertTrue([e for e in slow if ATOM_ERR in e and "42" in e], slow)
        self.assertEqual(self.errs(task_body(), None), [])

    def test_the_expected_label_is_not_an_assertion_shaped_token(self):
        atoms = ["42"]
        slow = self.errs(task_body(), atoms)
        self.assertTrue([e for e in slow if ATOM_ERR in e], slow)   # body has **Expected:**

    def test_assert_expect_and_check_tokens_cover_the_atom(self):
        atoms = ["42"]
        cases = [
            task_body(code=("value = load_settings()", "assert value is not None")),
            task_body(prose=("The retry budget is 42 attempts.", "We expect the budget to hold.")),
            task_body(prose=("The retry budget is 42 attempts.", "CHECK the budget before deploy.")),
        ]
        for body in cases:
            self.assertFalse([e for e in self.errs(body, atoms) if ATOM_ERR in e], body)

    def test_the_atom_inside_a_run_expected_fence_covers_it(self):
        body = task_body(run_fence="python3 -m unittest tests.test_a -k budget42")
        self.assertFalse([e for e in self.errs(body, ["42"]) if ATOM_ERR in e], body)

    def test_a_quoted_atom_span_is_also_covered_by_the_rule(self):
        body = task_body(prose=("The contract says `must ship` in so many words.",))
        slow = self.errs(body, ["must ship", "42"])
        self.assertTrue([e for e in slow if ATOM_ERR in e and "must ship" in e], slow)
        self.assertFalse([e for e in slow if "'42'" in e], slow)


class CheckInlinePath(TempRepo):
    def test_a_long_spec_without_a_stamp_still_takes_the_inline_path(self):
        root, spec, plan = self.repo(LONG_SPEC_TEXT, LONG_RANGE,
                                     with_t01(task_body(), LONG_RANGE))
        rc, out = self.run_tool(["check", plan, "--spec", spec], root)
        self.assertEqual(rc, 0, out)
        self.assertIn("OK plan:", out)

    def test_the_same_spec_with_a_slow_stamp_refuses_the_inline_path(self):
        root, spec, plan = self.repo(LONG_SPEC_TEXT, LONG_RANGE,
                                     with_t01(task_body(), LONG_RANGE))
        stamp_slow(root)
        rc, out = self.run_tool(["check", plan, "--spec", spec], root)
        self.assertEqual(rc, 1, out)
        self.assertIn("mode stamp is slow", out)
        self.assertNotIn("OK plan:", out)
        self.assertNotIn("PACE", out)


class LintTaskSlow(TempRepo):
    def _work(self, root, spec, plan):
        work = os.path.join(root, ".work", "plan")
        os.makedirs(os.path.join(work, "tasks"), exist_ok=True)
        with open(os.path.join(work, "work.json"), "w", encoding="utf-8") as fh:
            json.dump({"plan": plan, "spec": spec, "repo": root, "allow": [],
                       "tasks": ["T01"], "review": []}, fh)
        return os.path.join(work, "tasks", "T01.md")

    def test_atom_in_prose_passes_with_no_stamp_and_errs_under_slow(self):
        root, spec, plan = self.repo()
        task = self._work(root, spec, plan)
        with open(task, "w", encoding="utf-8") as fh:
            fh.write(task_body())
        rc, out = self.run_tool(["lint-task", plan, task], root)
        self.assertEqual(rc, 0, out)
        stamp_slow(root)
        rc, out = self.run_tool(["lint-task", plan, task], root)
        self.assertEqual(rc, 1, out)
        self.assertIn(ATOM_ERR, out)
        self.assertIn("42", out)


class BuildSlowStamp(TempRepo):
    def test_slow_stamp_prints_repairs_3_and_split_always(self):
        root, spec, plan = self.repo()
        rc, out = self.run_tool(["build", plan, "--spec", spec, "--lane", "agent"], root)
        self.assertEqual(rc, 0, out)
        self.assertNotIn("SLOW", out)
        stamp_slow(root)
        rc, out = self.run_tool(["build", plan, "--spec", spec, "--lane", "agent"], root)
        self.assertEqual(rc, 0, out)
        self.assertIn("SLOW | repairs 3 | split always", out)

    def test_no_split_and_an_explicit_repairs_value_under_slow(self):
        root, spec, plan = self.repo()
        stamp_slow(root)
        rc, out = self.run_tool(["build", plan, "--spec", spec, "--lane", "agent",
                                 "--no-split"], root)
        self.assertEqual(rc, 0, out)
        self.assertIn("split always", out)
        rc, out = self.run_tool(["build", plan, "--spec", spec, "--lane", "agent",
                                 "--repairs", "5"], root)
        self.assertEqual(rc, 0, out)
        self.assertIn("SLOW | repairs 5 | split always", out)


class FullCheckSlow(TempRepo):
    def test_full_check_enforces_the_atom_lint_only_under_slow(self):
        root, spec, plan_path = self.repo(plan=with_t01(task_body()))
        plan = plan_tool.load(plan_path)
        cs, errs = plan_tool.parse_contracts(plan)
        self.assertEqual(errs, [], errs)
        bodies = {"T01": plan_tool.strip_generated(
            "### T01: settings\n\n" + task_body() + "\n")}
        e, _w = plan_tool.full_check(plan_path, plan, cs, bodies, spec, [])
        self.assertFalse([x for x in e if ATOM_ERR in x], e)
        stamp_slow(root)
        e2, _w = plan_tool.full_check(plan_path, plan, cs, bodies, spec, [])
        self.assertTrue([x for x in e2 if ATOM_ERR in x and "42" in x], e2)


if __name__ == "__main__":
    unittest.main()
