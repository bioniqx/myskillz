import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = os.path.join(HERE, "..", "..", "glm-brainstorming", "scripts", "check.py")
TODAY = "2026-10-26"


def run(mode_args, stdin="", cwd=None):
    r = subprocess.run([sys.executable, "-I", CHECK] + mode_args + ["--today", TODAY], input=stdin,
                       capture_output=True, text=True, cwd=cwd, timeout=30)
    return r.returncode, r.stdout


class CitesTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="bs_check_")
        os.makedirs(os.path.join(self.root, "src"))
        with open(os.path.join(self.root, "src", "app.py"), "w", encoding="utf-8") as fh:
            fh.write("import os\n\ndef connect(url):\n    return pool.get(url)\n\nclass Pool:\n    pass\n")

    def cites(self, text):
        return run(["cites", "--root", self.root], text)

    def test_real_citation_with_snippet_is_ok(self):
        rc, out = self.cites('src/app.py:4 - connect uses the pool - "return pool.get(url)"\n')
        self.assertEqual(rc, 0, out)
        self.assertIn("OK src/app.py:4", out)

    def test_snippet_within_three_lines_is_tolerated(self):
        rc, out = self.cites('src/app.py:6 - the pool class - "return pool.get(url)"\n')
        self.assertEqual(rc, 0, out)

    def test_invented_line_number_is_bad_and_points_to_the_real_line(self):
        rc, out = self.cites('src/app.py:40 - nope - "return pool.get(url)"\n')
        self.assertEqual(rc, 1)
        self.assertIn("line out of range", out)
        rc, out = self.cites('src/app.py:7 - wrong line - "import os"\n')
        self.assertEqual(rc, 1)
        self.assertIn("appears at line 1", out)

    def test_missing_file_and_escape_are_bad(self):
        rc, out = self.cites('src/ghost.py:1 - x - "y"\n../outside.py:1 - x - "y"\n')
        self.assertEqual(rc, 1)
        self.assertIn("file not found", out)
        self.assertIn("leaves the repository root", out)

    def test_citation_without_quote_is_unchecked_not_ok(self):
        rc, out = self.cites("src/app.py:3 - connect exists\n")
        self.assertEqual(rc, 0)
        self.assertIn("NOQUOTE src/app.py:3", out)
        self.assertIn("unchecked=1", out)

    def test_host_port_is_not_a_citation(self):
        rc, out = self.cites("the service listens on example.com:443 and nothing else\n")
        self.assertEqual(rc, 0)
        self.assertIn("ok=0 bad=0 unchecked=0", out)


class WebTests(unittest.TestCase):
    GOOD = ('lib X 4.2 dropped the flag - A - https://docs.example.org/x/changelog - 2026-08-01 - '
            '"The legacy flag was removed in 4.2."')

    def web(self, text):
        return run(["web"], text)

    def test_complete_tier_a_claim_is_ok(self):
        rc, out = self.web("CLAIMS:\n" + self.GOOD.replace(" - ", " — ") + "\n")
        self.assertEqual(rc, 0, out)
        self.assertIn("ok=1 weak=0 drop=0", out)

    def test_dash_variants_are_accepted(self):
        rc, out = self.web(self.GOOD + "\n")
        self.assertIn("ok=1", out)

    def test_future_missing_or_invalid_dates_are_dropped(self):
        for date in ("2027-01-01", "2026-13-40"):
            rc, out = self.web(self.GOOD.replace("2026-08-01", date) + "\n")
            self.assertEqual(rc, 1, date)
            self.assertIn("DROP", out)
        rc, out = self.web(self.GOOD.replace(" - 2026-08-01", "") + "\n")
        self.assertEqual(rc, 1)
        self.assertIn("no date", out)

    def test_http_search_page_and_unquoted_claims_are_dropped(self):
        rc, out = self.web(self.GOOD.replace("https://", "http://") + "\n")
        self.assertIn("not https", out)
        rc, out = self.web(self.GOOD.replace("https://docs.example.org/x/changelog", "https://www.google.com/search?q=x") + "\n")
        self.assertIn("search results page", out)
        rc, out = self.web(self.GOOD.replace(' - "The legacy flag was removed in 4.2."', "") + "\n")
        self.assertIn("no verbatim quote", out)

    def test_quote_over_25_words_is_dropped(self):
        long_quote = " ".join(["word"] * 26)
        rc, out = self.web(self.GOOD.replace("The legacy flag was removed in 4.2.", long_quote) + "\n")
        self.assertEqual(rc, 1)
        self.assertIn("26 words", out)

    def test_tier_c_and_stale_claims_are_weak_not_dropped(self):
        rc, out = self.web(self.GOOD.replace(" - A - ", " - C - ") + "\n")
        self.assertEqual(rc, 0)
        self.assertIn("WEAK", out)
        rc, out = self.web(self.GOOD.replace("2026-08-01", "2024-01-15") + "\n")
        self.assertEqual(rc, 0)
        self.assertIn("months old", out)

    def test_label_lines_are_not_claims(self):
        rc, out = self.web("ANSWER: use X\nCONFLICTS: none\nVERSION_NOTES: n/a\nUNVERIFIED: none\n")
        self.assertIn("ok=0 weak=0 drop=0", out)


