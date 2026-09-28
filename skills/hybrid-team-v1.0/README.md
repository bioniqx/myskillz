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
- `opencode` CLI v2.0.18 on `PATH`, authenticated for the providers in your routing config.
  Without it, hybrid-team still works - `doctor` detects it is missing and routes every slice to
  Claude with one NOTE.
- Drop this folder where Claude Code loads skills from, alongside (not instead of) `dev-team-v3.2`
  if you want both installed: agents are namespaced `ht-*` and state lives under
  `.claude/hybrid-team/`, so the two skills never collide.

## Backends

| Backend | Runs | Where |
|---|---|---|
| Claude | planning, all reviews, verification, investigators, RED, `research`/`perf`, anything the router can't offload | Claude Code subagents, background |
| opencode | GREEN of small/trivial `code`, `refactor`, `test` backfill, non-large `chore`, `docs` | `.claude/worktrees/oc-<id>` via the `lane` command |

## Config

- **Shipped defaults**: `hybrid-team-v1.0/routing.default.json`.
- **User file**: `~/.config/hybrid-team/routing.json` - created by `doctor --fix` from the
  defaults if missing; edit it to change models, variants or slot counts. Override the path with
  env `HT_ROUTING=<path>`.
- **Per run**: the plan JSON's `routing` block overrides keys for that run only.
- **Per slice**: a slice's `backend` field pins it directly, bypassing the routing table.

    {"preset": "hybrid",
     "tiers": {
       "std":  {"model": "zai-coding-plan/glm-5.3",       "variant": "high", "max_parallel": 6,
                "stall_s": 180, "timeout_s": {"trivial": 600, "small": 1200, "large": 2400}},
       "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low",  "max_parallel": 6,
                "stall_s": 120, "timeout_s": {"trivial": 300, "small": 600, "large": 1200}}},
     "escalate_to": "claude", "max_escalations": 1}

`preset` selects the row table (`claude`, `hybrid`, `max` - see `SKILL.md`). `tiers` maps a tier
name to an `opencode` model (`provider/model`), a `variant` (the thinking level, passed as the
`#<variant>` model suffix), a `max_parallel` slot cap, a stall timeout in seconds and a per-`size`
run timeout. `rows` (present in `routing.default.json`, omitted above for brevity) maps the table
rows `code`, `refactor`, `test`, `chore`, `docs`, `trivial` to a tier name, so you can point any row
at a tier you added - e.g. a `kimi` tier running `moonshotai/kimi-k2.7-code`. `escalate_to` and
`max_escalations` control what happens when a lane can't be resumed (see `SKILL.md`'s failure
table); the shipped default is one escalation to Claude, then the normal BLOCKED flow.

## Environment variables

- `HT_ROUTING=<path>` - routing config path, instead of `~/.config/hybrid-team/routing.json`.
- `HT_OC_BIN=<path>` - path to the `opencode` executable (or a fake one, in tests) instead of
  resolving `opencode` on `PATH`.

## Troubleshooting

- `devteam doctor` - reports whether opencode is reachable and authenticated
  (`oc_available(root: Path, routing: dict) -> bool` is the check it runs internally), whether the
  routing file parses, and whether `.claude/settings.local.json` has the concurrency/timeout limits
  hybrid-team needs. `doctor --fix` writes anything missing.
- opencode missing or auth broken -> every slice routes to Claude automatically; nothing to fix
  before a run, only before you want the cost savings back.
- A lane stuck with no progress -> `devteam next` escalates it itself once the stall timeout for its
  tier elapses; you never need to intervene by hand.
- `bash hybrid-team-v1.0/scripts/selftest.sh` - the self-check; on macOS 6 known failures are
  expected (GNU `sed -i`, `/var` -> `/private/var`, a bash 3.2 word-split) and match dev-team's
  baseline exactly.

## Differences from dev-team-v3.2

- New `lane <id>` engine subcommand runs one opencode-backed slice to completion (or a blocked
  marker) inside its own worktree.
- New backend router (`routing.default.json` / user routing file) decides Claude vs. opencode per
  slice from its `kind`/`size`/`risk`, or a slice's own `backend` field.
- New failure handling for opencode lanes (stall, timeout, throttle, crash, spawn) with escalation
  back to Claude.
- `devteam stats` reports token/cost split by backend and tier in addition to dev-team's slice
  counts.
- Everything else - plan format, profiles, merge/`integrate`, guards, checkpoints, review cadence -
  is identical to dev-team-v3.2. Preset `claude` reproduces dev-team-v3.2's behaviour exactly.
