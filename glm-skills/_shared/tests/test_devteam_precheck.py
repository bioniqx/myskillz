import importlib.util
import inspect
import os
import threading
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
DEVTEAM = os.path.join(HERE, "..", "..", "glm-dev-team", "scripts", "devteam.py")


def _load_devteam():
    spec = importlib.util.spec_from_file_location("devteam_under_test", DEVTEAM)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


devteam = _load_devteam()


def _devteam_text():
    with open(DEVTEAM, encoding="utf-8") as fh:
        return fh.read()


def _function_source(text, name):
    start = text.index("def %s(" % name)
    end = text.find("\ndef ", start + 1)
    if end == -1:
        end = len(text)
    return text[start:end]


class TestPrecheckOneContract(unittest.TestCase):
    def test_precheck_one_exists_with_exact_signature(self):
        self.assertTrue(callable(devteam.precheck_one))
        self.assertEqual(
            list(inspect.signature(devteam.precheck_one).parameters), ["c", "sl"]
        )

    def test_precheck_one_body_is_read_only(self):
        body = _function_source(_devteam_text(), "precheck_one")
        for banned in ("save_state(", "state_lock", "merge_slice(", "reject("):
            self.assertNotIn(banned, body,
                             "precheck_one must stay read-only: %s found" % banned)


class TestPrecheckConcurrency(unittest.TestCase):
    def test_precheck_all_runs_slices_concurrently_capped_at_eight(self):
        live = [0]
        peak = [0]
        lock = threading.Lock()

        def fake_precheck(c, sl):
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.01)
            with lock:
                live[0] -= 1
            return {"slice": sl}

        with mock.patch.object(devteam, "precheck_one", fake_precheck):
            devteam.precheck_all({}, list(range(40)))
        self.assertLessEqual(peak[0], 8)
        self.assertGreater(peak[0], 1)

    def test_precheck_all_preserves_slice_order(self):
        def fake_precheck(c, sl):
            return {"slice": sl}

        with mock.patch.object(devteam, "precheck_one", fake_precheck):
            out = devteam.precheck_all({}, list(range(12)))
        self.assertEqual(out, [{"slice": n} for n in range(12)])


class TestIntegrateStructure(unittest.TestCase):
    def test_do_integrate_prechecks_before_the_integration_loop(self):
        body = _function_source(_devteam_text(), "do_integrate")
        self.assertIn("precheck_all(", body,
                      "do_integrate must run precheck_all before the integration loop")
        self.assertIn("integrate_one(", body,
                      "do_integrate must still call integrate_one for every slice")
        self.assertLess(body.index("precheck_all("), body.index("integrate_one("),
                        "prechecks must complete before the first integrate_one call")

    def test_integrate_one_gains_a_trailing_pc_parameter(self):
        params = list(inspect.signature(devteam.integrate_one).parameters)
        self.assertEqual(params[-1], "pc",
                         "integrate_one must receive its precheck result as a trailing pc param")


class TestBranchMissingReject(unittest.TestCase):
    def test_missing_tip_rejects_instead_of_raising(self):
        st = {"slices": {"S1": {"status": "inflight", "mode": "work", "kind": "chore",
                                "base_sha": "0" * 40, "files": ["a.txt"],
                                "history": [], "rejected": None}}}
        pc = {"claim": {"worktree": "/tmp/gone", "branch": "nosuch", "base": None}}
        msg = devteam.integrate_one("/tmp", st, "S1", pc=pc)
        self.assertIn("branch nosuch not found", msg)
        self.assertIn("retry S1", msg)


if __name__ == "__main__":
    unittest.main()
