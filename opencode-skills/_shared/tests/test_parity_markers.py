"""Parity markers: the oc dev-team port must keep the symbols the original gained in the repair.

A marker is a plain-text token that must appear in the skill's shipped files (scripts, plugins,
agents, docs; never the tests). If a future change to the original adds a guard or gate, add its
token here so the port cannot silently fall behind.
"""
import re
import unittest
from pathlib import Path

OC_ROOT = Path(__file__).resolve().parents[2]
SKILL = OC_ROOT / "oc-dev-team"
ORIGINAL = OC_ROOT.parent / "claude-skills" / "claude-dev-team-v3.2"
SUFFIXES = {".py", ".js", ".sh", ".md", ".json"}
SKIP_DIRS = {"tests", "__pycache__", "docs", ".git"}

MARKERS = ("finish_gate_problems", "commit_errors", "salvage_worktree")
SHELL_KEY = re.compile(r"""["']shell["']|\bshell\s*:""")
OLD_BASH_KEY = re.compile(r"""["']bash["']\s*:|^\s*bash\s*:""", re.M)


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
            self.skipTest("original not present next to opencode-skills")
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

    def test_port_names_the_shell_permission_key(self):
        self.assertRegex(corpus(SKILL), SHELL_KEY)

    def test_port_has_no_v1_bash_permission_key(self):
        agents = SKILL / "agents"
        self.assertTrue(agents.is_dir(), str(agents))
        for path in sorted(agents.glob("*.md")):
            with self.subTest(agent=path.name):
                self.assertNotRegex(path.read_text(encoding="utf-8"), OLD_BASH_KEY)


if __name__ == "__main__":
    unittest.main()
