import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ha_briefs
import ha_doctor
import hybrid_shared
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


class TestClassifyViaHybridShared(unittest.TestCase):
    def test_too_many_requests_is_throttle(self):
        self.assertEqual(hybrid_shared.classify(1, ["429 Too Many Requests"], ""), "throttle")

    def test_expired_plan_is_auth(self):
        self.assertEqual(hybrid_shared.classify(1, ["plan expired, please renew"], ""), "auth")

    def test_clean_run_is_empty(self):
        self.assertEqual(hybrid_shared.classify(0, [], ""), "")

    def test_removed_classification_helpers_are_gone(self):
        self.assertFalse(hasattr(ha_doctor, "classify_error"))
        self.assertFalse(hasattr(oc_run, "UNAVAILABLE_RE"))
