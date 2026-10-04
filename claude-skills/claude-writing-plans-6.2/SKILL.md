---
name: claude-writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code. Produces a portable TDD checkbox implementation plan at maximum speed - contracts locked once, task bodies fanned out to up to 64 parallel writers from script-built briefs, verified by a deterministic linter.
argument-hint: "[spec-path] [--thorough]"
allowed-tools: Bash(python3 *)
compatibility: Claude Code v2.1.217+ recommended (subagent cap setting); python3 3.8+
---

# Writing Plans (v8 - max-parallel)

> Version labels: `claude-writing-plans-6.2` is the install folder name; `v8` is the skill's internal version (see `CHANGELOG.md`). Both name the same release.

Write implementation plans for an engineer with zero context and questionable taste: exact files, real code, exact commands with expected output, commits. DRY. YAGNI. TDD.

**Announce:** "I'm using the claude-writing-plans skill to create the implementation plan."

## Context (computed when the skill loaded)

```!
python3 "${CLAUDE_SKILL_DIR}/scripts/plan_tool.py" context "$ARGUMENTS"
```

If the block above shows a raw command instead of output, run `python3 <this skill dir>/scripts/plan_tool.py context <spec>` in the same message as your Phase 0 reads. `TOOL` below = the `tool:` line of the context (use it verbatim).

## Speed Doctrine

1. **Serial only where divergence is born** (the Contracts). Everything else runs in parallel, one message per wave.
2. **Never type what the script generates:** Execution Protocol, File Structure, Execution Waves, `[P]`, Depends/Runs-after lines, Interfaces blocks, writer briefs. Output tokens are the bottleneck.
3. **Machines check, models judge.** Structure, placeholders, portability, file ownership, signatures, Run/Expected, `git add` scope and code-block syntax are one script call - never a model re-read.
4. **Respect the cap.** Running subagents above `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (default 20) fail with "Concurrent subagent limit reached". The script sizes the fan-out to the cap from the context line; never dispatch more.
5. **Keep the cache warm.** Don't change model or effort mid-skill (each change re-reads the whole conversation uncached). Writers get facts from briefs, not from exploring.
6. **Fix-and-move-on.** After a fix, re-run only the script - no re-review.

## Portability Rule (the plan is the product)

The process uses subagents; the plan file must not mention them. It is plain Markdown any AI agent or human with a shell, an editor and git can execute. The linter enforces this.

## Scope Check

Independent subsystems -> one plan each; plans may be produced concurrently with the writer budget split between them.

## Pipeline

## Phase 0 - Load (ONE message)

Read the spec fully and 2-5 pattern files picked from the context (a test, a similar module, build config) - all in one message of parallel Reads. Only when the repo is large and you cannot locate the affected code from the context: add up to 3 narrow `Explore` agents in that same message. Estimate the task count N.

**N = 1 -> Inline path. N >= 2 -> Fan-out (Phases 1-4).** Writers run in parallel from N = 2, so a two-task plan is never written serially.

## Phase 1 - Contracts (serial, ONE Write)

Write `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` containing only:

````markdown
# [Feature] Implementation Plan

**Goal:** [one sentence]

**Architecture:** [2-3 sentences]

**Tech Stack:** [key technologies]

## Global Constraints

- [project-wide rule with exact values from the spec / CLAUDE.md - one per line]

## References

- `path/to/pattern_file.py` - [why every writer should see it]   (optional section; inlined into every brief)

## Contracts

#### T01: Config loader
- Files: `src/config.py`, `tests/test_config.py`
- Produces: `def load_config(path: Path) -> Config`; `class Config`
- Consumes: `class Path` (existing)
- Spec: L12-40

#### T02: HTTP app
- Depends: T01
- Files: `src/api.py`, `tests/test_api.py`
- Produces: `def create_app(config: Config) -> App`
- Read: `src/legacy_app.py`
- Spec: L41-77, L120-131
- Tier: deep
````

Contract rules (quality is locked here):
- IDs sequential `T01..` (`T001` if > 99). A producer's ID is lower than its consumers'.
- `Files` (required): every path the task creates/modifies/tests. Tasks sharing a file are auto-serialized (Runs after), so give each task its own files; wire shared registries in one final task.
- `Produces`: exact backticked declarations (name, params, types, return) as they will appear in code. `Consumes`: copy the producer's text byte-for-byte; `(existing)` for codebase symbols. Omit `Consumes` to mean "all Produces of my Depends". Depends are auto-added from Consumes.
- `Spec`: line ranges from the context heading map; writers get exactly these lines.
- `Read` (optional): extra existing files this writer needs. `Tier` (optional): `light` (trivial config/docs) or `deep` (algorithmic, security, concurrency). Every writer runs on sonnet whatever the tier; the tier only decides which tasks `review` picks (`deep` is always reviewed). Default: standard.
- Right-size: smallest unit with its own test cycle a reviewer could reject independently.
- Legitimate project vocabulary that the placeholder/portability scan would flag (e.g. a TODO app, a class named `Task`) needs `--allow WORD` on every `contracts`/`assemble`/`check` call - decide this now, not after `assemble` fails.

Run `TOOL contracts <plan> --spec <spec>` (add `--agents 64` only if you know the real cap is higher than what the script detected). Fix every `ERR` with Edit and re-run until `OK`. Treat `WARN spec uncovered` as a missing task unless the section is non-functional. `OK` prints `WORK`, the `DISPATCH` table and the next command.

## Phase 2 - Fan-out writers (ONE message)

For every DISPATCH row, one Agent call - all in a single message:
- `subagent_type`: as printed (`claude-plan-task-writer` when installed; if the call says the type is unknown, use `general-purpose`)
- `model`: the row's MODEL
- `description`: `plan <ID>`
- `prompt`: `Read <BRIEF> and follow it exactly.` - nothing else; the brief carries contract, spec lines, inlined files, rules and lint command.

A call refused with "Concurrent subagent limit reached" means other subagents hold slots: don't retry it in a loop - dispatch those rows again after the next completion notification.

Then, in your next message, run the printed `TOOL wait <plan>` with Bash `timeout: 600000`. It blocks until every task file lints OK. Don't act on individual completion notifications while waiting.
- `DONE` -> Phase 3.
- `PENDING` -> if those agents are still running, run `wait` again. If they returned `FAIL` or stopped: re-dispatch only those IDs in one message (same prompt), or fix a small issue yourself with Edit + `TOOL lint-task <plan> <task file>`.

## Phase 3 - Risk-based review (ONE message)

Run `TOOL review <plan>` (`--all` when invoked with `--thorough` or the user asks for maximum assurance). `NONE` -> skip to Phase 4. Otherwise dispatch its rows exactly like Phase 2 (agent type as printed: `claude-plan-task-writer` when installed, otherwise `general-purpose`; model `sonnet`), then run the printed `wait --review`. Each reviewer brief inlines the task bodies and the existing target files, so a reviewer reads nothing else. Reviewers fix their own task files in place. An "Unfixable (needs contract change)" line -> edit that contract, re-run `contracts`, re-dispatch only the affected writers, `wait`.

## Phase 4 - Assemble (ONE command)

`TOOL assemble <plan> --clean` - re-lints everything, then renders the canonical plan: execution note, Execution Protocol, File Structure (if you wrote none), Execution Waves, and each task's heading/`[P]`/Depends/Runs-after/Interfaces, then deletes the scratch dir. On `ERR` nothing is written: fix the named task file, re-run. Legitimate project vocabulary (e.g. a TODO app): add `--allow TODO`.

## Inline Path (N = 1)

Read `task-writer-prompt.md` in this skill dir for the body format. Write the skeleton + Contracts, then `<!-- TASKS -->`, then each task as `### T01: Name` followed by its body - all in ONE Write. Run `TOOL check <plan> --spec <spec>`; fix `ERR`s; done (it renders the same canonical plan).

