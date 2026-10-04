---
name: hybrid-brainstorming
description: "Opt-in fork of brainstorming: use when the user says 'hybrid', mentions 'opencode', asks to save tokens/cost or usage limits, or invokes /hybrid-brainstorming. Turns intent into an approved design in the fewest human turns, same as brainstorming, but first asks for the run mode (hybrid, Claude only or opencode only) and offloads low-judgment exploration lanes (code lookups, single-fact web checks, web research, and in mode opencode approach drafts) to a local opencode CLI, gated by a mechanical grounding check. Every opencode failure is reported at once; connection failures retry 3 times, then hybrid mode moves the rest of the run to Claude Sonnet 5.5 (other failures fall back to Claude once per lane). Every judgment step (classification, synthesis, design, spec, self-review, visual companion) stays on Claude."
when_to_use: "Use instead of brainstorming for: 'build/add/implement X (hybrid)', 'design X with opencode', explicit requests to cut Claude usage or cost during exploration, or the literal command /hybrid-brainstorming. Same triggers as brainstorming otherwise once the user has opted into the hybrid routing."
allowed-tools:
  - Bash(sh "${CLAUDE_SKILL_DIR}/scripts/context.sh")
  - Bash(python3 "${CLAUDE_SKILL_DIR}/scripts/bslane.py":*)
  - Bash(${CLAUDE_SKILL_DIR}/scripts/start-server.sh:*)
  - Bash(${CLAUDE_SKILL_DIR}/scripts/stop-server.sh:*)
  - Bash(kill -0:*)
  - Read
  - Grep
  - Glob
  - WebSearch
  - WebFetch
---

# Hybrid Brainstorming → Approved Design, Fastest Path

Classify, fan out (code + web) in as few tool rounds as possible, decide
with evidence, ask once, present once, get approval.

## Live context (preloaded — zero tool calls spent)

!`sh "${CLAUDE_SKILL_DIR}/scripts/context.sh"`

Trust this block instead of re-running `ls`, `find`, `git status`, or
`cat` on manifests. Reference files live in `skill_dir`; read them by
absolute path. (Harness without skill preprocessing shows a raw `!`
command above → run that script inside your first round.)

## Step 0: Run mode (first action, before everything else)

**HARD GATE: the mode popup is mandatory.** Unless the args contain `mode=hybrid|claude|opencode` (or this is a resumed run whose mode is already frozen in run state), the very first tool call of this skill is AskUserQuestion with the three options below, before reading files, planning or running any script. AskUserQuestion may be a deferred tool: load its schema with ToolSearch (`select:AskUserQuestion`) first, then call it. This overrides any "act first", "never block on questions" or auto-mode default. Do not guess the mode from the user's wording (even "hybrid" or "opencode"), from `preset` in routing.json or from an earlier run, and never pick Hybrid on the user's behalf. Wait for the answer.

Live context prints a `shared config:` line: the source label
`$HYBRID_OPENCODE_STD/$HYBRID_OPENCODE_LITE` (the env vars that hold the
shared opencode models; LITE defaults to STD), then the `std` and `lite`
specs as `provider/model#variant`, each followed by its source, then
`(valid)`. The source is `(skill)` when the tier's model comes from this
skill's own `<skill dir>/routing.json`, or `(shared)` when it comes from
those env vars. The line reads `no config (missing)` /
`no config (invalid: ...)` when some tier has no model in either place. If
it does, tell the user to set `HYBRID_OPENCODE_STD` (and optionally
`HYBRID_OPENCODE_LITE`), each `provider/model[#variant]`, in the `env` block
of `~/.claude/settings.json`, e.g.
`{"env": {"HYBRID_OPENCODE_STD": "opencode/muse-spark-1.3-contributor-free#xhigh"}}`,
then restart Claude Code (exporting them in the shell also works). With no
preloaded context, run the script from Live context once, then ask.

