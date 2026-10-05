---
name: oc-brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, choosing a library or architecture, or modifying behavior. Turns intent into an approved design in the fewest human turns: repo context in one call, wide parallel lanes across the codebase AND the live web (current docs, releases, best practices), cited evidence, one approval gate before any implementation. Use for: 'build/add/implement X', 'how should we design or architect X', picking the best current approach, library, framework, or service for something we will build, new projects or subsystems, refactors that change interfaces, and 'can we / is it possible' feasibility spikes."
metadata:
  version: "10.0"
---

# Brainstorming → Approved Design

Classify → fan out wide in one round → decide on evidence → ask once →
present once → get approval. Lower rule number wins a conflict.

## Live context (one call)

Run `sh <Base directory>/scripts/oc-context.sh` as a round-1 call, with the
"Base directory for this skill" path in place of `<Base directory>`. If a
context block with a `harness:` line is already in the conversation (the
`/oc-brainstorm` command runs the script first), use it and skip the call.
Trust the block: never re-run `ls`, `find`, `git status`, or `cat` on
manifests. Reference files live in `skill_dir`; read by absolute path.

## R0 — The gate

Do not write code, scaffold, run an implementation skill, or touch any
file outside `.oc-brainstorm/` until you have told your human partner
what you intend and they said yes. Inside `.oc-brainstorm/` write only
the spec pre-draft (`drafts/`) and, once the user accepts the visual
companion, its screens and state (the session folder the start script
creates). Every task, every path. Parallel work is read-only:
exploration, research, drafting, review. Ceremony scales with the task;
R0 never does.

## R1 — Classify; open your first message with it

First line: `Path: <Spike|Bounded|Architectural> — <one-line reason>`.
Hidden complexity found mid-task upgrades the path (stop, say so).
Nothing downgrades. In doubt, go heavier.

- **Spike** — "can we / is it possible", or "what is the best way" with
  nothing to build yet. Output is an answer, not kept code. Round 1:
  relevant reads + web searches. Message: answer-so-far with sources + a
  2-3 sentence probe plan, optional if the docs already settle it. Nod →
  probe cheaply → recommendation. Anything built is labeled throwaway.
  No doc, no spec.
- **Bounded** — well-scoped change to a flow that ALREADY EXISTS here
  (flag, small endpoint, field, one-file fix). No existing flow to read =
  not bounded. Direct calls only, plus 2-6 lanes in a large or
  unfamiliar repo. Message: short design (approach, files, testing) +
  Evidence if researched + assumptions + ≤4 forking questions. Explicit
  yes → implement with the normal workflow (TDD applies).
- **Architectural** — new projects or subsystems, or changes to
  boundaries and interfaces others depend on. Decomposition check first:
  independent subsystems → plan lanes for the first sub-project only.
  Round 1, one message: direct reads + direct searches for single-hop
  questions + lanes for multi-hop ones + `Read architectural.md`, then
  follow it. The ONLY skill you invoke next is `oc-writing-plans`
  (fallback `writing-plans`, only when no skill with that exact name is
  installed).

Human replies before hand-off: Spike 1-2 · Bounded 1-2 · Architectural
2-3. Count before sending; over budget → merge messages.

## R2 — Lane economics

Every lane runs on the model selected in this OpenCode window. Never pass
a model or variant to `subagent`; the lane agents declare none.

1. One lane per question that needs several reads or searches. Never
   spawn a lane for what one direct call answers.
2. Give each lane one slice, a tool-call cap and a word cap (the agent
   bodies carry them). Small bounded lanes are what make width cheap.
3. The main thread does classification, merge, design, final message —
   nothing a lane can do.
4. Lanes never write files. Drafts and specs are written by the main
   session.

## R3 — Spend thought where it decides

Dispatch rounds, lane merging, spec formatting and re-presenting one
changed section are mechanical: act on the plan, do not re-deliberate it.
Spend the deliberation on turns that pick between approaches, including
the merged architectural message that picks AND presents in one turn, and
on the implementation work that follows approval.

## R4 — Batch every independent call, plan the rounds

Batch all independent calls in one message. Open the round with
`Round 1: N calls in this message`, then make all N. If only 1-2 land, do
NOT continue serially: re-issue the remainder as one batch, or move that
work into lanes (each batches internally).

Plan rounds, never discover them — each is a full turn. Targets:
Spike/Bounded ≤3 rounds, Architectural ≤4; lane completions not counted.

