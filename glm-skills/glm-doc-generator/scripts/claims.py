#!/usr/bin/env python3
"""Thin wrapper for glm-doc-generator: hand off to the vendored decide.py.

handoff.py open prints this path so the model does not invent the command.
No logic lives here: this script runs `decide.py claim` from the same
directory, forwards argv and stdin untouched, and exits with the child's
exit code. Do not edit the vendored decide.py; _shared/sync.sh rewrites it.
"""
import os
import subprocess
import sys

DECIDE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "decide.py")

if __name__ == "__main__":
    sys.exit(subprocess.run([sys.executable, DECIDE, "claim"] + sys.argv[1:]).returncode)
