import concurrent.futures
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT = os.path.join(HERE, "..", "..", "glm-requirements-code-audit", "scripts", "audit.py")
SCRIPTS = os.path.dirname(AUDIT)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


def _load_audit():
    spec = importlib.util.spec_from_file_location("audit_under_test", AUDIT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


audit = _load_audit()


class RecordingFan:
    """Fan stand-in for tests: real worker threads plus an ordered submit log."""

    def __init__(self, workers=8):
        self.log = []
        self.lock = threading.Lock()
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=workers)

    def submit(self, fn, *args):
        with self.lock:
            self.log.append((fn.__name__,) + args)
        return self.pool.submit(fn, *args)

    def shutdown(self):
        self.pool.shutdown(wait=True)


class PipelineTests(unittest.TestCase):
    @staticmethod
    def _pipeline(items, fan, should_verify, judge_fn=None, verify_fn=None,
                  warm_judge=None, warm_verify=None):
        if judge_fn is None:
            def judge_fn(it):
                return ({"id": it}, None)
        if verify_fn is None:
            def verify_fn(it, row):
                return ({"verdict_for": it}, None)
        return audit.run_judge_verify_pipeline(
            items, judge_fn, verify_fn,
            should_verify, fan, warm_judge=warm_judge, warm_verify=warm_verify)

    def test_verify_is_submitted_while_the_judge_tail_is_still_running(self):
        judge_a_may_finish = threading.Event()
        observed = {"verify_ran_while_a_blocked": False, "a_judge_timed_out": False}

        def judge_fn(item):
            if item != "a":
                return ({"id": item}, None)
            if not judge_a_may_finish.wait(timeout=5):
                observed["a_judge_timed_out"] = True
            return ({"id": item}, None)

        def verify_fn(item, row):
            if item == "b":
                observed["verify_ran_while_a_blocked"] = not judge_a_may_finish.is_set()
                judge_a_may_finish.set()
            return ({"verdict_for": item}, None)

        fan = RecordingFan()
        findings, verdicts = self._pipeline(
            ["a", "b", "c"], fan, lambda it, row: True,
            judge_fn=judge_fn, verify_fn=verify_fn)
        fan.shutdown()

        self.assertFalse(observed["a_judge_timed_out"])
        self.assertTrue(observed["verify_ran_while_a_blocked"])
        self.assertEqual([entry[0] for entry in fan.log[:3]],
                         ["judge_fn", "judge_fn", "judge_fn"])
        self.assertEqual([f[0]["id"] for f in findings], ["a", "b", "c"])
        self.assertEqual([v[0]["verdict_for"] for v in verdicts],
                         ["a", "b", "c"])

    def test_items_where_should_verify_is_false_produce_no_verify_jobs(self):
        def verify_fn(item, row):
            raise AssertionError("no verify job may run when should_verify is False")

        fan = RecordingFan()
        findings, verdicts = self._pipeline(["a", "b"], fan, lambda it, row: False,
                                            verify_fn=verify_fn)
        fan.shutdown()

        self.assertEqual([f[0]["id"] for f in findings], ["a", "b"])
        self.assertEqual(verdicts, [None, None])
        self.assertTrue(all(entry[0] == "judge_fn" for entry in fan.log))

    def test_warm_ups_fire_once_before_their_first_submission(self):
        order = []

        def judge_fn(item):
            order.append(("judge", item))
            return ({"id": item}, None)

        def verify_fn(item, row):
            order.append(("verify", item))
            return ({"verdict_for": item}, None)

        fan = RecordingFan()
        self._pipeline(["a", "b"], fan, lambda it, row: True,
                       judge_fn=judge_fn, verify_fn=verify_fn,
                       warm_judge=lambda: order.append("warm_judge"),
                       warm_verify=lambda: order.append("warm_verify"))
        fan.shutdown()

        self.assertEqual(order[0], "warm_judge")
        verify_positions = [i for i, entry in enumerate(order)
                            if isinstance(entry, tuple) and entry[0] == "verify"]
        self.assertTrue(verify_positions)
        self.assertLess(order.index("warm_verify"), min(verify_positions))
        self.assertEqual(order.count("warm_judge"), 1)
        self.assertEqual(order.count("warm_verify"), 1)

    def test_every_job_flows_through_the_fan_pool(self):
        fan = RecordingFan()
        findings, verdicts = self._pipeline(
            list("abcdef"), fan, lambda it, row: it in "bc")
        fan.shutdown()

        kinds = [entry[0] for entry in fan.log]
        self.assertEqual(kinds.count("judge_fn"), 6)
        self.assertEqual(kinds.count("verify_fn"), 2)
        self.assertEqual([f[0]["id"] for f in findings], list("abcdef"))
        self.assertEqual([v[0]["verdict_for"] if v else None for v in verdicts],
                         [None, "b", "c", None, None, None])

    def test_api_errors_travel_as_error_rows_not_exceptions(self):
        def judge_fn(item):
            if item == "b":
                return (None, "api error: 429")
            return ({"id": item}, None)

        def verify_fn(item, row):
            if row is None:
                raise AssertionError("an error row must not be verified")
            return ({"verdict_for": item}, None)

        fan = RecordingFan()
        findings, verdicts = self._pipeline(
            ["a", "b"], fan, lambda it, row: True,
            judge_fn=judge_fn, verify_fn=verify_fn)
        fan.shutdown()

        self.assertEqual(findings[0], ({"id": "a"}, None))
        self.assertEqual(findings[1], (None, "api error: 429"))
        self.assertEqual([v[0]["verdict_for"] for v in verdicts[:1]], ["a"])
        self.assertIsNone(verdicts[1])


