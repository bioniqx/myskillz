"""Routing config and role router for hybrid-brainstorming.

Decides whether a lane (typed by role, never by a tier the model picks) runs
on Claude or on an opencode-backed tier, following the preset table and the
shipped defaults / user overrides for the routing file.
"""

import json
import os
from pathlib import Path

ROLES = ("locate", "explore", "fact", "research", "draft")
PRESETS = ("claude", "hybrid", "max")

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
    return Path.home() / ".config" / "hybrid-brainstorming" / "routing.json"


def _merge(base, override):
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
    if user_path and Path(user_path).exists():
        with open(str(user_path)) as f:
            user_routing = json.load(f)
        routing = _merge(routing, user_routing)
    return routing


def _tier_available(tier_name, routing, doctor):
    if not tier_name or not doctor.get("ok"):
        return False
    tier = routing.get("tiers", {}).get(tier_name)
    if tier is None:
        return False
    if tier.get("disabled"):
        return False
    tier_doctor = doctor.get("tiers", {}).get(tier_name)
    if tier_doctor is None or not tier_doctor.get("ok"):
        return False
    return True


def route(role: str, routing: dict, doctor: dict, backend: str = "", preset: str = "") -> str:
    if backend:
        if backend == "claude":
            return "claude"
        if backend.startswith("oc:"):
            tier_name = backend.split(":", 1)[1]
            if _tier_available(tier_name, routing, doctor):
                return backend
        return "claude"

    active_preset = preset or routing.get("preset", "hybrid")
    if active_preset == "claude":
        return "claude"

    if role == "research" and not doctor.get("websearch", False):
        return "claude"

    tier_name = None
    if active_preset == "max":
        tier_name = routing.get("max_roles", {}).get(role)
    if tier_name is None:
        tier_name = routing.get("roles", {}).get(role)

    if not tier_name or tier_name == "claude":
        return "claude"

    if _tier_available(tier_name, routing, doctor):
        return "oc:" + tier_name
    return "claude"


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
