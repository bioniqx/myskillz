import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hybrid_shared as hs

SCRIPT = str(Path(hs.__file__).resolve())
BOTH = "prov/big#high"
SUMMARY_SRC = "$HYBRID_OPENCODE_STD/$HYBRID_OPENCODE_LITE"


def _script_env(std=None, lite=None):
    """Copy of the real environment with the two shared vars explicitly removed, then set as given."""
    env = dict(os.environ)
    env.pop(hs.STD_ENV, None)
    env.pop(hs.LITE_ENV, None)
    if std is not None:
        env[hs.STD_ENV] = std
    if lite is not None:
        env[hs.LITE_ENV] = lite
    return env


def _run_script(*argv, std=None, lite=None):
    proc = subprocess.run(
        [sys.executable, SCRIPT] + list(argv),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
        env=_script_env(std, lite),
    )
    return proc


class TempDirCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)


class TestSharedConfig(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(hs.MODES, ("hybrid", "claude", "opencode"))
        self.assertEqual(hs.STD_ENV, "HYBRID_OPENCODE_STD")
        self.assertEqual(hs.LITE_ENV, "HYBRID_OPENCODE_LITE")
        self.assertEqual(hs.SHARED_SOURCE, SUMMARY_SRC)
        self.assertEqual(hs.DOCTOR_TTL_S, 600)
        self.assertEqual(hs.NON_RETRYABLE, ("auth", "quota", "model", "config"))

    def test_file_based_api_is_gone(self):
        for name in ("SHARED_ENV", "shared_config_path", "_validate", "TIER_KEYS"):
            self.assertFalse(hasattr(hs, name), name)

    def test_std_unset_is_one_problem(self):
        expected = ({}, ["HYBRID_OPENCODE_STD is not set"])
        self.assertEqual(hs.load_shared({}), expected)
        self.assertEqual(hs.load_shared({hs.STD_ENV: ""}), expected)
        self.assertEqual(hs.load_shared({hs.STD_ENV: "   "}), expected)

    def test_lite_alone_does_not_satisfy_std(self):
        self.assertEqual(hs.load_shared({hs.LITE_ENV: "prov/small"}), ({}, ["HYBRID_OPENCODE_STD is not set"]))

    def test_old_config_variable_is_not_a_fallback(self):
        env = {"HYBRID_OPENCODE_CONFIG": "/somewhere/opencode.json"}
        self.assertEqual(hs.load_shared(env), ({}, ["HYBRID_OPENCODE_STD is not set"]))

    def test_std_only_makes_lite_equal_std(self):
        tiers, problems = hs.load_shared({hs.STD_ENV: BOTH})
        self.assertEqual(problems, [])
        self.assertEqual(tiers, {"std": {"model": "prov/big", "variant": "high"},
                                 "lite": {"model": "prov/big", "variant": "high"}})
        self.assertEqual(tiers["lite"], tiers["std"])

    def test_blank_lite_defaults_to_std(self):
        tiers, problems = hs.load_shared({hs.STD_ENV: "prov/big", hs.LITE_ENV: "  "})
        self.assertEqual(problems, [])
        self.assertEqual(tiers["lite"], {"model": "prov/big"})

    def test_lite_override(self):
        tiers, problems = hs.load_shared({hs.STD_ENV: BOTH, hs.LITE_ENV: "prov/small-flash#low"})
        self.assertEqual(problems, [])
        self.assertEqual(tiers, {"std": {"model": "prov/big", "variant": "high"},
                                 "lite": {"model": "prov/small-flash", "variant": "low"}})

    def test_variant_is_optional(self):
        tiers, _ = hs.load_shared({hs.STD_ENV: "prov/big", hs.LITE_ENV: "prov/small#low"})
        self.assertEqual(tiers["std"], {"model": "prov/big"})
        self.assertNotIn("variant", tiers["std"])
        self.assertEqual(tiers["lite"], {"model": "prov/small", "variant": "low"})

    def test_tiers_carry_only_model_and_variant(self):
        tiers, _ = hs.load_shared({hs.STD_ENV: BOTH})
        for tier in tiers.values():
            self.assertLessEqual(set(tier), {"model", "variant"})
            self.assertNotIn("max_parallel", tier)

    def test_values_are_stripped_and_nested_model_paths_allowed(self):
        tiers, problems = hs.load_shared({hs.STD_ENV: "  openrouter/vendor/model-1#high \n"})
        self.assertEqual(problems, [])
        self.assertEqual(tiers["std"], {"model": "openrouter/vendor/model-1", "variant": "high"})

    def test_invalid_std_names_the_variable_and_empties_tiers(self):
        tiers, problems = hs.load_shared({hs.STD_ENV: "no-provider", hs.LITE_ENV: "prov/ok"})
        self.assertEqual(tiers, {})
        self.assertEqual(problems, ["HYBRID_OPENCODE_STD must be provider/model[#variant], got 'no-provider'"])

    def test_invalid_lite_names_the_variable_and_empties_tiers(self):
        tiers, problems = hs.load_shared({hs.STD_ENV: BOTH, hs.LITE_ENV: "bad model"})
        self.assertEqual(tiers, {})
        self.assertEqual(problems, ["HYBRID_OPENCODE_LITE must be provider/model[#variant], got 'bad model'"])

    def test_invalid_std_with_defaulted_lite_reports_both_variables(self):
        tiers, problems = hs.load_shared({hs.STD_ENV: "no-provider"})
        self.assertEqual(tiers, {})
        self.assertEqual(len(problems), 2)
        self.assertTrue(problems[0].startswith("HYBRID_OPENCODE_STD must be provider/model[#variant]"))
        self.assertTrue(problems[1].startswith("HYBRID_OPENCODE_LITE must be provider/model[#variant]"))

    def test_bad_specs_are_rejected(self):
        for bad in ("muse-spark-1.3-contributor-free", "prov/", "/m", "prov/ m", "#high", "prov/m#a#b", "prov/m#a b"):
            tiers, problems = hs.load_shared({hs.STD_ENV: bad, hs.LITE_ENV: BOTH})
            self.assertEqual(tiers, {}, bad)
            self.assertEqual(len(problems), 1, bad)
            self.assertIn("HYBRID_OPENCODE_STD must be provider/model[#variant]", problems[0], bad)

    def test_env_defaults_to_os_environ(self):
        with mock.patch.dict(os.environ, {hs.STD_ENV: BOTH}):
            os.environ.pop(hs.LITE_ENV, None)
            tiers, problems = hs.load_shared()
        self.assertEqual(problems, [])
        self.assertEqual(tiers["lite"], {"model": "prov/big", "variant": "high"})
        with mock.patch.dict(os.environ):
            os.environ.pop(hs.STD_ENV, None)
            self.assertEqual(hs.load_shared(), ({}, ["HYBRID_OPENCODE_STD is not set"]))

    def test_explicit_env_ignores_os_environ(self):
        with mock.patch.dict(os.environ, {hs.STD_ENV: "os/wins"}):
            tiers, _ = hs.load_shared({hs.STD_ENV: "arg/wins"})
        self.assertEqual(tiers["std"]["model"], "arg/wins")


class TestPrecedence(unittest.TestCase):
    def test_skill_model_wins_and_never_takes_shared_variant(self):
        routing = {"preset": "hybrid", "tiers": {"std": {"model": "own/m", "max_parallel": 2, "timeout_s": 900}}}
        user = {"tiers": {"std": {"model": "own/m"}}}
        shared = {"std": {"model": "prov/big", "variant": "high"}}
        result = hs.resolve_tiers(routing, shared, user)
        self.assertEqual(result["tiers"]["std"], {"model": "own/m", "max_parallel": 2, "timeout_s": 900})
        self.assertEqual(result["model_sources"]["std"], "skill")
        self.assertEqual(result["preset"], "hybrid")
        self.assertEqual(routing["tiers"]["std"]["max_parallel"], 2)

    def test_skill_variant_and_max_parallel_kept(self):
        routing = {"tiers": {"std": {"model": "own/m", "variant": "low", "max_parallel": 1}}}
        user = {"tiers": {"std": {"model": "own/m", "variant": "low", "max_parallel": 1}}}
        shared = {"std": {"model": "prov/big", "variant": "high"}}
        result = hs.resolve_tiers(routing, shared, user)
        self.assertEqual(result["tiers"]["std"], {"model": "own/m", "variant": "low", "max_parallel": 1})

    def test_shared_used_when_skill_sets_no_model(self):
        routing = {"tiers": {"lite": {"variant": "stale", "max_parallel": 3}}}
        user = {"tiers": {"lite": {"variant": "stale", "max_parallel": 3}}}
        shared = {"lite": {"model": "prov/small", "variant": "low"}}
        result = hs.resolve_tiers(routing, shared, user)
        self.assertEqual(result["tiers"]["lite"], {"model": "prov/small", "variant": "low", "max_parallel": 3})
        self.assertEqual(result["model_sources"]["lite"], "shared")

    def test_shared_max_parallel_is_never_copied(self):
        routing = {"tiers": {"std": {"max_parallel": 2}}}
        result = hs.resolve_tiers(routing, {"std": {"model": "prov/big", "max_parallel": 9}}, {})
        self.assertEqual(result["tiers"]["std"], {"max_parallel": 2, "model": "prov/big"})
        result = hs.resolve_tiers({"tiers": {"std": {}}}, {"std": {"model": "prov/big", "max_parallel": 9}}, {})
        self.assertEqual(result["tiers"]["std"], {"model": "prov/big"})

    def test_env_loaded_tiers_resolve_as_shared(self):
        tiers, _ = hs.load_shared({hs.STD_ENV: BOTH, hs.LITE_ENV: "prov/small"})
        result = hs.resolve_tiers({"tiers": {"std": {"timeout_s": 5}}}, tiers, {})
        self.assertEqual(result["tiers"]["std"], {"timeout_s": 5, "model": "prov/big", "variant": "high"})
        self.assertEqual(result["tiers"]["lite"], {"model": "prov/small"})
        self.assertEqual(result["model_sources"], {"std": "shared", "lite": "shared"})

    def test_no_model_anywhere_is_none(self):
        result = hs.resolve_tiers({"tiers": {"std": {"timeout_s": 5}}}, {}, {})
        self.assertEqual(result["tiers"]["std"], {"timeout_s": 5})
        self.assertEqual(result["model_sources"], {"std": "none", "lite": "none"})


class TestModes(unittest.TestCase):
    def test_known_modes_map_to_themselves(self):
        for mode in hs.MODES:
            self.assertEqual(hs.mode_to_preset(mode), (mode, ""))
        self.assertEqual(hs.mode_to_preset(" Opencode "), ("opencode", ""))

    def test_max_alias_becomes_opencode_with_warning(self):
        preset, note = hs.mode_to_preset("max")
        self.assertEqual(preset, "opencode")
        self.assertIn("'max'", note)

    def test_unknown_mode_is_an_error(self):
        self.assertEqual(
            hs.mode_to_preset("turbo"),
            ("", "unknown mode 'turbo' (expected hybrid, claude or opencode)"),
        )
        self.assertEqual(hs.mode_to_preset("")[0], "")

    def test_model_spec(self):
        self.assertEqual(hs.model_spec({"model": "p/m", "variant": "high", "max_parallel": 2}), "p/m#high")
        self.assertEqual(hs.model_spec({"model": "p/m"}), "p/m")
        self.assertEqual(hs.model_spec({"variant": "high"}), "")
        self.assertEqual(hs.model_spec(None), "")

    def test_config_summary_ok(self):
        tiers = {"std": {"model": "p/m", "variant": "high"}, "lite": {"model": "p/f"}}
        self.assertEqual(
            hs.config_summary(tiers, []),
            "opencode config ok $HYBRID_OPENCODE_STD/$HYBRID_OPENCODE_LITE :: std=p/m#high, lite=p/f",
        )

    def test_config_summary_from_env(self):
        tiers, problems = hs.load_shared({hs.STD_ENV: BOTH})
        self.assertEqual(
            hs.config_summary(tiers, problems),
            "opencode config ok $HYBRID_OPENCODE_STD/$HYBRID_OPENCODE_LITE :: std=prov/big#high, lite=prov/big#high",
        )

    def test_config_summary_unusable(self):
        self.assertEqual(
            hs.config_summary(*hs.load_shared({})),
            "opencode config UNUSABLE $HYBRID_OPENCODE_STD/$HYBRID_OPENCODE_LITE :: HYBRID_OPENCODE_STD is not set"
            " (hybrid and opencode modes unavailable)",
        )
        self.assertEqual(
            hs.config_summary({}, ["a", "b", "c"]),
            "opencode config UNUSABLE $HYBRID_OPENCODE_STD/$HYBRID_OPENCODE_LITE :: a; b; c"
            " (hybrid and opencode modes unavailable)",
        )
        self.assertEqual(
            hs.config_summary({}, ["a", "b", "c", "d"]),
            "opencode config UNUSABLE $HYBRID_OPENCODE_STD/$HYBRID_OPENCODE_LITE :: a; b; c (+1 more)"
            " (hybrid and opencode modes unavailable)",
        )

    def test_config_summary_takes_no_path(self):
        with self.assertRaises(TypeError):
            hs.config_summary({}, ["a"], Path("/cfg/opencode.json"))


class TestDoctorCache(unittest.TestCase):
    TIER = {"model": "p/m", "variant": "high", "max_parallel": 3}
    ENTRY = {"ok": True, "key": "p/m#high", "checked_at": 1000.0, "kind": "", "detail": ""}

    def test_cache_key_is_model_and_variant(self):
        self.assertEqual(hs.cache_key(self.TIER), "p/m#high")
        self.assertEqual(hs.cache_key({"model": "p/m"}), "p/m")

    def test_fresh_within_ttl_only(self):
        self.assertTrue(hs.cache_fresh(self.ENTRY, self.TIER, 1000.0))
        self.assertTrue(hs.cache_fresh(self.ENTRY, self.TIER, 1000.0 + hs.DOCTOR_TTL_S - 1))
        self.assertFalse(hs.cache_fresh(self.ENTRY, self.TIER, 1000.0 + hs.DOCTOR_TTL_S))
        self.assertFalse(hs.cache_fresh(self.ENTRY, self.TIER, 999.0))

    def test_model_edit_invalidates_entry(self):
        self.assertFalse(hs.cache_fresh(self.ENTRY, {"model": "p/m", "variant": "low"}, 1001.0))
        self.assertFalse(hs.cache_fresh(self.ENTRY, {"model": "q/m", "variant": "high"}, 1001.0))

    def test_ok_flag_is_not_part_of_freshness(self):
        self.assertTrue(hs.cache_fresh(dict(self.ENTRY, ok=False), self.TIER, 1001.0))

    def test_malformed_entries_are_stale(self):
        for entry in ({}, None, dict(self.ENTRY, checked_at="1000"), dict(self.ENTRY, checked_at=True)):
            self.assertFalse(hs.cache_fresh(entry, self.TIER, 1001.0))
        self.assertFalse(hs.cache_fresh(dict(self.ENTRY, key=""), {}, 1001.0))


class TestClassify(unittest.TestCase):
    def test_clean_run_is_empty_kind(self):
        self.assertEqual(hs.classify(0, [], ""), "")
        self.assertEqual(hs.classify(0, [], "", finished=True), "")

    def test_runner_kinds(self):
        self.assertEqual(hs.classify(None, [], "spawn failed: No such file"), "spawn")
        self.assertEqual(hs.classify(-15, [], "", killed="timeout"), "timeout")
        self.assertEqual(hs.classify(-15, [], "", killed="stall"), "stall")
        self.assertEqual(hs.classify(-15, [], "", killed="timeout", finished=True), "timeout")

    def test_kind_table(self):
        cases = [
            ("auth", ["APIError: 401 Unauthorized"], ""),
            ("auth", [], "Error: Invalid API key provided"),
            ("auth", ["ProviderAuthError: token expired, please renew"], ""),
            ("quota", ["APIError: Insufficient balance"], ""),
            ("quota", [], "HTTP 402 Payment Required"),
            ("model", ["ProviderModelNotFoundError: prov/nope"], ""),
            ("model", [], "Error: model prov/nope not found"),
            ("model", ["unknown model 'x'"], ""),
            ("throttle", ["APIError: 429 Too Many Requests"], ""),
            ("throttle", [], "rate limit reached"),
            ("context", ["APIError: context length exceeded"], ""),
            ("crash", [], "Segmentation fault"),
            ("crash", ["UnknownError: boom"], ""),
        ]
        for kind, errors, tail in cases:
            self.assertEqual(hs.classify(1, errors, tail), kind, (errors, tail))

    def test_provider_auth_error_is_auth(self):
        self.assertEqual(hs.classify(1, ["ProviderAuthError: bad key"], ""), "auth")

    def test_stack_trace_line_numbers_are_not_http_codes(self):
        for n in (401, 402, 403):
            tail = "TypeError x\n    at foo (/src/index.js:%d:9)" % n
            self.assertEqual(hs.classify(1, [], tail), "crash", n)

    def test_colon_adjacent_http_codes_still_classify(self):
        self.assertEqual(hs.classify(1, [], "HTTP 403: Forbidden"), "auth")
        self.assertEqual(hs.classify(1, [], '{"statusCode":401,"message":"x"}'), "auth")
        self.assertEqual(hs.classify(1, [], "Request failed with status code 402: Payment Required"), "quota")

    def test_colon_adjacent_codes_in_messages_and_json(self):
        self.assertEqual(hs.classify(1, ["HTTP 402: Payment Required"], ""), "quota")
        self.assertEqual(hs.classify(1, ["Error 403: Forbidden"], ""), "auth")
        self.assertEqual(hs.classify(1, ['{"statusCode":402}'], ""), "quota")
        self.assertEqual(hs.classify(1, ['{"status":403}'], ""), "auth")

    def test_stack_frame_column_numbers_are_not_http_codes(self):
        for n in (401, 402, 403):
            tail = "TypeError x\n    at foo (/src/index.js:12:%d)" % n
            self.assertEqual(hs.classify(1, [], tail), "crash", n)

    def test_http_codes_still_match_with_punctuation(self):
        self.assertEqual(hs.classify(1, ["APIError: 401 Unauthorized"], ""), "auth")
        self.assertEqual(hs.classify(1, [], "HTTP 402 Payment Required"), "quota")
        self.assertEqual(hs.classify(1, [], "status 403 Forbidden"), "auth")

    def test_recovered_needs_finish_and_exit_one(self):
        self.assertEqual(hs.classify(1, ["APIError: 429 Too Many Requests"], "", finished=True), "recovered")
        self.assertEqual(hs.classify(1, [], "", finished=True), "recovered")
        self.assertEqual(hs.classify(1, [], "", finished=False), "crash")
        self.assertEqual(hs.classify(2, [], "", finished=True), "crash")

    def test_error_event_with_exit_zero_still_fails(self):
        self.assertEqual(hs.classify(0, ["ProviderAuthError: Unauthorized"], ""), "auth")

    def test_v2_error_types_map_to_kinds(self):
        cases = [
            ("model", "provider.no-route: Model unavailable: nosuch/model"),
            ("model", "provider.no-route: Variant unavailable: max"),
            ("auth", "provider.auth (HTTP 403): OpenCode's free tier can only be used from within OpenCode"),
            ("auth", "provider.auth: Authorization failed"),
            ("quota", "provider.quota: credit balance is too low"),
            ("config", 'unknown: Agent not found: "x"'),
            ("throttle", "provider.rate-limit (HTTP 429)"),
            ("crash", "provider.timeout: Request timed out"),
            ("crash", "unknown: Transport: The socket connection was closed unexpectedly"),
        ]
        for kind, note in cases:
            self.assertEqual(hs.classify(1, [note], ""), kind, note)

    def test_provider_timeout_is_a_retryable_crash(self):
        kind = hs.classify(1, ["provider.timeout: Request timed out"], "")
        self.assertTrue(hs.should_retry(kind, 0))

    def test_context_pattern_is_narrow(self):
        for tail in ("RangeError: Stack overflow in parser", "bash: ls: Argument list too long",
                     "ENAMETOOLONG: file name too long"):
            self.assertEqual(hs.classify(1, [], tail), "crash", tail)
        for note in ("APIError: prompt is too long: 213000 tokens > 200000 maximum",
                     "APIError: maximum context length is 128000 tokens", "APIError: context_length_exceeded",
                     "APIError: exceeds the context window", "APIError: too many tokens"):
            self.assertEqual(hs.classify(1, [note], ""), "context", note)

    def test_traceback_line_numbers_are_not_http_codes(self):
        for n, kind in ((401, "auth"), (402, "quota"), (403, "auth"), (429, "throttle")):
            tail = 'Traceback\n  File "/src/run.py", line %d, in main\nValueError' % n
            self.assertEqual(hs.classify(1, [], tail), "crash", n)
            self.assertEqual(hs.classify(1, [], "HTTP %d: x" % n), kind, n)

    def test_error_note(self):
        self.assertEqual(hs.error_note({"type": "provider.auth", "status": 403, "message": "no"}),
                         "provider.auth (HTTP 403): no")
        self.assertEqual(hs.error_note({"type": "provider.rate-limit", "status": "429"}),
                         "provider.rate-limit (HTTP 429)")
        self.assertEqual(hs.error_note({"type": "APIError", "message": "429 x"}), "APIError: 429 x")
        self.assertEqual(hs.error_note({"type": "t", "status": True}), "t")
        self.assertEqual(hs.error_note("nope"), "error")

    def test_first_error(self):
        errors = ["", "APIError:\n  401\tUnauthorized", "second"]
        self.assertEqual(hs.first_error(errors, "tail"), "APIError: 401 Unauthorized")
        self.assertEqual(hs.first_error([], "line one\nline two\n"), "line one line two")
        long_tail = "x" * 300 + " END"
        self.assertEqual(hs.first_error([], long_tail), long_tail[-200:])
        self.assertEqual(hs.first_error(None, ""), "")


class TestOcLine(unittest.TestCase):
    def test_format_with_log(self):
        line = hs.oc_line("OC-ERROR", "hybrid-team", "S3", "std", "p/m#high", "auth", "APIError: 401", log="/r/S3.err")
        self.assertEqual(line, "OC-ERROR hybrid-team S3 tier=std model=p/m#high kind=auth :: APIError: 401 log=/r/S3.err")

    def test_single_line_and_detail_cap(self):
        line = hs.oc_line("OC-WARN", "hybrid-brainstorming", "L1", "lite", "p/f", "empty", "a\nb\r\n" + "z" * 500)
        self.assertNotIn("\n", line)
        self.assertNotIn("\r", line)
        detail = line.split(" :: ", 1)[1]
        self.assertEqual(len(detail), 200)
        self.assertTrue(detail.startswith("a b zzz"))
        self.assertTrue(detail.endswith("..."))

    def test_empty_fields_and_level_alias(self):
        line = hs.oc_line("warn", "hybrid-writing-plans", "", "", "", "format", "")
        self.assertEqual(line, "OC-WARN hybrid-writing-plans - tier=- model=- kind=format :: -")
        line = hs.oc_line("error", "hybrid-team", "S 1", "std", "p/m", "crash", "x")
        self.assertTrue(line.startswith("OC-ERROR hybrid-team S_1 tier=std "))


class TestReportLog(TempDirCase):
    def test_take_unreported_returns_each_line_once(self):
        path = self.root / "run" / "oc-errors.jsonl"
        self.assertEqual(hs.take_unreported(path), [])
        hs.log_line(path, "OC-ERROR a b tier=std model=p/m kind=auth :: x")
        hs.log_line(path, "OC-WARN a c tier=lite model=p/f kind=empty :: y")
        self.assertEqual(hs.take_unreported(path), [
            "OC-ERROR a b tier=std model=p/m kind=auth :: x",
            "OC-WARN a c tier=lite model=p/f kind=empty :: y",
        ])
        self.assertEqual(hs.take_unreported(path), [])
        hs.log_line(path, "OC-ERROR a d tier=std model=p/m kind=crash :: z")
        self.assertEqual(hs.take_unreported(path), ["OC-ERROR a d tier=std model=p/m kind=crash :: z"])

    def test_partial_trailing_record_waits_for_next_call(self):
        path = self.root / "oc-errors.jsonl"
        hs.log_line(path, "first")
        with open(str(path), "a", encoding="utf-8") as fh:
            fh.write('{"line": "sec')
        self.assertEqual(hs.take_unreported(path), ["first"])
        with open(str(path), "a", encoding="utf-8") as fh:
            fh.write('ond"}\n')
        self.assertEqual(hs.take_unreported(path), ["second"])

    def test_seen_offset_is_written_atomically(self):
        path = self.root / "oc-errors.jsonl"
        hs.log_line(path, "one")
        with mock.patch.object(hs.os, "replace", wraps=os.replace) as replace:
            self.assertEqual(hs.take_unreported(path), ["one"])
        self.assertEqual(replace.call_count, 1)
        self.assertEqual(replace.call_args[0][1], str(path) + ".seen")
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["oc-errors.jsonl", "oc-errors.jsonl.seen"])

    def test_failed_offset_write_keeps_the_old_offset(self):
        path = self.root / "oc-errors.jsonl"
        hs.log_line(path, "one")
        hs.take_unreported(path)
        seen = self.root / "oc-errors.jsonl.seen"
        old = seen.read_text(encoding="utf-8")
        hs.log_line(path, "two")
        with mock.patch.object(hs.os, "replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                hs.take_unreported(path)
        self.assertEqual(seen.read_text(encoding="utf-8"), old)
        self.assertEqual(hs.take_unreported(path), ["two"])

    def test_records_are_json_with_timestamp(self):
        path = self.root / "oc-errors.jsonl"
        hs.log_line(path, "OC-WARN a\nb")
        record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(record["line"], "OC-WARN a b")
        self.assertIsInstance(record["ts"], float)


class TestBreaker(TempDirCase):
    def setUp(self):
        super().setUp()
        self.state = self.root / "lanes"

    def test_closed_by_default(self):
        self.assertEqual(hs.breaker_open(self.state, "std", "p/m#high"), {})
        self.assertEqual(hs.breaker_skip(self.state, "std", "p/m#high"), 0)
        self.assertEqual(hs.breaker_summary(self.state, "hybrid-brainstorming"), [])

    def test_retryable_kinds_never_trip(self):
        for kind in ("throttle", "crash", "timeout", "stall", "spawn", "context", "recovered"):
            self.assertFalse(hs.breaker_trip(self.state, "std", "p/m", kind, "x"))
        self.assertEqual(hs.breaker_open(self.state, "std", "p/m"), {})

    def test_trip_open_skip_and_summary(self):
        self.assertTrue(hs.breaker_trip(self.state, "std", "p/m#high", "auth", "APIError: 401\nUnauthorized"))
        self.assertFalse(hs.breaker_trip(self.state, "std", "p/m#high", "quota", "later"))
        entry = hs.breaker_open(self.state, "std", "p/m#high")
        self.assertEqual(entry["kind"], "auth")
        self.assertEqual(entry["detail"], "APIError: 401 Unauthorized")
        self.assertEqual(entry["skipped"], 0)
        self.assertEqual(hs.breaker_open(self.state, "std", "p/m#low"), {})
        self.assertEqual(hs.breaker_open(self.state, "lite", "p/m#high"), {})
        self.assertEqual(hs.breaker_skip(self.state, "std", "p/m#high"), 1)
        self.assertEqual(hs.breaker_skip(self.state, "std", "p/m#high"), 2)
        self.assertEqual(hs.breaker_open(self.state, "std", "p/m#high")["skipped"], 2)
        self.assertEqual(hs.breaker_summary(self.state, "hybrid-team"), [
            "OC-ERROR hybrid-team breaker tier=std model=p/m#high kind=breaker"
            " :: 2 units skipped after kind=auth: APIError: 401 Unauthorized",
        ])

    def test_summary_ignores_breakers_without_skipped_units(self):
        self.assertTrue(hs.breaker_trip(self.state, "lite", "p/f", "model", "not found"))
        self.assertEqual(hs.breaker_summary(self.state, "hybrid-team"), [])


class TestRetryPolicy(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(hs.CONNECTION_KINDS, ("spawn", "stall", "throttle", "crash"))
        self.assertEqual(hs.OC_RETRIES, 3)
        self.assertEqual(hs.RETRY_DELAYS_S, (10, 30, 60))
        self.assertEqual(hs.RETRY_DELAY_ENV, "HYBRID_OC_RETRY_DELAY_S")
        self.assertEqual(hs.FALLBACK_MODEL, "sonnet")
        self.assertEqual(hs.SWITCH_FILE, "oc-switched.json")

    def test_should_retry_boundaries(self):
        for kind in hs.CONNECTION_KINDS:
            for done in range(hs.OC_RETRIES):
                self.assertTrue(hs.should_retry(kind, done), (kind, done))
            self.assertFalse(hs.should_retry(kind, hs.OC_RETRIES), kind)
            self.assertFalse(hs.should_retry(kind, hs.OC_RETRIES + 1), kind)

    def test_should_retry_never_for_other_kinds(self):
        others = hs.NON_RETRYABLE + ("timeout", "context", "grounding", "lint", "oracle", "gate", "empty",
                                     "format", "recovered", "switch", "breaker", "")
        for kind in others:
            self.assertFalse(hs.should_retry(kind, 0), kind)

    def test_retry_delay_defaults(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(hs.RETRY_DELAY_ENV, None)
            self.assertEqual([hs.retry_delay(n) for n in range(3)], [10, 30, 60])
            self.assertEqual(hs.retry_delay(3), 60)
            self.assertEqual(hs.retry_delay(99), 60)

    def test_retry_delay_env_overrides_every_delay(self):
        with mock.patch.dict(os.environ, {hs.RETRY_DELAY_ENV: "0"}):
            self.assertEqual([hs.retry_delay(n) for n in range(5)], [0] * 5)
        with mock.patch.dict(os.environ, {hs.RETRY_DELAY_ENV: " 7 "}):
            self.assertEqual([hs.retry_delay(n) for n in range(3)], [7, 7, 7])

    def test_retry_delay_ignores_non_digit_env(self):
        for raw in ("", "  ", "abc", "-1", "1.5"):
            with mock.patch.dict(os.environ, {hs.RETRY_DELAY_ENV: raw}):
                self.assertEqual(hs.retry_delay(0), 10, repr(raw))
                self.assertEqual(hs.retry_delay(2), 60, repr(raw))

    def test_switches_run(self):
        for kind in hs.CONNECTION_KINDS + hs.NON_RETRYABLE:
            self.assertTrue(hs.switches_run(kind), kind)
        for kind in ("timeout", "context", "grounding", "lint", "oracle", "gate", "empty", "format",
                     "recovered", "switch", "breaker", ""):
            self.assertFalse(hs.switches_run(kind), kind)


class TestSwitch(TempDirCase):
    def setUp(self):
        super().setUp()
        self.state = self.root / "run" / "lanes"

    def test_unswitched_by_default(self):
        self.assertEqual(hs.run_switched(self.state), {})

    def test_first_caller_wins_and_record_is_kept(self):
        self.assertTrue(hs.switch_to_claude(self.state, "S3", "std", "p/m#high", "throttle", "429\nToo Many"))
        self.assertFalse(hs.switch_to_claude(self.state, "S4", "lite", "p/f", "auth", "later"))
        entry = hs.run_switched(self.state)
        self.assertEqual({k: entry[k] for k in ("unit", "tier", "spec", "kind", "detail")}, {
            "unit": "S3", "tier": "std", "spec": "p/m#high", "kind": "throttle", "detail": "429 Too Many"})
        self.assertIsInstance(entry["switched_at"], float)
        self.assertTrue((self.state / hs.SWITCH_FILE).is_file())

    def test_switch_is_per_state_dir(self):
        self.assertTrue(hs.switch_to_claude(self.state, "S1", "std", "p/m", "crash", "x"))
        other = self.root / "next-run"
        self.assertEqual(hs.run_switched(other), {})
        self.assertTrue(hs.switch_to_claude(other, "S1", "std", "p/m", "crash", "x"))

    def test_run_switched_missing_or_corrupt_is_empty(self):
        self.state.mkdir(parents=True)
        path = self.state / hs.SWITCH_FILE
        self.assertEqual(hs.run_switched(self.state), {})
        for raw in ("", "not json", '{"unit": ', "[1, 2]", '"str"', "null"):
            path.write_text(raw, encoding="utf-8")
            self.assertEqual(hs.run_switched(self.state), {}, repr(raw))
        path.write_text('{"unit": "S1", "kind": "spawn"}', encoding="utf-8")
        self.assertEqual(hs.run_switched(self.state)["kind"], "spawn")

    def test_detail_is_capped(self):
        hs.switch_to_claude(self.state, "S1", "std", "p/m", "stall", "z" * 500)
        self.assertLessEqual(len(hs.run_switched(self.state)["detail"]), 200)

    def test_exactly_one_thread_wins(self):
        import threading
        results = []
        start = threading.Barrier(8)

        def worker(n):
            start.wait()
            results.append((n, hs.switch_to_claude(self.state, "S%d" % n, "std", "p/m", "crash", "x")))

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        winners = [n for n, won in results if won]
        self.assertEqual(len(results), 8)
        self.assertEqual(len(winners), 1)
        self.assertEqual(hs.run_switched(self.state)["unit"], "S%d" % winners[0])

    def test_exactly_one_process_wins(self):
        code = ("import sys; sys.path.insert(0, %r); import hybrid_shared as hs; "
                "print(hs.switch_to_claude(sys.argv[1], sys.argv[2], 'std', 'p/m', 'crash', 'x'))"
                % str(Path(hs.__file__).resolve().parent))
        procs = [subprocess.Popen([sys.executable, "-c", code, str(self.state), "S%d" % n],
                                  stdout=subprocess.PIPE, universal_newlines=True) for n in range(4)]
        outs = [p.communicate()[0].strip() for p in procs]
        self.assertEqual([p.returncode for p in procs], [0] * 4)
        self.assertEqual(sorted(outs), ["False", "False", "False", "True"])
        self.assertEqual(hs.run_switched(self.state)["unit"], "S%d" % outs.index("True"))

    def test_switch_line_text(self):
        entry = {"unit": "S3", "tier": "std", "spec": "p/m#high", "kind": "throttle", "detail": "429 Too Many"}
        self.assertEqual(hs.switch_line("hybrid-team", entry),
                         "OC-ERROR hybrid-team S3 tier=std model=p/m#high kind=switch"
                         " :: opencode throttle: 429 Too Many; the rest of this run uses Claude sonnet")

    def test_switch_line_from_recorded_entry_is_one_line(self):
        hs.switch_to_claude(self.state, "L1", "lite", "p/f", "auth", "APIError: 401\nUnauthorized")
        line = hs.switch_line("hybrid-brainstorming", hs.run_switched(self.state))
        self.assertNotIn("\n", line)
        self.assertEqual(line, "OC-ERROR hybrid-brainstorming L1 tier=lite model=p/f kind=switch"
                               " :: opencode auth: APIError: 401 Unauthorized; the rest of this run uses Claude sonnet")


class TestCli(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(hs.STD_ENV, None)
        os.environ.pop(hs.LITE_ENV, None)

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = hs.cli(list(argv))
        return rc, out.getvalue().splitlines()

    def test_config_with_std_unset_exits_zero(self):
        rc, lines = self.run_cli("config")
        self.assertEqual(rc, 0)
        self.assertEqual(lines, [
            "opencode config UNUSABLE %s :: HYBRID_OPENCODE_STD is not set (hybrid and opencode modes unavailable)"
            % SUMMARY_SRC,
        ])

    def test_check_with_std_unset_prints_oc_error_and_fails(self):
        rc, lines = self.run_cli("check", "--skill", "hybrid-team")
        self.assertEqual(rc, 1)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("opencode config UNUSABLE "))
        self.assertEqual(lines[1], "OC-ERROR hybrid-team config tier=- model=- kind=config :: HYBRID_OPENCODE_STD is not set")

    def test_check_reads_the_process_environment(self):
        os.environ[hs.STD_ENV] = "prov/big#high"
        os.environ[hs.LITE_ENV] = "prov/small"
        self.assertEqual(self.run_cli("check"), (0, [
            "opencode config ok %s :: std=prov/big#high, lite=prov/small" % SUMMARY_SRC,
        ]))

    def test_mode(self):
        self.assertEqual(self.run_cli("mode", "claude"), (0, ["preset=claude"]))
        rc, lines = self.run_cli("mode", "max", "--skill", "hybrid-team")
        self.assertEqual(rc, 0)
        self.assertTrue(lines[0].startswith("OC-WARN hybrid-team config tier=- model=- kind=config :: "))
        self.assertEqual(lines[1], "preset=opencode")
        rc, lines = self.run_cli("mode", "turbo")
        self.assertEqual(rc, 2)
        self.assertEqual(lines, [
            "OC-ERROR hybrid-skills config tier=- model=- kind=config"
            " :: unknown mode 'turbo' (expected hybrid, claude or opencode)",
        ])

    def test_bad_usage_returns_code_instead_of_exiting(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(hs.cli([]), 2)
            self.assertEqual(hs.cli(["mode"]), 2)

    def test_init_is_gone_and_fails_in_argparse(self):
        err = io.StringIO()
        with redirect_stderr(err), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(hs.cli(["init", "--std", "prov/big#high"]), 2)
        self.assertEqual(out.getvalue(), "")
        self.assertIn("invalid choice", err.getvalue())


class TestCliSubprocess(unittest.TestCase):
    def test_config_std_unset_exits_zero(self):
        proc = _run_script("config")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), [
            "opencode config UNUSABLE %s :: HYBRID_OPENCODE_STD is not set (hybrid and opencode modes unavailable)"
            % SUMMARY_SRC,
        ])

    def test_config_lite_alone_is_unusable_but_exits_zero(self):
        proc = _run_script("config", lite="prov/small")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("HYBRID_OPENCODE_STD is not set", proc.stdout)

    def test_config_std_only_lite_follows_std(self):
        proc = _run_script("config", std="prov/big#high")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), [
            "opencode config ok %s :: std=prov/big#high, lite=prov/big#high" % SUMMARY_SRC,
        ])

    def test_config_lite_override(self):
        proc = _run_script("config", std="prov/big#high", lite="prov/small")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), [
            "opencode config ok %s :: std=prov/big#high, lite=prov/small" % SUMMARY_SRC,
        ])

    def test_config_invalid_value_still_exits_zero(self):
        proc = _run_script("config", std="no-provider")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("opencode config UNUSABLE", proc.stdout)
        self.assertIn("HYBRID_OPENCODE_STD must be provider/model[#variant], got 'no-provider'", proc.stdout)

    def test_check_ok_exits_zero_without_oc_error(self):
        proc = _run_script("check", "--skill", "hybrid-team", std="prov/big#high", lite="prov/small#low")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), [
            "opencode config ok %s :: std=prov/big#high, lite=prov/small#low" % SUMMARY_SRC,
        ])

    def test_check_std_unset_fails_with_oc_error(self):
        proc = _run_script("check", "--skill", "hybrid-team")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("opencode config UNUSABLE %s" % SUMMARY_SRC))
        self.assertEqual(lines[1], "OC-ERROR hybrid-team config tier=- model=- kind=config :: HYBRID_OPENCODE_STD is not set")

    def test_check_invalid_lite_names_lite(self):
        proc = _run_script("check", std="prov/big", lite="nope")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertIn("HYBRID_OPENCODE_LITE must be provider/model[#variant], got 'nope'", lines[0])
        self.assertTrue(lines[1].startswith("OC-ERROR hybrid-skills config tier=- model=- kind=config :: HYBRID_OPENCODE_LITE must be"))

    def test_mode_does_not_depend_on_the_environment(self):
        proc = _run_script("mode", "hybrid")
        self.assertEqual((proc.returncode, proc.stdout.splitlines()), (0, ["preset=hybrid"]))
        proc = _run_script("mode", "turbo", std="prov/big")
        self.assertEqual(proc.returncode, 2)

    def test_init_subcommand_is_removed(self):
        proc = _run_script("init", "--std", "prov/big#high", std="prov/big")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertIn("invalid choice", proc.stderr)
        self.assertIn("'init'", proc.stderr)


