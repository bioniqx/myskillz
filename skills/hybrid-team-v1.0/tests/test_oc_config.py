import fnmatch
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import oc_config


def _resolve(bash, command):
    # Simulates opencode's last-match-wins permission resolution.
    result = None
    for pattern, value in bash.items():
        if fnmatch.fnmatch(command, pattern):
            result = value
    return result


class TestPermissionBlock(unittest.TestCase):
    def test_permission_block_allows_helpers_denies_dangerous(self):
        commands = {"test": "pytest tests/", "lint": "ruff check .", "typecheck": "mypy ."}
        block = oc_config.permission_block("/abs/hybrid-team-v1.0/scripts/devteam.py", commands)

        assert block["edit"] == "allow"
        assert block["external_directory"] == "deny"

        bash = block["bash"]
        assert bash["python3 /abs/hybrid-team-v1.0/scripts/devteam.py commit-red *"] == "allow"
        assert bash["python3 /abs/hybrid-team-v1.0/scripts/devteam.py commit-green *"] == "allow"
        assert bash["python3 /abs/hybrid-team-v1.0/scripts/devteam.py commit-work *"] == "allow"
        assert bash["python3 /abs/hybrid-team-v1.0/scripts/devteam.py commit-fast *"] == "allow"
        assert bash["git status*"] == "allow"
        assert bash["git diff*"] == "allow"
        assert bash["git log*"] == "allow"
        assert bash["git show*"] == "allow"
        assert bash["pytest tests/*"] == "allow"
        assert bash["ruff check .*"] == "allow"
        assert bash["mypy .*"] == "allow"
        assert bash["git push*"] == "deny"
        assert bash["git reset*"] == "deny"
        assert bash["git rebase*"] == "deny"
        assert bash["git commit*"] == "deny"
        assert bash["npm install*"] == "deny"
        assert bash["pip install*"] == "deny"
        assert bash["curl*"] == "deny"
        assert bash["wget*"] == "deny"

    def test_permission_block_denies_package_installers(self):
        # Criterion: deny-list bypasses via installers must be closed.
        commands = {"test": "pytest tests/"}
        block = oc_config.permission_block("/abs/hybrid-team-v1.0/scripts/devteam.py", commands)
        bash = block["bash"]
        for pattern in (
            "python -m pip install*",
            "python3 -m pip install*",
            "uv pip install*",
            "npm ci*",
            "npx*",
            "poetry add*",
            "brew install*",
            "go install*",
            "go get*",
            "gem install*",
        ):
            assert bash[pattern] == "deny", pattern

    def test_permission_block_denies_git_and_network_bypasses(self):
        # Criterion: git -C/-c option bypass and remote/network tools must be denied.
        commands = {"test": "pytest tests/"}
        block = oc_config.permission_block("/abs/hybrid-team-v1.0/scripts/devteam.py", commands)
        bash = block["bash"]
        for pattern in (
            "git -C*",
            "git -c*",
            "git pull*",
            "git fetch*",
            "git clone*",
            "git clean*",
            "git branch -D*",
            "git tag*",
            "scp*",
            "rsync*",
        ):
            assert bash[pattern] == "deny", pattern

    def test_permission_block_generic_deny_before_plan_command_allow(self):
        # Criterion: plan commands must win over generic denies — the plan's
        # own test/lint/typecheck allow rules must be ordered after every
        # generic deny rule so last-match-wins keeps them runnable even when
        # a broad deny (like npx*) would otherwise also match.
        commands = {"test": "pytest tests/", "lint": "ruff check .", "typecheck": "mypy ."}
        block = oc_config.permission_block("/abs/hybrid-team-v1.0/scripts/devteam.py", commands)
        bash = block["bash"]
        keys = list(bash.keys())
        deny_positions = [i for i, k in enumerate(keys) if bash[k] == "deny"]
        plan_allow_positions = [keys.index(k) for k in ("pytest tests/*", "ruff check .*", "mypy .*")]
        assert deny_positions and plan_allow_positions
        assert max(deny_positions) < min(plan_allow_positions)

    def test_plan_npx_command_allowed_over_generic_npx_deny(self):
        # Criterion: a plan test command starting with npx is allowed (its
        # allow rule comes after the npx* deny).
        commands = {"test": "npx vitest run"}
        block = oc_config.permission_block("/abs/hybrid-team-v1.0/scripts/devteam.py", commands)
        bash = block["bash"]
        assert bash["npx*"] == "deny"
        assert bash["npx vitest run*"] == "allow"
        keys = list(bash.keys())
        assert keys.index("npx vitest run*") > keys.index("npx*")
        assert _resolve(bash, "npx vitest run") == "allow"

    def test_non_plan_npx_and_npm_install_stay_denied(self):
        # Criterion: a non-plan command such as 'npx some-tool' and
        # 'npm install x' stays denied.
        commands = {"test": "npx vitest run"}
        block = oc_config.permission_block("/abs/hybrid-team-v1.0/scripts/devteam.py", commands)
        bash = block["bash"]
        assert _resolve(bash, "npx some-tool") == "deny"
        assert _resolve(bash, "npm install x") == "deny"

    def test_permission_block_none_commands_not_allowed(self):
        # Edge case: a plan command explicitly set to "none" must not become
        # an allow rule (it means "nothing to run here", not a real command).
        commands = {"test": "none", "lint": "none", "typecheck": "none"}
        block = oc_config.permission_block("/abs/hybrid-team-v1.0/scripts/devteam.py", commands)

        bash = block["bash"]
        assert "none*" not in bash
        for value in bash.values():
            assert value != "none"
        # deny rules and commit helpers still present regardless
        assert bash["git push*"] == "deny"
        assert bash["python3 /abs/hybrid-team-v1.0/scripts/devteam.py commit-green *"] == "allow"


