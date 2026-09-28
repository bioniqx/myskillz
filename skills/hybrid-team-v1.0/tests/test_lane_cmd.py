"""End-to-end tests for `devteam.py lane <id>`, driven through the fake opencode CLI."""
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

TESTS_DIR = Path(__file__).resolve().parent
ENGINE = TESTS_DIR.parent / "scripts" / "devteam.py"
FAKE = TESTS_DIR / "fake_opencode.py"
STATE = ".claude/hybrid-team"
USAGE = {"input": 100, "output": 20, "reasoning": 5, "cache_read": 7, "cache_write": 3, "cost": 0.25}

DONE_TEXT = ("## Slice: S1\n## Status: Done\n## Gate:\n$ test -f docs/guide.md\n"
             "exit 0 - docs/guide.md is present\n## Notes:\nwrote the guide\n")
DONE_STEP = {"write": {"docs/guide.md": "# Guide\n"}, "commit": "docs(S1): add the guide",
             "usage": USAGE, "text": DONE_TEXT}
LAZY_STEP = {"text": "## Slice: S1\n## Status: Done\n## Notes:\nall good\n"}

PLAN = {
    "request": "lane test",
    "commands": {"test": "none"},
    "slices": [{
        "id": "S1", "title": "guide", "goal": "write the user guide", "kind": "docs",
        "size": "small", "deps": [], "files": ["docs/guide.md"],
        "criteria": ["docs/guide.md exists"], "verify": "test -f docs/guide.md",
    }],
}


def git(args, cwd):
    r = subprocess.run(["git"] + list(args), cwd=str(cwd), text=True, capture_output=True, check=True)
    return r.stdout.strip()


class LaneTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.script = self.tmp / "fake_script.json"
        self.log = self.tmp / "fake_log.jsonl"
        self.routing = self.tmp / "routing.json"
        self.env = dict(os.environ, HOME=str(self.home), HT_OC_BIN=str(FAKE),
                        HT_FAKE_SCRIPT=str(self.script), HT_FAKE_LOG=str(self.log),
                        HT_ROUTING=str(self.routing), PYTHONDONTWRITEBYTECODE="1")
        git(["init", "-q"], self.repo)
        git(["config", "user.email", "t@example.invalid"], self.repo)
        git(["config", "user.name", "t"], self.repo)
        git(["config", "commit.gpgsign", "false"], self.repo)
        (self.repo / "README.md").write_text("demo\n")
        git(["add", "README.md"], self.repo)
        git(["commit", "-qm", "init"], self.repo)
        plan = self.tmp / "plan.json"
        plan.write_text(json.dumps(PLAN))
        self.engine("init", str(plan))
        self.engine("dispatch", "S1")
        self.state = self.repo / STATE
        self.wt = self.repo / ".claude" / "worktrees" / "oc-S1"

    def engine(self, *args, check=True):
        r = subprocess.run([sys.executable, str(ENGINE)] + list(args), cwd=str(self.repo), env=self.env,
                           text=True, capture_output=True, timeout=120)
        if check:
            self.assertEqual(r.returncode, 0, msg="%s\n%s" % (r.stdout, r.stderr))
        return r

    def set_script(self, step):
        self.script.write_text(json.dumps(step))

    def marker(self, kind):
        return json.loads((self.state / "slices" / ("S1." + kind)).read_text())

    def records(self):
        path = self.state / "lanes.jsonl"
        return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(ln) for ln in self.log.read_text().splitlines() if ln.strip()]

    def assert_blocked(self, reason):
        self.assertFalse((self.state / "slices" / "S1.done").exists())
        m = self.marker("blocked")
        for key in ("t", "worktree", "branch", "note"):
            self.assertIn(key, m)
        self.assertEqual(m["reason"], reason)
        self.assertEqual(m["backend"], "oc:lite")
        rec = self.records()[-1]
        self.assertEqual(rec["outcome"], "blocked")
        self.assertEqual(rec["reason"], reason)
        self.assertFalse(rec["escalated"])
        return m