GOOD_SPEC = """# Design

## 1. Architecture
Two services behind one gateway, reusing the existing queue.

## 2. Components
- gateway: routes requests
- worker: drains the queue

## 3. Data flow
Request enters the gateway, is queued, and the worker writes the result.

## 4. Error handling
Failed jobs retry three times, then land in a dead-letter queue.

## 5. Testing
Contract tests per component and one end-to-end test.

## 6. Evidence
- Queue retries are idempotent - [docs](https://docs.example.org/queue) (2026-07-01)
- Gateway limit is 1000 rps - [docs](https://docs.example.org/gw) (2026-06-10)

## 7. Assumptions
- Postgres like the rest of the repo.

## 8. Out of scope
No UI changes.
"""


class SpecTests(unittest.TestCase):
    def lint(self, text):
        fd, path = tempfile.mkstemp(suffix=".md")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        return run(["spec", path])

    def test_complete_spec_passes(self):
        rc, out = self.lint(GOOD_SPEC)
        self.assertEqual(rc, 0, out)
        self.assertIn("fail=0", out)

    def test_missing_and_empty_sections_fail(self):
        rc, out = self.lint(GOOD_SPEC.replace("## 8. Out of scope\nNo UI changes.\n", ""))
        self.assertEqual(rc, 1)
        self.assertIn("FAIL Out of scope - required section is missing", out)
        rc, out = self.lint(GOOD_SPEC.replace("Contract tests per component and one end-to-end test.", ""))
        self.assertIn("FAIL Testing - section is empty", out)

    def test_placeholders_fail_but_code_fences_are_ignored(self):
        rc, out = self.lint(GOOD_SPEC.replace("No UI changes.", "No UI changes. TBD for mobile."))
        self.assertEqual(rc, 1)
        self.assertIn("placeholder", out)
        fenced = GOOD_SPEC.replace("No UI changes.", "```\n# TODO in an example\n```\nNo UI changes.")
        rc, out = self.lint(fenced)
        self.assertEqual(rc, 0, out)

    def test_evidence_lines_need_https_and_a_date(self):
        rc, out = self.lint(GOOD_SPEC.replace("(2026-07-01)", ""))
        self.assertEqual(rc, 1)
        self.assertIn("no (YYYY-MM-DD) date", out)
        rc, out = self.lint(GOOD_SPEC.replace("https://docs.example.org/queue", "docs.example.org/queue"))
        self.assertIn("no https URL", out)

    def test_repo_internal_design_may_say_none(self):
        text = GOOD_SPEC.split("## 6. Evidence")[0] + "## 6. Evidence\nNone: repo-internal change.\n\n## 7. Assumptions\n- Same DB.\n\n## 8. Out of scope\nNo UI work planned.\n"
        rc, out = self.lint(text)
        self.assertEqual(rc, 0, out)


if __name__ == "__main__":
    unittest.main()
