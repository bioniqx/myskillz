# hybrid-brainstorming

A fork of `brainstorming-6.3` that keeps every judgment step on Claude and offloads
low-judgment exploration lanes to the local `opencode` CLI. Every run starts with a run-mode
choice, and the opencode models come from two env vars shared by all hybrid skills; this skill's own
routing file can override the model of a tier. Read `SKILL.md` for how brainstorming drives it;
this file covers installation, configuration and troubleshooting.

## Why

Claude decides and synthesizes. The cheap model only fetches facts, and each fact must pass a
mechanical grounding check before it reaches the main thread:
- A code finding must cite a `path:line` that exists.
- A web claim must quote text that really appears in what the lane fetched.

In mode `hybrid`, a lane whose output cannot be grounded falls back to Claude once, and the failure
is reported to you first. A connection failure is retried 3 times; if opencode is still down, the rest
of the run moves to Claude Sonnet 5.5. This cuts Claude token spend on exploration lanes without changing the
brainstorming contract.

## Install / requirements

- Claude Code >= 2.1.267, git >= 2.31, python3.
- `opencode` CLI v2.0.18 on `PATH`, authenticated for the providers of your configured models.
  Without it, mode `claude` works as before. In modes `hybrid` and `opencode`, `bslane.py` prints an
  `OC-ERROR ... kind=spawn` line at once; hybrid then runs the lane on Claude, opencode holds it.
- Drop this folder where Claude Code loads skills from, alongside (not instead of) `brainstorming-6.3`
  if you want both installed: the only injected agent is `hybrid-brainstorm-lane`, and the skill's own name and
  state directory differ from `brainstorming-6.3`'s, so the two skills never collide.

## Run modes

Every run asks "Run this skill in which mode?" before any work. Invocation args
`mode=hybrid|claude|opencode` skip the question, and hand-offs between hybrid skills pass the mode on.
The question shows the `std` and `lite` model specs and where each one comes from: `(skill)` for
this skill's own routing file, `(shared)` for the shared env vars.

| Mode | What runs where | On an opencode failure |
|---|---|---|
| `hybrid` (recommended) | Judgment on Claude; `locate`, `explore`, `fact` and `research` lanes on opencode (`draft` stays on Claude) | Reported at once. A connection failure is retried 3 times, then the rest of the run switches to Claude Sonnet 5.5. Any other failure re-runs that one lane on Claude |
| `claude` | Everything on Claude; opencode is never called and no doctor run is needed | Not applicable |
| `opencode` | Every lane that has an opencode runner goes to opencode, `research` and `draft` included | Connection failures are retried 3 times too. Then, as before: reported at once, the lane is held, and you are asked: retry / run on Claude / switch to hybrid / abort. No switch |

The mode is passed to every `bslane.py` call as `--preset <mode>`. Reviewers, synthesis, design, spec
and self-review stay on Claude in every mode.

## Presets

| Preset | `locate`/`explore` | `fact` | `research` | `draft` |
|---|---|---|---|---|
| `claude` | Claude | Claude | Claude | Claude |
| `hybrid` (default) | opencode | opencode | opencode, but only while `websearch=on` (otherwise one `OC-ERROR` and a Claude fallback) | Claude |
| `opencode` | opencode | opencode | opencode, but only while `websearch=on` (otherwise the lane is held with an `OC-ERROR`, with no Claude fallback) | opencode |

The old preset name `max` is still accepted as an alias for `opencode` and prints an
`OC-WARN ... kind=config` line.

## Backends

| Backend | Runs | Where |
|---|---|---|
| Claude | main thread (classify, T0, synthesis, design, spec, self-review), draft lanes (in preset `claude` or `hybrid`), research lanes (in preset `claude`), claim verifier, spec pre-draft | Claude Code background |
| opencode | Code lanes (roles `locate`, `explore`), web lanes (role `fact`, in preset `hybrid`/`opencode`), research lanes (preset `hybrid`/`opencode`, while `websearch=on`), draft lanes (preset `opencode` only) | `.hybrid-superpowers/brainstorm/lanes/<id>` via `bslane.py` |

## Config

