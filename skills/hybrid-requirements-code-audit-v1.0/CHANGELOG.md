# CHANGELOG

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
- Routing via `routing.default.json` deep-merged under `~/.config/hybrid-requirements-code-audit/routing.json` (`HA_ROUTING`).
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
