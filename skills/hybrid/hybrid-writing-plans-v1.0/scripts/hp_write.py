#!/usr/bin/env python3
"""hp_write: the background oc-write engine.

Runs every opencode group of a plan: one writer turn, lint-repair turns in the same opencode
session, .ok/.oc markers for tasks that pass lint, and one fallback marker per group for the rest.
A run that fails on the connection is retried; if it still fails (or the failure is non-retryable),
preset hybrid switches the rest of the run to Claude (hybrid_shared.switch_to_claude) and preset
opencode holds the group.
"""
import datetime
import json
import os
import signal
import subprocess
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
import hybrid_shared  # noqa: E402

SKILL = "hybrid-writing-plans"
LEVEL_ERROR = "ERROR"
LEVEL_WARN = "WARN"
TOKEN_KEYS = ("input", "output", "reasoning", "cache_read", "cache_write")
MAX_ERR_LINES = 25
ROUND1_MESSAGE = ("Read the attached brief and follow it exactly. Reply with the full body of every task, "
                  "each between a line '@@@ BEGIN <ID>' and a line '@@@ END <ID>'.")
# A connection retry is always a fresh run, so a repair turn re-sends the brief with its repair message.
FRESH_REPAIR_MESSAGE = ("Read the attached brief and follow it exactly. An earlier reply to it was rejected by the lint "
                        "check (details below), so reply only for the tasks named below, in the same marker format.\n\n")
STOPPING = threading.Event()  # set by the SIGTERM handler: no new opencode run may start


def _pick(name: str):
    """Return the named attribute from whichever sibling module defines it."""
    for mod in (oc_run, hp_config, hp_briefs, hp_telemetry):
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


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _one_line(text) -> str:
    return " ".join(str(text).split())[:300]


def _note(res: dict) -> str:
    """The one-line detail of a failed opencode run."""
    errors = "; ".join(str(e) for e in (res.get("errors") or []))
    return _one_line(res.get("note") or errors or "opencode exited with {}".format(res.get("rc")))


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


def errors_log(work: str) -> Path:
    """The run's OC line log: <work>/oc/oc-errors.jsonl."""
    return Path(oc_dir(work)) / "oc-errors.jsonl"


def report(work: str, gid: str, tier: str, tcfg: dict, level: str, kind: str, detail: str, log: str = "") -> str:
    """Build one OC line, append it to the run's log and return it."""
    spec = hybrid_shared.model_spec(tcfg) if tcfg.get("model") else ""
    line = hybrid_shared.oc_line(level, SKILL, gid, tier, spec, kind, detail, log)
    hybrid_shared.log_line(errors_log(work), line)
    return line


def _contracts(plan_path: str) -> tuple:
    plan = plan_tool.load(plan_path)
    cs, _ = plan_tool.parse_contracts(plan)
    cs = cs or []
    if cs:
        plan_tool.analyze(cs, None, None)
    return plan, cs


def write_fallback(plan_path: str, gid: str, task_ids: list, reason: str, errors: dict, held: bool = False) -> dict:
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
    folder = oc_dir(work)
    switched = not held and bool(hybrid_shared.run_switched(Path(folder)))
    marker = {
        "gid": gid,
        "reason": reason,
        "tasks": list(task_ids),
        "brief": os.path.abspath(brief),
        "model": hybrid_shared.FALLBACK_MODEL if switched else plan_tool.TIER_MODEL[tier],
        "subagent_type": "hybrid-plan-task-writer" if plan_tool.agent_installed(repo) else "general-purpose",
        "errors": {str(t): [str(x) for x in (v or [])][:MAX_ERR_LINES] for t, v in (errors or {}).items()},
        "t": _now_iso(),
    }
    if held:
        marker["held"] = True
    _remove(os.path.join(folder, gid + ".fallback.sent"))
    plan_tool.save(os.path.join(folder, gid + ".fallback"), json.dumps(marker, indent=1) + "\n")
    return marker


