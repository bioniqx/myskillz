"""Tests for hb_router: routing config, role router, claude agent mapping, cooldown."""

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hb_router  # noqa: E402
import hybrid_shared  # noqa: E402


class TestConstants(unittest.TestCase):
    def test_roles(self):
        self.assertEqual(
            hb_router.ROLES, ("locate", "explore", "fact", "research", "draft")
        )

    def test_presets(self):
        self.assertEqual(hb_router.PRESETS, ("claude", "hybrid", "opencode"))


class TestUserRoutingPath(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("HYBRID_BRAINSTORMING_ROUTING", None)
        self.tmp = tempfile.mkdtemp()

    def test_default_path_is_next_to_the_shipped_defaults(self):
        skill_dir = Path(hb_router.__file__).resolve().parent.parent
        self.assertEqual(hb_router.user_routing_path(), skill_dir / "routing.json")
        self.assertTrue((skill_dir / "routing.default.json").exists())

    def test_env_override(self):
        custom = str(Path(self.tmp) / "custom-routing.json")
        os.environ["HYBRID_BRAINSTORMING_ROUTING"] = custom
        self.assertEqual(hb_router.user_routing_path(), Path(custom))


class SharedConfigCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("HYBRID_OPENCODE_STD", None)
        os.environ.pop("HYBRID_OPENCODE_LITE", None)
        os.environ.pop("HYBRID_OPENCODE_MAX_PARALLEL", None)

    def set_shared(self, tiers):
        for name, var in (("std", "HYBRID_OPENCODE_STD"), ("lite", "HYBRID_OPENCODE_LITE")):
            tier = tiers.get(name)
            if tier:
                variant = "#" + tier["variant"] if tier.get("variant") else ""
                os.environ[var] = tier["model"] + variant

    def write_defaults(self):
        path = self.tmp / "defaults.json"
        path.write_text(
            json.dumps(
                {
                    "preset": "hybrid",
                    "tiers": {
                        "std": {"max_parallel": 6, "stall_s": 90},
                        "lite": {"max_parallel": 6, "stall_s": 60},
                    },
                }
            )
        )
        return path


class TestLoadRouting(SharedConfigCase):
    def test_merges_user_over_defaults(self):
        defaults_path = self.tmp / "defaults-merge.json"
        user_path = self.tmp / "user.json"
        defaults_path.write_text(
            json.dumps(
                {
                    "preset": "hybrid",
                    "tiers": {"std": {"stall_s": 90, "max_parallel": 6}},
                    "roles": {"locate": "lite", "research": "claude"},
                }
            )
        )
        user_path.write_text(
            json.dumps({"preset": "max", "roles": {"locate": "std"}})
        )
        routing = hb_router.load_routing(defaults_path, user_path)
        self.assertEqual(routing["preset"], "max")
        self.assertEqual(routing["roles"]["locate"], "std")
        self.assertEqual(routing["roles"]["research"], "claude")
        self.assertEqual(routing["tiers"]["std"]["stall_s"], 90)

    def test_missing_user_file_returns_defaults(self):
        defaults_path = self.tmp / "defaults-only.json"
        user_path = self.tmp / "missing-user.json"
        defaults_path.write_text(json.dumps({"preset": "hybrid"}))
        routing = hb_router.load_routing(defaults_path, user_path)
        self.assertEqual(routing["preset"], "hybrid")

    def test_shipped_defaults_carry_no_model_or_variant(self):
        defaults = Path(__file__).resolve().parents[1] / "routing.default.json"
        routing = hb_router.load_routing(defaults, None)
        for tier in routing["tiers"].values():
            self.assertNotIn("model", tier)
            self.assertNotIn("variant", tier)

    def test_shipped_defaults_allow_four_opencode_runs_per_tier(self):
        defaults = Path(__file__).resolve().parents[1] / "routing.default.json"
        routing = hb_router.load_routing(defaults, None)
        self.assertEqual([routing["tiers"][t]["max_parallel"] for t in ("std", "lite")], [4, 4])

    def test_shared_env_supplies_model_and_variant(self):
        self.set_shared(
            {
                "std": {"model": "acme/big", "variant": "high"},
                "lite": {"model": "acme/small"},
            }
        )
        routing = hb_router.load_routing(self.write_defaults(), None)
        std = routing["tiers"]["std"]
        self.assertEqual(std["model"], "acme/big")
        self.assertEqual(std["variant"], "high")
        self.assertEqual(std["max_parallel"], 6)
        self.assertEqual(std["stall_s"], 90)
        self.assertEqual(routing["tiers"]["lite"]["model"], "acme/small")
        self.assertEqual(routing["model_sources"], {"std": "shared", "lite": "shared"})

    def test_skill_file_model_wins_over_shared_env(self):
        self.set_shared(
            {
                "std": {"model": "acme/big", "variant": "high"},
                "lite": {"model": "acme/small"},
            }
        )
        user_path = self.tmp / "user-wins.json"
        user_path.write_text(
            json.dumps(
                {"tiers": {"std": {"model": "glm/own", "variant": "low", "stall_s": 5}}}
            )
        )
        routing = hb_router.load_routing(self.write_defaults(), user_path)
        std = routing["tiers"]["std"]
        self.assertEqual(std["model"], "glm/own")
        self.assertEqual(std["variant"], "low")
        self.assertEqual(std["stall_s"], 5)
        self.assertEqual(routing["tiers"]["lite"]["model"], "acme/small")
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "shared"})
        self.assertEqual(routing["config_warnings"], [])

    def test_skill_model_without_variant_gets_no_variant(self):
        self.set_shared(
            {
                "std": {"model": "acme/big", "variant": "high"},
                "lite": {"model": "acme/small"},
            }
        )
        user_path = self.tmp / "user-no-variant.json"
        user_path.write_text(json.dumps({"tiers": {"std": {"model": "glm/own"}}}))
        routing = hb_router.load_routing(self.write_defaults(), user_path)
        self.assertEqual(routing["tiers"]["std"]["model"], "glm/own")
        self.assertNotIn("variant", routing["tiers"]["std"])

    def test_tier_without_skill_model_takes_shared_model_and_variant(self):
        self.set_shared(
            {
                "std": {"model": "acme/big", "variant": "high"},
                "lite": {"model": "acme/small"},
            }
        )
        user_path = self.tmp / "user-no-model.json"
        user_path.write_text(json.dumps({"tiers": {"std": {"stall_s": 5}}}))
        routing = hb_router.load_routing(self.write_defaults(), user_path)
        std = routing["tiers"]["std"]
        self.assertEqual(std["model"], "acme/big")
        self.assertEqual(std["variant"], "high")
        self.assertEqual(std["stall_s"], 5)
        self.assertEqual(routing["model_sources"], {"std": "shared", "lite": "shared"})

    def test_tier_with_no_model_anywhere_is_a_problem(self):
        user_path = self.tmp / "user-one-tier.json"
        user_path.write_text(json.dumps({"tiers": {"std": {"model": "glm/own"}}}))
        routing = hb_router.load_routing(self.write_defaults(), user_path)
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "none"})
        self.assertNotIn("model", routing["tiers"]["lite"])
        self.assertTrue(
            any(
                "lite" in problem
                and str(user_path) in problem
                and hybrid_shared.SHARED_SOURCE in problem
                for problem in routing["config_problems"]
            )
        )

    def test_max_parallel_prefers_skill_file_then_defaults(self):
        self.set_shared(
            {"std": {"model": "acme/big"}, "lite": {"model": "acme/small"}}
        )
        routing = hb_router.load_routing(self.write_defaults(), None)
        self.assertEqual(routing["tiers"]["std"]["max_parallel"], 6)
        self.assertEqual(routing["tiers"]["lite"]["max_parallel"], 6)
        user_path = self.tmp / "user-parallel.json"
        user_path.write_text(json.dumps({"tiers": {"std": {"max_parallel": 2}}}))
        routing = hb_router.load_routing(self.write_defaults(), user_path)
        self.assertEqual(routing["tiers"]["std"]["max_parallel"], 2)
        self.assertEqual(routing["tiers"]["lite"]["max_parallel"], 6)

    def test_max_parallel_env_sits_between_skill_file_and_defaults(self):
        self.set_shared({"std": {"model": "acme/big"}, "lite": {"model": "acme/small"}})
        os.environ["HYBRID_OPENCODE_MAX_PARALLEL"] = "3"
        routing = hb_router.load_routing(self.write_defaults(), None)
        self.assertEqual([routing["tiers"][t]["max_parallel"] for t in ("std", "lite")], [3, 3])
        user_path = self.tmp / "user-parallel.json"
        user_path.write_text(json.dumps({"tiers": {"std": {"max_parallel": 2}}}))
        routing = hb_router.load_routing(self.write_defaults(), user_path)
        self.assertEqual([routing["tiers"][t]["max_parallel"] for t in ("std", "lite")], [2, 3])

    def test_clean_user_file_has_no_warnings(self):
        user_path = self.tmp / "user-clean.json"
        user_path.write_text(json.dumps({"preset": "claude"}))
        routing = hb_router.load_routing(self.write_defaults(), user_path)
        self.assertEqual(routing["config_warnings"], [])

    def test_valid_shared_env_has_no_problems(self):
        self.set_shared(
            {"std": {"model": "acme/big"}, "lite": {"model": "acme/small"}}
        )
        routing = hb_router.load_routing(self.write_defaults(), None)
        self.assertEqual(routing["config_problems"], [])

    def test_missing_shared_env_is_a_problem(self):
        routing = hb_router.load_routing(self.write_defaults(), None)
        self.assertIn("HYBRID_OPENCODE_STD is not set", routing["config_problems"])

    def test_invalid_shared_env_is_a_problem(self):
        self.set_shared({"std": {"model": "no-provider-prefix"}})
        routing = hb_router.load_routing(self.write_defaults(), None)
        self.assertTrue(routing["config_problems"])

    def test_shared_problems_are_reported_only_when_a_tier_needs_them(self):
        user_path = self.tmp / "user-both.json"
        user_path.write_text(
            json.dumps(
                {
                    "tiers": {
                        "std": {"model": "glm/big"},
                        "lite": {"model": "glm/small"},
                    }
                }
            )
        )
        routing = hb_router.load_routing(self.write_defaults(), user_path)
        self.assertEqual(routing["model_sources"], {"std": "skill", "lite": "skill"})
        self.assertEqual(routing["config_problems"], [])
        user_path.write_text(json.dumps({"tiers": {"std": {"model": "glm/big"}}}))
        routing = hb_router.load_routing(self.write_defaults(), user_path)
        _, shared_problems = hybrid_shared.load_shared()
        self.assertTrue(shared_problems)
        for problem in shared_problems:
            self.assertIn(problem, routing["config_problems"])

    def test_malformed_user_file_is_a_problem_not_ignored(self):
        self.set_shared(
            {"std": {"model": "acme/big"}, "lite": {"model": "acme/small"}}
        )
        user_path = self.tmp / "user-broken.json"
        user_path.write_text("{not json")
        routing = hb_router.load_routing(self.write_defaults(), user_path)
        self.assertEqual(routing["preset"], "hybrid")
        self.assertEqual(len(routing["config_problems"]), 1)
        self.assertIn(str(user_path), routing["config_problems"][0])

    def test_non_object_user_file_is_a_problem(self):
        self.set_shared(
            {"std": {"model": "acme/big"}, "lite": {"model": "acme/small"}}
        )
        user_path = self.tmp / "user-list.json"
        user_path.write_text("[1, 2]")
        routing = hb_router.load_routing(self.write_defaults(), user_path)
        self.assertEqual(len(routing["config_problems"]), 1)
        self.assertIn(str(user_path), routing["config_problems"][0])

    def test_wrong_typed_keys_are_problems_and_reset_to_the_defaults(self):
        self.set_shared({"std": {"model": "acme/big"}, "lite": {"model": "acme/small"}})
        cases = [
            ({"roles": [1]}, "roles"),
            ({"max_roles": "x"}, "max_roles"),
            ({"roles": {"locate": 5}}, "roles.locate"),
            ({"tiers": {"lite": {"max_parallel": "abc"}}}, "tiers.lite.max_parallel"),
            ({"tiers": {"lite": {"max_parallel": 0}}}, "tiers.lite.max_parallel"),
            ({"tiers": {"lite": {"stall_s": None}}}, "tiers.lite.stall_s"),
            ({"tiers": {"lite": {"timeout_s": True}}}, "tiers.lite.timeout_s"),
            ({"tiers": {"lite": {"model": 5}}}, "tiers.lite.model"),
            ({"tiers": {"lite": "x"}}, "tiers.lite"),
            ({"tiers": [1]}, "tiers"),
            ({"slot_wait_s": "soon"}, "slot_wait_s"),
            ({"throttle_cooldown_s": -1}, "throttle_cooldown_s"),
            ({"preset": "turbo"}, "preset"),
            ({"preset": 3}, "preset"),
        ]
        for user, key in cases:
            with self.subTest(user=user):
                user_path = self.tmp / "user-typed.json"
                user_path.write_text(json.dumps(user))
                routing = hb_router.load_routing(self.write_defaults(), user_path)
                self.assertEqual(len(routing["config_problems"]), 1, routing["config_problems"])
                self.assertIn("%s: %s must be" % (user_path, key), routing["config_problems"][0])
                self.assertEqual(routing["preset"], "hybrid")
                self.assertEqual(routing["tiers"]["lite"]["stall_s"], 60)  # the lite defaults survive
                self.assertEqual(routing["tiers"]["lite"]["max_parallel"], 6)
                self.assertEqual(routing["tiers"]["lite"]["model"], "acme/small")

    def test_preset_max_alias_is_a_warning_not_a_problem(self):
        self.set_shared({"std": {"model": "acme/big"}, "lite": {"model": "acme/small"}})
        user_path = self.tmp / "user-max.json"
        user_path.write_text(json.dumps({"preset": "max"}))
        routing = hb_router.load_routing(self.write_defaults(), user_path)
        self.assertEqual(routing["config_problems"], [])
        self.assertEqual(len(routing["config_warnings"]), 1)


