"""Tests for hp_write: opencode writer turns, lint-repair rounds, fallback markers, down marking."""
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hp_wait  # noqa: E402
import hp_write  # noqa: E402
import hybrid_shared  # noqa: E402

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


def head(line: str) -> list:
    """First four fields of an OC line: level, skill, unit, tier."""
    return line.split()[:4]


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
        self.work = os.path.join(str(self.repo), "docs", ".hybrid-work", "demo")
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
            "HYBRID_WRITING_PLANS_ROUTING": str(root / "routing.json"),
            "HYBRID_WRITING_PLANS_DOCTOR_CACHE": str(root / "doctor.json"),
            "HYBRID_WRITING_PLANS_TELEMETRY": str(root / "lanes.jsonl"),
            "HYBRID_WRITING_PLANS_OC_BIN": str(Path(__file__).resolve().parent / "fake_opencode.py"),
            "HYBRID_OPENCODE_STD": "zai-coding-plan/glm-5.3#high",
            "HYBRID_OPENCODE_LITE": "zai-coding-plan/glm-5.3-flash#low",
            "XDG_DATA_HOME": str(root / "xdg"),
            "HYBRID_OC_RETRY_DELAY_S": "0",
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

    def set_preset(self, preset: str) -> None:
        info = self.info()
        info["preset"] = preset
        self.save_info(info)

    def marker(self, gid: str) -> dict:
        return json.loads(Path(self.work, "oc", gid + ".fallback").read_text(encoding="utf-8"))

    def telemetry(self) -> list:
        path = Path(self.env["HYBRID_WRITING_PLANS_TELEMETRY"])
        if not path.exists():
            return []
        return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]

    def run_o01(self, shared=None):
        return hp_write.run_group(self.plan, "O01", ["T01", "T02"], "std",
                                  shared or hp_write.new_shared(self.info()))

    def switched(self) -> dict:
        return hybrid_shared.run_switched(Path(self.work, "oc"))

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

    def test_write_fallback_held_marker(self):
        marker = hp_write.write_fallback(self.plan, "O01", ["T01"], "auth", {}, held=True)
        self.assertTrue(marker["held"])
        self.assertTrue(self.marker("O01")["held"])

    def test_errors_log_lives_in_the_oc_folder(self):
        self.assertEqual(hp_write.errors_log(self.work), Path(self.work, "oc", "oc-errors.jsonl"))

    def test_report_builds_logs_and_returns_the_line(self):
        line = hp_write.report(self.work, "O01", "std", TIER_STD, hp_write.LEVEL_ERROR, "crash", "boom",
                               "/x/O01.1.err")
        self.assertEqual(head(line), ["OC-ERROR", "hybrid-writing-plans", "O01", "tier=std"])
        self.assertTrue(line.endswith(" kind=crash :: boom log=/x/O01.1.err"), line)
        self.assertEqual(hybrid_shared.take_unreported(hp_write.errors_log(self.work)), [line])


