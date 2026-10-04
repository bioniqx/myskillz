"""Parity tests for oc_guard.py: engine-subcommand deny, quoted-argument scan, write patterns."""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[2] / "oc-dev-team" / "scripts" / "oc_guard.py"
_SPEC = importlib.util.spec_from_file_location("oc_guard_port_under_test", str(GUARD))
G = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(G)

ENGINE = "/skill/scripts/oc_devteam.py"


def run_oc(payload):
    r = subprocess.run([sys.executable, str(GUARD), "oc"], input=json.dumps(payload),
                       capture_output=True, text=True)
    return r.returncode, r.stdout


def decision(out):
    if not out.strip():
        return "", ""
    hso = json.loads(out)["hookSpecificOutput"]
    return hso["permissionDecision"], hso["permissionDecisionReason"]


class GuardPortTests(unittest.TestCase):
    def setUp(self):
        self.wt = Path(tempfile.mkdtemp()).resolve()
        sd = self.wt / ".oc-slice"
        sd.mkdir()
        (sd / "id").write_text("S1\n")
        (sd / "footprint").write_text("src/\n")
        self.addCleanup(shutil.rmtree, str(self.wt), True)

    def shell(self, command):
        rc, out = run_oc({"tool": "shell", "args": {"command": command, "workdir": str(self.wt)},
                          "cwd": str(self.wt), "role": "programmer"})
        self.assertEqual(rc, 0)
        return decision(out)

    def test_path_matches_strips_only_a_literal_dot_slash(self):
        self.assertFalse(G.path_matches(".env", "env"))
        self.assertFalse(G.path_matches(".claude/x", "claude/"))
        self.assertTrue(G.path_matches("./src/a.py", "src"))

    def test_lane_cannot_run_engine_reset(self):
        verdict, reason = self.shell(f"python3 {ENGINE} reset --yes")
        self.assertEqual(verdict, "deny")
        self.assertIn("drives the engine", reason)

    def test_lane_cannot_run_finish_force_behind_a_wrapper(self):
        verdict, reason = self.shell(f"timeout 60 python3 {ENGINE} finish --force")
        self.assertEqual(verdict, "deny")
        self.assertIn("drives the engine", reason)

    def test_lane_may_still_claim_and_report(self):
        for cmd in (f"python3 {ENGINE} claim S1 --worktree {self.wt}",
                    f"python3 {ENGINE} report S1 --file {self.wt}/.oc-slice/report.md"):
            _, reason = self.shell(cmd)
            self.assertNotIn("drives the engine", reason)

    def test_quoted_argument_is_not_mistaken_for_a_push(self):
        _, reason = self.shell("grep 'git push' README.md")
        self.assertNotIn("Blocked", reason)

    def test_unquoted_push_is_still_denied(self):
        verdict, reason = self.shell("git push origin main")
        self.assertEqual(verdict, "deny")
        self.assertIn("Blocked", reason)

    def test_worktree_list_is_readable_but_add_is_not(self):
        _, reason = self.shell("git worktree list")
        self.assertNotIn("integration/history", reason)
        verdict, reason = self.shell("git worktree add ../x")
        self.assertEqual(verdict, "deny")
        self.assertIn("integration/history", reason)

    def test_python_write_text_to_run_state_is_denied(self):
        verdict, reason = self.shell(
            "python3 -c \"open('.opencode/oc-dev-team/slices/S1.done').write_text('x')\"")
        self.assertEqual(verdict, "deny")
        self.assertIn("run state", reason)

    def test_python_write_bytes_to_slice_metadata_is_denied(self):
        verdict, reason = self.shell(
            "python3 -c \"import pathlib; pathlib.Path('.oc-slice/red').write_bytes(b'x')\"")
        self.assertEqual(verdict, "deny")
        self.assertIn("dev-team metadata", reason)

    def test_write_marker_resets_the_stop_counter(self):
        sd = self.wt / ".oc-slice"
        (sd / "stop_blocks").write_text("2")
        G.write_marker(self.wt, sd, "S1", "done")
        self.assertFalse((sd / "stop_blocks").exists())


