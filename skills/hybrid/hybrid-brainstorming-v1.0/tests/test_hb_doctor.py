import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hb_doctor
import hybrid_shared
from hb_config import SENTINEL

NOW = time.time()


def _default_routing():
    return {
        "preset": "hybrid",
        "tiers": {
            "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high",
                     "max_parallel": 6, "stall_s": 90, "timeout_s": 300},
            "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low",
                      "max_parallel": 6, "stall_s": 60, "timeout_s": 180},
        },
        "roles": {"locate": "lite", "explore": "std", "fact": "lite",
                   "research": "claude", "draft": "claude"},
        "max_roles": {"research": "std", "draft": "std"},
        "slot_wait_s": 60, "throttle_cooldown_s": 120,
    }


def _fresh_entry(tier, checked_at):
    return {"ok": True, "key": hybrid_shared.cache_key(tier), "checked_at": checked_at,
            "kind": "", "detail": "listed in opencode models"}


def _default_doctor(checked_at=NOW):
    tiers = _default_routing()["tiers"]
    return {
        "t": "2026-09-28T12:00:00Z",
        "ok": True,
        "version": "2.0.18",
        "binary": "opencode",
        "tiers": {name: _fresh_entry(tier, checked_at) for name, tier in tiers.items()},
        "websearch": False,
        "status_line": "",
    }


class EnvIsolatedTestCase(unittest.TestCase):
    def setUp(self):
        self._saved_environ = dict(os.environ)
        self._tmp = tempfile.mkdtemp()
        os.environ["HOME"] = self._tmp
        os.environ.pop("HB_DOCTOR_CACHE", None)
        os.environ.pop("HB_ROUTING", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_environ)


class TestDoctorCachePath(EnvIsolatedTestCase):
    def test_default_path_under_home_cache(self):
        path = hb_doctor.doctor_cache_path()
        self.assertEqual(
            path,
            Path(self._tmp) / ".cache" / "hybrid-brainstorming" / "doctor.json",
        )

    def test_env_override(self):
        override = Path(self._tmp) / "custom" / "doctor.json"
        os.environ["HB_DOCTOR_CACHE"] = str(override)
        path = hb_doctor.doctor_cache_path()
        self.assertEqual(path, override)


class TestLoadWriteDoctor(EnvIsolatedTestCase):
    def test_load_missing_file_returns_empty_dict(self):
        missing = Path(self._tmp) / "nope" / "doctor.json"
        self.assertEqual(hb_doctor.load_doctor(missing), {})

    def test_write_then_load_round_trips(self):
        path = Path(self._tmp) / "cache" / "doctor.json"
        data = _default_doctor()
        hb_doctor.write_doctor(path, data)
        self.assertTrue(path.is_file())
        loaded = hb_doctor.load_doctor(path)
        self.assertEqual(loaded, data)


class TestStatusLine(EnvIsolatedTestCase):
    def test_unavailable_when_doctor_missing(self):
        line = hb_doctor.status_line(_default_routing(), {})
        self.assertEqual(
            line,
            "opencode: unavailable → preset claude (run bslane.py doctor)",
        )

    def test_matches_spec_example(self):
        line = hb_doctor.status_line(_default_routing(), _default_doctor(), now=NOW)
        self.assertEqual(
            line,
            "opencode: v2.0.18 preset=hybrid locate=oc:lite explore=oc:std "
            "fact=oc:lite research=claude draft=claude websearch=off "
            "(doctor 2026-09-28)",
        )

    def test_stale_entries_say_stale(self):
        doctor = _default_doctor(checked_at=NOW - 3600)
        line = hb_doctor.status_line(_default_routing(), doctor, now=NOW)
        self.assertEqual(
            line,
            "opencode: v2.0.18 preset=hybrid stale tiers=lite,std "
            "(doctor 2026-09-28) → run bslane.py doctor",
        )

    def test_model_edit_makes_only_that_tier_stale(self):
        routing = _default_routing()
        routing["tiers"]["std"]["model"] = "zai-coding-plan/glm-5.4"
        line = hb_doctor.status_line(routing, _default_doctor(), now=NOW)
        self.assertEqual(
            line,
            "opencode: v2.0.18 preset=hybrid stale tiers=std "
            "(doctor 2026-09-28) → run bslane.py doctor",
        )

    def test_tier_missing_from_doctor_is_stale(self):
        doctor = _default_doctor()
        del doctor["tiers"]["lite"]
        line = hb_doctor.status_line(_default_routing(), doctor, now=NOW)
        self.assertIn("stale tiers=lite ", line)

    def test_preset_claude_never_reports_stale(self):
        routing = _default_routing()
        routing["preset"] = "claude"
        line = hb_doctor.status_line(routing, _default_doctor(checked_at=NOW - 3600), now=NOW)
        self.assertNotIn("stale", line)

    def test_now_defaults_to_the_clock(self):
        fresh = hb_doctor.status_line(_default_routing(), _default_doctor(checked_at=time.time()))
        self.assertNotIn("stale", fresh)
        old = hb_doctor.status_line(_default_routing(),
                                    _default_doctor(checked_at=time.time() - 3600))
        self.assertIn("stale", old)


