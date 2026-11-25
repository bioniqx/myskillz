"""Spec 2026-11-25: plan_tool.py doctor prints the effort, the model ids the pin selects and
the key the pinned provider reads."""
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
TIERS = ("light", "std", "deep")


def doctor_output(case, pin):
    """doctor's stdout with no key found, under one pin word; the exit code must be 1."""
    buf = io.StringIO()
    fake = mock.patch.object(plan_tool, "find_credentials", return_value=(None, "", "", ""))
    with mock.patch.dict(os.environ, {"GLM_FLASH": pin}), fake, contextlib.redirect_stdout(buf):
        code = plan_tool.cmd_doctor(argparse.Namespace(ping=False))
    case.assertEqual(code, 1, "no key means doctor exits 1")
    return buf.getvalue()


def models_row(case, pin):
    rows = [ln for ln in doctor_output(case, pin).splitlines() if ln.startswith("models")]
    case.assertEqual(len(rows), 1, "doctor prints exactly one models row")
    return rows[0]


class DoctorModelsRow(unittest.TestCase):
    def test_row_prints_the_effort_each_tier_sets(self):
        row = models_row(self, "glm")
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIn("%s=%s/%s" % (tier, plan_tool.GLM[tier][0], plan_tool.GLM[tier][1]), row)

    def test_row_does_not_hardcode_a_low_light_tier(self):
        self.assertEqual(plan_tool.GLM["light"][1], "high")
        self.assertNotIn("light=%s/low" % plan_tool.GLM["light"][0], models_row(self, "glm"))

    def test_row_prints_the_ids_a_deepseek_pin_selects(self):
        row = models_row(self, "deepseek")
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIn("%s=deepseek-flash/%s" % (tier, plan_tool.GLM[tier][1]), row)

    def test_row_prints_the_id_a_pro_pin_selects(self):
        row = models_row(self, "glm-5.4")
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIn("%s=glm-5.4/%s" % (tier, plan_tool.GLM[tier][1]), row)

    def test_an_unknown_pin_word_keeps_the_table_ids(self):
        row = models_row(self, "nonsense")
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIn("%s=%s/%s" % (tier, plan_tool.GLM[tier][0], plan_tool.GLM[tier][1]), row)


class DoctorKeyHint(unittest.TestCase):
    def test_a_deepseek_pin_hints_the_deepseek_key(self):
        out = doctor_output(self, "deepseek")
        self.assertIn("export DEEPSEEK_API_KEY=", out)
        self.assertNotIn("ZAI_API_KEY", out)

    def test_a_glm_pin_keeps_the_glm_hint(self):
        out = doctor_output(self, "glm")
        self.assertIn("export ZAI_API_KEY=", out)
        self.assertNotIn("DEEPSEEK_API_KEY", out)


if __name__ == "__main__":
    unittest.main()
