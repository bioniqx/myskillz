"""Run one opencode process for a hybrid-brainstorming lane and parse its JSON event stream.

Vendored runner, stdlib only, Python 3.8+. opencode v2.0.20 has no --variant or
--dir flag: the variant rides on --model as provider/model#variant and the repo
root is the cwd. Every tool call's input and output is kept for the grounding
gate; large outputs that opencode saved to a file are read back from that file.
"""
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

import hybrid_shared

THROTTLE_RE = hybrid_shared.THROTTLE_RE
SAVED_RE = re.compile(r"full output saved to (/[^\]\s]+)\]")

POLL_S = 0.1
KILL_GRACE_S = 2.0
SAVED_MAX_BYTES = 2000000


def build_cmd(binary: str, agent: str, model: str, variant: str, message: str) -> list:
    """Return the argv for one `opencode run` (no --dir, no --variant, no session reuse)."""
    spec = model + "#" + variant if variant else model
    # A fixed --title stops opencode's hidden title agent: without it every run first calls the provider's
    # default small model (opencode/gpt-6-luna, paid, 402 on the free plan), not $HYBRID_OPENCODE_*.
    return [
        binary, "run", "--standalone", "--agent", agent,
        "--model", spec, "--format", "json", "--auto", "--title", agent, message,
    ]


def _empty_usage():
    return {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0, "cost": 0.0}


def _num(value):
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return value
    return 0


def _dict(value):
    return value if isinstance(value, dict) else {}


def _tool_output_root():
    """Opencode's tool-output dir, resolved at call time so tests can set the env.

    Honors $XDG_DATA_HOME, falling back to ~/.local/share.
    """
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return Path(base) / "opencode" / "tool-output"


def _resolve_saved(output):
    """Replace a trailing `full output saved to <path>]` marker with the saved file's text.

    Only a marker that ends the output and names a file under opencode's
    tool-output directory is resolved; anything else stays plain text.
    """
    match = SAVED_RE.search(output)
    if not match or match.end() != len(output.rstrip()):
        return output
    root = _tool_output_root().resolve()
    saved = Path(match.group(1)).resolve()
    if root not in saved.parents:
        return output
    try:
        with open(str(saved), "rb") as fh:
            data = fh.read(SAVED_MAX_BYTES)
    except OSError:
        return output
    return data.decode("utf-8", errors="replace")


def _tool_record(part):
    state = _dict(part.get("state"))
    output = state.get("output")
    output = output if isinstance(output, str) else ""
    return {
        "tool": str(part.get("tool") or ""),
        "status": str(state.get("status") or ""),
        "input": _dict(state.get("input")),
        "output": _resolve_saved(output),
    }


def parse_events(path: Path) -> dict:
    """Parse an opencode --format json stream file.

    Returns {session, text, usage{input,output,reasoning,cache_read,cache_write,cost},
    errors[list of hybrid_shared.error_note lines], throttled, events,
    tools[{tool,status,input,output}], finished}. finished means the run completed: a step_finish with reason "stop" (v1), or, on
    v2.0.20, which never emits a terminal step_finish, a stream that ENDS in a fully streamed
    text part (part.time.end set; a later step_start, tool_use or error event undoes it).
    usage sums the step_finish events, so on v2.0.20 it is a lower bound: the final step reports
    nothing (`opencode session export <session>` has the totals).
    A missing file yields the empty result; non-JSON lines are skipped but still
    scanned for throttling.
    """
    result = {
        "session": "",
        "text": "",
        "usage": _empty_usage(),
        "errors": [],
        "throttled": False,
        "events": 0,
        "tools": [],
        "finished": False,
    }
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return result
    answered = False
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except ValueError:
            if THROTTLE_RE.search(line):
                result["throttled"] = True
            continue
        if not isinstance(event, dict):
            continue
        result["events"] += 1
        sid = event.get("sessionID")
        if isinstance(sid, str) and sid and not result["session"]:
            result["session"] = sid
        etype = event.get("type")
        part = _dict(event.get("part"))
        if etype == "text":
            text = part.get("text")
            if isinstance(text, str):
                result["text"] = text
            # v2.0.20 ends a good run with a fully streamed text part and no step_finish
            answered = isinstance(text, str) and bool(_dict(part.get("time")).get("end"))
        elif etype == "step_start":
            answered = False
        elif etype == "tool_use":
            result["tools"].append(_tool_record(part))
            answered = False
        elif etype == "step_finish":
            tokens = _dict(part.get("tokens"))
            cache = _dict(tokens.get("cache"))
            usage = result["usage"]
            usage["input"] += _num(tokens.get("input"))
            usage["output"] += _num(tokens.get("output"))
            usage["reasoning"] += _num(tokens.get("reasoning"))
            usage["cache_read"] += _num(cache.get("read"))
            usage["cache_write"] += _num(cache.get("write"))
            usage["cost"] += float(_num(part.get("cost")))
            if part.get("reason") == "stop":
                result["finished"] = True
        elif etype == "error":
            err = _dict(event.get("error"))
            note = hybrid_shared.error_note(err)
            answered = False
            result["errors"].append(note)
            if THROTTLE_RE.search(note) or THROTTLE_RE.search(json.dumps(err)):
                result["throttled"] = True
    result["finished"] = result["finished"] or answered
    return result


