# systematic-debugging 10.0

Root-cause-first debugging for OpenCode v2. Every model turn, and every worker the skill starts, runs on the model selected in the OpenCode window; nothing here sets a provider, model or effort.

The Iron Law: no fix until a `ROOT CAUSE: X causes Y because Z` line is backed by evidence observed in this session. Everything else exists to remove model turns.

## How it saves turns

One call per phase, and each call opens its own local threads (`-j` up to 64 or the CPU count; model workers started by `scan` run in waves of 6, `OC_MAX_LANES` up to 8):

| Phase | One call | Without the tool |
|---|---|---|
| Evidence | `oc_debug_tool.py probe` | snapshot + N frame reads + M greps + repro + git history, one call each |
| N commands | `oc_debug_tool.py run -j N` | N shell calls |
| Hypotheses | `oc_debug_tool.py experiment -j N` | one worker per hypothesis |
| Judgment fan-out | `oc_debug_tool.py scan`, then the printed dispatch rows | one brief per area, written by hand |

Plus deterministic lane triage printed by `probe`, a byte-identical brief prefix across all `scan` workers so the provider cache can hit from the second worker on, a 5-line state carry against long-horizon drift, and prose written as numbered rules.

## Fan-out

`scan` writes one brief per area and prints one dispatch row per brief for the `oc-debug-worker` agent, each with `background: true`. Make every printed call in one turn, one after another without waiting, then end the turn; each worker replies with a `VERDICT:` block. This works in interactive sessions only. `scan` never calls a model itself.

## Install

OpenCode v2 only. Put the folder at `~/.config/opencode/skills/oc-systematic-debugging/` (or `$OPENCODE_CONFIG_DIR/skills/oc-systematic-debugging/`, or `.opencode/skills/oc-systematic-debugging/` per project). Run `sh install-opencode.sh` once to install the `oc-debug-worker` agent.

    python3 <skill>/scripts/oc_debug_tool.py doctor
    python3 <skill>/scripts/oc_debug_tool.py setup

Needs bash (3.2+ works), git and python3 (stdlib only). `timeout`/`gtimeout` is optional, for `-t`.

## Layout

    SKILL.md                         12 numbered rules, loaded on use
    references/parallel-playbook.md  concurrency layers, isolation, recipes
    references/root-cause-tracing.md backward tracing, one-shot instrumentation
    references/defense-in-depth.md   layered guards after the fix
    references/flaky-and-timing.md   condition waits, flake root causes
    scripts/oc_debug_tool.py            probe · run · experiment · scan · doctor · setup
    scripts/oc-snapshot.sh              git, deps, toolchain, CPUs in one call
    scripts/oc-stress.sh                N parallel reruns, Wilson CI, Fisher test vs baseline
    scripts/oc-bisect-parallel.sh       k-ary git bisect in worktrees, log_(J+1) N rounds
    scripts/oc-find-polluter.sh         parallel polluter search, one worktree per worker
    opencode/agents/oc-debug-worker.md  worker agent for the scan rows (declares no model)
    evals/README.md                     manual scenarios graded by hand, never loaded at runtime

## Measured

Verified in a 2-CPU container:

| | measured |
|---|---|
| `probe` on a 3-frame traceback | 0.3 s, one call |
| `experiment`, 8 hypotheses x 2 arms | 1.4 s, 16 isolated worktrees, 1 CONFIRMED / 7 REFUTED |
| `run`, 3 x 1 s commands | 1.0 s wall, exit codes preserved |
| `oc-bisect-parallel.sh -j 5`, 13 commits | 2 rounds, correct culprit |
| `oc-stress.sh -n 60 -j 8` | 1 s, rate + Wilson CI + failing logs |

Statistics in `oc-stress.sh` were cross-checked against SciPy (`fisher_exact`, Wilson interval).

## Quality guards that did not move

Iron Law; two-sided hypotheses; failed candidate fixes count toward the 3-fix stop even inside a worktree, diagnostic toggles do not; null/undefined/KeyError errors never take the FAST lane; statistical proof for flaky fixes (Fisher p < 0.05, not "it passed a few times"); reversible mitigation allowed during a production incident but never as the fix.

`experiment` gives the control arm and the treatment arm a worktree each. Sharing one tree between arms lets build caches and stale compiled files leak across and can turn a real root cause into "REFUTED".

## Changelog

10.0 - OpenCode v2 only. `scan` always writes worker briefs and prints one background dispatch row per worker plus a `NEXT:` line that tells the model to read the `VERDICT:` replies; it no longer calls a model API. Removed the tier, model and effort flags, the API-key and base-URL handling, harness detection and the other-harness setup blocks. The `oc-debug-worker` agent declares no model, and the model-tuning reference and the duplicate top-level agent file are deleted.

Parity repair against the original systematic-debugging 6.3 (still 10.0): the control and treatment arms of a hypothesis run one after the other; SWARM routing again covers non-deterministic, multi-component, performance, many-cause and unknown-culprit failures; the worker agent gets `steps: 12`; `scan` prints its dispatch rows in waves of at most 8 workers; evals are ported into `evals/README.md`.
