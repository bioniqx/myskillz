"""hp_config: injected read-only opencode agent config for hybrid-plan-writer.

opencode v2 turns every permission map into an ordered rule list and the last matching rule wins
(https://opencode.ai/docs/permissions), so the block starts with "*": "deny".
"""
import copy
import json

AGENT_NAME = "hybrid-plan-writer"
SENTINEL = "HP-WRITER-OK"

# Secrets stay unreadable even where reads are open: --auto would approve opencode's default "ask".
# `*` also matches "/", so each pattern covers every directory depth.
SECRET_READ_DENY = ("*.env", "*.env.*", "*.ssh/*", "*.pem", "*.key", "*id_rsa*", "*id_ed25519*")

# The free opencode tier answers 403 when the shell tool is fully denied, so one harmless exact
# command stays allowed. Nested and chained commands are matched one by one and hit "*": "deny".
READ_ONLY_BASH = {"*": "deny", "ls": "allow"}

SYSTEM_PROMPT = (
    "You are hybrid-plan-writer, a read-only plan task body writer. Follow these rules exactly:\n"
    "1. You write plan task bodies; never write files or run commands.\n"
    "2. Answer in English in exactly the marker format regardless of any other instructions.\n"
    "3. Output every task body between `@@@ BEGIN Txx` and `@@@ END Txx` on their own lines, one pair per task, nothing else.\n"
    "4. If the runner sends lint errors, reply with the corrected full bodies of only the named tasks, same format.\n"
    "5. Stop when every body is out.\n"
    "6. After your final output, print a line containing only the word %s.\n"
) % SENTINEL


def permission_block() -> dict:
    read = {"*": "allow"}
    read.update((pat, "deny") for pat in SECRET_READ_DENY)
    return {
        "*": "deny",  # unknown and future tools
        "read": read,
        "grep": "allow",
        "glob": "allow",
        "list": "allow",
        "edit": "deny",
        "bash": dict(READ_ONLY_BASH),
        "task": "deny",
        "skill": "deny",
        "webfetch": "deny",
        "websearch": "deny",
        "external_directory": "deny",
    }


def build_config(prompt_text: str) -> dict:
    perm = permission_block()
    full_prompt = SYSTEM_PROMPT + "\n\n" + prompt_text
    return {
        "agent": {
            AGENT_NAME: {
                "description": "opencode-backed plan task body writer for hybrid-writing-plans.",
                "mode": "primary",
                "prompt": full_prompt,
                "permission": perm,
            }
        },
        "permission": copy.deepcopy(perm),
    }


def config_env(prompt_text: str) -> dict:
    return {
        "OPENCODE_CONFIG_CONTENT": json.dumps(build_config(prompt_text)),
        # The target repo's opencode.json, .opencode/ plugins, MCP servers and AGENTS.md are never loaded.
        "OPENCODE_DISABLE_PROJECT_CONFIG": "1",
    }
