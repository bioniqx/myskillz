import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import audit  # noqa: E402
from test_plan_cli import CliBase, doctor_ok  # noqa: E402


class StubConfig(object):
    def __init__(self, models):
        self.models = models

    def model(self, role):
        return self.models[role]


C = StubConfig({"investigator": "haiku", "verifier": "sonnet", "parser": "haiku"})


class BackendsLineTest(unittest.TestCase):
    def test_no_opencode_rows_gives_empty_line(self):
        findings = [{"id": "R1", "status": "MATCHED"}, {"id": "R2", "status": "MISSING", "backend": "claude"}]
        verdicts = [{"id": "R1", "verified_status": "MATCHED"}]
        self.assertEqual(audit.backends_line(C, findings, verdicts), "")

    def test_mixed_investigators_and_claude_verifiers(self):
        findings = [
            {"id": "R1", "status": "MATCHED", "backend": "oc:std"},
            {"id": "R2", "status": "MATCHED", "backend": "oc:std"},
            {"id": "R3", "status": "MISSING"},
        ]
        verdicts = [{"id": "R1", "verified_status": "MATCHED", "backend": "claude"}]
        self.assertEqual(
            audit.backends_line(C, findings, verdicts),
            "- Backends: investigators oc:std (2 items) + claude haiku (1 items); "
            "verifiers claude sonnet (1 items)",
        )

    def test_opencode_verifier_only_triggers_line(self):
        findings = [{"id": "R1", "status": "MATCHED"}]
        verdicts = [{"id": "R1", "verified_status": "PARTIAL", "backend": "oc:std"}]
        self.assertEqual(
            audit.backends_line(C, findings, verdicts),
            "- Backends: investigators claude haiku (1 items); verifiers oc:std (1 items)",
        )

    def test_no_verdicts_shows_none(self):
        findings = [{"id": "R1", "status": "MATCHED", "backend": "oc:lite"}]
        self.assertEqual(
            audit.backends_line(C, findings, []),
            "- Backends: investigators oc:lite (1 items); verifiers none",
        )


class ItemRecordsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("HYBRID_AUDIT_TELEMETRY")
        self.tele = str(Path(self.tmp.name) / "lanes.jsonl")
        os.environ["HYBRID_AUDIT_TELEMETRY"] = self.tele

    def tearDown(self):
        if self.old is None:
            os.environ.pop("HYBRID_AUDIT_TELEMETRY", None)
        else:
            os.environ["HYBRID_AUDIT_TELEMETRY"] = self.old
        self.tmp.cleanup()

    def build(self):
        findings = {
            "R1": {"id": "R1", "status": "MATCHED", "backend": "oc:std"},
            "R2": {"id": "R2", "status": "MISSING"},
            "R3": {"id": "R3", "status": "PARTIAL", "backend": "claude"},
        }
        verdicts = {"R1": {"id": "R1", "verified_status": "PARTIAL"}}
        adjudications = {"R2": "MATCHED", "R3": "PARTIAL"}
        finals = {"R1": "PARTIAL", "R2": "MATCHED", "R3": "PARTIAL"}
        return audit.item_records("/repo", ["R1", "R2", "R3"], findings, verdicts, adjudications, finals, 100.0)

    def test_item_records_fields(self):
        recs = self.build()
        self.assertEqual(len(recs), 3)
        r1, r2, r3 = recs
        self.assertEqual(r1, {
            "t": 100.0, "kind": "item", "repo": "/repo", "id": "R1", "backend": "oc:std",
            "inv": "MATCHED", "ver": "PARTIAL", "final": "PARTIAL",
            "verifier_overturned": True, "lead_overturned": False,
        })
        self.assertEqual(r2["backend"], "claude")
        self.assertIsNone(r2["ver"])
        self.assertFalse(r2["verifier_overturned"])
        self.assertTrue(r2["lead_overturned"])
        self.assertEqual(r3["backend"], "claude")
        self.assertFalse(r3["lead_overturned"])

    def test_missing_finding_row_is_claude_unsearched(self):
        recs = audit.item_records("/repo", ["R9"], {}, {}, {}, {"R9": "UNSEARCHED"}, 5.0)
        self.assertEqual(recs[0]["backend"], "claude")
        self.assertEqual(recs[0]["inv"], "UNSEARCHED")
        self.assertEqual(recs[0]["final"], "UNSEARCHED")

    def test_emit_appends_one_line_per_record(self):
        audit.emit_item_telemetry(self.build())
        lines = Path(self.tele).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual([json.loads(x)["id"] for x in lines], ["R1", "R2", "R3"])
        self.assertTrue(all(json.loads(x)["kind"] == "item" for x in lines))

    def test_emit_swallows_write_failure(self):
        blocker = Path(self.tmp.name) / "blocker"
        blocker.write_text("a file, not a directory", encoding="utf-8")
        os.environ["HYBRID_AUDIT_TELEMETRY"] = str(blocker / "lanes.jsonl")
        audit.emit_item_telemetry(self.build())
        self.assertFalse(Path(self.tele).exists())


