# Slice kinds and task types

Reference for planning. Read it when you map a request onto slices.

## Slice kinds: how one pipeline covers every task

| `kind` | Pipeline the engine runs | Use it for |
|---|---|---|
| `code` *(default)* | RED tests committed → GREEN implementation | features, bug fixes, new behaviour |
| `test` | tests only, one commit, must really add tests | coverage backfill, characterization tests |
| `refactor` | one commit; **may not touch any test file** (hooks + merge both reject it); before/after test runs pasted | renames, extractions, restructuring, codemods |
| `chore` | one commit; the slice's `verify` command output is the proof | build, CI, deps, config, tooling, release plumbing, scaffolding |
| `docs` | one commit; `verify` proof | READMEs, ADRs, API docs, runbooks |
| `perf` | one commit; before **and** after numbers required | optimization |
| `research` | read-only; the deliverable is a report file, nothing is merged; follow-up slices in its report are queued automatically | feasibility, upgrade assessment, architecture or security survey |

## Task types: how they map

| Task | Shape |
|---|---|
| Greenfield project / new service | `start` runs `git init` if needed; S1 = `chore` scaffold slice (`verify` = the build/test command), then normal `code` slices fan out. |
| Framework/library migration, version upgrade | one `research` slice (assessment) ready now ∥ a wide fan of `refactor`/`chore` slices over disjoint files; the research report queues the follow-ups. |
| Codemod / mass rename | `refactor` slices partitioned by directory, disjoint footprints. |
| Security audit, architecture review | `research` slices per area; each report's `fixes` block becomes test-first `code` slices automatically. |
| Database migration / schema change | `chore` slice (migration file + `verify` = migrate up/down on the isolated DB_SUFFIX) → dependent `code` slices. |
| CI/CD, Dockerfile, infra-as-code, release plumbing | `chore` slices with a `verify` that really exercises it (`act`, `docker build`, `terraform validate`, dry-run). **Applying** to prod/staging is never done by a lane: confirm with the user, run it yourself. |
| Performance | `perf` slices with a pinned `commands.bench`; before/after numbers are the merge evidence. |
| Flaky/failing tests, tech-debt sweep | `brief-debug` for the cause; `test`/`refactor` slices for the sweep. |
| UI/frontend | `code` slices with component tests; a `verify` that builds; screenshots only if the user asks (built-in browser / Chrome tools, by you, not a lane). |
| Docs at scale | `docs` slices per document, `verify` = link/build check. |
| Dependency add/remove | one `chore` slice owning the manifest **and** lockfile; lanes never run installers: after it merges, you run the install once in the integration checkout before dispatching dependents. |
| Open a PR / ship | `finish` writes `.claude/dev-team/summary.md`; `gh pr create --body-file` it (push/PR only when the user asked). |

## Slicing rules

**Vertical** (S1 = thinnest end-to-end path, each slice one increment); `deps` only for true runtime
prerequisites (anything pinned as a contract is not a dependency); `files` = exact source **and
test** paths, pairwise **disjoint** (a shared path serializes two slices); `kind` per the table
above; `size` honestly (it is the scheduler's weight *and* the model router); `risk: high` sparingly
(security, concurrency, subtle logic: it costs a split RED/GREEN dispatch + verification);
`isolation: true` when tests touch a port/DB/filesystem outside the footprint (the engine pins
values); leanest viable slices, reuse what exists. **Width is the product you are designing.**
The plan's JSON block is printed by `devteam plan-template`.
