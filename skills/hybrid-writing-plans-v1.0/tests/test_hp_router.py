import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hp_router  # noqa: E402

DEFAULTS = Path(__file__).resolve().parents[1] / "routing.default.json"

EXPECTED_DEFAULTS = {
    "preset": "hybrid",
    "tiers": {
        "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "max_parallel": 6,
                "stall_s": 180, "timeout_s": 900},
        "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low", "max_parallel": 6,
                 "stall_s": 120, "timeout_s": 600},
    },
    "roles": {"light": "lite", "std": "std", "deep": "claude"},
    "max_roles": {"deep": "std"},
    "review_oc": {"hybrid": "all", "max": "risky"},
    "oc_group_max": 3,
    "max_repairs": 2,
    "throttle_cooldown_s": 120,
}


class _TempEnvCase(unittest.TestCase):
    def setUp(self):
        self._saved_env = dict(os.environ)
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["HOME"] = str(self.tmp)
        os.environ["HP_ROUTING"] = str(self.tmp / "routing.json")
        os.environ["HP_DOCTOR_CACHE"] = str(self.tmp / "doctor.json")
        os.environ["HP_TELEMETRY"] = str(self.tmp / "lanes.jsonl")

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_env)
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def write_user(self, data):
        path = self.tmp / "routing.json"
        if isinstance(data, str):
            path.write_text(data)
        else:
            path.write_text(json.dumps(data))
        return path


class RoutingConfigTest(_TempEnvCase):
    def test_constants(self):
        self.assertEqual(hp_router.PRESETS, ("claude", "hybrid", "max"))
        self.assertEqual(hp_router.CONTRACT_TIERS, ("light", "std", "deep"))

    def test_default_file_is_exact(self):
        with open(str(DEFAULTS)) as f:
            self.assertEqual(json.load(f), EXPECTED_DEFAULTS)

    def test_user_routing_path_from_env(self):
        self.assertEqual(hp_router.user_routing_path(), self.tmp / "routing.json")

    def test_user_routing_path_default(self):
        del os.environ["HP_ROUTING"]
        self.assertEqual(
            hp_router.user_routing_path(),
            self.tmp / ".config" / "hybrid-writing-plans" / "routing.json",
        )

    def test_load_routing_without_user_file(self):
        routing = hp_router.load_routing(DEFAULTS, self.tmp / "missing.json")
        self.assertEqual(routing, EXPECTED_DEFAULTS)

    def test_load_routing_deep_merges_user_file(self):
        user = self.write_user({
            "preset": "max",
            "tiers": {"std": {"variant": "max"}, "big": {"model": "acme/big", "variant": ""}},
            "roles": {"std": "big"},
        })
        routing = hp_router.load_routing(DEFAULTS, user)
        self.assertEqual(routing["preset"], "max")
        self.assertEqual(routing["tiers"]["std"]["model"], "zai-coding-plan/glm-5.3")
        self.assertEqual(routing["tiers"]["std"]["variant"], "max")
        self.assertEqual(routing["tiers"]["std"]["timeout_s"], 900)
        self.assertEqual(routing["tiers"]["big"], {"model": "acme/big", "variant": ""})
        self.assertEqual(routing["tiers"]["lite"], EXPECTED_DEFAULTS["tiers"]["lite"])
        self.assertEqual(routing["roles"], {"light": "lite", "std": "big", "deep": "claude"})
        self.assertEqual(routing["max_repairs"], 2)

    def test_load_routing_ignores_broken_user_file(self):
        user = self.write_user("{not json")
        self.assertEqual(hp_router.load_routing(DEFAULTS, user), EXPECTED_DEFAULTS)
        user = self.write_user([1, 2, 3])
        self.assertEqual(hp_router.load_routing(DEFAULTS, user), EXPECTED_DEFAULTS)

    def test_effective_preset(self):
        routing = hp_router.load_routing(DEFAULTS, self.tmp / "missing.json")
        self.assertEqual(hp_router.effective_preset(routing), "hybrid")
        self.assertEqual(hp_router.effective_preset(routing, "max"), "max")
        self.assertEqual(hp_router.effective_preset(routing, "claude"), "claude")
        self.assertEqual(hp_router.effective_preset({}), "hybrid")
        self.assertEqual(hp_router.effective_preset({"preset": "max"}), "max")
        self.assertEqual(hp_router.effective_preset({"preset": "turbo"}), "claude")
        self.assertEqual(hp_router.effective_preset(routing, "turbo"), "claude")


def make_doctor(*names, **overrides):
    tiers = {}
    for name in names:
        entry = {"model": "acme/" + name, "variant": "", "listed": True,
                 "ping": "ok", "note": "", "down": None}
        entry.update(overrides.get(name, {}))
        tiers[name] = entry
    return {"t": "2026-09-28T10:00:00Z", "ok": True, "version": "2.0.18",
            "binary": "opencode", "tiers": tiers}