class GuardPortF5Tests(GuardPortTests):
    """Remaining spec-listed guard fixes (stop gate, write patterns, allow-list, read-only role)."""

    def git(self, *args):
        r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=str(self.wt),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def stop(self, report):
        r = subprocess.run([sys.executable, str(GUARD), "stop"], capture_output=True, text=True,
                           input=json.dumps({"cwd": str(self.wt), "last_assistant_message": report}))
        return r.returncode, r.stderr

    def ro(self, command, role="reviewer"):
        rc, out = run_oc({"tool": "shell", "args": {"command": command, "workdir": str(self.wt)},
                          "cwd": str(self.wt), "role": role})
        self.assertEqual(rc, 0)
        return decision(out)

    def init_repo(self, subject, mode, kind):
        self.git("init", "-q")
        (self.wt / ".gitignore").write_text(".oc-slice/\n")
        (self.wt / "src").mkdir()
        (self.wt / "src" / "a.py").write_text("x = 1\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", subject)
        sd = self.wt / ".oc-slice"
        (sd / "base").write_text(self.git("rev-parse", "HEAD") + "\n")
        (sd / "mode").write_text(mode + "\n")
        (sd / "kind").write_text(kind + "\n")

    REPORT = ("## Status: Complete\n## Gate: python3 -m unittest -v -> Ran 3 tests in 0.1s\nOK\n"
              "## Notes: none\n")

    def test_stale_feat_subject_does_not_count_as_committed_when_base_is_set(self):
        self.init_repo("feat(S1): left over from an earlier run", "work", "chore")
        rc, err = self.stop(self.REPORT)
        self.assertEqual(rc, 2)
        self.assertIn("nothing committed yet", err)

    def test_new_commit_after_base_counts_as_committed(self):
        self.init_repo("feat(S1): left over from an earlier run", "work", "chore")
        (self.wt / "src" / "a.py").write_text("x = 2\n")
        self.git("commit", "-q", "-am", "chore(S1): real work")
        rc, err = self.stop(self.REPORT)
        self.assertEqual(rc, 0, err)

    def test_renamed_frozen_test_file_is_reported(self):
        self.init_repo("init", "work", "refactor")
        (self.wt / "tests").mkdir()
        (self.wt / "tests" / "test_a.py").write_text("def test_a():\n    assert 1 == 1\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "test(S1): RED")
        base = self.git("rev-parse", "HEAD")
        (self.wt / ".oc-slice" / "base").write_text(base + "\n")
        self.git("mv", "tests/test_a.py", "src/a_moved.py")
        self.git("commit", "-q", "-m", "refactor(S1): move")
        rc, err = self.stop(self.REPORT)
        self.assertEqual(rc, 2)
        self.assertIn("a REFACTOR slice changed test files: tests/test_a.py", err)

    def test_open_write_to_run_state_is_denied(self):
        verdict, reason = self.shell(
            "python3 -c \"open('.opencode/oc-dev-team/slices/S1.done','w').close()\"")
        self.assertEqual(verdict, "deny")
        self.assertIn("run state", reason)

    def test_open_write_to_slice_metadata_is_denied(self):
        verdict, reason = self.shell("python3 -c \"open('.oc-slice/red','w').close()\"")
        self.assertEqual(verdict, "deny")
        self.assertIn("dev-team metadata", reason)

    def test_open_for_reading_run_state_is_not_blocked_as_a_write(self):
        _, reason = self.shell("python3 -c \"print(open('.opencode/oc-dev-team/state.json','r').read())\"")
        self.assertNotIn("Blocked", reason)

    def test_git_merge_base_and_worktree_list_are_preapproved(self):
        for cmd in ("git merge-base HEAD main", "git worktree list"):
            verdict, reason = self.shell(cmd)
            self.assertEqual(verdict, "allow", cmd)
            self.assertIn("read-only git", reason)

    def test_metachar_inside_quotes_does_not_defeat_preapproval(self):
        verdict, reason = self.shell("grep -n 'a;b' README.md")
        self.assertEqual(verdict, "allow")
        self.assertIn("read-only command", reason)

    def test_substitution_inside_double_quotes_is_still_meta(self):
        verdict, _ = self.shell('grep -n "$(id)" README.md')
        self.assertNotEqual(verdict, "allow")

    def test_prefix_match_compares_canonical_script_paths(self):
        real = self.wt / "real"
        real.mkdir()
        link = self.wt / "link"
        link.symlink_to(real)
        (real / "t.py").write_text("")
        argv = ["python3", str(link / "t.py"), "claim", "S1"]
        self.assertEqual(G.prefix_match(argv, [f"python3 {real}/t.py claim"]), f"python3 {real}/t.py claim")
        self.assertIsNone(G.prefix_match(argv, [f"python3 {real}/other.py claim"]))

    def test_edit_through_a_symlinked_worktree_path_is_judged_on_its_real_path(self):
        alias = self.wt.parent / (self.wt.name + "-alias")
        alias.symlink_to(self.wt)
        self.addCleanup(alias.unlink)
        rc, out = run_oc({"tool": "edit", "args": {"filePath": str(alias / "src" / "a.py")},
                          "cwd": str(self.wt), "role": "programmer"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "allow")
        rc, out = run_oc({"tool": "edit", "args": {"filePath": str(alias / "other" / "a.py")},
                          "cwd": str(self.wt), "role": "programmer"})
        self.assertEqual(decision(out)[0], "deny")

    def test_readonly_role_denies_package_managers_and_make_install(self):
        for cmd in ("brew install jq", "apt-get install jq", "apt install jq", "dnf install jq",
                    "yum remove jq", "apk upgrade jq", "pacman upgrade jq", "snap install jq",
                    "pipx uninstall x", "bundle install", "make install", "make uninstall"):
            verdict, reason = self.ro(cmd)
            self.assertEqual(verdict, "deny", cmd)
            self.assertIn("Read-only role", reason, cmd)

    def test_readonly_role_tool_name_as_argument_is_not_denied(self):
        for cmd in ("grep -rn mv src", "ls | grep dd", "grep -rn install src"):
            verdict, reason = self.ro(cmd)
            self.assertEqual(verdict, "allow", cmd)

    def test_readonly_role_still_denies_a_mutating_tool_at_command_position(self):
        for cmd in ("rm -rf src", "ls && mv a b", "timeout 5 rm x", "sh -c 'rm x'", "ls | xargs rm"):
            verdict, reason = self.ro(cmd)
            self.assertEqual(verdict, "deny", cmd)
            self.assertIn("Read-only role", reason, cmd)


if __name__ == "__main__":
    unittest.main()
