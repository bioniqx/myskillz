#!/usr/bin/env python3
"""Fake `opencode` CLI for hybrid-writing-plans tests. Never calls a model or the network.

Env HYBRID_WRITING_PLANS_FAKE_SCRIPT names a JSON file holding one step object or a list of steps
(call N uses entry N, so each round replays its own event stream; the last entry
repeats; the count lives in <script>.calls).
Env HYBRID_WRITING_PLANS_FAKE_LOG names a file that receives one JSON line per call:
{argv, cwd, pwd, config, session, attach, attach_text}, where session is the
--session value, attach the -f path and attach_text that file's content ("" when
absent or unreadable).
Env HYBRID_WRITING_PLANS_FAKE_MODELS=empty makes `models` list nothing.

Step keys (all optional):
  session     session id to emit (default: the --session value, else ses_fake0001)
  save        {absolute path: text}; files written first (simulates saved tool output)
  grandchild  path; spawn a sleeping child in this process group, write its pid there
  ticks       number of step_start events, tick_s seconds apart (default 0.1)
  raw         lines written verbatim to stdout
  events      event objects emitted as JSON lines (sessionID added when missing)
  usage       {input, output, reasoning, cache_read, cache_write, cost}; one step_finish
  text        final text event
  stderr      text written to stderr
  sleep       seconds to sleep before exiting
  scenario    canned step merged under the other keys: auth, model_not_found, throttle,
              recovered (exit 1 after a terminal stop), empty (exit 0, no output)
  finish_reason  reason written on the step_finish event (default: none)
  error       {type, message}; an error event, then exit 1 unless `exit` is set
  exit        exit code (default 0)
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

FAKE_SCRIPT_ENV = "HYBRID_WRITING_PLANS_FAKE_SCRIPT"
FAKE_LOG_ENV = "HYBRID_WRITING_PLANS_FAKE_LOG"
FAKE_MODELS_ENV = "HYBRID_WRITING_PLANS_FAKE_MODELS"
DEFAULT_SESSION = "ses_fake0001"
FAKE_VERSION = "2.0.18"


def _flag(argv, names):
    """Value following the first flag in `names`, ignoring the trailing message."""
    for i, arg in enumerate(argv[:-1]):
        if arg in names:
            return str(argv[i + 1])
    return ""


def _read_attach(path):
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
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


SCENARIOS = {
    "auth": {"error": {"type": "ProviderAuthError", "message": "401 Unauthorized: invalid api key"}},
    "model_not_found": {"error": {"type": "ProviderModelNotFoundError",
                                  "message": "model zai-coding-plan/nope not found"}},
    "throttle": {"error": {"type": "APIError", "message": "429 Too Many Requests"}},
    "recovered": {
        "events": [{"type": "error", "error": {"type": "APIError", "message": "upstream hiccup, retried"}}],
        "usage": {"input": 5, "output": 2},
        "finish_reason": "stop",
        "text": "recovered reply",
        "exit": 1,
    },
    "empty": {},
}


def _expand(step):
    """Merge the canned scenario named by step["scenario"] under the step's own keys."""
    merged = dict(SCENARIOS.get(str(step.get("scenario") or ""), {}))
    merged.update({k: v for k, v in step.items() if k != "scenario"})
    return merged


def _log(argv):
    log_path = os.environ.get(FAKE_LOG_ENV, "")
    if not log_path:
        return
    is_run = bool(argv) and argv[0] == "run"
    attach = _flag(argv, ("-f", "--file")) if is_run else ""
    record = {
        "argv": list(argv),
        "cwd": os.getcwd(),
        "pwd": os.environ.get("PWD", ""),
        "config": os.environ.get("OPENCODE_CONFIG_CONTENT", ""),
        "session": _flag(argv, ("--session", "-s")) if is_run else "",
        "attach": attach,
        "attach_text": _read_attach(attach),
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
        if os.environ.get(FAKE_MODELS_ENV, "") == "empty":
            return 0
        print("zai-coding-plan/glm-5.3", flush=True)
        print("zai-coding-plan/glm-5.3-flash", flush=True)
        return 0
    if not argv or argv[0] != "run":
        sys.stderr.write("fake opencode: unsupported command\n")
        return 2
    step = _expand(_load_step(os.environ.get(FAKE_SCRIPT_ENV, "")))
    session = str(step.get("session") or _flag(argv, ("--session", "-s")) or DEFAULT_SESSION)

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
        part = {
            "type": "step-finish",
            "tokens": {
                "input": usage.get("input", 0),
                "output": usage.get("output", 0),
                "reasoning": usage.get("reasoning", 0),
                "cache": {"read": usage.get("cache_read", 0), "write": usage.get("cache_write", 0)},
            },
            "cost": usage.get("cost", 0),
        }
        if step.get("finish_reason"):
            part["reason"] = step["finish_reason"]
        _emit({"type": "step_finish", "part": part}, session)
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
