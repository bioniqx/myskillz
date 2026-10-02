"""Shell-level checks for systematic-debugging/scripts (oc-bisect-parallel.sh, oc-stress.sh)."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "oc-systematic-debugging" / "scripts"
BISECT = SCRIPTS / "oc-bisect-parallel.sh"
STRESS = SCRIPTS / "oc-stress.sh"
BASH = shutil.which("bash")
TIMEOUT_WARNING = "warn: no timeout/gtimeout found; -t ignored"


def path_without_timeout(dest):
    """Fill dest with symlinks to every executable on PATH except timeout/gtimeout."""
    seen = set()
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d or not os.path.isdir(d):
            continue
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for name in names:
            if name in seen or name in ("timeout", "gtimeout"):
                continue
            src = os.path.join(d, name)
            if os.path.isfile(src) and os.access(src, os.X_OK):
                seen.add(name)
                os.symlink(src, os.path.join(dest, name))
    return dest


def git_env(tmp):
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_CONFIG_NOSYSTEM": "1", "HOME": tmp, "TMPDIR": tmp,
    })
    return env


def make_repo(tmp):
    """Two-commit repo: HEAD~1 is good, HEAD is bad."""
    repo = os.path.join(tmp, "repo")
    os.mkdir(repo)
    env = git_env(tmp)
    for args in (["init", "-q"], ):
        subprocess.run(["git"] + args, cwd=repo, env=env, check=True)
    for v in ("1", "2"):
        Path(repo, "v.txt").write_text(v + "\n")
        subprocess.run(["git", "add", "v.txt"], cwd=repo, env=env, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "v" + v], cwd=repo, env=env, check=True)
    return repo


@unittest.skipUnless(BASH and shutil.which("git"), "needs bash and git")
class BisectTimeoutWarningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = make_repo(self.tmp)
        farm = os.path.join(self.tmp, "bin")
        os.mkdir(farm)
        self.env = git_env(self.tmp)
        self.env["PATH"] = path_without_timeout(farm)

    def run_bisect(self, *opts):
        cmd = [BASH, str(BISECT), "-j", "1", "--no-verify"] + list(opts) + ["HEAD~1", "HEAD", "--", "true"]
        return subprocess.run(cmd, cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=120)

    def test_t_without_timeout_binary_warns(self):
        r = self.run_bisect("-t", "5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(TIMEOUT_WARNING, r.stderr)
        self.assertIn("FIRST BAD COMMIT", r.stdout)

    def test_no_t_no_warning(self):
        r = self.run_bisect()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(TIMEOUT_WARNING, r.stderr)


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


@unittest.skipUnless(BASH, "needs bash")
class HelperScriptsParseTest(unittest.TestCase):
    def test_every_helper_script_passes_bash_n(self):
        for name in ("oc-snapshot.sh", "oc-stress.sh", "oc-bisect-parallel.sh", "oc-find-polluter.sh", "oc-lib.sh"):
            r = subprocess.run([BASH, "-n", str(SCRIPTS / name)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, name + ": " + r.stderr)


if __name__ == "__main__":
    unittest.main()
