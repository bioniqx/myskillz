"""Session-model tier vocabulary pinned across the four tuning docs.

Authoritative vocabulary: six session models (display names exactly
GLM-5.3-Flash, DeepSeek V4.1 Flash, GLM 5.3, DeepSeek V4 Pro,
Claude Sonnet 5.5), three tier words (flash tier, pro tier, Claude tier),
no numeric speed/price table rows for the new tiers, and the
brainstorming economics row for the pro model never says "not used".
"""

import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = [
    "../../z-brainstorming/z-tuning.md",
    "../../z-writing-plans/references/z-tuning.md",
    "../../z-requirements-code-audit/references/z-tuning.md",
    "../../z-systematic-debugging/references/z-tuning.md",
]
SESSION_MODELS = [
    "GLM-5.3-Flash",
    "DeepSeek V4.1 Flash",
    "GLM 5.3",
    "GLM 5.4",
    "DeepSeek V4 Pro",
    "Claude Sonnet 5.5",
]
TIER_WORDS = ["flash tier", "pro tier", "Claude tier"]
# Models that had no table row in any tuning doc before this slice.
NEW_TIER_MODELS = ["GLM 5.4", "DeepSeek V4 Pro", "Claude Sonnet 5.5"]
PINNED_PRO_RULE = "pro tier: only when the session is pinned to it"
# "GLM 5.3" counts only as its own display name, never inside a Flash name.
STANDALONE_GLM_53 = re.compile(r"GLM 5\.3(?!-Flash)")


def _read(rel):
    with open(os.path.join(HERE, rel), encoding="utf-8") as fh:
        return fh.read()


def _table_rows(text):
    return [ln for ln in text.splitlines() if ln.lstrip().startswith("|")]


def _is_new_tier_row(row):
    return any(name in row for name in NEW_TIER_MODELS)


def _has_numeric_claim(row):
    return "$" in row or "tok/s" in row


def _session_models_block(text):
    body, capture = [], False
    for ln in text.splitlines():
        if ln.startswith("## "):
            if capture:
                break
            capture = ln.strip() == "## Session models"
        elif capture:
            body.append(ln)
    return "\n".join(body)


class SessionModelNameTests(unittest.TestCase):
    """Criterion: six model names in each of the four docs."""

    def test_all_four_docs_name_the_five_session_models(self):
        for rel in DOCS:
            with self.subTest(doc=rel):
                text = _read(rel)
                for name in SESSION_MODELS:
                    if name == "GLM 5.3":
                        self.assertIsNotNone(
                            STANDALONE_GLM_53.search(text),
                            "GLM 5.3 must appear as its own display name, "
                            "not only inside GLM-5.3-Flash",
                        )
                    else:
                        self.assertIn(name, text)


class TierWordTests(unittest.TestCase):
    """Criterion: three tier words in each of the four docs."""

    def test_all_four_docs_name_the_three_tiers(self):
        for rel in DOCS:
            with self.subTest(doc=rel):
                text = _read(rel)
                for tier in TIER_WORDS:
                    self.assertIn(tier, text)


class SessionModelsBlockTests(unittest.TestCase):
    """Criterion: a Session models block exists and claims no speeds or prices."""

    def test_session_models_block_present_without_speed_or_price_numbers(self):
        for rel in DOCS:
            with self.subTest(doc=rel):
                block = _session_models_block(_read(rel))
                self.assertTrue(block, "missing a non-empty '## Session models' block")
                self.assertNotIn("$", block)
                self.assertNotIn("tok/s", block)


class Glm54RowTests(unittest.TestCase):
    """Criterion: the GLM 5.4 row sits in every table and its facts are dated."""

    def test_every_doc_carries_the_glm_5_4_row_and_a_dated_note(self):
        for rel in DOCS:
            with self.subTest(doc=rel):
                text = _read(rel)
                self.assertIn("| GLM 5.4 | pro tier |", text)
                self.assertIn("glm-5.4", text)
                self.assertIn("2026-11-25", text)

class NewTierNumericRowTests(unittest.TestCase):
    """Criterion: no numeric table rows for the new tiers."""

    def test_no_table_row_for_a_new_tier_model_carries_numbers(self):
        for rel in DOCS:
            with self.subTest(doc=rel):
                for row in _table_rows(_read(rel)):
                    if _is_new_tier_row(row):
                        self.assertFalse(_has_numeric_claim(row), row)

    def test_guard_leaves_the_pre_existing_numbered_pro_row_alone(self):
        # Edge case: the brainstorming economics table already carries numbers
        # for GLM-5.3; tier wording is added to that row without stripping them.
        row = "| GLM-5.3 | 63.4 tok/s | 1.40 | 4.40 | " + PINNED_PRO_RULE + " |"
        self.assertFalse(_is_new_tier_row(row))

    def test_guard_flags_a_numbered_row_for_a_new_tier_model(self):
        row = "| DeepSeek V4 Pro | 63 tok/s | 1.40 | 4.40 | pro tier |"
        self.assertTrue(_is_new_tier_row(row))
        self.assertTrue(_has_numeric_claim(row))


class BrainstormingProRowTests(unittest.TestCase):
    """Criterion: the pro economics row states the tier rule, never 'not used'."""

    DOC = DOCS[0]

    def test_pro_economics_row_carries_the_pinned_tier_rule(self):
        rows = _table_rows(_read(self.DOC))
        self.assertTrue(any(PINNED_PRO_RULE in row for row in rows))

    def test_no_economics_table_row_says_not_used(self):
        for row in _table_rows(_read(self.DOC)):
            self.assertNotIn("not used", row)


class DenylistRemovedTests(unittest.TestCase):
    """Edge case: the model denylist is gone from the brainstorming copy,
    from every occurrence, not just the first."""

    def test_brainstorming_keeps_no_do_not_name_denylist(self):
        text = _read(DOCS[0])
        self.assertNotIn("Do not name", text)


if __name__ == "__main__":
    unittest.main()