def _routing(preset="hybrid"):
    return {
        "preset": preset,
        "tiers": {
            "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high"},
            "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low"},
        },
        "roles": {
            "locate": "lite",
            "explore": "std",
            "fact": "lite",
            "research": "std",
            "draft": "claude",
        },
        "max_roles": {"research": "std", "draft": "std"},
    }


def _tier_entry(name, ok):
    return {
        "ok": ok,
        "key": hybrid_shared.cache_key(_routing()["tiers"][name]),
        "checked_at": time.time(),
        "kind": "" if ok else "auth",
        "detail": "" if ok else "auth failed",
    }


def _doctor(ok=True, websearch=True, tier_ok=True, std_ok=None, lite_ok=None):
    std_ok = tier_ok if std_ok is None else std_ok
    lite_ok = tier_ok if lite_ok is None else lite_ok
    return {
        "ok": ok,
        "websearch": websearch,
        "tiers": {
            "std": _tier_entry("std", std_ok),
            "lite": _tier_entry("lite", lite_ok),
        },
    }


class TestRoute(unittest.TestCase):
    def test_backend_flag_claude_wins(self):
        result = hb_router.route(
            "locate", _routing(), _doctor(), backend="claude"
        )
        self.assertEqual(result, "claude")

    def test_backend_flag_oc_tier_available(self):
        result = hb_router.route(
            "locate", _routing(), _doctor(), backend="oc:std"
        )
        self.assertEqual(result, "oc:std")

    def test_backend_flag_oc_tier_unavailable_falls_back(self):
        result = hb_router.route(
            "locate", _routing(), _doctor(tier_ok=False), backend="oc:std"
        )
        self.assertEqual(result, "claude")

    def test_backend_flag_oc_tier_unavailable_is_held_in_opencode_preset(self):
        result = hb_router.route(
            "locate",
            _routing(),
            _doctor(tier_ok=False),
            backend="oc:std",
            preset="opencode",
        )
        self.assertEqual(result, "held")

    def test_default_hybrid_preset_routes_locate_to_lite(self):
        result = hb_router.route("locate", _routing(), _doctor())
        self.assertEqual(result, "oc:lite")

    def test_default_hybrid_preset_routes_research_to_std(self):
        result = hb_router.route("research", _routing(), _doctor())
        self.assertEqual(result, "oc:std")

    def test_default_hybrid_preset_keeps_draft_on_claude(self):
        result = hb_router.route("draft", _routing(), _doctor())
        self.assertEqual(result, "claude")

    def test_opencode_preset_routes_research_to_std(self):
        result = hb_router.route(
            "research", _routing(), _doctor(), preset="opencode"
        )
        self.assertEqual(result, "oc:std")

    def test_opencode_preset_routes_every_role_to_a_tier(self):
        expected = {
            "locate": "oc:lite",
            "explore": "oc:std",
            "fact": "oc:lite",
            "research": "oc:std",
            "draft": "oc:std",
        }
        for role, want in expected.items():
            with self.subTest(role=role):
                result = hb_router.route(
                    role, _routing(), _doctor(), preset="opencode"
                )
                self.assertEqual(result, want)

    def test_opencode_preset_read_from_routing(self):
        result = hb_router.route(
            "research", _routing(preset="opencode"), _doctor()
        )
        self.assertEqual(result, "oc:std")

    def test_opencode_preset_research_held_when_websearch_off(self):
        result = hb_router.route(
            "research", _routing(), _doctor(websearch=False), preset="opencode"
        )
        self.assertEqual(result, "held")

    def test_hybrid_preset_research_falls_back_when_websearch_off(self):
        result = hb_router.route(
            "research", _routing(), _doctor(websearch=False)
        )
        self.assertEqual(result, "claude")

    def test_max_alias_routes_like_opencode(self):
        result = hb_router.route(
            "research", _routing(), _doctor(), preset="max"
        )
        self.assertEqual(result, "oc:std")

    def test_unknown_preset_raises(self):
        with self.assertRaises(ValueError):
            hb_router.route("locate", _routing(), _doctor(), preset="turbo")
        with self.assertRaises(ValueError):
            hb_router.route("locate", _routing(preset="turbo"), _doctor())

    def test_preset_claude_forces_claude_without_doctor(self):
        result = hb_router.route("locate", _routing(), {}, preset="claude")
        self.assertEqual(result, "claude")

    def test_opencode_preset_role_pinned_to_claude_is_claude_not_held(self):
        routing = _routing()
        del routing["max_roles"]["research"]
        routing["roles"]["research"] = "claude"
        self.assertEqual(hb_router.route("research", routing, _doctor(websearch=False), preset="opencode"), "claude")
        routing["max_roles"]["research"] = "claude"
        self.assertEqual(hb_router.route("research", routing, _doctor(), preset="opencode"), "claude")

    def test_tier_disabled_falls_back(self):
        routing = _routing()
        routing["tiers"]["lite"]["disabled"] = True
        result = hb_router.route("locate", routing, _doctor())
        self.assertEqual(result, "claude")

    def test_tier_disabled_is_held_in_opencode_preset(self):
        routing = _routing()
        routing["tiers"]["lite"]["disabled"] = True
        result = hb_router.route("locate", routing, _doctor(), preset="opencode")
        self.assertEqual(result, "held")

    def test_doctor_not_ok_falls_back(self):
        result = hb_router.route("locate", _routing(), _doctor(ok=False))
        self.assertEqual(result, "claude")

    def test_doctor_not_ok_is_held_in_opencode_preset(self):
        result = hb_router.route(
            "locate", _routing(), _doctor(ok=False), preset="opencode"
        )
        self.assertEqual(result, "held")

    def test_tier_without_model_is_unavailable(self):
        routing = _routing()
        del routing["tiers"]["lite"]["model"]
        self.assertEqual(hb_router.route("locate", routing, _doctor()), "claude")
        self.assertEqual(
            hb_router.route("locate", routing, _doctor(), preset="opencode"),
            "held",
        )

    def test_stale_doctor_entry_is_unavailable(self):
        later = time.time() + 10 ** 9
        self.assertEqual(
            hb_router.route("locate", _routing(), _doctor(), now=later), "claude"
        )
        self.assertEqual(
            hb_router.route(
                "locate", _routing(), _doctor(), now=later, preset="opencode"
            ),
            "held",
        )

    def test_doctor_entry_for_a_different_model_is_unavailable(self):
        routing = _routing()
        routing["tiers"]["lite"]["model"] = "zai-coding-plan/other"
        result = hb_router.route("locate", routing, _doctor())
        self.assertEqual(result, "claude")

    def test_one_failed_tier_does_not_disable_the_other(self):
        doctor = _doctor(std_ok=False)
        self.assertEqual(hb_router.route("locate", _routing(), doctor), "oc:lite")
        self.assertEqual(hb_router.route("explore", _routing(), doctor), "claude")
        self.assertEqual(
            hb_router.route("explore", _routing(), doctor, preset="opencode"),
            "held",
        )

    def test_open_breaker_makes_tier_unavailable(self):
        breaker_dir = Path(tempfile.mkdtemp())
        lite_spec = hybrid_shared.model_spec(_routing()["tiers"]["lite"])
        with mock.patch.object(
            hybrid_shared, "breaker_open", return_value={"kind": "auth"}
        ) as opened:
            hybrid_result = hb_router.route(
                "locate", _routing(), _doctor(), breaker_dir=breaker_dir
            )
            opencode_result = hb_router.route(
                "locate",
                _routing(),
                _doctor(),
                preset="opencode",
                breaker_dir=breaker_dir,
            )
        self.assertEqual(hybrid_result, "claude")
        self.assertEqual(opencode_result, "held")
        opened.assert_called_with(breaker_dir, "lite", lite_spec)

    def test_closed_breaker_keeps_the_tier(self):
        breaker_dir = Path(tempfile.mkdtemp())
        result = hb_router.route(
            "locate", _routing(), _doctor(), breaker_dir=breaker_dir
        )
        self.assertEqual(result, "oc:lite")

    def test_breaker_is_not_checked_without_a_directory(self):
        with mock.patch.object(hybrid_shared, "breaker_open") as opened:
            result = hb_router.route("locate", _routing(), _doctor())
        self.assertEqual(result, "oc:lite")
        opened.assert_not_called()


