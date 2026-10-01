"""Split the active checklist items between opencode and Claude investigator batches."""
import math
import sys
from pathlib import Path
from typing import List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit  # noqa: E402
from ha_router import oc_queues_overflow, route  # noqa: E402


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


def split_batches(active: list, routing: dict, doctor: dict, preset: str, cap: int, solo: bool, now: float = 0.0, breaker_dir: Path = None) -> list:
    """Return [(backend, items)]: Claude batches first, then opencode batches.

    Backend "held" means preset opencode found no usable tier: the caller
    reports it and does not dispatch those batches.
    """
    backend = route("investigator", routing, doctor, preset, now=now, breaker_dir=breaker_dir)
    if backend in ("claude", "held"):
        return [(backend, b) for b in audit.partition_items(active, cap, solo)]
    tier = backend[len("oc:"):]
    max_parallel = max(1, int(routing["tiers"][tier].get("max_parallel", 1)))
    batch_max = max(1, int(routing.get("oc_batch_max", 4)))
    capacity = max_parallel * batch_max
    queue = oc_queues_overflow(routing, preset)
    if queue:
        capacity = len(active)  # no Claude overflow: extra batches wait for a free opencode slot
    ordered = sorted(active, key=_order_key)
    oc_items = ordered[:capacity]
    rest = ordered[capacity:]
    out = []
    if rest:
        out.extend(("claude", b) for b in audit.partition_items(rest, cap, solo))
    if oc_items:
        n_batches = min(max_parallel, len(oc_items))
        if queue:
            n_batches = max(n_batches, math.ceil(len(oc_items) / float(batch_max)))
        out.extend((backend, b) for b in _near_equal(oc_items, n_batches))
    return out
