"""Routing config and router for hybrid-team.

Decides whether a slice (or a phase of a slice) runs in the main session, on
an opencode-backed tier, or is held. Presets are claude, hybrid and opencode.
Tier model and variant come from the per-skill user file when it sets a model,
else from $HYBRID_OPENCODE_STD/$HYBRID_OPENCODE_LITE (hybrid_shared.resolve_tiers);
max_parallel comes from the per-skill file, else $HYBRID_OPENCODE_MAX_PARALLEL, else routing.default.json;
"held" is returned only in preset opencode, when a unit that has an opencode
runner has no usable opencode tier.
"""

import copy
import json
import os
import sys
from pathlib import Path

import hybrid_shared

PRESETS = ("claude", "hybrid", "opencode")

SKILL_DIR = Path(__file__).resolve().parent.parent

# perf stays on Claude: the gate only counts lines of the pasted bench output (no numeric before/after
# check), so there is no deterministic oracle, and finding the optimization is diagnosis.
_NON_OFFLOADABLE_KINDS = ("research", "perf", "investigator", "brief-debug")
_NON_OFFLOADABLE_MODES = ("fast", "research")


def user_routing_path() -> Path:
    override = os.environ.get("HYBRID_TEAM_ROUTING")
    if override:
        return Path(override)
    return SKILL_DIR / "routing.json"


def _merge(base, override):
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _read_user_routing(user_path, problems):
    try:
        with open(str(user_path)) as f:
            user_routing = json.load(f)
    except (OSError, ValueError) as exc:
        problems.append("%s: cannot read (%s)" % (user_path, exc))
        return {}
    if not isinstance(user_routing, dict):
        problems.append("%s: top level must be a JSON object" % user_path)
        return {}
    for key in ("tiers", "rows"):
        if key in user_routing and not isinstance(user_routing[key], dict):
            problems.append("%s: %s must be a JSON object" % (user_path, key))
            del user_routing[key]
    for name, tier in list(user_routing.get("tiers", {}).items()):
        if not isinstance(tier, dict):
            problems.append("%s: tiers.%s must be a JSON object" % (user_path, name))
            del user_routing["tiers"][name]
    return user_routing


def _normalize_preset(routing, problems, warnings):
    raw = routing.get("preset", "hybrid")
    if raw in PRESETS:
        return
    if raw == "max":
        result = hybrid_shared.mode_to_preset(raw)
        routing["preset"] = result[0]
        note = result[1] if len(result) > 1 else ""
        warnings.append(note if isinstance(note, str) and note
                        else "preset 'max' is an alias of 'opencode'")
        return
    problems.append("unknown preset %r (use claude, hybrid or opencode)" % (raw,))


def load_routing(defaults_path: Path, user_path: Path, plan_routing: dict) -> dict:
    with open(str(defaults_path)) as f:
        routing = json.load(f)
    problems = []
    warnings = []
    user_routing = {}
    if user_path and Path(user_path).exists():
        user_routing = _read_user_routing(user_path, problems)
        routing = _merge(routing, user_routing)
    shared_tiers, shared_problems = hybrid_shared.load_shared()
    effective = copy.deepcopy(user_routing)   # the plan overlay below must never write into user_routing
    plan_tiers = (plan_routing or {}).get("tiers")
    for name, plan_tier in (plan_tiers.items() if isinstance(plan_tiers, dict) else ()):
        if isinstance(plan_tier, dict) and plan_tier.get("model"):
            tiers = effective.setdefault("tiers", {})
            kept = {k: v for k, v in tiers.get(name, {}).items()
                    if k not in ("model", "variant")}
            tiers[name] = _merge(kept, plan_tier)
    routing = hybrid_shared.resolve_tiers(routing, shared_tiers, effective)
    sources = routing["model_sources"]
    if "shared" in sources.values() or "none" in sources.values():
        problems.extend(shared_problems)
    for name, source in sources.items():
        if source == "none":
            problems.append("tier %s has no model: set tiers.%s.model in %s or in %s"
                            % (name, name, user_path, hybrid_shared.SHARED_SOURCE))
    if plan_routing:
        routing = _merge(routing, plan_routing)
    _normalize_preset(routing, problems, warnings)
    routing["config_problems"] = problems
    routing["config_warnings"] = warnings
    return routing


