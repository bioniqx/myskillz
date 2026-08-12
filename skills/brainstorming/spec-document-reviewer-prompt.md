# Parallel Spec Review — Dispatch Template

**When to use:** only for large or multi-component specs (>~120 lines or >3 components). Smaller specs get the inline self-review in SKILL.md Step 4 — dispatching agents for a small spec is slower than just reading it.

**How to dispatch:** ALL reviewers in ONE message so they run concurrently. Read-only. Fastest model available (haiku). 5 reviewers standard; for very large specs, shard the completeness and consistency reviewers per major section — total cap 64 concurrent.

| Reviewer | Single dimension it checks |
|----------|---------------------------|
| completeness | TODOs, placeholders, "TBD", missing/incomplete sections |
| consistency | internal contradictions; architecture vs. feature-description mismatches |
| clarity | requirements ambiguous enough to be built two different ways |
| scope | covers multiple independent subsystems / needs decomposition |
| yagni | unrequested features, over-engineering |

## Per-reviewer prompt

```
Subagent (Explore or general-purpose, model: haiku):
  description: "Spec review: [DIMENSION]"
  prompt: |
    You are a spec reviewer checking exactly ONE dimension: [DIMENSION] — [dimension description from table].

    Spec to review: [SPEC_FILE_PATH]

    Calibration: only flag issues that would cause real problems during
    implementation planning. Minor wording, stylistic preferences, and
    "this section is less detailed than others" are NOT issues.

    Output (compact, nothing else):
    STATUS: PASS | FAIL
    ISSUES:            (omit entirely if PASS)
    - [section]: [issue] — [why it matters for planning]
    NOTES: [max 2 advisory suggestions, optional]
```

## Aggregation

- Any FAIL → fix the flagged issues inline in the spec. Do NOT re-dispatch reviewers — fix and move on.
- All PASS → proceed to commit and hand-off.
- Advisory NOTES never block.
