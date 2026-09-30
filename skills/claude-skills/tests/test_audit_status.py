"""Black-box tests for audit.py's `status`/`queue`/`adjudicate` state machine.

Covers K09 (spec W5-1, W5-2):
  - the adjudication queue's deterministic spot-check sample is a fixed function
    of the item set (adjudicating an item never reshuffles the rest of the sample)
  - repeated `adjudicate --accept-queue` drains the queue to empty
  - after a partial SubagentStop, `status`'s NEXT names the redispatch command;
    after `--redispatch` a stale events file no longer flags the batch as stuck;
    a failing retry (batch-NN-rNNN) counts toward its base batch batch-NN
  - `--undispatch`, `--redispatch` and `--failed` work for verifier batches (batch-VNN);
    a failed verifier batch's ids leave verify_assigned and reappear for verification
  - solo mode re-lists undispatched verifier batches on every status
  - whenever nothing is running, NEXT is a concrete command, never
    "wait for completion notifications"

All fixtures live under the SYSTEM temp dir (never inside this repo/worktree) so
guard.py/devteam.py's parent-dir walk for .slice/ / .claude/dev-team never sees them.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "requirements-code-audit" / "scripts" / "audit.py"
assert SCRIPT.exists(), SCRIPT


def run(args, cwd, timeout=30):
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["HOME"] = str(cwd)  # never let the script touch the real HOME
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--cwd", str(cwd)] + args,
        cwd=str(cwd), capture_output=True, text=True, timeout=timeout, env=env,
    )


def checklist_row(i, **overrides):
    row = {
        "id": "REQ-%03d" % i, "text": "Requirement %d text" % i, "strength": "MUST",
        "category": "core", "stakes": "normal", "evidence_expected": "",
        "search_hints": ["term%d" % i], "tags": [], "source": "", "question": "",
    }
    row.update(overrides)
    return row


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""), encoding="utf-8")


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def finding(rid, status="MATCHED", confidence="high"):
    return {"id": rid, "status": status, "confidence": confidence,
            "evidence": [{"path": "src/x.py", "lines": "1-2", "note": "ok"}],
            "searched": ["term"], "notes": ""}


class AuditStatusTestCase(unittest.TestCase):
    def setUp(self):
        self.cwd = Path(os.path.realpath(tempfile.mkdtemp(prefix="audit_status_")))
        self.addCleanup(shutil.rmtree, str(self.cwd), True)
        (self.cwd / "spec.md").write_text("The system MUST do things.\n", encoding="utf-8")
        self.out = self.cwd / ".audit"

    def init_audit(self, agents="generic", cap=20):
        r = run(["init", "--spec", "spec.md", "--agents", agents, "--cap", str(cap)], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def set_state(self, **updates):
        state = read_json(self.out / "state.json")
        state.update(updates)
        write_json(self.out / "state.json", state)
        return state

    # ---------------------------------------------------------------- criterion 1

    def test_spotcheck_sample_deterministic_across_adjudication(self):
        """600-item fixture: adjudicating a sampled item must not change which
        other items get spot-checked (the sample is a fixed function of the set)."""
        self.init_audit()
        n = 600
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, n + 1)])
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding("REQ-%03d" % i) for i in range(1, n + 1)])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])

        r1 = run(["queue"], self.cwd)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        sample0 = sorted(rid for rid, why in re.findall(r"^(REQ-\d+) \[[^\]]*\] — (.*)$", r1.stdout, re.M)
                          if "spot-check sample" in why)
        self.assertEqual(len(sample0), 30, r1.stdout)  # max(3, ceil(0.05*600))

        decided = sample0[0]
        r2 = run(["adjudicate", "--set", decided, "MATCHED", "--note", "spot-checked ok"], self.cwd)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)

        r3 = run(["queue"], self.cwd)
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
        sample1 = sorted(rid for rid, why in re.findall(r"^(REQ-\d+) \[[^\]]*\] — (.*)$", r3.stdout, re.M)
                          if "spot-check sample" in why)

        self.assertEqual(
            sample1, [rid for rid in sample0 if rid != decided],
            "adjudicating one sampled item reshuffled the rest of the spot-check sample",
        )

    def test_accept_queue_drains_to_empty(self):
        self.init_audit()
        n = 30
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, n + 1)])
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding("REQ-%03d" % i) for i in range(1, n + 1)])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])

        for _ in range(20):
            r = run(["queue"], self.cwd)
            if "Adjudication queue is empty" in r.stdout:
                break
            ra = run(["adjudicate", "--accept-queue"], self.cwd)
            self.assertEqual(ra.returncode, 0, ra.stdout + ra.stderr)
        else:
            self.fail("repeated `adjudicate --accept-queue` never drained the queue to empty")

    # ---------------------------------------------------------------- criterion 2

    def test_partial_subagentstop_redispatch_and_stale_events(self):
        self.init_audit(agents="generic", cap=2)
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, 7)])
        rp = run(["plan"], self.cwd)
        self.assertEqual(rp.returncode, 0, rp.stdout + rp.stderr)
        state = read_json(self.out / "state.json")
        self.assertIn("batch-01", state["batches"])
        self.assertIn("batch-02", state["batches"])
        ids1 = state["batches"]["batch-01"]["ids"]

        # batch-02 fully covered; batch-01 partial (2 of 3), agent reported done anyway
        write_jsonl(self.out / "findings" / "batch-02.jsonl",
                    [finding(rid) for rid in state["batches"]["batch-02"]["ids"]])
        write_jsonl(self.out / "findings" / "batch-01.jsonl", [finding(ids1[0]), finding(ids1[1])])
        write_json(self.out / "events" / "batch-01.json", {"batch": "batch-01", "ok": True, "msg": "done: 2/3 written"})

        r1 = run(["status"], self.cwd)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        self.assertIn("NOTE: agents finished without complete output: batch-01", r1.stdout)
        self.assertIn("--redispatch batch-01", r1.stdout, "NEXT must name the redispatch command")

        r2 = run(["status", "--redispatch", "batch-01"], self.cwd)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        m = re.search(r"\b(batch-01-r\d+)\b", r2.stdout)
        self.assertIsNotNone(m, "redispatch did not produce a retry batch: %s" % r2.stdout)
        retry_name = m.group(1)

        r3 = run(["status"], self.cwd)
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
        self.assertNotIn(
            "NOTE: agents finished without complete output: batch-01", r3.stdout,
            "a stale events file (older than the fresh redispatch) still flags the batch as stuck",
        )

        # the stale original event no longer matters; now the RETRY itself fails
        (self.out / "events" / "batch-01.json").unlink()
        write_json(self.out / "events" / (retry_name + ".json"), {"batch": retry_name, "ok": False, "msg": "retry stopped early"})

        r4 = run(["status"], self.cwd)
        self.assertEqual(r4.returncode, 0, r4.stdout + r4.stderr)
        self.assertIn(
            "FAILED/partial: batch-01", r4.stdout,
            "a failing retry event (batch-01-rNNN) must count toward its base batch batch-01",
        )

    # ---------------------------------------------------------------- criterion 3

    def test_verifier_batch_undispatch_redispatch_failed(self):
        self.init_audit(agents="generic")
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1), checklist_row(2)])
        t0 = time.time() - 1000
        self.set_state(
            plan_time=time.time(), batches={}, verify={"batch-V01": {"ids": ["REQ-001", "REQ-002"], "dispatched": t0}},
            verify_assigned={"REQ-001": "batch-V01", "REQ-002": "batch-V01"},
            spotchecked=[], hedges={}, failed=[],
        )

        with self.subTest("undispatch"):
            r = run(["status", "--undispatch", "batch-V01"], self.cwd)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            state = read_json(self.out / "state.json")
            self.assertIsNone(state["verify"]["batch-V01"]["dispatched"])

        with self.subTest("redispatch"):
            self.set_state(verify={"batch-V01": {"ids": ["REQ-001", "REQ-002"], "dispatched": t0}})
            r = run(["status", "--redispatch", "batch-V01"], self.cwd)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertRegex(r.stdout, r"batch-V01-r\d+", "--redispatch does not work for verifier batches")

        with self.subTest("failed"):
            self.set_state(verify={"batch-V01": {"ids": ["REQ-001", "REQ-002"], "dispatched": t0}},
                            verify_assigned={"REQ-001": "batch-V01", "REQ-002": "batch-V01"}, failed=[])
            r = run(["status", "--failed", "batch-V01"], self.cwd)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            state = read_json(self.out / "state.json")
            self.assertNotEqual(
                state.get("verify_assigned", {}).get("REQ-001"), "batch-V01",
                "a failed verifier batch's ids must leave verify_assigned so they reappear for verification",
            )

    # ---------------------------------------------------------------- criterion 4 + 5

    def test_solo_mode_relists_undispatched_verifier_batches(self):
        self.init_audit(agents="solo")
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, 6)])
        write_jsonl(self.out / "findings" / "manual.jsonl",
                    [finding("REQ-%03d" % i, status="PARTIAL", confidence="medium") for i in range(1, 6)])
        self.set_state(plan_time=time.time(), batches={}, verify={}, verify_assigned={},
                        spotchecked=[], hedges={}, failed=[])

        r1 = run(["status"], self.cwd)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        self.assertIn("SOLO MODE", r1.stdout)
        self.assertIn("batch-V01", r1.stdout)

        r2 = run(["status"], self.cwd)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn(
            "batch-V01", r2.stdout,
            "solo mode must re-list still-undispatched verifier batches on every status",
        )
        self.assertNotIn(
            "wait for completion notifications", r2.stdout,
            "solo mode never has anything 'running' to wait for",
        )

    def test_next_never_says_wait_when_nothing_running(self):
        """Edge case: an investigator finishes (SubagentStop ok) but its findings
        file has zero entries. Nothing is running (ri=rv=0), so NEXT must be a
        concrete command, never the generic 'wait for completion' line."""
        self.init_audit(agents="generic", cap=1)
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1), checklist_row(2)])
        rp = run(["plan"], self.cwd)
        self.assertEqual(rp.returncode, 0, rp.stdout + rp.stderr)
        write_jsonl(self.out / "findings" / "batch-01.jsonl", [])  # zero findings
        write_json(self.out / "events" / "batch-01.json", {"batch": "batch-01", "ok": True, "msg": "done: 0/2 written"})

        r = run(["status"], self.cwd)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(
            "wait for completion notifications", r.stdout,
            "nothing is running (ri=rv=0); NEXT must name a concrete command instead",
        )

    # ---------------------------------------------------------------- F8 criteria

    def test_solo_mode_relists_unfinished_investigator_batches(self):
        """After `plan` marks wave-1 batches dispatched, solo `status` must keep
        re-listing every unfinished investigator batch on every call, and NEXT
        must never tell a solo lead to wait for a notification that never comes."""
        self.init_audit(agents="solo")
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(i) for i in range(1, 11)])
        rp = run(["plan"], self.cwd)
        self.assertEqual(rp.returncode, 0, rp.stdout + rp.stderr)
        state = read_json(self.out / "state.json")
        batch_names = sorted(state["batches"])
        self.assertGreaterEqual(len(batch_names), 2, state["batches"])

        first_ids = state["batches"][batch_names[0]]["ids"]
        write_jsonl(self.out / "findings" / "manual.jsonl", [finding(rid) for rid in first_ids])

        for _ in range(2):
            r = run(["status"], self.cwd)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            for b in batch_names[1:]:
                self.assertIn(b, r.stdout, "unfinished investigator batch %s must stay listed: %s" % (b, r.stdout))
            self.assertNotIn(
                "wait for completion notifications", r.stdout,
                "solo mode never has anything 'running' to wait for",
            )

    def test_generic_undispatched_verifier_batch_relisted_by_later_status(self):
        """`--undispatch` leaves the verifier batch undispatched in THAT call; a
        separate later plain `status` with free slots re-lists and dispatches it."""
        self.init_audit(agents="generic")
        write_jsonl(self.out / "checklist.jsonl", [checklist_row(1), checklist_row(2)])
        t0 = time.time() - 1000
        self.set_state(
            plan_time=time.time(), batches={}, verify={"batch-V01": {"ids": ["REQ-001", "REQ-002"], "dispatched": t0}},
            verify_assigned={"REQ-001": "batch-V01", "REQ-002": "batch-V01"},
            spotchecked=[], hedges={}, failed=[],
        )

        r1 = run(["status", "--undispatch", "batch-V01"], self.cwd)
        self.assertEqual(r1.returncode, 0, r1.stdout + r1.stderr)
        self.assertIsNone(read_json(self.out / "state.json")["verify"]["batch-V01"]["dispatched"],
                          "--undispatch must leave the batch undispatched in that same call")

        r2 = run(["status"], self.cwd)
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        self.assertIn("batch-V01", r2.stdout,
                      "an undispatched verifier batch with free slots must be re-listed: %s" % r2.stdout)
        self.assertIsNotNone(read_json(self.out / "state.json")["verify"]["batch-V01"]["dispatched"],
                             "the re-listed verifier batch must be marked dispatched again")


if __name__ == "__main__":
    unittest.main()
