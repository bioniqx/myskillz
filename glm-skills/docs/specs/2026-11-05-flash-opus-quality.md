# Flash lanes, Opus decisions

Date: 2026-11-05. Status: chosen solution, build procedure written, not implemented. Scope:
`glm-brainstorming`, `glm-writing-plans`, and `glm-dev-team`. Nothing in `../claude-skills/`
is touched. When this is implemented, work happens on `main` (repo rule). The session model
for all three skills is GLM-5.3-Flash. No judgment call is promoted to GLM-5.3 or to Claude.

## Decision

GLM-5.3-Flash does not become Claude Opus 5.5 by prompting. On the work these three skills
actually own, Opus-quality is a property of who is allowed to close a decision. Flash may
propose approaches, tests, and attacks. It may not pick the approach, declare a review
approved, or treat a sentence as a fact. A shared checker closes those three acts from a fact
ledger, a score, and a command it re-runs.

That is the whole design. The current engines, guards, frozen tests, `check.py`, and
`plan_tool.py` stay. They already are the harness. The gap that remains is the slots where
a Flash judgment, or a GLM-5.3 reviewer, is still the closer.

## What "like Opus 5.5" means here

Parity is claimed only on the task distribution of these three skills: an approved design
that survives the repo and the sources it cites, a plan whose tasks cover the spec, and an
implementation whose defects a later reader can reproduce with a command. It is not a claim about Design Arena taste, FrontierMath, or
open-ended prose.

Public head-to-heads (not re-run for this spec) say where a skill can and cannot close the gap.
Model Matchbook, 2026-11-04, Claude Opus 5.5 vs GLM 5.3 Flash:

| Axis | Opus 5.5 | Flash | What the skill can do about it |
| --- | --- | --- | --- |
| LiveBench agentic coding | 71.7% | 56.8% | Close it on planned repo work by making the oracle external. Do not claim it on arbitrary terminal tasks. |
| LiveBench instruction following | 65.7% | 52.8% | Close it. Requirement atoms live in the engine, not in the context window. |
| LiveBench coding | 89.3% | 79.0% | Close the part that a frozen test plus an executed attack can see. |
| FACTS grounding | 62.4% | 56.1% | Exceed both, on citations only: an unproved cite cannot decide a design. |
| FrontierMath tiers 1-3 | 91.2% | 55.8% | Do not chase. A slice whose correctness is a proof the engine cannot run is refused, not "solved". |
| GPQA Diamond | 90.6% | 90.2% | Already tied. No work. |
| Design Arena coding Elo | 1384 | 1279 | Partial. Force distinct alternatives and let the user break a tie. Do not pretend the rubric has taste. |

Van Deth's one-harness study (June 2026, GLM-5.2 vs Opus 4.6-4.8, small N) is the reason this
spec does not rebuild the harness. The same GLM, moved from a flat runner onto a real agent
loop, went from 1.74 to 4.37 on a real-code review and from 2.94 to 4.45 on an agent-engine
design, level with the Opus lanes. `glm-dev-team` and `glm-brainstorming` are already that
kind of harness. Another layer of prompt rules will not move the number. Replacing the
remaining closers will.

## The five slots in brainstorming and dev-team

1. **Approach pick.** `glm-brainstorming` hard rule 7 and R2.2 keep the choice of approach on
   the main thread. Under this constraint the main thread is Flash. `glm-tuning.md` already
   notes that a Flash reviewer shares the drafter's blind spots, and it still allows promoting
   one lane to GLM-5.3 when that lane picks the approach. That promotion is rejected here.
2. **Citation proof.** `check.py` verifies that a `path:line` snippet occurs, and it lints the
   shape of a web claim. It never fetches. A dated, well-formed, invented URL passes `send`.
   The tuning doc states this limit on purpose (hermetic, no network).
3. **Plan authorship.** On any task that is not a one-line edit, the Conductor, in a long
   session, writes `.claude/dev-team/plan.md`. Flash's instruction-following gap shows up as
   dropped requirements. Nothing checks that every atom of the request landed in a slice or in
   an out-of-scope line.
4. **Same-agent oracle.** `briefing_text` and `integrate_one` already implement modes `red` and
   `green`, and a `red-done` slice keeps its footprint. `do_dispatch` never selects those
   modes. The code branch sets `mode = "slice"` for every `kind: code` slice, including
   `risk: high`, so one agent writes the tests and then the code that satisfies them.
   `commit-red` blocks empty and tautological tests. It cannot block a test that encodes the
   wrong reading of the request.
5. **Prose verdict.** `devteam.py` re-runs the lane's own gate before merge, and it rejects
   `APPROVED` when the report has no `## Evidence` heading. It does not re-run the commands
   the reviewer claims to have run. A confident `APPROVED` with a heading still merges.
   Same-family critique without a new executed fact rubber-stamps. That is the failure mode
   the tuning table already recorded for soft agreement, moved one step later in the pipeline.

Two contradictions are resolved by this spec, not left as options. `SKILL.md` R2 says the
brainstorming lanes are Flash at low effort. The three agent files and `glm-tuning.md` pin
`thoughtLevel: max`. Low effort fabricates APIs. Max effort before a tool call is latency and
has not produced Opus decisions. Effort is pinned per agent file, once, at the values in
"Roles" below. `SKILL.md` stops stating an effort.

## Rejected alternatives

- **More rules in `SKILL.md`.** Both bodies are already at the size where GLM drops the middle.
  Skill criteria forbid layering rules after a failed run. A rule the model can skip is not a
  closer.
- **Escalate the closer to GLM-5.3.** Same family, shared blind spots, about 9x the price of
  Flash, and it violates the constraint. A GLM-5.3 main thread is not Opus 5.5 either.
- **Best-of-N full implementations.** Correlated samples, painful merges, and the weak test
  travels with every sample. Sample decisions and attacks, implement once.
- **Self-critique on the same evidence.** Changes nothing the model already believed. A
  critique counts only when it brings a fact or a command the engine can re-run.
- **Fine-tune, or activation steering from frontier traces (REVEAL, Nov 2026).** Not a skill
  change. Published gains on Terminal-Bench were single-digit and did not transfer cleanly.
  Out of scope even though Flash is open-weight.
- **`thoughtLevel: max` on every lane.** Already the dev-team setting, and the reason a run
  feels slow. It does not fix slots 1-5.
- **Ask the user more often.** Human turns dominate wall-clock. R6 stays: at most four
  questions, and only a low-margin fork may become one.

## Shared kernel

One home: `_shared/decide.py`, copied by `_shared/sync.sh` into
`glm-brainstorming/scripts/decide.py`, `glm-writing-plans/scripts/decide.py`, and
`glm-dev-team/scripts/decide.py` the same way `handoff.py` is copied. Callers are
`check.py`, `plan_tool.py`, and `devteam.py`. Skills do not restate the algorithm.
`SKILL.md` gains a pointer, not a second copy. Net line count of each `SKILL.md` stays
under 500.

### Fact ledger

A fact is a record the engine stores, never a sentence the model remembers.

```
F-<n>  kind=file|command|user|web
       loc=<path:line or argv or url>
       sha256=<of the quoted bytes>
       text=<verbatim, 25 words or less for web>
       status=OK|WEAK|UNPROVEN
```

