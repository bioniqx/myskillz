---
name: hybrid-writing-plans
description: "Opt-in fork of writing-plans: use only when the user says 'hybrid', mentions 'opencode', asks to save tokens, cost or usage limits while planning, or invokes /hybrid-writing-plans. Produces the same portable TDD checkbox implementation plan as writing-plans - contracts locked once by Claude, task bodies fanned out to opencode writers (per-tier model and thinking level) and Claude writers from script-built briefs, every body verified by the same deterministic linter, with lint-repair turns in the same opencode session and one Claude fallback per failed group. Connection failures are retried 3 times, then hybrid mode moves the rest of the run to Claude Sonnet 5.5. Reviewers and every judgment step stay on Claude."
argument-hint: "[spec-path] [--thorough] [mode=hybrid|claude|opencode]"
allowed-tools: Bash(python3 *)
compatibility: Claude Code v2.1.217+ recommended (subagent cap setting); python3 3.8+; opencode CLI v2.0.19 for the hybrid and opencode modes
---

# Hybrid Writing Plans (v1.0 - opencode writers)

Write implementation plans for an engineer with zero context and questionable taste: exact files, real code, exact commands with expected output, commits. DRY. YAGNI. TDD.

**Announce:** "I'm using the hybrid-writing-plans skill to create the implementation plan."

## Context (computed when the skill loaded)

```!
python3 "${CLAUDE_SKILL_DIR}/scripts/plan_tool.py" context "$ARGUMENTS"
```

If the block above shows a raw command instead of output, run `python3 <this skill dir>/scripts/plan_tool.py context <spec>` in the same message as your Phase 0 reads. `TOOL` below = the `tool:` line of the context (use it verbatim).

## Step 0 - Run mode (before any other work)

**HARD GATE: the mode popup is mandatory.** Unless the args contain `mode=hybrid|claude|opencode` (or this is a resumed run whose mode is already frozen in run state), the very first tool call of this skill is AskUserQuestion with the three options below, before reading files, planning or running any script. AskUserQuestion may be a deferred tool: load its schema with ToolSearch (`select:AskUserQuestion`) first, then call it. This overrides any "act first", "never block on questions" or auto-mode default. Do not guess the mode from the user's wording (even "hybrid" or "opencode"), from `preset` in routing.json or from an earlier run, and never pick Hybrid on the user's behalf. Wait for the answer.

The context ends its opencode block with a `mode:` line (a separate `mode: THOROUGH` line further down is the review setting, not the run mode).

- `mode: <hybrid|claude|opencode> (from arguments)` -> use that mode and do not ask. Hand-offs between the hybrid skills (brainstorming, writing-plans, team) pass it along as `mode=<mode>`.
- `mode: unset ...` or `mode: '<x>' is not valid ...` -> your first tool call is AskUserQuestion, "Run this skill in which mode?", with three options. Put the configured `std` and `lite` specs from the config line (the line after `opencode:`) into the descriptions, each with its `(skill)` or `(shared)` mark from the end of that line, or "no config" when that line says the config is missing or invalid:
  - **Hybrid (Recommended)** - judgment on Claude, task writers on opencode, every opencode error reported at once, automatic Claude fallback; after 3 failed retries of a connection error the rest of the run moves to Claude Sonnet.
  - **Claude only** - opencode is never called; the same pipeline, contract rules and linter as writing-plans 6.2.
  - **opencode only** - every task the routing table sends to opencode goes to opencode, with no silent Claude fallback.
- Persist the choice by passing `--preset <mode>` to `contracts` (Phase 1). The script freezes it in `work.json`; `wait`, `review` and `assemble` never ask again.
- The old name `max` still works as an alias of `opencode` and prints one OC-WARN line.

## Speed Doctrine

