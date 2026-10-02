"""OpenCode team-leader memory path: guard edit-ro allows it and reset does not delete it."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "dev-team-glm"
GUARD = SKILL / "scripts" / "guard.py"
LEADER = SKILL / "opencode" / "agents" / "team-leader.md"

FRONTMATTER = """---
name: team-leader
description: Senior technical lead for the dev-team workflow. PLANNING: deep analysis of a request against the real codebase → an executable, maximally parallel vertical-slice plan (pinned contracts, disjoint footprints, testable acceptance criteria, risk, isolation) written as .claude/dev-team/plan.md with a machine-readable JSON block. PLAN ADOPTION: maps an existing plan onto slices without re-deriving it. Plans any kind of software work — features, bug fixes, refactors, migrations, test backfill, performance, infrastructure/CI, documentation and read-only research — as one DAG of typed slices. VERIFICATION: judges whether delivered code fulfills the user's intent. Reasoning-heavy, read-only; remembers each repository's map across sessions.
model: pro
effort: max
temperature: 1.0
access: write
bash: true
web: true
steps: 120
---
"""

MEM_RE = re.compile(r"`?(\.claude/[^\s`]*MEMORY\.md)`?")


class TeamLeaderMemory(unittest.TestCase):
    def setUp(self):
        self.text = LEADER.read_text(encoding="utf-8")
        self.paths = MEM_RE.findall(self.text)

    def test_memory_paths_present_and_consistent(self):
        self.assertGreaterEqual(len(self.paths), 2, "Memory paragraph and step 2 must both name the path")
        self.assertEqual(len(set(self.paths)), 1, f"memory paths differ: {sorted(set(self.paths))}")

    def test_memory_paragraph_and_planning_step2_name_same_path(self):
        para = re.search(r"\*\*Memory\.\*\*(.*?)\n\n", self.text, re.S)
        step2 = re.search(r"\n2\. \*\*Ground it in the code\.\*\*(.*?)\n3\. ", self.text, re.S)
        self.assertIsNotNone(para)
        self.assertIsNotNone(step2)
        p1, p2 = MEM_RE.findall(para.group(1)), MEM_RE.findall(step2.group(1))
        self.assertTrue(p1 and p2)
        self.assertEqual(set(p1), set(p2))

    def test_guard_edit_ro_allows_every_memory_path(self):
        with tempfile.TemporaryDirectory() as repo:
            for rel in set(self.paths):
                payload = {"tool_name": "Write", "tool_input": {"file_path": f"{repo}/{rel}"},
                           "agent_type": "team-leader", "cwd": repo}
                out = subprocess.run([sys.executable, str(GUARD), "edit-ro"], input=json.dumps(payload),
                                     text=True, capture_output=True, timeout=30).stdout
                self.assertNotIn('"deny"', out, f"guard denies {rel}: {out}")
                if out.strip():
                    self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_memory_path_outside_reset_state_dir(self):
        self.assertTrue(self.paths)
        for rel in self.paths:
            self.assertFalse(rel.startswith(".claude/dev-team/"), f"{rel} is deleted by reset --yes")

    def test_frontmatter_unchanged(self):
        self.assertTrue(self.text.startswith(FRONTMATTER))


if __name__ == "__main__":
    unittest.main()
