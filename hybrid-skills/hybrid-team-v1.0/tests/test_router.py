import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import router


SHIPPED_DEFAULTS = Path(__file__).resolve().parents[1] / "routing.default.json"

DEFAULT_ROUTING = {
    "preset": "hybrid",
    "tiers": {
        "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "max_parallel": 6,
                "stall_s": 180, "timeout_s": {"trivial": 600, "small": 1200, "large": 2400}},
        "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low", "max_parallel": 6,
                 "stall_s": 120, "timeout_s": {"trivial": 300, "small": 600, "large": 1200}},
    },
    "rows": {"code": "std", "refactor": "std", "test": "std", "chore": "std",
              "docs": "lite", "trivial": "lite"},
    "max_escalations": 1,
}

MODELS_ENV = {"HYBRID_OPENCODE_STD": "prov/std-model#high",
              "HYBRID_OPENCODE_LITE": "prov/lite-model#low"}


class RouterTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self._old_env = {key: os.environ.get(key)
                         for key in ("HOME", "HYBRID_TEAM_ROUTING", "HYBRID_OPENCODE_STD", "HYBRID_OPENCODE_LITE",
                                     "HYBRID_OPENCODE_MAX_PARALLEL")}
        os.environ["HOME"] = str(self.tmp_path)
        os.environ.pop("HYBRID_TEAM_ROUTING", None)
        os.environ.pop("HYBRID_OPENCODE_STD", None)
        os.environ.pop("HYBRID_OPENCODE_LITE", None)
        os.environ.pop("HYBRID_OPENCODE_MAX_PARALLEL", None)
        self.breaker_dir = self.tmp_path / "breaker"

    def tearDown(self):
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def routing(self, **overrides):
        routing = json.loads(json.dumps(DEFAULT_ROUTING))
        return router._merge(routing, overrides) if overrides else routing

    def set_shared(self, env=MODELS_ENV):
        os.environ.update(env)


class TestPresets(RouterTestCase):
    def test_presets_tuple(self):
        self.assertEqual(router.PRESETS, ("claude", "hybrid", "opencode"))


class TestUserRoutingPath(RouterTestCase):
    def test_default_next_to_shipped_defaults(self):
        self.assertEqual(router.user_routing_path(), SHIPPED_DEFAULTS.parent / "routing.json")

    def test_default_ignores_home(self):
        self.assertFalse(str(router.user_routing_path()).startswith(str(self.tmp_path)))

    def test_env_override(self):
        override = self.tmp_path / "custom" / "routing.json"
        os.environ["HYBRID_TEAM_ROUTING"] = str(override)
        self.assertEqual(router.user_routing_path(), override)


class TestDefaultRoutingFile(RouterTestCase):
    def test_no_model_variant_or_escalate_to(self):
        data = json.loads(SHIPPED_DEFAULTS.read_text())
        self.assertEqual(data["preset"], "hybrid")
        self.assertNotIn("escalate_to", data)
        for name, tier in data["tiers"].items():
            self.assertNotIn("model", tier, name)
            self.assertNotIn("variant", tier, name)