Legal premise: the model cites `F-<n>`, and `decide.py` resolves it. A design sentence or a
plan contract that names a path, a version, an API, a number, or "the code does X" without a
fact id is a `send` / `plan-lint` failure. The repair line names the sentence. The model
deletes it or binds it to a real id. It does not get to mark its own sentence verified.

`prove` fetches at most four load-bearing web facts per decision, stdlib only, timeout 15s,
no redirect past one hop. The quote must be a substring of the body. Otherwise the fact is
`UNPROVEN` and cannot score. `--offline` (the unit-test mode) marks every web fact `UNPROVEN`
and does not open a socket. File and command facts stay hermetic either way.

### Requirement atoms

The engine freezes the request before any design or plan is drafted.

1. Take checkbox lines, lines that start with a requirement word already in the text, every
   quoted literal of two or more characters, and every integer of two or more digits.
2. One fresh Flash call, no other context, may only emit `ATOM: <verbatim span>` lines.
   `decide.py` drops any span that is not a substring of the request. One follow-up call may
   add spans still missing. Then the list is frozen.
3. The model cannot invent an atom. A span that is not in the source is discarded, not repaired
   by the model.

Coverage: each atom sits in exactly one option or slice, or in the out-of-scope line the user
sees. Zero homes or two homes fails the lint.

### Decision score

Used for a brainstorming approach and for a contested plan split. Candidates come from the
existing three lenses (repo reuse, current upstream practice, smallest change). A fourth is
not generated. The breaker for a candidate sees the candidate, the ledger, and the atoms. It
does not see the drafter's tradeoff prose. Its prompt is the agent file plus a slice whose
question is last, same prefix-cache rule as R11.

A breaker returns either `COUNTEREXAMPLE` plus a command or a `path:line` the engine
reproduces, or `NO-BREAK` plus the checks it ran. The engine re-runs those checks. A check
that does not reproduce is ignored, not treated as a pass.

```
score(option) =
    +3  if every atom is in this option or in its out-of-scope line
    +2  if every fact it relies on exists and is OK
    -5  per counterexample the engine reproduced
    -2  per new dependency that probe did not find in the repo
    -1  per assumption that cites no fact and is not in the ask list
```

The engine prints `DECISION pick=<id> margin=<n>` or `DECISION ask=<fork>`. The main thread
reads that line and does not pick. Margin is the gap to the second place. A margin below 3
is a user question, counted against the existing cap of 4. If more than four forks are that
close, the four with the smallest margin are asked and the rest are vetoable assumptions on
the higher score. A negative top score, or every option broken, stops the run and asks. Flash
is not allowed to invent a bridging fact. One extra gather wave is the only retry, and only
when a breaker named a missing fact id.

Leave-one-out runs only when the margin is 3 or 4. One breaker re-scores the winner with its
highest-weighted fact removed. If the winner changes, that fork is asked. This is the
anti-correlation step. Temperature diversity and "you are a careful reviewer" are not used.
All lanes are Flash, so independence has to come from hidden rationale, reversed fact order,
and a different required output (a command, not an essay).

### Roles and effort

Pinned only in the agent frontmatter. ZCode honors `thoughtLevel` only next to a real model
id, which these files already have.

| Agent | Effort | Closes what |
| --- | --- | --- |
| `glm-explorer`, `glm-researcher` | high | Ledger entries. Copy from tool output. Zero findings is valid. |
| `glm-drafter` | max | One approach candidate inside one lens. Does not pick. |
| `glm-design-breaker` (new, brainstorming only) | max | Counterexample or NO-BREAK. Does not see drafter prose. |
| `glm-programmer-*` in `RED` | max | Tests from the contract and the signatures, no implementation plan in the prompt. |
| `glm-programmer-*` in `GREEN` | high | Make the frozen tests pass. Cannot edit tests. |
| `glm-spot-reviewer` in `MODE: ATTACK` | max | One attack test or one command. Does not emit a binding verdict. |
| `glm-team-leader` planning | max | A schema plan in a fresh context: request, atoms, probe output. Not the session history. |
| `glm-plan-task-writer` | high | Task bodies from a brief. Does not redraw the contract. |
| `glm-plan-task-writer-deep` | max | Same job for a tier the engine marked deep. Still Flash. |
| `glm-plan-reviewer` | max | A rewrite the linter can reject. The word Approved merges nothing. |

ZCode has no per-dispatch effort. The Agent tool takes no `model` and no `thoughtLevel`.
The mapping in "How to build it" is how this table is pinned: RED goes to
`glm-programmer-strong` (max), a first-try GREEN goes to `glm-programmer-lite` (high).
`glm-programmer-strong` also stays the lane for `risk: high`, `size: large`, and retries.
There is no smarter model to promote it to.

Width is unchanged: brainstorming hard-caps at 8 concurrent provider calls, dev-team at the
governor cap. A decision is two waves, not eight serial chats. Wave 1 drafts up to three
approaches. Wave 2 breaks those three. Both waves are one message each.

## glm-brainstorming

Round 1 is unchanged in shape: `context.sh`, `handoff.py route`, then reads and lanes that
write ledger entries rather than essays. `check.py cites` still runs before a file fact is
trusted. `check.py prove` is the new web step, on the load-bearing claims only.

Round 2 is the decision, not a main-thread synthesis. Architectural path: three drafters, three
breakers, then `decide.py score`. Bounded path: one candidate is enough when probe shows a
single existing flow; the breaker still runs, because a single unattacked draft is how Flash
rubber-stamps. Spike path: the "candidate" is the answer, and it cannot cite an `UNPROVEN`
fact as the reason.

The design message is assembled from the winning card. The model writes the short prose
sections. `check.py send` grows one check: every factual sentence carries a fact id that
resolves, the out-of-scope line and the assumptions are present, and the pick matches
`DECISION`. A mismatch is a FAIL, repaired by re-rendering, not by arguing.

`Approve this design?` and `check.py approve` stay the human closer. Soft agreement stays a
no. The user is the second model for the residual that has no oracle: taste, and any fork
with margin below 3.

`architectural.md` section 2 currently says "Pick and sharpen" on the main thread. That
sentence is replaced by "Render the option `DECISION` named." The lens prompt in that file
stays the drafter prompt. Breaker rules live only in `agents/glm-design-breaker.md`.

R2.2 ("judgment stays on the main thread") is deleted. The replacement, one line: the main
thread renders `DECISION` and does not choose an approach. R3's effort ladder is deleted from
`SKILL.md` so the agent files are the only home.

## glm-dev-team

### Plan

`devteam probe` and atom extraction run before the leader. The leader is a fresh agent. Its
prompt is the request, the atom list, and the probe output. It writes a plan the existing
`references/plan.md` schema already describes. `devteam plan-lint` then rejects the plan when:

- an atom has zero homes or two homes
- two slices share a write path
- a `kind: code` slice has no executable check
- a slice names a path probe did not see and the plan does not mark as new

Repair loop is two. The engine prints the FAIL line. The leader edits the plan. On the third
failure the Conductor asks the user and does not start. The Conductor does not rewrite the
plan from session memory.

### Slice

