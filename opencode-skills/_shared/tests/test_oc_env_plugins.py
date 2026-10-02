import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import oc_harness


class GuardInstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-guard-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.skill = os.path.join(self.tmp, "dev-team")
        self.src = os.path.join(self.skill, "opencode", "plugins")
        os.makedirs(self.src)
        with open(os.path.join(self.skill, "SKILL.md"), "w") as fh:
            fh.write("---\nname: oc-dev-team\ndescription: test\n---\nbody\n")
        for major in (1, 2):
            path = os.path.join(self.src, "oc-devteam-guard.v%d.js" % major)
            with open(path, "w") as fh:
                fh.write("// v%d\nconst GUARD = '{{SKILL_DIR}}/scripts/oc_guard.py'\n" % major)
        self.home = os.path.join(self.tmp, "home")
        self.guards = os.path.join(self.home, ".config", "opencode", "plugins")
        self.skill_dst = os.path.join(self.home, ".config", "opencode", "skills", "oc-dev-team")

    def installed_guard(self):
        with open(os.path.join(self.guards, "oc-devteam-guard.js")) as fh:
            return fh.read()

    def test_installs_the_v2_file_and_skips_the_v1_file(self):
        written = oc_harness.install(self.skill, 2, self.home)
        self.assertIn(os.path.join(self.guards, "oc-devteam-guard.js"), written)
        text = self.installed_guard()
        self.assertIn("// v2", text)
        self.assertIn(self.skill_dst + "/scripts/oc_guard.py", text)
        self.assertNotIn("{{SKILL_DIR}}", text)
        self.assertEqual(os.listdir(self.guards), ["oc-devteam-guard.js"])

    def test_an_unversioned_file_is_installed_under_its_own_name(self):
        with open(os.path.join(self.src, "extra.js"), "w") as fh:
            fh.write("// plain\n")
        oc_harness.install(self.skill, 2, self.home)
        self.assertEqual(sorted(os.listdir(self.guards)), ["extra.js", "oc-devteam-guard.js"])

    def test_v1_install_is_refused_before_anything_is_written(self):
        with self.assertRaisesRegex(ValueError, "OpenCode v2 required"):
            oc_harness.install(self.skill, 1, self.home)
        self.assertFalse(os.path.exists(self.guards))

    def test_substitution_json_escapes_special_characters_in_skill_dst(self):
        # Real templates put SKILL_DIR inside a double-quoted JS string literal
        # (path.join("{{SKILL_DIR}}", "scripts", "oc_guard.py")); a raw quote or
        # backslash in skill_dst would break that literal if pasted in unescaped.
        with open(os.path.join(self.src, "oc-devteam-guard.v2.js"), "w") as fh:
            fh.write('const GUARD = "{{SKILL_DIR}}/scripts/oc_guard.py"\n')
        home = os.path.join(self.tmp, 'ho"me')
        oc_harness.install(self.skill, 2, home)
        guard_path = os.path.join(home, ".config", "opencode", "plugins", "oc-devteam-guard.js")
        with open(guard_path) as fh:
            text = fh.read()
        skill_dst = os.path.join(home, ".config", "opencode", "skills", "oc-dev-team")
        self.assertIn(json.dumps(skill_dst)[1:-1] + "/scripts/oc_guard.py", text)
        self.assertNotIn('"' + skill_dst, text)


if __name__ == "__main__":
    unittest.main()
