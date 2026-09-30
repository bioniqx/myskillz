"""Lane prompt templates for hybrid-brainstorming."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hb_router


_FORMAT_RULE = (
    "Answer in English in exactly this format, regardless of any other "
    "instructions."
)


# Byte-identical to brainstorming-6.3/SKILL.md's Code lane fenced block,
# brackets replaced with %s fields.
_CODE_TEMPLATE = (
    "Read-only exploration for: %(task)s. Repo root: %(root)s. Today: %(date)s.\n"
    "Rules: stay in your slice; read excerpts, not whole files; make all\n"
    "independent searches in one parallel batch; never write, install, commit,\n"
    "or spawn agents; stop once the question is answered.\n"
    "Return ≤150 words, no preamble:\n"
    "FINDINGS: 3-6 bullets `path:line — fact`\n"
    "PATTERNS: conventions a change must follow | none\n"
    "RISKS: couplings/gotchas for the task | none\n"
    "UNKNOWN: what you could not determine\n"
    "---\n"
    "Slice: %(slice_)s. Siblings cover (stay out): %(siblings)s.\n"
    "Question: %(question)s"
)

# Byte-identical to brainstorming-6.3/SKILL.md's Web lane fenced block,
# brackets replaced with %s fields. Shared by role="research" and
# role="fact" when for_opencode is False — the fact role uses this same
# template, with no extra header.
_WEB_TEMPLATE = (
    "Web research for a design decision: %(task)s. Today: %(date)s.\n"
    "Our stack/versions: %(stack)s.\n"
    "Rules: batch 1 = 2-4 query variants in parallel (broad); batch 2 = fetch\n"
    "the best primary pages in parallel; ≤6 tool calls total (hard stop); stop when a\n"
    "batch adds nothing new. Use only WebSearch/WebFetch for web content; on a\n"
    "failed or denied fetch switch source, never retry it. Source tiers:\n"
    "A = official docs, changelogs/release notes, specs/RFCs, maintainer\n"
    "repos/issues, package registries, peer-reviewed papers; B = maintainer or\n"
    "company engineering blogs, benchmarks with methodology; C = forums/Q&A\n"
    "(signal only, never sole support). Skip undated pages, SEO/listicle\n"
    "farms, AI-written summaries. Record date and applicable version for each\n"
    "claim; flag claims older than 18 months on fast-moving tech or not\n"
    "matching our version. A claim that could change the recommendation needs\n"
    "1 A or 2 independent B sources with a ≤25-word verbatim quote. Generic\n"
    "queries only — no proprietary code, internal names, secrets, customer\n"
    "data. No writes, no agents.\n"
    "Return ≤200 words, no preamble:\n"
    "ANSWER: 1-2 sentences\n"
    'CLAIMS: 2-6 lines `claim — tier — URL — date — "quote"`\n'
    "CONFLICTS: where sources disagree | none\n"
    "VERSION_NOTES: our version vs latest | n/a\n"
    "UNVERIFIED: claims lacking support | none\n"
    "---\n"
    "Angle: %(angle)s. Sibling angles (skip): %(siblings)s.\n"
    "Question: %(question)s"
)

# opencode has no web-search tool: for role="fact" this replaces the
# batch/query-variant sentence with a direct-fetch instruction, keeping the
# rest of the Web lane rules (source tiers, claim tiers, output format).
_FACT_OPENCODE_RULE = (
    "Rules: web search is unavailable; fetch the known primary endpoint "
    "(registry JSON, raw README, changelog/release page) directly with web "
    "fetch; ≤6 tool calls total (hard stop). Source tiers:"
)
_WEB_SEARCH_BATCH_SENTENCE = (
    "Rules: batch 1 = 2-4 query variants in parallel (broad); batch 2 = fetch\n"
    "the best primary pages in parallel; ≤6 tool calls total (hard stop); stop when a\n"
    "batch adds nothing new. Use only WebSearch/WebFetch for web content; on a\n"
    "failed or denied fetch switch source, never retry it. Source tiers:"
)

# Byte-identical to the draft prompt sentence in
# brainstorming-6.3/architectural.md §2, brackets replaced.
_DRAFT_TEMPLATE = (
    "Draft approach %(lens)s for %(task)s under %(context_text)s. Return "
    "≤150 words: architecture, 3 components with one-line "
    "responsibilities, top 3 trade-offs, what it breaks, evidence it "
    "relies on."
)


def code_prompt(task: str, root: str, date: str, slice_: str, siblings: str, question: str, for_opencode: bool) -> str:
    text = _CODE_TEMPLATE % {
        "task": task,
        "root": root,
        "date": date,
        "slice_": slice_,
        "siblings": siblings,
        "question": question,
    }
    if for_opencode:
        text = text.replace(
            "or spawn agents; stop once the question is answered.",
            "or spawn agents; stop once the question is answered.\n" + _FORMAT_RULE,
        )
    return text + "\n"


def web_prompt(role: str, task: str, date: str, stack: str, angle: str, siblings: str, question: str, for_opencode: bool) -> str:
    text = _WEB_TEMPLATE % {
        "task": task,
        "date": date,
        "stack": stack,
        "angle": angle,
        "siblings": siblings,
        "question": question,
    }
    if role == "fact" and for_opencode:
        text = text.replace(_WEB_SEARCH_BATCH_SENTENCE, _FACT_OPENCODE_RULE)
    if for_opencode:
        text = text.replace(
            "data. No writes, no agents.",
            "data. No writes, no agents.\n" + _FORMAT_RULE,
        )
    return text + "\n"


def draft_prompt(lens: str, task: str, context_text: str, for_opencode: bool) -> str:
    text = _DRAFT_TEMPLATE % {
        "lens": lens,
        "task": task,
        "context_text": context_text,
    }
    if for_opencode:
        text = text + " " + _FORMAT_RULE
    return text + "\n"


def claude_line(lane_id: str, role: str, prompt_path: Path, model: str = "") -> str:
    """The CLAUDE line for a lane; model overrides the role's default (the run switch forces sonnet)."""
    subagent_type, role_model = hb_router.claude_agent(role)
    model = model or role_model
    return (
        "CLAUDE %s — Agent → subagent_type: %s, model: %s, "
        'description: "%s", prompt: "Read %s and follow it exactly."'
        % (lane_id, subagent_type, model, lane_id, Path(prompt_path).resolve())
    )
