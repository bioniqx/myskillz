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


def _pipe_run_captured(cmd, timeout):
    # These tests mock subprocess.run and hand back stdout directly; the real run_captured reads
    # stdout from a temp file (opencode truncates pipes), which a mock cannot fill.
    import subprocess as _sp
    return _sp.run(cmd, capture_output=True, text=True, timeout=timeout)


_SEAM = []


def setUpModule():
    import hybrid_shared
    for owner in (hybrid_shared, hp_doctor):
        if hasattr(owner, "run_captured"):
            patcher = mock.patch.object(owner, "run_captured", _pipe_run_captured)
            patcher.start()
            _SEAM.append(patcher)


def tearDownModule():
    while _SEAM:
        _SEAM.pop().stop()
from hp_config import AGENT_NAME, SENTINEL
from hybrid_shared import cache_key

MODELS_OUT = "zai-coding-plan/glm-5.3\nzai-coding-plan/glm-5.3-flash\n"
UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
UNAVAILABLE_LINE = "opencode: unavailable → Claude writers (preset hybrid; run plan_tool.py doctor --ping)"
UNAVAILABLE_OPENCODE = "opencode: unavailable → tasks held (preset opencode; run plan_tool.py doctor --ping)"
NOW = 1800000000.0
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
        "roles": {"light": "lite", "std": "std", "deep": "claude"},
        "max_roles": {"deep": "std"},
        "review_oc": {"hybrid": "all", "max": "risky"},
        "oc_group_max": 3, "max_repairs": 2, "throttle_cooldown_s": 120,
    }


def _entry(name, ok=True, kind="", detail="listed", age=10.0):
    return {"ok": ok, "key": cache_key(_routing()["tiers"][name]),
            "checked_at": NOW - age, "kind": kind, "detail": detail}


def _doctor():
    return {
        "t": "2026-09-28T12:00:00Z",
        "ok": True,
        "version": "2.0.18",
        "binary": "/usr/bin/opencode",
        "tiers": {"std": _entry("std"), "lite": _entry("lite")},
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
        os.environ["HYBRID_WRITING_PLANS_ROUTING"] = str(tmp / "cfg" / "routing.json")
        os.environ["HYBRID_WRITING_PLANS_DOCTOR_CACHE"] = str(tmp / "cache" / "doctor.json")
        os.environ["HYBRID_WRITING_PLANS_TELEMETRY"] = str(tmp / "cache" / "lanes.jsonl")
        os.environ.pop("HYBRID_OPENCODE_STD", None)
        os.environ.pop("HYBRID_OPENCODE_LITE", None)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved_environ)
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestDoctorCachePath(EnvIsolatedTestCase):
    def test_default_path_under_home_cache(self):
        os.environ.pop("HYBRID_WRITING_PLANS_DOCTOR_CACHE", None)
        self.assertEqual(
            hp_doctor.doctor_cache_path(),
            Path(self._tmp) / ".cache" / "hybrid-writing-plans" / "doctor.json",
        )

    def test_env_override(self):
        override = Path(self._tmp) / "custom" / "doctor.json"
        os.environ["HYBRID_WRITING_PLANS_DOCTOR_CACHE"] = str(override)
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


class TestDownMarksAreGone(unittest.TestCase):
    def test_persistent_down_marks_and_the_local_classifier_are_removed(self):
        for name in ("mark_down", "classify_error", "_UNAVAILABLE_RE"):
            self.assertFalse(hasattr(hp_doctor, name), name)


