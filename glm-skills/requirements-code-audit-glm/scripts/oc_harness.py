"""Shared OpenCode harness: version detection and v1/v2 dialect rendering."""

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

PROVIDER = "zai-coding-plan"
MODELS = {"flash": "glm-5.3-flash", "pro": "glm-5.3"}
EFFORTS = ("low", "high", "max")
MAX_PARALLEL = 8  # the provider allows 8 concurrent API calls; provider cap, keep in sync: _shared/zai_client.py MAX_PARALLEL
DEFAULT_LANES = 6  # default agent/OpenCode lane width; OC_MAX_LANES may raise it up to MAX_PARALLEL


def detect(binary: str = "opencode") -> int:
    try:
        result = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, timeout=10
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return 0
    text = (result.stdout or "") + (result.stderr or "")
    match = re.search(r"(\d+)\.\d+\.\d+", text)
    if not match:
        return 0
    return int(match.group(1))


OC_SKILL_DIRS = (os.path.join(".opencode", "skills"), os.path.join(".config", "opencode", "skills"))
MAJOR_MARKER = ".oc-major"


def _skill_dir_for(script_path):
    """The skill folder of a script: its parent, or the parent's parent for a `scripts/` dir."""
    folder = os.path.dirname(os.path.abspath(script_path))
    return os.path.dirname(folder) if os.path.basename(folder) == "scripts" else folder


def _has_part(path, rel):
    return (os.sep + rel.strip(os.sep) + os.sep) in path


def _within(path, root):
    for base in (os.path.abspath(root), os.path.realpath(root)):
        base = base.rstrip(os.sep)
        if path == base or path.startswith(base + os.sep):
            return True
    return False


def harness(script_path: str = "") -> str:
    """Return 'opencode', 'claude', 'zcode' or 'unknown' for the harness running script_path.

    v2.0.18 sets only OPENCODE_TERMINAL=1 in shell children, so the script location and the
    install marker count as evidence too. script_path defaults to this module's own file."""
    env = os.environ
    if env.get("OPENCODE") or env.get("OPENCODE_TERMINAL") \
            or env.get("DEVTEAM_HARNESS", "").strip().lower() == "opencode":
        return "opencode"
    script = os.path.abspath(script_path or __file__)
    paths = [script, os.path.realpath(script)]
    config_dir = env.get("OPENCODE_CONFIG_DIR", "")
    for path in paths:
        if any(_has_part(path, rel) for rel in OC_SKILL_DIRS):
            return "opencode"
        if config_dir and _within(path, config_dir):
            return "opencode"
    for folder in (os.path.dirname(script), _skill_dir_for(script)):
        if os.path.isfile(os.path.join(folder, MAJOR_MARKER)):
            return "opencode"
    if env.get("CLAUDECODE") or any(k.startswith("CLAUDE_CODE") for k in env):
        return "claude"
    if any(k.startswith(("ZCODE", "Z_CODE")) for k in env):
        return "zcode"
    for path in paths:
        if _has_part(path, ".zcode"):
            return "zcode"
        if _has_part(path, ".claude"):
            return "claude"
    return "unknown"


_DETECT_CACHE = {}


def _read_marker(skill_dir):
    try:
        with open(os.path.join(skill_dir, MAJOR_MARKER)) as fh:
            value = int(fh.read().strip())
    except (OSError, ValueError):
        return 0
    return value if value > 0 else 0


def major(skill_dir: str = "", binary: str = "opencode") -> int:
    """OpenCode major version: the skill's .oc-major marker first, then detect() cached per binary.

    skill_dir defaults to the skill folder holding this module. 0 means unknown / not found."""
    found = _read_marker(skill_dir or _skill_dir_for(__file__))
    if found:
        return found
    if binary not in _DETECT_CACHE:
        _DETECT_CACHE[binary] = detect(binary)
    return _DETECT_CACHE[binary]


FALLBACK_AGENT = "general"
NON_OC_AGENTS = ("general-purpose", "Explore")


def dispatch_line(agent: str, prompt_path: str, description: str, major: int, background: bool = True) -> str:
    """The tool call a model copies to start one lane.

    v1: task(subagent_type=..., description=..., prompt=...). v2: the renamed dispatch tool with
    agent/description/prompt/background. Never emits a model alias: v2 rejects a model not written
    provider/model. Unknown or Claude-only agent names fall back to the built-in `general`."""
    name = (agent or "").strip()
    if not name or name in NON_OC_AGENTS:
        name = FALLBACK_AGENT
    prompt = "Read %s and follow it exactly." % prompt_path
    quoted = [json.dumps(value, ensure_ascii=False) for value in (name, description, prompt)]
    if major >= 2:
        return "subagent(agent=%s, description=%s, prompt=%s, background=%s)" % (
            quoted[0], quoted[1], quoted[2], "true" if background else "false")
    return "task(subagent_type=%s, description=%s, prompt=%s)" % (quoted[0], quoted[1], quoted[2])


