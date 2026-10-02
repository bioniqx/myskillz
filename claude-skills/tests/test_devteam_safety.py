"""Black-box + direct-import tests for K01: devteam.py safety hardening.

Covers: remove_worktree() root-guard, --no-renames on footprint/frozen-test diffs,
validate_plan() type checks (including on the retry plan refresh), a strict add-fixes
non-dict spec, and mode-aware claim-header / dirty-tree-rejection text.

Fixtures are real git repos built under the SYSTEM temp dir (never inside this repo or a
worktree) via tempfile.mkdtemp() + os.path.realpath(). The engine itself is exercised as a
subprocess (matching selftest.sh's own black-box style); the pure functions (path_matches,
validate_plan, remove_worktree, add_fixes_from_text) are exercised via direct import since
they need no git state at all.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

DEVTEAM_PATH = str(Path(__file__).resolve().parents[1] / "claude-dev-team-v3.2" / "scripts" / "devteam.py")

spec = importlib.util.spec_from_file_location("devteam_under_test", DEVTEAM_PATH)
dt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dt)


def run_dt(args, cwd, env=None):
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    return subprocess.run([sys.executable, DEVTEAM_PATH] + args, cwd=str(cwd),
                           capture_output=True, text=True, env=full_env, timeout=60)


def new_repo():
    """A fresh, disposable git repo under the system temp dir (realpath'd)."""
    d = Path(os.path.realpath(tempfile.mkdtemp()))
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=d, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=d, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=d, check=True)
    return d


def commit_all(d, msg):
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)
    subprocess.run(["git", "commit", "-q", "-m", msg], cwd=d, check=True)


PLAN_TMPL = """# plan
```json
%s
```
"""


class TestPathMatches(unittest.TestCase):
    """Criterion: path_matches strips only leading './' prefixes."""

    def test_dotenv_does_not_match_env(self):
        self.assertFalse(dt.path_matches(".env", "env"))

    def test_dotgithub_does_not_match_github_prefix(self):
        self.assertFalse(dt.path_matches(".github/x", "github/"))

    def test_leading_dot_slash_still_stripped(self):
        # the intended behaviour: repeated leading "./" IS still normalised away
        self.assertTrue(dt.path_matches("./src/a.py", "src/a.py"))
        self.assertTrue(dt.path_matches("src/a.py", "./src/a.py"))


class TestRemoveWorktreeRootGuard(unittest.TestCase):
    """Criterion: remove_worktree(root, wt) is a no-op when realpath(wt) == realpath(root)."""

    def test_noop_when_wt_equals_root(self):
        root = new_repo()
        (root / "f").write_text("x")
        commit_all(root, "init")
        try:
            dt.remove_worktree(str(root), str(root))
        except Exception:
            pass  # the unguarded bug destroys the checkout and then crashes on a missing cwd;
                  # the assertions below are what actually pins the behaviour down.
        self.assertTrue((root / ".git").exists(), "the integration checkout's .git must survive")
        self.assertTrue(root.exists(), "the integration checkout itself must survive")

    def test_noop_when_wt_is_a_symlinked_alias_of_root(self):
        # Edge case: claim worktree path given via a symlinked parent (e.g. /tmp -> /private/tmp
        # on macOS). remove_worktree must compare realpaths, not raw strings.
        real_root = new_repo()
        (real_root / "f").write_text("x")
        commit_all(real_root, "init")
        alias_parent = Path(tempfile.mkdtemp())  # NOT realpath'd: may itself be a symlink alias
        alias = alias_parent / "alias"
        os.symlink(real_root, alias)
        dt.remove_worktree(str(real_root), str(alias))
        self.assertTrue((real_root / ".git").exists(), "the integration checkout's .git must survive")


