# Parallel Spec Review — Reviewer Dispatch Templates

Dispatch ALL FOUR reviewers below **in a single message** (four
concurrent subagent calls). Each reviewer owns one lens, so they never
duplicate work and the whole review costs one subagent round instead
of four. Merge their findings, fix inline, no re-review loop.

**Dispatch after:** spec document is written to `docs/superpowers/specs/`

**Shared prompt skeleton** — instantiate once per reviewer, filling
`[LENS]` and `[LENS_INSTRUCTIONS]`:

```
Subagent (general-purpose), one call per lens, all four in ONE message:
  description: "Spec review: [LENS]"
  prompt: |
    You are a spec reviewer with exactly one lens: [LENS].
    Ignore everything outside your lens — other reviewers cover it.

    **Spec to review:** [SPEC_FILE_PATH]

    [LENS_INSTRUCTIONS]

    ## Calibration

    Only flag issues that would cause real problems during
    implementation planning. Minor wording, stylistic preferences, and
    "less detailed than other sections" are NOT issues. Approve unless
    there are serious gaps that would lead to a flawed plan.

    ## Output Format (keep it short)

    **Lens:** [LENS]
    **Status:** Approved | Issues Found
    **Issues (if any):**
    - [Section X]: [specific issue] - [why it matters for planning]
    **Recommendations (advisory, non-blocking):** [max 3, or "none"]
```

## The Four Lenses

| # | LENS | LENS_INSTRUCTIONS |
|---|------|-------------------|
| 1 | Completeness | Hunt for TODOs, placeholders, "TBD", empty or missing sections, requirements stated but never specified. |
| 2 | Consistency | Hunt for internal contradictions: sections that conflict, architecture that doesn't match feature descriptions, data flows that reference components the spec doesn't define. |
| 3 | Clarity & Ambiguity | Hunt for requirements ambiguous enough that two competent implementers would build different things. For each, state the two readings. |
| 4 | Scope & YAGNI | Is this focused enough for ONE implementation plan, or does it span independent subsystems needing decomposition? Flag unrequested features and over-engineering. |

## Merging

1. Collect the four reports (they arrive together).
2. Union the issues; drop duplicates.
3. Fix every issue inline in the spec. Use judgment on advisory
   recommendations.
4. Do NOT re-dispatch reviewers after fixing — fix and move on to the
   user review gate.
