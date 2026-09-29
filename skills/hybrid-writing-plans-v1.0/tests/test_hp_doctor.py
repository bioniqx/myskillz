import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hp_doctor
from hp_config import AGENT_NAME, SENTINEL

MODELS_OUT = "zai-coding-plan/glm-5.3\nzai-coding-plan/glm-5.3-flash\n"
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
UNAVAILABLE_LINE = "opencode: unavailable → preset claude (run plan_tool.py doctor --ping)"


def _routing():
    return {
        "preset": "hybrid",
        "tiers": {
            "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high",
                    "max_parallel": 6, "stall_s": 180, "timeout_s": 900},
            "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low",
                     "max_parallel": 6, "stall_s": 120, "timeout_s": 600},
        },
        "roles": {"light": "lite", "std": "std", "deep": "claude"},
        "max_roles": {"deep": "std"},
        "review_oc": {"hybrid": "all", "max": "risky"},
        "oc_group_max": 3, "max_repairs": 2, "throttle_cooldown_s": 120,
    }


def _doctor():
    return {
        "t": "2026-09-28T12:00:00Z",
        "ok": True,
        "version": "2.0.18",
        "binary": "/usr/bin/opencode",
        "tiers": {
            "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high",
                    "listed": True, "ping": "ok", "note": SENTINEL, "down": None},
            "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low",
                     "listed": True, "ping": "ok", "note": SENTINEL, "down": None},
        },
    }


def _result(text="", reason="", errors=None, note=""):
    return {
        "session": "s1", "text": text,
        "usage": {"input": 1, "output": 1, "reasoning": 0,
                  "cache_read": 0, "cache_write": 0, "cost": 0.0},
        "errors": list(errors or []), "throttled": reason == "throttle",
        "events": 1, "tools": [],
        "rc": 1 if reason else 0, "reason": reason, "note": note,
        "pid": 1, "duration": 0.1,
    }


class EnvIsolatedTestCase(unittest.TestCase):
    def setUp(self):
        self._saved_environ = dict(os.environ)
        self._tmp = tempfile.mkdtemp()
        tmp = Path(self._tmp)
        os.environ["HOME"] = self._tmp
        os.environ["HP_ROUTING"] = str(tmp / "cfg" / "routing.json")
        os.environ["HP_DOCTOR_CACHE"] = str(tmp / "cache" / "doctor.json")
        os.environ["HP_TELEMETRY"] = str(tmp / "cache" / "lanes.jsonl")

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_environ)
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestDoctorCachePath(EnvIsolatedTestCase):
    def test_default_path_under_home_cache(self):
        os.environ.pop("HP_DOCTOR_CACHE", None)
        self.assertEqual(
            hp_doctor.doctor_cache_path(),
            Path(self._tmp) / ".cache" / "hybrid-writing-plans" / "doctor.json",
        )

    def test_env_override(self):
        override = Path(self._tmp) / "custom" / "doctor.json"
        os.environ["HP_DOCTOR_CACHE"] = str(override)
        self.assertEqual(hp_doctor.doctor_cache_path(), override)

    def test_models_timeout_constant(self):
        self.assertEqual(hp_doctor.MODELS_TIMEOUT_S, 60)


class TestLoadWriteDoctor(EnvIsolatedTestCase):
    def test_load_missing_file_returns_empty_dict(self):
        self.assertEqual(hp_doctor.load_doctor(Path(self._tmp) / "nope" / "doctor.json"), {})

    def test_load_unparseable_file_returns_empty_dict(self):
        path = Path(self._tmp) / "doctor.json"
        path.write_text("{not json")
        self.assertEqual(hp_doctor.load_doctor(path), {})

    def test_load_non_dict_returns_empty_dict(self):
        path = Path(self._tmp) / "doctor.json"
        path.write_text("[1, 2]")
        self.assertEqual(hp_doctor.load_doctor(path), {})

    def test_write_then_load_round_trips(self):
        path = Path(self._tmp) / "cache" / "deeper" / "doctor.json"
        data = _doctor()
        hp_doctor.write_doctor(path, data)
        self.assertTrue(path.is_file())
        self.assertEqual(hp_doctor.load_doctor(path), data)
        self.assertEqual(json.loads(path.read_text()), data)

    def test_write_goes_through_temp_file_in_same_dir_and_os_replace(self):
        path = Path(self._tmp) / "cache" / "doctor.json"
        seen = []
        real_replace = os.replace

        def spy(src, dst):
            seen.append((Path(src), Path(dst), json.loads(Path(src).read_text())))
            real_replace(src, dst)

        with mock.patch.object(hp_doctor.os, "replace", side_effect=spy):
            hp_doctor.write_doctor(path, _doctor())
        self.assertEqual(len(seen), 1)
        src, dst, content = seen[0]
        self.assertEqual(dst, path)
        self.assertNotEqual(src, path)
        self.assertEqual(src.parent, path.parent)
        self.assertEqual(content, _doctor())
        self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["doctor.json"])
        self.assertEqual(hp_doctor.load_doctor(path), _doctor())

    def test_failed_replace_keeps_old_target_and_cleans_temp(self):
        path = Path(self._tmp) / "cache" / "doctor.json"
        hp_doctor.write_doctor(path, {"old": True})
        with mock.patch.object(hp_doctor.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                hp_doctor.write_doctor(path, _doctor())
        self.assertEqual(hp_doctor.load_doctor(path), {"old": True})
        self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["doctor.json"])


