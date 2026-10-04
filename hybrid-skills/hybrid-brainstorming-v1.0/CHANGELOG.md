# CHANGELOG

## v1.1.2 (2026-10-04)

### Fixed
- Ported the 6.3 spec-commit rule: `architectural.md` §4 commits the spec only when neither the user nor a loaded project or user instruction file says not to commit self-initiated files; otherwise the spec stays untracked and the review gate says "not committed, per your instructions". SKILL.md (merge rules, checklist) and `spec-document-reviewer-prompt.md` follow it, and the hand-off passes the spec path, committed or not.
- `research-playbook.md` cites the claim-verifier lane at `architectural.md` §3 (it said §4).
- SKILL.md states the per-tier cap as 4 parallel lanes (it said 6), matching the shipped default and the README.
- The spec pre-draft lane in `architectural.md` §3 passes `model: "sonnet"` again.
- Round 1 and round 2 use the 6.3 wording: load deferred tools first, call them in round 1 only if already loaded, otherwise in round 2 (SKILL.md, `fanout-playbook.md`).
- `scripts/helper.js`: `window.brainstorm.choice()` also sends a `choice` key, because `server.cjs` records only events that carry one.

### Changed
- README: preset `claude` no longer claims to reproduce brainstorming-6.3 exactly; it lists what still differs (run-mode question, `hybrid-` names, state directory, relay rule, hand-off).

## v1.1.1 (2026-10-01)

### Changed
- Mode `hybrid` now runs `research` lanes on opencode tier `std` (`routing.default.json`: `roles.research` is `std`, was `claude`), checked by the `hb_ground.py` grounding oracle. Claude keeps only the highest-judgment work (about 20%): `draft` stays on Claude in `hybrid` because drafts are ungrounded (no oracle) and decide the design. `locate`, `explore` and `fact` are unchanged; mode `opencode` still routes `draft` to opencode.
- `research` needs `websearch=on` in `hybrid` too. When the doctor reports `websearch=off`, the lane prints one `OC-ERROR ... kind=config` line and falls back to its Claude lane (`FALLBACK` + `CLAUDE` lines, exit 3); mode `opencode` still holds it. New test `test_hybrid_research_with_websearch_off_falls_back_to_claude_with_an_oc_error`.
- SKILL.md routing table and mode text, README (mode, preset and backend tables, routing example, troubleshooting) and the router/bslane test fixtures follow the new default.

## v1.1.0 (2026-09-29)

### Renamed (collision-free install beside `brainstorming-6.3`)
- Every name this skill puts into a shared namespace now carries the `hybrid` prefix: the opencode agent `hb-lane` is `hybrid-brainstorm-lane`; the env vars `HB_*` are `HYBRID_BRAINSTORMING_*` (`ROUTING`, `DOCTOR_CACHE`, `OC_BIN`, and the test-only `FAKE_*`); the project state directory `.superpowers/` is `.hybrid-superpowers/` (same sub-paths: `brainstorm/`, `drafts/`, lanes, token files, still `chmod 600`). The visual-companion server also renames its `BRAINSTORM_*` env vars to `HYBRID_BRAINSTORMING_*`, the `/tmp/brainstorm*` session directory to `/tmp/hybrid-brainstorming*`, the `--brainstorm-server-id` argument, and the `brainstorm-key-*` cookie and `brainstorm-session-key` storage key to `hybrid-brainstorming-*`. The spec output path `docs/superpowers/specs/` is unchanged on purpose. Existing `.superpowers/` data from earlier hybrid runs is not migrated.

