import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hp_partition  # noqa: E402
import hybrid_shared  # noqa: E402
import plan_tool  # noqa: E402

NOW = 1800000000.0

ROUTING = {
    "preset": "hybrid",
    "tiers": {
        "std": {"model": "acme/std-model", "variant": "high", "max_parallel": 6, "stall_s": 180, "timeout_s": 900},
        "lite": {"model": "acme/lite-model", "variant": "low", "max_parallel": 6, "stall_s": 120, "timeout_s": 600},
    },
    "roles": {"light": "lite", "std": "std", "deep": "claude"},
    "max_roles": {"deep": "std"},
    "review_oc": {"hybrid": "all", "max": "risky"},
    "oc_group_max": 3,
    "max_repairs": 2,
    "throttle_cooldown_s": 120,
}


def doctor_ok(routing=ROUTING, **overrides):
    tiers = {}
    for name, tier in routing["tiers"].items():
        entry = {"ok": True, "key": hybrid_shared.cache_key(tier), "checked_at": NOW,
                 "kind": "", "detail": ""}
        entry.update(overrides.get(name, {}))
        tiers[name] = entry
    return {"tiers": tiers}


def C(tid, tier="std", spec=((1, 1),), files=1, produces=0):
    return {
        "id": tid, "tier": tier, "spec": list(spec),
        "files": ["pkg/%s_%d.py" % (tid.lower(), i) for i in range(files)],
        "produces": ["def p%d_%s()" % (i, tid.lower()) for i in range(produces)],
    }


def shape(groups):
    return [(gid, backend, [c["id"] for c in g]) for gid, backend, g in groups]


def run_groups(cs, preset, doctor=None, cap=20, routing=ROUTING, breaker_dir=None):
    doctor = doctor_ok(routing) if doctor is None else doctor
    return hp_partition.route_groups(cs, routing, doctor, preset, cap, now=NOW, breaker_dir=breaker_dir)


class RouteGroupsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        env = {
            "HOME": t,
            "XDG_DATA_HOME": os.path.join(t, "data"),
            "HYBRID_OPENCODE_STD": "acme/std-model#high",
            "HYBRID_OPENCODE_LITE": "acme/lite-model#low",
            "HYBRID_WRITING_PLANS_ROUTING": os.path.join(t, "routing.json"),
            "HYBRID_WRITING_PLANS_DOCTOR_CACHE": os.path.join(t, "doctor.json"),
            "HYBRID_WRITING_PLANS_TELEMETRY": os.path.join(t, "lanes.jsonl"),
        }
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_claude_preset_matches_62_partition(self):
        cs = [C("T01"), C("T02"), C("T03")]
        got = run_groups(cs, "claude")
        self.assertEqual(shape(got), [("T01", "claude", ["T01"]), ("T02", "claude", ["T02"]), ("T03", "claude", ["T03"])])
        got = run_groups(cs, "claude", cap=1)
        self.assertEqual(shape(got), [("W01", "claude", ["T01", "T02", "T03"])])
        self.assertEqual([g for _, _, g in got], plan_tool.partition(cs, 1))

    def test_hybrid_routes_by_tier_and_names_oc_groups_in_id_order(self):
        cs = [C("T01", "light"), C("T02", "deep"), C("T03", "std"), C("T04", "light")]
        got = run_groups(cs, "hybrid")
        self.assertEqual(shape(got), [
            ("T02", "claude", ["T02"]),
            ("O01", "oc:lite", ["T01"]),
            ("O02", "oc:std", ["T03"]),
            ("O03", "oc:lite", ["T04"]),
        ])

    def test_opencode_preset_sends_deep_to_std(self):
        got = run_groups([C("T01", "deep")], "opencode")
        self.assertEqual(shape(got), [("O01", "oc:std", ["T01"])])

    def test_max_alias_behaves_like_opencode(self):
        got = run_groups([C("T01", "deep")], "max")
        self.assertEqual(shape(got), [("O01", "oc:std", ["T01"])])

    def test_unknown_preset_raises(self):
        with self.assertRaises(ValueError):
            run_groups([C("T01")], "turbo")

    def test_no_doctor_cache_means_all_claude_in_hybrid(self):
        cs = [C("T01", "light"), C("T02", "std")]
        got = run_groups(cs, "hybrid", doctor={})
        self.assertEqual(shape(got), [("T01", "claude", ["T01"]), ("T02", "claude", ["T02"])])

    def test_no_doctor_cache_holds_every_task_in_opencode(self):
        cs = [C("T01", "light"), C("T02", "std")]
        got = run_groups(cs, "opencode", doctor={})
        self.assertEqual(shape(got), [("T01", "held", ["T01"]), ("T02", "held", ["T02"])])

    def test_opencode_holds_only_tasks_without_a_usable_tier(self):
        cs = [C("T01", "light"), C("T02", "std"), C("T03", "deep")]
        doctor = doctor_ok(std={"ok": False, "kind": "auth", "detail": "bad key"})
        got = run_groups(cs, "opencode", doctor=doctor)
        self.assertEqual(shape(got), [
            ("O01", "oc:lite", ["T01"]),
            ("T02", "held", ["T02"]),
            ("T03", "held", ["T03"]),
        ])

    def test_open_breaker_holds_in_opencode_and_falls_back_in_hybrid(self):
        cs = [C("T01"), C("T02")]
        breaker_dir = Path(self.tmp.name)
        with mock.patch.object(hybrid_shared, "breaker_open",
                               return_value={"kind": "auth", "detail": "bad key"}):
            got = run_groups(cs, "opencode", breaker_dir=breaker_dir)
            self.assertEqual(shape(got), [("T01", "held", ["T01"]), ("T02", "held", ["T02"])])
            got = run_groups(cs, "hybrid", breaker_dir=breaker_dir)
            self.assertEqual(shape(got), [("T01", "claude", ["T01"]), ("T02", "claude", ["T02"])])

    def small_tier(self, **extra):
        routing = copy.deepcopy(ROUTING)
        routing["tiers"]["std"]["max_parallel"] = 1
        routing["oc_group_max"] = 2
        routing.update(extra)
        return routing

    def heavy_tasks(self):
        cs = [C("T01"), C("T02"), C("T03", spec=((1, 300),)), C("T04", spec=((1, 60),))]
        self.assertGreater(plan_tool.weight(cs[2]), plan_tool.weight(cs[3]))
        self.assertGreater(plan_tool.weight(cs[3]), plan_tool.weight(cs[0]))
        return cs

    def test_overflow_moves_heaviest_to_claude_when_oc_overflow_is_claude(self):
        got = run_groups(self.heavy_tasks(), "hybrid", routing=self.small_tier(oc_overflow="claude"))
        self.assertEqual(shape(got), [
            ("T03", "claude", ["T03"]),
            ("T04", "claude", ["T04"]),
            ("O01", "oc:std", ["T01", "T02"]),
        ])

    def test_hybrid_overflow_is_queued_on_opencode_by_default(self):
        got = run_groups(self.heavy_tasks(), "hybrid", routing=self.small_tier())
        self.assertEqual({backend for _, backend, _ in got}, {"oc:std"})
        self.assertEqual(sorted(c["id"] for _, _, g in got for c in g), ["T01", "T02", "T03", "T04"])
        self.assertEqual(len(got), 2)  # ceil(4 / oc_group_max); max_parallel 1 so the second group waits for the slot

    def test_max_parallel_above_8_is_clamped_to_8_groups(self):
        routing = copy.deepcopy(ROUTING)
        routing["tiers"]["std"]["max_parallel"] = 40
        routing["oc_group_max"] = 1
        got = run_groups([C("T%02d" % i) for i in range(1, 21)], "hybrid", routing=routing)
        self.assertEqual(hp_partition._max_parallel(routing, "std"), 8)
        self.assertEqual(len(got), 20)  # one task per group; at most 8 run at once, the rest queue

    def test_hybrid_default_with_more_than_18_std_tasks_sends_all_to_opencode(self):
        cs = [C("T%02d" % i) for i in range(1, 31)]
        got = run_groups(cs, "hybrid")
        self.assertEqual({backend for _, backend, _ in got}, {"oc:std"})
        self.assertEqual(sorted(c["id"] for _, _, g in got for c in g), [c["id"] for c in cs])
        self.assertEqual(len(got), 10)  # 30 / oc_group_max 3; 6 slots, so 4 groups queue
        self.assertTrue(all(len(g) <= 3 for _, _, g in got))

    def test_oc_overflow_claude_restores_the_old_split_beyond_18_tasks(self):
        cs = [C("T%02d" % i) for i in range(1, 21)]
        got = run_groups(cs, "hybrid", routing=dict(ROUTING, oc_overflow="claude"))
        on_oc = [c["id"] for _, backend, g in got if backend == "oc:std" for c in g]
        on_claude = [c["id"] for _, backend, g in got if backend == "claude" for c in g]
        self.assertEqual((len(on_oc), len(on_claude)), (18, 2))

    def test_tasks_within_capacity_are_unchanged_by_oc_overflow(self):
        cs = [C("T%02d" % i) for i in range(1, 19)]
        queued, split = run_groups(cs, "hybrid"), run_groups(cs, "hybrid", routing=dict(ROUTING, oc_overflow="claude"))
        self.assertEqual(shape(queued), shape(split))
        self.assertEqual({backend for _, backend, _ in queued}, {"oc:std"})
        self.assertEqual(len(queued), 6)

    def test_unusable_tier_still_routes_to_claude_whatever_oc_overflow_says(self):
        cs = [C("T%02d" % i) for i in range(1, 25)]
        doctor = doctor_ok(std={"ok": False, "kind": "auth", "detail": "bad key"})
        got = run_groups(cs, "hybrid", doctor=doctor)
        self.assertEqual({backend for _, backend, _ in got}, {"claude"})

    def test_invalid_oc_overflow_value_queues(self):
        got = run_groups(self.heavy_tasks(), "hybrid", routing=self.small_tier(oc_overflow="bogus"))
        self.assertEqual({backend for _, backend, _ in got}, {"oc:std"})

    def test_opencode_overflow_stays_on_opencode_in_groups_capped_by_oc_group_max(self):
        for overflow in ("queue", "claude"):
            with self.subTest(oc_overflow=overflow):
                got = run_groups(self.heavy_tasks(), "opencode", routing=self.small_tier(oc_overflow=overflow))
                self.assertEqual({backend for _, backend, _ in got}, {"oc:std"})
                self.assertEqual(sorted(c["id"] for _, _, g in got for c in g), ["T01", "T02", "T03", "T04"])
                self.assertEqual(len(got), 2)


if __name__ == "__main__":
    unittest.main()
