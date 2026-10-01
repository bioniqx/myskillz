# hybrid-team

A fork of `dev-team-v3.2` that keeps every judgment-heavy step on Claude and offloads
low-judgment, oracle-backed execution to the local `opencode` CLI, with a configurable model and
thinking level per tier. Read `SKILL.md` for how the Conductor drives it; this file covers
installation, configuration and troubleshooting.

## Why

Claude decides WHAT to build and WHETHER it is right. The cheap model only EXECUTES a precise spec
against a machine oracle - frozen tests, a `verify` command, or an existing suite that must stay
green. A slice with no oracle is never offloaded. This cuts Claude token spend on implementation
lanes without lowering the merge bar dev-team-v3.2 enforces today.

## Install / requirements

- Claude Code >= 2.1.267, git >= 2.31, python3.
- `opencode` CLI v2.0.20 on `PATH`, authenticated for the providers of your configured models
  (the shared `HYBRID_OPENCODE_STD` / `HYBRID_OPENCODE_LITE` models or a per-skill override, see Config). Without it, hybrid-team still works in
  the `claude` and `hybrid` modes - `doctor` reports it with an `OC-ERROR` line and every slice
  runs on Claude; in `opencode` mode those slices are held instead.
- Drop this folder where Claude Code loads skills from, alongside (not instead of) `dev-team-v3.2`
  if you want both installed: every shared name carries the `hybrid` prefix (see Names) and state lives under
  `.claude/hybrid-team/`, so the two skills never collide.

## Backends

| Backend | Runs | Where |
|---|---|---|
| Claude | planning, all reviews, verification, investigators, RED, `research`/`perf`, anything the router can't offload | Claude Code subagents, background |
| opencode | GREEN of `code` (any size, except `risk: high`), `refactor`, `test` backfill, `chore`, `docs` | `.claude/worktrees/hybrid-oc-<id>` via the `lane` command |

## Run modes

Each run starts with one question (skipped when the invocation args carry `mode=hybrid`,
`mode=claude` or `mode=opencode`, which hand-offs from the other hybrid skills use): hybrid
(recommended), Claude only, or opencode only. The answer becomes the preset passed as
`start --route` and is kept in the run state, so a resumed run never asks again. The question
lists the `std` and `lite` model specs, each marked `(skill)` (the model is set in
`<skill dir>/routing.json`) or `(shared)` (it comes from the shared env vars, see Config).

| Mode / preset | opencode | On an opencode failure |
|---|---|---|
| Claude only / `claude` | never spawned; `doctor` not required | not applicable |
| Hybrid / `hybrid` | offloadable lanes run on it | a connection failure is retried 3 times first; then the `OC-ERROR` line is printed at once and the slice re-runs on Claude automatically. A connection or non-retryable failure also switches the rest of the run to Claude Sonnet 5.5 (`model: sonnet`, one `kind=switch` line); timeout, context and gate failures only fall back per slice |
| opencode only / `opencode` | every lane the router can offload, including `risk: high` slices | a connection failure is retried 3 times first; then the `OC-ERROR` line is printed at once and the slice is held, with no Claude fallback and no switch; Claude asks once per root cause: retry on opencode, run the unit on Claude, switch the run to hybrid, or abort |

`max` is the old name of `opencode`; it is still accepted and prints an `OC-WARN ... kind=config`
line. Any other preset name is an `OC-ERROR ... kind=config` and the command exits non-zero.
Reviewers, the leader, RED, verification and investigation stay on Claude in every mode.

A Small request (one coherent slice, about 6 files or fewer, no new shared interface, no concurrency or
security surface) follows the mode: in `claude` the Conductor implements it in the Fast lane, in `hybrid`
and `opencode` it runs as a one-slice pipeline (inline one-slice plan, no leader, `devteam start`): RED on
Claude, GREEN or WORK on opencode, normal review. That is why the mode question comes before the route for
Small work. One obvious edit, a code question, review-only and investigation need no mode and skip the
question; an obvious edit also never starts the engine, because an opencode spin-up costs more than the
edit. `perf` slices stay on Claude: the gate only counts lines of the pasted bench output and does not
compare before/after numbers, so there is no deterministic oracle, and finding the optimization is
diagnosis. A `docs` slice that runs on Claude (mode `claude` or a fallback) uses sonnet unless
`size: large`; in `hybrid` and `opencode` it goes to the `lite` tier at any size.

