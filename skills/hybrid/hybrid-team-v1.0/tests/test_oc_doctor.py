import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import oc_doctor
import hybrid_shared

FAKE = Path(__file__).resolve().parent / "fake_opencode.py"


class TestCheckOpencode(unittest.TestCase):
    def test_binary_found_and_tiers_complete(self):
        routing = {
            "tiers": {
                "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high"},
                "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low"},
            },
            "rows": {"code": "std", "trivial": "lite"},
        }
        checks = oc_doctor.check_opencode("python3", routing)
        by_name = {c["name"]: c for c in checks}
        self.assertTrue(by_name["opencode_binary"]["ok"])
        self.assertTrue(by_name["tiers"]["ok"])
        self.assertTrue(by_name["tier:std"]["ok"])
        self.assertTrue(by_name["tier:lite"]["ok"])
        self.assertTrue(by_name["row:code"]["ok"])
        self.assertTrue(by_name["row:trivial"]["ok"])

    def test_binary_missing_and_no_tiers(self):
        checks = oc_doctor.check_opencode("no-such-opencode-binary-xyz", {})
        by_name = {c["name"]: c for c in checks}
        self.assertFalse(by_name["opencode_binary"]["ok"])
        self.assertFalse(by_name["tiers"]["ok"])

    def test_row_pointing_at_missing_tier_fails(self):
        routing = {
            "tiers": {"std": {"model": "m", "variant": "high"}},
            "rows": {"code": "ghost"},
        }
        checks = oc_doctor.check_opencode("python3", routing)
        by_name = {c["name"]: c for c in checks}
        self.assertFalse(by_name["row:code"]["ok"])

    def test_models_check_runs_binary_models_and_flags_missing_model(self):
        # fake_opencode.py's `models` subcommand always prints exactly:
        #   zai-coding-plan/glm-5.3
        #   zai-coding-plan/glm-5.3-flash
        routing = {
            "tiers": {
                "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high"},
                "ghost": {"model": "no-such-model/on-earth", "variant": "low"},
            },
            "rows": {},
        }
        checks = oc_doctor.check_opencode(str(FAKE), routing)
        by_name = {c["name"]: c for c in checks}
        self.assertTrue(by_name["opencode_models"]["ok"])
        self.assertTrue(by_name["model:std"]["ok"])
        self.assertFalse(by_name["model:ghost"]["ok"])

    def test_models_check_not_ok_on_nonzero_exit(self):
        original_run = oc_doctor.subprocess.run

        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="boom")

        oc_doctor.subprocess.run = fake_run
        try:
            checks = oc_doctor.check_opencode("python3", {"tiers": {}, "rows": {}})
        finally:
            oc_doctor.subprocess.run = original_run
        by_name = {c["name"]: c for c in checks}
        self.assertFalse(by_name["opencode_models"]["ok"])

    def test_models_check_not_ok_on_timeout(self):
        original_run = oc_doctor.subprocess.run

        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 0))

        oc_doctor.subprocess.run = fake_run
        try:
            checks = oc_doctor.check_opencode("python3", {"tiers": {}, "rows": {}})
        finally:
            oc_doctor.subprocess.run = original_run
        by_name = {c["name"]: c for c in checks}
        self.assertFalse(by_name["opencode_models"]["ok"])

    def test_models_check_retries_once_after_timeout_then_succeeds(self):
        original_run = oc_doctor.subprocess.run
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if len(calls) == 1:
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 0))
            return subprocess.CompletedProcess(
                cmd, returncode=0, stdout="zai-coding-plan/glm-5.3\n", stderr="")

        oc_doctor.subprocess.run = fake_run
        try:
            checks = oc_doctor.check_opencode("python3", {"tiers": {}, "rows": {}})
        finally:
            oc_doctor.subprocess.run = original_run
        by_name = {c["name"]: c for c in checks}
        self.assertEqual(len(calls), 2)
        self.assertTrue(by_name["opencode_models"]["ok"])

    def test_models_check_retries_once_after_empty_then_succeeds(self):
        original_run = oc_doctor.subprocess.run
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            if len(calls) == 1:
                return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
            return subprocess.CompletedProcess(
                cmd, returncode=0, stdout="zai-coding-plan/glm-5.3\n", stderr="")

        oc_doctor.subprocess.run = fake_run
        try:
            checks = oc_doctor.check_opencode("python3", {"tiers": {}, "rows": {}})
        finally:
            oc_doctor.subprocess.run = original_run
        by_name = {c["name"]: c for c in checks}
        self.assertEqual(len(calls), 2)
        self.assertTrue(by_name["opencode_models"]["ok"])

    def test_models_check_two_consecutive_timeouts_still_not_ok(self):
        original_run = oc_doctor.subprocess.run
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 0))

        oc_doctor.subprocess.run = fake_run
        try:
            checks = oc_doctor.check_opencode("python3", {"tiers": {}, "rows": {}})
        finally:
            oc_doctor.subprocess.run = original_run
        by_name = {c["name"]: c for c in checks}
        self.assertEqual(len(calls), 2)
        self.assertFalse(by_name["opencode_models"]["ok"])

    def test_models_timeout_constant_is_60(self):
        self.assertEqual(oc_doctor.MODELS_TIMEOUT_S, 60)

    def _check_with_run(self, fake_run, routing):
        original_run = oc_doctor.subprocess.run
        oc_doctor.subprocess.run = fake_run
        try:
            checks = oc_doctor.check_opencode("python3", routing)
        finally:
            oc_doctor.subprocess.run = original_run
        return {c["name"]: c for c in checks}

    def test_ok_checks_have_empty_kind_and_line(self):
        routing = {
            "tiers": {"std": {"model": "zai-coding-plan/glm-5.3", "variant": "high"}},
            "rows": {"code": "std"},
        }
        checks = oc_doctor.check_opencode(str(FAKE), routing)
        for check in checks:
            self.assertEqual(check["kind"], "", check)
            self.assertEqual(check["line"], "", check)
            self.assertTrue(check["ok"], check)

    def test_empty_models_listing_is_config_issue_with_oc_line(self):
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")

        routing = {
            "tiers": {"std": {"model": "zai-coding-plan/glm-5.3", "variant": "high"}},
            "rows": {},
        }
        by_name = self._check_with_run(fake_run, routing)
        models = by_name["opencode_models"]
        self.assertEqual(models["kind"], "config")
        self.assertFalse(models["ok"])
        self.assertEqual(models["detail"], "opencode models listed nothing")
        self.assertTrue(models["line"].startswith("OC-ERROR hybrid-team doctor "))
        self.assertIn("kind=config :: opencode models listed nothing", models["line"])
        # a failed listing gives every tier model check the listing's kind
        std = by_name["model:std"]
        self.assertEqual(std["kind"], "config")
        self.assertFalse(std["ok"])

    def test_failed_models_command_kind_comes_from_classify(self):
        def fake_run(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, returncode=1, stdout="", stderr="boom")

        by_name = self._check_with_run(fake_run, {"tiers": {}, "rows": {}})
        models = by_name["opencode_models"]
        expected = hybrid_shared.classify(1, [], "boom")
        self.assertEqual(models["kind"], expected)
        self.assertFalse(models["ok"])
        self.assertIn("kind=%s" % expected, models["line"])
        self.assertIn("boom", models["line"])

    def test_models_timeout_kind_is_timeout(self):
        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kwargs.get("timeout", 0))

        by_name = self._check_with_run(fake_run, {"tiers": {}, "rows": {}})
        models = by_name["opencode_models"]
        self.assertEqual(models["kind"], "timeout")
        self.assertFalse(models["ok"])
        self.assertIn("kind=timeout", models["line"])

    def test_missing_binary_is_spawn_issue(self):
        checks = oc_doctor.check_opencode("no-such-opencode-binary-xyz", {})
        by_name = {c["name"]: c for c in checks}
        binary = by_name["opencode_binary"]
        self.assertEqual(binary["kind"], "spawn")
        self.assertFalse(binary["ok"])
        self.assertIn("kind=spawn", binary["line"])
        self.assertIn("not found: no-such-opencode-binary-xyz", binary["line"])
        self.assertEqual(by_name["opencode_models"]["kind"], "spawn")

    def test_model_missing_from_listing_is_model_issue(self):
        ghost = {"model": "no-such-model/on-earth", "variant": "low"}
        routing = {
            "tiers": {
                "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high"},
                "ghost": ghost,
            },
            "rows": {},
        }
        checks = oc_doctor.check_opencode(str(FAKE), routing)
        by_name = {c["name"]: c for c in checks}
        self.assertEqual(by_name["model:std"]["kind"], "")
        row = by_name["model:ghost"]
        self.assertEqual(row["kind"], "model")
        self.assertFalse(row["ok"])
        self.assertIn("tier=ghost", row["line"])
        self.assertIn("model=%s" % hybrid_shared.model_spec(ghost), row["line"])

    def test_config_issues_have_config_kind(self):
        routing = {"tiers": {"std": {"variant": "high"}}, "rows": {"code": "ghost"}}
        checks = oc_doctor.check_opencode(str(FAKE), routing)
        by_name = {c["name"]: c for c in checks}
        self.assertEqual(by_name["tier:std"]["kind"], "config")
        self.assertFalse(by_name["tier:std"]["ok"])
        self.assertEqual(by_name["row:code"]["kind"], "config")
        empty = {c["name"]: c for c in oc_doctor.check_opencode(str(FAKE), {})}
        self.assertEqual(empty["tiers"]["kind"], "config")
        self.assertIn("kind=config", empty["tiers"]["line"])

    def test_tier_without_variant_is_ok(self):
        routing = {"tiers": {"std": {"model": "zai-coding-plan/glm-5.3"}}, "rows": {}}
        checks = oc_doctor.check_opencode(str(FAKE), routing)
        by_name = {c["name"]: c for c in checks}
        self.assertEqual(by_name["tier:std"]["kind"], "")
        self.assertTrue(by_name["tier:std"]["ok"])
        self.assertTrue(by_name["model:std"]["ok"])


