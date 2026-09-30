import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
TOOL = SKILL / "scripts" / "plan_tool.py"
FAKE = HERE / "fake_opencode.py"
WP62 = Path(__file__).resolve().parents[3] / "claude-skills" / "writing-plans-6.2"
TOOL62 = WP62 / "scripts" / "plan_tool.py"

PLAN = "\n".join([
    "# Demo Implementation Plan",
    "",
    "**Goal:** Add greeting helpers and a small command line entry point.",
    "",
    "**Architecture:** One module per helper under `src/`.",
    "",
    "**Tech Stack:** Python 3.8 stdlib.",
    "",
    "## Global Constraints",
    "",
    "- Python stdlib only.",
    "",
    "## Contracts",
    "",
    "#### T01: greet helper",
    "- Depends: none",
    "- Files: `src/greet.py`, `tests/test_greet.py`",
    "- Produces: `def greet(name: str) -> str`",
    "- Spec: L1-4",
    "- Tier: light",
    "",
    "#### T02: farewell helper",
    "- Files: `src/bye.py`",
    "- Produces: `def bye(name: str) -> str`",
    "- Read: `src/bye.py`",
    "- Spec: L5-8",
    "",
    "#### T03: shout helper",
    "- Depends: T01",
    "- Files: `src/shout.py`",
    "- Consumes: `def greet(name: str) -> str`",
    "- Produces: `def shout(name: str) -> str`",
    "- Spec: L9-12",
    "",
    "#### T04: command line entry point",
    "- Depends: T02, T03",
    "- Files: `src/cli.py`",
    "- Spec: L13-15",
    "- Tier: deep",
    "",
])

SPEC = "\n".join([
    "# Demo spec",
    "Greeting returns Hello and the name.",
    "Names are stripped first.",
    "",
    "## Farewell",
    "Farewell returns Bye and the name.",
    "An empty name gives Bye.",
    "",
    "## Shout",
    "Shout upper-cases the greeting.",
    "It adds an exclamation mark.",
    "",
    "## CLI",
    "The CLI prints the greeting and the farewell.",
    "It exits 0.",
]) + "\n"


def make_repo(root: Path) -> Path:
    (root / ".git").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "bye.py").write_text('def bye(name):\n    return "Bye " + name\n', encoding="utf-8")
    (root / "docs" / "plans").mkdir(parents=True)
    (root / "docs" / "spec.md").write_text(SPEC, encoding="utf-8")
    plan = root / "docs" / "plans" / "2026-01-01-demo.md"
    plan.write_text(PLAN, encoding="utf-8")
    return plan


@unittest.skipUnless(TOOL62.is_file(), "writing-plans-6.2 is not present next to this skill")
class GoldenTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hp-golden-"))
        self.repo = self.tmp / "repo"
        self.plan = make_repo(self.repo)
        self.spec = self.repo / "docs" / "spec.md"
        self.work = self.plan.parent / ".work" / self.plan.stem
        (self.tmp / "home").mkdir()
        routing = json.loads((SKILL / "routing.default.json").read_text(encoding="utf-8"))
        routing["preset"] = "claude"
        (self.tmp / "routing.json").write_text(json.dumps(routing), encoding="utf-8")
        tier = {"listed": True, "ping": "ok", "note": "", "down": None}
        doctor = {"t": "2026-09-28T00:00:00Z", "ok": True, "version": "2.0.18", "binary": str(FAKE), "tiers": {
            "std": dict(tier, model="zai-coding-plan/glm-5.3", variant="high"),
            "lite": dict(tier, model="zai-coding-plan/glm-5.3-flash", variant="low")}}
        (self.tmp / "doctor.json").write_text(json.dumps(doctor), encoding="utf-8")
        self.env = dict(os.environ)
        self.env.pop("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", None)
        self.env.update({
            "HOME": str(self.tmp / "home"),
            "HP_ROUTING": str(self.tmp / "routing.json"),
            "HP_DOCTOR_CACHE": str(self.tmp / "doctor.json"),
            "HP_TELEMETRY": str(self.tmp / "lanes.jsonl"),
            "HP_OC_BIN": str(FAKE),
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        self.env.pop("HYBRID_OPENCODE_STD", None)
        self.env.pop("HYBRID_OPENCODE_LITE", None)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_tool(self, tool, *args):
        p = subprocess.run([sys.executable, str(tool)] + [str(x) for x in args], cwd=str(self.repo),
                           env=self.env, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout

    def snapshot(self):
        briefs = self.work / "briefs"
        return {f.name: f.read_text(encoding="utf-8") for f in sorted(briefs.iterdir())} if briefs.is_dir() else {}

    def compare(self, *args):
        rc62, out62 = self.run_tool(TOOL62, "contracts", self.plan, *args)
        briefs62 = self.snapshot()
        shutil.rmtree(self.work)
        rc, out = self.run_tool(TOOL, "contracts", self.plan, *args)
        briefs = self.snapshot()

        def swap(s):
            return s.replace(str(TOOL62), str(TOOL))

        self.assertEqual(rc62, 0, out62)
        self.assertEqual(rc, rc62, out)
        self.assertEqual(out, swap(out62))
        self.assertTrue(briefs62)
        self.assertEqual(sorted(briefs), sorted(briefs62))
        for name, text in briefs62.items():
            self.assertEqual(briefs[name], swap(text), name)

    def test_one_writer_per_task(self):
        self.compare("--spec", self.spec)

    def test_grouped_writers(self):
        self.compare("--spec", self.spec, "--agents", "2")


if __name__ == "__main__":
    unittest.main()
