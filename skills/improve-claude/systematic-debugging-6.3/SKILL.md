---
name: systematic-debugging
description: Root-cause-first debugging for any bug, test failure, flaky test, build/CI failure, regression, performance problem or unexpected behavior. Use BEFORE proposing or making any fix.
when_to_use: Error or stack trace, failing or intermittent test, "it worked before", passes locally but fails in CI, a fix that did not work, 2+ failed fix attempts. Scales from a 2-round fix to parallel fan-out of up to 64 workers.
---

# Systematic Debugging

**Iron Law:** no fix until you can write `ROOT CAUSE: X causes Y because Z` backed by evidence observed in this session (output, trace, diff, repro). A guess is not evidence. Speed comes from parallelism and fewer round-trips, never from skipping the root cause.

Scripts: `S=${CLAUDE_SKILL_DIR}/scripts` — prefix script commands with that absolute path (reference files write `$S/...`). If the variable was not substituted, use the `scripts/` folder next to this file. Every script supports `-h`.

## Speed rules (every lane)

- **Rounds are the cost; width is almost free.** Put every independent Read/Grep/Glob/git/short command in ONE message. Go sequential only when call B needs A's output.
- **Never wait idle.** Commands > ~30 s (suite, build, stress, bisect) run with `run_in_background: true` (no such parameter → `nohup <cmd> > /tmp/<name>.log 2>&1 &`, read the log later); keep investigating in the same round. Never edit, stash or check out a tree while a background command is running in it.
- **Keep context small, keep exit codes.** `set -o pipefail; <cmd> 2>&1 | tail -80` (or `grep -nE 'FAIL|Error|panic'`); runner flags `--bail` / `-x` / `-q`. Run the single failing test, not the suite, while investigating.
- **Volume → shell, judgment → agents.** Repetition (reruns, bisect) → scripts with `-j`. Independent reading/analysis → parallel subagents launched in one message.

## Step 0 — Triage into a lane (no tool call)

| Lane | Pick it when | Leave it when |
|---|---|---|
| **FAST** | Deterministic AND error names file:line AND the cause is fully visible there: syntax/type/compile error, missing import/export, misspelled identifier, wrong arity. **Not** null/undefined/bad-value errors — those usually originate elsewhere → STANDARD | 3 rounds without a verified fix, or 1 failed fix → STANDARD |
| **STANDARD** | Reproducible, cause not visible at the error site | Non-deterministic, multi-component, no hypothesis after Phase 2 (≈ 4 rounds), or 2 failed fixes → SWARM |
| **SWARM** | Intermittent/flaky · regression with unknown culprit · multi-component (CI→build→deploy, API→service→DB) · performance · many plausible causes | 3 failed fixes → STOP (see limit) |

Escalating keeps the failed-fix count. Never de-escalate after a failed fix. Entering SWARM: Read `references/parallel-playbook.md` in the same message as its first commands.

## FAST lane

1. **One round:** Read the code at the error site (±40 lines) + Grep the symbol + rerun the failing command if its output is not already in context.
2. **Next round:** write the ROOT CAUSE line citing what you saw → minimal fix.
3. **Next round:** rerun the exact failing command plus its test file if one exists. Pass → final report. A fix that only reveals the *next* compile error is progress, not a failed fix.

## STANDARD lane

### Phase 1 — Evidence (one wide round, at most one follow-up)

Batch in one message:
- `bash $S/snapshot.sh` — branch, dirty files, diff stat, recent commits, dependency-file commits, toolchain versions, CPU count (always exits 0).
- Read every in-repo frame of the stack trace, not only the top one.
- Grep the exact error text and the failing symbol.
- Run the minimal repro, filtered (background if slow).
- "It used to work" → `git log --oneline -S'<symbol>' -10` and `git diff <last-good>..HEAD --stat`.

Read errors completely: message, code, file:line, first in-repo frame, every `Caused by`, adjacent warnings.
Not deterministic → SWARM (`stress.sh`) before anything else. Fails only in CI → first reproduce CI conditions locally (same image/env vars, `CI=true`, CPU load via `stress.sh -j`); if impossible, add boundary logging to the CI job and read its output.
**Multi-component:** instrument every boundary in ONE run (what enters, what exits, env/config propagation per layer) → find the breaking boundary → investigate only that component.
**Bad value deep in the stack:** trace it backward to where it is created → `references/root-cause-tracing.md`.

