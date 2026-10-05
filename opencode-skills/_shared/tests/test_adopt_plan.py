import argparse
import contextlib
import importlib.util
import inspect
import io
import json
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "..", "..", "oc-writing-plans")
PLAN_TOOL = os.path.join(SKILL, "scripts", "oc_plan_tool.py")
AGENT_NAMES = ("oc-plan-task-writer", "oc-plan-task-writer-deep", "oc-plan-reviewer")
MAJOR = 2


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_under_test", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()


def _read(*parts):
    with open(os.path.join(SKILL, *parts), encoding="utf-8") as fh:
        return fh.read()


def _frontmatter(name):
    text = _read("opencode", "agents", name + ".md")
    head = text.split("---\n")[1]
    fields = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, text


def _plan_text(n, deep=()):
    rows = ["# Demo Plan", "", "**Goal:** demo.", "", "## Global Constraints", "", "- none", "",
            "## Contracts", ""]
    for i in range(1, n + 1):
        tid = "T%02d" % i
        rows += ["#### %s: part %d" % (tid, i), "- Depends: none", "- Files: `src/p%02d.py`" % i,
                 "- Produces: `def f%02d() -> int`" % i, "- Spec: L1-1",
                 "- Tier: %s" % ("deep" if tid in deep else "std"), ""]
    return "\n".join(rows) + "\n"


def _run(fn, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args)
    return rc, buf.getvalue()


class RemovedRoutingTests(unittest.TestCase):
    GONE = ("zai_client", "call_model", "model_for", "find_credentials", "protocol_for",
            "KEY_ENV", "DEFAULT_BASE", "Budget", "pmap", "agent_cap", "workers_cap",
            "detect_harness", "run_review", "pick_risky", "lint_one", "extract_body")

    def test_direct_api_symbols_are_gone(self):
        for name in self.GONE:
            self.assertFalse(hasattr(plan_tool, name), name)

    def _exit_code(self, argv):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                plan_tool.main(argv)
        return cm.exception.code

    def test_removed_flags_are_rejected(self):
        for argv in (["build", "plan.md", "--lane", "api"], ["build", "plan.md", "--repairs", "1"],
                     ["build", "plan.md", "--max-tokens", "9"], ["setup", "--harness", "opencode"],
                     ["doctor", "--ping"]):
            self.assertEqual(self._exit_code(argv), 2, argv)


class AgentForTests(unittest.TestCase):
    def test_deep_tier_selects_the_deep_writer(self):
        self.assertEqual(plan_tool.agent_for("deep"), "oc-plan-task-writer-deep")

    def test_light_and_std_tiers_select_the_plain_writer(self):
        for tier in ("light", "std"):
            self.assertEqual(plan_tool.agent_for(tier), "oc-plan-task-writer")

    def test_signature_takes_only_the_tier(self):
        self.assertEqual(list(inspect.signature(plan_tool.agent_for).parameters), ["tier"])


class CommandSignatureTests(unittest.TestCase):
    def test_build_review_and_setup_take_one_namespace_arg(self):
        for name in ("cmd_build", "cmd_review", "cmd_setup"):
            fn = getattr(plan_tool, name)
            self.assertEqual(list(inspect.signature(fn).parameters), ["a"], name)


class AgentFileTests(unittest.TestCase):
    def test_bundled_agent_is_rendered_for_major_two(self):
        with mock.patch.object(plan_tool.oc_harness, "render_agent", return_value="RENDERED") as ren:
            text = plan_tool.agent_file("oc-plan-task-writer-deep")
        self.assertEqual(text, "RENDERED")
        source, major = ren.call_args[0]
        self.assertEqual(major, MAJOR)
        self.assertIn("deep-tier", source)

    def test_unknown_agent_is_none(self):
        self.assertIsNone(plan_tool.agent_file("no-such-agent"))