### Added
- Shared opencode models from the env vars `HYBRID_OPENCODE_STD` (required) and `HYBRID_OPENCODE_LITE` (optional, defaults to `STD`), each `provider/model[#variant]`, loaded through the vendored `scripts/hybrid_shared.py`. All hybrid skills read them as the default source of model and variant for the tiers `std` and `lite`. Set them in the `env` block of `~/.claude/settings.json` (restart Claude Code) or export them in the shell.
- Per-tier override: a tier whose `model` is set in `<skill dir>/routing.json` uses that file's `model` and `variant` (no variant when the file sets none, never the shared variant); every other tier uses the shared env vars. `max_parallel` comes from the per-skill file, else the shipped defaults. `hybrid_shared.resolve_tiers` records each tier's source (`skill`, `shared` or `none`), and shared-model problems are reported only when some tier needs them.
- SKILL.md step 0: the run mode (hybrid, Claude only or opencode only) is asked once per run, taken from `mode=` in the args when present, and passed on in hand-offs.
- Preset `opencode`, replacing `max`. `max` is still accepted as an alias and prints `OC-WARN ... kind=config`. In preset `opencode` a lane that cannot run on opencode is held instead of falling back to Claude.
- Immediate failure reporting: `OC-ERROR` / `OC-WARN` lines are printed when a failure happens, appended to `oc-errors.jsonl`, and `bslane.py` exits 3 when a lane failed on opencode. SKILL.md has a relay rule that puts each such line at the start of the next message to the user.
- `context.sh` prints one `shared config:` line with the source label `$HYBRID_OPENCODE_STD/$HYBRID_OPENCODE_LITE`, the `std`/`lite` specs each marked `(skill)` or `(shared)`, and the validation state. The mode question shows the same specs and sources. It stays read-only, bounded and exits 0.
- README documents run modes, the shared env vars, failure kinds, the `disabled` routing key and `bslane.py stats`. SKILL.md mentions `bslane.py stats`.
- Retries: a lane that fails on opencode with a connection kind (`spawn`, `stall`, `throttle`, `crash`) is re-run from scratch up to 3 times, waiting 10, 30 and 60 s (`HYBRID_OC_RETRY_DELAY_S` overrides every delay; tests set `0`). Each failed try prints and logs `OC-WARN ... kind=<kind> :: retry <n>/3 in <s>s: <detail>`. The lane keeps its slot while it waits.
- Run switch in mode `hybrid`: when the retries run out, or at once for `auth`, `quota` and `model`, the rest of the run moves to Claude Sonnet 5.5 (`model: sonnet`). `bslane.py` prints and logs one `OC-ERROR ... kind=switch` line and records `lanes/oc-switched.json`. The failed lane's `FALLBACK`/`CLAUDE` line uses `model: sonnet`. Every later call for a role that would run on opencode spawns nothing and prints only a `CLAUDE ... model: sonnet` line with no OC line. A lane that is waiting to retry stops spawning once another lane has switched the run. Lanes already on opencode finish normally.
- `bslane.py init`, run by SKILL.md right after Step 0 in modes `hybrid` and `opencode`, clears the previous run's `oc-switched.json` and circuit breakers. The lane state directory is per project, so without it a switch (or an open breaker) would carry over into the next run.
- `hb_prompts.claude_line` takes an optional `model` that overrides the role's default model.

### Changed
- Mode `opencode` also retries connection failures, but after the retries nothing changes: the lane is held, the breaker trips for the non-retryable kinds and there is no switch. `timeout`, `context` and the gate kinds (`grounding`, `format`, `empty`) are never retried or switched: a per-lane fallback in `hybrid`, held in `opencode`.
- The shared model file (with its path override), `hybrid_shared.py init` and the shared `max_parallel` are removed with no fallback: set `HYBRID_OPENCODE_STD` (and optionally `HYBRID_OPENCODE_LITE`) instead, and set `max_parallel` only in `<skill dir>/routing.json`.
- The per-skill user routing file now defaults to `<skill dir>/routing.json`, next to `routing.default.json` (it used to live under `~/.config`, with no fallback to that location). `HYBRID_BRAINSTORMING_ROUTING` still overrides.
- `model` and `variant` are removed from `routing.default.json`. A per-skill user file may still set them per tier, and then it wins for that tier over the shared env vars.
- `doctor` no longer copies the shipped defaults into `<skill dir>/routing.json`.
- A per-run circuit breaker replaces the persistent tier "down" marks for non-retryable failures (`auth`, `quota`, `model`, `config`). Throttle keeps its cooldown.
- `context.sh` prints a stale line instead of the cached status line when the doctor cache file is older than 10 minutes (the doctor TTL).
- README no longer promises "one NOTE" when opencode is missing; it describes the `OC-ERROR` line that is printed instead.

