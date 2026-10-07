# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role in the skillz monorepo

`glm-skills/` holds the **variants for ZCode / GLM**, derived from the original skills in
`../claude-skills/` (the source of truth). Sibling variants: `../hybrid-skills/` (Claude + opencode cost
saving) and `../opencode-skills/` (opencode-only). Port behaviour changes from the original rather than
editing the original from here.

## What this directory is

GLM-5.3 / GLM-5.3-Flash ports of the Claude-tuned originals in `../claude-skills/`
(`claude-brainstorming-6.3`, `claude-dev-team-v3.2`, `claude-doc-generator`,
`claude-requirements-code-audit`, `claude-systematic-debugging-6.3`, `claude-writing-plans-6.2`). Each
`glm-*/` folder is a self-contained skill meant to be installed into **ZCode** (or a Claude-compatible
harness). Claude Code does not load skills nested this deep, so nothing here is active in this session.
The git root is the skillz monorepo root (`../`), not this folder.

When a port changes behaviour, compare against the sibling original. Keep GLM-specific changes in the port
only; do not edit the originals from here.

## Commands

All scripts are stdlib-only Python 3 or POSIX shell. No build step, no dependencies to install (ripgrep
optional for the audit).

```bash
# glm-dev-team engine + hook guards: full end-to-end self-test in a throwaway repo (exit 0 = all pass)
bash glm-dev-team/scripts/selftest.sh

# Syntax check every script
for f in */scripts/*.py; do python3 -m py_compile "$f"; done

# Environment / key / endpoint checks (each script has one; --ping hits the live API)
python3 glm-systematic-debugging/scripts/debug_tool.py doctor --ping
python3 glm-requirements-code-audit/scripts/audit.py doctor --ping
python3 glm-writing-plans/scripts/plan_tool.py doctor --ping
python3 glm-dev-team/scripts/devteam.py doctor        # --fix writes .claude/settings.local.json + agents

# Print the install/config block for a harness
python3 <skill>/scripts/<tool>.py setup --harness zcode|claude

# Install all eight skills into ZCode: skills to ~/.zcode/skills/<name>, agents rewritten to ZCode
# frontmatter into ~/.zcode/agents. The agent install and the user-level hook merge into
# ~/.zcode/cli/config.json are delegated to devteam.py doctor in its zcode harness mode: a
# key-preserving merge (existing user keys survive, .bak before rewrite, re-run is a no-op) whose
# hook commands point at the installed skill's absolute guard.py path.
sh install-zcode.sh [--home DIR] [--flash MODEL_ID] [--main MODEL_ID] [--dry-run]

# Vendored-copy identity, py_compile and SKILL.md hygiene across all glm skills
python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v

# Full Python suite (all _shared/tests). __pycache__ is untracked/ignored; pass this env var to
# keep skill dirs free of bytecode.
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests
```

`_shared/*.py` (`zai_client.py`, `oc_harness.py`) is the source of truth; each skill's `scripts/` copy is
vendored from it by `sh _shared/sync.sh` — never edit a vendored copy by hand.

The Python suite under `_shared/tests` is the main automated suite and runs on every change.
`selftest.sh` is a second automated suite that covers the glm-dev-team engine end to end. It isolates itself
(temp `HOME`, `DEVTEAM_PROVIDER=glm`, `DEVTEAM_GOVERNOR=off`, `DEVTEAM_PEAK=off`, no real transcripts). New
engine behaviour gets a check there. It was written for GNU userland and runs on macOS as well; the
last full run reported 371 pass, 0 fail (the README records the same count). If it goes red on macOS,
reproduce on Linux before blaming the change.
`glm-systematic-debugging/evals/` are manual scenarios graded by hand in a fresh session; they are never
loaded at runtime.

## Architecture: the shared GLM design

Every port applies the same set of model facts; each skill with a tuning surface documents them in its
`glm-tuning.md` (glm-idea-to-spec has none):

- **Aliases collapse on Z.ai.** `haiku` maps to `glm-5.3-flash`. Both `sonnet` and `opus` map to `glm-5.3`,
  so a "sonnet" lane is not cheaper. Worker lanes default to Flash and judgment lanes use GLM-5.3. Never
  pick `opus` over `sonnet` for cost reasons.
- **Thinking is always on.** `reasoning_effort` accepts only `low | high | max` (no `medium`) and defaults
  to `max`. Effort is the real latency dial, so every tier maps to one explicit effort. Claude Code forwards
  effort only when `*_SUPPORTED_CAPABILITIES` includes `effort`; on ZCode, effort reaches GLM through the
  installed agent's `thoughtLevel` (honored only together with a specific `model` id).