Every `strict` or `balanced` `kind: code` slice uses two dispatches. `turbo` and `spike`
stay on today's one-lane path. `do_dispatch` is the function that has to start selecting
`red` and then `green`. The rest of the RED/GREEN machinery is already there.

1. `RED` lane. Prompt contains the contract, the atom ids, and the public signatures. It does
   not contain an implementation plan. `commit-red` freezes the tests, as it does today.
2. `GREEN` lane. Different dispatch, same worktree, tests frozen. Hooks already refuse test
   edits. It implements.
3. The engine re-runs the gate, as it does today. A green claim in the report is not evidence.
4. `glm-spot-reviewer` with `MODE: ATTACK`, in a review slot after GREEN. It adds one test or
   one command. The engine runs it in a throwaway worktree, on the slice commit and on the
   parent commit.

| Result on parent | Result on slice | Engine outcome |
| --- | --- | --- |
| fail | pass | The new test pins the change. Keep it. Not a finding. |
| pass | fail | The slice broke a behavior the parent held. BLOCKER. Queue a fix. |
| fail | fail | Incomplete against an atom the test quotes, or out of scope. BLOCKER only when the assertion quotes an atom. Otherwise discard. |
| pass | pass | The test does not see the change. Discard. |

`APPROVED` in a report is ignored. Merge happens only when the gate passed, every reproduced
BLOCKER is fixed or the loop cap of 2 is hit and the leftovers are named to the user, and
`plan-lint` is still clean. `finish` already refuses an open review. It additionally refuses
while a reproduced BLOCKER has no fix slice.

`turbo` and `spike` stay opt-in and keep their current weaker meaning. The Conductor already
says what they trade away. This spec does not silently upgrade them.

### Conductor paraphrase

The engine writes the claim prompt (not the briefing file) to its run directory and prints
`PROMPT <id> <sha256>`. `guard_zcode` denies an `Agent` or `Task` call whose prompt matches
`claim <id>` and is not byte-identical to that file. A prompt with no claim id is left
alone, so ordinary Agent calls still work. The Conductor is told to paste verbatim. A denied
launch never writes a claim file, so the existing `UNCLAIMED` reprint covers it. The exact
hook placement is in "How to build it".

## glm-writing-plans

The plan is the contract `glm-dev-team` will build. A weak plan makes the later attack gate
busy and still ships the wrong product. This skill already put structure, signatures, file
ownership, and `Run`/`Expected` into `plan_tool.py`. What it still lets a model close is the
decomposition, the spec coverage escape, and a reviewer on GLM-5.3.

R0 stays three orchestrator calls. A fourth call is the failure the skill already names, and
it is where Flash drifts. Every new closer runs inside `brief` / `build` / `analyze` /
`review_one`. Call 2 still writes one Contracts section. That write is a proposal. `build`
accepts it or prints `ERR` and does not fan out writers.

### Slots

1. **Coverage escape.** `spec_coverage` reports an uncovered heading as a warning.
   `analyze` folds that into `warns`. R4 tells the orchestrator to treat `WARN spec
   uncovered` as a missing task unless the section is non-functional. Flash is the one who
   decides "non-functional".
2. **Invented existing symbols.** `Consumes` marked `(existing)` is not looked up. A name
   recalled from memory becomes a signature the writer then copies, and `lint_body` only
   checks that the contract text appears in the body.
3. **Tier as a model upgrade.** `GLM["deep"]` is `glm-5.3` at `max`. `review_one` calls
   `call_model(..., "deep")`, so the reviewer is GLM-5.3. `glm-plan-task-writer-deep.md`
   and `glm-plan-reviewer.md` pin the same id. The api-lane `light` effort is `low`, which
   is the setting that fabricates APIs.
4. **Reviewer rewrite.** A reply that starts with `APPROVED` keeps the original body. Any
   other reply replaces the body when the new lint error count is less than or equal to the
   old one. A rewrite can drop assertions and still lint. The agent file says not to weaken
   tests. Nothing counts them.
5. **One decomposition sample.** Call 2 draws every task boundary. A contract that covers
   the atoms and still stuffs an 80-line spec range into one task lints clean. There is no
   second candidate, and there must not be a second orchestrator turn to go get one.

`injectAgentsMd: true` on all three plan agents pulls project `AGENTS.md` into a lane whose
brief is supposed to be the only instruction. Flash follows the last copy. The brief already
inlines `body-rules.md` through `shared_prefix`.

### What the engine closes

- An uncovered spec heading is an `ERR`, unless the heading line itself contains one of
  `non-goal`, `out of scope`, `background`, `revision history`, `references`, `glossary`,
  `table of contents`. The model does not classify the heading.
- Mechanical atoms from `decide.extract_atoms` on the spec must each be a substring of
  exactly one contract's spec-range text, or of the plan's `Out of scope` line.
- An `(existing)` symbol must occur in a file named by that task's `Read`. No `Read` path
  is an `ERR`, not a license to recall the name.
- Tier only moves up. A spec range that contains `auth`, `password`, `token`, `secret`,
  `migration`, `concurrent`, `thread`, `lock`, `race`, `payment`, or `billing` as a word
  becomes `deep` even when the contract said `light` or `std`. `deep` means Flash at `max`,
  not a bigger model. `PLAN_MODEL_DEEP` may still override the id, and a run that sets it
  is outside this bar.
- A review rewrite is kept only when lint does not get worse, every assertion-shaped token
  the old body had is still there, and every atom the old body quoted is still there.
  `APPROVED` keeps the original. It is not a merge of a judgment.
- A contract whose spec range is over 80 lines, or whose `Files` list has more than four
  paths, gets one Flash split proposal inside `build`, at most three such tasks. The split
  replaces the original only when `analyze` is clean, atom coverage still holds, and the
  new file sets partition the old one. Otherwise `build` prints `SPLIT <id> rejected` and
  keeps the original. `--no-split` skips the attempt.

Writers still fill bodies. The repair loop inside `write_one` stays. It is already a linter
telling Flash what to fix. That is not one of the slots.

## How to build it

Do the six ship steps in order. Do not start a later step by weakening an earlier gate.
Stdlib only. No new dependency. After each step run the command in that step. A red test is
fixed before the next step starts.

Work on `main`. Do not edit `../claude-skills/`.

### Step 1 — `_shared/decide.py`

Create `_shared/decide.py`. Add a third copy loop in `_shared/sync.sh`, same shape as the
`handoff.py` loop, limited to `glm-brainstorming`, `glm-writing-plans`, and `glm-dev-team`. In
`_shared/tests/test_vendored.py`, add `decide.py` to the `skills` dict for those three
skills only. The expected sync count is derived from that dict. Do not copy `decide.py`
into the other five skills.

`decide.py` imports nothing from `check.py`, `plan_tool.py`, or `devteam.py`. Those three
import it. When they are run as scripts, their directory is on `sys.path`, so `import decide`
resolves to the vendored file next to them.

Public functions, and the CLI that calls them:

