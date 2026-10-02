# -*- coding: utf-8 -*-
"""Black-box tests for claude-requirements-code-audit/hooks/audit_guard.{py,sh} (slice K11)."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOKS_DIR = REPO_ROOT / "claude-skills" / "claude-requirements-code-audit" / "hooks"
GUARD_PY = HOOKS_DIR / "audit_guard.py"
GUARD_SH = HOOKS_DIR / "audit_guard.sh"


def make_repo():
    """A real system-temp fixture repo with an ACTIVE audit config, never under the real repo."""
    root = os.path.realpath(tempfile.mkdtemp(prefix="k11-audit-"))
    audit_dir = os.path.join(root, ".audit")
    os.makedirs(audit_dir)
    Path(os.path.join(audit_dir, "ACTIVE")).write_text("1", encoding="utf-8")
    scripts_dir = os.path.join(root, "claude-requirements-code-audit", "scripts")
    cfg = {
        "active": True,
        "out_dir": audit_dir,
        "repo_root": root,
        "spec_files": [],
        "scripts_dir": scripts_dir,
    }
    Path(os.path.join(audit_dir, "config.json")).write_text(json.dumps(cfg), encoding="utf-8")
    return root, scripts_dir


def run_guard(root, payload):
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = root
    proc = subprocess.run(
        [sys.executable, str(GUARD_PY)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
    )
    return proc


def read_decision(proc):
    if not proc.stdout.strip():
        return None
    return json.loads(proc.stdout)["hookSpecificOutput"].get("permissionDecision")


def read_event(root, file_path):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Read",
        "tool_input": {"file_path": file_path},
        "cwd": root,
    }


def bash_event(root, command, subagent=False):
    d = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": root,
    }
    if subagent:
        d["agent_id"] = "sub-1"
        d["agent_type"] = "claude-rca-investigator"
    return d


class DocPathTests(unittest.TestCase):
    """Criterion 1: real source files are readable; real docs stay blocked."""

    @classmethod
    def setUpClass(cls):
        cls.root, cls.scripts_dir = make_repo()

    def assert_allowed(self, path):
        proc = run_guard(self.root, read_event(self.root, path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(read_decision(proc), "expected no decision (allowed) for %s, got %r" % (path, proc.stdout))

    def assert_blocked(self, path):
        proc = run_guard(self.root, read_event(self.root, path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "deny", "expected deny for %s, got %r" % (path, proc.stdout))

    def test_source_files_named_like_docs_are_allowed(self):
        for path in (
            "src/orders/history.ts",
            "src/license/validator.go",
            "src/HistoryController.php",
            "src/notices.py",
            "src/changes_feed.py",
            "docs/api/handler.py",
        ):
            with self.subTest(path=path):
                self.assert_allowed(path)

    def test_real_docs_still_blocked(self):
        for path in ("README.md", "CHANGELOG", "HISTORY.md", "docs/guide.md"):
            with self.subTest(path=path):
                self.assert_blocked(path)

    def test_windows_style_separators_ignored(self):
        self.assert_blocked("documentation\\HISTORY.md")
        self.assert_allowed("src\\license\\validator.go")

    def test_uppercase_license_extension_still_blocked(self):
        self.assert_blocked("LICENSE.TXT")


class ChainedCommandTests(unittest.TestCase):
    """Criterion 2: the lead's auto-allow only fires for the bare bundled script call."""

    @classmethod
    def setUpClass(cls):
        cls.root, cls.scripts_dir = make_repo()

    def audit_cmd(self, suffix=""):
        return "python3 %s/audit.py status%s" % (self.scripts_dir, suffix)

    def test_plain_command_is_auto_allowed(self):
        proc = run_guard(self.root, bash_event(self.root, self.audit_cmd()))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "allow")

    def test_chained_variants_are_not_auto_allowed(self):
        variants = [
            " && rm -rf src",
            "; rm -rf src",
            " | rm -rf src",
            " ` rm -rf src `",
            " $(rm -rf src)",
            "\nrm -rf src",
        ]
        for suffix in variants:
            with self.subTest(suffix=repr(suffix)):
                proc = run_guard(self.root, bash_event(self.root, self.audit_cmd(suffix)))
                self.assertEqual(proc.returncode, 0, proc.stderr)
                decision = read_decision(proc)
                self.assertNotEqual(decision, "allow",
                                     "chained command must not be auto-allowed: %r -> %r" % (suffix, proc.stdout))


