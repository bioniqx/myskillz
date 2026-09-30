"""K23: fail/retry/finish never lose a lane's uncommitted work.

Black-box: real devteam.py subprocesses against disposable git repos in the SYSTEM temp dir.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEVTEAM_PATH = str(Path(__file__).resolve().parents[1] / "dev-team-v3.2" / "scripts" / "devteam.py")


def run_dt(args, cwd, env=None):
    return subprocess.run([sys.executable, DEVTEAM_PATH] + args, cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=60)


def git(args, cwd):
    return subprocess.run(["git"] + args, cwd=str(cwd), check=True, capture_output=True, text=True).stdout


class SalvageFixture(unittest.TestCase):
    def setUp(self):
        repo = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(repo), True)
        for a in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"],
                  ["config", "user.name", "t"], ["config", "commit.gpgsign", "false"]):
            git(a, repo)
        (repo / "src").mkdir()
        (repo / "src" / "S1.js").write_text("module.exports = 0;\n")
        git(["add", "-A"], repo)
        git(["commit", "-q", "-m", "init"], repo)
        plan = {"request": "K23", "profile": "balanced",
                "commands": {"test": "none", "test_file": "none"},
                "slices": [{"id": "S1", "title": "s1", "files": ["src/S1.js", "src/new.js"],
                            "risk": "low", "criteria": ["works"]}]}
        (repo / "plan.md").write_text("# plan\n```json\n%s\n```\n" % json.dumps(plan))
        self.assertEqual(run_dt(["init", "plan.md"], repo).returncode, 0)
        self.assertEqual(run_dt(["dispatch", "S1"], repo).returncode, 0)
        git(["worktree", "add", "-q", ".claude/worktrees/w1", "-b", "worktree-w1", "HEAD"], repo)
        self.repo = repo
        self.wt = repo / ".claude" / "worktrees" / "w1"
        r = run_dt(["claim", "S1"], self.wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.main_head = git(["rev-parse", "HEAD"], repo).strip()

    def dirty(self):
        (self.wt / "src" / "S1.js").write_text("module.exports = 42;\n")  # tracked change
        (self.wt / "src" / "new.js").write_text("module.exports = 'new';\n")  # untracked

    def kept_branch(self):
        return git(["branch", "--list", "attempt/S1-*", "--format=%(refname:short)"], self.repo).split()


class TestSalvageOnRetry(SalvageFixture):
    def test_dirty_worktree_is_committed_onto_kept_branch(self):
        self.dirty()
        r = run_dt(["retry", "S1"], self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        kept = self.kept_branch()
        self.assertEqual(len(kept), 1, kept)
        self.assertEqual(git(["log", "-1", "--format=%s", kept[0]], self.repo).strip(), "wip(S1): salvage")
        self.assertEqual(git(["show", kept[0] + ":src/S1.js"], self.repo), "module.exports = 42;\n")
        self.assertEqual(git(["show", kept[0] + ":src/new.js"], self.repo), "module.exports = 'new';\n")
        self.assertIn(kept[0], r.stdout)
        self.assertIn("salvage", r.stdout)
        self.assertFalse(self.wt.exists())

    def test_salvage_never_lands_on_integration_branch(self):
        self.dirty()
        self.assertEqual(run_dt(["retry", "S1"], self.repo).returncode, 0)
        self.assertEqual(git(["rev-parse", "main"], self.repo).strip(), self.main_head)
        self.assertEqual((self.repo / "src" / "S1.js").read_text(), "module.exports = 0;\n")
        self.assertFalse((self.repo / "src" / "new.js").exists())

    def test_clean_worktree_gets_no_wip_commit(self):
        r = run_dt(["retry", "S1"], self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        kept = self.kept_branch()
        self.assertEqual(len(kept), 1, kept)
        self.assertEqual(git(["rev-parse", kept[0]], self.repo).strip(), self.main_head)
        self.assertNotIn("salvage", r.stdout)
        self.assertFalse(self.wt.exists())


class TestSalvageIdContainingPatch(unittest.TestCase):
    def test_finish_force_on_patch_named_slice_keeps_salvage_branch(self):
        plan = {"request": "K25", "profile": "balanced",
                "commands": {"test": "none", "test_file": "none"},
                "slices": [{"id": "patchfix", "title": "p", "files": ["src/new.js"],
                            "risk": "low", "criteria": ["works"]}]}
        repo = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(repo), True)
        for a in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"],
                  ["config", "user.name", "t"], ["config", "commit.gpgsign", "false"]):
            git(a, repo)
        (repo / "src").mkdir()
        (repo / "src" / "S1.js").write_text("x\n")
        git(["add", "-A"], repo)
        git(["commit", "-q", "-m", "init"], repo)
        (repo / "plan.md").write_text("# plan\n```json\n%s\n```\n" % json.dumps(plan))
        self.assertEqual(run_dt(["init", "plan.md"], repo).returncode, 0)
        self.assertEqual(run_dt(["dispatch", "patchfix"], repo).returncode, 0)
        git(["worktree", "add", "-q", ".claude/worktrees/w2", "-b", "worktree-w2", "HEAD"], repo)
        wt = repo / ".claude" / "worktrees" / "w2"
        self.assertEqual(run_dt(["claim", "patchfix"], wt).returncode, 0)
        (wt / "src" / "new.js").write_text("module.exports = 'new';\n")
        run_dt(["finish", "--force"], repo)
        branches = git(["branch", "--list", "attempt/patchfix-*", "--format=%(refname:short)"], repo).split()
        self.assertEqual(len(branches), 1, branches)
        self.assertEqual(git(["log", "-1", "--format=%s", branches[0]], repo).strip(), "wip(patchfix): salvage")


class TestSalvageIgnoresGpgSign(SalvageFixture):
    def test_salvage_commit_works_when_signing_is_forced_on_with_a_broken_program(self):
        git(["config", "commit.gpgsign", "true"], self.repo)
        git(["config", "gpg.program", "/nonexistent/gpg"], self.repo)
        self.dirty()
        r = run_dt(["retry", "S1"], self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        kept = self.kept_branch()
        self.assertEqual(len(kept), 1, kept)
        self.assertEqual(git(["log", "-1", "--format=%s", kept[0]], self.repo).strip(), "wip(S1): salvage")


class TestRetryNamesBranchOnlyWhenRenamed(SalvageFixture):
    def test_no_kept_message_when_branch_rename_fails(self):
        cf = self.repo / ".claude" / "dev-team" / "slices" / "S1.claim.json"
        claim = json.loads(cf.read_text())
        claim["branch"] = "worktree-does-not-exist"   # rename of a missing branch fails
        cf.write_text(json.dumps(claim))
        r = run_dt(["retry", "S1"], self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("previous branch kept", r.stdout)
        self.assertNotIn("attempt/S1-", r.stdout)

    def test_kept_message_when_branch_renamed(self):
        r = run_dt(["retry", "S1"], self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(len(self.kept_branch()), 1)
        self.assertIn("previous branch kept as " + self.kept_branch()[0], r.stdout)


class TestSalvageOnFinish(SalvageFixture):
    def test_finish_force_salvages_dirty_worktree(self):
        self.dirty()
        r = run_dt(["finish", "--force"], self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("salvage", r.stdout, r.stdout + r.stderr)
        self.assertFalse(self.wt.exists())
        branches = git(["branch", "--list", "--format=%(refname:short)"], self.repo).split()
        found = [b for b in branches if b != "main" and
                 git(["log", "-1", "--format=%s", b], self.repo).strip() == "wip(S1): salvage"]
        self.assertTrue(found, branches)
        self.assertEqual(git(["rev-parse", "main"], self.repo).strip(), self.main_head)

    def test_failed_salvage_commit_falls_back_to_patch_file(self):
        self.dirty()
        git(["config", "--unset", "user.email"], self.repo)
        git(["config", "--unset", "user.name"], self.repo)
        git(["config", "user.useConfigOnly", "true"], self.repo)
        home = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, home, True)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env.update(HOME=home, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        r = run_dt(["finish", "--force"], self.repo, env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        patches = list((self.repo / ".claude" / "dev-team" / "salvage").glob("S1-*.patch"))
        self.assertEqual(len(patches), 1, r.stdout + r.stderr)
        self.assertIn(str(patches[0]), r.stdout)
        self.assertIn("module.exports = 42;", patches[0].read_text())


if __name__ == "__main__":
    unittest.main()
