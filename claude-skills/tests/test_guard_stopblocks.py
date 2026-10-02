"""Black-box tests for claude-dev-team-v3.2/scripts/guard.py (T06): the Stop gate's block counter.

`stop_blocks` counts how often the Stop gate refused a slice. It must restart from zero whenever
the lane is finished (done marker, blocked marker, or the gate giving up), so a resumed slice is
gated afresh instead of finding the counter already at MAX_STOP_BLOCKS.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD_PY = Path(__file__).resolve().parents[1] / "claude-dev-team-v3.2" / "scripts" / "guard.py"
GATE_MSG = "## Status: Complete\n## Gate: ran the checks -> all output was clean and green\n"


def run_stop(wt, message):
    return subprocess.run([sys.executable, str(GUARD_PY), "stop"],
                          input=json.dumps({"cwd": str(wt), "last_assistant_message": message}),
                          cwd=str(wt), capture_output=True, text=True, timeout=10)


def git(args, cwd):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True).stdout.strip()


def make_chore_slice(base):
    """A work-mode slice with NOTHING committed since its base: the Stop gate blocks it."""
    wt = Path(base)
    wt.mkdir(parents=True)
    for args in (["init", "-q"], ["config", "user.email", "a@a.com"], ["config", "user.name", "a"],
                 ["config", "commit.gpgsign", "false"]):
        git(args, wt)
    (wt / "a.txt").write_text("a\n")
    git(["add", "-A"], wt)
    git(["commit", "-q", "-m", "chore: base"], wt)
    sd = wt / ".slice"
    sd.mkdir()
    (sd / "id").write_text("T06\n")
    (sd / "kind").write_text("chore\n")
    (sd / "mode").write_text("work\n")
    (sd / "base").write_text(git(["rev-parse", "HEAD"], wt) + "\n")
    return wt


class StopBlocksResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wt = make_chore_slice(Path(os.path.realpath(self.tmp.name)) / "wt")

    def test_gate_blocks_again_after_it_gave_up_once(self):
        for expected in (2, 2, 0):          # two blocks, then the give-up that lets the lane stop
            r = run_stop(self.wt, GATE_MSG)
            self.assertEqual(r.returncode, expected, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertFalse((self.wt / ".slice" / "stop_blocks").exists(),
                         "finishing the lane must clear the counter")
        r = run_stop(self.wt, GATE_MSG)     # the slice is resumed with the same problem
        self.assertEqual(r.returncode, 2, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("nothing committed", r.stderr)

    def test_blocked_report_clears_the_counter(self):
        (self.wt / ".slice" / "stop_blocks").write_text("1")
        r = run_stop(self.wt, "## Status: Blocked\n## Notes: need the contract\n")
        self.assertEqual(r.returncode, 0, msg=f"stderr={r.stderr!r}")
        self.assertFalse((self.wt / ".slice" / "stop_blocks").exists())

    def test_passing_gate_clears_the_counter(self):
        (self.wt / ".slice" / "stop_blocks").write_text("1")
        (self.wt / "b.txt").write_text("b\n")
        git(["add", "-A"], self.wt)
        git(["commit", "-q", "-m", "chore(T06): work"], self.wt)
        r = run_stop(self.wt, GATE_MSG)
        self.assertEqual(r.returncode, 0, msg=f"stderr={r.stderr!r}")
        self.assertFalse((self.wt / ".slice" / "stop_blocks").exists())


if __name__ == "__main__":
    unittest.main()