class TestStatusLine(EnvIsolatedTestCase):
    def _line(self, doctor, backends=None, preset="hybrid", now=NOW):
        backends = backends or {"light": "oc:lite", "std": "oc:std", "deep": "claude"}
        with mock.patch.object(hp_doctor, "route",
                               side_effect=lambda tier, routing, doc, pre: backends[tier]), \
             mock.patch.object(hp_doctor, "effective_preset", return_value=preset), \
             mock.patch.object(hp_doctor, "review_policy", return_value="all"):
            return hp_doctor.status_line(_routing(), doctor, preset, now)

    def _all_claude(self):
        return {"light": "claude", "std": "claude", "deep": "claude"}

    def test_unavailable_when_doctor_missing(self):
        self.assertEqual(self._line({}), UNAVAILABLE_LINE)

    def test_unavailable_when_version_missing(self):
        doctor = _doctor()
        doctor["version"] = ""
        self.assertEqual(self._line(doctor), UNAVAILABLE_LINE)

    def test_unavailable_when_not_ok(self):
        doctor = _doctor()
        doctor["ok"] = False
        self.assertEqual(self._line(doctor), UNAVAILABLE_LINE)

    def test_unavailable_line_in_opencode_mode_says_held_not_claude(self):
        self.assertEqual(self._line({}, preset="opencode"), UNAVAILABLE_OPENCODE)

    def test_disabled_tier_is_marked_in_the_line(self):
        routing = _routing()
        routing["tiers"]["std"]["disabled"] = True
        self.assertEqual(hp_doctor._tier_note(_doctor(), routing, "std", NOW), "disabled")

    def test_claude_preset_needs_no_doctor(self):
        self.assertEqual(self._line({}, preset="claude"), "opencode: not used (preset claude)")

    def test_matches_spec_example(self):
        self.assertEqual(
            self._line(_doctor()),
            "opencode: v2.0.18 preset=hybrid light=oc:lite std=oc:std deep=claude "
            "review_oc=all (doctor 2026-09-28)",
        )

    def test_down_tier_shows_kind(self):
        doctor = _doctor()
        doctor["tiers"]["std"] = _entry("std", ok=False, kind="auth", detail="expired")
        backends = {"light": "oc:lite", "std": "claude", "deep": "claude"}
        self.assertEqual(
            self._line(doctor, backends),
            "opencode: v2.0.18 preset=hybrid light=oc:lite std=claude(down: auth) "
            "deep=claude review_oc=all (doctor 2026-09-28)",
        )

    def test_stale_tier_says_stale(self):
        doctor = _doctor()
        doctor["tiers"]["std"] = _entry("std", age=100000.0)
        backends = {"light": "oc:lite", "std": "claude", "deep": "claude"}
        self.assertEqual(
            self._line(doctor, backends),
            "opencode: v2.0.18 preset=hybrid light=oc:lite std=claude(stale) "
            "deep=claude review_oc=all (doctor 2026-09-28)",
        )

    def test_now_argument_drives_staleness(self):
        line = self._line(_doctor(), self._all_claude(), now=NOW + 100000.0)
        self.assertIn(" light=claude(stale) ", line)
        self.assertIn(" std=claude(stale) ", line)
        self.assertIn(" deep=claude ", line)

    def test_default_now_is_the_clock(self):
        with mock.patch.object(hp_doctor, "_clock", return_value=NOW + 100000.0):
            line = self._line(_doctor(), self._all_claude(), now=0.0)
        self.assertIn(" std=claude(stale) ", line)

    def test_missing_tier_entry_is_stale(self):
        doctor = _doctor()
        del doctor["tiers"]["lite"]
        line = self._line(doctor, self._all_claude())
        self.assertIn(" light=claude(stale) ", line)
        self.assertIn(" std=claude ", line)

    def test_changed_model_is_stale(self):
        doctor = _doctor()
        doctor["tiers"]["std"]["key"] = "old-provider/old-model#high"
        line = self._line(doctor, self._all_claude())
        self.assertIn(" std=claude(stale) ", line)

    def test_held_tier_shows_kind(self):
        doctor = _doctor()
        doctor["tiers"]["std"] = _entry("std", ok=False, kind="quota", detail="no credit")
        backends = {"light": "oc:lite", "std": "held", "deep": "claude"}
        line = self._line(doctor, backends, preset="opencode")
        self.assertIn(" std=held(down: quota) ", line)

    def test_opencode_preset_notes_follow_max_roles(self):
        doctor = _doctor()
        doctor["tiers"]["std"] = _entry("std", ok=False, kind="quota", detail="no credit")
        backends = {"light": "oc:lite", "std": "held", "deep": "held"}
        line = self._line(doctor, backends, preset="opencode")
        self.assertIn(" deep=held(down: quota) ", line)

    def test_claude_preset_line(self):
        doctor = _doctor()
        doctor["tiers"]["std"] = _entry("std", ok=False, kind="auth", detail="expired")
        line = self._line(doctor, self._all_claude(), preset="claude")
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
        raise AssertionError("run_once must not be called here")

    def _doctor_run(self, ping=False, previous=None, run_once_fake=None, kind="crash",
                    routing=None, which="/usr/bin/opencode", **fake_kwargs):
        fake, calls = self._subprocess_fake(**fake_kwargs)
        self.classify = mock.Mock(return_value=kind)
        with mock.patch.object(hp_doctor.shutil, "which", return_value=which), \
             mock.patch.object(hp_doctor.subprocess, "run", side_effect=fake), \
             mock.patch.object(hp_doctor, "config_env", return_value={}), \
             mock.patch.object(hp_doctor, "classify", self.classify), \
             mock.patch.object(hp_doctor, "_clock", return_value=NOW), \
             mock.patch.object(hp_doctor, "run_once",
                               side_effect=run_once_fake or self._no_run_once):
            result = hp_doctor.run_doctor("opencode", routing or _routing(), ping,
                                          Path(self._tmp) / "work", previous or {})
        return result, calls

    def _ping_fake(self, result, seen=None):
        def _run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            if seen is not None:
                seen.append({"cmd": list(cmd), "cwd": Path(cwd), "stall_s": stall_s,
                             "timeout_s": timeout_s})
            return result
        return _run_once

    def _ping_by_model(self, by_model):
        def _run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            for spec, result in by_model.items():
                if spec in cmd:
                    return result
            raise AssertionError("unexpected ping cmd %r" % (cmd,))
        return _run_once

    def test_plain_doctor_checks_version_and_models(self):
        result, calls = self._doctor_run()
        self.assertEqual(set(result), {"t", "ok", "version", "binary", "tiers"})
        self.assertRegex(result["t"], UTC_RE)
        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "2.0.18")
        self.assertEqual(result["binary"], "/usr/bin/opencode")
        std = result["tiers"]["std"]
        self.assertEqual(set(std), ENTRY_KEYS)
        self.assertEqual(std, {"ok": True, "key": cache_key(_routing()["tiers"]["std"]),
                               "checked_at": NOW, "kind": "", "detail": "listed"})
        self.assertEqual(result["tiers"]["lite"]["key"], cache_key(_routing()["tiers"]["lite"]))
        self.assertIn(("--version", 10), calls)
        self.assertIn(("models", 60), calls)
        self.classify.assert_not_called()

    def test_key_changes_when_the_variant_changes(self):
        routing = _routing()
        routing["tiers"]["std"]["variant"] = "low"
        result, _calls = self._doctor_run(routing=routing)
        self.assertNotEqual(result["tiers"]["std"]["key"], cache_key(_routing()["tiers"]["std"]))
        self.assertEqual(result["tiers"]["std"]["key"], cache_key(routing["tiers"]["std"]))

    def test_version_output_is_normalised(self):
        result, _calls = self._doctor_run(version_out="opencode v2.0.18 (abc123)\nupdate available\n")
        self.assertEqual(result["version"], "2.0.18")

    def test_models_are_retried_once(self):
        result, calls = self._doctor_run(models_failures=1)
        self.assertTrue(result["ok"])
        self.assertTrue(result["tiers"]["std"]["ok"])
        self.assertEqual([c for c in calls if c[0] == "models"], [("models", 60), ("models", 60)])

    def test_models_failing_twice_fails_every_tier_with_the_classified_kind(self):
        result, calls = self._doctor_run(models_failures=2)
        self.assertFalse(result["ok"])
        for name in ("std", "lite"):
            entry = result["tiers"][name]
            self.assertFalse(entry["ok"])
            self.assertEqual(entry["kind"], "crash")
            self.assertIn("boom", entry["detail"])
        self.classify.assert_called_with(1, [], "boom")
        self.assertEqual(len([c for c in calls if c[0] == "models"]), 2)

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

    def test_binary_not_found_is_a_spawn_error(self):
        result, _calls = self._doctor_run(which=None)
        self.assertFalse(result["ok"])
        self.assertEqual(result["binary"], "opencode")
        std = result["tiers"]["std"]
        self.assertFalse(std["ok"])
        self.assertEqual(std["kind"], "spawn")
        self.assertIn("not found", std["detail"])

    def test_unlisted_model_fails_only_that_tier(self):
        result, _calls = self._doctor_run(models_out="zai-coding-plan/glm-5.3\n")
        self.assertTrue(result["ok"])
        self.assertTrue(result["tiers"]["std"]["ok"])
        lite = result["tiers"]["lite"]
        self.assertFalse(lite["ok"])
        self.assertEqual(lite["kind"], "model")
        self.assertIn("zai-coding-plan/glm-5.3-flash", lite["detail"])

    def test_tier_without_a_model_is_a_config_error(self):
        routing = _routing()
        del routing["tiers"]["lite"]["model"]
        result, _calls = self._doctor_run(routing=routing)
        lite = result["tiers"]["lite"]
        self.assertFalse(lite["ok"])
        self.assertEqual(lite["kind"], "config")
        self.assertEqual(lite["key"], "")
        self.assertIn("no model", lite["detail"])
        self.assertTrue(result["tiers"]["std"]["ok"])

    def test_plain_doctor_keeps_a_fresh_ping_result(self):
        previous = _doctor()
        previous["tiers"]["std"] = _entry("std", detail="ping ok", age=100.0)
        result, _calls = self._doctor_run(previous=previous)
        self.assertEqual(result["tiers"]["std"], previous["tiers"]["std"])
        self.assertEqual(result["tiers"]["lite"]["checked_at"], NOW)

    def test_plain_doctor_keeps_a_fresh_failed_ping(self):
        previous = _doctor()
        previous["tiers"]["std"] = dict(_entry("std", ok=False, kind="auth", detail="401 unauthorized", age=100.0),
                                        ping=True)
        result, _calls = self._doctor_run(previous=previous)
        self.assertEqual(result["tiers"]["std"], previous["tiers"]["std"])
        self.assertEqual(result["tiers"]["lite"]["detail"], "listed")

    def test_plain_doctor_rechecks_a_failure_that_was_not_a_ping(self):
        previous = _doctor()
        previous["tiers"]["std"] = _entry("std", ok=False, kind="model", detail="not listed", age=100.0)
        result, _calls = self._doctor_run(previous=previous)
        self.assertEqual((result["tiers"]["std"]["ok"], result["tiers"]["std"]["detail"]), (True, "listed"))

    def test_ping_entries_are_marked_as_pings(self):
        result, _calls = self._doctor_run(ping=True, run_once_fake=self._ping_fake(_result(text=SENTINEL)))
        self.assertTrue(result["tiers"]["std"]["ping"])

    def test_models_listing_never_uses_standalone(self):
        cmds = []

        def _run(cmd, **kwargs):
            cmds.append(list(cmd))
            if cmd[1] == "--version":
                return SimpleNamespace(returncode=0, stdout="2.0.18\n", stderr="")
            return SimpleNamespace(returncode=0, stdout=MODELS_OUT, stderr="")

        with mock.patch.object(hp_doctor.shutil, "which", return_value="/usr/bin/opencode"), \
                mock.patch.object(hp_doctor.subprocess, "run", side_effect=_run):
            hp_doctor.run_doctor("opencode", _routing(), False, Path(self._tmp) / "work", {})
        # `models --standalone` always lists nothing on opencode v2.0.20
        self.assertIn(["opencode", "models"], cmds)
        self.assertNotIn("--standalone", [a for c in cmds for a in c])

    def test_ping_failure_is_classified_on_stderr_not_on_the_note(self):
        def _run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            Path(err_path).write_text("provider said: 401 Unauthorized\n", encoding="utf-8")
            return _result(reason="crash", note="exit 1")

        self._doctor_run(ping=True, run_once_fake=_run_once)
        stderr_args = {c[0][2] for c in self.classify.call_args_list}
        self.assertEqual(stderr_args, {"provider said: 401 Unauthorized"})

    def test_plain_doctor_drops_a_stale_ping_result(self):
        previous = _doctor()
        previous["tiers"]["std"] = _entry("std", detail="ping ok", age=100000.0)
        result, _calls = self._doctor_run(previous=previous)
        self.assertEqual(result["tiers"]["std"]["checked_at"], NOW)
        self.assertEqual(result["tiers"]["std"]["detail"], "listed")

    def test_plain_doctor_drops_a_ping_result_for_another_model(self):
        previous = _doctor()
        previous["tiers"]["std"] = _entry("std", detail="ping ok", age=100.0)
        previous["tiers"]["std"]["key"] = "other-provider/other-model#high"
        result, _calls = self._doctor_run(previous=previous)
        self.assertEqual(result["tiers"]["std"]["checked_at"], NOW)
        self.assertEqual(result["tiers"]["std"]["key"], cache_key(_routing()["tiers"]["std"]))

    def test_ping_ok_uses_the_writer_agent(self):
        seen = []
        result, _calls = self._doctor_run(
            ping=True, run_once_fake=self._ping_fake(_result(text=SENTINEL), seen))
        for name in ("std", "lite"):
            entry = result["tiers"][name]
            self.assertEqual((entry["ok"], entry["kind"], entry["detail"]), (True, "", "ping ok"))
            self.assertEqual(entry["checked_at"], NOW)
        self.assertEqual(len(seen), 2)
        std_call = [s for s in seen if "zai-coding-plan/glm-5.3#high" in s["cmd"]][0]
        self.assertIn("--agent", std_call["cmd"])
        self.assertEqual(std_call["cmd"][std_call["cmd"].index("--agent") + 1], AGENT_NAME)
        self.assertEqual(std_call["stall_s"], 180)
        self.assertEqual(std_call["timeout_s"], 900)
        self.assertEqual(std_call["cwd"], Path(self._tmp) / "work")
        self.assertTrue((Path(self._tmp) / "work").is_dir())

    def test_ping_replaces_a_previous_failure(self):
        previous = _doctor()
        previous["tiers"]["std"] = _entry("std", ok=False, kind="auth", detail="expired", age=100.0)
        result, _calls = self._doctor_run(
            ping=True, previous=previous, run_once_fake=self._ping_fake(_result(text=SENTINEL)))
        std = result["tiers"]["std"]
        self.assertTrue(std["ok"])
        self.assertEqual(std["kind"], "")
        self.assertEqual(std["checked_at"], NOW)

    def test_ping_tolerates_punctuation_and_backticks(self):
        for text in ("`%s`." % SENTINEL, "Sure.\n%s!" % SENTINEL, "'%s'" % SENTINEL):
            result, _calls = self._doctor_run(
                ping=True, run_once_fake=self._ping_fake(_result(text=text)))
            self.assertTrue(result["tiers"]["std"]["ok"], text)

    def test_ping_sentence_mentioning_sentinel_fails(self):
        result, _calls = self._doctor_run(
            ping=True, kind="",
            run_once_fake=self._ping_fake(_result(text="I will not say %s" % SENTINEL)))
        std = result["tiers"]["std"]
        self.assertFalse(std["ok"])
        self.assertEqual(std["kind"], "format")
        self.assertEqual(std["detail"], "I will not say %s" % SENTINEL)
        self.assertTrue(result["ok"])

    def test_ping_with_no_reply_is_empty(self):
        result, _calls = self._doctor_run(
            ping=True, kind="", run_once_fake=self._ping_fake(_result(text="")))
        std = result["tiers"]["std"]
        self.assertFalse(std["ok"])
        self.assertEqual(std["kind"], "empty")
        self.assertEqual(std["detail"], "no sentinel in reply")

    def test_ping_auth_failure_uses_the_classified_kind_and_first_error(self):
        errors = ["APIError: Your coding plan has expired\nRenew at https://example.invalid"]
        failed = _result(reason="unavailable", errors=errors)
        result, _calls = self._doctor_run(
            ping=True, kind="auth", run_once_fake=self._ping_fake(failed))
        std = result["tiers"]["std"]
        self.assertFalse(std["ok"])
        self.assertEqual(std["kind"], "auth")
        self.assertIn("APIError: Your coding plan has expired", std["detail"])
        self.assertEqual(std["checked_at"], NOW)
        self.assertTrue(result["ok"])
        self.classify.assert_called_with(1, errors, "", "", False)

    def test_ping_timeout_passes_killed_to_the_classifier(self):
        failed = _result(reason="timeout")
        result, _calls = self._doctor_run(
            ping=True, kind="timeout", run_once_fake=self._ping_fake(failed))
        std = result["tiers"]["std"]
        self.assertFalse(std["ok"])
        self.assertEqual(std["kind"], "timeout")
        self.assertEqual(std["detail"], "timeout")
        self.classify.assert_called_with(1, [], "", "timeout", False)

    def test_ping_exit_one_after_a_finished_reply_is_ok(self):
        recovered = dict(_result(text=SENTINEL, reason="crash"), finished=True)
        result, _calls = self._doctor_run(ping=True, run_once_fake=self._ping_fake(recovered))
        self.assertTrue(result["tiers"]["std"]["ok"])
        crashed = _result(text=SENTINEL, reason="crash")
        result, _calls = self._doctor_run(
            ping=True, kind="crash", run_once_fake=self._ping_fake(crashed))
        self.assertFalse(result["tiers"]["std"]["ok"])
        self.assertEqual(result["tiers"]["std"]["kind"], "crash")

    def test_ping_throttle_keeps_the_tier_usable(self):
        failed = _result(reason="throttle", errors=["APIError: 429 Too Many Requests"])
        result, _calls = self._doctor_run(
            ping=True, kind="throttle", run_once_fake=self._ping_fake(failed))
        std = result["tiers"]["std"]
        self.assertTrue(std["ok"])
        self.assertEqual(std["kind"], "throttle")
        self.assertIn("429", std["detail"])

    def test_one_failed_ping_does_not_disable_the_other_tier(self):
        by_model = {
            "zai-coding-plan/glm-5.3#high": _result(
                reason="unavailable", errors=["APIError: plan expired"]),
            "zai-coding-plan/glm-5.3-flash#low": _result(text=SENTINEL),
        }
        result, _calls = self._doctor_run(
            ping=True, kind="auth", run_once_fake=self._ping_by_model(by_model))
        self.assertFalse(result["tiers"]["std"]["ok"])
        self.assertEqual(result["tiers"]["std"]["kind"], "auth")
        self.assertTrue(result["tiers"]["lite"]["ok"])
        self.assertTrue(result["ok"])

    def test_unlisted_model_is_not_pinged(self):
        seen = []
        result, _calls = self._doctor_run(
            ping=True, models_out="zai-coding-plan/glm-5.3\n",
            run_once_fake=self._ping_fake(_result(text=SENTINEL), seen))
        self.assertEqual(len(seen), 1)
        self.assertTrue(result["tiers"]["std"]["ok"])
        self.assertEqual(result["tiers"]["lite"]["kind"], "model")

    def test_ping_is_skipped_when_the_base_check_failed(self):
        result, _calls = self._doctor_run(ping=True, models_failures=2)
        self.assertFalse(result["ok"])
        self.assertFalse(result["tiers"]["std"]["ok"])
        self.assertFalse(result["tiers"]["lite"]["ok"])


if __name__ == "__main__":
    unittest.main()