class PipelineRobustnessTests(unittest.TestCase):
    def test_warm_up_failure_degrades_to_a_warning(self):
        def boom():
            raise RuntimeError("api error: 500")

        fan = RecordingFan()
        findings, verdicts = PipelineTests._pipeline(
            ["a", "b"], fan, lambda it, row: True, warm_judge=boom, warm_verify=boom)
        fan.shutdown()

        self.assertEqual([f[0]["id"] for f in findings], ["a", "b"])
        self.assertEqual([v[0]["verdict_for"] for v in verdicts], ["a", "b"])


class ResumeSelectionTests(unittest.TestCase):
    def test_should_verify_item_ignores_prior_verdicts(self):
        it = {"id": "R1", "stakes": "normal", "strength": "SHOULD"}
        row = {"status": "MATCHED", "confidence": "medium"}
        self.assertTrue(audit.should_verify_item(False, it, row),
                        "a fresh re-judge must get its adversarial pass even with a stale verdict")
        self.assertFalse(audit.should_verify_item(True, it, row))
        settled = {"status": "MATCHED", "confidence": "high", "passes": 2}
        self.assertFalse(audit.should_verify_item(False, it, settled))

    def test_residual_covers_settled_ids_without_this_runs_verdict(self):
        live, verdicts = ["R2"], {"R2"}
        self.assertEqual(audit.residual_verify_ids(["R1", "R2", "R3"], live, verdicts),
                         ["R1", "R3"])
        self.assertEqual(audit.residual_verify_ids(["R2"], live, verdicts), [])


