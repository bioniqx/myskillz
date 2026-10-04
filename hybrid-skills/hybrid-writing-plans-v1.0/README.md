# hybrid-writing-plans

A fork of `writing-plans-6.2` that keeps every judgment step on Claude and offloads
task-body writers to the local `opencode` CLI, with a configurable model and
thinking level per tier. Read `SKILL.md` for how the plan tool drives it; this file covers
installation, configuration and troubleshooting.

## Why

Claude locks the contracts and judges the result. The cheap model only fills in task
bodies whose shape the contracts already fix, and every body must pass the existing
deterministic linter before it counts:
- Every contract `Produces` signature appears verbatim in the code.
- Every Run step is followed by Expected output or failure message.
- Python, JSON, TOML, bash and JS code blocks are syntax-checked (compiled, never run).

The tasks of a group whose output cannot pass the linter fall back to Claude once (one fallback per group). This cuts Claude
token spend on task bodies without changing the planning contract.

## Install / requirements

- Claude Code v2.1.217+ recommended (subagent cap setting), python3 3.8+.
- `opencode` CLI v2.0.19 on `PATH`, authenticated for the provider of the models in `HYBRID_OPENCODE_STD` / `HYBRID_OPENCODE_LITE`
  (see Config). With mode `claude`, or without opencode,
  hybrid-writing-plans behaves like writing-plans 6.2. In modes `hybrid` and `opencode` a missing or
  unusable opencode is reported at once as an `OC-ERROR` line (`kind=config`), and the context shows
  `opencode: unavailable ...` until `plan_tool.py doctor --ping` succeeds.
- Drop this folder where Claude Code loads skills from, alongside (not instead of) `writing-plans-6.2`
  if you want both installed. Every name this skill puts into a shared namespace carries the `hybrid` prefix
  (see Names), so it never collides with writing-plans-6.2: the Claude writer agent is
  `~/.claude/agents/hybrid-plan-task-writer.md` (installed by this skill's `setup`; a stale or placeholder copy is
  replaced, a current one is left alone), and the scratch folder is `<plan-dir>/.hybrid-work/<plan>/`.

## Run mode and presets

Each run starts by asking which mode to use (hybrid, Claude only or opencode only), unless the arguments carry `mode=hybrid|claude|opencode`. The choice is passed to `contracts` as `--preset` and frozen in `work.json`; resumed runs (`wait`, `review`, `assemble`) never ask again, and hand-offs from hybrid-brainstorming pass `mode=` along. `max`, the old name of `opencode`, still works and prints one `OC-WARN` line; any other unknown preset prints `OC-ERROR ... kind=config` and exits non-zero.

Routing is chosen per task by its contract `Tier` (`light`, `std` = no `Tier` line, `deep`) and the preset. Phase 0, Contracts and assemble always stay on Claude. The inline path (N <= 3 tasks, every body written by Claude in one Write) exists only in preset `claude`; presets `hybrid` and `opencode` always fan out, even for one task, so the bodies go to opencode.

| Preset | `light` writer | `std` writer | `deep` writer | `review_oc` | On an opencode failure |
|---|---|---|---|---|---|
| `claude` | Claude haiku | Claude sonnet | Claude opus | - (6.2 review triggers only) | opencode is never spawned |
| `hybrid` (default) | oc:`lite` | oc:`std` | Claude opus | `risky` (only oc tasks that hit a 6.2 trigger are reviewed) | OC line at once, connection errors retried 3 times, then the rest of the run switches to Claude sonnet |
| `opencode` | oc:`lite` | oc:`std` | oc:`std` | `risky` (6.2 review triggers only) | OC line at once, connection errors retried 3 times, then the unit is held and the user is asked |

## Backends

| Backend | Runs | Where |
|---|---|---|
| Claude | contracts, review, assemble, Claude-routed and fallback writers | foreground `Agent` calls |
| opencode | writers routed to `oc:<tier>` (preset `hybrid`/`opencode`) | background `plan_tool.py oc-write`, scratch in `<plan-dir>/.hybrid-work/<plan>/oc/` |

