# CHANGELOG

## Unreleased

### Fixed
- Guard hook: the fork ships `hooks/audit_guard.py` and `hooks/audit_guard.sh`, the original guard retargeted to `.hybrid-audit/` (it used to be the original's `.audit/`-only guard, which never armed for a hybrid audit). The launcher and the hook arm only on `.hybrid-audit/ACTIVE` and `config.json`; registration is optional and described in SETUP.md section 5.
- Text layer: agent and plugin names are the real `claude-rca-investigator`, `claude-rca-verifier`, `claude-rca-parser` and `claude-req-audit:`; the claims of bundled agents, plugin-level structural blocking and `SubagentStop` events now say they depend on registering the fork's hook; `schemas.md` names the injected agents `hybrid-audit-<role>`.
- Preset `claude` text equals the original: Claude investigators run on sonnet, large specs start at about 800 words, and workflow-mode investigators use sonnet.
- The queue text no longer calls the 5% sample deterministic; a MATCHED, high-confidence item of normal stakes is documented as covered only by the stable spot-check sample (the accepted ceiling).

### Changed
- Preset `hybrid`: investigator overflow now queues on opencode instead of going to Claude haiku. `plan` used to keep only `max_parallel × oc_batch_max` items (24 by default) on opencode and sent the rest to Claude, so 60 items meant 36 on Claude. Now all items are split into opencode batches of up to `oc_batch_max` (60 items = 15 batches); the first `max_parallel` start at once and `status` dispatches the rest as slots free up, the same path preset `opencode` already used. A queued batch has no start time, so it is never hedged before its own run starts, and the `plan` summary reads `N opencode batches (M items), K queued for a free slot`. New routing key `oc_overflow`: `"queue"` (default in `routing.default.json`) or `"claude"` (the old split). Preset `opencode` ignores it (always queues); any other value is a `config_problems` entry naming the file and key, and the default applies. A tier that is unusable (breaker, switch, doctor, throttle cooldown) still routes everything to Claude, and failure fallbacks and the run switch are unchanged. To get the old behaviour set `"oc_overflow": "claude"` in a skill-dir `routing.json`.
- Preset `hybrid`: spec parsers (large-spec section decomposition) now run on opencode tier `std` (`roles.parser` is `std` in `routing.default.json`, was `claude`). A section that fails falls back to a Claude sonnet parser once (`parse-merge` prints `FALLBACK section-NN (<reason>) → Claude parser`); the lead still does the faithfulness pass over the merged draft. Verifiers stay on Claude sonnet in hybrid (the adversarial cross-model check), investigators are unchanged. Reason: Claude keeps only the ~20% highest-judgment work and opencode does the execution. Presets `claude` and `opencode` are unchanged. To keep parsers on Claude, set `"roles": {"parser": "claude"}` in a skill-dir `routing.json`.

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
- The default user routing file is now `<skill dir>/routing.json`, next to `routing.default.json`, instead of a per-skill folder under `~/.config` (`HYBRID_AUDIT_ROUTING` still overrides; the old path is no longer read).

### Renamed (no collision with the original skill)
- Every name this skill puts in a shared namespace now carries the `hybrid` prefix: opencode agents `hybrid-audit-investigator` / `hybrid-audit-verifier` / `hybrid-audit-parser` (were `ha-*`), env vars `HYBRID_AUDIT_*` (were `HA_*`), the project state dir `<cwd>/.hybrid-audit/` (was `.audit/`, which the original skill also writes), archives `.hybrid-audit.prev-<timestamp>/`, and the saved workflow `hybrid-audit-run`. Existing `.audit/` runs are not read; re-run `init`. The `rca-*` agents and `req-audit:` prefix stay: they are the original skill's.

### Removed
- The persistent tier "down" marks: the run's circuit breaker replaced them.

### Fixed
- Re-synced with requirements-code-audit: `read_jsonl` BOM and concatenated-object fallback; `Merged.events` drops events older than a batch's latest dispatch (`oc:` events keep their names); a stable `queue_ids` spot sample; `clear_run_artifacts` on `plan`/`parse-plan` reruns; verifier `--failed`/`--redispatch`; the `adjudicate` UNSEARCHED guard; `plan_ids`; `check_evidence` accepts `L1-2` and en-dash ranges; `status` relists undispatched solo batches; `git_exclude` follows a linked worktree's `commondir`; `status` prints the adjudication queue itself; references and SKILL.md carry the same wording.
- Oracle: an invalid `verified_status` (and a verifier `UNSEARCHED`) is rejected and repaired instead of coerced and counted as done; `confidence` is normalized to low/medium/high (a float no longer wedges `status`); parser validation problems feed the repair turn; `is_doc_path` is the original's, so `src/history.py`, `LicenseService.java`, `changes.py`, `history/store.py` and `docs/conf.py` keep their evidence; `.GIT/...` and `.hybrid-audit/...` citations are rejected.
- `doctor --ping` writes its logs to the cache folder, never into the audited repo; `opencode models` runs with `--standalone`; a tier with no model and a timed-out `opencode models` get their own kinds (`config`/`timeout`), not "model not found".
- `status --retry` re-pings and closes the breaker of a tier that answers, so `auth`, `quota`, `model` and `config` can be recovered.
- Tier health is frozen when the audit starts (`state.json` `health`): a stale doctor cache no longer downgrades verifiers mid-run. `init` (and `plan` for an audit without a snapshot) pings once when the cache is missing or stale for the mode's tiers, or prints an `OC-ERROR`.
- MISSING, PARTIAL and CONFLICT verdicts from opencode verifiers are queued for Claude adjudication in every mode and flagged by `check`.
- `init` also clears `oc-breaker/`, `events/` and `oc-errors.jsonl` (+ `.seen`) of an earlier audit, including with `--force --out X`.
- Wrong-typed `max_parallel`, `oc_batch_max`, `timeout_s`, `stall_s`, `max_repairs` and `throttle_cooldown_s` are config problems, and `"model": null` is not; mode opencode honours `oc_batch_max`; `opencode_stranded` reads a failed event with the same falsy check as the harvester; the refusal hint says to run `status` first; the `max` alias warning is logged; a stall/timeout line keeps the runner's note; a crash inside `oc-run` prints an OC line and writes a failed event; the breaker kinds come from `hybrid_shared.NON_RETRYABLE`.
- SKILL.md: full relay rule, the preload prints each tier's model with its source `(skill|shared)`; `references/schemas.md` describes the current presets, kinds, breaker, held and switch records.

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
- Routing via `routing.default.json` deep-merged under `<skill dir>/routing.json` (`HYBRID_AUDIT_ROUTING`).
- Presets `claude`, `hybrid` (default) and `max`, selected per audit with `init --preset claude|hybrid|max`.
- Capacity split: items beyond a tier's `max_parallel` stay on Claude at `plan` time.
- The `opencode:` status line in `init` output.
- `oc-run <name>`: marker block parsing, evidence oracle, repair turns in the same opencode session, atomic output and an event file.
- The evidence oracle (foreign ids removed, invalid status to `UNSEARCHED`, bad citations dropped, rows demoted to `confidence: low`).
- One Claude fallback per failed opencode batch, with tier down-marking on `unavailable` and a cooldown on `throttle`.
- `doctor [--ping]`.
- `stats` and telemetry in `lanes.jsonl` (`HYBRID_AUDIT_TELEMETRY`).
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
- The `.hybrid-audit/` layout, existing schema keys, status taxonomy, priority rules, report structure and the `check` gate.
- `audit.check_evidence`.
- `allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)`.
- No agents, hooks or plugin manifest of its own (reuses `req-audit`).
- Workflow mode stays all-Claude.
- Preset `claude` reproduces requirements-code-audit exactly.
