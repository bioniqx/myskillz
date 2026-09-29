"""Routing config and role router for hybrid-requirements-code-audit.

Decides whether an audit role (investigator, verifier or parser) runs on
Claude or on an opencode-backed routing tier, following the preset table,
the shipped defaults merged with the user routing file, the doctor cache
and the per-audit throttle cooldowns.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

PRESETS = ("claude", "hybrid", "max")
ROLES = ("investigator", "verifier", "parser")

_DEFAULT_PRESET = "hybrid"


def user_routing_path() -> Path:
    override = os.environ.get("HA_ROUTING")
    if override:
        return Path(override)
    return Path.home() / ".config" / "hybrid-requirements-code-audit" / "routing.json"


def _merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_routing(defaults_path: Path, user_path: Path) -> dict:
    with open(str(defaults_path)) as f:
        routing = json.load(f)
    if not isinstance(routing, dict):
        routing = {}
    if user_path and Path(user_path).is_file():
        try:
            with open(str(user_path)) as f:
                user_routing = json.load(f)
        except (OSError, ValueError):
            user_routing = None
        if isinstance(user_routing, dict):
            routing = _merge(routing, user_routing)
    return routing


def effective_preset(routing: dict, preset: str = "") -> str:
    active = preset or routing.get("preset") or _DEFAULT_PRESET
    if active not in PRESETS:
        return "claude"
    return active


def role_tier(role: str, routing: dict, preset: str = "") -> str:
    active = effective_preset(routing, preset)
    if active == "claude":
        return "claude"
    roles = routing.get("roles")
    tier = roles.get(role) if isinstance(roles, dict) else None
    if active == "max":
        max_roles = routing.get("max_roles")
        if isinstance(max_roles, dict) and role in max_roles:
            tier = max_roles[role]
    if not tier or not isinstance(tier, str):
        return "claude"
    return tier


def tier_available(name: str, routing: dict, doctor: dict) -> bool:
    if not name or not isinstance(doctor, dict) or doctor.get("ok") is not True:
        return False
    tiers = routing.get("tiers")
    if not isinstance(tiers, dict) or not isinstance(tiers.get(name), dict):
        return False
    doctor_tiers = doctor.get("tiers")
    if not isinstance(doctor_tiers, dict):
        return False
    entry = doctor_tiers.get(name)
    if not isinstance(entry, dict):
        return False
    if entry.get("listed") is not True:
        return False
    if entry.get("ping") == "failed":
        return False
    if entry.get("down") is not None:
        return False
    return True


def route(role: str, routing: dict, doctor: dict, preset: str = "", cooldown: dict = None, now: float = 0.0) -> str:
    tier = role_tier(role, routing, preset)
    if tier == "claude":
        return "claude"
    tiers = routing.get("tiers")
    if not isinstance(tiers, dict) or tier not in tiers:
        return "claude"
    if not tier_available(tier, routing, doctor):
        return "claude"
    until = (cooldown or {}).get(tier, 0)
    try:
        until = float(until)
    except (TypeError, ValueError):
        until = 0.0
    if now < until:
        return "claude"
    return "oc:" + tier