class TestValidatePlanTypes(unittest.TestCase):
    """Criterion: validate_plan rejects with a clean DevteamError (no traceback, no state
    written): non-str id, non-list or non-str-element deps/files/criteria."""

    def base_slice(self, **over):
        s = {"id": "S1", "title": "t", "files": ["a.py"], "criteria": ["c"], "deps": [], "risk": "low"}
        s.update(over)
        return {"request": "r", "commands": {"test": "none"}, "slices": [s]}

    def assert_rejected_cleanly(self, plan):
        try:
            dt.validate_plan(plan)
        except dt.DevteamError:
            return  # correct: a clean, typed rejection
        except Exception as e:  # pragma: no cover - this IS the bug we're pinning down
            self.fail(f"validate_plan crashed with {type(e).__name__} instead of a clean DevteamError: {e}")
        self.fail("validate_plan accepted a malformed plan instead of rejecting it")

    def test_non_str_id_rejected(self):
        self.assert_rejected_cleanly(self.base_slice(id=1, deps=[1]))

    def test_non_list_files_rejected(self):
        self.assert_rejected_cleanly(self.base_slice(files="a.py"))

    def test_non_str_element_files_rejected(self):
        self.assert_rejected_cleanly(self.base_slice(files=[1, 2]))

    def test_non_list_criteria_rejected(self):
        self.assert_rejected_cleanly(self.base_slice(criteria="works"))

    def test_non_str_element_criteria_rejected(self):
        self.assert_rejected_cleanly(self.base_slice(criteria=[1, 2]))

    def test_non_list_deps_rejected(self):
        self.assert_rejected_cleanly(self.base_slice(deps=5))

    def test_numeric_id_1_with_matching_numeric_deps_1_rejected(self):
        # Edge case: types must be checked even when id and deps coincidentally "match" by value.
        self.assert_rejected_cleanly(self.base_slice(id=1, deps=[1]))


class TestAddFixesStrictNonDict(unittest.TestCase):
    """Criterion: strict add-fixes with a non-dict spec exits with a clean DevteamError message."""

    def test_non_dict_spec_raises_devteam_error_not_attribute_error(self):
        st = {"slices": {}}
        text = '```json\n{"fixes": ["not-a-dict"]}\n```'
        try:
            dt.add_fixes_from_text(st, text, strict=True)
        except dt.DevteamError:
            return
        except Exception as e:
            self.fail(f"add_fixes_from_text(strict=True) crashed with {type(e).__name__} "
                      f"instead of a clean DevteamError: {e}")
        self.fail("add_fixes_from_text(strict=True) silently accepted a non-dict fix spec")