def _harness_line(script_path: str = "") -> str:
    """`<harness> <major>` for the CLI; major stays 0 outside OpenCode so no binary is spawned."""
    script = script_path or __file__
    name = harness(script)
    found = major(_skill_dir_for(script)) if name == "opencode" else 0
    return "%s %d" % (name, found)


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
            if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                try:
                    value = json.loads(value)
                except ValueError:
                    value = value[1:-1]
            elif value == "true":
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
    model_id = MODELS.get(model_key, model_key)
    if "/" not in model_id:
        model_id = "{}/{}".format(PROVIDER, model_id)
    effort = fields.get("effort", "high")
    steps = fields.get("steps")
    access = fields.get("access", "read")
    bash = fields.get("bash", False)
    web = fields.get("web", False)
    temperature = fields.get("temperature")
    write_paths = fields.get("write_paths") if access == "write" else None

    edit_perm = "allow" if access == "write" else "deny"
    bash_perm = "allow" if bash else "deny"
    web_perm = "allow" if web else "deny"

    lines = ["---"]
    lines.append("description: {}".format(json.dumps(description)))
    # v1 `opencode run --agent` silently falls back to the default agent for a `mode: subagent` agent
    lines.append("mode: {}".format("all" if major == 1 else "subagent"))
    lines.append("hidden: true")
    lines.append("model: {}".format(model_id))
    if major == 1:
        if temperature is not None:
            lines.append("temperature: {}".format(temperature))
        if steps is not None:
            lines.append("steps: {}".format(steps))
        lines.append("permission:")
        if write_paths:
            lines.append("  edit:")
            lines.append('    "*": deny')
            lines.append('    "{}": allow'.format(write_paths))
        else:
            lines.append("  edit: {}".format(edit_perm))
        lines.append("  bash: {}".format(bash_perm))
        lines.append("  webfetch: {}".format(web_perm))
        if write_paths:
            lines.append("  task: deny")
        lines.append("reasoningEffort: {}".format(effort))
    else:
        if steps is not None:
            lines.append("steps: {}".format(steps))
        if temperature is not None:
            lines.append("temperature: {}".format(temperature))
        # Verified against the installed opencode v2.0.16 binary (strings):
        # AgentConfig.permission is PermissionConfig, the same nested-map
        # shape v1 uses -- not the {action, resource, effect} rule list
        # (that shape is the runtime Permission.Ruleset, never the agent
        # frontmatter schema). Object keys are read, edit, glob, grep,
        # list, bash, shell, task, external_directory, webfetch, skill, ...
        # opencode v2.0.22 names the shell tool "shell": an agent that sets
        # only "bash" has every shell command denied, so both keys are
        # written with the same value.
        lines.append("permission:")
        if write_paths:
            lines.append("  edit:")
            lines.append('    "*": deny')
            lines.append('    "{}": allow'.format(write_paths))
        else:
            lines.append("  edit: {}".format(edit_perm))
        lines.append("  bash: {}".format(bash_perm))
        lines.append("  shell: {}".format(bash_perm))
        lines.append("  webfetch: {}".format(web_perm))
        if write_paths:
            lines.append("  task: deny")
        # v2 gates websearch separately from webfetch; an explicit value keeps a headless lane from
        # opening the interactive provider form. `execute` is v2's code-mode tool, which would run
        # code outside the `bash` permission, so it is always denied.
        lines.append("  websearch: {}".format(web_perm))
        lines.append("  execute: deny")
        # v2 applies the agent's variant when the `subagent` tool dispatches it; with no variant GLM
        # runs at max. `opencode run --model` overrides it, so build_run_cmd adds the #variant suffix.
        if effort in EFFORTS:
            lines.append("variant: {}".format(effort))
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


WEBSEARCH_NOTE = (
    "websearch: OpenCode v2 needs a websearch provider. Without one, a headless lane that calls",
    "websearch opens an interactive form and times out. Option: keep the web-search-prime MCP",
    "server below (it reads ZAI_API_KEY), or render agents with web: false.",
    "variants: low/high/max set reasoningEffort, so `--model zai-coding-plan/glm-5.3#max` resolves.",
)


