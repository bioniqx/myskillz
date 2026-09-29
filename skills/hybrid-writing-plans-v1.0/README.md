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

A task whose output cannot pass the linter falls back to Claude once. This cuts Claude
token spend on task bodies without changing the planning contract.

## Install / requirements

- Claude Code v2.1.217+ recommended (subagent cap setting), python3 3.8+.
- `opencode` CLI v2.0.18 on `PATH`, authenticated for the providers in your routing config.
  Without it, hybrid-writing-plans still works: with no doctor cache every task routes to Claude, and
  the context shows `opencode: unavailable → preset claude (run plan_tool.py doctor --ping)`.
- Drop this folder where Claude Code loads skills from, alongside (not instead of) `writing-plans-6.2`
  if you want both installed. The injected opencode agent is `hp-writer`. Both skills share the Claude
  writer agent `~/.claude/agents/plan-task-writer.md`: this skill's `setup` installs it only when it is
  missing and never overwrites it, so an existing copy may still run writing-plans-6.2's `hook-lint`.
  That is safe because the linter is identical and `assemble` re-lints every task with this skill's linter.

## Presets

Routing is chosen per task by its contract `Tier` (`light`, `std` = no `Tier` line, `deep`) and the preset
(routing file `preset`, or `--preset claude|hybrid|max` passed to `contracts`). Phase 0, Contracts, the
inline path and assemble always stay on Claude.

| Preset | `light` writer | `std` writer | `deep` writer | `review_oc` |
|---|---|---|---|---|
| `claude` | Claude haiku | Claude sonnet | Claude opus | - (6.2 review triggers only) |
| `hybrid` (default) | oc:`lite` | oc:`std` | Claude opus | `all` (every oc task is reviewed) |
| `max` | oc:`lite` | oc:`std` | oc:`std` | `risky` (6.2 review triggers only) |

## Backends

| Backend | Runs | Where |
|---|---|---|
| Claude | contracts, review, assemble, Claude-routed and fallback writers | foreground `Agent` calls |
| opencode | writers routed to `oc:<tier>` (preset `hybrid`/`max`) | background `plan_tool.py oc-write`, scratch in `<plan-dir>/.work/<plan>/oc/` |

## Config

- **Shipped defaults**: `hybrid-writing-plans-v1.0/routing.default.json`.
- **User file**: `~/.config/hybrid-writing-plans/routing.json` - created by `doctor` from the
  defaults if missing; edit it to change models, variants or slot counts. Override the path with
  env `HP_ROUTING=<path>`.
- **Per run**: `--preset claude|hybrid|max` overrides the file's `preset` for one `contracts` call.

```json
{"preset": "hybrid",
 "tiers": {
   "std":  {"model": "zai-coding-plan/glm-5.3",       "variant": "high", "max_parallel": 6,
            "stall_s": 180, "timeout_s": 900},
   "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low",  "max_parallel": 6,
            "stall_s": 120, "timeout_s": 600}},
 "roles": {"light": "lite", "std": "std", "deep": "claude"},
 "max_roles": {"deep": "std"},
 "review_oc": {"hybrid": "all", "max": "risky"},
 "oc_group_max": 3, "max_repairs": 2, "throttle_cooldown_s": 120}
```

`preset` selects the routing behaviour (`claude`, `hybrid`, `max` - see `SKILL.md`). `tiers` maps a tier
name to an `opencode` model (`provider/model`), a `variant` (the thinking level), a `max_parallel` slot cap,
a stall timeout and a wall-time timeout in seconds. Both apply to each opencode turn of a group, so a
group's worst case is `(1 + max_repairs) × timeout_s`. `roles` maps task contract tiers to routing tiers in the
active preset; `max_roles` overrides them for the `max` preset only. Users may add tiers and point roles at
them. The timeouts are longer than hybrid-brainstorming's lanes because task bodies are larger, multi-step work.

## Environment variables

- `HP_ROUTING=<path>` - routing config path, instead of `~/.config/hybrid-writing-plans/routing.json`.
- `HP_OC_BIN=<path>` - path to the `opencode` executable (or a fake one, in tests) instead of
  resolving `opencode` on `PATH`.
- `HP_DOCTOR_CACHE=<path>` - doctor cache path, instead of `~/.cache/hybrid-writing-plans/doctor.json`.
- `HP_TELEMETRY=<path>` - telemetry log path, instead of `~/.cache/hybrid-writing-plans/lanes.jsonl`.

## Troubleshooting

- `plan_tool.py doctor [--ping]` - reports whether the routing file parses and prints the context status
  line. Only `--ping` actually checks auth (a sentinel reply); a plain `doctor` run records availability
  without probing. Without opencode, every task routes to Claude automatically; nothing to fix before a run,
  only before you want the cost savings back.
- A task stuck with no progress - `stall` timeout will escalate it back to Claude after the threshold
  for its tier elapses; you never need to intervene by hand.
- Lint failures - if a task's output cannot pass the linter, it falls back to Claude once automatically.
- Opencode unavailable - `doctor` detects it is missing and reports the issue. `plan_tool.py` continues with
  Claude for all writers; nothing breaks, only cost savings are foregone.

## GLM Coding Plan note

The shipped tiers use the `zai-coding-plan` provider. While that GLM Coding Plan is expired, opencode
replies with an error such as "Your GLM Coding Plan package has expired and is temporarily unavailable";
the run is classed `unavailable`, the tier is marked down in the doctor cache and its tasks fall back to
Claude. `plan_tool.py doctor --ping` proves this path. Until the plan is renewed, point both tiers of your
user routing file at a working model (for example `google/gemini-3.1-flash-lite`).

## Differences from writing-plans-6.2

- New `scripts/oc_run.py`: the vendored opencode runner module (a library, opencode only).
- New backend router (`routing.default.json` / user routing file) decides Claude vs. opencode per
  task from its contract `Tier` and the preset (`--preset`).
- New failure handling for opencode writers (spawn, crash, stall, timeout, unavailable, throttle, format,
  lint) with lint-repair turns in the same opencode session and one Claude fallback per failed group.
- Same gate as 6.2: opencode-written task bodies must pass plan_tool's existing linter before they count.
- SKILL.md frontmatter changes: `name: hybrid-writing-plans` and an opt-in description; `allowed-tools`
  stays `Bash(python3 *)`, as in writing-plans-6.2.
- Telemetry appended to `~/.cache/hybrid-writing-plans/lanes.jsonl` (`HP_TELEMETRY`): one group record per
  opencode group (task IDs, tier, model, variant, rounds, outcome, reason, duration, tokens) and one review
  record per reviewed task from `wait --review` (whether review fixed it), summarised by `plan_tool.py stats`.
- Preset `claude` reproduces writing-plans-6.2's behaviour exactly.
