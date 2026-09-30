"""K24: harvested/added fix slices get a workable kind.

Black-box: real devteam.py subprocesses against a disposable git repo in the SYSTEM temp dir.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEVTEAM_PATH = str(Path(__file__).resolve().parents[1] / "dev-team-v3.2" / "scripts" / "devteam.py")


def run_dt(args, cwd):
    return subprocess.run([sys.executable, DEVTEAM_PATH] + args, cwd=str(cwd),
                          capture_output=True, text=True, timeout=60)


def git(args, cwd):
    return subprocess.run(["git"] + args, cwd=str(cwd), check=True, capture_output=True, text=True).stdout


class FixKind(unittest.TestCase):
    TEST_CMD = "none"

    def setUp(self):
        repo = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(repo), True)
        for a in (["init", "-q", "-b", "main"], ["config", "user.email", "t@t"],
                  ["config", "user.name", "t"], ["config", "commit.gpgsign", "false"]):
            git(a, repo)
        (repo / "a.txt").write_text("x\n")
        git(["add", "-A"], repo)
        git(["commit", "-q", "-m", "init"], repo)
        plan = {"request": "K24", "profile": "balanced",
                "commands": {"test": self.TEST_CMD, "test_file": "none"},
                "slices": [{"id": "S1", "title": "s1", "files": ["a.txt"],
                            "risk": "low", "criteria": ["works"]}]}
        (repo / "plan.md").write_text("# plan\n```json\n%s\n```\n" % json.dumps(plan))
        self.assertEqual(run_dt(["init", "plan.md"], repo).returncode, 0)
        self.repo = repo

    def harvest(self, fix):
        fix = dict(fix, title="fix it", criteria=["fixed"])
        (self.repo / "rep.md").write_text("```json\n%s\n```\n" % json.dumps({"fixes": [fix]}))
        r = run_dt(["add-fixes", "rep.md"], self.repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        st = json.loads((self.repo / ".claude" / "dev-team" / "state.json").read_text())
        return st["slices"]["F1"], r.stdout + r.stderr

    def test_docs_only_footprint_becomes_docs_with_default_verify(self):
        s, _ = self.harvest({"files": ["README.md", "notes/a.txt", "guide.rst", "LICENSE"]})
        self.assertEqual(s["kind"], "docs")
        self.assertTrue(s["verify"].strip())
        self.assertIn("README.md", s["verify"])

    def test_mixed_docs_and_code_is_not_docs(self):
        s, _ = self.harvest({"files": ["README.md", "src/x.js", "tests/x.test.js"]})
        self.assertEqual(s["kind"], "code")

    def test_code_fix_without_test_path_is_not_a_code_slice(self):
        s, msg = self.harvest({"files": ["src/x.js"]})
        self.assertNotEqual(s["kind"], "code")
        self.assertIn("NOTE", msg)
        self.assertIn("src/x.js", msg)

    def test_code_fix_with_test_path_stays_code(self):
        s, _ = self.harvest({"files": ["src/x.js", "tests/x.test.js"]})
        self.assertEqual(s["kind"], "code")

    def test_explicit_kind_code_is_respected(self):
        s, _ = self.harvest({"kind": "code", "files": ["README.md"]})
        self.assertEqual(s["kind"], "code")

    def test_explicit_kind_refactor_is_respected(self):
        s, _ = self.harvest({"kind": "refactor", "files": ["README.md"]})
        self.assertEqual(s["kind"], "refactor")

    def test_explicit_docs_without_verify_on_doc_files_stays_docs_with_verify(self):
        s, _ = self.harvest({"kind": "docs", "files": ["README.md"]})
        self.assertEqual(s["kind"], "docs")
        self.assertTrue(s["verify"].strip())
        self.assertIn("README.md", s["verify"])

    def test_explicit_chore_without_verify_on_code_file_is_not_code(self):
        s, msg = self.harvest({"kind": "chore", "files": ["src/x.js"]})
        self.assertNotEqual(s["kind"], "code")
        self.assertIn("NOTE", msg)
        self.assertIn("src/x.js", msg)

    def test_explicit_code_without_test_path_keeps_code_and_notes(self):
        s, msg = self.harvest({"kind": "code", "files": ["src/x.js"]})
        self.assertEqual(s["kind"], "code")
        self.assertIn("NOTE", msg)
        self.assertIn("no test path", msg)

    def test_explicit_chore_with_verify_is_respected(self):
        s, _ = self.harvest({"kind": "chore", "verify": "true", "files": ["src/c.js"]})
        self.assertEqual(s["kind"], "chore")
        self.assertEqual(s["verify"], "true")


class FixKindConfiguredTest(FixKind):
    TEST_CMD = "make check-all"

    def test_code_without_test_path_verifies_with_configured_test_command(self):
        s, _ = self.harvest({"files": ["src/x.js"]})
        self.assertEqual(s["kind"], "chore")
        self.assertEqual(s["verify"], "make check-all")

    def test_docs_branch_keeps_ls_verify(self):
        s, _ = self.harvest({"files": ["README.md"]})
        self.assertEqual(s["kind"], "docs")
        self.assertTrue(s["verify"].startswith("ls --"))



class FixKindNoTestCommand(FixKind):
    def test_code_without_test_path_falls_back_to_ls(self):
        s, _ = self.harvest({"files": ["src/x.js"]})
        self.assertEqual(s["kind"], "chore")
        self.assertTrue(s["verify"].startswith("ls --"))
        self.assertIn("src/x.js", s["verify"])


if __name__ == "__main__":
    unittest.main()
