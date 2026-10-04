import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "oc-requirements-code-audit", "scripts"))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(1, SCRIPTS)

import oc_audit as audit  # noqa: E402


def item(rid, **kw):
    row = {"id": rid, "text": "Requirement %s" % rid, "strength": "MUST", "stakes": "normal",
           "search_hints": ["login", "session"], "tags": []}
    row.update(kw)
    return row


def put(path, rows):
    d = os.path.dirname(path)
    if not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + u"\n")


class PortBase(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo, "src"))
        with io.open(os.path.join(self.repo, "src", "app.py"), "w", encoding="utf-8") as fh:
            fh.write(u"".join(u"line_%d = %d\n" % (i, i) for i in range(1, 11)))
        self.out = os.path.join(self.tmp, "audit")
        os.makedirs(self.out)
        cfg = {"version": audit.VERSION, "active": True, "repo_root": self.repo,
               "out_dir": self.out, "spec_files": [], "lang": "en", "threads": 8,
               "retrieval": "python"}
        put(os.path.join(self.out, "config.json"), [cfg])
        with io.open(os.path.join(self.out, "config.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(cfg))
        with io.open(os.path.join(self.out, "index.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"files": ["src/app.py"], "symbols": {}, "routes": {},
                                 "lines": {"src/app.py": 10}}))
        with io.open(os.path.join(self.out, "repo-map.txt"), "w", encoding="utf-8") as fh:
            fh.write(u"files=1\n")

    def rows(self, name, rows):
        put(os.path.join(self.out, name), rows)

    def run_cmd(self, *argv):
        buf, err = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            try:
                audit.main(["--out", self.out] + list(argv))
            except SystemExit as e:
                code = e.code
        return code, buf.getvalue()


EV = [{"path": "src/app.py", "lines": "1-3", "note": "n"}]


class FinalAndEvidenceTest(PortBase):
    def test_adjudication_beats_the_tag(self):
        self.rows("checklist.jsonl", [item("REQ-001", tags=["static-limit"])])
        self.rows("adjudications.jsonl", [{"id": "REQ-001", "final_status": "PARTIAL"}])
        m = audit.Merged(audit.Ctx(self.out))
        self.assertEqual(m.final("REQ-001"), ("PARTIAL", "lead"))

    def test_evidence_comes_from_the_deciding_pass(self):
        self.rows("checklist.jsonl", [item("REQ-001")])
        self.rows("findings/batch-01.jsonl", [
            {"id": "REQ-001", "status": "PARTIAL", "confidence": "high", "evidence": EV, "searched": ["x"]}])
        self.rows("verify/batch-V01.jsonl", [
            {"id": "REQ-001", "verified_status": "MISSING", "agree": False, "confidence": "high",
             "evidence": [], "searched": ["y"]}])
        m = audit.Merged(audit.Ctx(self.out))
        self.assertEqual(m.final("REQ-001")[0], "MISSING")
        self.assertEqual(m.evidence("REQ-001"), [])


class QueueTest(PortBase):
    def test_untagged_unverifiable_is_queued_and_agreed_missing_is_not(self):
        self.rows("checklist.jsonl", [item("REQ-001"), item("REQ-002")])
        self.rows("findings/batch-01.jsonl", [
            {"id": "REQ-001", "status": "UNVERIFIABLE", "confidence": "high", "evidence": []},
            {"id": "REQ-002", "status": "MISSING", "confidence": "high", "evidence": [], "searched": ["a"]}])
        self.rows("verify/batch-V01.jsonl", [
            {"id": "REQ-002", "verified_status": "MISSING", "agree": True, "confidence": "high",
             "evidence": [], "searched": ["b"]}])
        _code, text = self.run_cmd("queue")
        self.assertIn("worker says UNVERIFIABLE (not tagged by lead)", text)
        self.assertNotIn("REQ-002  MISSING", text)

    def test_spot_sample_is_seeded_and_stable_after_adjudication(self):
        items = [item("REQ-%03d" % i) for i in range(1, 41)]
        self.rows("checklist.jsonl", items)
        self.rows("findings/batch-01.jsonl", [
            {"id": r["id"], "status": "MATCHED", "confidence": "high", "evidence": EV} for r in items])
        m = audit.Merged(audit.Ctx(self.out))
        first = audit.spot_sample(m)
        self.assertEqual(len(first), 3)
        self.assertEqual(first, audit.spot_sample(m))
        self.rows("adjudications.jsonl", [{"id": first[0], "final_status": "MATCHED"}])
        self.assertEqual(first, audit.spot_sample(audit.Merged(audit.Ctx(self.out))))


class CheckGateTest(PortBase):
    def check(self, items, findings, verdicts=None, plan=None):
        self.rows("checklist.jsonl", items)
        self.rows("findings/batch-01.jsonl", findings)
        if verdicts:
            self.rows("verify/batch-V01.jsonl", verdicts)
        self.rows("plan.jsonl", plan or [])
        return self.run_cmd("check")

    def test_partial_never_verified_fails(self):
        code, text = self.check([item("REQ-001")], [
            {"id": "REQ-001", "status": "PARTIAL", "confidence": "high", "evidence": EV}])
        self.assertEqual(code, 2)
        self.assertIn("never verified or adjudicated", text)

    def test_disagreement_fails(self):
        code, text = self.check([item("REQ-001")], [
            {"id": "REQ-001", "status": "MATCHED", "confidence": "low", "evidence": EV}], [
            {"id": "REQ-001", "verified_status": "PARTIAL", "agree": False, "confidence": "high",
             "evidence": EV}])
        self.assertIn("disagree -- adjudicate", text)

    def test_missing_without_searched_fails(self):
        code, text = self.check([item("REQ-001")], [
            {"id": "REQ-001", "status": "MISSING", "confidence": "low", "evidence": []}], [
            {"id": "REQ-001", "verified_status": "MISSING", "agree": True, "confidence": "high",
             "evidence": []}], [{"ids": ["REQ-001"], "title": "t", "priority": "P1", "effort": "S",
                                 "target": "x"}])
        self.assertIn("MISSING without any `searched`", text)

    def test_unverified_high_stakes_match_warns_and_plan_warnings(self):
        code, text = self.check([item("REQ-001", stakes="high"),
                                 item("REQ-002", strength="MAY")], [
            {"id": "REQ-001", "status": "MATCHED", "confidence": "high", "evidence": EV},
            {"id": "REQ-002", "status": "PARTIAL", "confidence": "high", "evidence": EV}], [
            {"id": "REQ-002", "verified_status": "PARTIAL", "agree": True, "confidence": "high",
             "evidence": EV}], [{"ids": ["REQ-002"], "title": "t", "priority": "P0", "effort": "X",
                                 "target": "x"}])
        self.assertIn("MATCHED with low confidence or high stakes but never verified", text)
        self.assertIn("MAY requirement at P0", text)
        self.assertIn("effort should be S/M/L", text)


class PlanStatusTest(PortBase):
    def test_replan_clears_stale_artifacts(self):
        self.rows("checklist.jsonl", [item("REQ-001")])
        self.rows("findings/batch-09.jsonl", [{"id": "REQ-001", "status": "MATCHED"}])
        self.rows("verify/batch-V01.jsonl", [{"id": "REQ-001", "verified_status": "MATCHED"}])
        self.rows("state.json", [])
        with io.open(os.path.join(self.out, "state.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"vbatches": {"batch-V01": {"ids": ["REQ-001"]}}}))
        self.run_cmd("plan")
        self.assertFalse(os.path.exists(os.path.join(self.out, "findings", "batch-09.jsonl")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "verify", "batch-V01.jsonl")))
        self.assertNotIn("vbatches", audit.Ctx(self.out).state())

    def test_failed_lane_ids_reach_the_verifier_wave(self):
        self.rows("checklist.jsonl", [item("REQ-001"), item("REQ-002")])
        self.rows("findings/batch-01.jsonl", [
            {"id": "REQ-001", "status": "MATCHED", "confidence": "high", "evidence": EV}])
        with io.open(os.path.join(self.out, "state.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"batches": {"batch-01": {"ids": ["REQ-001", "REQ-002"],
                                                           "wave": "A", "dispatched": 1.0}}}))
        _code, text = self.run_cmd("status", "--failed", "batch-01")
        self.assertIn("batch-V01", text)
        with io.open(os.path.join(self.out, "batches", "batch-V01.md"), encoding="utf-8") as fh:
            brief = fh.read()
        self.assertIn("REQ-002", brief)
        self.assertIn("UNSEARCHED", brief)
        self.assertIn("about 10 tool calls", brief)

    def test_undispatch_prints_the_row_again(self):
        self.rows("checklist.jsonl", [item("REQ-001")])
        with io.open(os.path.join(self.out, "state.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"batches": {"batch-01": {"ids": ["REQ-001"], "wave": "A",
                                                           "dispatched": 1.0}}}))
        _code, text = self.run_cmd("status", "--undispatch", "batch-01")
        self.assertIn("DISPATCH again", text)
        self.assertIn("rca batch-01", text)


class ParseFailureTest(PortBase):
    def test_unparseable_output_is_moved_aside_and_dispatched_again(self):
        spec = u"# Spec\n\n" + (u"The system must log every event. " * 120) + u"\n"
        os.makedirs(os.path.join(self.out, "spec"))
        with io.open(os.path.join(self.out, "spec", "spec.txt"), "w", encoding="utf-8") as fh:
            fh.write(spec)
        self.run_cmd("parse")
        out1 = os.path.join(self.out, "parse", "parse-01.jsonl")
        with io.open(out1, "w", encoding="utf-8") as fh:
            fh.write(u'{"id": "S01-001", "text"\n')
        _code, text = self.run_cmd("parse")
        self.assertIn("FAIL  parse-01", text)
        self.assertTrue(os.path.exists(out1 + ".bad"))
        self.assertIn("rca parse-01", text)


if __name__ == "__main__":
    unittest.main()
