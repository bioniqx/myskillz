"""Parity markers: the glm glm-dev-team port must keep the symbols the original gained in the repair.

A marker is a plain-text token that must appear in the skill's shipped files (scripts, plugins,
agents, docs; never the tests). If a future change to the original adds a guard or gate, add its
token here so the port cannot silently fall behind.
"""
import re
import unittest
from pathlib import Path

GLM_ROOT = Path(__file__).resolve().parents[2]
SKILL = GLM_ROOT / "glm-dev-team"
ORIGINAL = GLM_ROOT.parent / "claude-skills" / "claude-dev-team-v3.2"
SUFFIXES = {".py", ".js", ".sh", ".md", ".json"}
SKIP_DIRS = {"tests", "__pycache__", "docs", ".git"}

MARKERS = ("finish_gate_problems", "validate_slice_types", "salvage_worktree")


def corpus(base):
    parts = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES:
            continue
        if SKIP_DIRS & set(path.relative_to(base).parts):
            continue
        parts.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(parts)


class ParityMarkerTests(unittest.TestCase):

    def test_original_still_has_the_markers(self):
        if not ORIGINAL.is_dir():
            self.skipTest("original not present next to glm-skills")
        text = corpus(ORIGINAL)
        for marker in MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_port_has_every_marker(self):
        self.assertTrue(SKILL.is_dir(), str(SKILL))
        text = corpus(SKILL)
        for marker in MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
