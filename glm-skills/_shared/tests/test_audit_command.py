import contextlib
import glob
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "..", "glm-requirements-code-audit", "scripts")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(1, SCRIPTS)

import oc_harness
import audit

ITEMS = [
    {"id": "REQ-001", "text": "Login locks the account after 5 failed attempts",
     "strength": "MUST", "category": "auth", "stakes": "normal",
     "search_hints": ["login", "lockout"], "tags": []},
    {"id": "REQ-002", "text": "Export writes a CSV file",
     "strength": "MUST", "category": "export", "stakes": "normal",
     "search_hints": ["export", "csv"], "tags": []},
]


def _write_jsonl(path, rows):
    d = os.path.dirname(path)
    if not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + u"\n")


def _read_jsonl(path):
    with io.open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


class _FakeClient(object):
    calls = 0
    in_tok = 0
    out_tok = 0
    cache_read = 0

AUDIT_MD = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "glm-requirements-code-audit",
    "opencode",
    "commands",
    "glm-audit.md",
)


class TestAuditCommand(unittest.TestCase):
    def _render(self):
        with open(AUDIT_MD, "r") as fh:
            text = fh.read()
        return oc_harness.render_command(text, 1, "/home/user/.config/opencode/skills/glm-requirements-code-audit")

    def test_body_mentions_loading_the_skill_and_keeps_arguments(self):
        rendered = self._render()
        self.assertIn("Load the glm-requirements-code-audit skill", rendered)
        self.assertIn("$ARGUMENTS", rendered)

    def test_first_step_is_audit_brief_spec_no_bare_arguments_line(self):
        rendered = self._render()
        body_lines = rendered.split("\n")
        step_lines = [line for line in body_lines if "audit.py" in line]
        self.assertTrue(step_lines, "expected at least one audit.py reference")
        self.assertIn("audit.py brief --spec", step_lines[0])
        for line in body_lines:
            stripped = line.strip()
            self.assertNotEqual(
                stripped,
                "python3 {}/scripts/audit.py $ARGUMENTS".format(
                    "/home/user/.config/opencode/skills/glm-requirements-code-audit"
                ),
            )
            self.assertFalse(
                stripped.endswith("audit.py $ARGUMENTS"),
                "found bare 'audit.py $ARGUMENTS' line: {!r}".format(line),
            )

    def test_skill_dir_placeholder_fully_replaced(self):
        rendered = self._render()
        self.assertNotIn("{{SKILL_DIR}}", rendered)


class TestAuditCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        self.out = os.path.join(self.tmp, "audit")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _main(self, *argv):
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = audit.main(["--out", self.out] + list(argv))
        return rc, buf.getvalue()

    def _make_audit(self, lane, state=None):
        os.makedirs(self.out)
        cfg = {"version": audit.VERSION, "active": True, "repo_root": self.repo,
               "out_dir": self.out, "spec_files": [], "lang": "en", "lane": lane,
               "tier": "std", "threads": 8, "retrieval": "python"}
        with io.open(os.path.join(self.out, "config.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(cfg))
        _write_jsonl(os.path.join(self.out, "checklist.jsonl"), ITEMS)
        with io.open(os.path.join(self.out, "index.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"files": [], "symbols": {}, "routes": {}, "lines": {}}))
        with io.open(os.path.join(self.out, "repo-map.txt"), "w", encoding="utf-8") as fh:
            fh.write(u"files=0\n")
        if state is not None:
            with io.open(os.path.join(self.out, "state.json"), "w", encoding="utf-8") as fh:
                fh.write(json.dumps(state))

    def _state(self):
        with io.open(os.path.join(self.out, "state.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_setup_exit_code_is_nonzero_without_opencode(self):
        with mock.patch.object(oc_harness, "detect", return_value=None):
            rc, out = self._main("setup", "--harness", "opencode")
        self.assertIn("opencode not found", out)
        self.assertEqual(rc, 1)

    def _brief(self, text, *extra):
        return self._main("brief", "--spec-text", text, "--repo", self.repo,
                          "--lane", "solo", *extra)

    def test_brief_without_force_keeps_the_old_pasted_spec(self):
        self._brief("OLD requirement text")
        pasted = os.path.join(self.out, "spec", "pasted-requirements.txt")
        with self.assertRaises(SystemExit):
            self._brief("NEW requirement text")
        self.assertEqual(_read(pasted), "OLD requirement text\n")

    def test_brief_force_archives_before_writing_the_pasted_spec(self):
        self._brief("OLD requirement text")
        self._brief("NEW requirement text", "--force")
        pasted = os.path.join(self.out, "spec", "pasted-requirements.txt")
        self.assertEqual(_read(pasted), "NEW requirement text\n")
        self.assertIn("NEW requirement text",
                      _read(os.path.join(self.out, "spec", "spec.txt")))
        prev = glob.glob(self.out + ".prev-*")
        self.assertEqual(len(prev), 1)
        self.assertEqual(_read(os.path.join(prev[0], "spec", "pasted-requirements.txt")),
                         "OLD requirement text\n")

    def test_status_does_not_redispatch_verifiers_already_out(self):
        self._make_audit("agent")
        _write_jsonl(os.path.join(self.out, "findings", "batch-01.jsonl"), [
            {"id": "REQ-001", "status": "MISSING", "confidence": "low", "evidence": [],
             "searched": ["login"], "notes": "nothing found"}])
        _rc, first = self._main("status")
        self.assertIn("batch-V01", first)
        self.assertEqual(self._state()["vbatches"]["batch-V01"]["ids"], ["REQ-001"])
        _rc, second = self._main("status")
        self.assertNotIn("batch-V02", second)
        self.assertIn("waiting on 1 verifier result(s) already dispatched: REQ-001", second)
        _rc, third = self._main("status", "--redispatch")
        self.assertIn("batch-V02", third)

    def test_agent_lane_resume_skips_finished_batches(self):
        state = {"batches": {
            "batch-01": {"ids": ["REQ-001"], "wave": "A", "dispatched": "earlier"},
            "batch-02": {"ids": ["REQ-002"], "wave": "A", "dispatched": "earlier"}}}
        self._make_audit("agent", state)
        _write_jsonl(os.path.join(self.out, "findings", "batch-01.jsonl"), [
            {"id": "REQ-001", "status": "MATCHED", "confidence": "high", "evidence": [],
             "notes": "done"}])
        _rc, out = self._main("run", "--resume")
        self.assertFalse(os.path.exists(os.path.join(self.out, "batches", "batch-01.md")))
        batches = self._state()["batches"]
        self.assertEqual(batches["batch-01"]["ids"], ["REQ-001"])
        self.assertNotIn("batch-02", batches)
        self.assertEqual(batches["batch-03"]["ids"], ["REQ-002"])
        self.assertTrue(os.path.exists(os.path.join(self.out, "batches", "batch-03.md")))
        self.assertIn("resume: 1 finished batch(es) kept, 1 requirement(s) to re-batch", out)

    def test_api_resume_verifies_only_ids_without_a_verdict(self):
        self._make_audit("api")
        _write_jsonl(os.path.join(self.out, "findings.jsonl"), [
            {"id": "REQ-001", "status": "MISSING", "confidence": "low", "evidence": [],
             "searched": ["login"], "notes": "none", "passes": 2}])
        _write_jsonl(os.path.join(self.out, "verdicts.jsonl"), [
            {"id": "REQ-001", "verified_status": "MISSING", "agree": True,
             "confidence": "high", "evidence": [], "reason": "kept from the first run",
             "searched": ["login"]}])
        called = []

        def fake_judge(*args, **kw):
            it = args[4]
            return {"id": it["id"], "status": "MISSING", "confidence": "low",
                    "evidence": [], "searched": ["export"], "notes": "none", "passes": 2}

        def fake_verify(*args, **kw):
            it = args[4]
            called.append(it["id"])
            return {"id": it["id"], "verified_status": "MISSING", "agree": True,
                    "confidence": "high", "evidence": [], "reason": "new pass",
                    "searched": ["export"]}

        with mock.patch.object(audit, "_client", return_value=_FakeClient()), \
                mock.patch.object(audit, "judge_one", side_effect=fake_judge), \
                mock.patch.object(audit, "verify_one", side_effect=fake_verify):
            self._main("run", "--resume")
        self.assertEqual(sorted(called), ["REQ-002"])
        verdicts = dict((r["id"], r) for r in
                        _read_jsonl(os.path.join(self.out, "verdicts.jsonl")))
        self.assertEqual(sorted(verdicts), ["REQ-001", "REQ-002"])
        self.assertEqual(verdicts["REQ-001"]["reason"], "kept from the first run")


if __name__ == "__main__":
    unittest.main()
