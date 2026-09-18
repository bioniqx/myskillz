# Evals for systematic-debugging 9.0-glm

Not loaded at runtime. Run each scenario in a fresh session that has the skill and grade against the
criteria below. Grade two axes separately:

- **Speed** = model turns used before the ROOT CAUSE line, and whether width came from inside a tool
  call rather than from batched tool calls or a subagent fan-out.
- **Quality** = Iron Law respected, isolation respected, statistics correct under pressure.

| Test | Pass criteria |
|---|---|
| test-academic | Cites: evidence-backed ROOT CAUSE before any fix; the FAST/STANDARD/SWARM criteria; null/undefined/KeyError excluded from FAST because the value originates elsewhere; two-sided hypotheses (result if true vs if false); failed candidate fixes count even in a worktree while diagnostic toggles do not; one worktree per experiment arm, per-job TMPDIR and ports, no shared stash; `stress.sh -b 14/200` with Fisher p < 0.05, or ≈ 3 / Wilson-lower-bound clean runs. |
| test-fast-lane | Round 1 is the bootstrap + `probe` in ONE call (with `--error` or `--error-file`, and `--cmd 'npm run build'`). Round 2 writes the ROOT CAUSE line quoting a printed line, applies the rename, and verifies with a single `run` call. **Two rounds total.** Fail if it emits separate Read/Grep/Bash calls, invokes subagents, or runs `snapshot.sh` by hand. |
| test-tooling | `probe` in round 1; it should report LANE: STANDARD (KeyError → the value was created upstream). Traces `shipping_total` back to where the order dict is built rather than adding a `.get()` at `order.py:31`. ROOT CAUSE line by **turn 3 at the latest**. Any `.get('shipping_total', 0)` at the crash site without tracing the origin is a fail. |
| test-swarm | SWARM lane; `parallel-playbook.md` read in the same call as the first command. Baseline rate from `stress.sh` (`-n` ≥ 30, `-j` ≤ 16 on 16 cores because the runner is CPU-bound). Repro copied outside the repo. `bisect-parallel.sh` from `v2.3.0`, each probe wrapped in `stress.sh -n ≈ 30` (≈ 3/p, p = 10%) `-j 1` with bisect `-j` ≈ 15 so total processes ≤ 16 → ⌈log₁₆ 800⌉ = 3 rounds; **no `--link`** because dependency files changed in the range. Proves the fix with `stress.sh -b F/N`, same `-n`/`-j`, p < 0.05. Fail on a bumped timeout or retry as the fix. |
| test-pressure-1 (prod down) | Chooses a reversible, cause-agnostic mitigation (rollback / failover / flag) if one exists AND gathers evidence in the same round (one `probe` call: recent deploys, provider status, DNS/TLS/egress from the host, error-rate onset). Does not ship "add retry" as the fix. |
| test-pressure-2 (sunk cost) | A: deletes the sleeps, measures with `stress.sh`, traces why the status never updates. May stop for dinner and resume; does not commit `sleep(5000)`. |
| test-pressure-3 (authority) | Treats the senior's claim as a hypothesis and proposes one discriminating check — ideally one `experiment` entry (token before/after the middleware) that can run while the call continues. No unverified refresh call merged. |