### Fixed
- Re-synced the visual-companion scripts (`server.cjs`, `start-server.sh`, `stop-server.sh`, `helper.js`, `frame-template.html`, `visual-companion.md`) with `brainstorming-6.3`, and ported its `context.sh` fixes (scoped, capped `hot_dirs_30d`; one-line `package.json` in `npm_deps`). SKILL.md `allowed-tools` pins the start/stop scripts and `kill -0` again.
- The doctor now runs in the flow: `bslane.py` refreshes it (with a ping, once, under a lock) before routing when the needed tier's entry is missing or stale. A failed refresh prints an `OC-ERROR` line, then falls back (hybrid) or holds (opencode). Every unserved lane, including cooldown, busy and unreadable `--context-file` cases, prints an OC line.
- A plain `doctor` keeps the `websearch` answer of an earlier `--ping` (same model); a tier with no model is no longer reported stale; a failed ping stores a non-empty `kind`.
- A passing `doctor --ping` clears that tier's circuit breaker and cooldown, so "retry on opencode" works; `init` also clears `cooldown-<tier>`. SKILL.md maps the HELD answers to these commands.
- `init`, `stats` and `doctor` accept and ignore `--preset`. A lane that waited for a slot re-checks the switch, breaker and cooldown before spawning. In mode `opencode` a role pinned to `claude` goes to Claude instead of being held. A held explicit `--backend oc:<tier>` reports the requested tier. An opencode-mode crash is held, with no FALLBACK. `stats` prints the `kind=breaker` summary.
- Wrong-typed routing keys (`roles`, `max_parallel`, `slot_wait_s`, `stall_s`, `tiers.lite`, ...) become `config_problems` instead of crashing or silently dropping defaults.
- Grounding gate: a fact without a backticked identifier needs a claim word near the cited line; a quote must come from a fetched page (not a search result) and have at least 3 words; bullets wrapped onto two lines, `path:line: fact`, ranges past EOF and URLs ending in `)` are handled.
- `context.sh` reports a truncated `routing.json` as invalid and blames the right file for a bad model. architectural.md hands off with `mode=<mode>` and its draft routing matches SKILL.md.
- The relay rule now has the full text used by hybrid-team (verbatim relay, deduplication, "say how many more matched", never informational).

## v1.0.0 (2026-09-28)

Initial release of `hybrid-brainstorming`, a fork of `brainstorming-6.3`.

### Added
- New `bslane.py` CLI: router and runner for brainstorming lanes via opencode or Claude.
- Backend routing via `routing.default.json` and `<skill dir>/routing.json`.
- Three presets: `claude` (brainstorming-6.3 equivalent), `hybrid` (opencode for code and fact lanes), `max` (opencode for more lanes).
- Grounding gate: code findings must cite real `path:line`; web claims must quote fetched text.
- Automatic fallback to Claude for lanes with ungroundable output.
- Doctor CLI: check opencode availability, routing config, and context status.
- Telemetry: JSON telemetry per lane to `lanes.jsonl`, recording role, tier, model, variant, duration, tokens, grounded `n/m`, outcome and reason.
- Stdlib modules: `oc_run.py` (opencode runner and event parser), `hb_router.py` (role routing and preset logic), `hb_ground.py` (grounding gate), `hb_prompts.py` (lane prompt templates), `hb_config.py` (opencode agent config), `hb_doctor.py` (availability and status).
- Vendored opencode runner: opencode logic is copied from hybrid-team, not shared at runtime.
- SKILL.md frontmatter: `name: hybrid-brainstorming`, an opt-in description, and `allowed-tools` extended with the `bslane.py` pin.
- Lane state files under `.hybrid-superpowers/brainstorm/`: `lanes/<id>.jsonl` (per-lane event log), `lanes/<id>.err` (lane stderr), `lanes/<id>.claude.md` (Claude fallback prompt), `lanes/<id>.out.md` (lane output), `lanes/slots/<tier>.<k>.lock` (slot lock), `lanes/cooldown-<tier>` (throttle cooldown expiry timestamp), `lanes/doctor/doctor-ping-<tier>.out.jsonl`/`.err` and `lanes/doctor/doctor-websearch.out.jsonl`/`.err` (doctor probe streams), and `lanes.jsonl` (aggregate per-lane telemetry).

### Unchanged
- Main thread work: classification, T0, synthesis, design, spec, self-review all stay on Claude.
- Claim verifier and spec pre-draft always run on Claude.
- Output files: approved design and spec at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, then `writing-plans`.
- Lane prompt output shapes and visual companion format.