class TestClaudeAgent(unittest.TestCase):
    def test_locate(self):
        self.assertEqual(hb_router.claude_agent("locate"), ("Explore", "haiku"))

    def test_explore(self):
        self.assertEqual(hb_router.claude_agent("explore"), ("Explore", "sonnet"))

    def test_fact(self):
        self.assertEqual(
            hb_router.claude_agent("fact"), ("general-purpose", "haiku")
        )

    def test_research(self):
        self.assertEqual(
            hb_router.claude_agent("research"), ("general-purpose", "sonnet")
        )

    def test_draft(self):
        self.assertEqual(
            hb_router.claude_agent("draft"), ("general-purpose", "sonnet")
        )


class TestCooldown(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_no_cooldown_file_means_not_in_cooldown(self):
        self.assertFalse(hb_router.in_cooldown(self.tmp, "std", now=1000.0))

    def test_start_cooldown_then_in_cooldown(self):
        hb_router.start_cooldown(self.tmp, "std", 120, now=1000.0)
        self.assertTrue(hb_router.in_cooldown(self.tmp, "std", now=1050.0))

    def test_cooldown_expires(self):
        hb_router.start_cooldown(self.tmp, "std", 120, now=1000.0)
        self.assertFalse(hb_router.in_cooldown(self.tmp, "std", now=1200.0))


if __name__ == "__main__":
    unittest.main()
