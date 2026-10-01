"""Doctor checks, per-tier cache entries, provider-error classification and the init status line."""
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

from hybrid_shared import cache_fresh, cache_key, classify, first_error, run_models, run_captured
from oc_run import build_cmd, run_once
from ha_router import ROLES, effective_preset, role_tier
from ha_config import AGENT_NAMES, SENTINEL, config_env

MODELS_TIMEOUT_S = 60
VERSION_TIMEOUT_S = 10
PING_ROLE = "investigator"
PING_PROMPT = "Reply with exactly the token %s and nothing else." % SENTINEL
UNAVAILABLE_LINE = "opencode: unavailable → preset claude (run audit.py doctor --ping)"
UNAVAILABLE_FORMAT = "opencode: unavailable preset=%s (run audit.py doctor --ping)"
EMPTY_MODELS_DETAIL = "opencode models listed nothing"
_SENTINEL_STRIP_CHARS = "`'\".,!?;:()[]{}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def first_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def doctor_cache_path() -> Path:
    env_path = os.environ.get("HYBRID_AUDIT_DOCTOR_CACHE")
    if env_path:
        return Path(env_path)
    return Path.home() / ".cache" / "hybrid-requirements-code-audit" / "doctor.json"


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


def _safe_role_tier(role: str, routing: dict, preset_eff: str) -> str:
    try:
        return str(role_tier(role, routing, preset_eff))
    except (KeyError, TypeError, AttributeError):
        return "claude"


def _role_backend(role: str, routing: dict, doctor: dict, preset_eff: str, now: float) -> str:
    unusable = "held" if preset_eff == "opencode" else "claude"
    tier_name = _safe_role_tier(role, routing, preset_eff)
    if tier_name == "claude":
        return "claude"
    routing_tiers = routing.get("tiers") if isinstance(routing.get("tiers"), dict) else {}
    tier = routing_tiers.get(tier_name)
    if not isinstance(tier, dict):
        return unusable
    doctor_tiers = doctor.get("tiers") if isinstance(doctor.get("tiers"), dict) else {}
    entry = doctor_tiers.get(tier_name)
    if not isinstance(entry, dict):
        return unusable
    if not cache_fresh(entry, tier, now):
        return "%s(stale)" % unusable
    if not entry.get("ok"):
        return "%s(down: %s)" % (unusable, entry.get("kind") or "unknown")
    return "oc:" + tier_name


def status_line(routing: dict, doctor: dict, preset: str = "", now: float = 0.0) -> str:
    routing = routing if isinstance(routing, dict) else {}
    preset_eff = effective_preset(routing, preset)
    if not isinstance(doctor, dict) or not doctor or not doctor.get("version") or not doctor.get("ok"):
        return UNAVAILABLE_FORMAT % preset_eff
    now = now or time.time()
    bits = ["%s=%s" % (role, _role_backend(role, routing, doctor, preset_eff, now))
            for role in ROLES]
    date = str(doctor.get("t") or "")[:10]
    return "opencode: v%s preset=%s %s (doctor %s)" % (
        doctor.get("version"), preset_eff, " ".join(bits), date,
    )


def _reply_has_sentinel(text: str) -> bool:
    for line in (text or "").splitlines():
        if line.strip().strip(_SENTINEL_STRIP_CHARS) == SENTINEL:
            return True
    return False


