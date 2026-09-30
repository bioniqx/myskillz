#!/usr/bin/env python3
"""hp_wait - fallback-aware helpers for `plan_tool.py wait` (stdlib only, Python 3.8+).

oc_alive(work)                  -> True while <work>/oc/oc-write.pid names a live process
fallback_line(fb)               -> the FALLBACK dispatch line for one fallback marker
pending_fallback_lines(work)    -> unreported OC lines, then a line for every unsent <gid>.fallback (touches <gid>.fallback.sent)
runner_died(plan, work, info, waited_s) -> writes runner-died fallbacks for unfinished opencode groups
                                           (left unsent: the next pending_fallback_lines call delivers them)
"""
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import plan_tool  # noqa: E402
import hp_write  # noqa: E402
import hybrid_shared  # noqa: E402

PID_FILE = "oc-write.pid"


def _read_pid(work: str) -> Optional[int]:
    path = os.path.join(hp_write.oc_dir(work), PID_FILE)
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    m = re.search(r'"pid"\s*:\s*(\d+)', text) or re.match(r"\s*(\d+)\s*$", text)
    if not m:
        return None
    pid = int(m.group(1))
    return pid if pid > 0 else None


def oc_alive(work: str) -> bool:
    pid = _read_pid(work)
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def fallback_line(fb: dict) -> str:
    gid = str(fb.get("gid", ""))
    if fb.get("held"):
        return ("HELD %s (%s) %s — preset opencode, do not dispatch. Ask the user once: retry on opencode / "
                "write these tasks yourself from %s (model %s) / switch the run to hybrid / abort." % (
                    gid, fb.get("reason", ""), ",".join(fb.get("tasks") or []),
                    fb.get("brief", ""), fb.get("model", "")))
    return ("FALLBACK %s (%s) %s → Agent subagent_type=%s model=%s description 'plan %sF' "
            "prompt: Read %s and follow it exactly." % (
                gid, fb.get("reason", ""), ",".join(fb.get("tasks") or []),
                fb.get("subagent_type", "general-purpose"), fb.get("model", "sonnet"),
                gid, fb.get("brief", "")))


def _unsent(work: str) -> List[str]:
    d = hp_write.oc_dir(work)
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return []
    return [os.path.join(d, n) for n in names
            if n.endswith(".fallback") and not os.path.exists(os.path.join(d, n + ".sent"))]


def pending_fallback_lines(work: str) -> list:
    """Unreported OC lines first, then one line per unsent fallback marker.

    Each OC line is delivered once (hybrid_shared.take_unreported tracks them). Each delivered
    marker gets a <gid>.fallback.sent file, so it is never delivered twice.
    """
    lines = list(hybrid_shared.take_unreported(hp_write.errors_log(work)))
    for path in _unsent(work):
        try:
            fb = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if not isinstance(fb, dict):
            continue
        lines.append(fallback_line(fb))
        plan_tool.touch(path + ".sent")
    return lines


RUNNER_GRACE_S = 15.0  # oc-write is launched in the same message as wait; give it time to write its pid


def runner_died(plan_path: str, work: str, info: dict, waited_s: float) -> list:
    if oc_alive(work) or _unsent(work):
        return []
    d = hp_write.oc_dir(work)
    if not os.path.exists(os.path.join(d, PID_FILE)) and waited_s < RUNNER_GRACE_S:
        return []
    groups = info.get("groups") or {}
    backend = info.get("backend") or {}
    tiers = (info.get("oc") or {}).get("tiers") or {}
    held = str(info.get("preset") or "") == "opencode"
    lines = []
    for gid in sorted(backend):
        if not str(backend[gid]).startswith("oc:"):
            continue
        if os.path.exists(os.path.join(d, gid + ".fallback")):
            continue
        ids = list(groups.get(gid) or [])
        states = {t: plan_tool.done_state(os.path.join(work, "tasks", t + ".md"), "ok") for t in ids}
        left = [t for t in ids if states[t] != "done"]
        if not left:
            continue
        errors = {t: ["opencode runner exited before finishing (task %s, waited %.0fs)" % (states[t], waited_s)]
                  for t in left}
        tier = str(backend[gid])[3:]
        hp_write.report(work, gid, tier, tiers.get(tier) or {}, hp_write.LEVEL_ERROR, "crash", errors[left[0]][0])
        fb = hp_write.write_fallback(plan_path, gid, left, "runner-died", errors, held=held)
        lines.append(fallback_line(fb))  # marker stays unsent; `wait` prints it via pending_fallback_lines
    return lines
