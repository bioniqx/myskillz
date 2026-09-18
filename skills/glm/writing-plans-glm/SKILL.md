---
name: writing-plans-glm
description: Use when you have a spec or requirements for a multi-step task, before touching code. Produces a portable TDD checkbox implementation plan in three tool calls - contracts locked once, task bodies fanned out to up to 64 concurrent writers by the script itself, verified by a deterministic linter.
argument-hint: "[spec-path] [--thorough]"
compatibility: python3 3.8+; OpenCode, ZCode, or any harness with a shell
---

# Writing Plans (v9 - GLM edition)

Write implementation plans for an engineer with zero context and questionable
taste: exact files, real code, exact commands with expected output, commits.
DRY. YAGNI. TDD.

Announce once: "I'm using the writing-plans skill to create the implementation plan."

# R0 - The whole pipeline is three tool calls

Call 1 `brief` -> Call 2 write the contracts -> Call 3 `build`. Nothing else.
Every extra turn costs a full reasoning pass, so treat any fourth call as a
defect to explain, not a habit.

# R1 - Call 1: resolve the tool and load everything

Run this as your FIRST tool call, with the spec path in place of `SPEC`:

```bash
T="$(ls -d ~/.zcode/skills/writing-plans/scripts/plan_tool.py \
  ~/.config/opencode/skills/writing-plans/scripts/plan_tool.py \
  ~/.claude/skills/writing-plans/scripts/plan_tool.py \
  ~/.agents/skills/writing-plans/scripts/plan_tool.py \
  .opencode/skills/writing-plans/scripts/plan_tool.py \
  .claude/skills/writing-plans/scripts/plan_tool.py 2>/dev/null | head -1)"
python3 "$T" brief SPEC
```

The output starts with a `TOOL:` line. Use that exact string for every later
call. The brief already contains the spec body with real line numbers, the spec
heading map, the repo file list, the stack, the test commands, the conventions
file and three or four auto-selected pattern files.

# R2 - Read nothing the brief already gave you

1. Do not re-read the spec. Do not open pattern files. Do not search the repo.
2. The single exception: the brief names a file as "not inlined" AND a contract
   cannot be written without it. Then read at most three such files, all in one
   message, and go straight on.
3. Never open the plan tool's source.

# R3 - Call 2: write the Contracts file

Count the tasks N from the spec. `N <= 3` -> inline path (R7). `N >= 4` ->
write `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` in ONE write, containing
only this:

````markdown
# [Feature] Implementation Plan

**Goal:** [one sentence]

**Architecture:** [2-3 sentences]

**Tech Stack:** [key technologies]

## Global Constraints

- [project-wide rule with exact values from the spec and the conventions file - one per line]

## References

- `path/to/pattern_file.py` - [why every writer should see it]

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

Contract rules - all plan quality is decided here, nowhere later:

1. IDs run `T01, T02, ...` with no gaps (`T001` past 99). A producer's ID is
   lower than every ID that consumes it.
2. `Files` is required and lists every path the task creates, modifies or tests.
   Two tasks sharing a file are serialized automatically, so give each task its
   own files and wire shared registries in one final task.
3. `Produces` holds exact backticked declarations - name, parameters, types,
   return - written the way they will appear in code. `Consumes` copies the
   producer's text byte for byte; `(existing)` marks a symbol already in the
   codebase. Omit `Consumes` to mean "everything my Depends produce". Depends
   are derived from Consumes automatically.
4. `Spec` gives line ranges from the heading map. Each writer receives exactly
   those lines and nothing else, so a wrong range silently starves a task.
5. `Read` (optional) adds existing files that writer needs inlined.
6. `Tier` (optional) is `light` for trivial config or docs, `deep` for
   algorithmic, security, concurrency or migration work. Default is standard.
   Tier picks the model and the reasoning effort, so it is the main speed dial.
7. Right-size each task: the smallest unit with its own test cycle that a
   reviewer could reject on its own.
8. `References` is optional and is inlined into every writer's shared prefix -
   put one or two exemplars there, never a pile.

# R4 - Call 3: build

```
<TOOL> build <plan> --spec <spec>
```

Run it with a shell timeout of 900000 ms or more. It validates the contracts,
fans out one writer per task over up to 64 concurrent threads, lints every body,
repairs failures automatically, runs a risk-based review pass, then assembles
and cleans up. Add `--thorough` (or when the user asked for maximum assurance)
to review every task instead of only the risky ones.

1. `ERR` before the fan-out means a contract problem. Fix those lines in the
   plan file and re-run the same command.
2. Named failing task IDs after the fan-out: re-run with `--resume` added. It
   retries only those.
3. `OK assembled ...` is done. Go to R5.
4. `LANE agent` in the output means no API key was found, so the script fell
   back to printing a DISPATCH table: dispatch one subagent per row, ALL in a
   single message, each with the prompt `Read <brief path> and follow it
   exactly.`, then run the printed `wait`, `review` and `assemble` commands in
   that order. Tell the user once that `<TOOL> doctor` shows how to enable the
   fast lane.

# R5 - Handoff

Report, with the numbers from the build output:

"Plan saved to `docs/superpowers/plans/<file>.md` - N tasks, W waves, up to K in
parallel. It is self-contained: any agent or engineer can execute it from its
Execution Protocol. Options: (1) subagent-driven here, fresh worker per task,
each wave's `[P]` tasks together; (2) inline here, sequential with checkpoints;
(3) hand the file to any coding agent or engineer with 'Execute this plan
following its Execution Protocol.' Which one?"

# R6 - Speed rules that decide the wall clock

1. Never type what the script generates: Execution Protocol, File Structure,
   Execution Waves, `[P]` markers, Depends and Runs-after lines, Interfaces
   blocks, writer briefs. Output tokens are the bottleneck.
2. Machines check, models judge. Structure, placeholders, portability, file
   ownership, signatures, Run/Expected, `git add` scope and code-block syntax
   are one script call - never a model re-read.
3. Batch or die. When a step legitimately needs several tool calls, issue them
   in ONE message. If only one or two land, re-issue the rest as a single batch
   instead of trickling them.
4. Fix and move on. After a fix, re-run the script only - no re-review.
5. Do not switch model or effort mid-skill; each switch re-reads the whole
   conversation uncached.
6. Independent subsystems get one plan each, and they can be built concurrently.

# R7 - Inline path (N <= 3)

Read `references/body-rules.md` in this skill directory for the body format.
Write the skeleton and Contracts, then `<!-- TASKS -->`, then each task as
`### T01: Name` followed by its body - all in ONE write. Then run
`<TOOL> check <plan> --spec <spec>`, fix any `ERR`, done.

# R8 - Portability (the plan is the product)

The plan file must never mention an agent, a subagent, a model, a skill, a
plugin or a vendor tool. It is plain Markdown that anyone with a shell, an
editor and git can execute. The linter enforces this and will fail the build.

# R9 - One-time setup

`<TOOL> doctor` reports the lane, the key, the models and the concurrency.
`<TOOL> setup --apply` installs the fallback subagent for the detected harness.
Never run `--apply` without the user's consent. The fast lane needs one export:

```bash
export ZAI_API_KEY=<GLM Coding Plan key>
export ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic
```
