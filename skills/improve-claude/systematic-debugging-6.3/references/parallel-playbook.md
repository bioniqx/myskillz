# Parallel Debugging Playbook (up to 64 concurrent workers)

Goal: cut wall-clock time with width without letting parallel work corrupt the evidence.
`$S` = the absolute scripts path from SKILL.md; start script commands with `S=<that path>;`.

## 1. Choose the cheapest layer that fits

| Layer | Concurrency | Extra tokens | Use for |
|---|---|---|---|
| Several tool calls in one message | keep a batch readable (≈ 5–15 calls) | none | reads, greps, git queries, short commands |
| Shell processes (`-j`, `xargs -P`, runner workers) | up to 64; CPU-bound → CPU count | none | reruns, bisect, polluter search, suites |
| Subagents (Agent tool) | 20 at once by default, extra ones queue (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`); nesting depth 3 | ≈ linear | judgment: reading an area, running one hypothesis experiment |
| Dynamic workflow | 16 at a time; only if the user opted in (`ultracode` / "use a workflow") | high | many agents in total across staged passes, adversarial cross-checks |

Volume goes to the shell; only judgment goes to agents. More than 20 subagents *simultaneously* needs `"env": {"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "64"}` in settings; otherwise extras queue (correct, not faster).

## 2. Width

- CPU-bound (tests, builds): total processes ≤ CPU count. A runner that already uses all cores (jest, vitest, pytest -n auto, go test) counts as one job using every CPU — do not multiply it.
- IO-bound (network, waiting on services): up to 64, each job with its own port/DB/temp dir; respect remote rate limits.
- Agents: one per genuinely independent unit (hypothesis, module, service). Beyond ~8 for one bug, merge cost usually exceeds the gain unless the search space is truly wide.
- Launch the whole batch in ONE message. One launch per round serializes everything.

## 3. Isolation (the quality guard)

Parallel experiments that write anything must not share mutable state.

- Worktree from current HEAD **with uncommitted changes**:
  ```bash
  wt=$(mktemp -d)/wt; git worktree add --detach "$wt" HEAD
  git diff HEAD --binary > "$wt.patch"; [ -s "$wt.patch" ] && git -C "$wt" apply "$wt.patch"
  ```
  Copy needed untracked/ignored files (`.env`, generated code). Clean up: `git worktree remove --force "$wt"; git worktree prune`.
- Agent tool `isolation: "worktree"` branches from the **default branch, not your HEAD** — use only if the bug reproduces there; otherwise create the worktree and give the agent its path.
- Per job: `TMPDIR`, port, DB/schema name, cache dir. Scripts export `STRESS_RUN` / `BISECT_JOB` / `POLLUTER_JOB`; combine them when nested: `PORT=$((20000 + ${BISECT_JOB:-0} * 100 + ${STRESS_RUN:-0}))`.
- `--link node_modules` (repo-root-relative; `--link packages/app/node_modules` for a package) symlinks deps into worktrees. Tests that write into linked dirs break isolation.
- `git stash` is shared by all worktrees of a repo — never stash from parallel workers.
- Anything outside the repo (`~/.cache`, a shared DB, system services) is shared: serialize or namespace.

## 4. Hypothesis swarm (parallel Phase 3)

1. List hypotheses from Phase 1–2 evidence, each with a discriminating experiment and predicted result if true AND if false. Drop those without.
2. Rank by likelihood × cheapness; run the top K together, each changing ONE variable in its own worktree.
3. **CONFIRMED** only if toggling the variable flips the outcome both ways (break ↔ fix). Flaky bug: both arms use the same `-n` and `-j`, run one after another (not concurrently competing for CPU), and the difference must be significant (`stress.sh -b`, §6).
4. Several confirmed → one upstream cause or an interaction: test the combination or trace upstream. None → new evidence, not wilder guesses.
5. A candidate *fix* that fails counts toward the 3-fix limit even in a worktree. Apply exactly one fix to the main tree, then Phase 4.

Subagent prompt (all in one message; `run_in_background` when they take minutes):

```
Investigate ONE hypothesis. Do NOT edit <main repo path>. Do not use git stash.
Context (≤10 lines): <error, repro command, key evidence>
Hypothesis: <H>. Experiment: <one-variable change>. If true: <A>. If false: <B>.
Workspace: <worktree path> — write only here.
Flaky: run both arms with S=<scripts path>; bash $S/stress.sh -n <N> -j <J> [-b F/N].
Reply in ≤12 lines:
VERDICT: CONFIRMED | REFUTED | INCONCLUSIVE
EVIDENCE: <exact commands + decisive output lines>
ROOT CAUSE: <X causes Y because Z, file:line> (if confirmed)
FIX DIFF: <≤15 lines or n/a>
NEW LEADS: <optional>
```

Model: pure search/reading → `subagent_type: Explore` (read-only; `model: haiku`/`sonnet` for simple lookups). Experiments needing judgment → session model.

## 5. Search swarm (parallel Phase 1)

Unknown location in a large codebase: one Explore agent per area (package, layer, service), each returns ≤ 10 lines `path:line — why relevant`. Known exact string → one Grep call beats agents.
Multi-service failure: one agent per service/log source: "did the request arrive, what came in, what went out, first error + timestamp". Merge on timestamp / request id.

## 6. Recipes

**Flaky / intermittent**
```bash
bash $S/stress.sh -n 200 -t 120 -- npx vitest run src/queue.test.ts        # baseline
bash $S/stress.sh -n 200 -t 120 -b 14/200 -- npx vitest run src/queue.test.ts   # after fix, same -n/-j
```
- Prints failure rate + 95% Wilson interval, failing log paths, exit-code histogram. `-k` keeps passing logs for pass/fail diffs.
- Runs share the working tree, ports, DBs and caches (only `TMPDIR` differs). If failures appear only at `-j > 1`, rerun at `-j 1` or namespace resources with `STRESS_RUN` before treating the rate as evidence. Conversely, raising `-j` above CPUs adds load that exposes races — use the same `-j` for before/after.
- **Proving a fix:** `-b F/N` (baseline failures/runs) prints a one-sided Fisher exact p-value; require p < 0.05. Runs needed with zero failures ≈ 3 / p_low, where p_low is the baseline's Wilson *lower* bound (the script prints it) — not the observed rate.
- For a flaky test cap each run: `-t`; `-x` stops at the first failure when you only need one failing log.

**Regression, unknown culprit**
```bash
cp tests/repro.sh /tmp/repro.sh   # keep the repro OUTSIDE the repo: old commits don't have it
bash $S/bisect-parallel.sh -j 15 --link node_modules v1.4.0 HEAD -- sh /tmp/repro.sh
```
- Exit codes like `git bisect run`: 0 good, 125 skip, other 1–127 bad (≥ 128 → skip). Make the repro exit 125 when a prerequisite is missing (doesn't build, file absent).
- Rounds = ⌈log₍ⱼ₊₁₎ N⌉: 1,000 commits → 10 rounds with `git bisect`, 3 with `-j 15`, 2 with `-j 63`. First-parent history (merges are units). Verifies good/bad first unless `--no-verify`. Your working tree is never touched. `-j 1` is slower than plain `git bisect`.
- Dependency files changed in the range (see `snapshot.sh`) → don't `--link`; install per commit: `-- sh -c 'npm ci --prefer-offline >/dev/null && sh /tmp/repro.sh'`.
- Flaky regression → each probe is a stress run: `-- bash $S/stress.sh -n <K> -j <m> -t <per-run s> -- sh /tmp/repro.sh`.
  - Runs per commit: K ≥ ln(0.05) / ln(1 − p) ≈ 3/p so a bad commit passes all K runs ≤ 5% of the time (p = 10% → K = 30; p = 2% → K = 150). Measure p on HEAD first.
  - Budget: bisect `-j` × stress `-j` ≤ CPUs (e.g. 16 cores: `-j 7` × `-j 2`, or `-j 15` × `-j 1`). Put the per-run timeout on stress (`-t`), not on bisect (its `-t` covers the whole probe).
  - Endpoints: keep verification on (it uses the same stress probe). Afterwards confirm culprit C with a bigger run: `stress.sh -n 100` at `C^` then at `C`, and `-b` to test the difference. The script warns on non-monotonic results (a good commit after a bad one) — treat that as a too-small K.

**Test pollution (files/dirs appear after tests)**
```bash
cd packages/core && bash $S/find-polluter.sh -j 16 --link packages/core/node_modules .git 'src/**/*.test.ts'
bash $S/find-polluter.sh -j 16 --cmd 'pytest -q' tmp/output.db 'tests/**/test_*.py'
```
- Run from the directory where you'd normally run the test; paths are relative to it. The repo-root `.git` itself cannot be a target.
- Worktrees get tracked files, uncommitted edits and untracked non-ignored files — not ignored ones (`.env`, generated code): `--link .env`. The script reports how many test runs exited non-zero; if all did, fix `--cmd`/`--link` before trusting "no polluter".
- Detects paths only, not DB rows or globals. Absolute pollution paths are shared → forced to `-j 1`.

**Order-dependent failures** (passes alone, fails in the suite): run serially with a shuffled, printed seed — `jest -i --randomize`, `vitest --sequence.shuffle --no-file-parallelism`, pytest-randomly without `-n`, `go test -p 1 -shuffle=on` — reproduce with the seed, then bisect the preceding tests: run several candidate subsets (each: subset + victim, serial) in parallel worktrees until one predecessor remains.

**Suites on one machine**: use the runner's native workers once (`--maxWorkers`, `pytest -n auto`, `go test -p N`, `cargo nextest run -j N`). `--shard=i/N` (jest, vitest, playwright) pays off only across separate machines/CI jobs.

**Performance**: measure before theorizing — profile once (`node --cpu-prof`, `py-spy record`, `go tool pprof`, `perf record`), then benchmark competing hypotheses under identical load, one after another; compare medians of ≥ 5 runs, never single runs.
