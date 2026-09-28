# Changelog

All notable changes to `hybrid-team` are documented in this file.

## 1.0.0

Initial release - a fork of `dev-team-v3.2` (event-driven, contract-gated pipeline, mechanical
gates, worker-agnostic merge) that adds a second execution backend:

- Backend router (`routing.default.json`, user override at `~/.config/hybrid-team/routing.json`,
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
