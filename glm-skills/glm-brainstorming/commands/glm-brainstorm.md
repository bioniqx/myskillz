---
description: Turn intent into an approved design: preloaded repo context, parallel lanes, one approval gate.
---

Run `sh {{SKILL_DIR}}/scripts/context.sh` with the shell tool first and use its output as the context block. In that same first message, run `python3 {{SKILL_DIR}}/scripts/ask.py mode` with the user's arguments on stdin. `MODE ask` means show the ASK block and wait. `MODE fast` means read `fast.md` in this skill. `MODE normal` means continue with the skill's gates.

Skill path: {{SKILL_DIR}}

Load skill glm-brainstorming with $ARGUMENTS.
