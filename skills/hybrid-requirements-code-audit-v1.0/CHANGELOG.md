# CHANGELOG

## v1.1.0 (2026-09-29)

### Added
- Retries and a run-wide switch: an opencode run that fails with `spawn`, `stall`, `throttle` or `crash` is retried up to 3 times as a fresh run (waits 10 s, 30 s, 60 s; `HYBRID_OC_RETRY_DELAY_S` overrides them), each failed try printing `OC-WARN ... :: retry <n>/3 in <s>s: <detail>`. In preset hybrid, once the retries are used up (or at once for `auth`, `quota`, `model`, `config`) the rest of the run switches to Claude Sonnet 5.5 (`model: sonnet`): one `OC-ERROR ... kind=switch :: opencode <kind>: <detail>; the rest of this run uses Claude sonnet` line, the record `oc-switched.json` in the audit dir, a `FALLBACK` on sonnet for the failed batch, and every later oc unit (investigators, verifiers, parsers) dispatched to Claude on sonnet with no `OPENCODE` block; running opencode batches are harvested normally and a late `oc-run` exits 3 as `FALLBACK (switched)` without spawning. `timeout`, `context` and the warning kinds keep their behaviour. Preset opencode retries too, then holds the unit as before (no switch). `init` starts unswitched.
- Run mode: `init --preset claude|hybrid|opencode`, asked once by SKILL.md Step 0a. `max` stays as an alias of `opencode` and prints one `OC-WARN kind=config` line; an unknown preset prints `OC-ERROR kind=config` and exits non-zero before anything is created.
- Preset `opencode`: investigators, verifiers and parsers go to opencode with no Claude overflow, fallback or hedge. A unit with no usable tier, or whose batch failed, is held (`held` in `state.json`); `status --retry`, `status --to-claude`, `status --mode` and `parse-merge --to-claude` are the user's answers.
- Shared models from the env vars `HYBRID_OPENCODE_STD` / `HYBRID_OPENCODE_LITE` (`provider/model[#variant]`, LITE defaults to STD; set them in the `env` block of `~/.claude/settings.json`), read by `init`, `plan`, `status` and `doctor`. Config problems print as `OC-ERROR kind=config`. A per-skill `routing.json` that sets a tier's `model` overrides them for that tier.
- `init`, `plan`, `parse-plan`, `parse-merge` and `status` print unreported `OC-ERROR` / `OC-WARN` lines from `oc-errors.jsonl` before anything else; `status` prints one breaker summary per finished wave.
- `doctor` prints one `OC-ERROR` line per unusable tier and per config problem.

### Changed
- Shared models come from env vars instead of a file: the file, its path variable, `hybrid_shared.py init` and the shared `max_parallel` are gone (`max_parallel` now comes only from the routing file); `doctor` prints the resolved specs as `shared  : <source> = std=..., lite=...` or `not set`.
- `oc-run` exits 3 when its batch failed, so the background notification is flagged.
- `doctor` no longer copies `routing.default.json` into the user routing file, and its cache entries are keyed by `model#variant`.
- SKILL.md gains Step 0a, the relay rule and the Held units section; the wording that called `OC` lines informational is gone.
- The default user routing file is now `<skill dir>/routing.json`, next to `routing.default.json`, instead of a per-skill folder under `~/.config` (`HA_ROUTING` still overrides; the old path is no longer read).

### Removed
- The persistent tier "down" marks: the run's circuit breaker replaced them.

## v1.0.1 (2026-09-28)

### Fixed
- One atomic writer: `audit.write_json` now goes through `ha_run.atomic_write`, and files it writes get the umask mode (usually 0644) instead of mkstemp's 0600. Written bytes are unchanged.
- `oc-run` repair rounds: rows re-sent for ids filled in an earlier round no longer add to the oracle `dropped`/`demoted`/`invalid_status` telemetry.
- `status` without a checklist keeps pointing to `audit.py parse-merge` after `parse-merge` handed every opencode section to Claude parsers (it used to fall back to `parse-plan`), with wording that holds whether sections are running or done. Preset `claude` output is unchanged.
- Solo `init` stores preset `claude` and prints the preset `claude` `opencode:` line, not the configured preset's routing, which solo never uses.
- The hybrid `plan` summary drops "of ≤N" when there are no Claude investigator batches.
- The oracle strips whitespace from row and batch ids, so `" R1 "` matches `R1` instead of counting as foreign.

## v1.0.0 (2026-09-28)

Initial release of `hybrid-requirements-code-audit`, a fork of `requirements-code-audit`.

### Added
- Routing via `routing.default.json` deep-merged under `<skill dir>/routing.json` (`HA_ROUTING`).
- Presets `claude`, `hybrid` (default) and `max`, selected per audit with `init --preset claude|hybrid|max`.
- Capacity split: items beyond a tier's `max_parallel` stay on Claude at `plan` time.
- The `opencode:` status line in `init` output.
- `oc-run <name>`: marker block parsing, evidence oracle, repair turns in the same opencode session, atomic output and an event file.
- The evidence oracle (foreign ids removed, invalid status to `UNSEARCHED`, bad citations dropped, rows demoted to `confidence: low`).
- One Claude fallback per failed opencode batch, with tier down-marking on `unavailable` and a cooldown on `throttle`.
- `doctor [--ping]`.
- `stats` and telemetry in `lanes.jsonl` (`HA_TELEMETRY`).
- Stdlib modules `oc_run`, `ha_router`, `ha_config`, `ha_briefs`, `ha_doctor`, `ha_oracle`, `ha_partition`, `ha_run`, `ha_dispatch`, `ha_telemetry`.
- `.oc.md` briefs written next to the Claude briefs.
- opencode scratch files in `<out>/oc/`.

### Changed
- `init`: preset, routing snapshot in `config.json`, status line.
- `parse-plan` and `parse-merge`: parser routing and fallback.
- `plan`: opencode batches and the summary suffix.
- `status`: per-backend slots, the `OPENCODE` block, fallbacks, verifier routing in `max`, merge across a batch's files.
- `report`: the `- Backends:` line.
- `finish`: item telemetry.
- SKILL.md gains a hybrid routing section and an opt-in description.

### Unchanged
- Every judgment step stays on Claude.
- The `.audit/` layout, existing schema keys, status taxonomy, priority rules, report structure and the `check` gate.
- `audit.check_evidence`.
- `allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)`.
- No agents, hooks or plugin manifest of its own (reuses `req-audit`).
- Workflow mode stays all-Claude.
- Preset `claude` reproduces requirements-code-audit exactly.