class TestLoadRouting(RouterTestCase):
    def write_defaults(self):
        defaults = json.loads(json.dumps(DEFAULT_ROUTING))
        for tier in defaults["tiers"].values():
            del tier["model"]
            del tier["variant"]
        path = self.tmp_path / "routing.default.json"
        path.write_text(json.dumps(defaults))
        return path

    def load(self, user_text=None, plan=None):
        self.user_path = self.tmp_path / "user-routing.json"
        if user_text is not None:
            self.user_path.write_text(user_text)
        return router.load_routing(self.write_defaults(), self.user_path, plan or {})

    def test_shared_env_supplies_model_and_variant(self):
        self.set_shared()
        routing = self.load()
        std = routing["tiers"]["std"]
        self.assertEqual(std["model"], "prov/std-model")
        self.assertEqual(std["variant"], "high")
        self.assertEqual(std["max_parallel"], 6)
        self.assertEqual(std["stall_s"], 180)
        self.assertEqual(routing["tiers"]["lite"]["model"], "prov/lite-model")
        self.assertEqual(routing["model_sources"], {"std": "shared", "lite": "shared"})
        self.assertEqual(routing["preset"], "hybrid")
        self.assertEqual(routing["config_problems"], [])
        self.assertEqual(routing["config_warnings"], [])

    def test_missing_shared_env_is_a_config_problem(self):
        routing = self.load()
        self.assertTrue(any("HYBRID_OPENCODE_STD is not set" in p for p in routing["config_problems"]))
        self.assertNotIn("model", routing["tiers"]["std"])
        self.assertEqual(routing["model_sources"], {"std": "none", "lite": "none"})
        self.assertEqual(routing["preset"], "hybrid")

    def test_invalid_shared_env_is_a_config_problem(self):
        self.set_shared({"HYBRID_OPENCODE_STD": "not-a-model"})
        routing = self.load()
        self.assertTrue(routing["config_problems"])

    def test_lite_defaults_to_the_std_model(self):
        self.set_shared({"HYBRID_OPENCODE_STD": "prov/std-model#high"})
        routing = self.load()
        self.assertEqual(routing["tiers"]["lite"]["model"], "prov/std-model")
        self.assertEqual(routing["tiers"]["lite"]["variant"], "high")
        self.assertEqual(routing["config_problems"], [])

    def test_user_file_overrides_non_model_keys(self):
        self.set_shared()
        routing = self.load(json.dumps({"preset": "claude",
                                        "tiers": {"std": {"stall_s": 99}}}))
        self.assertEqual(routing["preset"], "claude")
        self.assertEqual(routing["tiers"]["std"]["stall_s"], 99)
        self.assertEqual(routing["tiers"]["std"]["model"], "prov/std-model")
        self.assertEqual(routing["config_warnings"], [])

    def test_plan_routing_overrides_user_and_defaults(self):
        self.set_shared()
        routing = self.load(json.dumps({"preset": "opencode"}), {"preset": "claude"})
        self.assertEqual(routing["preset"], "claude")

    def test_plan_routing_is_merged_last(self):
        self.set_shared()
        routing = self.load(json.dumps({"tiers": {"std": {"model": "own/model"}}}),
                            {"tiers": {"std": {"model": "plan/model", "stall_s": 42}}})
        self.assertEqual(routing["tiers"]["std"]["model"], "plan/model")
        self.assertEqual(routing["tiers"]["std"]["stall_s"], 42)
        self.assertEqual(routing["tiers"]["lite"]["model"], "prov/lite-model")

    def test_plan_tier_models_count_as_skill_sourced_without_shared_file(self):
        routing = self.load(None, {"tiers": {"std": {"model": "plan/std"},
                                             "lite": {"model": "plan/lite"}}})
        self.assertEqual(routing["config_problems"], [])
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "skill"})
        self.assertEqual(routing["tiers"]["std"]["model"], "plan/std")
        self.assertEqual(routing["tiers"]["lite"]["model"], "plan/lite")

    def test_plan_tier_model_drops_shared_variant(self):
        self.set_shared()
        routing = self.load(None, {"tiers": {"std": {"model": "plan/std"}}})
        self.assertEqual(routing["tiers"]["std"]["model"], "plan/std")
        self.assertNotIn("variant", routing["tiers"]["std"])
        self.assertEqual(routing["model_sources"]["std"], "skill")
        self.assertEqual(routing["tiers"]["lite"]["variant"], "low")

    def test_wrong_typed_user_keys_are_config_problems(self):
        self.set_shared()
        for bad in ({"tiers": ["x"]}, {"rows": "std"}, {"tiers": {"std": 5}}):
            routing = self.load(json.dumps(bad))
            self.assertTrue(any("user-routing.json" in p for p in routing["config_problems"]),
                            bad)
            self.assertEqual(routing["tiers"]["std"]["model"], "prov/std-model")
            self.assertIsInstance(routing["rows"], dict)
            s = {"id": "S", "kind": "code", "size": "small", "mode": "slice"}
            router.route(s, routing, True)

    def test_user_file_model_wins_over_shared_model(self):
        self.set_shared()
        routing = self.load(json.dumps({"tiers": {"std": {"model": "own/model",
                                                          "variant": "low"}}}))
        self.assertEqual(routing["tiers"]["std"]["model"], "own/model")
        self.assertEqual(routing["tiers"]["std"]["variant"], "low")
        self.assertEqual(routing["tiers"]["lite"]["model"], "prov/lite-model")
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "shared"})
        self.assertEqual(routing["config_warnings"], [])
        self.assertEqual(routing["config_problems"], [])

    def test_user_model_without_variant_gets_no_variant(self):
        self.set_shared()
        routing = self.load(json.dumps({"tiers": {"std": {"model": "own/model"}}}))
        self.assertEqual(routing["tiers"]["std"]["model"], "own/model")
        self.assertNotIn("variant", routing["tiers"]["std"])

    def test_tier_without_user_model_takes_shared_model_and_variant(self):
        self.set_shared()
        routing = self.load(json.dumps({"tiers": {"std": {"stall_s": 99}}}))
        self.assertEqual(routing["tiers"]["std"]["model"], "prov/std-model")
        self.assertEqual(routing["tiers"]["std"]["variant"], "high")
        self.assertEqual(routing["model_sources"], {"std": "shared", "lite": "shared"})

    def test_tier_with_no_model_anywhere_is_a_config_problem(self):
        routing = self.load(json.dumps({"tiers": {"std": {"model": "own/model"}}}))
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "none"})
        self.assertNotIn("model", routing["tiers"]["lite"])
        self.assertTrue(any("lite" in p and str(self.user_path) in p
                            and router.hybrid_shared.SHARED_SOURCE in p
                            for p in routing["config_problems"]))

    def test_max_parallel_prefers_user_file_then_defaults(self):
        self.set_shared()
        routing = self.load()
        self.assertEqual(routing["tiers"]["std"]["max_parallel"], 6)
        self.assertEqual(routing["tiers"]["lite"]["max_parallel"], 6)
        routing = self.load(json.dumps({"tiers": {"std": {"max_parallel": 2}}}))
        self.assertEqual(routing["tiers"]["std"]["max_parallel"], 2)
        self.assertEqual(routing["tiers"]["lite"]["max_parallel"], 6)

    def test_max_parallel_env_sits_between_user_file_and_defaults(self):
        self.set_shared(dict(MODELS_ENV, HYBRID_OPENCODE_MAX_PARALLEL="3"))
        routing = self.load()
        self.assertEqual([routing["tiers"][t]["max_parallel"] for t in ("std", "lite")], [3, 3])
        routing = self.load(json.dumps({"tiers": {"std": {"max_parallel": 2}}}))
        self.assertEqual([routing["tiers"][t]["max_parallel"] for t in ("std", "lite")], [2, 3])

    def test_shared_problems_are_reported_only_when_a_tier_needs_them(self):
        routing = self.load(json.dumps({"tiers": {"std": {"model": "own/std"},
                                                  "lite": {"model": "own/lite"}}}))
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "skill"})
        self.assertEqual(routing["config_problems"], [])
        routing = self.load(json.dumps({"tiers": {"std": {"model": "own/std"}}}))
        _, shared_problems = router.hybrid_shared.load_shared()
        self.assertTrue(shared_problems)
        for problem in shared_problems:
            self.assertIn(problem, routing["config_problems"])

    def test_malformed_user_file_is_a_config_problem(self):
        self.set_shared()
        routing = self.load("{not json")
        self.assertEqual(len(routing["config_problems"]), 1)
        self.assertIn(str(self.user_path), routing["config_problems"][0])
        self.assertEqual(routing["tiers"]["std"]["stall_s"], 180)

    def test_non_object_user_file_is_a_config_problem(self):
        self.set_shared()
        routing = self.load("[]")
        self.assertEqual(len(routing["config_problems"]), 1)
        self.assertIn(str(self.user_path), routing["config_problems"][0])

    def test_preset_max_is_an_alias_of_opencode_with_one_warning(self):
        self.set_shared()
        routing = self.load(json.dumps({"preset": "max"}))
        self.assertEqual(routing["preset"], "opencode")
        self.assertEqual(len(routing["config_warnings"]), 1)
        self.assertEqual(routing["config_problems"], [])

    def test_unknown_preset_is_a_config_problem(self):
        self.set_shared()
        routing = self.load(json.dumps({"preset": "turbo"}))
        self.assertEqual(len(routing["config_problems"]), 1)
        self.assertIn("turbo", routing["config_problems"][0])

    def test_shipped_defaults_resolve_from_shared_file(self):
        self.set_shared()
        routing = router.load_routing(SHIPPED_DEFAULTS, self.tmp_path / "no-user.json", {})
        self.assertEqual(routing["config_problems"], [])
        self.assertEqual(routing["tiers"]["std"]["model"], "prov/std-model")
        self.assertEqual(routing["tiers"]["lite"]["max_parallel"], 4)
        self.assertEqual(routing["tiers"]["lite"]["stall_s"], 120)
        self.assertNotIn("escalate_to", routing)


