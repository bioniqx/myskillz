# CHANGELOG

## v1.0.0 (2026-09-28)

Initial release of `hybrid-brainstorming`, a fork of `brainstorming-6.3`.

### Added
- New `bslane.py` CLI: router and runner for brainstorming lanes via opencode or Claude.
- Backend routing via `routing.default.json` and `~/.config/hybrid-brainstorming/routing.json`.
- Three presets: `claude` (brainstorming-6.3 equivalent), `hybrid` (opencode for code and fact lanes), `max` (opencode for more lanes).
- Grounding gate: code findings must cite real `path:line`; web claims must quote fetched text.
- Automatic fallback to Claude for lanes with ungroundable output.
- Doctor CLI: check opencode availability, routing config, and context status.
- Telemetry: JSON telemetry per lane to `lanes.jsonl`, recording role, tier, model, variant, duration, tokens, grounded `n/m`, outcome and reason.
- Stdlib modules: `oc_run.py` (opencode runner and event parser), `hb_router.py` (role routing and preset logic), `hb_ground.py` (grounding gate), `hb_prompts.py` (lane prompt templates), `hb_config.py` (opencode agent config), `hb_doctor.py` (availability and status).
- Vendored opencode runner: opencode logic is copied from hybrid-team, not shared at runtime.
- SKILL.md frontmatter: `name: hybrid-brainstorming`, an opt-in description, and `allowed-tools` extended with the `bslane.py` pin.
- Lane state files under `.superpowers/brainstorm/`: `lanes/<id>.jsonl` (per-lane event log), `lanes/<id>.err` (lane stderr), `lanes/<id>.claude.md` (Claude fallback prompt), `lanes/<id>.out.md` (lane output), `lanes/slots/<tier>.<k>.lock` (slot lock), `lanes/cooldown-<tier>` (throttle cooldown expiry timestamp), `lanes/doctor/doctor-ping-<tier>.out.jsonl`/`.err` and `lanes/doctor/doctor-websearch.out.jsonl`/`.err` (doctor probe streams), and `lanes.jsonl` (aggregate per-lane telemetry).

### Unchanged
- Main thread work: classification, T0, synthesis, design, spec, self-review all stay on Claude.
- Claim verifier and spec pre-draft always run on Claude.
- Output files: approved design and spec at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, then `writing-plans`.
- Lane prompt output shapes and visual companion format.
