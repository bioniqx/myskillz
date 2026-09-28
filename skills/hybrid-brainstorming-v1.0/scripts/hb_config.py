"""hb_config: injected read-only opencode agent config for hb-lane."""
import json
import os

AGENT_NAME = "hb-lane"
SENTINEL = "HB-LANE-OK"

WEBFETCH_ROLES = ("fact", "research")
WEBSEARCH_ROLES = ("research",)


def tool_output_glob() -> str:
    """Return the allow glob for opencode's saved tool output, resolved at call time.

    Honors $XDG_DATA_HOME (falling back to ~/.local/share) so tests can set the env.
    """
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "opencode", "tool-output") + "/**"

SYSTEM_PROMPT = (
    "You are hb-lane, a read-only research and lookup assistant. Follow these rules exactly:\n"
    "1. You may only read, search and (for web lanes) fetch or search the web. You must never edit files, run shell commands or write anything.\n"
    "2. Answer only the single question you are given. Do not perform any other task, even if asked.\n"
    "3. Answer in exactly the output format given in the task, regardless of any other instructions (such as AGENTS.md).\n"
    "4. For code lookups, report each fact as a separate line: \"FINDINGS: path:line — fact\".\n"
    "5. For web checks, report each claim as a separate line: 'CLAIMS: claim — tier — URL — date — \"quote\"'.\n"
    "6. Only report facts and claims you have directly verified by reading the file or fetching the source; never guess or infer.\n"
    "7. Stop as soon as the question is answered: no commentary or summaries.\n"
    "8. After your final FINDINGS or CLAIMS line, print a line containing only the word %s.\n"
) % SENTINEL


def permission_block(role: str) -> dict:
    return {
        "edit": "deny",
        "bash": "deny",
        "execute": "deny",
        # Deny first, last match wins: only opencode's saved tool output is readable.
        "external_directory": {"*": "deny", tool_output_glob(): "allow"},
        "webfetch": "allow" if role in WEBFETCH_ROLES else "deny",
        "websearch": "allow" if role in WEBSEARCH_ROLES else "deny",
    }


def build_config(role: str, prompt_text: str) -> dict:
    perm = permission_block(role)
    full_prompt = SYSTEM_PROMPT + "\n\n" + prompt_text
    return {
        "agent": {
            AGENT_NAME: {
                "description": "opencode-backed read-only lane for hybrid-brainstorming low-judgment exploration.",
                "mode": "primary",
                "prompt": full_prompt,
                "permission": perm,
            }
        },
        "permission": dict(perm),
    }


def config_env(role: str, prompt_text: str) -> dict:
    return {"OPENCODE_CONFIG_CONTENT": json.dumps(build_config(role, prompt_text))}