class TestRoute(RouterTestCase):
    def test_slice_backend_claude_wins(self):
        s = {"kind": "code", "size": "trivial", "backend": "claude"}
        self.assertEqual(router.route(s, self.routing(), True), "claude")

    def test_slice_backend_oc_tier_wins_when_available(self):
        s = {"kind": "chore", "size": "large", "backend": "oc:std", "verify": "pytest -q"}
        self.assertEqual(router.route(s, self.routing(), True), "oc:std")

    def test_slice_backend_oc_tier_falls_back_when_unavailable(self):
        s = {"kind": "chore", "size": "large", "backend": "oc:std", "verify": "pytest -q"}
        self.assertEqual(router.route(s, self.routing(), False), "claude")

    def test_slice_backend_unknown_tier_falls_back_to_claude(self):
        s = {"kind": "chore", "size": "large", "backend": "oc:nonexistent",
             "verify": "pytest -q"}
        self.assertEqual(router.route(s, self.routing(), True), "claude")

    def test_mode_fast_forces_claude(self):
        s = {"kind": "code", "size": "trivial", "mode": "fast"}
        self.assertEqual(router.route(s, self.routing(), True), "claude")

    def test_mode_research_forces_claude(self):
        s = {"kind": "chore", "mode": "research"}
        self.assertEqual(router.route(s, self.routing(), True), "claude")

    def test_chore_without_verify_mode_research_forces_claude_no_oracle(self):
        s = {"kind": "chore", "size": "small", "mode": "research"}
        self.assertEqual(router.route(s, self.routing(), True), "claude")

    def test_investigator_kind_forces_claude(self):
        s = {"kind": "investigator"}
        self.assertEqual(router.route(s, self.routing(), True), "claude")

    def test_risk_high_forces_claude(self):
        s = {"kind": "chore", "size": "small", "risk": "high"}
        self.assertEqual(router.route(s, self.routing(), True), "claude")

    def test_docs_routes_to_lite(self):
        s = {"kind": "docs", "size": "small", "verify": "make check"}
        self.assertEqual(router.route(s, self.routing(), True), "oc:lite")

    def test_trivial_size_chore_routes_to_lite(self):
        s = {"kind": "chore", "size": "trivial", "verify": "pytest -q"}
        self.assertEqual(router.route(s, self.routing(), True), "oc:lite")

    def test_refactor_non_large_routes_to_std(self):
        s = {"kind": "refactor", "size": "small"}
        self.assertEqual(router.route(s, self.routing(), True), "oc:std")

    def test_large_code_hybrid_routes_to_std(self):
        s = {"kind": "code", "size": "large"}
        self.assertEqual(router.route(s, self.routing(preset="opencode"), True), "oc:std")
        self.assertEqual(router.route(s, self.routing(preset="hybrid"), True), "oc:std")

    def test_large_high_risk_code_hybrid_stays_claude(self):
        s = {"kind": "code", "size": "large", "risk": "high"}
        self.assertEqual(router.route(s, self.routing(preset="hybrid"), True), "claude")

    def test_preset_claude_forces_claude(self):
        s = {"kind": "docs", "size": "trivial"}
        self.assertEqual(router.route(s, self.routing(preset="claude"), True), "claude")

    def test_oc_unavailable_forces_claude(self):
        s = {"kind": "test", "size": "small"}
        self.assertEqual(router.route(s, self.routing(), False), "claude")

    def test_disabled_tier_forces_claude(self):
        routing = self.routing()
        routing["tiers"]["std"]["disabled"] = True
        s = {"kind": "test", "size": "small"}
        self.assertEqual(router.route(s, routing, True), "claude")

    def test_tier_without_model_forces_claude_in_hybrid(self):
        routing = self.routing()
        del routing["tiers"]["std"]["model"]
        s = {"kind": "test", "size": "small"}
        self.assertEqual(router.route(s, routing, True), "claude")


