"""Spec 2026-11-25: plan_tool.py doctor prints the effort each tier sets."""
import argparse
import contextlib
import importlib.util
import io
import os
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "z-writing-plans", "scripts", "plan_tool.py")


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_doctor_under_test", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()


class DoctorModelsRow(unittest.TestCase):
    def _row(self):
        buf = io.StringIO()
        fake = mock.patch.object(plan_tool, "find_credentials", return_value=(None, "", "", ""))
        with fake, contextlib.redirect_stdout(buf):
            code = plan_tool.cmd_doctor(argparse.Namespace(ping=False))
        self.assertEqual(code, 1, "no key means doctor exits 1")
        rows = [ln for ln in buf.getvalue().splitlines() if ln.startswith("models")]
        self.assertEqual(len(rows), 1, buf.getvalue())
        return rows[0]

    def test_row_prints_the_effort_each_tier_sets(self):
        row = self._row()
        for tier in ("light", "std", "deep"):
            model, effort = plan_tool.GLM[tier][0], plan_tool.GLM[tier][1]
            with self.subTest(tier=tier):
                self.assertIn("%s=%s/%s" % (tier, model, effort), row)

    def test_row_does_not_hardcode_a_low_light_tier(self):
        self.assertEqual(plan_tool.GLM["light"][1], "high")
        self.assertNotIn("light=%s/low" % plan_tool.GLM["light"][0], self._row())


if __name__ == "__main__":
    unittest.main()
