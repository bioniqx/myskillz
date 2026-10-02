# AGENTS.md

This file guides agents working in this repository.

## What this directory is

Six OpenCode v2 skills: `oc-brainstorming`, `oc-dev-team`, `oc-doc-generator`, `oc-requirements-code-audit`,
`oc-systematic-debugging` and `oc-writing-plans`. Every installed name carries the `oc-` prefix so it never
clashes with a same-named skill, agent, command or plugin from another harness: skill folders and SKILL.md
`name`, agent files (`oc-programmer.md`), command files (`/oc-devteam`) and the plugin (`oc-devteam-guard`).
Dev-team guard roles stay bare (`programmer`); the plugin strips the `oc-` from `event.agent`. Each source folder is named `oc-<skill>` (for example
`oc-dev-team`) and is a self-contained skill that is copied into `~/.config/opencode/skills/oc-<skill>` by
`install-opencode.sh`; the installed name comes from the SKILL.md `name`, not the folder. Every skill runs on whatever model is selected in the
OpenCode window: no file chooses a provider, a model id, a model alias or a reasoning effort, and nothing
calls a model API directly. No script spawns `opencode`. OpenCode v1 and every other harness are
unsupported.

The installer never touches an existing `~/.config/opencode`; the user runs it afterwards.

## Commands

All scripts are stdlib-only Python 3 or POSIX shell. There is no build step and nothing to install
(ripgrep is optional for the audit).

- `bash oc-dev-team/scripts/oc-selftest.sh` runs the dev-team engine and hook guards end to end in a throwaway
  repo (exit 0 means all checks pass).
