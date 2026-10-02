"""Black-box and direct-import tests for T05: shorter repeated engine output.

Covers: print_ready's WAITING line (a count unless the run is stalled), the endgame block
(printed once per exhaustion), the `~/` spelling of the engine path in launch lines, and the
trimmed programmer report format.

Fixtures are real git repos under the SYSTEM temp dir (never inside this repo).
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEVTEAM_PATH = str(Path(__file__).resolve().parents[1] / "claude-dev-team-v3.2" / "scripts" / "devteam.py")

spec = importlib.util.spec_from_file_location("devteam_under_test_t05", DEVTEAM_PATH)
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)


def run_dt(args, cwd):
    return subprocess.run([sys.executable, DEVTEAM_PATH] + args, cwd=str(cwd),
                          capture_output=True, text=True, timeout=60)


def new_repo():
    d = Path(os.path.realpath(tempfile.mkdtemp()))
    for cmd in (["git", "init", "-q", "-b", "main"], ["git", "config", "user.email", "t@t"],
                ["git", "config", "user.name", "t"], ["git", "config", "commit.gpgsign", "false"]):
        subprocess.run(cmd, cwd=d, check=True)
    return d


def slice_record(sid, files, status="pending", deps=None):
    return {"id": sid, "title": sid, "goal": "", "kind": "code", "size": "small", "verify": "",
            "model": "", "deps": list(deps or []), "files": list(files), "risk": "low",
            "criteria": ["works"], "edge_cases": [], "context": [], "isolation": None,
            "status": status, "mode": None, "attempt": 0, "base_sha": None, "red_sha": None,
            "worktree": None, "branch": None, "merged_sha": None, "history": []}


def printed(fn, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class WaitingListTests(unittest.TestCase):
    def test_count_only_while_something_is_ready(self):
        st = {"slices": {
            "S1": slice_record("S1", ["src/s1.js"]),
            "S2": slice_record("S2", ["src/s2.js"], deps=["S1"]),
            "S3": slice_record("S3", ["src/s3.js"], deps=["S1"]),
        }}
        text = printed(dt.print_ready, st)
        self.assertIn("READY: S1", text)
        self.assertIn("WAITING: 2 on deps/footprints", text)
        self.assertNotIn("S2", text)
        self.assertNotIn("S3", text)

    def test_ids_are_listed_when_the_run_is_stalled(self):
        st = {"slices": {
            "F1": slice_record("F1", ["src/f1.js"], status="failed"),
            "S2": slice_record("S2", ["src/s2.js"], deps=["F1"]),
        }}
        text = printed(dt.print_ready, st)
        self.assertIn("WAITING on deps/footprints: S2", text)
        self.assertIn("UNRESOLVED", text)


class LaunchPathTests(unittest.TestCase):
    HOME_SCRIPT = str(Path.home() / "tools" / "dt" / "devteam.py")

    def test_script_under_home_is_spelled_with_a_tilde(self):
        self.assertEqual(dt.short_script(self.HOME_SCRIPT), "~/tools/dt/devteam.py")

    def test_script_outside_home_stays_absolute_and_quoted(self):
        self.assertEqual(dt.short_script("/no-such-home-dir/a b/devteam.py"),
                         "'/no-such-home-dir/a b/devteam.py'")

    def test_launch_line_uses_the_short_path(self):
        st = {"script": self.HOME_SCRIPT, "root": os.path.realpath(tempfile.gettempdir())}
        text = printed(dt.print_dispatch, st, [("S1", slice_record("S1", ["src/s1.js"]), "slice")], [])
        self.assertIn('prompt: "python3 ~/tools/dt/devteam.py claim S1"', text)

    def test_permission_rules_cover_both_spellings(self):
        st = {"script": self.HOME_SCRIPT, "commands": {}, "slices": {}}
        rules = dt.allow_rules_for(st)
        self.assertIn(f"Bash(python3 {self.HOME_SCRIPT}:*)", rules)
        self.assertIn("Bash(python3 ~/tools/dt/devteam.py:*)", rules)
        self.assertIn("Bash(python3 ~/tools/dt/devteam.py *)", rules)


class ReportFormatTests(unittest.TestCase):
    def test_final_message_drops_the_per_file_and_per_criterion_detail(self):
        text = "\n".join(dt.report_block("S1", "title", "slice"))
        for keep in ("## Slice: S1", "## Status:", "## Worktree:", "## Gate:", "## Notes:"):
            self.assertIn(keep, text)
        for drop in ("## Changes", "## Criteria"):
            self.assertNotIn(drop, text)

    def test_research_report_format_is_unchanged(self):
        text = "\n".join(dt.report_block("R1", "title", "research"))
        self.assertIn("## Report: <absolute path of the report you wrote>", text)


class EndgameOnceTests(unittest.TestCase):
    def make_repo(self):
        repo = new_repo()
        (repo / "src").mkdir()
        (repo / "src" / ".keep").write_text("")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
        plan = {"request": "T05 fixtures", "profile": "balanced", "commands": {"test": "none", "test_file": "none"},
                "slices": [{"id": "S1", "title": "s1", "files": ["src/S1.js"], "risk": "low",
                            "criteria": ["works"]}]}
        (repo / "plan.md").write_text("# plan\n```json\n" + json.dumps(plan) + "\n```\n")
        r = run_dt(["init", "plan.md"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return repo

    def set_status(self, repo, status):
        p = repo / ".claude" / "dev-team" / "state.json"
        st = json.loads(p.read_text())
        st["slices"]["S1"]["status"] = status
        p.write_text(json.dumps(st))

    def next_out(self, repo):
        r = run_dt(["next"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def test_endgame_steps_print_once_and_again_after_a_requeue(self):
        repo = self.make_repo()
        self.set_status(repo, "done")
        first = self.next_out(repo)
        self.assertIn("endgame:", first)
        self.assertIn("queue empty, reviews APPROVED", first)
        second = self.next_out(repo)
        self.assertIn("DAG EXHAUSTED", second)
        self.assertIn("printed earlier", second)
        self.assertNotIn("queue empty, reviews APPROVED", second)
        self.set_status(repo, "pending")
        self.assertNotIn("DAG EXHAUSTED", self.next_out(repo))
        self.set_status(repo, "done")
        self.assertIn("queue empty, reviews APPROVED", self.next_out(repo))


if __name__ == "__main__":
    unittest.main()
