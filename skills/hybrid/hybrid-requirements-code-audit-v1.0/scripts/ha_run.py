#!/usr/bin/env python3
"""ha_run: the oc-run engine.

Runs one investigator batch (batch-NN), verifier batch (batch-VNN) or parser section (section-NN) on
opencode. It sends round 1 with the attached opencode brief. When ids are missing or the JSON does not
parse, it runs repair turns in the same session. It then applies the evidence oracle and writes the
output file atomically. It also writes the event file and appends one telemetry record. Each OC-ERROR or
OC-WARN line is printed the moment it happens and appended to <audit>/oc-errors.jsonl, then one summary
line is printed. It never writes state.json or the doctor cache and never raises.
"""
import contextlib
import datetime
import io
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit  # noqa: E402
import oc_run  # noqa: E402
import ha_config  # noqa: E402
import ha_briefs  # noqa: E402
import ha_telemetry  # noqa: E402
import ha_doctor  # noqa: E402
import ha_oracle  # noqa: E402
import hybrid_shared  # noqa: E402
from ha_router import effective_preset, route  # noqa: E402

TOKEN_KEYS = ("input", "output", "reasoning", "cache_read", "cache_write")
ORACLE_KEYS = ("foreign", "dropped", "demoted", "invalid_status")
MAX_ERR_LINES = 25
BRIEF_DIRS = {"investigator": "batches", "verifier": "verify", "parser": "parse"}
OUT_DIRS = {"investigator": "findings", "verifier": "verify", "parser": "parse"}
ROUND1_MESSAGE = ("Read the attached brief and follow it exactly. Reply with the JSON rows, one object per line, "
                  "between a line '@@@ BEGIN {name}' and a line '@@@ END {name}'.")
ROLE_PATTERNS = (("verifier", re.compile(r"^batch-V\d+$")),
                 ("investigator", re.compile(r"^batch-\d+$")),
                 ("parser", re.compile(r"^section-\d+$")))
WRAPPER_LINES = ("[", "]", "],", "[,")
SKILL = "hybrid-requirements-code-audit"
ERRORS_FILE = "oc-errors.jsonl"
QUIET_REASONS = ("cooldown", "breaker", "switched")
_UMASK = os.umask(0)  # read once: umask is process-global
os.umask(_UMASK)


def _pick(name: str):
    """Return the named attribute from whichever sibling module defines it."""
    for mod in (oc_run, ha_config, ha_briefs, ha_telemetry, ha_doctor, ha_oracle):
        value = getattr(mod, name, None)
        if value is not None:
            return value
    raise AttributeError("no sibling module defines {}".format(name))


build_cmd = _pick("build_cmd")
run_once = _pick("run_once")
AGENT_NAMES = _pick("AGENT_NAMES")
config_env = _pick("config_env")
record = _pick("record")
split_block = _pick("split_block")
repair_message = _pick("repair_message")
doctor_cache_path = _pick("doctor_cache_path")
load_doctor = _pick("load_doctor")
apply_oracle = _pick("apply_oracle")
normalize_row = audit.normalize_row


def role_of(name: str) -> str:
    """'investigator' for batch-NN, 'verifier' for batch-VNN, 'parser' for section-NN, else ''."""
    for role, pattern in ROLE_PATTERNS:
        if pattern.match(name or ""):
            return role
    return ""


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _one_line(text) -> str:
    return " ".join(str(text).split())[:300]