class TestClassifyError(unittest.TestCase):
    def test_unavailable_patterns(self):
        for message in (
            "APIError: Your coding plan has expired",
            "Please renew your subscription",
            "Model unavailable for this account",
            "401 Unauthorized",
            "request unauthorised",
            "ProviderError: Invalid API key",
            "Insufficient balance",
            "insufficient quota for model",
        ):
            self.assertEqual(hp_doctor.classify_error(message), "unavailable", message)

    def test_unavailable_wins_over_throttle(self):
        self.assertEqual(hp_doctor.classify_error("429: plan expired"), "unavailable")

    def test_throttle_patterns(self):
        for message in ("APIError: 429 Too Many Requests", "rate limit exceeded",
                        "Rate-limited, retry later", "ratelimit hit"):
            self.assertEqual(hp_doctor.classify_error(message), "throttle", message)

    def test_other_errors_are_unclassified(self):
        self.assertEqual(hp_doctor.classify_error("boom: connection reset"), "")
        self.assertEqual(hp_doctor.classify_error(""), "")


class TestMarkDown(EnvIsolatedTestCase):
    def test_mark_down_sets_entry_and_keeps_the_rest(self):
        path = Path(self._tmp) / "cache" / "doctor.json"
        hp_doctor.write_doctor(path, _doctor())
        hp_doctor.mark_down(path, "std", "unavailable",
                            "APIError: plan expired\nRenew at https://example.invalid")
        loaded = hp_doctor.load_doctor(path)
        down = loaded["tiers"]["std"]["down"]
        self.assertEqual(down["reason"], "unavailable")
        self.assertEqual(down["message"], "APIError: plan expired")
        self.assertRegex(down["at"], UTC_RE)
        self.assertIsNone(loaded["tiers"]["lite"]["down"])
        self.assertTrue(loaded["tiers"]["std"]["listed"])
        self.assertEqual(loaded["version"], "2.0.18")
        self.assertTrue(loaded["ok"])

    def test_mark_down_creates_missing_file_and_tier(self):
        path = Path(self._tmp) / "fresh" / "doctor.json"
        hp_doctor.mark_down(path, "lite", "unavailable", "insufficient balance")
        loaded = hp_doctor.load_doctor(path)
        self.assertEqual(loaded["tiers"]["lite"]["down"]["reason"], "unavailable")
        self.assertEqual(loaded["tiers"]["lite"]["down"]["message"], "insufficient balance")


class TestStatusLine(EnvIsolatedTestCase):
    def test_unavailable_when_doctor_missing(self):
        self.assertEqual(hp_doctor.status_line(_routing(), {}), UNAVAILABLE_LINE)

    def test_unavailable_when_version_missing(self):
        doctor = _doctor()
        doctor["version"] = ""
        self.assertEqual(hp_doctor.status_line(_routing(), doctor), UNAVAILABLE_LINE)

    def test_unavailable_when_not_ok(self):
        doctor = _doctor()
        doctor["ok"] = False
        self.assertEqual(hp_doctor.status_line(_routing(), doctor), UNAVAILABLE_LINE)

    def test_matches_spec_example(self):
        self.assertEqual(
            hp_doctor.status_line(_routing(), _doctor()),
            "opencode: v2.0.18 preset=hybrid light=oc:lite std=oc:std deep=claude "
            "review_oc=all (doctor 2026-09-28)",
        )

    def test_down_tier_shows_reason(self):
        doctor = _doctor()
        doctor["tiers"]["std"]["down"] = {"reason": "unavailable", "message": "expired",
                                          "at": "2026-09-28T12:05:00Z"}
        self.assertEqual(
            hp_doctor.status_line(_routing(), doctor),
            "opencode: v2.0.18 preset=hybrid light=oc:lite std=claude(down: unavailable) "
            "deep=claude review_oc=all (doctor 2026-09-28)",
        )

    def test_mark_down_then_status_line(self):
        path = Path(self._tmp) / "cache" / "doctor.json"
        hp_doctor.write_doctor(path, _doctor())
        hp_doctor.mark_down(path, "lite", "unavailable", "Invalid API key")
        line = hp_doctor.status_line(_routing(), hp_doctor.load_doctor(path))
        self.assertIn(" light=claude(down: unavailable) ", line)
        self.assertIn(" std=oc:std ", line)

    def test_max_preset_override(self):
        self.assertEqual(
            hp_doctor.status_line(_routing(), _doctor(), "max"),
            "opencode: v2.0.18 preset=max light=oc:lite std=oc:std deep=oc:std "
            "review_oc=risky (doctor 2026-09-28)",
        )

    def test_claude_preset_routes_everything_to_claude(self):
        doctor = _doctor()
        doctor["tiers"]["std"]["down"] = {"reason": "unavailable", "message": "expired",
                                          "at": "2026-09-28T12:05:00Z"}
        line = hp_doctor.status_line(_routing(), doctor, "claude")
        self.assertTrue(line.startswith(
            "opencode: v2.0.18 preset=claude light=claude std=claude deep=claude review_oc="))
        self.assertNotIn("down", line)
        self.assertTrue(line.endswith(" (doctor 2026-09-28)"))


