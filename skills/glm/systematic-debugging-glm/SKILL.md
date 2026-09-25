---
name: systematic-debugging
description: Root-cause-first debugging for any bug, test failure, flaky test, build/CI failure, regression, performance problem or unexpected behavior - use BEFORE proposing or making any fix. Triggers - an error or stack trace, a failing or intermittent test, "it worked before", passes locally but fails in CI, a fix that did not work, 2+ failed fix attempts. One tool call per phase instead of many, and fan-out to 64 parallel workers from inside the tools, so width costs no extra model turns.
license: MIT
metadata:
  version: "9.0-glm"
  models: "glm-5.3, glm-5.3-flash"
  harness: "opencode, zcode, claude-compatible"
---

# Systematic Debugging

**Iron Law:** no fix until you can write `ROOT CAUSE: X causes Y because Z`, backed by evidence you observed in this session (output, trace, diff, repro). A guess is not evidence. Speed comes from fewer model turns, never from skipping the root cause.

## R0. Bootstrap — put this in front of your FIRST command, once

```bash
for d in "${CLAUDE_SKILL_DIR:-}" .opencode/skills/systematic-debugging ~/.config/opencode/skills/systematic-debugging .claude/skills/systematic-debugging ~/.claude/skills/systematic-debugging .agents/skills/systematic-debugging ~/.agents/skills/systematic-debugging ~/.zcode/skills/systematic-debugging; do [ -f "$d/scripts/debug_tool.py" ] && S=$(cd "$d/scripts" && pwd) && break; done; echo "S=$S"
```

Every tool output starts with `S=<absolute path>`. Shell variables do not survive between tool calls, so paste that **literal absolute path** into every later command — `$S` below is shorthand for it, not a variable you can rely on. `python3 $S/debug_tool.py -h` and every subcommand's `-h` list the flags.

## R1. One call per phase — do not batch tool calls, batch *inside* one call

You emit few parallel tool calls per turn, and each turn costs seconds of latency. So width never lives in your message; it lives inside the tools, which open up to 64 threads themselves.

| Phase | Exactly one call | Replaces |
| --- | --- | --- |
| Evidence | `python3 $S/debug_tool.py probe --cmd '<repro>' --error-file <file>` | snapshot + stack-frame reads + greps + repro + history + triage |
| Any N commands | `python3 $S/debug_tool.py run -j 8 'cmd1' 'cmd2' 'cmd3'` | N separate Bash calls |
| Hypotheses | `python3 $S/debug_tool.py experiment --spec exp.json -j 16` | N subagents, each running one experiment |
| Judgment fan-out | `python3 $S/debug_tool.py scan --area A --area B --question '...'` | N subagents reading N areas |
| Flaky / bisect / polluter | `bash $S/stress.sh` · `bash $S/bisect-parallel.sh` · `bash $S/find-polluter.sh` | dozens of sequential reruns |

Rules:

1. Round 1 is always `probe`. Put a long error into a file first; pass `--cmd` whenever you have a repro command.
2. Never run two shell calls in a row when `run` can do both in one.
3. Anything over ~60 s that you are not blocked on: `nohup <cmd> > /tmp/<name>.log 2>&1 &`, keep working, read the log later. Never edit, stash or check out a tree while a background command runs in it, and never `git stash` while a worktree or background job is live — the stash is shared by the whole repo.
4. Run the single failing test, not the suite, while investigating. The tools already keep exit codes and tail the output for you.

## R2. Triage — `probe` prints `LANE:` for you

Take the lane `probe` printed. Override it only for these three reasons, and say which:

1. FAST → STANDARD after 3 rounds without a verified fix, or after 1 failed fix.
2. STANDARD → SWARM when the repro is not reproducible, when no hypothesis survives round 3, or after 2 failed fixes.
3. Never de-escalate after a failed fix, and escalation keeps the failed-fix count.

A null / undefined / None / nil / KeyError / index-out-of-range error is never FAST: the bad value was created somewhere upstream of the line that crashed.

## R3. FAST lane — 2 rounds

1. `probe` (already done). The frame window and grep hits it printed are your evidence.
2. Write the `ROOT CAUSE` line quoting a printed line → make the minimal fix → `python3 $S/debug_tool.py run '<the failing command>' '<its test file>'` in the same call. A fix that only reveals the *next* compile error is progress, not a failed fix.

## R4. STANDARD lane — 3 rounds

1. **Evidence** — `probe` output. Read errors completely: message, code, file:line, every in-repo frame, every `Caused by`, adjacent warnings. A bad value deep in the stack → trace it back to where it is *created*, not where it is used: `references/root-cause-tracing.md`. Multi-component (CI→build→deploy, API→service→DB) → instrument every boundary in ONE run (what entered, what exited, config per layer), then investigate only the boundary that broke. Fails only in CI → first reproduce CI conditions locally (same image, same env vars, `CI=true`, load via `stress.sh -j`); if that is impossible, add boundary logging to the CI job and read its output.
2. **Compare and hypothesize, in one message.** Find a working analogue (a sibling test that passes, the last good commit, the reference implementation) and list every difference — do not pre-filter "can't matter" — including the implicit ones: config, env vars, versions, ordering, shared state. Then write 2–4 hypotheses in the spec file:

   ```bash
   python3 $S/debug_tool.py experiment --template > /tmp/exp.json     # fill in: hypothesis, cmd, and ONE of patch_file / env / treatment_cmd
   python3 $S/debug_tool.py experiment --spec /tmp/exp.json -j 16
   ```

   Each hypothesis changes exactly one variable. The tool runs the control and treatment arms in two separate worktrees at the same time, which is also the causation proof the old manual "revert the fix, watch it break, restore" step gave you. CONFIRMED means one arm passed and the other failed — nothing else. Refuted → the evidence changed; write new hypotheses, never wilder ones.