def _check_version(binary: str) -> str:
    try:
        proc = run_captured([binary, "--version"], VERSION_TIMEOUT_S)
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
    """(ok, models, note, kind): a timeout is kind timeout, a spawn error spawn, anything else config."""
    try:
        proc = run_models(binary, MODELS_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return (False, [], "`%s models` timed out after %ss" % (binary, MODELS_TIMEOUT_S), "timeout")
    except OSError as exc:
        return (False, [], "`%s models` error: %s" % (binary, exc), "spawn")
    if proc.returncode != 0:
        return (False, [], "`%s models` exit %d: %s" % (
            binary, proc.returncode, first_line(proc.stderr or "")), "config")
    models = [line.split()[0] for line in (proc.stdout or "").splitlines() if line.strip()]
    if not models:
        return (False, [], EMPTY_MODELS_DETAIL, "config")
    return (True, models, "", "")


def _entry(tier: dict, now: float, ok: bool, kind: str, detail: str) -> dict:
    return {"ok": ok, "key": cache_key(tier), "checked_at": now, "kind": kind, "detail": detail}


def _ping_tier(binary: str, name: str, tier: dict, workdir: Path, now: float, logdir: Path) -> dict:
    """One-token ping run in workdir (the repo); its event and stderr logs go to logdir, never the repo."""
    model = str(tier.get("model", ""))
    variant = str(tier.get("variant", ""))
    workdir = Path(workdir)
    logdir = Path(logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    out_path = logdir / ("doctor-ping-%s.jsonl" % name)
    err_path = logdir / ("doctor-ping-%s.err" % name)
    cmd = build_cmd(binary, AGENT_NAMES[PING_ROLE], model, variant, PING_PROMPT)
    env = dict(os.environ, **config_env(PING_ROLE))
    result = run_once(cmd, workdir, env, out_path, err_path,
                      int(tier.get("stall_s", 60)), int(tier.get("timeout_s", 180)))
    reason = result.get("reason") or ""
    text = result.get("text") or ""
    finished = bool(result.get("finished"))
    if _reply_has_sentinel(text) and (not reason or finished):
        return _entry(tier, now, True, "recovered" if reason else "", SENTINEL)
    errors = [str(e) for e in (result.get("errors") or [])]
    stderr_tail = str(result.get("stderr_tail") or result.get("note") or "")
    killed = reason if reason in ("timeout", "stall") else ""
    kind = classify(result.get("rc"), errors, stderr_tail, killed, finished) or "format"
    detail = first_error(errors, stderr_tail) or first_line(text) or reason \
        or "no sentinel in reply"
    return _entry(tier, now, False, kind, detail)


def run_doctor(binary: str, routing: dict, ping: bool, workdir: Path, previous: dict,
               names=None, logdir: Path = None) -> dict:
    """Check the binary, `opencode models` and (ping) each tier; names limits the tiers checked, the others
    keep their previous entry. Ping logs go to logdir (default: the doctor cache's folder)."""
    workdir = Path(workdir)
    logdir = Path(logdir) if logdir else doctor_cache_path().parent
    routing = routing if isinstance(routing, dict) else {}
    previous = previous if isinstance(previous, dict) else {}
    tiers = routing.get("tiers") if isinstance(routing.get("tiers"), dict) else {}
    prev_tiers = previous.get("tiers") if isinstance(previous.get("tiers"), dict) else {}
    now = time.time()

    resolved = shutil.which(binary)
    if not resolved and Path(binary).is_file():
        resolved = binary

    version = _check_version(binary)
    models_ok, models, models_note, models_kind = _run_models_once(binary)
    if not models_ok:
        models_ok, models, models_note, models_kind = _run_models_once(binary)
    binary_ok = bool(resolved) and bool(version)
    base_ok = binary_ok and models_ok

    results = {}
    for name in sorted(tiers):
        tier = tiers[name] if isinstance(tiers[name], dict) else {}
        model = str(tier.get("model", ""))
        prev_entry = prev_tiers.get(name)
        if names is not None and name not in names:
            if isinstance(prev_entry, dict):
                results[name] = prev_entry
        elif base_ok and not ping and isinstance(prev_entry, dict) \
                and cache_fresh(prev_entry, tier, now):
            results[name] = prev_entry
        elif not binary_ok:
            results[name] = _entry(tier, now, False, "spawn",
                                   "opencode binary or version check failed")
        elif not models_ok:
            results[name] = _entry(tier, now, False, models_kind, models_note)
        elif not model:
            results[name] = _entry(tier, now, False, "config",
                                   "tier %s has no model: set $HYBRID_OPENCODE_STD or tiers.%s.model" % (name, name))
        elif model not in models:
            results[name] = _entry(tier, now, False, "model",
                                   "model %s not found in `%s models`" % (model, binary))
        elif ping:
            results[name] = _ping_tier(binary, name, tier, workdir, now, logdir)
        else:
            results[name] = _entry(tier, now, True, "", "listed")

    return {
        "t": _now(),
        "ok": base_ok,
        "version": version,
        "binary": resolved or binary,
        "tiers": results,
    }