class TestPingTier(unittest.TestCase):
    def _patch(self, build_cmd=None, config_env=None, run_once=None):
        originals = (oc_doctor.build_cmd, oc_doctor.config_env, oc_doctor.run_once)
        if build_cmd is not None:
            oc_doctor.build_cmd = build_cmd
        if config_env is not None:
            oc_doctor.config_env = config_env
        if run_once is not None:
            oc_doctor.run_once = run_once
        return originals

    def _unpatch(self, originals):
        oc_doctor.build_cmd, oc_doctor.config_env, oc_doctor.run_once = originals

    def test_sends_constant_ping_message_and_prompt_only_as_agent_prompt(self):
        calls = {}

        def fake_build_cmd(binary, model, variant, message, session=""):
            calls["build_cmd"] = (binary, model, variant, message, session)
            return [binary, "run", "--model", model, message]

        def fake_config_env(prompt_text, engine, commands):
            calls["config_env"] = (prompt_text, engine, commands)
            return {"OPENCODE_CONFIG_CONTENT": "{}"}

        def fake_run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            return {"session": "sess-1", "text": oc_doctor.SENTINEL, "rc": 0, "reason": ""}

        originals = self._patch(fake_build_cmd, fake_config_env, fake_run_once)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tier = {"model": "zai-coding-plan/glm-5.3", "variant": "high"}
                oc_doctor.ping_tier("opencode", tier, "you are a careful engineer", "ht-programmer", Path(tmp))
        finally:
            self._unpatch(originals)

        # the CLI message is the constant PING, never the agent prompt text
        self.assertEqual(calls["build_cmd"][3], oc_doctor.PING)
        self.assertNotEqual(calls["build_cmd"][3], "you are a careful engineer")
        # prompt_text is injected only through config_env, as the agent's prompt
        self.assertEqual(calls["config_env"][0], "you are a careful engineer")
        self.assertEqual(calls["config_env"][1], "ht-programmer")

    def test_env_passed_to_run_once_includes_os_environ_and_config(self):
        captured = {}

        def fake_build_cmd(binary, model, variant, message, session=""):
            return [binary, "run"]

        def fake_config_env(prompt_text, engine, commands):
            return {"OPENCODE_CONFIG_CONTENT": '{"agent": {}}'}

        def fake_run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            captured["env"] = env
            return {"session": "sess-1", "text": oc_doctor.SENTINEL, "rc": 0, "reason": ""}

        originals = self._patch(fake_build_cmd, fake_config_env, fake_run_once)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tier = {"model": "m", "variant": "high"}
                oc_doctor.ping_tier("opencode", tier, "prompt", "ht-programmer", Path(tmp))
        finally:
            self._unpatch(originals)

        env = captured["env"]
        self.assertEqual(env.get("PATH"), os.environ.get("PATH"))
        self.assertEqual(env.get("HOME"), os.environ.get("HOME"))
        self.assertEqual(env.get("OPENCODE_CONFIG_CONTENT"), '{"agent": {}}')

    def test_ok_when_final_text_stripped_equals_sentinel(self):
        def fake_build_cmd(binary, model, variant, message, session=""):
            return [binary, "run"]

        def fake_config_env(prompt_text, engine, commands):
            return {"OPENCODE_CONFIG_CONTENT": "{}"}

        def fake_run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            return {"session": "sess-1", "text": "  %s\n" % oc_doctor.SENTINEL, "rc": 0, "reason": ""}

        originals = self._patch(fake_build_cmd, fake_config_env, fake_run_once)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tier = {"model": "zai-coding-plan/glm-5.3", "variant": "high"}
                ok, detail = oc_doctor.ping_tier("opencode", tier, "ping", "ht-programmer", Path(tmp))
        finally:
            self._unpatch(originals)

        self.assertTrue(ok)
        self.assertEqual(detail["model"], "zai-coding-plan/glm-5.3")
        self.assertEqual(detail["variant"], "high")
        self.assertEqual(detail["sessionID"], "sess-1")

    def test_not_ok_when_text_only_contains_sentinel(self):
        def fake_build_cmd(binary, model, variant, message, session=""):
            return [binary, "run"]

        def fake_config_env(prompt_text, engine, commands):
            return {"OPENCODE_CONFIG_CONTENT": "{}"}

        def fake_run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            return {"session": "sess-2", "text": "hello %s" % oc_doctor.SENTINEL, "rc": 0, "reason": ""}

        originals = self._patch(fake_build_cmd, fake_config_env, fake_run_once)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tier = {"model": "m", "variant": "low"}
                ok, detail = oc_doctor.ping_tier("opencode", tier, "ping", "ht-programmer", Path(tmp))
        finally:
            self._unpatch(originals)

        self.assertFalse(ok)
        self.assertEqual(detail["text"], "hello %s" % oc_doctor.SENTINEL)

    def test_not_ok_without_sentinel(self):
        def fake_build_cmd(binary, model, variant, message, session=""):
            return [binary, "run"]

        def fake_config_env(prompt_text, engine, commands):
            return {"OPENCODE_CONFIG_CONTENT": "{}"}

        def fake_run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            return {"session": "sess-2", "text": "no sentinel here", "rc": 0, "reason": ""}

        originals = self._patch(fake_build_cmd, fake_config_env, fake_run_once)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tier = {"model": "m", "variant": "low"}
                ok, detail = oc_doctor.ping_tier("opencode", tier, "ping", "ht-programmer", Path(tmp))
        finally:
            self._unpatch(originals)

        self.assertFalse(ok)
        self.assertEqual(detail["text"], "no sentinel here")


