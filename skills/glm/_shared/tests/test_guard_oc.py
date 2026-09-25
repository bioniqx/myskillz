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
