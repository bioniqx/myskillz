---
description: Turn intent into an approved design: preloaded repo context, parallel lanes, one approval gate.
---

The first call is `python3 {{SKILL_DIR}}/scripts/handoff.py open --self glm-brainstorming` with the user's arguments on stdin. That one call runs `sh {{SKILL_DIR}}/scripts/context.sh` and `ask.py mode`. Do not run those yourself. The default is FAST: `MODE fast` means follow the PACE fast NEXT. `MODE slow` means follow the prelude's `NEXT` only. `OPEN: routed` means follow `NEXT:` and do not design.

Skill path: {{SKILL_DIR}}

Load skill glm-brainstorming with $ARGUMENTS.
