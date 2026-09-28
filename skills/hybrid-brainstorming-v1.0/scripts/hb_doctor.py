"""Doctor checks, cache and context status line for the opencode backend."""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from oc_run import build_cmd, run_once
from hb_router import route
from hb_config import AGENT_NAME, SENTINEL, config_env

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
    env_path = os.environ.get("HB_DOCTOR_CACHE")
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


def status_line(routing: dict, doctor: dict) -> str:
    if not doctor or not doctor.get("version"):
        return "opencode: unavailable → preset claude (run bslane.py doctor)"

    preset = routing.get("preset", "claude") if isinstance(routing, dict) else "claude"
    version = doctor.get("version", "")
    timestamp = doctor.get("t", "")
    date = timestamp[:10] if timestamp else ""
    websearch = "on" if doctor.get("websearch") else "off"

    role_bits = []
    for role_name in ROLES:
        backend = route(role_name, routing, doctor)
        role_bits.append("%s=%s" % (role_name, backend))

    return "opencode: v%s preset=%s %s websearch=%s (doctor %s)" % (
        version, preset, " ".join(role_bits), websearch, date,
    )


def _check_version(binary: str) -> tuple:
    try:
        proc = subprocess.run([binary, "--version"], capture_output=True, text=True,
                               timeout=MODELS_TIMEOUT_S)
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


def _ping_tier(binary: str, name: str, tier: dict, workdir: Path) -> tuple:
    model = tier.get("model", "") if isinstance(tier, dict) else ""
    variant = tier.get("variant", "") if isinstance(tier, dict) else ""

    workdir = Path(workdir)
    out_path = workdir / ("doctor-ping-%s.out.jsonl" % name)
    err_path = workdir / ("doctor-ping-%s.err" % name)

    cmd = build_cmd(binary, AGENT_NAME, model, variant, PING)
    prompt_text = "Reply with exactly the token %s and nothing else." % SENTINEL
    env = dict(os.environ, **config_env("locate", prompt_text))

    result = run_once(cmd, workdir, env, out_path, err_path,
                       stall_s=tier.get("stall_s", 60) if isinstance(tier, dict) else 60,
                       timeout_s=tier.get("timeout_s", 180) if isinstance(tier, dict) else 180)

    text = (result.get("text") or "").strip()
    ok = (not result.get("reason")) and _reply_has_sentinel(text)
    note = text if ok else (result.get("note") or result.get("reason") or "no sentinel")
    return (ok, note)


def _probe_websearch(binary: str, routing: dict, workdir: Path) -> bool:
    tiers = routing.get("tiers", {}) if isinstance(routing, dict) else {}
    roles = routing.get("roles", {}) if isinstance(routing, dict) else {}
    tier_name = roles.get("research")
    tier = tiers.get(tier_name) if tier_name else None
    if not tier:
        tier = next(iter(tiers.values()), None)
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


def run_doctor(binary: str, routing: dict, ping: bool, workdir: Path) -> dict:
    workdir = Path(workdir)
    tiers = routing.get("tiers", {}) if isinstance(routing, dict) else {}

    resolved = shutil.which(binary)
    if not resolved and Path(binary).is_file():
        resolved = binary

    version, _version_note = _check_version(binary)
    models_ok, models, models_note = _run_models_once(binary)
    if not models_ok:
        models_ok, models, models_note = _run_models_once(binary)

    tier_results = {}
    overall_ok = bool(resolved) and bool(version) and models_ok
    for name in sorted(tiers.keys()):
        tier = tiers[name]
        model = tier.get("model", "") if isinstance(tier, dict) else ""
        variant = tier.get("variant", "") if isinstance(tier, dict) else ""
        model_listed = models_ok and model in models

        if ping:
            ok, note = _ping_tier(binary, name, tier, workdir)
        else:
            ok = model_listed
            note = models_note if model_listed else "model %s not found in `%s models`" % (model, binary)

        tier_results[name] = {"model": model, "variant": variant, "ok": ok, "note": note}
        overall_ok = overall_ok and ok

    websearch = _probe_websearch(binary, routing, workdir) if ping else False

    data = {
        "t": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ok": overall_ok,
        "version": version,
        "binary": resolved or binary,
        "tiers": tier_results,
        "websearch": websearch,
        "status_line": "",
    }
    data["status_line"] = status_line(routing, data)
    return data
