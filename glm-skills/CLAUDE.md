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
`*-glm/` folder is a self-contained skill meant to be copied into a harness (Claude Code on the Z.ai
route, OpenCode, or ZCode). Claude Code does not load skills nested this deep, so nothing here is active in
this session. The git root is the skillz monorepo root (`../`), not this folder.

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
python3 <skill>/scripts/<tool>.py setup --harness opencode|zcode|claude

# Install all six skills into ZCode: skills to ~/.zcode/skills/<name>, agents rewritten to ZCode frontmatter into ~/.zcode/agents
sh install-zcode.sh [--home DIR] [--flash MODEL_ID] [--main MODEL_ID] [--dry-run]

# Install all six skills into OpenCode and print the config snippet (for Claude Code, copy a folder by hand)
sh install-opencode.sh [--major N] [--home DIR]

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

Every port applies the same set of model facts. Each skill's `glm-tuning.md` gives the details:

- **Aliases collapse on Z.ai.** `haiku` maps to `glm-5.3-flash`. Both `sonnet` and `opus` map to `glm-5.3`,
  so a "sonnet" lane is not cheaper. Worker lanes default to Flash and judgment lanes use GLM-5.3. Never
  pick `opus` over `sonnet` for cost reasons.
- **Thinking is always on.** `reasoning_effort` accepts only `low | high | max` (no `medium`) and defaults
  to `max`. Effort is the real latency dial, so every tier maps to one explicit effort. Claude Code forwards
  effort only when `*_SUPPORTED_CAPABILITIES` includes `effort`. On OpenCode, effort reaches GLM via
  frontmatter `reasoningEffort` on v1 (agents are rendered `mode: all`) and on v2 via the agent's
  `variant:` when the `subagent` tool dispatches it (a v2 agent with no variant runs at max). `opencode run
  --model` overrides the agent's model and variant, so `oc_harness.py` adds a `#<effort>` suffix to lanes.
