"""Doctor checks, provider-error classification, down marking and the init status line."""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from oc_run import THROTTLE_RE, UNAVAILABLE_RE, build_cmd, run_once
from ha_router import ROLES, effective_preset, role_tier
from ha_config import AGENT_NAMES, SENTINEL, config_env

MODELS_TIMEOUT_S = 60
VERSION_TIMEOUT_S = 10
PING_ROLE = "investigator"
PING_PROMPT = "Reply with exactly the token %s and nothing else." % SENTINEL
UNAVAILABLE_LINE = "opencode: unavailable → preset claude (run audit.py doctor --ping)"
_SENTINEL_STRIP_CHARS = "`'\".,!?;:()[]{}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def first_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def doctor_cache_path() -> Path:
    env_path = os.environ.get("HA_DOCTOR_CACHE")
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


def classify_error(message: str) -> str:
    text = message or ""
    if UNAVAILABLE_RE.search(text):
        return "unavailable"
    if THROTTLE_RE.search(text):
        return "throttle"
    return ""


def mark_down(path: Path, tier: str, reason: str, message: str) -> None:
    data = load_doctor(path)
    tiers = data.get("tiers")
    if not isinstance(tiers, dict):
        tiers = {}
        data["tiers"] = tiers
    entry = tiers.get(tier)
    if not isinstance(entry, dict):
        entry = {}
        tiers[tier] = entry
    entry["down"] = {"reason": reason, "message": first_line(message), "at": _now()}
    write_doctor(path, data)


def _safe_role_tier(role: str, routing: dict, preset_eff: str) -> str:
    try:
        return str(role_tier(role, routing, preset_eff))
    except (KeyError, TypeError, AttributeError):
        return "claude"


def _role_backend(role: str, routing: dict, doctor: dict, preset_eff: str) -> str:
    tier = _safe_role_tier(role, routing, preset_eff)
    if tier == "claude":
        return "claude"
    routing_tiers = routing.get("tiers") if isinstance(routing.get("tiers"), dict) else {}
    if tier not in routing_tiers:
        return "claude"
    doctor_tiers = doctor.get("tiers") if isinstance(doctor.get("tiers"), dict) else {}
    entry = doctor_tiers.get(tier)
    if not isinstance(entry, dict):
        return "claude"
    down = entry.get("down")
    if isinstance(down, dict):
        return "claude(down: %s)" % (down.get("reason") or "unknown")
    if not entry.get("listed") or entry.get("ping") == "failed":
        return "claude"
    return "oc:" + tier


def status_line(routing: dict, doctor: dict, preset: str = "") -> str:
    if not isinstance(doctor, dict) or not doctor or not doctor.get("version") or not doctor.get("ok"):
        return UNAVAILABLE_LINE
    routing = routing if isinstance(routing, dict) else {}
    preset_eff = effective_preset(routing, preset)
    bits = ["%s=%s" % (role, _role_backend(role, routing, doctor, preset_eff)) for role in ROLES]
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
        proc = subprocess.run([binary, "models"], capture_output=True, text=True,
                              timeout=MODELS_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return (False, [], "`%s models` timed out after %ss" % (binary, MODELS_TIMEOUT_S))
    except OSError as exc:
        return (False, [], "`%s models` error: %s" % (binary, exc))
    if proc.returncode != 0:
        return (False, [], "`%s models` exit %d: %s" % (
            binary, proc.returncode, first_line(proc.stderr or "")))
    models = [line.split()[0] for line in (proc.stdout or "").splitlines() if line.strip()]
    if not models:
        return (False, [], "`%s models` listed nothing" % binary)
    return (True, models, "")


def _ping_tier(binary: str, name: str, tier: dict, workdir: Path) -> dict:
    model = str(tier.get("model", ""))
    variant = str(tier.get("variant", ""))
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out_path = workdir / ("doctor-ping-%s.jsonl" % name)
    err_path = workdir / ("doctor-ping-%s.err" % name)
    cmd = build_cmd(binary, AGENT_NAMES[PING_ROLE], model, variant, PING_PROMPT)
    env = dict(os.environ, **config_env(PING_ROLE))
    result = run_once(cmd, workdir, env, out_path, err_path,
                      int(tier.get("stall_s", 60)), int(tier.get("timeout_s", 180)))
    reason = result.get("reason") or ""
    text = result.get("text") or ""
    if not reason and _reply_has_sentinel(text):
        return {"ping": "ok", "note": SENTINEL, "down_reason": ""}
    errors = [str(e) for e in (result.get("errors") or [])]
    run_note = str(result.get("note") or "")
    message = (first_line(errors[0]) if errors else "") or first_line(run_note) \
        or first_line(text) or reason or "no sentinel in reply"
    if reason == "unavailable" or classify_error("\n".join(errors + [run_note])) == "unavailable":
        down_reason = "unavailable"
    else:
        down_reason = ""
    return {"ping": "failed", "note": message, "down_reason": down_reason}


def run_doctor(binary: str, routing: dict, ping: bool, workdir: Path, previous: dict) -> dict:
    workdir = Path(workdir)
    routing = routing if isinstance(routing, dict) else {}
    previous = previous if isinstance(previous, dict) else {}
    tiers = routing.get("tiers") if isinstance(routing.get("tiers"), dict) else {}
    prev_tiers = previous.get("tiers") if isinstance(previous.get("tiers"), dict) else {}

    resolved = shutil.which(binary)
    if not resolved and Path(binary).is_file():
        resolved = binary

    version = _check_version(binary)
    models_ok, models, models_note = _run_models_once(binary)
    if not models_ok:
        models_ok, models, models_note = _run_models_once(binary)
    base_ok = bool(resolved) and bool(version) and models_ok

    results = {}
    for name in sorted(tiers):
        tier = tiers[name] if isinstance(tiers[name], dict) else {}
        model = str(tier.get("model", ""))
        variant = str(tier.get("variant", ""))
        listed = models_ok and model in models
        prev_entry = prev_tiers.get(name) if isinstance(prev_tiers.get(name), dict) else {}
        prev_down = prev_entry.get("down") if isinstance(prev_entry.get("down"), dict) else None

        if not models_ok:
            list_note = models_note
        elif listed:
            list_note = "listed"
        else:
            list_note = "model %s not found in `%s models`" % (model, binary)

        if ping and base_ok:
            probe = _ping_tier(binary, name, tier, workdir)
            ping_state = probe["ping"]
            note = probe["note"]
            if ping_state == "ok":
                down = None
            elif probe["down_reason"]:
                down = {"reason": probe["down_reason"], "message": note, "at": _now()}
            else:
                down = prev_down
        elif ping:
            ping_state = "failed"
            note = list_note if not models_ok else "opencode binary or version check failed"
            down = prev_down
        else:
            ping_state = "unchecked"
            note = list_note
            down = prev_down

        results[name] = {"model": model, "variant": variant, "listed": listed,
                         "ping": ping_state, "note": note, "down": down}

    return {
        "t": _now(),
        "ok": base_ok,
        "version": version,
        "binary": resolved or binary,
        "tiers": results,
    }
