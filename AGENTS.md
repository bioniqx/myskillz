# AGENTS.md

Guidance for agents working in this repository.

## What this repo is

This is `~/.claude` — the live Claude Code user config directory — synced to GitHub as `bioniqx/myskillz`. It is a config/skills repo, not a software project: there is no root build, lint, or test command.

The working tree is the live config: edits take effect in Claude Code sessions immediately, committed or not. Commit freely; never push.

## Safety rails (do not bypass)

- `git push` is denied twice — a `permissions.deny` rule and a PreToolUse hook in `settings.json` (the denial reason is in Vietnamese). Commits and all other git commands are allowed; the user pushes manually.
- A PreToolUse hook (`rtk hook claude`) rewrites Bash commands through `rtk`, a token-optimizing proxy. Transparent and intentional; see `RTK.md`.

## Layout

- `skills/<dir>/SKILL.md` — the main content. The frontmatter `name:` is the skill's trigger id and drops the directory's version suffix: `dev-team-v3.2` → `name: dev-team`, `brainstorming-6.3` → `name: brainstorming`.
- `skills/glm-skills/` — GLM-5.3 ports of the versioned skills, self-contained with its own test suite and installer. Its `CLAUDE.md` is the authoritative guide (commands, architecture, harness gotchas) — read it before changing anything under `skills/glm-skills/`.
- `skills/synced/` — skills auto-synced from marketplaces/plugins (`docx`, `pdf`, `xlsx`, …). Auto-managed; do not hand-edit.
- `agents/` — global Claude Code subagents (all projects). `.claude/agents/` is a separate, diverged copy scoped to sessions working inside `~/.claude` itself. The two differ; know which one you are editing.
- `CLAUDE.md` — persona and working principles loaded into every session. `docs/superpowers/` — design specs from the GLM porting work (historical).
- Gitignored dirs (`sessions/`, `projects/`, `history.jsonl`, `shell-snapshots/`, `cache/`, …) are runtime state — never edit or commit them.
- Tracked residue exists (`.idea/`, `.DS_Store`, `debug/`, `feedback/`, `mcp-needs-auth-cache.json`); leave it unless asked.

## Gotchas

- **Installed skill copies are separate from this repo.** Claude Code does not load skills nested under `skills/glm-skills/`; OpenCode runs the `-glm` skills from installed copies in `~/.config/opencode/skills/`. Editing a skill here does not update the installed copy — re-run `skills/glm-skills/install-opencode.sh` (or the skill's `<tool>.py setup --harness opencode`).
- **Stale path references.** The tree was renamed `skills/glm` → `skills/glm-skills/`, but older docs and the permission allowlist in `.claude/settings.local.json` still reference `skills/glm/...`. Trust the real path.
- `skills/improve-claude/` is untracked and holds byte-identical copies of the versioned skills in `skills/` — scratch, not load-bearing.
