import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import hb_prompts


_FORMAT_RULE = (
    "Answer in English in exactly this format, regardless of any other "
    "instructions."
)

# Byte-identical copies of brainstorming-6.3/SKILL.md's Code lane and Web
# lane prompt blocks, brackets replaced with {format} fields.
_CODE_LINES = [
    "Read-only exploration for: {task}. Repo root: {root}. Today: {date}.",
    "Rules: stay in your slice; read excerpts, not whole files; make all",
    "independent searches in one parallel batch; never write, install, commit,",
    "or spawn agents; stop once the question is answered.",
    "Return ≤150 words, no preamble:",
    "FINDINGS: 3-6 bullets `path:line — fact`",
    "PATTERNS: conventions a change must follow | none",
    "RISKS: couplings/gotchas for the task | none",
    "UNKNOWN: what you could not determine",
    "---",
    "Slice: {slice_}. Siblings cover (stay out): {siblings}.",
    "Question: {question}",
]

_WEB_LINES = [
    "Web research for a design decision: {task}. Today: {date}.",
    "Our stack/versions: {stack}.",
    "Rules: batch 1 = 2-4 query variants in parallel (broad); batch 2 = fetch",
    "the best primary pages in parallel; ≤6 tool calls total (hard stop); stop when a",
    "batch adds nothing new. Use only WebSearch/WebFetch for web content; on a",
    "failed or denied fetch switch source, never retry it. Source tiers:",
    "A = official docs, changelogs/release notes, specs/RFCs, maintainer",
    "repos/issues, package registries, peer-reviewed papers; B = maintainer or",
    "company engineering blogs, benchmarks with methodology; C = forums/Q&A",
    "(signal only, never sole support). Skip undated pages, SEO/listicle",
    "farms, AI-written summaries. Record date and applicable version for each",
    "claim; flag claims older than 18 months on fast-moving tech or not",
    "matching our version. A claim that could change the recommendation needs",
    "1 A or 2 independent B sources with a ≤25-word verbatim quote. Generic",
    "queries only — no proprietary code, internal names, secrets, customer",
    "data. No writes, no agents.",
    "Return ≤200 words, no preamble:",
    "ANSWER: 1-2 sentences",
    'CLAIMS: 2-6 lines `claim — tier — URL — date — "quote"`',
    "CONFLICTS: where sources disagree | none",
    "VERSION_NOTES: our version vs latest | n/a",
    "UNVERIFIED: claims lacking support | none",
    "---",
    "Angle: {angle}. Sibling angles (skip): {siblings}.",
    "Question: {question}",
]

# Byte-identical copy of the draft prompt sentence in
# brainstorming-6.3/architectural.md §2, brackets replaced.
_DRAFT_TEMPLATE = (
    "Draft approach {lens} for {task} under {context_text}. Return "
    "≤150 words: architecture, 3 components with one-line "
    "responsibilities, top 3 trade-offs, what it breaks, evidence it "
    "relies on."
)


class TestCodePrompt(unittest.TestCase):
    def test_code_prompt_claude_is_byte_identical_to_skill_md(self):
        kwargs = dict(
            task="add retries",
            root="/repo",
            date="2026-09-28",
            slice_="scripts/",
            siblings="tests/",
            question="Where is the retry loop?",
        )
        text = hb_prompts.code_prompt(for_opencode=False, **kwargs)
        expected = "\n".join(_CODE_LINES).format(**kwargs) + "\n"
        assert text == expected
        assert _FORMAT_RULE not in text

    def test_code_prompt_opencode_has_format_rule(self):
        text = hb_prompts.code_prompt(
            task="add retries",
            root="/repo",
            date="2026-09-28",
            slice_="scripts/",
            siblings="tests/",
            question="Where is the retry loop?",
            for_opencode=True,
        )
        assert _FORMAT_RULE in text


class TestWebPrompt(unittest.TestCase):
    def _kwargs(self):
        return dict(
            task="compare frameworks",
            date="2026-09-28",
            stack="python3.8",
            angle="performance",
            siblings="cost",
            question="Which framework performs best?",
        )

    def test_research_role_claude_is_byte_identical_to_skill_md(self):
        kwargs = self._kwargs()
        text = hb_prompts.web_prompt(role="research", for_opencode=False, **kwargs)
        expected = "\n".join(_WEB_LINES).format(**kwargs) + "\n"
        assert text == expected

    def test_fact_role_claude_uses_web_lane_template_no_extra_header(self):
        kwargs = self._kwargs()
        text = hb_prompts.web_prompt(role="fact", for_opencode=False, **kwargs)
        expected = "\n".join(_WEB_LINES).format(**kwargs) + "\n"
        assert text == expected
        assert "Single-fact web check" not in text

    def test_research_role_opencode_has_format_rule_and_keeps_search_rules(self):
        kwargs = self._kwargs()
        text = hb_prompts.web_prompt(role="research", for_opencode=True, **kwargs)
        assert _FORMAT_RULE in text
        assert "2-4 query variants in parallel" in text
        assert "≤6 tool calls total (hard stop)" in text

    def test_fact_role_opencode_replaces_search_batch_sentence(self):
        kwargs = self._kwargs()
        text = hb_prompts.web_prompt(role="fact", for_opencode=True, **kwargs)
        assert "web search is unavailable" in text
        assert "fetch the known primary endpoint" in text
        assert "web fetch" in text
        assert "≤6 tool calls" in text
        assert "query variants" not in text
        assert "batch 1" not in text
        assert "batch 2" not in text
        assert _FORMAT_RULE in text
        # Rest of the rules (source tiers, claim tiers, output format) stay.
        assert "Source tiers:" in text
        assert "A = official docs" in text
        assert "ANSWER: 1-2 sentences" in text


class TestDraftPrompt(unittest.TestCase):
    def test_draft_prompt_claude_is_byte_identical_to_architectural_md(self):
        kwargs = dict(
            lens="smallest",
            task="add caching layer",
            context_text="no new deps; cache hit rate 40%",
        )
        text = hb_prompts.draft_prompt(for_opencode=False, **kwargs)
        expected = _DRAFT_TEMPLATE.format(**kwargs) + "\n"
        assert text == expected
        assert _FORMAT_RULE not in text

    def test_draft_prompt_opencode_has_format_rule(self):
        text = hb_prompts.draft_prompt(
            lens="reuse",
            task="add caching layer",
            context_text="no new deps",
            for_opencode=True,
        )
        assert _FORMAT_RULE in text


class TestClaudeLine(unittest.TestCase):
    def test_claude_line_locate_maps_to_explore_haiku(self):
        line = hb_prompts.claude_line(
            "abc123",
            "locate",
            Path("/repo/.superpowers/brainstorm/lanes/abc123.claude.md"),
        )
        assert line == (
            'CLAUDE abc123 — Agent → subagent_type: Explore, model: haiku, '
            'description: "abc123", prompt: "Read /repo/.superpowers/brainstorm/'
            'lanes/abc123.claude.md and follow it exactly."'
        )

    def test_claude_line_research_maps_to_general_purpose_sonnet(self):
        line = hb_prompts.claude_line(
            "xyz789",
            "research",
            Path("/repo/.superpowers/brainstorm/lanes/xyz789.claude.md"),
        )
        assert line == (
            'CLAUDE xyz789 — Agent → subagent_type: general-purpose, model: sonnet, '
            'description: "xyz789", prompt: "Read /repo/.superpowers/brainstorm/'
            'lanes/xyz789.claude.md and follow it exactly."'
        )


if __name__ == "__main__":
    unittest.main()