class RunGroupTests(HpWriteBase):
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
        self.assertEqual(res["oc_lines"], [])

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
        self.assertEqual(self.switched(), {})
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
        self.assertEqual(len(res["oc_lines"]), 1)
        self.assertEqual(head(res["oc_lines"][0])[:3], ["OC-WARN", "hybrid-writing-plans", "O01"])
        self.assertIn(" kind=lint :: T02 still failing lint after 3 rounds", res["oc_lines"][0])

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
        self.assertIn(" kind=format :: no @@@ BEGIN/END block for T01,T02 after 3 rounds", res["oc_lines"][0])
        self.assertNotIn("held", marker)

    def script(self, step):
        path = Path(self.tmp) / "fake-script.json"
        path.write_text(json.dumps(step), encoding="utf-8")
        return mock.patch.dict(os.environ, {"HYBRID_WRITING_PLANS_FAKE_SCRIPT": str(path)})

    def test_auth_failure_trips_breaker_and_queued_groups_fall_back(self):
        self.set_preset("opencode")
        shared = hp_write.new_shared(self.info())
        failure = {"rc": 1, "reason": "auth", "errors": ["APIError: subscription expired"],
                   "note": "APIError: subscription expired"}
        with self.fake([failure]):
            first = self.run_o01(shared)
            second = hp_write.run_group(self.plan, "O02", ["T01"], "std", shared)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual((first["outcome"], first["reason"]), ("fallback", "auth"))
        self.assertEqual((second["reason"], second["rounds"]), ("breaker", 0))
        self.assertEqual(shared["tripped"], {"std": "auth"})
        self.assertEqual(len(first["oc_lines"]), 1)
        line = first["oc_lines"][0]
        self.assertEqual(head(line), ["OC-ERROR", "hybrid-writing-plans", "O01", "tier=std"])
        self.assertIn(" kind=auth :: APIError: subscription expired", line)
        self.assertTrue(line.endswith(os.path.join("oc", "O01.1.err")), line)
        self.assertEqual(second["oc_lines"], [])
        self.assertIn("subscription expired", self.marker("O01")["errors"]["T01"][-1])
        self.assertEqual(self.marker("O02")["tasks"], ["T01"])
        self.assertEqual(self.marker("O02")["reason"], "breaker")
        summary = hybrid_shared.breaker_summary(Path(self.work, "oc"), hp_write.SKILL)
        self.assertEqual(len(summary), 1)
        self.assertIn("kind=breaker", summary[0])
        self.assertIn("kind=auth", Path(self.work, "oc", "oc-errors.jsonl").read_text(encoding="utf-8"))

    def test_repeat_failure_of_a_tripped_tier_prints_no_second_line(self):
        self.set_preset("opencode")
        failure = {"rc": 1, "reason": "auth", "errors": ["APIError: subscription expired"],
                   "note": "APIError: subscription expired"}
        with self.fake([failure]), \
                mock.patch.object(hp_write.hybrid_shared, "breaker_trip", return_value=False), \
                mock.patch.object(hp_write.hybrid_shared, "breaker_skip", return_value=1) as skip:
            res = self.run_o01()
        self.assertEqual(res["oc_lines"], [])
        self.assertEqual(res["reason"], "auth")
        skip.assert_not_called()  # the group ran: it is not a skipped unit
        self.assertEqual(self.marker("O01")["reason"], "auth")

    def test_every_non_retryable_kind_trips_the_breaker(self):
        self.set_preset("opencode")
        for kind in ("auth", "quota", "model"):
            with self.subTest(kind=kind):
                shared = hp_write.new_shared(self.info())
                failure = {"rc": 1, "reason": kind, "errors": ["boom"], "note": "boom"}
                with self.fake([failure]), \
                        mock.patch.object(hp_write.hybrid_shared, "breaker_trip", return_value=True) as trip:
                    res = self.run_o01(shared)
                self.assertEqual(shared["tripped"], {"std": kind})
                self.assertEqual(trip.call_args[0][3], kind)
                self.assertIn(" kind=%s :: boom" % kind, res["oc_lines"][0])

    def test_tier_without_model_reports_a_config_error(self):
        info = self.info()
        info["oc"]["tiers"]["std"]["model"] = ""
        self.save_info(info)
        shared = hp_write.new_shared(info)
        with self.fake([]):
            res = self.run_o01(shared)
        self.assertEqual(self.calls, [])
        self.assertEqual(res["reason"], "config")
        self.assertIn(" kind=config :: tier std has no model in work.json", res["oc_lines"][0])
        self.assertEqual(shared["tripped"], {"std": "config"})

    def test_throttle_starts_cooldown_and_reports_once(self):
        self.set_preset("opencode")
        shared = hp_write.new_shared(self.info())
        failure = {"rc": 1, "reason": "throttle", "errors": ["APIError: 429 rate limit"], "note": "429 rate limit"}
        with self.fake([failure] * 4):
            first = self.run_o01(shared)
            second = hp_write.run_group(self.plan, "O02", ["T02"], "std", shared)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual((first["reason"], second["reason"]), ("throttle", "throttle"))
        self.assertGreater(shared["cooldown"]["std"], time.time())
        self.assertEqual(self.marker("O02")["reason"], "throttle")
        self.assertEqual(len(first["oc_lines"]), 4)
        self.assertIn(" kind=throttle :: 429 rate limit", first["oc_lines"][3])
        self.assertEqual(second["oc_lines"], [])
        self.assertEqual(shared["tripped"], {})

    def test_empty_replies_are_reported_as_empty(self):
        with self.fake([{"text": ""}] * 3):
            res = self.run_o01()
        self.assertEqual((res["outcome"], res["reason"]), ("fallback", "empty"))
        self.assertEqual(self.switched(), {})
        self.assertIn(" kind=empty :: opencode returned no text in 3 rounds", res["oc_lines"][0])
        self.assertEqual(self.marker("O01")["reason"], "empty")

    def test_recovered_exit_is_accepted_with_a_warning(self):
        reply = {"rc": 1, "reason": "recovered", "errors": ["APIError: upstream hiccup"],
                 "note": "APIError: upstream hiccup", "text": GOOD_T01 + "\n" + GOOD_T02}
        with self.fake([reply]):
            res = self.run_o01()
        self.assertEqual(res["outcome"], "ok")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len(res["oc_lines"]), 1)
        self.assertEqual(head(res["oc_lines"][0])[:3], ["OC-WARN", "hybrid-writing-plans", "O01"])
        self.assertIn(" kind=recovered :: APIError: upstream hiccup", res["oc_lines"][0])
        self.assertFalse(os.path.exists(os.path.join(self.work, "oc", "O01.fallback")))

    def test_recovered_exit_without_bodies_is_a_crash(self):
        reply = {"rc": 1, "reason": "recovered", "errors": ["APIError: upstream hiccup"],
                 "note": "APIError: upstream hiccup", "text": ""}
        with self.fake([reply]):
            res = self.run_o01()
        self.assertEqual((res["outcome"], res["reason"]), ("fallback", "crash"))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.switched(), {})
        self.assertEqual(head(res["oc_lines"][0])[0], "OC-ERROR")
        self.assertIn(" kind=crash :: APIError: upstream hiccup", res["oc_lines"][0])

    def test_opencode_preset_holds_the_group_instead_of_falling_back(self):
        self.set_preset("opencode")
        failure = {"rc": 1, "reason": "auth", "errors": ["boom"], "note": "boom"}
        with self.fake([failure]):
            res = self.run_o01()
        self.assertTrue(res["held"])
        self.assertTrue(res["line"].startswith("OC O01 oc:std HELD (auth) passed=- failed=T01,T02 — 1 rounds — "),
                        res["line"])
        self.assertTrue(self.marker("O01")["held"])
        self.assertEqual(len(res["oc_lines"]), 1)

    def test_recovered_exit_one_end_to_end(self):
        with self.script({"scenario": "recovered", "text": GOOD_T01 + "\n" + GOOD_T02}):
            res = self.run_o01()
        self.assertEqual(res["outcome"], "ok")
        self.assertEqual(len(res["oc_lines"]), 1)
        self.assertEqual(head(res["oc_lines"][0])[:3], ["OC-WARN", "hybrid-writing-plans", "O01"])
        self.assertIn(" kind=recovered ", res["oc_lines"][0])

    def test_auth_error_end_to_end(self):
        shared = hp_write.new_shared(self.info())
        with self.script({"scenario": "auth"}):
            res = self.run_o01(shared)
        self.assertEqual((res["outcome"], res["reason"]), ("fallback", "auth"))
        self.assertIn(" kind=auth ", res["oc_lines"][0])
        self.assertEqual(shared["tripped"], {"std": "auth"})
        self.assertEqual(self.marker("O01")["reason"], "auth")


