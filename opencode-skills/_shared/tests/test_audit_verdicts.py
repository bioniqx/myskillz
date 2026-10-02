import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from argparse import Namespace

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "oc-requirements-code-audit", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import oc_audit as audit  # noqa: E402


def _repo():
    d = tempfile.mkdtemp(prefix="audit-verdicts-")
    os.makedirs(os.path.join(d, "src"))
    with io.open(os.path.join(d, "src", "app.py"), "w", encoding="utf-8") as fh:
        fh.write(u"".join(u"line_%d = %d\n" % (i, i) for i in range(1, 11)))
    return d


ITEM = {"id": "REQ-001", "text": "Users can log in", "strength": "MUST",
        "stakes": "normal", "search_hints": ["login", "session"]}
GOOD_MATCH = {"status": "MATCHED", "confidence": "high",
              "evidence": [{"path": "src/app.py", "lines": "1-3", "note": "login"}],
              "notes": "found"}
REJECTED = {"id": "REQ-001", "verified_status": "MISSING", "confidence": "high",
            "evidence": [], "reason": "nothing", "lint_error": ["evidence path x does not exist"]}
ACCEPTED = {"id": "REQ-001", "verified_status": "MATCHED", "agree": True, "confidence": "high",
            "evidence": [{"path": "src/app.py", "lines": "2-4", "note": "login"}],
            "reason": "login at app.py"}