- `for f in */scripts/*.py; do python3 -m py_compile "$f"; done` syntax-checks every script.
- `sh install-opencode.sh [--home DIR]` installs all six skills into OpenCode and prints the config snippet.
- `python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v` checks
  vendored-copy identity, py_compile and SKILL.md hygiene across all skills.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests` runs the full
  Python suite. The environment variable keeps skill folders free of bytecode.
- `sh _shared/sync.sh` refreshes every vendored copy of `_shared/oc_harness.py`.

`_shared/oc_harness.py` is the single source of truth for the shared module. Each skill's `scripts/` copy
is vendored from it by `sh _shared/sync.sh`; never edit a vendored copy by hand. The module keeps only
`detect`, `harness`, `major`, `parse_frontmatter`, `render_agent`, `render_command`, `dispatch_line`,
`install`, `check` and `skill_name`, and contains no process spawning.

The Python suite under `_shared/tests` is the main automated suite and runs on every change.
`oc-selftest.sh` is a second automated suite that covers the dev-team engine end to end. It isolates itself
(temp `HOME`, no real transcripts). New engine behaviour gets a check there. It was written for GNU
userland. On macOS it reports 5 known failures that come from BSD userland; run it on Linux before
trusting a red result, and never add to those 5.

## Architecture: one execution path

The interactive OpenCode session model launches every lane. There is no other route.

- **Dispatch rows.** A tool script writes one brief per lane, then prints one `oc_harness.dispatch_line`
  row per lane: a v2 `subagent(agent=..., description=..., prompt="Read <brief> and follow it exactly.",
  background=true)` call. The session model emits all rows in one message and the background lanes run
  concurrently. Agent files carry no `model`, `variant`, `effort` or `reasoningEffort` field, so a lane runs
  on the model of the primary agent that launched it.
- **Result files.** Every lane writes its own result to a file the script names (task file, findings or
  verdict JSONL, report, slice marker). A script command (`status`, `wait`, `next`) reads those files,
  merges them and prints the next rows and a `NEXT:` line. Debug `scan` workers only reply with a
  `VERDICT:` line and need no file.
- **Lost lanes.** A lane that never writes its result file is reported by id, and the script prints the
  same dispatch row again (`--redispatch` in the audit, `resume` in dev-team). Scripts hold no rate-limit
  logic: a failing lane is visible to the session.
- **Prefix caching.** Every brief in a fan-out wave shares a byte-identical prefix block. Keep it identical
  when editing prompts.
- **Prompt style.** Instructions are numbered imperative rules (R0, R1, ...) with no XML ceremony. Tables
  are kept only for reference data. Each SKILL.md pins a small turn budget (for example "three tool
  calls"), and each script prints a `NEXT:` line so the model does not deliberate about plumbing.
- **State directories.** dev-team writes under `.opencode/oc-dev-team`, doc-generator under
  `.opencode/oc-doc-gen`, the audit under `<cwd>/.oc-audit/`.

### Per-skill engines

- **dev-team**: `oc_devteam.py` is a deterministic scheduler and integrator. The flow is
  `start <plan.md>` once, then `next` on every wake-up. Each programmer lane works in its own git worktree
  under `.opencode/oc-dev-team/wt/<lane id>` on branch `oc-devteam/<lane id>`, created from the slice's recorded
  base by `oc_devteam.py claim <lane id> --worktree`. A lane has no working-directory setting, so the
  programmer passes `workdir` to `shell` and uses absolute paths for `read`, `edit` and `write`. The
  programmer finishes with `oc_devteam.py report`, which rejects an unfinished slice in-band and
  force-completes after `MAX_STOP_BLOCKS`; completion markers live in
  `.opencode/oc-dev-team/slices/<id>.done|.blocked` and `next` integrates them. `README.md` is in Vietnamese.
  Tool-call enforcement lives in one JavaScript plugin under `oc-dev-team/opencode/plugins/`, copied to
  `<home>/.config/opencode/plugins/` by `oc_harness.install()`. It exports
  `export default { id: 'oc-devteam-guard', setup: async (api) => { api.tool.hook('execute.before', async
  (event) => {...}) } }`. On `write`, `edit`, `shell`, `execute` and similar tools it calls
  `python3 oc_guard.py oc` with JSON on stdin and throws `Error(reason)` when the decision is `deny`. The
  programmer role gets the edit and shell checks; any other role gets the read-only checks with
  `agent_type` set to the role. The role comes from `event.agent` when it names a dev-team role
  (programmer, code-reviewer, spot-reviewer, investigator, team-leader), and `guard_oc` identifies the
  lane from the path or `workdir` in the tool input. There is no `ctx.directory` in v2, so the plugin uses
  `process.cwd()`. Plugin failures allow the call (fail-open).
- **systematic-debugging**: `oc_debug_tool.py` runs one call per phase: `probe`, `run -j`, `experiment` (a
  separate worktree for each control and treatment arm) and `scan` (dispatch rows, one worker per
  hypothesis). Helper shell scripts: `oc-stress.sh` (Wilson CI and Fisher test), `oc-bisect-parallel.sh` and
  `oc-find-polluter.sh`.
- **requirements-code-audit**: `oc_audit.py` works as `brief`, checklist, `run` (retrieve, judge, repair,
  verify), `finalize`. Retrieval is deterministic Python, not model search. Section parsing goes through
  the parser agent, and the repair wave re-dispatches rows that fail the checker. A checker rejects
  invented `path:lines` citations before they reach the report. It writes only under `<cwd>/.oc-audit/`.
- **writing-plans**: `oc_plan_tool.py` works as `brief`, write contracts, `build`, which prints dispatch
  rows for the task bodies, lints them and repairs them. Tier routing is `light` / default / `deep`.
- **brainstorming**: `scripts/oc-context.sh` supplies repo context. It must stay read-only, bounded (55 output
  lines or fewer) and always exit 0. It also contains the visual-companion server (`oc-server.cjs`,
  `oc-start-server.sh`).
- **doc-generator**: a single self-contained SKILL.md with no scripts. It states that it must never read
  other files.

### OpenCode v2 facts (v2.0.x)

Verified by local probes against a fake provider (`_shared/tests/fake_provider.py`) unless marked
otherwise.

- **Tools.** `edit, glob, grep, question, read, shell, skill, subagent, webfetch, websearch, write,
  execute`. There is no `bash`, `apply_patch`, `task` or `todowrite`. `shell` input is
  `{command, workdir, timeout, background}`, `write` is `{path, content}`, `edit` is
  `{path, oldString, newString, replaceAll}`. Permissions are named after the tools.
- **Plugin hook.** `execute.before` events carry `{tool, sessionID, agent, messageID, id, input}`.
  Throwing inside the hook blocks the tool; the run still exits 0.
- **Model resolution.** A `subagent` dispatch of an agent with no `model` sends the parent's model
  (probed on v2.0.20, in both orders). `opencode run` without `--model` does not reuse the last used
  model, which is why no script uses `opencode run`. Variant inheritance was not probed, so reasoning
  effort is not controlled.
- **Skills.** On a name clash the config-dir copy wins. Skill frontmatter honours only `name`,
  `description` and `metadata`; `allowed-tools` and `!` preload blocks are ignored.
- **Built-in agent.** The general agent is `general`; other agent names do not exist.
- **Env.** v2 sets only `OPENCODE_TERMINAL=1` in shell children and never sets `OPENCODE`, so harness
  detection goes through `oc_harness.harness()` (env markers, then the script's install path and the
  install marker), never `OPENCODE` alone.
- **Shell timeout.** The `shell` tool's default timeout is 120000 ms (read from the binary, confirmed by
  `test_oc_contract.py`).

## Conventions and gotchas

- **Frontmatter is minimal.** SKILL.md frontmatter holds only `name`, `description` and `metadata`, and
  `description` is at most 1024 characters. Check its length after editing.
- **Everything installed is `oc-` prefixed.** Every SKILL.md frontmatter `name` equals its folder name
  (`oc-brainstorming`, `oc-dev-team`, `oc-doc-generator`, `oc-requirements-code-audit`,
  `oc-systematic-debugging`, `oc-writing-plans`); agent and command files and the plugin id also start with
  `oc-`. `test_all_skills.py` enforces this.
- **Public signatures keep `major`.** Functions in `_shared/oc_harness.py` keep their `major` parameter;
  any value other than 2 raises `ValueError("OpenCode v2 required")`.
- **No model settings anywhere.** No file may set a provider, model id, model alias, `variant`, effort or
  reasoning-effort field, and nothing calls `run_lanes`, `build_run_cmd` or `lane_results`.
- Record behaviour changes in the skill's README or SKILL.md; skills ship no CHANGELOG.
