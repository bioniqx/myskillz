import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import devteam  # noqa: E402


def init_repo(root):
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(root), check=True)
    (root / "README.md").write_text("hybrid-team test repo\n")
    subprocess.run(["git", "add", "README.md"], cwd=str(root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(root), check=True)


ROUTING = {
    "preset": "hybrid",
    "tiers": {
        "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "max_parallel": 6,
                 "stall_s": 180, "timeout_s": {"trivial": 600, "small": 1200, "large": 2400}},
        "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low", "max_parallel": 6,
                  "stall_s": 120, "timeout_s": {"trivial": 300, "small": 600, "large": 1200}},
    },
    "escalate_to": "claude",
    "max_escalations": 1,
}

MODELS_ENV = {"HYBRID_OPENCODE_STD": "zai-coding-plan/glm-5.3#high",
              "HYBRID_OPENCODE_LITE": "zai-coding-plan/glm-5.3-flash#low"}


def use_shared_env(case):
    """Set the shared model env vars (whatever the caller's real environment holds). Call it FIRST in
    setUp: the patch restores os.environ to the snapshot it takes here."""
    patcher = mock.patch.dict(os.environ, MODELS_ENV)
    patcher.start()
    case.addCleanup(patcher.stop)


class TestOcAvailable(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        init_repo(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_available_true_when_no_issues(self):
        checks = [{"name": "opencode_binary", "ok": True, "detail": "/usr/bin/opencode"},
                  {"name": "tiers", "ok": True, "detail": "tiers: lite, std"}]
        with mock.patch.object(devteam, "check_opencode", return_value=checks) as mocked:
            result = devteam.oc_available(self.root, ROUTING)
        mocked.assert_called_once_with("opencode", ROUTING)
        self.assertTrue(result)
        status_path = self.root / ".claude" / "hybrid-team" / "oc_status.json"
        self.assertTrue(status_path.exists())
        data = json.loads(status_path.read_text())
        self.assertTrue(data["available"])
        self.assertEqual(data["issues"], [])

    def test_available_false_when_issues_present(self):
        checks = [{"name": "opencode_binary", "ok": False, "detail": "not found: opencode"},
                  {"name": "tiers", "ok": True, "detail": "tiers: lite, std"}]
        with mock.patch.object(devteam, "check_opencode", return_value=checks):
            result = devteam.oc_available(self.root, ROUTING)
        self.assertFalse(result)
        status_path = self.root / ".claude" / "hybrid-team" / "oc_status.json"
        data = json.loads(status_path.read_text())
        self.assertFalse(data["available"])
        self.assertEqual(data["issues"], [{"name": "opencode_binary", "ok": False, "detail": "not found: opencode"}])

    def test_tier_scoped_failure_fails_only_that_tier(self):
        checks = [{"name": "opencode_binary", "ok": True, "detail": "/usr/bin/opencode"},
                  {"name": "model:std", "ok": False, "kind": "model",
                   "detail": "zai-coding-plan/glm-5.3 not listed"}]
        with mock.patch.object(devteam, "check_opencode", return_value=checks):
            result = devteam.oc_available(self.root, ROUTING)
        self.assertTrue(result)
        sd = self.root / ".claude" / "hybrid-team"
        tiers = json.loads((sd / "oc_status.json").read_text())["tiers"]
        self.assertEqual((tiers["std"]["ok"], tiers["std"]["kind"]), (False, "model"))
        self.assertIn("not listed", tiers["std"]["detail"])
        self.assertTrue(tiers["lite"]["ok"])
        self.assertEqual(tiers["lite"]["key"], devteam.hybrid_shared.cache_key(ROUTING["tiers"]["lite"]))
        self.assertIsInstance(tiers["lite"]["checked_at"], float)
        self.assertEqual(devteam.usable_tiers(sd, ROUTING), {"std": False, "lite": True})


class TestCmdDoctorOc(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        use_shared_env(self)
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        init_repo(self.root)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self._old_home = os.environ.get("HOME")
        self._old_ht_routing = os.environ.get("HT_ROUTING")
        os.environ["HOME"] = str(self.home)
        os.environ["HT_ROUTING"] = str(self.home / "routing.json")

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        if self._old_ht_routing is None:
            os.environ.pop("HT_ROUTING", None)
        else:
            os.environ["HT_ROUTING"] = self._old_ht_routing
        self.tmp.cleanup()

    def test_doctor_reports_opencode_ok(self):
        args = argparse.Namespace(root=str(self.root), ping=False, routing=None, fix=False)
        with mock.patch.object(devteam, "check_opencode", return_value=[]):
            devteam.cmd_doctor(args)
        status_path = self.root / ".claude" / "hybrid-team" / "oc_status.json"
        data = json.loads(status_path.read_text())
        self.assertTrue(data["available"])

    def test_doctor_pings_each_tier(self):
        args = argparse.Namespace(root=str(self.root), ping=True, routing=None, fix=False)
        calls = []

        def fake_ping(binary, tier, prompt_text, engine, workdir):
            calls.append((binary, tier, prompt_text, engine, workdir))
            return (True, "ok")

        with mock.patch.object(devteam, "check_opencode", return_value=[]), \
                mock.patch.object(devteam, "ping_tier", side_effect=fake_ping) as mocked:
            devteam.cmd_doctor(args)
        self.assertEqual(mocked.call_count, len(ROUTING["tiers"]))
        self.assertTrue(calls)
        prompt_path = Path(devteam.__file__).resolve().parents[1] / "agents" / "opencode" / "ht-programmer.prompt.md"
        expected_prompt = prompt_path.read_text() if prompt_path.exists() else ""
        expected_workdir = self.root / ".claude" / "hybrid-team"
        for binary, tier, prompt_text, engine, workdir in calls:
            self.assertEqual(prompt_text, expected_prompt)
            self.assertEqual(workdir, expected_workdir)

    def test_doctor_reports_each_failed_check_as_oc_error(self):
        args = argparse.Namespace(root=str(self.root), ping=False, routing=None, fix=False)
        checks = [{"name": "opencode_binary", "ok": False, "kind": "spawn", "detail": "not found: opencode"}]
        with mock.patch.object(devteam, "check_opencode", return_value=checks), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as buf:
            devteam.cmd_doctor(args)
        text = buf.getvalue()
        self.assertIn("OC-ERROR hybrid-team doctor tier=- model=- kind=spawn", text)
        self.assertIn("not found: opencode", text)

    def test_failed_ping_marks_only_that_tier(self):
        args = argparse.Namespace(root=str(self.root), ping=True, routing=None, fix=False)

        def fake_ping(binary, tier, prompt_text, engine, workdir):
            if tier.get("variant") == "high":
                return (False, {"kind": "auth", "message": "401 unauthorized"})
            return (True, {"kind": "", "message": ""})

        with mock.patch.object(devteam, "check_opencode", return_value=[]), \
                mock.patch.object(devteam, "ping_tier", side_effect=fake_ping), \
                mock.patch("sys.stdout", new_callable=io.StringIO) as buf:
            devteam.cmd_doctor(args)
        data = json.loads((self.root / ".claude" / "hybrid-team" / "oc_status.json").read_text())
        self.assertEqual((data["tiers"]["std"]["ok"], data["tiers"]["std"]["kind"]), (False, "auth"))
        self.assertTrue(data["tiers"]["lite"]["ok"])
        self.assertTrue(data["available"])
        self.assertIn("OC-ERROR hybrid-team doctor tier=std", buf.getvalue())
        self.assertIn("kind=auth", buf.getvalue())

    def test_stale_ping_pings_only_tiers_without_a_fresh_ok_entry(self):
        calls = []

        def fake_ping(binary, tier, prompt_text, engine, workdir):
            calls.append(tier.get("variant"))
            return (True, {"kind": "", "message": ""})

        status_path = self.root / ".claude" / "hybrid-team" / "oc_status.json"

        def doctor():
            devteam.cmd_doctor(argparse.Namespace(root=str(self.root), ping="stale", routing=None, fix=False))

        with mock.patch.object(devteam, "check_opencode", return_value=[]), \
                mock.patch.object(devteam, "ping_tier", side_effect=fake_ping), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            doctor()
            self.assertEqual(sorted(calls), ["high", "low"])
            doctor()
            self.assertEqual(len(calls), 2)
            data = json.loads(status_path.read_text())
            data["tiers"]["std"]["checked_at"] = 0.0
            status_path.write_text(json.dumps(data))
            doctor()
        self.assertEqual(calls[2:], ["high"])


class TestDoctorRoutingFile(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        use_shared_env(self)
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        init_repo(self.root)
        self.home = Path(self.tmp.name) / "home"
        self.home.mkdir()
        self._old_home = os.environ.get("HOME")
        self._old_ht_routing = os.environ.get("HT_ROUTING")
        os.environ["HOME"] = str(self.home)
        self.routing_path = self.home / "routing.json"
        os.environ["HT_ROUTING"] = str(self.routing_path)

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        if self._old_ht_routing is None:
            os.environ.pop("HT_ROUTING", None)
        else:
            os.environ["HT_ROUTING"] = self._old_ht_routing
        self.tmp.cleanup()

    def test_fix_never_writes_the_user_routing_file(self):
        self.assertFalse(self.routing_path.exists())
        args = argparse.Namespace(root=str(self.root), ping=False, routing=None, fix=True)
        with mock.patch.object(devteam, "check_opencode", return_value=[]):
            devteam.cmd_doctor(args)
        self.assertFalse(self.routing_path.exists())

    def test_fix_never_overwrites_existing_routing_file(self):
        self.routing_path.parent.mkdir(parents=True, exist_ok=True)
        self.routing_path.write_text(json.dumps({"preset": "custom-untouched"}))
        args = argparse.Namespace(root=str(self.root), ping=False, routing=None, fix=True)
        with mock.patch.object(devteam, "check_opencode", return_value=[]):
            devteam.cmd_doctor(args)
        self.assertEqual(json.loads(self.routing_path.read_text()), {"preset": "custom-untouched"})

    def test_without_fix_creates_nothing(self):
        args = argparse.Namespace(root=str(self.root), ping=False, routing=None, fix=False)
        with mock.patch.object(devteam, "check_opencode", return_value=[]):
            devteam.cmd_doctor(args)
        self.assertFalse(self.routing_path.exists())


class TestCmdFinishSafety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        init_repo(self.root)
        self.worktrees_dir = self.root / ".claude" / "worktrees"
        self.worktrees_dir.mkdir(parents=True)
        subprocess.run(
            ["git", "worktree", "add", "-b", "oc-slice1", str(self.worktrees_dir / "oc-slice1")],
            cwd=str(self.root), check=True,
        )
        self.state_dir = self.root / ".claude" / "hybrid-team"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(self.root), check=True,
            capture_output=True, text=True,
        ).stdout.strip()

    def tearDown(self):
        self.tmp.cleanup()

    def branch_exists(self):
        out = subprocess.run(["git", "branch", "--list", "oc-slice1"], cwd=str(self.root),
                             check=True, capture_output=True, text=True).stdout
        return "oc-slice1" in out

    def write_state(self, status):
        state = {"slices": {"slice1": {"status": status}}, "merges": [], "reviews": {}, "checkpoints": [],
                 "start_sha": self.head_sha, "integration_branch": "main", "request": "test"}
        (self.state_dir / "state.json").write_text(json.dumps(state))

    def test_finish_without_force_leaves_unfinished_oc_worktree_and_branch(self):
        self.write_state("inflight")
        args = argparse.Namespace(root=str(self.root), force=False)
        with self.assertRaises(devteam.DevteamError):
            devteam.cmd_finish(args)
        self.assertTrue((self.worktrees_dir / "oc-slice1").exists())
        self.assertTrue(self.branch_exists())

    def test_finish_success_removes_oc_worktree_and_branch(self):
        self.write_state("done")
        args = argparse.Namespace(root=str(self.root), force=False)
        devteam.cmd_finish(args)
        self.assertFalse((self.worktrees_dir / "oc-slice1").exists())
        self.assertFalse(self.branch_exists())


class TestCmdFinishOc(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        init_repo(self.root)
        self.worktrees_dir = self.root / ".claude" / "worktrees"
        self.worktrees_dir.mkdir(parents=True)
        subprocess.run(
            ["git", "worktree", "add", "-b", "oc-slice1", str(self.worktrees_dir / "oc-slice1")],
            cwd=str(self.root), check=True,
        )
        subprocess.run(
            ["git", "worktree", "add", "-b", "native-slice2", str(self.worktrees_dir / "native-slice2")],
            cwd=str(self.root), check=True,
        )
        state_dir = self.root / ".claude" / "hybrid-team"
        state_dir.mkdir(parents=True, exist_ok=True)
        head_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(self.root), check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        state = {"slices": {}, "merges": [], "reviews": {}, "checkpoints": [],
                 "start_sha": head_sha, "integration_branch": "main", "request": "test"}
        (state_dir / "state.json").write_text(json.dumps(state))

    def tearDown(self):
        self.tmp.cleanup()

    def test_finish_removes_only_oc_worktrees(self):
        args = argparse.Namespace(root=str(self.root))
        devteam.cmd_finish(args)
        self.assertFalse((self.worktrees_dir / "oc-slice1").exists())
        self.assertTrue((self.worktrees_dir / "native-slice2").exists())


class TestCmdStats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        init_repo(self.root)
        self.state_dir = self.root / ".claude" / "hybrid-team"
        self.state_dir.mkdir(parents=True)
        self.lanes_path = self.state_dir / "lanes.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def test_stats_prints_per_tier_summary(self):
        raw_records = [
            {"id": "slice1", "backend": "oc:std", "tier": "std", "model": "zai-coding-plan/glm-5.3",
             "variant": "high", "mode": "code", "outcome": "done", "reason": "", "escalated": False,
             "duration_s": 100.0, "tokens": {"input": 10, "output": 20, "reasoning": 0,
             "cache_read": 0, "cache_write": 0}, "cost": 0.0, "runs": 1},
            {"id": "slice2", "backend": "oc:std", "tier": "std", "model": "zai-coding-plan/glm-5.3",
             "variant": "high", "mode": "code", "outcome": "blocked", "reason": "stall", "escalated": True,
             "duration_s": 300.0, "tokens": {"input": 30, "output": 40, "reasoning": 0,
             "cache_read": 0, "cache_write": 0}, "cost": 0.0, "runs": 1},
        ]
        with self.lanes_path.open("w") as fh:
            for rec in raw_records:
                fh.write(json.dumps(rec) + "\n")

        # `lane_stats` (consumed from T06) already groups raw lanes.jsonl records by
        # (backend, tier): this is the shape it returns for the two raw_records above.
        groups = [{"backend": "oc:std", "tier": "std", "count": 2, "escalated": 1,
                   "escalation_rate": 0.5, "median_time_s": 200.0,
                   "tokens": {"input": 40, "output": 60, "reasoning": 0,
                              "cache_read": 0, "cache_write": 0}, "cost": 0.0}]

        args = argparse.Namespace(root=str(self.root))
        with mock.patch.object(devteam, "lane_stats", return_value=groups) as mocked, \
                mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            rc = devteam.cmd_stats(args)
        mocked.assert_called_once_with(self.lanes_path)
        self.assertEqual(rc, 0)
        output = out.getvalue()
        self.assertIn("tier=std", output)
        self.assertIn("slices=2", output)
        self.assertIn("escalation_rate=0.50", output)
        self.assertIn("median_s=200.0", output)
        self.assertIn("tokens=100", output)


if __name__ == "__main__":
    unittest.main()