- **Round 1 = everything nameable now**, in ONE message, including the
  context call. When the repo layout is not known yet, keep round 1 to
  the context call plus the web searches and lanes the request alone
  justifies, and issue the file reads, greps and repo lanes in round 2.
  Load any deferred tool you will need (`websearch`, `webfetch`,
  `question`) first: call it in round 1 only if it is already available,
  otherwise in round 2.
- **Round 2 = the repo fan-out and follow-ups**: every file plausibly
  involved (small repo with a `files:` list → all of them), the key symbol
  greps, the remaining lanes, the web searches that round 1 had to load
  first, the best primary URLs to fetch.
- **Round 3 = conflicts only**, then write the message.
- Never serialize independent calls. Never re-run a denied or failed call
  unchanged — switch source or drop it.

## R5 — Carry state explicitly

Errors compound along long chains. Prefer wide-and-shallow (many one-hop
lanes) over deep chains; never let a lane chain more than 4 tool calls.
Before each gate restate to yourself in ≤5 lines: PATH · DECIDED · OPEN ·
EVIDENCE COUNT · NEXT. Re-read R0 before any tool call that writes.

## R6 — Assume, do not ask

Human round-trips dominate wall-clock. An answer ≥80% likely from the
repo, conventions, research, or the request becomes a vetoable assumption
inside the design ("Assuming Postgres like the rest of `/services` — say
otherwise"). Ask only questions whose answer forks the design; batch ≤4.
With the `question` tool make item 1 "Approve this design?" (Approve /
Approve with my answers below / Revise) so one reply both answers and
approves; otherwise ask in plain text.

## R7 — Width

One lane per question whose answer you will cite or act on; never pad.
The ceiling is `lanes=` in Live context (default 6, hard max 8, claim
verifier and reviewer lanes included). Over the ceiling →
dispatch the lanes that can change the approach set first, then refill in
batches as completions arrive. A rejected dispatch is never retried
unchanged. Details: `fanout-playbook.md` (read when planning more lanes than `lanes=` or
after a fan-out failure).

## R8 — Overlap machine work with human wait

Every message you send leaves useful lanes running: unasked questions →
assumptions, claim verification, runner-up approach. Late results: fold
them in silently; message the user only if one invalidates something shown.

## R9 — Load only what the path needs

Spike/Bounded: this file only. Architectural: `architectural.md` in round 1.
`research-playbook.md` for >3 web lanes or conflicting evidence.
`visual-companion.md` only if accepted.

## R10 — Research before recommending

Training data is stale. Get live evidence before recommending a library,
framework, service, API usage, version, security or performance
technique, or standard — and whenever the user asks for the best or
latest way. Skip for repo-internal logic, or when the user says offline.

1. Pin queries to the versions in Live context AND check the latest
   release; the gap is often the finding.
2. Primary sources first. Fetch-friendly endpoints beat HTML repo pages:
   `raw.githubusercontent.com/<org>/<repo>/HEAD/README.md`,
   `pypi.org/pypi/<pkg>/json`, `registry.npmjs.org/<pkg>/latest`,
   `proxy.golang.org/<module>/@latest`, `crates.io/api/v1/crates/<name>`.
   Ask `webfetch` to extract ("quote the exact sentence and date"), never
   to summarize.
3. Web content only via `websearch`/`webfetch` — never curl, gh, pip, or
   scripts via `shell`. No web search provider → `webfetch` on the
   endpoints above. Generic technical terms only: no proprietary code,
   internal names, secrets, or customer data.
4. A claim that can change the recommendation needs one primary source or
   two independent secondary ones, with date and version. Accuracy falls
   as calls pile up: verify the load-bearing claims, stop when searches
   stop adding facts.
5. In the design: **Evidence**, 2-7 lines `claim — [source](url)
   (YYYY-MM-DD)`. Label anything unverified.

## R11 — Lane briefs

The rules, output labels and word caps live in the lane agents, so every
sibling shares one byte-identical system prompt. The `prompt` you send is
only the brief: keep every field short and put the slice lines LAST.

**Code lane** — `agent: "oc-explorer"` (read-only, 4 tool calls, 120 words):

    Task: [TASK, one line]. Root: [ROOT]. Today: [DATE].
    Slice: [SLICE]. Siblings cover (stay out): [SIBLINGS].
    Question: [ONE precise question]

It answers with FINDINGS, PATTERNS, RISKS, UNKNOWN.

**Web lane** — `agent: "oc-researcher"` (web only, 5 tool calls, 160 words):

    Task: [TASK, one line]. Today: [DATE].
    Our stack and versions: [FROM LIVE CONTEXT].
    Angle: [ANGLE]. Sibling angles (skip): [SIBLINGS].
    Question: [ONE precise question]

It answers with ANSWER, CLAIMS, CONFLICTS, VERSION_NOTES, UNVERIFIED.

Other lane jobs (approach drafts, claim verification, spec review) use
agent `general` with the template in the file that defines them.

**Merge:** scratch-list the `path:line` facts and cited claims.
Conflicts → one direct check next round. Every UNKNOWN or UNVERIFIED
becomes an assumption or one of the ≤4 questions, never a new exploration
round unless the design cannot be drafted without it. A lane denied web
access → do its 1-2 decisive fetches yourself. Never narrate the
exploration; show the design and cite inline.

## R12 — Merge messages to meet the turn budget

Questions + provisional design in one message; one reply answers and
approves, or you re-present only the changed sections. Approaches +
recommended design in one message (architectural). Spec write + inline
self-review + commit (only when allowed, see `architectural.md` §4) in
one turn, then the single review gate — never a separate "I wrote the
spec" message. A visual-companion offer rides with
the first question batch. Serialize only when one answer determines the
next question.

## Checklist (∥ = one concurrent message)

- **Spike:** ∥ reads + searches (+ ∥ fetches) → Path line + answer-so-far
  - probe plan → nod → probe → recommendation.
- **Bounded:** ∥ reads + greps (+ searches) → ∥ follow-ups → Path line +
  design + Evidence + assumptions + questions → explicit yes → implement.
- **Architectural:** ∥ reads + searches + multi-hop lanes + read
  `architectural.md` → ∥ fetches → design message per `architectural.md`
  (claim-verifier lane launched that same turn, not awaited) → approval →
  spec + inline self-review + commit if allowed, one turn → review gate →
  oc-writing-plans.

## Red flags

- "Too simple to need a design" / "I'll call it bounded and skip the
  spec" → reaching for a label to skip work IS the doubt. Simple means a
  two-sentence design, then approval. Never no design.
- "I know this kind of app, so it's bounded" → bounded measures the repo,
  not you. No existing flow = architectural.
- "Let me look around first" → Live context lists the files and versions.
  Read everything plausible in the first fan-out round.
- "I already know the best practice" → training data is stale. Parallel
  searches cost seconds; a wrong library costs days.
- "The fetch failed, let me try curl" → switch source via `webfetch` or
  drop it. Never retry a denial.
- "A blog says so" / "more sources = more accurate" → check tier, date,
  version; accuracy drops as calls grow. Verify load-bearing claims only.
- "I'll spawn a lane for this one search" → one direct call answers it.
- "Spawn dozens because I can" → one lane per question you will act on; stay
  under the `lanes=` ceiling in Live context (default 6, hard max 8).
- "I'll ask to be safe" → a vetoable assumption costs zero turns; a
  question costs one.
- "It grew, but I'm almost done" → hidden complexity upgrades the path.
  Parallel work is never implementation, and a spike's kept code is a new
  request to classify.

## OpenCode tools and lanes

Tool names are the OpenCode v2 names: `read`, `grep`, `glob`, `shell`,
`websearch`, `webfetch`, `question`, `subagent`, `skill`. Missing
capability → substitute, never stall.

1. Dispatch each lane as a background `subagent` call: `agent:
   "oc-explorer"` (Code lane) or `"oc-researcher"` (Web lane), a short
   `description`, `prompt` = the filled R11 brief, `background: true`, no
   `model` or `variant` argument. Fire all lanes in one message without
   waiting; completions arrive as notifications.
2. Background `subagent` unavailable or rejected → run the same brief in a
   foreground `subagent` with agent `general`. Never invent agent names.
3. Ask questions with `question`; without it, numbered plain text with
   approval as item 1.
4. No task-list tool: carry state per R5.
5. A `shell` call that can run longer than 120 s must use `background:
   true` and a `timeout`; a foreground call is killed at 120 s.

## Visual companion

A browser tab for mockups and diagrams — a tool, not a mode. Offer only
when a question is clearer shown than told, folded into the question
batch: "Want mockups/diagrams in a browser tab as we go?
(token-heavier)". Declined → never re-offer. Accepted → read
`visual-companion.md`. Layouts and diagrams go to the browser;
requirements, trade-offs and scope stay in the terminal.

---

R0 still applies: no implementation until they said yes.
