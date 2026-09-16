---
name: brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation. Optimized for minimum human round-trips and maximum parallel exploration (up to 64 concurrent subagents)."
---

# Brainstorming Ideas Into Designs

Turn ideas into approved designs in the fewest possible human turns:
classify, fan out exploration, ask once, present once, get approval.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, scaffold any
project, or take any implementation action until you have told your
human partner what you intend and they have approved it. Every task,
every path. Ceremony scales with the task; the approval gate never does.
</HARD-GATE>

## Speed Doctrine

Wall-clock = human round-trips (seconds to hours each) + sequential
tool calls (seconds each) + tokens you load. Attack in that order.

1. **Turn budget is a hard target.** Spike: 2 human turns. Bounded: 2.
   Architectural: 3-4. Count before you send; if you are over, merge
   messages (see "Merge Rules").
2. **Assume, don't ask.** If the repo, conventions, or the request make
   an answer ≥80% likely, state it as an assumption inside the design
   ("Assuming Postgres like the rest of `/services` — say otherwise").
   The user corrects in the same reply that approves. Ask a real
   question only when the answer forks the design.
3. **One message, one fan-out.** Every independent read, grep, or
   subagent goes in ONE message as concurrent tool calls, up to 64.
   If B does not need A's output, they run together. Never queue.
4. **Overlap machine work with human wait.** Fire exploration BEFORE
   your first question; while the user reads a design or spec,
   background work (drafts, reviewers, further exploration) is already
   running. See `fanout-playbook.md` for the mechanics.
5. **Load only what this path needs.** Spike/Bounded: this file only.
   Architectural: read `architectural.md` when you reach the approaches
   step, `spec-document-reviewer-prompt.md` when the spec is written,
   `visual-companion.md` only if the companion is accepted.

Parallelism never touches the gate: concurrent work is read-only
exploration, drafting, and review — never implementation.

## Merge Rules (how the turn budget is met)

- **Questions + provisional design in one message.** Present the design
  built on your assumptions, with the ≤4 forking questions attached
  (AskUserQuestion when available, multiple-choice). One reply from the
  user answers and approves, or answers and you re-present only the
  changed sections.
- **Approaches + recommended design in one message** (architectural):
  2-3 approaches with trade-offs, then the full sectioned design of the
  one you recommend. If they pick another, re-present the delta.
- **Write spec + commit + parallel review in one turn**, then the single
  user review gate. Never a separate "I wrote the spec" message before
  review.
- **Visual-companion offer rides along with the first question batch**
  when a visual question is foreseeable — never as its own message.
- Serialize only when an answer determines which question comes next.

## Three Paths

Classify before your first message and say it out loud ("this looks
bounded — short design in chat, no spec") so the user can override.
When in doubt, take the heavier path. The ratchet is one-way: hidden
complexity discovered mid-task upgrades the path — stop, say so, step
up. Nothing downgrades mid-task.

- **Spike** — feasibility question ("can we…", "is it possible…");
  output is an answer, not code you keep. Turn 1: question + probe plan
  (2-3 sentences) + any cheap reads already done. Turn 2: findings and
  recommendation; anything built is labeled throwaway. No doc, no spec.
- **Bounded** — well-scoped change to a flow that ALREADY EXISTS in this
  repo (new flag, small endpoint, one-file fix). Familiarity with the
  kind of app is not enough — no existing flow to read means it is not
  bounded. Turn 1: fan-out reads → short design in chat (approach, files
  touched, testing) + assumptions + ≤4 forking questions. Turn 2: yes →
  implement with the normal workflow (TDD applies). No spec, no plan doc.
- **Architectural** — new projects, new subsystems, changes that
  restructure boundaries or interfaces others depend on. Turn 1: fan
  out Explore subagents (one per subsystem/doc area/open question, up
  to 64) + direct reads in one message → scope check → batched
  questions with assumptions. Turn 2: approaches + recommended design,
  all sections, one approval. Turn 3: spec written, committed, reviewed
  by 4 parallel reviewers, fixed inline → user review gate. Turn 4:
  invoke writing-plans — the ONLY skill you invoke next.

**Terminal states are path-bound.** Architectural → writing-plans, never
another implementation skill. Bounded → direct implementation. Spike →
a reported recommendation.

## Checklist

Create one task per step; ∥ marks a single concurrent fan-out.

**Spike:** ∥ explore (few reads) → present question + probe plan → nod
→ investigate as cheaply as correctness allows → report recommendation.

**Bounded:** ∥ explore (files, docs, recent commits, one batch) →
design-in-chat + assumptions + batched questions → STOP for explicit
yes → implement.

**Architectural:** ∥ explore (Explore subagents + reads, ≤64, one
message; read `fanout-playbook.md` for partitioning) → scope check
(multi-subsystem? decompose into sub-projects, brainstorm the first) →
batched questions + assumptions (+ companion offer if visual questions
are foreseeable) → read `architectural.md` → approaches + design in one
message → one approval → spec to
`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` + commit + ∥ 4
reviewers (`spec-document-reviewer-prompt.md`) in one turn → fix inline
→ user review gate → writing-plans.

## Red Flags

| Thought | Reality |
| --- | --- |
| "Too simple to need a design" | Simple = two-sentence design in chat, then approval. Never no design. |
| "I'll call it bounded and skip the spec" | Reaching for a label to skip work IS the doubt — go heavier. |
| "Design is obvious — I'll start while they read" | The gate is the approval, not the design's length. |
| "I know this kind of app, so it's bounded" | Bounded measures the repo, not you. No existing flow = architectural. |
| "It grew, but I'm almost done" | Hidden complexity upgrades the path mid-task. Stop and say so. |
| "I'll ask one question per message to be thorough" | Thoroughness is WHICH questions, not how many messages. Batch. |
| "I'll ask instead of assuming, to be safe" | An assumption the user can veto costs zero turns; a question costs one. |
| "More agents is always faster" | Fan-out costs tokens and merge time. A spike needs none; a monorepo needs dozens. |
| "The spike worked, so I'll keep the code" | A spike's output is an answer. Keeping code is a new request — classify it. |
| "I can implement while waiting for approval" | Parallel work is exploration, drafting, review — never implementation. |

## Visual Companion (summary)

Browser tab for mockups, diagrams, side-by-side layouts. A tool, not a
mode. Offer only when a question is clearer shown than told, folded into
the question batch as one option: "Want mockups/diagrams in a browser
tab as we go? (new, token-heavier)". If declined, don't re-offer. If
accepted, read `visual-companion.md` and start the server with
`--open`. Per-question test still applies: layouts and diagrams →
browser; requirements, trade-offs, scope → terminal.
