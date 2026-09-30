"""Regression tests for the hybrid fix run: doctor pings and plan routing, retry re-ping, no silent
routing to Claude, the Step 0 preload, lane exit codes and lines, and the plan re-check at integrate.
Driven through `devteam.py` subprocesses and the fake opencode CLI; every path is a temp dir."""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from test_dispatch_flow import (DONE_STEP, FAKE, MODELS_ENV, FlowBase, chore_slice, code_slice,  # noqa: E402
                                docs_slice, git, inproc, plan_of)

import devteam  # noqa: E402
import oc_doctor  # noqa: E402
import router  # noqa: E402

LITE = "zai-coding-plan/glm-5.3-flash#low"
PING_OK = {"text": "HT-AGENT-OK", "finish": "stop"}
THROTTLE = {"scenario": "throttle"}


class Base(FlowBase):
    def step(self, data):
        self.script.write_text(json.dumps(data))
        Path(str(self.script) + ".calls").unlink(missing_ok=True)

    def fake_calls(self, cmd):
        log = self.tmp / "fake_log.jsonl"
        recs = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()] if log.exists() else []
        return [r["argv"] for r in recs if r["argv"][:1] == [cmd]]

    def write_status(self, **tiers):
        """Doctor cache with one entry per tier: name=(ok, age_s[, kind])."""
        shared = devteam.hybrid_shared.load_shared(MODELS_ENV)[0]
        entries = {}
        for name, spec in tiers.items():
            ok, age = spec[0], spec[1]
            entries[name] = {"ok": ok, "key": devteam.hybrid_shared.cache_key(shared[name]),
                             "checked_at": time.time() - age, "kind": "" if ok else (spec[2:] or ("auth",))[0],
                             "detail": "" if ok else "401 unauthorized"}
        self.state_dir.mkdir(parents=True, exist_ok=True)
        (self.state_dir / "oc_status.json").write_text(
            json.dumps({"available": any(e["ok"] for e in entries.values()), "issues": [], "tiers": entries}))

    def status(self):
        return json.loads((self.state_dir / "oc_status.json").read_text())


class DoctorPingTest(Base):
    """Item 3: a fresh failed entry must never block the ping that would clear it."""

    def doctor(self, ping):
        calls = []

        def fake_ping(binary, tier, prompt_text, engine, workdir):
            calls.append(tier.get("variant"))
            return (True, {"kind": "", "message": ""})

        with inproc(self), mock.patch.object(devteam, "check_opencode", return_value=[]), \
                mock.patch.object(devteam, "ping_tier", side_effect=fake_ping), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            devteam.cmd_doctor(argparse.Namespace(root=str(self.repo), ping=ping, routing=None, fix=False))
        return sorted(calls)

    def test_ping_repings_tiers_whose_fresh_entry_failed_and_overwrites_it(self):
        self.write_status(std=(False, 5), lite=(False, 5))
        self.assertEqual(self.doctor(True), ["high", "low"])
        st = self.status()
        self.assertTrue(st["available"])
        self.assertEqual([st["tiers"][n]["ok"] for n in ("std", "lite")], [True, True])

    def test_stale_mode_repings_only_the_failed_tier(self):
        self.write_status(std=(True, 5), lite=(False, 5))
        self.assertEqual(self.doctor("stale"), ["low"])
        self.assertTrue(self.status()["tiers"]["lite"]["ok"])

    def test_tier_without_a_model_has_one_config_issue_and_no_model_issue(self):
        checks = oc_doctor.check_opencode(str(FAKE), {"tiers": {"std": {"variant": "high"}}, "rows": {}})
        bad = [c for c in checks if not c["ok"]]
        self.assertEqual([(c["name"], c["kind"]) for c in bad], [("tier:std", "config")])

    def test_models_listing_never_uses_standalone(self):
        with mock.patch.dict(os.environ, {"HT_FAKE_LOG": str(self.tmp / "fake_log.jsonl")}):
            os.environ.pop("HT_FAKE_SCRIPT", None)
            oc_doctor.check_opencode(str(FAKE), {"tiers": {}, "rows": {}})
        # `models --standalone` always lists nothing on opencode v2.0.20
        self.assertEqual(self.fake_calls("models")[0], ["models"])


