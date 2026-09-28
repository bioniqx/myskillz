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

PING = "PING"
MODELS_TIMEOUT_S = 60


def _run_models_once(binary: str) -> tuple:
    """One attempt at `<binary> models`. Returns (ok, models, detail)."""
    try:
        proc = subprocess.run([binary, "models"], capture_output=True, text=True,
                               timeout=MODELS_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return (False, [], "timed out after %ss" % MODELS_TIMEOUT_S)
    except OSError as exc:
        return (False, [], "error: %s" % exc)
    if proc.returncode != 0:
        return (False, [], "exit %d: %s" % (proc.returncode, (proc.stderr or "").strip()))
    models = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not models:
        return (False, [], "models: (empty)")
    return (True, models, "models: %s" % ", ".join(models))


def check_opencode(binary: str, routing: dict) -> list:
    """Static and live checks of the opencode binary and routing configuration.

    Returns a list of {"name": str, "ok": bool, "detail": str} dicts.
    """
    checks = []

    resolved = shutil.which(binary)
    if not resolved and Path(binary).is_file():
        resolved = binary
    checks.append({
        "name": "opencode_binary",
        "ok": bool(resolved),
        "detail": resolved if resolved else "not found: %s" % binary,
    })

    models_ok, models, models_detail = _run_models_once(binary)
    if not models_ok:
        models_ok, models, models_detail = _run_models_once(binary)
    checks.append({"name": "opencode_models", "ok": models_ok, "detail": models_detail})

    tiers = routing.get("tiers", {}) if isinstance(routing, dict) else {}
    if not tiers:
        checks.append({
            "name": "tiers",
            "ok": False,
            "detail": "no tiers configured in routing",
        })
    else:
        checks.append({
            "name": "tiers",
            "ok": True,
            "detail": "tiers: %s" % ", ".join(sorted(tiers.keys())),
        })

    for name in sorted(tiers.keys()):
        tier = tiers[name]
        model = tier.get("model") if isinstance(tier, dict) else None
        variant = tier.get("variant") if isinstance(tier, dict) else None
        ok = bool(model) and bool(variant)
        checks.append({
            "name": "tier:%s" % name,
            "ok": ok,
            "detail": "model=%s variant=%s" % (model, variant),
        })

        model_present = models_ok and model in models
        checks.append({
            "name": "model:%s" % name,
            "ok": model_present,
            "detail": "%s %s in `%s models`" % (
                model, "found" if model_present else "not found", binary),
        })

    rows = routing.get("rows", {}) if isinstance(routing, dict) else {}
    for row_name in sorted(rows.keys()):
        tier_name = rows[row_name]
        ok = tier_name in tiers
        checks.append({
            "name": "row:%s" % row_name,
            "ok": ok,
            "detail": "-> tier %s" % tier_name,
        })

    return checks


def ping_tier(binary: str, tier: dict, prompt_text: str, engine: str, workdir: Path) -> tuple:
    """Send one tiny working ping to a tier and verify the sentinel comes back.

    The CLI message is always the constant PING; prompt_text is injected only
    as the agent's own prompt, via config_env. Returns (ok: bool, detail: dict)
    where detail has model, variant, text, sessionID and error.
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
    ok = (not result.get("reason")) and text.strip() == SENTINEL

    detail = {
        "model": model,
        "variant": variant,
        "ok": ok,
        "text": text,
        "sessionID": result.get("session", ""),
        "error": result.get("reason") or None,
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