class BundledAgentTests(unittest.TestCase):
    def test_no_agent_sets_model_effort_or_variant(self):
        for name in AGENT_NAMES:
            fm, _ = _frontmatter(name)
            for key in ("model", "effort", "variant", "reasoningEffort"):
                self.assertNotIn(key, fm, name)

    def test_agents_keep_write_access_and_24_steps(self):
        for name in AGENT_NAMES:
            fm, _ = _frontmatter(name)
            self.assertEqual(fm["access"], "write", name)
            self.assertEqual(fm["bash"], "true", name)
            self.assertEqual(fm["steps"], "24", name)
            self.assertTrue(fm["description"], name)

    def test_deep_writer_keeps_its_extra_rule(self):
        _, text = _frontmatter("oc-plan-task-writer-deep")
        self.assertIn("Deep tier: check every consumed signature", text)
        self.assertIn("T07 OK", text)

    def test_reviewer_reports_verdicts(self):
        _, text = _frontmatter("oc-plan-reviewer")
        for word in ("APPROVED", "FIXED", "FAIL"):
            self.assertIn(word, text)


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        for p in (mock.patch.dict(os.environ, {"HOME": self.home}),
                  mock.patch.object(plan_tool.oc_harness, "render_agent",
                                    side_effect=lambda text, major: text)):
            p.start()
            self.addCleanup(p.stop)

    def run_setup(self, apply):
        with mock.patch.object(plan_tool.oc_harness, "install",
                               return_value=["oc-plan-task-writer.md"]) as inst:
            rc, out = _run(plan_tool.cmd_setup, argparse.Namespace(apply=apply))
        self.assertEqual(rc, 0, out)
        return out, inst

    def test_dry_run_lists_every_agent_and_installs_nothing(self):
        out, inst = self.run_setup(False)
        inst.assert_not_called()
        for name in AGENT_NAMES:
            self.assertIn(name + ".md", out)
        self.assertIn("Re-run with --apply", out)

    def test_apply_installs_through_the_shared_installer(self):
        out, inst = self.run_setup(True)
        inst.assert_called_once_with(plan_tool.SKILL_DIR, MAJOR, self.home)
        self.assertIn("OK written", out)

    def test_dry_run_discloses_global_skill_folder_and_command_files(self):
        # no install mock: the dry-run must not touch anything, only disclose
        rc, out = _run(plan_tool.cmd_setup, argparse.Namespace(apply=False))
        self.assertEqual(rc, 0, out)
        skill_dst = os.path.join(self.home, ".config", "opencode", "skills", "oc-writing-plans")
        cmd_dst = os.path.join(self.home, ".config", "opencode", "commands", "oc-plan.md")
        lines = out.splitlines()
        self.assertTrue(any("replace" in l and skill_dst in l for l in lines), out)
        self.assertTrue(any("overwrite" in l and cmd_dst in l for l in lines), out)
        self.assertFalse(os.path.exists(skill_dst))
        self.assertIn("NEXT:", out)

    def test_up_to_date_agents_need_no_install(self):
        adir = os.path.join(self.home, ".config", "opencode", "agents")
        os.makedirs(adir)
        for name in AGENT_NAMES:
            with open(os.path.join(adir, name + ".md"), "w", encoding="utf-8") as fh:
                fh.write(plan_tool.agent_file(name))
        out, inst = self.run_setup(True)
        inst.assert_not_called()
        self.assertIn("OK setup already complete", out)


class DoctorTests(unittest.TestCase):
    def doctor(self, installed):
        with mock.patch.object(plan_tool, "agent_installed", return_value=installed), \
                mock.patch.object(plan_tool, "on_opencode", return_value=True):
            return _run(plan_tool.cmd_doctor, argparse.Namespace())

    def test_missing_agents_exit_one_and_point_to_setup(self):
        rc, out = self.doctor(None)
        self.assertEqual(rc, 1, out)
        self.assertIn("missing", out)
        self.assertIn("setup --apply", out)

    def test_installed_agents_exit_zero_with_a_next_line(self):
        rc, out = self.doctor("/fake/agents")
        self.assertEqual(rc, 0, out)
        self.assertIn("NEXT:", out)


class SkillFilesTests(unittest.TestCase):
    def _head(self):
        return _read("SKILL.md").split("---\n")[1]

    def test_skill_frontmatter_holds_only_name_description_metadata(self):
        keys = [l.split(":")[0] for l in self._head().splitlines() if l and not l.startswith(" ")]
        self.assertEqual(keys, ["name", "description", "metadata"])

    def test_skill_description_fits_1024_characters(self):
        line = next(l for l in self._head().splitlines() if l.startswith("description:"))
        self.assertLessEqual(len(line[len("description:"):].strip()), 1024)

    def test_reviewer_prompt_matches_agent_reply_format(self):
        text = _read("plan-reviewer-prompt.md")
        self.assertIn("APPROVED", text)
        self.assertNotIn("Status: Approved", text)

    def test_body_rules_name_the_word_the_linter_rejects(self):
        self.assertIn("OpenCode", _read("references", "body-rules.md"))