class TestRoutePresetClaude(RouterTestCase):
    def test_claude_preset_ignores_explicit_oc_backend(self):
        s = {"kind": "chore", "size": "small", "verify": "pytest -q", "backend": "oc:std"}
        self.assertEqual(router.route(s, self.routing(preset="claude"), True), "claude")

    def test_unknown_preset_raises_instead_of_falling_back(self):
        s = {"kind": "test", "size": "small"}
        with self.assertRaises(ValueError):
            router.route(s, self.routing(preset="turbo"), True)

    def test_max_is_not_a_preset_here(self):
        s = {"kind": "test", "size": "small"}
        with self.assertRaises(ValueError):
            router.route(s, self.routing(preset="max"), True)


class TestRouteOpencodePreset(RouterTestCase):
    def oc(self):
        return self.routing(preset="opencode")

    def test_large_high_risk_code_routes_to_std(self):
        s = {"kind": "code", "size": "large", "risk": "high"}
        self.assertEqual(router.route(s, self.oc(), True), "oc:std")

    def test_large_refactor_routes_to_std(self):
        s = {"kind": "refactor", "size": "large"}
        self.assertEqual(router.route(s, self.oc(), True), "oc:std")
        self.assertEqual(router.route(s, self.routing(preset="hybrid"), True), "oc:std")

    def test_docs_routes_to_lite(self):
        s = {"kind": "docs", "size": "small", "verify": "make check"}
        self.assertEqual(router.route(s, self.oc(), True), "oc:lite")

    def test_no_oracle_stays_claude(self):
        s = {"kind": "chore", "size": "small"}
        self.assertEqual(router.route(s, self.oc(), True), "claude")

    def test_fast_and_research_modes_stay_claude(self):
        for mode in ("fast", "research"):
            s = {"kind": "code", "size": "small", "mode": mode}
            self.assertEqual(router.route(s, self.oc(), True), "claude")

    def test_kinds_without_an_opencode_runner_stay_claude(self):
        for kind in ("investigator", "perf", "research", "brief-debug", "mystery"):
            s = {"kind": kind, "size": "small"}
            self.assertEqual(router.route(s, self.oc(), True), "claude")

    def test_explicit_claude_backend_stays_claude(self):
        s = {"kind": "code", "size": "small", "backend": "claude"}
        self.assertEqual(router.route(s, self.oc(), True), "claude")

    def test_oc_unavailable_is_held(self):
        s = {"kind": "test", "size": "small"}
        self.assertEqual(router.route(s, self.oc(), False), "held")

    def test_disabled_tier_is_held(self):
        routing = self.oc()
        routing["tiers"]["std"]["disabled"] = True
        s = {"kind": "test", "size": "small"}
        self.assertEqual(router.route(s, routing, True), "held")

    def test_tier_without_model_is_held(self):
        routing = self.oc()
        del routing["tiers"]["std"]["model"]
        s = {"kind": "test", "size": "small"}
        self.assertEqual(router.route(s, routing, True), "held")

    def test_row_without_a_tier_is_held(self):
        routing = self.oc()
        del routing["rows"]["test"]
        s = {"kind": "test", "size": "small"}
        self.assertEqual(router.route(s, routing, True), "held")

    def test_explicit_oc_backend_unavailable_is_held(self):
        s = {"kind": "chore", "size": "small", "verify": "pytest -q", "backend": "oc:std"}
        self.assertEqual(router.route(s, self.oc(), False), "held")
        self.assertEqual(router.route(s, self.routing(preset="hybrid"), False), "claude")

    def test_explicit_oc_backend_with_unknown_tier_is_held(self):
        s = {"kind": "chore", "size": "small", "verify": "pytest -q",
             "backend": "oc:nonexistent"}
        self.assertEqual(router.route(s, self.oc(), True), "held")
        self.assertEqual(router.route(s, self.routing(preset="hybrid"), True), "claude")


