"""The provider's 8-concurrent-call cap is vendored per skill (no cross-imports); every copy must equal zai_client.MAX_PARALLEL."""
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.dirname(HERE))
import zai_client  # noqa: E402

PY_CONSTANTS = (
    ("_shared/oc_harness.py", "MAX_PARALLEL"),
    ("requirements-code-audit-glm/scripts/audit.py", "MAX_PARALLEL"),
    ("writing-plans-glm/scripts/plan_tool.py", "MAX_WORKERS"),
    ("systematic-debugging-glm/scripts/debug_tool.py", "MAX_API"),
    ("dev-team-glm/scripts/devteam.py", "NON_CLAUDE_CAP"),
)


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


class ProviderCapConsistent(unittest.TestCase):
    def test_source_of_truth_is_8(self):
        self.assertEqual(zai_client.MAX_PARALLEL, 8)

    def test_python_constants_match(self):
        for rel, name in PY_CONSTANTS:
            m = re.search(r"^%s\s*=\s*(\d+)\b" % name, read(rel), re.M)
            self.assertIsNotNone(m, "%s: %s not found" % (rel, name))
            self.assertEqual(int(m.group(1)), zai_client.MAX_PARALLEL, "%s: %s" % (rel, name))

    def test_context_sh_c8_clamps_to_cap(self):
        rel = "brainstorming-glm/scripts/context.sh"
        m = re.search(r"^c8\(\)\s*\{.*$", read(rel), re.M)
        self.assertIsNotNone(m, "c8() not found in " + rel)
        cap = zai_client.MAX_PARALLEL
        self.assertRegex(m.group(0), r"-gt %d \]; then echo %d\b" % (cap, cap))


if __name__ == "__main__":
    unittest.main()
