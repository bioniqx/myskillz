---
name: glm-brainstorming
description: "Use this before ANY creative work - creating features, building components, adding functionality, choosing a library or architecture, or modifying behavior. Turns intent into an approved design in the fewest human turns: preloaded repo context, up to 8 parallel lanes (default 8) across the codebase AND the live web (current docs, releases, best practices), cited evidence, one approval gate before any implementation. Routes misrouted requests to the matching glm-* sibling skill and borrows sibling agents as lanes. Tuned for GLM-5.3 and GLM-5.3-Flash. Do NOT use when the design or plan is already settled or the user asks for direct implementation - go straight to glm-writing-plans (approved design in hand) or glm-dev-team (plan in hand); a trivial one-touch edit needs no design at all."
when_to_use: "Use for: 'build/add/implement X', 'how should we design or architect X', picking the best current approach, library, framework, or service for something we will build, new projects or subsystems, refactors that change interfaces, and 'can we / is it possible' feasibility spikes. Not for: writing a plan from an approved design (glm-writing-plans), implementing a settled plan (glm-dev-team), or trivial edits with no design choice."
allowed-tools:
  - Bash(sh *context.sh*)
  - Bash(sh *start-server.sh*)
  - Bash(sh *stop-server.sh*)
  - Bash(python3 *check.py*)
  - Bash(kill -0:*)
  - Agent
  - Read
  - Grep
  - Glob
  - WebSearch
  - WebFetch
---

# Brainstorming → Approved Design

Classify → fan out wide in one round → decide on evidence → ask once →
present once → get approval. Lower rule number wins a conflict.

## Hard rules (the rest of this file is detail)

1. No code, scaffold or file write outside `.brainstorm/drafts/` until
   `check.py approve --asked design` prints `RESULT approve yes` on the
   human reply to the design message. Any other reply is not approval (R14).
2. Line 1 of every message you show is `Path: <Spike|Bounded|Architectural> — reason`,
   `Path unchanged: <path>`, or the hand-off line. Run `check.py send` on
   the draft first; repair every FAIL and re-run, and never show a FAIL (R14).
3. Round 1 is ONE message containing everything nameable, opened with
   `Round 1: N calls in this message`. The first two calls are context.sh
   and `check.py route` on the user request. `ROUTE` other than `none` is
   binding: hand off, do not design.
4. Never cite a path:line, URL, date, version or quote you did not see
   in a tool result in this session. `check.py send` re-checks the draft;
   a line you cannot prove is labelled unverified or deleted.
5. Run `check.py cites` and `check.py web` on lane output before any of
   it enters the draft (R14).
6. Ask at most 4 forking questions; everything else is a vetoable
   assumption.
7. Judgment stays on the main thread. Lane rules live only in the
   agent file; the dispatch prompt is the R11 slice and nothing else.
8. Hidden complexity upgrades the path; nothing downgrades.

## Live context (first round-1 call)

Run `sh <Base directory>/scripts/context.sh` as your first round-1 call,
with the "Base directory for this skill" path in place of
`<Base directory>`. If a context block with a `harness:` line is already
in the conversation (the `/glm-brainstorm` command injects one), use it
and skip the script.

Trust this block. Never re-run `ls`, `find`, `git status`, or `cat` on
manifests. Reference files live in `skill_dir` — installed at
`~/.zcode/skills/glm-brainstorming/`; read by absolute path.

## R0 — The gate

Do not write code, scaffold, run an implementation skill, or touch any
file outside `.brainstorm/drafts/` until you have told your human
partner what you intend and `check.py approve --asked design` printed
`RESULT approve yes` on their reply. Every task, every path. The script
rejects soft agreement; do not overrule it.
The one exception is the visual companion, after the user accepts it:
its screens go to `screen_dir` under `.brainstorm/brainstorm/`.
Parallel work is read-only: exploration, research, drafting, review
(a sibling lane's own report file under `.claude/dev-team/`, R11, is
not implementation).
Ceremony scales with the task; R0 never does.

## R1 — Classify; open your first message with it

