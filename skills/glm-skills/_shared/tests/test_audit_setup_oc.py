import argparse
import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "requirements-code-audit-glm", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import audit  # noqa: E402
import oc_harness  # noqa: E402

SETUP_MD = os.path.normpath(os.path.join(HERE, "..", "..", "requirements-code-audit-glm", "SETUP.md"))


class IsolatedHome(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)

    def run_setup(self, dry_run=False):
        args = argparse.Namespace(harness="opencode", dry_run=dry_run)
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"HOME": self.home}, clear=False):
            with redirect_stdout(buf):
                rc = audit.cmd_setup(args)
        return rc, buf.getvalue()


class OpenCodeAgentInstall(IsolatedHome):
    def test_writes_rendered_agent_files_with_real_dialect(self):
        with mock.patch.object(oc_harness, "detect", return_value=2):
            rc, out = self.run_setup()
        self.assertEqual(rc or 0, 0)
        inv = os.path.join(self.home, ".config", "opencode", "agents", "rca-investigator.md")
        ver = os.path.join(self.home, ".config", "opencode", "agents", "rca-verifier.md")
        self.assertTrue(os.path.isfile(inv), out)
        self.assertTrue(os.path.isfile(ver), out)
        with open(inv) as fh:
            inv_text = fh.read()
        with open(ver) as fh:
            ver_text = fh.read()
        self.assertIn("mode: subagent", inv_text)
        self.assertIn("model: zai-coding-plan/glm-5.3-flash", inv_text)
        self.assertIn("mode: subagent", ver_text)
        # anchored: "glm-5.3" alone must not also match "glm-5.3-flash"
        self.assertRegex(ver_text, r"(?m)^model: zai-coding-plan/glm-5\.3$")

    def test_prints_installed_paths_from_install(self):
        with mock.patch.object(oc_harness, "detect", return_value=2), \
             mock.patch.object(oc_harness, "install", return_value=["/x/a.md", "/x/b.md"]):
            rc, out = self.run_setup()
        self.assertEqual(rc or 0, 0)
        self.assertIn("  installed /x/a.md", out)
        self.assertIn("  installed /x/b.md", out)

    def test_prints_nothing_installed_when_install_returns_empty(self):
        with mock.patch.object(oc_harness, "detect", return_value=2), \
             mock.patch.object(oc_harness, "install", return_value=[]):
            rc, out = self.run_setup()
        self.assertEqual(rc or 0, 0)
        self.assertNotIn("  installed ", out)

    def test_returns_1_when_opencode_not_found(self):
        with mock.patch.object(oc_harness, "detect", return_value=0):
            rc, out = self.run_setup()
        self.assertEqual(rc, 1)
        self.assertIn("opencode not found", out)


class SetupDocInstructions(unittest.TestCase):
    def test_opencode_section_points_at_the_install_command_not_hand_copy(self):
        with open(SETUP_MD) as fh:
            text = fh.read()
        self.assertTrue(
            "oc_harness.py install" in text or "audit.py setup" in text,
            "SETUP.md should name the install command for OpenCode")
        self.assertNotIn("from `opencode/agents/`", text,
                          "SETUP.md should not tell users to hand-copy the neutral opencode/agents/*.md sources")


if __name__ == "__main__":
    unittest.main()
