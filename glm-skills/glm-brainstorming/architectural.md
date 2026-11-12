# Architectural Path — Design, Spec, Hand-off

Read in round 1, alongside the fan-out. Covers everything from the first
lane results to `glm-writing-plans`. SKILL.md's R0-R12 still apply; this file
adds the shape of the messages. If `ask.py mode` printed `MODE fast`,
`fast.md` replaces the question in §2 and the review gate in §4. Do not ask.

## 1. Merge or split the first message

**Merge (default).** Goal and key constraints are clear, no open question
would change WHICH approaches are viable, and all lanes fit under the
`lanes=` width. Send the design message (§2) as soon as the lanes that
decide the approach set are back; fold later lanes into the spec. While
decisive lanes are still running, end the turn with one status line
("Exploring N code + M web lanes; design follows") — do not poll. Budget:
2 human turns.

**Split.** The request is too open to design (unknown users, goal, or a
constraint that eliminates whole approaches), or lanes exceed `lanes=` (default 8,
hard max 8) and must run in waves. Send questions + assumptions right away while lanes
keep running; the user thinks while machines work. Next message is the
design. Budget: 3 human turns.

Decomposition (multi-subsystem request → sub-projects, first one only) is
stated inside whichever message goes first, so the user can veto it there
without spending a turn.

## 2. The design message

**Approaches (top).** 2-3, each with: a one-line summary, 2-3 trade-offs,
what it would break, and the evidence line that most supports or
undermines it. Put each on its own line as `APPROACH 1:` (the recommendation),
`APPROACH 2:`, and `APPROACH 3:` only when a real third exists.
`check.py send` fails an Architectural draft with fewer than 2. YAGNI: cut
unrequested features.

For large or contested problems, draft approaches with 2-3 parallel
`glm-drafter` lanes (built-in general-purpose if that agent is not installed), each forced onto a different lens so they
do not converge: (a) maximum reuse of existing repo patterns, (b)
current best practice per the web evidence, (c) smallest change that
ships the goal. A contested lens is not picked here. `decide.py score`
prints `DECISION`; render that option.

```
Draft one design approach. Lens: [LENS]. Task: [TASK].
Constraints: [CONSTRAINTS]. Key findings: [FINDINGS]. Evidence: [EVIDENCE LINES].
Rules:
1 Stay inside your lens even if another looks better; siblings cover the others.
2 No tool calls unless a fact is missing; then 2 at most.
3 Output only the five labels below. No preamble, no headings. 150 words max. Counts are maximums.
ARCHITECTURE: 2-3 sentences
COMPONENTS: up to 3 lines `name — one-line responsibility`; fewer is fine
TRADEOFFS: top 3, one line each
BREAKS: what this would break | nothing
RELIES_ON: the evidence lines this depends on
```

Render the option the DECISION line named. Do not draft another approach
and do not change the pick.

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
   Every line must come from `check.py web` output marked OK or WEAK
   (SKILL.md R14); a WEAK line is labelled unverified.
7. Assumptions — every ≥80%-likely answer you did not ask about, one line
   each, phrased so one "yes" confirms all of them.
8. Out of scope — one line naming what this design deliberately will not do,
   so the approval covers the exclusion too.

Keep sections short: small single-purpose units, well-defined interfaces,
independently testable; follow existing repo patterns; targeted
improvements only where an existing problem affects this work.

**Close with the R6 ask**, including the exact line `Approve this design?`
so one reply both answers and approves. `check.py send` treats that line
as the design message and requires Out of scope and Assumptions.

## 3. No extra lanes on the design turn

Do not launch a claim verifier, a runner-up, or a spec pre-draft. Each
one finishes later and wakes a full thinking pass, and `check.py close`
already gates the claims and the pick (SKILL.md R8). Write the design
in the same turn, after `check.py close` prints `DECISION` and `check.py send` accepts the draft. Do not start work the user's
reply is likely to invalidate wholesale.

## 4. After approval — spec turn (one turn, no intermediate message)

Stay on the effort pinned in the agent file. This turn is formatting
and targeted edits, in one message.

1. Write the spec to `docs/specs/YYYY-MM-DD-<topic>-design.md` (user
   preferences override the path) from the approved design, applying the
   user's corrections with targeted edits. Content = the approved design, including Evidence,
   Assumptions and Out of scope. Use `elements-of-style:writing-clearly-and-concisely` if
   available.
2. Lint the spec: run `python3 <skill_dir>/scripts/check.py spec <spec path>`.
   Fix every FAIL in place. A WARN may stay only if you can justify it in
   one clause.
   Then the inline self-review per `spec-document-reviewer-prompt.md` — five
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

Invoke `glm-writing-plans` (the name this port installs under). Pass the
spec path as its input: the committed path
(`docs/specs/YYYY-MM-DD-<topic>-design.md`, or the path user
preferences chose), or the untracked path when the commit was skipped. No
other skill, no code, no scaffolding.
