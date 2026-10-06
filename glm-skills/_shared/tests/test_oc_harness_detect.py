"""harness(), major(), dispatch_line() and the `harness` CLI subcommand of oc_harness.py."""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.dirname(HERE)
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import oc_harness  # noqa: E402


def make_script(root, *parts):
    """Create <root>/<parts...>/scripts/tool.py and return its path."""
    scripts = os.path.join(root, *parts, "scripts")
    os.makedirs(scripts, exist_ok=True)
    path = os.path.join(scripts, "tool.py")
    with open(path, "w") as fh:
        fh.write("")
    return path


def write_marker(skill_dir, text):
    with open(os.path.join(skill_dir, ".oc-major"), "w") as fh:
        fh.write(text)


class HarnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-harness-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.plain = make_script(self.tmp, "plain", "demo")

    def test_opencode_terminal_env(self):
        with mock.patch.dict(os.environ, {"OPENCODE_TERMINAL": "1"}, clear=True):
            self.assertEqual(oc_harness.harness(self.plain), "opencode")

    def test_opencode_env(self):
        with mock.patch.dict(os.environ, {"OPENCODE": "1"}, clear=True):
            self.assertEqual(oc_harness.harness(self.plain), "opencode")

    def test_devteam_harness_env(self):
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "opencode"}, clear=True):
            self.assertEqual(oc_harness.harness(self.plain), "opencode")

    def test_project_skills_dir(self):
        script = make_script(self.tmp, "proj", ".opencode", "skills", "demo")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(oc_harness.harness(script), "opencode")

    def test_user_config_skills_dir(self):
        script = make_script(self.tmp, "home", ".config", "opencode", "skills", "demo")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(oc_harness.harness(script), "opencode")

    def test_opencode_config_dir_env(self):
        config = os.path.join(self.tmp, "cfg")
        script = make_script(config, "skills", "demo")
        with mock.patch.dict(os.environ, {"OPENCODE_CONFIG_DIR": config}, clear=True):
            self.assertEqual(oc_harness.harness(script), "opencode")

    def test_oc_major_marker_in_skill_dir(self):
        script = make_script(self.tmp, "anywhere", "demo")
        write_marker(os.path.join(self.tmp, "anywhere", "demo"), "2")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(oc_harness.harness(script), "opencode")

    def test_opencode_path_beats_claude_env(self):
        script = make_script(self.tmp, "proj", ".opencode", "skills", "demo")
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=True):
            self.assertEqual(oc_harness.harness(script), "opencode")

    def test_claude_env(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=True):
            self.assertEqual(oc_harness.harness(self.plain), "claude")

    def test_claude_skills_path(self):
        script = make_script(self.tmp, "home", ".claude", "skills", "demo")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(oc_harness.harness(script), "claude")

    def test_zcode_env(self):
        with mock.patch.dict(os.environ, {"ZCODE_SESSION": "1"}, clear=True):
            self.assertEqual(oc_harness.harness(self.plain), "zcode")

    def test_unknown(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(oc_harness.harness(self.plain), "unknown")


class MajorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-major-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        oc_harness._DETECT_CACHE.clear()
        self.addCleanup(oc_harness._DETECT_CACHE.clear)
        self.skill = os.path.join(self.tmp, "demo")
        os.makedirs(self.skill)
        self.missing_binary = os.path.join(self.tmp, "no-such-opencode")

    def fake_binary(self, version):
        """An executable that prints `version` and appends one line to <tmp>/calls per run."""
        path = os.path.join(self.tmp, "opencode")
        with open(path, "w") as fh:
            fh.write('#!/bin/sh\necho call >> "%s"\necho "%s"\n'
                     % (os.path.join(self.tmp, "calls"), version))
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return path

    def calls(self):
        try:
            with open(os.path.join(self.tmp, "calls")) as fh:
                return len(fh.read().splitlines())
        except OSError:
            return 0

    def test_marker_wins_without_spawning(self):
        write_marker(self.skill, "2\n")
        binary = self.fake_binary("1.18.33")
        self.assertEqual(oc_harness.major(self.skill, binary), 2)
        self.assertEqual(self.calls(), 0)

    def test_detect_fallback_is_cached(self):
        binary = self.fake_binary("2.0.18")
        self.assertEqual(oc_harness.major(self.skill, binary), 2)
        self.assertEqual(oc_harness.major(self.skill, binary), 2)
        self.assertEqual(self.calls(), 1)

    def test_bad_marker_falls_back_to_detect(self):
        write_marker(self.skill, "not a number")
        binary = self.fake_binary("1.18.33")
        self.assertEqual(oc_harness.major(self.skill, binary), 1)

    def test_no_marker_no_binary_is_zero(self):
        self.assertEqual(oc_harness.major(self.skill, self.missing_binary), 0)


class DispatchLineTest(unittest.TestCase):
    def test_v1_task_call(self):
        line = oc_harness.dispatch_line("glm-plan-task-writer", "/w/briefs/T01.md", "plan T01", 1)
        self.assertEqual(
            line,
            'task(subagent_type="glm-plan-task-writer", description="plan T01", '
            'prompt="Read /w/briefs/T01.md and follow it exactly.")')

    def test_v2_background_call(self):
        line = oc_harness.dispatch_line("glm-plan-task-writer", "/w/briefs/T01.md", "plan T01", 2)
        self.assertEqual(
            line,
            'subagent(agent="glm-plan-task-writer", description="plan T01", '
            'prompt="Read /w/briefs/T01.md and follow it exactly.", background=true)')

    def test_v2_foreground_call(self):
        line = oc_harness.dispatch_line("glm-reviewer", "/w/r.md", "review", 2, background=False)
        self.assertTrue(line.startswith('subagent(agent="glm-reviewer", '))
        self.assertTrue(line.endswith("background=false)"))

    def test_fallback_agent_is_general(self):
        for name in ("", "general-purpose", "Explore"):
            for version in (1, 2):
                line = oc_harness.dispatch_line(name, "/w/b.md", "d", version)
                self.assertIn('"general"', line)
                self.assertNotIn("general-purpose", line)
                self.assertNotIn("Explore", line)

    def test_never_emits_a_model(self):
        for version in (1, 2):
            line = oc_harness.dispatch_line("glm-reviewer", "/w/b.md", "d", version)
            self.assertNotIn("model", line)
            self.assertNotIn("haiku", line)
            self.assertNotIn("sonnet", line)


class HarnessCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-cli-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_cli(self, script, extra_env):
        env = {"PATH": os.environ.get("PATH", ""), "HOME": self.tmp, "PYTHONDONTWRITEBYTECODE": "1"}
        env.update(extra_env)
        return subprocess.run(
            [sys.executable, os.path.join(SHARED, "oc_harness.py"), "harness", "--script", script],
            capture_output=True, text=True, env=env, timeout=30)

    def test_opencode_install_prints_marker_major(self):
        script = make_script(self.tmp, ".config", "opencode", "skills", "demo")
        write_marker(os.path.join(self.tmp, ".config", "opencode", "skills", "demo"), "2")
        result = self.run_cli(script, {})
        self.assertEqual(result.stdout.strip(), "opencode 2")
        self.assertEqual(result.returncode, 0)

    def test_claude_prints_zero_major(self):
        script = make_script(self.tmp, "plain", "demo")
        result = self.run_cli(script, {"CLAUDECODE": "1"})
        self.assertEqual(result.stdout.strip(), "claude 0")
        self.assertEqual(result.returncode, 0)
