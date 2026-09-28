"""Tests for hb_router: routing config, role router, claude agent mapping, cooldown."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hb_router  # noqa: E402


class TestConstants(unittest.TestCase):
    def test_roles(self):
        self.assertEqual(
            hb_router.ROLES, ("locate", "explore", "fact", "research", "draft")
        )

    def test_presets(self):
        self.assertEqual(hb_router.PRESETS, ("claude", "hybrid", "max"))


class TestUserRoutingPath(unittest.TestCase):
    def setUp(self):
        self._old_home = os.environ.get("HOME")
        self._old_routing = os.environ.get("HB_ROUTING")
        self.tmp = tempfile.mkdtemp()
        os.environ["HOME"] = self.tmp
        os.environ.pop("HB_ROUTING", None)

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        if self._old_routing is None:
            os.environ.pop("HB_ROUTING", None)
        else:
            os.environ["HB_ROUTING"] = self._old_routing

    def test_default_path(self):
        expected = Path(self.tmp) / ".config" / "hybrid-brainstorming" / "routing.json"
        self.assertEqual(hb_router.user_routing_path(), expected)

    def test_env_override(self):
        custom = str(Path(self.tmp) / "custom-routing.json")
        os.environ["HB_ROUTING"] = custom
        self.assertEqual(hb_router.user_routing_path(), Path(custom))


class TestLoadRouting(unittest.TestCase):
    def test_merges_user_over_defaults(self):
        tmp = tempfile.mkdtemp()
        defaults_path = Path(tmp) / "defaults.json"
        user_path = Path(tmp) / "user.json"
        defaults_path.write_text(
            json.dumps(
                {
                    "preset": "hybrid",
                    "tiers": {"std": {"model": "a", "max_parallel": 6}},
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
        self.assertEqual(routing["tiers"]["std"]["model"], "a")

    def test_missing_user_file_returns_defaults(self):
        tmp = tempfile.mkdtemp()
        defaults_path = Path(tmp) / "defaults.json"
        user_path = Path(tmp) / "missing-user.json"
        defaults_path.write_text(json.dumps({"preset": "hybrid"}))
        routing = hb_router.load_routing(defaults_path, user_path)
        self.assertEqual(routing["preset"], "hybrid")


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
            "research": "claude",
            "draft": "claude",
        },
        "max_roles": {"research": "std", "draft": "std"},
    }


def _doctor(ok=True, websearch=True, tier_ok=True):
    return {
        "ok": ok,
        "websearch": websearch,
        "tiers": {
            "std": {"ok": tier_ok},
            "lite": {"ok": tier_ok},
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

    def test_default_hybrid_preset_routes_locate_to_lite(self):
        result = hb_router.route("locate", _routing(), _doctor())
        self.assertEqual(result, "oc:lite")

    def test_default_hybrid_preset_routes_research_to_claude(self):
        result = hb_router.route("research", _routing(), _doctor())
        self.assertEqual(result, "claude")

    def test_max_preset_routes_research_to_std(self):
        result = hb_router.route(
            "research", _routing(), _doctor(), preset="max"
        )
        self.assertEqual(result, "oc:std")

    def test_max_preset_research_falls_back_when_websearch_off(self):
        result = hb_router.route(
            "research", _routing(), _doctor(websearch=False), preset="max"
        )
        self.assertEqual(result, "claude")

    def test_preset_claude_forces_claude(self):
        result = hb_router.route(
            "locate", _routing(), _doctor(), preset="claude"
        )
        self.assertEqual(result, "claude")

    def test_tier_disabled_falls_back(self):
        routing = _routing()
        routing["tiers"]["lite"]["disabled"] = True
        result = hb_router.route("locate", routing, _doctor())
        self.assertEqual(result, "claude")

    def test_doctor_not_ok_falls_back(self):
        result = hb_router.route("locate", _routing(), _doctor(ok=False))
        self.assertEqual(result, "claude")


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