class PlanRoutingDoctorTest(Base):
    """Item 4: the doctor and the ping run on the effective routing, plan block included."""
    PLAN_ROUTING = {"tiers": {"lite": {"model": "zai-coding-plan/glm-5.3", "variant": "max"}}}

    def test_start_pings_the_plan_level_model_and_the_tier_stays_on_opencode(self):
        self.step(PING_OK)
        path = self.tmp / "plan.json"
        path.write_text(json.dumps(plan_of(docs_slice("D1"), routing=self.PLAN_ROUTING)))
        r = self.engine("start", str(path))
        self.assertIn("=== LANE D1 oc:lite", r.stdout)
        self.assertNotIn("=== DISPATCH D1", r.stdout)
        self.assertEqual(self.status()["tiers"]["lite"]["key"], "zai-coding-plan/glm-5.3#max")
        self.assertIn("zai-coding-plan/glm-5.3#max", [a[a.index("--model") + 1] for a in self.fake_calls("run")])
        self.assertIs(self.st()["oc_tiers"]["lite"], True)

    def test_doctor_inside_a_run_checks_the_plan_level_model(self):
        self.init(plan_of(docs_slice("D1"), routing=self.PLAN_ROUTING))
        self.step(PING_OK)
        self.engine("doctor", "--ping")
        self.assertEqual(self.status()["tiers"]["lite"]["key"], "zai-coding-plan/glm-5.3#max")


class RetryRepingTest(Base):
    """Item 2: `retry <id>` after a hold re-pings the tier, clears its breaker and refreshes oc_ok."""

    def held(self):
        self.init(plan_of(docs_slice("D1")), "--route", "opencode")
        self.assertTrue(devteam.hybrid_shared.breaker_trip(self.state_dir, "lite", LITE, "auth", "invalid api key"))
        r = self.engine("dispatch", "D1")
        self.assertIn("HELD D1 (auth)", r.stdout)
        return r.stdout

    def test_held_line_names_the_tier_model_and_root_cause(self):
        out = self.held()
        self.assertIn("OC-ERROR hybrid-team D1 tier=lite model=%s kind=auth :: breaker open after kind=auth" % LITE, out)

    def test_retry_after_breaker_hold_pings_and_goes_back_to_opencode(self):
        self.held()
        self.step(PING_OK)
        r = self.engine("retry", "D1")
        self.assertIn("ping lite: OK", r.stdout)
        self.assertEqual(devteam.hybrid_shared.breaker_open(self.state_dir, "lite", LITE), {})
        self.assertIn("=== LANE D1 oc:lite", self.engine("dispatch", "D1").stdout)

    def test_retry_with_a_failed_ping_reports_it_and_holds_again(self):
        self.held()
        self.step({"scenario": "auth"})
        r = self.engine("retry", "D1")
        self.assertIn("OC-ERROR hybrid-team doctor tier=lite", r.stdout)
        self.assertIn("kind=auth", r.stdout)
        self.assertTrue(devteam.hybrid_shared.breaker_open(self.state_dir, "lite", LITE))
        self.assertIn("HELD D1", self.engine("dispatch", "D1").stdout)

    def test_retry_refreshes_oc_ok_frozen_false_at_init(self):
        self.env["HT_OC_BIN"] = str(self.tmp / "no-such-opencode")
        r = self.init(plan_of(docs_slice("D1")), "--route", "opencode")
        self.assertIn("kind=spawn :: opencode binary not found", r.stdout)
        self.assertIs(self.st()["oc_ok"], False)
        self.assertIn("HELD D1", self.engine("dispatch", "D1").stdout)
        self.env["HT_OC_BIN"] = str(FAKE)
        self.step(PING_OK)
        self.engine("retry", "D1")
        self.assertIs(self.st()["oc_ok"], True)
        self.assertIn("=== LANE D1 oc:lite", self.engine("dispatch", "D1").stdout)


class NoSilentClaudeTest(Base):
    """Item 6: a tier the doctor did not clear prints an OC line when its slices go to Claude."""

    def test_stale_entry_at_init_warns_once_per_tier_in_hybrid(self):
        self.write_status(std=(True, 5), lite=(True, devteam.hybrid_shared.DOCTOR_TTL_S + 60))
        self.init(plan_of(docs_slice("D1"), docs_slice("D2")))
        r = self.engine("dispatch", "D1")
        self.assertIn("=== DISPATCH D1", r.stdout)
        self.assertIn("OC-WARN hybrid-team D1 tier=lite model=%s kind=config :: no fresh doctor result" % LITE, r.stdout)
        r2 = self.engine("dispatch", "D2")
        self.assertIn("=== DISPATCH D2", r2.stdout)
        self.assertNotIn("OC-WARN", r2.stdout)

    def test_missing_binary_is_reported_at_init_in_hybrid(self):
        self.env["HT_OC_BIN"] = str(self.tmp / "no-such-opencode")
        r = self.init(plan_of(docs_slice("D1")))
        self.assertIn("OC-ERROR hybrid-team init", r.stdout)
        self.assertIn("kind=spawn", r.stdout)

    def test_old_unavailable_flag_in_the_cache_does_not_disable_a_new_run(self):
        self.state_dir.mkdir(parents=True)
        (self.state_dir / "oc_status.json").write_text(json.dumps({"available": False, "issues": []}))
        self.init(plan_of(docs_slice("D1")))
        self.assertIs(self.st()["oc_ok"], True)