A connection failure (`spawn`, `stall`, `throttle`, `crash`) is retried in the lane up to 3 times,
waiting 10 s, 30 s and 60 s, and each failed try prints
`OC-WARN ... kind=<kind> :: retry <n>/3 in <s>s: <detail>`. In `hybrid` mode, once the retries are
spent (or at once for `auth`, `quota`, `model`, `config`), the whole rest of the run uses Claude
Sonnet 5.5: the engine prints one
`OC-ERROR ... kind=switch :: opencode <kind>: <detail>; the rest of this run uses Claude sonnet` line,
records `oc-switched.json` in the run state directory, and every later slice that would have gone to
opencode is dispatched to Claude with `model: sonnet` (opencode is not spawned again). Lanes already
running on opencode finish normally. `opencode` mode is unchanged after the retries: the slice is
held. `init` starts every run unswitched.

Every error line has one shape: `OC-ERROR <skill> <unit> tier=<tier> model=<spec> kind=<kind> :: <detail>`,
plus ` log=<path>` when a log exists. `OC-WARN` has the same shape for problems that did not stop the
work (`recovered`, `empty`, `format`, ...). Each line is also appended to `oc-errors.jsonl` in
the run state directory.

## Config

- **Shared opencode models** (read by all four hybrid skills): env `HYBRID_OPENCODE_STD` (required,
  the `std` tier) and `HYBRID_OPENCODE_LITE` (optional, the `lite` tier; defaults to
  `HYBRID_OPENCODE_STD`). They are the default place for a tier's model and variant, one setting for
  all hybrid skills. Each value is `provider/model[#variant]`: `provider/model` is required and the
  optional `#<variant>` suffix is the thinking level. Set them in the `"env"` block of
  `~/.claude/settings.json`, then restart Claude Code (exporting them in the shell before starting
  Claude Code also works):

      {"env": {"HYBRID_OPENCODE_STD": "opencode/muse-spark-1.3-contributor-free#xhigh"}}

  Add `HYBRID_OPENCODE_LITE` only when the `lite` tier should use a different model. A missing
  `HYBRID_OPENCODE_STD` or a value that is not `provider/model[#variant]` is reported as a config
  problem.
- **Shipped defaults**: `hybrid-team-v1.0/routing.default.json` - it carries no `model` or `variant`.
- **User file**: `<skill dir>/routing.json` (e.g. `~/.claude/skills/hybrid-team-v1.0/routing.json`) -
  optional; `doctor --fix` no longer creates it. Write it to change stall or run timeouts, `rows` or
  `max_escalations`, or to override a tier's model (see Precedence). A file that does not parse is
  reported as a config problem, never skipped silently. Override the path with env
  `HYBRID_TEAM_ROUTING=<path>`.
- **Precedence per tier** (`std`, `lite`): when the user file sets `tiers.<tier>.model`, the tier
  uses that file's `model` and `variant` and is shown as `(skill)`; a tier that sets no `variant`
  there runs without one, and the shared variant is never mixed in. Otherwise the tier uses
  `model` and `variant` from its shared env var and is shown as `(shared)`. `max_parallel` comes from
  the user file, else the env var `HYBRID_OPENCODE_MAX_PARALLEL` (1 to 64), else the shipped defaults (4). The shared env vars are
  reported as unset or invalid only when some tier needs them, and a tier with no model in either
  place is an `OC-ERROR ... kind=config`. The run-mode question shows each tier's source next to its spec.

      {"tiers": {"std": {"model": "zai-coding-plan/glm-5.3", "variant": "high"}}}

  This user file moves only `std`; `lite` keeps following `HYBRID_OPENCODE_LITE`.