CRASH = {"error": {"type": "UnknownError", "message": "boom"}}


class RetrySwitchTests(HpWriteBase):
    def script(self, steps) -> None:
        path = Path(self.tmp) / "fake-script.json"
        path.write_text(json.dumps(steps), encoding="utf-8")
        self.fake_log = Path(self.tmp) / "fake.log"
        patcher = mock.patch.dict(os.environ, {"HYBRID_WRITING_PLANS_FAKE_SCRIPT": str(path), "HYBRID_WRITING_PLANS_FAKE_LOG": str(self.fake_log)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def runs(self) -> list:
        if not self.fake_log.exists():
            return []
        records = [json.loads(x) for x in self.fake_log.read_text(encoding="utf-8").splitlines() if x.strip()]
        return [r for r in records if r["argv"][:1] == ["run"]]

    def kinds(self, res) -> list:
        return [x.split()[0] + " " + x.split()[5] for x in res["oc_lines"]]

    def test_connection_failure_is_retried_as_a_fresh_run(self):
        self.script([{"scenario": "throttle", "session": "ses_dead"}, {"text": GOOD_T01 + "\n" + GOOD_T02}])
        shared = hp_write.new_shared(self.info())
        res = self.run_o01(shared)
        runs = self.runs()
        self.assertEqual((res["outcome"], len(runs)), ("ok", 2))
        self.assertEqual((runs[1]["session"], runs[1]["attach"]), ("", self.oc_brief))
        self.assertEqual(len(res["oc_lines"]), 1)
        line = res["oc_lines"][0]
        self.assertEqual(head(line), ["OC-WARN", "hybrid-writing-plans", "O01", "tier=std"])
        self.assertIn(" kind=throttle :: retry 1/3 in 0s: ", line)
        self.assertTrue(line.endswith(os.path.join("oc", "O01.1.err")), line)
        self.assertTrue(os.path.exists(os.path.join(self.work, "oc", "O01.1.r1.err")))
        self.assertEqual(hybrid_shared.take_unreported(hp_write.errors_log(self.work)), [line])
        self.assertEqual((shared["cooldown"], self.switched()), ({}, {}))
        self.assertFalse(os.path.exists(os.path.join(self.work, "oc", "O01.fallback")))

    def test_connection_retry_of_a_repair_turn_is_a_fresh_run_with_the_brief(self):
        self.script([{"text": GOOD_T01 + "\n" + BAD_T02, "session": "ses_9"},
                     {"scenario": "throttle", "session": "ses_dead"},
                     {"text": GOOD_T02}])
        res = self.run_o01()
        runs = self.runs()
        self.assertEqual((res["outcome"], len(runs)), ("ok", 3))
        self.assertEqual((runs[1]["session"], runs[1]["attach"]), ("ses_9", ""))  # the repair turn itself continues
        self.assertEqual((runs[2]["session"], runs[2]["attach"]), ("", self.oc_brief))  # its retry never does
        self.assertNotIn("--session", runs[2]["argv"])
        message = runs[2]["argv"][-1]
        self.assertIn("Read the attached brief", message)
        self.assertIn("T02: ", message)
        self.assertIn("ERR ", message)
        self.assertNotIn("T01: ", message.split("Output now")[0])

    def test_throttle_started_by_another_group_stops_this_group_before_its_next_turn(self):
        shared = hp_write.new_shared(self.info())
        calls = []

        def run_once(cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
            calls.append(list(cmd))
            shared["cooldown"]["std"] = time.time() + 100  # another group just got throttled
            return {"session": "ses_1", "text": GOOD_T01 + "\n" + BAD_T02, "usage": {}, "errors": [], "rc": 0,
                    "reason": "", "note": ""}

        with mock.patch.object(hp_write, "run_once", run_once):
            res = self.run_o01(shared)
        self.assertEqual(len(calls), 1)  # no repair turn
        self.assertEqual((res["reason"], res["passed"], res["failed"]), ("throttle", ["T01"], ["T02"]))
        self.assertEqual(self.marker("O01")["reason"], "throttle")

    def test_retry_waits_10_30_60_seconds(self):
        os.environ.pop(hybrid_shared.RETRY_DELAY_ENV)
        failure = {"rc": 1, "reason": "stall", "errors": [], "note": "stall: no event for 180s"}
        with self.fake([failure] * 4), mock.patch.object(hp_write.time, "sleep") as sleep:
            res = self.run_o01()
        self.assertEqual([c[0][0] for c in sleep.call_args_list], [10, 30, 60])
        for n, secs in ((1, 10), (2, 30), (3, 60)):
            self.assertIn(" kind=stall :: retry %d/3 in %ds: stall: no event for 180s" % (n, secs),
                          res["oc_lines"][n - 1])

    def test_three_retries_then_the_hybrid_run_switches_to_claude(self):
        self.script([CRASH] * 4)
        res = self.run_o01()
        self.assertEqual(len(self.runs()), 4)
        self.assertEqual(self.kinds(res), ["OC-WARN kind=crash"] * 3 + ["OC-ERROR kind=crash", "OC-ERROR kind=switch"])
        self.assertIn(" :: retry 3/3 in 0s: UnknownError: boom", res["oc_lines"][2])
        self.assertTrue(res["oc_lines"][4].endswith(
            " :: opencode crash: UnknownError: boom; the rest of this run uses Claude sonnet"), res["oc_lines"][4])
        self.assertEqual((res["outcome"], res["reason"], res["held"]), ("fallback", "crash", False))
        marker = self.marker("O01")
        self.assertEqual((marker["model"], marker["reason"]), ("sonnet", "crash"))
        self.assertNotIn("held", marker)
        entry = self.switched()
        self.assertEqual((entry["unit"], entry["tier"], entry["kind"]), ("O01", "std", "crash"))
        logged = Path(self.work, "oc", "oc-errors.jsonl").read_text(encoding="utf-8")
        self.assertEqual(logged.count("kind=switch"), 1)

    def test_non_retryable_failure_switches_at_once(self):
        self.script({"scenario": "auth"})
        res = self.run_o01()
        self.assertEqual(len(self.runs()), 1)
        self.assertEqual(self.kinds(res), ["OC-ERROR kind=auth", "OC-ERROR kind=switch"])
        self.assertIn(" :: opencode auth: ", res["oc_lines"][1])
        self.assertEqual(self.marker("O01")["model"], "sonnet")
        self.assertEqual(self.switched()["kind"], "auth")

    def test_timeout_neither_retries_nor_switches(self):
        info = self.info()
        info["oc"]["tiers"]["std"]["timeout_s"] = 1
        self.save_info(info)
        self.script({"sleep": 30})
        res = self.run_o01()
        self.assertEqual(len(self.runs()), 1)
        self.assertEqual(self.kinds(res), ["OC-ERROR kind=timeout"])
        marker = self.marker("O01")
        self.assertEqual((marker["reason"], marker["model"]), ("timeout", "opus"))
        self.assertEqual(self.switched(), {})

    def test_after_a_switch_later_groups_get_sonnet_fallbacks_without_spawning(self):
        self.script({"scenario": "auth"})
        shared = hp_write.new_shared(self.info())
        self.run_o01(shared)
        later = hp_write.run_group(self.plan, "O02", ["T01"], "std", shared)
        self.assertEqual(len(self.runs()), 1)
        self.assertEqual((later["reason"], later["rounds"], later["oc_lines"]), ("switched", 0, []))
        self.assertTrue(later["line"].startswith("OC O02 oc:std FALLBACK (switched) passed=- failed=T01 — 0 rounds"),
                        later["line"])
        marker = self.marker("O02")
        self.assertEqual((marker["reason"], marker["model"], marker["tasks"]), ("switched", "sonnet", ["T01"]))
        self.assertIn("tier std is not used: this run switched to Claude sonnet", marker["errors"]["T01"][0])
        lines = hp_wait.pending_fallback_lines(self.work)
        self.assertEqual(len([x for x in lines if " kind=switch " in x]), 1)
        fallbacks = [x for x in lines if x.startswith("FALLBACK ")]
        self.assertEqual(len(fallbacks), 2)
        self.assertTrue(all(" model=sonnet " in x for x in fallbacks), fallbacks)
        self.assertIn("FALLBACK O02 (switched) T01 → Agent ", fallbacks[1])
        self.assertEqual(hp_wait.pending_fallback_lines(self.work), [])

    def test_opencode_preset_retries_then_holds_without_a_switch(self):
        self.set_preset("opencode")
        self.script([CRASH] * 4)
        res = self.run_o01()
        self.assertEqual(len(self.runs()), 4)
        self.assertEqual(self.kinds(res), ["OC-WARN kind=crash"] * 3 + ["OC-ERROR kind=crash"])
        self.assertTrue(res["line"].startswith("OC O01 oc:std HELD (crash) passed=- failed=T01,T02 — 1 rounds — "),
                        res["line"])
        marker = self.marker("O01")
        self.assertEqual((marker["held"], marker["model"]), (True, "opus"))
        self.assertEqual(self.switched(), {})

    def test_opencode_preset_non_retryable_failure_has_no_retry_and_no_switch(self):
        self.set_preset("opencode")
        self.script({"scenario": "auth"})
        res = self.run_o01()
        self.assertEqual(len(self.runs()), 1)
        self.assertEqual(self.kinds(res), ["OC-ERROR kind=auth"])
        self.assertEqual(self.switched(), {})

    def test_two_failing_groups_print_one_switch_line(self):
        info = self.info()
        info["groups"] = {"O01": ["T01"], "O02": ["T02"]}
        info["backend"] = {"O01": "oc:std", "O02": "oc:std"}
        self.save_info(info)
        Path(self.work, "briefs", "O02.oc.md").write_text("oc brief for T02\n", encoding="utf-8")
        self.script({"scenario": "auth"})
        out = io.StringIO()
        with redirect_stdout(out):
            hp_write.oc_write(self.plan)
        lines = out.getvalue().splitlines()
        self.assertEqual(len([x for x in lines if " kind=switch " in x]), 1)
        self.assertEqual(lines[-1], "OC-WRITE done 0/2 groups")
        self.assertEqual(self.marker("O01")["model"], "sonnet")
        logged = Path(self.work, "oc", "oc-errors.jsonl").read_text(encoding="utf-8")
        self.assertEqual(logged.count("kind=switch"), 1)


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

    def test_no_opencode_groups(self):
        info = self.info()
        info["backend"] = {"O01": "claude"}
        self.save_info(info)
        with self.fake([]):
            rc, lines = self.run_oc_write()
        self.assertEqual((rc, lines), (0, ["OC none"]))
        self.assertEqual(self.calls, [])

    def test_oc_groups_leave_out_tasks_that_are_already_done(self):
        info = self.info()
        Path(self.work, "tasks", "T01.md").write_text("body\n", encoding="utf-8")
        Path(self.work, "tasks", "T01.md.ok").write_text("1", encoding="utf-8")
        self.assertEqual(hp_write._oc_groups(info, self.work), [("O01", ["T02"], "std")])
        self.assertEqual(hp_write._oc_groups(info), [("O01", ["T01", "T02"], "std")])
        Path(self.work, "tasks", "T02.md").write_text("body\n", encoding="utf-8")
        Path(self.work, "tasks", "T02.md.ok").write_text("1", encoding="utf-8")
        self.assertEqual(hp_write._oc_groups(info, self.work), [])

    def test_oc_write_rewrites_only_pending_tasks_and_keeps_a_reviewed_body(self):
        kept = Path(self.work, "tasks", "T01.md")
        kept.write_text("reviewer fixed this body\n", encoding="utf-8")
        Path(self.work, "tasks", "T01.md.ok").write_text("1", encoding="utf-8")
        with self.fake([{"text": GOOD_T01 + "\n" + GOOD_T02}]):
            rc, lines = self.run_oc_write()
        self.assertEqual(rc, 0)
        self.assertEqual(kept.read_text(encoding="utf-8"), "reviewer fixed this body\n")
        self.assertTrue(lines[0].startswith("OC O01 oc:std OK T02 — "), lines[0])
        self.assertEqual(len(self.calls), 1)

    def test_oc_write_with_every_task_done_runs_nothing(self):
        for tid in ("T01", "T02"):
            Path(self.work, "tasks", tid + ".md").write_text("body\n", encoding="utf-8")
            Path(self.work, "tasks", tid + ".md.ok").write_text("1", encoding="utf-8")
        with self.fake([]):
            rc, lines = self.run_oc_write()
        self.assertEqual((rc, lines, self.calls), (0, ["OC none"], []))

    def test_non_retryable_kinds_come_from_hybrid_shared(self):
        self.assertFalse(hasattr(hp_write, "NON_RETRYABLE"))

    def test_group_crash_is_contained(self):
        with mock.patch.object(hp_write, "run_group", side_effect=RuntimeError("boom")):
            rc, lines = self.run_oc_write()
        self.assertEqual(rc, 0)
        self.assertEqual(len(lines), 3, lines)
        self.assertEqual(head(lines[0]), ["OC-ERROR", "hybrid-writing-plans", "O01", "tier=std"])
        self.assertIn(" kind=crash :: RuntimeError: boom", lines[0])
        self.assertEqual(lines[1], "OC O01 oc:std FALLBACK (crash) passed=- failed=T01,T02 — 0 rounds — 0s")
        self.assertEqual(lines[2], "OC-WRITE done 0/1 groups")
        marker = self.marker("O01")
        self.assertEqual((marker["reason"], marker["tasks"]), ("crash", ["T01", "T02"]))
        self.assertEqual(marker["errors"]["T01"], ["RuntimeError: boom"])
        self.assertFalse(os.path.exists(os.path.join(self.work, "oc", "oc-write.pid")))

    def test_each_tier_reports_its_own_failure(self):
        info = self.info()
        info["preset"] = "opencode"
        info["groups"] = {"O01": ["T01"], "O02": ["T02"]}
        info["backend"] = {"O01": "oc:std", "O02": "oc:deep"}
        info["oc"]["tiers"]["deep"] = dict(TIER_STD, model="zai-coding-plan/glm-5.3-deep")
        self.save_info(info)
        Path(self.work, "briefs", "O02.oc.md").write_text("oc brief for T02\n", encoding="utf-8")
        failure = {"rc": 1, "reason": "auth", "errors": ["APIError: subscription expired"],
                   "note": "APIError: subscription expired"}
        with self.fake([dict(failure), dict(failure)]):
            rc, lines = self.run_oc_write()
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.calls), 2)
        errors = [x for x in lines if x.startswith("OC-ERROR ")]
        self.assertEqual(sorted(x.split()[3] for x in errors), ["tier=deep", "tier=std"])
        self.assertEqual(lines[-1], "OC-WRITE done 0/2 groups")

    def test_skipped_group_is_summarised_once(self):
        info = self.info()
        info["preset"] = "opencode"
        info["groups"] = {"O01": ["T01"], "O02": ["T02"]}
        info["backend"] = {"O01": "oc:std", "O02": "oc:std"}
        info["oc"]["tiers"]["std"]["max_parallel"] = 1
        self.save_info(info)
        Path(self.work, "briefs", "O02.oc.md").write_text("oc brief for T02\n", encoding="utf-8")
        failure = {"rc": 1, "reason": "auth", "errors": ["APIError: subscription expired"],
                   "note": "APIError: subscription expired"}
        with self.fake([failure]):
            rc, lines = self.run_oc_write()
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(len([x for x in lines if " kind=auth " in x]), 1)
        summary = [x for x in lines if " kind=breaker " in x]
        self.assertEqual(len(summary), 1)
        self.assertEqual(lines[-2], summary[0])
        self.assertEqual(lines[-1], "OC-WRITE done 0/2 groups")
        logged = Path(self.work, "oc", "oc-errors.jsonl").read_text(encoding="utf-8")
        self.assertIn("kind=breaker", logged)

    def test_groups_beyond_max_parallel_queue_for_a_slot_and_still_finish(self):
        info = self.info()
        info["groups"] = {"O01": ["T01"], "O02": ["T02"]}
        info["backend"] = {"O01": "oc:std", "O02": "oc:std"}
        info["oc"]["tiers"]["std"]["max_parallel"] = 1
        self.save_info(info)
        Path(self.work, "briefs", "O02.oc.md").write_text("oc brief for T02\n", encoding="utf-8")
        both = {"text": GOOD_T01 + "\n" + GOOD_T02}
        with self.fake([dict(both), dict(both)]):
            rc, lines = self.run_oc_write()
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.calls), 2)
        self.assertEqual([x for x in lines if x.startswith(("OC-ERROR", "OC-WARN"))], [])
        self.assertEqual(sorted(x.split()[1] for x in lines if x.startswith("OC O")), ["O01", "O02"])
        self.assertEqual(lines[-1], "OC-WRITE done 2/2 groups")

    def test_group_lines_print_before_other_groups_finish(self):
        info = self.info()
        info["groups"] = {"O01": ["T01"], "O02": ["T02"]}
        info["backend"] = {"O01": "oc:std", "O02": "oc:std"}
        self.save_info(info)
        seen = threading.Event()
        released = []

        class Spy(io.StringIO):
            def write(self, text):
                if text.startswith("OC O01 "):
                    seen.set()
                return super().write(text)

        def fake_run_group(plan_path, gid, ids, tier, shared):
            if gid == "O02":
                released.append(seen.wait(10))
            return {"gid": gid, "outcome": "ok", "oc_lines": [],
                    "line": "OC {} oc:{} OK {} — 1 rounds — 0s".format(gid, tier, ",".join(ids))}

        with redirect_stdout(Spy()), mock.patch.object(hp_write, "run_group", side_effect=fake_run_group):
            hp_write.oc_write(self.plan)
        self.assertEqual(released, [True])


