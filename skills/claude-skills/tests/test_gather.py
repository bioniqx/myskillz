"""Black-box tests for git-diff-summary/scripts/gather.sh."""
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "git-diff-summary"
GATHER = SKILL_DIR / "scripts" / "gather.sh"
SKILL_MD = SKILL_DIR / "SKILL.md"

BASE_ENV = {
    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "t@example.com",
}


def _git(repo, *args, env):
    subprocess.run(["git", *args], cwd=str(repo), env=env, check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)


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


def run_gather(repo, env, args=None, tmpdir=None):
    full_env = dict(env)
    full_env["GDS_NO_FETCH"] = "1"
    if tmpdir is not None:
        full_env["TMPDIR"] = str(tmpdir)
    cmd = ["bash", str(GATHER)] + (args or [])
    return subprocess.run(cmd, cwd=str(repo), env=full_env,
                           capture_output=True, text=True, timeout=20)


class TestGatherFailed(unittest.TestCase):
    """Criterion: mktemp failure prints GATHER_FAILED and exits 0 (never cancels the skill)."""

    def test_unwritable_tmpdir_prints_marker_and_exits_zero(self):
        root = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(root), ignore_errors=True)
        repo, env = make_repo(root)
        env = dict(env)
        env["TMPDIR"] = str(root / "no-such-parent-dir" / "deeper")
        result = run_gather(repo, env)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "GATHER_FAILED (mktemp)")


class TestFewerGitCalls(unittest.TestCase):
    """Criterion: a no-fetch run computes merge-base once and lists untracked files once."""

    def _instrumented_env(self, root, env):
        real_git = shutil.which("git")
        bindir = root / "bin"
        bindir.mkdir()
        logfile = root / "git.calls.log"
        wrapper = bindir / "git"
        wrapper.write_text(
            "#!/bin/sh\n"
            "printf '%%s\\n' \"$*\" >> '%s'\n"
            "exec '%s' \"$@\"\n" % (logfile, real_git)
        )
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
        new_env = dict(env)
        new_env["PATH"] = str(bindir) + os.pathsep + env["PATH"]
        return new_env, logfile

    def test_no_fetch_run_calls_merge_base_and_ls_files_once_each(self):
        root = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(root), ignore_errors=True)
        repo, env = make_repo(root)
        _git(repo, "update-ref", "refs/heads/feature", "HEAD", env=env)
        _git(repo, "symbolic-ref", "HEAD", "refs/heads/feature", env=env)
        (repo / "a.txt").write_text("one\ntwo\n")
        _git(repo, "add", "a.txt", env=env)
        _git(repo, "commit", "-q", "-m", "feat", env=env)
        (repo / "untracked.txt").write_text("hi\n")

        inst_env, logfile = self._instrumented_env(root, env)
        tmp = root / "gathertmp"
        tmp.mkdir()
        result = run_gather(repo, inst_env, tmpdir=tmp)
        self.assertEqual(result.returncode, 0)
        self.assertIn("MODE=INLINE", result.stdout)

        log = logfile.read_text()
        merge_base_calls = sum(1 for line in log.splitlines() if re.search(r"(^| )merge-base( |$)", line))
        ls_files_calls = sum(1 for line in log.splitlines() if "ls-files" in line)
        self.assertEqual(merge_base_calls, 1, "git call count (after fix): %r" % log)
        self.assertEqual(ls_files_calls, 1, "git call count (after fix): %r" % log)


