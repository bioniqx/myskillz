"""Tests for hp_write: opencode writer turns, lint-repair rounds, fallback markers, down marking."""
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hp_write  # noqa: E402

FENCE = "`" * 3
TIER_STD = {"model": "zai-coding-plan/glm-5.3", "variant": "high", "max_parallel": 6, "stall_s": 180,
            "timeout_s": 900}


def plan_text() -> str:
    return "\n".join([
        "# Demo Plan",
        "",
        "**Goal:** Demo plan for hp_write tests.",
        "",
        "## Global Constraints",
        "",
        "- Python only.",
        "",
        "## Contracts",
        "",
        "#### T01: Alpha",
        "- Depends: —",
        "- Files: `src/a.py`",
        "- Produces: `def alpha() -> int`",
        "- Spec: L1-1",
        "- Tier: deep",
        "",
        "#### T02: Beta",
        "- Depends: —",
        "- Files: `src/b.py`",
        "- Spec: L1-1",
        "",
    ])


def body_for(tid: str, path: str, produces: str = "") -> str:
    code = produces + ":\n    return 1" if produces else "VALUE = 1"
    return "\n".join([
        "**Files:**",
        "- Create: `{}`".format(path),
        "",
        "- [ ] **Step 1: Write the module**",
        "",
        FENCE + "python",
        code,
        FENCE,
        "",
        "- [ ] **Step 2: Check it compiles**",
        "",
        "Run: `python3 -m py_compile {}`".format(path),
        "Expected: no output",
        "",
        "- [ ] **Step 3: Commit**",
        "",
        FENCE + "bash",
        "git " + "add " + path,
        "git commit -m \"feat: {}\"".format(tid.lower()),
        FENCE,
    ])


def wrap(tid: str, body: str) -> str:
    return "\n".join(["@@@ BEGIN " + tid, body, "@@@ END " + tid])


GOOD_T01 = wrap("T01", body_for("T01", "src/a.py", "def alpha() -> int"))
GOOD_T02 = wrap("T02", body_for("T02", "src/b.py"))
BAD_T02 = wrap("T02", "**Files:**\n- Create: `src/b.py`\n")


class HpWriteBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        root = Path(self.tmp)
        self.repo = root / "repo"
        (self.repo / ".git").mkdir(parents=True)
        (self.repo / "docs").mkdir()
        (root / "home").mkdir()
        self.plan = str(self.repo / "docs" / "demo.md")
        Path(self.plan).write_text(plan_text(), encoding="utf-8")
        self.work = os.path.join(str(self.repo), "docs", ".work", "demo")
        os.makedirs(os.path.join(self.work, "tasks"))
        os.makedirs(os.path.join(self.work, "briefs"))
        self.oc_brief = os.path.join(self.work, "briefs", "O01.oc.md")
        Path(self.oc_brief).write_text("oc brief for T01 and T02\n", encoding="utf-8")
        self.save_info({
            "plan": self.plan, "spec": None, "repo": str(self.repo), "allow": [], "agents": 4,
            "tasks": ["T01", "T02"], "groups": {"O01": ["T01", "T02"]}, "review": [], "preset": "hybrid",
            "backend": {"O01": "oc:std"},
            "oc": {"tiers": {"std": dict(TIER_STD)}, "max_repairs": 2, "throttle_cooldown_s": 120,
                   "review_oc": "all"},
        })
        self.env = {
            "HOME": str(root / "home"),
            "HP_ROUTING": str(root / "routing.json"),
            "HP_DOCTOR_CACHE": str(root / "doctor.json"),
            "HP_TELEMETRY": str(root / "lanes.jsonl"),
            "HP_OC_BIN": str(Path(__file__).resolve().parent / "fake_opencode.py"),
        }
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = []
        self.pid_seen = []

    def save_info(self, info: dict) -> None:
        Path(self.work, "work.json").write_text(json.dumps(info), encoding="utf-8")

    def info(self) -> dict:
        return json.loads(Path(self.work, "work.json").read_text(encoding="utf-8"))

    def marker(self, gid: str) -> dict:
        return json.loads(Path(self.work, "oc", gid + ".fallback").read_text(encoding="utf-8"))

    def telemetry(self) -> list:
        path = Path(self.env["HP_TELEMETRY"])
        if not path.exists():
            return []
        return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

    def fake(self, replies):
        queue = list(replies)
        pid_path = os.path.join(self.work, "oc", "oc-write.pid")

        def run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            self.calls.append({"cmd": list(cmd), "cwd": str(cwd), "pwd": env.get("PWD"), "out": str(out_path),
                               "err": str(err_path), "stall": stall_s, "timeout": timeout_s})
            self.pid_seen.append(os.path.exists(pid_path))
            res = {"session": "ses_1", "text": "",
                   "usage": {"input": 10, "output": 5, "reasoning": 1, "cache_read": 0, "cache_write": 0,
                             "cost": 0.0},
                   "errors": [], "throttled": False, "events": 2, "tools": [], "rc": 0, "reason": "", "note": "",
                   "pid": 4242, "duration": 0.1}
            if queue:
                res.update(queue.pop(0))
            return res

        return mock.patch.object(hp_write, "run_once", run_once)


