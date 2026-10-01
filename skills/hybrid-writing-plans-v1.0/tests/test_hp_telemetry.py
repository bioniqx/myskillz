import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hp_telemetry  # noqa: E402


class TelemetryFileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_default_path_is_under_home(self):
        with mock.patch.dict(os.environ, {"HOME": str(self.root)}):
            os.environ.pop("HYBRID_WRITING_PLANS_TELEMETRY", None)
            self.assertEqual(hp_telemetry.telemetry_path(),
                             self.root / ".cache" / "hybrid-writing-plans" / "lanes.jsonl")

    def test_env_overrides_path(self):
        target = self.root / "t" / "lanes.jsonl"
        with mock.patch.dict(os.environ, {"HOME": str(self.root), "HYBRID_WRITING_PLANS_TELEMETRY": str(target)}):
            self.assertEqual(hp_telemetry.telemetry_path(), target)

    def test_record_appends_json_lines_and_load_reads_them(self):
        path = self.root / "deep" / "dir" / "lanes.jsonl"
        with mock.patch.dict(os.environ, {"HOME": str(self.root), "HYBRID_WRITING_PLANS_TELEMETRY": str(path)}):
            hp_telemetry.record({"kind": "group", "gid": "O01"})
            hp_telemetry.record({"kind": "review", "task": "T01", "t": "2026-09-28T00:00:00Z"})
        self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 2)
        recs = hp_telemetry.load_records(path)
        self.assertEqual([r["kind"] for r in recs], ["group", "review"])
        self.assertEqual(recs[0]["gid"], "O01")
        self.assertRegex(recs[0]["t"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertEqual(recs[1]["t"], "2026-09-28T00:00:00Z")

    def test_record_does_not_mutate_its_argument(self):
        path = self.root / "lanes.jsonl"
        rec = {"kind": "group"}
        with mock.patch.dict(os.environ, {"HOME": str(self.root), "HYBRID_WRITING_PLANS_TELEMETRY": str(path)}):
            hp_telemetry.record(rec)
        self.assertEqual(rec, {"kind": "group"})

    def test_record_swallows_write_failures(self):
        blocker = self.root / "blocker"
        blocker.write_text("not a directory", encoding="utf-8")
        target = blocker / "sub" / "lanes.jsonl"
        with mock.patch.dict(os.environ, {"HOME": str(self.root), "HYBRID_WRITING_PLANS_TELEMETRY": str(target)}):
            hp_telemetry.record({"kind": "group"})
            hp_telemetry.record({"kind": "group", "bad": object()})
        self.assertFalse(target.exists())

    def test_load_skips_bad_lines_and_missing_file(self):
        path = self.root / "lanes.jsonl"
        path.write_text('{"kind": "group"}\nnot json\n[1, 2]\n\n{"kind": "review"}\n', encoding="utf-8")
        self.assertEqual([r["kind"] for r in hp_telemetry.load_records(path)], ["group", "review"])
        self.assertEqual(hp_telemetry.load_records(self.root / "missing.jsonl"), [])


class FileShaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_sha256_hex_of_file_bytes(self):
        path = self.root / "T01.md"
        path.write_bytes(b"abc")
        self.assertEqual(hp_telemetry.file_sha(str(path)), hashlib.sha256(b"abc").hexdigest())

    def test_changes_when_content_changes(self):
        path = self.root / "T01.md"
        path.write_bytes(b"one")
        before = hp_telemetry.file_sha(str(path))
        path.write_bytes(b"two")
        self.assertNotEqual(before, hp_telemetry.file_sha(str(path)))

    def test_missing_file_is_empty_string(self):
        self.assertEqual(hp_telemetry.file_sha(str(self.root / "missing.md")), "")


def _group(repo, gid, tier, tasks, rounds, round1_ok, outcome, reason, duration, tin, tout, treason):
    return {"t": "2026-09-28T00:00:00Z", "kind": "group", "repo": repo, "plan": repo + "/plan.md",
            "gid": gid, "tier": tier, "model": "m", "variant": "high", "tasks": tasks, "rounds": rounds,
            "round1_ok": round1_ok, "outcome": outcome, "reason": reason, "duration_s": duration,
            "tokens": {"input": tin, "output": tout, "reasoning": treason, "cache_read": 0, "cache_write": 0}}


def _review(repo, task, tier, fixed):
    return {"t": "2026-09-28T00:00:00Z", "kind": "review", "repo": repo, "plan": repo + "/plan.md",
            "task": task, "tier": tier, "fixed_by_review": fixed}


RECORDS = [
    _group("/r1", "O01", "lite", ["T01", "T02"], 1, 2, "ok", "", 10.0, 100, 20, 5),
    _group("/r1", "O02", "lite", ["T03"], 3, 0, "fallback", "lint", 30.0, 200, 40, 5),
    _group("/r2", "O01", "std", ["T04", "T05"], 2, 1, "partial", "format", 20.0, 50, 10, 0),
    _review("/r1", "T01", "lite", True),
    _review("/r1", "T02", "lite", False),
    _review("/r2", "T04", "std", False),
    {"kind": "other", "repo": "/r1", "tier": "lite"},
]

LITE_LINE = ("tier=lite groups=2 tasks=3 round1_pass=67% (2/3) mean_rounds=2.0 fallback=50% (1/2) "
             "reasons=lint:1 review_fix=50% (1/2) median_s=20.0 tokens=in:300 out:60 reasoning:10")
STD_LINE = ("tier=std groups=1 tasks=2 round1_pass=50% (1/2) mean_rounds=2.0 fallback=100% (1/1) "
            "reasons=format:1 review_fix=0% (0/1) median_s=20.0 tokens=in:50 out:10 reasoning:0")


class StatsLinesTest(unittest.TestCase):
    def test_all_repos_per_tier(self):
        self.assertEqual(hp_telemetry.stats_lines(RECORDS),
                         ["telemetry: 3 groups, 3 reviewed tasks", LITE_LINE, STD_LINE])

    def test_repo_filter_normalises_trailing_slash(self):
        self.assertEqual(hp_telemetry.stats_lines(RECORDS, "/r1/"),
                         ["telemetry: 2 groups, 2 reviewed tasks for repo /r1", LITE_LINE])

    def test_tier_with_reviews_only(self):
        lines = hp_telemetry.stats_lines([_review("/r3", "T09", "lite", True)])
        self.assertEqual(lines, [
            "telemetry: 0 groups, 1 reviewed tasks",
            "tier=lite groups=0 tasks=0 round1_pass=- mean_rounds=- fallback=- reasons=- "
            "review_fix=100% (1/1) median_s=- tokens=in:0 out:0 reasoning:0",
        ])

    def test_no_records(self):
        self.assertEqual(hp_telemetry.stats_lines([]), ["telemetry: no records"])
        self.assertEqual(hp_telemetry.stats_lines(RECORDS, "/nowhere"),
                         ["telemetry: no records for repo /nowhere"])