class AdjudicateFinalizeTests(unittest.TestCase):
    """`adjudicate --finalize` folds the finalize call into adjudication."""

    ITEM = {"text": "The system MUST do REQ-001", "strength": "MUST", "stakes": "normal",
            "category": "core", "search_hints": ["alpha"], "tags": []}

    def setUp(self):
        self.root = os.path.realpath(tempfile.mkdtemp(prefix="glm-audit-fin-"))
        self.addCleanup(shutil.rmtree, self.root, True)
        self.repo = os.path.join(self.root, "repo")
        self.out = os.path.join(self.repo, ".audit")
        for sub in ("findings", "verify", "batches", "spec"):
            os.makedirs(os.path.join(self.out, sub))
        src = os.path.join(self.repo, "src")
        os.makedirs(src)
        with io.open(os.path.join(src, "a.py"), "w", encoding="utf-8") as fh:
            fh.write("".join("line %d\n" % n for n in range(1, 41)))
        cfg = {"version": audit.VERSION, "active": True, "repo_root": self.repo,
               "out_dir": self.out, "spec_files": ["spec.md"], "lang": "en", "lane": "api",
               "tier": "std", "threads": 4, "retrieval": "python",
               "models": {"judge": list(audit.TIERS["std"]["judge"]),
                          "verify": list(audit.TIERS["std"]["verify"])}}
        self.write(os.path.join(self.out, "config.json"), json.dumps(cfg))
        self.checklist([dict(self.ITEM, id="REQ-001")])
        self.write(os.path.join(self.out, "findings.jsonl"), json.dumps({
            "id": "REQ-001", "status": "MATCHED", "confidence": "high",
            "evidence": [{"path": "src/a.py", "lines": "1-5", "note": "n"}],
            "searched": ["alpha"], "notes": "n"}) + "\n")

    def write(self, path, text):
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def checklist(self, rows):
        self.write(os.path.join(self.out, "checklist.jsonl"),
                   "".join(json.dumps(r) + "\n" for r in rows))

    def plan(self, rows):
        self.write(os.path.join(self.out, "plan.jsonl"),
                   "".join(json.dumps(r) + "\n" for r in rows))

    def run_cli(self, *args):
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.pop("AUDIT_DIR", None)
        return subprocess.run(
            [sys.executable, AUDIT, "--out", self.out] + list(args),
            cwd=self.repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", errors="replace")

    def test_with_plan_and_rows_it_reports_and_closes_in_the_same_run(self):
        self.plan([{"ids": ["REQ-001"], "title": "t", "priority": "P2", "effort": "S",
                    "target": "x"}])
        r = self.run_cli("adjudicate", "--set", "REQ-001", "MATCHED", "--note", "n",
                         "--finalize")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("recorded REQ-001 = MATCHED", r.stdout)
        self.assertIn("GATE: PASS", r.stdout)
        self.assertIn("AUDIT CLOSED  1 requirements", r.stdout)
        self.assertTrue(os.path.exists(
            os.path.join(self.out, "glm-requirements-code-audit.md")))

    def test_without_plan_jsonl_it_prints_the_hint_and_no_report(self):
        r = self.run_cli("adjudicate", "--set", "REQ-001", "MATCHED", "--finalize")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("recorded REQ-001 = MATCHED", r.stdout)
        self.assertIn("plan.jsonl", r.stdout)
        self.assertIn("NEXT after that: audit.py finalize", r.stdout)
        self.assertNotIn("GATE:", r.stdout)
        self.assertNotIn("AUDIT CLOSED", r.stdout)
        self.assertFalse(os.path.exists(
            os.path.join(self.out, "glm-requirements-code-audit.md")))

    def test_without_the_flag_adjudicate_only_records(self):
        self.plan([{"ids": ["REQ-001"], "title": "t", "priority": "P2", "effort": "S",
                    "target": "x"}])
        r = self.run_cli("adjudicate", "--set", "REQ-001", "MATCHED")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("recorded REQ-001 = MATCHED", r.stdout)
        self.assertNotIn("GATE:", r.stdout)
        self.assertNotIn("AUDIT CLOSED", r.stdout)
        self.assertFalse(os.path.exists(
            os.path.join(self.out, "glm-requirements-code-audit.md")))

    def test_a_failing_gate_still_stops_the_finalization(self):
        self.checklist([dict(self.ITEM, id="REQ-001"),
                        dict(self.ITEM, id="REQ-002", search_hints=["beta"])])
        self.plan([{"ids": ["REQ-001"], "title": "t", "priority": "P2", "effort": "S",
                    "target": "x"}])
        r = self.run_cli("adjudicate", "--set", "REQ-001", "MATCHED", "--finalize")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("REQ-002 is still unsettled", r.stdout)
        self.assertIn("GATE: FAIL", r.stdout)
        self.assertIn("finalize stopped at the gate", r.stdout)
        self.assertNotIn("AUDIT CLOSED", r.stdout)


if __name__ == "__main__":
    unittest.main()