class WriterGroupingTests(unittest.TestCase):
    def test_group_count_is_ceil_of_quarter(self):
        for n, want in ((0, 0), (1, 1), (4, 1), (5, 2), (10, 3), (32, 8), (40, 10)):
            self.assertEqual(plan_tool.writer_group_count(n), want, n)

    def test_cap_groups_splits_oversized_groups(self):
        self.assertEqual(plan_tool.cap_groups([[1, 2, 3, 4, 5, 6], [7]]), [[1, 2, 3, 4], [5, 6], [7]])

    def test_lane_width_default_and_env(self):
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": ""}):
            self.assertEqual(plan_tool.lane_width(), 8)
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "3"}):
            self.assertEqual(plan_tool.lane_width(), 3)
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "x"}):
            self.assertEqual(plan_tool.lane_width(), 8)
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "64"}):
            self.assertEqual(plan_tool.lane_width(), 8)
        self.assertEqual(plan_tool.MAX_WORKERS, 8)

    def test_on_opencode_asks_shared_harness_with_script_path(self):
        with mock.patch.object(plan_tool.oc_harness, "harness", return_value="opencode") as h:
            self.assertTrue(plan_tool.on_opencode())
        h.assert_called_once_with(plan_tool.TOOL)
        with mock.patch.object(plan_tool.oc_harness, "harness", return_value="other"):
            self.assertFalse(plan_tool.on_opencode())
        with mock.patch.object(plan_tool.oc_harness, "harness", side_effect=OSError("boom")):
            self.assertFalse(plan_tool.on_opencode())


class OpenCodeDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patches = [mock.patch.object(plan_tool, "agent_installed", return_value="/fake/agents"),
                   mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "8"})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.plan = os.path.join(self.tmp, "plan.md")

    def write_plan(self, n, deep=()):
        with open(self.plan, "w", encoding="utf-8") as fh:
            fh.write(_plan_text(n, deep))

    def contracts(self, n, deep=()):
        self.write_plan(n, deep)
        rc, out = _run(plan_tool.cmd_contracts,
                       argparse.Namespace(plan=self.plan, spec=None, allow=[], workers=None))
        self.assertEqual(rc, 0, out)
        work = plan_tool.default_work(self.plan)
        with open(os.path.join(work, "work.json"), encoding="utf-8") as fh:
            info = json.load(fh)
        return out, work, info

    def build(self, resume=False, thorough=False):
        ns = argparse.Namespace(plan=self.plan, spec=None, allow=[], workers=None,
                                resume=resume, thorough=thorough)
        rc, out = _run(plan_tool.cmd_build, ns)
        self.assertEqual(rc, 0, out)
        return out

    def expected(self, agent, work, sub, gid, description):
        return plan_tool.oc_harness.dispatch_line(agent, os.path.join(work, sub, gid + ".md"),
                                                  description, MAJOR)

    def test_ten_tasks_make_three_groups_of_at_most_four(self):
        _, _, info = self.contracts(10)
        sizes = [len(v) for v in info["groups"].values()]
        self.assertEqual(len(sizes), 3)
        self.assertTrue(all(s <= 4 for s in sizes), sizes)
        self.assertEqual(info["groups"]["W01"], ["T01", "T02", "T03", "T04"])

    def test_dispatch_uses_writer_agent(self):
        out, work, _ = self.contracts(10)
        self.assertIn(self.expected("oc-plan-task-writer", work, "briefs", "W01", "plan T01-T04"), out)
        self.assertIn(self.expected("oc-plan-task-writer", work, "briefs", "W03", "plan T09-T10"), out)
        for foreign in ("general-purpose", "subagent_type="):
            self.assertNotIn(foreign, out)

    def test_deep_group_goes_to_deep_writer(self):
        out, work, info = self.contracts(5, deep=("T05",))
        self.assertEqual(info["groups"]["W02"], ["T04", "T05"])
        self.assertIn(self.expected("oc-plan-task-writer-deep", work, "briefs", "W02", "plan T04-T05"), out)
        self.assertIn(self.expected("oc-plan-task-writer", work, "briefs", "W01", "plan T01-T03"), out)

    def test_deep_group_falls_back_to_writer_when_deep_agent_missing(self):
        only_writer = lambda repo, name="oc-plan-task-writer": None if name == "oc-plan-task-writer-deep" else "/fake/agents"
        with mock.patch.object(plan_tool, "agent_installed", side_effect=only_writer):
            out, work, _ = self.contracts(5, deep=("T05",))
        self.assertIn(self.expected("oc-plan-task-writer", work, "briefs", "W02", "plan T04-T05"), out)
        self.assertNotIn("oc-plan-task-writer-deep", out)

    def test_missing_agents_fall_back_to_general_and_point_to_setup(self):
        with mock.patch.object(plan_tool, "agent_installed", return_value=None):
            out, work, _ = self.contracts(10)
        self.assertIn(self.expected("general", work, "briefs", "W01", "plan T01-T04"), out)
        self.assertIn("setup --apply", out)
        self.assertNotIn("general-purpose", out)

    def test_forty_tasks_split_into_messages_of_lane_width(self):
        out, work, info = self.contracts(40)
        self.assertEqual(len(info["groups"]), 10)
        self.assertTrue(all(len(v) == 4 for v in info["groups"].values()))
        self.assertIn("MESSAGE 1 (8 calls", out)
        self.assertIn("MESSAGE 2 (2 calls", out)
        self.assertIn("At most 8 calls may be in flight", out)
        self.assertIn(self.expected("oc-plan-task-writer", work, "briefs", "W10", "plan T37-T40"), out)

    def test_build_prints_dispatch_without_any_key(self):
        self.write_plan(6)
        out = self.build()
        work = plan_tool.default_work(self.plan)
        self.assertIn("LANE agent", out)
        self.assertIn("MESSAGE 1 (2 calls", out)
        self.assertTrue(os.path.isfile(os.path.join(work, "briefs", "W01.md")))
        self.assertFalse(any(l.endswith("--all") for l in out.splitlines()), out)

    def test_resume_skips_tasks_that_already_lint_ok(self):
        self.write_plan(6)
        self.build()
        work = plan_tool.default_work(self.plan)
        body = os.path.join(work, "tasks", "T01.md")
        with open(body, "w", encoding="utf-8") as fh:
            fh.write("**Files:**\n")
        with open(body + ".ok", "w", encoding="utf-8") as fh:
            fh.write("1")
        stale = time.time() - 60
        os.utime(body, (stale, stale))
        self.build(resume=True)
        with open(os.path.join(work, "work.json"), encoding="utf-8") as fh:
            info = json.load(fh)
        ids = [t for v in info["groups"].values() for t in v]
        self.assertEqual(ids, ["T02", "T03", "T04", "T05", "T06"])

    def test_thorough_adds_all_flag_to_review_command(self):
        self.write_plan(3)
        out = self.build(thorough=True)
        lines = [l for l in out.splitlines() if l.startswith("THEN:") and " review " in l]
        self.assertEqual(len(lines), 1, out)
        self.assertTrue(lines[0].endswith(" --all"), lines)

    def review(self, installed):
        _, work, _ = self.contracts(2, deep=("T01",))
        with open(os.path.join(work, "tasks", "T01.md"), "w", encoding="utf-8") as fh:
            fh.write("**Files:**\n- Create: `src/p01.py`\n")
        with mock.patch.object(plan_tool, "agent_installed", return_value=installed):
            rc, out = _run(plan_tool.cmd_review,
                           argparse.Namespace(plan=self.plan, all=False, size=None, agents=None))
        self.assertEqual(rc, 0, out)
        return out, work

    def test_review_dispatches_plan_reviewer(self):
        out, work = self.review("/fake/agents")
        self.assertIn(self.expected("oc-plan-reviewer", work, "review-briefs", "R01", "review T01"), out)
        self.assertNotIn("general-purpose", out)

    def test_review_falls_back_to_general_without_reviewer_agent(self):
        out, work = self.review(None)
        self.assertIn(self.expected("general", work, "review-briefs", "R01", "review T01"), out)


if __name__ == "__main__":
    unittest.main()