class RunModelsTest(TempDirCase):
    """opencode v2.0.20 answers the first `models` call after an idle service with an empty list."""

    def _binary(self, empty_calls):
        counter = self.root / "calls"
        script = self.root / "opencode"
        script.write_text(
            "#!/bin/sh\n"
            'echo x >> "%s"\n'
            'n=$(wc -l < "%s")\n'
            '[ "$n" -le %d ] && exit 0\n'
            "echo opencode/some-model\n" % (counter, counter, empty_calls))
        script.chmod(0o755)
        return str(script), counter

    def test_empty_first_answer_is_retried(self):
        binary, counter = self._binary(empty_calls=1)
        with mock.patch.dict(os.environ, {hs.RETRY_DELAY_ENV: "0"}):
            proc = hs.run_models(binary, 10)
        self.assertEqual(proc.stdout.split(), ["opencode/some-model"])
        self.assertEqual(len(counter.read_text().split()), 2)

    def test_output_is_read_through_a_file_not_a_pipe(self):
        # opencode v2.0.20 exits before flushing a pipe; a file-backed stdout keeps the whole answer
        script = self.root / "opencode"
        script.write_text("#!/bin/sh\n[ -p /dev/stdout ] && exit 0\necho a/one\necho a/two\n")
        script.chmod(0o755)
        proc = hs.run_models(str(script), 10)
        self.assertEqual(proc.stdout.split(), ["a/one", "a/two"])
        self.assertEqual(hs.run_captured([str(script)], 10).stdout.split(), ["a/one", "a/two"])

    def test_full_first_answer_is_not_repeated(self):
        binary, counter = self._binary(empty_calls=0)
        proc = hs.run_models(binary, 10)
        self.assertEqual(proc.stdout.split(), ["opencode/some-model"])
        self.assertEqual(len(counter.read_text().split()), 1)

    def test_still_empty_after_the_retries_is_returned_empty(self):
        binary, counter = self._binary(empty_calls=99)
        with mock.patch.dict(os.environ, {hs.RETRY_DELAY_ENV: "0"}):
            proc = hs.run_models(binary, 10)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertEqual(len(counter.read_text().split()), hs.MODELS_EMPTY_RETRIES + 1)


