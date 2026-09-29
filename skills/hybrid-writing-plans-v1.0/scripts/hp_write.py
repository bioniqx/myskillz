#!/usr/bin/env python3
"""hp_write: the background oc-write engine.

Runs every opencode group of a plan: one writer turn, lint-repair turns in the same opencode
session, .ok/.oc markers for tasks that pass lint, and one fallback marker per group for the rest.
"""
import datetime
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_tool  # noqa: E402
import oc_run  # noqa: E402
import hp_config  # noqa: E402
import hp_briefs  # noqa: E402
import hp_telemetry  # noqa: E402
import hp_doctor  # noqa: E402

TOKEN_KEYS = ("input", "output", "reasoning", "cache_read", "cache_write")
MAX_ERR_LINES = 25
ROUND1_MESSAGE = ("Read the attached brief and follow it exactly. Reply with the full body of every task, "
                  "each between a line '@@@ BEGIN <ID>' and a line '@@@ END <ID>'.")


def _pick(name: str):
    """Return the named attribute from whichever sibling module defines it."""
    for mod in (oc_run, hp_config, hp_briefs, hp_telemetry, hp_doctor):
        value = getattr(mod, name, None)
        if value is not None:
            return value
    raise AttributeError("no sibling module defines {}".format(name))


build_cmd = _pick("build_cmd")
run_once = _pick("run_once")
AGENT_NAME = _pick("AGENT_NAME")
config_env = _pick("config_env")
record = _pick("record")
split_bodies = _pick("split_bodies")
repair_message = _pick("repair_message")
doctor_cache_path = _pick("doctor_cache_path")
mark_down = _pick("mark_down")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _one_line(text) -> str:
    return " ".join(str(text).split())[:300]


