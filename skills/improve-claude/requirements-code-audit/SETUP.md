# Setup — requirements-code-audit

The folder works at three levels. Pick the highest one your environment allows; the skill detects the rest.

| Level | What loads | Speed / hardening |
|---|---|---|
| **Plugin (recommended)** — folder copied to `~/.claude/skills/` with its `.claude-plugin/plugin.json` | skill + agents `req-audit:rca-investigator/verifier/parser` + guard hooks | 64-way fan-out, tool-restricted workers (no shell), git-history/docs/writes blocked structurally, zero permission prompts for audit-dir writes and the bundled script |
| **Local agents** — plain skill + `agents/*.md` copied into `.claude/agents/` | skill + agents `rca-*` (with `permissionMode: acceptEdits`) | same speed; hooks only if you add them to settings (below) |
| **Generic** — SKILL.md + scripts only (also Cowork / claude.ai upload) | skill; workers are `general-purpose` subagents on `haiku`/`sonnet` | same speed where an Agent tool exists; rules are prompt-enforced |

## 1. Install (Claude Code)

```bash
# personal scope: loads in every project, no trust dialog, no install step
cp -R requirements-code-audit ~/.claude/skills/requirements-code-audit
chmod +x ~/.claude/skills/requirements-code-audit/hooks/audit_guard.sh ~/.claude/skills/requirements-code-audit/scripts/audit.py
```

Restart Claude Code (or run `/reload-plugins`). Verify: `/agents` lists `rca-investigator`, `rca-verifier`, `rca-parser`;
`/hooks` shows the plugin's `PreToolUse` and `SubagentStop` entries; `/req-audit:requirements-code-audit` appears in `/`.

Project scope instead: copy into `<repo>/.claude/skills/requirements-code-audit`. Skills-directory plugins load only
after you accept the workspace trust dialog and only from the session's primary working directory — launch Claude
Code from the repo root.

## 2. Raise the concurrency cap to 64

Claude Code (v2.1.217+) refuses to spawn more than **20** concurrent subagents by default. The skill plans around
whatever the cap is, but it is designed for 64. Add to `~/.claude/settings.json` (or the project's `.claude/settings.json`):

```json
{
  "env": { "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "64" }
}
```

Restart. `audit.py init` prints the cap it detected. Sessions with `ultracode` effort are exempt from the cap.

Optional, subscription plans only: keep worker prompt caches warm for an hour during very long audits by adding
`experimental:\n  cacheTtl: 1h` to the agent files (v2.1.248+). Not needed for normal runs.

## 3. Permissions — what to expect

- Read/Grep/Glob inside the working directory never prompt. Workers write only under `<cwd>/.audit/`.
- Plugin level: the guard hook auto-approves writes under the audit dir and calls to `scripts/audit.py`, so the audit
  runs prompt-free even in Manual permission mode. Auto mode (Pro/Max/Team default) is also prompt-free.
- Local-agents level in Manual mode: the agents' `permissionMode: acceptEdits` covers their writes; to also avoid
  prompts for the script add `"Bash(python3 ~/.claude/skills/requirements-code-audit/scripts/*)"` to
  `permissions.allow` in `.claude/settings.local.json`.
- The guard is armed only while `<cwd>/.audit/ACTIVE` exists (created by `audit.py init`, removed by `audit.py finish`).
  Outside an audit it exits in a few milliseconds and does nothing.

## 4. Hooks at the local-agents level (optional)

Add to `.claude/settings.local.json` (adjust the path):

```json
{
  "hooks": {
    "PreToolUse": [{ "matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit|Read|Grep|Glob",
                     "hooks": [{ "type": "command", "command": "\"$HOME/.claude/skills/requirements-code-audit/hooks/audit_guard.sh\"" }] }],
    "SubagentStop": [{ "matcher": ".*",
                       "hooks": [{ "type": "command", "command": "\"$HOME/.claude/skills/requirements-code-audit/hooks/audit_guard.sh\"" }] }]
  }
}
```

## 5. Windows

Use `python` instead of `python3` in the `allowed-tools` line of `SKILL.md` and when calling the script. The bash
launcher needs Git Bash; without it, point the hook commands at `python hooks/audit_guard.py` directly (the fast-path
marker check is then skipped — the Python script does the same check).

## 6. Where things go

- `<cwd>/.audit/` — everything the audit writes (checklist, batches, findings, verdicts, report, CSV). Added to
  `.git/info/exclude` automatically (local, untracked; the codebase is not modified).
- `audit.py init --force` archives a previous audit to `.audit.prev-<timestamp>/`.
- Uninstall: delete the skill folder. Nothing else is written outside audit dirs.

## 7. Cowork / claude.ai

Upload the `.skill` file (or the folder). Agents and hooks are ignored there; the skill runs in generic mode
(general-purpose subagents with `model: haiku`/`sonnet`) or solo mode when no Agent tool exists. The repo must be
mounted in the session so `scripts/audit.py` can scan it.
