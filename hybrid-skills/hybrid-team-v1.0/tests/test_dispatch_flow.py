"""Engine-level tests for routing state, the RED/GREEN code split, independent slot caps and
escalation, driven through `devteam.py` subprocesses and the fake opencode CLI."""
import argparse
import contextlib
import fcntl
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import devteam  # noqa: E402

TESTS_DIR = Path(__file__).resolve().parent
ENGINE = SCRIPTS / "devteam.py"
DEVTEAM_ENGINE = TESTS_DIR.parents[1] / "dev-team-v3.2" / "scripts" / "devteam.py"
FAKE = TESTS_DIR / "fake_opencode.py"
STATE = ".claude/hybrid-team"

DONE_TEXT = ("## Slice: D1\n## Status: Done\n## Gate:\n$ test -f docs/d1.md\n"
             "exit 0 - docs/d1.md is present\n## Notes:\nwrote the doc\n")
DONE_STEP = {"write": {"docs/d1.md": "# D1\n"}, "commit": "docs(D1): add the doc", "text": DONE_TEXT}
BLOCKED_STEP = {"text": "## Slice: D1\n## Status: Blocked\n## Notes:\nthe verify command needs network access\n"}
MODELS_ENV = {"HYBRID_OPENCODE_STD": "zai-coding-plan/glm-5.3#high",
              "HYBRID_OPENCODE_LITE": "zai-coding-plan/glm-5.3-flash#low"}


def code_slice(sid):
    return {"id": sid, "title": "code " + sid, "goal": "implement " + sid, "kind": "code", "size": "small",
            "deps": [], "files": ["src/%s.py" % sid.lower(), "tests/test_%s.py" % sid.lower()],
            "criteria": [sid + " works"]}


def docs_slice(sid):
    return {"id": sid, "title": "doc " + sid, "goal": "write doc " + sid, "kind": "docs", "size": "small",
            "deps": [], "files": ["docs/%s.md" % sid.lower()], "criteria": ["doc exists"],
            "verify": "test -f docs/%s.md" % sid.lower()}


def chore_slice(sid):
    return {"id": sid, "title": "chore " + sid, "goal": "tidy " + sid, "kind": "chore", "size": "small",
            "deps": [], "files": ["conf/%s.cfg" % sid.lower()], "criteria": ["config exists"],
            "verify": "test -f conf/%s.cfg" % sid.lower()}


def plan_of(*slices, **extra):
    p = {"request": "flow test", "commands": {"test": "none"}, "slices": list(slices)}
    p.update(extra)
    return p


def git(args, cwd):
    r = subprocess.run(["git"] + list(args), cwd=str(cwd), text=True, capture_output=True, check=True)
    return r.stdout.strip()


def make_repo(path):
    path.mkdir()
    git(["init", "-q"], path)
    git(["config", "user.email", "t@example.invalid"], path)
    git(["config", "user.name", "t"], path)
    git(["config", "commit.gpgsign", "false"], path)
    (path / "README.md").write_text("demo\n")
    git(["add", "README.md"], path)
    git(["commit", "-qm", "init"], path)


class FlowBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.repo = self.tmp / "repo"
        make_repo(self.repo)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.script = self.tmp / "fake_script.json"
        self.routing = self.tmp / "routing.json"
        self.env = dict(os.environ, HOME=str(self.home), HYBRID_TEAM_OC_BIN=str(FAKE),
                        HYBRID_TEAM_FAKE_SCRIPT=str(self.script), HYBRID_TEAM_FAKE_LOG=str(self.tmp / "fake_log.jsonl"),
                        HYBRID_TEAM_ROUTING=str(self.routing), XDG_DATA_HOME=str(self.tmp / "xdg"),
                        PYTHONDONTWRITEBYTECODE="1", HYBRID_OC_RETRY_DELAY_S="0", **MODELS_ENV)
        self.env.pop("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", None)
        self.env.pop("HYBRID_OPENCODE_MAX_PARALLEL", None)
        self.state_dir = self.repo / STATE

    def engine(self, *args, check=True, engine=ENGINE, cwd=None):
        r = subprocess.run([sys.executable, str(engine)] + list(args), cwd=str(cwd or self.repo), env=self.env,
                           text=True, capture_output=True, timeout=120)
        if check:
            self.assertEqual(r.returncode, 0, msg="%s\n%s" % (r.stdout, r.stderr))
        return r

    def init(self, plan, *flags, cwd=None, engine=ENGINE):
        path = self.tmp / "plan.json"
        path.write_text(json.dumps(plan))
        return self.engine("init", str(path), *flags, cwd=cwd, engine=engine)

    def set_routing(self, data):
        self.routing.write_text(json.dumps(data))

    def st(self):
        return json.loads((self.state_dir / "state.json").read_text())

    def save_st(self, st):
        (self.state_dir / "state.json").write_text(json.dumps(st))


