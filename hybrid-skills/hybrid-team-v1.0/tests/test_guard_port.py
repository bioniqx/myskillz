"""Black-box tests for the guard.py parity port (T12): write_marker clears stop_blocks, and the
read-only role guard decides on the command position (ro_mutating_tool) plus the brew/apt/make deny."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD_PY = Path(__file__).resolve().parents[1] / "scripts" / "guard.py"


def run_guard(mode, payload, cwd):
    return subprocess.run(
        [sys.executable, str(GUARD_PY), mode],
        input=json.dumps(payload),
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=10,
    )


def decision_of(result):
    out = result.stdout.strip()
    if not out:
        return None
    data = json.loads(out)
    return (data.get("hookSpecificOutput") or {}).get("permissionDecision")


def make_slice_root(base, sid="T12"):
    root = Path(base)
    sd = root / ".slice"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "id").write_text(sid + "\n")
    (sd / "kind").write_text("code\n")
    (sd / "mode").write_text("slice\n")
    return root


class StopBlocksResetTest(unittest.TestCase):
    """write_marker must unlink .slice/stop_blocks so a resumed lane is gated afresh."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(os.path.realpath(self.tmp.name))

    def _lane(self, name, blocks):
        run_root = self.base / (name + "_root")
        run_root.mkdir()
        wt = make_slice_root(self.base / name)
        (wt / ".slice" / "root").write_text(str(run_root) + "\n")
        (wt / ".slice" / "stop_blocks").write_text(str(blocks))
        return wt, run_root

    def test_done_marker_clears_stop_blocks(self):
        wt, run_root = self._lane("wt_done", 2)
        r = run_guard("stop", {"cwd": str(wt), "last_assistant_message": "## Status: Complete\n"}, cwd=str(wt))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertTrue((run_root / ".claude" / "hybrid-team" / "slices" / "T12.done").exists())
        self.assertFalse((wt / ".slice" / "stop_blocks").exists())

    def test_blocked_marker_clears_stop_blocks(self):
        wt, run_root = self._lane("wt_blocked", 1)
        r = run_guard("stop", {"cwd": str(wt), "last_assistant_message": "## Status: Blocked\n## Notes: no spec\n"},
                      cwd=str(wt))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertTrue((run_root / ".claude" / "hybrid-team" / "slices" / "T12.blocked").exists())
        self.assertFalse((wt / ".slice" / "stop_blocks").exists())


class ReadOnlyCommandPositionTest(unittest.TestCase):
    """A tool name used only as an argument is not a mutation; a mutation at command position is."""

    NOT_DENIED = [
        "grep -rn mv src",
        "ls | grep dd",
        "grep -rn install src",
        "command -v rm",
        "git log --oneline",
    ]
    DENIED = [
        "rm -rf src",
        "env rm x",
        "timeout 5 rm x",
        "ls | xargs rm",
        "find . -name x -exec rm {} +",
        'bash -c "rm -rf src"',
        'eval "mv a b"',
        'echo "unterminated; rm x',
        "apt remove curl",
        "apt-get remove curl",
        "brew upgrade",
        "make install",
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wt = Path(os.path.realpath(self.tmp.name)) / "wt_ro"
        self.wt.mkdir()

    def _decision(self, cmd):
        r = run_guard("bash-ro", {"tool_input": {"command": cmd}, "cwd": str(self.wt)}, cwd=str(self.wt))
        self.assertEqual(r.returncode, 0, msg=f"cmd={cmd!r} stderr={r.stderr!r}")
        return decision_of(r), r

    def test_tool_name_as_argument_is_not_denied(self):
        for cmd in self.NOT_DENIED:
            with self.subTest(cmd=cmd):
                decision, r = self._decision(cmd)
                self.assertNotEqual(decision, "deny", msg=f"stdout={r.stdout!r}")

    def test_mutation_at_command_position_is_denied(self):
        for cmd in self.DENIED:
            with self.subTest(cmd=cmd):
                decision, r = self._decision(cmd)
                self.assertEqual(decision, "deny", msg=f"stdout={r.stdout!r}")


if __name__ == "__main__":
    unittest.main()
