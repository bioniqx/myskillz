import importlib.util
import inspect
import os
import threading
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "glm-writing-plans", "scripts", "plan_tool.py")


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_brief_under_test", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()


class RunReconContractTests(unittest.TestCase):
    def test_run_recon_maps_step_names_to_results_in_original_order(self):
        steps = [
            ("git", lambda: "log-output"),
            ("status", lambda: "status-output"),
            ("spec", lambda: "spec-body"),
        ]
        result = plan_tool.run_recon(steps)
        self.assertIsInstance(result, dict)
        self.assertEqual(result, {"git": "log-output", "status": "status-output", "spec": "spec-body"})
        self.assertEqual(list(result), ["git", "status", "spec"])

    def test_run_recon_signature_is_exact(self):
        with open(PLAN_TOOL, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("def run_recon(steps) -> dict:", text)


class RunReconConcurrencyTests(unittest.TestCase):
    def test_run_recon_runs_steps_concurrently(self):
        barrier = threading.Barrier(3, timeout=10)

        def waiter(value):
            barrier.wait()
            return value

        steps = [
            ("one", lambda: waiter(1)),
            ("two", lambda: waiter(2)),
            ("three", lambda: waiter(3)),
        ]
        result = plan_tool.run_recon(steps)
        self.assertEqual(result, {"one": 1, "two": 2, "three": 3})

    def test_run_recon_never_exceeds_eight_in_flight(self):
        live, peak, lock = [0], [0], threading.Lock()

        def probe():
            with lock:
                live[0] += 1
                peak[0] = max(peak[0], live[0])
            time.sleep(0.02)
            with lock:
                live[0] -= 1
            return True

        steps = [("step%02d" % i, probe) for i in range(24)]
        result = plan_tool.run_recon(steps)
        self.assertEqual(len(result), 24)
        self.assertLessEqual(peak[0], 8)


class CmdBriefWiringTests(unittest.TestCase):
    def test_cmd_brief_calls_run_recon(self):
        source = inspect.getsource(plan_tool.cmd_brief)
        self.assertIn("run_recon(", source)


if __name__ == "__main__":
    unittest.main()
