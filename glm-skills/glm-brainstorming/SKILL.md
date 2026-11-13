---
name: glm-brainstorming
description: "Use this before ANY creative work, or when the user says FAST or che do FAST. Creating features, building components, adding functionality, choosing a library or architecture, or modifying behavior. Turns intent into an approved design, or in FAST into a spec, a plan, and a glm-dev-team run that codes until done without another question. Preloaded repo context, up to 8 parallel lanes (default 8) across the codebase AND the live web (current docs, releases, best practices), cited evidence, one approval gate before implementation unless FAST is on. Routes misrouted requests to the matching glm-* sibling skill and borrows sibling agents as lanes. Tuned for GLM-5.3 and GLM-5.3-Flash. Do NOT use when the design or plan is already settled or the user asks for direct implementation - go straight to glm-writing-plans (approved design in hand) or glm-dev-team (plan in hand); a trivial one-touch edit needs no design at all."
when_to_use: "Use for: 'build/add/implement X', 'how should we design or architect X', picking the best current approach, library, framework, or service for something we will build, new projects or subsystems, refactors that change interfaces, 'can we / is it possible' feasibility spikes, and FAST / che do FAST / design and build straight through. Not for: writing a plan from an approved design (glm-writing-plans), implementing a settled plan (glm-dev-team), or trivial edits with no design choice."
allowed-tools:
  - Bash(sh *context.sh*)
  - Bash(sh *start-server.sh*)
  - Bash(sh *stop-server.sh*)
  - Bash(python3 *check.py*)
  - Bash(python3 *decide.py*)
  - Bash(python3 *handoff.py*)
  - Bash(python3 *ask.py*)
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
`MODE fast` does not ask: `fast.md` replaces that gate.

## Mode — before round 1

The first round-1 call is one command. It runs route,
`sh <Base directory>/scripts/context.sh`, and `ask.py mode`. Do not run
those three yourself, and do not launch a lane in that message.

```bash
python3 <skill_dir>/scripts/handoff.py open --self glm-brainstorming
```

The user request is the stdin. A previous `FROM-LINE` stays first. Follow
the last `NEXT:` line.

- `OPEN: routed` → follow `HANDOFF` or `STOP`. Do not design.
- `MODE fast` → read `fast.md` and follow it. It replaces the human gates below.
- `MODE normal` → the rest of this file. Do not ask which mode.
- `MODE ask` → the first line the user sees is `Dùng chế độ FAST không?`, then the script's `ASK:` block. End the turn. On the reply, run `ask.py mode --reply` with that reply on stdin and take the branch above.

A later message that names FAST or refuses it is a new `ask.py mode` on that
message. The script stores the choice in `.brainstorm/drafts/mode.json`.

## Hard rules (the rest of this file is detail)

1. No code, scaffold or file write outside `.brainstorm/drafts/` until
   `check.py approve --asked design` prints `RESULT approve yes`. The
   stdin is the human reply, or the `AUTO` block `ask.py` prints (R6, or `fast.md`).
2. Line 1 of every message you show is `Path: <Spike|Bounded|Architectural> — reason`,
   `Path unchanged: <path>`, or the hand-off line. Run `check.py send` on
   the draft first; repair every FAIL and re-run, and never show a FAIL (R14).
3. Round 1 is ONE message containing everything nameable, opened with
   `Round 1: N calls in this message`. The first round-1 call already ran:
   `open` printed route, context, and mode. `HANDOFF` or `STOP` is binding:
   follow its `NEXT:` line, do not design.
   `STAY` means you classify the path. `GUARD` lines bind the whole task.
4. Never cite a path:line, URL, date, version or quote you did not see
   in a tool result in this session. `check.py send` re-checks the draft;
   a line you cannot prove is labelled unverified or deleted.
5. Run `check.py intake` on lane output before any of it enters the
   draft. `check.py close` breaks and scores. `check.py send` is the
   next tool in that same wake, after `DECISION` is known (R14).
6. Ask at most 4 forking questions; everything else is a vetoable
   assumption.
7. The main thread renders the DECISION line and does not choose an
   approach. Lane rules live only in the agent file; the dispatch prompt
   is the R11 slice and nothing else.
8. Hidden complexity upgrades the path; nothing downgrades.

## Live context (inside the first round-1 call)

`open` already ran `sh <Base directory>/scripts/context.sh`. Trust the
`=== PRELUDE ===` block. If a context block with a `harness:` line is
already in the conversation, use it and do not run `open` again.

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

Triage before the Path line. `open` already routed. `HANDOFF` or `STOP`
is binding: the line you show is `Not a design task - handing to <skill>
because <reason>` (it replaces the Path line), then do what `NEXT:` says,
and do not design. `STAY` means the script saw nothing more specific;
classify the path below. A mixed
request hands off the first step only. At a real exit (R13), run
`handoff.py next --self glm-brainstorming --event <event>` with an event
from the `EXITS` line, and only when the user wants that next job.
When a later step is a job this skill does not do, run
`handoff.py call --self glm-brainstorming --to <skill>` and follow `NEXT:`.

