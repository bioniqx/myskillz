import concurrent.futures
import importlib.util
import os
import sys
import threading
import time
import unittest
from unittest import mock

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

    def test_shared_pool_never_exceeds_eight_in_flight_jobs(self):
        live = [0]
        peak = [0]
        lock = threading.Lock()

        def judge_fn(item):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.005)
            with lock:
                live[0] -= 1
            return ({"id": item}, None)

        def verify_fn(item, row):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.005)
            with lock:
                live[0] -= 1
            return ({"verdict_for": item}, None)

        fan = RecordingFan(workers=8)
        self._pipeline(list(range(40)), fan, lambda it, row: True,
                       judge_fn=judge_fn, verify_fn=verify_fn)
        fan.shutdown()

        self.assertLessEqual(peak[0], 8)

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


if __name__ == "__main__":
    unittest.main()
