import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hp_wait  # noqa: E402
import hp_write  # noqa: E402


class WaitCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.env = mock.patch.dict(os.environ, {
            "HOME": self.tmp,
            "HP_ROUTING": os.path.join(self.tmp, "routing.json"),
            "HP_DOCTOR_CACHE": os.path.join(self.tmp, "doctor.json"),
            "HP_TELEMETRY": os.path.join(self.tmp, "lanes.jsonl"),
        })
        self.env.start()
        self.work = os.path.join(self.tmp, "work")
        self.oc = hp_write.oc_dir(self.work)
        os.makedirs(self.oc, exist_ok=True)
        os.makedirs(os.path.join(self.work, "tasks"), exist_ok=True)
        self.plan = os.path.join(self.tmp, "plan.md")

    def tearDown(self):
        self.env.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_pid(self, text):
        with open(os.path.join(self.oc, "oc-write.pid"), "w", encoding="utf-8") as f:
            f.write(text)

    def write_fb(self, gid, tasks, reason="lint", sent=False):
        fb = {"gid": gid, "reason": reason, "tasks": tasks,
              "brief": os.path.join(self.work, "briefs", gid + "F.md"),
              "model": "sonnet", "subagent_type": "plan-task-writer",
              "errors": {}, "t": "2026-09-28T00:00:00Z"}
        path = os.path.join(self.oc, gid + ".fallback")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(fb, f)
        if sent:
            with open(path + ".sent", "w") as f:
                f.write("1")
        return fb

    def mark_done(self, tid):
        md = os.path.join(self.work, "tasks", tid + ".md")
        with open(md, "w", encoding="utf-8") as f:
            f.write("body\n")
        with open(md + ".ok", "w") as f:
            f.write("1")