3. **Fix and verify** — one fix at the source, no drive-by refactors. Turn the repro into a failing automated test first and see it fail for the expected reason. Then one call:

   ```bash
   python3 $S/debug_tool.py run -j 4 '<new test>' '<the failing test file>' '<affected suite>'
   ```

   Flaky bug → prove it with `bash $S/stress.sh -b <baseline F/N>` at the baseline's `-n`/`-j`; only Fisher p < 0.05 counts. Bad data crossed layers → `references/defense-in-depth.md`. Timing bug → condition waits, never sleeps → `references/flaky-and-timing.md`.

## R5. SWARM lane — 4 to 6 rounds

Read `references/parallel-playbook.md` in the same call as the first command below.

1. Intermittent → `bash $S/stress.sh -n 200 -- <single test cmd>` for a failure rate, a Wilson interval and failing logs. Measure, never eyeball.
2. Regression, culprit unknown → copy the repro outside the repo, then `bash $S/bisect-parallel.sh -j 15 <good> HEAD -- sh /tmp/repro.sh` (⌈log₁₆ N⌉ rounds instead of ⌈log₂ N⌉).
3. A test leaves files behind → `bash $S/find-polluter.sh -j 16 <path> '<test glob>'`.
4. Unknown location or many plausible causes → `python3 $S/debug_tool.py scan --area <pkg> --area <pkg> --question '<one question>' --context-file /tmp/evidence.txt`. It fans out to 64 workers itself, with one shared prefix so the cache hits from the second worker on. With no API key it writes the worker prompts to files and tells you to dispatch them as subagents instead — dispatch them all in one message.
5. Everything the swarm returns is a *lead*. Promote a lead to a cause only through `experiment`.

## R6. Fix-attempt limit

Count every candidate fix that failed, in the main tree or in a worktree. Diagnostic toggles (changing a variable to learn, not to fix) do not count. **3 failed fixes → STOP.** Architecture signals: each fix exposes new coupling, fixes need large refactors, symptoms move. Report what was ruled out and talk to the user before attempt #4.

## R7. Effort and model ladder

Thinking is always on; only the effort level is yours to choose. Spending `max` on a mechanical round is pure latency.

| Work | Effort | Tier flag for `scan` |
| --- | --- | --- |
| Reading `probe` output, running commands, writing the report | low | `--tier light` |
| Drafting hypotheses, comparing against a working analogue | high | `--tier std` (default) |
| Choosing between confirmed causes, designing the fix, architecture calls | max | `--tier deep` |

`scan` sets this per worker for you. For your own turns, say the level you are using in one word and keep it there for the round.

## R8. State carry — restate before each lane change and before the fix

Five lines, no more: `BUG:` · `LANE:` · `EVIDENCE SO FAR:` · `RULED OUT:` · `FAILED FIXES: n/3`. This is what keeps a long investigation from drifting.

## R9. Red flags → go back to R4.1

"Quick fix now, investigate later" · "just try X" · several changes then run the tests · skipping the failing test · "probably X" with no evidence · adapting a pattern you have not read fully · listing fixes before tracing the data flow · bumping a sleep, timeout or retry as the fix · a null check at the crash site · "one more attempt" after 2 failures · the user says "stop guessing", "is that actually happening?", "we're stuck".

| Rationalization | Reality |
| --- | --- |
| "Simple / urgent, no time" | FAST costs 2 rounds; guessing costs more. |
| "Prod is down" | Mitigate first with a reversible, cause-agnostic action (rollback, flag, failover, degrade) — that is not a fix — while ONE `probe` call gathers evidence. The root cause still precedes the code change. |
| "Several fixes at once saves time" | Parallelize isolated experiments, never fixes in one tree. |
| "Senior/author says it's X" | That is a hypothesis; one `experiment` entry settles it. |
| "4 hours of sleeps can't be wasted" | Sunk cost. Delete them; a timing guess is not a root cause. |
| "I'll write the test after" | Untested fixes regress; the failing test is the proof. |

## R10. When evidence says "no code root cause"

Only after ruling causes out with evidence (environment, external service, true nondeterminism): record what was ruled out, add bounded handling (timeout, capped retry with backoff, clear error) and logging that would catch it next time. Most "no root cause" verdicts are incomplete investigations.

## R11. Final report — always, at most 6 lines

`ROOT CAUSE` · `EVIDENCE` · `FIX` (file:line) · `VERIFIED BY` (commands + result) · `RISK / FOLLOW-UP`
