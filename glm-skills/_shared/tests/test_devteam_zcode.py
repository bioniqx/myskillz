import os
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "glm-dev-team", "scripts")
sys.path.insert(0, SCRIPTS)

import devteam  # noqa: E402


class TestDevteamZcodeCore(unittest.TestCase):
    """zcode engine core: harness detection (env override + path detector),
    the glm provider default, strong/lite dispatch routing and the
    model-less Agent line."""

    def test_is_zcode_by_env_override(self):
        oc = devteam._oc_harness()
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "zcode"}, clear=True), \
                mock.patch.object(oc, "harness", return_value="claude"):
            self.assertTrue(devteam.is_zcode())
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "claude"}, clear=True), \
                mock.patch.object(oc, "harness", return_value="zcode"):
            self.assertFalse(devteam.is_zcode())
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "opencode"}, clear=True), \
                mock.patch.object(oc, "harness", return_value="zcode"):
            self.assertFalse(devteam.is_zcode())

    def test_is_zcode_by_path_detector(self):
        oc = devteam._oc_harness()
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(oc, "harness", return_value="zcode") as h:
            self.assertTrue(devteam.is_zcode())
        h.assert_called_once_with(str(Path(devteam.__file__).resolve()))
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(oc, "harness", return_value="claude"):
            self.assertFalse(devteam.is_zcode())

    def test_detect_provider_defaults_to_glm_on_zcode(self):
        with mock.patch.object(devteam, "is_zcode", return_value=True):
            self.assertEqual(devteam.detect_provider(), "glm")
        with mock.patch.object(devteam, "is_zcode", return_value=False), \
                mock.patch.object(devteam, "is_opencode", return_value=False):
            self.assertEqual(devteam.detect_provider(), "anthropic")

    def test_strong_slices_route_to_programmer_strong_on_zcode(self):
        strong_cases = [
            {"id": "S1", "title": "risky slice", "risk": "high", "size": "small", "attempt": 1},
            {"id": "S2", "title": "large slice", "risk": "low", "size": "large", "attempt": 1},
            {"id": "S3", "title": "retry slice", "risk": "low", "size": "small", "attempt": 2},
        ]
        with mock.patch.object(devteam, "is_zcode", return_value=True):
            for s in strong_cases:
                line = devteam.dispatch_route({}, s, "zcode")
                self.assertIn("glm-programmer-strong", line, s)
                self.assertNotIn("model:", line, s)

    def test_lite_slices_route_to_programmer_lite_on_zcode(self):
        lite = {"id": "S4", "title": "easy slice", "risk": "low", "size": "small", "attempt": 1}
        with mock.patch.object(devteam, "is_zcode", return_value=True):
            line = devteam.dispatch_route({}, lite, "zcode")
        self.assertIn("glm-programmer-lite", line)
        self.assertNotIn("model:", line)
