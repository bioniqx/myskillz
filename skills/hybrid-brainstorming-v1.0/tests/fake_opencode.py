#!/usr/bin/env python3
"""Fake `opencode` CLI for hybrid-brainstorming tests. Never calls a model or the network.

Env HB_FAKE_SCRIPT names a JSON file holding one step object or a list of steps
(call N uses entry N, the last entry repeats; the count lives in <script>.calls).
Env HB_FAKE_LOG names a file that receives one JSON line per call:
{argv, cwd, pwd, config}.

Step keys (all optional):
  save    {absolute path: text}; files written first (simulates saved tool output)
  grandchild  path; spawn a sleeping child in this process group, write its pid there
  ticks   number of step_start events, tick_s seconds apart (default 0.1)
  raw     lines written verbatim to stdout
  events  event objects emitted as JSON lines (sessionID added when missing)
  usage   {input, output, reasoning, cache_read, cache_write, cost}; one step_finish
  text    final text event
  stderr  text written to stderr
  sleep   seconds to sleep before exiting
  error   {type, message}; an error event, then exit 1 unless `exit` is set
  exit    exit code (default 0)
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

FAKE_SCRIPT_ENV = "HB_FAKE_SCRIPT"
FAKE_LOG_ENV = "HB_FAKE_LOG"
DEFAULT_SESSION = "ses_fake0001"
FAKE_VERSION = "2.0.18"


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
    session = str(step.get("session") or DEFAULT_SESSION)

    for target, content in (step.get("save") or {}).items():
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(content), encoding="utf-8")

    if step.get("grandchild"):
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        pid_path = Path(step["grandchild"])
        tmp_path = Path(str(pid_path) + ".tmp")
        tmp_path.write_text(str(child.pid), encoding="utf-8")
        os.replace(str(tmp_path), str(pid_path))

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
