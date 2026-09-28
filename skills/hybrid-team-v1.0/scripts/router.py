"""Routing config and router for hybrid-team.

Decides whether a slice (or a phase of a slice) runs on Claude or on an
opencode-backed tier, following the preset table in the design spec
(section 7) and the per-slice / per-run / user overrides in section 8.
"""

import json
import os
from pathlib import Path

PRESETS = ("claude", "hybrid", "max")

_NON_OFFLOADABLE_KINDS = ("research", "perf", "investigator", "brief-debug")
_NON_OFFLOADABLE_MODES = ("fast", "research")


def user_routing_path() -> Path:
    override = os.environ.get("HT_ROUTING")
    if override:
        return Path(override)
    return Path.home() / ".config" / "hybrid-team" / "routing.json"


def _merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def load_routing(defaults_path: Path, user_path: Path, plan_routing: dict) -> dict:
    with open(str(defaults_path)) as f:
        routing = json.load(f)
    if user_path and Path(user_path).exists():
        with open(str(user_path)) as f:
            user_routing = json.load(f)
        routing = _merge(routing, user_routing)
    if plan_routing:
        routing = _merge(routing, plan_routing)
    return routing


def _tier_available(tier_name, routing, oc_ok):
    if not tier_name or not oc_ok:
        return False
    tier = routing.get("tiers", {}).get(tier_name)
    if tier is None:
        return False
    if tier.get("disabled"):
        return False
    return True


def _row_key(s):
    kind = s.get("kind")
    size = s.get("size")
    if kind == "docs":
        return "docs"
    if size == "trivial" and kind in ("chore", "refactor"):
        return "trivial"
    if kind in ("code", "refactor", "test", "chore"):
        return kind
    return None


def _has_oracle(s):
    if s.get("kind") in ("chore", "docs") and not (s.get("verify") or "").strip():
        return False
    return True


def route(s: dict, routing: dict, oc_ok: bool) -> str:
    mode = s.get("mode")
    if mode in _NON_OFFLOADABLE_MODES:
        return "claude"

    if not _has_oracle(s):
        return "claude"

    backend = s.get("backend")
    if backend == "claude":
        return "claude"
    if backend and backend.startswith("oc:"):
        tier_name = backend.split(":", 1)[1]
        if _tier_available(tier_name, routing, oc_ok):
            return backend
        return "claude"

    kind = s.get("kind")
    if kind in _NON_OFFLOADABLE_KINDS:
        return "claude"

    preset = routing.get("preset", "hybrid")
    if preset == "claude":
        return "claude"

    if s.get("risk") == "high":
        return "claude"

    size = s.get("size")
    if size == "large" and not (preset == "max" and kind == "code"):
        return "claude"

    row_key = _row_key(s)
    if row_key is None:
        return "claude"

    tier_name = routing.get("rows", {}).get(row_key)
    if _tier_available(tier_name, routing, oc_ok):
        return "oc:" + tier_name
    return "claude"


def phase_backend(s: dict, mode: str, routing: dict, oc_ok: bool) -> str:
    if mode in _NON_OFFLOADABLE_MODES:
        return "claude"
    if mode == "red":
        return "claude"
    return route(s, routing, oc_ok)


def needs_split(s: dict, routing: dict, oc_ok: bool) -> bool:
    if s.get("kind") != "code":
        return False
    if s.get("backend") == "claude":
        return False
    return route(s, routing, oc_ok) != "claude"
