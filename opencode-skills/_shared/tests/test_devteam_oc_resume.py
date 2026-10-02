"""dev-team `resume` prints the dispatch row again for the slice's existing worktree, integrate rejections
point at `resume`/`retry`, and the checkpoint runs detached with its results under <state>/logs."""
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

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "oc-dev-team" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import oc_devteam as devteam  # noqa: E402
import oc_harness  # noqa: E402

PLAN = {
    "request": "resume fixture",
    "commands": {"test": "echo checkpoint-ran"},
    "slices": [{"id": "S1", "title": "one", "files": ["src/a.py", "tests/test_a.py"],
                "criteria": ["c1"]}],
}


class RunFixture(unittest.TestCase):
    """A real git repo with an initialised dev-team run, driven in-process through devteam.main."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.repo = base / "repo"
        self.repo.mkdir()
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
        (wt / ".oc-slice").mkdir(exist_ok=True)
        (wt / ".oc-slice" / "stop_blocks").write_text("2")
        return wt


class ResumeTest(RunFixture):
    def test_resume_prints_the_row_again_with_the_note(self):
        wt = self.dispatch_with_worktree()
        devteam.write_atomic(devteam.marker_file(self.root, "S1", "blocked"), '{"note": "which contract?"}')
        devteam.write_atomic(devteam.marker_file(self.root, "S1", "done"), "{}")
        rc, text = self.run_cli("resume", "S1", "--note", "use contract C1")
        self.assertEqual(rc, 0, text)
        prompt = devteam.state_dir(self.root) / "prompts" / "S1.md"
        self.assertIn(oc_harness.dispatch_line("oc-programmer", str(prompt), "S1", 2), text)
        body = prompt.read_text()
        self.assertIn(f"claim S1 --worktree {wt}", body)
        self.assertIn("## Resume note from the Conductor", body)
        self.assertTrue(body.rstrip().endswith("use contract C1"))
        self.assertFalse((wt / ".oc-slice" / "stop_blocks").exists())
        self.assertIsNone(devteam.read_marker(self.root, "S1", "done"))
        self.assertIsNone(devteam.read_marker(self.root, "S1", "blocked"))
        self.assertIn("RESUMED S1 → programmer", text)
        self.assertIn("NEXT: emit every dispatch row above", text)
        s = devteam.load_state(self.root)["slices"]["S1"]
        self.assertEqual(s["status"], "inflight")
        self.assertIsNone(s["rejected"])
        self.assertEqual(s["history"][-1]["event"], "resume")
        self.assertEqual(s["history"][-1]["note"], "use contract C1")

    def test_resume_needs_the_existing_worktree(self):
        st = devteam.load_state(self.root)
        devteam.do_dispatch(self.root, st, ["S1"])
        rc, text = self.run_cli("resume", "S1")
        self.assertEqual(rc, 1)
        self.assertIn("retry S1", text)

    def test_resume_refuses_a_slice_that_is_not_in_flight(self):
        rc, text = self.run_cli("resume", "S1")
        self.assertEqual(rc, 1)
        self.assertIn("pending", text)


class IntegrateMessageTest(RunFixture):
    """An integrate rejection names the `resume` / `retry` command."""

    def test_rejection_points_to_resume(self):
        wt = self.dispatch_with_worktree()
        rc, text = self.run_cli("claim", "S1", "--worktree", str(wt))
        self.assertEqual(rc, 0, text)
        st = devteam.load_state(self.root)
        r = devteam.do_integrate(self.root, st, ["S1"], remove=False)[0]
        self.assertIn("REJECTED — no RED commit", r)
        self.assertIn("add failing tests first", r)
        self.assertIn('`resume S1 --note "<what to fix>"` asking the lane to add failing tests first', r)
        self.assertIn("the S1 lane has exited", r)

    def test_research_rejection_points_to_retry(self):
        with tempfile.TemporaryDirectory() as td:
            st = {"script": "/x/oc_devteam.py",
                  "slices": {"S2": {"status": "inflight", "mode": "research", "history": []}}}
            r = devteam.integrate_one(Path(td), st, "S2")
        self.assertIn("NOT INTEGRATED — no report at", r)
        self.assertIn("`retry S2` so a fresh investigator can write it", r)
        self.assertNotIn("resume S2", r)


class PromptHelpersTest(unittest.TestCase):
    def test_resume_brief_appends_note(self):
        out = devteam.resume_brief("CLAIMED S1\n# Briefing\n", "  use contract C1  ")
        self.assertTrue(out.startswith("CLAIMED S1\n# Briefing"))
        self.assertIn("## Resume note from the Conductor", out)
        self.assertTrue(out.rstrip().endswith("use contract C1"))

    def test_resume_brief_without_note_is_unchanged(self):
        self.assertEqual(devteam.resume_brief("brief\n", ""), "brief\n")
        self.assertEqual(devteam.resume_brief("brief\n", "   "), "brief\n")

    def test_programmer_prompt_binds_the_worktree(self):
        text = devteam.programmer_prompt({"script": "/x/oc_devteam.py"}, "S1", Path("/w/S1"))
        self.assertIn("python3 /x/oc_devteam.py claim S1 --worktree /w/S1", text)
        self.assertIn("workdir=/w/S1", text)
        self.assertNotIn("Resume note", text)
        self.assertIn("## Resume note from the Conductor",
                      devteam.programmer_prompt({"script": "/x/oc_devteam.py"}, "S1", Path("/w/S1"), "fix it"))

    def test_resume_hint_names_the_command(self):
        hint = devteam.resume_hint({"script": "/x/oc_devteam.py"}, "S1")
        self.assertIn("python3 /x/oc_devteam.py resume S1 --note", hint)
        self.assertIn("same worktree", hint)
        self.assertIn("the S1 lane has exited", hint)


class CheckpointTest(RunFixture):
    def test_checkpoint_runs_detached_and_is_collected(self):
        rc, text = self.run_cli("checkpoint")
        self.assertEqual(rc, 0, text)
        self.assertIn("running detached", text)
        self.assertRegex(text, r"(?m)^NEXT: python3 .* wait$")
        st = devteam.load_state(self.root)
        self.assertIsInstance(st["checkpoint_pending"].get("pid"), int)
        wt = Path(st["checkpoint_pending"]["wt"])
        self.assertEqual(wt, devteam.state_dir(self.root) / "checkpoints" / "checkpoint-1")
        logs = devteam.state_dir(self.root) / "logs"
        done = logs / "checkpoint-1.done"
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
        self.assertFalse((logs / "checkpoint-1.pid").exists())
        self.assertFalse(wt.exists())
        self.assertIn("checkpoint-ran", (logs / "checkpoint-1.log").read_text())


class KilledCheckpointTest(RunFixture):
    """A detached checkpoint killed by a signal never appends EXIT=; its dead pid must end the wait."""

    def pending(self, pid):
        st = devteam.load_state(self.root)
        st["checkpoint_pending"] = {"n": 1, "sha": "a" * 40, "wt": "", "merges_at": 0,
                                    "t": devteam.now(), "pid": pid}
        logs = devteam.state_dir(self.root) / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "checkpoint-1.log").write_text("running tests...\n")
        for ext in (".pid", ".done"):
            (logs / f"checkpoint-1{ext}").write_text(str(pid))
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
        logs = devteam.state_dir(self.root) / "logs"
        for ext in (".pid", ".done"):
            self.assertFalse((logs / f"checkpoint-1{ext}").exists(), ext)

    def test_live_pid_without_exit_stays_running(self):
        st = self.pending(os.getpid())
        self.assertTrue(devteam.checkpoint_running(self.root, st))
        self.assertEqual(devteam.harvest_checkpoint(self.root, st), [])
        self.assertIsInstance(st["checkpoint_pending"], dict)
        self.assertEqual(st["checkpoints"], [])


if __name__ == "__main__":
    unittest.main()
