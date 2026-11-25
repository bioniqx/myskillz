"""Spec 2026-11-25: plan_tool.py doctor prints the effort, the model ids the lane will call and the
key the pinned provider reads; setup prints the same key hint.

Every call runs with a throwaway HOME and without the developer's PLAN_* variables, so no test
reads the real pin file or override."""
import argparse
import contextlib
import importlib.util
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
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


def throwaway_home(case, pin_word=None):
    """A throwaway HOME, holding a pin file when pin_word is given."""
    path = Path(tempfile.mkdtemp())
    case.addCleanup(shutil.rmtree, path, True)
    if pin_word is not None:
        (path / ".zcode").mkdir()
        (path / ".zcode" / "z-flash").write_text(pin_word + "\n", encoding="utf-8")
    return path


def run_isolated(case, run, pin, home, **extra):
    """(exit code, stdout) of run() under a throwaway HOME and one env pin, with no API key found."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("PLAN_") and k != "GLM_FLASH"}
    env.update({"GLM_FLASH": pin, "HOME": str(home)})
    env.update(extra)
    buf = io.StringIO()
    fake = mock.patch.object(plan_tool, "find_credentials", return_value=(None, "", "", ""))
    with mock.patch.dict(os.environ, env, clear=True), fake, contextlib.redirect_stdout(buf):
        code = run()
    return code, buf.getvalue()


def doctor_output(case, pin, home, **extra):
    code, out = run_isolated(
        case, lambda: plan_tool.cmd_doctor(argparse.Namespace(ping=False)), pin, home, **extra)
    case.assertEqual(code, 1, "no key means doctor exits 1")
    return out


def models_row(case, pin, home, **extra):
    rows = [ln for ln in doctor_output(case, pin, home, **extra).splitlines() if ln.startswith("models")]
    case.assertEqual(len(rows), 1, "doctor prints exactly one models row")
    return rows[0]


class DoctorModelsRow(unittest.TestCase):
    def test_row_prints_the_effort_each_tier_sets(self):
        row = models_row(self, "glm", throwaway_home(self))
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIn("%s=%s/%s" % (tier, plan_tool.GLM[tier][0], plan_tool.GLM[tier][1]), row)

    def test_row_does_not_hardcode_a_low_light_tier(self):
        self.assertEqual(plan_tool.GLM["light"][1], "high")
        self.assertNotIn("light=%s/low" % plan_tool.GLM["light"][0], models_row(self, "glm", throwaway_home(self)))

    def test_row_prints_the_ids_a_deepseek_pin_selects(self):
        row = models_row(self, "deepseek", throwaway_home(self))
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIn("%s=deepseek-flash/%s" % (tier, plan_tool.GLM[tier][1]), row)

    def test_row_prints_the_id_a_pro_pin_selects(self):
        row = models_row(self, "glm-5.4", throwaway_home(self))
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIn("%s=glm-5.4/%s" % (tier, plan_tool.GLM[tier][1]), row)

    def test_an_unknown_env_word_with_no_pin_file_keeps_the_table_ids(self):
        row = models_row(self, "nonsense", throwaway_home(self))
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIn("%s=%s/%s" % (tier, plan_tool.GLM[tier][0], plan_tool.GLM[tier][1]), row)

    def test_an_unknown_env_word_falls_through_to_a_deepseek_pin_file(self):
        row = models_row(self, "nonsense", throwaway_home(self, "deepseek"))
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIn("%s=deepseek-flash/%s" % (tier, plan_tool.GLM[tier][1]), row)

    def test_row_prints_the_ids_the_model_overrides_select(self):
        row = models_row(self, "glm", throwaway_home(self), PLAN_MODEL_STD="glm-5.4", PLAN_MODEL_DEEP="glm-5.4")
        for tier in TIERS:
            with self.subTest(tier=tier):
                self.assertIn("%s=glm-5.4/%s" % (tier, plan_tool.GLM[tier][1]), row)


class DoctorKeyHint(unittest.TestCase):
    def test_a_deepseek_pin_hints_the_deepseek_key(self):
        out = doctor_output(self, "deepseek", throwaway_home(self))
        self.assertIn("export DEEPSEEK_API_KEY=", out)
        self.assertNotIn("ZAI_API_KEY", out)

    def test_a_glm_pin_keeps_the_glm_hint(self):
        out = doctor_output(self, "glm", throwaway_home(self))
        self.assertIn("export ZAI_API_KEY=", out)
        self.assertNotIn("DEEPSEEK_API_KEY", out)


class SetupKeyHint(unittest.TestCase):
    def _setup_output(self, pin):
        code, out = run_isolated(
            self, lambda: plan_tool.cmd_setup(argparse.Namespace(apply=False)), pin, throwaway_home(self))
        self.assertEqual(code, 0, out)
        self.assertIn("DRY-RUN", out, "setup without --apply only reports")
        return out

    def test_a_deepseek_pin_hints_the_deepseek_key(self):
        out = self._setup_output("deepseek")
        self.assertIn("export DEEPSEEK_API_KEY=", out)
        self.assertNotIn("ZAI_API_KEY", out)

    def test_a_glm_pin_keeps_the_glm_hint(self):
        out = self._setup_output("glm")
        self.assertIn("export ZAI_API_KEY=", out)
        self.assertNotIn("DEEPSEEK_API_KEY", out)


if __name__ == "__main__":
    unittest.main()