def new_shared(info: dict) -> dict:
    """In-process state shared by every group thread: lock, tier semaphores, cooldowns, tripped tiers."""
    tiers = (info.get("oc") or {}).get("tiers") or {}
    sems = {}
    for name, cfg in tiers.items():
        size = int((cfg or {}).get("max_parallel", 1) or 1)
        sems[name] = threading.BoundedSemaphore(max(1, size))
    return {"lock": threading.Lock(), "sems": sems, "cooldown": {}, "tripped": {},
            "binary": os.environ.get("HYBRID_WRITING_PLANS_OC_BIN", "opencode")}


def _semaphore(shared: dict, tier: str, size) -> threading.BoundedSemaphore:
    with shared["lock"]:
        sem = shared["sems"].get(tier)
        if sem is None:
            sem = threading.BoundedSemaphore(max(1, int(size or 1)))
            shared["sems"][tier] = sem
        return sem


def _blocked(shared: dict, tier: str) -> str:
    """'breaker' when a non-retryable failure stopped the tier, 'throttle' while it cools down, else ''."""
    with shared["lock"]:
        if tier in shared["tripped"]:
            return "breaker"
        if shared["cooldown"].get(tier, 0.0) > time.time():
            return "throttle"
    return ""


def _summary(gid: str, tier: str, passed: list, failed: list, reason: str, rounds: int, secs: int,
             held: bool = False) -> str:
    if not failed:
        return "OC {} oc:{} OK {} — {} rounds — {}s".format(gid, tier, ",".join(passed), rounds, secs)
    label = "HELD" if held else "FALLBACK"
    return "OC {} oc:{} {} ({}) passed={} failed={} — {} rounds — {}s".format(
        gid, tier, label, reason, ",".join(passed) or "-", ",".join(failed), rounds, secs)


BLOCK_NOTES = {"breaker": "was stopped by the circuit breaker", "throttle": "is cooling down after a throttle",
               "config": "has no model in work.json",
               "switched": "is not used: this run switched to Claude " + hybrid_shared.FALLBACK_MODEL}


