"""Tests for hp_briefs: oc brief head, body markers and repair message."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hp_briefs  # noqa: E402
import plan_tool  # noqa: E402


class TempHomeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hp-briefs-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = {"HOME": self.tmp,
               "HYBRID_WRITING_PLANS_ROUTING": os.path.join(self.tmp, "routing.json"),
               "HYBRID_WRITING_PLANS_DOCTOR_CACHE": os.path.join(self.tmp, "doctor.json"),
               "HYBRID_WRITING_PLANS_TELEMETRY": os.path.join(self.tmp, "lanes.jsonl")}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)


class TestHead(TempHomeCase):
    def test_rules_text_is_body_format_and_rules_of_task_writer_prompt(self):
        tmpl = plan_tool.load(os.path.join(plan_tool.SKILL_DIR, "task-writer-prompt.md"))
        text = hp_briefs.rules_text()
        self.assertEqual(text, tmpl[tmpl.index("## Body format"):].strip() + "\n")
        self.assertTrue(text.startswith("## Body format"))
        self.assertIn("## Rules", text)
        self.assertNotIn("## Procedure", text)
        self.assertNotIn("LINT:", text)

    def test_marker_constants(self):
        self.assertEqual(hp_briefs.MARK_BEGIN, "@@@ BEGIN ")
        self.assertEqual(hp_briefs.MARK_END, "@@@ END ")

    def test_oc_head_fills_tasks_markers_and_rules(self):
        head = hp_briefs.oc_head(["T03", "T04"])
        self.assertIn("T03, T04", head)
        self.assertIn("@@@ BEGIN T03\n", head)
        self.assertIn("@@@ END T04", head)
        self.assertIn(hp_briefs.rules_text().strip(), head)
        for ph in ("{TASKS}", "{MARKERS}", "{RULES}", "{OUT}", "{LINT}"):
            self.assertNotIn(ph, head)
        self.assertNotIn("LINT:", head)
        self.assertNotIn("## Procedure", head)

    def test_prompt_file_holds_head_and_placeholders_only(self):
        raw = plan_tool.load(os.path.join(plan_tool.SKILL_DIR, "oc-writer-prompt.md"))
        for ph in ("{TASKS}", "{MARKERS}", "{RULES}"):
            self.assertIn(ph, raw)
        self.assertNotIn("## Rules", raw)
        self.assertNotIn("## Body format", raw)


class TestOcBrief(TempHomeCase):
    def make_plan(self):
        repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(repo, ".git"))
        os.makedirs(os.path.join(repo, "docs"))
        plan_path = os.path.join(repo, "docs", "demo.md")
        lines = [
            "# Demo plan",
            "",
            "**Goal:** demo.",
            "",
            "## Global Constraints",
            "",
            "- Stdlib only.",
            "",
            "## Contracts",
            "",
            "#### T01: First",
            "- Files: `pkg/a.py`",
            "- Produces: `def a() -> int`",
            "",
            "#### T02: Second",
            "- Depends: T01",
            "- Files: `pkg/b.py`",
            "- Consumes: `def a() -> int`",
            "",
        ]
        plan = "\n".join(lines) + "\n"
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write(plan)
        return repo, plan_path, plan

    def test_oc_brief_is_oc_head_plus_writer_brief_tail(self):
        repo, plan_path, plan = self.make_plan()
        cs, errs = plan_tool.parse_contracts(plan)
        self.assertEqual(errs, [])
        errs, _ = plan_tool.analyze(cs, None, repo)
        self.assertEqual(errs, [])
        cmap = {c["id"]: c for c in cs}
        work = plan_tool.default_work(plan_path)
        full = plan_tool.writer_brief(plan_path, plan, [cmap["T02"]], cmap, work, None, repo, [])
        brief = hp_briefs.oc_brief(plan_path, plan, [cmap["T02"]], cmap, work, None, repo, [])
        self.assertEqual(brief, hp_briefs.oc_head(["T02"]) + "\n\n" + full[full.index("## Plan header"):])
        self.assertIn("## Contract T02 (locked)", brief)
        self.assertIn("Consumes `def a() -> int`", brief)
        self.assertIn("## Global Constraints", brief)
        self.assertNotIn("LINT:", brief)
        self.assertNotIn("OUT (one file per task)", brief)
        self.assertEqual(brief.count("## Body format"), 1)
        self.assertTrue(brief.endswith("\n"))


class TestSplitBodies(unittest.TestCase):
    def test_extracts_only_group_ids_and_ignores_outside_text(self):
        text = "\n".join([
            "Here are the bodies.",
            "@@@ BEGIN T03",
            "**Files:**",
            "- Create: `a.py`",
            "@@@ END T03",
            "noise between",
            "@@@ BEGIN T09",
            "foreign body",
            "@@@ END T09",
            "  @@@ BEGIN T04  ",
            "",
            "body four",
            "",
            "@@@ END T04",
            "Done.",
        ])
        out = hp_briefs.split_bodies(text, ["T03", "T04"])
        self.assertEqual(list(out), ["T03", "T04"])
        self.assertEqual(out["T03"], "**Files:**\n- Create: `a.py`\n")
        self.assertEqual(out["T04"], "body four\n")

    def test_unterminated_empty_and_abandoned_blocks_are_missing(self):
        text = "\n".join([
            "@@@ BEGIN T01", "first try",
            "@@@ BEGIN T02", "second", "@@@ END T02",
            "@@@ BEGIN T03", "", "@@@ END T03",
            "@@@ BEGIN T04", "never closed",
        ])
        out = hp_briefs.split_bodies(text, ["T01", "T02", "T03", "T04"])
        self.assertEqual(out, {"T02": "second\n"})

    def test_unwraps_a_fenced_body_and_keeps_inner_fences(self):
        text = "\n".join([
            "@@@ BEGIN T05",
            "````markdown",
            "**Files:**",
            "```bash",
            "git commit -m \"x\"",
            "```",
            "````",
            "@@@ END T05",
        ])
        out = hp_briefs.split_bodies(text, ["T05"])
        self.assertEqual(out["T05"], "**Files:**\n```bash\ngit commit -m \"x\"\n```\n")

    def test_order_follows_task_ids_and_last_complete_copy_wins(self):
        text = "\n".join([
            "@@@ BEGIN T02", "old", "@@@ END T02",
            "@@@ BEGIN T01", "one", "@@@ END T01",
            "@@@ BEGIN T02", "new", "@@@ END T02",
        ])
        out = hp_briefs.split_bodies(text, ["T01", "T02"])
        self.assertEqual(list(out), ["T01", "T02"])
        self.assertEqual(out["T02"], "new\n")

    def test_empty_text(self):
        self.assertEqual(hp_briefs.split_bodies("", ["T01"]), {})


class TestRepairMessage(unittest.TestCase):
    def test_lists_errors_and_missing_in_id_order(self):
        errors = {"T05": ["T05: no commit step"], "T03": ["T03: e%d" % i for i in range(30)]}
        msg = hp_briefs.repair_message(errors, ["T04"])
        self.assertIn("only these tasks: T03, T04, T05.", msg)
        self.assertIn("ERR  T05: no commit step", msg)
        self.assertIn("T04: missing from your reply", msg)
        self.assertEqual(msg.count("ERR  T03: "), 25)
        self.assertIn("ERR  T03: e24\n", msg)
        self.assertNotIn("ERR  T03: e25", msg)
        self.assertIn("(+5 more errors not shown)", msg)
        self.assertIn("@@@ BEGIN T04\n", msg)
        self.assertIn("@@@ END T05", msg)
        self.assertIn("Do not write files or run commands.", msg)
        self.assertLess(msg.index("T03: 30 lint error(s)"), msg.index("T04: missing"))
        self.assertLess(msg.index("T04: missing"), msg.index("T05: 1 lint error(s)"))
        self.assertTrue(msg.endswith("\n"))

    def test_missing_wins_over_errors_and_empty_lists_are_ignored(self):
        msg = hp_briefs.repair_message({"T01": ["T01: bad"], "T02": []}, ["T01"])
        self.assertIn("only these tasks: T01.", msg)
        self.assertIn("T01: missing from your reply", msg)
        self.assertNotIn("ERR  T01: bad", msg)
        self.assertNotIn("T02", msg)

    def test_nothing_to_repair(self):
        self.assertEqual(hp_briefs.repair_message({}, []), "")
        self.assertEqual(hp_briefs.repair_message({"T01": []}, []), "")
