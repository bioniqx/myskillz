#!/usr/bin/env python3
"""bslane: run one hybrid-brainstorming lane on opencode, or hand it to Claude."""
import argparse
import datetime
import fcntl
import json
import os
import re
import shutil
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oc_run  # noqa: E402
import hb_router  # noqa: E402
import hb_ground  # noqa: E402
import hb_prompts  # noqa: E402
import hb_config  # noqa: E402
import hb_doctor  # noqa: E402
import hybrid_shared  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULTS_PATH = SKILL_DIR / "routing.default.json"
LANE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
TOKEN_KEYS = ("input", "output", "reasoning", "cache_read", "cache_write")
TOOL_NAME = "hybrid-brainstorming"
OC_LOG_NAME = "oc-errors.jsonl"
NON_RETRYABLE = ("auth", "quota", "model", "config")
PRESETS = ("claude", "hybrid", "opencode")
SENTINEL = "HB-LANE-OK"
DOCTOR_LOCK_WAIT_S = 600


def _pick(name):
    """Return the named attribute from whichever sibling module defines it."""
    for mod in (oc_run, hb_router, hb_ground, hb_prompts, hb_config, hb_doctor, hybrid_shared):
        value = getattr(mod, name, None)
        if value is not None:
            return value
    raise AttributeError("no sibling module defines {}".format(name))


build_cmd = _pick("build_cmd")
run_once = _pick("run_once")
user_routing_path = _pick("user_routing_path")
load_routing = _pick("load_routing")
route = _pick("route")
in_cooldown = _pick("in_cooldown")
start_cooldown = _pick("start_cooldown")
ground_code = _pick("ground_code")
ground_web = _pick("ground_web")
code_prompt = _pick("code_prompt")
web_prompt = _pick("web_prompt")
draft_prompt = _pick("draft_prompt")
claude_line = _pick("claude_line")
AGENT_NAME = _pick("AGENT_NAME")
config_env = _pick("config_env")
doctor_cache_path = _pick("doctor_cache_path")
load_doctor = _pick("load_doctor")
write_doctor = _pick("write_doctor")
run_doctor = _pick("run_doctor")
status_line = _pick("status_line")


def lanes_dir(root: Path) -> Path:
    d = Path(root) / ".hybrid-brainstorm" / "brainstorm" / "lanes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def acquire_slot(lanes: Path, tier: str, max_parallel: int, wait_s: float):
    """Take one of max_parallel non-blocking flock slots for tier; poll until wait_s. None when all busy."""
    slots = Path(lanes) / "slots"
    slots.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(0.0, float(wait_s))
    while True:
        for k in range(max(1, int(max_parallel))):
            fh = open(slots / "{}.{}.lock".format(tier, k), "a+")
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                fh.close()
                continue
            return fh
        if time.monotonic() >= deadline:
            return None
        time.sleep(0.2)


def release_slot(fh) -> None:
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    finally:
        fh.close()


def acquire_slots(lanes: Path, tier: str, max_parallel: int, pool: int, wait_s: float):
    """Hold one tier slot AND one slot of the shared cross-tier pool, taken in that fixed order.

    Returns (handles, busy): handles are the held slots ([] when busy); busy names what was full ("" or the tier or "pool").
    wait_s is one budget for both waits.
    """
    deadline = time.monotonic() + max(0.0, float(wait_s))
    tier_fh = acquire_slot(lanes, tier, max_parallel, wait_s)
    if tier_fh is None:
        return [], tier
    pool_fh = acquire_slot(lanes, "pool", pool, max(0.0, deadline - time.monotonic()))
    if pool_fh is None:
        release_slot(tier_fh)
        return [], "pool"
    return [tier_fh, pool_fh], ""


def release_slots(handles) -> None:
    for fh in reversed(handles):
        release_slot(fh)


