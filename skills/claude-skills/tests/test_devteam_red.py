"""K22: commit-red stages only test files; integrate rejects a RED commit that touches source.

Black-box: real devteam.py subprocesses against disposable git repos in the SYSTEM temp dir.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEVTEAM_PATH = str(Path(__file__).resolve().parents[1] / "dev-team-v3.2" / "scripts" / "devteam.py")
TEST_JS = 'test("x", () => { assert.equal(1, 1); });\n'


def run_dt(args, cwd):
    return subprocess.run([sys.executable, DEVTEAM_PATH] + args, cwd=str(cwd),
                          capture_output=True, text=True, timeout=60)


def git(args, cwd):
    return subprocess.run(["git"] + args, cwd=str(cwd), check=True, capture_output=True, text=True).stdout


def new_repo(test):
    d = Path(os.path.realpath(tempfile.mkdtemp()))
    test.addCleanup(shutil.rmtree, str(d), True)
    for a in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"],
              ["config", "user.name", "t"], ["config", "commit.gpgsign", "false"]):
        git(a, d)
    return d


class RedFixture(unittest.TestCase):
    RISK = "low"

    def setUp(self):
        repo = new_repo(self)
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "src" / ".keep").write_text("")
        (repo / "src" / "S1.js").write_text("// original\n")
        (repo / "tests" / ".keep").write_text("")
        git(["add", "-A"], repo)
        git(["commit", "-q", "-m", "init"], repo)
        plan = {"request": "K22", "profile": "balanced",
                "commands": {"test": "none", "test_file": "none"},
                "slices": [{"id": "S1", "title": "s1", "files": ["src/S1.js", "src/new.js", "conftest.py", "tests/S1.test.js"],
                            "risk": self.RISK, "criteria": ["works"]}]}
        (repo / "plan.md").write_text("# plan\n```json\n%s\n```\n" % json.dumps(plan))
        r = run_dt(["init", "plan.md"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run_dt(["dispatch", "S1"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        git(["worktree", "add", "-q", ".claude/worktrees/w1", "-b", "worktree-w1", "HEAD"], repo)
        self.repo = repo
        self.wt = repo / ".claude" / "worktrees" / "w1"
        r = run_dt(["claim", "S1"], self.wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.claim_out = r.stdout


class TestCommitRedStagesOnlyTests(RedFixture):
    def test_source_stubs_are_discarded_after_red_commit(self):
        (self.wt / "tests" / "S1.test.js").write_text(TEST_JS)
        (self.wt / "src" / "S1.js").write_text("module.exports = 0;\n")   # stub edit of a tracked file
        (self.wt / "src" / "new.js").write_text("module.exports = 0;\n")  # new untracked stub
        r = run_dt(["commit-red", "S1"], self.wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        committed = git(["show", "--name-only", "--format=", "HEAD"], self.wt).split()
        self.assertEqual(committed, ["tests/S1.test.js"])
        self.assertEqual((self.wt / "src" / "S1.js").read_text(), "// original\n")
        self.assertFalse((self.wt / "src" / "new.js").exists())
        status = [l for l in git(["status", "--porcelain"], self.wt).splitlines() if ".slice" not in l]
        self.assertEqual(status, [])
        self.assertIn("discard", (r.stdout + r.stderr).lower())

    def test_discarded_stubs_are_saved_as_a_recoverable_patch(self):
        (self.wt / "tests" / "S1.test.js").write_text(TEST_JS)
        (self.wt / "src" / "S1.js").write_text("module.exports = 0;\n")
        (self.wt / "conftest.py").write_text("STUB_MARKER = 42\n")
        r = run_dt(["commit-red", "S1"], self.wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        patch = self.repo / ".claude" / "dev-team" / "salvage" / "S1-red.patch"
        self.assertTrue(patch.exists(), "no salvage patch written")
        self.assertIn("S1-red.patch", r.stdout + r.stderr)
        text = patch.read_text()
        self.assertIn("STUB_MARKER = 42", text)
        self.assertIn("module.exports = 0;", text)
        self.assertNotIn("tests/S1.test.js", text)
        self.assertFalse((self.wt / "conftest.py").exists())
        git(["apply", "--check", str(patch)], self.wt)

    def test_slice_brief_does_not_say_stubs_are_committed_with_red(self):
        self.assert_brief_discards_stubs(self.claim_out)

    def assert_brief_discards_stubs(self, brief):
        text = brief.lower()
        self.assertIn("stub", text)
        self.assertNotIn("committed with red", text)
        self.assertNotIn("belong to the green", text)
        self.assertRegex(text, r"stubs?[^\n]*discard")

    def test_green_commit_still_commits_the_source(self):
        (self.wt / "tests" / "S1.test.js").write_text(TEST_JS)
        (self.wt / "src" / "S1.js").write_text("module.exports = 0;\n")
        self.assertEqual(run_dt(["commit-red", "S1"], self.wt).returncode, 0)
        (self.wt / "src" / "S1.js").write_text("module.exports = 1;\n")
        r = run_dt(["commit-green", "S1"], self.wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(git(["show", "--name-only", "--format=", "HEAD"], self.wt).split(), ["src/S1.js"])

    def test_only_source_changed_is_still_refused(self):
        (self.wt / "src" / "S1.js").write_text("module.exports = 0;\n")
        r = run_dt(["commit-red", "S1"], self.wt)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(git(["rev-list", "--count", "HEAD"], self.wt).strip(), "1")


class TestRedModeStubs(TestCommitRedStagesOnlyTests):
    RISK = "high"

    @unittest.skip("commit-green is refused in MODE RED by design")
    def test_green_commit_still_commits_the_source(self):
        pass

    def test_red_mode_brief_and_clean_worktree(self):
        self.assertIn("MODE: RED", self.claim_out)
        self.assert_brief_discards_stubs(self.claim_out)


class TestIntegrateRejectsRedWithSource(RedFixture):
    def test_raw_red_commit_touching_source_is_rejected_naming_file(self):
        (self.wt / "tests" / "S1.test.js").write_text(TEST_JS)
        (self.wt / "src" / "S1.js").write_text("module.exports = 1;\n")
        git(["add", "-A"], self.wt)
        git(["commit", "-q", "-m", "test(S1): RED — hand rolled"], self.wt)
        r = run_dt(["integrate", "S1"], self.repo)
        out = r.stdout + r.stderr
        self.assertIn("REJECTED", out)
        self.assertIn("src/S1.js", out)
        self.assertIn("RED", out)

    def test_clean_red_then_green_still_integrates(self):
        (self.wt / "tests" / "S1.test.js").write_text(TEST_JS)
        self.assertEqual(run_dt(["commit-red", "S1"], self.wt).returncode, 0)
        (self.wt / "src" / "S1.js").write_text("module.exports = 1;\n")
        self.assertEqual(run_dt(["commit-green", "S1"], self.wt).returncode, 0)
        r = run_dt(["integrate", "S1"], self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("REJECTED", r.stdout + r.stderr)


class TestStageFootprintNoRenames(unittest.TestCase):
    def test_move_to_test_path_lists_old_and_new_names(self):
        repo = new_repo(self)
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "src" / "S1.js").write_text("".join("line %d\n" % i for i in range(30)))
        git(["add", "-A"], repo)
        git(["commit", "-q", "-m", "init"], repo)
        git(["mv", "src/S1.js", "tests/S1.test.js"], repo)
        spec = importlib.util.spec_from_file_location("devteam_under_test", DEVTEAM_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        staged = mod.stage_footprint(str(repo), ["src/S1.js", "tests/S1.test.js"])
        self.assertEqual(sorted(staged), ["src/S1.js", "tests/S1.test.js"])


if __name__ == "__main__":
    unittest.main()
