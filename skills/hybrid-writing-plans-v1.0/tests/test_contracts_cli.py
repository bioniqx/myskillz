import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPTS = SKILL / "scripts"
TOOL = SCRIPTS / "plan_tool.py"
FAKE = HERE / "fake_opencode.py"
sys.path.insert(0, str(SCRIPTS))

import hp_telemetry  # noqa: E402

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


class CliBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hp-cli-"))
        self.repo = self.tmp / "repo"
        self.plan = make_repo(self.repo)
        self.spec = self.repo / "docs" / "spec.md"
        self.work = self.plan.parent / ".work" / self.plan.stem
        (self.tmp / "home").mkdir()
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
        self.q = "python3 " + shlex.quote(str(TOOL))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tool(self, *args):
        p = subprocess.run([sys.executable, str(TOOL)] + [str(x) for x in args], cwd=str(self.repo),
                           env=self.env, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout, p.stderr

    def write_doctor(self):
        tier = {"listed": True, "ping": "ok", "note": "", "down": None}
        doctor = {"t": "2026-09-28T00:00:00Z", "ok": True, "version": "2.0.18", "binary": str(FAKE), "tiers": {
            "std": dict(tier, model="zai-coding-plan/glm-5.3", variant="high"),
            "lite": dict(tier, model="zai-coding-plan/glm-5.3-flash", variant="low")}}
        Path(self.env["HP_DOCTOR_CACHE"]).write_text(json.dumps(doctor), encoding="utf-8")

    def work_json(self):
        return json.loads((self.work / "work.json").read_text(encoding="utf-8"))


class ContractsRoutingTest(CliBase):
    def test_hybrid_routes_light_and_std_to_opencode(self):
        self.write_doctor()
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec)
        self.assertEqual(rc, 0, out + err)
        lines = out.splitlines()
        ok = [l for l in lines if l.startswith("OK contracts:")]
        self.assertEqual(len(ok), 1, out)
        self.assertTrue(ok[0].endswith("| 1 writers (cap 20) | 3 opencode groups"), ok[0])
        oc_head = "OPENCODE 3 groups (T01, T02, T03) | run in the BACKGROUND in the SAME message: %s oc-write %s" % (
            self.q, shlex.quote(str(self.plan)))
        self.assertIn(oc_head, lines)
        briefs = self.work / "briefs"
        for gid, backend, span in (("O01", "oc:lite", "T01"), ("O02", "oc:std", "T02"), ("O03", "oc:std", "T03")):
            self.assertIn("%-4s %-7s %-9s %s" % (gid, backend, span, briefs / (gid + ".oc.md")), lines)
            self.assertTrue((briefs / (gid + ".oc.md")).is_file(), gid)
            self.assertFalse((briefs / (gid + ".md")).exists(), gid)
        self.assertIn("%-4s %-7s %-9s %s" % ("T04", "opus", "T04", briefs / "T04.md"), lines)
        self.assertTrue((briefs / "T04.md").is_file())
        dispatch = [i for i, l in enumerate(lines) if l.startswith("DISPATCH 1 writers in ONE message")]
        self.assertEqual(len(dispatch), 1, out)
        self.assertLess(dispatch[0], lines.index(oc_head))
        self.assertEqual(lines[-1], "THEN run: %s wait %s" % (self.q, shlex.quote(str(self.plan))))
        info = self.work_json()
        for key in ("plan", "spec", "repo", "allow", "agents", "tasks", "groups", "review"):
            self.assertIn(key, info)
        self.assertEqual(info["preset"], "hybrid")
        self.assertEqual(info["backend"], {"O01": "oc:lite", "O02": "oc:std", "O03": "oc:std", "T04": "claude"})
        self.assertEqual(info["groups"], {"O01": ["T01"], "O02": ["T02"], "O03": ["T03"], "T04": ["T04"]})
        self.assertEqual(info["oc"]["tiers"]["std"]["model"], "zai-coding-plan/glm-5.3")
        self.assertEqual(info["oc"]["tiers"]["lite"]["variant"], "low")
        self.assertEqual(info["oc"]["max_repairs"], 2)
        self.assertEqual(info["oc"]["throttle_cooldown_s"], 120)
        self.assertEqual(info["oc"]["review_oc"], "all")

    def test_max_preset_sends_every_task_to_opencode(self):
        self.write_doctor()
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "max")
        self.assertEqual(rc, 0, out + err)
        lines = out.splitlines()
        ok = [l for l in lines if l.startswith("OK contracts:")][0]
        self.assertTrue(ok.endswith("| 0 writers (cap 20) | 4 opencode groups"), ok)
        self.assertFalse([l for l in lines if l.startswith("DISPATCH")], out)
        self.assertNotIn("ID   MODEL   TASKS     BRIEF", lines)
        self.assertTrue(any(l.startswith("OPENCODE 4 groups (T01, T02, T03, T04) |") for l in lines), out)
        info = self.work_json()
        self.assertEqual(info["preset"], "max")
        self.assertEqual(info["backend"], {"O01": "oc:lite", "O02": "oc:std", "O03": "oc:std", "O04": "oc:std"})
        self.assertEqual(info["oc"]["review_oc"], "risky")

    def test_missing_doctor_cache_keeps_every_task_on_claude(self):
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec)
        self.assertEqual(rc, 0, out + err)
        self.assertNotIn("OPENCODE", out)
        self.assertNotIn("opencode groups", out)
        info = self.work_json()
        self.assertEqual(set(info["backend"].values()), {"claude"})
        self.assertEqual(sorted(f.name for f in (self.work / "briefs").iterdir()),
                         ["T01.md", "T02.md", "T03.md", "T04.md"])

    def test_preset_claude_ignores_a_healthy_opencode(self):
        self.write_doctor()
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "claude")
        self.assertEqual(rc, 0, out + err)
        self.assertNotIn("OPENCODE", out)
        info = self.work_json()
        self.assertEqual(info["preset"], "claude")
        self.assertEqual(set(info["backend"].values()), {"claude"})


