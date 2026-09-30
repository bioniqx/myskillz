# Evals for systematic-debugging

Not loaded at runtime. Run each scenario in a fresh subagent that has the skill (launch all 6 in ONE message so they run in parallel) and grade against the expected behavior below.

| Test | Pass criteria |
|---|---|
| test-academic | Cites: evidence-backed ROOT CAUSE line before fixes; FAST/STANDARD/SWARM criteria; null/undefined errors excluded from FAST (value originates elsewhere); two-sided hypothesis (result if true vs if false); failed candidate fixes count even in worktrees, diagnostic toggles don't; separate worktrees / per-job TMPDIR, ports, no shared stash; `stress.sh -b 14/200` with Fisher p < 0.05, or ≈ 3 / Wilson-lower-bound zero-failure runs. |
| test-fast-lane | FAST lane. Round 1: one message with Read of total.ts around line 42 + Grep `subTotal` (other usages) + (optional) Read of the `Cart` type. Round 2: ROOT CAUSE line citing the TS error + the type definition → rename → rerun `npm run build` (and related test). No subagents, no snapshot/scripts, ≤ 3 rounds. |
| test-swarm | SWARM lane; playbook read in the same message as the first commands. Background `stress.sh` on HEAD with `-n` ≥ 30 and `-j` ≤ 16 (40 s CPU-bound tests; check whether the runner already parallelizes) to get a baseline rate + failing logs, while reading failing logs/CI output in parallel. Repro script copied outside the repo. `bisect-parallel.sh` from `v2.3.0` to HEAD with each probe wrapped in `stress.sh -n` ≈ 30 (≈ 3/p; p = 10%) `-j 1`, bisect `-j` ≈ 15 so total processes ≤ 16 → ⌈log₁₆ 800⌉ = 3 rounds; no `--link` if dependency files changed in the range. Then read the culprit diff, form two-sided hypotheses, prove the fix with `stress.sh -b F/N` (same `-n`/`-j`, p < 0.05). No retry/sleep bump as the fix. |
| test-pressure-1 (prod down) | Chooses a reversible, cause-agnostic mitigation (rollback / failover / flag) if one exists AND in the same round gathers evidence in parallel (recent deploys/changes, provider status, network/DNS/TLS from the host, error-rate start time). Does NOT ship "add retry" as the fix without evidence. |
| test-pressure-2 (sunk cost) | A: deletes the sleeps; starts Phase 1 (status never updates → trace why; stress to measure). May stop for dinner and resume, but does not commit `sleep(5000)`. |
| test-pressure-3 (authority) | Treats the senior's claim as a hypothesis; proposes one fast discriminating check (e.g. token before/after middleware, middleware source) — can be run in parallel while the call continues; no unverified refresh call merged. |

Scoring: speed = number of rounds and whether independent calls were batched; quality = Iron Law respected, isolation respected, correct statistics.
