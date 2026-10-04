"""The fork's plan tool must lint and brief the way the original plan tool does."""
import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
HP = HERE.parent
TOOL = HP / "scripts" / "plan_tool.py"
FAKE = HERE / "fake_opencode.py"
_spec = importlib.util.spec_from_file_location("hp_plan_tool_port", str(TOOL))
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

FENCE = "`" * 3
PLAN_TEXT = "\n".join([
    "# Demo Implementation Plan", "", "**Goal:** Two helpers.", "", "## Contracts", "",
    "#### T01: First", "- Files: `src/one.py`", "- Produces: `def one() -> int`", "",
    "#### T02: Second", "- Files: `src/two.py`", "- Produces: `def two() -> int`", ""])


def body(code="x = 1", add="git add src/a.py", commit='git commit -m "feat: a"'):
    return "\n".join([
        "**Files:**", "- Create: `src/a.py`", "",
        "- [ ] **Step 1: Write**", "", FENCE + "python", code, FENCE, "",
        "- [ ] **Step 2: Commit**", "", FENCE + "bash", add, commit, FENCE]) + "\n"


CONTRACT = {"id": "T01", "files": ["src/a.py"], "produces": []}


def lint(text):
    return M.lint_body(CONTRACT, text, [], "T01", None, ())[0]


class TierModelTests(unittest.TestCase):
    def test_every_writer_tier_is_sonnet(self):
        self.assertEqual(M.TIER_MODEL, {"light": "sonnet", "std": "sonnet", "deep": "sonnet"})


    def test_docs_do_not_claim_an_opus_writer(self):
        for name in ("README.md", "SKILL.md"):
            text = (HP / name).read_text(encoding="utf-8")
            self.assertNotIn("Claude opus", text, name)
            self.assertNotIn("keeps it on Claude opus", text, name)


class ScanPortTests(unittest.TestCase):
    def test_allow_hit_stem_and_regex(self):
        self.assertTrue(M.allow_hit("subagents", ["subagent"]))
        self.assertTrue(M.allow_hit("Claude", ["re:Cl.*"]))
        self.assertFalse(M.allow_hit("Claude", ["re:Cl"]))
        self.assertFalse(M.allow_hit("Claude", ["todo"]))

    def test_scan_honours_stems_and_regexes(self):
        self.assertEqual(M.scan("The subagents run.\n", ["subagent"], "t"), [])
        self.assertEqual(M.scan("The subagents run.\n", ["re:subagents"], "t"), [])
        self.assertEqual(len(M.scan("The subagents run.\n", ["agents"], "t")), 1)


class LintPortTests(unittest.TestCase):
    def test_clean_body_has_no_errors(self):
        self.assertEqual(lint(body()), [])

    def test_commit_all_flag_is_rejected(self):
        errs = lint(body(commit='git commit -am "feat: a"'))
        self.assertTrue(any("stages every tracked change" in e for e in errs), errs)

    def test_commit_without_add_is_rejected(self):
        errs = lint(body(add=""))
        self.assertTrue(any("has no earlier `git add`" in e for e in errs), errs)


class ContractsPortTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(os.path.realpath(tempfile.mkdtemp(prefix="hp-port-")))
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.repo = self.tmp / "repo"
        (self.repo / ".git").mkdir(parents=True)
        (self.tmp / "home").mkdir()
        self.plan = self.repo / "docs" / "plans" / "plan.md"
        self.work = self.plan.parent / ".hybrid-work" / "plan"
        self.write(self.plan, PLAN_TEXT)
        routing = json.loads((HP / "routing.default.json").read_text(encoding="utf-8"))
        routing["preset"] = "claude"
        self.write(self.tmp / "routing.json", json.dumps(routing))
        tier = {"listed": True, "ping": "ok", "note": "", "down": None}
        doctor = {"t": "2026-09-28T00:00:00Z", "ok": True, "version": "2.0.18", "binary": str(FAKE), "tiers": {
            "std": dict(tier, model="zai-coding-plan/glm-5.3", variant="high"),
            "lite": dict(tier, model="zai-coding-plan/glm-5.3-flash", variant="low")}}
        self.write(self.tmp / "doctor.json", json.dumps(doctor))
        self.env = dict(os.environ)
        self.env.pop("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", None)
        self.env.pop("HYBRID_OPENCODE_STD", None)
        self.env.pop("HYBRID_OPENCODE_LITE", None)
        self.env.pop("HYBRID_OPENCODE_MAX_PARALLEL", None)
        self.env.update({
            "HOME": str(self.tmp / "home"),
            "XDG_DATA_HOME": str(self.tmp / "xdg"),
            "HYBRID_WRITING_PLANS_ROUTING": str(self.tmp / "routing.json"),
            "HYBRID_WRITING_PLANS_DOCTOR_CACHE": str(self.tmp / "doctor.json"),
            "HYBRID_WRITING_PLANS_TELEMETRY": str(self.tmp / "lanes.jsonl"),
            "HYBRID_WRITING_PLANS_OC_BIN": str(FAKE),
            "PYTHONDONTWRITEBYTECODE": "1",
        })

    def write(self, path, text):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def contracts(self):
        p = subprocess.run([sys.executable, str(TOOL), "contracts", str(self.plan), "--preset", "claude"],
                           cwd=str(self.repo), env=self.env, capture_output=True, text=True, timeout=120)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        return p.stdout

    def test_contract_hashes_cover_the_producers_a_task_depends_on(self):
        cs = [{"id": "T01", "text": "one", "deps_all": []}, {"id": "T02", "text": "two", "deps_all": ["T01"]}]
        before = M.contract_hashes(cs)
        cs[0]["text"] = "changed"
        after = M.contract_hashes(cs)
        self.assertNotEqual(before["T01"], after["T01"])
        self.assertNotEqual(before["T02"], after["T02"])
        cs[1]["text"] = "two!"
        self.assertEqual(after["T01"], M.contract_hashes(cs)["T01"])

    def test_reviewer_brief_inlines_the_task_bodies(self):
        cs, _ = M.parse_contracts(PLAN_TEXT)
        M.analyze(cs, None, None)
        self.write(self.work / "tasks" / "T01.md", "**Files:**\n- Create: `src/one.py`\nBODY-MARKER-LINE\n")
        brief = M.reviewer_brief(str(self.plan), PLAN_TEXT, cs[:1], str(self.work), None, str(self.repo))
        self.assertIn("    3| BODY-MARKER-LINE", brief)

    def test_reviewer_brief_forbids_opencode_in_task_bodies(self):
        cs, _ = M.parse_contracts(PLAN_TEXT)
        M.analyze(cs, None, None)
        self.write(self.work / "tasks" / "T01.md", "**Files:**\n- Create: `src/one.py`\n")
        brief = M.reviewer_brief(str(self.plan), PLAN_TEXT, cs[:1], str(self.work), None, str(self.repo))
        self.assertIn("must not name opencode", brief)
        self.assertIn("remove any mention", brief)

    def test_copied_prompts_stay_byte_identical_and_changelog_is_honest(self):
        self.assertNotIn("opencode", (HP / "agents" / "hybrid-plan-task-writer.md").read_text(encoding="utf-8").lower())
        log = (HP / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertNotIn("the Claude writer agent and the reviewer brief now forbid", log)

    def test_setup_refreshes_a_stale_agent_file(self):
        agent_path = self.tmp / "home" / ".claude" / "agents" / "hybrid-plan-task-writer.md"
        self.write(agent_path, "old agent text\n")
        with mock.patch.dict(os.environ, {"HOME": str(self.tmp / "home")}), contextlib.redirect_stdout(io.StringIO()):
            rc = M.cmd_setup(argparse.Namespace(scope="user", apply=True))
        self.assertEqual(rc, 0)
        want = M.load(M.AGENT_TEMPLATE).replace("__PLAN_TOOL__", M.qtool())
        self.assertEqual(agent_path.read_text(encoding="utf-8"), want)

    def test_contracts_does_not_redispatch_a_group_that_already_has_ok(self):
        out = self.contracts()
        self.assertIn("briefs/T01.md", out)
        self.assertIn("briefs/T02.md", out)
        for tid in ("T01", "T02"):
            self.write(self.work / "tasks" / (tid + ".md"), "x")
        self.write(self.work / "tasks" / "T01.md.ok", "1")
        out = self.contracts()
        self.assertNotIn("briefs/T01.md", out)
        self.assertIn("briefs/T02.md", out)
        self.write(self.work / "tasks" / "T02.md.ok", "1")
        out = self.contracts()
        self.assertNotIn("briefs/T02.md", out)
        self.assertIn("NOTHING TO DISPATCH", out)


if __name__ == "__main__":
    unittest.main()
