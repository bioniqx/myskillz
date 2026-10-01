import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from oc_brief import build_brief, BRIEF_CAP


class BuildBriefTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.worktree = Path(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_build_brief_includes_core_sections(self):
        s = {
            "goal": "Add the router module",
            "criteria": ["router.py exists", "tests pass"],
            "contracts": ["def route(row: str) -> str"],
            "footprint": ["scripts/router.py"],
            "commands": [],
            "context": [],
        }
        brief = build_brief("Claim: implement router", s, self.worktree, [])
        self.assertIn("Claim: implement router", brief)
        self.assertIn("Add the router module", brief)
        self.assertIn("router.py exists", brief)
        self.assertIn("def route(row: str) -> str", brief)
        self.assertIn("scripts/router.py", brief)

    def test_build_brief_inlines_frozen_test_file(self):
        test_path = self.worktree / "tests" / "test_router.py"
        test_path.parent.mkdir(parents=True)
        test_path.write_text(
            "def test_route():\n    assert route('code') == 'std'\n"
        )
        s = {
            "goal": "Add router",
            "criteria": [],
            "contracts": [],
            "footprint": [],
            "commands": [],
            "context": [],
        }
        brief = build_brief("Claim", s, self.worktree, ["tests/test_router.py"])
        self.assertIn("Frozen RED test (expect GREEN)", brief)
        self.assertIn("def test_route():", brief)
        self.assertIn("assert route('code') == 'std'", brief)

    def test_build_brief_inlines_context_file(self):
        ctx_path = self.worktree / "docs" / "notes.md"
        ctx_path.parent.mkdir(parents=True)
        ctx_path.write_text("Routing notes: trivial rows map to lite tier.")
        s = {
            "goal": "Add router",
            "criteria": [],
            "contracts": [],
            "footprint": [],
            "commands": ["python3 -m unittest discover -s tests"],
            "context": ["docs/notes.md"],
        }
        brief = build_brief("Claim", s, self.worktree, [])
        self.assertIn("Context files", brief)
        self.assertIn("Routing notes: trivial rows map to lite tier.", brief)
        self.assertIn("python3 -m unittest discover -s tests", brief)

    def test_build_brief_truncates_when_over_cap(self):
        s = {
            "goal": "x" * 100,
            "criteria": [],
            "contracts": [],
            "footprint": [],
            "commands": [],
            "context": [],
        }
        brief = build_brief("Claim", s, self.worktree, [], cap=100)
        self.assertLessEqual(len(brief), 100)
        self.assertIn("truncated", brief)

    def test_missing_context_file_is_skipped(self):
        s = {
            "goal": "Add router",
            "criteria": [],
            "contracts": [],
            "footprint": [],
            "commands": [],
            "context": ["docs/missing.md"],
        }
        brief = build_brief("Claim", s, self.worktree, [])
        self.assertNotIn("docs/missing.md", brief)
        self.assertNotIn("Context files", brief)

    def test_context_path_strips_symbol_suffix(self):
        ctx_path = self.worktree / "src" / "y.py"
        ctx_path.parent.mkdir(parents=True)
        ctx_path.write_text("def Foo():\n    return 1\n")
        s = {
            "goal": "Add router",
            "criteria": [],
            "contracts": [],
            "footprint": [],
            "commands": [],
            "context": ["src/y.py#Foo"],
        }
        brief = build_brief("Claim", s, self.worktree, [])
        self.assertIn("Context files", brief)
        self.assertIn("def Foo():", brief)

    def test_build_brief_does_not_raise_on_invalid_utf8(self):
        frozen_path = self.worktree / "tests" / "test_bad.py"
        frozen_path.parent.mkdir(parents=True)
        frozen_path.write_bytes(b"def test_x():\n    pass  # \xff\xfe bad bytes\n")
        ctx_path = self.worktree / "docs" / "bad.md"
        ctx_path.parent.mkdir(parents=True)
        ctx_path.write_bytes(b"Note: \xff\xfe invalid utf-8 bytes here.")
        s = {
            "goal": "Add router",
            "criteria": [],
            "contracts": [],
            "footprint": [],
            "commands": [],
            "context": ["docs/bad.md"],
        }
        brief = build_brief("Claim", s, self.worktree, ["tests/test_bad.py"])
        self.assertIn("def test_x():", brief)

    def test_build_brief_skips_context_file_with_nul_byte(self):
        ctx_path = self.worktree / "docs" / "nul.md"
        ctx_path.parent.mkdir(parents=True)
        ctx_path.write_bytes(b"before\x00after")
        s = {
            "goal": "Add router",
            "criteria": [],
            "contracts": [],
            "footprint": [],
            "commands": [],
            "context": ["docs/nul.md"],
        }
        brief = build_brief("Claim", s, self.worktree, [])
        self.assertNotIn("\x00", brief)
        self.assertNotIn("before", brief)
        self.assertNotIn("Context files", brief)

    def test_build_brief_reads_utf8_regardless_of_locale(self):
        ctx_path = self.worktree / "docs" / "unicode.md"
        ctx_path.parent.mkdir(parents=True)
        ctx_path.write_bytes("cafe notes: éé ☃".encode("utf-8"))
        scripts_dir = str(Path(__file__).resolve().parents[1] / "scripts")
        out_path = Path(self.tmp) / "brief_out.bin"
        code = (
            "import sys; sys.path.insert(0, {scripts!r});"
            "from oc_brief import build_brief;"
            "s = {{'goal': '', 'criteria': [], 'contracts': [], "
            "'footprint': [], 'commands': [], 'context': ['docs/unicode.md']}};"
            "brief = build_brief('Claim', s, {worktree!r}, []);"
            "open({out!r}, 'wb').write(brief.encode('utf-8'))"
        ).format(scripts=scripts_dir, worktree=str(self.worktree), out=str(out_path))
        env = dict(os.environ)
        env["LC_ALL"] = "C"
        env["LANG"] = "C"
        env["PYTHONUTF8"] = "0"
        env.pop("PYTHONIOENCODING", None)
        result = subprocess.run(
            [sys.executable, "-c", code], env=env, capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        content = out_path.read_bytes().decode("utf-8")
        self.assertIn("éé ☃", content)


if __name__ == "__main__":
    unittest.main()