class PreloadTest(Base):
    """Item 5: `router.py config` prints each tier's spec with its source and always exits 0."""

    def run_config(self):
        r = subprocess.run([sys.executable, str(SCRIPTS / "router.py"), "config"], env=self.env, text=True,
                           capture_output=True, cwd=str(self.tmp), timeout=60)
        self.assertEqual(r.returncode, 0, msg=r.stderr)
        return r.stdout

    def test_prints_specs_with_skill_and_shared_marks(self):
        self.set_routing({"tiers": {"std": {"model": "acme/big", "variant": "high"}}})
        out = self.run_config()
        self.assertIn("config: std=acme/big#high (skill) lite=%s (shared)" % LITE, out)
        self.assertIn("opencode config ok", out)

    def test_no_config_and_broken_file_still_exit_zero(self):
        self.env.pop("HYBRID_OPENCODE_STD")
        self.env.pop("HYBRID_OPENCODE_LITE")
        self.assertIn("config: std=no config lite=no config", self.run_config())
        self.routing.write_text("{not json")
        self.assertIn("config:", self.run_config())

    def test_skill_pins_the_preload_command(self):
        text = (SCRIPTS.parent / "SKILL.md").read_text()
        cmd = "python3 ${CLAUDE_SKILL_DIR}/scripts/router.py config"
        self.assertIn("!`%s`" % cmd, text)
        self.assertIn("Bash(%s)" % cmd, text)
        desc = text.split("description: >-")[1].split("allowed-tools:")[0]
        self.assertLessEqual(len(" ".join(desc.split())), 1024)


class LaneMinorTest(Base):
    """Item 7: exit code, throttle cap in preset opencode, breaker summary once, quoting, notes."""

    def lane_run(self, sid):
        return self.engine("lane", sid, check=False)

    def test_failed_lane_exits_non_zero_and_a_done_lane_exits_zero(self):
        self.init(plan_of(docs_slice("D1")))
        self.engine("dispatch", "D1")
        self.step({"scenario": "auth"})
        self.assertEqual(self.lane_run("D1").returncode, 1)
        self.init(plan_of(docs_slice("D1")), "--force")
        self.engine("dispatch", "D1")
        self.step(DONE_STEP)
        self.assertEqual(self.lane_run("D1").returncode, 0)

    def test_throttle_hold_in_preset_opencode_halves_the_tier_cap(self):
        self.init(plan_of(chore_slice("H1")), "--route", "opencode")
        self.engine("dispatch", "H1")
        self.step(THROTTLE)
        self.lane_run("H1")
        self.assertIn("HELD H1 (throttle)", self.engine("next", "--no-review").stdout)
        self.assertEqual(self.st()["oc_caps"], {"std": 3})

    def test_breaker_summary_is_printed_once(self):
        self.init(plan_of(docs_slice("D1")))
        self.assertTrue(devteam.hybrid_shared.breaker_trip(self.state_dir, "lite", LITE, "auth", "invalid api key"))
        self.engine("dispatch", "D1")
        st = self.st()
        st["slices"]["D1"].update(status="done", merged_sha=git(["rev-parse", "HEAD"], self.repo))
        self.save_st(st)
        self.assertIn("kind=breaker", self.engine("next", "--no-review").stdout)
        self.assertNotIn("kind=breaker", self.engine("next", "--no-review").stdout)
        self.assertEqual((self.state_dir / "oc-errors.jsonl").read_text().count("kind=breaker"), 1)

    def test_lane_line_quotes_a_skill_path_with_a_space(self):
        with mock.patch.object(devteam, "SKILL_DIR", Path("/x/my skills/hybrid-team")):
            self.assertIn("python3 '/x/my skills/hybrid-team/scripts/devteam.py' lane S1",
                          devteam.lane_line("S1", "oc:std"))

    def test_stall_retry_warn_names_the_stall_not_the_exit_code(self):
        self.set_routing({"tiers": {"lite": {"stall_s": 1}}})
        self.init(plan_of(docs_slice("D1")))
        self.engine("dispatch", "D1")
        self.step([{"sleep": 8, "ticks": 0}, DONE_STEP])
        out = self.lane_run("D1").stdout
        self.assertIn("kind=stall :: retry 1/3 in 0s: stall: no event for 1s", out)
        self.assertNotIn("exit -", out)

    def test_recovered_warning_is_not_carried_over_a_clean_continuation(self):
        self.init(plan_of(docs_slice("D1")))
        self.engine("dispatch", "D1")
        lazy = {"text": "## Slice: D1\n## Status: Done\n## Notes:\nall good\n", "finish": "stop", "exit": 1}
        self.step([lazy, DONE_STEP])
        r = self.lane_run("D1")
        self.assertIn("LANE D1 DONE", r.stdout)
        self.assertNotIn("kind=recovered", r.stdout)


