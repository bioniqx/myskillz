---
name: brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation."
---

# Brainstorming Ideas Into Designs

Turn ideas into validated designs fast: classify the request, explore
context in parallel, batch your questions, present a design, get
approval.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, scaffold any
project, or take any implementation action until you have told your
human partner what you intend and they have approved it. This applies
to EVERY task on EVERY path — the ceremony scales with the task; the
approval gate never does.
</HARD-GATE>

## Speed Doctrine

Wall-clock time is dominated by (1) human round-trips and (2)
sequential tool calls. Attack both, in that order:

- **Batch questions.** Group up to 4 independent clarifying questions
  into ONE message, multiple-choice preferred (use the AskUserQuestion
  tool when available). Serialize only when an answer genuinely
  determines the next question. Never spend a round-trip on anything
  the repo can answer.
- **Fan out, never queue.** Every independent read, search, or
  subagent dispatch goes in ONE message as concurrent tool calls — up
  to 64 in parallel. If call B does not need call A's output, they run
  together.
- **Overlap machine work with human wait.** Fire exploration subagents
  BEFORE composing your first question; results land while the user
  types. While the user reviews a design or spec, pre-stage the next
  step (draft reviewer dispatches, outline the spec skeleton).
- **Scale concurrency to the task.** Spike or bounded: a handful of
  parallel reads. Architectural in a large repo: fan wide — one
  Explore subagent per subsystem, doc area, or open question, up to 64
  concurrently. Don't dispatch agents whose answers you won't use.

Parallelism never touches the gate: concurrent work is read-only
exploration, drafting, and review — never implementation.

## Three Paths

Classify before your first question and say it out loud — "this looks
bounded, so I'll present a short design here rather than write a
spec" — so your human partner can override:

- **Spike** — a feasibility question ("can we...", "is it possible...")
  whose output is an answer, not code you keep. Present question +
  probe plan in 2-3 sentences, get a nod, investigate as cheaply as
  correctness allows, report a recommendation. Anything built stays
  labeled throwaway. No design doc, no spec.
- **Bounded** — a well-scoped change to a flow that ALREADY EXISTS in
  this repo: a new flag, a small endpoint, a one-file fix.
  Understanding the kind of app is not enough — if there is no
  existing flow to read, it is not bounded. Ask the questions that
  matter (batched), present a short design IN CHAT, and STOP until you
  hear yes. No spec file, no plan document.
- **Architectural** — new projects, new subsystems, changes that
  restructure component boundaries or interfaces others depend on.
  Full process: parallel exploration, batched questions, 2-3
  approaches, sectioned design, written spec, then writing-plans.

When in doubt, take the heavier path. The ratchet is one-way: hidden
complexity discovered mid-task upgrades the path — stop, say so, step
up. Nothing downgrades mid-task.

## Red Flags

| Thought | Reality |
| --------- | --------- |
| "Too simple to need a design" | Simple means a SHORT design — two sentences in chat, then approval. Never no design. |
| "I'll call it bounded and skip the spec" | Reaching for a label to skip work IS the doubt — take the heavier path. |
| "Design is obvious — I'll start while they read it" | The gate is the approval, not the design's length. Present, then stop. |
| "I know this kind of app, so it's bounded" | Bounded measures the repo, not your familiarity. No existing flow = architectural. |
| "The spike works, so I'll keep the code" | A spike's output is an answer. Keeping code is a new request — classify it. |
| "It grew, but I'm almost done" | Hidden complexity upgrades the path mid-task. Stop and say so. |
| "They approved the spike, so the follow-up is approved" | Each task gets its own classification and approval. |
| "I'll ask questions one at a time to be thorough" | Thoroughness is WHICH questions you ask, not how many messages. Batch independent ones. |
| "More agents is always faster" | Fan-out costs tokens and merge time. Match concurrency to task size; a spike needs none. |
| "I can implement in parallel while waiting for approval" | Parallel work is exploration, drafting, review — never implementation. |

## Checklist

Classify first, announce the path, then create a task per item and
complete them in order. Steps marked ∥ run as a single concurrent
fan-out, not a sequence.

**Spike:**

1. ∥ **Explore context** — the few reads needed to frame the probe
2. **Present question + probe plan** — 2-3 sentences
3. **Get approval** — a nod is enough
4. **Investigate** — as cheaply as correctness allows
5. **Report findings** — a recommendation; label builds throwaway

**Bounded:**