| CLI | Stdin | Writes | Prints |
| --- | --- | --- | --- |
| `atoms` | the request text | nothing | one `ATOM: <span>` line per mechanical atom, then `NEXT:` |
| `atoms --check --source FILE` | the Flash call's stdout | nothing | `ATOM:` lines kept, `DROP:` lines rejected, then `FROZEN n=` |
| `add --ledger FILE` | one fact block | the ledger | `F-<n> status=<OK\|WEAK\|UNPROVEN>` or `FAIL` |
| `prove --ledger FILE [--offline]` | nothing | statuses in the ledger | one line per web fact |
| `break --root DIR --ledger FILE` | breaker reports | `reproduced` on each report | `BREAK <id> reproduced=yes\|no` |
| `score --ledger FILE --deps FILE` | a JSON list of options | nothing | one `DECISION` line |
| `bind --ledger FILE` | a draft | nothing | `FAIL` lines, then `RESULT bind fail=<n>` |

`atoms` is mechanical. It does not call a model.

- Keep a line that starts with `must`, `shall`, `need to`, or `needs to`, checkbox marker
  optional. The span is the line with the marker stripped.
- Keep each quoted literal of two or more characters.
- Keep each integer of two or more digits, except an integer inside a `YYYY-MM-DD` date or
  inside a version (`1.2`, `1.2.3`).
- De-duplicate, preserve order.

`atoms --check` keeps a model line only when it is `ATOM: <span>` and `<span>` is a
substring of `--source`. Anything else is `DROP`. The model cannot repair a drop. The
conductor runs one Flash call with no other context, prompt equal to the request text plus
the sentence "Emit only ATOM: lines, each span copied verbatim." Then it runs `--check`.
One follow-up is allowed, same rule, asking only for spans not yet emitted. Then stop.
`FROZEN` is the list `atoms` plus the kept model spans.

Ledger file, JSON, created by `add`:

```json
{"facts": [
  {"id": "F-1", "kind": "file", "loc": "src/a.py:12", "sha256": "<hex>",
   "text": "return pool.get(url)", "status": "OK"}
]}
```

`kind` is `file`, `command`, `user`, or `web`. `add` assigns the next `F-<n>`. It does not
trust an id in the input. A `file` fact is `OK` only when `check.py`'s existing `eval_cite`
would accept `loc` plus `text` (call that function, do not reimplement the 3-line window).
A `command` fact is `OK` only when `text` is a substring of a stdout file the caller passes
as `--stdout PATH`. A `user` fact is `OK` only when `text` is a substring of `--source`.
A `web` fact starts as `UNPROVEN`.

`prove` looks at web facts only, at most four per run. Further web facts stay `UNPROVEN`
with reason `cap`. `--offline` sets every web fact to `UNPROVEN` with reason `offline` and
must not open a socket. The unit test monkeypatches `urllib.request.urlopen` to raise, and
asserts it was not called. Live fetch, used only without `--offline`:

- stdlib `urllib.request` only
- timeout 15 seconds
- at most one redirect, then `UNPROVEN`
- read at most 1_000_000 bytes, text bodies only
- `status=OK` only when `text` is a substring of the body and is 25 words or fewer
- otherwise `UNPROVEN`

`score` refuses to pick an option that was not attacked. Input is a JSON list:

```json
[{
  "id": "A1",
  "lens": "reuse",
  "text": "APPROACH 1: ...",
  "atoms_hit": ["exact atom"],
  "out_of_scope": "one line",
  "fact_ids": ["F-1"],
  "new_deps": ["some-pkg"],
  "assumptions": [{"text": "...", "fact": "F-2"}]
}]
```

`--deps` is a newline list of package names already in the repo (the conductor builds it
from the manifests `context.sh` printed, not from the model). The breaker record is a
separate file the `break` command writes next to the ledger, `breaks.json`. The model does
not set `reproduced`.

Breaker stdin, one report per option:

```
OPTION A1
COUNTEREXAMPLE
cmd: python3 -m unittest tests.test_x
```

or `cite: src/a.py:12 "snippet"`, or:

```
OPTION A1
NO-BREAK
check: <command>
```

`break` reproduces a `cmd` or a `check` by running it with `subprocess`, timeout 60 seconds,
`cwd=--root`, no shell when the command splits with `shlex`. Exit non-zero means the
counterexample reproduced. Exit zero means a `check` reproduced. A `cite` reproduces only
when `eval_cite` returns ok and the snippet contains a token from that option's `text` or
from one of its atoms. Anything that does not reproduce is ignored. It is not a pass and
not a penalty.

Score, computed by `score`, never by the model:

```
+3  every frozen atom is in atoms_hit or in out_of_scope
+2  every fact_id exists and is OK
-5  per reproduced COUNTEREXAMPLE
-2  per new_deps name absent from --deps
-1  per assumption whose fact is missing or not OK
```

An option with no reproduced `check` and no reproduced `COUNTEREXAMPLE` is unattacked.
`score` prints `DECISION ask=unattacked` if the best option is unattacked. Otherwise it
sorts by score. Margin is first minus second. A single option uses second = 0.

- Top score negative, or every option has a reproduced counterexample: `DECISION stop`.
- Margin below 3: `DECISION ask=<id of the fork>`.
- Otherwise: `DECISION pick=<id> margin=<n>`.

Leave-one-out is mechanical. When the margin is 3 or 4, drop the winner's longest OK fact
and recompute. If the winner changes or the margin falls below 3, print `DECISION ask=`
instead. Do not spend a second Flash call on it.

`bind` fails a draft line when it contains a path, an `https://` URL, or a version token,
unless that line also contains an `F-<n>` whose ledger record is `OK`, or the line contains
the word `unverified`. Existing `check.py send` checks stay. `bind` does not re-judge tone.

Tests in `_shared/tests/test_decide.py`, unittest, no network:

- a model atom that is not a substring is dropped
- a year inside a date is not an atom, and a 2-digit criterion number is
- score arithmetic for each term, including a reproduced break of -5
- margin below 3 prints `ask`, margin 3 or more prints `pick`
- an unattacked option does not win
- leave-one-out flips a margin-3 winner when its only OK fact is removed
- `prove --offline` does not call `urlopen`
- `bind` fails a dated `https` line with no fact id, and passes the same line with `F-1`
  when that fact is `OK`

Run:

```bash
cd glm-skills && sh _shared/sync.sh && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_decide.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_vendored.py' -v
```

### Step 2 — wire `check.py send` to the ledger

In `glm-brainstorming/scripts/check.py`:

- `import decide`
- add `prove` and `bind` subparsers that call `decide.main` with the same argv tail, so
  there is one CLI the skill names (`check.py prove`, `check.py bind`)
- at the end of `check_send`, after the existing cite and URL loops, call `decide.bind_text`
  on the visible draft when `--ledger` is set
- a missing `--ledger` on a design draft (the draft contains `Approve this design?`) is
  itself a `FAIL ledger`
- keep `check.py` from opening sockets. Fetching stays in `decide.prove`. The existing
  `web` subcommand stays shape-only, so current web tests keep passing

Extend `SendTests` in `_shared/tests/test_glm_brainstorm_check.py`:

- design draft with a dated URL and no ledger fails
- the same draft passes when the ledger has an `OK` web fact whose `loc` is that URL and
  the line cites its id
- `--offline` prove on an invented URL yields `UNPROVEN`, and `score` will not give that
  option the +2

Do not add a live fetch to the suite. One manual `prove` without `--offline` is enough
later, and it is not a merge gate.