- **Shared models** (all four hybrid skills read them): env vars `HYBRID_OPENCODE_STD` (required)
  and `HYBRID_OPENCODE_LITE` (optional, defaults to `HYBRID_OPENCODE_STD`), each
  `provider/model[#variant]`. They are the default source of the model and variant of the tiers
  `std` and `lite`. Set them once in the `env` block of `~/.claude/settings.json` and restart
  Claude Code (exporting them in the shell also works):

```json
{"env": {
  "HYBRID_OPENCODE_STD":  "opencode/muse-spark-1.3-contributor-free#xhigh",
  "HYBRID_OPENCODE_LITE": "opencode/muse-spark-1.3-contributor-free#low"}}
```

  `provider/model` is required and `#variant` (the thinking level) is optional. The slot count of a
  tier (`max_parallel`, 1 to 8) comes from the env var `HYBRID_OPENCODE_MAX_PARALLEL` (shared by all
  four hybrid skills; the shipped default is 4). A tier that sets `max_parallel` in the user file below
  keeps that value. An invalid value is a config problem and makes modes `hybrid` and `opencode` unavailable.
- **Shipped defaults**: `hybrid-brainstorming-v1.0/routing.default.json`. It carries no model or variant.
- **User file** (optional): `<skill dir>/routing.json`, next to `routing.default.json` (for example
  `~/.claude/skills/hybrid-brainstorming-v1.0/routing.json`). `doctor` no longer creates it.
  It holds roles, timeouts and slot waits, and it may override the model of a tier. Override the path
  with env `HYBRID_BRAINSTORMING_ROUTING=<path>`. A malformed user file is reported as a config problem, never silently
  ignored.
- **Precedence per tier** (`std`, `lite`):
  - When the user file sets `tiers.<tier>.model`, that tier uses the user file's `model` and `variant`
    and is shown as `(skill)`. A tier that sets no `variant` there runs without one; the shared
    variant is never mixed in.
  - Otherwise the tier uses `model` and `variant` from the shared env vars and is shown as `(shared)`.
  - `max_parallel` comes from the user file, else `HYBRID_OPENCODE_MAX_PARALLEL`, else the shipped defaults (4).
  - The shared env vars are reported as missing or invalid only when some tier has no model of its own.
    A tier with no model in either file makes modes `hybrid` and `opencode` print
    `OC-ERROR ... kind=config`.
  - The mode question and the `shared config:` line of the run's live context show each tier's
    spec followed by `(skill)` or `(shared)`.

  Example user file: it moves only `std` to another model, and `lite` keeps following the shared env vars.

```json
{"tiers": {"std": {"model": "zai-coding-plan/glm-5.4", "variant": "high"}}}
```

- **Per lane**: a `--backend` flag overrides routing for that call.

```json
{"preset": "hybrid",
 "tiers": {
   "std":  {"stall_s": 90, "timeout_s": 300},
   "lite": {"stall_s": 60, "timeout_s": 180}},
 "roles": {"locate": "lite", "explore": "std", "fact": "lite", "research": "std", "draft": "claude"},
 "max_roles": {"research": "std", "draft": "std"},
 "slot_wait_s": 60, "throttle_cooldown_s": 120}
```

`preset` is the default routing behaviour (`claude`, `hybrid`, `opencode`); the run mode overrides it
for a run. Each tier here holds a stall timeout and a lane timeout in seconds. `roles` maps roles to
tiers in the active preset; `max_roles` overrides them for the `opencode` preset only (the key keeps
its old name). Users may add tiers and point roles at them. The timeouts are shorter than
hybrid-team's because lanes answer a single question.

`disabled` is an optional key of a tier in the user file (`"disabled": true`) that the router reads. It
is not part of the shipped defaults. A tier with it set is treated as unavailable, regardless of the
doctor result.

## Names

Names this skill puts into shared namespaces, all prefixed `hybrid` so it installs beside `brainstorming-6.3`:

- opencode agent: `hybrid-brainstorm-lane`
- Env vars: `HYBRID_BRAINSTORMING_ROUTING`, `HYBRID_BRAINSTORMING_DOCTOR_CACHE`, `HYBRID_BRAINSTORMING_OC_BIN`; the visual companion uses `HYBRID_BRAINSTORMING_*` instead of `BRAINSTORM_*`
- Project state dir: `.hybrid-superpowers/` (`brainstorm/`, `drafts/`); session dir under `/tmp/hybrid-brainstorming-*`
- Unchanged on purpose: the spec path `docs/superpowers/specs/` (input of the next pipeline stage)