1. ∥ **Explore context** — files, docs, recent commits in one parallel batch
2. **Ask clarifying questions** — batch the independent ones into one message
3. **Present short design in chat** — approach, files touched, testing
4. **Get approval** — STOP; wait for an explicit yes
5. **Implement** — normal development workflow (TDD applies); no plan doc

**Architectural:**

1. ∥ **Explore context** — fan out Explore subagents (one per subsystem/topic, up to 64) plus direct reads, all in one message
2. **Offer visual companion just-in-time** — NOT upfront; see Visual Companion below
3. **Ask clarifying questions** — batched multiple-choice sets; serialize only true dependencies
4. **Propose 2-3 approaches** — trade-offs + your recommendation; draft competing approaches with concurrent subagents when the repo is large
5. **Present design** — ALL sections in one message, each labeled and scaled to its complexity; ask for one approval, inviting per-section objections
6. **Write design doc** — `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, commit
7. ∥ **Parallel spec review** — dispatch the 4 reviewers in `spec-document-reviewer-prompt.md` in one message; merge and fix inline
8. **User reviews spec** — gate below
9. **Invoke writing-plans** — the ONLY skill you invoke next

**Terminal states are path-bound.** Architectural → writing-plans,
never any other implementation skill. Bounded → direct implementation,
no plan doc. Spike → a reported recommendation.

## The Process

(Spike stops at "present probe, get a nod". Bounded = context +
batched questions + short in-chat design. Everything below from
"Approaches" onward is architectural depth.)

**Understanding the idea:**

- Explore current project state FIRST, in parallel (files, docs, recent commits)
- Assess scope before detailed questions: if the request spans multiple
  independent subsystems, flag it and decompose into sub-projects —
  each gets its own spec → plan → implementation cycle. Brainstorm the
  first sub-project through the normal flow.
- Batch independent questions (max 4/message, multiple-choice
  preferred); split only genuinely dependent chains across messages
- Focus on purpose, constraints, success criteria

**Approaches:**

- Propose 2-3 with trade-offs; lead with your recommendation and why
- YAGNI ruthlessly — cut unnecessary features from every approach

**Presenting the design:**

- One message, sectioned: architecture, components, data flow, error
  handling, testing. A few sentences per straightforward section, up
  to 200-300 words for nuanced ones.
- Ask for approval once, inviting objections per section ("Section 3
  wrong? Tell me and I'll revise just that."). Revise and re-present
  only the changed sections.

**Design for isolation and clarity:**

- Small units, one clear purpose each, well-defined interfaces,
  independently testable
- For each unit: what does it do, how do you use it, what does it
  depend on? If internals can't change without breaking consumers, the
  boundaries need work.
- Focused files are also easier for you — you reason better about code
  you can hold in context at once

**Existing codebases:**

- Follow existing patterns. Include targeted improvements where
  existing problems affect the work; don't propose unrelated
  refactoring.

## After the Design (architectural path)

- Write the spec to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
  (user preferences override); use
  elements-of-style:writing-clearly-and-concisely if available; commit.
- **Parallel spec review:** dispatch all four reviewer subagents from
  `spec-document-reviewer-prompt.md` in a single message. Merge
  findings, fix inline, no re-review loop.
- **User review gate:**

  > "Spec written and committed to `<path>`. Please review it and let
  > me know if you want to make any changes before we start writing
  > out the implementation plan."

  Wait. If changes are requested, make them, re-run the parallel
  review, and ask again. Only proceed on approval.
- **Implementation:** invoke writing-plans. No other skill.

## Visual Companion

A browser-based companion for mockups, diagrams, and visual options.
A tool, not a mode.

**Offer just-in-time, never upfront.** Wait until a question would
genuinely be clearer shown than told — a real mockup/layout/diagram
question, not merely a UI topic. Then offer, as its own message (no
other content), and wait:

> "This next part might be easier if I show you — I can put together
> mockups, diagrams, and comparisons in a browser tab as we go. It's
> still new and can be token-intensive. Want me to? I'll open it for
> you."

If declined, continue text-only and don't offer again unless they
raise it. If accepted, read `skills/brainstorming/visual-companion.md`
before proceeding and start the server with `--open`.

**Per-question test, even after acceptance:** would the user
understand this better by SEEING it? Mockups, wireframes, layout
comparisons, architecture diagrams → browser. Requirements, tradeoff
lists, A/B/C text options, scope → terminal. A question about a UI
topic is not automatically a visual question.
