import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ha_doctor
from ha_config import AGENT_NAMES, SENTINEL

MODELS_OUT = "zai-coding-plan/glm-5.3\nzai-coding-plan/glm-5.3-flash\n"
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
UNAVAILABLE_LINE = "opencode: unavailable → preset claude (run audit.py doctor --ping)"
UNAVAILABLE_HYBRID = "opencode: unavailable preset=hybrid (run audit.py doctor --ping)"
NOW = 1_800_000_000.0
ENTRY_KEYS = {"ok", "key", "checked_at", "kind", "detail"}


def _routing():
    return {
        "preset": "hybrid",
        "tiers": {
            "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high",
                    "max_parallel": 6, "stall_s": 180, "timeout_s": 900},
            "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low",
                     "max_parallel": 6, "stall_s": 120, "timeout_s": 600},
        },
        "roles": {"investigator": "std", "verifier": "claude", "parser": "claude"},
        "max_roles": {"verifier": "std", "parser": "std"},
        "oc_batch_max": 4, "max_repairs": 2, "throttle_cooldown_s": 120,
    }


def _entry(tier, ok=True, kind="", detail="listed", checked_at=NOW):
    return {"ok": ok, "key": ha_doctor.cache_key(tier), "checked_at": checked_at,
            "kind": kind, "detail": detail}


def _doctor(routing=None, checked_at=NOW):
    tiers = (routing or _routing())["tiers"]
    return {
        "t": "2026-09-28T12:00:00Z",
        "ok": True,
        "version": "2.0.18",
        "binary": "/usr/bin/opencode",
        "tiers": {name: _entry(tiers[name], detail=SENTINEL, checked_at=checked_at)
                  for name in ("std", "lite")},
    }


def _result(text="", reason="", errors=None, note="", finished=False):
    return {
        "session": "s1", "text": text,
        "usage": {"input": 1, "output": 1, "reasoning": 0,
                  "cache_read": 0, "cache_write": 0, "cost": 0.0},
        "errors": list(errors or []), "throttled": reason == "throttle",
        "events": 1, "tools": [], "finished": finished,
        "rc": 1 if reason else 0, "reason": reason, "note": note,
        "pid": 1, "duration": 0.1,
    }


