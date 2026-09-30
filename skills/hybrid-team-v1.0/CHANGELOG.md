# Changelog

All notable changes to `hybrid-team` are documented in this file.

## 1.1.0

- Run mode: every run starts by asking (or reading `mode=hybrid|claude|opencode` from the args)
  whether to run in hybrid, Claude-only or opencode-only mode. The answer is passed as
  `start --route hybrid|claude|opencode` and kept in the run state, so a resumed run never asks again.
- Shared opencode models: each tier's `model` and `variant` now default to env `HYBRID_OPENCODE_STD`
  (`std`, required) and `HYBRID_OPENCODE_LITE` (`lite`, defaults to STD), each `provider/model[#variant]`,
  shared by the four hybrid skills. `model` and `variant` were removed from `routing.default.json`.
  A tier whose `model` is set in `<skill dir>/routing.json` still uses that file's `model` and
  `variant` (no variant if it sets none, never the shared variant); the run-mode question marks each
  tier `(skill)` or `(shared)`. `doctor --fix` no longer copies the routing defaults into the user file.
- The shared models come from env vars only: set them in the `"env"` block of `~/.claude/settings.json`
  (e.g. `{"env": {"HYBRID_OPENCODE_STD": "opencode/muse-spark-1.3-contributor-free#xhigh"}}`) and restart
  Claude Code, or export them in the shell. There is no shared config file, no `init` command and no
  shared `max_parallel`: slot caps come from `<skill dir>/routing.json` or `routing.default.json`.
- The per-skill user routing file now lives next to the shipped defaults, at `<skill dir>/routing.json`
  (e.g. `~/.claude/skills/hybrid-team-v1.0/routing.json`), not under `~/.config`. There is no fallback
  to the old location: move an existing file there or point env `HT_ROUTING` at it.
- Preset `opencode` replaces `max` (`max` is still accepted as an alias and prints
  `OC-WARN ... kind=config`). An unknown preset is an `OC-ERROR ... kind=config` and a non-zero
  exit instead of silently becoming `claude`. In `opencode` mode a slice whose tier is unusable is
  held and never falls back to Claude on its own.
- Immediate error reporting: every opencode failure prints an `OC-ERROR` or `OC-WARN` line the moment
  it happens (a lane's background Bash, `next`, `doctor`), and `SKILL.md` tells the Conductor to relay
  it before any other work. Non-retryable kinds (`auth`, `quota`, `model`, `config`) open a per-run
  breaker for the tier.
- Retries and the switch to Claude: a lane retries a connection failure (`spawn`, `stall`, `throttle`,
  `crash`) up to 3 times, as fresh runs after 10 s, 30 s and 60 s, printing
  `OC-WARN ... kind=<kind> :: retry <n>/3 in <s>s: <detail>` for each failed try (env
  `HYBRID_OC_RETRY_DELAY_S` overrides every delay, for tests). In preset `hybrid`, a connection failure
  that survives the retries, or a non-retryable one (`auth`, `quota`, `model`, `config`), switches the
  whole rest of the run to Claude Sonnet 5.5: one `OC-ERROR ... kind=switch` line is printed and
  logged, the failed slice and every later slice that would have gone to opencode is dispatched to
  Claude with `model: sonnet`, and opencode is not spawned again (lanes already running finish
  normally). `timeout`, `context` and the gate kinds neither retry nor switch. Preset `opencode` keeps
  the retries but is otherwise unchanged (held, ask the user, breaker; no switch). The switch is
  `oc-switched.json` in `.claude/hybrid-team/`; `init` deletes it, like the breaker.
- Fixes: `doctor` prints the issues list it used to drop; the `.blocked` marker names the stderr log;
  `escalate_to` (documented, never read) is removed; the agent hook loops now also probe
  `skills/hybrid-team-v1.0`; `start` pings every tier without a fresh doctor result in presets
  `hybrid` and `opencode` (`doctor --ping` pings all), and the docs no longer claim a bare `doctor`
  checks authentication, describe stall handling correctly, and no longer call escalation
  "transparent".

## 1.0.1

- opencode lanes deny the `execute` tool: it runs JS with network access that the bash
  deny-list (`curl*`, `wget*`, ...) does not cover.

## 1.0.0

Initial release - a fork of `dev-team-v3.2` (event-driven, contract-gated pipeline, mechanical
gates, worker-agnostic merge) that adds a second execution backend:

- Backend router (`routing.default.json`, user override at `<skill dir>/routing.json`,
  env `HT_ROUTING`) maps each slice's `kind`/`size`/`risk` to Claude or an opencode tier, under
  presets `claude` (identical to dev-team-v3.2), `hybrid` (default) and `max`.
- New `lane <id>` engine subcommand: spawns the local `opencode` CLI in an isolated worktree
  (`.claude/worktrees/oc-<id>`), captures its JSON event stream, and writes the same
  `.done`/`.blocked` marker shape a Claude programmer writes.
- `doctor` gained an opencode availability/auth check; missing or broken opencode degrades to
  all-Claude routing with one NOTE, never a hard failure.
- Failure handling for opencode lanes: gate double-block, stall, timeout, 429/quota throttle, crash
  and spawn errors all resolve to a `.blocked` marker with a `reason`, then escalate once to Claude
  before falling back to the normal BLOCKED flow.
- `stats` reports Claude vs. opencode token/cost split per tier.
- Namespace: `ht-`-prefixed Claude agents, `.claude/hybrid-team/` state dir, `hybrid-team-root`
  pointer file - installable side by side with `dev-team-v3.2`.
