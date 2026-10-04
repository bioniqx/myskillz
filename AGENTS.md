# AGENTS.md

This file guides OpenCode sessions working in this repo.

## What this repo is

A monorepo of **agent skills** (SKILL.md instructions plus the stdlib-only Python/shell scripts, subagent
definitions and hooks behind them). There is no application code, no package manager and no build step.
Six core workflows (brainstorming, dev-team, doc-generator, requirements-code-audit,
systematic-debugging, writing-plans) exist as variants in the `glm-skills/` and `opencode-skills/` folders
(`hybrid-skills/` has four of them: brainstorming, dev-team, requirements-code-audit, writing-plans).
`claude-skills/` holds the originals: those six plus `git-diff-summary` and `frontend-design`, 8 skills in
total, and the last two have no variants by design. The four top-level folders are:

| Folder | Role | Naming |
|---|---|---|
| `claude-skills/` | **Original, source of truth** for Claude Code | `claude-<skill>-<ver>` |
| `glm-skills/` | Variants for ZCode / GLM (Z.ai route) | `<skill>-glm` |
| `hybrid-skills/` | Variants that mix Claude + the local `opencode` CLI to cut cost (Claude keeps all judgment, opencode executes low-judgment units behind a machine-checked oracle) | `hybrid-<skill>-v1.0` |
| `opencode-skills/` | Variants built only for opencode | `oc-<skill>` |

Each folder has its own guidance file (`CLAUDE.md`; `opencode-skills/` also has `AGENTS.md`). **Read the
one for the folder you are touching before editing** — they hold the per-skill architecture, harness
constraints and conventions, and are not repeated here.

## Working across folders

- **Change behaviour in `claude-skills/` first, then port.** Variants are derived from the originals;
  never treat a variant as the reference, and keep harness-specific changes inside the variant.
- Files under `hybrid-skills/`, `glm-skills/` and `opencode-skills/` have intentionally different
  frontmatter and installed names (e.g. the `-glm` suffix is dropped from `name`); don't "normalize" them
  back to the original's form.
- Nothing here is active in a Claude Code session: skills are loaded only after being installed into a
  harness skills dir (`~/.claude/skills`, `.opencode`, `.zcode`, ...), so editing a skill here does not
  change the current session's behaviour.

## Git workflow

- Always work directly on `main`: write code and commit on `main`, never create new branches.

## Commands

Everything is stdlib Python 3 + POSIX shell; `pytest` is not installed, use `unittest`. Run from inside the
folder, not the repo root (there is no root-level test runner).

```bash
# claude-skills/ — full suite, then a single file / class / test
cd claude-skills && python3 -m unittest discover -s tests -v
python3 -m unittest tests.test_plan_lint -v
python3 -m unittest tests.test_plan_lint.PortabilityScanTests.test_todo_tbd_fixme_xxx_are_case_sensitive -v

# glm-skills/ and opencode-skills/ — full suite; frontmatter/naming check only
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests
python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v

# hybrid-skills/ — each skill has its own tests/ dir
cd hybrid-skills/<skill> && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t tests -q
```

Installers: `claude-skills/install-skill.sh`, `hybrid-skills/install.sh`, and
`sh install-opencode.sh [--home DIR]` in `glm-skills/` and `opencode-skills/`.

## Repo gotchas

- The root `.gitignore` is inherited from a `~/.claude` checkout (it ignores `plugins/`, `projects/`,
  `sessions/`, ...); don't read it as a statement about this repo's layout.
- Skill descriptions have hard length limits in some harnesses (ZCode drops a skill whose `description`
  exceeds 1024 characters); re-check after editing frontmatter.
