import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ha_briefs
import ha_doctor
import oc_run


class TestOcHeadWriteFileWording(unittest.TestCase):
    def test_keeps_current_text_as_prefix(self):
        old = (
            "Output the JSONL for this batch between a line `@@@ BEGIN batch-01` and a line "
            "`@@@ END batch-01`, nothing else. You cannot write files; the runner writes them."
        )
        self.assertTrue(ha_briefs.oc_head("batch-01").startswith(old))

    def test_appends_one_sentence_resolving_write_and_reply_wording(self):
        head = ha_briefs.oc_head("batch-01")
        extra = head.split("the runner writes them.", 1)[1].strip()
        self.assertTrue(extra)
        self.assertEqual(extra.count(". "), 0)
        self.assertTrue(extra.endswith("."))
        low = extra.lower()
        self.assertIn("write", low)
        self.assertIn("output file", low)
        self.assertIn("reply with one line", low)
        self.assertIn("marker block instead", low)
        self.assertIn("json lines", low)

    def test_brief_carries_the_new_sentence(self):
        brief = ha_briefs.to_oc_brief("Task line\n\nWrite the findings file BEFORE your final reply.", "b")
        self.assertIn("marker block instead", brief)


class TestClassifyErrorReusesOcRunRegexes(unittest.TestCase):
    def test_uses_oc_run_regex_objects(self):
        self.assertIs(ha_doctor.THROTTLE_RE, oc_run.THROTTLE_RE)
        self.assertIs(ha_doctor.UNAVAILABLE_RE, oc_run.UNAVAILABLE_RE)
        self.assertFalse(hasattr(ha_doctor, "_THROTTLE_RE"))
        self.assertFalse(hasattr(ha_doctor, "_UNAVAILABLE_RE"))

    def test_too_many_requests_is_throttle(self):
        self.assertEqual(ha_doctor.classify_error("429 Too Many Requests"), "throttle")
        self.assertEqual(ha_doctor.classify_error("Too Many Requests"), "throttle")

    def test_expired_plan_is_unavailable(self):
        self.assertEqual(ha_doctor.classify_error("Your plan has expired, please renew"), "unavailable")

    def test_unrelated_is_empty(self):
        self.assertEqual(ha_doctor.classify_error("connection reset"), "")