Hand-off guards: routing is not implementation, so R0 stands. At most 3
skills; the script enforces the cap and a cycle. Subagents never invoke
skills. A path upgrade that reveals a sibling stops and routes. Sibling
not installed: `NEXT:` names the file; if that file is missing, say
`sh install-zcode.sh` and continue here only when the task is design-shaped.

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

`glm-explorer`, `glm-researcher`, `glm-drafter` and `glm-design-breaker`
are Flash. Model and effort live only in each agent file; never add a
`model` parameter. Sibling agents join only per the R11 sibling-lane
table, when a lane needs a shell (explorer and researcher have none).

1. Code slices dispatch `glm-explorer`. Web slices dispatch
   `glm-researcher`. Approach drafts dispatch `glm-drafter`. Attacks
   dispatch `glm-design-breaker`. Do not dispatch a claim verifier, a
   runner-up, or a spec pre-draft (R8).
2. The main thread does classification, merge, the final message, and
   the `DECISION` render — nothing a lane can do.
3. Never spawn a lane for what one direct call answers.

## R3 — Decision, not a second effort ladder

Effort is pinned in the agent file. Do not set it from this file.
`decide.py score` prints `DECISION`. Render that option (R14 procedure).

## R4 — Force the batch, plan the rounds

GLM emits fewer parallel tool calls per turn than Claude unless given a
number. Open the round with `Round 1: N calls in this message`, then make
all N. If only 1-2 land, do NOT continue serially: re-issue the remainder
as one batch, or move that work into Flash lanes (each batches
internally).

Plan rounds, never discover them. Each main turn is a full thinking
pass at the pinned effort, so a spare round is the wall clock. Budgets
before the design is shown: Spike/Bounded 3 rounds, Architectural 4.
Lane completions are not extra rounds. A round past the budget is a
defect: fold the work into the open round or drop it.

- **Round 1 = everything nameable now**, in ONE message: every file
  plausibly involved (small repo with a `files:` list → all of them), the
  key symbol greps, and all fact lanes. Tools that are not loaded yet
  wait for the intake message, not a round of their own.
- Follow-ups round 1 revealed, and one direct check of a conflict, go in
  the intake message (conductor step 2). They are not a new round.
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
Name the recommended option id in that message. In the same message
start `python3 <skill_dir>/scripts/ask.py wait --ledger .brainstorm/drafts/ledger.json --options .brainstorm/drafts/options.json --timeout 900`
with `run_in_background: true`, then end the turn. A chat reply before
it finishes: first call `ask.py cancel`, then `approve` on that reply.
The wait's `AUTO` block is the reply when 15 minutes pass with none:
pass that block to `approve`, render its pick, write the spec, and take
the R13 exit. `DECISION stop` or `ask=unattacked` is not a pick.

## R7 — Width

One lane per question whose answer you will cite or act on; never pad.
Concurrent lanes: never above `lanes=` in the caps line Live context
prints (default 8 — the provider's full concurrent-call budget, hard
max 8). Over `lanes=` → dispatch the lanes that
can change the approach set first, then refill in batches as completions arrive. Details: `fanout-playbook.md`
(read when planning more lanes than `lanes=` or after a fan-out failure).

## R8 — Do not start a lane you will not cite

A lane that finishes later wakes this thread for a full thinking pass.
Do not launch a claim verifier, a runner-up, or a spec pre-draft.
`check.py intake` and `check.py close` already gate claims and the pick.
Unasked questions become assumptions (R6). Late results from the lanes
you did launch: fold them in silently; message the user only if one
invalidates something shown.

## R9 — Load only what the path needs

Spike/Bounded: this file only. Architectural: `architectural.md` in round 1.
`research-playbook.md` for >3 web lanes or conflicting evidence.
`glm-tuning.md` only when configuring the runtime or hitting a
GLM-specific failure. `fast.md` only after `ask.py mode` printed `MODE fast`.
`spec-document-reviewer-prompt.md` on the
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
of `agents/glm-explorer.md`, `agents/glm-researcher.md`,
`agents/glm-drafter.md` and `agents/glm-design-breaker.md`. Do not restate
them in the prompt. A second
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
approach-lens prompt in `architectural.md`. Do not add rules on top of it.

**Attack lane** — `subagent_type: "glm-design-breaker"`. The user message
is the option text, the fact ids, and the atoms, question last. Do not
paste the drafter's tradeoff lines into it.

**Sibling lanes** — agents installed by other glm skills. They count
toward `lanes=` and run longer than a code or web lane, so each needs
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