class PlanDriftTest(Base):
    """Item 8: integrate re-validates footprint, kind and mode against the plan's JSON block."""

    def lane_done(self):
        self.init(plan_of(docs_slice("D1")))
        self.engine("dispatch", "D1")
        self.step(DONE_STEP)
        self.engine("lane", "D1")

    def tamper(self, **change):
        st = self.st()
        st["slices"]["D1"].update(change)
        self.save_st(st)

    def test_widened_footprint_in_state_is_rejected_and_restored(self):
        self.lane_done()
        self.tamper(files=["docs/d1.md", "src/"])
        r = self.engine("integrate", "D1")
        self.assertIn("D1: REJECTED — the run state no longer matches the plan", r.stdout)
        self.assertIn("src/", r.stdout)
        self.assertNotIn("MERGED", r.stdout)
        self.assertEqual(self.st()["slices"]["D1"]["files"], ["docs/d1.md"])

    def test_changed_kind_or_mode_is_rejected(self):
        self.lane_done()
        self.tamper(kind="research", mode="research")
        r = self.engine("integrate", "D1")
        self.assertIn("kind is research, the plan says docs", r.stdout)
        self.assertNotIn("RESEARCH RECORDED", r.stdout)
        self.assertEqual(self.st()["slices"]["D1"]["kind"], "docs")

    def test_untouched_state_and_retry_files_widening_pass(self):
        self.lane_done()
        self.assertIn("D1: MERGED", self.engine("integrate", "D1").stdout)
        self.init(plan_of(code_slice("C1")), "--force")
        st = self.st()
        s = st["slices"]["C1"]
        s.update(mode="slice", files=s["files"] + ["src/extra.py"])
        s["history"].append({"event": "retry", "files": s["files"]})
        self.assertEqual(devteam.plan_drift(self.repo, st, s), [])
        s["mode"] = "fast"          # balanced profile: a code slice never runs untested
        self.assertIn("mode is fast", devteam.plan_drift(self.repo, st, s)[0])


class ResyncTest(Base):
    """Item 1: behaviour taken over from dev-team since the fork."""

    def test_init_force_wipes_stale_review_reports(self):
        self.init(plan_of(docs_slice("D1")))
        for sub in ("reviews", "logs", "research"):
            (self.state_dir / sub / "r1.report.md").write_text("VERDICT: APPROVED\n")
        self.init(plan_of(docs_slice("D1")), "--force")
        for sub in ("reviews", "logs", "research"):
            self.assertEqual(list((self.state_dir / sub).iterdir()), [])

    def test_hook_probe_order_covers_the_versioned_folder(self):
        cands = [str(c) for c in devteam.hooks_resolve_candidates(Path("/r"))]
        self.assertEqual(cands[:2], ["/r/.claude/skills/hybrid-team/scripts/guard.py",
                                     "/r/.claude/skills/hybrid-team-v1.0/scripts/guard.py"])
        self.assertEqual(len(cands), 4)

    def test_never_removes_the_integration_checkout_as_a_worktree(self):
        devteam.remove_worktree(self.repo, str(self.repo))
        self.assertTrue((self.repo / "README.md").exists())

    def test_finish_salvages_uncommitted_lane_work_before_sweeping_oc_worktrees(self):
        self.init(plan_of(docs_slice("D1")))
        self.engine("dispatch", "D1")
        self.step({"write": {"docs/d1.md": "# wip\n"}, "text": "## Slice: D1\n## Status: Blocked\n## Notes:\nstuck\n"})
        self.engine("lane", "D1", check=False)
        r = self.engine("finish", "--force")
        self.assertIn("wip(D1): salvage", r.stdout)
        self.assertIn("attempt/D1-1", git(["branch", "--list", "attempt/*"], self.repo))
        self.assertFalse((self.repo / ".claude" / "worktrees" / "oc-D1").exists())

    def test_plan_tier_overlay_never_writes_into_the_user_routing(self):
        self.set_routing({"tiers": {"std": {"model": "acme/big", "variant": "high", "max_parallel": 2}}})
        seen = {}
        real = router._read_user_routing

        def spy(path, problems):
            seen["user"] = real(path, problems)
            return seen["user"]

        with mock.patch.dict(os.environ, dict(MODELS_ENV, HT_ROUTING=str(self.routing))), \
                mock.patch.object(router, "_read_user_routing", side_effect=spy):
            routing = router.load_routing(SCRIPTS.parent / "routing.default.json", self.routing,
                                          {"tiers": {"std": {"model": "plan/model"}}})
        self.assertEqual(routing["tiers"]["std"]["model"], "plan/model")
        self.assertEqual(seen["user"]["tiers"]["std"]["model"], "acme/big")


if __name__ == "__main__":
    unittest.main()
