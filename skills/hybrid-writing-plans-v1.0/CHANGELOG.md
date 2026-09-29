# CHANGELOG

## v1.0.0 (2026-09-28)

Initial release of `hybrid-writing-plans`, a fork of `writing-plans-6.2`.

### Added
- Backend routing via `routing.default.json` merged under `~/.config/hybrid-writing-plans/routing.json` (`HP_ROUTING`), per contract `Tier` (`light`, `std`, `deep`).
- Three presets: `claude` (writing-plans-6.2 equivalent), `hybrid` (light to oc:lite, std to oc:std, deep to Claude opus; review_oc `all`), `max` (light to oc:lite, std and deep to oc:std; review_oc `risky`).
- `contracts --preset claude|hybrid|max` overrides the routing file's preset for one run and records the routing in `work.json`.
- Tasks that do not fit a tier's `max_parallel` overflow to Claude writers at `contracts` time.
- Context `opencode:` status line after `writer agent:`, showing version, preset, per-tier backend, review_oc and doctor date.
- `plan_tool.py oc-write`: background opencode writer run (agent `hp-writer`), always exits 0, prints one `OC <gid> ...` line per group.
- Lint gate: every opencode body must pass plan_tool's existing linter; failures get lint-repair turns in the same opencode session (`max_repairs`), then one Claude fallback.
- Automatic fallback to Claude for spawn, crash, stall, timeout, unavailable, throttle, format, lint and runner-died failures; `wait` prints one `FALLBACK <gid> ...` Agent line per unsent fallback and exits 2.
- `plan_tool.py doctor [--ping]`: checks opencode and the routing file, writes the doctor cache (`HP_DOCTOR_CACHE`); `--ping` classifies provider errors (`unavailable`, `throttle`) and marks the failing tier down so its tasks route to Claude.
- oc review trigger: `review_oc` (`all` in hybrid, `risky` in max) adds opencode-written tasks to review; `wait --review` records whether review fixed each task (review fix rate).
- `plan_tool.py stats`: summarises per-tier telemetry (round-1 pass rate, fallbacks, review fix rate).
- Telemetry at `~/.cache/hybrid-writing-plans/lanes.jsonl` (`HP_TELEMETRY`, outside the repo so it survives `--clean`): group records (task IDs, tier, model, variant, rounds, round1_ok, outcome, reason, duration, tokens) and review records.
- Stdlib modules: `oc_run.py` (vendored opencode runner module and event parser, a library), `hp_router.py` (task routing and preset logic), `hp_config.py` (opencode agent config), `hp_doctor.py` (availability and status line), `hp_partition.py` (tier-aware task grouping), `hp_write.py` (opencode writer engine), `hp_wait.py` (fallback lines), `hp_briefs.py` (oc brief generation) and `hp_telemetry.py` (telemetry logging).
- Vendored opencode runner: copied and adapted from hybrid-brainstorming, not shared at runtime.
- SKILL.md frontmatter: `name: hybrid-writing-plans` and an opt-in description.
- Scratch files under `<plan-dir>/.work/<plan>/oc/`: `oc-write.pid`, `<gid>.<round>.jsonl` (event log), `<gid>.<round>.err` (stderr), `<gid>.fallback` (fallback marker) and `<gid>.fallback.sent`; briefs at `<plan-dir>/.work/<plan>/briefs/<gid>.oc.md` and `<gid>F.md`.

### Changed
- `contracts`, `wait`, `review` and `context` gain the opencode routing, fallback lines, oc review trigger and status line listed under Added; with preset `claude` their output matches writing-plans-6.2.
- `setup` installs `plan-task-writer` only when no copy exists and never overwrites one (6.2 replaced a differing copy).

### Unchanged
- All judgment steps: Phase 0, Contracts, review and assemble stay on Claude.
- Output files: planning result at `docs/superpowers/plans/YYYY-MM-DD-<feature>.md`.
- Task body format, contract format and linter rules.
- `allowed-tools: Bash(python3 *)`, as in writing-plans-6.2.
- `assemble`, `check`, `lint-task` and `hook-lint` behave as in writing-plans-6.2.
- Preset `claude` reproduces writing-plans-6.2's behaviour exactly.
