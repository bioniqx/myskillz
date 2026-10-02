"""Black-box tests for audit.py verifier brief budget and investigator model tier (T10).

All fixtures live under the SYSTEM temp dir (never inside this repo/worktree).
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "claude-requirements-code-audit" / "scripts" / "audit.py"
assert SCRIPT.exists(), SCRIPT


def run(args, cwd, timeout=30):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["HOME"] = str(cwd)  # never let the script touch the real HOME
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--cwd", str(cwd)] + args,
        cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env,
    )


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


class VerifyBriefTestCase(unittest.TestCase):
    def setUp(self):
        self.cwd = Path(os.path.realpath(tempfile.mkdtemp(prefix="audit_vbrief_")))
        self.addCleanup(shutil.rmtree, str(self.cwd), True)
        (self.cwd / "spec.md").write_text("The system MUST do things.\n", encoding="utf-8")
        self.out = self.cwd / ".audit"
        self.init = run(["init", "--spec", "spec.md", "--agents", "generic", "--cap", "20"], self.cwd)
        self.assertEqual(self.init.returncode, 0, self.init.stdout + self.init.stderr)

    def make_verify_brief(self):
        row = {"id": "REQ-001", "text": "Requirement 1 text", "strength": "MUST", "category": "core",
               "stakes": "normal", "evidence_expected": "", "search_hints": ["term1"], "tags": [],
               "source": "", "question": ""}
        write_jsonl(self.out / "checklist.jsonl", [row])
        state = json.loads((self.out / "state.json").read_text(encoding="utf-8"))
        state.update(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                     spotchecked=[], hedges={}, failed=[])
        (self.out / "state.json").write_text(json.dumps(state), encoding="utf-8")
        write_jsonl(self.out / "findings" / "manual.jsonl", [
            {"id": "REQ-001", "status": "PARTIAL", "confidence": "medium",
             "evidence": [{"path": "src/x.py", "lines": "1-2", "note": "partly"}],
             "searched": ["term1"], "notes": ""}])
        r = run(["status"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        brief = self.out / "verify" / "batch-V01.md"
        self.assertTrue(brief.exists(), "status must write the verifier brief: " + r.stdout)
        return brief.read_text(encoding="utf-8")

    def test_verify_brief_has_own_budget_not_investigator_budget(self):
        text = self.make_verify_brief()
        self.assertNotIn("About 6 tool calls per requirement", text)
        self.assertNotIn("a second,\n  adversarial verifier re-checks every non-MATCHED item", text)
        self.assertNotIn("do not over-search", text)
        self.assertIn("Verifier budget", text)
        self.assertIn("No later pass re-checks you", text)

    def test_investigator_brief_keeps_first_pass_budget(self):
        row = {"id": "REQ-001", "text": "Requirement 1 text", "strength": "MUST", "category": "core",
               "stakes": "normal", "evidence_expected": "", "search_hints": ["term1"], "tags": [],
               "source": "", "question": ""}
        write_jsonl(self.out / "checklist.jsonl", [row])
        r = run(["plan"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = (self.out / "batches" / "batch-01.md").read_text(encoding="utf-8")
        self.assertIn("About 6 tool calls per requirement", text)
        self.assertNotIn("Verifier budget", text)

    def test_investigators_run_on_sonnet(self):
        self.assertRegex(self.init.stdout, r"investigator=\S+ \(sonnet\)")


if __name__ == "__main__":
    unittest.main()