def parse_block(block: str) -> tuple:
    """Parse a marker block with read_jsonl tolerance; return (normalized rows, error lines)."""
    rows, errors = [], []
    for n, raw in enumerate((block or "").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("//") or line.startswith("#") or line in WRAPPER_LINES:
            continue
        if line.endswith(","):
            line = line[:-1].rstrip()
        try:
            obj = json.loads(line)
        except ValueError as exc:
            errors.append("line {}: {} — {}".format(n, _one_line(exc), line[:120]))
            continue
        objs = obj if isinstance(obj, list) else [obj]
        if not all(isinstance(o, dict) for o in objs):
            errors.append("line {}: not a JSON object — {}".format(n, line[:120]))
        rows.extend(normalize_row(o) for o in objs if isinstance(o, dict))
    return rows, errors


def atomic_write(path: Path, text: str) -> None:
    """Write text to path through mkstemp in the same directory and os.replace, with the umask file mode."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.chmod(tmp, 0o666 & ~_UMASK)
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _context(cwd: str) -> dict:
    """Read-only view of the audit through audit.Ctx: output dir, repo root, config.json, state.json."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            c = audit.Ctx(cwd)
    except SystemExit:
        raise RuntimeError(_one_line(buf.getvalue()) or "no audit here")
    return {"out": Path(c.out).resolve(), "repo": Path(c.repo).resolve(), "cfg": c.cfg, "state": c.state}


def _unit(state: dict, name: str, role: str) -> tuple:
    """(checklist ids, stored backend) of the batch, verifier batch or parser section."""
    if role == "parser":
        backends = (state.get("parse") or {}).get("backends") or {}
        return [], str(backends.get(name) or "")
    units = state.get("verify" if role == "verifier" else "batches")
    entry = units.get(name) if isinstance(units, dict) else None
    if not isinstance(entry, dict):
        return [], ""
    return [str(i) for i in entry.get("ids") or []], str(entry.get("backend") or "")


def _tier_of(ctx: dict, role: str, backend: str) -> str:
    """The opencode tier of the unit: its stored oc:<tier> backend, else what the router picks for its role."""
    if backend.startswith("oc:"):
        return backend[3:]
    if backend == "claude":
        return ""
    cfg = ctx["cfg"]
    routed = route(role, cfg.get("routing") or {}, ctx["state"].get("health") or load_doctor(doctor_cache_path()),
                   str(cfg.get("preset") or ""), ctx["state"].get("cooldown"), time.time(), ctx["out"])
    return routed[3:] if routed.startswith("oc:") else ""


def _audit_rel(out: Path, repo: Path) -> str:
    try:
        rel = os.path.relpath(str(out), str(repo))
    except ValueError:
        return ""
    return "" if rel.startswith("..") else rel


def _brief_path(ctx: dict, st: dict) -> Path:
    return ctx["out"] / BRIEF_DIRS[st["role"]] / (st["name"] + ".oc.md")


def _new_state(ctx: dict, name: str, role: str) -> dict:
    ids, backend = _unit(ctx["state"], name, role) if role else ([], "")
    tier = _tier_of(ctx, role, backend) if role else ""
    tcfg = ((ctx["cfg"].get("routing") or {}).get("tiers") or {}).get(tier) or {}
    return {"name": name, "role": role, "tier": tier, "tcfg": dict(tcfg),
            "model": str(tcfg.get("model") or ""), "variant": str(tcfg.get("variant") or ""),
            "spec": hybrid_shared.model_spec(tcfg) if tcfg else "", "log": "",
            "ids": ids, "rows": {}, "parser_rows": [], "parse_ok": False, "rounds": 0, "round1_valid": 0,
            "oracle": {k: 0 for k in ORACLE_KEYS}, "tokens": {k: 0 for k in TOKEN_KEYS}}


def _hybrid(ctx: dict) -> bool:
    """True when this audit runs in preset hybrid (the only preset whose run can switch to Claude)."""
    try:
        return effective_preset(ctx["cfg"].get("routing") or {}, str(ctx["cfg"].get("preset") or "")) == "hybrid"
    except ValueError:
        return False


def _blocked(ctx: dict, st: dict) -> tuple:
    """(reason, message) that stops the unit before any spawn, else ('', '')."""
    name, role, tier = st["name"], st["role"], st["tier"]
    if not role:
        return "spawn", "unknown batch name {}".format(name)
    if role != "parser" and not st["ids"]:
        return "spawn", "no checklist ids for {} in state.json".format(name)
    if _hybrid(ctx) and hybrid_shared.run_switched(ctx["out"]):
        return "switched", "the run switched to Claude {}; opencode is not used any more".format(
            hybrid_shared.FALLBACK_MODEL)
    if not tier or not st["model"]:
        return "spawn", "no opencode tier routed for {}".format(name)
    brief = _brief_path(ctx, st)
    if not brief.is_file():
        return "spawn", "missing opencode brief {}".format(brief)
    if hybrid_shared.breaker_skip(ctx["out"], tier, st["spec"]):
        return "breaker", "circuit breaker open for tier {} ({})".format(tier, st["spec"])
    until = float((ctx["state"].get("cooldown") or {}).get(tier) or 0)
    now = time.time()
    if now < until:
        return "cooldown", "tier {} cools down for {}s more".format(tier, int(until - now))
    return "", ""


def _add_stats(st: dict, stats) -> None:
    for k in ORACLE_KEYS:
        st["oracle"][k] += int((stats or {}).get(k) or 0)


def _absorb(st: dict, rows: list, errors: list, missing: list, repo: Path, rnd: int, out: Path) -> list:
    """Run the oracle on one round's rows and keep rows that fill ids still missing.

    Returns the oracle's problem lines (checklist problems, rejected rows) for the next repair turn;
    a parser section with problems does not pass.
    """
    role = st["role"]
    if role == "parser":
        if errors:
            return []
        kept, stats = apply_oracle(rows, [], repo, role, audit_dir=out)
        _add_stats(st, stats)
        if stats.get("problems"):
            return list(stats["problems"])
        st["parser_rows"] = list(kept)
        st["parse_ok"] = True
        if rnd == 1:
            st["round1_valid"] = len(kept)
        return []
    # rows for ids filled in an earlier round are discarded, so keep them out of the oracle stats
    fresh = [r for r in rows if str(r.get("id", "")).strip() not in st["rows"]]
    kept, stats = apply_oracle(fresh, list(st["ids"]), repo, role, audit_dir=out)
    _add_stats(st, stats)
    for row in kept:
        rid = str(row.get("id"))
        if rid in missing and rid not in st["rows"]:
            st["rows"][rid] = row
    if rnd == 1:
        st["round1_valid"] = len(st["rows"])
    return list(stats.get("problems") or [])


def _log_of(st: dict) -> str:
    """The unit's last stderr file when it exists, else ''."""
    return st["log"] if st["log"] and Path(st["log"]).is_file() else ""


def _emit(ctx, st: dict, level: str, kind: str, detail: str, log: str = "") -> None:
    """Print one OC line at once and append it to <audit>/oc-errors.jsonl; a non-retryable ERROR trips the breaker."""
    line = hybrid_shared.oc_line(level, SKILL, st["name"], st["tier"] or "none", st["spec"] or "none",
                                 kind, detail, log)
    print(line)
    sys.stdout.flush()
    if ctx is None:
        return
    try:
        hybrid_shared.log_line(ctx["out"] / ERRORS_FILE, line)
        if level == "ERROR" and kind in hybrid_shared.NON_RETRYABLE and st["tier"]:
            hybrid_shared.breaker_trip(ctx["out"], st["tier"], st["spec"], kind, detail)
    except OSError:
        pass  # the line is already printed; a failed state write must not change the outcome


def _report_failure(ctx, st, name: str, reason: str, note: str) -> None:
    """Print the OC line of a failed unit; cooldown and breaker blocks stay quiet, their cause was reported already."""
    if not reason or reason in QUIET_REASONS:
        return
    st = st or {"name": name, "tier": "", "spec": "", "log": ""}
    _emit(ctx, st, "WARN" if reason == "format" else "ERROR", reason, note, _log_of(st))


def _turns(ctx: dict, st: dict) -> tuple:
    """Round 1 plus at most max_repairs repair rounds; return (reason, message), ('', '') on success."""
    name, role, ids = st["name"], st["role"], st["ids"]
    repo, out, tcfg = ctx["repo"], ctx["out"], st["tcfg"]
    routing = ctx["cfg"].get("routing") or {}
    env = dict(os.environ, **config_env(role, _audit_rel(out, repo)))
    env["PWD"] = str(repo)
    binary = os.environ.get("HA_OC_BIN", "opencode")
    folder = out / "oc"
    folder.mkdir(parents=True, exist_ok=True)
    max_repairs = max(0, int(routing.get("max_repairs", 2)))
    session, missing, errors = "", list(ids), []
    for rnd in range(1, max_repairs + 2):
        if rnd == 1:
            message, attach = ROUND1_MESSAGE.format(name=name), str(_brief_path(ctx, st))
        else:
            message, attach = repair_message(name, list(missing), errors[:MAX_ERR_LINES]), ""
        err_path = folder / "{}.{}.err".format(name, rnd)
        cmd = build_cmd(binary, AGENT_NAMES[role], st["model"], st["variant"], message, session, attach)
        retries = 0
        while True:  # a connection failure repeats this exact turn; the failed run's session is never resumed
            res = run_once(cmd, repo, env, folder / "{}.{}.jsonl".format(name, rnd), err_path,
                           int(tcfg.get("stall_s", 180)), int(tcfg.get("timeout_s", 900)))
            st["rounds"] = rnd
            st["log"] = str(err_path)
            usage = res.get("usage") or {}
            for k in TOKEN_KEYS:
                st["tokens"][k] += int(usage.get(k) or 0)
            run_errors = [str(e) for e in (res.get("errors") or [])]
            reason = str(res.get("reason") or "")
            if not reason and (res.get("rc") != 0 or run_errors):
                reason = "crash"
            note = str(res.get("note") or "")
            if reason in ("stall", "timeout") and note:
                first = note  # the watchdog's own reason beats whatever the killed process printed last
            else:
                first = hybrid_shared.first_error(run_errors, str(res.get("stderr_tail") or ""))
            detail = _one_line(first or note or "opencode exited with {}".format(res.get("rc")))
            if not hybrid_shared.should_retry(reason, retries):
                break
            delay = hybrid_shared.retry_delay(retries)
            retries += 1
            _emit(ctx, st, "WARN", reason, "retry {}/{} in {}s: {}".format(retries, hybrid_shared.OC_RETRIES, delay, detail),
                  _log_of(st))
            time.sleep(delay)
        session = str(res.get("session") or session)
        if reason == "recovered":
            _emit(ctx, st, "WARN", "recovered", detail, _log_of(st))
        elif not reason and not str(res.get("text") or "").strip():
            _emit(ctx, st, "WARN", "empty", "opencode returned no text", _log_of(st))
        block = split_block(str(res.get("text") or ""), name)
        rows, errors = parse_block(block)
        if not rows and not errors:
            errors = ["no JSON rows between '@@@ BEGIN {0}' and '@@@ END {0}' in your reply".format(name)]
        errors = errors + _absorb(st, rows, errors, list(missing), repo, rnd, out)
        missing = [i for i in ids if i not in st["rows"]]
        if (st["parse_ok"] if role == "parser" else not missing):
            return "", ""
        if reason and reason != "recovered":
            return reason, detail
        if not session:
            break
    if role == "parser":
        note = "; ".join(errors[:3]) or "no parsable block"
    else:
        note = "ids still missing after {} rounds: {}".format(st["rounds"], ", ".join(missing))
    return "format", _one_line(note)


def _switch(ctx: dict, st: dict, reason: str, note: str) -> None:
    """Preset hybrid: a final connection or non-retryable failure moves the rest of the run to Claude.

    Prints and logs the kind=switch line once; every later status/plan routes to Claude sonnet.
    """
    if not hybrid_shared.switches_run(reason) or not _hybrid(ctx):
        return
    try:
        if hybrid_shared.switch_to_claude(ctx["out"], st["name"], st["tier"], st["spec"], reason, note):
            line = hybrid_shared.switch_line(SKILL, hybrid_shared.run_switched(ctx["out"]))
            print(line)
            sys.stdout.flush()
            hybrid_shared.log_line(ctx["out"] / ERRORS_FILE, line)
    except OSError:
        pass  # the failed unit still falls back to Claude; only the run-wide switch is lost


def _summary(name: str, tier: str, ok: bool, reason: str, written: int, total: int, rounds: int, secs: int) -> str:
    head = "OK" if ok else "FALLBACK ({})".format(reason)
    return "OC {} oc:{} {} {}/{} — {} rounds — {}s".format(name, tier or "none", head, written, total, rounds, secs)


def _finish(ctx: dict, st: dict, reason: str, note: str, started: float) -> dict:
    """Write the output file, the event file and the telemetry record; return the result dict."""
    name, role, tier = st["name"], st["role"], st["tier"]
    dropped, demoted, invalid = st["oracle"]["dropped"], st["oracle"]["demoted"], st["oracle"]["invalid_status"]
    if dropped or demoted or invalid:
        _emit(ctx, st, "WARN", "oracle", "oracle dropped {} and demoted {} rows, rejected {} rows with an invalid status"
              .format(dropped, demoted, invalid))
    if role == "parser":
        rows, ok, total = list(st["parser_rows"]), bool(st["parse_ok"]), 0
    else:
        rows = [st["rows"][i] for i in st["ids"] if i in st["rows"]]
        total = len(st["ids"])
        ok = bool(st["ids"]) and len(rows) == total
    reason = "" if ok else (reason or "format")
    note = "" if ok else note
    backend = "oc:" + tier
    out = ctx["out"]
    if rows and role in OUT_DIRS:
        body = "".join(json.dumps(dict(r, backend=backend), ensure_ascii=False) + "\n" for r in rows)
        atomic_write(out / OUT_DIRS[role] / (name + ".jsonl"), body)
    written = len(rows)
    secs = round(time.time() - started, 1)
    event = {"batch": name, "ok": ok, "agent_type": "opencode:ha-" + (role or "unknown"), "backend": backend,
             "reason": reason or None, "message": note, "rounds": st["rounds"], "written": written,
             "total": total, "t": time.time()}
    if role:
        atomic_write(out / "events" / (name + ".json"), json.dumps(event, indent=1) + "\n")
    outcome = "ok" if ok else ("partial" if written else "fallback")
    rec = {"t": _now_iso(), "kind": "run", "repo": str(ctx["repo"]), "name": name, "role": role, "tier": tier,
           "model": st["model"], "variant": st["variant"], "items": total, "rounds": st["rounds"],
           "round1_valid": st["round1_valid"], "oracle": dict(st["oracle"]), "outcome": outcome,
           "reason": reason, "duration_s": secs, "tokens": dict(st["tokens"])}
    try:
        record(rec)
    except Exception:
        pass
    return {"name": name, "role": role, "tier": tier, "backend": backend, "ok": ok, "reason": reason,
            "message": note, "rounds": st["rounds"], "written": written, "total": total,
            "outcome": outcome, "duration_s": secs, "tokens": dict(st["tokens"]),
            "line": _summary(name, tier, ok, reason, written, total, st["rounds"], int(round(secs)))}


def _fail_event(ctx: dict, st: dict, reason: str, note: str) -> None:
    """Best effort: a failed event so `status` harvests the unit instead of waiting for it forever."""
    if not st["role"]:
        return
    event = {"batch": st["name"], "ok": False, "agent_type": "opencode:ha-" + st["role"],
             "backend": "oc:" + st["tier"], "reason": reason, "message": note, "rounds": st["rounds"],
             "written": 0, "total": len(st["ids"]), "t": time.time()}
    try:
        atomic_write(ctx["out"] / "events" / (st["name"] + ".json"), json.dumps(event, indent=1) + "\n")
    except OSError:
        pass  # the OC line is already printed and the process exits non-zero


def run_named(cwd: str, name: str) -> dict:
    """Run one opencode batch/section end to end; print each OC line as it happens, then one summary line; never raise."""
    started = time.time()
    role = role_of(name)
    ctx, st, result = None, None, None
    reason, note, ran = "", "", False
    try:
        ctx = _context(cwd)
        st = _new_state(ctx, name, role)
        reason, note = _blocked(ctx, st)
        if not reason:
            reason, note = _turns(ctx, st)
            ran = True
    except Exception as exc:
        reason, note = "crash", "{}: {}".format(type(exc).__name__, _one_line(exc))
    _report_failure(ctx, st, name, reason, note)
    if ran and reason:
        _switch(ctx, st, reason, note)
    if ctx is not None and st is not None:
        try:
            result = _finish(ctx, st, reason, note, started)
        except Exception as exc:
            reason, note = "crash", "{}: {}".format(type(exc).__name__, _one_line(exc))
            _report_failure(ctx, st, name, reason, note)
            _fail_event(ctx, st, reason, note)
    if result is None:
        tier = st["tier"] if st else ""
        rounds = st["rounds"] if st else 0
        secs = round(time.time() - started, 1)
        result = {"name": name, "role": role, "tier": tier, "backend": "oc:" + tier, "ok": False,
                  "reason": reason or "crash", "message": note, "rounds": rounds, "written": 0, "total": 0,
                  "outcome": "fallback", "duration_s": secs, "tokens": {k: 0 for k in TOKEN_KEYS},
                  "line": _summary(name, tier, False, reason or "crash", 0, 0, rounds, int(round(secs)))}
    print(result["line"])
    sys.stdout.flush()
    return result