def config_snippet(major: int, deny: list) -> str:
    # Verified against the installed opencode v2.0.16 binary: `permission` is `PermissionConfig`, the same nested-map shape ({"skill": {"<name>": "deny"}}) in both major 1 and major 2.
    # v2 `#max` fails with "Variant unavailable" unless the provider model defines `variants.max`.
    # The result is JSONC (OpenCode parses opencode.json as JSONC): `//` note lines, then the object.
    variants = {effort: {"reasoningEffort": effort} for effort in EFFORTS}
    config = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            PROVIDER: {
                "models": {
                    MODELS["pro"]: {"variants": dict(variants)},
                    MODELS["flash"]: {"variants": dict(variants)},
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
    notes = ["// " + line for line in WEBSEARCH_NOTE]
    return "\n".join(notes) + "\n" + json.dumps(config, indent=2)


THROTTLE_CODES = ("1302", "1305")


def _is_429(value) -> bool:
    return value is not None and str(value).strip() == "429"


def _zai_code(body) -> str:
    """The Z.ai error code inside a v1 `responseBody` (a JSON string or an object), or ""."""
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return ""
    if not isinstance(body, dict):
        return ""
    err = body.get("error")
    code = err.get("code") if isinstance(err, dict) else body.get("code")
    return "" if code is None else str(code)


def is_throttle_event(event: dict) -> bool:
    """True only for an OpenCode error event that reports a rate limit.

    v2: `{"type":"error","error":{"type":"provider.rate-limit","status":429}}` (or any status 429).
    v1: `error.name == "APIError"` with `data.statusCode` 429, or a `data.responseBody` Z.ai code
    1302/1305. Tool output, text and step events never count, whatever numbers they quote.
    """
    if not isinstance(event, dict) or event.get("type") != "error":
        return False
    err = event.get("error")
    if not isinstance(err, dict):
        return False
    if err.get("type") == "provider.rate-limit" or _is_429(err.get("status")):
        return True
    data = err.get("data")
    if err.get("name") != "APIError" or not isinstance(data, dict):
        return False
    return _is_429(data.get("statusCode")) or _zai_code(data.get("responseBody")) in THROTTLE_CODES


RUN_FLAGS = ["--agent", "--model", "--format", "--auto", "--standalone"]


def check_run_flags(major: int, binary: str = "opencode") -> list:
    """Return the run flags missing from `opencode run --help` (v2 only)."""
    if major < 2:
        return []
    # to a file, not a pipe: v2 exits before flushing piped help output past ~512 bytes
    try:
        with tempfile.TemporaryFile() as out:
            subprocess.run([binary, "run", "--help"], stdout=out, stderr=subprocess.STDOUT, timeout=30)
            out.seek(0)
            text = out.read().decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired):
        return list(RUN_FLAGS)
    return [f for f in RUN_FLAGS if not re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(f), text)]


def build_run_cmd(lane: dict, major: int, binary: str = "opencode") -> list:
    """The `opencode run` argv for one lane. The brief is NOT in argv: _start_lane writes it to
    the process's stdin and closes stdin. v2 wraps a whitespace argv message in literal quotes and
    parses a leading `-` as a flag, and Linux argv hits E2BIG past 128 KiB."""
    model = lane.get("model") or "pro"
    if "/" not in model:
        model = PROVIDER + "/" + MODELS.get(model, model)
    # v2 takes effort only as a model variant (`glm-5.3#high`); v1 takes it from the agent's
    # frontmatter `reasoningEffort` and rejects the suffix.
    if major >= 2 and lane.get("effort") in EFFORTS:
        model += "#" + lane["effort"]
    if major < 2:
        # Absolute, so opencode's own --dir resolution can't re-resolve it a
        # second time against the subprocess cwd _start_lane already set to
        # this same directory (which would turn "docs" into "docs/docs").
        lane_dir = os.path.abspath(lane.get("dir") or ".")
        return [binary, "run", "--dir", lane_dir, "--agent", lane["agent"],
                "-m", model, "--format", "json", "--auto"]
    # v2 has no --dir flag; the lane's working directory is instead passed as
    # the subprocess cwd (see _start_lane). --standalone runs a private
    # server in this process instead of talking to opencode's managed
    # background service, so the plugin sees this process's env
    # (DEVTEAM_ROLE/DEVTEAM_SLICE) instead of running inside a shared,
    # long-lived service process.
    return [binary, "run", "--standalone", "--agent", lane["agent"], "--model", model,
            "--format", "json", "--auto"]


