import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "oc-requirements-code-audit", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import oc_audit as audit  # noqa: E402
import oc_harness  # noqa: E402

class Doctor(unittest.TestCase):
    def doctor(self, major):
        buf = io.StringIO()
        with mock.patch.object(oc_harness, "detect", return_value=major), \
                redirect_stdout(buf):
            audit.main(["doctor"])
        return buf.getvalue()

    def test_reports_opencode_and_lane_width_only(self):
        out = self.doctor(2)
        self.assertIn("opencode    v2", out)
        self.assertIn("OC_MAX_LANES", out)
        for gone in ("api key", "base url", "route", "tiers", "ping"):
            self.assertNotIn(gone, out)

    def test_flags_v1_and_a_missing_install(self):
        self.assertIn("OpenCode v2 required", self.doctor(1))
        self.assertIn("NOT FOUND -- install OpenCode v2", self.doctor(0))


class Setup(unittest.TestCase):
    def test_dry_run_writes_nothing(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": home}), \
                mock.patch.object(oc_harness, "detect", return_value=2), \
                redirect_stdout(buf):
            audit.main(["setup", "--harness", "opencode", "--dry-run"])
        out = buf.getvalue()
        self.assertIn("OC_MAX_LANES", out)
        self.assertIn("(dry run -- nothing written)", out)

    def test_unsupported_harness_is_rejected(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        with mock.patch.dict(os.environ, {"HOME": home}), \
                self.assertRaises(SystemExit) as cm, redirect_stderr(io.StringIO()):
            audit.main(["setup", "--harness", "other"])
        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(os.listdir(home), [])


class DocumentationConfigs(unittest.TestCase):
    def test_skill_md_r3_step_1_has_no_parallel_read(self):
        skill_path = os.path.join(os.path.dirname(__file__), "..", "..", "oc-requirements-code-audit", "SKILL.md")
        with open(skill_path, 'r') as f:
            content = f.read()
        r3_section = content.split('## R3')[1].split('## R4')[0]
        self.assertNotIn('in parallel: `Read`', r3_section, "R3 should not have parallel Read and run")
        self.assertIn('run `A brief', r3_section, "R3 should have run A brief without parallel Read")

    def test_skill_md_finalize_matches_code_behavior(self):
        skill_path = os.path.join(os.path.dirname(__file__), "..", "..", "oc-requirements-code-audit", "SKILL.md")
        with open(skill_path, 'r') as f:
            content = f.read()
        self.assertIn('an unplanned discrepancy', content)
        self.assertNotIn('a CONFLICT not planned at P0', content, "CONFLICT should not fail gate; doc must align with code behavior")

    def test_agent_investigator_write_paths(self):
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "oc-requirements-code-audit", "opencode", "agents", "oc-rca-investigator.md")
        with open(agent_path, 'r') as f:
            content = f.read()
        self.assertIn('write_paths: **/.oc-audit/**', content, "rca-investigator must have session-relative write_paths")

    def test_agent_investigator_steps(self):
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "oc-requirements-code-audit", "opencode", "agents", "oc-rca-investigator.md")
        with open(agent_path, 'r') as f:
            content = f.read()
        self.assertRegex(content, r'steps:\s*30', "rca-investigator must have steps: 30")

    def test_agent_verifier_write_paths(self):
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "oc-requirements-code-audit", "opencode", "agents", "oc-rca-verifier.md")
        with open(agent_path, 'r') as f:
            content = f.read()
        self.assertIn('write_paths: **/.oc-audit/**', content, "rca-verifier must have session-relative write_paths")

    def test_agent_verifier_steps(self):
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "oc-requirements-code-audit", "opencode", "agents", "oc-rca-verifier.md")
        with open(agent_path, 'r') as f:
            content = f.read()
        self.assertRegex(content, r'steps:\s*25', "rca-verifier must have steps: 25")
