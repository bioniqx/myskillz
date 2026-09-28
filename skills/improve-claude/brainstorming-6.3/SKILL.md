---
name: brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, choosing a library or architecture, or modifying behavior. Turns intent into an approved design in the fewest human turns: preloaded repo context, up to 64 parallel lanes across the codebase AND the live web (current docs, releases, best practices), cited evidence, one approval gate before any implementation."
when_to_use: "Use for: 'build/add/implement X', 'how should we design or architect X', picking the best current approach, library, framework, or service for something we will build, new projects or subsystems, refactors that change interfaces, and 'can we / is it possible' feasibility spikes."
allowed-tools:
  - Bash(sh "${CLAUDE_SKILL_DIR}/scripts/context.sh")
  - Read
  - Grep
  - Glob
  - WebSearch
  - WebFetch
---

# Brainstorming → Approved Design, Fastest Path

Classify, fan out (code + web) in as few tool rounds as possible, decide
with evidence, ask once, present once, get approval.

## Live context (preloaded — zero tool calls spent)

!`sh "${CLAUDE_SKILL_DIR}/scripts/context.sh"`

Trust this block instead of re-running `ls`, `find`, `git status`, or
`cat` on manifests. Reference files live in `skill_dir`; read them by
absolute path. (Harness without skill preprocessing shows a raw `!`
command above → run that script inside your first round.)

<HARD-GATE>
Do NOT invoke any implementation skill, write code, scaffold, or take any
implementation action until you have told your human partner what you
intend and they have approved it. Every task, every path. Parallel work
is read-only exploration, research, drafting (only under
`.superpowers/drafts/`), and review — never implementation. Ceremony
scales with the task; the gate never does.
</HARD-GATE>

## Three paths — classify first, and open your first message with it

First line of your first message: `Path: <Spike|Bounded|Architectural> —
<one-line reason>` so the user can override. When in doubt, go heavier.
Hidden complexity found mid-task upgrades the path (stop, say so);
nothing downgrades.

- **Spike** — "can we… / is it possible…", or a pure "what's the best way"
  question with nothing to build yet; output is an answer, not kept code.
  Round 1: relevant reads + web searches. Message: answer-so-far with
  sources + probe plan (2-3 sentences) — if docs already settle it, say so
  and offer the probe as optional. Nod → probe cheaply → recommendation.
  Anything built is labeled throwaway. No doc, no spec.
- **Bounded** — well-scoped change to a flow that ALREADY EXISTS in this
  repo (flag, small endpoint, field, one-file fix). No existing flow to
  read = not bounded. T0 rounds (+ 2-6 T1 lanes only in a large or
  unfamiliar repo). Message: short design (approach, files, testing) +
  Evidence lines if researched + assumptions + ≤4 forking questions.
  Explicit yes → implement with the normal workflow (TDD applies).
- **Architectural** — new projects/subsystems, changes to boundaries or
  interfaces others depend on. Decomposition check before partitioning:
  independent subsystems → plan lanes for the first sub-project only.
  Round 1, one message: T0 reads + T0 web searches for single-hop
  questions + T1 lanes only for multi-hop questions (code slices of a big
  repo, research that must compare several sources) + `Read
  architectural.md`. Then follow `architectural.md`. The ONLY skill you
  invoke next is writing-plans.

Turn budget (human replies before hand-off): Spike 1-2 · Bounded 1-2 ·
Architectural 2-3. Count before sending; over budget → merge messages.

## Speed doctrine (ordered by wall-clock impact)

