import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hp_router  # noqa: E402
import hybrid_shared  # noqa: E402

DEFAULTS = Path(__file__).resolve().parents[1] / "routing.default.json"
NOW = 1800000000.0
STALE = 1000000000.0

EXPECTED_DEFAULTS = {
    "preset": "hybrid",
    "tiers": {
        "std": {"max_parallel": 6, "stall_s": 180, "timeout_s": 900},
        "lite": {"max_parallel": 6, "stall_s": 120, "timeout_s": 600},
    },
    "roles": {"light": "lite", "std": "std", "deep": "claude"},
    "max_roles": {"deep": "std"},
    "review_oc": {"hybrid": "all", "opencode": "risky"},
    "oc_group_max": 3,
    "max_repairs": 2,
    "throttle_cooldown_s": 120,
}

SHARED = {
    "HYBRID_OPENCODE_STD": "acme/std-model#high",
    "HYBRID_OPENCODE_LITE": "acme/lite-model",
}


def core(routing):
    return {k: v for k, v in routing.items()
            if k not in ("config_problems", "config_warnings", "model_sources")}


class _TempEnvCase(unittest.TestCase):
    def setUp(self):
        self._saved_env = dict(os.environ)
        self.tmp = Path(tempfile.mkdtemp())
        os.environ["HOME"] = str(self.tmp)
        os.environ["XDG_DATA_HOME"] = str(self.tmp / "data")
        os.environ.pop("HYBRID_OPENCODE_STD", None)
        os.environ.pop("HYBRID_OPENCODE_LITE", None)
        os.environ["HP_ROUTING"] = str(self.tmp / "routing.json")
        os.environ["HP_DOCTOR_CACHE"] = str(self.tmp / "doctor.json")
        os.environ["HP_TELEMETRY"] = str(self.tmp / "lanes.jsonl")

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_env)
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def write_user(self, data):
        path = self.tmp / "routing.json"
        path.write_text(data if isinstance(data, str) else json.dumps(data))
        return path

    def set_shared(self, env):
        os.environ.update(env)


