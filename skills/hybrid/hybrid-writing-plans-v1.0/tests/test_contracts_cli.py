import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPTS = SKILL / "scripts"
TOOL = SCRIPTS / "plan_tool.py"
FAKE = HERE / "fake_opencode.py"
sys.path.insert(0, str(SCRIPTS))

import hp_telemetry  # noqa: E402
import hybrid_shared  # noqa: E402

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


SHARED = {"tiers": {
    "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high"},
    "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low"}}}
SHARED_VARS = {"HYBRID_OPENCODE_STD": "zai-coding-plan/glm-5.3#high",
              "HYBRID_OPENCODE_LITE": "zai-coding-plan/glm-5.3-flash#low"}


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
            "XDG_DATA_HOME": str(self.tmp / "xdg"),
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        self.env.pop("HYBRID_OPENCODE_STD", None)
        self.env.pop("HYBRID_OPENCODE_LITE", None)
        self.q = "python3 " + shlex.quote(str(TOOL))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def tool(self, *args):
        p = subprocess.run([sys.executable, str(TOOL)] + [str(x) for x in args], cwd=str(self.repo),
                           env=self.env, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout, p.stderr

    def set_shared(self, env=None):
        self.env.update(SHARED_VARS if env is None else env)

    def write_doctor(self, bad_tiers=(), checked_at=None):
        self.set_shared()
        stamp = time.time() if checked_at is None else checked_at
        tiers = {}
        for name, spec in SHARED["tiers"].items():
            entry = {"ok": True, "key": hybrid_shared.cache_key(spec), "checked_at": stamp,
                     "kind": "", "detail": ""}
            if name in bad_tiers:
                entry.update({"ok": False, "kind": "auth", "detail": "401 unauthorized"})
            tiers[name] = entry
        doctor = {"t": "2026-09-29T00:00:00Z", "ok": True, "version": "2.0.19", "binary": str(FAKE),
                  "tiers": tiers}
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

    def test_opencode_preset_sends_every_task_to_opencode(self):
        self.write_doctor()
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "opencode")
        self.assertEqual(rc, 0, out + err)
        lines = out.splitlines()
        ok = [l for l in lines if l.startswith("OK contracts:")][0]
        self.assertTrue(ok.endswith("| 0 writers (cap 20) | 4 opencode groups"), ok)
        self.assertFalse([l for l in lines if l.startswith("DISPATCH")], out)
        self.assertNotIn("ID   MODEL   TASKS     BRIEF", lines)
        self.assertTrue(any(l.startswith("OPENCODE 4 groups (T01, T02, T03, T04) |") for l in lines), out)
        self.assertFalse([l for l in lines if l.startswith("OC-")], out)
        info = self.work_json()
        self.assertEqual(info["preset"], "opencode")
        self.assertEqual(info["backend"], {"O01": "oc:lite", "O02": "oc:std", "O03": "oc:std", "O04": "oc:std"})

    def test_preset_claude_ignores_a_healthy_opencode(self):
        self.write_doctor()
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "claude")
        self.assertEqual(rc, 0, out + err)
        self.assertNotIn("OPENCODE", out)
        info = self.work_json()
        self.assertEqual(info["preset"], "claude")
        self.assertEqual(set(info["backend"].values()), {"claude"})


