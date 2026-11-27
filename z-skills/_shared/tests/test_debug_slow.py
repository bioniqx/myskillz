"""Slow mode stamp: probe LANE label, SLOW measure hints, close falsifier gate."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOL = (Path(__file__).resolve().parents[2]
        / "z-systematic-debugging" / "scripts" / "debug_tool.py")
_spec = importlib.util.spec_from_file_location("debug_tool_slow", str(TOOL))
DT = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(DT)

NAME_ERR = ('  File "app.py", line 2, in <module>\n'
            "NameError: name 'foo' is not defined")


class SlowRepo(unittest.TestCase):
    """A throwaway git repo plus helpers to stamp a mode and drive the tool."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="sdslow."))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        subprocess.run(["git", "init", "-q", self.tmp], check=True)
        Path(self.tmp, "app.py").write_text("x = 1\nprint(foo)\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")
        self.git("commit", "-q", "--allow-empty", "-m", "second")

    def git(self, *args):
        subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
                        "-c", "commit.gpgsign=false"] + list(args), cwd=self.tmp,
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def stamp(self, text):
        d = Path(self.tmp, ".claude", "dev-team")
        d.mkdir(parents=True, exist_ok=True)
        (d / "mode").write_text(text)

    def main(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = DT.main(argv)
        return rc, buf.getvalue()

    def probe(self, error):
        argv = ["probe", "--error", error, "--dir", self.tmp]
        return self.main(argv)

    def close(self, records, report=""):
        d = Path(self.tmp, ".debug")
        d.mkdir(parents=True, exist_ok=True)
        (d / "experiments.json").write_text(json.dumps(records))
        Path(self.tmp, "report.txt").write_text(report)
        return self.main(["close", "--experiments", str(d / "experiments.json"),
                          "--report", str(Path(self.tmp, "report.txt"))])

    def saved_records(self):
        return json.loads(Path(self.tmp, ".debug", "experiments.json").read_text())


class ProbeLaneLabelTests(SlowRepo):
    def test_fast_lane_relabels_slow_only_under_slow_stamp(self):
        self.stamp("slow 123\n")
        rc, out = self.probe(NAME_ERR)
        self.assertEqual(rc, 0)
        self.assertIn("LANE: SLOW", out)
        self.assertNotIn("LANE: FAST", out)

    def test_fast_lane_label_unchanged_without_stamp(self):
        rc, out = self.probe(NAME_ERR)
        self.assertEqual(rc, 0)
        self.assertIn("LANE: FAST", out)
        self.assertNotIn("LANE: SLOW", out)

    def test_fast_lane_label_unchanged_under_fast_stamp(self):
        self.stamp("fast 123\n")
        rc, out = self.probe(NAME_ERR)
        self.assertEqual(rc, 0)
        self.assertIn("LANE: FAST", out)

    def test_swarm_lane_keeps_its_label_under_slow_stamp(self):
        self.stamp("slow 123\n")
        rc, out = self.probe("the build sometimes fails")
        self.assertEqual(rc, 0)
        self.assertIn("LANE: SWARM", out)


class SlowMeasureHintTests(SlowRepo):
    def test_slow_stamp_measures_flaky_at_200(self):
        self.stamp("slow 123\n")
        rc, out = self.probe("the build sometimes fails")
        self.assertEqual(rc, 0)
        self.assertIn("stress.sh -n 200", out)
        self.assertNotIn("stress.sh -n 40", out)

    def test_no_stamp_keeps_the_40_measure_hint(self):
        rc, out = self.probe("the build sometimes fails")
        self.assertEqual(rc, 0)
        self.assertIn("stress.sh -n 40", out)

    def test_no_git_history_is_read_even_for_a_regression_phrase(self):
        self.stamp("slow 123\n")
        rc, out = self.probe("the checkout worked before the upgrade")
        self.assertEqual(rc, 0)
        self.assertNotIn("bisect", out.lower())
        self.assertNotIn("== HISTORY ==", out)

    def test_flaky_names_no_bisect(self):
        self.stamp("slow 123\n")
        rc, out = self.probe("the build sometimes fails")
        self.assertEqual(rc, 0)
        self.assertNotIn("bisect-parallel.sh", out)


class SlowCloseFalsifierTests(SlowRepo):
    def records(self, **extra):
        rec = {"id": "h1", "verdict": "CONFIRMED", "role": "diagnose"}
        rec.update(extra)
        return [rec]

    def test_slow_missing_falsifier_prints_no_root_cause(self):
        self.stamp("slow 123\n")
        rc, out = self.close(self.records())
        self.assertEqual(rc, 2)
        self.assertNotIn("ROOT CAUSE", out)
        self.assertIn("FAIL falsify - h1", out)
        self.assertIn("NEXT: nobody is asked. Write ONE falsify command for h1", out)
        self.assertIn("on the main thread", out)
        self.assertNotIn("(ask ", out)
        self.assertNotIn("ask the user", out)

    def test_slow_nonzero_falsify_prints_root_cause_and_stores_exit(self):
        self.stamp("slow 123\n")
        rc, out = self.close(self.records(falsify="false"))
        self.assertEqual(rc, 0)
        self.assertIn("ROOT CAUSE: h1", out)
        self.assertIn("DECISION pick=h1", out)
        self.assertEqual(self.saved_records()[0]["falsify_exit"], 1)

    def test_slow_zero_falsify_is_treated_like_missing(self):
        self.stamp("slow 123\n")
        rc, out = self.close(self.records(falsify="true"))
        self.assertEqual(rc, 2)
        self.assertNotIn("ROOT CAUSE", out)
        self.assertEqual(self.saved_records()[0]["falsify_exit"], 0)

    def test_stored_exit_is_not_trusted_the_command_is_rerun(self):
        self.stamp("slow 123\n")
        rc, out = self.close(self.records(falsify="true", falsify_exit=1))
        self.assertEqual(rc, 2)
        self.assertNotIn("ROOT CAUSE", out)
        self.assertEqual(self.saved_records()[0]["falsify_exit"], 0)

    def test_slow_asks_twice_then_states_the_leftover(self):
        self.stamp("slow 123\n")
        rc1, out1 = self.close(self.records())
        rc2, out2 = self.close(self.saved_records())
        rc3, out3 = self.close(self.saved_records())
        self.assertEqual((rc1, rc2, rc3), (2, 2, 2))
        self.assertIn("try 1 of 2", out1)
        self.assertIn("try 2 of 2", out2)
        self.assertIn("Leftover: h1 stays unconfirmed", out3)
        self.assertNotIn("try 3", out3)
        self.assertIn("finish it on the main thread", out3)
        self.assertIn("name what is left in the summary", out3)
        self.assertNotIn("to the user", out3)
        for out in (out1, out2, out3):
            self.assertNotIn("ROOT CAUSE", out)

    def test_status_only_confirmed_does_not_pass_the_slow_gate(self):
        self.stamp("slow 123\n")
        rc, out = self.close([{"id": "h1", "status": "CONFIRMED", "role": "diagnose",
                               "falsify": "false", "falsify_exit": 1}])
        self.assertEqual(rc, 2)
        self.assertNotIn("ROOT CAUSE", out)

    def test_no_stamp_close_accepts_today_single_confirmed(self):
        rc, out = self.close(self.records())
        self.assertEqual(rc, 0)
        self.assertIn("ROOT CAUSE: h1", out)
        self.assertIn("DECISION pick=h1", out)

    def test_fast_stamp_close_accepts_today_single_confirmed(self):
        self.stamp("fast 123\n")
        rc, out = self.close(self.records())
        self.assertEqual(rc, 0)
        self.assertIn("ROOT CAUSE: h1", out)

    def test_slow_unpicked_close_hands_nothing_to_the_user(self):
        self.stamp("slow 123\n")
        rc, out = self.close([])
        self.assertEqual(rc, 2)
        self.assertIn("NEXT: do not write a root cause. Nobody is asked", out)
        self.assertIn("name what is left in the summary", out)
        self.assertNotIn("ask the user", out)

    def test_no_stamp_unpicked_close_keeps_asking_the_user(self):
        rc, out = self.close([])
        self.assertEqual(rc, 2)
        self.assertIn("NEXT: do not write a root cause. Run the experiment the line names, "
                      "or ask the user.", out)
        self.assertNotIn("Nobody is asked", out)


class NoCauseCloseTests(SlowRepo):
    """`close` on a report that legally says NO CAUSE: pick=none is not a pick."""

    def test_under_a_slow_stamp_it_names_the_summary(self):
        self.stamp("slow 123\n")
        rc, out = self.close([{"id": "h1", "verdict": "REFUTED", "role": "diagnose"}],
                             report="NO CAUSE\n")
        self.assertEqual(rc, 0, out)
        self.assertIn("DECISION pick=none", out)
        self.assertIn("NEXT: no experiment is confirmed, so the report says NO CAUSE; "
                      "name what is left in the summary.", out)
        self.assertNotIn("the cause is the id", out)

    def test_without_a_stamp_it_keeps_the_short_line(self):
        rc, out = self.close([{"id": "h1", "verdict": "REFUTED", "role": "diagnose"}],
                             report="NO CAUSE\n")
        self.assertEqual(rc, 0, out)
        self.assertIn("NEXT: no experiment is confirmed, so the report says NO CAUSE.", out)
        self.assertNotIn("summary", out)


class WorktreeRetryTests(unittest.TestCase):
    """Under load git now and then fails a worktree add; one retry after a prune."""

    def test_a_failed_worktree_add_is_retried_once_after_a_prune(self):
        calls = []

        def fake_sh(cmd, cwd=None, timeout=None, env=None):
            calls.append(cmd)
            if cmd.startswith("git worktree add"):
                return (1, "fatal: failed to read commondir") if len(calls) == 1 else (0, "")
            return (0, "")

        with mock.patch.object(DT, "sh", fake_sh):
            self.assertIsNone(DT.make_worktree("/nowhere", "/nowhere/.debug/w/x", [], None))
        self.assertTrue(calls[0].startswith("git worktree add --detach --force"), calls)
        self.assertEqual(calls[1], "git worktree prune")
        self.assertEqual(calls[0], calls[2])

    def test_a_second_failure_is_still_reported(self):
        def fake_sh(cmd, cwd=None, timeout=None, env=None):
            return (1, "fatal: nope") if cmd.startswith("git worktree add") else (0, "")

        with mock.patch.object(DT, "sh", fake_sh):
            err = DT.make_worktree("/nowhere", "/nowhere/.debug/w/x", [], None)
        self.assertTrue(err and err.startswith("worktree add failed"), err)


if __name__ == "__main__":
    unittest.main()
