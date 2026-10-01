"""Doctor checks, cache and context status line for the opencode backend."""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from oc_run import build_cmd, run_once
from hb_router import route
from hb_config import AGENT_NAME, SENTINEL, config_env
from hybrid_shared import cache_fresh, cache_key, classify, first_error, model_spec, run_models, run_captured

MODELS_TIMEOUT_S = 60
PING = "PING"
ROLES = ("locate", "explore", "fact", "research", "draft")
_SENTINEL_STRIP_CHARS = "`'\".,!?;:()[]{}"


def _reply_has_sentinel(text: str) -> bool:
    for line in text.splitlines():
        if line.strip().strip(_SENTINEL_STRIP_CHARS) == SENTINEL:
            return True
    return False


def doctor_cache_path() -> Path:
    env_path = os.environ.get("HYBRID_BRAINSTORMING_DOCTOR_CACHE")
    if env_path:
        return Path(env_path)
    return Path.home() / ".cache" / "hybrid-brainstorming" / "doctor.json"


def load_doctor(path: Path) -> dict:
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_doctor(path: Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _stale_tiers(routing: dict, doctor: dict, now: float) -> list:
    tiers = routing.get("tiers", {}) if isinstance(routing, dict) else {}
    entries = doctor.get("tiers") or {}
    return [name for name in sorted(tiers)
            if isinstance(tiers[name], dict) and tiers[name].get("model")  # a tier with no model is config, not stale
            and (not isinstance(entries.get(name), dict) or not cache_fresh(entries[name], tiers[name], now))]


def status_line(routing: dict, doctor: dict, now: float = 0.0) -> str:
    if not doctor or not doctor.get("version"):
        return "opencode: unavailable → preset claude (run bslane.py doctor)"

    preset = routing.get("preset", "claude") if isinstance(routing, dict) else "claude"
    version = doctor.get("version", "")
    timestamp = doctor.get("t", "")
    date = timestamp[:10] if timestamp else ""
    websearch = "on" if doctor.get("websearch") else "off"

    stale = _stale_tiers(routing, doctor, now or time.time()) if preset != "claude" else []
    if stale:
        return "opencode: v%s preset=%s stale tiers=%s (doctor %s) → run bslane.py doctor" % (
            version, preset, ",".join(stale), date,
        )

    role_bits = []
    for role_name in ROLES:
        backend = route(role_name, routing, doctor)
        role_bits.append("%s=%s" % (role_name, backend))

    return "opencode: v%s preset=%s %s websearch=%s (doctor %s)" % (
        version, preset, " ".join(role_bits), websearch, date,
    )


def _check_version(binary: str) -> tuple:
    try:
        proc = run_captured([binary, "--version"], MODELS_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return ("", "timed out after %ss" % MODELS_TIMEOUT_S)
    except OSError as exc:
        return ("", "error: %s" % exc)
    if proc.returncode != 0:
        return ("", "exit %d: %s" % (proc.returncode, (proc.stderr or "").strip()))
    raw = proc.stdout.strip()
    match = re.search(r"\d+(?:\.\d+)+", raw)
    if match:
        bare = match.group(0)
    else:
        tokens = raw.split()
        bare = tokens[0] if tokens else raw
    return (bare, "")


def _run_models_once(binary: str) -> tuple:
    try:
        proc = run_models(binary, MODELS_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return (False, [], "timeout", "opencode models timed out after %ss" % MODELS_TIMEOUT_S)
    except OSError as exc:
        return (False, [], "spawn", _one_line("cannot run %s models: %s" % (binary, exc)))
    if proc.returncode != 0:
        stderr_tail = (proc.stderr or "").strip()[-500:]
        kind = classify(proc.returncode, [], stderr_tail)
        detail = first_error([], stderr_tail) or "exit %d" % proc.returncode
        return (False, [], kind, _one_line(detail))
    models = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    if not models:
        return (False, [], "config", "opencode models listed nothing")
    return (True, models, "", "")


def _one_line(text: str, limit: int = 200) -> str:
    return " ".join(str(text).split())[:limit]


def _tail(path: Path, limit: int = 500) -> str:
    try:
        return Path(path).read_text(errors="replace").strip()[-limit:]
    except OSError:
        return ""


def _ping_tier(binary: str, name: str, tier: dict, workdir: Path) -> tuple:
    workdir = Path(workdir)
    out_path = workdir / ("doctor-ping-%s.out.jsonl" % name)
    err_path = workdir / ("doctor-ping-%s.err" % name)

    cmd = build_cmd(binary, AGENT_NAME, tier.get("model", ""), tier.get("variant", ""), PING)
    prompt_text = "Reply with exactly the token %s and nothing else." % SENTINEL
    env = dict(os.environ, **config_env("locate", prompt_text))

    result = run_once(cmd, workdir, env, out_path, err_path,
                       stall_s=tier.get("stall_s", 60), timeout_s=tier.get("timeout_s", 180))

    text = (result.get("text") or "").strip()
    if not result.get("reason") and _reply_has_sentinel(text):
        return (True, "", "ping ok")

    errors = result.get("errors") or []
    stderr_tail = _tail(err_path)
    kind = classify(result.get("rc"), errors, stderr_tail,
                     result.get("reason") or "", bool(result.get("finished")))
    if kind in ("", "recovered"):  # ran cleanly but did not answer with the sentinel
        kind = "format" if text else "empty"
    detail = first_error(errors, stderr_tail) or result.get("note") or result.get("reason") or "no sentinel"
    return (False, kind, _one_line(detail))


def _websearch_tier(routing: dict):
    tiers = routing.get("tiers") or {}
    for role_map in ("roles", "max_roles"):
        name = (routing.get(role_map) or {}).get("research")
        if name in tiers:
            return tiers[name]
    return next(iter(tiers.values()), None)


def _probe_websearch(binary: str, routing: dict, workdir: Path) -> bool:
    tier = _websearch_tier(routing)
    if not tier:
        return False

    model = tier.get("model", "")
    variant = tier.get("variant", "")

    workdir = Path(workdir)
    out_path = workdir / "doctor-websearch.out.jsonl"
    err_path = workdir / "doctor-websearch.err"

    cmd = build_cmd(
        binary, AGENT_NAME, model, variant,
        "Search the web for the current opencode CLI version and reply with the token %s." % SENTINEL,
    )
    prompt_text = "Use the websearch tool once, then reply with exactly the token %s." % SENTINEL
    env = dict(os.environ, **config_env("research", prompt_text))

    result = run_once(cmd, workdir, env, out_path, err_path,
                       stall_s=tier.get("stall_s", 60), timeout_s=tier.get("timeout_s", 180))

    if result.get("reason"):
        return False
    text = result.get("text") or ""
    if "web search cancelled" in text.lower():
        return False
    for tool in result.get("tools", []):
        if tool.get("tool") == "websearch" and tool.get("status") == "completed":
            return True
    return False


def run_doctor(binary: str, routing: dict, ping: bool, workdir: Path, prev: dict = None,
               probe_web: bool = True) -> dict:
    """Check opencode and every tier. Web search is probed only with ping and probe_web; otherwise the
    previous cache's answer is kept while it was found for the same model, so a plain doctor never
    flips a ping's `websearch=on` back to off."""
    workdir = Path(workdir)
    tiers = routing.get("tiers", {}) if isinstance(routing, dict) else {}

    resolved = shutil.which(binary)
    if not resolved and Path(binary).is_file():
        resolved = binary

    version, _version_note = _check_version(binary)
    models_ok, models, models_kind, models_detail = _run_models_once(binary)
    if not models_ok:
        models_ok, models, models_kind, models_detail = _run_models_once(binary)

    tier_results = {}
    for name in sorted(tiers.keys()):
        tier = tiers[name]
        if not tier.get("model"):
            ok, kind = False, "config"
            detail = "tier has no model in the skill routing file or the shared opencode config"
        elif ping:
            ok, kind, detail = _ping_tier(binary, name, tier, workdir)
        elif not models_ok:
            ok, kind, detail = False, models_kind, models_detail
        elif tier.get("model", "") in models:
            ok, kind, detail = True, "", "listed in opencode models"
        else:
            ok, kind = False, "model"
            detail = _one_line("model %s not found in `%s models`" % (model_spec(tier), binary))
        tier_results[name] = {"ok": ok, "key": cache_key(tier), "checked_at": time.time(),
                              "kind": kind, "detail": detail}

    web_key = cache_key(_websearch_tier(routing))
    prev = prev if isinstance(prev, dict) else {}
    if ping and probe_web:
        websearch = _probe_websearch(binary, routing, workdir)
    else:
        websearch = bool(web_key) and bool(prev.get("websearch")) and prev.get("websearch_key") == web_key

    opencode_ok = bool(resolved) and bool(version) and models_ok
    any_tier_ok = any(entry["ok"] for entry in tier_results.values())

    data = {
        "t": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": opencode_ok and (any_tier_ok or not tier_results),
        "version": version,
        "binary": resolved or binary,
        "tiers": tier_results,
        "websearch": websearch,
        "websearch_key": web_key,
        "status_line": "",
    }
    data["status_line"] = status_line(routing, data, time.time())
    return data