class TestRouteNoOracle(RouterTestCase):
    def test_chore_missing_verify_forces_claude_hybrid(self):
        s = {"kind": "chore", "size": "small"}
        self.assertEqual(router.route(s, self.routing(preset="hybrid"), True), "claude")

    def test_chore_empty_verify_forces_claude_opencode(self):
        s = {"kind": "chore", "size": "small", "verify": "   "}
        self.assertEqual(router.route(s, self.routing(preset="opencode"), True), "claude")

    def test_docs_missing_verify_forces_claude(self):
        s = {"kind": "docs", "size": "small"}
        self.assertEqual(router.route(s, self.routing(), True), "claude")

    def test_chore_no_verify_forces_claude_even_with_explicit_oc_backend(self):
        s = {"kind": "chore", "size": "small", "backend": "oc:std"}
        self.assertEqual(router.route(s, self.routing(), True), "claude")

    def test_docs_no_verify_forces_claude_even_with_explicit_oc_backend(self):
        s = {"kind": "docs", "size": "small", "backend": "oc:lite"}
        self.assertEqual(router.route(s, self.routing(), True), "claude")

    def test_chore_with_verify_routes_to_std(self):
        s = {"kind": "chore", "size": "small", "verify": "pytest -q"}
        self.assertEqual(router.route(s, self.routing(), True), "oc:std")

    def test_docs_with_verify_routes_to_lite(self):
        s = {"kind": "docs", "size": "small", "verify": "make check"}
        self.assertEqual(router.route(s, self.routing(), True), "oc:lite")

    def test_chore_with_verify_explicit_backend_wins(self):
        s = {"kind": "chore", "size": "small", "verify": "pytest -q", "backend": "oc:lite"}
        self.assertEqual(router.route(s, self.routing(), True), "oc:lite")


