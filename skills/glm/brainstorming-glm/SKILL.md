---
name: brainstorming-glm
description: "You MUST use this before any creative work - creating features, building components, adding functionality, choosing a library or architecture, or modifying behavior. Turns intent into an approved design in the fewest human turns: preloaded repo context, up to 64 parallel lanes across the codebase AND the live web (current docs, releases, best practices), cited evidence, one approval gate before any implementation. Tuned for GLM-5.3 and GLM-5.3-Flash."
when_to_use: "Use for: 'build/add/implement X', 'how should we design or architect X', picking the best current approach, library, framework, or service for something we will build, new projects or subsystems, refactors that change interfaces, and 'can we / is it possible' feasibility spikes."
allowed-tools:
  - Bash(sh "${CLAUDE_SKILL_DIR}/scripts/context.sh")
  - Read
  - Grep
  - Glob
  - WebSearch
  - WebFetch
---

# Brainstorming → Approved Design

Classify → fan out wide in one round → decide on evidence → ask once →
present once → get approval. Lower rule number wins a conflict.

## Live context (preloaded — zero tool calls spent)

!`sh "${CLAUDE_SKILL_DIR}/scripts/context.sh"`

Trust this block. Never re-run `ls`, `find`, `git status`, or `cat` on
manifests. Reference files live in `skill_dir`; read by absolute path. A
raw `!` line above instead of output → run that script in round 1.

## R0 — The gate

Do not write code, scaffold, run an implementation skill, or touch any
file outside `.superpowers/drafts/` until you have told your human
partner what you intend and they said yes. Every task, every path.
Parallel work is read-only: exploration, research, drafting, review.
Ceremony scales with the task; R0 never does.

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
  not bounded. Direct calls only, plus 2-6 Flash lanes in a large or
  unfamiliar repo. Message: short design (approach, files, testing) +
  Evidence if researched + assumptions + ≤4 forking questions. Explicit
  yes → implement with the normal workflow (TDD applies).
- **Architectural** — new projects or subsystems, or changes to
  boundaries and interfaces others depend on. Decomposition check first:
  independent subsystems → plan lanes for the first sub-project only.
  Round 1, one message: direct reads + direct searches for single-hop
  questions + lanes for multi-hop ones + `Read architectural.md`, then
  follow it. The ONLY skill you invoke next is writing-plans.

Human replies before hand-off: Spike 1-2 · Bounded 1-2 · Architectural
2-3. Count before sending; over budget → merge messages.

## R2 — Lane economics (biggest speed lever on GLM)

Model slots map to GLM models: `haiku` → GLM-5.3-Flash, `sonnet` AND
`opus` → GLM-5.3. A `sonnet` lane is the main model billed again — same
weights, same ~63 tok/s. Flash runs ~1.8× faster at ~9× less cost with 3×
coding-plan quota.

1. Default EVERY lane to `model: "haiku"`: reads, greps, symbol hunts,
   single-fact web checks, doc extraction, claim verification, approach
   drafts, spec pre-draft, spec reviewers.
2. Spend `model: "sonnet"` only on a lane whose conclusion decides WHICH
   approach wins. Never more than 2.
3. The main thread does classification, merge, design, final message —
   nothing a lane can do.
4. No aliases in your harness → name ids: `glm-5.3-flash` for workers,
   `glm-5.3` for the ≤2 judgment lanes.
5. Never spawn a lane for what one direct call answers.

## R3 — Effort ladder (reasoning is always on; you pick depth)

GLM-5.3 cannot disable thinking. `reasoning_effort` is `low | high |
max`, default `max`, and thinking tokens are emitted before any tool call
— so `max` on a mechanical round is pure latency.

- `low` — dispatch rounds, merging lane output, writing/formatting the
  spec, re-presenting one changed section.
- `high` — drafting a design whose approach is already settled,
  resolving conflicting evidence.
- `max` — any turn that picks between approaches, including the merged
  architectural message that picks AND presents in one turn, plus the
  implementation work that follows approval.

Set it where the harness exposes it (Claude Code `--effort` / `/effort`;
API `reasoning_effort`; clients with `off` map it to `low`). No control
available → shorten the round, never ask the model to "think less".

## R4 — Force the batch, plan the rounds

GLM emits fewer parallel tool calls per turn than Claude unless given a
number. Open the round with `Round 1: N calls in this message`, then make
all N. If only 1-2 land, do NOT continue serially: re-issue the remainder
as one batch, or move that work into Flash lanes (each batches
internally).

