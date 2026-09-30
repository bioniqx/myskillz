---
name: skills-verification-commands
description: How to verify the claude-skills optimization run (git root, test/selftest commands, read-only hook limits, known seams)
metadata:
  type: project
---

Git root is the parent `skillz/` (not `claude-skills/`); run git/tests from there. The 2026-09-29 optimization run
(spec `claude-skills/docs/superpowers/specs/2026-09-29-claude-skills-optimization-design.md`) verified with:
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s claude-skills/tests -t claude-skills/tests`
- `bash claude-skills/dev-team-v3.2/scripts/selftest.sh` (250/250 on macOS after K08/F24)

**Why:** the read-only leader hook denies any command containing `>` redirects (even to scratchpad), so run tests
with `| tail` in background instead of redirecting. glm-skills commits inside the range come from a concurrent
glm run, not from the claude-skills run.

**How to apply:** when verifying, check `!` preloads for unquoted `$ARGUMENTS` (a free-text apostrophe cancels the
skill) — writing-plans was fixed, git-diff-summary was the leftover seam.
