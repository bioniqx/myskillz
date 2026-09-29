import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hp_telemetry  # noqa: E402

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
        self.work = self.root / "docs" / "plans" / ".work" / "demo"
        (self.work / "tasks").mkdir(parents=True)
        (self.work / "oc").mkdir()
        (self.work / "briefs").mkdir()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.telemetry = self.tmp / "lanes.jsonl"
        self.doctor = self.tmp / "doctor.json"
        self.env = dict(os.environ, HOME=str(self.home), HP_ROUTING=str(self.tmp / "routing.json"),
                        HP_DOCTOR_CACHE=str(self.doctor), HP_TELEMETRY=str(self.telemetry),
                        HP_OC_BIN=FAKE, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
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
                  "subagent_type": "plan-task-writer", "errors": {"T01": ["T01: no commit step"]},
                  "t": "2026-09-28T10:00:00Z"}
        (self.work / "oc" / "O01.fallback").write_text(json.dumps(marker), encoding="utf-8")
        r = self.run_tool("wait", str(self.plan), "--timeout", "10", "--idle", "10")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        line = ("FALLBACK O01 (lint) T01 → Agent subagent_type=plan-task-writer model=sonnet "
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

    def test_dead_runner_writes_runner_died_fallback(self):
        self.write_work()
        (self.work / "oc" / "oc-write.pid").write_text(str(self.dead_pid()), encoding="utf-8")
        r = self.run_tool("wait", str(self.plan), "--timeout", "15", "--idle", "15")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        rows = [l for l in r.stdout.splitlines() if l.startswith("FALLBACK O01 (runner-died) T01 → Agent ")]
        self.assertEqual(len(rows), 1, r.stdout)
        self.assertTrue((self.work / "oc" / "O01.fallback").exists())
        self.assertTrue((self.work / "oc" / "O01.fallback.sent").exists())


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


UNAVAILABLE = "opencode: unavailable → preset claude (run plan_tool.py doctor --ping)"


class ContextLineTest(CliBase):
    def write_doctor(self, std_down=None):
        tiers = {
            "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "listed": True, "ping": "ok",
                    "note": "", "down": std_down},
            "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low", "listed": True, "ping": "ok",
                     "note": "", "down": None},
        }
        self.doctor.write_text(json.dumps({"t": "2026-09-28T10:00:00Z", "ok": True, "version": "2.0.18",
                                           "binary": FAKE, "tiers": tiers}), encoding="utf-8")

    def opencode_line(self, *args):
        r = self.run_tool("context", *args)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        lines = r.stdout.splitlines()
        i = next(n for n, l in enumerate(lines) if l.startswith("writer agent:"))
        return lines[i + 1]

    def test_no_doctor_cache_prints_unavailable(self):
        self.assertEqual(self.opencode_line(), UNAVAILABLE)

    def test_hybrid_line_from_cache(self):
        self.write_doctor()
        self.assertEqual(self.opencode_line(),
                         "opencode: v2.0.18 preset=hybrid light=oc:lite std=oc:std deep=claude "
                         "review_oc=all (doctor 2026-09-28)")

    def test_preset_argument_is_passed(self):
        self.write_doctor()
        self.assertEqual(self.opencode_line("--preset", "max"),
                         "opencode: v2.0.18 preset=max light=oc:lite std=oc:std deep=oc:std "
                         "review_oc=risky (doctor 2026-09-28)")

    def test_down_tier_shows_reason(self):
        self.write_doctor(std_down={"reason": "unavailable", "message": "model not found",
                                    "at": "2026-09-28T10:05:00Z"})
        self.assertIn("std=claude(down: unavailable)", self.opencode_line())


class SetupAgentTest(CliBase):
    def agent_path(self):
        return self.home / ".claude" / "agents" / "plan-task-writer.md"

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
