"""oc_config: injected opencode agent config, permission block, and prompt wiring for ht-programmer."""
import json

AGENT_NAME = "ht-programmer"
SENTINEL = "HT-AGENT-OK"

READ_ONLY_GIT = ("git status*", "git diff*", "git log*", "git show*")

COMMIT_HELPERS = ("commit-red", "commit-green", "commit-work", "commit-fast")

DENY_BASH = (
    "git push*",
    "git reset*",
    "git rebase*",
    "git commit*",
    "git merge*",
    "git checkout*",
    "git switch*",
    "git stash*",
    "git worktree*",
    "git -C*",
    "git -c*",
    "git pull*",
    "git fetch*",
    "git clone*",
    "git clean*",
    "git branch -D*",
    "git tag*",
    "npm install*",
    "npm i*",
    "npm ci*",
    "npx*",
    "pip install*",
    "pip3 install*",
    "python -m pip install*",
    "python3 -m pip install*",
    "uv pip install*",
    "yarn add*",
    "pnpm add*",
    "uv add*",
    "poetry add*",
    "brew install*",
    "go install*",
    "go get*",
    "gem install*",
    "cargo install*",
    "curl*",
    "wget*",
    "nc*",
    "ssh*",
    "scp*",
    "rsync*",
)


def permission_block(engine: str, commands: dict) -> dict:
    bash = {}
    for sub in COMMIT_HELPERS:
        bash["python3 %s %s *" % (engine, sub)] = "allow"
    for pattern in READ_ONLY_GIT:
        bash[pattern] = "allow"
    for pattern in DENY_BASH:
        bash[pattern] = "deny"
    for name in ("test", "lint", "typecheck"):
        cmd = commands.get(name)
        if cmd and cmd != "none":
            bash[cmd + "*"] = "allow"
    return {
        "edit": "allow",
        "bash": bash,
        "execute": "deny",
        "external_directory": "deny",
    }


def build_config(prompt_text: str, engine: str, commands: dict) -> dict:
    perm = permission_block(engine, commands)
    top_level_bash_deny = dict((k, v) for k, v in perm["bash"].items() if v == "deny")
    return {
        "agent": {
            AGENT_NAME: {
                "description": "opencode-backed implementer for hybrid-team low-judgment slices.",
                "mode": "primary",
                "prompt": prompt_text,
                "permission": perm,
            }
        },
        "permission": {
            "bash": top_level_bash_deny,
            "execute": "deny",
            "external_directory": "deny",
        },
    }


def config_env(prompt_text: str, engine: str, commands: dict) -> dict:
    return {"OPENCODE_CONFIG_CONTENT": json.dumps(build_config(prompt_text, engine, commands))}
