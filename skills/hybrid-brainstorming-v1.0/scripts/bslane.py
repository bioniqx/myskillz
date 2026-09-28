#!/usr/bin/env python3
"""bslane: run one hybrid-brainstorming lane on opencode, or hand it to Claude."""
import argparse
import datetime
import fcntl
import json
import os
import re
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

SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULTS_PATH = SKILL_DIR / "routing.default.json"
LANE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
TOKEN_KEYS = ("input", "output", "reasoning", "cache_read", "cache_write")


def _pick(name):
    """Return the named attribute from whichever sibling module defines it."""
    for mod in (oc_run, hb_router, hb_ground, hb_prompts, hb_config, hb_doctor):
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


def lanes_dir(root: Path) -> Path:
    d = Path(root) / ".superpowers" / "brainstorm" / "lanes"
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
        fallbacks = [r for r in recs if r.get("outcome") == "fallback"]
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

    def fallback(reason, note, extra=None):
        rec["outcome"] = "fallback"
        rec["reason"] = reason
        record(root, rec)
        lines = ["FALLBACK {} ({}) — {}".format(a.id, reason, _one_line(note)), cline]
        return "\n".join(lines + list(extra or []))

    try:
        routing = load_routing(DEFAULTS_PATH, user_routing_path())
    except Exception as exc:
        return fallback("config", "routing unreadable: {}".format(exc))
    if ctx_error:
        return fallback("config", ctx_error)
    doctor = load_doctor(doctor_cache_path())
    dest = route(role, routing, doctor, a.backend or "", a.preset or "")
    if dest == "claude":
        record(root, rec)
        return cline
    tier = dest[3:] if dest.startswith("oc:") else dest
    rec["backend"] = "oc:" + tier
    rec["tier"] = tier
    tcfg = (routing.get("tiers") or {}).get(tier)
    if not isinstance(tcfg, dict) or not tcfg.get("model"):
        return fallback("config", "tier {} is not defined in routing".format(tier))
    rec["model"] = str(tcfg["model"])
    rec["variant"] = str(tcfg.get("variant", ""))
    if in_cooldown(lanes, tier, time.time()):
        return fallback("cooldown", "tier {} is cooling down after a throttle".format(tier))
    max_parallel = int(tcfg.get("max_parallel", 1))
    wait_s = float(routing.get("slot_wait_s", 60))
    slot = acquire_slot(lanes, tier, max_parallel, wait_s)
    if slot is None:
        return fallback("busy", "all {} slots of tier {} busy for {:.0f}s".format(max_parallel, tier, wait_s))
    prompt = render(True)
    try:
        cmd = build_cmd(os.environ.get("HB_OC_BIN", "opencode"), AGENT_NAME, rec["model"], rec["variant"], prompt)
        env = dict(os.environ, **config_env(role, prompt))
        env["PWD"] = str(root)
        res = run_once(cmd, root, env, lanes / "{}.jsonl".format(a.id), lanes / "{}.err".format(a.id),
                       int(tcfg.get("stall_s", 90)), int(tcfg.get("timeout_s", 300)))
    finally:
        release_slot(slot)
    rec["duration_s"] = round(float(res.get("duration") or 0.0), 1)
    usage = res.get("usage") or {}
    rec["tokens"] = {k: int(usage.get(k) or 0) for k in TOKEN_KEYS}
    errors = res.get("errors") or []
    reason = res.get("reason") or ""
    if not reason and (res.get("rc") != 0 or errors):
        reason = "crash"
    if reason:
        if reason == "throttle":
            start_cooldown(lanes, tier, int(routing.get("throttle_cooldown_s", 120)), time.time())
        note = res.get("note") or "; ".join(errors) or "opencode exited with {}".format(res.get("rc"))
        return fallback(reason, note)
    text = (res.get("text") or "").strip()
    marker = {"code": "FINDINGS", "web": "ANSWER"}.get(kind)
    if not text:
        return fallback("format", "empty final text")
    if marker and marker not in text:
        return fallback("format", "no {} section in the output".format(marker))
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
            return fallback("grounding", "grounded {}/{}".format(g["grounded"], g["total"]), unverified)
        head = "LANE {} {} oc:{} OK — grounded {}/{} — {}s".format(a.id, role, tier, g["grounded"], g["total"],
                                                                  secs)
        body = g["text"]
    out = "\n".join([head] + ([body] if body else []) + unverified)
    (lanes / "{}.out.md".format(a.id)).write_text(out + "\n", encoding="utf-8")
    rec["outcome"] = "ok"
    record(root, rec)
    return out


