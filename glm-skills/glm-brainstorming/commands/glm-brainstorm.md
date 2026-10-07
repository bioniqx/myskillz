---
description: Turn intent into an approved design: preloaded repo context, parallel lanes, one approval gate.
---
!`sh {{SKILL_DIR}}/scripts/context.sh`

A raw `!` line above instead of output (`opencode run` does not expand
`!` in commands): run `sh {{SKILL_DIR}}/scripts/context.sh` with the
shell tool first and use its output as the context block. One call, then
continue.

Skill path: {{SKILL_DIR}}

Load skill glm-brainstorming with $ARGUMENTS.
