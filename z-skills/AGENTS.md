# AGENTS.md

Guidance for agents working in `z-skills/`. Read together with `../CLAUDE.md` (the monorepo-level
reference for the whole skills repo: architecture, commands, gotchas) - it stays the detailed
reference for this folder.

## Target models and harnesses

These skills target four session models - GLM-5.3-Flash, DeepSeek-V4.1-Flash (model id
`deepseek-flash`), GLM-5.3 and DeepSeek-V4-Pro - and two harnesses: ZCode and DeepSeek Harness
(dsh). Declare them in each SKILL.md frontmatter (`metadata.models`, `metadata.harness`). The
provider route is picked at runtime by `_shared/flash_pin.py`: pin word in `~/.zcode/z-flash`
(`glm` or `deepseek`; env `GLM_FLASH` wins; `glm-5.3` / `deepseek-v4-pro` pin the pro lane). Keys:
GLM via `ZAI_API_KEY` (or the other `KEY_ENV` names in `zai_client.py`), DeepSeek via
`DEEPSEEK_API_KEY` / `DEEPSEEK_KEY`. Every change must keep all four models and both harnesses
working - never hardcode one provider or one harness.

## Layout

- `z-<skill>/` - one directory per skill: `SKILL.md` plus optional `references/`, `scripts/`,
  `agents/`, `commands/`.
- `_shared/` - source of truth for the Python helpers vendored into skills (see below) and
  `_shared/tests/` (the only test suite for this folder).
- `docs/` - `skill-criteria.md` (mandatory gate, below), `GLM_CODING_PROTOCOL_EN.md` (the coding
  protocol the target models must follow - read before changing skill-body rules), `plans/`, `specs/`.
- Installers: `install-zcode.sh` (skills + agents + commands into `~/.zcode`, tracked by a manifest)
  and `install-dsh.sh` (skills into the dsh home; dsh discovers only a root `SKILL.md` and requires
  a kebab-case `name` plus a non-empty `description`).

## Vendored scripts (architecture boundary)

`zai_client.py`, `flash_pin.py`, `handoff.py` and `decide.py` live once in `_shared/` and are copied
byte-identical into per-skill `scripts/` by `_shared/sync.sh`. Never edit a vendored copy directly:
edit `_shared/`, run `sh _shared/sync.sh`, then re-run the suite (`test_vendored.py` hashes every copy).

## Commands

stdlib Python 3 + POSIX shell only; run from inside `z-skills/`:

```bash
# full suite
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests

# SKILL.md hygiene only (frontmatter/naming limits)
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v
```

## Skill quality criteria (mandatory)

Every skill written or edited in this folder MUST satisfy [docs/skill-criteria.md](docs/skill-criteria.md)
before it is committed. In short: ZCode hard limits (description at or under 1024 chars with the
WHEN clause inside the first 250, body under 500 lines and under the 100KB truncation, frontmatter
`name` equal to the directory name), a pushy third-person description, an imperative body with
progressive disclosure into `references/`, scripts for deterministic work, and none of the
anti-patterns listed there. Run the SKILL.md hygiene suite (see Commands) after every frontmatter edit.
