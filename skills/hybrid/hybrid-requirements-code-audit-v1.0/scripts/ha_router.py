"""Routing config and role router for hybrid-requirements-code-audit.

Decides whether an audit role (investigator, verifier or parser) runs on
Claude, on an opencode-backed routing tier, or is held. A tier's model comes
from the user routing file when it sets one, else from the shared env vars
(hybrid_shared.resolve_tiers); the shipped defaults carry only roles,
timeouts and batch settings. The decision uses the preset table, the doctor
cache, the circuit breaker and the per-audit throttle cooldowns.
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hybrid_shared  # noqa: E402

PRESETS = ("claude", "hybrid", "opencode")
ROLES = ("investigator", "verifier", "parser")

_DEFAULT_PRESET = "hybrid"


def user_routing_path() -> Path:
    override = os.environ.get("HA_ROUTING")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "routing.json"


def _merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _read_user_file(user_path: Path, problems: list):
    try:
        with open(str(user_path)) as f:
            user_routing = json.load(f)
    except (OSError, ValueError) as exc:
        problems.append("cannot read %s: %s" % (user_path, exc))
        return None
    if not isinstance(user_routing, dict):
        problems.append("%s must hold a JSON object" % user_path)
        return None
    return user_routing


NUMBER_KEYS = ("oc_batch_max", "max_repairs", "throttle_cooldown_s")
TIER_NUMBER_KEYS = ("max_parallel", "stall_s", "timeout_s")


def _drop_bad_numbers(entry: dict, keys: tuple, where: str, user_path, problems: list) -> None:
    """A tuning key that is not a JSON number is reported and dropped, so the shipped default applies."""
    for key in keys:
        value = entry.get(key)
        if key in entry and (isinstance(value, bool) or not isinstance(value, (int, float))):
            problems.append("%s: %s%s must be a number, got %r" % (user_path, where, key, value))
            del entry[key]


def _drop_bad_tiers(user_routing: dict, user_path, problems: list) -> None:
    _drop_bad_numbers(user_routing, NUMBER_KEYS, "", user_path, problems)
    tiers = user_routing.get("tiers")
    if tiers is None:
        return
    if not isinstance(tiers, dict):
        problems.append("%s: tiers must be a JSON object" % user_path)
        del user_routing["tiers"]
        return
    for name in list(tiers):
        entry = tiers[name]
        if not isinstance(entry, dict):
            problems.append("%s: tiers.%s must be a JSON object" % (user_path, name))
            del tiers[name]
            continue
        if entry.get("model") is not None and not isinstance(entry["model"], str):
            problems.append("%s: tiers.%s.model must be a string" % (user_path, name))
            del entry["model"]
        _drop_bad_numbers(entry, TIER_NUMBER_KEYS, "tiers.%s." % name, user_path, problems)


def load_routing(defaults_path: Path, user_path: Path) -> dict:
    with open(str(defaults_path)) as f:
        routing = json.load(f)
    if not isinstance(routing, dict):
        routing = {}
    problems = []
    user_routing = {}
    if user_path and Path(user_path).is_file():
        loaded = _read_user_file(user_path, problems)
        if loaded is not None:
            user_routing = loaded
            _drop_bad_tiers(user_routing, user_path, problems)
            routing = _merge(routing, user_routing)
    shared_tiers, shared_problems = hybrid_shared.load_shared()
    routing = hybrid_shared.resolve_tiers(routing, shared_tiers, user_routing)
    sources = routing["model_sources"]
    if "shared" in sources.values() or "none" in sources.values():
        problems.extend(shared_problems)
    for name, source in sources.items():
        if source == "none":
            problems.append("tier %s has no model: set tiers.%s.model in %s or set %s"
                            % (name, name, user_path, hybrid_shared.SHARED_SOURCE))
    warnings = []
    if routing.get("preset") == "max":
        warnings.append(hybrid_shared.mode_to_preset("max")[1])
    routing["config_problems"] = problems
    routing["config_warnings"] = warnings
    return routing


def effective_preset(routing: dict, preset: str = "") -> str:
    requested = preset or routing.get("preset") or _DEFAULT_PRESET
    if requested in PRESETS:
        return requested
    active = hybrid_shared.mode_to_preset(requested)[0]
    if active not in PRESETS:
        raise ValueError("unknown preset: %r" % (requested,))
    return active


def role_tier(role: str, routing: dict, preset: str = "") -> str:
    active = effective_preset(routing, preset)
    if active == "claude":
        return "claude"
    roles = routing.get("roles")
    tier = roles.get(role) if isinstance(roles, dict) else None
    if active == "opencode":
        max_roles = routing.get("max_roles")
        if isinstance(max_roles, dict) and role in max_roles:
            tier = max_roles[role]
    if not tier or not isinstance(tier, str):
        return "claude"
    return tier


def tier_available(name: str, routing: dict, doctor: dict, now: float = 0.0, breaker_dir: Path = None) -> bool:
    if not name or not isinstance(doctor, dict):
        return False
    tiers = routing.get("tiers")
    tier = tiers.get(name) if isinstance(tiers, dict) else None
    if not isinstance(tier, dict) or not tier.get("model"):
        return False
    doctor_tiers = doctor.get("tiers")
    entry = doctor_tiers.get(name) if isinstance(doctor_tiers, dict) else None
    if not isinstance(entry, dict) or entry.get("ok") is not True:
        return False
    if doctor.get("frozen"):
        # a run's health snapshot (audit.py freeze_health) never goes stale; a model edit still invalidates it
        if entry.get("key") != hybrid_shared.cache_key(tier):
            return False
    elif not hybrid_shared.cache_fresh(entry, tier, now or time.time()):
        return False
    if breaker_dir is not None:
        spec = hybrid_shared.model_spec(tier)
        if hybrid_shared.breaker_open(breaker_dir, name, spec):
            return False
    return True


def route(role: str, routing: dict, doctor: dict, preset: str = "", cooldown: dict = None, now: float = 0.0, breaker_dir: Path = None) -> str:
    active = effective_preset(routing, preset)
    tier = role_tier(role, routing, active)
    if tier == "claude":
        return "claude"
    if active == "hybrid" and breaker_dir is not None and hybrid_shared.run_switched(breaker_dir):
        return "claude"  # the run moved to Claude after an opencode failure (hybrid_shared.switch_to_claude)
    unusable = "held" if active == "opencode" else "claude"
    if not tier_available(tier, routing, doctor, now, breaker_dir):
        return unusable
    until = (cooldown or {}).get(tier, 0)
    try:
        until = float(until)
    except (TypeError, ValueError):
        until = 0.0
    if now < until:
        return unusable
    return "oc:" + tier
