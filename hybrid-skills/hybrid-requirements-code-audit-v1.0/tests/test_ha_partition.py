import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import audit  # noqa: E402
import ha_partition  # noqa: E402
import hybrid_shared  # noqa: E402

NOW = 1800000000.0


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


def make_doctor(routing):
    tiers = {}
    for name, tier in routing["tiers"].items():
        tiers[name] = {"ok": True, "key": hybrid_shared.cache_key(tier),
                       "checked_at": NOW, "kind": "", "detail": ""}
    return {"tiers": tiers}


def make_items(n):
    return [{"id": "R-%03d" % i, "category": "core", "text": "requirement %d" % i}
            for i in range(1, n + 1)]


def ids_of(batches):
    return [it["id"] for _, items in batches for it in items]


def split(active, routing, doctor, preset, breaker_dir=None):
    return ha_partition.split_batches(active, routing, doctor, preset, 4, False,
                                      now=NOW, breaker_dir=breaker_dir)


class SplitBatchesTest(unittest.TestCase):
    def setUp(self):
        self.routing = make_routing()
        self.doctor = make_doctor(self.routing)

    def test_preset_claude_matches_original_partition(self):
        active = make_items(30)
        got = split(active, self.routing, self.doctor, "claude")
        want = [("claude", b) for b in audit.partition_items(active, 4, False)]
        self.assertEqual(got, want)

    def test_unavailable_opencode_matches_original_partition(self):
        active = make_items(30)
        got = split(active, self.routing, {}, "hybrid")
        want = [("claude", b) for b in audit.partition_items(active, 4, False)]
        self.assertEqual(got, want)

    def test_investigator_on_claude_matches_original_partition(self):
        self.routing["roles"]["investigator"] = "claude"
        active = make_items(30)
        got = split(active, self.routing, self.doctor, "hybrid")
        want = [("claude", b) for b in audit.partition_items(active, 4, False)]
        self.assertEqual(got, want)

    def test_hybrid_queues_every_item_on_opencode_by_default(self):
        active = make_items(60)
        got = split(active, self.routing, self.doctor, "hybrid")
        self.assertEqual({b for b, _ in got}, {"oc:std"})
        self.assertEqual(len(got), 15)
        self.assertEqual([len(items) for _, items in got], [4] * 15)
        self.assertEqual(ids_of(got), ["R-%03d" % i for i in range(1, 61)])

    def test_hybrid_queue_matches_opencode_preset(self):
        active = make_items(30)
        self.assertEqual(split(active, self.routing, self.doctor, "hybrid"),
                         split(active, self.routing, self.doctor, "opencode"))

    def test_oc_overflow_claude_restores_the_capacity_split(self):
        self.routing["oc_overflow"] = "claude"
        active = make_items(60)
        got = split(active, self.routing, self.doctor, "hybrid")
        self.assertEqual(len([1 for b, _ in got if b == "oc:std"]), 6)
        self.assertEqual(sum(len(items) for b, items in got if b == "oc:std"), 24)
        self.assertEqual(sum(len(items) for b, items in got if b == "claude"), 36)

    def test_max_parallel_above_8_is_clamped_in_the_capacity_split(self):
        self.routing["oc_overflow"] = "claude"
        self.routing["tiers"]["std"]["max_parallel"] = 64
        got = split(make_items(200), self.routing, self.doctor, "hybrid")
        self.assertEqual(len([1 for b, _ in got if b == "oc:std"]), 8)
        self.assertEqual(sum(len(items) for b, items in got if b == "oc:std"), 8 * 4)

    def test_oc_overflow_is_ignored_in_opencode_preset(self):
        self.routing["oc_overflow"] = "claude"
        got = split(make_items(30), self.routing, self.doctor, "opencode")
        self.assertEqual({b for b, _ in got}, {"oc:std"})
        self.assertEqual(sum(len(items) for _, items in got), 30)

    def test_unusable_tier_still_routes_everything_to_claude_with_queue(self):
        active = make_items(30)
        self.routing["oc_overflow"] = "queue"
        got = split(active, self.routing, {}, "hybrid")
        self.assertEqual({b for b, _ in got}, {"claude"})

    def test_capacity_split_claude_first_then_opencode(self):
        self.routing["oc_overflow"] = "claude"
        active = make_items(30)
        got = split(active, self.routing, self.doctor, "hybrid")
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
        self.routing["oc_overflow"] = "claude"
        active = make_items(10)
        got = split(active, self.routing, self.doctor, "hybrid")
        self.assertEqual([b for b, _ in got], ["oc:std"] * 6)
        self.assertEqual([len(items) for _, items in got], [2, 2, 2, 2, 1, 1])
        self.assertEqual(ids_of(got), ["R-%03d" % i for i in range(1, 11)])

    def test_fewer_items_than_parallel_slots(self):
        active = make_items(3)
        got = split(active, self.routing, self.doctor, "hybrid")
        self.assertEqual(got, [("oc:std", [it]) for it in active])

    def test_opencode_walks_category_id_order(self):
        active = [
            {"id": "R-002", "category": "beta", "text": "b2"},
            {"id": "R-001", "category": "beta", "text": "b1"},
            {"id": "R-003", "category": "alpha", "text": "a3"},
        ]
        got = split(active, self.routing, self.doctor, "hybrid")
        self.assertEqual(ids_of(got), ["R-003", "R-001", "R-002"])

    def test_opencode_preset_uses_investigator_tier(self):
        self.routing["roles"]["investigator"] = "lite"
        active = make_items(5)
        got = split(active, self.routing, self.doctor, "opencode")
        self.assertEqual({b for b, _ in got}, {"oc:lite"})
        self.assertEqual(sum(len(items) for _, items in got), 5)

    def test_opencode_preset_sends_every_item_to_opencode(self):
        active = make_items(30)
        got = split(active, self.routing, self.doctor, "opencode")
        self.assertEqual({b for b, _ in got}, {"oc:std"})
        self.assertEqual([len(items) for _, items in got], [4, 4, 4, 4, 4, 4, 3, 3])  # oc_batch_max 4 caps a batch
        self.assertEqual(ids_of(got), ["R-%03d" % i for i in range(1, 31)])

    def test_opencode_preset_holds_when_no_tier_is_usable(self):
        active = make_items(30)
        got = split(active, self.routing, {}, "opencode")
        want = [("held", b) for b in audit.partition_items(active, 4, False)]
        self.assertEqual(got, want)
        self.assertEqual(sorted(ids_of(got)), sorted(it["id"] for it in active))

    def test_open_breaker_falls_back_or_holds(self):
        active = make_items(8)
        breaker_dir = Path("unused-breaker-dir")
        with mock.patch.object(hybrid_shared, "breaker_open", return_value={"kind": "auth"}):
            hybrid = split(active, self.routing, self.doctor, "hybrid", breaker_dir)
            opencode = split(active, self.routing, self.doctor, "opencode", breaker_dir)
        self.assertEqual({b for b, _ in hybrid}, {"claude"})
        self.assertEqual({b for b, _ in opencode}, {"held"})
        self.assertEqual(sorted(ids_of(opencode)), sorted(it["id"] for it in active))

    def test_empty_active_returns_no_batches(self):
        for preset in ("hybrid", "opencode"):
            self.assertEqual(split([], self.routing, self.doctor, preset), [])


if __name__ == "__main__":
    unittest.main()