1. **Serial only where divergence is born** (the Contracts). Everything else runs in parallel, one message per wave.
2. **Never type what the script generates:** Execution Protocol, File Structure, Execution Waves, `[P]`, Depends/Runs-after lines, Interfaces blocks, writer briefs, opencode briefs, fallback briefs. Output tokens are the bottleneck.
3. **Machines check, models judge.** Structure, placeholders, portability, file ownership, signatures, Run/Expected, `git add` scope and code-block syntax are one script call - never a model re-read. The linter is the oracle for every body, whoever wrote it.
4. **Respect the cap.** Running subagents above `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (default 20) fail with "Concurrent subagent limit reached". The script sizes the Claude fan-out as writers = min(live cap, 12, ceil(Claude-routed tasks/3)), batching about 3 tasks per writer because every agent has a fixed token overhead, and sizes the opencode fan-out to each tier's `max_parallel` (at most 8 per tier, clamped) AND a shared pool across all tiers (`HYBRID_OPENCODE_POOL`, default 6, at most 8), so no more than the pool's worth of opencode runs are in flight at once; never dispatch more.
5. **Keep the cache warm.** Don't change model or effort mid-skill (each change re-reads the whole conversation uncached). Writers get facts from briefs, not from exploring.
6. **Fix-and-move-on.** After a fix, re-run only the script - no re-review.

## Portability Rule (the plan is the product)

The process uses subagents and opencode; the plan file must not mention them. It is plain Markdown any AI agent or human with a shell, an editor and git can execute. The linter enforces the terms it scans for; it does not scan for the word opencode, so the writer and reviewer briefs forbid it and a reviewer removes any hit.

## Scope Check

Independent subsystems -> one plan each; plans may be produced concurrently with the writer budget split between them.

## Hybrid routing

The context shows one `opencode:` line right after `writer agent:`, then the shared-config line and the `mode:` line. Example: `opencode: v2.0.19 preset=hybrid light=oc:lite std=oc:std deep=claude review_oc=risky (doctor 2026-09-29)`.

For each contract tier (`light`, `std` = no `Tier` line, `deep`) the value is `claude` (Claude writer, 6.2 model map), `oc:<tier>` (opencode writer on that routing tier) or `claude(<reason>)` (the routing tier is unusable). `opencode: unavailable ...` means there is no usable doctor entry: `contracts` prints an `OC-ERROR` line saying why, then in mode hybrid every writer is Claude and in mode opencode the tasks are held.

| Work | `claude` | `hybrid` (default) | `opencode` |
|---|---|---|---|
| Phase 0, Contracts, assemble | Claude | Claude | Claude |
| Inline path (N <= 3) | Claude | never used: always fan-out | never used: always fan-out |
| Writer, contract `Tier: light` | Claude sonnet | oc:`lite` | oc:`lite` |
| Writer, default tier | Claude sonnet | oc:`std` | oc:`std` |
| Writer, contract `Tier: deep` | Claude sonnet | Claude sonnet | oc:`std` |
| Reviewers | Claude sonnet, 6.2 triggers | Claude sonnet, 6.2 triggers | Claude sonnet, 6.2 triggers |
| Fallback writer | - | Claude, model per the tier map (`sonnet` once the run has switched) | none: the unit is held (Failure policy) |

Models come from two environment variables shared by all four hybrid skills: `HYBRID_OPENCODE_STD` (required) and `HYBRID_OPENCODE_LITE` (optional, defaults to `STD`), each `provider/model[#variant]`, for example `opencode/muse-spark-1.3-contributor-free#xhigh`. Set them in the `"env"` block of `~/.claude/settings.json`, for example `{"env": {"HYBRID_OPENCODE_STD": "opencode/muse-spark-1.3-contributor-free#xhigh"}}`, then restart Claude Code; exporting them in the shell works too. When the config line says `HYBRID_OPENCODE_STD is not set`, tell the user that. Timeouts, roles and review policy stay in `$HYBRID_WRITING_PLANS_ROUTING` (default `<skill dir>/routing.json`, for example `~/.claude/skills/hybrid-writing-plans-v1.0/routing.json`), merged over the shipped `routing.default.json`. That per-skill file may also override a tier's model: a tier whose `tiers.<tier>.model` is set there uses that `model` and its `variant` (none when omitted), every other tier uses the shared models. `max_parallel` comes only from that file or the shipped defaults. The context config line and the doctor's tier lines mark each tier `(skill)` or `(shared)`. The mode comes from Step 0: `contracts --preset <mode>` routes once and records the result in `work.json`. Mode `claude` follows writing-plans 6.2 (same contract rules and linter, compared by `tests/test_lint_parity.py`) and never needs a doctor run.

Rules:
- Routing, partitioning and every brief are the script's job. Never hand-write an opencode brief, never edit a `<gid>.oc.md` or `<gid>F.md` brief, never run `opencode` yourself.
- **Relay rule (always on).** Any `OC-ERROR` or `OC-WARN` line in tool output - from `contracts`, `oc-write`, `wait`, `review`, `assemble` or `doctor` - means your next message to the user starts with that line, verbatim, before any other work. Deduplicate identical `kind` + `tier` pairs: relay the first line and say how many more matched. Never treat these lines as informational and never skip one.
- `oc-write` runs once per `contracts` run, always as a background Bash call, in the same message as the Claude `Agent` calls. It lints every body, sends lint repairs back to the same opencode session, prints each OC line as its group finishes and writes a fallback brief for anything it gives up on. It always exits 0; `wait` is what reports the failures to you. A `contracts` re-run keeps every opencode task body that survived (contract unchanged, still lint-clean, for example fixed by a reviewer) and only prints an `OPENCODE` row for groups with a pending or invalidated task; `oc-write` never rewrites a finished body. The run mode is frozen in `work.json`: a re-run without `--preset` keeps it, and a doctor cache that goes stale in the middle of a run never moves a tier to Claude.
- A `FALLBACK` line from `wait` is one Claude `Agent` call: launch it exactly as printed (subagent type, model, description, prompt), once. Never retry the opencode group in place.
- `oc-write` retries a group whose opencode run failed on the connection (`spawn`, `stall`, `throttle`, `crash`) itself, up to 3 times, 10, 30 and 60 s apart, as a fresh run (never a `--session` continuation). Each failed try is one `OC-WARN ... kind=<kind> :: retry <n>/3 in <s>s: <detail>` line. Lint-repair turns are separate and unchanged. `timeout`, `context` and the gate kinds (`grounding`, `lint`, `oracle`, `gate`, `empty`, `format`, `recovered`) are not connection problems: no retry, no switch.
- Overflow queues, it does not move to Claude. A tier runs at most min(`max_parallel`, pool) groups at once (the pool is shared by all tiers: `HYBRID_OPENCODE_POOL`, default 6, up to 8), each of up to `oc_group_max` tasks; `contracts` splits the tasks beyond that into more groups of the same size (in mode hybrid and in mode opencode), and `oc-write` runs them as slots free up, in the same call (`wait` covers them; a `NOTE ... queue for a free slot` line says how many). Only `oc_overflow: "claude"` in `routing.json` (mode hybrid) restores the old split, where the heaviest overflow tasks go to Claude writers. A tier that is unusable, throttled or slow costs nothing extra: an unusable tier's tasks go to Claude (mode hybrid) or are held (mode opencode) at `contracts` time, and failed groups come back as `FALLBACK`.

Failure policy:

| Mode | On OC-ERROR / OC-WARN |
|---|---|
| claude | opencode is never spawned; the doctor is not required. |
| hybrid | Relay the line at once, then continue: the Claude writers take over as printed. After the retries, a connection error or a non-retryable one (`auth`, `quota`, `model`, `config`) switches the run (below). |
| opencode | Relay the line at once. Never run the unit on Claude by yourself. The retries happen here too; after them nothing changes: the unit is held. |

**Switch (mode hybrid only).** When a group still fails after its retries, or fails with `auth`, `quota`, `model` or `config`, `oc-write` records the switch in `<work>/oc/oc-switched.json` and prints and logs one `OC-ERROR ... kind=switch :: opencode <kind>: <detail>; the rest of this run uses Claude sonnet` line, once (relay it like any other). From then on the rest of that run uses Claude Sonnet 5.5 (`model: sonnet`): the failed group and every group that had not started come back as `FALLBACK <gid> (<reason>) ...` lines with `model=sonnet` and no opencode spawn, and `wait` prints them like any other fallback (launch them exactly as printed). Groups already running on opencode finish and are harvested normally. A new `contracts` run starts unswitched. In mode opencode there is no switch.

In mode opencode a `HELD` block from `contracts`, or a `HELD` line from `wait` (a group that failed while running), is an offer, not an order. After relaying the lines, ask once per root cause with AskUserQuestion (identical failures go into one question): retry on opencode / run this unit on Claude / switch the run to hybrid / abort.
- Retry: fix the cause (for example `TOOL doctor --ping`), re-run `contracts <plan> --preset opencode` and dispatch the rows it prints for tasks that are not written yet.
- Run on Claude: for a `HELD` block from `contracts`, launch its brief rows exactly as printed; for a `HELD` line from `wait`, launch one Agent call with the model printed on that line, description `plan <gid>F` and prompt `Read <brief> and follow it exactly.` Then run `TOOL wait <plan> --include-held`.
- Switch to hybrid: re-run `contracts <plan> --preset hybrid` and continue.
- Abort: stop and tell the user what is left.

## Pipeline

### Phase 0 - Load (ONE message)

Read the spec fully and 2-5 pattern files picked from the context (a test, a similar module, build config) - all in one message of parallel Reads. Only when the repo is large and you cannot locate the affected code from the context: add up to 3 narrow `Explore` agents in that same message. Estimate the task count N.

**Mode `claude`: N <= 3 -> Inline path, N >= 4 -> Fan-out (Phases 1-4). Modes `hybrid` and `opencode`: always Fan-out (Phases 1-4), whatever N is, even N = 1: Claude writes only the Contracts and the task bodies go to opencode per tier. Never use the Inline path in those modes.**

### Phase 1 - Contracts (serial, ONE Write)

Write `docs/plans/YYYY-MM-DD-<feature>.md` containing only:

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
- `Read` (optional): extra existing files this writer needs. `Tier` (optional): `light` (trivial config/docs) or `deep` (algorithmic, security, concurrency). Default: `std`. The tier also picks the backend (see Hybrid routing), so tier honestly: a contract that needs deep judgment must say `Tier: deep`, which keeps it on Claude (sonnet) in `hybrid`.
- Right-size: smallest unit with its own test cycle a reviewer could reject independently. The tighter the contract, the better a cheap writer does.
- Legitimate project vocabulary that the placeholder/portability scan would flag (for example a to-do app, or a class named `Task`) needs `--allow WORD` on every `contracts`/`assemble`/`check` call - decide this now, not after `assemble` fails.

Run `TOOL contracts <plan> --spec <spec>` (add `--agents K` only if you know the real cap differs from what the script detected; Claude writers stay <= 12 and ~ceil(tasks/3); always add `--preset <mode>` with the mode chosen in Step 0). Fix every `ERR` with Edit and re-run until `OK`. Treat `WARN spec uncovered` as a missing task unless the section is non-functional. `OK` prints `WORK`, the `DISPATCH` table for the Claude groups (only when there are any), the `OPENCODE` block for the opencode groups (only when there are any) and the next command.

### Phase 2 - Fan-out writers (ONE message)

In a single message:
- For every DISPATCH row, one Agent call:
  - `subagent_type`: as printed (`hybrid-plan-task-writer` when installed; if the call says the type is unknown, use `general-purpose`)
  - `model`: the row's MODEL
  - `description`: `plan <ID>`
  - `prompt`: `Read <BRIEF> and follow it exactly.` - nothing else; the brief carries contract, spec lines, inlined files, rules and lint command.
- When an `OPENCODE` block was printed, exactly one Bash call with `run_in_background: true` running the command on the `OPENCODE` line (`TOOL oc-write <plan>`), verbatim. Its rows (`O01 oc:std T03-T05 <brief>`) are for your information; do not dispatch them yourself.

A call refused with "Concurrent subagent limit reached" means other subagents hold slots: don't retry it in a loop - dispatch those rows again after the next completion notification.

Then, in your next message, run the printed `TOOL wait <plan>` with Bash `timeout: 600000`. It blocks until every task file lints OK, an opencode group has fallen back or a new opencode error appears. Queued opencode groups that have not started are not failures: while `oc-write` runs, `wait` reports no idle stall, and a `PENDING ... timeout` that prints `oc-write is still running` just means run `wait` again. It prints unreported `OC-ERROR` / `OC-WARN` lines before anything else: relay them per the relay rule. Launch nothing on individual completion notifications (Agent or `oc-write`) while waiting; if a notification carries OC lines, relay them first.
- `DONE` -> Phase 3.
- `FALLBACK <gid> (<reason>) <ids> → Agent subagent_type=<type> model=<model> description 'plan <gid>F' prompt: Read <brief> and follow it exactly.` -> mode hybrid: launch every FALLBACK Agent call exactly as printed, all in ONE message, then run `wait` again. Each fallback is launched once; `wait` never prints a sent one again. After a switch every FALLBACK line says `model=sonnet` (reason `switched` for groups that never started). Mode opencode never prints `FALLBACK`; it prints `HELD` instead.
- Exit 2 with `Relay the OC-ERROR lines above` -> relay them, then run `wait` again.
- `HELD <gid> (<reason>) <ids> ...` (exit 2, mode opencode) or `HELD <ids> not written ...` (exit 3, only held tasks are left) -> do not dispatch anything yourself: see Failure policy.
- `PENDING` -> if those agents or `oc-write` are still running, run `wait` again. If Claude writers returned `FAIL` or stopped: re-dispatch only those IDs in one message (same prompt), or fix a small issue yourself with Edit + `TOOL lint-task <plan> <task file>`.

### Phase 3 - Risk-based review (ONE message)

Run `TOOL review <plan>` (`--all` when invoked with `--thorough` or the user asks for maximum assurance). Besides the 6.2 triggers it adds the `oc` trigger for opencode-written tasks, per the context line's `review_oc`: `all` reviews every opencode-written task, `risky` (the default in every mode) only those that also hit another trigger (tier deep, long body, consumes >= 3, lint warnings). Setting `review_oc.hybrid: "all"` in the skill's `routing.json` restores reviewing every opencode task in hybrid. `NONE` -> skip to Phase 4. Otherwise dispatch its rows exactly like Phase 2 (`general-purpose`, `sonnet`), then run the printed `wait --review`. Reviewers fix their own task files in place. An "Unfixable (needs contract change)" line -> edit that contract, re-run `contracts`, re-dispatch only the affected writers (Agent rows and, if printed, the background `oc-write`), `wait`.

### Phase 4 - Assemble (ONE command)

`TOOL assemble <plan> --clean` - re-lints everything, then renders the canonical plan: execution note, Execution Protocol, File Structure (if you wrote none), Execution Waves, and each task's heading/`[P]`/Depends/Runs-after/Interfaces, then deletes the scratch dir. On `ERR` nothing is written: fix the named task file, re-run. Legitimate project vocabulary that trips the placeholder check: add `--allow <word>`.

## Inline Path (mode `claude` only, N <= 3)

Read `task-writer-prompt.md` in this skill dir for the body format. Write the skeleton + Contracts, then `<!-- TASKS -->`, then each task as `### T01: Name` followed by its body - all in ONE Write. Run `TOOL check <plan> --spec <spec>`; fix `ERR`s; done (it renders the same canonical plan). Modes `hybrid` and `opencode` never use this path (they fan out for every N), because it would write every body on Claude.

## Execution Handoff

After `OK`, offer (waves/width from the script output):

**"Plan saved to `docs/plans/<file>.md` - N tasks, W waves, up to K tasks in parallel. It is self-contained: any agent or engineer can execute it via its Execution Protocol. Options:**

**1. Team-driven (recommended)** - mode `hybrid` or `opencode`: the `hybrid-team` skill adopts this plan as authoritative and implements it end to end, low-judgment slices on opencode; mode `claude`: the `dev-team` skill does the same, Claude only.

**2. Subagent-Driven here** - fresh subagent per task, review between tasks; each wave's `[P]` tasks dispatched together in one message (within the subagent cap).

**3. Inline Execution here** - sequential, with checkpoints.

**4. Hand off** - give the file to any coding agent or human with: *"Execute this plan following its Execution Protocol."*

**Which approach?"**

- Team-driven, mode `hybrid` or `opencode` -> invoke the `hybrid-team` skill with args `<plan path> mode=<mode>` (`<mode>` is the Step 0 run mode; the chain brainstorming -> writing-plans -> team keeps one mode). If `hybrid-team` is not installed, say so and offer `dev-team` (args `<plan path>`).
- Team-driven, mode `claude` -> invoke the `dev-team` skill with args `<plan path>`.
- Subagent-Driven -> dispatch each wave's `[P]` tasks yourself as subagents here, reviewing between waves.
- Inline -> execute the plan yourself here, sequentially, with checkpoints.
- Hand off -> nothing else; the plan carries everything.

## One-time setup (tell the user when the context shows cap < 12, `opencode: unavailable`, or a stale/placeholder writer agent)

`TOOL setup` (dry run) then `TOOL setup --apply`, then restart Claude Code. It sets `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=16` only when the variable is set and below 12 (unset keeps the default 20; a higher value is never lowered), pre-approves `TOOL` and edits under `docs/plans/`, and installs the `hybrid-plan-task-writer` agent (sonnet, effort medium, no CLAUDE.md load, PostToolUse auto-lint hook that saves each writer a turn); a stale or placeholder copy is replaced, a current one is left alone. Never run `--apply` without the user's consent.

`TOOL doctor --ping` checks the opencode binary and version, validates the shared models (`HYBRID_OPENCODE_STD` / `HYBRID_OPENCODE_LITE`) and the per-skill routing file, confirms each tier's model is listed, sends each tier one tiny ping and writes the doctor cache the context line reads. Failures print as `OC-ERROR` lines and one tier's failure never disables the other; it never creates or edits a config file. Run it once after installing opencode or changing the variables (restart Claude Code first), and again when the context line shows `unavailable` or a `claude(...)` tier; a cache entry past its time limit counts as unusable. The context line itself never spawns opencode. `TOOL stats` summarises the per-tier telemetry (round-1 pass rate, fallbacks, review fix rate). Optional: `/fast` speeds the serial contract phase on Opus.
