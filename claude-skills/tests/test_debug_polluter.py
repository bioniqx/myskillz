"""Black-box tests for claude-systematic-debugging-6.3/scripts/find-polluter.sh (T19).

Covers: polluter detection, a clean run, a leftover untracked pollution file that
must not be blamed on the first test, and the vendor/build directories that must
not be scanned for test files. Fixtures live under the system temp dir.
"""
import os
import shutil
import subprocess
import tempfile
import unittest

SCRIPTS = os.path.realpath(os.path.join(
    os.path.dirname(__file__), "..", "claude-systematic-debugging-6.3", "scripts"))
FINDPOL = os.path.join(SCRIPTS, "find-polluter.sh")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write(text)


def git(repo, *args):
    subprocess.run(["git", "-C", repo] + list(args), check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class PolluterBase(unittest.TestCase):
    def setUp(self):
        self.tmproot = os.path.realpath(tempfile.mkdtemp(prefix="polltest."))
        self.addCleanup(shutil.rmtree, self.tmproot, ignore_errors=True)
        self.repo = os.path.join(self.tmproot, "repo")
        os.makedirs(self.repo)
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        git(self.repo, "config", "user.email", "t@t.example")
        git(self.repo, "config", "user.name", "tester")
        # runner: logs every file it is given; creates polluted.out for b.test.js only
        # when the untracked helper.txt was carried into the worktree.
        self.log = os.path.join(self.tmproot, "runs.log")
        self.runner = os.path.join(self.tmproot, "runner.sh")
        write(self.runner,
              '#!/usr/bin/env bash\n'
              'echo "$1" >> "%s"\n'
              'case "$1" in\n'
              '  *b.test.js) [ -f helper.txt ] && : > polluted.out;;\n'
              'esac\n'
              'exit 0\n' % self.log)
        os.chmod(self.runner, 0o755)

    def commit_all(self):
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "fixture")

    def run_finder(self, *extra):
        env = dict(os.environ)
        env["TMPDIR"] = self.tmproot
        return subprocess.run(
            ["bash", FINDPOL, "-j", "2", "--cmd", "bash " + self.runner]
            + list(extra) + ["polluted.out", "**/*.test.js"],
            cwd=self.repo, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=60)

    def logged(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log) as fh:
            return fh.read().split()

    def make_tests(self):
        for name in ("a", "b", "c"):
            write(os.path.join(self.repo, "src", name + ".test.js"), "// test\n")
        self.commit_all()
        write(os.path.join(self.repo, "helper.txt"), "untracked helper\n")


class FindPolluterDetectionTests(PolluterBase):
    def test_finds_the_polluting_test_file(self):
        self.make_tests()
        r = self.run_finder()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FOUND POLLUTER: src/b.test.js", r.stdout)
        self.assertIn("created polluted.out", r.stdout)

    def test_reports_no_polluter_when_nothing_pollutes(self):
        for name in ("a", "b"):
            write(os.path.join(self.repo, "src", name + ".test.js"), "// test\n")
        self.commit_all()
        r = self.run_finder()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("No polluter found across 2 files", r.stdout)
        self.assertNotIn("FOUND POLLUTER", r.stdout)

    def test_absolute_pollution_path_still_finds_the_polluter(self):
        self.make_tests()
        marker = os.path.join(self.tmproot, "abs_polluted.out")
        cmd = "bash -c 'case \"$1\" in *b.test.js) : > %s;; esac' _" % marker
        env = dict(os.environ)
        env["TMPDIR"] = self.tmproot
        r = subprocess.run(
            ["bash", FINDPOL, "--cmd", cmd, marker, "**/*.test.js"],
            cwd=self.repo, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, timeout=60)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FOUND POLLUTER: src/b.test.js", r.stdout)


class FindPolluterIsolationTests(PolluterBase):
    def test_leftover_untracked_pollution_file_is_not_blamed_on_first_test(self):
        self.make_tests()
        write(os.path.join(self.repo, "polluted.out"), "leftover from an earlier run\n")
        r = self.run_finder()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FOUND POLLUTER: src/b.test.js", r.stdout)
        self.assertNotIn("FOUND POLLUTER: src/a.test.js", r.stdout)

    def test_leftover_pollution_alone_does_not_report_a_polluter(self):
        for name in ("a", "b"):
            write(os.path.join(self.repo, "src", name + ".test.js"), "// test\n")
        self.commit_all()
        write(os.path.join(self.repo, "polluted.out"), "leftover from an earlier run\n")
        r = self.run_finder()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("FOUND POLLUTER", r.stdout)

    def test_vendor_and_build_dirs_are_not_scanned(self):
        write(os.path.join(self.repo, ".gitignore"), "vendor_dir/\n")
        write(os.path.join(self.repo, "src", "a.test.js"), "// test\n")
        for d in ("dist", ".venv/lib", ".claude", "node_modules/pkg"):
            write(os.path.join(self.repo, d, "x.test.js"), "// test\n")
        write(os.path.join(self.repo, "vendor_dir", "w.test.js"), "// test\n")
        self.commit_all()
        r = self.run_finder("--link", "vendor_dir")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("across 1 test files", r.stderr)
        self.assertEqual(self.logged(), ["src/a.test.js"])


if __name__ == "__main__":
    unittest.main()
