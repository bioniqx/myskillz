"""Black-box tests for plan_tool.py lint: --allow by stem/regex and unsafe commit detection (T15).

Runs the real script against throwaway directories under the system temp dir.
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


def run_tool(args, cwd, timeout=25):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run([sys.executable, TOOL] + list(args), cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=timeout)


def make_repo():
    d = os.path.realpath(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    return d


def lint(repo, body, *allow):
    plan = os.path.join(repo, "plan.md")
    with open(plan, "w") as f:
        f.write("# P\n\n## Contracts\n\n#### T01: Demo\n- Files: `demo.py`\n\n")
    task = os.path.join(repo, "T01.md")
    with open(task, "w") as f:
        f.write(body)
    args = ["lint-task", plan, task]
    for a in allow:
        args += ["--allow", a]
    return run_tool(args, cwd=repo)


def prose_body(mid):
    return ("**Files:**\n- Modify: `demo.py`\n\n" + mid + "\n\n"
            "- [ ] **Step 1: implement**\n\n```python\nx = 1\n```\n\n"
            "Then `git commit -m \"feat\"`.\n")


class AllowStemTests(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def test_without_allow_the_hit_is_reported(self):
        p = lint(self.repo, prose_body("Run it through the subagents helper."))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("'subagents'", p.stdout)

    def test_stem_allows_the_plural(self):
        p = lint(self.repo, prose_body("Run it through the subagents helper."), "subagent")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_stem_allows_a_longer_phrase(self):
        p = lint(self.repo, prose_body("Use the Task tool here."), "Task")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_regex_allow(self):
        p = lint(self.repo, prose_body("Run it through the subagents helper."), "re:sub-?agents?")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_regex_must_match_the_whole_hit(self):
        p = lint(self.repo, prose_body("Run it through the subagents helper."), "re:agents")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("'subagents'", p.stdout)

    def test_invalid_regex_is_ignored(self):
        p = lint(self.repo, prose_body("Run it through the subagents helper."), "re:(")
        self.assertNotEqual(p.returncode, 0)
        self.assertNotIn("Traceback", p.stderr)


def shell_body(*blocks):
    out = ("**Files:**\n- Modify: `demo.py`\n\n"
           "- [ ] **Step 1: implement**\n\n```python\nx = 1\n```\n\n")
    for i, b in enumerate(blocks, 2):
        out += "- [ ] **Step %d: commit**\n\n```bash\n%s\n```\n\n" % (i, b)
    return out


class CommitSafetyTests(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()
        self.addCleanup(shutil.rmtree, self.repo, ignore_errors=True)

    def test_explicit_add_then_commit_passes(self):
        p = lint(self.repo, shell_body('git add demo.py && git commit -m "feat"'))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_commit_am_is_rejected(self):
        p = lint(self.repo, shell_body('git add demo.py\ngit commit -am "feat"'))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("-a/--all", p.stdout)

    def test_commit_a_flag_is_rejected(self):
        p = lint(self.repo, shell_body('git add demo.py && git commit -a -m "feat"'))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("-a/--all", p.stdout)

    def test_commit_all_flag_is_rejected(self):
        p = lint(self.repo, shell_body('git add demo.py && git commit --all -m "feat"'))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("-a/--all", p.stdout)

    def test_commit_without_add_is_rejected(self):
        p = lint(self.repo, shell_body('git commit -m "feat"'))
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("no earlier `git add`", p.stdout)

    def test_amend_is_not_mistaken_for_all(self):
        p = lint(self.repo, shell_body('git add demo.py && git commit --amend -m "feat"'))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_dash_a_inside_the_message_is_ignored(self):
        p = lint(self.repo, shell_body('git add demo.py && git commit -m "fix a -a flag"'))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_add_in_an_earlier_block_counts(self):
        p = lint(self.repo, shell_body("git add demo.py", 'git commit -m "feat"'))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()
