"""S1: five-model GUARD line, pro pin words, pro API id, zai_client docstring."""
import contextlib
import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.dirname(HERE)
sys.path.insert(0, SHARED)


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SHARED, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


flash_pin = _load("flash_pin_pro_under_test", "flash_pin.py")
handoff = _load("handoff_guard_under_test", "handoff.py")
zai_client = _load("zai_client_doc_under_test", "zai_client.py")

SESSION_MODELS = (
    "GLM-5.3-Flash",
    "DeepSeek V4.1 Flash",
    "GLM 5.3",
    "DeepSeek V4 Pro",
    "Claude Sonnet 5.5",
)


@contextlib.contextmanager
def _env(values):
    """Run with exactly `values` in os.environ, then restore it."""
    saved = dict(os.environ)
    os.environ.clear()
    os.environ.update(values)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(saved)


def _pin_home(case, word):
    home = tempfile.mkdtemp()
    case.addCleanup(shutil.rmtree, home, True)
    os.makedirs(os.path.join(home, ".zcode"))
    with open(os.path.join(home, ".zcode", "z-flash"), "w", encoding="utf-8") as fh:
        fh.write(word)
    return home


class ProPinWords(unittest.TestCase):
    def test_deepseek_v4_pro_env_word_maps_to_deepseek_provider(self):
        with _env({"GLM_FLASH": "deepseek-v4-pro"}):
            self.assertEqual(flash_pin.provider(), "deepseek")

    def test_glm_5_3_env_word_maps_to_glm_provider(self):
        with _env({"GLM_FLASH": "glm-5.3"}):
            self.assertEqual(flash_pin.provider(), "glm")

    def test_pro_word_in_pin_file_maps_to_its_provider(self):
        for word, want in (("glm-5.3", "glm"), ("deepseek-v4-pro", "deepseek")):
            with self.subTest(word=word):
                home = _pin_home(self, word + "\n")
                with _env({}):
                    self.assertEqual(flash_pin.provider(home), want)


class PinWord(unittest.TestCase):
    def test_returns_raw_first_env_token(self):
        with _env({"GLM_FLASH": "deepseek-v4-pro trailing words"}):
            self.assertEqual(flash_pin.pin_word(), "deepseek-v4-pro")

    def test_env_wins_over_pin_file(self):
        home = _pin_home(self, "deepseek\n")
        with _env({"GLM_FLASH": "glm-5.3"}):
            self.assertEqual(flash_pin.pin_word(home), "glm-5.3")

    def test_reads_pin_file_when_env_unset(self):
        home = _pin_home(self, "deepseek-v4-pro\n")
        with _env({}):
            self.assertEqual(flash_pin.pin_word(home), "deepseek-v4-pro")

    def test_preserves_the_written_case(self):
        with _env({"GLM_FLASH": "DeepSeek-V4-Pro"}):
            self.assertEqual(flash_pin.pin_word(), "DeepSeek-V4-Pro")

    def test_empty_env_falls_through_to_pin_file(self):
        home = _pin_home(self, "deepseek\n")
        with _env({"GLM_FLASH": "", "HOME": home}):
            self.assertEqual(flash_pin.pin_word(), "deepseek")
            self.assertEqual(flash_pin.provider(), "deepseek")

    def test_absent_pin_file_means_no_pin_and_glm(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        with _env({"HOME": home}):
            self.assertEqual(flash_pin.pin_word(), "")
            self.assertEqual(flash_pin.provider(), "glm")


class ProHttpResolve(unittest.TestCase):
    def test_deepseek_pro_pin_resolves_pro_api_id_for_every_model(self):
        with _env({"GLM_FLASH": "deepseek-v4-pro"}):
            for model in ("glm-5.3-flash", "GLM-5.3", "anything-else"):
                with self.subTest(model=model):
                    self.assertEqual(
                        flash_pin.resolve_http_model(model), "deepseek-v4-pro")

    def test_z_pro_pin_resolves_pro_api_id_for_every_model(self):
        with _env({"GLM_FLASH": "glm-5.3"}):
            for model in ("glm-5.3-flash", "some-other-model"):
                with self.subTest(model=model):
                    self.assertEqual(flash_pin.resolve_http_model(model), "glm-5.3")

    def test_pro_api_maps_both_pro_words_to_their_api_ids(self):
        pro_api = getattr(flash_pin, "PRO_API", {})
        self.assertEqual(pro_api.get("deepseek-v4-pro"), "deepseek-v4-pro")
        self.assertEqual(pro_api.get("glm-5.3"), "glm-5.3")


class FlashTierUnchanged(unittest.TestCase):
    def test_deepseek_flash_pin_keeps_today_remap(self):
        with _env({"GLM_FLASH": "deepseek"}):
            self.assertEqual(flash_pin.provider(), "deepseek")
            cases = (("glm-5.3-flash", "deepseek-flash"),
                     ("GLM-5.3", "deepseek-flash"),
                     ("unlisted-model", "unlisted-model"))
            for model, want in cases:
                with self.subTest(model=model):
                    self.assertEqual(flash_pin.resolve_http_model(model), want)

    def test_z_flash_pin_keeps_passthrough(self):
        with _env({"GLM_FLASH": "glm"}):
            self.assertEqual(flash_pin.provider(), "glm")
            self.assertEqual(
                flash_pin.resolve_http_model("glm-5.3-flash"), "glm-5.3-flash")

    def test_pin_file_flash_word_still_selects_deepseek(self):
        home = _pin_home(self, "deepseek\n")
        with _env({}):
            self.assertEqual(flash_pin.provider(home), "deepseek")

    def test_unknown_pin_word_falls_back_to_glm_without_crash(self):
        with _env({"GLM_FLASH": "claude-sonnet-5.5"}):
            self.assertEqual(flash_pin.pin_word(), "claude-sonnet-5.5")
            self.assertEqual(flash_pin.provider(), "glm")
            self.assertEqual(
                flash_pin.resolve_http_model("glm-5.3-flash"), "glm-5.3-flash")


class GuardFlashLine(unittest.TestCase):
    def _line(self):
        lines = [g for g in handoff.GUARDS if g.startswith("GUARD flash:")]
        self.assertEqual(
            len(lines), 1, "expected one GUARD flash line, found %d" % len(lines))
        return lines[0]

    def test_names_all_five_session_models(self):
        line = self._line()
        for name in SESSION_MODELS:
            with self.subTest(model=name):
                self.assertIn(name, line)

    def test_keeps_the_no_promotion_rule(self):
        self.assertIn("never promote a lane to another model", self._line())


class ZaiClientDocstring(unittest.TestCase):
    def test_names_five_session_models_and_both_providers(self):
        doc = zai_client.__doc__ or ""
        for name in SESSION_MODELS:
            with self.subTest(model=name):
                self.assertIn(name, doc)
        self.assertIn("provider", doc.lower())


if __name__ == "__main__":
    unittest.main()