def _lane_brief(lane):
    """The lane's brief text: the file's content when `brief` names a file, else the string itself."""
    brief = lane["brief"]
    if os.path.isfile(brief):
        with open(brief) as f:
            return f.read()
    return brief


def _feed_stdin(proc, brief):
    """Write the brief to the lane's stdin, then close it: v2 hangs while stdin stays open."""
    try:
        proc.stdin.write(brief)
    except (OSError, ValueError):
        pass
    finally:
        try:
            proc.stdin.close()
        except (OSError, ValueError):
            pass


STALL_BY_ROLE = {"programmer": 900, "programmer-lite": 900, "team-leader": 900, "code-reviewer": 600, "spot-reviewer": 600, "investigator": 600}


def lane_stall(lane: dict, default: int = 180) -> int:
    """Seconds without a JSON event before a lane counts as stalled.

    v2 emits events only at step and part boundaries, so a long shell call or long thinking is
    silent. Order: the lane's own positive `stall`, then STALL_BY_ROLE for its `role`, its env
    `DEVTEAM_ROLE` or its `agent` name, then `default`.
    """
    value = lane.get("stall")
    try:
        if value is not None and int(value) > 0:
            return int(value)
    except (TypeError, ValueError):
        pass
    env = lane.get("env") or {}
    for key in (lane.get("role"), env.get("DEVTEAM_ROLE"), lane.get("agent")):
        if isinstance(key, str) and key in STALL_BY_ROLE:
            return STALL_BY_ROLE[key]
    return int(default)


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
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            # Only error events feed the governor: tool output quoting "429" or "1302" never does.
            if is_throttle_event(event):
                state["throttles"] += 1
            if event.get("type") == "aborted":
                state["aborted"] = True
                state["error"] = line[:500]
            elif event.get("type") == "error" or event.get("error"):
                state["error"] = line[:500]


def _last_line(path):
    try:
        with open(path) as f:
            lines = [line.strip() for line in f if line.strip()]
    except OSError:
        return ""
    return lines[-1][:500] if lines else ""


def _start_lane(lane, out_dir, major, binary, width, stall=180):
    lane_id = str(lane["id"])
    err_path = os.path.join(out_dir, lane_id + ".err")
    err_file = open(err_path, "w")
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (lane.get("env") or {}).items()})
    cwd = os.path.abspath(lane.get("dir") or ".")
    # v2 --standalone takes its project root from $PWD, not the real cwd: an inherited PWD would
    # point the lane's file tools at the caller's directory.
    env["PWD"] = cwd
    try:
        brief = _lane_brief(lane)
        proc = subprocess.Popen(build_run_cmd(lane, major, binary), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=err_file, text=True, bufsize=1, env=env,
                                start_new_session=True, cwd=cwd)
    except OSError as exc:
        # A bad lane dir, an unreadable brief file or any other spawn failure
        # must not crash the whole wave; the caller turns this into a per-lane FAIL result.
        err_file.close()
        return {"id": lane_id, "start_error": str(exc)}
    # start_new_session=True makes the lane its own process-group leader (pgid == pid); callers
    # may os.killpg() the number in <out_dir>/<lane id>.pgid while the lane runs.
    pgid_path = os.path.join(out_dir, lane_id + ".pgid")
    with open(pgid_path, "w") as fh:
        fh.write(str(proc.pid))
    now = time.monotonic()
    state = {"id": lane_id, "proc": proc, "err_path": err_path, "err_file": err_file,
             "out": os.path.join(out_dir, lane_id + ".jsonl"), "start": now, "last": now,
             "timeout": float(lane.get("timeout") or 0), "last_event": "", "error": "",
             "throttles": 0, "seen": 0, "width": width, "stall": lane_stall(lane, stall),
             "pgid_path": pgid_path, "lane": lane}
    state["reader"] = threading.Thread(target=_read_events, args=(state,), daemon=True)
    state["reader"].start()
    # A separate thread, so a brief larger than the pipe buffer can't block the scheduler.
    threading.Thread(target=_feed_stdin, args=(proc, brief), daemon=True).start()
    return state


