import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import oc_harness

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SKILLS = ["brainstorming", "dev-team", "doc-generator",
          "requirements-code-audit", "systematic-debugging", "writing-plans"]


def _agent(extra):
    return "---\ndescription: d\n{}---\nbody\n".format(extra)


class RenderAgentNoModelTests(unittest.TestCase):
    def test_model_values_never_reach_the_output(self):
        for value in ("flash", "pro", "other/some-model"):
            out = oc_harness.render_agent(_agent("model: %s\n" % value), 2)
            self.assertEqual([ln for ln in out.splitlines() if ln.startswith("model:")], [], value)

    def test_effort_values_never_reach_the_output(self):
        for value in ("low", "medium", "high", "max"):
            source = _agent("effort: %s\nvariant: %s\nreasoningEffort: %s\n" % (value, value, value))
            out = oc_harness.render_agent(source, 2)
            for prefix in ("effort:", "variant:", "reasoningEffort:"):
                self.assertEqual([ln for ln in out.splitlines() if ln.startswith(prefix)], [], value)

    def test_output_is_identical_with_or_without_model_keys(self):
        plain = oc_harness.render_agent(_agent(""), 2)
        keyed = oc_harness.render_agent(_agent("model: pro\neffort: max\n"), 2)
        self.assertEqual(plain, keyed)


class VendoredCopyTests(unittest.TestCase):
    def test_vendored_copies_byte_identical(self):
        with open(os.path.join(ROOT, "_shared", "oc_harness.py"), "rb") as f:
            src = f.read()
        for skill in SKILLS:
            with open(os.path.join(ROOT, "oc-" + skill, "scripts", "oc_harness.py"), "rb") as f:
                self.assertEqual(f.read(), src, skill)


if __name__ == "__main__":
    unittest.main()