## Config

- **Shared models** (all four hybrid skills): env `HYBRID_OPENCODE_STD` (required, tier `std`) and `HYBRID_OPENCODE_LITE` (optional, tier `lite`, defaults to `HYBRID_OPENCODE_STD`), each `provider/model[#variant]`. A missing `HYBRID_OPENCODE_STD` or a value that is not `provider/model[#variant]` is reported as a config problem.
- **Shipped defaults**: `routing.default.json` - timeouts, roles and review policy. It carries no model or variant.
- **Per-skill user file** (optional): `<skill dir>/routing.json` (for example `~/.claude/skills/hybrid-writing-plans-v1.0/routing.json`), path override env `HYBRID_WRITING_PLANS_ROUTING`. Besides timeouts, roles and review policy it may set `tiers.<tier>.model` (and `variant`) to override the shared model for that one tier; a malformed file is reported as a config problem, never skipped silently.
- **Precedence** per tier (`std`, `lite`): when the per-skill file sets `tiers.<tier>.model`, that tier uses the per-skill `model` and `variant` (no variant when the file omits it; the shared variant is never mixed in); otherwise it uses the model and variant from the shared env var. `max_parallel` comes from the per-skill file, else the env var `HYBRID_OPENCODE_MAX_PARALLEL` (1 to 64), else the shipped default (4). Everything else: per-skill file over shipped defaults. The context config line and the doctor's tier lines mark each tier `(skill)` or `(shared)`.
- **Tuning keys** (shipped defaults, overridable in the per-skill file): `max_repairs` (lint-repair turns per group, default 2), `oc_group_max` (tasks per opencode group; default 3), `oc_overflow` (what happens to tasks beyond `max_parallel * oc_group_max` per tier: `"queue"`, the default, splits them into more groups of about `oc_group_max` tasks that `oc-write` runs as slots free up, in the same call; `"claude"`, mode `hybrid` only, sends the heaviest overflow tasks to Claude writers as before. Preset `opencode` always queues. Any other value is a config problem naming the file and key, and `queue` is used) and `throttle_cooldown_s` (seconds a tier stays closed to new groups and to further turns of running groups after a `throttle`; default 120).
- **`tiers.<tier>.disabled`**: `"disabled": true` in the per-skill file makes the tier unusable whatever the doctor says (routed to Claude, or held in mode `opencode`). It is not in the shipped defaults.
- **`review_oc`**: `hybrid` and `opencode` keys (`all` or `risky`; default `risky` in both, set `hybrid: "all"` to review every opencode task); `max` is still read as the old name of `opencode`. A wrong-typed `roles`, `max_roles`, `review_oc`, an `oc_overflow` that is not `queue` or `claude`, or an unknown `preset` in the per-skill file is a config problem (printed as `OC-ERROR ... kind=config`) and the shipped value stays.
- **Per run**: `mode=` / `--preset` picks the preset for one `contracts` call; a re-run without `--preset` keeps the mode frozen in `work.json`.
- `doctor` never copies the defaults into the user file; it only writes the doctor cache.

Set the variables in the `"env"` block of `~/.claude/settings.json`, then restart Claude Code (exporting them in the shell also works):

```json
{"env": {
  "HYBRID_OPENCODE_STD":  "zai-coding-plan/glm-5.3#high",
  "HYBRID_OPENCODE_LITE": "zai-coding-plan/glm-5.3-flash#low"}}
```

Each tier is an `opencode` model and thinking level (the part after `#`). The stall and wall-time timeouts (seconds) stay per skill: both apply to each opencode turn of a group, so a group's worst case is `(1 + max_repairs) × timeout_s`. `roles` in the shipped defaults maps task contract tiers to routing tiers; a second map there sends `deep` tasks to `std` in preset `opencode`. The timeouts are longer than hybrid-brainstorming's lanes because task bodies are larger, multi-step work.

## Environment variables