## Environment variables

- `HYBRID_OPENCODE_STD=<provider/model[#variant]>` - shared `std` tier model (required for modes
  `hybrid` and `opencode`, unless every tier sets its own model in the user file).
- `HYBRID_OPENCODE_LITE=<provider/model[#variant]>` - shared `lite` tier model, defaults to `HYBRID_OPENCODE_STD`.
- `HYBRID_BRAINSTORMING_ROUTING=<path>` - routing config path, instead of `<skill dir>/routing.json`.
- `HYBRID_BRAINSTORMING_OC_BIN=<path>` - path to the `opencode` executable (or a fake one, in tests) instead of
  resolving `opencode` on `PATH`.
- `HYBRID_BRAINSTORMING_DOCTOR_CACHE=<path>` - doctor cache path, instead of `~/.cache/hybrid-brainstorming/doctor.json`.
- `HYBRID_OC_RETRY_DELAY_S=<seconds>` - one delay for every retry, instead of 10/30/60 s (tests set `0`).

## Failure reporting

Every opencode failure is printed the moment it is detected, in one fixed shape:
`OC-ERROR hybrid-brainstorming <lane> tier=<tier> model=<spec> kind=<kind> :: <detail>`, plus
` log=<path>` when a log file exists. `OC-WARN` has the same shape for non-fatal notices. The same
lines are appended to `oc-errors.jsonl` in the run state directory, and `bslane.py` exits 3 when a
lane failed on opencode.

- `OC-ERROR` kinds: `spawn`, `timeout`, `stall`, `auth`, `quota`, `model`, `throttle`, `context`,
  `crash`, `config`, `breaker`, `switch`.
- `OC-WARN` kinds: `recovered`, `empty`, `format`, `grounding`, `lint`, `oracle`, `gate`.
- `auth`, `quota`, `model` and `config` failures cannot succeed on retry. They open a per-run circuit
  breaker for the tier, so later lanes skip it instead of repeating the failure. `throttle` keeps its
  cooldown.
- `recovered` means opencode exited with code 1 after a clean finish and the output passed the
  grounding gate, so the result is used.

### Retries and the run switch

- **Retries.** `spawn`, `stall`, `throttle` and `crash` are connection failures. `bslane.py` re-runs
  the lane from scratch (never a session continuation) up to 3 times, waiting 10, 30 and 60 s. Each
  failed try prints and logs `OC-WARN ... kind=<kind> :: retry <n>/3 in <s>s: <detail>`. The slot stays
  held while it waits. `timeout`, `context` and the gate kinds are not connection problems and are
  never retried.
- **Switch (mode `hybrid` only).** When the retries run out, or at once for `auth`, `quota` and
  `model`, the rest of the run moves to Claude Sonnet 5.5. `bslane.py` prints and logs one
  `OC-ERROR ... kind=switch :: opencode <kind>: <detail>; the rest of this run uses Claude sonnet`
  and records it in `<root>/.hybrid-superpowers/brainstorm/lanes/oc-switched.json`. The failed lane falls
  back with `model: sonnet`. Every later call for a role that would run on opencode spawns nothing
  and prints only the `CLAUDE <id> ...` line with `model: sonnet`, without an OC line. Lanes already
  running on opencode finish and are used as usual. Roles that Claude owns anyway, and
  `--backend claude`, keep their own model.
- **Not a connection problem.** `timeout`, `context` and the gate kinds keep their old behaviour:
  a per-lane fallback in `hybrid`, held in `opencode`. Setup errors found before opencode is spawned
  (`kind=config`, doctor results) also stay per lane.
- **Mode `opencode`.** Connection failures are retried too. After the retries nothing changes: the
  lane is held, you are asked, the breaker trips for the non-retryable kinds. There is no switch.
- **A new run starts unswitched.** The lane state directory belongs to the project, not to one run,
  so SKILL.md has the model run `bslane.py init` right after the mode is chosen. `init` deletes
  `oc-switched.json` and the circuit breakers of the previous run.

