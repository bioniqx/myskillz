import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ha_router  # noqa: E402
import hybrid_shared  # noqa: E402

SKILL = Path(__file__).resolve().parents[1]
DEFAULTS = SKILL / "routing.default.json"
NOW = 1800000000.0

EXPECTED_DEFAULTS = {
    "preset": "hybrid",
    "tiers": {
        "std": {"max_parallel": 4, "stall_s": 180, "timeout_s": 900},
        "lite": {"max_parallel": 4, "stall_s": 120, "timeout_s": 600},
    },
    "roles": {"investigator": "std", "verifier": "claude", "parser": "std"},
    "max_roles": {"verifier": "std", "parser": "std"},
    "oc_batch_max": 4,
    "oc_overflow": "queue",
    "max_repairs": 2,
    "throttle_cooldown_s": 120,
}

SHARED = {
    "tiers": {
        "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high"},
        "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low"},
    }
}
SHARED_VARS = {
    hybrid_shared.STD_ENV: hybrid_shared.model_spec(SHARED["tiers"]["std"]),
    hybrid_shared.LITE_ENV: hybrid_shared.model_spec(SHARED["tiers"]["lite"]),
}


def make_routing():
    with open(str(DEFAULTS)) as f:
        routing = json.load(f)
    for name, tier in SHARED["tiers"].items():
        routing["tiers"][name].update(tier)
    return routing


def good_doctor(routing, checked_at=NOW):
    tiers = {}
    for name, tier in routing["tiers"].items():
        tiers[name] = {"ok": True, "key": hybrid_shared.cache_key(tier),
                       "checked_at": checked_at, "kind": "", "detail": ""}
    return {"tiers": tiers}


