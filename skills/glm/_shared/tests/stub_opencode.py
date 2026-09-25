#!/usr/bin/env python3
"""Stub `opencode` binary for tests: --version, run --help, run <brief>."""
import json
import os
import sys
import time

FLAGS = ["--dir", "--agent", "--model", "--format", "--auto"]


def emit(event):
    print(json.dumps(event), flush=True)


def log(argv):
    path = os.environ.get("STUB_OC_LOG")
    if path:
        with open(path, "a") as f:
            f.write(json.dumps(argv) + "\n")


def main(argv):
    if argv[:1] == ["--version"]:
        print(os.environ.get("STUB_OC_VERSION", "1.18.32"))
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
    log(argv)
    brief = argv[-1]
    emit({"type": "step_start", "part": {"type": "step-start"}})
    if "throttle" in brief:
        inner = json.dumps({"error": {"code": "1302", "message": "High concurrency"}})
        emit({"type": "error", "error": {"name": "APIError", "data": {"message": inner}}})
        return 1
    if "stall" in brief:
        time.sleep(60)
        return 0
    if "fail" in brief:
        print("stub failure", file=sys.stderr)
        return 3
    if "slow" in brief:
        time.sleep(1)
    emit({"type": "text", "part": {"type": "text", "text": "done: " + brief}})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