- `HYBRID_OPENCODE_STD=<provider/model[#variant]>` - shared model for tier `std` (required for the modes `hybrid` and `opencode`).
- `HYBRID_OPENCODE_LITE=<provider/model[#variant]>` - shared model for tier `lite` (optional, defaults to `HYBRID_OPENCODE_STD`).
- `HYBRID_OC_RETRY_DELAY_S=<seconds>` - replaces every retry delay (default 10, 30, 60); the tests set it to `0`.
- `HYBRID_WRITING_PLANS_ROUTING=<path>` - routing config path, instead of `<skill dir>/routing.json`.
- `HYBRID_WRITING_PLANS_OC_BIN=<path>` - path to the `opencode` executable (or a fake one, in tests) instead of
  resolving `opencode` on `PATH`.
- `HYBRID_WRITING_PLANS_DOCTOR_CACHE=<path>` - doctor cache path, instead of `~/.cache/hybrid-writing-plans/doctor.json`.
- `HYBRID_WRITING_PLANS_TELEMETRY=<path>` - telemetry log path, instead of `~/.cache/hybrid-writing-plans/lanes.jsonl`.

## Names

Names shared with other tools all start with `hybrid`, so this skill installs beside writing-plans-6.2 without collisions.

- Claude agent: `hybrid-plan-task-writer` (`~/.claude/agents/hybrid-plan-task-writer.md`).
- opencode agent (injected per run): `hybrid-plan-writer`.
- Env vars: `HYBRID_WRITING_PLANS_ROUTING`, `HYBRID_WRITING_PLANS_DOCTOR_CACHE`, `HYBRID_WRITING_PLANS_OC_BIN`, `HYBRID_WRITING_PLANS_TELEMETRY` (plus the shared `HYBRID_OPENCODE_*`).
- Work dir: `<plan-dir>/.hybrid-work/<plan>/` (add `.hybrid-work/` to `.gitignore` if you do not want it tracked).
- Unchanged on purpose: the skill name `hybrid-writing-plans` and the plan output path `docs/superpowers/plans/`, which the next pipeline stage reads.

## Troubleshooting

