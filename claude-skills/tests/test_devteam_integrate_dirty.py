"""Black-box tests for T02: `integrate` blocks only on dirty paths the slice itself changes.

An uncommitted tracked change elsewhere in the integration checkout (for example an agent file
that `doctor --fix` rewrote) must not abort the whole call. A dirty path that the slice also
changes is rejected for that slice only, and the slice stays in flight.

Fixtures are real git repos under the SYSTEM temp dir; the engine runs as a subprocess.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEVTEAM_PATH = str(Path(__file__).resolve().parents[1] / "claude-dev-team-v3.2" / "scripts" / "devteam.py")

FENCE = "`" * 3
PLAN_TMPL = "# plan\n" + FENCE + "json\n%s\n" + FENCE + "\n"


def run_dt(args, cwd):
    return subprocess.run([sys.executable, DEVTEAM_PATH] + args, cwd=str(cwd),
                          capture_output=True, text=True, timeout=60)


def new_repo():
    d = Path(os.path.realpath(tempfile.mkdtemp()))
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=d, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=d, check=True)
    return d


def commit_all(d, msg):
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=d, check=True)


def slice_spec(sid):
    low = sid.lower()
    return {"id": sid, "title": low, "files": [f"src/{low}.js", f"tests/{low}.test.js"],
            "risk": "low", "criteria": ["works"]}


class IntegrateDirtyRootTests(unittest.TestCase):

    def make_repo(self, sids, extra_files):
        repo = new_repo()
        self.addCleanup(shutil.rmtree, str(repo), True)
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "src" / ".keep").write_text("")
        (repo / "tests" / ".keep").write_text("")
        for rel, content in extra_files.items():
            (repo / rel).write_text(content)
        commit_all(repo, "init")
        plan = {"request": "T02 dirty-root fixtures", "profile": "balanced",
                "commands": {"test": "none", "test_file": "none"},
                "slices": [slice_spec(sid) for sid in sids]}
        (repo / "plan.md").write_text(PLAN_TMPL % json.dumps(plan))
        r = run_dt(["init", "plan.md"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return repo

    def deliver(self, repo, sid, wt_name, src_text):
        """Dispatch and claim `sid` in its own worktree, commit RED then GREEN there, and leave
        the branch ready for `integrate`."""
        low = sid.lower()
        r = run_dt(["dispatch", sid], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        subprocess.run(["git", "worktree", "add", "-q", f".claude/worktrees/{wt_name}",
                        "-b", f"worktree-{wt_name}", "HEAD"], cwd=repo, check=True)
        wt = repo / ".claude" / "worktrees" / wt_name
        r = run_dt(["claim", sid], wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (wt / "tests" / f"{low}.test.js").write_text(f'test("{low}", () => {{ assert.equal(1, 1); }});\n')
        r = run_dt(["commit-red", low], wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (wt / "src" / f"{low}.js").write_text(src_text)
        r = run_dt(["commit-green", low], wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_unrelated_dirty_tracked_file_does_not_block(self):
        repo = self.make_repo(["D1"], {"README.md": "hello\n"})
        self.deliver(repo, "D1", "w1", "module.exports = 1;\n")
        (repo / "README.md").write_text("local notes\n")
        r = run_dt(["integrate", "D1"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("D1: MERGED", r.stdout)
        self.assertEqual((repo / "README.md").read_text(), "local notes\n")
        self.assertEqual((repo / "src" / "d1.js").read_text(), "module.exports = 1;\n")

    def test_dirty_path_the_slice_changes_is_rejected_for_that_slice(self):
        repo = self.make_repo(["D2"], {"src/d2.js": "old\n"})
        self.deliver(repo, "D2", "w2", "new\n")
        (repo / "src" / "d2.js").write_text("local edit\n")
        r = run_dt(["integrate", "D2"], repo)
        out = r.stdout + r.stderr
        self.assertIn("NOT INTEGRATED", out)
        self.assertIn("src/d2.js", out)
        self.assertEqual((repo / "src" / "d2.js").read_text(), "local edit\n")
        state = json.loads((repo / ".claude" / "dev-team" / "state.json").read_text())
        self.assertEqual(state["slices"]["D2"]["status"], "inflight")

    def test_one_blocked_slice_does_not_stop_the_others(self):
        repo = self.make_repo(["D3", "D4"], {"src/d3.js": "old\n"})
        self.deliver(repo, "D3", "w3", "new\n")
        self.deliver(repo, "D4", "w4", "module.exports = 4;\n")
        (repo / "src" / "d3.js").write_text("local edit\n")
        r = run_dt(["integrate", "D3", "D4"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("D3: NOT INTEGRATED", r.stdout)
        self.assertIn("D4: MERGED", r.stdout)
        self.assertEqual((repo / "src" / "d4.js").read_text(), "module.exports = 4;\n")


if __name__ == "__main__":
    unittest.main()
