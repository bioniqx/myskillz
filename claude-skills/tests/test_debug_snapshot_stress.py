"""Black-box tests for snapshot.sh and stress.sh fixes (T20)."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "claude-systematic-debugging-6.3")
SNAPSHOT = os.path.join(SKILL, "scripts", "snapshot.sh")
STRESS = os.path.join(SKILL, "scripts", "stress.sh")


def sh(cmd, cwd=None, env=None, timeout=60):
    return subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, timeout=timeout)


class BaseTC(unittest.TestCase):
    def setUp(self):
        self.tmproot = os.path.realpath(tempfile.mkdtemp(prefix="sdsnap."))
        self.addCleanup(shutil.rmtree, self.tmproot, ignore_errors=True)


class TestSnapshotRelativeInvocation(BaseTC):
    def test_cpu_count_survives_relative_script_path_and_dir_argument(self):
        target = os.path.join(self.tmproot, "proj")
        os.makedirs(target)
        skill = os.path.realpath(SKILL)
        parent = os.path.dirname(skill)
        rel = os.path.join(os.path.basename(skill), "scripts", "snapshot.sh")
        r = sh(["bash", rel, target], cwd=parent)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("No such file", r.stderr)
        self.assertRegex(r.stdout, r"## cwd: \S+\s+cpus: \d+\s+os: ")
        self.assertIn(target, r.stdout)

    def test_missing_directory_is_reported_and_exits_zero(self):
        missing = os.path.join(self.tmproot, "nope")
        r = sh(["bash", SNAPSHOT, missing])
        self.assertEqual(r.returncode, 0)
        self.assertIn("snapshot: no such dir: " + missing, r.stdout)


class TestStressBaselineValidation(BaseTC):
    def test_zero_baseline_runs_are_rejected_up_front(self):
        for bad in ("0/0", "5/0", "3/00"):
            r = sh(["bash", STRESS, "-n", "2", "-j", "1", "-b", bad, "--", "true"])
            self.assertEqual(r.returncode, 2, bad + "\n" + r.stdout + r.stderr)
            self.assertIn("error: -b expects F/N with N > 0", r.stderr)
            self.assertNotIn("division by zero", r.stderr)
            self.assertNotIn("RESULT", r.stdout)


class TestStressReusedOutputDir(BaseTC):
    def test_stale_results_in_reused_output_dir_are_ignored(self):
        out = os.path.join(self.tmproot, "out")
        os.makedirs(out)
        for name, body in (("rc.99", "1\n"), ("FAIL.99.rc1.log", "old\n"),
                           ("run.98.log", "old pass log\n"), (".stop", "")):
            with open(os.path.join(out, name), "w") as fh:
                fh.write(body)
        r = sh(["bash", STRESS, "-n", "4", "-j", "2", "-x", "-o", out, "--", "true"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("RESULT: 0/4 failed", r.stdout)
        for name in ("rc.99", "FAIL.99.rc1.log", "run.98.log", ".stop"):
            self.assertFalse(os.path.exists(os.path.join(out, name)), name)

    def test_second_run_in_same_dir_counts_only_its_own_failures(self):
        out = os.path.join(self.tmproot, "out2")
        first = sh(["bash", STRESS, "-n", "4", "-j", "2", "-o", out, "--", "bash", "-c", "exit 1"])
        self.assertEqual(first.returncode, 1, first.stdout + first.stderr)
        self.assertIn("RESULT: 4/4 failed", first.stdout)
        second = sh(["bash", STRESS, "-n", "3", "-j", "2", "-o", out, "--", "true"])
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertIn("RESULT: 0/3 failed", second.stdout)


class TestStressStatsOutput(BaseTC):
    def test_wilson_interval_and_fix_proof_hint_for_half_failures(self):
        r = sh(["bash", STRESS, "-n", "10", "-j", "2", "--",
                "bash", "-c", "exit $((STRESS_RUN % 2))"])
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertRegex(
            r.stdout,
            r"RESULT: 5/10 failed \(50\.0%\), 95% Wilson CI \[23\.66%, 76\.3%\], wall \d+s")
        self.assertIn("To prove a fix: >= 13 clean runs (3 / Wilson lower bound), "
                      "or rerun with -b 5/10", r.stdout)

    def test_rule_of_three_when_no_failures(self):
        r = sh(["bash", STRESS, "-n", "10", "-j", "2", "--", "true"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertRegex(r.stdout, r"RESULT: 0/10 failed \(0\.0%\), 95% Wilson CI \[0\.00%, 27\.8%\]")
        self.assertIn("No failures: 95% upper bound on failure rate ~ 30.00% (rule of three)", r.stdout)

    def test_fisher_exact_against_baseline(self):
        r = sh(["bash", STRESS, "-n", "10", "-j", "2", "-b", "10/10", "--", "true"])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("VS BASELINE 10/10: one-sided Fisher exact p = 5.413e-06 -> "
                      "rate is significantly LOWER (fix supported)", r.stdout)
        self.assertIn("zero-failure runs needed vs baseline ~ 5", r.stdout)

    def test_fisher_not_significant_when_rates_match(self):
        r = sh(["bash", STRESS, "-n", "10", "-j", "2", "-b", "5/10", "--",
                "bash", "-c", "exit $((STRESS_RUN % 2))"])
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("NOT significant", r.stdout)


if __name__ == "__main__":
    unittest.main()