class TestPhaseBackendNoOracle(RouterTestCase):
    def test_green_phase_chore_missing_verify_forces_claude(self):
        s = {"kind": "chore", "size": "small"}
        self.assertEqual(router.phase_backend(s, "green", self.routing(), True), "claude")

    def test_green_phase_docs_missing_verify_forces_claude_opencode(self):
        s = {"kind": "docs", "size": "small"}
        self.assertEqual(
            router.phase_backend(s, "green", self.routing(preset="opencode"), True), "claude"
        )

    def test_green_phase_chore_with_verify_routes_to_std(self):
        s = {"kind": "chore", "size": "small", "verify": "pytest -q"}
        self.assertEqual(router.phase_backend(s, "green", self.routing(), True), "oc:std")


class TestPhaseBackend(RouterTestCase):
    def test_red_phase_always_claude(self):
        s = {"kind": "code", "size": "trivial"}
        self.assertEqual(router.phase_backend(s, "red", self.routing(), True), "claude")

    def test_red_phase_stays_claude_in_opencode_even_when_green_is_held(self):
        s = {"kind": "code", "size": "trivial"}
        routing = self.routing(preset="opencode")
        self.assertEqual(router.phase_backend(s, "red", routing, False), "claude")
        self.assertEqual(router.phase_backend(s, "green", routing, False), "held")

    def test_green_phase_trivial_code_routes_to_std(self):
        s = {"kind": "code", "size": "trivial"}
        self.assertEqual(router.phase_backend(s, "green", self.routing(), True), "oc:std")

    def test_green_phase_large_code_hybrid_routes_to_std(self):
        s = {"kind": "code", "size": "large"}
        self.assertEqual(router.phase_backend(s, "green", self.routing(), True), "oc:std")

    def test_green_phase_large_code_opencode_routes_to_std(self):
        s = {"kind": "code", "size": "large"}
        routing = self.routing(preset="opencode")
        self.assertEqual(router.phase_backend(s, "green", routing, True), "oc:std")

    def test_fast_mode_forces_claude(self):
        s = {"kind": "code", "size": "trivial", "mode": "fast"}
        self.assertEqual(router.phase_backend(s, "green", self.routing(), True), "claude")


class TestNeedsSplit(RouterTestCase):
    def test_non_code_never_splits(self):
        s = {"kind": "chore", "size": "trivial"}
        self.assertFalse(router.needs_split(s, self.routing(), True))

    def test_code_trivial_splits_when_oc_ok(self):
        s = {"kind": "code", "size": "trivial"}
        self.assertTrue(router.needs_split(s, self.routing(), True))

    def test_code_trivial_does_not_split_when_oc_unavailable(self):
        s = {"kind": "code", "size": "trivial"}
        self.assertFalse(router.needs_split(s, self.routing(), False))

    def test_code_large_hybrid_splits(self):
        s = {"kind": "code", "size": "large"}
        self.assertTrue(router.needs_split(s, self.routing(), True))

    def test_code_large_opencode_splits(self):
        s = {"kind": "code", "size": "large"}
        self.assertTrue(router.needs_split(s, self.routing(preset="opencode"), True))

    def test_held_code_slice_still_splits_so_green_is_reported(self):
        s = {"kind": "code", "size": "trivial"}
        self.assertTrue(router.needs_split(s, self.routing(preset="opencode"), False))

    def test_claude_preset_never_splits(self):
        s = {"kind": "code", "size": "trivial"}
        self.assertFalse(router.needs_split(s, self.routing(preset="claude"), True))

    def test_explicit_claude_backend_never_splits(self):
        s = {"kind": "code", "size": "trivial", "backend": "claude"}
        self.assertFalse(router.needs_split(s, self.routing(), True))