class TestExistingScenariosUnchanged(unittest.TestCase):
    """Criterion: output is unchanged on the existing scenarios."""

    def setUp(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(self.root), ignore_errors=True)

    def test_not_a_repo(self):
        plain_dir = self.root / "plain"
        plain_dir.mkdir()
        result = run_gather(plain_dir, dict(os.environ, HOME=str(self.root / "home")))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "NOT_A_REPO")

    def test_branch_ahead(self):
        repo, env = make_repo(self.root)
        _git(repo, "update-ref", "refs/heads/feature", "HEAD", env=env)
        _git(repo, "symbolic-ref", "HEAD", "refs/heads/feature", env=env)
        (repo / "a.txt").write_text("one\ntwo\n")
        _git(repo, "add", "a.txt", env=env)
        _git(repo, "commit", "-q", "-m", "feat", env=env)
        result = run_gather(repo, env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("BRANCH=feature", result.stdout)
        self.assertIn("AHEAD_BEHIND(behind ahead)=0 1", result.stdout)
        self.assertIn("MODE=INLINE", result.stdout)
        self.assertIn("+two", result.stdout)

    def test_uncommitted_only(self):
        repo, env = make_repo(self.root)
        (repo / "a.txt").write_text("one\nchanged\n")
        result = run_gather(repo, env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("UNCOMMITTED=yes (included)", result.stdout)
        self.assertIn("AHEAD_BEHIND(behind ahead)=0 0", result.stdout)
        self.assertIn("+changed", result.stdout)

    def test_untracked_only(self):
        repo, env = make_repo(self.root)
        (repo / "new.txt").write_text("brand new\n")
        result = run_gather(repo, env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("(new, untracked)", result.stdout)
        self.assertIn("+brand new", result.stdout)

    def test_detached_head(self):
        repo, env = make_repo(self.root)
        head_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo), env=env,
                                   capture_output=True, text=True, check=True).stdout.strip()
        _git(repo, "update-ref", "--no-deref", "HEAD", head_sha, env=env)
        result = run_gather(repo, env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("BRANCH=(detached HEAD)", result.stdout)


class TestFilenamesWithSpacesAndUnicode(unittest.TestCase):
    """Edge case: untracked filenames with spaces/unicode."""

    def test_space_and_unicode_filename_included_verbatim(self):
        root = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(root), ignore_errors=True)
        repo, env = make_repo(root)
        name = "an untracked file 混合 名前.txt"
        (repo / name).write_text("hello there\n")
        result = run_gather(repo, env)
        self.assertEqual(result.returncode, 0)
        self.assertIn(name, result.stdout)
        self.assertIn("+hello there", result.stdout)


class TestSkillMdMarkersAndAllowedTools(unittest.TestCase):
    """Criterion: SKILL.md's marker table handles GATHER_FAILED; allowed-tools pins the
    script under ${CLAUDE_SKILL_DIR} and matches the preload invocation byte-for-byte."""

    def setUp(self):
        self.text = SKILL_MD.read_text()

    def test_gather_failed_row_in_marker_table(self):
        self.assertRegex(self.text, r"\|\s*`GATHER_FAILED`\s*\|")

    def test_allowed_tools_pins_script_and_matches_preload(self):
        allowed_line = next(l for l in self.text.splitlines() if l.startswith("allowed-tools:"))
        m = re.search(r"Bash\((bash [^)]*gather\.sh[^)]*)\)", allowed_line)
        self.assertIsNotNone(m, "no pinned gather.sh Bash rule in allowed-tools: %r" % allowed_line)
        pinned_prefix = m.group(1).rstrip("*")
        self.assertIn("${CLAUDE_SKILL_DIR}", pinned_prefix)

        preload_match = re.search(r"```!\s*\n(.*?)\n```", self.text, re.S)
        self.assertIsNotNone(preload_match, "no ```! preload block found")
        preload_line = preload_match.group(1).strip()
        self.assertTrue(
            preload_line.startswith(pinned_prefix),
            "allowed-tools pin %r is not a byte-for-byte prefix of the preload %r" % (pinned_prefix, preload_line),
        )

    def test_description_length(self):
        desc_line = next(l for l in self.text.splitlines() if l.startswith("description:"))
        self.assertLessEqual(len(desc_line) - len("description: "), 1024)


class TestUntrackedNoiseGitSide(unittest.TestCase):
    """Criterion: untracked() classifies noise vs kept with git pathspecs (EXC) and at most
    two ls-files calls, no per-file bash pattern loop; is_noise/NPAT removed."""

    SOURCE = GATHER.read_text()

    def test_is_noise_and_npat_removed_from_source(self):
        self.assertNotIn("is_noise", self.SOURCE)
        self.assertNotIn("NPAT", self.SOURCE)

    def _instrumented_env(self, root, env):
        real_git = shutil.which("git")
        bindir = root / "bin"
        bindir.mkdir()
        logfile = root / "git.calls.log"
        wrapper = bindir / "git"
        wrapper.write_text(
            "#!/bin/sh\n"
            "printf '%%s\\n' \"$*\" >> '%s'\n"
            "exec '%s' \"$@\"\n" % (logfile, real_git)
        )
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
        new_env = dict(env)
        new_env["PATH"] = str(bindir) + os.pathsep + env["PATH"]
        return new_env, logfile

    def test_noise_untracked_file_excluded_with_at_most_two_ls_files_calls(self):
        root = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(root), ignore_errors=True)
        repo, env = make_repo(root)
        (repo / "package-lock.json").write_text('{"secret-noise-marker": 1}\n')
        (repo / "kept.txt").write_text("kept content\n")

        inst_env, logfile = self._instrumented_env(root, env)
        tmp = root / "gathertmp"
        tmp.mkdir()
        result = run_gather(repo, inst_env, tmpdir=tmp)
        self.assertEqual(result.returncode, 0)

        # noise file's content never reaches the diff; kept file's content does
        self.assertNotIn("secret-noise-marker", result.stdout)
        self.assertIn("kept content", result.stdout)

        log = logfile.read_text()
        ls_files_lines = [l for l in log.splitlines() if "ls-files" in l]
        self.assertLessEqual(len(ls_files_lines), 2, "git call count: %r" % log)

    def test_50k_noise_files_under_node_modules_classified_under_one_second(self):
        root = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(root), ignore_errors=True)
        repo, env = make_repo(root)
        nm = repo / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        for i in range(50000):
            (nm / ("f%d.js" % i)).write_text("x")
        (repo / "kept.txt").write_text("kept content\n")

        import time
        t0 = time.time()
        result = run_gather(repo, env)
        elapsed = time.time() - t0
        self.assertEqual(result.returncode, 0)
        self.assertIn("kept content", result.stdout)
        self.assertNotIn("f0.js", result.stdout)
        # generous bound: a per-file bash pattern loop over 50k files x ~29 patterns would take
        # many seconds; git-side pathspec pruning finishes in well under a second.
        self.assertLess(elapsed, 5.0, "gather.sh took %.2fs on 50k noise files" % elapsed)


