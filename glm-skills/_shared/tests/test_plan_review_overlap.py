import importlib.util
import inspect
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "glm-writing-plans", "scripts", "plan_tool.py")


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_review_overlap", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()


def _cmd_build_source():
    return inspect.getsource(plan_tool.cmd_build)


class ReviewBudgetGateTests(unittest.TestCase):
    """The shared Budget and the no-review flag gate every overlapped submission."""

    def test_every_review_submission_sits_behind_the_budget_gate(self):
        src = _cmd_build_source()
        sites = list(re.finditer(r"review_one\(", src))
        self.assertTrue(sites, "cmd_build submits no review at all")
        for m in sites:
            window = src[max(0, m.start() - 300):m.start()]
            self.assertIn(
                "budget.blown()",
                window,
                "review_one call at offset %d is not gated by Budget.blown()" % m.start(),
            )

    def test_every_review_submission_honors_no_review(self):
        src = _cmd_build_source()
        sites = list(re.finditer(r"review_one\(", src))
        self.assertTrue(sites, "cmd_build submits no review at all")
        for m in sites:
            window = src[max(0, m.start() - 300):m.start()]
            self.assertIn(
                "no_review",
                window,
                "review_one call at offset %d ignores the no-review flag" % m.start(),
            )

    def test_review_results_are_collected_in_a_mapping(self):
        src = _cmd_build_source()
        self.assertIn("review_results = {}", src)
        self.assertIn("review_results[", src)


class ReviewOverlapTests(unittest.TestCase):
    """Review submission moved from after the writer wave into it."""

    def test_submission_at_write_completion_and_consumption_after_the_wave(self):
        src = _cmd_build_source()
        submit = src.index("review_results[")
        consume = src.index("review_results.get(")
        self.assertLess(
            submit,
            consume,
            "review submission must be written before the post-wave consumption reads it",
        )

    def test_submission_follows_both_marks(self):
        src = _cmd_build_source()
        ok = src.index(".ok")
        warn = src.index(".warn")
        submit = src.index("review_results[")
        self.assertLess(
            ok,
            submit,
            "review must be submitted only after the .ok mark is written",
        )
        self.assertLess(
            warn,
            submit,
            "review must be submitted only after the .warn signal it reads is written",
        )


if __name__ == "__main__":
    unittest.main()
