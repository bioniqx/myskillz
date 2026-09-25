"""Shared OpenCode harness: version detection and v1/v2 dialect rendering."""

import json
import os
import re
import subprocess
import threading
import time

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


THROTTLE_RE = re.compile(
    r'\\?"(?:code|status|statusCode|status_code)\\?"\s*:\s*\\?"?(?:429|1302|1305)(?!\d)'
    r"|\b429 Too Many Requests\b",
    re.I,
)
RUN_FLAGS = ["--dir", "--agent", "--model", "--format", "--auto"]


def check_run_flags(major: int, binary: str = "opencode") -> list:
    """Return the run flags missing from `opencode run --help` (v2 only)."""
    if major < 2:
        return []
    try:
        proc = subprocess.run([binary, "run", "--help"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return list(RUN_FLAGS)
    text = proc.stdout + proc.stderr
    return [f for f in RUN_FLAGS if not re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(f), text)]


def build_run_cmd(lane: dict, major: int, binary: str = "opencode") -> list:
    model = lane.get("model") or "pro"
    if "/" not in model:
        model = PROVIDER + "/" + MODELS.get(model, model)
    brief = lane["brief"]
    if os.path.isfile(brief):
        with open(brief) as f:
            brief = f.read()
    model_flag = "-m" if major < 2 else "--model"
    return [binary, "run", "--dir", lane.get("dir") or ".", "--agent", lane["agent"],
            model_flag, model, "--format", "json", "--auto", brief]


def _read_events(state):
    with open(state["out"], "w") as out:
        for line in state["proc"].stdout:
            out.write(line)
            out.flush()
            line = line.strip()
            if not line:
                continue
            state["last"] = time.monotonic()
            state["last_event"] = line[:500]
            if THROTTLE_RE.search(line):
                state["throttles"] += 1
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and (event.get("type") == "error" or "error" in event):
                state["error"] = line[:500]


def _last_line(path):
    try:
        with open(path) as f:
            lines = [line.strip() for line in f if line.strip()]
    except OSError:
        return ""
    return lines[-1][:500] if lines else ""


def _start_lane(lane, out_dir, major, binary, width):
    lane_id = str(lane["id"])
    err_path = os.path.join(out_dir, lane_id + ".err")
    err_file = open(err_path, "w")
    proc = subprocess.Popen(build_run_cmd(lane, major, binary), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=err_file, text=True, bufsize=1)
    now = time.monotonic()
    state = {"id": lane_id, "proc": proc, "err_path": err_path, "err_file": err_file,
             "out": os.path.join(out_dir, lane_id + ".jsonl"), "start": now, "last": now,
             "timeout": float(lane.get("timeout") or 0), "last_event": "", "error": "",
             "throttles": 0, "seen": 0, "width": width}
    state["reader"] = threading.Thread(target=_read_events, args=(state,), daemon=True)
    state["reader"].start()
    return state


def _absorb(state, width):
    while state["seen"] < state["throttles"]:
        state["seen"] += 1
        width = max(1, width // 2)
    return width


def _finish(state, status, out_dir):
    state["err_file"].close()
    code = state["proc"].returncode
    error = state["error"]
    if status is None:
        status = "OK" if code == 0 else "FAIL"
    if status == "FAIL" and not error:
        error = _last_line(state["err_path"])
    result = {"id": state["id"], "status": status, "exit": code, "error": error,
              "last_event": state["last_event"], "throttles": state["throttles"],
              "width": state["width"], "out": state["out"]}
    with open(os.path.join(out_dir, state["id"] + ".done"), "w") as f:
        json.dump(result, f, indent=2)
    return result


def run_lanes(lanes: list, out_dir: str, width: int = 8, stall: int = 180, binary: str = "opencode", major: int = 0) -> list:
    """Run one `opencode run` process per lane; write <id>.jsonl, <id>.err and <id>.done."""
    if not major:
        major = detect(binary)
    if not major:
        raise SystemExit("opencode not found: " + binary)
    missing = check_run_flags(major, binary)
    if missing:
        raise SystemExit("opencode run --help lacks flag(s): " + ", ".join(missing))
    os.makedirs(out_dir, exist_ok=True)
    width = max(1, min(int(width), 64))
    pending = list(lanes)
    running = []
    results = {}
    while pending or running:
        while pending and len(running) < width:
            running.append(_start_lane(pending.pop(0), out_dir, major, binary, width))
        time.sleep(0.05)
        for state in list(running):
            width = _absorb(state, width)
            status = None
            if state["proc"].poll() is None:
                now = time.monotonic()
                if now - state["last"] > stall:
                    status = "STALL"
                    state["error"] = "no event for %ss, last event: %s" % (stall, state["last_event"] or "none")
                elif state["timeout"] and now - state["start"] > state["timeout"]:
                    status = "TIMEOUT"
                    state["error"] = "timeout after %ss, last event: %s" % (state["timeout"], state["last_event"] or "none")
                else:
                    continue
                state["proc"].kill()
            state["proc"].wait()
            state["reader"].join()
            width = _absorb(state, width)
            running.remove(state)
            results[state["id"]] = _finish(state, status, out_dir)
    return [results[str(item["id"])] for item in lanes]
