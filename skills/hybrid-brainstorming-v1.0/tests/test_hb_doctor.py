import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hb_doctor
from hb_config import SENTINEL


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


def _default_doctor():
    return {
        "t": "2026-09-28T12:00:00Z",
        "ok": True,
        "version": "2.0.18",
        "binary": "opencode",
        "tiers": {
            "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high",
                     "ok": True, "note": SENTINEL},
            "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low",
                      "ok": True, "note": SENTINEL},
        },
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
        line = hb_doctor.status_line(_default_routing(), _default_doctor())
        self.assertEqual(
            line,
            "opencode: v2.0.18 preset=hybrid locate=oc:lite explore=oc:std "
            "fact=oc:lite research=claude draft=claude websearch=off "
            "(doctor 2026-09-28)",
        )


class TestRunDoctor(EnvIsolatedTestCase):
    def _fake_subprocess_run(self, cmd, capture_output, text, timeout):
        if cmd[1] == "--version":
            return SimpleNamespace(returncode=0, stdout="2.0.18\n", stderr="")
        if cmd[1] == "models":
            return SimpleNamespace(
                returncode=0,
                stdout="zai-coding-plan/glm-5.3\nzai-coding-plan/glm-5.3-flash\n",
                stderr="",
            )
        raise AssertionError("unexpected cmd %r" % (cmd,))

    def test_run_doctor_without_ping_checks_binary_and_models(self):
        with mock.patch.object(hb_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(hb_doctor.subprocess, "run", side_effect=self._fake_subprocess_run):
            result = hb_doctor.run_doctor("opencode", _default_routing(), False, Path(self._tmp))

        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "2.0.18")
        self.assertEqual(result["binary"], "/usr/bin/opencode")
        self.assertTrue(result["tiers"]["std"]["ok"])
        self.assertTrue(result["tiers"]["lite"]["ok"])
        self.assertFalse(result["websearch"])
        self.assertIn("opencode: v2.0.18", result["status_line"])

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

    def test_run_doctor_with_ping_probes_tiers_and_websearch(self):
        with mock.patch.object(hb_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(hb_doctor.subprocess, "run", side_effect=self._fake_subprocess_run), \
             mock.patch.object(hb_doctor, "build_cmd", return_value=["opencode", "run"]), \
             mock.patch.object(hb_doctor, "config_env", return_value={}), \
             mock.patch.object(hb_doctor, "run_once", side_effect=self._fake_run_once):
            result = hb_doctor.run_doctor("opencode", _default_routing(), True, Path(self._tmp))

        self.assertTrue(result["ok"])
        self.assertTrue(result["websearch"])
        self.assertEqual(result["tiers"]["std"]["note"], SENTINEL)
        self.assertEqual(result["tiers"]["lite"]["note"], SENTINEL)


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


class TestVersionNormalization(EnvIsolatedTestCase):
    def _fake_subprocess_run_with_version(self, version_stdout):
        def _run(cmd, capture_output, text, timeout):
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

    def _ping_with_text(self, text):
        fake_result = {
            "session": "s1", "text": text,
            "usage": {"input": 0, "output": 0, "reasoning": 0,
                       "cache_read": 0, "cache_write": 0, "cost": 0.0},
            "errors": [], "throttled": False, "events": 1, "tools": [],
            "rc": 0, "reason": "", "note": "", "pid": 1, "duration": 0.1,
        }
        with mock.patch.object(hb_doctor, "build_cmd", return_value=["opencode", "run"]), \
             mock.patch.object(hb_doctor, "config_env", return_value={}), \
             mock.patch.object(hb_doctor, "run_once", return_value=fake_result):
            return hb_doctor._ping_tier("opencode", "std", self._tier(), Path(self._tmp))

    def test_reply_with_trailing_period_is_ok(self):
        ok, note = self._ping_with_text("HB-LANE-OK.")
        self.assertTrue(ok)

    def test_reply_wrapped_in_backticks_is_ok(self):
        ok, note = self._ping_with_text("`HB-LANE-OK`")
        self.assertTrue(ok)

    def test_reply_mentioning_sentinel_in_sentence_is_not_ok(self):
        ok, note = self._ping_with_text("I will not say HB-LANE-OK")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