def _remove(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def oc_dir(work: str) -> str:
    """Return <work>/oc, creating it when missing."""
    path = os.path.join(work, "oc")
    os.makedirs(path, exist_ok=True)
    return path


def _contracts(plan_path: str) -> tuple:
    plan = plan_tool.load(plan_path)
    cs, _ = plan_tool.parse_contracts(plan)
    cs = cs or []
    if cs:
        plan_tool.analyze(cs, None, None)
    return plan, cs


def write_fallback(plan_path: str, gid: str, task_ids: list, reason: str, errors: dict) -> dict:
    """Render briefs/<gid>F.md for exactly task_ids and write oc/<gid>.fallback; return the marker."""
    plan_path = os.path.abspath(plan_path)
    work, info = plan_tool.load_work(plan_path)
    repo = info.get("repo") or plan_tool.repo_root(plan_path)
    plan, cs = _contracts(plan_path)
    cmap = {c["id"]: c for c in cs}
    group = [cmap[t] for t in task_ids if t in cmap]
    brief = os.path.join(work, "briefs", gid + "F.md")
    plan_tool.save(brief, plan_tool.writer_brief(plan_path, plan, group, cmap, work, info.get("spec"), repo,
                                                 list(info.get("allow") or [])))
    tier = max((c["tier"] for c in group), key=lambda t: plan_tool.TIER_RANK[t]) if group else "std"
    marker = {
        "gid": gid,
        "reason": reason,
        "tasks": list(task_ids),
        "brief": os.path.abspath(brief),
        "model": plan_tool.TIER_MODEL[tier],
        "subagent_type": "plan-task-writer" if plan_tool.agent_installed(repo) else "general-purpose",
        "errors": {str(t): [str(x) for x in (v or [])][:MAX_ERR_LINES] for t, v in (errors or {}).items()},
        "t": _now_iso(),
    }
    folder = oc_dir(work)
    _remove(os.path.join(folder, gid + ".fallback.sent"))
    plan_tool.save(os.path.join(folder, gid + ".fallback"), json.dumps(marker, indent=1) + "\n")
    return marker


def new_shared(info: dict) -> dict:
    """In-process state shared by every group thread: lock, tier semaphores, cooldowns, down tiers."""
    tiers = (info.get("oc") or {}).get("tiers") or {}
    sems = {}
    for name, cfg in tiers.items():
        size = int((cfg or {}).get("max_parallel", 1) or 1)
        sems[name] = threading.BoundedSemaphore(max(1, size))
    return {"lock": threading.Lock(), "sems": sems, "cooldown": {}, "down": set(),
            "binary": os.environ.get("HP_OC_BIN", "opencode")}


def _semaphore(shared: dict, tier: str, size) -> threading.BoundedSemaphore:
    with shared["lock"]:
        sem = shared["sems"].get(tier)
        if sem is None:
            sem = threading.BoundedSemaphore(max(1, int(size or 1)))
            shared["sems"][tier] = sem
        return sem


def _cache_down(tier: str) -> bool:
    try:
        data = json.loads(Path(doctor_cache_path()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    tiers = data.get("tiers") if isinstance(data, dict) else None
    entry = tiers.get(tier) if isinstance(tiers, dict) else None
    return isinstance(entry, dict) and bool(entry.get("down"))


def _blocked(shared: dict, tier: str) -> str:
    """'unavailable' when the tier is down, 'throttle' while it cools down, else ''."""
    with shared["lock"]:
        if tier in shared["down"]:
            return "unavailable"
        if shared["cooldown"].get(tier, 0.0) > time.time():
            return "throttle"
    return "unavailable" if _cache_down(tier) else ""


def _summary(gid: str, tier: str, passed: list, failed: list, reason: str, rounds: int, secs: int) -> str:
    if not failed:
        return "OC {} oc:{} OK {} — {} rounds — {}s".format(gid, tier, ",".join(passed), rounds, secs)
    return "OC {} oc:{} FALLBACK ({}) passed={} failed={} — {} rounds — {}s".format(
        gid, tier, reason, ",".join(passed) or "-", ",".join(failed), rounds, secs)


BLOCK_NOTES = {"unavailable": "is marked down", "throttle": "is cooling down after a throttle",
               "spawn": "has no model in work.json"}


def run_group(plan_path: str, gid: str, task_ids: list, tier_name: str, shared: dict) -> dict:
    """Write one opencode group: round 1, up to max_repairs repair rounds, then a fallback for the rest."""
    plan_path = os.path.abspath(plan_path)
    started = time.time()
    work, info = plan_tool.load_work(plan_path)
    repo = str(info.get("repo") or plan_tool.repo_root(plan_path))
    oc = info.get("oc") or {}
    tcfg = (oc.get("tiers") or {}).get(tier_name) or {}
    model = str(tcfg.get("model") or "")
    variant = str(tcfg.get("variant") or "")
    max_repairs = max(0, int(oc.get("max_repairs", 2)))
    cooldown_s = int(oc.get("throttle_cooldown_s", 120))
    folder = oc_dir(work)
    tdir = os.path.join(work, "tasks")
    os.makedirs(tdir, exist_ok=True)
    _remove(os.path.join(folder, gid + ".fallback"))
    _remove(os.path.join(folder, gid + ".fallback.sent"))
    st = {"pending": list(task_ids), "passed": [], "rounds": 0, "round1_ok": 0,
          "tokens": {k: 0 for k in TOKEN_KEYS}}

    def write_task(tid: str, body: str, rnd: int) -> list:
        path = os.path.join(tdir, tid + ".md")
        for ext in (".ok", ".warn", ".oc"):
            _remove(path + ext)
        plan_tool.save(path, body.strip("\n") + "\n")
        errs, warns, _ = plan_tool.lint_file(plan_path, path)
        if errs:
            return [str(e) for e in errs]
        if warns:
            plan_tool.save(path + ".warn", "\n".join(warns))
        plan_tool.save(path + ".oc", json.dumps({"tier": tier_name, "model": model, "variant": variant,
                                                 "round": rnd}) + "\n")
        plan_tool.touch(path + ".ok")
        return []

    def turns() -> tuple:
        brief_path = os.path.join(work, "briefs", gid + ".oc.md")
        if not os.path.isfile(brief_path):
            note = "missing oc brief {}".format(brief_path)
            return "spawn", {t: [note] for t in st["pending"]}
        # The brief travels only as the -f attachment; the injected agent prompt stays the fixed system rules.
        env = dict(os.environ, **config_env(""))
        env["PWD"] = repo
        binary = str(shared.get("binary") or os.environ.get("HP_OC_BIN", "opencode"))
        session, errors, failed, missing = "", {}, [], []
        for rnd in range(1, max_repairs + 2):
            if rnd == 1:
                message, attach = ROUND1_MESSAGE, brief_path
            else:
                message = repair_message({t: errors[t][:MAX_ERR_LINES] for t in failed}, list(missing))
                attach = ""
            cmd = build_cmd(binary, AGENT_NAME, model, variant, message, session, attach)
            res = run_once(cmd, Path(repo), env, Path(folder) / "{}.{}.jsonl".format(gid, rnd),
                           Path(folder) / "{}.{}.err".format(gid, rnd),
                           int(tcfg.get("stall_s", 180)), int(tcfg.get("timeout_s", 900)))
            st["rounds"] = rnd
            usage = res.get("usage") or {}
            for k in TOKEN_KEYS:
                st["tokens"][k] += int(usage.get(k) or 0)
            session = str(res.get("session") or session)
            bodies = split_bodies(str(res.get("text") or ""), list(st["pending"]))
            failed, missing = [], []
            for tid in list(st["pending"]):
                if tid not in bodies:
                    missing.append(tid)
                    continue
                errs = write_task(tid, bodies[tid], rnd)
                if errs:
                    errors[tid] = errs
                    failed.append(tid)
                    continue
                errors.pop(tid, None)
                st["pending"].remove(tid)
                st["passed"].append(tid)
                if rnd == 1:
                    st["round1_ok"] += 1
            run_errors = [str(e) for e in (res.get("errors") or [])]
            reason = str(res.get("reason") or "")
            if not reason and (res.get("rc") != 0 or run_errors):
                reason = "crash"
            if reason:
                note = _one_line(res.get("note") or "; ".join(run_errors)
                                 or "opencode exited with {}".format(res.get("rc")))
                if reason == "unavailable":
                    # Held across mark_down so concurrent read-modify-writes of the cache never lose a tier.
                    with shared["lock"]:
                        shared["down"].add(tier_name)
                        try:
                            mark_down(doctor_cache_path(), tier_name, reason, note)
                        except Exception:
                            pass
                elif reason == "throttle":
                    with shared["lock"]:
                        shared["cooldown"][tier_name] = time.time() + cooldown_s
                return reason, {t: errors.get(t, [])[:MAX_ERR_LINES] + [note] for t in st["pending"]}
            if not st["pending"]:
                return "", {}
            if not session:
                break
        out = {t: errors[t][:MAX_ERR_LINES] for t in failed}
        out.update({t: ["missing from your reply"] for t in missing})
        return ("lint" if failed else "format"), out

    reason = _blocked(shared, tier_name)
    if not reason and not model:
        reason = "spawn"
    if reason:
        note = "tier {} {}".format(tier_name, BLOCK_NOTES[reason])
        errs_out = {t: [note] for t in st["pending"]}
    else:
        with _semaphore(shared, tier_name, tcfg.get("max_parallel", 1)):
            reason = _blocked(shared, tier_name)
            if reason:
                note = "tier {} {}".format(tier_name, BLOCK_NOTES[reason])
                errs_out = {t: [note] for t in st["pending"]}
            else:
                try:
                    reason, errs_out = turns()
                except Exception as exc:
                    note = "{}: {}".format(type(exc).__name__, _one_line(exc))
                    reason, errs_out = "crash", {t: [note] for t in st["pending"]}
    pending = [t for t in task_ids if t in st["pending"]]
    passed = [t for t in task_ids if t in st["passed"]]
    if not pending:
        reason = ""
    else:
        reason = reason or "format"
        try:
            write_fallback(plan_path, gid, pending, reason, {t: errs_out.get(t, []) for t in pending})
        except Exception:
            pass
    secs = round(time.time() - started, 1)
    outcome = "ok" if not pending else ("partial" if passed else "fallback")
    line = _summary(gid, tier_name, passed, pending, reason, st["rounds"], int(round(secs)))
    rec = {"t": _now_iso(), "kind": "group", "repo": repo, "plan": plan_path, "gid": gid, "tier": tier_name,
           "model": model, "variant": variant, "tasks": list(task_ids), "rounds": st["rounds"],
           "round1_ok": st["round1_ok"], "outcome": outcome, "reason": reason, "duration_s": secs,
           "tokens": dict(st["tokens"])}
    try:
        record(rec)
    except Exception:
        pass
    return {"gid": gid, "tier": tier_name, "model": model, "variant": variant, "tasks": list(task_ids),
            "passed": passed, "failed": pending, "rounds": st["rounds"], "round1_ok": st["round1_ok"],
            "outcome": outcome, "reason": reason, "duration_s": secs, "tokens": dict(st["tokens"]),
            "line": line}


def _oc_groups(info: dict) -> list:
    """[(gid, task ids, tier)] for every group whose backend is oc:<tier>, ordered by gid."""
    groups = info.get("groups") or {}
    out = []
    for gid, backend in sorted((info.get("backend") or {}).items()):
        if isinstance(backend, str) and backend.startswith("oc:") and gid in groups:
            out.append((gid, list(groups[gid]), backend[3:]))
    return out


def _crash_result(plan_path: str, gid: str, task_ids: list, tier: str, exc: Exception) -> dict:
    work, _ = plan_tool.load_work(plan_path)
    failed = [t for t in task_ids
              if plan_tool.done_state(os.path.join(work, "tasks", t + ".md"), "ok") != "done"]
    passed = [t for t in task_ids if t not in failed]
    note = "{}: {}".format(type(exc).__name__, _one_line(exc))
    if failed:
        try:
            write_fallback(plan_path, gid, failed, "crash", {t: [note] for t in failed})
        except Exception:
            pass
    return {"gid": gid, "tier": tier, "tasks": list(task_ids), "passed": passed, "failed": failed,
            "outcome": "ok" if not failed else ("partial" if passed else "fallback"),
            "reason": "crash" if failed else "", "line": _summary(gid, tier, passed, failed, "crash", 0, 0)}


def oc_write(plan_path: str) -> int:
    """Run every opencode group of the plan in its own thread, print one line per group; always 0."""
    try:
        plan_path = os.path.abspath(plan_path)
        work, info = plan_tool.load_work(plan_path)
        groups = _oc_groups(info) if info else []
        if not groups:
            print("OC none")
            return 0
        pid_path = os.path.join(oc_dir(work), "oc-write.pid")
        plan_tool.save(pid_path, "{}\n".format(os.getpid()))
        results = {}
        try:
            shared = new_shared(info)

            def one(gid: str, ids: list, tier: str) -> None:
                try:
                    results[gid] = run_group(plan_path, gid, ids, tier, shared)
                except Exception as exc:
                    results[gid] = _crash_result(plan_path, gid, ids, tier, exc)

            threads = [threading.Thread(target=one, args=g, daemon=True) for g in groups]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
        finally:
            _remove(pid_path)
        ok = 0
        for gid, ids, tier in groups:
            res = results.get(gid) or _crash_result(plan_path, gid, ids, tier,
                                                    RuntimeError("group thread returned nothing"))
            print(res["line"])
            ok += 1 if res.get("outcome") == "ok" else 0
        print("OC-WRITE done {}/{} groups".format(ok, len(groups)))
        sys.stdout.flush()
    except Exception as exc:
        print("OC-WRITE error {}: {}".format(type(exc).__name__, _one_line(exc)))
    return 0
