import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hb_ground  # noqa: E402


class ParseTests(unittest.TestCase):
    def test_sections_constant(self):
        self.assertEqual(
            hb_ground.SECTIONS,
            ("FINDINGS", "PATTERNS", "RISKS", "UNKNOWN", "ANSWER", "CLAIMS",
             "CONFLICTS", "VERSION_NOTES", "UNVERIFIED"),
        )

    def test_normalize(self):
        self.assertEqual(hb_ground.normalize("  Foo\n\tBAR   baz "), "foo bar baz")
        self.assertEqual(hb_ground.normalize(""), "")

    def test_parse_sections(self):
        text = (
            "preamble is ignored\n"
            "FINDINGS:\n"
            "- a.py:1 — x\n"
            "* b.py:2 — y\n"
            "\n"
            "**PATTERNS:**\n"
            "1. uses flock\n"
            "### RISKS:\n"
            "- race on slot files\n"
            "ANSWER: inline answer\n"
            "UNVERIFIED: none\n"
            "UNKNOWN:\n"
        )
        self.assertEqual(
            hb_ground.parse_sections(text),
            {
                "FINDINGS": ["a.py:1 — x", "b.py:2 — y"],
                "PATTERNS": ["uses flock"],
                "RISKS": ["race on slot files"],
                "ANSWER": ["inline answer"],
                "UNVERIFIED": [],
                "UNKNOWN": [],
            },
        )

    def test_parse_sections_empty_text(self):
        self.assertEqual(hb_ground.parse_sections(""), {})
        self.assertEqual(hb_ground.parse_sections("no headers at all\n"), {})

    def test_parse_sections_drops_sentinel(self):
        text = "FINDINGS:\n- a.py:1 — x\n- HB-LANE-OK\n"
        self.assertEqual(hb_ground.parse_sections(text), {"FINDINGS": ["a.py:1 — x"]})


CORE_LINES = (
    # pkg/core.py: line 3 defines lane_is_live, line 14 defines caller,
    # line 15 calls lane_is_live, line 20 sets OTHER; 20 lines total.
    ["import os", "", "def lane_is_live(pid):", "    return os.path.exists(pid)"]
    + ["# pad"] * 9
    + ["def caller():", "    return lane_is_live(1)"]
    + ["# pad"] * 4
    + ["OTHER = 1"]
)


class GroundCodeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.root = self.base / "repo"
        (self.root / "pkg").mkdir(parents=True)
        (self.root / "pkg" / "core.py").write_text("\n".join(CORE_LINES) + "\n", encoding="utf-8")
        (self.base / "secret.py").write_text("lane_is_live = 1\n", encoding="utf-8")
        (self.root / "pkg" / "names.py").write_text("name = 1\n", encoding="utf-8")
        (self.root / "pkg" / "dotted.py").write_text("# ref pkg.mod.name here\n", encoding="utf-8")
        comma_lines = ["# l%d" % n for n in range(1, 9)] + ["def foo(): pass"] + ["# l%d" % n for n in range(10, 13)]
        (self.root / "pkg" / "comma.py").write_text("\n".join(comma_lines) + "\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def ground(self, *findings):
        text = "FINDINGS:\n" + "\n".join("- " + f for f in findings) + "\n"
        return hb_ground.ground_code(text, self.root)

    def test_valid_path_line(self):
        line = "pkg/core.py:3 — `lane_is_live` is defined here"
        r = self.ground(line)
        self.assertTrue(r["ok"])
        self.assertEqual((r["grounded"], r["total"]), (1, 1))
        self.assertEqual(r["items"], [line])
        self.assertEqual(r["unverified"], [])

    def test_line_range(self):
        r = self.ground("pkg/core.py:14-15 — `caller` calls `lane_is_live`")
        self.assertTrue(r["ok"])
        self.assertEqual(r["grounded"], 1)

    def test_backticked_path(self):
        r = self.ground("`pkg/core.py:3` — `lane_is_live` is defined here")
        self.assertTrue(r["ok"])

    def test_missing_file(self):
        r = self.ground("pkg/nope.py:1 — `x` gone")
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], ["pkg/nope.py:1 — `x` gone (missing file)"])

    def test_outside_root_absolute(self):
        line = "%s:1 — `lane_is_live` leaked" % (self.base / "secret.py")
        r = self.ground(line)
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [line + " (outside repo root)"])

    def test_outside_root_dotdot(self):
        line = "../secret.py:1 — `lane_is_live` leaked"
        r = self.ground(line)
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [line + " (outside repo root)"])

    def test_line_past_end(self):
        r = self.ground("pkg/core.py:21 — `OTHER` is set")
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], ["pkg/core.py:21 — `OTHER` is set (line out of range)"])
        r = self.ground("pkg/core.py:0 — `OTHER` is set")
        self.assertEqual(r["unverified"], ["pkg/core.py:0 — `OTHER` is set (line out of range)"])

    def test_range_past_end(self):
        r = self.ground("pkg/core.py:19-25 — padding")
        self.assertEqual(r["unverified"], ["pkg/core.py:19-25 — padding (line out of range)"])

    def test_identifier_not_near(self):
        r = self.ground("pkg/core.py:3 — `OTHER` is set here")
        self.assertFalse(r["ok"])
        self.assertEqual(
            r["unverified"], ["pkg/core.py:3 — `OTHER` is set here (`OTHER` not near line 3)"]
        )

    def test_identifier_window_edges(self):
        r = self.ground("pkg/core.py:20 — `lane_is_live` is five lines up")
        self.assertTrue(r["ok"])
        r = self.ground("pkg/core.py:14 — `OTHER` is six lines down")
        self.assertEqual(
            r["unverified"],
            ["pkg/core.py:14 — `OTHER` is six lines down (`OTHER` not near line 14)"],
        )

    def test_sentinel_line_ignored(self):
        text = (
            "FINDINGS:\n"
            "- pkg/core.py:3 — `lane_is_live` is defined here\n"
            "- pkg/core.py:21 — `OTHER` is set\n"
            "- HB-LANE-OK\n"
        )
        r = hb_ground.ground_code(text, self.root)
        self.assertTrue(r["ok"])
        self.assertEqual((r["grounded"], r["total"]), (1, 2))
        self.assertEqual(
            r["unverified"], ["pkg/core.py:21 — `OTHER` is set (line out of range)"]
        )

    def test_col_suffix_accepted(self):
        r = self.ground("pkg/core.py:3:5 — `lane_is_live` is defined here")
        self.assertTrue(r["ok"])

    def test_no_dash_separator_accepted(self):
        r = self.ground("pkg/core.py:3 `lane_is_live` is defined here")
        self.assertTrue(r["ok"])
        self.assertEqual((r["grounded"], r["total"]), (1, 1))

    def test_identifier_trailing_parens(self):
        r = self.ground("pkg/core.py:20 — `lane_is_live()` is called here")
        self.assertTrue(r["ok"])

    def test_identifier_dotted_last_component(self):
        r = self.ground("pkg/core.py:20 — `pkg.core.lane_is_live` is referenced here")
        self.assertTrue(r["ok"])

    def test_identifier_boundary_bare_name(self):
        r = self.ground("pkg/names.py:1 — `pkg.mod.name` is referenced here")
        self.assertTrue(r["ok"])

    def test_identifier_boundary_rejects_prefix(self):
        line = "pkg/names.py:1 — `pkg.mod.nam` is referenced here"
        r = self.ground(line)
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [line + " (`pkg.mod.nam` not near line 1)"])

    def test_dotted_full_identifier_grounded(self):
        r = self.ground("pkg/dotted.py:1 — `pkg.mod.name` is referenced here")
        self.assertTrue(r["ok"])

    def test_dotted_suffix_identifier_grounded(self):
        r = self.ground("pkg/dotted.py:1 — `mod.name` is referenced here")
        self.assertTrue(r["ok"])

    def test_dotted_truncated_suffix_ungrounded(self):
        line = "pkg/dotted.py:1 — `pkg.mod.nam` is referenced here"
        r = self.ground(line)
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [line + " (`pkg.mod.nam` not near line 1)"])

    def test_dotted_truncated_last_segment_ungrounded(self):
        line = "pkg/dotted.py:1 — `mod.nam` is referenced here"
        r = self.ground(line)
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [line + " (`mod.nam` not near line 1)"])

    def test_comma_lines_grounded_near_second(self):
        line = "pkg/comma.py:2,9 — `foo` is defined here"
        r = self.ground(line)
        self.assertTrue(r["ok"])
        self.assertEqual((r["grounded"], r["total"]), (1, 1))

    def test_comma_lines_out_of_range_ungrounded(self):
        line = "pkg/comma.py:2,99 — `foo` is defined here"
        r = self.ground(line)
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [line + " (line out of range)"])

    def test_dotted_near_miss_qualifiers_ungrounded(self):
        for ident in ("kg.mod.name", "other.name", "zzz.qqq.name"):
            line = "pkg/dotted.py:1 — `%s` is referenced here" % ident
            r = self.ground(line)
            self.assertFalse(r["ok"], ident)
            self.assertEqual(r["unverified"], [line + " (`%s` not near line 1)" % ident])

    def test_mixed_range_comma_grounded(self):
        r = self.ground("pkg/comma.py:1-3,9 — `foo` is defined here")
        self.assertTrue(r["ok"])
        self.assertEqual((r["grounded"], r["total"]), (1, 1))

    def test_mixed_range_comma_out_of_range(self):
        line = "pkg/comma.py:1-3,99 — `foo` is defined here"
        r = self.ground(line)
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [line + " (line out of range)"])

    def test_comma_then_range_grounded(self):
        r = self.ground("pkg/comma.py:1,5-9 — `foo` is defined here")
        self.assertTrue(r["ok"])
        self.assertEqual((r["grounded"], r["total"]), (1, 1))

    def test_comma_then_range_out_of_range(self):
        line = "pkg/comma.py:1,5-99 — `foo` is defined here"
        r = self.ground(line)
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [line + " (line out of range)"])

    def test_reversed_range_out_of_range(self):
        line = "pkg/comma.py:5-2 — `foo` is defined here"
        r = self.ground(line)
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [line + " (line out of range)"])

    def test_dash_without_leading_space(self):
        r = self.ground("pkg/core.py:3— `lane_is_live` is defined here")
        self.assertTrue(r["ok"])
        self.assertEqual((r["grounded"], r["total"]), (1, 1))

    def test_malformed_finding(self):
        r = self.ground("somewhere in core — `x`")
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], ["somewhere in core — `x` (not path:line — fact)"])

    def test_threshold_half_is_enough(self):
        r = self.ground("pkg/core.py:3 — `lane_is_live` is defined here", "pkg/nope.py:1 — `x` gone")
        self.assertTrue(r["ok"])
        self.assertEqual((r["grounded"], r["total"]), (1, 2))

    def test_threshold_below_half(self):
        r = self.ground(
            "pkg/core.py:3 — `lane_is_live` is defined here",
            "pkg/nope.py:1 — `x` gone",
            "pkg/core.py:21 — `OTHER` is set",
        )
        self.assertFalse(r["ok"])
        self.assertEqual((r["grounded"], r["total"]), (1, 3))

    def test_no_findings(self):
        r = hb_ground.ground_code("PATTERNS:\n- uses os.path\n", self.root)
        self.assertFalse(r["ok"])
        self.assertEqual((r["grounded"], r["total"]), (0, 0))

    def test_passthrough_and_result(self):
        text = (
            "FINDINGS:\n"
            "- pkg/core.py:3 — `lane_is_live` is defined here\n"
            "- pkg/core.py:3 — `OTHER` is set here\n"
            "PATTERNS:\n"
            "- uses os.path\n"
            "RISKS:\n"
            "- none known beyond races\n"
            "UNKNOWN:\n"
            "- who else imports pkg\n"
        )
        r = hb_ground.ground_code(text, self.root)
        self.assertTrue(r["ok"])
        self.assertEqual(r["passthrough"]["RISKS"], ["none known beyond races"])
        self.assertEqual(
            r["result"],
            "FINDINGS (grounded):\n"
            "- pkg/core.py:3 — `lane_is_live` is defined here\n"
            "PATTERNS (lane-reported):\n"
            "- uses os.path\n"
            "RISKS (lane-reported):\n"
            "- none known beyond races\n"
            "UNKNOWN (lane-reported):\n"
            "- who else imports pkg",
        )