class ContractsResetTest(CliBase):
    def seed_stale(self):
        oc = self.work / "oc"
        tasks = self.work / "tasks"
        oc.mkdir(parents=True)
        tasks.mkdir(parents=True)
        (oc / "oc-write.pid").write_text("999999\n", encoding="utf-8")
        (oc / "O09.fallback").write_text(json.dumps({"gid": "O09", "reason": "lint", "tasks": ["T04"]}), encoding="utf-8")
        (tasks / "T04.md.oc").write_text(json.dumps({"tier": "std", "model": "m", "variant": "", "round": 1}),
                                         encoding="utf-8")
        return oc, tasks

    def test_contracts_clears_stale_oc_scratch(self):
        self.write_doctor()
        oc, _ = self.seed_stale()
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec)
        self.assertEqual(rc, 0, out + err)
        self.assertFalse((oc / "oc-write.pid").exists())
        self.assertFalse((oc / "O09.fallback").exists())
        self.assertEqual(list(oc.iterdir()) if oc.exists() else [], [])

    def test_contracts_clears_stale_task_oc_markers(self):
        _, tasks = self.seed_stale()
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "claude")
        self.assertEqual(rc, 0, out + err)
        self.assertFalse((tasks / "T04.md.oc").exists())
        self.assertEqual(list(tasks.glob("*.md.oc")), [])


class OcWriteTest(CliBase):
    def test_oc_write_without_opencode_groups(self):
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "claude")
        self.assertEqual(rc, 0, out + err)
        rc, out, err = self.tool("oc-write", self.plan)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(out.strip(), "OC none")


class DoctorTest(CliBase):
    def test_doctor_with_missing_binary(self):
        missing = str(self.tmp / "no-such-opencode")
        self.env["HP_OC_BIN"] = missing
        routing = Path(self.env["HP_ROUTING"])
        rc, out, err = self.tool("doctor")
        self.assertEqual(rc, 1, out + err)
        lines = out.splitlines()
        self.assertIn("routing: %s (created from defaults)" % routing, lines)
        self.assertIn("opencode: unavailable (%s)" % missing, lines)
        self.assertIn("doctor cache: %s" % self.env["HP_DOCTOR_CACHE"], lines)
        defaults = json.loads((SKILL / "routing.default.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(routing.read_text(encoding="utf-8")), defaults)
        cache = json.loads(Path(self.env["HP_DOCTOR_CACHE"]).read_text(encoding="utf-8"))
        self.assertFalse(cache.get("ok"))
        rc, out, err = self.tool("doctor")
        self.assertEqual(rc, 1, out + err)
        self.assertIn("routing: %s" % routing, out.splitlines())


class StatsTest(CliBase):
    def write_records(self):
        tokens = {"input": 1000, "output": 400, "reasoning": 50, "cache_read": 10, "cache_write": 5}
        recs = [
            {"t": "2026-09-28T10:00:00Z", "kind": "group", "repo": str(self.repo), "plan": str(self.plan),
             "gid": "O01", "tier": "std", "model": "zai-coding-plan/glm-5.3", "variant": "high",
             "tasks": ["T01", "T02"], "rounds": 2, "round1_ok": 1, "outcome": "ok", "reason": "",
             "duration_s": 42.0, "tokens": tokens},
            {"t": "2026-09-28T11:00:00Z", "kind": "group", "repo": "/elsewhere", "plan": "/elsewhere/p.md",
             "gid": "O01", "tier": "lite", "model": "zai-coding-plan/glm-5.3-flash", "variant": "low",
             "tasks": ["T03"], "rounds": 3, "round1_ok": 0, "outcome": "fallback", "reason": "lint",
             "duration_s": 80.5, "tokens": tokens},
            {"t": "2026-09-28T12:00:00Z", "kind": "review", "repo": str(self.repo), "plan": str(self.plan),
             "task": "T01", "tier": "std", "fixed_by_review": True},
        ]
        path = Path(self.env["HP_TELEMETRY"])
        path.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
        return path

    def test_stats_all_repos(self):
        path = self.write_records()
        rc, out, err = self.tool("stats")
        self.assertEqual(rc, 0, out + err)
        want = hp_telemetry.stats_lines(hp_telemetry.load_records(path), "")
        self.assertTrue(want)
        self.assertEqual(out, "".join(l + "\n" for l in want))

    def test_stats_one_repo(self):
        path = self.write_records()
        rc, out, err = self.tool("stats", "--repo", self.repo)
        self.assertEqual(rc, 0, out + err)
        want = hp_telemetry.stats_lines(hp_telemetry.load_records(path), str(self.repo))
        self.assertEqual(out, "".join(l + "\n" for l in want))

    def test_stats_without_telemetry(self):
        rc, out, err = self.tool("stats")
        self.assertEqual(rc, 0, out + err)
        want = hp_telemetry.stats_lines([], "")
        self.assertEqual(out, "".join(l + "\n" for l in want))


if __name__ == "__main__":
    unittest.main()
