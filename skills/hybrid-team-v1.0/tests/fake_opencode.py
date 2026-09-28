#!/usr/bin/env python3
"""Fake `opencode` CLI for hybrid-team tests. Never calls a model.

Env HT_FAKE_SCRIPT names a JSON file holding one step object or a list of steps
(call N uses entry N, the last entry repeats; the count lives in <script>.calls).
Env HT_FAKE_LOG names a file that receives one JSON line per call:
{argv, cwd, pwd, config}.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

FAKE_SCRIPT_ENV = "HT_FAKE_SCRIPT"
FAKE_LOG_ENV = "HT_FAKE_LOG"
DEFAULT_SESSION = "ses_fake0001"
FAKE_VERSION = "2.0.18"


def _session_from(argv):
    for i, arg in enumerate(argv):
        if arg in ("-s", "--session") and i + 1 < len(argv):
            return argv[i + 1]
    return ""


def _load_step(script_path):
    if not script_path:
        return {"text": "done"}
    path = Path(script_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data
    counter = Path(str(path) + ".calls")
    try:
        n = int(counter.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        n = 0
    counter.write_text(str(n + 1), encoding="utf-8")
    if not data:
        return {"text": "done"}
    return data[min(n, len(data) - 1)]


def _log(argv):
    log_path = os.environ.get(FAKE_LOG_ENV, "")
    if not log_path:
        return
    record = {
        "argv": list(argv),
        "cwd": os.getcwd(),
        "pwd": os.environ.get("PWD", ""),
        "config": os.environ.get("OPENCODE_CONFIG_CONTENT", ""),
    }
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _emit(event, session):
    ev = dict(event)
    ev.setdefault("sessionID", session)
    sys.stdout.write(json.dumps(ev) + "\n")
    sys.stdout.flush()


def _commit(message):
    quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL, "check": False}
    subprocess.run(["git", "add", "-A"], **quiet)
    subprocess.run(
        ["git", "-c", "user.name=fake-opencode", "-c", "user.email=fake@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "-q", "-m", message],
        **quiet
    )


def main(argv: list) -> int:
    _log(argv)
    if argv and argv[0] == "--version":
        print(FAKE_VERSION, flush=True)
        return 0
    if argv and argv[0] == "models":
        print("zai-coding-plan/glm-5.3", flush=True)
        print("zai-coding-plan/glm-5.3-flash", flush=True)
        return 0
    if not argv or argv[0] != "run":
        sys.stderr.write("fake opencode: unsupported command\n")
        return 2
    step = _load_step(os.environ.get(FAKE_SCRIPT_ENV, ""))
    session = _session_from(argv) or step.get("session") or DEFAULT_SESSION

    for rel, content in (step.get("write") or {}).items():
        target = Path.cwd() / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    if step.get("commit"):
        _commit(str(step["commit"]))

    tick_s = float(step.get("tick_s", 0.1))
    for i in range(int(step.get("ticks", 0))):
        _emit({"type": "step_start", "part": {"type": "step-start", "n": i}}, session)
        time.sleep(tick_s)
    for line in step.get("raw") or []:
        sys.stdout.write(str(line) + "\n")
        sys.stdout.flush()
    for event in step.get("events") or []:
        _emit(event, session)
    usage = step.get("usage")
    if usage is not None:
        _emit({"type": "step_finish", "part": {
            "type": "step-finish",
            "tokens": {
                "input": usage.get("input", 0),
                "output": usage.get("output", 0),
                "reasoning": usage.get("reasoning", 0),
                "cache": {"read": usage.get("cache_read", 0), "write": usage.get("cache_write", 0)},
            },
            "cost": usage.get("cost", 0),
        }}, session)
    if "text" in step:
        _emit({"type": "text", "part": {"type": "text", "text": step["text"]}}, session)
    if step.get("stderr"):
        sys.stderr.write(str(step["stderr"]))
        sys.stderr.flush()
    sleep_s = float(step.get("sleep", 0))
    if sleep_s:
        time.sleep(sleep_s)
    err = step.get("error")
    if err:
        _emit({"type": "error", "error": {
            "type": err.get("type", "UnknownError"),
            "message": err.get("message", ""),
        }}, session)
        return int(step.get("exit", 1))
    return int(step.get("exit", 0))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
