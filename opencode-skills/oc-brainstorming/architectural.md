# Architectural Path — Design, Spec, Hand-off

Read in round 1, alongside the fan-out. Covers everything from the first
lane results to `oc-writing-plans`. SKILL.md's R0-R12 still apply; this file
adds the shape of the messages.

## 1. Merge or split the first message

**Merge (default).** Goal and key constraints are clear, no open question
would change WHICH approaches are viable, and all lanes fit under the
`lanes=` ceiling (max 8). Send the design message (§2) as soon as the lanes that
decide the approach set are back; fold later lanes into the spec. While
decisive lanes are still running, end the turn with one status line
("Exploring N code + M web lanes; design follows") — do not poll. Budget:
2 human turns.

**Split.** The request is too open to design (unknown users, goal, or a
constraint that eliminates whole approaches), or lanes exceed the cap and
must run in waves. Send questions + assumptions right away while lanes
keep running; the user thinks while machines work. Next message is the
design. Budget: 3 human turns.

Decomposition (multi-subsystem request → sub-projects, first one only) is
stated inside whichever message goes first, so the user can veto it there
without spending a turn.

## 2. The design message

**Approaches (top).** 2-3, each with: a one-line summary, 2-3 trade-offs,
what it would break, and the evidence line that most supports or
undermines it. Lead with your recommendation and why. YAGNI: cut
unrequested features.

For large or contested problems, draft approaches with 2-3 parallel
background lanes (`subagent`, agent `general`), each forced onto a
different lens so they do not converge: (a) maximum reuse of existing
repo patterns, (b) current best practice per the web evidence, (c)
smallest change that ships the goal. Send the template below as the
`prompt`.

```
Draft one design approach. Lens: [LENS]. Task: [TASK].
Constraints: [CONSTRAINTS]. Key findings: [FINDINGS]. Evidence: [EVIDENCE LINES].
Rules:
1 Stay inside your lens even if another looks better; siblings cover the others.
2 No tool calls unless a fact is missing; then 2 at most.
3 Output only the five labels below. No preamble, no headings. 150 words max.
ARCHITECTURE: 2-3 sentences
COMPONENTS: 3 lines `name — one-line responsibility`
TRADEOFFS: top 3, one line each
BREAKS: what this would break | nothing
RELIES_ON: the evidence lines this depends on
```

Pick and sharpen. Do not draft from scratch.

**Design of the recommended approach.** Labeled sections, each scaled to
its complexity — a few sentences, up to ~250 words when genuinely
nuanced:

1. Architecture — components and boundaries; cite existing files.
2. Components — per unit: purpose, how it is used, dependencies. If
   internals cannot change without breaking consumers, fix the boundary.
3. Data flow.
4. Error handling.
5. Testing — what proves it works, at which level.
6. Evidence — 2-7 lines `claim — [source](url) (YYYY-MM-DD)`; unverified
   items labeled; the version gap between the repo and the latest release.
7. Assumptions — every ≥80%-likely answer you did not ask about, one line
   each, phrased so one "yes" confirms all of them.

Keep sections short: small single-purpose units, well-defined interfaces,
independently testable; follow existing repo patterns; targeted
improvements only where an existing problem affects this work.

**Close with one approval ask** (the first `question` item if used):
"Approve as-is, answer the questions, or name the section that is wrong
and I will revise just that."

## 3. Leave lanes running while the user reads (same turn as §2)

Launch these, then write the design message immediately in the same turn.
Never wait for them. Their results are consumed in the spec turn (§4).
All three run as background `subagent` lanes (agent `general`).

- **Claim verifier** — one lane, only if the design rests on web-sourced
  claims. Cited links often work while the page does not support the
  claim, so check the few claims that decide the design.

```
Verify claims against their sources. Today: [DATE].
Rules:
1 websearch/webfetch only. Max 6 tool calls. Search failing or asking for input: webfetch primary URLs.
2 Open the cited URL; if it does not settle the claim, look for one newer primary source.
3 A failed or denied fetch is switched, never retried.
4 Output one line per claim, nothing else. No preamble. 200 words max.
Format: `claim — SUPPORTED | CONTRADICTED | UNCLEAR — verbatim quote of 25 words or less — better source if any`
---
Claims:
[PASTE THE EVIDENCE LINES]
```

- **Spec pre-draft** — the main session writes it, not a lane: `oc-explorer`
  and `oc-researcher` are `edit: deny`, and `general` may stop on a write
  prompt. Write it to `.oc-brainstorm/drafts/<topic>-design.md` (never the
  specs path) as the last call of the design turn, and do not commit it.
  A rejected design is overwritten later.
- **Runner-up approach** — one lane, only when the top two approaches are
  close. It fleshes out the runner-up's sections so "use B instead" costs
  one re-present, not a new exploration.

Do not start work the user's reply is likely to invalidate wholesale.

## 4. After approval — spec turn (one turn, no intermediate message)

This turn is formatting and targeted edits, not judgment: do not
re-deliberate the design.

1. Move the pre-draft, if you wrote one, to
   `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` (user preferences
   override the path) and apply the user's corrections and the verifier's
   results with targeted edits. No draft → write the spec from the
   approved design. Content = the approved design, including Evidence and
   Assumptions.
2. Inline self-review per `spec-document-reviewer-prompt.md` — five
   lenses, one pass, about a minute; fix in place. Escalate to parallel
   reviewers only under that file's criteria, and wait for all of them.
3. Commit the spec (`git add` + `git commit`, one commit, after fixes)
   only when neither the user nor a loaded project or user instruction
   file says not to commit self-initiated files; otherwise leave the spec
   untracked.
4. End the turn with the review gate:

   > "Spec written and committed to `<path>`. Please review it and let me
   > know if you want to make any changes before we start writing out the
   > implementation plan."

   If the commit was skipped, say so instead: "Spec written to `<path>`
   (not committed, per your instructions). Please review it and let me
   know if you want to make any changes before we start writing out the
   implementation plan."

Changes requested → apply, re-run the self-review on the changed sections
only, commit if committing, ask again. Proceed only on approval.

## 5. Hand-off

Invoke `oc-writing-plans`; if no skill with that exact name is installed,
invoke `writing-plans`. Pass the spec path
(`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, or the path user
preferences chose), committed or not, as its input. No other skill, no
code, no scaffolding.
