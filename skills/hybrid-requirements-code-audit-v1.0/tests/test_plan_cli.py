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
SCRIPTS = HERE.parent / "scripts"
AUDIT = SCRIPTS / "audit.py"
FAKE = HERE / "fake_opencode.py"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ha_briefs  # noqa: E402
import ha_telemetry  # noqa: E402

UNAVAILABLE = "opencode: unavailable → preset claude (run audit.py doctor --ping)"
DOWN = {"reason": "unavailable", "message": "plan expired", "at": "2026-09-28T00:00:00Z"}


def tier_entry(model, variant, down=None):
    return {"model": model, "variant": variant, "listed": True, "ping": "ok", "note": "", "down": down}


def doctor_ok(std_down=None):
    return {"t": "2026-09-28T09:30:00Z", "ok": True, "version": "2.0.18", "binary": "opencode",
            "tiers": {"std": tier_entry("zai-coding-plan/glm-5.3", "high", std_down),
                      "lite": tier_entry("zai-coding-plan/glm-5.3-flash", "low")}}


def checklist_rows(n):
    return [{"id": "REQ-%03d" % i, "text": "Requirement %d must hold" % i, "strength": "MUST",
             "category": "core", "stakes": "normal", "search_hints": ["req%d" % i], "tags": [],
             "source": "§%d" % i} for i in range(1, n + 1)]


class CliBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.work = self.tmp / "work"
        (self.work / "src").mkdir(parents=True)
        (self.work / "src" / "app.py").write_text("def login():\n    return True\n", encoding="utf-8")
        self.spec = self.work / "spec.md"
        self.spec.write_text("# Spec\n\n1. Users must log in.\n\n2. Admins must approve new accounts.\n",
                             encoding="utf-8")
        self.out = self.work / ".audit"
        home = self.tmp / "home"
        home.mkdir()
        self.cache = self.tmp / "cache" / "doctor.json"
        self.routing = self.tmp / "config" / "routing.json"
        self.telemetry = self.tmp / "cache" / "lanes.jsonl"
        self.env = dict(os.environ)
        self.env.pop("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", None)
        self.env.update({"HOME": str(home), "HA_ROUTING": str(self.routing), "HA_DOCTOR_CACHE": str(self.cache),
                         "HA_TELEMETRY": str(self.telemetry), "HA_OC_BIN": str(FAKE),
                         "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"})

    def tearDown(self):
        shutil.rmtree(str(self.tmp), ignore_errors=True)

    def cli(self, *args):
        return subprocess.run([sys.executable, str(AUDIT), "--cwd", str(self.work)] + list(args), env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")

    def write_json_file(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")

    def init(self, preset=None):
        args = ["init", "--spec", str(self.spec), "--cap", "3"]
        if preset:
            args += ["--preset", preset]
        r = self.cli(*args)
        self.assertEqual(r.returncode, 0, r.stdout)
        return r.stdout.splitlines()

    def opencode_line(self, lines):
        i = [k for k, line in enumerate(lines) if line.startswith("  repo map  :")][0]
        return lines[i + 1]

    def config(self):
        return json.loads((self.out / "config.json").read_text(encoding="utf-8"))

    def state(self):
        return json.loads((self.out / "state.json").read_text(encoding="utf-8"))

    def write_checklist(self, n):
        (self.out / "checklist.jsonl").write_text(
            "\n".join(json.dumps(r) for r in checklist_rows(n)) + "\n", encoding="utf-8")


class InitTests(CliBase):
    def test_opencode_line_follows_repo_map(self):
        self.write_json_file(self.cache, doctor_ok())
        lines = self.init()
        self.assertEqual(self.opencode_line(lines),
                         "opencode: v2.0.18 preset=hybrid investigator=oc:std verifier=claude parser=claude"
                         " (doctor 2026-09-28)")

    def test_down_tier_shows_reason(self):
        self.write_json_file(self.cache, doctor_ok(std_down=DOWN))
        line = self.opencode_line(self.init())
        self.assertIn("investigator=claude(down: unavailable)", line)

    def test_missing_cache_prints_unavailable(self):
        self.assertEqual(self.opencode_line(self.init()), UNAVAILABLE)

    def test_corrupt_cache_prints_unavailable(self):
        self.cache.parent.mkdir(parents=True, exist_ok=True)
        self.cache.write_text("{not json", encoding="utf-8")
        self.assertEqual(self.opencode_line(self.init()), UNAVAILABLE)

    def test_preset_and_routing_written_to_config(self):
        self.write_json_file(self.routing, {"oc_batch_max": 2})
        self.init("max")
        cfg = self.config()
        self.assertEqual(cfg["preset"], "max")
        self.assertEqual(cfg["routing"]["oc_batch_max"], 2)
        self.assertEqual(cfg["routing"]["tiers"]["std"]["max_parallel"], 6)
        self.assertEqual(cfg["routing"]["max_roles"]["verifier"], "std")


class PlanTests(CliBase):
    def hybrid_audit(self, preset=None, cache=True):
        if cache:
            self.write_json_file(self.cache, doctor_ok())
        self.write_json_file(self.routing, {"tiers": {"std": {"max_parallel": 2}}, "oc_batch_max": 2})
        self.init(preset)
        self.write_checklist(10)

    def plan(self):
        r = self.cli("plan", "--cap", "3")
        self.assertEqual(r.returncode, 0, r.stdout)
        return r.stdout.splitlines()

    def test_capacity_overflow_and_continuous_naming(self):
        self.hybrid_audit()
        lines = self.plan()
        self.assertEqual(lines[0], "plan: 10 requirements (0 skipped as static-limit/ambiguous) → 3 investigator"
                                   " batches of ≤2, 1 wave(s), cap=3 | 2 opencode batches (4 items)")
        batches = self.state()["batches"]
        self.assertEqual(sorted(batches), ["batch-%02d" % i for i in range(1, 6)])
        self.assertEqual([batches["batch-%02d" % i]["backend"] for i in range(1, 6)],
                         ["claude", "claude", "claude", "oc:std", "oc:std"])
        self.assertEqual(batches["batch-01"]["ids"], ["REQ-005", "REQ-006"])
        self.assertEqual(batches["batch-04"]["ids"], ["REQ-001", "REQ-002"])
        self.assertEqual(batches["batch-05"]["ids"], ["REQ-003", "REQ-004"])
        scripts_dir = self.config()["scripts_dir"]
        self.assertIn("OPENCODE 2 batches (4 items) | run each in the BACKGROUND (Bash run_in_background)"
                      " in the SAME message:", lines)
        self.assertIn('  batch-04 oc:std (2 items) → python3 "%s/audit.py" oc-run batch-04' % scripts_dir, lines)
        self.assertTrue(any(line.startswith("DISPATCH NOW") for line in lines))
        self.assertFalse(any("batch-04 → prompt" in line for line in lines))

    def test_opencode_batches_get_both_briefs(self):
        self.hybrid_audit()
        self.plan()
        bdir = self.out / "batches"
        body = (bdir / "batch-04.md").read_text(encoding="utf-8")
        self.assertEqual((bdir / "batch-04.oc.md").read_text(encoding="utf-8"),
                         ha_briefs.to_oc_brief(body, "batch-04"))
        self.assertTrue((bdir / "batch-01.md").exists())
        self.assertFalse((bdir / "batch-01.oc.md").exists())

    def test_preset_claude_keeps_original_plan(self):
        self.hybrid_audit(preset="claude")
        lines = self.plan()
        self.assertEqual(lines[0], "plan: 10 requirements (0 skipped as static-limit/ambiguous) → 3 investigator"
                                   " batches of ≤4, 1 wave(s), cap=3")
        self.assertFalse(any(line.startswith("OPENCODE") for line in lines))
        self.assertEqual({b["backend"] for b in self.state()["batches"].values()}, {"claude"})
        self.assertEqual(list((self.out / "batches").glob("*.oc.md")), [])

    def test_unavailable_doctor_plans_claude(self):
        self.hybrid_audit(cache=False)
        lines = self.plan()
        self.assertFalse(any(line.startswith("OPENCODE") for line in lines))
        self.assertEqual({b["backend"] for b in self.state()["batches"].values()}, {"claude"})


class ParseTests(CliBase):
    def parse_plan(self, preset):
        self.write_json_file(self.cache, doctor_ok())
        self.init(preset)
        r = self.cli("parse-plan", "--sections", "2")
        self.assertEqual(r.returncode, 0, r.stdout)
        return r.stdout.splitlines()

    def test_max_routes_parsers_to_opencode(self):
        lines = self.parse_plan("max")
        parse = self.state()["parse"]
        self.assertEqual(parse["backends"], {"section-01": "oc:std", "section-02": "oc:std"})
        pdir = self.out / "parse"
        body = (pdir / "section-01.md").read_text(encoding="utf-8")
        self.assertEqual((pdir / "section-01.oc.md").read_text(encoding="utf-8"),
                         ha_briefs.to_oc_brief(body, "section-01"))
        self.assertTrue(any(line.startswith("OPENCODE 2 sections") for line in lines))
        self.assertFalse(any(line.startswith("DISPATCH NOW") for line in lines))

    def test_hybrid_keeps_claude_parsers(self):
        lines = self.parse_plan("hybrid")
        self.assertEqual(self.state()["parse"]["backends"], {"section-01": "claude", "section-02": "claude"})
        self.assertTrue(any(line.startswith("DISPATCH NOW") for line in lines))
        self.assertFalse(any(line.startswith("OPENCODE") for line in lines))
        self.assertEqual(list((self.out / "parse").glob("*.oc.md")), [])

    def test_parse_merge_prints_fallback(self):
        self.parse_plan("max")
        pdir = self.out / "parse"
        row = {"id": "S02-001", "text": "Admins must approve new accounts.", "strength": "MUST",
               "category": "admin", "search_hints": ["approve"], "tags": []}
        (pdir / "section-02.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
        event = {"batch": "section-01", "ok": False, "agent_type": "opencode:ha-parser", "backend": "oc:std",
                 "reason": "format", "message": "no parsable block", "rounds": 3, "written": 0, "total": 0,
                 "t": 1.0}
        self.write_json_file(self.out / "events" / "section-01.json", event)
        r = self.cli("parse-merge")
        self.assertEqual(r.returncode, 0, r.stdout)
        lines = r.stdout.splitlines()
        i = lines.index("FALLBACK section-01 (format) → Claude parser")
        self.assertEqual(lines[i + 1], "  section-01 → prompt: Parser section-01: read %s and follow it exactly."
                         % (pdir / "section-01.md"))
        self.assertFalse((self.out / "events" / "section-01.json").exists())
        self.assertTrue((self.out / "oc" / "section-01.event.json").exists())
        state = self.state()
        self.assertEqual(state["fallbacks"], {"section-01": "format"})
        self.assertEqual(state["parse"]["backends"]["section-01"], "claude")
        again = self.cli("parse-merge").stdout
        self.assertNotIn("FALLBACK", again)

    def no_checklist_status(self):
        return ("STATUS: no checklist yet.\nNEXT: write %s (see SKILL.md Step 1), then `audit.py plan`.\n"
                % (self.out / "checklist.jsonl"))

    def test_status_after_opencode_parse_points_to_parse_merge(self):
        self.parse_plan("max")
        r = self.cli("status")
        self.assertEqual(r.returncode, 0, r.stdout)
        nxt = [line for line in r.stdout.splitlines() if line.startswith("NEXT:")]
        self.assertEqual(len(nxt), 1, r.stdout)
        self.assertIn("audit.py parse-merge", nxt[0])
        self.assertNotIn("audit.py parse-plan", r.stdout)
        self.assertNotIn("then `audit.py plan`", r.stdout)

    def test_status_after_claude_parse_unchanged(self):
        self.parse_plan("claude")
        self.assertEqual(self.state()["parse"]["backends"], {"section-01": "claude", "section-02": "claude"})
        r = self.cli("status")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout, self.no_checklist_status())

    def test_status_without_parse_state_unchanged(self):
        self.write_json_file(self.cache, doctor_ok())
        self.init("claude")
        r = self.cli("status")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout, self.no_checklist_status())


class CommandTests(CliBase):
    def test_oc_run_down_tier_prints_one_fallback_line(self):
        self.write_json_file(self.cache, doctor_ok())
        self.write_json_file(self.routing, {"tiers": {"std": {"max_parallel": 2}}, "oc_batch_max": 2})
        self.init()
        self.write_checklist(10)
        self.assertEqual(self.cli("plan", "--cap", "3").returncode, 0)
        self.write_json_file(self.cache, doctor_ok(std_down=DOWN))
        before = (self.out / "state.json").read_bytes()
        r = self.cli("oc-run", "batch-04")
        self.assertEqual(r.returncode, 0, r.stdout)
        lines = r.stdout.strip().splitlines()
        self.assertEqual(len(lines), 1, r.stdout)
        self.assertRegex(lines[0], r"^OC batch-04 oc:std FALLBACK \(down\) 0/2 — \d+ rounds — \d+s$")
        event = json.loads((self.out / "events" / "batch-04.json").read_text(encoding="utf-8"))
        self.assertEqual((event["ok"], event["reason"], event["backend"]), (False, "down", "oc:std"))
        self.assertEqual((self.out / "state.json").read_bytes(), before)

    def test_doctor_without_binary_writes_cache_and_user_routing(self):
        self.env["HA_OC_BIN"] = str(self.tmp / "no-such-opencode")
        r = self.cli("doctor")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertFalse(json.loads(self.cache.read_text(encoding="utf-8"))["ok"])
        defaults = json.loads((SCRIPTS.parent / "routing.default.json").read_text(encoding="utf-8"))
        self.assertEqual(json.loads(self.routing.read_text(encoding="utf-8")), defaults)
        self.assertIn(str(self.routing), r.stdout)
        self.assertIn(UNAVAILABLE, r.stdout.splitlines())
        self.assertFalse(self.out.exists())

    def test_stats_prints_stats_lines(self):
        record = {"t": 1.0, "kind": "run", "repo": str(self.work), "name": "batch-01", "role": "investigator",
                  "tier": "std", "model": "zai-coding-plan/glm-5.3", "variant": "high", "items": 4, "rounds": 1,
                  "round1_valid": 4, "oracle": {"foreign": 0, "dropped": 0, "demoted": 0, "invalid_status": 0},
                  "outcome": "ok", "reason": "", "duration_s": 12.5,
                  "tokens": {"input": 100, "output": 50, "reasoning": 0, "cache_read": 0, "cache_write": 0}}
        self.telemetry.parent.mkdir(parents=True, exist_ok=True)
        self.telemetry.write_text(json.dumps(record) + "\n", encoding="utf-8")
        records = ha_telemetry.load_records(self.telemetry)
        r = self.cli("stats")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(r.stdout.rstrip("\n"), "\n".join(ha_telemetry.stats_lines(records, "")).rstrip("\n"))
        r = self.cli("stats", "--repo", str(self.work))
        self.assertEqual(r.stdout.rstrip("\n"),
                         "\n".join(ha_telemetry.stats_lines(records, str(self.work))).rstrip("\n"))
        self.assertTrue(re.search(r"\S", r.stdout) or not ha_telemetry.stats_lines(records, str(self.work)))
