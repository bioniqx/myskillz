# Parallel Debugging Playbook (up to 64 workers, zero extra model turns)

`$S` = the absolute scripts path printed as `S=` by every tool output; paste it literally, shell variables do not survive between tool calls.
Goal: cut wall-clock time with width, without letting parallel work corrupt the evidence.

## 1. Pick the cheapest layer

| Layer | Concurrency | Model turns it costs | Use for |
|---|---|---|---|
| `python3 $S/debug_tool.py probe` | ~10 internal jobs | 1 | the whole evidence phase |
| `python3 $S/debug_tool.py run -j N` | up to 64 | 1 | any N shell commands |
| `bash $S/*.sh -j N` | up to 64 | 1 | reruns, bisect, polluter search |
| `python3 $S/debug_tool.py experiment -j N` | up to 64 (2 worktrees per hypothesis) | 1 | hypotheses, control vs treatment |
| `python3 $S/debug_tool.py scan -j N` | up to 64 API workers | 1 | judgment: read an area, rank suspects |
| Subagents dispatched by the harness | harness-dependent, see below | 1 message, N agent turns | last resort |

**Subagents are the slow layer here, not the fast one.** Some harnesses dispatch them one at a time no matter how many you request, which turns a 64-way fan-out into 64 sequential runs. Others run foreground subagents truly in parallel. `scan` sidesteps the question: it opens its own threads. Use subagents only when `scan` reports no API key, and then dispatch every prompt in a single message.

Volume goes to the shell. Judgment goes to `scan`. Verdicts come only from `experiment`.

## 2. Width

- CPU-bound (tests, builds): total processes ≤ CPU count. A runner that already uses every core (jest, vitest, `pytest -n auto`, `go test`) counts as one job using all of them — do not multiply it.
- IO-bound (network, waiting on services): up to 64, each job with its own port / DB / temp dir; respect remote rate limits.
- API workers (`scan`): 64 is fine; they are pure network waits.
- Nested parallelism multiplies: bisect `-j` × stress `-j` ≤ CPUs.

## 3. Isolation — the quality guard

Parallel work that writes anything must not share mutable state.

- `experiment` gives **each arm its own worktree**, from your HEAD, with your uncommitted changes applied. That is deliberate: a control arm and a treatment arm sharing one tree leak build caches, `.pyc` files, generated code and databases into each other, and a stale artifact silently turns a real cause into "REFUTED".
- Hand-rolled worktree from current HEAD with uncommitted changes:
  ```bash
  wt=$(mktemp -d)/wt; git worktree add --detach "$wt" HEAD
  git diff HEAD --binary > "$wt.patch"; [ -s "$wt.patch" ] && git -C "$wt" apply "$wt.patch"
  # cleanup: git worktree remove --force "$wt"; git worktree prune
  ```
  Copy the untracked/ignored files the build needs (`.env`, generated code) — worktrees do not carry them. `--link node_modules` (repo-root-relative) symlinks deps in; tests that *write* into a linked dir break isolation.
- Per job: `TMPDIR`, port, DB/schema name, cache dir. The scripts export `STRESS_RUN` / `BISECT_JOB` / `POLLUTER_JOB`, `experiment` exports `SD_EXPERIMENT` / `SD_ARM` / `SD_RUN`. Combine when nested: `PORT=$((20000 + ${BISECT_JOB:-0} * 100 + ${STRESS_RUN:-0}))`.
- `git stash` is shared by every worktree of a repo — never stash from a parallel worker.
- Anything outside the repo (`~/.cache`, a shared DB, system services) is shared: serialize it or namespace it.

## 4. Hypothesis swarm — one call, `experiment`

1. From the `probe` evidence, write 2–4 hypotheses. Each needs a discriminating experiment: one variable, and a predicted outcome if true AND if false. A hypothesis without both predictions is not worth running.
2. `python3 $S/debug_tool.py experiment --template > /tmp/exp.json`, fill it in, `python3 $S/debug_tool.py experiment --spec /tmp/exp.json -j 16`.
   - `patch_file` — a diff applied only to the treatment arm.
   - `env` — variables set only for the treatment arm.
   - `treatment_cmd` — a different command for the treatment arm (shuffled seed, serial run, different runner flag).
   - `runs: N` — repeat both arms N times; use it for anything flaky.
   - `expect: treatment_passes | treatment_fails` — which way the outcome should move.
   - `setup`, `cwd`, `link`, `timeout` — per hypothesis.
3. **CONFIRMED** means the outcome flipped in the predicted direction. With `runs > 1`, a difference of one run is noise: prove a flaky fix with `stress.sh -b F/N` and require Fisher p < 0.05.
4. Several CONFIRMED → one upstream cause or an interaction: test the combination, or trace upstream. None → get new evidence, do not guess wider.
5. A candidate *fix* that fails counts toward the 3-fix limit even in a worktree. Apply exactly one fix to the main tree, then verify.

