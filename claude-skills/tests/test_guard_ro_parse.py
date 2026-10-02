"""Black-box tests for the read-only Bash policy in claude-dev-team-v3.2/scripts/guard.py (task T07).

A read-only role may run harmless commands that only MENTION a mutating tool's name as an argument
(`grep -rn install src`); mutating tools are denied only at command position, including behind
wrappers, xargs, find -exec and sh -c / eval payloads.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD_PY = Path(__file__).resolve().parents[1] / "claude-dev-team-v3.2" / "scripts" / "guard.py"


def decide(cmd, cwd):
    """The permissionDecision the bash-ro guard prints for `cmd` ('allow' / 'deny'), or None when silent."""
    r = subprocess.run([sys.executable, str(GUARD_PY), "bash-ro"],
                       input=json.dumps({"tool_input": {"command": cmd}, "cwd": cwd}),
                       cwd=cwd, capture_output=True, text=True, timeout=10)
    assert r.returncode == 0, r.stderr
    out = r.stdout.strip()
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out else None


class ReadOnlyCommandPositionTest(unittest.TestCase):
    ALLOWED = [
        "grep -rn install src",
        "rg -n touch src",
        "ls | grep -i dd",
        "cat x | grep ln",
        "ls src | grep -i tee | wc -l",
        "grep -rn mkdir . | head -5",
        'grep -rn "install" src',
        "rg -n 'rm -rf' src",
        'echo "rm -rf x"',
        "git log --oneline --grep install",
        "which rm",
    ]
    NOT_DENIED = [
        "command -v rm",
        "grep -rn install src; ls src",
        "ls src && grep -rn touch src",
    ]
    DENIED = [
        # direct, and with a path or quotes around the tool name
        "rm -rf src", "touch x", "mkdir d", "mv a b", "cp a b", "ln -s a b", "chmod +x f", "chown u f",
        "dd if=a of=b", "rsync -a a b", "install -m 644 a b", "truncate -s 0 f",
        "/bin/rm x", '"rm" x', "FOO=1 rm x", "2>/dev/null rm x",
        # after a separator, a newline, a subshell, a backtick or a shell keyword
        "echo hi && rm x", "ls || touch y", "git status; rm x", "git status\nrm x", "(rm x)",
        "echo `rm x`", "if true; then rm x; fi", "grep foo x | tee out.txt", "cat x | dd of=y",
        # behind wrappers, xargs, find -exec, sh -c and eval
        "env FOO=1 touch x", "env -u FOO rm x", "sudo mkdir /x", "sudo -u root rm x", "time cp a b",
        "timeout 5 rm x", "nice -n 5 mv a b", "nohup touch x", "ls | xargs rm",
        "find . -name '*.tmp' | xargs rm -f", "xargs -I {} cp {} /tmp/x < list",
        "find . -exec rm {} \x5c;", "find . -type f -exec sh -c 'rm \"$1\"' _ {} \x5c;",
        "sh -c 'rm -rf src'", 'bash -lc "touch x"', "eval 'rm x'",
        # wrappers and system package managers a plain command-position scan would miss
        "busybox rm x", "builtin command rm x", "make install", "brew install foo", "sudo apt-get install x",
        # unparsable quoting falls back to the conservative substring scan
        'rm "unterminated', 'grep install "src',
        # redirects and in-place edits stay denied
        "ls > out.txt", "echo hi >> log", "sed -i 's/a/b/' f",
    ]

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = os.path.realpath(self.tmp.name)

    def test_harmless_commands_with_mutating_words_are_allowed(self):
        for cmd in self.ALLOWED:
            with self.subTest(cmd=cmd):
                self.assertEqual(decide(cmd, self.cwd), "allow")

    def test_compound_and_lookup_commands_are_not_denied(self):
        for cmd in self.NOT_DENIED:
            with self.subTest(cmd=cmd):
                self.assertNotEqual(decide(cmd, self.cwd), "deny")

    def test_mutating_tools_at_command_position_are_denied(self):
        for cmd in self.DENIED:
            with self.subTest(cmd=cmd):
                self.assertEqual(decide(cmd, self.cwd), "deny")


if __name__ == "__main__":
    unittest.main()
