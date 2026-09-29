import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ha_oracle  # noqa: E402
from ha_oracle import DOC_PATH, check_citation  # noqa: E402


def make_repo(root: Path) -> Path:
    repo = root / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "app.py").write_text("".join("line %d\n" % i for i in range(1, 11)), encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "api.md").write_text("a\nb\nc\nd\ne\nf\ng\nh\ni\nj\n", encoding="utf-8")
    (repo / "README.md").write_text("readme\n", encoding="utf-8")
    (repo / ".git").mkdir()
    (repo / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    (root / "outside.py").write_text("x = 1\n", encoding="utf-8")
    return repo


class CheckCitationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_doc_path_regex_matches_guard(self):
        self.assertTrue(DOC_PATH.search("docs/api.md"))
        self.assertTrue(DOC_PATH.search("README.md"))
        self.assertTrue(DOC_PATH.search("pkg/CHANGELOG"))
        self.assertFalse(DOC_PATH.search("src/app.py"))

    def test_good_relative_citation(self):
        self.assertEqual(check_citation(self.repo, {"path": "src/app.py", "lines": "2-4"}), "")

    def test_good_absolute_citation(self):
        ev = {"path": str(self.repo / "src" / "app.py"), "lines": "1-3"}
        self.assertEqual(check_citation(self.repo, ev), "")

    def test_outside_repo(self):
        self.assertEqual(check_citation(self.repo, {"path": "../outside.py", "lines": "1-1"}), "outside repo")
        ev = {"path": str(self.root / "outside.py"), "lines": "1-1"}
        self.assertEqual(check_citation(self.repo, ev), "outside repo")

    def test_git_path(self):
        self.assertEqual(check_citation(self.repo, {"path": ".git/config", "lines": "1-1"}), ".git path")

    def test_doc_path(self):
        self.assertEqual(check_citation(self.repo, {"path": "docs/api.md", "lines": "3-9"}), "doc path")
        self.assertEqual(check_citation(self.repo, {"path": "README.md", "lines": "1-1"}), "doc path")

    def test_line_range_past_end_uses_check_evidence(self):
        reason = check_citation(self.repo, {"path": "src/app.py", "lines": "8-40"})
        self.assertTrue(reason)
        self.assertNotIn(reason, ("outside repo", ".git path", "doc path"))

    def test_missing_file_uses_check_evidence(self):
        reason = check_citation(self.repo, {"path": "src/nope.py", "lines": "1-2"})
        self.assertTrue(reason)
        self.assertNotIn(reason, ("outside repo", ".git path", "doc path"))


    def test_directory_citation_rejected(self):
        self.assertTrue(check_citation(self.repo, {"path": "src", "lines": "1-2"}))
        self.assertTrue(check_citation(self.repo, {"path": "src", "lines": ""}))
        self.assertTrue(check_citation(self.repo, {"path": ".", "lines": "1"}))
        self.assertTrue(check_citation(self.repo, {"path": ".", "lines": "1-3"}))

    def test_zero_and_reversed_lines_rejected(self):
        self.assertTrue(check_citation(self.repo, {"path": "src/app.py", "lines": "0"}))
        self.assertTrue(check_citation(self.repo, {"path": "src/app.py", "lines": "0-2"}))
        self.assertTrue(check_citation(self.repo, {"path": "src/app.py", "lines": "3-1"}))
        self.assertEqual(check_citation(self.repo, {"path": "src/app.py", "lines": "3-3"}), "")


class ApplyOracleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = make_repo(self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_verifier_falls_back_to_status(self):
        rows = [{"id": "R1", "status": "MISSING", "confidence": "high", "evidence": []}]
        kept, stats = ha_oracle.apply_oracle(rows, ["R1"], self.repo, "verifier")
        self.assertEqual(kept[0]["verified_status"], "MISSING")
        self.assertEqual(stats["invalid_status"], 0)

    def test_verifier_without_any_status_is_invalid_once(self):
        rows = [{"id": "R1", "confidence": "high", "evidence": []}]
        kept, stats = ha_oracle.apply_oracle(rows, ["R1"], self.repo, "verifier")
        self.assertEqual(kept[0]["verified_status"], "UNSEARCHED")
        self.assertEqual(stats["invalid_status"], 1)

    def test_matched_with_only_directory_citation_demoted(self):
        rows = [{"id": "R1", "status": "MATCHED", "confidence": "high", "evidence": [{"path": "src", "lines": "1-2"}]}]
        kept, stats = ha_oracle.apply_oracle(rows, ["R1"], self.repo, "investigator")
        self.assertEqual(kept[0]["evidence"], [])
        self.assertEqual(kept[0]["confidence"], "low")
        self.assertEqual(stats["dropped"], 1)
        self.assertEqual(stats["demoted"], 1)

    def test_whitespace_ids_are_stripped_not_foreign(self):
        rows = [{"id": " R1 ", "status": "MISSING", "evidence": []},
                {"id": "R2\n", "status": "MISSING", "evidence": []}]
        row = rows[0]
        kept, stats = ha_oracle.apply_oracle(rows, ["R1", " R2"], self.repo, "investigator")
        self.assertEqual([r["id"] for r in kept], ["R1", "R2"])
        self.assertEqual(stats["foreign"], 0)
        self.assertEqual(row["id"], " R1 ")

    def test_foreign_rows_removed(self):
        rows = [
            {"id": "R1", "status": "MATCHED", "confidence": "high", "evidence": [{"path": "src/app.py", "lines": "1-2"}]},
            {"id": "R9", "status": "MATCHED", "confidence": "high", "evidence": [{"path": "src/app.py", "lines": "1-2"}]},
        ]
        kept, stats = ha_oracle.apply_oracle(rows, ["R1", "R2"], self.repo, "investigator")
        self.assertEqual([r["id"] for r in kept], ["R1"])
        self.assertEqual(stats["foreign"], 1)
        self.assertEqual(stats["dropped"], 0)
        self.assertEqual(stats["demoted"], 0)
        self.assertEqual(kept[0]["confidence"], "high")
        self.assertEqual(kept[0]["evidence"], [{"path": "src/app.py", "lines": "1-2"}])

    def test_invalid_status_becomes_unsearched(self):
        rows = [{"id": "R1", "status": "BOGUS", "confidence": "high", "evidence": []}]
        kept, stats = ha_oracle.apply_oracle(rows, ["R1"], self.repo, "investigator")
        self.assertEqual(kept[0]["status"], "UNSEARCHED")
        self.assertEqual(stats["invalid_status"], 1)

    def test_bad_citation_dropped_noted_and_demoted(self):
        rows = [{"id": "R1", "status": "MATCHED", "confidence": "high", "notes": "seen in handler",
                 "evidence": [{"path": "src/app.py", "lines": "1-2"}, {"path": "docs/api.md", "lines": "3-9"}]}]
        kept, stats = ha_oracle.apply_oracle(rows, ["R1"], self.repo, "investigator")
        row = kept[0]
        self.assertEqual(row["evidence"], [{"path": "src/app.py", "lines": "1-2"}])
        self.assertEqual(row["notes"], "seen in handler; oracle: dropped docs/api.md:3-9 — doc path")
        self.assertEqual(row["confidence"], "low")
        self.assertEqual(stats["dropped"], 1)
        self.assertEqual(stats["demoted"], 1)

    def test_demoted_once_per_row(self):
        rows = [{"id": "R1", "status": "MATCHED", "confidence": "high",
                 "evidence": [{"path": ".git/config", "lines": "1-1"}, {"path": "README.md", "lines": "1-1"}]}]
        kept, stats = ha_oracle.apply_oracle(rows, ["R1"], self.repo, "investigator")
        self.assertEqual(kept[0]["evidence"], [])
        self.assertEqual(kept[0]["notes"],
                         "oracle: dropped .git/config:1-1 — .git path; oracle: dropped README.md:1-1 — doc path")
        self.assertEqual(stats["dropped"], 2)
        self.assertEqual(stats["demoted"], 1)

    def test_matched_without_citation_demoted(self):
        rows = [{"id": "R1", "status": "MATCHED", "confidence": "high", "evidence": []}]
        kept, stats = ha_oracle.apply_oracle(rows, ["R1"], self.repo, "investigator")
        self.assertEqual(kept[0]["confidence"], "low")
        self.assertEqual(stats["demoted"], 1)
        self.assertEqual(stats["dropped"], 0)

    def test_input_rows_not_mutated(self):
        row = {"id": "R1", "status": "MATCHED", "confidence": "high",
               "evidence": [{"path": "docs/api.md", "lines": "3-9"}]}
        ha_oracle.apply_oracle([row], ["R1"], self.repo, "investigator")
        self.assertEqual(row["confidence"], "high")
        self.assertEqual(len(row["evidence"]), 1)

    def test_verifier_uses_verified_status_and_reason(self):
        rows = [
            {"id": "R1", "verified_status": "MATCHED", "confidence": "high", "reason": "ok",
             "evidence": [{"path": "../outside.py", "lines": "1-1"}]},
            {"id": "R2", "verified_status": "NOPE", "confidence": "high", "evidence": []},
            {"id": "R3", "verified_status": "MATCHED", "confidence": "high", "evidence": []},
        ]
        kept, stats = ha_oracle.apply_oracle(rows, ["R1", "R2"], self.repo, "verifier")
        self.assertEqual([r["id"] for r in kept], ["R1", "R2"])
        self.assertEqual(kept[0]["reason"], "ok; oracle: dropped ../outside.py:1-1 — outside repo")
        self.assertEqual(kept[0]["confidence"], "low")
        self.assertNotIn("notes", kept[0])
        self.assertEqual(kept[1]["verified_status"], "UNSEARCHED")
        self.assertEqual(stats["foreign"], 1)
        self.assertEqual(stats["invalid_status"], 1)
        self.assertEqual(stats["dropped"], 1)

    def test_parser_rows_unchanged_with_problems(self):
        rows = [{"id": "R1", "text": "The system shall log in."}, {"text": "missing id"}]
        kept, stats = ha_oracle.apply_oracle(rows, [], self.repo, "parser")
        self.assertEqual(kept, rows)
        self.assertEqual(stats["foreign"], 0)
        self.assertEqual(stats["dropped"], 0)
        self.assertEqual(stats["problems"], list(ha_oracle.audit.validate_checklist(rows)))


if __name__ == "__main__":
    unittest.main()