class InitRoutingStateTest(FlowBase):
    def test_init_records_merged_routing_preset_and_oc_ok(self):
        self.set_routing({"preset": "max", "tiers": {"std": {"max_parallel": 2}}})
        self.init(plan_of(code_slice("C1"), routing={"rows": {"docs": "std"}}))
        st = self.st()
        self.assertEqual(st["routing"]["tiers"]["std"]["max_parallel"], 2)
        self.assertEqual(st["routing"]["tiers"]["lite"]["model"], "zai-coding-plan/glm-5.3-flash")
        self.assertEqual(st["routing"]["rows"]["docs"], "std")
        self.assertEqual(st["preset"], "opencode")
        self.assertIs(st["oc_ok"], True)

    def test_route_flag_overrides_routing_preset(self):
        self.set_routing({"preset": "hybrid"})
        self.init(plan_of(code_slice("C1")), "--route", "claude")
        self.assertEqual(self.st()["preset"], "claude")

    def test_missing_binary_gives_plain_dev_team_dispatch(self):
        self.env["HYBRID_TEAM_OC_BIN"] = str(self.tmp / "no-such-opencode")
        self.init(plan_of(code_slice("C1"), docs_slice("D1"), chore_slice("H1")))
        self.assertIs(self.st()["oc_ok"], False)
        r = self.engine("dispatch", "C1", "D1", "H1")
        self.assertNotIn("=== LANE", r.stdout)
        self.assertIn("=== DISPATCH C1 [CODE/SLICE]", r.stdout)
        self.assertIn("=== DISPATCH D1 [DOCS/WORK]", r.stdout)
        self.assertIn("=== DISPATCH H1 [CHORE/WORK]", r.stdout)
        self.assertEqual(r.stdout.count("subagent_type: hybrid-team-programmer"), 3)


class InitBackendPinTest(FlowBase):
    def test_init_copies_backend_into_state(self):
        plan = plan_of(docs_slice("D1"))
        plan["slices"][0]["backend"] = "claude"
        self.init(plan)
        self.assertEqual(self.st()["slices"]["D1"]["backend"], "claude")

    def test_backend_claude_pin_dispatches_not_lane(self):
        plan = plan_of(docs_slice("D1"))
        plan["slices"][0]["backend"] = "claude"
        self.init(plan)
        self.assertIs(self.st()["oc_ok"], True)
        self.assertEqual(self.st()["preset"], "hybrid")
        r = self.engine("dispatch", "D1")
        self.assertIn("=== DISPATCH D1", r.stdout)
        self.assertNotIn("=== LANE", r.stdout)

    def test_oc_pin_on_risk_high_slice_still_dispatches_on_claude(self):
        plan = plan_of(docs_slice("D1"))
        plan["slices"][0]["backend"] = "oc:lite"
        plan["slices"][0]["risk"] = "high"
        self.init(plan)
        r = self.engine("dispatch", "D1")
        self.assertIn("=== DISPATCH D1", r.stdout)

    def test_unknown_backend_value_warns_on_init(self):
        plan = plan_of(docs_slice("D1"))
        plan["slices"][0]["backend"] = "bogus"
        r = self.init(plan)
        self.assertIn("NOTE:", r.stdout)
        self.assertIn("D1", r.stdout)
        self.assertIn("backend", r.stdout.lower())

    def test_backend_tier_absent_from_routing_warns_naming_slice(self):
        plan = plan_of(docs_slice("D1"))
        plan["slices"][0]["backend"] = "oc:ghost"
        r = self.init(plan)
        self.assertIn("NOTE:", r.stdout)
        self.assertIn("D1", r.stdout)
        self.assertIn("oc:ghost", r.stdout)

    def test_non_string_backend_value_warns_not_raises(self):
        for val in (True, 5):
            plan = plan_of(docs_slice("D1"))
            plan["slices"][0]["backend"] = val
            r = self.init(plan, "--force")
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            self.assertIn("NOTE:", r.stdout)
            self.assertIn("D1", r.stdout)


class LaneStillRunningTest(FlowBase):
    def _record_live_pid(self, sid):
        """Simulate a genuinely running lane process: a real process whose recorded argv still
        matches `ps`, the same shape `run_once` records for `kill_stale_lane`/`lane_is_live`."""
        proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.addCleanup(self._reap, proc)
        args = subprocess.run(["ps", "-ww", "-o", "args=", "-p", str(proc.pid)],
                              text=True, capture_output=True).stdout.strip()
        lanes = self.state_dir / "lanes"
        lanes.mkdir(parents=True, exist_ok=True)
        (lanes / f"{sid}.pid").write_text(json.dumps({"pid": proc.pid, "args": args}))
        return proc

    @staticmethod
    def _reap(proc):
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)

    def _dispatch_and_claim(self, sid):
        self.init(plan_of(docs_slice(sid)))
        r = self.engine("dispatch", sid)
        self.assertIn(f"=== LANE {sid} oc:lite", r.stdout)
        wt = self.repo / ".claude" / "worktrees" / ("hybrid-oc-" + sid)
        git(["worktree", "add", "-f", "-B", "hybrid-oc-" + sid, str(wt)], self.repo)
        base = git(["rev-parse", "HEAD"], self.repo)
        claim_path = self.state_dir / "slices" / (sid + ".claim.json")
        claim_path.parent.mkdir(parents=True, exist_ok=True)
        claim_path.write_text(json.dumps({"id": sid, "worktree": str(wt), "branch": "hybrid-oc-" + sid,
                                          "base": base, "claimed": "now", "attempt": 1}))
        target = wt / "docs" / (sid.lower() + ".md")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# in progress, not committed\n")
        return wt

    def test_integrate_running_lane_prints_still_running_and_does_not_escalate(self):
        wt = self._dispatch_and_claim("D1")
        self._record_live_pid("D1")
        r = self.engine("integrate", "D1")
        self.assertIn("lane still running", r.stdout)
        self.assertNotIn("ESCALATE", r.stdout)
        self.assertTrue(wt.exists())
        self.assertEqual(self.st()["backends"]["D1"], "oc:lite")

    def test_integrate_dead_lane_does_not_print_still_running_and_escalates(self):
        """No pid record at all — the plain 'no marker yet' case that used to hang forever."""
        wt = self._dispatch_and_claim("D1")
        r = self.engine("integrate", "D1")
        self.assertNotIn("lane still running", r.stdout)
        self.assertIn("ESCALATE D1", r.stdout)

    def test_integrate_stale_pid_record_does_not_print_still_running_and_escalates(self):
        """A pid record exists but the process behind it is gone (or the pid was recycled)."""
        wt = self._dispatch_and_claim("D1")
        lanes = self.state_dir / "lanes"
        lanes.mkdir(parents=True, exist_ok=True)
        (lanes / "D1.pid").write_text(json.dumps({"pid": 999999, "args": "opencode run --standalone"}))
        r = self.engine("integrate", "D1")
        self.assertNotIn("lane still running", r.stdout)
        self.assertIn("ESCALATE D1", r.stdout)

    def test_rejected_lane_with_marker_still_escalates(self):
        """No regression: a lane that DID finish (marker present) but fails gate keeps escalating."""
        self.init(plan_of(docs_slice("D1")))
        r = self.engine("dispatch", "D1")
        self.assertIn("=== LANE D1 oc:lite", r.stdout)
        self.script.write_text(json.dumps(DONE_STEP))
        self.engine("lane", "D1")
        wt = self.repo / ".claude" / "worktrees" / "hybrid-oc-D1"
        (wt / "docs" / "d1.md").write_text("# D1 edited, not committed\n")
        r = self.engine("integrate", "D1")
        self.assertIn("ESCALATE D1", r.stdout)