Triage before the Path line: a misrouted task gets routed, not
designed. In the round-1 batch, right after context.sh, run
`check.py route` with the user request on stdin. `ROUTE` other than
`none` is binding: the hand-off line names that skill, and the
because-clause names the request type. `ALSO` is a second hit; hand
off the first skill only. `ROUTE none` means the script saw nothing
obvious; you still classify with the list below. Match the request
against the sibling skills; on a hit,
announce the hand-off in one line ("Not a design task — handing to X
because Y") — that line replaces the Path line — then invoke the
Skill tool for X with a 2-3 line summary (task plus what is already
known). The target skill's rules own the task from that call.

Hand-off rules, one per request type:

1. Raw product idea, "is it viable/profitable", market research → hand
   off to `glm-idea-to-spec`.
2. Bug, failing test, error, unexpected behavior → `glm-systematic-debugging`.
3. "Does the code match this spec/PRD", gaps vs a requirements doc →
   `glm-requirements-code-audit`.
4. Document existing code: README, API reference, guides →
   `glm-doc-generator`.
5. Summarize branch changes vs main, commit or PR message →
   `glm-git-diff-summary`.
6. Approved design already in hand → `glm-writing-plans`.
7. Approved plan already in hand, or a settled task the user asks to
   just implement, review, refactor or migrate → `glm-dev-team`.

Mixed request (e.g. "audit against the spec, then redesign the gaps") →
hand off the first step only and say the rest is a new request after it.

Hand-off guards: routing is not implementation, so R0 stands
unchanged. At most 3 skills loaded per task, counting this one. One
direction per task — a hand-off target never routes back here. Lanes
and subagents never invoke skills. Mid-task hand-off points: a path
upgrade that reveals the task belongs to a sibling (stop, say so,
route), and the post-approval exits in R13. Sibling skill not
installed → say so in one line, point to `sh install-zcode.sh`, and
continue here only if the task is design-shaped.

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
  not bounded. Direct calls only, plus 2-4 Flash lanes in a large or
  unfamiliar repo. Message: short design (approach, files, testing) + one
  out-of-scope line + Evidence if researched + assumptions + ≤4 forking
  questions. Explicit
  yes → implement with the normal workflow (TDD applies), or the R13 exit.
- **Architectural** — new projects or subsystems, or changes to
  boundaries and interfaces others depend on. Decomposition check first:
  independent subsystems → plan lanes for the first sub-project only.
  Round 1, one message: direct reads + direct searches for single-hop
  questions + lanes for multi-hop ones + `Read architectural.md`, then
  follow it. The ONLY skill you invoke next is `glm-writing-plans`.

Human replies before hand-off: Spike 1-2 · Bounded 1-2 · Architectural
2-3. Count before sending; over budget → merge messages.

## R2 — Lane economics (biggest speed lever on GLM)

`glm-explorer`, `glm-researcher` and `glm-drafter` are Flash at low
effort, pinned in their frontmatter; never add a `model` parameter.
Flash runs ~1.8× faster than the main thread at ~9×
less cost with 3× coding-plan quota. Sibling agents join only per the
R11 sibling-lane table, when a lane needs a shell (explorer and
researcher have none).

1. Code slices dispatch `glm-explorer`. Web slices dispatch
   `glm-researcher`. Approach drafts, the claim verifier and the
   runner-up dispatch `glm-drafter`. All three pin Flash at low effort.
   Spec pre-draft is the one writable lane (`general-purpose`), and only
   when a file write will not raise a prompt.
2. Work whose conclusion decides WHICH approach wins stays on the main
   thread (GLM-5.3).
3. The main thread does classification, merge, design, final message —
   nothing a lane can do.
4. Never spawn a lane for what one direct call answers.

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

Set it where the runtime exposes it: per installed agent via
`thoughtLevel` in its agent file, or `reasoning_effort` on the API
(clients that expose an `off` setting map it to `low`). No control
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
  key symbol greps, ToolSearch to load every deferred tool you will need
  (WebSearch, WebFetch, AskUserQuestion, TaskCreate) first, and all
  lanes. Web searches (2-4 variants per question) and TaskCreate join
  round 1 only if those tools are already loaded; otherwise call them in
  round 2.
- **Round 2 = follow-ups round 1 revealed**: the web searches and
  TaskCreate that round 1 had to load tools for, fetches of the best
  primary URLs, reads of newly discovered files. The `check.py cites` and
  `check.py web` calls join this round (R14), in the same batch.
- **Round 3 = conflicts only**, then write the message.
- Never serialize independent calls. Never re-run a denied or failed call
  unchanged — switch source or drop it.

## R5 — Carry state explicitly

GLM loses accuracy on long chains, and a private restatement does not
hold the state. Prefer wide-and-shallow (many one-hop lanes) over deep
chains; never let a lane chain more than 4 tool calls. The Path line of
the next message is the state, and `check.py send` rejects a draft that
dropped it. Re-read R0 before any tool call that writes.

## R6 — Assume, do not ask

Human round-trips dominate wall-clock. An answer ≥80% likely from the
repo, conventions, research, or the request becomes a vetoable assumption
inside the design ("Assuming Postgres like the rest of `/services` — say
otherwise"). Ask only questions whose answer forks the design — and a decision
the whole design rests on, with no ≥80% answer in sight, IS a fork: ask it,
never pick silently. Batch ≤4. Whether a later reply is approval is
decided by `check.py approve`, not by how agreeable it sounds.
With AskUserQuestion make item 1 "Approve this design?" (Approve /
Approve with my answers below / Revise) so one reply both answers and
approves; otherwise ask in plain text.

## R7 — Width

One lane per question whose answer you will cite or act on; never pad.
Concurrent lanes: never above `lanes=` in the caps line Live context
prints (default 8 — the provider's full concurrent-call budget, hard
max 8). Over `lanes=` → dispatch the lanes that
can change the approach set first, then refill in batches as completions arrive. Details: `fanout-playbook.md`
(read when planning more lanes than `lanes=` or after a fan-out failure).

## R8 — Overlap machine work with human wait

Every message you send leaves useful lanes running: unasked questions →
assumptions, claim verification, spec pre-draft. Late results: fold them
in silently; message the user only if one invalidates something shown.

## R9 — Load only what the path needs

Spike/Bounded: this file only. Architectural: `architectural.md` in round 1.
`research-playbook.md` for >3 web lanes or conflicting evidence.
`glm-tuning.md` only when configuring the runtime or hitting a
GLM-specific failure. `spec-document-reviewer-prompt.md` on the
Architectural path — load it for the inline self-review of every spec
(architectural.md §4) and when launching escalated spec review lanes.
`visual-companion.md` only if accepted. `scripts/check.py` is run
(R14), never read.

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

## R11 — Dispatch the slice; the agent file owns the rules

The lane rules, word caps and output labels live in one place: the body
of `agents/glm-explorer.md`, `agents/glm-researcher.md` and
`agents/glm-drafter.md`. Do not restate them in the prompt. A second
copy drifts, and GLM follows whichever copy it sees last. Prefix caching
is the agent file, identical for every sibling; the slice lines below
are the whole user message, with the question last.

Agent missing → built-in `Explore` (code) or `general-purpose` (web,
drafts). Then read that agent file once and paste its body under the
frontmatter ahead of the slice. Do not reconstruct the rules from memory.

**Code lane** — `subagent_type: "glm-explorer"`:

```
Task: [ONE LINE]. Root: [ROOT]. Today: [DATE].
Slice: [SLICE]. Siblings cover (stay out): [SIBLINGS].
Question: [ONE precise question]
```

**Web lane** — `subagent_type: "glm-researcher"`:

```
Task: [ONE LINE]. Today: [DATE].
Our stack and versions: [FROM LIVE CONTEXT].
Angle: [ANGLE]. Sibling angles (skip): [SIBLINGS].
Question: [ONE precise question]
```

**Draft lane** — `subagent_type: "glm-drafter"`. The user message is the
prompt already written in `architectural.md` (approach lens, claim
verifier, or runner-up). Do not add rules on top of it.

**Sibling lanes** — agents installed by other glm skills. They count
toward `lanes=` and run long (dozens of turns, not 4-5), so each needs
a reason a Code/Web lane cannot meet. Briefings go to `.brainstorm/drafts/`; the
dev-team guard lets those roles write reports only under
`.claude/dev-team/research/` or `reviews/`, so name report paths there.
Rules, one per agent:

1. `glm-debug-worker`: use it for one claim about CURRENT behavior that
   only running a command settles (does test X pass, what does command Y
   print, is flag Z honored) — Spike probes, Bounded load-bearing
   assumptions. Prompt: one hypothesis, the exact command, "FIX: n/a";
   it answers inline in 12 lines.
2. `glm-investigator`: use it for a feasibility, dependency/upgrade,
   security or architecture survey needing git archaeology or read-only
   builds/tests beyond 4 hops. Spike/Architectural only, max 2 per
   task. Prompt: a briefing file with the question, angle, sibling
   angles and report path `.claude/dev-team/research/brainstorm-<slug>-<n>.md`.
3. `glm-spot-reviewer`: use it after an approved Bounded change touching
   >1 file or any auth, money, data or concurrency surface (R13).
   Prompt: a briefing file with the request, approved design as
   acceptance criteria, file scope, `git diff` command, test command and
   report path `.claude/dev-team/reviews/brainstorm-<slug>.md`.

Every other sibling agent (`glm-team-leader`, `glm-programmer-*`,
`glm-code-reviewer`, `glm-plan-*`, `glm-rca-*`, `glm-doc-*`) needs its
owner skill's engine (worktrees, script-built briefs, run state):
reach it only by handing off to that skill, never by direct dispatch.
Sibling agent not installed → its Code-lane equivalent (`glm-explorer`),
or the main thread runs the one command itself.

**Merge:** scratch-list the `path:line` facts and cited claims, after
`check.py` has run on them (R14). Conflicts → one direct check next round. Every UNKNOWN or UNVERIFIED
becomes an assumption or one of the ≤4 questions, never a new exploration
round unless the design cannot be drafted without it. A lane denied web
access → do its 1-2 decisive fetches yourself. Never narrate the
exploration; show the design and cite inline.

## R12 — Merge messages to meet the turn budget

Questions + provisional design in one message; one reply answers and
approves, or you re-present only the changed sections. Approaches +
recommended design in one message (architectural). Spec write + inline
self-review + commit if allowed (`architectural.md` §4) in one turn, then the single review gate — never a
separate "I wrote the spec" message. A visual-companion offer rides with
the first question batch. Serialize only when one answer determines the
next question.

## R13 — Post-approval exits

The approved deliverable picks the next owner; announce it in one line.

- **Architectural** → `glm-writing-plans` with the spec path
  (`architectural.md` §5). Nothing else.
- **Bounded**, ≤3 files, one flow → implement here (TDD applies); then
  the `glm-spot-reviewer` lane if R11 says so, fix its BLOCKER/MAJOR
  findings, report done with the test line.
- **Bounded** that turned out to need >3 files or parallel slices →
  hand the approved design to `glm-dev-team` instead of implementing.
- **Spike** → the recommendation ends the task; building on it is a
  new request to classify.
- Done and the user wants a commit or PR message → `glm-git-diff-summary`
  (counts toward the 3-skill cap).

## R14 — Verify before you cite, send, or write

Lane output is untrusted. `python3 <skill_dir>/scripts/check.py` is
stdlib-only and read-only; paste stdin through a heredoc. Run it, never
read it. The script's own line is the repair. A non-zero exit is a
result: do not retry the same input.

1. `cites --root <repo>` — FINDINGS `path:line — fact — "snippet"`. Round 2, before a lane line enters the draft.
2. `web` — CLAIMS `claim — tier — URL — date — "quote"`. Same round.
3. `spec <path>` — after the spec is written, before the five-lens review.
4. `route` — the user request, in round 1 beside context.sh. `ROUTE` other than `none` is binding. Always exit 0.
5. `send --root <repo>` — the draft, before you show it, and again after each repair. Do not show a FAIL. `--approved` only after approve printed yes.
6. `approve --asked design` — the reply to the design message, before any write outside `.brainstorm/drafts/`. `--asked other` is never a yes.

```
python3 <skill_dir>/scripts/check.py send --root <repo> <<'EOF'
<the draft>
EOF
```

BAD, DROP, and a failed cite are dropped or re-read. WEAK, NOQUOTE, and
unverified stay labelled unverified. A spec FAIL is fixed in place.
`approve no` means you do not write.

## Checklist (∥ = one concurrent message)

`check.py route` joins round 1. `check.py send` runs on every draft below before it is shown.

- **Spike:** ∥ reads + searches (+ ∥ fetches + `check.py` on lane
  output) → Path line + answer-so-far
  - probe plan → nod → probe → recommendation.
- **Bounded:** ∥ reads + greps (+ searches) → ∥ follow-ups (+ `check.py`
  on lane output) → Path line + design (with its out-of-scope line) +
  Evidence + assumptions + questions → explicit yes → implement.
- **Architectural:** ∥ reads + searches + multi-hop lanes + read
  `architectural.md` → ∥ fetches + `check.py cites`/`web` → design message per `architectural.md`
  (claim-verifier and spec pre-draft lanes launched that same turn, not
  awaited) → approval → spec + `check.py spec` + inline self-review + commit if allowed, one turn →
  review gate → glm-writing-plans.

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
- "A GLM-5.3 lane will be smarter" → same model as the main thread at ~9×
  Flash's cost; judgment stays on the main thread (R2). And never a lane
  for one search.
- "Spawn 6 because I can" → width must buy a saved human turn or a
  better decision. One lane per question you will cite or act on; the
  known failure is dozens of lanes for a simple query.
- "I'll ask to be safe" → a vetoable assumption costs zero turns; a
  question costs one.
- "It grew, but I'm almost done" → hidden complexity upgrades the path.
  Parallel work is never implementation, and a spike's kept code is a new
  request to classify.
- "It's misrouted, but I can design it anyway" → routing costs one
  line; designing the wrong task costs the session.
- "glm-programmer can just build the bounded change" → sibling agents
  outside the R11 table need their owner's engine; hand off instead.
- "An investigator is deeper, use it everywhere" → a 60-turn agent per
  lane; only when a shell or >4 hops is required, max 2.

## Harness fallbacks

Live context prints a `harness:` line.
Missing capability → substitute, never stall.

1. Agent / subagents missing → run the work yourself in R4 batches;
   never stall.
2. AskUserQuestion missing (ZCode has the tool — use it) → ask in plain
   text: numbered questions in chat, approval ask as item 1.
3. ToolSearch missing → tools are already live; skip it.
4. TaskCreate missing → use TodoWrite for the checklist write.

**ZCode lane rule.** A lane is one `Agent` tool call: Code lanes use
`subagent_type: "glm-explorer"`, Web lanes `"glm-researcher"`, approach drafts,
the claim verifier and the runner-up `"glm-drafter"`. Those files pin the model
and effort (Flash, low), so never add a `model` parameter. The prompt is the
R11 slice. Agents not installed → the built-ins `Explore` (Code) and
`general-purpose` (Web, drafts, verifier), and the prompt gains the agent-file
body in front of that slice. Launch every
lane of the round in ONE message (ZCode runs subagents launched together in
parallel), then end the turn. A lane that may outlive the turn goes out with
`run_in_background: true`; its completion notification is the wake-up.

## Visual companion

A browser tab for mockups and diagrams — a tool, not a mode. Offer only
when a question is clearer shown than told, folded into the question
batch: "Want mockups/diagrams in a browser tab as we go?
(token-heavier)". Declined → never re-offer. Accepted → read
`visual-companion.md` and start
`<skill_dir>/scripts/start-server.sh --project-dir <repo> --open`.
Layouts and diagrams go to the browser;
requirements, trade-offs and scope stay in the terminal.

---

R0 still applies: no implementation until `check.py approve` printed yes.

## Before you send (every message)

1. `check.py send` printed `RESULT send fail=0`. A FAIL is repaired, not shown.
2. Line 1 is the Path line, `Path unchanged:`, or the hand-off line.
3. A design message contains `Approve this design?`, an assumption, and Out of scope.
4. No write outside `.brainstorm/drafts/` until `check.py approve --asked design` printed yes on this reply.
5. The reply budget for this path is not exceeded.
6. Each lane prompt is only the R11 slice. The rules were left in the agent file.
