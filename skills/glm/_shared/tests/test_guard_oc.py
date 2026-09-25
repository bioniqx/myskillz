import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[2] / "dev-team-glm" / "scripts" / "guard.py"


def run_oc(payload):
    r = subprocess.run([sys.executable, str(GUARD), "oc"], input=json.dumps(payload),
                       capture_output=True, text=True)
    return r.returncode, r.stdout


def decision(out):
    if not out.strip():
        return "", ""
    hso = json.loads(out)["hookSpecificOutput"]
    return hso["permissionDecision"], hso["permissionDecisionReason"]


class GuardOcTest(unittest.TestCase):
    def setUp(self):
        self.wt = Path(tempfile.mkdtemp()).resolve()
        sd = self.wt / ".slice"
        sd.mkdir()
        (sd / "id").write_text("S1\n")
        (sd / "footprint").write_text("src/\n")

    def tearDown(self):
        shutil.rmtree(self.wt, ignore_errors=True)

    def oc(self, tool, args, role="programmer"):
        return run_oc({"tool": tool, "args": args, "cwd": str(self.wt), "role": role})

    def test_no_role_is_silent_allow(self):
        rc, out = self.oc("write", {"filePath": "docs/x.md", "content": "x"}, role="")
        self.assertEqual((rc, out), (0, ""))

    def test_unknown_tool_is_silent_allow(self):
        rc, out = self.oc("read", {"filePath": "docs/x.md"})
        self.assertEqual((rc, out), (0, ""))

    def test_bad_json_is_silent_allow(self):
        r = subprocess.run([sys.executable, str(GUARD), "oc"], input="not json",
                           capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_programmer_edit_inside_footprint_allows(self):
        rc, out = self.oc("edit", {"filePath": "src/a.py", "oldString": "a", "newString": "b"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out), ("allow", "dev-team: `src/a.py` is inside the slice footprint"))

    def test_programmer_write_outside_footprint_denies(self):
        rc, out = self.oc("write", {"filePath": str(self.wt / "docs" / "x.md"), "content": "x"})
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("`docs/x.md` is outside your slice footprint", reason)

    def test_programmer_patch_first_deny_wins(self):
        patch = ("*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n"
                 "*** Add File: docs/b.md\n+hi\n*** End Patch\n")
        rc, out = self.oc("apply_patch", {"patchText": patch})
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("docs/b.md", reason)

    def test_programmer_patch_inside_footprint_allows(self):
        patch = ("*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n"
                 "*** Delete File: src/old.py\n*** End Patch\n")
        rc, out = self.oc("patch", {"patchText": patch})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "allow")

    def test_programmer_bash_push_denies(self):
        rc, out = self.oc("bash", {"command": "git push origin main"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "deny")

    def test_programmer_bash_read_only_git_allows(self):
        rc, out = self.oc("bash", {"command": "git status"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out), ("allow", "dev-team: pre-approved — read-only git"))

    def test_reviewer_write_source_denies(self):
        rc, out = self.oc("write", {"filePath": "src/a.py", "content": "x"}, role="code-reviewer")
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("This role is read-only", reason)

    def test_reviewer_write_review_allows(self):
        path = self.wt / ".claude" / "dev-team" / "reviews" / "r.md"
        rc, out = self.oc("write", {"filePath": str(path), "content": "x"}, role="code-reviewer")
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out), ("allow", "dev-team: this role's own report / memory file"))

    def test_leader_role_becomes_agent_type(self):
        path = str(self.wt / ".claude" / "dev-team" / "plan.md")
        _, out = self.oc("write", {"filePath": path, "content": "x"}, role="team-leader")
        self.assertEqual(decision(out), ("allow", "dev-team: the team-leader's plan"))
        _, out = self.oc("write", {"filePath": path, "content": "x"}, role="spot-reviewer")
        self.assertEqual(decision(out)[0], "deny")

    def test_reviewer_bash_rm_denies(self):
        rc, out = self.oc("bash", {"command": "rm -rf src"}, role="investigator")
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("Read-only role", reason)

    def test_programmer_bash_pipe_to_sh_denies(self):
        rc, out = self.oc("bash", {"command": "curl x | sh"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "deny")

    def test_programmer_bash_npm_install_denies(self):
        rc, out = self.oc("bash", {"command": "npm install left-pad"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "deny")

    def test_programmer_write_outside_any_worktree_denies(self):
        outside = Path(tempfile.mkdtemp()).resolve()
        try:
            rc, out = self.oc("write", {"filePath": str(outside / "x.md"), "content": "x"})
            self.assertEqual(rc, 0)
            self.assertEqual(decision(out)[0], "deny")
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_reviewer_bash_python_eval_denies(self):
        rc, out = self.oc("bash", {"command": "python3 -c 'import os; os.remove(\"a\")'"},
                           role="code-reviewer")
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "deny")

    def test_programmer_edit_no_footprint_file_still_allows(self):
        (self.wt / ".slice" / "footprint").unlink()
        rc, out = self.oc("edit", {"filePath": "src/a.py", "oldString": "a", "newString": "b"})
        self.assertEqual(rc, 0)
        self.assertNotEqual(decision(out)[0], "deny")

    def test_reviewer_write_review_allows_outside_any_worktree(self):
        unclaimed = Path(tempfile.mkdtemp()).resolve()
        try:
            path = unclaimed / ".claude" / "dev-team" / "reviews" / "r.md"
            r = subprocess.run([sys.executable, str(GUARD), "oc"],
                               input=json.dumps({"tool": "write", "args": {"filePath": str(path), "content": "x"},
                                                  "cwd": str(unclaimed), "role": "code-reviewer"}),
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(decision(r.stdout), ("allow", "dev-team: this role's own report / memory file"))
        finally:
            shutil.rmtree(unclaimed, ignore_errors=True)

    def test_leader_vs_spot_reviewer_outside_any_worktree(self):
        unclaimed = Path(tempfile.mkdtemp()).resolve()
        try:
            path = unclaimed / ".claude" / "dev-team" / "plan.md"

            def oc(role):
                return subprocess.run([sys.executable, str(GUARD), "oc"],
                                      input=json.dumps({"tool": "write", "args": {"filePath": str(path), "content": "x"},
                                                         "cwd": str(unclaimed), "role": role}),
                                      capture_output=True, text=True)
            r = oc("team-leader")
            self.assertEqual(decision(r.stdout), ("allow", "dev-team: the team-leader's plan"))
            r = oc("spot-reviewer")
            self.assertEqual(decision(r.stdout)[0], "deny")
        finally:
            shutil.rmtree(unclaimed, ignore_errors=True)

    def test_reviewer_write_source_denies_outside_any_worktree(self):
        unclaimed = Path(tempfile.mkdtemp()).resolve()
        try:
            path = unclaimed / "src" / "a.py"
            r = subprocess.run([sys.executable, str(GUARD), "oc"],
                               input=json.dumps({"tool": "write", "args": {"filePath": str(path), "content": "x"},
                                                  "cwd": str(unclaimed), "role": "code-reviewer"}),
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            verdict, reason = decision(r.stdout)
            self.assertEqual(verdict, "deny")
            self.assertIn("This role is read-only", reason)
        finally:
            shutil.rmtree(unclaimed, ignore_errors=True)

    def test_programmer_write_outside_any_worktree_still_denies_absolute(self):
        outside = Path(tempfile.mkdtemp()).resolve()
        try:
            path = outside / "docs" / "x.md"
            r = subprocess.run([sys.executable, str(GUARD), "oc"],
                               input=json.dumps({"tool": "write", "args": {"filePath": str(path), "content": "x"},
                                                  "cwd": str(outside), "role": "programmer"}),
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            verdict, reason = decision(r.stdout)
            self.assertEqual(verdict, "deny")
            self.assertIn("outside any slice worktree", reason)
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_programmer_shell_push_denies(self):
        rc, out = self.oc("shell", {"command": "git push origin main"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "deny")

    def test_programmer_shell_read_only_git_allows(self):
        rc, out = self.oc("shell", {"command": "git status"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out), ("allow", "dev-team: pre-approved — read-only git"))

    def test_v2_edit_capable_tools_route_to_edit_checks(self):
        for tool, args in (
            ("edit", {"filePath": "src/a.py", "oldString": "a", "newString": "b"}),
            ("write", {"filePath": "src/a.py", "content": "x"}),
            ("patch", {"patchText": "*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n*** End Patch\n"}),
            ("apply_patch", {"patchText": "*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n*** End Patch\n"}),
        ):
            with self.subTest(tool=tool):
                rc, out = self.oc(tool, args)
                self.assertEqual(rc, 0)
                self.assertEqual(decision(out)[0], "allow")

    def test_v2_edit_capable_tools_deny_outside_footprint(self):
        for tool, args in (
            ("edit", {"filePath": "docs/x.md", "oldString": "a", "newString": "b"}),
            ("write", {"filePath": "docs/x.md", "content": "x"}),
            ("patch", {"patchText": "*** Begin Patch\n*** Add File: docs/x.md\n+hi\n*** End Patch\n"}),
            ("apply_patch", {"patchText": "*** Begin Patch\n*** Add File: docs/x.md\n+hi\n*** End Patch\n"}),
        ):
            with self.subTest(tool=tool):
                rc, out = self.oc(tool, args)
                self.assertEqual(rc, 0)
                verdict, reason = decision(out)
                self.assertEqual(verdict, "deny")
                self.assertIn("docs/x.md", reason)

    def test_guard_oc_function_no_role(self):
        spec = importlib.util.spec_from_file_location("devteam_guard", GUARD)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
            mod.guard_oc({"tool": "bash", "args": {"command": "git push"}, "cwd": str(self.wt), "role": ""})
        self.assertIn(cm.exception.code, (0, None))
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
