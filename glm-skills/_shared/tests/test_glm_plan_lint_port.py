import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = str(ROOT / "writing-plans-glm" / "scripts" / "plan_tool.py")
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


if __name__ == "__main__":
    unittest.main()