class LaneRunTest(LaneTestBase):
    def test_done_lane_runs_in_oc_worktree(self):
        self.set_script(DONE_STEP)
        r = self.engine("lane", "S1")
        self.assertIn("LANE S1 DONE", r.stdout)
        self.assertEqual(self.marker("done")["backend"], "oc:lite")
        self.assertFalse((self.state / "slices" / "S1.blocked").exists())
        self.assertEqual(git(["rev-parse", "--abbrev-ref", "HEAD"], self.wt), "oc-S1")
        self.assertTrue((self.wt / "docs" / "guide.md").exists())
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["pwd"], str(self.wt))
        self.assertEqual(Path(calls[0]["cwd"]).resolve(), self.wt)
        argv = calls[0]["argv"]
        self.assertEqual(argv[:5], ["run", "--standalone", "--agent", "ht-programmer", "--model"])
        self.assertEqual(argv[argv.index("--model") + 1], "zai-coding-plan/glm-5.3-flash#low")
        self.assertIn("--auto", argv)
        self.assertNotIn("-s", argv)
        self.assertIn("write the user guide", argv[-1])
        self.assertIn("ht-programmer", calls[0]["config"])
        self.assertTrue((self.state / "lanes" / "S1.jsonl").exists())
        self.assertFalse((self.state / "lanes" / "S1.pid").exists())
        rec = self.records()[-1]
        self.assertEqual(rec["id"], "S1")
        self.assertEqual(rec["backend"], "oc:lite")
        self.assertEqual(rec["tier"], "lite")
        self.assertEqual(rec["model"], "zai-coding-plan/glm-5.3-flash")
        self.assertEqual(rec["variant"], "low")
        self.assertEqual(rec["mode"], "work")
        self.assertEqual(rec["outcome"], "done")
        self.assertEqual(rec["reason"], "")
        self.assertFalse(rec["escalated"])
        self.assertEqual(rec["runs"], 1)
        self.assertIsInstance(rec["duration_s"], float)
        self.assertEqual(rec["tokens"], {"input": 100, "output": 20, "reasoning": 5,
                                         "cache_read": 7, "cache_write": 3})
        self.assertAlmostEqual(rec["cost"], 0.25)

    def test_agent_reported_blocked_is_gate(self):
        self.set_script({"text": "## Slice: S1\n## Status: Blocked\n## Notes:\nthe verify command needs network access\n"})
        r = self.engine("lane", "S1")
        self.assertIn("ESCALATE S1", r.stdout)
        m = self.assert_blocked("gate")
        self.assertIn("network access", m["note"])

    def test_error_event_is_crash(self):
        self.set_script({"error": {"type": "ProviderAuthError", "message": "invalid api key"}})
        r = self.engine("lane", "S1")
        self.assertIn("ESCALATE S1", r.stdout)
        m = self.assert_blocked("crash")
        self.assertIn("ProviderAuthError", m["note"])

    def test_missing_binary_is_spawn(self):
        self.env["HT_OC_BIN"] = str(self.tmp / "no-such-opencode")
        self.set_script(DONE_STEP)
        r = self.engine("lane", "S1")
        self.assertIn("ESCALATE S1", r.stdout)
        self.assert_blocked("spawn")
        self.assertEqual(self.records()[-1]["runs"], 1)

    def test_silent_process_is_stall(self):
        self.routing.write_text(json.dumps({"tiers": {"lite": {"stall_s": 1}}}))
        self.set_script({"sleep": 8, "text": DONE_TEXT})
        r = self.engine("lane", "S1")
        self.assertIn("ESCALATE S1", r.stdout)
        self.assert_blocked("stall")

    def test_stale_lane_process_is_killed(self):
        self.set_script(DONE_STEP)
        proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
        self.addCleanup(self._reap, proc)
        args = subprocess.run(["ps", "-ww", "-o", "args=", "-p", str(proc.pid)],
                              text=True, capture_output=True).stdout.strip()
        (self.state / "lanes").mkdir(parents=True, exist_ok=True)
        (self.state / "lanes" / "S1.pid").write_text(json.dumps({"pid": proc.pid, "args": args}))
        r = self.engine("lane", "S1")
        self.assertIn("killed stale lane process group %d" % proc.pid, r.stdout)
        self.assertEqual(proc.wait(timeout=10), -signal.SIGKILL)
        self.assertEqual(self.marker("done")["backend"], "oc:lite")

    @staticmethod
    def _reap(proc):
        if proc.poll() is None:
            proc.kill()
            proc.wait()


class LaneContinuationTest(LaneTestBase):
    def test_gate_block_continues_same_session(self):
        self.set_script([LAZY_STEP, DONE_STEP])
        r = self.engine("lane", "S1")
        calls = self.calls()
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["argv"][-3:-1], ["-s", "ses_fake0001"])
        self.assertIn("nothing committed yet", calls[1]["argv"][-1])
        self.assertIn("LANE S1 DONE", r.stdout)
        self.assertEqual(self.marker("done")["backend"], "oc:lite")
        rec = self.records()[-1]
        self.assertEqual(rec["outcome"], "done")
        self.assertEqual(rec["runs"], 2)
        self.assertEqual(rec["tokens"]["input"], 100)

    def test_gate_gives_up_after_max_continuations(self):
        self.set_script(LAZY_STEP)
        r = self.engine("lane", "S1")
        self.assertEqual(len(self.calls()), 3)
        self.assertIn("ESCALATE S1", r.stdout)
        m = self.assert_blocked("gate")
        self.assertIn("nothing committed yet", m["note"])
        self.assertEqual(self.records()[-1]["runs"], 3)


if __name__ == "__main__":
    unittest.main()
