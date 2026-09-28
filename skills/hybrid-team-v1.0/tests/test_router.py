import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import router


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
    "escalate_to": "claude",
    "max_escalations": 1,
}


class RouterTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self._old_home = os.environ.get("HOME")
        self._old_ht_routing = os.environ.get("HT_ROUTING")
        os.environ["HOME"] = str(self.tmp_path)
        os.environ.pop("HT_ROUTING", None)

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        if self._old_ht_routing is None:
            os.environ.pop("HT_ROUTING", None)
        else:
            os.environ["HT_ROUTING"] = self._old_ht_routing
        self._tmp.cleanup()

    def routing(self, **overrides):
        routing = json.loads(json.dumps(DEFAULT_ROUTING))
        return router._merge(routing, overrides) if overrides else routing


class TestPresets(RouterTestCase):
    def test_presets_tuple(self):
        self.assertEqual(router.PRESETS, ("claude", "hybrid", "max"))


class TestUserRoutingPath(RouterTestCase):
    def test_default_under_home(self):
        expected = self.tmp_path / ".config" / "hybrid-team" / "routing.json"
        self.assertEqual(router.user_routing_path(), expected)

    def test_env_override(self):
        override = self.tmp_path / "custom" / "routing.json"
        os.environ["HT_ROUTING"] = str(override)
        self.assertEqual(router.user_routing_path(), override)


class TestLoadRouting(RouterTestCase):
    def test_defaults_only(self):
        defaults_path = self.tmp_path / "routing.default.json"
        defaults_path.write_text(json.dumps(DEFAULT_ROUTING))
        user_path = self.tmp_path / "no-such-user-routing.json"
        routing = router.load_routing(defaults_path, user_path, {})
        self.assertEqual(routing["preset"], "hybrid")
        self.assertEqual(routing["tiers"]["std"]["model"], "zai-coding-plan/glm-5.3")

    def test_user_file_overrides_defaults(self):
        defaults_path = self.tmp_path / "routing.default.json"
        defaults_path.write_text(json.dumps(DEFAULT_ROUTING))
        user_path = self.tmp_path / "user-routing.json"
        user_path.write_text(json.dumps({"preset": "max",
                                          "tiers": {"std": {"variant": "low"}}}))
        routing = router.load_routing(defaults_path, user_path, {})
        self.assertEqual(routing["preset"], "max")
        self.assertEqual(routing["tiers"]["std"]["variant"], "low")
        self.assertEqual(routing["tiers"]["std"]["model"], "zai-coding-plan/glm-5.3")

    def test_plan_routing_overrides_user_and_defaults(self):
        defaults_path = self.tmp_path / "routing.default.json"
        defaults_path.write_text(json.dumps(DEFAULT_ROUTING))
        user_path = self.tmp_path / "user-routing.json"
        user_path.write_text(json.dumps({"preset": "max"}))
        routing = router.load_routing(defaults_path, user_path, {"preset": "claude"})
        self.assertEqual(routing["preset"], "claude")


class TestRoute(RouterTestCase):
    def test_slice_backend_claude_wins(self):
        s = {"kind": "code", "size": "trivial", "backend": "claude"}
        self.assertEqual(router.route(s, self.routing(), True), "claude")

    def test_slice_backend_oc_tier_wins_when_available(self):
        s = {"kind": "chore", "size": "large", "backend": "oc:std", "verify": "pytest -q"}
        self.assertEqual(router.route(s, self.routing(), True), "oc:std")

    def test_slice_backend_oc_tier_falls_back_when_unavailable(self):
        s = {"kind": "chore", "size": "large", "backend": "oc:std"}
        self.assertEqual(router.route(s, self.routing(), False), "claude")

    def test_slice_backend_unknown_tier_falls_back_to_claude(self):
        s = {"kind": "chore", "size": "large", "backend": "oc:nonexistent"}
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

    def test_large_code_hybrid_forces_claude(self):
        s = {"kind": "code", "size": "large"}
        self.assertEqual(router.route(s, self.routing(preset="max"), True), "oc:std")
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


class TestRouteNoOracle(RouterTestCase):
    def test_chore_missing_verify_forces_claude_hybrid(self):
        s = {"kind": "chore", "size": "small"}
        self.assertEqual(router.route(s, self.routing(preset="hybrid"), True), "claude")

    def test_chore_empty_verify_forces_claude_max(self):
        s = {"kind": "chore", "size": "small", "verify": "   "}
        self.assertEqual(router.route(s, self.routing(preset="max"), True), "claude")

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

    def test_green_phase_docs_missing_verify_forces_claude_max(self):
        s = {"kind": "docs", "size": "small"}
        self.assertEqual(
            router.phase_backend(s, "green", self.routing(preset="max"), True), "claude"
        )

    def test_green_phase_chore_with_verify_routes_to_std(self):
        s = {"kind": "chore", "size": "small", "verify": "pytest -q"}
        self.assertEqual(router.phase_backend(s, "green", self.routing(), True), "oc:std")


class TestPhaseBackend(RouterTestCase):
    def test_red_phase_always_claude(self):
        s = {"kind": "code", "size": "trivial"}
        self.assertEqual(router.phase_backend(s, "red", self.routing(), True), "claude")

    def test_green_phase_trivial_code_routes_to_std(self):
        s = {"kind": "code", "size": "trivial"}
        self.assertEqual(router.phase_backend(s, "green", self.routing(), True), "oc:std")

    def test_green_phase_large_code_hybrid_stays_claude(self):
        s = {"kind": "code", "size": "large"}
        self.assertEqual(router.phase_backend(s, "green", self.routing(), True), "claude")

    def test_green_phase_large_code_max_routes_to_std(self):
        s = {"kind": "code", "size": "large"}
        routing = self.routing(preset="max")
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

    def test_code_large_hybrid_does_not_split(self):
        s = {"kind": "code", "size": "large"}
        self.assertFalse(router.needs_split(s, self.routing(), True))

    def test_code_large_max_splits(self):
        s = {"kind": "code", "size": "large"}
        self.assertTrue(router.needs_split(s, self.routing(preset="max"), True))

    def test_explicit_claude_backend_never_splits(self):
        s = {"kind": "code", "size": "trivial", "backend": "claude"}
        self.assertFalse(router.needs_split(s, self.routing(), True))


if __name__ == "__main__":
    unittest.main()
