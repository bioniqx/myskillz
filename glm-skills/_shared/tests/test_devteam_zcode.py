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
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "zcode"}, clear=True):
            self.assertTrue(devteam.is_zcode())
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "other"}, clear=True):
            self.assertFalse(devteam.is_zcode())

    def test_is_zcode_by_path_detector(self):
        """A ZCODE* env marker or a .zcode path component marks the harness."""
        with mock.patch.dict(os.environ, {"ZCODE_TERMINAL": "1"}, clear=True):
            self.assertTrue(devteam.is_zcode())
        with mock.patch.dict(os.environ, {"Z_CODE": "1"}, clear=True):
            self.assertTrue(devteam.is_zcode())
        # no marker: the checkout path carries no .zcode component
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(devteam.is_zcode())

    def test_detect_provider_defaults_to_glm_on_zcode(self):
        """Isolated from the ambient env: no DEVTEAM_PROVIDER, no ANTHROPIC_BASE_URL —
        the zcode default (glm) and the plain fallthrough (anthropic) hold on their own."""
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(devteam, "is_zcode", return_value=True):
            self.assertEqual(devteam.detect_provider(), "glm")
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(devteam, "is_zcode", return_value=False):
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
                self.assertIn("subagent_type=", line, s)
                self.assertIn("description=", line, s)
                self.assertNotIn("model:", line, s)

    def test_lite_slices_route_to_programmer_lite_on_zcode(self):
        lite = {"id": "S4", "title": "easy slice", "risk": "low", "size": "small", "attempt": 1}
        with mock.patch.object(devteam, "is_zcode", return_value=True):
            line = devteam.dispatch_route({}, lite, "zcode")
        self.assertIn("glm-programmer-lite", line)
        self.assertIn("subagent_type=", line)
        self.assertIn("description=", line)
        self.assertNotIn("model:", line)


class TestGlmMistakeGates(unittest.TestCase):
    """Machine checks for the failures GLM-5.3 leaves in a slice: a criterion's concrete
    value never reaches the test, and an added import names a module that does not exist."""

    def test_criterion_literal_must_appear_in_test_text(self):
        self.assertEqual(devteam.criterion_gaps("assert.equal(got, 200)", ["returns 404 when missing"]),
                         [("returns 404 when missing", ["404"])])
        self.assertEqual(devteam.criterion_gaps("assert.equal(got, 404)", ["returns 404 when missing"]), [])
        self.assertEqual(devteam.criterion_gaps('expect(body).toBe("widget")', ['status is "widget"']), [])
        self.assertEqual(devteam.criterion_gaps("assert.equal(1, 1)", ["sub works"]), [])

    def test_comment_only_literal_does_not_satisfy_the_criterion(self):
        gaps = devteam.criterion_gaps("", ["returns 404"])
        self.assertEqual(gaps, [("returns 404", ["404"])])
        text = devteam._code_without_comments("// 404\nassert.equal(got, 200)")
        self.assertEqual(devteam.criterion_gaps(text, ["returns 404"]), [("returns 404", ["404"])])

    def test_python_import_allows_stdlib_repo_and_declared_dep(self):
        root = Path(self._tmpdir())
        (root / "pkg").mkdir()
        (root / "pkg" / "mod.py").write_text("x = 1\n")
        (root / "requirements.txt").write_text("Flask>=2\n")
        self.assertEqual(devteam.import_problems_in_line(root, "pkg/mod.py", "import os"), [])
        self.assertEqual(devteam.import_problems_in_line(root, "pkg/mod.py", "from pathlib import Path"), [])
        self.assertEqual(devteam.import_problems_in_line(root, "pkg/mod.py", "import pkg.mod"), [])
        self.assertEqual(devteam.import_problems_in_line(root, "pkg/mod.py", "import flask"), [])
        bad = devteam.import_problems_in_line(root, "pkg/mod.py", "import not_a_real_module_zzz")
        self.assertTrue(bad and "does not resolve" in bad[0])
        missing = devteam.import_problems_in_line(root, "pkg/mod.py", "from os import not_a_real_function_zzz")
        self.assertTrue(missing and "no such attribute" in missing[0])

    def test_relative_js_and_bare_import(self):
        root = Path(self._tmpdir())
        (root / "src").mkdir()
        (root / "src" / "real.js").write_text("exports.a = 1\n")
        (root / "package.json").write_text('{"dependencies":{"left-pad":"1.0.0"}}\n')
        self.assertEqual(
            devteam.import_problems_in_line(root, "src/app.js", 'import x from "./real.js"'), [])
        self.assertEqual(
            devteam.import_problems_in_line(root, "src/app.js", 'const fs = require("fs")'), [])
        self.assertEqual(
            devteam.import_problems_in_line(root, "src/app.js", 'const lp = require("left-pad")'), [])
        missing = devteam.import_problems_in_line(root, "src/app.js", 'import x from "./missing.js"')
        self.assertTrue(missing and "relative file missing" in missing[0])
        bare = devteam.import_problems_in_line(root, "src/app.js", 'require("not-a-package-zzz")')
        self.assertTrue(bare and "package.json" in bare[0])

    def test_go_import_follows_go_mod(self):
        root = Path(self._tmpdir())
        (root / "pkg").mkdir()
        (root / "go.mod").write_text("module example.com/app\n\ngo 1.22\n")
        self.assertEqual(devteam.import_problems_in_line(root, "main.go", 'import "fmt"'), [])
        self.assertEqual(devteam.import_problems_in_line(root, "main.go", 'import "example.com/app/pkg"'), [])
        bad = devteam.import_problems_in_line(root, "main.go", 'import "example.com/missing/mod"')
        self.assertTrue(bad and "go.mod" in bad[0])

    def test_unclaimed_reprints_only_after_the_grace_and_only_once(self):
        root = Path(self._tmpdir())
        st = {"slices": {
            "S1": {"status": "inflight", "mode": "slice", "dispatched": 1, "title": "one", "id": "S1"},
            "S2": {"status": "inflight", "mode": "research", "dispatched": 1, "title": "two", "id": "S2"},
            "S3": {"status": "pending", "mode": "slice", "dispatched": 1, "title": "three", "id": "S3"},
        }}
        with mock.patch.object(devteam, "read_claim", return_value=None), \
                mock.patch.object(devteam, "read_marker", return_value=None), \
                mock.patch.dict(os.environ, {"DEVTEAM_UNCLAIMED_S": "10"}):
            blocks = devteam.unclaimed_blocks(root, st, now_ts=100)
        self.assertEqual([b[0] for b in blocks], ["S1"])
        self.assertGreaterEqual(st["slices"]["S1"]["relaunch_at"], 100)
        with mock.patch.object(devteam, "read_claim", return_value=None), \
                mock.patch.object(devteam, "read_marker", return_value=None), \
                mock.patch.dict(os.environ, {"DEVTEAM_UNCLAIMED_S": "10"}):
            again = devteam.unclaimed_blocks(root, st, now_ts=105)
        self.assertEqual(again, [])

    @staticmethod
    def _tmpdir():
        import tempfile
        return tempfile.mkdtemp()