def _ensure_user_routing(user_path: Path) -> str:
    """Create the user routing file as a byte copy of the defaults if missing. Return a report line or ""."""
    user_path = Path(user_path)
    if user_path.exists():
        return ""
    user_path.parent.mkdir(parents=True, exist_ok=True)
    user_path.write_bytes(DEFAULTS_PATH.read_bytes())
    return "created user routing file: {}".format(user_path)


def _allow_rule_line() -> str:
    return 'settings allow rule for prompt-free background lanes: Bash(python3 "{}":*)'.format(
        SKILL_DIR / "scripts" / "bslane.py")


def _doctor_text(ping: bool, root: Path) -> str:
    user_path = user_routing_path()
    try:
        routing_note = _ensure_user_routing(user_path)
    except OSError as exc:
        routing_note = "routing file error ({}): {}".format(type(exc).__name__, _one_line(exc))
    try:
        routing = load_routing(DEFAULTS_PATH, user_path)
        doctor_workdir = lanes_dir(root) / "doctor"
        doctor_workdir.mkdir(parents=True, exist_ok=True)
        data = run_doctor(os.environ.get("HB_OC_BIN", "opencode"), routing, ping, doctor_workdir)
        write_doctor(doctor_cache_path(), data)
    except Exception as exc:
        lines = ["opencode: doctor failed ({}: {}) → preset claude".format(type(exc).__name__, _one_line(exc))]
        if routing_note:
            lines.append(routing_note)
        lines.append(_allow_rule_line())
        return "\n".join(lines)
    lines = [str(data.get("status_line") or "opencode: unavailable → preset claude (run bslane.py doctor)")]
    if routing_note:
        lines.append(routing_note)
    for name, t in sorted((data.get("tiers") or {}).items()):
        note = " — " + _one_line(t["note"]) if t.get("note") else ""
        lines.append("tier {}: {}#{} {}{}".format(name, t.get("model", ""), t.get("variant", ""),
                                                  "ok" if t.get("ok") else "FAIL", note))
    lines.append("websearch: {}".format("on" if data.get("websearch") else "off"))
    lines.append("cache: {}".format(doctor_cache_path()))
    lines.append(_allow_rule_line())
    return "\n".join(lines)


def _stats_text(root: Path) -> str:
    path = Path(root) / ".superpowers" / "brainstorm" / "lanes.jsonl"
    rows = lane_stats(path)
    if not rows:
        return "no lanes recorded in {}".format(path)
    lines = ["role       tier   lanes  fallback  reasons                  grounded  median_s  tokens in/out"]
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
        sp.add_argument("--preset", default="", choices=["claude", "hybrid", "max"])

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

    doctor = sub.add_parser("doctor", help="probe opencode and write the doctor cache")
    doctor.add_argument("--ping", action="store_true")
    sub.add_parser("stats", help="per role and tier lane statistics")
    return p


def main(argv: list) -> int:
    args = build_parser().parse_args(argv)
    root = Path.cwd().resolve()
    if args.cmd in ("code", "web", "draft"):
        try:
            out = run_lane(args.cmd, args, root)
        except Exception as exc:
            out = "FALLBACK {} (crash) — {}: {}".format(args.id, type(exc).__name__, _one_line(exc))
            path = root / ".superpowers" / "brainstorm" / "lanes" / "{}.claude.md".format(args.id)
            if path.exists():
                role = "draft" if args.cmd == "draft" else args.role
                out += "\n" + claude_line(args.id, role, path)
        print(out)
        return 0
    if args.cmd == "doctor":
        print(_doctor_text(args.ping, root))
        return 0
    print(_stats_text(root))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
