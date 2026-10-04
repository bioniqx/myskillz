"""Parity tests for the glm guard.py against the original v3.2 guard. The guard runs as a subprocess
(JSON on stdin) for hook behaviour and is imported for pure helpers. Fixtures live under the system temp dir."""
import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD_PATH = str(Path(__file__).resolve().parents[2] / "dev-team-glm" / "scripts" / "guard.py")


def load_guard():
    spec = importlib.util.spec_from_file_location("glm_guard_under_test", GUARD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


G = load_guard()


class GuardCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.wt = self.tmp / "wt"
        (self.wt / ".slice").mkdir(parents=True)
        (self.wt / ".slice" / "id").write_text("S1\n")
        (self.wt / ".slice" / "footprint").write_text("src/\ntests/\n")
        (self.wt / ".slice" / "mode").write_text("slice\n")

    def run_guard(self, mode, command, cwd=None):
        payload = {"cwd": str(cwd or self.wt), "tool_input": {"command": command}}
        env = dict(os.environ, HOME=str(self.tmp))
        r = subprocess.run([sys.executable, GUARD_PATH, mode], input=json.dumps(payload), text=True,
                           capture_output=True, env=env, timeout=30)
        return r.stdout

    def denied(self, mode, command):
        return '"permissionDecision": "deny"' in self.run_guard(mode, command)


class PathMatchesTests(unittest.TestCase):
    def test_only_a_literal_dot_slash_is_stripped(self):
        self.assertFalse(G.path_matches(".env", "env"))
        self.assertFalse(G.path_matches(".claude/x", "claude/"))
        self.assertTrue(G.path_matches("./src/a.py", "src/a.py"))


class LaneEngineDenyTests(GuardCase):
    def test_engine_subcommands_are_denied_from_a_lane(self):
        self.assertTrue(self.denied("bash", "python3 /x/scripts/devteam.py reset --yes"))
        self.assertTrue(self.denied("bash", "python3 /x/scripts/devteam.py finish --force"))
        self.assertTrue(self.denied("bash", "timeout 5 python3 /x/scripts/devteam.py next; true"))

    def test_lane_helpers_are_not_denied(self):
        self.assertFalse(self.denied("bash", "python3 /x/scripts/devteam.py claim S1"))
        self.assertFalse(self.denied("bash", "grep -n reset /x/scripts/devteam.py"))

    def test_quoted_git_push_is_not_a_push(self):
        self.assertFalse(self.denied("bash", "grep 'git push' README.md"))
        self.assertTrue(self.denied("bash", "git push origin main"))
        self.assertTrue(self.denied("bash", 'bash -c "git push"'))


class MetadataWritePatternTests(GuardCase):
    def test_slice_and_run_state_writes_are_denied(self):
        self.assertTrue(self.denied("bash", "python3 -c \"open('.slice/red','w')\""))
        self.assertTrue(self.denied("bash", "python3 -c \"from pathlib import Path; Path('.slice/red').write_text('x')\""))
        self.assertTrue(self.denied("bash", "python3 -c \"open('.claude/dev-team/state.json','w')\""))
        self.assertTrue(self.denied("bash", "echo x > .claude/dev-team/state.json"))


class ReadOnlyRoleTests(GuardCase):
    def test_merge_base_and_worktree_list_are_readable(self):
        self.assertFalse(self.denied("bash-ro", "git merge-base HEAD main"))
        self.assertFalse(self.denied("bash-ro", "git worktree list"))
        self.assertTrue(self.denied("bash-ro", "git worktree add ../x"))

    def test_mutating_tool_is_judged_at_command_position(self):
        self.assertFalse(self.denied("bash-ro", "grep -rn mv src"))
        self.assertFalse(self.denied("bash-ro", "ls | grep dd"))
        self.assertTrue(self.denied("bash-ro", "ls && rm x"))
        self.assertEqual(G.ro_mutating_tool("grep -rn install src"), "")
        self.assertEqual(G.ro_mutating_tool("ls && rm x"), "rm")

    def test_package_managers_and_make_are_denied(self):
        self.assertTrue(self.denied("bash-ro", "apt remove foo"))
        self.assertTrue(self.denied("bash-ro", "brew upgrade"))
        self.assertTrue(self.denied("bash-ro", "make install"))


class WriteCapableTests(unittest.TestCase):
    def test_hardened_write_forms_are_never_approved(self):
        self.assertTrue(G.write_capable(["awk", 'BEGIN{system("x")}']))
        self.assertTrue(G.write_capable(["awk", "-f", "prog.awk"]))
        self.assertTrue(G.write_capable(["sed", "-n", "w out.txt"]))
        self.assertTrue(G.write_capable(["git", "diff", "--out=x"]))
        self.assertTrue(G.write_capable(["sort", "--out", "x"]))
        self.assertFalse(G.write_capable(["grep", "-n", "x", "f"]))

    SED_WRITE_SCRIPTS = (r"\%s%w /tmp/a%b%c", r"\%s%e touch%a%b", r"s/a\/b/w /tmp/x", "s/a/b/;w /tmp/x")

    def test_sed_w_e_hidden_in_s_lookalikes_is_write_capable(self):
        for script in self.SED_WRITE_SCRIPTS:
            self.assertTrue(G.write_capable(["sed", script, "in.txt"]), script)
            self.assertIsNone(G.bash_allow_reason(f"sed '{script}' in.txt", None, [], [], readonly=True), script)

    def test_whole_plain_sed_s_command_stays_allowed(self):
        self.assertFalse(G.write_capable(["sed", "s/we/us/g", "in.txt"]))
        self.assertFalse(G.write_capable(["sed", "-n", "s|we|us|gp", "in.txt"]))
        self.assertTrue(G.bash_allow_reason("sed 's/we/us/g' in.txt", None, [], [], readonly=True))

    def test_write_exec_form_delegates_to_write_capable(self):
        self.assertTrue(G.write_exec_form(["awk", 'BEGIN{system("x")}']))

    def test_canon_argv_resolves_symlinked_absolute_paths(self):
        tmp = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(tmp), True)
        (tmp / "real").mkdir()
        os.symlink(tmp / "real", tmp / "link")
        self.assertEqual(G.canon_argv([str(tmp / "link"), "plain"]), [str(tmp / "real"), "plain"])
        pinned = f"python3 {tmp / 'real' / 'd.py'}"
        self.assertEqual(G.prefix_match(["python3", str(tmp / "link" / "d.py"), "claim"], [pinned]), pinned)

    def test_segment_allowed_refuses_sed_in_place_forms(self):
        for flag in ("-i", "-ni", "-nI", "-i.bak", "--in-place", "--in-pl", "--in-place=.bak"):
            self.assertIsNone(G.segment_allowed(["sed", flag, "s/a/b/", "f"], [], []), flag)

    def test_segment_allowed_keeps_plain_sed_read_only(self):
        self.assertEqual(G.segment_allowed(["sed", "-n", "1p", "f"], [], []), "read-only command")


class StopGateTests(GuardCase):
    def test_write_marker_resets_stop_blocks(self):
        sd = self.wt / ".slice"
        (sd / "stop_blocks").write_text("2")
        G.write_marker(self.wt, sd, "S1", "done")
        self.assertFalse((sd / "stop_blocks").exists())

    def test_ensure_red_cache_is_scoped_to_the_slice_base(self):
        src = inspect.getsource(G.ensure_red_cache)
        self.assertIn('f"{base}..HEAD"', src)

    def test_committed_test_is_bound_to_base(self):
        src = inspect.getsource(G.guard_stop)
        self.assertIn("head != base", src)
        self.assertNotIn("not committed and not (base and head and head != base)", src)

    def test_edit_guard_skips_the_red_probe_for_red_work_fast(self):
        src = inspect.getsource(G.guard_edit)
        self.assertIn('mode not in ("red", "work", "fast")', src)
        self.assertIn("os.path.realpath", src)


class DiffFlagsTests(unittest.TestCase):
    def test_diffs_ignore_renames(self):
        self.assertIn('"--no-renames"', inspect.getsource(G.guard_stop))


if __name__ == "__main__":
    unittest.main()
