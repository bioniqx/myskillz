"""glm-dev-team on OpenCode: `devteam.py resume <slice id> [--note TEXT]` relaunches a fresh lane in the
slice's existing worktree, and the checkpoint runs detached so `wait`/`next` collect it."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "glm-dev-team" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import devteam  # noqa: E402

PLAN = {
    "request": "resume fixture",
    "commands": {"test": "echo checkpoint-ran"},
    "slices": [{"id": "S1", "title": "one", "files": ["src/a.py", "tests/test_a.py"],
                "criteria": ["c1"]}],
}


class RunFixture(unittest.TestCase):
    """A real git repo with an initialised glm-dev-team run, driven in-process through devteam.main."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.repo = base / "repo"
        self.repo.mkdir()
        tx = base / "tx"
        tx.mkdir()
        self.env = mock.patch.dict(os.environ, {"DEVTEAM_TRANSCRIPTS_DIR": str(tx),
                                                "DEVTEAM_PROVIDER": "glm",
                                                "DEVTEAM_GOVERNOR": "off",
                                                # pin the harness: ambient ZCODE_* vars would flip
                                                # is_zcode() and resume would unpack a zcode line
                                                "DEVTEAM_HARNESS": "claude"})
        self.env.start()
        self.cwd = os.getcwd()
        os.chdir(self.repo)
        self.git("init", "-q", "-b", "main")
        self.git("commit", "-q", "--allow-empty", "-m", "init")
        plan = base / "plan.json"
        plan.write_text(json.dumps(PLAN))
        rc, text = self.run_cli("init", str(plan))
        self.assertEqual(rc, 0, text)
        self.root = devteam.find_root()

    def tearDown(self):
        os.chdir(self.cwd)
        self.env.stop()
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                        "-c", "commit.gpgsign=false"] + list(args),
                       cwd=str(self.repo), check=True, capture_output=True)

    def run_cli(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = devteam.main(list(args))
        return rc, buf.getvalue()

    def dispatch_with_worktree(self):
        st = devteam.load_state(self.root)
        devteam.do_dispatch(self.root, st, ["S1"])
        st = devteam.load_state(self.root)
        wt = devteam.lane_worktree(self.root, st, "S1")
        (wt / ".slice").mkdir(exist_ok=True)
        (wt / ".slice" / "stop_blocks").write_text("2")
        return wt


class ResumeTest(RunFixture):
    def test_resume_relaunches_lane_in_existing_worktree(self):
        wt = self.dispatch_with_worktree()
        devteam.slice_blocked_marker(self.root, wt, "S1", "which contract?")
        devteam.write_atomic(devteam.marker_file(self.root, "S1", "done"), "{}")
        with mock.patch.object(devteam, "is_opencode", return_value=True), \
                mock.patch.object(devteam, "launch_lane", return_value=4242) as launch:
            rc, text = self.run_cli("resume", "S1", "--note", "use contract C1")
        self.assertEqual(rc, 0, text)
        launch.assert_called_once()
        args, kwargs = launch.call_args
        self.assertEqual(args[2], "S1")
        self.assertEqual(args[3], "glm-programmer")
        self.assertIn("claim S1", args[5])
        self.assertEqual(kwargs.get("note"), "use contract C1")
        self.assertFalse((wt / ".slice" / "stop_blocks").exists())
        self.assertIsNone(devteam.read_marker(self.root, "S1", "done"))
        self.assertIsNone(devteam.read_marker(self.root, "S1", "blocked"))
        self.assertIn("RESUMED S1", text)
        self.assertIn("pid 4242", text)
        self.assertRegex(text, r"(?m)^NEXT: python3 .* wait$")
        s = devteam.load_state(self.root)["slices"]["S1"]
        self.assertEqual(s["status"], "inflight")
        self.assertIsNone(s["rejected"])
        self.assertEqual(s["history"][-1]["event"], "resume")
        self.assertEqual(s["history"][-1]["note"], "use contract C1")

    def test_resume_refused_off_opencode(self):
        self.dispatch_with_worktree()
        with mock.patch.object(devteam, "is_opencode", return_value=False), \
                mock.patch.object(devteam, "launch_lane") as launch:
            rc, text = self.run_cli("resume", "S1", "--note", "x")
        self.assertEqual(rc, 1)
        self.assertIn("SendMessage", text)
        launch.assert_not_called()

    def test_resume_needs_the_existing_worktree(self):
        st = devteam.load_state(self.root)
        devteam.do_dispatch(self.root, st, ["S1"])
        with mock.patch.object(devteam, "is_opencode", return_value=True), \
                mock.patch.object(devteam, "launch_lane") as launch:
            rc, text = self.run_cli("resume", "S1")
        self.assertEqual(rc, 1)
        self.assertIn("retry S1", text)
        launch.assert_not_called()

    def test_resume_refuses_a_slice_that_is_not_in_flight(self):
        with mock.patch.object(devteam, "is_opencode", return_value=True), \
                mock.patch.object(devteam, "launch_lane") as launch:
            rc, text = self.run_cli("resume", "S1")
        self.assertEqual(rc, 1)
        self.assertIn("pending", text)
        launch.assert_not_called()


class IntegrateMessageTest(RunFixture):
    """An integrate rejection on OpenCode points at `resume`, never at SendMessage."""

    def reject_without_red(self, opencode):
        wt = self.dispatch_with_worktree()
        os.chdir(wt)
        try:
            rc, text = self.run_cli("claim", "S1")
        finally:
            os.chdir(self.repo)
        self.assertEqual(rc, 0, text)
        st = devteam.load_state(self.root)
        with mock.patch.object(devteam, "is_opencode", return_value=opencode):
            return devteam.do_integrate(self.root, st, ["S1"], remove=False)[0]

    def test_opencode_rejection_points_to_resume(self):
        r = self.reject_without_red(True)
        self.assertIn("REJECTED — no RED commit", r)
        self.assertIn("add failing tests first", r)
        self.assertIn("resume S1 --note", r)
        self.assertNotIn("SendMessage", r)

    def test_claude_rejection_is_unchanged(self):
        r = self.reject_without_red(False)
        self.assertIn("SendMessage the agent to add failing tests first", r)
        self.assertNotIn("resume S1", r)

    def test_opencode_research_rejection_points_to_retry(self):
        st = {"script": "/x/devteam.py"}
        msg = ("S2: NOT INTEGRATED — no report at /r/S2.md. SendMessage the glm-investigator to write it "
               "(read-only slice: the report IS the deliverable), then integrate again.")
        r = devteam.opencode_message(st, "S2", msg)
        self.assertIn("no report at /r/S2.md", r)
        self.assertIn("retry S2", r)
        self.assertNotIn("SendMessage", r)
        self.assertNotIn("resume S2", r)


class ResumeHelpersTest(unittest.TestCase):
    def test_resume_brief_appends_note(self):
        out = devteam.resume_brief("CLAIMED S1\n# Briefing\n", "  use contract C1  ")
        self.assertTrue(out.startswith("CLAIMED S1\n# Briefing"))
        self.assertIn("## Resume note from the Conductor", out)
        self.assertTrue(out.rstrip().endswith("use contract C1"))

    def test_resume_brief_without_note_is_unchanged(self):
        self.assertEqual(devteam.resume_brief("brief\n", ""), "brief\n")
        self.assertEqual(devteam.resume_brief("brief\n", "   "), "brief\n")

    def test_launch_lane_records_note_in_spec(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(devteam.subprocess, "Popen") as popen:
            popen.return_value.pid = os.getpid()
            devteam.launch_lane(Path(td), {"provider": "glm"}, "S9", "glm-programmer", "",
                                "python3 x claim S9", note="fix the footprint")
            spec = json.loads((devteam.lanes_dir(td) / "S9.lane.json").read_text())
        self.assertEqual(spec["note"], "fix the footprint")

    def test_launch_lane_note_defaults_to_empty(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(devteam.subprocess, "Popen") as popen:
            popen.return_value.pid = os.getpid()
            devteam.launch_lane(Path(td), {"provider": "glm"}, "S8", "glm-programmer", "",
                                "python3 x claim S8")
            spec = json.loads((devteam.lanes_dir(td) / "S8.lane.json").read_text())
        self.assertEqual(spec["note"], "")

    def test_resume_hint_names_the_command(self):
        hint = devteam.resume_hint({"script": "/x/devteam.py"}, "S1")
        self.assertIn("python3 /x/devteam.py resume S1 --note", hint)
        self.assertIn("same worktree", hint)

    def test_resume_hint_never_names_sendmessage(self):
        hint = devteam.resume_hint({"script": "/x/devteam.py"}, "S1")
        self.assertIn("resume S1 --note", hint)
        self.assertIn("the S1 lane has exited", hint)
        self.assertNotIn("SendMessage", hint)


class CheckpointTest(RunFixture):
    def test_opencode_checkpoint_runs_detached_and_is_collected(self):
        with mock.patch.object(devteam, "is_opencode", return_value=True):
            rc, text = self.run_cli("checkpoint")
            self.assertEqual(rc, 0, text)
            self.assertIn("running detached", text)
            self.assertNotIn("run_in_background", text)
            self.assertRegex(text, r"(?m)^NEXT: python3 .* wait$")
            st = devteam.load_state(self.root)
            self.assertIsInstance(st["checkpoint_pending"].get("pid"), int)
            done = devteam.lanes_dir(self.root) / "checkpoint-1.done"
            deadline = time.monotonic() + 15
            while not done.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertTrue(done.exists(), "detached checkpoint never wrote its .done")
            self.assertTrue(devteam.checkpoint_finished(self.root, st))
            self.assertFalse(devteam.checkpoint_running(self.root, st))
            rc, text = self.run_cli("wait", "--timeout", "3")
            self.assertIn("WAIT: a lane finished", text)
            lines = devteam.harvest_checkpoint(self.root, st)
        self.assertIn("PASS (exit 0)", lines[0])
        self.assertFalse(done.exists())
        self.assertFalse((devteam.lanes_dir(self.root) / "checkpoint-1.pid").exists())
        log = devteam.state_dir(self.root) / "logs" / "checkpoint-1.log"
        self.assertIn("checkpoint-ran", log.read_text())

    def test_claude_checkpoint_still_prints_background_command(self):
        with mock.patch.object(devteam, "is_opencode", return_value=False):
            rc, text = self.run_cli("checkpoint")
        self.assertEqual(rc, 0, text)
        self.assertIn("run_in_background: true", text)
        self.assertFalse((devteam.lanes_dir(self.root) / "checkpoint-1.done").exists())
        st = devteam.load_state(self.root)
        self.assertTrue(devteam.checkpoint_running(self.root, st))


class KilledCheckpointTest(RunFixture):
    """A detached checkpoint killed by a signal never appends EXIT=; its dead pid must end the wait."""

    def pending(self, pid):
        st = devteam.load_state(self.root)
        st["checkpoint_pending"] = {"n": 1, "sha": "a" * 40, "wt": "", "merges_at": 0,
                                    "t": devteam.now(), "pid": pid}
        log = devteam.state_dir(self.root) / "logs" / "checkpoint-1.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("running tests...\n")
        d = devteam.lanes_dir(self.root)
        d.mkdir(parents=True, exist_ok=True)
        for ext in (".pid", ".done", ".end"):
            (d / f"checkpoint-1{ext}").write_text(str(pid))
        return st

    def dead_pid(self):
        p = subprocess.Popen(["true"])
        p.wait()
        return p.pid

    def test_dead_pid_without_exit_is_not_running(self):
        st = self.pending(self.dead_pid())
        self.assertFalse(devteam.checkpoint_running(self.root, st))

    def test_dead_pid_without_exit_is_harvested_as_fail(self):
        st = self.pending(self.dead_pid())
        lines = devteam.harvest_checkpoint(self.root, st)
        self.assertTrue(lines)
        self.assertIn("CHECKPOINT 1", lines[0])
        self.assertIn("FAIL", lines[0])
        self.assertIs(st["checkpoint_pending"], False)
        self.assertEqual(st["checkpoints"][-1]["result"], "fail")
        self.assertIn("signal", st["checkpoints"][-1]["note"])
        d = devteam.lanes_dir(self.root)
        for ext in (".pid", ".done", ".end"):
            self.assertFalse((d / f"checkpoint-1{ext}").exists(), ext)

    def test_live_pid_without_exit_stays_running(self):
        st = self.pending(os.getpid())
        self.assertTrue(devteam.checkpoint_running(self.root, st))
        self.assertEqual(devteam.harvest_checkpoint(self.root, st), [])
        self.assertIsInstance(st["checkpoint_pending"], dict)
        self.assertEqual(st["checkpoints"], [])


if __name__ == "__main__":
    unittest.main()
