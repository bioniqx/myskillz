"""Black-box tests for T11: parse threshold near 800 words and lean investigator batch briefs.

Fixtures live under the system temp dir, never inside this repo.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
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


def checklist_row(i):
    return {
        "id": "REQ-%03d" % i, "text": "Requirement %d text" % i, "strength": "MUST",
        "category": "core", "stakes": "normal", "evidence_expected": "",
        "search_hints": ["term%d" % i], "tags": [], "source": "", "question": "",
    }


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


class BatchTokensTestCase(unittest.TestCase):
    def setUp(self):
        self.cwd = Path(os.path.realpath(tempfile.mkdtemp(prefix="audit_tokens_")))
        self.addCleanup(shutil.rmtree, str(self.cwd), True)
        self.out = self.cwd / ".audit"

    def init_audit(self, words=5, agents="generic", cap=20):
        (self.cwd / "spec.md").write_text(" ".join(["word"] * words) + "\n", encoding="utf-8")
        r = run(["init", "--spec", "spec.md", "--agents", agents, "--cap", str(cap)], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def plan(self, n):
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, n + 1)])
        r = run(["plan"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def batch_files(self):
        return sorted(p.name for p in (self.out / "batches").glob("batch-*.md"))

    def batch_text(self, name):
        return (self.out / "batches" / (name + ".md")).read_text(encoding="utf-8")

    # ---------------------------------------------------------------- parse threshold

    def test_spec_over_800_words_gets_parser_dispatch(self):
        r = self.init_audit(words=1000)
        self.assertIn("parallelise parsing", r.stdout, r.stdout)

    def test_spec_under_800_words_is_read_by_the_lead(self):
        r = self.init_audit(words=700)
        self.assertNotIn("parallelise parsing", r.stdout, r.stdout)
        self.assertIn("read the spec", r.stdout, r.stdout)

    # ---------------------------------------------------------------- lean batch briefs

    def test_local_agents_batch_omits_rules_block(self):
        self.init_audit(agents="local")
        self.plan(4)
        text = self.batch_text("batch-01")
        self.assertNotIn("## Hard rules", text)
        self.assertNotIn("## Speed rules", text)
        self.assertIn("## Repo map", text)
        self.assertIn("## Requirements", text)
        self.assertIn("UNSEARCHED", text)

    def test_generic_agents_batch_keeps_rules_block(self):
        self.init_audit(agents="generic")
        self.plan(4)
        text = self.batch_text("batch-01")
        self.assertIn("## Hard rules", text)
        self.assertIn("## Speed rules", text)

    # ---------------------------------------------------------------- batch sizing

    def test_local_agents_target_two_to_three_items_per_batch(self):
        self.init_audit(agents="local", cap=20)
        self.plan(7)
        names = self.batch_files()
        self.assertEqual(names, ["batch-01.md", "batch-02.md", "batch-03.md"])
        sizes = [self.batch_text(n[:-3]).count("### REQ-") for n in names]
        self.assertEqual(sum(sizes), 7)
        self.assertTrue(all(2 <= s <= 3 for s in sizes), sizes)

    def test_generic_agents_batch_count_unchanged(self):
        self.init_audit(agents="generic", cap=20)
        self.plan(9)
        names = self.batch_files()
        self.assertEqual(len(names), 9, names)


class SearchGlobRuleTests(unittest.TestCase):
    def test_generic_brief_carries_grep_glob_rule(self):
        cwd = Path(os.path.realpath(tempfile.mkdtemp(prefix="audit_glob_")))
        self.addCleanup(shutil.rmtree, str(cwd), True)
        (cwd / "spec.md").write_text("word\n", encoding="utf-8")
        r = run(["init", "--spec", "spec.md", "--agents", "generic"], cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        write_jsonl(cwd / ".audit" / "checklist.jsonl", [checklist_row(1)])
        r = run(["plan"], cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        text = (cwd / ".audit" / "batches" / "batch-01.md").read_text(encoding="utf-8")
        self.assertIn('glob="!*.md', text)

    def test_agent_files_carry_grep_glob_rule(self):
        base = Path(__file__).resolve().parents[1] / "claude-requirements-code-audit" / "agents"
        for n in ("claude-rca-investigator.md", "claude-rca-verifier.md"):
            self.assertIn("!*.md", (base / n).read_text(encoding="utf-8"), n)


if __name__ == "__main__":
    unittest.main()