class TestLoadRouting(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        patcher = mock.patch.dict(os.environ, SHARED_VARS)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("HYBRID_OPENCODE_MAX_PARALLEL", None)

    def unset_shared(self, *names):
        for name in names or SHARED_VARS:
            os.environ.pop(name, None)

    def load(self, user=None):
        return ha_router.load_routing(DEFAULTS, user or self.tmp / "absent-routing.json")

    def test_constants(self):
        self.assertEqual(ha_router.PRESETS, ("claude", "hybrid", "opencode"))
        self.assertEqual(ha_router.ROLES, ("investigator", "verifier", "parser"))

    def test_shipped_defaults_exact(self):
        with open(str(DEFAULTS)) as f:
            self.assertEqual(json.load(f), EXPECTED_DEFAULTS)

    def test_shared_env_supplies_model_and_variant(self):
        routing = self.load()
        self.assertEqual(routing["tiers"]["std"]["model"], "zai-coding-plan/glm-5.3")
        self.assertEqual(routing["tiers"]["std"]["variant"], "high")
        self.assertEqual(routing["tiers"]["std"]["timeout_s"], 900)
        self.assertEqual(routing["tiers"]["lite"]["model"], "zai-coding-plan/glm-5.3-flash")
        self.assertEqual(routing["tiers"]["lite"]["variant"], "low")
        self.assertEqual(routing["model_sources"], {"std": "shared", "lite": "shared"})
        self.assertEqual(routing["config_problems"], [])
        self.assertEqual(routing["config_warnings"], [])

    def test_lite_defaults_to_std(self):
        self.unset_shared(hybrid_shared.LITE_ENV)
        routing = self.load()
        self.assertEqual(routing["tiers"]["lite"]["model"], SHARED["tiers"]["std"]["model"])
        self.assertEqual(routing["tiers"]["lite"]["variant"], SHARED["tiers"]["std"]["variant"])
        self.assertEqual(routing["model_sources"], {"std": "shared", "lite": "shared"})
        self.assertEqual(routing["config_problems"], [])

    def test_max_parallel_comes_from_the_defaults_and_the_user_file(self):
        routing = self.load()
        self.assertEqual(routing["tiers"]["std"]["max_parallel"], 4)
        self.assertEqual(routing["tiers"]["lite"]["max_parallel"], 4)
        user = self.tmp / "routing.json"
        user.write_text(json.dumps({"tiers": {"std": {"max_parallel": 2, "timeout_s": 1200}}}))
        routing = self.load(user)
        self.assertEqual(routing["tiers"]["std"]["max_parallel"], 2)
        self.assertEqual(routing["tiers"]["std"]["timeout_s"], 1200)
        self.assertEqual(routing["tiers"]["lite"]["max_parallel"], 4)

    def test_max_parallel_env_sits_between_the_user_file_and_the_defaults(self):
        os.environ["HYBRID_OPENCODE_MAX_PARALLEL"] = "3"
        routing = self.load()
        self.assertEqual([routing["tiers"][t]["max_parallel"] for t in ("std", "lite")], [3, 3])
        user = self.tmp / "routing.json"
        user.write_text(json.dumps({"tiers": {"std": {"max_parallel": 2}}}))
        routing = self.load(user)
        self.assertEqual([routing["tiers"][t]["max_parallel"] for t in ("std", "lite")], [2, 3])

    def test_user_file_deep_merged(self):
        user = self.tmp / "routing.json"
        user.write_text(json.dumps({
            "preset": "opencode",
            "tiers": {"std": {"stall_s": 60}, "big": {"stall_s": 5}},
            "roles": {"verifier": "std"},
            "max_repairs": 1,
        }))
        routing = self.load(user)
        self.assertEqual(routing["preset"], "opencode")
        self.assertEqual(routing["tiers"]["std"]["stall_s"], 60)
        self.assertEqual(routing["tiers"]["std"]["timeout_s"], 900)
        self.assertEqual(routing["tiers"]["lite"]["stall_s"], 120)
        self.assertEqual(routing["tiers"]["big"]["stall_s"], 5)
        self.assertEqual(routing["roles"],
                         {"investigator": "std", "verifier": "std", "parser": "std"})
        self.assertEqual(routing["max_repairs"], 1)
        self.assertEqual(routing["oc_batch_max"], 4)
        self.assertEqual(routing["config_problems"], [])

    def test_user_file_model_wins_over_shared_env(self):
        user = self.tmp / "routing.json"
        user.write_text(json.dumps(
            {"tiers": {"std": {"model": "own/model", "variant": "low", "stall_s": 77}}}))
        routing = self.load(user)
        self.assertEqual(routing["tiers"]["std"]["model"], "own/model")
        self.assertEqual(routing["tiers"]["std"]["variant"], "low")
        self.assertEqual(routing["tiers"]["std"]["stall_s"], 77)
        self.assertEqual(routing["tiers"]["lite"]["model"], "zai-coding-plan/glm-5.3-flash")
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "shared"})
        self.assertEqual(routing["config_warnings"], [])
        self.assertEqual(routing["config_problems"], [])

    def test_user_model_without_variant_gets_no_variant(self):
        user = self.tmp / "routing.json"
        user.write_text(json.dumps({"tiers": {"std": {"model": "own/model"}}}))
        routing = self.load(user)
        self.assertEqual(routing["tiers"]["std"]["model"], "own/model")
        self.assertNotIn("variant", routing["tiers"]["std"])

    def test_tier_with_no_model_anywhere_is_a_config_problem(self):
        self.unset_shared()
        user = self.tmp / "routing.json"
        user.write_text(json.dumps({"tiers": {"std": {"model": "own/model"}}}))
        routing = self.load(user)
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "none"})
        self.assertNotIn("model", routing["tiers"]["lite"])
        self.assertTrue(any("lite" in p and str(user) in p and hybrid_shared.SHARED_SOURCE in p
                            for p in routing["config_problems"]))

    def test_wrong_typed_numbers_are_config_problems_not_crashes(self):
        user = self.tmp / "routing.json"
        user.write_text(json.dumps({"oc_batch_max": "four", "max_repairs": True,
                                    "tiers": {"std": {"max_parallel": "six", "timeout_s": "soon", "stall_s": 90}}}))
        routing = self.load(user)
        text = " ".join(routing["config_problems"])
        for key in ("oc_batch_max", "max_repairs", "tiers.std.max_parallel", "tiers.std.timeout_s"):
            self.assertIn(key, text)
        self.assertEqual(routing["oc_batch_max"], 4)
        self.assertEqual(routing["tiers"]["std"]["stall_s"], 90)
        self.assertIsInstance(routing["tiers"]["std"]["max_parallel"], int)

    def test_oc_overflow_defaults_to_queue_and_accepts_claude(self):
        self.assertEqual(self.load()["oc_overflow"], "queue")
        user = self.tmp / "routing.json"
        user.write_text(json.dumps({"oc_overflow": "claude"}))
        routing = self.load(user)
        self.assertEqual(routing["oc_overflow"], "claude")
        self.assertEqual(routing["config_problems"], [])

    def test_bad_oc_overflow_is_a_config_problem_and_falls_back_to_queue(self):
        user = self.tmp / "routing.json"
        for bad in ("haiku", "Claude", True, 3, ["claude"], None):
            user.write_text(json.dumps({"oc_overflow": bad}))
            routing = self.load(user)
            self.assertEqual(routing["oc_overflow"], "queue", bad)
            self.assertEqual(len(routing["config_problems"]), 1, bad)
            self.assertIn("oc_overflow", routing["config_problems"][0])
            self.assertIn(str(user), routing["config_problems"][0])

    def test_oc_queues_overflow(self):
        queues = ha_router.oc_queues_overflow
        self.assertTrue(queues({"preset": "hybrid"}))
        self.assertTrue(queues({"preset": "hybrid", "oc_overflow": "queue"}))
        self.assertFalse(queues({"preset": "hybrid", "oc_overflow": "claude"}))
        self.assertFalse(queues({"preset": "hybrid", "oc_overflow": "claude"}, "hybrid"))
        self.assertTrue(queues({"preset": "hybrid", "oc_overflow": "claude"}, "opencode"))
        self.assertTrue(queues({"oc_overflow": "claude"}, "max"))

    def test_null_model_in_a_user_tier_is_not_a_problem(self):
        user = self.tmp / "routing.json"
        user.write_text(json.dumps({"tiers": {"std": {"model": None}}}))
        self.assertEqual(self.load(user)["config_problems"], [])

    def test_shared_problems_are_reported_only_when_a_tier_needs_them(self):
        self.unset_shared()
        user = self.tmp / "routing.json"
        user.write_text(json.dumps({"tiers": {
            "std": {"model": "own/model"}, "lite": {"model": "own/small"}}}))
        routing = self.load(user)
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "skill"})
        self.assertEqual(routing["config_problems"], [])
        user.write_text(json.dumps({"tiers": {"std": {"model": "own/model"}}}))
        routing = self.load(user)
        _, shared_problems = hybrid_shared.load_shared()
        self.assertTrue(shared_problems)
        for problem in shared_problems:
            self.assertIn(problem, routing["config_problems"])

    def test_unset_shared_env_is_reported(self):
        self.unset_shared()
        routing = self.load()
        self.assertIn("HYBRID_OPENCODE_STD is not set", routing["config_problems"])
        self.assertTrue(all(isinstance(p, str) for p in routing["config_problems"]))
        self.assertNotIn("model", routing["tiers"]["std"])
        self.assertEqual(routing["model_sources"], {"std": "none", "lite": "none"})
        self.assertEqual(routing["roles"], EXPECTED_DEFAULTS["roles"])

    def test_invalid_shared_env_is_reported(self):
        os.environ[hybrid_shared.STD_ENV] = "no-provider"
        routing = self.load()
        self.assertTrue(any(hybrid_shared.STD_ENV in p for p in routing["config_problems"]))
        self.assertTrue(all(isinstance(p, str) for p in routing["config_problems"]))

    def test_preset_max_in_the_user_file_gets_a_warning(self):
        user = self.tmp / "routing.json"
        user.write_text(json.dumps({"preset": "max"}))
        routing = self.load(user)
        self.assertEqual(len(routing["config_warnings"]), 1)
        self.assertIn("max", routing["config_warnings"][0])
        self.assertEqual(routing["config_problems"], [])
        self.assertEqual(ha_router.effective_preset(routing), "opencode")

    def test_wrong_typed_tiers_in_user_file_keep_defaults_and_report(self):
        user = self.tmp / "routing.json"
        for bad in ([1], "x"):
            user.write_text(json.dumps({"tiers": bad}))
            routing = self.load(user)
            self.assertEqual(routing["tiers"]["std"]["timeout_s"], 900)
            self.assertTrue(any(str(user) in p for p in routing["config_problems"]))

    def test_wrong_typed_tier_entry_keeps_defaults_and_names_the_key(self):
        user = self.tmp / "routing.json"
        user.write_text(json.dumps({"tiers": {"std": "x"}}))
        routing = self.load(user)
        self.assertEqual(routing["tiers"]["std"]["stall_s"], 180)
        self.assertEqual(routing["tiers"]["std"]["timeout_s"], 900)
        self.assertTrue(any(str(user) in p and "tiers.std" in p
                            for p in routing["config_problems"]))

    def test_wrong_typed_tier_model_is_reported_and_not_used(self):
        user = self.tmp / "routing.json"
        user.write_text(json.dumps({"tiers": {"std": {"model": 5}}}))
        routing = self.load(user)
        self.assertTrue(any(str(user) in p for p in routing["config_problems"]))
        self.assertNotEqual(routing["model_sources"]["std"], "skill")

    def test_malformed_user_file_is_reported(self):
        bad = self.tmp / "bad.json"
        bad.write_text("{not json")
        routing = self.load(bad)
        self.assertEqual(routing["roles"], EXPECTED_DEFAULTS["roles"])
        self.assertEqual(len(routing["config_problems"]), 1)
        self.assertIn(str(bad), routing["config_problems"][0])
        lst = self.tmp / "list.json"
        lst.write_text("[1, 2]")
        routing = self.load(lst)
        self.assertEqual(len(routing["config_problems"]), 1)
        self.assertIn(str(lst), routing["config_problems"][0])


