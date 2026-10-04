"""Black-box tests for the remaining `devteam.py finish` gate paths (T03).

tests/test_devteam_finish_gate.py pins the checkpoint conditions. This file pins the other
refusals and the happy-path output: slices not done, reviews not closed (open, no
verdict, CHANGES_REQUIRED), merged slices never sent to review, what --force prints, and
the PR-ready summary written on a clean finish.

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


def approved(rid="r1"):
    return {rid: {"status": "done", "verdict": "APPROVED", "slices": ["G1"], "shards": 1}}


class FinishPathTests(unittest.TestCase):

    def finishable_repo(self, slice_status="done", **state_over):
        """A repo whose single slice G1 is merged, reviewed (APPROVED) and checkpointed (pass);
        `slice_status` and `state_over` then break one condition at a time."""
        repo = new_repo()
        self.addCleanup(shutil.rmtree, str(repo), True)
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "src" / ".keep").write_text("")
        (repo / "tests" / ".keep").write_text("")
        commit_all(repo, "init")
        plan = {
            "request": "T03 finish paths", "profile": "balanced",
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
        st["slices"]["G1"].update({"status": slice_status, "merged_sha": head})
        st.update({"merges": ["G1"], "reviewed_upto": 1, "merges_since_checkpoint": 0,
                   "checkpoint_pending": False, "reviews": approved(),
                   "checkpoints": [{"t": 1, "sha": head, "result": "pass", "note": ""}]})
        st.update(state_over)
        sp.write_text(json.dumps(st))
        return repo

    def assert_refused(self, repo, needle):
        r = run_dt(["finish"], repo)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(needle, r.stderr)
        self.assertNotIn("FINISHED", r.stdout)

    def test_slice_not_done_blocks(self):
        repo = self.finishable_repo(slice_status="running")
        self.assert_refused(repo, "slices not done: G1")

    def test_force_finishes_with_a_slice_not_done(self):
        repo = self.finishable_repo(slice_status="running")
        r = run_dt(["finish", "--force"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FINISHED", r.stdout)

    def test_open_review_blocks(self):
        reviews = {"r1": {"status": "running", "verdict": None, "slices": ["G1"], "shards": 1}}
        repo = self.finishable_repo(reviews=reviews)
        self.assert_refused(repo, "reviews not closed: r1 (running/no verdict)")

    def test_changes_required_review_blocks(self):
        reviews = {"r1": {"status": "done", "verdict": "CHANGES_REQUIRED", "slices": ["G1"], "shards": 1}}
        repo = self.finishable_repo(reviews=reviews)
        self.assert_refused(repo, "r1 (done/CHANGES_REQUIRED)")

    def test_merged_slice_never_sent_to_review_blocks(self):
        repo = self.finishable_repo(reviewed_upto=0, reviews={})
        self.assert_refused(repo, "1 merged slice(s) never sent to review: G1")

    def test_force_names_the_open_reviews_it_bypassed(self):
        reviews = {"r1": {"status": "running", "verdict": None, "slices": ["G1"], "shards": 1}}
        repo = self.finishable_repo(reviews=reviews)
        r = run_dt(["finish", "--force"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("REVIEWS NOT CLOSED (finishing anyway because --force): r1 (running/no verdict)", r.stdout)

    def test_clean_finish_writes_the_pr_summary(self):
        repo = self.finishable_repo()
        r = run_dt(["finish"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FINISHED: 1 slices merged on", r.stdout)
        summary = repo / ".claude" / "dev-team" / "summary.md"
        self.assertIn("PR-ready summary written to", r.stdout)
        self.assertTrue(summary.is_file())
        text = summary.read_text()
        self.assertIn("## Summary", text)
        self.assertIn("T03 finish paths", text)
        self.assertIn("- **G1**", text)
        self.assertIn("review r1: APPROVED", text)


if __name__ == "__main__":
    unittest.main()