Any other sibling agent: run
`handoff.py borrow --self glm-brainstorming --agent <name>`.
`AGENT` is one dispatch; the `PROMPT` block is the user message.
`HANDOFF` means that agent needs its owner skill: follow `NEXT:` and do not dispatch it.
`handoff.py agents` lists both kinds. Do not reconstruct the list from memory.
Sibling agent not installed → `glm-explorer`, or the main thread runs the one command.

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

Run `handoff.py next --self glm-brainstorming --event <event>` and follow
`NEXT:`. The event is the bullet you are taking. Do not pick the sibling
from memory.

The approved deliverable picks the next owner; announce it in one line.

- **Architectural** → write the spec, then `glm-writing-plans` with that
  path (`architectural.md` §5). On a human `approve yes`, run
  `ask.py chain --pick <id>` first. An automatic pick already wrote
  `.brainstorm/drafts/chain.json`. Nothing else.
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

1. `intake --root <repo>` — findings and claims together, when lanes return, before a lane line enters the draft. `cites` and `web` remain for one kind of line.
2. `close --root <repo> --ledger <path> --options <path>` — stdin is `## BREAKERS` only. It loads the options file itself and prints `DECISION`. Do not pass `## DRAFT` here: the pick is not known yet.
3. `prove --ledger .brainstorm/drafts/ledger.json --offline` unless the user said live. Repair every FAIL, never show one.
4. `spec <path>` — after the spec is written, before the five-lens review.
5. `route` — same table as `handoff.py route`. Prefer `handoff.py` in round 1 (hard rule 3). `ROUTE` other than `none` is binding. Always exit 0.
6. `send --ledger --pick <id>` — the draft, after `close` printed `DECISION pick=<id>`, and again after each repair. The pick id has to appear in the draft. Do not show a FAIL. `--approved` only after approve printed yes.
7. `approve --asked design` — the reply to the design message, before any write outside `.brainstorm/drafts/`. `--asked other` is never a yes.

```
python3 <skill_dir>/scripts/check.py send --root <repo> <<'EOF'
<the draft>
EOF
```

BAD, DROP, and a failed cite are dropped or re-read. WEAK, NOQUOTE, and
unverified stay labelled unverified. A spec FAIL is fixed in place.
`approve no` means you do not write. The conductor procedure, in order. Each number is one message.

1. Round 1, after `open`: `decide.py atoms` on the request, and the fact lanes, in that one message. Make the Flash atom call only when atoms printed no `ATOM` line; then `atoms --check`. `decide.py add` once per kept finding, ledger at `.brainstorm/drafts/ledger.json`. Do not re-run context, mode, or route.
2. When those lanes return: `check.py intake --root <repo>` on their findings and claims (`## CITES` and `## WEB`), and the drafters, in that same message. Architectural: three `glm-drafter` lenses. Bounded with one existing flow: one drafter. Spike: no drafter. The answer is still one option and still needs a breaker.
3. When the drafters return: write `.brainstorm/drafts/options.json` and launch one `glm-design-breaker` per option. End the turn.
4. When the breakers return: one `check.py close --root <repo> --ledger .brainstorm/drafts/ledger.json --options .brainstorm/drafts/options.json` with stdin `## BREAKERS` only. It prints `DECISION` from the options file. Then, in that same wake, `check.py send --ledger .brainstorm/drafts/ledger.json --pick <id>` on the draft that names that id. Show the design only when send prints `RESULT send fail=0`. `pick` renders that card. `ask` asks that one fork and arms `ask.py wait` (R6). `MODE fast` does not take that branch (`fast.md`). `stop` does not render. `unattacked` runs the missing breaker once. Never invent a fact. On `approve yes`, run `ask.py chain --pick <id>`.

## Checklist (∥ = one concurrent message)

- **Spike:** round 1 lanes → `check.py intake` → one breaker → `check.py close` → answer.
- **Bounded:** round 1 lanes → `check.py intake` + one drafter → one breaker → `check.py close` → yes → implement or the R13 exit.
- **Architectural:** round 1 lanes + `architectural.md` → `check.py intake` + three drafters → one breaker each → `check.py close` → approval → spec + `check.py spec` + inline self-review, one turn → glm-writing-plans.

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
- "A GLM-5.3 lane will be smarter" → every lane is Flash. `decide.py`
  picks. Never a lane for one search.
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
- "glm-programmer can just build the bounded change" → run
  `handoff.py borrow`. `HANDOFF` means the owner skill; do not dispatch it.
- "An investigator is deeper, use it everywhere" → a long agent per
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
`subagent_type: "glm-explorer"`, Web lanes `"glm-researcher"`, approach drafts
`"glm-drafter"`, attacks `"glm-design-breaker"`. Those files pin the model and effort, so never add
a `model` parameter. The prompt is the
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
