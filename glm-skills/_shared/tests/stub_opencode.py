#!/usr/bin/env python3
"""Stub `opencode` binary for tests: --version, run --help, run [flags] [message].

STUB_OC_VERSION selects the mode: a value starting "2." behaves like OpenCode
v2.0.x (rejects --dir, requires --standalone, events carry timestamp and
sessionID, the final text step has no step_finish, v2 rate-limit error shape).
Anything else (default 1.18.33) behaves like v1.18.x (accepts --dir, rejects
--standalone and a `#` model suffix, APIError 429 error shape).
The brief is the positional message, or stdin (read to EOF) when there is none.
STUB_OC_LOG gets one JSON line per run: {"argv": [...], "stdin": "..."}.
Brief keywords: stall_child, exit_child, throttle, aborted, stall, fail, slow.
"""
import json
import os
import subprocess
import sys
import time

DEFAULT_VERSION = "1.18.33"
FLAGS = ["--dir", "--agent", "--model", "--format", "--auto", "--standalone"]

V1_VALUE_FLAGS = {"--dir", "--model", "-m", "--agent", "--format", "--variant", "--session",
                  "--file", "--title"}
V1_BOOL_FLAGS = {"--auto", "--continue", "--share"}
V2_VALUE_FLAGS = {"--model", "-m", "--agent", "--format", "--session", "--file", "--title",
                  "--server"}
V2_BOOL_FLAGS = {"--standalone", "--continue", "--fork", "--thinking", "--auto"}

V1_THROTTLE = {"type": "error", "error": {"name": "APIError", "data": {
    "statusCode": 429,
    "responseBody": json.dumps({"error": {"code": "1302"}}, separators=(",", ":")),
}}}
V2_THROTTLE = {"type": "error", "error": {"type": "provider.rate-limit", "status": 429}}
ABORTED = {"type": "aborted"}
SESSION_ID = "ses_stub0001"
TOKENS = {"input": 10, "output": 5}


class UsageError(Exception):
    pass


def version():
    return os.environ.get("STUB_OC_VERSION", DEFAULT_VERSION)


def is_v2():
    return version().startswith("2.")


def emit(event, v2=False):
    if v2:
        event = dict(event, timestamp=int(time.time() * 1000), sessionID=SESSION_ID)
    print(json.dumps(event), flush=True)


def emit_raw(event):
    print(json.dumps(event), flush=True)


def log(argv, stdin):
    path = os.environ.get("STUB_OC_LOG")
    if path:
        with open(path, "a") as f:
            f.write(json.dumps({"argv": argv, "stdin": stdin}) + "\n")


def parse(args, v2):
    value_flags = V2_VALUE_FLAGS if v2 else V1_VALUE_FLAGS
    bool_flags = V2_BOOL_FLAGS if v2 else V1_BOOL_FLAGS
    opts = {}
    message = []
    i = 0
    while i < len(args):
        tok = args[i]
        if tok.startswith("-") and len(tok) > 1:
            name, eq, inline = tok.partition("=")
            if name in value_flags:
                if eq:
                    value = inline
                elif i + 1 < len(args):
                    i += 1
                    value = args[i]
                else:
                    raise UsageError("missing value for %s" % name)
                opts["--model" if name == "-m" else name] = value
            elif name in bool_flags and not eq:
                opts[name] = True
            else:
                raise UsageError("unknown option %s" % name)
        else:
            message.append(tok)
        i += 1
    return opts, message


def check(opts, v2):
    if v2:
        if "--standalone" not in opts:
            return "v2 stub needs --standalone (no managed background service in tests)"
    elif "#" in opts.get("--model", ""):
        return "UnknownError: model variant suffix '#' is not supported"
    return ""


def spawn_child():
    # The child inherits our stdout pipe and outlives us.
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    pid_file = os.environ.get("STUB_CHILD_PID_FILE")
    if pid_file:
        with open(pid_file, "w") as f:
            f.write(str(child.pid))


def behave(brief, v2):
    emit({"type": "step_start", "part": {"type": "step-start"}}, v2)
    if "stall_child" in brief:
        # A kill of only this process leaves the pipe open (needs a process-group kill).
        spawn_child()
        time.sleep(60)
        return 0
    if "exit_child" in brief:
        # This process exits right away; the child still holds our stdout pipe.
        spawn_child()
        return 0
    if "throttle" in brief:
        emit_raw(V2_THROTTLE if v2 else V1_THROTTLE)
        return 1
    if "aborted" in brief:
        emit_raw(ABORTED)
        return 1
    if "stall" in brief:
        time.sleep(60)
        return 0
    if "fail" in brief:
        print("stub failure", file=sys.stderr)
        return 3
    if "slow" in brief:
        time.sleep(1)
    text = {"type": "text", "part": {"type": "text", "text": "done: " + brief}}
    finish = {"type": "step_finish", "part": {"type": "step-finish", "tokens": TOKENS}}
    if v2:
        emit({"type": "tool_use", "part": {"type": "tool", "tool": "read",
                                           "state": {"status": "completed"}}}, v2)
        emit(finish, v2)
        emit({"type": "step_start", "part": {"type": "step-start"}}, v2)
        emit(text, v2)  # v2: the final text step has no step_finish
    else:
        emit(text)
        emit(finish)
    return 0


def main(argv):
    v2 = is_v2()
    if argv[:1] == ["--version"]:
        print(version())
        return 0
    if argv[:1] != ["run"]:
        print("stub opencode: unknown command", file=sys.stderr)
        return 2
    if "--help" in argv:
        missing = os.environ.get("STUB_OC_MISSING", "").split(",")
        for flag in FLAGS:
            if flag not in missing:
                print("  %s  <value>" % flag)
        return 0
    try:
        opts, message = parse(argv[1:], v2)
    except UsageError as exc:
        log(argv, "")
        print("stub opencode: %s" % exc, file=sys.stderr)
        return 1
    stdin = "" if message else sys.stdin.read()
    log(argv, stdin)
    problem = check(opts, v2)
    if problem:
        print("stub opencode: %s" % problem, file=sys.stderr)
        return 1
    brief = " ".join(message) if message else stdin
    if v2 and message and any(c.isspace() for c in brief):
        brief = '"%s"' % brief  # v2 wraps a whitespace argv message in literal quotes
    return behave(brief, v2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
