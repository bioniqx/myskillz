# hybrid-requirements-code-audit

An opt-in fork of `requirements-code-audit` that keeps every judgment step on Claude and offloads the
evidence legwork (investigators; in mode `opencode` also verifiers and parsers) to the local `opencode` CLI.
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

Honest gain: `hybrid` cuts request and usage-limit pressure a lot and Claude cost moderately. `opencode` cuts the most, but then the safety net (verifiers) runs on opencode too and nothing falls back to Claude.

## Install / requirements

- python3 3.8+ (stdlib only).
- `opencode` CLI v2.0.18 on `PATH` for modes `hybrid` and `opencode`, authenticated for the providers of your
  `HYBRID_OPENCODE_STD` / `HYBRID_OPENCODE_LITE` models. Without it the audit runs as mode `claude`.
- Runs in Claude Code or Cowork, like the original.
- Reuses the installed `req-audit` plugin's `rca-*` agents and guard hook; this skill ships no agents,
  hooks or plugin manifest of its own. Without the plugin it falls back to generic mode
  (`general-purpose` subagents).
- One-time check: `python3 scripts/audit.py doctor --ping`.

## Modes

SKILL.md asks for the mode once per audit (or takes `mode=hybrid|claude|opencode` from its arguments) and passes it as `init --preset`.

| Mode (`preset`) | Investigators | Verifiers | Parsers | On an opencode failure |
|---|---|---|---|---|
| `claude` | Claude haiku | Claude sonnet | Claude sonnet (identical to requirements-code-audit) | opencode is never called |
| `hybrid` (default) | `oc:std` (overflow → Claude haiku) | Claude sonnet | Claude sonnet | connection failures are retried 3 times; then the line is shown at once, the batch falls back to Claude and the rest of the run switches to Claude sonnet |
| `opencode` | `oc:std`, no Claude overflow | `oc:std` | `oc:std` | connection failures are retried 3 times; then the line is shown at once and the unit is held: retry / run on Claude / switch to hybrid / abort |

The lead's work (init, checklist, faithfulness pass, adjudication, `plan.jsonl`, report, check, finish) is Claude in every mode. `max` is a deprecated alias of `opencode`; workflow mode requires mode `claude`. Every MISSING, PARTIAL or CONFLICT verdict an opencode verifier gives goes to Claude adjudication (it is listed in the queue and `check` flags it until adjudicated), in every mode. Tier health is frozen when the audit starts: `init` pings once when the doctor cache is missing or stale for the tiers its mode uses (or prints an `OC-ERROR`), and later commands never downgrade a tier because the cache aged; `status --retry` re-pings and closes the breaker of a tier that answers.

## Backends

| Backend | Runs | Where |
|---|---|---|
| Claude | lead, Claude-routed roles, hedges, fallbacks | Agent-tool subagents (`req-audit:rca-*`, or `general-purpose` in generic mode), as in the original |
| opencode | batches routed to `oc:<tier>` (mode `hybrid`/`opencode`) | one background Bash process per batch: `python3 "<scripts_dir>/audit.py" oc-run <name>`, printed in the `OPENCODE` block after the `DISPATCH` blocks |

The lead runs `audit.py status` on every completion notification (Agent or background Bash). Hedges and
fallbacks always go to Claude with the role's model (`sonnet` once the run has switched, see Troubleshooting).

## Config

