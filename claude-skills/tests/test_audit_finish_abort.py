"""Black-box tests for `audit.py finish` and `audit.py abort` (T04).

Both commands close the audit and disarm the guard hooks: the `.audit/ACTIVE` marker is removed
and `config.json` records `active: false` plus a `finished` timestamp. `finish` prints the
headline numbers for the report; `abort` is the same close without needing a report.

Runs the real script in a throwaway directory under the system temp dir.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TESTS_DIR)  # claude-skills/
AUDIT = os.path.join(BASE_DIR, "claude-requirements-code-audit", "scripts", "audit.py")


class AuditCase(unittest.TestCase):
    def setUp(self):
        self.cwd = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.cwd, ignore_errors=True)
        with open(os.path.join(self.cwd, "spec.md"), "w") as f:
            f.write("# Requirements\n\n- R1: the app must greet the user.\n")
        self.audit_dir = os.path.join(self.cwd, ".audit")

    def audit(self, *args):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, AUDIT, "--cwd", self.cwd] + list(args),
                              cwd=self.cwd, env=env, capture_output=True, text=True, timeout=30)

    def init(self):
        p = self.audit("init", "--spec", os.path.join(self.cwd, "spec.md"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(os.path.exists(os.path.join(self.audit_dir, "ACTIVE")))
        return p

    def config(self):
        with open(os.path.join(self.audit_dir, "config.json")) as f:
            return json.load(f)

    def write_checklist(self):
        with open(os.path.join(self.audit_dir, "checklist.jsonl"), "w") as f:
            f.write(json.dumps({"id": "R1", "text": "the app must greet the user",
                                "strength": "MUST", "source": "spec.md"}) + "\n")


class FinishTests(AuditCase):
    def test_finish_disarms_the_guard_and_prints_the_headline(self):
        self.init()
        self.write_checklist()
        p = self.audit("finish")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("Audit closed (guard hooks disarmed)", p.stdout)
        self.assertIn("HEADLINE: Total requirements 1", p.stdout)
        self.assertIn("Discrepancies: 0", p.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.audit_dir, "ACTIVE")))
        cfg = self.config()
        self.assertIs(cfg["active"], False)
        self.assertTrue(cfg["finished"])

    def test_finish_twice_is_harmless(self):
        self.init()
        self.assertEqual(self.audit("finish").returncode, 0)
        p = self.audit("finish")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("Audit closed", p.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.audit_dir, "ACTIVE")))

    def test_init_after_finish_asks_for_force(self):
        self.init()
        self.audit("finish")
        p = self.audit("init", "--spec", os.path.join(self.cwd, "spec.md"))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("A finished audit exists here. Use --force", p.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.audit_dir, "ACTIVE")))

    def test_finish_without_an_audit_fails(self):
        p = self.audit("finish")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("no audit here", p.stdout)


class AbortTests(AuditCase):
    def test_abort_closes_the_audit_without_writing_a_report(self):
        self.init()
        p = self.audit("abort")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("Audit closed (guard hooks disarmed)", p.stdout)
        self.assertFalse(os.path.exists(os.path.join(self.audit_dir, "ACTIVE")))
        self.assertIs(self.config()["active"], False)
        self.assertFalse(os.path.exists(os.path.join(self.audit_dir, "requirements-code-audit.md")))

    def test_abort_without_an_audit_fails(self):
        p = self.audit("abort")
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertIn("no audit here", p.stdout)


if __name__ == "__main__":
    unittest.main()
