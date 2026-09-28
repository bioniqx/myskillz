"""A second `lane <id>` is refused while a live lane engine owns the opencode child recorded in
`lanes/<id>.pid`; a child whose parent is not that engine is still killed as stale. Lane liveness
is an OS lock on `lanes/<id>.lock`, and retry/fail signal a child's parent only when it is that
lane's engine."""
import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock

import test_dispatch_flow
from test_dispatch_flow import (FlowBase, docs_slice, gone, plan_of, ps_args, reap, run_lane_inproc,  # noqa: F401
                                devteam)

PARENT_CODE = ("import subprocess,sys; p=subprocess.Popen(['sleep','60'], start_new_session=True); "
               "print(p.pid, flush=True); p.wait()")
# stays alive after its child is killed, so "parent left alone" is observable
SLEEPING_PARENT_CODE = ("import subprocess,sys,time; p=subprocess.Popen(['sleep','60'], start_new_session=True); "
                        "print(p.pid, flush=True); time.sleep(60)")
HOLDER_CODE = ("import fcntl,sys,time; f=open(sys.argv[1],'a'); fcntl.flock(f, fcntl.LOCK_EX); "
               "print('locked', flush=True); time.sleep(60)")


class LaneRefusalChildWindowTest(FlowBase):
    def setUp(self):
        super().setUp()
        self.init(plan_of(docs_slice("D1")))
        self.assertIn("=== LANE D1 oc:lite", self.engine("dispatch", "D1").stdout)
        self.lanes = self.state_dir / "lanes"
        self.lanes.mkdir(parents=True, exist_ok=True)
        self.pidf = self.lanes / "D1.pid"

    def spawn_parent(self, *tail, code=PARENT_CODE):
        """A parent process whose argv ends with `tail`, running one `sleep` child; returns the child pid."""
        parent = subprocess.Popen([sys.executable, "-c", code] + list(tail), stdout=subprocess.PIPE, text=True)
        child = int(parent.stdout.readline().strip())

        def cleanup():
            try:
                os.kill(child, 9)
            except OSError:
                pass
            reap(parent)
            parent.stdout.close()
        self.addCleanup(cleanup)
        return parent, child

    def test_second_lane_refused_while_child_parent_is_live_lane_engine(self):
        parent, child = self.spawn_parent("lane", "D1")
        args = ps_args(child)
        self.assertTrue(args)
        rec = json.dumps({"pid": child, "args": args})
        self.pidf.write_text(rec)
        with mock.patch("os.killpg") as kp, mock.patch("os.kill") as k:
            with self.assertRaises(devteam.DevteamError) as cm:
                run_lane_inproc(self)
        self.assertIn("lane already running", str(cm.exception))
        kp.assert_not_called()
        k.assert_not_called()
        self.assertEqual(self.pidf.read_text(), rec)
        self.assertFalse((self.state_dir / "slices" / "D1.done").exists())
        self.assertFalse((self.state_dir / "slices" / "D1.blocked").exists())
        self.assertFalse((self.repo / ".claude" / "worktrees" / "oc-D1").exists())
        self.assertIsNone(parent.poll())

    def test_child_whose_parent_is_not_this_lane_engine_is_killed_as_stale(self):
        parent, child = self.spawn_parent("lane", "D9")
        args = ps_args(child)
        self.assertTrue(args)
        self.pidf.write_text(json.dumps({"pid": child, "args": args}))
        with mock.patch("os.killpg") as kp:
            run_lane_inproc(self, lane_worktree=mock.Mock(side_effect=devteam.DevteamError("boom-for-test")))
        kp.assert_called_once_with(child, mock.ANY)
        self.assertFalse(self.pidf.exists())
        self.assertEqual(json.loads((self.state_dir / "slices" / "D1.blocked").read_text())["reason"], "spawn")

    # --- retry signals a child's parent only when it is this lane's engine

    def test_retry_on_child_of_verified_engine_terminates_parent_and_child(self):
        parent, child = self.spawn_parent("lane", "D1", code=SLEEPING_PARENT_CODE)
        self.pidf.write_text(json.dumps({"pid": child, "args": ps_args(child)}))
        self.assertIn("re-queued", self.engine("retry", "D1").stdout)
        parent.wait(timeout=15)
        self.assertIsNotNone(parent.poll())
        self.assertTrue(gone(child))
        self.assertFalse(self.pidf.exists())

    def test_retry_on_child_of_unrelated_parent_kills_child_only(self):
        parent, child = self.spawn_parent("lane", "D9", code=SLEEPING_PARENT_CODE)
        self.pidf.write_text(json.dumps({"pid": child, "args": ps_args(child)}))
        self.assertIn("re-queued", self.engine("retry", "D1").stdout)
        self.assertTrue(gone(child))
        self.assertIsNone(parent.poll())
        self.assertFalse(self.pidf.exists())

    # --- the lane lock: lanes/<id>.lock held by the running engine

    def hold_lock(self):
        """Another process holding an exclusive flock on lanes/D1.lock."""
        holder = subprocess.Popen([sys.executable, "-c", HOLDER_CODE, str(self.lanes / "D1.lock")],
                                  stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: (reap(holder), holder.stdout.close()))
        self.assertEqual(holder.stdout.readline().strip(), "locked")
        return holder

    def test_lane_is_live_while_another_process_holds_the_lock(self):
        self.hold_lock()
        self.assertFalse(self.pidf.exists())
        self.assertTrue(devteam.lane_is_live(self.repo, "D1"))

    def test_second_lane_refused_while_lock_held_touches_nothing(self):
        self.hold_lock()
        blocked = self.state_dir / "slices" / "D1.blocked"
        blocked.parent.mkdir(parents=True, exist_ok=True)
        blocked.write_text("sentinel")
        wt = mock.Mock(side_effect=devteam.DevteamError("boom-for-test"))
        with self.assertRaises(devteam.DevteamError) as cm:
            run_lane_inproc(self, lane_worktree=wt, out=mock.Mock(), LANE_LOCK_WAIT_S=0.2)
        self.assertIn("lane already running", str(cm.exception))
        wt.assert_not_called()
        self.assertEqual(blocked.read_text(), "sentinel")
        self.assertFalse((self.state_dir / "slices" / "D1.done").exists())
        self.assertFalse(self.pidf.exists())
        self.assertFalse((self.repo / ".claude" / "worktrees" / "oc-D1").exists())

    def test_lock_released_when_holder_is_sigkilled_and_new_lane_runs(self):
        holder = self.hold_lock()
        self.assertTrue(devteam.lane_is_live(self.repo, "D1"))
        os.kill(holder.pid, signal.SIGKILL)
        holder.wait(timeout=10)
        self.assertFalse(devteam.lane_is_live(self.repo, "D1"))
        seen = {}

        def fail_worktree(root, st, sid):
            seen["live"] = devteam.lane_is_live(self.repo, "D1")
            raise devteam.DevteamError("boom-for-test")

        run_lane_inproc(self, lane_worktree=mock.Mock(side_effect=fail_worktree), out=mock.Mock())
        self.assertIs(seen.get("live"), True)
        self.assertEqual(json.loads((self.state_dir / "slices" / "D1.blocked").read_text())["reason"], "spawn")
        self.assertFalse(devteam.lane_is_live(self.repo, "D1"))


