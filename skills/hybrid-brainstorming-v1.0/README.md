# hybrid-brainstorming

A fork of `brainstorming-6.3` that keeps every judgment step on Claude and offloads
low-judgment exploration lanes to the local `opencode` CLI, with a configurable model and
thinking level per tier. Read `SKILL.md` for how brainstorming drives it; this file covers
installation, configuration and troubleshooting.

## Why

Claude decides and synthesizes. The cheap model only fetches facts, and each fact must pass a
mechanical grounding check before it reaches the main thread:
- A code finding must cite a `path:line` that exists.
- A web claim must quote text that really appears in what the lane fetched.

A lane whose output cannot be grounded falls back to Claude once. This cuts Claude token spend
on exploration lanes without changing the brainstorming contract.

## Install / requirements

- Claude Code >= 2.1.267, git >= 2.31, python3.
- `opencode` CLI v2.0.18 on `PATH`, authenticated for the providers in your routing config.
  Without it, hybrid-brainstorming still works - `doctor` detects it is missing and routes every lane to
  Claude with one NOTE.
- Drop this folder where Claude Code loads skills from, alongside (not instead of) `brainstorming-6.3`
  if you want both installed: the only injected agent is `hb-lane`, and the skill's own name and
  state directory differ from `brainstorming-6.3`'s, so the two skills never collide.

## Presets

| Preset | `locate`/`explore` | `fact` | `research`/`draft` |
|---|---|---|---|
| `claude` | Claude | Claude | Claude |
| `hybrid` (default) | opencode | opencode | Claude |
| `max` | opencode | opencode | opencode, but `research` only while `websearch=on` (falls back to Claude when `websearch=off`) |

## Backends

| Backend | Runs | Where |
|---|---|---|
| Claude | main thread (classify, T0, synthesis, design, spec, self-review), draft lanes, research lanes (in preset `claude` or `hybrid`), claim verifier, spec pre-draft | Claude Code background |
| opencode | Code lanes (roles `locate`, `explore`), web lanes (role `fact`, in preset `hybrid`/`max`), draft/research lanes (in preset `max` only) | `.superpowers/brainstorm/lanes/<id>` via `bslane.py` |

## Config

- **Shipped defaults**: `hybrid-brainstorming-v1.0/routing.default.json`.
- **User file**: `~/.config/hybrid-brainstorming/routing.json` - created by `doctor` from the
  defaults if missing; edit it to change models, variants or slot counts. Override the path with
  env `HB_ROUTING=<path>`.
- **Per lane**: a `--backend` flag overrides routing for that call.

```json
{"preset": "hybrid",
 "tiers": {
   "std":  {"model": "zai-coding-plan/glm-5.3",       "variant": "high", "max_parallel": 6,
            "stall_s": 90, "timeout_s": 300},
   "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low",  "max_parallel": 6,
            "stall_s": 60, "timeout_s": 180}},
 "roles": {"locate": "lite", "explore": "std", "fact": "lite", "research": "claude", "draft": "claude"},
 "max_roles": {"research": "std", "draft": "std"},
 "slot_wait_s": 60, "throttle_cooldown_s": 120}
```

`preset` selects the routing behaviour (`claude`, `hybrid`, `max` - see `SKILL.md`). `tiers` maps a tier
name to an `opencode` model (`provider/model`), a `variant` (the thinking level), a `max_parallel` slot cap,
a stall timeout in seconds and a timeout in seconds for each lane run. `roles` maps roles to tiers in the
active preset; `max_roles` overrides them for the `max` preset only. Users may add tiers and point roles at
them. The timeouts are shorter than hybrid-team's because lanes answer a single question.

## Environment variables

- `HB_ROUTING=<path>` - routing config path, instead of `~/.config/hybrid-brainstorming/routing.json`.
- `HB_OC_BIN=<path>` - path to the `opencode` executable (or a fake one, in tests) instead of
  resolving `opencode` on `PATH`.
- `HB_DOCTOR_CACHE=<path>` - doctor cache path, instead of `~/.cache/hybrid-brainstorming/doctor.json`.

## Troubleshooting

- `bslane.py doctor [--ping]` - reports whether the routing file parses and prints the context status
  line. Only `--ping` actually checks auth (a sentinel reply) and web search; a plain `doctor` run
  records `websearch=off` without probing it. Without opencode, every lane routes to Claude
  automatically; nothing to fix before a run, only before you want the cost savings back.
- A lane stuck with no progress - `stall` timeout will escalate it back to Claude after the threshold
  for its tier elapses; you never need to intervene by hand.
- Grounding failures - if a lane's output cannot be verified as grounded (code path exists, web quote
  verified), it falls back to Claude once automatically.
- `websearch=off` - opencode asks once, interactively, to allow a search provider; that prompt is
  cancelled in a background run, so a plain `doctor` run records `websearch=off`. Fix: open the
  `opencode` TUI once and allow web search, then re-run `bslane.py doctor --ping` - only `--ping`
  actually checks auth (via a sentinel reply) and web search, so a plain `doctor` run cannot confirm
  the fix. Until then, `research` lanes route to Claude even in preset `max`; `fact` lanes still work
  through webfetch.
- Prompt-free wide fan-outs - add the settings allow rule
  `Bash(python3 "<skill dir>/scripts/bslane.py":*)` so background lanes don't hit a permission prompt.

## Differences from brainstorming-6.3

- New `bslane.py` CLI runs lanes via opencode or Claude depending on routing.
- New backend router (`routing.default.json` / user routing file) decides Claude vs. opencode per
  lane from its role, or a lane's own `--backend` flag.
- New failure handling for opencode lanes (stall, timeout, throttle, crash, spawn) with automatic
  escalation back to Claude.
- New grounding gate: code and web findings must cite a real `path:line` or web quote before they
  reach the main thread.
- SKILL.md frontmatter changes: `name: hybrid-brainstorming`, an opt-in description, and
  `allowed-tools` that add the `bslane.py` pin.
- Telemetry: one JSON line per lane appended to `<root>/.superpowers/brainstorm/lanes.jsonl`
  with role, tier, model, variant, duration, tokens, grounded `n/m`, outcome and reason - no cost field.
- Preset `claude` reproduces brainstorming-6.3's behaviour exactly.
