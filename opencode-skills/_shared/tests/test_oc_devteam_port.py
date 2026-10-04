"""Parity tests: the oc engine behaves like the reference engine on the ported P0 fixes.

Fixtures are real git repos under the SYSTEM temp dir (realpath-resolved); the engine is run as a
subprocess for CLI behaviour and imported for pure helpers.
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

ENGINE = Path(__file__).resolve().parents[2] / "oc-dev-team" / "scripts" / "oc_devteam.py"
_SPEC = importlib.util.spec_from_file_location("oc_devteam_port_under_test", str(ENGINE))
DT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(DT)

FENCE = "`" * 3
PLAN_TMPL = "# plan\n" + FENCE + "json\n%s\n" + FENCE + "\n"
STATE_REL = Path(".opencode") / "oc-dev-team"


def run_dt(args, cwd):
    return subprocess.run([sys.executable, str(ENGINE)] + args, cwd=str(cwd),
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


def plan_text(slices):
    plan = {"request": "port parity fixtures", "profile": "balanced",
            "commands": {"test": "none", "test_file": "none"}, "slices": slices}
    return PLAN_TMPL % json.dumps(plan)


class PathMatchesTests(unittest.TestCase):
    def test_footprint_env_does_not_match_dotenv(self):
        self.assertFalse(DT.path_matches(".env", "env"))

    def test_footprint_dir_does_not_match_dot_dir(self):
        self.assertFalse(DT.path_matches(".claude/x", "claude/"))

    def test_literal_dot_slash_is_stripped(self):
        self.assertTrue(DT.path_matches("./src/a.py", "src"))
        self.assertTrue(DT.path_matches("src/a.py", "./src/"))


class PlanHelperTests(unittest.TestCase):
    def test_research_slice_holds_no_footprint(self):
        self.assertEqual(DT.plan_fp({"kind": "research", "files": ["src/a.py"]}), [])
        self.assertEqual(DT.plan_fp({"files": ["src/a.py"]}), ["src/a.py"])

    def test_malformed_slice_types_raise_clean_error(self):
        with self.assertRaises(DT.DevteamError):
            DT.validate_slice_types([{"id": "S1", "files": "src/a.py"}])
        with self.assertRaises(DT.DevteamError):
            DT.validate_slice_types([{"id": 7, "files": ["a"]}])

    def test_next_fix_id_skips_taken_ids(self):
        st = {"fix_counter": 0, "slices": {"F1": {}}}
        self.assertEqual(DT.next_fix_id(st), "F2")
        self.assertEqual(st["fix_counter"], 2)

    def test_pytest_raises_counts_as_an_assertion(self):
        self.assertTrue(DT.ASSERT_TOKENS.search("with pytest.raises(ValueError):\n    f()"))


class EngineSourceTests(unittest.TestCase):
    def test_diff_calls_use_no_renames_and_red_source_is_rejected(self):
        text = ENGINE.read_text()
        self.assertIn("red-touches-source", text)
        self.assertNotIn('["diff", "--name-only"', text)
        self.assertNotIn('["show", "--name-only"', text)


class RepoCase(unittest.TestCase):
    def repo_with_plan(self, slices):
        repo = new_repo()
        self.addCleanup(shutil.rmtree, str(repo), True)
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "src" / ".keep").write_text("")
        (repo / "tests" / ".keep").write_text("")
        commit_all(repo, "init")
        (repo / "plan.md").write_text(plan_text(slices))
        return repo


class ReadyAndInitTests(RepoCase):
    SLICES = [{"id": "S1", "title": "s1", "files": ["src/a.py", "tests/a.py"], "criteria": ["c"]},
              {"id": "S2", "title": "s2", "files": ["src/b.py", "tests/b.py"], "criteria": ["c"]},
              {"id": "S3", "title": "s3", "kind": "research", "files": ["src/c.py"], "criteria": ["c"]}]

    def test_red_done_slice_still_holds_its_footprint(self):
        repo = self.repo_with_plan(self.SLICES)
        self.assertEqual(run_dt(["init", "plan.md"], repo).returncode, 0)
        st = DT.load_state(repo)
        st["slices"]["S1"]["status"] = "red-done"
        st["slices"]["S2"]["files"] = ["src/a.py"]
        st["slices"]["S3"]["files"] = ["src/a.py"]
        ready, _ = DT.ready_slices(st)
        self.assertNotIn("S2", ready)
        self.assertIn("S3", ready)

    def test_init_force_clears_stale_reviews_logs_research(self):
        repo = self.repo_with_plan(self.SLICES)
        self.assertEqual(run_dt(["init", "plan.md"], repo).returncode, 0)
        stale = repo / STATE_REL / "reviews" / "r1.report.md"
        stale.write_text("## Review verdict: APPROVED\n")
        old_log = repo / STATE_REL / "logs" / "checkpoint-1.log"
        old_log.write_text("old\n")
        r = run_dt(["init", "--force", "plan.md"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(stale.exists())
        self.assertFalse(old_log.exists())


class FinishGateTests(RepoCase):
    def finishable_repo(self, **state_over):
        repo = self.repo_with_plan([{"id": "G1", "title": "g1", "files": ["src/g1.js", "tests/g1.test.js"],
                                     "risk": "low", "criteria": ["works"]}])
        self.assertEqual(run_dt(["init", "plan.md"], repo).returncode, 0)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
                              text=True, check=True).stdout.strip()
        sp = repo / STATE_REL / "state.json"
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
        r = run_dt(["finish"], self.finishable_repo())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FINISHED", r.stdout)

    def test_missing_checkpoint_blocks(self):
        self.assert_blocked(self.finishable_repo(checkpoints=[]), "no checkpoint has been recorded")

    def test_failed_last_checkpoint_blocks(self):
        repo = self.finishable_repo(checkpoints=[{"t": 1, "sha": "a" * 40, "result": "fail", "note": ""}])
        self.assert_blocked(repo, "the last checkpoint result is fail, not pass")

    def test_pending_checkpoint_blocks(self):
        repo = self.finishable_repo(checkpoint_pending={"n": 2, "sha": "b" * 40, "wt": "x", "merges_at": 1, "t": 1})
        self.assert_blocked(repo, "a checkpoint is still pending")

    def test_merge_after_last_checkpoint_blocks(self):
        self.assert_blocked(self.finishable_repo(merges_since_checkpoint=2),
                            "2 merge(s) landed after the last checkpoint snapshot")

    def test_changes_required_verification_blocks(self):
        self.assert_blocked(self.finishable_repo(verification_verdict="CHANGES_REQUIRED"),
                            "the verification verdict is CHANGES_REQUIRED")

    def test_merged_slices_never_reviewed_block(self):
        r = run_dt(["finish"], self.finishable_repo(reviewed_upto=0))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("reviews not closed", r.stderr)
        self.assertIn("never sent to review", r.stderr)

    def test_force_finishes_and_names_the_bypassed_gate(self):
        repo = self.finishable_repo(checkpoints=[], verification_verdict="CHANGES_REQUIRED")
        r = run_dt(["finish", "--force"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FINISH GATE BYPASSED", r.stdout)
        self.assertIn("no checkpoint has been recorded", r.stdout)


class WorktreeTests(RepoCase):
    def test_salvage_commits_uncommitted_lane_work(self):
        repo = self.repo_with_plan([{"id": "S1", "title": "s1", "files": ["src/a.py"], "criteria": ["c"]}])
        commit_all(repo, "plan")
        wt = repo.parent / (repo.name + "-wt")
        self.addCleanup(shutil.rmtree, str(wt), True)
        subprocess.run(["git", "worktree", "add", "-q", "-b", "lane", str(wt)], cwd=repo, check=True)
        (wt / "src" / "new.py").write_text("x = 1\n")
        res = DT.salvage_worktree(repo, "S1", str(wt), 1)
        self.assertEqual(res["kind"], "commit")
        log = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=wt, capture_output=True,
                             text=True, check=True).stdout.strip()
        self.assertEqual(log, "wip(S1): salvage")
        self.assertIsNone(DT.salvage_worktree(repo, "S1", str(wt), 1))

    def test_remove_worktree_never_removes_the_integration_checkout(self):
        repo = self.repo_with_plan([{"id": "S1", "title": "s1", "files": ["src/a.py"], "criteria": ["c"]}])
        DT.remove_worktree(repo, str(repo))
        self.assertTrue((repo / ".git").exists())
        self.assertTrue((repo / "plan.md").exists())


if __name__ == "__main__":
    unittest.main()