class LaneLivenessRecordedBeforeWorktreeTest(FlowBase):
    def test_cmd_lane_records_own_pid_before_worktree_and_claim(self):
        """The pid file must exist, with this process's own pid, at the moment `lane_worktree`
        is first called — proving the liveness record predates worktree/claim, so the start-up
        window is covered even though no opencode child exists yet."""
        self.init(plan_of(docs_slice("D1")))
        self.engine("dispatch", "D1")
        pidf = self.state_dir / "lanes" / "D1.pid"
        seen = {}

        def fail_worktree(root, st, sid):
            try:
                seen["rec"] = json.loads(pidf.read_text())
            except OSError:
                seen["rec"] = None
            raise devteam.DevteamError("boom-for-test")

        old_cwd = os.getcwd()
        old_env = dict(os.environ)
        os.chdir(str(self.repo))
        os.environ.update(self.env)
        try:
            with mock.patch.object(devteam, "lane_worktree", side_effect=fail_worktree):
                devteam.cmd_lane(argparse.Namespace(id="D1"))
        finally:
            os.chdir(old_cwd)
            os.environ.clear()
            os.environ.update(old_env)

        self.assertIsNotNone(seen.get("rec"))
        self.assertEqual(seen["rec"]["pid"], os.getpid())
        marker = json.loads((self.state_dir / "slices" / "D1.blocked").read_text())
        self.assertEqual(marker["reason"], "spawn")


class LaneLivenessDuringGateTest(FlowBase):
    def test_lane_is_live_during_gate_gap_and_cleared_after_cmd_lane_returns(self):
        """Between two opencode runs -- inside run_stop_gate, with no child process and no marker
        yet -- the lane must still read as live, and `integrate` must say so without escalating.
        Once cmd_lane truly returns (here: done, on the second gate call), no liveness record may
        remain and `lane_is_live` must go back to False."""
        self.init(plan_of(docs_slice("D1")))
        self.engine("dispatch", "D1")
        self.script.write_text(json.dumps({"text": "run text"}))
        seen = {}
        calls = {"n": 0}

        def fake_gate(wt, text):
            calls["n"] += 1
            if calls["n"] == 1:
                # no opencode child running right now, and no .done/.blocked marker yet
                seen["live_during_gate"] = devteam.lane_is_live(self.repo, "D1")
                st = devteam.load_state(self.repo)
                results = devteam.do_integrate(self.repo, st, ["D1"], remove=False)
                seen["integrate_msg"] = results[0]
                return subprocess.CompletedProcess(args=[], returncode=2, stdout="", stderr="continue please")
            devteam.write_atomic(devteam.marker_file(self.repo, "D1", "done"), json.dumps({}))
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        old_cwd, old_env = os.getcwd(), dict(os.environ)
        os.chdir(str(self.repo))
        os.environ.clear()
        os.environ.update(self.env)
        try:
            with mock.patch.object(devteam, "run_stop_gate", side_effect=fake_gate):
                devteam.cmd_lane(argparse.Namespace(id="D1"))
        finally:
            os.chdir(old_cwd)
            os.environ.clear()
            os.environ.update(old_env)

        self.assertEqual(calls["n"], 2)
        self.assertTrue(seen.get("live_during_gate"))
        self.assertIn("lane still running", seen.get("integrate_msg", ""))
        self.assertNotIn("ESCALATE", seen.get("integrate_msg", ""))
        self.assertFalse(devteam.lane_is_live(self.repo, "D1"))
        self.assertFalse((self.state_dir / "lanes" / "D1.pid").exists())


def ps_args(pid):
    return subprocess.run(["ps", "-ww", "-o", "args=", "-p", str(pid)], text=True, capture_output=True).stdout.strip()


def reap(proc):
    if proc.poll() is None:
        proc.kill()
        proc.wait(timeout=10)


def gone(pid, wait_s=10.0):
    """True once `pid` no longer exists (or is only a zombie) within `wait_s` seconds."""
    end = time.time() + wait_s
    while time.time() < end:
        state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], text=True, capture_output=True).stdout.strip()
        if not state or state.startswith("Z"):
            return True
        time.sleep(0.1)
    return False


