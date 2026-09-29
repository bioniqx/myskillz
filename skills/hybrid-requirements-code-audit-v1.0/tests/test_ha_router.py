import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ha_router  # noqa: E402

SKILL = Path(__file__).resolve().parents[1]
DEFAULTS = SKILL / "routing.default.json"

EXPECTED_DEFAULTS = {
    "preset": "hybrid",
    "tiers": {
        "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "max_parallel": 6,
                "stall_s": 180, "timeout_s": 900},
        "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low", "max_parallel": 6,
                 "stall_s": 120, "timeout_s": 600},
    },
    "roles": {"investigator": "std", "verifier": "claude", "parser": "claude"},
    "max_roles": {"verifier": "std", "parser": "std"},
    "oc_batch_max": 4,
    "max_repairs": 2,
    "throttle_cooldown_s": 120,
}


def good_doctor():
    return {
        "t": "2026-09-28T10:00:00Z",
        "ok": True,
        "version": "2.0.18",
        "binary": "opencode",
        "tiers": {
            "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "listed": True,
                    "ping": "ok", "note": "", "down": None},
            "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low", "listed": True,
                     "ping": "unchecked", "note": "", "down": None},
        },
    }


def defaults():
    return ha_router.load_routing(DEFAULTS, Path("/nonexistent/ha-routing.json"))


