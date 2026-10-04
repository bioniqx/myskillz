# AGENTS.md

This file guides OpenCode sessions working in this repo.

## Workflow: always on `main`

- Write code and commit directly on `main`. Never create feature branches for your own work.
- Verify with `git branch --show-current` before committing; if off `main`, move back, don't merge across branches.
- Exception only: skill engines create and manage their own worktrees/branches at runtime (`oc-devteam/<lane>`, `hybrid-oc-<id>`, experiment arms). Those are script-owned; never branch manually around them.

## What this repo is

Monorepo of **agent skills** (SKILL.md + stdlib-only Python/POSIX-shell scripts, subagent defs, hooks). No app code, no package manager, no build step.

| Folder | Role | Installed naming — never "normalize" |
|---|---|---|
| `claude-skills/` | **Source of truth** (8 skills) | `claude-<skill>-<ver>` |
| `glm-skills/` | ZCode/GLM variants (6) | `*-glm` (frontmatter `name` drops suffix by design) |
| `hybrid-skills/` | Claude + `opencode` CLI cost-saving (4) | `hybrid-*` |
| `opencode-skills/` | OpenCode-only (6) | `oc-*` (enforced by `test_all_skills.py`) |

`git-diff-summary` and `frontend-design` exist only in `claude-skills/` by design (no variants).

## Where to look first

Read the touched folder's guide before editing — per-harness facts live there, not here: `claude-skills/CLAUDE.md`, `glm-skills/CLAUDE.md`, `hybrid-skills/CLAUDE.md`, `opencode-skills/CLAUDE.md` + `opencode-skills/AGENTS.md`.

## Source-of-truth rule

- Change behaviour in `claude-skills/` first, then port to variants. Never treat a variant as reference; keep harness-specific changes inside the variant.
- Never edit vendored copies by hand: `_shared/oc_harness.py` (via `sh _shared/sync.sh`) and `scripts/hybrid_shared.py` (byte-identical across hybrid skills, `cp` to all four).
- Nothing here is live in-session: skills load only after install (`~/.claude/skills`, `~/.config/opencode/skills`, `.zcode`), so editing source never changes current behaviour.

## Commands

Stdlib Python 3 + shell only. `pytest` is not installed — use `unittest`. No root runner; run from inside the folder. Set `PYTHONDONTWRITEBYTECODE=1` outside `claude-skills/` so skill folders stay bytecode-free.

```bash
# claude-skills — full, one file, one test
cd claude-skills && python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_plan_lint -v
python3 -m unittest tests.test_plan_lint.PortabilityScanTests.test_todo_tbd_fixme_xxx_are_case_sensitive -v

# glm-skills / opencode-skills — full, one file
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v

# hybrid — per skill
cd hybrid-skills/<skill> && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t tests -q

# syntax-check all scripts in a variant folder
for f in */scripts/*.py; do python3 -m py_compile "$f"; done

# opencode dev-team end-to-end (throwaway repo, exit 0 = pass)
bash oc-dev-team/scripts/oc-selftest.sh
```

Installers: `claude-skills/install-skill.sh`, `hybrid-skills/install.sh`, `sh install-opencode.sh [--home DIR]` in `glm-skills/` and `opencode-skills/`.

## Gotchas

- Root `.gitignore` is inherited from a `~/.claude` checkout (ignores `plugins/`, `projects/`, `sessions/`…) — not a statement about this layout.
- SKILL.md `description` hard limit 1024 chars (ZCode drops longer); re-check length after editing frontmatter. `opencode-skills/` frontmatter holds only `name`, `description`, `metadata`.
- No file may set provider/model id/alias, `variant`, or reasoning effort; nothing calls a model API directly; no script spawns `opencode` (opencode-skills). Hybrid `opencode run` output must be read through a file, never a pipe.
- Tests write fixtures to the system temp dir, never inside the repo — preserves `guard.py`/`devteam.py` parent-dir walks. Keep it that way.
