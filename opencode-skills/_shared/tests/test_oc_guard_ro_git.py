"""Read-only roles may run git merge-base and git worktree list, but not git merge / worktree add."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[2] / "oc-dev-team" / "scripts" / "oc_guard.py"


class ReadOnlyGitTests(unittest.TestCase):
    def setUp(self):
        self.wt = Path(tempfile.mkdtemp()).resolve()
        sd = self.wt / ".oc-slice"
        sd.mkdir()
        (sd / "id").write_text("S1\n")
        (sd / "footprint").write_text("src/\n")
        self.addCleanup(shutil.rmtree, str(self.wt), True)

    def ro(self, command, role="reviewer"):
        r = subprocess.run([sys.executable, str(GUARD), "oc"], capture_output=True, text=True,
                           input=json.dumps({"tool": "shell",
                                             "args": {"command": command, "workdir": str(self.wt)},
                                             "cwd": str(self.wt), "role": role}))
        self.assertEqual(r.returncode, 0)
        if not r.stdout.strip():
            return ""
        return json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"]

    def test_merge_base_is_allowed(self):
        self.assertNotEqual(self.ro("git merge-base HEAD HEAD"), "deny")

    def test_worktree_list_is_allowed(self):
        self.assertNotEqual(self.ro("git worktree list"), "deny")

    def test_merge_is_denied(self):
        self.assertEqual(self.ro("git merge x"), "deny")

    def test_worktree_add_is_denied(self):
        self.assertEqual(self.ro("git worktree add p"), "deny")


if __name__ == "__main__":
    unittest.main()
