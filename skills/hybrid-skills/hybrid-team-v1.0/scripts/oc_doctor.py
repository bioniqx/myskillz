"""Doctor checks, tier ping and lane statistics for the opencode backend."""
import json
import os
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from oc_lane import build_cmd, run_once
from oc_config import config_env, SENTINEL
from hybrid_shared import cache_key, classify, first_error, model_spec, oc_line, run_models

PING = "PING"
MODELS_TIMEOUT_S = 60
LINE_SOURCE = "hybrid-team"
EMPTY_MODELS = "opencode models listed nothing"
WARN_KINDS = ("recovered", "empty", "format", "grounding", "lint", "oracle", "gate")
STDERR_TAIL_CHARS = 2000


def _level(kind: str) -> str:
    """OC line level for a failure kind."""
    return "OC-WARN" if kind in WARN_KINDS else "OC-ERROR"


def _spec(tier) -> str:
    """Model spec for OC lines; '-' when the tier has no model."""
    if isinstance(tier, dict) and tier.get("model"):
        return model_spec(tier)
    return "-"


def _tail(path: Path) -> str:
    """Last STDERR_TAIL_CHARS characters of a stderr file; empty when it is missing."""
    try:
        return Path(path).read_text(errors="replace")[-STDERR_TAIL_CHARS:]
    except OSError:
        return ""


def _issue(name: str, ok: bool, detail: str, kind: str = "",
           tier: str = "-", spec: str = "-") -> dict:
    """One check result. A failing check also carries its kind and its OC line."""
    if ok:
        return {"name": name, "ok": True, "detail": detail, "kind": "", "line": ""}
    line = oc_line(_level(kind), LINE_SOURCE, "doctor", tier, spec, kind, detail)
    return {"name": name, "ok": False, "detail": detail, "kind": kind, "line": line}