class TestLoadRouting(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(ha_router.PRESETS, ("claude", "hybrid", "max"))
        self.assertEqual(ha_router.ROLES, ("investigator", "verifier", "parser"))

    def test_shipped_defaults_exact(self):
        with open(str(DEFAULTS)) as f:
            self.assertEqual(json.load(f), EXPECTED_DEFAULTS)

    def test_missing_user_file_gives_defaults(self):
        self.assertEqual(defaults(), EXPECTED_DEFAULTS)

    def test_user_file_deep_merged(self):
        with tempfile.TemporaryDirectory() as tmp:
            user = Path(tmp) / "routing.json"
            user.write_text(json.dumps({
                "preset": "max",
                "tiers": {"std": {"variant": "low"}, "big": {"model": "x/y", "variant": ""}},
                "roles": {"verifier": "std"},
                "max_repairs": 1,
            }))
            routing = ha_router.load_routing(DEFAULTS, user)
        self.assertEqual(routing["preset"], "max")
        self.assertEqual(routing["tiers"]["std"]["variant"], "low")
        self.assertEqual(routing["tiers"]["std"]["model"], "zai-coding-plan/glm-5.3")
        self.assertEqual(routing["tiers"]["std"]["timeout_s"], 900)
        self.assertEqual(routing["tiers"]["lite"], EXPECTED_DEFAULTS["tiers"]["lite"])
        self.assertEqual(routing["tiers"]["big"], {"model": "x/y", "variant": ""})
        self.assertEqual(routing["roles"],
                         {"investigator": "std", "verifier": "std", "parser": "claude"})
        self.assertEqual(routing["max_repairs"], 1)
        self.assertEqual(routing["oc_batch_max"], 4)

    def test_invalid_user_file_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json")
            self.assertEqual(ha_router.load_routing(DEFAULTS, bad), EXPECTED_DEFAULTS)
            lst = Path(tmp) / "list.json"
            lst.write_text("[1, 2]")
            self.assertEqual(ha_router.load_routing(DEFAULTS, lst), EXPECTED_DEFAULTS)

    def test_merge_does_not_mutate_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            user = Path(tmp) / "routing.json"
            user.write_text(json.dumps({"tiers": {"std": {"variant": "low"}}}))
            ha_router.load_routing(DEFAULTS, user)
        self.assertEqual(defaults()["tiers"]["std"]["variant"], "high")

    def test_user_routing_path_env_override(self):
        with mock.patch.dict(os.environ, {"HA_ROUTING": "/tmp/x/routing.json"}):
            self.assertEqual(ha_router.user_routing_path(), Path("/tmp/x/routing.json"))

    def test_user_routing_path_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = dict(os.environ)
            env.pop("HA_ROUTING", None)
            env["HOME"] = tmp
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(
                    ha_router.user_routing_path(),
                    Path(tmp) / ".config" / "hybrid-requirements-code-audit" / "routing.json",
                )


class TestPresetAndRoleTier(unittest.TestCase):
    def test_effective_preset_argument_wins(self):
        routing = defaults()
        self.assertEqual(ha_router.effective_preset(routing, "max"), "max")
        self.assertEqual(ha_router.effective_preset(routing, "claude"), "claude")

    def test_effective_preset_from_routing(self):
        routing = defaults()
        self.assertEqual(ha_router.effective_preset(routing), "hybrid")
        routing["preset"] = "max"
        self.assertEqual(ha_router.effective_preset(routing, ""), "max")

    def test_effective_preset_fallbacks(self):
        self.assertEqual(ha_router.effective_preset({}), "hybrid")
        self.assertEqual(ha_router.effective_preset({"preset": "turbo"}), "claude")
        self.assertEqual(ha_router.effective_preset(defaults(), "bogus"), "claude")

    def test_role_tier_claude_preset(self):
        routing = defaults()
        for role in ha_router.ROLES:
            self.assertEqual(ha_router.role_tier(role, routing, "claude"), "claude")

    def test_role_tier_hybrid(self):
        routing = defaults()
        self.assertEqual(ha_router.role_tier("investigator", routing, "hybrid"), "std")
        self.assertEqual(ha_router.role_tier("verifier", routing, "hybrid"), "claude")
        self.assertEqual(ha_router.role_tier("parser", routing, "hybrid"), "claude")
        self.assertEqual(ha_router.role_tier("investigator", routing), "std")

    def test_role_tier_max(self):
        routing = defaults()
        self.assertEqual(ha_router.role_tier("investigator", routing, "max"), "std")
        self.assertEqual(ha_router.role_tier("verifier", routing, "max"), "std")
        self.assertEqual(ha_router.role_tier("parser", routing, "max"), "std")
        routing["max_roles"] = {"verifier": "lite"}
        self.assertEqual(ha_router.role_tier("verifier", routing, "max"), "lite")
        self.assertEqual(ha_router.role_tier("parser", routing, "max"), "claude")

    def test_role_tier_unknown_role_or_missing_roles(self):
        routing = defaults()
        self.assertEqual(ha_router.role_tier("lead", routing, "hybrid"), "claude")
        self.assertEqual(ha_router.role_tier("investigator", {"preset": "hybrid"}), "claude")


class TestRoute(unittest.TestCase):
    def test_tier_available_good(self):
        self.assertTrue(ha_router.tier_available("std", defaults(), good_doctor()))
        self.assertTrue(ha_router.tier_available("lite", defaults(), good_doctor()))

    def test_tier_available_rejections(self):
        routing = defaults()
        self.assertFalse(ha_router.tier_available("std", routing, {}))
        self.assertFalse(ha_router.tier_available("std", routing, None))
        self.assertFalse(ha_router.tier_available("", routing, good_doctor()))
        self.assertFalse(ha_router.tier_available("big", routing, good_doctor()))
        doctor = good_doctor()
        doctor["ok"] = False
        self.assertFalse(ha_router.tier_available("std", routing, doctor))
        doctor = good_doctor()
        doctor["tiers"]["std"]["listed"] = False
        self.assertFalse(ha_router.tier_available("std", routing, doctor))
        doctor = good_doctor()
        doctor["tiers"]["std"]["ping"] = "failed"
        self.assertFalse(ha_router.tier_available("std", routing, doctor))
        doctor = good_doctor()
        doctor["tiers"]["std"]["down"] = {"reason": "unavailable", "message": "quota",
                                          "at": "2026-09-28T11:00:00Z"}
        self.assertFalse(ha_router.tier_available("std", routing, doctor))
        doctor = good_doctor()
        del doctor["tiers"]["std"]
        self.assertFalse(ha_router.tier_available("std", routing, doctor))

    def test_route_hybrid(self):
        routing = defaults()
        doctor = good_doctor()
        self.assertEqual(ha_router.route("investigator", routing, doctor), "oc:std")
        self.assertEqual(ha_router.route("verifier", routing, doctor), "claude")
        self.assertEqual(ha_router.route("parser", routing, doctor, "hybrid"), "claude")

    def test_route_max(self):
        routing = defaults()
        doctor = good_doctor()
        for role in ha_router.ROLES:
            self.assertEqual(ha_router.route(role, routing, doctor, "max"), "oc:std")

    def test_route_preset_claude(self):
        routing = defaults()
        for role in ha_router.ROLES:
            self.assertEqual(ha_router.route(role, routing, good_doctor(), "claude"), "claude")

    def test_route_preset_from_routing_file(self):
        routing = defaults()
        routing["preset"] = "claude"
        self.assertEqual(ha_router.route("investigator", routing, good_doctor()), "claude")
        routing["preset"] = "max"
        self.assertEqual(ha_router.route("verifier", routing, good_doctor()), "oc:std")

    def test_route_unavailable_or_down(self):
        routing = defaults()
        self.assertEqual(ha_router.route("investigator", routing, {}), "claude")
        doctor = good_doctor()
        doctor["tiers"]["std"]["down"] = {"reason": "throttle", "message": "429",
                                          "at": "2026-09-28T11:00:00Z"}
        self.assertEqual(ha_router.route("investigator", routing, doctor), "claude")

    def test_route_missing_tier(self):
        routing = defaults()
        routing["roles"]["investigator"] = "gpu"
        self.assertEqual(ha_router.route("investigator", routing, good_doctor()), "claude")

    def test_route_user_tier(self):
        routing = defaults()
        routing["roles"]["investigator"] = "lite"
        self.assertEqual(ha_router.route("investigator", routing, good_doctor()), "oc:lite")

    def test_route_cooldown(self):
        routing = defaults()
        doctor = good_doctor()
        cooldown = {"std": 200.0}
        self.assertEqual(
            ha_router.route("investigator", routing, doctor, "", cooldown, 100.0), "claude")
        self.assertEqual(
            ha_router.route("investigator", routing, doctor, "", cooldown, 200.0), "oc:std")
        self.assertEqual(
            ha_router.route("investigator", routing, doctor, "hybrid", {"lite": 999.0}, 1.0),
            "oc:std")
        self.assertEqual(
            ha_router.route("investigator", routing, doctor, "hybrid", None, 5.0), "oc:std")


if __name__ == "__main__":
    unittest.main()