def run_group(plan_path: str, gid: str, task_ids: list, tier_name: str, shared: dict) -> dict:
    """Write one opencode group: round 1, up to max_repairs repair rounds, then a fallback (or hold) for the rest."""
    plan_path = os.path.abspath(plan_path)
    started = time.time()
    work, info = plan_tool.load_work(plan_path)
    repo = str(info.get("repo") or plan_tool.repo_root(plan_path))
    oc = info.get("oc") or {}
    tcfg = (oc.get("tiers") or {}).get(tier_name) or {}
    model = str(tcfg.get("model") or "")
    variant = str(tcfg.get("variant") or "")
    spec = hybrid_shared.model_spec(tcfg) if model else ""
    held = str(info.get("preset") or "") == "opencode"
    max_repairs = max(0, int(oc.get("max_repairs", 2)))
    cooldown_s = int(oc.get("throttle_cooldown_s", 120))
    folder = oc_dir(work)
    tdir = os.path.join(work, "tasks")
    os.makedirs(tdir, exist_ok=True)
    _remove(os.path.join(folder, gid + ".fallback"))
    _remove(os.path.join(folder, gid + ".fallback.sent"))
    st = {"pending": list(task_ids), "passed": [], "rounds": 0, "round1_ok": 0, "empty": 0, "retries": 0,
          "recovered": False, "lines": [], "tokens": {k: 0 for k in TOKEN_KEYS}}

    def emit(level: str, kind: str, detail: str, log: str = "") -> None:
        st["lines"].append(report(work, gid, tier_name, tcfg, level, kind, _one_line(detail), log))

    def fail(kind: str, note: str, log: str) -> None:
        """Report one failure. A non-retryable kind trips the breaker, and only the first trip prints a line."""
        if kind in hybrid_shared.NON_RETRYABLE:
            opened = hybrid_shared.breaker_trip(Path(folder), tier_name, spec, kind, note)
            with shared["lock"]:
                shared["tripped"][tier_name] = kind
            if not opened:  # this group ran and failed like the first one: it is not a skipped unit
                return
        elif kind == "throttle":
            with shared["lock"]:
                shared["cooldown"][tier_name] = time.time() + cooldown_s
        emit(LEVEL_ERROR, kind, note, log)

    def blocked() -> str:
        """'switched' once a hybrid run moved to Claude, else the tier's breaker or cooldown state."""
        if not held and hybrid_shared.run_switched(Path(folder)):
            return "switched"
        return _blocked(shared, tier_name)

    def switch_run(kind: str, note: str) -> bool:
        """Hybrid only: this failure moves the rest of the run to Claude. True only for the first caller."""
        return not held and hybrid_shared.switches_run(kind) and hybrid_shared.switch_to_claude(
            Path(folder), gid, tier_name, spec, kind, note)

    def write_task(tid: str, body: str, rnd: int) -> list:
        path = os.path.join(tdir, tid + ".md")
        for ext in (".ok", ".warn", ".oc", ".fail"):
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
            fail("spawn", note, "")
            return "spawn", {t: [note] for t in st["pending"]}
        # The brief travels only as the -f attachment; the injected agent prompt stays the fixed system rules.
        env = dict(os.environ, **config_env(""))
        env["PWD"] = repo
        binary = str(shared.get("binary") or os.environ.get("HYBRID_WRITING_PLANS_OC_BIN", "opencode"))
        session, errors, failed, missing = "", {}, [], []
        for rnd in range(1, max_repairs + 2):
            if rnd == 1:
                message, attach = ROUND1_MESSAGE, brief_path
            else:
                message = repair_message({t: errors[t][:MAX_ERR_LINES] for t in failed}, list(missing))
                attach = ""
            attempt = 0
            while True:  # a connection failure repeats this turn as a fresh run, never on the dead --session
                if (rnd > 1 or attempt) and _blocked(shared, tier_name) == "throttle":  # another group was throttled
                    note = "tier {} {}".format(tier_name, BLOCK_NOTES["throttle"])
                    return "throttle", {t: errors.get(t, [])[:MAX_ERR_LINES] + [note] for t in st["pending"]}
                if STOPPING.is_set():
                    return "crash", {t: ["oc-write was terminated"] for t in st["pending"]}
                if attempt:
                    cmd = build_cmd(binary, AGENT_NAME, model, variant,
                                    message if rnd == 1 else FRESH_REPAIR_MESSAGE + message, "", brief_path)
                else:
                    cmd = build_cmd(binary, AGENT_NAME, model, variant, message, session, attach)
                tag = ".r{}".format(attempt) if attempt else ""
                err_path = os.path.join(folder, "{}.{}{}.err".format(gid, rnd, tag))
                res = run_once(cmd, Path(repo), env, Path(folder) / "{}.{}{}.jsonl".format(gid, rnd, tag),
                               Path(err_path), int(tcfg.get("stall_s", 180)), int(tcfg.get("timeout_s", 900)))
                usage = res.get("usage") or {}
                for k in TOKEN_KEYS:
                    st["tokens"][k] += int(usage.get(k) or 0)
                kind = str(res.get("reason") or "")
                if not hybrid_shared.should_retry(kind, st["retries"]):
                    break
                delay = hybrid_shared.retry_delay(st["retries"])
                st["retries"] += 1
                attempt += 1
                emit(LEVEL_WARN, kind, "retry {}/{} in {}s: {}".format(
                    st["retries"], hybrid_shared.OC_RETRIES, delay, _note(res)), err_path)
                time.sleep(delay)
            st["rounds"] = rnd
            session = str(res.get("session") or session)
            if not str(res.get("text") or "").strip():
                st["empty"] += 1
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
            raw, note = kind, _note(res)
            if kind == "recovered":
                if bodies:
                    if not st["recovered"]:
                        st["recovered"] = True
                        emit(LEVEL_WARN, "recovered", note, err_path)
                    kind = ""
                else:
                    kind = "crash"
            if kind:
                switched = switch_run(raw, note)  # before fail(): a thread that sees the breaker sees the switch
                fail(kind, note, err_path)
                if switched:
                    line = hybrid_shared.switch_line(SKILL, hybrid_shared.run_switched(Path(folder)))
                    hybrid_shared.log_line(errors_log(work), line)
                    st["lines"].append(line)
                return kind, {t: errors.get(t, [])[:MAX_ERR_LINES] + [note] for t in st["pending"]}
            if not st["pending"]:
                return "", {}
            if not session:
                break
        out = {t: errors[t][:MAX_ERR_LINES] for t in failed}
        out.update({t: ["missing from your reply"] for t in missing})
        if failed:
            kind = "lint"
            detail = "{} still failing lint after {} rounds: {}".format(
                ",".join(failed), st["rounds"], errors[failed[0]][0])
        elif st["empty"] == st["rounds"]:
            kind = "empty"
            detail = "opencode returned no text in {} rounds".format(st["rounds"])
        else:
            kind = "format"
            detail = "no @@@ BEGIN/END block for {} after {} rounds".format(",".join(missing), st["rounds"])
        emit(LEVEL_WARN, kind, detail, err_path)
        return kind, out

    def stop_early(reason: str) -> tuple:
        """(reason, errors) for a group that never spawned: its tier is stopped, cooling down or has no model."""
        note = "tier {} {}".format(tier_name, BLOCK_NOTES[reason])
        if reason == "breaker":
            hybrid_shared.breaker_skip(Path(folder), tier_name, spec)
        elif reason == "config":
            fail("config", note, "")
        return reason, {t: [note] for t in st["pending"]}

    reason = blocked()
    if not reason and not model:
        reason = "config"
    if reason:
        reason, errs_out = stop_early(reason)
    else:
        with _semaphore(shared, tier_name, tcfg.get("max_parallel", 1)):
            started = time.time()  # a queued group's clock starts when it gets a slot
            reason = blocked()
            if reason:
                reason, errs_out = stop_early(reason)
            else:
                try:
                    reason, errs_out = turns()
                except Exception as exc:
                    note = "{}: {}".format(type(exc).__name__, _one_line(exc))
                    fail("crash", note, "")
                    reason, errs_out = "crash", {t: [note] for t in st["pending"]}
    pending = [t for t in task_ids if t in st["pending"]]
    passed = [t for t in task_ids if t in st["passed"]]
    if not pending:
        reason = ""
    else:
        reason = reason or "format"
        try:
            write_fallback(plan_path, gid, pending, reason, {t: errs_out.get(t, []) for t in pending}, held=held)
        except Exception:
            pass
    secs = round(time.time() - started, 1)
    outcome = "ok" if not pending else ("partial" if passed else "fallback")
    line = _summary(gid, tier_name, passed, pending, reason, st["rounds"], int(round(secs)), held)
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
            "held": held, "oc_lines": list(st["lines"]), "line": line}