def run_lane_inproc(case, sid="D1", **patches):
    """Run `cmd_lane(sid)` in this process from `case.repo` with `case.env`, patching devteam attributes."""
    old_cwd, old_env = os.getcwd(), dict(os.environ)
    os.chdir(str(case.repo))
    os.environ.clear()
    os.environ.update(case.env)
    try:
        with mock.patch.multiple(devteam, **patches) if patches else mock.patch.object(devteam, "out"):
            devteam.cmd_lane(argparse.Namespace(id=sid))
    finally:
        os.chdir(old_cwd)
        os.environ.clear()
        os.environ.update(old_env)


@contextlib.contextmanager
def inproc(case):
    """Run engine calls in this process from `case.repo` with `case.env`."""
    old_cwd, old_env = os.getcwd(), dict(os.environ)
    os.chdir(str(case.repo))
    os.environ.clear()
    os.environ.update(case.env)
    try:
        yield
    finally:
        os.chdir(old_cwd)
        os.environ.clear()
        os.environ.update(old_env)


class KillStaleLaneNeverKillsOwnPidTest(FlowBase):
    def write_rec(self, rec):
        lanes = self.state_dir / "lanes"
        lanes.mkdir(parents=True, exist_ok=True)
        (lanes / "D1.pid").write_text(json.dumps(rec))

    def test_kill_stale_lane_skips_a_record_matching_its_own_pid(self):
        """An own-pid record (pid recycling) must never reach os.killpg."""
        self.write_rec({"pid": os.getpid(), "args": ps_args(os.getpid())})
        with mock.patch("os.killpg") as kp:
            note = devteam.kill_stale_lane(self.repo, "D1")
        kp.assert_not_called()
        self.assertEqual(note, "")

    def test_kill_stale_lane_never_kills_a_live_engine_record(self):
        """A live previous engine (engine: true, exact argv, not our pid) must never be killpg'd."""
        proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.addCleanup(reap, proc)
        args = ps_args(proc.pid)
        self.assertTrue(args)
        self.assertNotEqual(proc.pid, os.getpid())
        self.write_rec({"pid": proc.pid, "args": args, "engine": True})
        with mock.patch("os.killpg") as kp:
            devteam.kill_stale_lane(self.repo, "D1")
        kp.assert_not_called()
        self.assertIsNone(proc.poll())

    def test_record_lane_pid_marks_engine(self):
        (self.state_dir / "lanes").mkdir(parents=True, exist_ok=True)
        devteam.record_lane_pid(self.repo, "D1", os.getpid())
        rec = json.loads((self.state_dir / "lanes" / "D1.pid").read_text())
        self.assertEqual(rec["pid"], os.getpid())
        self.assertIs(rec["engine"], True)

    def test_kill_stale_lane_still_kills_a_recorded_live_opencode_child(self):
        """No regression: a genuinely live, different process is still killed as before."""
        proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.addCleanup(lambda: proc.poll() is None and (proc.kill(), proc.wait(timeout=10)))
        args = subprocess.run(["ps", "-ww", "-o", "args=", "-p", str(proc.pid)],
                              text=True, capture_output=True).stdout.strip()
        lanes = self.state_dir / "lanes"
        lanes.mkdir(parents=True, exist_ok=True)
        (lanes / "D1.pid").write_text(json.dumps({"pid": proc.pid, "args": args}))
        note = devteam.kill_stale_lane(self.repo, "D1")
        self.assertIn("killed stale lane process group", note)
        proc.wait(timeout=10)
        self.assertIsNotNone(proc.poll())


class LaneSingleEngineTest(FlowBase):
    def setUp(self):
        super().setUp()
        self.init(plan_of(docs_slice("D1")))
        self.assertIn("=== LANE D1 oc:lite", self.engine("dispatch", "D1").stdout)
        self.lanes = self.state_dir / "lanes"
        self.lanes.mkdir(parents=True, exist_ok=True)
        self.pidf = self.lanes / "D1.pid"

    def test_second_lane_refused_while_engine_live(self):
        proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.addCleanup(reap, proc)
        rec = json.dumps({"pid": proc.pid, "args": ps_args(proc.pid), "engine": True})
        self.pidf.write_text(rec)
        marker_dir = self.state_dir / "slices"
        with self.assertRaises(devteam.DevteamError) as cm:
            run_lane_inproc(self)
        self.assertIn("lane already running", str(cm.exception))
        self.assertEqual(self.pidf.read_text(), rec)
        self.assertFalse((marker_dir / "D1.done").exists())
        self.assertFalse((marker_dir / "D1.blocked").exists())
        self.assertFalse((self.repo / ".claude" / "worktrees" / "hybrid-oc-D1").exists())
        self.assertIsNone(proc.poll())

    def test_dead_engine_record_is_removed_as_stale(self):
        self.pidf.write_text(json.dumps({"pid": 999999, "args": "python3 devteam.py lane D1", "engine": True}))
        run_lane_inproc(self, lane_worktree=mock.Mock(side_effect=devteam.DevteamError("boom-for-test")))
        self.assertFalse(self.pidf.exists())
        self.assertEqual(json.loads((self.state_dir / "slices" / "D1.blocked").read_text())["reason"], "spawn")

    def test_record_removed_only_after_blocked_marker(self):
        seen = {}
        real = devteam.write_lane_marker

        def spy(*a, **k):
            seen["during"] = self.pidf.exists()
            return real(*a, **k)

        run_lane_inproc(self, lane_worktree=mock.Mock(side_effect=devteam.DevteamError("boom-for-test")),
                             write_lane_marker=spy)
        self.assertIs(seen.get("during"), True)
        self.assertTrue((self.state_dir / "slices" / "D1.blocked").exists())
        self.assertFalse(self.pidf.exists())

    def test_record_removed_only_after_done_patch(self):
        self.script.write_text(json.dumps({"text": "run text"}))
        seen = {}
        real = devteam._patch_marker

        def gate(wt, text):
            devteam.write_atomic(devteam.marker_file(self.repo, "D1", "done"), json.dumps({}))
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        def spy(*a, **k):
            seen["during"] = self.pidf.exists()
            return real(*a, **k)

        run_lane_inproc(self, run_stop_gate=gate, _patch_marker=spy)
        self.assertIs(seen.get("during"), True)
        self.assertEqual(json.loads((self.state_dir / "slices" / "D1.done").read_text())["backend"], "oc:lite")
        self.assertFalse(self.pidf.exists())


