"""Black-box test: bisect-parallel.sh removes ignored build output between rounds (T21)."""
import os
import shutil
import subprocess
import tempfile
import unittest

SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "claude-systematic-debugging-6.3")
BISECT = os.path.join(SKILL, "scripts", "bisect-parallel.sh")


def git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args), check=True,
                          stdout=subprocess.PIPE, text=True).stdout.strip()


class TestBisectCleansIgnoredOutput(unittest.TestCase):
    def setUp(self):
        self.tmproot = os.path.realpath(tempfile.mkdtemp(prefix="sdbisect."))
        self.addCleanup(shutil.rmtree, self.tmproot, ignore_errors=True)

    def test_stale_ignored_output_does_not_flip_good_commits_to_bad(self):
        repo = os.path.join(self.tmproot, "repo")
        os.makedirs(repo)
        subprocess.run(["git", "init", "-q", repo], check=True)
        git(repo, "config", "user.email", "t@t.example")
        git(repo, "config", "user.name", "tester")
        with open(os.path.join(repo, ".gitignore"), "w") as fh:
            fh.write("build/\nnode_modules/\n")
        os.makedirs(os.path.join(repo, "node_modules"))
        with open(os.path.join(repo, "node_modules", "dep"), "w") as fh:
            fh.write("dep\n")
        bad_at = 7
        for i in range(0, 13):
            with open(os.path.join(repo, "version.txt"), "w") as fh:
                fh.write(str(i))
            git(repo, "add", ".gitignore", "version.txt")
            git(repo, "commit", "-q", "-m", "v%d" % i)
        good = git(repo, "rev-list", "--max-parents=0", "HEAD")
        # The probe leaves ignored output behind. A worktree reused in a later round
        # that still holds it would report every commit as bad.
        probe = ('if [ -e build/marker ]; then echo stale ignored output; exit 1; fi; '
                 '[ -e node_modules/dep ] || { echo deps not linked; exit 1; }; '
                 'mkdir -p build; : > build/marker; '
                 '[ "$(cat version.txt)" -lt %d ]' % bad_at)
        env = dict(os.environ, TMPDIR=self.tmproot)
        r = subprocess.run(["bash", BISECT, "-j", "2", "--no-verify", "--link", "node_modules", good, "HEAD",
                            "--", "bash", "-c", probe],
                           cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("FIRST BAD COMMIT", r.stdout)
        self.assertRegex(r.stdout, r"(?m)^\s+v%d$" % bad_at)
        # clean -x must remove the symlink in the worktree, never the linked directory itself
        self.assertTrue(os.path.exists(os.path.join(repo, "node_modules", "dep")))


if __name__ == "__main__":
    unittest.main()
