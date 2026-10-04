# CLAUDE.md

@AGENTS.md

## Role in the skillz monorepo

`opencode-skills/` holds the **variants built specifically for opencode** (`oc-*`), derived from the
original skills in `../claude-skills/` (the source of truth). Sibling variants: `../glm-skills/` (ZCode /
GLM) and `../hybrid-skills/` (Claude + opencode cost saving). Port behaviour changes from the original.

This guide names the sibling folders and harnesses on purpose, so `_shared/tests/test_no_foreign_refs.py`
allowlists it. Do not copy those names into any other tracked file.
