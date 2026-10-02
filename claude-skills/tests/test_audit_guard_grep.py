"""Black-box tests for T12: audit_guard.py Grep/Glob prose-doc policy and tighter write checks.

Fixtures live under the system temp dir, never inside this repo.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD_PY = Path(__file__).resolve().parents[1] / "claude-requirements-code-audit" / "hooks" / "audit_guard.py"
assert GUARD_PY.exists(), GUARD_PY

DOC_GLOB = "!*.md !*.mdx !*.markdown !*.rst !*.adoc !*.asciidoc !*.textile !*.org"


class GuardCase(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="t12-audit-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.out_dir = os.path.join(self.root, ".audit")
        os.makedirs(self.out_dir)
        self.spec = os.path.join(self.root, "req", "spec.md")
        os.makedirs(os.path.dirname(self.spec))
        Path(self.spec).write_text("The system MUST log in.\n", encoding="utf-8")
        cfg = {
            "active": True,
            "out_dir": self.out_dir,
            "repo_root": self.root,
            "spec_files": [self.spec],
            "scripts_dir": os.path.join(self.root, "skill", "scripts"),
        }
        Path(self.out_dir, "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    def decide(self, tool, tool_input, worker=False):
        event = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input, "cwd": self.root}
        if worker:
            event["agent_id"] = "sub-1"
            event["agent_type"] = "claude-rca-investigator"
        env = dict(os.environ)
        env["CLAUDE_PROJECT_DIR"] = self.root
        proc = subprocess.run([sys.executable, str(GUARD_PY)], input=json.dumps(event),
                              capture_output=True, text=True, timeout=10, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        if not proc.stdout.strip():
            return None, ""
        out = json.loads(proc.stdout)["hookSpecificOutput"]
        return out.get("permissionDecision"), out.get("permissionDecisionReason", "")

    def assert_denied(self, tool, tool_input, worker=False):
        decision, reason = self.decide(tool, tool_input, worker)
        self.assertEqual(decision, "deny", "expected deny for %s %r, got %r" % (tool, tool_input, decision))
        return reason

    def assert_not_denied(self, tool, tool_input, worker=False):
        decision, reason = self.decide(tool, tool_input, worker)
        self.assertNotEqual(decision, "deny", "unexpected deny for %s %r: %s" % (tool, tool_input, reason))


class GrepGlobPolicyTests(GuardCase):
    def test_grep_without_glob_denied_and_message_states_allowed_form(self):
        reason = self.assert_denied("Grep", {"pattern": "login"})
        self.assertIn(DOC_GLOB, reason)

    def test_grep_directory_without_glob_denied_for_worker_too(self):
        self.assert_denied("Grep", {"pattern": "login", "path": "src"}, worker=True)

    def test_grep_with_only_md_excluded_denied(self):
        self.assert_denied("Grep", {"pattern": "login", "glob": "!*.md"})

    def test_grep_exclusion_tokens_are_matched_whole(self):
        # "!*.md" is a prefix of "!*.mdx"; a glob that lacks the md token must still be denied
        self.assert_denied("Grep", {"pattern": "login", "glob": "!*.mdx !*.markdown !*.rst !*.adoc !*.asciidoc !*.textile !*.org"})

    def test_grep_with_all_doc_extensions_excluded_allowed(self):
        self.assert_not_denied("Grep", {"pattern": "login", "glob": DOC_GLOB})
        self.assert_not_denied("Grep", {"pattern": "login", "path": "src", "glob": DOC_GLOB}, worker=True)

    def test_grep_single_source_file_allowed(self):
        src = os.path.join(self.root, "src", "a.py")
        os.makedirs(os.path.dirname(src))
        Path(src).write_text("x = 1\n", encoding="utf-8")
        self.assert_not_denied("Grep", {"pattern": "x", "path": src})

    def test_grep_single_doc_file_denied(self):
        readme = os.path.join(self.root, "README.md")
        Path(readme).write_text("hello\n", encoding="utf-8")
        self.assert_denied("Grep", {"pattern": "hello", "path": readme})

    def test_grep_outside_repo_allowed(self):
        other = os.path.realpath(tempfile.mkdtemp(prefix="t12-other-"))
        self.addCleanup(shutil.rmtree, other, True)
        self.assert_not_denied("Grep", {"pattern": "x", "path": other})

    def test_grep_audit_dir_and_spec_file_allowed(self):
        self.assert_not_denied("Grep", {"pattern": "x", "path": self.out_dir})
        self.assert_not_denied("Grep", {"pattern": "log", "path": self.spec})

    def test_grep_git_dir_still_denied(self):
        reason = self.assert_denied("Grep", {"pattern": "x", "path": os.path.join(self.root, ".git"), "glob": DOC_GLOB})
        self.assertIn("git", reason.lower())

    def test_glob_patterns_that_can_match_docs_denied(self):
        for pattern in ("**/*", "docs/**", "**/*.md", "**/README*", "*"):
            with self.subTest(pattern=pattern):
                reason = self.assert_denied("Glob", {"pattern": pattern})
                self.assertIn("**/*.py", reason)

    def test_glob_patterns_naming_source_extensions_allowed(self):
        for pattern in ("**/*.py", "src/**/*.{ts,tsx}", "**/Dockerfile", "src/app/main.go"):
            with self.subTest(pattern=pattern):
                self.assert_not_denied("Glob", {"pattern": pattern})


class WriteCheckTests(GuardCase):
    def test_worker_redirect_into_out_dir_allowed(self):
        cmd = "echo x > %s/findings/batch-01.jsonl" % self.out_dir
        self.assert_not_denied("Bash", {"command": cmd}, worker=True)

    def test_worker_out_dir_mention_does_not_exempt_other_writes(self):
        cmd = "rm -rf src; echo %s" % self.out_dir
        self.assert_denied("Bash", {"command": cmd}, worker=True)

    def test_worker_redirect_outside_out_dir_denied_even_if_out_dir_in_args(self):
        cmd = "echo %s > src/a.py" % self.out_dir
        self.assert_denied("Bash", {"command": cmd}, worker=True)

    def test_worker_redirect_dotdot_escape_denied(self):
        cmd = "echo x > %s/../src/a.py" % self.out_dir
        self.assert_denied("Bash", {"command": cmd}, worker=True)

    def test_worker_out_dir_redirect_followed_by_rm_denied(self):
        cmd = "echo x > %s/a.jsonl; rm -rf src" % self.out_dir
        self.assert_denied("Bash", {"command": cmd}, worker=True)


class ReadClaudeDirTests(GuardCase):
    def test_read_prose_under_dot_claude_inside_repo_denied(self):
        self.assert_denied("Read", {"file_path": os.path.join(self.root, ".claude", "notes.md")})

    def test_read_prose_under_dot_claude_outside_repo_allowed(self):
        other = os.path.realpath(tempfile.mkdtemp(prefix="t12-cfg-"))
        self.addCleanup(shutil.rmtree, other, True)
        self.assert_not_denied("Read", {"file_path": os.path.join(other, ".claude", "skills", "x", "README.md")})


if __name__ == "__main__":
    unittest.main()
