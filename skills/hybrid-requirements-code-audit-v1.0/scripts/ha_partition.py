"""Split the active checklist items between opencode and Claude investigator batches."""
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit  # noqa: E402
from ha_router import route  # noqa: E402


def _order_key(item: dict) -> Tuple[str, str]:
    return (str(item.get("category") or ""), str(item.get("id") or ""))


def _near_equal(items: list, n_batches: int) -> List[list]:
    base, extra = divmod(len(items), n_batches)
    out = []
    pos = 0
    for i in range(n_batches):
        size = base + (1 if i < extra else 0)
        out.append(items[pos:pos + size])
        pos += size
    return out


def split_batches(active: list, routing: dict, doctor: dict, preset: str, cap: int, solo: bool) -> list:
    """Return [(backend, items)]: Claude batches first, then opencode batches."""
    backend = route("investigator", routing, doctor, preset)
    if backend == "claude":
        return [("claude", b) for b in audit.partition_items(active, cap, solo)]
    tier = backend[len("oc:"):]
    max_parallel = max(1, int(routing["tiers"][tier].get("max_parallel", 1)))
    batch_max = max(1, int(routing.get("oc_batch_max", 4)))
    capacity = max_parallel * batch_max
    ordered = sorted(active, key=_order_key)
    oc_items = ordered[:capacity]
    rest = ordered[capacity:]
    out = []
    if rest:
        out.extend(("claude", b) for b in audit.partition_items(rest, cap, solo))
    if oc_items:
        n_batches = min(max_parallel, len(oc_items))
        out.extend((backend, b) for b in _near_equal(oc_items, n_batches))
    return out