- Args contain `mode=hybrid|claude|opencode` → use that mode, do not ask.
- Otherwise your first tool call is AskUserQuestion (load it with
  ToolSearch first if it is still deferred): "Run this skill in which
  mode?"
  - **Hybrid (Recommended)** — judgment on Claude, low-judgment lanes on
    opencode, every failure reported at once, Claude fallback.
  - **Claude only** — opencode is never called.
  - **opencode only** — every offloadable lane goes to opencode, no silent
    Claude fallback.

  Put the `std=… lite=…` specs from the shared config line, each with its
  `(skill)` or `(shared)` source, into the hybrid and opencode option
  descriptions; write "no config" there when the line says so.
- The question does not count against the turn budget below.
- The mode is also the preset: `hybrid`, `claude` or `opencode`. Pass
  `--preset <mode>` on every `bslane.py` call for the rest of the run.
- Modes `hybrid` and `opencode`: run `python3
  "${CLAUDE_SKILL_DIR}/scripts/bslane.py" init` once (foreground) as soon as
  the mode is known, before Round 1 dispatches any lane. It clears the
  previous run's switch to Claude and circuit breakers (lane state is per
  project, not per run), so every run starts on opencode.
- Hand-offs carry the mode: invoke the next skill with args `mode=<mode>`.

## Relay rule (every mode)

**Relay rule (always on).** Any `OC-ERROR` or `OC-WARN` line in tool output —
from `bslane.py` (`init`, `doctor`, `stats` or a lane's result) — means your
next message to the user starts with that line, verbatim, before any other
work. Deduplicate identical `kind` + `tier` pairs: relay the first line and
say how many more matched. Never treat these lines as informational and never
skip one.

<HARD-GATE>
Do NOT invoke any implementation skill, write code, scaffold, or take any
implementation action until you have told your human partner what you
intend and they have approved it. Every task, every path. Parallel work
is read-only exploration, research, drafting (only under
`.hybrid-superpowers/drafts/`), and review — never implementation. Ceremony
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
  invoke next is hybrid-writing-plans with args `mode=<mode>`, or
  writing-plans (no args) if it is not installed. Pass it the spec path,
  committed or not.

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
     (WebSearch/WebFetch/AskUserQuestion/TaskCreate), and all T1 lanes
     (`Agent` lanes and `bslane.py` calls). Web searches (2-4 variants per
     question) and TaskCreate join round 1 only if those tools are already
     loaded: load first, call in the same round only if already
     available; otherwise call them in round 2.
   - **Round 2 = follow-ups revealed by round 1**, in ONE message: the web
     searches and TaskCreate that round 1 had to load first, WebFetch of
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
   verification, spec pre-draft). Late results while you wait: fold them in
   silently; message the user only if one invalidates something shown or
   carries an `OC-ERROR` / `OC-WARN` line (Relay rule).
7. **Load only what the path needs.** Spike/Bounded: this file only.
   Architectural: `architectural.md` (in round 1); `research-playbook.md`
   for >3 web lanes or conflicting evidence; `visual-companion.md` only if
   accepted.

## Hybrid routing

The run mode from Step 0 decides where each role runs:

| Mode | `locate` `explore` `fact` | `research` | `draft` |
| --- | --- | --- | --- |
| `claude` | `Agent` lane | `Agent` lane | `Agent` lane |
| `hybrid` | `bslane.py` | `bslane.py` (needs `websearch=on`, else `Agent` lane after an `OC-ERROR`) | `Agent` lane |
| `opencode` | `bslane.py` | `bslane.py` (needs `websearch=on`, else held) | `bslane.py` |

What stays on Claude in every mode, and why: T0 reads and searches (seconds
each, and their output is the context your judgment needs), `draft` in
`hybrid` (no oracle, it decides the design), the claim verifier (the
independent check on lane output), the design, the spec and its
self-review (the deliverable the user approves), and the visual companion
(no oracle).

