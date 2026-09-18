# Spec Review — Inline Self-Review First, Lanes Only When Stakes Demand

## Why inline by default

Superpowers v5.0.6 (2026-03-24) replaced its spec/plan reviewer subagent
loop after "regression testing across 5 versions with 5 trials each showed
identical quality scores regardless of whether the review loop ran"; the
loop cost ~25 minutes, while self-review "catches 3-5 real bugs per run in
~30s". Review inline. Factual risk is handled in parallel by the claim
verifier dispatched with the design message (`architectural.md` §3).

On GLM this matters more, not less: a reviewer loop is a deep chain, and
deep chains are where GLM's accuracy drops. One pass with five lenses,
held in one context, beats five handoffs.

## Inline self-review — 5 lenses, one pass, about a minute, fix in place

Run at `reasoning_effort: low`. Flag only issues that would cause real
problems during implementation planning. Wording, style, and uneven
detail are not issues.

1. **Completeness** — TODO, TBD, placeholders, empty sections,
   requirements stated but never specified.
2. **Consistency** — sections that contradict each other, data flows
   referencing undefined components, claims about existing code the repo
   contradicts (spot-check with parallel reads in one round).
3. **Clarity** — any requirement two competent implementers would build
   differently; rewrite it to one reading.
4. **Scope and YAGNI** — does it fit ONE implementation plan?
   Unrequested features or over-engineering get cut. Independent
   subsystems get decomposed.
5. **Evidence** — every load-bearing external claim has a dated source,
   verifier results are applied, unverified items are labeled as
   assumptions.

## Escalate to parallel reviewers only if

The spec touches security or auth, data migration or deletion, money, or
a public API or contract others depend on — or the user asks for a
review. Then dispatch lenses 1-4 as four `haiku` (Flash) general-purpose
lanes in ONE message; lens 5 stays with the claim verifier. Each reads
the spec itself — do not paste it. Wait for all four before the review
gate.

```
You are a spec reviewer with exactly one lens: [LENS]. Ignore everything outside it; other reviewers cover the rest.
Spec file: [SPEC_FILE_PATH].
Rules:
1 Read the spec fully before judging.
2 Read repo files only to confirm a claim the spec makes about existing code. Max 6 tool calls.
3 Flag only issues that would cause real problems during implementation planning. Wording and style are not issues.
4 Approve unless there are serious gaps.
5 Output only the four labels below. No preamble, no headings. 200 words max.
LENS: [LENS]
STATUS: Approved | Issues Found
ISSUES: one per line `[Section] — issue — why it matters for planning`
ADVISORY: up to 3 non-blocking recommendations | none
---
Lens instructions: [LENS INSTRUCTIONS from the list above]
```

Merge: union the ISSUES, drop duplicates, fix inline, one commit. No
re-review loop — go straight to the user review gate.