class RoutingConfigTest(_TempEnvCase):
    def test_constants(self):
        self.assertEqual(hp_router.PRESETS, ("claude", "hybrid", "opencode"))
        self.assertEqual(hp_router.CONTRACT_TIERS, ("light", "std", "deep"))

    def test_default_file_is_exact(self):
        with open(str(DEFAULTS)) as f:
            self.assertEqual(json.load(f), EXPECTED_DEFAULTS)

    def test_user_routing_path_from_env(self):
        self.assertEqual(hp_router.user_routing_path(), self.tmp / "routing.json")

    def test_user_routing_path_default(self):
        del os.environ["HP_ROUTING"]
        self.assertEqual(hp_router.user_routing_path(), DEFAULTS.parent / "routing.json")

    def test_user_routing_path_default_ignores_home(self):
        del os.environ["HP_ROUTING"]
        os.environ["HOME"] = str(self.tmp / "other-home")
        path = hp_router.user_routing_path()
        self.assertEqual(path, DEFAULTS.parent / "routing.json")
        self.assertNotIn(str(self.tmp), str(path))

    def test_load_routing_without_shared_env_reports_it(self):
        routing = hp_router.load_routing(DEFAULTS, self.tmp / "missing.json")
        self.assertEqual(core(routing), EXPECTED_DEFAULTS)
        self.assertEqual(routing["config_warnings"], [])
        self.assertEqual(routing["model_sources"], {"std": "none", "lite": "none"})
        self.assertTrue(any("HYBRID_OPENCODE_STD is not set" in p for p in routing["config_problems"]))

    def test_load_routing_applies_shared_env(self):
        self.set_shared(SHARED)
        routing = hp_router.load_routing(DEFAULTS, self.tmp / "missing.json")
        self.assertEqual(routing["config_problems"], [])
        self.assertEqual(routing["config_warnings"], [])
        self.assertEqual(routing["model_sources"], {"std": "shared", "lite": "shared"})
        std = routing["tiers"]["std"]
        self.assertEqual(std["model"], "acme/std-model")
        self.assertEqual(std["variant"], "high")
        self.assertEqual(std["max_parallel"], 6)
        self.assertEqual(std["timeout_s"], 900)
        self.assertEqual(routing["tiers"]["lite"]["model"], "acme/lite-model")
        self.assertNotIn("variant", routing["tiers"]["lite"])
        self.assertEqual(routing["tiers"]["lite"]["timeout_s"], 600)

    def test_lite_defaults_to_std_when_only_std_is_set(self):
        self.set_shared({"HYBRID_OPENCODE_STD": "acme/std-model#high"})
        routing = hp_router.load_routing(DEFAULTS, self.tmp / "missing.json")
        self.assertEqual(routing["config_problems"], [])
        self.assertEqual(routing["model_sources"], {"std": "shared", "lite": "shared"})
        self.assertEqual(routing["tiers"]["lite"]["model"], "acme/std-model")
        self.assertEqual(routing["tiers"]["lite"]["variant"], "high")

    def test_load_routing_reports_invalid_shared_env(self):
        self.set_shared({"HYBRID_OPENCODE_STD": "no-provider"})
        routing = hp_router.load_routing(DEFAULTS, self.tmp / "missing.json")
        self.assertTrue(any("HYBRID_OPENCODE_STD must be" in p for p in routing["config_problems"]))
        self.set_shared({"HYBRID_OPENCODE_STD": "acme/std-model", "HYBRID_OPENCODE_LITE": "bad model"})
        routing = hp_router.load_routing(DEFAULTS, self.tmp / "missing.json")
        self.assertTrue(any("HYBRID_OPENCODE_LITE must be" in p for p in routing["config_problems"]))

    def test_load_routing_deep_merges_user_file(self):
        self.set_shared(SHARED)
        user = self.write_user({
            "preset": "opencode",
            "tiers": {"std": {"timeout_s": 50}, "big": {"stall_s": 7}},
            "roles": {"std": "big"},
        })
        routing = hp_router.load_routing(DEFAULTS, user)
        self.assertEqual(routing["preset"], "opencode")
        self.assertEqual(routing["tiers"]["std"]["timeout_s"], 50)
        self.assertEqual(routing["tiers"]["std"]["stall_s"], 180)
        self.assertEqual(routing["tiers"]["std"]["model"], "acme/std-model")
        self.assertEqual(routing["tiers"]["big"]["stall_s"], 7)
        self.assertEqual(routing["tiers"]["lite"]["timeout_s"], 600)
        self.assertEqual(routing["roles"], {"light": "lite", "std": "big", "deep": "claude"})
        self.assertEqual(routing["max_repairs"], 2)
        self.assertEqual(routing["model_sources"], {"std": "shared", "lite": "shared"})
        self.assertEqual(routing["config_problems"], [])
        self.assertEqual(routing["config_warnings"], [])

    def test_skill_file_model_wins_per_tier(self):
        self.set_shared(SHARED)
        user = self.write_user({"tiers": {
            "std": {"model": "own/std-model", "variant": "max", "timeout_s": 50},
        }})
        routing = hp_router.load_routing(DEFAULTS, user)
        std = routing["tiers"]["std"]
        self.assertEqual(std["model"], "own/std-model")
        self.assertEqual(std["variant"], "max")
        self.assertEqual(std["timeout_s"], 50)
        self.assertEqual(std["max_parallel"], 6)
        self.assertEqual(routing["tiers"]["lite"]["model"], "acme/lite-model")
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "shared"})
        self.assertEqual(routing["config_problems"], [])
        self.assertEqual(routing["config_warnings"], [])

    def test_skill_model_without_variant_gets_no_variant(self):
        self.set_shared(SHARED)
        user = self.write_user({"tiers": {"std": {"model": "own/std-model"}}})
        routing = hp_router.load_routing(DEFAULTS, user)
        self.assertEqual(routing["tiers"]["std"]["model"], "own/std-model")
        self.assertNotIn("variant", routing["tiers"]["std"])

    def test_tier_without_skill_model_takes_shared_model_and_variant(self):
        self.set_shared(SHARED)
        user = self.write_user({"tiers": {"std": {"timeout_s": 50}}})
        routing = hp_router.load_routing(DEFAULTS, user)
        self.assertEqual(routing["tiers"]["std"]["model"], "acme/std-model")
        self.assertEqual(routing["tiers"]["std"]["variant"], "high")
        self.assertEqual(routing["model_sources"], {"std": "shared", "lite": "shared"})

    def test_tier_with_no_model_anywhere_is_a_config_problem(self):
        user = self.write_user({"tiers": {"std": {"model": "own/std-model"}}})
        routing = hp_router.load_routing(DEFAULTS, user)
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "none"})
        self.assertNotIn("model", routing["tiers"]["lite"])
        self.assertTrue(any(
            "lite" in p and str(user) in p and hybrid_shared.SHARED_SOURCE in p
            for p in routing["config_problems"]))

    def test_max_parallel_prefers_skill_file_then_defaults(self):
        self.set_shared(SHARED)
        routing = hp_router.load_routing(DEFAULTS, self.tmp / "missing.json")
        self.assertEqual(routing["tiers"]["std"]["max_parallel"], 6)
        self.assertEqual(routing["tiers"]["lite"]["max_parallel"], 6)
        user = self.write_user({"tiers": {"std": {"max_parallel": 2}}})
        routing = hp_router.load_routing(DEFAULTS, user)
        self.assertEqual(routing["tiers"]["std"]["max_parallel"], 2)
        self.assertEqual(routing["tiers"]["lite"]["max_parallel"], 6)

    def test_shared_problems_are_reported_only_when_a_tier_needs_them(self):
        user = self.write_user({"tiers": {
            "std": {"model": "own/std-model"},
            "lite": {"model": "own/lite-model"},
        }})
        routing = hp_router.load_routing(DEFAULTS, user)
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "skill"})
        self.assertEqual(routing["config_problems"], [])
        user = self.write_user({"tiers": {"std": {"model": "own/std-model"}}})
        routing = hp_router.load_routing(DEFAULTS, user)
        _, shared_problems = hybrid_shared.load_shared()
        self.assertTrue(shared_problems)
        for problem in shared_problems:
            self.assertIn(problem, routing["config_problems"])

    def test_load_routing_reports_broken_user_file(self):
        self.set_shared(SHARED)
        for content in ("{not json", [1, 2, 3]):
            user = self.write_user(content)
            routing = hp_router.load_routing(DEFAULTS, user)
            self.assertEqual(routing["tiers"]["std"]["model"], "acme/std-model")
            self.assertEqual(routing["roles"], EXPECTED_DEFAULTS["roles"])
            self.assertEqual(len(routing["config_problems"]), 1)
            self.assertIn(str(user), routing["config_problems"][0])
            self.assertEqual(routing["config_warnings"], [])

    def test_wrong_typed_user_tiers_are_reported_and_ignored(self):
        self.set_shared(SHARED)
        for bad in ([1], "x"):
            user = self.write_user({"tiers": bad})
            routing = hp_router.load_routing(DEFAULTS, user)
            self.assertEqual(routing["tiers"]["std"]["timeout_s"], 900)
            self.assertTrue(any(str(user) in p for p in routing["config_problems"]))

    def test_wrong_typed_user_tier_entry_is_reported_and_ignored(self):
        self.set_shared(SHARED)
        user = self.write_user({"tiers": {"std": "x"}})
        routing = hp_router.load_routing(DEFAULTS, user)
        self.assertEqual(routing["tiers"]["std"]["stall_s"], 180)
        self.assertEqual(routing["tiers"]["std"]["timeout_s"], 900)
        self.assertTrue(any(str(user) in p and "tiers.std" in p for p in routing["config_problems"]))

    def test_preset_max_in_user_file_warns(self):
        self.set_shared(SHARED)
        routing = hp_router.load_routing(DEFAULTS, self.write_user({"preset": "max"}))
        self.assertEqual(len(routing["config_warnings"]), 1)
        self.assertIn("deprecated name of 'opencode'", routing["config_warnings"][0])
        self.assertNotIn("running as", routing["config_warnings"][0])  # it must not claim what the run will do
        routing = hp_router.load_routing(DEFAULTS, self.write_user({"preset": " MAX "}))
        self.assertEqual(len(routing["config_warnings"]), 1)  # case-insensitive like mode_to_preset
        routing = hp_router.load_routing(DEFAULTS, self.write_user({"preset": "opencode"}))
        self.assertEqual(routing["config_warnings"], [])

    def test_wrong_typed_roles_and_bogus_preset_are_config_problems_not_crashes(self):
        self.set_shared(SHARED)
        for user_data, key in (({"roles": ["std"]}, "roles"), ({"max_roles": "x"}, "max_roles"),
                               ({"review_oc": [1]}, "review_oc"), ({"roles": {"std": ["x"]}}, "roles.std"),
                               ({"preset": "bogus"}, "preset"), ({"preset": 5}, "preset")):
            with self.subTest(user=user_data):
                user = self.write_user(user_data)
                routing = hp_router.load_routing(DEFAULTS, user)
                self.assertTrue(any(str(user) in p and key in p for p in routing["config_problems"]),
                                routing["config_problems"])
                self.assertEqual(hp_router.effective_preset(routing), "hybrid")
                self.assertEqual(routing["roles"]["std"], "std")
                self.assertIn(hp_router.route("std", routing, {}, "hybrid"), ("claude",))
                hp_router.review_policy(routing, "opencode")

    def test_disabled_tier_is_unavailable_whatever_the_doctor_says(self):
        self.set_shared(SHARED)
        routing = hp_router.load_routing(DEFAULTS, self.write_user({"tiers": {"std": {"disabled": True}}}))
        now = 1800000000.0
        doctor = {"ok": True, "tiers": {n: {"ok": True, "key": hybrid_shared.cache_key(routing["tiers"][n]),
                                            "checked_at": now} for n in ("std", "lite")}}
        self.assertEqual(hp_router.route("std", routing, doctor, "hybrid", now), "claude")
        self.assertEqual(hp_router.route("std", routing, doctor, "opencode", now), "held")
        self.assertEqual(hp_router.route("light", routing, doctor, "hybrid", now), "oc:lite")

    def test_review_oc_accepts_opencode_and_the_old_max_key(self):
        routing = {"review_oc": {"hybrid": "risky", "opencode": "all"}}
        self.assertEqual(hp_router.review_policy(routing, "opencode"), "all")
        routing = {"review_oc": {"max": "all"}}
        self.assertEqual(hp_router.review_policy(routing, "opencode"), "all")
        routing = {"review_oc": {"max": "all", "opencode": "risky"}}
        self.assertEqual(hp_router.review_policy(routing, "opencode"), "risky")

    def test_old_max_key_in_the_user_file_beats_the_shipped_opencode_default(self):
        self.set_shared(SHARED)
        routing = hp_router.load_routing(DEFAULTS, self.write_user({"review_oc": {"max": "all"}}))
        self.assertEqual(hp_router.review_policy(routing, "opencode"), "all")

    def test_effective_preset(self):
        routing = hp_router.load_routing(DEFAULTS, self.tmp / "missing.json")
        self.assertEqual(hp_router.effective_preset(routing), "hybrid")
        self.assertEqual(hp_router.effective_preset(routing, "opencode"), "opencode")
        self.assertEqual(hp_router.effective_preset(routing, "claude"), "claude")
        self.assertEqual(hp_router.effective_preset({}), "hybrid")
        self.assertEqual(hp_router.effective_preset({"preset": "opencode"}), "opencode")

    def test_effective_preset_max_is_an_alias_of_opencode(self):
        self.assertEqual(hp_router.effective_preset({}, "max"), "opencode")
        self.assertEqual(hp_router.effective_preset({"preset": "max"}), "opencode")

    def test_effective_preset_rejects_unknown_preset(self):
        with self.assertRaises(ValueError):
            hp_router.effective_preset({"preset": "turbo"})
        with self.assertRaises(ValueError):
            hp_router.effective_preset({}, "turbo")