Live context's `opencode:` line (`opencode: v<version> preset=<preset> ...
websearch=on|off (doctor <YYYY-MM-DD>)`, or `opencode: unavailable → ...`)
is context only. Mode `claude` never calls `bslane.py` and needs no doctor
run. In the other two modes `bslane.py` refreshes the doctor cache itself
(a ping, once, under a lock) when the tier a lane needs has no entry or an
entry older than 10 minutes, so the first lane of a run may take a few extra
seconds and you never run `doctor` before a lane. It reports, with an
`OC-ERROR` line, any role it cannot serve on opencode: a failed refresh or
ping, a config problem, a tier in cooldown or with all slots busy, an
unreadable `--context-file`. A role the routing pins to `claude` prints no OC
line.

Role → Claude lane mapping (used for roles the mode keeps on Claude, and
for any oc lane that falls back in mode `hybrid`, always with `model:
sonnet` once a `kind=switch` line has been printed): `locate` →
`Explore`/`haiku`; `explore` → `Explore`/`sonnet`; `fact` →
`general-purpose`/`haiku`; `research` → `general-purpose`/`sonnet`; `draft`
→ `general-purpose`/`sonnet`.

Round 1, one message, dispatches everything: T0 reads/searches, `Agent`
lanes for every role the mode keeps on Claude, and
`Bash(run_in_background) python3 "${CLAUDE_SKILL_DIR}/scripts/bslane.py"
code|web …` (with `--preset <mode>`) for every role the mode offloads — all
together, never split across rounds. `draft` never dispatches in round 1:
it fires later, once the approach-deciding lanes are back — see
`architectural.md` §2. Never launch more oc lanes for one tier at once than
that tier's `max_parallel` (the skill's own routing file if it sets one,
else `$HYBRID_OPENCODE_MAX_PARALLEL`, else the shipped default 4); queue the rest and dispatch a replacement
the moment a slot frees up (a lane's stdout line signals completion).

Lane ids match `[A-Za-z0-9_-]{1,40}` and must be unique per lane you
dispatch this session. The env vars `HYBRID_OPENCODE_STD` and
`HYBRID_OPENCODE_LITE` (LITE defaults to STD; each `provider/model[#variant]`,
set in the `env` block of `~/.claude/settings.json`) set the `std` and `lite`
models and variants for every hybrid skill. A tier whose `model` is set in
`$HYBRID_BRAINSTORMING_ROUTING` (default `<skill dir>/routing.json`) uses
that file's `model` and `variant` instead (no variant when that file sets
none). Roles, timeouts and slot waits also live in `$HYBRID_BRAINSTORMING_ROUTING`, merged
over the shipped defaults. Per-tier caps default to 4 parallel lanes (`max_parallel`).
`--preset claude|hybrid|opencode` (the mode) overrides the routing
file's preset for one call: `hybrid` routes locate/explore/fact/research to
opencode tiers and keeps draft on Claude; `opencode` also routes draft to an
opencode tier; `claude` routes every role to Claude.
`init`, `stats` and `doctor` accept `--preset` and ignore it.
`python3 "${CLAUDE_SKILL_DIR}/scripts/bslane.py" stats` summarizes the lane
telemetry (`lanes.jsonl`); run it when the user asks how the lanes did, and in
mode `opencode` once before the design message if any lane was `HELD`: it
starts with one `OC-ERROR ... kind=breaker :: N units skipped` line per
tripped root cause (relay it). A lane skipped by an open breaker prints only
its `HELD` line, because the trip already printed the cause.

Each `bslane.py` call prints zero or more `OC-ERROR` / `OC-WARN` lines
first (relay them, see the Relay rule), then exactly one of four shapes on
completion:
- `LANE <id> <role> oc:<tier> OK — grounded <n>/<m> — <secs>s` (drafts:
  `ungrounded` instead of `grounded <n>/<m>`), then the grounded result,
  then any `UNVERIFIED:` lines. Merge the result exactly like a Claude
  lane's result; treat each `UNVERIFIED:` line like the lane-prompt
  `UNVERIFIED` field — fold it into an assumption or one of the ≤4
  questions, never into a new exploration round.
- `FALLBACK <id> (<reason>) — <note>` followed on the next line by
  `CLAUDE <id> — Agent → subagent_type: <type>, model: <model>,
  description: "<id>", prompt: "Read <path> and follow it exactly."` —
  launch exactly that one `Agent` lane, once, then merge its result when
  it completes. Never retry the oc lane itself. Mode `hybrid` only.
