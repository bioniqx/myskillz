"""Black-box + direct-import tests for T04: the model on review dispatch lines (decision D1) and
the release of idle review shards once a CHANGES_REQUIRED review has queued its fix slices.

Fixtures are real git repos under the SYSTEM temp dir, never inside this repo.
"""
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEVTEAM_PATH = str(Path(__file__).resolve().parents[1] / "claude-dev-team-v3.2" / "scripts" / "devteam.py")

spec = importlib.util.spec_from_file_location("devteam_under_test_review_model", DEVTEAM_PATH)
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)

FENCE = "`" * 3


def run_dt(args, cwd):
    return subprocess.run([sys.executable, DEVTEAM_PATH] + args, cwd=str(cwd),
                          capture_output=True, text=True, timeout=60)


def must(args, cwd):
    r = run_dt(args, cwd)
    assert r.returncode == 0, f"{args} failed: {r.stdout}{r.stderr}"
    return r


def git_run(args, cwd):
    subprocess.run(["git"] + args, cwd=str(cwd), check=True)


def make_repo(slice_ids, profile="balanced", review_batch=None):
    repo = Path(os.path.realpath(tempfile.mkdtemp()))
    git_run(["init", "-q", "-b", "main"], repo)
    for key, value in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        git_run(["config", key, value], repo)
    for d in ("src", "tests"):
        (repo / d).mkdir()
        (repo / d / ".keep").write_text("")
    git_run(["add", "-A"], repo)
    git_run(["commit", "-q", "-m", "init"], repo)
    plan = {"request": "T04 fixtures", "profile": profile,
            "commands": {"test": "none", "test_file": "none"},
            "slices": [{"id": sid, "title": sid.lower(),
                        "files": [f"src/{sid}.js", f"tests/{sid}.test.js"],
                        "risk": "low", "criteria": ["works"]} for sid in slice_ids]}
    if review_batch:
        plan["review_batch"] = review_batch
    (repo / "plan.md").write_text("# plan\n" + FENCE + "json\n" + json.dumps(plan) + "\n" + FENCE + "\n")
    must(["init", "plan.md"], repo)
    return repo


def merge(repo, sid):
    """Dispatch one slice, run RED then GREEN in its own worktree, and integrate it."""
    must(["dispatch", sid], repo)
    wt = Path(os.path.realpath(tempfile.mkdtemp())) / f"w-{sid}"
    git_run(["worktree", "add", "-q", str(wt), "-b", f"worktree-{sid}", "HEAD"], repo)
    must(["claim", sid], wt)
    (wt / "tests" / f"{sid}.test.js").write_text('test("x", () => { assert.equal(1, 1); });\n')
    must(["commit-red", sid], wt)
    (wt / "src" / f"{sid}.js").write_text("module.exports = 1;\n")
    git_run(["add", "-A"], wt)
    must(["commit-green", sid], wt)
    must(["integrate", sid], repo)


def report(verdict, fixes=None):
    text = f"## Verdict: {verdict}\n\nfindings\n"
    if fixes is not None:
        text += "\n" + FENCE + "json\n" + json.dumps({"fixes": fixes}) + "\n" + FENCE + "\n"
    return text


FIX = {"id": "F?", "title": "fix a", "files": ["src/a.py", "tests/test_a.py"],
       "criteria": ["a works"]}


class TestReviewDispatchModel(unittest.TestCase):
    def reviewer_line(self, out):
        m = re.search(r"^.*\b(?:code|spot)-reviewer\b.*$", out, re.M)
        self.assertIsNotNone(m, out)
        return m.group(0)

    def test_review_model_policy(self):
        self.assertEqual(dt.review_model(final=False, spot=False), "sonnet")
        self.assertEqual(dt.review_model(final=True, spot=False), "opus")
        self.assertEqual(dt.review_model(final=True, spot=True), "sonnet")
        self.assertEqual(dt.review_model(final=False, spot=True), "sonnet")

    def test_incremental_batch_review_runs_on_sonnet(self):
        repo = make_repo(["S1", "S2"], review_batch=1)
        merge(repo, "S1")
        line = self.reviewer_line(must(["review-batch"], repo).stdout)
        self.assertIn("claude-code-reviewer", line)
        self.assertTrue(line.endswith(", model: sonnet"), line)

    def test_next_opens_an_incremental_review_on_sonnet(self):
        repo = make_repo(["S1", "S2"], review_batch=1)
        merge(repo, "S1")
        out = must(["next"], repo).stdout
        self.assertIn("=== REVIEW r1", out)
        line = self.reviewer_line(out)
        self.assertTrue(line.endswith(", model: sonnet"), line)

    def test_forced_final_review_runs_on_opus(self):
        repo = make_repo(["S1"])
        merge(repo, "S1")
        line = self.reviewer_line(must(["review-batch", "--force"], repo).stdout)
        self.assertIn("claude-code-reviewer", line)
        self.assertTrue(line.endswith(", model: opus"), line)

    def test_next_opens_the_final_review_on_opus_when_the_dag_is_exhausted(self):
        repo = make_repo(["S1"])
        merge(repo, "S1")
        out = must(["next"], repo).stdout
        self.assertIn("=== REVIEW r1", out)
        line = self.reviewer_line(out)
        self.assertTrue(line.endswith(", model: opus"), line)

    def test_spot_depth_final_review_stays_on_sonnet(self):
        repo = make_repo(["S1"], profile="turbo")
        merge(repo, "S1")
        line = self.reviewer_line(must(["review-batch", "--force"], repo).stdout)
        self.assertIn("claude-spot-reviewer", line)
        self.assertTrue(line.endswith(", model: sonnet"), line)


class TestReviewShardsStayReserved(unittest.TestCase):
    """The Conductor resumes a CHANGES_REQUIRED reviewer for the re-review, so its shards stay reserved."""

    def harvest(self, text):
        root = Path(os.path.realpath(tempfile.mkdtemp()))
        reviews = dt.state_dir(root) / "reviews"
        reviews.mkdir(parents=True)
        (reviews / "r1.report.md").write_text(text)
        st = {"slices": {}, "fix_counter": 0,
              "reviews": {"r1": {"slices": [], "status": "reported", "shards": 1, "verdict": None}}}
        dt.harvest_reviews(root, st)
        return st

    def test_shards_stay_reserved_after_fix_slices_are_queued(self):
        st = self.harvest(report("CHANGES_REQUIRED", [FIX]))
        self.assertEqual(st["reviews"]["r1"]["verdict"], "CHANGES_REQUIRED")
        self.assertIn("F1", st["slices"])
        self.assertEqual(dt.reserved_slots(st), dt.RESERVED_MIN + 1)

    def test_shards_stay_reserved_when_no_fix_slice_was_queued(self):
        st = self.harvest(report("CHANGES_REQUIRED"))
        self.assertEqual(dt.reserved_slots(st), dt.RESERVED_MIN + 1)

    def test_only_non_approved_shards_are_reserved(self):
        st = {"reviews": {"r1": {"status": "done", "verdict": "CHANGES_REQUIRED", "shards": 3,
                                  "shard_verdicts": ["APPROVED", "CHANGES_REQUIRED", "CHANGES_REQUIRED"]}}}
        self.assertEqual(dt.reserved_slots(st), dt.RESERVED_MIN + 2)


if __name__ == "__main__":
    unittest.main()