def record(root: Path, rec: dict) -> None:
    path = lanes_dir(root).parent / "lanes.jsonl"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def lane_stats(path: Path) -> list:
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    groups = {}
    for line in lines:
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        key = (str(rec.get("role", "")), str(rec.get("tier") or "claude"))
        groups.setdefault(key, []).append(rec)
    out = []
    for key in sorted(groups):
        recs = groups[key]
        fallbacks = [r for r in recs if r.get("outcome") in ("fallback", "held")]
        reasons = {}
        for r in fallbacks:
            reason = str(r.get("reason") or "unknown")
            reasons[reason] = reasons.get(reason, 0) + 1
        gated = [r for r in recs if int(r.get("total") or 0) > 0]
        passed = [r for r in gated if r.get("outcome") == "ok"]
        durations = [float(r.get("duration_s") or 0.0) for r in recs if r.get("outcome") != "claude"]
        tokens = {k: 0 for k in TOKEN_KEYS}
        for r in recs:
            used = r.get("tokens") or {}
            for k in TOKEN_KEYS:
                tokens[k] += int(used.get(k) or 0)
        out.append({
            "role": key[0],
            "tier": key[1],
            "lanes": len(recs),
            "fallbacks": len(fallbacks),
            "fallback_rate": round(len(fallbacks) / len(recs), 3),
            "reasons": reasons,
            "grounding_pass_rate": round(len(passed) / len(gated), 3) if gated else None,
            "median_s": round(statistics.median(durations), 1) if durations else None,
            "tokens": tokens,
        })
    return out


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _one_line(text) -> str:
    return " ".join(str(text).split())[:300]


def _gate(g: dict) -> dict:
    """Normalise a grounding result into ok, grounded, total, kept text and unverified lines."""
    grounded = g.get("grounded", g.get("n", 0))
    kept = g.get("kept", g.get("lines"))
    if isinstance(grounded, list):
        kept = grounded if kept is None else kept
        grounded = len(grounded)
    unverified = g.get("unverified") or []
    if isinstance(unverified, str):
        unverified = [line for line in unverified.splitlines() if line.strip()]
    total = g.get("total", g.get("m"))
    if total is None:
        total = int(grounded) + len(unverified)
    ok = g.get("ok", g.get("passed", g.get("pass")))
    if ok is None:
        ok = int(total) > 0 and not unverified
    text = g.get("text", g.get("result"))
    if not isinstance(text, str):
        text = kept if isinstance(kept, str) else "\n".join(str(x) for x in (kept or []))
    return {"ok": bool(ok), "grounded": int(grounded), "total": int(total), "text": text.strip(),
            "unverified": [str(u) for u in unverified]}


def _unverified_lines(lines: list) -> list:
    return [u if u.startswith("UNVERIFIED") else "UNVERIFIED: " + u for u in lines]


def _tier_spec(routing: dict, tier: str) -> str:
    tcfg = (routing.get("tiers") or {}).get(tier)
    if isinstance(tcfg, dict) and tcfg.get("model"):
        return hybrid_shared.model_spec(tcfg)
    return ""


def _role_tier(routing: dict, role: str, preset: str) -> str:
    tier = (routing.get("roles") or {}).get(role, "claude")
    if preset == "opencode":
        tier = (routing.get("max_roles") or {}).get(role, tier)
    return tier


def _want_tier(routing: dict, role: str, preset: str, backend: str) -> str:
    """The opencode tier this lane should run on; "" when Claude serves it by design."""
    if backend == "claude" or preset == "claude":
        return ""
    if backend.startswith("oc:"):
        return backend[3:]
    tier = _role_tier(routing, role, preset)
    tcfg = (routing.get("tiers") or {}).get(tier)
    if tier == "claude" or (preset != "opencode" and isinstance(tcfg, dict) and tcfg.get("disabled")):
        return ""  # pinned to Claude, or a tier the user turned off: hybrid quietly uses Claude
    return tier


def _checked(doctor: dict, routing: dict, tier: str) -> bool:
    tcfg = (routing.get("tiers") or {}).get(tier)
    return isinstance(tcfg, dict) and hybrid_shared.cache_fresh((doctor.get("tiers") or {}).get(tier), tcfg,
                                                                 time.time())


