import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import devteam  # noqa: E402

ROUTING = {
    "preset": "hybrid",
    "tiers": {
        "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "max_parallel": 6},
        "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low", "max_parallel": 6},
    },
    "rows": {
        "code": "std",
        "refactor": "std",
        "test": "std",
        "chore": "std",
        "docs": "lite",
        "trivial": "lite",
    },
    "escalate_to": "claude",
    "max_escalations": 1,
}


def make_state(**extra):
    st = {"preset": "hybrid", "routing": json.loads(json.dumps(ROUTING)), "oc_ok": True}
    st.update(extra)
    return st


class TempHomeCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._old_home = os.environ.get("HOME")
        os.environ["HOME"] = str(self.tmp)

    def tearDown(self):
        if self._old_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._old_home
        shutil.rmtree(str(self.tmp), ignore_errors=True)


class SliceBackendTest(TempHomeCase):
    def test_explicit_claude_backend_wins(self):
        s = {"id": "S1", "kind": "refactor", "size": "small", "backend": "claude"}
        self.assertEqual(devteam.slice_backend(make_state(), s, "tdd"), "claude")

    def test_explicit_oc_backend_routes_to_tier(self):
        s = {"id": "S1", "kind": "refactor", "size": "small", "backend": "oc:std"}
        self.assertEqual(devteam.slice_backend(make_state(), s, "tdd"), "oc:std")

    def test_preset_claude_forces_claude(self):
        s = {"id": "S1", "kind": "refactor", "size": "small", "backend": "oc:std"}
        st = make_state(preset="claude")
        self.assertEqual(devteam.slice_backend(st, s, "tdd"), "claude")

    def test_opencode_unavailable_forces_claude(self):
        s = {"id": "S1", "kind": "refactor", "size": "small", "backend": "oc:std"}
        st = make_state(oc_ok=False)
        self.assertEqual(devteam.slice_backend(st, s, "tdd"), "claude")

    def test_research_mode_forces_claude(self):
        s = {"id": "S1", "kind": "refactor", "size": "small"}
        self.assertEqual(devteam.slice_backend(make_state(), s, "research"), "claude")

    def test_escalated_slice_stays_on_claude(self):
        s = {"id": "S1", "kind": "refactor", "size": "small", "backend": "oc:std"}
        st = make_state(escalations={"S1": 1})
        self.assertEqual(devteam.slice_backend(st, s, "tdd"), "claude")

    def test_red_phase_of_split_code_slice_is_claude(self):
        s = {"id": "S1", "kind": "code", "size": "small", "backend": "oc:std"}
        self.assertEqual(devteam.slice_backend(make_state(), s, "red"), "claude")

    def test_tier_the_doctor_did_not_clear_falls_back_to_claude_in_hybrid(self):
        s = {"id": "S1", "kind": "refactor", "size": "small", "backend": "oc:std"}
        st = make_state(oc_tiers={"std": False, "lite": True})
        self.assertEqual(devteam.slice_backend(st, s, "tdd"), "claude")

    def test_tier_the_doctor_did_not_clear_is_held_in_preset_opencode(self):
        s = {"id": "S1", "kind": "refactor", "size": "small", "backend": "oc:std"}
        st = make_state(preset="opencode", oc_tiers={"std": False, "lite": True})
        self.assertEqual(devteam.slice_backend(st, s, "tdd"), "held")

    def test_cleared_tier_keeps_its_lane(self):
        s = {"id": "S1", "kind": "refactor", "size": "small", "backend": "oc:std"}
        st = make_state(oc_tiers={"std": True, "lite": True})
        self.assertEqual(devteam.slice_backend(st, s, "tdd"), "oc:std")

    def test_legacy_max_state_reads_as_opencode(self):
        self.assertEqual(devteam.st_preset(make_state(preset="max")), "opencode")
        self.assertEqual(devteam.st_preset(make_state(preset="claude")), "claude")