class EnvIsolatedTestCase(unittest.TestCase):
    def setUp(self):
        self._saved_environ = dict(os.environ)
        self._tmp = tempfile.mkdtemp()
        tmp = Path(self._tmp)
        os.environ["HOME"] = self._tmp
        os.environ["HA_ROUTING"] = str(tmp / "cfg" / "routing.json")
        os.environ["HA_DOCTOR_CACHE"] = str(tmp / "cache" / "doctor.json")
        os.environ["HA_TELEMETRY"] = str(tmp / "cache" / "lanes.jsonl")
        os.environ["HYBRID_OPENCODE_STD"] = "zai-coding-plan/glm-5.3#high"
        os.environ["HYBRID_OPENCODE_LITE"] = "zai-coding-plan/glm-5.3-flash#low"
        os.environ["XDG_DATA_HOME"] = str(tmp / "data")
        os.environ.pop("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_environ)
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestDoctorCachePath(EnvIsolatedTestCase):
    def test_default_path_under_home_cache(self):
        os.environ.pop("HA_DOCTOR_CACHE", None)
        self.assertEqual(
            ha_doctor.doctor_cache_path(),
            Path(self._tmp) / ".cache" / "hybrid-requirements-code-audit" / "doctor.json",
        )

    def test_env_override(self):
        override = Path(self._tmp) / "custom" / "doctor.json"
        os.environ["HA_DOCTOR_CACHE"] = str(override)
        self.assertEqual(ha_doctor.doctor_cache_path(), override)

    def test_constants(self):
        self.assertEqual(ha_doctor.MODELS_TIMEOUT_S, 60)
        self.assertEqual(ha_doctor.VERSION_TIMEOUT_S, 10)
        self.assertEqual(ha_doctor.UNAVAILABLE_LINE, UNAVAILABLE_LINE)


class TestLoadWriteDoctor(EnvIsolatedTestCase):
    def test_load_missing_file_returns_empty_dict(self):
        self.assertEqual(ha_doctor.load_doctor(Path(self._tmp) / "nope" / "doctor.json"), {})

    def test_load_unparseable_file_returns_empty_dict(self):
        path = Path(self._tmp) / "doctor.json"
        path.write_text("{not json")
        self.assertEqual(ha_doctor.load_doctor(path), {})

    def test_load_non_dict_returns_empty_dict(self):
        path = Path(self._tmp) / "doctor.json"
        path.write_text("[1, 2]")
        self.assertEqual(ha_doctor.load_doctor(path), {})

    def test_write_then_load_round_trips(self):
        path = Path(self._tmp) / "cache" / "deeper" / "doctor.json"
        data = _doctor()
        ha_doctor.write_doctor(path, data)
        self.assertTrue(path.is_file())
        self.assertEqual(ha_doctor.load_doctor(path), data)
        self.assertEqual(json.loads(path.read_text()), data)

    def test_write_goes_through_temp_file_in_same_dir_and_os_replace(self):
        path = Path(self._tmp) / "cache" / "doctor.json"
        seen = []
        real_replace = os.replace

        def spy(src, dst):
            seen.append((Path(src), Path(dst), json.loads(Path(src).read_text())))
            real_replace(src, dst)

        with mock.patch.object(ha_doctor.os, "replace", side_effect=spy):
            ha_doctor.write_doctor(path, _doctor())
        self.assertEqual(len(seen), 1)
        src, dst, content = seen[0]
        self.assertEqual(dst, path)
        self.assertNotEqual(src, path)
        self.assertEqual(src.parent, path.parent)
        self.assertEqual(content, _doctor())
        self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["doctor.json"])

    def test_failed_replace_keeps_old_target_and_cleans_temp(self):
        path = Path(self._tmp) / "cache" / "doctor.json"
        ha_doctor.write_doctor(path, {"old": True})
        with mock.patch.object(ha_doctor.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                ha_doctor.write_doctor(path, _doctor())
        self.assertEqual(ha_doctor.load_doctor(path), {"old": True})
        self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["doctor.json"])