- **Per run**: the plan JSON's `routing` block is merged last and overrides keys for that run only.
- **Per slice**: a slice's `backend` field pins it directly, bypassing the routing table.

      {"preset": "hybrid",
       "tiers": {
         "std":  {"stall_s": 180, "timeout_s": {"trivial": 600, "small": 1200, "large": 2400}},
         "lite": {"stall_s": 120, "timeout_s": {"trivial": 300, "small": 600, "large": 1200}}},
       "max_escalations": 1}

`preset` selects the row table (`claude`, `hybrid`, `opencode`; the old `max` is still accepted as an
alias - see Run modes), and the run mode chosen at start is passed as `--route` and wins for that run.
`tiers` holds, per tier name, a stall timeout in seconds and a per-`size` run timeout (plus an
optional `model`, `variant` and `max_parallel`, see Precedence). `rows` (present
in `routing.default.json`, omitted above for brevity) maps the table rows `code`, `refactor`, `test`,
`chore`, `docs`, `trivial` to a tier name. `max_escalations` caps how often a slice that failed on
opencode is re-dispatched to Claude in `hybrid` mode (shipped default: one, then the normal BLOCKED
flow). `escalate_to` was documented but never read; it has been removed.

## Names

Everything this skill puts into a shared namespace is prefixed `hybrid`, so it installs beside dev-team:

- Agents: `hybrid-team-programmer`, `hybrid-team-code-reviewer`, `hybrid-team-spot-reviewer`,
  `hybrid-team-investigator`, `hybrid-team-leader` (files in `agents/`, installed by `doctor --fix`);
  the opencode agent is `hybrid-team-programmer`.
- Env vars: `HYBRID_TEAM_ROUTING`, `HYBRID_TEAM_OC_BIN`, plus the shared `HYBRID_OPENCODE_*`; test
  harness only: `HYBRID_TEAM_FAKE_SCRIPT`, `HYBRID_TEAM_FAKE_LOG`.
- Git: lane worktree `.claude/worktrees/hybrid-oc-<id>` on branch `hybrid-oc-<id>`, checkpoint
  worktree `.claude/worktrees/hybrid-checkpoint-<n>`, salvage branches `hybrid-attempt/<id>-<n>`.
  Leftover cleanup only touches these prefixes.
- State: `.claude/hybrid-team/`.

## Environment variables

- `HYBRID_TEAM_ROUTING=<path>` - routing config path, instead of `<skill dir>/routing.json`.
- `HYBRID_OPENCODE_STD=<provider/model[#variant]>` - shared model for the `std` tier (required unless
  every tier sets its own `model` in the routing file).
- `HYBRID_OPENCODE_LITE=<provider/model[#variant]>` - shared model for the `lite` tier; defaults to
  `HYBRID_OPENCODE_STD`.
- `HYBRID_TEAM_OC_BIN=<path>` - path to the `opencode` executable (or a fake one, in tests) instead of
  resolving `opencode` on `PATH`.
- `HYBRID_OC_RETRY_DELAY_S=<seconds>` - replaces every wait between connection retries (10/30/60 s
  by default); tests set it to `0`.

## Troubleshooting

- `devteam doctor` - reports whether opencode is on `PATH` and lists each tier's model
  (`oc_available(root: Path, routing: dict) -> bool` is the check it runs internally), whether the
  per-skill config file parses (and the shared env vars are set and valid, when some tier takes its model from them), and whether `.claude/settings.local.json` has the
  concurrency/timeout limits hybrid-team needs. A bare `doctor` sends no test prompt; `doctor --ping`
  pings every tier, and `start` pings each tier without a fresh result in `hybrid` and `opencode`
  mode, so a bad login, quota or model shows up before any lane is dispatched as
  `OC-ERROR ... kind=auth` (or `quota`, `model`). Every problem is printed as an `OC-ERROR` or
  `OC-WARN` line. `doctor --fix` writes anything missing; it no longer copies the routing defaults.