## Execution Handoff

After `OK`, offer (waves/width from the script output):

**"Plan saved to `docs/superpowers/plans/<file>.md` - N tasks, W waves, up to K tasks in parallel. It is self-contained: any agent or engineer can execute it via its Execution Protocol. Options:**

**1. Subagent-Driven here (recommended)** - fresh subagent per task, review between tasks; each wave's `[P]` tasks dispatched together in one message (within the subagent cap).

**2. Inline Execution here** - sequential, with checkpoints.

**3. Hand off** - the `claude-dev-team-v3.2` skill (or `claude-dev-team` when only the bare name is installed) adopts this plan as authoritative and implements it end to end; or give the file to any coding agent or human with: *"Execute this plan following its Execution Protocol."*

**Which approach?"**

- Subagent-Driven -> dispatch each wave's `[P]` tasks yourself as subagents here, reviewing between waves.
- Inline -> execute the plan yourself here, sequentially, with checkpoints.
- Hand off -> nothing else; the plan carries everything (claude-dev-team or any other agent/human).

## One-time speed setup (tell the user when the context shows cap < 64, or flags a stale/placeholder writer agent)

`TOOL setup` (dry run) then `TOOL setup --apply`, then restart Claude Code. It sets `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=64`, pre-approves `TOOL` and edits under `docs/superpowers/plans/`, and installs the `claude-plan-task-writer` agent (sonnet, effort medium, no CLAUDE.md load, PostToolUse auto-lint hook that saves each writer a turn). Never run `--apply` without the user's consent. Optional: `/fast` speeds the serial contract phase on Opus.