Run the existing brainstorm check module the same way as step 1, pattern
`test_glm_brainstorm_check.py`.

### Step 3 — brainstorming renders `DECISION`

Agent pins. ZCode honors `thoughtLevel` only next to a real model id. Today
`glm-explorer.md`, `glm-researcher.md`, and `glm-drafter.md` pin
`account:zai-individual-coding-plan/GLM-5.3` at `max`. Change the model id to
`GLM-5.3-Flash`. Set effort to `high` on explorer and researcher, and `max` on drafter.

Add `glm-brainstorming/agents/glm-design-breaker.md`. `install-zcode.sh` discovers
`agents/*.md`, so the installer needs no name list. `devteam.py doctor` does not install
this agent. Frontmatter, matching the drafter file's keys:

```yaml
name: "glm-design-breaker"
description: "Flash lane for glm-brainstorming: attack one approach. Returns a counterexample or NO-BREAK. Does not pick."
model: "account:zai-individual-coding-plan/GLM-5.3-Flash"
thoughtLevel: max
color: blue
maxTurns: 8
disallowedTools: Write, Edit, Bash
injectAgentsMd: false
```

Body, and this is the only copy of these rules:

```
Follow the user message. It names one option, the fact ids, and the atoms.
You do not see the other options. You do not pick a winner.
Rules:
1 Try to break this option. A break is a command that fails, or a path:line quote that contradicts the option.
2 If you cannot break it, run one check that should succeed if the option is true, and report that check.
3 Copy paths, quotes, and commands from a tool result or from the user message. Never invent one.
4 No tool call unless a fact is missing. Then 2 at most. WebSearch and WebFetch only.
5 Output only the labels below. No preamble. Zero is not a label. You must print one of the two blocks.

OPTION: <id>
COUNTEREXAMPLE
cmd: <command>
```

or `cite: <path:line> "<snippet>"` in place of `cmd`, or:

```
OPTION: <id>
NO-BREAK
check: <command>
```

`architectural.md` lens prompt stays the drafter prompt. Replace the sentence "Pick and
sharpen. Do not draft from scratch." with "Render the option the DECISION line named. Do
not draft another approach and do not change the pick."

`SKILL.md` edits, and nothing else in that file. Net lines must stay under 500. Delete
more than you add.

- Hard rule 7. Replace "Judgment stays on the main thread. Lane rules live only in the
  agent file; the dispatch prompt is the R11 slice and nothing else." with "The main
  thread renders the DECISION line and does not choose an approach. Lane rules live only
  in the agent file; the dispatch prompt is the R11 slice and nothing else."
- R2. Delete the sentence that says work whose conclusion decides which approach wins stays
  on the main thread. Delete every claim that the lanes run at low effort. The agent file
  is the only effort pin.
- Delete the whole R3 effort ladder. `glm-tuning.md` sections 2 and 3 currently restate
  effort and currently say the three lanes pin Flash at max, which is not what the files
  contain. Replace those two sections with: model and effort live only in the agent
  frontmatter; this file is the economics and the failure table.
- R11. Add `glm-design-breaker` as the attack lane. The user message is the option text,
  the fact ids, and the atoms, question last. Do not paste the drafter's tradeoff lines
  into that message.
- R14. Add two commands next to `cites` and `web`: `check.py prove --ledger <path>
  --offline` unless the user said live, then `check.py bind --ledger <path>` on the draft.
  `send` already calls `bind` when `--ledger` is set. The skill's line is "run bind, repair
  every FAIL, do not show a FAIL."

Conductor procedure the skill states in one checklist under R14, not as a second essay:

1. Round 1 is unchanged: `context.sh`, `handoff.py route`, lanes that emit fact blocks.
   Run `check.py cites`, then `decide.py add` once per kept finding, ledger at
   `.brainstorm/drafts/ledger.json`.
2. Run `decide.py atoms` on the user request, then the one Flash atom call, then
   `atoms --check`.
3. Architectural: three `glm-drafter` lanes, the existing lenses, in one message. Bounded
   with one existing flow: one drafter. Spike: the answer is the only option, and it still
   needs a breaker.
4. Next message: one `glm-design-breaker` per option, in one message. Paste their stdout
   to `decide.py break`. Then `decide.py score`.
5. On `DECISION pick`, render that card. On `ask`, ask that one fork, inside the existing
   cap of 4. On `stop`, ask and do not render a design. On `unattacked`, run the missing
   breaker once. Do not invent a fact to raise the score.
6. `check.py send --ledger` before the design is shown. The `APPROACH` line that is the
   pick must be the id `DECISION` printed. A mismatch is a FAIL.

`check.py approve` is unchanged.

Fixture tests, added to the brainstorm check module, no model calls:

- invented URL, ledger `UNPROVEN`, `score` does not pick that option
- soft agreement still fails `approve` (already tested; do not duplicate, point at it)
- architectural draft with one `APPROACH` line still fails `send`
- `bind` fails when the rendered pick id is not the `DECISION` id (pass the expected id
  with `--pick`)

Run `test_glm_brainstorm_check.py` and `test_all_skills.py`. Confirm each brainstorming
description is still at or under 1024 characters and the body is under 500 lines.

### Step 4 — dev-team: atoms, the split, the attack, the hash

#### Pins

`_shared/tests/test_devteam_zcode_doctor.py` still expects `glm-programmer-strong`,
`glm-code-reviewer`, and `glm-team-leader` on `GLM-5.3`. The agent files on disk are
already `GLM-5.3-Flash`. Do not put `GLM-5.3` back. Update the test's `pins` table to:

| Agent | Model | thoughtLevel |
| --- | --- | --- |
| `glm-programmer-lite` | GLM-5.3-Flash | high |
| `glm-programmer-strong` | GLM-5.3-Flash | max |
| `glm-code-reviewer` | GLM-5.3-Flash | high |
| `glm-spot-reviewer` | GLM-5.3-Flash | max |
| `glm-investigator` | GLM-5.3-Flash | high |
| `glm-team-leader` | GLM-5.3-Flash | max |

Set those frontmatter values. `SKILL.md` currently says every agent stays at
`thoughtLevel: max` and tells the conductor not to lower it. Delete that sentence. The
agent file is the pin. Also change the opening mode list in `glm-programmer-lite.md` and
`glm-programmer-strong.md`: `RED` then `GREEN` is the strict/balanced code path, `SLICE`
remains the turbo path. One sentence each. Do not paste the scheduler algorithm into the
agent file.

#### Atoms and plan-lint

Add `devteam atoms` and `devteam plan-lint`. Both call `decide.py`.

- `atoms` reads the plan's `request` field, or stdin when no plan exists yet, runs the
  mechanical extractor, prints `NEXT:` for the one Flash call, and on `--check` writes
  `.claude/dev-team/atoms.json`.
- `plan-lint` fails when `atoms.json` is missing.
- Each frozen atom must be a substring of exactly one slice's `goal` + `criteria` +
  `edge_cases`, or of the out-of-scope line in the prose above the JSON block. Zero homes
  or two homes is a FAIL naming the atom.
- A path in `files` that does not exist on disk must be listed in that slice's `new_files`.
  Existence is the check. Do not ask the model whether probe saw it.
