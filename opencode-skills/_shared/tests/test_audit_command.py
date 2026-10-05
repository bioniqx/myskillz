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
SCRIPTS = os.path.join(HERE, "..", "..", "oc-requirements-code-audit", "scripts")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(1, SCRIPTS)

import oc_harness
import oc_audit as audit

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


AUDIT_MD = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "oc-requirements-code-audit",
    "opencode",
    "commands",
    "oc-audit.md",
)


class TestAuditCommand(unittest.TestCase):
    def _render(self):
        with open(AUDIT_MD, "r") as fh:
            text = fh.read()
        return oc_harness.render_command(text, 2, "/home/user/.config/opencode/skills/oc-requirements-code-audit")

    def test_body_mentions_loading_the_skill_and_keeps_arguments(self):
        rendered = self._render()
        self.assertIn("Load the oc-requirements-code-audit skill", rendered)
        self.assertIn("$ARGUMENTS", rendered)

    def test_first_step_is_audit_brief_spec_no_bare_arguments_line(self):
        rendered = self._render()
        body_lines = rendered.split("\n")
        step_lines = [line for line in body_lines if "oc_audit.py" in line]
        self.assertTrue(step_lines, "expected at least one oc_audit.py reference")
        self.assertIn("oc_audit.py brief --spec", step_lines[0])
        for line in body_lines:
            stripped = line.strip()
            self.assertNotEqual(
                stripped,
                "python3 {}/scripts/oc_audit.py $ARGUMENTS".format(
                    "/home/user/.config/opencode/skills/oc-requirements-code-audit"
                ),
            )
            self.assertFalse(
                stripped.endswith("oc_audit.py $ARGUMENTS"),
                "found bare 'oc_audit.py $ARGUMENTS' line: {!r}".format(line),
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

    def _make_audit(self, state=None):
        os.makedirs(self.out)
        cfg = {"version": audit.VERSION, "active": True, "repo_root": self.repo,
               "out_dir": self.out, "spec_files": [], "lang": "en",
               "threads": 8, "retrieval": "python"}
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
        return self._main("brief", "--spec-text", text, "--repo", self.repo, *extra)

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
        self._make_audit()
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

    def _lane_cap_audit(self, pending, age=5):
        """10 requirements: batches 1..pending unanswered, the rest answered MISSING (verifier work)."""
        items = [dict(ITEMS[0], id="REQ-%03d" % i) for i in range(1, 11)]
        t = audit.now()
        batches = {"batch-%02d" % i: {"ids": [items[i - 1]["id"]], "wave": "A",
                                      "dispatched": t - (age if i <= pending else 5)}
                   for i in range(1, 11)}
        self._make_audit({"batches": batches})
        _write_jsonl(os.path.join(self.out, "checklist.jsonl"), items)
        for i in range(pending + 1, 11):
            self._answer_missing(i)

    def _answer_missing(self, i):
        _write_jsonl(os.path.join(self.out, "findings", "batch-%02d.jsonl" % i), [
            {"id": "REQ-%03d" % i, "status": "MISSING", "confidence": "low",
             "evidence": [], "searched": ["x"], "notes": "nothing found"}])

    def test_status_holds_verifiers_while_eight_pass1_lanes_are_in_flight(self):
        self._lane_cap_audit(8)
        _rc, out = self._main("status")
        self.assertNotIn("DISPATCH", out)
        self.assertIn("holding 2 row(s): lanes in flight 8 of 8", out)
        self.assertEqual(self._state()["vbatches"], {})

    def test_status_dispatches_at_most_the_free_lanes_then_the_rest_later(self):
        self._lane_cap_audit(3)
        _rc, out = self._main("status")
        self.assertEqual(len([l for l in out.splitlines() if "oc-rca-verifier" in l]), 5)
        self.assertEqual(len(self._state()["vbatches"]), 5)
        self.assertIn("holding 2 row(s): lanes in flight 8 of 8", out)
        for i in range(1, 4):  # the pass-1 lanes answer: 5 verifiers still out, 3 lanes free
            self._answer_missing(i)
        _rc, again = self._main("status")
        self.assertEqual(len([l for l in again.splitlines() if "oc-rca-verifier" in l]), 3)
        self.assertEqual(len(self._state()["vbatches"]), 8)
        self.assertIn("holding 2 row(s): lanes in flight 8 of 8", again)

    def test_status_hedges_only_into_free_lanes(self):
        self._lane_cap_audit(4, age=10 ** 6)
        with mock.patch.dict(os.environ, {"OC_MAX_LANES": "4"}):
            _rc, out = self._main("status")
        self.assertNotIn("DISPATCH hedges", out)
        self.assertEqual(self._state()["hedges"], {})
        with mock.patch.dict(os.environ, {"OC_MAX_LANES": "6"}):
            _rc, out = self._main("status")
        self.assertEqual(len([l for l in out.splitlines() if ".r2" in l and "oc-rca-inv" in l]), 2)
        self.assertEqual(len(self._state()["hedges"]), 2)
        self.assertIn("holding 8 row(s): lanes in flight 6 of 6", out)

    def test_plan_resume_skips_finished_batches(self):
        state = {"batches": {
            "batch-01": {"ids": ["REQ-001"], "wave": "A", "dispatched": "earlier"},
            "batch-02": {"ids": ["REQ-002"], "wave": "A", "dispatched": "earlier"}}}
        self._make_audit(state)
        _write_jsonl(os.path.join(self.out, "findings", "batch-01.jsonl"), [
            {"id": "REQ-001", "status": "MATCHED", "confidence": "high", "evidence": [],
             "notes": "done"}])
        _rc, out = self._main("plan", "--resume")
        self.assertFalse(os.path.exists(os.path.join(self.out, "batches", "batch-01.md")))
        batches = self._state()["batches"]
        self.assertEqual(batches["batch-01"]["ids"], ["REQ-001"])
        self.assertNotIn("batch-02", batches)
        self.assertEqual(batches["batch-03"]["ids"], ["REQ-002"])
        self.assertTrue(os.path.exists(os.path.join(self.out, "batches", "batch-03.md")))
        self.assertIn("resume: 1 finished batch(es) kept, 1 requirement(s) to re-batch", out)

    def test_plan_prints_one_background_row_per_batch(self):
        self._make_audit()
        _rc, out = self._main("plan")
        brief = os.path.join(self.out, "batches", "batch-01.md")
        want = oc_harness.dispatch_line("oc-rca-investigator", brief, "rca batch-01", 2,
                                        background=True)
        self.assertIn("  " + want, out.splitlines())
        self.assertNotIn("oc_harness.py run", out)
        self.assertTrue(os.path.exists(brief))
        self.assertIn("NEXT after the workers report: oc_audit.py status", out)

    def test_status_prints_the_verifier_wave_as_background_rows(self):
        self._make_audit()
        _write_jsonl(os.path.join(self.out, "findings", "batch-01.jsonl"), [
            {"id": "REQ-001", "status": "MISSING", "confidence": "low", "evidence": [],
             "searched": ["login"], "notes": "nothing found"}])
        _rc, out = self._main("status")
        brief = os.path.join(self.out, "batches", "batch-V01.md")
        want = oc_harness.dispatch_line("oc-rca-verifier", brief, "rca batch-V01", 2,
                                        background=True)
        self.assertIn("  " + want, out.splitlines())
        self.assertIn("PRELIMINARY FINDINGS to overturn:", _read(brief))

    def test_removed_options_and_commands_are_rejected(self):
        with mock.patch.dict(os.environ, {"HOME": self.tmp}):
            for argv in (["brief", "--spec-text", "x", "--lane", "solo"],
                         ["brief", "--spec-text", "x", "--tier", "std"],
                         ["plan", "--tier", "std"], ["run"], ["doctor", "--ping"],
                         ["setup", "--harness", "other"]):
                with self.assertRaises(SystemExit) as cm, \
                        contextlib.redirect_stderr(io.StringIO()):
                    audit.main(["--out", self.out] + argv)
                self.assertEqual(cm.exception.code, 2, argv)

    def test_source_has_no_direct_api_lane_code(self):
        src = _read(os.path.join(SCRIPTS, "oc_audit.py"))
        for word in ("TIERS", "FLASH", "detect_lane", "AGENT_ALIAS", "BASE_ENV",
                     "SETUP_ENV", "class Client", "_oc_lane_wave", "lane == "):
            self.assertNotIn(word, src)


def _spec_section(topic):
    return (u"## %s\n" % topic
            + (u"The system must log every %s event. " % topic) * 120 + u"\n")


SPEC_TEXT = u"# Spec\n\n" + _spec_section("export") + _spec_section("login")


class TestParseBatches(unittest.TestCase):
    def test_one_named_batch_per_section_in_document_order(self):
        batches = audit.parse_batches(SPEC_TEXT)
        self.assertEqual([name for name, _sec in batches], ["parse-01", "parse-02"])
        self.assertEqual(u"".join(sec for _name, sec in batches), SPEC_TEXT)
        self.assertTrue(batches[1][1].startswith(u"## login"))

    def test_empty_spec_gives_no_batches(self):
        self.assertEqual(audit.parse_batches(u""), [])


RCA_PARSER_MD = os.path.join(HERE, "..", "..", "oc-requirements-code-audit",
                             "opencode", "agents", "oc-rca-parser.md")


class TestRcaParserAgent(unittest.TestCase):
    def test_frontmatter_names_no_model_and_body_pins_the_reply(self):
        text = _read(RCA_PARSER_MD)
        self.assertTrue(text.startswith("---\n"))
        front = text.split("---\n")[1]
        keys = [line.split(":")[0].strip() for line in front.splitlines() if ":" in line]
        self.assertIn("description", keys)
        for banned in ("model", "effort", "variant", "reasoningEffort", "provider"):
            self.assertNotIn(banned, keys)
        self.assertIn("parse-NN done:", text)
        self.assertIn("absolute path", text)


def _fake_row(agent, prompt_path, description, major, background=False):
    return u"ROW %s %s %s bg=%s" % (agent, prompt_path, description, background)


class TestAuditParse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        self.out = os.path.join(self.tmp, "audit")
        os.makedirs(os.path.join(self.out, "spec"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        cfg = {"version": audit.VERSION, "active": True, "repo_root": self.repo,
               "out_dir": self.out, "spec_files": [], "lang": "en"}
        with io.open(os.path.join(self.out, "config.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(cfg))
        self._spec(SPEC_TEXT)
        self.brief1 = os.path.join(self.out, "batches", "parse-01.md")
        self.brief2 = os.path.join(self.out, "batches", "parse-02.md")
        self.out1 = os.path.join(self.out, "parse", "parse-01.jsonl")
        self.out2 = os.path.join(self.out, "parse", "parse-02.jsonl")
        self.draft = os.path.join(self.out, "checklist.draft.jsonl")

    def _spec(self, text):
        with io.open(os.path.join(self.out, "spec", "spec.txt"), "w", encoding="utf-8") as fh:
            fh.write(text)

    def _parse(self):
        buf, err = io.StringIO(), io.StringIO()
        with mock.patch.object(oc_harness, "dispatch_line", side_effect=_fake_row) as row, \
                contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = audit.main(["--out", self.out, "parse"])
        self.assertEqual(rc, 0)
        return row, buf.getvalue()

    def _calls(self, *pairs):
        return [mock.call("oc-rca-parser", brief, "rca " + name, 2, background=True)
                for name, brief in pairs]

    def test_first_call_writes_one_brief_per_section_and_prints_parser_rows(self):
        row, out = self._parse()
        self.assertEqual(row.call_args_list,
                         self._calls(("parse-01", self.brief1), ("parse-02", self.brief2)))
        self.assertIn(u"ROW oc-rca-parser %s rca parse-01 bg=True" % self.brief1, out)
        self.assertIn(u"ROW oc-rca-parser %s rca parse-02 bg=True" % self.brief2, out)
        brief = _read(self.brief2)
        self.assertIn(self.out2, brief)
        self.assertTrue(os.path.isabs(self.out2))
        self.assertIn("Section 2 of 2. Use ids REQ-02001, REQ-02002", brief)
        self.assertIn("## login", brief)
        self.assertIn("search_hints decide whether the audit finds the code", brief)
        self.assertNotIn("Reply with JSON Lines", brief)
        self.assertIn("NEXT:", out)
        self.assertIn("oc_audit.py parse", out)
        self.assertFalse(os.path.exists(self.draft))

    def test_parser_wave_holds_at_most_eight_rows(self):
        self._spec(u"\n\n".join(u"## s%d\n\n%s" % (i, u"The system must log. " * 300)
                                 for i in range(12)))
        row, out = self._parse()
        self.assertEqual(len(row.call_args_list), 8)
        self.assertIn("more section(s) wait", out)

    def test_second_call_dispatches_only_the_sections_without_an_output_file(self):
        self._parse()
        _write_jsonl(self.out1, [])
        row, _out = self._parse()
        self.assertEqual(row.call_args_list, self._calls(("parse-02", self.brief2)))
        self.assertFalse(os.path.exists(self.draft))

    def test_call_after_the_wave_merges_lane_files_into_the_draft(self):
        self._parse()
        _write_jsonl(self.out1, [
            {"id": "REQ-01001", "text": "Every export event is logged.", "strength": "MUST",
             "stakes": "high", "search_hints": ["export", "audit_log"], "tags": []},
            {"id": "REQ-01002", "text": "Export writes a CSV file", "strength": "MUST",
             "search_hints": ["export", "csv"], "tags": []}])
        _write_jsonl(self.out2, [
            {"id": "REQ-02001", "text": "every export event is logged", "strength": "MUST",
             "search_hints": ["export", "log"]},
            {"id": "REQ-02002", "text": "Every login event is logged", "strength": "SHOULD",
             "search_hints": ["login", "audit_log"]}])
        row, out = self._parse()
        row.assert_not_called()
        rows = _read_jsonl(self.draft)
        self.assertEqual([r["id"] for r in rows], ["REQ-001", "REQ-002", "REQ-003"])
        self.assertEqual([r["text"] for r in rows],
                         ["Every export event is logged.", "Export writes a CSV file",
                          "Every login event is logged"])
        self.assertEqual(rows[2]["tags"], [])
        self.assertEqual(rows[2]["stakes"], "normal")
        self.assertIn("draft: 3 requirements", out)
        self.assertIn("NEXT:", out)
        self.assertIn("oc_audit.py parse --accept", out)

    def test_changed_section_drops_its_stale_output_and_dispatches_again(self):
        self._parse()
        _write_jsonl(self.out1, [])
        _write_jsonl(self.out2, [])
        self._spec(SPEC_TEXT.replace("login", "logout"))
        row, _out = self._parse()
        self.assertEqual(row.call_args_list, self._calls(("parse-02", self.brief2)))
        self.assertTrue(os.path.exists(self.out1))
        self.assertFalse(os.path.exists(self.out2))
        self.assertIn("## logout", _read(self.brief2))


if __name__ == "__main__":
    unittest.main()
