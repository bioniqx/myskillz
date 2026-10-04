"""Port tests for the requirements-code-audit engine of the GLM edition (T22)."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.realpath(
    os.path.join(HERE, "..", "..", "requirements-code-audit-glm", "scripts"))
sys.path.insert(0, SCRIPTS)
import audit  # noqa: E402

AUDIT_PY = os.path.join(SCRIPTS, "audit.py")


def item(rid, **kw):
    row = {"id": rid, "text": "The system MUST do %s" % rid, "strength": "MUST",
           "stakes": "normal", "category": "core", "search_hints": ["alpha", "beta"],
           "tags": []}
    row.update(kw)
    return row


def evidence(lines="1-5"):
    return [{"path": "src/a.py", "lines": lines, "note": "n"}]


def finding(rid, status="MATCHED", confidence="high", **kw):
    row = {"id": rid, "status": status, "confidence": confidence,
           "evidence": evidence(), "searched": ["alpha", "beta"], "notes": "n"}
    row.update(kw)
    return row


def verdict(rid, status="MATCHED", agree=True, confidence="high", **kw):
    row = {"id": rid, "verified_status": status, "agree": agree,
           "confidence": confidence, "evidence": evidence(), "searched": ["gamma"],
           "reason": "r"}
    row.update(kw)
    return row


class AuditCase(unittest.TestCase):
    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="glm-audit-port-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.repo = os.path.join(self.root, "repo")
        self.out = os.path.join(self.repo, ".audit")
        for sub in ("findings", "verify", "batches", "spec"):
            os.makedirs(os.path.join(self.out, sub))
        self.write_file(os.path.join(self.repo, "src", "a.py"),
                        "".join("line %d\n" % n for n in range(1, 41)))
        self.config()
        self.checklist([])

    def write_file(self, path, text):
        folder = os.path.dirname(path)
        if not os.path.isdir(folder):
            os.makedirs(folder)
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def read_file(self, path):
        with io.open(path, encoding="utf-8") as fh:
            return fh.read()

    def config(self, **extra):
        cfg = {"version": audit.VERSION, "active": True, "repo_root": self.repo,
               "out_dir": self.out, "spec_files": [], "lang": "en", "lane": "api",
               "tier": "std", "threads": 4, "retrieval": "python",
               "models": {"judge": list(audit.TIERS["std"]["judge"]),
                          "verify": list(audit.TIERS["std"]["verify"])}}
        cfg.update(extra)
        self.write_file(os.path.join(self.out, "config.json"), json.dumps(cfg))

    def jsonl(self, name, rows):
        self.write_file(os.path.join(self.out, name),
                        "".join(json.dumps(r) + "\n" for r in rows))

    def checklist(self, rows):
        self.jsonl("checklist.jsonl", rows)

    def ctx(self):
        return audit.Ctx(self.out)

    def merged(self):
        return audit.Merged(self.ctx())

    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.pop("AUDIT_DIR", None)
        return subprocess.run(
            [sys.executable, AUDIT_PY, "--out", self.out] + list(args),
            cwd=self.repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", errors="replace")


class MergeSemanticsTests(AuditCase):
    def test_adjudication_beats_tag(self):
        self.checklist([item("REQ-001", tags=["static-limit"])])
        self.jsonl("adjudications.jsonl",
                   [{"id": "REQ-001", "final_status": "MISSING", "note": "n"}])
        self.assertEqual(self.merged().final("REQ-001"), ("MISSING", "lead"))

    def test_tag_without_adjudication_is_unverifiable(self):
        self.checklist([item("REQ-001", tags=["static-limit"])])
        self.jsonl("findings.jsonl", [finding("REQ-001")])
        self.assertEqual(self.merged().final("REQ-001"), ("UNVERIFIABLE", "tag"))

    def test_evidence_follows_the_deciding_pass(self):
        self.checklist([item("REQ-001")])
        self.jsonl("findings.jsonl", [finding("REQ-001", evidence=evidence("1-5"))])
        self.jsonl("verdicts.jsonl", [verdict("REQ-001", status="PARTIAL", agree=False,
                                              evidence=evidence("10-12"))])
        m = self.merged()
        self.assertEqual(m.final("REQ-001")[0], "PARTIAL")
        self.assertEqual(m.evidence("REQ-001")[0]["lines"], "10-12")
        self.jsonl("adjudications.jsonl",
                   [{"id": "REQ-001", "final_status": "MATCHED", "note": "n"}])
        m = self.merged()
        self.assertEqual(m.final("REQ-001")[0], "MATCHED")
        self.assertEqual(m.evidence("REQ-001")[0]["lines"], "1-5")

    def test_string_evidence_rows_are_coerced(self):
        self.checklist([item("REQ-001")])
        self.jsonl("findings/batch-01.jsonl", [{
            "id": "REQ-001", "status": "MATCHED", "confidence": "HIGH",
            "evidence": ["src/a.py:3-4 - does x"], "searched": "alpha"}])
        m = self.merged()
        self.assertEqual(m.evidence("REQ-001"),
                         [{"path": "src/a.py", "lines": "3-4", "note": "does x"}])
        self.assertEqual(m.find["REQ-001"]["searched"], ["alpha"])
        self.assertEqual(m.find["REQ-001"]["confidence"], "high")

    def test_plan_ids_accepts_a_string(self):
        self.assertEqual(audit.plan_ids({"ids": "REQ-001"}), ["REQ-001"])
        self.assertEqual(audit.plan_ids({"id": "REQ-002"}), ["REQ-002"])
        self.assertEqual(audit.plan_ids({"ids": ["A", "B"]}), ["A", "B"])


class QueueAndAdjudicateTests(AuditCase):
    def test_queue_rows_follow_the_original_rule(self):
        self.checklist([item("REQ-001"), item("REQ-002"), item("REQ-003"),
                        item("REQ-004"), item("REQ-005", tags=["static-limit"]),
                        item("REQ-006")])
        self.jsonl("findings.jsonl", [
            finding("REQ-001", status="MISSING", confidence="low"),
            finding("REQ-002", status="CONFLICT"),
            finding("REQ-003", status="PARTIAL", confidence="medium"),
            finding("REQ-004", status="UNVERIFIABLE", confidence="medium"),
            finding("REQ-005", status="MATCHED"),
            finding("REQ-006", status="MATCHED"),
        ])
        self.jsonl("verdicts.jsonl", [
            verdict("REQ-001", status="MISSING"),
            verdict("REQ-003", status="PARTIAL"),
            verdict("REQ-006", status="MATCHED", confidence="low"),
        ])
        rows = dict((r[0], r) for r in audit.queue_rows(self.merged()))
        self.assertEqual(set(rows), {"REQ-002", "REQ-004", "REQ-006"})

    def test_spot_sample_is_deterministic_and_skips_verified(self):
        ids = ["REQ-%03d" % n for n in range(1, 41)]
        self.checklist([item(i) for i in ids])
        self.jsonl("findings.jsonl", [finding(i) for i in ids])
        self.jsonl("verdicts.jsonl", [verdict(i) for i in ids[:5]])
        first = audit.spot_sample(self.merged())
        second = audit.spot_sample(self.merged())
        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        self.assertFalse(set(first) & set(ids[:5]))

    def test_adjudicate_accepts_several_set_pairs(self):
        self.checklist([item("REQ-001"), item("REQ-002")])
        r = self.run_cli("adjudicate", "--set", "REQ-001", "MISSING",
                         "--set", "REQ-002", "PARTIAL", "--note", "why")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = [json.loads(line) for line in
                self.read_file(os.path.join(self.out, "adjudications.jsonl")).splitlines()]
        self.assertEqual([(x["id"], x["final_status"]) for x in rows],
                         [("REQ-001", "MISSING"), ("REQ-002", "PARTIAL")])

    def test_accept_refuses_an_unsearched_item(self):
        self.checklist([item("REQ-001")])
        r = self.run_cli("adjudicate", "--accept", "REQ-001")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("UNSEARCHED", r.stderr)

    def test_accept_queue_records_the_queue_and_skips_unsearched(self):
        self.checklist([item("REQ-001"), item("REQ-002")])
        self.jsonl("findings.jsonl", [finding("REQ-001", status="CONFLICT")])
        r = self.run_cli("adjudicate", "--accept-queue")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = [json.loads(line) for line in
                self.read_file(os.path.join(self.out, "adjudications.jsonl")).splitlines()]
        self.assertEqual([(x["id"], x["final_status"]) for x in rows],
                         [("REQ-001", "CONFLICT")])
        self.assertIn("skipped", r.stdout)
        self.assertIn("REQ-002", r.stdout)


class CheckGateTests(AuditCase):
    def plan(self, rows):
        self.jsonl("plan.jsonl", rows)

    def entry(self, ids, priority="P1", effort="S"):
        return {"ids": ids, "title": "t", "priority": priority, "effort": effort,
                "target": "x"}

    def test_partial_never_verified_is_an_error(self):
        self.checklist([item("REQ-001")])
        self.jsonl("findings.jsonl", [finding("REQ-001", status="PARTIAL",
                                              confidence="medium")])
        self.plan([self.entry(["REQ-001"])])
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("never verified", r.stdout)

    def test_disagreement_is_an_error(self):
        self.checklist([item("REQ-001")])
        self.jsonl("findings.jsonl", [finding("REQ-001")])
        self.jsonl("verdicts.jsonl", [verdict("REQ-001", status="PARTIAL", agree=False)])
        self.plan([self.entry(["REQ-001"])])
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("disagree", r.stdout)

    def test_missing_without_searched_is_an_error(self):
        self.checklist([item("REQ-001")])
        self.jsonl("findings.jsonl", [finding("REQ-001", status="MISSING",
                                              confidence="low", evidence=[],
                                              searched=[])])
        self.jsonl("verdicts.jsonl", [verdict("REQ-001", status="MISSING", evidence=[],
                                              searched=[])])
        self.plan([self.entry(["REQ-001"])])
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("without any `searched`", r.stdout)

    def test_matched_low_confidence_unverified_only_warns(self):
        self.checklist([item("REQ-001")])
        self.jsonl("findings.jsonl", [finding("REQ-001", confidence="medium")])
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("WARN", r.stdout)
        self.assertIn("never verified", r.stdout)
        self.assertIn("GATE: PASS", r.stdout)

    def test_effort_and_priority_warnings(self):
        self.checklist([item("REQ-001", stakes="high"), item("REQ-002", strength="MAY")])
        self.jsonl("findings.jsonl", [finding("REQ-001", status="PARTIAL"),
                                      finding("REQ-002", status="PARTIAL")])
        self.jsonl("verdicts.jsonl", [verdict("REQ-001", status="PARTIAL"),
                                      verdict("REQ-002", status="PARTIAL")])
        self.plan([self.entry(["REQ-001"], priority="P1", effort="XL"),
                   self.entry(["REQ-002"], priority="P0")])
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("effort should be S/M/L", r.stdout)
        self.assertIn("expected P0", r.stdout)
        self.assertIn("MAY requirement at P0", r.stdout)

    def test_no_second_pass_is_an_error(self):
        self.checklist([item("REQ-001")])
        self.jsonl("findings.jsonl", [finding("REQ-001", confidence="medium")])
        self.write_file(os.path.join(self.out, "state.json"),
                        json.dumps({"run": {"wave_b": 0}}))
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("no second pass ran", r.stdout)

    def test_string_ids_and_string_evidence_do_not_crash(self):
        self.checklist([item("REQ-001")])
        self.jsonl("findings/batch-01.jsonl", [{
            "id": "REQ-001", "status": "PARTIAL", "confidence": "medium",
            "evidence": ["src/a.py:3-4 - does x"], "searched": "alpha"}])
        self.jsonl("verify/batch-V01.jsonl", [{
            "id": "REQ-001", "verified_status": "PARTIAL", "agree": True,
            "confidence": "high", "evidence": ["src/a.py:3-4"], "reason": "r"}])
        self.plan([{"ids": "REQ-001", "title": "t", "priority": "P1", "effort": "S",
                    "target": "x"}])
        r = self.run_cli("check")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        r = self.run_cli("report")
        self.assertEqual(r.returncode, 0, r.stderr)
        report = self.read_file(os.path.join(self.out, "requirements-code-audit.md"))
        self.assertIn("(REQ-001)", report)
        self.assertNotIn("R, E, Q", report)


class InputToleranceTests(AuditCase):
    def test_read_jsonl_accepts_a_whole_file_array(self):
        path = os.path.join(self.root, "rows.jsonl")
        self.write_file(path, json.dumps([{"id": "A"}, {"id": "B"}], indent=2))
        rows, errors = audit.read_jsonl(path)
        self.assertEqual([r["id"] for r in rows], ["A", "B"])
        self.assertEqual(errors, [])

    def test_read_jsonl_tolerates_comments_and_trailing_commas(self):
        path = os.path.join(self.root, "rows.jsonl")
        self.write_file(path, '# a note\n{"id": "A"},\n{"id": "B"}\n')
        rows, errors = audit.read_jsonl(path)
        self.assertEqual([r["id"] for r in rows], ["A", "B"])
        self.assertEqual(errors, [])

    def test_read_jsonl_reads_concatenated_pretty_objects(self):
        path = os.path.join(self.root, "rows.jsonl")
        self.write_file(path, '{\n "id": "A"\n}\n{\n "id": "B"\n}\n')
        rows, errors = audit.read_jsonl(path)
        self.assertEqual([r["id"] for r in rows], ["A", "B"])
        self.assertEqual(errors, [])

    def test_validate_checklist_accepts_dotted_ids_and_single_hints(self):
        rows = [item("FR.2", search_hints=["only"]), item("1", search_hints=[])]
        self.assertEqual(audit.validate_checklist(rows), [])

    def test_walk_repo_keeps_ci_dirs_and_template_files(self):
        tree = os.path.join(self.root, "tree")
        for rel in (".circleci/config.yml", ".github/workflows/ci.yml",
                    "views/page.erb", "contracts/Token.sol", "web/Index.cshtml",
                    "src/app.py", ".git/config", ".venv/lib.py", "docs/guide.md",
                    "README.md"):
            self.write_file(os.path.join(tree, rel), "x = 1\n")
        found = set(r[0] for r in audit.walk_repo(tree))
        for rel in (".circleci/config.yml", ".github/workflows/ci.yml",
                    "views/page.erb", "contracts/Token.sol", "web/Index.cshtml",
                    "src/app.py"):
            self.assertIn(rel, found)
        for rel in (".git/config", ".venv/lib.py", "docs/guide.md", "README.md"):
            self.assertNotIn(rel, found)

    def test_load_spec_extracts_pdf_text_with_pdftotext(self):
        bindir = os.path.join(self.root, "bin")
        script = os.path.join(bindir, "pdftotext")
        self.write_file(script, "#!/bin/sh\necho 'The system MUST log in.'\n")
        os.chmod(script, 0o755)
        pdf = os.path.join(self.root, "spec.pdf")
        with io.open(pdf, "wb") as fh:
            fh.write(b"%PDF-1.4\n")
        path = bindir + os.pathsep + os.environ.get("PATH", "")
        with mock.patch.dict(os.environ, {"PATH": path}):
            text, warns = audit.load_spec([pdf])
        self.assertIn("The system MUST log in.", text)
        self.assertEqual(warns, [])

    def test_load_spec_warns_when_pdftotext_is_missing(self):
        pdf = os.path.join(self.root, "spec.pdf")
        with io.open(pdf, "wb") as fh:
            fh.write(b"%PDF-1.4\n")
        with mock.patch.object(audit.shutil, "which", return_value=None):
            text, warns = audit.load_spec([pdf])
        self.assertNotIn("MUST", text)
        self.assertTrue(any("pdftotext" in w for w in warns))

    def test_load_spec_reads_xlsx_cells(self):
        path = os.path.join(self.root, "spec.xlsx")
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("xl/sharedStrings.xml",
                       "<sst><si><t>ID</t></si>"
                       "<si><t>The system MUST lock accounts &amp; log it</t></si></sst>")
            z.writestr("xl/worksheets/sheet1.xml",
                       '<worksheet><sheetData><row r="1">'
                       '<c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>'
                       '<row r="2"><c r="A2"><v>7</v></c><c r="B2" s="1"/></row>'
                       "</sheetData></worksheet>")
        text, warns = audit.load_spec([path])
        self.assertIn("ID\tThe system MUST lock accounts & log it", text)
        self.assertIn("\n7", text)
        self.assertEqual(warns, [])

    def test_parse_helpers_keep_identical_text_and_flag_duplicates(self):
        rows = [{"text": "The system MUST lock accounts."},
                {"text": "The system MUST lock accounts."}]
        clean = audit.renumber_draft(rows)
        self.assertEqual([r["id"] for r in clean], ["REQ-001", "REQ-002"])
        self.assertEqual(audit.possible_duplicates(clean), [("REQ-001", "REQ-002", 1.0)])

    def test_section_rows_reports_failed_sections(self):
        res = {"s01": ('{"id": "X", "text": "a"}', None),
               "s02": (None, RuntimeError("boom")),
               "s03": ("no json here", None)}
        rows, failed = audit.section_rows(res)
        self.assertEqual(len(rows), 1)
        self.assertEqual([k for k, _why in failed], ["s02", "s03"])

    def test_parse_on_the_agent_lane_does_not_point_at_missing_parsers(self):
        self.config(lane="agent")
        r = self.run_cli("parse")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("write checklist.jsonl yourself", r.stderr)
        self.assertNotIn("subagent", r.stderr)


class StubRetriever(object):
    def gather(self, it, tier, **kw):
        return {"queries": ["alpha"], "snippets": [], "layers": [], "considered": [],
                "near_misses": []}


class AgentLaneAndReportTests(AuditCase):
    def test_verify_batches_hold_at_most_three_items(self):
        self.assertEqual(audit.VERIFY_MAX_PER_AGENT, 3)
        groups = audit._agent_groups(list(range(40)), 4, audit.VERIFY_MAX_PER_AGENT, False)
        self.assertTrue(all(len(g) <= 3 for g in groups))

    def test_replan_clears_stale_findings_and_verify_batches(self):
        self.jsonl("findings/batch-01.jsonl", [finding("REQ-001")])
        self.jsonl("verify/batch-V01.jsonl", [verdict("REQ-001")])
        st = {"batches": {"batch-01": {"ids": ["REQ-001"]}},
              "vbatches": {"batch-V01": {"ids": ["REQ-001"]}}}
        audit.clear_run_artifacts(self.ctx(), st)
        self.assertEqual(os.listdir(os.path.join(self.out, "findings")), [])
        self.assertEqual(os.listdir(os.path.join(self.out, "verify")), [])
        self.assertEqual(st["vbatches"], {})

    def test_agent_batch_schema_asks_for_searched(self):
        for kind in ("find", "verify"):
            path = audit._batch_file(self.ctx(), StubRetriever(), "batch-%s" % kind,
                                     [item("REQ-001")], kind)
            self.assertIn('"searched"', self.read_file(path))

    def test_git_citations_are_rejected(self):
        self.write_file(os.path.join(self.repo, ".git", "config"), "[core]\n")
        row = {"status": "MATCHED", "confidence": "high",
               "evidence": [{"path": ".git/config", "lines": "1", "note": "n"}]}
        _out, errs, _warns = audit.lint_finding(row, {"id": "REQ-001"}, self.repo, set())
        self.assertTrue(any(".git/" in e for e in errs), errs)

    def test_report_keeps_full_text_and_counts_unsettled(self):
        long_text = "The system MUST " + "x" * 300
        self.checklist([item("REQ-001", text=long_text), item("REQ-002")])
        self.jsonl("findings.jsonl", [finding("REQ-001")])
        r = self.run_cli("report")
        self.assertEqual(r.returncode, 0, r.stderr)
        report = self.read_file(os.path.join(self.out, "requirements-code-audit.md"))
        self.assertIn(long_text, report)
        self.assertIn("Unsettled: 1", report)

    def test_finish_does_not_claim_a_write_guard(self):
        self.checklist([item("REQ-001")])
        r = self.run_cli("finish")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("guard", r.stdout)