- Pairwise disjoint `files` is already rejected by plan validation. Do not write a second
  copy. Call the existing validator and add the atom and `new_files` checks beside it.
- A `kind: code` slice with an empty `criteria` list fails. The existing "code slice needs
  a test path" check stays.

`cmd_start` runs `plan-lint` before `do_dispatch`. On FAIL it prints the lines and does not
dispatch. The conductor may run `atoms --check` and edit `plan.md` twice. The attempt count
lives in `.claude/dev-team/plan-lint.count`. On the third failure `start` prints
`ASK the user` and still does not dispatch. The conductor does not rewrite the plan from
memory. The leader prompt for a fresh planning call is the request, `atoms.json`, and the
`probe` stdout saved at `.claude/dev-team/probe.txt`. `cmd_probe` already prints the
commands. Make it also write that file.

#### Selecting red and green

In `do_dispatch`, replace the code branch that always sets `mode = "slice"`. Keep the
non-code and spike branches. New order:

1. `kind != "code"`: existing `KIND_MODE`.
2. `fast_level >= 4` and not a review fix and not `risk: high`: `fast` (spike). Unchanged.
3. `status == "red-done"`: `green`. This must be tested before the next line, or a
   finished RED is dispatched as RED again.
4. `fast_level < 2` (strict and balanced, both store `fast: 0`): `red`.
5. Else: `slice` (turbo).

`base_sha` for `green` is already `s["red_sha"]` in `do_dispatch`. `cmd_claim` already
resets the worktree to `base_sha` and writes `.slice/red` when `mode == green`. Do not add
a worktree creator.

`dispatch_route`: treat `mode == "red"` as strong, so RED runs on
`glm-programmer-strong` at max. A first GREEN with `risk != high`, `size != large`, and
`attempt < 2` stays `glm-programmer-lite` at high. The existing retry and risk rules stay.

`integrate_one` already sets `red-done`, removes the RED worktree, and returns a line that
tells the conductor to run `dispatch <id>`. Change that line. `cmd_next` already calls
`do_dispatch` on ready slices after integrate, and `red-done` is ready. The same `next`
prints the GREEN launch. The return line should say `GREEN launched below`. A second
`dispatch` would double-launch.

RED briefing already says "write no implementation". Keep it. Do not put a procedure for
the production code into the RED brief. GREEN briefing already says the tests are frozen.

#### Attack

`glm-spot-reviewer` stays read-only. `guard_edit_ro` already blocks repo writes. Do not
give it Write. It writes a report, and the engine runs the test.

After a balanced or strict GREEN proof succeeds, `integrate_one` does not call
`merge_slice` yet. Set `status` to `green-proved`, keep the tip sha, and print
`ATTACK <id>`. `cmd_next` launches `glm-spot-reviewer` with `MODE: ATTACK` when a slice is
`green-proved` and a review slot is free. The prompt is the existing review brief plus
three lines: the contract atoms, the parent sha, the tip sha. No verdict is requested.

The report contains one fenced block:

```
ATTACK-FILE
<test body>
ATTACK-CMD
<the plan test_file command, or a single argv the plan already allows>
ATOM
<an atom substring, or none>
```

