import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "dev-team-glm", "scripts")
sys.path.insert(0, SCRIPTS)

import devteam  # noqa: E402


class HarnessDetectionTest(unittest.TestCase):
    """DE1: OpenCode v2 never sets OPENCODE, so detection must go through oc_harness.harness()."""

    def test_opencode_detected_through_oc_harness(self):
        oc = devteam._oc_harness()
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(oc, "harness", return_value="opencode") as h:
            self.assertTrue(devteam.is_opencode())
        h.assert_called_once_with(str(Path(devteam.__file__).resolve()))

    def test_claude_when_oc_harness_says_claude(self):
        oc = devteam._oc_harness()
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(oc, "harness", return_value="claude"):
            self.assertFalse(devteam.is_opencode())

    def test_devteam_harness_override_wins(self):
        oc = devteam._oc_harness()
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "claude"}, clear=True), \
                mock.patch.object(oc, "harness", return_value="opencode"):
            self.assertFalse(devteam.is_opencode())
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "opencode"}, clear=True), \
                mock.patch.object(oc, "harness", return_value="claude"):
            self.assertTrue(devteam.is_opencode())

    def test_v1_opencode_marker_still_detected(self):
        oc = devteam._oc_harness()
        with mock.patch.dict(os.environ, {"OPENCODE": "1"}, clear=True), \
                mock.patch.object(oc, "harness", return_value="claude"):
            self.assertTrue(devteam.is_opencode())


class LiteLaneAgentTest(unittest.TestCase):
    """DE7: on OpenCode a programmer-lite slice must run the lite agent at low effort, not programmer."""

    def test_lite_lane_keeps_lite_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(devteam, "terminate_lane_process"), \
                    mock.patch.object(devteam.subprocess, "Popen", return_value=mock.MagicMock(pid=4242)):
                pid = devteam.launch_lane(root, {"provider": "glm"}, "S1", "programmer-lite", "",
                                          "python3 x claim S1")
            spec = json.loads((devteam.lanes_dir(root) / "S1.lane.json").read_text())
        self.assertEqual(pid, 4242)
        self.assertEqual(spec["agent"], "programmer-lite")
        self.assertEqual(spec["effort"], "low")
        self.assertTrue(spec["writer"])


class ProgrammerLiteInstallTest(unittest.TestCase):
    """F17: an OpenCode install ships programmer-lite (effort low, programmer body) and doctor checks it."""

    def test_install_ships_programmer_lite_at_low_effort(self):
        oc = devteam._oc_harness()
        skill_dir = str(Path(SCRIPTS).parent)
        for major, effort_line in ((1, "reasoningEffort: low"), (2, "variant: low")):
            with tempfile.TemporaryDirectory() as home:
                oc.install(skill_dir, major, home)
                adir = Path(home) / ".config" / "opencode" / "agents"
                installed = {p.stem for p in adir.glob("*.md")}
                self.assertIn("programmer-lite", installed)
                self.assertTrue(set(devteam.OC_AGENT_NAMES) <= installed)
                lite = (adir / "programmer-lite.md").read_text()
                prog = (adir / "programmer.md").read_text()
                self.assertIn(effort_line, lite.split("\n---\n", 1)[0])
                self.assertEqual(lite.split("\n---\n", 1)[1], prog.split("\n---\n", 1)[1])

    def test_doctor_agent_names_include_programmer_lite(self):
        self.assertIn("programmer-lite", devteam.OC_AGENT_NAMES)


class ConcurrencyCapTest(unittest.TestCase):
    """DE8: Claude Code's subagent cap (default 20) must not bound OpenCode lanes; OpenCode is non-Claude, so 8."""

    def test_opencode_is_capped_at_8_not_by_claude_limit(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(devteam, "is_opencode", return_value=True):
            self.assertEqual(devteam.concurrency_limit(), devteam.NON_CLAUDE_CAP)
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "8"}, clear=True), \
                mock.patch.object(devteam, "is_opencode", return_value=True):
            self.assertEqual(devteam.concurrency_limit(), devteam.NON_CLAUDE_CAP)

    def test_claude_keeps_its_cap(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(devteam, "is_opencode", return_value=False):
            self.assertEqual(devteam.concurrency_limit(), devteam.DEFAULT_LIMIT)
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "8"}, clear=True), \
                mock.patch.object(devteam, "is_opencode", return_value=False):
            self.assertEqual(devteam.concurrency_limit(), 8)


class LaunchHintTest(unittest.TestCase):
    """DE9: on OpenCode the lanes already run, so `start` must point to `wait`, not to Agent calls."""

    def test_opencode_hint_points_to_wait(self):
        with mock.patch.object(devteam, "is_opencode", return_value=True):
            hint = devteam.launch_hint()
        self.assertIn(" wait`", hint)
        self.assertIn("`next`", hint)
        self.assertNotIn("Agent call", hint)

    def test_claude_hint_unchanged(self):
        with mock.patch.object(devteam, "is_opencode", return_value=False):
            hint = devteam.launch_hint()
        self.assertEqual(hint, "Launch every Agent call above in ONE message (parallel tool calls), then end the "
                               "turn. On each wake-up (completion notification, background result, user answer): "
                               "`next` — no ids needed.")


if __name__ == "__main__":
    unittest.main()
