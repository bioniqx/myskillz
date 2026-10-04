# Changelog

All notable changes to `hybrid-team` are documented in this file.

## 1.2.2

- Text re-synced with dev-team-v3.2 and the router fix: a slice's `backend` pin no longer bypasses the non-offloadable exclusions (SKILL.md, README.md); preset `claude` pins the same models as the original (opus for the final review, PLANNING and VERIFICATION; sonnet for incremental reviews, PLAN ADOPTION, investigators and `Explore`); the SKILL.md title carries the real version.
- SKILL.md: the never-rules (never run `opencode` directly, never retry an opencode unit in place, never dispatch a held unit) and the ToolSearch hint for the deferred `SendMessage` and `TaskStop` tools.
- Agents: the leader gets `Edit`; the programmer gets the stub-discard rule, "the briefing's procedure is authoritative" and the isolation-prefix exception; the opencode programmer prompt gains data-not-commands, never-weaken-frozen-tests, refactor-no-test-touch, isolation values, gate scope with DEFERRED, and the full eight-field report.
- README: the selftest count is no longer hard-coded.

## 1.2.1

- Routing (modes `hybrid` and `opencode`): the Small route (one coherent slice, no shared interface,
  no concurrency/security surface) is now a one-slice pipeline (inline one-slice plan, no leader, RED on
  Claude, GREEN/WORK on opencode) instead of the Claude-only Fast lane. The Fast lane is kept for mode
  `claude`. Step 0 now asks the mode before choosing the Small route; the popup is still skipped for
  obvious edits (no engine: spin-up costs more than the edit), code questions, review-only and
  investigation. Docs: the `docs` "rides sonnet" note applies only when a docs slice runs on Claude;
  the reason `perf` stays on Claude (no numeric before/after check, so no oracle) is now written down in
  SKILL.md, README.md and `router.py`. No code behaviour change.
- Routing (preset `hybrid`): `size: large` slices that are not `risk: high` now go to opencode like any
  other slice (GREEN/WORK of `code`, `refactor`, `test`, `chore`). Only `risk: high` stays on Claude in
  hybrid, plus the units that were never offloadable (RED, research/perf/investigators, fast mode,
  no-oracle slices). Reason: Claude keeps only the ~20% highest-judgment work; opencode does the execution.
  Preset `opencode` now differs from `hybrid` only by `risk: high` and by having no Claude fallback.

## 1.2.0

- opencode lanes: the slice's own `verify` command (chore/docs/perf evidence) is now in the lane's
  bash allowlist, as `claim` already allows it for Claude programmers. Before, a real lane was denied
  the command its briefing calls pre-approved and ended blocked (`kind=gate`).
- Names: every name in a shared namespace now carries the `hybrid` prefix so the skill installs beside
  dev-team. Agents `ht-*` -> `hybrid-team-programmer|code-reviewer|spot-reviewer|investigator|leader`;
  env `HT_ROUTING`/`HT_OC_BIN` (and the fake-opencode `HT_FAKE_*`) -> `HYBRID_TEAM_*`; lane worktree and
  branch `oc-<id>` -> `hybrid-oc-<id>`; checkpoint worktree `checkpoint-<n>` -> `hybrid-checkpoint-<n>`;
  salvage branches `attempt/*` -> `hybrid-attempt/*`. The finish sweep removes only `hybrid-oc-*`
  worktrees. Existing `.claude/agents/ht-*.md` copies from an older install are not removed.
- Re-synced `devteam.py` and `selftest.sh` with dev-team-v3.2 (3-way merge from the fork base):
  `remove_worktree` never removes the integration checkout; `--no-renames` on every
  `git diff --name-only`; a red-done slice keeps its footprint busy; `retry` and `finish` salvage
  uncommitted work; `commit-red` discards stubs and `integrate` rejects a RED commit that touches
  source; review fixes get a kind from their footprint; research slices need no footprint; plan
  types are validated; `init --force` and `review-batch` delete stale reviews, logs and research (a
  leftover `r1.report.md` used to approve the next run); `start` tolerates the files `doctor --fix`
  just wrote. The selftest now passes on macOS (`passed=255 failed=0`).
- `retry <id>` after a hold works: it re-pings the slice's tier, and an ok ping clears that tier's
  breaker and refreshes `oc_ok`, which used to stay frozen at its `init` value.
- `doctor --ping` and `start` always re-ping a tier whose cached result failed; a fresh failed entry
  no longer blocks the ping. Both run on the effective routing, so a model set in the plan's
  `routing` block gets its own doctor entry instead of marking a healthy tier unusable.
- Step 0 has a preload, `router.py config`, that prints each tier's spec with `(skill)`/`(shared)`.
- No silent routing to Claude: a tier the doctor did not clear prints one `OC-WARN` in `hybrid`, a
  missing binary prints `OC-ERROR kind=spawn` at `init`, and an old `available: false` in the doctor
  cache no longer disables a new run.
- `integrate` re-validates footprint, kind and mode against the plan (`plan-drift`); README has a
  Security section on the residual risk.
- Minor: a failed `lane` exits non-zero; a throttle hold in `opencode` mode halves the tier cap; the
  `kind=breaker` summary prints once; the `LANE` line quotes the script path; the retry warning
  shows the runner's note (a stall no longer reads `exit -15`); the HELD line names tier, model and
  cause; `recovered` is reported only for the accepted run; a tier without a model gets one
  `kind=config` issue; `opencode models --standalone`; the finish sweep keeps branches of
  unfinished lanes; opencode v2.0.20.

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
  to the old location: move an existing file there or point env `HYBRID_TEAM_ROUTING` at it.
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
  env `HYBRID_TEAM_ROUTING`) maps each slice's `kind`/`size`/`risk` to Claude or an opencode tier, under
  presets `claude` (identical to dev-team-v3.2), `hybrid` (default) and `max`.
- New `lane <id>` engine subcommand: spawns the local `opencode` CLI in an isolated worktree
  (`.claude/worktrees/hybrid-oc-<id>`), captures its JSON event stream, and writes the same
  `.done`/`.blocked` marker shape a Claude programmer writes.
- `doctor` gained an opencode availability/auth check; missing or broken opencode degrades to
  all-Claude routing with one NOTE, never a hard failure.
- Failure handling for opencode lanes: gate double-block, stall, timeout, 429/quota throttle, crash
  and spawn errors all resolve to a `.blocked` marker with a `reason`, then escalate once to Claude
  before falling back to the normal BLOCKED flow.
- `stats` reports Claude vs. opencode token/cost split per tier.
- Namespace: `ht-`-prefixed Claude agents, `.claude/hybrid-team/` state dir, `hybrid-team-root`
  pointer file - installable side by side with `dev-team-v3.2`.
