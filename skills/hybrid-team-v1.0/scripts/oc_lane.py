"""Run one opencode process for a hybrid-team lane and parse its JSON event stream.

Stdlib only, Python 3.8+. opencode v2.0.18 has no --variant or --dir flag: the
variant rides on --model as provider/model#variant and the worktree is the cwd.
"""
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

import hybrid_shared

THROTTLE_RE = re.compile(r"\b429\b|Too Many Requests|rate.?limit", re.I)

AGENT_NAME = "ht-programmer"
POLL_S = 0.1
KILL_GRACE_S = 2.0


def build_cmd(binary: str, model: str, variant: str, message: str, session: str = "") -> list:
    """Return the argv for one `opencode run`; `session` continues an existing session."""
    spec = model + "#" + variant if variant else model
    cmd = [
        binary, "run", "--standalone", "--agent", AGENT_NAME,
        "--model", spec, "--format", "json", "--auto",
    ]
    if session:
        cmd += ["-s", session]
    cmd.append(message)
    return cmd


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


def parse_events(path: Path) -> dict:
    """Parse an opencode --format json stream file.

    Returns {session, text, usage{input,output,reasoning,cache_read,cache_write,cost},
    errors[list of "type: message"], throttled, finished, events}. finished is True once a
    step_finish event carries part.reason == "stop". A missing file yields the
    empty result; non-JSON lines are skipped but still scanned for throttling.
    """
    result = {
        "session": "",
        "text": "",
        "usage": _empty_usage(),
        "errors": [],
        "throttled": False,
        "finished": False,
        "events": 0,
    }
    try:
        raw = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return result
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
            kind = str(err.get("type") or "error")
            message = str(err.get("message") or "")
            note = kind + ": " + message if message else kind
            result["errors"].append(note)
            if THROTTLE_RE.search(note) or THROTTLE_RE.search(json.dumps(err)):
                result["throttled"] = True
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

    stdout goes to out_path (the JSON event stream), stderr to err_path. Returns the
    parse_events() keys plus:
      rc        exit code (None on spawn error)
      reason    "" when the process is accepted, else one of spawn, stall, timeout,
                throttle, crash
      kind      "" for a clean run, else the hybrid_shared.classify() kind. An accepted
                run (reason "") can still carry a warning kind: recovered (non-zero exit
                after a terminal stop) or empty (exit 0 with no text output)
      detail    one line with the first error message or the stderr tail, "" when clean
      note      failure text, "" when reason is ""
      pid       process id (0 on spawn error)
      duration  seconds
    """
    cwd = Path(cwd)
    out_path = Path(out_path)
    err_path = Path(err_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    err_path.parent.mkdir(parents=True, exist_ok=True)
    full_env = dict(env)
    full_env["PWD"] = str(cwd)
    result = {"rc": None, "reason": "", "kind": "", "detail": "", "note": "", "pid": 0, "duration": 0.0}
    start = time.monotonic()
    killed = ""
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
            if killed:
                _kill_group(proc)
            result["rc"] = proc.returncode
    result.update(parse_events(out_path))
    result["duration"] = round(time.monotonic() - start, 3)
    if proc is None:
        result["reason"] = "spawn"
        result["kind"] = "spawn"
        result["note"] = spawn_error
        result["detail"] = spawn_error
        return result
    err_tail = _tail(err_path)
    throttled = bool(result["throttled"]) or bool(THROTTLE_RE.search(err_tail))
    result["throttled"] = throttled
    errors = "; ".join(result["errors"])
    failed = bool(killed) or result["rc"] != 0 or bool(result["errors"])
    if not failed:
        if not result["text"].strip():
            result["kind"] = "empty"
            result["detail"] = "exit 0 with no text output"
        return result
    kind = hybrid_shared.classify(result["rc"], result["errors"], err_tail, killed, result["finished"])
    if kind == "crash" and throttled and not killed:
        kind = "throttle"
    result["kind"] = kind
    result["detail"] = hybrid_shared.first_error(result["errors"], err_tail) or "exit %s" % result["rc"]
    if kind == "recovered":
        return result
    if kind == "stall":
        result["reason"] = "stall"
        result["note"] = "stall: no event for %ss" % stall_s
    elif kind == "timeout":
        result["reason"] = "timeout"
        result["note"] = "timeout: wall time over %ss" % timeout_s
    elif kind == "throttle":
        result["reason"] = "throttle"
        result["note"] = errors or err_tail or "throttle"
    else:
        result["reason"] = "crash"
        result["note"] = errors or "exit %s: %s" % (result["rc"], err_tail)
    return result
