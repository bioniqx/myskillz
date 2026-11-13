---
description: Turn intent into an approved design: preloaded repo context, parallel lanes, one approval gate.
---

The first call is `python3 {{SKILL_DIR}}/scripts/handoff.py open --self glm-brainstorming` with the user's arguments on stdin. That one call runs `sh {{SKILL_DIR}}/scripts/context.sh` and `ask.py mode`. Do not run those yourself. `MODE ask` means show the ASK block and wait. `MODE fast` means read `fast.md` in this skill. `MODE normal` means continue with the skill's gates. `OPEN: routed` means follow `NEXT:` and do not design.

Skill path: {{SKILL_DIR}}

Load skill glm-brainstorming with $ARGUMENTS.
