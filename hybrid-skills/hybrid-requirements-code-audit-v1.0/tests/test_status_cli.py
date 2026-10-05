import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent / "scripts" / "audit.py"
FAKE = HERE / "fake_opencode.py"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import audit  # noqa: E402
import hybrid_shared  # noqa: E402

SKILL = "hybrid-requirements-code-audit"
SHARED = {"tiers": {"std": {"model": "zai-coding-plan/glm-5.3", "variant": "high"},
                    "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low"}}}
STD_SPEC = hybrid_shared.cache_key(SHARED["tiers"]["std"])
SHARED_VARS = {hybrid_shared.STD_ENV: STD_SPEC,
              hybrid_shared.LITE_ENV: hybrid_shared.cache_key(SHARED["tiers"]["lite"])}


def _utc():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


class StatusCliTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name).resolve()
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.repo = self.tmp / "repo"
        (self.repo / "src").mkdir(parents=True)
        (self.repo / "src" / "app.py").write_text(
            "def login():\n    return True\n\n\ndef logout():\n    return False\n",
            encoding="utf-8",
        )
        self.spec = self.repo / "spec.md"
        self.spec.write_text("# Spec\n\n1. Users must log in.\n\n2. Users must log out.\n", encoding="utf-8")
        self.out = self.repo / ".hybrid-audit"
        self.routing = self.tmp / "routing.json"
        self.doctor = self.tmp / "doctor.json"
        self.telemetry = self.tmp / "lanes.jsonl"
        self.env = dict(os.environ)
        self.env.pop("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", None)
        self.env.pop("HYBRID_OPENCODE_MAX_PARALLEL", None)
        self.env.pop("HYBRID_OPENCODE_POOL", None)
        self.env.update({
            "HOME": str(self.home),
            "HYBRID_AUDIT_ROUTING": str(self.routing),
            "HYBRID_AUDIT_DOCTOR_CACHE": str(self.doctor),
            "HYBRID_AUDIT_TELEMETRY": str(self.telemetry),
            "HYBRID_AUDIT_OC_BIN": str(FAKE),
            "XDG_DATA_HOME": str(self.tmp / "data"),
            "HYBRID_OC_RETRY_DELAY_S": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        self.env.update(SHARED_VARS)

    def tearDown(self):
        self._tmp.cleanup()

    def _audit(self, *args):
        return subprocess.run(
            [sys.executable, str(AUDIT), "--cwd", str(self.repo)] + list(args),
            env=self.env, capture_output=True, encoding="utf-8", timeout=60,
        )

    def _doctor_ok(self):
        _write_json(self.doctor, {
            "t": _utc(), "ok": True, "version": "2.0.18", "binary": str(FAKE),
            "tiers": {name: {"ok": True, "key": hybrid_shared.cache_key(tier), "checked_at": time.time(),
                             "kind": "", "detail": "listed"}
                      for name, tier in SHARED["tiers"].items()},
        })

    def _bootstrap(self, preset, n_items=4, cap=4):
        proc = self._audit("init", "--spec", str(self.spec), "--cap", str(cap), "--preset", preset)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        rows = [{"id": "R%d" % i, "text": "Requirement %d must be implemented" % i, "strength": "MUST",
                 "category": "auth", "stakes": "normal", "search_hints": ["login"], "tags": [],
                 "source": "spec.md:%d" % i} for i in range(1, n_items + 1)]
        _write_jsonl(self.out / "checklist.jsonl", rows)
        proc = self._audit("plan", "--cap", str(cap))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return self.out, proc.stdout

    def _state(self, out):
        return json.loads((out / "state.json").read_text(encoding="utf-8"))

    def _batch_ids(self, out, name):
        return list(self._state(out)["batches"][name]["ids"])

    def _row(self, rid):
        return {"id": rid, "status": "MISSING", "evidence": [], "notes": "not found"}

    def test_merge_fills_missing_ids_from_retry_file(self):
        out, _ = self._bootstrap("claude", n_items=4, cap=1)
        ids = self._batch_ids(out, "batch-01")
        self.assertEqual(len(ids), 4)
        _write_jsonl(out / "findings" / "batch-01.jsonl", [self._row(ids[0])])
        time.sleep(0.05)
        _write_jsonl(out / "findings" / "batch-01.r1.jsonl", [self._row(i) for i in ids[1:]])
        m = audit.Merged(audit.Ctx(str(self.repo)))
        self.assertEqual(sorted(i for i in ids if i in m.finding), sorted(ids))
        self.assertEqual(m.coverage["batch-01"], (4, 4))
        self.assertTrue(m.batch_done["batch-01"])

    def _oc_batches(self, out):
        batches = self._state(out)["batches"]
        return [(n, b) for n, b in sorted(batches.items()) if str(b.get("backend", "")).startswith("oc:")]

    def _fail_event(self, out, name, reason, message):
        _write_json(out / "events" / ("%s.json" % name), {
            "batch": name, "ok": False, "agent_type": "opencode:hybrid-audit-investigator",
            "backend": "oc:std", "reason": reason, "message": message,
            "rounds": 1, "written": 0, "total": 2, "t": time.time(),
        })

    def test_throttle_event_falls_back_to_claude_and_sets_cooldown(self):
        self._doctor_ok()
        out, _ = self._bootstrap("hybrid", n_items=4, cap=4)
        oc = self._oc_batches(out)
        self.assertTrue(oc, json.dumps(self._state(out)["batches"]))
        name, b = oc[0]
        self._fail_event(out, name, "throttle", "rate limit exceeded")
        before = time.time()
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("FALLBACK %s (throttle) → Claude investigator: %d uncovered ids"
                      % (name, len(b["ids"])), proc.stdout)
        self.assertIn("%s-r" % name, proc.stdout)
        self.assertNotIn("oc-run %s" % name, proc.stdout)
        state = self._state(out)
        self.assertEqual(state["fallbacks"][name], "throttle")
        self.assertGreaterEqual(state["cooldown"]["std"], before + 119)
        self.assertEqual(state["batches"][name]["backend"], "claude")
        self.assertFalse((out / "events" / ("%s.json" % name)).exists())
        self.assertTrue((out / "oc" / ("%s.event.json" % name)).exists())

    def test_status_dispatches_queued_opencode_batches_in_opencode_block(self):
        self._doctor_ok()
        _write_json(self.routing, {"tiers": {"std": {"max_parallel": 2}}, "oc_batch_max": 1, "oc_overflow": "claude"})
        out, _ = self._bootstrap("hybrid", n_items=3, cap=4)
        oc = self._oc_batches(out)
        self.assertEqual(len(oc), 2, json.dumps(self._state(out)["batches"]))
        first, meta = oc[0]
        queued = oc[1][0]
        _write_jsonl(out / "findings" / ("%s.jsonl" % first),
                     [dict(self._row(i), backend="oc:std") for i in meta["ids"]])
        _write_json(out / "events" / ("%s.json" % first), {
            "batch": first, "ok": True, "agent_type": "opencode:hybrid-audit-investigator",
            "backend": "oc:std", "reason": None, "message": "", "rounds": 1,
            "written": len(meta["ids"]), "total": len(meta["ids"]), "t": time.time(),
        })
        proc = self._audit("status", "--undispatch", queued)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("OPENCODE 1 batches", proc.stdout)
        self.assertIn('audit.py" oc-run %s' % queued, proc.stdout)
        self.assertIn("completion notification (Agent or background Bash)", proc.stdout)
        self.assertEqual(self._state(out)["batches"][queued]["backend"], "oc:std")
        self.assertTrue((out / "batches" / ("%s.oc.md" % queued)).exists())

    def test_hybrid_queued_batch_waits_for_an_opencode_slot_instead_of_overflowing_to_claude(self):
        self._doctor_ok()
        _write_json(self.routing, {"tiers": {"std": {"max_parallel": 2}}, "oc_batch_max": 1})
        out, _ = self._bootstrap("hybrid", n_items=3, cap=4)
        (first, meta), (second, _), (queued, qmeta) = self._oc_batches(out)
        self.assertEqual((qmeta["wave"], qmeta["dispatched"]), (2, None))
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("Investigator %s:" % queued, proc.stdout)
        self.assertNotIn("oc-run %s" % queued, proc.stdout)
        queued_state = self._state(out)["batches"][queued]
        self.assertEqual((queued_state["backend"], queued_state["dispatched"]), ("oc:std", None))
        _write_jsonl(out / "findings" / ("%s.jsonl" % first),
                     [dict(self._row(i), backend="oc:std") for i in meta["ids"]])
        _write_json(out / "events" / ("%s.json" % first), {
            "batch": first, "ok": True, "agent_type": "opencode:hybrid-audit-investigator",
            "backend": "oc:std", "reason": None, "message": "", "rounds": 1,
            "written": len(meta["ids"]), "total": len(meta["ids"]), "t": time.time(),
        })
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('audit.py" oc-run %s' % queued, proc.stdout)
        self.assertEqual(self._state(out)["batches"][queued]["backend"], "oc:std")

    def test_pool_env_caps_the_opencode_batches_dispatched_at_once(self):
        self._doctor_ok()
        self.env["HYBRID_OPENCODE_POOL"] = "1"
        _write_json(self.routing, {"tiers": {"std": {"max_parallel": 4}}, "oc_batch_max": 1})
        out, _ = self._bootstrap("hybrid", n_items=3, cap=4)
        waves = [meta["wave"] for _, meta in self._oc_batches(out)]
        self.assertEqual(waves, [1, 2, 2])

    def test_queued_batch_is_not_hedged_until_its_own_run_has_started(self):
        self._doctor_ok()
        _write_json(self.routing, {"tiers": {"std": {"max_parallel": 1}}, "oc_batch_max": 1})
        out, _ = self._bootstrap("hybrid", n_items=4, cap=4)
        oc = self._oc_batches(out)
        self.assertEqual(len(oc), 4, json.dumps(self._state(out)["batches"]))
        (b1, m1), (b2, m2), (b3, _), (b4, _) = oc
        t0 = time.time() - 1000
        state = self._state(out)
        for name in (b1, b2, b3):  # b4 stays queued: no free slot, so it has no start time
            state["batches"][name]["dispatched"] = t0
        _write_json(out / "state.json", state)
        for name, meta in ((b1, m1), (b2, m2)):
            path = out / "findings" / ("%s.jsonl" % name)
            _write_jsonl(path, [dict(self._row(i), backend="oc:std") for i in meta["ids"]])
            os.utime(str(path), (t0 + 10, t0 + 10))
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        stragglers = proc.stdout[proc.stdout.index("STRAGGLERS"):]
        self.assertIn("  %s (running " % b3, stragglers)
        self.assertNotIn(b4, stragglers)
        self.assertNotIn(b4, self._state(out)["hedges"])
        self.assertIsNone(self._state(out)["batches"][b4]["dispatched"])

    def test_claude_preset_status_has_no_opencode_output(self):
        out, _ = self._bootstrap("claude", n_items=4, cap=1)
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("OPENCODE", proc.stdout)
        self.assertNotIn("oc-run", proc.stdout)
        self.assertNotIn("background Bash", proc.stdout)
        self.assertNotIn("fallbacks", self._state(out))

    def test_opencode_preset_routes_verifier_batches_to_opencode(self):
        self._doctor_ok()
        out, _ = self._bootstrap("opencode", n_items=4, cap=4)
        for name, b in self._state(out)["batches"].items():
            rows = [{"id": i, "status": "MATCHED",
                     "evidence": [{"path": "src/app.py", "lines": "1-2", "note": "def login():"}],
                     "notes": "found", "backend": b.get("backend", "claude")} for i in b["ids"]]
            _write_jsonl(out / "findings" / ("%s.jsonl" % name), rows)
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        state = self._state(out)
        verify = state.get("verify", {})
        self.assertTrue(verify)
        oc = [n for n, v in verify.items() if str(v.get("backend", "")).startswith("oc:")]
        self.assertTrue(oc)
        for name, v in verify.items():
            self.assertLessEqual(len(v["ids"]), 3)
            self.assertTrue((out / "verify" / ("%s.md" % name)).exists())
        for name in oc:
            self.assertTrue((out / "verify" / ("%s.oc.md" % name)).exists())
            self.assertIn('audit.py" oc-run %s' % name, proc.stdout)
        self.assertEqual(sorted(state["verify_assigned"]), ["R1", "R2", "R3", "R4"])

    def test_failed_opencode_verify_batch_falls_back_to_claude_once(self):
        self._doctor_ok()
        _write_json(self.routing, {"roles": {"verifier": "std"}})
        out, _ = self._bootstrap("hybrid", n_items=4, cap=4)
        for name, b in self._state(out)["batches"].items():
            rows = [{"id": i, "status": "MATCHED", "evidence": [{"path": "src/app.py", "lines": "1-2"}],
                     "notes": "found", "backend": b.get("backend", "claude")} for i in b["ids"]]
            _write_jsonl(out / "findings" / ("%s.jsonl" % name), rows)
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        name, v = [(n, v) for n, v in sorted(self._state(out)["verify"].items())
                   if str(v.get("backend", "")).startswith("oc:")][0]
        _write_json(out / "events" / ("%s.json" % name), {
            "batch": name, "ok": False, "agent_type": "opencode:hybrid-audit-verifier", "backend": v["backend"],
            "reason": "format", "message": "no marker block", "rounds": 3, "written": 0,
            "total": len(v["ids"]), "t": time.time(),
        })
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("FALLBACK %s (format) → Claude verifier: %d uncovered ids" % (name, len(v["ids"])), proc.stdout)
        self.assertIn("  %s → prompt: Verifier %s: read %s and follow it exactly."
                      % (name, name, out / "verify" / ("%s.md" % name)), proc.stdout)
        state = self._state(out)
        self.assertEqual(state["fallbacks"][name], "format")
        self.assertEqual(state["verify"][name]["backend"], "claude")
        again = self._audit("status")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertNotIn("FALLBACK", again.stdout)
        self.assertNotIn("Verifier %s:" % name, again.stdout)

    def test_slow_opencode_batch_gets_one_claude_hedge(self):
        self._doctor_ok()
        _write_json(self.routing, {"tiers": {"std": {"max_parallel": 2}}, "oc_batch_max": 1, "oc_overflow": "claude"})
        out, _ = self._bootstrap("hybrid", n_items=3, cap=4)
        oc = self._oc_batches(out)
        self.assertEqual(len(oc), 2, json.dumps(self._state(out)["batches"]))
        (done, meta), (slow, _) = oc
        t0 = time.time() - 1000
        state = self._state(out)
        for name, _ in oc:
            state["batches"][name]["dispatched"] = t0
        _write_json(out / "state.json", state)
        path = out / "findings" / ("%s.jsonl" % done)
        _write_jsonl(path, [dict(self._row(i), backend="oc:std") for i in meta["ids"]])
        os.utime(str(path), (t0 + 10, t0 + 10))
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        stragglers = proc.stdout[proc.stdout.index("STRAGGLERS"):]
        self.assertIn("  %s (running " % slow, stragglers)
        self.assertIn(", oc:std) → HEDGE prompt: Investigator %s: read %s and follow it exactly, but write your "
                      "findings to %s instead." % (slow, out / "batches" / ("%s.md" % slow),
                                                   out / "findings" / ("%s.r2.jsonl" % slow)), stragglers)
        self.assertIn(slow, self._state(out)["hedges"])
        again = self._audit("status")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertNotIn("STRAGGLERS", again.stdout)

    def _all_matched(self, out, confidence=None):
        for name, b in self._state(out)["batches"].items():
            rows = [{"id": i, "status": "MATCHED", "evidence": [{"path": "src/app.py", "lines": "1-2"}],
                     "notes": "found", "backend": b.get("backend", "claude")} for i in b["ids"]]
            if confidence:
                for row in rows:
                    row["confidence"] = confidence
            _write_jsonl(out / "findings" / ("%s.jsonl" % name), rows)

    def _held_investigator(self):
        self._doctor_ok()
        out, _ = self._bootstrap("opencode", n_items=4, cap=4)
        name = self._oc_batches(out)[0][0]
        self._fail_event(out, name, "timeout", "no output for 180s")
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return out, name, proc

    def test_status_prints_logged_oc_lines_first_and_only_once(self):
        out, _ = self._bootstrap("claude", n_items=4, cap=1)
        line = hybrid_shared.oc_line("OC-ERROR", SKILL, "batch-01", "std", STD_SPEC, "auth", "401 Unauthorized")
        hybrid_shared.log_line(out / "oc-errors.jsonl", line)
        first = self._audit("status")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(first.stdout.splitlines()[0], line)
        again = self._audit("status")
        self.assertNotIn(line, again.stdout)

    def test_opencode_preset_failure_holds_the_batch_without_a_claude_fallback(self):
        out, name, proc = self._held_investigator()
        self.assertNotIn("FALLBACK", proc.stdout)
        self.assertNotIn("Investigator %s:" % name, proc.stdout)
        state = self._state(out)
        self.assertEqual(state["batches"][name]["backend"], "held")
        self.assertEqual(state["held"][name]["role"], "investigator")
        self.assertNotIn(name, state.get("fallbacks", {}))
        self.assertTrue(any(ln.startswith("NEXT:") and "held" in ln for ln in proc.stdout.splitlines()), proc.stdout)
        again = self._audit("status")
        self.assertNotIn("oc-run %s" % name, again.stdout)

    def test_retry_releases_a_held_batch_for_opencode(self):
        out, name, _ = self._held_investigator()
        self._fake({"text": "HA-INVESTIGATOR-OK", "finish": "stop"})  # --retry re-pings the tier
        proc = self._audit("status", "--retry", "all")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn('audit.py" oc-run %s' % name, proc.stdout)
        state = self._state(out)
        self.assertEqual(state["batches"][name]["backend"], "oc:std")
        self.assertEqual(state.get("held", {}), {})

    def test_retry_rereads_the_shared_env_fixed_after_init(self):
        self._doctor_ok()
        for name in SHARED_VARS:
            self.env.pop(name)
        out, _ = self._bootstrap("opencode", n_items=4, cap=4)
        self.assertEqual({b["backend"] for b in self._state(out)["batches"].values()}, {"held"})
        self.env.update(SHARED_VARS)
        self._fake({"text": "HA-INVESTIGATOR-OK", "finish": "stop"})  # --retry re-pings the tier
        proc = self._audit("status", "--retry", "all")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual({b["backend"] for b in self._state(out)["batches"].values()}, {"oc:std"})
        self.assertEqual(self._state(out).get("held", {}), {})

    def test_to_claude_runs_the_role_on_claude(self):
        out, name, _ = self._held_investigator()
        proc = self._audit("status", "--to-claude", "investigator")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("Investigator %s: read %s and follow it exactly." % (name, out / "batches" / ("%s.md" % name)),
                      proc.stdout)
        state = self._state(out)
        self.assertEqual(state["batches"][name]["backend"], "claude")
        self.assertEqual(state["claude_roles"], ["investigator"])
        self.assertEqual(state.get("held", {}), {})

    def test_mode_hybrid_reroutes_batches_held_at_plan_time(self):
        out, _ = self._bootstrap("opencode", n_items=4, cap=4)
        self.assertEqual({b["backend"] for b in self._state(out)["batches"].values()}, {"held"})
        proc = self._audit("status", "--mode", "hybrid")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        cfg = json.loads((out / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["preset"], "hybrid")
        self.assertEqual({b["backend"] for b in self._state(out)["batches"].values()}, {"claude"})
        self.assertIn("Investigator batch-01: read", proc.stdout)

    def test_failed_opencode_verify_batch_is_held_in_opencode_preset(self):
        self._doctor_ok()
        out, _ = self._bootstrap("opencode", n_items=4, cap=4)
        self._all_matched(out)
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        name, v = [(n, v) for n, v in sorted(self._state(out)["verify"].items())
                   if str(v.get("backend", "")).startswith("oc:")][0]
        _write_json(out / "events" / ("%s.json" % name), {
            "batch": name, "ok": False, "agent_type": "opencode:hybrid-audit-verifier", "backend": v["backend"],
            "reason": "format", "message": "no marker block", "rounds": 3, "written": 0,
            "total": len(v["ids"]), "t": time.time(),
        })
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("FALLBACK", proc.stdout)
        state = self._state(out)
        self.assertEqual(state["verify"][name]["backend"], "held")
        self.assertEqual(state["held"][name]["role"], "verifier")

    def _held_verifier(self):
        self._doctor_ok()
        out, _ = self._bootstrap("opencode", n_items=4, cap=4)
        self._all_matched(out)
        self._audit("status")
        name, v = [(n, v) for n, v in sorted(self._state(out)["verify"].items())
                   if str(v.get("backend", "")).startswith("oc:")][0]
        _write_json(out / "events" / ("%s.json" % name), {
            "batch": name, "ok": False, "agent_type": "opencode:hybrid-audit-verifier", "backend": v["backend"],
            "reason": "format", "message": "no marker block", "rounds": 3, "written": 0,
            "total": len(v["ids"]), "t": time.time(),
        })
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(self._state(out)["verify"][name]["backend"], "held")
        return out, name

    def _assert_no_stranded_verifier(self, out):
        state = self._state(out)
        if not state.get("held"):
            for name, v in state.get("verify", {}).items():
                self.assertFalse(v.get("backend") == "held" and v.get("dispatched") is None, name)

    def test_mode_claude_does_not_strand_a_held_verifier_batch(self):
        out, name = self._held_verifier()
        proc = self._audit("status", "--mode", "claude")
        cfg = json.loads((out / "config.json").read_text(encoding="utf-8"))
        state = self._state(out)
        if proc.returncode != 0:
            self.assertTrue(any(ln.startswith("OC-ERROR %s status " % SKILL) and " kind=config" in ln
                                for ln in proc.stdout.splitlines()), proc.stdout)
            self.assertEqual(cfg["preset"], "opencode")
        else:
            again = self._audit("status")
            self.assertIn("Verifier %s: read" % name, proc.stdout + again.stdout)
            self.assertEqual(self._state(out)["verify"][name]["backend"], "claude")
        self._assert_no_stranded_verifier(out)
        self.assertIn(state["verify"][name]["backend"], ("held", "claude"))

    def test_mode_claude_is_refused_while_opencode_units_are_in_flight(self):
        self._doctor_ok()
        out, _ = self._bootstrap("opencode", n_items=4, cap=4)
        self.assertTrue(self._oc_batches(out))
        proc = self._audit("status", "--mode", "claude")
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        self.assertTrue(any(ln.startswith("OC-ERROR %s status " % SKILL) and " kind=config" in ln
                            for ln in proc.stdout.splitlines()), proc.stdout)
        cfg = json.loads((out / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["preset"], "opencode")

    def _failed_event(self, out, name, meta, agent):
        _write_json(out / "events" / ("%s.json" % name), {
            "batch": name, "ok": False, "agent_type": agent, "backend": meta["backend"],
            "reason": "format", "message": "no marker block", "rounds": 3, "written": 1,
            "total": len(meta["ids"]), "t": time.time(),
        })

    def _assert_claude_refused(self, out):
        proc = self._audit("status", "--mode", "claude")
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        self.assertTrue(any(ln.startswith("OC-ERROR %s status " % SKILL) and " kind=config" in ln
                            for ln in proc.stdout.splitlines()), proc.stdout)
        cfg = json.loads((out / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["preset"], "opencode")

    def test_mode_claude_is_refused_for_a_partial_verify_file_with_a_failed_event(self):
        self._doctor_ok()
        _write_json(self.routing, {"tiers": {"std": {"max_parallel": 1}}, "oc_batch_max": 4})
        out, _ = self._bootstrap("opencode", n_items=4, cap=4)
        self._all_matched(out)
        self._audit("status")
        name, v = [(n, v) for n, v in sorted(self._state(out)["verify"].items())
                   if str(v.get("backend", "")).startswith("oc:") and len(v["ids"]) > 1][0]
        _write_jsonl(out / "verify" / ("%s.jsonl" % name),
                     [{"id": v["ids"][0], "verdict": "CONFIRMED", "notes": "ok"}])
        self._failed_event(out, name, v, "opencode:hybrid-audit-verifier")
        self._assert_claude_refused(out)

    def test_mode_claude_is_refused_for_a_partial_findings_file_with_a_failed_event(self):
        self._doctor_ok()
        _write_json(self.routing, {"tiers": {"std": {"max_parallel": 1}}, "oc_batch_max": 4})
        out, _ = self._bootstrap("opencode", n_items=4, cap=4)
        name, b = [(n, b) for n, b in sorted(self._state(out)["batches"].items())
                   if str(b.get("backend", "")).startswith("oc:") and len(b["ids"]) > 1][0]
        _write_jsonl(out / "findings" / ("%s.jsonl" % name), [dict(self._row(b["ids"][0]), backend=b["backend"])])
        self._failed_event(out, name, b, "opencode:hybrid-audit-investigator")
        self._assert_claude_refused(out)

    def test_mode_claude_is_allowed_when_opencode_units_are_fully_covered(self):
        self._doctor_ok()
        out, _ = self._bootstrap("opencode", n_items=4, cap=4)
        for name, b in self._state(out)["batches"].items():
            _write_jsonl(out / "findings" / ("%s.jsonl" % name),
                         [dict(self._row(i), backend=b["backend"]) for i in b["ids"]])
        proc = self._audit("status", "--mode", "claude")
        self.assertFalse(any(ln.startswith("OC-ERROR ") and "--mode claude would strand" in ln
                             for ln in proc.stdout.splitlines()), proc.stdout)
        cfg = json.loads((out / "config.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["preset"], "claude")

    def test_mode_help_lists_the_accepted_values(self):
        proc = self._audit("status", "-h")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        text = " ".join(proc.stdout.split())
        self.assertIn("hybrid|claude|opencode", text)
        self.assertIn("max", text)

    def test_breaker_summary_is_printed_once_when_the_wave_ends(self):
        self._doctor_ok()
        out, _ = self._bootstrap("hybrid", n_items=4, cap=4)
        hybrid_shared.breaker_trip(out, "std", STD_SPEC, "auth", "401 Unauthorized")
        self.assertGreater(hybrid_shared.breaker_skip(out, "std", STD_SPEC), 0)
        self._all_matched(out, confidence="high")
        first = self._audit("status")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        summary = [ln for ln in first.stdout.splitlines() if " kind=breaker " in ln]
        self.assertEqual(len(summary), 1, first.stdout)
        self.assertTrue(summary[0].startswith("OC-ERROR %s breaker " % SKILL), summary[0])
        again = self._audit("status")
        self.assertNotIn(" kind=breaker ", again.stdout)

    # ---- frozen tier health, explicit retry, fresh init, risky opencode verdicts

    def _missing_findings(self, out):
        for name, b in self._state(out)["batches"].items():
            _write_jsonl(out / "findings" / ("%s.jsonl" % name),
                         [{"id": i, "status": "MISSING", "confidence": "high", "evidence": [], "notes": "none",
                           "backend": b.get("backend", "claude")} for i in b["ids"]])

    def test_stale_doctor_cache_never_downgrades_a_running_audit(self):
        self._doctor_ok()
        out, _ = self._bootstrap("opencode", n_items=4, cap=4)
        self.assertTrue(self._state(out)["health"]["frozen"])
        self._missing_findings(out)
        old = json.loads(self.doctor.read_text(encoding="utf-8"))
        for entry in old["tiers"].values():
            entry["checked_at"] = time.time() - 86400
        _write_json(self.doctor, old)
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        verify = self._state(out)["verify"]
        self.assertTrue(verify and all(v["backend"] == "oc:std" for v in verify.values()), verify)
        self.assertFalse(self._state(out).get("held"), proc.stdout)

    def test_explicit_retry_pings_and_closes_the_tier_breaker(self):
        self._doctor_ok()
        out, _ = self._bootstrap("hybrid", n_items=4, cap=4)
        hybrid_shared.breaker_trip(out, "std", STD_SPEC, "auth", "401 Unauthorized")
        self.assertTrue(hybrid_shared.breaker_open(out, "std", STD_SPEC))
        self._fake({"text": "HA-INVESTIGATOR-OK", "finish": "stop"})
        proc = self._audit("status", "--retry", "all")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(hybrid_shared.breaker_open(out, "std", STD_SPEC), proc.stdout)

    def test_force_init_resets_breakers_events_and_oc_lines_in_a_reused_out_dir(self):
        self._doctor_ok()
        out, _ = self._bootstrap("hybrid", n_items=2, cap=4)
        hybrid_shared.breaker_trip(out, "std", STD_SPEC, "auth", "401")
        self._fail_event(out, "batch-01", "timeout", "late")
        (out / "oc-errors.jsonl").write_text('"OC-ERROR old"\n', encoding="utf-8")
        (out / "oc-errors.jsonl.seen").write_text("1\n", encoding="utf-8")
        proc = self._audit("init", "--force", "--spec", str(self.spec), "--out", str(out), "--preset", "hybrid")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse(hybrid_shared.breaker_open(out, "std", STD_SPEC))
        self.assertEqual(list((out / "events").glob("*.json")), [])
        self.assertFalse((out / "oc-errors.jsonl").exists())
        self.assertFalse((out / "oc-errors.jsonl.seen").exists())

    def test_opencode_verifier_missing_verdict_is_queued_for_claude_adjudication(self):
        self._doctor_ok()
        out, _ = self._bootstrap("opencode", n_items=2, cap=4)
        self._missing_findings(out)
        self._audit("status")
        for name, v in self._state(out)["verify"].items():
            _write_jsonl(out / "verify" / ("%s.jsonl" % name),
                         [{"id": i, "verified_status": "MISSING", "confidence": "high", "reason": "two passes",
                           "evidence": [], "backend": v["backend"]} for i in v["ids"]])
        m = audit.Merged(audit.Ctx(str(self.repo)))
        queued = dict(m.queue_ids())
        self.assertEqual(sorted(queued), ["R1", "R2"])
        self.assertIn("opencode verifier", queued["R1"])

    # ---- retries and the switch to Claude sonnet

    def _fake(self, step):
        script, log = self.tmp / "fake.json", self.tmp / "fake.log"
        _write_json(script, step)
        self.env.update({"HYBRID_AUDIT_FAKE_SCRIPT": str(script), "HYBRID_AUDIT_FAKE_LOG": str(log)})
        return log

    @staticmethod
    def _spawns(log):
        if not log.exists():
            return 0
        return sum(1 for ln in log.read_text(encoding="utf-8").splitlines() if json.loads(ln)["argv"][:1] == ["run"])

    def _two_oc_batches(self, preset="hybrid"):
        self._doctor_ok()
        _write_json(self.routing, {"tiers": {"std": {"max_parallel": 2}}, "oc_batch_max": 1, "oc_overflow": "claude"})
        out, _ = self._bootstrap(preset, n_items=3, cap=4)
        oc = [n for n, _ in self._oc_batches(out)]
        # mode opencode sends the third item to opencode too (it waits for a slot, max_parallel 2); hybrid with oc_overflow claude sends it to Claude
        self.assertEqual(len(oc), 3 if preset == "opencode" else 2, json.dumps(self._state(out)["batches"]))
        return out, oc[:2]

    def test_connection_failure_switches_the_rest_of_the_run_to_claude_sonnet(self):
        out, (first, second) = self._two_oc_batches()
        log = self._fake({"scenario": "throttle"})
        run = self._audit("oc-run", first)
        self.assertEqual(run.returncode, 3, run.stdout + run.stderr)
        self.assertEqual(self._spawns(log), 4)
        self.assertEqual(run.stdout.count(" :: retry "), 3, run.stdout)
        self.assertEqual(run.stdout.count(" kind=switch :: "), 1, run.stdout)
        self.assertTrue((out / "oc-switched.json").exists())
        # `second` is still waiting for an opencode slot: it goes to Claude sonnet, the failed one falls back too
        proc = self._audit("status", "--undispatch", second)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(proc.stdout.count(" kind=switch :: "), 1, proc.stdout)
        self.assertIn("FALLBACK %s (throttle) → Claude investigator" % first, proc.stdout)
        self.assertIn("Investigator %s: read" % second, proc.stdout)
        self.assertIn("Investigator %s-r" % first, proc.stdout)
        self.assertRegex(proc.stdout, r"DISPATCH NOW .*subagent_type=general-purpose, model=sonnet;")
        self.assertNotIn("model=haiku", proc.stdout)
        self.assertNotIn("OPENCODE", proc.stdout)
        self.assertNotIn("oc-run", proc.stdout)
        batches = self._state(out)["batches"]
        self.assertEqual((batches[first]["backend"], batches[second]["backend"]), ("claude", "claude"))
        self.assertEqual(self._spawns(log), 4)
        again = self._audit("status")
        self.assertNotIn(" kind=switch :: ", again.stdout)
        self.assertNotIn("OPENCODE", again.stdout)

    def test_an_oc_run_started_after_the_switch_spawns_nothing_and_falls_back_to_sonnet(self):
        out, (first, second) = self._two_oc_batches()
        log = self._fake({"scenario": "throttle"})
        self.assertEqual(self._audit("oc-run", first).returncode, 3)
        late = self._audit("oc-run", second)
        self.assertEqual(late.returncode, 3, late.stdout + late.stderr)
        self.assertRegex(late.stdout.strip(), r"^OC %s oc:std FALLBACK \(switched\) 0/\d+ — 0 rounds — \d+s$" % second)
        self.assertEqual(self._spawns(log), 4)
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("FALLBACK %s (switched) → Claude investigator" % second, proc.stdout)
        self.assertIn("Investigator %s-r" % second, proc.stdout)
        self.assertRegex(proc.stdout, r"DISPATCH NOW .*model=sonnet;")

    def test_plan_after_the_switch_is_all_claude_sonnet(self):
        out, _ = self._two_oc_batches()
        hybrid_shared.switch_to_claude(out, "batch-01", "std", STD_SPEC, "auth", "401 Unauthorized")
        proc = self._audit("plan", "--cap", "4")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("OPENCODE", proc.stdout)
        self.assertRegex(proc.stdout, r"DISPATCH NOW .*model=sonnet;")
        self.assertEqual({b["backend"] for b in self._state(out)["batches"].values()}, {"claude"})

    def test_verifiers_and_parsers_route_to_claude_after_the_switch(self):
        self._doctor_ok()
        _write_json(self.routing, {"roles": {"verifier": "std", "parser": "std"}})
        out, _ = self._bootstrap("hybrid", n_items=4, cap=4)
        hybrid_shared.switch_to_claude(out, "batch-01", "std", STD_SPEC, "crash", "exit 1")
        self._all_matched(out)
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        verify = self._state(out)["verify"]
        self.assertTrue(verify)
        self.assertEqual({v["backend"] for v in verify.values()}, {"claude"})
        self.assertNotIn("OPENCODE", proc.stdout)
        self.assertRegex(proc.stdout, r"DISPATCH NOW .*subagent_type=general-purpose, model=sonnet;")
        parse = self._audit("parse-plan", "--sections", "2")
        self.assertEqual(parse.returncode, 0, parse.stdout + parse.stderr)
        self.assertNotIn("OPENCODE", parse.stdout)
        self.assertIn("model=sonnet", parse.stdout)
        self.assertEqual(set(self._state(out)["parse"]["backends"].values()), {"claude"})

    def test_preset_opencode_retries_then_holds_without_a_switch(self):
        out, (first, _) = self._two_oc_batches("opencode")
        log = self._fake({"scenario": "throttle"})
        run = self._audit("oc-run", first)
        self.assertEqual(run.returncode, 3, run.stdout + run.stderr)
        self.assertEqual(self._spawns(log), 4)
        self.assertEqual(run.stdout.count(" :: retry "), 3, run.stdout)
        self.assertNotIn("kind=switch", run.stdout)
        self.assertFalse((out / "oc-switched.json").exists())
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("FALLBACK", proc.stdout)
        self.assertNotIn("kind=switch", proc.stdout)
        self.assertEqual(self._state(out)["batches"][first]["backend"], "held")
        self.assertTrue(any(ln.startswith("NEXT:") and "held" in ln for ln in proc.stdout.splitlines()), proc.stdout)

    def test_a_new_audit_starts_unswitched(self):
        out, _ = self._two_oc_batches()
        hybrid_shared.switch_to_claude(out, "batch-01", "std", STD_SPEC, "auth", "401 Unauthorized")
        proc = self._audit("init", "--force", "--spec", str(self.spec), "--preset", "hybrid")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse((self.out / "oc-switched.json").exists())
        other = self.tmp / "other-out"
        hybrid_shared.switch_to_claude(other, "batch-01", "std", STD_SPEC, "auth", "401 Unauthorized")
        proc = self._audit("init", "--force", "--spec", str(self.spec), "--preset", "hybrid", "--out", str(other))
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertFalse((other / "oc-switched.json").exists())


if __name__ == "__main__":
    unittest.main()
