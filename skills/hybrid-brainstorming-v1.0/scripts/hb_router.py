"""Routing config and role router for hybrid-brainstorming.

Decides whether a lane (typed by role, never by a tier the model picks) runs
on Claude or on an opencode-backed tier, following the preset table and the
shipped defaults / user overrides for the routing file.
"""

import copy
import json
import math
import os
import time
from pathlib import Path

import hybrid_shared

ROLES = ("locate", "explore", "fact", "research", "draft")
PRESETS = ("claude", "hybrid", "opencode")

_CLAUDE_AGENTS = {
    "locate": ("Explore", "haiku"),
    "explore": ("Explore", "sonnet"),
    "fact": ("general-purpose", "haiku"),
    "research": ("general-purpose", "sonnet"),
    "draft": ("general-purpose", "sonnet"),
}


def user_routing_path() -> Path:
    override = os.environ.get("HB_ROUTING")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "routing.json"


def _merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _sanitize(routing, defaults, label):
    """Return one problem per wrong-typed key of the merged routing and reset that key.

    A bad value goes back to the shipped default (or is dropped when there is none), so
    nothing downstream crashes on it; the caller reports the problems as config errors.
    """
    problems = []

    def fix(parent, key, path, ok, want, default_parent):
        if key in parent and not ok(parent[key]):
            problems.append("%s: %s must be %s, got %s" % (label, path, want, json.dumps(parent[key])))
            if isinstance(default_parent, dict) and key in default_parent:
                parent[key] = copy.deepcopy(default_parent[key])
            else:
                del parent[key]

    def number(low):
        return lambda v: (isinstance(v, (int, float)) and not isinstance(v, bool)
                          and math.isfinite(v) and v >= low)

    is_obj = lambda v: isinstance(v, dict)  # noqa: E731
    slots = lambda v: isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 64  # noqa: E731
    fix(routing, "preset", "preset", lambda v: v in PRESETS or v == "max", "claude, hybrid or opencode", defaults)
    for key in ("roles", "max_roles"):
        fix(routing, key, key, is_obj, "an object mapping role to tier name", defaults)
        for role in list(routing.get(key) or {}):
            fix(routing[key], role, "%s.%s" % (key, role), lambda v: isinstance(v, str) and bool(v),
                "a tier name", defaults.get(key))
    fix(routing, "tiers", "tiers", is_obj, "an object", defaults)
    for name in list(routing.get("tiers") or {}):
        tiers = routing["tiers"]
        fix(tiers, name, "tiers.%s" % name, is_obj, "an object", defaults.get("tiers"))
        if name not in tiers:
            continue
        dtier = (defaults.get("tiers") or {}).get(name)
        fix(tiers[name], "max_parallel", "tiers.%s.max_parallel" % name, slots, "an integer from 1 to 64", dtier)
        for key in ("stall_s", "timeout_s"):
            fix(tiers[name], key, "tiers.%s.%s" % (name, key), number(1), "a number of seconds", dtier)
        for key in ("model", "variant"):
            fix(tiers[name], key, "tiers.%s.%s" % (name, key), lambda v: isinstance(v, str), "a string", None)
    for key in ("slot_wait_s", "throttle_cooldown_s"):
        fix(routing, key, key, number(0), "a number of seconds", defaults)
    return problems


def load_routing(defaults_path: Path, user_path: Path) -> dict:
    with open(str(defaults_path)) as f:
        routing = json.load(f)
    defaults = copy.deepcopy(routing)
    problems = []
    user_routing = {}
    if user_path and Path(user_path).exists():
        try:
            with open(str(user_path)) as f:
                user_routing = json.load(f)
            if not isinstance(user_routing, dict):
                raise ValueError("top level must be a JSON object")
        except (OSError, ValueError) as exc:
            problems.append("%s: %s" % (user_path, exc))
            user_routing = {}
        else:
            routing = _merge(routing, user_routing)
    problems.extend(_sanitize(routing, defaults, user_path))
    shared_tiers, shared_problems = hybrid_shared.load_shared()
    routing = hybrid_shared.resolve_tiers(routing, shared_tiers, user_routing)
    sources = routing["model_sources"]
    if "shared" in sources.values() or "none" in sources.values():
        problems.extend(shared_problems)
    for name, source in sources.items():
        if source == "none":
            problems.append(
                "tier %s has no model: set tiers.%s.model in %s or in %s"
                % (name, name, user_path, hybrid_shared.SHARED_SOURCE)
            )
    routing["config_problems"] = problems
    routing["config_warnings"] = []
    if routing.get("preset") == "max":
        routing["config_warnings"].append(hybrid_shared.mode_to_preset("max")[1])
    return routing


def _tier_available(tier_name, routing, doctor, now=0.0, breaker_dir=None):
    if not tier_name or not doctor.get("ok"):
        return False
    tier = routing.get("tiers", {}).get(tier_name)
    if tier is None or tier.get("disabled") or not tier.get("model"):
        return False
    tier_doctor = doctor.get("tiers", {}).get(tier_name)
    if tier_doctor is None or not tier_doctor.get("ok"):
        return False
    if not hybrid_shared.cache_fresh(tier_doctor, tier, now):
        return False
    if breaker_dir is not None:
        spec = hybrid_shared.model_spec(tier)
        if hybrid_shared.breaker_open(breaker_dir, tier_name, spec):
            return False
    return True


def _active_preset(name):
    if name == "max":
        name = hybrid_shared.mode_to_preset(name)[0]
    if name not in PRESETS:
        raise ValueError("unknown preset: %s" % name)
    return name


def route(role: str, routing: dict, doctor: dict, backend: str = "", preset: str = "", now: float = 0.0, breaker_dir: Path = None) -> str:
    """Return "claude", "oc:<tier>" or "held".

    "held" is returned only in preset opencode, when no usable tier exists for
    the role. Preset hybrid falls back to "claude" instead.
    """
    now = now or time.time()
    active_preset = _active_preset(preset or routing.get("preset", "hybrid"))
    unusable = "held" if active_preset == "opencode" else "claude"

    if backend:
        if backend == "claude":
            return "claude"
        if backend.startswith("oc:"):
            tier_name = backend.split(":", 1)[1]
            if _tier_available(tier_name, routing, doctor, now, breaker_dir):
                return backend
        return unusable

    if active_preset == "claude":
        return "claude"

    if role == "research" and not doctor.get("websearch", False):
        return unusable

    tier_name = None
    if active_preset == "opencode":
        tier_name = routing.get("max_roles", {}).get(role)
    if tier_name is None:
        tier_name = routing.get("roles", {}).get(role)
    if tier_name == "claude":  # pinned to Claude on purpose: never held
        return "claude"

    if _tier_available(tier_name, routing, doctor, now, breaker_dir):
        return "oc:" + tier_name
    return unusable


def claude_agent(role: str) -> tuple:
    return _CLAUDE_AGENTS[role]


def in_cooldown(lanes_dir: Path, tier: str, now: float) -> bool:
    path = Path(lanes_dir) / ("cooldown-" + tier)
    if not path.exists():
        return False
    try:
        expiry = float(path.read_text().strip())
    except (OSError, ValueError):
        return False
    return now < expiry


def start_cooldown(lanes_dir: Path, tier: str, seconds: int, now: float) -> None:
    path = Path(lanes_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / ("cooldown-" + tier)).write_text(str(now + seconds))