def _audit_dir(repo, verdict, cfg=None, state=None):
    out = tempfile.mkdtemp(prefix="audit-out-")
    with io.open(os.path.join(out, "config.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(dict({"repo_root": repo}, **(cfg or {}))))
    finding = dict(GOOD_MATCH, id="REQ-001", confidence="medium")
    for name, row in (("checklist.jsonl", ITEM), ("findings.jsonl", finding),
                      ("verdicts.jsonl", verdict)):
        with io.open(os.path.join(out, name), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + u"\n")
    if state is not None:
        with io.open(os.path.join(out, "state.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(state))
    return out


def _check(out):
    buf = io.StringIO()
    code = None
    with contextlib.redirect_stdout(buf):
        try:
            audit.cmd_check(Namespace(out=out))
        except SystemExit as e:
            code = e.code
    return code, buf.getvalue()


class MergedRejectedTest(unittest.TestCase):
    def test_rejected_verdict_row_falls_back_to_the_finding(self):
        repo = _repo()
        self.addCleanup(shutil.rmtree, repo, True)
        out = _audit_dir(repo, REJECTED)
        self.addCleanup(shutil.rmtree, out, True)
        m = audit.Merged(audit.Ctx(out))
        self.assertEqual(m.final("REQ-001"), ("MATCHED", "investigator"))
        self.assertNotIn("REQ-001", m.ver)
        self.assertIn("REQ-001", m.ver_rejected)
        self.assertEqual(m.evidence("REQ-001")[0]["path"], "src/app.py")


class CheckGateRejectedTest(unittest.TestCase):
    def test_gate_fails_on_an_unadjudicated_rejected_verdict(self):
        repo = _repo()
        self.addCleanup(shutil.rmtree, repo, True)
        out = _audit_dir(repo, REJECTED)
        self.addCleanup(shutil.rmtree, out, True)
        code, text = _check(out)
        self.assertIn("rejected the verifier's answer", text)
        self.assertIn("GATE: FAIL", text)
        self.assertEqual(code, 2)


class CheckGateSingleLaneTest(unittest.TestCase):
    def test_old_api_lane_config_gets_no_api_only_warning(self):
        repo = _repo()
        self.addCleanup(shutil.rmtree, repo, True)
        out = _audit_dir(repo, ACCEPTED, cfg={"lane": "api", "tier": "std"},
                         state={"run": {"wave_b": 0}})
        self.addCleanup(shutil.rmtree, out, True)
        code, text = _check(out)
        self.assertIsNone(code)
        self.assertNotIn("no second pass ran", text)
        self.assertIn("GATE: PASS", text)


class ReportMethodTest(unittest.TestCase):
    def test_method_line_names_opencode_lanes_and_no_model(self):
        repo = _repo()
        self.addCleanup(shutil.rmtree, repo, True)
        out = _audit_dir(repo, ACCEPTED, cfg={"retrieval": "python"})
        self.addCleanup(shutil.rmtree, out, True)
        with contextlib.redirect_stdout(io.StringIO()):
            audit.cmd_report(Namespace(out=out, lang=None, headings=None))
        with io.open(os.path.join(out, "requirements-code-audit.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("OpenCode lanes, deterministic retrieval (python), "
                      "adversarial second pass on 1 item(s)", text)
        self.assertNotIn("api lane", text)


LANE_ITEM = {"text": "Users can log in", "strength": "MUST", "stakes": "normal",
             "search_hints": ["login", "session"]}
LANE_GOOD = {"id": "REQ-001", "status": "MATCHED", "confidence": "high",
             "evidence": [{"path": "src/app.py", "lines": "1-3", "note": "login"}],
             "notes": "found"}
LANE_BAD = {"id": "REQ-002", "status": "MATCHED", "confidence": "high",
            "evidence": [{"path": "src/ghost.py", "lines": "1-3", "note": "invented"}],
            "notes": "made up"}
PHANTOM = dict(LANE_BAD, evidence=[{"path": "src/phantom.py", "lines": "1-2"}])


def _lane_audit(rows=None):
    """A temp repo with an audit dir inside it, shaped like a finished investigator wave."""
    repo = tempfile.mkdtemp(prefix="audit-lane-")
    os.makedirs(os.path.join(repo, "src"))
    with io.open(os.path.join(repo, "src", "app.py"), "w", encoding="utf-8") as fh:
        fh.write(u"".join(u"line_%d = %d\n" % (i, i) for i in range(1, 11)))
    out = os.path.join(repo, ".oc-audit")
    os.makedirs(os.path.join(out, "findings"))
    with io.open(os.path.join(out, "config.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"repo_root": repo}))
    audit.write_jsonl(os.path.join(out, "checklist.jsonl"),
                      [dict(LANE_ITEM, id="REQ-001"), dict(LANE_ITEM, id="REQ-002")])
    audit.write_jsonl(os.path.join(out, "findings", "batch-01.jsonl"),
                      rows if rows is not None else [LANE_GOOD, LANE_BAD])
    return repo, out


def _rows_by_id(path):
    rows, _bad = audit.read_jsonl(path)
    return dict((r["id"], r) for r in rows)


def _read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


def _answer(out, name, rows):
    """Play a repair lane: write its rows where its brief told it to."""
    audit.write_jsonl(os.path.join(out, "findings", name + ".jsonl"), rows)


class LaneLintTest(unittest.TestCase):
    def setUp(self):
        self.repo, self.out = _lane_audit()
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.batch = os.path.join(self.out, "findings", "batch-01.jsonl")

    def test_invented_citation_is_rejected_and_unsettled(self):
        rejected = audit.lint_lane_dir(self.out, "findings", self.repo)
        self.assertEqual([r["id"] for r in rejected], ["REQ-002"])
        self.assertIn("does not exist", rejected[0]["lint_error"][0])
        rows = _rows_by_id(self.batch)
        self.assertEqual(rows["REQ-001"]["status"], "MATCHED")
        self.assertEqual(rows["REQ-001"]["confidence"], "high")
        self.assertNotIn("lint_error", rows["REQ-001"])
        self.assertEqual(rows["REQ-002"]["status"], "UNSEARCHED")
        self.assertEqual(rows["REQ-002"]["rejected_status"], "MATCHED")
        self.assertEqual(rows["REQ-002"]["evidence"], [])

    def test_second_lint_reports_nothing_new_and_keeps_the_rejection(self):
        audit.lint_lane_dir(self.out, "findings", self.repo)
        self.assertEqual(audit.lint_lane_dir(self.out, "findings", self.repo), [])
        rows = _rows_by_id(self.batch)
        self.assertTrue(rows["REQ-002"]["lint_error"])
        self.assertEqual(rows["REQ-002"]["status"], "UNSEARCHED")

    def test_missing_directory_is_an_empty_lint(self):
        self.assertEqual(audit.lint_lane_dir(self.out, "verify", self.repo, kind="verdict"), [])

    def test_unparseable_line_is_kept_verbatim(self):
        with io.open(self.batch, "a", encoding="utf-8") as fh:
            fh.write(u'{"id": "REQ-003", "status"\n')
        rejected = audit.lint_lane_dir(self.out, "findings", self.repo)
        self.assertEqual([r["id"] for r in rejected], ["REQ-002"])
        self.assertIn(u'{"id": "REQ-003", "status"', _read(self.batch))
        self.assertEqual(_rows_by_id(self.batch)["REQ-002"]["status"], "UNSEARCHED")


class RepairWaveTest(unittest.TestCase):
    def setUp(self):
        self.repo, self.out = _lane_audit()
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.rejected = audit.lint_lane_dir(self.out, "findings", self.repo)

    def test_max_repair_rounds_is_two(self):
        self.assertEqual(audit.MAX_REPAIR_ROUNDS, 2)

    def test_brief_holds_only_the_rejected_rows(self):
        batches = audit.repair_wave(self.out, self.rejected, self.repo, 1)
        self.assertEqual(batches, [("repair-r1-01",
                                    os.path.join(self.out, "batches", "repair-r1-01.md"))])
        brief = _read(batches[0][1])
        self.assertIn("REPAIR", brief)
        self.assertIn("REQUIREMENT REQ-002 ", brief)
        self.assertIn("src/ghost.py", brief)
        self.assertNotIn("REQUIREMENT REQ-001 ", brief)
        self.assertIn(os.path.join(self.out, "findings", "repair-r1-01.jsonl"), brief)

    def test_a_later_call_in_the_same_round_takes_the_next_number(self):
        audit.repair_wave(self.out, self.rejected, self.repo, 1)
        again = audit.repair_wave(self.out, self.rejected, self.repo, 1)
        self.assertEqual([name for name, _p in again], ["repair-r1-02"])

    def test_rows_are_split_into_briefs_of_at_most_six(self):
        many = [dict(self.rejected[0], id="REQ-%03d" % i) for i in range(1, 8)]
        batches = audit.repair_wave(self.out, many, self.repo, 2)
        self.assertEqual([name for name, _p in batches], ["repair-r2-01", "repair-r2-02"])
        self.assertIn("REQUIREMENT REQ-007 ", _read(batches[1][1]))

    def test_no_brief_past_the_round_limit(self):
        self.assertEqual(audit.repair_wave(self.out, self.rejected, self.repo,
                                           audit.MAX_REPAIR_ROUNDS + 1), [])
        self.assertFalse(os.path.exists(os.path.join(self.out, "batches")))

    def test_nothing_rejected_writes_nothing(self):
        self.assertEqual(audit.repair_wave(self.out, [], self.repo, 1), [])
        self.assertFalse(os.path.exists(os.path.join(self.out, "batches")))


class JudgeLintTest(unittest.TestCase):
    def _audit(self, rows=None):
        repo, out = _lane_audit(rows)
        self.addCleanup(shutil.rmtree, repo, True)
        return out

    def _lint(self, out, redispatch=False):
        return audit.judge_lint(audit.Ctx(out), redispatch)

    def test_rejected_row_goes_to_repair_round_one(self):
        out = self._audit()
        batches, waiting = self._lint(out)
        self.assertEqual([name for name, _p in batches], ["repair-r1-01"])
        self.assertEqual(waiting, [])
        self.assertEqual(audit.Ctx(out).state()["repairs"], {"REQ-002": 1})

    def test_unanswered_repair_waits_until_redispatch(self):
        out = self._audit()
        self._lint(out)
        self.assertEqual(self._lint(out), ([], ["REQ-002"]))
        batches, waiting = self._lint(out, True)
        self.assertEqual([name for name, _p in batches], ["repair-r1-02"])
        self.assertEqual(waiting, [])

    def test_accepted_repair_settles_the_row(self):
        out = self._audit()
        self._lint(out)
        _answer(out, "repair-r1-01", [dict(LANE_GOOD, id="REQ-002")])
        self.assertEqual(self._lint(out), ([], []))
        m = audit.Merged(audit.Ctx(out))
        self.assertEqual(m.final("REQ-002"), ("MATCHED", "investigator"))
        self.assertEqual(m.evidence("REQ-002")[0]["path"], "src/app.py")

    def test_two_repair_rounds_then_the_row_goes_to_the_verifier_unsettled(self):
        out = self._audit()
        self._lint(out)
        _answer(out, "repair-r1-01", [PHANTOM])
        batches, _waiting = self._lint(out)
        self.assertEqual([name for name, _p in batches], ["repair-r2-01"])
        brief = _read(batches[0][1])
        self.assertIn("src/phantom.py", brief)
        self.assertNotIn("REQUIREMENT REQ-001 ", brief)
        _answer(out, "repair-r2-01", [PHANTOM])
        self.assertEqual(self._lint(out), ([], []))
        m = audit.Merged(audit.Ctx(out))
        self.assertEqual(m.find["REQ-002"]["status"], "UNSEARCHED")
        self.assertTrue(audit.needs_verify(m.by_id["REQ-002"], m.find["REQ-002"]))

    def test_clean_findings_send_nothing(self):
        out = self._audit([LANE_GOOD, dict(LANE_GOOD, id="REQ-002")])
        self.assertEqual(self._lint(out), ([], []))
        self.assertFalse(os.path.exists(os.path.join(out, "batches")))

    def test_verdict_files_are_linted_and_agree_is_recomputed(self):
        out = self._audit([LANE_GOOD, dict(LANE_GOOD, id="REQ-002")])
        audit.write_jsonl(os.path.join(out, "verify", "batch-V01.jsonl"), [
            {"id": "REQ-001", "verified_status": "MISSING", "agree": True, "confidence": "high",
             "evidence": [{"path": "src/ghost.py", "lines": "1-2"}], "reason": "invented"},
            {"id": "REQ-002", "verified_status": "PARTIAL", "agree": True, "confidence": "high",
             "evidence": [{"path": "src/app.py", "lines": "2-4"}], "reason": "limit missing"},
        ])
        self._lint(out)
        m = audit.Merged(audit.Ctx(out))
        self.assertIn("REQ-001", m.ver_rejected)
        self.assertNotIn("REQ-001", m.ver)
        self.assertEqual(m.final("REQ-001"), ("MATCHED", "investigator"))
        self.assertEqual(m.final("REQ-002"), ("PARTIAL", "verifier"))
        self.assertIs(m.ver["REQ-002"]["agree"], False)


class StatusRepairTest(unittest.TestCase):
    def _status(self, out):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            audit.cmd_status(Namespace(out=out, cap=None, redispatch=False))
        return buf.getvalue()

    def test_status_sends_repairs_before_any_verifier(self):
        repo, out = _lane_audit()
        self.addCleanup(shutil.rmtree, repo, True)
        text = self._status(out)
        self.assertIn("repair-r1-01", text)
        self.assertIn("NEXT after they report: oc_audit.py status", text)
        self.assertNotIn("rca-verifier", text)

    def test_rejected_verdict_is_not_waited_on(self):
        repo, out = _lane_audit([LANE_GOOD, dict(LANE_GOOD, id="REQ-002")])
        self.addCleanup(shutil.rmtree, repo, True)
        audit.write_json(os.path.join(out, "state.json"),
                         {"vbatches": {"batch-V01": {"ids": ["REQ-001"], "wave": "B"}}})
        audit.write_jsonl(os.path.join(out, "verify", "batch-V01.jsonl"), [
            {"id": "REQ-001", "verified_status": "MISSING", "agree": False, "confidence": "high",
             "evidence": [{"path": "src/ghost.py", "lines": "1-2"}], "reason": "invented"}])
        text = self._status(out)
        self.assertNotIn("waiting on", text)
        self.assertIn("NEXT: oc_audit.py queue", text)
        self.assertIn("REQ-001", audit.Merged(audit.Ctx(out)).ver_rejected)


AGENTS = os.path.normpath(os.path.join(SCRIPTS, "..", "opencode", "agents"))


class LaneAgentFilesTest(unittest.TestCase):
    def _read(self, name):
        text = _read(os.path.join(AGENTS, name))
        front = text.split("---")[1]
        keys = [line.split(":")[0].strip() for line in front.strip().split("\n")]
        return keys, text

    def test_investigator_knows_the_repair_batch(self):
        _keys, text = self._read("oc-rca-investigator.md")
        self.assertIn("REPAIR", text)
        self.assertIn("at most two repair rounds", text)

    def test_verifier_knows_verdicts_are_linted(self):
        _keys, text = self._read("oc-rca-verifier.md")
        self.assertIn("citation checker", text)

    def test_neither_agent_sets_a_model_or_an_effort(self):
        for name in ("oc-rca-investigator.md", "oc-rca-verifier.md"):
            keys, _text = self._read(name)
            for banned in ("model", "effort", "variant", "reasoningEffort"):
                self.assertNotIn(banned, keys, name)


if __name__ == "__main__":
    unittest.main()