def _kill_group(proc):
    """Kill the lane's whole process group, not just its immediate pid, so a
    child that inherited our stdout pipe (and would otherwise keep it open
    forever) dies too. `_start_lane` passes start_new_session=True, which makes
    the process group id equal proc.pid, so this still works even after
    proc.poll()/wait() has already reaped the leader (getpgid(proc.pid) would
    fail at that point; proc.pid stays valid to killpg regardless)."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def _drop_pgid(state):
    path = state.get("pgid_path")
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


def _raise_on_signal(signum, frame):
    # Unwinds run_lanes, whose except-branch kills every running lane's process group.
    raise SystemExit(128 + signum)


def _install_signal_handlers():
    """SIGTERM/SIGINT -> SystemExit in run_lanes; returns the previous handlers (main thread only)."""
    if threading.current_thread() is not threading.main_thread():
        return {}
    old = {}
    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            old[signum] = signal.signal(signum, _raise_on_signal)
        except (OSError, ValueError):
            pass
    return old


def _restore_signal_handlers(old):
    for signum, handler in old.items():
        try:
            signal.signal(signum, signal.SIG_DFL if handler is None else handler)
        except (OSError, TypeError, ValueError):
            pass


def _absorb(state, width):
    while state["seen"] < state["throttles"]:
        state["seen"] += 1
        width = max(1, width // 2)
    return width


def _write_result(out_dir, lane_id, status, exit_code, error, last_event="", throttles=0, width=0):
    """Build one lane's result dict, write its <id>.done and return it. The <id>.jsonl is
    created empty if the lane never got far enough to produce one (e.g. a spawn failure),
    so `out` always names a real file."""
    out_path = os.path.join(out_dir, lane_id + ".jsonl")
    if not os.path.exists(out_path):
        open(out_path, "w").close()
    result = {"id": lane_id, "status": status, "exit": exit_code, "error": error,
              "last_event": last_event, "throttles": throttles, "width": width, "out": out_path}
    with open(os.path.join(out_dir, lane_id + ".done"), "w") as f:
        json.dump(result, f, indent=2)
    return result


def _finish(state, status, out_dir):
    _drop_pgid(state)
    state["err_file"].close()
    code = state["proc"].returncode
    error = state["error"]
    if status is None:
        # v2 `{"type":"aborted"}` fails the lane even when opencode exits 0.
        status = "OK" if code == 0 and not state.get("aborted") else "FAIL"
    if status == "FAIL" and not error:
        error = _last_line(state["err_path"])
    return _write_result(out_dir, state["id"], status, code, error,
                          state["last_event"], state["throttles"], state["width"])


STANDALONE_RACE = "Standalone server exited before reporting readiness"
# v1 1.18 processes that start together on a fresh data dir all run the SQLite migrations; the
# losers exit 1 with one of these on stderr (seen on opencode 1.18.33).
V1_DB_RACES = ("database is locked", "Failed query:")
# Retries per lane: a v1 retry can collide again with a sibling that is still migrating.
RACE_RETRIES = {1: 3, 2: 1}
# A re-queued lane waits this many seconds times its attempt number, so it does not collide again.
RACE_RETRY_DELAY = 0.5


def _standalone_race(state, major):
    """Lanes started together on a fresh data dir race during init: v2 `run --standalone` losers
    exit 1 with STANDALONE_RACE, v1 losers with a V1_DB_RACES message. Either way they emitted no
    event and did no work, so they are safe to retry."""
    if state["proc"].returncode == 0 or state["last_event"]:
        return False
    markers = (STANDALONE_RACE,) if major >= 2 else V1_DB_RACES
    try:
        with open(state["err_path"], errors="replace") as fh:
            text = fh.read()
    except OSError:
        return False
    return any(m in text for m in markers)


def env_lanes() -> int:
    """OC_MAX_LANES clamped to [1, MAX_PARALLEL]; unset, empty or non-numeric gives DEFAULT_LANES."""
    try:
        return max(1, min(MAX_PARALLEL, int(os.environ.get("OC_MAX_LANES", "").strip())))
    except ValueError:
        return DEFAULT_LANES


def run_lanes(lanes: list, out_dir: str, width: int = DEFAULT_LANES, stall: int = 180, binary: str = "opencode", major: int = 0) -> list:
    """Run one `opencode run` process per lane; write <id>.jsonl, <id>.err and <id>.done."""
    if not major:
        major = detect(binary)
    if not major:
        raise SystemExit("opencode not found: " + binary)
    missing = check_run_flags(major, binary)
    if missing:
        raise SystemExit("opencode run --help lacks flag(s): " + ", ".join(missing))
    os.makedirs(out_dir, exist_ok=True)
    width = max(1, min(int(width), MAX_PARALLEL))
    pending = list(lanes)
    running = []
    results = {}
    retried = {}
    not_before = {}
    old_handlers = _install_signal_handlers()
    try:
        while pending or running:
            now = time.monotonic()
            for item in [p for p in pending if not_before.get(str(p["id"]), 0) <= now]:
                if len(running) >= width:
                    break
                pending.remove(item)
                state = _start_lane(item, out_dir, major, binary, width, stall)
                if "start_error" in state:
                    lane_id = state["id"]
                    results[lane_id] = _write_result(out_dir, lane_id, "FAIL", None,
                                                      state["start_error"], width=width)
                else:
                    running.append(state)
            time.sleep(0.05)
            for state in list(running):
                width = _absorb(state, width)
                status = None
                if state["proc"].poll() is None:
                    now = time.monotonic()
                    if now - state["last"] > state["stall"]:
                        status = "STALL"
                        state["error"] = "no event for %ss, last event: %s" % (state["stall"], state["last_event"] or "none")
                    elif state["timeout"] and now - state["start"] > state["timeout"]:
                        status = "TIMEOUT"
                        state["error"] = "timeout after %ss, last event: %s" % (state["timeout"], state["last_event"] or "none")
                    else:
                        continue
                    _kill_group(state["proc"])
                state["proc"].wait()
                # The lane's own process may have exited on its own while a
                # descendant it spawned (inheriting our stdout pipe) lives on;
                # kill the whole group so the reader thread's read() gets EOF
                # instead of blocking forever on that descendant.
                _kill_group(state["proc"])
                state["reader"].join(5)
                width = _absorb(state, width)
                running.remove(state)
                if (status is None and retried.get(state["id"], 0) < RACE_RETRIES.get(major, 1)
                        and _standalone_race(state, major)):
                    retried[state["id"]] = retried.get(state["id"], 0) + 1
                    not_before[state["id"]] = time.monotonic() + RACE_RETRY_DELAY * retried[state["id"]]
                    _drop_pgid(state)
                    state["err_file"].close()
                    pending.insert(0, state["lane"])
                    continue
                results[state["id"]] = _finish(state, status, out_dir)
    except BaseException:
        # Exceptions, SIGTERM and SIGINT all land here: no lane outlives the caller.
        for state in running:
            _kill_group(state["proc"])
            _drop_pgid(state)
        raise
    finally:
        _restore_signal_handlers(old_handlers)
    return [results[str(item["id"])] for item in lanes]


def _event_text(event):
    part = event.get("part")
    if isinstance(part, dict) and isinstance(part.get("text"), str):
        return part["text"]
    text = event.get("text")
    return text if isinstance(text, str) else ""


def _final_text(path):
    """Text of the last step that produced text. v2's final text step has no step_finish, so a
    step is delimited by step_start only."""
    last, current = [], []
    try:
        with open(path) as fh:
            lines = fh.read().splitlines()
    except OSError:
        return ""
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "step_start":
            current = []
        elif event.get("type") == "text":
            text = _event_text(event)
            if text:
                current.append(text)
                last = current
    return "\n".join(last).strip()


def lane_results(out_dir: str) -> list:
    """One dict per lane in out_dir, sorted by id: id, status (RUNNING without a .done), error
    and the lane's final assistant text, so callers never read the raw .jsonl."""
    try:
        names = os.listdir(out_dir)
    except OSError:
        return []
    ids = sorted({n[:-5] for n in names if n.endswith(".done")}
                 | {n[:-6] for n in names if n.endswith(".jsonl")})
    rows = []
    for lane_id in ids:
        try:
            with open(os.path.join(out_dir, lane_id + ".done")) as fh:
                done = json.load(fh)
        except (OSError, ValueError):
            done = {}
        if not isinstance(done, dict):
            done = {}
        rows.append({"id": lane_id, "status": done.get("status") or "RUNNING",
                     "error": done.get("error") or "",
                     "text": _final_text(os.path.join(out_dir, lane_id + ".jsonl"))})
    return rows