Plan rounds, never discover them — each is a full turn (~3.4 s to first
token, then always-on thinking at ~63 tok/s before any call). Targets:
Spike/Bounded ≤3 rounds, Architectural ≤4; lane completions not counted.

- **Round 1 = everything nameable now**, in ONE message: every file
  plausibly involved (small repo with a `files:` list → all of them), the
  key symbol greps, all web searches (2-4 variants per question),
  ToolSearch for every deferred tool you will need, all lanes, batched
  TaskCreate.
- **Round 2 = follow-ups round 1 revealed**: fetch the best primary URLs,
  read newly discovered files.
- **Round 3 = conflicts only**, then write the message.
- Never serialize independent calls. Never re-run a denied or failed call
  unchanged — switch source or drop it.

## R5 — Carry state explicitly

GLM loses accuracy on long chains and errors compound. Prefer
wide-and-shallow (many one-hop lanes) over deep chains; never let a lane
chain more than 4 tool calls. Before each gate restate to yourself in ≤5
lines: PATH · DECIDED · OPEN · EVIDENCE COUNT · NEXT. Re-read R0 before
any tool call that writes.

## R6 — Assume, do not ask

Human round-trips dominate wall-clock. An answer ≥80% likely from the
repo, conventions, research, or the request becomes a vetoable assumption
inside the design ("Assuming Postgres like the rest of `/services` — say
otherwise"). Ask only questions whose answer forks the design; batch ≤4.
With AskUserQuestion make item 1 "Approve this design?" (Approve /
Approve with my answers below / Revise) so one reply both answers and
approves; otherwise ask in plain text.

## R7 — Width

One lane per question whose answer you will cite or act on; never pad.
Ceiling 64 concurrent lanes, and never over the subagent cap in Live
context (the harness rejects the next one and says not to retry). Over
the cap → dispatch the lanes that can change the approach set first, then
refill in batches as completions arrive. Details: `fanout-playbook.md`
(read when planning >8 lanes or after a fan-out failure).

## R8 — Overlap machine work with human wait

Every message you send leaves useful lanes running: unasked questions →
assumptions, claim verification, spec pre-draft. Late results: fold them
in silently; message the user only if one invalidates something shown.

## R9 — Load only what the path needs

Spike/Bounded: this file only. Architectural: `architectural.md` in round

1. `research-playbook.md` for >3 web lanes or conflicting evidence.
`glm-tuning.md` only when configuring the runtime or hitting a
GLM-specific failure. `visual-companion.md` only if accepted.

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
   Ask WebFetch to extract ("quote the exact sentence and date"), never
   to summarize.
3. Web content only via WebSearch/WebFetch — never curl, gh, pip, or
   scripts via Bash. Generic technical terms only: no proprietary code,
   internal names, secrets, or customer data.
4. A claim that can change the recommendation needs one primary source or
   two independent secondary ones, with date and version. Accuracy falls
   as calls pile up: verify the load-bearing claims, stop when searches
   stop adding facts.
5. In the design: **Evidence**, 2-7 lines `claim — [source](url)
   (YYYY-MM-DD)`. Label anything unverified.

## R11 — Lane prompts are rule lists, not essays

GLM is trained for brevity; prose fights the training. Imperative
numbered rules, no XML ceremony, no tool inventory (the harness injects
tool schemas ahead of your text). Caching is prefix-based: keep the
shared block byte-identical across siblings and put slice lines LAST.
Flash is verbose unless capped, so give it a word limit and exact labels.

**Code lane** — `subagent_type: "Explore"`, `model: "haiku"`
(`general-purpose` only if it must run commands):

```
Read-only exploration. Task: [TASK, one line]. Root: [ROOT]. Today: [DATE].
Rules:
1 Stay in your slice; siblings cover the rest.
2 Put every independent search in one parallel batch.
3 Read excerpts, never whole files.
4 Max 4 tool calls; stop as soon as the question is answered.
5 Never write, install, commit, or spawn agents.
6 Output only the four labels below. No preamble, no headings. 120 words max.
FINDINGS: 3-6 lines `path:line — fact`
PATTERNS: conventions a change must follow | none
RISKS: couplings or gotchas for this task | none
UNKNOWN: what you could not determine | none
---
Slice: [SLICE]. Siblings cover (stay out): [SIBLINGS].
Question: [ONE precise question]
```

**Web lane** — `subagent_type: "general-purpose"`, `model: "haiku"`
(`sonnet` only for a contested comparison that picks the approach):

```
Web research for a design decision. Task: [TASK, one line]. Today: [DATE].
Our stack and versions: [FROM LIVE CONTEXT].
Rules:
1 Batch 1 = 2-4 query variants in parallel. Batch 2 = fetch the best primary pages in parallel. Batch 3 only for a conflict.
2 Max 5 tool calls; stop when a batch adds nothing new.
3 WebSearch/WebFetch only. Never curl, gh, pip, or scripts. A failed or denied fetch is switched, never retried.
4 Tier A = official docs, changelogs, specs/RFCs, maintainer repos and issues, registries, peer-reviewed papers. Tier B = maintainer or company engineering blogs, benchmarks with published methodology. Tier C = forums, signal only. Reject undated pages, listicles, AI-written roundups.
5 A claim that could change the recommendation needs 1 A or 2 independent B, each with a verbatim quote of 25 words or less, plus date and version. Flag anything over 18 months old on fast-moving tech, or not matching our version.
6 Generic technical terms only. No internal names, code, secrets, or customer data.
7 Output only the five labels below. No preamble, no headings. 160 words max.
ANSWER: 1-2 sentences
CLAIMS: 2-6 lines `claim — tier — URL — date — "quote"`
CONFLICTS: where sources disagree | none
VERSION_NOTES: our version vs latest | n/a
UNVERIFIED: claims lacking support | none
---
Angle: [ANGLE]. Sibling angles (skip): [SIBLINGS].
Question: [ONE precise question]
```

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
self-review + commit in one turn, then the single review gate — never a
separate "I wrote the spec" message. A visual-companion offer rides with
the first question batch. Serialize only when one answer determines the
next question.

## Checklist (∥ = one concurrent message)

- **Spike:** ∥ reads + searches (+ ∥ fetches) → Path line + answer-so-far
  - probe plan → nod → probe → recommendation.
- **Bounded:** ∥ reads + greps (+ searches) → ∥ follow-ups → Path line +
  design + Evidence + assumptions + questions → explicit yes → implement.
- **Architectural:** ∥ reads + searches + multi-hop lanes + read
  `architectural.md` → ∥ fetches → design message per `architectural.md`
  (claim-verifier and spec pre-draft lanes launched that same turn, not
  awaited) → approval → spec + inline self-review + commit, one turn →
  review gate → writing-plans.

## Red flags

- "Too simple to need a design" / "I'll call it bounded and skip the
  spec" → reaching for a label to skip work IS the doubt. Simple means a
  two-sentence design, then approval. Never no design.
- "I know this kind of app, so it's bounded" → bounded measures the repo,
  not you. No existing flow = architectural.
- "Let me look around first" → Live context lists the files and versions.
  Read everything plausible in round 1.
- "I already know the best practice" → training data is stale. Parallel
  searches cost seconds; a wrong library costs days.
- "The fetch failed, let me try curl" → switch source via WebFetch or
  drop it. Never retry a denial.
- "A blog says so" / "more sources = more accurate" → check tier, date,
  version; accuracy drops as calls grow. Verify load-bearing claims only.
- "A sonnet lane will be smarter" → same model as the main thread at ~9×
  Flash's cost. Use Flash. And never a lane for one search.
- "I'll ask to be safe" → a vetoable assumption costs zero turns; a
  question costs one.
- "It grew, but I'm almost done" → hidden complexity upgrades the path.
  Parallel work is never implementation, and a spike's kept code is a new
  request to classify.

## Harness fallbacks

Live context prints a `harness:` line. Missing capability → substitute,
never stall.

| Missing | Substitute |
| --- | --- |
| Agent / subagents | Lanes become direct calls; keep the 2-4 highest-value questions and the round count. |
| AskUserQuestion | Plain text, numbered, approval as question 1. |
| ToolSearch | Tools are already live; skip it. |
| Workflow | Run waves of lanes. |
| `!` preprocessing (raw `!` above) | Run `scripts/context.sh` as your first round-1 call. |
| TaskCreate | Track state in the message per R5. |

## Visual companion

A browser tab for mockups and diagrams — a tool, not a mode. Offer only
when a question is clearer shown than told, folded into the question
batch: "Want mockups/diagrams in a browser tab as we go?
(token-heavier)". Declined → never re-offer. Accepted → read
`visual-companion.md`. Layouts and diagrams go to the browser;
requirements, trade-offs and scope stay in the terminal.

---

R0 still applies: no implementation until they said yes.
