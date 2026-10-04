"""Parity tests for the glm devteam.py engine against the original v3.2 engine.

Fixtures are real git repos under the SYSTEM temp dir (realpath); the engine runs as a subprocess or is
imported from its path. HOME, transcripts and every DEVTEAM_* / OPENCODE* variable are pinned per call.
"""
import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DT_PATH = str(Path(__file__).resolve().parents[2] / "dev-team-glm" / "scripts" / "devteam.py")
FENCE = "`" * 3
PLAN_TMPL = "# plan\n" + FENCE + "json\n%s\n" + FENCE + "\n"


def load_dt():
    spec = importlib.util.spec_from_file_location("glm_devteam_under_test", DT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DT = load_dt()


def clean_env(tmp):
    env = dict(os.environ)
    for k in list(env):
        if k.startswith(("DEVTEAM_", "OPENCODE", "HYBRID_")):
            del env[k]
    (tmp / "home").mkdir(exist_ok=True)
    (tmp / "tx").mkdir(exist_ok=True)
    env.update(HOME=str(tmp / "home"), XDG_DATA_HOME=str(tmp / "home"), DEVTEAM_PROVIDER="anthropic",
               DEVTEAM_HARNESS="claude", DEVTEAM_TRANSCRIPTS_DIR=str(tmp / "tx"))
    return env


class Base(unittest.TestCase):
    def new_repo(self):
        tmp = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        self.env = clean_env(tmp)
        repo = tmp / "repo"
        repo.mkdir()
        for args in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"],
                     ["config", "user.name", "t"], ["config", "commit.gpgsign", "false"]):
            subprocess.run(["git"] + args, cwd=repo, check=True)
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "src" / ".keep").write_text("")
        (repo / "tests" / ".keep").write_text("")
        self.commit_all(repo, "init")
        return repo

    @staticmethod
    def commit_all(repo, msg):
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", msg], cwd=repo, check=True)

    def dt(self, args, repo):
        return subprocess.run([sys.executable, DT_PATH] + args, cwd=str(repo), capture_output=True,
                              text=True, timeout=90, env=self.env)

    def init_plan(self, repo, slices, extra=None, force=False):
        plan = {"request": "parity", "profile": "balanced", "commands": {"test": "none", "test_file": "none"},
                "slices": slices}
        plan.update(extra or {})
        (repo / "plan.md").write_text(PLAN_TMPL % json.dumps(plan))
        r = self.dt(["init", "plan.md"] + (["--force"] if force else []), repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    @staticmethod
    def state_path(repo):
        return repo / ".claude" / "dev-team" / "state.json"

    def edit_state(self, repo, fn):
        sp = self.state_path(repo)
        st = json.loads(sp.read_text())
        fn(st)
        sp.write_text(json.dumps(st))


def slice_(sid, files, **kw):
    d = {"id": sid, "title": sid, "files": files, "risk": "low", "criteria": ["works"]}
    d.update(kw)
    return d


class PathMatchesTests(unittest.TestCase):
    def test_only_a_literal_dot_slash_is_stripped(self):
        self.assertFalse(DT.path_matches(".env", "env"))
        self.assertFalse(DT.path_matches(".claude/x", "claude/"))
        self.assertTrue(DT.path_matches("./src/a.py", "src/a.py"))
        self.assertTrue(DT.path_matches("src/a/b.py", "./src/"))


class PlanValidationTests(Base):
    def test_malformed_plan_is_a_clean_error(self):
        repo = self.new_repo()
        (repo / "plan.md").write_text(PLAN_TMPL % json.dumps(
            {"request": "x", "slices": [{"id": 7, "files": "src/a.py"}]}))
        r = self.dt(["init", "plan.md"], repo)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("invalid plan", r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_validate_slice_types_and_plan_fp(self):
        with self.assertRaises(DT.DevteamError) as ctx:
            DT.validate_slice_types([{"id": "S1", "deps": "S0"}])
        self.assertIn("deps must be a list of strings", str(ctx.exception))
        self.assertEqual(DT.plan_fp({"kind": "research", "files": ["a"]}), [])
        self.assertEqual(DT.plan_fp({"files": ["a"]}), ["a"])

    def test_research_slice_may_have_no_files(self):
        repo = self.new_repo()
        self.init_plan(repo, [slice_("R1", [], kind="research")])


class ReadyFootprintTests(Base):
    def test_red_done_holds_its_footprint_and_research_is_exempt(self):
        repo = self.new_repo()
        self.init_plan(repo, [slice_("S1", ["src/a.py", "tests/a.test.js"]), slice_("S2", ["src/a.py"]),
                              slice_("R1", ["src/a.py"], kind="research")])
        self.edit_state(repo, lambda st: st["slices"]["S1"].update({"status": "red-done"}))
        st = DT.load_state(repo)
        ready, _ = DT.ready_slices(st)
        self.assertIn("S1", ready)
        self.assertIn("R1", ready)
        self.assertNotIn("S2", ready)


class FinishGateTests(Base):
    def finishable_repo(self, **over):
        repo = self.new_repo()
        self.init_plan(repo, [slice_("G1", ["src/g1.js", "tests/g1.test.js"])])
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True,
                              check=True).stdout.strip()

        def fix(st):
            st["slices"]["G1"].update({"status": "done", "merged_sha": head})
            st.update({"merges": ["G1"], "reviewed_upto": 1, "merges_since_checkpoint": 0,
                       "checkpoint_pending": False,
                       "checkpoints": [{"t": 1, "sha": head, "result": "pass", "note": ""}]})
            st.update(over)
        self.edit_state(repo, fix)
        return repo

    def assert_blocked(self, repo, needle):
        r = self.dt(["finish"], repo)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(needle, r.stderr)

    def test_clean_run_finishes(self):
        r = self.dt(["finish"], self.finishable_repo())
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FINISHED", r.stdout)

    def test_gate_conditions_block(self):
        self.assert_blocked(self.finishable_repo(checkpoints=[]), "no checkpoint has been recorded")
        self.assert_blocked(self.finishable_repo(
            checkpoints=[{"t": 1, "sha": "a" * 40, "result": "fail", "note": ""}]),
            "the last checkpoint result is fail, not pass")
        self.assert_blocked(self.finishable_repo(
            checkpoint_pending={"n": 2, "sha": "b" * 40, "wt": "x", "merges_at": 1, "t": 1}),
            "a checkpoint is still pending")
        self.assert_blocked(self.finishable_repo(merges_since_checkpoint=2),
                            "2 merge(s) landed after the last checkpoint snapshot")
        self.assert_blocked(self.finishable_repo(verification_verdict="CHANGES_REQUIRED"),
                            "the verification verdict is CHANGES_REQUIRED")

    def test_merged_slice_never_sent_to_review_blocks(self):
        self.assert_blocked(self.finishable_repo(reviewed_upto=0), "never sent to review")

    def test_force_names_every_bypassed_condition(self):
        r = self.dt(["finish", "--force"], self.finishable_repo(
            checkpoints=[], verification_verdict="CHANGES_REQUIRED"))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FINISH GATE BYPASSED", r.stdout)
        self.assertIn("no checkpoint has been recorded", r.stdout)


class WorktreeTests(Base):
    def make_worktree(self, repo):
        wt = repo.parent / "wt1"
        subprocess.run(["git", "worktree", "add", "-q", "-b", "devteam/S9", str(wt)], cwd=repo, check=True)
        return wt

    def test_salvage_commits_uncommitted_lane_work(self):
        repo = self.new_repo()
        wt = self.make_worktree(repo)
        self.assertIsNone(DT.salvage_worktree(repo, "S9", str(wt), 1))
        (wt / "src" / "new.py").write_text("x = 1\n")
        res = DT.salvage_worktree(repo, "S9", str(wt), 1)
        self.assertEqual(res["kind"], "commit")
        subject = subprocess.run(["git", "log", "-1", "--format=%s"], cwd=wt, capture_output=True,
                                 text=True).stdout.strip()
        self.assertEqual(subject, "wip(S9): salvage")

    def test_remove_worktree_never_removes_the_integration_checkout(self):
        repo = self.new_repo()
        DT.remove_worktree(repo, str(repo))
        self.assertTrue((repo / ".git").exists())

    def test_remove_worktree_removes_a_locked_worktree(self):
        repo = self.new_repo()
        wt = self.make_worktree(repo)
        subprocess.run(["git", "worktree", "lock", str(wt)], cwd=repo, check=True)
        DT.remove_worktree(repo, str(wt))
        self.assertFalse(wt.exists())


class FixQueueTests(Base):
    def test_next_fix_id_skips_taken_ids(self):
        st = {"fix_counter": 0, "slices": {"F1": {}}}
        self.assertEqual(DT.next_fix_id(st), "F2")
        self.assertEqual(st["fix_counter"], 2)

    def add_fixes(self, specs):
        repo = self.new_repo()
        self.init_plan(repo, [slice_("G1", ["src/g1.js", "tests/g1.test.js"])])
        (repo / "report.md").write_text("## Fix slices\n" + FENCE + "json\n" + json.dumps({"fixes": specs})
                                        + "\n" + FENCE + "\n")
        r = self.dt(["add-fixes", "report.md"], repo)
        return repo, r

    def test_docs_only_fix_becomes_a_docs_slice(self):
        repo, r = self.add_fixes([{"id": "F?", "title": "doc", "files": ["docs/a.md"], "criteria": ["c"]}])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = json.loads(self.state_path(repo).read_text())
        self.assertEqual(st["slices"]["F1"]["kind"], "docs")

    def test_fix_without_test_path_becomes_chore_with_a_note(self):
        repo, r = self.add_fixes([{"id": "F?", "title": "src", "files": ["src/x.py"], "criteria": ["c"]}])
        self.assertIn("has no test path", r.stdout)
        st = json.loads(self.state_path(repo).read_text())
        self.assertEqual(st["slices"]["F1"]["kind"], "chore")

    def test_explicit_code_fix_without_test_path_notes_it(self):
        repo, r = self.add_fixes([{"id": "F?", "title": "src", "files": ["src/y.py"], "criteria": ["c"],
                                   "kind": "code"}])
        self.assertIn("explicit code slice", r.stdout)

    def test_non_object_fix_spec_is_refused(self):
        repo, r = self.add_fixes(["not an object"])
        self.assertIn("must be an object", r.stdout + r.stderr)


class InitForceTests(Base):
    def test_init_force_clears_stale_reviews_logs_and_research(self):
        repo = self.new_repo()
        self.init_plan(repo, [slice_("G1", ["src/g1.js", "tests/g1.test.js"])])
        sd = repo / ".claude" / "dev-team"
        for rel in ("reviews/r1.report.md", "logs/checkpoint-1.log", "research/R1.md"):
            (sd / rel).write_text("## Review verdict: APPROVED\nEXIT=0\n")
        self.init_plan(repo, [slice_("G1", ["src/g1.js", "tests/g1.test.js"])], force=True)
        for rel in ("reviews/r1.report.md", "logs/checkpoint-1.log", "research/R1.md"):
            self.assertFalse((sd / rel).exists(), rel)


class DoctorAndStatsTests(Base):
    def test_dirty_excluding_drops_what_doctor_wrote(self):
        root = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(root), True)
        kept = DT.dirty_excluding(root, [(" M", "a.txt"), (" M", "b.txt")], [root / "a.txt"])
        self.assertEqual(kept, [(" M", "b.txt")])

    def test_assert_tokens_accept_pytest_raises(self):
        self.assertTrue(DT.ASSERT_TOKENS.search("with pytest.raises(ValueError):\n    f()"))

    def test_shard_verdicts_reserve_only_shards_that_asked_for_changes(self):
        st = {"reviews": {"r1": {"status": "done", "verdict": "CHANGES_REQUIRED", "shards": 4,
                                 "shard_verdicts": ["APPROVED", "CHANGES_REQUIRED", "APPROVED", "APPROVED"]}}}
        self.assertEqual(DT.reserved_slots(st), DT.reserve_min(st) + 1)

    def test_stall_detection(self):
        root = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(root), True)
        self.assertEqual(DT.STALL_MINUTES_DEFAULT, 20)
        st = {"slices": {"S1": {"status": "inflight", "dispatched": 1000, "history": []}}}
        self.assertEqual(DT.stalled_lanes(root, st, now_ts=1000 + 25 * 60), [("S1", 25)])
        self.assertEqual(DT.stalled_lanes(root, st, now_ts=1000 + 60), [])


class SourceParityTests(unittest.TestCase):
    def test_integration_and_red_guards_are_present(self):
        self.assertIn("red-touches-source", inspect.getsource(DT.integrate_one))
        self.assertIn("dirty-root", inspect.getsource(DT.merge_slice))
        self.assertNotIn("uncommitted tracked changes — commit/stash first", inspect.getsource(DT.do_integrate))
        self.assertIn("--no-renames", inspect.getsource(DT.stage_footprint))
        self.assertIn("--no-renames", inspect.getsource(DT.integrate_one))
        self.assertIn("discarded", inspect.getsource(DT.cmd_commit_red))
        self.assertIn("UNRESOLVED", inspect.getsource(DT.print_ready))
        self.assertIn("endgame_shown", inspect.getsource(DT.cmd_next))
        self.assertIn("written", inspect.getsource(DT.cmd_doctor))


if __name__ == "__main__":
    unittest.main()
