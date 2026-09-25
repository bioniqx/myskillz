# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

GLM-5.3 / GLM-5.3-Flash ports of the Claude-tuned skills that sit one level up in `~/.claude/skills/`
(`brainstorming-6.3`, `dev-team-v3.2`, `doc-generator`, `requirements-code-audit`,
`systematic-debugging-6.3`, `writing-plans-6.2`). Each `*-glm/` folder is a self-contained skill meant to
be copied into a harness (Claude Code on the Z.ai route, OpenCode, or ZCode). Claude Code does not load
skills nested this deep, so nothing here is active in this session. The git root is `~/.claude`, not this
folder.

When a port changes behaviour, compare against the sibling original. Keep GLM-specific changes in the port
only; do not edit the originals from here.

## Commands

All scripts are stdlib-only Python 3 or POSIX shell. No build step, no dependencies to install (ripgrep
optional for the audit).

```bash
# dev-team engine + hook guards: full end-to-end self-test in a throwaway repo (exit 0 = all pass)
bash dev-team-glm/scripts/selftest.sh

# Syntax check every script
for f in */scripts/*.py; do python3 -m py_compile "$f"; done

# Environment / key / endpoint checks (each script has one; --ping hits the live API)
python3 systematic-debugging-glm/scripts/debug_tool.py doctor --ping
python3 requirements-code-audit-glm/scripts/audit.py doctor --ping
python3 writing-plans-glm/scripts/plan_tool.py doctor --ping
python3 dev-team-glm/scripts/devteam.py doctor        # --fix writes .claude/settings.local.json + agents

# Print the install/config block for a harness
python3 <skill>/scripts/<tool>.py setup --harness opencode|zcode|claude

# Install all Phase 1 + Phase 2 skills into OpenCode and print the config snippet
sh install-opencode.sh [--major N] [--home DIR]

# Vendored-copy identity, py_compile and SKILL.md hygiene across all glm skills
python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v

# Full Python suite (all _shared/tests). Never rewrite tracked __pycache__/*.pyc, so pass this env var.
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests
```

`_shared/*.py` (`zai_client.py`, `oc_harness.py`) is the source of truth; each skill's `scripts/` copy is
vendored from it by `sh _shared/sync.sh` — never edit a vendored copy by hand.

The Python suite under `_shared/tests` is the main automated suite and runs on every change.
`selftest.sh` is a second automated suite that covers the dev-team engine end to end. It isolates itself
(temp `HOME`, `DEVTEAM_PROVIDER=glm`, `DEVTEAM_GOVERNOR=off`, `DEVTEAM_PEAK=off`, no real transcripts). New
engine behaviour gets a check there. It was written for GNU userland (the README reports 308/308). On
macOS it currently reports 302 pass, 6 fail. At least one failure comes from the test itself, not the
engine: BSD `sed` rejects the GNU-style `sed -i` call. Run it on Linux before trusting a red result.
`systematic-debugging-glm/evals/` are manual scenarios graded by hand in a fresh session; they are never
loaded at runtime.

## Architecture: the shared GLM design

Every port applies the same set of model facts. Each skill's `glm-tuning.md` gives the details:

- **Aliases collapse on Z.ai.** `haiku` maps to `glm-5.3-flash`. Both `sonnet` and `opus` map to `glm-5.3`,
  so a "sonnet" lane is not cheaper. Worker lanes default to Flash and judgment lanes use GLM-5.3. Never
  pick `opus` over `sonnet` for cost reasons.
- **Thinking is always on.** `reasoning_effort` accepts only `low | high | max` (no `medium`) and defaults
  to `max`. Effort is the real latency dial, so every tier maps to one explicit effort. Claude Code forwards
  effort only when `*_SUPPORTED_CAPABILITIES` includes `effort`.
