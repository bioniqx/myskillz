---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything: which files to touch, actual code, how to test, what to commit. Assume a skilled developer who knows nothing about our toolset, problem domain, or good test design. DRY. YAGNI. TDD. Frequent commits.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Save plans to:** `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md` (user preferences override).
**Scratch dir for parallel work:** `docs/superpowers/plans/.work/<feature-name>/` — deleted after assembly.

**Speed doctrine:** the slow part of planning is writing task bodies with real code. Never write them serially when there are 4+ tasks — lock the contracts once, then fan task bodies out to parallel subagents (max 64, all dispatched in a single message). Serial effort goes only where divergence is possible: the Contract Table.

## Scope Check

If the spec covers multiple independent subsystems, suggest one plan per subsystem — each producing working, testable software on its own. Independent subsystem plans can themselves be built concurrently (split the 64-agent budget between them).

## Pipeline

### Route (decide during the single spec read)

| Estimated tasks | Path |
|---|---|
| ≤ 3 | **Inline**: write the whole plan in one pass, then run Final Checks yourself. Subagent overhead isn't worth it. |
| 4+ | **Fan-out**: Phases 1–3 below. |

Read the spec exactly once; estimate the task count during that read.

### Phase 1 — Skeleton (serial; this is where quality is locked)

Write the plan file with:

1. **Header + Global Constraints** (template below)
2. **File Structure** — every file created/modified, one clear responsibility each. Prefer small focused files; split by responsibility, not technical layer; follow existing codebase patterns.
3. **Contract Table** — one row per task: task number/name, files, and **exact** Produces/Consumes signatures (function names, parameter and return types, verbatim). This is the single source of truth parallel writers copy from. Ambiguous signatures are the *only* way parallel writing diverges — spend the effort here, not in review.

Then write one brief per task at `.work/<feature>/briefs/task-NN.md` (zero-padded NN). Each brief is **self-sufficient** — a writer never reads the spec:

- Verbatim spec excerpts relevant to this task (copy, don't summarize)
- Its own Contract Table row + the rows it consumes
- Global Constraints (copy them in — writers don't open the plan file)
- Exact file paths (Create / Modify / Test)

### Phase 2 — Fan-out (parallel, max 64)

Dispatch **all** task writers in **ONE message** so they run concurrently — one `Task` (general-purpose) per task:

- N ≤ 64 → one writer per task.
- N > 64 → chunk *contiguous* tasks (⌈N/64⌉ per writer) so writers never exceed 64. Contiguous chunks keep consumed contracts local.

Each writer writes only its own file `.work/<feature>/tasks/task-NN.md` — isolated outputs, zero write contention, no shared state. Use the Task Writer Prompt below verbatim, pasting in the Task Structure template.

### Phase 3 — Assemble + Verify (mechanical, fast)

1. **Assemble** with a single command — zero-padded names guarantee order:
   `cat .work/<feature>/tasks/task-*.md >> docs/superpowers/plans/<plan>.md`
2. **Signature check:** grep each Contract Table signature against the assembled plan. Any mismatch → fix inline. Contracts were locked in Phase 1, so consistency is a grep, not a re-read.
3. **Placeholder scan:** grep the assembled plan for `TBD|TODO|implement later|appropriate error handling|similar to Task`. Hits → fix inline.
4. **Coverage skim:** each spec section maps to a task. Gap → write the missing task inline (or dispatch one more writer).
5. **Plans > 10 tasks:** dispatch parallel reviewers per `plan-document-reviewer-prompt.md`, sharded into contiguous task ranges, all in ONE message. Fix real issues; ignore advisory notes.
6. Delete `.work/<feature>/`.

Fix-and-move-on: never re-run a full review after a fix.

## Task Writer Prompt

```
You are writing Task NN of an implementation plan. Everything you need is in
this prompt and your brief. Do NOT read the spec, the plan, or explore the
codebase. You MAY read only files listed under "Modify" in your brief.

Brief: <absolute path to .work/<feature>/briefs/task-NN.md>
Write EXACTLY one file: <absolute path to .work/<feature>/tasks/task-NN.md>

Format — follow exactly:
<paste the Task Structure template here>

Rules:
- Copy Interfaces signatures VERBATIM from your brief's contract rows.
- Bite-sized steps, one action each (2–5 min), TDD cycle per behavior:
  write failing test → run to see it fail (exact command + expected failure)
  → minimal implementation → run to see it pass → commit.
- Real code in every code step. The implementer sees ONLY your task file.
- Banned content (self-check before returning): "TBD", "TODO", "implement
  later", "add appropriate error handling/validation", tests described but
  not written, "similar to Task N", any symbol not defined in your brief.
- Return only the text: "task-NN written". Do not echo the task body.
```

## Plan Document Header

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

## Global Constraints

[The spec's project-wide requirements — version floors, dependency limits,
naming and copy rules, platform requirements — one line each, exact values
copied verbatim from the spec. Every task implicitly includes this section.]

---
```

## Task Structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Interfaces:**
- Consumes: [what this task uses from earlier tasks — exact signatures]
- Produces: [what later tasks rely on — exact names, parameter and return
  types. A task's implementer sees only their own task; this block is how
  they learn what neighboring tasks expect.]

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## Task Right-Sizing

A task is the smallest unit that carries its own test cycle and is worth a fresh reviewer's gate. Fold setup, configuration, scaffolding, and docs into the task whose deliverable needs them; split only where a reviewer could reject one task while approving its neighbor. Each task ends with an independently testable deliverable.

## No Placeholders

Every step must contain the actual content an engineer needs. **Plan failures** — never write, always scan for:

- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — tasks may be read out of order)
- Steps describing *what* without *how* (code blocks required for code steps)
- References to types/functions/methods not defined in any task

## Final Checks (inline path only)

Fan-out plans are verified in Phase 3. For inline plans, check yourself: (1) every spec requirement maps to a task; (2) placeholder scan per the list above; (3) signatures used in later tasks match earlier definitions exactly. Fix inline; no re-review.

## Execution Handoff

After saving the plan, offer:

**"Plan complete and saved to `docs/superpowers/plans/<filename>.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration. Independent tasks (per the Contract Table) may execute concurrently.

**2. Inline Execution** — execute in this session via executing-plans, batch execution with checkpoints.

**Which approach?"**

- Subagent-Driven → REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`
- Inline → REQUIRED SUB-SKILL: `superpowers:executing-plans`
