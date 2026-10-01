import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hybrid_shared  # noqa: E402
import ha_run  # noqa: E402


class RoleOfTest(unittest.TestCase):
    def test_roles(self):
        self.assertEqual(ha_run.role_of("batch-03"), "investigator")
        self.assertEqual(ha_run.role_of("batch-V02"), "verifier")
        self.assertEqual(ha_run.role_of("section-01"), "parser")

    def test_unknown_names(self):
        self.assertEqual(ha_run.role_of("batch-03.r2"), "")
        self.assertEqual(ha_run.role_of("notes"), "")
        self.assertEqual(ha_run.role_of(""), "")


class ParseBlockTest(unittest.TestCase):
    def test_tolerant_rows_and_errors(self):
        block = "\n".join(["", "// comment", "[", '{"id": "R1", "status": "MATCHED"},', "not json", "]"])
        rows, errors = ha_run.parse_block(block)
        self.assertEqual([r["id"] for r in rows], ["R1"])
        self.assertEqual(len(errors), 1)
        self.assertIn("not json", errors[0])

    def test_empty_block(self):
        self.assertEqual(ha_run.parse_block(""), ([], []))

    def test_non_object_is_an_error(self):
        rows, errors = ha_run.parse_block("[1, 2]")
        self.assertEqual(rows, [])
        self.assertEqual(len(errors), 1)


ROUTING = {
    "preset": "hybrid",
    "tiers": {"std": {"model": "zai-coding-plan/glm-5.3", "variant": "high", "max_parallel": 6,
                      "stall_s": 180, "timeout_s": 900}},
    "roles": {"investigator": "std", "verifier": "claude", "parser": "claude"},
    "oc_batch_max": 4,
    "max_repairs": 2,
    "throttle_cooldown_s": 120,
}
SPEC = hybrid_shared.model_spec(ROUTING["tiers"]["std"])


def _result(text="", session="ses_1", rc=0, reason="", errors=None, note=""):
    return {"session": session, "text": text,
            "usage": {"input": 10, "output": 5, "reasoning": 1, "cache_read": 0, "cache_write": 0, "cost": 0.0},
            "errors": list(errors or []), "throttled": False, "events": 3, "tools": [],
            "rc": rc, "reason": reason, "note": note, "pid": 4242, "duration": 0.1}


def _block(name, rows):
    lines = ["chatter outside the block", "@@@ BEGIN " + name]
    lines += [r if isinstance(r, str) else json.dumps(r) for r in rows]
    lines += ["@@@ END " + name, "trailing text"]
    return "\n".join(lines)


def _row(rid, notes=""):
    return {"id": rid, "status": "MATCHED", "evidence": [], "notes": notes}


def _fake_oracle(rows, ids, repo, role, audit_dir=None):
    kept = list(rows) if role == "parser" else [r for r in rows if r.get("id") in ids]
    stats = {"foreign": len(rows) - len(kept), "dropped": 0, "demoted": 0, "invalid_status": 0, "problems": []}
    return kept, stats


class RunBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.repo = (self.tmp / "repo")
        self.out = self.repo / "audit-out"
        for sub in ("batches", "verify", "parse", "findings", "events"):
            (self.out / sub).mkdir(parents=True)
        (self.out / "batches" / "batch-01.oc.md").write_text("investigator brief\n", encoding="utf-8")
        (self.out / "verify" / "batch-V01.oc.md").write_text("verifier brief\n", encoding="utf-8")
        (self.out / "parse" / "section-01.oc.md").write_text("parser brief\n", encoding="utf-8")
        self.repo = self.repo.resolve()
        self.out = self.out.resolve()
        self.state = {
            "batches": {"batch-01": {"ids": ["R1", "R2"], "wave": 1, "dispatched": None, "backend": "oc:std"}},
            "verify": {"batch-V01": {"ids": ["R1"], "dispatched": None, "backend": "oc:std"}},
            "parse": {"backends": {"section-01": "oc:std"}},
        }
        self.cfg = {"preset": "hybrid", "routing": json.loads(json.dumps(ROUTING)), "repo": str(self.repo)}
        self.doctor = {"ok": True, "version": "2.0.19", "tiers": {"std": {
            "ok": True, "key": hybrid_shared.cache_key(ROUTING["tiers"]["std"]),
            "checked_at": time.time(), "kind": "", "detail": "listed"}}}
        self.script = []
        self.calls = []
        self.records = []
        self.stdout = io.StringIO()
        env = {"HOME": str(self.tmp / "home"), "HYBRID_AUDIT_ROUTING": str(self.tmp / "routing.json"),
               "HYBRID_AUDIT_DOCTOR_CACHE": str(self.tmp / "doctor.json"), "HYBRID_AUDIT_TELEMETRY": str(self.tmp / "lanes.jsonl"),
               "HYBRID_OPENCODE_STD": SPEC, "HYBRID_OPENCODE_LITE": SPEC,
               "XDG_DATA_HOME": str(self.tmp / "data"),
               "HYBRID_OC_RETRY_DELAY_S": "0",
               "HYBRID_AUDIT_OC_BIN": str(self.tmp / "no-such-opencode")}
        patches = [
            mock.patch.dict(os.environ, env),
            mock.patch.object(ha_run, "_context", self.fake_context),
            mock.patch.object(ha_run, "run_once", self.fake_run_once),
            mock.patch.object(ha_run, "record", self.records.append),
            mock.patch.object(ha_run, "load_doctor", lambda path: self.doctor),
            mock.patch.object(ha_run, "doctor_cache_path", lambda: self.tmp / "doctor.json"),
            mock.patch.object(ha_run, "apply_oracle", _fake_oracle),
            mock.patch.object(ha_run, "config_env",
                              lambda role, audit_rel="": {"OPENCODE_CONFIG_CONTENT": "{\"role\": \"%s\"}" % role}),
            mock.patch("sys.stdout", self.stdout),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def fake_context(self, cwd):
        return {"out": self.out, "repo": self.repo, "cfg": self.cfg, "state": self.state}

    def fake_run_once(self, cmd, cwd, env, out_path, err_path, stall_s, timeout_s):
        self.calls.append({"cmd": list(cmd), "cwd": cwd, "env": env, "out": out_path, "err": err_path,
                           "stall_s": stall_s, "timeout_s": timeout_s})
        return self.script.pop(0) if self.script else _result(text="")

    def read_rows(self, path):
        return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]

    def event(self, name):
        return json.loads((self.out / "events" / (name + ".json")).read_text(encoding="utf-8"))

    def lines(self):
        return self.stdout.getvalue().splitlines()

    def oc_lines(self):
        return [ln for ln in self.lines() if ln.startswith(("OC-ERROR", "OC-WARN"))]

    def line(self):
        return self.lines()[-1]

    def errors_log(self):
        path = self.out / "oc-errors.jsonl"
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def assertOcLine(self, line, level, unit, kind):
        pattern = r"^OC-%s\s+hybrid-requirements-code-audit %s tier=std model=%s kind=%s :: " % (
            level, unit, re.escape(SPEC), kind)
        self.assertRegex(line, pattern)

    def fail(self, kind, detail="boom"):
        rc = None if kind == "spawn" else 1
        return _result("", rc=rc, reason=kind, errors=[] if kind in ("spawn", "stall", "timeout") else [detail],
                       note=detail)

    def switched(self):
        return hybrid_shared.run_switched(self.out)



