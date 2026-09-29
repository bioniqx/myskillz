"""Routing config and tier router for hybrid-writing-plans.

Decides whether a plan task (typed by its contract Tier: light, std or deep)
is written by Claude or by an opencode-backed routing tier, following the
preset table, the shipped defaults merged with the user routing file, and
the doctor cache.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

PRESETS = ("claude", "hybrid", "max")
CONTRACT_TIERS = ("light", "std", "deep")

_DEFAULT_PRESET = "hybrid"
_REVIEW_DEFAULTS = {"claude": "risky", "hybrid": "all", "max": "risky"}
_REVIEW_VALUES = ("all", "risky")


def user_routing_path() -> Path:
    override = os.environ.get("HP_ROUTING")
    if override:
        return Path(override)
    return Path.home() / ".config" / "hybrid-writing-plans" / "routing.json"


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


def route(tier: str, routing: dict, doctor: dict, preset: str = "") -> str:
    if tier not in CONTRACT_TIERS:
        tier = "std"
    active = effective_preset(routing, preset)
    if active == "claude":
        return "claude"
    tier_name = None
    if active == "max":
        max_roles = routing.get("max_roles")
        if isinstance(max_roles, dict):
            tier_name = max_roles.get(tier)
    if tier_name is None:
        roles = routing.get("roles")
        if isinstance(roles, dict):
            tier_name = roles.get(tier)
    if not tier_name or tier_name == "claude":
        return "claude"
    if tier_available(tier_name, routing, doctor):
        return "oc:" + tier_name
    return "claude"


def review_policy(routing: dict, preset: str = "") -> str:
    active = effective_preset(routing, preset)
    table = routing.get("review_oc")
    value = table.get(active) if isinstance(table, dict) else None
    if value in _REVIEW_VALUES:
        return value
    return _REVIEW_DEFAULTS[active]
