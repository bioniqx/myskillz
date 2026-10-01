# Spec Review — Inline Self-Review First, Subagents Only When Stakes Demand

## Why inline by default

Superpowers v5.0.6 (2026-03-24) replaced its spec/plan reviewer subagent
loop after "regression testing across 5 versions with 5 trials each showed
identical quality scores regardless of whether the review loop ran"; the
loop cost ~25 minutes, while self-review "catches 3-5 real bugs per run in
~30s". Review inline. Factual risk is handled in parallel by the claim
verifier dispatched with the design message (`architectural.md` §3).

## Inline self-review — 5 lenses, one pass, about a minute, fix in place

Flag only issues that would cause real problems during implementation
planning. Wording, style, and uneven detail are not issues.

1. **Completeness** — TODO, TBD, placeholders, empty sections,
   requirements stated but never specified.
2. **Consistency** — sections that contradict each other, data flows
   referencing undefined components, claims about existing code the repo
   contradicts (spot-check with parallel reads in one round).
3. **Clarity** — any requirement two competent implementers would build
   differently; rewrite it to one reading.
4. **Scope & YAGNI** — fits ONE implementation plan? Unrequested features
   or over-engineering → cut. Independent subsystems → decompose.
5. **Evidence** — every load-bearing external claim has a dated source;
   verifier results applied; unverified items labeled as assumptions.

## Escalate to parallel reviewers only if

The spec touches security/auth, data migration or deletion, money, or a
public API/contract others depend on — or the user asks for a review.
Then dispatch lenses 1-4 as four `sonnet` general-purpose lanes in ONE
message (lens 5 stays with the claim verifier). Each reads the spec
itself — don't paste it. Wait for all four before the review gate.

```
You are a spec reviewer with exactly one lens: [LENS]. Ignore everything
outside it — other reviewers cover the rest.
Spec: [SPEC_FILE_PATH]. Read it fully. Read repo files only to confirm a
claim the spec makes about existing code.
[LENS INSTRUCTIONS from the list above]
Calibration: flag only issues that would cause real problems during
implementation planning. Approve unless there are serious gaps.
Return ≤200 words, no preamble:
LENS: [LENS]
STATUS: Approved | Issues Found
ISSUES: one per line `[Section] — issue — why it matters for planning`
ADVISORY: ≤3 non-blocking recommendations | none
```

Merge: union ISSUES, drop duplicates, fix inline, one commit. No
re-review loop — go straight to the user review gate.
