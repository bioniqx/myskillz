import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = str(ROOT / "glm-writing-plans" / "scripts" / "plan_tool.py")
FENCE = "`" * 3

PLAN = """# Demo Implementation Plan

**Goal:** demo

**Architecture:** demo

**Tech Stack:** python

## Global Constraints

- none

## Contracts

#### T01: Greeter
- Files: `src/greet.py`, `tests/test_greet.py`
- Produces: `def greet(name: str) -> str`
- Spec: L1-5
"""


def body(commit_cmd, prose="Write the greeter."):
    return (
        "**Files:**\n"
        "- Create: `src/greet.py`\n"
        "- Test: `tests/test_greet.py`\n\n"
        "- [ ] **Step 1: Write the failing test**\n\n"
        + prose + "\n\n"
        + FENCE + "python\n"
        "def greet(name: str) -> str:\n"
        "    return 'hi ' + name\n"
        + FENCE + "\n\n"
        "- [ ] **Step 2: Run test to verify it fails**\n\n"
        "Run: `python3 -m unittest tests.test_greet -v`\n"
        "Expected: FAIL with ImportError\n\n"
        "- [ ] **Step 3: Commit**\n\n"
        + FENCE + "bash\n" + commit_cmd + "\n" + FENCE + "\n"
    )


class GlmLintPortTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(self.d), True)
        self.plan = self.d / "plan.md"
        self.plan.write_text(PLAN)

    def lint(self, text, *extra):
        task = self.d / "T01.md"
        task.write_text(text)
        r = subprocess.run([sys.executable, TOOL, "lint-task", str(self.plan), str(task)] + list(extra),
                           capture_output=True, text=True, timeout=60)
        return r.stdout + r.stderr

    def test_commit_dash_a_is_rejected(self):
        out = self.lint(body("git add src/greet.py tests/test_greet.py\ngit commit -a -m 'x'"))
        self.assertIn("ERR", out)

    def test_commit_without_add_is_rejected(self):
        out = self.lint(body("git commit -m 'x'"))
        self.assertIn("ERR", out)

    def test_explicit_add_then_commit_passes(self):
        out = self.lint(body("git add src/greet.py tests/test_greet.py\ngit commit -m 'x'"))
        self.assertNotIn("ERR", out)

    def test_lowercase_todo_in_prose_is_not_flagged(self):
        out = self.lint(body("git add src/greet.py tests/test_greet.py\ngit commit -m 'x'",
                             prose="Build the todo list greeter."))
        self.assertNotIn("ERR", out)

    def test_uppercase_todo_in_prose_is_flagged(self):
        out = self.lint(body("git add src/greet.py tests/test_greet.py\ngit commit -m 'x'",
                             prose="TODO fill this in."))
        self.assertIn("ERR", out)

    def test_allow_stem_permits_banned_word(self):
        out = self.lint(body("git add src/greet.py tests/test_greet.py\ngit commit -m 'x'",
                             prose="TODO fill this in."), "--allow", "TODO")
        self.assertNotIn("ERR", out)


GOOD = "git add src/greet.py tests/test_greet.py\ngit commit -m 'x'"
BAD = "git commit -m 'x'"


class GlmMarksAndWaitTests(unittest.TestCase):
    def setUp(self):
        self.d = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(self.d), True)
        self.plan = self.d / "plan.md"
        self.plan.write_text(PLAN)
        self.work = self.d / ".work" / "plan"
        (self.work / "tasks").mkdir(parents=True)
        (self.work / "work.json").write_text(json.dumps({"plan": str(self.plan), "tasks": ["T01"], "allow": []}))
        self.task = self.work / "tasks" / "T01.md"

    def run_tool(self, *args, stdin=None):
        env = dict(os.environ, PLAN_TOOL_WAIT_MIN_AGE="0")
        return subprocess.run([sys.executable, TOOL] + list(args), capture_output=True, text=True,
                              input=stdin, env=env, timeout=60)

    def lint(self, text):
        self.task.write_text(text)
        return self.run_tool("lint-task", str(self.plan), str(self.task))

    def mark(self, suffix):
        return Path(str(self.task) + suffix)

    def test_lint_task_fail_then_clean_then_warn_marks(self):
        self.lint(body(BAD))
        self.assertTrue(self.mark(".fail").exists())
        self.assertFalse(self.mark(".ok").exists())
        self.lint(body(GOOD))
        self.assertFalse(self.mark(".fail").exists())
        self.assertTrue(self.mark(".ok").exists())
        self.mark(".warn").write_text("stale")
        self.lint(body(GOOD))
        self.assertFalse(self.mark(".warn").exists())

    def test_lint_task_warn_only_writes_warn_and_clean_removes_it(self):
        self.lint(body("git add src tests/test_greet.py\ngit commit -m 'x'"))
        self.assertFalse(self.mark(".fail").exists())
        self.assertTrue(self.mark(".ok").exists())
        self.assertIn("stages a directory", self.mark(".warn").read_text())
        self.lint(body(GOOD))
        self.assertFalse(self.mark(".warn").exists())
        self.assertTrue(self.mark(".ok").exists())

    def test_hook_lint_writes_fail_then_ok(self):
        self.task.write_text(body(BAD))
        payload = json.dumps({"tool_input": {"file_path": str(self.task)}})
        r = self.run_tool("hook-lint", stdin=payload)
        self.assertIn("plan-lint: FAIL", r.stdout)
        self.assertTrue(self.mark(".fail").exists())
        self.task.write_text(body(GOOD))
        r = self.run_tool("hook-lint", stdin=payload)
        self.assertIn("plan-lint: OK", r.stdout)
        self.assertFalse(self.mark(".fail").exists())
        self.assertTrue(self.mark(".ok").exists())

    def test_wait_reports_stuck_failing_unchanged_task(self):
        self.task.write_text(body(BAD))
        self.mark(".fail").write_text("ERR")
        r = self.run_tool("wait", str(self.plan))
        self.assertEqual(r.returncode, 1)
        self.assertIn("failing and unchanged", r.stdout)
        self.assertNotIn("NameError", r.stdout + r.stderr)

    def test_wait_exits_zero_when_ok_mark_is_newer(self):
        self.task.write_text(body(GOOD))
        time.sleep(0.05)
        self.mark(".ok").write_text("1")
        r = self.run_tool("wait", str(self.plan))
        self.assertEqual(r.returncode, 0)
        self.assertIn("DONE 1/1", r.stdout)

    def test_task_mtime_and_task_stuck_defined(self):
        src = Path(TOOL).read_text()
        self.assertIn("def task_mtime(", src)
        self.assertIn("def task_stuck(", src)


if __name__ == "__main__":
    unittest.main()
