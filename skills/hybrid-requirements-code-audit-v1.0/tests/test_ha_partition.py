import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import audit  # noqa: E402
import ha_partition  # noqa: E402


def make_routing():
    return {
        "preset": "hybrid",
        "tiers": {
            "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high",
                    "max_parallel": 6, "stall_s": 180, "timeout_s": 900},
            "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low",
                     "max_parallel": 6, "stall_s": 120, "timeout_s": 600},
        },
        "roles": {"investigator": "std", "verifier": "claude", "parser": "claude"},
        "max_roles": {"verifier": "std", "parser": "std"},
        "oc_batch_max": 4,
        "max_repairs": 2,
        "throttle_cooldown_s": 120,
    }


def make_doctor():
    tier = {"listed": True, "ping": "ok", "note": "", "down": None}
    return {
        "t": "2026-09-28T00:00:00Z",
        "ok": True,
        "version": "2.0.18",
        "binary": "opencode",
        "tiers": {
            "std": dict(tier, model="zai-coding-plan/glm-5.3", variant="high"),
            "lite": dict(tier, model="zai-coding-plan/glm-5.3-flash", variant="low"),
        },
    }


def make_items(n):
    return [{"id": "R-%03d" % i, "category": "core", "text": "requirement %d" % i}
            for i in range(1, n + 1)]


def ids_of(batches):
    return [it["id"] for _, items in batches for it in items]


class SplitBatchesTest(unittest.TestCase):
    def test_preset_claude_matches_original_partition(self):
        active = make_items(30)
        got = ha_partition.split_batches(active, make_routing(), make_doctor(), "claude", 4, False)
        want = [("claude", b) for b in audit.partition_items(active, 4, False)]
        self.assertEqual(got, want)

    def test_unavailable_opencode_matches_original_partition(self):
        active = make_items(30)
        got = ha_partition.split_batches(active, make_routing(), {}, "hybrid", 4, False)
        want = [("claude", b) for b in audit.partition_items(active, 4, False)]
        self.assertEqual(got, want)

    def test_investigator_on_claude_matches_original_partition(self):
        routing = make_routing()
        routing["roles"]["investigator"] = "claude"
        active = make_items(30)
        got = ha_partition.split_batches(active, routing, make_doctor(), "hybrid", 4, False)
        want = [("claude", b) for b in audit.partition_items(active, 4, False)]
        self.assertEqual(got, want)

    def test_capacity_split_claude_first_then_opencode(self):
        active = make_items(30)
        got = ha_partition.split_batches(active, make_routing(), make_doctor(), "hybrid", 4, False)
        claude = [(b, items) for b, items in got if b == "claude"]
        oc = [(b, items) for b, items in got if b != "claude"]
        self.assertEqual(got, claude + oc)
        self.assertEqual(len(oc), 6)
        self.assertEqual({b for b, _ in oc}, {"oc:std"})
        self.assertEqual([len(items) for _, items in oc], [4, 4, 4, 4, 4, 4])
        self.assertEqual(ids_of(oc), ["R-%03d" % i for i in range(1, 25)])
        rest = active[24:]
        self.assertEqual(claude, [("claude", b) for b in audit.partition_items(rest, 4, False)])
        self.assertEqual(sorted(ids_of(got)), sorted(it["id"] for it in active))

    def test_small_checklist_goes_entirely_to_opencode(self):
        active = make_items(10)
        got = ha_partition.split_batches(active, make_routing(), make_doctor(), "hybrid", 4, False)
        self.assertEqual([b for b, _ in got], ["oc:std"] * 6)
        self.assertEqual([len(items) for _, items in got], [2, 2, 2, 2, 1, 1])
        self.assertEqual(ids_of(got), ["R-%03d" % i for i in range(1, 11)])

    def test_fewer_items_than_parallel_slots(self):
        active = make_items(3)
        got = ha_partition.split_batches(active, make_routing(), make_doctor(), "hybrid", 4, False)
        self.assertEqual(got, [("oc:std", [it]) for it in active])

    def test_opencode_walks_category_id_order(self):
        active = [
            {"id": "R-002", "category": "beta", "text": "b2"},
            {"id": "R-001", "category": "beta", "text": "b1"},
            {"id": "R-003", "category": "alpha", "text": "a3"},
        ]
        got = ha_partition.split_batches(active, make_routing(), make_doctor(), "hybrid", 4, False)
        self.assertEqual(ids_of(got), ["R-003", "R-001", "R-002"])

    def test_max_preset_uses_investigator_tier(self):
        routing = make_routing()
        routing["roles"]["investigator"] = "lite"
        active = make_items(5)
        got = ha_partition.split_batches(active, routing, make_doctor(), "max", 4, False)
        self.assertEqual({b for b, _ in got}, {"oc:lite"})
        self.assertEqual(sum(len(items) for _, items in got), 5)

    def test_empty_active_returns_no_batches(self):
        got = ha_partition.split_batches([], make_routing(), make_doctor(), "hybrid", 4, False)
        self.assertEqual(got, [])


if __name__ == "__main__":
    unittest.main()