class SupersedeLaneTest(FlowBase):
    ENGINE_SRC = ("import subprocess, sys, time\n"
                  "c = subprocess.Popen(['sleep', '60'], start_new_session=True)\n"
                  "print(c.pid, flush=True)\n"
                  "time.sleep(60)\n")

    def start_live_lane(self):
        self.init(plan_of(docs_slice("D1")))
        self.assertIn("=== LANE D1 oc:lite", self.engine("dispatch", "D1").stdout)
        eng = subprocess.Popen([sys.executable, "-c", self.ENGINE_SRC], stdout=subprocess.PIPE, text=True)
        self.addCleanup(reap, eng)
        child = int(eng.stdout.readline())
        self.addCleanup(lambda: subprocess.run(["kill", "-9", str(child)], capture_output=True))
        lanes = self.state_dir / "lanes"
        lanes.mkdir(parents=True, exist_ok=True)
        (lanes / "D1.pid").write_text(json.dumps({"pid": eng.pid, "args": ps_args(eng.pid), "engine": True}))
        return eng, child, lanes / "D1.pid"

    def assert_superseded(self, eng, child, pidf):
        eng.wait(timeout=15)
        self.assertIsNotNone(eng.poll())
        self.assertTrue(gone(child))
        self.assertFalse(pidf.exists())

    def test_retry_terminates_live_lane_before_requeue(self):
        eng, child, pidf = self.start_live_lane()
        r = self.engine("retry", "D1")
        self.assertIn("re-queued", r.stdout)
        self.assert_superseded(eng, child, pidf)
        self.assertEqual(self.st()["slices"]["D1"]["status"], "pending")

    def test_fail_terminates_live_lane(self):
        eng, child, pidf = self.start_live_lane()
        self.engine("fail", "D1", "--why", "stuck")
        self.assert_superseded(eng, child, pidf)
        self.assertEqual(self.st()["slices"]["D1"]["status"], "failed")


class SliceBackendFallbackTest(unittest.TestCase):
    def test_falls_back_to_routing_preset(self):
        routing = {"preset": "claude", "tiers": {"std": {"model": "m", "variant": "v"}},
                   "rows": {"refactor": "std"}}
        st = {"routing": routing, "oc_ok": True}
        s = {"id": "S1", "kind": "refactor", "size": "small", "backend": "oc:std"}
        self.assertEqual(devteam.slice_backend(st, s, "work"), "claude")
        st["routing"] = dict(routing, preset="max")
        self.assertEqual(devteam.slice_backend(st, s, "work"), "oc:std")


class CodeSplitTest(FlowBase):
    def test_red_on_claude_then_green_on_opencode(self):
        self.init(plan_of(code_slice("C1")))
        r = self.engine("dispatch", "C1")
        self.assertIn("=== DISPATCH C1 [CODE/RED]", r.stdout)
        self.assertIn("subagent_type: hybrid-team-programmer", r.stdout)
        self.assertNotIn("=== LANE", r.stdout)
        st = self.st()
        self.assertEqual(st["slices"]["C1"]["mode"], "red")
        self.assertEqual(st["backends"]["C1"], "claude")
        # the RED commit was integrated
        s = st["slices"]["C1"]
        s.update(status="red-done", red_sha=git(["rev-parse", "HEAD"], self.repo), worktree=None, branch=None)
        self.save_st(st)
        r = self.engine("dispatch", "C1")
        self.assertIn("=== LANE C1 oc:std", r.stdout)
        self.assertNotIn("=== DISPATCH C1", r.stdout)
        st = self.st()
        self.assertEqual(st["slices"]["C1"]["mode"], "green")
        self.assertEqual(st["backends"]["C1"], "oc:std")


class EscalationTest(FlowBase):
    def dispatch_lane(self):
        self.init(plan_of(docs_slice("D1")))
        r = self.engine("dispatch", "D1")
        self.assertIn("=== LANE D1 oc:lite", r.stdout)

    def assert_escalated_dispatch(self, text):
        self.assertIn("ESCALATE D1", text)
        self.assertIn("=== DISPATCH D1 [DOCS/WORK]", text)
        self.assertLess(text.index("ESCALATE D1"), text.index("=== DISPATCH D1"))
        block = text[text.index("=== DISPATCH D1"):]
        self.assertIn("subagent_type: hybrid-team-programmer", block.splitlines()[1])
        s = self.st()
        self.assertEqual(s["slices"]["D1"]["attempt"], 2)
        self.assertEqual(s["slices"]["D1"]["status"], "inflight")
        self.assertEqual(s["backends"]["D1"], "claude")

    def test_blocked_lane_is_redispatched_to_claude_once(self):
        self.dispatch_lane()
        self.script.write_text(json.dumps(BLOCKED_STEP))
        self.engine("lane", "D1", check=False)
        self.assertTrue((self.state_dir / "slices" / "D1.blocked").exists())
        r = self.engine("next", "--no-review")
        self.assertTrue(r.stdout.startswith("OC-WARN hybrid-team D1 tier=lite"), r.stdout)
        self.assert_escalated_dispatch(r.stdout)
        r2 = self.engine("next", "--no-review")
        self.assertNotIn("OC-WARN hybrid-team D1", r2.stdout)
        self.assertNotIn("ESCALATE D1", r2.stdout)
        self.assertNotIn("=== DISPATCH D1", r2.stdout)
        self.assertEqual(self.st()["slices"]["D1"]["attempt"], 2)

    def test_rejected_lane_is_redispatched_in_same_integrate_output(self):
        self.dispatch_lane()
        self.script.write_text(json.dumps(DONE_STEP))
        self.engine("lane", "D1")
        wt = self.repo / ".claude" / "worktrees" / "hybrid-oc-D1"
        (wt / "docs" / "d1.md").write_text("# D1 edited, not committed\n")
        r = self.engine("integrate", "D1")
        self.assertIn("NOT READY", r.stdout)
        self.assert_escalated_dispatch(r.stdout)
        self.assertIn("OC-WARN hybrid-team D1 tier=lite", r.stdout)
        self.assertIn("kind=gate", r.stdout)
        self.assertLess(r.stdout.index("OC-WARN hybrid-team D1"), r.stdout.index("ESCALATE D1"))


