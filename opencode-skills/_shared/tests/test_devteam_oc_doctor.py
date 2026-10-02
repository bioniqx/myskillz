"""dev-team `doctor [--fix]`: the single OpenCode v2 doctor."""
import argparse
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(ROOT, "oc-dev-team", "scripts")
SKILL_DIR = os.path.join(ROOT, "oc-dev-team")
FAKE_OC = '#!/bin/sh\n[ "$FAKE_OC_VERSION" = none ] && exit 127\necho "opencode $FAKE_OC_VERSION"\n'
sys.path.insert(0, SCRIPTS)

import oc_harness  # noqa: E402  (the vendored copy next to oc_devteam.py)


def load_devteam():
    spec = importlib.util.spec_from_file_location("devteam_oc", os.path.join(SCRIPTS, "oc_devteam.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dt = load_devteam()
AGENTS = ["oc-code-reviewer.md", "oc-investigator.md", "oc-programmer.md", "oc-spot-reviewer.md", "oc-team-leader.md"]


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.bin = os.path.join(self.tmp, "bin")
        self.repo = os.path.join(self.tmp, "repo")
        for d in (self.home, self.bin, self.repo):
            os.makedirs(d)
        opencode = os.path.join(self.bin, "opencode")
        with open(opencode, "w") as f:
            f.write(FAKE_OC)
        os.chmod(opencode, 0o755)
        for args in (["init", "-q"],
                     ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                      "commit", "-q", "--allow-empty", "-m", "init"]):
            subprocess.run(["git"] + args, cwd=self.repo, check=True, capture_output=True)
        self.old = os.getcwd()
        os.chdir(self.repo)
        self.env = mock.patch.dict(os.environ, {
            "HOME": self.home, "PATH": self.bin + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_OC_VERSION": "2.0.20"})
        self.env.start()
        self.name = oc_harness.skill_name(SKILL_DIR)
        self.oc = os.path.join(self.home, ".config", "opencode")

    def tearDown(self):
        self.env.stop()
        os.chdir(self.old)
        shutil.rmtree(self.tmp)

    def doctor(self, fix=False):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dt.cmd_doctor(argparse.Namespace(fix=fix))
        return buf.getvalue()

    def install_plugin(self):
        """The real plugin file a full `oc_harness.install` writes, not a hand-typed fixture."""
        oc_harness.install(SKILL_DIR, 2, self.home)

    def test_reports_missing_install(self):
        out = self.doctor()
        self.assertIn("DOCTOR found:", out)
        self.assertIn("MISSING: %s is not installed for OpenCode" % self.name, out)
        self.assertIn("agent oc-programmer not installed", out)
        self.assertIn("agent oc-team-leader not installed", out)
        self.assertIn("guard plugin not installed", out)
        self.assertIn("run `doctor --fix`", out)

    def test_fix_installs_the_agents_and_the_plugin_for_v2(self):
        out = self.doctor(fix=True)
        self.assertIn("installed ", out)
        self.assertIn("updated git info/exclude", out)
        self.assertIn("RESTART OpenCode", out)
        with open(os.path.join(self.oc, "skills", self.name, ".oc-major")) as f:
            self.assertEqual(f.read().strip(), "2")
        installed = os.listdir(os.path.join(self.oc, "agents"))
        self.assertEqual([a for a in AGENTS if a not in installed], [])
        self.assertTrue(os.path.isfile(os.path.join(self.oc, "plugins", "oc-devteam-guard.js")))
        exclude = Path(self.repo, ".git", "info", "exclude").read_text()
        self.assertIn(".opencode/oc-dev-team/", exclude)
        again = self.doctor()
        self.assertIn("INSTALLED: %s (major 2)" % self.name, again)
        self.assertNotIn("agent oc-programmer not installed", again)
        self.assertNotIn("guard plugin not installed", again)

    def test_opencode_missing(self):
        os.environ["FAKE_OC_VERSION"] = "none"
        self.assertIn("OpenCode v2 not found on PATH", self.doctor())

    def test_opencode_v1_is_not_enough(self):
        os.environ["FAKE_OC_VERSION"] = "1.18.33"
        self.assertIn("OpenCode v2 not found on PATH (detected: 1)", self.doctor())

    def test_plugin_edited_after_install(self):
        self.install_plugin()
        path = os.path.join(self.oc, "plugins", "oc-devteam-guard.js")
        with open(path, "a") as f:
            f.write("\n// local edit\n")
        out = self.doctor()
        self.assertIn("plugin oc-devteam-guard.js does not match the OpenCode v2 template", out)
        self.assertIn("re-run `doctor --fix`", out)

    def test_plugin_ok(self):
        self.install_plugin()
        out = self.doctor()
        self.assertNotIn("guard plugin not installed", out)
        self.assertNotIn("oc_guard.py path does not resolve", out)
        self.assertNotIn("does not match the OpenCode v", out)

    def test_plugin_unresolved(self):
        self.install_plugin()
        shutil.rmtree(os.path.join(self.oc, "skills", self.name))
        self.assertIn("plugin oc-devteam-guard.js: its oc_guard.py path does not resolve", self.doctor())

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_plugin_load_error(self):
        d = os.path.join(self.oc, "plugins")
        os.makedirs(d)
        with open(os.path.join(d, "guard.js"), "w") as f:
            f.write("export default {\n// oc_guard.py\n")
        self.assertIn("plugin guard.js fails to load", self.doctor())

    def test_removed_subcommands_and_flags(self):
        script = os.path.join(SCRIPTS, "oc_devteam.py")
        for argv in (["doctor", "--harness", "opencode"], ["allow", "pytest"], ["stats"], ["lane-run", "S1"],
                     ["init", "p.json", "--tier", "pro"]):
            r = subprocess.run([sys.executable, script] + argv, cwd=self.repo, text=True, capture_output=True)
            self.assertEqual(r.returncode, 2, (argv, r.stderr))


if __name__ == "__main__":
    unittest.main()
