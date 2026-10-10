# AGENTS.md

Guidance for agents working in `glm-skills/`. Read together with `CLAUDE.md` (architecture,
commands, per-skill engines and conventions) - it stays the detailed reference for this folder.

## Skill quality criteria (mandatory)

Every skill written or edited in this folder MUST satisfy [docs/skill-criteria.md](docs/skill-criteria.md)
before it is committed. In short: ZCode hard limits (description at or under 1024 chars with the
WHEN clause inside the first 250, body under 500 lines and under the 100KB truncation, frontmatter
`name` equal to the directory name), a pushy third-person description, an imperative body with
progressive disclosure into `references/`, scripts for deterministic work, and none of the
anti-patterns listed there. Run the SKILL.md hygiene suite after every frontmatter edit:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v
```
