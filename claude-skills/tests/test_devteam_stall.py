"""Black-box + direct-import tests for T03: stall detection for in-flight lanes that never wrote a
done or blocked marker (decision D2). `next` and `status` print `STALLED?` plus the exact retry
command, and never act on it.

Fixtures are real git repos under the SYSTEM temp dir, never inside this repo.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

DEVTEAM_PATH = str(Path(__file__).resolve().parents[1] / "claude-dev-team-v3.2" / "scripts" / "devteam.py")

spec = importlib.util.spec_from_file_location("devteam_under_test_stall", DEVTEAM_PATH)
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)

FENCE = "`" * 3
NOW = 1_800_000_000


def run_dt(args, cwd, env=None):
    full_env = dict(os.environ)
    full_env.pop("DEVTEAM_STALL_MINUTES", None)
    full_env.update(env or {})
    return subprocess.run([sys.executable, DEVTEAM_PATH] + args, cwd=str(cwd),
                          capture_output=True, text=True, env=full_env, timeout=60)


def git_run(args, cwd):
    subprocess.run(["git"] + args, cwd=str(cwd), check=True)


def make_dispatched_repo():
    """A repo whose only slice S1 is in flight: dispatched, never finished."""
    repo = Path(os.path.realpath(tempfile.mkdtemp()))
    git_run(["init", "-q", "-b", "main"], repo)
    for key, value in (("user.email", "t@t"), ("user.name", "t"), ("commit.gpgsign", "false")):
        git_run(["config", key, value], repo)
    for d in ("src", "tests"):
        (repo / d).mkdir()
        (repo / d / ".keep").write_text("")
    git_run(["add", "-A"], repo)
    git_run(["commit", "-q", "-m", "init"], repo)
    plan = {"request": "T03 fixtures", "profile": "balanced",
            "commands": {"test": "none", "test_file": "none"},
            "slices": [{"id": "S1", "title": "s1", "files": ["src/S1.js", "tests/S1.test.js"],
                        "risk": "low", "criteria": ["works"]}]}
    (repo / "plan.md").write_text("# plan\n" + FENCE + "json\n" + json.dumps(plan) + "\n" + FENCE + "\n")
    for cmd in (["init", "plan.md"], ["dispatch", "S1"]):
        r = run_dt(cmd, repo)
        assert r.returncode == 0, r.stdout + r.stderr
    return repo


def age_dispatch(repo, seconds):
    """Rewrite S1's dispatch time so the lane looks `seconds` old."""
    p = dt.state_dir(repo) / "state.json"
    st = json.loads(p.read_text())
    st["slices"]["S1"]["dispatched"] = int(time.time()) - seconds
    p.write_text(json.dumps(st))


def inflight_slice(sid, dispatched, mode="slice", history=None, status="inflight"):
    return {"id": sid, "status": status, "mode": mode, "dispatched": dispatched,
            "history": list(history or [])}


