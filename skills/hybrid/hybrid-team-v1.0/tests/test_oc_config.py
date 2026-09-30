import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import oc_config

ENGINE = "/abs/hybrid-team-v1.0/scripts/devteam.py"
COMMANDS = {"test": "pytest tests/", "lint": "ruff check .", "typecheck": "mypy ."}
PREFIX = "PORT=1 DB_SUFFIX=x TMPDIR=.slice/tmp "


def _match(pattern, command):
    # opencode: "*" matches anything, "?" exactly one character; a trailing " *" also matches the bare command.
    if pattern.endswith(" *"):
        rx = re.escape(pattern[:-2]).replace(r"\*", ".*").replace(r"\?", ".") + "( .*)?"
    else:
        rx = re.escape(pattern).replace(r"\*", ".*").replace(r"\?", ".")
    return re.fullmatch(rx, command, re.S) is not None


def resolve(bash, command):
    # Simulates opencode's ordered rule list: the LAST matching rule wins, no match means allow.
    result = "allow"
    for pattern, value in bash.items():
        if _match(pattern, command):
            result = value
    return result


class TestPermissionBlock(unittest.TestCase):
    def setUp(self):
        self.block = oc_config.permission_block(ENGINE, COMMANDS)
        self.bash = self.block["bash"]

    def test_default_deny_and_removed_keys(self):
        assert self.block["*"] == "deny"
        assert list(self.bash)[0] == "*" and self.bash["*"] == "deny"
        assert "execute" not in self.block
        for tool in ("webfetch", "websearch", "task", "skill"):
            assert self.block[tool] == "deny", tool
        assert self.block["edit"]["*"] == "allow"
        for path in (".slice/**", ".git", ".git/**"):
            assert self.block["edit"][path] == "deny", path

    def test_allowed_commands(self):
        for cmd in (
            "pytest tests/", "pytest tests/test_a.py -q", "ruff check .", "mypy .",
            PREFIX + "pytest tests/",
            "python3 %s commit-red -m msg" % ENGINE,
            "python3 %s commit-green" % ENGINE,
            "python3 %s commit-work -m x" % ENGINE,
            "python3 %s commit-fast -m x" % ENGINE,
            "git status", "git diff HEAD", "git log -n 3", "git show HEAD",
            "ls", "ls -la src", "cat src/a.py", "head -n 5 a.py", "tail a.py", "wc -l a.py",
            "grep -rn foo src", "rg foo src", "find src -name '*.py'",
        ):
            assert resolve(self.bash, cmd) == "allow", cmd

    def test_denied_commands(self):
        for cmd in (
            "python3 -c 'import urllib.request'", "python3 script.py",
            "/usr/bin/git push origin main", "git push", "git update-ref refs/heads/x HEAD",
            "git branch -f main HEAD", "git config core.hooksPath /tmp/h", "git commit -m x",
            "git -C /other status", "git diff --output=out.txt", "git log --output=x",
            "cat ~/.ssh/id_ed25519", "cat .env", "cat config/.env.local", "cat key.pem",
            "cat ../secret", "cat /etc/passwd", "cat $HOME/x", "cat `pwd`/x", "cat < a",
            "env", "printenv", "curl http://x", "wget http://x", "npm install x", "pip install x",
            "find . -exec rm {} ;", "find . -delete", "find . -fprint out", "rg --pre sh foo",
            "ls > out.txt", "pytest tests/ > out.txt", "echo hi", "rm -rf x", "sh -c 'x'",
        ):
            assert resolve(self.bash, cmd) == "deny", cmd

    def test_none_commands_not_allowed(self):
        block = oc_config.permission_block(ENGINE, {"test": "none", "lint": "n/a", "typecheck": "-"})
        assert "none*" not in block["bash"] and "n/a*" not in block["bash"]
        assert resolve(block["bash"], "none") == "deny"
        assert resolve(block["bash"], "python3 %s commit-green" % ENGINE) == "allow"

    def test_pinned_command_with_files_placeholder(self):
        block = oc_config.permission_block(ENGINE, {"test_file": "pytest {files} -q"})
        assert resolve(block["bash"], "pytest tests/test_a.py") == "allow"

    def test_plan_commands_survive_generic_denies(self):
        block = oc_config.permission_block(ENGINE, {"test": "npx vitest run"})
        assert resolve(block["bash"], "npx vitest run") == "allow"
        assert resolve(block["bash"], "npx other-tool") == "deny"

    def test_secret_read_denies(self):
        read = self.block["read"]
        assert list(read.items())[0] == ("*", "allow")
        for pat in ("*.env", "*.env.*", "*.ssh/*", "*.pem", "*.key", "*id_rsa*", "*id_ed25519*"):
            assert read[pat] == "deny", pat

    def test_external_directory_is_fenced(self):
        ext = self.block["external_directory"]
        assert list(ext.items()) == [("*", "deny"), (oc_config.tool_output_glob(), "allow")]