def _ensure_doctor(routing: dict, lanes: Path, tier: str, preset: str) -> tuple:
    """Load the doctor cache; refresh it with a ping, once, under a lock, when tier's entry is missing or stale.

    Returns (doctor, error); error is "" unless the refresh itself failed. A tier that cannot be checked
    (unknown, no model, disabled, open breaker) triggers no refresh: the caller reports it as it is.
    """
    doctor = load_doctor(doctor_cache_path()) or {}
    tcfg = (routing.get("tiers") or {}).get(tier)
    if (not isinstance(tcfg, dict) or not tcfg.get("model") or tcfg.get("disabled") or _checked(doctor, routing, tier)
            or hybrid_shared.breaker_open(lanes, tier, hybrid_shared.model_spec(tcfg))):
        return doctor, ""
    lock = acquire_slot(lanes, "doctor", 1, DOCTOR_LOCK_WAIT_S)
    if lock is None:
        return doctor, "no fresh doctor check: another lane's refresh took over {}s".format(DOCTOR_LOCK_WAIT_S)
    try:
        doctor = load_doctor(doctor_cache_path()) or {}  # another lane may have refreshed while this one waited
        if _checked(doctor, routing, tier):
            return doctor, ""
        workdir = lanes / "doctor"
        workdir.mkdir(parents=True, exist_ok=True)
        try:
            data = run_doctor(os.environ.get("HYBRID_BRAINSTORMING_OC_BIN", "opencode"), routing, True, workdir, doctor,
                              preset == "opencode")
            write_doctor(doctor_cache_path(), data)
        except Exception as exc:
            return doctor, "doctor refresh failed ({}: {})".format(type(exc).__name__, _one_line(exc))
        return data, ""
    finally:
        release_slot(lock)


def _why_unserved(routing: dict, doctor: dict, lanes: Path, tier: str, role: str, refresh_err: str) -> tuple:
    """(kind, detail) for the OC line of a lane the router could not send to its tier."""
    tcfg = (routing.get("tiers") or {}).get(tier)
    if not isinstance(tcfg, dict):
        return "config", "tier {} does not exist in the routing".format(tier)
    if tcfg.get("disabled"):
        return "config", "tier {} is disabled in the routing file".format(tier)
    spec = hybrid_shared.model_spec(tcfg)
    if not spec:
        return "config", "tier {} has no model in the per-skill routing file or the shared opencode config".format(tier)
    tripped = hybrid_shared.breaker_open(lanes, tier, spec)
    if tripped:
        return "breaker", "tier {} was tripped earlier in this run by kind={}: {}".format(
            tier, tripped.get("kind"), tripped.get("detail"))
    if refresh_err:
        return "config", refresh_err
    entry = (doctor.get("tiers") or {}).get(tier)
    if not hybrid_shared.cache_fresh(entry, tcfg, time.time()):
        return "config", "tier {} has no fresh doctor check; run bslane.py doctor --ping".format(tier)
    if not entry.get("ok"):
        return entry.get("kind") or "crash", entry.get("detail") or "the doctor check for tier {} failed".format(tier)
    if not doctor.get("ok"):
        return ("config" if doctor.get("version") else "spawn"), (
            "opencode is not usable (no working version or model list); run bslane.py doctor")
    if role == "research" and not doctor.get("websearch"):
        return "config", ("web search is off for tier {}; allow it once in the opencode TUI, "
                          "then run bslane.py doctor --ping").format(tier)
    return "config", "tier {} is unavailable".format(tier)


def _clear_tier(lanes: Path, tier: str, spec: str) -> bool:
    """Forget a tier's open breaker (and its skip count) and throttle cooldown; True when any existed."""
    breaker = hybrid_shared._breaker_file(lanes, tier, spec)
    cleared = False
    for path in (breaker, breaker.with_suffix(".skip"), Path(lanes) / ("cooldown-" + tier)):
        try:
            path.unlink()
            cleared = True
        except FileNotFoundError:
            pass
    return cleared


