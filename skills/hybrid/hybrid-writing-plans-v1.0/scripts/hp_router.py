"""Routing config and tier router for hybrid-writing-plans.

Decides whether a plan task (typed by its contract Tier: light, std or deep)
is written by claude, by an opencode-backed routing tier, or is held (preset
opencode with no usable opencode tier). Inputs: the shipped defaults, the
user routing file, the shared opencode models ($HYBRID_OPENCODE_STD and
$HYBRID_OPENCODE_LITE) and the doctor cache. Per tier, the user routing file's
model and variant win and the shared models are the fallback
(hybrid_shared.resolve_tiers); max_parallel comes only from the user routing
file or the shipped defaults.
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hybrid_shared  # noqa: E402

PRESETS = ("claude", "hybrid", "opencode")
CONTRACT_TIERS = ("light", "std", "deep")

_DEFAULT_PRESET = "hybrid"
_REVIEW_DEFAULTS = {"claude": "risky", "hybrid": "all", "opencode": "risky"}
_REVIEW_VALUES = ("all", "risky")


def user_routing_path() -> Path:
    override = os.environ.get("HP_ROUTING")
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


def _read_user_routing(user_path: Path) -> tuple:
    """Return (routing dict or None, problem text)."""
    try:
        with open(str(user_path)) as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        return None, "cannot read %s: %s" % (user_path, exc)
    if not isinstance(data, dict):
        return None, "%s must hold a JSON object" % user_path
    return data, ""


def _drop_bad_tiers(data: dict, user_path: Path, problems: list) -> dict:
    """Return data without a non-object tiers value or non-object tier entries, noting each in problems."""
    tiers = data.get("tiers")
    if tiers is None:
        return data
    data = dict(data)
    if not isinstance(tiers, dict):
        problems.append("%s: tiers must be a JSON object; ignored" % user_path)
        del data["tiers"]
        return data
    kept = {}
    for name, entry in tiers.items():
        if isinstance(entry, dict):
            kept[name] = entry
        else:
            problems.append("%s: tiers.%s must be a JSON object; ignored" % (user_path, name))
    data["tiers"] = kept
    return data


def _drop_bad_values(data: dict, user_path: Path, problems: list) -> dict:
    """Return data without the roles, review_oc and preset values the router cannot use, noting each in problems."""
    data = _drop_bad_tiers(data, user_path, problems)
    data = dict(data)
    for key in ("roles", "max_roles"):
        if key not in data:
            continue
        if not isinstance(data[key], dict):
            problems.append("%s: %s must be a JSON object; ignored" % (user_path, key))
            del data[key]
            continue
        kept = {}
        for tier, role in data[key].items():
            if isinstance(role, str):
                kept[tier] = role
            else:
                problems.append("%s: %s.%s must be a tier name (a string); ignored" % (user_path, key, tier))
        data[key] = kept
    if "review_oc" in data and not isinstance(data["review_oc"], dict):
        problems.append("%s: review_oc must be a JSON object; ignored" % user_path)
        del data["review_oc"]
    if "preset" in data and hybrid_shared.mode_to_preset(data["preset"])[0] not in PRESETS:
        problems.append("%s: preset %r is not one of claude, hybrid, opencode; ignored" % (user_path, data["preset"]))
        del data["preset"]
    return data


def load_routing(defaults_path: Path, user_path: Path) -> dict:
    with open(str(defaults_path)) as f:
        routing = json.load(f)
    if not isinstance(routing, dict):
        routing = {}
    problems: list = []
    user_routing: dict = {}
    if user_path and Path(user_path).is_file():
        data, problem = _read_user_routing(user_path)
        if problem:
            problems.append(problem)
        else:
            user_routing = _drop_bad_values(data, user_path, problems)
            routing = _merge(routing, user_routing)
            legacy = user_routing.get("review_oc")  # review_oc.max is the old name of review_oc.opencode
            if isinstance(legacy, dict) and "max" in legacy and "opencode" not in legacy:
                routing["review_oc"] = dict(routing.get("review_oc") or {}, opencode=legacy["max"])
    shared_tiers, shared_problems = hybrid_shared.load_shared()
    routing = hybrid_shared.resolve_tiers(routing, shared_tiers, user_routing)
    sources = routing["model_sources"]
    if "shared" in sources.values() or "none" in sources.values():
        problems.extend(shared_problems)
    for name, source in sources.items():
        if source == "none":
            problems.append("tier %s has no model: set tiers.%s.model in %s or in %s"
                            % (name, name, user_path, hybrid_shared.SHARED_SOURCE))
    routing["config_problems"] = problems
    routing["config_warnings"] = []
    if str(user_routing.get("preset") or "").strip().lower() == "max":
        routing["config_warnings"].append("%s sets preset 'max', the deprecated name of 'opencode'; rename it" % user_path)
    return routing


def effective_preset(routing: dict, preset: str = "") -> str:
    """Return claude, hybrid or opencode. The alias max maps to opencode; anything else raises ValueError."""
    active = preset or routing.get("preset") or _DEFAULT_PRESET
    resolved = hybrid_shared.mode_to_preset(active)[0]
    if resolved not in PRESETS:
        raise ValueError("unknown preset: %s" % active)
    return resolved


def tier_available(name: str, routing: dict, doctor: dict, now: float = 0.0, breaker_dir: Path = None) -> bool:
    tiers = routing.get("tiers")
    tier = tiers.get(name) if isinstance(tiers, dict) else None
    if not name or not isinstance(tier, dict) or tier.get("disabled") or not tier.get("model"):
        return False
    doctor_tiers = doctor.get("tiers") if isinstance(doctor, dict) else None
    entry = doctor_tiers.get(name) if isinstance(doctor_tiers, dict) else None
    if not isinstance(entry, dict) or entry.get("ok") is not True:
        return False
    if not hybrid_shared.cache_fresh(entry, tier, now or time.time()):
        return False
    if breaker_dir is not None:
        spec = hybrid_shared.model_spec(tier)
        if hybrid_shared.breaker_open(Path(breaker_dir), name, spec):
            return False
    return True


def route(tier: str, routing: dict, doctor: dict, preset: str = "", now: float = 0.0, breaker_dir: Path = None) -> str:
    """Return claude, oc:<tier> or held. held only occurs in preset opencode."""
    if tier not in CONTRACT_TIERS:
        tier = "std"
    active = effective_preset(routing, preset)
    if active == "claude":
        return "claude"
    tier_name = None
    if active == "opencode":
        max_roles = routing.get("max_roles")
        if isinstance(max_roles, dict):
            tier_name = max_roles.get(tier)
    if tier_name is None:
        roles = routing.get("roles")
        if isinstance(roles, dict):
            tier_name = roles.get(tier)
    if not tier_name or tier_name == "claude":
        return "claude"
    if tier_available(tier_name, routing, doctor, now, breaker_dir):
        return "oc:" + tier_name
    return "held" if active == "opencode" else "claude"


def review_policy(routing: dict, preset: str = "") -> str:
    active = effective_preset(routing, preset)
    table = routing.get("review_oc")
    for key in (("opencode", "max") if active == "opencode" else (active,)):  # "max" is the old key of opencode
        value = table.get(key) if isinstance(table, dict) else None
        if value in _REVIEW_VALUES:
            return value
    return _REVIEW_DEFAULTS[active]
