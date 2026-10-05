# Setup — hybrid-requirements-code-audit

hybrid-requirements-code-audit is an opt-in fork of requirements-code-audit: the same audit, with investigators and spec
parsers (and, in mode `opencode`, verifiers) run on the opencode CLI while every judgment step stays on Claude. It ships no
agents or plugin manifest of its own and only an optional guard hook (`hooks/audit_guard.py`, section 5): it reuses the `claude-rca-*` agents of the installed claude-req-audit
plugin (the `requirements-code-audit` skill). It works at the same three levels. Pick the highest one your environment
allows; the skill detects the rest.

| Level | What loads | Speed / hardening |
|---|---|---|
| **Plugin (recommended)** — `requirements-code-audit` copied to `~/.claude/skills/` with its `.claude-plugin/plugin.json`, this folder next to it | this skill + the plugin's agents `claude-req-audit:claude-rca-investigator/verifier/parser` | parallel fan-out up to the live cap, tool-restricted workers (no shell); with this fork's guard hook registered (section 5) git-history, docs and writes are blocked structurally and audit-dir writes and this skill's `scripts/audit.py` (every `oc-run` included) need no permission prompt |
| **Local agents** — this skill + requirements-code-audit's `agents/*.md` copied into `.claude/agents/` | this skill + agents `claude-rca-*` (with `permissionMode: acceptEdits`) | same speed; hooks only if you add them to settings (below) |
| **Generic** — this folder only (also Cowork / claude.ai upload) | this skill; workers are `general-purpose` subagents on `haiku`/`sonnet` | same speed where an Agent tool exists; rules are prompt-enforced |

opencode is independent of the level. When it is missing or unhealthy, `init` prints
`opencode: unavailable preset=hybrid (run audit.py doctor --ping)` and in mode hybrid the audit runs exactly as
requirements-code-audit does (in mode opencode the units are held).

## 1. Install (Claude Code)

```bash
# personal scope: loads in every project, no trust dialog, no install step
cp -R hybrid-requirements-code-audit-v1.0 ~/.claude/skills/hybrid-requirements-code-audit-v1.0
chmod +x ~/.claude/skills/hybrid-requirements-code-audit-v1.0/scripts/audit.py ~/.claude/skills/hybrid-requirements-code-audit-v1.0/hooks/audit_guard.sh
# recommended: the claude-req-audit plugin that provides the agents (skip if already installed)
cp -R requirements-code-audit ~/.claude/skills/requirements-code-audit
chmod +x ~/.claude/skills/requirements-code-audit/hooks/audit_guard.sh ~/.claude/skills/requirements-code-audit/scripts/audit.py
```

Restart Claude Code (or run `/reload-plugins`). Verify: `/hybrid-requirements-code-audit` appears in `/`; with the
plugin, `/agents` lists `claude-rca-investigator`, `claude-rca-verifier`, `claude-rca-parser` and, once you register this fork's guard (section 5), `/hooks` shows its `PreToolUse`
and `SubagentStop` entries.

Project scope instead: copy both folders into `<repo>/.claude/skills/`. Skills-directory plugins load only after you
accept the workspace trust dialog and only from the session's primary working directory — launch Claude Code from the
repo root.

## 2. Check the concurrency cap (optional)

