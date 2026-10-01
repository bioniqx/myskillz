"""Black-box tests for hybrid-team-v1.0/scripts/guard.py (slice K05).

Covers: false denials on read-only git verbs and quoted `>`/`->` content, the
`.slice/base`-known committed check (HEAD != base), path_matches' C2 "./"
stripping, --no-renames on frozen/refactor diffs (C4), and the Edit-path
`ensure_red_cache` skip for RED/WORK/FAST (no wasted `git log`).
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD_PY = Path(__file__).resolve().parents[1] / "scripts" / "guard.py"


def run_guard(mode, payload, cwd):
    return subprocess.run(
        [sys.executable, str(GUARD_PY), mode],
        input=json.dumps(payload),
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=10,
    )


def decision_of(result):
    out = result.stdout.strip()
    if not out:
        return None, None
    data = json.loads(out)
    hso = data.get("hookSpecificOutput") or {}
    return hso.get("permissionDecision"), hso.get("permissionDecisionReason")


def make_slice_root(base, footprint=(), kind="code", mode="slice", sid="K05"):
    root = Path(base)
    sd = root / ".slice"
    sd.mkdir(parents=True, exist_ok=True)
    (sd / "id").write_text(sid + "\n")
    (sd / "kind").write_text(kind + "\n")
    (sd / "mode").write_text(mode + "\n")
    if footprint:
        (sd / "footprint").write_text("\n".join(footprint) + "\n")
    return root


def git(args, cwd):
    r = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    return r.stdout.strip()


def init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    git(["init", "-q"], path)
    git(["config", "user.email", "a@a.com"], path)
    git(["config", "user.name", "a"], path)
    return path


class NotDeniedTest(unittest.TestCase):
    """W2-4: commands that must never be denied — for both the programmer and read-only guards."""

    CMDS = [
        "git merge-base HEAD~1 HEAD",
        "git stash list",
        "git worktree list",
        "cat .slice/base 2>/dev/null",
        'grep -rn "=>" src/',
        "git log --format='%h -> %s'",
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)

    def test_not_denied_for_programmer(self):
        wt = make_slice_root(Path(self.base) / "wt_prog")
        for cmd in self.CMDS:
            with self.subTest(cmd=cmd):
                r = run_guard("bash", {"tool_input": {"command": cmd}, "cwd": str(wt)}, cwd=str(wt))
                decision, _ = decision_of(r)
                self.assertEqual(r.returncode, 0)
                self.assertNotEqual(decision, "deny", msg=f"cmd={cmd!r} stdout={r.stdout!r}")

    def test_not_denied_for_readonly_role(self):
        wt = Path(self.base) / "wt_ro"
        wt.mkdir(parents=True)
        for cmd in self.CMDS:
            with self.subTest(cmd=cmd):
                r = run_guard("bash-ro", {"tool_input": {"command": cmd}, "cwd": str(wt)}, cwd=str(wt))
                decision, _ = decision_of(r)
                self.assertEqual(r.returncode, 0)
                self.assertNotEqual(decision, "deny", msg=f"cmd={cmd!r} stdout={r.stdout!r}")


class StillDeniedTest(unittest.TestCase):
    """Regression guard: the false-denial fixes above must not widen real denials."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)

    def test_mutating_git_verbs_still_denied_programmer(self):
        wt = make_slice_root(Path(self.base) / "wt_deny")
        for cmd in ("git merge origin/main", "git stash push -m wip", "git stash pop", "git stash"):
            with self.subTest(cmd=cmd):
                r = run_guard("bash", {"tool_input": {"command": cmd}, "cwd": str(wt)}, cwd=str(wt))
                decision, _ = decision_of(r)
                self.assertEqual(r.returncode, 0)
                self.assertEqual(decision, "deny", msg=f"cmd={cmd!r} stdout={r.stdout!r}")

    def test_mutating_git_verbs_still_denied_readonly(self):
        wt = Path(self.base) / "wt_deny_ro"
        wt.mkdir(parents=True)
        for cmd in ("git merge origin/main", "git stash push -m wip", "git stash pop"):
            with self.subTest(cmd=cmd):
                r = run_guard("bash-ro", {"tool_input": {"command": cmd}, "cwd": str(wt)}, cwd=str(wt))
                decision, _ = decision_of(r)
                self.assertEqual(r.returncode, 0)
                self.assertEqual(decision, "deny", msg=f"cmd={cmd!r} stdout={r.stdout!r}")

    def test_real_redirect_outside_footprint_never_preapproved(self):
        wt = make_slice_root(Path(self.base) / "wt_redir", footprint=["src/"])
        r = run_guard("bash", {"tool_input": {"command": "echo hi > /tmp/gk05_outside.txt"}, "cwd": str(wt)}, cwd=str(wt))
        decision, _ = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertNotEqual(decision, "allow", msg=f"stdout={r.stdout!r}")

    def test_quoted_arrow_then_real_redirect_still_not_preapproved(self):
        """Edge case: a quoted `>` followed by a REAL redirect must still be caught."""
        wt = make_slice_root(Path(self.base) / "wt_redir2", footprint=["src/"])
        cmd = 'grep ">" file.txt > /tmp/gk05_out2.txt'
        r = run_guard("bash", {"tool_input": {"command": cmd}, "cwd": str(wt)}, cwd=str(wt))
        decision, _ = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertNotEqual(decision, "allow", msg=f"stdout={r.stdout!r}")


