"""status helpers: per-backend slots, opencode dispatch lines, event harvest, hedging."""
import os
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit  # noqa: E402
import ha_doctor  # noqa: E402


def _routing(c) -> dict:
    return c.cfg.get("routing") or {}


def _cap(c) -> int:
    return int(c.state.get("cap", c.cfg.get("cap", audit.DEFAULT_CAP)))


def _entries(c) -> List[Tuple[str, dict, bool]]:
    """(name, meta, is_verifier) for every investigator and verifier batch."""
    out = [(n, meta, False) for n, meta in c.state.get("batches", {}).items()]
    out += [(n, meta, True) for n, meta in c.state.get("verify", {}).items()]
    return out


def _is_running(m, name: str, meta: dict, is_verifier: bool) -> bool:
    done = (m.vdone if is_verifier else m.batch_done).get(name)
    return bool(meta.get("dispatched")) and not done and name not in m.failed and name not in m.events


def oc_command(c, name: str) -> str:
    return 'python3 "%s/audit.py" oc-run %s' % (c.cfg["scripts_dir"], name)


def oc_block(rows: list, unit: str = "batches") -> list:
    items = sum(int(r[2]) for r in rows)
    lines = ["OPENCODE %d %s (%d items) | run each in the BACKGROUND (Bash run_in_background) "
             "in the SAME message:" % (len(rows), unit, items)]
    for row in rows:
        lines.append("  %s %s (%d items) → %s" % tuple(row))
    lines.append("After dispatching: run `audit.py status` on every completion notification "
                 "(Agent or background Bash).")
    return lines


def backend_running(c, m) -> dict:
    running = {"claude": 0}  # type: Dict[str, int]
    for tier in _routing(c).get("tiers", {}):
        running["oc:" + tier] = 0
    hedges = c.state.get("hedges", {})
    for name, meta, is_verifier in _entries(c):
        if not _is_running(m, name, meta, is_verifier):
            continue
        backend = meta.get("backend") or "claude"
        running[backend] = running.get(backend, 0) + 1
        if not is_verifier and hedges.get(name):
            running["claude"] += 1
    return running


def free_slots(c, m) -> dict:
    running = backend_running(c, m)
    free = {"claude": max(0, _cap(c) - running.get("claude", 0))}
    for tier, spec in _routing(c).get("tiers", {}).items():
        key = "oc:" + tier
        free[key] = max(0, int(spec.get("max_parallel", 0)) - running.get(key, 0))
    return free


def _role_of(name: str, ev: dict) -> str:
    agent = str(ev.get("agent_type") or "")
    if agent.startswith("opencode:ha-"):
        return agent[len("opencode:ha-"):]
    if name.startswith("section-"):
        return "parser"
    if name.startswith("batch-V"):
        return "verifier"
    return "investigator"


def harvest_oc_events(c, m, now: float) -> list:
    st = c.state
    routing = _routing(c)
    out = []  # type: List[dict]
    for name in sorted(m.events):
        ev = m.events[name]
        backend = str(ev.get("backend") or "")
        if not backend.startswith("oc:") or ev.get("ok") or name in st.get("fallbacks", {}):
            continue
        tier = backend[len("oc:"):]
        reason = str(ev.get("reason") or "crash")
        role = _role_of(name, ev)
        if reason == "unavailable":
            ha_doctor.mark_down(ha_doctor.doctor_cache_path(), tier, "unavailable",
                                str(ev.get("message") or ""))
        elif reason == "throttle":
            st.setdefault("cooldown", {})[tier] = now + float(routing.get("throttle_cooldown_s", 120))
        src = Path(c.out) / "events" / ("%s.json" % name)
        dst = Path(c.out) / "oc" / ("%s.event.json" % name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            os.replace(str(src), str(dst))
        m.events.pop(name, None)
        m.failed.discard(name)
        st.setdefault("fallbacks", {})[name] = reason
        meta = st.get("batches", {}).get(name)
        if meta is None:
            meta = st.get("verify", {}).get(name)
        if meta is not None:
            meta["backend"] = "claude"
        backends = st.get("parse", {}).get("backends")
        if isinstance(backends, dict) and name in backends:
            backends[name] = "claude"
        if role == "parser" or meta is None:
            ids = []  # type: List[str]
        elif role == "verifier":
            ids = list(meta.get("ids", []))
        else:
            ids = [i for i in meta.get("ids", []) if i not in m.finding]
        out.append({"name": name, "role": role, "reason": reason, "ids": ids})
    return out


def should_hedge_oc(c, m, name: str, now: float) -> bool:
    batches = c.state.get("batches", {})
    meta = batches.get(name)
    if meta is None or c.state.get("hedges", {}).get(name) or not _is_running(m, name, meta, False):
        return False
    backend = str(meta.get("backend") or "claude")
    if not backend.startswith("oc:"):
        return False
    tier = [b for b, bm in batches.items() if (bm.get("backend") or "claude") == backend]
    finished = [b for b in tier if m.batch_done.get(b)]
    if 2 * len(finished) < len(tier):
        return False
    durations = [m.batch_time[b] - float(batches[b]["dispatched"]) for b in finished
                 if b in m.batch_time and batches[b].get("dispatched")]
    median = statistics.median(durations) if durations else 0.0
    threshold = max(float(audit.HEDGE_MIN_SECONDS), 2.0 * median)
    return now - float(meta["dispatched"]) > threshold