def _oc_groups(info: dict, work: str = "") -> list:
    """[(gid, task ids, tier)] for every group whose backend is oc:<tier>, ordered by gid.

    With `work`, only tasks that are not done yet are listed (a contracts re-run keeps the bodies that survived,
    and a reviewer may have fixed one), and a group with nothing left is dropped."""
    groups = info.get("groups") or {}
    out = []
    for gid, backend in sorted((info.get("backend") or {}).items()):
        if isinstance(backend, str) and backend.startswith("oc:") and gid in groups:
            ids = [t for t in groups[gid]
                   if not work or plan_tool.done_state(os.path.join(work, "tasks", t + ".md"), "ok") != "done"]
            if ids:
                out.append((gid, ids, backend[3:]))
    return out


def _kill_children() -> None:
    """SIGTERM, then SIGKILL, the process group of every opencode run this process started.

    Each run is its own session leader (oc_run spawns with start_new_session), so the children are found as the
    processes whose parent is this one. ponytail: a `ps` scan, run twice, not a registry in oc_run; a run spawned
    in the microseconds around the scan is missed, and a shared spawn registry would close that."""
    me, own = os.getpid(), os.getpgrp()
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            out = subprocess.run(["ps", "-A", "-o", "pid=,ppid=,pgid="], capture_output=True, text=True,
                                 timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            return
        for line in out.splitlines():
            f = line.split()
            if len(f) == 3 and all(x.isdigit() for x in f) and int(f[1]) == me and int(f[2]) != own:
                try:
                    os.killpg(int(f[2]), sig)
                except OSError:
                    pass
        time.sleep(0.3)


def _crash_result(plan_path: str, gid: str, task_ids: list, tier: str, exc: Exception) -> dict:
    work, info = plan_tool.load_work(plan_path)
    held = str(info.get("preset") or "") == "opencode"
    tcfg = ((info.get("oc") or {}).get("tiers") or {}).get(tier) or {}
    failed = [t for t in task_ids
              if plan_tool.done_state(os.path.join(work, "tasks", t + ".md"), "ok") != "done"]
    passed = [t for t in task_ids if t not in failed]
    note = "{}: {}".format(type(exc).__name__, _one_line(exc))
    lines = []
    if failed:
        lines.append(report(work, gid, tier, tcfg, LEVEL_ERROR, "crash", note))
        try:
            write_fallback(plan_path, gid, failed, "crash", {t: [note] for t in failed}, held=held)
        except Exception:
            pass
    return {"gid": gid, "tier": tier, "tasks": list(task_ids), "passed": passed, "failed": failed,
            "outcome": "ok" if not failed else ("partial" if passed else "fallback"),
            "reason": "crash" if failed else "", "held": held, "oc_lines": lines,
            "line": _summary(gid, tier, passed, failed, "crash", 0, 0, held)}


def _print_result(res: dict, lock) -> None:
    """Print one group's OC lines and its summary line together, without interleaving with other groups."""
    with lock:
        for line in res.get("oc_lines") or []:
            print(line)
        print(res["line"])
        sys.stdout.flush()


def oc_write(plan_path: str) -> int:
    """Run every opencode group in its own thread, print each group's lines the moment it ends; always 0."""
    try:
        plan_path = os.path.abspath(plan_path)
        work, info = plan_tool.load_work(plan_path)
        groups = _oc_groups(info, work) if info else []
        if not groups:
            print("OC none")
            return 0
        pid_path = os.path.join(oc_dir(work), "oc-write.pid")
        plan_tool.save(pid_path, "{}\n".format(os.getpid()))
        results = {}
        shared = new_shared(info)
        STOPPING.clear()

        def on_term(signum, frame):
            STOPPING.set()
            _kill_children()
            _remove(pid_path)
            print("OC-WRITE terminated by SIGTERM: opencode runs stopped, unfinished tasks are left for wait")
            sys.stdout.flush()
            os._exit(0)

        old_term = None
        try:
            old_term = signal.signal(signal.SIGTERM, on_term)
        except ValueError:  # not the main thread (in-process callers): no handler
            pass
        try:

            def one(gid: str, ids: list, tier: str) -> None:
                try:
                    res = run_group(plan_path, gid, ids, tier, shared)
                except Exception as exc:
                    res = _crash_result(plan_path, gid, ids, tier, exc)
                results[gid] = res
                _print_result(res, shared["lock"])

            threads = [threading.Thread(target=one, args=g, daemon=True) for g in groups]
            for th in threads:
                th.start()
            for th in threads:
                th.join()
        finally:
            _remove(pid_path)
            if old_term is not None:
                signal.signal(signal.SIGTERM, old_term)
        ok = 0
        for gid, ids, tier in groups:
            res = results.get(gid)
            if res is None:
                res = _crash_result(plan_path, gid, ids, tier, RuntimeError("group thread returned nothing"))
                _print_result(res, shared["lock"])
            ok += 1 if res.get("outcome") == "ok" else 0
        for line in hybrid_shared.breaker_summary(Path(oc_dir(work)), SKILL):
            hybrid_shared.log_line(errors_log(work), line)
            print(line)
        print("OC-WRITE done {}/{} groups".format(ok, len(groups)))
        sys.stdout.flush()
    except Exception as exc:
        print("OC-WRITE error {}: {}".format(type(exc).__name__, _one_line(exc)))
    return 0
