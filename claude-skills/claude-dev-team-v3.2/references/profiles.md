# Profiles, setup details and speed

Reference for the profile dial, one-time setup and why the engine is fast. Read it when choosing a
profile or when a run is slower than expected.

## Profiles (`--profile`, default `balanced`)

| Profile | Per-slice gate | RED verification run | Review | Checkpoints |
|---|---|---|---|---|
| `strict` | full lint+typecheck+build | every slice | incremental | every N merges |
| **`balanced`** (default) | slice tests + **file-scoped** lint/typecheck | high-risk slices only | incremental | every N merges |
| `turbo` | deferred to one final full gate | none | one final sharded, spot depth | one final |
| `spike` | turbo, **and low-risk slices ship with no tests** | none | final, spot depth | one final |

`balanced` is the default because the two things it cuts cost almost nothing in assurance: a
*file-scoped* linter is the same check on the only files that changed, and the skipped RED run is
replaced by a **static vacuous-test check**: `commit-red` refuses a test file with no assertions
or with fewer test cases than the slice has criteria. Incremental reviews stay on: they overlap
the build, so they are free in wall-clock.

Choose `turbo` or `spike` **only when the user asks**, never infer them, never leave one on for
the next request. `spike` breaks the test-first rule on purpose: say in one line what is being
traded before you dispatch, and list every untested slice in the final report with an offer to
harden it. In `turbo`/`spike`: **never block on a question**; take the recommended default,
record it under `## Assumptions` in `plan.md`, and put every decision you made in the final report
so the user can overturn one.

## Setup details

`devteam start <plan.md>` runs `doctor --fix`, `init` and the first `dispatch` in one call. `doctor
--fix` alone writes `.claude/settings.local.json` (subagent concurrency 64, tool-use concurrency 64,
subagent stall timeout and Bash timeouts raised so a long gate is not killed mid-slice,
`subagentPromptCacheTtl: 1h`, `worktree.baseRef: head`, an allow rule for the engine), writes
`.worktreeinclude` so env files reach every worktree, installs the five agents into
`.claude/agents/` with hooks pinned to `guard.py`, and adds git excludes. **Env limits and newly
installed agents apply at startup**: if `--fix` changed them, tell the user to restart Claude Code
once; until then the engine caps dispatches at the live limit (default 20). `init` adds allow rules
for every plan command. Not a git repo yet → `start` initialises one. Requires Claude Code ≥
2.1.267 (agent `effort:` honoured), git ≥ 2.31, python3.

## Why this is fast (keep these properties intact)

1. **No wave barriers.** Workers run in the background; each completion wakes you and its
   dependents dispatch immediately. Never wait for siblings, never poll, never `sleep`.
2. **One argument-less engine call per turn.** Programmers report through a Stop-gate marker,
   reviewers through their report file, checkpoints through their log: `next` harvests all of it.
3. **Tiny prompts.** A dispatch is one line; the briefing is a file the engine wrote. Your output
   tokens per launch stay near zero: they are on the critical path when you launch 64.
4. **Native isolation.** `isolation: worktree` in the programmer's frontmatter: Claude Code creates
   the worktree, runs every command inside it, and blocks writes to the main checkout. `claim`
   resets the base and links `node_modules`-type dirs.
5. **Critical-path scheduling.** The ready set is ordered by the *heaviest* remaining dependency
   chain (slice `size` is its weight), so the longest path starts first.
6. **Cheap work on a cheap model.** Every lane rides sonnet; only the final review and the
   team-leader's PLANNING and VERIFICATION use opus. The mechanical gates and the reviewer catch
   what a smaller model gets wrong.
7. **Mechanical gates.** RED-before-GREEN, vacuous-test check, frozen tests, refactor invariants,
   footprints, clean tree: checked by hooks while the agent is still alive (warm fix) and again
   at merge.
8. **Review overlaps build.** Incremental reviewers run per batch of merged slices; the final
   review covers only the last delta and is sharded (~10 files each, up to 12).
9. **Warm resumes.** `SendMessage` to a finished agent id resumes it with full context and
   worktree: use it for BLOCKING answers, gate rejections, turn-limit partials, re-reviews. (A
   resume takes a slot without checking the cap: the engine reserves for it.)
10. **Caching.** Identical agent files + one-line prompts → shared prefixes; every agent and the
    settings ask for a 1-hour prompt cache, which is what makes warm resumes cheap later.
11. **Never a prompt.** `dontAsk` + hook pre-approval: no lane ever stalls on a permission dialog,
    and pre-approved commands normally bypass the auto-mode classifier as well.

## Speed ceiling

Remaining dials, in order: **`/fast`** for the Conductor and opus roles (user's credits); **profile
`turbo` / `spike`** (ask the user, don't assume); raise `review_batch` / `checkpoint_every` in the
plan for very large runs; `effort: low` on the programmer for boilerplate-heavy work; more
`Explore` or `research` agents for planning. Past `spike` nothing is left but the two remaining
rules: independent review and one writer per path. If asked to cut those, say plainly what breaks,
and don't.
