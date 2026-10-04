"""Parity tests for the hybrid engine against the original dev-team engine: the finish gate,
doctor's opencode default, overlap-only dirty-root, the shipped parallel default, and a marker
test that the ported symbols exist."""
import argparse
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import devteam  # noqa: E402

ENGINE = SCRIPTS / "devteam.py"
STATE = ".claude/hybrid-team"
MODELS_ENV = {"HYBRID_OPENCODE_STD": "zai-coding-plan/glm-5.3#high",
              "HYBRID_OPENCODE_LITE": "zai-coding-plan/glm-5.3-flash#low"}


def git(args, cwd):
    r = subprocess.run(["git"] + list(args), cwd=str(cwd), text=True, capture_output=True, check=True)
    return r.stdout.strip()


def make_repo(tmp):
    repo = Path(os.path.realpath(str(tmp))) / "repo"
    repo.mkdir()
    git(["init", "-q", "-b", "main"], repo)
    git(["config", "user.email", "t@example.invalid"], repo)
    git(["config", "user.name", "t"], repo)
    git(["config", "commit.gpgsign", "false"], repo)
    (repo / "README.md").write_text("demo\n")
    git(["add", "README.md"], repo)
    git(["commit", "-qm", "init"], repo)
    return repo


class FinishGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), XDG_DATA_HOME=str(self.tmp / "xdg"),
                        HYBRID_TEAM_OC_BIN=str(self.tmp / "no-such-opencode"),
                        HYBRID_TEAM_ROUTING=str(self.tmp / "routing.json"),
                        PYTHONDONTWRITEBYTECODE="1", **MODELS_ENV)
        self.env.pop("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", None)
        self.env.pop("HYBRID_OPENCODE_MAX_PARALLEL", None)

    def engine(self, repo, *args):
        return subprocess.run([sys.executable, str(ENGINE)] + list(args), cwd=str(repo), env=self.env,
                              text=True, capture_output=True, timeout=120)

    def finishable_repo(self, **state_over):
        """A repo whose single slice G1 is merged, reviewed and checkpointed (gate fully green);
        `state_over` then overwrites top-level state keys to break one condition at a time."""
        repo = make_repo(self.tmp)
        plan = {"request": "finish gate fixtures", "profile": "balanced",
                "commands": {"test": "none", "test_file": "none"},
                "slices": [{"id": "G1", "title": "g1", "goal": "g1", "kind": "code", "size": "small",
                            "deps": [], "files": ["src/g1.py", "tests/test_g1.py"], "risk": "low",
                            "criteria": ["works"]}]}
        plan_path = self.tmp / "plan.json"
        plan_path.write_text(json.dumps(plan))
        r = self.engine(repo, "init", str(plan_path), "--route", "claude")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        head = git(["rev-parse", "HEAD"], repo)
        sp = repo / STATE / "state.json"
        st = json.loads(sp.read_text())
        st["slices"]["G1"].update({"status": "done", "merged_sha": head})
        st.update({"merges": ["G1"], "reviewed_upto": 1, "merges_since_checkpoint": 0,
                   "checkpoint_pending": False,
                   "checkpoints": [{"t": 1, "sha": head, "result": "pass", "note": ""}]})
        st.update(state_over)
        sp.write_text(json.dumps(st))
        return repo

    def assert_blocked(self, repo, needle):
        r = self.engine(repo, "finish")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("finish gate", r.stderr)
        self.assertIn(needle, r.stderr)

    def test_clean_run_finishes(self):
        repo = self.finishable_repo()
        r = self.engine(repo, "finish")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FINISHED", r.stdout)

    def test_run_with_no_merges_needs_no_checkpoint(self):
        repo = self.finishable_repo(merges=[], reviewed_upto=0, checkpoints=[])
        r = self.engine(repo, "finish")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_failed_last_checkpoint_blocks(self):
        repo = self.finishable_repo(checkpoints=[{"t": 1, "sha": "a" * 40, "result": "fail", "note": ""}])
        self.assert_blocked(repo, "the last checkpoint result is fail, not pass")

    def test_missing_checkpoint_blocks(self):
        repo = self.finishable_repo(checkpoints=[])
        self.assert_blocked(repo, "no checkpoint has been recorded")

    def test_pending_checkpoint_blocks(self):
        repo = self.finishable_repo(checkpoint_pending={"n": 2, "sha": "b" * 40, "wt": "x",
                                                        "merges_at": 1, "t": 1})
        self.assert_blocked(repo, "a checkpoint is still pending")

    def test_merge_after_last_checkpoint_blocks(self):
        repo = self.finishable_repo(merges_since_checkpoint=2)
        self.assert_blocked(repo, "2 merge(s) landed after the last checkpoint snapshot")

    def test_changes_required_verification_blocks(self):
        repo = self.finishable_repo(verification_verdict="CHANGES_REQUIRED")
        self.assert_blocked(repo, "the verification verdict is CHANGES_REQUIRED")

    def test_force_finishes_and_names_every_bypassed_condition(self):
        repo = self.finishable_repo(checkpoints=[], verification_verdict="CHANGES_REQUIRED")
        r = self.engine(repo, "finish", "--force")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FINISH GATE BYPASSED", r.stdout)
        self.assertIn("no checkpoint has been recorded", r.stdout)
        self.assertIn("the verification verdict is CHANGES_REQUIRED", r.stdout)


class DoctorOpencodeDefaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.root = make_repo(self.tmp)
        env = dict(MODELS_ENV, HOME=str(self.tmp), XDG_DATA_HOME=str(self.tmp / "xdg"))
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("HYBRID_TEAM_ROUTING", None)

    def run_doctor(self, preset, **extra):
        routing = self.tmp / "routing.json"
        routing.write_text(json.dumps({"preset": preset}))
        args = argparse.Namespace(root=str(self.root), ping=False, routing=str(routing), fix=False, **extra)
        with mock.patch.object(devteam, "doctor_opencode") as spawned:
            devteam.cmd_doctor(args)
        return spawned

    def test_claude_preset_never_spawns_opencode_checks(self):
        self.assertFalse(self.run_doctor("claude").called)

    def test_hybrid_preset_runs_opencode_checks(self):
        self.assertTrue(self.run_doctor("hybrid").called)

    def test_explicit_oc_false_wins_over_a_hybrid_preset(self):
        self.assertFalse(self.run_doctor("hybrid", oc=False).called)


class IntegrateDirtyRootTests(unittest.TestCase):
    def test_do_integrate_has_no_blanket_dirty_tree_refusal(self):
        self.assertNotIn("uncommitted tracked changes", inspect.getsource(devteam.do_integrate))

    def test_merge_slice_refuses_only_on_overlap_with_the_slice(self):
        src = inspect.getsource(devteam.merge_slice)
        self.assertIn('"dirty-root"', src)
        self.assertIn("set(touched)", src)


class ShippedDefaultsTests(unittest.TestCase):
    def test_default_oc_max_parallel_matches_the_shipped_routing_default(self):
        shipped = json.loads((SCRIPTS.parent / "routing.default.json").read_text())
        for name, tier in shipped["tiers"].items():
            self.assertEqual(devteam.DEFAULT_OC_MAX_PARALLEL, tier["max_parallel"], name)


class ParityMarkerTests(unittest.TestCase):
    """Fails when a symbol the original engine has is missing from the hybrid fork."""

    def test_ported_symbols_exist(self):
        for name in ("finish_gate_problems", "salvage_worktree", "validate_slice_types", "next_fix_id",
                     "dirty_excluding", "plan_fp", "doctor_wants_oc"):
            self.assertTrue(callable(getattr(devteam, name, None)), name)


if __name__ == "__main__":
    unittest.main()
