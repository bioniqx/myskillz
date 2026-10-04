"""Parity markers: hybrid-requirements-code-audit must keep its evidence oracle and the shared
failure-line helpers that every hybrid skill vendors.
"""
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
ORIGINAL = SKILL.parent.parent / "claude-skills" / "claude-requirements-code-audit"
SUFFIXES = {".py", ".js", ".sh", ".md", ".json"}
SKIP_DIRS = {"tests", "__pycache__", "docs", ".git"}

FORK_MARKERS = ("oc_line", "take_unreported")


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

    def test_original_audit_engine_is_present(self):
        if not ORIGINAL.is_dir():
            self.skipTest("original not present next to hybrid-skills")
        self.assertTrue((ORIGINAL / "scripts" / "audit.py").is_file())

    def test_fork_keeps_the_evidence_oracle(self):
        self.assertTrue((SKILL / "scripts" / "ha_oracle.py").is_file())

    def test_fork_has_every_marker(self):
        text = corpus(SKILL)
        for marker in FORK_MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_missing_marker_is_reported_missing(self):
        self.assertNotIn("no_such_marker_zzq_41", corpus(SKILL))


if __name__ == "__main__":
    unittest.main()