class TestUntrackedNoiseListed(unittest.TestCase):
    """Criteria: untracked noise paths are listed (capped, collapsed) in NUMSTAT; header restored."""

    def _repo(self):
        root = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(root), ignore_errors=True)
        return (root,) + make_repo(root)

    def test_only_untracked_lockfile_is_only_noise_and_listed(self):
        root, repo, env = self._repo()
        (repo / "package-lock.json").write_text('{"secret-noise-marker": 1}\n')
        result = run_gather(repo, env)
        self.assertEqual(result.returncode, 0)
        self.assertIn("package-lock.json (new, untracked, noise: content skipped)", result.stdout)
        self.assertIn("ONLY_NOISE_OR_BINARY", result.stdout)
        self.assertNotIn("EMPTY_DIFF", result.stdout)
        self.assertNotIn("secret-noise-marker", result.stdout)

    def test_untracked_noise_listing_capped_at_50(self):
        root, repo, env = self._repo()
        (repo / "locks").mkdir()
        for i in range(80):
            (repo / "locks" / ("m%d.min.js" % i)).write_text("x")
        result = run_gather(repo, env)
        listed = [l for l in result.stdout.splitlines() if "noise: content skipped" in l]
        self.assertEqual(len(listed), 50)

    def test_node_modules_collapsed_to_single_entry(self):
        root, repo, env = self._repo()
        nm = repo / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        for i in range(2000):
            (nm / ("f%d.js" % i)).write_text("x")
        result = run_gather(repo, env)
        listed = [l for l in result.stdout.splitlines() if "noise: content skipped" in l]
        self.assertEqual(len(listed), 1, listed)
        self.assertIn("node_modules/", listed[0])
        self.assertNotIn("f0.js", result.stdout)

    def test_nested_noise_collapses_to_outermost_dir(self):
        root, repo, env = self._repo()
        pkg = repo / "node_modules" / "pkg"
        (pkg / "dist").mkdir(parents=True)
        (pkg / "lib").mkdir()
        (pkg / "dist" / "a.js").write_text("x")
        (pkg / "a.min.js").write_text("x")
        (pkg / "a.js.map").write_text("x")
        (pkg / "lib" / "b.js").write_text("x")
        (repo / "package-lock.json").write_text("{}\n")
        result = run_gather(repo, env)
        listed = [l.split("\t")[-1].split(" (")[0] for l in result.stdout.splitlines()
                  if "noise: content skipped" in l]
        self.assertEqual(sorted(listed), ["node_modules/", "package-lock.json"], listed)

    def test_root_lockfile_survives_many_noise_packages(self):
        root, repo, env = self._repo()
        for i in range(60):
            d = repo / "node_modules" / ("p%d" % i) / "dist"
            d.mkdir(parents=True)
            (d / "a.js").write_text("x")
        (repo / "yarn.lock").write_text("# lock\n")
        result = run_gather(repo, env)
        self.assertIn("yarn.lock (new, untracked, noise: content skipped)", result.stdout)

    def test_numstat_header_wording_restored(self):
        root, repo, env = self._repo()
        (repo / "kept.txt").write_text("kept content\n")
        result = run_gather(repo, env)
        self.assertIn("NUMSTAT (+ - path; noise files counted, content excluded)", result.stdout)
        self.assertNotIn("not counted", result.stdout)
        self.assertIn("kept content", result.stdout)

    def test_overflow_marker_after_50_listed_noise_paths(self):
        root, repo, env = self._repo()
        (repo / "locks").mkdir()
        for i in range(80):
            (repo / "locks" / ("m%d.min.js" % i)).write_text("x")
        result = run_gather(repo, env)
        lines = result.stdout.splitlines()
        listed = [l for l in lines if "noise: content skipped" in l]
        self.assertEqual(len(listed), 50)
        overflow = [l for l in lines if l == "... +30 more untracked noise paths"]
        self.assertEqual(len(overflow), 1)
        self.assertEqual(lines.index(overflow[0]), lines.index(listed[-1]) + 1)

    def test_no_overflow_marker_at_or_below_50(self):
        root, repo, env = self._repo()
        (repo / "locks").mkdir()
        for i in range(50):
            (repo / "locks" / ("m%d.min.js" % i)).write_text("x")
        result = run_gather(repo, env)
        self.assertEqual(len([l for l in result.stdout.splitlines() if "noise: content skipped" in l]), 50)
        self.assertNotIn("more untracked noise paths", result.stdout)

    def _exclude_run(self, pattern, noise, kept):
        root, repo, env = self._repo()
        for name in noise + kept:
            (repo / name).write_text("body-of-file\n")
        env = dict(env)
        env["GDS_EXCLUDE"] = pattern
        out = run_gather(repo, env).stdout
        for name in noise:
            self.assertIn("%s (new, untracked, noise: content skipped)" % name, out)
        for name in kept:
            self.assertIn("%s (new, untracked)" % name, out)
            self.assertNotIn("%s (new, untracked, noise" % name, out)

    def test_gds_exclude_plus_and_question_mark_are_glob_literal(self):
        self._exclude_run("a+b?.txt", ["a+bX.txt"], ["aab.txt", "aabX.txt", "ab.txt"])

    def test_gds_exclude_parens_escaped(self):
        self._exclude_run("f(1).txt", ["f(1).txt"], ["f1.txt", "f.txt"])

    def test_gds_exclude_braces_pipe_caret_dollar_escaped(self):
        self._exclude_run("g{2}|h^i$.txt", ["g{2}|h^i$.txt"], ["gg.txt", "h.txt", "g2.txt"])