class TestPingTierClassified(unittest.TestCase):
    TIER = {"model": "zai-coding-plan/glm-5.3", "variant": "high"}

    def setUp(self):
        saved = (oc_doctor.build_cmd, oc_doctor.config_env, oc_doctor.run_once,
                 oc_doctor.classify, oc_doctor.first_error)
        self.addCleanup(self._restore, saved)
        self.result = {}
        self.err_text = ""
        self.kind = "crash"
        self.first = ""
        self.classify_calls = []

        def fake_run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            if self.err_text:
                Path(err_path).write_text(self.err_text)
            return dict(self.result)

        def fake_classify(rc, errors, stderr_tail, killed="", finished=False):
            self.classify_calls.append((rc, errors, stderr_tail, killed, finished))
            return self.kind

        oc_doctor.build_cmd = lambda binary, model, variant, message, session="": [binary, "run"]
        oc_doctor.config_env = lambda prompt_text, engine, commands: {}
        oc_doctor.run_once = fake_run_once
        oc_doctor.classify = fake_classify
        oc_doctor.first_error = lambda errors, stderr_tail: self.first

    @staticmethod
    def _restore(saved):
        (oc_doctor.build_cmd, oc_doctor.config_env, oc_doctor.run_once,
         oc_doctor.classify, oc_doctor.first_error) = saved

    def _ping(self):
        with tempfile.TemporaryDirectory() as tmp:
            return oc_doctor.ping_tier("opencode", self.TIER, "ping", "ht-programmer", Path(tmp))

    def test_ok_ping_carries_cache_key_and_no_kind(self):
        self.result = {"session": "s0", "text": oc_doctor.SENTINEL, "rc": 0, "reason": ""}
        ok, detail = self._ping()
        self.assertEqual(detail["key"], hybrid_shared.cache_key(self.TIER))
        self.assertTrue(ok)
        self.assertEqual(detail["kind"], "")
        self.assertEqual(detail["level"], "")
        self.assertEqual(detail["message"], "")
        self.assertEqual(detail["log"], "")
        self.assertEqual(self.classify_calls, [])

    def test_failed_ping_is_classified_with_stderr_tail_and_log(self):
        self.result = {"session": "s1", "text": "", "rc": 1, "reason": "",
                       "errors": ["bad key"], "finished": False}
        self.err_text = "line one\nauth failed\n"
        self.kind = "auth"
        self.first = "invalid api key"
        ok, detail = self._ping()
        self.assertFalse(ok)
        self.assertEqual(detail["kind"], "auth")
        self.assertEqual(detail["level"], "OC-ERROR")
        self.assertEqual(detail["message"], "invalid api key")
        self.assertTrue(detail["log"].endswith("doctor-ping.err"))
        rc, errors, stderr_tail, killed, finished = self.classify_calls[0]
        self.assertEqual((rc, errors, killed, finished), (1, ["bad key"], "", False))
        self.assertIn("auth failed", stderr_tail)

    def test_kill_reason_is_passed_to_classify_as_killed(self):
        self.result = {"session": "s2", "text": "", "rc": None, "reason": "stall"}
        self.kind = "stall"
        ok, detail = self._ping()
        self.assertFalse(ok)
        self.assertEqual(self.classify_calls[0][3], "stall")
        self.assertEqual(detail["kind"], "stall")
        self.assertEqual(detail["error"], "stall")
        self.assertIn("stall", detail["message"])

    def test_wrong_reply_without_classified_failure_is_a_warning(self):
        self.kind = ""
        self.result = {"session": "s3", "text": "no sentinel here", "rc": 0, "reason": ""}
        ok, detail = self._ping()
        self.assertFalse(ok)
        self.assertEqual(detail["kind"], "format")
        self.assertEqual(detail["level"], "OC-WARN")
        self.assertIn("no sentinel here", detail["message"])
        self.result = {"session": "s4", "text": "", "rc": 0, "reason": ""}
        ok, detail = self._ping()
        self.assertFalse(ok)
        self.assertEqual(detail["kind"], "empty")
        self.assertEqual(detail["level"], "OC-WARN")