- **GLM emits few parallel tool calls per turn, and OpenCode v1 runs subagents serially.** Fan-out therefore
  lives inside the Python tools: each one opens up to 8 threads and calls the Z.ai API directly (the "api
  lane"). A single model turn replaces many batched tool calls. Each tool has an **agent lane** fallback
  that writes briefs for subagents when no API key is found (`--lane api|agent`). On OpenCode v2 the
  `subagent` tool takes `background: true`, so agent-lane workers run concurrently even at one call per
  turn (interactive sessions only; a headless `opencode run` can exit before they report).
- **Prefix caching.** Every request in a fan-out wave shares a byte-identical system/prefix block. Keep it
  identical when editing prompts.
- **Prompt style.** Instructions are written as numbered imperative rules (R0, R1, …) with no XML
  ceremony. Tables are kept only for reference data. Each SKILL.md pins a small turn budget (for example
  "three tool calls", "four calls"), and each script prints a `NEXT:` line so the model does not
  deliberate about plumbing.
- **Key discovery.** Scripts read `ZAI_API_KEY` / `GLM_API_KEY` / `ANTHROPIC_AUTH_TOKEN`, and also named
  key fields in `~/.claude/settings.json`, `~/.config/opencode/*.json` and `~/.zcode/*.json`. They never
  write tokens or base URLs.

### Per-skill engines

- **glm-dev-team**: `devteam.py` is a deterministic scheduler and integrator. The flow is
  `start <plan.md>` once, then `next` on every wake-up. Programmers work in git worktrees. `guard.py` holds
  the PreToolUse hooks that enforce file footprints, frozen tests and read-only roles. An AIMD
  **governor** sizes concurrency by tier (`DEVTEAM_GLM_TIER`), halves it on 429/1302/1305 errors, and halves
  its ceiling during Z.ai peak hours. Agent definitions live in `agents/` and are installed by `doctor --fix`.
  `README.md` is in Vietnamese.
  **glm-dev-team on OpenCode:** When running on OpenCode (`is_opencode()`: `DEVTEAM_HARNESS` decides when set,
  else `OPENCODE`, else `oc_harness.harness()`, since v2 never sets `OPENCODE`),
  `devteam.py` dispatches each lane to a separate `oc_harness.run_lanes()` call in its own git worktree
  under `.claude/dev-team/wt/<lane id>`. The glm-programmer's brief is read from stdout of `devteam.py claim
  <lane id>`. Tool-call enforcement moves from the PreToolUse hook into plugins (`plugins/<base>.v1.js`
  and `<base>.v2.js`) that run `python3 guard.py oc` mode; a guard rule enforces glm-programmer edit/bash and
  read-only roles via agent type. Worktrees are created from the slice's recorded base on branch
  `devteam/<lane id>`. Lane outputs go to `.claude/dev-team/lanes/<id>.jsonl` (handled by `oc_harness`);
  completion markers stay in `.claude/dev-team/slices/<id>.done|.blocked` (written by `guard.py stop`). The
  stop gate blocks after each glm-programmer exits, pipes `{"cwd": worktree, "last_assistant_message":
  final_text}` to `guard.py stop`, and re-runs the lane up to 2 times if blocked (appending stderr to the
  brief).
  **Plugin role mapping:** OpenCode agent names (glm-programmer, glm-code-reviewer, glm-spot-reviewer, glm-investigator,
  glm-team-leader) are set in env `DEVTEAM_ROLE` per lane; when it is unset, the v2 plugin uses `event.agent` if
  it names a glm-dev-team role. The plugins (`glm-dev-team/opencode/plugins/`) define v1 and v2 shapes; at install time, `oc_harness.install()` copies the matching major
  version to `<home>/.config/opencode/plugins/`. v1 plugin exports a `DevteamGuard` hook; v2 exports
  `export default { id: 'glm-devteam-guard', setup: async (api) => { api.tool.hook('execute.before', async
  (event) => {...}) } }` — the real shape the installed v2.0.16 binary validates and calls (verified from
  the binary: `PluginModule.load` requires a default export matching `{id, effect}` or `{id, setup}`, and
  `api.tool.hook` forwards to the Tool service's `execute.before` trigger, whose event carries
  `{tool, sessionID, agent, messageID, id, input}`). There is no `ctx.directory` in v2; the plugin uses
  `process.cwd()` instead. Both hooks run before tool execution: on receipt of `write`, `edit`, `patch`,
  `apply_patch`, `multiedit`, `shell`, `bash`, `execute` or `batch` tools, they call `python3
  guard.py oc` with JSON on stdin and throw `Error(reason)` if the decision is `deny`. Guard mode choice:
  glm-programmer role gets `edit`/`bash` checks; any other role gets read-only (`edit-ro`/`bash-ro`) with
  `agent_type` set to the role; no role prints nothing (silent allow). Plugin failures allow calls (same
  fail-open as Python-side guard). v2 `opencode run` has no `--dir` flag; lanes instead run with the lane's
  working directory passed as the subprocess `cwd` and `$PWD` (v2 `--standalone` resolves its project root
  from `$PWD`; v1 keeps `--dir`).
- **glm-systematic-debugging**: `debug_tool.py` runs one call per phase: `probe`, `run -j`,
  `experiment` (a separate worktree for each control and treatment arm) and `scan` (8 API workers). Helper
  shell scripts: `stress.sh` (Wilson CI and Fisher test), `bisect-parallel.sh` and `find-polluter.sh`.
- **glm-requirements-code-audit**: `audit.py` works as `brief` → checklist → `run` (retrieve, judge,
  repair, verify) → `finalize`. Retrieval is deterministic Python, not model search. A checker rejects
  invented `path:lines` citations before they reach the report. It writes only under `<cwd>/.audit/`.
  `opencode/agents/` holds the fallback-lane agents in OpenCode frontmatter. ZCode agents live in `agents/zcode/` (audit, glm-doc-generator); `install-zcode.sh` also rewrites glm-debug-worker and the glm-dev-team agents to ZCode frontmatter (real GLM ids via `--flash`/`--main`, `thoughtLevel`, no `effort`/`hooks`/`isolation`) and gets glm-plan-task-writer from `plan_tool.py setup --harness zcode --apply`.
- **glm-writing-plans**: `plan_tool.py` works as `brief` → write contracts → `build`, which fans out task
  bodies, lints them and repairs them. Tier routing is `light` / default / `deep`.
- **glm-brainstorming**: `scripts/context.sh` is injected through `!` preload. It must stay read-only,
  bounded (about 55 lines or fewer) and **always exit 0**, because a non-zero exit cancels the skill. It
  also contains the visual-companion server (`server.cjs`, `start-server.sh`).
- **glm-doc-generator**: a single self-contained SKILL.md. Its `scripts/` folder holds only the vendored
  `oc_harness.py` (installer plumbing); the skill runs no script of its own and states that it must never
  read other files.

### OpenCode version facts (v1.18.x and v2.0.x)

Both lines are supported: v1 stable (latest release v1.18.33) and v2 beta (local 2.0.18). All facts were
verified on 2026-09-28 by local probes against a fake provider unless marked otherwise.

- **Tools.** v2.0.18 exposes `edit, glob, grep, question, read, shell, skill, subagent, webfetch,
  websearch, write, execute`; it has no `bash`, `apply_patch`, `task` or `todowrite`. v2 shell input is
  `{command, workdir, timeout, background}`, write is `{path, content}`, edit is
  `{path, oldString, newString, replaceAll}`. v1.18.33 exposes `bash, edit, glob, grep, read, skill,
  task, todowrite, webfetch, write`; v1 hook args are `command` (bash) and `filePath` plus `content`
  (write). The v2 migration docs rename permissions: `bash` is now `shell`, `task` is now `subagent`, and
  `write` and `patch` are now `edit`.
- **Plugin hook.** v2 `execute.before` events carry `{tool, sessionID, agent, messageID, id, input}`. v1
  `tool.execute.before` gets `(input{tool,sessionID,callID}, output{args})`. In both, throwing inside the
  hook blocks the tool; in v2 the run still exits 0.
- **Effort.** v2 sends effort only through `--model provider/model#effort` (the request carries
  `"reasoning_effort":"high"` for `#high`). `#max` fails ("Variant unavailable", `provider.no-route`)
  unless the provider config defines `variants.max`. `run --agent` ignores the agent's model and variant;
  `subagent` dispatch honours `variant`. This contradicts the v2 agents docs, which say variants are not
  yet sent with model requests. v1 takes effort from agent frontmatter `reasoningEffort` plus `--agent`;
  a `#high` suffix exits 1 with UnknownError.
