import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import oc_harness

INSTALLER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                         "install-opencode.sh")

AGENT = (
    "---\n"
    "description: test agent\n"
    "model: flash\n"
    "effort: high\n"
    "access: read\n"
    "bash: false\n"
    "web: false\n"
    "steps: 5\n"
    "---\n"
    "Do the work.\n"
)
COMMAND = "---\ndescription: run debug\n---\n!`python3 {{SKILL_DIR}}/scripts/tool.py doctor`\nLoad the skill with $ARGUMENTS\n"


SKILL_NAMES = {"oc-brainstorming", "oc-dev-team", "oc-doc-generator", "oc-requirements-code-audit",
               "oc-systematic-debugging", "oc-writing-plans"}


def stub_opencode_env(home, version="2.0.20"):
    """Environment whose `opencode --version` prints `version` and whose HOME is `home`."""
    bindir = os.path.join(home, ".stub-bin")
    os.makedirs(bindir, exist_ok=True)
    binary = os.path.join(bindir, "opencode")
    with open(binary, "w") as fh:
        fh.write('#!/bin/sh\necho "%s"\n' % version)
    os.chmod(binary, 0o755)
    return dict(os.environ, HOME=home, PYTHONDONTWRITEBYTECODE="1",
                PATH=bindir + os.pathsep + os.environ.get("PATH", ""))


def make_skill(root, folder="systematic-debugging", name="systematic-debugging"):
    skill = os.path.join(root, folder)
    os.makedirs(os.path.join(skill, "opencode", "agents"))
    os.makedirs(os.path.join(skill, "opencode", "commands"))
    os.makedirs(os.path.join(skill, "scripts", "__pycache__"))
    with open(os.path.join(skill, "SKILL.md"), "w") as fh:
        fh.write("---\nname: %s\ndescription: test skill\n---\nbody\n" % name)
    with open(os.path.join(skill, "opencode", "agents", "worker.md"), "w") as fh:
        fh.write(AGENT)
    with open(os.path.join(skill, "opencode", "commands", "oc-debug.md"), "w") as fh:
        fh.write(COMMAND)
    with open(os.path.join(skill, "scripts", "__pycache__", "x.pyc"), "w") as fh:
        fh.write("junk")
    return skill


