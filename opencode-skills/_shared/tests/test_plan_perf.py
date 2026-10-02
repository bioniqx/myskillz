"""Speed optimizations in writing-plans/scripts/oc_plan_tool.py (spec WP11, WP13, WP14)."""
import argparse
import contextlib
import importlib.util
import io
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PLAN_TOOL = os.path.join(ROOT, "oc-writing-plans", "scripts", "oc_plan_tool.py")


def load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_perf", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pt = load_plan_tool()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class TmpDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="plan-perf-")
        os.makedirs(os.path.join(self.tmp, ".git"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class PickPatternsTest(TmpDirCase):
    def test_low_score_candidate_is_not_read(self):
        ten = "".join("line %d\n" % i for i in range(10))
        write(os.path.join(self.tmp, "src", "zzz.py"), ten)
        write(os.path.join(self.tmp, "tests", "test_widget.py"), ten)
        reads = []
        real_load = pt.load

        def counting_load(path):
            reads.append(os.path.relpath(path, self.tmp))
            return real_load(path)

        with mock.patch.object(pt, "load", counting_load), mock.patch.object(pt, "sh", return_value=""):
            got = pt.pick_patterns(["src/zzz.py", "tests/test_widget.py"], self.tmp, "the widget spec")
        self.assertEqual(got, ["tests/test_widget.py"])
        self.assertEqual(reads, [os.path.join("tests", "test_widget.py")])



class BriefConventionsTest(TmpDirCase):
    def run_brief(self, oc):
        write(os.path.join(self.tmp, "AGENTS.md"), "# Rules\nMARKER-RULE-42 always use tabs\n")
        ns = argparse.Namespace(rest=[], spec_lines=900, patterns=4, pattern_lines=700)
        out = io.StringIO()
        old = os.getcwd()
        os.chdir(self.tmp)
        try:
            with mock.patch.object(pt, "on_opencode", return_value=oc), \
                    mock.patch.object(pt, "sh", return_value=""), \
                    contextlib.redirect_stdout(out):
                rc = pt.cmd_brief(ns)
        finally:
            os.chdir(old)
        self.assertEqual(rc, 0)
        self.assertNotIn("brief partial", out.getvalue())
        return out.getvalue()

    def test_oc_harness_skips_inlining(self):
        text = self.run_brief(True)
        self.assertNotIn("MARKER-RULE-42", text)
        self.assertIn("conventions AGENTS.md (2 lines) - already in the agent context", text)

    def test_oc_harness_inlines_files_it_does_not_load(self):
        # the agent loads only the first root match of AGENTS.md / CLAUDE.md, never .claude/CLAUDE.md
        write(os.path.join(self.tmp, "CLAUDE.md"), "MARKER-CLAUDE-7 root rule\n")
        write(os.path.join(self.tmp, ".claude", "CLAUDE.md"), "MARKER-NESTED-9 nested rule\n")
        text = self.run_brief(True)
        self.assertNotIn("MARKER-RULE-42", text)
        self.assertIn("MARKER-CLAUDE-7", text)
        self.assertIn("MARKER-NESTED-9", text)

    def test_other_harness_still_inlines(self):
        text = self.run_brief(False)
        self.assertIn("MARKER-RULE-42", text)

    def test_brief_reports_agent_lane_with_no_key_or_model(self):
        text = self.run_brief(True)
        self.assertIn("lane: agent", text)
        for gone in ("models:", "API key", "api key"):
            self.assertNotIn(gone, text)


class ResumeTodoTest(TmpDirCase):
    def setUp(self):
        super().setUp()
        self.work = os.path.join(self.tmp, "work")
        self.body = os.path.join(self.work, "tasks", "T01.md")
        write(self.body, "**Files:**\n")
        write(self.body + ".ok", "1")
        self.cs = [{"id": "T01"}, {"id": "T02"}]

    def ids(self, resume):
        return [c["id"] for c in pt.resume_todo(self.cs, self.work, resume)]

    def test_stale_ok_is_rewritten(self):
        now = time.time()
        os.utime(self.body + ".ok", (now - 60, now - 60))
        os.utime(self.body, (now, now))
        self.assertEqual(self.ids(True), ["T01", "T02"])

    def test_fresh_ok_is_skipped(self):
        now = time.time()
        os.utime(self.body, (now - 60, now - 60))
        os.utime(self.body + ".ok", (now, now))
        self.assertEqual(self.ids(True), ["T02"])

    def test_without_resume_everything_is_written(self):
        self.assertEqual(self.ids(False), ["T01", "T02"])


if __name__ == "__main__":
    unittest.main()
