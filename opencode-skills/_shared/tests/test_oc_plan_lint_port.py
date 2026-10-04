"""The oc plan tool must lint the way the original plan tool does."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[2] / "oc-writing-plans" / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("oc_plan_tool_port", str(SCRIPTS / "oc_plan_tool.py"))
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

FENCE = "`" * 3
WORD = "TO" + "DO"


class ScanTests(unittest.TestCase):
    def test_lowercase_todo_and_code_span_are_clean(self):
        text = "A todo app plan keeps a todo list.\nUse the `Claude` note at https://claude.ai/docs here.\n"
        self.assertEqual(M.scan(text, [], "plan"), [])

    def test_uppercase_marker_and_prose_portability_still_fail(self):
        errs = M.scan(WORD + ": later\nAsk Claude to help.\n", [], "plan")
        self.assertEqual(len(errs), 2)
        self.assertIn("placeholder", errs[0])
        self.assertIn("portability", errs[1])

    def test_fenced_code_skips_portability_and_scans_markers_on_request(self):
        text = "\n".join([FENCE + "python", "x = 'Claude'", "y = '" + WORD + "'", FENCE]) + "\n"
        self.assertEqual(M.scan(text, [], "t"), [])
        errs = M.scan(text, [], "t", fenced_placeholders=True)
        self.assertEqual(len(errs), 1)
        self.assertIn("placeholder", errs[0])

    def test_allow_hit_stem_and_regex(self):
        self.assertTrue(M.allow_hit("subagents", ["subagent"]))
        self.assertTrue(M.allow_hit(WORD, ["re:TO.*"]))
        self.assertFalse(M.allow_hit(WORD, ["re:TOD"]))
        self.assertFalse(M.allow_hit("Claude", ["todo"]))
        self.assertEqual(M.scan("The subagents run.\n", ["subagent"], "t"), [])




def body(code="x = 1", add="git add src/a.py", commit='git commit -m "feat: a"', extra=""):
    return "\n".join([
        "**Files:**", "- Create: `src/a.py`", "",
        "- [ ] **Step 1: Write**", "", FENCE + "python", code, FENCE, "",
        "- [ ] **Step 2: Commit**", "", FENCE + "bash", add, commit, FENCE, extra]) + "\n"


CONTRACT = {"id": "T01", "files": ["src/a.py"], "produces": []}


def lint(text):
    return M.lint_body(CONTRACT, text, [], "T01", None, ())[0]


class LintBodyTests(unittest.TestCase):
    def test_clean_body_has_no_errors(self):
        self.assertEqual(lint(body()), [])

    def test_commit_all_flag_is_rejected(self):
        errs = lint(body(commit='git commit -am "feat: a"'))
        self.assertTrue(any("stages every tracked change" in e for e in errs), errs)

    def test_commit_without_add_is_rejected(self):
        errs = lint(body(add=""))
        self.assertTrue(any("has no earlier `git add`" in e for e in errs), errs)

    def test_fake_task_heading_inside_a_fence_is_rejected(self):
        errs = lint(body(extra=FENCE + "text\n### T09: fake task\n" + FENCE))
        self.assertTrue(any("heading inside a task body" in e for e in errs), errs)

    def test_hash_comment_inside_a_fence_is_not_a_heading(self):
        errs = lint(body(extra=FENCE + "text\n# note\n" + FENCE))
        self.assertFalse(any("heading inside a task body" in e for e in errs), errs)

    def test_files_block_takes_only_the_first_span(self):
        text = "**Files:**\n- Create: `src/a.py` (see `docs/b.md`)\n"
        self.assertEqual(M.files_block(text), ["src/a.py"])

    def test_marker_inside_a_code_block_is_rejected(self):
        errs = lint(body(code="x = '" + WORD + "'"))
        self.assertTrue(any("placeholder" in e for e in errs), errs)

    def test_spec_coverage_ignores_fenced_headings(self):
        with tempfile.TemporaryDirectory() as d:
            spec = os.path.join(d, "spec.md")
            with open(spec, "w", encoding="utf-8") as f:
                f.write("\n".join(["# Title", "intro", FENCE + "text", "# fake heading", "inside", FENCE]) + "\n")
            out = M.spec_coverage([{"id": "T01", "spec": [(1, 3)]}], spec)
        self.assertEqual(out, [])

    def test_sh_adds_no_optional_locks(self):
        seen = []

        class Done:
            returncode = 0
            stdout = "out"

        def fake_run(cmd, **kw):
            seen.append(list(cmd))
            return Done()

        with mock.patch.object(M.subprocess, "run", fake_run):
            self.assertEqual(M.sh(["git", "status"]), "out")
        self.assertEqual(seen, [["git", "--no-optional-locks", "status"]])



PLAN_TEXT = "\n".join([
    "# Demo Implementation Plan", "", "**Goal:** Demo.", "", "## Contracts", "",
    "#### T01: Build", "- Files: `src/a.py`", "- Produces: `def a() -> int`", ""])


class MarksWaitAndBriefTests(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="oc-port-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        os.makedirs(os.path.join(self.tmp, ".git"))

    def write(self, path, text):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_apply_marks_lifecycle(self):
        task = os.path.join(self.tmp, "T01.md")
        self.write(task, "body")
        M.apply_marks(task, "ok", ["boom"], [])
        self.assertTrue(os.path.exists(task + ".fail"))
        self.assertFalse(os.path.exists(task + ".ok"))
        M.apply_marks(task, "ok", [], ["careful"])
        self.assertFalse(os.path.exists(task + ".fail"))
        self.assertTrue(os.path.exists(task + ".ok"))
        self.assertTrue(os.path.exists(task + ".warn"))
        M.apply_marks(task, "ok", [], [])
        self.assertFalse(os.path.exists(task + ".warn"))

    def test_contract_hashes_cover_the_producers_a_task_depends_on(self):
        cs = [{"id": "T01", "text": "one", "deps_all": []}, {"id": "T02", "text": "two", "deps_all": ["T01"]}]
        before = M.contract_hashes(cs)
        cs[0]["text"] = "changed"
        after = M.contract_hashes(cs)
        self.assertNotEqual(before["T01"], after["T01"])
        self.assertNotEqual(before["T02"], after["T02"])
        cs[1]["text"] = "two!"
        self.assertEqual(after["T01"], M.contract_hashes(cs)["T01"])

    def test_task_stuck_needs_a_fail_mark_and_quiet_time(self):
        task = os.path.join(self.tmp, "T01.md")
        self.write(task, "body")
        self.assertFalse(M.task_stuck(task, 99))
        self.write(task + ".fail", "boom")
        self.assertFalse(M.task_stuck(task, 10))
        self.assertTrue(M.task_stuck(task, 45))

    def test_wait_reports_a_stuck_failing_task(self):
        plan = os.path.join(self.tmp, "plan.md")
        work = os.path.join(self.tmp, ".work", "plan")
        self.write(os.path.join(work, "work.json"), json.dumps({"tasks": ["T01"], "review": []}))
        task = os.path.join(work, "tasks", "T01.md")
        self.write(task, "x")
        self.write(task + ".fail", "x")
        args = argparse.Namespace(plan=plan, review=False, timeout=3, idle=3)
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"PLAN_TOOL_WAIT_MIN_AGE": "0"}), contextlib.redirect_stdout(out):
            rc = M.cmd_wait(args)
        self.assertEqual(rc, 1)
        self.assertIn("unchanged for >=0s", out.getvalue())

    def test_build_drops_the_files_of_a_changed_contract(self):
        plan = os.path.join(self.tmp, "plan.md")
        self.write(plan, PLAN_TEXT)
        args = argparse.Namespace(plan=plan, spec=None, allow=[], workers=None, resume=False, thorough=False)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(M.cmd_build(args), 0)
        body_path = os.path.join(self.tmp, ".work", "plan", "tasks", "T01.md")
        for suffix in ("", ".ok", ".fail"):
            self.write(body_path + suffix, "x")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(M.cmd_build(args), 0)
        self.assertTrue(os.path.exists(body_path))
        self.write(plan, PLAN_TEXT.replace("def a() -> int", "def a() -> str"))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(M.cmd_build(args), 0)
        for suffix in ("", ".ok", ".fail"):
            self.assertFalse(os.path.exists(body_path + suffix), suffix)

    def test_hook_lint_writes_a_fail_mark(self):
        plan = os.path.join(self.tmp, "plan.md")
        self.write(plan, PLAN_TEXT)
        work = os.path.join(self.tmp, ".work", "plan")
        self.write(os.path.join(work, "work.json"), json.dumps({"plan": plan}))
        task = os.path.join(work, "tasks", "T01.md")
        self.write(task, "bad\n")
        event = json.dumps({"tool_input": {"file_path": task}})
        with mock.patch("sys.stdin", io.StringIO(event)), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(M.cmd_hook_lint(argparse.Namespace()), 0)
        self.assertTrue(os.path.exists(task + ".fail"))
        self.assertFalse(os.path.exists(task + ".ok"))

    def test_reviewer_brief_inlines_the_task_bodies(self):
        plan = os.path.join(self.tmp, "plan.md")
        self.write(plan, PLAN_TEXT)
        cs, _ = M.parse_contracts(PLAN_TEXT)
        M.analyze(cs, None, None)
        work = os.path.join(self.tmp, ".work", "plan")
        self.write(os.path.join(work, "tasks", "T01.md"), "**Files:**\n- Create: `src/a.py`\nBODY-MARKER-LINE\n")
        brief = M.reviewer_brief(plan, PLAN_TEXT, cs, work, None, self.tmp)
        self.assertIn("    3| BODY-MARKER-LINE", brief)



if __name__ == "__main__":
    unittest.main()
