# glm-skills execution-speed optimization — design spec

Date: 2026-10-10. Status: approved design (Approach A, full 7 work items, idea-to-spec
interview collapse approved). Scope: `glm-skills/` only. Nothing in `../claude-skills/` is
touched: GLM parallelism is documented as harness-specific (glm-skills/CLAUDE.md, "Architecture:
the shared GLM design"), so it stays in the port. Work happens on `main` per repo rule.

Goal: fastest wall-clock per skill run with every existing quality gate intact.

## Evidence (repo facts, lane-verified 2026-10-10)

Already parallel — leave untouched:
- audit.py:1403-1480 `Fan` ThreadPoolExecutor (max 8, warm-up prefix request); wave A judge
  parallel (2193-2198), wave B verify parallel (2225-2230).
- plan_tool.py:306-310 `pmap` (max 8); writer fan-out 1163, review fan-out 1246.
- debug_tool.py: probe pool 291-326; scan 8 API workers 867-914; bisect-parallel.sh:52-72
  batched rounds; stress.sh and find-polluter.sh already xargs -P.
- gather.sh: backgrounded fetch, speculative gen, 300 s freshness stamp.
- SKILL.md files already mandate one-message batching and push width into engine calls.

Serial bottlenecks (the work):
1. audit.py:2145-2244 — hard barrier: all judging finishes before any verify starts, though
   `verify_one` needs only its own item's finding. Wave B is usually smaller than wave A, so
   the gain is bounded by the judge tail.
2. plan_tool.py:1617-1712 — `cmd_brief` recon fully serial read-only; 1589-1595
   `pick_patterns` reads candidates one by one.
3. plan_tool.py:1080-1124 — review starts only after ALL writers succeed, though
   `review_one` needs one finished body (`.ok` marks exist). Global `Budget` gate at 1103.
4. glm-idea-to-spec/SKILL.md:24-114 — rigid Phase 0-5; 2-4 serial interview rounds even when
   the brief already answers them; research parallel only with a Task tool. Fast mode (133)
   is the only short-circuit today.
5. context.sh:50-67 — serial git chain; hot-dir git log (58) and second ls-files (65)
   dominate on large repos; manifest find-walk (76) is a second full walk.
6. gather.sh:42-44 — serial base-branch probing loop; 190 — re-chunk loop re-runs awk per
   iteration.
7. devteam.py:2000-2088 — read-only pre-checks (dirty status, log scans, footprint diffs)
   run serially before each serial `merge_slice`. Merges mutate shared HEAD and stay serial.

Out of scope by design: debug_tool.py:335-337 flake reruns and 664-668 same-worktree repeats
are serial on purpose (semantically load-bearing); bisect round order is inherent.

## Work items

Each item is independently implementable and testable; no item changes any CLI shape,
on-disk format, or public behavior contract.

### 1. audit.py — pipeline verify behind judge (remove the A→B barrier)
Replace the two-wave submission with one completion-aware stream: submit all judge jobs to
`Fan`; when a judge result lands and the item `needs_verify`, submit its verify job into the
same pool immediately.
- Total in-flight jobs still capped at MAX_PARALLEL=8 (verify fills judge-tail slots; no new
  rate-limit exposure).
- Keep both prefix warm-ups: judge prefix before the first judge job, verify prefix before
  the first verify submission.
- Preserve RA20 resume semantics: per-item keys, `verify_targets` keeps settled verdicts, an
  interrupted run resumes without redoing settled items.
- `findings.jsonl` / `verdicts.jsonl` contents unchanged; write timing may shift to
  drain-time. Final report content and ordering identical to today (report assembly sorts by
  requirement order; interleaving must not leak into it).

### 2. plan_tool.py — parallelize `cmd_brief` recon
Route the independent read-only steps (git log / ls-files / status, conventions reads,
inline pattern-file reads, spec read, `pick_patterns` candidate reads) through `pmap`;
merge results in the current deterministic order.
- `brief` output must stay byte-identical on the existing test fixtures.

### 3. plan_tool.py — overlap review with writes in `cmd_build`
Submit `review_one` as each writer finishes successfully (existing risky-task pick logic
unchanged). A failed write skips its review and keeps today's failure path.
- Global `Budget` trip stops new review submissions as well as new writes.
- Exit-code semantics unchanged (any failed write still aborts with the same report).

### 4. glm-idea-to-spec/SKILL.md — collapse interview when the brief is detailed
- When the initial brief already answers Phase 0-2 questions (target users, goal, success
  criteria), collapse remaining questions into ONE batched Ask round.
- Batch research query variants in one message (WebSearch/WebFetch) when no Task tool exists.
- Phase order verdict-before-spec unchanged. Fast mode unchanged.
- No scripts, no agents, no frontmatter `name` change; description stays under 1024 chars.

### 5. context.sh — dedupe and run the heavy git calls concurrently
Capture `git ls-files` output once and reuse it for the file count, the `files:` line and the
`tree:` aggregation (today it runs twice). Background the hot-dir git log into a temp file
while the main git block executes; join and emit in the current output order.
- Stays read-only, bounded output, and ALWAYS exit 0 (guard every backgrounded git with
  `|| true`; `wait` must not propagate a non-zero status into the script's exit).

### 6. gather.sh — micro
- Replace the serial base-branch probing loop with one batched refs query
  (`git for-each-ref` / `rev-parse --verify` over candidates).
- Compute re-chunk boundaries once per pass instead of re-running awk per iteration.
- Output byte-identical on this repo before/after.

### 7. devteam.py — overlap read-only pre-checks ahead of the serial merge loop
In the integration path, run the read-only per-slice pre-checks (dirty status, log scans,
footprint diffs) through a small thread pool before the serial `merge_slice` loop.
- All mutations stay inside `state_lock` / `save_state`; merge order, conflict reporting and
  the `next` wake-up chain are unchanged.

## Guardrails (must not change)

- Flake-check serialization and same-worktree repeat serialization (debug semantics).
- Governor AIMD / 429 halving; MAX_PARALLEL=8; `workers_cap()`.
- Prefix caching: byte-identical shared blocks; both warm-ups retained (item 1).
- Audit citation checker, deterministic retrieval, writes only under `.audit/`.
- Budget abort gate semantics (item 3 keeps the gate, widens what it stops).
- stdlib-only, no new dependencies; shell scripts stay read-only and exit 0.
- Every devteam state mutation through `save_state`/`state_lock`.

## Testing

- Per item, extend `_shared/tests`: pipeline order + resume under interruption (audit, with
  `fake_provider.py` under artificial delay), brief byte-stability (plan), budget-trip during
  overlap (plan), pre-check overlap under `state_lock` (devteam port tests).
- Full suite: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t
  _shared/tests`.
- `bash glm-dev-team/scripts/selftest.sh`; pass criterion: the same set as the recorded
  baseline (323 pass, 6 pre-existing Claude-lane failures).
- Wall-clock before/after for items 1-3 using `fake_provider.py` with injected delay;
  `time sh scripts/context.sh` and `time sh gather.sh` for items 5-6 on this repo.
- Hygiene: `test_all_skills.py` (vendored-copy identity, py_compile, SKILL.md rules).

## Bookkeeping

- Version bumps + CHANGELOG entries where the skill keeps one (audit v9, writing-plans v9,
  dev-team v4.0; brainstorming untouched except context.sh if its CHANGELOG covers scripts —
  record there). idea-to-spec and git-diff-summary keep no changelog.
- dev-team README.md (Vietnamese) only if a user-visible step changes (none expected).

## Rejected alternatives

- Guidance-only (SKILL.md edits): leaves the three engine barriers; marginal gains.
- asyncio/rewrite of engines: large diff, breaks the scheduler-is-a-pure-function-of-state
  design and stdlib-deterministic patterns; the serial local work does not justify it.

## Assumptions

- glm-skills/ only; no backports to ../claude-skills/ in this pass.
- Branch: main, direct commits, per repo rule.
- The 6 selftest failures are pre-existing and stay out of scope.