class ContractsReportingTest(CliBase):
    def oc_lines(self, out, level="OC-ERROR"):
        return [l for l in out.splitlines() if l.startswith(level + " hybrid-writing-plans")]

    def test_max_is_an_alias_for_opencode_with_a_warning(self):
        self.write_doctor()
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "max")
        self.assertEqual(rc, 0, out + err)
        warns = self.oc_lines(out, "OC-WARN")
        self.assertEqual(len(warns), 1, out)
        self.assertIn("kind=config", warns[0])
        self.assertEqual(self.work_json()["preset"], "opencode")

    def test_unknown_preset_is_a_config_error(self):
        self.write_doctor()
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "bogus")
        self.assertNotEqual(rc, 0, out + err)
        errors = self.oc_lines(out)
        self.assertEqual(len(errors), 1, out)
        self.assertIn("kind=config", errors[0])
        self.assertFalse((self.work / "work.json").exists())

    def test_missing_doctor_cache_falls_back_to_claude_and_reports(self):
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec)
        self.assertEqual(rc, 0, out + err)
        self.assertFalse([l for l in out.splitlines() if l.startswith("OPENCODE ")], out)
        self.assertNotIn("opencode groups", out)
        errors = self.oc_lines(out)
        self.assertTrue(errors, out)
        self.assertTrue(all("kind=config" in l for l in errors), errors)
        info = self.work_json()
        self.assertEqual(set(info["backend"].values()), {"claude"})
        self.assertEqual(sorted(f.name for f in (self.work / "briefs").iterdir()),
                         ["T01.md", "T02.md", "T03.md", "T04.md"])

    def test_stale_doctor_entries_fall_back_to_claude_and_report(self):
        self.write_doctor(checked_at=1.0)
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec)
        self.assertEqual(rc, 0, out + err)
        self.assertTrue(self.oc_lines(out), out)
        self.assertEqual(set(self.work_json()["backend"].values()), {"claude"})

    def test_failed_tier_is_reported_and_does_not_disable_the_other_tier(self):
        self.write_doctor(bad_tiers=("std",))
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec)
        self.assertEqual(rc, 0, out + err)
        errors = self.oc_lines(out)
        self.assertEqual(len(errors), 1, out)
        for part in ("tier=std", "kind=auth", "401 unauthorized"):
            self.assertIn(part, errors[0])
        backends = set(self.work_json()["backend"].values())
        self.assertIn("oc:lite", backends)
        self.assertNotIn("oc:std", backends)

    def test_preset_claude_is_silent_without_any_config(self):
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "claude")
        self.assertEqual(rc, 0, out + err)
        self.assertFalse([l for l in out.splitlines() if l.startswith("OC-")], out)
        self.assertEqual(set(self.work_json()["backend"].values()), {"claude"})

    def test_opencode_preset_holds_groups_when_no_tier_is_usable(self):
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "opencode")
        self.assertEqual(rc, 0, out + err)
        lines = out.splitlines()
        self.assertTrue(self.oc_lines(out), out)
        self.assertTrue([l for l in lines if l.startswith("HELD ")], out)
        self.assertFalse([l for l in lines if l.startswith(("DISPATCH", "OPENCODE", "THEN run"))], out)
        self.assertIn("NOTHING dispatched: every group is held", lines)
        info = self.work_json()
        self.assertEqual(info["preset"], "opencode")
        self.assertEqual(set(info["backend"].values()), {"held"})
        for gid in info["groups"]:
            self.assertTrue((self.work / "briefs" / (gid + ".md")).is_file(), gid)

    def test_model_in_the_user_file_is_used_for_that_tier(self):
        self.write_doctor()
        Path(self.env["HP_ROUTING"]).write_text(
            json.dumps({"tiers": {"std": {"model": "own/model"}}}), encoding="utf-8")
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.oc_lines(out, "OC-WARN"), [], out)
        errors = self.oc_lines(out)
        self.assertEqual(len(errors), 1, out)
        for part in ("tier=std", "model=own/model", "kind=config"):
            self.assertIn(part, errors[0])
        tiers = self.work_json()["oc"]["tiers"]
        self.assertEqual(tiers["std"]["model"], "own/model")
        self.assertNotIn("variant", tiers["std"])
        self.assertEqual(tiers["lite"]["model"], "zai-coding-plan/glm-5.3-flash")


def body_t02(extra=""):
    fence = "`" * 3
    return "\n".join([
        "**Files:**", "- Modify: `src/bye.py`", "",
        "- [ ] **Step 1: Write bye**", "",
        fence + "python", "def bye(name: str) -> str:", '    return "Bye " + name', fence, "",
        "- [ ] **Step 2: Check**", "",
        "Run: `python3 -m py_compile src/bye.py`", "Expected: no output", "",
        "- [ ] **Step 3: Commit**", "",
        fence + "bash", "git add src/bye.py", 'git commit -m "feat: bye"', fence, extra,
    ]) + "\n"