def _tier_available(tier_name, routing, oc_ok, breaker_dir=None):
    if not tier_name or not oc_ok:
        return False
    tier = routing.get("tiers", {}).get(tier_name)
    if tier is None:
        return False
    if tier.get("disabled") or not tier.get("model"):
        return False
    if breaker_dir is not None:
        if hybrid_shared.run_switched(breaker_dir):   # a hybrid run that switched to Claude uses no opencode tier
            return False
        spec = hybrid_shared.model_spec(tier)
        if hybrid_shared.breaker_open(breaker_dir, tier_name, spec):
            return False
    return True


def _no_tier(preset):
    return "held" if preset == "opencode" else "claude"


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


def route(s: dict, routing: dict, oc_ok: bool, breaker_dir: Path = None) -> str:
    preset = routing.get("preset", "hybrid")
    if preset not in PRESETS:
        raise ValueError("unknown preset %r" % (preset,))
    if preset == "claude":
        return "claude"

    mode = s.get("mode")
    if mode in _NON_OFFLOADABLE_MODES:
        return "claude"

    if not _has_oracle(s):
        return "claude"

    backend = s.get("backend")
    if backend == "claude":
        return "claude"

    # the exclusions apply to a pinned slice too: a pin chooses a tier, it never lifts a guard
    kind = s.get("kind")
    if kind in _NON_OFFLOADABLE_KINDS:
        return "claude"

    if preset == "hybrid":
        if s.get("risk") == "high":
            return "claude"

    if backend and backend.startswith("oc:"):
        tier_name = backend.split(":", 1)[1]
        if _tier_available(tier_name, routing, oc_ok, breaker_dir):
            return backend
        return _no_tier(preset)

    row_key = _row_key(s)
    if row_key is None:
        return "claude"

    tier_name = routing.get("rows", {}).get(row_key)
    if _tier_available(tier_name, routing, oc_ok, breaker_dir):
        return "oc:" + tier_name
    return _no_tier(preset)


def phase_backend(s: dict, mode: str, routing: dict, oc_ok: bool, breaker_dir: Path = None) -> str:
    if mode in _NON_OFFLOADABLE_MODES:
        return "claude"
    if mode == "red":
        return "claude"
    return route(s, routing, oc_ok, breaker_dir)


def needs_split(s: dict, routing: dict, oc_ok: bool, breaker_dir: Path = None) -> bool:
    if s.get("kind") != "code":
        return False
    if s.get("backend") == "claude":
        return False
    # "held" also splits, so the GREEN phase is reported instead of running in the main session
    return route(s, routing, oc_ok, breaker_dir) != "claude"


def config_line(routing: dict) -> str:
    """Step 0's config line: each tier's spec followed by where its model came from, e.g.
    `config: std=zai/glm-5.3#high (skill) lite=zai/glm-5.3-flash (shared)`; `no config` for a
    tier with a model in neither place."""
    tiers = routing.get("tiers") or {}
    sources = routing.get("model_sources") or {}
    parts = []
    for name in hybrid_shared.TIERS:
        spec = hybrid_shared.model_spec(tiers.get(name) or {})
        parts.append("%s=%s" % (name, "%s (%s)" % (spec, sources.get(name)) if spec and sources.get(name) in
                                ("skill", "shared") else "no config"))
    return "config: " + " ".join(parts)


def main(argv) -> int:
    """`router.py config`: the `!` preload of SKILL.md Step 0. Read-only, no subprocess, always exit 0."""
    if argv[:1] != ["config"]:
        print("usage: router.py config")
        return 0
    try:
        routing = load_routing(SKILL_DIR / "routing.default.json", user_routing_path(), {})
        print(hybrid_shared.config_summary(routing.get("tiers") or {}, routing.get("config_problems") or []))
        print(config_line(routing))
    except Exception as exc:  # a preload that fails would cancel the skill
        print("config: unreadable (%s: %s) - run `devteam doctor`" % (type(exc).__name__, exc))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
