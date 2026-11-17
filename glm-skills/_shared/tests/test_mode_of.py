"""mode_of: FAST is the default, SLOW only when the user says so."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

import handoff  # noqa: E402


class ModeOfTests(unittest.TestCase):
    def test_fast_tokens(self):
        self.assertEqual(handoff.mode_of("FAST", ""), "fast")
        self.assertEqual(handoff.mode_of("che do fast", ""), "fast")
        self.assertEqual(handoff.mode_of("use FAST mode", ""), "fast")
        self.assertEqual(handoff.mode_of("D\u00f9ng ch\u1ebf \u0111\u1ed9 fast", ""), "fast")
        self.assertEqual(handoff.mode_of("--fast", ""), "fast")
        self.assertEqual(handoff.mode_of("/fast", ""), "fast")

    def test_slow_tokens(self):
        self.assertEqual(handoff.mode_of("SLOW", ""), "slow")
        self.assertEqual(handoff.mode_of("slow mode", ""), "slow")
        self.assertEqual(handoff.mode_of("che do slow", ""), "slow")
        self.assertEqual(handoff.mode_of("che do chat luong", ""), "slow")
        self.assertEqual(handoff.mode_of("Ch\u1ebf \u0111\u1ed9 ch\u1ea5t l\u01b0\u1ee3ng", ""), "slow")
        self.assertEqual(handoff.mode_of("uu tien chat luong", ""), "slow")
        self.assertEqual(handoff.mode_of("\u01b0u ti\u00ean ch\u1ea5t l\u01b0\u1ee3ng", ""), "slow")
        self.assertEqual(handoff.mode_of("quality mode", ""), "slow")
        self.assertEqual(handoff.mode_of("--slow", ""), "slow")
        self.assertEqual(handoff.mode_of("/slow", ""), "slow")

    def test_refusals(self):
        self.assertEqual(handoff.mode_of("khong dung fast", ""), "fast")
        self.assertEqual(handoff.mode_of("khong dung slow", ""), "fast")
        self.assertEqual(handoff.mode_of("do not use FAST mode", ""), "fast")
        self.assertEqual(handoff.mode_of("without slow mode please", ""), "fast")

    def test_empty_text_is_fast(self):
        self.assertEqual(handoff.mode_of("", "slow"), "fast")
        self.assertEqual(handoff.mode_of("   \n", ""), "fast")

    def test_both_present_the_later_match_wins(self):
        self.assertEqual(handoff.mode_of("FAST build it, but switch to SLOW", ""), "slow")
        self.assertEqual(handoff.mode_of("SLOW please, but actually FAST", ""), "fast")
        self.assertEqual(handoff.mode_of("dung fast nhung uu tien chat luong", ""), "slow")

    def test_no_mode_word_keeps_the_stamp(self):
        self.assertEqual(handoff.mode_of("build a login page", "slow"), "slow")
        self.assertEqual(handoff.mode_of("build a login page", "fast"), "fast")

    def test_a_stored_normal_is_fast(self):
        self.assertEqual(handoff.mode_of("build a login page", "normal"), "fast")
        self.assertEqual(handoff.mode_of("build a login page", ""), "fast")

    def test_a_followup_without_a_mode_word_keeps_slow(self):
        self.assertEqual(handoff.mode_of("also fix the settings page", "slow"), "slow")

    def test_mixed_coordinates_still_order_by_text(self):
        folded_first = "ch\u1ebf \u0111\u1ed9 chat l\u01b0\u1ee3ng nh\u01b0ng sau \u0111\u00f3 d\u00f9ng FAST"
        self.assertEqual(handoff.mode_of(folded_first, ""), "fast")


if __name__ == "__main__":
    unittest.main()