class TestLaneStats(unittest.TestCase):
    def test_aggregates_by_backend_and_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            lanes_path = Path(tmp) / "lanes.jsonl"
            records = [
                {
                    "backend": "oc:std",
                    "tier": "std",
                    "escalated": False,
                    "duration_s": 10,
                    "tokens": {"input": 100, "output": 50, "reasoning": 5,
                               "cache_read": 1, "cache_write": 2},
                    "cost": 0.0,
                },
                {
                    "backend": "oc:std",
                    "tier": "std",
                    "escalated": True,
                    "duration_s": 30,
                    "tokens": {"input": 200, "output": 60, "reasoning": 8,
                               "cache_read": 3, "cache_write": 4},
                    "cost": 0.0,
                },
                {
                    "backend": "claude",
                    "tier": "-",
                    "escalated": False,
                    "duration_s": 20,
                    "tokens": {},
                    "cost": 0.0,
                },
            ]
            with lanes_path.open("w") as f:
                for record in records:
                    f.write(json.dumps(record) + "\n")

            stats = oc_doctor.lane_stats(lanes_path)

        by_key = {(s["backend"], s["tier"]): s for s in stats}
        std = by_key[("oc:std", "std")]
        self.assertEqual(std["count"], 2)
        self.assertEqual(std["escalated"], 1)
        self.assertEqual(std["escalation_rate"], 0.5)
        self.assertEqual(std["median_time_s"], 20)
        self.assertEqual(std["tokens"]["input"], 300)
        self.assertEqual(std["tokens"]["output"], 110)

        claude = by_key[("claude", "-")]
        self.assertEqual(claude["count"], 1)
        self.assertEqual(claude["escalation_rate"], 0.0)

    def test_missing_file_returns_empty_list(self):
        stats = oc_doctor.lane_stats(Path("/tmp/does-not-exist-lanes.jsonl"))
        self.assertEqual(stats, [])


if __name__ == "__main__":
    unittest.main()