class TestBuildConfig(unittest.TestCase):
    def test_build_config_embeds_agent_and_top_level_deny(self):
        commands = {"test": "pytest tests/"}
        config = oc_config.build_config(
            "You are ht-programmer.", "/abs/hybrid-team-v1.0/scripts/devteam.py", commands
        )

        agent = config["agent"][oc_config.AGENT_NAME]
        assert agent["prompt"] == "You are ht-programmer."
        assert agent["permission"]["edit"] == "allow"
        assert agent["permission"]["bash"]["pytest tests/*"] == "allow"
        assert agent["permission"]["bash"]["git push*"] == "deny"

        top = config["permission"]
        assert top["external_directory"] == "deny"
        assert top["bash"]["git push*"] == "deny"
        assert top["bash"]["curl*"] == "deny"
        assert "pytest tests/*" not in top["bash"]

    def test_build_config_denies_execute_tool(self):
        # opencode's `execute` tool runs JS with network access outside the bash deny-list.
        config = oc_config.build_config("p", "/abs/devteam.py", {})
        assert config["agent"][oc_config.AGENT_NAME]["permission"]["execute"] == "deny"
        assert config["permission"]["execute"] == "deny"


class TestConfigEnv(unittest.TestCase):
    def test_config_env_returns_json_serialized_config(self):
        commands = {"test": "pytest tests/"}
        env = oc_config.config_env(
            "You are ht-programmer.", "/abs/hybrid-team-v1.0/scripts/devteam.py", commands
        )

        assert list(env.keys()) == ["OPENCODE_CONFIG_CONTENT"]
        decoded = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        expected = oc_config.build_config(
            "You are ht-programmer.", "/abs/hybrid-team-v1.0/scripts/devteam.py", commands
        )
        assert decoded == expected

    def test_config_env_agent_top_level_deny_same_as_build_config(self):
        # Criterion: config_env returns OPENCODE_CONFIG_CONTENT JSON defining
        # agent ht-programmer with the same denies at top level.
        commands = {"test": "pytest tests/"}
        env = oc_config.config_env(
            "You are ht-programmer.", "/abs/hybrid-team-v1.0/scripts/devteam.py", commands
        )
        decoded = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        agent_deny = dict(
            (k, v) for k, v in decoded["agent"][oc_config.AGENT_NAME]["permission"]["bash"].items()
            if v == "deny"
        )
        assert agent_deny == decoded["permission"]["bash"]

    def test_constants(self):
        assert oc_config.AGENT_NAME == "ht-programmer"
        assert oc_config.SENTINEL == "HT-AGENT-OK"


if __name__ == "__main__":
    unittest.main()
