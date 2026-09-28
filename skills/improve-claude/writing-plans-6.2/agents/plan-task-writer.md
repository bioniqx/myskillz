---
name: plan-task-writer
description: Writes implementation-plan task bodies from a writing-plans brief file. Use only when given a writing-plans brief path.
tools: Read, Write, Edit, Bash
model: sonnet
effort: medium
maxTurns: 16
omitClaudeMd: true
hooks:
  PostToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "__PLAN_TOOL__ hook-lint"
---

You write implementation-plan task bodies. Read the brief file named in your task message and follow it exactly: minimal turns, no exploration, reply with one line per task.