PYPI_URL = "https://pypi.org/pypi/httpx/json"
FETCH = {
    "tool": "webfetch",
    "status": "completed",
    "input": {"url": PYPI_URL, "format": "text"},
    "output": '{"info": {"version": "0.28.1"}, "upload_time":   "2024-12-06T15:37:21"}\n'
              "HTTPX is a fully featured HTTP client for Python 3.",
}
SEARCH = {
    "tool": "websearch",
    "status": "completed",
    "input": {"query": "httpx changelog"},
    "output": "Title: Changelog\nURL: https://www.python-httpx.org/changelog/\n"
              "Text: The 0.28.0 release drops the deprecated verify and cert arguments.",
}
EXECUTE = {
    "tool": "execute",
    "status": "completed",
    "input": {"code": "fetch('https://pypi.org/pypi/httpx/json')"},
    "output": "latest upload 2024-12-06T15:37:21",
}
C_FETCH = ('Latest httpx is 0.28.1 — official — https://pypi.org/pypi/httpx/json — 2024-12-06 — '
           '"HTTPX is a FULLY featured   HTTP client"')
C_SEARCH = ('0.28 drops verify and cert — official — https://www.python-httpx.org/changelog — '
            '2024-11-28 — "drops the deprecated verify and cert arguments"')
