import os
import shutil
import stat
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import oc_harness

FAKE_OPENCODE = """#!/bin/sh
if [ "$1" = "--version" ]; then echo 1.18.32; exit 0; fi
printf '%s' "$DEVTEAM_ROLE" > "$ENV_OUT"
echo '{"type":"text","part":{"text":"done"}}'
"""


class LaneEnvTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-env-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.binary = os.path.join(self.tmp, "opencode")
        with open(self.binary, "w") as fh:
            fh.write(FAKE_OPENCODE)
        os.chmod(self.binary, os.stat(self.binary).st_mode | stat.S_IEXEC)

    def test_lane_env_reaches_the_process(self):
        env_out = os.path.join(self.tmp, "role.txt")
        lane = {"id": "a", "agent": "programmer", "model": "flash", "dir": self.tmp, "brief": "go",
                "env": {"DEVTEAM_ROLE": "programmer", "ENV_OUT": env_out}}
        rows = oc_harness.run_lanes([lane], os.path.join(self.tmp, "out"), binary=self.binary, major=1)
        self.assertEqual(rows[0]["status"], "OK")
        with open(env_out) as fh:
            self.assertEqual(fh.read(), "programmer")
        self.assertNotIn("DEVTEAM_ROLE", os.environ)


class PluginInstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-plugin-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.skill = os.path.join(self.tmp, "dev-team-glm")
        os.makedirs(os.path.join(self.skill, "opencode", "plugins"))
        with open(os.path.join(self.skill, "SKILL.md"), "w") as fh:
            fh.write("---\nname: dev-team\ndescription: test\n---\nbody\n")
        for major in (1, 2):
            path = os.path.join(self.skill, "opencode", "plugins", "devteam-guard.v%d.js" % major)
            with open(path, "w") as fh:
                fh.write("// v%d\nconst GUARD = '{{SKILL_DIR}}/scripts/guard.py'\n" % major)
        self.home = os.path.join(self.tmp, "home")
        self.plugins = os.path.join(self.home, ".config", "opencode", "plugins")
        self.skill_dst = os.path.join(self.home, ".config", "opencode", "skills", "dev-team")

    def installed_plugin(self):
        with open(os.path.join(self.plugins, "devteam-guard.js")) as fh:
            return fh.read()

    def test_installs_the_plugin_matching_the_major(self):
        written = oc_harness.install(self.skill, 2, self.home)
        self.assertIn(os.path.join(self.plugins, "devteam-guard.js"), written)
        text = self.installed_plugin()
        self.assertIn("// v2", text)
        self.assertIn(self.skill_dst + "/scripts/guard.py", text)
        self.assertNotIn("{{SKILL_DIR}}", text)
        self.assertEqual(os.listdir(self.plugins), ["devteam-guard.js"])

    def test_v1_install_uses_the_v1_source(self):
        oc_harness.install(self.skill, 1, self.home)
        self.assertIn("// v1", self.installed_plugin())


if __name__ == "__main__":
    unittest.main()
