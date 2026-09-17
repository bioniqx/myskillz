---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything: which files to touch, actual code, how to test, what to commit. Assume a skilled developer who knows nothing about our toolset, problem domain, or good test design. DRY. YAGNI. TDD. Frequent commits.

**The plan is a model-agnostic artifact.** Any AI agent (Claude, GPT, Gemini, Copilot, Cursor, local models) or human engineer must be able to execute it with nothing but the plan file and a shell. The *process* below may use Claude-specific tooling (subagents); the *output* never does. See "Model-Agnostic Output Rules".

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Save plans to:** `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md` (user preferences override).
**Scratch dir for parallel work:** `docs/superpowers/plans/.work/<feature-name>/` — deleted after assembly.

**Speed doctrine:** the slow part of planning is writing task bodies with real code. Never write them serially when there are 4+ tasks — lock the contracts once, then fan task bodies out to parallel subagents (max 64, all dispatched in a single message). Serial effort goes only where divergence is possible: the Contract Table.

## Model-Agnostic Output Rules

The assembled plan must satisfy all of these (aligned with the AGENTS.md convention and GitHub Spec Kit's task format — the current cross-vendor standards):

1. **Plain CommonMark only.** No YAML beyond standard fenced code blocks, no tool-specific syntax, no XML directives.
2. **Zero tool/vendor references inside the plan.** Banned in the output: "skill", "sub-skill", "subagent", "superpowers", "Claude", "dispatch", or any instruction that assumes a specific product. The executor is addressed as "you" (an AI agent or engineer).
3. **Self-contained.** Everything needed is in the plan: the Execution Protocol (header template below), Global Constraints, and full task bodies. The executor never needs the spec, this skill, or the codebase docs.
4. **Executable commands only.** Every run step is an exact shell command plus expected output. No "run the tests" — always `pytest tests/x.py::test_y -v` / `Expected: PASS`.
5. **Explicit dependencies.** Each task declares `Depends on:` (task IDs or `none`). Tasks safe to run in parallel with other `[P]` tasks (disjoint files, dependencies satisfied) carry a `[P]` marker in their heading. This lets any orchestrator — single-threaded or multi-agent — schedule correctly without parsing prose.
6. **Repo conventions defer to `AGENTS.md`.** If the target repo has an `AGENTS.md`/`CLAUDE.md`, copy its build/test/style commands into Global Constraints verbatim rather than referencing the file.

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
3. **Contract Table** — one row per task: task ID/name, files, `Depends on`, and **exact** Produces/Consumes signatures (function names, parameter and return types, verbatim). This is the single source of truth parallel writers copy from. Ambiguous signatures are the *only* way parallel writing diverges — spend the effort here, not in review. Derive each task's `Depends on:` line and `[P]` marker from this table.

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
4. **Portability scan:** grep the assembled plan (case-insensitive) for `skill|subagent|superpowers|claude|dispatch`. Any hit inside the plan body violates Model-Agnostic Output Rules → rewrite inline in neutral terms.
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
- Copy the "Depends on" task IDs and [P] marker from your brief's contract row.
- Bite-sized steps, one action each (2–5 min), TDD cycle per behavior:
  write failing test → run to see it fail (exact command + expected failure)
  → minimal implementation → run to see it pass → commit.
- Real code in every code step. The implementer sees ONLY your task file.
- The implementer may be ANY AI model or a human: plain Markdown only, no
  references to tools, skills, subagents, or vendors — address them as "you".
- Banned content (self-check before returning): "TBD", "TODO", "implement
  later", "add appropriate error handling/validation", tests described but
  not written, "similar to Task N", any symbol not defined in your brief,
  any tool/vendor/skill reference.
- Return only the text: "task-NN written". Do not echo the task body.
```

## Plan Document Header

```markdown
# [Feature Name] Implementation Plan

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

## Execution Protocol

This plan is self-contained: you (an AI agent or engineer) need only this
file and a shell. Do not consult external specs or documents.

1. Read Global Constraints and this protocol fully before starting.
2. Execute tasks in ID order (Task 1, Task 2, …). A task may start only
   when every task in its "Depends on" list is complete. Tasks marked
   `[P]` may run in parallel with other `[P]` tasks whose file lists do
   not overlap — if you cannot run tasks in parallel, ID order is always
   correct.
3. Within a task, follow the steps exactly in order. Mark each checkbox
   `- [x]` as you complete it.
4. Run every command exactly as written and compare against the stated
   expected output. If a "verify it fails" step passes, or a "verify it
   passes" step fails, STOP — fix within the current task before moving on.
   Never skip or reorder verification steps.
5. Commit after each task using the commit step provided. Never batch
   commits across tasks.
6. If a step is impossible as written (missing file, changed API), stop and
   report the exact step and error rather than improvising a workaround.

## Global Constraints

[The spec's project-wide requirements — version floors, dependency limits,
naming and copy rules, platform requirements, plus build/test commands
copied verbatim from the repo's AGENTS.md if one exists — one line each,
exact values copied verbatim. Every task implicitly includes this section.]

---
```

## Task Structure

````markdown
### Task N [P]: [Component Name]

*(`[P]` only if parallel-safe; omit otherwise)*

**Depends on:** [task IDs, or "none"]

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
- Tool/vendor/skill references inside the plan body (violates Model-Agnostic Output Rules)

## Final Checks (inline path only)

Fan-out plans are verified in Phase 3. For inline plans, check yourself: (1) every spec requirement maps to a task; (2) placeholder scan per the list above; (3) signatures used in later tasks match earlier definitions exactly; (4) portability scan — no tool/vendor/skill references in the plan body. Fix inline; no re-review.

## Execution Handoff

After saving the plan, offer:

**"Plan complete and saved to `docs/superpowers/plans/<filename>.md`. The plan is self-contained — any AI agent or engineer can execute it by following its Execution Protocol. Execution options:**

**1. Subagent-Driven here (recommended in this session)** — fresh subagent per task, review between tasks, fast iteration. Tasks marked `[P]` with disjoint files may execute concurrently.

**2. Inline Execution here** — execute in this session, batch execution with checkpoints.

**3. Hand off to another agent/tool** — give any AI coding agent (or engineer) the plan file; the embedded Execution Protocol is all it needs.

**Which approach?"**

- Subagent-Driven → REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`
- Inline → REQUIRED SUB-SKILL: `superpowers:executing-plans`
- Hand off → no further action; the plan file is the deliverable.