C_ABSENT = ('httpx supports HTTP/3 — blog — https://pypi.org/pypi/httpx/json — 2024-12-06 — '
            '"supports HTTP/3 natively"')
C_PROBE = ('httpx 0.28.1 was released on 2024-11-28 — official — https://pypi.org/pypi/httpx/json — '
           '2024-11-28 — "2024-11-28"')
NOT_IN_TOOLS = " (quote not in session tool output)"


def web(*claims, answer="httpx 0.28.1 is the latest release."):
    lines = []
    if answer:
        lines.append("ANSWER: " + answer)
    lines.append("CLAIMS:")
    lines.extend("- " + c for c in claims)
    return "\n".join(lines) + "\n"


class GroundWebTests(unittest.TestCase):
    def test_quote_in_webfetch_output(self):
        r = hb_ground.ground_web(web(C_FETCH), [FETCH])
        self.assertTrue(r["ok"])
        self.assertEqual((r["grounded"], r["total"]), (1, 1))
        self.assertEqual(r["items"], [C_FETCH])
        self.assertEqual(r["unverified"], [])
        self.assertEqual(r["answer"], ["httpx 0.28.1 is the latest release."])

    def test_quote_and_url_from_search_result(self):
        r = hb_ground.ground_web(web(C_SEARCH), [SEARCH])
        self.assertTrue(r["ok"])
        self.assertEqual(r["items"], [C_SEARCH])

    def test_quote_absent(self):
        r = hb_ground.ground_web(web(C_ABSENT), [FETCH])
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [C_ABSENT + NOT_IN_TOOLS])

    def test_quote_only_in_model_text(self):
        claim = ('released recently — official — https://pypi.org/pypi/httpx/json — 2024-12-06 — '
                 '"is the latest release, published 2024-12-06"')
        text = web(claim, answer="0.28.1 is the latest release, published 2024-12-06.")
        r = hb_ground.ground_web(text, [FETCH])
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [claim + NOT_IN_TOOLS])

    def test_execute_output_does_not_count(self):
        claim = ('upload date — official — https://pypi.org/pypi/httpx/json — 2024-12-06 — '
                 '"latest upload 2024-12-06"')
        r = hb_ground.ground_web(web(claim), [EXECUTE])
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [claim + NOT_IN_TOOLS])

    def test_probe_regression_misreported_date(self):
        r = hb_ground.ground_web(web(C_PROBE), [FETCH, EXECUTE])
        self.assertFalse(r["ok"])
        self.assertEqual(r["grounded"], 0)
        self.assertEqual(r["unverified"], [C_PROBE + NOT_IN_TOOLS])

    def test_quote_only_in_grep_output(self):
        claim = ('httpx 0.28.1 upload — official — https://pypi.org/pypi/httpx/json — 2024-12-06 — '
                 '"released from the grep corpus only"')
        grep = {"tool": "grep", "status": "completed", "input": {"pattern": "released"},
                "output": "tool-output/abc:3: Released from the grep   corpus only today"}
        fetch = dict(FETCH, output="unrelated body")
        r = hb_ground.ground_web(web(claim), [fetch, grep])
        self.assertTrue(r["ok"])
        self.assertEqual(r["items"], [claim])
        self.assertEqual(r["unverified"], [])

    def test_url_not_fetched(self):
        claim = ('httpx is full featured — official — https://example.com/httpx — 2024-12-06 — '
                 '"HTTPX is a fully featured HTTP client"')
        r = hb_ground.ground_web(web(claim), [FETCH])
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [claim + " (URL not fetched or searched)"])

    def test_failed_tool_does_not_count(self):
        r = hb_ground.ground_web(web(C_FETCH), [dict(FETCH, status="error")])
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [C_FETCH + NOT_IN_TOOLS])

    def test_missing_answer(self):
        r = hb_ground.ground_web(web(C_FETCH, answer=None), [FETCH])
        self.assertFalse(r["ok"])
        self.assertEqual(r["grounded"], 1)

    def test_claim_without_quote(self):
        claim = "httpx is fast — blog — https://pypi.org/pypi/httpx/json — 2024-12-06 — no quote here"
        r = hb_ground.ground_web(web(claim), [FETCH])
        self.assertEqual(r["unverified"], [claim + " (no quote)"])

    def test_sentinel_line_ignored(self):
        text = web(C_FETCH) + "UNVERIFIED:\n- HB-LANE-OK\n"
        r = hb_ground.ground_web(text, [FETCH])
        self.assertTrue(r["ok"])
        self.assertEqual(r["unverified"], [])

    def test_url_fragment_and_scheme_equal(self):
        claim = ('httpx is full featured — official — https://pypi.org/pypi/httpx/json#info — '
                 '2024-12-06 — "HTTPX is a fully featured HTTP client"')
        fetch = dict(FETCH, input={"url": "http://pypi.org/pypi/httpx/json", "format": "text"})
        r = hb_ground.ground_web(web(claim), [fetch])
        self.assertTrue(r["ok"])
        self.assertEqual(r["unverified"], [])

    def test_url_fragment_after_trailing_slash(self):
        claim = ('httpx is full featured — official — https://pypi.org/pypi/httpx/json/#info — '
                  '2024-12-06 — "HTTPX is a fully featured HTTP client"')
        r = hb_ground.ground_web(web(claim), [FETCH])
        self.assertTrue(r["ok"])
        self.assertEqual(r["unverified"], [])

    def test_short_quote_not_grounded(self):
        claim = 'httpx works — official — https://pypi.org/pypi/httpx/json — 2024-12-06 — "works"'
        r = hb_ground.ground_web(web(claim), [FETCH])
        self.assertFalse(r["ok"])
        self.assertEqual(r["unverified"], [claim + " (quote too short)"])

    def test_partial_with_lane_unverified_and_passthrough(self):
        text = web(C_FETCH, C_ABSENT) + (
            "UNVERIFIED:\n"
            "- maintainers plan HTTP/3\n"
            "VERSION_NOTES:\n"
            "- 0.28 removed verify/cert kwargs\n"
        )
        r = hb_ground.ground_web(text, [FETCH])
        self.assertTrue(r["ok"])
        self.assertEqual((r["grounded"], r["total"]), (1, 2))
        self.assertEqual(r["unverified"], [C_ABSENT + NOT_IN_TOOLS, "maintainers plan HTTP/3"])
        self.assertEqual(r["passthrough"]["VERSION_NOTES"], ["0.28 removed verify/cert kwargs"])
        self.assertEqual(
            r["result"],
            "ANSWER:\n"
            "- httpx 0.28.1 is the latest release.\n"
            "CLAIMS (grounded):\n"
            "- " + C_FETCH + "\n"
            "VERSION_NOTES (lane-reported):\n"
            "- 0.28 removed verify/cert kwargs",
        )


if __name__ == "__main__":
    unittest.main()