### Phase 2 — Compare (same round as Phase 1 whenever possible)

- Find a working analogue: similar code in this repo, a passing sibling test, the last good commit, the reference implementation. Read the reference completely.
- List every difference between working and broken; do not pre-filter "can't matter".
- Note implicit dependencies: config, env vars, versions, ordering, shared state.

### Phase 3 — Hypothesis

- Write `H: <cause> because <evidence>. Experiment E: <one-variable change>. If H true: <result A>. If false: <result B>.` A ≠ B, or E is not worth running.
- Confirmed → Phase 4. Refuted → revert E, form a new H from the new evidence. Never stack changes.
- ≥ 2 live hypotheses with cheap experiments → run them simultaneously in isolated worktrees (playbook §4), not one per round.
- Stuck → say "I don't understand X", name the evidence that would settle it, get it.

### Phase 4 — Fix and verify

1. Turn the repro into a failing automated test (one-off script if no framework). See it fail for the expected reason.
2. One fix at the source, not at the symptom. No drive-by refactors.
3. Verify in one round: new test + failing test file (foreground); affected suite with the runner's native workers (background). Flaky bug → `stress.sh -b <baseline F/N>` with the baseline's `-n`/`-j`; proven only if Fisher p < 0.05 (playbook §6).
4. When cheap and nothing runs in the tree: revert only the fix, confirm the test fails, restore — proves causation.
5. Bad data crossed several layers → guards at each layer: `references/defense-in-depth.md`.
6. Timing bug → condition waits, never sleeps: `references/flaky-and-timing.md`.

## SWARM tools (details: `references/parallel-playbook.md`)

| Problem | Command | Speed-up |
|---|---|---|
| Intermittent failure → rate + failing logs | `bash $S/stress.sh -n 200 -- <cmd>` (`-j` defaults to CPUs) | N runs in ≈ N/J wall time |
| Regression, culprit unknown | `bash $S/bisect-parallel.sh -j 15 <good> <bad> -- <cmd>` | ⌈log₁₆ N⌉ rounds vs ⌈log₂ N⌉ |
| A test leaves files/dirs behind | `bash $S/find-polluter.sh -j 16 <path> '<glob>'` | one isolated worktree per worker |
| Several hypotheses / unknown location | subagents, 1 per hypothesis or area, in ONE message | independent contexts |

## Fix-attempt limit

Count every candidate fix that failed — in the main tree or in a parallel experiment. Diagnostic experiments (toggling a variable to learn, not to fix) do not count. **3 failed fixes → STOP.** Architecture signals: each fix exposes new coupling elsewhere, fixes need large refactors, symptoms move. Report what was ruled out and discuss with the user before attempt #4.

## Red flags → return to Phase 1

"Quick fix now, investigate later" · "just try X" · several changes then run tests · skipping the failing test · "probably X" with no evidence · adapting a pattern you have not read fully · listing fixes before tracing data flow · bumping a sleep/timeout/retry as the fix · a null check at the crash site · "one more attempt" after 2 failures · the user says "stop guessing", "is that actually happening?", "we're stuck".

| Rationalization | Reality |
|---|---|
| "Simple / urgent, no time" | FAST lane costs 2 rounds; guessing costs more. |
| "Prod is down" | Mitigate first with a reversible, cause-agnostic action (rollback, feature flag, failover, degrade the feature) — that is not a fix — while ONE parallel round gathers evidence (change timeline vs error onset, DNS/TLS/egress from the host, provider status). Root cause still precedes the code change. |
| "Several fixes at once saves time" | Parallelize isolated experiments, never fixes in one tree. |
| "Senior/author says it's X" | That is a hypothesis; one experiment confirms it. |
| "4 hours of sleeps can't be wasted" | Sunk cost. Delete them; a timing guess is not a root cause. |
| "I'll write the test after" | Untested fixes regress; the failing test is the proof. |

## When evidence says "no code root cause"

Only after ruling causes out with evidence (environment, external service, true nondeterminism): record what was ruled out, add bounded handling (timeout, capped retry with backoff, clear error), add logging that would catch it next time. Most "no root cause" verdicts are incomplete investigations.

## Final report (always, ≤ 6 lines)

`ROOT CAUSE` · `EVIDENCE` · `FIX` (file:line) · `VERIFIED BY` (commands + result) · `RISK / FOLLOW-UP`