class SigtermTest(HpWriteBase):
    def test_sigterm_kills_the_opencode_process_groups_and_removes_the_pid_file(self):
        pid_file = Path(self.tmp) / "grandchild.pid"
        script = Path(self.tmp) / "sleepy.json"
        script.write_text(json.dumps({"grandchild": str(pid_file), "sleep": 60, "text": "x"}), encoding="utf-8")
        env = dict(os.environ, HYBRID_WRITING_PLANS_FAKE_SCRIPT=str(script), PYTHONDONTWRITEBYTECODE="1")
        tool = str(Path(hp_write.__file__).with_name("plan_tool.py"))
        proc = subprocess.Popen([sys.executable, tool, "oc-write", self.plan], env=env, cwd=str(self.repo),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        try:
            deadline = time.time() + 30
            while not pid_file.exists() and time.time() < deadline:
                time.sleep(0.1)
            self.assertTrue(pid_file.exists(), "the fake opencode never started")
            child = int(pid_file.read_text(encoding="utf-8"))
            os.kill(child, 0)
            proc.send_signal(signal.SIGTERM)
            out, err = proc.communicate(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
        self.assertEqual(proc.returncode, 0, out + err)
        self.assertIn("terminated by SIGTERM", out)
        for _ in range(50):
            try:
                os.kill(child, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            os.kill(child, signal.SIGKILL)
            self.fail("the opencode process group survived SIGTERM of oc-write")
        self.assertFalse(os.path.exists(os.path.join(self.work, "oc", "oc-write.pid")))