def _run_models_once(binary: str) -> tuple:
    """`<binary> models` (hybrid_shared.run_models retries an empty first answer).
    Returns (ok, models, detail, kind)."""
    try:
        proc = run_models(binary, MODELS_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return (False, [], "timed out after %ss" % MODELS_TIMEOUT_S, "timeout")
    except OSError as exc:
        return (False, [], "error: %s" % exc, "spawn")
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        kind = classify(proc.returncode, [], stderr)
        return (False, [], "exit %d: %s" % (proc.returncode, stderr), kind)
    models = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not models:
        return (False, [], EMPTY_MODELS, "config")
    return (True, models, "models: %s" % ", ".join(models), "")


def check_opencode(binary: str, routing: dict) -> list:
    """Static and live checks of the opencode binary and routing configuration.

    Returns a list of {"name": str, "ok": bool, "detail": str, "kind": str,
    "line": str} dicts. A failing check has a failure kind and a ready OC line;
    a passing check has an empty kind and an empty line.
    """
    checks = []

    resolved = shutil.which(binary)
    if not resolved and Path(binary).is_file():
        resolved = binary
    checks.append(_issue(
        "opencode_binary",
        bool(resolved),
        resolved if resolved else "not found: %s" % binary,
        "spawn",
    ))

    models_ok, models, models_detail, models_kind = _run_models_once(binary)
    if not models_ok:
        models_ok, models, models_detail, models_kind = _run_models_once(binary)
    checks.append(_issue("opencode_models", models_ok, models_detail, models_kind))

    tiers = routing.get("tiers", {}) if isinstance(routing, dict) else {}
    if not tiers:
        checks.append(_issue("tiers", False, "no tiers configured in routing", "config"))
    else:
        checks.append(_issue("tiers", True, "tiers: %s" % ", ".join(sorted(tiers.keys()))))

    for name in sorted(tiers.keys()):
        tier = tiers[name]
        model = tier.get("model") if isinstance(tier, dict) else None
        variant = tier.get("variant") if isinstance(tier, dict) else None
        spec = _spec(tier)
        checks.append(_issue(
            "tier:%s" % name,
            bool(model),
            "model=%s variant=%s" % (model, variant),
            "config", name, spec,
        ))
        if not model:
            continue   # the tier:<name> check above already reports it (kind=config)

        model_present = models_ok and model in models
        checks.append(_issue(
            "model:%s" % name,
            model_present,
            "%s %s in `%s models`" % (
                model, "found" if model_present else "not found", binary),
            "model" if models_ok else models_kind, name, spec,
        ))

    rows = routing.get("rows", {}) if isinstance(routing, dict) else {}
    for row_name in sorted(rows.keys()):
        tier_name = rows[row_name]
        checks.append(_issue(
            "row:%s" % row_name,
            tier_name in tiers,
            "-> tier %s" % tier_name,
            "config",
        ))

    return checks


def ping_tier(binary: str, tier: dict, prompt_text: str, engine: str, workdir: Path) -> tuple:
    """Send one tiny working ping to a tier and verify the sentinel comes back.

    The CLI message is always the constant PING; prompt_text is injected only
    as the lane prompt, via config_env. Returns (ok: bool, detail: dict) where
    detail has model, variant, text, sessionID and error (the kill reason or
    None), plus the classification of a failed ping: key (the doctor cache key
    of the tier), kind ("" when ok), level ("OC-ERROR" or "OC-WARN", "" when
    ok), message (one line) and log (the stderr file, "" when it is empty).
    """
    model = tier.get("model", "") if isinstance(tier, dict) else ""
    variant = tier.get("variant", "") if isinstance(tier, dict) else ""

    workdir = Path(workdir)
    out_path = workdir / "doctor-ping.out.jsonl"
    err_path = workdir / "doctor-ping.err"

    cmd = build_cmd(binary, model, variant, PING)
    env = dict(os.environ, **config_env(prompt_text, engine, {}))

    result = run_once(cmd, workdir, env, out_path, err_path, stall_s=30, timeout_s=60)

    text = result.get("text") or ""
    reason = result.get("reason") or ""
    ok = (not reason) and text.strip() == SENTINEL
    stderr_tail = _tail(err_path)

    kind = ""
    message = ""
    if not ok:
        errors = result.get("errors") or []
        kind = classify(result.get("rc"), errors, stderr_tail,
                        killed=reason, finished=bool(result.get("finished")))
        if not kind:
            kind = "format" if text.strip() else "empty"
        message = first_error(errors, stderr_tail) or "ping %s: got %r" % (
            reason or "reply mismatch", text[:80])

    detail = {
        "model": model,
        "variant": variant,
        "ok": ok,
        "text": text,
        "sessionID": result.get("session", ""),
        "error": reason or None,
        "key": cache_key(tier),
        "kind": kind,
        "level": _level(kind) if kind else "",
        "message": message,
        "log": str(err_path) if stderr_tail else "",
    }
    return (ok, detail)


def lane_stats(lanes_path: Path) -> list:
    """Aggregate lane records from lanes.jsonl into per backend/tier stats.

    Each line of lanes_path is a JSON record with keys: backend, tier,
    escalated (bool), duration_s (number), tokens (dict with input, output,
    reasoning, cache_read, cache_write) and cost (number).

    Returns a list of dicts, one per (backend, tier) group, sorted by
    backend then tier:
        {"backend": ..., "tier": ..., "count": int, "escalated": int,
         "escalation_rate": float, "median_time_s": float,
         "tokens": {"input": int, "output": int, "reasoning": int,
                     "cache_read": int, "cache_write": int},
         "cost": float}
    """
    lanes_path = Path(lanes_path)
    groups = {}

    if lanes_path.is_file():
        for line in lanes_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            backend = record.get("backend", "claude")
            tier = record.get("tier", "-")
            key = (backend, tier)
            group = groups.setdefault(key, {
                "backend": backend,
                "tier": tier,
                "count": 0,
                "escalated": 0,
                "times": [],
                "tokens": {
                    "input": 0,
                    "output": 0,
                    "reasoning": 0,
                    "cache_read": 0,
                    "cache_write": 0,
                },
                "cost": 0.0,
            })
            group["count"] += 1
            if record.get("escalated"):
                group["escalated"] += 1
            duration = record.get("duration_s")
            if duration is not None:
                group["times"].append(duration)
            tokens = record.get("tokens") or {}
            for tok_key in group["tokens"]:
                group["tokens"][tok_key] += tokens.get(tok_key, 0)
            group["cost"] += record.get("cost", 0.0)

    out = []
    for key in sorted(groups.keys()):
        group = groups[key]
        times = group.pop("times")
        count = group["count"]
        group["escalation_rate"] = (
            float(group["escalated"]) / count if count else 0.0
        )
        group["median_time_s"] = statistics.median(times) if times else 0.0
        out.append(group)

    return out