class QuoteHandlingTest(unittest.TestCase):
    """F13: quotes must neither pre-approve command substitution nor hide a denied verb/path."""

    SUBST = ['echo "$(touch x)"', 'cat "`id`"', 'echo "${HOME}"']

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)

    def _run(self, mode, cmd, name):
        wt = Path(self.base) / name
        if mode == "bash":
            make_slice_root(wt, footprint=["src/"])
        else:
            wt.mkdir(parents=True)
        r = run_guard(mode, {"tool_input": {"command": cmd}, "cwd": str(wt)}, cwd=str(wt))
        self.assertEqual(r.returncode, 0)
        return decision_of(r)[0], r

    def test_plain_quoted_echo_is_still_preapproved(self):
        for mode in ("bash", "bash-ro"):
            decision, r = self._run(mode, 'echo "hello world"', f"ctl_{mode}")
            self.assertEqual(decision, "allow", msg=f"mode={mode} stdout={r.stdout!r}")

    def test_command_substitution_in_double_quotes_never_preapproved(self):
        for mode in ("bash", "bash-ro"):
            for i, cmd in enumerate(self.SUBST):
                with self.subTest(mode=mode, cmd=cmd):
                    decision, r = self._run(mode, cmd, f"subst_{mode}_{i}")
                    self.assertNotEqual(decision, "allow", msg=f"stdout={r.stdout!r}")

    def test_programmer_denies_quoted_git_verbs_and_quoted_redirect_targets(self):
        cmds = ['bash -c "git push"', 'sh -c "git merge x"', 'echo x > ".slice/red"',
                'printf x > ".claude/hybrid-team/slices/K1.done"']
        for i, cmd in enumerate(cmds):
            with self.subTest(cmd=cmd):
                decision, r = self._run("bash", cmd, f"deny_prog_{i}")
                self.assertEqual(decision, "deny", msg=f"stdout={r.stdout!r}")

    def test_readonly_denies_quoted_mutations_in_shell_dash_c(self):
        for i, cmd in enumerate(['bash -c "rm -rf src"', 'bash -c "git commit -m x"']):
            with self.subTest(cmd=cmd):
                decision, r = self._run("bash-ro", cmd, f"deny_ro_{i}")
                self.assertEqual(decision, "deny", msg=f"stdout={r.stdout!r}")