- opencode missing or auth broken -> in `hybrid` mode the slice runs on Claude after the error line;
  in `opencode` mode it is held and Claude asks what to do. Nothing to fix before a `claude`-only run.
- A lane stuck with no progress -> the lane process itself kills the opencode process group once its
  tier's stall timeout elapses and writes a `.blocked` marker that names the stderr log; `devteam
  next` only harvests that marker (in `hybrid` mode it then re-dispatches the slice to Claude). The
  `OC-ERROR ... kind=stall` line is printed when it happens.
- A tier is marked `(skill)` in the run-mode question but you want the shared model -> delete `model`
  and `variant` from that tier in `<skill dir>/routing.json` (a leftover model there keeps
  winning for hybrid-team); the tier then follows its shared env var.
- `bash hybrid-team-v1.0/scripts/selftest.sh` - the self-check. Since 1.2.0 it passes on macOS
  too (`passed=255 failed=0`); before the re-sync with dev-team it had 8 known macOS harness
  failures (GNU `sed -i`, `/var` -> `/private/var`, a bash 3.2 word-split).
- A slice is `HELD` in `opencode` mode -> the `OC-ERROR` line names the tier, model and cause.
  `devteam retry <id>` pings that tier again: an ok ping clears its breaker and the slice goes back
  to opencode; `devteam retry <id> --claude` runs it on Claude instead.
- `doctor --ping` always pings a tier whose last ping failed (and `start` does too), and both check
  the run's effective routing, including a model set in the plan's `routing` block.
- The run-mode question reads its specs from `python3 <skill dir>/scripts/router.py config`
  (read-only, always exits 0): `config: std=<spec> (skill|shared) lite=<spec> (...)`, or
  `no config` for a tier without a model.

## Security

- opencode lanes run with a deny-by-default permission allowlist, and `integrate` re-derives
  everything it merges from git: footprint, frozen tests, RED commit.
- **Residual risk: tests run model-written code with your rights.** A lane writes tests and
  implementation, and the gate executes them. No opencode permission can stop that code from
  writing anywhere you can, including `.claude/hybrid-team/state.json` (for example to widen its
  own footprint or change its slice kind).
- Mitigation: before merging, `integrate` re-validates each slice's footprint, kind and mode against
  the plan's JSON block (`plan.json` from `init`, the `plan.md` that `retry` re-reads, and
  `retry --files`). A mismatch is rejected as `plan-drift` and the plan's values are restored.
  This catches a rewritten state file; it does not stop code that also rewrites the plan files or
  touches anything outside the repo.
- The real fix is an OS sandbox (container, VM or a sandboxed user) around the whole run. Use one
  for repos or models you do not trust, and review the diff before you push.

## Differences from dev-team-v3.2

- New `lane <id>` engine subcommand runs one opencode-backed slice to completion (or a blocked
  marker) inside its own worktree.
- New backend router (`routing.default.json` / user routing file) decides Claude vs. opencode per
  slice from its `kind`/`size`/`risk`, or a slice's own `backend` field.
- New failure handling for opencode lanes (stall, timeout, throttle, crash, spawn, auth, quota,
  model, config): every failure is reported at once as an `OC-ERROR` or `OC-WARN` line, then
  `hybrid` mode escalates back to Claude and `opencode` mode holds the slice. Connection failures
  are retried 3 times first, and in `hybrid` mode a connection or non-retryable failure switches
  the rest of the run to Claude Sonnet 5.5.
- A run-mode question (hybrid, Claude only, opencode only) and shared opencode models from env
  `HYBRID_OPENCODE_STD` / `HYBRID_OPENCODE_LITE` for all hybrid skills, which a skill's own routing
  file can override per tier.
- `devteam stats` reports token/cost split by backend and tier in addition to dev-team's slice
  counts.
- Everything else - plan format, profiles, merge/`integrate`, guards, checkpoints, review cadence -
  is identical to dev-team-v3.2. Preset `claude` reproduces dev-team-v3.2's behaviour exactly.