PROBE_AGENT = (
    "---\n"
    "description: effort probe\n"
    "model: flash\n"
    "effort: %s\n"
    "access: read\n"
    "bash: false\n"
    "web: false\n"
    "steps: 1\n"
    "---\n"
    "Answer with the number only.\n"
)
PROBE_BRIEF = "How many prime numbers are below 100? Answer with the number only."


def skill_name(skill_dir: str) -> str:
    """Install name = SKILL.md frontmatter name without a trailing -glm."""
    with open(os.path.join(skill_dir, "SKILL.md")) as fh:
        fields, _ = parse_frontmatter(fh.read())
    name = str(fields.get("name") or os.path.basename(os.path.normpath(skill_dir)))
    return name[:-4] if name.endswith("-glm") else name


def install(skill_dir: str, major: int, home: str = "") -> list:
    if major not in (1, 2):
        raise ValueError("major must be 1 or 2, got %r" % (major,))
    root = os.path.join(home or os.path.expanduser("~"), ".config", "opencode")
    skill_dst = os.path.join(root, "skills", skill_name(skill_dir))
    if os.path.realpath(skill_dir) != os.path.realpath(skill_dst):
        if os.path.isdir(skill_dst):
            shutil.rmtree(skill_dst)
        shutil.copytree(skill_dir, skill_dst,
                        ignore=shutil.ignore_patterns("__pycache__", ".idea", ".DS_Store"))
    written = [skill_dst]
    for kind in ("agents", "commands"):
        src = os.path.join(skill_dir, "opencode", kind)
        if not os.path.isdir(src):
            continue
        dst = os.path.join(root, kind)
        os.makedirs(dst, exist_ok=True)
        for fname in sorted(os.listdir(src)):
            if not fname.endswith(".md"):
                continue
            with open(os.path.join(src, fname)) as fh:
                text = fh.read()
            if kind == "agents":
                text = render_agent(text, major)
            else:
                text = render_command(text, major, skill_dst)
            path = os.path.join(dst, fname)
            with open(path, "w") as fh:
                fh.write(text)
            written.append(path)
    plugins_src = os.path.join(skill_dir, "opencode", "plugins")
    suffix = ".v%d.js" % major
    if os.path.isdir(plugins_src):
        plugins_dst = os.path.join(root, "plugins")
        os.makedirs(plugins_dst, exist_ok=True)
        for fname in sorted(os.listdir(plugins_src)):
            if not fname.endswith(suffix):
                continue
            with open(os.path.join(plugins_src, fname)) as fh:
                # skill_dst sits inside a JS string literal in the template, so it must be
                # JS/JSON-escaped, not pasted in raw (a quote or backslash would break the JS).
                text = fh.read().replace("{{SKILL_DIR}}", json.dumps(skill_dst)[1:-1])
            path = os.path.join(plugins_dst, fname[:-len(suffix)] + ".js")
            with open(path, "w") as fh:
                fh.write(text)
            written.append(path)
    marker = os.path.join(skill_dst, ".oc-major")
    with open(marker, "w") as fh:
        fh.write(str(major))
    written.append(marker)
    return written