class TestUserRoutingPath(unittest.TestCase):
    def test_user_routing_path_env_override(self):
        with mock.patch.dict(os.environ, {"HYBRID_AUDIT_ROUTING": "/tmp/x/routing.json"}):
            self.assertEqual(ha_router.user_routing_path(), Path("/tmp/x/routing.json"))

    def test_user_routing_path_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env.pop("HYBRID_AUDIT_ROUTING", None)
            env["HOME"] = tmp
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(ha_router.user_routing_path(), SKILL / "routing.json")

    def test_user_routing_path_default_is_next_to_shipped_defaults(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("HYBRID_AUDIT_ROUTING", None)
            self.assertEqual(ha_router.user_routing_path().parent, DEFAULTS.parent)


class TestPresetAndRoleTier(unittest.TestCase):
    def test_effective_preset_argument_wins(self):
        routing = make_routing()
        self.assertEqual(ha_router.effective_preset(routing, "opencode"), "opencode")
        self.assertEqual(ha_router.effective_preset(routing, "claude"), "claude")

    def test_max_is_an_alias_of_opencode(self):
        routing = make_routing()
        self.assertEqual(ha_router.effective_preset(routing, "max"), "opencode")
        routing["preset"] = "max"
        self.assertEqual(ha_router.effective_preset(routing), "opencode")

    def test_effective_preset_from_routing(self):
        routing = make_routing()
        self.assertEqual(ha_router.effective_preset(routing), "hybrid")
        routing["preset"] = "opencode"
        self.assertEqual(ha_router.effective_preset(routing, ""), "opencode")

    def test_effective_preset_default_and_unknown(self):
        self.assertEqual(ha_router.effective_preset({}), "hybrid")
        with self.assertRaises(ValueError):
            ha_router.effective_preset({"preset": "turbo"})
        with self.assertRaises(ValueError):
            ha_router.effective_preset(make_routing(), "bogus")

    def test_role_tier_claude_preset(self):
        routing = make_routing()
        for role in ha_router.ROLES:
            self.assertEqual(ha_router.role_tier(role, routing, "claude"), "claude")

    def test_role_tier_hybrid(self):
        routing = make_routing()
        self.assertEqual(ha_router.role_tier("investigator", routing, "hybrid"), "std")
        self.assertEqual(ha_router.role_tier("verifier", routing, "hybrid"), "claude")
        self.assertEqual(ha_router.role_tier("parser", routing, "hybrid"), "std")
        self.assertEqual(ha_router.role_tier("investigator", routing), "std")

    def test_role_tier_opencode(self):
        routing = make_routing()
        self.assertEqual(ha_router.role_tier("investigator", routing, "opencode"), "std")
        self.assertEqual(ha_router.role_tier("verifier", routing, "opencode"), "std")
        self.assertEqual(ha_router.role_tier("parser", routing, "opencode"), "std")
        routing["max_roles"] = {"verifier": "lite"}
        self.assertEqual(ha_router.role_tier("verifier", routing, "opencode"), "lite")
        self.assertEqual(ha_router.role_tier("parser", routing, "opencode"), "std")

    def test_role_tier_unknown_role_or_missing_roles(self):
        routing = make_routing()
        self.assertEqual(ha_router.role_tier("lead", routing, "hybrid"), "claude")
        self.assertEqual(ha_router.role_tier("investigator", {"preset": "hybrid"}), "claude")


class TestTierAvailable(unittest.TestCase):
    def setUp(self):
        self.routing = make_routing()

    def available(self, name, doctor, breaker_dir=None):
        return ha_router.tier_available(name, self.routing, doctor, NOW, breaker_dir)

    def test_good(self):
        doctor = good_doctor(self.routing)
        self.assertTrue(self.available("std", doctor))
        self.assertTrue(self.available("lite", doctor))

    def test_rejections(self):
        doctor = good_doctor(self.routing)
        self.assertFalse(self.available("std", {}))
        self.assertFalse(self.available("std", None))
        self.assertFalse(self.available("", doctor))
        self.assertFalse(self.available("big", doctor))
        del doctor["tiers"]["lite"]
        self.assertFalse(self.available("lite", doctor))

    def test_failed_entry_disables_only_its_tier(self):
        doctor = good_doctor(self.routing)
        doctor["tiers"]["std"]["ok"] = False
        doctor["tiers"]["std"]["kind"] = "auth"
        self.assertFalse(self.available("std", doctor))
        self.assertTrue(self.available("lite", doctor))

    def test_stale_entry(self):
        self.assertFalse(self.available("std", good_doctor(self.routing, checked_at=1.0)))

    def test_key_mismatch_after_model_change(self):
        doctor = good_doctor(self.routing)
        self.routing["tiers"]["std"]["model"] = "other/model"
        self.assertFalse(self.available("std", doctor))
        self.assertTrue(self.available("lite", doctor))

    def test_tier_without_model(self):
        doctor = good_doctor(self.routing)
        del self.routing["tiers"]["std"]["model"]
        self.assertFalse(self.available("std", doctor))

    def test_default_now_uses_current_time(self):
        doctor = good_doctor(self.routing, checked_at=time.time())
        self.assertTrue(ha_router.tier_available("std", self.routing, doctor))

    def test_open_breaker_disables_tier(self):
        doctor = good_doctor(self.routing)
        breaker_dir = Path("unused-breaker-dir")
        spec = hybrid_shared.model_spec(self.routing["tiers"]["std"])
        with mock.patch.object(hybrid_shared, "breaker_open",
                               return_value={"kind": "auth"}) as opened:
            self.assertFalse(self.available("std", doctor, breaker_dir))
        opened.assert_called_once_with(breaker_dir, "std", spec)

    def test_closed_breaker_keeps_tier(self):
        doctor = good_doctor(self.routing)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(self.available("std", doctor, Path(tmp)))

    def test_no_breaker_dir_skips_the_breaker(self):
        doctor = good_doctor(self.routing)
        with mock.patch.object(hybrid_shared, "breaker_open") as opened:
            self.assertTrue(self.available("std", doctor))
        opened.assert_not_called()


class TestRoute(unittest.TestCase):
    def setUp(self):
        self.routing = make_routing()
        self.doctor = good_doctor(self.routing)

    def route(self, role, preset="", doctor=None, cooldown=None, now=NOW, breaker_dir=None):
        doctor = self.doctor if doctor is None else doctor
        return ha_router.route(role, self.routing, doctor, preset, cooldown, now, breaker_dir)

    def test_route_hybrid(self):
        self.assertEqual(self.route("investigator"), "oc:std")
        self.assertEqual(self.route("verifier"), "claude")
        self.assertEqual(self.route("parser", "hybrid"), "oc:std")

    def test_route_opencode(self):
        for role in ha_router.ROLES:
            self.assertEqual(self.route(role, "opencode"), "oc:std")

    def test_route_max_alias_routes_like_opencode(self):
        self.assertEqual(self.route("verifier", "max"), "oc:std")

    def test_route_preset_claude_needs_no_doctor(self):
        for role in ha_router.ROLES:
            self.assertEqual(self.route(role, "claude", doctor={}), "claude")

    def test_route_preset_from_routing_file(self):
        self.routing["preset"] = "claude"
        self.assertEqual(self.route("investigator"), "claude")
        self.routing["preset"] = "opencode"
        self.assertEqual(self.route("verifier"), "oc:std")

    def test_route_unknown_preset_raises(self):
        with self.assertRaises(ValueError):
            self.route("investigator", "bogus")

    def test_hybrid_falls_back_to_claude(self):
        stale = good_doctor(self.routing, checked_at=1.0)
        failed = good_doctor(self.routing)
        failed["tiers"]["std"]["ok"] = False
        for doctor in ({}, stale, failed):
            self.assertEqual(self.route("investigator", "hybrid", doctor=doctor), "claude")

    def test_opencode_holds_instead_of_falling_back(self):
        stale = good_doctor(self.routing, checked_at=1.0)
        failed = good_doctor(self.routing)
        failed["tiers"]["std"]["ok"] = False
        for doctor in ({}, stale, failed):
            for role in ha_router.ROLES:
                self.assertEqual(self.route(role, "opencode", doctor=doctor), "held")

    def test_open_breaker_falls_back_or_holds(self):
        with mock.patch.object(hybrid_shared, "breaker_open", return_value={"kind": "quota"}):
            self.assertEqual(
                self.route("investigator", "hybrid", breaker_dir=Path("unused-breaker-dir")),
                "claude")
            self.assertEqual(
                self.route("investigator", "opencode", breaker_dir=Path("unused-breaker-dir")),
                "held")

    def test_switched_hybrid_run_routes_every_role_to_claude(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.route("investigator", "hybrid", breaker_dir=Path(tmp)), "oc:std")
            hybrid_shared.switch_to_claude(Path(tmp), "batch-01", "std", "m/x", "auth", "401")
            for role in ha_router.ROLES:
                self.assertEqual(self.route(role, "hybrid", breaker_dir=Path(tmp)), "claude")
            self.assertEqual(self.route("investigator", "opencode", breaker_dir=Path(tmp)), "oc:std")

    def test_missing_tier_definition(self):
        self.routing["roles"]["investigator"] = "gpu"
        self.assertEqual(self.route("investigator", "hybrid"), "claude")
        self.assertEqual(self.route("investigator", "opencode"), "held")

    def test_opencode_keeps_a_role_pinned_to_claude(self):
        self.routing["roles"]["investigator"] = "claude"
        self.assertEqual(self.route("investigator", "opencode"), "claude")

    def test_route_user_tier(self):
        self.routing["roles"]["investigator"] = "lite"
        self.assertEqual(self.route("investigator"), "oc:lite")

    def test_one_failed_tier_leaves_the_other(self):
        self.doctor["tiers"]["std"]["ok"] = False
        self.routing["roles"]["investigator"] = "lite"
        self.assertEqual(self.route("investigator", "opencode"), "oc:lite")
        self.assertEqual(self.route("verifier", "opencode"), "held")

    def test_route_cooldown(self):
        cooldown = {"std": NOW + 2.0}
        self.assertEqual(
            self.route("investigator", "hybrid", cooldown=cooldown, now=NOW + 1.0), "claude")
        self.assertEqual(
            self.route("investigator", "opencode", cooldown=cooldown, now=NOW + 1.0), "held")
        self.assertEqual(
            self.route("investigator", "hybrid", cooldown=cooldown, now=NOW + 2.0), "oc:std")
        self.assertEqual(
            self.route("investigator", "hybrid", cooldown={"lite": NOW + 999.0}, now=NOW + 1.0),
            "oc:std")
        self.assertEqual(
            self.route("investigator", "hybrid", cooldown=None, now=NOW + 5.0), "oc:std")

    def test_default_now_uses_current_time(self):
        doctor = good_doctor(self.routing, checked_at=time.time())
        self.assertEqual(ha_router.route("investigator", self.routing, doctor), "oc:std")


if __name__ == "__main__":
    unittest.main()