## Troubleshooting

- `bslane.py doctor [--ping]` - reports whether the config files parse and prints the context status
  line. Only `--ping` actually checks auth (a sentinel reply) and web search; a plain `doctor` run
  does not probe web search and keeps the answer of the last `--ping` for the same model. Lanes refresh
  a missing or stale (over 600 s) doctor entry themselves before routing; if that refresh fails they
  print an `OC-ERROR` line and fall back (hybrid) or are held (opencode). A passing `doctor --ping`
  also clears that tier's circuit breaker and cooldown, which is how "retry on opencode" works after
  an `auth`, `quota` or `model` failure. Without opencode, mode `claude` is unaffected, and the
  other modes report `OC-ERROR ... kind=spawn`.
- A lane stuck with no progress - an `OC-ERROR ... kind=stall` line is printed when the threshold for
  its tier elapses. Hybrid re-runs the lane on Claude; opencode holds it and asks you.
- Grounding failures - an `OC-WARN ... kind=grounding` line is printed when a lane's output cannot be
  verified as grounded (code path exists, web quote verified). Hybrid falls back to Claude once
  automatically.
- `websearch=off` - opencode asks once, interactively, to allow a search provider; that prompt is
  cancelled in a background run, so a `doctor --ping` run records `websearch=off`. Fix: open the
  `opencode` TUI once and allow web search, then re-run `bslane.py doctor --ping` - only `--ping`
  actually checks auth (via a sentinel reply) and web search, so a plain `doctor` run cannot confirm
  the fix. Until then, `research` lanes fall back to Claude in mode `hybrid` and are held in mode
  `opencode`; `fact` lanes still work through webfetch.
- A tier shows `(skill)` but you want the shared model - delete `model` and `variant` from that tier
  in `<skill dir>/routing.json`; the tier then follows the shared env vars.
- `OC-ERROR ... kind=config` - some tier has no usable model: the user file sets none for it and
  `HYBRID_OPENCODE_STD` is not set or is invalid. The preload line `shared config:` in the run's live
  context shows the source label, each tier's spec and source, and the validation state.
- `bslane.py stats` - summarizes the per-lane telemetry in `lanes.jsonl`.
- `bslane.py init` - starts a run: clears the previous run's switch to Claude and circuit breakers.
  Every lane is sent to Claude sonnet with no OC line although opencode works? A stale
  `oc-switched.json` is left over; run `bslane.py init` (or delete it) and continue.
- Prompt-free wide fan-outs - add the settings allow rule
  `Bash(python3 "<skill dir>/scripts/bslane.py":*)` so background lanes don't hit a permission prompt.

## Differences from brainstorming-6.3

- New `bslane.py` CLI runs lanes via opencode or Claude depending on routing.
- New backend router (`routing.default.json` / user routing file) decides Claude vs. opencode per
  lane from its role, or a lane's own `--backend` flag.
- New run-mode question at the start of every run, and shared model env vars for all hybrid skills
  that this skill's own routing file can override per tier.
- New failure handling for opencode lanes (stall, timeout, throttle, crash, spawn): every failure is
  reported at once as an `OC-ERROR` / `OC-WARN` line, connection failures are retried 3 times, and
  mode `hybrid` escalates to Claude (per lane, or for the rest of the run after a connection or
  auth-type failure).
- New grounding gate: code and web findings must cite a real `path:line` or web quote before they
  reach the main thread.
- SKILL.md frontmatter changes: `name: hybrid-brainstorming`, an opt-in description, and
  `allowed-tools` that add the `bslane.py` pin.
- Telemetry: one JSON line per lane appended to `<root>/.hybrid-superpowers/brainstorm/lanes.jsonl`
  with role, tier, model, variant, duration, tokens, grounded `n/m`, outcome and reason - no cost field.
- The preset `claude` runs every lane on Claude with brainstorming-6.3's
  lane roles, prompts and flow. It still differs in the run-mode question
  at Step 0, the `hybrid-` names, the `.hybrid-superpowers/` state
  directory, the relay rule and the `hybrid-writing-plans` hand-off.