class SlotCapTest(FlowBase):
    @staticmethod
    def free_of(text):
        m = re.search(r"(\d+) free of (\d+)", text)
        return int(m.group(1)), int(m.group(2))

    def test_lanes_do_not_use_claude_slots(self):
        self.init(plan_of(docs_slice("D1"), docs_slice("D2"), code_slice("C1")))
        before = self.free_of(self.engine("ready").stdout)
        r = self.engine("dispatch", "D1", "D2")
        self.assertEqual(r.stdout.count("=== LANE"), 2)
        self.assertEqual(self.free_of(self.engine("ready").stdout), before)

    def test_next_limits_lanes_by_tier_cap_only(self):
        self.env["CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS"] = "3"
        self.set_routing({"tiers": {"lite": {"max_parallel": 2}}})
        self.init(plan_of(docs_slice("D1"), docs_slice("D2"), docs_slice("D3"), code_slice("C1"),
                          code_slice("C2")))
        r = self.engine("next", "--no-review")
        self.assertEqual(r.stdout.count("=== LANE"), 2, r.stdout)
        self.assertEqual(r.stdout.count("=== DISPATCH"), 1, r.stdout)
        self.assertNotIn("SKIPPED", r.stdout)

    def test_fail_frees_tier_slot(self):
        self.set_routing({"tiers": {"lite": {"max_parallel": 1}}})
        self.init(plan_of(docs_slice("D1"), docs_slice("D2")))
        self.assertIn("=== LANE D1", self.engine("dispatch", "D1").stdout)
        r = self.engine("dispatch", "D2")
        self.assertNotIn("=== LANE D2", r.stdout)
        self.assertIn("no free oc:lite lane slot", r.stdout)
        self.engine("fail", "D1", "--why", "lane died")
        self.assertIn("=== LANE D2 oc:lite", self.engine("dispatch", "D2").stdout)

    def test_oc_slots_derived_from_inflight_backends(self):
        st = {"routing": {"tiers": {"lite": {"max_parallel": 3}}},
              "slices": {"A": {"status": "inflight"}, "B": {"status": "failed"}, "C": {"status": "inflight"}},
              "backends": {"A": "oc:lite", "B": "oc:lite", "C": "claude"}}
        self.assertEqual(devteam.oc_slots(st, "lite"), 2)


class LaneBackendTest(FlowBase):
    def test_lane_uses_recorded_backend(self):
        self.init(plan_of(docs_slice("D1")))
        self.assertIn("=== LANE D1 oc:lite", self.engine("dispatch", "D1").stdout)
        self.set_routing({"rows": {"docs": "std"}})
        self.script.write_text(json.dumps(DONE_STEP))
        self.engine("lane", "D1")
        recs = [json.loads(x) for x in (self.state_dir / "lanes.jsonl").read_text().splitlines() if x.strip()]
        self.assertEqual(recs[-1]["backend"], "oc:lite")
        self.assertEqual(recs[-1]["model"], "zai-coding-plan/glm-5.3-flash")

    def test_non_oc_backend_writes_spawn_marker(self):
        self.set_routing({"preset": "claude"})
        self.init(plan_of(docs_slice("D1")))
        self.assertIn("=== DISPATCH D1", self.engine("dispatch", "D1").stdout)
        self.engine("lane", "D1", check=False)
        m = json.loads((self.state_dir / "slices" / "D1.blocked").read_text())
        self.assertEqual(m["reason"], "spawn")
        self.assertEqual(m["backend"], "claude")
        self.assertIn("note", m)


class EscalatedLockTest(unittest.TestCase):
    def test_mark_lane_escalated_holds_flock_through_replace(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(tmp), True)
        path = tmp / "lanes.jsonl"
        path.write_text(json.dumps({"id": "S1", "escalated": False}) + "\n")
        seen = []
        real_replace = os.replace

        def probe(src, dst):
            with open(str(path)) as f:
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(f, fcntl.LOCK_UN)
                    seen.append("unlocked")
                except OSError:
                    seen.append("locked")
            return real_replace(src, dst)

        with mock.patch.object(devteam.os, "replace", side_effect=probe):
            devteam._mark_lane_escalated(path, "S1")
        self.assertEqual(seen, ["locked"])
        self.assertTrue(json.loads(path.read_text().splitlines()[0])["escalated"])