- **Shared models**: two env vars for all four hybrid skills, each `provider/model[#variant]` (`#variant` is the optional thinking level): `HYBRID_OPENCODE_STD` (required, tier `std`) and `HYBRID_OPENCODE_LITE` (optional, tier `lite`, defaults to the `std` value). Set them in the `"env"` block of `~/.claude/settings.json`, for example `{"env": {"HYBRID_OPENCODE_STD": "opencode/muse-spark-1.3-contributor-free#xhigh"}}`, then restart Claude Code; exporting them in the shell also works. An unset or invalid variable is reported as `OC-ERROR ... kind=config` and makes modes `hybrid` and `opencode` unusable; mode `claude` never reads them. `max_parallel` is not shared: it comes from the routing file.
- **Shipped defaults**: `hybrid-requirements-code-audit-v1.0/routing.default.json` (roles, batch sizes, timeouts; no model).
- **User file** (optional): `<skill dir>/routing.json` (next to `routing.default.json`, e.g. `~/.claude/skills/hybrid-requirements-code-audit-v1.0/routing.json`), deep-merged over the defaults (env `HA_ROUTING`). The skill never creates it. A `tiers.<tier>.model` in it overrides the shared model for that tier (with this file's own `variant`); tiers without one use the shared env vars.
- **Per audit**: `init --preset claude|hybrid|opencode` overrides the file's `preset`.

Keys of the routing file:

- `max_parallel` - opencode processes per tier; in mode hybrid items beyond that capacity stay on Claude at `plan` time.
- `oc_batch_max` - items per opencode batch. `max_repairs` - repair turns per batch (same opencode session).
- `stall_s` / `timeout_s` - stall and wall-time limits per turn, so a batch's worst case is `(1 + max_repairs) × timeout_s`.
- `throttle_cooldown_s` - how long a throttled tier waits or stays on Claude.
- `roles` maps each role to a tier (or `claude`) in mode `hybrid`; `max_roles` does the same in mode `opencode`. Users may add tiers and point `roles`/`max_roles` at them.

## Environment variables

- `HYBRID_OPENCODE_STD=<provider/model[#variant]>` - shared model of tier `std` (required for modes `hybrid` and `opencode`).
- `HYBRID_OPENCODE_LITE=<provider/model[#variant]>` - shared model of tier `lite` (default: the `HYBRID_OPENCODE_STD` value).
- `HA_OC_BIN=<path>` - the `opencode` executable (default `opencode`).
- `HYBRID_OC_RETRY_DELAY_S=<seconds>` - replaces the 10/30/60 s waits between retries (tests use `0`).
- `HA_ROUTING=<path>` - user routing file (default `<skill dir>/routing.json`).
- `HA_DOCTOR_CACHE=<path>` - doctor cache (default `~/.cache/hybrid-requirements-code-audit/doctor.json`).
- `HA_TELEMETRY=<path>` - telemetry log (default `~/.cache/hybrid-requirements-code-audit/lanes.jsonl`).
- `HA_FAKE_SCRIPT`, `HA_FAKE_LOG` - for the test fake only.

## Troubleshooting

- `init` prints an `opencode:` status line with the version, mode and each role's backend. With no usable doctor entry it prints `opencode: unavailable preset=<preset> (run audit.py doctor --ping)`.
- `audit.py doctor [--ping]` - validates the shared env vars, checks the binary and its version and whether each tier's model is listed; only `--ping` actually probes auth with a sentinel reply. Results go to the doctor cache, and every unusable tier prints as an `OC-ERROR` line. It never creates a config file.
- Every opencode failure prints as `OC-ERROR <skill> <unit> tier=<tier> model=<spec> kind=<kind> :: <detail>` (or `OC-WARN`) the moment it happens, and is also appended to `<audit dir>/oc-errors.jsonl`; `status` shows the lines nobody has seen yet before anything else. Kinds: `spawn`, `timeout`, `stall`, `auth`, `quota`, `model`, `throttle`, `context`, `crash`, `config`, `breaker`, `switch`; warnings: `recovered`, `empty`, `format`, `grounding`, `lint`, `oracle`, `gate`.
- Retries: a run that fails with `spawn`, `stall`, `throttle` or `crash` is repeated up to 3 times as a fresh run (waits of 10 s, 30 s and 60 s; `HYBRID_OC_RETRY_DELAY_S=<seconds>` overrides them, tests set it to 0). Each failed try prints `OC-WARN ... kind=<kind> :: retry <n>/3 in <s>s: <detail>`. `timeout`, `context` and the warning kinds are never retried. Repair turns for `format` failures are separate and unchanged.
- Switch (mode hybrid only): when the retries are used up, or at once for `auth`, `quota`, `model` and `config`, one `OC-ERROR ... kind=switch :: opencode <kind>: <detail>; the rest of this run uses Claude sonnet` line is printed and logged, and the record `<audit dir>/oc-switched.json` is written. The failed batch falls back to Claude on `model: sonnet`, and every later unit that would have gone to opencode (investigators, verifiers, parsers) is dispatched to Claude on `sonnet` with no `OPENCODE` block; running opencode batches finish and are harvested normally, and a late `oc-run` exits 3 as `FALLBACK (switched)` without spawning. A new `init` starts unswitched. Mode `opencode` never switches: after the retries the unit is held as before.
- `auth`, `quota`, `model` and `config` failures open the run's circuit breaker: the tier is skipped without spawning opencode, and `status` prints one `kind=breaker` summary when a wave ends.
- `FALLBACK <name> (<reason>)` lines from `status` / `parse-merge` (mode hybrid) mean a failed opencode batch went to Claude once. Reasons: `spawn`, `crash`, `stall`, `timeout`, `auth`, `quota`, `model`, `throttle`, `format` (ids missing or no parsable block after the last repair), `cooldown` (tier in throttle cooldown), `breaker` (breaker open), `switched` (the run already moved to Claude).
- In mode opencode nothing falls back: a `NEXT:` line says how many units are held. Answer with `status --retry all`, `status --to-claude investigator|verifier`, `parse-merge --to-claude` or `status --mode hybrid`.
- `oc-run` exits 3 when its batch failed. Raw opencode output is kept in `<out>/oc/`: `<name>.<round>.jsonl` (events) and `<name>.<round>.err`.
- `audit.py stats [--repo <path>]` summarises telemetry.

## Differences from requirements-code-audit

- New `routing.default.json`, the shared env-var models and an optional `routing.json` next to it.
- New modules: `scripts/oc_run.py` (vendored runner), `ha_router.py`, `ha_config.py`, `ha_briefs.py`,
  `ha_doctor.py`, `ha_oracle.py`, `ha_partition.py`, `ha_run.py`, `ha_dispatch.py`, `ha_telemetry.py`.
- New commands `oc-run`, `doctor`, `stats` and flag `init --preset`.
- Run modes `claude`, `hybrid` and `opencode`, asked once by SKILL.md, with held units in mode `opencode`.
- Immediate `OC-ERROR` / `OC-WARN` lines, `oc-errors.jsonl` and a per-run circuit breaker.
- Three retries of connection failures, then (mode hybrid) a run-wide switch to Claude sonnet.
- `backend` keys in state, findings and verdict rows; per-backend slot accounting.
- One Claude fallback per failed opencode batch.
- The `- Backends:` report line.
- With preset `claude` the output is byte-identical to the original.