class TestBuildConfig(unittest.TestCase):
    def test_build_config_embeds_agent_and_top_level_permission(self):
        config = oc_config.build_config("You are ht-programmer.", ENGINE, COMMANDS)
        agent = config["agent"][oc_config.AGENT_NAME]
        assert agent["prompt"] == "You are ht-programmer."
        assert agent["permission"]["edit"]["*"] == "allow"
        assert config["permission"] == agent["permission"]
        assert config["permission"] is not agent["permission"]
        assert config["permission"]["bash"]["*"] == "deny"


class TestConfigEnv(unittest.TestCase):
    def test_config_env_returns_json_serialized_config_and_disables_project_config(self):
        env = oc_config.config_env("You are ht-programmer.", ENGINE, COMMANDS)
        assert sorted(env) == ["OPENCODE_CONFIG_CONTENT", "OPENCODE_DISABLE_PROJECT_CONFIG"]
        assert env["OPENCODE_DISABLE_PROJECT_CONFIG"] == "1"
        decoded = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        assert decoded == oc_config.build_config("You are ht-programmer.", ENGINE, COMMANDS)
        # Rule order matters to opencode (last match wins): it must survive JSON.
        assert list(decoded["permission"]["bash"]) == list(oc_config.permission_block(ENGINE, COMMANDS)["bash"])

    def test_constants(self):
        assert oc_config.AGENT_NAME == "ht-programmer"
        assert oc_config.SENTINEL == "HT-AGENT-OK"


class TestReviewBypasses(unittest.TestCase):
    """Command strings a security review found allowed; every one must now resolve to deny."""

    def setUp(self):
        self.bash = oc_config.permission_block(ENGINE, COMMANDS)["bash"]

    def test_pinned_command_flags_cannot_leave_the_worktree(self):
        for cmd in (
            "pytest tests/ --junitxml=/Users/me/.zshrc",
            "pytest tests/ --basetemp=/Users/me/Documents",
            "ruff check . --fix --output-file=/Users/me/.zshrc",
            "pytest tests/ --junitxml=$HOME/.git/hooks/pre-commit",
            PREFIX + "pytest tests/ --junitxml=/tmp/x",
            "PORT=1 LD_PRELOAD=x DB_SUFFIX=y TMPDIR=.slice/tmp pytest tests/",
        ):
            assert resolve(self.bash, cmd) == "deny", cmd

    def test_pinned_prefix_no_longer_matches_a_longer_word(self):
        assert resolve(self.bash, "pytestx tests/") == "deny"
        assert resolve(self.bash, "pytest tests/test_a.py -q") == "allow"
        assert resolve(self.bash, "pytest tests/") == "allow"

    def test_rg_hostname_and_hyperlink_execution_denied(self):
        assert resolve(self.bash, "rg --hostname-bin=./h.sh --hyperlink-format=default x") == "deny"

    def test_quoted_or_globbed_secret_reads_denied(self):
        for cmd in ("cat '.env'", 'cat ".env"', "cat .e[n]v", "git show 'HEAD:.env'", "cat .npmrc",
                    "cat .aws/credentials", "ls ..", "grep -f/etc/passwd x"):
            assert resolve(self.bash, cmd) == "deny", cmd

    def test_commit_helpers_still_allowed_but_not_with_redirection(self):
        assert resolve(self.bash, "python3 %s commit-green S1" % ENGINE) == "allow"
        assert resolve(self.bash, "python3 %s commit-green S1 > out" % ENGINE) == "deny"
        assert resolve(self.bash, "python3 %s integrate S1" % ENGINE) == "deny"



if __name__ == "__main__":
    unittest.main()
