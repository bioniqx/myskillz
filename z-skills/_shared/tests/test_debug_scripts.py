"""Shell-level checks for z-systematic-debugging/scripts (stress.sh)."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRESS = ROOT / "z-systematic-debugging" / "scripts" / "stress.sh"
BASH = shutil.which("bash")


@unittest.skipUnless(BASH, "needs bash")
class StressOutputDirReuseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = dict(os.environ, TMPDIR=self.tmp)
        self.out = os.path.join(self.tmp, "out")

    def run_stress(self, *cmd):
        argv = [BASH, str(STRESS), "-n", "2", "-j", "1", "-o", self.out, "--"] + list(cmd)
        return subprocess.run(argv, cwd=self.tmp, env=self.env, capture_output=True, text=True, timeout=120)

    def test_fresh_dir_runs(self):
        r = self.run_stress("true")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("RESULT: 0/2 failed", r.stdout)

    def test_reused_dir_after_pass_is_refused(self):
        self.assertEqual(self.run_stress("true").returncode, 0)
        r = self.run_stress("true")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("already holds stress results", r.stderr)
        self.assertNotIn("RESULT:", r.stdout)

    def test_old_fail_logs_are_kept_not_counted(self):
        os.mkdir(self.out)
        Path(self.out, "rc.1").write_text("1\n")
        Path(self.out, "FAIL.1.rc1.log").write_text("old failure\n")
        r = self.run_stress("true")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("already holds stress results", r.stderr)
        self.assertEqual(Path(self.out, "FAIL.1.rc1.log").read_text(), "old failure\n")


if __name__ == "__main__":
    unittest.main()
