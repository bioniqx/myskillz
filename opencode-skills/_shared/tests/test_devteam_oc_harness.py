"""dev-team engine: constants, agent-only routing and dispatch rows."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "oc-dev-team", "scripts")
sys.path.insert(0, SCRIPTS)

import oc_devteam as devteam  # noqa: E402
import oc_harness  # noqa: E402


class ConstantsTest(unittest.TestCase):
    def test_state_dir_and_engine_version(self):
        self.assertEqual(devteam.STATE_DIRNAME, ".opencode/oc-dev-team")
        self.assertEqual(devteam.ENGINE_VERSION, "5.0")
        self.assertIn(".opencode/oc-dev-team/", devteam.EXCLUDE_LINES)

    def test_concurrency_limit_is_the_hard_cap(self):
        self.assertEqual(devteam.concurrency_limit(), devteam.HARD_CAP)

    def test_doctor_checks_the_five_agents(self):
        self.assertEqual(devteam.OC_AGENT_NAMES,
                         ("programmer", "code-reviewer", "spot-reviewer", "investigator", "team-leader"))


class RoutingTest(unittest.TestCase):
    def test_dispatch_route_names_an_agent_only(self):
        heavy = {"risk": "high", "size": "large", "attempt": 3, "kind": "code"}
        self.assertEqual(devteam.dispatch_route({}, heavy, "slice"), "programmer")
        self.assertEqual(devteam.dispatch_route({}, {"size": "trivial", "kind": "docs"}, "work"), "programmer")
        self.assertEqual(devteam.dispatch_route({}, {"kind": "research"}, "research"), "investigator")


class EmitAgentTest(unittest.TestCase):
    def test_emit_agent_writes_the_prompt_and_returns_the_v2_row(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            line = devteam.emit_agent(root, {}, "code-reviewer", "Read r1.md and follow it exactly.", "review r1")
            prompt = root / ".opencode" / "oc-dev-team" / "prompts" / "review-r1.md"
            self.assertEqual(prompt.read_text(), "Read r1.md and follow it exactly.\n")
        self.assertEqual(line, oc_harness.dispatch_line("oc-code-reviewer", str(prompt), "review r1", 2))
        self.assertIn("background", line)

    def test_label_becomes_a_safe_prompt_file_name(self):
        with tempfile.TemporaryDirectory() as td:
            devteam.emit_agent(Path(td), {}, "team-leader", "x", "verify intent")
            self.assertTrue((Path(td) / ".opencode" / "oc-dev-team" / "prompts" / "verify-intent.md").exists())

    def test_launch_hint_is_a_next_line_that_waits(self):
        hint = devteam.launch_hint()
        self.assertTrue(hint.startswith("NEXT: emit every dispatch row above in ONE message"), hint)
        self.assertIn(" wait`", hint)
        self.assertIn("`next`", hint)
        self.assertIn("read the reports", devteam.launch_hint("read the reports"))


if __name__ == "__main__":
    unittest.main()
