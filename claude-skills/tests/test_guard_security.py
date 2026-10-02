"""Black-box security tests for claude-dev-team-v3.2/scripts/guard.py (slice K04).

Covers: realpath edit paths, canonical .slice/allow match, no write-capable
read-only commands, and lanes cannot drive the engine via devteam.py.
"""
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD_PY = Path(__file__).resolve().parents[1] / "claude-dev-team-v3.2" / "scripts" / "guard.py"


def run_guard(mode, payload, cwd):
    r = subprocess.run(
        [sys.executable, str(GUARD_PY), mode],
        input=json.dumps(payload),
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return r


def decision_of(result):
    """The permissionDecision ('allow'/'deny') printed on stdout, or None (silent = normal flow)."""
    out = result.stdout.strip()
    if not out:
        return None, None
    data = json.loads(out)
    hso = data.get("hookSpecificOutput") or {}
    return hso.get("permissionDecision"), hso.get("permissionDecisionReason")


def make_slice_root(base, footprint=(), kind="code", allow_lines=()):
    root = Path(base)
    sd = root / ".slice"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "id").write_text("K04\n")
    (sd / "kind").write_text(kind + "\n")
    if footprint:
        (sd / "footprint").write_text("\n".join(footprint) + "\n")
    if allow_lines:
        (sd / "allow").write_text("\n".join(allow_lines) + "\n")
    return root


class GuardSecurityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)

    # --- W2-1: realpath edit paths -----------------------------------------

    def test_symlinked_worktree_edit_inside_footprint_is_allowed(self):
        real = Path(self.base) / "real_wt"
        make_slice_root(real, footprint=["file.py"])
        (real / "sub").mkdir(parents=True)
        (real / "file.py").write_text("x = 1\n")
        link = Path(self.base) / "linked_wt"
        os.symlink(real, link)

        # Edge case: a relative file_path with ".." that still resolves inside the footprint.
        payload = {"tool_name": "Edit", "cwd": str(link),
                   "tool_input": {"file_path": "sub/../file.py"}}
        r = run_guard("edit", payload, cwd=str(link))
        decision, reason = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(decision, "allow", msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("footprint", reason or "")

    def test_symlinked_worktree_edit_outside_footprint_is_still_denied(self):
        real = Path(self.base) / "real_wt2"
        make_slice_root(real, footprint=["file.py"])
        (real / "file.py").write_text("x = 1\n")
        (real / "other.py").write_text("y = 2\n")
        link = Path(self.base) / "linked_wt2"
        os.symlink(real, link)

        payload = {"tool_name": "Edit", "cwd": str(link),
                   "tool_input": {"file_path": "other.py"}}
        r = run_guard("edit", payload, cwd=str(link))
        decision, reason = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(decision, "deny", msg=f"stdout={r.stdout!r}")
        self.assertIn("footprint", reason or "")

    # --- §8 addendum: canonical .slice/allow match --------------------------

    def _engine_pair(self, dirname):
        """A real devteam.py stub and a symlinked alias to it, both under self.base."""
        real_dir = Path(self.base) / dirname  # a space in the name: edge case
        real_dir.mkdir(parents=True)
        script_real = real_dir / "devteam.py"
        script_real.write_text("# stub\n")
        link_dir = Path(self.base) / (dirname + "-link")
        os.symlink(real_dir, link_dir)
        script_link = link_dir / "devteam.py"
        return str(script_real), str(script_link)

    def test_pinned_helper_preapproved_when_allow_has_resolved_and_command_is_literal(self):
        script_real, script_link = self._engine_pair("My Engine A")
        wt = make_slice_root(Path(self.base) / "wt_a",
                              allow_lines=[f'python3 {shlex.quote(script_real)} commit-red "title"'])
        payload = {"tool_name": "Bash", "cwd": str(wt),
                   "tool_input": {"command": f'python3 {shlex.quote(script_link)} commit-red "title"'}}
        r = run_guard("bash", payload, cwd=str(wt))
        decision, reason = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(decision, "allow", msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pinned", reason or "")

    def test_pinned_helper_preapproved_when_allow_has_literal_and_command_is_resolved(self):
        script_real, script_link = self._engine_pair("My Engine B")
        wt = make_slice_root(Path(self.base) / "wt_b",
                              allow_lines=[f'python3 {shlex.quote(script_link)} commit-red "title"'])
        payload = {"tool_name": "Bash", "cwd": str(wt),
                   "tool_input": {"command": f'python3 {shlex.quote(script_real)} commit-red "title"'}}
        r = run_guard("bash", payload, cwd=str(wt))
        decision, reason = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(decision, "allow", msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("pinned", reason or "")

    def test_only_the_pinned_subcommand_gets_preapproved(self):
        script_real, script_link = self._engine_pair("My Engine C")
        wt = make_slice_root(Path(self.base) / "wt_c",
                              allow_lines=[f'python3 {shlex.quote(script_real)} commit-red "title"'])
        # Same script (either spelling), a DIFFERENT subcommand: must not be pre-approved,
        # and must be explicitly denied (K04 criterion: lanes cannot drive the engine).
        payload = {"tool_name": "Bash", "cwd": str(wt),
                   "tool_input": {"command": f'python3 {shlex.quote(script_link)} integrate'}}
        r = run_guard("bash", payload, cwd=str(wt))
        decision, reason = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(decision, "deny", msg=f"stdout={r.stdout!r}")
        self.assertIn("integrate", (reason or "").lower() + " " + str(reason))

    # --- W2-3: lanes cannot drive the engine --------------------------------

    def test_devteam_control_subcommands_denied_from_a_lane(self):
        wt = make_slice_root(Path(self.base) / "wt_ctl")
        for sub in ("integrate", "finish", "reset", "next", "dispatch"):
            with self.subTest(sub=sub):
                payload = {"tool_name": "Bash", "cwd": str(wt),
                           "tool_input": {"command": f"python3 /fake/dir/devteam.py {sub}"}}
                r = run_guard("bash", payload, cwd=str(wt))
                decision, reason = decision_of(r)
                self.assertEqual(r.returncode, 0)
                self.assertEqual(decision, "deny", msg=f"sub={sub} stdout={r.stdout!r}")
                self.assertTrue(reason)

    def test_devteam_allowed_subcommands_are_not_denied_by_the_control_check(self):
        wt = make_slice_root(Path(self.base) / "wt_ctl2")
        for sub in ("claim", "commit-red", "commit-green", "commit-work", "commit-fast"):
            with self.subTest(sub=sub):
                payload = {"tool_name": "Bash", "cwd": str(wt),
                           "tool_input": {"command": f"python3 /fake/dir/devteam.py {sub} K04"}}
                r = run_guard("bash", payload, cwd=str(wt))
                decision, _ = decision_of(r)
                self.assertEqual(r.returncode, 0)
                self.assertNotEqual(decision, "deny", msg=f"sub={sub} stdout={r.stdout!r}")

    def test_devteam_control_denial_survives_a_spaced_script_path(self):
        wt = make_slice_root(Path(self.base) / "wt_ctl3")
        payload = {"tool_name": "Bash", "cwd": str(wt),
                   "tool_input": {"command": 'python3 "/fake/My Dir/devteam.py" integrate'}}
        r = run_guard("bash", payload, cwd=str(wt))
        decision, reason = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(decision, "deny", msg=f"stdout={r.stdout!r}")
        self.assertTrue(reason)

    # --- W2-2: no write-capable read-only commands --------------------------

    WRITE_CAPABLE = [
        "git diff --output=/tmp/x.diff",
        "git log --output=/tmp/x.log",
        "git grep -Ovim pattern",
        "git grep --open-files-in-pager=vim pattern",
        "sort -o /tmp/out.txt file.txt",
        "sort --output=/tmp/out.txt file.txt",
        "sed 's/a/b/w /tmp/out.txt' file.txt",
        "rg --pre cat pattern",
        # F3: abbreviated/combined-short-flag spellings must be caught too.
        "git show --output=F HEAD",
        "git grep --open=touch p",
        "git grep -nOtouch p",
        "sort -uo F a",
        "sort --out=F a",
        "sed -n 1wF a",
        "sed s/a/b/wF a",
    ]

    def test_write_capable_commands_not_preapproved_for_programmer(self):
        wt = make_slice_root(Path(self.base) / "wt_wc")
        for cmd in self.WRITE_CAPABLE:
            with self.subTest(cmd=cmd):
                payload = {"tool_name": "Bash", "cwd": str(wt), "tool_input": {"command": cmd}}
                r = run_guard("bash", payload, cwd=str(wt))
                decision, _ = decision_of(r)
                self.assertEqual(r.returncode, 0)
                self.assertNotEqual(decision, "allow", msg=f"cmd={cmd!r} stdout={r.stdout!r}")

    def test_write_capable_commands_not_preapproved_for_readonly_role(self):
        wt = make_slice_root(Path(self.base) / "wt_wc_ro")
        for cmd in self.WRITE_CAPABLE:
            with self.subTest(cmd=cmd):
                payload = {"tool_name": "Bash", "cwd": str(wt), "tool_input": {"command": cmd}}
                r = run_guard("bash-ro", payload, cwd=str(wt))
                decision, _ = decision_of(r)
                self.assertEqual(r.returncode, 0)
                self.assertNotEqual(decision, "allow", msg=f"cmd={cmd!r} stdout={r.stdout!r}")

    def test_sed_print_only_stays_preapproved(self):
        """Edge case: `sed -n 'p'` has no write command and must stay read-only."""
        wt = make_slice_root(Path(self.base) / "wt_sed_ok")
        payload = {"tool_name": "Bash", "cwd": str(wt),
                   "tool_input": {"command": "sed -n 'p' file.txt"}}
        r = run_guard("bash", payload, cwd=str(wt))
        decision, _ = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(decision, "allow", msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")

    # --- F19: wrappers / compound commands and exec-capable awk/sed -----------

    def _decide(self, mode, wt, cmd):
        payload = {"tool_name": "Bash", "cwd": str(wt), "tool_input": {"command": cmd}}
        r = run_guard(mode, payload, cwd=str(wt))
        self.assertEqual(r.returncode, 0)
        return decision_of(r)

    def test_engine_control_denied_through_wrappers_and_compound_commands(self):
        wt = make_slice_root(Path(self.base) / "wt_f19_deny")
        for cmd in ("timeout 600 python3 /x/devteam.py integrate",
                    "env python3 /x/devteam.py next",
                    "nice python3 /x/devteam.py reset --yes",
                    "cd sub && python3 /x/devteam.py integrate",
                    "python3 /x/devteam.py finish; true"):
            with self.subTest(cmd=cmd):
                decision, reason = self._decide("bash", wt, cmd)
                self.assertEqual(decision, "deny", msg=cmd)
                self.assertTrue(reason)

    def test_engine_name_as_argument_still_not_denied_in_f19(self):
        wt = make_slice_root(Path(self.base) / "wt_f19_arg")
        for cmd in ("grep -n x scripts/devteam.py",
                    "git diff -- scripts/devteam.py",
                    "python3 -m py_compile scripts/devteam.py",
                    "wc -l scripts/devteam.py scripts/guard.py",
                    "cd sub && grep -n x scripts/devteam.py"):
            with self.subTest(cmd=cmd):
                decision, _ = self._decide("bash", wt, cmd)
                self.assertNotEqual(decision, "deny", msg=cmd)

    def test_pinned_commit_green_stays_preapproved_in_f19(self):
        script_real = os.path.realpath(os.path.join(self.base, "eng", "devteam.py"))
        allow_line = f"python3 {shlex.quote(script_real)} commit-green"
        wt = make_slice_root(Path(self.base) / "wt_f19_pin", allow_lines=[allow_line])
        decision, _ = self._decide("bash", wt, f"python3 {shlex.quote(script_real)} commit-green t")
        self.assertEqual(decision, "allow")

    EXEC_CAPABLE = [
        "awk 'BEGIN{system(\"touch x\")}'",
        "awk '{print > \"o\"}' f",
        "awk '{print | \"sh\"}' f",
        "sed -n '1e touch x' f",
        "sed 's/a/b/e' f",
        "sed -n '1Wo' f",
    ]

    def test_exec_capable_awk_sed_never_preapproved(self):
        wt = make_slice_root(Path(self.base) / "wt_f19_exec")
        for mode in ("bash", "bash-ro"):
            for cmd in self.EXEC_CAPABLE:
                with self.subTest(mode=mode, cmd=cmd):
                    decision, _ = self._decide(mode, wt, cmd)
                    self.assertNotEqual(decision, "allow", msg=cmd)

    def test_plain_awk_sed_stay_preapproved_in_f19(self):
        wt = make_slice_root(Path(self.base) / "wt_f19_ok")
        for cmd in ("awk '{print $1}' f", "sed -n 'p' f", "sed -n 1,80p src/workers/x.py",
                    "sed -n 5p www.txt"):
            for mode in ("bash", "bash-ro"):
                with self.subTest(mode=mode, cmd=cmd):
                    decision, _ = self._decide(mode, wt, cmd)
                    self.assertEqual(decision, "allow", msg=cmd)

    # --- F33: awk pre-approval inspects only the program text ----------------

    def test_awk_comparison_programs_and_odd_file_names_preapproved_in_f33(self):
        wt = make_slice_root(Path(self.base) / "wt_f33_ok")
        for cmd in ("awk 'NR>1' f", "awk '$3 > 0 {print}' f", "awk '{print}' system.log",
                    "awk -F: '{print $1}' getline.txt"):
            for mode in ("bash", "bash-ro"):
                with self.subTest(mode=mode, cmd=cmd):
                    decision, _ = self._decide(mode, wt, cmd)
                    self.assertEqual(decision, "allow", msg=cmd)

    def test_awk_redirect_pipe_system_getline_or_file_prog_never_preapproved_in_f33(self):
        wt = make_slice_root(Path(self.base) / "wt_f33_bad")
        for cmd in ("awk '{print >> \"o\"}' f", "awk '{printf \"%s\", $1 > \"o\"}' f",
                    "awk '{print $1 | \"sort\"}' f", "awk '{\"date\" | getline d}' f",
                    "awk 'BEGIN{getline x < \"f\"}'", "awk 'BEGIN{system(\"id\")}'",
                    "awk -f prog.awk f", "awk -v a=1 '{print > \"o\"}' f"):
            for mode in ("bash", "bash-ro"):
                with self.subTest(mode=mode, cmd=cmd):
                    decision, _ = self._decide(mode, wt, cmd)
                    self.assertNotEqual(decision, "allow", msg=cmd)

    # --- F44: -F/--assign values and uninspectable gawk options ---------------

    def test_awk_separator_value_or_uninspectable_option_never_preapproved_in_f44(self):
        wt = make_slice_root(Path(self.base) / "wt_f44_bad")
        for cmd in ("awk -F , '{print > \"o\"}' f", "awk -F ' ' 'BEGIN{system(\"id\")}'",
                    "awk --field-separator , '{print > \"o\"}' f",
                    "awk --assign x=1 '{print > \"o\"}' f", "awk -E p.awk f",
                    "awk -l ext '{print}' f", "awk --include lib '{print}' f"):
            for mode in ("bash", "bash-ro"):
                with self.subTest(mode=mode, cmd=cmd):
                    decision, _ = self._decide(mode, wt, cmd)
                    self.assertNotEqual(decision, "allow", msg=cmd)

    def test_awk_separator_and_plain_programs_stay_preapproved_in_f44(self):
        wt = make_slice_root(Path(self.base) / "wt_f44_ok")
        for cmd in ("awk -F, '{print}' f", "awk -F : '{print $1}' f", "awk 'NR>1' f",
                    "awk '$3 > 0 {print}' f", "awk '{print}' system.log"):
            for mode in ("bash", "bash-ro"):
                with self.subTest(mode=mode, cmd=cmd):
                    decision, _ = self._decide(mode, wt, cmd)
                    self.assertEqual(decision, "allow", msg=cmd)

    def test_engine_deny_message_appears_once_in_source_in_f33(self):
        src = GUARD_PY.read_text()
        self.assertEqual(src.count("drives the engine (integrate/finish/reset/next/dispatch"), 1)

    # --- F31: every segment (incl. newlines) scanned; sed option parsing ------

    def test_engine_control_denied_in_any_segment_and_via_absolute_env(self):
        wt = make_slice_root(Path(self.base) / "wt_f31_deny")
        for cmd in ("echo hi\npython3 /x/devteam.py integrate",
                    "python3 /x/devteam.py claim t && python3 /x/devteam.py integrate",
                    "/usr/bin/env python3 /x/devteam.py next"):
            with self.subTest(cmd=cmd):
                decision, reason = self._decide("bash", wt, cmd)
                self.assertEqual(decision, "deny", msg=cmd)
                self.assertTrue(reason)

    def test_lane_helpers_and_engine_name_arguments_not_denied_in_f31(self):
        wt = make_slice_root(Path(self.base) / "wt_f31_ok")
        for cmd in ("cd sub && python3 /x/devteam.py commit-green t",
                    "grep -n x scripts/devteam.py"):
            with self.subTest(cmd=cmd):
                decision, _ = self._decide("bash", wt, cmd)
                self.assertNotEqual(decision, "deny", msg=cmd)

    def test_sed_glued_abbreviated_and_in_place_never_preapproved(self):
        wt = make_slice_root(Path(self.base) / "wt_f31_sed")
        for mode in ("bash", "bash-ro"):
            for cmd in ("sed -e'1e id' f", "sed --expr='1e id' f",
                        "sed -ni 's/a/b/' f", "sed -nI 's/a/b/' f"):
                with self.subTest(mode=mode, cmd=cmd):
                    decision, _ = self._decide(mode, wt, cmd)
                    self.assertNotEqual(decision, "allow", msg=cmd)

    def test_plain_sed_forms_stay_preapproved_in_f31(self):
        wt = make_slice_root(Path(self.base) / "wt_f31_sedok")
        for cmd in ("sed -n 'p' f", "sed -n 1,80p src/workers/x.py", "sed -n 5p www.txt",
                    "sed -ne 'p' f"):
            for mode in ("bash", "bash-ro"):
                with self.subTest(mode=mode, cmd=cmd):
                    decision, _ = self._decide(mode, wt, cmd)
                    self.assertEqual(decision, "allow", msg=cmd)

    # --- fail-open on malformed hook input -----------------------------------

    def test_git_show_head_plain_stays_preapproved(self):
        """Edge case: plain `git show HEAD` (no write-capable flag) must stay read-only."""
        wt = make_slice_root(Path(self.base) / "wt_show_ok")
        payload = {"tool_name": "Bash", "cwd": str(wt), "tool_input": {"command": "git show HEAD"}}
        r = run_guard("bash", payload, cwd=str(wt))
        decision, _ = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(decision, "allow", msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")

    # --- F3: precise devteam.py engine detection -----------------------------

    def test_devteam_py_as_plain_argument_is_not_treated_as_engine_invocation(self):
        """`devteam.py` appearing only as a filename ARGUMENT to grep/git/wc/py_compile must never
        be mistaken for actually executing the engine, and so must never be denied."""
        wt = make_slice_root(Path(self.base) / "wt_f3_plain")
        commands = [
            "grep -n x scripts/devteam.py",
            "git diff -- scripts/devteam.py",
            "python3 -m py_compile scripts/devteam.py",
            "wc -l scripts/devteam.py scripts/guard.py",
        ]
        for cmd in commands:
            with self.subTest(cmd=cmd):
                payload = {"tool_name": "Bash", "cwd": str(wt), "tool_input": {"command": cmd}}
                r = run_guard("bash", payload, cwd=str(wt))
                decision, reason = decision_of(r)
                self.assertEqual(r.returncode, 0)
                self.assertNotEqual(decision, "deny",
                                     msg=f"cmd={cmd!r} stdout={r.stdout!r} stderr={r.stderr!r}")

    def test_devteam_py_execution_still_denied_with_interpreter_flags(self):
        wt = make_slice_root(Path(self.base) / "wt_f3_denied")
        for sub in ("integrate", "finish", "reset", "next", "dispatch"):
            for cmd in (f"python3 /x/devteam.py {sub}", f"python3 -B /x/devteam.py {sub}"):
                with self.subTest(cmd=cmd):
                    payload = {"tool_name": "Bash", "cwd": str(wt), "tool_input": {"command": cmd}}
                    r = run_guard("bash", payload, cwd=str(wt))
                    decision, reason = decision_of(r)
                    self.assertEqual(r.returncode, 0)
                    self.assertEqual(decision, "deny", msg=f"cmd={cmd!r} stdout={r.stdout!r}")
                    self.assertTrue(reason)

    # --- F3: argv-based pinned helper match -----------------------------------

    def test_pinned_devteam_helper_matches_on_shlex_argv_not_unquoted_spaces(self):
        script_real, script_link = self._engine_pair("F3 Engine")
        allow_line = f"python3 {shlex.quote(script_real)} commit-green"
        wt = make_slice_root(Path(self.base) / "wt_f3_pin", allow_lines=[allow_line])

        approved_cmds = [
            f'python3 "{script_real}" commit-green t',
            f"python3 '{script_real}' commit-green t",
            f'python3 "{script_link}" commit-green t',
        ]
        for cmd in approved_cmds:
            with self.subTest(cmd=cmd):
                payload = {"tool_name": "Bash", "cwd": str(wt), "tool_input": {"command": cmd}}
                r = run_guard("bash", payload, cwd=str(wt))
                decision, reason = decision_of(r)
                self.assertEqual(r.returncode, 0)
                self.assertEqual(decision, "allow", msg=f"cmd={cmd!r} stdout={r.stdout!r} stderr={r.stderr!r}")
                self.assertIn("pinned", reason or "")

        # An unquoted path with an embedded space: a real shell would split it into several
        # arguments, so it must NOT be treated as the pinned command.
        unquoted_cmd = f"python3 {script_real} commit-green t"
        payload = {"tool_name": "Bash", "cwd": str(wt), "tool_input": {"command": unquoted_cmd}}
        r = run_guard("bash", payload, cwd=str(wt))
        decision, _ = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertNotEqual(decision, "allow", msg=f"stdout={r.stdout!r}")

    def test_normalize_and_pinned_devteam_helpers_removed_in_favour_of_prefix_match(self):
        """Structural: the ad-hoc devteam-specific matchers are gone; the canonical `prefix_match`
        (already used for footprint/git allow-listing) is what does the argv matching now."""
        spec = importlib.util.spec_from_file_location("guard_under_test_f3", str(GUARD_PY))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertFalse(hasattr(mod, "normalize_devteam_command"),
                          "normalize_devteam_command must be removed")
        self.assertFalse(hasattr(mod, "pinned_devteam_match"),
                          "pinned_devteam_match must be removed")
        self.assertTrue(hasattr(mod, "prefix_match"))

    def test_malformed_json_stdin_fails_open(self):
        wt = make_slice_root(Path(self.base) / "wt_bad")
        r = subprocess.run([sys.executable, str(GUARD_PY), "edit"], input="not json{{{",
                            cwd=str(wt), capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)

    def test_empty_payload_fails_open(self):
        wt = make_slice_root(Path(self.base) / "wt_bad2")
        r = run_guard("bash", {}, cwd=str(wt))
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)

    def test_unknown_mode_fails_open(self):
        wt = make_slice_root(Path(self.base) / "wt_bad3")
        r = run_guard("nonexistent-mode", {"tool_input": {}}, cwd=str(wt))
        self.assertEqual(r.returncode, 0)
        self.assertNotIn("Traceback", r.stderr)


if __name__ == "__main__":
    unittest.main()