1. **Human round-trips dominate.** Assume, don't ask: an answer ≥80%
   likely from the repo, conventions, research, or the request becomes a
   vetoable assumption inside the design ("Assuming Postgres like the
   rest of `/services` — say otherwise"). Ask only questions whose answer
   forks the design; batch ≤4. With AskUserQuestion, make the first
   question "Approve this design?" (Approve / Approve with my answers
   below / Revise) so one reply both answers and approves; otherwise ask
   in plain text.
2. **Tool rounds are the next cost — plan them, don't discover them.**
   Every round is a full model turn (~5-20 s). Targets for the main
   thread: Spike/Bounded ≤3 rounds, Architectural ≤4 (background lane
   completions not counted).
   - **Round 1 = everything you can name now**, in ONE message: Read every
     file plausibly involved (small repo with a `files:` list → read all
     relevant source files at once), Grep for the key symbols, all web
     searches (2-4 variants per question), ToolSearch for any deferred
     tool you will need (WebSearch/WebFetch/AskUserQuestion/TaskCreate),
     all T1 lanes, and batched TaskCreate.
   - **Round 2 = follow-ups revealed by round 1**, in ONE message: WebFetch
     the best primary URLs, reads of newly discovered files.
   - **Round 3 = conflicts only**, then write the message.
   - Never serialize independent calls. Never re-run a denied or failed
     call unchanged — switch source or drop it.
3. **Cheapest lane tier that answers** (latencies are typical):

   | Tier | Mechanism | Latency | Use for |
   | --- | --- | --- | --- |
   | T0 | Direct calls in the main thread: Read, Grep, Glob, WebSearch, WebFetch | seconds | known files, symbol hits, one-hop facts, one doc page |
   | T1 | `Agent` subagents (background), one per independent question | ~0.5-5 min | multi-hop exploration of a slice in a big repo; research that must read and follow several sources; approach drafts |
   | T2 | `Workflow` with `parallel()` + `schema` | minutes | only when lanes > subagent cap AND workflow cap > subagent cap AND the user explicitly opted into workflows (ultracode, or asked for a workflow / maximum parallelism) |

   Never spawn a subagent for what one T0 call answers.
4. **Width.** One lane per question whose answer you will cite or act on;
   never pad. Ceiling 64 concurrent lanes; T1 agents never exceed the
   subagent cap in Live context (the harness rejects the next one and
   says not to retry). More lanes than the cap → dispatch the lanes that
   can change the approach set first, then refill in batches as
   completions arrive. Details: `fanout-playbook.md` (read when planning
   >8 T1 lanes or after a fan-out failure).
5. **Model tiering** (pass `model` explicitly — Explore inherits the main
   model): `haiku` for locate/lookup and single-fact web checks; `sonnet`
   for judgment (hidden couplings, source quality, approach drafts, claim
   verification); the main model only for synthesis.
6. **Overlap machine work with human wait.** Each message you send leaves
   useful lanes running (unasked questions → assumptions, claim
   verification, spec pre-draft). Late results while you wait: fold them
   in silently; message the user only if one invalidates something shown.
7. **Load only what the path needs.** Spike/Bounded: this file only.
   Architectural: `architectural.md` (in round 1); `research-playbook.md`
   for >3 web lanes or conflicting evidence; `visual-companion.md` only if
   accepted.

## Research before recommending

Training data is stale for anything fast-moving. Before recommending a
library, framework, service, API usage, version, security or performance
technique, or standard — or when the user asks for the best/latest way —
get live evidence. Skip for repo-internal logic, or when the user says
offline/no web.

- Pin queries to the versions in Live context AND check the latest
  release — the gap is often the finding.
- Primary sources first: official docs, changelogs/release notes, specs,
  maintainer issues. Fetch-friendly endpoints beat HTML repo pages:
  `raw.githubusercontent.com/<org>/<repo>/HEAD/README.md`,
  `pypi.org/pypi/<pkg>/json`, `registry.npmjs.org/<pkg>/latest`,
  `proxy.golang.org/<module>/@latest`, `crates.io/api/v1/crates/<name>`.
  Ask WebFetch to extract ("quote the exact sentence and date"), not to
  summarize.
- Web content comes only through WebSearch/WebFetch — never curl, gh, pip,
  or scripts via Bash.
- A claim that can change the recommendation needs one primary source or
  two independent secondary ones, with date and version. Accuracy falls
  as tool calls pile up: budget, verify the load-bearing claims, stop when
  searches stop adding facts.
- Queries use generic technical terms only — never proprietary code,
  internal names, secrets, or customer data.
- In the design: **Evidence**, 2-7 lines `claim — [source](url)
  (YYYY-MM-DD)`; label anything unverified.

## Lane prompts (fill brackets; keep the shared block first and identical across lanes so siblings reuse the prompt cache)

**Code lane** (`subagent_type: "Explore"`; `general-purpose` only if it
must run commands):

```
Read-only exploration for: [TASK, one line]. Repo root: [ROOT]. Today: [DATE].
Rules: stay in your slice; read excerpts, not whole files; make all
independent searches in one parallel batch; never write, install, commit,
or spawn agents; stop once the question is answered.
Return ≤150 words, no preamble:
FINDINGS: 3-6 bullets `path:line — fact`
PATTERNS: conventions a change must follow | none
RISKS: couplings/gotchas for the task | none
UNKNOWN: what you could not determine
---
Slice: [SLICE]. Siblings cover (stay out): [SIBLINGS].
Question: [ONE precise question]
```

**Web lane** (`subagent_type: "general-purpose"`, `model: "sonnet"`;
`haiku` for single-fact checks):

```
Web research for a design decision: [TASK, one line]. Today: [DATE].
Our stack/versions: [FROM LIVE CONTEXT].
Rules: batch 1 = 2-4 query variants in parallel (broad); batch 2 = fetch
the best primary pages in parallel; ≤6 tool calls total (hard stop); stop when a
batch adds nothing new. Use only WebSearch/WebFetch for web content; on a
failed or denied fetch switch source, never retry it. Source tiers:
A = official docs, changelogs/release notes, specs/RFCs, maintainer
repos/issues, package registries, peer-reviewed papers; B = maintainer or
company engineering blogs, benchmarks with methodology; C = forums/Q&A
(signal only, never sole support). Skip undated pages, SEO/listicle
farms, AI-written summaries. Record date and applicable version for each
claim; flag claims older than 18 months on fast-moving tech or not
matching our version. A claim that could change the recommendation needs
1 A or 2 independent B sources with a ≤25-word verbatim quote. Generic
queries only — no proprietary code, internal names, secrets, customer
data. No writes, no agents.
Return ≤200 words, no preamble:
ANSWER: 1-2 sentences
CLAIMS: 2-6 lines `claim — tier — URL — date — "quote"`
CONFLICTS: where sources disagree | none
VERSION_NOTES: our version vs latest | n/a
UNVERIFIED: claims lacking support | none
---
Angle: [ANGLE]. Sibling angles (skip): [SIBLINGS].
Question: [ONE precise question]
```

**Merge:** keep a scratch list of `path:line` facts and cited claims.
Conflicts → one T0 check in your next round. Every UNKNOWN or UNVERIFIED
becomes an assumption or one of the ≤4 questions — never a new
exploration round unless the design can't be drafted without it. A lane
denied web access → do its 1-2 decisive fetches yourself as T0. Don't
narrate the exploration; show the design and cite inline.

## Merge rules (how the turn budget is met)

- Questions + provisional design in one message; one reply answers and
  approves, or you re-present only the changed sections.
- Approaches + recommended design in one message (architectural).
- Spec write + inline self-review + commit in one turn, then the single
  review gate. Never a separate "I wrote the spec" message.
- Visual-companion offer rides with the first question batch when a
  visual question is foreseeable — never its own message.
- Serialize only when an answer determines the next question.

## Checklist (∥ = one concurrent message)

**Spike:** ∥ reads + web searches (+ ∥ fetches) → Path line + answer-so-far
+ probe plan → nod → probe → recommendation.

**Bounded:** ∥ reads + symbol greps (+ web searches) → ∥ follow-ups/fetches
→ Path line + design + Evidence + assumptions + questions → explicit yes
→ implement.

**Architectural:** ∥ T0 reads + T0 searches + multi-hop T1 lanes + read
`architectural.md` → ∥ fetches → design message per `architectural.md`
(approaches + design + Evidence + assumptions + questions), with
claim-verifier / spec pre-draft lanes launched in that same turn and not
awaited → approval → spec
`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` + inline self-review
+ commit (one turn) → review gate → writing-plans.

## Red flags

| Thought | Reality |
| --- | --- |
| "Too simple to need a design" | Simple = two-sentence design, then approval. Never no design. |
| "I'll call it bounded and skip the spec" | Reaching for a label to skip work IS the doubt — go heavier. |
| "I know this kind of app, so it's bounded" | Bounded measures the repo, not you. No existing flow = architectural. |
| "Let me look around first, then decide what to read" | Live context already lists files and versions. Read everything plausible in round 1. |
| "I already know the best practice" | Training data is stale. Parallel searches cost seconds; a wrong library costs days. |
| "The fetch failed, let me try curl / gh" | Switch to a registry JSON or raw URL via WebFetch, or drop it. Never retry a denial. |
| "A blog says so" | Check tier, date, and version. One secondary source is not evidence. |
| "More sources = more accurate" | Accuracy drops as tool calls grow. Budget; verify only load-bearing claims. |
| "Spawn 64 because I can" | One lane per question you will act on. Respect the cap. |
| "A subagent for one search" | A T0 call in the same round is an order of magnitude faster. |
| "I'll ask to be safe" | A vetoable assumption costs zero turns; a question costs one. |
| "It grew, but I'm almost done" | Hidden complexity upgrades the path. Stop and say so. |
| "I can implement while they read" | Parallel work is exploration, research, drafting, review — never implementation. |
| "The spike worked, so I'll keep the code" | A spike's output is an answer. Keeping code is a new request — classify it. |

## Visual Companion (summary)

Browser tab for mockups, diagrams, side-by-side layouts — a tool, not a
mode. Offer only when a question is clearer shown than told, folded into
the question batch: "Want mockups/diagrams in a browser tab as we go?
(token-heavier)". Declined → don't re-offer. Accepted → read
`visual-companion.md`; start `<skill_dir>/scripts/start-server.sh
--project-dir <repo> --open`. Layouts and diagrams → browser;
requirements, trade-offs, scope → terminal.
