import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hp_partition  # noqa: E402
import plan_tool  # noqa: E402

ROUTING = {
    "preset": "hybrid",
    "tiers": {
        "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "max_parallel": 6, "stall_s": 180, "timeout_s": 900},
        "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low", "max_parallel": 6, "stall_s": 120, "timeout_s": 600},
    },
    "roles": {"light": "lite", "std": "std", "deep": "claude"},
    "max_roles": {"deep": "std"},
    "review_oc": {"hybrid": "all", "max": "risky"},
    "oc_group_max": 3,
    "max_repairs": 2,
    "throttle_cooldown_s": 120,
}


def doctor_ok():
    tier = {"listed": True, "ping": "ok", "note": "", "down": None}
    return {
        "t": "2026-09-28T10:00:00Z", "ok": True, "version": "2.0.18", "binary": "opencode",
        "tiers": {
            "std": dict(tier, model="zai-coding-plan/glm-5.3", variant="high"),
            "lite": dict(tier, model="zai-coding-plan/glm-5.3-flash", variant="low"),
        },
    }


def C(tid, tier="std", spec=((1, 1),), files=1, produces=0):
    return {
        "id": tid, "tier": tier, "spec": list(spec),
        "files": ["pkg/%s_%d.py" % (tid.lower(), i) for i in range(files)],
        "produces": ["def p%d_%s()" % (i, tid.lower()) for i in range(produces)],
    }


def shape(groups):
    return [(gid, backend, [c["id"] for c in g]) for gid, backend, g in groups]


class RouteGroupsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        env = {
            "HOME": t,
            "HP_ROUTING": os.path.join(t, "routing.json"),
            "HP_DOCTOR_CACHE": os.path.join(t, "doctor.json"),
            "HP_TELEMETRY": os.path.join(t, "lanes.jsonl"),
        }
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_claude_preset_matches_62_partition(self):
        cs = [C("T01"), C("T02"), C("T03")]
        got = hp_partition.route_groups(cs, ROUTING, doctor_ok(), "claude", 20)
        self.assertEqual(shape(got), [("T01", "claude", ["T01"]), ("T02", "claude", ["T02"]), ("T03", "claude", ["T03"])])
        got = hp_partition.route_groups(cs, ROUTING, doctor_ok(), "claude", 1)
        self.assertEqual(shape(got), [("W01", "claude", ["T01", "T02", "T03"])])
        self.assertEqual([g for _, _, g in got], plan_tool.partition(cs, 1))

    def test_hybrid_routes_by_tier_and_names_oc_groups_in_id_order(self):
        cs = [C("T01", "light"), C("T02", "deep"), C("T03", "std"), C("T04", "light")]
        got = hp_partition.route_groups(cs, ROUTING, doctor_ok(), "hybrid", 20)
        self.assertEqual(shape(got), [
            ("T02", "claude", ["T02"]),
            ("O01", "oc:lite", ["T01"]),
            ("O02", "oc:std", ["T03"]),
            ("O03", "oc:lite", ["T04"]),
        ])

    def test_max_preset_sends_deep_to_std(self):
        got = hp_partition.route_groups([C("T01", "deep")], ROUTING, doctor_ok(), "max", 20)
        self.assertEqual(shape(got), [("O01", "oc:std", ["T01"])])

    def test_no_doctor_cache_means_all_claude(self):
        cs = [C("T01", "light"), C("T02", "std")]
        got = hp_partition.route_groups(cs, ROUTING, {}, "hybrid", 20)
        self.assertEqual(shape(got), [("T01", "claude", ["T01"]), ("T02", "claude", ["T02"])])

    def test_overflow_moves_heaviest_to_claude(self):
        routing = copy.deepcopy(ROUTING)
        routing["tiers"]["std"]["max_parallel"] = 1
        routing["oc_group_max"] = 2
        cs = [C("T01"), C("T02"), C("T03", spec=((1, 300),)), C("T04", spec=((1, 60),))]
        self.assertGreater(plan_tool.weight(cs[2]), plan_tool.weight(cs[3]))
        self.assertGreater(plan_tool.weight(cs[3]), plan_tool.weight(cs[0]))
        got = hp_partition.route_groups(cs, routing, doctor_ok(), "hybrid", 20)
        self.assertEqual(shape(got), [
            ("T03", "claude", ["T03"]),
            ("T04", "claude", ["T04"]),
            ("O01", "oc:std", ["T01", "T02"]),
        ])


if __name__ == "__main__":
    unittest.main()