class TestDoctorFixes(EnvIsolatedTestCase):
    def test_tier_without_a_model_is_never_stale(self):
        routing = _default_routing()
        del routing["tiers"]["lite"]["model"]
        line = hb_doctor.status_line(routing, _default_doctor(), now=NOW)
        self.assertNotIn("stale", line)

    def test_failed_ping_that_ran_cleanly_gets_a_kind(self):
        def run_once(cmd, cwd, env, out_path, err_path, stall_s=0, timeout_s=0):
            return {"text": text, "errors": [], "rc": 0, "reason": "", "note": "", "tools": []}

        tier = _default_routing()["tiers"]["std"]
        with mock.patch.object(hb_doctor, "build_cmd", return_value=["x"]), \
             mock.patch.object(hb_doctor, "config_env", return_value={}), \
             mock.patch.object(hb_doctor, "run_once", side_effect=run_once):
            for text, kind in (("", "empty"), ("something else", "format")):
                ok, got, detail = hb_doctor._ping_tier("opencode", "std", tier, Path(self._tmp))
                self.assertEqual((ok, got), (False, kind))
                self.assertTrue(detail)

    def test_plain_doctor_keeps_a_websearch_found_by_a_ping_for_the_same_model(self):
        routing = _default_routing()
        web_key = hybrid_shared.cache_key(routing["tiers"]["std"])  # roles.research is claude, so max_roles: std
        prev = {"websearch": True, "websearch_key": web_key}
        with mock.patch.object(hb_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(hb_doctor.subprocess, "run", side_effect=TestRunDoctor()._subprocess_run(
                 TestRunDoctor.MODELS)):
            kept = hb_doctor.run_doctor("opencode", routing, False, Path(self._tmp), prev)
            self.assertTrue(kept["websearch"])
            self.assertEqual(kept["websearch_key"], web_key)
            self.assertFalse(hb_doctor.run_doctor("opencode", routing, False, Path(self._tmp))["websearch"])
            routing["tiers"]["std"]["model"] = "zai-coding-plan/glm-5.3-flash"
            self.assertFalse(hb_doctor.run_doctor("opencode", routing, False, Path(self._tmp), prev)["websearch"])


class TestRunDoctor(EnvIsolatedTestCase):
    MODELS = "zai-coding-plan/glm-5.3\nzai-coding-plan/glm-5.3-flash\n"

    def _subprocess_run(self, models_stdout, models_rc=0, models_stderr=""):
        def _run(cmd, capture_output, text, timeout, stdin=None):
            if cmd[1] == "--version":
                return SimpleNamespace(returncode=0, stdout="2.0.18\n", stderr="")
            if cmd[1] == "models":
                return SimpleNamespace(returncode=models_rc, stdout=models_stdout,
                                       stderr=models_stderr)
            raise AssertionError("unexpected cmd %r" % (cmd,))
        return _run

    def _doctor(self, models_stdout, **models_kwargs):
        with mock.patch.object(hb_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(hb_doctor.subprocess, "run",
                                side_effect=self._subprocess_run(models_stdout, **models_kwargs)):
            return hb_doctor.run_doctor("opencode", _default_routing(), False, Path(self._tmp))

    def _fake_run_once(self, cmd, cwd, env, out_path, err_path, stall_s=0, timeout_s=0):
        name = Path(out_path).name
        if name.startswith("doctor-ping-"):
            return {
                "session": "s1", "text": SENTINEL,
                "usage": {"input": 1, "output": 1, "reasoning": 0,
                           "cache_read": 0, "cache_write": 0, "cost": 0.0},
                "errors": [], "throttled": False, "events": 1, "tools": [],
                "rc": 0, "reason": "", "note": "", "pid": 1, "duration": 0.1,
            }
        if name == "doctor-websearch.out.jsonl":
            return {
                "session": "s2", "text": SENTINEL,
                "usage": {"input": 1, "output": 1, "reasoning": 0,
                           "cache_read": 0, "cache_write": 0, "cost": 0.0},
                "errors": [], "throttled": False, "events": 2,
                "tools": [{"tool": "websearch", "status": "completed",
                            "input": {}, "output": "ok"}],
                "rc": 0, "reason": "", "note": "", "pid": 2, "duration": 0.2,
            }
        raise AssertionError("unexpected out_path %r" % (out_path,))

    def _ping_doctor(self, run_once):
        with mock.patch.object(hb_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(hb_doctor.subprocess, "run",
                                side_effect=self._subprocess_run(self.MODELS)), \
             mock.patch.object(hb_doctor, "build_cmd", return_value=["opencode", "run"]), \
             mock.patch.object(hb_doctor, "config_env", return_value={}), \
             mock.patch.object(hb_doctor, "run_once", side_effect=run_once):
            return hb_doctor.run_doctor("opencode", _default_routing(), True, Path(self._tmp))

    def test_run_doctor_without_ping_checks_binary_and_models(self):
        before = time.time()
        result = self._doctor(self.MODELS)
        after = time.time()

        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "2.0.18")
        self.assertEqual(result["binary"], "/usr/bin/opencode")
        self.assertFalse(result["websearch"])
        self.assertIn("opencode: v2.0.18", result["status_line"])
        self.assertNotIn("stale", result["status_line"])
        tiers = _default_routing()["tiers"]
        for name in ("std", "lite"):
            entry = result["tiers"][name]
            self.assertEqual(sorted(entry), ["checked_at", "detail", "key", "kind", "ok"])
            self.assertTrue(entry["ok"])
            self.assertEqual(entry["kind"], "")
            self.assertEqual(entry["key"], hybrid_shared.cache_key(tiers[name]))
            self.assertTrue(before <= entry["checked_at"] <= after)

    def test_run_doctor_with_ping_probes_tiers_and_websearch(self):
        result = self._ping_doctor(self._fake_run_once)

        self.assertTrue(result["ok"])
        self.assertTrue(result["websearch"])
        for name in ("std", "lite"):
            entry = result["tiers"][name]
            self.assertTrue(entry["ok"])
            self.assertEqual(entry["kind"], "")
            self.assertEqual(entry["detail"], "ping ok")

    def test_one_failed_tier_does_not_disable_the_other(self):
        result = self._doctor("zai-coding-plan/glm-5.3\n")

        self.assertTrue(result["ok"])
        self.assertTrue(result["tiers"]["std"]["ok"])
        lite = result["tiers"]["lite"]
        self.assertFalse(lite["ok"])
        self.assertEqual(lite["kind"], "model")
        self.assertIn("zai-coding-plan/glm-5.3-flash", lite["detail"])
        self.assertIn("not found in `opencode models`", lite["detail"])

    def test_all_tiers_failed_marks_doctor_not_ok(self):
        result = self._doctor("other/model\n")

        self.assertFalse(result["ok"])
        self.assertFalse(result["tiers"]["std"]["ok"])
        self.assertFalse(result["tiers"]["lite"]["ok"])

    def test_empty_models_listing_is_config_error_for_every_tier(self):
        result = self._doctor("")

        self.assertFalse(result["ok"])
        for name in ("std", "lite"):
            entry = result["tiers"][name]
            self.assertFalse(entry["ok"])
            self.assertEqual(entry["kind"], "config")
            self.assertEqual(entry["detail"], "opencode models listed nothing")

    def test_tier_without_a_model_is_a_config_error(self):
        routing = _default_routing()
        del routing["tiers"]["lite"]["model"]
        with mock.patch.object(hb_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(hb_doctor.subprocess, "run",
                                side_effect=self._subprocess_run(self.MODELS)):
            result = hb_doctor.run_doctor("opencode", routing, False, Path(self._tmp))

        lite = result["tiers"]["lite"]
        self.assertFalse(lite["ok"])
        self.assertEqual(lite["kind"], "config")
        self.assertIn("no model", lite["detail"])
        self.assertTrue(result["tiers"]["std"]["ok"])
        self.assertTrue(result["ok"])

    def test_models_command_failure_uses_classify(self):
        with mock.patch.object(hb_doctor, "classify", return_value="auth") as classify, \
             mock.patch.object(hb_doctor, "first_error", return_value="401 unauthorized"):
            result = self._doctor("", models_rc=1, models_stderr="401 unauthorized")

        entry = result["tiers"]["std"]
        self.assertEqual((entry["ok"], entry["kind"], entry["detail"]),
                         (False, "auth", "401 unauthorized"))
        classify.assert_called_with(1, [], "401 unauthorized")

    def test_missing_binary_is_spawn_error_for_every_tier(self):
        with mock.patch.object(hb_doctor.shutil, "which", return_value=None), \
             mock.patch.object(hb_doctor.subprocess, "run", side_effect=OSError("no such file")):
            result = hb_doctor.run_doctor("opencode", _default_routing(), False, Path(self._tmp))

        self.assertFalse(result["ok"])
        self.assertEqual(result["version"], "")
        for name in ("std", "lite"):
            self.assertEqual(result["tiers"][name]["kind"], "spawn")
            self.assertIn("no such file", result["tiers"][name]["detail"])

    def test_detail_is_a_single_line_of_at_most_200_chars(self):
        long_text = "first line\nsecond line " + "x" * 300
        with mock.patch.object(hb_doctor, "classify", return_value="crash"), \
             mock.patch.object(hb_doctor, "first_error", return_value=long_text):
            result = self._doctor("", models_rc=1, models_stderr="boom")

        detail = result["tiers"]["std"]["detail"]
        self.assertNotIn("\n", detail)
        self.assertEqual(len(detail), 200)
        self.assertTrue(detail.startswith("first line second line "))

    def test_failed_ping_is_classified_per_tier(self):
        failed = {
            "session": "", "text": "",
            "usage": {"input": 0, "output": 0, "reasoning": 0,
                       "cache_read": 0, "cache_write": 0, "cost": 0.0},
            "errors": ["ProviderAuthError: bad key"], "throttled": False, "events": 0,
            "tools": [], "rc": 1, "reason": "", "note": "", "pid": 3, "duration": 0.1,
        }

        def run_once(cmd, cwd, env, out_path, err_path, stall_s=0, timeout_s=0):
            if Path(out_path).name == "doctor-ping-std.out.jsonl":
                return failed
            return self._fake_run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s)

        with mock.patch.object(hb_doctor, "classify", return_value="auth") as classify, \
             mock.patch.object(hb_doctor, "first_error", return_value="ProviderAuthError: bad key"):
            result = self._ping_doctor(run_once)

        std = result["tiers"]["std"]
        self.assertEqual((std["ok"], std["kind"], std["detail"]),
                         (False, "auth", "ProviderAuthError: bad key"))
        self.assertTrue(result["tiers"]["lite"]["ok"])
        self.assertTrue(result["ok"])
        classify.assert_called_once_with(1, ["ProviderAuthError: bad key"], "", "", False)


class TestProbeWebsearchExactMatch(EnvIsolatedTestCase):
    def _fake_result(self, tool_name):
        return {
            "session": "s1", "text": SENTINEL,
            "usage": {"input": 0, "output": 0, "reasoning": 0,
                       "cache_read": 0, "cache_write": 0, "cost": 0.0},
            "errors": [], "throttled": False, "events": 1,
            "tools": [{"tool": tool_name, "status": "completed",
                        "input": {}, "output": "ok"}],
            "rc": 0, "reason": "", "note": "", "pid": 1, "duration": 0.1,
        }

    def test_completed_codesearch_tool_does_not_set_websearch_on(self):
        with mock.patch.object(hb_doctor, "build_cmd", return_value=["opencode", "run"]), \
             mock.patch.object(hb_doctor, "config_env", return_value={}), \
             mock.patch.object(hb_doctor, "run_once", return_value=self._fake_result("codesearch")):
            result = hb_doctor._probe_websearch("opencode", _default_routing(), Path(self._tmp))
        self.assertFalse(result)

    def test_completed_websearch_tool_sets_websearch_on(self):
        with mock.patch.object(hb_doctor, "build_cmd", return_value=["opencode", "run"]), \
             mock.patch.object(hb_doctor, "config_env", return_value={}), \
             mock.patch.object(hb_doctor, "run_once", return_value=self._fake_result("websearch")):
            result = hb_doctor._probe_websearch("opencode", _default_routing(), Path(self._tmp))
        self.assertTrue(result)


class TestProbeWebsearchTier(EnvIsolatedTestCase):
    def _probed_model(self, routing):
        fake = {
            "session": "s1", "text": SENTINEL,
            "usage": {"input": 0, "output": 0, "reasoning": 0,
                       "cache_read": 0, "cache_write": 0, "cost": 0.0},
            "errors": [], "throttled": False, "events": 1, "tools": [],
            "rc": 0, "reason": "", "note": "", "pid": 1, "duration": 0.1,
        }
        with mock.patch.object(hb_doctor, "build_cmd", return_value=["opencode", "run"]) as build_cmd, \
             mock.patch.object(hb_doctor, "config_env", return_value={}), \
             mock.patch.object(hb_doctor, "run_once", return_value=fake):
            hb_doctor._probe_websearch("opencode", routing, Path(self._tmp))
        return build_cmd.call_args[0][2]

    def test_research_role_tier_is_probed(self):
        routing = _default_routing()
        routing["roles"]["research"] = "lite"
        self.assertEqual(self._probed_model(routing), "zai-coding-plan/glm-5.3-flash")

    def test_non_tier_research_role_uses_max_roles_tier(self):
        routing = _default_routing()
        routing["max_roles"]["research"] = "lite"
        self.assertEqual(self._probed_model(routing), "zai-coding-plan/glm-5.3-flash")

    def test_no_research_tier_falls_back_to_first_tier(self):
        routing = _default_routing()
        del routing["max_roles"]
        self.assertEqual(self._probed_model(routing), "zai-coding-plan/glm-5.3")


class TestVersionNormalization(EnvIsolatedTestCase):
    def _fake_subprocess_run_with_version(self, version_stdout):
        def _run(cmd, capture_output, text, timeout, stdin=None):
            if cmd[1] == "--version":
                return SimpleNamespace(returncode=0, stdout=version_stdout, stderr="")
            if cmd[1] == "models":
                return SimpleNamespace(
                    returncode=0,
                    stdout="zai-coding-plan/glm-5.3\nzai-coding-plan/glm-5.3-flash\n",
                    stderr="",
                )
            raise AssertionError("unexpected cmd %r" % (cmd,))
        return _run

    def test_prefixed_version_output_is_normalised_to_bare_number(self):
        with mock.patch.object(hb_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(hb_doctor.subprocess, "run",
                                side_effect=self._fake_subprocess_run_with_version("opencode v2.0.18\n")):
            result = hb_doctor.run_doctor("opencode", _default_routing(), False, Path(self._tmp))

        self.assertEqual(result["version"], "2.0.18")
        self.assertTrue(result["status_line"].startswith("opencode: v2.0.18 "))

    def test_bare_version_output_stays_bare(self):
        with mock.patch.object(hb_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(hb_doctor.subprocess, "run",
                                side_effect=self._fake_subprocess_run_with_version("2.0.18\n")):
            result = hb_doctor.run_doctor("opencode", _default_routing(), False, Path(self._tmp))

        self.assertEqual(result["version"], "2.0.18")
        self.assertTrue(result["status_line"].startswith("opencode: v2.0.18 "))

    def test_trailing_build_hash_does_not_win_over_version_number(self):
        with mock.patch.object(hb_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(hb_doctor.subprocess, "run",
                                side_effect=self._fake_subprocess_run_with_version(
                                    "opencode 2.0.18 (abc123)\n")):
            result = hb_doctor.run_doctor("opencode", _default_routing(), False, Path(self._tmp))

        self.assertEqual(result["version"], "2.0.18")
        self.assertTrue(result["status_line"].startswith("opencode: v2.0.18 "))

    def test_trailing_update_notice_line_does_not_win_over_version_number(self):
        with mock.patch.object(hb_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(hb_doctor.subprocess, "run",
                                side_effect=self._fake_subprocess_run_with_version(
                                    "opencode v2.0.18\nupdate available: run upgrade\n")):
            result = hb_doctor.run_doctor("opencode", _default_routing(), False, Path(self._tmp))

        self.assertEqual(result["version"], "2.0.18")
        self.assertTrue(result["status_line"].startswith("opencode: v2.0.18 "))

    def test_digit_free_multiline_output_falls_back_to_first_token(self):
        with mock.patch.object(hb_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(hb_doctor.subprocess, "run",
                                side_effect=self._fake_subprocess_run_with_version(
                                    "unknown build\nplease reinstall\n")):
            result = hb_doctor.run_doctor("opencode", _default_routing(), False, Path(self._tmp))

        self.assertEqual(result["version"], "unknown")
        self.assertNotIn("\n", result["status_line"])
        self.assertTrue(result["status_line"].startswith("opencode: vunknown "))


class TestPingTierTolerantSentinel(EnvIsolatedTestCase):
    def _tier(self):
        return {"model": "zai-coding-plan/glm-5.3", "variant": "high",
                "stall_s": 90, "timeout_s": 300}

    def _result(self, **overrides):
        result = {
            "session": "s1", "text": "",
            "usage": {"input": 0, "output": 0, "reasoning": 0,
                       "cache_read": 0, "cache_write": 0, "cost": 0.0},
            "errors": [], "throttled": False, "events": 1, "tools": [],
            "rc": 0, "reason": "", "note": "", "pid": 1, "duration": 0.1,
        }
        result.update(overrides)
        return result

    def _ping_with_result(self, fake_result):
        with mock.patch.object(hb_doctor, "build_cmd", return_value=["opencode", "run"]), \
             mock.patch.object(hb_doctor, "config_env", return_value={}), \
             mock.patch.object(hb_doctor, "run_once", return_value=fake_result):
            return hb_doctor._ping_tier("opencode", "std", self._tier(), Path(self._tmp))

    def _ping_with_text(self, text):
        return self._ping_with_result(self._result(text=text))

    def test_reply_with_trailing_period_is_ok(self):
        ok, kind, detail = self._ping_with_text("HB-LANE-OK.")
        self.assertTrue(ok)
        self.assertEqual((kind, detail), ("", "ping ok"))

    def test_reply_wrapped_in_backticks_is_ok(self):
        ok, kind, detail = self._ping_with_text("`HB-LANE-OK`")
        self.assertTrue(ok)
        self.assertEqual((kind, detail), ("", "ping ok"))

    def test_reply_mentioning_sentinel_in_sentence_is_not_ok(self):
        ok, kind, detail = self._ping_with_text("I will not say HB-LANE-OK")
        self.assertFalse(ok)

    def test_failed_ping_passes_run_details_to_classify(self):
        (Path(self._tmp) / "doctor-ping-std.err").write_text("stalled\n")
        fake = self._result(rc=-9, reason="stall", note="no output for 90s", finished=False)
        with mock.patch.object(hb_doctor, "classify", return_value="stall") as classify, \
             mock.patch.object(hb_doctor, "first_error", return_value=""):
            ok, kind, detail = self._ping_with_result(fake)
        classify.assert_called_once_with(-9, [], "stalled", "stall", False)
        self.assertEqual((ok, kind, detail), (False, "stall", "no output for 90s"))

    def test_failed_ping_passes_finished_flag_and_error_detail(self):
        fake = self._result(rc=1, text="nope", errors=["ProviderAuthError: bad key"], finished=True)
        with mock.patch.object(hb_doctor, "classify", return_value="auth") as classify, \
             mock.patch.object(hb_doctor, "first_error", return_value="ProviderAuthError: bad key"):
            ok, kind, detail = self._ping_with_result(fake)
        classify.assert_called_once_with(1, ["ProviderAuthError: bad key"], "", "", True)
        self.assertEqual((ok, kind, detail), (False, "auth", "ProviderAuthError: bad key"))


if __name__ == "__main__":
    unittest.main()
