# Plan Document Reviewer Prompt Template

Use when dispatching plan reviewer subagents (Phase 3, step 6 of writing-plans).

**Purpose:** Verify the plan is complete, matches the spec, has proper task decomposition, and is portable — executable by any AI model or human engineer.

**Dispatch after:** The plan is fully assembled.

## Sharding (parallel review)

- **≤ 10 tasks:** one reviewer, whole plan.
- **> 10 tasks:** shard into contiguous task ranges (~5–10 tasks per shard, never more than 64 reviewers) and dispatch ALL shards in **ONE message** so they run concurrently. Each shard reviewer checks only its range; cross-task signature consistency is already covered by the Contract Table grep, so shards don't need each other's content.
- Reviewers do judgment work, not generation — a smaller/faster model is acceptable here.
- Merge results: any shard reporting Issues → fix those tasks inline. No re-review after fixes.

## Prompt (per shard)

```
Subagent (general-purpose):
  description: "Review plan tasks TNN–TMM"
  prompt: |
    You are a plan document reviewer. Verify this plan is complete and ready
    for implementation. Review ONLY Tasks TNN–TMM.

    **Plan to review:** [PLAN_FILE_PATH]
    **Spec sections for these tasks:** [SPEC_FILE_PATH or verbatim excerpts —
    prefer excerpts so the reviewer reads nothing else]

    ## What to Check

    | Category | What to Look For |
    |----------|------------------|
    | Completeness | TODOs, placeholders, incomplete tasks, missing steps |
    | Spec Alignment | Tasks cover their spec requirements, no major scope creep |
    | Task Decomposition | Clear boundaries, actionable steps, correct Depends lists, valid [P] markers (parallel tasks share no files) |
    | Buildability | Could an engineer follow each task without getting stuck? |
    | Portability | The task must be executable by ANY AI model or a human using only a shell, an editor, and git. Flag any reference to a skill, sub-skill, subagent, plugin, slash command, vendor tool, or specific AI product, and any instruction that assumes a particular harness. |

    ## Calibration

    **Only flag issues that would cause real problems during implementation.**
    An implementer building the wrong thing or getting stuck is an issue.
    A task that only one vendor's model could execute is an issue.
    Minor wording, stylistic preferences, and "nice to have" suggestions are not.

    Approve unless there are serious gaps — missing requirements, contradictory
    steps, placeholder content, vendor-locked instructions, or tasks too vague
    to act on.

    ## Output Format (keep it short — no prose beyond this)

    **Status:** Approved | Issues Found

    **Issues (if any):**
    - [Task TXX, Step Y]: [specific issue] - [why it matters]

    **Recommendations (advisory, never block):**
    - [suggestions]
```

**Reviewer returns:** Status, Issues (if any), Recommendations — nothing else.