- `CLAUDE <id> — Agent → subagent_type: <type>, model: <model>,
  description: "<id>", prompt: "Read <path> and follow it exactly."` on
  its own (the role is routed straight to Claude) — launch that one
  `Agent` lane the same way.
- `HELD <id> (<reason>) — <note>` — mode `opencode` only: the lane was not
  run and no Claude lane is offered (see the exit code 3 rules below).

Connection failures (`spawn`, `stall`, `throttle`, `crash`) are retried
inside `bslane.py`: up to 3 fresh opencode runs, waiting 10, 30 then 60 s.
Every failed try prints `OC-WARN ... kind=<kind> :: retry <n>/3 in <s>s:
<detail>` (relay it; the lane is only slower, launch nothing for it). In mode
`hybrid`, when the retries run out, or at once for `auth`, `quota`,
`model` and `config` from an opencode run, the whole rest of the run leaves opencode for Claude Sonnet 5.5:
`bslane.py` prints one `OC-ERROR ... kind=switch :: opencode <kind>:
<detail>; the rest of this run uses Claude sonnet`, then the failed lane's
own `FALLBACK` + `CLAUDE ... model: sonnet`. From then on every `bslane.py`
call for a role the mode offloads spawns nothing and prints only a bare
`CLAUDE <id> ... model: sonnet` line with no OC line: keep dispatching those
roles through `bslane.py` and launch exactly the `Agent` lane it names.
Lanes already running on opencode finish and are merged as usual. `timeout`,
`context` and the gate failures (`grounding`, `format`, `empty`) are not
connection problems: no retry, no switch, one `FALLBACK` for that lane only.
Mode `opencode` retries the same way but never switches: after the retries
the lane is `HELD` (rules below).

Exit code 3 means the lane failed on opencode. Any other non-zero exit, or
an argparse usage error, means no lane was started. Either way the lane
produced no result, so act by mode:
- `hybrid`: relay the OC lines, then launch the `CLAUDE` line's `Agent` lane
  once (no `CLAUDE` line → the role's Claude lane from the mapping above,
  model `sonnet` if a `kind=switch` line has been printed). Never retry the
  oc lane yourself.
- `opencode`: relay the OC lines, launch no Claude lane and retry nothing
  on your own. Ask once per root cause with AskUserQuestion: retry on
  opencode / run this lane on Claude / switch the run to hybrid (then use
  `--preset hybrid`) / abort. Put identical failures in one question and
  keep the lanes that did not fail running. Map the answers to commands:
  - **retry on opencode** → run `python3
    "${CLAUDE_SKILL_DIR}/scripts/bslane.py" doctor --ping` in the foreground
    (relay its OC lines). A passing ping clears that tier's circuit breaker
    and throttle cooldown (`tier <t>: breaker and cooldown cleared`); then
    re-dispatch each held lane with the same arguments under a fresh id
    (`<id>-r1`). A tier whose ping still fails stays held: tell the user
    instead of re-dispatching it.
  - **run this lane on Claude** → repeat the same `bslane.py` call with
    `--backend claude` and launch the `CLAUDE` line it prints.
  - **switch the run to hybrid** → `--preset hybrid` on every later call.
  - **abort** → stop dispatching lanes and say so.

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

## Lane prompts (fill brackets; keep the shared block first and identical across lanes so siblings reuse the prompt cache)

For a role routed `oc:<tier>`, `bslane.py` owns the prompt template shown
below — you never assemble the prompt text yourself. Pass only the
bracket values as CLI arguments (`--task`, `--slice`, `--siblings`,
`--question`, `--stack`, `--angle`, `--lens`, `--context-file`), as
described in Hybrid routing. The templates below apply only to lanes
dispatched as `Agent` — a role routed `claude`, or a fallback from an oc
lane.

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
- Spec write + inline self-review + commit (only when allowed, see
  `architectural.md` §4) in one turn, then the single review gate. Never a
  separate "I wrote the spec" message.
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
+ commit if allowed (one turn) → review gate → hybrid-writing-plans with args
`mode=<mode>` (writing-plans, no args, if it is not installed).

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