Claude Code (v2.1.217+) refuses to spawn more than **20** concurrent subagents by default. The skill plans around
whatever the cap is (default 20) and fans out at most 12 Claude investigators at once, so a cap of 12 or more is enough and there is no need for 64. To set it explicitly, add to `~/.claude/settings.json` (or the project's `.claude/settings.json`):

```json
{
  "env": { "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "20" }
}
```

Restart. `audit.py init` prints the cap it detected. Sessions with `ultracode` effort are exempt from the cap.

opencode batches are background Bash processes, not subagents, so they do not count against this cap. Each routing
tier runs at most its own `max_parallel` batches at once, and never more than the shared pool (`HYBRID_OPENCODE_POOL`, default 6, max 8) opencode batches run at once across tiers (section 3).

Optional, subscription plans only: keep worker prompt caches warm for an hour during very long audits by adding
`experimental:\n  cacheTtl: 1h` to the claude-req-audit plugin's agent files (v2.1.248+). Not needed for normal runs.

## 3. opencode and routing

1. Install the opencode CLI (tested with v2.0.19) and set up the provider that serves the tier models, so that `opencode models` lists them.
2. Set the shared models in two env vars that all four hybrid skills read: `HYBRID_OPENCODE_STD` (required, tier `std`) and `HYBRID_OPENCODE_LITE` (optional, tier `lite`, defaults to the `std` value). Each is `provider/model[#variant]`, where `#variant` is the optional thinking level. Put them in the `"env"` block of `~/.claude/settings.json`, then restart Claude Code:

   ```json
   {"env": {"HYBRID_OPENCODE_STD": "opencode/muse-spark-1.3-contributor-free#xhigh"}}
   ```

   Exporting them in the shell also works. The slot cap `max_parallel` (default 4 per tier) can be set for all four hybrid skills with the env var `HYBRID_OPENCODE_MAX_PARALLEL` (1 to 8), and the cross-tier pool with `HYBRID_OPENCODE_POOL` (1 to 8, default 6; `audit.py doctor` prints the effective value), or `max_parallel` per skill in the routing file (below), which wins.
3. Run the doctor once with `python3 ~/.claude/skills/hybrid-requirements-code-audit-v1.0/scripts/audit.py doctor --ping`. It validates the shared env vars, checks `opencode --version`, confirms that `opencode models` lists each tier's model, sends each tier one tiny prompt through the injected `hybrid-audit-investigator` agent (it must answer `HA-INVESTIGATOR-OK`) and writes the doctor cache that the `opencode:` line of `init` reads. Every unusable tier and every config problem prints as an `OC-ERROR` line; one tier's failure never disables the other. It never creates or edits a config file; its ping logs (`doctor-ping-<tier>.jsonl/.err`) go to the cache folder, never into a repo. It works outside an audit. Run it again after changing the env vars or the routing file, and when `init` shows `opencode: unavailable`, `claude(down: <kind>)` or `held(...)`. A cache entry is valid for the exact `model#variant` it checked and for a limited time. `init` refreshes a missing or stale entry with one ping for the tiers its mode uses (never in mode `claude`), then freezes the result for that audit.

The opencode agents (`hybrid-audit-investigator`, `hybrid-audit-verifier`, `hybrid-audit-parser`) are injected per turn through
`OPENCODE_CONFIG_CONTENT`; nothing is written to `~/.config/opencode` or to the repo. They are read-only: edits, shell,
web access and sub-tasks are denied, and so are reads of docs, `.git/` and the audit dir. `audit.py oc-run` writes their
output after an evidence oracle has checked every citation.

**Routing file:** optional. `<skill dir>/routing.json` (next to `routing.default.json`, e.g. `~/.claude/skills/hybrid-requirements-code-audit-v1.0/routing.json`), or the path in env `HYBRID_AUDIT_ROUTING`, is deep-merged over the shipped `routing.default.json` (dicts merge key by key, other values replace), so it only needs the keys you change, for example `{"roles": {"investigator": "lite"}}`. The skill never creates it. Models and thinking levels normally come from the shared env vars; a `tiers.<tier>.model` set here overrides the shared model for that tier only, together with this file's own `variant` (never mixed with the shared variant). `audit.py doctor` marks each tier `(skill)` or `(shared)`. The shipped defaults:

    {"preset": "hybrid",
     "tiers": {
       "std":  {"max_parallel": 4, "stall_s": 180, "timeout_s": 900},
       "lite": {"max_parallel": 4, "stall_s": 120, "timeout_s": 600}},
     "roles": {"investigator": "std", "verifier": "claude", "parser": "std"},
     "max_roles": {"verifier": "std", "parser": "std"},
     "oc_batch_max": 4, "oc_overflow": "queue", "max_repairs": 2, "throttle_cooldown_s": 120}

| Mode (`preset`) | investigator | verifier | parser |
|---|---|---|---|
| `claude` | Claude | Claude | Claude (output byte-identical to requirements-code-audit) |
| `hybrid` (default) | `roles.investigator` (`std`) | `roles.verifier` (`claude`) | `roles.parser` (`std`) |
| `opencode` | `max_roles.investigator`, else `roles.investigator` (`std`) | `max_roles.verifier` (`std`) | `max_roles.parser` (`std`) |

- `init --preset claude|hybrid|opencode` overrides the file's `preset` for one audit; SKILL.md asks for it once per audit. `max` is a deprecated alias of `opencode` and prints one `OC-WARN` line. `config.json` keeps the effective preset and a snapshot of the merged routing.
- A role value of `claude` means Claude; any other value names a tier. `max_roles` is the role table of mode `opencode` (the key keeps its old name).
- `max_parallel`: opencode batches a tier runs at once (1 to 8; a larger value is clamped to 8, and all tiers together never run more than the shared pool of opencode calls at once, parser and verifier waves included; `HYBRID_OPENCODE_POOL`, default 6, 1 to 8, so a tier effectively runs `min(max_parallel, pool)`). `oc_batch_max`: items per opencode batch. Batches beyond `max_parallel` wait for a free opencode slot and are dispatched by `status` as slots free up (a waiting batch is never hedged). `oc_overflow` (`"queue"` default, or `"claude"`): with `"claude"`, mode hybrid sends the active items beyond `max_parallel × oc_batch_max` to Claude haiku batches at `plan` time instead of queueing them; mode opencode always queues. An unusable tier still sends everything to Claude in mode hybrid.
- `stall_s` and `timeout_s` apply to each opencode turn. `max_repairs` caps the repair turns (same session) per batch, so a batch's worst case is `(1 + max_repairs) × timeout_s`.
- `throttle_cooldown_s`: after a rate-limit failure, the tier's queued batches wait or go to Claude for this many seconds.
- A tier that fails with `auth`, `quota`, `model` or `config` opens the run's circuit breaker (kept under `.hybrid-audit/`): later units skip that tier without spawning opencode until the next audit.
- A failed opencode run of kind `spawn`, `stall`, `throttle` or `crash` is retried up to 3 times (10 s, 30 s, 60 s apart; `HYBRID_OC_RETRY_DELAY_S` overrides the waits). In mode hybrid, once the retries are used up (or at once for `auth`, `quota`, `model`, `config`), the rest of the run switches to Claude Sonnet 5.5 (`model: sonnet`): one `OC-ERROR ... kind=switch` line, the record `.hybrid-audit/oc-switched.json`, and no further opencode spawns or `OPENCODE` blocks until the next `init`. Mode opencode retries too but never switches; the unit is held as before.
- In mode opencode a unit without a usable tier is held, never run on Claude by itself; SKILL.md "Held units" says how the user answers.

**Environment overrides:**

| Variable | Default | Meaning |
|---|---|---|
| `HYBRID_AUDIT_OC_BIN` | `opencode` | opencode binary |
| `HYBRID_AUDIT_ROUTING` | `<skill dir>/routing.json` | user routing file |
| `HYBRID_OPENCODE_STD` | none (required for modes `hybrid` and `opencode`) | shared model of tier `std`, `provider/model[#variant]` (all four hybrid skills) |
| `HYBRID_OPENCODE_LITE` | the `HYBRID_OPENCODE_STD` value | shared model of tier `lite` |
| `HYBRID_AUDIT_DOCTOR_CACHE` | `~/.cache/hybrid-requirements-code-audit/doctor.json` | doctor cache |
| `HYBRID_AUDIT_TELEMETRY` | `~/.cache/hybrid-requirements-code-audit/lanes.jsonl` | telemetry log |
| `HYBRID_AUDIT_FAKE_SCRIPT`, `HYBRID_AUDIT_FAKE_LOG` | none | tests only (`tests/fake_opencode.py`) |

## 4. Permissions — what to expect

- Read/Grep/Glob inside the working directory never prompt. Workers write only under `<cwd>/.hybrid-audit/`; opencode
  workers write nothing themselves.
- With this fork's guard hook registered (section 5), the hook auto-approves writes under the audit dir and calls to this skill's `scripts/audit.py`
  (the `scripts_dir` recorded in `config.json`), including every background `oc-run`, so the audit runs prompt-free
  even in Manual permission mode. Auto mode (Pro/Max/Team default) is also prompt-free.
- Local-agents level in Manual mode: the agents' `permissionMode: acceptEdits` covers their writes; to also avoid
  prompts for the script add `"Bash(python3 ~/.claude/skills/hybrid-requirements-code-audit-v1.0/scripts/*)"` to
  `permissions.allow` in `.claude/settings.local.json`. The `OPENCODE` lines run
  `python3 "<absolute scripts dir>/audit.py" oc-run <name>`; add a matching rule if they still prompt.
- The guard is armed only while `<cwd>/.hybrid-audit/ACTIVE` exists (created by `audit.py init`, removed by
  `audit.py finish`). Outside an audit it exits in a few milliseconds and does nothing.

## 5. Guard hook (optional, any level)

The guard ships with this fork (`hooks/audit_guard.sh` launches `hooks/audit_guard.py`). The original skill's guard only watches `.audit/` and never arms for `.hybrid-audit/`. Add to `.claude/settings.local.json` (adjust the path):

```json
{
  "hooks": {
    "PreToolUse": [{ "matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit|Read|Grep|Glob",
                     "hooks": [{ "type": "command", "command": "\"$HOME/.claude/skills/hybrid-requirements-code-audit-v1.0/hooks/audit_guard.sh\"" }] }],
    "SubagentStop": [{ "matcher": ".*",
                       "hooks": [{ "type": "command", "command": "\"$HOME/.claude/skills/hybrid-requirements-code-audit-v1.0/hooks/audit_guard.sh\"" }] }]
  }
}
```

## 6. Windows

Use `python` instead of `python3` in the `allowed-tools` line of `SKILL.md` and when calling the script, including the
printed `oc-run` commands. Set `HYBRID_AUDIT_OC_BIN` when opencode is not on `PATH` as `opencode`. The guard's bash launcher
(`hooks/audit_guard.sh`) needs Git Bash; without it, point the hook commands at `python hooks/audit_guard.py` of this fork directly (the fast-path marker check is then skipped — the Python script does the same check).

## 7. Where things go

- `<cwd>/.hybrid-audit/` — everything the audit writes (checklist, batches, findings, verdicts, report, CSV). Added to
  `.git/info/exclude` automatically (local, untracked; the codebase is not modified). This includes the `*.oc.md`
  briefs next to their Claude briefs and `.hybrid-audit/oc/`, the opencode scratch dir: each turn's raw event stream
  `<name>.<round>.jsonl` and stderr `<name>.<round>.err`, plus the event files set aside after a fallback.
- `audit.py init --force` archives a previous audit to `.hybrid-audit.prev-<timestamp>/`.
- Outside audit dirs, shared by every repo and separate from the other hybrid skills:
  - `~/.cache/hybrid-requirements-code-audit/doctor.json` — the doctor cache;
  - `~/.cache/hybrid-requirements-code-audit/lanes.jsonl` — telemetry: one record per opencode run and one per
    requirement at `finish`, each with the repo root. `audit.py stats [--repo <path>]` compares opencode against Claude.
- Uninstall: delete the skill folder (this also removes its optional `routing.json`) and
  `~/.cache/hybrid-requirements-code-audit/`. Nothing else is written outside audit dirs. Keep requirements-code-audit
  installed if you still use it.

## 8. Cowork / claude.ai

Upload the `.skill` file (or the folder). Agents and hooks are ignored there and opencode is normally absent: `init`
prints `opencode: unavailable preset=hybrid (run audit.py doctor --ping)` and the skill runs as
requirements-code-audit does, in generic mode (general-purpose subagents with `model: haiku`/`sonnet`) or solo mode
when no Agent tool exists. The repo must be mounted in the session so `scripts/audit.py` can scan it.
