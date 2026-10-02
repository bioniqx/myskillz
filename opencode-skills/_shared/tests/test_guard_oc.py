import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[2] / "oc-dev-team" / "scripts" / "oc_guard.py"


def run_oc(payload):
    r = subprocess.run([sys.executable, str(GUARD), "oc"], input=json.dumps(payload),
                       capture_output=True, text=True)
    return r.returncode, r.stdout


def decision(out):
    if not out.strip():
        return "", ""
    hso = json.loads(out)["hookSpecificOutput"]
    return hso["permissionDecision"], hso["permissionDecisionReason"]


class GuardOcTest(unittest.TestCase):
    def setUp(self):
        self.wt = Path(tempfile.mkdtemp()).resolve()
        sd = self.wt / ".oc-slice"
        sd.mkdir()
        (sd / "id").write_text("S1\n")
        (sd / "footprint").write_text("src/\n")

    def tearDown(self):
        shutil.rmtree(self.wt, ignore_errors=True)

    def oc(self, tool, args, role="programmer"):
        # a programmer's shell call must name its worktree; the explicit-workdir tests pass their own
        if tool in ("bash", "shell") and isinstance(args, dict) and "workdir" not in args:
            args = dict(args, workdir=str(self.wt))
        return run_oc({"tool": tool, "args": args, "cwd": str(self.wt), "role": role})

    def test_no_role_is_silent_allow(self):
        rc, out = self.oc("write", {"filePath": "docs/x.md", "content": "x"}, role="")
        self.assertEqual((rc, out), (0, ""))

    def test_unknown_tool_is_silent_allow(self):
        rc, out = self.oc("read", {"filePath": "docs/x.md"})
        self.assertEqual((rc, out), (0, ""))

    def test_bad_json_is_silent_allow(self):
        r = subprocess.run([sys.executable, str(GUARD), "oc"], input="not json",
                           capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_programmer_edit_inside_footprint_allows(self):
        rc, out = self.oc("edit", {"filePath": "src/a.py", "oldString": "a", "newString": "b"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out), ("allow", "dev-team: `src/a.py` is inside the slice footprint"))

    def test_programmer_lite_role_is_gone(self):
        rc, out = self.oc("edit", {"filePath": "src/a.py", "oldString": "a", "newString": "b"},
                          role="programmer-lite")
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("This role is read-only", reason)

    def test_programmer_write_outside_footprint_denies(self):
        rc, out = self.oc("write", {"filePath": str(self.wt / "docs" / "x.md"), "content": "x"})
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("`docs/x.md` is outside your slice footprint", reason)

    def test_programmer_patch_first_deny_wins(self):
        patch = ("*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n"
                 "*** Add File: docs/b.md\n+hi\n*** End Patch\n")
        rc, out = self.oc("apply_patch", {"patchText": patch})
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("docs/b.md", reason)

    def test_programmer_patch_inside_footprint_allows(self):
        patch = ("*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n"
                 "*** Delete File: src/old.py\n*** End Patch\n")
        rc, out = self.oc("patch", {"patchText": patch})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "allow")

    def test_programmer_bash_push_denies(self):
        rc, out = self.oc("bash", {"command": "git push origin main"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "deny")

    def test_programmer_bash_read_only_git_allows(self):
        rc, out = self.oc("bash", {"command": "git status"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out), ("allow", "dev-team: pre-approved — read-only git"))

    def test_reviewer_write_source_denies(self):
        rc, out = self.oc("write", {"filePath": "src/a.py", "content": "x"}, role="code-reviewer")
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("This role is read-only", reason)

    def test_reviewer_write_review_allows(self):
        path = self.wt / ".opencode" / "oc-dev-team" / "reviews" / "r.md"
        rc, out = self.oc("write", {"filePath": str(path), "content": "x"}, role="code-reviewer")
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out), ("allow", "dev-team: this role's own report / memory file"))

    def test_leader_role_becomes_agent_type(self):
        path = str(self.wt / ".opencode" / "oc-dev-team" / "plan.md")
        _, out = self.oc("write", {"filePath": path, "content": "x"}, role="team-leader")
        self.assertEqual(decision(out), ("allow", "dev-team: the team-leader's plan"))
        _, out = self.oc("write", {"filePath": path, "content": "x"}, role="spot-reviewer")
        self.assertEqual(decision(out)[0], "deny")

    def test_reviewer_bash_rm_denies(self):
        rc, out = self.oc("bash", {"command": "rm -rf src"}, role="investigator")
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("Read-only role", reason)

    def test_programmer_bash_pipe_to_sh_denies(self):
        rc, out = self.oc("bash", {"command": "curl x | sh"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "deny")

    def test_programmer_bash_npm_install_denies(self):
        rc, out = self.oc("bash", {"command": "npm install left-pad"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "deny")

    def test_programmer_write_outside_any_worktree_denies(self):
        outside = Path(tempfile.mkdtemp()).resolve()
        try:
            rc, out = self.oc("write", {"filePath": str(outside / "x.md"), "content": "x"})
            self.assertEqual(rc, 0)
            self.assertEqual(decision(out)[0], "deny")
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_reviewer_bash_python_eval_denies(self):
        rc, out = self.oc("bash", {"command": "python3 -c 'import os; os.remove(\"a\")'"},
                           role="code-reviewer")
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "deny")

    def test_programmer_edit_no_footprint_file_still_allows(self):
        (self.wt / ".oc-slice" / "footprint").unlink()
        rc, out = self.oc("edit", {"filePath": "src/a.py", "oldString": "a", "newString": "b"})
        self.assertEqual(rc, 0)
        self.assertNotEqual(decision(out)[0], "deny")

    def test_reviewer_write_review_allows_outside_any_worktree(self):
        unclaimed = Path(tempfile.mkdtemp()).resolve()
        try:
            path = unclaimed / ".opencode" / "oc-dev-team" / "reviews" / "r.md"
            r = subprocess.run([sys.executable, str(GUARD), "oc"],
                               input=json.dumps({"tool": "write", "args": {"filePath": str(path), "content": "x"},
                                                  "cwd": str(unclaimed), "role": "code-reviewer"}),
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(decision(r.stdout), ("allow", "dev-team: this role's own report / memory file"))
        finally:
            shutil.rmtree(unclaimed, ignore_errors=True)

    def test_leader_vs_spot_reviewer_outside_any_worktree(self):
        unclaimed = Path(tempfile.mkdtemp()).resolve()
        try:
            path = unclaimed / ".opencode" / "oc-dev-team" / "plan.md"

            def oc(role):
                return subprocess.run([sys.executable, str(GUARD), "oc"],
                                      input=json.dumps({"tool": "write", "args": {"filePath": str(path), "content": "x"},
                                                         "cwd": str(unclaimed), "role": role}),
                                      capture_output=True, text=True)
            r = oc("team-leader")
            self.assertEqual(decision(r.stdout), ("allow", "dev-team: the team-leader's plan"))
            r = oc("spot-reviewer")
            self.assertEqual(decision(r.stdout)[0], "deny")
        finally:
            shutil.rmtree(unclaimed, ignore_errors=True)

    def test_reviewer_write_source_denies_outside_any_worktree(self):
        unclaimed = Path(tempfile.mkdtemp()).resolve()
        try:
            path = unclaimed / "src" / "a.py"
            r = subprocess.run([sys.executable, str(GUARD), "oc"],
                               input=json.dumps({"tool": "write", "args": {"filePath": str(path), "content": "x"},
                                                  "cwd": str(unclaimed), "role": "code-reviewer"}),
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            verdict, reason = decision(r.stdout)
            self.assertEqual(verdict, "deny")
            self.assertIn("This role is read-only", reason)
        finally:
            shutil.rmtree(unclaimed, ignore_errors=True)

    def test_programmer_write_outside_any_worktree_still_denies_absolute(self):
        outside = Path(tempfile.mkdtemp()).resolve()
        try:
            path = outside / "docs" / "x.md"
            r = subprocess.run([sys.executable, str(GUARD), "oc"],
                               input=json.dumps({"tool": "write", "args": {"filePath": str(path), "content": "x"},
                                                  "cwd": str(outside), "role": "programmer"}),
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0)
            verdict, reason = decision(r.stdout)
            self.assertEqual(verdict, "deny")
            self.assertIn("outside any slice worktree", reason)
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_programmer_shell_push_denies(self):
        rc, out = self.oc("shell", {"command": "git push origin main"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "deny")

    def test_programmer_shell_read_only_git_allows(self):
        rc, out = self.oc("shell", {"command": "git status"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out), ("allow", "dev-team: pre-approved — read-only git"))

    def test_v2_path_key_routes_to_edit_checks(self):
        # the real v2.0.16 edit/write schemas name the file `path`, not `filePath`
        rc, out = self.oc("write", {"path": "src/a.py", "content": "x"})
        self.assertEqual(decision(out), ("allow", "dev-team: `src/a.py` is inside the slice footprint"))
        rc, out = self.oc("edit", {"path": "docs/x.md", "oldString": "a", "newString": "b"})
        self.assertEqual(decision(out)[0], "deny")

    def test_programmer_shell_workdir_outside_worktree_denies(self):
        outside = Path(tempfile.mkdtemp()).resolve()
        try:
            rc, out = self.oc("shell", {"command": "git status", "workdir": str(outside)})
            verdict, reason = decision(out)
            self.assertEqual(verdict, "deny")
            self.assertIn("outside your slice worktree", reason)
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_programmer_shell_workdir_inside_worktree_allows(self):
        (self.wt / "src").mkdir()
        rc, out = self.oc("shell", {"command": "git status", "workdir": "src"})
        self.assertEqual(decision(out)[0], "allow")

    def test_code_mode_execute_denied_for_every_role(self):
        for role in ("programmer", "code-reviewer"):
            with self.subTest(role=role):
                rc, out = self.oc("execute", {"code": "return 1"}, role=role)
                self.assertEqual(decision(out)[0], "deny")

    def test_v2_edit_capable_tools_route_to_edit_checks(self):
        for tool, args in (
            ("edit", {"filePath": "src/a.py", "oldString": "a", "newString": "b"}),
            ("write", {"filePath": "src/a.py", "content": "x"}),
            ("patch", {"patchText": "*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n*** End Patch\n"}),
            ("apply_patch", {"patchText": "*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n*** End Patch\n"}),
        ):
            with self.subTest(tool=tool):
                rc, out = self.oc(tool, args)
                self.assertEqual(rc, 0)
                self.assertEqual(decision(out)[0], "allow")

    def test_v2_edit_capable_tools_deny_outside_footprint(self):
        for tool, args in (
            ("edit", {"filePath": "docs/x.md", "oldString": "a", "newString": "b"}),
            ("write", {"filePath": "docs/x.md", "content": "x"}),
            ("patch", {"patchText": "*** Begin Patch\n*** Add File: docs/x.md\n+hi\n*** End Patch\n"}),
            ("apply_patch", {"patchText": "*** Begin Patch\n*** Add File: docs/x.md\n+hi\n*** End Patch\n"}),
        ):
            with self.subTest(tool=tool):
                rc, out = self.oc(tool, args)
                self.assertEqual(rc, 0)
                verdict, reason = decision(out)
                self.assertEqual(verdict, "deny")
                self.assertIn("docs/x.md", reason)

    def test_guard_oc_function_no_role(self):
        spec = importlib.util.spec_from_file_location("devteam_guard", GUARD)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
            mod.guard_oc({"tool": "bash", "args": {"command": "git push"}, "cwd": str(self.wt), "role": ""})
        self.assertIn(cm.exception.code, (0, None))
        self.assertEqual(buf.getvalue(), "")

    def test_args_json_string_is_parsed(self):
        # v2 `input.repair` can hand the args over as a JSON string instead of an object
        rc, out = self.oc("write", json.dumps({"filePath": "docs/x.md", "content": "x"}))
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("`docs/x.md` is outside your slice footprint", reason)
        rc, out = self.oc("shell", json.dumps({"command": "git push origin main"}))
        self.assertEqual(decision(out)[0], "deny")
        rc, out = self.oc("edit", json.dumps({"filePath": "src/a.py", "oldString": "a", "newString": "b"}))
        self.assertEqual(decision(out), ("allow", "dev-team: `src/a.py` is inside the slice footprint"))

    def test_unparseable_args_deny_in_lane_mode(self):
        for args in ("{not json", "[1, 2]", ["src/a.py"], 7):
            with self.subTest(args=args):
                rc, out = self.oc("write", args)
                self.assertEqual(rc, 0)
                verdict, reason = decision(out)
                self.assertEqual(verdict, "deny")
                self.assertIn("could not be parsed", reason)

    def test_unparseable_args_without_role_stay_silent(self):
        rc, out = self.oc("write", "{not json", role="")
        self.assertEqual((rc, out), (0, ""))

    def test_non_string_shell_fields_deny(self):
        for args in ({"command": 5}, {"command": "git status", "workdir": 5}):
            with self.subTest(args=args):
                rc, out = self.oc("shell", args)
                self.assertEqual(rc, 0)
                verdict, reason = decision(out)
                self.assertEqual(verdict, "deny")
                self.assertIn("needs a string `command`", reason)

    def test_batch_and_question_denied_in_lane_mode(self):
        for tool in ("batch", "question"):
            for role in ("programmer", "code-reviewer"):
                with self.subTest(tool=tool, role=role):
                    rc, out = self.oc(tool, {}, role=role)
                    self.assertEqual(rc, 0)
                    verdict, reason = decision(out)
                    self.assertEqual(verdict, "deny")
                    self.assertIn(f"`{tool}` is disabled in dev-team lanes", reason)

    def test_indented_patch_header_is_checked(self):
        # v2 trims patch lines before applying them, so an indented header is live
        patch = ("*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n"
                 "  *** Add File: docs/b.md\n+hi\n*** End Patch\n")
        rc, out = self.oc("apply_patch", {"patchText": patch})
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("docs/b.md", reason)

    def test_indented_patch_header_denied_for_read_only_role(self):
        patch = "*** Begin Patch\n    *** Update File: src/a.py\n@@\n-x\n+y\n*** End Patch\n"
        rc, out = self.oc("patch", {"patchText": patch}, role="code-reviewer")
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("This role is read-only", reason)

    def test_headerless_patch_denied_for_every_role(self):
        for role in ("programmer", "code-reviewer"):
            with self.subTest(role=role):
                rc, out = self.oc("patch", {"patchText": "@@\n-x\n+y\n"}, role=role)
                self.assertEqual(rc, 0)
                verdict, reason = decision(out)
                self.assertEqual(verdict, "deny")
                self.assertIn("names no file", reason)

    def test_edit_without_path_denied_for_every_role(self):
        for tool, args in (("write", {"content": "x"}),
                           ("edit", {"oldString": "a", "newString": "b"}),
                           ("write", {"filePath": "", "content": "x"})):
            for role in ("programmer", "code-reviewer"):
                with self.subTest(tool=tool, args=args, role=role):
                    rc, out = self.oc(tool, args, role=role)
                    self.assertEqual(rc, 0)
                    verdict, reason = decision(out)
                    self.assertEqual(verdict, "deny")
                    self.assertIn("names no file", reason)

    def test_removed_hook_modes_are_silent_allow(self):
        payload = {"tool_input": {"command": "git push origin main", "file_path": "docs/x.md"},
                   "cwd": str(self.wt), "agent_type": "code-reviewer"}
        for mode in ("edit", "bash", "perm", "edit-ro", "bash-ro"):
            with self.subTest(mode=mode):
                r = subprocess.run([sys.executable, str(GUARD), mode], input=json.dumps(payload),
                                   capture_output=True, text=True)
                self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_guard_module_state_dir(self):
        spec = importlib.util.spec_from_file_location("devteam_guard_surface", GUARD)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.STATE_DIRNAME, ".opencode/oc-dev-team")

    def test_stop_mode_blocks_a_slice_with_no_red_commit(self):
        r = subprocess.run([sys.executable, str(GUARD), "stop"],
                           input=json.dumps({"cwd": str(self.wt), "last_assistant_message": "## Status: Done"}),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("no RED commit", r.stderr)

    def test_stop_mode_outside_a_slice_is_silent_allow(self):
        other = Path(tempfile.mkdtemp()).resolve()
        try:
            r = subprocess.run([sys.executable, str(GUARD), "stop"],
                               input=json.dumps({"cwd": str(other), "last_assistant_message": "done"}),
                               capture_output=True, text=True)
            self.assertEqual((r.returncode, r.stdout), (0, ""))
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_symlinked_cwd_edit_inside_footprint_allows(self):
        linkdir = Path(tempfile.mkdtemp())
        try:
            link = linkdir / "wt"
            link.symlink_to(self.wt)
            for fp in ("src/a.py", str(link / "src" / "a.py")):
                with self.subTest(filePath=fp):
                    rc, out = run_oc({"tool": "edit",
                                      "args": {"filePath": fp, "oldString": "a", "newString": "b"},
                                      "cwd": str(link), "role": "programmer"})
                    self.assertEqual(rc, 0)
                    self.assertEqual(decision(out),
                                     ("allow", "dev-team: `src/a.py` is inside the slice footprint"))
        finally:
            shutil.rmtree(linkdir, ignore_errors=True)

    def test_unapproved_shell_deny_lists_pinned_forms(self):
        (self.wt / ".oc-slice" / "allow").write_text("python3 -m pytest -q\nmake lint\n")
        rc, out = self.oc("shell", {"command": "curl example.com"})
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("Pinned forms from `.oc-slice/allow`: `python3 -m pytest -q`, `make lint`.", reason)

    def test_unapproved_shell_deny_says_when_nothing_is_pinned(self):
        rc, out = self.oc("shell", {"command": "curl example.com"})
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("No commands are pinned for this lane (`.oc-slice/allow` is empty).", reason)


class GuardOcLaneFromInputTest(unittest.TestCase):
    """Lanes run from the main checkout: the edit path or the shell `workdir` picks the slice."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        state = self.root / ".opencode" / "oc-dev-team"
        state.mkdir(parents=True)
        (state / "state.json").write_text("{}")
        self.wt = self.make_slice("S1", "src/")
        self.wt2 = self.make_slice("S2", "docs/")
        self.hint = str(state / "wt") + "/<slice id>"

    def make_slice(self, sid, footprint):
        wt = self.root / ".opencode" / "oc-dev-team" / "wt" / sid
        sd = wt / ".oc-slice"
        sd.mkdir(parents=True)
        (sd / "id").write_text(sid + "\n")
        (sd / "footprint").write_text(footprint + "\n")
        return wt

    def oc(self, tool, args, role="programmer"):
        return decision(run_oc({"tool": tool, "args": args, "cwd": str(self.root), "role": role})[1])

    def test_edit_path_selects_its_slice(self):
        self.assertEqual(self.oc("edit", {"path": str(self.wt / "src" / "a.py"), "oldString": "a", "newString": "b"}),
                         ("allow", "dev-team: `src/a.py` is inside the slice footprint"))
        self.assertEqual(self.oc("write", {"path": str(self.wt2 / "docs" / "x.md"), "content": "x"}),
                         ("allow", "dev-team: `docs/x.md` is inside the slice footprint"))
        verdict, reason = self.oc("write", {"path": str(self.wt2 / "src" / "a.py"), "content": "x"})
        self.assertEqual(verdict, "deny")
        self.assertIn("`src/a.py` is outside your slice footprint (docs/)", reason)

    def test_write_outside_every_worktree_is_denied_naming_the_worktree(self):
        for p in ("src/a.py", str(self.root / "src" / "a.py")):
            with self.subTest(path=p):
                verdict, reason = self.oc("write", {"path": p, "content": "x"})
                self.assertEqual(verdict, "deny")
                self.assertIn("outside any slice worktree", reason)
                self.assertIn(self.hint, reason)

    def test_shell_workdir_selects_its_slice(self):
        (self.wt / "src").mkdir()
        for wd in (self.wt, self.wt / "src", self.wt2):
            with self.subTest(workdir=str(wd)):
                self.assertEqual(self.oc("shell", {"command": "git status", "workdir": str(wd)}),
                                 ("allow", "dev-team: pre-approved — read-only git"))

    def test_shell_workdir_brings_that_slice_footprint(self):
        self.assertEqual(self.oc("shell", {"command": "touch src/new.py", "workdir": str(self.wt)})[0], "allow")
        self.assertEqual(self.oc("shell", {"command": "touch src/new.py", "workdir": str(self.wt2)})[0], "deny")

    def test_programmer_shell_without_workdir_is_denied_naming_the_worktree(self):
        verdict, reason = self.oc("shell", {"command": "git status"})
        self.assertEqual(verdict, "deny")
        self.assertIn("must pass `workdir`", reason)
        self.assertIn(self.hint, reason)

    def test_shell_workdir_outside_every_worktree_is_denied(self):
        verdict, reason = self.oc("shell", {"command": "git status", "workdir": str(self.root)})
        self.assertEqual(verdict, "deny")
        self.assertIn("outside your slice worktree", reason)
        self.assertIn(self.hint, reason)

    def test_read_only_roles_need_no_workdir(self):
        self.assertEqual(self.oc("shell", {"command": "git status"}, role="code-reviewer"),
                         ("allow", "dev-team: pre-approved — read-only git"))
        verdict, reason = self.oc("shell", {"command": "rm -rf src"}, role="code-reviewer")
        self.assertEqual(verdict, "deny")
        self.assertIn("Read-only role", reason)
        review = self.root / ".opencode" / "oc-dev-team" / "reviews" / "r.md"
        self.assertEqual(self.oc("write", {"path": str(review), "content": "x"}, role="code-reviewer"),
                         ("allow", "dev-team: this role's own report / memory file"))


class GuardOcFreshLaneTest(unittest.TestCase):
    """A fresh lane has no .oc-slice/ yet: it may run `claim` for its own worktree and nothing else."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.root, True)
        state = self.root / ".opencode" / "oc-dev-team"
        state.mkdir(parents=True)
        self.script = "/skills/oc-dev-team/scripts/oc_devteam.py"
        (state / "state.json").write_text(json.dumps({"script": self.script}))
        self.fresh = state / "wt" / "S1"
        self.fresh.mkdir(parents=True)
        self.claimed = state / "wt" / "S2"
        (self.claimed / ".oc-slice").mkdir(parents=True)
        (self.claimed / ".oc-slice" / "id").write_text("S2\n")
        (self.claimed / ".oc-slice" / "footprint").write_text("src/\n")

    def oc(self, tool, args):
        return decision(run_oc({"tool": tool, "args": args, "cwd": str(self.root), "role": "programmer"})[1])

    def shell(self, command, workdir=None):
        return self.oc("shell", {"command": command, "workdir": str(workdir or self.fresh)})

    def test_claim_in_unclaimed_worktree_is_allowed(self):
        verdict, _ = self.shell(f"python3 {self.script} claim S1 --worktree {self.fresh}")
        self.assertEqual(verdict, "allow")

    def test_anything_else_in_unclaimed_worktree_is_denied_telling_to_claim(self):
        for cmd in ("git status", "touch src/a.py", f"python3 {self.script} commit-red x",
                    f"python3 {self.script} claim S2 --worktree {self.fresh}"):
            with self.subTest(command=cmd):
                verdict, reason = self.shell(cmd)
                self.assertEqual(verdict, "deny")
                self.assertIn("claim", reason)

    def test_report_md_write_is_allowed_in_claimed_worktree(self):
        for tool in ("write", "edit"):
            with self.subTest(tool=tool):
                verdict, _ = self.oc(tool, {"path": str(self.claimed / ".oc-slice" / "report.md"),
                                            "content": "x", "oldString": "a", "newString": "b"})
                self.assertEqual(verdict, "allow")

    def test_other_slice_metadata_writes_stay_denied(self):
        for name in ("footprint", "allow", "id", "red"):
            with self.subTest(name=name):
                verdict, reason = self.oc("write", {"path": str(self.claimed / ".oc-slice" / name), "content": "x"})
                self.assertEqual(verdict, "deny")
                self.assertIn("dev-team metadata", reason)


if __name__ == "__main__":
    unittest.main()
