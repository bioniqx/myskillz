import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEW_SCRIPTS = HERE.parent / "scripts"
ORIG = Path(__file__).resolve().parents[2] / "requirements-code-audit"
ORIG_SCRIPTS = ORIG / "scripts"
FAKE = HERE / "fake_opencode.py"
TS_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?")
UNAVAILABLE = "opencode: unavailable → preset claude (run audit.py doctor --ping)"

APP = "def login(password):\n    return check(password)\n\ndef export_csv():\n    return ''\n"
SPEC = "# Spec\n\n1. Users must log in with a password.\n\n2. Admins must approve new accounts.\n"
CHECKLIST = [
    {"id": "REQ-001", "text": "Users must log in with a password", "strength": "MUST", "category": "auth",
     "stakes": "high", "evidence_expected": "a login handler", "search_hints": ["login", "password"], "tags": [],
     "source": "§1"},
    {"id": "REQ-002", "text": "Sessions should expire after 30 minutes", "strength": "SHOULD", "category": "auth",
     "stakes": "normal", "search_hints": ["session", "expire"], "tags": [], "source": "§1"},
    {"id": "REQ-003", "text": "Admins must approve new accounts", "strength": "MUST", "category": "admin",
     "stakes": "normal", "search_hints": ["approve"], "tags": [], "source": "§2"},
    {"id": "REQ-004", "text": "Reports may be exported as CSV", "strength": "MAY", "category": "reports",
     "stakes": "normal", "search_hints": ["csv"], "tags": [], "source": "§3"},
    {"id": "REQ-005", "text": "Audit logs must be kept", "strength": "MUST", "category": "admin",
     "stakes": "normal", "search_hints": ["audit"], "tags": [], "source": "§2"},
    {"id": "REQ-006", "text": "The system should be fast", "strength": "SHOULD", "category": "perf",
     "stakes": "normal", "search_hints": [], "tags": ["ambiguous"], "question": "How fast?", "source": "§4"},
]
FINDINGS = {"REQ-001": ("MATCHED", "high"), "REQ-002": ("PARTIAL", "medium"), "REQ-003": ("MISSING", "low"),
            "REQ-004": ("MATCHED", "high"), "REQ-005": ("MATCHED", "high")}
EVIDENCE = [{"path": "src/app.py", "lines": "1-2", "note": "login handler"}]
SEARCHED = ["login", "password", "session", "expire", "approve", "approval", "csv", "audit"]


def finding_row(rid):
    status, conf = FINDINGS[rid]
    return {"id": rid, "status": status, "confidence": conf, "excerpt": "", "notes": "note for " + rid,
            "evidence": [] if status == "MISSING" else list(EVIDENCE), "searched": list(SEARCHED)}


def verdict_row(rid):
    status = FINDINGS[rid][0]
    return {"id": rid, "verified_status": status, "agree": True, "confidence": "high",
            "evidence": [] if status == "MISSING" else list(EVIDENCE), "searched": ["approval flow"],
            "reason": "confirmed " + rid}


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


@unittest.skipUnless((ORIG_SCRIPTS / "audit.py").exists(), "requirements-code-audit is not present")
class GoldenTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        home = self.tmp / "home"
        home.mkdir()
        self.env = dict(os.environ)
        self.env.pop("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", None)
        self.env.pop("HYBRID_OPENCODE_STD", None)
        self.env.pop("HYBRID_OPENCODE_LITE", None)
        self.env.update({"HOME": str(home), "HA_ROUTING": str(self.tmp / "config" / "routing.json"),
                         "HA_DOCTOR_CACHE": str(self.tmp / "cache" / "doctor.json"),
                         "HA_TELEMETRY": str(self.tmp / "cache" / "lanes.jsonl"), "HA_OC_BIN": str(FAKE),
                         "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def run_side(self, side, scripts, init_extra):
        root = self.tmp / side
        work = root / "work"
        (work / "src").mkdir(parents=True)
        (work / "src" / "app.py").write_text(APP, encoding="utf-8")
        spec = work / "spec.md"
        spec.write_text(SPEC, encoding="utf-8")
        out = work / ".audit"

        def cli(*args):
            r = subprocess.run([sys.executable, str(scripts / "audit.py"), "--cwd", str(work)] + list(args),
                               env=self.env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stdout)
            return r.stdout

        def norm(text):
            text = text.replace(str(scripts), "<SCRIPTS>").replace(str(root), "<ROOT>")
            return TS_RE.sub("<TS>", text)

        texts = {"init": norm(cli("init", "--spec", str(spec), "--cap", "4", *init_extra))}
        write_rows(out / "checklist.jsonl", CHECKLIST)
        texts["plan"] = norm(cli("plan", "--cap", "4"))
        state = json.loads((out / "state.json").read_text(encoding="utf-8"))
        for name, meta in state["batches"].items():
            write_rows(out / "findings" / (name + ".jsonl"), [finding_row(rid) for rid in meta["ids"]])
        texts["status-1"] = norm(cli("status"))
        state = json.loads((out / "state.json").read_text(encoding="utf-8"))
        for name, meta in state.get("verify", {}).items():
            write_rows(out / "verify" / (name + ".jsonl"), [verdict_row(rid) for rid in meta["ids"]])
        texts["status-2"] = norm(cli("status"))
        texts["report"] = norm(cli("report"))
        for sub in ("batches", "verify"):
            for f in sorted((out / sub).glob("*.md")):
                texts["%s/%s" % (sub, f.name)] = norm(f.read_text(encoding="utf-8"))
        for fname in ("requirements-code-audit.md", "traceability.csv"):
            texts[fname] = norm((out / fname).read_text(encoding="utf-8"))
        return texts

    def test_claude_preset_matches_original(self):
        orig = self.run_side("orig", ORIG_SCRIPTS, [])
        new = self.run_side("new", NEW_SCRIPTS, ["--preset", "claude"])
        self.assertEqual(sorted(new), sorted(orig))
        self.assertTrue(any(k.startswith("verify/") for k in orig))
        for key in sorted(orig):
            if key != "init":
                self.assertEqual(new[key], orig[key], key)

    def test_init_differs_only_by_opencode_line(self):
        orig = self.run_side("orig", ORIG_SCRIPTS, [])["init"].splitlines()
        new = self.run_side("new", NEW_SCRIPTS, ["--preset", "claude"])["init"].splitlines()
        self.assertEqual([line for line in new if line.startswith("opencode:")], [UNAVAILABLE])
        self.assertEqual([line for line in new if not line.startswith("opencode:")], orig)
        self.assertTrue(new[new.index(UNAVAILABLE) - 1].startswith("  repo map  :"))
