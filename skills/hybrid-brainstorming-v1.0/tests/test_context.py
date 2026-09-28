import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

CONTEXT_SH = Path(__file__).resolve().parents[1] / "scripts" / "context.sh"

UNAVAILABLE = "opencode: unavailable → preset claude (run bslane.py doctor)"


class TestContextSh(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cwd = self.root / "work"
        self.cwd.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        self.marker = self.root / "opencode-ran.marker"
        self.fake_bin = self.root / "opencode"
        self.fake_bin.write_text(
            "#!/bin/sh\ntouch '%s'\necho fake-opencode\n" % self.marker
        )
        self.fake_bin.chmod(self.fake_bin.stat().st_mode | stat.S_IEXEC)
        self.routing_path = self.root / "routing.json"
        self.doctor_path = self.root / "doctor.json"

    def run_context(self, oc_bin, routing_path=None, doctor_path=None):
        env = dict(os.environ)
        env["HOME"] = str(self.home)
        env["HB_OC_BIN"] = oc_bin
        if routing_path is not None:
            env["HB_ROUTING"] = str(routing_path)
        else:
            env.pop("HB_ROUTING", None)
        if doctor_path is not None:
            env["HB_DOCTOR_CACHE"] = str(doctor_path)
        else:
            env.pop("HB_DOCTOR_CACHE", None)
        result = subprocess.run(
            ["sh", str(CONTEXT_SH)],
            cwd=str(self.cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result

    def write_routing(self, payload, pretty=False):
        text = json.dumps(payload, indent=2) if pretty else json.dumps(payload)
        self.routing_path.write_text(text)

    def write_doctor(self, payload):
        self.doctor_path.write_text(json.dumps(payload))

    def test_status_line_printed_verbatim_with_spaces_preserved(self):
        status_line = "opencode:  v2.0.18   preset=hybrid  locate=oc:lite websearch=off"
        self.write_doctor(
            {"t": "2026-09-28T12:00:00Z", "version": "2.0.18", "status_line": status_line}
        )
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            doctor_path=self.doctor_path,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(status_line, result.stdout)
        self.assertFalse(self.marker.exists())

    def test_missing_opencode_binary_prints_unavailable(self):
        self.write_doctor(
            {"t": "2026-09-28T12:00:00Z", "version": "2.0.18", "status_line": "opencode: v2.0.18 preset=claude"}
        )
        result = self.run_context(
            oc_bin=str(self.root / "no-such-opencode-binary"),
            routing_path=self.routing_path,
            doctor_path=self.doctor_path,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(UNAVAILABLE, result.stdout)
        self.assertFalse(self.marker.exists())

    def test_missing_doctor_cache_prints_unavailable(self):
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            doctor_path=self.root / "no-such-doctor.json",
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(UNAVAILABLE, result.stdout)
        self.assertFalse(self.marker.exists())

    def test_empty_status_line_prints_unavailable(self):
        self.write_doctor({"t": "2026-09-28T12:00:00Z", "version": "2.0.18", "status_line": ""})
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            doctor_path=self.doctor_path,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(UNAVAILABLE, result.stdout)
        self.assertFalse(self.marker.exists())

    def test_absent_status_line_key_prints_unavailable(self):
        self.write_doctor({"t": "2026-09-28T12:00:00Z", "version": "2.0.18"})
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            doctor_path=self.doctor_path,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(UNAVAILABLE, result.stdout)
        self.assertFalse(self.marker.exists())

    def test_status_line_ignores_routing_file_oc_tiers(self):
        self.write_routing(
            {
                "preset": "hybrid",
                "roles": {
                    "locate": "lite",
                    "explore": "std",
                    "fact": "lite",
                    "research": "claude",
                    "draft": "claude",
                },
            },
            pretty=True,
        )
        all_claude_line = (
            "opencode: v2.0.18 preset=claude locate=claude explore=claude "
            "fact=claude research=claude draft=claude websearch=off (doctor 2026-09-28)"
        )
        self.write_doctor(
            {"t": "2026-09-28T12:00:00Z", "version": "2.0.18", "status_line": all_claude_line}
        )
        result = self.run_context(
            oc_bin=str(self.fake_bin),
            routing_path=self.routing_path,
            doctor_path=self.doctor_path,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn(all_claude_line, result.stdout)
        self.assertNotIn("locate=oc:lite", result.stdout)
        self.assertFalse(self.marker.exists())

    def test_shell_syntax_is_valid(self):
        result = subprocess.run(
            ["sh", "-n", str(CONTEXT_SH)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