class TestPreloadQuotesArguments(unittest.TestCase):
    """Criterion: the ```! preload passes "$ARGUMENTS" quoted, so free text never breaks the shell."""

    PRELOAD = 'bash "${CLAUDE_SKILL_DIR}/scripts/gather.sh" "$ARGUMENTS"'

    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.path.realpath(tempfile.mkdtemp()))
        cls.repo, cls.env = make_repo(cls.root)
        cls.env = dict(cls.env)
        cls.env["GDS_NO_FETCH"] = "1"
        cls.text = SKILL_MD.read_text()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.root), ignore_errors=True)

    def _preload_line(self):
        m = re.search(r"```!\s*\n(.*?)\n```", self.text, re.S)
        self.assertIsNotNone(m, "no ```! preload block found")
        return m.group(1).strip()

    def _run(self, arg):
        line = self._preload_line().replace("${CLAUDE_SKILL_DIR}", str(SKILL_DIR)).replace("$ARGUMENTS", arg)
        return subprocess.run(["sh", "-c", line], cwd=str(self.repo), env=self.env,
                              capture_output=True, text=True, timeout=20)

    def test_preload_line_is_exactly_quoted_form(self):
        self.assertEqual(self._preload_line(), self.PRELOAD)

    def test_allowed_tools_still_prefix_matches_preload(self):
        allowed = next(l for l in self.text.splitlines() if l.startswith("allowed-tools:"))
        self.assertIn('Bash(bash "${CLAUDE_SKILL_DIR}/scripts/gather.sh"*)', allowed)
        self.assertTrue(self._preload_line().startswith('bash "${CLAUDE_SKILL_DIR}/scripts/gather.sh"'))

    def test_every_argument_shape_exits_zero_without_syntax_error(self):
        for arg in ["", "main", "what's changed", "(vs main)", "so sánh với main"]:
            r = self._run(arg)
            self.assertEqual(r.returncode, 0, "arg %r: %s" % (arg, r.stderr))
            self.assertNotIn("syntax error", r.stderr.lower(), "arg %r" % arg)
            self.assertNotIn("unexpected", r.stderr.lower(), "arg %r" % arg)

    def test_main_uses_main_as_base(self):
        r = self._run("main")
        self.assertNotIn("WARN_BASE_ARG_IGNORED", r.stdout)
        direct = run_gather(self.repo, self.env, ["main"])
        self.assertEqual(r.stdout, direct.stdout)

    def test_empty_argument_same_as_no_argument(self):
        r = self._run("")
        direct = run_gather(self.repo, self.env)
        self.assertEqual(r.stdout, direct.stdout)
        self.assertNotIn("WARN_BASE_ARG_IGNORED", r.stdout)

    def test_free_text_warns_and_continues(self):
        r = self._run("so sánh với main")
        self.assertIn("WARN_BASE_ARG_IGNORED=so sánh với main", r.stdout)
        self.assertIn("REF", r.stdout)


if __name__ == "__main__":
    unittest.main()
