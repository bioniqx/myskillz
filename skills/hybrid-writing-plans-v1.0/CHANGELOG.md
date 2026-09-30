# CHANGELOG

## v1.1.0 (2026-09-29)

Shared opencode config, run-mode prompt and immediate error reporting.

### Added
- Shared models `HYBRID_OPENCODE_STD` and `HYBRID_OPENCODE_LITE` (`provider/model[#variant]`; `LITE` defaults to `STD`) for the tiers `std` and `lite`, used by all four hybrid skills. `model` and `variant` moved out of `routing.default.json`. A tier whose `model` is set in `<skill dir>/routing.json` uses that model and its `variant` (none when omitted) instead of the shared one; every other tier uses the shared models.
- SKILL.md Step 0: asks for the run mode (hybrid, Claude only or opencode only) unless the arguments carry `mode=`; the choice is passed to `contracts --preset` and frozen in `work.json`.
- Preset `opencode` (replaces `max`; `max` stays as an alias and prints one `OC-WARN ... kind=config` line). In this preset a group without a usable opencode tier is held: `contracts` prints `OC-ERROR` and a `HELD` block, dispatches nothing for it and never falls back to Claude on its own.
- `wait` prints unreported `OC-ERROR` / `OC-WARN` lines before anything else, ends at once with exit 2 on a new `OC-ERROR`, and exits 3 when only held tasks are left; `wait --include-held` waits for them after the user chose Claude.
- `context` prints the shared-config summary line, with each tier marked `(skill)` or `(shared)`, and a `mode:` line right after the `opencode:` line.
- SKILL.md relay rule and failure policy per mode.
- Connection retries: an opencode run that fails with `spawn`, `stall`, `throttle` or `crash` is repeated up to 3 times, 10, 30 and 60 s apart (`HYBRID_OC_RETRY_DELAY_S` overrides every delay, for tests), as a fresh run, never a `--session` continuation. Each failed try prints and logs one `OC-WARN ... kind=<kind> :: retry <n>/3 in <s>s: <detail>` line. Lint-repair turns are separate and unchanged; `timeout`, `context` and the gate kinds are not connection problems and neither retry nor switch. Retry logs are kept per try as `<gid>.<round>.r<n>.jsonl` / `.err`.
- Switch to Claude in preset `hybrid`: a group that still fails after its retries, or fails with `auth`, `quota`, `model` or `config`, records `oc/oc-switched.json` and prints and logs one `OC-ERROR ... kind=switch :: opencode <kind>: <detail>; the rest of this run uses Claude sonnet` line. From then on the failed group and every group that had not started (reason `switched`) get a fallback marker with `model` sonnet (Claude Sonnet 5.5) and no opencode spawn, and `wait` prints them as `FALLBACK` lines; groups already running finish and are harvested normally. A new `contracts` run starts unswitched. Preset `opencode` retries too but never switches: after the retries the group is held as before.

### Changed
- The shared models come only from the env vars `HYBRID_OPENCODE_STD` / `HYBRID_OPENCODE_LITE`, set for example in the `"env"` block of `~/.claude/settings.json` (then restart Claude Code); there is no shared file, path override or fallback, and no shared `max_parallel`: it now comes only from `<skill dir>/routing.json` or `routing.default.json`.
- The default per-skill user routing file moved out of the user's `~/.config` tree to `<skill dir>/routing.json`, next to `routing.default.json` (for example `~/.claude/skills/hybrid-writing-plans-v1.0/routing.json`); `HP_ROUTING` still overrides it and the old location is no longer read.
- `contracts --preset` accepts `claude`, `hybrid`, `opencode` and `max`; any other value prints `OC-ERROR ... kind=config` and exits 1.
- `contracts` reports at once why opencode is not used (config problems, failed tier with its kind, no usable doctor entry) instead of routing to Claude silently.
- `doctor` no longer copies the shipped defaults into the user file; it validates both config files, prints the config summary, prints each tier line with its `(skill)` or `(shared)` mark, prints one `OC-ERROR` per problem or failed tier, and exits 1 when opencode is missing, the config has problems or a tier failed.
- `assemble --clean` keeps `oc/oc-errors.jsonl`.
- `wait` prints a `HELD` marker from a failed group (mode opencode) with a do-not-dispatch message instead of the FALLBACK launch message.
- SKILL.md no longer calls the `OC` lines informational.

### Fixed
- The README and the v1.0.0 changelog said `doctor` validates the routing file; it now does.

## v1.0.0 (2026-09-28)

Initial release of `hybrid-writing-plans`, a fork of `writing-plans-6.2`.

### Added
- Backend routing via `routing.default.json` merged under `<skill dir>/routing.json` (`HP_ROUTING`), per contract `Tier` (`light`, `std`, `deep`).
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