def check(skill_dir: str, home: str = "") -> list:
    name = skill_name(skill_dir)
    root = os.path.join(home or os.path.expanduser("~"), ".config", "opencode")
    marker = os.path.join(root, "skills", name, ".oc-major")
    if not os.path.isfile(marker):
        return ["MISSING: %s is not installed for OpenCode" % name]
    with open(marker) as fh:
        major = int(fh.read().strip())
    lines = ["INSTALLED: %s (major %d)" % (name, major)]
    detected = detect()
    if not detected:
        lines.append("FAIL: opencode binary not found")
        return lines
    if detected != major:
        lines.append("FAIL: installed major %d != detected major %d, re-run install-opencode.sh" % (major, detected))
    for flag in check_run_flags(detected):
        lines.append("FAIL: opencode run lacks %s" % flag)
    return lines


def _reasoning(obj) -> int:
    if isinstance(obj, dict):
        tokens = obj.get("tokens")
        if isinstance(tokens, dict) and isinstance(tokens.get("reasoning"), int):
            return tokens["reasoning"]
        return sum(_reasoning(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_reasoning(v) for v in obj)
    return 0


def reasoning_tokens(path: str) -> int:
    """Sum `tokens.reasoning` over every JSON event in one lane's .jsonl output."""
    total = 0
    try:
        with open(path) as fh:
            lines = fh.read().splitlines()
    except OSError:
        return 0
    for line in lines:
        try:
            total += _reasoning(json.loads(line))
        except ValueError:
            continue
    return total


def probe_effort(binary: str = "opencode", home: str = "") -> str:
    """Run the same prompt at low and max effort; honored when max reasons >1.5x longer."""
    major = detect(binary)
    if not major:
        return "unknown"
    agents_dir = os.path.join(home or os.path.expanduser("~"), ".config", "opencode", "agents")
    os.makedirs(agents_dir, exist_ok=True)
    out_dir = tempfile.mkdtemp(prefix="oc-probe-")
    lanes, written = [], []
    for level in ("low", "max"):
        path = os.path.join(agents_dir, "glm-probe-%s.md" % level)
        with open(path, "w") as fh:
            fh.write(render_agent(PROBE_AGENT % level, major))
        written.append(path)
        lanes.append({"id": "probe-" + level, "agent": "glm-probe-" + level, "model": "flash",
                      "effort": level, "dir": out_dir, "brief": PROBE_BRIEF, "timeout": 300})
    try:
        rows = run_lanes(lanes, out_dir, width=2, binary=binary, major=major)
        tokens = {r["id"]: reasoning_tokens(r["out"]) for r in rows if r.get("status") == "OK"}
    finally:
        for path in written:
            if os.path.isfile(path):
                os.remove(path)
        shutil.rmtree(out_dir, ignore_errors=True)
    low, high = tokens.get("probe-low", 0), tokens.get("probe-max", 0)
    if not low or not high:
        return "unknown"
    return "honored" if high > 1.5 * low else "ignored"


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(prog="oc_harness.py", description="OpenCode harness helpers")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("detect", help="print the OpenCode major version (0 = not found)")
    p = sub.add_parser("install", help="install one skill with its agents and commands")
    p.add_argument("skill_dir")
    p.add_argument("major", nargs="?", type=int, default=0)
    p.add_argument("home", nargs="?", default="")
    p = sub.add_parser("check", help="verify installed skills against the local opencode")
    p.add_argument("skill_dirs", nargs="+")
    p.add_argument("--home", default="", help="home dir holding .config/opencode (default ~)")
    p = sub.add_parser("snippet", help="print the opencode.json snippet")
    p.add_argument("major", nargs="?", type=int, default=0)
    p = sub.add_parser("run", help="run a lanes JSON file as parallel opencode processes")
    p.add_argument("lanes_json")
    p.add_argument("--out", default=".oc-lanes")
    p.add_argument("--width", type=int, default=env_lanes())
    p.add_argument("--stall", type=int, default=180,
                   help="stall seconds for lanes with no `stall` value and no role in STALL_BY_ROLE")
    p = sub.add_parser("result", help="print each lane's final assistant text")
    p.add_argument("out_dir")
    sub.add_parser("probe-effort", help="check whether OpenCode passes reasoning effort to GLM")
    p = sub.add_parser("harness", help="print '<harness> <major>' for the running script")
    p.add_argument("--script", default="", help="script whose location is checked (default: this file)")
    try:
        a = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)

    if a.cmd == "detect":
        major = detect()
        print(major)
        return 0 if major else 1
    if a.cmd == "install":
        major = a.major or detect()
        if not major:
            print("opencode not found; pass the major version (1 or 2)")
            return 1
        for path in install(a.skill_dir, major, a.home):
            print(path)
        print("NEXT: python3 %s snippet %d  (merge into opencode.json once)" % (os.path.abspath(__file__), major))
        return 0
    if a.cmd == "check":
        failed = False
        for skill_dir in a.skill_dirs:
            for line in check(skill_dir, a.home):
                print(line)
                failed = failed or line.startswith(("FAIL", "MISSING"))
        return 1 if failed else 0
    if a.cmd == "snippet":
        print(config_snippet(a.major or detect() or 1, []))
        return 0
    if a.cmd == "harness":
        print(_harness_line(a.script))
        return 0
    if a.cmd == "run":
        with open(a.lanes_json) as fh:
            lanes = json.load(fh)
        rows = run_lanes(lanes, a.out, width=max(1, min(MAX_PARALLEL, a.width)), stall=a.stall)
        for r in rows:
            print("LANE %s %s exit=%s %s" % (r["id"], r["status"], r.get("exit"), r.get("error") or ""))
        bad = [r["id"] for r in rows if r["status"] != "OK"]
        if bad:
            print("NEXT: rerun only lanes %s after fixing the errors above" % ", ".join(bad))
            return 1
        print("NEXT: python3 %s result %s  (each lane's final answer)" % (os.path.abspath(__file__), a.out))
        return 0
    if a.cmd == "result":
        rows = lane_results(a.out_dir)
        if not rows:
            print("no lanes in %s" % a.out_dir)
            print("NEXT: pass the --out directory of a `run`")
            return 1
        for r in rows:
            print(("LANE %s: %s %s" % (r["id"], r["status"], r["error"])).rstrip())
            print(r["text"] or "(no assistant text)")
            print("")
        bad = [r["id"] for r in rows if r["status"] != "OK"]
        if bad:
            print("NEXT: rerun only lanes %s after fixing the errors above" % ", ".join(bad))
        else:
            print("NEXT: act on the lane answers above; open %s/<id>.jsonl only to debug a lane" % a.out_dir)
        return 0
    print("EFFORT %s" % probe_effort())
    return 0


if __name__ == "__main__":
    sys.exit(main())
