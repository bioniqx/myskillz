"""Parity tests for oc_guard.py: engine-subcommand deny, quoted-argument scan, write patterns."""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[2] / "oc-dev-team" / "scripts" / "oc_guard.py"
_SPEC = importlib.util.spec_from_file_location("oc_guard_port_under_test", str(GUARD))
G = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(G)

ENGINE = "/skill/scripts/oc_devteam.py"


def run_oc(payload):
    r = subprocess.run([sys.executable, str(GUARD), "oc"], input=json.dumps(payload),
                       capture_output=True, text=True)
    return r.returncode, r.stdout


def decision(out):
    if not out.strip():
        return "", ""
    hso = json.loads(out)["hookSpecificOutput"]
    return hso["permissionDecision"], hso["permissionDecisionReason"]


class GuardPortTests(unittest.TestCase):
    def setUp(self):
        self.wt = Path(tempfile.mkdtemp()).resolve()
        sd = self.wt / ".oc-slice"
        sd.mkdir()
        (sd / "id").write_text("S1\n")
        (sd / "footprint").write_text("src/\n")
        self.addCleanup(shutil.rmtree, str(self.wt), True)

    def shell(self, command):
        rc, out = run_oc({"tool": "shell", "args": {"command": command, "workdir": str(self.wt)},
                          "cwd": str(self.wt), "role": "programmer"})
        self.assertEqual(rc, 0)
        return decision(out)

    def test_path_matches_strips_only_a_literal_dot_slash(self):
        self.assertFalse(G.path_matches(".env", "env"))
        self.assertFalse(G.path_matches(".claude/x", "claude/"))
        self.assertTrue(G.path_matches("./src/a.py", "src"))

    def test_lane_cannot_run_engine_reset(self):
        verdict, reason = self.shell(f"python3 {ENGINE} reset --yes")
        self.assertEqual(verdict, "deny")
        self.assertIn("drives the engine", reason)

    def test_lane_cannot_run_finish_force_behind_a_wrapper(self):
        verdict, reason = self.shell(f"timeout 60 python3 {ENGINE} finish --force")
        self.assertEqual(verdict, "deny")
        self.assertIn("drives the engine", reason)

    def test_lane_may_still_claim_and_report(self):
        for cmd in (f"python3 {ENGINE} claim S1 --worktree {self.wt}",
                    f"python3 {ENGINE} report S1 --file {self.wt}/.oc-slice/report.md"):
            _, reason = self.shell(cmd)
            self.assertNotIn("drives the engine", reason)

    def test_quoted_argument_is_not_mistaken_for_a_push(self):
        _, reason = self.shell("grep 'git push' README.md")
        self.assertNotIn("Blocked", reason)

    def test_unquoted_push_is_still_denied(self):
        verdict, reason = self.shell("git push origin main")
        self.assertEqual(verdict, "deny")
        self.assertIn("Blocked", reason)

    def test_worktree_list_is_readable_but_add_is_not(self):
        _, reason = self.shell("git worktree list")
        self.assertNotIn("integration/history", reason)
        verdict, reason = self.shell("git worktree add ../x")
        self.assertEqual(verdict, "deny")
        self.assertIn("integration/history", reason)

    def test_python_write_text_to_run_state_is_denied(self):
        verdict, reason = self.shell(
            "python3 -c \"open('.opencode/oc-dev-team/slices/S1.done').write_text('x')\"")
        self.assertEqual(verdict, "deny")
        self.assertIn("run state", reason)

    def test_python_write_bytes_to_slice_metadata_is_denied(self):
        verdict, reason = self.shell(
            "python3 -c \"import pathlib; pathlib.Path('.oc-slice/red').write_bytes(b'x')\"")
        self.assertEqual(verdict, "deny")
        self.assertIn("dev-team metadata", reason)

    def test_write_marker_resets_the_stop_counter(self):
        sd = self.wt / ".oc-slice"
        (sd / "stop_blocks").write_text("2")
        G.write_marker(self.wt, sd, "S1", "done")
        self.assertFalse((sd / "stop_blocks").exists())


if __name__ == "__main__":
    unittest.main()