def _strip_sentinel(text: str) -> str:
    lines = [line.replace(SENTINEL, "").rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def _log_path(lanes: Path, lane_id: str) -> str:
    for suffix in (".err", ".jsonl"):
        path = Path(lanes) / (lane_id + suffix)
        try:
            if path.stat().st_size:
                return str(path)
        except OSError:
            continue
    return ""


def _config_lines(routing, unit: str) -> list:
    if not routing:
        return []
    lines = []
    for problem in routing.get("config_problems") or []:
        lines.append(hybrid_shared.oc_line("ERROR", TOOL_NAME, unit, "", "", "config", problem))
    for warning in routing.get("config_warnings") or []:
        lines.append(hybrid_shared.oc_line("WARN", TOOL_NAME, unit, "", "", "config", warning))
    return lines


def _exit_code(out: str) -> int:
    for line in out.splitlines():
        if not line.startswith("OC-"):
            return 3 if line.startswith(("FALLBACK ", "HELD ")) else 0
    return 0


def run_lane(kind: str, a, root: Path) -> str:
    root = Path(root).resolve()
    lanes = lanes_dir(root)
    role = "draft" if kind == "draft" else a.role
    today = datetime.date.today().isoformat()
    context_text, ctx_error = "", ""
    if kind == "draft":
        try:
            context_text = Path(a.context_file).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            ctx_error = "cannot read context file {}: {}".format(a.context_file, exc.strerror or exc)

    def render(for_opencode):
        if kind == "code":
            return code_prompt(a.task, str(root), today, a.slice, a.siblings, a.question, for_opencode)
        if kind == "web":
            return web_prompt(role, a.task, today, a.stack, a.angle, a.siblings, a.question, for_opencode)
        return draft_prompt(a.lens, a.task, context_text, for_opencode)

    claude_path = lanes / "{}.claude.md".format(a.id)
    claude_path.write_text(render(False), encoding="utf-8")
    cline = claude_line(a.id, role, claude_path)
    rec = {"t": _now_iso(), "id": a.id, "role": role, "backend": "claude", "tier": "", "model": "",
           "variant": "", "outcome": "claude", "reason": "", "grounded": 0, "total": 0, "duration_s": 0.0,
           "tokens": {k: 0 for k in TOKEN_KEYS}}
    notes = []
    preset = ""

    def oc(level, tier, model, okind, detail):
        line = hybrid_shared.oc_line(level, TOOL_NAME, a.id, tier, model, okind, detail, _log_path(lanes, a.id))
        hybrid_shared.log_line(lanes / OC_LOG_NAME, line)
        notes.append(line)

    def finish(lines):
        return "\n".join(notes + lines)

    def fallback(reason, note, extra=None, model=""):
        rec["outcome"] = "fallback"
        rec["reason"] = reason
        record(root, rec)
        lines = ["FALLBACK {} ({}) — {}".format(a.id, reason, _one_line(note)),
                 claude_line(a.id, role, claude_path, model) if model else cline]
        return finish(lines + list(extra or []))

    def hold(reason, note, extra=None):
        rec["outcome"] = "held"
        rec["reason"] = reason
        record(root, rec)
        lines = ["HELD {} ({}) — {}".format(a.id, reason, _one_line(note))]
        return finish(lines + list(extra or []))

    def fail(reason, note, extra=None):
        if preset == "opencode":
            return hold(reason, note, extra)
        return fallback(reason, note, extra)

    if a.preset:
        try:
            preset, preset_note = hybrid_shared.mode_to_preset(a.preset)
        except ValueError as exc:
            preset, preset_note = "", str(exc)
        if preset not in PRESETS:
            detail = preset_note or "unknown preset {}".format(a.preset)
            oc("ERROR", "", "", "config", detail)
            return hold("config", detail)
        if preset_note:
            oc("WARN", "", "", "config", preset_note)
    try:
        routing = load_routing(DEFAULTS_PATH, user_routing_path())
    except Exception as exc:
        detail = "routing unreadable: {}".format(_one_line(exc))
        if preset != "claude":
            oc("ERROR", "", "", "config", detail)
        return fail("config", detail)
    preset = preset or hybrid_shared.mode_to_preset(str(routing.get("preset") or "hybrid"))[0] or "hybrid"
    a.resolved_preset = preset  # main() needs it if something below crashes

    def switched():
        """The run left opencode: spawn nothing and print no OC line."""
        rec.update(reason="switched", backend="claude", tier="", model="", variant="")
        record(root, rec)
        return finish([claude_line(a.id, role, claude_path, hybrid_shared.FALLBACK_MODEL)])

    if (preset == "hybrid" and not ctx_error and hybrid_shared.run_switched(lanes)
            and (a.backend.startswith("oc:") or (not a.backend and _role_tier(routing, role, preset) != "claude"))):
        return switched()
    if preset != "claude":
        for line in _config_lines(routing, a.id):
            hybrid_shared.log_line(lanes / OC_LOG_NAME, line)
            notes.append(line)
        if routing.get("config_problems"):
            return fail("config", routing["config_problems"][0])
    if ctx_error:
        if preset != "claude":
            oc("ERROR", "", "", "config", ctx_error)
        return fail("config", ctx_error)
    want = _want_tier(routing, role, preset, a.backend)
    if not want:  # Claude serves this lane by design: no doctor, no OC line
        record(root, rec)
        return finish([cline])
    doctor, refresh_err = _ensure_doctor(routing, lanes, want, preset)
    dest = route(role, routing, doctor, a.backend or "", preset, time.time(), lanes)
    if dest in ("claude", "held"):  # the tier the lane needs cannot serve it
        want_spec = _tier_spec(routing, want)
        rec["backend"] = "oc:" + want
        rec["tier"] = want
        okind, detail = _why_unserved(routing, doctor, lanes, want, role, refresh_err)
        if okind == "breaker":  # the trip printed the root cause; stats prints one summary of the skipped lanes
            skipped = hybrid_shared.breaker_skip(lanes, want, want_spec)
            detail = "{}; {} lanes skipped so far".format(detail, skipped)
        else:
            oc("ERROR", want, want_spec, okind, detail)
        return fail(okind, detail)
    tier = dest[3:] if dest.startswith("oc:") else dest
    rec["backend"] = "oc:" + tier
    rec["tier"] = tier
    tcfg = (routing.get("tiers") or {}).get(tier)
    spec = _tier_spec(routing, tier)
    if not spec:
        detail = "tier {} has no model in the per-skill routing file or the shared opencode config".format(tier)
        oc("ERROR", tier, "", "config", detail)
        return fail("config", detail)
    rec["model"] = str(tcfg["model"])
    rec["variant"] = str(tcfg.get("variant", ""))
    if in_cooldown(lanes, tier, time.time()):
        msg = "tier {} is cooling down after a throttle".format(tier)
        oc("ERROR", tier, spec, "throttle", msg)
        return fail("cooldown", msg)
    max_parallel = int(tcfg.get("max_parallel", 1))
    wait_s = float(routing.get("slot_wait_s", 60))
    pool, pool_problem = hybrid_shared.pool_from_env()
    if pool is None:
        oc("ERROR", tier, spec, "config", pool_problem)
        return fail("config", pool_problem)
    slot, busy = acquire_slots(lanes, tier, max_parallel, pool, wait_s)
    if not slot:
        msg = ("all {} slots of tier {} busy for {:.0f}s".format(max_parallel, tier, wait_s) if busy == tier else
               "all {} shared opencode pool slots busy for {:.0f}s".format(pool, wait_s))
        oc("ERROR", tier, spec, "timeout", msg)
        return fail("busy", msg)
    # The wait may have been long: another lane can have switched the run, tripped the breaker or been throttled.
    if preset == "hybrid" and hybrid_shared.run_switched(lanes):
        release_slots(slot)
        return switched()
    if hybrid_shared.breaker_open(lanes, tier, spec):
        release_slots(slot)
        skipped = hybrid_shared.breaker_skip(lanes, tier, spec)
        return fail("breaker", "tier {} was tripped while this lane waited for a slot; {} lanes skipped so far"
                    .format(tier, skipped))
    if in_cooldown(lanes, tier, time.time()):
        release_slots(slot)
        msg = "tier {} started cooling down while this lane waited for a slot".format(tier)
        oc("ERROR", tier, spec, "throttle", msg)
        return fail("cooldown", msg)
    prompt = render(True)
    retries = 0
    try:
        cmd = build_cmd(os.environ.get("HYBRID_BRAINSTORMING_OC_BIN", "opencode"), AGENT_NAME, rec["model"], rec["variant"], prompt)
        env = dict(os.environ, **config_env(role, prompt))
        env["PWD"] = str(root)
        while True:  # connection failures retry as fresh runs; the slots stay held (a throttled provider gets less load)
            res = run_once(cmd, root, env, lanes / "{}.jsonl".format(a.id), lanes / "{}.err".format(a.id),
                           int(tcfg.get("stall_s", 90)), int(tcfg.get("timeout_s", 300)))
            reason = res.get("reason") or ""
            detail = res.get("detail") or res.get("note") or "opencode exited with {}".format(res.get("rc"))
            if not hybrid_shared.should_retry(reason, retries):
                break
            delay = hybrid_shared.retry_delay(retries)
            retries += 1
            oc("WARN", tier, spec, reason, "retry {}/{} in {}s: {}".format(retries, hybrid_shared.OC_RETRIES, delay,
                                                                          detail))
            time.sleep(delay)
            if preset == "hybrid" and hybrid_shared.run_switched(lanes):
                break  # another lane already moved the run to Claude: stop spawning
    finally:
        release_slots(slot)
    rec["duration_s"] = round(float(res.get("duration") or 0.0), 1)
    usage = res.get("usage") or {}
    rec["tokens"] = {k: int(usage.get(k) or 0) for k in TOKEN_KEYS}
    if reason == "recovered":
        oc("WARN", tier, spec, "recovered", detail)
    elif reason:
        if reason == "throttle":
            start_cooldown(lanes, tier, int(routing.get("throttle_cooldown_s", 120)), time.time())
        if reason in NON_RETRYABLE:
            hybrid_shared.breaker_trip(lanes, tier, spec, reason, detail)
        oc("ERROR", tier, spec, reason, detail)
        if preset == "hybrid" and hybrid_shared.switches_run(reason):
            if hybrid_shared.switch_to_claude(lanes, a.id, tier, spec, reason, detail):
                line = hybrid_shared.switch_line(TOOL_NAME, hybrid_shared.run_switched(lanes))
                hybrid_shared.log_line(lanes / OC_LOG_NAME, line)
                notes.append(line)
            return fallback(reason, res.get("note") or detail, model=hybrid_shared.FALLBACK_MODEL)
        return fail(reason, res.get("note") or detail)
    text = (res.get("text") or "").strip()
    if kind == "draft":
        text = _strip_sentinel(text)
    marker = {"code": "FINDINGS", "web": "ANSWER"}.get(kind)
    if not text:
        oc("WARN", tier, spec, "empty", "opencode finished without any answer text")
        return fail("empty", "empty final text")
    if marker and marker not in text:
        msg = "no {} section in the output".format(marker)
        oc("WARN", tier, spec, "format", msg)
        return fail("format", msg)
    secs = int(round(rec["duration_s"]))
    if kind == "draft":
        head = "LANE {} draft oc:{} OK — ungrounded — {}s".format(a.id, tier, secs)
        body = text
        unverified = []
    else:
        raw = ground_code(text, root) if kind == "code" else ground_web(text, res.get("tools") or [])
        g = _gate(raw)
        rec["grounded"] = g["grounded"]
        rec["total"] = g["total"]
        unverified = _unverified_lines(g["unverified"])
        if not g["ok"]:
            msg = "grounded {}/{}".format(g["grounded"], g["total"])
            oc("WARN", tier, spec, "grounding", msg)
            return fail("grounding", msg, unverified)
        head = "LANE {} {} oc:{} OK — grounded {}/{} — {}s".format(a.id, role, tier, g["grounded"], g["total"],
                                                                  secs)
        body = g["text"]
    out = "\n".join([head] + ([body] if body else []) + unverified)
    (lanes / "{}.out.md".format(a.id)).write_text(out + "\n", encoding="utf-8")
    rec["outcome"] = "ok"
    record(root, rec)
    return finish([out])


def _init_text(root: Path) -> str:
    """Start a run: forget the previous run's switch to Claude, circuit breakers and cooldowns (lanes/ is per project)."""
    lanes = lanes_dir(root)
    try:
        (lanes / hybrid_shared.SWITCH_FILE).unlink()
    except FileNotFoundError:
        pass
    shutil.rmtree(str(lanes / hybrid_shared.BREAKER_DIR), ignore_errors=True)
    for path in lanes.glob("cooldown-*"):
        path.unlink()
    return "run state reset: opencode switch, breakers and cooldowns cleared in {}".format(lanes)


def _allow_rule_line() -> str:
    return 'settings allow rule for prompt-free background lanes: Bash(python3 "{}":*)'.format(
        SKILL_DIR / "scripts" / "bslane.py")


def _doctor_text(ping: bool, root: Path) -> str:
    routing = None
    lanes = lanes_dir(root)
    try:
        routing = load_routing(DEFAULTS_PATH, user_routing_path())
        doctor_workdir = lanes / "doctor"
        doctor_workdir.mkdir(parents=True, exist_ok=True)
        data = run_doctor(os.environ.get("HYBRID_BRAINSTORMING_OC_BIN", "opencode"), routing, ping, doctor_workdir,
                          load_doctor(doctor_cache_path()))
        write_doctor(doctor_cache_path(), data)
    except Exception as exc:
        detail = "doctor failed ({}: {})".format(type(exc).__name__, _one_line(exc))
        lines = [hybrid_shared.oc_line("ERROR", TOOL_NAME, "doctor", "", "", "config", detail)]
        lines += _config_lines(routing, "doctor")
        lines.append(_allow_rule_line())
        return "\n".join(lines)
    lines = [status_line(routing, data, time.time())]
    lines += _config_lines(routing, "doctor")
    for name, entry in sorted((data.get("tiers") or {}).items()):
        spec = _tier_spec(routing, name) or name
        source = (routing.get("model_sources") or {}).get(name, "shared")
        if entry.get("ok"):
            lines.append("tier {}: {} ({}) ok".format(name, spec, source))
            if ping and _clear_tier(lanes, name, spec):  # a live ping is the answer to "retry on opencode"
                lines.append("tier {}: breaker and cooldown cleared".format(name))
        else:
            lines.append(hybrid_shared.oc_line("ERROR", TOOL_NAME, "doctor", name, spec,
                                               entry.get("kind") or "crash",
                                               entry.get("detail") or "tier check failed"))
    lines.append("websearch: {}".format("on" if data.get("websearch") else "off"))
    lines.append("cache: {}".format(doctor_cache_path()))
    lines.append(_allow_rule_line())
    return "\n".join(lines)


def _stats_text(root: Path) -> str:
    base = Path(root) / ".hybrid-brainstorm" / "brainstorm"
    path = base / "lanes.jsonl"
    alerts = hybrid_shared.breaker_summary(base / "lanes", TOOL_NAME)  # one OC-ERROR per tripped root cause
    for line in alerts:
        hybrid_shared.log_line(base / "lanes" / OC_LOG_NAME, line)
    rows = lane_stats(path)
    if not rows:
        return "\n".join(alerts + ["no lanes recorded in {}".format(path)])
    lines = alerts + ["role       tier   lanes  fallback  reasons                  grounded  median_s  tokens in/out"]
    for r in rows:
        reasons = ",".join("{}:{}".format(k, v) for k, v in sorted(r["reasons"].items())) or "-"
        gp = "-" if r["grounding_pass_rate"] is None else "{:.0f}%".format(100 * r["grounding_pass_rate"])
        med = "-" if r["median_s"] is None else "{:.1f}".format(r["median_s"])
        lines.append("{:<10} {:<6} {:>5}  {:>7.0f}%  {:<24} {:>8}  {:>8}  {}/{}".format(
            r["role"], r["tier"], r["lanes"], 100 * r["fallback_rate"], reasons, gp, med,
            r["tokens"]["input"], r["tokens"]["output"]))
    return "\n".join(lines)


def _lane_id(value):
    if not LANE_ID_RE.match(value):
        raise argparse.ArgumentTypeError("lane id must match [A-Za-z0-9_-]{1,40}")
    return value


def _backend(value):
    if value in ("", "claude") or (value.startswith("oc:") and len(value) > 3):
        return value
    raise argparse.ArgumentTypeError("backend must be claude or oc:<tier>")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="bslane.py", description="Run one hybrid-brainstorming lane.")
    sub = p.add_subparsers(dest="cmd")
    sub.required = True

    def lane_common(sp):
        sp.add_argument("--id", required=True, type=_lane_id)
        sp.add_argument("--task", default="")
        sp.add_argument("--backend", default="", type=_backend)
        sp.add_argument("--preset", default="")

    code = sub.add_parser("code", help="code lookup lane")
    lane_common(code)
    code.add_argument("--role", required=True, choices=["locate", "explore"])
    code.add_argument("--slice", default="")
    code.add_argument("--siblings", default="")
    code.add_argument("--question", default="")

    web = sub.add_parser("web", help="web lane")
    lane_common(web)
    web.add_argument("--role", required=True, choices=["fact", "research"])
    web.add_argument("--stack", default="")
    web.add_argument("--angle", default="")
    web.add_argument("--siblings", default="")
    web.add_argument("--question", default="")

    draft = sub.add_parser("draft", help="approach draft lane")
    lane_common(draft)
    draft.add_argument("--lens", required=True, choices=["reuse", "best-practice", "smallest", "runner-up"])
    draft.add_argument("--context-file", required=True)

    doctor = sub.add_parser("doctor", help="probe opencode and write the doctor cache; --ping clears breakers")
    doctor.add_argument("--ping", action="store_true")
    doctor.add_argument("--preset", default="")  # accepted and ignored: SKILL.md passes it on every call
    stats = sub.add_parser("stats", help="per role and tier lane statistics, then breaker summaries")
    stats.add_argument("--preset", default="")
    init = sub.add_parser("init", help="start a run: clear the previous run's switch, breakers and cooldowns")
    init.add_argument("--preset", default="")
    return p


