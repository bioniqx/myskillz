"""Shared OpenCode harness: version detection and v1/v2 dialect rendering."""

import json
import re
import subprocess

PROVIDER = "zai-coding-plan"
MODELS = {"flash": "glm-5.3-flash", "pro": "glm-5.3"}


def detect(binary: str = "opencode") -> int:
    try:
        result = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, OSError):
        return 0
    text = (result.stdout or "") + (result.stderr or "")
    match = re.search(r"(\d+)\.\d+\.\d+", text)
    if not match:
        return 0
    return int(match.group(1))


def parse_frontmatter(text: str) -> tuple:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return ({}, text)
    fields = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "true":
                value = True
            elif value == "false":
                value = False
            elif re.match(r"^-?\d+$", value):
                value = int(value)
            elif re.match(r"^-?\d+\.\d+$", value):
                value = float(value)
            fields[key] = value
        i += 1
    body = "\n".join(lines[i + 1:]).strip("\n")
    return (fields, body)


def render_agent(text: str, major: int) -> str:
    fields, body = parse_frontmatter(text)
    description = fields.get("description", "")
    model_key = fields.get("model", "pro")
    model_id = "{}/{}".format(PROVIDER, MODELS[model_key])
    effort = fields.get("effort", "high")
    steps = fields.get("steps")
    access = fields.get("access", "read")
    bash = fields.get("bash", False)
    web = fields.get("web", False)
    temperature = fields.get("temperature")

    edit_perm = "allow" if access == "write" else "deny"
    bash_perm = "allow" if bash else "deny"
    web_perm = "allow" if web else "deny"

    lines = ["---"]
    lines.append("description: {}".format(json.dumps(description)))
    lines.append("mode: subagent")
    lines.append("hidden: true")
    lines.append("model: {}".format(model_id))
    if major == 1:
        if temperature is not None:
            lines.append("temperature: {}".format(temperature))
        if steps is not None:
            lines.append("steps: {}".format(steps))
        lines.append("permission:")
        lines.append("  edit: {}".format(edit_perm))
        lines.append("  bash: {}".format(bash_perm))
        lines.append("  webfetch: {}".format(web_perm))
        lines.append("reasoningEffort: {}".format(effort))
    else:
        if steps is not None:
            lines.append("steps: {}".format(steps))
        lines.append("permissions:")
        for action, effect in (("edit", edit_perm), ("bash", bash_perm), ("webfetch", web_perm)):
            lines.append("  - action: {}".format(action))
            lines.append('    resource: "*"')
            lines.append("    effect: {}".format(effect))
        lines.append("request:")
        lines.append("  body:")
        lines.append("    reasoning_effort: {}".format(effort))
        if temperature is not None:
            lines.append("    temperature: {}".format(temperature))
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines)


def render_command(text: str, major: int, skill_dir: str) -> str:
    fields, body = parse_frontmatter(text)
    description = fields.get("description", "")
    rendered_body = body.replace("{{SKILL_DIR}}", skill_dir)
    lines = ["---", "description: {}".format(json.dumps(description)), "---", "", rendered_body]
    return "\n".join(lines)


def config_snippet(major: int, deny: list) -> str:
    config = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            PROVIDER: {
                "models": {
                    MODELS["pro"]: {},
                    MODELS["flash"]: {},
                }
            }
        },
        "mcp": {
            "web-search-prime": {
                "type": "remote",
                "url": "https://api.z.ai/api/mcp/web_search_prime/mcp",
                "headers": {"Authorization": "Bearer {env:ZAI_API_KEY}"},
            }
        },
    }
    if deny:
        config["permission"] = {"skill": {pattern: "deny" for pattern in deny}}
    return json.dumps(config, indent=2)
