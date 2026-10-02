"""oc_debug_tool.py experiment: worktree completeness (SD4) and patch order (SD5)."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOL = (Path(__file__).resolve().parents[2]
        / "oc-systematic-debugging" / "scripts" / "oc_debug_tool.py")


def load_tool():
    spec = importlib.util.spec_from_file_location("debug_tool_experiment_under_test", str(TOOL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DT = load_tool()


def git(repo, *args):
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
                    "-c", "commit.gpgsign=false"] + list(args),
                   cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class ExperimentRepo(unittest.TestCase):
    """A throwaway git repo, a separate caller cwd and a private TMPDIR."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="sdexp-test."))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        self.caller = os.path.join(self.tmp, "caller")
        self.tmpdir = os.path.join(self.tmp, "t")
        for d in (self.repo, self.caller, self.tmpdir):
            os.makedirs(d)
        git(self.repo, "init", "-q")
        self.write("flag.txt", "a\nbroken\n")
        self.write(".gitignore", "node_modules/\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "init")

    def write(self, rel, text):
        p = Path(self.repo, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def run_exp(self, spec):
        Path(self.caller, "spec.json").write_text(json.dumps(spec))
        out, err = io.StringIO(), io.StringIO()
        old = os.getcwd()
        os.chdir(self.caller)
        try:
            with mock.patch.dict(os.environ, {"TMPDIR": self.tmpdir}):
                with contextlib.redirect_stdout(out):
                    with contextlib.redirect_stderr(err):
                        rc = DT.main(["experiment", "--spec", "spec.json",
                                      "--dir", self.repo, "-j", "2"])
        finally:
            os.chdir(old)
        return rc, out.getvalue() + "\n" + err.getvalue()


class WorktreeCompletenessTest(ExperimentRepo):
    """SD4: untracked files and ignored dependency dirs reach every arm."""

    def test_untracked_file_reaches_worktree(self):
        self.write("data/fixture.txt", "needed by the repro\n")
        rc, out = self.run_exp([{
            "id": "h1", "hypothesis": "FLAG fixes it",
            "cmd": 'test -f data/fixture.txt || exit 3; test "$FLAG" = fixed',
            "env": {"FLAG": "fixed"}, "expect": "treatment_passes"}])
        self.assertIn("[CONFIRMED] h1", out)
        self.assertEqual(rc, 0)

    def test_ignored_dependency_dir_is_linked_by_default(self):
        self.write("node_modules/dep/index.js", "module.exports = 1\n")
        rc, out = self.run_exp([{
            "id": "h1", "hypothesis": "FLAG fixes it",
            "cmd": 'test -f node_modules/dep/index.js || exit 3; test "$FLAG" = fixed',
            "env": {"FLAG": "fixed"}, "expect": "treatment_passes"}])
        self.assertIn("[CONFIRMED] h1", out)
        self.assertEqual(rc, 0)

    def test_control_not_reproducing_is_inconclusive(self):
        rc, out = self.run_exp([{
            "id": "h1", "hypothesis": "FLAG fixes it",
            "cmd": "true", "env": {"FLAG": "fixed"}, "expect": "treatment_passes"}])
        self.assertIn("[INCONCLUSIVE] h1", out)
        self.assertIn("control did not reproduce", out)
        self.assertEqual(rc, 1)


class PatchOrderTest(ExperimentRepo):
    """SD5: patch_file resolves against the caller's cwd; a patch that already
    contains the WIP is applied on HEAD instead of on top of the WIP."""

    ON_HEAD = ("--- a/flag.txt\n+++ b/flag.txt\n@@ -1,2 +1,2 @@\n"
               " a\n-broken\n+fixed\n")
    CONTAINS_WIP = ("--- a/flag.txt\n+++ b/flag.txt\n@@ -1,2 +1,2 @@\n"
                    "-a\n-broken\n+a-wip\n+fixed\n")
    ON_WIP = ("--- a/flag.txt\n+++ b/flag.txt\n@@ -1,2 +1,2 @@\n"
              " a-wip\n-broken\n+fixed\n")

    def spec(self, cmd):
        return [{"id": "h1", "hypothesis": "the patch fixes it", "cmd": cmd,
                 "patch_file": "fix.diff", "expect": "treatment_passes"}]

    def test_relative_patch_file_resolves_against_caller_cwd(self):
        Path(self.caller, "fix.diff").write_text(self.ON_HEAD)
        rc, out = self.run_exp(self.spec("grep -qx fixed flag.txt"))
        self.assertIn("[CONFIRMED] h1", out)
        self.assertEqual(rc, 0)

    def test_missing_patch_file_is_rejected_up_front(self):
        rc, out = self.run_exp(self.spec("grep -qx fixed flag.txt"))
        self.assertEqual(rc, 2)
        self.assertIn("patch_file", out)
        self.assertIn(os.path.join(self.caller, "fix.diff"), out)

    def test_patch_that_contains_wip_is_applied_on_head(self):
        self.write("flag.txt", "a-wip\nbroken\n")
        Path(self.caller, "fix.diff").write_text(self.CONTAINS_WIP)
        rc, out = self.run_exp(self.spec("grep -qx a-wip flag.txt && grep -qx fixed flag.txt"))
        self.assertIn("[CONFIRMED] h1", out)
        self.assertIn("already contains the WIP", out)
        self.assertEqual(rc, 0)

    def test_patch_on_top_of_wip_still_applies(self):
        self.write("flag.txt", "a-wip\nbroken\n")
        Path(self.caller, "fix.diff").write_text(self.ON_WIP)
        rc, out = self.run_exp(self.spec("grep -qx a-wip flag.txt && grep -qx fixed flag.txt"))
        self.assertIn("[CONFIRMED] h1", out)
        self.assertNotIn("already contains the WIP", out)
        self.assertEqual(rc, 0)


class TemplateTest(unittest.TestCase):
    def test_template_prints_a_valid_spec(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = DT.main(["experiment", "--template"])
        self.assertEqual(rc, 0)
        self.assertEqual([h["id"] for h in json.loads(out.getvalue())], ["h1", "h2", "h3"])


if __name__ == "__main__":
    unittest.main()