class WorkerFalseBlockTests(unittest.TestCase):
    """Criterion 3: safe redirects / quoted text don't trip worker or git-history checks."""

    @classmethod
    def setUpClass(cls):
        cls.root, cls.scripts_dir = make_repo()

    def test_stderr_redirect_not_blocked(self):
        proc = run_guard(self.root, bash_event(self.root, "grep foo file.txt 2>/dev/null", subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotEqual(read_decision(proc), "deny")

    def test_grep_fat_arrow_not_blocked(self):
        proc = run_guard(self.root, bash_event(self.root, "grep '=>' file.js", subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotEqual(read_decision(proc), "deny")

    def test_grep_quoted_git_log_not_blocked(self):
        proc = run_guard(self.root, bash_event(self.root, "grep 'git log' notes.txt", subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotEqual(read_decision(proc), "deny")

    def test_real_git_log_still_blocked(self):
        proc = run_guard(self.root, bash_event(self.root, "git log --oneline -5", subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "deny")

    def test_real_git_show_still_blocked(self):
        proc = run_guard(self.root, bash_event(self.root, "git show HEAD~1", subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "deny")


class QuoteAwareGitTests(unittest.TestCase):
    """Criterion (F4): quote-aware git detection — real git invocations hidden behind
    shell -c wrappers or per-word quoting are still caught; grep patterns are not."""

    @classmethod
    def setUpClass(cls):
        cls.root, cls.scripts_dir = make_repo()

    def test_bash_c_single_quoted_git_log_denied(self):
        proc = run_guard(self.root, bash_event(self.root, "bash -c 'git log -p'", subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "deny", proc.stdout)

    def test_sh_c_double_quoted_git_show_denied(self):
        proc = run_guard(self.root, bash_event(self.root, 'sh -c "git show HEAD~1"', subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "deny", proc.stdout)

    def test_quoted_git_subcommand_word_denied(self):
        proc = run_guard(self.root, bash_event(self.root, "git 'log' -p", subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "deny", proc.stdout)

    def test_quoted_git_word_denied(self):
        proc = run_guard(self.root, bash_event(self.root, '"git" log -p', subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "deny", proc.stdout)

    def test_bash_c_git_commit_denied_as_mutation(self):
        proc = run_guard(self.root, bash_event(self.root, "bash -c 'git commit -am x'", subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "deny", proc.stdout)

    def test_bash_c_echo_redirect_denied_as_writeish(self):
        proc = run_guard(self.root, bash_event(self.root, "bash -c 'echo x > src/a'", subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "deny", proc.stdout)

    def test_grep_git_log_src_not_blocked(self):
        proc = run_guard(self.root, bash_event(self.root, "grep 'git log' src", subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotEqual(read_decision(proc), "deny", proc.stdout)

    def test_grep_fat_arrow_src_not_blocked(self):
        proc = run_guard(self.root, bash_event(self.root, "grep '=>' src", subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotEqual(read_decision(proc), "deny", proc.stdout)

    def test_stderr_devnull_not_blocked(self):
        proc = run_guard(self.root, bash_event(self.root, "cmd 2>/dev/null", subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotEqual(read_decision(proc), "deny", proc.stdout)


class TxtDocBasenameTests(unittest.TestCase):
    """Criterion (F4): .txt is only doc-like for known doc basenames, not any .txt file."""

    @classmethod
    def setUpClass(cls):
        cls.root, cls.scripts_dir = make_repo()

    def assert_allowed(self, path):
        proc = run_guard(self.root, read_event(self.root, path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(read_decision(proc), "expected no decision (allowed) for %s, got %r" % (path, proc.stdout))

    def assert_blocked(self, path):
        proc = run_guard(self.root, read_event(self.root, path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "deny", "expected deny for %s, got %r" % (path, proc.stdout))

    def test_non_doc_txt_files_allowed(self):
        for path in ("requirements.txt", "CMakeLists.txt", "testdata/sample.txt"):
            with self.subTest(path=path):
                self.assert_allowed(path)

    def test_doc_basename_txt_still_blocked(self):
        for path in ("LICENSE.TXT", "README.txt"):
            with self.subTest(path=path):
                self.assert_blocked(path)

    def test_other_docs_still_blocked(self):
        for path in ("README.md", "CHANGELOG", "HISTORY.md", "docs/guide.md"):
            with self.subTest(path=path):
                self.assert_blocked(path)


class ShFastPathTests(unittest.TestCase):
    """Criterion 4: the launcher uses `python3 -S` and skips Python entirely when inactive."""

    def test_launcher_invokes_python_with_dash_s(self):
        text = GUARD_SH.read_text(encoding="utf-8")
        self.assertIn("python3 -S", text)
        self.assertIn("python -S", text)

    def test_inactive_path_exits_fast_without_python(self):
        root = os.path.realpath(tempfile.mkdtemp(prefix="k11-audit-inactive-"))
        env = dict(os.environ)
        env["CLAUDE_PROJECT_DIR"] = root
        start = time.time()
        proc = subprocess.run(
            ["bash", str(GUARD_SH)],
            input="{}",
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
        elapsed = time.time() - start
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertLess(elapsed, 0.3, "inactive path should exit without starting Python: took %.3fs" % elapsed)


class QuotedArgHandlingTests(unittest.TestCase):
    """Criterion (F9): grep/rg/awk/sed quoted args with flags-with-values, multiple quoted
    tokens, and script literals must not be misread as git history or a write."""

    @classmethod
    def setUpClass(cls):
        cls.root, cls.scripts_dir = make_repo()

    def assert_not_denied(self, command):
        proc = run_guard(self.root, bash_event(self.root, command, subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotEqual(read_decision(proc), "deny", "unexpected deny for %r -> %r" % (command, proc.stdout))

    def assert_denied(self, command):
        proc = run_guard(self.root, bash_event(self.root, command, subagent=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "deny", "expected deny for %r -> %r" % (command, proc.stdout))

    def test_grep_flag_with_value_before_pattern_not_denied(self):
        self.assert_not_denied("grep -n -A 3 '=>' src")

    def test_grep_repeated_e_flag_not_denied(self):
        self.assert_not_denied("grep -e a -e '=>' src")

    def test_rg_glob_flag_and_pattern_not_denied(self):
        self.assert_not_denied("rg -g '*.py' 'git log' src")

    def test_grep_include_flag_and_pattern_not_denied(self):
        self.assert_not_denied("grep --include '*.py' 'git show' .")

    def test_awk_script_with_angle_bracket_not_denied(self):
        self.assert_not_denied("awk 'NF > 100' f.txt")

    def test_sed_script_mentioning_git_not_denied(self):
        self.assert_not_denied("sed -n '/git show/p' f")

    def test_malformed_single_quote_still_reveals_chained_git_log(self):
        self.assert_denied("grep 'a\\' src; git log -p; echo 'b'")

    def test_command_substitution_inside_double_quotes_still_denied(self):
        self.assert_denied('grep "$(git log -p)" src')


class EscapedQuoteAndScriptBypassTests(unittest.TestCase):
    """Criterion (F22): backslash-escaped quotes and executable awk/sed scripts must not hide
    git history or writes; harmless awk/sed/grep patterns stay allowed."""

    @classmethod
    def setUpClass(cls):
        cls.root, cls.scripts_dir = make_repo()

    def decide(self, command, subagent):
        proc = run_guard(self.root, bash_event(self.root, command, subagent=subagent))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return read_decision(proc), proc.stdout

    def assert_history_denied(self, command):
        for sub in (False, True):
            d, out = self.decide(command, sub)
            self.assertEqual(d, "deny", "expected history deny for %r (worker=%s) -> %r" % (command, sub, out))

    def assert_write_denied(self, command):
        d, out = self.decide(command, True)
        self.assertEqual(d, "deny", "expected write deny for %r -> %r" % (command, out))

    def assert_worker_allowed(self, command):
        d, out = self.decide(command, True)
        self.assertNotEqual(d, "deny", "unexpected deny for %r -> %r" % (command, out))

    def test_escaped_quote_hides_git_log_denied(self):
        self.assert_history_denied("grep a\\' src; git log -p; echo \\'")

    def test_awk_system_git_log_denied(self):
        self.assert_history_denied("""awk 'BEGIN{system("git log -p")}' f""")

    def test_awk_getline_git_show_denied(self):
        self.assert_history_denied("""awk 'BEGIN{"git show HEAD" | getline x}' f""")

    def test_sed_e_command_git_log_denied(self):
        self.assert_history_denied("sed '1e git log -p' f")

    def test_escaped_quote_hides_rm_denied_for_worker(self):
        self.assert_write_denied("grep a\\' src; rm -rf src; echo \\'")

    def test_awk_print_redirect_denied_for_worker(self):
        self.assert_write_denied("""echo \\'  |  awk '{print > "out.txt"}' f""")

    def test_sed_w_command_denied_for_worker(self):
        self.assert_write_denied("sed -n 'w out' f")

    def test_f9_harmless_patterns_still_allowed(self):
        for c in ("grep -n -A 3 '=>' src", "grep -e a -e '=>' src", "rg -g '*.py' 'git log' src",
                  "grep --include '*.py' 'git show' .", "awk 'NF > 100' f.txt", "sed -n '/git show/p' f",
                  "awk 'NF>1 || $2' f.txt"):
            self.assert_worker_allowed(c)

    def test_f9_malformed_and_substitution_still_denied(self):
        self.assert_history_denied("grep 'a\\' src; git log -p; echo 'b'")
        self.assert_history_denied('grep "$(git log -p)" src')


class SedAwkLiveFormTests(EscapedQuoteAndScriptBypassTests):
    """Criterion (F32): sed w/W/e with no space are live; read-only awk with a lone | is not."""

    def test_sed_no_space_w_denied_for_worker(self):
        self.assert_write_denied("sed -n 'wout' f")

    def test_sed_capital_W_with_address_denied_for_worker(self):
        self.assert_write_denied("sed -n '1W out' f")

    def test_sed_s_flag_w_no_space_denied_for_worker(self):
        self.assert_write_denied("sed 's/a/b/wout' f")

    def test_sed_e_no_space_git_log_denied(self):
        self.assert_history_denied("sed '1egit log -p' f")

    def test_sed_e_git_reset_denied_as_mutation_for_non_worker(self):
        d, out = self.decide("sed -n '1e git reset --hard' f", False)
        self.assertEqual(d, "deny", out)
        self.assertIn("change git state", out)

    def test_sed_e_glued_git_reflog_denied_as_history_for_non_worker(self):
        d, out = self.decide("sed '1egit reflog' f", False)
        self.assertEqual(d, "deny", out)
        self.assertIn("history", out)

    def test_sed_e_git_rev_list_denied_as_history_for_non_worker(self):
        d, out = self.decide("sed '1e git rev-list HEAD' f", False)
        self.assertEqual(d, "deny", out)
        self.assertIn("history", out)

    def test_awk_field_separator_pipe_allowed(self):
        self.assert_worker_allowed("awk -F'|' '{print $2}' f")

    def test_awk_regex_alternation_allowed(self):
        self.assert_worker_allowed("awk '/foo|bar/' f")

    def test_awk_print_pipe_to_command_denied(self):
        self.assert_history_denied("""awk '{print $1 | "git log -p"}' f""")

    def test_awk_command_pipe_getline_denied(self):
        self.assert_history_denied("""awk 'BEGIN{"git log -p" | getline x}' f""")

    def test_awk_print_pipe_to_command_denied_for_worker(self):
        self.assert_write_denied("""awk '{print $1 | "sort"}' f""")

    def test_sed_glued_git_after_earlier_command_letter_denied(self):
        for c in ("sed -n '/error/p;1egit log' f", "sed -n '/w/p;1egit log' f",
                  "sed -n 's/e/x/;1egit log' f", "sed -n '/e/p;egit log' f",
                  "sed -n '/warn/p;1egit show HEAD' f"):
            self.assert_history_denied(c)

    def test_sed_glued_subcommand_words_not_broken(self):
        for c in ("sed '1egit reflog' f", "sed '1e git rev-list HEAD' f"):
            d, out = self.decide(c, False)
            self.assertEqual(d, "deny", out)
            self.assertIn("history", out)
        d, out = self.decide("sed -n '1e git reset --hard' f", False)
        self.assertEqual(d, "deny", out)
        self.assertIn("change git state", out)

    def test_harmless_sed_scripts_with_w_e_words_allowed(self):
        for c in ("sed -n '/warn/p' f", "sed -n '/the end/p' f", "sed 's/a/b/g' f"):
            self.assert_worker_allowed(c)


class TxtDocDirBasenameTests(unittest.TestCase):
    """Criterion (F9): generic .txt basenames inside a doc directory are prose and blocked;
    known non-doc .txt basenames stay allowed even inside a doc directory."""

    @classmethod
    def setUpClass(cls):
        cls.root, cls.scripts_dir = make_repo()

    def assert_allowed(self, path):
        proc = run_guard(self.root, read_event(self.root, path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(read_decision(proc), "expected no decision (allowed) for %s, got %r" % (path, proc.stdout))

    def assert_blocked(self, path):
        proc = run_guard(self.root, read_event(self.root, path))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(read_decision(proc), "deny", "expected deny for %s, got %r" % (path, proc.stdout))

    def test_generic_txt_in_doc_dirs_blocked(self):
        for path in ("docs/notes.txt", "wiki/page.txt"):
            with self.subTest(path=path):
                self.assert_blocked(path)

    def test_known_non_doc_txt_basenames_allowed(self):
        for path in ("docs/requirements.txt", "requirements.txt", "CMakeLists.txt", "testdata/sample.txt"):
            with self.subTest(path=path):
                self.assert_allowed(path)


if __name__ == "__main__":
    unittest.main()