class EngineFixture(unittest.TestCase):
    """Shared helpers for full-engine (subprocess) tests."""

    def make_repo_with_plan(self, slices, profile="balanced", extra_files=None):
        repo = new_repo()
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "src" / ".keep").write_text("")
        (repo / "tests" / ".keep").write_text("")
        for rel, content in (extra_files or {}).items():
            p = repo / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        commit_all(repo, "init")
        plan = {
            "request": "K01 safety fixtures", "profile": profile,
            "commands": {"test": "none", "test_file": "none"},
            "slices": slices,
        }
        planp = repo / "plan.md"
        planp.write_text(PLAN_TMPL % json.dumps(plan))
        r = run_dt(["init", "plan.md"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return repo

    def add_worktree_and_claim(self, repo, sid, wt_name):
        r = run_dt(["dispatch", sid], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        subprocess.run(["git", "worktree", "add", "-q", f".claude/worktrees/{wt_name}",
                         "-b", f"worktree-{wt_name}", "HEAD"], cwd=repo, check=True)
        wt = repo / ".claude" / "worktrees" / wt_name
        r = run_dt(["claim", sid], wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return wt, r.stdout


class TestGitMvFootprintEscape(EngineFixture):
    """Criterion: a slice that `git mv`s a file from outside its footprint into its footprint
    is rejected at integrate (the deleted original is detected)."""

    def test_mv_outside_file_into_footprint_is_caught(self):
        repo = self.make_repo_with_plan(
            [{"id": "MV1", "title": "mv", "files": ["src/mv1.js", "tests/mv1.test.js"],
              "risk": "low", "criteria": ["works"]}],
            extra_files={"src/outside.js": "function outside(){ return 1; }\n" * 3})
        wt, _ = self.add_worktree_and_claim(repo, "MV1", "w1")
        (wt / "tests" / "mv1.test.js").write_text('test("mv1", () => { assert.equal(1, 1); });\n')
        r = run_dt(["commit-red", "MV1"], wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # Move a file that was NEVER in MV1's footprint into a footprint path, unmodified
        # (high similarity => git's default rename detection pairs it with the deletion), and
        # commit it directly (as a careless/compromised agent bypassing commit-green would) —
        # `integrate` is the safety net of last resort and must still catch it on its own.
        subprocess.run(["git", "mv", "src/outside.js", "src/mv1.js"], cwd=wt, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "raw green"], cwd=wt, check=True)
        r = run_dt(["integrate", "MV1"], repo)
        self.assertIn("footprint", r.stdout.lower() + r.stderr.lower(),
                      f"the deleted outside file must be caught as a footprint violation; got: {r.stdout}{r.stderr}")
        self.assertIn("src/outside.js", r.stdout + r.stderr,
                      f"the rejection must name the file that was moved from outside the footprint; got: {r.stdout}{r.stderr}")

    def test_mv_with_low_similarity_content_is_still_caught(self):
        # Edge case: rename with similarity < 50% (git's own heuristic would not pair these
        # even without --no-renames) — this must be, and already is, rejected either way.
        repo = self.make_repo_with_plan(
            [{"id": "MV2", "title": "mv2", "files": ["src/mv2.js", "tests/mv2.test.js"],
              "risk": "low", "criteria": ["works"]}],
            extra_files={"src/outside2.js": "a\nb\nc\nd\ne\nf\ng\nh\n"})
        wt, _ = self.add_worktree_and_claim(repo, "MV2", "w2")
        (wt / "tests" / "mv2.test.js").write_text('test("mv2", () => { assert.equal(1, 1); });\n')
        r = run_dt(["commit-red", "MV2"], wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        subprocess.run(["git", "rm", "-q", "src/outside2.js"], cwd=wt, check=True)
        (wt / "src" / "mv2.js").write_text("totally unrelated new content\nxyz\n123\n")
        subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "raw green"], cwd=wt, check=True)
        r = run_dt(["integrate", "MV2"], repo)
        self.assertIn("src/outside2.js", r.stdout + r.stderr)


class TestFrozenTestRenameRejected(EngineFixture):
    """Criterion: renaming a frozen test is rejected."""

    def test_renamed_frozen_test_is_rejected(self):
        repo = self.make_repo_with_plan(
            [{"id": "RN1", "title": "rn1",
              "files": ["src/rn1.js", "tests/rn1.test.js", "tests/rn1_renamed.test.js"],
              "risk": "low", "criteria": ["works"]}])
        wt, _ = self.add_worktree_and_claim(repo, "RN1", "w3")
        (wt / "tests" / "rn1.test.js").write_text('test("rn1", () => { assert.equal(1, 1); });\n')
        r = run_dt(["commit-red", "RN1"], wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        subprocess.run(["git", "mv", "tests/rn1.test.js", "tests/rn1_renamed.test.js"], cwd=wt, check=True)
        (wt / "src" / "rn1.js").write_text("module.exports = 1;\n")
        subprocess.run(["git", "add", "-A"], cwd=wt, check=True)
        r = run_dt(["commit-green", "RN1"], wt)
        if r.returncode != 0:   # rejected early: commit-green restores frozen tests
            self.assertIn("frozen test files were modified", r.stdout + r.stderr)
            return
        r = run_dt(["integrate", "RN1"], repo)
        out = r.stdout + r.stderr
        self.assertTrue("tests-modified" in out or "REJECTED" in out,
                         f"renaming a frozen test must be rejected; got: {out}")


class TestModeAwareClaimAndDirtyRejection(EngineFixture):
    """Criterion: the claim header and the dirty-tree rejection name the helpers of the
    claimed mode (WORK: commit-work; FAST: commit-fast)."""

    def test_work_mode_names_commit_work(self):
        repo = self.make_repo_with_plan(
            [{"id": "WK1", "title": "wk1", "kind": "chore", "files": ["src/chore.txt"],
              "risk": "low", "criteria": ["works"], "verify": "true"}],
            extra_files={"src/chore.txt": "before\n"})
        wt, claim_out = self.add_worktree_and_claim(repo, "WK1", "w4")
        self.assertIn("commit-work", claim_out,
                      f"a WORK-mode claim header must name commit-work; got: {claim_out}")
        (wt / "src" / "chore.txt").write_text("dirty, uncommitted\n")
        r = run_dt(["integrate", "WK1"], repo)
        out = r.stdout + r.stderr
        self.assertIn("commit-work", out,
                      f"the dirty-tree rejection for a WORK-mode slice must name commit-work; got: {out}")

    def test_fast_mode_names_commit_fast(self):
        repo = self.make_repo_with_plan(
            [{"id": "SPK1", "title": "spk1", "files": ["src/spk1.js", "tests/spk1.test.js"],
              "risk": "low", "criteria": ["works"]}],
            profile="spike")
        wt, claim_out = self.add_worktree_and_claim(repo, "SPK1", "w5")
        self.assertIn("commit-fast", claim_out,
                      f"a FAST-mode claim header must name commit-fast; got: {claim_out}")
        (wt / "src" / "spk1.js").write_text("dirty, uncommitted\n")
        r = run_dt(["integrate", "SPK1"], repo)
        out = r.stdout + r.stderr
        self.assertIn("commit-fast", out,
                      f"the dirty-tree rejection for a FAST-mode slice must name commit-fast; got: {out}")


class TestRetryRefreshesTypeChecked(EngineFixture):
    """Criterion: validate_plan's type checks run on the retry plan refresh too."""

    def test_retry_with_malformed_plan_refresh_fails_cleanly(self):
        repo = self.make_repo_with_plan(
            [{"id": "RT1", "title": "rt1", "files": ["src/rt1.js", "tests/rt1.test.js"],
              "risk": "low", "criteria": ["works"]}])
        wt, _ = self.add_worktree_and_claim(repo, "RT1", "w6")
        r = run_dt(["fail", "RT1", "--why", "testing retry refresh"], repo)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        state_before = json.loads((repo / ".claude" / "dev-team" / "state.json").read_text())
        # Simulate a plan.md edited (by hand or by a reviewer) with a malformed footprint type
        # for the retried slice — this must be rejected the same way init would reject it.
        bad_plan = {
            "request": "K01 safety fixtures", "profile": "balanced",
            "commands": {"test": "none", "test_file": "none"},
            "slices": [{"id": "RT1", "title": "rt1", "files": 5, "risk": "low", "criteria": ["works"]}],
        }
        planmd = PLAN_TMPL % json.dumps(bad_plan)
        (repo / "plan.md").write_text(planmd)
        state_dir = repo / ".claude" / "dev-team"
        (state_dir / "plan.md").write_text(planmd)
        r = run_dt(["retry", "RT1"], repo)
        self.assertNotEqual(r.returncode, 0,
                             "retry must refuse a malformed plan.md refresh, not silently adopt it")
        self.assertNotIn("Traceback", r.stderr,
                          f"retry must fail with a clean DevteamError, not a raw traceback; got: {r.stderr}")
        state_after = json.loads((repo / ".claude" / "dev-team" / "state.json").read_text())
        self.assertEqual(state_before["slices"]["RT1"]["files"], state_after["slices"]["RT1"]["files"],
                          "a rejected retry must not have written corrupted state")


if __name__ == "__main__":
    unittest.main()