class OcSlotsTest(TempHomeCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("HYBRID_OPENCODE_POOL", None)

    def test_default_cap_when_nothing_runs(self):
        self.assertEqual(devteam.oc_slots(make_state(), "std"), 6)   # tier cap 6, default pool 6

    def test_running_lanes_use_slots_of_their_tier_only(self):
        os.environ["HYBRID_OPENCODE_POOL"] = "8"
        st = make_state(oc_running={"S1": "std", "S2": "std", "S3": "lite"})
        self.assertEqual(devteam.oc_slots(st, "std"), 4)
        self.assertEqual(devteam.oc_slots(st, "lite"), 5)

    def test_pool_is_shared_across_tiers(self):
        st = make_state(oc_running={"S1": "std", "S2": "std", "S3": "std", "S4": "lite"})   # 4 of 6 used
        self.assertEqual(devteam.oc_slots(st, "std"), 2)
        self.assertEqual(devteam.oc_slots(st, "lite"), 2)

    def test_pool_env_resizes_the_pool(self):
        os.environ["HYBRID_OPENCODE_POOL"] = "3"
        st = make_state(oc_running={"S1": "lite"})
        self.assertEqual(devteam.oc_slots(st, "std"), 2)

    def test_invalid_pool_env_falls_back_to_default(self):
        os.environ["HYBRID_OPENCODE_POOL"] = "99"
        self.assertEqual(devteam.oc_slots(make_state(), "std"), 6)

    def test_extra_counts_lanes_picked_this_round(self):
        self.assertEqual(devteam.oc_slots(make_state(), "std", {"std": 2, "lite": 3}), 1)

    def test_live_cap_overrides_configured_cap(self):
        st = make_state(oc_caps={"std": 3}, oc_running={"S1": "std"})
        self.assertEqual(devteam.oc_slots(st, "std"), 2)

    def test_configured_cap_never_exceeds_eight(self):
        os.environ["HYBRID_OPENCODE_POOL"] = "8"
        st = make_state()
        st["routing"]["tiers"]["std"]["max_parallel"] = 40
        self.assertEqual(devteam.oc_slots(st, "std"), 8)

    def test_unknown_tier_has_no_slots(self):
        self.assertEqual(devteam.oc_slots(make_state(), "huge"), 0)

    def test_never_negative(self):
        running = dict(("S%d" % i, "std") for i in range(9))
        st = make_state(oc_running=running)
        self.assertEqual(devteam.oc_slots(st, "std"), 0)
        self.assertEqual(devteam.oc_slots(st, "lite"), 0)


class LaneLineTest(unittest.TestCase):
    def test_lane_line_format(self):
        expected = (
            "=== LANE S1 oc:std — run in the BACKGROUND: "
            "python3 {}/scripts/devteam.py lane S1".format(SCRIPTS.parent)
        )
        self.assertEqual(devteam.lane_line("S1", "oc:std"), expected)


def lane_record(sid, tier="std", outcome="blocked", reason="gate"):
    return {
        "id": sid,
        "backend": "oc:" + tier,
        "tier": tier,
        "model": "zai-coding-plan/glm-5.3",
        "variant": "high",
        "mode": "tdd",
        "outcome": outcome,
        "reason": reason,
        "escalated": False,
        "duration_s": 1.5,
        "tokens": {"input": 1, "output": 2, "reasoning": 0, "cache_read": 0, "cache_write": 0},
        "cost": 0.0,
        "runs": 1,
    }


class EscalateTest(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.root = self.tmp / "repo"
        self.state_dir = self.root / ".claude" / "hybrid-team"
        self.state_dir.mkdir(parents=True)
        self.lanes = self.state_dir / "lanes.jsonl"
        recs = [lane_record("S1", reason="stall"), lane_record("S2"), lane_record("S1", reason="gate")]
        self.lanes.write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")

    def read_lanes(self):
        return [json.loads(l) for l in self.lanes.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_first_escalation_marks_last_record_and_returns_escalate_line(self):
        st = make_state(oc_running={"S1": "std"})
        out = devteam.escalate(self.root, st, "S1", "gate", "gate blocked twice")
        self.assertEqual(out, "ESCALATE S1 oc:std -> claude (gate): gate blocked twice")
        recs = self.read_lanes()
        self.assertEqual([r["escalated"] for r in recs], [False, False, True])
        self.assertEqual(st["escalations"], {"S1": 1})
        self.assertEqual(st["escalation_notes"]["S1"], {"reason": "gate", "note": "gate blocked twice"})
        self.assertNotIn("S1", st["oc_running"])
        self.assertEqual(devteam.slice_backend(st, {"id": "S1", "kind": "refactor", "backend": "oc:std"}, "tdd"), "claude")

    def test_second_escalation_returns_blocked(self):
        st = make_state()
        devteam.escalate(self.root, st, "S1", "gate", "first")
        out = devteam.escalate(self.root, st, "S1", "crash", "second")
        self.assertEqual(out, "BLOCKED S1: max escalations reached (crash): second")
        self.assertEqual(st["escalations"], {"S1": 1})

    def test_throttle_halves_live_cap_of_tier(self):
        st = make_state(oc_running={"S1": "std"})
        devteam.escalate(self.root, st, "S1", "throttle", "HTTP 429")
        self.assertEqual(st["oc_caps"], {"std": 3})
        self.assertEqual(devteam.oc_slots(st, "std"), 3)
        st["escalations"] = {}
        devteam.escalate(self.root, st, "S2", "throttle", "HTTP 429")
        self.assertEqual(st["oc_caps"], {"std": 1})

    def test_tier_falls_back_to_lane_record(self):
        st = make_state()
        out = devteam.escalate(self.root, st, "S2", "spawn", "opencode not found")
        self.assertEqual(out, "ESCALATE S2 oc:std -> claude (spawn): opencode not found")

    def test_missing_lanes_file_still_escalates(self):
        self.lanes.unlink()
        st = make_state()
        out = devteam.escalate(self.root, st, "S9", "crash", "boom")
        self.assertEqual(out, "ESCALATE S9 oc -> claude (crash): boom")
        self.assertFalse(self.lanes.exists())

    def test_removes_oc_worktree_and_branch(self):
        git = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]
        subprocess.run(git + ["init", "-q"], cwd=str(self.root), check=True)
        (self.root / "a.txt").write_text("a\n", encoding="utf-8")
        subprocess.run(git + ["add", "a.txt"], cwd=str(self.root), check=True)
        subprocess.run(git + ["commit", "-q", "-m", "init"], cwd=str(self.root), check=True)
        wt = self.root / ".claude" / "worktrees" / "hybrid-oc-S1"
        subprocess.run(git + ["worktree", "add", "-q", "-b", "hybrid-oc-S1", str(wt)], cwd=str(self.root), check=True)
        st = make_state(oc_running={"S1": "std"})
        devteam.escalate(self.root, st, "S1", "stall", "no events for 300s")
        self.assertFalse(wt.exists())
        branches = subprocess.run(
            ["git", "branch", "--list", "hybrid-oc-S1"], cwd=str(self.root),
            stdout=subprocess.PIPE, universal_newlines=True, check=True,
        ).stdout
        self.assertEqual(branches.strip(), "")


TIER = {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low"}


class LaneOcTest(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.root = self.tmp / "repo"
        self.errors = self.root / ".claude" / "hybrid-team" / "oc-errors.jsonl"

    def test_prints_logs_and_trips_breaker_on_non_retryable_kind(self):
        spec = devteam.hybrid_shared.model_spec(TIER)
        with mock.patch.object(devteam.hybrid_shared, "breaker_trip") as trip, \
                mock.patch("sys.stdout", new_callable=io.StringIO) as buf:
            line = devteam.lane_oc(self.root, "OC-ERROR", "S1", "lite", TIER, "auth",
                                   "invalid api key", "/x/S1.err")
        self.assertTrue(line.startswith(
            "OC-ERROR hybrid-team S1 tier=lite model=%s kind=auth :: invalid api key" % spec), line)
        self.assertIn("log=/x/S1.err", line)
        self.assertEqual(buf.getvalue().strip(), line)
        self.assertIn("invalid api key", self.errors.read_text())
        trip.assert_called_once_with(self.root / ".claude" / "hybrid-team", "lite", spec, "auth",
                                     "invalid api key")

    def test_gate_warning_does_not_trip_breaker(self):
        with mock.patch.object(devteam.hybrid_shared, "breaker_trip") as trip, \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            line = devteam.lane_oc(self.root, "OC-WARN", "S1", "lite", TIER, "gate", "nothing committed")
        self.assertTrue(line.startswith("OC-WARN hybrid-team S1 tier=lite"), line)
        self.assertIn("kind=gate", line)
        trip.assert_not_called()


class LaneLoopTest(TempHomeCase):
    def setUp(self):
        super().setUp()
        self.root = self.tmp / "repo"
        patcher = mock.patch.dict(os.environ, {"HYBRID_OC_RETRY_DELAY_S": "0"})   # a connection failure retries
        patcher.start()
        self.addCleanup(patcher.stop)

    def loop(self, res):
        texts = []

        def gate(wt, text):
            texts.append(text)
            devteam.write_atomic(devteam.marker_file(self.root, "S1", "done"), "{}")
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        with mock.patch.object(devteam, "run_lane_process", return_value=res), \
                mock.patch.object(devteam, "run_stop_gate", side_effect=gate), \
                mock.patch("sys.stdout", new_callable=io.StringIO):
            agg = devteam.lane_loop(self.root, "S1", self.root, TIER, "opencode", {}, "go", 60, 600)
        return agg, texts

    def test_exit_1_after_finished_step_is_recovered_when_gate_passes(self):
        agg, texts = self.loop({"rc": 1, "finished": True, "reason": "crash", "note": "exit 1",
                                "text": "## Status: Done", "session": "ses_1", "usage": {}})
        self.assertEqual(agg["outcome"], "done")
        self.assertTrue(agg["recovered"])
        self.assertEqual(texts, ["## Status: Done"])

    def test_exit_1_without_finished_step_stays_a_failure(self):
        agg, texts = self.loop({"rc": 1, "finished": False, "reason": "crash", "note": "exit 1",
                                "text": "partial", "session": "ses_1", "usage": {}})
        self.assertEqual((agg["outcome"], agg["reason"]), ("blocked", "crash"))
        self.assertEqual(texts, [])

    def test_no_text_is_empty(self):
        agg, texts = self.loop({"rc": 0, "finished": True, "reason": "", "note": "",
                                "text": "  ", "session": "ses_1", "usage": {}})
        self.assertEqual((agg["outcome"], agg["reason"]), ("blocked", "empty"))
        self.assertEqual(texts, [])

    def test_failure_kind_replaces_the_generic_crash_reason(self):
        agg, texts = self.loop({"rc": 1, "finished": False, "reason": "crash", "kind": "auth",
                                "note": "ProviderAuthError: invalid api key", "text": "",
                                "session": "ses_1", "usage": {}})
        self.assertEqual((agg["outcome"], agg["reason"]), ("blocked", "auth"))
        self.assertEqual(texts, [])


if __name__ == "__main__":
    unittest.main()
