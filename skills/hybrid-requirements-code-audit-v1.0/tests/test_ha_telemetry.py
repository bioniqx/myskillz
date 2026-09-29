import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ha_telemetry  # noqa: E402


class TestPathRecordLoad(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_telemetry_path_env_override(self):
        target = self.root / "t" / "lanes.jsonl"
        with mock.patch.dict(os.environ, {"HA_TELEMETRY": str(target)}):
            self.assertEqual(ha_telemetry.telemetry_path(), target)

    def test_telemetry_path_default_under_home(self):
        env = dict(os.environ)
        env.pop("HA_TELEMETRY", None)
        env["HOME"] = str(self.root)
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(
                ha_telemetry.telemetry_path(),
                self.root / ".cache" / "hybrid-requirements-code-audit" / "lanes.jsonl",
            )

    def test_record_appends_lines_and_adds_t(self):
        target = self.root / "sub" / "lanes.jsonl"
        with mock.patch.dict(os.environ, {"HA_TELEMETRY": str(target)}):
            ha_telemetry.record({"kind": "run", "name": "batch-01"})
            ha_telemetry.record({"kind": "item", "id": "R1", "t": "2026-01-01T00:00:00Z"})
        lines = target.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        first = json.loads(lines[0])
        second = json.loads(lines[1])
        self.assertEqual(first["kind"], "run")
        self.assertEqual(first["name"], "batch-01")
        self.assertRegex(first["t"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(second["t"], "2026-01-01T00:00:00Z")

    def test_record_swallows_write_failure(self):
        blocker = self.root / "file.txt"
        blocker.write_text("x", encoding="utf-8")
        target = blocker / "lanes.jsonl"
        with mock.patch.dict(os.environ, {"HA_TELEMETRY": str(target)}):
            self.assertIsNone(ha_telemetry.record({"kind": "run"}))
        self.assertFalse(target.exists())

    def test_load_records_skips_bad_lines(self):
        target = self.root / "lanes.jsonl"
        target.write_text(
            '{"kind": "run", "name": "a"}\n\nnot json\n[1, 2]\n{"kind": "item", "id": "R1"}\n',
            encoding="utf-8",
        )
        recs = ha_telemetry.load_records(target)
        self.assertEqual(recs, [{"kind": "run", "name": "a"}, {"kind": "item", "id": "R1"}])

    def test_load_records_missing_file(self):
        self.assertEqual(ha_telemetry.load_records(self.root / "absent.jsonl"), [])


RUNS = [
    {"kind": "run", "repo": "/r", "name": "batch-01", "role": "investigator", "tier": "std",
     "model": "zai-coding-plan/glm-5.3", "variant": "high", "items": 4, "rounds": 1, "round1_valid": 4,
     "oracle": {"foreign": 0, "dropped": 1, "demoted": 1, "invalid_status": 0},
     "outcome": "ok", "reason": "", "duration_s": 40.0,
     "tokens": {"input": 100, "output": 10, "reasoning": 5, "cache_read": 0, "cache_write": 0}},
    {"kind": "run", "repo": "/r", "name": "batch-02", "role": "investigator", "tier": "std",
     "model": "zai-coding-plan/glm-5.3", "variant": "high", "items": 2, "rounds": 3, "round1_valid": 0,
     "oracle": {"foreign": 0, "dropped": 0, "demoted": 0, "invalid_status": 0},
     "outcome": "fallback", "reason": "format", "duration_s": 30.0,
     "tokens": {"input": 50, "output": 5, "reasoning": 0, "cache_read": 0, "cache_write": 0}},
    {"kind": "run", "repo": "/other", "name": "batch-V01", "role": "verifier", "tier": "std",
     "model": "zai-coding-plan/glm-5.3", "variant": "high", "items": 4, "rounds": 1, "round1_valid": 4,
     "oracle": {"foreign": 0, "dropped": 0, "demoted": 0, "invalid_status": 0},
     "outcome": "ok", "reason": "", "duration_s": 20.0,
     "tokens": {"input": 10, "output": 1, "reasoning": 0, "cache_read": 0, "cache_write": 0}},
]

ITEMS = [
    {"kind": "item", "repo": "/r", "id": "R1", "backend": "oc:std", "inv": "MATCHED", "ver": "MATCHED",
     "final": "MATCHED", "verifier_overturned": False, "lead_overturned": False},
    {"kind": "item", "repo": "/r", "id": "R2", "backend": "oc:std", "inv": "MATCHED", "ver": "PARTIAL",
     "final": "PARTIAL", "verifier_overturned": True, "lead_overturned": False},
    {"kind": "item", "repo": "/r", "id": "R3", "backend": "claude", "inv": "MISSING", "ver": None,
     "final": "MATCHED", "verifier_overturned": False, "lead_overturned": True},
]


class TestStatsLines(unittest.TestCase):
    def test_no_records(self):
        self.assertEqual(ha_telemetry.stats_lines([]), ["telemetry: no records"])
        self.assertEqual(ha_telemetry.stats_lines(RUNS, repo="/nowhere"),
                         ["telemetry: no records for repo /nowhere"])

    def test_all_repos(self):
        lines = ha_telemetry.stats_lines(RUNS + ITEMS + ["junk", {"kind": "other"}])
        self.assertEqual(lines, [
            "telemetry: 3 runs, 3 items",
            "run role=investigator backend=oc:std runs=2 items=6 round1_valid=67% (4/6) "
            "fallback=50% (1/2) reasons=format:1 oracle_dropped=1 oracle_demoted=17% (1/6) "
            "median_s_per_item=12.5 tokens=in:150 out:15 reasoning:5",
            "run role=verifier backend=oc:std runs=1 items=4 round1_valid=100% (4/4) "
            "fallback=0% (0/1) reasons=- oracle_dropped=0 oracle_demoted=0% (0/4) "
            "median_s_per_item=5.0 tokens=in:10 out:1 reasoning:0",
            "items backend=claude n=1 verifier_overturn=- lead_overturn=100% (1/1)",
            "items backend=oc:std n=2 verifier_overturn=50% (1/2) lead_overturn=0% (0/2)",
        ])

    def test_repo_filter(self):
        lines = ha_telemetry.stats_lines(RUNS + ITEMS, repo="/r/")
        self.assertEqual(lines[0], "telemetry: 2 runs, 3 items for repo /r")
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[1].startswith("run role=investigator backend=oc:std runs=2 "))
        self.assertFalse(any(line.startswith("run role=verifier") for line in lines))

    def test_parser_run_with_zero_items(self):
        rec = {"kind": "run", "repo": "/r", "role": "parser", "tier": "lite", "items": 0, "rounds": 1,
               "round1_valid": 0, "oracle": {}, "outcome": "ok", "reason": "", "duration_s": 8.0,
               "tokens": {"input": 7, "output": 2, "reasoning": 1}}
        lines = ha_telemetry.stats_lines([rec])
        self.assertEqual(lines, [
            "telemetry: 1 runs, 0 items",
            "run role=parser backend=oc:lite runs=1 items=0 round1_valid=- fallback=0% (0/1) reasons=- "
            "oracle_dropped=0 oracle_demoted=- median_s_per_item=8.0 tokens=in:7 out:2 reasoning:1",
        ])


if __name__ == "__main__":
    unittest.main()
