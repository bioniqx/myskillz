"""dev-team subagent lanes, driven through the CLI in a real repository: dispatch rows, claim --worktree,
report, wait, retry, verify-brief, review-pr and brief-debug."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "oc-dev-team", "scripts")
sys.path.insert(0, SCRIPTS)

import oc_devteam as devteam  # noqa: E402
import oc_harness  # noqa: E402

DEVTEAM = os.path.join(SCRIPTS, "oc_devteam.py")
GATE_TEXT = "dev-team gate — you are not done yet"

PLAN = {"request": "r", "commands": {"test": "true"},
        "slices": [{"id": "S1", "title": "one", "deps": [], "files": ["src/a.py", "tests/test_a.py"],
                    "risk": "low", "criteria": ["works"]},
                   {"id": "R1", "title": "look", "kind": "research", "deps": [], "files": ["docs/r1.md"],
                    "criteria": ["answer"]}]}


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo, "src"))
        os.makedirs(os.path.join(self.tmp, "home"))
        self.env = dict(os.environ, HOME=os.path.join(self.tmp, "home"))
        for cmd in (["git", "init", "-q", "-b", "main"], ["git", "config", "user.email", "t@t"],
                    ["git", "config", "user.name", "t"], ["git", "config", "commit.gpgsign", "false"]):
            self.git(*cmd[1:])
        Path(self.repo, "src", "a.py").write_text("x = 1\n")
        Path(self.tmp, "plan.json").write_text(json.dumps(PLAN))
        self.git("add", "-A")
        self.git("commit", "-qm", "init")
        self.cli("init", os.path.join(self.tmp, "plan.json"))

    def git(self, *args, cwd=None):
        r = subprocess.run(["git"] + list(args), cwd=cwd or self.repo, text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout.strip()

    def cli(self, *args, cwd=None, code=0):
        r = subprocess.run([sys.executable, DEVTEAM] + list(args), cwd=cwd or self.repo, env=self.env,
                           text=True, capture_output=True)
        self.assertEqual(r.returncode, code, r.stdout + r.stderr)
        return r.stdout + r.stderr

    def state(self, *parts):
        return Path(self.repo, ".opencode", "oc-dev-team", *parts)

    def prompt(self, lane_id):
        return self.state("prompts", f"{lane_id}.md")

    def dispatch_and_claim(self):
        self.cli("dispatch", "S1")
        wt = self.state("wt", "S1")
        self.cli("claim", "S1", "--worktree", str(wt))
        return wt

    def report(self, wt, text, code):
        f = wt / ".oc-slice" / "report.md"
        f.write_text(text)
        return self.cli("report", "S1", "--file", str(f), cwd=str(wt), code=code)


class DispatchTest(RepoCase):
    def test_dispatch_creates_the_worktree_and_prints_the_row(self):
        out = self.cli("dispatch", "S1")
        wt = self.state("wt", "S1")
        self.assertIn(oc_harness.dispatch_line("oc-programmer", str(self.prompt("S1")), "S1", 2), out)
        self.assertIn("NEXT: emit every dispatch row above", out)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD", cwd=str(wt)), "oc-devteam/S1")
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=str(wt)), self.git("rev-parse", "HEAD"))
        text = self.prompt("S1").read_text()
        self.assertIn(f"claim S1 --worktree {wt}", text)
        self.assertIn(f"workdir={wt}", text)
        self.assertFalse(self.state("lanes").exists())

    def test_research_slice_gets_an_investigator_row_and_no_worktree(self):
        out = self.cli("dispatch", "R1")
        self.assertIn(oc_harness.dispatch_line("oc-investigator", str(self.prompt("R1")), "R1", 2), out)
        self.assertEqual(self.prompt("R1").read_text(),
                         f"Read {self.state('briefs', 'R1.md')} and follow it exactly.\n")
        self.assertFalse(self.state("wt", "R1").exists())

    def test_lane_worktree_without_base_sha_raises_devteam_error(self):
        root = Path(self.repo)
        st = devteam.load_state(root)   # S1 was `init`ed but never dispatched: base_sha is still None
        with self.assertRaisesRegex(devteam.DevteamError, "S1"):
            devteam.lane_worktree(root, st, "S1")

    def test_retry_prints_the_row_again_on_a_fresh_worktree(self):
        wt = self.dispatch_and_claim()
        out = self.cli("retry", "S1")
        self.assertIn("S1: re-queued as pending", out)
        self.assertIn(oc_harness.dispatch_line("oc-programmer", str(self.prompt("S1")), "S1", 2), out)
        self.assertTrue((wt / ".git").exists())
        self.assertFalse((wt / ".oc-slice").exists())
        self.assertEqual(self.git("branch", "--list", "attempt/S1-1"), "attempt/S1-1")

    def test_verify_brief_prints_a_team_leader_row(self):
        out = self.cli("verify-brief")
        self.assertIn(oc_harness.dispatch_line("oc-team-leader", str(self.prompt("verify-intent")),
                                               "verify intent", 2), out)
        self.assertIn(str(self.state("reviews", "verification.md")), self.prompt("verify-intent").read_text())

    def test_review_pr_prints_reviewer_rows(self):
        Path(self.repo, "src", "b.py").write_text("y = 2\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "second")
        out = self.cli("review-pr", "HEAD", "--shards", "1")
        prompts = sorted(self.state("prompts").glob("review-pr*.md"))
        self.assertEqual(len(prompts), 1, out)
        label = "review " + prompts[0].stem[len("review-"):]
        self.assertIn(oc_harness.dispatch_line("oc-code-reviewer", str(prompts[0]), label, 2), out)
        self.assertIn("NEXT: emit every dispatch row above", out)

    def test_brief_debug_prints_investigator_rows(self):
        out = self.cli("brief-debug", "it crashes", "-n", "2")
        for name in ("debug1", "debug2"):
            self.assertIn(oc_harness.dispatch_line("oc-investigator", str(self.prompt(name)), name, 2), out)
            self.assertIn(str(self.state("research", name + ".md")), self.prompt(name).read_text())


class ClaimTest(RepoCase):
    def test_claim_takes_the_worktree_from_the_argument(self):
        self.cli("dispatch", "S1")
        wt = self.state("wt", "S1")
        out = self.cli("claim", "S1", "--worktree", str(wt))
        self.assertIn(f"CLAIMED S1 — worktree {wt}", out)
        self.assertIn(f"pass workdir={wt} on EVERY shell call", out)
        self.assertIn(f"report S1 --file {wt}/.oc-slice/report.md", out)
        self.assertEqual(devteam.read_claim(Path(self.repo), "S1")["worktree"], str(wt))
        self.assertIn(" report", (wt / ".oc-slice" / "allow").read_text())

    def test_claim_in_the_integration_checkout_is_refused(self):
        self.cli("dispatch", "S1")
        self.assertIn("integration checkout", self.cli("claim", "S1", code=1))

    def test_claim_needs_an_existing_worktree(self):
        self.cli("dispatch", "S1")
        self.assertIn("is not a directory", self.cli("claim", "S1", "--worktree", "/no/such/wt", code=1))


class ReportTest(RepoCase):
    def test_blocked_report_writes_the_blocked_marker_and_next_shows_it(self):
        wt = self.dispatch_and_claim()
        out = self.report(wt, "## Slice: S1 — one\n## Status: Blocked\n## Notes: need the schema\n", 0)
        self.assertIn("REPORTED S1: blocked", out)
        self.assertIn("NEXT: end your turn", out)
        self.assertEqual(json.loads(self.state("slices", "S1.blocked").read_text())["note"], "need the schema")
        self.assertFalse(self.state("slices", "S1.done").exists())
        nxt = self.cli("next")
        self.assertIn("BLOCKED S1: need the schema", nxt)
        self.assertIn("resume S1 --note", nxt)

    def test_unfinished_report_is_refused_in_band_then_force_completed(self):
        wt = self.dispatch_and_claim()
        for _ in range(2):
            out = self.report(wt, "still working", 2)
            self.assertIn("REPORT S1: NOT ACCEPTED", out)
            self.assertIn(GATE_TEXT, out)
            self.assertFalse(self.state("slices", "S1.done").exists())
        self.assertIn("REPORTED S1: done", self.report(wt, "still working", 0))
        note = json.loads(self.state("slices", "S1.done").read_text())["note"]
        self.assertTrue(note.startswith("accepted after 2 blocked report(s)"), note)

    def test_complete_slice_is_accepted_and_merged_by_next(self):
        wt = self.dispatch_and_claim()
        (wt / "tests").mkdir()
        (wt / "tests" / "test_a.py").write_text("from src.a import x\n\n\ndef test_x():\n    assert x == 2\n")
        self.cli("commit-red", "one", cwd=str(wt))
        (wt / "src" / "a.py").write_text("x = 2\n")
        self.cli("commit-green", "one", cwd=str(wt))
        out = self.report(wt, "## Slice: S1 — one\n## Status: Complete\n## Commits: RED a | GREEN b\n"
                              "## Gate: pytest tests/test_a.py -> 1 passed\n## Notes: none\n", 0)
        self.assertIn("REPORTED S1: done", out)
        self.assertIn("S1: MERGED", self.cli("next"))
        self.assertEqual(Path(self.repo, "src", "a.py").read_text(), "x = 2\n")

    def test_report_needs_a_claimed_worktree(self):
        self.cli("dispatch", "S1")
        f = Path(self.tmp, "report.md")
        f.write_text("## Status: Blocked\n")
        self.assertIn("is not claimed for S1", self.cli("report", "S1", "--file", str(f), code=1))

    def test_report_needs_a_readable_file(self):
        self.dispatch_and_claim()
        self.assertIn("cannot read the report", self.cli("report", "S1", "--file", "/no/such.md", code=1))


class WaitTest(RepoCase):
    def test_times_out_naming_the_slice_without_a_result(self):
        self.cli("dispatch", "S1")
        start = time.monotonic()
        out = self.cli("wait", "--timeout", "1")
        self.assertGreaterEqual(time.monotonic() - start, 1)
        self.assertIn("WAIT: nothing finished in 1s", out)
        self.assertIn("RUNNING (no result yet): S1", out)
        self.assertIn("NEXT: python3 ", out)

    def test_returns_when_a_slice_marker_appears(self):
        self.cli("dispatch", "S1")
        timer = threading.Timer(0.5, self.state("slices", "S9.done").write_text, args=("{}",))
        timer.start()
        self.addCleanup(timer.cancel)
        start = time.monotonic()
        out = self.cli("wait", "--timeout", "30")
        self.assertLess(time.monotonic() - start, 10)
        self.assertIn("WAIT: a lane finished", out)

    def open_review(self):
        sp = self.state("state.json")
        st = json.loads(sp.read_text())
        st["reviews"] = {"r1": {"status": "dispatched", "shards": 1}}
        sp.write_text(json.dumps(st))

    def test_returns_at_once_when_nothing_is_running(self):
        start = time.monotonic()
        out = self.cli("wait", "--timeout", "30")
        self.assertLess(time.monotonic() - start, 3)
        self.assertIn("WAIT: nothing is running", out)
        self.assertIn("NEXT: python3 ", out)

    def test_exclude_lines_use_the_opencode_memory_dir(self):
        self.assertIn(".opencode/agent-memory-local/", devteam.EXCLUDE_LINES)

    def test_returns_when_a_review_report_lands(self):
        self.open_review()
        self.state("reviews").mkdir(parents=True, exist_ok=True)
        timer = threading.Timer(0.5, self.state("reviews", "r1.report.md").write_text, args=("## Review verdict: APPROVED\n",))
        timer.start()
        self.addCleanup(timer.cancel)
        start = time.monotonic()
        out = self.cli("wait", "--timeout", "30")
        self.assertLess(time.monotonic() - start, 10)
        self.assertIn("WAIT: a lane finished", out)

    def test_returns_at_once_when_a_result_is_already_there(self):
        wt = self.dispatch_and_claim()
        self.report(wt, "## Status: Blocked\n## Notes: q\n", 0)
        start = time.monotonic()
        self.assertIn("WAIT: a lane finished", self.cli("wait", "--timeout", "30"))
        self.assertLess(time.monotonic() - start, 10)


if __name__ == "__main__":
    unittest.main()
