#!/usr/bin/env python3
"""ha_run: the oc-run engine.

Runs one investigator batch (batch-NN), verifier batch (batch-VNN) or parser section (section-NN) on
opencode. It sends round 1 with the attached opencode brief. When ids are missing or the JSON does not
parse, it runs repair turns in the same session. It then applies the evidence oracle and writes the
output file atomically. It also writes the event file, appends one telemetry record and prints one
summary line. It never writes state.json or the doctor cache and never raises.
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


def _tier_of(cfg: dict, role: str, backend: str) -> str:
    """The opencode tier of the unit: its stored oc:<tier> backend, else the routing of its role."""
    if backend.startswith("oc:"):
        return backend[3:]
    if backend == "claude":
        return ""
    routing = cfg.get("routing") or {}
    preset = str(cfg.get("preset") or routing.get("preset") or "hybrid")
    if preset == "claude":
        return ""
    value = (routing.get("roles") or {}).get(role, "claude")
    if preset == "max":
        value = (routing.get("max_roles") or {}).get(role, value)
    return "" if value == "claude" else str(value)


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
    tier = _tier_of(ctx["cfg"], role, backend) if role else ""
    tcfg = ((ctx["cfg"].get("routing") or {}).get("tiers") or {}).get(tier) or {}
    return {"name": name, "role": role, "tier": tier, "tcfg": dict(tcfg),
            "model": str(tcfg.get("model") or ""), "variant": str(tcfg.get("variant") or ""),
            "ids": ids, "rows": {}, "parser_rows": [], "parse_ok": False, "rounds": 0, "round1_valid": 0,
            "oracle": {k: 0 for k in ORACLE_KEYS}, "tokens": {k: 0 for k in TOKEN_KEYS}}


def _blocked(ctx: dict, st: dict) -> tuple:
    """(reason, message) that stops the unit before any spawn, else ('', '')."""
    name, role, tier = st["name"], st["role"], st["tier"]
    if not role:
        return "spawn", "unknown batch name {}".format(name)
    if role != "parser" and not st["ids"]:
        return "spawn", "no checklist ids for {} in state.json".format(name)
    if not tier or not st["model"]:
        return "spawn", "no opencode tier routed for {}".format(name)
    doctor = load_doctor(doctor_cache_path())
    tiers = doctor.get("tiers") if isinstance(doctor, dict) else None
    entry = tiers.get(tier) if isinstance(tiers, dict) else None
    down = entry.get("down") if isinstance(entry, dict) else None
    if down:
        why = down.get("reason") if isinstance(down, dict) else down
        return "down", "tier {} is marked down ({})".format(tier, why)
    until = float((ctx["state"].get("cooldown") or {}).get(tier) or 0)
    now = time.time()
    if now < until:
        return "cooldown", "tier {} cools down for {}s more".format(tier, int(until - now))
    brief = _brief_path(ctx, st)
    if not brief.is_file():
        return "spawn", "missing opencode brief {}".format(brief)
    return "", ""


def _add_stats(st: dict, stats) -> None:
    for k in ORACLE_KEYS:
        st["oracle"][k] += int((stats or {}).get(k) or 0)


def _absorb(st: dict, rows: list, errors: list, missing: list, repo: Path, rnd: int) -> None:
    """Run the oracle on one round's rows and keep rows that fill ids still missing."""
    role = st["role"]
    if role == "parser":
        if errors:
            return
        kept, stats = apply_oracle(rows, [], repo, role)
        _add_stats(st, stats)
        st["parser_rows"] = list(kept)
        st["parse_ok"] = True
        if rnd == 1:
            st["round1_valid"] = len(kept)
        return
    # rows for ids filled in an earlier round are discarded, so keep them out of the oracle stats
    fresh = [r for r in rows if str(r.get("id", "")).strip() not in st["rows"]]
    kept, stats = apply_oracle(fresh, list(st["ids"]), repo, role)
    _add_stats(st, stats)
    for row in kept:
        rid = str(row.get("id"))
        if rid in missing and rid not in st["rows"]:
            st["rows"][rid] = row
    if rnd == 1:
        st["round1_valid"] = len(st["rows"])


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
        cmd = build_cmd(binary, AGENT_NAMES[role], st["model"], st["variant"], message, session, attach)
        res = run_once(cmd, repo, env, folder / "{}.{}.jsonl".format(name, rnd),
                       folder / "{}.{}.err".format(name, rnd),
                       int(tcfg.get("stall_s", 180)), int(tcfg.get("timeout_s", 900)))
        st["rounds"] = rnd
        usage = res.get("usage") or {}
        for k in TOKEN_KEYS:
            st["tokens"][k] += int(usage.get(k) or 0)
        session = str(res.get("session") or session)
        block = split_block(str(res.get("text") or ""), name)
        rows, errors = parse_block(block)
        if not rows and not errors:
            errors = ["no JSON rows between '@@@ BEGIN {0}' and '@@@ END {0}' in your reply".format(name)]
        _absorb(st, rows, errors, list(missing), repo, rnd)
        missing = [i for i in ids if i not in st["rows"]]
        if (st["parse_ok"] if role == "parser" else not missing):
            return "", ""
        run_errors = [str(e) for e in (res.get("errors") or [])]
        reason = str(res.get("reason") or "")
        if not reason and (res.get("rc") != 0 or run_errors):
            reason = "crash"
        if reason:
            return reason, _one_line(res.get("note") or "; ".join(run_errors)
                                     or "opencode exited with {}".format(res.get("rc")))
        if not session:
            break
    if role == "parser":
        note = "; ".join(errors[:3]) or "no parsable block"
    else:
        note = "ids still missing after {} rounds: {}".format(st["rounds"], ", ".join(missing))
    return "format", _one_line(note)


def _summary(name: str, tier: str, ok: bool, reason: str, written: int, total: int, rounds: int, secs: int) -> str:
    head = "OK" if ok else "FALLBACK ({})".format(reason)
    return "OC {} oc:{} {} {}/{} — {} rounds — {}s".format(name, tier or "none", head, written, total, rounds, secs)


def _finish(ctx: dict, st: dict, reason: str, note: str, started: float) -> dict:
    """Write the output file, the event file and the telemetry record; return the result dict."""
    name, role, tier = st["name"], st["role"], st["tier"]
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


def run_named(cwd: str, name: str) -> dict:
    """Run one opencode batch/section end to end; print exactly one summary line; never raise."""
    started = time.time()
    role = role_of(name)
    ctx, st, result = None, None, None
    reason, note = "", ""
    try:
        ctx = _context(cwd)
        st = _new_state(ctx, name, role)
        reason, note = _blocked(ctx, st)
        if not reason:
            reason, note = _turns(ctx, st)
    except Exception as exc:
        reason, note = "crash", "{}: {}".format(type(exc).__name__, _one_line(exc))
    if ctx is not None and st is not None:
        try:
            result = _finish(ctx, st, reason, note, started)
        except Exception as exc:
            reason, note = "crash", "{}: {}".format(type(exc).__name__, _one_line(exc))
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