class ReportBackendsCliTest(CliBase):
    def report_lines(self, preset):
        if preset != "claude":
            self.write_json_file(self.cache, doctor_ok())
        self.init(preset)
        self.write_checklist(4)
        r = self.cli("plan", "--cap", "3")
        self.assertEqual(r.returncode, 0, r.stdout)
        for name, b in self.state()["batches"].items():
            (self.out / "findings" / ("%s.jsonl" % name)).write_text("".join(json.dumps(
                {"id": i, "status": "MATCHED", "confidence": "high", "backend": b["backend"],
                 "evidence": [{"path": "src/app.py", "lines": "1-2"}]}) + "\n" for i in b["ids"]), encoding="utf-8")
        r = self.cli("report")
        self.assertEqual(r.returncode, 0, r.stdout)
        return (self.out / "requirements-code-audit.md").read_text(encoding="utf-8").splitlines()

    def test_backends_line_sits_between_date_and_constraints(self):
        lines = self.report_lines("hybrid")
        i = [k for k, line in enumerate(lines) if line.startswith("- Backends:")]
        self.assertEqual(len(i), 1, "\n".join(lines))
        self.assertIn("investigators oc:std (", lines[i[0]])
        self.assertTrue(lines[i[0] - 1].startswith("- %s: " % audit.HEADINGS["en"]["date"]))
        self.assertEqual(lines[i[0] + 1], "- %s" % audit.HEADINGS["en"]["constraints"])

    def test_claude_preset_report_has_no_backends_line(self):
        lines = self.report_lines("claude")
        self.assertFalse([line for line in lines if "Backends" in line])
        k = [n for n, line in enumerate(lines) if line.startswith("- %s: " % audit.HEADINGS["en"]["date"])][0]
        self.assertEqual(lines[k + 1], "- %s" % audit.HEADINGS["en"]["constraints"])


class AbortGateCliTest(CliBase):
    def test_abort_disarms_and_later_finish_emits_no_telemetry(self):
        self.init("claude")
        self.write_checklist(3)
        self.assertTrue((self.out / audit.ACTIVE).exists())
        r = self.cli("abort")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("Audit closed (guard hooks disarmed).", r.stdout)
        self.assertFalse((self.out / audit.ACTIVE).exists())
        self.assertFalse(self.config()["active"])
        self.assertTrue(self.config()["finished"])
        r = self.cli("finish")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("HEADLINE: Total requirements 3", r.stdout)
        recs = self.telemetry.read_text(encoding="utf-8").splitlines() if self.telemetry.exists() else []
        self.assertEqual([x for x in recs if json.loads(x).get("kind") == "item"], [])


if __name__ == "__main__":
    unittest.main()
