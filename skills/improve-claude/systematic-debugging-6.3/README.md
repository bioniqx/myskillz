# systematic-debugging (speed-optimized, parallel)

Root-cause-first debugging for Claude Code, rebuilt for minimum wall-clock time: adaptive lanes (FAST / STANDARD / SWARM), one-message parallel tool batches, background jobs, isolated parallel experiments, and scripts that fan out to 64 workers. Not loaded by Claude unless it opens it.

## Install
Copy the folder to `~/.claude/skills/systematic-debugging/` (personal) or `.claude/skills/systematic-debugging/` (project). Scripts need bash (3.2+ works, macOS default), git, and optionally `timeout`/`gtimeout` for `-t`.

## Layout
```
SKILL.md                         core process (~2k tokens, loaded on use)
references/parallel-playbook.md  concurrency layers, isolation, hypothesis/search swarms, recipes
references/root-cause-tracing.md backward tracing + one-shot instrumentation
references/defense-in-depth.md   layered guards after the fix
references/flaky-and-timing.md   condition waits, flake root causes
scripts/snapshot.sh              one-call evidence snapshot (git, deps, toolchain, CPUs)
scripts/stress.sh                N parallel reruns, failure rate + Wilson CI, Fisher test vs baseline
scripts/bisect-parallel.sh       k-ary git bisect in worktrees (log_(J+1) N rounds)
scripts/find-polluter.sh         parallel polluter search, one worktree per worker
evals/                           pressure + speed scenarios with pass criteria
```

## Optional settings for maximum parallelism (`~/.claude/settings.json`)
```json
{
  "env": { "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "64" },
  "permissions": { "allow": ["Bash(git worktree *)"] }
}
```
Default is 20 concurrent subagents (extra ones queue). Shell-level parallelism in the scripts is not limited by this setting. Pre-approving the scripts themselves (`Bash(bash /abs/path/scripts/*)`) also pre-approves whatever command you pass after `--`, so only do that in trusted repos or auto mode.

## Measured (synthetic repo, 300 commits, culprit at #137, 3 s test)
| | wall time |
|---|---|
| `git bisect run` | 27.1 s (~9 sequential test runs) |
| `bisect-parallel.sh -j 15` | 8.0 s (2 rounds, verified endpoints) |
| `stress.sh -n 200 -j 32`, 0.2 s test | 1.8 s |
| `find-polluter.sh` 40 files × 0.5 s, `-j 8` vs `-j 1` | 1.2 s vs 3.1 s (polluter was 6th in order) |

Statistics in `stress.sh` cross-checked against SciPy (`fisher_exact`, Wilson interval).

## Changes vs original
- Lanes: trivial deterministic bugs fixed in 2 rounds; hard ones get parallel tooling. Iron Law unchanged.
- Parallel-by-default instructions; background long commands; filtered output with preserved exit codes.
- Two-sided hypotheses; parallel hypothesis swarm with worktree isolation; failed candidate fixes in worktrees still count toward the 3-fix stop.
- Flaky-fix proof is statistical (Fisher exact / Wilson lower bound) instead of "it passed a few times".
- Prod incidents: reversible mitigation allowed before root cause, never a guessed code fix.
- Dev artifacts (pressure tests, creation log) moved out of the runtime path into `evals/`; Lace-specific example replaced by generic TS/Python helpers.
