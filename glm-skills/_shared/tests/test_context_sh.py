import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CONTEXT_SH = os.path.join(HERE, "..", "..", "glm-brainstorming", "scripts", "context.sh")


def run_context(cwd):
    return subprocess.run(["sh", CONTEXT_SH], cwd=cwd, capture_output=True,
                          text=True, timeout=60)


def git(repo, *args):
    subprocess.run(["git", "-C", repo] + list(args), check=True,
                   capture_output=True, text=True)


def make_repo(extra_top_level=0):
    repo = tempfile.mkdtemp(prefix="ctx_sh_")
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "test")
    for rel in ("alpha.txt", "docs/readme.md", "src/main.py"):
        path = os.path.join(repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("x\n")
    for i in range(extra_top_level):
        with open(os.path.join(repo, "fill_%02d.txt" % i), "w", encoding="utf-8") as fh:
            fh.write("x\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "initial commit")
    return repo


class TestScriptShape(unittest.TestCase):
    def script_text(self):
        with open(CONTEXT_SH, encoding="utf-8") as fh:
            return fh.read()

    def test_git_ls_files_runs_exactly_once(self):
        self.assertEqual(self.script_text().count("git ls-files"), 1)

    def test_hot_dir_log_is_backgrounded_guarded_and_joined(self):
        text = self.script_text()
        self.assertIn("|| true &", text)
        self.assertRegex(text, r"(?m)^\s*wait\b")
        self.assertTrue(text.rstrip().endswith("exit 0"))


class TestOutputContract(unittest.TestCase):
    def setUp(self):
        self.repo = make_repo()

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_exits_zero_and_keeps_line_order(self):
        proc = run_context(self.repo)
        self.assertEqual(proc.returncode, 0)
        lines = proc.stdout.splitlines()
        git_line = next(i for i, l in enumerate(lines) if l.startswith("git: "))
        commits = next(i for i, l in enumerate(lines) if l == "recent_commits:")
        hot = next(i for i, l in enumerate(lines) if l.startswith("hot_dirs_30d:"))
        files = next(i for i, l in enumerate(lines) if l.startswith("files:"))
        self.assertLess(git_line, commits)
        self.assertLess(commits, hot)
        self.assertLess(hot, files)

    def test_small_repo_counts_and_names_tracked_files(self):
        proc = run_context(self.repo)
        self.assertIn("tracked=3", proc.stdout)
        self.assertIn("modified=0", proc.stdout)
        files_line = next(l for l in proc.stdout.splitlines() if l.startswith("files:"))
        self.assertEqual(files_line, "files: alpha.txt docs/readme.md src/main.py ")

    def test_hot_dirs_line_groups_top_level_dirs(self):
        proc = run_context(self.repo)
        hot = next(l for l in proc.stdout.splitlines() if l.startswith("hot_dirs_30d:"))
        self.assertIn("docs(1)", hot)
        self.assertIn("src(1)", hot)
        self.assertIn(".(1)", hot)

    def test_recent_commits_lists_the_last_commit(self):
        proc = run_context(self.repo)
        self.assertIn("initial commit", proc.stdout)

    def test_two_runs_are_byte_identical(self):
        first = run_context(self.repo).stdout
        second = run_context(self.repo).stdout
        self.assertEqual(first, second)

    def test_empty_repo_keeps_the_files_line_shape(self):
        empty = tempfile.mkdtemp(prefix="ctx_sh_empty_")
        git(empty, "init", "-q")
        try:
            proc = run_context(empty)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("tracked=0", proc.stdout)
            files_line = next(l for l in proc.stdout.splitlines() if l.startswith("files:"))
            self.assertEqual(files_line, "files: ")
        finally:
            shutil.rmtree(empty, ignore_errors=True)


class TestTreeBranch(unittest.TestCase):
    def test_many_files_repo_prints_tree_not_files(self):
        repo = make_repo(extra_top_level=60)
        try:
            proc = run_context(repo)
            self.assertEqual(proc.returncode, 0)
            lines = proc.stdout.splitlines()
            self.assertFalse(any(l.startswith("files:") for l in lines))
            tree = next(l for l in lines if l.startswith("tree:"))
            self.assertIn(".(61)", tree)
            self.assertIn("docs/(1)", tree)
            self.assertIn("src/(1)", tree)
        finally:
            shutil.rmtree(repo, ignore_errors=True)


class TestOutsideRepo(unittest.TestCase):
    def test_exits_zero_outside_a_git_repo(self):
        plain = tempfile.mkdtemp(prefix="ctx_sh_plain_")
        try:
            proc = run_context(plain)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("git: none", proc.stdout)
        finally:
            shutil.rmtree(plain, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