- Every opencode failure is printed at the moment it happens as `OC-ERROR <skill> <unit> tier=<tier> model=<spec> kind=<kind> :: <detail>` (or `OC-WARN` for a recovered or non-blocking event). Kinds: `spawn`, `timeout`, `stall`, `auth`, `quota`, `model`, `throttle`, `context`, `crash`, `config`, `breaker`, `switch` (errors) and `recovered`, `empty`, `format`, `grounding`, `lint`, `oracle`, `gate` (warnings; the `max` alias warning uses `config`). The lines are also kept in `<plan-dir>/.hybrid-work/<plan>/oc/oc-errors.jsonl`, which `assemble --clean` keeps.
- `plan_tool.py doctor [--ping]` - validates the shared models and the per-skill routing file, prints the config summary and one `OC-ERROR` line per config problem or failed tier, and writes the doctor cache. Only `--ping` actually checks auth (a sentinel reply). It exits 1 when opencode is missing, the config has problems or a tier failed.
- Retries: when an opencode run fails on the connection (`spawn`, `stall`, `throttle`, `crash`), `oc-write` repeats it up to 3 times, 10, 30 and 60 seconds apart, as a fresh run (not a `--session` continuation). Each failed try prints one `OC-WARN ... kind=<kind> :: retry <n>/3 in <s>s: <detail>` line; lint-repair turns are separate and unchanged. `timeout`, `context` and the gate kinds (`grounding`, `lint`, `oracle`, `gate`, `empty`, `format`, `recovered`) are not connection problems: no retry, no switch.
- Switch to Claude (mode `hybrid` only): when a group still fails after its retries, or fails with `auth`, `quota`, `model` or `config`, one `OC-ERROR ... kind=switch :: opencode <kind>: <detail>; the rest of this run uses Claude sonnet` line is printed and logged, and the rest of that run uses Claude Sonnet 5.5 (`model: sonnet`). The failed group and every group that had not started get a fallback marker with `model=sonnet` (reason `switched` for the ones that never started) and no opencode process is spawned for them; `wait` prints them as ordinary `FALLBACK` lines. Groups already running on opencode finish and are harvested normally. The switch is recorded in `<plan-dir>/.hybrid-work/<plan>/oc/oc-switched.json`, so a new `contracts` run starts unswitched.
- In mode `opencode` a failed `auth`, `quota`, `model` or `config` tier stops further attempts for the rest of the run, and a group that still fails after the retries is held; nothing switches, and you are asked what to do.
- Re-running `contracts` (after a contract edit or a reviewer's "Unfixable") keeps every opencode task body whose contract did not change and that still lints clean, including one a reviewer fixed; only groups with a pending or invalidated task get an `OPENCODE` row, and `oc-write` never rewrites a finished body. A doctor cache that expires in the middle of a run does not move a tier to Claude; a real failed check does.
- Stopping `oc-write` with SIGTERM also stops its opencode runs (their process groups); `wait` then reports the unfinished tasks as `runner-died`.
- A connection retry of a lint-repair turn is a fresh run that re-sends the brief plus the repair message (never `--session`).
- A group held at runtime (mode `opencode`) ends every later `wait` with exit 3, like one held by `contracts`.
- A task stuck with no progress - the `stall` timeout escalates it after the threshold for its tier; you never need to intervene by hand.
- Lint failures - if a group's output cannot pass the linter, its failed tasks fall back to Claude once automatically (mode `hybrid`).
- Execution Handoff: after `assemble`, mode `hybrid` or `opencode` offers `hybrid-team` (args `<plan> mode=<mode>`), mode `claude` offers `dev-team`.

## GLM Coding Plan note

The example tiers use the `zai-coding-plan` provider. While that GLM Coding Plan is expired, opencode replies with an error such as "Your GLM Coding Plan package has expired and is temporarily unavailable"; the run is reported at once as an `OC-ERROR` line (`kind=quota` or `kind=auth`), the tier stops being tried, and the rest of the run switches to Claude sonnet (mode `hybrid`) or the tasks are held (mode `opencode`). Until the plan is renewed, set `HYBRID_OPENCODE_STD` and `HYBRID_OPENCODE_LITE` to a working model (for example `google/gemini-3.1-flash-lite`), and remove any `model` in the per-skill file that overrides it.

## Differences from writing-plans-6.2

- New `scripts/oc_run.py`: the vendored opencode runner module (a library, opencode only).
- New backend router (`routing.default.json` / user routing file) decides Claude vs. opencode per
  task from its contract `Tier` and the preset (`--preset`).
- New failure handling for opencode writers (spawn, crash, stall, timeout, auth, quota, model, config, throttle,
  context, empty, format, lint) with lint-repair turns in the same opencode session and one Claude fallback per failed group.
- Same gate as 6.2: opencode-written task bodies must pass plan_tool's existing linter before they count.
- SKILL.md frontmatter changes: `name: hybrid-writing-plans` and an opt-in description; `allowed-tools`
  stays `Bash(python3 *)`, as in writing-plans-6.2.
- Telemetry appended to `~/.cache/hybrid-writing-plans/lanes.jsonl` (`HYBRID_WRITING_PLANS_TELEMETRY`): one group record per
  opencode group (task IDs, tier, model, variant, rounds, outcome, reason, duration, tokens) and one review
  record per reviewed task from `wait --review` (whether review fixed it), summarised by `plan_tool.py stats`.
- Shared models from env vars for the four hybrid skills, a run-mode question at the start, preset `opencode` (alias `max`), and immediate `OC-ERROR` / `OC-WARN` reporting with a held state instead of a silent fallback in mode `opencode`.
- Preset `claude` follows writing-plans-6.2 (same contract rules and linter); `tests/test_lint_parity.py` runs both linters over the same bodies.
- The plan text must not mention opencode. The shared linter does not scan for that word, so the writer and reviewer briefs forbid it and a reviewer removes any hit.