class RunNamedTest(RunBase):
    def test_all_ids_in_round_one(self):
        self.script = [_result(_block("batch-01", [_row("R1"), _row("R2"), _row("R9")]))]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertTrue(res["ok"])
        self.assertEqual(len(self.calls), 1)
        call = self.calls[0]
        cmd = call["cmd"]
        self.assertIn("hybrid-audit-investigator", cmd)
        self.assertEqual(cmd[cmd.index("-f") + 1], str(self.out / "batches" / "batch-01.oc.md"))
        self.assertNotIn("--session", cmd)
        self.assertEqual(call["cwd"], self.repo)
        self.assertEqual(call["env"]["PWD"], str(self.repo))
        self.assertEqual(call["env"]["OPENCODE_CONFIG_CONTENT"], "{\"role\": \"investigator\"}")
        self.assertEqual((call["stall_s"], call["timeout_s"]), (180, 900))
        self.assertEqual(Path(call["out"]), self.out / "oc" / "batch-01.1.jsonl")
        self.assertEqual(Path(call["err"]), self.out / "oc" / "batch-01.1.err")
        rows = self.read_rows(self.out / "findings" / "batch-01.jsonl")
        self.assertEqual([r["id"] for r in rows], ["R1", "R2"])
        self.assertTrue(all(r["backend"] == "oc:std" for r in rows))
        ev = self.event("batch-01")
        self.assertEqual(ev["batch"], "batch-01")
        self.assertIs(ev["ok"], True)
        self.assertIsNone(ev["reason"])
        self.assertEqual(ev["agent_type"], "opencode:hybrid-audit-investigator")
        self.assertEqual(ev["backend"], "oc:std")
        self.assertEqual((ev["rounds"], ev["written"], ev["total"]), (1, 2, 2))
        self.assertIsInstance(ev["t"], float)
        line = self.line()
        self.assertTrue(line.startswith("OC batch-01 oc:std OK 2/2 — 1 rounds — "), line)
        self.assertTrue(line.endswith("s"), line)
        rec = self.records[0]
        self.assertEqual((rec["kind"], rec["name"], rec["role"], rec["tier"]), ("run", "batch-01", "investigator", "std"))
        self.assertEqual((rec["items"], rec["rounds"], rec["round1_valid"]), (2, 1, 2))
        self.assertEqual(rec["outcome"], "ok")
        self.assertEqual(rec["oracle"], {"foreign": 1, "dropped": 0, "demoted": 0, "invalid_status": 0})
        self.assertEqual(rec["tokens"]["input"], 10)
        self.assertEqual(rec["model"], "zai-coding-plan/glm-5.3")
        self.assertEqual(self.oc_lines(), [])
        self.assertFalse((self.out / "state.json").exists())

    def test_repair_turn_fills_only_missing_ids(self):
        self.script = [_result(_block("batch-01", [_row("R1", "first")])),
                       _result(_block("batch-01", [_row("R1", "second"), _row("R2", "second")]))]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertTrue(res["ok"])
        self.assertEqual(len(self.calls), 2)
        repair = self.calls[1]["cmd"]
        self.assertEqual(repair[repair.index("--session") + 1], "ses_1")
        self.assertNotIn("-f", repair)
        rows = {r["id"]: r for r in self.read_rows(self.out / "findings" / "batch-01.jsonl")}
        self.assertEqual(rows["R1"]["notes"], "first")
        self.assertEqual(rows["R2"]["notes"], "second")
        self.assertEqual(self.records[0]["round1_valid"], 1)
        self.assertTrue(self.line().startswith("OC batch-01 oc:std OK 2/2 — 2 rounds — "))

    def test_repair_resent_batch_ids_are_not_foreign(self):
        self.script = [_result(_block("batch-01", [_row("R1", "first")])),
                       _result(_block("batch-01", [_row("R1", "second"), _row("R2", "second"), _row("R9")]))]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertTrue(res["ok"])
        self.assertEqual(self.records[0]["oracle"]["foreign"], 1)
        rows = {r["id"]: r for r in self.read_rows(self.out / "findings" / "batch-01.jsonl")}
        self.assertEqual(rows["R1"]["notes"], "first")

    def test_repair_resent_filled_row_adds_no_oracle_stats(self):
        def missing(rid, notes, evidence):
            return {"id": rid, "status": "MISSING", "evidence": evidence, "notes": notes}
        bad = [{"path": "src/nope.py", "lines": "1-2"}]
        self.script = [_result(_block("batch-01", [missing("R1", "first", [])])),
                       _result(_block("batch-01", [missing("R1", "second", bad), missing("R2", "second", [])]))]
        with mock.patch.object(ha_run, "apply_oracle", ha_run.ha_oracle.apply_oracle):
            res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertTrue(res["ok"])
        self.assertEqual(self.records[0]["oracle"], {"foreign": 0, "dropped": 0, "demoted": 0, "invalid_status": 0})
        rows = {r["id"]: r for r in self.read_rows(self.out / "findings" / "batch-01.jsonl")}
        self.assertEqual(rows["R1"]["notes"], "first")

    def test_list_shaped_state_is_not_read(self):
        self.state["batches"] = [{"name": "batch-01", "ids": ["R1", "R2"], "backend": "oc:std"}]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(res["reason"], "spawn")
        self.assertEqual(self.calls, [])

    def test_format_after_max_repairs_keeps_written_rows(self):
        self.script = [_result(_block("batch-01", [_row("R1")])) for _ in range(5)]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "format")
        self.assertEqual(len(self.calls), 3)
        rows = self.read_rows(self.out / "findings" / "batch-01.jsonl")
        self.assertEqual([r["id"] for r in rows], ["R1"])
        ev = self.event("batch-01")
        self.assertEqual((ev["ok"], ev["reason"], ev["written"], ev["total"], ev["rounds"]), (False, "format", 1, 2, 3))
        self.assertIn("R2", ev["message"])
        self.assertEqual(self.records[0]["outcome"], "partial")
        self.assertTrue(self.line().startswith("OC batch-01 oc:std FALLBACK (format) 1/2 — 3 rounds — "))
        oc = self.oc_lines()
        self.assertEqual(len(oc), 1, oc)
        self.assertOcLine(oc[0], "WARN", "batch-01", "format")
        self.assertEqual(hybrid_shared.breaker_skip(self.out, "std", SPEC), 0)

    def test_no_block_is_format_without_output(self):
        self.script = [_result("I could not do it") for _ in range(3)]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(res["reason"], "format")
        self.assertEqual(len(self.calls), 3)
        self.assertFalse((self.out / "findings" / "batch-01.jsonl").exists())
        self.assertEqual(self.records[0]["outcome"], "fallback")
        self.assertTrue(self.line().startswith("OC batch-01 oc:std FALLBACK (format) 0/2 — 3 rounds — "))

    def test_auth_failure_is_reported_at_once_and_trips_the_breaker(self):
        self.script = [_result("", rc=1, reason="auth", errors=["APIError: subscription expired"],
                               note="APIError: subscription expired")]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(res["reason"], "auth")
        self.assertEqual(len(self.calls), 1)
        self.assertFalse((self.out / "findings" / "batch-01.jsonl").exists())
        ev = self.event("batch-01")
        self.assertEqual((ev["ok"], ev["reason"]), (False, "auth"))
        self.assertIn("expired", ev["message"])
        lines = self.lines()
        self.assertEqual(len(lines), 3, lines)
        self.assertOcLine(lines[0], "ERROR", "batch-01", "auth")
        self.assertIn("expired", lines[0])
        self.assertOcLine(lines[1], "ERROR", "batch-01", "switch")
        self.assertTrue(lines[2].startswith("OC batch-01 oc:std FALLBACK (auth) 0/2 — 1 rounds — "))
        self.assertIn("kind=auth", self.errors_log())
        self.assertGreater(hybrid_shared.breaker_skip(self.out, "std", SPEC), 0)

    def test_open_breaker_never_spawns_and_stays_quiet(self):
        hybrid_shared.breaker_trip(self.out, "std", SPEC, "auth", "401 Unauthorized")
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(res["reason"], "breaker")
        self.assertEqual(self.calls, [])
        ev = self.event("batch-01")
        self.assertEqual((ev["ok"], ev["reason"], ev["rounds"]), (False, "breaker", 0))
        self.assertEqual(self.oc_lines(), [])
        self.assertTrue(self.line().startswith("OC batch-01 oc:std FALLBACK (breaker) 0/2 — 0 rounds — "))

    def test_throttle_is_reported_without_tripping_the_breaker(self):
        self.script = [self.fail("throttle", "APIError: 429 Too Many Requests") for _ in range(4)]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(res["reason"], "throttle")
        oc = self.oc_lines()
        self.assertOcLine(oc[3], "ERROR", "batch-01", "throttle")
        self.assertEqual(hybrid_shared.breaker_skip(self.out, "std", SPEC), 0)

    def test_spawn_failure_is_reported(self):
        self.script = [_result("", rc=None, reason="spawn", note="spawn failed: no such file") for _ in range(4)]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(res["reason"], "spawn")
        oc = self.oc_lines()
        self.assertOcLine(oc[3], "ERROR", "batch-01", "spawn")
        self.assertIn("no such file", oc[3])

    def test_recovered_exit_is_accepted_with_a_warning(self):
        self.script = [_result(_block("batch-01", [_row("R1"), _row("R2")]), rc=1, reason="recovered",
                               errors=["StepError: tool call failed, step recovered"])]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertTrue(res["ok"])
        self.assertEqual(len(self.calls), 1)
        oc = self.oc_lines()
        self.assertEqual(len(oc), 1, oc)
        self.assertOcLine(oc[0], "WARN", "batch-01", "recovered")
        self.assertTrue(self.line().startswith("OC batch-01 oc:std OK 2/2 — 1 rounds — "))
        self.assertEqual(hybrid_shared.breaker_skip(self.out, "std", SPEC), 0)

    def test_empty_reply_warns_then_repairs(self):
        self.script = [_result(""), _result(_block("batch-01", [_row("R1"), _row("R2")]))]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertTrue(res["ok"])
        self.assertEqual(len(self.calls), 2)
        oc = self.oc_lines()
        self.assertEqual(len(oc), 1, oc)
        self.assertOcLine(oc[0], "WARN", "batch-01", "empty")

    def test_oracle_drops_and_demotes_are_warned(self):
        def oracle(rows, ids, repo, role, audit_dir=None):
            kept = [r for r in rows if r.get("id") in ids]
            return kept, {"foreign": 0, "dropped": 2, "demoted": 1, "invalid_status": 0, "problems": []}

        self.script = [_result(_block("batch-01", [_row("R1"), _row("R2")]))]
        with mock.patch.object(ha_run, "apply_oracle", oracle):
            res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertTrue(res["ok"])
        oc = self.oc_lines()
        self.assertEqual(len(oc), 1, oc)
        self.assertOcLine(oc[0], "WARN", "batch-01", "oracle")
        self.assertIn("dropped 2", oc[0])
        self.assertIn("demoted 1", oc[0])

    def test_tier_comes_from_the_router_when_the_state_has_no_backend(self):
        self.state["batches"]["batch-01"]["backend"] = ""
        self.script = [_result(_block("batch-01", [_row("R1"), _row("R2")]))]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertTrue(res["ok"])
        self.assertEqual(res["tier"], "std")

    def test_cooldown_never_spawns(self):
        self.state["cooldown"] = {"std": time.time() + 600}
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(res["reason"], "cooldown")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.event("batch-01")["reason"], "cooldown")

    def test_verifier_batch(self):
        verdict = {"id": "R1", "verified_status": "MATCHED", "reason": "checked"}
        self.script = [_result(_block("batch-V01", [verdict]))]
        res = ha_run.run_named(str(self.repo), "batch-V01")
        self.assertTrue(res["ok"])
        cmd = self.calls[0]["cmd"]
        self.assertIn("hybrid-audit-verifier", cmd)
        self.assertEqual(cmd[cmd.index("-f") + 1], str(self.out / "verify" / "batch-V01.oc.md"))
        rows = self.read_rows(self.out / "verify" / "batch-V01.jsonl")
        self.assertEqual([(r["id"], r["backend"]) for r in rows], [("R1", "oc:std")])
        self.assertEqual(self.event("batch-V01")["agent_type"], "opencode:hybrid-audit-verifier")

    def test_parser_section(self):
        items = [{"id": "R1", "text": "Users can log in"}, {"id": "R2", "text": "Users can log out"}]
        self.script = [_result(_block("section-01", items))]
        res = ha_run.run_named(str(self.repo), "section-01")
        self.assertTrue(res["ok"])
        self.assertIn("hybrid-audit-parser", self.calls[0]["cmd"])
        rows = self.read_rows(self.out / "parse" / "section-01.jsonl")
        self.assertEqual([r["id"] for r in rows], ["R1", "R2"])
        ev = self.event("section-01")
        self.assertEqual((ev["ok"], ev["total"], ev["written"]), (True, 0, 2))
        self.assertTrue(self.line().startswith("OC section-01 oc:std OK 2/0 — 1 rounds — "))

    def test_parser_parse_error_triggers_repair(self):
        good = {"id": "R1", "text": "Users can log in"}
        self.script = [_result(_block("section-01", [json.dumps(good), "not json"])),
                       _result(_block("section-01", [good]))]
        res = ha_run.run_named(str(self.repo), "section-01")
        self.assertTrue(res["ok"])
        self.assertEqual(len(self.calls), 2)
        self.assertIn("--session", self.calls[1]["cmd"])

    def test_unknown_name_is_spawn(self):
        res = ha_run.run_named(str(self.repo), "notes")
        self.assertEqual(res["reason"], "spawn")
        self.assertEqual(self.calls, [])
        self.assertIn("FALLBACK (spawn)", self.line())
        oc = self.oc_lines()
        self.assertEqual(len(oc), 1, oc)
        self.assertRegex(oc[0], r"^OC-ERROR\s+hybrid-requirements-code-audit notes tier=none model=none kind=spawn :: ")

    def test_context_error_still_reports_and_prints_the_summary(self):
        def broken(cwd):
            raise RuntimeError("no audit here")
        with mock.patch.object(ha_run, "_context", broken):
            res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(res["reason"], "crash")
        self.assertIn("no audit here", res["message"])
        oc = self.oc_lines()
        self.assertEqual(len(oc), 1, oc)
        self.assertRegex(oc[0], r"^OC-ERROR\s+hybrid-requirements-code-audit batch-01 tier=none model=none kind=crash :: ")
        self.assertTrue(self.line().startswith("OC batch-01 oc:none FALLBACK (crash) 0/0 — 0 rounds — "))