class TestOcAlive(WaitCase):
    def test_missing_pid_file_is_not_alive(self):
        self.assertFalse(hp_wait.oc_alive(self.work))

    def test_missing_work_dir_is_not_alive(self):
        self.assertFalse(hp_wait.oc_alive(os.path.join(self.tmp, "nowhere")))

    def test_live_pid_is_alive(self):
        self.write_pid(str(os.getpid()))
        self.assertTrue(hp_wait.oc_alive(self.work))

    def test_json_pid_file_is_read(self):
        self.write_pid(json.dumps({"t": "2026-09-28T00:00:00Z", "pid": os.getpid()}))
        self.assertTrue(hp_wait.oc_alive(self.work))

    def test_dead_pid_is_not_alive(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        self.write_pid(str(p.pid))
        self.assertFalse(hp_wait.oc_alive(self.work))

    def test_garbage_pid_file_is_not_alive(self):
        self.write_pid("not-a-pid")
        self.assertFalse(hp_wait.oc_alive(self.work))


class TestFallbackLines(WaitCase):
    def test_fallback_line_matches_spec_format(self):
        fb = {"gid": "O02", "reason": "lint", "tasks": ["T06"], "brief": "/w/briefs/O02F.md",
              "model": "sonnet", "subagent_type": "plan-task-writer", "errors": {}, "t": "x"}
        self.assertEqual(
            hp_wait.fallback_line(fb),
            "FALLBACK O02 (lint) T06 → Agent subagent_type=plan-task-writer model=sonnet "
            "description 'plan O02F' prompt: Read /w/briefs/O02F.md and follow it exactly.")

    def test_fallback_line_joins_tasks_with_commas(self):
        fb = {"gid": "O01", "reason": "stall", "tasks": ["T03", "T04"], "brief": "/w/briefs/O01F.md",
              "model": "opus", "subagent_type": "general-purpose"}
        line = hp_wait.fallback_line(fb)
        self.assertTrue(line.startswith("FALLBACK O01 (stall) T03,T04 → Agent subagent_type=general-purpose model=opus "))
        self.assertIn("description 'plan O01F'", line)

    def test_pending_lines_only_unsent_and_marks_sent(self):
        fb1 = self.write_fb("O01", ["T01", "T02"], reason="timeout")
        self.write_fb("O02", ["T05"], sent=True)
        lines = hp_wait.pending_fallback_lines(self.work)
        self.assertEqual(lines, [hp_wait.fallback_line(fb1)])
        self.assertTrue(os.path.exists(os.path.join(self.oc, "O01.fallback.sent")))
        self.assertEqual(hp_wait.pending_fallback_lines(self.work), [])

    def test_pending_lines_sorted_by_gid(self):
        fb2 = self.write_fb("O02", ["T05"])
        fb1 = self.write_fb("O01", ["T01"])
        self.assertEqual(hp_wait.pending_fallback_lines(self.work),
                         [hp_wait.fallback_line(fb1), hp_wait.fallback_line(fb2)])

    def test_pending_lines_skip_unreadable_marker(self):
        with open(os.path.join(self.oc, "O03.fallback"), "w", encoding="utf-8") as f:
            f.write("{not json")
        self.assertEqual(hp_wait.pending_fallback_lines(self.work), [])
        self.assertFalse(os.path.exists(os.path.join(self.oc, "O03.fallback.sent")))

    def test_pending_lines_without_oc_dir(self):
        self.assertEqual(hp_wait.pending_fallback_lines(os.path.join(self.tmp, "nowhere")), [])


class TestRunnerDied(WaitCase):
    def setUp(self):
        super().setUp()
        self.info = {"tasks": ["T01", "T02", "T03"],
                     "groups": {"O01": ["T01", "T02"], "T03": ["T03"]},
                     "backend": {"O01": "oc:std", "T03": "claude"}}
        self.calls = []
        test = self

        def fake_write_fallback(plan_path, gid, task_ids, reason, errors):
            test.calls.append((plan_path, gid, list(task_ids), reason, errors))
            return test.write_fb(gid, list(task_ids), reason=reason)

        self.patch = mock.patch.object(hp_write, "write_fallback", side_effect=fake_write_fallback)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        super().tearDown()

    def dead_pid(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        self.write_pid(str(p.pid))

    def test_live_runner_writes_nothing(self):
        self.write_pid(str(os.getpid()))
        self.assertEqual(hp_wait.runner_died(self.plan, self.work, self.info, 100.0), [])
        self.assertEqual(self.calls, [])

    def test_dead_runner_writes_fallback_for_unfinished_oc_tasks(self):
        self.dead_pid()
        self.mark_done("T01")
        lines = hp_wait.runner_died(self.plan, self.work, self.info, 42.0)
        self.assertEqual(len(self.calls), 1)
        plan_path, gid, ids, reason, errors = self.calls[0]
        self.assertEqual((plan_path, gid, ids, reason), (self.plan, "O01", ["T02"], "runner-died"))
        self.assertEqual(sorted(errors), ["T02"])
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("FALLBACK O01 (runner-died) T02 → Agent "))
        self.assertFalse(os.path.exists(os.path.join(self.oc, "O01.fallback.sent")))
        self.assertEqual(hp_wait.pending_fallback_lines(self.work), lines)
        self.assertTrue(os.path.exists(os.path.join(self.oc, "O01.fallback.sent")))
        self.assertEqual(hp_wait.runner_died(self.plan, self.work, self.info, 50.0), [])
        self.assertEqual(len(self.calls), 1)

    def test_pending_fallback_blocks_runner_died(self):
        self.dead_pid()
        self.write_fb("O09", ["T09"])
        self.assertEqual(hp_wait.runner_died(self.plan, self.work, self.info, 100.0), [])
        self.assertEqual(self.calls, [])

    def test_group_with_sent_fallback_is_skipped(self):
        self.dead_pid()
        self.write_fb("O01", ["T01", "T02"], reason="lint", sent=True)
        self.assertEqual(hp_wait.runner_died(self.plan, self.work, self.info, 100.0), [])
        self.assertEqual(self.calls, [])

    def test_all_oc_tasks_done_writes_nothing(self):
        self.dead_pid()
        self.mark_done("T01")
        self.mark_done("T02")
        self.assertEqual(hp_wait.runner_died(self.plan, self.work, self.info, 100.0), [])
        self.assertEqual(self.calls, [])

    def test_missing_pid_file_waits_for_grace_period(self):
        early = hp_wait.RUNNER_GRACE_S - 1.0
        self.assertEqual(hp_wait.runner_died(self.plan, self.work, self.info, early), [])
        self.assertEqual(self.calls, [])
        lines = hp_wait.runner_died(self.plan, self.work, self.info, hp_wait.RUNNER_GRACE_S)
        self.assertEqual([c[2] for c in self.calls], [["T01", "T02"]])
        self.assertEqual(len(lines), 1)

    def test_info_without_backend_writes_nothing(self):
        self.dead_pid()
        self.assertEqual(hp_wait.runner_died(self.plan, self.work, {"tasks": ["T01"], "groups": {"T01": ["T01"]}}, 100.0), [])
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
