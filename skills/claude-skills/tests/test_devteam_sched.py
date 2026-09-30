"""Black-box + direct-import tests for K02: devteam.py scheduling correctness.

Covers: init/start --force wiping stale reviews/logs/research (and each new brief/checkpoint
deleting its own stale target first), start succeeding after doctor --fix rewrites a tracked
agent file, research slices holding no footprint, red-done marking its footprint busy, the
stall/UNRESOLVED hint, finish counting never-reviewed merges, review-shard reservations only
for non-APPROVED shards, and hooks_resolve() probing dev-team-* folders too.

Fixtures are real git repos built under the SYSTEM temp dir (never inside this repo or a
worktree) via tempfile.mkdtemp() + os.path.realpath(). The engine is exercised as a subprocess
for anything involving git/worktree state; pure scheduling functions (ready_slices,
reserved_slots, print_ready, hooks_resolve) are exercised via direct import since they need no
git state at all.
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEVTEAM_PATH = str(Path(__file__).resolve().parents[1] / "dev-team-v3.2" / "scripts" / "devteam.py")

spec = importlib.util.spec_from_file_location("devteam_under_test_k02", DEVTEAM_PATH)
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)


def run_dt(args, cwd, env=None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run([sys.executable, DEVTEAM_PATH] + args, cwd=str(cwd),
                           capture_output=True, text=True, env=full_env, timeout=60)


def new_repo():
    """A fresh, disposable git repo under the system temp dir (realpath'd)."""
    d = Path(os.path.realpath(tempfile.mkdtemp()))
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=d, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=d, check=True)
    return d


def commit_all(d, msg):
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=d, check=True)


PLAN_TMPL = """# plan
```json
%s
```
"""


def slice_record(sid, files, status="pending", deps=None, risk="low", size="small"):
    """A minimal in-memory slice record shaped like init() would build, for direct-import
    tests of the pure scheduling functions (no repo/state.json needed)."""
    return {"id": sid, "title": sid, "goal": "", "kind": "code", "size": size, "verify": "",
            "model": "", "deps": list(deps or []), "files": list(files), "risk": risk,
            "criteria": ["works"], "edge_cases": [], "context": [], "isolation": None,
            "status": status, "mode": None, "attempt": 0, "base_sha": None, "red_sha": None,
            "worktree": None, "branch": None, "merged_sha": None, "history": []}


