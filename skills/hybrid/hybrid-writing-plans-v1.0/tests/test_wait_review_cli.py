import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hp_telemetry  # noqa: E402
import hybrid_shared  # noqa: E402
import plan_tool  # noqa: E402

TESTS = Path(__file__).resolve().parent
TOOL = str(Path(__file__).resolve().parents[1] / "scripts" / "plan_tool.py")
FAKE = str(TESTS / "fake_opencode.py")

PLAN = "\n".join([
    "# Demo Implementation Plan",
    "",
    "**Goal:** Demo plan for the wait and review tests.",
    "",
    "## Global Constraints",
    "",
    "- Python 3.8 stdlib only.",
    "",
    "## Contracts",
    "",
    "#### T01: First",
    "- Depends: —",
    "- Files: `pkg/a.py`",
    "- Spec: L1-2",
    "",
    "#### T02: Second",
    "- Depends: —",
    "- Files: `pkg/b.py`",
    "- Spec: L1-2",
    "",
])

BODY = "**Files:**\n- Create: `pkg/a.py`\n\nbody line one\nbody line two\n"


class CliBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.root = self.tmp / "repo"
        (self.root / ".git").mkdir(parents=True)
        self.plan = self.root / "docs" / "plans" / "demo.md"
        self.plan.parent.mkdir(parents=True)
        self.plan.write_text(PLAN, encoding="utf-8")
        self.work = self.root / "docs" / "plans" / ".hybrid-work" / "demo"
        (self.work / "tasks").mkdir(parents=True)
        (self.work / "oc").mkdir()
        (self.work / "briefs").mkdir()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.telemetry = self.tmp / "lanes.jsonl"
        self.doctor = self.tmp / "doctor.json"
        self.env = dict(os.environ, HOME=str(self.home), HYBRID_WRITING_PLANS_ROUTING=str(self.tmp / "routing.json"),
                        HYBRID_WRITING_PLANS_DOCTOR_CACHE=str(self.doctor), HYBRID_WRITING_PLANS_TELEMETRY=str(self.telemetry),
                        HYBRID_WRITING_PLANS_OC_BIN=FAKE, HYBRID_OPENCODE_STD="zai-coding-plan/glm-5.3#high",
                        HYBRID_OPENCODE_LITE="zai-coding-plan/glm-5.3-flash#low",
                        XDG_DATA_HOME=str(self.tmp / "xdg"), PYTHONDONTWRITEBYTECODE="1",
                        PYTHONIOENCODING="utf-8")
        self.env.pop("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", None)

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def run_tool(self, *args, cwd=None, timeout=90):
        return subprocess.run([sys.executable, TOOL] + list(args), env=self.env, cwd=str(cwd or self.root),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                              universal_newlines=True, encoding="utf-8")

    def write_work(self, **extra):
        info = {
            "plan": str(self.plan), "spec": None, "repo": str(self.root), "allow": [], "agents": 4,
            "tasks": ["T01", "T02"], "groups": {"O01": ["T01"], "T02": ["T02"]}, "review": [],
            "preset": "hybrid", "backend": {"O01": "oc:std", "T02": "claude"},
            "oc": {"tiers": {"std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "max_parallel": 6,
                                     "stall_s": 180, "timeout_s": 900}},
                   "max_repairs": 2, "throttle_cooldown_s": 120, "review_oc": "all"},
        }
        info.update(extra)
        (self.work / "work.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
        return info

    def read_work(self):
        return json.loads((self.work / "work.json").read_text(encoding="utf-8"))

    def write_task(self, tid, mark=None, oc_tier=None):
        path = self.work / "tasks" / (tid + ".md")
        path.write_text(BODY, encoding="utf-8")
        if oc_tier:
            (self.work / "tasks" / (tid + ".md.oc")).write_text(
                json.dumps({"tier": oc_tier, "model": "zai-coding-plan/glm-5.3", "variant": "high", "round": 1}),
                encoding="utf-8")
        if mark:
            (self.work / "tasks" / (tid + ".md." + mark)).write_text("1", encoding="utf-8")
        return path

    def dead_pid(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        return p.pid


class WaitFallbackTest(CliBase):
    def test_pending_fallback_prints_line_marks_sent_and_exits_2(self):
        self.write_work()
        (self.work / "oc" / "oc-write.pid").write_text(str(os.getpid()), encoding="utf-8")
        brief = str(self.work / "briefs" / "O01F.md")
        marker = {"gid": "O01", "reason": "lint", "tasks": ["T01"], "brief": brief, "model": "sonnet",
                  "subagent_type": "hybrid-plan-task-writer", "errors": {"T01": ["T01: no commit step"]},
                  "t": "2026-09-28T10:00:00Z"}
        (self.work / "oc" / "O01.fallback").write_text(json.dumps(marker), encoding="utf-8")
        r = self.run_tool("wait", str(self.plan), "--timeout", "10", "--idle", "10")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        line = ("FALLBACK O01 (lint) T01 → Agent subagent_type=hybrid-plan-task-writer model=sonnet "
                "description 'plan O01F' prompt: Read %s and follow it exactly." % brief)
        self.assertIn(line, r.stdout.splitlines())
        self.assertIn("Launch every FALLBACK Agent call above in ONE message, then run wait again.", r.stdout)
        self.assertTrue((self.work / "oc" / "O01.fallback.sent").exists())
        self.write_task("T01", mark="ok")
        self.write_task("T02", mark="ok")
        r2 = self.run_tool("wait", str(self.plan), "--timeout", "10", "--idle", "10")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertTrue(r2.stdout.startswith("DONE 2/2 tasks"), r2.stdout)

    def test_live_runner_counts_as_progress(self):
        self.write_work()
        (self.work / "oc" / "oc-write.pid").write_text(str(os.getpid()), encoding="utf-8")
        r = self.run_tool("wait", str(self.plan), "--timeout", "3", "--idle", "1")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("PENDING", r.stdout)
        self.assertIn("timeout", r.stdout)
        self.assertNotIn("no progress", r.stdout)
        self.assertIn("oc-write is still running (groups beyond a tier's max_parallel wait for a free slot): run wait again.",
                      r.stdout.splitlines())

    def test_dead_runner_writes_runner_died_fallback(self):
        self.write_work()
        (self.work / "oc" / "oc-write.pid").write_text(str(self.dead_pid()), encoding="utf-8")
        r = self.run_tool("wait", str(self.plan), "--timeout", "15", "--idle", "15")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        rows = [l for l in r.stdout.splitlines() if l.startswith("FALLBACK O01 (runner-died) T01 → Agent ")]
        self.assertEqual(len(rows), 1, r.stdout)
        self.assertTrue((self.work / "oc" / "O01.fallback").exists())
        self.assertTrue((self.work / "oc" / "O01.fallback.sent").exists())


OC_ERROR = "OC-ERROR hybrid-writing-plans O01 tier=std model=zai-coding-plan/glm-5.3 kind=auth :: 401 unauthorized"
OC_WARN = "OC-WARN hybrid-writing-plans O01 tier=std model=zai-coding-plan/glm-5.3 kind=recovered :: exit 1 after a finished step"


class WaitOcLinesTest(CliBase):
    def wait_inprocess(self, fresh, *args):
        calls = []

        def fake_take_unreported(path):
            calls.append(path)
            return list(fresh) if len(calls) == 1 else []

        out = io.StringIO()
        with mock.patch.object(hybrid_shared, "take_unreported", side_effect=fake_take_unreported):
            with contextlib.redirect_stdout(out):
                rc = plan_tool.main(["wait", str(self.plan)] + list(args))
        return rc, out.getvalue().splitlines(), calls

    def test_unreported_lines_print_before_done(self):
        self.write_work(backend={"O01": "claude", "T02": "claude"})
        self.write_task("T01", mark="ok")
        self.write_task("T02", mark="ok")
        rc, lines, calls = self.wait_inprocess([OC_WARN], "--timeout", "10", "--idle", "10")
        self.assertEqual(rc, 0, lines)
        self.assertEqual(lines[0], OC_WARN)
        self.assertTrue(lines[1].startswith("DONE 2/2 tasks"), lines)
        self.assertEqual(calls[0], self.work / "oc" / "oc-errors.jsonl")

    def test_new_oc_error_returns_at_once_with_exit_2(self):
        self.write_work(backend={"O01": "claude", "T02": "claude"})
        rc, lines, calls = self.wait_inprocess([OC_ERROR], "--timeout", "30", "--idle", "30")
        self.assertEqual(rc, 2, lines)
        self.assertEqual(lines[0], OC_ERROR)
        self.assertIn("Relay the OC-ERROR lines above", lines[1])

    def test_held_groups_end_the_wait_with_exit_3(self):
        self.write_work(backend={"O01": "held", "T02": "claude"})
        self.write_task("T02", mark="ok")
        r = self.run_tool("wait", str(self.plan), "--timeout", "10", "--idle", "10")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("HELD T01", r.stdout)

    def test_include_held_waits_for_the_claude_writer(self):
        self.write_work(backend={"O01": "held", "T02": "claude"})
        self.write_task("T02", mark="ok")
        r = self.run_tool("wait", str(self.plan), "--include-held", "--timeout", "2", "--idle", "1")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("PENDING", r.stdout)

    def test_held_marker_from_a_failed_group_is_not_offered_for_dispatch(self):
        self.write_work(preset="opencode")
        (self.work / "oc" / "oc-write.pid").write_text(str(os.getpid()), encoding="utf-8")
        marker = {"gid": "O01", "reason": "auth", "tasks": ["T01"], "held": True, "model": "sonnet",
                  "brief": str(self.work / "briefs" / "O01F.md"), "errors": {}}
        (self.work / "oc" / "O01.fallback").write_text(json.dumps(marker), encoding="utf-8")
        r = self.run_tool("wait", str(self.plan), "--timeout", "10", "--idle", "10")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertTrue(any(l.startswith("HELD O01 (auth) T01") for l in r.stdout.splitlines()), r.stdout)
        self.assertIn("Do not dispatch the HELD groups above.", r.stdout)
        self.assertNotIn("Launch every FALLBACK", r.stdout)


    def test_group_held_at_runtime_ends_a_second_wait_with_exit_3(self):
        self.write_work(preset="opencode", backend={"O01": "oc:std", "T02": "claude"})
        self.write_task("T02", mark="ok")
        marker = {"gid": "O01", "reason": "auth", "tasks": ["T01"], "held": True, "model": "sonnet",
                  "brief": str(self.work / "briefs" / "O01F.md"), "errors": {}}
        (self.work / "oc" / "O01.fallback").write_text(json.dumps(marker), encoding="utf-8")
        (self.work / "oc" / "O01.fallback.sent").write_text("1", encoding="utf-8")  # the HELD line was already shown
        r = self.run_tool("wait", str(self.plan), "--timeout", "10", "--idle", "10")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("HELD T01 not written", r.stdout)
        r2 = self.run_tool("wait", str(self.plan), "--include-held", "--timeout", "2", "--idle", "1")
        self.assertEqual(r2.returncode, 1, r2.stdout + r2.stderr)  # the user chose Claude: wait for it
        self.assertIn("PENDING", r2.stdout)

    def test_held_task_ids_reads_held_markers_but_not_plain_fallbacks(self):
        info = self.write_work(backend={"O01": "oc:std", "T02": "claude"})
        (self.work / "oc" / "O01.fallback").write_text(
            json.dumps({"gid": "O01", "tasks": ["T01"], "held": True}), encoding="utf-8")
        (self.work / "oc" / "O02.fallback").write_text(
            json.dumps({"gid": "O02", "tasks": ["T02"]}), encoding="utf-8")
        (self.work / "oc" / "O03.fallback").write_text("not json", encoding="utf-8")
        self.assertEqual(plan_tool.held_task_ids(info, str(self.work)), {"T01"})
        self.assertEqual(plan_tool.held_task_ids(info), set())


class CleanWorkTest(CliBase):
    def test_clean_keeps_the_error_log(self):
        (self.work / "oc" / "oc-errors.jsonl").write_text('{"line": "x"}\n', encoding="utf-8")
        (self.work / "oc" / "O01.1.err").write_text("boom\n", encoding="utf-8")
        self.write_task("T01", mark="ok")
        self.assertTrue(plan_tool.clean_work(str(self.work)))
        self.assertEqual((self.work / "oc" / "oc-errors.jsonl").read_text(encoding="utf-8"), '{"line": "x"}\n')
        self.assertEqual(sorted(p.name for p in self.work.rglob("*")), ["oc", "oc-errors.jsonl"])

    def test_clean_removes_everything_without_an_error_log(self):
        self.write_task("T01", mark="ok")
        self.assertFalse(plan_tool.clean_work(str(self.work)))
        self.assertFalse(self.work.exists())


class ReviewOcTest(CliBase):
    def test_review_oc_all_picks_oc_tasks_and_stores_hash(self):
        self.write_work()
        t01 = self.write_task("T01", mark="ok", oc_tier="std")
        self.write_task("T02", mark="ok")
        r = self.run_tool("review", str(self.plan))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("REVIEW 1 tasks: T01(oc)", r.stdout)
        info = self.read_work()
        self.assertEqual(info["review"], ["T01"])
        self.assertEqual(info["review_hash"], {"T01": hp_telemetry.file_sha(str(t01))})
        self.assertNotIn("review_logged", info)
        self.assertTrue((self.work / "review-briefs" / "R01.md").exists())

    def test_review_oc_risky_uses_only_62_triggers(self):
        info = self.write_work()
        info["oc"]["review_oc"] = "risky"
        (self.work / "work.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
        self.write_task("T01", mark="ok", oc_tier="std")
        self.write_task("T02", mark="ok")
        r = self.run_tool("review", str(self.plan))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("NONE"), r.stdout)
        info = self.read_work()
        self.assertEqual(info["review"], [])
        self.assertEqual(info["review_hash"], {})


class WaitReviewTelemetryTest(CliBase):
    def test_done_review_logs_one_record_per_oc_task_once(self):
        t01 = self.write_task("T01", mark="rev", oc_tier="std")
        t02 = self.write_task("T02", mark="rev", oc_tier="lite")
        self.write_work(review=["T01", "T02"],
                        review_hash={"T01": "0" * 64, "T02": hp_telemetry.file_sha(str(t02))})
        self.assertTrue(t01.exists())
        r = self.run_tool("wait", str(self.plan), "--review", "--timeout", "10", "--idle", "10")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(r.stdout.startswith("DONE 2/2 reviews"), r.stdout)
        recs = [json.loads(l) for l in self.telemetry.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(recs), 2)
        by = {x["task"]: x for x in recs}
        self.assertEqual(by["T01"]["kind"], "review")
        self.assertEqual(by["T01"]["tier"], "std")
        self.assertIs(by["T01"]["fixed_by_review"], True)
        self.assertEqual(by["T02"]["tier"], "lite")
        self.assertIs(by["T02"]["fixed_by_review"], False)
        self.assertEqual(by["T01"]["plan"], str(self.plan))
        self.assertEqual(by["T01"]["repo"], str(self.root))
        self.assertIs(self.read_work()["review_logged"], True)
        r2 = self.run_tool("wait", str(self.plan), "--review", "--timeout", "10", "--idle", "10")
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        again = [l for l in self.telemetry.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(again), 2)


SHARED = {"tiers": {
    "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high"},
    "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low"}}}


