import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
ORIG = Path(__file__).resolve().parents[2] / "requirements-code-audit"
FORK_AUDIT = HERE / "scripts" / "audit.py"

SPEC = (
    "# Spec\n\n"
    "## 1. Auth\n"
    "Users MUST log in with email and password.\n"
    "Sessions MUST expire after 30 minutes.\n\n"
    "## 2. Orders\n"
    "The system SHOULD list the orders of the current user.\n"
    "Orders MAY be exported as CSV.\n"
)

CHECKLIST = [
    {"id": "REQ-%03d" % i, "text": "Requirement number %d MUST hold." % i, "strength": "MUST",
     "category": "auth" if i % 2 else "orders", "stakes": "high" if i == 1 else "normal",
     "evidence_expected": "code for requirement %d" % i, "search_hints": ["req%d" % i, "login"],
     "tags": [], "source": "§%d" % i}
    for i in range(1, 8)
]
CHECKLIST.append({"id": "REQ-008", "text": "Pages MUST load in under 200 ms.", "strength": "MUST",
                  "category": "perf", "stakes": "normal", "search_hints": ["latency"],
                  "tags": ["static-limit"], "source": "§3"})


def child_env(tmp):
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", None)
    env.pop("HYBRID_OPENCODE_STD", None)
    env.pop("HYBRID_OPENCODE_LITE", None)
    home = Path(tmp) / "home"
    home.mkdir(parents=True, exist_ok=True)
    env.update({
        "HOME": str(home),
        "HYBRID_AUDIT_ROUTING": str(Path(tmp) / "routing.json"),
        "HYBRID_AUDIT_DOCTOR_CACHE": str(Path(tmp) / "doctor.json"),
        "HYBRID_AUDIT_TELEMETRY": str(Path(tmp) / "lanes.jsonl"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
    })
    # Never reach the real opencode (its `models` can block for a minute on an isolated HOME).
    stub = Path(tmp) / "bin" / "opencode"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    stub.chmod(0o755)
    env["PATH"] = str(stub.parent) + os.pathsep + env.get("PATH", "")
    return env


def run(script, root, env, *args):
    p = subprocess.run([sys.executable, str(script), "--cwd", str(root)] + list(args), env=env,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8")
    if p.returncode != 0:
        raise AssertionError("%s %s exited %d:\n%s%s" % (script, " ".join(args), p.returncode, p.stdout, p.stderr))
    return p


def make_audit(script, root, env, cap=3):
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app.py").write_text("def login(email, password):\n    return True\n", encoding="utf-8")
    (root / "spec.md").write_text(SPEC, encoding="utf-8")
    run(script, root, env, "init", "--spec", str(root / "spec.md"), "--cap", str(cap), "--lang", "en")
    (root / ".hybrid-audit" / "checklist.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in CHECKLIST) + "\n", encoding="utf-8")


def norm(text, root):
    return text.replace(str(root), "<ROOT>")


def load_audit():
    import audit
    return audit


class ForkFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.env = child_env(self.tmp)

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_fork_files_exist(self):
        for rel in ("scripts/audit.py", "references/report-format.md", "references/workflow-mode.md"):
            self.assertTrue((HERE / rel).is_file(), rel)

    @unittest.skipUnless(ORIG.is_dir(), "requirements-code-audit not present")
    def test_references_match_original(self):
        for name in ("report-format.md", "workflow-mode.md"):
            self.assertEqual((HERE / "references" / name).read_bytes(),
                             (ORIG / "references" / name).read_bytes(), name)

    @unittest.skipUnless(ORIG.is_dir(), "requirements-code-audit not present")
    def test_plan_and_parse_plan_match_original(self):
        outs = []
        for script, sub in ((ORIG / "scripts" / "audit.py", "orig"), (FORK_AUDIT, "fork")):
            root = self.tmp / sub / "work"
            make_audit(script, root, self.env)
            texts = [norm(run(script, root, self.env, "plan").stdout, root),
                     norm(run(script, root, self.env, "parse-plan", "--sections", "2").stdout, root)]
            audit_dir = root / ".hybrid-audit"
            files = sorted((audit_dir / "batches").glob("*.md")) + sorted((audit_dir / "parse").glob("*.md"))
            self.assertTrue(files)
            for f in files:
                texts.append(f.name + "\n" + norm(f.read_text(encoding="utf-8"), root))
            outs.append(texts)
        self.assertEqual(outs[0], outs[1])


class PartitionItemsTest(unittest.TestCase):
    def items(self, n):
        return [{"id": "REQ-%03d" % i, "category": "c%d" % (i % 2)} for i in range(1, n + 1)]

    def test_even_split_sorted_by_category_then_id(self):
        audit = load_audit()
        items = self.items(10)
        before = [r["id"] for r in items]
        batches = audit.partition_items(items, 4, False)
        self.assertEqual([len(b) for b in batches], [3, 3, 2, 2])
        flat = [r["id"] for b in batches for r in b]
        self.assertEqual(flat, [r["id"] for r in sorted(items, key=lambda r: (r["category"], r["id"]))])
        self.assertEqual([r["id"] for r in items], before)

    def test_one_item_per_batch_when_cap_is_large(self):
        audit = load_audit()
        batches = audit.partition_items(self.items(30), 64, False)
        self.assertEqual(len(batches), 30)
        self.assertTrue(all(len(b) == 1 for b in batches))

    def test_max_batch_limits_batch_size(self):
        audit = load_audit()
        batches = audit.partition_items(self.items(100), 4, False)
        self.assertEqual(len(batches), 9)
        self.assertEqual(max(len(b) for b in batches), audit.MAX_BATCH)
        self.assertEqual(sum(len(b) for b in batches), 100)

    def test_solo_uses_solo_batch_size(self):
        audit = load_audit()
        batches = audit.partition_items(self.items(10), 64, True)
        self.assertEqual([len(b) for b in batches], [5, 5])

    def test_empty(self):
        audit = load_audit()
        self.assertEqual(audit.partition_items([], 4, False), [])


class BodyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.env = child_env(self.tmp)
        self.root = self.tmp / "work"
        make_audit(FORK_AUDIT, self.root, self.env)
        run(FORK_AUDIT, self.root, self.env, "plan")
        self.audit = load_audit()
        self.c = self.audit.Ctx(str(self.root))
        self.repo_map = (self.c.out / "repo_map.md").read_text(encoding="utf-8")
        self.by_id = {r["id"]: r for r in self.c.checklist()[0]}

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def test_batch_body_matches_plan_files(self):
        c = self.c
        self.assertTrue(c.state["batches"])
        for name, meta in c.state["batches"].items():
            items = [self.by_id[i] for i in meta["ids"]]
            body = self.audit.batch_body(c, name, items, self.repo_map, c.out / "findings" / (name + ".jsonl"))
            self.assertEqual(body, (c.out / "batches" / (name + ".md")).read_text(encoding="utf-8"))

    def test_batch_body_custom_output(self):
        c = self.c
        item = self.by_id["REQ-001"]
        outp = c.out / "findings" / "batch-01.r5.jsonl"
        body = self.audit.batch_body(c, "batch-01-r5", [item], self.repo_map, outp)
        self.assertTrue(body.startswith("# Investigator batch-01-r5 — requirements↔code audit\nCodebase root: %s\n" % c.repo))
        self.assertIn("Write findings to: %s\n" % outp, body)
        self.assertIn("`batch-01-r5 done: <k>/1 written`", body)
        self.assertIn(self.audit.HARD_RULES, body)
        self.assertTrue(body.endswith(self.audit.item_block(item)))
        self.assertFalse((c.out / "batches" / "batch-01-r5.md").exists())

    def test_verify_body(self):
        c = self.c
        rid = c.state["batches"]["batch-01"]["ids"][0]
        rid2 = c.state["batches"]["batch-02"]["ids"][0]
        row = {"id": rid, "status": "missing", "confidence": "low", "evidence": [],
               "searched": ["login"], "notes": "nothing found"}
        (c.out / "findings" / "batch-01.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        m = self.audit.Merged(c)
        body = self.audit.verify_body(c, "batch-V01", [rid, rid2], m, self.repo_map)
        self.assertTrue(body.startswith(
            "# Verifier batch-V01 — requirements↔code audit (adversarial second pass)\nCodebase root: %s\nWrite verdicts to: %s\n"
            % (c.repo, c.out / "verify" / "batch-V01.jsonl")))
        self.assertIn("`batch-V01 done: <k>/2 written`", body)
        self.assertIn("Preliminary finding: status=MISSING confidence=low", body)
        self.assertIn("  already searched: login", body)
        self.assertIn("  notes: nothing found", body)
        self.assertIn("Preliminary finding: NONE (UNSEARCHED", body)
        self.assertIn(self.audit.VERIFY_RULES, body)
        self.assertIn("## Items to verify (2)\n", body)
        self.assertFalse((c.out / "verify" / "batch-V01.md").exists())

    def test_parse_body_matches_parse_plan_files(self):
        run(FORK_AUDIT, self.root, self.env, "parse-plan", "--sections", "2")
        c = self.audit.Ctx(str(self.root))
        chunks = self.audit.split_sections(self.audit.load_spec_text(c.cfg["spec_files"]), 2)
        files = sorted((c.out / "parse").glob("section-*.md"))
        self.assertEqual(len(files), len(chunks))
        for i, chunk in enumerate(chunks, 1):
            name = "section-%02d" % i
            outp = c.out / "parse" / (name + ".jsonl")
            body = self.audit.parse_body(c, name, chunk, outp)
            self.assertEqual(body, (c.out / "parse" / (name + ".md")).read_text(encoding="utf-8"))

    def test_parse_body_section_ids(self):
        c = self.c
        outp = c.out / "parse" / "section-07.jsonl"
        body = self.audit.parse_body(c, "section-07", "Users MUST log in.", outp)
        self.assertTrue(body.startswith(
            "# Parser section-07 — requirements↔code audit (spec parsing)\nWrite your output to: %s\n" % outp))
        self.assertIn("`S07-001`, `S07-002`", body)
        self.assertIn(self.audit.CHECKLIST_RULES, body)
        self.assertIn(self.audit.CHECKLIST_SCHEMA, body)
        self.assertTrue(body.endswith("## SECTION TEXT (verbatim; language: en)\nUsers MUST log in.\n"))


if __name__ == "__main__":
    unittest.main()