class PathMatchesC2Test(unittest.TestCase):
    """C2: path_matches strips only a literal leading './' loop, never lstrip('./')."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)

    def test_leading_dot_file_not_confused_with_stripped_footprint_entry(self):
        # lstrip("./") would strip the leading dot off ".config" and wrongly equate it with
        # footprint entry "config"; the C2 while-loop must not.
        wt = make_slice_root(Path(self.base) / "wt_dot", footprint=["config"])
        (wt / ".config").write_text("secret\n")
        payload = {"tool_name": "Edit", "cwd": str(wt), "tool_input": {"file_path": ".config"}}
        r = run_guard("edit", payload, cwd=str(wt))
        decision, reason = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(decision, "deny", msg=f"stdout={r.stdout!r}")
        self.assertIn("footprint", reason or "")

    def test_genuine_leading_dot_slash_in_footprint_entry_still_strips(self):
        wt = make_slice_root(Path(self.base) / "wt_dotslash", footprint=["./file.py"])
        (wt / "file.py").write_text("x = 1\n")
        payload = {"tool_name": "Edit", "cwd": str(wt), "tool_input": {"file_path": "file.py"}}
        r = run_guard("edit", payload, cwd=str(wt))
        decision, _ = decision_of(r)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(decision, "allow", msg=f"stdout={r.stdout!r}")


class CommittedCheckTest(unittest.TestCase):
    """W2-5: with .slice/base known, committed == (HEAD != base); an old commit reusing the
    slice id must not count."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)

    def _gate_message(self, extra_lines=1):
        lines = "\n".join(f"line {i}: ran something -> ok" for i in range(extra_lines))
        return f"## Status: Complete\n## Gate: {lines}\n"

    def test_old_commit_reusing_slice_id_does_not_count_as_committed(self):
        wt = init_repo(Path(self.base) / "wt_old")
        (wt / "a.txt").write_text("a\n")
        git(["add", "-A"], wt)
        git(["commit", "-q", "-m", "chore(K05): old leftover run"], wt)
        (wt / "b.txt").write_text("b\n")
        git(["add", "-A"], wt)
        git(["commit", "-q", "-m", "chore: unrelated setup"], wt)
        base_sha = git(["rev-parse", "HEAD"], wt)
        make_slice_root(wt, kind="chore", mode="work")
        (wt / ".slice" / "base").write_text(base_sha + "\n")
        payload = {"cwd": str(wt), "last_assistant_message": self._gate_message()}
        r = run_guard("stop", payload, cwd=str(wt))
        self.assertEqual(r.returncode, 2, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("nothing committed", r.stderr)

    def test_new_commit_after_base_counts_as_committed(self):
        wt = init_repo(Path(self.base) / "wt_new")
        (wt / "a.txt").write_text("a\n")
        git(["add", "-A"], wt)
        git(["commit", "-q", "-m", "chore(K05): old leftover run"], wt)
        (wt / "b.txt").write_text("b\n")
        git(["add", "-A"], wt)
        git(["commit", "-q", "-m", "chore: unrelated setup"], wt)
        base_sha = git(["rev-parse", "HEAD"], wt)
        (wt / "c.txt").write_text("c\n")
        git(["add", "-A"], wt)
        git(["commit", "-q", "-m", "chore(K05): this run's work"], wt)
        make_slice_root(wt, kind="chore", mode="work")
        (wt / ".slice" / "base").write_text(base_sha + "\n")
        payload = {"cwd": str(wt), "last_assistant_message": self._gate_message()}
        r = run_guard("stop", payload, cwd=str(wt))
        self.assertEqual(r.returncode, 0, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertNotIn("nothing committed", r.stderr)


class NoRenamesTest(unittest.TestCase):
    """C4: a rename that would otherwise hide a frozen/test file from --name-only must still
    be caught once --no-renames is passed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)

    def test_refactor_cannot_hide_a_renamed_test_file(self):
        wt = init_repo(Path(self.base) / "wt_rename")
        (wt / "tests").mkdir()
        content = "def test_a():\n    assert 1 == 1\n" + ("# pad line filler content here\n" * 30)
        (wt / "tests" / "test_x.py").write_text(content)
        git(["add", "-A"], wt)
        git(["commit", "-q", "-m", "chore(K05): base"], wt)
        base_sha = git(["rev-parse", "HEAD"], wt)

        git(["rm", "-q", "tests/test_x.py"], wt)
        (wt / "renamed_util.py").write_text(content)  # identical content: git detects a rename
        git(["add", "-A"], wt)
        git(["commit", "-q", "-m", "refactor(K05): rename away the test"], wt)

        make_slice_root(wt, kind="refactor", mode="work", footprint=["tests/", "renamed_util.py"])
        (wt / ".slice" / "base").write_text(base_sha + "\n")
        gate = "## Status: Complete\n## Gate: before: 1 passed\nafter: 1 passed\nlint: clean\n"
        r = run_guard("stop", {"cwd": str(wt), "last_assistant_message": gate}, cwd=str(wt))
        self.assertEqual(r.returncode, 2, msg=f"stdout={r.stdout!r} stderr={r.stderr!r}")
        self.assertIn("test_x.py", r.stderr)
        self.assertIn("REFACTOR slice changed test files", r.stderr)


class EditPathSkipTest(unittest.TestCase):
    """W2 perf: an Edit in RED/WORK/FAST must not probe for a RED commit via ensure_red_cache."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = os.path.realpath(self.tmp.name)

    def _repo_with_discoverable_red(self, name):
        wt = init_repo(Path(self.base) / name)
        (wt / "file.py").write_text("x = 1\n")
        (wt / "tests").mkdir()
        (wt / "tests" / "test_x.py").write_text("def test_a():\n    assert True\n")
        git(["add", "-A"], wt)
        git(["commit", "-q", "-m", "test(K05): RED - failing tests"], wt)
        return wt

    def test_red_work_fast_skip_the_red_probe(self):
        for mode in ("red", "work", "fast"):
            with self.subTest(mode=mode):
                wt = self._repo_with_discoverable_red(f"wt_skip_{mode}")
                make_slice_root(wt, footprint=["file.py"], mode=mode)
                payload = {"tool_name": "Edit", "cwd": str(wt), "tool_input": {"file_path": "file.py"}}
                r = run_guard("edit", payload, cwd=str(wt))
                decision, _ = decision_of(r)
                self.assertEqual(r.returncode, 0)
                self.assertNotEqual(decision, "deny", msg=f"mode={mode} stdout={r.stdout!r}")
                self.assertFalse((wt / ".slice" / "red").exists(),
                                 msg=f"mode={mode}: ensure_red_cache ran (git log spawned) when it should be skipped")

    def test_slice_and_green_still_run_the_red_probe(self):
        for mode in ("slice", "green"):
            with self.subTest(mode=mode):
                wt = self._repo_with_discoverable_red(f"wt_run_{mode}")
                make_slice_root(wt, footprint=["file.py"], mode=mode)
                payload = {"tool_name": "Edit", "cwd": str(wt), "tool_input": {"file_path": "file.py"}}
                r = run_guard("edit", payload, cwd=str(wt))
                decision, _ = decision_of(r)
                self.assertEqual(r.returncode, 0)
                self.assertNotEqual(decision, "deny", msg=f"mode={mode} stdout={r.stdout!r}")
                self.assertTrue((wt / ".slice" / "red").exists(),
                                msg=f"mode={mode}: ensure_red_cache should still run and cache the RED commit")


class InlineInterpreterMetadataTest(unittest.TestCase):
    """F24: inline interpreters writing .slice/ or .claude/hybrid-team/ are denied (quoted content is scanned)."""

    DENIED = [
        ("""python3 -c "open('.slice/red','w').write('x')" """, "`.slice/`"),
        ("""python3 -c 'open(".slice/red","w").write("x")'""", "`.slice/`"),
        ("""python3 -c "open('.slice/base','a').write('x')" """, "`.slice/`"),
        ("""python3 -c "open('.claude/hybrid-team/slices/K1.done','w').write('x')" """, "`.claude/hybrid-team/`"),
    ]
    NOT_DENIED = [
        """python3 -c "print(open('src/a.py').read())" """,
        """python3 -c "print('a -> b')" """,
        "cat .slice/base 2>/dev/null",
        "git log --format='%h -> %s'",
        """python3 -c "print(open('.slice/base').read())" """,
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wt = make_slice_root(Path(os.path.realpath(self.tmp.name)) / "wt", footprint=["src/"])

    def _run(self, cmd):
        r = run_guard("bash", {"tool_input": {"command": cmd}, "cwd": str(self.wt)}, cwd=str(self.wt))
        self.assertEqual(r.returncode, 0)
        return decision_of(r)

    def test_inline_interpreter_writes_denied_with_metadata_reason(self):
        for cmd, label in self.DENIED:
            with self.subTest(cmd=cmd):
                decision, reason = self._run(cmd)
                self.assertEqual(decision, "deny")
                self.assertIn(label + " is", reason or "")

    def test_inline_interpreter_reads_and_quoted_arrows_not_denied(self):
        for cmd in self.NOT_DENIED:
            with self.subTest(cmd=cmd):
                decision, _ = self._run(cmd)
                self.assertNotEqual(decision, "deny")


class QuoteKeptScopeTest(unittest.TestCase):
    """F39: quoted text is scanned only by metadata patterns; a multi-line quote hides nothing."""

    NOT_DENIED = ['grep -n "git push" src/a.py',
                  'git log --oneline --grep "git worktree add"',
                  "rg 'git reset --hard' src/"]
    ENGINE_DENIED = ['echo "x\n" ; python3 /x/devteam.py integrate',
                     'git commit -m "feat: x\n\ndetails" && python3 /x/devteam.py integrate']
    META_DENIED = ["""python3 -c "import pathlib; pathlib.Path('.slice/red').write_text('x')" """,
                   """python3 -c "print(1, file=open('.claude/hybrid-team/slices/K1.done','w'))" """]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wt = make_slice_root(Path(os.path.realpath(self.tmp.name)) / "wt", footprint=["src/"])

    def _run(self, cmd):
        r = run_guard("bash", {"tool_input": {"command": cmd}, "cwd": str(self.wt)}, cwd=str(self.wt))
        self.assertEqual(r.returncode, 0)
        return decision_of(r)

    def test_git_verbs_inside_quotes_not_denied(self):
        for cmd in self.NOT_DENIED:
            with self.subTest(cmd=cmd):
                self.assertNotEqual(self._run(cmd)[0], "deny")

    def test_multiline_quote_does_not_hide_engine_call(self):
        for cmd in self.ENGINE_DENIED:
            with self.subTest(cmd=cmd):
                decision, reason = self._run(cmd)
                self.assertEqual(decision, "deny")
                self.assertIn("drives the engine", reason or "")

    def test_metadata_writes_in_quotes_still_denied(self):
        for cmd in self.META_DENIED:
            with self.subTest(cmd=cmd):
                decision, reason = self._run(cmd)
                self.assertEqual(decision, "deny")
                self.assertIn("is hybrid-team metadata" if ".slice" in cmd else "is the Conductor's run state",
                              reason or "")

    def test_unquoted_history_verb_still_denied(self):
        decision, reason = self._run("git reset --hard HEAD~1")
        self.assertEqual(decision, "deny")
        self.assertIn("history rewriting", reason or "")


class SubstitutionAndOpenModeTest(unittest.TestCase):
    """F43: $()/backtick spans in double quotes still reach the history scan; open('.slice/..', w/a/x) denied."""

    SUBST_DENIED = ['git commit -m "$(git push origin x)"',
                    'echo "$(git reset --hard HEAD~1)"',
                    'echo "`git push`"']
    NOT_DENIED = ['grep -n "git push" f',
                  'git log --grep "git worktree add"',
                  "rg 'git reset --hard' src/",
                  "cat .slice/red",
                  """python3 -c "open('.slice/red').read()" """,
                  """python3 -c "open('.slice/red','r').read()" """]
    OPEN_DENIED = ["""python3 -c "open('.slice/red','w')" """,
                   """python3 -c "open('.slice/red','a')" """,
                   """python3 -c "open('.slice/red','x')" """,
                   """python3 -c "open('.slice/red', 'w')" """]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.wt = make_slice_root(Path(os.path.realpath(self.tmp.name)) / "wt", footprint=["src/"])

    def _run(self, cmd):
        r = run_guard("bash", {"tool_input": {"command": cmd}, "cwd": str(self.wt)}, cwd=str(self.wt))
        self.assertEqual(r.returncode, 0)
        return decision_of(r)

    def test_substitution_in_double_quotes_denied_with_history_reason(self):
        for cmd in self.SUBST_DENIED:
            with self.subTest(cmd=cmd):
                decision, reason = self._run(cmd)
                self.assertEqual(decision, "deny")
                self.assertRegex(reason or "", "integration/history commands|history rewriting")

    def test_plain_quoted_verbs_and_reads_not_denied(self):
        for cmd in self.NOT_DENIED:
            with self.subTest(cmd=cmd):
                self.assertNotEqual(self._run(cmd)[0], "deny")

    def test_open_slice_write_modes_denied_with_metadata_reason(self):
        for cmd in self.OPEN_DENIED:
            with self.subTest(cmd=cmd):
                decision, reason = self._run(cmd)
                self.assertEqual(decision, "deny")
                self.assertIn("`.slice/` is hybrid-team metadata", reason or "")


if __name__ == "__main__":
    unittest.main()
