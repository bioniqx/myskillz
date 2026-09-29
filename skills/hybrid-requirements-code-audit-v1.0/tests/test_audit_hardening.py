import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "scripts"))

import audit  # noqa: E402
import ha_run  # noqa: E402
from test_plan_cli import CliBase, doctor_ok  # noqa: E402


class PlanResetsFallbacksTest(CliBase):
    def planned(self, preset):
        if preset != "claude":
            self.write_json_file(self.cache, doctor_ok())
        self.write_json_file(self.routing, {"tiers": {"std": {"max_parallel": 2}}, "oc_batch_max": 2})
        self.init(preset)
        self.write_checklist(10)
        st = self.state()
        st["fallbacks"] = {"batch-04": "format", "batch-05": "crash"}
        self.write_json_file(self.out / "state.json", st)
        r = self.cli("plan", "--cap", "3")
        self.assertEqual(r.returncode, 0, r.stdout)
        return self.state()

    def test_claude_plan_resets_fallbacks(self):
        self.assertEqual(self.planned("claude")["fallbacks"], {})

    def test_hybrid_plan_resets_fallbacks(self):
        st = self.planned("hybrid")
        self.assertEqual(st["batches"]["batch-04"]["backend"], "oc:std")
        self.assertEqual(st["fallbacks"], {})


class WriteJsonAtomicTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "sub"
        self.path = self.dir / "state.json"
        self.obj = {"a": 1, "b": ["é", {"c": None}]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_bytes_as_before(self):
        audit.write_json(self.path, self.obj)
        self.assertEqual(self.path.read_bytes(),
                         json.dumps(self.obj, ensure_ascii=False, indent=1).encode("utf-8"))
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["state.json"])

    def test_uses_ha_run_atomic_write_in_target_dir(self):
        with mock.patch.object(ha_run, "atomic_write", wraps=ha_run.atomic_write) as aw, \
                mock.patch("tempfile.mkstemp", wraps=tempfile.mkstemp) as mk, \
                mock.patch("os.replace", wraps=os.replace) as rep:
            audit.write_json(self.path, self.obj)
        self.assertEqual(aw.call_count, 1)
        self.assertEqual(mk.call_count, 1)
        self.assertEqual(Path(mk.call_args[1]["dir"]).resolve(), self.dir.resolve())
        self.assertEqual(rep.call_count, 1)
        self.assertEqual(Path(rep.call_args[0][1]).resolve(), self.path.resolve())

    def test_failure_removes_temp_and_keeps_old_file(self):
        audit.write_json(self.path, {"old": True})
        with mock.patch("os.replace", side_effect=OSError("boom")):
            with self.assertRaises(OSError):
                audit.write_json(self.path, self.obj)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"old": True})
        self.assertEqual(sorted(p.name for p in self.dir.iterdir()), ["state.json"])

    def test_file_mode_follows_umask(self):
        audit.write_json(self.path, self.obj)
        umask = os.umask(0)
        os.umask(umask)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o666 & ~umask)


class MinorFixesCliTest(CliBase):
    def test_status_keeps_parse_merge_after_every_section_fell_back(self):
        self.write_json_file(self.cache, doctor_ok())
        self.init("max")
        r = self.cli("parse-plan", "--sections", "2")
        self.assertEqual(r.returncode, 0, r.stdout)
        backends = self.state()["parse"]["backends"]
        self.assertEqual(set(backends.values()), {"oc:std"})
        for name in backends:
            self.write_json_file(self.out / "events" / (name + ".json"), {"batch": name, "ok": False, "reason": "crash"})
        r = self.cli("parse-merge")
        self.assertIn("FALLBACK section-01 (crash) → Claude parser", r.stdout)
        self.assertEqual(set(self.state()["parse"]["backends"].values()), {"claude"})
        r = self.cli("status")
        self.assertIn("NEXT: once every parser section has finished, `audit.py parse-merge`", r.stdout)
        self.assertNotIn("parse-plan", r.stdout)

    def test_claude_status_after_parse_plan_is_unchanged(self):
        self.init("claude")
        self.cli("parse-plan", "--sections", "2")
        r = self.cli("status")
        self.assertEqual(r.stdout.splitlines()[-1],
                         "NEXT: write %s (see SKILL.md Step 1), then `audit.py plan`." % (self.out / "checklist.jsonl"))

    def test_solo_init_prints_what_preset_claude_prints(self):
        self.write_json_file(self.cache, doctor_ok())
        base = ["init", "--spec", str(self.spec), "--cap", "3"]
        solo = self.cli(*(base + ["--agents", "solo", "--preset", "hybrid"]))
        self.assertEqual(solo.returncode, 0, solo.stdout)
        self.assertEqual(self.config()["preset"], "claude")
        claude = self.cli(*(base + ["--preset", "claude", "--force"]))
        self.assertEqual(claude.returncode, 0, claude.stdout)
        self.assertEqual(self.opencode_line(solo.stdout.splitlines()),
                         self.opencode_line(claude.stdout.splitlines()))
        self.assertIn("preset=claude investigator=claude", self.opencode_line(solo.stdout.splitlines()))

    def test_all_opencode_plan_has_no_claude_batch_size(self):
        self.write_json_file(self.cache, doctor_ok())
        self.init()
        self.write_checklist(4)
        r = self.cli("plan", "--cap", "3")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout.splitlines()[0], "plan: 4 requirements (0 skipped as static-limit/ambiguous) → 0"
                                                   " investigator batches, 1 wave(s), cap=3 | 4 opencode batches (4 items)")


class FinishTelemetryOnceTest(CliBase):
    def items(self):
        if not self.telemetry.exists():
            return []
        recs = [json.loads(x) for x in self.telemetry.read_text(encoding="utf-8").splitlines() if x.strip()]
        return [r for r in recs if r.get("kind") == "item"]

    def closed(self, cmd):
        self.init("claude")
        self.write_checklist(3)
        r = self.cli(cmd)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_second_finish_adds_no_records(self):
        self.closed("finish")
        first = len(self.items())
        self.assertEqual(first, 3)
        r = self.cli("finish")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(len(self.items()), first)

    def test_abort_emits_none(self):
        self.closed("abort")
        self.assertEqual(self.items(), [])

    def test_finish_after_abort_emits_none(self):
        self.closed("abort")
        r = self.cli("finish")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(self.items(), [])


class UnsearchedVerdictTest(unittest.TestCase):
    def rec(self, verdict, adj=None):
        findings = {"R1": {"id": "R1", "status": "MISSING"}}
        adjs = {"R1": adj} if adj else {}
        return audit.item_records("/repo", ["R1"], findings, {"R1": verdict}, adjs, {"R1": adj or "MISSING"}, 1.0)[0]

    def test_unsearched_verdict_is_no_verdict(self):
        r = self.rec({"id": "R1", "verified_status": "UNSEARCHED"})
        self.assertIsNone(r["ver"])
        self.assertFalse(r["verifier_overturned"])
        self.assertFalse(r["lead_overturned"])

    def test_status_normalizing_to_unsearched_is_no_verdict(self):
        r = self.rec({"id": "R1", "status": "skipped"})
        self.assertIsNone(r["ver"])
        self.assertFalse(r["verifier_overturned"])

    def test_lead_overturn_compares_against_inv(self):
        self.assertFalse(self.rec({"id": "R1", "verified_status": "UNSEARCHED"}, adj="MISSING")["lead_overturned"])
        self.assertTrue(self.rec({"id": "R1", "verified_status": "UNSEARCHED"}, adj="MATCHED")["lead_overturned"])


if __name__ == "__main__":
    unittest.main()