class EngineFixture(unittest.TestCase):
    """Shared helpers for full-engine (subprocess) tests."""

    def make_repo_with_plan(self, slices, profile="balanced", extra_files=None):
        repo = new_repo()
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "src" / ".keep").write_text("")
        (repo / "tests" / ".keep").write_text("")
        for rel, content in (extra_files or {}).items():
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        commit_all(repo, "init")
        plan = {
            "request": "K02 sched fixtures", "profile": profile,
            "commands": {"test": "none", "test_file": "none"},
            "slices": slices,
        }
        planp = repo / "plan.md"
        planp.write_text(PLAN_TMPL % json.dumps(plan))
        r = run_dt(["init", "plan.md"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return repo

    def add_worktree_and_claim(self, repo, sid, wt_name):
        r = run_dt(["dispatch", sid], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        subprocess.run(["git", "worktree", "add", "-q", f".claude/worktrees/{wt_name}",
                         "-b", f"worktree-{wt_name}", "HEAD"], cwd=repo, check=True)
        wt = repo / ".claude" / "worktrees" / wt_name
        r = run_dt(["claim", sid], wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return wt, r.stdout

    def merge_one_slice(self, repo, sid="S1"):
        """RED -> GREEN -> integrate a trivial slice, leaving it `done` and merged, but never
        sent through review-batch."""
        wt, _ = self.add_worktree_and_claim(repo, sid, f"w-{sid}")
        (wt / "tests" / f"{sid}.test.js").write_text('test("x", () => { assert.equal(1, 1); });\n')
        r = run_dt(["commit-red", sid], wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        (wt / "src" / f"{sid}.js").write_text("module.exports = 1;\n")
        subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
        r = run_dt(["commit-green", sid], wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run_dt(["integrate", sid], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class TestForceWipesStaleArtifacts(EngineFixture):
    """Criterion: init --force / start --force leave no stale reviews/, logs/ or research/ files."""

    def test_force_wipes_stale_reviews_logs_research_dirs(self):
        repo = self.make_repo_with_plan(
            [{"id": "S1", "title": "s1", "files": ["src/S1.js", "tests/S1.test.js"],
              "risk": "low", "criteria": ["works"]}])
        sd = repo / ".claude" / "dev-team"
        (sd / "reviews").mkdir(exist_ok=True)
        (sd / "reviews" / "r1.report.md").write_text("## Verdict: APPROVED\nstale\n")
        (sd / "logs").mkdir(exist_ok=True)
        (sd / "logs" / "checkpoint-1.log").write_text("stale output\nEXIT=0\n")
        (sd / "research").mkdir(exist_ok=True)
        (sd / "research" / "OLD.md").write_text("## Findings\nstale\n")
        r = run_dt(["init", "plan.md", "--force"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((sd / "reviews" / "r1.report.md").exists(),
                          "init --force must wipe stale reviews/ files")
        self.assertFalse((sd / "logs" / "checkpoint-1.log").exists(),
                          "init --force must wipe stale logs/ files")
        self.assertFalse((sd / "research" / "OLD.md").exists(),
                          "init --force must wipe stale research/ files")


class TestStaleTargetDeletedBeforeNewWrite(EngineFixture):
    """Criterion: a new brief or checkpoint deletes its own target report/log first."""

    def test_stale_checkpoint_log_deleted_before_new_checkpoint_starts(self):
        repo = self.make_repo_with_plan(
            [{"id": "S1", "title": "s1", "files": ["src/S1.js", "tests/S1.test.js"],
              "risk": "low", "criteria": ["works"]}])
        sd = repo / ".claude" / "dev-team"
        (sd / "logs").mkdir(exist_ok=True)
        stale_log = sd / "logs" / "checkpoint-1.log"
        stale_log.write_text("leftover from a previous run\nEXIT=0\n")
        r = run_dt(["checkpoint"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(stale_log.exists(),
                          "a stale checkpoint-1.log must never be left for the next `next` to "
                          "misread as a PASS before the real run has written anything")

    def test_stale_review_report_deleted_before_new_brief(self):
        repo = self.make_repo_with_plan(
            [{"id": "S1", "title": "s1", "files": ["src/S1.js", "tests/S1.test.js"],
              "risk": "low", "criteria": ["works"]}])
        self.merge_one_slice(repo, "S1")
        sd = repo / ".claude" / "dev-team"
        (sd / "reviews").mkdir(exist_ok=True)
        stale = sd / "reviews" / "r1.report.md"
        stale.write_text("## Verdict: APPROVED\nstale leftover\n")
        r = run_dt(["review-batch", "--force"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(stale.exists(),
                          "the new review's target report must be deleted before its brief is "
                          "written, so a stale report is never harvested as this round's verdict")


class TestStartAfterDoctorFix(unittest.TestCase):
    """Criterion: start succeeds in a repo that tracks .claude/agents/*.md which doctor --fix
    rewrites (only the paths doctor wrote are excluded from init's dirty check)."""

    def _repo_with_tracked_agent(self):
        repo = new_repo()
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "src" / ".keep").write_text("")
        (repo / "tests" / ".keep").write_text("")
        agents_dir = repo / ".claude" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "programmer.md").write_text("stale shipped-agent content\n")
        commit_all(repo, "init")
        plan = {
            "request": "r", "profile": "balanced",
            "commands": {"test": "none", "test_file": "none"},
            "slices": [{"id": "S1", "title": "s1", "files": ["src/S1.js", "tests/S1.test.js"],
                        "risk": "low", "criteria": ["works"]}],
        }
        (repo / "plan.md").write_text(PLAN_TMPL % json.dumps(plan))
        return repo

    def test_start_succeeds_when_doctor_fix_rewrites_tracked_agent(self):
        repo = self._repo_with_tracked_agent()
        r = run_dt(["start", "plan.md"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("PROFILE", r.stdout, r.stdout + r.stderr)

    def test_start_still_fails_on_unrelated_dirty_tracked_file(self):
        # Only the paths doctor --fix wrote may be excluded: an unrelated tracked change must
        # still block `start`, so this is not a blanket "ignore all dirt" fix.
        repo = self._repo_with_tracked_agent()
        (repo / "src" / ".keep").write_text("unrelated dirty change\n")
        r = run_dt(["start", "plan.md"], repo)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("uncommitted", (r.stdout + r.stderr).lower())


class TestResearchFootprint(EngineFixture):
    """Criterion: research slices hold no footprint and accept files: []."""

    def test_validate_plan_accepts_research_slice_with_empty_files(self):
        plan = {"request": "r", "commands": {"test": "none"},
                "slices": [{"id": "R1", "title": "research", "kind": "research", "files": [],
                            "risk": "low", "criteria": ["answered"]}]}
        try:
            dt.validate_plan(plan)
        except dt.DevteamError as e:
            self.fail(f"a research slice with files: [] must be accepted; got: {e}")

    def test_research_slice_never_serializes_a_code_slice(self):
        # Edge case: a research slice (files: []) alongside a normal code slice — both must be
        # ready together, never treated as sharing a footprint.
        repo = self.make_repo_with_plan(
            [{"id": "R1", "title": "research", "kind": "research", "files": [],
              "risk": "low", "criteria": ["answered"]},
             {"id": "S1", "title": "s1", "files": ["src/S1.js", "tests/S1.test.js"],
              "risk": "low", "criteria": ["works"]}])
        r = run_dt(["ready"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        ready_line = next(ln for ln in r.stdout.splitlines() if ln.startswith("READY"))
        self.assertIn("R1", ready_line, r.stdout)
        self.assertIn("S1", ready_line, r.stdout)


class TestResearchHoldsNoFootprint(EngineFixture):
    """Criterion: a research slice may omit `files`, and never holds a code slice back."""

    RES = {"id": "R1", "title": "research", "kind": "research", "risk": "low",
           "criteria": ["answered"]}
    CODE = {"id": "S1", "title": "s1", "files": ["src/S1.js", "tests/S1.test.js"],
            "risk": "low", "criteria": ["works"]}

    def test_validate_plan_accepts_research_slice_without_files_key(self):
        plan = {"request": "r", "commands": {"test": "none"}, "slices": [dict(self.RES)]}
        try:
            dt.validate_plan(plan)
        except dt.DevteamError as e:
            self.fail(f"a research slice with no files key must be accepted; got: {e}")

    def test_init_accepts_research_slice_without_files_key(self):
        # make_repo_with_plan asserts `init` exits 0 (no KeyError)
        repo = self.make_repo_with_plan([dict(self.RES), dict(self.CODE)])
        st = json.loads((repo / ".claude" / "dev-team" / "state.json").read_text())
        self.assertEqual(st["slices"]["R1"]["files"], [])

    def test_no_share_a_path_warning_for_research_overlapping_code(self):
        res = dict(self.RES, files=["src/S1.js"])
        plan = {"request": "r", "commands": {"test": "none"},
                "slices": [res, dict(self.CODE)]}
        warns = dt.validate_plan(plan)
        self.assertFalse([w for w in warns if "share a path" in w], warns)

    def test_code_slices_still_warn_when_they_share_a_path(self):
        other = dict(self.CODE, id="S2", title="s2")
        plan = {"request": "r", "commands": {"test": "none"},
                "slices": [dict(self.CODE), other]}
        warns = dt.validate_plan(plan)
        self.assertTrue([w for w in warns if "share a path" in w], warns)

    def test_inflight_research_does_not_hold_back_code_slice(self):
        r = slice_record("R1", ["src/S1.js"], status="inflight")
        r["kind"] = "research"
        st = {"slices": {"R1": r, "S1": slice_record("S1", ["src/S1.js"])}}
        ready, _ = dt.ready_slices(st)
        self.assertIn("S1", ready)

    def test_pending_research_and_code_are_ready_together(self):
        r = slice_record("R1", ["src/S1.js"])
        r["kind"] = "research"
        st = {"slices": {"R1": r, "S1": slice_record("S1", ["src/S1.js"])}}
        ready, _ = dt.ready_slices(st)
        self.assertIn("R1", ready)
        self.assertIn("S1", ready)

    def test_code_slice_still_blocked_by_inflight_code_slice(self):
        st = {"slices": {"A": slice_record("A", ["src/x.js"], status="inflight"),
                         "B": slice_record("B", ["src/x.js"])}}
        ready, _ = dt.ready_slices(st)
        self.assertNotIn("B", ready)

    def test_dispatch_never_skips_code_slice_for_research_overlap(self):
        repo = self.make_repo_with_plan(
            [dict(self.RES, files=["src/S1.js"]), dict(self.CODE)])
        r = run_dt(["dispatch", "R1", "S1"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("=== DISPATCH R1", r.stdout)
        self.assertIn("=== DISPATCH S1", r.stdout)
        self.assertNotIn("SKIPPED", r.stdout)

    def test_dispatch_code_slice_while_research_inflight(self):
        repo = self.make_repo_with_plan(
            [dict(self.RES, files=["src/S1.js"]), dict(self.CODE)])
        r = run_dt(["dispatch", "R1"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run_dt(["dispatch", "S1"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("=== DISPATCH S1", r.stdout)
        self.assertNotIn("SKIPPED", r.stdout)


class TestRedDoneBusy(unittest.TestCase):
    """Criterion: a slice in red-done state marks its footprint busy."""

    def test_red_done_slice_marks_footprint_busy(self):
        st = {"slices": {
            "R1": slice_record("R1", ["src/shared.js"], status="red-done"),
            "S2": slice_record("S2", ["src/shared.js", "src/other.js"], status="pending"),
        }}
        ready, _inflight = dt.ready_slices(st)
        self.assertIn("R1", ready, "the red-done slice must still be schedulable for GREEN")
        self.assertNotIn("S2", ready,
                          "S2 overlaps a red-done slice's footprint and must stay blocked")

    def test_red_done_does_not_block_a_disjoint_slice(self):
        st = {"slices": {
            "R1": slice_record("R1", ["src/shared.js"], status="red-done"),
            "S3": slice_record("S3", ["src/unrelated.js"], status="pending"),
        }}
        ready, _inflight = dt.ready_slices(st)
        self.assertIn("S3", ready)


class TestStallHint(unittest.TestCase):
    """Criterion: when nothing is in flight, nothing is ready and slices still wait, `next`
    must print a stuck/UNRESOLVED line naming each blocked slice, its failed dependency and
    the recovery command. Edge case: a failed slice with two dependents."""

    def test_stall_prints_unresolved_for_each_dependent_of_a_failed_slice(self):
        st = {"slices": {
            "F1": slice_record("F1", ["src/f1.js"], status="failed"),
            "S2": slice_record("S2", ["src/s2.js"], status="pending", deps=["F1"]),
            "S3": slice_record("S3", ["src/s3.js"], status="pending", deps=["F1"]),
        }}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dt.print_ready(st)
        text = buf.getvalue()
        self.assertIn("UNRESOLVED", text, text)
        self.assertIn("S2", text, text)
        self.assertIn("S3", text, text)
        self.assertIn("F1", text, text)
        self.assertIn("retry F1", text, text)

    def test_no_stall_line_when_something_is_ready(self):
        st = {"slices": {
            "S1": slice_record("S1", ["src/s1.js"], status="pending"),
        }}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dt.print_ready(st)
        self.assertNotIn("UNRESOLVED", buf.getvalue())


class TestFinishCountsUnreviewedMerges(EngineFixture):
    """Criterion: finish counts merges[reviewed_upto:] as unreviewed in its warning."""

    def test_finish_warns_on_merges_never_sent_to_review(self):
        repo = self.make_repo_with_plan(
            [{"id": "S1", "title": "s1", "files": ["src/S1.js", "tests/S1.test.js"],
              "risk": "low", "criteria": ["works"]}])
        self.merge_one_slice(repo, "S1")
        r = run_dt(["finish"], repo)
        self.assertNotEqual(r.returncode, 0,
                             "finish must refuse when a merged slice was never sent to review")
        out = r.stdout + r.stderr
        self.assertIn("never sent to review", out, out)
        self.assertIn("S1", out, out)


class TestReviewShardReservations(unittest.TestCase):
    """Criterion: print_ready's advertised free slots subtract review-shard reservations; a
    CHANGES_REQUIRED review reserves slots only for its non-APPROVED shards."""

    def test_reserved_slots_counts_only_non_approved_shards(self):
        st = {"reviews": {"r1": {"status": "done", "verdict": "CHANGES_REQUIRED", "shards": 3,
                                  "shard_verdicts": ["APPROVED", "CHANGES_REQUIRED", "APPROVED"]}}}
        self.assertEqual(dt.reserved_slots(st), dt.RESERVED_MIN + 1)

    def test_reserved_slots_all_shards_approved_reserves_nothing_extra(self):
        # Edge case: a review with all shards APPROVED.
        st = {"reviews": {"r1": {"status": "done", "verdict": "APPROVED", "shards": 3,
                                  "shard_verdicts": ["APPROVED", "APPROVED", "APPROVED"]}}}
        self.assertEqual(dt.reserved_slots(st), dt.RESERVED_MIN)

    def test_print_ready_frees_slot_when_fewer_shards_need_a_re_review(self):
        more_reserved = {"slices": {}, "reviews": {
            "r1": {"status": "done", "verdict": "CHANGES_REQUIRED", "shards": 3,
                   "shard_verdicts": ["APPROVED", "CHANGES_REQUIRED", "APPROVED"]}}}
        less_reserved = {"slices": {}, "reviews": {}}
        buf1, buf2 = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf1):
            dt.print_ready(more_reserved)
        with contextlib.redirect_stdout(buf2):
            dt.print_ready(less_reserved)
        free1 = int(re.search(r"(\d+) free of", buf1.getvalue()).group(1))
        free2 = int(re.search(r"(\d+) free of", buf2.getvalue()).group(1))
        self.assertEqual(free2, free1 + 1,
                          "only the one non-APPROVED shard should be reserved, freeing the rest")


class TestHooksResolveCandidates(unittest.TestCase):
    """Criterion: hooks_resolve() probes the C3 candidate list including dev-team-* folders."""

    def test_candidates_include_project_root_glob_folder(self):
        root = Path(os.path.realpath(tempfile.mkdtemp()))
        d = root / ".claude" / "skills" / "dev-team-v9.9" / "scripts"
        d.mkdir(parents=True)
        guard = d / "guard.py"
        guard.write_text("# fake guard\n")
        cands = dt.hooks_resolve_candidates(root)
        self.assertIn(guard, cands,
                      "the probe list must include a dev-team-* glob match under the project root")
        self.assertEqual(cands[0], root / ".claude" / "skills" / "dev-team" / "scripts" / "guard.py",
                          "the exact 'dev-team' name must be probed before the glob, per C3")

    def test_hooks_resolve_true_via_dev_team_glob_candidate(self):
        root = Path(os.path.realpath(tempfile.mkdtemp()))
        d = root / ".claude" / "skills" / "dev-team-v9.9" / "scripts"
        d.mkdir(parents=True)
        (d / "guard.py").write_text("# fake guard\n")
        agent_text = (
            "hooks:\n"
            "  Stop:\n"
            "    - hooks:\n"
            "        - type: command\n"
            "          timeout: 30\n"
            "          command: >-\n"
            "            sh -c 'for d in \"$CLAUDE_PROJECT_DIR/.claude/skills/dev-team\" "
            "\"$CLAUDE_PROJECT_DIR\"/.claude/skills/dev-team-* \"$HOME/.claude/skills/dev-team\" "
            "\"$HOME\"/.claude/skills/dev-team-*;\n"
            "            do [ -f \"$d/scripts/guard.py\" ] && exec python3 \"$d/scripts/guard.py\" stop; done; exit 0'\n"
        )
        agent_file = root / "agent.md"
        agent_file.write_text(agent_text)
        self.assertTrue(dt.hooks_resolve(agent_file, root),
                         "hooks_resolve must find guard.py under a dev-team-* folder too, "
                         "not only the exact 'dev-team' name")


class TestIntegrateFewerGitCalls(EngineFixture):
    """Criteria: one SLICE integrate spawns >=3 fewer git subprocesses than at 9f4c980 (which
    measured BASELINE_GIT_CALLS), no `worktree unlock`, at most one `worktree prune`; a locked
    worktree is still removed."""

    BASELINE_GIT_CALLS = 17  # counted at 9f4c980 on this fixture

    def _integrate_counting(self, lock):
        repo = self.make_repo_with_plan([{
            "id": "S1", "title": "one", "goal": "g", "kind": "code", "size": "small", "risk": "low",
            "files": ["src/S1.js", "tests/S1.test.js"], "criteria": ["works"], "deps": []}])
        wt, _ = self.add_worktree_and_claim(repo, "S1", "w-S1")
        (wt / "tests" / "S1.test.js").write_text('test("x", () => { assert.equal(1, 1); });\n')
        self.assertEqual(run_dt(["commit-red", "S1"], wt).returncode, 0)
        (wt / "src" / "S1.js").write_text("module.exports = 1;\n")
        subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
        self.assertEqual(run_dt(["commit-green", "S1"], wt).returncode, 0)
        if lock:
            subprocess.run(["git", "worktree", "lock", str(wt)], cwd=repo, check=True)
        calls = []
        real_run = subprocess.run

        def counting_run(args, *a, **kw):
            calls.append(list(args) if isinstance(args, (list, tuple)) else [args])
            return real_run(args, *a, **kw)

        old_cwd = os.getcwd()
        os.chdir(str(repo))
        subprocess.run = counting_run
        try:
            st = dt.load_state(repo)
            res = dt.do_integrate(repo, st, ["S1"])
        finally:
            subprocess.run = real_run
            os.chdir(old_cwd)
        self.assertIn("MERGED", res[0])
        return repo, wt, calls

    def test_fewer_git_calls_no_unlock_single_prune(self):
        _, wt, calls = self._integrate_counting(lock=False)
        git_calls = [c for c in calls if c and c[0] == "git"]
        self.assertLessEqual(len(git_calls), self.BASELINE_GIT_CALLS - 3)
        self.assertFalse([c for c in git_calls if c[1:3] == ["worktree", "unlock"]],
                         "no separate `git worktree unlock`")
        self.assertLessEqual(len([c for c in git_calls if c[1:3] == ["worktree", "prune"]]), 1)
        self.assertFalse(wt.exists())

    def test_locked_worktree_still_removed_after_merge(self):
        repo, wt, calls = self._integrate_counting(lock=True)
        self.assertFalse(wt.exists(), "a locked worktree must still be removed after merge")
        listing = subprocess.run(["git", "worktree", "list"], cwd=repo, capture_output=True,
                                 text=True).stdout
        self.assertNotIn("w-S1", listing)
        self.assertFalse([c for c in calls if c[:3] == ["git", "worktree", "unlock"]])


if __name__ == "__main__":
    unittest.main()
