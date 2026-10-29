# claude-writing-plans v8 (max-parallel) — changes from v7

Version label note: `claude-writing-plans-6.2` is the installation directory name; `v8` is the internal skill version number (same release).

## Critical concurrency fix
- Claude Code defaults to only **20 concurrent subagents** (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`). v7 dispatched 64 writers in a single message -> writers from the 21st onward were rejected with "Concurrent subagent limit reached". v8 reads the real limit, packs tasks into <= cap writers (balanced by workload), and `setup --apply` raises it to 64.

## Faster orchestrator (sequential bottleneck)
- Repo context + spec heading map are **injected when loading the skill** (`!` command) -> skips one tool round trip.
- Orchestrator no longer types Execution Protocol, File Structure, Waves, `Parallel:`, Depends inferred from Consumes, Interfaces — scripts generate all of them.
- Each writer's prompt is reduced to 1 line (`Read <brief> and follow it exactly.`).

## Faster writers
- Script generates **dedicated briefs for each writer**: contract, pre-sliced spec lines, existing files inlined with line numbers, full lint rules -> writer only reads 1 file.
- Hard rule forbids writer from reading scripts or exploring the repo (empirical measurement: this was the primary cause of slow writers).
- Optional `claude-plan-task-writer` agent: sonnet, medium effort, does not load CLAUDE.md, PostToolUse hook automatically lints after Write/Edit -> saves 1 turn/writer.
- `Tier: light|deep` only affects task selection for review (deep is always reviewed); all writers run on sonnet.
- `wait` blocks until all tasks lint OK (no need to handle 64 notifications).

## Stronger machine verification (replacing model reviews)
- Syntax checking for code blocks: Python, JSON, TOML, bash, JS (`fragment` to skip intentionally incomplete snippets).
- Files in task ⊆ Files of the contract; `git add` only touches explicit paths belonging to the task; each `Run:` has an `Expected:`; steps are continuously numbered; Create/Modify matches disk state.
- Tasks sharing files are automatically ordered (`Runs after`), warning on "hot files" that cause serialization.
- Risk-based review (deep / long / many dependencies / has WARN), `--thorough` to review all; each reviewer gets 1 dedicated slot.

## Benchmark A/B (same repo, same 4 contracts, n=1 — high LLM variance)
| | v7 | v8 |
|---|---|---|
| Wall-clock fan-out (slowest task) | 275 s | 163 s |
| Total writer time | 543 s | 314 s |
| Tool calls | 33 | 12 (3/writer) |
Script: `contracts` 70 tasks < 0.25 s, `assemble` 70 tasks 0.3 s.

## Installation
1. Extract into `~/.claude/skills/claude-writing-plans-6.2/` (skills synced from claude.ai will not execute `!` commands).
2. One-time setup: `python3 ~/.claude/skills/claude-writing-plans-6.2/scripts/plan_tool.py setup` (dry-run) -> `--apply` -> restart Claude Code.

## W8 — preload never cancels skill, bounded context, contract hashing, warn/fail marks, legacy agent detection, faster assemble/wait
- Preload `!` now passes `"$ARGUMENTS"` as ONE quoted token; `context` always exits code 0 even with empty arguments, embedded quotes, non-existent paths, detached HEAD, repo with no commits, or outside a git repo — eliminating the risk of aborting the entire skill due to shell-split errors.
- `context` uses `git --no-optional-locks` for all git commands (avoids touching index mtime) and caps the visible file list at <=30 (total output <=~55 lines) even on 300+ file repos.
- `contracts` now hashes (sha256) each contract's content; if a contract changes, the script removes only `TXX.md` + `TXX.md.ok` (and other marks) for that task, keeping other tasks untouched.
- `lint-task` and `hook-lint` share the same marking function: lint with warnings writes `.warn`, clean lint clears old `.warn`, lint errors write `.fail` (and `.fail` is cleared on clean re-lint).
- `context` detects pre-installed `claude-plan-task-writer` agent still containing the `__PLAN_TOOL__` placeholder (where `setup --apply` has not been run) and always warns, even when the subagent cap is already at maximum.
- `wait` returns `PENDING` early when all remaining tasks are `.fail` and unchanged for >=45 seconds, instead of waiting for the full `--idle`/`--timeout`.
- `assemble` runs `node --check` for code blocks in parallel across tasks rather than sequentially.
- Reviewer brief now pre-inlines existing target file contents (matching writer brief), so reviewers need no extra reads.
- SKILL.md: dropped "ultracode" mention, added `--allow` recommendation early in Phase 1, repointed hand-off to `claude-dev-team` instead of obsolete hand-off skills, and clarified in "One-time speed setup" that it also handles legacy agents/placeholders.