def make_doctor(routing, *names, **overrides):
    tiers = {}
    for name in names:
        entry = {"ok": True, "key": hybrid_shared.cache_key(routing["tiers"][name]),
                 "checked_at": NOW, "kind": "", "detail": ""}
        entry.update(overrides.get(name, {}))
        tiers[name] = entry
    return {"tiers": tiers}


class RouterTest(_TempEnvCase):
    def setUp(self):
        super().setUp()
        self.set_shared(SHARED)
        self.routing = hp_router.load_routing(DEFAULTS, self.tmp / "missing.json")
        self.doctor = make_doctor(self.routing, "std", "lite")

    def route(self, tier, preset="", doctor=None, routing=None, breaker_dir=None):
        return hp_router.route(tier, routing or self.routing,
                               self.doctor if doctor is None else doctor,
                               preset, NOW, breaker_dir)

    def test_tier_available_true(self):
        self.assertTrue(hp_router.tier_available("std", self.routing, self.doctor, NOW))
        self.assertTrue(hp_router.tier_available("lite", self.routing, self.doctor, NOW))

    def test_tier_available_false_cases(self):
        self.assertFalse(hp_router.tier_available("std", self.routing, {}, NOW))
        self.assertFalse(hp_router.tier_available("", self.routing, self.doctor, NOW))
        ghost = {"tiers": {"ghost": {"ok": True, "key": "x", "checked_at": NOW,
                                     "kind": "", "detail": ""}}}
        self.assertFalse(hp_router.tier_available("ghost", self.routing, ghost, NOW))
        self.assertFalse(hp_router.tier_available("lite", self.routing,
                                                  make_doctor(self.routing, "std"), NOW))
        failed = make_doctor(self.routing, "std", "lite",
                             std={"ok": False, "kind": "auth", "detail": "bad key"})
        self.assertFalse(hp_router.tier_available("std", self.routing, failed, NOW))
        self.assertTrue(hp_router.tier_available("lite", self.routing, failed, NOW))

    def test_tier_available_needs_a_fresh_matching_entry(self):
        stale = make_doctor(self.routing, "std", std={"checked_at": STALE})
        self.assertFalse(hp_router.tier_available("std", self.routing, stale, NOW))
        wrong_key = make_doctor(self.routing, "std", std={"key": "another-model"})
        self.assertFalse(hp_router.tier_available("std", self.routing, wrong_key, NOW))

    def test_tier_without_model_is_unavailable(self):
        for name in ("HYBRID_OPENCODE_STD", "HYBRID_OPENCODE_LITE"):
            os.environ.pop(name, None)
        routing = hp_router.load_routing(DEFAULTS, self.tmp / "missing.json")
        doctor = {"tiers": {"std": {"ok": True, "key": "x", "checked_at": NOW,
                                    "kind": "", "detail": ""}}}
        self.assertFalse(hp_router.tier_available("std", routing, doctor, NOW))

    def test_open_breaker_makes_tier_unavailable(self):
        with mock.patch.object(hybrid_shared, "breaker_open",
                               return_value={"kind": "auth", "detail": "bad key"}):
            self.assertFalse(hp_router.tier_available("std", self.routing, self.doctor, NOW, self.tmp))
            self.assertEqual(self.route("std", "hybrid", breaker_dir=self.tmp), "claude")
            self.assertEqual(self.route("std", "opencode", breaker_dir=self.tmp), "held")
            self.assertEqual(self.route("std", "hybrid"), "oc:std")

    def test_closed_breaker_is_checked_with_tier_and_spec(self):
        spec = hybrid_shared.model_spec(self.routing["tiers"]["std"])
        with mock.patch.object(hybrid_shared, "breaker_open", return_value={}) as opened:
            self.assertTrue(hp_router.tier_available("std", self.routing, self.doctor, NOW, self.tmp))
        opened.assert_called_once_with(self.tmp, "std", spec)

    def test_route_hybrid(self):
        self.assertEqual(self.route("light"), "oc:lite")
        self.assertEqual(self.route("std"), "oc:std")
        self.assertEqual(self.route("deep"), "claude")

    def test_route_unknown_tier_is_std(self):
        self.assertEqual(self.route(""), "oc:std")
        self.assertEqual(self.route("huge"), "oc:std")

    def test_route_opencode(self):
        self.assertEqual(self.route("light", "opencode"), "oc:lite")
        self.assertEqual(self.route("std", "opencode"), "oc:std")
        self.assertEqual(self.route("deep", "opencode"), "oc:std")

    def test_route_max_is_an_alias_of_opencode(self):
        self.assertEqual(self.route("deep", "max"), "oc:std")

    def test_route_claude_preset_never_consults_doctor_or_breaker(self):
        with mock.patch.object(hybrid_shared, "breaker_open",
                               side_effect=AssertionError("breaker used")):
            for tier in hp_router.CONTRACT_TIERS:
                self.assertEqual(self.route(tier, "claude", doctor={}, breaker_dir=self.tmp), "claude")
                routing = dict(self.routing, preset="claude")
                self.assertEqual(self.route(tier, doctor={}, routing=routing, breaker_dir=self.tmp),
                                 "claude")

    def test_route_preset_argument_overrides_file(self):
        routing = dict(self.routing, preset="claude")
        self.assertEqual(self.route("std", "hybrid", routing=routing), "oc:std")
        self.assertEqual(self.route("deep", "opencode", routing=routing), "oc:std")

    def test_route_unknown_preset_raises(self):
        with self.assertRaises(ValueError):
            self.route("std", "turbo")

    def test_hybrid_falls_back_to_claude(self):
        for tier in hp_router.CONTRACT_TIERS:
            self.assertEqual(self.route(tier, "hybrid", doctor={}), "claude")
        failed = make_doctor(self.routing, "std", "lite",
                             std={"ok": False, "kind": "model", "detail": "model not found"})
        self.assertEqual(self.route("std", "hybrid", doctor=failed), "claude")
        self.assertEqual(self.route("light", "hybrid", doctor=failed), "oc:lite")

    def test_opencode_holds_when_no_usable_tier(self):
        for tier in hp_router.CONTRACT_TIERS:
            self.assertEqual(self.route(tier, "opencode", doctor={}), "held")
        failed = make_doctor(self.routing, "std", "lite",
                             std={"ok": False, "kind": "model", "detail": "model not found"})
        self.assertEqual(self.route("std", "opencode", doctor=failed), "held")
        self.assertEqual(self.route("deep", "opencode", doctor=failed), "held")
        self.assertEqual(self.route("light", "opencode", doctor=failed), "oc:lite")
        stale = make_doctor(self.routing, "std", "lite", std={"checked_at": STALE})
        self.assertEqual(self.route("std", "opencode", doctor=stale), "held")

    def test_route_missing_routing_tier(self):
        user = self.write_user({"roles": {"light": "ghost"}})
        routing = hp_router.load_routing(DEFAULTS, user)
        self.assertEqual(self.route("light", "hybrid", routing=routing), "claude")
        self.assertEqual(self.route("light", "opencode", routing=routing), "held")

    def test_route_user_role_remap(self):
        user = self.write_user({"roles": {"std": "lite"}})
        routing = hp_router.load_routing(DEFAULTS, user)
        self.assertEqual(self.route("std", "hybrid", routing=routing), "oc:lite")
        self.assertEqual(self.route("light", "hybrid", routing=routing), "oc:lite")

    def test_role_set_to_claude_is_kept_in_opencode_preset(self):
        user = self.write_user({"roles": {"std": "claude"}})
        routing = hp_router.load_routing(DEFAULTS, user)
        self.assertEqual(self.route("std", "opencode", routing=routing), "claude")

    def test_route_without_now_uses_the_clock(self):
        fresh = {"checked_at": time.time()}
        doctor = make_doctor(self.routing, "std", "lite", std=fresh, lite=fresh)
        self.assertEqual(hp_router.route("std", self.routing, doctor), "oc:std")

    def test_review_policy(self):
        self.assertEqual(hp_router.review_policy(self.routing), "all")
        self.assertEqual(hp_router.review_policy(self.routing, "hybrid"), "all")
        self.assertEqual(hp_router.review_policy(self.routing, "opencode"), "risky")
        self.assertEqual(hp_router.review_policy(self.routing, "claude"), "risky")
        custom = dict(self.routing, review_oc={"hybrid": "risky", "max": "all"})
        self.assertEqual(hp_router.review_policy(custom), "risky")
        self.assertEqual(hp_router.review_policy(custom, "opencode"), "all")
        broken = dict(self.routing, review_oc={"hybrid": "sometimes"})
        self.assertEqual(hp_router.review_policy(broken), "all")
        self.assertEqual(hp_router.review_policy(broken, "opencode"), "risky")
        self.assertEqual(hp_router.review_policy({}), "all")