def main(argv: list) -> int:
    args = build_parser().parse_args(argv)
    root = Path.cwd().resolve()
    if args.cmd in ("code", "web", "draft"):
        try:
            out = run_lane(args.cmd, args, root)
        except Exception as exc:
            detail = "{}: {}".format(type(exc).__name__, _one_line(exc))
            line = hybrid_shared.oc_line("ERROR", TOOL_NAME, args.id, "", "", "crash", detail)
            lanes = root / ".hybrid-brainstorm" / "brainstorm" / "lanes"
            hybrid_shared.log_line(lanes / OC_LOG_NAME, line)
            preset = getattr(args, "resolved_preset", "") or (
                hybrid_shared.mode_to_preset(args.preset)[0] if args.preset else "")
            if preset == "opencode":  # mode opencode never falls back on its own
                out = "\n".join([line, "HELD {} (crash) — {}".format(args.id, detail)])
            else:
                out = "\n".join([line, "FALLBACK {} (crash) — {}".format(args.id, detail)])
                path = lanes / "{}.claude.md".format(args.id)
                if path.exists():
                    role = "draft" if args.cmd == "draft" else args.role
                    out += "\n" + claude_line(args.id, role, path)
        print(out)
        return _exit_code(out)
    if args.cmd == "doctor":
        print(_doctor_text(args.ping, root))
        return 0
    if args.cmd == "init":
        print(_init_text(root))
        return 0
    print(_stats_text(root))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
