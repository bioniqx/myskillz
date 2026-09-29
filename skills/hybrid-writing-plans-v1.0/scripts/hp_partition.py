"""hp_partition - tier-aware partitioning of contracts into Claude and opencode writer groups."""
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import plan_tool  # noqa: E402
import hp_router  # noqa: E402


def _max_parallel(routing: dict, tier: str) -> int:
    settings = (routing.get("tiers") or {}).get(tier) or {}
    try:
        return max(1, int(settings.get("max_parallel", 1)))
    except (TypeError, ValueError):
        return 1


def _group_max(routing: dict) -> int:
    try:
        return max(1, int(routing.get("oc_group_max", 3)))
    except (TypeError, ValueError):
        return 3


def route_groups(cs: list, routing: dict, doctor: dict, preset: str, cap: int) -> list:
    """Return [(gid, backend, [contract, ...]), ...].

    Claude groups come first (6.2 partition, order and naming), then opencode groups
    O01, O02, ... ordered by first task ID across tiers. backend is "claude" or "oc:<tier>".
    Per tier, tasks beyond max_parallel * oc_group_max move to Claude, heaviest first.
    """
    claude: List[dict] = []
    by_tier: Dict[str, List[dict]] = {}
    for c in cs:
        backend = hp_router.route(c.get("tier") or "std", routing, doctor, preset)
        if backend == "claude":
            claude.append(c)
        else:
            by_tier.setdefault(backend[3:], []).append(c)
    group_max = _group_max(routing)
    oc_groups: List[Tuple[str, List[dict]]] = []
    for tier, tasks in by_tier.items():
        mp = _max_parallel(routing, tier)
        capacity = mp * group_max
        if len(tasks) > capacity:
            ranked = sorted(tasks, key=lambda c: (-plan_tool.weight(c), plan_tool.num(c["id"])))
            moved = {c["id"] for c in ranked[:len(tasks) - capacity]}
            claude.extend(c for c in tasks if c["id"] in moved)
            tasks = [c for c in tasks if c["id"] not in moved]
        for g in plan_tool.partition(tasks, mp):
            oc_groups.append((tier, g))
    claude.sort(key=lambda c: plan_tool.num(c["id"]))
    parts = plan_tool.partition(claude, max(1, cap))
    out = [((g[0]["id"] if len(parts) == len(claude) else "W%02d" % (i + 1)), "claude", g)
           for i, g in enumerate(parts)]
    oc_groups.sort(key=lambda x: plan_tool.num(x[1][0]["id"]))
    out += [("O%02d" % (i + 1), "oc:" + tier, g) for i, (tier, g) in enumerate(oc_groups)]
    return out
