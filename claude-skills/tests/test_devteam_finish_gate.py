"""Black-box tests for T01: `finish` refuses to close a run whose checkpoint state is not clean.

Gate (all must hold unless --force): the last checkpoint passed, no checkpoint is pending, no
merge landed after the last checkpoint snapshot, and the verification verdict is not
CHANGES_REQUIRED. A run that merged nothing needs no checkpoint. --force still finishes and
prints exactly which conditions it bypassed.

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


class FinishGateTests(unittest.TestCase):

    def finishable_repo(self, **state_over):
        """A repo whose single slice G1 is merged, reviewed and checkpointed (gate fully green);
        `state_over` then overwrites top-level state keys to break one condition at a time."""
        repo = new_repo()
        self.addCleanup(shutil.rmtree, str(repo), True)
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "src" / ".keep").write_text("")
        (repo / "tests" / ".keep").write_text("")
        commit_all(repo, "init")
        plan = {
            "request": "T01 finish gate fixtures", "profile": "balanced",
            "commands": {"test": "none", "test_file": "none"},
            "slices": [{"id": "G1", "title": "g1", "files": ["src/g1.js", "tests/g1.test.js"],
                        "risk": "low", "criteria": ["works"]}],
        }
        (repo / "plan.md").write_text(PLAN_TMPL % json.dumps(plan))
        r = run_dt(["init", "plan.md"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
                              text=True, check=True).stdout.strip()
        sp = repo / ".claude" / "dev-team" / "state.json"
        st = json.loads(sp.read_text())
        st["slices"]["G1"].update({"status": "done", "merged_sha": head})
        st.update({"merges": ["G1"], "reviewed_upto": 1, "merges_since_checkpoint": 0,
                   "checkpoint_pending": False,
                   "checkpoints": [{"t": 1, "sha": head, "result": "pass", "note": ""}]})
        st.update(state_over)
        sp.write_text(json.dumps(st))
        return repo

    def assert_blocked(self, repo, needle):
        r = run_dt(["finish"], repo)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("finish gate", r.stderr)
        self.assertIn(needle, r.stderr)

    def test_clean_run_finishes(self):
        repo = self.finishable_repo()
        r = run_dt(["finish"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FINISHED", r.stdout)

    def test_run_with_no_merges_needs_no_checkpoint(self):
        repo = self.finishable_repo(merges=[], reviewed_upto=0, checkpoints=[])
        r = run_dt(["finish"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_failed_last_checkpoint_blocks(self):
        repo = self.finishable_repo(checkpoints=[{"t": 1, "sha": "a" * 40, "result": "fail", "note": ""}])
        self.assert_blocked(repo, "the last checkpoint result is fail, not pass")

    def test_missing_checkpoint_blocks(self):
        repo = self.finishable_repo(checkpoints=[])
        self.assert_blocked(repo, "no checkpoint has been recorded")

    def test_pending_checkpoint_blocks(self):
        repo = self.finishable_repo(checkpoint_pending={"n": 2, "sha": "b" * 40, "wt": "x", "merges_at": 1, "t": 1})
        self.assert_blocked(repo, "a checkpoint is still pending")

    def test_merge_after_last_checkpoint_blocks(self):
        repo = self.finishable_repo(merges_since_checkpoint=2)
        self.assert_blocked(repo, "2 merge(s) landed after the last checkpoint snapshot")

    def test_changes_required_verification_blocks(self):
        repo = self.finishable_repo(verification_verdict="CHANGES_REQUIRED")
        self.assert_blocked(repo, "the verification verdict is CHANGES_REQUIRED")

    def test_force_finishes_and_names_every_bypassed_condition(self):
        repo = self.finishable_repo(checkpoints=[], verification_verdict="CHANGES_REQUIRED")
        r = run_dt(["finish", "--force"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FINISH GATE BYPASSED", r.stdout)
        self.assertIn("no checkpoint has been recorded", r.stdout)
        self.assertIn("the verification verdict is CHANGES_REQUIRED", r.stdout)


if __name__ == "__main__":
    unittest.main()