- **GLM emits few parallel tool calls per turn.** Fan-out therefore
  lives inside the Python tools: each one opens up to 8 threads and calls the Z.ai API directly (the "api
  lane"). A single model turn replaces many batched tool calls. Each tool has an **agent lane** fallback
  that writes briefs for subagents when no API key is found (`--lane api|agent`); on ZCode, foreground
  subagents launched together in one message run in parallel.
- **Prefix caching.** Every request in a fan-out wave shares a byte-identical system/prefix block. Keep it
  identical when editing prompts.
- **Prompt style.** Instructions are written as numbered imperative rules (R0, R1, …) with no XML
  ceremony. Tables are kept only for reference data. Each SKILL.md pins a small turn budget (for example
  "three tool calls", "four calls"), and each script prints a `NEXT:` line so the model does not
  deliberate about plumbing.
- **Key discovery.** Scripts read `ZAI_API_KEY` / `GLM_API_KEY` / `ANTHROPIC_AUTH_TOKEN`, and also named
  key fields in `~/.claude/settings.json`, `~/.config/opencode/*.json` and `~/.zcode/*.json`
  (`~/.zcode/v2/credentials.json` is the first zcode path; the hyphenated `api-key` field under
  `account-provider → coding-plan → account → <plan> → <uuid>` is found). They never write tokens or
  base URLs.

### Per-skill engines

- **glm-dev-team**: `devteam.py` is a deterministic scheduler and integrator. The flow is
  `start <plan.md>` once, then `next` on every wake-up. Programmers work in git worktrees. `guard.py` holds
  the PreToolUse hooks that enforce file footprints, frozen tests and read-only roles. An AIMD
  **governor** sizes concurrency by tier (`DEVTEAM_GLM_TIER`, default `api` — the full 8-call window), halves
  it on 429/1302/1305 errors; peak-hour halving is opt-in via `DEVTEAM_PEAK=on`. Agent definitions live in `agents/` and are installed by `doctor --fix`.
  `README.md` is in Vietnamese.
- **glm-systematic-debugging**: `debug_tool.py` runs one call per phase: `probe`, `run -j`,
  `experiment` (a separate worktree for each control and treatment arm) and `scan` (8 API workers). Helper
  shell scripts: `stress.sh` (Wilson CI and Fisher test), `bisect-parallel.sh` and `find-polluter.sh`.
- **glm-requirements-code-audit**: `audit.py` works as `brief` → checklist → `run` (retrieve, judge,
  repair, verify) → `finalize`. Retrieval is deterministic Python, not model search. A checker rejects
  invented `path:lines` citations before they reach the report. It writes only under `<cwd>/.audit/`.
  ZCode agents live in `agents/`; `install-zcode.sh` rewrites them — plus glm-debug-worker and the
  glm-dev-team agents — to ZCode frontmatter (real GLM ids via `--flash`/`--main`, `thoughtLevel`, no
  `effort`/`hooks`/`isolation`) and gets glm-plan-task-writer from `plan_tool.py setup --harness zcode --apply`.
  The `opencode/` folders in three skills hold legacy neutral agent sources: kept on disk, installed by
  nothing.
- **glm-writing-plans**: `plan_tool.py` works as `brief` → write contracts → `build`, which fans out task
  bodies, lints them and repairs them. Tier routing is `light` / default / `deep`.
- **glm-brainstorming**: `scripts/context.sh` is injected through the `!` preload line (or the
  `/glm-brainstorm` command); on ZCode, which has no `!` preload, the SKILL.md tells the model to run it
  as a round-1 call when the raw `!` line shows. It must stay read-only,
  bounded (about 55 lines or fewer) and **always exit 0**, because a non-zero exit cancels the skill. It
  also contains the visual-companion server (`server.cjs`, `start-server.sh`).
- **glm-doc-generator**: a single self-contained SKILL.md. Its `scripts/` folder holds only the vendored
  `oc_harness.py` (legacy installer plumbing, no longer referenced by SKILL.md); the skill runs no script of
  its own and states that it must never read other files.
- **glm-idea-to-spec**: a self-contained SKILL.md plus four reference docs (`evaluation-framework.md`,
  `question-bank.md`, `research-playbook.md`, `spec-template.md` under `references/`); no scripts, no
  agents, no tuning doc — every turn is pure model guidance for research-backed spec writing.
- **glm-git-diff-summary**: SKILL.md + the read-only `scripts/gather.sh` (merge-base → working-tree diff,
  background fetch with a per-repo stamp, chunks for Read or an agent fan-out). No API key, no agents or
  commands, no tuning doc; process identity is glm- scoped (`/tmp/glm-gds.*`, `.git/glm-gds-fetched-*`,
  `GLM_GDS_*` env vars) so the Claude-tuned original can run on the same machine without interference.

### Legacy OpenCode runtime support (inert)

The skills are documented and installed for ZCode only, but the shared runtime still carries its
verified OpenCode code paths (`oc_harness.py` lanes, `guard.py oc` mode, the v1/v2 plugins,
`is_opencode()` detection, `setup --harness opencode`, `OC_MAX_LANES`). They never trigger on ZCode
and are kept — code, vendored copies, plugins and the tests that cover them — so no file had to be
deleted and the suite stays green. Do not extend them; new behaviour targets ZCode first. The facts
that guided them (OpenCode v1.18.x/v2.0.x tool names, hook shapes, effort routing, 429 behaviour)
live in git history and `docs/specs/2026-09-28-opencode-hardening-design.md`.

### ZCode facts (3.14.4)

All facts were verified against the local 3.14.4 binary unless marked otherwise.

- **Skills.** Skills live at `~/.zcode/skills/<name>/SKILL.md`, invoked as `$<name>`. A frontmatter
  `description` over 1024 characters makes ZCode drop the whole skill; a body over 100KB is truncated when
  loaded. Per-turn trigger metadata is the name plus a description excerpt of up to 250 characters, so the
  WHEN-clause must sit at the front of every description. There is no `!` preload support; unknown
  frontmatter keys are ignored.
- **Agents.** Custom subagents live at `~/.zcode/agents/<name>.md`, user level only, no nesting; several
  launched together in the foreground run in parallel. Frontmatter keys: `name`, `description`, `model`,
  `thoughtLevel` (honored only together with a specific `model`), `color`, `tools`/`disallowedTools`,
  `maxTurns`, `injectAgentsMd`, `mcpServers`; no haiku/sonnet/opus aliases exist. The installed agents
  split lite/strong — lite workers run on `glm-5.3-flash` (the `--flash` default), strong judgment agents
  on `glm-5.3` (the `--main` default).
- **Dispatch.** Subagents are dispatched through the `Agent` tool (Task alias) whose input schema is
  `{description, prompt, subagent_type, run_in_background}` with `subagent_type` omitted defaulting to
  `general-purpose` — the Claude Code Task shape minus the `model` parameter (binary-verified; the web
  docs confirm the tool and the `general-purpose` + `Explore` built-ins but do not document the schema).
  `SendMessage`, `TaskStop`, and Bash `run_in_background` + `timeout` all exist and are
  Claude-Code-compatible.
- **Hooks.** A full Claude-Code-compatible hook system — SessionStart, UserPromptSubmit, PreToolUse,
  PermissionRequest, PostToolUse, PostToolUseFailure, Stop — with no SubagentStop. Hooks are configured at
  user level only, in `~/.zcode/cli/config.json` (`hooks.enabled: true`); project/workspace-level hooks
  are ignored. Hook stdin JSON carries snake_case + camelCase fields including `agent_type` (the calling
  agent's name); exit code 2 blocks; stdout `hookSpecificOutput.permissionDecision` = allow/ask/deny —
  the exact shapes `guard.py` already prints.
- **Credentials.** There is no public headless CLI. Credentials live at `~/.zcode/v2/credentials.json`
  under `account-provider → coding-plan → account → <plan> → <uuid> → api-key` (field name `api-key`,
  hyphenated; OAuth/JWT fields keep distinct names and are never picked).
- **Session reload.** Skills, agents and hook config are read at session start; anything installed or
  reconfigured mid-session — including a fresh hook merge — takes effect only in a new session.

## Conventions and gotchas

- **Harness constraints drive frontmatter.** ZCode drops a skill whose
  `description` is longer than 1024 characters and has no `effort`/`permissionMode` fields or model aliases
  (use real GLM ids plus `thoughtLevel`). Check description length after editing.
- **Every installable name carries the `glm-` prefix.** Skill folders, SKILL.md frontmatter
  `name`, agents and commands are all `glm-*`, so they install next to the
  Claude-tuned originals without shadowing them. Bootstrap path-resolution loops search for
  `glm-systematic-debugging`, `glm-writing-plans`, `glm-dev-team` and so on across the `.zcode`,
  `.claude` and `.agents` skill dirs. Every SKILL.md frontmatter `name` equals its
  folder name (`glm-brainstorming`, `glm-dev-team`, `glm-doc-generator`, `glm-requirements-code-audit`, `glm-systematic-debugging`,
  `glm-writing-plans`, `glm-idea-to-spec`); `test_all_skills.py` enforces this. Runtime state
  keeps its old unprefixed paths (`.claude/dev-team/`, `.audit/`, `.brainstorm/`, `devteam/<id>`
  branches, `devteam.py`/`audit.py` script names); only install identity is prefixed.
- Version tags: the debugging and audit ports are `9.0` / v9 and glm-writing-plans is v9; glm-brainstorming is `9.3`
  (per its CHANGELOG), and glm-dev-team is v4.0. Record behaviour changes in the skill's CHANGELOG/README where
  one exists.
