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

## Portability Rule (the plan is the product)

The *process* below may use Claude-specific machinery (subagents, skills, the Task tool). The *product* — the plan file — must not. The finished plan is a self-contained, plain-Markdown document executable by **any** AI agent (Claude, DeepSeek, Qwen, GLM, Codex, Gemini, …) or human engineer with only a shell, an editor, and git. This follows the AGENTS.md / Spec Kit conventions that cross-agent tooling standardized on: plain Markdown, checkbox steps, sequential task IDs (`T01`, `T02`, …), explicit `Depends:` lists, and a `[P]` marker on tasks safe to run in parallel.

Concretely, the plan body must NEVER contain:

- References to vendor tools, skills, sub-skills, subagents, plugins, or slash commands ("use superpowers:X", "dispatch a Task agent", "invoke skill Y")
- Instructions that only work in one harness ("open a new Claude session", "use your Edit tool")
- Anything the executor can't do with shell + editor + git

Everything the executor needs travels inside the plan: the Execution Protocol, Global Constraints, real code, exact commands, and expected outputs.

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

1. **Header + Execution Protocol + Global Constraints** (template below)
2. **File Structure** — every file created/modified, one clear responsibility each. Prefer small focused files; split by responsibility, not technical layer; follow existing codebase patterns.
3. **Contract Table** — one row per task: task ID (`TNN`, zero-padded, matching brief/task file numbering), name, **Depends** (task IDs that must complete first, or "—"), **[P]** if parallel-safe (no shared files with any other `[P]` task, no dependency on an incomplete task), files, and **exact** Produces/Consumes signatures (function names, parameter and return types, verbatim). This is the single source of truth parallel writers copy from. Ambiguous signatures are the *only* way parallel writing diverges — spend the effort here, not in review.

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
4. **Portability scan:** grep the assembled plan (case-insensitive) for `superpowers|sub-skill|subskill|subagent|slash command|Task tool|Claude|Anthropic|Copilot|Cursor|skill:`. Any hit in the plan body → rewrite that line in tool-neutral language (plain shell commands, plain instructions). The plan must run on any model.
5. **Coverage skim:** each spec section maps to a task. Gap → write the missing task inline (or dispatch one more writer).
6. **Plans > 10 tasks:** dispatch parallel reviewers per `plan-document-reviewer-prompt.md`, sharded into contiguous task ranges, all in ONE message. Fix real issues; ignore advisory notes.
7. Delete `.work/<feature>/`.

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
- Copy the Depends list and [P] marker VERBATIM from your brief's contract row.
- Bite-sized steps, one action each (2–5 min), TDD cycle per behavior:
  write failing test → run to see it fail (exact command + expected failure)
  → minimal implementation → run to see it pass → commit.
- Real code in every code step. The implementer sees ONLY your task file.
- The implementer may be ANY AI model or a human: write plain instructions
  and shell commands only — never reference skills, subagents, plugins,
  vendor tools, or any specific AI product.
- Banned content (self-check before returning): "TBD", "TODO", "implement
  later", "add appropriate error handling/validation", tests described but
  not written, "similar to Task N", any symbol not defined in your brief,
  any vendor/tool/skill/subagent reference.
- Return only the text: "task-NN written". Do not echo the task body.
```

## Plan Document Header

````markdown
# [Feature Name] Implementation Plan

> **Execution note:** This plan is self-contained and tool-agnostic. Any AI
> agent or human engineer can execute it with only a shell, a code editor,
> and git. No specific AI product, skill, or plugin is required. Follow the
> Execution Protocol below.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

## Execution Protocol (for any AI agent or human engineer)

1. Execute tasks in ID order (T01, T02, …). A task may start only when every
   task in its **Depends** list is complete.
2. Tasks marked `[P]` touch disjoint files and have no incomplete
   dependencies: an orchestrator that supports parallel workers MAY run them
   concurrently; a single agent simply runs them in ID order. Never run two
   tasks that modify the same file at the same time.
3. Within a task, execute steps top to bottom. Mark each checkbox `- [x]`
   when done — the checkboxes are the progress ledger; to resume an
   interrupted run, continue from the first unchecked step.
4. Run every command exactly as written and compare the output to the stated
   Expected result. On mismatch, stop and fix before continuing — never
   proceed past a failing step.
5. Code blocks are the implementation — copy them verbatim. Signatures in
   each task's **Interfaces** block are contracts with other tasks: do not
   rename, reorder parameters, or change types.
6. Commit exactly where the plan says to commit, with the given message.
   Never batch commits across tasks.
7. Global Constraints below apply to every task.
8. If anything is ambiguous, missing, or contradicts the codebase, STOP and
   ask the requester. Do not invent behavior.

## Global Constraints

[The spec's project-wide requirements — version floors, dependency limits,
naming and copy rules, platform requirements — one line each, exact values
copied verbatim from the spec. Every task implicitly includes this section.]

---
````

## Task Structure

````markdown
### T[NN]: [Component Name] [P]

**Depends:** T[XX], T[YY] (or "—")

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

`[P]` appears only when the Contract Table marks the task parallel-safe; omit it otherwise.

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
- References to skills, subagents, plugins, or any specific AI product/tool (the plan must be executable by any model or human)

## Final Checks (inline path only)

Fan-out plans are verified in Phase 3. For inline plans, check yourself: (1) every spec requirement maps to a task; (2) placeholder scan per the list above; (3) portability scan — no vendor/tool/skill/subagent references, Execution Protocol present; (4) signatures used in later tasks match earlier definitions exactly; (5) every task has an ID, a Depends line, and correct `[P]` marking. Fix inline; no re-review.

## Execution Handoff

After saving the plan, offer:

**"Plan complete and saved to `docs/superpowers/plans/<filename>.md`. The plan is self-contained — any AI agent or engineer can execute it by following its embedded Execution Protocol. Execution options:**

**1. Subagent-Driven here (recommended in this session)** — fresh subagent per task, review between tasks, fast iteration. Tasks marked `[P]` in the Contract Table may execute concurrently.

**2. Inline Execution here** — execute in this session, batch execution with checkpoints.

**3. Hand off to another agent/model** — give the plan file to any coding agent (DeepSeek, Qwen, GLM, Codex, Gemini, a human, …) with the single instruction: *"Execute this plan following its Execution Protocol."* Nothing else is needed.

**Which approach?"**

- Subagent-Driven → REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`
- Inline → REQUIRED SUB-SKILL: `superpowers:executing-plans`
- Hand off → no further action; the plan document carries everything.
