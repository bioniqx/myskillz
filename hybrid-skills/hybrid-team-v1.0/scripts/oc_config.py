"""oc_config: injected opencode agent config, permission block, and prompt wiring for hybrid-team-programmer.

How opencode v2 decides (https://opencode.ai/docs/permissions, checked against v2.0.20):
- Every permission map becomes an ordered rule list and the LAST matching rule wins. A tool or a
  command that no rule matches is allowed, so every map here starts with "*": "deny".
- A shell line is parsed and every command in it (chained, piped, nested in $(...) or backticks) is
  matched on its own, as its full text including env prefixes and redirections. `*` matches any
  characters, and a pattern that ends in " *" also matches the bare command.

shortcut: the pinned test/lint/typecheck/build commands run model-written code with the user's
rights, so a test file can still reach the network or read any file the user can. Permission rules
cannot stop that; the ceiling is "no direct shell escape". Upgrade path: run the lane inside an OS
sandbox (sandbox-exec, bwrap or a container) with no network and a worktree-only filesystem.
"""
import copy
import json
import os
import re

AGENT_NAME = "hybrid-team-programmer"
SENTINEL = "HT-AGENT-OK"

READ_ONLY_GIT = ("git status *", "git diff *", "git log *", "git show *")

READ_ONLY_TOOLS = ("ls *", "cat *", "head *", "tail *", "wc *", "grep *", "rg *", "find *")

COMMIT_HELPERS = ("commit-red", "commit-green", "commit-work", "commit-fast")

# `verify` is the slice's own evidence command (chore/docs/perf), which the briefing calls pre-approved.
COMMAND_KEYS = ("build", "test", "test_file", "lint", "lint_file", "typecheck", "typecheck_file", "bench", "verify")

# Same text as devteam.isolation_prefix(), with the per-slice values wildcarded.
ISOLATION_PREFIX = "PORT=* DB_SUFFIX=* TMPDIR=.slice/tmp "

# Applied after the read-only allows only: flags that make a reader write or execute, and quoting or
# globbing that hides a secret path from the text patterns below.
INSPECTION_DENY = (
    "find*-exec*", "find*-ok*", "find*-delete*", "find*-fprint*", "find*-fls*",
    "rg*--pre*", "rg*--hostname*", "rg*--hyperlink*",
    "git*--output*", "git*--ext-diff*",
    # Quotes are needed by find/grep/rg, but not by the readers that could name a secret file.
    "cat*'*", "cat*\"*", "cat*[*", "head*'*", "head*\"*", "head*[*", "tail*'*", "tail*\"*", "tail*[*",
    "wc*'*", "wc*\"*", "wc*[*", "git*'*", "git*\"*", "git*[*",
)

# Applied after the pinned commands, so they also cover them: absolute or parent paths, expansions,
# redirections and secret file names. The commit helpers are re-allowed after this block.
PATH_DENY = (
    "*$*", "*`*", "*~*", "*..*", "*>*", "*<*", "* /*", "*=/*", "*-?/*",
    "*LD_PRELOAD*", "*DYLD_*", "*PYTHONPATH*", "*NODE_OPTIONS*", "*BASH_ENV*",
    "*.env", "*.env *", "*.env.*", "*.ssh*", "*.pem*", "*.key*", "*id_rsa*", "*id_ed25519*",
    "*.npmrc*", "*.netrc*", "*.aws*",
)

# Applied last: the helpers take a free-text message but never a redirection or an expansion.
LAST_DENY = ("*>*", "*<*", "*$*", "*`*")

SECRET_READ_DENY = ("*.env", "*.env.*", "*.ssh/*", "*.pem", "*.key", "*id_rsa*", "*id_ed25519*", "*.npmrc", "*.netrc", "*.aws/*")


def tool_output_glob() -> str:
    """Allow glob for opencode's saved (truncated) tool output, e.g. a long test log."""
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "opencode", "tool-output") + "/*"


def bash_block(engine: str, commands: dict) -> dict:
    bash = {"*": "deny"}
    for pattern in READ_ONLY_TOOLS + READ_ONLY_GIT:
        bash[pattern] = "allow"
    for pattern in INSPECTION_DENY:
        bash[pattern] = "deny"
    for name in COMMAND_KEYS:
        # opencode matches each command of a chain on its own, so allow every part of a pinned chain
        # ("stylua --check {files} && selene {files}" must allow "selene <file>" too).
        # Operators inside quotes (python3 -c "a; b") do not split: the lookahead needs balanced quotes after it.
        for part in re.split(r"""(?:&&|\|\||;|\|)(?=(?:[^"']|"[^"]*"|'[^']*')*$)""", str(commands.get(name) or "")):
            cmd = part.split("{files}")[0].strip()
            if cmd and cmd.lower() not in ("none", "n/a", "-"):
                tail = "*" if cmd.endswith("/") else " *"  # "pytest tests/" also covers "pytest tests/unit"
                bash[cmd + tail] = "allow"
                bash[ISOLATION_PREFIX + cmd + tail] = "allow"
    for pattern in PATH_DENY:
        bash[pattern] = "deny"
    for sub in COMMIT_HELPERS:
        bash["python3 %s %s *" % (engine, sub)] = "allow"
    for pattern in LAST_DENY:
        bash.pop(pattern, None)  # re-insert so the rule sits after the helper allows (last match wins)
        bash[pattern] = "deny"
    return bash


def permission_block(engine: str, commands: dict) -> dict:
    read = {"*": "allow"}
    read.update((pat, "deny") for pat in SECRET_READ_DENY)
    return {
        "*": "deny",  # unknown and future tools
        "read": read,
        # The engine's .slice state and the git pointer are never edited by the model (a lane that rewrote
        # .slice/footprint would defeat the stop gate); the commit helpers write them, not the edit tool.
        "edit": {"*": "allow", ".slice/**": "deny", "**/.slice/**": "deny", ".git": "deny", ".git/**": "deny", "**/.git/**": "deny"},
        "grep": "allow",
        "glob": "allow",
        "list": "allow",
        "todowrite": "allow",
        "bash": bash_block(engine, commands),
        # opencode v2.0.22 names the shell tool "shell"; same rules, or every lane's gate is denied.
        "shell": bash_block(engine, commands),
        "webfetch": "deny",
        "websearch": "deny",
        "task": "deny",
        "skill": "deny",
        "external_directory": {"*": "deny", tool_output_glob(): "allow"},
    }


def build_config(prompt_text: str, engine: str, commands: dict) -> dict:
    perm = permission_block(engine, commands)
    return {
        "agent": {
            AGENT_NAME: {
                "description": "opencode-backed implementer for hybrid-team low-judgment slices.",
                "mode": "primary",
                "prompt": prompt_text,
                "permission": perm,
            }
        },
        # Repeated at top level so a silent fallback to another agent is still fenced.
        "permission": copy.deepcopy(perm),
    }


def config_env(prompt_text: str, engine: str, commands: dict) -> dict:
    return {
        "OPENCODE_CONFIG_CONTENT": json.dumps(build_config(prompt_text, engine, commands)),
        # The target repo's opencode.json, .opencode/ plugins, MCP servers and AGENTS.md are never loaded.
        "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
    }