class OrphanChildLivenessTest(FlowBase):
    """lanes/D1.lock exists but is free (the engine died): a still-running non-engine child record
    keeps the lane live; an engine record never does — the lock alone decides engine liveness."""

    def setUp(self):
        super().setUp()
        self.lanes = self.state_dir / "lanes"
        self.lanes.mkdir(parents=True, exist_ok=True)

    def free_lock_and_record(self, **extra):
        (self.lanes / "D1.lock").touch()
        proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.addCleanup(reap, proc)
        args = ps_args(proc.pid)
        self.assertTrue(args)
        rec = {"pid": proc.pid, "args": args}
        rec.update(extra)
        (self.lanes / "D1.pid").write_text(json.dumps(rec))

    def test_free_lock_live_orphan_child_record_is_live(self):
        self.free_lock_and_record()
        self.assertTrue(devteam.lane_is_live(self.repo, "D1"))

    def test_free_lock_live_engine_record_is_not_live(self):
        self.free_lock_and_record(engine=True)
        self.assertFalse(devteam.lane_is_live(self.repo, "D1"))

    def test_free_lock_no_record_is_not_live_and_held_lock_is_live(self):
        (self.lanes / "D1.lock").touch()
        self.assertFalse(devteam.lane_is_live(self.repo, "D1"))
        holder = subprocess.Popen([sys.executable, "-c", HOLDER_CODE, str(self.lanes / "D1.lock")],
                                  stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: (reap(holder), holder.stdout.close()))
        self.assertEqual(holder.stdout.readline().strip(), "locked")
        self.assertTrue(devteam.lane_is_live(self.repo, "D1"))

    def test_integrate_free_lock_live_orphan_reports_still_running(self):
        wt = test_dispatch_flow.LaneStillRunningTest._dispatch_and_claim(self, "D1")
        self.free_lock_and_record()
        r = self.engine("integrate", "D1")
        self.assertIn("lane still running", r.stdout)
        self.assertNotIn("ESCALATE", r.stdout)
        self.assertTrue(wt.exists())
        self.assertEqual(self.st()["backends"]["D1"], "oc:lite")


class SharedInprocHelperTest(FlowBase):
    def test_run_lane_inproc_defined_once_and_imported(self):
        self.assertIs(run_lane_inproc, test_dispatch_flow.run_lane_inproc)
        definition = "def " + "run_lane_inproc("
        self.assertNotIn(definition, Path(__file__).read_text())
        self.assertEqual(Path(test_dispatch_flow.__file__).read_text().count(definition), 1)