class ContextLineTest(CliBase):
    def write_doctor(self, std_ok=True):
        tiers = {}
        for name, spec in SHARED["tiers"].items():
            ok = std_ok or name != "std"
            tiers[name] = {"ok": ok, "key": hybrid_shared.cache_key(spec), "checked_at": time.time(),
                           "kind": "" if ok else "auth", "detail": "" if ok else "401 unauthorized"}
        self.doctor.write_text(json.dumps({"t": "2026-09-29T10:00:00Z", "ok": True, "version": "2.0.19",
                                           "binary": FAKE, "tiers": tiers}), encoding="utf-8")

    def context_lines(self, *args):
        r = self.run_tool("context", *args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        i = next(n for n, l in enumerate(lines) if l.startswith("writer agent:"))
        return lines[i + 1:i + 4]

    def opencode_line(self, *args):
        return self.context_lines(*args)[0]

    def test_no_doctor_cache_prints_unavailable(self):
        line = self.opencode_line()
        self.assertTrue(line.startswith("opencode:"), line)
        self.assertIn("unavailable", line)

    def test_hybrid_line_from_cache(self):
        self.write_doctor()
        line = self.opencode_line()
        for part in ("v2.0.19", "preset=hybrid", "light=oc:lite", "std=oc:std", "deep=claude"):
            self.assertIn(part, line)

    def test_opencode_mode_argument_is_passed(self):
        self.write_doctor()
        line = self.opencode_line("mode=opencode")
        self.assertIn("preset=opencode", line)
        self.assertIn("deep=oc:std", line)

    def test_max_preset_argument_maps_to_opencode(self):
        self.write_doctor()
        self.assertIn("preset=opencode", self.opencode_line("--preset", "max"))

    def test_failed_tier_shows_claude(self):
        self.write_doctor(std_ok=False)
        self.assertIn("std=claude", self.opencode_line())

    def test_config_line_shows_source_and_specs(self):
        self.write_doctor()
        line = self.context_lines()[1]
        self.assertIn(hybrid_shared.SHARED_SOURCE, line)
        self.assertIn("std=zai-coding-plan/glm-5.3#high, lite=zai-coding-plan/glm-5.3-flash#low", line)

    def test_config_line_marks_each_tier_skill_or_shared(self):
        self.write_doctor()
        Path(self.env["HYBRID_WRITING_PLANS_ROUTING"]).write_text(
            json.dumps({"tiers": {"lite": {"model": "own/model"}}}), encoding="utf-8")
        line = self.context_lines()[1]
        self.assertIn("lite=own/model", line)
        self.assertIn("model from: std (shared), lite (skill)", line)

    def test_config_line_without_the_env_says_std_is_not_set(self):
        self.env.pop("HYBRID_OPENCODE_STD")
        self.env.pop("HYBRID_OPENCODE_LITE")
        line = self.context_lines()[1]
        self.assertIn(hybrid_shared.SHARED_SOURCE, line)
        self.assertIn("HYBRID_OPENCODE_STD is not set", line)

    def test_mode_line(self):
        self.assertTrue(self.context_lines()[2].startswith("mode: unset"))
        self.assertEqual(self.context_lines("mode=claude")[2], "mode: claude (from arguments)")
        self.assertEqual(self.context_lines("--preset", "max")[2], "mode: opencode (from arguments)")
        self.assertTrue(self.context_lines("mode=bogus")[2].startswith("mode: 'bogus' is not valid"))


class PreloadCommandTest(CliBase):
    """The `!` preload line of SKILL.md, run through a shell the way Claude Code inlines $ARGUMENTS."""

    def preload(self, arguments):
        text = (Path(TOOL).parents[1] / "SKILL.md").read_text(encoding="utf-8")
        block = text.split("```!\n", 1)[1].split("\n```", 1)[0]
        cmd = block.replace("${CLAUDE_SKILL_DIR}", str(Path(TOOL).parents[1])).replace("$ARGUMENTS", arguments)
        return subprocess.run(["sh", "-c", cmd], env=self.env, cwd=str(self.root), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=90, universal_newlines=True, encoding="utf-8")

    def test_apostrophe_in_the_arguments_does_not_break_the_preload(self):
        self.write_doctor()
        r = self.preload("docs/plans/demo.md it's the users' plan --thorough mode=opencode")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")
        self.assertIn("mode: opencode (from arguments)", r.stdout)
        self.assertIn("preset=opencode", r.stdout)
        self.assertIn("mode: THOROUGH", r.stdout)

    def test_skill_md_hands_off_to_hybrid_team_with_the_mode(self):
        text = (Path(TOOL).parents[1] / "SKILL.md").read_text(encoding="utf-8")
        handoff = text.split("## Execution Handoff", 1)[1].split("## One-time setup", 1)[0]
        self.assertIn("`hybrid-team` skill with args `<plan path> mode=<mode>`", handoff)
        self.assertIn("`dev-team` skill with args `<plan path>`", handoff)
        desc = text.split('description: "', 1)[1].split('"\n', 1)[0]
        self.assertLessEqual(len(desc), 1024)
        self.assertIn("one Claude fallback per failed group", desc)

    def test_no_arguments_still_runs(self):
        r = self.preload("")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("mode: unset", r.stdout)

    def test_mode_inside_one_string_argument(self):
        r = self.run_tool("context", "docs/plans/demo.md --thorough mode=claude")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("mode: claude (from arguments)", r.stdout)
        self.assertIn("mode: THOROUGH", r.stdout)

    def write_doctor(self):
        specs = {"std": {"model": "zai-coding-plan/glm-5.3", "variant": "high"},
                 "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low"}}
        tiers = {n: {"ok": True, "key": hybrid_shared.cache_key(t), "checked_at": time.time(), "kind": "", "detail": ""}
                 for n, t in specs.items()}
        self.doctor.write_text(json.dumps({"t": "2026-09-29T10:00:00Z", "ok": True, "version": "2.0.19",
                                           "binary": FAKE, "tiers": tiers}), encoding="utf-8")


class SetupAgentTest(CliBase):
    def agent_path(self):
        return self.home / ".claude" / "agents" / "hybrid-plan-task-writer.md"

    def test_existing_agent_is_never_overwritten(self):
        self.agent_path().parent.mkdir(parents=True)
        self.agent_path().write_text("custom agent\n", encoding="utf-8")
        r = self.run_tool("setup", "--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("write agent", r.stdout)
        self.assertEqual(self.agent_path().read_text(encoding="utf-8"), "custom agent\n")
        self.assertTrue((self.home / ".claude" / "settings.json").exists())

    def test_missing_agent_is_installed(self):
        r = self.run_tool("setup", "--apply")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("write agent", r.stdout)
        text = self.agent_path().read_text(encoding="utf-8")
        self.assertNotIn("__PLAN_TOOL__", text)
        self.assertIn("plan_tool.py", text)
