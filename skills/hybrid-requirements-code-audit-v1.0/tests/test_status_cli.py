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
        self.out = self.repo / ".audit"
        self.routing = self.tmp / "routing.json"
        self.doctor = self.tmp / "doctor.json"
        self.telemetry = self.tmp / "lanes.jsonl"
        self.env = dict(os.environ)
        self.env.pop("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", None)
        self.env.update({
            "HOME": str(self.home),
            "HA_ROUTING": str(self.routing),
            "HA_DOCTOR_CACHE": str(self.doctor),
            "HA_TELEMETRY": str(self.telemetry),
            "HA_OC_BIN": str(FAKE),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
        })

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
            "tiers": {
                "std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "listed": True,
                        "ping": "ok", "note": "", "down": None},
                "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low", "listed": True,
                         "ping": "ok", "note": "", "down": None},
            },
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
            "batch": name, "ok": False, "agent_type": "opencode:ha-investigator",
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

    def test_unavailable_event_marks_tier_down(self):
        self._doctor_ok()
        out, _ = self._bootstrap("hybrid", n_items=4, cap=4)
        name = self._oc_batches(out)[0][0]
        self._fail_event(out, name, "unavailable", "model not found")
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("FALLBACK %s (unavailable)" % name, proc.stdout)
        cache = json.loads(self.doctor.read_text(encoding="utf-8"))
        self.assertEqual(cache["tiers"]["std"]["down"]["reason"], "unavailable")
        again = self._audit("status")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(again.stdout.count("FALLBACK %s" % name), 0)

    def test_status_dispatches_queued_opencode_batches_in_opencode_block(self):
        self._doctor_ok()
        _write_json(self.routing, {"tiers": {"std": {"max_parallel": 2}}, "oc_batch_max": 1})
        out, _ = self._bootstrap("hybrid", n_items=3, cap=4)
        oc = self._oc_batches(out)
        self.assertEqual(len(oc), 2, json.dumps(self._state(out)["batches"]))
        first, meta = oc[0]
        queued = oc[1][0]
        _write_jsonl(out / "findings" / ("%s.jsonl" % first),
                     [dict(self._row(i), backend="oc:std") for i in meta["ids"]])
        _write_json(out / "events" / ("%s.json" % first), {
            "batch": first, "ok": True, "agent_type": "opencode:ha-investigator",
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

    def test_claude_preset_status_has_no_opencode_output(self):
        out, _ = self._bootstrap("claude", n_items=4, cap=1)
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertNotIn("OPENCODE", proc.stdout)
        self.assertNotIn("oc-run", proc.stdout)
        self.assertNotIn("background Bash", proc.stdout)
        self.assertNotIn("fallbacks", self._state(out))

    def test_max_preset_routes_verifier_batches_to_opencode(self):
        self._doctor_ok()
        out, _ = self._bootstrap("max", n_items=4, cap=4)
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
        out, _ = self._bootstrap("max", n_items=4, cap=4)
        for name, b in self._state(out)["batches"].items():
            rows = [{"id": i, "status": "MATCHED", "evidence": [{"path": "src/app.py", "lines": "1-2"}],
                     "notes": "found", "backend": b.get("backend", "claude")} for i in b["ids"]]
            _write_jsonl(out / "findings" / ("%s.jsonl" % name), rows)
        proc = self._audit("status")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        name, v = [(n, v) for n, v in sorted(self._state(out)["verify"].items())
                   if str(v.get("backend", "")).startswith("oc:")][0]
        _write_json(out / "events" / ("%s.json" % name), {
            "batch": name, "ok": False, "agent_type": "opencode:ha-verifier", "backend": v["backend"],
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
        _write_json(self.routing, {"tiers": {"std": {"max_parallel": 2}}, "oc_batch_max": 1})
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


if __name__ == "__main__":
    unittest.main()
