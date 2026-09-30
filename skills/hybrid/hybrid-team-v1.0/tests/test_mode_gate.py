"""The run-mode popup must be a hard gate in SKILL.md (it was skipped when a global "act first" rule won)."""
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"


class ModeGateTest(unittest.TestCase):
    def test_popup_is_a_mandatory_first_action(self):
        text = SKILL.read_text(encoding="utf-8")
        assert "HARD GATE: the mode popup is mandatory" in text
        gate = text[text.index("HARD GATE: the mode popup"):][:900]
        for needle in ("AskUserQuestion", "ToolSearch", "mode=hybrid|claude|opencode", "never pick Hybrid"):
            assert needle in gate, needle
        for option in ("Hybrid (Recommended)", "Claude only", "opencode only"):
            assert option in text, option


if __name__ == "__main__":
    unittest.main()
