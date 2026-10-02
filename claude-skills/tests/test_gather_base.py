"""Black-box tests for claude-git-diff-summary/scripts/gather.sh: base validation and diff size caps."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

GATHER = Path(__file__).resolve().parents[1] / "claude-git-diff-summary" / "scripts" / "gather.sh"

BASE_ENV = {
    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@example.com",
}


def _git(repo, *args, env):
    subprocess.run(["git", *args], cwd=str(repo), env=env, check=True,
                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)


def _out(repo, *args, env):
    return subprocess.run(["git", *args], cwd=str(repo), env=env, check=True,
                          capture_output=True, text=True, timeout=15).stdout.strip()


def make_repo(root):
    """A one-commit repo on branch 'main', no remote (so gather.sh never fetches)."""
    repo = root / "repo"
    repo.mkdir()
    env = dict(os.environ)
    env.update(BASE_ENV)
    env["HOME"] = str(root / "home")
    os.makedirs(env["HOME"], exist_ok=True)
    _git(repo, "init", "-q", env=env)
    (repo / "a.txt").write_text("one\n")
    _git(repo, "add", "a.txt", env=env)
    _git(repo, "commit", "-q", "-m", "init", env=env)
    _git(repo, "symbolic-ref", "HEAD", "refs/heads/main", env=env)
    return repo, env


def run_gather(repo, env, args=None):
    full_env = dict(env)
    full_env["GDS_NO_FETCH"] = "1"
    return subprocess.run(["bash", str(GATHER)] + (args or []), cwd=str(repo), env=full_env,
                          capture_output=True, text=True, timeout=20)


class _FeatureRepo(unittest.TestCase):
    """main points at the first commit; HEAD is on branch 'feature'."""

    def setUp(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(self.root), ignore_errors=True)
        self.repo, self.env = make_repo(self.root)
        self.first = _out(self.repo, "rev-parse", "HEAD", env=self.env)
        _git(self.repo, "update-ref", "refs/heads/feature", "HEAD", env=self.env)
        _git(self.repo, "symbolic-ref", "HEAD", "refs/heads/feature", env=self.env)

    def commit_file(self, name, text):
        (self.repo / name).write_text(text)
        _git(self.repo, "add", name, env=self.env)
        _git(self.repo, "commit", "-q", "-m", "add " + name, env=self.env)


class TestBaseRef(_FeatureRepo):
    def test_full_sha_base_resolves(self):
        self.commit_file("a.txt", "one\ntwo\n")
        out = run_gather(self.repo, self.env, [self.first]).stdout
        self.assertNotIn("NO_BASE", out)
        self.assertNotIn("WARN_BASE_ARG_IGNORED", out)
        self.assertIn("REF=%s" % self.first, out)
        self.assertIn("+two", out)

    def test_tag_base_resolves(self):
        self.commit_file("a.txt", "one\ntwo\n")
        _git(self.repo, "tag", "v1.0", self.first, env=self.env)
        out = run_gather(self.repo, self.env, ["v1.0"]).stdout
        self.assertNotIn("NO_BASE", out)
        self.assertIn("REF=v1.0", out)
        self.assertIn("+two", out)

    def test_leading_dash_argument_is_ignored_as_free_text(self):
        self.commit_file("a.txt", "one\ntwo\n")
        out = run_gather(self.repo, self.env, ["-x"]).stdout
        self.assertIn("WARN_BASE_ARG_IGNORED=-x", out)
        self.assertIn("REF=main", out)

    def test_unknown_name_still_reports_no_base(self):
        self.commit_file("a.txt", "one\ntwo\n")
        out = run_gather(self.repo, self.env, ["no-such-base"]).stdout
        self.assertIn("NO_BASE=no-such-base", out)


class TestDiffSizeCaps(_FeatureRepo):
    @staticmethod
    def _lines(n):
        return "".join("line %05d %s\n" % (i, "x" * 30) for i in range(n))

    def test_diff_over_80000_bytes_fans_out_with_top_files_summary(self):
        self.commit_file("big.txt", self._lines(3000))
        self.commit_file("small.txt", self._lines(5))
        out = run_gather(self.repo, self.env).stdout
        self.assertIn("MODE=FAN_OUT", out)
        lines = out.splitlines()
        idx = lines.index("== TOP FILES (lines changed, top 15) ==")
        self.assertEqual(lines[idx + 1], "3000\tbig.txt")
        self.assertEqual(lines[idx + 2], "5\tsmall.txt")

    def test_diff_under_80000_bytes_still_uses_read_mode(self):
        self.commit_file("mid.txt", self._lines(1200))
        out = run_gather(self.repo, self.env).stdout
        self.assertIn("MODE=READ", out)
        self.assertNotIn("FAN_OUT", out)


if __name__ == "__main__":
    unittest.main()