class TestStalledLanes(unittest.TestCase):
    """Direct-import tests of stalled_lanes / stall_lines / stall_minutes."""

    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("DEVTEAM_STALL_MINUTES", None)
        self.root = Path(os.path.realpath(tempfile.mkdtemp()))
        (dt.state_dir(self.root) / "slices").mkdir(parents=True)

    def state(self, **slices):
        return {"slices": slices, "script": "/x/devteam.py"}

    def test_silent_lane_older_than_default_is_stalled(self):
        st = self.state(S1=inflight_slice("S1", NOW - 25 * 60))
        self.assertEqual(dt.stalled_lanes(self.root, st, now_ts=NOW), [("S1", 25)])

    def test_threshold_is_twenty_minutes_by_default(self):
        self.assertEqual(dt.stall_minutes(), 20)
        young = self.state(S1=inflight_slice("S1", NOW - 19 * 60))
        exact = self.state(S1=inflight_slice("S1", NOW - 20 * 60))
        self.assertEqual(dt.stalled_lanes(self.root, young, now_ts=NOW), [])
        self.assertEqual(dt.stalled_lanes(self.root, exact, now_ts=NOW), [("S1", 20)])

    def test_done_marker_means_not_stalled(self):
        dt.marker_file(self.root, "S1", "done").write_text("{}")
        st = self.state(S1=inflight_slice("S1", NOW - 90 * 60))
        self.assertEqual(dt.stalled_lanes(self.root, st, now_ts=NOW), [])

    def test_blocked_marker_means_not_stalled(self):
        dt.marker_file(self.root, "S1", "blocked").write_text('{"note": "need an answer"}')
        st = self.state(S1=inflight_slice("S1", NOW - 90 * 60))
        self.assertEqual(dt.stalled_lanes(self.root, st, now_ts=NOW), [])

    def test_env_override_lowers_the_threshold(self):
        os.environ["DEVTEAM_STALL_MINUTES"] = "3"
        st = self.state(S1=inflight_slice("S1", NOW - 5 * 60))
        self.assertEqual(dt.stall_minutes(), 3)
        self.assertEqual(dt.stalled_lanes(self.root, st, now_ts=NOW), [("S1", 5)])

    def test_invalid_env_values_fall_back_to_default(self):
        for bad in ("abc", "0", "-5", ""):
            os.environ["DEVTEAM_STALL_MINUTES"] = bad
            self.assertEqual(dt.stall_minutes(), 20, bad)

    def test_recent_history_event_resets_the_clock(self):
        st = self.state(S1=inflight_slice("S1", NOW - 90 * 60,
                                          history=[{"t": NOW - 60, "event": "no-commit"}]))
        self.assertEqual(dt.stalled_lanes(self.root, st, now_ts=NOW), [])

    def test_only_inflight_lanes_can_stall(self):
        st = self.state(**{sid: inflight_slice(sid, NOW - 90 * 60, status=status)
                           for sid, status in (("A", "pending"), ("B", "done"), ("C", "failed"),
                                               ("D", "red-done"), ("E", "conflict"))})
        self.assertEqual(dt.stalled_lanes(self.root, st, now_ts=NOW), [])

    def test_lane_without_a_dispatch_time_is_never_reported(self):
        st = self.state(S1=inflight_slice("S1", None))
        self.assertEqual(dt.stalled_lanes(self.root, st, now_ts=NOW), [])

    def test_research_lane_with_finished_report_is_not_stalled(self):
        report = dt.state_dir(self.root) / "research" / "R1.md"
        report.parent.mkdir(parents=True)
        report.write_text("## Findings\nall good\n")
        st = self.state(R1=inflight_slice("R1", NOW - 90 * 60, mode="research"))
        self.assertEqual(dt.stalled_lanes(self.root, st, now_ts=NOW), [])

    def test_research_lane_without_a_report_is_stalled(self):
        st = self.state(R1=inflight_slice("R1", NOW - 90 * 60, mode="research"))
        self.assertEqual(dt.stalled_lanes(self.root, st, now_ts=NOW), [("R1", 90)])

    def test_stall_line_carries_the_exact_retry_command(self):
        st = self.state(S1=inflight_slice("S1", NOW - 30 * 60))
        lines = dt.stall_lines(self.root, st, now_ts=NOW)
        self.assertEqual(len(lines), 1, lines)
        self.assertTrue(lines[0].startswith("STALLED? S1"), lines[0])
        self.assertIn("python3 /x/devteam.py retry S1", lines[0])

    def test_no_stall_lines_when_nothing_is_stalled(self):
        st = self.state(S1=inflight_slice("S1", NOW - 60))
        self.assertEqual(dt.stall_lines(self.root, st, now_ts=NOW), [])


class TestStallInCommands(unittest.TestCase):
    """The same behavior seen through the real `next` and `status` commands."""

    def test_next_prints_stalled_with_the_retry_command(self):
        repo = make_dispatched_repo()
        age_dispatch(repo, 30 * 60)
        r = run_dt(["next"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("STALLED? S1", r.stdout)
        self.assertIn("retry S1", r.stdout)

    def test_status_prints_stalled_with_the_retry_command(self):
        repo = make_dispatched_repo()
        age_dispatch(repo, 30 * 60)
        r = run_dt(["status"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("STALLED? S1", r.stdout)
        self.assertIn("retry S1", r.stdout)

    def test_fresh_dispatch_prints_no_stall_line(self):
        repo = make_dispatched_repo()
        for cmd in ("next", "status"):
            r = run_dt([cmd], repo)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn("STALLED?", r.stdout)

    def test_env_override_reaches_the_engine(self):
        repo = make_dispatched_repo()
        age_dispatch(repo, 5 * 60)
        quiet = run_dt(["status"], repo)
        loud = run_dt(["status"], repo, env={"DEVTEAM_STALL_MINUTES": "1"})
        self.assertNotIn("STALLED?", quiet.stdout)
        self.assertIn("STALLED? S1", loud.stdout)

    def test_a_stalled_lane_is_reported_but_never_acted_on(self):
        repo = make_dispatched_repo()
        age_dispatch(repo, 30 * 60)
        self.assertEqual(run_dt(["next"], repo).returncode, 0)
        st = json.loads((dt.state_dir(repo) / "state.json").read_text())
        self.assertEqual(st["slices"]["S1"]["status"], "inflight")


if __name__ == "__main__":
    unittest.main()
