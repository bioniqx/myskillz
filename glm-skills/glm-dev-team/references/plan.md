# Plan, kinds, and profiles

Read this only when writing or adopting a plan. Do not read it on a wake-up.

## Slice kinds

| `kind` | What the engine runs | Use it for |
| --- | --- | --- |
| `code` *(default)* | one lane: RED tests committed, then GREEN | features, bug fixes, including `risk: high` |
| `test` | tests only; must really add tests | coverage backfill, characterization |
| `refactor` | one commit; may not touch any test file; before/after runs pasted | renames, extractions, codemods |
| `chore` | one commit; the slice's `verify` output is the proof | build, CI, deps, config, scaffolding |
| `docs` | one commit; `verify` proof; lite lane unless `size: large` | READMEs, ADRs, runbooks |
| `perf` | one commit; before and after numbers | optimization |
| `research` | read-only report; nothing merged; its `fixes` block queues follow-ups | feasibility, upgrade, security, architecture |

Task shapes: **greenfield** → `start` runs `git init`; S1 = `chore` scaffold (`verify` = build/test), then `code` slices. **Migration/upgrade** → one `research` assessment beside `refactor`/`chore` slices over disjoint files. **Codemod** → `refactor` slices per directory. **Audit** → `research` per area (fixes become `code` slices). **DB migration** → `chore` (migrate up/down on the pinned `DB_SUFFIX`) → dependent `code`. **CI/infra** → `chore` with a `verify` that exercises it (`docker build`, `terraform validate`, dry-run). Applying to prod or staging is never a lane's job. **Perf** → `perf` with `commands.bench`. **Flaky tests** → `brief-debug`, then `test`/`refactor`. **UI** → `code` with component tests. **Dependency add/remove** → one `chore` owning manifest + lockfile; lanes never install. **Ship** → `finish` writes `summary.md` for `gh pr create --body-file` (push or PR only when asked).

## Profiles (`--profile`, default `balanced`)

| Profile | Per-slice gate | RED verification run | Review | Checkpoints |
| --- | --- | --- | --- | --- |
| `strict` | full lint+typecheck+build | every slice | incremental, after programmers | every N merges |
| **`balanced`** | slice tests + file-scoped lint/typecheck | high-risk only | incremental, after programmers | every N merges |
| `turbo` | one final full gate | none | one final, sharded, spot | one final |
| `spike` | turbo, low-risk slices ship with no tests | none | final, spot | one final |

A skipped RED run is replaced by a static check: `commit-red` refuses tests with no assertions or fewer cases than criteria. Choose `turbo` or `spike` only when the user asks ("fast mode", "nhanh nhất", "prototype", "throwaway", "no tests"). In `spike`, say in one line what is traded and list every untested slice at the end. In `turbo`/`spike` never block on a question: take the recommended default and record it under `## Assumptions`.

High-risk slices write tests inside the same lane as every other `code` slice. The engine still re-runs the RED commit and rejects tests that already pass.

## Plan file (`.claude/dev-team/plan.md`)

Prose for the user (Understanding with its out-of-scope line, open questions, assumptions, dispatch DAG) plus one json block the engine executes (`devteam plan-template`):

```json
{"request": "…",
 "profile": "balanced",
 "glm": {"tier": "api"},
 "commands": {"build": "…|none", "test": "…", "test_file": "… {files}", "lint": "…|none",
              "lint_file": "… {files}|none", "typecheck": "…|none", "typecheck_file": "…|none",
              "bench": "(perf only)"},
 "contracts": ["C1 <name>: <exact signature/schema> — established in S1, consumed by S2"],
 "notes": "conventions, gotchas, representative test file",
 "test_globs": [],
 "slices": [{"id": "S1", "title": "walking skeleton", "goal": "…", "kind": "code",
             "size": "small", "deps": [], "files": ["src/…", "tests/…"], "risk": "low",
             "isolation": false, "criteria": ["testable…"], "edge_cases": ["…"],
             "context": ["src/x.ts#Foo"], "verify": "(chore/docs/perf only)"}]}
```

Slicing rules:

- Vertical: S1 is the thinnest end-to-end path.
- `deps` only for true runtime prerequisites. A pinned contract is not a dependency.
- `files` are exact source and test paths, pairwise disjoint.
- `size` is the scheduler weight and the model router: `trivial` and `small` use the lite lane, `large` uses the strong lane. `risk: high` also uses the strong lane, still one dispatch.
- `risk: high` only for security, concurrency, or subtle logic. The engine runs RED proof on it.
- `isolation: true` when tests touch a port, database, or filesystem outside the footprint.
- Put paths the lane must read under `context`. The launch line carries them so the first turn can Read them with `claim`.
- Width is the product. The governor window only queues the width you designed. Cut lean slices. Do not merge slices only to fit the window.

## Gates the engine enforces

The conductor does not re-check these. On a printed rejection, send that text to the lane.

1. Proof run, before merge, on `strict` and `balanced`. The engine re-runs the slice tests, the `verify` command, or the refactor suite, plus the file-scoped lint and typecheck. `DEVTEAM_PROOF` overrides. `DEVTEAM_PROOF_TIMEOUT` defaults to 600 seconds. At most four proofs run at once.
2. RED proof. `strict`: every code slice. `balanced`: `risk: high` only. Tests that already pass on the RED commit are rejected.
3. Static checks at `commit-red` and `commit-green`: no skip, tautology, TODO, empty catch, or unresolvable import. A criterion number or quoted value must appear in the test.
4. Stop gate: `## Gate:` must show the command that ran, and `## Criteria:` must be present. `Complete` with a criterion "not met" is refused.
5. Review fails closed. APPROVED or PASS with no `## Evidence` is UNKNOWN.
6. Plan validation: a `code` slice whose footprint has no test path is an error. Absolute or `..` paths are errors.
7. After two rejections of the same dispatch the engine prints `retry <id>` (cold restart on `glm-programmer-strong`).
