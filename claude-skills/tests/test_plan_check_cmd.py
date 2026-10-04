"""Black-box tests for `plan_tool.py check` (T04): the single-task path with task bodies written
inline in the plan file after the contracts.

`check` lints every inline body, then renders the same canonical plan `assemble` produces. It
must refuse (and leave the plan file byte-identical) when a body is missing, breaks a lint rule,
or has no contract.

Runs the real script against throwaway git repos under the system temp dir.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TESTS_DIR)  # claude-skills/
TOOL = os.path.join(BASE_DIR, "claude-writing-plans-6.2", "scripts", "plan_tool.py")
FENCE = "`" * 3

HEADER = ("# Demo Plan\n\n**Goal:** demo\n\n**Architecture:** demo\n\n**Tech Stack:** python\n\n"
          "## Global Constraints\n\n- keep it simple\n\n## Contracts\n\n")
CONTRACT_ONE = "#### T01: Demo\n- Files: `demo.py`\n- Spec: L1-L3\n\n"
CONTRACT_TWO = "#### T02: Second\n- Files: `other.py`\n- Spec: L5-L6\n\n"
SPEC = "## Alpha\n\nalpha text\n\n## Beta\n\nbeta text\n"


def inline_task(n, path):
    return ("### T%02d: Task %d\n\n**Files:**\n- Create: `%s`\n\n"
            "- [ ] **Step 1: implement**\n\n%spython\nx = %d\n%s\n\n"
            "Then `git commit -m \"feat\"`.\n" % (n, n, path, FENCE, n, FENCE))


class CheckCase(unittest.TestCase):
    def setUp(self):
        self.repo = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)
        for cmd in (["init", "-q"], ["config", "user.email", "t@example.com"],
                    ["config", "user.name", "T"], ["config", "commit.gpgsign", "false"]):
            subprocess.run(["git"] + cmd, cwd=self.repo, check=True)
        self.plan = os.path.join(self.repo, "plan.md")

    def write_plan(self, text):
        with open(self.plan, "w") as f:
            f.write(text)

    def read_plan(self):
        with open(self.plan) as f:
            return f.read()

    def check(self, *extra):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, TOOL, "check", self.plan] + list(extra),
                              cwd=self.repo, env=env, capture_output=True, text=True, timeout=40)


class CheckTests(CheckCase):
    def test_single_inline_task_is_rendered_into_the_canonical_plan(self):
        self.write_plan(HEADER + CONTRACT_ONE + inline_task(1, "demo.py"))
        p = self.check()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("OK plan: 1 tasks | 1 waves | max wave width 1", p.stdout)
        text = self.read_plan()
        for needle in ("## Execution Protocol", "## File Structure", "## Execution Waves",
                       "**Wave 1:** T01", "### T01: Demo", "**Depends:** —"):
            self.assertIn(needle, text)

    def test_two_inline_tasks_over_disjoint_files_share_a_parallel_wave(self):
        self.write_plan(HEADER + CONTRACT_ONE + CONTRACT_TWO
                        + inline_task(1, "demo.py") + "\n---\n\n" + inline_task(2, "other.py"))
        p = self.check()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("**Wave 1:** T01 [P], T02 [P]", self.read_plan())

    def test_check_twice_leaves_the_plan_unchanged(self):
        self.write_plan(HEADER + CONTRACT_ONE + inline_task(1, "demo.py"))
        self.assertEqual(self.check().returncode, 0)
        first = self.read_plan()
        self.assertEqual(self.check().returncode, 0)
        self.assertEqual(self.read_plan(), first)

    def test_missing_task_body_fails_and_leaves_the_plan_untouched(self):
        self.write_plan(HEADER + CONTRACT_ONE + CONTRACT_TWO + inline_task(1, "demo.py"))
        before = self.read_plan()
        p = self.check()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("T02: task body missing", p.stdout)
        self.assertEqual(self.read_plan(), before)

    def test_lint_error_in_an_inline_body_fails_and_leaves_the_plan_untouched(self):
        self.write_plan(HEADER + CONTRACT_ONE + inline_task(1, "elsewhere.py"))
        before = self.read_plan()
        p = self.check()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("Files lists `elsewhere.py` which is not in the contract Files", p.stdout)
        self.assertEqual(self.read_plan(), before)

    def test_inline_body_without_a_contract_fails(self):
        self.write_plan(HEADER + CONTRACT_ONE + inline_task(1, "demo.py") + "\n---\n\n"
                        + inline_task(9, "ghost.py"))
        p = self.check()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("T09: task body has no contract", p.stdout)

    def test_spec_flag_reports_an_uncovered_section_as_a_warning(self):
        with open(os.path.join(self.repo, "spec.md"), "w") as f:
            f.write(SPEC)
        self.write_plan(HEADER + CONTRACT_ONE + inline_task(1, "demo.py"))
        p = self.check("--spec", os.path.join(self.repo, "spec.md"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("WARN spec uncovered L5-7 ## Beta", p.stdout)

    def test_plan_without_a_contracts_section_fails(self):
        self.write_plan("# Demo Plan\n\nno contracts here\n")
        p = self.check()
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("no '## Contracts' section", p.stdout)


if __name__ == "__main__":
    unittest.main()
