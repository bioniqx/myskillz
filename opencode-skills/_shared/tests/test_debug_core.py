import contextlib
import importlib.util
import io
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

_T16_DT_PATH = (Path(__file__).resolve().parents[2]
                / "oc-systematic-debugging" / "scripts" / "oc_debug_tool.py")
_t16_spec = importlib.util.spec_from_file_location("debug_tool_t16", str(_T16_DT_PATH))
DT16 = importlib.util.module_from_spec(_t16_spec)
_t16_spec.loader.exec_module(DT16)


def _t16_main(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = DT16.main(argv)
    return rc, buf.getvalue()


class _T16TmpRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="t16dbg.")
        subprocess.run(["git", "init", "-q", self.tmp], check=True)
        self.addCleanup(shutil.rmtree, self.tmp, True)


class DebugToolClampTest(unittest.TestCase):
    def test_zero_means_default(self):
        self.assertEqual(DT16.clamp(0, 8), 8)
        self.assertEqual(DT16.clamp("0", 8), 8)

    def test_negative_means_default(self):
        self.assertEqual(DT16.clamp(-3, 5), 5)

    def test_explicit_value_kept_and_capped(self):
        self.assertEqual(DT16.clamp(3, 8), 3)
        self.assertEqual(DT16.clamp(999, 8), DT16.MAXJ)
        self.assertEqual(DT16.clamp("x", 8), 8)


class DebugToolParallelDefaultTest(_T16TmpRepo):
    def test_run_default_is_parallel(self):
        rc, out = _t16_main(["run", "--dir", self.tmp, "true", "true", "true"])
        self.assertEqual(rc, 0)
        self.assertIn("(3 parallel,", out)

    def test_probe_extra_repros_stay_serial(self):
        # Overlapping runs would see the lock dir and exit 3 instead of 1.
        cmd = "mkdir lk 2>/dev/null || exit 3; sleep 0.3; rmdir lk; exit 1"
        rc, out = _t16_main(["probe", "--cmd", cmd, "--dir", self.tmp])
        self.assertEqual(rc, 0)
        self.assertIn("exit codes: [1, 1, 1]", out)
        self.assertNotIn("LANE: SWARM", out)


class DebugToolSwarmRouteTest(_T16TmpRepo):
    def test_traceback_is_not_a_race(self):
        self.assertIsNone(DT16.SWARM_RE.search("Traceback (most recent call last):"))
        self.assertIsNone(DT16.SWARM_RE.search("see the backtrace below"))

    def test_real_race_still_matches(self):
        self.assertIsNotNone(DT16.SWARM_RE.search("a data race in the pool"))
        self.assertIsNotNone(DT16.SWARM_RE.search("two writers race on the file"))

    def test_python_traceback_routes_standard(self):
        Path(self.tmp, "app.py").write_text("x = 1\nint('a')\n")
        err = ('Traceback (most recent call last):\n'
               '  File "app.py", line 2, in <module>\n'
               'ValueError: bad literal')
        rc, out = _t16_main(["probe", "--error", err, "--dir", self.tmp])
        self.assertEqual(rc, 0)
        self.assertIn("LANE: STANDARD", out)


class DebugToolFastNextQuoteTest(_T16TmpRepo):
    def test_fast_next_quotes_cmd(self):
        Path(self.tmp, "app.py").write_text("x = 1\nprint(foo)\n")
        err = ('  File "app.py", line 2, in <module>\n'
               "NameError: name 'foo' is not defined")
        cmd = 'test -f "missing file.txt"'
        rc, out = _t16_main(["probe", "--error", err, "--cmd", cmd, "--dir", self.tmp])
        self.assertEqual(rc, 0)
        self.assertIn("LANE: FAST", out)
        self.assertIn("oc_debug_tool.py run -- " + shlex.quote(cmd), out)


class DebugToolRunWallTest(_T16TmpRepo):
    def test_wall_is_real_elapsed_time(self):
        rc, out = _t16_main(["run", "-j", "1", "--dir", self.tmp, "sleep 0.4", "sleep 0.4"])
        self.assertEqual(rc, 0)
        m = re.search(r"\(1 parallel, ([\d.]+)s wall\)", out)
        self.assertIsNotNone(m, out)
        self.assertGreaterEqual(float(m.group(1)), 0.7)


class DebugToolDoctorTest(_T16TmpRepo):
    def run_doctor(self, *extra):
        old = os.getcwd()
        os.chdir(self.tmp)
        try:
            return _t16_main(["doctor"] + list(extra))
        finally:
            os.chdir(old)

    def test_doctor_reports_the_harness_and_has_no_api_rows(self):
        rc, out = self.run_doctor()
        self.assertEqual(rc, 0)
        self.assertIn("harness:", out)
        self.assertIn("oc-snapshot.sh:", out)
        for gone in ("api key", "base url", "tiers"):
            self.assertNotIn(gone, out)

    def test_doctor_has_no_ping_flag(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                DT16.main(["doctor", "--ping"])
        self.assertEqual(cm.exception.code, 2)