class WriteFallbackTests(HpWriteBase):
    def test_oc_dir_creates_folder(self):
        path = hp_write.oc_dir(self.work)
        self.assertEqual(path, os.path.join(self.work, "oc"))
        self.assertTrue(os.path.isdir(path))

    def test_write_fallback_renders_brief_and_marker(self):
        os.makedirs(os.path.join(self.work, "oc"))
        sent = Path(self.work, "oc", "O01.fallback.sent")
        sent.write_text("old", encoding="utf-8")
        marker = hp_write.write_fallback(self.plan, "O01", ["T01"], "lint", {"T01": ["T01: no commit step"]})
        brief = os.path.join(self.work, "briefs", "O01F.md")
        self.assertEqual(marker["gid"], "O01")
        self.assertEqual(marker["reason"], "lint")
        self.assertEqual(marker["tasks"], ["T01"])
        self.assertEqual(marker["brief"], brief)
        self.assertEqual(marker["model"], "opus")
        self.assertEqual(marker["subagent_type"], "general-purpose")
        self.assertEqual(marker["errors"], {"T01": ["T01: no commit step"]})
        self.assertRegex(marker["t"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertIn("Contract T01", Path(brief).read_text(encoding="utf-8"))
        self.assertNotIn("Contract T02", Path(brief).read_text(encoding="utf-8"))
        self.assertEqual(self.marker("O01"), marker)
        self.assertFalse(sent.exists())

    def test_write_fallback_std_task_uses_sonnet(self):
        marker = hp_write.write_fallback(self.plan, "O02", ["T02"], "format", {})
        self.assertEqual(marker["model"], "sonnet")
        self.assertEqual(marker["errors"], {})
        self.assertTrue(os.path.isfile(os.path.join(self.work, "briefs", "O02F.md")))


class RunGroupTests(HpWriteBase):
    def run_o01(self, shared=None):
        return hp_write.run_group(self.plan, "O01", ["T01", "T02"], "std",
                                  shared or hp_write.new_shared(self.info()))

    def test_round1_ok_writes_markers_and_telemetry(self):
        with self.fake([{"text": GOOD_T01 + "\nchatter outside markers\n" + GOOD_T02}]):
            res = self.run_o01()
        self.assertEqual(res["outcome"], "ok")
        self.assertEqual(res["passed"], ["T01", "T02"])
        self.assertEqual(res["failed"], [])
        self.assertEqual((res["rounds"], res["round1_ok"]), (1, 2))
        self.assertTrue(res["line"].startswith("OC O01 oc:std OK T01,T02 — 1 rounds — "), res["line"])
        for tid in ("T01", "T02"):
            self.assertTrue(os.path.exists(os.path.join(self.work, "tasks", tid + ".md.ok")))
        meta = json.loads(Path(self.work, "tasks", "T01.md.oc").read_text(encoding="utf-8"))
        self.assertEqual(meta, {"tier": "std", "model": TIER_STD["model"], "variant": "high", "round": 1})
        call = self.calls[0]
        self.assertEqual(call["cmd"][1], "run")
        self.assertEqual(call["cmd"][call["cmd"].index("-f") + 1], self.oc_brief)
        self.assertNotIn("--session", call["cmd"])
        self.assertEqual((call["cwd"], call["pwd"]), (str(self.repo), str(self.repo)))
        self.assertEqual((call["stall"], call["timeout"]), (180, 900))
        self.assertTrue(call["out"].endswith(os.path.join("oc", "O01.1.jsonl")))
        self.assertTrue(call["err"].endswith(os.path.join("oc", "O01.1.err")))
        self.assertFalse(os.path.exists(os.path.join(self.work, "oc", "O01.fallback")))
        rec = self.telemetry()[-1]
        self.assertEqual((rec["kind"], rec["gid"], rec["outcome"], rec["rounds"]), ("group", "O01", "ok", 1))
        self.assertEqual((rec["tier"], rec["round1_ok"], rec["tokens"]["input"]), ("std", 2, 10))

    def test_repair_round_reuses_session_without_attachment(self):
        replies = [{"text": GOOD_T01 + "\n" + BAD_T02, "session": "ses_9"}, {"text": GOOD_T02, "session": "ses_9"}]
        with self.fake(replies):
            res = self.run_o01()
        self.assertEqual(res["outcome"], "ok")
        self.assertEqual((res["rounds"], res["round1_ok"]), (2, 1))
        cmd = self.calls[1]["cmd"]
        self.assertEqual(cmd[cmd.index("--session") + 1], "ses_9")
        self.assertNotIn("-f", cmd)
        self.assertIn("T02", cmd[-1])
        meta = json.loads(Path(self.work, "tasks", "T02.md.oc").read_text(encoding="utf-8"))
        self.assertEqual(meta["round"], 2)
        self.assertEqual(self.telemetry()[-1]["tokens"]["output"], 10)

    def test_lint_failure_falls_back_after_max_repairs(self):
        with self.fake([{"text": GOOD_T01 + "\n" + BAD_T02}, {"text": BAD_T02}, {"text": BAD_T02}]):
            res = self.run_o01()
        self.assertEqual(len(self.calls), 3)
        self.assertEqual((res["outcome"], res["reason"]), ("partial", "lint"))
        self.assertEqual((res["passed"], res["failed"]), (["T01"], ["T02"]))
        self.assertTrue(res["line"].startswith("OC O01 oc:std FALLBACK (lint) passed=T01 failed=T02 — 3 rounds — "),
                        res["line"])
        marker = self.marker("O01")
        self.assertEqual((marker["tasks"], marker["reason"], marker["model"]), (["T02"], "lint", "sonnet"))
        self.assertTrue(marker["errors"]["T02"])
        self.assertTrue(os.path.exists(os.path.join(self.work, "tasks", "T01.md.ok")))
        self.assertFalse(os.path.exists(os.path.join(self.work, "tasks", "T02.md.ok")))
        self.assertEqual(self.telemetry()[-1]["outcome"], "partial")

    def test_missing_bodies_fall_back_as_format(self):
        with self.fake([{"text": "no markers here"}] * 3):
            res = self.run_o01()
        self.assertEqual(len(self.calls), 3)
        self.assertEqual((res["outcome"], res["reason"]), ("fallback", "format"))
        self.assertIn("FALLBACK (format) passed=- failed=T01,T02 — 3 rounds — ", res["line"])
        marker = self.marker("O01")
        self.assertEqual(marker["tasks"], ["T01", "T02"])
        self.assertEqual(marker["model"], "opus")
        self.assertEqual(marker["errors"]["T01"], ["missing from your reply"])

    def test_unavailable_marks_tier_down_and_queued_groups_fall_back(self):
        cache = {"t": "2026-09-28T00:00:00Z", "ok": True, "version": "2.0.18", "binary": "opencode",
                 "tiers": {"std": {"model": TIER_STD["model"], "variant": "high", "listed": True, "ping": "ok",
                                   "note": "", "down": None}}}
        Path(self.env["HP_DOCTOR_CACHE"]).write_text(json.dumps(cache), encoding="utf-8")
        shared = hp_write.new_shared(self.info())
        failure = {"rc": 1, "reason": "unavailable", "errors": ["APIError: subscription expired"],
                   "note": "subscription expired"}
        with self.fake([failure]):
            first = self.run_o01(shared)
            second = hp_write.run_group(self.plan, "O02", ["T01"], "std", shared)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual((first["outcome"], first["reason"]), ("fallback", "unavailable"))
        self.assertEqual((second["reason"], second["rounds"]), ("unavailable", 0))
        self.assertIn("std", shared["down"])
        down = json.loads(Path(self.env["HP_DOCTOR_CACHE"]).read_text(encoding="utf-8"))["tiers"]["std"]["down"]
        self.assertIsNotNone(down)
        self.assertEqual(down["reason"], "unavailable")
        self.assertIn("subscription expired", self.marker("O01")["errors"]["T01"][-1])
        self.assertEqual(self.marker("O02")["tasks"], ["T01"])

    def test_mark_down_runs_while_holding_shared_lock(self):
        shared = hp_write.new_shared(self.info())
        held = []

        def spy(path, tier, reason, message):
            held.append((tier, shared["lock"].locked()))

        failure = {"rc": 1, "reason": "unavailable", "errors": ["APIError: subscription expired"],
                   "note": "subscription expired"}
        with self.fake([failure]), mock.patch.object(hp_write, "mark_down", side_effect=spy):
            self.run_o01(shared)
        self.assertEqual(held, [("std", True)])

    def test_throttle_starts_cooldown(self):
        shared = hp_write.new_shared(self.info())
        failure = {"rc": 1, "reason": "throttle", "errors": ["APIError: 429 rate limit"], "note": "429 rate limit"}
        with self.fake([failure]):
            first = self.run_o01(shared)
            second = hp_write.run_group(self.plan, "O02", ["T02"], "std", shared)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual((first["reason"], second["reason"]), ("throttle", "throttle"))
        self.assertGreater(shared["cooldown"]["std"], time.time())
        self.assertEqual(self.marker("O02")["reason"], "throttle")


class OcWriteTests(HpWriteBase):
    def run_oc_write(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = hp_write.oc_write(self.plan)
        return rc, out.getvalue().splitlines()

    def test_prints_group_lines_and_removes_pid(self):
        with self.fake([{"text": GOOD_T01 + "\n" + GOOD_T02}]):
            rc, lines = self.run_oc_write()
        self.assertEqual(rc, 0)
        self.assertEqual(len(lines), 2, lines)
        self.assertTrue(lines[0].startswith("OC O01 oc:std OK T01,T02 — 1 rounds — "), lines[0])
        self.assertEqual(lines[1], "OC-WRITE done 1/1 groups")
        self.assertEqual(self.pid_seen, [True])
        self.assertFalse(os.path.exists(os.path.join(self.work, "oc", "oc-write.pid")))

    def test_concurrent_unavailable_tiers_are_both_marked_down(self):
        info = self.info()
        info["groups"] = {"O01": ["T01"], "O02": ["T02"]}
        info["backend"] = {"O01": "oc:std", "O02": "oc:deep"}
        info["oc"]["tiers"]["deep"] = dict(TIER_STD, model="zai-coding-plan/glm-5.3-deep")
        self.save_info(info)
        Path(self.work, "briefs", "O02.oc.md").write_text("oc brief for T02\n", encoding="utf-8")
        blank = {"model": "", "variant": "", "listed": True, "ping": "ok", "note": "", "down": None}
        cache = {"t": "2026-09-28T00:00:00Z", "ok": True, "version": "2.0.18", "binary": "opencode",
                 "tiers": {"std": dict(blank), "deep": dict(blank)}}
        Path(self.env["HP_DOCTOR_CACHE"]).write_text(json.dumps(cache), encoding="utf-8")
        real_load = hp_write.hp_doctor.load_doctor

        def slow_load(path):
            data = real_load(path)
            time.sleep(0.3)
            return data

        failure = {"rc": 1, "reason": "unavailable", "errors": ["APIError: subscription expired"],
                   "note": "subscription expired"}
        with self.fake([dict(failure), dict(failure)]), \
                mock.patch.object(hp_write.hp_doctor, "load_doctor", side_effect=slow_load):
            rc, lines = self.run_oc_write()
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(lines[-1], "OC-WRITE done 0/2 groups")
        tiers = json.loads(Path(self.env["HP_DOCTOR_CACHE"]).read_text(encoding="utf-8"))["tiers"]
        for name in ("std", "deep"):
            self.assertIsNotNone(tiers[name]["down"], name)
            self.assertEqual(tiers[name]["down"]["reason"], "unavailable")

    def test_no_opencode_groups(self):
        info = self.info()
        info["backend"] = {"O01": "claude"}
        self.save_info(info)
        with self.fake([]):
            rc, lines = self.run_oc_write()
        self.assertEqual((rc, lines), (0, ["OC none"]))
        self.assertEqual(self.calls, [])

    def test_group_crash_is_contained(self):
        with mock.patch.object(hp_write, "run_group", side_effect=RuntimeError("boom")):
            rc, lines = self.run_oc_write()
        self.assertEqual(rc, 0)
        self.assertEqual(lines, ["OC O01 oc:std FALLBACK (crash) passed=- failed=T01,T02 — 0 rounds — 0s",
                                 "OC-WRITE done 0/1 groups"])
        marker = self.marker("O01")
        self.assertEqual((marker["reason"], marker["tasks"]), ("crash", ["T01", "T02"]))
        self.assertEqual(marker["errors"]["T01"], ["RuntimeError: boom"])
        self.assertFalse(os.path.exists(os.path.join(self.work, "oc", "oc-write.pid")))