class RouterTest(_TempEnvCase):
    def setUp(self):
        super().setUp()
        self.routing = hp_router.load_routing(DEFAULTS, self.tmp / "missing.json")
        self.doctor = make_doctor("std", "lite")

    def test_tier_available_true(self):
        self.assertTrue(hp_router.tier_available("std", self.routing, self.doctor))
        self.assertTrue(hp_router.tier_available("lite", self.routing, self.doctor))
        unchecked = make_doctor("std", std={"ping": "unchecked"})
        self.assertTrue(hp_router.tier_available("std", self.routing, unchecked))

    def test_tier_available_false_cases(self):
        self.assertFalse(hp_router.tier_available("std", self.routing, {}))
        not_ok = make_doctor("std")
        not_ok["ok"] = False
        self.assertFalse(hp_router.tier_available("std", self.routing, not_ok))
        self.assertFalse(hp_router.tier_available("ghost", self.routing, make_doctor("ghost")))
        self.assertFalse(hp_router.tier_available("lite", self.routing, make_doctor("std")))
        unlisted = make_doctor("std", std={"listed": False})
        self.assertFalse(hp_router.tier_available("std", self.routing, unlisted))
        failed = make_doctor("std", std={"ping": "failed"})
        self.assertFalse(hp_router.tier_available("std", self.routing, failed))
        down = make_doctor("std", std={"down": {"reason": "throttle", "message": "429",
                                                "at": "2026-09-28T10:05:00Z"}})
        self.assertFalse(hp_router.tier_available("std", self.routing, down))
        self.assertFalse(hp_router.tier_available("", self.routing, self.doctor))

    def test_route_hybrid(self):
        self.assertEqual(hp_router.route("light", self.routing, self.doctor), "oc:lite")
        self.assertEqual(hp_router.route("std", self.routing, self.doctor), "oc:std")
        self.assertEqual(hp_router.route("deep", self.routing, self.doctor), "claude")

    def test_route_unknown_tier_is_std(self):
        self.assertEqual(hp_router.route("", self.routing, self.doctor), "oc:std")
        self.assertEqual(hp_router.route("huge", self.routing, self.doctor), "oc:std")

    def test_route_max(self):
        self.assertEqual(hp_router.route("light", self.routing, self.doctor, "max"), "oc:lite")
        self.assertEqual(hp_router.route("std", self.routing, self.doctor, "max"), "oc:std")
        self.assertEqual(hp_router.route("deep", self.routing, self.doctor, "max"), "oc:std")

    def test_route_claude_preset(self):
        for tier in hp_router.CONTRACT_TIERS:
            self.assertEqual(hp_router.route(tier, self.routing, self.doctor, "claude"), "claude")
        routing = dict(self.routing, preset="claude")
        for tier in hp_router.CONTRACT_TIERS:
            self.assertEqual(hp_router.route(tier, routing, self.doctor), "claude")

    def test_route_preset_argument_overrides_file(self):
        routing = dict(self.routing, preset="claude")
        self.assertEqual(hp_router.route("std", routing, self.doctor, "hybrid"), "oc:std")
        self.assertEqual(hp_router.route("deep", routing, self.doctor, "max"), "oc:std")

    def test_route_falls_back_to_claude(self):
        for tier in hp_router.CONTRACT_TIERS:
            self.assertEqual(hp_router.route(tier, self.routing, {}, "max"), "claude")
        down = make_doctor("std", "lite", std={"down": {"reason": "unavailable",
                                                        "message": "model gone",
                                                        "at": "2026-09-28T10:05:00Z"}})
        self.assertEqual(hp_router.route("std", self.routing, down), "claude")
        self.assertEqual(hp_router.route("deep", self.routing, down, "max"), "claude")
        self.assertEqual(hp_router.route("light", self.routing, down), "oc:lite")

    def test_route_missing_routing_tier(self):
        user = self.write_user({"roles": {"light": "ghost"}})
        routing = hp_router.load_routing(DEFAULTS, user)
        doctor = make_doctor("std", "lite", "ghost")
        self.assertEqual(hp_router.route("light", routing, doctor), "claude")

    def test_route_user_tier(self):
        user = self.write_user({"tiers": {"big": {"model": "acme/big", "variant": "high"}},
                                "roles": {"std": "big"}})
        routing = hp_router.load_routing(DEFAULTS, user)
        doctor = make_doctor("std", "lite", "big")
        self.assertEqual(hp_router.route("std", routing, doctor), "oc:big")
        self.assertEqual(hp_router.route("light", routing, doctor), "oc:lite")

    def test_review_policy(self):
        self.assertEqual(hp_router.review_policy(self.routing), "all")
        self.assertEqual(hp_router.review_policy(self.routing, "hybrid"), "all")
        self.assertEqual(hp_router.review_policy(self.routing, "max"), "risky")
        self.assertEqual(hp_router.review_policy(self.routing, "claude"), "risky")
        custom = dict(self.routing, review_oc={"hybrid": "risky", "max": "all"})
        self.assertEqual(hp_router.review_policy(custom), "risky")
        self.assertEqual(hp_router.review_policy(custom, "max"), "all")
        broken = dict(self.routing, review_oc={"hybrid": "sometimes"})
        self.assertEqual(hp_router.review_policy(broken), "all")
        self.assertEqual(hp_router.review_policy(broken, "max"), "risky")
        self.assertEqual(hp_router.review_policy({}), "all")
