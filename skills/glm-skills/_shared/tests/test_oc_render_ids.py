import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import oc_harness

GLM = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SKILLS = ["brainstorming-glm", "dev-team-glm", "doc-generator-glm",
          "requirements-code-audit-glm", "systematic-debugging-glm", "writing-plans-glm"]


def _agent(model):
    return "---\ndescription: d\nmodel: {}\n---\nbody\n".format(model)


class TestRenderAgentModelIds(unittest.TestCase):
    def _model_lines(self, model, major):
        out = oc_harness.render_agent(_agent(model), major)
        return [ln for ln in out.splitlines() if ln.startswith("model:")]

    def test_bare_model_id_gets_provider_prefix(self):
        for major in (1, 2):
            self.assertEqual(self._model_lines("glm-5.3", major), ["model: zai-coding-plan/glm-5.3"])
            self.assertEqual(self._model_lines("glm-5.3-flash", major),
                             ["model: zai-coding-plan/glm-5.3-flash"])

    def test_provider_model_id_kept_unchanged(self):
        for major in (1, 2):
            self.assertEqual(self._model_lines("zai-coding-plan/glm-5.3", major),
                             ["model: zai-coding-plan/glm-5.3"])
            self.assertEqual(self._model_lines("other/some-model", major), ["model: other/some-model"])

    def test_aliases_keep_current_output(self):
        for major in (1, 2):
            self.assertEqual(self._model_lines("flash", major), ["model: zai-coding-plan/glm-5.3-flash"])
            self.assertEqual(self._model_lines("pro", major), ["model: zai-coding-plan/glm-5.3"])

    def test_vendored_copies_byte_identical(self):
        with open(os.path.join(GLM, "_shared", "oc_harness.py"), "rb") as f:
            src = f.read()
        for skill in SKILLS:
            with open(os.path.join(GLM, skill, "scripts", "oc_harness.py"), "rb") as f:
                self.assertEqual(f.read(), src, skill)


if __name__ == "__main__":
    unittest.main()
