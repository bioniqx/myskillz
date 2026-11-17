"""SLOW wave C: second judge, substring drop, CONFLICT flip. No network."""
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
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "glm-requirements-code-audit", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import audit  # noqa: E402


def _repo():
    d = tempfile.mkdtemp(prefix="audit-slow-")
    os.makedirs(os.path.join(d, "src"))
    with io.open(os.path.join(d, "src", "app.py"), "w", encoding="utf-8") as fh:
        fh.write(u"".join(u"line_%d = %d\n" % (i, i) for i in range(1, 21)))
    return d


class FakeCl(object):
    def __init__(self, replies):
        self.replies = list(replies)

    def call(self, model, effort, prefix, task, max_tokens, temperature=None, **kw):
        r = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return json.dumps(r)


ITEM = {"id": "REQ-001", "text": "Users can log in", "strength": "MUST",
        "stakes": "normal", "search_hints": ["login"]}


class SlowAuditTestBase(unittest.TestCase):
    def setUp(self):
        self.repo = _repo()
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.out = tempfile.mkdtemp(prefix="audit-slow-out-")
        self.addCleanup(shutil.rmtree, self.out, True)
        os.makedirs(os.path.join(self.repo, ".claude", "dev-team"))
        with io.open(os.path.join(self.repo, ".claude", "dev-team", "mode"), "w",
                     encoding="utf-8") as fh:
            fh.write("slow 123\n")
        with io.open(os.path.join(self.out, "config.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"repo_root": self.repo, "lane": "api", "tier": "std"}))

    def write_row(self, name, row):
        with io.open(os.path.join(self.out, name), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + u"\n")

    def ctx(self):
        return audit.Ctx(self.out)


class DropUnquotedTests(SlowAuditTestBase):
    def test_a_matched_whose_quote_is_absent_is_dropped(self):
        verdict = {"id": "REQ-001", "verified_status": "MATCHED", "confidence": "high",
                   "evidence": [{"path": "src/app.py", "lines": "2-4"}],
                   "agree": True,
                   "attack": {"kind": "NO-BREAK", "path": "src/app.py",
                              "lines": "2-4", "quote": "not in the file at all"}}
        self.write_row("checklist.jsonl", ITEM)
        self.write_row("findings.jsonl", dict(
            {"id": "REQ-001", "status": "MATCHED", "confidence": "medium",
             "evidence": [{"path": "src/app.py", "lines": "2-4", "note": "login"}],
             "notes": "found"}))
        self.write_row("verdicts.jsonl", verdict)
        c = self.ctx()
        m = audit.Merged(c)
        self.assertEqual(m.final("REQ-001")[0], "MATCHED")
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            pass
        dropped = audit.slow_drop_unquoted(c, m)
        self.assertEqual(dropped, ["REQ-001"])
        m2 = audit.Merged(c)
        self.assertEqual(m2.final("REQ-001")[0], "UNSEARCHED")
        with io.open(os.path.join(self.out, "findings.jsonl"), encoding="utf-8") as fh:
            row = json.loads(fh.readline())
        self.assertEqual(row["status"], "UNSEARCHED")
        self.assertIn("substring", row["notes"])


class SecondJudgeTests(SlowAuditTestBase):
    def test_a_reproduced_counterexample_flips_the_finding_to_conflict(self):
        finding = {"id": "REQ-001", "status": "MATCHED", "confidence": "medium",
                   "evidence": [{"path": "src/app.py", "lines": "2-4",
                                 "quote": "line_2 = 2", "note": "login"}],
                   "notes": "found"}
        self.write_row("checklist.jsonl", ITEM)
        self.write_row("findings.jsonl", finding)
        c = self.ctx()
        cl = FakeCl([{"id": "REQ-001", "kind": "COUNTEREXAMPLE",
                      "command": "false", "path": "", "lines": "", "quote": ""}])
        row = audit.second_one(cl, ("fake-model", "high"), audit.second_prefix(),
                               dict(ITEM), finding["evidence"], self.repo, 800)
        self.assertEqual(row["kind"], "COUNTEREXAMPLE")
        self.assertTrue(row["reproduced"], "the engine re-ran `false` and saw non-zero")
        flipped = audit.apply_second_conflicts(c, {"REQ-001": row})
        self.assertEqual(flipped, ["REQ-001"])
        m = audit.Merged(c)
        self.assertEqual(m.final("REQ-001")[0], "CONFLICT")
        self.assertEqual(m.counts()["CONFLICT"], 1)

    def test_a_quote_counterexample_reproduces_only_from_the_cited_lines(self):
        probe = {"kind": "COUNTEREXAMPLE", "path": "src/app.py",
                 "lines": "5-6", "quote": "line_5 = 5"}
        self.assertTrue(audit.second_reproduces(self.repo, probe))
        probe_bad = dict(probe, quote="paraphrase that is not there")
        self.assertFalse(audit.second_reproduces(self.repo, probe_bad))
        self.assertFalse(audit.second_reproduces(self.repo, {"kind": "NO-BREAK"}))

    def test_a_flipped_conflict_is_not_dropped_by_the_substring_pass(self):
        finding = {"id": "REQ-001", "status": "MATCHED", "confidence": "medium",
                   "evidence": [{"path": "src/app.py", "lines": "2-4", "note": "login"}],
                   "notes": "found"}
        self.write_row("checklist.jsonl", ITEM)
        self.write_row("findings.jsonl", finding)
        c = self.ctx()
        sec = {"id": "REQ-001", "kind": "COUNTEREXAMPLE", "command": "false",
               "path": "", "lines": "", "quote": "", "reproduced": True}
        self.assertEqual(audit.apply_second_conflicts(c, {"REQ-001": sec}),
                         ["REQ-001"])
        m = audit.Merged(c)
        self.assertEqual(audit.slow_drop_unquoted(c, m), [])
        self.assertEqual(audit.Merged(c).final("REQ-001")[0], "CONFLICT")

    def test_the_prompt_carries_the_item_and_cited_lines_and_nothing_else(self):
        prefix = audit.second_prefix()
        self.assertIn("second judge", prefix.lower())
        self.assertNotIn("REPOSITORY MAP", prefix.upper())
        finding = {"evidence": [{"path": "src/app.py", "lines": "2-4"}]}
        task = audit.second_task(dict(ITEM), audit.cited_snips(self.repo, finding["evidence"]))
        self.assertIn("Users can log in", task)
        self.assertIn("line_2 = 2", task)
        self.assertNotIn("verified_status", task)


class AgentLaneWaveCTests(SlowAuditTestBase):
    def test_ingest_engine_verifies_raw_rows_and_wave_c_dispatches_once(self):
        self.write_row("checklist.jsonl", ITEM)
        self.write_row("findings.jsonl", {
            "id": "REQ-001", "status": "MATCHED", "confidence": "high",
            "evidence": [{"path": "src/app.py", "lines": "2-4", "note": "x"}],
            "notes": "found"})
        c = self.ctx()
        st = c.state()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            act = audit._second_wave_agent(c, audit.Merged(c), st)
        self.assertIsNone(act, "a batch is out")
        self.assertIn("DISPATCH second judges", buf.getvalue())
        self.assertEqual(len(st["sbatches"]), 1)
        # the worker writes a raw row: reproduced is NOT the model's to set
        audit.mk(c.p("second"))
        with io.open(c.p("second", "batch-C01.jsonl"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": "REQ-001", "kind": "COUNTEREXAMPLE",
                                 "command": "false", "path": "", "lines": "",
                                 "quote": "", "reproduced": False}) + u"\n")
        audit._second_ingest(c)
        m = audit.Merged(c)
        self.assertTrue(m.second["REQ-001"]["reproduced"])
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            flipped = audit._second_wave_agent(c, m, st)
        self.assertEqual(flipped, ["REQ-001"])
        self.assertEqual(audit.Merged(c).final("REQ-001")[0], "CONFLICT")


class FastLaneUntouchedTests(unittest.TestCase):
    def test_no_slow_stamp_runs_neither_pass(self):
        repo = _repo()
        self.addCleanup(shutil.rmtree, repo, True)
        out = tempfile.mkdtemp(prefix="audit-fast-out-")
        self.addCleanup(shutil.rmtree, out, True)
        with io.open(os.path.join(out, "config.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"repo_root": repo, "lane": "api", "tier": "std"}))
        c = audit.Ctx(out)
        self.assertFalse(audit.slow_stamp(c))

    def test_a_short_spec_with_no_slow_stamp_still_prints_pace_short(self):
        handoff = os.path.normpath(os.path.join(HERE, "..", "handoff.py"))
        root = _repo()
        self.addCleanup(shutil.rmtree, root, True)
        import subprocess
        spec = os.path.join(root, "req.md")
        with io.open(spec, "w", encoding="utf-8") as fh:
            fh.write(u"The button must save.\n" * 30)
        env = dict(os.environ, DOCGEN_STATE_DIR=os.path.join(root, "state"))
        proc = subprocess.run(
            [sys.executable, handoff, "open", "--self",
             "glm-requirements-code-audit", "--spec", spec],
            input=u"audit the code against the spec",
            capture_output=True, text=True, timeout=90, cwd=root, env=env)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PACE: short", proc.stdout)
        self.assertNotIn("PACE: slow", proc.stdout)
        self.assertNotIn("second judge", proc.stdout)


if __name__ == "__main__":
    unittest.main()