class TestStatusLine(EnvIsolatedTestCase):
    def _line(self, doctor, preset="", routing=None, now=NOW):
        return ha_doctor.status_line(routing or _routing(), doctor, preset, now)

    def test_unavailable_when_doctor_missing(self):
        self.assertEqual(self._line({}), UNAVAILABLE_HYBRID)

    def test_unavailable_when_version_missing(self):
        doctor = _doctor()
        doctor["version"] = ""
        self.assertEqual(self._line(doctor), UNAVAILABLE_HYBRID)

    def test_unavailable_when_not_ok(self):
        doctor = _doctor()
        doctor["ok"] = False
        self.assertEqual(self._line(doctor), UNAVAILABLE_HYBRID)

    def test_unavailable_names_the_effective_preset_and_never_claims_claude(self):
        self.assertEqual(self._line({}, "claude"),
                         "opencode: unavailable preset=claude (run audit.py doctor --ping)")
        self.assertNotIn("→", self._line({}))

    def test_matches_spec_example(self):
        self.assertEqual(
            self._line(_doctor()),
            "opencode: v2.0.18 preset=hybrid investigator=oc:std verifier=claude "
            "parser=claude (doctor 2026-09-28)",
        )

    def test_failed_tier_shows_its_kind(self):
        doctor = _doctor()
        doctor["tiers"]["std"] = _entry(_routing()["tiers"]["std"], ok=False, kind="auth",
                                        detail="Invalid API key")
        self.assertEqual(
            self._line(doctor),
            "opencode: v2.0.18 preset=hybrid investigator=claude(down: auth) "
            "verifier=claude parser=claude (doctor 2026-09-28)",
        )

    def test_one_failed_tier_leaves_the_other_tier_usable(self):
        routing = _routing()
        routing["roles"]["parser"] = "lite"
        doctor = _doctor(routing)
        doctor["tiers"]["std"] = _entry(routing["tiers"]["std"], ok=False, kind="model",
                                        detail="model not found")
        line = self._line(doctor, routing=routing)
        self.assertIn(" investigator=claude(down: model) ", line)
        self.assertTrue(line.endswith(" parser=oc:lite (doctor 2026-09-28)"))

    def test_stale_entry_is_reported_as_stale(self):
        self.assertEqual(
            self._line(_doctor(), now=NOW + 3600),
            "opencode: v2.0.18 preset=hybrid investigator=claude(stale) "
            "verifier=claude parser=claude (doctor 2026-09-28)",
        )

    def test_edited_model_invalidates_the_entry_at_once(self):
        routing = _routing()
        doctor = _doctor(routing)
        routing["tiers"]["std"]["model"] = "zai-coding-plan/glm-5.4"
        self.assertIn(" investigator=claude(stale) ", self._line(doctor, routing=routing))

    def test_claude_preset_routes_everything_to_claude(self):
        doctor = _doctor()
        doctor["tiers"]["std"] = _entry(_routing()["tiers"]["std"], ok=False, kind="quota",
                                        detail="plan expired")
        self.assertEqual(
            self._line(doctor, "claude"),
            "opencode: v2.0.18 preset=claude investigator=claude verifier=claude "
            "parser=claude (doctor 2026-09-28)",
        )

    def test_opencode_preset_reports_held_units(self):
        doctor = _doctor()
        with mock.patch.object(ha_doctor, "effective_preset", return_value="opencode"), \
             mock.patch.object(ha_doctor, "role_tier", return_value="std"):
            self.assertEqual(
                self._line(doctor),
                "opencode: v2.0.18 preset=opencode investigator=oc:std verifier=oc:std "
                "parser=oc:std (doctor 2026-09-28)",
            )
            doctor["tiers"]["std"] = _entry(_routing()["tiers"]["std"], ok=False, kind="quota",
                                            detail="plan expired")
            self.assertEqual(
                self._line(doctor),
                "opencode: v2.0.18 preset=opencode investigator=held(down: quota) "
                "verifier=held(down: quota) parser=held(down: quota) (doctor 2026-09-28)",
            )

    def test_tier_missing_from_routing_or_cache_is_claude(self):
        routing = _routing()
        routing["roles"]["investigator"] = "ghost"
        self.assertIn(" investigator=claude ", self._line(_doctor(), routing=routing))
        doctor = _doctor()
        del doctor["tiers"]["std"]
        self.assertIn(" investigator=claude ", self._line(doctor))

    def test_lite_role_routes_to_lite(self):
        routing = _routing()
        routing["roles"]["parser"] = "lite"
        self.assertTrue(self._line(_doctor(), routing=routing).endswith(
            " parser=oc:lite (doctor 2026-09-28)"))


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
        raise AssertionError("run_once must not be called here")

    def _doctor_run(self, ping=False, previous=None, run_once_fake=None, routing=None,
                    **fake_kwargs):
        fake, calls = self._subprocess_fake(**fake_kwargs)
        with mock.patch.object(ha_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
             mock.patch.object(ha_doctor.subprocess, "run", side_effect=fake), \
             mock.patch.object(ha_doctor, "config_env", return_value={}), \
             mock.patch.object(ha_doctor, "run_once",
                               side_effect=run_once_fake or self._no_run_once):
            result = ha_doctor.run_doctor("opencode", routing or _routing(), ping,
                                          Path(self._tmp) / "work", previous or {})
        return result, calls

    def _ping_fake(self, result, seen=None):
        def _run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            if seen is not None:
                seen.append({"cmd": list(cmd), "cwd": Path(cwd), "stall_s": stall_s,
                             "timeout_s": timeout_s, "out_path": Path(out_path)})
            return result
        return _run_once

    def _previous(self, age=30.0):
        return _doctor(checked_at=time.time() - age)

    def _failed_std(self, age=30.0):
        return _entry(_routing()["tiers"]["std"], ok=False, kind="auth",
                      detail="Invalid API key", checked_at=time.time() - age)

    def test_plain_doctor_checks_version_and_models(self):
        before = time.time()
        result, calls = self._doctor_run()
        self.assertEqual(set(result), {"t", "ok", "version", "binary", "tiers"})
        self.assertRegex(result["t"], UTC_RE)
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "2.0.18")
        self.assertEqual(result["binary"], "/usr/bin/opencode")
        std = result["tiers"]["std"]
        self.assertEqual(set(std), ENTRY_KEYS)
        self.assertTrue(std["ok"])
        self.assertEqual(std["key"], ha_doctor.cache_key(_routing()["tiers"]["std"]))
        self.assertNotEqual(std["key"], result["tiers"]["lite"]["key"])
        self.assertGreaterEqual(std["checked_at"], before)
        self.assertLessEqual(std["checked_at"], time.time())
        self.assertEqual(std["kind"], "")
        self.assertEqual(std["detail"], "listed")
        self.assertTrue(result["tiers"]["lite"]["ok"])
        self.assertIn(("--version", 10), calls)
        self.assertIn(("models", 60), calls)

    def test_version_output_is_normalised(self):
        result, _calls = self._doctor_run(version_out="opencode v2.0.18 (abc123)\nupdate available\n")
        self.assertEqual(result["version"], "2.0.18")

    def test_models_are_retried_once(self):
        result, calls = self._doctor_run(models_failures=1)
        self.assertTrue(result["ok"])
        self.assertTrue(result["tiers"]["std"]["ok"])
        self.assertEqual([c for c in calls if c[0] == "models"], [("models", 60), ("models", 60)])

    def test_models_failing_twice_is_not_ok(self):
        result, calls = self._doctor_run(models_failures=2)
        self.assertFalse(result["ok"])
        for name in ("std", "lite"):
            entry = result["tiers"][name]
            self.assertFalse(entry["ok"])
            self.assertEqual(entry["kind"], "config")
            self.assertIn("boom", entry["detail"])
        self.assertEqual(len([c for c in calls if c[0] == "models"]), 2)
        self.assertEqual(ha_doctor.status_line(_routing(), result), UNAVAILABLE_HYBRID)

    def test_empty_models_listing_is_a_config_error(self):
        result, calls = self._doctor_run(models_out="")
        self.assertFalse(result["ok"])
        for name in ("std", "lite"):
            entry = result["tiers"][name]
            self.assertFalse(entry["ok"])
            self.assertEqual(entry["kind"], "config")
            self.assertEqual(entry["detail"], "opencode models listed nothing")
        # 2 doctor attempts x (1 call + 2 empty-answer retries in hybrid_shared.run_models)
        self.assertEqual(len([c for c in calls if c[0] == "models"]), 6)

    def test_missing_binary_marks_every_tier_spawn(self):
        with mock.patch.object(ha_doctor.shutil, "which", return_value=None), \
             mock.patch.object(ha_doctor.subprocess, "run",
                               side_effect=FileNotFoundError("no opencode")), \
             mock.patch.object(ha_doctor, "run_once", side_effect=self._no_run_once):
            result = ha_doctor.run_doctor("opencode-missing", _routing(), True,
                                          Path(self._tmp) / "work", {})
        self.assertFalse(result["ok"])
        for name in ("std", "lite"):
            entry = result["tiers"][name]
            self.assertFalse(entry["ok"])
            self.assertEqual(entry["kind"], "spawn")
            self.assertEqual(entry["detail"], "opencode binary or version check failed")

    def test_unlisted_model_fails_only_that_tier(self):
        result, _calls = self._doctor_run(models_out="zai-coding-plan/glm-5.3\n")
        self.assertTrue(result["ok"])
        self.assertTrue(result["tiers"]["std"]["ok"])
        lite = result["tiers"]["lite"]
        self.assertFalse(lite["ok"])
        self.assertEqual(lite["kind"], "model")
        self.assertIn("zai-coding-plan/glm-5.3-flash", lite["detail"])

    def test_plain_doctor_keeps_a_fresh_previous_entry(self):
        previous = self._previous()
        failed = self._failed_std()
        previous["tiers"]["std"] = failed
        result, _calls = self._doctor_run(previous=previous)
        self.assertEqual(result["tiers"]["std"], failed)
        self.assertEqual(result["tiers"]["lite"], previous["tiers"]["lite"])

    def test_plain_doctor_rechecks_a_stale_previous_entry(self):
        previous = self._previous(age=3600.0)
        stale = self._failed_std(age=3600.0)
        previous["tiers"]["std"] = stale
        result, _calls = self._doctor_run(previous=previous)
        std = result["tiers"]["std"]
        self.assertTrue(std["ok"])
        self.assertEqual(std["detail"], "listed")
        self.assertGreater(std["checked_at"], stale["checked_at"])

    def test_edited_model_forces_a_recheck(self):
        previous = self._previous()
        routing = _routing()
        routing["tiers"]["std"]["model"] = "zai-coding-plan/glm-5.3-flash"
        result, _calls = self._doctor_run(previous=previous, routing=routing)
        std = result["tiers"]["std"]
        self.assertEqual(std["key"], ha_doctor.cache_key(routing["tiers"]["std"]))
        self.assertNotEqual(std["key"], previous["tiers"]["std"]["key"])
        self.assertGreater(std["checked_at"], previous["tiers"]["std"]["checked_at"])

    def test_ping_ok_uses_the_investigator_agent_and_replaces_a_fresh_entry(self):
        seen = []
        previous = self._previous()
        previous["tiers"]["std"] = self._failed_std()
        result, _calls = self._doctor_run(
            ping=True, previous=previous,
            run_once_fake=self._ping_fake(_result(text=SENTINEL), seen))
        std = result["tiers"]["std"]
        self.assertTrue(std["ok"])
        self.assertEqual(std["kind"], "")
        self.assertEqual(std["detail"], SENTINEL)
        self.assertGreater(std["checked_at"], previous["tiers"]["std"]["checked_at"])
        self.assertTrue(result["tiers"]["lite"]["ok"])
        self.assertEqual(len(seen), 2)
        std_call = [s for s in seen if "zai-coding-plan/glm-5.3#high" in s["cmd"]][0]
        self.assertEqual(std_call["cmd"][std_call["cmd"].index("--agent") + 1],
                         AGENT_NAMES["investigator"])
        self.assertEqual(std_call["cmd"][std_call["cmd"].index("--agent") + 1], "ha-investigator")
        self.assertNotIn("--session", std_call["cmd"])
        self.assertNotIn("-f", std_call["cmd"])
        self.assertEqual(std_call["stall_s"], 180)
        self.assertEqual(std_call["timeout_s"], 900)
        self.assertEqual(std_call["cwd"], Path(self._tmp) / "work")
        # ping logs go next to the doctor cache, never into the working directory (the audited repo)
        self.assertEqual(std_call["out_path"].parent, ha_doctor.doctor_cache_path().parent)
        self.assertFalse((Path(self._tmp) / "work").exists())

    def test_ping_tolerates_punctuation_and_backticks(self):
        for text in ("`%s`." % SENTINEL, "Sure.\n%s!" % SENTINEL, "'%s'" % SENTINEL):
            result, _calls = self._doctor_run(
                ping=True, run_once_fake=self._ping_fake(_result(text=text)))
            self.assertTrue(result["tiers"]["std"]["ok"], text)

    def test_ping_sentence_mentioning_sentinel_fails_as_format(self):
        with mock.patch.object(ha_doctor, "classify", return_value=""), \
             mock.patch.object(ha_doctor, "first_error", return_value=""):
            result, _calls = self._doctor_run(
                ping=True,
                run_once_fake=self._ping_fake(_result(text="I will not say %s" % SENTINEL)))
        std = result["tiers"]["std"]
        self.assertFalse(std["ok"])
        self.assertEqual(std["kind"], "format")
        self.assertEqual(std["detail"], "I will not say %s" % SENTINEL)
        self.assertTrue(result["ok"])

    def test_ping_failure_uses_the_shared_classifier(self):
        failed = _result(reason="crash", errors=["ProviderError: Invalid API key"])
        with mock.patch.object(ha_doctor, "classify", return_value="auth") as classify_mock, \
             mock.patch.object(ha_doctor, "first_error",
                               return_value="ProviderError: Invalid API key") as first_mock:
            result, _calls = self._doctor_run(ping=True, run_once_fake=self._ping_fake(failed))
        for name in ("std", "lite"):
            entry = result["tiers"][name]
            self.assertFalse(entry["ok"])
            self.assertEqual(entry["kind"], "auth")
            self.assertEqual(entry["detail"], "ProviderError: Invalid API key")
        self.assertEqual(classify_mock.call_count, 2)
        classify_mock.assert_called_with(1, ["ProviderError: Invalid API key"], "", "", False)
        first_mock.assert_called_with(["ProviderError: Invalid API key"], "")
        self.assertTrue(result["ok"])

    def test_ping_timeout_passes_the_kill_reason_to_the_classifier(self):
        failed = _result(reason="timeout")
        with mock.patch.object(ha_doctor, "classify", return_value="timeout") as classify_mock, \
             mock.patch.object(ha_doctor, "first_error", return_value=""):
            result, _calls = self._doctor_run(ping=True, run_once_fake=self._ping_fake(failed))
        classify_mock.assert_called_with(1, [], "", "timeout", False)
        std = result["tiers"]["std"]
        self.assertEqual(std["kind"], "timeout")
        self.assertEqual(std["detail"], "timeout")

    def test_ping_exit_one_after_a_finished_reply_is_recovered(self):
        recovered = _result(text=SENTINEL, reason="crash", finished=True)
        result, _calls = self._doctor_run(ping=True, run_once_fake=self._ping_fake(recovered))
        std = result["tiers"]["std"]
        self.assertTrue(std["ok"])
        self.assertEqual(std["kind"], "recovered")
        self.assertEqual(std["detail"], SENTINEL)

    def test_one_failed_tier_does_not_disable_the_other(self):
        def _run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            if "zai-coding-plan/glm-5.3#high" in cmd:
                return _result(reason="crash", errors=["ProviderError: quota exhausted"])
            return _result(text=SENTINEL)

        with mock.patch.object(ha_doctor, "classify", return_value="quota"), \
             mock.patch.object(ha_doctor, "first_error",
                               return_value="ProviderError: quota exhausted"):
            result, _calls = self._doctor_run(ping=True, run_once_fake=_run_once)
        self.assertTrue(result["ok"])
        self.assertFalse(result["tiers"]["std"]["ok"])
        self.assertEqual(result["tiers"]["std"]["kind"], "quota")
        self.assertTrue(result["tiers"]["lite"]["ok"])
        self.assertEqual(result["tiers"]["lite"]["detail"], SENTINEL)
        self.assertIn(" investigator=claude(down: quota) ",
                      ha_doctor.status_line(_routing(), result))

    def test_unlisted_model_is_not_pinged(self):
        seen = []
        result, _calls = self._doctor_run(
            ping=True, models_out="zai-coding-plan/glm-5.3\n",
            run_once_fake=self._ping_fake(_result(text=SENTINEL), seen))
        self.assertEqual(len(seen), 1)
        self.assertTrue(result["tiers"]["std"]["ok"])
        self.assertEqual(result["tiers"]["lite"]["kind"], "model")

    def test_ping_skipped_when_base_check_fails(self):
        result, _calls = self._doctor_run(ping=True, models_failures=2)
        self.assertFalse(result["ok"])
        self.assertEqual(result["tiers"]["std"]["kind"], "config")

    def test_status_line_from_run_doctor_result(self):
        result, _calls = self._doctor_run()
        self.assertEqual(
            ha_doctor.status_line(_routing(), result),
            "opencode: v2.0.18 preset=hybrid investigator=oc:std verifier=claude parser=claude "
            "(doctor %s)" % result["t"][:10],
        )

    def test_write_and_reload_run_doctor_result(self):
        result, _calls = self._doctor_run()
        path = ha_doctor.doctor_cache_path()
        ha_doctor.write_doctor(path, result)
        self.assertEqual(path, Path(self._tmp) / "cache" / "doctor.json")
        self.assertEqual(ha_doctor.load_doctor(path), result)
