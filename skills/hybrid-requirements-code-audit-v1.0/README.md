# hybrid-requirements-code-audit

An opt-in fork of `requirements-code-audit` that keeps every judgment step on Claude and offloads the
evidence legwork (investigators; in preset `max` also verifiers and parsers) to the local `opencode` CLI.
The `.audit/` layout, schemas, report and traceability CSV are the same as the original. Read `SKILL.md`
for how `audit.py` drives an audit; this file covers installation, configuration and troubleshooting.

## Why

Claude writes the checklist, adjudicates and writes the remediation plan. The cheap model only gathers
evidence for requirements the checklist already fixes, and every opencode row passes a deterministic
oracle before it counts:
- Foreign ids (not in the batch) are removed.
- An invalid status becomes `UNSEARCHED`.
- Citations outside the repo, under `.git`, in doc paths or failing the evidence check are dropped, and
  the row is demoted to `confidence: low`.

Every non-MATCHED, low-confidence or high-stakes item still goes through Wave B (verifiers).

Honest gain: `hybrid` cuts request and usage-limit pressure a lot and Claude cost moderately. `max` cuts
the most, but then the safety net (verifiers) runs on GLM too.

## Install / requirements

- python3 3.8+ (stdlib only).
- `opencode` CLI v2.0.18 on `PATH` for presets `hybrid` and `max`, authenticated for the providers in your
  routing config. Without it the audit runs as preset `claude`.
- Runs in Claude Code or Cowork, like the original.
- Reuses the installed `req-audit` plugin's `rca-*` agents and guard hook; this skill ships no agents,
  hooks or plugin manifest of its own. Without the plugin it falls back to generic mode
  (`general-purpose` subagents).
- One-time check: `python3 scripts/audit.py doctor --ping`.

## Presets

| Preset | Investigators | Verifiers | Parsers |
|---|---|---|---|
| `claude` | Claude haiku | Claude sonnet | Claude sonnet (identical to requirements-code-audit) |
| `hybrid` (default) | `oc:std` (overflow → Claude haiku) | Claude sonnet | Claude sonnet |
| `max` | `oc:std` (overflow → Claude haiku) | `oc:std` (overflow → Claude sonnet) | `oc:std` (overflow → Claude sonnet) |

The lead's work (init, checklist, faithfulness pass, adjudication, `plan.jsonl`, report, check, finish)
is Claude in every preset. Select per audit with `init --preset claude|hybrid|max`; workflow mode
requires `--preset claude`.

## Backends

| Backend | Runs | Where |
|---|---|---|
| Claude | lead, Claude-routed roles, hedges, fallbacks | Agent-tool subagents (`req-audit:rca-*`, or `general-purpose` in generic mode), as in the original |
| opencode | batches routed to `oc:<tier>` (preset `hybrid`/`max`) | one background Bash process per batch: `python3 "<scripts_dir>/audit.py" oc-run <name>`, printed in the `OPENCODE` block after the `DISPATCH` blocks |

The lead runs `audit.py status` on every completion notification (Agent or background Bash). Hedges and
fallbacks always go to Claude with the role's model.

## Config

- **Shipped defaults**: `hybrid-requirements-code-audit-v1.0/routing.default.json`.
- **User file**: `~/.config/hybrid-requirements-code-audit/routing.json` - created by `doctor` if missing,
  deep-merged over the defaults (dicts merge recursively, other values replace). Override the path with
  env `HA_ROUTING=<path>`.
- **Per audit**: `init --preset claude|hybrid|max` overrides the file's `preset`.

```json
{"preset": "hybrid",
 "tiers": {
   "std":  {"model": "zai-coding-plan/glm-5.3",       "variant": "high", "max_parallel": 6,
            "stall_s": 180, "timeout_s": 900},
   "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low",  "max_parallel": 6,
            "stall_s": 120, "timeout_s": 600}},
 "roles": {"investigator": "std", "verifier": "claude", "parser": "claude"},
 "max_roles": {"verifier": "std", "parser": "std"},
 "oc_batch_max": 4, "max_repairs": 2, "throttle_cooldown_s": 120}
```

- `variant` - the thinking level, passed as the `#<variant>` model suffix.
- `max_parallel` - opencode processes per tier; items beyond that capacity stay on Claude at `plan` time.
- `oc_batch_max` - items per opencode batch.
- `max_repairs` - repair turns per batch (same opencode session).
- `stall_s` / `timeout_s` - stall and wall-time limits per turn, so a batch's worst case is
  `(1 + max_repairs) × timeout_s`.
- `throttle_cooldown_s` - how long a throttled tier stays on Claude.
- `roles` maps each role to a tier (or `claude`) in preset `hybrid`; `max_roles` overrides it in preset
  `max`. Users may add tiers and point `roles`/`max_roles` at them.

## Environment variables

- `HA_OC_BIN=<path>` - the `opencode` executable (default `opencode`).
- `HA_ROUTING=<path>` - user routing file (default `~/.config/hybrid-requirements-code-audit/routing.json`).
- `HA_DOCTOR_CACHE=<path>` - doctor cache (default `~/.cache/hybrid-requirements-code-audit/doctor.json`).
- `HA_TELEMETRY=<path>` - telemetry log (default `~/.cache/hybrid-requirements-code-audit/lanes.jsonl`).
- `HA_FAKE_SCRIPT`, `HA_FAKE_LOG` - for the test fake only.

## Troubleshooting

- `init` prints an `opencode:` status line with the version, preset and each role's backend. With no
  usable opencode it prints `opencode: unavailable → preset claude (run audit.py doctor --ping)`.
- `audit.py doctor [--ping]` - checks the binary and its version and whether each tier's
  model is listed (an unreadable user routing file is ignored and the defaults are used); only `--ping` actually probes auth with a sentinel reply. Results go
  to the doctor cache.
- `FALLBACK <name> (<reason>)` lines from `status` / `parse-merge` mean a failed opencode batch went to
  Claude once. Reasons: `spawn`, `crash`, `stall`, `timeout`, `unavailable`, `throttle`, `format`
  (ids missing or no parsable block after the last repair), `down` (tier marked down before spawning),
  `cooldown` (tier in throttle cooldown).
- Raw opencode output is kept in `<out>/oc/`: `<name>.<round>.jsonl` (events) and `<name>.<round>.err`.
- `audit.py stats [--repo <path>]` summarises telemetry.

## GLM Coding Plan note

The shipped tiers use the `zai-coding-plan` provider. While that GLM Coding Plan is expired, opencode
replies with an "expired" error; the run is classed `unavailable` (checked before throttling), the tier is
marked down in the doctor cache and its batches fall back to Claude. `audit.py doctor --ping` proves this
path. Until the plan is renewed, point the tiers of your user routing file at a working model.

## Differences from requirements-code-audit

- New `routing.default.json` plus the user routing file.
- New modules: `scripts/oc_run.py` (vendored runner), `ha_router.py`, `ha_config.py`, `ha_briefs.py`,
  `ha_doctor.py`, `ha_oracle.py`, `ha_partition.py`, `ha_run.py`, `ha_dispatch.py`, `ha_telemetry.py`.
- New commands `oc-run`, `doctor`, `stats` and flag `init --preset`.
- `backend` keys in state, findings and verdict rows; per-backend slot accounting.
- One Claude fallback per failed opencode batch.
- The `- Backends:` report line.
- With preset `claude` the output is byte-identical to the original.
