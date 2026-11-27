"""SLOW engine gates: the mutant procedure and its hold rule. No model calls."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DEVTEAM = os.path.join(HERE, "..", "..", "z-dev-team", "scripts", "devteam.py")


def _load_devteam():
    spec = importlib.util.spec_from_file_location("devteam_slow_under_test", DEVTEAM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


devteam = _load_devteam()

MOD = "def inc(n):\n    return n + 1\n"
RUNNER = ("\n"
          "if __name__ == '__main__':\n"
          "    import unittest\n"
          "    unittest.main()\n")
WEAK_TEST = ("import unittest\n"
             "from mod import inc\n"
             "\n"
             "class T(unittest.TestCase):\n"
             "    def test_inc(self):\n"
             "        result = inc(1)\n"
             "        assert result == 2\n"
             + RUNNER)
# deleting the first assert also deletes the walrus binding, so the remaining
# assert fails: the suite can fail -> MUTANT ok
OK_TEST = ("import unittest\n"
           "from mod import inc\n"
           "\n"
           "class T(unittest.TestCase):\n"
           "    def test_inc(self):\n"
           "        assert (got := inc(1)) == 2\n"
           "        assert inc(got) == 3\n"
           + RUNNER)
NO_ASSERT_TEST = ("import unittest\n"
                  "from mod import inc\n"
                  "\n"
                  "class T(unittest.TestCase):\n"
                  "    def test_inc(self):\n"
                  "        inc(1)\n"
                  + RUNNER)


def _py():
    return os.path.basename(sys.executable)


class MutantGateTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="devteam-mutant-")
        self.addCleanup(shutil.rmtree, self.dir, True)

    def write(self, name, body):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        return name

    def gate(self, files, test_file):
        cmd = "%s %s" % (_py(), test_file)
        return devteam.run_mutant_gate(files, cmd, self.dir, 60)

    def test_a_suite_that_still_passes_is_weak(self):
        self.write("mod.py", MOD)
        name = self.write("test_weak.py", WEAK_TEST)
        before = open(os.path.join(self.dir, name), encoding="utf-8").read()
        res = self.gate([name], name)
        self.assertEqual(res["verdict"], "weak")
        self.assertEqual(res["site"], 1)
        self.assertTrue(res["diff"])
        after = open(os.path.join(self.dir, name), encoding="utf-8").read()
        self.assertEqual(before, after, "the mutated file must be restored")

    def test_a_remaining_assert_that_fails_is_ok(self):
        self.write("mod.py", MOD)
        name = self.write("test_ok.py", OK_TEST)
        rc = subprocess.run([sys.executable, name], cwd=self.dir,
                            capture_output=True).returncode
        self.assertEqual(rc, 0, "the green suite itself must pass first")
        res = self.gate([name], name)
        self.assertEqual(res["verdict"], "ok")

    def test_no_assertion_shaped_line_is_skip(self):
        self.write("mod.py", MOD)
        name = self.write("test_none.py", NO_ASSERT_TEST)
        res = self.gate([name], name)
        self.assertEqual(res["verdict"], "skip")

    def test_a_file_that_does_not_parse_is_skipped_not_run(self):
        name = self.write("test_broken.py", "def test_x(:\n    assert 1\n")
        res = self.gate([name], "true")
        self.assertEqual(res["verdict"], "skip")

    def test_a_command_that_cannot_run_is_skip(self):
        self.write("mod.py", MOD)
        name = self.write("test_weak.py", WEAK_TEST)
        res = devteam.run_mutant_gate(
            [name], "definitely-not-a-command-xyz", self.dir, 5)
        self.assertEqual(res["verdict"], "skip")


class MutantRejectTests(unittest.TestCase):
    def slice(self, n=0):
        return {"id": "S1", "mutant_n": n, "history": [], "reject_n": 0}

    def test_weak_holds_with_the_diff_and_caps_at_two_reopens(self):
        proof = {"mutant": {"verdict": "weak", "file": "tests/a.py", "site": 1,
                            "diff": "--- a\n+++ b\n-del"}}
        s = self.slice()
        first = devteam.mutant_reject(s, "S1", proof)
        self.assertIn("MUTANT weak", first)
        self.assertIn("diff", first.lower())
        self.assertEqual(s["mutant_n"], 1)
        second = devteam.mutant_reject(self.slice(1), "S1", proof)
        self.assertIn("MUTANT weak", second)
        s3 = self.slice(2)
        third = devteam.mutant_reject(s3, "S1", proof)
        self.assertIn("leftover after 2", third)
        self.assertIn("does not merge", third)
        self.assertTrue(s3["mutant_leftover"])
        # SLOW contract: a cap the engine reaches is finished on the main thread and named in the summary
        self.assertIn("on the main thread", third)
        self.assertIn("name it in the summary", third)
        self.assertIn("nobody is asked", third)
        self.assertNotIn("to the user", third)

    def test_ok_skip_and_none_do_not_hold(self):
        for proof in ({"mutant": {"verdict": "ok"}}, {"mutant": {"verdict": "skip"}}, {}, None):
            self.assertIsNone(devteam.mutant_reject(self.slice(), "S1", proof))


class ModeStampTests(unittest.TestCase):
    def test_first_field_of_the_stamp_file(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        self.assertEqual(devteam.mode_stamp(root), "")
        sd = os.path.join(root, ".claude", "dev-team")
        os.makedirs(sd)
        with open(os.path.join(sd, "mode"), "w", encoding="utf-8") as fh:
            fh.write("slow 1770000000\n")
        self.assertEqual(devteam.mode_stamp(root), "slow")
        with open(os.path.join(sd, "mode"), "w", encoding="utf-8") as fh:
            fh.write("fast 1770000000\n")
        self.assertEqual(devteam.mode_stamp(root), "fast")


class SlowHintTests(unittest.TestCase):
    """Printed SLOW wording: the Conductor answers itself; the full-pace lines stay byte for byte."""

    def test_a_blocked_lane_under_a_slow_stamp_is_answered_by_the_conductor(self):
        line = devteam.blocked_hint("S9", True)
        self.assertIn("SendMessage the S9 agent", line)
        self.assertIn("nobody is asked", line)
        self.assertIn("irreversible action", line)
        self.assertNotIn("ask now", line)

    def test_a_blocked_lane_without_a_slow_stamp_keeps_the_full_pace_line(self):
        # the engine's own line, arrow included (U+2192), byte for byte
        self.assertEqual(
            devteam.blocked_hint("S9", False),
            "  \u2192 SendMessage the S9 agent the answer (plan/contracts) and it resumes in its worktree; "
            "if only the user can answer, ask now and keep everything else running.")

    def test_the_third_lint_failure_asks_nobody_under_a_slow_stamp(self):
        self.assertEqual(devteam.lint_stuck_hint(False), "ASK the user")
        line = devteam.lint_stuck_hint(True)
        self.assertIn("nobody is asked", line)
        self.assertIn("then `start` again", line)
        self.assertNotIn("ASK", line)


class MutantCliTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="devteam-mutant-cli-")
        self.addCleanup(shutil.rmtree, self.root, True)
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=self.root, check=True)
        for name, body in (("mod.py", MOD), ("test_weak.py", WEAK_TEST)):
            with open(os.path.join(self.root, name), "w", encoding="utf-8") as fh:
                fh.write(body)

    def run_cli(self, test_file):
        return subprocess.run(
            [sys.executable, DEVTEAM, "mutant", "--file", test_file,
             "--cmd", "%s %s" % (_py(), test_file)],
            cwd=self.root, capture_output=True, text=True, timeout=120)

    def test_weak_exits_one_and_restores_the_file(self):
        before = open(os.path.join(self.root, "test_weak.py"), encoding="utf-8").read()
        proc = self.run_cli("test_weak.py")
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("MUTANT weak", proc.stdout)
        self.assertIn("Mutant diff", proc.stdout)
        after = open(os.path.join(self.root, "test_weak.py"), encoding="utf-8").read()
        self.assertEqual(before, after)

    def test_ok_and_skip_are_named_in_the_summary_not_to_the_user(self):
        for name, body, verdict in (("test_ok.py", OK_TEST, "ok"),
                                    ("test_none.py", NO_ASSERT_TEST, "skip")):
            with open(os.path.join(self.root, name), "w", encoding="utf-8") as fh:
                fh.write(body)
            proc = self.run_cli(name)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            self.assertIn("Name MUTANT %s in the summary" % verdict, proc.stdout)
            self.assertNotIn("to the user", proc.stdout)

    def test_a_missing_file_is_a_usage_error(self):
        proc = subprocess.run(
            [sys.executable, DEVTEAM, "mutant", "--file", "nope.py", "--cmd", "true"],
            cwd=self.root, capture_output=True, text=True, timeout=60)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("no such file", (proc.stdout + proc.stderr))


if __name__ == "__main__":
    unittest.main()
