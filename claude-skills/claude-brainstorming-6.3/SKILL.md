---
name: claude-brainstorming
description: "You MUST use this before any creative work - creating features, building components, adding functionality, choosing a library or architecture, or modifying behavior. Turns intent into an approved design in the fewest human turns: preloaded repo context, parallel lanes (at most 12 at once) across the codebase AND the live web (current docs, releases, best practices), cited evidence, one approval gate before any implementation."
when_to_use: "Use for: 'build/add/implement X', 'how should we design or architect X', picking the best current approach, library, framework, or service for something we will build, new projects or subsystems, refactors that change interfaces, and 'can we / is it possible' feasibility spikes."
allowed-tools:
  - Bash(sh "${CLAUDE_SKILL_DIR}/scripts/context.sh")
  - Bash(${CLAUDE_SKILL_DIR}/scripts/start-server.sh:*)
  - Bash(${CLAUDE_SKILL_DIR}/scripts/stop-server.sh:*)
  - Bash(kill -0:*)
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
`.brainstorm/drafts/`), and review — never implementation. Ceremony
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
  read = not bounded. T0 rounds (+ 0-2 code lanes in a small repo, 2-4 plus
  0-2 web lanes in a large or unfamiliar one). Message: short design (approach, files, testing) +
  Evidence lines if researched + assumptions + ≤4 forking questions.
  Explicit yes → implement with the normal workflow (TDD applies).
- **Architectural** — new projects/subsystems, changes to boundaries or
  interfaces others depend on. Decomposition check before partitioning:
  independent subsystems → plan lanes for the first sub-project only.
  Round 1, one message: T0 reads + T0 web searches for single-hop
  questions + T1 lanes only for multi-hop questions (code slices of a big
  repo, research that must compare several sources) + `Read
  architectural.md`. Then follow `architectural.md`. The ONLY skill you
  invoke next is `claude-writing-plans-6.2`
  (fallback `claude-writing-plans`).
  Flow: spec + commit if allowed (one turn) → review gate → claude-writing-plans-6.2.
  This is the conditional commit rule in `architectural.md`.

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
     relevant source files at once), Grep for the key symbols, ToolSearch
     for any deferred tool you will need
     (WebSearch/WebFetch/AskUserQuestion/TaskCreate), and all T1 lanes.
     Web searches (2-4 variants per question) and TaskCreate join round 1
     only if those tools are already loaded: load first, call in the same
     round only if already available; otherwise call them in round 2.
   - **Round 2 = follow-ups revealed by round 1**, in ONE message: the web
     searches and TaskCreate that round 1 had to load first, WebFetch of the
     best primary URLs, reads of newly discovered files.
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
4. **Width and models.** One lane per question you will cite or act on; width = min(questions, Live-context `subagents=` cap, 12); excess runs in waves. Fewer, fuller lanes beat many tiny ones. Pass `model` explicitly: `sonnet` for lanes, `haiku` only for locate or single-fact checks, the main model only for synthesis. Details: `lanes.md`; `fanout-playbook.md` when planning more than 8 T1 lanes.
5. **Overlap machine work with human wait.** Each message you send leaves
   useful lanes running (unasked questions → assumptions, claim
   verification, spec pre-draft). Late results while you wait: fold them
   in silently; message the user only if one invalidates something shown.
6. **Load only what the path needs.** Spike/Bounded: this file only (plus `lanes.md` when T1 lanes are planned).
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
  maintainer issues. Fetch-friendly endpoints (raw README, package
  registries — full list in `research-playbook.md` §2) beat HTML repo
  pages. Ask WebFetch to extract ("quote the exact sentence and date"),
  not to summarize.
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

## Lane prompts and extended red flags

Before dispatching any T1 lane, Read `lanes.md` from `skill_dir`: it holds the code-lane and web-lane prompt templates, how to merge lane results, and the remaining red-flag rows. Pass `model` explicitly on every lane.

## Red flags

| Thought | Reality |
| --- | --- |
| "Too simple to need a design" | Simple = two-sentence design, then approval. Never no design. |
| "I'll call it bounded and skip the spec" | Reaching for a label to skip work IS the doubt — go heavier. |
| "I know this kind of app, so it's bounded" | Bounded measures the repo, not you. No existing flow = architectural. |
| "I can implement while they read" | Parallel work is exploration, research, drafting, review — never implementation. |

## Visual Companion (summary)

Offer a browser tab for mockups and diagrams only when a question is clearer shown than told, folded into the question batch. Declined: do not re-offer. Accepted: read `visual-companion.md` and start `<skill_dir>/scripts/start-server.sh --project-dir <repo> --open`.