class PresetClaudeParityTest(FlowBase):
    @staticmethod
    def normalize(text, repo):
        text = text.replace(str(repo), "REPO")
        text = re.sub(r"python3 \S*devteam\.py", "python3 ENGINE", text)
        return text.replace("hybrid-team-programmer", "programmer")

    def test_dispatch_output_matches_dev_team(self):
        if not DEVTEAM_ENGINE.exists():
            self.skipTest("dev-team-v3.2 not present")
        self.set_routing({"preset": "claude"})
        plan = plan_of(code_slice("C1"), docs_slice("D1"), chore_slice("H1"))
        self.init(plan)
        mine = self.engine("dispatch", "C1", "D1", "H1").stdout
        other_repo = self.tmp / "other"
        make_repo(other_repo)
        self.init(plan, cwd=other_repo, engine=DEVTEAM_ENGINE)
        theirs = self.engine("dispatch", "C1", "D1", "H1", cwd=other_repo, engine=DEVTEAM_ENGINE).stdout
        self.assertIn("=== DISPATCH C1 [CODE/SLICE]", mine)
        self.assertEqual(self.normalize(mine, self.repo).splitlines(),
                         self.normalize(theirs, other_repo).splitlines())


class PresetConfigTest(FlowBase):
    def test_route_max_becomes_opencode_with_a_config_warning(self):
        r = self.init(plan_of(docs_slice("D1")), "--route", "max")
        self.assertEqual(self.st()["preset"], "opencode")
        self.assertIn("OC-WARN hybrid-team preset", r.stdout)
        self.assertIn("kind=config", r.stdout)

    def test_unknown_route_is_a_config_error_and_stops(self):
        path = self.tmp / "plan.json"
        path.write_text(json.dumps(plan_of(docs_slice("D1"))))
        r = self.engine("init", str(path), "--route", "bogus", check=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("OC-ERROR hybrid-team preset", r.stdout)
        self.assertIn("kind=config", r.stdout)
        self.assertFalse((self.state_dir / "state.json").exists())

    def test_missing_shared_config_is_reported_and_hybrid_falls_back(self):
        self.env.pop("HYBRID_OPENCODE_STD")
        self.env.pop("HYBRID_OPENCODE_LITE")
        r = self.init(plan_of(docs_slice("D1")))
        self.assertIn("OC-ERROR hybrid-team config", r.stdout)
        self.assertIn("kind=config", r.stdout)
        self.assertIs(self.st()["oc_ok"], False)
        self.assertIn("=== DISPATCH D1", self.engine("dispatch", "D1").stdout)


class UnreportedLinesTest(FlowBase):
    def log(self, unit):
        line = devteam.hybrid_shared.oc_line("OC-ERROR", "hybrid-team", unit, "lite",
                                             "zai-coding-plan/glm-5.3-flash#low", "auth", "invalid api key")
        devteam.hybrid_shared.log_line(self.state_dir / "oc-errors.jsonl", line)
        return line

    def test_next_prints_unreported_lines_first_and_once(self):
        self.init(plan_of(docs_slice("D1")))
        line = self.log("D1")
        r = self.engine("next", "--no-review")
        self.assertEqual(r.stdout.splitlines()[0], line)
        self.assertNotIn(line, self.engine("next", "--no-review").stdout)

    def test_status_prints_unreported_lines_first(self):
        self.init(plan_of(docs_slice("D1")))
        line = self.log("D1")
        self.assertEqual(self.engine("status").stdout.splitlines()[0], line)


class StartDoctorTest(FlowBase):
    def start(self, *flags):
        path = self.tmp / "plan.json"
        path.write_text(json.dumps(plan_of(docs_slice("D1"))))
        seen = []
        with inproc(self), mock.patch.object(devteam, "cmd_doctor", side_effect=seen.append), \
                mock.patch("sys.stdout", io.StringIO()):
            rc = devteam.main(["start", str(path)] + list(flags))
        self.assertEqual(rc, 0)
        return seen[0]

    def test_start_pings_stale_tiers_in_preset_hybrid(self):
        a = self.start()
        self.assertEqual((a.fix, a.ping, a.oc), (True, "stale", True))

    def test_start_never_touches_opencode_in_preset_claude(self):
        a = self.start("--route", "claude")
        self.assertEqual((a.fix, a.ping, a.oc), (True, False, False))
        self.assertEqual(self.st()["preset"], "claude")


class BreakerSummaryTest(FlowBase):
    def test_endgame_reports_the_breaker_summary(self):
        self.init(plan_of(docs_slice("D1")))
        st = self.st()
        st["slices"]["D1"].update(status="done", merged_sha=git(["rev-parse", "HEAD"], self.repo))
        self.save_st(st)
        line = devteam.hybrid_shared.oc_line("OC-ERROR", "hybrid-team", "breaker", "lite",
                                             "zai-coding-plan/glm-5.3-flash#low", "breaker", "3 units skipped")
        buf = io.StringIO()
        with inproc(self), \
                mock.patch.object(devteam.hybrid_shared, "breaker_summary", return_value=[line]) as summary, \
                mock.patch("sys.stdout", buf):
            rc = devteam.main(["next", "--no-review"])
        self.assertEqual(rc, 0)
        summary.assert_called_once_with(self.state_dir, "hybrid-team")
        self.assertIn("DAG EXHAUSTED", buf.getvalue())
        self.assertIn(line, buf.getvalue())

    def test_slice_sent_to_claude_by_an_open_breaker_is_counted(self):
        self.init(plan_of(docs_slice("D1")))
        spec = "zai-coding-plan/glm-5.3-flash#low"
        self.assertTrue(devteam.hybrid_shared.breaker_trip(self.state_dir, "lite", spec, "auth", "invalid api key"))
        r = self.engine("dispatch", "D1")
        self.assertIn("=== DISPATCH D1", r.stdout)
        self.assertNotIn("=== LANE", r.stdout)
        lines = devteam.hybrid_shared.breaker_summary(self.state_dir, "hybrid-team")
        self.assertEqual(len(lines), 1)
        self.assertIn("kind=breaker", lines[0])
        self.assertIn("1 units skipped", lines[0])


class OpencodeHoldTest(FlowBase):
    def test_unusable_opencode_holds_the_slice_instead_of_falling_back(self):
        self.env["HYBRID_TEAM_OC_BIN"] = str(self.tmp / "no-such-opencode")
        self.init(plan_of(docs_slice("D1")), "--route", "opencode")
        r = self.engine("dispatch", "D1")
        self.assertIn("OC-ERROR hybrid-team D1", r.stdout)
        self.assertIn("HELD D1", r.stdout)
        self.assertNotIn("=== LANE", r.stdout)
        self.assertNotIn("=== DISPATCH D1", r.stdout)
        self.assertEqual(self.st()["slices"]["D1"]["status"], "failed")
        self.assertNotIn("OC-ERROR hybrid-team D1", self.engine("next", "--no-review").stdout)

    def test_blocked_lane_is_held_then_retried_on_the_main_backend(self):
        self.init(plan_of(docs_slice("D1")), "--route", "opencode")
        self.assertIn("=== LANE D1 oc:lite", self.engine("dispatch", "D1").stdout)
        self.script.write_text(json.dumps(BLOCKED_STEP))
        self.engine("lane", "D1", check=False)
        r = self.engine("next", "--no-review")
        self.assertTrue(r.stdout.startswith("OC-WARN hybrid-team D1 tier=lite"), r.stdout)
        self.assertIn("HELD D1 (gate)", r.stdout)
        self.assertNotIn("ESCALATE", r.stdout)
        self.assertNotIn("=== DISPATCH D1", r.stdout)
        self.assertEqual(self.st()["slices"]["D1"]["status"], "failed")
        self.engine("retry", "D1", "--claude")
        self.assertIn("=== DISPATCH D1 [DOCS/WORK]", self.engine("dispatch", "D1").stdout)

    def test_open_breaker_holds_and_counts_the_slice(self):
        self.init(plan_of(docs_slice("D1")), "--route", "opencode")
        spec = "zai-coding-plan/glm-5.3-flash#low"
        self.assertTrue(devteam.hybrid_shared.breaker_trip(self.state_dir, "lite", spec, "auth", "invalid api key"))
        r = self.engine("dispatch", "D1")
        self.assertIn("HELD D1", r.stdout)
        self.assertNotIn("=== DISPATCH D1", r.stdout)
        lines = devteam.hybrid_shared.breaker_summary(self.state_dir, "hybrid-team")
        self.assertEqual(len(lines), 1)
        self.assertIn("1 units skipped", lines[0])


class RunResetAndRetryHealthTest(FlowBase):
    def write_oc_status(self, lite_ok):
        entries = {name: {"ok": True if name == "std" else lite_ok, "key": devteam.hybrid_shared.cache_key(tier),
                          "checked_at": time.time(), "kind": "", "detail": ""}
                   for name, tier in devteam.hybrid_shared.load_shared(MODELS_ENV)[0].items()}
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "oc_status.json").write_text(json.dumps({"available": True, "issues": [], "tiers": entries}))

    def test_init_force_resets_a_tripped_breaker(self):
        self.init(plan_of(docs_slice("D1")))
        spec = "zai-coding-plan/glm-5.3-flash#low"
        self.assertTrue(devteam.hybrid_shared.breaker_trip(self.state_dir, "lite", spec, "auth", "invalid api key"))
        self.init(plan_of(docs_slice("D1")), "--force")
        self.assertIn("=== LANE D1 oc:lite", self.engine("dispatch", "D1").stdout)
        self.assertEqual(devteam.hybrid_shared.breaker_summary(self.state_dir, "hybrid-team"), [])

    def test_retry_rereads_doctor_tier_health_in_preset_opencode(self):
        self.write_oc_status(False)
        self.init(plan_of(docs_slice("D1")), "--route", "opencode")
        self.assertIn("HELD D1", self.engine("dispatch", "D1").stdout)
        self.write_oc_status(True)
        self.engine("retry", "D1")
        r = self.engine("dispatch", "D1")
        self.assertIn("=== LANE D1 oc:lite", r.stdout)
        self.assertNotIn("HELD D1", r.stdout)

    def test_retry_of_other_slice_keeps_tier_when_doctor_cache_went_stale(self):
        self.write_oc_status(True)
        self.init(plan_of(docs_slice("D1"), docs_slice("D2")))
        self.engine("fail", "D2", "--why", "boom")
        path = self.state_dir / "oc_status.json"
        status = json.loads(path.read_text())
        for entry in status["tiers"].values():
            entry["checked_at"] = time.time() - devteam.hybrid_shared.DOCTOR_TTL_S - 60
        path.write_text(json.dumps(status))
        self.engine("retry", "D2")
        r = self.engine("dispatch", "D1")
        self.assertIn("=== LANE D1 oc:lite", r.stdout)
        self.assertNotIn("=== DISPATCH D1", r.stdout)

    def test_retry_claude_still_dispatches_to_claude(self):
        self.write_oc_status(False)
        self.init(plan_of(docs_slice("D1")), "--route", "opencode")
        self.assertIn("HELD D1", self.engine("dispatch", "D1").stdout)
        self.write_oc_status(True)
        self.engine("retry", "D1", "--claude")
        r = self.engine("dispatch", "D1")
        self.assertIn("=== DISPATCH D1", r.stdout)
        self.assertNotIn("=== LANE", r.stdout)


if __name__ == "__main__":
    unittest.main()
