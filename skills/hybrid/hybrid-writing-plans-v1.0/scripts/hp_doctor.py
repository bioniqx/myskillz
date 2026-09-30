"""Doctor checks, per-tier cache entries and the context status line."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from oc_run import build_cmd, run_once
from hp_router import CONTRACT_TIERS, effective_preset, route, review_policy
from hp_config import AGENT_NAME, SENTINEL, config_env
from hybrid_shared import cache_fresh, cache_key, classify, first_error, run_models

MODELS_TIMEOUT_S = 60
VERSION_TIMEOUT_S = 10
PING = "PING"
PING_OK = "ping ok"
UNAVAILABLE_LINES = {
    "hybrid": "opencode: unavailable → Claude writers (preset hybrid; run plan_tool.py doctor --ping)",
    "opencode": "opencode: unavailable → tasks held (preset opencode; run plan_tool.py doctor --ping)",
}
CLAUDE_ONLY_LINE = "opencode: not used (preset claude)"
_SENTINEL_STRIP_CHARS = "`'\".,!?;:()[]{}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clock() -> float:
    return time.time()


def first_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def doctor_cache_path() -> Path:
    env_path = os.environ.get("HP_DOCTOR_CACHE")
    if env_path:
        return Path(env_path)
    return Path.home() / ".cache" / "hybrid-writing-plans" / "doctor.json"


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
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def _role_tier(tier: str, routing: dict, preset_eff: str) -> str:
    if preset_eff == "claude":
        return ""
    roles = routing.get("roles") if isinstance(routing.get("roles"), dict) else {}
    role = roles.get(tier, "claude")
    if preset_eff in ("opencode", "max"):
        max_roles = routing.get("max_roles") if isinstance(routing.get("max_roles"), dict) else {}
        role = max_roles.get(tier, role)
    return "" if role == "claude" else str(role)


def _tier_note(doctor: dict, routing: dict, name: str, now: float) -> str:
    tiers = routing.get("tiers") if isinstance(routing.get("tiers"), dict) else {}
    tier = tiers.get(name)
    if not isinstance(tier, dict) or not tier.get("model"):
        return "down: config"
    if tier.get("disabled"):
        return "disabled"
    entries = doctor.get("tiers") if isinstance(doctor.get("tiers"), dict) else {}
    entry = entries.get(name)
    if not isinstance(entry, dict) or not entry or not cache_fresh(entry, tier, now):
        return "stale"
    if not entry.get("ok"):
        return "down: %s" % (entry.get("kind") or "unknown")
    return ""


def status_line(routing: dict, doctor: dict, preset: str = "", now: float = 0.0) -> str:
    routing = routing if isinstance(routing, dict) else {}
    preset_eff = effective_preset(routing, preset)
    usable = isinstance(doctor, dict) and bool(doctor.get("version")) and bool(doctor.get("ok"))
    if not usable:
        return CLAUDE_ONLY_LINE if preset_eff == "claude" else UNAVAILABLE_LINES[preset_eff]
    now = now or _clock()
    bits = []
    for tier in CONTRACT_TIERS:
        backend = route(tier, routing, doctor, preset)
        if backend in ("claude", "held"):
            name = _role_tier(tier, routing, preset_eff)
            note = _tier_note(doctor, routing, name, now) if name else ""
            if note:
                backend = "%s(%s)" % (backend, note)
        bits.append("%s=%s" % (tier, backend))
    date = str(doctor.get("t") or "")[:10]
    return "opencode: v%s preset=%s %s review_oc=%s (doctor %s)" % (
        doctor.get("version"), preset_eff, " ".join(bits), review_policy(routing, preset), date,
    )


def _reply_has_sentinel(text: str) -> bool:
    for line in (text or "").splitlines():
        if line.strip().strip(_SENTINEL_STRIP_CHARS) == SENTINEL:
            return True
    return False


def _check_version(binary: str) -> str:
    try:
        proc = subprocess.run([binary, "--version"], capture_output=True, text=True,
                              timeout=VERSION_TIMEOUT_S)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    if proc.returncode != 0:
        return ""
    raw = (proc.stdout or "").strip()
    match = re.search(r"\d+(?:\.\d+)+", raw)
    if match:
        return match.group(0)
    tokens = raw.split()
    return tokens[0] if tokens else ""


def _run_models_once(binary: str) -> tuple:
    try:
        proc = run_models(binary, MODELS_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return (False, [], "timeout", "`%s models` timed out after %ss" % (binary, MODELS_TIMEOUT_S))
    except OSError as exc:
        return (False, [], "spawn", "`%s models` error: %s" % (binary, exc))
    if proc.returncode != 0:
        stderr = proc.stderr or ""
        kind = classify(proc.returncode, [], stderr) or "crash"
        detail = "`%s models` exit %d: %s" % (binary, proc.returncode, first_error([], stderr))
        return (False, [], kind, detail)
    models = [line.split()[0] for line in (proc.stdout or "").splitlines() if line.strip()]
    if not models:
        return (False, [], "config", "opencode models listed nothing")
    return (True, models, "", "")


def _ping_tier(binary: str, name: str, tier: dict, workdir: Path) -> tuple:
    model = str(tier.get("model", ""))
    variant = str(tier.get("variant", ""))
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out_path = workdir / ("doctor-ping-%s.jsonl" % name)
    err_path = workdir / ("doctor-ping-%s.err" % name)
    cmd = build_cmd(binary, AGENT_NAME, model, variant, PING)
    prompt_text = "Reply with exactly the token %s and nothing else." % SENTINEL
    env = dict(os.environ, **config_env(prompt_text))
    result = run_once(cmd, workdir, env, out_path, err_path,
                      int(tier.get("stall_s", 60)), int(tier.get("timeout_s", 180)))
    reason = result.get("reason") or ""
    text = result.get("text") or ""
    if _reply_has_sentinel(text) and (not reason or result.get("finished")):
        return (True, "", PING_OK)
    errors = [str(e) for e in (result.get("errors") or [])]
    try:  # classify on opencode's stderr, not on the runner's one-line note
        stderr_tail = err_path.read_text(encoding="utf-8", errors="replace").strip()[-500:]
    except OSError:
        stderr_tail = ""
    killed = reason if reason in ("stall", "timeout") else ""
    kind = classify(result.get("rc"), errors, stderr_tail, killed, False)
    detail = first_error(errors, stderr_tail) or first_line(text) or reason or "no sentinel in reply"
    if kind == "throttle":
        return (True, kind, detail)
    return (False, kind or ("format" if text.strip() else "empty"), detail)


def _tier_entry(tier: dict, now: float, ok: bool, kind: str, detail: str, ping: bool = False) -> dict:
    key = cache_key(tier) if tier.get("model") else ""
    entry = {"ok": ok, "key": key, "checked_at": now, "kind": kind, "detail": detail}
    if ping:  # a real reply check: a plain `doctor` (no --ping) keeps it until it expires
        entry["ping"] = True
    return entry


def run_doctor(binary: str, routing: dict, ping: bool, workdir: Path, previous: dict) -> dict:
    workdir = Path(workdir)
    routing = routing if isinstance(routing, dict) else {}
    previous = previous if isinstance(previous, dict) else {}
    tiers = routing.get("tiers") if isinstance(routing.get("tiers"), dict) else {}
    prev_tiers = previous.get("tiers") if isinstance(previous.get("tiers"), dict) else {}
    now = _clock()

    resolved = shutil.which(binary)
    if not resolved and Path(binary).is_file():
        resolved = binary

    version = _check_version(binary)
    models_ok, models, models_kind, models_detail = _run_models_once(binary)
    if not models_ok:
        models_ok, models, models_kind, models_detail = _run_models_once(binary)
    base_ok = bool(resolved) and bool(version) and models_ok

    if not resolved:
        base_fail = ("spawn", "opencode binary not found: %s" % binary)
    elif not version:
        base_fail = ("spawn", "`%s --version` failed" % binary)
    elif not models_ok:
        base_fail = (models_kind, models_detail)
    else:
        base_fail = None

    results = {}
    for name in sorted(tiers):
        tier = tiers[name] if isinstance(tiers[name], dict) else {}
        model = str(tier.get("model", ""))
        prev_entry = prev_tiers.get(name) if isinstance(prev_tiers.get(name), dict) else {}
        if not model:
            ok, kind, detail = False, "config", "tier %s has no model in the opencode config" % name
        elif base_fail:
            ok, kind, detail = False, base_fail[0], base_fail[1]
        elif model not in models:
            ok, kind, detail = False, "model", "model %s not found in `%s models`" % (model, binary)
        elif ping:
            ok, kind, detail = _ping_tier(binary, name, tier, workdir)
            results[name] = _tier_entry(tier, now, ok, kind, detail, ping=True)
            continue
        elif (prev_entry.get("ping") or prev_entry.get("detail") == PING_OK) and cache_fresh(prev_entry, tier, now):
            results[name] = dict(prev_entry)  # a fresh ping result, good or failed, is not overwritten by "listed"
            continue
        else:
            ok, kind, detail = True, "", "listed"
        results[name] = _tier_entry(tier, now, ok, kind, detail)

    return {
        "t": _now(),
        "ok": base_ok,
        "version": version,
        "binary": resolved or binary,
        "tiers": results,
    }