class Patch:
    """Swap module attributes for one test and restore them afterwards."""

    def __init__(self, test, **attrs):
        for key, value in attrs.items():
            original = getattr(oc_harness, key)
            test.addCleanup(setattr, oc_harness, key, original)
            setattr(oc_harness, key, value)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-install-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.skill = make_skill(self.tmp)
        self.home = os.path.join(self.tmp, "home")
        self.root = os.path.join(self.home, ".config", "opencode")

    def test_skill_name_is_the_frontmatter_name(self):
        other = make_skill(self.tmp, "writing-plans", "writing-plans")
        self.assertEqual(oc_harness.skill_name(other), "writing-plans")
        self.assertEqual(oc_harness.skill_name(self.skill), "systematic-debugging")
        kept = make_skill(self.tmp, "odd-folder", "suffix-name")
        self.assertEqual(oc_harness.skill_name(kept), "suffix-name")
        nameless = os.path.join(self.tmp, "nameless")
        os.makedirs(nameless)
        with open(os.path.join(nameless, "SKILL.md"), "w") as fh:
            fh.write("---\ndescription: no name field\n---\nbody\n")
        self.assertEqual(oc_harness.skill_name(nameless), "nameless")

    def test_install_uses_frontmatter_name_and_writes_marker(self):
        written = oc_harness.install(self.skill, 2, self.home)
        dst = os.path.join(self.root, "skills", "systematic-debugging")
        self.assertIn(dst, written)
        self.assertTrue(os.path.isfile(os.path.join(dst, "SKILL.md")))
        self.assertFalse(os.path.exists(os.path.join(dst, "scripts", "__pycache__")))
        with open(os.path.join(dst, ".oc-major")) as fh:
            self.assertEqual(fh.read().strip(), "2")

    def test_install_renders_agents_and_commands_under_their_own_names(self):
        oc_harness.install(self.skill, 2, self.home)
        agent = os.path.join(self.root, "agents", "worker.md")
        command = os.path.join(self.root, "commands", "oc-debug.md")
        with open(agent) as fh:
            text = fh.read()
        self.assertIn("mode: subagent", text)
        self.assertNotIn("model:", text)
        self.assertNotIn("variant:", text)
        self.assertNotIn("reasoning", text)
        with open(command) as fh:
            text = fh.read()
        dst = os.path.join(self.root, "skills", "systematic-debugging")
        self.assertIn("python3 %s/scripts/tool.py doctor" % dst, text)
        self.assertNotIn("{{SKILL_DIR}}", text)

    def test_install_refuses_every_major_but_two_and_writes_nothing(self):
        for major in (0, 1, 3):
            with self.assertRaisesRegex(ValueError, "OpenCode v2 required"):
                oc_harness.install(self.skill, major, self.home)
        self.assertFalse(os.path.exists(self.root))


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-check-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.skill = make_skill(self.tmp)
        self.home = os.path.join(self.tmp, "home")
        real = os.path.expanduser
        self.addCleanup(setattr, os.path, "expanduser", real)
        os.path.expanduser = lambda path: path.replace("~", self.home, 1)

    def test_missing_install(self):
        self.assertEqual(oc_harness.check(self.skill), ["MISSING: systematic-debugging is not installed for OpenCode"])

    def test_major_mismatch(self):
        oc_harness.install(self.skill, 2, self.home)
        marker = os.path.join(self.home, ".config", "opencode", "skills", "systematic-debugging", ".oc-major")
        with open(marker, "w") as fh:
            fh.write("1")
        Patch(self, detect=lambda binary="opencode": 2)
        lines = oc_harness.check(self.skill)
        self.assertEqual(lines[0], "INSTALLED: systematic-debugging (major 1)")
        self.assertIn("FAIL: installed major 1 != detected major 2, re-run install-opencode.sh", lines)

    def test_v1_binary_is_a_failure(self):
        oc_harness.install(self.skill, 2, self.home)
        Patch(self, detect=lambda binary="opencode": 1)
        lines = oc_harness.check(self.skill)
        self.assertEqual(lines[0], "INSTALLED: systematic-debugging (major 2)")
        self.assertIn("FAIL: OpenCode v2 required, found major 1", lines)

    def test_clean_install_has_no_failure(self):
        oc_harness.install(self.skill, 2, self.home)
        Patch(self, detect=lambda binary="opencode": 2)
        self.assertEqual(oc_harness.check(self.skill), ["INSTALLED: systematic-debugging (major 2)"])

    def test_binary_missing(self):
        oc_harness.install(self.skill, 2, self.home)
        Patch(self, detect=lambda binary="opencode": 0)
        self.assertIn("FAIL: opencode binary not found", oc_harness.check(self.skill))


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-main-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.skill = make_skill(self.tmp)
        self.home = os.path.join(self.tmp, "home")

    def run_main(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = oc_harness.main(argv)
        return rc, buf.getvalue()

    def test_install_positional_major_and_home(self):
        rc, out = self.run_main(["install", self.skill, "2", self.home])
        self.assertEqual(rc, 0)
        self.assertIn(os.path.join(self.home, ".config", "opencode", "skills", "systematic-debugging"), out)
        self.assertIn("NEXT:", out)

    def test_install_refuses_a_v1_major_with_one_line(self):
        rc, out = self.run_main(["install", self.skill, "1", self.home])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "OpenCode v2 required")
        self.assertFalse(os.path.exists(self.home))

    def test_install_refuses_a_detected_v1_binary(self):
        Patch(self, detect=lambda binary="opencode": 1)
        rc, out = self.run_main(["install", self.skill])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "OpenCode v2 required")

    def test_install_without_opencode_fails(self):
        Patch(self, detect=lambda binary="opencode": 0)
        rc, out = self.run_main(["install", self.skill])
        self.assertEqual(rc, 1)
        self.assertIn("opencode not found", out)

    def test_detect_returns_one_when_missing(self):
        Patch(self, detect=lambda binary="opencode": 0)
        rc, out = self.run_main(["detect"])
        self.assertEqual(rc, 1)
        self.assertIn("0", out)

    def test_detect_prints_major_and_returns_zero(self):
        Patch(self, detect=lambda binary="opencode": 2)
        rc, out = self.run_main(["detect"])
        self.assertEqual(rc, 0)
        self.assertIn("2", out)

    def test_check_returns_one_on_fail_line(self):
        Patch(self, check=lambda skill_dir, home="": ["MISSING: foo is not installed for OpenCode"])
        rc, out = self.run_main(["check", self.skill])
        self.assertEqual(rc, 1)
        self.assertIn("MISSING: foo is not installed for OpenCode", out)

    def test_check_returns_one_on_fail_line_after_installed_line(self):
        Patch(self, check=lambda skill_dir, home="": [
            "INSTALLED: x (major 2)",
            "FAIL: OpenCode v2 required, found major 1",
        ])
        rc, out = self.run_main(["check", self.skill])
        self.assertEqual(rc, 1)
        self.assertIn("INSTALLED: x (major 2)", out)
        self.assertIn("FAIL: OpenCode v2 required, found major 1", out)

    def test_check_returns_zero_for_clean_install(self):
        Patch(self, check=lambda skill_dir, home="": ["INSTALLED: systematic-debugging (major 2)"])
        rc, out = self.run_main(["check", self.skill])
        self.assertEqual(rc, 0)
        self.assertIn("INSTALLED: systematic-debugging (major 2)", out)

    def test_removed_subcommands_and_unknown_command_return_two(self):
        for command in ("snippet", "probe-effort", "run", "result", "bogus"):
            saved = sys.stderr
            sys.stderr = io.StringIO()
            try:
                rc = oc_harness.main([command])
            finally:
                sys.stderr = saved
            self.assertEqual(rc, 2, command)


class InstallFromOwnDestinationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-selfinstall-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        skills_root = os.path.join(self.home, ".config", "opencode", "skills")
        os.makedirs(skills_root)
        self.skill_dst = make_skill(skills_root, "systematic-debugging", "systematic-debugging")

    def test_install_from_its_own_destination_does_not_delete_it(self):
        written = oc_harness.install(self.skill_dst, 2, self.home)
        self.assertIn(self.skill_dst, written)
        self.assertTrue(os.path.isfile(os.path.join(self.skill_dst, "SKILL.md")))
        self.assertTrue(os.path.isdir(os.path.join(self.skill_dst, "scripts")))
        with open(os.path.join(self.skill_dst, ".oc-major")) as fh:
            self.assertEqual(fh.read().strip(), "2")
        agent = os.path.join(self.home, ".config", "opencode", "agents", "worker.md")
        self.assertTrue(os.path.isfile(agent))


class InstallerWarningTests(unittest.TestCase):
    """install-opencode.sh against a temp home: folder names, version gate, clashes."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-installer-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.foreign_skills = os.path.join(self.home, ".claude", "skills")
        self.config_skills = os.path.join(self.home, ".config", "opencode", "skills")

    def run_installer(self, *args, version="2.0.20"):
        return subprocess.run(
            ["sh", INSTALLER, "--home", self.home] + list(args),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, env=stub_opencode_env(self.home, version), timeout=120)

    def installed_output(self):
        proc = self.run_installer()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def make_skill_dir(self, parent, folder):
        path = os.path.join(parent, folder)
        os.makedirs(path)
        with open(os.path.join(path, "SKILL.md"), "w") as fh:
            fh.write("---\nname: %s\ndescription: old copy\n---\nbody\n" % folder)
        return path

    def test_major_flag_is_gone(self):
        proc = self.run_installer("--major", "2")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Usage:", proc.stderr)
        self.assertNotIn("--major", proc.stderr)

    def test_v1_binary_is_rejected_before_anything_is_installed(self):
        proc = self.run_installer(version="1.18.33")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("OpenCode v2 required", proc.stderr)
        self.assertFalse(os.path.exists(self.config_skills))

    def test_installs_each_skill_under_its_folder_name(self):
        self.installed_output()
        self.assertEqual(set(os.listdir(self.config_skills)), SKILL_NAMES)

    def test_clean_home_prints_no_warnings(self):
        out = self.installed_output()
        self.assertNotIn("WARN:", out)
        self.assertNotIn("rm -rf", out)
        self.assertNotIn("OPENCODE_DISABLE", out)
        self.assertIn("NEXT:", out)

    def test_lists_clashes_only_for_the_same_name_without_deleting(self):
        original = self.make_skill_dir(self.foreign_skills, "oc-doc-generator")
        other = self.make_skill_dir(self.foreign_skills, "unrelated-skill")
        out = self.installed_output()
        self.assertIn("WARN: clash: %s" % original, out)
        self.assertNotIn("WARN: clash: %s" % other, out)
        self.assertIn("may conflict", out)
        self.assertNotIn("rm -rf", out)
        self.assertTrue(os.path.isfile(os.path.join(original, "SKILL.md")))
        self.assertTrue(os.path.isfile(os.path.join(other, "SKILL.md")))


if __name__ == "__main__":
    unittest.main()
