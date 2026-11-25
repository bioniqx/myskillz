"""Audit 2026-11-25: the printed review line names the real reason of an UNKNOWN verdict.

An APPROVED report without an Evidence section and a report with no verdict line both end as
UNKNOWN; each must be described by what is actually wrong with it."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "z-dev-team", "scripts"))
import devteam  # noqa: E402


def harvest(case, report):
    """harvest_reviews' lines for one review report written into a throwaway root."""
    root = Path(tempfile.mkdtemp())
    case.addCleanup(shutil.rmtree, root, True)
    reviews = root / devteam.STATE_DIRNAME / "reviews"
    reviews.mkdir(parents=True)
    (reviews / "r1.report.md").write_text(report, encoding="utf-8")
    return devteam.harvest_reviews(root, {"reviews": {"r1": {"status": "inflight", "shards": 1}}})


class ReviewVerdictReason(unittest.TestCase):
    def test_an_approval_without_evidence_is_named_as_such(self):
        lines = harvest(self, "## Review verdict: APPROVED\nLooks done.\n")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("REVIEW r1: UNKNOWN", lines[0])
        self.assertIn("counted as NOT approved", lines[0])
        self.assertNotIn("no verdict line found", lines[0])

    def test_a_report_without_a_verdict_line_says_so(self):
        lines = harvest(self, "## Notes\nNo verdict here.\n")
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("REVIEW r1: UNKNOWN", lines[0])
        self.assertIn("no verdict line found in the report", lines[0])
        self.assertNotIn("counted as NOT approved", lines[0])

    def test_an_approval_with_evidence_is_approved(self):
        lines = harvest(self, "## Review verdict: APPROVED\n\n## Evidence\nran the suite: OK\n")
        self.assertEqual(lines, ["REVIEW r1: APPROVED"])


if __name__ == "__main__":
    unittest.main()