def body_simple(path, sig, tid, other=None):
    fence = "`" * 3
    adds = path + (" " + other if other else "")
    return "\n".join(["**Files:**", "- Create: `%s`" % path] + (["- Create: `%s`" % other] if other else []) + [
        "", "- [ ] **Step 1: Write**", "", fence + "python", sig + ":", "    return name", fence, "",
        "- [ ] **Step 2: Check**", "", "Run: `python3 -m py_compile %s`" % path, "Expected: no output", "",
        "- [ ] **Step 3: Commit**", "", fence + "bash", "git add " + adds, 'git commit -m "feat: %s"' % tid, fence]) + "\n"


def plan_tool_done(path):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import plan_tool
    return plan_tool.done_state(str(path), "ok")


class ContractsRerunTest(CliBase):
    def seed_written_t02(self):
        tasks = self.work / "tasks"
        (tasks / "T02.md").write_text(body_t02(), encoding="utf-8")
        (tasks / "T02.md.ok").write_text("1", encoding="utf-8")
        (tasks / "T02.md.oc").write_text(json.dumps({"tier": "std", "round": 1}), encoding="utf-8")

    def first_run(self, *extra):
        self.write_doctor()
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, *extra)
        self.assertEqual(rc, 0, out + err)
        return out

    def opencode_row(self, out):
        return [l for l in out.splitlines() if l.startswith("OPENCODE ")][0]

    def test_rerun_keeps_a_written_opencode_body_and_dispatches_only_the_rest(self):
        self.first_run()
        self.seed_written_t02()
        (self.work / "tasks" / "T02.md").write_text(body_t02("\nreviewer touched this\n"), encoding="utf-8")  # .ok is stale
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "hybrid")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("2 groups (T01, T03)", self.opencode_row(out))
        self.assertFalse((self.work / "briefs" / "O02.oc.md").exists())
        self.assertTrue((self.work / "briefs" / "O03.oc.md").is_file())
        self.assertIn("reviewer touched this", (self.work / "tasks" / "T02.md").read_text(encoding="utf-8"))
        self.assertTrue((self.work / "tasks" / "T02.md.oc").exists())
        self.assertEqual(plan_tool_done(self.work / "tasks" / "T02.md"), "done")  # the stale mark was refreshed
        self.assertTrue(any(l.endswith("| 2 opencode groups") for l in out.splitlines()), out)

    def test_rerun_with_every_opencode_task_written_dispatches_no_opencode_group(self):
        self.first_run()
        self.seed_written_t02()
        (self.work / "tasks" / "T01.md").write_text(
            body_simple("src/greet.py", "def greet(name: str) -> str", "t01", "tests/test_greet.py"), encoding="utf-8")
        (self.work / "tasks" / "T03.md").write_text(
            body_simple("src/shout.py", "def shout(name: str) -> str", "t03"), encoding="utf-8")
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "hybrid")
        self.assertEqual(rc, 0, out + err)
        self.assertIn("OPENCODE none to run", out)
        self.assertFalse([l for l in out.splitlines() if l.startswith("OPENCODE ") and "groups" in l], out)
        self.assertEqual(list((self.work / "briefs").glob("*.oc.md")), [])

    def test_brief_of_a_partly_written_group_names_only_the_pending_tasks(self):
        Path(self.env["HP_ROUTING"]).write_text(json.dumps({"tiers": {"std": {"max_parallel": 1}}}), encoding="utf-8")
        self.first_run()
        self.assertEqual(self.work_json()["groups"]["O02"], ["T02", "T03"])
        self.seed_written_t02()
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "hybrid")
        self.assertEqual(rc, 0, out + err)
        brief = (self.work / "briefs" / "O02.oc.md").read_text(encoding="utf-8")
        self.assertIn("@@@ BEGIN T03", brief)
        self.assertNotIn("@@@ BEGIN T02", brief)
        self.assertNotIn("Contract T02", brief)

    def test_changed_contract_invalidates_body_marks_and_oc_marker(self):
        self.first_run()
        self.seed_written_t02()
        (self.work / "tasks" / "T02.md.fail").write_text("old", encoding="utf-8")
        text = self.plan.read_text(encoding="utf-8").replace("- Spec: L5-8", "- Spec: L5-7")
        self.plan.write_text(text, encoding="utf-8")
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "hybrid")
        self.assertEqual(rc, 0, out + err)
        for suffix in ("", ".ok", ".oc", ".fail"):
            self.assertFalse((self.work / "tasks" / ("T02.md" + suffix)).exists(), suffix)
        self.assertIn("3 groups (T01, T02, T03)", self.opencode_row(out))

    def test_stale_doctor_in_the_middle_of_a_run_does_not_downgrade_a_tier(self):
        self.first_run()
        before = self.work_json()["backend"]
        self.assertIn("oc:std", before.values())
        self.write_doctor(checked_at=1.0)  # the cache went stale
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec)  # no --preset: the run's mode is kept
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.work_json()["backend"], before)
        self.assertEqual(self.work_json()["preset"], "hybrid")
        self.assertFalse([l for l in out.splitlines() if l.startswith("OC-")], out)

    def test_a_real_failure_after_the_first_run_still_downgrades_the_tier(self):
        self.first_run()
        self.write_doctor(bad_tiers=("std",))
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec)
        self.assertEqual(rc, 0, out + err)
        self.assertNotIn("oc:std", self.work_json()["backend"].values())
        self.assertTrue([l for l in out.splitlines() if l.startswith("OC-ERROR") and "kind=auth" in l], out)

    def test_the_frozen_opencode_mode_survives_a_rerun_without_preset(self):
        self.first_run("--preset", "opencode")
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec)
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(self.work_json()["preset"], "opencode")


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

    def test_contracts_starts_a_new_run_unswitched(self):
        self.write_doctor()
        oc, _ = self.seed_stale()
        hybrid_shared.switch_to_claude(oc, "O01", "std", "m", "auth", "401")
        self.assertTrue(hybrid_shared.run_switched(oc))
        rc, out, err = self.tool("contracts", self.plan, "--spec", self.spec, "--preset", "hybrid")
        self.assertEqual(rc, 0, out + err)
        self.assertEqual(hybrid_shared.run_switched(oc), {})
        self.assertFalse((oc / hybrid_shared.SWITCH_FILE).exists())

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
    def missing_binary(self):
        missing = str(self.tmp / "no-such-opencode")
        self.env["HP_OC_BIN"] = missing
        return missing

    def test_doctor_with_missing_binary_creates_no_routing_file(self):
        missing = self.missing_binary()
        routing = Path(self.env["HP_ROUTING"])
        rc, out, err = self.tool("doctor")
        self.assertEqual(rc, 1, out + err)
        lines = out.splitlines()
        self.assertIn("opencode: unavailable (%s)" % missing, lines)
        self.assertIn("doctor cache: %s" % self.env["HP_DOCTOR_CACHE"], lines)
        self.assertFalse(routing.exists())
        cache = json.loads(Path(self.env["HP_DOCTOR_CACHE"]).read_text(encoding="utf-8"))
        self.assertFalse(cache.get("ok"))
        rc, out, err = self.tool("doctor")
        self.assertEqual(rc, 1, out + err)
        self.assertFalse(routing.exists())

    def test_doctor_prints_the_shared_config_summary(self):
        self.missing_binary()
        self.set_shared()
        rc, out, err = self.tool("doctor")
        summary = [l for l in out.splitlines() if l.startswith("opencode config") and hybrid_shared.SHARED_SOURCE in l]
        self.assertEqual(len(summary), 1, out)
        self.assertIn("glm-5.3", summary[0])

    def test_doctor_reports_an_invalid_shared_config(self):
        self.missing_binary()
        self.set_shared({"HYBRID_OPENCODE_STD": "no-provider-prefix"})
        rc, out, err = self.tool("doctor")
        self.assertEqual(rc, 1, out + err)
        errors = [l for l in out.splitlines() if l.startswith("OC-ERROR hybrid-writing-plans")]
        self.assertTrue(errors, out)
        self.assertTrue(all("kind=config" in l for l in errors), errors)


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
