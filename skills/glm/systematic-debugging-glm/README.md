# systematic-debugging 9.0-glm

Root-cause-first debugging, rebuilt for **GLM-5.3 / GLM-5.3-Flash** on **OpenCode** and **ZCode**.

The Iron Law is unchanged: no fix until a `ROOT CAUSE: X causes Y because Z` line is backed by evidence observed in this session. Everything else changed to remove model turns.

## What is different from the generic version

The generic skill buys speed by telling the model to put many tool calls in one message and to launch many subagents at once. On this pairing, both assumptions fail:

- GLM-5.3 emits only a couple of tool calls per turn, so a "batch of 12 reads" quietly becomes six round-trips.
- OpenCode dispatches subagent tasks one at a time, so a 64-way fan-out becomes 64 sequential runs. (ZCode does run foreground subagents in parallel.)

So the parallelism moved **out of the model's turn and into the tools**. One call per phase; each call opens its own threads, up to 64.

| Phase | 9.0-glm: one call | Generic version |
|---|---|---|
| Evidence | `debug_tool.py probe` | snapshot + N frame reads + M greps + repro + git history, batched by the model |
| N commands | `debug_tool.py run -j N` | N Bash calls in one message |
| Hypotheses | `debug_tool.py experiment -j N` | one subagent per hypothesis |
| Judgment fan-out | `debug_tool.py scan -j 64` | one subagent per area |

Plus: deterministic lane triage printed by `probe` (no model reasoning spent on a routing table), an effort ladder so mechanical work does not run at `reasoning_effort: max`, a byte-identical prompt prefix across all 64 `scan` workers so the provider cache hits from the second worker on, a 5-line state carry against long-horizon drift, and prose rewritten as numbered rules — GLM follows those better than behavior tables.

## Install

| Harness | Path |
|---|---|
| OpenCode | `~/.config/opencode/skills/systematic-debugging/` (or `.opencode/skills/…` per project; `~/.claude/skills/` and `~/.agents/skills/` are read too) |
| ZCode | `~/.zcode/skills/systematic-debugging/` — invoke with `$systematic-debugging`; copy `agents/debug-worker.md` to `~/.zcode/agents/` |
| Claude-compatible | `~/.claude/skills/systematic-debugging/` |

```bash
export ZAI_API_KEY=<GLM Coding Plan key>       # optional: enables the 64-thread scan lane
python3 <skill>/scripts/debug_tool.py doctor --ping
python3 <skill>/scripts/debug_tool.py setup --harness opencode   # or zcode | claude
```

Needs bash (3.2+ works), git and python3 (stdlib only). `timeout`/`gtimeout` is optional, for `-t`. Without an API key everything still works except `scan`, which falls back to writing subagent prompts.

## Layout

```
SKILL.md                         12 numbered rules, loaded on use
references/glm-tuning.md         model + harness facts, failure modes
references/parallel-playbook.md  concurrency layers, isolation, recipes
references/root-cause-tracing.md backward tracing, one-shot instrumentation
references/defense-in-depth.md   layered guards after the fix
references/flaky-and-timing.md   condition waits, flake root causes
scripts/debug_tool.py            probe · run · experiment · scan · doctor · setup
scripts/snapshot.sh              git, deps, toolchain, CPUs in one call
scripts/stress.sh                N parallel reruns, Wilson CI, Fisher test vs baseline
scripts/bisect-parallel.sh       k-ary git bisect in worktrees, log_(J+1) N rounds
scripts/find-polluter.sh         parallel polluter search, one worktree per worker
agents/debug-worker.md           subagent definition for the fallback lane
evals/                           pressure + speed scenarios with pass criteria
```

## Measured

Verified in this build (2-CPU container; the model-turn column is what actually dominates wall time in practice):

| | measured |
|---|---|
| `probe` on a 3-frame traceback | 0.3 s, **one** call — replaces snapshot + 3 frame reads + 2 greps + git history + 3 repro runs |
| `scan`, 64 workers, 0.4 s mock latency | 0.65 s wall, **peak concurrency 64**, **1 distinct prompt prefix** (cache hit from worker 2) |
| `experiment`, 8 hypotheses × 2 arms | 1.4 s, 16 isolated worktrees, 1 CONFIRMED / 7 REFUTED |
| `run`, 3 × 1 s commands | 1.0 s wall, exit codes preserved |
| `bisect-parallel.sh -j 5`, 13 commits | 2 rounds, correct culprit |
| `stress.sh -n 60 -j 8` | 1 s, rate + Wilson CI + failing logs |

Statistics in `stress.sh` were cross-checked against SciPy (`fisher_exact`, Wilson interval).

## Quality guards that did not move

Iron Law; two-sided hypotheses; failed candidate fixes count toward the 3-fix stop even inside a worktree, diagnostic toggles do not; null/undefined/KeyError errors never take the FAST lane; statistical proof for flaky fixes (Fisher p < 0.05, not "it passed a few times"); reversible mitigation allowed during a production incident but never as the fix.

One guard got **stronger**: `experiment` now gives the control arm and the treatment arm a worktree each. Sharing one tree between arms lets build caches and stale compiled files leak across — during this build that silently turned a real root cause into "REFUTED" until the arms were separated.
