---
name: brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation."
---

# Brainstorming Ideas Into Designs — Fast Path

Turn ideas into approved designs and specs in minimum wall-clock time. Two laws govern everything:

1. **User round-trips are the most expensive operation.** Batch questions, merge approval gates. Target: 2 gates total.
2. **All independent work runs in parallel.** Sequential calls for independent work are a bug.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it. This applies to EVERY project regardless of perceived simplicity.
</HARD-GATE>

## Parallel Execution Rules

- Batch ALL independent tool calls into one message: file reads, greps, git commands, subagent dispatches. Never wait on one before dispatching another independent one.
- Fan out subagents for exploration and review. **Hard cap: 64 concurrent** (beyond platform limits they queue automatically). Scale to the job: 1 direct read for a tiny project, 2–4 scouts typical, up to 8 for a large repo. Never spawn a subagent for what one direct tool call answers.
- Scouts are read-only Explore agents on the fastest model available (haiku). Reviewers use the default model.
- Anything not requiring user input proceeds without pausing. Stop only at Gate 1 and Gate 2.

## The Flow (2 user gates)

Create the full task list (one call, all tasks) at Step 1, mark items complete as you go.

### Step 1 — Parallel context scan (zero user wait)

In a single message, dispatch parallel scouts:

- **Scout A:** project structure, entry points, tech stack
- **Scout B:** docs, READMEs, existing specs in `docs/superpowers/specs/`
- **Scout C:** recent git history and current branch state
- **Scout D+** (only if the request touches specific code): the files/patterns it touches

While scouts run, draft clarifying questions from the request itself.

**Scope check first:** if the request spans multiple independent subsystems (e.g., "chat + billing + analytics"), don't refine details — propose a decomposition, then brainstorm sub-project #1 through this same flow. Each sub-project gets its own spec → plan → implementation cycle.

### Step 2 — GATE 1: One batched question round

Merge scout findings with the request, then ask ALL clarifying questions in ONE round via `AskUserQuestion` (up to 4 questions per call, multiple-choice preferred — "Other" is automatic). Cover: purpose, constraints, success criteria, scope cuts.

- No AskUserQuestion on this platform → send all questions as a single numbered list in one message.
- **Max 2 rounds.** A second round only if an answer genuinely spawns new decisions. One-question-per-message is banned.
- Trivial projects: skip Gate 1 entirely — fold the single open question into the Gate 2 message.

### Step 3 — GATE 2: Approaches + full design, one approval

One message containing all of:

1. **2–3 approaches** with trade-offs, your recommendation first, YAGNI applied to each
2. **The complete design** under the recommended approach — architecture, components, data flow, error handling, testing — each section scaled to complexity (one sentence to ~200 words)
3. **One approval ask:** approve as-is / approve with changes / switch approach

Per-section approval is banned — it costs O(sections) round-trips for O(1) information. If the user requests changes, revise and re-present the affected parts in one message.

### Step 4 — Write, review, commit, hand off (one turn, no extra gate)

On approval, do all of this in a single turn:

1. Write the spec to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (user preferences for location override). Use elements-of-style:writing-clearly-and-concisely if available.
2. **Inline self-review, fix in place:** placeholders/TBDs, internal contradictions, two-way-interpretable requirements, scope creep. No re-review loop — fix and move on.
3. **Large or multi-component specs only** (>~120 lines or >3 components): dispatch parallel per-dimension reviewers per `spec-document-reviewer-prompt.md` — all reviewers in one message. Apply fixes inline.
4. Commit the spec.
5. Close with: *"Spec written and committed to `<path>`. Say 'go' to start the implementation plan, or tell me what to change."* — the spec-review gate rides on the hand-off message; no separate round-trip.

On "go": **invoke writing-plans.** That is the ONLY terminal state. Never invoke frontend-design, mcp-builder, or any other implementation skill from here.

## Anti-Patterns (banned)

- **"Too simple to need a design."** Every project gets a design; for trivial ones it's 2–3 sentences and Gate 2 absorbs Gate 1.
- **One question per message.** Batch into rounds.
- **Per-section design approval.** One consolidated approval.
- **Sequential exploration.** Parallel scouts in one message.
- **Polling or blocking waits** on servers/subagents when independent work exists.

## Design Quality Bar

- Break the system into units with one clear purpose, well-defined interfaces, independently understandable and testable. For each unit answer: what does it do, how is it used, what does it depend on. If internals can't change without breaking consumers, boundaries need work.
- Existing codebases: follow existing patterns; include targeted improvements only where existing problems affect this work; no unrelated refactors.
- YAGNI ruthlessly — strip unrequested features from every approach and design.

## Visual Companion (lazy-loaded)

Browser companion for mockups, diagrams, visual comparisons. Offer **just-in-time** — the first time a question is genuinely clearer shown than told — never upfront. To save a round-trip, append the offer to the current question message: *"I can show these as clickable mockups in a browser tab — want that? It's still new and can be token-intensive."*

Only if accepted: read `skills/brainstorming/visual-companion.md`, then start the server with `--open` and the project dir (it backgrounds itself — never block on it). Per-question test thereafter: content that IS visual (mockups, layouts, diagrams) → browser; content that is text (requirements, trade-offs, A/B/C choices) → terminal. If declined, stay text-only and don't offer again.
