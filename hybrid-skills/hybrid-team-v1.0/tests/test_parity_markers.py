"""Parity markers: hybrid-team must keep the symbols the original dev-team gained in the repair.

A marker is a plain-text token that must appear in the skill's shipped files (never the tests).
Claude-only mode must reproduce the original, so the original's guards and gates must exist here.
"""
import re
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ORIGINAL = SKILL.parent.parent / "claude-skills" / "claude-dev-team-v3.2"
SUFFIXES = {".py", ".js", ".sh", ".md", ".json"}
SKIP_DIRS = {"tests", "__pycache__", "docs", ".git"}

MARKERS = ("finish_gate_problems", "validate_slice_types", "salvage_worktree")
SHELL_KEY = re.compile(r"""["']shell["']""")


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
            self.skipTest("original not present next to hybrid-skills")
        text = corpus(ORIGINAL)
        for marker in MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_fork_has_every_marker(self):
        text = corpus(SKILL)
        for marker in MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_missing_marker_is_reported_missing(self):
        self.assertNotIn("no_such_marker_zzq_41", corpus(SKILL))

    def test_programmer_permission_block_names_the_shell_key(self):
        text = (SKILL / "scripts" / "oc_config.py").read_text(encoding="utf-8")
        self.assertRegex(text, SHELL_KEY)


if __name__ == "__main__":
    unittest.main()
