"""Flash does not name a root cause. experiment records do."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.realpath(
    os.path.join(HERE, "..", "..", "glm-systematic-debugging", "scripts"))
sys.path.insert(0, SCRIPTS)
import debug_tool  # noqa: E402


class ClassifyCauseTests(unittest.TestCase):
    def test_one_confirmed_diagnosis_needs_no_drafted_report(self):
        records = [{"id": "h1", "verdict": "CONFIRMED", "role": "diagnose"}]
        fails, decision = debug_tool.classify_cause(records, "")
        self.assertEqual(fails, [])
        self.assertEqual(decision, "DECISION pick=h1")

    def test_one_confirmed_diagnosis_is_the_only_legal_cause(self):
        records = [{"id": "h1", "verdict": "CONFIRMED", "role": "diagnose"}]
        fails, decision = debug_tool.classify_cause(records, "ROOT CAUSE: h1\nFIX: n/a\n")
        self.assertEqual(fails, [])
        self.assertEqual(decision, "DECISION pick=h1")

    def test_a_cause_with_no_experiment_stops(self):
        fails, decision = debug_tool.classify_cause([], "ROOT CAUSE: the cache\n")
        self.assertTrue(fails)
        self.assertEqual(decision, "DECISION stop")

    def test_two_confirmed_diagnoses_ask(self):
        records = [
            {"id": "h1", "verdict": "CONFIRMED", "role": "diagnose"},
            {"id": "h2", "verdict": "CONFIRMED", "role": "diagnose"},
        ]
        fails, decision = debug_tool.classify_cause(records, "ROOT CAUSE: h1\n")
        self.assertTrue(fails)
        self.assertEqual(decision, "DECISION ask=h1")

    def test_no_cause_is_legal_when_nothing_confirmed(self):
        records = [{"id": "h1", "verdict": "REFUTED", "role": "diagnose"}]
        fails, decision = debug_tool.classify_cause(records, "NO CAUSE\n")
        self.assertEqual(fails, [])
        self.assertEqual(decision, "DECISION pick=none")

    def test_a_fix_line_needs_a_confirmed_fix_experiment(self):
        records = [{"id": "h1", "verdict": "CONFIRMED", "role": "diagnose"}]
        fails, decision = debug_tool.classify_cause(records, "ROOT CAUSE: h1\nFIX: src/a.py:3\n")
        self.assertTrue(any("fix" in f for f in fails))
        self.assertEqual(decision, "DECISION stop")

    def test_a_confirmed_fix_lets_the_fix_line_stand(self):
        records = [
            {"id": "h1", "verdict": "CONFIRMED", "role": "diagnose"},
            {"id": "h2", "verdict": "CONFIRMED", "role": "fix"},
        ]
        fails, decision = debug_tool.classify_cause(
            records, "ROOT CAUSE: h1\nFIX: src/a.py:3\n")
        self.assertEqual(fails, [])
        self.assertEqual(decision, "DECISION pick=h1")


class DebugTierTests(unittest.TestCase):
    def test_every_tier_is_flash_and_light_is_high(self):
        for name, (model, effort) in debug_tool.TIERS.items():
            self.assertEqual(model, "glm-5.3-flash", name)
            self.assertNotEqual(effort, "low", name)
        self.assertEqual(debug_tool.TIERS["deep"][1], "max")

    def test_worker_pins_flash_and_does_not_load_agents_md(self):
        path = os.path.join(SCRIPTS, "..", "agents", "glm-debug-worker.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("GLM-5.3-Flash", text)
        self.assertIn("thoughtLevel: max", text)
        self.assertIn("injectAgentsMd: false", text)


if __name__ == "__main__":
    unittest.main()