## 5. Search swarm — one call, `scan`

Unknown location in a large codebase: one worker per area.

```bash
python3 $S/debug_tool.py scan --area packages/api --area packages/worker --area packages/db \
  --question 'which code path can leave order.status pending after payment succeeds?' \
  --context-file /tmp/evidence.txt --tier std -j 64
```

Every worker gets the same system prompt and the same shared context, byte for byte, so the provider's prompt cache hits from the second worker onward. Each returns at most 12 lines in a fixed VERDICT shape. Multi-service failure: one worker per service or log source — "did the request arrive, what came in, what went out, first error + timestamp" — then merge on timestamp or request id.

With no API key, `scan` writes the prompts to files and prints the dispatch list; send them all in one message as subagents, and expect them to be slower.

Whatever `scan` returns is a lead. Confirm it with `experiment`.

## 6. Recipes

**Flaky / intermittent**
```bash
bash $S/stress.sh -n 200 -t 120 -- npx vitest run src/queue.test.ts            # baseline
bash $S/stress.sh -n 200 -t 120 -b 14/200 -- npx vitest run src/queue.test.ts  # after fix, same -n/-j
```
- Prints failure rate, 95% Wilson interval, failing log paths, exit-code histogram. `-k` keeps passing logs so you can diff pass against fail.
- Runs share the working tree, ports, DBs and caches (only `TMPDIR` differs). If failures only appear at `-j > 1`, rerun at `-j 1` or namespace resources with `STRESS_RUN` before treating the rate as evidence. Raising `-j` above the CPU count adds load and surfaces races — use the same `-j` on both sides of a comparison.
- **Proving a fix:** `-b F/N` prints a one-sided Fisher exact p; require p < 0.05. Clean runs needed ≈ 3 / p_low, where p_low is the baseline's Wilson *lower* bound (the script prints it) — not the observed rate.
- `-x` stops at the first failure when you only need one failing log.

**Regression, unknown culprit**
```bash
cp tests/repro.sh /tmp/repro.sh   # keep the repro OUTSIDE the repo: old commits do not have it
bash $S/bisect-parallel.sh -j 15 --link node_modules v1.4.0 HEAD -- sh /tmp/repro.sh
```
- Exit codes as `git bisect run`: 0 good, 125 skip, 1–127 bad, ≥128 skip. Make the repro exit 125 when a prerequisite is missing (does not build, file absent).
- Rounds = ⌈log₍ⱼ₊₁₎ N⌉: 1,000 commits → 10 rounds with plain `git bisect`, 3 with `-j 15`, 2 with `-j 63`. First-parent history; merges are units. Endpoints are verified first unless `--no-verify`. Your working tree is never touched.
- Dependency files changed inside the range (`probe` prints them) → do not `--link`; install per commit: `-- sh -c 'npm ci --prefer-offline >/dev/null && sh /tmp/repro.sh'`.
- Flaky regression → each probe is itself a stress run: `-- bash $S/stress.sh -n <K> -j <m> -t <s> -- sh /tmp/repro.sh`. K ≥ 3/p so a bad commit passes all K runs less than 5% of the time (p = 10% → K = 30; p = 2% → K = 150); measure p on HEAD first. Budget bisect `-j` × stress `-j` ≤ CPUs. Put the per-run timeout on stress, not on bisect. A "good" commit after a bad one means K was too small — the script warns.

**Test pollution (files or dirs appear after tests)**
```bash
cd packages/core && bash $S/find-polluter.sh -j 16 --link packages/core/node_modules .git 'src/**/*.test.ts'
bash $S/find-polluter.sh -j 16 --cmd 'pytest -q' tmp/output.db 'tests/**/test_*.py'
```
Run it from the directory you would normally run the tests in; paths are relative to it. Worktrees get tracked files, uncommitted edits and untracked non-ignored files — not ignored ones (`--link .env`). If the script reports that every run exited non-zero, fix `--cmd`/`--link` before trusting "no polluter". It detects paths only, not DB rows or globals.

**Order-dependent failures** (passes alone, fails in the suite): run serially with a shuffled, printed seed — `jest -i --randomize`, `vitest --sequence.shuffle --no-file-parallelism`, pytest-randomly without `-n`, `go test -p 1 -shuffle=on` — reproduce with the seed, then bisect the predecessors: several candidate subsets (each: subset + victim, serial) as `experiment` entries with `treatment_cmd`, in parallel worktrees, until one predecessor remains.

**Suites on one machine**: use the runner's native workers once (`--maxWorkers`, `pytest -n auto`, `go test -p N`, `cargo nextest run -j N`). `--shard=i/N` pays off only across separate machines.

**Performance**: measure before theorizing — profile once (`node --cpu-prof`, `py-spy record`, `go tool pprof`, `perf record`), then benchmark competing hypotheses under identical load, one after another, comparing medians of ≥ 5 runs. Never a single run.
