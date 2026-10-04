"""Black-box tests for the plan_tool.py lint rules (T04).

One test per rule: contract ids and Consumes (`contracts`), and the task-body rules of
`lint-task` (Files subset, steps, Run/Expected, code-block syntax, produced signatures,
`git add` scope, commit step). The placeholder, portability and fence rules are already
pinned in tests/test_plan_lint.py.

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
COMMIT = 'Then `git commit -m "feat"`.'


def run_tool(args, cwd, timeout=25):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, TOOL] + list(args), cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=timeout)


def make_repo():
    d = os.path.realpath(tempfile.mkdtemp())
    for cmd in (["init", "-q"], ["config", "user.email", "t@example.com"],
                ["config", "user.name", "T"], ["config", "commit.gpgsign", "false"]):
        subprocess.run(["git"] + cmd, cwd=d, check=True)
    with open(os.path.join(d, "README.md"), "w") as f:
        f.write("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=d, check=True)
    return d


def body_text(files=("Modify: `demo.py`",), steps=("implement",), code="x = 1", lang="python",
              tail=COMMIT, extra=""):
    lines = ["**Files:**"] + ["- " + f for f in files] + [""]
    if extra:
        lines += [extra, ""]
    for i, name in enumerate(steps, 1):
        lines += ["- [ ] **Step %d: %s**" % (i, name), ""]
    if code is not None:
        lines += [FENCE + lang, code, FENCE, ""]
    if tail:
        lines.append(tail)
    return "\n".join(lines) + "\n"


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def write(self, name, text):
        path = os.path.join(self.repo, name)
        with open(path, "w") as f:
            f.write(text)
        return path

    def contracts(self, text, *extra):
        plan = self.write("plan.md", "# P\n\n## Contracts\n\n" + text)
        return run_tool(["contracts", plan] + list(extra), cwd=self.repo)

    def lint(self, body, contract="#### T01: Demo\n- Files: `demo.py`\n"):
        plan = self.write("plan.md", "# P\n\n## Contracts\n\n" + contract)
        task = self.write("T01.md", body)
        return run_tool(["lint-task", plan, task], cwd=self.repo)

    def assert_lint_error(self, result, needle):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ERR  ", result.stdout)
        self.assertIn(needle, result.stdout)


class ContractRuleTests(RepoCase):
    def test_ids_must_be_sequential_without_gaps(self):
        p = self.contracts("#### T01: A\n- Files: `a.py`\n\n#### T03: C\n- Files: `c.py`\n")
        self.assert_lint_error(p, "T03: expected id T02 (sequential, zero-padded, no gaps)")

    def test_consuming_a_signature_nobody_produces_is_an_error(self):
        p = self.contracts(
            "#### T01: A\n- Files: `a.py`\n- Produces: `def a() -> None`\n\n"
            "#### T02: B\n- Files: `b.py`\n- Depends: T01\n- Consumes: `def nope() -> None`\n")
        self.assert_lint_error(p, "T02: consumes `def nope() -> None` which no task produces verbatim")

    def test_consuming_from_a_later_task_is_an_error(self):
        p = self.contracts(
            "#### T01: A\n- Files: `a.py`\n- Consumes: `def b() -> None`\n\n"
            "#### T02: B\n- Files: `b.py`\n- Produces: `def b() -> None`\n")
        self.assert_lint_error(p, "T01: consumes `def b() -> None` from later task T02")

    def test_depending_on_a_later_task_is_an_error(self):
        p = self.contracts("#### T01: A\n- Files: `a.py`\n- Depends: T02\n\n#### T02: B\n- Files: `b.py`\n")
        self.assert_lint_error(p, "T01: depends on later/self task T02")

    def test_a_contract_without_files_is_an_error(self):
        p = self.contracts("#### T01: A\n- Produces: `def a() -> None`\n")
        self.assert_lint_error(p, "T01: '- Files:' needs at least one `backticked` path")


class BodyRuleTests(RepoCase):
    def test_a_valid_body_passes(self):
        p = self.lint(body_text())
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("OK T01", p.stdout)

    def test_files_list_may_not_name_a_path_outside_the_contract(self):
        p = self.lint(body_text(files=("Modify: `demo.py`", "Create: `extra.py`")))
        self.assert_lint_error(p, "Files lists `extra.py` which is not in the contract Files")

    def test_files_list_must_name_every_contract_path(self):
        contract = "#### T01: Demo\n- Files: `demo.py`, `other.py`\n"
        p = self.lint(body_text(), contract=contract)
        self.assert_lint_error(p, "contract file `other.py` missing from the **Files:** list")

    def test_body_without_step_checkboxes_is_an_error(self):
        p = self.lint(body_text(steps=()))
        self.assert_lint_error(p, "no '- [ ] **Step N: ...**' checkboxes")

    def test_steps_must_be_numbered_in_order(self):
        body = body_text(steps=("one", "two")).replace("Step 2:", "Step 3:")
        p = self.lint(body)
        self.assert_lint_error(p, "steps must be numbered 1..2 in order (got [1, 3])")

    def test_run_line_without_expected_is_an_error(self):
        p = self.lint(body_text(extra="Run: `python3 -m unittest -v`"))
        self.assert_lint_error(p, "has no 'Expected:' before the next Run/Step")

    def test_run_line_followed_by_expected_passes(self):
        p = self.lint(body_text(extra="Run: `python3 -m unittest -v`\nExpected: OK"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_invalid_python_block_is_an_error(self):
        p = self.lint(body_text(code="def broken(:\n    pass"))
        self.assert_lint_error(p, "python syntax line 1")

    def test_invalid_json_block_is_an_error(self):
        p = self.lint(body_text(code="{not json", lang="json"))
        self.assert_lint_error(p, "(json)")

    def test_fragment_fence_skips_the_syntax_check(self):
        p = self.lint(body_text(code="def broken(:", lang="python fragment"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_produced_signature_must_appear_verbatim(self):
        contract = "#### T01: Demo\n- Files: `demo.py`\n- Produces: `def run(n: int) -> int`\n"
        p = self.lint(body_text(code="def run(n):\n    return n"), contract=contract)
        self.assert_lint_error(p, "produced signature not written verbatim in the body: `def run(n: int) -> int`")

    def test_git_add_of_everything_is_an_error(self):
        p = self.lint(body_text(extra=FENCE + "bash\ngit add .\n" + FENCE))
        self.assert_lint_error(p, "stage explicit paths from Files only")

    def test_git_add_of_a_path_outside_the_contract_is_an_error(self):
        p = self.lint(body_text(extra=FENCE + "bash\ngit add other.py\n" + FENCE))
        self.assert_lint_error(p, "`git add` path `other.py` is not in the contract Files")

    def test_body_without_a_commit_step_is_an_error(self):
        p = self.lint(body_text(tail=""))
        self.assert_lint_error(p, "no commit step")


if __name__ == "__main__":
    unittest.main()
