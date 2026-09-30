# Architectural Path — Design, Spec, Hand-off

Read in round 1 (alongside the fan-out). Covers everything from the first
lane results to `writing-plans`.

## 1. Merge or split the first message

- **Merge (default):** goal and key constraints are clear, no open
  question would change WHICH approaches are viable, and all lanes fit
  under the subagent cap. Send the design message (§2) as soon as the
  lanes that decide the approach set are back; fold later lanes into the
  spec. While decisive T1 lanes are still running, end the turn with one
  status line ("Exploring N code + M web lanes; design follows") — don't
  poll. Budget: 2 human turns.
- **Split:** the request is too open to design (unknown users, goal, or a
  constraint that eliminates whole approaches), or lanes exceed the cap
  and must run in waves. Send the questions + assumptions right away
  while lanes keep running; the user thinks while machines work. Next
  message is the design. Budget: 3 human turns.

Decomposition (multi-subsystem request → sub-projects, first one only)
is stated inside whichever message goes first; the user can veto it
there without spending a turn.

## 2. The design message

**Approaches (top):** 2-3, each: one-line summary, 2-3 trade-offs, what it
would break, and the evidence line that most supports or undermines it.
Lead with your recommendation and why. YAGNI: cut unrequested features.

For large or contested problems, draft approaches with 2-3 parallel
`sonnet` lanes, each forced onto a different lens so they don't converge
on the same idea: (a) maximum reuse of existing repo patterns, (b) current
best practice per the web evidence, (c) smallest change that ships the
goal. Prompt: "Draft approach [lens] for [TASK] under [constraints + key
findings + evidence lines]. Return ≤150 words: architecture, 3 components
with one-line responsibilities, top 3 trade-offs, what it breaks, evidence
it relies on." Pick and sharpen; don't draft from scratch.

**Design of the recommended approach:** labeled sections, each scaled to
its complexity (a few sentences → ≤250 words when nuanced):

1. Architecture — components and boundaries; cite existing files.
2. Components — per unit: purpose, how it's used, dependencies. If
   internals can't change without breaking consumers, fix the boundary.
3. Data flow.
4. Error handling.
5. Testing — what proves it works, at which level.
6. Evidence — 2-7 lines `claim — [source](url) (YYYY-MM-DD)`; unverified
   items labeled; version gap between the repo and the latest release.
7. Assumptions — every ≥80%-likely answer you didn't ask about, one line
   each, phrased so one "yes" confirms all of them.

Keep sections short: small single-purpose units, well-defined
interfaces, independently testable; follow existing repo patterns;
targeted improvements only where an existing problem affects this work.

**Close with one approval ask** (first AskUserQuestion item if used):
"Approve as-is, answer the questions, or name the section that's wrong
and I'll revise just that."

## 3. Leave lanes running while the user reads (same turn as §2)

Launch these background lanes and then write the design message
immediately in the same turn — never wait for them before sending the
design. Their results are consumed in the spec turn (§4).

- **Claim verifier** (1 `sonnet` general-purpose lane) — only if the
  design rests on web-sourced claims. Prompt: "For each claim below, open
  the cited URL and any newer primary source; return per line `claim —
  SUPPORTED | CONTRADICTED | UNCLEAR — ≤25-word quote — better source if
  any`, ≤200 words. WebSearch/WebFetch only." Paste the Evidence lines.
  Cited links often work while the page doesn't support the claim, so
  check the few claims that decide the design.
- **Spec pre-draft** (1 lane) — only when file writes won't raise a
  permission prompt (acceptEdits, auto, or bypass mode). Use a `fork` if
  the harness offers one (it inherits the conversation); otherwise
  `general-purpose` with the design pasted. It writes the spec to
  `.superpowers/drafts/<topic>-design.md` (never the specs path), does not
  commit, and returns only the path. Rejected design → overwrite later.
- **Runner-up approach** (1 `sonnet` lane) — only when the top two
  approaches are close; it fleshes out the runner-up's sections so "use B
  instead" costs one re-present, not a new exploration.

Don't start work the user's reply is likely to invalidate wholesale.

## 4. After approval — spec turn (one turn, no intermediate message)

1. If a pre-draft lane is still running, stop it (TaskStop) and write the
   spec yourself. Otherwise move the draft to
   `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (user preferences
   override the path) and apply the user's corrections and the verifier's
   results with targeted edits. No draft → write the spec from the
   approved design. Content = the approved design, including Evidence and
   Assumptions. Use `elements-of-style:writing-clearly-and-concisely` if
   available.
2. Inline self-review per `spec-document-reviewer-prompt.md` (5 lenses,
   about a minute); fix in place. Escalate to parallel reviewers only
   under that file's criteria, and wait for all of them.
3. `git add` + `git commit` the spec (one commit, after fixes).
4. End the turn with the review gate:

   > "Spec written and committed to `<path>`. Please review it and let me
   > know if you want to make any changes before we start writing out the
   > implementation plan."

Changes requested → apply, re-run the self-review on the changed
sections, commit, ask again. Proceed only on approval.

## 5. Hand-off

Invoke `writing-plans`. No other skill, no code, no scaffolding.
