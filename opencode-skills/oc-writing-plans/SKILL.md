---
name: oc-writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code. Produces a portable TDD checkbox implementation plan - contracts locked once, task bodies written in parallel by background workers from script-built briefs, verified by a deterministic linter. Runs on the model selected in the current session.
metadata:
  version: "10"
---

# Writing Plans (v10)

Write implementation plans for an engineer with zero context and questionable
taste: exact files, real code, exact commands with expected output, commits.
DRY. YAGNI. TDD.

Announce once: "I'm using the writing-plans skill to create the implementation plan."

# R0 - The pipeline

Call 1 `brief` -> Call 2 write the contracts -> Call 3 `build` -> one turn that
dispatches the writers -> `wait`, `review`, `assemble`. Every extra turn costs a
full reasoning pass, so treat any call beyond these as a defect to explain, not a
habit.

# R1 - Call 1: resolve the tool and load everything

Run this as your FIRST tool call, with the spec path in place of `SPEC`:

```bash
for d in "${OPENCODE_CONFIG_DIR:-}/skills/oc-writing-plans" \
  .opencode/skills/oc-writing-plans \
  ~/.config/opencode/skills/oc-writing-plans \
  .agents/skills/oc-writing-plans \
  ~/.agents/skills/oc-writing-plans; do
  [ -f "$d/scripts/oc_plan_tool.py" ] && T="$d/scripts/oc_plan_tool.py" && break
done
[ -z "$T" ] && echo "writing-plans skill not found in any standard location" >&2 && exit 1
python3 "$T" brief SPEC
```

The output starts with a `TOOL:` line. Use that exact string for every later
call. The brief already contains the spec body with real line numbers, the spec
heading map, the repo file list, the stack, the test commands, the conventions
file and three or four auto-selected pattern files.

# R2 - Read nothing the brief already gave you

1. Do not re-read the spec. Do not search the repo.
2. The brief inlines up to four auto-selected pattern files. If they miss the
   test framework or a similar module a contract needs, pick up to three more
   from the brief's file list (2-5 pattern files in total) and read them in ONE
   message of parallel reads. The same applies to a file the brief names as
   "not inlined" that a contract cannot be written without. Then go straight on.
3. Never open the plan tool's source.

# R3 - Call 2: write the Contracts file

Count the tasks N from the spec. `N = 1` -> inline path (R7). `N >= 2` ->
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
   Tier only picks the writer agent (`deep` uses `oc-plan-task-writer-deep`, which
   also checks every consumed signature); it never selects a model.
7. Right-size each task: the smallest unit with its own test cycle that a
   reviewer could reject on its own.
8. `References` is optional and is inlined into every writer's shared prefix -
   put one or two exemplars there, never a pile.
9. Legitimate project vocabulary that the placeholder and portability scan would
   flag (a to-do list app, a class named `Task`) needs `--allow WORD` on every
   `build`, `assemble` and `check` call. `--allow` takes a case-insensitive stem
   (`subagent` also exempts `subagents`) or `re:PATTERN` matching the whole hit.
   Decide this now, not after `assemble` fails.

# R4 - Call 3: build

```
<TOOL> build <plan> --spec <spec>
```

It validates the contracts, writes one brief per writer group (up to four tasks
each) and prints a DISPATCH table with ready-made calls. Add `--thorough` (or
when the user asked for maximum assurance) to review every task instead of only
the risky ones.

1. `ERR` before the table means a contract problem. Fix those lines in the plan
   file and re-run the same command. Treat `WARN spec uncovered` as a missing
   task unless the section is non-functional.
2. Send each printed MESSAGE verbatim: every call in it runs in the background
   and all of them go in one message. Then end the turn. At most 8 calls may be
   in flight: send the next MESSAGE, if any, only after the last writer of the
   previous one reported and its task files exist.
3. When every writer has reported, run the printed `wait`, `review` and
   `assemble` commands in that order. `review` prints its own DISPATCH table:
   send it the same way, then run `wait --review` and `assemble`. A reviewer
   reply `T07 FAIL: ...` names an issue that needs a contract change: edit that
   contract in the plan file, re-run `build --resume` (a changed contract
   deletes its own task file and the task files of every task that depends on
   it), send only the rows it prints, then run `wait` again.
4. `wait` names failing task IDs: re-run `build` with `--resume` added. It writes
   briefs only for tasks that do not lint OK yet.
5. A row that names the `general` agent means the writer agents are not
   installed. Tell the user once that `<TOOL> setup --apply` installs them; the
   plan still builds.

Interactive sessions only: a headless run can exit before background calls
report.

# R5 - Handoff

Report, with the numbers from the build output:

"Plan saved to `docs/superpowers/plans/<file>.md` - N tasks, W waves, up to K in
parallel. It is self-contained: any agent or engineer can execute it from its
Execution Protocol. Options: (1) subagent-driven here (recommended), fresh
worker per task, each wave's `[P]` tasks together; (2) inline here, sequential
with checkpoints; (3) hand off: the oc-dev-team skill adopts this plan as
authoritative and implements it end to end, or give the file to any coding agent
or engineer with 'Execute this plan following its Execution Protocol.' Which one?"

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
5. Do not change the selected model mid-skill; each switch re-reads the whole
   conversation uncached.
6. Independent subsystems get one plan each, and they can be built concurrently.

# R7 - Inline path (N = 1)

Read `references/body-rules.md` in this skill directory for the body format.
Write the skeleton and Contracts, then `<!-- TASKS -->`, then each task as
`### T01: Name` followed by its body - all in ONE write. Then run
`<TOOL> check <plan> --spec <spec>`, fix any `ERR`, done.

# R8 - Portability (the plan is the product)

The plan file must never mention an agent, a model, a skill, a plugin or a
vendor tool. It is plain Markdown that anyone with a shell, an editor and git
can execute. The linter enforces this and will fail the build.

# R9 - One-time setup

`<TOOL> doctor` reports the harness and which agents are installed.
`<TOOL> setup --apply` installs `oc-plan-task-writer`, `oc-plan-task-writer-deep` and
`oc-plan-reviewer`. Never run `--apply` without the user's consent.
