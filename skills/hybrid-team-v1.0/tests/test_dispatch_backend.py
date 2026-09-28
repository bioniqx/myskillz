import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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


class OcSlotsTest(TempHomeCase):
    def test_default_cap_when_nothing_runs(self):
        self.assertEqual(devteam.oc_slots(make_state(), "std"), 6)

    def test_running_lanes_use_slots_of_their_tier_only(self):
        st = make_state(oc_running={"S1": "std", "S2": "std", "S3": "lite"})
        self.assertEqual(devteam.oc_slots(st, "std"), 4)
        self.assertEqual(devteam.oc_slots(st, "lite"), 5)

    def test_live_cap_overrides_configured_cap(self):
        st = make_state(oc_caps={"std": 3}, oc_running={"S1": "std"})
        self.assertEqual(devteam.oc_slots(st, "std"), 2)

    def test_unknown_tier_has_no_slots(self):
        self.assertEqual(devteam.oc_slots(make_state(), "huge"), 0)

    def test_never_negative(self):
        running = dict(("S%d" % i, "std") for i in range(9))
        st = make_state(oc_running=running)
        self.assertEqual(devteam.oc_slots(st, "std"), 0)


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
        wt = self.root / ".claude" / "worktrees" / "oc-S1"
        subprocess.run(git + ["worktree", "add", "-q", "-b", "oc-S1", str(wt)], cwd=str(self.root), check=True)
        st = make_state(oc_running={"S1": "std"})
        devteam.escalate(self.root, st, "S1", "stall", "no events for 300s")
        self.assertFalse(wt.exists())
        branches = subprocess.run(
            ["git", "branch", "--list", "oc-S1"], cwd=str(self.root),
            stdout=subprocess.PIPE, universal_newlines=True, check=True,
        ).stdout
        self.assertEqual(branches.strip(), "")


if __name__ == "__main__":
    unittest.main()
