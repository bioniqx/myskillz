"""Black-box tests for brainstorming-6.3/scripts/context.sh (K17).

Runs the real script via subprocess against tempfile.mkdtemp() fixtures
(realpath'd, outside the repo/worktree) so guard.py/devteam.py never see them.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(REPO_ROOT, "claude-skills", "brainstorming-6.3", "scripts", "context.sh")


def run_script(cwd, env=None, interpreter="sh", timeout=30):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    proc = subprocess.run(
        [interpreter, SCRIPT],
        cwd=cwd,
        env=full_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout.decode("utf-8", "replace"), proc.stderr.decode("utf-8", "replace")


def git(args, cwd, env=None):
    full_env = dict(os.environ)
    full_env["GIT_AUTHOR_NAME"] = "t"
    full_env["GIT_AUTHOR_EMAIL"] = "t@t.t"
    full_env["GIT_COMMITTER_NAME"] = "t"
    full_env["GIT_COMMITTER_EMAIL"] = "t@t.t"
    if env:
        full_env.update(env)
    subprocess.run(["git"] + args, cwd=cwd, env=full_env, check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def mkrepo():
    d = os.path.realpath(tempfile.mkdtemp(prefix="ctxtest-"))
    git(["init", "-q"], d)
    return d


def extract_field(stdout, name):
    for line in stdout.splitlines():
        if line.startswith(name + ":"):
            return line[len(name) + 1:].strip()
    return None


class NpmDepsOneLineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="ctxtest-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_pkg(self, content):
        with open(os.path.join(self.tmp, "package.json"), "w") as f:
            f.write(content)

    def test_empty_deps_one_line(self):
        self._write_pkg('{"name": "x", "dependencies": {}}')
        rc, out, err = run_script(self.tmp)
        self.assertEqual(rc, 0, err)
        deps = extract_field(out, "npm_deps")
        self.assertIsNotNone(deps)
        self.assertEqual(deps.strip(), "")

    def test_one_dep_one_line(self):
        self._write_pkg('{"name": "x", "dependencies": { "react": "^18" }}')
        rc, out, err = run_script(self.tmp)
        self.assertEqual(rc, 0, err)
        deps = extract_field(out, "npm_deps")
        self.assertIsNotNone(deps)
        self.assertIn("react", deps)

    def test_multi_dep_one_line(self):
        self._write_pkg('{"dependencies": { "react": "^18", "lodash": "^4" }}')
        rc, out, err = run_script(self.tmp)
        self.assertEqual(rc, 0, err)
        deps = extract_field(out, "npm_deps")
        self.assertIn("react", deps)
        self.assertIn("lodash", deps)

    def test_no_dependencies_key(self):
        # Edge case: package.json exists but has no dependencies field at all.
        self._write_pkg('{"name": "x", "version": "1.0.0"}')
        rc, out, err = run_script(self.tmp)
        self.assertEqual(rc, 0, err)
        deps = extract_field(out, "npm_deps")
        self.assertIsNotNone(deps)
        self.assertEqual(deps.strip(), "")


class HotDirsCwdScopeTests(unittest.TestCase):
    def setUp(self):
        self.repo = mkrepo()

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_hot_dirs_scoped_to_cwd(self):
        sub = os.path.join(self.repo, "sub")
        nested = os.path.join(sub, "nested")
        other = os.path.join(self.repo, "otherdir")
        os.makedirs(nested)
        os.makedirs(other)
        with open(os.path.join(nested, "a.txt"), "w") as f:
            f.write("a")
        with open(os.path.join(other, "b.txt"), "w") as f:
            f.write("b")
        git(["add", "-A"], self.repo)
        git(["commit", "-q", "-m", "seed"], self.repo)

        rc, out, err = run_script(sub)
        self.assertEqual(rc, 0, err)
        hot = extract_field(out, "hot_dirs_30d")
        self.assertIsNotNone(hot)
        self.assertIn("nested", hot)
        self.assertNotIn("otherdir", hot)


class ExitsCleanTests(unittest.TestCase):
    def _check(self, cwd, env=None, interpreter="sh"):
        rc, out, err = run_script(cwd, env=env, interpreter=interpreter)
        self.assertEqual(rc, 0, err)
        lines = out.splitlines()
        self.assertLessEqual(len(lines), 55, "too many lines: %d" % len(lines))

    def test_non_git_dir(self):
        d = os.path.realpath(tempfile.mkdtemp(prefix="ctxtest-"))
        try:
            self._check(d)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_empty_repo(self):
        d = mkrepo()
        try:
            self._check(d)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_bare_repo(self):
        d = os.path.realpath(tempfile.mkdtemp(prefix="ctxtest-"))
        try:
            git(["init", "-q", "--bare"], d)
            self._check(d)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_home_like_dir(self):
        d = os.path.realpath(tempfile.mkdtemp(prefix="ctxtest-"))
        try:
            self._check(d, env={"HOME": d})
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_under_dash(self):
        dash = shutil.which("dash")
        interpreter = dash if dash else "sh"
        d = os.path.realpath(tempfile.mkdtemp(prefix="ctxtest-"))
        try:
            self._check(d, interpreter=interpreter)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_cwd_with_spaces(self):
        parent = os.path.realpath(tempfile.mkdtemp(prefix="ctxtest-"))
        d = os.path.join(parent, "dir with spaces")
        os.makedirs(d)
        try:
            self._check(d)
        finally:
            shutil.rmtree(parent, ignore_errors=True)


class HugeCommitPerfTests(unittest.TestCase):
    """Uses git plumbing (one shared blob, git mktree) to build a 150k-entry
    commit without touching the index or working tree, so setup stays fast
    and `git status` has nothing to scan."""

    @classmethod
    def setUpClass(cls):
        cls.repo = mkrepo()
        blob = subprocess.run(
            ["git", "hash-object", "-w", "--stdin"],
            cwd=cls.repo, input=b"x", stdout=subprocess.PIPE, check=True,
        ).stdout.decode().strip()
        n = 150000
        lines = "\n".join("100644 blob %s\tfile%d" % (blob, i) for i in range(n)) + "\n"
        tree = subprocess.run(
            ["git", "mktree"], cwd=cls.repo, input=lines.encode(),
            stdout=subprocess.PIPE, check=True,
        ).stdout.decode().strip()
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t.t",
                   GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t.t")
        commit = subprocess.run(
            ["git", "commit-tree", tree, "-m", "huge"],
            cwd=cls.repo, env=env, stdout=subprocess.PIPE, check=True,
        ).stdout.decode().strip()
        subprocess.run(["git", "update-ref", "refs/heads/master", commit],
                        cwd=cls.repo, check=True)
        subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/master"],
                        cwd=cls.repo, check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.repo, ignore_errors=True)

    def test_completes_quickly_on_huge_commit(self):
        start = time.time()
        rc, out, err = run_script(self.repo, timeout=25)
        elapsed = time.time() - start
        self.assertEqual(rc, 0, err)
        # Regression guard: the head -n 20000 cap keeps awk from ever
        # walking all 150k `--name-only` lines.
        self.assertLess(elapsed, 15.0, "took %.2fs, expected the head -n 20000 cap to keep this fast" % elapsed)


if __name__ == "__main__":
    unittest.main()