class TestRunDoctor(EnvIsolatedTestCase):
    def _subprocess_fake(self, version_out="2.0.18\n", models_failures=0, models_out=MODELS_OUT):
        calls = []
        state = {"models": 0}

        def _run(cmd, **kwargs):
            calls.append((cmd[1], kwargs.get("timeout")))
            if cmd[1] == "--version":
                return SimpleNamespace(returncode=0, stdout=version_out, stderr="")
            if cmd[1] == "models":
                state["models"] += 1
                if state["models"] <= models_failures:
                    return SimpleNamespace(returncode=1, stdout="", stderr="boom")
                return SimpleNamespace(returncode=0, stdout=models_out, stderr="")
            raise AssertionError("unexpected cmd %r" % (cmd,))

        return _run, calls

    def _no_run_once(self, *args, **kwargs):
        raise AssertionError("run_once must not be called without ping")

    def _doctor_run(self, ping=False, previous=None, run_once_fake=None, **fake_kwargs):
        fake, calls = self._subprocess_fake(**fake_kwargs)
        with mock.patch.object(hp_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(hp_doctor.subprocess, "run", side_effect=fake), \
             mock.patch.object(hp_doctor, "config_env", return_value={}), \
             mock.patch.object(hp_doctor, "run_once",
                               side_effect=run_once_fake or self._no_run_once):
            result = hp_doctor.run_doctor("opencode", _routing(), ping,
                                          Path(self._tmp) / "work", previous or {})
        return result, calls

    def _ping_fake(self, result, seen=None):
        def _run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            if seen is not None:
                seen.append({"cmd": list(cmd), "cwd": Path(cwd), "stall_s": stall_s,
                             "timeout_s": timeout_s})
            return result
        return _run_once

    def _down(self):
        return {"reason": "unavailable", "message": "expired", "at": "2026-09-27T08:00:00Z"}

    def _previous_with_std_down(self):
        previous = _doctor()
        previous["tiers"]["std"]["down"] = self._down()
        return previous

    def test_plain_doctor_checks_version_and_models(self):
        result, calls = self._doctor_run()
        self.assertEqual(set(result), {"t", "ok", "version", "binary", "tiers"})
        self.assertRegex(result["t"], UTC_RE)
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "2.0.18")
        self.assertEqual(result["binary"], "/usr/bin/opencode")
        std = result["tiers"]["std"]
        self.assertEqual(std["model"], "zai-coding-plan/glm-5.3")
        self.assertEqual(std["variant"], "high")
        self.assertTrue(std["listed"])
        self.assertEqual(std["ping"], "unchecked")
        self.assertIsNone(std["down"])
        self.assertIsInstance(std["note"], str)
        self.assertTrue(result["tiers"]["lite"]["listed"])
        self.assertIn(("--version", 10), calls)
        self.assertIn(("models", 60), calls)

    def test_version_output_is_normalised(self):
        result, _calls = self._doctor_run(version_out="opencode v2.0.18 (abc123)\nupdate available\n")
        self.assertEqual(result["version"], "2.0.18")

    def test_models_are_retried_once(self):
        result, calls = self._doctor_run(models_failures=1)
        self.assertTrue(result["ok"])
        self.assertTrue(result["tiers"]["std"]["listed"])
        self.assertEqual([c for c in calls if c[0] == "models"], [("models", 60), ("models", 60)])

    def test_models_failing_twice_is_not_ok(self):
        result, calls = self._doctor_run(models_failures=2)
        self.assertFalse(result["ok"])
        self.assertFalse(result["tiers"]["std"]["listed"])
        self.assertFalse(result["tiers"]["lite"]["listed"])
        self.assertEqual(len([c for c in calls if c[0] == "models"]), 2)

    def test_unlisted_model(self):
        result, _calls = self._doctor_run(models_out="zai-coding-plan/glm-5.3\n")
        self.assertTrue(result["ok"])
        self.assertTrue(result["tiers"]["std"]["listed"])
        self.assertFalse(result["tiers"]["lite"]["listed"])
        self.assertIn("zai-coding-plan/glm-5.3-flash", result["tiers"]["lite"]["note"])

    def test_plain_doctor_keeps_previous_down(self):
        result, _calls = self._doctor_run(previous=self._previous_with_std_down())
        self.assertEqual(result["tiers"]["std"]["down"], self._down())
        self.assertEqual(result["tiers"]["std"]["ping"], "unchecked")
        self.assertIsNone(result["tiers"]["lite"]["down"])

    def test_ping_ok_clears_down_and_uses_the_writer_agent(self):
        seen = []
        result, _calls = self._doctor_run(
            ping=True, previous=self._previous_with_std_down(),
            run_once_fake=self._ping_fake(_result(text=SENTINEL), seen))
        std = result["tiers"]["std"]
        self.assertEqual(std["ping"], "ok")
        self.assertIsNone(std["down"])
        self.assertEqual(result["tiers"]["lite"]["ping"], "ok")
        self.assertEqual(len(seen), 2)
        std_call = [s for s in seen if "zai-coding-plan/glm-5.3#high" in s["cmd"]][0]
        self.assertIn("--agent", std_call["cmd"])
        self.assertEqual(std_call["cmd"][std_call["cmd"].index("--agent") + 1], AGENT_NAME)
        self.assertEqual(std_call["stall_s"], 180)
        self.assertEqual(std_call["timeout_s"], 900)
        self.assertEqual(std_call["cwd"], Path(self._tmp) / "work")
        self.assertTrue((Path(self._tmp) / "work").is_dir())

    def test_ping_tolerates_punctuation_and_backticks(self):
        for text in ("`%s`." % SENTINEL, "Sure.\n%s!" % SENTINEL, "'%s'" % SENTINEL):
            result, _calls = self._doctor_run(
                ping=True, run_once_fake=self._ping_fake(_result(text=text)))
            self.assertEqual(result["tiers"]["std"]["ping"], "ok", text)

    def test_ping_sentence_mentioning_sentinel_fails(self):
        result, _calls = self._doctor_run(
            ping=True, run_once_fake=self._ping_fake(_result(text="I will not say %s" % SENTINEL)))
        self.assertEqual(result["tiers"]["std"]["ping"], "failed")
        self.assertIsNone(result["tiers"]["std"]["down"])
        self.assertTrue(result["ok"])

    def test_ping_unavailable_marks_down_with_first_line(self):
        failed = _result(reason="unavailable", errors=[
            "APIError: Your coding plan has expired\nRenew at https://example.invalid"])
        result, _calls = self._doctor_run(ping=True, run_once_fake=self._ping_fake(failed))
        std = result["tiers"]["std"]
        self.assertEqual(std["ping"], "failed")
        self.assertEqual(std["down"]["reason"], "unavailable")
        self.assertEqual(std["down"]["message"], "APIError: Your coding plan has expired")
        self.assertRegex(std["down"]["at"], UTC_RE)
        self.assertEqual(std["note"], "APIError: Your coding plan has expired")
        self.assertTrue(result["ok"])

    def test_ping_error_text_is_classified_even_on_crash(self):
        failed = _result(reason="crash", errors=["ProviderError: Invalid API key"])
        result, _calls = self._doctor_run(ping=True, run_once_fake=self._ping_fake(failed))
        self.assertEqual(result["tiers"]["lite"]["down"]["reason"], "unavailable")
        self.assertEqual(result["tiers"]["lite"]["down"]["message"], "ProviderError: Invalid API key")

    def test_ping_throttle_does_not_mark_down(self):
        failed = _result(reason="throttle", errors=["APIError: 429 Too Many Requests"])
        result, _calls = self._doctor_run(ping=True, run_once_fake=self._ping_fake(failed))
        std = result["tiers"]["std"]
        self.assertEqual(std["ping"], "failed")
        self.assertIsNone(std["down"])
        self.assertEqual(std["note"], "APIError: 429 Too Many Requests")

    def test_ping_throttle_keeps_previous_down(self):
        failed = _result(reason="throttle", errors=["APIError: rate limit exceeded"])
        result, _calls = self._doctor_run(ping=True, previous=self._previous_with_std_down(),
                                          run_once_fake=self._ping_fake(failed))
        self.assertEqual(result["tiers"]["std"]["down"], self._down())

    def test_status_line_from_run_doctor_result(self):
        result, _calls = self._doctor_run()
        line = hp_doctor.status_line(_routing(), result)
        self.assertTrue(line.startswith(
            "opencode: v2.0.18 preset=hybrid light=oc:lite std=oc:std deep=claude review_oc=all "))


if __name__ == "__main__":
    unittest.main()