class RetryAndSwitchTest(RunBase):
    """Connection failures retry a fresh run three times; then a hybrid run switches to Claude sonnet."""

    def good(self):
        return _result(_block("batch-01", [_row("R1"), _row("R2")]))

    def sessions(self):
        return [c["cmd"][c["cmd"].index("--session") + 1] if "--session" in c["cmd"] else "" for c in self.calls]

    def test_retry_then_success_needs_no_switch(self):
        self.script = [self.fail("stall", "stall: no event for 180s"), self.good()]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertTrue(res["ok"])
        self.assertEqual(res["rounds"], 1)
        self.assertEqual(self.sessions(), ["", ""])
        self.assertEqual(self.calls[0]["cmd"], self.calls[1]["cmd"])
        oc = self.oc_lines()
        self.assertEqual(len(oc), 1, oc)
        self.assertOcLine(oc[0], "WARN", "batch-01", "stall")
        self.assertIn(":: retry 1/3 in 0s: stall: no event for 180s", oc[0])
        self.assertIn("kind=stall", self.errors_log())
        self.assertEqual(self.switched(), {})
        self.assertEqual(hybrid_shared.breaker_skip(self.out, "std", SPEC), 0)

    def test_three_retries_then_the_run_switches_to_claude(self):
        self.script = [self.fail("throttle", "429 Too Many Requests") for _ in range(5)]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "throttle")
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(self.sessions(), ["", "", "", ""])
        oc = self.oc_lines()
        self.assertEqual(len(oc), 5, oc)
        for n in (1, 2, 3):
            self.assertOcLine(oc[n - 1], "WARN", "batch-01", "throttle")
            self.assertIn(":: retry %d/3 in 0s: " % n, oc[n - 1])
        self.assertOcLine(oc[3], "ERROR", "batch-01", "throttle")
        self.assertOcLine(oc[4], "ERROR", "batch-01", "switch")
        self.assertIn("opencode throttle: 429 Too Many Requests; the rest of this run uses Claude sonnet", oc[4])
        self.assertEqual(self.lines()[-2], oc[4])
        self.assertTrue(self.line().startswith("OC batch-01 oc:std FALLBACK (throttle) 0/2 — 1 rounds — "))
        self.assertEqual(self.errors_log().count("kind=switch"), 1)
        entry = self.switched()
        self.assertEqual((entry["unit"], entry["kind"], entry["tier"], entry["spec"]), ("batch-01", "throttle", "std", SPEC))
        self.assertEqual(self.event("batch-01")["reason"], "throttle")

    def test_retry_delays_follow_the_shared_schedule(self):
        self.script = [self.fail("crash", "exit 1: boom") for _ in range(4)]
        with mock.patch.dict(os.environ, {"HYBRID_OC_RETRY_DELAY_S": ""}), \
                mock.patch.object(ha_run.time, "sleep") as sleep:
            ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual([c[0][0] for c in sleep.call_args_list], [10, 30, 60])
        self.assertIn("retry 3/3 in 60s", self.oc_lines()[2])

    def test_auth_switches_at_once_without_a_retry(self):
        self.script = [self.fail("auth", "APIError: 401 Unauthorized"), self.good()]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(res["reason"], "auth")
        self.assertEqual(len(self.calls), 1)
        oc = self.oc_lines()
        self.assertEqual(len(oc), 2, oc)
        self.assertOcLine(oc[0], "ERROR", "batch-01", "auth")
        self.assertOcLine(oc[1], "ERROR", "batch-01", "switch")
        self.assertEqual(self.switched()["kind"], "auth")
        self.assertGreater(hybrid_shared.breaker_skip(self.out, "std", SPEC), 0)

    def test_timeout_and_context_never_retry_or_switch(self):
        for kind in ("timeout", "context"):
            self.script = [self.fail(kind, kind + " problem"), self.good()]
            del self.calls[:]
            res = ha_run.run_named(str(self.repo), "batch-01")
            self.assertEqual(res["reason"], kind)
            self.assertEqual(len(self.calls), 1, kind)
            self.assertFalse(any("retry" in ln or "kind=switch" in ln for ln in self.oc_lines()), kind)
            self.assertEqual(self.switched(), {}, kind)

    def test_format_failure_keeps_its_repair_turns_and_never_switches(self):
        self.script = [_result(_block("batch-01", [_row("R1")])) for _ in range(5)]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(res["reason"], "format")
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(self.switched(), {})

    def test_a_retried_repair_turn_continues_the_last_good_session_not_the_failed_one(self):
        self.script = [_result(_block("batch-01", [_row("R1")]), session="ses_good"),
                       dict(self.fail("stall", "stall: no event"), session="ses_failed"),
                       self.good()]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertTrue(res["ok"])
        self.assertEqual(self.sessions(), ["", "ses_good", "ses_good"])
        self.assertEqual(res["rounds"], 2)

    def test_units_after_the_switch_never_spawn_opencode_and_print_nothing(self):
        hybrid_shared.switch_to_claude(self.out, "batch-01", "std", SPEC, "auth", "401 Unauthorized")
        for name, role in (("batch-01", "investigator"), ("batch-V01", "verifier"), ("section-01", "parser")):
            res = ha_run.run_named(str(self.repo), name)
            self.assertEqual(res["reason"], "switched", name)
            self.assertFalse(res["ok"])
        self.assertEqual(self.calls, [])
        self.assertEqual(self.oc_lines(), [])
        self.assertEqual(self.errors_log(), "")
        self.assertEqual(self.event("batch-01")["reason"], "switched")
        self.assertEqual(hybrid_shared.breaker_skip(self.out, "std", SPEC), 0)
        self.assertTrue(self.line().startswith("OC section-01 oc:std FALLBACK (switched) 0/0 — 0 rounds — "))

    def test_preset_opencode_retries_then_stays_held_without_a_switch(self):
        self.cfg["preset"] = "opencode"
        self.script = [self.fail("throttle", "429 Too Many Requests") for _ in range(5)]
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(res["reason"], "throttle")
        self.assertEqual(len(self.calls), 4)
        oc = self.oc_lines()
        self.assertEqual(len(oc), 4, oc)
        self.assertEqual([("WARN", "ERROR")[i == 3] for i in range(4)], [ln.split()[0][3:] for ln in oc])
        self.assertFalse(any("kind=switch" in ln for ln in oc))
        self.assertEqual(self.switched(), {})

    def test_preset_opencode_auth_never_switches(self):
        self.cfg["preset"] = "opencode"
        self.script = [self.fail("auth", "401 Unauthorized")]
        ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(self.switched(), {})
        self.assertFalse(any("kind=switch" in ln for ln in self.oc_lines()))

    def test_failures_before_any_opencode_run_do_not_switch(self):
        self.state["batches"]["batch-01"]["ids"] = []
        res = ha_run.run_named(str(self.repo), "batch-01")
        self.assertEqual(res["reason"], "spawn")
        self.assertEqual(self.switched(), {})
