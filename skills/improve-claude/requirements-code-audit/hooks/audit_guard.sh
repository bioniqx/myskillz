#!/usr/bin/env bash
# requirements-code-audit guard — thin launcher.
# Fast path (a few ms): when no audit is active in this project, exit 0 without even reading stdin,
# so the hook costs nothing in normal sessions. Only during an active audit do we hand the event to Python.
root="${CLAUDE_PROJECT_DIR:-$PWD}"
if [ ! -f "$root/.audit/ACTIVE" ]; then
  exit 0
fi
dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$dir/audit_guard.py"
elif command -v python >/dev/null 2>&1; then
  exec python "$dir/audit_guard.py"
fi
# No Python: fail open (non-blocking) but say so once per call on stderr.
echo "audit_guard: python not found; guard not enforced" >&2
exit 0
