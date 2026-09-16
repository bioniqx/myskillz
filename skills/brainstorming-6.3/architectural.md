# Architectural Path — Approaches, Design, Spec

Read this only on the architectural path, after exploration and the
first question batch. It covers turns 2-4.

## Scope check (before any question)

If the request spans multiple independent subsystems, say so and
decompose into sub-projects, each with its own spec → plan →
implementation cycle. Brainstorm only the first sub-project through the
flow below. Decomposition is a design decision — state it and let the
user veto.

## Turn 2 — approaches + design, one message

**Approaches (top of message):** 2-3, each: one-line summary, 2-3
trade-offs, what it would break. Lead with your recommendation and why.
YAGNI ruthlessly — cut unrequested features from every approach. If the
repo is large, these come from the concurrent approach workers
(`fanout-playbook.md` §4); your job is to pick and sharpen, not to draft.

**Design of the recommended approach (rest of message):** sectioned,
each section labeled and scaled to its complexity — a few sentences
when straightforward, up to 200-300 words when nuanced:

1. Architecture — components and boundaries, cite existing files
2. Components — for each unit: what it does, how it is used, what it
   depends on. If internals can't change without breaking consumers,
   the boundary needs work.
3. Data flow
4. Error handling
5. Testing — what proves it works, at which level
6. Assumptions — every ≥80%-likely answer you did not ask about,
   one line each, phrased so a "yes" confirms all of them

**Close with one approval ask, inviting per-section objections:**
"Approve as-is, or tell me which section is wrong and I'll revise just
that." Revise and re-present only the changed sections.

Design principles that keep the sections short: small units with one
purpose, well-defined interfaces, independently testable; follow
existing repo patterns; include targeted improvements only where an
existing problem affects this work — no unrelated refactoring.

## Turn 3 — spec + commit + review, one turn

Do all of the following before ending the turn:

1. Write `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (user
   preferences override the path). Content = the approved design with
   the user's corrections applied. Use
   `elements-of-style:writing-clearly-and-concisely` if available.
2. In ONE message: `git add` + `git commit` of the spec AND the four
   reviewer subagents from `spec-document-reviewer-prompt.md`.
3. Merge findings, fix inline, amend or make a second commit. No
   re-review loop.
4. End the turn with the user review gate:

   > "Spec written and committed to `<path>`. Please review it and let
   > me know if you want to make any changes before we start writing
   > out the implementation plan."

Wait. If changes are requested: apply, re-run the four reviewers in one
message, commit, ask again. Proceed only on approval.

## Turn 4 — hand-off

Invoke `writing-plans`. No other skill, no code, no scaffolding.