def _size(path):
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _tail(path, limit=500):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text.strip()[-limit:]


def _kill_group(proc):
    """SIGTERM the whole process group, then SIGKILL after a short grace period."""
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except OSError:
        pass
    deadline = time.monotonic() + KILL_GRACE_S
    while time.monotonic() < deadline and proc.poll() is None:
        time.sleep(POLL_S)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass
    try:
        proc.wait(timeout=KILL_GRACE_S)
    except subprocess.TimeoutExpired:
        pass


def run_once(cmd: list, cwd: Path, env: dict, out_path: Path, err_path: Path, stall_s: int, timeout_s: int) -> dict:
    """Run one opencode process under a stall/timeout watchdog.

    `env` is the complete environment (callers pass dict(os.environ, **extra));
    PWD is forced to cwd. stdout goes to out_path (the JSON event stream), stderr
    to err_path. Returns the parse_events() keys plus rc (None on spawn error),
    reason ("" on success, else spawn, stall, timeout or a hybrid_shared.classify
    kind such as auth, quota, model, throttle, context, crash or recovered),
    note, detail (the first error message, one line), pid (0 on spawn error) and
    duration in seconds. throttle is reported only when the run failed. A run is a success when rc is 0 with no error events (v2.0.20 has no completion marker to
    require); "recovered" means an error event or exit 1 happened but the run finished after it.
    """
    cwd = Path(cwd)
    out_path = Path(out_path)
    err_path = Path(err_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    err_path.parent.mkdir(parents=True, exist_ok=True)
    full_env = dict(env)
    full_env["PWD"] = str(cwd)
    result = {"rc": None, "reason": "", "note": "", "detail": "", "pid": 0, "duration": 0.0}
    start = time.monotonic()
    killed = ""
    spawn_error = ""
    proc = None
    with open(str(out_path), "wb") as out_f, open(str(err_path), "wb") as err_f:
        try:
            proc = subprocess.Popen(
                [str(c) for c in cmd],
                cwd=str(cwd),
                env=full_env,
                stdin=subprocess.DEVNULL,
                stdout=out_f,
                stderr=err_f,
                start_new_session=True,
            )
        except (OSError, ValueError) as exc:
            proc = None
            spawn_error = "spawn failed: %s" % exc
        if proc is not None:
            result["pid"] = proc.pid
            last_size = 0
            last_activity = start
            try:
                while proc.poll() is None:
                    now = time.monotonic()
                    size = _size(out_path)
                    if size != last_size:
                        last_size = size
                        last_activity = now
                    if timeout_s and now - start > timeout_s:
                        killed = "timeout"
                        break
                    if stall_s and now - last_activity > stall_s:
                        killed = "stall"
                        break
                    time.sleep(POLL_S)
            finally:
                if proc.poll() is None:
                    _kill_group(proc)
            result["rc"] = proc.returncode
    result.update(parse_events(out_path))
    result["duration"] = round(time.monotonic() - start, 3)
    if proc is None:
        result["reason"] = "spawn"
        result["note"] = spawn_error
        result["detail"] = spawn_error
        return result
    err_tail = _tail(err_path)
    throttled = bool(result["throttled"]) or bool(THROTTLE_RE.search(err_tail))
    result["throttled"] = throttled
    errors = "; ".join(result["errors"])
    failed = bool(killed) or result["rc"] != 0 or bool(result["errors"])
    if not failed:
        return result
    if killed == "stall":
        result["reason"] = "stall"
        result["note"] = "stall: no event for %ss" % stall_s
        result["detail"] = result["note"]
    elif killed == "timeout":
        result["reason"] = "timeout"
        result["note"] = "timeout: wall time over %ss" % timeout_s
        result["detail"] = result["note"]
    else:
        kind = hybrid_shared.classify(result["rc"], result["errors"], err_tail, killed, result["finished"])
        if kind == "crash" and throttled:
            kind = "throttle"
        result["reason"] = kind or "crash"
        if result["reason"] == "throttle":
            result["note"] = errors or err_tail or "throttle"
        else:
            result["note"] = errors or "exit %s: %s" % (result["rc"], err_tail)
        result["detail"] = hybrid_shared.first_error(result["errors"], err_tail)
    return result