The engine, not the reviewer, chooses the path: the directory of the first test path in
the slice footprint, file name `test_attack_<id>.py` (or the project's test suffix if the
footprint's test file has one). Reject a body that fails `vacuous_test_check`. That
outcome is `DISCARD`, not a blocker.

Run it with `run_at_commit`. Add an optional `overlay` argument, default `None`, written
into the detached worktree after `link_deps` and before `run_proof`. Existing RED-proof
callers pass nothing. Run once at `base_sha` (parent) and once at the GREEN tip.

| Parent | Slice | Quotes an atom | Result |
| --- | --- | --- | --- |
| fail | pass | either | `ATTACK PIN`. Not a finding. Then `merge_slice`. |
| pass | fail | either | `ATTACK BLOCKER`. Do not merge. Queue a fix on the same slice. |
| fail | fail | yes | `ATTACK BLOCKER`. The slice does not meet that atom. |
| fail | fail | no | `DISCARD`. Then `merge_slice`. |
| pass | pass | either | `DISCARD`. Then `merge_slice`. |
| did not run |  |  | `DISCARD`. Then `merge_slice` only when the body was empty. A body that threw before exit is a `BLOCKER`. |

`attack_n` on the slice starts at 0. Each `BLOCKER` increments it. At 2, stop launching
attacks, do not merge, print the leftover to the user. `cmd_finish` refuses while any
slice is `green-proved` or has an open `BLOCKER`. `--force` still exists and names them.

Ignore `APPROVED` in a review report for this merge decision. The word can stay in the
report for the final sharded review's prose. It does not flip a slice to merged.
`review-done` keeps its current fail-closed behavior for the final review batch. The
attack table is an additional closer, not a replacement for "missing Evidence counts as
not approved."

Put `classify_attack(parent_rc, slice_rc, quotes_atom, ran)` in `devteam.py` so the four
rows are a pure function. Test it in `_shared/tests/test_devteam_attack.py` with no git
repo. Then one test that `do_dispatch` on a balanced code slice in `pending` returns mode
`red`, and the same slice in `red-done` returns mode `green`. One test that turbo
(`fast >= 2`) still returns `slice`.

#### Prompt hash

The launch prompt is not the briefing. `print_dispatch` emits `claim_prompt`: `python3
<script> claim <id>` plus optional `CONTEXT:` paths. The briefing is a file the lane reads
after `claim`. Hash that short string. Do not hash an essay.

`print_dispatch` writes the exact prompt to `.claude/dev-team/prompts/<id>.txt` and prints
`PROMPT <id> <sha256>` above the Agent line. `LANE_PROMPT_RES` must still find
`claim <id>` in that string, so do not put a header inside the prompt.

In `guard_zcode`, before the foreign-role allow, when `tool_name` is `Agent` or `Task`:

- Read the prompt from the hook payload.
- If it does not match `claim <id>`, allow. Ordinary Agent calls are not dev-team launches.
- If `.claude/dev-team/prompts/<id>.txt` does not exist, allow. There is no run to protect.
- If it exists and the prompt is not byte-identical to the file, deny with the reason
  `prompt hash mismatch for <id>`.
- A deny is reprinted once by the existing `UNCLAIMED` path. Do not add a second reprint
  policy. `print_unclaimed` already reprints a launch that never claimed. A denied Agent
  call never writes a claim file, so the same path covers it.

The conductor's `agent_type` is not a programmer role. The check has to run before
`guard_zcode` returns allow for a foreign role. Lane Write and Bash checks are unchanged.

`SKILL.md` conductor section: one line, "paste the Agent prompt verbatim; a hash mismatch
is denied and reprinted." Do not restate the guard.

Run `test_devteam_zcode_doctor.py`, `test_devteam_attack.py`, and the guard test module
that already drives `guard_zcode`. Add two guard cases: a matching claim prompt is
allowed, a claim prompt with one extra word is denied, a prompt with no claim id is
allowed.

### Step 5 — selftest

Add a section at the end of `glm-dev-team/scripts/selftest.sh`, using the file's `mkt` and
`check` helpers. One throwaway repo, one `kind: code` slice, profile `balanced`.

- Commit a parent function and a test that passes on the parent.
- Drive RED the way neighboring sections drive a slice, so `next` reaches `red-done` and
  prints a GREEN launch without a second `dispatch` command.
- Commit a GREEN that makes the parent test fail.
- Plant an attack report whose overlay fails on the GREEN tip and passes on the parent.
- Assert the output contains `ATTACK BLOCKER` and does not contain `S1: MERGED`.
- Apply a fix commit that makes the overlay pass, run `next` again, and assert `MERGED`.

No assertion may require the report to contain `APPROVED`.

Run `bash glm-dev-team/scripts/selftest.sh` from `glm-skills`. Then the full
`_shared/tests` discovery command from `CLAUDE.md`. Do not describe the skills as having
reached the bar until that selftest exits 0.

### Step 6 — glm-writing-plans

Do this after step 1, so `decide.py` is already vendored next to `plan_tool.py`. It does
not wait on the brainstorming or dev-team steps. It must not add an orchestrator call.
R0's three calls stay.

#### Pins

In `GLM` at the top of `plan_tool.py`, change the table to:

```python
GLM = {
    "light": ("glm-5.3-flash", "high", "glm-5.3-flash"),
    "std":   ("glm-5.3-flash", "high", "glm-5.3-flash"),
    "deep":  ("glm-5.3-flash", "max",  "glm-5.3-flash"),
}
```

`light` was `low`. `deep` was `glm-5.3`. `review_one` already calls `call_model` with tier
`deep`, so this one table moves the reviewer onto Flash at max. Leave `PLAN_MODEL_DEEP`
in place as an operator override, and print `OUT OF BAR` when it is set to something
other than `glm-5.3-flash`. Do not delete the override.

Agent files:

| File | model today | set model | set thoughtLevel | set injectAgentsMd |
| --- | --- | --- | --- | --- |
| `agents/glm-plan-task-writer.md` | Flash, max, true | Flash | high | false |
| `agents/glm-plan-task-writer-deep.md` | GLM-5.3, max, true | Flash | max | false |
| `agents/glm-plan-reviewer.md` | GLM-5.3, max, true | Flash | max | false |

`references/glm-tuning.md` restates the old tier table, including deep on GLM-5.3 and
light at low. Replace that table with one sentence: api-lane model and effort live only
in the `GLM` dict, agent-lane model and effort live only in the agent frontmatter. Keep
the failure-mode table. Fix the row that says a deep lane is a bigger model. Deep is
max effort on Flash.

In `SKILL.md` R3 rule 6, delete the claim that tier picks the model. Replace it with:
tier is a hint, `build` may raise it, and it never selects a model other than Flash.
In R4 item 3, delete "unless that spec section is non-functional". An uncovered heading
is an `ERR` to fix with a contract or with an `Out of scope` line. Do not add a fourth
call. The body stays under 500 lines. The description stays at or under 1024 characters.

Extend `ZcodeAgentAndDispatchTests` in `_shared/tests/test_adopt_plan.py` so each of the
three frontmatters contains `GLM-5.3-Flash` and the thoughtLevel in the table above, and
`injectAgentsMd: false`. Today that test only checks that the keys exist.

#### Coverage and symbols

`spec_coverage` stays the heading walker. `analyze` currently does `warns += spec_coverage(...)`.
Split the return into errors and ignored headings. A heading whose line contains one of
these substrings, case insensitive, is ignored: `non-goal`, `out of scope`, `background`,
`revision history`, `references`, `glossary`, `table of contents`. Every other uncovered
heading is an `ERR` from `analyze`, so `prepare` refuses to fan out. Do not leave it as
a warning the orchestrator may waive.

After `parse_contracts`, call `decide.extract_atoms` on the spec text. No model call.
Each atom must be a substring of the spec lines named by exactly one contract's `Spec`
range, or of the plan's `Out of scope` line. Zero homes or two homes is an `ERR` naming
the atom. A spec with no mechanical atoms does not skip the heading check.

For each entry in `c["external"]`, take the first identifier (`[A-Za-z_][A-Za-z0-9_]*`).
Read each `Read` path under the repo, skip files over 1 MB. The identifier must occur in
at least one of them. No `Read` path, or no occurrence, is `ERR <id>: existing symbol
<name> is not in a Read file`. Do not search the whole repo. A name the model remembers
but did not point at is the failure this check exists for.

#### Tier upgrade

One tuple, `DEEP_WORDS`, next to `GLM`. After contracts parse, if any spec-range line
matches a word in that tuple, set `c["tier"] = "deep"` when it was `light` or `std`, and
append `TIER <id> <old> -> deep (<word>)` to the build output. Never lower a `deep` the
contract already set. Words: `auth`, `password`, `token`, `secret`, `migration`,
`concurrent`, `thread`, `lock`, `race`, `payment`, `billing`. Match with a word boundary,
case insensitive, on the spec-range text only.

#### Review rewrite

In `review_one`, keep the early return when the reply starts with `APPROVED` or the
extracted body is under 80 characters. Before `save`, also discard the rewrite when:

- `assert_count(new) < assert_count(body)`
- any mechanical atom that occurs in `body` does not occur in `new`

`assert_count` counts matches of `\b(assert|assertEqual|assertTrue|assertFalse|pytest\.raises)\b`
and of `expect(`. Put it next to `lint_body` so both lanes share it.

On the agent lane the reviewer edits the task file itself. When `write_one` or
`lint-task` first marks a body `.ok`, write `tasks/<id>.md.asserts` with the count.
`lint_body` takes an optional previous count. When the file exists and the new count is
lower, that is an `ERR`, same channel as a missing `Expected:`. The reviewer prompt
already says to run the lint command and fix every `ERR`. Do not add a second copy of
this rule to the agent file. You may delete the sentence that tells the reviewer to
report `Status: Approved` as a verdict that ends the task. The reply can still be
`Status: Approved` when it changed nothing. The script is what keeps the body.

#### One split, inside build

Add `split_wide(cfg, plan, cs, spec, repo)` and call it from `cmd_build` after `prepare`
returns no errors and before the writer fan-out. Skip it on `--no-split`, on the agent
lane (no key), and when `PLAN_MODEL_DEEP` is outside the bar.

A contract is wide when its spec range covers more than 80 lines or `len(files) > 4`.
Take at most three, in id order. For each, one `call_model` at tier `std` (Flash, high).
The user text is the contract block plus the spec lines it names, and the instruction to
return two or three `#### Tnn` blocks that partition `Files` and cover the same `Spec`
lines. Parse with `parse_contracts`. Accept only when:

- `analyze` reports no errors on the plan with that one contract replaced by the new ones
- `decide.extract_atoms` coverage still holds
- the union of the new `files` lists equals the old list, and the lists do not overlap

Renumber with the existing sequential-id check by rebuilding the contract list in order
and running `analyze` again. On any failure, leave the original and print `SPLIT <id>
rejected`. On success, rewrite the Contracts section in the plan file and print
`SPLIT <id> -> <new ids>`. Cap the extra model calls at three. They sit inside the
existing `build` call, under the same 8-wide cap. They are not a fourth orchestrator turn.

#### Tests

New file `_shared/tests/test_plan_flash_gate.py`. No network. Stub `call_model` for the
split. Cases:

- an uncovered `## Behavior` heading is an `ERR`; an uncovered `## Background` heading
  is not
- an atom that sits in two spec ranges fails; an atom only in `Out of scope` passes
- `(existing)` `load_config` with no `Read`, or a `Read` file that does not contain the
  name, is an `ERR`
- a range containing `lock` raises `light` to `deep`; a contract already marked `deep`
  stays `deep`
- a review rewrite that deletes one `assert` is discarded; a rewrite that keeps the
  asserts and the atoms is saved
- a split whose files overlap is rejected; a split that partitions the files and covers
  the same lines replaces the contract
- `GLM["deep"][0] == "glm-5.3-flash"`

Run:

```bash
cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_flash_gate.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_plan.py' -v
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_lint.py' -v
```

The existing lint suite must stay green. The new checks are `ERR`s on top of `lint_body`,
not replacements for a signature or a `Run`/`Expected` pair.

## What Flash still will not match

A design choice with no fact, no failing command, and two options inside the margin is taste.
The user decides it. A bug that no test and no attack command can express, in particular a
numerical or concurrency proof, is reported as unchecked rather than waved through. Shipping
that slice requires the user to accept the assumption in the design message. That refusal is
the Opus behavior worth copying: do not sound certain where the check cannot be run.

## Definition of done

The procedure is "How to build it". A step is done only when its own test command exits 0.
Do not start a later step by weakening an earlier gate.

1. `test_decide.py` and `test_vendored.py` pass. No skill prose in this step.
2. `test_glm_brainstorm_check.py` passes, including the ledger cases. No live fetch in the suite.
3. Brainstorming `SKILL.md` is under 500 lines, the description is at or under 1024 characters,
   and `test_all_skills.py` passes. `glm-design-breaker.md` exists and pins Flash at max.
4. `test_devteam_attack.py`, `test_devteam_zcode_doctor.py`, and the guard hash cases pass.
   Balanced `pending` dispatches `red`. `red-done` dispatches `green`. Turbo still dispatches
   `slice`.
5. `bash glm-dev-team/scripts/selftest.sh` exits 0, including the attack section that blocks
   merge until the overlay passes, with no assertion on the word `APPROVED`. The full
   `_shared/tests` discovery command then passes.
6. `test_plan_flash_gate.py`, `test_adopt_plan.py`, and `test_plan_lint.py` pass. The three
   plan agents pin Flash. `GLM["deep"]` is `glm-5.3-flash`. An uncovered behavior heading
   is an `ERR`. A rewrite that drops an assertion is discarded.

Quality bar, measured on a frozen set of 10 design briefs and 10 implementation tasks kept
outside the skills as fixtures, scored by executable checks (atom coverage, cite resolution,
gate command, attack table), not by a model judge:

- Atom coverage and cite resolution at 100 percent on the fixture set. This is allowed to
  exceed Opus, because it is mechanical.
- Every fixture bug in the attack set produces a queued fix with Flash as the only model.
- On 10 frozen specs, every mechanical atom has one home, every `(existing)` symbol is in
  a Read file, and no plan that lints still has an uncovered behavior heading.
- A blinded read of the design fixtures is the taste check. Win-plus-tie against a single
  Opus 5.5 design on the same brief, at or above half the set, is the bar for "like". Below
  that, the residual is reported as taste and is not papered over with another prompt.

Until step 5's selftest and step 6's plan gate are green, the skills have not reached this
bar. Do not describe them as having reached it.

## Sources

Repo, read for this spec:

- `glm-brainstorming/SKILL.md` R2, R3, R6, R11, R14 and hard rule 7. Judgment on the main
  thread, low-effort lanes in prose, approval token, cite-before-use.
- `glm-brainstorming/glm-tuning.md` sections 1, 4, and 7. Shared blind spots, the failure
  table, and the offline checker.
- `glm-brainstorming/architectural.md` section 2. Three lenses, main-thread pick.
- `glm-dev-team/SKILL.md` and `agents/glm-programmer-lite.md` modes. Default `SLICE` versus
  high-risk `RED`/`GREEN`. Review fail-closed on a missing verdict.
- `glm-dev-team/scripts/devteam.py`. `APPROVED` without an Evidence heading is rejected. The
  heading is not executed.
- `docs/skill-criteria.md` sections 3 and 5. One home for a rule. Do not stack rules after a
  miss. Scripts own deterministic work.
- `_shared/sync.sh`. The vendoring pattern `decide.py` joins.
- `glm-writing-plans/SKILL.md` R0, R3, R4. Three orchestrator calls, tier as the model dial,
  and the non-functional escape on an uncovered heading.
- `glm-writing-plans/scripts/plan_tool.py`. `GLM["deep"]` is `glm-5.3`. `spec_coverage`
  returns warnings. `review_one` calls tier `deep` and keeps a rewrite whose lint count did
  not get worse. `lint_body` checks that a signature appears in the body, not that an
  `(existing)` name appears in a Read file.
- `glm-writing-plans/agents/glm-plan-task-writer-deep.md` and `glm-plan-reviewer.md` pin
  `GLM-5.3` at max with `injectAgentsMd: true`. The std writer already pins Flash.

The build procedure was checked against the code as it stands: `do_dispatch` always sets
`mode = "slice"` for code, `briefing_text` and `integrate_one` already implement `red` /
`green` / `red-done`, `cmd_claim` resets a green worktree to `base_sha`, `run_at_commit`
is the detached-checkout runner, `print_dispatch` launches `claim_prompt` rather than the
briefing, `guard_zcode` allows any tool that is not Write, Edit, or Bash before the role
check, and the three brainstorming agent files pin `GLM-5.3` while `test_devteam_zcode_doctor.py`
still expects three dev-team agents on `GLM-5.3`. The procedure names those sites so the
implementation does not invent a second scheduler.

Outside:

- Model Matchbook, Claude Opus 5.5 vs GLM 5.3 Flash, retrieved 2026-11-05. Axis numbers in
  the table above. https://modelmatchbook.com/compare/anthropic/claude-opus-5.5-20260921/vs/z-ai/glm-5.3-flash-20260826
- Vincent van Deth, "Five Model Families, One Agentic Harness", June 2026. Harness versus flat
  runner for GLM-5.2, not for 5.3-Flash and not against Opus 5.5. Used only as evidence that
  the harness is the wrong layer to rebuild. https://vincentvandeth.nl/blog/frontier-models-one-agentic-harness
- Stanford, "Scalable Weak-to-Strong Verifier Hardening", arXiv 2610.15924, October 2026.
  The hacker-fixer idea is adopted as fixture tests in `selftest.sh`, not as an online agent
  that edits the engine during a user run. https://arxiv.org/abs/2610.15924
- Cognaptus summary of REVEAL, 2026-11-02. Activation steering from frontier traces. Rejected
  as the method. Single-digit Terminal-Bench movement, needs weights. https://cognaptus.com/blog/2026-11-02-from-agent-traces-to-steering-signalswithout-finetuning/

UNVERIFIED: the exact parallel-tool-call ceiling of GLM-5.3-Flash. The existing skills already
assume "as few as two unless the prompt states a count", and this design keeps that assumption
by putting the count in the engine's launch line.
