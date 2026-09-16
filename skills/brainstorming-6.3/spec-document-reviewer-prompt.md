# Parallel Spec Review — Reviewer Dispatch

Dispatch ALL FOUR reviewers **in the same message as the git commit of
the spec** (one Bash call + four `Agent` calls). Each owns one lens, so
nothing is duplicated and the review costs one round. Merge, fix
inline, no re-review loop.

`subagent_type: "general-purpose"`, `model: "sonnet"` where the harness
accepts it. Each reviewer reads the spec itself — do not paste it.

## Prompt skeleton (fill `[LENS]`, `[LENS_INSTRUCTIONS]`, `[SPEC_FILE_PATH]`)

```
description: "Spec review: [LENS]"
prompt: |
  You are a spec reviewer with exactly one lens: [LENS]. Ignore
  everything outside it — other reviewers cover the rest.

  Spec: [SPEC_FILE_PATH]. Read it fully. Read repo files only to
  confirm a claim the spec makes about existing code.

  [LENS_INSTRUCTIONS]

  Calibration: flag only issues that would cause real problems during
  implementation planning. Wording, style, and "less detailed than
  other sections" are NOT issues. Approve unless there are serious gaps
  that would lead to a flawed plan.

  Return EXACTLY this, ≤200 words, no preamble:
  LENS: [LENS]
  STATUS: Approved | Issues Found
  ISSUES: (one per line) `[Section] — issue — why it matters for planning`
  ADVISORY: ≤3 non-blocking recommendations, or "none"
```

## The four lenses

| # | LENS | LENS_INSTRUCTIONS |
| --- | --- | --- |
| 1 | Completeness | Hunt for TODOs, placeholders, "TBD", empty or missing sections, requirements stated but never specified. |
| 2 | Consistency | Hunt for internal contradictions: sections that conflict, architecture that doesn't match feature descriptions, data flows referencing components the spec never defines, claims about existing code that the repo contradicts. |
| 3 | Clarity & Ambiguity | Hunt for requirements ambiguous enough that two competent implementers would build different things. For each, state the two readings. |
| 4 | Scope & YAGNI | Is this focused enough for ONE implementation plan, or does it span independent subsystems needing decomposition? Flag unrequested features and over-engineering. |

## Merging

1. The four reports arrive together. Union the ISSUES; drop duplicates.
2. Fix every issue inline in the spec. Use judgment on ADVISORY items.
3. Commit the fix. Do NOT re-dispatch reviewers — go straight to the
   user review gate.
