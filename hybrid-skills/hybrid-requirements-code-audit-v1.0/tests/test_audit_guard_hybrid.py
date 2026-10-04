"""Black-box tests for the hybrid audit guard hook and the text layer around it.

Fixtures live under the system temp dir; the hook runs as a subprocess with a minimal
environment (HOME and CLAUDE_CONFIG_DIR point into the fixture).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
GUARD_PY = SKILL_DIR / "hooks" / "audit_guard.py"
GUARD_SH = SKILL_DIR / "hooks" / "audit_guard.sh"
WORKER = "claude-req-audit:claude-rca-investigator"


def run_guard(project, event, via_launcher=False):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(project / "home"),
        "CLAUDE_CONFIG_DIR": str(project / "home" / ".claude"),
        "CLAUDE_PROJECT_DIR": str(project),
    }
    if via_launcher:
        cmd = ["bash", str(GUARD_SH)]
    else:
        cmd = [sys.executable, str(GUARD_PY)]
    return subprocess.run(cmd, input=json.dumps(event), capture_output=True, text=True,
                          env=env, timeout=30)


def decision(result):
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


def reason(result):
    return json.loads(result.stdout)["hookSpecificOutput"].get("permissionDecisionReason", "")


class GuardHookTests(unittest.TestCase):
    def setUp(self):
        self.project = Path(os.path.realpath(tempfile.mkdtemp()))
        self.addCleanup(shutil.rmtree, str(self.project), True)

    def arm(self, dirname=".hybrid-audit"):
        audit = self.project / dirname
        audit.mkdir()
        (audit / "ACTIVE").write_text("1")
        cfg = {"active": True, "repo_root": str(self.project), "out_dir": str(audit),
               "spec_files": [str(self.project / "spec.txt")], "scripts_dir": ""}
        (audit / "config.json").write_text(json.dumps(cfg))
        return audit

    def pre(self, tool, tool_input, **extra):
        event = {"hook_event_name": "PreToolUse", "tool_name": tool,
                 "tool_input": tool_input, "cwd": str(self.project)}
        event.update(extra)
        return event

    def test_files_exist(self):
        self.assertTrue(GUARD_PY.is_file(), "missing %s" % GUARD_PY)
        self.assertTrue(GUARD_SH.is_file(), "missing %s" % GUARD_SH)

    def test_git_history_denied_when_hybrid_dir_is_active(self):
        self.arm()
        result = run_guard(self.project, self.pre("Bash", {"command": "git log -p"}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(decision(result), "deny")
        self.assertIn("hybrid-requirements-code-audit", reason(result))

    def test_original_audit_dir_does_not_arm_the_guard(self):
        self.arm(".audit")
        result = run_guard(self.project, self.pre("Bash", {"command": "git log -p"}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_write_outside_audit_dir_denied(self):
        self.arm()
        target = str(self.project / "src" / "app.py")
        result = run_guard(self.project, self.pre("Write", {"file_path": target}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(decision(result), "deny")

    def test_write_inside_audit_dir_allowed(self):
        audit = self.arm()
        target = str(audit / "findings" / "batch-01.jsonl")
        result = run_guard(self.project, self.pre("Write", {"file_path": target}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(decision(result), "allow")

    def test_worker_write_shell_denied(self):
        self.arm()
        event = self.pre("Bash", {"command": "rm -rf build"}, agent_type=WORKER, agent_id="a1")
        result = run_guard(self.project, event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(decision(result), "deny")
        self.assertIn("workers are read-only", reason(result))

    def test_worker_prose_read_denied(self):
        self.arm()
        event = self.pre("Read", {"file_path": str(self.project / "README.md")},
                         agent_type=WORKER, agent_id="a1")
        result = run_guard(self.project, event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(decision(result), "deny")
        self.assertIn("prose documentation", reason(result))
        self.assertIn("workers", reason(result))

    def test_git_dir_read_denied(self):
        self.arm()
        event = self.pre("Read", {"file_path": str(self.project / ".git" / "config")})
        result = run_guard(self.project, event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(decision(result), "deny")

    def test_subagent_stop_records_event(self):
        audit = self.arm()
        event = {"hook_event_name": "SubagentStop", "agent_type": WORKER, "agent_id": "a1",
                 "last_assistant_message": "batch-03 done", "cwd": str(self.project)}
        result = run_guard(self.project, event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(decision(result))
        record = json.loads((audit / "events" / "batch-03.json").read_text())
        self.assertTrue(record["ok"])
        self.assertEqual(record["batch"], "batch-03")
        self.assertEqual(record["agent_type"], WORKER)

    def test_launcher_is_silent_without_marker(self):
        result = run_guard(self.project, self.pre("Bash", {"command": "git log -p"}),
                           via_launcher=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_launcher_runs_guard_when_active(self):
        self.arm()
        result = run_guard(self.project, self.pre("Bash", {"command": "git log -p"}),
                           via_launcher=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(decision(result), "deny")

    def test_launcher_ignores_original_marker(self):
        self.arm(".audit")
        result = run_guard(self.project, self.pre("Bash", {"command": "git log -p"}),
                           via_launcher=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")


class TextLayerTests(unittest.TestCase):
    CHECKED = ("SKILL.md", "SETUP.md", "README.md", "references/schemas.md",
               "references/workflow-mode.md")

    def read(self, rel):
        return (SKILL_DIR / rel).read_text(encoding="utf-8")

    def test_no_stale_agent_or_plugin_names(self):
        stale = re.compile(r"(?<![\w-])(rca-|req-audit)")
        for rel in self.CHECKED:
            match = stale.search(self.read(rel))
            self.assertIsNone(match, "%s still has %r" % (rel, match and match.group(0)))

    def test_setup_registers_this_forks_hook(self):
        setup = self.read("SETUP.md")
        self.assertIn("hybrid-requirements-code-audit-v1.0/hooks/audit_guard.sh", setup)
        self.assertNotIn("$HOME/.claude/skills/requirements-code-audit/hooks/audit_guard.sh", setup)

    def test_parse_threshold_and_investigator_model_match_the_original(self):
        skill = self.read("SKILL.md")
        self.assertIn("> ~800 words", skill)
        self.assertNotIn("~2,500", skill)
        self.assertIn("| Investigators | Claude sonnet |", skill)
        self.assertIn("| `claude` | Claude sonnet | Claude sonnet |", self.read("README.md"))

    def test_schemas_names_match_the_injected_agents(self):
        schemas = self.read("references/schemas.md")
        self.assertNotIn("opencode:ha-", schemas)
        self.assertIn("opencode:hybrid-audit-<role>", schemas)
        self.assertIn("hooks/audit_guard.py", schemas)

    def test_workflow_mode_investigators_use_sonnet(self):
        flow = self.read("references/workflow-mode.md")
        self.assertIn("model `sonnet`", flow)
        self.assertNotIn("model `haiku`", flow)

    def test_matched_high_confidence_ceiling_is_documented(self):
        self.assertIn("accepted ceiling", self.read("SKILL.md"))
        self.assertIn("accepted ceiling", self.read("README.md"))

    def test_guard_claims_are_true(self):
        skill = self.read("SKILL.md")
        self.assertNotIn("ships no Claude agents or guard hooks", skill)
        self.assertNotIn("bundled agents, guard hooks", skill)
        self.assertIn("hooks/audit_guard.py", skill)

    def test_changelog_records_the_guard(self):
        self.assertIn("audit_guard", self.read("CHANGELOG.md"))


if __name__ == "__main__":
    unittest.main()