- **GLM emits few parallel tool calls per turn, and OpenCode runs subagents serially.** Fan-out therefore
  lives inside the Python tools: each one opens up to 64 threads and calls the Z.ai API directly (the "api
  lane"). A single model turn replaces many batched tool calls. Each tool has an **agent lane** fallback
  that writes briefs for subagents when no API key is found (`--lane api|agent`).
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

- **dev-team-glm**: `devteam.py` is a deterministic scheduler and integrator. The flow is
  `start <plan.md>` once, then `next` on every wake-up. Programmers work in git worktrees. `guard.py` holds
  the PreToolUse hooks that enforce file footprints, frozen tests and read-only roles. An AIMD
  **governor** sizes concurrency by tier (`DEVTEAM_GLM_TIER`), halves it on 429/1302/1305 errors, and halves
  its ceiling during Z.ai peak hours. Agent definitions live in `agents/` and are installed by `doctor --fix`.
  `README.md` is in Vietnamese.
  **dev-team on OpenCode:** When running on OpenCode (env `DEVTEAM_HARNESS=opencode` or `OPENCODE` set),
  `devteam.py` dispatches each lane to a separate `oc_harness.run_lanes()` call in its own git worktree
  under `.claude/dev-team/wt/<lane id>`. The programmer's brief is read from stdout of `devteam.py claim
  <lane id>`. Tool-call enforcement moves from the PreToolUse hook into plugins (`plugins/<base>.v1.js`
  and `<base>.v2.js`) that run `python3 guard.py oc` mode; a guard rule enforces programmer edit/bash and
  read-only roles via agent type. Worktrees are created from the slice's recorded base on branch
  `devteam/<lane id>`. Lane outputs go to `.claude/dev-team/lanes/<id>.jsonl` (handled by `oc_harness`);
  completion markers stay in `.claude/dev-team/slices/<id>.done|.blocked` (written by `guard.py stop`). The
  stop gate blocks after each programmer exits, pipes `{"cwd": worktree, "last_assistant_message":
  final_text}` to `guard.py stop`, and re-runs the lane up to 2 times if blocked (appending stderr to the
  brief).
  **Plugin role mapping:** OpenCode agent names (programmer, code-reviewer, spot-reviewer, investigator,
  team-leader) are set in env `DEVTEAM_ROLE` per lane. The plugins (`skills/glm/dev-team-glm/opencode/
  plugins/`) define v1 and v2 shapes; at install time, `oc_harness.install()` copies the matching major
  version to `<home>/.config/opencode/plugins/`. v1 plugin exports a `DevteamGuard` hook; v2 exports
  `export default { id: 'devteam-guard', setup: async (api) => { api.tool.hook('execute.before', async
  (event) => {...}) } }` — the real shape the installed v2.0.16 binary validates and calls (verified from
  the binary: `PluginModule.load` requires a default export matching `{id, effect}` or `{id, setup}`, and
  `api.tool.hook` forwards to the Tool service's `execute.before` trigger, whose event carries `tool` and
  `input`). There is no `ctx.directory` in v2; the plugin uses `process.cwd()` instead. Both hooks run
  before tool execution: on receipt of `edit`, `write`, `patch`/`apply_patch`, or `bash` tools, they call `python3
  guard.py oc` with JSON on stdin and throw `Error(reason)` if the decision is `deny`. Guard mode choice:
  programmer role gets `edit`/`bash` checks; any other role gets read-only (`edit-ro`/`bash-ro`) with
  `agent_type` set to the role; no role prints nothing (silent allow). Plugin failures allow calls (same
  fail-open as Python-side guard). v2 `opencode run` has no `--dir` flag; lanes instead run with the lane's
  working directory passed as the subprocess `cwd` (v1 keeps `--dir`).
- **systematic-debugging-glm**: `debug_tool.py` runs one call per phase: `probe`, `run -j`,
  `experiment` (a separate worktree for each control and treatment arm) and `scan` (64 API workers). Helper
  shell scripts: `stress.sh` (Wilson CI and Fisher test), `bisect-parallel.sh` and `find-polluter.sh`.
- **requirements-code-audit-glm**: `audit.py` works as `brief` → checklist → `run` (retrieve, judge,
  repair, verify) → `finalize`. Retrieval is deterministic Python, not model search. A checker rejects
  invented `path:lines` citations before they reach the report. It writes only under `<cwd>/.audit/`.
  `agents/zcode/` and `agents/opencode/` hold the fallback-lane agents in each harness's frontmatter dialect.
- **writing-plans-glm**: `plan_tool.py` works as `brief` → write contracts → `build`, which fans out task
  bodies, lints them and repairs them. Tier routing is `light` / default / `deep`.
- **brainstorming-glm**: `scripts/context.sh` is injected through `!` preload. It must stay read-only,
  bounded (about 55 lines or fewer) and **always exit 0**, because a non-zero exit cancels the skill. It
  also contains the visual-companion server (`server.cjs`, `start-server.sh`).
- **doc-generator-glm**: a single self-contained SKILL.md with no scripts. The skill states that it must
  never read other files.

## Conventions and gotchas

- **Harness constraints drive frontmatter.** OpenCode parses only `name`, `description`, `license`,
  `compatibility` and `metadata`, and ignores `allowed-tools` and `!` injection. ZCode drops a skill whose
  `description` is longer than 1024 characters and has no `effort`/`permissionMode` fields or model aliases
  (use real GLM ids plus `thoughtLevel`). Check description length after editing.
- **Installed folder names drop the `-glm` suffix.** Bootstrap path-resolution loops search for
  `systematic-debugging`, `writing-plans`, `dev-team` and so on across the `.opencode`, `.config/opencode`,
  `.claude`, `.agents` and `.zcode` skill dirs. Every SKILL.md frontmatter `name` drops the `-glm` suffix
  (`brainstorming`, `dev-team`, `doc-generator`, `requirements-code-audit`, `systematic-debugging`,
  `writing-plans`); `test_all_skills.py` enforces this.
- Version tags: the debugging, audit and writing-plans ports are `9.0-glm` / v9, brainstorming is `9.0-glm`
  (per its CHANGELOG), and dev-team is v4.0. Record behaviour changes in the skill's CHANGELOG/README where
  one exists.
