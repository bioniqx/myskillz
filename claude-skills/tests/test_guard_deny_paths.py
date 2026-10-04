"""Black-box tests for the guard.py denial paths (T03).

One test per path: a programmer editing another slice's worktree, an edit outside the
slice footprint, git pointed at another checkout (`-C` / `--git-dir` / `GIT_DIR`),
`git checkout <ref>`, and the read-only roles (edit-ro / bash-ro).

guard.py runs as a subprocess with the hook JSON on stdin; fixtures live under the
system temp dir (resolved with realpath) so the parent-directory walk for `.slice/`
never meets this repository.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD_PY = Path(__file__).resolve().parents[1] / "claude-dev-team-v3.2" / "scripts" / "guard.py"


def run_guard(mode, payload, cwd):
    return subprocess.run([sys.executable, str(GUARD_PY), mode], input=json.dumps(payload),
                          cwd=str(cwd), capture_output=True, text=True, timeout=15)


def decision_of(result):
    out = result.stdout.strip()
    if not out:
        return None, None
    hso = json.loads(out).get("hookSpecificOutput") or {}
    return hso.get("permissionDecision"), hso.get("permissionDecisionReason")


def make_slice_root(path, sid, footprint=(), kind="code", mode="slice"):
    sd = Path(path) / ".slice"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "id").write_text(sid + "\n")
    (sd / "kind").write_text(kind + "\n")
    (sd / "mode").write_text(mode + "\n")
    if footprint:
        (sd / "footprint").write_text("\n".join(footprint) + "\n")
    return Path(path)


class GuardCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(os.path.realpath(tmp.name))

    def edit(self, wt, rel_or_abs):
        path = str(rel_or_abs)
        return run_guard("edit", {"tool_input": {"file_path": path}, "cwd": str(wt)}, wt)

    def bash(self, wt, command, mode="bash"):
        return run_guard(mode, {"tool_input": {"command": command}, "cwd": str(wt)}, wt)


class EditDenialTests(GuardCase):
    def test_edit_inside_another_slices_worktree_is_denied(self):
        mine = make_slice_root(self.base / "wt_a", "A1", footprint=["src/a.py"])
        other = make_slice_root(self.base / "wt_b", "B1", footprint=["src/b.py"])
        r = self.edit(mine, other / "src" / "b.py")
        decision, reason = decision_of(r)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(decision, "deny", r.stdout)
        self.assertIn("another slice's worktree", reason)

    def test_edit_outside_the_footprint_is_denied(self):
        wt = make_slice_root(self.base / "wt", "A1", footprint=["src/a.py"])
        r = self.edit(wt, wt / "src" / "b.py")
        decision, reason = decision_of(r)
        self.assertEqual(decision, "deny", r.stdout)
        self.assertIn("outside your slice footprint", reason)

    def test_edit_inside_the_footprint_is_allowed(self):
        wt = make_slice_root(self.base / "wt", "A1", footprint=["src/a.py"])
        r = self.edit(wt, wt / "src" / "a.py")
        decision, reason = decision_of(r)
        self.assertEqual(decision, "allow", r.stdout)
        self.assertIn("inside the slice footprint", reason)


class GitRedirectAndCheckoutTests(GuardCase):
    def test_git_pointed_at_another_checkout_is_denied(self):
        wt = make_slice_root(self.base / "wt", "A1", footprint=["src/a.py"])
        for cmd in ("git -C ../other status",
                    "git --git-dir=../other/.git log",
                    "git --work-tree ../other diff",
                    "GIT_DIR=../other/.git git status"):
            with self.subTest(cmd=cmd):
                r = self.bash(wt, cmd)
                decision, reason = decision_of(r)
                self.assertEqual(decision, "deny", r.stdout)
                self.assertIn("points git at another checkout", reason)

    def test_plain_read_only_git_in_the_worktree_is_not_denied(self):
        wt = make_slice_root(self.base / "wt", "A1", footprint=["src/a.py"])
        decision, _ = decision_of(self.bash(wt, "git status --short"))
        self.assertNotEqual(decision, "deny")

    def test_git_checkout_of_a_ref_is_denied(self):
        wt = make_slice_root(self.base / "wt", "A1", footprint=["src/a.py"])
        r = self.bash(wt, "git checkout main")
        decision, reason = decision_of(r)
        self.assertEqual(decision, "deny", r.stdout)
        self.assertIn("would leave your slice branch", reason)

    def test_git_checkout_restoring_a_file_is_not_denied(self):
        wt = make_slice_root(self.base / "wt", "A1", footprint=["src/a.py"])
        decision, _ = decision_of(self.bash(wt, "git checkout -- src/a.py"))
        self.assertNotEqual(decision, "deny")


class ReadOnlyRoleTests(GuardCase):
    def test_read_only_role_cannot_edit_source(self):
        r = self.edit_ro(self.base / "src" / "app.py")
        decision, reason = decision_of(r)
        self.assertEqual(decision, "deny", r.stdout)
        self.assertIn("read-only", reason)

    def test_read_only_role_may_write_its_own_report(self):
        report = self.base / ".claude" / "dev-team" / "reviews" / "r1.report.md"
        decision, reason = decision_of(self.edit_ro(report))
        self.assertEqual(decision, "allow")
        self.assertIn("report", reason)

    def test_only_the_team_leader_may_write_the_plan(self):
        plan = self.base / ".claude" / "dev-team" / "plan.md"
        leader, _ = decision_of(self.edit_ro(plan, agent="claude-team-leader"))
        reviewer, _ = decision_of(self.edit_ro(plan, agent="claude-code-reviewer"))
        self.assertEqual(leader, "allow")
        self.assertEqual(reviewer, "deny")

    def test_read_only_shell_denies_mutating_commands(self):
        for cmd in ("rm -rf build", "git commit -m x", "echo hi > out.txt", "git -C ../x status"):
            with self.subTest(cmd=cmd):
                r = self.bash(self.base, cmd, mode="bash-ro")
                decision, reason = decision_of(r)
                self.assertEqual(decision, "deny", r.stdout)
                self.assertIn("Read-only role", reason)

    def test_read_only_shell_allows_read_only_git(self):
        decision, _ = decision_of(self.bash(self.base, "git status", mode="bash-ro"))
        self.assertEqual(decision, "allow")

    def edit_ro(self, path, agent="claude-code-reviewer"):
        payload = {"tool_input": {"file_path": str(path)}, "cwd": str(self.base), "agent_type": agent}
        return run_guard("edit-ro", payload, self.base)


if __name__ == "__main__":
    unittest.main()
