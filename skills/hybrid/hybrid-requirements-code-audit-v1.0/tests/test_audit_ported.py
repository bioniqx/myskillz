"""Hermetic black-box tests for the hybrid audit.py, ported from the Claude-only skill's
test_audit_misc.py and test_audit_status.py.

Every fixture lives under the system temp dir, every `init` passes `--preset claude` (claude mode must
behave exactly like the original skill), and every spawned audit.py gets a hermetic environment: temp
HOME, temp routing/doctor/telemetry/XDG paths, no opencode binary and no HYBRID_OPENCODE_* variables.

Covers (misc): idempotent plan/parse-plan re-runs, robust JSONL (pretty-printed, BOM, bad lines), the
UNSEARCHED status and adjudicate guard, string `ids` in plan.jsonl, `check` line-range formats,
git_exclude from a linked worktree, adjudicate performance, status printing the queue, report running
the check inline.
Covers (status): the stable spot-check sample, queue draining, partial SubagentStop redispatch and stale
events, verifier --undispatch/--redispatch/--failed, solo-mode relisting, NEXT never saying "wait" when
nothing is running.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit.py"
assert SCRIPT.exists(), SCRIPT

_ENV_DIR = None


def setUpModule():
    global _ENV_DIR
    _ENV_DIR = Path(os.path.realpath(tempfile.mkdtemp(prefix="audit_ported_env_")))


def tearDownModule():
    shutil.rmtree(str(_ENV_DIR), True)


def hermetic_env():
    env = dict(os.environ)
    for k in ("HYBRID_OPENCODE_STD", "HYBRID_OPENCODE_LITE", "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS"):
        env.pop(k, None)
    (_ENV_DIR / "home").mkdir(exist_ok=True)
    env.update({
        "HOME": str(_ENV_DIR / "home"),  # never let the script touch the real HOME
        "HYBRID_AUDIT_ROUTING": str(_ENV_DIR / "routing.json"),  # deliberately absent
        "HYBRID_AUDIT_DOCTOR_CACHE": str(_ENV_DIR / "doctor.json"),
        "HYBRID_AUDIT_TELEMETRY": str(_ENV_DIR / "lanes.jsonl"),
        "XDG_DATA_HOME": str(_ENV_DIR / "data"),
        "HYBRID_AUDIT_OC_BIN": str(_ENV_DIR / "no-such-opencode"),
        "HYBRID_OC_RETRY_DELAY_S": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    return env


def run(args, cwd, timeout=30):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--cwd", str(cwd)] + args,
        cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=hermetic_env(),
    )


def checklist_row(i, **overrides):
    row = {
        "id": "REQ-%03d" % i, "text": "Requirement %d text" % i, "strength": "MUST",
        "category": "core", "stakes": "normal", "evidence_expected": "",
        "search_hints": ["term%d" % i], "tags": [], "source": "", "question": "",
    }
    row.update(overrides)
    return row


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""), encoding="utf-8")


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def finding(rid, status="MATCHED", confidence="high", searched=("term",), evidence=None):
    return {"id": rid, "status": status, "confidence": confidence,
            "evidence": evidence if evidence is not None else [{"path": "src/x.py", "lines": "1-2", "note": "ok"}],
            "searched": list(searched), "notes": ""}


class AuditMiscTestCase(unittest.TestCase):
    def setUp(self):
        self.cwd = Path(os.path.realpath(tempfile.mkdtemp(prefix="audit_misc_")))
        self.addCleanup(shutil.rmtree, str(self.cwd), True)
        (self.cwd / "spec.md").write_text("The system MUST do things.\n", encoding="utf-8")
        self.out = self.cwd / ".hybrid-audit"

    def init_audit(self, agents="generic", cap=20):
        r = run(["init", "--spec", "spec.md", "--agents", agents, "--cap", str(cap), "--preset", "claude"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def set_state(self, **updates):
        state = read_json(self.out / "state.json")
        state.update(updates)
        write_json(self.out / "state.json", state)
        return state

    # ---------------------------------------------------------------- idempotent re-runs

    def test_plan_rerun_clears_stale_findings_verify_events(self):
        self.init_audit(cap=2)
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, 5)])
        r1 = run(["plan"], self.cwd)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)

        stale_finding = self.out / "findings" / "batch-01.jsonl"
        stale_verify = self.out / "verify" / "batch-V01.jsonl"
        stale_event = self.out / "events" / "batch-01.json"
        write_jsonl(stale_finding, [finding("REQ-001")])
        write_jsonl(stale_verify, [finding("REQ-001")])
        write_json(stale_event, {"batch": "batch-01", "ok": True, "msg": "done: 1/1 written"})
        self.assertTrue(stale_finding.exists() and stale_verify.exists() and stale_event.exists())

        r2 = run(["plan"], self.cwd)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertFalse(stale_finding.exists(), "plan re-run must clear stale findings")
        self.assertFalse(stale_verify.exists(), "plan re-run must clear stale verify files")
        self.assertFalse(stale_event.exists(), "plan re-run must clear stale events")

    def test_parse_plan_rerun_clears_stale_sections(self):
        self.init_audit()
        r1 = run(["parse-plan", "--sections", "4"], self.cwd)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        pdir = self.out / "parse"
        for i in range(1, 5):
            write_jsonl(pdir / ("section-%02d.jsonl" % i), [{"id": "S%02d-001" % i, "text": "x", "strength": "MUST"}])
        self.assertEqual(len(list(pdir.glob("section-*.jsonl"))), 4)

        r2 = run(["parse-plan", "--sections", "2"], self.cwd)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertEqual(list(pdir.glob("section-*.jsonl")), [], "parse-plan re-run must clear stale section-*.jsonl")

    def test_parse_merge_reads_only_expected_sections(self):
        self.init_audit()
        pdir = self.out / "parse"
        pdir.mkdir(parents=True, exist_ok=True)
        self.set_state(parse={"sections": 2, "dispatched": time.time()})
        write_jsonl(pdir / "section-01.jsonl", [{"id": "S01-001", "text": "one", "strength": "MUST"}])
        write_jsonl(pdir / "section-02.jsonl", [{"id": "S02-001", "text": "two", "strength": "MUST"}])
        # a leftover file from a PRIOR run with more sections (k=3) that parse-plan didn't clear
        write_jsonl(pdir / "section-03.jsonl", [{"id": "S03-001", "text": "stale-leftover", "strength": "MUST"}])

        r = run(["parse-merge"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        draft_rows = [json.loads(l) for l in (self.out / "checklist.draft.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(draft_rows), 2, "parse-merge must read only sections 1..expected, not stale leftovers: %r" % draft_rows)
        self.assertNotIn("stale-leftover", [row["text"] for row in draft_rows])

    # ---------------------------------------------------------------- robust JSONL

    def test_pretty_printed_json_findings_parsed(self):
        self.init_audit()
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1)])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])
        pretty = json.dumps([finding("REQ-001")], indent=2, ensure_ascii=False)
        (self.out / "findings" / "manual.jsonl").parent.mkdir(parents=True, exist_ok=True)
        (self.out / "findings" / "manual.jsonl").write_text(pretty, encoding="utf-8")

        r = run(["status"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("✅", r.stdout, "pretty-printed JSON findings must be parsed (expected a MATCHED count): %s" % r.stdout)

    def test_unparseable_findings_line_reported_by_status(self):
        self.init_audit()
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1)])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])
        bad = self.out / "findings" / "manual.jsonl"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text('{"id": "REQ-001", "status": "MATCHED", broken\n', encoding="utf-8")

        r = run(["status"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("manual.jsonl", r.stdout, "an unparseable findings line must be surfaced by status: %s" % r.stdout)

    def test_empty_findings_file_does_not_crash(self):
        self.init_audit()
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1)])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])
        empty = self.out / "findings" / "empty.jsonl"
        empty.parent.mkdir(parents=True, exist_ok=True)
        empty.write_text("", encoding="utf-8")

        r = run(["status"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_bom_at_findings_file_start_is_parsed(self):
        self.init_audit()
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1)])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])
        bomfile = self.out / "findings" / "manual.jsonl"
        bomfile.parent.mkdir(parents=True, exist_ok=True)
        content = "\ufeff" + json.dumps(finding("REQ-001")) + "\n"
        bomfile.write_bytes(content.encode("utf-8"))

        r = run(["status"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("✅", r.stdout, "a BOM at the start of a findings file must not break parsing: %s" % r.stdout)

    # ---------------------------------------------------------------- schema

    def test_findings_schema_enum_includes_unsearched(self):
        self.init_audit(cap=2)
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1)])
        r = run(["plan"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        batch_md = (self.out / "batches" / "batch-01.md").read_text(encoding="utf-8")
        self.assertIn("UNSEARCHED", batch_md, "FINDINGS_SCHEMA's status enum must include UNSEARCHED")
        self.assertRegex(batch_md, r'"status":"MATCHED\|PARTIAL\|MISSING\|CONFLICT\|UNVERIFIABLE\|UNSEARCHED"')

    # ---------------------------------------------------------------- plan ids as string

    def test_plan_entry_ids_as_string_treated_as_one_element_list(self):
        self.init_audit()
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1)])
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding("REQ-001", status="MISSING", evidence=[])])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])
        run(["adjudicate", "--set", "REQ-001", "MISSING", "--note", "confirmed gap"], self.cwd)
        write_jsonl(self.out / "plan.jsonl", [
            {"ids": "REQ-001", "priority": "P1", "title": "fix it", "effort": "S"},
        ])

        rs = run(["status"], self.cwd)
        self.assertEqual(rs.returncode, 0, rs.stdout + rs.stderr)
        self.assertNotIn("need a remediation entry", rs.stdout,
                          "a string `ids` field must be recognised as covering REQ-001: %s" % rs.stdout)

        rc = run(["check"], self.cwd)
        self.assertNotIn("REQ-001: discrepancy without a remediation entry", rc.stdout + rc.stderr)

        rr = run(["report"], self.cwd)
        self.assertEqual(rr.returncode, 0, rr.stdout + rr.stderr)
        report_text = (self.out / "requirements-code-audit.md").read_text(encoding="utf-8")
        self.assertIn("(REQ-001)", report_text)
        self.assertNotIn("R, E, Q", report_text, "a string `ids` field must not be split character by character")

    # ---------------------------------------------------------------- adjudicate refuses UNSEARCHED

    def test_adjudicate_accept_refuses_unsearched(self):
        self.init_audit()
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1)])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])
        r = run(["adjudicate", "--accept", "REQ-001"], self.cwd)
        self.assertNotEqual(r.returncode, 0, "accepting an UNSEARCHED id must be refused")
        self.assertIn("UNSEARCHED", r.stdout + r.stderr)
        adj_path = self.out / "adjudications.jsonl"
        self.assertTrue(not adj_path.exists() or adj_path.read_text(encoding="utf-8").strip() == "",
                         "a refused accept must not write an adjudication")

    def test_adjudicate_accept_queue_skips_unsearched(self):
        self.init_audit()
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1), checklist_row(2)])
        # REQ-002 has a real (CONFLICT) finding so it queues deterministically and can be accepted;
        # REQ-001 has no finding at all -> UNSEARCHED -> must be skipped, not recorded.
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding("REQ-002", status="CONFLICT")])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])

        r = run(["adjudicate", "--accept-queue"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        adj_path = self.out / "adjudications.jsonl"
        rows = [json.loads(l) for l in adj_path.read_text(encoding="utf-8").splitlines() if l.strip()] if adj_path.exists() else []
        ids = {row["id"] for row in rows}
        self.assertIn("REQ-002", ids)
        self.assertNotIn("REQ-001", ids, "--accept-queue must not record an UNSEARCHED id")
        for row in rows:
            self.assertNotEqual(row["final_status"], "UNSEARCHED")

    # ---------------------------------------------------------------- check: adjudicated MISSING skip

    def test_check_skips_searched_terms_rule_for_adjudicated_missing(self):
        self.init_audit()
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1)])
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding("REQ-001", status="MISSING", searched=[], evidence=[])])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])

        r1 = run(["check"], self.cwd)
        self.assertIn("MISSING without any `searched` terms", r1.stdout, r1.stdout)

        r2 = run(["adjudicate", "--set", "REQ-001", "MISSING", "--note", "confirmed, adequately searched"], self.cwd)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

        r3 = run(["check"], self.cwd)
        self.assertNotIn("MISSING without any `searched` terms", r3.stdout,
                          "the searched-terms rule must be skipped once the id is adjudicated: %s" % r3.stdout)

    # ---------------------------------------------------------------- check: evidence line formats

    def test_check_accepts_L_prefixed_and_en_dash_line_ranges(self):
        self.init_audit()
        src = self.cwd / "src" / "x.py"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("\n".join("line %d" % i for i in range(1, 70)) + "\n", encoding="utf-8")
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1), checklist_row(2)])
        write_jsonl(self.out / "findings" / "manual.jsonl", [
            finding("REQ-001", evidence=[{"path": "src/x.py", "lines": "L41-L58", "note": "ok"}]),
            finding("REQ-002", evidence=[{"path": "src/x.py", "lines": "41–58", "note": "ok"}]),
        ])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])

        r = run(["check"], self.cwd)
        self.assertNotIn("unparseable", r.stdout, r.stdout)

    # ---------------------------------------------------------------- git_exclude / linked worktree

    def _make_worktree_repo(self, base):
        main = base / "main_repo"
        main.mkdir()
        genv = dict(os.environ)
        genv["HOME"] = str(base)
        genv["GIT_AUTHOR_NAME"] = genv["GIT_COMMITTER_NAME"] = "t"
        genv["GIT_AUTHOR_EMAIL"] = genv["GIT_COMMITTER_EMAIL"] = "t@example.com"

        def g(args, cwd):
            return subprocess.run(["git"] + args, cwd=str(cwd), env=genv, capture_output=True, text=True, timeout=30)

        self.assertEqual(g(["init", "-q"], main).returncode, 0)
        (main / "README.md").write_text("x\n", encoding="utf-8")
        self.assertEqual(g(["add", "."], main).returncode, 0)
        self.assertEqual(g(["commit", "-q", "-m", "init"], main).returncode, 0, g(["commit", "-q", "-m", "init"], main).stderr)
        wt = base / "linked_wt"
        rw = g(["worktree", "add", "-q", str(wt), "-b", "feature"], main)
        self.assertEqual(rw.returncode, 0, rw.stdout + rw.stderr)
        return main, wt

    def test_git_exclude_writes_common_dir_info_exclude_from_linked_worktree(self):
        base = Path(os.path.realpath(tempfile.mkdtemp(prefix="audit_gitwt_")))
        self.addCleanup(shutil.rmtree, str(base), True)
        main, wt = self._make_worktree_repo(base)
        (wt / "spec.md").write_text("The system MUST do things.\n", encoding="utf-8")

        r = run(["init", "--spec", "spec.md", "--preset", "claude"], wt)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

        common_exclude = main / ".git" / "info" / "exclude"
        self.assertTrue(common_exclude.exists(), "info/exclude must be written to the COMMON git dir, not the worktree's private git dir")
        self.assertIn(".hybrid-audit", common_exclude.read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- perf: adjudicate at scale

    def test_adjudicate_accept_queue_fast_with_many_queued(self):
        self.init_audit()
        n = 600
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, n + 1)])
        rows = [finding("REQ-%03d" % i, status="CONFLICT") for i in range(1, 324)]
        rows += [finding("REQ-%03d" % i, status="MATCHED", confidence="high") for i in range(324, n + 1)]
        write_jsonl(self.out / "findings" / "manual.jsonl", rows)
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])

        rq = run(["queue"], self.cwd)
        self.assertEqual(rq.returncode, 0, rq.stdout + rq.stderr)

        t0 = time.time()
        ra = run(["adjudicate", "--accept-queue"], self.cwd, timeout=20)
        elapsed = time.time() - t0
        self.assertEqual(ra.returncode, 0, ra.stdout + ra.stderr)
        self.assertLess(elapsed, 0.5, "adjudicate --accept-queue with ~323 queued ids of 600 took %.2fs (Merged(c) must be built once, not per id)" % elapsed)

    # ---------------------------------------------------------------- report runs check inline / status prints queue

    def test_status_prints_queue_itself_once_waves_complete(self):
        self.init_audit()
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1)])
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding("REQ-001", status="CONFLICT")])
        write_jsonl(self.out / "verify" / "batch-V01.jsonl", [finding("REQ-001", status="CONFLICT")])
        self.set_state(plan_time=time.time(), batches={},
                        verify={"batch-V01": {"ids": ["REQ-001"], "dispatched": time.time()}},
                        verify_assigned={"REQ-001": "batch-V01"},
                        spotchecked=[], hedges={}, failed=[])

        r = run(["status"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("REQ-001", r.stdout, "status must print the queued item itself, not just point at `audit.py queue`: %s" % r.stdout)
        self.assertIn("requirement:", r.stdout)

    # ---------------------------------------------------------------- F17: no O(N) MEANWHILE queue, read_jsonl errors

    def planned(self, n, cap=5):
        self.init_audit(cap=cap)
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, n + 1)])
        r = run(["plan"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def load_audit(self, name):
        import importlib.util
        spec = importlib.util.spec_from_file_location(name, str(SCRIPT))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_status_after_plan_prints_no_queue_blocks(self):
        self.planned(40)
        r = run(["status"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("already queued for adjudication", r.stdout)
        self.assertNotIn("requirement:", r.stdout)
        self.assertNotIn("no finding", r.stdout)
        self.assertNotIn("spot-check sample", r.stdout)

    def test_status_mid_wave_only_presents_ids_with_finding(self):
        self.planned(6, cap=2)
        # REQ-001 has a CONFLICT finding (ready); the rest have no finding yet
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding("REQ-001", status="CONFLICT")])
        r = run(["status"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("already queued for adjudication (1)", r.stdout, r.stdout)
        self.assertNotIn("no finding", r.stdout)
        self.assertNotIn("spot-check sample", r.stdout)

    def test_status_mid_wave_hides_id_awaiting_assigned_verifier(self):
        self.planned(2, cap=2)
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding("REQ-001", status="CONFLICT")])
        st = read_json(self.out / "state.json")
        st.setdefault("verify", {})["batch-V01"] = {"ids": ["REQ-001"], "dispatched": time.time()}
        st.setdefault("verify_assigned", {})["REQ-001"] = "batch-V01"
        write_json(self.out / "state.json", st)
        r = run(["status"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("already queued for adjudication", r.stdout, r.stdout)

    def test_status_names_bad_findings_file_and_line(self):
        self.init_audit()
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1)])
        write_jsonl(self.out / "findings" / "batch-01.jsonl", [finding("REQ-001")])
        (self.out / "findings" / "bad.jsonl").write_text('{"id":"A"}\n{"id":"B", broken\n', encoding="utf-8")
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                       spotchecked=[], hedges={}, failed=[])
        r = run(["status"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("bad.jsonl:2", r.stdout, r.stdout)

    def test_read_jsonl_returns_rows_and_errors(self):
        mod = self.load_audit("audit_mod_f17")
        p = self.cwd / "x.jsonl"
        p.write_text('{"id":"A"}\n{"id":"B", broken\n', encoding="utf-8")
        rows, errs = mod.read_jsonl(p)
        self.assertEqual([r["id"] for r in rows], ["A"])
        self.assertTrue(errs)
        self.assertIn("x.jsonl:2", errs[0])

    def test_plan_fails_on_one_bad_checklist_line(self):
        self.init_audit()
        lines = [json.dumps(checklist_row(i)) for i in (1, 2)] + ['{"id": "REQ-003", broken']
        (self.out / "checklist.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        r = run(["plan"], self.cwd)
        self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("checklist.jsonl:3", r.stdout + r.stderr)

    def test_pretty_printed_finding_with_inline_evidence_object(self):
        mod = self.load_audit("audit_mod_f17b")
        p = self.cwd / "pretty.jsonl"
        p.write_text('{\n "id": "REQ-001",\n "status": "MATCHED",\n "evidence": [\n'
                     '  {"path": "src/x.py", "lines": "1-2", "note": "ok"}\n ]\n}\n', encoding="utf-8")
        rows, errs = mod.read_jsonl(p)
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0].get("id"), "REQ-001")
        self.assertEqual(errs, [])

    def test_report_runs_check_inline_and_prints_verdict(self):
        self.init_audit()
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1)])
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding("REQ-001")])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])

        r = run(["report"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CHECK:", r.stdout, "report must run the check logic inline and print its verdict: %s" % r.stdout)

    def test_status_does_not_queue_id_assigned_to_verifier_in_same_call(self):
        self.init_audit()
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1)])
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding("REQ-001", status="CONFLICT", confidence="medium")])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])

        r1 = run(["status"], self.cwd)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        self.assertIn("batch-V01", r1.stdout, r1.stdout)
        self.assertEqual(read_json(self.out / "state.json")["verify_assigned"].get("REQ-001"), "batch-V01")
        self.assertNotIn("already queued for adjudication", r1.stdout,
                         "an id dispatched to a verifier in this same call must not be listed as ready to adjudicate")

        r2 = run(["status"], self.cwd)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertNotIn("already queued for adjudication", r2.stdout,
                         "an id still assigned to an unfinished verifier must stay out of the queue block")



class AuditStatusTestCase(unittest.TestCase):
    def setUp(self):
        self.cwd = Path(os.path.realpath(tempfile.mkdtemp(prefix="audit_status_")))
        self.addCleanup(shutil.rmtree, str(self.cwd), True)
        (self.cwd / "spec.md").write_text("The system MUST do things.\n", encoding="utf-8")
        self.out = self.cwd / ".hybrid-audit"

    def init_audit(self, agents="generic", cap=20):
        r = run(["init", "--spec", "spec.md", "--agents", agents, "--cap", str(cap), "--preset", "claude"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def set_state(self, **updates):
        state = read_json(self.out / "state.json")
        state.update(updates)
        write_json(self.out / "state.json", state)
        return state

    # ---------------------------------------------------------------- criterion 1

    def test_spotcheck_sample_deterministic_across_adjudication(self):
        """600-item fixture: adjudicating a sampled item must not change which
        other items get spot-checked (the sample is a fixed function of the set)."""
        self.init_audit()
        n = 600
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, n + 1)])
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding("REQ-%03d" % i) for i in range(1, n + 1)])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])

        r1 = run(["queue"], self.cwd)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        sample0 = sorted(rid for rid, why in re.findall(r"^(REQ-\d+) \[[^\]]*\] — (.*)$", r1.stdout, re.M)
                          if "spot-check sample" in why)
        self.assertEqual(len(sample0), 30, r1.stdout)  # max(3, ceil(0.05*600))

        decided = sample0[0]
        r2 = run(["adjudicate", "--set", decided, "MATCHED", "--note", "spot-checked ok"], self.cwd)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

        r3 = run(["queue"], self.cwd)
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
        sample1 = sorted(rid for rid, why in re.findall(r"^(REQ-\d+) \[[^\]]*\] — (.*)$", r3.stdout, re.M)
                          if "spot-check sample" in why)

        self.assertEqual(
            sample1, [rid for rid in sample0 if rid != decided],
            "adjudicating one sampled item reshuffled the rest of the spot-check sample",
        )

    def test_accept_queue_drains_to_empty(self):
        self.init_audit()
        n = 30
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, n + 1)])
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding("REQ-%03d" % i) for i in range(1, n + 1)])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])

        for _ in range(20):
            r = run(["queue"], self.cwd)
            if "Adjudication queue is empty" in r.stdout:
                break
            ra = run(["adjudicate", "--accept-queue"], self.cwd)
            self.assertEqual(ra.returncode, 0, ra.stdout + ra.stderr)
        else:
            self.fail("repeated `adjudicate --accept-queue` never drained the queue to empty")

    # ---------------------------------------------------------------- criterion 2

    def test_partial_subagentstop_redispatch_and_stale_events(self):
        self.init_audit(agents="generic", cap=2)
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, 7)])
        rp = run(["plan"], self.cwd)
        self.assertEqual(rp.returncode, 0, rp.stdout + rp.stderr)
        state = read_json(self.out / "state.json")
        self.assertIn("batch-01", state["batches"])
        self.assertIn("batch-02", state["batches"])
        ids1 = state["batches"]["batch-01"]["ids"]

        # batch-02 fully covered; batch-01 partial (2 of 3), agent reported done anyway
        write_jsonl(self.out / "findings" / "batch-02.jsonl",
                    [finding(rid) for rid in state["batches"]["batch-02"]["ids"]])
        write_jsonl(self.out / "findings" / "batch-01.jsonl", [finding(ids1[0]), finding(ids1[1])])
        write_json(self.out / "events" / "batch-01.json", {"batch": "batch-01", "ok": True, "msg": "done: 2/3 written"})

        r1 = run(["status"], self.cwd)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        self.assertIn("NOTE: agents finished without complete output: batch-01", r1.stdout)
        self.assertIn("--redispatch batch-01", r1.stdout, "NEXT must name the redispatch command")

        r2 = run(["status", "--redispatch", "batch-01"], self.cwd)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        m = re.search(r"\b(batch-01-r\d+)\b", r2.stdout)
        self.assertIsNotNone(m, "redispatch did not produce a retry batch: %s" % r2.stdout)
        retry_name = m.group(1)

        r3 = run(["status"], self.cwd)
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
        self.assertNotIn(
            "NOTE: agents finished without complete output: batch-01", r3.stdout,
            "a stale events file (older than the fresh redispatch) still flags the batch as stuck",
        )

        # the stale original event no longer matters; now the RETRY itself fails
        (self.out / "events" / "batch-01.json").unlink()
        write_json(self.out / "events" / (retry_name + ".json"), {"batch": retry_name, "ok": False, "msg": "retry stopped early"})

        r4 = run(["status"], self.cwd)
        self.assertEqual(r4.returncode, 0, r4.stdout + r4.stderr)
        self.assertIn(
            "FAILED/partial: batch-01", r4.stdout,
            "a failing retry event (batch-01-rNNN) must count toward its base batch batch-01",
        )

    # ---------------------------------------------------------------- criterion 3

    def test_verifier_batch_undispatch_redispatch_failed(self):
        self.init_audit(agents="generic")
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1), checklist_row(2)])
        t0 = time.time() - 1000
        self.set_state(
            plan_time=time.time(), batches={}, verify={"batch-V01": {"ids": ["REQ-001", "REQ-002"], "dispatched": t0}},
            verify_assigned={"REQ-001": "batch-V01", "REQ-002": "batch-V01"},
            spotchecked=[], hedges={}, failed=[],
        )

        with self.subTest("undispatch"):
            r = run(["status", "--undispatch", "batch-V01"], self.cwd)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            state = read_json(self.out / "state.json")
            self.assertIsNone(state["verify"]["batch-V01"]["dispatched"])

        with self.subTest("redispatch"):
            self.set_state(verify={"batch-V01": {"ids": ["REQ-001", "REQ-002"], "dispatched": t0}})
            r = run(["status", "--redispatch", "batch-V01"], self.cwd)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertRegex(r.stdout, r"batch-V01-r\d+", "--redispatch does not work for verifier batches")

        with self.subTest("failed"):
            self.set_state(verify={"batch-V01": {"ids": ["REQ-001", "REQ-002"], "dispatched": t0}},
                            verify_assigned={"REQ-001": "batch-V01", "REQ-002": "batch-V01"}, failed=[])
            r = run(["status", "--failed", "batch-V01"], self.cwd)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            state = read_json(self.out / "state.json")
            self.assertNotEqual(
                state.get("verify_assigned", {}).get("REQ-001"), "batch-V01",
                "a failed verifier batch's ids must leave verify_assigned so they reappear for verification",
            )

    # ---------------------------------------------------------------- criterion 4 + 5

    def test_solo_mode_relists_undispatched_verifier_batches(self):
        self.init_audit(agents="solo")
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, 6)])
        write_jsonl(self.out / "findings" / "manual.jsonl",
                    [finding("REQ-%03d" % i, status="PARTIAL", confidence="medium") for i in range(1, 6)])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])

        r1 = run(["status"], self.cwd)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        self.assertIn("SOLO MODE", r1.stdout)
        self.assertIn("batch-V01", r1.stdout)

        r2 = run(["status"], self.cwd)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn(
            "batch-V01", r2.stdout,
            "solo mode must re-list still-undispatched verifier batches on every status",
        )
        self.assertNotIn(
            "wait for completion notifications", r2.stdout,
            "solo mode never has anything 'running' to wait for",
        )

    def test_next_never_says_wait_when_nothing_running(self):
        """Edge case: an investigator finishes (SubagentStop ok) but its findings
        file has zero entries. Nothing is running (ri=rv=0), so NEXT must be a
        concrete command, never the generic 'wait for completion' line."""
        self.init_audit(agents="generic", cap=1)
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1), checklist_row(2)])
        rp = run(["plan"], self.cwd)
        self.assertEqual(rp.returncode, 0, rp.stdout + rp.stderr)
        write_jsonl(self.out / "findings" / "batch-01.jsonl", [])  # zero findings
        write_json(self.out / "events" / "batch-01.json", {"batch": "batch-01", "ok": True, "msg": "done: 0/2 written"})

        r = run(["status"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(
            "wait for completion notifications", r.stdout,
            "nothing is running (ri=rv=0); NEXT must name a concrete command instead",
        )

    # ---------------------------------------------------------------- F8 criteria

    def test_solo_mode_relists_unfinished_investigator_batches(self):
        """After `plan` marks wave-1 batches dispatched, solo `status` must keep
        re-listing every unfinished investigator batch on every call, and NEXT
        must never tell a solo lead to wait for a notification that never comes."""
        self.init_audit(agents="solo")
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, 11)])
        rp = run(["plan"], self.cwd)
        self.assertEqual(rp.returncode, 0, rp.stdout + rp.stderr)
        state = read_json(self.out / "state.json")
        batch_names = sorted(state["batches"])
        self.assertGreaterEqual(len(batch_names), 2, state["batches"])

        first_ids = state["batches"][batch_names[0]]["ids"]
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding(rid) for rid in first_ids])

        for _ in range(2):
            r = run(["status"], self.cwd)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            for b in batch_names[1:]:
                self.assertIn(b, r.stdout, "unfinished investigator batch %s must stay listed: %s" % (b, r.stdout))
            self.assertNotIn(
                "wait for completion notifications", r.stdout,
                "solo mode never has anything 'running' to wait for",
            )

    def test_generic_undispatched_verifier_batch_relisted_by_later_status(self):
        """`--undispatch` leaves the verifier batch undispatched in THAT call; a
        separate later plain `status` with free slots re-lists and dispatches it."""
        self.init_audit(agents="generic")
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1), checklist_row(2)])
        t0 = time.time() - 1000
        self.set_state(
            plan_time=time.time(), batches={}, verify={"batch-V01": {"ids": ["REQ-001", "REQ-002"], "dispatched": t0}},
            verify_assigned={"REQ-001": "batch-V01", "REQ-002": "batch-V01"},
            spotchecked=[], hedges={}, failed=[],
        )

        r1 = run(["status", "--undispatch", "batch-V01"], self.cwd)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        self.assertIsNone(read_json(self.out / "state.json")["verify"]["batch-V01"]["dispatched"],
                          "--undispatch must leave the batch undispatched in that same call")

        r2 = run(["status"], self.cwd)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("batch-V01", r2.stdout,
                      "an undispatched verifier batch with free slots must be re-listed: %s" % r2.stdout)
        self.assertIsNotNone(read_json(self.out / "state.json")["verify"]["batch-V01"]["dispatched"],
                             "the re-listed verifier batch must be marked dispatched again")



if __name__ == "__main__":
    unittest.main()