- **`run` flags.** v2: `--standalone --server --continue --session --fork --model provider/model#variant
  --agent --format default|json --file --title --thinking --auto`, no `--dir`. v1: `--dir --model --agent
  --format --variant`, no `--standalone`.
- **Brief.** Both read the brief verbatim from stdin when argv has no message. v2 wraps an argv message
  containing whitespace in literal quotes, and an open stdin pipe hangs the run, so stdin must be closed.
- **Events.** v2 JSON event types are `step_start, tool_use, step_finish, text, error`, emitted only at
  step/part boundaries; the final text step has no `step_finish`.
- **429.** v2 retries 12 times over about 86 s, then emits
  `{"type":"error","error":{"type":"provider.rate-limit","status":429}}` and exits 1; the response body,
  including Z.ai code 1302, is dropped. v1 retries 7 times over about 77 s, then emits an error with
  `name: "APIError"` and `data.statusCode: 429`; `data.responseBody` carries the Z.ai code
  (`1302`/`1305`).
- **Skills.** v2 always scans `~/.claude/skills` and has no `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS`, so the
  installer prints that hint only for v1. On a name clash the config-dir copy wins. v2 skill frontmatter
  honours only `name`, `description` and `metadata`; `allowed-tools` and `!` preload blocks are ignored.
  (Sandbox `opencode serve` probe.)
- **Built-in agent.** The general agent is `general`; `general-purpose` and `Explore` do not exist.
- **Env.** v2 sets only `OPENCODE_TERMINAL=1` in shell children and never sets `OPENCODE`, so harness
  detection goes through `oc_harness.harness()` (env markers, then the script's install path and the
  install marker), never `OPENCODE` alone.
- **Read from the binary, confirmed by `test_oc_contract.py`:** the v2 shell tool's default timeout is
  120000 ms.

## Conventions and gotchas

- **Harness constraints drive frontmatter.** OpenCode parses only `name`, `description`, `license`,
  `compatibility` and `metadata`, and ignores `allowed-tools` and `!` injection. ZCode drops a skill whose
  `description` is longer than 1024 characters and has no `effort`/`permissionMode` fields or model aliases
  (use real GLM ids plus `thoughtLevel`). Check description length after editing.
- **Every installable name carries the `glm-` prefix.** Skill folders, SKILL.md frontmatter
  `name`, agents, commands and plugins are all `glm-*`, so they install next to the
  Claude-tuned originals without shadowing them. Bootstrap path-resolution loops search for
  `glm-systematic-debugging`, `glm-writing-plans`, `glm-dev-team` and so on across the `.opencode`, `.config/opencode`,
  `.claude`, `.agents` and `.zcode` skill dirs. Every SKILL.md frontmatter `name` equals its
  folder name (`glm-brainstorming`, `glm-dev-team`, `glm-doc-generator`, `glm-requirements-code-audit`, `glm-systematic-debugging`,
  `glm-writing-plans`, `glm-idea-to-spec`); `test_all_skills.py` enforces this. Runtime state
  keeps its old unprefixed paths (`.claude/dev-team/`, `.audit/`, `.brainstorm/`, `devteam/<id>`
  branches, `devteam.py`/`audit.py` script names); only install identity is prefixed.
- Version tags: the debugging and audit ports are `9.0` / v9 and glm-writing-plans is v9; glm-brainstorming is `9.3`
  (per its CHANGELOG), and glm-dev-team is v4.0. Record behaviour changes in the skill's CHANGELOG/README where
  one exists.
