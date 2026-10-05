"""dev-team OpenCode agents: model-free frontmatter, the .opencode state dir, programmer lanes that work
through workdir + absolute paths and finish with `report`, and the team-leader memory path that guard oc
allows and `reset --yes` never deletes."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[2] / "oc-dev-team"
GUARD = SKILL / "scripts" / "oc_guard.py"
AGENTS = SKILL / "opencode" / "agents"
LEADER = AGENTS / "oc-team-leader.md"

FRONTMATTER = """---
name: oc-team-leader
description: Senior technical lead for the dev-team workflow. PLANNING: deep analysis of a request against the real codebase → an executable, maximally parallel vertical-slice plan (pinned contracts, disjoint footprints, testable acceptance criteria, risk, isolation) written as .opencode/oc-dev-team/plan.md with a machine-readable JSON block. PLAN ADOPTION: maps an existing plan onto slices without re-deriving it. Plans any kind of software work — features, bug fixes, refactors, migrations, test backfill, performance, infrastructure/CI, documentation and read-only research — as one DAG of typed slices. VERIFICATION: judges whether delivered code fulfills the user's intent. Reasoning-heavy, read-only; remembers each repository's map across sessions.
temperature: 1.0
access: write
bash: true
web: true
steps: 120
---
"""

MEM_RE = re.compile(r"`?(\.opencode/[^\s`]*MEMORY\.md)`?")
AGENT_NAMES = ["oc-code-reviewer", "oc-investigator", "oc-programmer", "oc-spot-reviewer", "oc-team-leader"]


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

    def test_guard_oc_allows_every_memory_path(self):
        with tempfile.TemporaryDirectory() as repo:
            for rel in set(self.paths):
                payload = {"tool": "write", "args": {"filePath": f"{repo}/{rel}"},
                           "role": "team-leader", "cwd": repo}
                out = subprocess.run([sys.executable, str(GUARD), "oc"], input=json.dumps(payload),
                                     text=True, capture_output=True, timeout=30).stdout
                self.assertNotIn('"deny"', out, f"guard denies {rel}: {out}")
                if out.strip():
                    self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_memory_path_outside_reset_state_dir(self):
        self.assertTrue(self.paths)
        for rel in self.paths:
            self.assertFalse(rel.startswith(".opencode/oc-dev-team/"), f"{rel} is deleted by reset --yes")

    def test_frontmatter_has_no_model_or_effort(self):
        self.assertTrue(self.text.startswith(FRONTMATTER))


class AgentFiles(unittest.TestCase):
    def agents(self):
        return {p.stem: p.read_text(encoding="utf-8") for p in sorted(AGENTS.glob("*.md"))}

    def test_the_five_agents_are_model_free_and_use_the_opencode_state_dir(self):
        agents = self.agents()
        self.assertEqual(sorted(agents), AGENT_NAMES)
        for name, text in agents.items():
            head = text.split("\n---\n", 1)[0].splitlines()
            for key in ("model:", "effort:", "reasoningEffort:", "variant:"):
                self.assertFalse(any(ln.startswith(key) for ln in head), f"{name} sets {key}")

    def test_programmer_works_through_workdir_and_finishes_with_report(self):
        text = self.agents()["oc-programmer"]
        for phrase in ("claim <ID> --worktree <wt>", "workdir=<wt>", "absolute paths under `<wt>/`",
                       "report <ID> --file <wt>/.oc-slice/report.md", "NOT ACCEPTED", "REPORTED <ID>"):
            self.assertIn(phrase, text)

    def test_team_leader_names_no_model_routing(self):
        text = self.agents()["oc-team-leader"]
        self.assertIn("it orders the scheduler's critical path (the heaviest chain of slices starts first).", text)
        self.assertIn("Width is the product you are designing. The engine's lane limit is a stated limit", text)
        self.assertNotIn("model routing", text.lower())


ROOT = Path(__file__).resolve().parents[2]


class LeftoverNames(unittest.TestCase):
    def test_team_leader_names_the_opencode_memory_path(self):
        text = LEADER.read_text(encoding="utf-8")
        self.assertIn(".opencode/agent-memory/oc-team-leader/MEMORY.md", text)

    def test_audit_version_is_new_and_doctor_prints_it(self):
        audit = ROOT / "oc-requirements-code-audit" / "scripts" / "oc_audit.py"
        m = re.search(r'^VERSION = "([^"]*)"', audit.read_text(encoding="utf-8"), re.M)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "10.0")
        with tempfile.TemporaryDirectory() as home:
            out = subprocess.run([sys.executable, str(audit), "doctor"], capture_output=True, text=True,
                                 timeout=60, cwd=home, env={"HOME": home, "PATH": "/usr/bin:/bin",
                                                            "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertIn("10.0", out.stdout + out.stderr)

    def test_server_brand_is_plain_label_without_links_or_telemetry(self):
        text = (ROOT / "oc-brainstorming" / "scripts" / "oc-server.cjs").read_text(encoding="utf-8")
        self.assertIn('<span class="brand-copy">Brainstorming</span>', text)
        self.assertNotIn("github.com", text)
        self.assertNotIn("TELEMETRY", text)


if __name__ == "__main__":
    unittest.main()