def _std_breaker_open(state_dir, tier, spec):
    return {"kind": "auth"} if tier == "std" else {}


class TestBreaker(RouterTestCase):
    def test_open_breaker_holds_the_tier_in_opencode_and_falls_back_in_hybrid(self):
        s = {"kind": "test", "size": "small"}
        with mock.patch.object(router.hybrid_shared, "breaker_open",
                               return_value={"kind": "auth"}):
            opencode = self.routing(preset="opencode")
            hybrid = self.routing(preset="hybrid")
            self.assertEqual(router.route(s, opencode, True, self.breaker_dir), "held")
            self.assertEqual(router.route(s, hybrid, True, self.breaker_dir), "claude")

    def test_breaker_is_checked_for_the_row_tier_and_spec(self):
        routing = self.routing()
        s = {"kind": "test", "size": "small"}
        with mock.patch.object(router.hybrid_shared, "breaker_open",
                               return_value={}) as opened:
            self.assertEqual(router.route(s, routing, True, self.breaker_dir), "oc:std")
        opened.assert_called_once_with(
            self.breaker_dir, "std", router.hybrid_shared.model_spec(routing["tiers"]["std"])
        )

    def test_no_breaker_dir_skips_the_check(self):
        s = {"kind": "test", "size": "small"}
        with mock.patch.object(router.hybrid_shared, "breaker_open") as opened:
            self.assertEqual(router.route(s, self.routing(), True), "oc:std")
        opened.assert_not_called()

    def test_breaker_on_one_tier_leaves_the_other_tier_usable(self):
        routing = self.routing(preset="opencode")
        with mock.patch.object(router.hybrid_shared, "breaker_open",
                               side_effect=_std_breaker_open):
            docs = {"kind": "docs", "size": "small", "verify": "make check"}
            test = {"kind": "test", "size": "small"}
            self.assertEqual(router.route(docs, routing, True, self.breaker_dir), "oc:lite")
            self.assertEqual(router.route(test, routing, True, self.breaker_dir), "held")

    def test_phase_backend_and_needs_split_honour_the_breaker(self):
        s = {"kind": "code", "size": "trivial"}
        opencode = self.routing(preset="opencode")
        hybrid = self.routing(preset="hybrid")
        with mock.patch.object(router.hybrid_shared, "breaker_open",
                               return_value={"kind": "quota"}):
            self.assertEqual(
                router.phase_backend(s, "green", opencode, True, self.breaker_dir), "held")
            self.assertEqual(
                router.phase_backend(s, "red", opencode, True, self.breaker_dir), "claude")
            self.assertTrue(router.needs_split(s, opencode, True, self.breaker_dir))
            self.assertEqual(
                router.phase_backend(s, "green", hybrid, True, self.breaker_dir), "claude")
            self.assertFalse(router.needs_split(s, hybrid, True, self.breaker_dir))


class TestBackendPinExclusions(RouterTestCase):
    """A slice's `backend: "oc:<tier>"` pin may not bypass the exclusions the router applies to
    every other slice (hybrid invariant 1: judgment stays on Claude)."""

    def route(self, s, **overrides):
        return router.route(s, self.routing(**overrides), True, self.breaker_dir)

    def test_pin_does_not_bypass_non_offloadable_kinds(self):
        for kind in ("research", "perf", "investigator", "brief-debug"):
            s = {"kind": kind, "size": "small", "backend": "oc:std", "verify": "pytest -q"}
            self.assertEqual(self.route(s), "claude", kind)
            self.assertEqual(self.route(s, preset="opencode"), "claude", kind)

    def test_pin_does_not_bypass_risk_high_in_hybrid(self):
        s = {"kind": "code", "size": "small", "risk": "high", "backend": "oc:std"}
        self.assertEqual(self.route(s), "claude")

    def test_pin_still_runs_risk_high_in_opencode_preset(self):
        s = {"kind": "code", "size": "small", "risk": "high", "backend": "oc:std"}
        self.assertEqual(self.route(s, preset="opencode"), "oc:std")

    def test_pin_is_honoured_for_an_ordinary_slice(self):
        s = {"kind": "code", "size": "small", "backend": "oc:lite"}
        self.assertEqual(self.route(s), "oc:lite")


if __name__ == "__main__":
    unittest.main()
