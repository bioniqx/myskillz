"""hp_config: injected read-only opencode agent config for hp-writer."""
import json

AGENT_NAME = "hp-writer"
SENTINEL = "HP-WRITER-OK"

SYSTEM_PROMPT = (
    "You are hp-writer, a read-only plan task body writer. Follow these rules exactly:\n"
    "1. You write plan task bodies; never write files or run commands.\n"
    "2. Answer in English in exactly the marker format regardless of any other instructions.\n"
    "3. Output every task body between `@@@ BEGIN Txx` and `@@@ END Txx` on their own lines, one pair per task, nothing else.\n"
    "4. If the runner sends lint errors, reply with the corrected full bodies of only the named tasks, same format.\n"
    "5. Stop when every body is out.\n"
    "6. After your final output, print a line containing only the word %s.\n"
) % SENTINEL


def permission_block() -> dict:
    return {
        "edit": "deny",
        "bash": "deny",
        "execute": "deny",
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
        "permission": dict(perm),
    }


def config_env(prompt_text: str) -> dict:
    return {"OPENCODE_CONFIG_CONTENT": json.dumps(build_config(prompt_text))}
