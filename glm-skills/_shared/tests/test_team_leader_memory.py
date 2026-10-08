"""glm-team-leader memory path: guard edit-ro allows it and reset does not delete it."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "glm-dev-team"
GUARD = SKILL / "scripts" / "guard.py"
LEADER = SKILL / "agents" / "glm-team-leader.md"

ZCODE_FM_KEYS = ["name", "description", "color", "model", "thoughtLevel", "maxTurns", "injectAgentsMd"]

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
                           "agent_type": "glm-team-leader", "cwd": repo}
                out = subprocess.run([sys.executable, str(GUARD), "edit-ro"], input=json.dumps(payload),
                                     text=True, capture_output=True, timeout=30).stdout
                self.assertNotIn('"deny"', out, f"guard denies {rel}: {out}")
                if out.strip():
                    self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_memory_path_outside_reset_state_dir(self):
        self.assertTrue(self.paths)
        for rel in self.paths:
            self.assertFalse(rel.startswith(".claude/dev-team/"), f"{rel} is deleted by reset --yes")

    def test_frontmatter_is_final_zcode(self):
        fm = self.text.split("\n---\n")[0]
        keys = [ln.split(":", 1)[0].strip() for ln in fm.splitlines()
                if ln[:1] not in ("", " ", "\t") and ":" in ln]
        self.assertEqual(keys, ZCODE_FM_KEYS)
        self.assertIn('name: "glm-team-leader"', fm)


if __name__ == "__main__":
    unittest.main()