class SessionScopeTest(TempDirCase):
    """The switch to Claude and the breakers belong to one Claude Code session and one flow."""

    def _as(self, session):
        return mock.patch.dict(os.environ, {hs.SESSION_ENV: session}) if session else mock.patch.dict(
            os.environ, {}, clear=False)

    def test_switch_does_not_survive_a_new_session(self):
        with self._as("sess-A"):
            self.assertTrue(hs.switch_to_claude(self.root, "T1", "std", "m/x#y", "spawn", "down"))
            self.assertEqual(hs.run_switched(self.root)["unit"], "T1")
            self.assertFalse(hs.switch_to_claude(self.root, "T2", "std", "m/x#y", "spawn", "down"))
        with self._as("sess-B"):
            self.assertEqual(hs.run_switched(self.root), {})
            # the stale record is replaced, and the new session can switch again
            self.assertTrue(hs.switch_to_claude(self.root, "T3", "std", "m/x#y", "crash", "down"))
            self.assertEqual(hs.run_switched(self.root)["unit"], "T3")

    def test_breaker_does_not_survive_a_new_session(self):
        with self._as("sess-A"):
            self.assertTrue(hs.breaker_trip(self.root, "std", "m/x#y", "auth", "bad key"))
            self.assertTrue(hs.breaker_open(self.root, "std", "m/x#y"))
            self.assertEqual(hs.breaker_skip(self.root, "std", "m/x#y"), 1)
        with self._as("sess-B"):
            self.assertEqual(hs.breaker_open(self.root, "std", "m/x#y"), {})
            self.assertEqual(hs.breaker_skip(self.root, "std", "m/x#y"), 0)
            self.assertEqual(hs.breaker_summary(self.root, "skill"), [])
            self.assertTrue(hs.breaker_trip(self.root, "std", "m/x#y", "quota", "no credit"))
            self.assertEqual(hs.breaker_open(self.root, "std", "m/x#y")["kind"], "quota")

    def test_same_session_keeps_the_switch(self):
        with self._as("sess-A"):
            hs.switch_to_claude(self.root, "T1", "std", "m/x#y", "spawn", "down")
        with self._as("sess-A"):
            self.assertEqual(hs.run_switched(self.root)["unit"], "T1")

    def test_reset_run_state_starts_a_new_flow(self):
        with self._as("sess-A"):
            hs.switch_to_claude(self.root, "T1", "std", "m/x#y", "spawn", "down")
            hs.breaker_trip(self.root, "lite", "m/x#y", "model", "unknown")
            (self.root / "cooldown-std").write_text("1")
            hs.reset_run_state(self.root)
            self.assertEqual(hs.run_switched(self.root), {})
            self.assertEqual(hs.breaker_open(self.root, "lite", "m/x#y"), {})
            self.assertFalse((self.root / "cooldown-std").exists())

    def test_reset_cli(self):
        with self._as("sess-A"):
            hs.switch_to_claude(self.root, "T1", "std", "m/x#y", "spawn", "down")
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(hs.cli(["reset", str(self.root)]), 0)
            self.assertEqual(hs.run_switched(self.root), {})


if __name__ == "__main__":
    unittest.main()
