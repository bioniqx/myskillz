# GLM Skills OpenCode v1/v2 Hardening Implementation Plan

> **Execution note:** This plan is self-contained and tool-agnostic. Any AI
> agent or human engineer can execute it with only a shell, a code editor, and
> git. Follow the Execution Protocol below.

**Goal:** Make the six GLM skill ports, `_shared/` and the installer work correctly on OpenCode v1 stable (1.18.x) and v2 beta (2.0.x). Every verified CRITICAL/MAJOR defect and OpenCode gap in the spec gets fixed, and the listed optimizations are applied.

**Architecture:** A shared OpenCode compatibility layer lives in `glm-skills/_shared/oc_harness.py`. It covers harness detection, dispatch-line rendering, the run command with the brief on stdin, error-event throttle detection, per-role stall and the lane lifecycle. It is vendored into every skill by `glm-skills/_shared/sync.sh`. Per-skill fixes then run in parallel, each with a disjoint file footprint and its own test files. Last comes an opt-in contract test module that drives the real `opencode` binary against a local fake provider.

**Tech Stack:** Python 3.8+ stdlib, POSIX sh, bash 3.2 (`bisect-parallel.sh` only), Node (`server.cjs`, `helper.js`, OpenCode plugins as ES modules), `unittest`.

## Execution Protocol (for any AI agent or human engineer)

1. A task may start only when every task in its **Depends** and **Runs after**
   lists is complete. Single worker: run tasks in ID order.
2. Parallel workers: follow **Execution Waves**. Tasks in the same wave touch
   disjoint files and MAY run concurrently (marked `[P]`). Never run two tasks
   that modify the same file at once.
3. Within a task, execute steps top to bottom and mark each checkbox `- [x]`
   when done. To resume, continue from the first unchecked step.
4. Run every command exactly as written and compare with **Expected**. On
   mismatch, stop and fix before continuing.
5. Code blocks are the implementation - copy them verbatim. Signatures under
   **Interfaces** are contracts with other tasks: never rename, reorder
   parameters, or change types.
6. Commit exactly where the plan says, with the given message, staging only the
   listed paths. Never batch commits across tasks.
7. **Global Constraints** apply to every task.
8. If anything is ambiguous, missing, or contradicts the codebase, STOP and ask
   the requester. Do not invent behavior.

## Global Constraints

- Edit only files under `glm-skills/`. Never edit the originals one level up (`dev-team-v3.2/`, `writing-plans-6.2/`, …). Never write to `~/.config/opencode`, `~/.claude` or `~/.agents`; tests use temp dirs only.
- All paths in this plan are relative to the git root. Every command runs from `glm-skills/` (start with `cd glm-skills`).
- Unit test command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p '<test file name>'`. Full suite: the same without `-p`. The full suite must end green (baseline: 276 tests, 11 red from stale fixture paths).
- dev-team selftest: `env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh`. It must report `passed=` ≥ 324 and `failed=` ≤ 5. The 5 known macOS failures are: GNU `sed -i`, 4× `/private/var` resolve, a bash 3.2 word-split.
- Scripts stay stdlib-only. No new dependencies.
- The source of truth is `glm-skills/_shared/oc_harness.py` and `glm-skills/_shared/zai_client.py`. A task that changes either file lists the vendored copies in its Files and finishes by running `sh _shared/sync.sh`. The copies must stay byte-identical, and no other task edits a vendored copy.
  - `oc_harness.py` is vendored into `brainstorming-glm`, `dev-team-glm`, `doc-generator-glm`, `requirements-code-audit-glm`, `systematic-debugging-glm` and `writing-plans-glm`.
  - `zai_client.py` is vendored into `requirements-code-audit-glm`, `systematic-debugging-glm` and `writing-plans-glm`.
- No unit test may start a real `opencode` against a real provider or call Z.ai. Use `_shared/tests/stub_opencode.py` and `_shared/tests/fakeapi.py`. The real-binary module `test_oc_contract.py` runs only with `OC_CONTRACT=1`.
- OpenCode facts, all verified 2026-09-28:
  - **Tools.** v2.0.18 tools are `edit, glob, grep, question, read, shell, skill, subagent, webfetch, websearch, write, execute`. The shell input is `{command, workdir, timeout, background}`, write is `{path, content}` and edit is `{path, oldString, newString, replaceAll}`. v1.18.33 tools are `bash, edit, glob, grep, read, skill, task, todowrite, webfetch, write`; its write args are `{filePath, content}`.
  - **Plugin hook.** In v2 the `execute.before` event is `{tool, sessionID, agent, messageID, id, input}`. In v1, `tool.execute.before` gets `(input{tool,sessionID,callID}, output{args})`. In both, throwing inside the hook blocks the tool.
  - **`run` flags.** v2 has `--standalone --server --continue --session --fork --model provider/model#variant --agent --format default|json --file --title --thinking --auto` and no `--dir`. v1 has `--dir --model --agent --format --variant` and no `--standalone`.
  - **Brief.** Both versions read the brief verbatim from stdin when no message argument is given. In v2, an argv message containing whitespace arrives wrapped in literal quotes, and a stdin that stays open hangs the run.
  - **Effort.** In v2 it is sent only through `--model provider/model#effort` (the request gets `reasoning_effort`); `run --agent` ignores the agent's model and variant; `#max` fails with `provider.no-route` unless the provider config defines `variants.max`. In v1 it comes from the agent frontmatter `reasoningEffort` plus `--agent`, and a `#` suffix exits 1.
  - **Events.** v2 JSON event types are `step_start, tool_use, step_finish, text, error`; they are emitted only at step/part boundaries, and the final text step has no `step_finish`.
  - **429.** v2 retries for about 86 s, then emits `{"type":"error","error":{"type":"provider.rate-limit","status":429}}` and exits 1. v1 emits an error with `name: "APIError"` and `data.statusCode: 429`, and `data.responseBody` carries the Z.ai code (`1302`/`1305`).
  - **Env.** v2 sets only `OPENCODE_TERMINAL=1` in shell children and never sets `OPENCODE`.
  - **Built-in agent.** OpenCode's built-in general agent is `general`; `general-purpose` and `Explore` do not exist there.
- SKILL.md frontmatter: `name` never carries the `-glm` suffix, and `description` is ≤ 1024 chars (`test_all_skills.py` enforces both). OpenCode ignores `allowed-tools` and `!` preload blocks.
- `brainstorming-glm/scripts/context.sh` is a preload: read-only, output ≤ 55 lines, always exit 0.
- Prompt style: numbered imperative rules (R0, R1, …), every script prints a `NEXT:` line, and prefix blocks shared across a fan-out wave stay byte-identical.
- The dev-team guard stays fail-open, because the integrate re-check is the real enforcement.
- `guard.py` and `devteam.py` duplicate `TEST_DIR_NAMES`, `TEST_FILE_PATTERNS` and `STATE_DIRNAME`. Change them together or not at all.
- Record each behaviour change in that skill's CHANGELOG or README where one exists.
- Commit messages: `fix(<skill>): …` or `feat(<skill>): …`, where `<skill>` is the folder name without `-glm` (`shared` for `_shared`).

## File Structure

- `glm-skills/_shared/` — sync.sh (T01), oc_harness.py (T03, T04, T05, T35), zai_client.py (T06)
- `glm-skills/_shared/tests/` — test_vendored.py (T01), test_devteam_plugins.py (T01, T09), stub_opencode.py (T02), test_stub_opencode.py (T02), test_oc_harness_detect.py (T03), test_oc_run.py (T04), test_oc_render.py (T05), test_zai_client.py (T06), test_guard_oc.py (T07), test_guard_readonly.py (T08), test_devteam_oc_harness.py (T11), test_devteam_oc_lanes.py (T12), test_devteam_oc_resume.py (T13), test_debug_core.py (T16), test_debug_experiment.py (T17), test_adopt_debug.py (T18), test_debug_scripts.py (T19), test_audit_retrieval.py (T21), test_audit_verdicts.py (T22), test_audit_command.py (T23), test_audit_setup_oc.py (T24), test_adopt_audit.py (T25), test_plan_lint.py (T26), test_adopt_plan.py (T27), test_plan_perf.py (T28), test_brainstorm_oc.py (T30), test_brainstorm_server.py (T31), test_oc_install.py (T33), test_all_skills.py (T34), test_oc_contract.py (T35), fake_provider.py (T35)
- `glm-skills/brainstorming-glm/scripts/` — oc_harness.py (T03, T04, T05, T35), context.sh (T30), start-server.sh (T31), server.cjs (T31), helper.js (T31)
- `glm-skills/dev-team-glm/scripts/` — oc_harness.py (T03, T04, T05, T35), guard.py (T07, T08), devteam.py (T11, T12, T13), selftest.sh (T14)
- `glm-skills/doc-generator-glm/scripts/` — oc_harness.py (T03, T04, T05, T35)
- `glm-skills/requirements-code-audit-glm/scripts/` — oc_harness.py (T03, T04, T05, T35), zai_client.py (T06), audit.py (T21, T22, T23, T24)
- `glm-skills/systematic-debugging-glm/scripts/` — oc_harness.py (T03, T04, T05, T35), zai_client.py (T06), debug_tool.py (T16, T17, T18), bisect-parallel.sh (T19), stress.sh (T19)
- `glm-skills/writing-plans-glm/scripts/` — oc_harness.py (T03, T04, T05, T35), zai_client.py (T06), plan_tool.py (T26, T27, T28)
- `glm-skills/dev-team-glm/opencode/plugins/` — devteam-guard.v1.js (T09), devteam-guard.v2.js (T09)
- `glm-skills/dev-team-glm/opencode/agents/` — programmer.md (T10), team-leader.md (T10)
- `glm-skills/dev-team-glm/` — SKILL.md (T15), README.md (T15)
- `glm-skills/systematic-debugging-glm/` — SKILL.md (T20), README.md (T20)
- `glm-skills/systematic-debugging-glm/opencode/agents/` — debug-worker.md (T20)
- `glm-skills/systematic-debugging-glm/opencode/commands/` — debug.md (T20)
- `glm-skills/systematic-debugging-glm/references/` — glm-tuning.md (T20)
- `glm-skills/requirements-code-audit-glm/` — SKILL.md (T25), SETUP.md (T25)
- `glm-skills/requirements-code-audit-glm/opencode/agents/` — rca-investigator.md (T25), rca-verifier.md (T25)
- `glm-skills/writing-plans-glm/opencode/agents/` — plan-task-writer.md (T27), plan-task-writer-deep.md (T27), plan-reviewer.md (T27)
- `glm-skills/writing-plans-glm/` — SKILL.md (T29), CHANGELOG.md (T29)
- `glm-skills/brainstorming-glm/` — SKILL.md (T32), architectural.md (T32), visual-companion.md (T32), CHANGELOG.md (T32)
- `glm-skills/brainstorming-glm/opencode/agents/` — researcher.md (T32)
- `glm-skills/` — install-opencode.sh (T33), CLAUDE.md (T36)
- `glm-skills/doc-generator-glm/` — SKILL.md (T34)
- `glm-skills/doc-generator-glm/opencode/commands/` — docs.md (T34, T35)

## Contracts

#### T01: Repair sync.sh and stale test fixture paths
- Files: `glm-skills/_shared/sync.sh`, `glm-skills/_shared/tests/test_vendored.py`, `glm-skills/_shared/tests/test_devteam_plugins.py`
- Produces: `sh _shared/sync.sh [DEST_ROOT]` (default DEST_ROOT = the `glm-skills` dir that contains `_shared`; paths resolved from the script location; never creates dirs outside DEST_ROOT)
- Spec: L107-131, L299-335
- Tier: light

#### T02: stub_opencode.py matches real v1 and v2
- Files: `glm-skills/_shared/tests/stub_opencode.py`, `glm-skills/_shared/tests/test_stub_opencode.py`
- Produces: stub env `STUB_OC_VERSION` (a value starting `2.` selects v2 behaviour: rejects `--dir`, requires `--standalone`, events carry `timestamp`/`sessionID`, the final text has no `step_finish`, errors use `{"type":"error","error":{"type":"provider.rate-limit","status":429}}`; otherwise v1 behaviour: accepts `--dir`, rejects `--standalone` and the `#` model suffix, errors use `{"type":"error","error":{"name":"APIError","data":{"statusCode":429,"responseBody":"{\"error\":{\"code\":\"1302\"}}"}}}`); stub reads the brief from stdin when argv has no message; `STUB_OC_LOG` lines are `{"argv": [...], "stdin": "..."}`; brief keyword `aborted` emits `{"type":"aborted"}`
- Spec: L107-131, L336-368
- Read: `glm-skills/_shared/tests/test_oc_run.py`
- Tier: std

#### T03: Shared harness detection, major version and dispatch lines
- Files: `glm-skills/_shared/oc_harness.py`, `glm-skills/brainstorming-glm/scripts/oc_harness.py`, `glm-skills/dev-team-glm/scripts/oc_harness.py`, `glm-skills/doc-generator-glm/scripts/oc_harness.py`, `glm-skills/requirements-code-audit-glm/scripts/oc_harness.py`, `glm-skills/systematic-debugging-glm/scripts/oc_harness.py`, `glm-skills/writing-plans-glm/scripts/oc_harness.py`, `glm-skills/_shared/tests/test_oc_harness_detect.py`
- Produces: `def harness(script_path: str = "") -> str`; `def major(skill_dir: str = "", binary: str = "opencode") -> int`; `def dispatch_line(agent: str, prompt_path: str, description: str, major: int, background: bool = True) -> str`; CLI `python3 oc_harness.py harness [--script PATH]` printing `<harness> <major>`
- Consumes: `def detect(binary: str = "opencode") -> int` (existing); `def check_run_flags(major: int, binary: str = "opencode") -> list` (existing)
- Spec: L72-100, L107-131, L336-368
- Read: `glm-skills/writing-plans-glm/scripts/plan_tool.py`
- Tier: std

#### T04: Run path: brief on stdin, error-event throttles, per-role stall, lifecycle, result
- Depends: T02
- Files: `glm-skills/_shared/oc_harness.py`, `glm-skills/brainstorming-glm/scripts/oc_harness.py`, `glm-skills/dev-team-glm/scripts/oc_harness.py`, `glm-skills/doc-generator-glm/scripts/oc_harness.py`, `glm-skills/requirements-code-audit-glm/scripts/oc_harness.py`, `glm-skills/systematic-debugging-glm/scripts/oc_harness.py`, `glm-skills/writing-plans-glm/scripts/oc_harness.py`, `glm-skills/_shared/tests/test_oc_run.py`
- Produces: `def build_run_cmd(lane: dict, major: int, binary: str = "opencode") -> list` (brief no longer in argv; `_start_lane` writes it to stdin and closes stdin); `def is_throttle_event(event: dict) -> bool`; `STALL_BY_ROLE = {"programmer": 900, "programmer-lite": 900, "team-leader": 900, "code-reviewer": 600, "spot-reviewer": 600, "investigator": 600}`; `def lane_stall(lane: dict, default: int = 180) -> int`; `def lane_results(out_dir: str) -> list`; CLI `python3 oc_harness.py result OUT_DIR`; pgid file `<out_dir>/<lane id>.pgid`; `def check(skill_dir: str, home: str = "") -> list`
- Spec: L72-100, L107-131, L288-298, L336-368
- Tier: deep

#### T05: Agent rendering and config snippet for v1/v2
- Files: `glm-skills/_shared/oc_harness.py`, `glm-skills/brainstorming-glm/scripts/oc_harness.py`, `glm-skills/dev-team-glm/scripts/oc_harness.py`, `glm-skills/doc-generator-glm/scripts/oc_harness.py`, `glm-skills/requirements-code-audit-glm/scripts/oc_harness.py`, `glm-skills/systematic-debugging-glm/scripts/oc_harness.py`, `glm-skills/writing-plans-glm/scripts/oc_harness.py`, `glm-skills/_shared/tests/test_oc_render.py`
- Produces: `def config_snippet(major: int, deny: list) -> str` (adds `variants` low/high/max with `reasoningEffort` for `glm-5.3` and `glm-5.3-flash` under `zai-coding-plan`, plus a websearch provider note and the `web-search-prime` MCP option); `def render_agent(text: str, major: int) -> str` (adds `execute: deny` and an explicit `websearch` permission; keeps `hidden` as today)
- Spec: L72-100, L107-131, L336-368
- Tier: std

#### T06: zai_client key discovery
- Files: `glm-skills/_shared/zai_client.py`, `glm-skills/requirements-code-audit-glm/scripts/zai_client.py`, `glm-skills/systematic-debugging-glm/scripts/zai_client.py`, `glm-skills/writing-plans-glm/scripts/zai_client.py`, `glm-skills/_shared/tests/test_zai_client.py`
- Produces: `def find_key(extra_env: tuple = ()) -> tuple` (never returns `ANTHROPIC_API_KEY`); `def _opencode_db_key(db_path: str) -> str`
- Spec: L72-100, L107-131
- Tier: std

#### T07: guard.py oc-mode input hardening
- Files: `glm-skills/dev-team-glm/scripts/guard.py`, `glm-skills/_shared/tests/test_guard_oc.py`
- Spec: L132-151, L336-368
- Tier: deep

#### T08: guard.py read-only allow-list holes
- Files: `glm-skills/dev-team-glm/scripts/guard.py`, `glm-skills/_shared/tests/test_guard_readonly.py`
- Spec: L132-151
- Tier: deep

#### T09: devteam-guard plugins v1/v2
- Depends: T01
- Files: `glm-skills/dev-team-glm/opencode/plugins/devteam-guard.v1.js`, `glm-skills/dev-team-glm/opencode/plugins/devteam-guard.v2.js`, `glm-skills/_shared/tests/test_devteam_plugins.py`
- Produces: plugins spawn `guard.py oc` only for tools `write`, `edit`, `patch`, `apply_patch`, `multiedit`, `shell`, `bash`, `execute`, `batch`; v2 uses `event.agent` as the role when `DEVTEAM_ROLE` is unset and the agent is one of `programmer`, `programmer-lite`, `code-reviewer`, `spot-reviewer`, `investigator`, `team-leader`
- Spec: L132-151, L336-368
- Tier: std

#### T10: dev-team OpenCode agent files
- Files: `glm-skills/dev-team-glm/opencode/agents/programmer.md`, `glm-skills/dev-team-glm/opencode/agents/team-leader.md`
- Spec: L132-151
- Read: `glm-skills/dev-team-glm/scripts/devteam.py`
- Tier: light

#### T11: devteam.py harness detection and dispatch routing
- Depends: T03
- Files: `glm-skills/dev-team-glm/scripts/devteam.py`, `glm-skills/_shared/tests/test_devteam_oc_harness.py`
- Consumes: `def harness(script_path: str = "") -> str`; `def major(skill_dir: str = "", binary: str = "opencode") -> int`
- Spec: L152-172
- Tier: std

#### T12: devteam.py lane lifecycle
- Depends: T04
- Files: `glm-skills/dev-team-glm/scripts/devteam.py`, `glm-skills/_shared/tests/test_devteam_oc_lanes.py`
- Consumes: `STALL_BY_ROLE = {"programmer": 900, "programmer-lite": 900, "team-leader": 900, "code-reviewer": 600, "spot-reviewer": 600, "investigator": 600}`; `def lane_stall(lane: dict, default: int = 180) -> int`; pgid file `<out_dir>/<lane id>.pgid`
- Spec: L152-172, L288-298
- Tier: deep

#### T13: devteam.py detached checkpoint and resume command
- Files: `glm-skills/dev-team-glm/scripts/devteam.py`, `glm-skills/_shared/tests/test_devteam_oc_resume.py`
- Produces: CLI `devteam.py resume <slice id> [--note TEXT]` (relaunches a fresh lane in the slice's existing worktree with the note appended to the brief, resets `.slice/stop_blocks`, clears stale `.done`/`.blocked` markers, prints a `NEXT:` line); checkpoint runs detached like `launch_lane` and is collected by `wait`/`next`
- Spec: L152-172
- Tier: deep

#### T14: dev-team selftest checks
- Depends: T08, T11, T13
- Files: `glm-skills/dev-team-glm/scripts/selftest.sh`
- Spec: L132-172, L299-335
- Tier: std

#### T15: dev-team SKILL.md and README for OpenCode
- Depends: T13, T11
- Files: `glm-skills/dev-team-glm/SKILL.md`, `glm-skills/dev-team-glm/README.md`
- Spec: L72-100, L132-172
- Read: `glm-skills/systematic-debugging-glm/SKILL.md`
- Tier: std

#### T16: debug_tool.py parallel defaults, lane routing, quoting, timing
- Files: `glm-skills/systematic-debugging-glm/scripts/debug_tool.py`, `glm-skills/_shared/tests/test_debug_core.py`
- Spec: L173-195
- Tier: std

#### T17: debug_tool.py experiment worktrees and patch order
- Files: `glm-skills/systematic-debugging-glm/scripts/debug_tool.py`, `glm-skills/_shared/tests/test_debug_experiment.py`
- Spec: L173-195
- Tier: deep

#### T18: debug_tool.py OpenCode lanes and scan context
- Depends: T03, T05
- Files: `glm-skills/systematic-debugging-glm/scripts/debug_tool.py`, `glm-skills/_shared/tests/test_adopt_debug.py`
- Consumes: `def harness(script_path: str = "") -> str`; `def major(skill_dir: str = "", binary: str = "opencode") -> int`; `def dispatch_line(agent: str, prompt_path: str, description: str, major: int, background: bool = True) -> str`; `def config_snippet(major: int, deny: list) -> str`
- Spec: L72-100, L173-195
- Tier: std

#### T19: systematic-debugging shell script fixes
- Files: `glm-skills/systematic-debugging-glm/scripts/bisect-parallel.sh`, `glm-skills/systematic-debugging-glm/scripts/stress.sh`, `glm-skills/_shared/tests/test_debug_scripts.py`
- Spec: L173-195
- Tier: light

#### T20: systematic-debugging docs, agent and command for OpenCode
- Depends: T17, T18
- Files: `glm-skills/systematic-debugging-glm/SKILL.md`, `glm-skills/systematic-debugging-glm/opencode/agents/debug-worker.md`, `glm-skills/systematic-debugging-glm/opencode/commands/debug.md`, `glm-skills/systematic-debugging-glm/references/glm-tuning.md`, `glm-skills/systematic-debugging-glm/README.md`
- Spec: L72-100, L173-195
- Tier: light

#### T21: audit.py retrieval and citation paths
- Files: `glm-skills/requirements-code-audit-glm/scripts/audit.py`, `glm-skills/_shared/tests/test_audit_retrieval.py`
- Spec: L196-220
- Tier: std

#### T22: audit.py verdict pipeline
- Files: `glm-skills/requirements-code-audit-glm/scripts/audit.py`, `glm-skills/_shared/tests/test_audit_verdicts.py`
- Spec: L196-220
- Tier: deep

#### T23: audit.py CLI state and resume
- Files: `glm-skills/requirements-code-audit-glm/scripts/audit.py`, `glm-skills/_shared/tests/test_audit_command.py`
- Spec: L196-220
- Tier: std

#### T24: audit.py OpenCode dispatch and batch sizing
- Depends: T03, T04
- Files: `glm-skills/requirements-code-audit-glm/scripts/audit.py`, `glm-skills/_shared/tests/test_audit_setup_oc.py`
- Consumes: `def harness(script_path: str = "") -> str`; `def major(skill_dir: str = "", binary: str = "opencode") -> int`; `def dispatch_line(agent: str, prompt_path: str, description: str, major: int, background: bool = True) -> str`; CLI `python3 oc_harness.py result OUT_DIR`
- Spec: L72-100, L196-220
- Tier: std

#### T25: requirements-code-audit docs and OpenCode agents
- Depends: T24
- Files: `glm-skills/requirements-code-audit-glm/SKILL.md`, `glm-skills/requirements-code-audit-glm/SETUP.md`, `glm-skills/requirements-code-audit-glm/opencode/agents/rca-investigator.md`, `glm-skills/requirements-code-audit-glm/opencode/agents/rca-verifier.md`, `glm-skills/_shared/tests/test_adopt_audit.py`
- Spec: L196-220
- Tier: light

#### T26: plan_tool.py linter fixes
- Files: `glm-skills/writing-plans-glm/scripts/plan_tool.py`, `glm-skills/_shared/tests/test_plan_lint.py`
- Spec: L221-240
- Tier: std

#### T27: plan_tool.py OpenCode dispatch, agents and grouping
- Depends: T03
- Files: `glm-skills/writing-plans-glm/scripts/plan_tool.py`, `glm-skills/writing-plans-glm/opencode/agents/plan-task-writer.md`, `glm-skills/writing-plans-glm/opencode/agents/plan-task-writer-deep.md`, `glm-skills/writing-plans-glm/opencode/agents/plan-reviewer.md`, `glm-skills/_shared/tests/test_adopt_plan.py`
- Consumes: `def harness(script_path: str = "") -> str`; `def major(skill_dir: str = "", binary: str = "opencode") -> int`; `def dispatch_line(agent: str, prompt_path: str, description: str, major: int, background: bool = True) -> str`
- Produces: OpenCode agents `plan-task-writer` (flash, `steps: 24`), `plan-task-writer-deep` (glm-5.3, effort max, `steps: 24`), `plan-reviewer` (glm-5.3, effort high); writer groups hold ≤ 4 tasks; group count = ceil(tasks / 4) capped at the lane width (default 8) on OpenCode
- Spec: L72-100, L221-240
- Tier: std

#### T28: plan_tool.py speed optimizations
- Files: `glm-skills/writing-plans-glm/scripts/plan_tool.py`, `glm-skills/_shared/tests/test_plan_perf.py`
- Spec: L221-240
- Tier: std

#### T29: writing-plans SKILL.md bootstrap and CHANGELOG
- Depends: T27
- Files: `glm-skills/writing-plans-glm/SKILL.md`, `glm-skills/writing-plans-glm/CHANGELOG.md`
- Spec: L72-100, L221-240
- Read: `glm-skills/systematic-debugging-glm/SKILL.md`
- Tier: light

#### T30: brainstorming context.sh OpenCode detection
- Depends: T03
- Files: `glm-skills/brainstorming-glm/scripts/context.sh`, `glm-skills/_shared/tests/test_brainstorm_oc.py`
- Consumes: CLI `python3 oc_harness.py harness [--script PATH]` printing `<harness> <major>`
- Spec: L241-262
- Tier: std

#### T31: brainstorming visual-companion scripts
- Files: `glm-skills/brainstorming-glm/scripts/start-server.sh`, `glm-skills/brainstorming-glm/scripts/server.cjs`, `glm-skills/brainstorming-glm/scripts/helper.js`, `glm-skills/_shared/tests/test_brainstorm_server.py`
- Spec: L241-262
- Tier: std

#### T32: brainstorming SKILL.md, playbooks and researcher agent
- Depends: T04, T30
- Files: `glm-skills/brainstorming-glm/SKILL.md`, `glm-skills/brainstorming-glm/architectural.md`, `glm-skills/brainstorming-glm/visual-companion.md`, `glm-skills/brainstorming-glm/opencode/agents/researcher.md`, `glm-skills/brainstorming-glm/CHANGELOG.md`
- Consumes: CLI `python3 oc_harness.py result OUT_DIR`
- Spec: L72-100, L241-262
- Tier: std

#### T33: install-opencode.sh clash and stale-install warnings
- Depends: T05
- Files: `glm-skills/install-opencode.sh`, `glm-skills/_shared/tests/test_oc_install.py`
- Spec: L107-131
- Tier: std

#### T34: doc-generator OpenCode agent names and command
- Files: `glm-skills/doc-generator-glm/SKILL.md`, `glm-skills/doc-generator-glm/opencode/commands/docs.md`, `glm-skills/_shared/tests/test_all_skills.py`
- Spec: L263-272
- Tier: light

#### T35: Real-binary contract tests and sandbox discovery check
- Depends: T04, T05, T09, T33
- Files: `glm-skills/_shared/tests/test_oc_contract.py`, `glm-skills/_shared/tests/fake_provider.py`, `glm-skills/_shared/oc_harness.py`, `glm-skills/brainstorming-glm/scripts/oc_harness.py`, `glm-skills/dev-team-glm/scripts/oc_harness.py`, `glm-skills/doc-generator-glm/scripts/oc_harness.py`, `glm-skills/requirements-code-audit-glm/scripts/oc_harness.py`, `glm-skills/systematic-debugging-glm/scripts/oc_harness.py`, `glm-skills/writing-plans-glm/scripts/oc_harness.py`, `glm-skills/doc-generator-glm/opencode/commands/docs.md`
- Consumes: `def build_run_cmd(lane: dict, major: int, binary: str = "opencode") -> list`; `def config_snippet(major: int, deny: list) -> str`; `def render_agent(text: str, major: int) -> str`
- Produces: `OC_CONTRACT=1` opt-in module; `render_agent` stops emitting `hidden` on v2 only if the test proves a hidden agent cannot be dispatched by the `subagent` tool; `/docs` gains a `` !`cmd` `` recon line only if the test proves v2 expands it
- Spec: L263-272, L299-368
- Tier: deep

#### T36: glm-skills CLAUDE.md harness facts
- Depends: T35
- Files: `glm-skills/CLAUDE.md`
- Spec: L336-381
- Tier: light

<!-- WAVES -->
## Execution Waves

Every task in a wave has all its Depends/Runs-after tasks in earlier waves. Tasks in the
same wave touch disjoint files, so a wave's `[P]` tasks may all run at once.

- **Wave 1:** T01 [P], T02 [P], T03 [P], T06 [P], T07 [P], T10 [P], T16 [P], T19 [P], T21 [P], T26 [P], T31 [P], T34 [P]
- **Wave 2:** T04 [P], T08 [P], T09 [P], T11 [P], T17 [P], T22 [P], T27 [P], T30 [P]
- **Wave 3:** T05 [P], T12 [P], T23 [P], T28 [P], T29 [P], T32 [P]
- **Wave 4:** T13 [P], T18 [P], T24 [P], T33 [P]
- **Wave 5:** T14 [P], T15 [P], T20 [P], T25 [P], T35 [P]
- **Wave 6:** T36
<!-- /WAVES -->

<!-- TASKS -->

### T01: Repair sync.sh and stale test fixture paths [P]

**Depends:** —

**Interfaces:**
- Produces: `sh _shared/sync.sh [DEST_ROOT]`; `glm-skills`; `_shared`

**Files:**
- Modify: `glm-skills/_shared/sync.sh`
- Modify: `glm-skills/_shared/tests/test_vendored.py`
- Modify: `glm-skills/_shared/tests/test_devteam_plugins.py`

The sync.sh script must be completed to produce the `sh _shared/sync.sh [DEST_ROOT]` command with correct path resolution.

- [ ] **Step 1: Fix sync.sh to resolve paths relative to script location**

The script currently assumes hardcoded relative paths (`../../..` and `skills/glm/_shared`) that don't exist and create directories outside the repo. Resolve all paths relative to the script's own location.

```sh
#!/bin/sh

set -e

script_dir=$(cd "$(dirname "$0")" && pwd)
dest_root="${1:-$(dirname "$script_dir")}"

zai_client_src="$script_dir/zai_client.py"
oc_harness_src="$script_dir/oc_harness.py"

zai_skills="systematic-debugging-glm writing-plans-glm requirements-code-audit-glm"
oc_skills="systematic-debugging-glm writing-plans-glm requirements-code-audit-glm brainstorming-glm doc-generator-glm dev-team-glm"

for skill in $zai_skills; do
    dest="$dest_root/$skill/scripts/zai_client.py"
    mkdir -p "$(dirname "$dest")"
    cp "$zai_client_src" "$dest"
    echo "synced $dest"
done

for skill in $oc_skills; do
    dest="$dest_root/$skill/scripts/oc_harness.py"
    mkdir -p "$(dirname "$dest")"
    cp "$oc_harness_src" "$dest"
    echo "synced $dest"
done
```

- [ ] **Step 2: Run test_vendored to verify sync.sh works**

Run: `cd /Users/yamazaki-ethan/Documents/Projects/skillz/glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_vendored.py' -v`
Expected: FAIL with `FileNotFoundError` or `AssertionError` because test paths still hardcode `skills/glm/...`

- [ ] **Step 3: Fix test_vendored.py to derive paths from __file__**

Replace the hardcoded `skills/glm/_shared` with derived paths:

```python
import unittest
import os
import hashlib
import subprocess


class TestVendored(unittest.TestCase):
    def test_sync_copies_and_verifies_identity(self):
        """Test that sync.sh copies files and they are byte-identical to sources."""
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
        shared_dir = os.path.join(repo_root, 'glm-skills/_shared')

        zai_client_src = os.path.join(shared_dir, 'zai_client.py')
        oc_harness_src = os.path.join(shared_dir, 'oc_harness.py')

        skills = {
            'zai_client.py': ['systematic-debugging-glm', 'writing-plans-glm', 'requirements-code-audit-glm'],
            'oc_harness.py': ['systematic-debugging-glm', 'writing-plans-glm', 'requirements-code-audit-glm', 'brainstorming-glm', 'doc-generator-glm', 'dev-team-glm']
        }

        sync_script = os.path.join(shared_dir, 'sync.sh')
        result = subprocess.run(['sh', sync_script, os.path.join(repo_root, 'glm-skills')], cwd=repo_root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"sync.sh failed: {result.stderr}")

        for filename, skill_list in skills.items():
            if filename == 'zai_client.py':
                src = zai_client_src
            else:
                src = oc_harness_src

            with open(src, 'rb') as f:
                src_bytes = f.read()
            src_hash = hashlib.sha256(src_bytes).hexdigest()

            for skill in skill_list:
                dest = os.path.join(repo_root, f'glm-skills/{skill}/scripts/{filename}')
                with open(dest, 'rb') as f:
                    dest_bytes = f.read()
                dest_hash = hashlib.sha256(dest_bytes).hexdigest()

                self.assertEqual(src_hash, dest_hash, f"{filename} in {skill} differs from canonical")

        lines = result.stdout.strip().split('\n')
        expected_count = len(skills['zai_client.py']) + len(skills['oc_harness.py'])
        self.assertEqual(len([l for l in lines if l.startswith('synced ')]), expected_count)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 4: Run test_vendored to verify it passes**

Run: `cd /Users/yamazaki-ethan/Documents/Projects/skillz/glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_vendored.py' -v`
Expected: PASS

- [ ] **Step 5: Fix test_devteam_plugins.py to derive paths from __file__**

Replace lines 10-12 to resolve plugin directory from test file location:

```python
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(TESTS_DIR, "..", "..", "..", ".."))
PLUGIN_DIR = os.path.join(REPO_ROOT, "glm-skills/dev-team-glm/opencode/plugins")
```

- [ ] **Step 6: Run test_devteam_plugins to verify it passes**

Run: `cd /Users/yamazaki-ethan/Documents/Projects/skillz/glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_plugins.py' -v`
Expected: PASS (or skipped if node is not installed; at minimum no FileNotFoundError about `skills/glm/dev-team-glm`)

- [ ] **Step 7: Run full _shared test suite**

Run: `cd /Users/yamazaki-ethan/Documents/Projects/skillz/glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: All tests pass; baseline 276 tests, 11 red from SH1/SH2 should now be green

- [ ] **Step 8: Commit**

```bash
cd /Users/yamazaki-ethan/Documents/Projects/skillz/glm-skills
git add glm-skills/_shared/sync.sh glm-skills/_shared/tests/test_vendored.py glm-skills/_shared/tests/test_devteam_plugins.py
git commit -m "fix(shared): repair sync.sh and test fixture paths

- Resolve sync.sh paths relative to script location instead of hardcoded ../../..
- Add DEST_ROOT parameter to sync.sh (default: parent of _shared)
- Derive test fixture paths from __file__ instead of hardcoding skills/glm/
- Fixes SH1 and SH2: eliminates 11 red tests in baseline suite"
```

---

### T02: stub_opencode.py matches real v1 and v2 [P]

**Depends:** —

**Interfaces:**
- Produces: `STUB_OC_VERSION`; `2.`; `--dir`; `--standalone`; `timestamp`; `sessionID`; `step_finish`; `{"type":"error","error":{"type":"provider.rate-limit","status":429}}`; `--dir`; `--standalone`; `#`; `{"type":"error","error":{"name":"APIError","data":{"statusCode":429,"responseBody":"{\"error\":{\"code\":\"1302\"}}"}}}`; `STUB_OC_LOG`; `{"argv": [...], "stdin": "..."}`; `aborted`; `{"type":"aborted"}`

**Files:**
- Modify: `glm-skills/_shared/tests/stub_opencode.py:1-76`
- Test: `glm-skills/_shared/tests/test_stub_opencode.py`

This task rewrites the test stub so that it has two modes. `STUB_OC_VERSION` values starting with `2.` behave like OpenCode v2.0.x. Any other value (the default is `1.18.33`) behaves like v1.18.x. In both modes the stub reads the brief from stdin when argv has no message. Each `STUB_OC_LOG` line is `{"argv": [...], "stdin": "..."}`. The brief keyword `aborted` emits `{"type":"aborted"}`. The throttle error lines are exact:

- v2: `{"type":"error","error":{"type":"provider.rate-limit","status":429}}`
- v1: `{"type":"error","error":{"name":"APIError","data":{"statusCode":429,"responseBody":"{\"error\":{\"code\":\"1302\"}}"}}}`

Existing brief keywords (`stall_child`, `exit_child`, `throttle`, `stall`, `fail`, `slow`), `STUB_OC_MISSING`, `STUB_CHILD_PID_FILE` and the `run --help` output stay as they are.

Note: after this task, `_shared/tests/test_oc_run.py` still reads the old argv-only log lines and still runs `major=2` lanes against the default v1 mode. That module is updated when `oc_harness` moves the brief to stdin. So the gate for this task is `test_stub_opencode.py`, not the full suite.

- [ ] **Step 1: Write the failing test**

Create `glm-skills/_shared/tests/test_stub_opencode.py`:

```python
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
STUB = os.path.join(HERE, "stub_opencode.py")

V1_THROTTLE = {"type": "error", "error": {"name": "APIError", "data": {
    "statusCode": 429, "responseBody": "{\"error\":{\"code\":\"1302\"}}"}}}
V2_THROTTLE = {"type": "error", "error": {"type": "provider.rate-limit", "status": 429}}
ABORTED = {"type": "aborted"}

V1_RUN = ["run", "--dir", HERE, "--agent", "worker", "-m", "zai-coding-plan/glm-5.3-flash",
          "--format", "json", "--auto"]
V2_RUN = ["run", "--standalone", "--agent", "worker", "--model", "zai-coding-plan/glm-5.3#high",
          "--format", "json", "--auto"]


class StubCase(unittest.TestCase):
    version = "1.18.33"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.log = os.path.join(self.tmp, "argv.log")

    def run_stub(self, args, stdin=""):
        env = dict(os.environ, STUB_OC_VERSION=self.version, STUB_OC_LOG=self.log)
        env.pop("STUB_OC_MISSING", None)
        return subprocess.run([sys.executable, STUB] + args, input=stdin, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=30)

    def events(self, proc):
        return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

    def logged(self):
        with open(self.log) as f:
            return [json.loads(line) for line in f]


class V1ModeTest(StubCase):
    version = "1.18.33"

    def test_version_prints_env_value(self):
        self.assertEqual(self.run_stub(["--version"]).stdout.strip(), "1.18.33")

    def test_accepts_dir_and_ends_with_step_finish(self):
        proc = self.run_stub(V1_RUN + ["one"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        events = self.events(proc)
        self.assertEqual([e["type"] for e in events], ["step_start", "text", "step_finish"])
        self.assertEqual(events[1]["part"]["text"], "done: one")
        self.assertNotIn("timestamp", events[0])

    def test_rejects_standalone(self):
        proc = self.run_stub(["run", "--standalone", "--format", "json", "one"])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--standalone", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_rejects_model_variant_suffix(self):
        args = ["run", "--dir", HERE, "-m", "zai-coding-plan/glm-5.3#high", "--format", "json", "one"]
        proc = self.run_stub(args)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("UnknownError", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_unknown_flag_is_rejected(self):
        proc = self.run_stub(["run", "--bogus", "one"])
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--bogus", proc.stderr)

    def test_throttle_error_shape(self):
        proc = self.run_stub(V1_RUN + ["throttle"])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.events(proc)[-1], V1_THROTTLE)

    def test_aborted_event(self):
        proc = self.run_stub(V1_RUN + ["aborted"])
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.events(proc)[-1], ABORTED)

    def test_reads_brief_from_stdin_when_no_message(self):
        brief = "-leading dash brief\n"
        proc = self.run_stub(V1_RUN, stdin=brief)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.events(proc)[1]["part"]["text"], "done: " + brief)
        self.assertEqual(self.logged(), [{"argv": V1_RUN, "stdin": brief}])

    def test_argv_message_is_logged_with_empty_stdin(self):
        proc = self.run_stub(V1_RUN + ["one two"])
        self.assertEqual(self.events(proc)[1]["part"]["text"], "done: one two")
        self.assertEqual(self.logged(), [{"argv": V1_RUN + ["one two"], "stdin": ""}])


class V2ModeTest(StubCase):
    version = "2.0.18"

    def test_version_prints_env_value(self):
        self.assertEqual(self.run_stub(["--version"]).stdout.strip(), "2.0.18")

    def test_events_carry_timestamp_and_session_and_final_text_has_no_step_finish(self):
        proc = self.run_stub(V2_RUN, stdin="look")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        events = self.events(proc)
        self.assertEqual([e["type"] for e in events],
                         ["step_start", "tool_use", "step_finish", "step_start", "text"])
        self.assertEqual(events[-1]["part"]["text"], "done: look")
        for event in events:
            self.assertIsInstance(event["timestamp"], int)
            self.assertTrue(event["sessionID"])

    def test_rejects_dir(self):
        proc = self.run_stub(V2_RUN + ["--dir", HERE], stdin="look")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--dir", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_requires_standalone(self):
        args = ["run", "--agent", "worker", "--model", "zai-coding-plan/glm-5.3", "--format", "json"]
        proc = self.run_stub(args, stdin="look")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("--standalone", proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_throttle_error_shape(self):
        proc = self.run_stub(V2_RUN, stdin="throttle")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.events(proc)[-1], V2_THROTTLE)

    def test_aborted_event(self):
        proc = self.run_stub(V2_RUN, stdin="aborted")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(self.events(proc)[-1], ABORTED)

    def test_argv_message_with_whitespace_arrives_quoted(self):
        proc = self.run_stub(V2_RUN + ["one two"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.events(proc)[-1]["part"]["text"], 'done: "one two"')

    def test_stdin_brief_is_verbatim_and_logged(self):
        brief = "line one\nline two\n"
        proc = self.run_stub(V2_RUN, stdin=brief)
        self.assertEqual(self.events(proc)[-1]["part"]["text"], "done: " + brief)
        self.assertEqual(self.logged(), [{"argv": V2_RUN, "stdin": brief}])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_stub_opencode.py'`
Expected: FAIL. Among others, `test_rejects_standalone` fails with `AssertionError: 0 != 1`, `test_reads_brief_from_stdin_when_no_message` errors with `TypeError: list indices must be integers or slices, not str` or an `AssertionError`, and the run ends with `FAILED (`.

- [ ] **Step 3: Write minimal implementation**

Replace the whole content of `glm-skills/_shared/tests/stub_opencode.py` with:

```python
#!/usr/bin/env python3
"""Stub `opencode` binary for tests: --version, run --help, run [flags] [message].

STUB_OC_VERSION selects the mode: a value starting "2." behaves like OpenCode
v2.0.x (rejects --dir, requires --standalone, events carry timestamp and
sessionID, the final text step has no step_finish, v2 rate-limit error shape).
Anything else (default 1.18.33) behaves like v1.18.x (accepts --dir, rejects
--standalone and a `#` model suffix, APIError 429 error shape).
The brief is the positional message, or stdin (read to EOF) when there is none.
STUB_OC_LOG gets one JSON line per run: {"argv": [...], "stdin": "..."}.
Brief keywords: stall_child, exit_child, throttle, aborted, stall, fail, slow.
"""
import json
import os
import subprocess
import sys
import time

DEFAULT_VERSION = "1.18.33"
FLAGS = ["--dir", "--agent", "--model", "--format", "--auto", "--standalone"]

V1_VALUE_FLAGS = {"--dir", "--model", "-m", "--agent", "--format", "--variant", "--session",
                  "--file", "--title"}
V1_BOOL_FLAGS = {"--auto", "--continue", "--share"}
V2_VALUE_FLAGS = {"--model", "-m", "--agent", "--format", "--session", "--file", "--title",
                  "--server"}
V2_BOOL_FLAGS = {"--standalone", "--continue", "--fork", "--thinking", "--auto"}

V1_THROTTLE = {"type": "error", "error": {"name": "APIError", "data": {
    "statusCode": 429,
    "responseBody": json.dumps({"error": {"code": "1302"}}, separators=(",", ":")),
}}}
V2_THROTTLE = {"type": "error", "error": {"type": "provider.rate-limit", "status": 429}}
ABORTED = {"type": "aborted"}
SESSION_ID = "ses_stub0001"
TOKENS = {"input": 10, "output": 5}


class UsageError(Exception):
    pass


def version():
    return os.environ.get("STUB_OC_VERSION", DEFAULT_VERSION)


def is_v2():
    return version().startswith("2.")


def emit(event, v2=False):
    if v2:
        event = dict(event, timestamp=int(time.time() * 1000), sessionID=SESSION_ID)
    print(json.dumps(event), flush=True)


def emit_raw(event):
    print(json.dumps(event), flush=True)


def log(argv, stdin):
    path = os.environ.get("STUB_OC_LOG")
    if path:
        with open(path, "a") as f:
            f.write(json.dumps({"argv": argv, "stdin": stdin}) + "\n")


def parse(args, v2):
    value_flags = V2_VALUE_FLAGS if v2 else V1_VALUE_FLAGS
    bool_flags = V2_BOOL_FLAGS if v2 else V1_BOOL_FLAGS
    opts = {}
    message = []
    i = 0
    while i < len(args):
        tok = args[i]
        if tok.startswith("-") and len(tok) > 1:
            name, eq, inline = tok.partition("=")
            if name in value_flags:
                if eq:
                    value = inline
                elif i + 1 < len(args):
                    i += 1
                    value = args[i]
                else:
                    raise UsageError("missing value for %s" % name)
                opts["--model" if name == "-m" else name] = value
            elif name in bool_flags and not eq:
                opts[name] = True
            else:
                raise UsageError("unknown option %s" % name)
        else:
            message.append(tok)
        i += 1
    return opts, message


def check(opts, v2):
    if v2:
        if "--standalone" not in opts:
            return "v2 stub needs --standalone (no managed background service in tests)"
    elif "#" in opts.get("--model", ""):
        return "UnknownError: model variant suffix '#' is not supported"
    return ""


def spawn_child():
    # The child inherits our stdout pipe and outlives us.
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    pid_file = os.environ.get("STUB_CHILD_PID_FILE")
    if pid_file:
        with open(pid_file, "w") as f:
            f.write(str(child.pid))


def behave(brief, v2):
    emit({"type": "step_start", "part": {"type": "step-start"}}, v2)
    if "stall_child" in brief:
        # A kill of only this process leaves the pipe open (needs a process-group kill).
        spawn_child()
        time.sleep(60)
        return 0
    if "exit_child" in brief:
        # This process exits right away; the child still holds our stdout pipe.
        spawn_child()
        return 0
    if "throttle" in brief:
        emit_raw(V2_THROTTLE if v2 else V1_THROTTLE)
        return 1
    if "aborted" in brief:
        emit_raw(ABORTED)
        return 1
    if "stall" in brief:
        time.sleep(60)
        return 0
    if "fail" in brief:
        print("stub failure", file=sys.stderr)
        return 3
    if "slow" in brief:
        time.sleep(1)
    text = {"type": "text", "part": {"type": "text", "text": "done: " + brief}}
    finish = {"type": "step_finish", "part": {"type": "step-finish", "tokens": TOKENS}}
    if v2:
        emit({"type": "tool_use", "part": {"type": "tool", "tool": "read",
                                           "state": {"status": "completed"}}}, v2)
        emit(finish, v2)
        emit({"type": "step_start", "part": {"type": "step-start"}}, v2)
        emit(text, v2)  # v2: the final text step has no step_finish
    else:
        emit(text)
        emit(finish)
    return 0


def main(argv):
    v2 = is_v2()
    if argv[:1] == ["--version"]:
        print(version())
        return 0
    if argv[:1] != ["run"]:
        print("stub opencode: unknown command", file=sys.stderr)
        return 2
    if "--help" in argv:
        missing = os.environ.get("STUB_OC_MISSING", "").split(",")
        for flag in FLAGS:
            if flag not in missing:
                print("  %s  <value>" % flag)
        return 0
    try:
        opts, message = parse(argv[1:], v2)
    except UsageError as exc:
        log(argv, "")
        print("stub opencode: %s" % exc, file=sys.stderr)
        return 1
    stdin = "" if message else sys.stdin.read()
    log(argv, stdin)
    problem = check(opts, v2)
    if problem:
        print("stub opencode: %s" % problem, file=sys.stderr)
        return 1
    brief = " ".join(message) if message else stdin
    if v2 and message and any(c.isspace() for c in brief):
        brief = '"%s"' % brief  # v2 wraps a whitespace argv message in literal quotes
    return behave(brief, v2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_stub_opencode.py'`
Expected: PASS. The output ends with `Ran 17 tests` and `OK`.

- [ ] **Step 5: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add glm-skills/_shared/tests/stub_opencode.py glm-skills/_shared/tests/test_stub_opencode.py
git commit -m "fix(shared): stub_opencode matches real OpenCode v1.18 and v2.0"
```

---

### T03: Shared harness detection, major version and dispatch lines [P]

**Depends:** —

**Interfaces:**
- Uses existing: `def detect(binary: str = "opencode") -> int`; `def check_run_flags(major: int, binary: str = "opencode") -> list`
- Produces: `def harness(script_path: str = "") -> str`; `def major(skill_dir: str = "", binary: str = "opencode") -> int`; `def dispatch_line(agent: str, prompt_path: str, description: str, major: int, background: bool = True) -> str`; `python3 oc_harness.py harness [--script PATH]`; `<harness> <major>`

**Files:**
- Modify: `glm-skills/_shared/oc_harness.py`
- Modify: `glm-skills/brainstorming-glm/scripts/oc_harness.py`
- Modify: `glm-skills/dev-team-glm/scripts/oc_harness.py`
- Modify: `glm-skills/doc-generator-glm/scripts/oc_harness.py`
- Modify: `glm-skills/requirements-code-audit-glm/scripts/oc_harness.py`
- Modify: `glm-skills/systematic-debugging-glm/scripts/oc_harness.py`
- Modify: `glm-skills/writing-plans-glm/scripts/oc_harness.py`
- Test: `glm-skills/_shared/tests/test_oc_harness_detect.py`

All commands run from `glm-skills/` (`cd glm-skills` first). Only `glm-skills/_shared/oc_harness.py` is edited by hand; the six vendored copies are refreshed by `sh _shared/sync.sh` in Step 17.

- [ ] **Step 1: Write the failing harness() tests**

Create `glm-skills/_shared/tests/test_oc_harness_detect.py`:

```python
"""harness(), major(), dispatch_line() and the `harness` CLI subcommand of oc_harness.py."""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.dirname(HERE)
if SHARED not in sys.path:
    sys.path.insert(0, SHARED)

import oc_harness  # noqa: E402


def make_script(root, *parts):
    """Create <root>/<parts...>/scripts/tool.py and return its path."""
    scripts = os.path.join(root, *parts, "scripts")
    os.makedirs(scripts, exist_ok=True)
    path = os.path.join(scripts, "tool.py")
    with open(path, "w") as fh:
        fh.write("")
    return path


def write_marker(skill_dir, text):
    with open(os.path.join(skill_dir, ".oc-major"), "w") as fh:
        fh.write(text)


class HarnessTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-harness-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.plain = make_script(self.tmp, "plain", "demo")

    def test_opencode_terminal_env(self):
        with mock.patch.dict(os.environ, {"OPENCODE_TERMINAL": "1"}, clear=True):
            self.assertEqual(oc_harness.harness(self.plain), "opencode")

    def test_opencode_env(self):
        with mock.patch.dict(os.environ, {"OPENCODE": "1"}, clear=True):
            self.assertEqual(oc_harness.harness(self.plain), "opencode")

    def test_devteam_harness_env(self):
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "opencode"}, clear=True):
            self.assertEqual(oc_harness.harness(self.plain), "opencode")

    def test_project_skills_dir(self):
        script = make_script(self.tmp, "proj", ".opencode", "skills", "demo")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(oc_harness.harness(script), "opencode")

    def test_user_config_skills_dir(self):
        script = make_script(self.tmp, "home", ".config", "opencode", "skills", "demo")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(oc_harness.harness(script), "opencode")

    def test_opencode_config_dir_env(self):
        config = os.path.join(self.tmp, "cfg")
        script = make_script(config, "skills", "demo")
        with mock.patch.dict(os.environ, {"OPENCODE_CONFIG_DIR": config}, clear=True):
            self.assertEqual(oc_harness.harness(script), "opencode")

    def test_oc_major_marker_in_skill_dir(self):
        script = make_script(self.tmp, "anywhere", "demo")
        write_marker(os.path.join(self.tmp, "anywhere", "demo"), "2")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(oc_harness.harness(script), "opencode")

    def test_opencode_path_beats_claude_env(self):
        script = make_script(self.tmp, "proj", ".opencode", "skills", "demo")
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=True):
            self.assertEqual(oc_harness.harness(script), "opencode")

    def test_claude_env(self):
        with mock.patch.dict(os.environ, {"CLAUDECODE": "1"}, clear=True):
            self.assertEqual(oc_harness.harness(self.plain), "claude")

    def test_claude_skills_path(self):
        script = make_script(self.tmp, "home", ".claude", "skills", "demo")
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(oc_harness.harness(script), "claude")

    def test_zcode_env(self):
        with mock.patch.dict(os.environ, {"ZCODE_SESSION": "1"}, clear=True):
            self.assertEqual(oc_harness.harness(self.plain), "zcode")

    def test_unknown(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(oc_harness.harness(self.plain), "unknown")
```

- [ ] **Step 2: Run the harness() tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_harness_detect.py' -k HarnessTest`
Expected: FAIL, 12 errors with "AttributeError: module 'oc_harness' has no attribute 'harness'"

- [ ] **Step 3: Implement harness()**

In `_shared/oc_harness.py`, insert this block directly below the `detect()` function (after its last line `return int(match.group(1))`) and above `def parse_frontmatter`:

```python
OC_SKILL_DIRS = (os.path.join(".opencode", "skills"), os.path.join(".config", "opencode", "skills"))
MAJOR_MARKER = ".oc-major"


def _skill_dir_for(script_path):
    """The skill folder of a script: its parent, or the parent's parent for a `scripts/` dir."""
    folder = os.path.dirname(os.path.abspath(script_path))
    return os.path.dirname(folder) if os.path.basename(folder) == "scripts" else folder


def _has_part(path, rel):
    return (os.sep + rel.strip(os.sep) + os.sep) in path


def _within(path, root):
    for base in (os.path.abspath(root), os.path.realpath(root)):
        base = base.rstrip(os.sep)
        if path == base or path.startswith(base + os.sep):
            return True
    return False


def harness(script_path: str = "") -> str:
    """Return 'opencode', 'claude', 'zcode' or 'unknown' for the harness running script_path.

    v2.0.18 sets only OPENCODE_TERMINAL=1 in shell children, so the script location and the
    install marker count as evidence too. script_path defaults to this module's own file."""
    env = os.environ
    if env.get("OPENCODE") or env.get("OPENCODE_TERMINAL") \
            or env.get("DEVTEAM_HARNESS", "").strip().lower() == "opencode":
        return "opencode"
    script = os.path.abspath(script_path or __file__)
    paths = [script, os.path.realpath(script)]
    config_dir = env.get("OPENCODE_CONFIG_DIR", "")
    for path in paths:
        if any(_has_part(path, rel) for rel in OC_SKILL_DIRS):
            return "opencode"
        if config_dir and _within(path, config_dir):
            return "opencode"
    for folder in (os.path.dirname(script), _skill_dir_for(script)):
        if os.path.isfile(os.path.join(folder, MAJOR_MARKER)):
            return "opencode"
    if env.get("CLAUDECODE") or any(k.startswith("CLAUDE_CODE") for k in env):
        return "claude"
    if any(k.startswith(("ZCODE", "Z_CODE")) for k in env):
        return "zcode"
    for path in paths:
        if _has_part(path, ".zcode"):
            return "zcode"
        if _has_part(path, ".claude"):
            return "claude"
    return "unknown"
```

- [ ] **Step 4: Run the harness() tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_harness_detect.py' -k HarnessTest`
Expected: PASS, "Ran 12 tests" and "OK"

- [ ] **Step 5: Write the failing major() tests**

Append this class to the end of `_shared/tests/test_oc_harness_detect.py`:

```python
class MajorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-major-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        oc_harness._DETECT_CACHE.clear()
        self.addCleanup(oc_harness._DETECT_CACHE.clear)
        self.skill = os.path.join(self.tmp, "demo")
        os.makedirs(self.skill)
        self.missing_binary = os.path.join(self.tmp, "no-such-opencode")

    def fake_binary(self, version):
        """An executable that prints `version` and appends one line to <tmp>/calls per run."""
        path = os.path.join(self.tmp, "opencode")
        with open(path, "w") as fh:
            fh.write('#!/bin/sh\necho call >> "%s"\necho "%s"\n'
                     % (os.path.join(self.tmp, "calls"), version))
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return path

    def calls(self):
        try:
            with open(os.path.join(self.tmp, "calls")) as fh:
                return len(fh.read().splitlines())
        except OSError:
            return 0

    def test_marker_wins_without_spawning(self):
        write_marker(self.skill, "2\n")
        binary = self.fake_binary("1.18.33")
        self.assertEqual(oc_harness.major(self.skill, binary), 2)
        self.assertEqual(self.calls(), 0)

    def test_detect_fallback_is_cached(self):
        binary = self.fake_binary("2.0.18")
        self.assertEqual(oc_harness.major(self.skill, binary), 2)
        self.assertEqual(oc_harness.major(self.skill, binary), 2)
        self.assertEqual(self.calls(), 1)

    def test_bad_marker_falls_back_to_detect(self):
        write_marker(self.skill, "not a number")
        binary = self.fake_binary("1.18.33")
        self.assertEqual(oc_harness.major(self.skill, binary), 1)

    def test_no_marker_no_binary_is_zero(self):
        self.assertEqual(oc_harness.major(self.skill, self.missing_binary), 0)
```

- [ ] **Step 6: Run the major() tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_harness_detect.py' -k MajorTest`
Expected: FAIL, 4 errors with "AttributeError: module 'oc_harness' has no attribute '_DETECT_CACHE'"

- [ ] **Step 7: Implement major()**

In `_shared/oc_harness.py`, insert this block directly below the `harness()` function added in Step 3 (after its final `return "unknown"`):

```python
_DETECT_CACHE = {}


def _read_marker(skill_dir):
    try:
        with open(os.path.join(skill_dir, MAJOR_MARKER)) as fh:
            value = int(fh.read().strip())
    except (OSError, ValueError):
        return 0
    return value if value > 0 else 0


def major(skill_dir: str = "", binary: str = "opencode") -> int:
    """OpenCode major version: the skill's .oc-major marker first, then detect() cached per binary.

    skill_dir defaults to the skill folder holding this module. 0 means unknown / not found."""
    found = _read_marker(skill_dir or _skill_dir_for(__file__))
    if found:
        return found
    if binary not in _DETECT_CACHE:
        _DETECT_CACHE[binary] = detect(binary)
    return _DETECT_CACHE[binary]
```

- [ ] **Step 8: Run the major() tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_harness_detect.py' -k MajorTest`
Expected: PASS, "Ran 4 tests" and "OK"

- [ ] **Step 9: Write the failing dispatch_line() tests**

Append this class to the end of `_shared/tests/test_oc_harness_detect.py`:

```python
class DispatchLineTest(unittest.TestCase):
    def test_v1_task_call(self):
        line = oc_harness.dispatch_line("plan-task-writer", "/w/briefs/T01.md", "plan T01", 1)
        self.assertEqual(
            line,
            'task(subagent_type="plan-task-writer", description="plan T01", '
            'prompt="Read /w/briefs/T01.md and follow it exactly.")')

    def test_v2_background_call(self):
        line = oc_harness.dispatch_line("plan-task-writer", "/w/briefs/T01.md", "plan T01", 2)
        self.assertEqual(
            line,
            'subagent(agent="plan-task-writer", description="plan T01", '
            'prompt="Read /w/briefs/T01.md and follow it exactly.", background=true)')

    def test_v2_foreground_call(self):
        line = oc_harness.dispatch_line("glm-reviewer", "/w/r.md", "review", 2, background=False)
        self.assertTrue(line.startswith('subagent(agent="glm-reviewer", '))
        self.assertTrue(line.endswith("background=false)"))

    def test_fallback_agent_is_general(self):
        for name in ("", "general-purpose", "Explore"):
            for version in (1, 2):
                line = oc_harness.dispatch_line(name, "/w/b.md", "d", version)
                self.assertIn('"general"', line)
                self.assertNotIn("general-purpose", line)
                self.assertNotIn("Explore", line)

    def test_never_emits_a_model(self):
        for version in (1, 2):
            line = oc_harness.dispatch_line("glm-reviewer", "/w/b.md", "d", version)
            self.assertNotIn("model", line)
            self.assertNotIn("haiku", line)
            self.assertNotIn("sonnet", line)
```

- [ ] **Step 10: Run the dispatch_line() tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_harness_detect.py' -k DispatchLineTest`
Expected: FAIL, 5 errors with "AttributeError: module 'oc_harness' has no attribute 'dispatch_line'"

- [ ] **Step 11: Implement dispatch_line()**

In `_shared/oc_harness.py`, insert this block directly below the `major()` function added in Step 7 (after its final `return _DETECT_CACHE[binary]`):

```python
FALLBACK_AGENT = "general"
NON_OC_AGENTS = ("general-purpose", "Explore")


def dispatch_line(agent: str, prompt_path: str, description: str, major: int, background: bool = True) -> str:
    """The tool call a model copies to start one lane.

    v1: task(subagent_type=..., description=..., prompt=...). v2: the renamed dispatch tool with
    agent/description/prompt/background. Never emits a model alias: v2 rejects a model not written
    provider/model. Unknown or Claude-only agent names fall back to the built-in `general`."""
    name = (agent or "").strip()
    if not name or name in NON_OC_AGENTS:
        name = FALLBACK_AGENT
    prompt = "Read %s and follow it exactly." % prompt_path
    quoted = [json.dumps(value, ensure_ascii=False) for value in (name, description, prompt)]
    if major >= 2:
        return "subagent(agent=%s, description=%s, prompt=%s, background=%s)" % (
            quoted[0], quoted[1], quoted[2], "true" if background else "false")
    return "task(subagent_type=%s, description=%s, prompt=%s)" % (quoted[0], quoted[1], quoted[2])
```

- [ ] **Step 12: Run the dispatch_line() tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_harness_detect.py' -k DispatchLineTest`
Expected: PASS, "Ran 5 tests" and "OK"

- [ ] **Step 13: Write the failing CLI tests**

Append this class to the end of `_shared/tests/test_oc_harness_detect.py`:

```python
class HarnessCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-cli-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_cli(self, script, extra_env):
        env = {"PATH": os.environ.get("PATH", ""), "HOME": self.tmp, "PYTHONDONTWRITEBYTECODE": "1"}
        env.update(extra_env)
        return subprocess.run(
            [sys.executable, os.path.join(SHARED, "oc_harness.py"), "harness", "--script", script],
            capture_output=True, text=True, env=env, timeout=30)

    def test_opencode_install_prints_marker_major(self):
        script = make_script(self.tmp, ".config", "opencode", "skills", "demo")
        write_marker(os.path.join(self.tmp, ".config", "opencode", "skills", "demo"), "2")
        result = self.run_cli(script, {})
        self.assertEqual(result.stdout.strip(), "opencode 2")
        self.assertEqual(result.returncode, 0)

    def test_claude_prints_zero_major(self):
        script = make_script(self.tmp, "plain", "demo")
        result = self.run_cli(script, {"CLAUDECODE": "1"})
        self.assertEqual(result.stdout.strip(), "claude 0")
        self.assertEqual(result.returncode, 0)
```

- [ ] **Step 14: Run the CLI tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_harness_detect.py' -k HarnessCliTest`
Expected: FAIL, 2 failures with "AssertionError: '' != 'opencode 2'" and "AssertionError: '' != 'claude 0'" (argparse rejects the unknown `harness` choice)

- [ ] **Step 15: Implement the `harness` subcommand**

The CLI contract is `python3 oc_harness.py harness [--script PATH]`, printing exactly one line `<harness> <major>`.

`main()` assigns a local variable `major` in its `detect` and `install` branches, so calling `major(...)` inside `main()` raises `UnboundLocalError`. The handler therefore goes through a module-level helper. In `_shared/oc_harness.py`, insert this block directly below the `dispatch_line()` function added in Step 11 (after its final `return "task(subagent_type=...` line):

```python
def _harness_line(script_path: str = "") -> str:
    """`<harness> <major>` for the CLI; major stays 0 outside OpenCode so no binary is spawned."""
    script = script_path or __file__
    name = harness(script)
    found = major(_skill_dir_for(script)) if name == "opencode" else 0
    return "%s %d" % (name, found)
```

In `main()` of `_shared/oc_harness.py`, add the parser directly below the line `sub.add_parser("probe-effort", help="check whether OpenCode passes reasoning effort to GLM")`:

```python fragment
    p = sub.add_parser("harness", help="print '<harness> <major>' for the running script")
    p.add_argument("--script", default="", help="script whose location is checked (default: this file)")
```

Then add the handler directly below the `snippet` handler (the `if a.cmd == "snippet":` block that ends with `return 0`) and above `if a.cmd == "run":`:

```python fragment
    if a.cmd == "harness":
        print(_harness_line(a.script))
        return 0
```

The parser block and handler are indented four spaces because they sit inside `main()`; keep that indentation.

- [ ] **Step 16: Run the whole new test module to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_harness_detect.py'`
Expected: PASS, "Ran 23 tests" and "OK"

- [ ] **Step 17: Vendor the shared module into the six skills**

If `_shared/sync.sh` still contains `skills/glm`, its path fix (T01) has not landed yet. Do not run it in that case: the old script runs `mkdir -p` on paths outside the repo before it fails. Copy the file directly instead. The command below makes that choice itself:

Run: `if grep -q 'skills/glm' _shared/sync.sh; then for s in brainstorming-glm dev-team-glm doc-generator-glm requirements-code-audit-glm systematic-debugging-glm writing-plans-glm; do cp _shared/oc_harness.py "$s/scripts/oc_harness.py"; done; else sh _shared/sync.sh; fi && for s in brainstorming-glm dev-team-glm doc-generator-glm requirements-code-audit-glm systematic-debugging-glm writing-plans-glm; do cmp _shared/oc_harness.py "$s/scripts/oc_harness.py" || echo "DIFF $s"; done`
Expected: no `DIFF` line (every vendored copy is byte-identical to `_shared/oc_harness.py`)

- [ ] **Step 18: Run the vendored copy's CLI and the full suite**

Run: `env -u OPENCODE -u OPENCODE_TERMINAL -u DEVTEAM_HARNESS -u OPENCODE_CONFIG_DIR CLAUDECODE=1 python3 dev-team-glm/scripts/oc_harness.py harness --script /tmp/plain/scripts/tool.py`
Expected: `claude 0`

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no failure or error in `test_oc_harness_detect` or `test_vendored`; the only red tests are the pre-existing stale-fixture ones (at most 11 from the baseline of 276, plus the 23 new tests all passing)

- [ ] **Step 19: Commit**

```bash
cd ..
git add glm-skills/_shared/oc_harness.py glm-skills/brainstorming-glm/scripts/oc_harness.py glm-skills/dev-team-glm/scripts/oc_harness.py glm-skills/doc-generator-glm/scripts/oc_harness.py glm-skills/requirements-code-audit-glm/scripts/oc_harness.py glm-skills/systematic-debugging-glm/scripts/oc_harness.py glm-skills/writing-plans-glm/scripts/oc_harness.py glm-skills/_shared/tests/test_oc_harness_detect.py
git commit -m "feat(shared): harness(), major() and dispatch_line() with a harness CLI subcommand"
cd glm-skills
```

---

### T04: Run path: brief on stdin, error-event throttles, per-role stall, lifecycle, result [P]

**Depends:** T02

**Runs after:** T03 (same files)

**Interfaces:**
- Consumes: `STUB_OC_VERSION`; `2.`; `--dir`; `--standalone`; `timestamp`; `sessionID`; `step_finish`; `{"type":"error","error":{"type":"provider.rate-limit","status":429}}`; `--dir`; `--standalone`; `#`; `{"type":"error","error":{"name":"APIError","data":{"statusCode":429,"responseBody":"{\"error\":{\"code\":\"1302\"}}"}}}`; `STUB_OC_LOG`; `{"argv": [...], "stdin": "..."}`; `aborted`; `{"type":"aborted"}`
- Produces: `def build_run_cmd(lane: dict, major: int, binary: str = "opencode") -> list`; `_start_lane`; `def is_throttle_event(event: dict) -> bool`; `STALL_BY_ROLE = {"programmer": 900, "programmer-lite": 900, "team-leader": 900, "code-reviewer": 600, "spot-reviewer": 600, "investigator": 600}`; `def lane_stall(lane: dict, default: int = 180) -> int`; `def lane_results(out_dir: str) -> list`; `python3 oc_harness.py result OUT_DIR`; `<out_dir>/<lane id>.pgid`; `def check(skill_dir: str, home: str = "") -> list`

**Files:**
- Modify: `glm-skills/_shared/oc_harness.py`
- Modify: `glm-skills/brainstorming-glm/scripts/oc_harness.py`
- Modify: `glm-skills/dev-team-glm/scripts/oc_harness.py`
- Modify: `glm-skills/doc-generator-glm/scripts/oc_harness.py`
- Modify: `glm-skills/requirements-code-audit-glm/scripts/oc_harness.py`
- Modify: `glm-skills/systematic-debugging-glm/scripts/oc_harness.py`
- Modify: `glm-skills/writing-plans-glm/scripts/oc_harness.py`
- Test: `glm-skills/_shared/tests/test_oc_run.py`

All commands run from `glm-skills/` (`cd glm-skills` first). Edit only `_shared/oc_harness.py` by hand; the six `scripts/oc_harness.py` copies are regenerated by `sh _shared/sync.sh` in Step 25. Other edits may already have landed in `_shared/oc_harness.py` (harness detection, dispatch rendering, `render_agent`, caching), so locate every edit below by the code it replaces, not by line number. The stub `_shared/tests/stub_opencode.py` already logs one JSON line per run to `$STUB_OC_LOG` in the shape `{"argv": [...], "stdin": "..."}`, emulates v2 when `STUB_OC_VERSION` starts with `2.`, answers the brief `throttle` with a v1 error `{"type":"error","error":{"name":"APIError","data":{"statusCode":429,"responseBody":"{\"error\":{\"code\":\"1302\"}}"}}}` or the v2 error `{"type":"error","error":{"type":"provider.rate-limit","status":429}}`, and answers the brief `aborted` with `{"type":"aborted"}`.

- [ ] **Step 1: Write the failing tests for error-event throttle detection and `aborted`**

In `_shared/tests/test_oc_run.py`, delete the whole `class ThrottleReTest` and put this class in its place:

```python
class IsThrottleEventTest(unittest.TestCase):
    def test_v2_rate_limit_error_is_a_throttle(self):
        self.assertTrue(oc_harness.is_throttle_event(
            {"type": "error", "error": {"type": "provider.rate-limit", "status": 429}}))

    def test_v2_status_429_alone_is_a_throttle(self):
        self.assertTrue(oc_harness.is_throttle_event(
            {"type": "error", "error": {"type": "provider.unknown", "status": 429}}))

    def test_v1_api_error_429_is_a_throttle(self):
        self.assertTrue(oc_harness.is_throttle_event(
            {"type": "error", "error": {"name": "APIError", "data": {"statusCode": 429}}}))

    def test_v1_api_error_body_codes_are_throttles(self):
        for code in ("1302", "1305"):
            body = json.dumps({"error": {"code": code}})
            with self.subTest(code=code):
                self.assertTrue(oc_harness.is_throttle_event(
                    {"type": "error",
                     "error": {"name": "APIError", "data": {"statusCode": 500, "responseBody": body}}}))

    def test_v1_contract_shape_is_a_throttle(self):
        line = ('{"type":"error","error":{"name":"APIError","data":{"statusCode":429,'
                '"responseBody":"{\\"error\\":{\\"code\\":\\"1302\\"}}"}}}')
        self.assertTrue(oc_harness.is_throttle_event(json.loads(line)))

    def test_other_errors_are_not_throttles(self):
        for event in [
            {"type": "error", "error": {"type": "provider.auth", "status": 401}},
            {"type": "error", "error": {"name": "APIError",
                                        "data": {"statusCode": 500,
                                                 "responseBody": '{"error":{"code":"1301"}}'}}},
            {"type": "error", "error": {"name": "APIError", "data": {"statusCode": 500,
                                                                     "responseBody": "not json"}}},
            {"type": "error", "error": "429"},
            {"type": "error"},
        ]:
            with self.subTest(event=event):
                self.assertFalse(oc_harness.is_throttle_event(event))

    def test_tool_output_never_counts(self):
        for event in [
            {"type": "tool_use", "part": {"state": {"output": "HTTP 429 Too Many Requests"}}},
            {"type": "tool_use", "part": {"state": {"output": '{"code":"1302","status":429}'}}},
            {"type": "text", "part": {"type": "text", "text": "the API said 1305"}},
            {"type": "step_finish", "part": {"tokens": {"input": 429}}},
        ]:
            with self.subTest(event=event):
                self.assertFalse(oc_harness.is_throttle_event(event))

    def test_non_dict_is_not_a_throttle(self):
        for event in (None, [], "429", 429):
            self.assertFalse(oc_harness.is_throttle_event(event))
```

Then add these three methods to the end of `class ReadEventsTest`:

```python fragment
    def test_tool_output_quoting_429_is_not_a_throttle(self):
        state = self.run_events([
            '{"type":"tool_use","part":{"state":{"output":"HTTP 429 Too Many Requests"}}}\n',
            '{"type":"tool_use","part":{"state":{"output":"{\\"code\\":\\"1302\\"}"}}}\n',
        ])
        self.assertEqual(state["throttles"], 0)
        self.assertEqual(state["error"], "")

    def test_error_event_throttle_is_counted(self):
        line = '{"type":"error","error":{"type":"provider.rate-limit","status":429}}'
        state = self.run_events([line + "\n"])
        self.assertEqual(state["throttles"], 1)
        self.assertEqual(state["error"], line)

    def test_aborted_event_is_recorded_as_the_lane_error(self):
        state = self.run_events(['{"type":"step_start"}\n', '{"type":"aborted"}\n'])
        self.assertEqual(state["error"], '{"type":"aborted"}')
        self.assertTrue(state["aborted"])
        self.assertEqual(state["throttles"], 0)
```

Then add these two methods to the end of `class RunLanesTest`:

```python fragment
    def test_v2_rate_limit_error_halves_width(self):
        env = {"STUB_OC_VERSION": "2.0.18", "STUB_OC_MISSING": ""}
        with mock.patch.dict(os.environ, env):
            results = oc_harness.run_lanes([lane("t", "throttle"), lane("c", "one")], self.out,
                                           width=2, binary=STUB, major=2)
        self.assertEqual(results[0]["status"], "FAIL")
        self.assertEqual(results[0]["throttles"], 1)
        self.assertIn("provider.rate-limit", results[0]["error"])

    def test_v2_aborted_event_fails_the_lane(self):
        env = {"STUB_OC_VERSION": "2.0.18", "STUB_OC_MISSING": ""}
        with mock.patch.dict(os.environ, env):
            results = oc_harness.run_lanes([lane("x", "aborted")], self.out, binary=STUB, major=2)
        self.assertEqual(results[0]["status"], "FAIL")
        self.assertIn("aborted", results[0]["error"])
        self.assertEqual(self.read_done("x")["status"], "FAIL")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_run.py' -k IsThrottleEventTest -k ReadEventsTest -k test_v2_rate_limit_error_halves_width -k test_v2_aborted_event_fails_the_lane`
Expected: FAIL with "AttributeError: module 'oc_harness' has no attribute 'is_throttle_event'" and "KeyError: 'aborted'"

- [ ] **Step 3: Replace the throttle regex with error-event detection**

In `_shared/oc_harness.py`, delete the whole `THROTTLE_RE = re.compile(...)` statement (the three lines starting `THROTTLE_RE = re.compile(`) and put this in its place, directly above `RUN_FLAGS = [...]`:

```python
THROTTLE_CODES = ("1302", "1305")


def _is_429(value) -> bool:
    return value is not None and str(value).strip() == "429"


def _zai_code(body) -> str:
    """The Z.ai error code inside a v1 `responseBody` (a JSON string or an object), or ""."""
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except ValueError:
            return ""
    if not isinstance(body, dict):
        return ""
    err = body.get("error")
    code = err.get("code") if isinstance(err, dict) else body.get("code")
    return "" if code is None else str(code)


def is_throttle_event(event: dict) -> bool:
    """True only for an OpenCode error event that reports a rate limit.

    v2: `{"type":"error","error":{"type":"provider.rate-limit","status":429}}` (or any status 429).
    v1: `error.name == "APIError"` with `data.statusCode` 429, or a `data.responseBody` Z.ai code
    1302/1305. Tool output, text and step events never count, whatever numbers they quote.
    """
    if not isinstance(event, dict) or event.get("type") != "error":
        return False
    err = event.get("error")
    if not isinstance(err, dict):
        return False
    if err.get("type") == "provider.rate-limit" or _is_429(err.get("status")):
        return True
    data = err.get("data")
    if err.get("name") != "APIError" or not isinstance(data, dict):
        return False
    return _is_429(data.get("statusCode")) or _zai_code(data.get("responseBody")) in THROTTLE_CODES
```

Replace the whole `def _read_events(state):` function with:

```python
def _read_events(state):
    with open(state["out"], "w") as out:
        for line in state["proc"].stdout:
            out.write(line)
            out.flush()
            line = line.strip()
            if not line:
                continue
            state["last"] = time.monotonic()
            state["last_event"] = line[:500]
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            # Only error events feed the governor: tool output quoting "429" or "1302" never does.
            if is_throttle_event(event):
                state["throttles"] += 1
            if event.get("type") == "aborted":
                state["aborted"] = True
                state["error"] = line[:500]
            elif event.get("type") == "error" or event.get("error"):
                state["error"] = line[:500]
```

In `def _finish(state, status, out_dir):` replace these two lines:

```python fragment
    if status is None:
        status = "OK" if code == 0 else "FAIL"
```

with:

```python fragment
    if status is None:
        # v2 `{"type":"aborted"}` fails the lane even when opencode exits 0.
        status = "OK" if code == 0 and not state.get("aborted") else "FAIL"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_run.py' -k IsThrottleEventTest -k ReadEventsTest -k test_v2_rate_limit_error_halves_width -k test_v2_aborted_event_fails_the_lane -k test_throttle_halves_width`
Expected: PASS, last line `OK`

- [ ] **Step 5: Confirm nothing else uses the deleted regex**

Run: `grep -rn "THROTTLE_RE" --include='*.py' _shared`
Expected: no output

- [ ] **Step 6: Write the failing tests for the brief on stdin**

In `class BuildRunCmdTest`, replace the bodies of `test_v1_command`, `test_v2_command_uses_long_model_flag_and_no_dir` and `test_brief_file_is_read` so the three methods read:

```python fragment
    def test_v1_command(self):
        cmd = oc_harness.build_run_cmd(lane("a", "look", dir="/tmp/repo"), 1)
        self.assertEqual(cmd, [
            "opencode", "run", "--dir", "/tmp/repo", "--agent", "worker",
            "-m", "zai-coding-plan/glm-5.3-flash", "--format", "json", "--auto",
        ])

    def test_v2_command_uses_long_model_flag_and_no_dir(self):
        cmd = oc_harness.build_run_cmd(lane("a", "look", dir="/tmp/repo", model="pro"), 2, binary="oc2")
        self.assertEqual(cmd, [
            "oc2", "run", "--standalone", "--agent", "worker",
            "--model", "zai-coding-plan/glm-5.3", "--format", "json", "--auto",
        ])
        self.assertNotIn("--dir", cmd)

    def test_brief_file_is_read(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("brief from file")
        self.addCleanup(os.unlink, f.name)
        self.assertEqual(oc_harness._lane_brief(lane("a", f.name)), "brief from file")
        self.assertNotIn("brief from file", oc_harness.build_run_cmd(lane("a", f.name), 1))
```

Add this method to the end of `class BuildRunCmdTest`:

```python fragment
    def test_brief_is_never_in_argv(self):
        for major in (1, 2):
            with self.subTest(major=major):
                cmd = oc_harness.build_run_cmd(lane("a", "- look at  this"), major)
                self.assertNotIn("- look at  this", cmd)
                self.assertEqual(cmd[-1], "--auto")
```

In `class RunLanesTest`, replace the `read_argvs` method with these two methods:

```python fragment
    def read_log(self, log):
        """One stub log entry per run: {"argv": [...], "stdin": "..."}."""
        with open(log) as f:
            return [json.loads(line) for line in f if line.strip()]

    def read_argvs(self, log):
        return [entry["argv"] for entry in self.read_log(log)]
```

Add these three methods to the end of `class RunLanesTest`:

```python fragment
    def test_brief_goes_to_stdin_not_argv(self):
        log = os.path.join(self.out, "argv.log")
        with mock.patch.dict(os.environ, {"STUB_OC_LOG": log}):
            results = oc_harness.run_lanes([lane("a", "one")], self.out, binary=STUB, major=1)
        self.assertEqual(results[0]["status"], "OK")
        entry = self.read_log(log)[0]
        self.assertEqual(entry["stdin"], "one")
        self.assertNotIn("one", entry["argv"])

    def test_brief_file_content_goes_to_stdin(self):
        log = os.path.join(self.out, "argv.log")
        brief_path = os.path.join(self.out, "brief.md")
        with open(brief_path, "w") as f:
            f.write("one")
        with mock.patch.dict(os.environ, {"STUB_OC_LOG": log}):
            results = oc_harness.run_lanes([lane("a", brief_path)], self.out, binary=STUB, major=1)
        self.assertEqual(results[0]["status"], "OK")
        entry = self.read_log(log)[0]
        self.assertEqual(entry["stdin"], "one")
        self.assertNotIn(brief_path, entry["argv"])

    def test_v2_dash_and_whitespace_brief_arrives_verbatim_and_stdin_is_closed(self):
        log = os.path.join(self.out, "argv.log")
        brief = "- starts with a dash\n  and has  spaces"
        env = {"STUB_OC_LOG": log, "STUB_OC_VERSION": "2.0.18", "STUB_OC_MISSING": ""}
        start = time.monotonic()
        with mock.patch.dict(os.environ, env):
            oc_harness.run_lanes([lane("d", brief)], self.out, stall=30, binary=STUB, major=2)
        self.assertLess(time.monotonic() - start, 15)
        entry = self.read_log(log)[0]
        self.assertEqual(entry["stdin"], brief)
        self.assertNotIn(brief, entry["argv"])
```

- [ ] **Step 7: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_run.py' -k BuildRunCmdTest -k test_brief_goes_to_stdin_not_argv -k test_brief_file_content_goes_to_stdin -k test_v2_dash_and_whitespace_brief`
Expected: FAIL with "AssertionError: Lists differ" and "AttributeError: module 'oc_harness' has no attribute '_lane_brief'"

- [ ] **Step 8: Send the brief on stdin and close it**

In `_shared/oc_harness.py`, replace the whole `def build_run_cmd(...)` function with:

```python
def build_run_cmd(lane: dict, major: int, binary: str = "opencode") -> list:
    """The `opencode run` argv for one lane. The brief is NOT in argv: _start_lane writes it to
    the process's stdin and closes stdin. v2 wraps a whitespace argv message in literal quotes and
    parses a leading `-` as a flag, and Linux argv hits E2BIG past 128 KiB."""
    model = lane.get("model") or "pro"
    if "/" not in model:
        model = PROVIDER + "/" + MODELS.get(model, model)
    # v2 takes effort only as a model variant (`glm-5.3#high`); v1 takes it from the agent's
    # frontmatter `reasoningEffort` and rejects the suffix.
    if major >= 2 and lane.get("effort") in EFFORTS:
        model += "#" + lane["effort"]
    if major < 2:
        # Absolute, so opencode's own --dir resolution can't re-resolve it a
        # second time against the subprocess cwd _start_lane already set to
        # this same directory (which would turn "docs" into "docs/docs").
        lane_dir = os.path.abspath(lane.get("dir") or ".")
        return [binary, "run", "--dir", lane_dir, "--agent", lane["agent"],
                "-m", model, "--format", "json", "--auto"]
    # v2 has no --dir flag; the lane's working directory is instead passed as
    # the subprocess cwd (see _start_lane). --standalone runs a private
    # server in this process instead of talking to opencode's managed
    # background service, so the plugin sees this process's env
    # (DEVTEAM_ROLE/DEVTEAM_SLICE) instead of running inside a shared,
    # long-lived service process.
    return [binary, "run", "--standalone", "--agent", lane["agent"], "--model", model,
            "--format", "json", "--auto"]


def _lane_brief(lane):
    """The lane's brief text: the file's content when `brief` names a file, else the string itself."""
    brief = lane["brief"]
    if os.path.isfile(brief):
        with open(brief) as f:
            return f.read()
    return brief


def _feed_stdin(proc, brief):
    """Write the brief to the lane's stdin, then close it: v2 hangs while stdin stays open."""
    try:
        proc.stdin.write(brief)
    except (OSError, ValueError):
        pass
    finally:
        try:
            proc.stdin.close()
        except (OSError, ValueError):
            pass
```

Replace the whole `def _start_lane(lane, out_dir, major, binary, width):` function with:

```python
def _start_lane(lane, out_dir, major, binary, width):
    lane_id = str(lane["id"])
    err_path = os.path.join(out_dir, lane_id + ".err")
    err_file = open(err_path, "w")
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (lane.get("env") or {}).items()})
    cwd = os.path.abspath(lane.get("dir") or ".")
    # v2 --standalone takes its project root from $PWD, not the real cwd: an inherited PWD would
    # point the lane's file tools at the caller's directory.
    env["PWD"] = cwd
    try:
        brief = _lane_brief(lane)
        proc = subprocess.Popen(build_run_cmd(lane, major, binary), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=err_file, text=True, bufsize=1, env=env,
                                start_new_session=True, cwd=cwd)
    except OSError as exc:
        # A bad lane dir, an unreadable brief file or any other spawn failure
        # must not crash the whole wave; the caller turns this into a per-lane FAIL result.
        err_file.close()
        return {"id": lane_id, "start_error": str(exc)}
    now = time.monotonic()
    state = {"id": lane_id, "proc": proc, "err_path": err_path, "err_file": err_file,
             "out": os.path.join(out_dir, lane_id + ".jsonl"), "start": now, "last": now,
             "timeout": float(lane.get("timeout") or 0), "last_event": "", "error": "",
             "throttles": 0, "seen": 0, "width": width}
    state["reader"] = threading.Thread(target=_read_events, args=(state,), daemon=True)
    state["reader"].start()
    # A separate thread, so a brief larger than the pipe buffer can't block the scheduler.
    threading.Thread(target=_feed_stdin, args=(proc, brief), daemon=True).start()
    return state
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_run.py' -k BuildRunCmdTest -k RunLanesTest`
Expected: PASS, last line `OK`

- [ ] **Step 10: Write the failing tests for per-role stall**

Add this class to `_shared/tests/test_oc_run.py`, directly above `class RunLanesTest`:

```python
class LaneStallTest(unittest.TestCase):
    def test_stall_by_role_table(self):
        self.assertEqual(oc_harness.STALL_BY_ROLE, {
            "programmer": 900, "programmer-lite": 900, "team-leader": 900,
            "code-reviewer": 600, "spot-reviewer": 600, "investigator": 600,
        })

    def test_lane_stall_value_wins(self):
        self.assertEqual(oc_harness.lane_stall({"stall": 42, "role": "programmer"}), 42)
        self.assertEqual(oc_harness.lane_stall({"stall": "42"}), 42)

    def test_role_defaults(self):
        for role, seconds in (("programmer", 900), ("programmer-lite", 900), ("team-leader", 900),
                              ("code-reviewer", 600), ("spot-reviewer", 600), ("investigator", 600)):
            with self.subTest(role=role):
                self.assertEqual(oc_harness.lane_stall({"role": role}), seconds)

    def test_role_from_env_then_agent(self):
        self.assertEqual(oc_harness.lane_stall({"env": {"DEVTEAM_ROLE": "spot-reviewer"}}), 600)
        self.assertEqual(oc_harness.lane_stall({"agent": "team-leader"}), 900)

    def test_unknown_role_uses_default(self):
        self.assertEqual(oc_harness.lane_stall({"agent": "worker"}), 180)
        self.assertEqual(oc_harness.lane_stall({"agent": "worker"}, default=30), 30)

    def test_invalid_stall_falls_through(self):
        self.assertEqual(oc_harness.lane_stall({"stall": "soon", "role": "investigator"}), 600)
        self.assertEqual(oc_harness.lane_stall({"stall": 0}), 180)
        self.assertEqual(oc_harness.lane_stall({"stall": None}, default=7), 7)
```

Add this method to the end of `class RunLanesTest`:

```python fragment
    def test_lane_stall_overrides_run_default(self):
        start = time.monotonic()
        results = oc_harness.run_lanes([lane("z", "stall", stall=1)], self.out, stall=60,
                                       binary=STUB, major=1)
        self.assertLess(time.monotonic() - start, 15)
        self.assertEqual(results[0]["status"], "STALL")
        self.assertIn("no event for 1s", results[0]["error"])
```

- [ ] **Step 11: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_run.py' -k LaneStallTest -k test_lane_stall_overrides_run_default`
Expected: FAIL with "AttributeError: module 'oc_harness' has no attribute 'STALL_BY_ROLE'"

- [ ] **Step 12: Add per-role stall**

In `_shared/oc_harness.py`, directly above `def _read_events(state):`, add:

```python
STALL_BY_ROLE = {"programmer": 900, "programmer-lite": 900, "team-leader": 900, "code-reviewer": 600, "spot-reviewer": 600, "investigator": 600}


def lane_stall(lane: dict, default: int = 180) -> int:
    """Seconds without a JSON event before a lane counts as stalled.

    v2 emits events only at step and part boundaries, so a long shell call or long thinking is
    silent. Order: the lane's own positive `stall`, then STALL_BY_ROLE for its `role`, its env
    `DEVTEAM_ROLE` or its `agent` name, then `default`.
    """
    value = lane.get("stall")
    try:
        if value is not None and int(value) > 0:
            return int(value)
    except (TypeError, ValueError):
        pass
    env = lane.get("env") or {}
    for key in (lane.get("role"), env.get("DEVTEAM_ROLE"), lane.get("agent")):
        if isinstance(key, str) and key in STALL_BY_ROLE:
            return STALL_BY_ROLE[key]
    return int(default)
```

Change the `_start_lane` signature line from:

```python fragment
def _start_lane(lane, out_dir, major, binary, width):
```

to:

```python fragment
def _start_lane(lane, out_dir, major, binary, width, stall=180):
```

and in its `state = {...}` literal replace the last line `"throttles": 0, "seen": 0, "width": width}` with:

```python fragment
             "throttles": 0, "seen": 0, "width": width, "stall": lane_stall(lane, stall)}
```

In `run_lanes`, replace:

```python fragment
                state = _start_lane(pending.pop(0), out_dir, major, binary, width)
```

with:

```python fragment
                state = _start_lane(pending.pop(0), out_dir, major, binary, width, stall)
```

and replace:

```python fragment
                    if now - state["last"] > stall:
                        status = "STALL"
                        state["error"] = "no event for %ss, last event: %s" % (stall, state["last_event"] or "none")
```

with:

```python fragment
                    if now - state["last"] > state["stall"]:
                        status = "STALL"
                        state["error"] = "no event for %ss, last event: %s" % (state["stall"], state["last_event"] or "none")
```

In `main`, replace the `run` parser's stall line `p.add_argument("--stall", type=int, default=180)` with:

```python fragment
    p.add_argument("--stall", type=int, default=180,
                   help="stall seconds for lanes with no `stall` value and no role in STALL_BY_ROLE")
```

- [ ] **Step 13: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_run.py' -k LaneStallTest -k RunLanesTest`
Expected: PASS, last line `OK`

- [ ] **Step 14: Write the failing tests for the pgid file and signal handling**

Add this class to `_shared/tests/test_oc_run.py`, directly above `if __name__ == "__main__":`:

```python
class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out, True)

    def test_pgid_file_names_the_lane_process_group_while_it_runs(self):
        pgid_path = os.path.join(self.out, "p.pgid")
        seen = []

        def sleep_side_effect(*_a, **_kw):
            if os.path.exists(pgid_path):
                with open(pgid_path) as f:
                    seen.append(int(f.read().strip()))
                raise RuntimeError("stop")

        with mock.patch("oc_harness.time.sleep", side_effect=sleep_side_effect):
            with self.assertRaises(RuntimeError):
                oc_harness.run_lanes([lane("p", "stall")], self.out, stall=5, binary=STUB, major=1)
        self.assertEqual(len(seen), 1)
        self.assertGreater(seen[0], 0)
        self.assertFalse(os.path.exists(pgid_path))

    def test_pgid_file_removed_when_lane_finishes(self):
        results = oc_harness.run_lanes([lane("a", "one")], self.out, binary=STUB, major=1)
        self.assertEqual(results[0]["status"], "OK")
        self.assertTrue(os.path.exists(os.path.join(self.out, "a.done")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "a.pgid")))

    def test_signal_handlers_are_restored(self):
        before = signal.getsignal(signal.SIGTERM)
        oc_harness.run_lanes([lane("a", "one")], self.out, binary=STUB, major=1)
        self.assertEqual(signal.getsignal(signal.SIGTERM), before)

    def test_sigterm_kills_every_lane_process_group(self):
        pid_file = os.path.join(self.out, "child.pid")
        script = (
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "import oc_harness\n"
            "oc_harness.run_lanes([%r], %r, binary=%r, major=1)\n"
        ) % (os.path.dirname(HERE), lane("x", "stall_child"), self.out, STUB)
        env = dict(os.environ, STUB_CHILD_PID_FILE=pid_file, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.Popen([sys.executable, "-c", script], env=env)

        def reap():
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        self.addCleanup(reap)
        for _ in range(200):
            if os.path.exists(pid_file) and os.path.getsize(pid_file):
                break
            time.sleep(0.05)
        with open(pid_file) as f:
            child_pid = int(f.read().strip())
        self.assertTrue(os.path.exists(os.path.join(self.out, "x.pgid")))
        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(10), 128 + signal.SIGTERM)
        time.sleep(0.3)
        with self.assertRaises(OSError):
            os.kill(child_pid, 0)
        self.assertFalse(os.path.exists(os.path.join(self.out, "x.pgid")))
```

- [ ] **Step 15: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_run.py' -k LifecycleTest`
Expected: FAIL with "AssertionError: RuntimeError not raised" and "AssertionError: False is not true"

- [ ] **Step 16: Write the pgid file and kill every lane group on SIGTERM/SIGINT**

In `_shared/oc_harness.py`, in `_start_lane`, insert these lines directly after the `except OSError as exc:` block (after its `return {"id": lane_id, "start_error": str(exc)}`) and before `now = time.monotonic()`:

```python fragment
    # start_new_session=True makes the lane its own process-group leader (pgid == pid); callers
    # may os.killpg() the number in <out_dir>/<lane id>.pgid while the lane runs.
    pgid_path = os.path.join(out_dir, lane_id + ".pgid")
    with open(pgid_path, "w") as fh:
        fh.write(str(proc.pid))
```

and in the same function's `state = {...}` literal replace its last line with:

```python fragment
             "throttles": 0, "seen": 0, "width": width, "stall": lane_stall(lane, stall),
             "pgid_path": pgid_path}
```

Directly above `def _absorb(state, width):`, add:

```python
def _drop_pgid(state):
    path = state.get("pgid_path")
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


def _raise_on_signal(signum, frame):
    # Unwinds run_lanes, whose except-branch kills every running lane's process group.
    raise SystemExit(128 + signum)


def _install_signal_handlers():
    """SIGTERM/SIGINT -> SystemExit in run_lanes; returns the previous handlers (main thread only)."""
    if threading.current_thread() is not threading.main_thread():
        return {}
    old = {}
    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            old[signum] = signal.signal(signum, _raise_on_signal)
        except (OSError, ValueError):
            pass
    return old


def _restore_signal_handlers(old):
    for signum, handler in old.items():
        try:
            signal.signal(signum, signal.SIG_DFL if handler is None else handler)
        except (OSError, TypeError, ValueError):
            pass
```

In `def _finish(state, status, out_dir):`, insert as its first line, above `state["err_file"].close()`:

```python fragment
    _drop_pgid(state)
```

In `run_lanes`, replace everything from the line `os.makedirs(out_dir, exist_ok=True)` down to and including the final `return [results[str(item["id"])] for item in lanes]` with:

```python fragment
    os.makedirs(out_dir, exist_ok=True)
    width = max(1, min(int(width), 64))
    pending = list(lanes)
    running = []
    results = {}
    old_handlers = _install_signal_handlers()
    try:
        while pending or running:
            while pending and len(running) < width:
                state = _start_lane(pending.pop(0), out_dir, major, binary, width, stall)
                if "start_error" in state:
                    lane_id = state["id"]
                    results[lane_id] = _write_result(out_dir, lane_id, "FAIL", None,
                                                      state["start_error"], width=width)
                else:
                    running.append(state)
            time.sleep(0.05)
            for state in list(running):
                width = _absorb(state, width)
                status = None
                if state["proc"].poll() is None:
                    now = time.monotonic()
                    if now - state["last"] > state["stall"]:
                        status = "STALL"
                        state["error"] = "no event for %ss, last event: %s" % (state["stall"], state["last_event"] or "none")
                    elif state["timeout"] and now - state["start"] > state["timeout"]:
                        status = "TIMEOUT"
                        state["error"] = "timeout after %ss, last event: %s" % (state["timeout"], state["last_event"] or "none")
                    else:
                        continue
                    _kill_group(state["proc"])
                state["proc"].wait()
                # The lane's own process may have exited on its own while a
                # descendant it spawned (inheriting our stdout pipe) lives on;
                # kill the whole group so the reader thread's read() gets EOF
                # instead of blocking forever on that descendant.
                _kill_group(state["proc"])
                state["reader"].join(5)
                width = _absorb(state, width)
                running.remove(state)
                results[state["id"]] = _finish(state, status, out_dir)
    except BaseException:
        # Exceptions, SIGTERM and SIGINT all land here: no lane outlives the caller.
        for state in running:
            _kill_group(state["proc"])
            _drop_pgid(state)
        raise
    finally:
        _restore_signal_handlers(old_handlers)
    return [results[str(item["id"])] for item in lanes]
```

- [ ] **Step 17: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_run.py' -k LifecycleTest -k RunLanesTest -k KillGroupTest`
Expected: PASS, last line `OK`

- [ ] **Step 18: Write the failing tests for `lane_results` and the `result` subcommand**

At the top of `_shared/tests/test_oc_run.py`, add `import contextlib` above `import json` and `import io` below it, so the imports start:

```python
import contextlib
import io
import json
```

Add this class directly above `if __name__ == "__main__":`:

```python
class LaneResultsTest(unittest.TestCase):
    def setUp(self):
        self.out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.out, True)

    def write_jsonl(self, lane_id, items):
        with open(os.path.join(self.out, lane_id + ".jsonl"), "w") as f:
            for item in items:
                f.write((item if isinstance(item, str) else json.dumps(item)) + "\n")

    def write_done(self, lane_id, status, error=""):
        with open(os.path.join(self.out, lane_id + ".done"), "w") as f:
            json.dump({"id": lane_id, "status": status, "error": error}, f)

    def test_final_text_is_the_last_step_with_text(self):
        self.write_jsonl("a", [
            {"type": "step_start", "part": {}},
            {"type": "text", "part": {"type": "text", "text": "thinking out loud"}},
            {"type": "tool_use", "part": {"state": {"output": "429 Too Many Requests"}}},
            {"type": "step_finish", "part": {}},
            {"type": "step_start", "part": {}},
            {"type": "text", "part": {"type": "text", "text": "FINAL ANSWER"}},
        ])
        self.write_done("a", "OK")
        self.assertEqual(oc_harness.lane_results(self.out),
                         [{"id": "a", "status": "OK", "error": "", "text": "FINAL ANSWER"}])

    def test_trailing_tool_only_step_keeps_the_earlier_text(self):
        self.write_jsonl("a", [
            {"type": "step_start"},
            {"type": "text", "text": "answer"},
            {"type": "step_finish"},
            {"type": "step_start"},
            {"type": "tool_use", "part": {"state": {"output": "ls"}}},
            "not json",
        ])
        self.write_done("a", "OK")
        self.assertEqual(oc_harness.lane_results(self.out)[0]["text"], "answer")

    def test_lane_without_done_is_running_and_rows_are_sorted(self):
        self.write_jsonl("b", [{"type": "text", "part": {"text": "partial"}}])
        self.write_jsonl("a", [])
        self.write_done("a", "FAIL", "boom")
        rows = oc_harness.lane_results(self.out)
        self.assertEqual([r["id"] for r in rows], ["a", "b"])
        self.assertEqual(rows[0], {"id": "a", "status": "FAIL", "error": "boom", "text": ""})
        self.assertEqual(rows[1]["status"], "RUNNING")
        self.assertEqual(rows[1]["text"], "partial")

    def test_missing_out_dir_is_empty(self):
        self.assertEqual(oc_harness.lane_results(os.path.join(self.out, "nope")), [])

    def test_result_cli_prints_each_lane_text(self):
        self.write_jsonl("a", [{"type": "text", "part": {"text": "answer a"}}])
        self.write_done("a", "OK")
        self.write_jsonl("b", [])
        self.write_done("b", "FAIL", "boom")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = oc_harness.main(["result", self.out])
        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("LANE a: OK\nanswer a\n", out)
        self.assertIn("LANE b: FAIL boom\n(no assistant text)\n", out)
        self.assertIn("NEXT: rerun only lanes b", out)

    def test_result_cli_empty_dir_exits_1(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = oc_harness.main(["result", self.out])
        self.assertEqual(code, 1)
        self.assertIn("NEXT:", buf.getvalue())

    def test_result_cli_as_script(self):
        self.write_jsonl("a", [{"type": "text", "part": {"text": "answer a"}}])
        self.write_done("a", "OK")
        script = os.path.join(os.path.dirname(HERE), "oc_harness.py")
        proc = subprocess.run([sys.executable, script, "result", self.out],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("LANE a: OK\nanswer a\n", proc.stdout)
```

- [ ] **Step 19: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_run.py' -k LaneResultsTest`
Expected: FAIL with "AttributeError: module 'oc_harness' has no attribute 'lane_results'"

- [ ] **Step 20: Add `lane_results` and the `result` subcommand**

In `_shared/oc_harness.py`, directly above `PROBE_AGENT = (`, add:

```python
def _event_text(event):
    part = event.get("part")
    if isinstance(part, dict) and isinstance(part.get("text"), str):
        return part["text"]
    text = event.get("text")
    return text if isinstance(text, str) else ""


def _final_text(path):
    """Text of the last step that produced text. v2's final text step has no step_finish, so a
    step is delimited by step_start only."""
    last, current = [], []
    try:
        with open(path) as fh:
            lines = fh.read().splitlines()
    except OSError:
        return ""
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "step_start":
            current = []
        elif event.get("type") == "text":
            text = _event_text(event)
            if text:
                current.append(text)
                last = current
    return "\n".join(last).strip()


def lane_results(out_dir: str) -> list:
    """One dict per lane in out_dir, sorted by id: id, status (RUNNING without a .done), error
    and the lane's final assistant text, so callers never read the raw .jsonl."""
    try:
        names = os.listdir(out_dir)
    except OSError:
        return []
    ids = sorted({n[:-5] for n in names if n.endswith(".done")}
                 | {n[:-6] for n in names if n.endswith(".jsonl")})
    rows = []
    for lane_id in ids:
        try:
            with open(os.path.join(out_dir, lane_id + ".done")) as fh:
                done = json.load(fh)
        except (OSError, ValueError):
            done = {}
        if not isinstance(done, dict):
            done = {}
        rows.append({"id": lane_id, "status": done.get("status") or "RUNNING",
                     "error": done.get("error") or "",
                     "text": _final_text(os.path.join(out_dir, lane_id + ".jsonl"))})
    return rows
```

In `main`, directly after the `run` parser's `--stall` argument, add:

```python fragment
    p = sub.add_parser("result", help="print each lane's final assistant text")
    p.add_argument("out_dir")
```

In the `if a.cmd == "run":` block, replace the line `print("NEXT: read %s/<id>.jsonl for each lane's output" % a.out)` with:

```python fragment
        print("NEXT: python3 %s result %s  (each lane's final answer)" % (os.path.abspath(__file__), a.out))
```

Directly above the final `print("EFFORT %s" % probe_effort())` line in `main`, add:

```python fragment
    if a.cmd == "result":
        rows = lane_results(a.out_dir)
        if not rows:
            print("no lanes in %s" % a.out_dir)
            print("NEXT: pass the --out directory of a `run`")
            return 1
        for r in rows:
            print(("LANE %s: %s %s" % (r["id"], r["status"], r["error"])).rstrip())
            print(r["text"] or "(no assistant text)")
            print("")
        bad = [r["id"] for r in rows if r["status"] != "OK"]
        if bad:
            print("NEXT: rerun only lanes %s after fixing the errors above" % ", ".join(bad))
        else:
            print("NEXT: act on the lane answers above; open %s/<id>.jsonl only to debug a lane" % a.out_dir)
        return 0
```

The CLI form callers use is `python3 oc_harness.py result OUT_DIR` (run from the skill's `scripts/` dir, or with the full path to `oc_harness.py`).

- [ ] **Step 21: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_run.py' -k LaneResultsTest`
Expected: PASS, last line `OK`

- [ ] **Step 22: Write the failing tests for `check()` honouring the home dir**

Add this class directly above `if __name__ == "__main__":`:

```python
class CheckHomeTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.other = tempfile.mkdtemp()
        self.skill = tempfile.mkdtemp()
        for path in (self.home, self.other, self.skill):
            self.addCleanup(shutil.rmtree, path, True)
        with open(os.path.join(self.skill, "SKILL.md"), "w") as f:
            f.write("---\nname: demo\ndescription: demo skill\n---\nbody\n")

    def install_marker(self, major):
        skill_dst = os.path.join(self.home, ".config", "opencode", "skills", "demo")
        os.makedirs(skill_dst)
        with open(os.path.join(skill_dst, ".oc-major"), "w") as f:
            f.write(str(major))

    def test_missing_under_given_home(self):
        self.assertEqual(oc_harness.check(self.skill, home=self.home),
                         ["MISSING: demo is not installed for OpenCode"])

    def test_installed_under_given_home_not_user_home(self):
        self.install_marker(1)
        with mock.patch.dict(os.environ, {"HOME": self.other}):
            with mock.patch("oc_harness.detect", return_value=1):
                lines = oc_harness.check(self.skill, home=self.home)
        self.assertEqual(lines, ["INSTALLED: demo (major 1)"])

    def test_check_cli_home_flag(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = oc_harness.main(["check", self.skill, "--home", self.home])
        self.assertEqual(code, 1)
        self.assertIn("MISSING: demo is not installed for OpenCode", buf.getvalue())
```

- [ ] **Step 23: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_run.py' -k CheckHomeTest`
Expected: FAIL with "TypeError: check() got an unexpected keyword argument 'home'"

- [ ] **Step 24: Honour the home dir in `check()`**

In `_shared/oc_harness.py`, replace the first three lines of `check`:

```python fragment
def check(skill_dir: str) -> list:
    name = skill_name(skill_dir)
    marker = os.path.join(os.path.expanduser("~"), ".config", "opencode", "skills", name, ".oc-major")
```

with:

```python fragment
def check(skill_dir: str, home: str = "") -> list:
    name = skill_name(skill_dir)
    root = os.path.join(home or os.path.expanduser("~"), ".config", "opencode")
    marker = os.path.join(root, "skills", name, ".oc-major")
```

In `main`, directly after `p.add_argument("skill_dirs", nargs="+")`, add:

```python fragment
    p.add_argument("--home", default="", help="home dir holding .config/opencode (default ~)")
```

and in the `if a.cmd == "check":` block replace `for line in check(skill_dir):` with:

```python fragment
            for line in check(skill_dir, a.home):
```

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_run.py'`
Expected: PASS, last line `OK`

- [ ] **Step 25: Vendor the harness into every skill**

Run: `sh _shared/sync.sh && for d in brainstorming-glm dev-team-glm doc-generator-glm requirements-code-audit-glm systematic-debugging-glm writing-plans-glm; do cmp _shared/oc_harness.py "$d/scripts/oc_harness.py"; done`
Expected: no output from the `cmp` loop (all six copies byte-identical)

- [ ] **Step 26: Run the full unit suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: PASS, last line `OK`

- [ ] **Step 27: Run the dev-team selftest**

Run: `env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh`
Expected: `passed=` 324 or more and `failed=` 5 or fewer (only the known macOS failures: GNU `sed -i`, 4x `/private/var` resolve, one bash 3.2 word-split)

- [ ] **Step 28: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add glm-skills/_shared/oc_harness.py glm-skills/brainstorming-glm/scripts/oc_harness.py glm-skills/dev-team-glm/scripts/oc_harness.py glm-skills/doc-generator-glm/scripts/oc_harness.py glm-skills/requirements-code-audit-glm/scripts/oc_harness.py glm-skills/systematic-debugging-glm/scripts/oc_harness.py glm-skills/writing-plans-glm/scripts/oc_harness.py glm-skills/_shared/tests/test_oc_run.py
git commit -m "fix(shared): brief on stdin, error-event throttles, per-role stall, pgid lifecycle, result subcommand, check --home"
```

---

### T05: Agent rendering and config snippet for v1/v2 [P]

**Depends:** —

**Runs after:** T04 (same files)

**Interfaces:**
- Produces: `def config_snippet(major: int, deny: list) -> str`; `variants`; `reasoningEffort`; `glm-5.3`; `glm-5.3-flash`; `zai-coding-plan`; `web-search-prime`; `def render_agent(text: str, major: int) -> str`; `execute: deny`; `websearch`; `hidden`

**Files:**
- Modify: `glm-skills/_shared/oc_harness.py`
- Modify: `glm-skills/brainstorming-glm/scripts/oc_harness.py`
- Modify: `glm-skills/dev-team-glm/scripts/oc_harness.py`
- Modify: `glm-skills/doc-generator-glm/scripts/oc_harness.py`
- Modify: `glm-skills/requirements-code-audit-glm/scripts/oc_harness.py`
- Modify: `glm-skills/systematic-debugging-glm/scripts/oc_harness.py`
- Modify: `glm-skills/writing-plans-glm/scripts/oc_harness.py`
- Test: `glm-skills/_shared/tests/test_oc_render.py`

All commands run from `glm-skills/` (`cd glm-skills`). An earlier task edits `_shared/oc_harness.py` before this one, so find the edit points by the code shown below, not by line numbers. Edit only `_shared/oc_harness.py` by hand. The six vendored copies are refreshed by `sh _shared/sync.sh` in Step 9.

- [ ] **Step 1: Write the failing render test (v2 `execute: deny` and explicit `websearch`)**

In `_shared/tests/test_oc_render.py`, add this method to `class TestOcHarnessRender`, directly after `test_render_agent_v2_permission_matches_v1_nested_map_shape`:

```python
    def test_render_agent_v2_denies_execute_and_sets_websearch(self):
        text = (
            "---\n"
            "description: Web agent\n"
            "model: flash\n"
            "effort: high\n"
            "access: read\n"
            "bash: false\n"
            "web: true\n"
            "---\n"
            "Agent prompt body.\n"
        )
        v2 = oc_harness.render_agent(text, 2)
        perm = v2.split("permission:\n", 1)[1].split("\n---", 1)[0]
        self.assertIn("  execute: deny", perm)
        self.assertIn("  websearch: allow", perm)
        self.assertIn("  webfetch: allow", perm)
        self.assertIn("hidden: true", v2)
        v2_no_web = oc_harness.render_agent(text.replace("web: true", "web: false"), 2)
        self.assertIn("  websearch: deny", v2_no_web)
        self.assertIn("  execute: deny", v2_no_web)
        v1 = oc_harness.render_agent(text, 1)
        self.assertNotIn("execute:", v1)
        self.assertNotIn("websearch:", v1)
        self.assertIn("hidden: true", v1)
```

- [ ] **Step 2: Run the render test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_render.py' -k test_render_agent_v2_denies_execute_and_sets_websearch`
Expected: FAIL with "AssertionError: '  execute: deny' not found in"

- [ ] **Step 3: Emit `execute: deny` and `websearch` in the v2 permission map**

In `_shared/oc_harness.py`, inside `def render_agent(text: str, major: int) -> str` (signature unchanged), in the `else:` (v2) branch, find this comment line:

```python fragment
        # v2 applies the agent's variant when the `subagent` tool dispatches it; with no variant GLM
```

Insert these lines directly above it, at the same indent (they follow the v2 `if write_paths: lines.append("  task: deny")` block, so they stay inside the `permission:` map):

```python fragment
        # v2 gates websearch separately from webfetch; an explicit value keeps a headless lane from
        # opening the interactive provider form. `execute` is v2's code-mode tool, which would run
        # code outside the `bash` permission, so it is always denied.
        lines.append("  websearch: {}".format(web_perm))
        lines.append("  execute: deny")
```

Leave `lines.append("hidden: true")` unchanged, and leave the v1 branch unchanged: v1.18 has no `execute` or `websearch` tool.

- [ ] **Step 4: Run the render test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_render.py' -k test_render_agent`
Expected: PASS (all `test_render_agent*` tests, `OK`)

- [ ] **Step 5: Write the failing snippet tests (variants and websearch note)**

In `_shared/tests/test_oc_render.py`, add this module-level helper directly below `import oc_harness`:

```python
def _snippet_json(snippet):
    """The snippet is JSONC: `//` note lines first, then one JSON object."""
    return json.loads("\n".join(ln for ln in snippet.splitlines() if not ln.lstrip().startswith("//")))
```

Replace the whole existing `test_config_snippet_contains_provider_and_deny_list` method with this version, which parses through the helper:

```python
    def test_config_snippet_contains_provider_and_deny_list(self):
        snippet = oc_harness.config_snippet(1, ["systematic-debugging", "writing-plans"])
        data = _snippet_json(snippet)
        self.assertIn("zai-coding-plan", data["provider"])
        self.assertEqual(data["permission"]["skill"]["systematic-debugging"], "deny")
        self.assertEqual(data["permission"]["skill"]["writing-plans"], "deny")
        self.assertIn("web-search-prime", data["mcp"])
        self.assertNotIn("permission", _snippet_json(oc_harness.config_snippet(1, [])))
```

Then add these two methods directly after it:

```python
    def test_config_snippet_defines_effort_variants_for_both_models(self):
        expected = {
            "low": {"reasoningEffort": "low"},
            "high": {"reasoningEffort": "high"},
            "max": {"reasoningEffort": "max"},
        }
        for major in (1, 2):
            data = _snippet_json(oc_harness.config_snippet(major, []))
            models = data["provider"]["zai-coding-plan"]["models"]
            self.assertEqual(sorted(models), ["glm-5.3", "glm-5.3-flash"])
            for model_id in ("glm-5.3", "glm-5.3-flash"):
                self.assertEqual(models[model_id]["variants"], expected)

    def test_config_snippet_carries_websearch_note_and_mcp_option(self):
        for major in (1, 2):
            snippet = oc_harness.config_snippet(major, ["writing-plans"])
            notes = [ln for ln in snippet.splitlines() if ln.startswith("//")]
            self.assertTrue(notes)
            self.assertTrue(snippet.startswith("//"))
            joined = "\n".join(notes)
            self.assertIn("websearch", joined)
            self.assertIn("web-search-prime", joined)
            data = _snippet_json(snippet)
            server = data["mcp"]["web-search-prime"]
            self.assertEqual(server["type"], "remote")
            self.assertEqual(server["url"], "https://api.z.ai/api/mcp/web_search_prime/mcp")
            self.assertEqual(server["headers"], {"Authorization": "Bearer {env:ZAI_API_KEY}"})
```

- [ ] **Step 6: Run the snippet tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_render.py' -k test_config_snippet`
Expected: FAIL with "KeyError: 'variants'" in `test_config_snippet_defines_effort_variants_for_both_models` and "AssertionError: [] is not true" in `test_config_snippet_carries_websearch_note_and_mcp_option`

- [ ] **Step 7: Rewrite `config_snippet` with variants and the websearch note**

In `_shared/oc_harness.py`, replace the whole `def config_snippet(major: int, deny: list) -> str:` function (from its `def` line down to its `return json.dumps(config, indent=2)` line) with:

```python
WEBSEARCH_NOTE = (
    "websearch: OpenCode v2 needs a websearch provider. Without one, a headless lane that calls",
    "websearch opens an interactive form and times out. Option: keep the web-search-prime MCP",
    "server below (it reads ZAI_API_KEY), or render agents with web: false.",
    "variants: low/high/max set reasoningEffort, so `--model zai-coding-plan/glm-5.3#max` resolves.",
)


def config_snippet(major: int, deny: list) -> str:
    # Verified against the installed opencode v2.0.16 binary: `permission` is `PermissionConfig`, the same nested-map shape ({"skill": {"<name>": "deny"}}) in both major 1 and major 2.
    # v2 `#max` fails with "Variant unavailable" unless the provider model defines `variants.max`.
    # The result is JSONC (OpenCode parses opencode.json as JSONC): `//` note lines, then the object.
    variants = {effort: {"reasoningEffort": effort} for effort in EFFORTS}
    config = {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            PROVIDER: {
                "models": {
                    MODELS["pro"]: {"variants": dict(variants)},
                    MODELS["flash"]: {"variants": dict(variants)},
                }
            }
        },
        "mcp": {
            "web-search-prime": {
                "type": "remote",
                "url": "https://api.z.ai/api/mcp/web_search_prime/mcp",
                "headers": {"Authorization": "Bearer {env:ZAI_API_KEY}"},
            }
        },
    }
    if deny:
        config["permission"] = {"skill": {pattern: "deny" for pattern in deny}}
    notes = ["// " + line for line in WEBSEARCH_NOTE]
    return "\n".join(notes) + "\n" + json.dumps(config, indent=2)
```

`EFFORTS` is the existing module constant `("low", "high", "max")`.

- [ ] **Step 8: Run the whole render module to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_render.py'`
Expected: PASS (`OK`, no failures)

- [ ] **Step 9: Vendor the change and verify the copies are byte-identical**

Run: `sh _shared/sync.sh && for d in brainstorming-glm dev-team-glm doc-generator-glm requirements-code-audit-glm systematic-debugging-glm writing-plans-glm; do cmp _shared/oc_harness.py "$d/scripts/oc_harness.py" || echo "DIFF $d"; done`
Expected: no `DIFF` line and no `cmp` output

- [ ] **Step 10: Run the full unit suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: PASS, ending in `OK` (no new failures versus the run before this task)

- [ ] **Step 11: Commit**

```bash
git add glm-skills/_shared/oc_harness.py glm-skills/brainstorming-glm/scripts/oc_harness.py glm-skills/dev-team-glm/scripts/oc_harness.py glm-skills/doc-generator-glm/scripts/oc_harness.py glm-skills/requirements-code-audit-glm/scripts/oc_harness.py glm-skills/systematic-debugging-glm/scripts/oc_harness.py glm-skills/writing-plans-glm/scripts/oc_harness.py glm-skills/_shared/tests/test_oc_render.py
git commit -m "feat(shared): v2 agents deny execute and set websearch; snippet defines effort variants and websearch note"
```

---

### T06: zai_client key discovery [P]

**Depends:** —

**Interfaces:**
- Produces: `def find_key(extra_env: tuple = ()) -> tuple`; `ANTHROPIC_API_KEY`; `def _opencode_db_key(db_path: str) -> str`

**Files:**
- Modify: `glm-skills/_shared/zai_client.py:51-128`
- Modify: `glm-skills/requirements-code-audit-glm/scripts/zai_client.py`
- Modify: `glm-skills/systematic-debugging-glm/scripts/zai_client.py`
- Modify: `glm-skills/writing-plans-glm/scripts/zai_client.py`
- Test: `glm-skills/_shared/tests/test_zai_client.py`

All commands run from `glm-skills/` (`cd glm-skills`). Only `_shared/zai_client.py` is edited by hand; the three `scripts/zai_client.py` copies are overwritten from it in Step 9 and must end byte-identical.

- [ ] **Step 1: Write the failing test (ANTHROPIC_API_KEY is never a Z.ai key)**

In `_shared/tests/test_zai_client.py`, insert this block immediately above the line `class TestGate(unittest.TestCase):`. It adds a shared temp-HOME base class plus sqlite helpers that Step 5 also uses.

```python
import sqlite3  # noqa: E402

Z = "z" * 20
O = "o" * 20
AUTH_DDL = "CREATE TABLE auth (provider_id TEXT PRIMARY KEY, data TEXT)"
DB_REL = ".local/share/opencode/opencode.db"


def make_db(path, script):
    """Write a sqlite file from (sql, params) pairs; each test owns its schema."""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    con = sqlite3.connect(path)
    try:
        for sql, params in script:
            con.execute(sql, params)
        con.commit()
    finally:
        con.close()
    return path


def auth_rows(*pairs):
    """An `auth` table with one JSON credential row per (provider id, entry)."""
    script = [(AUTH_DDL, ())]
    for pid, entry in pairs:
        script.append(("INSERT INTO auth VALUES (?, ?)", (pid, json.dumps(entry))))
    return script


class _HomeCase(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.cwd = tempfile.mkdtemp()
        self.old = os.getcwd()
        os.chdir(self.cwd)
        self.env = mock.patch.dict(os.environ, {"HOME": self.home}, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        os.chdir(self.old)
        shutil.rmtree(self.home)
        shutil.rmtree(self.cwd)

    def put(self, rel, obj):
        p = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f)
        return p

    def db(self, script, rel=DB_REL):
        return make_db(os.path.join(self.home, rel), script)


class TestNoAnthropicKey(_HomeCase):
    def test_env_anthropic_api_key_never_used(self):
        os.environ["ANTHROPIC_API_KEY"] = "a" * 20
        self.assertEqual(zai_client.find_key(), (None, None))

    def test_extra_env_cannot_reintroduce_it(self):
        os.environ["ANTHROPIC_API_KEY"] = "a" * 20
        self.assertEqual(zai_client.find_key(("ANTHROPIC_API_KEY",)), (None, None))

    def test_settings_field_never_used(self):
        self.put(".claude/settings.json", {"env": {"ANTHROPIC_API_KEY": "a" * 20}})
        self.assertEqual(zai_client.find_key(), (None, None))

    def test_does_not_shadow_opencode_auth(self):
        os.environ["ANTHROPIC_API_KEY"] = "a" * 20
        auth = self.put(".local/share/opencode/auth.json",
                        {"zai-coding-plan": {"type": "api", "key": Z}})
        self.assertEqual(zai_client.find_key(), (Z, auth))

    def test_auth_token_still_used(self):
        os.environ["ANTHROPIC_API_KEY"] = "a" * 20
        os.environ["ANTHROPIC_AUTH_TOKEN"] = "t" * 20
        self.assertEqual(zai_client.find_key(), ("t" * 20, "env:ANTHROPIC_AUTH_TOKEN"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_zai_client.py' -k TestNoAnthropicKey`
Expected: FAIL with `FAILED (failures=4)`; e.g. `AssertionError: Tuples differ: ('aaaaaaaaaaaaaaaaaaaa', 'env:ANTHROPIC_API_KEY') != (None, None)`. Only `test_auth_token_still_used` passes.

- [ ] **Step 3: Write minimal implementation**

In `_shared/zai_client.py`, replace the `KEY_ENV = (...)` and `KEY_FIELDS = (...)` assignments (lines 51-54, directly above `KEY_FILES`) with (`NEVER_ENV` names a variable that is never read: that key is never a Z.ai key and only earns a 401):

```python
KEY_ENV = ("ZAI_API_KEY", "Z_AI_API_KEY", "GLM_API_KEY", "ZHIPUAI_API_KEY",
           "ANTHROPIC_AUTH_TOKEN")
NEVER_ENV = ("ANTHROPIC_API_KEY",)
KEY_FIELDS = ("ZAI_API_KEY", "GLM_API_KEY", "ANTHROPIC_AUTH_TOKEN",
              "apiKey", "api_key", "key")
```

Then replace the whole `def find_key(...)` function with:

```python
def find_key(extra_env: tuple = ()) -> tuple:
    """Return (key, source) or (None, None). Never returns ANTHROPIC_API_KEY."""
    for name in tuple(extra_env) + KEY_ENV:
        if name in NEVER_ENV:
            continue
        v = (os.environ.get(name) or "").strip()
        if v:
            return v, "env:" + name
    for p in KEY_FILES:
        path = os.path.expanduser(p) if p.startswith("~") else os.path.join(os.getcwd(), p[2:])
        try:
            with open(path, encoding="utf-8") as f:
                obj = json.load(f)
        except (OSError, ValueError):
            continue
        got = _opencode_key(obj) if "opencode" in p else _walk_for_key(obj)
        if got:
            return got, path
    return None, None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_zai_client.py' -k TestNoAnthropicKey`
Expected: PASS (`Ran 5 tests` ... `OK`)

- [ ] **Step 5: Write the failing test (read-only opencode.db lookup)**

In `_shared/tests/test_zai_client.py`, insert this class immediately below the `TestNoAnthropicKey` class (still above `class TestGate(unittest.TestCase):`):

```python
class TestOpencodeDbKey(_HomeCase):
    def test_row_per_provider(self):
        p = self.db(auth_rows(("openai", {"type": "api", "key": O}),
                              ("zai-coding-plan", {"type": "api", "key": Z})))
        self.assertEqual(zai_client._opencode_db_key(p), Z)

    def test_coding_plan_wins_over_zai(self):
        p = self.db(auth_rows(("zai", {"type": "api", "key": "y" * 20}),
                              ("zai-coding-plan", {"type": "api", "key": Z})))
        self.assertEqual(zai_client._opencode_db_key(p), Z)

    def test_plain_secret_column(self):
        p = self.db([("CREATE TABLE credential (provider TEXT, api_key TEXT)", ()),
                     ("INSERT INTO credential VALUES (?, ?)", ("openrouter", O)),
                     ("INSERT INTO credential VALUES (?, ?)", ("zai", Z))])
        self.assertEqual(zai_client._opencode_db_key(p), Z)

    def test_auth_json_blob_in_kv_table(self):
        blob = {"openai": {"type": "api", "key": O}, "zai": {"type": "api", "key": Z}}
        p = self.db([("CREATE TABLE kv (key TEXT PRIMARY KEY, value BLOB)", ()),
                     ("INSERT INTO kv VALUES (?, ?)",
                      ("auth", json.dumps(blob).encode("utf-8")))])
        self.assertEqual(zai_client._opencode_db_key(p), Z)

    def test_other_providers_only(self):
        p = self.db(auth_rows(("openai", {"type": "api", "key": O}),
                              ("zhipuai", {"type": "api", "key": Z}),
                              ("openrouter", {"type": "api", "key": "a" * 20})))
        self.assertEqual(zai_client._opencode_db_key(p), "")

    def test_templated_value_rejected(self):
        p = self.db(auth_rows(("zai-coding-plan", {"type": "api", "key": "{env:ZAI_API_KEY}"})))
        self.assertEqual(zai_client._opencode_db_key(p), "")

    def test_unrelated_table_ignored(self):
        p = self.db([("CREATE TABLE session (id TEXT, title TEXT)", ()),
                     ("INSERT INTO session VALUES (?, ?)", ("zai", Z))])
        self.assertEqual(zai_client._opencode_db_key(p), "")

    def test_missing_file_not_created(self):
        p = os.path.join(self.home, "nope", "opencode.db")
        self.assertEqual(zai_client._opencode_db_key(p), "")
        self.assertFalse(os.path.exists(os.path.dirname(p)))

    def test_not_a_database(self):
        p = os.path.join(self.home, DB_REL)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(b"not a sqlite file " * 64)
        self.assertEqual(zai_client._opencode_db_key(p), "")

    def test_never_writes(self):
        p = self.db(auth_rows(("zai-coding-plan", {"type": "api", "key": Z})))
        with open(p, "rb") as f:
            before = f.read()
        mtime = os.stat(p).st_mtime_ns
        self.assertEqual(zai_client._opencode_db_key(p), Z)
        with open(p, "rb") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(os.stat(p).st_mtime_ns, mtime)
        self.assertEqual(os.listdir(os.path.dirname(p)), ["opencode.db"])

    def test_find_key_reads_db(self):
        p = self.db(auth_rows(("zai-coding-plan", {"type": "api", "key": Z})))
        self.assertEqual(zai_client.find_key(), (Z, p))

    def test_auth_json_beats_db(self):
        self.db(auth_rows(("zai-coding-plan", {"type": "api", "key": Z})))
        auth = self.put(".local/share/opencode/auth.json",
                        {"zai-coding-plan": {"type": "api", "key": "j" * 20}})
        self.assertEqual(zai_client.find_key(), ("j" * 20, auth))

    def test_db_beats_claude_settings(self):
        p = self.db(auth_rows(("zai-coding-plan", {"type": "api", "key": Z})))
        self.put(".claude/settings.json", {"env": {"ANTHROPIC_AUTH_TOKEN": "c" * 20}})
        self.assertEqual(zai_client.find_key(), (Z, p))

    def test_broken_db_falls_through(self):
        p = os.path.join(self.home, DB_REL)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(b"garbage" * 200)
        settings = self.put(".claude/settings.json", {"env": {"ANTHROPIC_AUTH_TOKEN": "c" * 20}})
        self.assertEqual(zai_client.find_key(), ("c" * 20, settings))
```

- [ ] **Step 6: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_zai_client.py' -k TestOpencodeDbKey`
Expected: FAIL with `FAILED (failures=2, errors=10)`; the errors read `AttributeError: module 'zai_client' has no attribute '_opencode_db_key'`, the failures are `test_find_key_reads_db` and `test_db_beats_claude_settings`.

- [ ] **Step 7: Write minimal implementation**

In `_shared/zai_client.py`, replace the `KEY_FILES = (...)` assignment with this one (the v2 database sits after the v1 `auth.json` files and before every non-OpenCode file):

```python
KEY_FILES = ("~/.local/share/opencode/auth.json", "~/.config/opencode/auth.json",
             "~/.local/share/opencode/opencode.db",
             "~/.config/opencode/opencode.json", "./opencode.json",
             "~/.claude/settings.json", "~/.claude/settings.local.json",
             "~/.zcode/settings.json", "~/.zcode/auth.json", "~/.zcode/config.json")
```

Insert these constants and helpers directly below the `_opencode_key` function (above `def find_key`). `DB_PROVIDERS` are the only ids read from the v2 database; a table is searched only if its name or a column name carries one of `DB_TABLE_HINTS`; a bare string cell counts as a secret only in a column whose name carries one of `DB_SECRET_COLS`:

```python
DB_PROVIDERS = ("zai-coding-plan", "zai")
DB_TABLE_HINTS = ("auth", "cred", "provider", "secret", "account", "key")
DB_SECRET_COLS = ("key", "token", "secret", "cred")
DB_ROW_LIMIT = 1000


def _as_text(v):
    if isinstance(v, bytes):
        try:
            return v.decode("utf-8")
        except UnicodeDecodeError:
            return None
    return v if isinstance(v, str) else None


def _json_obj(text):
    t = (text or "").strip()
    if not t.startswith("{"):
        return None
    try:
        obj = json.loads(t)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def _entry_secret(entry):
    if isinstance(entry, dict):
        for f in ("key", "apiKey", "api_key"):
            if _valid_key(entry.get(f)):
                return entry.get(f)
    return None


def _db_row_keys(cols, row):
    """{provider id: key} from one row, for the ids in DB_PROVIDERS only."""
    texts = [(str(c).lower(), _as_text(v)) for c, v in zip(cols, row)]
    owner = next((t for _, t in texts if t in DB_PROVIDERS), None)
    found = {}
    for col, t in texts:
        if t is None or t == owner:
            continue
        obj = _json_obj(t)
        if obj is not None:
            if owner:
                got = _entry_secret(obj)
                if got:
                    found.setdefault(owner, got)
            for pid in DB_PROVIDERS:
                got = _entry_secret(obj.get(pid))
                if got:
                    found.setdefault(pid, got)
        elif owner and any(h in col for h in DB_SECRET_COLS) and _valid_key(t):
            found.setdefault(owner, t)
    return found


def _opencode_db_key(db_path: str) -> str:
    """Z.ai key from an OpenCode v2 opencode.db, or "".

    Opens the file read-only (file:...?mode=ro), finds credential tables by
    introspecting the schema and reads only zai-coding-plan / zai entries.
    Any error, missing table or unexpected shape returns "". Never writes.
    """
    try:
        import sqlite3
    except ImportError:
        return ""
    uri = "file:%s?mode=ro" % urllib.parse.quote(os.path.abspath(db_path))
    try:
        con = sqlite3.connect(uri, uri=True, timeout=1)
    except Exception:
        return ""
    found = {}
    try:
        names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for name in names:
            q = '"%s"' % str(name).replace('"', '""')
            cols = [r[1] for r in con.execute("PRAGMA table_info(%s)" % q)]
            hay = " ".join([str(name)] + [str(c) for c in cols]).lower()
            if not any(h in hay for h in DB_TABLE_HINTS):
                continue
            for row in con.execute("SELECT * FROM %s LIMIT %d" % (q, DB_ROW_LIMIT)):
                for pid, key in _db_row_keys(cols, row).items():
                    found.setdefault(pid, key)
    except Exception:
        return ""
    finally:
        con.close()
    for pid in DB_PROVIDERS:
        if pid in found:
            return found[pid]
    return ""
```

Replace the whole `def find_key(...)` function (the Step 3 version) with:

```python
def find_key(extra_env: tuple = ()) -> tuple:
    """Return (key, source) or (None, None). Never returns ANTHROPIC_API_KEY."""
    for name in tuple(extra_env) + KEY_ENV:
        if name in NEVER_ENV:
            continue
        v = (os.environ.get(name) or "").strip()
        if v:
            return v, "env:" + name
    for p in KEY_FILES:
        path = os.path.expanduser(p) if p.startswith("~") else os.path.join(os.getcwd(), p[2:])
        if path.endswith(".db"):
            got = _opencode_db_key(path)
            if got:
                return got, path
            continue
        try:
            with open(path, encoding="utf-8") as f:
                obj = json.load(f)
        except (OSError, ValueError):
            continue
        got = _opencode_key(obj) if "opencode" in p else _walk_for_key(obj)
        if got:
            return got, path
    return None, None
```

- [ ] **Step 8: Run test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_zai_client.py'`
Expected: PASS (`OK`; every test in the file, including the 5 `TestNoAnthropicKey` and 14 `TestOpencodeDbKey` tests, is green)

- [ ] **Step 9: Vendor the source into the three copies and verify they are identical**

These are the `zai_client.py` copies that `sh _shared/sync.sh` makes; copying them directly keeps this step correct whether or not the sync.sh path fix has landed yet.

```bash
cp _shared/zai_client.py requirements-code-audit-glm/scripts/zai_client.py
cp _shared/zai_client.py systematic-debugging-glm/scripts/zai_client.py
cp _shared/zai_client.py writing-plans-glm/scripts/zai_client.py
```

Run: `for d in requirements-code-audit-glm systematic-debugging-glm writing-plans-glm; do cmp _shared/zai_client.py "$d/scripts/zai_client.py" && echo "same $d"; done`
Expected: three lines `same requirements-code-audit-glm`, `same systematic-debugging-glm`, `same writing-plans-glm` and no `differ` output

- [ ] **Step 10: Run the full unit suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no failure or error from `test_zai_client.py`; the only red tests, if any, are the pre-existing stale fixture-path failures in `test_devteam_plugins.py` / `test_vendored.py` (baseline 11), and none are new.

- [ ] **Step 11: Commit**

```bash
cd ..
git add glm-skills/_shared/zai_client.py glm-skills/requirements-code-audit-glm/scripts/zai_client.py glm-skills/systematic-debugging-glm/scripts/zai_client.py glm-skills/writing-plans-glm/scripts/zai_client.py glm-skills/_shared/tests/test_zai_client.py
git commit -m "fix(shared): never send ANTHROPIC_API_KEY to Z.ai; read OpenCode v2 key from opencode.db read-only"
```

---

### T07: guard.py oc-mode input hardening [P]

**Depends:** —

**Files:**
- Modify: `glm-skills/dev-team-glm/scripts/guard.py:163-790`
- Test: `glm-skills/_shared/tests/test_guard_oc.py`

This task hardens the `guard.py oc` bridge against the inputs OpenCode really sends. It covers spec rows DG1 (args as a JSON string), DG2 (indented patch headers), DG3 (edit/write with no path), DG6 (symlink `abspath` vs `resolve()` mismatch), DG7 (`batch` / `question` / `execute` in lane mode) and DG11 (deny message names the pinned forms). The guard stays fail-open for internal errors (`main()` is unchanged). The new denies apply only when a role is set, which is lane mode. All commands run from `glm-skills/` (`cd glm-skills` first). Every new test method goes inside `class GuardOcTest`, directly after `test_guard_oc_function_no_role` and before `if __name__ == "__main__":`.

- [ ] **Step 1: Write the failing tests for args parsing and lane-mode tool denies (DG1, DG7)**

Add these methods to `GuardOcTest` in `_shared/tests/test_guard_oc.py`:

```python fragment
    def test_args_json_string_is_parsed(self):
        # v2 `input.repair` can hand the args over as a JSON string instead of an object
        rc, out = self.oc("write", json.dumps({"filePath": "docs/x.md", "content": "x"}))
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("`docs/x.md` is outside your slice footprint", reason)
        rc, out = self.oc("shell", json.dumps({"command": "git push origin main"}))
        self.assertEqual(decision(out)[0], "deny")
        rc, out = self.oc("edit", json.dumps({"filePath": "src/a.py", "oldString": "a", "newString": "b"}))
        self.assertEqual(decision(out), ("allow", "dev-team: `src/a.py` is inside the slice footprint"))

    def test_unparseable_args_deny_in_lane_mode(self):
        for args in ("{not json", "[1, 2]", ["src/a.py"], 7):
            with self.subTest(args=args):
                rc, out = self.oc("write", args)
                self.assertEqual(rc, 0)
                verdict, reason = decision(out)
                self.assertEqual(verdict, "deny")
                self.assertIn("could not be parsed", reason)

    def test_unparseable_args_without_role_stay_silent(self):
        rc, out = self.oc("write", "{not json", role="")
        self.assertEqual((rc, out), (0, ""))

    def test_non_string_shell_fields_deny(self):
        for args in ({"command": 5}, {"command": "git status", "workdir": 5}):
            with self.subTest(args=args):
                rc, out = self.oc("shell", args)
                self.assertEqual(rc, 0)
                verdict, reason = decision(out)
                self.assertEqual(verdict, "deny")
                self.assertIn("needs a string `command`", reason)

    def test_batch_and_question_denied_in_lane_mode(self):
        for tool in ("batch", "question"):
            for role in ("programmer", "code-reviewer"):
                with self.subTest(tool=tool, role=role):
                    rc, out = self.oc(tool, {}, role=role)
                    self.assertEqual(rc, 0)
                    verdict, reason = decision(out)
                    self.assertEqual(verdict, "deny")
                    self.assertIn(f"`{tool}` is disabled in dev-team lanes", reason)
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_oc.py' -k test_args_json_string_is_parsed -k test_unparseable_args -k test_non_string_shell_fields_deny -k test_batch_and_question_denied_in_lane_mode`
Expected: FAIL. Each failure reads `AssertionError: '' != 'deny'`, because the guard currently crashes on `.get` and fails open to a silent allow. The summary line is `FAILED (failures=11)`. `test_unparseable_args_without_role_stay_silent` already passes.

- [ ] **Step 3: Parse the args and deny the lane-mode tools**

In `dev-team-glm/scripts/guard.py`, insert these definitions directly after the `oc_capture` function and before `def guard_oc(inp):`:

```python
OC_LANE_DENY_TOOLS = {
    "execute": "OpenCode Code Mode (`execute`) is disabled in dev-team lanes so every tool call "
               "can be checked on its own. Call the tools directly.",
    "batch": "`batch` is disabled in dev-team lanes so every tool call can be checked on its own. "
             "Call the tools one at a time.",
    "question": "`question` is disabled in dev-team lanes: a headless lane has nobody to answer it, so the "
                "run would block. Decide from the brief, or end with `## Status: Blocked` and the question.",
}


def oc_args(raw):
    """The tool args as a dict, or None when they cannot be read. v2 may hand them over as a JSON
    string (`input.repair`); anything that is still not an object after decoding is unreadable."""
    if raw is None or raw == "":
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    return raw if isinstance(raw, dict) else None
```

In `guard_oc`, replace this block:

```python fragment
    tool = (inp.get("tool") or "").lower()
    args = inp.get("args") or {}
    prog = role == "programmer"
    cwd = inp.get("cwd") or os.getcwd()
    base = {"cwd": cwd, "agent_type": role}
    if tool == "execute":
        deny("dev-team: OpenCode Code Mode (`execute`) is disabled in dev-team lanes so every tool call "
             "can be checked on its own. Call the tools directly.")
```

with:

```python fragment
    tool = (inp.get("tool") or "").lower()
    args = oc_args(inp.get("args"))
    if args is None:
        deny(f"dev-team: the `{tool}` arguments could not be parsed as a JSON object, so the call cannot "
             "be checked. Retry it with well-formed arguments.")
    prog = role == "programmer"
    cwd = inp.get("cwd") or os.getcwd()
    base = {"cwd": cwd, "agent_type": role}
    if tool in OC_LANE_DENY_TOOLS:
        deny("dev-team: " + OC_LANE_DENY_TOOLS[tool])
```

In the same function, replace the start of the shell branch:

```python fragment
    if tool in ("bash", "shell"):
        workdir = args.get("workdir")
        if workdir:
```

with:

```python fragment
    if tool in ("bash", "shell"):
        workdir = args.get("workdir")
        command = args.get("command")
        if not isinstance(command, str) or (workdir is not None and not isinstance(workdir, str)):
            deny(f"dev-team: `{tool}` needs a string `command` (and a string `workdir` when one is given); "
                 "these arguments cannot be checked.")
        if workdir:
```

Then, a few lines below, replace `tool_input={"command": args.get("command") or ""}` with `tool_input={"command": command}`.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_oc.py'`
Expected: PASS. The output ends with `OK` and shows no failures (this includes the existing `test_code_mode_execute_denied_for_every_role` and `test_unknown_tool_is_silent_allow`).

- [ ] **Step 5: Write the failing tests for patch headers and missing paths (DG2, DG3)**

Add these methods to `GuardOcTest`:

```python fragment
    def test_indented_patch_header_is_checked(self):
        # v2 trims patch lines before applying them, so an indented header is live
        patch = ("*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n"
                 "  *** Add File: docs/b.md\n+hi\n*** End Patch\n")
        rc, out = self.oc("apply_patch", {"patchText": patch})
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("docs/b.md", reason)

    def test_indented_patch_header_denied_for_read_only_role(self):
        patch = "*** Begin Patch\n    *** Update File: src/a.py\n@@\n-x\n+y\n*** End Patch\n"
        rc, out = self.oc("patch", {"patchText": patch}, role="code-reviewer")
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("This role is read-only", reason)

    def test_headerless_patch_denied_for_every_role(self):
        for role in ("programmer", "code-reviewer"):
            with self.subTest(role=role):
                rc, out = self.oc("patch", {"patchText": "@@\n-x\n+y\n"}, role=role)
                self.assertEqual(rc, 0)
                verdict, reason = decision(out)
                self.assertEqual(verdict, "deny")
                self.assertIn("names no file", reason)

    def test_edit_without_path_denied_for_every_role(self):
        for tool, args in (("write", {"content": "x"}),
                           ("edit", {"oldString": "a", "newString": "b"}),
                           ("write", {"filePath": "", "content": "x"})):
            for role in ("programmer", "code-reviewer"):
                with self.subTest(tool=tool, args=args, role=role):
                    rc, out = self.oc(tool, args, role=role)
                    self.assertEqual(rc, 0)
                    verdict, reason = decision(out)
                    self.assertEqual(verdict, "deny")
                    self.assertIn("names no file", reason)

    def test_edit_ro_mode_without_path_denies(self):
        r = subprocess.run([sys.executable, str(GUARD), "edit-ro"],
                           input=json.dumps({"tool_input": {}, "cwd": str(self.wt),
                                             "agent_type": "code-reviewer"}),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)
        verdict, reason = decision(r.stdout)
        self.assertEqual(verdict, "deny")
        self.assertIn("names no file", reason)
```

- [ ] **Step 6: Run the new tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_oc.py' -k test_indented_patch_header -k test_headerless_patch_denied_for_every_role -k test_edit_without_path_denied_for_every_role -k test_edit_ro_mode_without_path_denies`
Expected: FAIL with `FAILED (failures=10)`. The programmer indented-header test fails with `AssertionError: 'allow' != 'deny'`. The read-only, headerless-reviewer and no-path cases fail with `AssertionError: '' != 'deny'` or with a `names no file` assertion (not found in the reason `` `` is outside any slice worktree``). The programmer headerless-patch subtest already passes.

- [ ] **Step 7: Check every stripped header and deny a write that names no file**

In `dev-team-glm/scripts/guard.py`, replace the `OC_PATCH_PATH` regex and `oc_patch_paths` function:

```python fragment
OC_PATCH_PATH = re.compile(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)$", re.M)


def oc_patch_paths(text):
    return [p.strip() for p in OC_PATCH_PATH.findall(text or "") if p.strip()]
```

with:

```python
OC_PATCH_PATH = re.compile(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to):\s*(.+)$")


def oc_patch_paths(text):
    """Every file a patch names. Each line is stripped first: v2 trims lines before it applies a
    patch, so an indented `*** Update File:` header is live and must be checked like any other."""
    if not isinstance(text, str):
        return []
    out_ = []
    for ln in text.splitlines():
        m = OC_PATCH_PATH.match(ln.strip())
        if m and m.group(1).strip():
            out_.append(m.group(1).strip())
    return out_
```

In `guard_oc`, replace:

```python fragment
    if tool in ("edit", "write", "multiedit"):
        paths = [args.get("filePath") or args.get("path") or ""]  # v1 filePath, v2 path
    elif tool in ("patch", "apply_patch"):
        paths = oc_patch_paths(args.get("patchText"))
        if prog and not paths:
            deny(f"`{tool}` names no file (no `*** Add/Update/Delete File:` header), so it cannot be checked "
                 "against your footprint. Rewrite it with a header naming each file it touches.")
    else:
        allow()
```

with:

```python fragment
    if tool in ("edit", "write", "multiedit"):
        p0 = args.get("filePath") or args.get("path") or ""  # v1 filePath, v2 path
        if not isinstance(p0, str) or not p0.strip():
            deny(f"`{tool}` names no file (no `filePath` / `path`), so it cannot be checked. "
                 "Retry it naming the file it writes.")
        paths = [p0]
    elif tool in ("patch", "apply_patch"):
        paths = oc_patch_paths(args.get("patchText"))
        if not paths:
            deny(f"`{tool}` names no file (no `*** Add/Update/Delete File:` header), so it cannot be checked "
                 "against your footprint. Rewrite it with a header naming each file it touches.")
    else:
        allow()
```

In `guard_edit_ro`, replace:

```python fragment
    path = tool_path(inp)
    if not path:
        allow()
    if not os.path.isabs(path):
        path = os.path.join(inp.get("cwd") or os.getcwd(), path)
```

with:

```python fragment
    path = tool_path(inp)
    if not path:
        deny("This role is read-only, and this write names no file, so it cannot be checked against the "
             "report / memory paths it may write. Report findings instead.")
    if not os.path.isabs(path):
        path = os.path.join(inp.get("cwd") or os.getcwd(), path)
```

- [ ] **Step 8: Run the test file to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_oc.py'`
Expected: PASS. The output ends with `OK`, and the existing patch tests (`test_programmer_patch_first_deny_wins`, `test_v2_edit_capable_tools_route_to_edit_checks`) still pass.

- [ ] **Step 9: Write the failing test for a symlinked worktree path (DG6)**

Add this method to `GuardOcTest`:

```python fragment
    def test_symlinked_cwd_edit_inside_footprint_allows(self):
        linkdir = Path(tempfile.mkdtemp())
        try:
            link = linkdir / "wt"
            link.symlink_to(self.wt)
            for fp in ("src/a.py", str(link / "src" / "a.py")):
                with self.subTest(filePath=fp):
                    rc, out = run_oc({"tool": "edit",
                                      "args": {"filePath": fp, "oldString": "a", "newString": "b"},
                                      "cwd": str(link), "role": "programmer"})
                    self.assertEqual(rc, 0)
                    self.assertEqual(decision(out),
                                     ("allow", "dev-team: `src/a.py` is inside the slice footprint"))
        finally:
            shutil.rmtree(linkdir, ignore_errors=True)
```

- [ ] **Step 10: Run the new test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_oc.py' -k test_symlinked_cwd_edit_inside_footprint_allows`
Expected: FAIL with `FAILED (failures=2)`. Each subtest shows a `('deny', '`../…/wt/src/a.py` is outside your slice footprint …')` tuple where the allow tuple was expected, because the path is `abspath`ed while the worktree is `resolve()`d.

- [ ] **Step 11: Resolve the edit path the same way as the worktree**

In `guard_edit`, replace:

```python fragment
    path = os.path.abspath(os.path.join(inp.get("cwd", ""), path)) if not os.path.isabs(path) else path
```

with:

```python fragment
    # find_slice_root() resolve()s the worktree, so resolve the path too: a symlinked cwd or a
    # /var -> /private/var alias must not turn an in-footprint edit into `../…` and deny it
    path = str(Path(path if os.path.isabs(path) else os.path.join(inp.get("cwd") or os.getcwd(), path)).resolve())
```

- [ ] **Step 12: Run the test file to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_oc.py'`
Expected: PASS. The output ends with `OK`.

- [ ] **Step 13: Write the failing tests for the pinned forms in the shell deny message (DG11)**

Add these methods to `GuardOcTest`:

```python fragment
    def test_unapproved_shell_deny_lists_pinned_forms(self):
        (self.wt / ".slice" / "allow").write_text("python3 -m pytest -q\nmake lint\n")
        rc, out = self.oc("shell", {"command": "curl example.com"})
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("Pinned forms from `.slice/allow`: `python3 -m pytest -q`, `make lint`.", reason)

    def test_unapproved_shell_deny_says_when_nothing_is_pinned(self):
        rc, out = self.oc("shell", {"command": "curl example.com"})
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("No commands are pinned for this lane (`.slice/allow` is empty).", reason)
```

- [ ] **Step 14: Run the new tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_oc.py' -k test_unapproved_shell_deny`
Expected: FAIL with `FAILED (failures=2)`. Each failure is an `AssertionError` saying the expected text is `not found in 'dev-team: OpenCode has no interactive fallback, so a bash command that isn't explicitly pre-approved is denied instead of silently allowed.'`.

- [ ] **Step 15: Add the pinned forms to the deny message**

In `dev-team-glm/scripts/guard.py`, insert this function directly after `oc_args`:

```python
def oc_pinned_hint(cwd, prog):
    """The command forms this lane may run without a prompt, for the unapproved-shell deny message:
    `.slice/allow` for a programmer, the plan's gate commands for a read-only role."""
    try:
        if prog:
            wt = find_slice_root(cwd)
            pinned = read_lines(wt / ".slice" / "allow") if wt else []
            src = "`.slice/allow`"
        else:
            pinned = plan_commands(find_state_root(cwd))
            src = "the plan's gate commands"
    except Exception:
        return ""
    forms = [p.strip() for p in pinned if p.strip()][:12]
    if not forms:
        return f" No commands are pinned for this lane ({src} is empty)."
    return f" Pinned forms from {src}: " + ", ".join(f"`{f}`" for f in forms) + "."
```

In the shell branch of `guard_oc`, replace:

```python fragment
        if not out.strip():
            deny("dev-team: OpenCode has no interactive fallback, so a bash command that isn't "
                 "explicitly pre-approved is denied instead of silently allowed.")
```

with:

```python fragment
        if not out.strip():
            deny("dev-team: OpenCode has no interactive fallback, so a bash command that isn't "
                 "explicitly pre-approved is denied instead of silently allowed."
                 + oc_pinned_hint(base["cwd"], prog))
```

- [ ] **Step 16: Run the test file to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_oc.py'`
Expected: PASS. The output ends with `OK`.

- [ ] **Step 17: Run the full unit suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no failure or error in any `test_guard_oc` or other guard test. The only failures allowed are the pre-existing stale-fixture-path ones that were already red before this task.

- [ ] **Step 18: Run the dev-team selftest**

Run: `env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh`
Expected: `passed=` is 324 or more and `failed=` is 5 or fewer. The only failures are the known macOS ones: GNU `sed -i`, 4× `/private/var` resolve, and a bash 3.2 word-split.

- [ ] **Step 19: Commit**

Run the commit from the git root (one level above `glm-skills/`).

```bash
cd "$(git rev-parse --show-toplevel)"
git add glm-skills/dev-team-glm/scripts/guard.py glm-skills/_shared/tests/test_guard_oc.py
git commit -m "fix(dev-team): harden guard.py oc input: JSON-string args, stripped patch headers, no-path deny, resolved paths, batch/question deny, pinned forms in deny"
```

---

### T08: guard.py read-only allow-list holes [P]

**Depends:** —

**Runs after:** T07 (same files)

**Files:**
- Modify: `glm-skills/dev-team-glm/scripts/guard.py`
- Test: `glm-skills/_shared/tests/test_guard_readonly.py`

This task covers spec rows DG4 (write/exec forms in the read-only allow-list), DG5 (rewriting formatters for read-only roles) and the `guard.py` half of DG14 (`devteam.py status` / `probe` for read-only roles). An earlier task has already edited `guard.py` (the `guard_oc` bridge). Anchor every edit below on the quoted code, not on line numbers. All commands run from `glm-skills/` (`cd glm-skills` first).

- [ ] **Step 1: Write the failing test for write/exec forms (DG4)**

Create `_shared/tests/test_guard_readonly.py`:

```python
"""guard.py read-only allow-list: write/exec forms (DG4), rewriting formatters (DG5), devteam status/probe (DG14)."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[2] / "dev-team-glm" / "scripts" / "guard.py"


def load_guard():
    spec = importlib.util.spec_from_file_location("devteam_guard_readonly", str(GUARD))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guard = load_guard()


def run_guard(mode, payload):
    r = subprocess.run([sys.executable, str(GUARD), mode], input=json.dumps(payload),
                       text=True, capture_output=True, timeout=30)
    return r.stdout


def decision(out):
    """'allow' / 'deny', or None for a silent exit (the normal permission flow)."""
    if not out.strip():
        return None
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"]


class GuardCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = self._tmp.name

    def bash_ro(self, cmd):
        return decision(run_guard("bash-ro", {"cwd": self.cwd, "agent_type": "reviewer",
                                              "tool_input": {"command": cmd}}))

    def oc_shell(self, cmd, role="reviewer"):
        return decision(run_guard("oc", {"tool": "shell", "args": {"command": cmd},
                                         "cwd": self.cwd, "role": role}))

    def preapproved(self, cmd, readonly=False):
        return guard.bash_allow_reason(cmd, None, footprint=[], pinned=[], readonly=readonly)


WRITE_EXEC_FORMS = [
    "git diff --output=/tmp/x.patch",
    "git diff --output /tmp/x.patch HEAD",
    "git log -p --output=log.txt",
    "git show --output=show.txt HEAD",
    "git grep --open-files-in-pager=vim foo",
    "git grep -Ovim foo",
    "rg --pre ./decompress.sh foo",
    "rg --pre=cat foo src",
    "uniq in.txt out.txt",
    "sed -n 's/a/b/w out.txt' in.txt",
    "sed 'w out.txt' in.txt",
    "sed '1e date' in.txt",
    "sed -e 's/a/b/e' in.txt",
    "sed -f prog.sed in.txt",
    "sort --compress-program=sh in.txt",
    "sort --compress-program sh in.txt",
    "cat in.txt | sed 'w out.txt'",
]

READ_ONLY_FORMS = [
    "git diff HEAD~1 -- src",
    "git log --oneline -5",
    "git show HEAD --stat",
    "git grep -n foo",
    "rg -n foo src",
    "sort -u in.txt",
    "uniq -c in.txt",
    "uniq -f 1 in.txt",
    "sed -n '1,5p' in.txt",
    "sed 's/we/us/g' in.txt",
    "cat in.txt | sort | uniq -c",
]


class ReadOnlyWriteExecFormsTest(GuardCase):
    def test_bash_ro_denies_write_and_exec_forms(self):
        bad = [c for c in WRITE_EXEC_FORMS if self.bash_ro(c) != "deny"]
        self.assertEqual(bad, [])

    def test_programmer_allow_list_does_not_preapprove_them(self):
        bad = [c for c in WRITE_EXEC_FORMS if self.preapproved(c) is not None]
        self.assertEqual(bad, [])

    def test_oc_bridge_denies_them(self):
        cmds = ["git diff --output=x.patch", "uniq in.txt out.txt", "rg --pre=cat foo"]
        bad = [c for c in cmds if self.oc_shell(c) != "deny"]
        self.assertEqual(bad, [])

    def test_read_only_forms_stay_allowed(self):
        bad = [c for c in READ_ONLY_FORMS if self.bash_ro(c) != "allow"]
        self.assertEqual(bad, [])
        bad = [c for c in READ_ONLY_FORMS if self.preapproved(c) is None]
        self.assertEqual(bad, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_readonly.py' -k ReadOnlyWriteExecFormsTest`
Expected: FAIL. The run ends with `FAILED (failures=3)`. The failures are `AssertionError: Lists differ` in `test_bash_ro_denies_write_and_exec_forms`, `test_programmer_allow_list_does_not_preapprove_them` and `test_oc_bridge_denies_them`, each listing the commands that are still allowed. `test_read_only_forms_stay_allowed` passes.

- [ ] **Step 3: Add the write/exec form detector to guard.py**

In `dev-team-glm/scripts/guard.py`, insert this block directly after the `def path_args(argv):` function and before `def segment_allowed(`:

```python
def _has(rest, *flags):
    """True when any argument is one of `flags` (a `--flag=value` form counts as `--flag`)."""
    return any(a.split("=", 1)[0] in flags for a in rest)


SED_WRITE_EXEC = re.compile(  # sed w/W FILE, e CMD, s///w FILE, s///e (a false match only costs the pre-approval)
    r"(?:^|[;{}\n/!,$0-9\s])\s*[wWe](?:\s|$|;|})"
    r"|s(.)(?:\\.|(?!\1).)*\1(?:\\.|(?!\1).)*\1[gpiImM0-9]*[we]")


def sed_scripts(argv):
    """The sed program texts of one sed argv, or None when a program comes from a file (`-f`)."""
    if "--sandbox" in argv:
        return []                # GNU sed rejects w/W/e/r in sandbox mode
    scripts, positional, i = [], [], 1
    while i < len(argv):
        a = argv[i]
        i += 1
        if a == "--":
            positional += argv[i:]
            break
        if a.startswith("--"):
            name, eq, val = a.partition("=")
            if name == "--file":
                return None
            if name == "--expression":
                if eq:
                    scripts.append(val)
                elif i < len(argv):
                    scripts.append(argv[i])
                    i += 1
            elif name == "--line-length" and not eq:
                i += 1
            continue
        if a.startswith("-") and len(a) > 1:
            for j, ch in enumerate(a[1:], start=1):
                if ch == "f":
                    return None
                if ch in ("e", "l"):
                    tail = a[j + 1:]
                    if ch == "e":
                        if tail:
                            scripts.append(tail)
                        elif i < len(argv):
                            scripts.append(argv[i])
                    if not tail and i < len(argv):
                        i += 1
                    break
            continue
        positional.append(a)
    if not scripts and positional:
        scripts.append(positional[0])
    return scripts


def write_exec_form(argv, readonly=False):
    """Why one argv writes a file or runs another program although its command looks read-only
    (`git diff --output`, `git grep -O`, `rg --pre`, `uniq IN OUT`, sed `w`/`e`,
    `sort --compress-program`), or None."""
    argv = strip_env_prefix(argv)
    if not argv:
        return None
    head, rest = os.path.basename(argv[0]), argv[1:]
    sub = rest[0] if rest else ""
    if head == "git":
        if sub in ("diff", "log", "show", "whatchanged") and _has(rest, "--output"):
            return f"`git {sub} --output` writes a file"
        if sub == "grep" and any(a.startswith("--op") or re.match(r"-[A-Za-z0-9]*O", a) for a in rest):
            return "`git grep --open-files-in-pager` / `-O` runs a program"
    if head == "rg" and _has(rest, "--pre"):
        return "`rg --pre` runs a preprocessor program on every file"
    if head == "sort" and any(a.startswith("--com") or a.startswith("--o") or re.match(r"-[A-Za-z]*o", a)
                              for a in rest):
        return "`sort --compress-program` / `-o` runs a program or writes a file"
    if head == "uniq":
        pos, i = [], 0
        while i < len(rest):
            a = rest[i]
            i += 1
            if a in ("-f", "-s", "-w"):
                i += 1
            elif a == "-" or not a.startswith("-"):
                pos.append(a)
        if len(pos) >= 2 and pos[1] != "-":
            return "`uniq INPUT OUTPUT` writes OUTPUT"
    if head == "sed":
        scripts = sed_scripts(argv)
        if scripts is None:
            return "`sed -f` runs a program file that cannot be checked here"
        if any(SED_WRITE_EXEC.search(s) for s in scripts):
            return "a sed `w`/`W`/`e` command or `s///w`/`s///e` flag writes a file or runs a command"
    return None


def shell_segments(cmd):
    """Each simple command of a shell line as an argv (split at ; & | && || and newlines, quotes respected)."""
    segs = []
    for line in cmd.split("\n"):
        lex = shlex.shlex(line, posix=True, punctuation_chars=";&|")
        lex.whitespace_split = True
        lex.commenters = ""
        cur = []
        try:
            for tok in lex:
                if tok and not tok.strip(";&|"):
                    segs.append(cur)
                    cur = []
                else:
                    cur.append(tok)
        except ValueError:
            pass
        segs.append(cur)
    return [s for s in segs if s]


def ro_forbidden_form(cmd):
    """The first write/exec form or rewriting formatter in any command of a shell line, or None."""
    for argv in shell_segments(cmd):
        why = write_exec_form(argv, readonly=True)
        if why:
            return why
    return None
```

- [ ] **Step 4: Make the allow-list skip those forms**

In `segment_allowed`, add the `write_exec_form` check right after the `if not argv: return None` guard, before the pinned-command check:

```python fragment
def segment_allowed(argv, footprint, pinned, readonly=False, wt=None):
    """Why this single argv is pre-approved, or None."""
    if not argv:
        return None
    if write_exec_form(argv, readonly=readonly):
        return None          # writes a file or runs another program: never pre-approved, not even when pinned
    if prefix_match(argv, pinned):
        return "pinned command from the briefing"
```

- [ ] **Step 5: Deny those forms explicitly for read-only roles**

In `guard_bash_ro`, insert the `ro_forbidden_form` check between the `for pat in BASH_RO_DENY:` loop and the `root = find_state_root(...)` line:

```python fragment
    for pat in BASH_RO_DENY:
        if re.search(pat, cmd):
            deny(f"Read-only role: `{raw[:80]}` looks like it modifies files/packages/git state. "
                 "Use Read/Grep/Glob, run tests/linters/diffs only, and report instead of changing anything.")
    why = ro_forbidden_form(cmd)
    if why:
        deny(f"Read-only role: `{raw[:80]}` is blocked: {why}. Run checks in their read-only form "
             "(`--check` / `--diff`, no output file, no helper program) and report instead of changing anything.")
    root = find_state_root(inp.get("cwd") or os.getcwd())
```

- [ ] **Step 6: Run test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_readonly.py' -k ReadOnlyWriteExecFormsTest`
Expected: PASS (`Ran 4 tests`, `OK`)

- [ ] **Step 7: Write the failing test for rewriting formatters (DG5)**

Append to the end of `_shared/tests/test_guard_readonly.py`:

```python
REWRITING = [
    "black .",
    "black src/app.py",
    "ruff format .",
    "ruff check --fix .",
    "ruff --fix .",
    "prettier --write .",
    "prettier -w src",
    "gofmt -w .",
    "go fmt ./...",
    "cargo fmt",
    "isort .",
    "rustfmt src/main.rs",
    "eslint --fix src",
    "npx prettier --write .",
    "uv run black .",
]

CHECK_MODES = [
    "black --check .",
    "black --diff src",
    "ruff check .",
    "ruff format --check .",
    "prettier --check .",
    "gofmt -l .",
    "cargo fmt --check",
    "isort --check-only .",
    "rustfmt --check src/main.rs",
]


class RewritingFormatterTest(GuardCase):
    def test_bash_ro_denies_rewriting_formatters(self):
        bad = [c for c in REWRITING if self.bash_ro(c) != "deny"]
        self.assertEqual(bad, [])

    def test_read_only_allow_list_skips_them(self):
        bad = [c for c in REWRITING if self.preapproved(c, readonly=True) is not None]
        self.assertEqual(bad, [])

    def test_check_modes_stay_allowed(self):
        bad = [c for c in CHECK_MODES if self.bash_ro(c) != "allow"]
        self.assertEqual(bad, [])

    def test_programmer_may_still_format(self):
        for cmd in ("black .", "gofmt -w .", "ruff format ."):
            self.assertIsNotNone(self.preapproved(cmd), cmd)
```

- [ ] **Step 8: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_readonly.py' -k RewritingFormatterTest`
Expected: FAIL. The run ends with `FAILED (failures=2)`. The failures are `AssertionError: Lists differ` in `test_bash_ro_denies_rewriting_formatters` and `test_read_only_allow_list_skips_them`, listing formatters such as `'black .'`. `test_check_modes_stay_allowed` and `test_programmer_may_still_format` pass.

- [ ] **Step 9: Add the formatter detector**

In `dev-team-glm/scripts/guard.py`, insert this function directly before `def write_exec_form(`:

```python
def rewrites_files(head, rest):
    """True when a formatter/fixer call rewrites files in place instead of only checking them."""
    sub = next((a for a in rest if not a.startswith("-")), "")
    runners = ("npx", "bunx", "pnpx")
    if sub and (head in runners or (head in ("poetry", "uv", "pnpm", "yarn", "bundle") and sub in ("run", "exec"))):
        tail = rest[rest.index(sub) + (0 if head in runners else 1):]
        inner = next((a for a in tail if not a.startswith("-")), "")
        return bool(inner) and rewrites_files(os.path.basename(inner), tail[tail.index(inner) + 1:])
    if head == "black":
        return not _has(rest, "--check", "--diff")
    if head == "isort":
        return not _has(rest, "--check-only", "--check", "-c", "--diff")
    if head == "ruff":
        return _has(rest, "--fix", "--fix-only") or (sub == "format" and not _has(rest, "--check", "--diff"))
    if head == "prettier":
        return _has(rest, "--write", "-w")
    if head == "gofmt":
        return _has(rest, "-w")
    if head == "go":
        return sub in ("fmt", "fix", "generate")
    if head == "cargo":
        return sub == "fix" or (sub == "fmt" and not _has(rest, "--check"))
    if head == "rustfmt":
        return not _has(rest, "--check")
    if head == "eslint":
        return _has(rest, "--fix")
    if head == "rubocop":
        return _has(rest, "-a", "-A", "--autocorrect", "--autocorrect-all", "--auto-correct",
                    "--auto-correct-all", "-x", "--fix-layout")
    if head == "deno":
        return sub == "fmt" and not _has(rest, "--check")
    if head == "dotnet":
        return sub == "format" and not _has(rest, "--verify-no-changes")
    return False
```

Then, at the end of `write_exec_form`, add the read-only formatter check between the sed block and the final `return None`:

```python fragment
        if any(SED_WRITE_EXEC.search(s) for s in scripts):
            return "a sed `w`/`W`/`e` command or `s///w`/`s///e` flag writes a file or runs a command"
    if readonly and rewrites_files(head, rest):
        return (f"`{head}` rewrites files in place; a read-only role may run a formatter only in its "
                "check mode (`--check` / `--diff`)")
    return None
```

- [ ] **Step 10: Run test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_readonly.py' -k RewritingFormatterTest`
Expected: PASS (`Ran 4 tests`, `OK`)

- [ ] **Step 11: Write the failing test for devteam status/probe (DG14)**

Append to the end of `_shared/tests/test_guard_readonly.py`:

```python
class DevteamStatusProbeTest(GuardCase):
    STATUS = [
        "python3 dev-team-glm/scripts/devteam.py status",
        "python3 /opt/skills/dev-team-glm/scripts/devteam.py probe",
        "python devteam.py status",
    ]
    OTHER = [
        "python3 dev-team-glm/scripts/devteam.py claim S1",
        "python3 devteam.py integrate S1",
        "python3 notdevteam.py status",
        "python3 dev-team-glm/scripts/guard.py oc",
    ]

    def test_status_and_probe_allowed_for_read_only_roles(self):
        bad = [c for c in self.STATUS if self.bash_ro(c) != "allow"]
        self.assertEqual(bad, [])

    def test_other_engine_verbs_are_not_preapproved(self):
        bad = [c for c in self.OTHER if self.bash_ro(c) == "allow"]
        self.assertEqual(bad, [])

    def test_programmer_allow_list_still_skips_the_engine(self):
        self.assertIsNone(self.preapproved("python3 devteam.py status"))
```

- [ ] **Step 12: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_readonly.py' -k DevteamStatusProbeTest`
Expected: FAIL. The run ends with `FAILED (failures=1)`. The failure is `AssertionError: Lists differ` in `test_status_and_probe_allowed_for_read_only_roles`, listing all three status/probe commands.

- [ ] **Step 13: Pre-approve status/probe for read-only roles**

In `segment_allowed`, inside the interpreter branch `if head in ("python", "python3", "node", "ruby", "php", "bash", "sh", "elixir"):`, add the status/probe check as the first statement, before the `INTERPRETER_EVAL_FLAGS` check:

```python fragment
        if head in ("python", "python3", "node", "ruby", "php", "bash", "sh", "elixir"):
            if readonly and head in ("python", "python3") and len(argv) >= 3 and \
                    (argv[1] == "devteam.py" or argv[1].endswith("/devteam.py")) and argv[2] in ("status", "probe"):
                return "dev-team engine status/probe (read-only)"
            if any(a in INTERPRETER_EVAL_FLAGS for a in argv[1:]):
                return None
```

- [ ] **Step 14: Run test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_guard_readonly.py'`
Expected: PASS (`Ran 11 tests`, `OK`)

- [ ] **Step 15: Run the full suite and the dev-team selftest**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no failure or error comes from `test_guard_readonly.py` or any other guard test. Any remaining red is limited to the known stale-fixture baseline.

Run: `env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh`
Expected: `passed=` is at least 324 and `failed=` is at most 5 (only the 5 known macOS failures).

- [ ] **Step 16: Commit**

```bash
cd ..
git add glm-skills/dev-team-glm/scripts/guard.py glm-skills/_shared/tests/test_guard_readonly.py
git commit -m "fix(dev-team): close read-only allow-list holes (write/exec flags, rewriting formatters, status/probe)"
```

---

### T09: devteam-guard plugins v1/v2 [P]

**Depends:** T01

**Interfaces:**
- Consumes: `sh _shared/sync.sh [DEST_ROOT]`; `glm-skills`; `_shared`
- Produces: `guard.py oc`; `write`; `edit`; `patch`; `apply_patch`; `multiedit`; `shell`; `bash`; `execute`; `batch`; `event.agent`; `DEVTEAM_ROLE`; `programmer`; `programmer-lite`; `code-reviewer`; `spot-reviewer`; `investigator`; `team-leader`

**Files:**
- Modify: `glm-skills/dev-team-glm/opencode/plugins/devteam-guard.v1.js:1-45`
- Modify: `glm-skills/dev-team-glm/opencode/plugins/devteam-guard.v2.js:1-49`
- Test: `glm-skills/_shared/tests/test_devteam_plugins.py`

This task fixes DG8, DG9 and DG10 from the spec. Both plugins now spawn `guard.py oc` only for the tools `write`, `edit`, `patch`, `apply_patch`, `multiedit`, `shell`, `bash`, `execute` and `batch`. The spawn is asynchronous. A failing guard still fails open, but the plugin warns loudly only once per lane, because one lane is one OpenCode process. When `DEVTEAM_ROLE` is unset, the v2 plugin falls back to `event.agent` if that names a dev-team role. The v2 plugin also awaits `api.tool.hook(...)`.

All commands run from `glm-skills/` (`cd glm-skills`).

- [ ] **Step 1: Fix the test module's plugin path and extend the node drivers**

In `_shared/tests/test_devteam_plugins.py`, find the block that starts at `TESTS_DIR = os.path.dirname(os.path.abspath(__file__))` and ends just before `class TestDevteamPlugins(unittest.TestCase):`. Today that is lines 10-151: the path constants, `NEEDS_NODE`, `_write_guard_stub`, `_write_recording_stub`, `_load_plugin_source`, `_run_v1` and `_run_v2`. Replace the whole block with the code below. It fixes the stale `skills/glm/...` path by resolving the plugins relative to this file. It also adds `calls`, `agent` and `delayed_hook` parameters to the drivers. Their defaults keep every existing test unchanged.

```python
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.abspath(
    os.path.join(TESTS_DIR, "..", "..", "dev-team-glm", "opencode", "plugins")
)
V1_PATH = os.path.join(PLUGIN_DIR, "devteam-guard.v1.js")
V2_PATH = os.path.join(PLUGIN_DIR, "devteam-guard.v2.js")

NEEDS_NODE = unittest.skipUnless(shutil.which("node"), "node not installed")

GUARDED_TOOLS = [
    "write",
    "edit",
    "patch",
    "apply_patch",
    "multiedit",
    "shell",
    "bash",
    "execute",
    "batch",
]
UNGUARDED_TOOLS = ["read", "glob", "grep", "todowrite", "webfetch", "skill", "question"]
DEVTEAM_AGENTS = [
    "programmer",
    "programmer-lite",
    "code-reviewer",
    "spot-reviewer",
    "investigator",
    "team-leader",
]
DENY = {
    "hookSpecificOutput": {
        "permissionDecision": "deny",
        "permissionDecisionReason": "guarded",
    }
}


def _write_guard_stub(skill_dir, decision):
    scripts_dir = os.path.join(skill_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    guard_path = os.path.join(scripts_dir, "guard.py")
    with open(guard_path, "w") as f:
        f.write(
            "import json\nimport sys\n\nsys.stdin.read()\nprint(json.dumps(%s))\n"
            % json.dumps(decision)
        )
    return guard_path


def _write_recording_stub(skill_dir, decision, record_path):
    scripts_dir = os.path.join(skill_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    guard_path = os.path.join(scripts_dir, "guard.py")
    with open(guard_path, "w") as f:
        f.write(
            "import json\nimport sys\n\n"
            "argv = sys.argv[1:]\n"
            "stdin_data = json.loads(sys.stdin.read())\n"
            "with open(%s, 'w') as rec:\n"
            "    json.dump({'argv': argv, 'stdin': stdin_data}, rec)\n"
            "print(json.dumps(%s))\n"
            % (json.dumps(record_path), json.dumps(decision))
        )
    return guard_path


def _write_failing_stub(skill_dir):
    scripts_dir = os.path.join(skill_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    guard_path = os.path.join(scripts_dir, "guard.py")
    with open(guard_path, "w") as f:
        f.write("import sys\n\nsys.stdin.read()\nsys.exit(1)\n")
    return guard_path


def _load_plugin_source(path, skill_dir):
    with open(path) as f:
        source = f.read()
    return source.replace("{{SKILL_DIR}}", skill_dir)


def _node_env(role):
    env = dict(os.environ)
    if role is None:
        env.pop("DEVTEAM_ROLE", None)
    else:
        env["DEVTEAM_ROLE"] = role
    return env


def _run_v1(tmp_dir, skill_dir, role, tool, args, calls=1):
    source = _load_plugin_source(V1_PATH, skill_dir)
    plugin_path = os.path.join(tmp_dir, "plugin.mjs")
    with open(plugin_path, "w") as f:
        f.write(source)
    driver_path = os.path.join(tmp_dir, "driver.mjs")
    driver = textwrap.dedent(
        """\
        import { DevteamGuard } from "%s";
        const hooks = await DevteamGuard({ directory: "/tmp/work" });
        const out = [];
        for (let i = 0; i < %d; i++) {
          try {
            await hooks["tool.execute.before"](
              { tool: "%s", sessionID: "s", callID: "c" },
              { args: %s }
            );
            out.push("ALLOWED");
          } catch (err) {
            out.push("DENIED:" + err.message);
          }
        }
        process.stdout.write(out.join("\\n"));
        """
    ) % (plugin_path, calls, tool, json.dumps(args))
    with open(driver_path, "w") as f:
        f.write(driver)
    return subprocess.run(
        ["node", driver_path],
        capture_output=True,
        text=True,
        env=_node_env(role),
        timeout=30,
    )


def _run_v2(tmp_dir, skill_dir, role, tool, args, agent="a", calls=1, delayed_hook=False):
    # Drives the plugin the way the real v2 binary does. It imports the
    # default export ({id, setup}) and calls setup(api) with a fake api
    # whose tool.hook(name, fn) records the registered hook. Then it invokes
    # that hook with the real event shape {tool, sessionID, agent, messageID,
    # id, input}. With delayed_hook the fake api registers the hook only
    # after a timer and returns a promise, so a plugin that does not await
    # the registration has no hook yet when setup() resolves.
    source = _load_plugin_source(V2_PATH, skill_dir)
    plugin_path = os.path.join(tmp_dir, "plugin.mjs")
    with open(plugin_path, "w") as f:
        f.write(source)
    work_dir = os.path.join(tmp_dir, "work")
    os.makedirs(work_dir, exist_ok=True)
    driver_path = os.path.join(tmp_dir, "driver.mjs")
    driver = textwrap.dedent(
        """\
        import plugin from "%s";
        if (typeof plugin.id !== "string" || plugin.id.length === 0) {
          throw new Error("plugin.id must be a non-empty string");
        }
        if (typeof plugin.setup !== "function") {
          throw new Error("plugin.setup must be a function");
        }
        const delayed = %s;
        const hooks = {};
        const api = {
          tool: {
            hook: (name, fn) => {
              if (!delayed) {
                hooks[name] = fn;
                return undefined;
              }
              return new Promise((resolve) => {
                setTimeout(() => {
                  hooks[name] = fn;
                  resolve();
                }, 20);
              });
            },
          },
        };
        await plugin.setup(api);
        if (typeof hooks["execute.before"] !== "function") {
          throw new Error("plugin did not register an execute.before hook");
        }
        const out = [];
        for (let i = 0; i < %d; i++) {
          try {
            await hooks["execute.before"]({
              tool: "%s",
              sessionID: "s",
              agent: %s,
              messageID: "m",
              id: "c",
              input: %s,
            });
            out.push("ALLOWED");
          } catch (err) {
            out.push("DENIED:" + err.message);
          }
        }
        process.stdout.write(out.join("\\n"));
        """
    ) % (
        plugin_path,
        "true" if delayed_hook else "false",
        calls,
        tool,
        json.dumps(agent),
        json.dumps(args),
    )
    with open(driver_path, "w") as f:
        f.write(driver)
    return subprocess.run(
        ["node", driver_path],
        capture_output=True,
        text=True,
        env=_node_env(role),
        timeout=30,
        cwd=work_dir,
    )
```

- [ ] **Step 2: Run the existing plugin tests against the new drivers**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_plugins.py'`
Expected: PASS, ending with `Ran 10 tests` and `OK`. This step only refactors test code, so the plugins are untouched.

- [ ] **Step 3: Write the failing v1 tests (tool filter, warn once, async spawn)**

Insert these methods at the end of `class TestDevteamPlugins`, directly above the `if __name__ == "__main__":` line:

```python
    @NEEDS_NODE
    def test_v1_skips_unguarded_tools(self):
        for tool in UNGUARDED_TOOLS:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                record_path = os.path.join(tmp_dir, "record.json")
                _write_recording_stub(skill_dir, DENY, record_path)
                result = _run_v1(
                    tmp_dir, skill_dir, "programmer", tool, {"filePath": "a.py"}
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "ALLOWED")
                self.assertFalse(
                    os.path.exists(record_path), "guard spawned for " + tool
                )

    @NEEDS_NODE
    def test_v1_guards_every_write_and_shell_tool(self):
        for tool in GUARDED_TOOLS:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                _write_guard_stub(skill_dir, DENY)
                result = _run_v1(
                    tmp_dir, skill_dir, "programmer", tool, {"command": "ls"}
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "DENIED:guarded")

    @NEEDS_NODE
    def test_v1_warns_fail_open_once(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_failing_stub(skill_dir)
            result = _run_v1(
                tmp_dir, skill_dir, "programmer", "bash", {"command": "ls"}, calls=2
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED\nALLOWED")
            self.assertEqual(result.stderr.count("failing open"), 1, result.stderr)

    def test_v1_source_uses_async_spawn(self):
        with open(V1_PATH) as f:
            source = f.read()
        self.assertNotIn("spawnSync", source)
        self.assertIn("spawn(", source)
```

- [ ] **Step 4: Run the v1 tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_plugins.py' -k test_v1`
Expected: FAIL. `test_v1_skips_unguarded_tools` fails with `AssertionError: 'DENIED:guarded' != 'ALLOWED'`. `test_v1_warns_fail_open_once` fails with `AssertionError: 2 != 1`. `test_v1_source_uses_async_spawn` fails with `AssertionError: 'spawnSync' unexpectedly found`. `test_v1_guards_every_write_and_shell_tool` and the older v1 tests already pass.

- [ ] **Step 5: Rewrite the v1 plugin**

Replace all of `dev-team-glm/opencode/plugins/devteam-guard.v1.js` with:

```javascript
// Calls: python3 guard.py oc
// Spawns guard.py only for tools that can write files or run commands. The spawn is
// asynchronous so read-only tools pay nothing and the event loop never blocks. A failing guard
// fails open (integrate re-checks the footprint) and warns loudly once per lane process.
import { spawn } from "node:child_process";
import path from "node:path";

const GUARDED_TOOLS = new Set([
  "write",
  "edit",
  "patch",
  "apply_patch",
  "multiedit",
  "shell",
  "bash",
  "execute",
  "batch",
]);
const GUARD_TIMEOUT_MS = 30000;

let warnedFailOpen = false;

function failOpen(reason) {
  if (warnedFailOpen) return;
  warnedFailOpen = true;
  console.error(
    "devteam-guard: WARNING guard.py oc " + reason +
      " — failing open for the rest of this lane; integrate re-checks the footprint"
  );
}

function runGuard(payload) {
  return new Promise((resolve) => {
    const guardScript = path.join("{{SKILL_DIR}}", "scripts", "guard.py");
    let settled = false;
    let timer = null;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      resolve(value);
    };
    let child;
    try {
      child = spawn("python3", [guardScript, "oc"], { stdio: ["pipe", "pipe", "ignore"] });
    } catch (err) {
      failOpen(err.message);
      finish(null);
      return;
    }
    let stdout = "";
    timer = setTimeout(() => {
      failOpen("timed out after " + GUARD_TIMEOUT_MS + " ms");
      child.kill("SIGKILL");
      finish(null);
    }, GUARD_TIMEOUT_MS);
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.on("error", (err) => {
      failOpen(err.message);
      finish(null);
    });
    child.on("close", (code) => {
      if (settled) return;
      if (code !== 0) {
        failOpen("exited " + code);
        finish(null);
        return;
      }
      const text = stdout.trim();
      if (!text) {
        finish(null);
        return;
      }
      try {
        finish(JSON.parse(text));
      } catch (err) {
        failOpen(err.message);
        finish(null);
      }
    });
    child.stdin.on("error", () => {});
    child.stdin.end(payload);
  });
}

export const DevteamGuard = async ({ directory }) => {
  return {
    "tool.execute.before": async (input, output) => {
      const role = process.env.DEVTEAM_ROLE;
      if (!role) return;
      if (!GUARDED_TOOLS.has(input.tool)) return;
      let decision = null;
      try {
        const payload = JSON.stringify({
          tool: input.tool,
          args: output.args,
          cwd: directory,
          role: role,
        });
        decision = await runGuard(payload);
      } catch (err) {
        failOpen(err.message);
        decision = null;
      }
      if (
        decision &&
        decision.hookSpecificOutput &&
        decision.hookSpecificOutput.permissionDecision === "deny"
      ) {
        throw new Error(
          decision.hookSpecificOutput.permissionDecisionReason || "denied by devteam guard"
        );
      }
    },
  };
};
```

- [ ] **Step 6: Run the v1 tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_plugins.py' -k test_v1`
Expected: PASS, ending with `OK`.

- [ ] **Step 7: Write the failing v2 tests (tool filter, agent role fallback, awaited registration, warn once, async spawn)**

Insert these methods at the end of `class TestDevteamPlugins`, directly above the `if __name__ == "__main__":` line:

```python
    @NEEDS_NODE
    def test_v2_skips_unguarded_tools(self):
        for tool in UNGUARDED_TOOLS:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                record_path = os.path.join(tmp_dir, "record.json")
                _write_recording_stub(skill_dir, DENY, record_path)
                result = _run_v2(
                    tmp_dir, skill_dir, "code-reviewer", tool, {"path": "a.py"}
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "ALLOWED")
                self.assertFalse(
                    os.path.exists(record_path), "guard spawned for " + tool
                )

    @NEEDS_NODE
    def test_v2_guards_every_write_and_shell_tool(self):
        for tool in GUARDED_TOOLS:
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                _write_guard_stub(skill_dir, DENY)
                result = _run_v2(
                    tmp_dir, skill_dir, "code-reviewer", tool, {"command": "ls"}
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "DENIED:guarded")

    @NEEDS_NODE
    def test_v2_uses_event_agent_as_role_when_env_unset(self):
        for agent in DEVTEAM_AGENTS:
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                record_path = os.path.join(tmp_dir, "record.json")
                _write_recording_stub(skill_dir, {}, record_path)
                result = _run_v2(
                    tmp_dir, skill_dir, None, "shell", {"command": "ls"}, agent=agent
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "ALLOWED")
                self.assertTrue(os.path.exists(record_path), "guard not spawned for " + agent)
                with open(record_path) as f:
                    record = json.load(f)
                self.assertEqual(record["stdin"]["role"], agent)
                self.assertEqual(record["stdin"]["tool"], "shell")
                self.assertEqual(record["stdin"]["args"], {"command": "ls"})

    @NEEDS_NODE
    def test_v2_env_role_wins_over_event_agent(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            record_path = os.path.join(tmp_dir, "record.json")
            _write_recording_stub(skill_dir, {}, record_path)
            result = _run_v2(
                tmp_dir,
                skill_dir,
                "code-reviewer",
                "shell",
                {"command": "ls"},
                agent="programmer",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            with open(record_path) as f:
                record = json.load(f)
            self.assertEqual(record["stdin"]["role"], "code-reviewer")

    @NEEDS_NODE
    def test_v2_ignores_non_devteam_agent(self):
        for agent in ["general", "build", "a"]:
            with self.subTest(agent=agent), tempfile.TemporaryDirectory() as tmp_dir:
                skill_dir = os.path.join(tmp_dir, "skill")
                record_path = os.path.join(tmp_dir, "record.json")
                _write_recording_stub(skill_dir, DENY, record_path)
                result = _run_v2(
                    tmp_dir, skill_dir, None, "shell", {"command": "rm -rf /"}, agent=agent
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "ALLOWED")
                self.assertFalse(os.path.exists(record_path), "guard spawned for " + agent)

    @NEEDS_NODE
    def test_v2_awaits_hook_registration(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_guard_stub(skill_dir, DENY)
            result = _run_v2(
                tmp_dir,
                skill_dir,
                "code-reviewer",
                "edit",
                {"path": "a.py", "oldString": "x", "newString": "y"},
                delayed_hook=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "DENIED:guarded")

    @NEEDS_NODE
    def test_v2_warns_fail_open_once(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_failing_stub(skill_dir)
            result = _run_v2(
                tmp_dir, skill_dir, "code-reviewer", "edit", {"path": "a.py"}, calls=2
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED\nALLOWED")
            self.assertEqual(result.stderr.count("failing open"), 1, result.stderr)

    def test_v2_source_uses_async_spawn_and_awaits_hook(self):
        with open(V2_PATH) as f:
            source = f.read()
        self.assertNotIn("spawnSync", source)
        self.assertIn("spawn(", source)
        self.assertIn("await api.tool.hook", source)
```

- [ ] **Step 8: Run the v2 tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_plugins.py' -k test_v2`
Expected: FAIL. `test_v2_skips_unguarded_tools` fails with `AssertionError: 'DENIED:guarded' != 'ALLOWED'`. `test_v2_uses_event_agent_as_role_when_env_unset` fails with `AssertionError: False is not true : guard not spawned for programmer`. `test_v2_awaits_hook_registration` fails with `AssertionError: 1 != 0` and `plugin did not register an execute.before hook` in stderr. `test_v2_warns_fail_open_once` fails with `AssertionError: 2 != 1`. `test_v2_source_uses_async_spawn_and_awaits_hook` fails with `AssertionError: 'spawnSync' unexpectedly found`. `test_v2_guards_every_write_and_shell_tool`, `test_v2_env_role_wins_over_event_agent`, `test_v2_ignores_non_devteam_agent` and the older v2 tests already pass.

- [ ] **Step 9: Rewrite the v2 plugin**

Replace all of `dev-team-glm/opencode/plugins/devteam-guard.v2.js` with:

```javascript
// OpenCode v2 plugin: default export {id, setup(api)}; api.tool.hook("execute.before", fn) fires
// before every tool call with an event {tool, sessionID, agent, messageID, id, input}. Throwing
// inside the hook denies the call. setup() gets no per-call directory from the api, so we use
// process.cwd() (the lane's cwd) for the guard payload instead. The role comes from DEVTEAM_ROLE;
// when that is unset (agents started by the subagent tool) event.agent is used if it names a
// dev-team role. guard.py is spawned asynchronously and only for tools that can write files or
// run commands. A failing guard fails open (integrate re-checks the footprint) and warns loudly
// once per lane process.
import { spawn } from "node:child_process";
import path from "node:path";

const GUARDED_TOOLS = new Set([
  "write",
  "edit",
  "patch",
  "apply_patch",
  "multiedit",
  "shell",
  "bash",
  "execute",
  "batch",
]);
const DEVTEAM_ROLES = new Set([
  "programmer",
  "programmer-lite",
  "code-reviewer",
  "spot-reviewer",
  "investigator",
  "team-leader",
]);
const GUARD_TIMEOUT_MS = 30000;

let warnedFailOpen = false;

function failOpen(reason) {
  if (warnedFailOpen) return;
  warnedFailOpen = true;
  console.error(
    "devteam-guard: WARNING guard.py oc " + reason +
      " — failing open for the rest of this lane; integrate re-checks the footprint"
  );
}

function resolveRole(event) {
  const envRole = process.env.DEVTEAM_ROLE;
  if (envRole) return envRole;
  if (event && typeof event.agent === "string" && DEVTEAM_ROLES.has(event.agent)) {
    return event.agent;
  }
  return null;
}

function runGuard(payload) {
  return new Promise((resolve) => {
    const guardScript = path.join("{{SKILL_DIR}}", "scripts", "guard.py");
    let settled = false;
    let timer = null;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      resolve(value);
    };
    let child;
    try {
      child = spawn("python3", [guardScript, "oc"], { stdio: ["pipe", "pipe", "ignore"] });
    } catch (err) {
      failOpen(err.message);
      finish(null);
      return;
    }
    let stdout = "";
    timer = setTimeout(() => {
      failOpen("timed out after " + GUARD_TIMEOUT_MS + " ms");
      child.kill("SIGKILL");
      finish(null);
    }, GUARD_TIMEOUT_MS);
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.on("error", (err) => {
      failOpen(err.message);
      finish(null);
    });
    child.on("close", (code) => {
      if (settled) return;
      if (code !== 0) {
        failOpen("exited " + code);
        finish(null);
        return;
      }
      const text = stdout.trim();
      if (!text) {
        finish(null);
        return;
      }
      try {
        finish(JSON.parse(text));
      } catch (err) {
        failOpen(err.message);
        finish(null);
      }
    });
    child.stdin.on("error", () => {});
    child.stdin.end(payload);
  });
}

export default {
  id: "devteam-guard",
  setup: async (api) => {
    await api.tool.hook("execute.before", async (event) => {
      const role = resolveRole(event);
      if (!role) return;
      if (!GUARDED_TOOLS.has(event.tool)) return;
      let decision = null;
      try {
        const payload = JSON.stringify({
          tool: event.tool,
          args: event.input,
          cwd: process.cwd(),
          role: role,
        });
        decision = await runGuard(payload);
      } catch (err) {
        failOpen(err.message);
        decision = null;
      }
      if (
        decision &&
        decision.hookSpecificOutput &&
        decision.hookSpecificOutput.permissionDecision === "deny"
      ) {
        throw new Error(
          decision.hookSpecificOutput.permissionDecisionReason || "denied by devteam guard"
        );
      }
    });
  },
};
```

- [ ] **Step 10: Run all plugin tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_plugins.py'`
Expected: PASS, ending with `Ran 22 tests` and `OK`.

- [ ] **Step 11: Run the full suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no failure or error comes from `test_devteam_plugins`, and the total of failures plus errors is no higher than the 11-test baseline.

- [ ] **Step 12: Commit**

```bash
cd ..
git add glm-skills/dev-team-glm/opencode/plugins/devteam-guard.v1.js glm-skills/dev-team-glm/opencode/plugins/devteam-guard.v2.js glm-skills/_shared/tests/test_devteam_plugins.py
git commit -m "fix(dev-team): guard plugins spawn async only for write/shell tools, warn once on fail-open, v2 falls back to event.agent role"
```

---

### T10: dev-team OpenCode agent files [P]

**Depends:** —

**Files:**
- Modify: `glm-skills/dev-team-glm/opencode/agents/programmer.md`
- Modify: `glm-skills/dev-team-glm/opencode/agents/team-leader.md`

- [ ] **Step 1: Clarify programmer re-runs claim in programmer.md**

In `programmer.md`, lines 20-25 say the dispatch prompt is `python3 <skill>/scripts/devteam.py claim <ID>`. Replace this section to clarify that the prompt **is** the claim output and running it again is the intended behavior:

```markdown
Your dispatch prompt **is** the output of `python3 <skill>/scripts/devteam.py claim <ID>` run by
the Conductor. Run it verbatim as your first Bash command (you will re-run it here, in your
worktree, to bind this branch and print your complete briefing).
```

- [ ] **Step 2: Add explicit memory path to team-leader.md**

In `team-leader.md`, line 23 mentions `**Memory.**` but never gives the actual path. Replace lines 23-26 to include the explicit path:

```markdown
**Memory.** Your memory for this repository lives in `.claude/dev-team/MEMORY.md`.
Before exploring, read it (module map, conventions, commands, past pitfalls). After planning,
save what would make the next plan faster: the module/ownership map, exact commands, test
conventions, contract hotspots, files that tend to be shared. Keep it curated and short.
```

- [ ] **Step 3: Clarify memory context in team-leader MODE PLANNING section**

In `team-leader.md`, line 68 mentions memory in the context of the `context` field. At the line explaining `context`, add a note about the memory file being the source of repository conventions:

After line 68 (after "representative test file (→ `context`)"), add inline:

```markdown
Record per-slice what programmers must open and one representative test file (→ `context`);
save repository conventions and module maps to `.claude/dev-team/MEMORY.md` for reuse.
```

Replace the existing line 68 "Record per slice…" with this version.

- [ ] **Step 4: Verify no syntax errors**

Check that both agent files remain valid YAML frontmatter and markdown:

```bash
cd /Users/yamazaki-ethan/Documents/Projects/skillz/glm-skills
head -20 dev-team-glm/opencode/agents/programmer.md
head -30 dev-team-glm/opencode/agents/team-leader.md
```

Expected: Both files show valid YAML frontmatter followed by markdown body.

- [ ] **Step 5: Commit**

```bash
cd /Users/yamazaki-ethan/Documents/Projects/skillz/glm-skills
git add glm-skills/dev-team-glm/opencode/agents/programmer.md glm-skills/dev-team-glm/opencode/agents/team-leader.md
git commit -m "docs(dev-team): clarify programmer re-runs claim, add memory path to team-leader"
```

---

### T11: devteam.py harness detection and dispatch routing [P]

**Depends:** T03

**Interfaces:**
- Consumes: `def harness(script_path: str = "") -> str`; `def major(skill_dir: str = "", binary: str = "opencode") -> int`

**Files:**
- Modify: `glm-skills/dev-team-glm/scripts/devteam.py`
- Test: `glm-skills/_shared/tests/test_devteam_oc_harness.py`

This task fixes four dev-team defects: DE1 (harness detection), DE7 (lite lane agent), DE8 (Claude-only concurrency cap) and DE9 (OpenCode launch hint). All commands run from `glm-skills/` (`cd glm-skills` first).

- [ ] **Step 1: Write the failing test for harness detection (DE1)**

Create `_shared/tests/test_devteam_oc_harness.py`:

```python
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "dev-team-glm", "scripts")
sys.path.insert(0, SCRIPTS)

import devteam  # noqa: E402


class HarnessDetectionTest(unittest.TestCase):
    """DE1: OpenCode v2 never sets OPENCODE, so detection must go through oc_harness.harness()."""

    def test_opencode_detected_through_oc_harness(self):
        oc = devteam._oc_harness()
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(oc, "harness", return_value="opencode") as h:
            self.assertTrue(devteam.is_opencode())
        h.assert_called_once_with(str(Path(devteam.__file__).resolve()))

    def test_claude_when_oc_harness_says_claude(self):
        oc = devteam._oc_harness()
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(oc, "harness", return_value="claude"):
            self.assertFalse(devteam.is_opencode())

    def test_devteam_harness_override_wins(self):
        oc = devteam._oc_harness()
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "claude"}, clear=True), \
                mock.patch.object(oc, "harness", return_value="opencode"):
            self.assertFalse(devteam.is_opencode())
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "opencode"}, clear=True), \
                mock.patch.object(oc, "harness", return_value="claude"):
            self.assertTrue(devteam.is_opencode())

    def test_v1_opencode_marker_still_detected(self):
        oc = devteam._oc_harness()
        with mock.patch.dict(os.environ, {"OPENCODE": "1"}, clear=True), \
                mock.patch.object(oc, "harness", return_value="claude"):
            self.assertTrue(devteam.is_opencode())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_harness.py' -k HarnessDetectionTest`
Expected: FAIL: `test_opencode_detected_through_oc_harness` with `AssertionError: False is not true`

- [ ] **Step 3: Route `is_opencode()` through `oc_harness.harness()`**

In `dev-team-glm/scripts/devteam.py`, replace the whole `def is_opencode() -> bool:` function (just below `MAX_LANE_RUNS = 4`) with:

```python
def is_opencode() -> bool:
    """OpenCode path: DEVTEAM_HARNESS decides when set; otherwise v1's OPENCODE marker, or
    oc_harness.harness() (which also recognises v2, where OPENCODE is never set)."""
    forced = os.environ.get("DEVTEAM_HARNESS")
    if forced is not None:
        return forced == "opencode"
    if os.environ.get("OPENCODE"):
        return True
    try:
        return _oc_harness().harness(str(Path(__file__).resolve())) == "opencode"
    except Exception:
        return False
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_harness.py' -k HarnessDetectionTest`
Expected: PASS (`Ran 4 tests` ... `OK`)

- [ ] **Step 5: Write the failing test for the lite lane agent (DE7)**

Append to `_shared/tests/test_devteam_oc_harness.py`:

```python
class LiteLaneAgentTest(unittest.TestCase):
    """DE7: on OpenCode a programmer-lite slice must run the lite agent at low effort, not programmer."""

    def test_lite_lane_keeps_lite_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(devteam, "terminate_lane_process"), \
                    mock.patch.object(devteam.subprocess, "Popen", return_value=mock.MagicMock(pid=4242)):
                pid = devteam.launch_lane(root, {"provider": "glm"}, "S1", "programmer-lite", "",
                                          "python3 x claim S1")
            spec = json.loads((devteam.lanes_dir(root) / "S1.lane.json").read_text())
        self.assertEqual(pid, 4242)
        self.assertEqual(spec["agent"], "programmer-lite")
        self.assertEqual(spec["effort"], "low")
        self.assertTrue(spec["writer"])
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_harness.py' -k LiteLaneAgentTest`
Expected: FAIL with `AssertionError: 'programmer' != 'programmer-lite'`

- [ ] **Step 7: Stop mapping programmer-lite onto programmer**

In `dev-team-glm/scripts/devteam.py`, replace the line

```python fragment
OC_AGENTS = {"programmer-lite": "programmer"}          # OpenCode has one programmer agent
```

with

```python fragment
OC_AGENTS = {}          # OpenCode ships programmer-lite too: v1 takes its effort from that agent's frontmatter
```

Leave `launch_lane` unchanged. Its `"agent": OC_AGENTS.get(agent, agent)` now passes `programmer-lite` through.

- [ ] **Step 8: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_harness.py' -k LiteLaneAgentTest`
Expected: PASS (`Ran 1 test` ... `OK`)

- [ ] **Step 9: Write the failing test for the Claude-only cap (DE8)**

Append to `_shared/tests/test_devteam_oc_harness.py`:

```python
class ConcurrencyCapTest(unittest.TestCase):
    """DE8: Claude Code's subagent cap (default 20) must not bound OpenCode lanes."""

    def test_opencode_is_not_capped_by_claude_limit(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(devteam, "is_opencode", return_value=True):
            self.assertEqual(devteam.concurrency_limit(), devteam.HARD_CAP)
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "8"}, clear=True), \
                mock.patch.object(devteam, "is_opencode", return_value=True):
            self.assertEqual(devteam.concurrency_limit(), devteam.HARD_CAP)

    def test_claude_keeps_its_cap(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(devteam, "is_opencode", return_value=False):
            self.assertEqual(devteam.concurrency_limit(), devteam.DEFAULT_LIMIT)
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "8"}, clear=True), \
                mock.patch.object(devteam, "is_opencode", return_value=False):
            self.assertEqual(devteam.concurrency_limit(), 8)
```

- [ ] **Step 10: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_harness.py' -k ConcurrencyCapTest`
Expected: FAIL: `test_opencode_is_not_capped_by_claude_limit` with `AssertionError: 20 != 64`

- [ ] **Step 11: Apply the cap only on Claude**

In `dev-team-glm/scripts/devteam.py`, replace the whole `def concurrency_limit():` function with:

```python
def concurrency_limit():
    """Claude Code's concurrent-subagent cap. OpenCode lanes are plain processes: only HARD_CAP
    (and the governor) bounds them, so the 40/64 tier ceilings stay reachable."""
    if is_opencode():
        return HARD_CAP
    raw = os.environ.get("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", "")
    limit = int(raw) if raw.isdigit() else DEFAULT_LIMIT
    return max(1, min(HARD_CAP, limit))
```

- [ ] **Step 12: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_harness.py' -k ConcurrencyCapTest`
Expected: PASS (`Ran 2 tests` ... `OK`)

- [ ] **Step 13: Write the failing test for the launch hint (DE9)**

Append to `_shared/tests/test_devteam_oc_harness.py`:

```python
class LaunchHintTest(unittest.TestCase):
    """DE9: on OpenCode the lanes already run, so `start` must point to `wait`, not to Agent calls."""

    def test_opencode_hint_points_to_wait(self):
        with mock.patch.object(devteam, "is_opencode", return_value=True):
            hint = devteam.launch_hint()
        self.assertIn(" wait`", hint)
        self.assertIn("`next`", hint)
        self.assertNotIn("Agent call", hint)

    def test_claude_hint_unchanged(self):
        with mock.patch.object(devteam, "is_opencode", return_value=False):
            hint = devteam.launch_hint()
        self.assertEqual(hint, "Launch every Agent call above in ONE message (parallel tool calls), then end the "
                               "turn. On each wake-up (completion notification, background result, user answer): "
                               "`next` — no ids needed.")
```

- [ ] **Step 14: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_harness.py' -k LaunchHintTest`
Expected: FAIL with `AttributeError: module 'devteam' has no attribute 'launch_hint'`

- [ ] **Step 15: Add `launch_hint()` and use it in `start`**

In `dev-team-glm/scripts/devteam.py`, add this function directly after `emit_agent` (before `def lane_worktree`):

```python
def launch_hint() -> str:
    """What the Conductor does right after a dispatch: launch the Agent calls (Claude Code), or on
    OpenCode just wait, because every lane process is already running."""
    if is_opencode():
        return (f"Every LANE above is already running — launch nothing. Run `python3 {q(Path(__file__).resolve())} "
                f"wait` (it returns as soon as a lane finishes), then `next` — no ids needed; repeat until the endgame.")
    return ("Launch every Agent call above in ONE message (parallel tool calls), then end the turn. "
            "On each wake-up (completion notification, background result, user answer): `next` — no ids needed.")
```

Then, in the `start` command (the block that ends with `print_dispatch(st, blocks, skipped)`), replace

```python fragment
    out(progress_line(st),
        "Launch every Agent call above in ONE message (parallel tool calls), then end the turn. "
        "On each wake-up (completion notification, background result, user answer): `next` — no ids needed.")
```

with

```python fragment
    out(progress_line(st), launch_hint())
```

- [ ] **Step 16: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_harness.py' -k LaunchHintTest`
Expected: PASS (`Ran 2 tests` ... `OK`)

- [ ] **Step 17: Run the whole test module, the full suite and the selftest**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_harness.py'`
Expected: PASS (`Ran 9 tests` ... `OK`)

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: this task adds no new failures. In particular, `test_devteam_oc_lanes.py` `HarnessTest.test_is_opencode` still passes.

Run: `env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh`
Expected: `passed=` ≥ 324 and `failed=` ≤ 5 (only the 5 known macOS failures)

- [ ] **Step 18: Commit**

```bash
cd ..
git add glm-skills/dev-team-glm/scripts/devteam.py glm-skills/_shared/tests/test_devteam_oc_harness.py
git commit -m "fix(dev-team): detect OpenCode v2 via oc_harness, keep the lite lane agent, Claude-only cap, wait hint"
```

---

### T12: devteam.py lane lifecycle [P]

**Depends:** T04

**Runs after:** T11 (same files)

**Interfaces:**
- Consumes: `STALL_BY_ROLE = {"programmer": 900, "programmer-lite": 900, "team-leader": 900, "code-reviewer": 600, "spot-reviewer": 600, "investigator": 600}`; `def lane_stall(lane: dict, default: int = 180) -> int`; `<out_dir>/<lane id>.pgid`

**Files:**
- Modify: `glm-skills/dev-team-glm/scripts/devteam.py`
- Test: `glm-skills/_shared/tests/test_devteam_oc_lanes.py`

This task fixes the OpenCode lane lifecycle in `devteam.py` (spec DE2, DE3, DE10, DE13, DE14, DE15). Every command runs from `glm-skills/` (`cd glm-skills` first). T11 edits the same files before this task, so find each edit by the code it names, not by line number. The consumed contract is `oc_harness.STALL_BY_ROLE`, `oc_harness.lane_stall(lane: dict, default: int = 180) -> int`, and the pgid file `<out_dir>/<lane id>.pgid`, which `oc_harness` writes into the lanes dir (the `out_dir` that `cmd_lane_run` passes to `run_lanes`).

- [ ] **Step 1: Write the failing tests for the opencode process-group kill (DE2)**

In `_shared/tests/test_devteam_oc_lanes.py`, add `import signal` after `import shutil`. Add `import oc_harness  # noqa: E402` right after `import devteam  # noqa: E402`. Then put this block just before `if __name__ == "__main__":`:

```python
def _killpg_quiet(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def _reaped_pid():
    p = subprocess.Popen(["true"])
    p.wait()
    return p.pid


class LaneLifecycleTest(RepoCase):
    def lanes(self):
        d = devteam.lanes_dir(Path(self.repo))
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_spec(self, lane_id, agent, writer):
        spec = {"id": lane_id, "agent": agent, "model": "flash", "effort": "high",
                "prompt": "do it", "writer": writer}
        (self.lanes() / f"{lane_id}.lane.json").write_text(json.dumps(spec))
        return spec

    def run_lane(self, lane_id, results):
        """Run cmd_lane_run in-process with oc_harness.run_lanes faked; return (lanes seen, gate calls)."""
        seen, gates = [], []
        real_run = subprocess.run

        def fake_run(cmd, *args, **kwargs):
            if any("guard.py" in str(c) for c in cmd):
                gates.append(cmd)
                return subprocess.CompletedProcess(cmd, 0, "", "")
            return real_run(cmd, *args, **kwargs)

        def fake_run_lanes(lanes, out_dir, **kwargs):
            seen.append(dict(lanes[0]))
            return [results[min(len(seen), len(results)) - 1]]

        old_cwd = os.getcwd()
        os.chdir(self.repo)
        try:
            with mock.patch.dict(os.environ, self.env, clear=True), \
                    mock.patch.object(devteam.subprocess, "run", side_effect=fake_run), \
                    mock.patch.object(oc_harness, "run_lanes", side_effect=fake_run_lanes):
                devteam.cmd_lane_run(SimpleNamespace(lane_id=lane_id))
        finally:
            os.chdir(old_cwd)
        return seen, gates

    def ok(self, lane_id):
        return {"status": "OK", "exit": 0, "error": None, "out": str(self.lanes() / f"{lane_id}.jsonl")}

    def test_terminate_kills_the_recorded_opencode_group(self):
        d = self.lanes()
        oc = subprocess.Popen([self.env["DEVTEAM_OC_BIN"], "run"], env=dict(self.env, FAKE_OC_SLEEP="30"),
                              start_new_session=True)
        self.addCleanup(_killpg_quiet, oc.pid)
        (d / "rev-r1.pgid").write_text(str(oc.pid))
        with mock.patch.dict(os.environ, self.env, clear=True):
            devteam.terminate_lane_process(d, "rev-r1")
        self.assertEqual(oc.wait(timeout=10), -signal.SIGKILL)
        self.assertFalse((d / "rev-r1.pgid").exists())

    def test_terminate_leaves_a_reused_pgid_alone(self):
        d = self.lanes()
        unrelated = subprocess.Popen(["sleep", "30"], start_new_session=True)
        self.addCleanup(_killpg_quiet, unrelated.pid)
        (d / "rev-r1.pgid").write_text(str(unrelated.pid))
        with mock.patch.dict(os.environ, self.env, clear=True):
            devteam.terminate_lane_process(d, "rev-r1")
        self.assertIsNone(unrelated.poll())
        self.assertFalse((d / "rev-r1.pgid").exists())
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_lanes.py' -k test_terminate_`
Expected: FAIL. `test_terminate_kills_the_recorded_opencode_group` fails with `subprocess.TimeoutExpired`, because the opencode group is never killed. `test_terminate_leaves_a_reused_pgid_alone` fails with `AssertionError: True is not false`, because the `.pgid` file is still there.

- [ ] **Step 3: Kill the recorded opencode group before the lane-run group**

In `dev-team-glm/scripts/devteam.py`, add this function right above `def terminate_lane_process(d, lane_id):`:

```python
def kill_lane_pgid(d, lane_id) -> bool:
    """Kill the `opencode` process group oc_harness recorded in lanes/<id>.pgid. opencode runs in its
    own session, so killing the lane-run group alone leaves it editing the recreated worktree. The group
    is killed only while its leader still runs the OpenCode binary (a reused pgid is left alone); the
    file is removed either way."""
    f = Path(d) / f"{lane_id}.pgid"
    try:
        pgid = int(f.read_text().strip())
    except (OSError, ValueError):
        return False
    name = os.path.basename(os.environ.get("DEVTEAM_OC_BIN") or "opencode")
    try:
        cmdline = subprocess.run(["ps", "-o", "command=", "-p", str(pgid)],
                                 text=True, capture_output=True).stdout
    except OSError:
        cmdline = ""
    killed = False
    if pgid > 1 and name and name in cmdline:
        try:
            os.killpg(pgid, signal.SIGKILL)
            killed = True
        except OSError:
            pass
    try:
        f.unlink()
    except OSError:
        pass
    return killed
```

In `terminate_lane_process`, make `kill_lane_pgid(d, lane_id)` the first statement after the docstring, before `pid_file = d / f"{lane_id}.pid"`:

```python fragment
    kill_lane_pgid(d, lane_id)
    pid_file = d / f"{lane_id}.pid"
```

Replace `clear_own_pid_file` so a finished lane-run also drops its `.pgid`. It only does this while it still owns the pid file.

```python
def clear_own_pid_file(d, lane_id):
    """Drop lanes/<id>.pid (and the opencode .pgid) once this process is done with them, but only if the
    pid file still holds our own pid — a relaunch may already have overwritten it with a newer lane-run's."""
    pid_file = d / f"{lane_id}.pid"
    try:
        if int(pid_file.read_text().strip()) == os.getpid():
            pid_file.unlink()
            (d / f"{lane_id}.pgid").unlink()
    except (OSError, ValueError):
        pass
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_lanes.py' -k test_terminate_ -k LaneProcessGroupTest`
Expected: PASS (`OK`, 4 tests)

- [ ] **Step 5: Write the failing tests for the per-role stall (DE3)**

Add these methods inside `LaneLifecycleTest`:

```python fragment
    def test_reviewer_lane_gets_the_reviewer_stall(self):
        self.write_spec("review-r1", "code-reviewer", False)
        seen, _ = self.run_lane("review-r1", [self.ok("review-r1")])
        self.assertEqual(seen[0]["stall"], oc_harness.STALL_BY_ROLE["code-reviewer"])
        self.assertEqual(seen[0]["stall"], 600)

    def test_programmer_lane_gets_the_programmer_stall(self):
        self.devteam("dispatch", "S1")
        self.write_spec("S1", "programmer", True)
        seen, _ = self.run_lane("S1", [self.ok("S1")])
        self.assertEqual(seen[0]["stall"], 900)
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_lanes.py' -k _stall`
Expected: FAIL with `KeyError: 'stall'` in both tests

- [ ] **Step 7: Set the stall from the role in `cmd_lane_run`**

In `cmd_lane_run`, right after the statement that builds the `lane = {"id": spec["id"], ...}` dict, before `if not spec.get("writer"):`, add:

```python fragment
    lane["stall"] = oc_harness.lane_stall(dict(lane, role=spec["agent"]))
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_lanes.py' -k _stall`
Expected: PASS (`OK`, 2 tests)

- [ ] **Step 9: Write the failing tests for "error with no commit blocks at once" (DE14)**

Add these methods inside `LaneLifecycleTest`:

```python fragment
    def test_lane_error_line_formats_v2_and_v1_errors(self):
        v2 = {"status": "ERROR", "error": {"type": "provider.rate-limit", "message": "429 Too Many Requests"}}
        v1 = {"status": "FAIL", "error": {"name": "APIError", "data": {"message": "Rate limit", "statusCode": 429}}}
        self.assertEqual(devteam.lane_error_line("L1", v2), "LANE L1: ERROR provider.rate-limit 429 Too Many Requests")
        self.assertEqual(devteam.lane_error_line("L2", v1), "LANE L2: FAIL APIError Rate limit")
        self.assertEqual(devteam.lane_error_line("L3", {"status": "STALL", "error": "no output for 900s"}),
                         "LANE L3: STALL no output for 900s")

    def test_writer_error_without_commit_blocks_without_reruns(self):
        self.devteam("dispatch", "S1")
        self.write_spec("S1", "programmer", True)
        err = {"status": "ERROR", "exit": 1, "out": str(self.lanes() / "S1.jsonl"),
               "error": {"type": "provider.rate-limit", "message": "429 Too Many Requests"}}
        seen, gates = self.run_lane("S1", [err])
        self.assertEqual(len(seen), 1)
        self.assertEqual(gates, [])
        note = json.loads(self.state("slices", "S1.blocked").read_text())["note"]
        self.assertIn("LANE S1: ERROR provider.rate-limit 429 Too Many Requests", note)
        self.assertFalse(self.state("slices", "S1.done").exists())
```

- [ ] **Step 10: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_lanes.py' -k lane_error_line -k without_commit`
Expected: FAIL. `test_lane_error_line_formats_v2_and_v1_errors` fails with `AttributeError: module 'devteam' has no attribute 'lane_error_line'`. `test_writer_error_without_commit_blocks_without_reruns` fails with `AssertionError: Lists differ`, because the stop gate still ran.

- [ ] **Step 11: Add `lane_error_line` and stop when an errored run left no commit**

Add this function right above `def cmd_lane_run(a):`:

```python
def lane_error_line(lane_id, r):
    """One line per lane error: `LANE <id>: <status> <error.type> <message>`. Handles the v2 error
    event ({type, message}), the v1 one ({name, data.message}) and a plain string."""
    err = r.get("error")
    if isinstance(err, dict):
        data = err.get("data") if isinstance(err.get("data"), dict) else {}
        etype = str(err.get("type") or err.get("name") or "")
        msg = str(err.get("message") or data.get("message") or "")
    else:
        etype, msg = "", str(err or r.get("last_event") or "no error event")
    return " ".join(x for x in (f"LANE {lane_id}: {r.get('status')}", etype, msg) if x)[:300]
```

In the writer branch of `cmd_lane_run`, add `base = slice_state(st, spec["id"]).get("base_sha") or ""` right before `for _ in range(MAX_LANE_RUNS):`. Inside the loop, add the check right after the line `r = oc_harness.run_lanes([lane], str(d), width=1, binary=binary)[0]`:

```python fragment
        base = slice_state(st, spec["id"]).get("base_sha") or ""
        for _ in range(MAX_LANE_RUNS):
            lane["brief"] = brief + note
            r = oc_harness.run_lanes([lane], str(d), width=1, binary=binary)[0]
            if r.get("status") != "OK" and base and git(["rev-parse", "HEAD"], wt, check=False) == base:
                line = lane_error_line(spec["id"], r)
                out(line)
                if not slice_marker_exists(root, spec["id"]):
                    slice_blocked_marker(root, wt, spec["id"], f"lane-run failed: {line} (no commit on the "
                                                               "branch, so a rerun would fail the same way)")
                return
```

The `return` sits inside the existing `try`, so the `finally` still clears the pid file and writes `.end`.

- [ ] **Step 12: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_lanes.py' -k lane_error_line -k without_commit -k LaneRunTest`
Expected: PASS (`OK`, all selected tests)

- [ ] **Step 13: Write the failing tests for relaunch hygiene (DE13)**

Add these methods inside `LaneLifecycleTest`:

```python fragment
    def test_lane_run_clears_stale_results_before_running(self):
        d = self.lanes()
        self.write_spec("review-r1", "code-reviewer", False)
        for ext, body in ((".done", '{"status": "FAIL"}'), (".end", "1"), (".pgid", "999999")):
            (d / f"review-r1{ext}").write_text(body)
        self.run_lane("review-r1", [self.ok("review-r1")])
        for ext in (".done", ".end", ".pgid", ".pid"):
            self.assertFalse((d / f"review-r1{ext}").exists(), ext)

    def test_relaunch_hint_is_a_detached_python3_command(self):
        root = Path(self.repo)
        sig = {"throttle": [], "down": [("review", "review-r1", "ERROR: boom", "1", time.time())],
               "spawn_fail": [], "spawned": {}}
        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(devteam, "is_opencode", return_value=True), \
                mock.patch.object(devteam, "lane_signals", return_value=sig):
            st = devteam.load_state(root)
            st["reviews"] = {"r1": {"status": "dispatched"}}
            text = "\n".join(devteam.govern(root, st, 0))
        self.assertIn("LANE DOWN review-r1", text)
        self.assertIn("nohup python3 ", text)
        self.assertIn("lane-run review-r1 > ", text)
```

- [ ] **Step 14: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_lanes.py' -k stale_results -k relaunch_hint`
Expected: FAIL. `test_lane_run_clears_stale_results_before_running` fails with `AssertionError: True is not false : .done`. `test_relaunch_hint_is_a_detached_python3_command` fails with `AssertionError: 'nohup python3 ' not found in`.

- [ ] **Step 15: Make lane-run self-cleaning and fix the hint**

In `cmd_lane_run`, right after `d = lanes_dir(root)`, add the lines below. A lane-run started by hand has no pid file, so it writes its own; otherwise `wait` would not see it as live.

```python fragment
    d = lanes_dir(root)
    for ext in (".done", ".end"):
        try:
            (d / f"{a.lane_id}{ext}").unlink()
        except OSError:
            pass
    if not (d / f"{a.lane_id}.pid").exists():
        write_atomic(d / f"{a.lane_id}.pid", str(os.getpid()))
```

In `govern`, the OpenCode `LANE DOWN` branch builds a hint for non-slice lanes: two comment lines, then the f-string `"\n  → relaunch it in the background: "` followed by `` f"`lane-run {name} > ... 2>&1 &`" ``. Replace those two comment lines and both f-string lines, up to and including the closing `))`, with:

```python fragment
                            # nohup + a redirected, backgrounded python3 detaches the lane from the tool's
                            # shell and pipes; lane-run clears the stale .done/.end itself before running
                            f"\n  → relaunch it detached: `nohup python3 {q(str(Path(__file__).resolve()))} "
                            f"lane-run {name} > {q(str(lanes_dir(root) / (name + '.log')))} 2>&1 &`"))
```

- [ ] **Step 16: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_lanes.py' -k stale_results -k relaunch_hint`
Expected: PASS (`OK`, 2 tests)

- [ ] **Step 17: Write the failing tests for dead and idle lanes (DE15, DE10)**

Add these methods inside `LaneLifecycleTest`:

```python fragment
    def test_signal_killed_lane_is_reported_down_once(self):
        d = self.lanes()
        self.write_spec("rev-r7", "code-reviewer", False)
        (d / "rev-r7.pid").write_text(str(_reaped_pid()))
        with mock.patch.dict(os.environ, self.env, clear=True):
            st = devteam.load_state(Path(self.repo))
            first = devteam.lane_signals(Path(self.repo), st)["down"]
            second = devteam.lane_signals(Path(self.repo), st)["down"]
        self.assertEqual([(k, n) for k, n, *_ in first], [("review", "rev-r7")])
        self.assertIn("killed by a signal", first[0][2])
        self.assertEqual([n for _, n, *_ in second], [])
        self.assertTrue((d / "rev-r7.end").exists())

    def test_lane_with_a_result_is_not_dead(self):
        d = self.lanes()
        self.write_spec("rev-r8", "code-reviewer", False)
        (d / "rev-r8.pid").write_text(str(_reaped_pid()))
        (d / "rev-r8.done").write_text('{"status": "OK"}')
        self.assertEqual(devteam.dead_lanes(d), [])

    def test_wait_returns_at_once_when_no_lane_is_running(self):
        start = time.monotonic()
        out = self.devteam("wait", "--timeout", "30", DEVTEAM_HARNESS="opencode")
        self.assertLess(time.monotonic() - start, 10)
        self.assertIn("WAIT: no lane is running", out)
        self.assertIn("NEXT: devteam next", out)

    def test_wait_reports_a_dead_lane(self):
        d = self.lanes()
        self.write_spec("rev-r3", "code-reviewer", False)
        (d / "rev-r3.pid").write_text(str(_reaped_pid()))
        start = time.monotonic()
        out = self.devteam("wait", "--timeout", "30", DEVTEAM_HARNESS="opencode")
        self.assertLess(time.monotonic() - start, 10)
        self.assertIn("rev-r3 died", out)
        self.assertIn("NEXT: devteam next", out)

    def test_wait_keeps_waiting_while_a_lane_is_alive(self):
        d = self.lanes()
        self.write_spec("rev-r4", "code-reviewer", False)
        alive = subprocess.Popen(["sleep", "30"], start_new_session=True)
        self.addCleanup(_killpg_quiet, alive.pid)
        (d / "rev-r4.pid").write_text(str(alive.pid))
        start = time.monotonic()
        out = self.devteam("wait", "--timeout", "2", DEVTEAM_HARNESS="opencode")
        self.assertGreaterEqual(time.monotonic() - start, 2)
        self.assertIn("WAIT: nothing finished in 2s", out)
```

- [ ] **Step 18: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_lanes.py' -k dead -k no_lane_is_running -k while_a_lane_is_alive`
Expected: FAIL. `test_signal_killed_lane_is_reported_down_once` fails with `AssertionError: Lists differ: [] != [('review', 'rev-r7')]`. `test_lane_with_a_result_is_not_dead` fails with `AttributeError: module 'devteam' has no attribute 'dead_lanes'`. `test_wait_returns_at_once_when_no_lane_is_running` and `test_wait_reports_a_dead_lane` fail with `AssertionError` on the elapsed time. `test_wait_keeps_waiting_while_a_lane_is_alive` already passes.

- [ ] **Step 19: Add live/dead lane detection and use it in `lane_signals` and `wait`**

Add these functions right below `lane_process_finished`:

```python
def _pid_alive(pid) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True                                   # EPERM: the process exists, it is just not ours
    return True


def lane_pids(d):
    """[(lane_id, pid)] for every lanes/<id>.pid that parses."""
    res = []
    for pf in sorted(Path(d).glob("*.pid")):
        try:
            res.append((pf.name[:-len(".pid")], int(pf.read_text().strip())))
        except (OSError, ValueError):
            continue
    return res


def live_lanes(d):
    """Lane ids whose recorded lane-run process is still running."""
    return [lane_id for lane_id, pid in lane_pids(d) if _pid_alive(pid)]


def dead_lanes(d):
    """[(lane_id, pid)] of lanes killed by a signal: the recorded pid is gone and the lane left no `.end`
    and no result (`lanes/<id>.done` for a non-writer, `slices/<id>.done|.blocked` for a writer)."""
    d = Path(d)
    slices = d.parent / "slices"
    found = []
    for lane_id, pid in lane_pids(d):
        if (d / f"{lane_id}.end").exists() or _pid_alive(pid):
            continue
        try:
            writer = bool(json.loads((d / f"{lane_id}.lane.json").read_text()).get("writer"))
        except (OSError, ValueError, AttributeError):
            writer = False
        if writer:
            if (slices / f"{lane_id}.done").exists() or (slices / f"{lane_id}.blocked").exists():
                continue
        elif (d / f"{lane_id}.done").exists():
            continue
        found.append((lane_id, pid))
    return found
```

In `lane_signals`, report each dead lane once, just before its final `return sig`. The loop over `*.done` ends with `sig["down"].append((kind, f.stem, text, str(int(mtime)), mtime))`. The `.end` it writes stops `wait` and later scans from reporting the lane again. Make the tail of the function read:

```python fragment
        sig["down"].append((kind, f.stem, text, str(int(mtime)), mtime))  # (kind, name, text, id, ts) — scan_transcripts' shape
    for lane_id, pid in dead_lanes(d):
        sig["down"].append((_lane_kind(st, lane_id), lane_id,
                            f"DOWN: killed by a signal (pid {pid} gone, no result and no end marker)",
                            f"pid{pid}", time.time()))
        write_atomic(d / f"{lane_id}.end", "killed")
    return sig
```

Replace `cmd_wait` with:

```python
def cmd_wait(a):
    """Block up to --timeout seconds until a lane finishes, then point the Conductor at `next`. On
    OpenCode it also returns at once when a lane died by a signal, or when no lane is running at all."""
    root = find_root()
    try:
        st = load_state(root)
    except DevteamError:
        st = None
    oc = is_opencode()
    d = lanes_dir(root)
    start = lane_marks(root)
    deadline = time.monotonic() + max(0, a.timeout)
    found = bool(st and any(finished_lanes(root, st)))
    msg = "WAIT: a lane finished"
    while not found:
        if oc:
            dead = dead_lanes(d)
            if dead:
                found, msg = True, ("WAIT: lane " + ", ".join(lane_id for lane_id, _ in dead)
                                    + " died without a result (LANE DOWN)")
                break
            if not live_lanes(d):
                found, msg = True, "WAIT: no lane is running"
                break
        if time.monotonic() >= deadline:
            break
        time.sleep(0.5)
        cur = lane_marks(root)
        found = any(start.get(k) != v for k, v in cur.items())
    out(msg if found else f"WAIT: nothing finished in {a.timeout}s (lanes keep running)",
        "NEXT: devteam next")
```

- [ ] **Step 20: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_lanes.py'`
Expected: PASS (`OK`, every test in the module, including `WaitTest` and `LaneProcessGroupTest`)

- [ ] **Step 21: Run the full suite and the dev-team selftest**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: final line `OK`

Run: `env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh`
Expected: `passed=` at least 324 and `failed=` at most 5 (only the known macOS failures)

- [ ] **Step 22: Commit**

```bash
cd ..
git add glm-skills/dev-team-glm/scripts/devteam.py glm-skills/_shared/tests/test_devteam_oc_lanes.py
git commit -m "fix(dev-team): OpenCode lane lifecycle: kill the opencode pgid, per-role stall, block errored no-commit lanes, report dead lanes, wait returns when idle"
```

---

### T13: devteam.py detached checkpoint and resume command [P]

**Depends:** —

**Runs after:** T12 (same files)

**Interfaces:**
- Produces: `devteam.py resume <slice id> [--note TEXT]`; `.slice/stop_blocks`; `.done`; `.blocked`; `NEXT:`; `launch_lane`; `wait`; `next`

**Files:**
- Modify: `glm-skills/dev-team-glm/scripts/devteam.py`
- Test: `glm-skills/_shared/tests/test_devteam_oc_resume.py`

T12 edits `devteam.py` before this task (lane launch, stall, harness detection). Every edit below is anchored on code text rather than line numbers: find the quoted anchor in the file as it stands after T12, and keep whatever T12 added around it.

- [ ] **Step 1: Write the failing tests for `resume`**

Create `glm-skills/_shared/tests/test_devteam_oc_resume.py`:

```python
"""dev-team on OpenCode: `devteam.py resume <slice id> [--note TEXT]` relaunches a fresh lane in the
slice's existing worktree, and the checkpoint runs detached so `wait`/`next` collect it."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "dev-team-glm" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import devteam  # noqa: E402

PLAN = {
    "request": "resume fixture",
    "commands": {"test": "echo checkpoint-ran"},
    "slices": [{"id": "S1", "title": "one", "files": ["src/a.py", "tests/test_a.py"],
                "criteria": ["c1"]}],
}


class RunFixture(unittest.TestCase):
    """A real git repo with an initialised dev-team run, driven in-process through devteam.main."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name).resolve()
        self.repo = base / "repo"
        self.repo.mkdir()
        tx = base / "tx"
        tx.mkdir()
        self.env = mock.patch.dict(os.environ, {"DEVTEAM_TRANSCRIPTS_DIR": str(tx),
                                                "DEVTEAM_PROVIDER": "glm",
                                                "DEVTEAM_GOVERNOR": "off"})
        self.env.start()
        self.cwd = os.getcwd()
        os.chdir(self.repo)
        self.git("init", "-q", "-b", "main")
        self.git("commit", "-q", "--allow-empty", "-m", "init")
        plan = base / "plan.json"
        plan.write_text(json.dumps(PLAN))
        rc, text = self.run_cli("init", str(plan))
        self.assertEqual(rc, 0, text)
        self.root = devteam.find_root()

    def tearDown(self):
        os.chdir(self.cwd)
        self.env.stop()
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                        "-c", "commit.gpgsign=false"] + list(args),
                       cwd=str(self.repo), check=True, capture_output=True)

    def run_cli(self, *args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = devteam.main(list(args))
        return rc, buf.getvalue()

    def dispatch_with_worktree(self):
        st = devteam.load_state(self.root)
        devteam.do_dispatch(self.root, st, ["S1"])
        st = devteam.load_state(self.root)
        wt = devteam.lane_worktree(self.root, st, "S1")
        (wt / ".slice").mkdir(exist_ok=True)
        (wt / ".slice" / "stop_blocks").write_text("2")
        return wt


class ResumeTest(RunFixture):
    def test_resume_relaunches_lane_in_existing_worktree(self):
        wt = self.dispatch_with_worktree()
        devteam.slice_blocked_marker(self.root, wt, "S1", "which contract?")
        devteam.write_atomic(devteam.marker_file(self.root, "S1", "done"), "{}")
        with mock.patch.object(devteam, "is_opencode", return_value=True), \
                mock.patch.object(devteam, "launch_lane", return_value=4242) as launch:
            rc, text = self.run_cli("resume", "S1", "--note", "use contract C1")
        self.assertEqual(rc, 0, text)
        launch.assert_called_once()
        args, kwargs = launch.call_args
        self.assertEqual(args[2], "S1")
        self.assertEqual(args[3], "programmer")
        self.assertIn("claim S1", args[5])
        self.assertEqual(kwargs.get("note"), "use contract C1")
        self.assertFalse((wt / ".slice" / "stop_blocks").exists())
        self.assertIsNone(devteam.read_marker(self.root, "S1", "done"))
        self.assertIsNone(devteam.read_marker(self.root, "S1", "blocked"))
        self.assertIn("RESUMED S1", text)
        self.assertIn("pid 4242", text)
        self.assertRegex(text, r"(?m)^NEXT: python3 .* wait$")
        s = devteam.load_state(self.root)["slices"]["S1"]
        self.assertEqual(s["status"], "inflight")
        self.assertIsNone(s["rejected"])
        self.assertEqual(s["history"][-1]["event"], "resume")
        self.assertEqual(s["history"][-1]["note"], "use contract C1")

    def test_resume_refused_off_opencode(self):
        self.dispatch_with_worktree()
        with mock.patch.object(devteam, "is_opencode", return_value=False), \
                mock.patch.object(devteam, "launch_lane") as launch:
            rc, text = self.run_cli("resume", "S1", "--note", "x")
        self.assertEqual(rc, 1)
        self.assertIn("SendMessage", text)
        launch.assert_not_called()

    def test_resume_needs_the_existing_worktree(self):
        st = devteam.load_state(self.root)
        devteam.do_dispatch(self.root, st, ["S1"])
        with mock.patch.object(devteam, "is_opencode", return_value=True), \
                mock.patch.object(devteam, "launch_lane") as launch:
            rc, text = self.run_cli("resume", "S1")
        self.assertEqual(rc, 1)
        self.assertIn("retry S1", text)
        launch.assert_not_called()

    def test_resume_refuses_a_slice_that_is_not_in_flight(self):
        with mock.patch.object(devteam, "is_opencode", return_value=True), \
                mock.patch.object(devteam, "launch_lane") as launch:
            rc, text = self.run_cli("resume", "S1")
        self.assertEqual(rc, 1)
        self.assertIn("pending", text)
        launch.assert_not_called()


class ResumeHelpersTest(unittest.TestCase):
    def test_resume_brief_appends_note(self):
        out = devteam.resume_brief("CLAIMED S1\n# Briefing\n", "  use contract C1  ")
        self.assertTrue(out.startswith("CLAIMED S1\n# Briefing"))
        self.assertIn("## Resume note from the Conductor", out)
        self.assertTrue(out.rstrip().endswith("use contract C1"))

    def test_resume_brief_without_note_is_unchanged(self):
        self.assertEqual(devteam.resume_brief("brief\n", ""), "brief\n")
        self.assertEqual(devteam.resume_brief("brief\n", "   "), "brief\n")

    def test_launch_lane_records_note_in_spec(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(devteam.subprocess, "Popen") as popen:
            popen.return_value.pid = os.getpid()
            devteam.launch_lane(Path(td), {"provider": "glm"}, "S9", "programmer", "",
                                "python3 x claim S9", note="fix the footprint")
            spec = json.loads((devteam.lanes_dir(td) / "S9.lane.json").read_text())
        self.assertEqual(spec["note"], "fix the footprint")

    def test_launch_lane_note_defaults_to_empty(self):
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(devteam.subprocess, "Popen") as popen:
            popen.return_value.pid = os.getpid()
            devteam.launch_lane(Path(td), {"provider": "glm"}, "S8", "programmer", "",
                                "python3 x claim S8")
            spec = json.loads((devteam.lanes_dir(td) / "S8.lane.json").read_text())
        self.assertEqual(spec["note"], "")

    def test_resume_hint_names_the_command(self):
        hint = devteam.resume_hint({"script": "/x/devteam.py"}, "S1")
        self.assertIn("python3 /x/devteam.py resume S1 --note", hint)
        self.assertIn("same worktree", hint)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_resume.py'`
Expected: FAIL, ending `FAILED (errors=9)`. The four `ResumeTest` cases error with `SystemExit: 2` (argparse: `invalid choice: 'resume'`). The `resume_brief`/`resume_hint` cases error with `AttributeError: module 'devteam' has no attribute 'resume_brief'` (or `'resume_hint'`). The two `launch_lane` cases error with `TypeError: launch_lane() got an unexpected keyword argument 'note'` or `KeyError: 'note'`.

- [ ] **Step 3: Let `launch_lane` carry a resume note into the lane spec**

In `glm-skills/dev-team-glm/scripts/devteam.py`, change the `launch_lane` signature line (anchor: `def launch_lane(root, st, lane_id, agent, model, prompt`) so it takes a keyword `note` that defaults to empty. Add a `"note": note` entry to the `spec` dict it writes to `<lane_id>.lane.json`. Leave everything else in the function exactly as T12 left it:

```python fragment
def launch_lane(root, st, lane_id, agent, model, prompt, note="") -> int:
    """Start `devteam.py lane-run <lane_id>` as a detached process; return its pid. `note` (from
    `resume --note`) is stored in the lane spec and appended to a writer's brief by lane-run."""
    # ... unchanged body up to the spec dict ...
    spec = {"id": lane_id, "agent": OC_AGENTS.get(agent, agent), "model": oc_model(st, agent, model),
            "effort": oc_effort(st, agent), "prompt": prompt, "writer": agent in WRITER_AGENTS,
            "note": note}
    # ... any keys T12 added to spec stay; the rest of the body is unchanged ...
```

- [ ] **Step 4: Append the note to the writer brief in `lane-run`**

In `cmd_lane_run`, replace the line

```python fragment
        brief, note = claim.stdout, ""
```

with

```python fragment
        brief, note = resume_brief(claim.stdout, spec.get("note") or ""), ""
```

- [ ] **Step 5: Add `resume_brief`, `resume_hint` and `cmd_resume`**

Insert these three functions directly after the end of `cmd_wait` (before `def print_dispatch`):

```python
def resume_brief(brief, note):
    """The claim briefing plus the Conductor's `resume --note` text (unchanged when there is none)."""
    note = (note or "").strip()
    if not note:
        return brief
    return (brief.rstrip("\n") + "\n\n## Resume note from the Conductor\n"
            "You are resuming this slice in its existing worktree: your earlier commits are kept. "
            "Act on this note first, then finish the procedure above.\n" + note + "\n")


def resume_hint(st, sid):
    """What to do instead of SendMessage on OpenCode, where the lane process has already exited."""
    return (f"  → OpenCode: the {sid} lane has exited, so SendMessage cannot reach it. Answer with "
            f"`python3 {q(st['script'])} resume {sid} --note \"<the answer or the fix>\"` "
            "(fresh lane, same worktree, commits kept); `retry " + sid + "` is the cold alternative.")


def cmd_resume(a):
    """`devteam.py resume <slice id> [--note TEXT]`: OpenCode's answer to BLOCKED / REJECTED. The lane
    process has exited, so a fresh lane is launched in the slice's existing worktree (its commits are
    kept) with the note appended to the brief. The Stop-gate counter `.slice/stop_blocks` is reset
    and the stale `.done`/`.blocked` markers are cleared first, so `wait`/`next` only see the new run."""
    root = find_root()
    st = load_state(root)
    sid = a.id
    s = slice_state(st, sid)
    if not is_opencode():
        raise DevteamError(f"`resume` relaunches an OpenCode lane; on Claude Code the {sid} agent is still "
                           f"reachable — SendMessage it the note (warm context), or `retry {sid}` (cold)")
    if s["status"] != "inflight":
        raise DevteamError(f"{sid} is {s['status']} — only an in-flight slice can be resumed "
                           f"(`retry {sid}` re-queues a failed or conflicted one)")
    if s.get("mode") == "research":
        raise DevteamError(f"{sid} is a research slice with no worktree — `retry {sid}` relaunches it")
    wt = state_dir(root) / "wt" / sid
    if not (wt / ".git").exists():
        raise DevteamError(f"{sid}: no worktree at {wt} — nothing to resume; `retry {sid}` starts a fresh attempt")
    note = (a.note or "").strip()
    try:
        (wt / ".slice" / "stop_blocks").unlink()     # guard.py's Stop-gate block counter starts over
    except OSError:
        pass
    clear_markers(root, sid)
    s["rejected"] = None
    s["dispatched"] = now()                           # older LANE DOWN signals belong to the previous run
    s["history"].append({"t": now(), "event": "resume", "note": note[:200]})
    save_state(root, st)
    agent, model, label = dispatch_route(st, s, s["mode"])
    sp = q(st["script"])
    pid = launch_lane(root, st, sid, agent, model, f"python3 {sp} claim {sid}", note=note)
    out(f"RESUMED {sid} → {agent} lane (pid {pid}, {label}) in {wt}"
        + (" with your note appended to the brief" if note else "")
        + "; stop-gate counter reset, stale .done/.blocked markers cleared",
        f"NEXT: python3 {sp} wait")
```

- [ ] **Step 6: Register the command and document it**

Add `"resume"` to `LOCKED_CMDS`. Anchor: the set that ends with `"status", "finish", "review-pr"}`. After the edit it ends with:

```python fragment
               "status", "finish", "review-pr", "resume"}
```

In `main`, directly after the `retry` parser line (anchor: `pr = sp.add_parser("retry");`), add:

```python fragment
    pr = sp.add_parser("resume"); pr.add_argument("id"); pr.add_argument("--note", default=""); pr.set_defaults(fn=cmd_resume)
```

In the module docstring, directly after the line that starts with `  retry <id>`, add:

```text
  resume <id> [--note TEXT] OpenCode: relaunch a fresh lane in the slice's existing worktree with the
                            note appended to its brief (the answer to BLOCKED / REJECTED; commits kept)
```

- [ ] **Step 7: Point BLOCKED and REJECTED messages at `resume` on OpenCode**

In `cmd_next`, replace the loop that starts with `for sid, note in blocked:` with:

```python fragment
    for sid, note in blocked:
        clear_markers(root, sid)     # printed once; a still-blocked agent writes it again on its next stop
        out(f"BLOCKED {sid}: {note or '(no note in the report: read the last message of that agent)'}",
            resume_hint(st, sid) if is_opencode() else
            f"  → SendMessage the {sid} agent the answer (plan/contracts) and it resumes in its worktree; "
            f"if only the user can answer, ask now and keep everything else running.")
```

In `do_integrate`, replace

```python fragment
        try:
            results.append(integrate_one(root, st, sid, remove=remove))
        except DevteamError as e:
```

with

```python fragment
        try:
            r = integrate_one(root, st, sid, remove=remove)
            if "SendMessage" in r and is_opencode():
                r += "\n" + resume_hint(st, sid)
            results.append(r)
        except DevteamError as e:
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_resume.py'`
Expected: PASS: `Ran 9 tests` then `OK`

- [ ] **Step 9: Write the failing tests for the detached checkpoint**

Append this class to `glm-skills/_shared/tests/test_devteam_oc_resume.py`, just above the `if __name__ == "__main__":` line:

```python
class CheckpointTest(RunFixture):
    def test_opencode_checkpoint_runs_detached_and_is_collected(self):
        with mock.patch.object(devteam, "is_opencode", return_value=True):
            rc, text = self.run_cli("checkpoint")
            self.assertEqual(rc, 0, text)
            self.assertIn("running detached", text)
            self.assertNotIn("run_in_background", text)
            self.assertRegex(text, r"(?m)^NEXT: python3 .* wait$")
            st = devteam.load_state(self.root)
            self.assertIsInstance(st["checkpoint_pending"].get("pid"), int)
            done = devteam.lanes_dir(self.root) / "checkpoint-1.done"
            deadline = time.monotonic() + 15
            while not done.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertTrue(done.exists(), "detached checkpoint never wrote its .done")
            self.assertTrue(devteam.checkpoint_finished(self.root, st))
            self.assertFalse(devteam.checkpoint_running(self.root, st))
            rc, text = self.run_cli("wait", "--timeout", "3")
            self.assertIn("WAIT: a lane finished", text)
            lines = devteam.harvest_checkpoint(self.root, st)
        self.assertIn("PASS (exit 0)", lines[0])
        self.assertFalse(done.exists())
        self.assertFalse((devteam.lanes_dir(self.root) / "checkpoint-1.pid").exists())
        log = devteam.state_dir(self.root) / "logs" / "checkpoint-1.log"
        self.assertIn("checkpoint-ran", log.read_text())

    def test_claude_checkpoint_still_prints_background_command(self):
        with mock.patch.object(devteam, "is_opencode", return_value=False):
            rc, text = self.run_cli("checkpoint")
        self.assertEqual(rc, 0, text)
        self.assertIn("run_in_background: true", text)
        self.assertFalse((devteam.lanes_dir(self.root) / "checkpoint-1.done").exists())
        st = devteam.load_state(self.root)
        self.assertTrue(devteam.checkpoint_running(self.root, st))
```

- [ ] **Step 10: Run the tests to verify the new ones fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_resume.py'`
Expected: FAIL, ending `FAILED (failures=1, errors=1)`. `test_opencode_checkpoint_runs_detached_and_is_collected` fails with `AssertionError: 'running detached' not found in ...`. `test_claude_checkpoint_still_prints_background_command` errors with `AttributeError: module 'devteam' has no attribute 'checkpoint_running'`.

- [ ] **Step 11: Add the detached launcher and the finished/running probes**

Insert these three functions directly after `harvest_checkpoint` (before `def cmd_next`):

```python
def launch_checkpoint(root, n, wt, cmd, log) -> int:
    """Run the checkpoint command detached (own session, stdin closed) like `launch_lane`, so no tool
    timeout can kill it. The shell appends EXIT=<code> to the log, then writes lanes/checkpoint-<n>.done,
    which `wait` sees through lane_marks and `next` collects through harvest_checkpoint."""
    d = lanes_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    done, tmp = d / f"checkpoint-{n}.done", d / f"checkpoint-{n}.done.tmp"
    for p in (done, tmp):
        try:
            p.unlink()
        except OSError:
            pass
    log.parent.mkdir(parents=True, exist_ok=True)
    script = (f"({cmd}) > {q(log)} 2>&1; rc=$?; echo \"EXIT=$rc\" >> {q(log)}; "
              f"echo \"$rc\" > {q(tmp)} && mv {q(tmp)} {q(done)}")
    try:
        proc = subprocess.Popen(["sh", "-c", script], cwd=str(wt), stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    except OSError as e:
        raise DevteamError(f"could not start checkpoint {n}: {e}")
    write_atomic(d / f"checkpoint-{n}.pid", str(proc.pid))
    return proc.pid


def checkpoint_finished(root, st):
    """True when the pending checkpoint's log already carries its EXIT=<code> line."""
    pending = (st or {}).get("checkpoint_pending")
    if not isinstance(pending, dict):
        return False
    log = state_dir(root) / "logs" / f"checkpoint-{pending['n']}.log"
    try:
        return bool(EXIT_RE.search(log.read_text(errors="replace")))
    except OSError:
        return False


def checkpoint_running(root, st):
    """A checkpoint is pending and has not written its exit code yet (it counts as a live lane)."""
    return isinstance((st or {}).get("checkpoint_pending"), dict) and not checkpoint_finished(root, st)
```

- [ ] **Step 12: Launch the checkpoint detached on OpenCode**

In `cmd_checkpoint`, replace everything from the line `log = state_dir(root) / "logs" / f"checkpoint-{n}.log"` to the end of the function with:

```python fragment
    log = state_dir(root) / "logs" / f"checkpoint-{n}.log"
    if pol(st, "gate") != "full":   # per-slice lint/type-check/build were scoped or deferred — run them here
        cmd = full_gate_cmd(st) or "echo 'no commands configured'"
    else:
        cmd = cmd_value(st["commands"], "test") or "echo 'no test command configured'"
    full = " — FULL GATE (test && lint && typecheck && build)" if pol(st, "gate") != "full" else ""
    if is_opencode():
        # OpenCode v1's bash tool has no background mode and kills a >120 s suite, which left
        # checkpoint_pending stuck: run it detached like a lane, and let `wait`/`next` collect it
        pid = launch_checkpoint(root, n, wt, cmd, log)
        st["checkpoint_pending"]["pid"] = pid
        save_state(root, st)
        out(f"CHECKPOINT {n} on snapshot {sha[:9]}{full}: running detached (pid {pid}), log {log}",
            "Nothing to report afterwards: `wait` wakes you when it ends and the next `next` reads its exit code.",
            f"NEXT: python3 {q(st['script'])} wait")
        return
    out(f"CHECKPOINT {n} on snapshot {sha[:9]}{full}: run in the BACKGROUND (Bash run_in_background: true):",
        f"  cd {q(wt)} && ({cmd}) > {q(log)} 2>&1; echo \"EXIT=$?\" >> {q(log)}; tail -5 {q(log)}",
        "Nothing to report afterwards: the next `next` reads the exit code out of that log itself.")
```

- [ ] **Step 13: Collect the checkpoint in `harvest_checkpoint` and `wait`**

In `harvest_checkpoint`, directly after the line `remove_worktree(root, pending.get("wt"))`, add:

```python fragment
    for ext in (".done", ".pid"):                   # the detached run's markers (OpenCode)
        try:
            (lanes_dir(root) / f"checkpoint-{pending['n']}{ext}").unlink()
        except OSError:
            pass
```

In `cmd_wait`, replace the initial-found expression

```python fragment
    found = bool(st and any(finished_lanes(root, st)))
```

with

```python fragment
    found = bool(st and (any(finished_lanes(root, st)) or checkpoint_finished(root, st)))
```

T12 may have given `cmd_wait` an early "no live lanes" return. If it did, count `checkpoint_running(root, st)` as a live lane in that check, so `wait` keeps waiting on a checkpoint that is still running. Nothing else needs to change for `wait` to wake up: `lanes/checkpoint-<n>.done` has no `.lane.json`, so `lane_marks` already treats it as a non-writer completion. Its content is a bare integer, and `lane_signals` skips any `.done` that is not a JSON object.

- [ ] **Step 14: Run the tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_devteam_oc_resume.py'`
Expected: PASS: `Ran 11 tests` then `OK`

- [ ] **Step 15: Run the full suite and the dev-team selftest**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: all 11 `test_devteam_oc_resume` tests pass, and the run has no failure or error that was not already failing before this task.

Run: `cd glm-skills && env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh`
Expected: the summary reports `passed=` 324 or more and `failed=` 5 or fewer (only the known macOS failures).

- [ ] **Step 16: Commit**

```bash
cd ..
git add glm-skills/dev-team-glm/scripts/devteam.py glm-skills/_shared/tests/test_devteam_oc_resume.py
git commit -m "feat(dev-team): resume command relaunches a lane in its worktree; detached OpenCode checkpoint"
```

---

### T14: dev-team selftest checks [P]

**Depends:** T08, T11, T13

**Interfaces:**
- Consumes: `devteam.py resume <slice id> [--note TEXT]`; `.slice/stop_blocks`; `.done`; `.blocked`; `NEXT:`; `launch_lane`; `wait`; `next`

**Files:**
- Modify: `glm-skills/dev-team-glm/scripts/selftest.sh:1159-1164`

All new checks go at the end of the file, after the OpenCode section. The anchor is the line `unset DEVTEAM_HARNESS DEVTEAM_PY`, which closes that section. Insert each block right after that line, or right after the block you added before it. Every block must stay above the final three lines:

```bash fragment
echo
echo "passed=$pass failed=$fail"
[ "$fail" -eq 0 ]
```

The block reuses these helpers already defined earlier in the file: `check`, `newrepo`, `D`, `$S`, `$G`, `$RA` (the "v3.2 adversarial round" repo), `$OCBIN` (the v1 stub `opencode` from the OpenCode section, which does real RED/GREEN commits only for slice `O1`) and `$OLDPATH`. Every check name starts with its spec ID (`DG4:`, `DG5:`, `DE1:`, `DE4:`, `DE6:`) so you can grep for it. The fixes these checks cover were made by the tasks this one depends on, so each new check should print `ok` on the first run. A `FAIL` means one of those fixes is missing. In that case stop and report which check failed. Do not weaken the check to make it pass.

- [ ] **Step 1: Add the DG4/DG5 read-only allow-list checks**

Insert this right after `unset DEVTEAM_HARNESS DEVTEAM_PY`:

```bash
echo "== OpenCode hardening DG4/DG5: read-only roles cannot write or exec through allow-listed tools"
roq() { printf '{"cwd":"%s","tool_input":{"command":%s}}' "$RA" "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$1")" | python3 "$G" bash-ro; }
roallow() { [[ "$(roq "$1")" == *"\"allow\""* ]]; }
ronotallow() { [[ "$(roq "$1")" != *"\"permissionDecision\": \"allow\""* ]]; }
check "DG4: plain git diff / git log / sort stay pre-approved for a reviewer" 'roallow "git diff HEAD" && roallow "git log -1" && roallow "sort src/a.js"'
check "DG4: git diff/log --output (a file write) is not pre-approved" 'ronotallow "git diff --output=/tmp/dg4 HEAD" && ronotallow "git log --output=notes.txt -1"'
check "DG4: git grep --open-files-in-pager (exec) is not pre-approved" 'ronotallow "git grep --open-files-in-pager=sh base"'
check "DG4: rg --pre (exec) is not pre-approved" 'ronotallow "rg --pre ./x.sh base src" && ronotallow "rg --pre=sh base src"'
check "DG4: uniq with an output file is not pre-approved" 'ronotallow "uniq src/a.js out.txt"'
check "DG4: sed w / e commands are not pre-approved" 'ronotallow "sed -n \"w out.txt\" src/a.js" && ronotallow "sed \"1e ls\" src/a.js"'
check "DG4: sort --compress-program (exec) is not pre-approved" 'ronotallow "sort --compress-program=sh src/a.js"'
mkdir -p "$RA/node_modules/.bin" && touch "$RA/node_modules/.bin/prettier"
check "DG5: a reviewer still runs the test runners for evidence" 'roallow "go test ./..." && roallow "make test"'
check "DG5: black / isort are not pre-approved for a reviewer" 'ronotallow "black src" && ronotallow "isort src"'
check "DG5: ruff --fix / ruff format are not pre-approved" 'ronotallow "ruff check --fix src" && ronotallow "ruff format src"'
check "DG5: prettier --write is not pre-approved" 'ronotallow "npx prettier --write src"'
check "DG5: gofmt -w / go fmt / cargo fmt are not pre-approved" 'ronotallow "gofmt -w ." && ronotallow "go fmt ./..." && ronotallow "cargo fmt"'
```

- [ ] **Step 2: Run the DG4/DG5 checks**

Run: `cd glm-skills && env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh 2>&1 | grep -E "^  (ok  |FAIL) DG[45]:"`
Expected: 12 lines, all starting with `  ok   DG4:` or `  ok   DG5:`, and no line starting with `  FAIL DG`.

- [ ] **Step 3: Add the DE1 harness-detection checks**

Insert this right after the Step 1 block:

```bash
echo "== OpenCode hardening DE1: v2 is detected from OPENCODE_TERMINAL alone"
export DEVTEAM_PY="$S/devteam.py"
ocplan() { # $1 slice id, $2 checkpoint_every (default 99) -> plan.md with one code slice
  local l; l=$(printf '%s' "$1" | tr 'A-Z' 'a-z')
  printf '```json\n{"request":"oc","commands":{"test":"true"},"review_batch":99,"checkpoint_every":%s,"slices":[{"id":"%s","title":"t","deps":[],"files":["src/%s.js","tests/%s.test.js"],"risk":"low","criteria":["c"]}]}\n```\n' "${2:-99}" "$1" "$l" "$l" > plan.md
}
RD1="$(newrepo rde1)"; cd "$RD1"; ocplan N1
D1OUT=$(env -u DEVTEAM_HARNESS -u OPENCODE -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT OPENCODE_TERMINAL=1 PATH="$OCBIN:$OLDPATH" python3 "$S/devteam.py" start plan.md 2>&1)
check "DE1: OPENCODE_TERMINAL=1 with no OPENCODE selects the OpenCode path (no Agent line)" '[[ "$D1OUT" == *"DISPATCH N1"* && "$D1OUT" != *"Agent → subagent_type"* ]]'
env -u DEVTEAM_HARNESS -u OPENCODE -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT OPENCODE_TERMINAL=1 PATH="$OCBIN:$OLDPATH" python3 "$S/devteam.py" wait --timeout 30 >/dev/null 2>&1
check "DE1: the v2-detected dispatch really launched an OpenCode lane" '[ -f "$RD1/.claude/dev-team/lanes/N1.jsonl" ]'
RD1C="$(newrepo rde1c)"; cd "$RD1C"; ocplan N1
D1CL=$(env -u DEVTEAM_HARNESS -u OPENCODE -u OPENCODE_TERMINAL python3 "$S/devteam.py" start plan.md 2>&1)
check "DE1: with no OpenCode variable the Claude path is kept (Agent line, no lane)" '[[ "$D1CL" == *"Agent → subagent_type: programmer"* ]] && [ ! -e "$RD1C/.claude/dev-team/lanes/N1.jsonl" ]'
```

- [ ] **Step 4: Run the DE1 checks**

Run: `cd glm-skills && env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh 2>&1 | grep -E "^  (ok  |FAIL) DE1:"`
Expected: 3 lines, all starting with `  ok   DE1:`.

- [ ] **Step 5: Add the DE4 detached-checkpoint checks**

Insert this right after the Step 3 block. The plan has one slice, `O1`, with `checkpoint_every` 1. The shared stub commits RED and GREEN for `O1`, so `next` merges it and starts a checkpoint:

```bash
echo "== OpenCode hardening DE4: the checkpoint runs detached and wait/next harvest it"
RD4="$(newrepo rde4)"; cd "$RD4"; ocplan O1 1
OCD() { DEVTEAM_HARNESS=opencode PATH="$OCBIN:$OLDPATH" python3 "$S/devteam.py" "$@"; }
OCD start plan.md >/dev/null 2>&1
OCD wait --timeout 30 >/dev/null 2>&1
D4OUT=$(OCD next 2>&1)
check "DE4: next merged O1 and started the checkpoint without a background Bash call" '[[ "$D4OUT" == *"O1: MERGED"* && "$D4OUT" == *"CHECKPOINT"* && "$D4OUT" != *"run in the BACKGROUND"* ]]'
check "DE4: next points the Conductor to wait" '[[ "$D4OUT" == *"NEXT:"*"wait"* ]]'
OCD wait --timeout 60 >/dev/null 2>&1
for i in 1 2 3 4 5 6 7 8 9 10; do grep -qs "EXIT=0" .claude/dev-team/logs/checkpoint-*.log && break; sleep 1; done
check "DE4: the detached checkpoint ran to the end and recorded EXIT=0" 'grep -qs "EXIT=0" .claude/dev-team/logs/checkpoint-*.log'
D4NEXT=$(OCD next 2>&1)
check "DE4: next harvested the checkpoint from its log and nothing stays pending" '[[ "$D4NEXT" == *"PASS (exit 0)"* ]] && python3 -c "import json;s=json.load(open(\".claude/dev-team/state.json\"));assert not s.get(\"checkpoint_pending\")"'
```

- [ ] **Step 6: Run the DE4 checks**

Run: `cd glm-skills && env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh 2>&1 | grep -E "^  (ok  |FAIL) DE4:"`
Expected: 4 lines, all starting with `  ok   DE4:`.

- [ ] **Step 7: Add the DE6 resume checks**

Insert this right after the Step 5 block. It uses a second stub `opencode` that always reports `## Status: Blocked`. The stub logs every call (slice, role, `--dir`, argv and stdin) to `$OCLOG6`:

```bash
echo "== OpenCode hardening DE6: resume relaunches a blocked lane in its worktree"
OCB6="$(mktemp -d)"; OCLOG6="$OCB6/calls.log"; export OCLOG6
cat > "$OCB6/opencode" <<'SH'
#!/usr/bin/env bash
set -u
if [ "${1:-}" = "--version" ]; then echo "1.18.32"; exit 0; fi
IN=""; if [ ! -t 0 ]; then IN="$(cat)"; fi
DIR=""; prev=""
for a in "$@"; do [ "$prev" = "--dir" ] && DIR="$a"; prev="$a"; done
printf 'CALL slice=%s role=%s dir=%s argv=%s stdin=%s\n' "${DEVTEAM_SLICE:-}" "${DEVTEAM_ROLE:-}" "$DIR" "$*" "$IN" >> "$OCLOG6"
printf '%s\n' '{"type":"text","part":{"type":"text","text":"## Status: Blocked\n## Notes: need src/shared.js which is outside my footprint"}}'
exit 0
SH
chmod +x "$OCB6/opencode"
RD6="$(newrepo rde6)"; cd "$RD6"; ocplan B1
OC6() { DEVTEAM_HARNESS=opencode PATH="$OCB6:$OLDPATH" python3 "$S/devteam.py" "$@"; }
OC6 start plan.md >/dev/null 2>&1
OC6 wait --timeout 30 >/dev/null 2>&1
check "DE6: a Blocked lane leaves a .blocked marker" '[ -f "$RD6/.claude/dev-team/slices/B1.blocked" ]'
D6OUT=$(OC6 next 2>&1)
check "DE6: next surfaces the block and names resume, not SendMessage" '[[ "$D6OUT" == *"BLOCKED B1"* && "$D6OUT" == *"resume B1"* && "$D6OUT" != *"SendMessage"* ]]'
B1WT="$RD6/.claude/dev-team/wt/B1"
printf '3\n' > "$B1WT/.slice/stop_blocks"
N6=$(grep -c "slice=B1" "$OCLOG6")
R6OUT=$(OC6 resume B1 --note "use src/y.js instead" 2>&1)
OC6 wait --timeout 30 >/dev/null 2>&1
check "DE6: resume relaunched a fresh lane and printed a NEXT: line" '[ "$(grep -c "slice=B1" "$OCLOG6")" -gt "$N6" ] && [[ "$R6OUT" == *"NEXT:"* ]]'
check "DE6: the relaunched lane runs in the same worktree" '[ -d "$B1WT/.slice" ] && grep "slice=B1" "$OCLOG6" | tail -1 | grep -q "dir=.*/.claude/dev-team/wt/B1 "'
check "DE6: resume reset .slice/stop_blocks" '[ ! -s "$B1WT/.slice/stop_blocks" ] || [ "$(tr -d "[:space:]" < "$B1WT/.slice/stop_blocks")" = 0 ]'
check "DE6: the --note text reaches the relaunched lane" 'grep -q "use src/y.js instead" "$OCLOG6" || grep -rqs "use src/y.js instead" "$RD6/.claude/dev-team/briefs" "$B1WT/.slice"'
cd "$R"
unset DEVTEAM_PY OCLOG6
```

- [ ] **Step 8: Run the DE6 checks**

Run: `cd glm-skills && env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh 2>&1 | grep -E "^  (ok  |FAIL) DE6:"`
Expected: 6 lines, all starting with `  ok   DE6:`.

- [ ] **Step 9: Syntax check and full selftest**

Run: `cd glm-skills && bash -n dev-team-glm/scripts/selftest.sh && echo SYNTAX-OK`
Expected: `SYNTAX-OK`

Run: `cd glm-skills && env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh 2>&1 | tail -1`
Expected: `passed=N failed=M` with N ≥ 349 (the 324 baseline plus the 25 new checks) and M ≤ 5. The only failures should be the 5 known macOS ones: GNU `sed -i`, 4× `/private/var` resolve, and the bash 3.2 word-split. No `FAIL` line may carry a `DG4:`, `DG5:`, `DE1:`, `DE4:` or `DE6:` prefix.

- [ ] **Step 10: Commit**

```bash
cd ..
git add glm-skills/dev-team-glm/scripts/selftest.sh
git commit -m "feat(dev-team): selftest checks for DG4, DG5, DE1, DE4, DE6 (OpenCode hardening)"
```

---

### T15: dev-team SKILL.md and README for OpenCode [P]

**Depends:** T11, T13

**Interfaces:**
- Consumes: `devteam.py resume <slice id> [--note TEXT]`; `.slice/stop_blocks`; `.done`; `.blocked`; `NEXT:`; `launch_lane`; `wait`; `next`

**Files:**
- Modify: `glm-skills/dev-team-glm/SKILL.md`
- Modify: `glm-skills/dev-team-glm/README.md`

This task changes documentation only. The check is a throwaway script in `/tmp` (not committed). It runs the SKILL.md bootstrap snippet in temp dirs and greps both files for the new OpenCode behaviour: DG12, DG15, DE1, DE3, DE4, DE6, DE7, DE8, DE9, DE10, DE13, DE14 and DE15, plus the guard notes DG7, DG8, DG9, DG11 and DG14. All commands run from `glm-skills/` (`cd glm-skills`).

- [ ] **Step 1: Write the failing check script**

Save as `/tmp/t15_check.py`:

```python
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path("dev-team-glm").resolve()
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
failures = []
temps = []


def need(name, text, fragment):
    if fragment not in text:
        failures.append("%s: missing %r" % (name, fragment))


def ban(name, text, fragment):
    if fragment in text:
        failures.append("%s: still has %r" % (name, fragment))


def fake_skill(base):
    scripts = base / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "devteam.py").write_text("", encoding="utf-8")
    return str(scripts)


def fresh():
    top = pathlib.Path(os.path.realpath(tempfile.mkdtemp(prefix="t15-")))
    temps.append(top)
    cwd = top / "repo"
    home = top / "home"
    cwd.mkdir()
    home.mkdir()
    return cwd, home


def run(snippet, cwd, home, extra=None):
    env = {"PATH": os.environ["PATH"], "HOME": str(home)}
    env.update(extra or {})
    return subprocess.run(["bash", "-c", snippet], cwd=str(cwd), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True)


def expect_found(label, proc, scripts):
    want = "D=%s" % scripts
    if proc.returncode != 0 or want not in proc.stdout.splitlines():
        failures.append("bootstrap %s: want %r, got rc=%d out=%r err=%r"
                        % (label, want, proc.returncode, proc.stdout, proc.stderr))


def check_bootstrap():
    m = re.search(r"```bash\n(D=; for d in [^\n]*)\n```", SKILL)
    if not m:
        failures.append("SKILL.md: bootstrap block not found")
        return
    snippet = m.group(1)

    cwd, home = fresh()
    proc = run(snippet, cwd, home)
    if proc.returncode != 1 or "not found" not in proc.stderr or "D=" in proc.stdout:
        failures.append("bootstrap miss: want exit 1 and 'not found' on stderr, got rc=%d out=%r err=%r"
                        % (proc.returncode, proc.stdout, proc.stderr))

    cwd, home = fresh()
    expect_found("CLAUDE_SKILL_DIR",
                 run(snippet, cwd, home, {"CLAUDE_SKILL_DIR": str(ROOT)}),
                 str(ROOT / "scripts"))

    cwd, home = fresh()
    base = fake_skill(cwd.parent / "base")
    fake_skill(cwd / ".opencode" / "skills" / "dev-team")
    expect_found("base dir line first",
                 run(snippet.replace("<base dir>", str(cwd.parent / "base")), cwd, home),
                 base)

    cwd, home = fresh()
    cfg = fake_skill(cwd.parent / "cfg" / "skills" / "dev-team")
    fake_skill(cwd / ".opencode" / "skills" / "dev-team")
    expect_found("OPENCODE_CONFIG_DIR before .opencode",
                 run(snippet, cwd, home, {"OPENCODE_CONFIG_DIR": str(cwd.parent / "cfg")}),
                 cfg)

    cwd, home = fresh()
    local = fake_skill(cwd / ".opencode" / "skills" / "dev-team")
    fake_skill(home / ".config" / "opencode" / "skills" / "dev-team")
    expect_found(".opencode before ~/.config/opencode", run(snippet, cwd, home), local)

    cwd, home = fresh()
    user_cfg = fake_skill(home / ".config" / "opencode" / "skills" / "dev-team")
    fake_skill(cwd / ".agents" / "skills" / "dev-team")
    fake_skill(home / ".claude" / "skills" / "dev-team")
    expect_found("~/.config/opencode before .agents", run(snippet, cwd, home), user_cfg)

    cwd, home = fresh()
    agents = fake_skill(cwd / ".agents" / "skills" / "dev-team")
    fake_skill(cwd / ".claude" / "skills" / "dev-team")
    expect_found(".agents before .claude", run(snippet, cwd, home), agents)


check_bootstrap()

for frag in ("Base directory for this skill", "OPENCODE_TERMINAL",
             "devteam resume <id> --note", ".slice/stop_blocks", "`general`"):
    need("SKILL.md", SKILL, frag)
for frag in ("`devteam <cmd>` below means `python3 ${CLAUDE_SKILL_DIR}/scripts/devteam.py <cmd>`",
             "when `DEVTEAM_HARNESS=opencode` or `OPENCODE` is set",
             "no role → silent allow",
             'devteam retry <id> --note "<answer or exact fix>"'):
    ban("SKILL.md", SKILL, frag)

for frag in ("devteam resume <id> --note", "OPENCODE_TERMINAL", ".slice/stop_blocks",
             "`general`", "\n5. **Stop gate:**", "OpenCode hardening (2026-09-28)"):
    need("README.md", README, frag)
for frag in ("hỏi vòng.4. **Stop gate:**", "hoặc `OPENCODE` được set"):
    ban("README.md", README, frag)

for top in temps:
    shutil.rmtree(str(top), ignore_errors=True)
for line in failures:
    print(line)
if failures:
    print("FAIL: %d problem(s)" % len(failures))
    sys.exit(1)
print("OK: dev-team SKILL.md and README.md checks pass")
```

- [ ] **Step 2: Run the check to verify it fails**

Run: `python3 /tmp/t15_check.py`
Expected: FAIL, exit 1. The first line is `SKILL.md: bootstrap block not found` and the last line is `FAIL: 18 problem(s)`.

- [ ] **Step 3: Replace the SKILL.md script-path line with the shared bootstrap snippet (DG12)**

In `dev-team-glm/SKILL.md`, replace this exact line (line 20):

```text
You are the **Conductor**. `devteam <cmd>` below means `python3 ${CLAUDE_SKILL_DIR}/scripts/devteam.py <cmd>`.
```

with:

````markdown
You are the **Conductor**.

**Bootstrap — put this in front of your FIRST command, once.** If the harness shows a "Base directory for this skill" line, replace `<base dir>` with that path. Otherwise leave it as is. OpenCode never sets `${CLAUDE_SKILL_DIR}`.

```bash
D=; for d in "${CLAUDE_SKILL_DIR:-<base dir>}" "$OPENCODE_CONFIG_DIR/skills/dev-team" .opencode/skills/dev-team ~/.config/opencode/skills/dev-team .agents/skills/dev-team ~/.agents/skills/dev-team .claude/skills/dev-team ~/.claude/skills/dev-team ~/.zcode/skills/dev-team; do [ -f "$d/scripts/devteam.py" ] && D=$(cd "$d/scripts" && pwd) && break; done; [ -n "$D" ] || { echo "dev-team: scripts/devteam.py not found in any skills dir; set CLAUDE_SKILL_DIR=<the Base directory for this skill>" >&2; exit 1; }; echo "D=$D"
```

The output starts with `D=<absolute path>`. Shell variables do not survive between tool calls, so paste that **literal absolute path**. `devteam <cmd>` below means `python3 <that path>/devteam.py <cmd>`. On a miss the snippet prints `dev-team: scripts/devteam.py not found …` and exits 1. Install the skill first (README, "OpenCode"), and never run `python3 "" …`.
````

- [ ] **Step 4: Rewrite the OpenCode protocol body (DE1, DE3, DE4, DE6-DE10, DE13-DE15, DG7-DG9, DG11, DG14)**

In `dev-team-glm/SKILL.md`, keep the `#### OpenCode protocol` heading. Replace everything after it, starting at the line that begins `On OpenCode, when` and ending at the item `4. \`LANE DOWN\`` together with its continuation line (the last line before `## Route first`), with:

```markdown
The engine detects OpenCode itself (`oc_harness.harness()`). Any of these marks it: `OPENCODE` or `OPENCODE_TERMINAL` is set (v2 sets only `OPENCODE_TERMINAL=1`), `DEVTEAM_HARNESS=opencode` is set, the skill sits under an OpenCode skills dir, or a `.oc-major` file sits next to the scripts. The Conductor then routes every lane through worktrees:

| Command | Purpose |
| --- | --- |
| `devteam start <plan.md>` | Starts the run. `doctor --fix` installs the agents, creates git worktrees at `.claude/dev-team/wt/<id>`, checks the plan and prints the ready lanes. Each lane process gets `env DEVTEAM_ROLE=<agent>` and `DEVTEAM_SLICE=<id>`. |
| `devteam wait [--timeout 100]` | Blocks up to `--timeout` seconds for one of three things: a new lane result, a completion marker in `.claude/dev-team/lanes/`, or a finished checkpoint. It returns at once when no lane is live, and it prints `NEXT: devteam next`. On v2 (your shell tool has a `background` param), run `devteam wait --timeout 3600` with `background: true` and end the turn. Its completion notification is your wake-up; keep only one wait running at a time. On v1, run it in the foreground with the default 100 s, which stays under the 120 s bash-tool limit. |
| `devteam next` | Reads all lane JSON output and markers (`.done`/`.blocked`), merges results, queues fixes, dispatches ready lanes and retries, and prints the endgame. The stop gate runs after each programmer lane: `lane-run` pipes `{"cwd": <worktree>, "last_assistant_message": <text>}` to `guard.py stop`. Exit 2 means blocked. The lane then re-runs once per block with the gate stderr appended to its brief, and is force-finished after 2 blocks (the counter is the worktree's `.slice/stop_blocks`). If a lane's status is not OK and its HEAD still equals the base, it writes `.blocked` with the lane error instead of burning reruns. The governor reads lane files, not transcripts. It prints `LANE DOWN <id> (<kind>): the lane process ended <error>` in two cases: a lane ends `FAIL`/`STALL`/`TIMEOUT` in `.claude/dev-team/lanes/<id>.done`, or a lane's pid is dead with no `.end` and no marker (killed by a signal). A stuck slice retries cold with `fail <id>`, then `retry <id>`. The worktree is discarded; only the branch `attempt/<id>-N` is kept for salvage. A stuck review or research lane is relaunched with the printed command. That command already starts with `python3`, runs detached and clears the stale `.done`. |
| `devteam resume <id> [--note TEXT]` | Warm fix. It relaunches a fresh lane in the **same** worktree with the note added to the brief, and resets `.slice/stop_blocks`. Use it for the answer to a `BLOCKED` question and for the fix to a `REJECTED` / `NOT READY` / `MERGE ERROR`. |
| `devteam retry <id> [--files ...]` | Cold retry. It creates a fresh worktree, switches to the stronger model (GLM-5.3) and re-dispatches, optionally with a wider file scope. |

Lanes run `python3 <devteam.py> lane-run <id>` in their worktree. `lane-run` claims the slice, runs through the vendored `oc_harness.run_lanes` and pipes the stop-gate JSON. Stall is per role: about 900 s for programmer and team-leader, 600 s for reviewers, so a long test or build is not killed. A `programmer-lite` slice runs the `programmer-lite` agent (effort low) on v1 and v2. The opencode process group of each lane is written to `lanes/<id>.pgid`, and the engine stops a lane by killing that group, so no orphan keeps editing a recreated worktree. A checkpoint is launched detached the same way as a lane, and `wait` reports when it ends. The Claude 20-agent cap does not apply: the tier ceilings (40/64) are reachable. Markers go to `.claude/dev-team/slices/<id>.done|.blocked` (stop gate only). Lane outputs go to `.claude/dev-team/lanes/<id>.jsonl|.err|.done` (runner only).

Tools are checked by `guard.py oc` mode: `edit`/`write`/`patch` and `bash` on v1, `edit`/`write`/`shell` on v2. A programmer gets the existing checks. Every other role is read-only, but may still run `devteam status` and `devteam probe`. When `DEVTEAM_ROLE` is unset, the v2 plugin takes the role from the event's `agent` if it names a dev-team role. In lane mode, `batch`, `question` and `execute` are denied, because a headless `question` blocks forever. OpenCode has no interactive fallback. An unapproved command, or a programmer write outside its own slice worktree, is DENIED outright and never left pending on a prompt. The deny message lists the pinned `.slice/allow` forms. Both plugins (v1 and v2) forward calls to `python3 guard.py oc` on stdin and throw `Error(reason)` on deny. Any plugin-side failure still allows the call, because the integrate re-check is the real enforcement. The plugin warns loudly once per lane and records the failure in the lane log.

Launch dev-team agents only through the engine's process lane (`devteam next` / `lane-run`), which sets `DEVTEAM_ROLE` and `DEVTEAM_SLICE` per lane. An agent spawned with OpenCode's own `task` (v1) or `subagent` (v2) tool gets neither variable, so never dispatch dev-team roles that way.

**Phases 2-4 on OpenCode.** The Claude Code tool names there map as follows:

1. `=== DISPATCH` / `REVIEW` / `INVESTIGATE` print a `LANE … running` line: the engine already started
   that lane. Launch nothing.
2. `CHECKPOINT …`: the engine already launched it detached. Launch nothing; `devteam wait` reports when it ends.
   A printed lane relaunch is already detached. v2: run it with the shell tool and `background: true`.
   v1: run it exactly as printed; it is wrapped in `( … ) > /dev/null 2>&1 &`, because a bare `&` keeps the bash tool blocked until the job ends.
3. `SendMessage` does not exist: a lane is a one-shot process. Answer a `BLOCKED` question, or apply a
   `REJECTED` / `NOT READY` / `MERGE ERROR` fix, with `devteam resume <id> --note "<answer or exact fix>"`.
   This is warm: a fresh lane in the same worktree, with the stop-gate counter reset. Use `devteam retry <id>`
   (cold: fresh worktree, GLM-5.3) only when a resume cannot fix it. The engine stops the old lane itself,
   so there is no `TaskStop`.
4. `LANE DOWN`: do exactly what the printed line says (`fail` + `retry` for a slice, the printed
   relaunch for a review or research lane).
5. `Explore` and `general-purpose` do not exist on OpenCode. Wherever this file says `Explore`, use
   the built-in `general` agent.
```

- [ ] **Step 5: Point the three `Explore` mentions at `general` on OpenCode**

In `dev-team-glm/SKILL.md`, make these three exact replacements:

1. In the "Route first" table, replace `` | A question about the code | `Explore` agents in parallel (one per area), answer. No engine. | `` with `` | A question about the code | `Explore` agents (`general` on OpenCode) in parallel (one per area), answer. No engine. | ``.
2. In Phase 1, replace `Huge codebase → first `Explore` agents (≤8, one per` with `Huge codebase → first `Explore` agents (`general` on OpenCode; ≤8, one per`.
3. In "Dispatch templates", replace `- **Explore** — built-in type, one per area;` with `- **Explore** — built-in type (`general` on OpenCode), one per area;`.

- [ ] **Step 6: Run the check to verify only README problems remain**

Run: `python3 /tmp/t15_check.py`
Expected: FAIL, exit 1. Every problem line starts with `README.md:` and the last line is `FAIL: 8 problem(s)`. No `SKILL.md:` or `bootstrap` line appears.

- [ ] **Step 7: Rewrite the README OpenCode section (DG15 split, detection, resume, lifecycle)**

In `dev-team-glm/README.md`, keep the `### OpenCode` heading. Replace everything after it, from the line starting `Trên OpenCode (khi` through item `10. **Chỉ dispatch qua engine:**` (the last line before `## Biến môi trường`), with:

```markdown
Trên OpenCode, engine tự nhận harness qua `oc_harness.harness()` khi có một trong các dấu hiệu sau: `OPENCODE` hoặc `OPENCODE_TERMINAL` được set (v2 chỉ set `OPENCODE_TERMINAL=1`), `DEVTEAM_HARNESS=opencode`, skill nằm trong thư mục skills của OpenCode, hoặc có file `.oc-major` cạnh scripts. Khi đó devteam chạy mỗi lane trong một git worktree riêng qua `oc_harness run`:

1. **Cài đặt:** chạy `python3 devteam.py doctor --harness opencode --fix` (hoặc `sh install-opencode.sh --major 1|2` cho 5 skill GLM còn lại). Lệnh này copy plugin guard (v1 hoặc v2 tùy major version) và các agent vào home OpenCode.
2. **Bootstrap:** OpenCode không set `${CLAUDE_SKILL_DIR}`, nên SKILL.md mở đầu bằng một vòng `for` tìm `scripts/devteam.py` theo thứ tự: dòng "Base directory for this skill", `$OPENCODE_CONFIG_DIR/skills`, `.opencode/skills`, `~/.config/opencode/skills`, rồi `.agents`, `~/.agents`, `.claude`, `~/.claude`, `~/.zcode`. Không tìm thấy thì báo lỗi rõ ràng và thoát với mã 1, không bao giờ chạy `python3 "" …`.
3. **Worktree:** với mỗi lane programmer, `lane-run` (không phải `devteam start`) tạo worktree tại `.claude/dev-team/wt/<id>` trên branch `devteam/<id>` từ base của slice, rồi chạy `claim` trong worktree đó và ghi env `DEVTEAM_ROLE`/`DEVTEAM_SLICE`.
4. **Vòng lặp:** `devteam wait` chặn tối đa 100 s để đợi kết quả lane, rồi `devteam next` đọc output JSON và dispatch lane mới cùng các retry. `wait` trả về ngay khi không còn lane nào đang chạy. Trên v2, tool shell có `background: true` (không timeout, tự báo khi xong): chạy `devteam wait --timeout 3600` ở nền rồi kết thúc lượt. Thông báo hoàn tất chính là tín hiệu đánh thức, không cần hỏi vòng.
5. **Stop gate:** sau mỗi programmer lane, `lane-run` (không phải `devteam next`) gọi `guard.py stop` với `{"cwd": <worktree>, "last_assistant_message": <text>}`. Exit 2 nghĩa là bị chặn: lane chạy lại tối đa 2 lần, với stderr của gate thêm vào brief, và bộ đếm nằm ở `.slice/stop_blocks`. Nếu lane lỗi mà HEAD vẫn bằng base, engine ghi `.blocked` kèm lỗi của lane thay vì chạy lại vô ích.
6. **Markers:** `.done` và `.blocked` ghi vào `.claude/dev-team/slices/<id>.*` (stop gate). Output của lane ghi vào `.claude/dev-team/lanes/<id>.jsonl|.err|.done` (runner).
7. **Stall và tiến trình:** stall tính theo role, khoảng 900 s cho programmer/team-leader và 600 s cho reviewer, nên test/build dài không bị giết oan. Process group của opencode được ghi vào `lanes/<id>.pgid`, và engine `killpg` theo file đó nên không để lại process mồ côi. Checkpoint được chạy tách nền giống lane, và `wait` báo khi nó xong. Trần 20 agent của Claude không áp cho OpenCode, nên đạt được trần tier 40/64. Slice `programmer-lite` chạy đúng agent lite (effort low) trên cả v1.
8. **Tool guards:** plugin v1/v2 pipe JSON (giống hook của Claude) đến `guard.py oc`. Programmer dùng bộ kiểm tra hiện có. Role khác chỉ được đọc, nhưng vẫn chạy được `devteam status`/`devteam probe`. Khi thiếu `DEVTEAM_ROLE`, plugin v2 lấy role từ `agent` của event nếu đó là role dev-team. Trong lane, `batch`, `question` và `execute` bị chặn, vì `question` headless sẽ treo. OpenCode không có prompt tương tác, nên một lệnh chưa được duyệt trước, hoặc một lượt ghi của programmer ra ngoài worktree của chính slice đó, đều bị TỪ CHỐI thẳng chứ không chờ hỏi. Thông báo từ chối liệt kê các dạng `.slice/allow` đã pin. Lỗi phía plugin vẫn cho qua (fail-open, vì bước integrate kiểm tra lại), nhưng plugin cảnh báo rõ một lần mỗi lane và ghi lỗi vào log lane.
9. **Sửa lỗi và retry:** OpenCode không có SendMessage vì lane là process chạy một lần. Câu trả lời cho `BLOCKED`, hay cách sửa cho `REJECTED` / `NOT READY` / `MERGE ERROR`, đi qua `devteam resume <id> --note "…"`: lệnh này chạy một lane mới trong **cùng** worktree và reset `.slice/stop_blocks`. Chỉ khi resume không cứu được mới dùng `devteam retry <id>`, lệnh tạo worktree mới, nâng lên GLM-5.3 và có thể mở rộng file scope. Engine tự dừng lane cũ.
10. **Lane chết:** governor đọc file lane (`.claude/dev-team/lanes/<id>.done`) thay vì transcript. Lane kết thúc `FAIL`/`STALL`/`TIMEOUT`, hoặc pid đã chết mà không có `.end` hay marker (bị signal giết), thì engine in `LANE DOWN <id> (<kind>)` kèm cách sửa. Với slice: `fail <id>` rồi `retry <id>` (worktree bị xoá, chỉ giữ branch `attempt/<id>-N` để cứu dữ liệu). Với review/research: chạy lại lệnh engine in ra. Lệnh đó đã có tiền tố `python3`, chạy tách nền và xoá `.done` cũ; dấu `&` trơn sẽ làm tool bash của OpenCode v1 bị treo tới khi lane xong.
11. **Doctor:** `python3 devteam.py doctor --harness opencode` kiểm tra agent, plugin, config và việc major version có khớp không.
12. **Chỉ dispatch qua engine:** agent dev-team chỉ được khởi chạy qua lane của engine (`devteam next` / `lane-run`), nơi gán `DEVTEAM_ROLE`/`DEVTEAM_SLICE` cho từng lane. Không bao giờ dispatch role dev-team bằng tool `task` (v1) hay `subagent` (v2) của OpenCode. Agent built-in của OpenCode là `general`; ở đó không có `general-purpose` hay `Explore`.
```

- [ ] **Step 8: Record the change in the README history**

In `dev-team-glm/README.md`, under the `## Lịch sử ngắn` heading, insert this as the first list item (just above the line starting `- **v3.2**`):

```markdown
- **OpenCode hardening (2026-09-28)** — v1 1.18.x và v2 2.0.x: bootstrap tìm thư mục skill mà không cần `${CLAUDE_SKILL_DIR}`; nhận v2 qua `OPENCODE_TERMINAL`; `resume <id> --note` thay cho SendMessage; stall theo role; checkpoint chạy tách nền; `wait` thoát khi không còn lane; `killpg` qua `lanes/<id>.pgid`; guard chặn `batch`/`question`/`execute` trong lane; báo LANE DOWN cho lane bị signal giết.
```

- [ ] **Step 9: Run the check to verify it passes**

Run: `python3 /tmp/t15_check.py`
Expected: PASS, with the single line `OK: dev-team SKILL.md and README.md checks pass` and exit 0.

- [ ] **Step 10: Run the skill frontmatter tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_all_skills.py'`
Expected: PASS. No failure or error mentions `dev-team` (the `name: dev-team` frontmatter and the description are unchanged).

- [ ] **Step 11: Run the dev-team selftest**

Run: `env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh`
Expected: `passed=` ≥ 324 and `failed=` ≤ 5. The only failures are the 5 known macOS ones.

- [ ] **Step 12: Commit**

```bash
cd ..
git add glm-skills/dev-team-glm/SKILL.md glm-skills/dev-team-glm/README.md
git commit -m "fix(dev-team): OpenCode v1/v2 bootstrap, resume, lifecycle and guard notes in SKILL.md and README"
cd glm-skills
rm -f /tmp/t15_check.py
```

---

### T16: debug_tool.py parallel defaults, lane routing, quoting, timing [P]

**Depends:** —

**Files:**
- Modify: `glm-skills/systematic-debugging-glm/scripts/debug_tool.py:53-58`
- Test: `glm-skills/_shared/tests/test_debug_core.py`

This task fixes four defects in `debug_tool.py`:
- SD1: `clamp(0, default)` returns 1, so every `-j` default of 0 runs serially.
- SD2: `race` in `SWARM_RE` has no word boundary, so "Traceback" routes to SWARM.
- SD3: the FAST `NEXT` line prints the repro command unquoted.
- SD7: `run` reports the longest single command as "wall" time.

All commands run from `glm-skills/` (`cd glm-skills`). Anchor every edit on the quoted code, not on line numbers, because the line numbers move as you edit.

- [ ] **Step 1: Write the failing tests for parallel defaults (SD1)**

Append the block below to the end of `_shared/tests/test_debug_core.py`. If the file does not exist, create it with this block as its content. If the file ends with an `if __name__ == "__main__":` block, keep that block as the last lines of the file.

```python
import contextlib
import importlib.util
import io
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

_T16_DT_PATH = (Path(__file__).resolve().parents[2]
                / "systematic-debugging-glm" / "scripts" / "debug_tool.py")
_t16_spec = importlib.util.spec_from_file_location("debug_tool_t16", str(_T16_DT_PATH))
DT16 = importlib.util.module_from_spec(_t16_spec)
_t16_spec.loader.exec_module(DT16)


def _t16_main(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = DT16.main(argv)
    return rc, buf.getvalue()


class _T16TmpRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="t16dbg.")
        subprocess.run(["git", "init", "-q", self.tmp], check=True)
        self.addCleanup(shutil.rmtree, self.tmp, True)


class DebugToolClampTest(unittest.TestCase):
    def test_zero_means_default(self):
        self.assertEqual(DT16.clamp(0, 8), 8)
        self.assertEqual(DT16.clamp("0", 8), 8)

    def test_negative_means_default(self):
        self.assertEqual(DT16.clamp(-3, 5), 5)

    def test_explicit_value_kept_and_capped(self):
        self.assertEqual(DT16.clamp(3, 8), 3)
        self.assertEqual(DT16.clamp(999, 8), DT16.MAXJ)
        self.assertEqual(DT16.clamp("x", 8), 8)


class DebugToolParallelDefaultTest(_T16TmpRepo):
    def test_run_default_is_parallel(self):
        rc, out = _t16_main(["run", "--dir", self.tmp, "true", "true", "true"])
        self.assertEqual(rc, 0)
        self.assertIn("(3 parallel,", out)

    def test_probe_extra_repros_stay_serial(self):
        # Overlapping runs would see the lock dir and exit 3 instead of 1.
        cmd = "mkdir lk 2>/dev/null || exit 3; sleep 0.3; rmdir lk; exit 1"
        rc, out = _t16_main(["probe", "--cmd", cmd, "--dir", self.tmp])
        self.assertEqual(rc, 0)
        self.assertIn("exit codes: [1, 1, 1]", out)
        self.assertNotIn("LANE: SWARM", out)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_core.py' -k DebugToolClampTest -k DebugToolParallelDefaultTest`
Expected: FAIL: `test_zero_means_default` (`AssertionError: 1 != 8`), `test_negative_means_default` (`AssertionError: 1 != 5`) and `test_run_default_is_parallel` (`'(3 parallel,' not found`), ending in `FAILED (failures=3)`. `test_probe_extra_repros_stay_serial` passes already, because every pool has one worker today. It guards the next step.

- [ ] **Step 3: Treat 0 as the default and keep the extra repros serial**

In `systematic-debugging-glm/scripts/debug_tool.py`, replace the whole `clamp` function with:

```python
def clamp(j, default):
    """Parse a -j value. 0, negative or unparseable means `default`."""
    try:
        j = int(j)
    except (TypeError, ValueError):
        j = default
    if j <= 0:
        j = default
    return max(1, min(MAXJ, int(j)))
```

In `cmd_probe`, find this line:

```python fragment
                repro += [f.result() for f in [ex.submit(run_repro, i) for i in range(1, extra + 1)]]
```

Replace it with the lines below. Runs of the same command in one tree at the same time share files, which would look like flakiness.

```python fragment
                # serial on purpose: parallel runs in one tree fake flakiness
                repro += [run_repro(i) for i in range(1, extra + 1)]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_core.py' -k DebugToolClampTest -k DebugToolParallelDefaultTest`
Expected: PASS (`Ran 5 tests`, `OK`)

- [ ] **Step 5: Write the failing tests for SWARM routing (SD2)**

Append to the end of `_shared/tests/test_debug_core.py`, above any `if __name__ == "__main__":` block:

```python
class DebugToolSwarmRouteTest(_T16TmpRepo):
    def test_traceback_is_not_a_race(self):
        self.assertIsNone(DT16.SWARM_RE.search("Traceback (most recent call last):"))
        self.assertIsNone(DT16.SWARM_RE.search("see the backtrace below"))

    def test_real_race_still_matches(self):
        self.assertIsNotNone(DT16.SWARM_RE.search("a data race in the pool"))
        self.assertIsNotNone(DT16.SWARM_RE.search("two writers race on the file"))

    def test_python_traceback_routes_standard(self):
        Path(self.tmp, "app.py").write_text("x = 1\nint('a')\n")
        err = ('Traceback (most recent call last):\n'
               '  File "app.py", line 2, in <module>\n'
               'ValueError: bad literal')
        rc, out = _t16_main(["probe", "--error", err, "--dir", self.tmp])
        self.assertEqual(rc, 0)
        self.assertIn("LANE: STANDARD", out)
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_core.py' -k DebugToolSwarmRouteTest`
Expected: FAIL: `test_traceback_is_not_a_race` (`AssertionError: <re.Match object ... match='race'> is not None`) and `test_python_traceback_routes_standard` (`'LANE: STANDARD' not found`), ending in `FAILED (failures=2)`

- [ ] **Step 7: Add word boundaries to the race term**

In `debug_tool.py`, replace the `SWARM_RE` definition with:

```python
SWARM_RE = re.compile(
    r"flak|intermittent|sometimes|randomly|\brace\b|\braces\b|\bracy\b|timeout|timed out|hangs?\b|"
    r"only in CI|passes locally|slow|performance|regress|worked before|"
    r"used to work|non-?deterministic", re.I)
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_core.py' -k DebugToolSwarmRouteTest`
Expected: PASS (`Ran 3 tests`, `OK`)

- [ ] **Step 9: Write the failing test for the quoted FAST NEXT line (SD3)**

Append to the end of `_shared/tests/test_debug_core.py`, above any `if __name__ == "__main__":` block:

```python
class DebugToolFastNextQuoteTest(_T16TmpRepo):
    def test_fast_next_quotes_cmd(self):
        Path(self.tmp, "app.py").write_text("x = 1\nprint(foo)\n")
        err = ('  File "app.py", line 2, in <module>\n'
               "NameError: name 'foo' is not defined")
        cmd = 'test -f "missing file.txt"'
        rc, out = _t16_main(["probe", "--error", err, "--cmd", cmd, "--dir", self.tmp])
        self.assertEqual(rc, 0)
        self.assertIn("LANE: FAST", out)
        self.assertIn("debug_tool.py run -- " + shlex.quote(cmd), out)
```

- [ ] **Step 10: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_core.py' -k DebugToolFastNextQuoteTest`
Expected: FAIL: `test_fast_next_quotes_cmd` with `AssertionError: 'debug_tool.py run -- \'test -f "missing file.txt"\'' not found in ...`, ending in `FAILED (failures=1)`

- [ ] **Step 11: Quote the command in the FAST NEXT line**

In `cmd_probe`, under `if lane == "FAST":`, replace this line:

```python fragment
        o.append("3. One call: python3 %s/debug_tool.py run -- %s" % (SCRIPTS, a.cmd or "<build/test cmd>"))
```

with:

```python fragment
        o.append("3. One call: python3 %s/debug_tool.py run -- %s"
                 % (SCRIPTS, shlex.quote(a.cmd) if a.cmd else "<build/test cmd>"))
```

- [ ] **Step 12: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_core.py' -k DebugToolFastNextQuoteTest`
Expected: PASS (`Ran 1 test`, `OK`)

- [ ] **Step 13: Write the failing test for real wall time (SD7)**

Append to the end of `_shared/tests/test_debug_core.py`, above any `if __name__ == "__main__":` block:

```python
class DebugToolRunWallTest(_T16TmpRepo):
    def test_wall_is_real_elapsed_time(self):
        rc, out = _t16_main(["run", "-j", "1", "--dir", self.tmp, "sleep 0.4", "sleep 0.4"])
        self.assertEqual(rc, 0)
        m = re.search(r"\(1 parallel, ([\d.]+)s wall\)", out)
        self.assertIsNotNone(m, out)
        self.assertGreaterEqual(float(m.group(1)), 0.7)
```

- [ ] **Step 14: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_core.py' -k DebugToolRunWallTest`
Expected: FAIL: `test_wall_is_real_elapsed_time` with `AssertionError: 0.4 not greater than or equal to 0.7`, ending in `FAILED (failures=1)`

- [ ] **Step 15: Measure real wall time in `cmd_run`**

In `cmd_run`, replace these lines:

```python fragment
    res = pmap(one, list(enumerate(cmds)), j)
    bad = [r for r in res if r["rc"] != 0]
    print("S=%s" % SCRIPTS)
    print("RESULT: %d/%d exited non-zero (%d parallel, %.1fs wall)"
          % (len(bad), len(res), j, max([r["sec"] for r in res] or [0])))
```

with:

```python fragment
    t_start = time.time()
    res = pmap(one, list(enumerate(cmds)), j)
    wall = time.time() - t_start
    bad = [r for r in res if r["rc"] != 0]
    print("S=%s" % SCRIPTS)
    print("RESULT: %d/%d exited non-zero (%d parallel, %.1fs wall)"
          % (len(bad), len(res), j, wall))
```

- [ ] **Step 16: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_core.py' -k DebugToolRunWallTest`
Expected: PASS (`Ran 1 test`, `OK`)

- [ ] **Step 17: Run the whole test file and the full suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_core.py'`
Expected: PASS (`OK`, and every `DebugTool*` test is included in the count)

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no new failures compared with the baseline (the only failures are the known stale-fixture-path tests, or none if those are already fixed)

- [ ] **Step 18: Commit**

Run these from the git root (one level above `glm-skills/`):

```bash
cd ..
git add glm-skills/systematic-debugging-glm/scripts/debug_tool.py glm-skills/_shared/tests/test_debug_core.py
git commit -m "fix(systematic-debugging): parallel -j defaults, race word boundary, quoted FAST next, real wall time"
```

---

### T17: debug_tool.py experiment worktrees and patch order [P]

**Depends:** —

**Runs after:** T16 (same files)

**Files:**
- Modify: `glm-skills/systematic-debugging-glm/scripts/debug_tool.py:496-616`
- Test: `glm-skills/_shared/tests/test_debug_experiment.py`

This task fixes spec rows SD4 and SD5 in `debug_tool.py experiment`. An earlier task edits the same file (clamp, `sh`, routing, NEXT line, wall time), so find each edit below by the quoted code, not by line number. All commands run from `glm-skills/`.

- [ ] **Step 1: Write the failing tests for worktree completeness (SD4)**

Create `glm-skills/_shared/tests/test_debug_experiment.py`:

```python
"""debug_tool.py experiment: worktree completeness (SD4) and patch order (SD5)."""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOL = (Path(__file__).resolve().parents[2]
        / "systematic-debugging-glm" / "scripts" / "debug_tool.py")


def load_tool():
    spec = importlib.util.spec_from_file_location("debug_tool_experiment_under_test", str(TOOL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DT = load_tool()


def git(repo, *args):
    subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
                    "-c", "commit.gpgsign=false"] + list(args),
                   cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class ExperimentRepo(unittest.TestCase):
    """A throwaway git repo, a separate caller cwd and a private TMPDIR."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix="sdexp-test."))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        self.caller = os.path.join(self.tmp, "caller")
        self.tmpdir = os.path.join(self.tmp, "t")
        for d in (self.repo, self.caller, self.tmpdir):
            os.makedirs(d)
        git(self.repo, "init", "-q")
        self.write("flag.txt", "a\nbroken\n")
        self.write(".gitignore", "node_modules/\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "init")

    def write(self, rel, text):
        p = Path(self.repo, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def run_exp(self, spec):
        Path(self.caller, "spec.json").write_text(json.dumps(spec))
        out, err = io.StringIO(), io.StringIO()
        old = os.getcwd()
        os.chdir(self.caller)
        try:
            with mock.patch.dict(os.environ, {"TMPDIR": self.tmpdir}):
                with contextlib.redirect_stdout(out):
                    with contextlib.redirect_stderr(err):
                        rc = DT.main(["experiment", "--spec", "spec.json",
                                      "--dir", self.repo, "-j", "2"])
        finally:
            os.chdir(old)
        return rc, out.getvalue() + "\n" + err.getvalue()


class WorktreeCompletenessTest(ExperimentRepo):
    """SD4: untracked files and ignored dependency dirs reach every arm."""

    def test_untracked_file_reaches_worktree(self):
        self.write("data/fixture.txt", "needed by the repro\n")
        rc, out = self.run_exp([{
            "id": "h1", "hypothesis": "FLAG fixes it",
            "cmd": 'test -f data/fixture.txt || exit 3; test "$FLAG" = fixed',
            "env": {"FLAG": "fixed"}, "expect": "treatment_passes"}])
        self.assertIn("[CONFIRMED] h1", out)
        self.assertEqual(rc, 0)

    def test_ignored_dependency_dir_is_linked_by_default(self):
        self.write("node_modules/dep/index.js", "module.exports = 1\n")
        rc, out = self.run_exp([{
            "id": "h1", "hypothesis": "FLAG fixes it",
            "cmd": 'test -f node_modules/dep/index.js || exit 3; test "$FLAG" = fixed',
            "env": {"FLAG": "fixed"}, "expect": "treatment_passes"}])
        self.assertIn("[CONFIRMED] h1", out)
        self.assertEqual(rc, 0)

    def test_control_not_reproducing_is_inconclusive(self):
        rc, out = self.run_exp([{
            "id": "h1", "hypothesis": "FLAG fixes it",
            "cmd": "true", "env": {"FLAG": "fixed"}, "expect": "treatment_passes"}])
        self.assertIn("[INCONCLUSIVE] h1", out)
        self.assertIn("control did not reproduce", out)
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the SD4 tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_experiment.py'`
Expected: FAIL with `FAILED (failures=3)`: the first two show `AssertionError: '[CONFIRMED] h1' not found in` (both arms exit 3, so the output reads `[REFUTED] h1`), and the third shows `AssertionError: '[INCONCLUSIVE] h1' not found in`.

- [ ] **Step 3: Copy untracked files, link ignored dependency dirs, and mark a silent control INCONCLUSIVE**

In `glm-skills/systematic-debugging-glm/scripts/debug_tool.py`, replace the whole `def make_worktree(root, path, links, wip_patch):` function with these three functions:

```python
DEFAULT_LINKS = ("node_modules", ".venv", "venv", "vendor/bundle")


def default_links(root):
    """Ignored dependency dirs that exist in root: linked into every worktree."""
    out = []
    for d in DEFAULT_LINKS:
        if os.path.isdir(os.path.join(root, d)):
            rc, _ = sh("git check-ignore -q %s" % shlex.quote(d), cwd=root, timeout=30)
            if rc == 0:
                out.append(d)
    return out


def copy_untracked(root, path):
    """Copy untracked, non-ignored files: HEAD plus the WIP diff misses them."""
    rc, out = sh("git ls-files --others --exclude-standard -z", cwd=root, timeout=120)
    if rc != 0:
        return 0
    n = 0
    for rel in out.split("\0"):
        if not rel:
            continue
        src, dst = os.path.join(root, rel), os.path.join(path, rel)
        if not (os.path.isfile(src) or os.path.islink(src)) or os.path.lexists(dst):
            continue
        os.makedirs(os.path.dirname(dst) or path, exist_ok=True)
        try:
            shutil.copy2(src, dst, follow_symlinks=False)
            n += 1
        except OSError:
            pass
    return n


def make_worktree(root, path, links, wip_patch):
    rc, out = sh("git worktree add --detach --force %s HEAD" % shlex.quote(path), cwd=root, timeout=300)
    if rc != 0:
        return "worktree add failed: " + tail(out, 5)
    if wip_patch and os.path.getsize(wip_patch) > 0:
        sh("git apply %s" % shlex.quote(wip_patch), cwd=path, timeout=120)
    copy_untracked(root, path)
    for d in links or []:
        src, dst = os.path.join(root, d), os.path.join(path, d)
        if os.path.exists(src) and not os.path.lexists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                os.symlink(src, dst)
            except OSError:
                pass
    return None
```

In `cmd_experiment`, directly after the line `arms = [(h, side) for h in spec for side in ("control", "treatment")]`, add:

```python fragment
    auto_links = default_links(root)
```

In `run_arm`, replace the line `err = make_worktree(root, wt, h.get("link"), wip)` with:

```python fragment
        links = list(h.get("link") or [])
        links += [d for d in auto_links if d not in links]
        err = make_worktree(root, wt, links, wip)
```

In the verdict loop, replace these two lines:

```python fragment
        if c["fails"] == t["fails"]:
            r["verdict"], r["note"] = "REFUTED", "the variable changed nothing"
```

with:

```python fragment
        if expect == "treatment_passes" and c["fails"] == 0:
            r["verdict"], r["note"] = "INCONCLUSIVE", (
                "the control did not reproduce the failure in its worktree; the repro likely "
                "needs a file the worktree lacks - list it under \"link\" or commit it")
        elif c["fails"] == t["fails"]:
            r["verdict"], r["note"] = "REFUTED", "the variable changed nothing"
```

- [ ] **Step 4: Run the SD4 tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_experiment.py'`
Expected: PASS: `Ran 3 tests` then `OK`.

- [ ] **Step 5: Write the failing tests for patch order and path (SD5)**

Append this class to `glm-skills/_shared/tests/test_debug_experiment.py`, above the `if __name__ == "__main__":` line:

```python
class PatchOrderTest(ExperimentRepo):
    """SD5: patch_file resolves against the caller's cwd; a patch that already
    contains the WIP is applied on HEAD instead of on top of the WIP."""

    ON_HEAD = ("--- a/flag.txt\n+++ b/flag.txt\n@@ -1,2 +1,2 @@\n"
               " a\n-broken\n+fixed\n")
    CONTAINS_WIP = ("--- a/flag.txt\n+++ b/flag.txt\n@@ -1,2 +1,2 @@\n"
                    "-a\n-broken\n+a-wip\n+fixed\n")
    ON_WIP = ("--- a/flag.txt\n+++ b/flag.txt\n@@ -1,2 +1,2 @@\n"
              " a-wip\n-broken\n+fixed\n")

    def spec(self, cmd):
        return [{"id": "h1", "hypothesis": "the patch fixes it", "cmd": cmd,
                 "patch_file": "fix.diff", "expect": "treatment_passes"}]

    def test_relative_patch_file_resolves_against_caller_cwd(self):
        Path(self.caller, "fix.diff").write_text(self.ON_HEAD)
        rc, out = self.run_exp(self.spec("grep -qx fixed flag.txt"))
        self.assertIn("[CONFIRMED] h1", out)
        self.assertEqual(rc, 0)

    def test_missing_patch_file_is_rejected_up_front(self):
        rc, out = self.run_exp(self.spec("grep -qx fixed flag.txt"))
        self.assertEqual(rc, 2)
        self.assertIn("patch_file", out)
        self.assertIn(os.path.join(self.caller, "fix.diff"), out)

    def test_patch_that_contains_wip_is_applied_on_head(self):
        self.write("flag.txt", "a-wip\nbroken\n")
        Path(self.caller, "fix.diff").write_text(self.CONTAINS_WIP)
        rc, out = self.run_exp(self.spec("grep -qx a-wip flag.txt && grep -qx fixed flag.txt"))
        self.assertIn("[CONFIRMED] h1", out)
        self.assertIn("already contains the WIP", out)
        self.assertEqual(rc, 0)

    def test_patch_on_top_of_wip_still_applies(self):
        self.write("flag.txt", "a-wip\nbroken\n")
        Path(self.caller, "fix.diff").write_text(self.ON_WIP)
        rc, out = self.run_exp(self.spec("grep -qx a-wip flag.txt && grep -qx fixed flag.txt"))
        self.assertIn("[CONFIRMED] h1", out)
        self.assertNotIn("already contains the WIP", out)
        self.assertEqual(rc, 0)
```

- [ ] **Step 6: Run the SD5 tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_experiment.py' -k PatchOrderTest`
Expected: FAIL with `FAILED (failures=3)`. `test_relative_patch_file_resolves_against_caller_cwd` and `test_patch_that_contains_wip_is_applied_on_head` show `AssertionError: '[CONFIRMED] h1' not found in` (the output reads `[INCONCLUSIVE] h1` with `patch did not apply`). `test_missing_patch_file_is_rejected_up_front` shows `AssertionError: 1 != 2`. `test_patch_on_top_of_wip_still_applies` passes.

- [ ] **Step 7: Resolve patch_file against the caller's cwd and skip the WIP when the patch contains it**

In `glm-skills/systematic-debugging-glm/scripts/debug_tool.py`, add this function directly above `def cmd_experiment(a):`:

```python
def apply_treatment_patch(wt, patch, wip_patch):
    """Apply patch on top of the WIP. If it does not apply there but applies on
    HEAD once the WIP is reversed, the patch already contains the WIP.
    Returns (ok, note)."""
    rc, out = sh("git apply %s" % shlex.quote(patch), cwd=wt, timeout=120)
    if rc == 0:
        return True, ""
    if wip_patch and os.path.getsize(wip_patch) > 0:
        rrc, _ = sh("git apply -R %s" % shlex.quote(wip_patch), cwd=wt, timeout=120)
        if rrc == 0:
            rc2, _ = sh("git apply %s" % shlex.quote(patch), cwd=wt, timeout=120)
            if rc2 == 0:
                return True, "patch already contains the WIP: applied on HEAD"
            sh("git apply %s" % shlex.quote(wip_patch), cwd=wt, timeout=120)
    return False, "patch did not apply: " + tail(out, 4)
```

In `cmd_experiment`, replace the validation loop:

```python fragment
    for i, h in enumerate(spec):
        h.setdefault("id", "h%d" % (i + 1))
        if not h.get("cmd"):
            print("hypothesis %s has no 'cmd'." % h["id"], file=sys.stderr)
            return 2
```

with:

```python fragment
    for i, h in enumerate(spec):
        h.setdefault("id", "h%d" % (i + 1))
        if not h.get("cmd"):
            print("hypothesis %s has no 'cmd'." % h["id"], file=sys.stderr)
            return 2
        if h.get("patch_file"):
            # resolve against the caller's cwd, never the arm's worktree
            pf = os.path.abspath(os.path.expanduser(str(h["patch_file"])))
            if not os.path.isfile(pf):
                print("hypothesis %s: patch_file %s not found (relative paths resolve "
                      "against %s)." % (h["id"], pf, os.getcwd()), file=sys.stderr)
                return 2
            h["patch_file"] = pf
```

In `run_arm`, replace the patch block:

```python fragment
        if side == "treatment" and h.get("patch_file"):
            rc, out = sh("git apply %s" % shlex.quote(h["patch_file"]), cwd=wt, timeout=120)
            if rc != 0:
                r["note"] = "patch did not apply: " + tail(out, 4)
                return r
```

with:

```python fragment
        if side == "treatment" and h.get("patch_file"):
            ok, note = apply_treatment_patch(wt, h["patch_file"], wip)
            r["note"] = note
            if not ok:
                return r
```

In the verdict loop, directly after the line `r["treatment"] = "%d/%d failed" % (t["fails"], t["runs"])`, add:

```python fragment
        arm_note = t.get("note", "")
```

and directly before the line `log = os.path.join(work, "log.%s.txt" % re.sub(r"\W+", "_", str(h["id"])))`, add:

```python fragment
        if arm_note:
            r["note"] = (r.get("note", "") + " (" + arm_note + ")").strip()
```

- [ ] **Step 8: Run the whole test file to verify it passes**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_experiment.py'`
Expected: PASS: `Ran 7 tests` then `OK`.

- [ ] **Step 9: Run the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no failure or error in `test_debug_experiment.py`, and no failures beyond those already present before this task.

- [ ] **Step 10: Commit**

```bash
git add glm-skills/systematic-debugging-glm/scripts/debug_tool.py glm-skills/_shared/tests/test_debug_experiment.py
git commit -m "fix(systematic-debugging): complete experiment worktrees and fix patch order

Copy untracked files and link ignored dependency dirs into every arm; a control
that does not reproduce is INCONCLUSIVE. Resolve patch_file against the caller's
cwd and apply a patch that already contains the WIP on HEAD."
```

---

### T18: debug_tool.py OpenCode lanes and scan context [P]

**Depends:** T03, T05

**Runs after:** T17 (same files)

**Interfaces:**
- Consumes: `def harness(script_path: str = "") -> str`; `def major(skill_dir: str = "", binary: str = "opencode") -> int`; `def dispatch_line(agent: str, prompt_path: str, description: str, major: int, background: bool = True) -> str`; `def config_snippet(major: int, deny: list) -> str`

**Files:**
- Modify: `glm-skills/systematic-debugging-glm/scripts/debug_tool.py`
- Modify: `glm-skills/_shared/tests/test_adopt_debug.py`

All commands run from `glm-skills/` (`cd glm-skills`). T17 edits the same two files before this task, so anchor every edit on the code shown here (function names and string literals), not on line numbers. This task covers spec rows SD6 (scan context), SD12 (setup snippet), SD13 (named agent, prompts under `<root>/.debug/`), SD14 (`S=` in prompts) and SD16 (`lanes.json` plus `NEXT: ... oc_harness.py run`).

- [ ] **Step 1: Write the failing tests for scan keywords, the area-scoped grep and code windows**

In `_shared/tests/test_adopt_debug.py`, insert these classes directly above the final `if __name__ == "__main__":` block:

```python
class TestQuestionKeywords(unittest.TestCase):
    def test_stopwords_dropped_and_order_kept(self):
        mod = load_debug_tool()
        assert mod.question_keywords("why does the parser drop the trailing token") == [
            "parser", "drop", "trailing", "token"]

    def test_limit_and_case_insensitive_dedupe(self):
        mod = load_debug_tool()
        assert mod.question_keywords("Parser parser alpha beta gamma delta", limit=3) == [
            "Parser", "alpha", "beta"]

    def test_no_question_gives_no_keywords(self):
        mod = load_debug_tool()
        assert mod.question_keywords(None) == []


class TestBuildTasksCodeWindows(unittest.TestCase):
    def test_area_prompt_carries_code_around_the_match(self):
        mod = load_debug_tool()
        root = tempfile.mkdtemp(prefix="sdscan_test.")
        self.addCleanup(mod.shutil.rmtree, root, True)
        pkg = Path(root) / "pkg"
        pkg.mkdir()
        (pkg / "parse.py").write_text(
            "def parse(text):\n"
            "    tokens = text.split()\n"
            "    return tokens[:-1]  # drops the trailing token\n")
        a = mod.argparse.Namespace(tasks=None, area=["pkg"],
                                   question="why does the parser drop the trailing token")
        tasks = mod.build_tasks(a, root)
        assert len(tasks) == 1
        prompt = tasks[0]["prompt"]
        assert "pkg/parse.py:3:" in prompt
        assert "CODE:" in prompt
        assert "return tokens[:-1]" in prompt.split("CODE:", 1)[1]


class TestBuildTasksGrepsAreaOnce(unittest.TestCase):
    def test_one_area_scoped_grep_per_area(self):
        mod = load_debug_tool()
        calls = []

        def fake_grep_area(root, area, words, cap):
            calls.append((area, list(words)))
            return ""

        def no_repo_wide_grep(*_a, **_k):
            raise AssertionError("build_tasks must not run a repo-wide grep per keyword")

        a = mod.argparse.Namespace(tasks=None, area=["src/a", "src/b"],
                                   question="why does the parser drop the trailing token")
        with patch.object(mod, "grep_area", fake_grep_area), \
                patch.object(mod, "grep", no_repo_wide_grep), \
                patch.object(mod, "sh", lambda *_a, **_k: (0, "x.py\n")):
            tasks = mod.build_tasks(a, ".")
        kw = ["parser", "drop", "trailing", "token"]
        assert calls == [("src/a", kw), ("src/b", kw)]
        assert [t["id"] for t in tasks] == ["src/a", "src/b"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_debug.py' -k QuestionKeywords -k BuildTasks`
Expected: FAIL, final line `FAILED (failures=1, errors=4)`: three `AttributeError: module 'debug_tool_under_test' has no attribute 'question_keywords'`, one `AttributeError` for the missing `grep_area`, and an `AssertionError` in `test_area_prompt_carries_code_around_the_match` because the prompt has no `CODE:` section.

- [ ] **Step 3: Implement stopword keywords, one area-scoped grep and capped code windows**

In `systematic-debugging-glm/scripts/debug_tool.py`, insert this block directly above `def build_tasks(a, root):`:

```python
SCAN_STOPWORDS = frozenset(
    "about after also because been before being cause caused causes could does doesn each "
    "error errors every fail failing fails failure from have here into just like made make "
    "makes more most only other over same should some such than that their them then there "
    "they this under used using very were what when where which while will with would wrong "
    "happen happens work works working".split())
SCAN_KEYWORDS = 5
SCAN_WINDOWS = 4
SCAN_WINDOW_CTX = 8
SCAN_CODE_CHARS = 6000


def question_keywords(question, limit=SCAN_KEYWORDS):
    """Content words of the question, stopwords dropped, first-seen order, deduped."""
    out, seen = [], set()
    for w in re.findall(r"[A-Za-z_][\w.]{3,}", question or ""):
        lw = w.lower()
        if lw in SCAN_STOPWORDS or lw in seen:
            continue
        seen.add(lw)
        out.append(w)
        if len(out) >= limit:
            break
    return out


def grep_area(root, area, words, cap):
    """ONE case-insensitive literal grep for all words, scoped to the area."""
    if not words:
        return ""
    pats = " ".join("-e %s" % shlex.quote(w) for w in words)
    if root and Path(root, ".git").exists():
        cmd = "git grep -I -n -i -F %s -- %s | head -%d" % (pats, shlex.quote(area), cap)
    else:
        cmd = ("grep -rIn -H -i -F %s %s --exclude-dir=node_modules --exclude-dir=.git "
               "--exclude-dir=dist --exclude-dir=build --exclude-dir=venv "
               "--exclude-dir=.venv --exclude-dir=target | head -%d"
               % (pats, shlex.quote(area), cap))
    rc, out = sh(cmd, cwd=root or ".", timeout=60)
    return out.strip()


def code_windows(root, hits, limit=SCAN_WINDOWS, ctx=SCAN_WINDOW_CTX, budget=SCAN_CODE_CHARS):
    """Numbered code around the first grep hits; overlapping hits share one window."""
    out, taken, used = [], [], 0
    for line in hits.split("\n"):
        m = re.match(r"([^:]+):(\d+):", line)
        if not m:
            continue
        rel, ln = m.group(1), int(m.group(2))
        if any(r == rel and abs(l - ln) <= ctx for r, l in taken):
            continue
        w = read_window(root, rel, ln, ctx)
        if used + len(w) > budget:
            break
        taken.append((rel, ln))
        out.append(w)
        used += len(w)
        if len(out) >= limit:
            break
    return "\n".join(out)
```

Then replace the whole body of `build_tasks` with:

```python
def build_tasks(a, root):
    if a.tasks:
        t = json.loads(Path(a.tasks).read_text())
        return [{"id": x.get("id", "t%d" % i), "prompt": x["prompt"]} for i, x in enumerate(t)]
    if not a.area:
        return []
    kw = question_keywords(a.question)
    out = []
    for area in a.area:
        rc, files = sh("git ls-files %s 2>/dev/null | head -60" % shlex.quote(area), cwd=root)
        if not files.strip():
            rc, files = sh("find %s -type f | head -60" % shlex.quote(area), cwd=root)
        hits = grep_area(root, area, kw, 30) if kw else ""
        code = code_windows(root, hits) if hits else ""
        out.append({"id": area, "prompt":
                    "AREA: %s\nFILES:\n%s\nMATCHES:\n%s\nCODE:\n%s\nQUESTION: %s\n"
                    "Read only what you were given. Name file:line for anything you claim."
                    % (area, head(files, 60), head(hits, 30), code or "(no match)",
                       a.question or "what here could cause the failure?")})
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_debug.py' -k QuestionKeywords -k BuildTasks`
Expected: PASS, final line `OK` (5 tests).

- [ ] **Step 5: Write the failing tests for the agent lane (named agent, `.debug/` prompts, `S=`, `lanes.json`)**

In `_shared/tests/test_adopt_debug.py`, insert this class directly above the final `if __name__ == "__main__":` block:

```python
class TestScanAgentLane(unittest.TestCase):
    def _run(self, harness_name):
        mod = load_debug_tool()
        root = tempfile.mkdtemp(prefix="sdlane_test.")
        self.addCleanup(mod.shutil.rmtree, root, True)
        tasks = Path(root) / "tasks.json"
        tasks.write_text(json.dumps([{"id": "t1", "prompt": "p1"}, {"id": "t2", "prompt": "p2"}]))
        a = mod.argparse.Namespace(
            tasks=str(tasks), area=None, question=None, context_file=None, context="shared ctx",
            tier="light", model=None, effort=None, base=None, max_tokens=100,
            print_prompts=False, out=None, jobs=0, dir=root)
        buf = io.StringIO()
        with patch.object(mod, "find_key", lambda: (None, "none")), \
                patch.object(mod.oc_harness, "harness", lambda *_a, **_k: harness_name), \
                patch.object(mod.oc_harness, "major", lambda *_a, **_k: 2):
            with redirect_stdout(buf):
                rc = mod.cmd_scan(a)
        return mod, rc, buf.getvalue(), Path(root) / ".debug" / "scan"

    def test_opencode_writes_lanes_for_debug_worker_under_project(self):
        mod, rc, out, d = self._run("opencode")
        assert rc == 0
        assert (d / "t1.txt").is_file() and (d / "t2.txt").is_file()
        lanes = json.loads((d / "lanes.json").read_text())
        assert [l["id"] for l in lanes] == ["t1", "t2"]
        assert [l["agent"] for l in lanes] == ["debug-worker", "debug-worker"]
        assert lanes[0]["brief"] == str((d / "t1.txt").resolve())
        assert "debug-worker" in out
        nxt = [l for l in out.splitlines() if l.startswith("NEXT: python3 ")]
        assert nxt and "oc_harness.py run" in nxt[-1]
        assert str(d / "lanes.json") in nxt[-1] or str((d / "lanes.json").resolve()) in nxt[-1]

    def test_prompts_carry_scripts_dir_in_a_byte_identical_prefix(self):
        mod, rc, out, d = self._run("opencode")
        t1 = (d / "t1.txt").read_text()
        t2 = (d / "t2.txt").read_text()
        assert t1.startswith(mod.SYS_PROMPT)
        assert ("S=%s" % mod.SCRIPTS) in t1
        assert t1.split("\n---\nTASK: ")[0] == t2.split("\n---\nTASK: ")[0]
        assert t1.endswith("TASK: p1") and t2.endswith("TASK: p2")

    def test_other_harness_names_the_agent_without_lanes_file(self):
        mod, rc, out, d = self._run("claude")
        assert rc == 0
        assert (d / "t1.txt").is_file()
        assert not (d / "lanes.json").exists()
        assert "debug-worker" in out
        assert "oc_harness.py run" not in out
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_debug.py' -k ScanAgentLane`
Expected: FAIL, final line `FAILED (errors=3)`, each with `AttributeError: <module 'debug_tool_under_test' ...> does not have the attribute 'oc_harness'`.

- [ ] **Step 7: Implement the named-agent lane with `lanes.json` on OpenCode**

In `systematic-debugging-glm/scripts/debug_tool.py`, directly below the line `import zai_client`, add:

```python
import oc_harness
WORKER_AGENT = "debug-worker"
```

In `cmd_scan`, replace the whole `if not key or a.print_prompts:` block (from that line through its `return 0`) with:

```python fragment
    if not key or a.print_prompts:
        # inside the project: no external_directory prompts for the workers
        d = Path(a.out) if a.out else Path(root) / ".debug" / "scan"
        d.mkdir(parents=True, exist_ok=True)
        # byte-identical prefix across workers; S= fills the agent's <scripts> placeholder
        prefix = SYS_PROMPT + "\n\nS=%s\n\n" % SCRIPTS + shared
        briefs = []
        for t in tasks:
            p = d / ("%s.txt" % re.sub(r"\W+", "_", t["id"]))
            p.write_text(prefix + "\n---\nTASK: " + t["prompt"])
            briefs.append((t["id"], str(p.resolve())))
        print("S=%s" % SCRIPTS)
        print("no API key found -- agent lane." if not key else "prompt files written.")
        if oc_harness.harness(str(Path(__file__).resolve())) == "opencode":
            mj = oc_harness.major(str(SKILL))
            lanes_file = d / "lanes.json"
            lanes_file.write_text(json.dumps(
                [{"id": tid, "agent": WORKER_AGENT, "brief": p} for tid, p in briefs], indent=2) + "\n")
            print("lanes: %s (%d x %s)" % (lanes_file, len(briefs), WORKER_AGENT))
            if mj >= 2:
                print("Or dispatch them as background subagents IN ONE message:")
                for tid, p in briefs:
                    print("  " + oc_harness.dispatch_line(WORKER_AGENT, p, "scan " + tid, mj,
                                                          background=True))
            print("Each worker answers in the VERDICT shape written at the top of its file.")
            print("NEXT: python3 %s/oc_harness.py run %s" % (SCRIPTS, shlex.quote(str(lanes_file))))
            return 0
        print("Dispatch these %d prompts as %s subagents IN ONE message (they are independent):"
              % (len(briefs), WORKER_AGENT))
        for tid, p in briefs:
            print("  %s: %s" % (WORKER_AGENT, p))
        print("Model for each worker: the cheap/fast tier. Each must answer in the VERDICT shape "
              "written at the top of its file.")
        print("NEXT: dispatch the %d %s subagents above in one message, then read their VERDICTs."
              % (len(briefs), WORKER_AGENT))
        return 0
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_debug.py' -k ScanAgentLane`
Expected: PASS, final line `OK` (3 tests).

- [ ] **Step 9: Write the failing tests for the shared OpenCode setup snippet**

In `_shared/tests/test_adopt_debug.py`, replace the existing class `TestCmdSetupMentionsOcHarness` with:

```python
class TestCmdSetupMentionsOcHarness(unittest.TestCase):
    def test_setup_opencode_mentions_oc_harness(self):
        mod = load_debug_tool()
        a = mod.argparse.Namespace(harness="opencode")
        buf = io.StringIO()
        with patch.object(mod.oc_harness, "major", lambda *_a, **_k: 2):
            with redirect_stdout(buf):
                rc = mod.cmd_setup(a)
        assert rc == 0
        assert "oc_harness.py run" in buf.getvalue()


class TestCmdSetupUsesSharedSnippet(unittest.TestCase):
    def test_setup_opencode_prints_shared_snippet_for_detected_major(self):
        mod = load_debug_tool()
        seen = {}

        def fake_snippet(major, deny):
            seen.update(major=major, deny=deny)
            return "SHARED-SNIPPET"

        a = mod.argparse.Namespace(harness="opencode", major=None)
        buf = io.StringIO()
        with patch.object(mod.oc_harness, "major", lambda *_a, **_k: 1), \
                patch.object(mod.oc_harness, "config_snippet", fake_snippet):
            with redirect_stdout(buf):
                rc = mod.cmd_setup(a)
        out = buf.getvalue()
        assert rc == 0
        assert out.startswith("SHARED-SNIPPET\n")
        assert seen == {"major": 1, "deny": []}
        assert '"zai":' not in out
        assert "one at a time" not in out
        assert "oc_harness.py run" in out

    def test_major_flag_skips_detection(self):
        mod = load_debug_tool()
        seen = {}

        def never(*_a, **_k):
            raise AssertionError("--major was given, detection must not run")

        def fake_snippet(major, deny):
            seen["major"] = major
            return "SHARED-SNIPPET"

        buf = io.StringIO()
        with patch.object(mod.oc_harness, "major", never), \
                patch.object(mod.oc_harness, "config_snippet", fake_snippet):
            with redirect_stdout(buf):
                rc = mod.main(["setup", "--harness", "opencode", "--major", "2"])
        assert rc == 0
        assert seen["major"] == 2
```

- [ ] **Step 10: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_debug.py' -k CmdSetup`
Expected: FAIL, final line `FAILED (failures=1, errors=1)`: an `AssertionError` in `test_setup_opencode_prints_shared_snippet_for_detected_major` (the output still starts with the old `zai` JSON), and a `SystemExit: 2` in `test_major_flag_skips_detection` with `unrecognized arguments: --major 2` on stderr.

- [ ] **Step 11: Implement setup through the shared snippet**

In `systematic-debugging-glm/scripts/debug_tool.py`, replace the whole `"opencode": """# ~/.config/opencode/opencode.json  (merge these keys)` entry of `SETUP` (through its closing `""",`, the line ending in `instead of a serial DISPATCH table."""`) with:

```python fragment
    "opencode": (
        "# export ZAI_API_KEY=<GLM Coding Plan key>\n"
        "# Skill goes in ~/.config/opencode/skills/systematic-debugging/ (or .opencode/skills/ per project).\n"
        "# Agent lane: without a key, `debug_tool.py scan` writes <root>/.debug/scan/lanes.json"
        " for the debug-worker agent.\n"
        "# Run every lane in parallel with: python3 <scripts>/oc_harness.py run"
        " <root>/.debug/scan/lanes.json"),
```

Replace `cmd_setup` with:

```python
def cmd_setup(a):
    if a.harness == "opencode":
        mj = getattr(a, "major", None) or oc_harness.major(str(SKILL))
        print(oc_harness.config_snippet(mj, []))
        print(SETUP["opencode"])
        return 0
    print(SETUP[a.harness])
    return 0
```

In `main`, in the `setup` subparser, directly below `q.add_argument("--harness", choices=list(SETUP), required=True)`, add:

```python fragment
    q.add_argument("--major", type=int, choices=[1, 2],
                   help="OpenCode major version (default: detected)")
```

- [ ] **Step 12: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_debug.py'`
Expected: PASS, final line `OK` (every test in the file, including the older `find_key`, `api_call` and `cmd_scan` client tests).

- [ ] **Step 13: Run the full suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: final line `OK`, with no failure in `test_adopt_debug.py`.

- [ ] **Step 14: Commit**

```bash
git add glm-skills/systematic-debugging-glm/scripts/debug_tool.py glm-skills/_shared/tests/test_adopt_debug.py
git commit -m "fix(systematic-debugging): scan code context, named debug-worker lanes, lanes.json and shared OpenCode setup snippet"
```

---

### T19: systematic-debugging shell script fixes [P]

**Depends:** —

**Files:**
- Modify: `glm-skills/systematic-debugging-glm/scripts/bisect-parallel.sh:32`
- Modify: `glm-skills/systematic-debugging-glm/scripts/stress.sh:26`
- Test: `glm-skills/_shared/tests/test_debug_scripts.py`

This task fixes SD9 and SD10. SD9: `bisect-parallel.sh -t SECONDS` is ignored without a word when neither `timeout` nor `gtimeout` is installed. It must print the same warning `stress.sh` already prints. SD10: `stress.sh -o DIR` on a directory that already holds `rc.*` / `FAIL.*` files from an earlier run counts those old results. The script must refuse (exit 2) and leave the old results alone, not delete them. All commands run from `glm-skills/` (`cd glm-skills` first).

- [ ] **Step 1: Write the failing test for the bisect `-t` warning (SD9)**

Create `glm-skills/_shared/tests/test_debug_scripts.py` with this content:

```python
"""Shell-level checks for systematic-debugging-glm/scripts (bisect-parallel.sh, stress.sh)."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "systematic-debugging-glm" / "scripts"
BISECT = SCRIPTS / "bisect-parallel.sh"
STRESS = SCRIPTS / "stress.sh"
BASH = shutil.which("bash")
TIMEOUT_WARNING = "warn: no timeout/gtimeout found; -t ignored"


def path_without_timeout(dest):
    """Fill dest with symlinks to every executable on PATH except timeout/gtimeout."""
    seen = set()
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d or not os.path.isdir(d):
            continue
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for name in names:
            if name in seen or name in ("timeout", "gtimeout"):
                continue
            src = os.path.join(d, name)
            if os.path.isfile(src) and os.access(src, os.X_OK):
                seen.add(name)
                os.symlink(src, os.path.join(dest, name))
    return dest


def git_env(tmp):
    env = dict(os.environ)
    env.update({
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_CONFIG_NOSYSTEM": "1", "HOME": tmp, "TMPDIR": tmp,
    })
    return env


def make_repo(tmp):
    """Two-commit repo: HEAD~1 is good, HEAD is bad."""
    repo = os.path.join(tmp, "repo")
    os.mkdir(repo)
    env = git_env(tmp)
    for args in (["init", "-q"], ):
        subprocess.run(["git"] + args, cwd=repo, env=env, check=True)
    for v in ("1", "2"):
        Path(repo, "v.txt").write_text(v + "\n")
        subprocess.run(["git", "add", "v.txt"], cwd=repo, env=env, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "v" + v], cwd=repo, env=env, check=True)
    return repo


@unittest.skipUnless(BASH and shutil.which("git"), "needs bash and git")
class BisectTimeoutWarningTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = make_repo(self.tmp)
        farm = os.path.join(self.tmp, "bin")
        os.mkdir(farm)
        self.env = git_env(self.tmp)
        self.env["PATH"] = path_without_timeout(farm)

    def run_bisect(self, *opts):
        cmd = [BASH, str(BISECT), "-j", "1", "--no-verify"] + list(opts) + ["HEAD~1", "HEAD", "--", "true"]
        return subprocess.run(cmd, cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=120)

    def test_t_without_timeout_binary_warns(self):
        r = self.run_bisect("-t", "5")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(TIMEOUT_WARNING, r.stderr)
        self.assertIn("FIRST BAD COMMIT", r.stdout)

    def test_no_t_no_warning(self):
        r = self.run_bisect()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn(TIMEOUT_WARNING, r.stderr)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_scripts.py' -v`
Expected: FAIL. `test_t_without_timeout_binary_warns` fails with `AssertionError: 'warn: no timeout/gtimeout found; -t ignored' not found in ...`. `test_no_t_no_warning` passes.

- [ ] **Step 3: Add the warning to `bisect-parallel.sh`**

In `glm-skills/systematic-debugging-glm/scripts/bisect-parallel.sh`, find the line that sets `TO`:

```bash
TO=$(sd_timeout_bin)
```

Replace it with this line, which uses the same message as `stress.sh`:

```bash
TO=$(sd_timeout_bin); [ -n "$T" ] && [ -z "$TO" ] && echo "warn: no timeout/gtimeout found; -t ignored" >&2
```

In the `usage()` heredoc, change the `-t` help line to:

```text
  -t SECONDS   timeout for the whole probe command (needs timeout/gtimeout, warns and is ignored without one); a timeout counts as bad (exit 124)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_scripts.py' -v`
Expected: PASS (`Ran 2 tests`, `OK`)

- [ ] **Step 5: Write the failing test for reusing `stress.sh -o DIR` (SD10)**

Add this class to `glm-skills/_shared/tests/test_debug_scripts.py`, just above the `if __name__ == "__main__":` line:

```python
@unittest.skipUnless(BASH, "needs bash")
class StressOutputDirReuseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.env = dict(os.environ, TMPDIR=self.tmp)
        self.out = os.path.join(self.tmp, "out")

    def run_stress(self, *cmd):
        argv = [BASH, str(STRESS), "-n", "2", "-j", "1", "-o", self.out, "--"] + list(cmd)
        return subprocess.run(argv, cwd=self.tmp, env=self.env, capture_output=True, text=True, timeout=120)

    def test_fresh_dir_runs(self):
        r = self.run_stress("true")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("RESULT: 0/2 failed", r.stdout)

    def test_reused_dir_after_pass_is_refused(self):
        self.assertEqual(self.run_stress("true").returncode, 0)
        r = self.run_stress("true")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("already holds stress results", r.stderr)
        self.assertNotIn("RESULT:", r.stdout)

    def test_old_fail_logs_are_kept_not_counted(self):
        os.mkdir(self.out)
        Path(self.out, "rc.1").write_text("1\n")
        Path(self.out, "FAIL.1.rc1.log").write_text("old failure\n")
        r = self.run_stress("true")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("already holds stress results", r.stderr)
        self.assertEqual(Path(self.out, "FAIL.1.rc1.log").read_text(), "old failure\n")
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_scripts.py' -v`
Expected: FAIL. `test_reused_dir_after_pass_is_refused` fails with `AssertionError: 0 != 2`. `test_old_fail_logs_are_kept_not_counted` fails with `AssertionError: 1 != 2`, because the old `FAIL.1` gets counted. `test_fresh_dir_runs` and both bisect tests pass.

- [ ] **Step 7: Make `stress.sh` refuse an output dir that already holds results**

In `glm-skills/systematic-debugging-glm/scripts/stress.sh`, find the line that creates the output dir:

```bash
[ -z "$OUT" ] && { OUT=$(mktemp -d "${TMPDIR:-/tmp}/stress.XXXXXX"); OWN_OUT=1; }; mkdir -p "$OUT"
```

Insert this block directly above it:

```bash
if [ -n "$OUT" ] && [ -d "$OUT" ] && ls -A "$OUT" 2>/dev/null | grep -q -e '^rc\.' -e '^FAIL\.' -e '^run\.'; then
  echo "error: -o $OUT already holds stress results (rc.*/FAIL.*/run.*); they would be counted. Use an empty dir or remove them first" >&2
  exit 2
fi
```

In the `usage()` heredoc, change the `-o` help line to:

```text
  -o  output dir (default: mktemp); must not already hold results of an earlier run (exit 2)
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug_scripts.py' -v`
Expected: PASS (`Ran 5 tests`, `OK`)

- [ ] **Step 9: Run the full suite and the shell syntax checks**

Run: `cd glm-skills && bash -n systematic-debugging-glm/scripts/bisect-parallel.sh && bash -n systematic-debugging-glm/scripts/stress.sh && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no output from `bash -n`. The suite ends with the 5 new tests passing, and every failure it lists was already failing before this task (the known stale-fixture reds).

- [ ] **Step 10: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add glm-skills/systematic-debugging-glm/scripts/bisect-parallel.sh glm-skills/systematic-debugging-glm/scripts/stress.sh glm-skills/_shared/tests/test_debug_scripts.py
git commit -m "fix(systematic-debugging): warn when bisect -t has no timeout binary; refuse reused stress -o dir"
```

---

### T20: systematic-debugging docs, agent and command for OpenCode [P]

**Depends:** T17, T18

**Files:**
- Modify: `glm-skills/systematic-debugging-glm/SKILL.md`
- Modify: `glm-skills/systematic-debugging-glm/opencode/agents/debug-worker.md`
- Modify: `glm-skills/systematic-debugging-glm/opencode/commands/debug.md`
- Modify: `glm-skills/systematic-debugging-glm/references/glm-tuning.md`
- Modify: `glm-skills/systematic-debugging-glm/README.md`

- [ ] **Step 1: Update SKILL.md bootstrap snippet to include OPENCODE_CONFIG_DIR**

Replace SKILL.md:15-21 (the R0 bootstrap code block) with:

```bash
for d in "${CLAUDE_SKILL_DIR:-}" "$OPENCODE_CONFIG_DIR/skills/systematic-debugging" .opencode/skills/systematic-debugging ~/.config/opencode/skills/systematic-debugging .claude/skills/systematic-debugging ~/.claude/skills/systematic-debugging .agents/skills/systematic-debugging ~/.agents/skills/systematic-debugging ~/.zcode/skills/systematic-debugging; do [ -f "$d/scripts/debug_tool.py" ] && S=$(cd "$d/scripts" && pwd) && break; done; echo "S=$S"
```

Expected: Bootstrap loop now checks OPENCODE_CONFIG_DIR per spec L93-96.

- [ ] **Step 2: Fix SKILL.md R3 step 2 placeholder wording**

Replace the second sentence of SKILL.md line 55 from:
```
2. Write the `ROOT CAUSE` line quoting a printed line → make the minimal fix → `python3 $S/debug_tool.py run '<the failing command>' '<its test file>'` in the same call. A fix that only reveals the *next* compile error is progress, not a failed fix.
```

To:
```
2. Write the `ROOT CAUSE` line quoting a printed line → make the minimal fix → `python3 $S/debug_tool.py run '<the failing command>' <path/to/test/file>` in the same call. A fix that only reveals the *next* compile error is progress, not a failed fix.
```

Expected: Placeholder no longer uses quoted `'<its test file>'` literal format (fixes SD8).

- [ ] **Step 3: Add setup snippet section to SKILL.md for zai-coding-plan variants**

Insert after SKILL.md line 82 (after R4 step 3, before R5 heading):

```
#### Setup snippet for OpenCode

```bash
python3 $S/debug_tool.py setup --harness opencode
```

This prints a provider block defining `variants` `low`/`high`/`max` (`reasoningEffort`) for `glm-5.3` and `glm-5.3-flash` under `zai-coding-plan`. Paste it into your OpenCode provider config. Without this, `#max` fails with "Variant unavailable" (fixes SD12).
```

Expected: SKILL.md includes setup snippet per spec L80.

- [ ] **Step 4: Update SKILL.md R5 step 4 to name debug-worker agent**

Replace SKILL.md:83 (R5 step 4 first sentence) to reference the agent by name. Change from:
```
4. Unknown location or many plausible causes → `python3 $S/debug_tool.py scan --area <pkg> --area <pkg> --question '<one question>' --context-file /tmp/evidence.txt`. It fans out to 64 workers itself, with one shared prefix so the cache hits from the second worker on. With no API key it writes the worker prompts to files and tells you to dispatch them as subagents instead — dispatch them all in one message. On OpenCode v2 (your `subagent` tool has a `background` param), instead dispatch each worker with `background: true`, one call after another without waiting, then end the turn — interactive sessions only, since a headless `opencode run` can exit before background children report.
```

To:
```
4. Unknown location or many plausible causes → `python3 $S/debug_tool.py scan --area <pkg> --area <pkg> --question '<one question>' --context-file /tmp/evidence.txt`. It fans out to 64 workers itself, with one shared prefix so the cache hits from the second worker on. With no API key it writes the worker prompts to files and tells you to dispatch them as subagents with the `debug-worker` agent instead — dispatch them all in one message. On OpenCode v2 (your `subagent` tool has a `background` param), instead dispatch each worker with the `debug-worker` agent and `background: true`, one call after another without waiting, then end the turn — interactive sessions only, since a headless `opencode run` can exit before background children report.
```

Expected: SKILL.md references the `debug-worker` agent by name (fixes SD13).

- [ ] **Step 5: Fix debug-worker.md placeholder variable**

Replace debug-worker.md:22 from:
```
4. For a flaky command, run both arms with the same `-n` and `-j` using `bash <scripts>/stress.sh`, and report the rates, not an impression.
```

To:
```
4. For a flaky command, run both arms with the same `-n` and `-j` using `bash $S/stress.sh`, and report the rates, not an impression.
```

Expected: `<scripts>` placeholder replaced with `$S` variable (fixes SD14).

- [ ] **Step 6: Update debug.md command to set S variable**

Replace debug.md:5-7 from:
```
Load the systematic-debugging skill with the provided arguments:

$ARGUMENTS
```

To:
```
Set the path to the skill scripts directory, then load the systematic-debugging skill:

S={{SKILL_DIR}}/scripts

$ARGUMENTS
```

Expected: `debug.md` defines `S={{SKILL_DIR}}/scripts` before skill invocation (fixes SD17).

- [ ] **Step 7: Verify all files are syntactically correct**

Run: `cd glm-skills && python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ['systematic-debugging-glm/SKILL.md', 'systematic-debugging-glm/opencode/agents/debug-worker.md', 'systematic-debugging-glm/opencode/commands/debug.md']]"`
Expected: No YAML parse errors on frontmatter sections.

- [ ] **Step 8: Verify bootstrap snippet uses correct format**

Run: `cd glm-skills && grep -A 5 'for d in' systematic-debugging-glm/SKILL.md | grep -q 'OPENCODE_CONFIG_DIR' && echo OK`
Expected: Output is `OK`

- [ ] **Step 9: Verify debug-worker agent definition is present**

Run: `cd glm-skills && grep -q 'debug-worker' systematic-debugging-glm/SKILL.md && echo OK`
Expected: Output is `OK`

- [ ] **Step 10: Verify S variable is defined in debug command**

Run: `cd glm-skills && grep 'S={{SKILL_DIR}}' systematic-debugging-glm/opencode/commands/debug.md && echo OK`
Expected: Output includes `S={{SKILL_DIR}}`

- [ ] **Step 11: Commit changes**

```bash
git add glm-skills/systematic-debugging-glm/SKILL.md glm-skills/systematic-debugging-glm/opencode/agents/debug-worker.md glm-skills/systematic-debugging-glm/opencode/commands/debug.md glm-skills/systematic-debugging-glm/references/glm-tuning.md glm-skills/systematic-debugging-glm/README.md
git commit -m "feat(systematic-debugging): OpenCode integration docs updates

Add OPENCODE_CONFIG_DIR to bootstrap snippet per shared contract.
Reference debug-worker agent by name in SKILL.md scan documentation.
Fill S variable placeholder in debug-worker.md stress.sh reference.
Add S={{SKILL_DIR}}/scripts to debug.md command definition.
Include setup snippet for zai-coding-plan variants in SKILL.md.
Reword test file placeholder in SKILL.md to prevent literal execution.

Fixes SD8, SD12, SD13, SD14, SD15, SD17."
```

---

### T21: audit.py retrieval and citation paths [P]

**Depends:** —

**Files:**
- Modify: `glm-skills/requirements-code-audit-glm/scripts/audit.py`
- Test: `glm-skills/_shared/tests/test_audit_retrieval.py`

This task fixes three retrieval and citation defects in `audit.py`:
- RA1: `is_doc` treats code files as prose.
- RA2: `lstrip("./")` mangles cited paths.
- RA3: the ripgrep globs are wrong.

Every command runs from `glm-skills/` (`cd glm-skills` first). Other tasks also edit `audit.py`, so find each edit by the code quoted below, not by line number.

- [ ] **Step 1: Write the failing test for prose classification (RA1)**

Create `_shared/tests/test_audit_retrieval.py`:

```python
"""audit.py retrieval and citation paths: is_doc, cited-path normalisation,
ripgrep globs (spec RA1-RA3)."""
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(
    HERE, "..", "..", "requirements-code-audit-glm", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
_spec = importlib.util.spec_from_file_location(
    "audit_retrieval_under_test", os.path.join(SCRIPTS, "audit.py"))
audit = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(audit)


def _write(root, rel, text):
    full = os.path.join(root, rel)
    d = os.path.dirname(full)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(full, "w", encoding="utf-8") as fh:
        fh.write(text)
    return full


class IsDocTest(unittest.TestCase):
    CODE = [
        "app/security.py", "src/to" "do.ts", "models/history.py", "pkg/support.go",
        "requirements.txt", "requirements-dev.txt", "blog/views.py",
        "site/app.js", "design/tokens.py", "book/models.rb", "security.py",
        "CMakeLists.txt",
    ]
    PROSE = [
        "README.md", "docs/guide.html", "notes.txt", "LICENSE", "CHANGELOG",
        "documentation/api.html", "wiki/Home.py", "adr/0001-choice.adoc",
        "src/README.rst", "handbook/onboarding.js",
    ]

    def test_code_files_with_doc_like_names_are_not_prose(self):
        for rel in self.CODE:
            self.assertFalse(audit.is_doc(rel), rel)

    def test_prose_by_extension_and_doc_dirs_is_still_prose(self):
        for rel in self.PROSE:
            self.assertTrue(audit.is_doc(rel), rel)

    def test_runtime_data_under_doc_dir_is_not_prose(self):
        self.assertFalse(audit.is_doc("docs/openapi.yaml"))
        self.assertFalse(audit.is_doc(".github/workflows/ci.yml"))

    def test_walk_repo_keeps_security_and_requirements(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root, True)
        _write(root, "app/security.py", "def check():\n    return True\n")
        _write(root, "requirements.txt", "flask==3.0\n")
        _write(root, "README.md", "readme text\n")
        rels = [r[0] for r in audit.walk_repo(root)]
        self.assertIn("app/security.py", rels)
        self.assertIn("requirements.txt", rels)
        self.assertNotIn("README.md", rels)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_retrieval.py' -k IsDocTest`
Expected: FAIL with `AssertionError: True is not false : app/security.py` in `test_code_files_with_doc_like_names_are_not_prose`, and `AssertionError: 'app/security.py' not found in` in `test_walk_repo_keeps_security_and_requirements`

- [ ] **Step 3: Classify prose by extension plus explicit doc dirs only**

In `requirements-code-audit-glm/scripts/audit.py`, replace the block that runs from `DOC_EXT = set(".md .markdown` through the end of the `DOC_DIRS = re.compile(...)` statement with the following. `RUNTIME_TXT` keeps the `.txt` files that pip, cmake and crawlers load. `DOC_NAME` now matches whole extension-less names only, so `security.py`, `history.py` and `support.go` count as code. `DOC_DIRS` lists explicit documentation trees only, because `blog/`, `site/`, `design/` and `book/` often hold application code.

```python
DOC_EXT = set(".md .markdown .mdx .rst .adoc .asciidoc .txt .rtf .org .wiki".split())
RUNTIME_TXT = re.compile(r"^(requirements|constraints)([-_.][\w.-]*)?\.txt$"
                         r"|^(cmakelists|robots|llms)\.txt$", re.I)
DOC_NAME = re.compile(
    r"^(readme|changelog|changes|history|contributing|code_of_conduct|license|licence"
    r"|copying|notice|authors|maintainers|to[d]o)$", re.I)
DOC_DIRS = re.compile(r"(^|/)(docs?|documentation|wiki|adrs?|rfcs?|handbook|"
                      r"\.github)(/|$)", re.I)
```

Then replace the whole `def is_doc(rel):` function with:

```python
def is_doc(rel):
    base = os.path.basename(rel)
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext in DOC_EXT:
        return not RUNTIME_TXT.match(base)
    if not ext and DOC_NAME.match(stem):
        return True
    if DOC_DIRS.search("/" + rel.replace(os.sep, "/")) and not RUNTIME_DATA.search(base):
        return True
    return False
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_retrieval.py' -k IsDocTest`
Expected: PASS (`Ran 4 tests` ... `OK`)

- [ ] **Step 5: Write the failing test for cited-path normalisation (RA2)**

Add this class to `_shared/tests/test_audit_retrieval.py`, directly above the `if __name__ == "__main__":` line:

```python
class CitePathTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        _write(self.root, ".eslintrc.json", '{\n  "rules": {}\n}\n')
        _write(self.root, "src/app.py", "a = 1\nb = 2\nc = 3\n")

    def _lint(self, path):
        row = {"status": "MATCHED", "confidence": "high", "notes": "n",
               "evidence": [{"path": path, "lines": "1-2", "note": "x"}]}
        return audit.lint_finding(row, {"id": "R1"}, self.root,
                                  {".eslintrc.json", "src/app.py"})

    def test_dotfile_keeps_its_leading_dot(self):
        out, errs, _ = self._lint(".eslintrc.json")
        self.assertEqual(errs, [])
        self.assertEqual(out["evidence"][0]["path"], ".eslintrc.json")

    def test_dot_slash_prefix_is_stripped(self):
        out, errs, _ = self._lint("./src/app.py")
        self.assertEqual(errs, [])
        self.assertEqual(out["evidence"][0]["path"], "src/app.py")

    def test_absolute_path_inside_root_becomes_relative(self):
        out, errs, _ = self._lint(os.path.join(self.root, "src", "app.py"))
        self.assertEqual(errs, [])
        self.assertEqual(out["evidence"][0]["path"], "src/app.py")

    def test_absolute_path_outside_root_is_rejected(self):
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other, True)
        outside = _write(other, "leak.py", "x = 1\ny = 2\n")
        out, errs, _ = self._lint(outside)
        self.assertEqual(out["evidence"], [])
        self.assertTrue(any("outside the codebase" in e for e in errs), errs)

    def test_norm_cite_path_helper(self):
        self.assertEqual(audit.norm_cite_path("././.env.example", self.root),
                         (".env.example", False))
        self.assertEqual(audit.norm_cite_path("", self.root), ("", False))
        self.assertEqual(audit.norm_cite_path(None, self.root), ("", False))
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_retrieval.py' -k CitePathTest`
Expected: FAIL. `test_dotfile_keeps_its_leading_dot` fails with `AssertionError: Lists differ: ['evidence path eslintrc.json does not exist in the codebase; ...`, and `test_norm_cite_path_helper` fails with `AttributeError: module 'audit_retrieval_under_test' has no attribute 'norm_cite_path'`

- [ ] **Step 7: Strip only the `./` prefix and resolve absolute paths**

In `requirements-code-audit-glm/scripts/audit.py`, add this function directly above `def lint_finding(`:

```python
def norm_cite_path(raw, root):
    """Normalise a cited evidence path to repo-relative form.

    Strips a leading "./" only, so a dotfile such as .eslintrc.json keeps its
    dot. An absolute path under root becomes relative. Returns (path, outside):
    outside is True for an absolute path that does not live under root."""
    path = str(raw or "").strip().replace(os.sep, "/")
    while path.startswith("./"):
        path = path[2:]
    if not path or not os.path.isabs(path):
        return path, False
    try:
        base = os.path.realpath(os.path.abspath(root))
        rel = os.path.relpath(os.path.realpath(path), base).replace(os.sep, "/")
    except ValueError:
        return path, True
    if rel == "." or rel == ".." or rel.startswith("../") or os.path.isabs(rel):
        return path, True
    return rel, False
```

Inside `lint_finding`, replace these four lines:

```python fragment
        path = str(e.get("path") or e.get("file") or "").strip().lstrip("./")
        path = path.replace(os.sep, "/")
        if not path:
            continue
```

with:

```python fragment
        path, outside = norm_cite_path(e.get("path") or e.get("file"), root)
        if not path:
            continue
        if outside:
            errs.append("evidence path %s is outside the codebase; cite repo-relative "
                        "paths shown in the excerpts" % path)
            continue
```

- [ ] **Step 8: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_retrieval.py' -k CitePathTest`
Expected: PASS (`Ran 5 tests` ... `OK`)

- [ ] **Step 9: Write the failing test for the ripgrep globs (RA3)**

Add these two classes to `_shared/tests/test_audit_retrieval.py`, directly above the `if __name__ == "__main__":` line:

```python
class _FakePopen(object):
    calls = []

    def __init__(self, args, **kw):
        _FakePopen.calls.append(list(args))

    def communicate(self, timeout=None):
        return b"", b""


def _bare_retriever(root, rg):
    r = audit.Retriever.__new__(audit.Retriever)
    r.root = root
    r.rg = rg
    r.files = []
    return r


class RgGlobArgsTest(unittest.TestCase):
    def _globs(self, **kw):
        _FakePopen.calls = []
        r = _bare_retriever(tempfile.gettempdir(), "rg")
        with mock.patch.object(audit.subprocess, "Popen", _FakePopen):
            r._rg(["retention"], **kw)
        args = _FakePopen.calls[-1]
        return [args[i + 1] for i, a in enumerate(args) if a == "--glob"]

    def test_data_only_globs(self):
        g = self._globs(data_only=True)
        self.assertIn("*.{yml,yaml}", g)
        self.assertNotIn("*.ya?ml", g)
        self.assertIn("**/migrations/**", g)
        self.assertNotIn("migrations/**", g)

    def test_tests_only_globs(self):
        g = self._globs(tests_only=True)
        self.assertIn("**/tests/**", g)
        self.assertIn("**/__tests__/**", g)
        self.assertNotIn("tests/**", g)


@unittest.skipUnless(shutil.which("rg"), "ripgrep not installed")
class RgGlobRealTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)
        _write(self.root, "config/app.yaml", "retention_days: 30\n")
        _write(self.root, "config/alt.yml", "retention_days: 7\n")
        _write(self.root, "pkg/db/migrations/0001_init.py", "retention_days = 30\n")
        _write(self.root, "pkg/tests/helpers.py", "retention_days = 1\n")
        _write(self.root, "src/core.py", "retention_days = 30\n")
        self.r = _bare_retriever(self.root, shutil.which("rg"))

    def test_data_only_finds_yaml_and_nested_migrations(self):
        paths = sorted(set(h[0] for h in self.r._rg(["retention_days"], data_only=True)))
        self.assertEqual(paths, ["config/alt.yml", "config/app.yaml",
                                 "pkg/db/migrations/0001_init.py"])

    def test_tests_only_finds_nested_tests_dir(self):
        paths = sorted(set(h[0] for h in self.r._rg(["retention_days"], tests_only=True)))
        self.assertEqual(paths, ["pkg/tests/helpers.py"])
```

- [ ] **Step 10: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_retrieval.py' -k RgGlob`
Expected: FAIL with `AssertionError: '*.{yml,yaml}' not found in` in `test_data_only_globs` and `AssertionError: '**/tests/**' not found in` in `test_tests_only_globs`. If `rg` is installed, the two `RgGlobRealTest` tests fail too, with `AssertionError: Lists differ`.

- [ ] **Step 11: Fix the ripgrep globs**

In `Retriever._rg` in `requirements-code-audit-glm/scripts/audit.py`, replace the `if tests_only:` and `if data_only:` blocks with:

```python fragment
        if tests_only:
            args += ["--glob", "*test*", "--glob", "*spec*", "--glob", "**/tests/**",
                     "--glob", "**/__tests__/**"]
        if data_only:
            args += ["--glob", "*.json", "--glob", "*.{yml,yaml}", "--glob", "*.sql",
                     "--glob", "*.toml", "--glob", "*.prisma", "--glob", "**/migrations/**",
                     "--glob", "*.xml", "--glob", "*.env*", "--glob", "*.conf"]
```

- [ ] **Step 12: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_retrieval.py'`
Expected: PASS (`Ran 13 tests` ... `OK`, or `OK (skipped=2)` when `rg` is not installed)

- [ ] **Step 13: Run the full suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: the only failures are the baseline stale-fixture failures (at most 11), and none of them are in `test_audit_retrieval.py`

- [ ] **Step 14: Commit**

```bash
cd ..
git add glm-skills/requirements-code-audit-glm/scripts/audit.py glm-skills/_shared/tests/test_audit_retrieval.py
git commit -m "fix(requirements-code-audit): prose by extension and doc dirs only, strip ./ prefix only, fix rg yaml/tests/migrations globs"
```

---

### T22: audit.py verdict pipeline [P]

**Depends:** —

**Runs after:** T21 (same files)

**Files:**
- Modify: `glm-skills/requirements-code-audit-glm/scripts/audit.py`
- Test: `glm-skills/_shared/tests/test_audit_verdicts.py`

This task fixes the api-lane verdict pipeline in `audit.py`: RA4 (pass-1 errors stamped on a clean pass-2 answer), RA5 (a rejected verdict still wins), RA18 (warm-up runs a whole `judge_one`), RA19 (truncated replies at `finish_reason == length`) and RA20 (`run --resume` re-verifies settled items and overwrites `verdicts.jsonl`). An earlier task edits the same file, so every edit below is anchored on code text, not on line numbers. All commands run from `glm-skills/` (`cd glm-skills`).

- [ ] **Step 1: Write the failing test for RA4 (clear pass-1 errors when pass 2 succeeds)**

Create `_shared/tests/test_audit_verdicts.py` with this content:

```python
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from argparse import Namespace

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.normpath(os.path.join(HERE, "..", "..", "requirements-code-audit-glm", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import audit  # noqa: E402


def _repo():
    d = tempfile.mkdtemp(prefix="audit-verdicts-")
    os.makedirs(os.path.join(d, "src"))
    with io.open(os.path.join(d, "src", "app.py"), "w", encoding="utf-8") as fh:
        fh.write(u"".join(u"line_%d = %d\n" % (i, i) for i in range(1, 11)))
    return d


class FakeRetr(object):
    def __init__(self, root):
        self.root = root

    def gather(self, it, tier, round2=False, extra_queries=None, tried=None):
        return {"snippets": [{"path": "src/app.py", "start": 1, "end": 5, "text": "line_1 = 1"}],
                "queries": ["round2_q" if round2 else "round1_q"],
                "considered": ["src/app.py"], "near_misses": [],
                "layers": ["symbol"], "chars": 10, "engine": "python"}

    def expand_region(self, rel, start, end):
        return None


class FakeCl(object):
    """Replies with the queued objects in order, then repeats the last one."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.log = []

    def call(self, model, effort, prefix, task, max_tokens, temperature=None, **kw):
        self.calls += 1
        self.log.append({"model": model, "effort": effort, "prefix": prefix,
                         "max_tokens": max_tokens, "kw": kw})
        r = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        return json.dumps(r)


ITEM = {"id": "REQ-001", "text": "Users can log in", "strength": "MUST",
        "stakes": "normal", "search_hints": ["login", "session"]}
BAD_MATCH = {"status": "MATCHED", "confidence": "low", "evidence": [], "notes": "no cite"}
GOOD_MATCH = {"status": "MATCHED", "confidence": "high",
              "evidence": [{"path": "src/app.py", "lines": "1-3", "note": "login"}],
              "notes": "found"}


class JudgeOneTest(unittest.TestCase):
    def setUp(self):
        self.repo = _repo()
        self.addCleanup(shutil.rmtree, self.repo, True)

    def test_clean_second_pass_clears_first_pass_errors(self):
        cl = FakeCl([BAD_MATCH, BAD_MATCH, BAD_MATCH, GOOD_MATCH])
        fix = audit.judge_one(None, cl, FakeRetr(self.repo), "PFX", dict(ITEM), "std", 1200)
        self.assertEqual(fix["status"], "MATCHED")
        self.assertNotIn("lint_error", fix)
        self.assertEqual(fix["passes"], 2)
        self.assertEqual(cl.calls, 4)

    def test_rejected_second_pass_keeps_errors_and_unsettles(self):
        cl = FakeCl([BAD_MATCH])
        fix = audit.judge_one(None, cl, FakeRetr(self.repo), "PFX", dict(ITEM), "std", 1200)
        self.assertEqual(fix["status"], "UNSEARCHED")
        self.assertTrue(fix["lint_error"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the RA4 test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_verdicts.py' -k JudgeOneTest`
Expected: FAIL: `test_clean_second_pass_clears_first_pass_errors` fails with `AssertionError: 'UNSEARCHED' != 'MATCHED'` and the run ends `FAILED (failures=1)`.

- [ ] **Step 3: Clear the errors when pass 2 is accepted**

In `requirements-code-audit-glm/scripts/audit.py`, inside `judge_one`, replace

```python fragment
            fix2, errs2, _w = lint_finding(row2, it, retr.root, paths)
            if not errs2:
                fix = fix2
```

with

```python fragment
            fix2, errs2, warns2 = lint_finding(row2, it, retr.root, paths)
            if not errs2:
                # RA4: the accepted pass-2 answer replaces pass 1 outright; pass-1
                # errors and warnings describe an answer that no longer exists.
                fix, errs, warns = fix2, [], warns2
```

- [ ] **Step 4: Run the RA4 tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_verdicts.py' -k JudgeOneTest`
Expected: PASS: `Ran 2 tests` then `OK`.

- [ ] **Step 5: Write the failing tests for RA5 (a rejected verdict is no verdict)**

Insert these classes into `_shared/tests/test_audit_verdicts.py`, directly above the `if __name__ == "__main__":` line:

```python
def _audit_dir(repo, verdict):
    out = tempfile.mkdtemp(prefix="audit-out-")
    with io.open(os.path.join(out, "config.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"repo_root": repo, "lane": "api", "tier": "std"}))
    finding = dict(GOOD_MATCH, id="REQ-001", confidence="medium")
    for name, row in (("checklist.jsonl", ITEM), ("findings.jsonl", finding),
                      ("verdicts.jsonl", verdict)):
        with io.open(os.path.join(out, name), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + u"\n")
    return out


REJECTED = {"id": "REQ-001", "verified_status": "MISSING", "confidence": "high",
            "evidence": [], "reason": "nothing", "lint_error": ["evidence path x does not exist"]}


class VerifyOneTest(unittest.TestCase):
    def setUp(self):
        self.repo = _repo()
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.prelim = dict(GOOD_MATCH, id="REQ-001", confidence="medium", searched=["round1_q"])

    def test_rejected_verdict_is_no_verdict(self):
        cl = FakeCl([{"verified_status": "MATCHED", "confidence": "high", "evidence": [],
                      "reason": "trust me", "agree": True}])
        v = audit.verify_one(None, cl, FakeRetr(self.repo), "VPFX", dict(ITEM),
                             self.prelim, "std", 1200)
        self.assertEqual(v["verified_status"], "UNSEARCHED")
        self.assertEqual(v["rejected_status"], "MATCHED")
        self.assertEqual(v["evidence"], [])
        self.assertTrue(v["lint_error"])
        self.assertEqual(cl.calls, 3)

    def test_accepted_verdict_is_kept(self):
        cl = FakeCl([{"verified_status": "MATCHED", "confidence": "high",
                      "evidence": [{"path": "src/app.py", "lines": "2-4"}],
                      "reason": "login at app.py", "agree": True}])
        v = audit.verify_one(None, cl, FakeRetr(self.repo), "VPFX", dict(ITEM),
                             self.prelim, "std", 1200)
        self.assertEqual(v["verified_status"], "MATCHED")
        self.assertNotIn("lint_error", v)


class MergedRejectedTest(unittest.TestCase):
    def test_rejected_verdict_row_falls_back_to_the_finding(self):
        repo = _repo()
        self.addCleanup(shutil.rmtree, repo, True)
        out = _audit_dir(repo, REJECTED)
        self.addCleanup(shutil.rmtree, out, True)
        m = audit.Merged(audit.Ctx(out))
        self.assertEqual(m.final("REQ-001"), ("MATCHED", "investigator"))
        self.assertNotIn("REQ-001", m.ver)
        self.assertIn("REQ-001", m.ver_rejected)
        self.assertEqual(m.evidence("REQ-001")[0]["path"], "src/app.py")


class CheckGateRejectedTest(unittest.TestCase):
    def test_gate_fails_on_an_unadjudicated_rejected_verdict(self):
        repo = _repo()
        self.addCleanup(shutil.rmtree, repo, True)
        out = _audit_dir(repo, REJECTED)
        self.addCleanup(shutil.rmtree, out, True)
        buf = io.StringIO()
        code = None
        with contextlib.redirect_stdout(buf):
            try:
                audit.cmd_check(Namespace(out=out))
            except SystemExit as e:
                code = e.code
        text = buf.getvalue()
        self.assertIn("rejected the verifier's answer", text)
        self.assertIn("GATE: FAIL", text)
        self.assertEqual(code, 2)
```

- [ ] **Step 6: Run the RA5 tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_verdicts.py' -k VerifyOneTest -k MergedRejectedTest -k CheckGateRejectedTest`
Expected: FAIL: `test_rejected_verdict_is_no_verdict` fails with `AssertionError: 'MATCHED' != 'UNSEARCHED'`, `test_rejected_verdict_row_falls_back_to_the_finding` fails with `AssertionError: Tuples differ: ('MISSING', 'verifier') != ('MATCHED', 'investigator')`, `test_gate_fails_on_an_unadjudicated_rejected_verdict` fails with `AssertionError: "rejected the verifier's answer" not found in ...`, and the run ends `FAILED (failures=3)`.

- [ ] **Step 7: Drop rejected verdicts in `verify_one`, `Merged`, `queue` and `check`**

In `verify_one`, replace

```python fragment
    fix["searched"] = (r2["queries"])[:40]
    if errs:
        fix["lint_error"] = errs[:4]
    return fix
```

with

```python fragment
    fix["searched"] = (r2["queries"])[:40]
    if errs:
        # RA5: a verdict the checker rejected is no verdict. Keep what it said
        # for the queue, but never let its status or evidence reach the merge.
        fix["lint_error"] = errs[:4]
        fix["rejected_status"] = fix.get("verified_status")
        fix["verified_status"] = "UNSEARCHED"
        fix["evidence"] = []
        fix["agree"] = False
    return fix
```

In `Merged.__init__`, replace

```python fragment
        self.ver = {}
        self.adj = {}
```

with

```python fragment
        self.ver = {}
        self.ver_rejected = {}
        self.adj = {}
```

In the same method, replace the two verdict loaders

```python fragment
        for r, _b in [read_jsonl(c.p("verdicts.jsonl"))]:
            for row in r:
                if row.get("id"):
                    self.ver[row["id"]] = row
        for name in sorted(os.listdir(c.p("verify")) if os.path.isdir(c.p("verify")) else []):
            if name.endswith(".jsonl"):
                rows, _b = read_jsonl(c.p("verify", name))
                for row in rows:
                    if row.get("id"):
                        self.ver[row["id"]] = row
```

with

```python fragment
        for r, _b in [read_jsonl(c.p("verdicts.jsonl"))]:
            for row in r:
                self._add_verdict(row)
        for name in sorted(os.listdir(c.p("verify")) if os.path.isdir(c.p("verify")) else []):
            if name.endswith(".jsonl"):
                rows, _b = read_jsonl(c.p("verify", name))
                for row in rows:
                    self._add_verdict(row)
```

and add this method to `Merged`, directly above `def final(self, rid):`:

```python fragment
    def _add_verdict(self, row):
        """RA5: a verdict row carrying lint_error was rejected by the checker.
        It is kept aside for the queue and the gate, never used as a verdict."""
        rid = row.get("id")
        if not rid:
            return
        if row.get("lint_error"):
            self.ver_rejected[rid] = row
            self.ver.pop(rid, None)
        else:
            self.ver[rid] = row
            self.ver_rejected.pop(rid, None)
```

In `cmd_queue`, replace

```python fragment
        if f.get("lint_error") or v.get("lint_error"):
```

with

```python fragment
        if f.get("lint_error") or rid in m.ver_rejected:
```

In `cmd_check`, replace

```python fragment
        if _tagged_unverifiable(it):
            continue
        if fs == "MISSING":
```

with

```python fragment
        if _tagged_unverifiable(it):
            continue
        if rid in m.ver_rejected and rid not in m.adj:
            errs.append("%s: the checker rejected the verifier's answer, so it has no second "
                        "pass -- adjudicate it or rerun: audit.py run --resume" % rid)
        if fs == "MISSING":
```

- [ ] **Step 8: Run the RA4 and RA5 tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_verdicts.py'`
Expected: PASS: `Ran 6 tests` then `OK`.

- [ ] **Step 9: Write the failing tests for RA19 (retry a reply cut off at the token cap)**

Insert this class into `_shared/tests/test_audit_verdicts.py`, directly above the `if __name__ == "__main__":` line:

```python
def _openai_reply(text, finish):
    return {"choices": [{"message": {"content": text}, "finish_reason": finish}], "usage": {}}


class LengthRetryTest(unittest.TestCase):
    def _client(self, replies, base="http://127.0.0.1:9", route="openai"):
        cl = audit.Client(base, "k" * 32, route)
        sent = []
        queue = list(replies)

        def fake_post(payload):
            sent.append(payload["max_tokens"])
            return queue.pop(0)

        cl._post = fake_post
        return cl, sent

    def test_length_stop_doubles_the_cap_until_the_reply_completes(self):
        cl, sent = self._client([_openai_reply("cut", "length"), _openai_reply("cut", "length"),
                                 _openai_reply("full", "stop")])
        text = cl.call(audit.FLASH, "high", "sys", "task", 1200)
        self.assertEqual(text, "full")
        self.assertEqual(sent, [1200, 2400, 4096])
        self.assertEqual(cl.truncated, 2)

    def test_no_retry_at_or_above_the_retry_cap(self):
        cl, sent = self._client([_openai_reply("cut", "length")])
        self.assertEqual(cl.call(audit.FLASH, "high", "sys", "task", audit.LENGTH_RETRY_CAP), "cut")
        self.assertEqual(sent, [audit.LENGTH_RETRY_CAP])

    def test_grow_false_never_retries(self):
        cl, sent = self._client([_openai_reply("cut", "length")])
        self.assertEqual(cl.call(audit.FLASH, "high", "sys", "task", 64, grow=False), "cut")
        self.assertEqual(sent, [64])
```

- [ ] **Step 10: Run the RA19 tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_verdicts.py' -k LengthRetryTest`
Expected: FAIL: `test_length_stop_doubles_the_cap_until_the_reply_completes` fails with `AssertionError: 'cut' != 'full'`, `test_no_retry_at_or_above_the_retry_cap` errors with `AttributeError: module 'audit' has no attribute 'LENGTH_RETRY_CAP'`, `test_grow_false_never_retries` errors with `TypeError: call() got an unexpected keyword argument 'grow'`, and the run ends `FAILED (failures=1, errors=2)`.

- [ ] **Step 11: Detect the length stop in the audit `Client` adapter and retry with a larger cap**

The vendored `zai_client` returns only the text, so the adapter records the stop reason by overriding `_done` (the base `call` passes every parsed response through it) in a thread-local, since one client is shared across the fan-out threads. In `audit.py`, directly above `class Client(zai_client.Client):`, add

Thinking tokens count against `max_tokens`, so a 900-1600 cap can cut the JSON answer off. A reply that stopped on the cap is retried with double the cap, up to `LENGTH_RETRY_CAP` (parse already asks for 8000 and is never grown).

```python
LENGTH_STOPS = ("length", "max_tokens")
LENGTH_RETRY_CAP = 4096
```

Then replace the whole `class Client(zai_client.Client):` definition (from that line down to the `return text or ""` that ends its `call` method) with

```python
class Client(zai_client.Client):
    """Transport, retries, 429/1302/1305 backoff and the shared AIMD width live
    in the vendored zai_client. This adapter keeps audit's call() shape and the
    per-run counters that run, parse and doctor print, and retries a reply that
    stopped on the token cap (RA19)."""

    def __init__(self, base, key, route=None, timeout=900):
        # route passed into __init__ (not set after) so self.url is computed from it
        zai_client.Client.__init__(self, key=key, base=base, route=route or route_of(base))
        self.timeout = timeout
        self.calls = 0
        self.in_tok = 0
        self.out_tok = 0
        self.cache_read = 0
        self.truncated = 0
        self._tl = threading.local()

    def _done(self, obj):
        fr = ""
        ch = obj.get("choices") if isinstance(obj, dict) else None
        if isinstance(ch, list) and ch and isinstance(ch[0], dict):
            fr = ch[0].get("finish_reason") or ""
        elif isinstance(obj, dict):
            fr = obj.get("stop_reason") or ""
        self._tl.finish = str(fr)
        return zai_client.Client._done(self, obj)

    def call(self, model, effort, prefix, task, max_tokens, temperature=None, retries=3,
             grow=True):
        mt = max_tokens
        while True:
            self._tl.finish = ""
            # explicit base-class call: self.call(...) would recurse into this override
            text = zai_client.Client.call(self, model, effort, prefix, task, mt,
                                           temperature=temperature, retries=retries)
            s = zai_client.Client.stats(self)  # shared-client's cumulative totals, not just this reply
            self.calls = s["calls"]
            self.in_tok = s["in_tok"]
            self.out_tok = s["out_tok"]
            self.cache_read = s["cache_read"]
            if grow and self._tl.finish in LENGTH_STOPS and mt < LENGTH_RETRY_CAP:
                mt = min(LENGTH_RETRY_CAP, mt * 2)
                with self._lock:
                    self.truncated += 1
                continue
            return text or ""
```

- [ ] **Step 12: Run the RA19 tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_verdicts.py' -k LengthRetryTest`
Expected: PASS: `Ran 3 tests` then `OK`.

- [ ] **Step 13: Write the failing tests for RA18 (warm the prefix with one call)**

Insert these classes into `_shared/tests/test_audit_verdicts.py`, directly above the `if __name__ == "__main__":` line:

```python
class FanWarmTest(unittest.TestCase):
    def _jobs(self, ran, n):
        return [("k%d" % i, (lambda i=i: ran.append(i) or i)) for i in range(n)]

    def test_callable_warm_makes_one_call_and_every_job_runs_once(self):
        warmed, ran = [], []
        res = audit.Fan(None, 4, quiet=True).run(self._jobs(ran, 6), "t",
                                                 warm=lambda: warmed.append(1))
        self.assertEqual(warmed, [1])
        self.assertEqual(sorted(ran), list(range(6)))
        self.assertEqual(res["k0"], (0, None))

    def test_failed_warm_call_does_not_stop_the_wave(self):
        ran = []

        def boom():
            raise RuntimeError("warm failed")

        fan = audit.Fan(None, 4, quiet=True)
        res = fan.run(self._jobs(ran, 6), "t", warm=boom)
        self.assertEqual(sorted(ran), list(range(6)))
        self.assertEqual(len(res), 6)
        self.assertEqual(fan.errors, [])

    def test_small_wave_skips_the_warm_call(self):
        warmed, ran = [], []
        audit.Fan(None, 4, quiet=True).run(self._jobs(ran, 3), "t",
                                           warm=lambda: warmed.append(1))
        self.assertEqual(warmed, [])
        self.assertEqual(sorted(ran), [0, 1, 2])


class WarmCallTest(unittest.TestCase):
    def test_warm_call_is_one_small_request_on_the_shared_prefix(self):
        cl = FakeCl([{}])
        audit.warm_call(cl, (audit.FLASH, "high"), "JUDGE-PREFIX")()
        self.assertEqual(cl.calls, 1)
        entry = cl.log[0]
        self.assertEqual((entry["model"], entry["effort"], entry["prefix"]),
                         (audit.FLASH, "high", "JUDGE-PREFIX"))
        self.assertEqual(entry["max_tokens"], 64)
        self.assertIs(entry["kw"].get("grow"), False)
```

- [ ] **Step 14: Run the RA18 tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_verdicts.py' -k FanWarmTest -k WarmCallTest`
Expected: FAIL: `test_callable_warm_makes_one_call_and_every_job_runs_once` fails with `AssertionError: Lists differ: [] != [1]`, `test_warm_call_is_one_small_request_on_the_shared_prefix` errors with `AttributeError: module 'audit' has no attribute 'warm_call'`, and the run ends `FAILED (failures=1, errors=1)`.

- [ ] **Step 15: Accept a warm-up callable in `Fan.run` and use it for waves A and B**

In `Fan.run`, replace the docstring and the warm-up block, from

```python fragment
        """jobs: [(key, fn)] where fn() -> result. Warms the shared prefix with
        one request so requests 2..N hit the prompt cache."""
```

to

```python fragment
        """jobs: [(key, fn)] where fn() -> result. warm is either a callable that
        makes exactly one cheap request on the shared prefix (RA18), so every
        job starts with the prefix cached, or True for the legacy warm-up that
        runs the first job alone before the rest."""
```

and replace

```python fragment
        start = 0
        if warm and total >= 6:
```

with

```python fragment
        start = 0
        if callable(warm):
            if total >= 6:
                try:
                    warm()
                except Exception as e:
                    if not self.quiet:
                        sys.stderr.write("  %s warm-up failed: %s\n" % (label, clip(str(e), 120)))
        elif warm and total >= 6:
```

Leave the body of the legacy branch (`k, f = jobs[0]` … `start = 1`) unchanged; `cmd_parse` still uses it.

Directly above the `# --------------------------------------------------------------------------- api lane waves` comment line, add

```python
WARM_TASK = u"Reply with the JSON object {} and nothing else."


def warm_call(cl, model_effort, prefix):
    """RA18: one small request that puts the wave's shared prefix in the prompt
    cache. Never grown on a length stop: only the cached prefix matters."""
    model, effort = model_effort
    return lambda: cl.call(model, effort, prefix, WARM_TASK, 64, temperature=0.0, grow=False)
```

In `cmd_run`, replace

```python fragment
    res = fan.run(jobs, "judged")
```

with

```python fragment
    res = fan.run(jobs, "judged", warm=warm_call(cl, c.tcfg["judge"], jp))
```

(the wave-B call is switched over in Step 19).

- [ ] **Step 16: Run the RA18 tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_verdicts.py' -k FanWarmTest -k WarmCallTest`
Expected: PASS: `Ran 4 tests` then `OK`.

- [ ] **Step 17: Write the failing tests for RA20 (`--resume` verifies only new ids)**

Insert this class into `_shared/tests/test_audit_verdicts.py`, directly above the `if __name__ == "__main__":` line:

```python
class VerifyTargetsTest(unittest.TestCase):
    ORDER = ["REQ-001", "REQ-002", "REQ-003", "REQ-004"]

    def _fixture(self):
        by_id = dict((rid, dict(ITEM, id=rid)) for rid in self.ORDER)
        findings = dict((rid, {"id": rid, "status": "MISSING", "confidence": "medium"})
                        for rid in self.ORDER)
        return by_id, findings

    def test_resume_keeps_settled_verdicts_and_verifies_the_rest(self):
        by_id, findings = self._fixture()
        done = dict((rid, findings[rid]) for rid in ("REQ-001", "REQ-002", "REQ-004"))
        prev_ver = {
            "REQ-001": {"id": "REQ-001", "verified_status": "MISSING"},
            "REQ-003": {"id": "REQ-003", "verified_status": "MATCHED"},
            "REQ-004": {"id": "REQ-004", "verified_status": "UNSEARCHED", "lint_error": ["x"]},
        }
        vset, kept = audit.verify_targets(self.ORDER, by_id, findings, done, prev_ver)
        self.assertEqual(vset, ["REQ-002", "REQ-003", "REQ-004"])
        self.assertEqual(kept, {"REQ-001": prev_ver["REQ-001"]})

    def test_fresh_run_verifies_what_needs_it(self):
        by_id, findings = self._fixture()
        findings["REQ-002"] = {"id": "REQ-002", "status": "MATCHED", "confidence": "high",
                               "passes": 2}
        vset, kept = audit.verify_targets(self.ORDER, by_id, findings, {}, {})
        self.assertEqual(vset, ["REQ-001", "REQ-003", "REQ-004"])
        self.assertEqual(kept, {})
```

- [ ] **Step 18: Run the RA20 tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_verdicts.py' -k VerifyTargetsTest`
Expected: FAIL: both tests error with `AttributeError: module 'audit' has no attribute 'verify_targets'` and the run ends `FAILED (errors=2)`.

- [ ] **Step 19: Add `verify_targets` and use it in `cmd_run`**

Directly below the `needs_verify` function (after its final `return False`), add

```python
def verify_targets(order, by_id, findings, done, prev_ver):
    """RA20: ids wave B must still verify, plus the verdicts a --resume keeps.
    A verdict is kept only when its finding was settled before this run (so
    the finding it judged is unchanged) and the checker accepted it."""
    kept = dict((rid, prev_ver[rid]) for rid in order
                if rid in done and rid in prev_ver and not prev_ver[rid].get("lint_error"))
    vset = [rid for rid in order
            if rid not in kept and needs_verify(by_id[rid], findings[rid])]
    return vset, kept
```

In `cmd_run`, replace the wave-B block, from

```python fragment
    by_id = dict((it["id"], it) for it in items)
    vset = [rid for rid in order if needs_verify(by_id[rid], findings[rid])]
```

down to and including

```python fragment
    elif a.no_verify:
        print("  skipped by --no-verify. The report will say so; MISSING items stay "
              "single-pass and `check` will fail.")
```

with

```python fragment
    by_id = dict((it["id"], it) for it in items)
    prev_ver = {}
    if a.resume:
        vrows, _b = read_jsonl(c.p("verdicts.jsonl"))
        prev_ver = dict((r["id"], r) for r in vrows if r.get("id"))
    vset, kept = verify_targets(order, by_id, findings, done, prev_ver)
    print("")
    print("WAVE B  %d of %d need an adversarial second pass  %s effort=%s%s"
          % (len(vset), len(order), c.tcfg["verify"][0], c.tcfg["verify"][1],
             ("  (%d verdict(s) kept from the last run)" % len(kept)) if kept else ""))
    verdicts = dict(kept)
    if vset and not a.no_verify:
        vjobs = []
        for rid in vset:
            def mkv(rid=rid):
                return lambda: verify_one(c, cl, retr, vp, by_id[rid], findings[rid],
                                          c.tier, mt)
            vjobs.append((rid, mkv()))
        vres = Fan(cl, c.threads).run(vjobs, "verified",
                                      warm=warm_call(cl, c.tcfg["verify"], vp))
        for rid, (row, err) in vres.items():
            if err is None:
                verdicts[rid] = row
            else:
                print("WARN  verify %s failed: %s" % (rid, clip(str(err), 120)))
    elif a.no_verify:
        print("  skipped by --no-verify. The report will say so; MISSING items stay "
              "single-pass and `check` will fail.")
    if verdicts or (vset and not a.no_verify):
        # kept + new verdicts together, so a --resume never drops settled ones
        write_jsonl(c.p("verdicts.jsonl"), [verdicts[i] for i in order if i in verdicts])
```

The `st["run"]` block below keeps `"wave_b": len(verdicts)`, which now counts the kept verdicts as well, so `check` does not warn "no second pass ran" after a resume that had nothing new to verify.

- [ ] **Step 20: Run the whole test file to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_verdicts.py'`
Expected: PASS: `Ran 15 tests` then `OK`.

- [ ] **Step 21: Run the full suite to check for regressions**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no failure or error in `test_audit_verdicts` and no new failure elsewhere. The only failures are the known stale-fixture ones present before this task (baseline 11).

- [ ] **Step 22: Commit**

```bash
cd ..
git add glm-skills/requirements-code-audit-glm/scripts/audit.py glm-skills/_shared/tests/test_audit_verdicts.py
git commit -m "fix(requirements-code-audit): verdict pipeline: clean pass 2 clears pass-1 errors, rejected verdict is no verdict, one-call warm-up, length-stop retry, resume keeps settled verdicts"
```

---

### T23: audit.py CLI state and resume [P]

**Depends:** —

**Runs after:** T22 (same files)

**Files:**
- Modify: `glm-skills/requirements-code-audit-glm/scripts/audit.py`
- Test: `glm-skills/_shared/tests/test_audit_command.py`

This task fixes five CLI state and resume defects in `audit.py`:
- RA9: `main` ignores the command's return code.
- RA7: `brief --spec-text` writes the pasted spec before the `--force` archive runs.
- RA6: `status` sends out verifiers again for ids that were already dispatched.
- RA8: agent-lane `run --resume` rebuilds every batch.
- RA20: api-lane `run --resume` re-verifies settled items and overwrites `verdicts.jsonl`.

All commands run from `glm-skills/` (`cd glm-skills` first). Anchor every edit on the quoted code, not on line numbers, because earlier edits to `audit.py` may have moved lines.

- [ ] **Step 1: Write the failing test for the setup exit code (RA9)**

In `_shared/tests/test_audit_command.py`, replace the import header (from `import os` through `import oc_harness`) with the block below. Keep `AUDIT_MD` and `TestAuditCommand` as they are.

```python
import contextlib
import glob
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(HERE, "..", "..", "requirements-code-audit-glm", "scripts")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(1, SCRIPTS)

import oc_harness
import audit

ITEMS = [
    {"id": "REQ-001", "text": "Login locks the account after 5 failed attempts",
     "strength": "MUST", "category": "auth", "stakes": "normal",
     "search_hints": ["login", "lockout"], "tags": []},
    {"id": "REQ-002", "text": "Export writes a CSV file",
     "strength": "MUST", "category": "export", "stakes": "normal",
     "search_hints": ["export", "csv"], "tags": []},
]


def _write_jsonl(path, rows):
    d = os.path.dirname(path)
    if not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + u"\n")


def _read_jsonl(path):
    with io.open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _read(path):
    with io.open(path, encoding="utf-8") as fh:
        return fh.read()


class _FakeClient(object):
    calls = 0
    in_tok = 0
    out_tok = 0
    cache_read = 0
```

Then insert this class directly above `if __name__ == "__main__":`:

```python
class TestAuditCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(self.repo)
        self.out = os.path.join(self.tmp, "audit")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _main(self, *argv):
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = audit.main(["--out", self.out] + list(argv))
        return rc, buf.getvalue()

    def _make_audit(self, lane, state=None):
        os.makedirs(self.out)
        cfg = {"version": audit.VERSION, "active": True, "repo_root": self.repo,
               "out_dir": self.out, "spec_files": [], "lang": "en", "lane": lane,
               "tier": "std", "threads": 8, "retrieval": "python"}
        with io.open(os.path.join(self.out, "config.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(cfg))
        _write_jsonl(os.path.join(self.out, "checklist.jsonl"), ITEMS)
        with io.open(os.path.join(self.out, "index.json"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"files": [], "symbols": {}, "routes": {}, "lines": {}}))
        with io.open(os.path.join(self.out, "repo-map.txt"), "w", encoding="utf-8") as fh:
            fh.write(u"files=0\n")
        if state is not None:
            with io.open(os.path.join(self.out, "state.json"), "w", encoding="utf-8") as fh:
                fh.write(json.dumps(state))

    def _state(self):
        with io.open(os.path.join(self.out, "state.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def test_setup_exit_code_is_nonzero_without_opencode(self):
        with mock.patch.object(oc_harness, "detect", return_value=None):
            rc, out = self._main("setup", "--harness", "opencode")
        self.assertIn("opencode not found", out)
        self.assertEqual(rc, 1)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_command.py' -k test_setup_exit_code_is_nonzero_without_opencode`
Expected: FAIL with "AssertionError: 0 != 1"

- [ ] **Step 3: Return the command's exit code from `main` (RA9)**

In `requirements-code-audit-glm/scripts/audit.py`, find the end of `main` and replace this block:

```python fragment
    try:
        a.fn(a)
    except KeyboardInterrupt:
        die("interrupted", 130)
    except BrokenPipeError:
        # output was piped into head/less; not an audit failure
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except Exception:
            pass
        return 0
    return 0
```

with:

```python fragment
    rc = 0
    try:
        rc = a.fn(a)
    except KeyboardInterrupt:
        die("interrupted", 130)
    except BrokenPipeError:
        # output was piped into head/less; not an audit failure
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except Exception:
            pass
        return 0
    return int(rc or 0)
```

The `if __name__ == "__main__":` block already calls `sys.exit(main())`, so `setup` now exits 1 when opencode is missing.

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_command.py' -k test_setup_exit_code_is_nonzero_without_opencode`
Expected: PASS (`OK`, 1 test)

- [ ] **Step 5: Write the failing tests for brief --spec-text ordering (RA7)**

Add these methods to `TestAuditCli`:

```python fragment
    def _brief(self, text, *extra):
        return self._main("brief", "--spec-text", text, "--repo", self.repo,
                          "--lane", "solo", *extra)

    def test_brief_without_force_keeps_the_old_pasted_spec(self):
        self._brief("OLD requirement text")
        pasted = os.path.join(self.out, "spec", "pasted-requirements.txt")
        with self.assertRaises(SystemExit):
            self._brief("NEW requirement text")
        self.assertEqual(_read(pasted), "OLD requirement text\n")

    def test_brief_force_archives_before_writing_the_pasted_spec(self):
        self._brief("OLD requirement text")
        self._brief("NEW requirement text", "--force")
        pasted = os.path.join(self.out, "spec", "pasted-requirements.txt")
        self.assertEqual(_read(pasted), "NEW requirement text\n")
        self.assertIn("NEW requirement text",
                      _read(os.path.join(self.out, "spec", "spec.txt")))
        prev = glob.glob(self.out + ".prev-*")
        self.assertEqual(len(prev), 1)
        self.assertEqual(_read(os.path.join(prev[0], "spec", "pasted-requirements.txt")),
                         "OLD requirement text\n")
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_command.py' -k test_brief_`
Expected: FAIL. `test_brief_without_force_keeps_the_old_pasted_spec` fails with "AssertionError: 'NEW requirement text\n' != 'OLD requirement text\n'", and `test_brief_force_archives_before_writing_the_pasted_spec` errors with "FileNotFoundError".

- [ ] **Step 7: Archive first, then write the pasted spec (RA7)**

In `cmd_brief`, replace the block that starts at `specs = list(a.spec or [])` and ends at the first `mk(out)`:

```python fragment
    specs = list(a.spec or [])
    if a.spec_text:
        mk(os.path.join(out, "spec"))
        p = os.path.join(out, "spec", "pasted-requirements.txt")
        write_text(p, a.spec_text)
        specs.append(p)
    if not specs:
        die("no requirements input. Pass --spec <file> (or --spec-text \"...\").")
    for s in specs:
        if not os.path.exists(s):
            die("spec not found: %s" % s)
    if os.path.exists(os.path.join(out, "config.json")) and not a.force:
        die("an audit already exists in %s (use --force to archive it)" % out)
    if a.force and os.path.isdir(out):
        prev = out + ".prev-" + time.strftime("%Y%m%d-%H%M%S")
        try:
            shutil.move(out, prev)
            sys.stderr.write("archived previous audit to %s\n" % prev)
        except Exception:
            pass
    mk(out)
```

with:

```python fragment
    specs = list(a.spec or [])
    if not specs and not a.spec_text:
        die("no requirements input. Pass --spec <file> (or --spec-text \"...\").")
    for s in specs:
        if not os.path.exists(s):
            die("spec not found: %s" % s)
    if os.path.exists(os.path.join(out, "config.json")) and not a.force:
        die("an audit already exists in %s (use --force to archive it)" % out)
    if a.force and os.path.isdir(out):
        prev = out + ".prev-" + time.strftime("%Y%m%d-%H%M%S")
        try:
            shutil.move(out, prev)
            sys.stderr.write("archived previous audit to %s\n" % prev)
        except Exception:
            pass
    # the pasted spec is written only after the refusal and the archive, so it
    # never clobbers a live audit and never gets moved into the .prev- copy
    if a.spec_text:
        mk(os.path.join(out, "spec"))
        p = os.path.join(out, "spec", "pasted-requirements.txt")
        write_text(p, a.spec_text)
        specs.append(p)
    mk(out)
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_command.py' -k test_brief_`
Expected: PASS (`OK`, 2 tests)

- [ ] **Step 9: Write the failing test for status re-dispatch (RA6)**

Add this method to `TestAuditCli`:

```python fragment
    def test_status_does_not_redispatch_verifiers_already_out(self):
        self._make_audit("agent")
        _write_jsonl(os.path.join(self.out, "findings", "batch-01.jsonl"), [
            {"id": "REQ-001", "status": "MISSING", "confidence": "low", "evidence": [],
             "searched": ["login"], "notes": "nothing found"}])
        _rc, first = self._main("status")
        self.assertIn("batch-V01", first)
        self.assertEqual(self._state()["vbatches"]["batch-V01"]["ids"], ["REQ-001"])
        _rc, second = self._main("status")
        self.assertNotIn("batch-V02", second)
        self.assertIn("waiting on 1 verifier result(s) already dispatched: REQ-001", second)
        _rc, third = self._main("status", "--redispatch")
        self.assertIn("batch-V02", third)
```

- [ ] **Step 10: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_command.py' -k test_status_does_not_redispatch_verifiers_already_out`
Expected: FAIL with "AssertionError: 'batch-V02' unexpectedly found in"

- [ ] **Step 11: Track dispatched verifier ids in `cmd_status` (RA6)**

In `cmd_status`, replace the `vset` assignment:

```python fragment
    vset = [i for i in live if i in have and needs_verify(by_id[i], m.find[i])
            and i not in m.ver]
```

with the block below. If the "has a verdict" condition in that assignment has since changed, keep the current conditions as they are and only append the `(redispatch or i not in dispatched)` clause.

```python fragment
    redispatch = bool(getattr(a, "redispatch", False))
    dispatched = set()
    for b in (st.get("vbatches") or {}).values():
        dispatched.update(b.get("ids") or [])
    pending = sorted(i for i in dispatched if i not in m.ver)
    vset = [i for i in live if i in have and needs_verify(by_id[i], m.find[i])
            and i not in m.ver and (redispatch or i not in dispatched)]
```

Still in `cmd_status`, find this code:

```python fragment
        print("NEXT after they report: audit.py status  (again), then audit.py queue")
        return
    cnt = m.counts()
```

Replace it with:

```python fragment
        print("NEXT after they report: audit.py status  (again), then audit.py queue")
        return
    if pending and not redispatch:
        print("")
        print("waiting on %d verifier result(s) already dispatched: %s"
              % (len(pending), ", ".join(pending[:20])))
        print("NEXT: when the verifiers report, run audit.py status again "
              "(audit.py status --redispatch re-packs them if a worker was lost)")
        return
    cnt = m.counts()
```

In `main`, add the flag to the status parser:

```python fragment
    p = sub.add_parser("status", help="agent lane: merge, pack verifiers, print NEXT")
    p.add_argument("--cap", type=int, default=None)
    p.add_argument("--redispatch", action="store_true",
                   help="re-pack verifiers that were dispatched but never reported")
    p.set_defaults(fn=cmd_status)
```

- [ ] **Step 12: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_command.py' -k test_status_does_not_redispatch_verifiers_already_out`
Expected: PASS (`OK`, 1 test)

- [ ] **Step 13: Write the failing test for agent-lane resume (RA8)**

Add this method to `TestAuditCli`:

```python fragment
    def test_agent_lane_resume_skips_finished_batches(self):
        state = {"batches": {
            "batch-01": {"ids": ["REQ-001"], "wave": "A", "dispatched": "earlier"},
            "batch-02": {"ids": ["REQ-002"], "wave": "A", "dispatched": "earlier"}}}
        self._make_audit("agent", state)
        _write_jsonl(os.path.join(self.out, "findings", "batch-01.jsonl"), [
            {"id": "REQ-001", "status": "MATCHED", "confidence": "high", "evidence": [],
             "notes": "done"}])
        _rc, out = self._main("run", "--resume")
        self.assertFalse(os.path.exists(os.path.join(self.out, "batches", "batch-01.md")))
        batches = self._state()["batches"]
        self.assertEqual(batches["batch-01"]["ids"], ["REQ-001"])
        self.assertNotIn("batch-02", batches)
        self.assertEqual(batches["batch-03"]["ids"], ["REQ-002"])
        self.assertTrue(os.path.exists(os.path.join(self.out, "batches", "batch-03.md")))
        self.assertIn("resume: 1 finished batch(es) kept, 1 requirement(s) to re-batch", out)
```

- [ ] **Step 14: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_command.py' -k test_agent_lane_resume_skips_finished_batches`
Expected: FAIL with "AssertionError: True is not false"

- [ ] **Step 15: Skip finished batches in `cmd_plan` on resume (RA8)**

In `audit.py`, add this helper directly above `def cmd_plan(a):`:

```python
def _plan_resume(c):
    """Agent-lane resume: keep every batch whose ids all have a final pass-1
    finding. Returns (kept batches, settled ids, first free batch number)."""
    st = c.state()
    old = st.get("batches") or {}
    m = Merged(c)
    settled = set(rid for rid, f in m.find.items()
                  if str(f.get("status") or "").upper() in FINAL_STATUSES)
    kept = {}
    for name, b in old.items():
        ids = b.get("ids") or []
        if ids and all(i in settled for i in ids):
            kept[name] = b
    nums = [batch_key(n)[0] for n in old]
    return kept, settled, (max(nums) + 1 if nums else 1)
```

In `cmd_plan`, replace:

```python fragment
    live = [it for it in items if not _tagged_unverifiable(it)]
    cap = int(a.cap or c.threads or 20)
```

with:

```python fragment
    live = [it for it in items if not _tagged_unverifiable(it)]
    kept, first = {}, 1
    if getattr(a, "resume", False):
        kept, settled, first = _plan_resume(c)
        live = [it for it in live if it["id"] not in settled]
        print("resume: %d finished batch(es) kept, %d requirement(s) to re-batch"
              % (len(kept), len(live)))
        if not live:
            st = c.state()
            st["batches"] = dict(kept)
            c.save_state(st)
            print("NEXT: audit.py status")
            return
    cap = int(a.cap or c.threads or 20)
```

Still in `cmd_plan`, replace `st["batches"] = {}` with:

```python fragment
    st["batches"] = dict(kept)
```

Then replace `for i, g in enumerate(groups, 1):` with:

```python fragment
    for i, g in enumerate(groups, first):
```

In `main`, add the flag to the plan parser:

```python fragment
    p = sub.add_parser("plan", help="agent lane: batch files with excerpts + dispatch list")
    p.add_argument("--cap", type=int, default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--resume", action="store_true",
                   help="keep finished batches, re-batch only unsettled ids")
    p.set_defaults(fn=cmd_plan)
```

`cmd_run` already hands its own `a` (which has `resume`) to `cmd_plan`, so `run --resume` on the agent lane now uses this path.

- [ ] **Step 16: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_command.py' -k test_agent_lane_resume_skips_finished_batches`
Expected: PASS (`OK`, 1 test)

- [ ] **Step 17: Write the failing test for api-lane resume verdicts (RA20)**

Add this method to `TestAuditCli`:

```python fragment
    def test_api_resume_verifies_only_ids_without_a_verdict(self):
        self._make_audit("api")
        _write_jsonl(os.path.join(self.out, "findings.jsonl"), [
            {"id": "REQ-001", "status": "MISSING", "confidence": "low", "evidence": [],
             "searched": ["login"], "notes": "none", "passes": 2}])
        _write_jsonl(os.path.join(self.out, "verdicts.jsonl"), [
            {"id": "REQ-001", "verified_status": "MISSING", "agree": True,
             "confidence": "high", "evidence": [], "reason": "kept from the first run",
             "searched": ["login"]}])
        called = []

        def fake_judge(*args, **kw):
            it = args[4]
            return {"id": it["id"], "status": "MISSING", "confidence": "low",
                    "evidence": [], "searched": ["export"], "notes": "none", "passes": 2}

        def fake_verify(*args, **kw):
            it = args[4]
            called.append(it["id"])
            return {"id": it["id"], "verified_status": "MISSING", "agree": True,
                    "confidence": "high", "evidence": [], "reason": "new pass",
                    "searched": ["export"]}

        with mock.patch.object(audit, "_client", return_value=_FakeClient()), \
                mock.patch.object(audit, "judge_one", side_effect=fake_judge), \
                mock.patch.object(audit, "verify_one", side_effect=fake_verify):
            self._main("run", "--resume")
        self.assertEqual(sorted(called), ["REQ-002"])
        verdicts = dict((r["id"], r) for r in
                        _read_jsonl(os.path.join(self.out, "verdicts.jsonl")))
        self.assertEqual(sorted(verdicts), ["REQ-001", "REQ-002"])
        self.assertEqual(verdicts["REQ-001"]["reason"], "kept from the first run")
```

- [ ] **Step 18: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_command.py' -k test_api_resume_verifies_only_ids_without_a_verdict`
Expected: FAIL with "AssertionError: Lists differ: ['REQ-001', 'REQ-002'] != ['REQ-002']"

- [ ] **Step 19: Keep settled verdicts and verify only ids without one (RA20)**

In `cmd_run`, replace:

```python fragment
    done = {}
    if a.resume:
        rows, _b = read_jsonl(c.p("findings.jsonl"))
        done = dict((r.get("id"), r) for r in rows
                    if r.get("status") in FINAL_STATUSES and not r.get("lint_error"))
        live = [it for it in live if it.get("id") not in done]
        print("resume: %d already settled, %d to do" % (len(done), len(live)))
```

with:

```python fragment
    done = {}
    prior_verdicts = {}
    if a.resume:
        rows, _b = read_jsonl(c.p("findings.jsonl"))
        done = dict((r.get("id"), r) for r in rows
                    if r.get("status") in FINAL_STATUSES and not r.get("lint_error"))
        live = [it for it in live if it.get("id") not in done]
        # a verdict survives only while the finding it judged is still the settled one
        vrows, _vb = read_jsonl(c.p("verdicts.jsonl"))
        prior_verdicts = dict((r.get("id"), r) for r in vrows if r.get("id") in done)
        print("resume: %d already settled (%d with a verdict), %d to do"
              % (len(done), len(prior_verdicts), len(live)))
```

Replace the Wave B selection:

```python fragment
    vset = [rid for rid in order if needs_verify(by_id[rid], findings[rid])]
```

with:

```python fragment
    vset = [rid for rid in order if rid not in prior_verdicts
            and needs_verify(by_id[rid], findings[rid])]
```

Then replace:

```python fragment
    verdicts = {}
    if vset and not a.no_verify:
```

with:

```python fragment
    verdicts = dict(prior_verdicts)
    if vset and not a.no_verify:
```

The existing `write_jsonl(c.p("verdicts.jsonl"), [verdicts[i] for i in order if i in verdicts])` now writes the kept verdicts together with the new ones, so a resume no longer drops earlier results.

- [ ] **Step 20: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_command.py' -k test_api_resume_verifies_only_ids_without_a_verdict`
Expected: PASS (`OK`, 1 test)

- [ ] **Step 21: Run the whole test file and the full suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_command.py'`
Expected: `OK`. Every test in the file passes, the original `TestAuditCommand` tests included.

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no failure or error in `test_audit_command.py`, and no test that passed before this task fails now.

- [ ] **Step 22: Commit**

```bash
cd ..
git add glm-skills/requirements-code-audit-glm/scripts/audit.py glm-skills/_shared/tests/test_audit_command.py
git commit -m "fix(requirements-code-audit): CLI exit codes, brief archive order, resume keeps finished batches and verdicts, status tracks dispatched verifiers"
```

---

### T24: audit.py OpenCode dispatch and batch sizing [P]

**Depends:** T03, T04

**Runs after:** T23 (same files)

**Interfaces:**
- Consumes: `def harness(script_path: str = "") -> str`; `def major(skill_dir: str = "", binary: str = "opencode") -> int`; `def dispatch_line(agent: str, prompt_path: str, description: str, major: int, background: bool = True) -> str`; `python3 oc_harness.py result OUT_DIR`

**Files:**
- Modify: `glm-skills/requirements-code-audit-glm/scripts/audit.py:2408-2586`
- Modify: `glm-skills/_shared/tests/test_audit_setup_oc.py:1-89`

All commands run from `glm-skills/` (`cd glm-skills`). T23 edits `audit.py` and this test file before you, so find each edit by the code quoted below, not only by line number.

Routing after this task (agent lane only; the api lane is unchanged):
- OpenCode v2: one background `subagent(...)` line per batch, built by `oc_harness.dispatch_line`.
- OpenCode v1: no per-batch `task` lines. Instead audit.py writes `<audit dir>/oc-lanes/wave-<name>.json` (one lane per batch) and prints exactly one line, `NEXT: python3 <abs scripts dir>/oc_harness.py run <json> --out <audit dir>/oc-lanes/<name>`. That runs every lane in parallel, one opencode process per lane. After the lanes finish, `audit.py status` is re-run as today.
- Other harnesses: `subagent_type=<agent>  prompt: ...` with no model alias.

- [ ] **Step 1: Write the failing dispatch tests**

In `_shared/tests/test_audit_setup_oc.py`, add `import json` directly below `import io`. Then insert these classes directly above the final `if __name__ == "__main__":` block. Keep every existing class.

```python
class AgentLaneDispatchLine(unittest.TestCase):
    def test_opencode_v2_uses_shared_dispatch_line(self):
        with mock.patch.object(oc_harness, "harness", return_value="opencode"), \
             mock.patch.object(oc_harness, "major", return_value=2):
            line = audit._dispatch("rca-investigator", "/a/batch-01.md", "rca batch-01")
        want = oc_harness.dispatch_line("rca-investigator", "/a/batch-01.md", "rca batch-01", 2,
                                        background=True)
        self.assertEqual(line, want)
        self.assertNotIn("haiku", line)
        self.assertNotIn("sonnet", line)

    def test_unknown_major_falls_back_to_v1_dialect(self):
        with mock.patch.object(oc_harness, "harness", return_value="opencode"), \
             mock.patch.object(oc_harness, "major", return_value=0):
            line = audit._dispatch("rca-verifier", "/a/b.md", "rca b")
        want = oc_harness.dispatch_line("rca-verifier", "/a/b.md", "rca b", 1, background=True)
        self.assertEqual(line, want)

    def test_non_opencode_line_names_no_model_alias(self):
        with mock.patch.object(oc_harness, "harness", return_value="zcode"):
            line = audit._dispatch("rca-investigator", "/a/b.md", "rca b")
        self.assertEqual(line, "subagent_type=rca-investigator  prompt: read /a/b.md and follow it exactly")

    def test_source_no_longer_prints_model_alias_dispatch(self):
        with open(os.path.join(SCRIPTS, "audit.py")) as fh:
            src = fh.read()
        self.assertNotIn("model=%s  prompt", src)


class V1LaneDispatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        tmp = self.tmp

        class FakeCtx(object):
            tcfg = audit.TIERS["std"]

            def p(self, *parts):
                return os.path.join(tmp, *parts)

        self.c = FakeCtx()
        self.lanes_dir = os.path.join(tmp, "oc-lanes")
        self.batches = [("batch-01", os.path.join(tmp, "batches", "batch-01.md")),
                        ("batch-02", os.path.join(tmp, "batches", "batch-02.md"))]

    def dispatch(self, major, agent, role, wave):
        buf = io.StringIO()
        with mock.patch.object(oc_harness, "harness", return_value="opencode"), \
             mock.patch.object(oc_harness, "major", return_value=major), \
             redirect_stdout(buf):
            audit._print_dispatch(self.c, wave, self.batches, agent, role, "DISPATCH")
        return buf.getvalue()

    def load(self, wave):
        with open(os.path.join(self.lanes_dir, "wave-%s.json" % wave)) as fh:
            return json.load(fh)

    def test_v1_investigators_write_lanes_json_and_one_next_line(self):
        out = self.dispatch(1, "rca-investigator", "judge", "A")
        lanes = self.load("A")
        self.assertEqual([lane["id"] for lane in lanes], ["batch-01", "batch-02"])
        for lane, (_, p) in zip(lanes, self.batches):
            self.assertEqual(lane["agent"], "rca-investigator")
            self.assertEqual(lane["model"], "flash")
            self.assertEqual(lane["effort"], "high")
            self.assertEqual(lane["brief"], os.path.abspath(p))
            self.assertEqual(lane["dir"], os.path.abspath(os.getcwd()))
        nexts = [line for line in out.splitlines() if line.startswith("NEXT:")]
        want = "NEXT: python3 %s run %s --out %s" % (
            os.path.join(SCRIPTS, "oc_harness.py"),
            os.path.join(self.lanes_dir, "wave-A.json"),
            os.path.join(self.lanes_dir, "A"))
        self.assertEqual(nexts, [want])
        self.assertNotIn("task(", out)
        self.assertNotIn("subagent_type=", out)

    def test_v1_verifiers_use_verify_tier(self):
        self.dispatch(1, "rca-verifier", "verify", "V01")
        lanes = self.load("V01")
        self.assertEqual(len(lanes), 2)
        for lane in lanes:
            self.assertEqual(lane["agent"], "rca-verifier")
            self.assertEqual(lane["model"], "pro")
            self.assertEqual(lane["effort"], "max")

    def test_v2_prints_background_subagent_lines_and_writes_no_lanes(self):
        out = self.dispatch(2, "rca-investigator", "judge", "A")
        for name, p in self.batches:
            want = oc_harness.dispatch_line("rca-investigator", p, "rca " + name, 2,
                                            background=True)
            self.assertIn("  " + want, out)
        self.assertFalse(os.path.exists(self.lanes_dir))
        self.assertNotIn("oc_harness.py run", out)
```

- [ ] **Step 2: Run the dispatch tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_setup_oc.py' -k Dispatch`
Expected: FAIL with "AttributeError: module 'audit' has no attribute '_dispatch'" (and "AttributeError: module 'audit' has no attribute '_print_dispatch'"; the source test fails with "'model=%s  prompt' unexpectedly found")

- [ ] **Step 3: Add the harness and dispatch helpers to audit.py**

In `requirements-code-audit-glm/scripts/audit.py`, insert this block directly above `def cmd_plan(a):`. `mk`, `write_text`, `FLASH` and `PRO` already exist in the file.

```python
OC_MODEL = {FLASH: "flash", PRO: "pro"}  # oc_harness run lane model names


def _oc():
    try:
        import oc_harness  # vendored next to this script by _shared/sync.sh
    except ImportError:
        return None
    return oc_harness


def _on_opencode():
    oc = _oc()
    return bool(oc) and oc.harness(os.path.abspath(__file__)) == "opencode"


def _oc_major():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    m = _oc().major(skill_dir=root)
    return m if m >= 2 else 1


def _oc_script():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "oc_harness.py")


def _dispatch(agent, prompt_path, description):
    """One dispatch line for the agent lane. Never names a model alias."""
    if _on_opencode():
        return _oc().dispatch_line(agent, prompt_path, description, _oc_major(),
                                   background=True)
    return u"subagent_type=%s  prompt: read %s and follow it exactly" % (agent, prompt_path)


def _oc_lane_wave(lanes_dir, name, batches, agent, model, effort, repo):
    """Write lanes_dir/wave-<name>.json (one lane per batch); return the NEXT line."""
    lanes_dir = os.path.abspath(lanes_dir)
    mk(lanes_dir)
    lanes = [{"id": b, "agent": agent, "model": OC_MODEL.get(model, model),
              "effort": effort, "dir": os.path.abspath(repo), "brief": os.path.abspath(p)}
             for b, p in batches]
    path = os.path.join(lanes_dir, "wave-%s.json" % name)
    write_text(path, json.dumps(lanes, indent=2, ensure_ascii=False) + u"\n")
    return u"NEXT: python3 %s run %s --out %s" % (_oc_script(), path,
                                                   os.path.join(lanes_dir, name))


def _print_dispatch(c, wave, batches, agent, role, header):
    """OpenCode v1: one oc_harness run command for the whole wave (parallel lanes).
    Everywhere else: one dispatch line per batch."""
    if _on_opencode() and _oc_major() == 1:
        model, effort = c.tcfg[role][0], c.tcfg[role][1]
        print(header + " -- OpenCode v1: one opencode process per lane, all in parallel:")
        print(_oc_lane_wave(c.p("oc-lanes"), wave, batches, agent, model, effort,
                            os.getcwd()))
        return
    print(header + " -- emit ALL of these in ONE message (they are independent):")
    print("  ZCode: subagents launched together run in parallel.")
    print("  OpenCode v2: background subagent calls run in parallel.")
    for name, p in batches:
        print("  " + _dispatch(agent, p, "rca " + name))
```

- [ ] **Step 4: Route the plan dispatch through `_print_dispatch`**

In `cmd_plan`, replace this block:

```python fragment
    print("DISPATCH -- emit ALL of these in ONE message (they are independent):")
    print("  ZCode: subagents launched together run in parallel.")
    print("  OpenCode: it dispatches them one at a time; that is an OpenCode limitation,")
    print("  not a plan problem -- the api lane exists precisely to avoid it.")
    for name, p in lines:
        print("  subagent_type=rca-investigator model=%s  prompt: read %s and follow it exactly"
              % (AGENT_ALIAS[c.tcfg["judge"][0]], p))
```

with:

```python fragment
    _print_dispatch(c, "A", lines, "rca-investigator", "judge", "DISPATCH")
```

Keep the `print("")` and `print("NEXT after the workers report: audit.py status")` lines after it.

- [ ] **Step 5: Route the verifier dispatch through `_print_dispatch`**

In `cmd_status`, inside `if vset:`, replace:

```python fragment
        print("")
        print("DISPATCH verifiers -- ONE message:")
```

with:

```python fragment
        vlines = []
```

In the same `for j, g in enumerate(groups, idx + 1):` loop, replace:

```python fragment
            print("  subagent_type=rca-verifier model=%s  prompt: read %s and follow it exactly"
                  % (AGENT_ALIAS[c.tcfg["verify"][0]], p))
```

with:

```python fragment
            vlines.append((name, p))
```

Then, directly after the loop and before `c.save_state(st)`, insert:

```python fragment
        print("")
        _print_dispatch(c, "V%02d" % (idx + 1), vlines, "rca-verifier", "verify",
                        "DISPATCH verifiers")
```

Leave the `AGENT_ALIAS` constant in place; nothing prints it any more.

- [ ] **Step 6: Run the dispatch tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_setup_oc.py' -k Dispatch`
Expected: PASS (`Ran 7 tests` ... `OK`)

- [ ] **Step 7: Write the failing batch-sizing tests**

Insert this class directly above the final `if __name__ == "__main__":` block in `_shared/tests/test_audit_setup_oc.py`.

```python
class AgentLaneBatchSizing(unittest.TestCase):
    def env(self, value=None):
        patch = mock.patch.dict(os.environ, {}, clear=False)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("OC_MAX_LANES", None)
        if value is not None:
            os.environ["OC_MAX_LANES"] = value

    def test_even_groups_balances_sizes_and_keeps_order(self):
        groups = audit._even_groups(list(range(10)), 3)
        self.assertEqual([len(g) for g in groups], [4, 3, 3])
        self.assertEqual(sum(groups, []), list(range(10)))

    def test_even_groups_of_nothing_is_empty(self):
        self.assertEqual(audit._even_groups([], 8), [])

    def test_opencode_caps_batch_count_at_default_lane_width(self):
        self.env()
        groups = audit._agent_groups(list(range(64)), 64, 12, True)
        self.assertEqual([len(g) for g in groups], [8] * 8)

    def test_opencode_honours_oc_max_lanes(self):
        self.env("3")
        groups = audit._agent_groups(list(range(10)), 64, 12, True)
        self.assertEqual([len(g) for g in groups], [4, 3, 3])

    def test_bad_oc_max_lanes_falls_back(self):
        self.env("many")
        self.assertEqual(audit._oc_lanes(), 8)
        self.env("0")
        self.assertEqual(audit._oc_lanes(), 1)

    def test_opencode_fewer_items_than_lanes_gives_one_each(self):
        self.env()
        groups = audit._agent_groups(list(range(5)), 64, 12, True)
        self.assertEqual([len(g) for g in groups], [1] * 5)

    def test_non_opencode_keeps_fixed_chunking(self):
        groups = audit._agent_groups(list(range(64)), 20, 12, False)
        self.assertEqual([len(g) for g in groups], [4] * 16)
        small = audit._agent_groups(list(range(7)), 20, 12, False)
        self.assertEqual([len(g) for g in small], [1] * 7)

    def test_empty_input_gives_no_batches(self):
        self.assertEqual(audit._agent_groups([], 20, 12, True), [])
        self.assertEqual(audit._agent_groups([], 20, 12, False), [])
```

- [ ] **Step 8: Run the batch-sizing tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_setup_oc.py' -k AgentLaneBatchSizing`
Expected: FAIL with "AttributeError: module 'audit' has no attribute '_even_groups'"

- [ ] **Step 9: Add the grouping helpers to audit.py**

Insert this block directly below the `_print_dispatch` function added in Step 3 (still above `def cmd_plan(a):`).

```python
def _oc_lanes():
    """OpenCode lane width: OC_MAX_LANES, default 8, never below 1."""
    try:
        n = int(os.environ.get("OC_MAX_LANES") or 8)
    except ValueError:
        n = 8
    return max(1, n)


def _even_groups(items, n):
    """Split items, in order, into n groups whose sizes differ by at most one."""
    if not items:
        return []
    n = max(1, min(n, len(items)))
    q, r = divmod(len(items), n)
    out, i = [], 0
    for k in range(n):
        j = i + q + (1 if k < r else 0)
        out.append(items[i:j])
        i = j
    return out


def _agent_groups(items, cap, max_per, opencode):
    """Agent-lane batches. OpenCode: at most _oc_lanes() batches, grouped evenly.
    Elsewhere: fixed chunks of 1..max_per items so at most cap batches."""
    if not items:
        return []
    if opencode:
        return _even_groups(items, min(len(items), cap, _oc_lanes()))
    size = 1 if len(items) <= cap else min(max_per, (len(items) + cap - 1) // cap)
    return [items[i:i + size] for i in range(0, len(items), size)]
```

- [ ] **Step 10: Use `_agent_groups` in `cmd_plan`**

In `cmd_plan`, replace:

```python fragment
    cap = int(a.cap or c.threads or 20)
    size = 1 if len(live) <= cap else min(12, (len(live) + cap - 1) // cap)
    retr = Retriever(c)
    groups, cur = [], []
    for it in sorted(live, key=lambda r: (r.get("category") or "", r["id"])):
        cur.append(it)
        if len(cur) >= size:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
```

with:

```python fragment
    cap = int(a.cap or c.threads or 20)
    ordered = sorted(live, key=lambda r: (r.get("category") or "", r["id"]))
    groups = _agent_groups(ordered, cap, 12, _on_opencode())
    size = max([len(g) for g in groups] or [0])
    retr = Retriever(c)
```

The `plan: %d requirements -> %d batch file(s) of %d` print keeps using `size`, now the largest batch.

- [ ] **Step 11: Use `_agent_groups` in `cmd_status`**

Inside `if vset:` in `cmd_status`, replace:

```python fragment
        cap = int(a.cap or c.threads or 20)
        size = 1 if len(vset) <= cap else min(6, (len(vset) + cap - 1) // cap)
        idx = len([k for k in (st.get("vbatches") or {})])
        groups, cur = [], []
        for rid in vset:
            cur.append(rid)
            if len(cur) >= size:
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
```

with:

```python fragment
        cap = int(a.cap or c.threads or 20)
        idx = len([k for k in (st.get("vbatches") or {})])
        groups = _agent_groups(list(vset), cap, 6, _on_opencode())
```

If T23 changed how `vset` or `idx` is computed, keep its version of those lines and replace only the `size` line and the `groups, cur` loop.

- [ ] **Step 12: Run the batch-sizing tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_setup_oc.py' -k AgentLaneBatchSizing`
Expected: PASS (`Ran 8 tests` ... `OK`)

- [ ] **Step 13: Write the failing setup-text test**

Insert this class directly above the final `if __name__ == "__main__":` block in `_shared/tests/test_audit_setup_oc.py`.

```python
class SetupAgentLaneText(IsolatedHome):
    def test_setup_describes_real_agent_lane_routing(self):
        with mock.patch.object(oc_harness, "detect", return_value=2), \
             mock.patch.object(oc_harness, "install", return_value=[]):
            rc, out = self.run_setup()
        self.assertEqual(rc or 0, 0)
        self.assertIn("OC_MAX_LANES", out)
        self.assertIn("v1 runs them in parallel through oc_harness.py run", out)
        self.assertIn("v2 dispatches them as background subagent calls", out)
```

- [ ] **Step 14: Run the setup-text test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_setup_oc.py' -k SetupAgentLaneText`
Expected: FAIL with "AssertionError: 'OC_MAX_LANES' not found in"

- [ ] **Step 15: Fix the setup text in `cmd_setup`**

In the OpenCode branch of `cmd_setup`, replace:

```python fragment
        print("\nOpenCode: agents run on zai-coding-plan/glm-5.3-flash (workers) and")
        print("zai-coding-plan/glm-5.3 (judgment). The api lane holds the 64 threads; the")
        print("agent-lane fallback runs through oc_harness.py run, one opencode process per lane.")
```

with:

```python fragment
        print("\nOpenCode: agents run on zai-coding-plan/glm-5.3-flash (workers) and")
        print("zai-coding-plan/glm-5.3 (judgment). The api lane holds the 64 threads.")
        print("Agent-lane fallback: plan makes at most OC_MAX_LANES (default 8) batches.")
        print("v1 runs them in parallel through oc_harness.py run (one opencode process")
        print("per lane; plan/status print the exact NEXT command).")
        print("v2 dispatches them as background subagent calls that run in parallel.")
```

- [ ] **Step 16: Run the setup-text test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_setup_oc.py' -k SetupAgentLaneText`
Expected: PASS (`Ran 1 test` ... `OK`)

- [ ] **Step 17: Run the whole test file and the full suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit_setup_oc.py'`
Expected: PASS (`OK`, including the 5 pre-existing tests and any T23 added)

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no new failures compared with the run before this task (only the known stale-fixture failures, if any remain)

- [ ] **Step 18: Commit**

Run from the git root (one level above `glm-skills/`):

```bash
cd ..
git add glm-skills/requirements-code-audit-glm/scripts/audit.py glm-skills/_shared/tests/test_audit_setup_oc.py
git commit -m "fix(requirements-code-audit): v1 agent lane via oc_harness run, v2 background subagent dispatch, batches capped at OC_MAX_LANES"
```

---

### T25: requirements-code-audit docs and OpenCode agents [P]

**Depends:** T24

**Files:**
- Modify: `glm-skills/requirements-code-audit-glm/SKILL.md`
- Modify: `glm-skills/requirements-code-audit-glm/SETUP.md`
- Modify: `glm-skills/requirements-code-audit-glm/opencode/agents/rca-investigator.md`
- Modify: `glm-skills/requirements-code-audit-glm/opencode/agents/rca-verifier.md`
- Modify: `glm-skills/_shared/tests/test_adopt_audit.py`

- [ ] **Step 1: Write test for documentation configuration requirements**

Add the following test class to `glm-skills/_shared/tests/test_adopt_audit.py` after the existing Setup class:

```python
class DocumentationConfigs(unittest.TestCase):
    def test_skill_md_r3_step_1_has_no_parallel_read(self):
        skill_path = os.path.join(os.path.dirname(__file__), "..", "..", "requirements-code-audit-glm", "SKILL.md")
        with open(skill_path, 'r') as f:
            content = f.read()
        r3_section = content.split('## R3')[1].split('## R4')[0]
        self.assertNotIn('in parallel: `Read`', r3_section, "R3 should not have parallel Read and run")
        self.assertIn('run\n`A brief', r3_section, "R3 should have run A brief without parallel Read")

    def test_skill_md_finalize_matches_code_behavior(self):
        skill_path = os.path.join(os.path.dirname(__file__), "..", "..", "requirements-code-audit-glm", "SKILL.md")
        with open(skill_path, 'r') as f:
            content = f.read()
        self.assertIn('an unplanned discrepancy', content)
        self.assertNotIn('a CONFLICT not planned at P0', content, "CONFLICT should not fail gate; doc must align with code behavior")

    def test_setup_md_paths_have_glm_suffix(self):
        setup_path = os.path.join(os.path.dirname(__file__), "..", "..", "requirements-code-audit-glm", "SETUP.md")
        with open(setup_path, 'r') as f:
            lines = f.readlines()
        setup_lines = [line for i, line in enumerate(lines, 1) if i in [10, 12, 28] and 'python3' in line and 'audit' in line]
        for line in setup_lines:
            self.assertIn('-glm', line, f"Setup paths must include -glm suffix: {line}")

    def test_agent_investigator_write_paths(self):
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "requirements-code-audit-glm", "opencode", "agents", "rca-investigator.md")
        with open(agent_path, 'r') as f:
            content = f.read()
        self.assertIn('write_paths: **/.audit/**', content, "rca-investigator must have session-relative write_paths")

    def test_agent_investigator_steps(self):
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "requirements-code-audit-glm", "opencode", "agents", "rca-investigator.md")
        with open(agent_path, 'r') as f:
            content = f.read()
        self.assertRegex(content, r'steps:\s*30', "rca-investigator must have steps: 30")

    def test_agent_verifier_write_paths(self):
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "requirements-code-audit-glm", "opencode", "agents", "rca-verifier.md")
        with open(agent_path, 'r') as f:
            content = f.read()
        self.assertIn('write_paths: **/.audit/**', content, "rca-verifier must have session-relative write_paths")

    def test_agent_verifier_steps(self):
        agent_path = os.path.join(os.path.dirname(__file__), "..", "..", "requirements-code-audit-glm", "opencode", "agents", "rca-verifier.md")
        with open(agent_path, 'r') as f:
            content = f.read()
        self.assertRegex(content, r'steps:\s*25', "rca-verifier must have steps: 25")
```

- [ ] **Step 2: Run test to verify fixes are needed**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest _shared/tests/test_adopt_audit.py DocumentationConfigs -v`
Expected: FAIL with multiple assertion errors about missing configurations and parallel Read

- [ ] **Step 3: Fix SKILL.md R3 section to remove parallel Read**

In `glm-skills/requirements-code-audit-glm/SKILL.md`, change line 78-79 from:

```markdown
In ONE turn, in parallel: `Read` the requirements file **and** run
`A brief --spec <file>
```

to:

```markdown
In ONE turn, run `A brief --spec <file>
```

Remove the Read instruction since brief outputs the spec verbatim.

- [ ] **Step 4: Fix SKILL.md R6 section finalize to match code behavior**

In `glm-skills/requirements-code-audit-glm/SKILL.md`, change line 136-137 from:

```markdown
`A finalize` = report + gate + close. It writes `.audit/requirements-code-audit.md` and `traceability.csv` in
the spec's language, fails loudly on a single-pass MISSING, an unplanned discrepancy, a citation that does not
exist or a CONFLICT not planned at P0, and prints the headline numbers.
```

to:

```markdown
`A finalize` = report + gate + close. It writes `.audit/requirements-code-audit.md` and `traceability.csv` in
the spec's language, fails loudly on a single-pass MISSING, an unplanned discrepancy or a citation that does not
exist, warns on CONFLICT, and prints the headline numbers.
```

- [ ] **Step 5: Fix SETUP.md paths to include -glm suffix**

In `glm-skills/requirements-code-audit-glm/SETUP.md`, line 10 change:

```bash
python3 requirements-code-audit/scripts/audit.py setup --harness zcode
```

to:

```bash
python3 requirements-code-audit-glm/scripts/audit.py setup --harness zcode
```

Line 12 change:

```bash
python3 requirements-code-audit/scripts/audit.py setup --harness opencode
```

to:

```bash
python3 requirements-code-audit-glm/scripts/audit.py setup --harness opencode
```

Line 28 change:

```bash fragment
python3 requirements-code-audit/scripts/oc_harness.py install requirements-code-audit <major>
```

to:

```bash fragment
python3 requirements-code-audit-glm/scripts/oc_harness.py install requirements-code-audit-glm <major>
```

- [ ] **Step 6: Fix rca-investigator.md to add write_paths and steps**

In `glm-skills/requirements-code-audit-glm/opencode/agents/rca-investigator.md`, change the frontmatter to add `steps` and update `write_paths`:

After the opening `---`, replace lines 3-9:

```yaml
description: Read-only code-evidence investigator for the requirements-code-audit skill. Spawn one per batch file; it reads the batch (which already contains pre-retrieved code excerpts), verifies the evidence, writes one JSONL findings file and replies with a single line. Never use it for anything else.
model: flash
effort: high
temperature: 0.0
access: write
write_paths: .audit/**
bash: false
web: false
```

with:

```yaml
description: Read-only code-evidence investigator for the requirements-code-audit skill. Spawn one per batch file; it reads the batch (which already contains pre-retrieved code excerpts), verifies the evidence, writes one JSONL findings file and replies with a single line. Never use it for anything else.
model: flash
effort: high
temperature: 0.0
steps: 30
access: write
write_paths: **/.audit/**
bash: false
web: false
```

- [ ] **Step 7: Fix rca-verifier.md to update model, add write_paths and steps**

In `glm-skills/requirements-code-audit-glm/opencode/agents/rca-verifier.md`, change the frontmatter to update model, add `steps` and update `write_paths`:

After the opening `---`, replace lines 3-9:

```yaml
description: Adversarial second-pass verifier for the requirements-code-audit skill. Spawn one per verify batch file; it tries to overturn each preliminary finding (prove MISSING items exist, confirm or refute PARTIAL/CONFLICT), writes one JSONL verdict file and replies with a single line. Never use it for anything else.
model: pro
effort: max
temperature: 0.0
access: write
write_paths: .audit/**
bash: false
web: false
```

with:

```yaml
description: Adversarial second-pass verifier for the requirements-code-audit skill. Spawn one per verify batch file; it tries to overturn each preliminary finding (prove MISSING items exist, confirm or refute PARTIAL/CONFLICT), writes one JSONL verdict file and replies with a single line. Never use it for anything else.
model: pro
effort: max
temperature: 0.0
steps: 25
access: write
write_paths: **/.audit/**
bash: false
web: false
```

- [ ] **Step 8: Run test to verify all fixes pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest _shared/tests/test_adopt_audit.py DocumentationConfigs -v`
Expected: PASS (all tests pass)

- [ ] **Step 9: Commit**

```bash
cd glm-skills && git add requirements-code-audit-glm/SKILL.md requirements-code-audit-glm/SETUP.md requirements-code-audit-glm/opencode/agents/rca-investigator.md requirements-code-audit-glm/opencode/agents/rca-verifier.md _shared/tests/test_adopt_audit.py
git commit -m "fix(requirements-code-audit): align docs with code, add agent steps and session-relative write_paths"
```

---

### T26: plan_tool.py linter fixes [P]

**Depends:** —

**Files:**
- Modify: `glm-skills/writing-plans-glm/scripts/plan_tool.py:46-696`
- Create: `glm-skills/_shared/tests/test_plan_lint.py`

Three linter defects are fixed in `plan_tool.py`, one behavior at a time:
1. The heading check matches column-0 `# comment` lines inside code fences.
2. `files_block` drops bare file names such as `Makefile`.
3. The `git add` check reads a chained `git add a && git commit -m x` line as one argument list.

All commands run from `glm-skills/` (`cd glm-skills` first).

- [ ] **Step 1: Write the failing test for headings inside code fences**

Create `_shared/tests/test_plan_lint.py` with exactly this content:

```python
import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "writing-plans-glm", "scripts", "plan_tool.py")


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_lint_under_test", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()
FENCE = "`" * 3


def contract(*files):
    return {"files": list(files), "produces": []}


def make_body(file_lines, code_lines, commit_line, extra=()):
    rows = ["**Files:**"] + list(file_lines) + [""] + list(extra) + [
        "- [ ] **Step 1: Write the code**", "",
        FENCE + "python"] + list(code_lines) + [FENCE, "",
        "- [ ] **Step 2: Commit**", "",
        FENCE + "bash", commit_line, FENCE, ""]
    return "\n".join(rows)


def lint(c, body):
    return plan_tool.lint_body(c, body, [], "T99")


HEADING_ERR = "heading inside a task body"


class HeadingFenceTest(unittest.TestCase):
    def test_hash_comment_inside_fence_is_not_a_heading(self):
        body = make_body(["- Create: `src/app.py`"],
                         ["# build the value", "x = 1"],
                         "git add src/app.py")
        errs, _ = lint(contract("src/app.py"), body + "\ngit commit -m x\n")
        self.assertFalse([e for e in errs if HEADING_ERR in e], errs)

    def test_hash_comment_inside_tilde_fence_is_not_a_heading(self):
        body = "\n".join(["**Files:**", "- Create: `src/app.py`", "",
                          "- [ ] **Step 1: Write the code**", "",
                          "~~~python", "## section comment", "x = 1", "~~~", "",
                          "- [ ] **Step 2: Commit**", "",
                          FENCE + "bash", "git add src/app.py", "git commit -m x", FENCE, ""])
        errs, _ = lint(contract("src/app.py"), body)
        self.assertFalse([e for e in errs if HEADING_ERR in e], errs)

    def test_heading_outside_fence_still_fails(self):
        body = make_body(["- Create: `src/app.py`"], ["x = 1"],
                         "git add src/app.py", extra=["## Notes", ""])
        errs, _ = lint(contract("src/app.py"), body + "\ngit commit -m x\n")
        self.assertTrue([e for e in errs if HEADING_ERR in e], errs)

    def test_heading_after_closed_fence_still_fails(self):
        body = make_body(["- Create: `src/app.py`"], ["x = 1"],
                         "git add src/app.py")
        errs, _ = lint(contract("src/app.py"), body + "\n### Late heading\ngit commit -m x\n")
        self.assertTrue([e for e in errs if HEADING_ERR in e], errs)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_lint.py'`
Expected: FAIL. `test_hash_comment_inside_fence_is_not_a_heading` and `test_hash_comment_inside_tilde_fence_is_not_a_heading` fail with `AssertionError` listing `T99: '#', '##' or '###' heading inside a task body breaks plan structure`, and the run ends `FAILED (failures=2)`.

- [ ] **Step 3: Skip fenced blocks in the heading check**

In `writing-plans-glm/scripts/plan_tool.py`, insert this function directly above `def lint_body(c, body, allow, label, repo=None, earlier_files=()):`

```python
def heading_outside_fences(body):
    """True when a '#', '##' or '###' heading sits outside every code fence."""
    fence = 0
    for l in body.splitlines():
        m = re.match(r"^\s*(`{3,}|~{3,})(.*)$", l)
        if m:
            if not fence:
                fence = len(m.group(1))
                continue
            if len(m.group(1)) >= fence and not m.group(2).strip():
                fence = 0
                continue
        if not fence and re.match(r"^#{1,3}\s", l):
            return True
    return False
```

Then, inside `lint_body`, replace these two lines:

```python fragment
    if re.search(r"^#{1,3}\s", body, re.M):
        errs.append("%s: '#', '##' or '###' heading inside a task body breaks plan structure (use '####' or bold)" % label)
```

with:

```python
    if heading_outside_fences(body):
        errs.append("%s: '#', '##' or '###' heading inside a task body breaks plan structure (use '####' or bold)" % label)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_lint.py'`
Expected: PASS: `Ran 4 tests` followed by `OK`.

- [ ] **Step 5: Write the failing test for bare file names in the Files list**

Append this class to `_shared/tests/test_plan_lint.py`, directly above the `if __name__ == "__main__":` line:

```python
class FilesBlockBareNameTest(unittest.TestCase):
    def test_bare_known_filenames_are_kept(self):
        body = "\n".join(["**Files:**",
                          "- Modify: `Makefile`",
                          "- Modify: `Dockerfile:3-9`",
                          "- Create: `Gemfile`",
                          "- Test: `tests/test_x.py`", ""])
        self.assertEqual(plan_tool.files_block(body),
                         ["Makefile", "Dockerfile", "Gemfile", "tests/test_x.py"])

    def test_symbol_mentions_are_still_skipped(self):
        body = "**Files:**\n- Modify: `src/a.py` (adds `run_all`)\n"
        self.assertEqual(plan_tool.files_block(body), ["src/a.py"])

    def test_lint_accepts_bare_filename_contract(self):
        body = make_body(["- Modify: `Makefile`", "- Create: `src/app.py`"], ["x = 1"],
                         "git add Makefile src/app.py")
        errs, _ = lint(contract("Makefile", "src/app.py"), body + "\ngit commit -m x\n")
        self.assertFalse([e for e in errs if "missing from the **Files:** list" in e], errs)
```

- [ ] **Step 6: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_lint.py' -k FilesBlockBareNameTest`
Expected: FAIL. `test_bare_known_filenames_are_kept` fails with `AssertionError: Lists differ: ['tests/test_x.py'] != ['Makefile', 'Dockerfile', 'Gemfile', 'tests/test_x.py']`, `test_lint_accepts_bare_filename_contract` fails listing `contract file `Makefile` missing from the **Files:** list`, and the run ends `FAILED (failures=2)`.

- [ ] **Step 7: Accept bare known file names in `files_block`**

In `writing-plans-glm/scripts/plan_tool.py`, insert this constant directly below the line `TICK = re.compile(r"`([^`\n]+)`")`:

```python
BARE_FILENAMES = {"Makefile", "makefile", "GNUmakefile", "Dockerfile", "Containerfile", "Gemfile",
                  "Rakefile", "Procfile", "Justfile", "justfile", "Vagrantfile", "Brewfile",
                  "Pipfile", "Jenkinsfile", "Caddyfile", "LICENSE", "README", "CHANGELOG"}
```

Then, inside `files_block`, replace this line:

```python fragment
        paths += [norm_path(x) for x in TICK.findall(l) if "/" in x or "." in x]  # skip `Symbol` mentions
```

with:

```python fragment
        paths += [norm_path(x) for x in TICK.findall(l)
                  if "/" in x or "." in x or norm_path(x) in BARE_FILENAMES]  # skip `Symbol` mentions
```

- [ ] **Step 8: Run test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_lint.py'`
Expected: PASS: `Ran 7 tests` followed by `OK`.

- [ ] **Step 9: Write the failing test for chained `git add` lines**

Append this class to `_shared/tests/test_plan_lint.py`, directly above the `if __name__ == "__main__":` line:

```python
class GitAddChainTest(unittest.TestCase):
    def _errs(self, commit_line, files=("src/app.py",)):
        body = make_body(["- Create: `%s`" % f for f in files], ["x = 1"], commit_line)
        errs, _ = lint(contract(*files), body)
        return errs

    def test_split_helper_returns_only_add_arguments(self):
        src = 'cd repo && git add a.py b.py && git commit -m "feat: x"\ngit add c.py; git status || true'
        self.assertEqual(plan_tool.git_add_args(src), ["a.py b.py", "c.py"])

    def test_and_chain_with_commit_is_clean(self):
        self.assertEqual(self._errs('git add src/app.py && git commit -m "feat: add app"'), [])

    def test_semicolon_and_or_chains_are_clean(self):
        self.assertEqual(self._errs("git add src/app.py; git commit -m x || true"), [])

    def test_foreign_path_in_chain_still_flagged(self):
        errs = self._errs("cd repo && git add other.py && git commit -m x")
        self.assertTrue([e for e in errs if "`git add` path `other.py` is not in the contract Files" in e], errs)
        self.assertFalse([e for e in errs if "`commit`" in e or "`&&`" in e], errs)

    def test_add_all_in_chain_still_flagged(self):
        errs = self._errs("git add -A && git commit -m x")
        self.assertTrue([e for e in errs if "stage explicit paths from Files only" in e], errs)
```

- [ ] **Step 10: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_lint.py' -k GitAddChainTest`
Expected: FAIL. `test_split_helper_returns_only_add_arguments` errors with `AttributeError: module 'plan_tool_lint_under_test' has no attribute 'git_add_args'`, the chain tests fail with errors such as `` `git add` path `&&` is not in the contract Files ``, and the run ends with `FAILED`.

- [ ] **Step 11: Split shell chains before tokenising `git add`**

In `writing-plans-glm/scripts/plan_tool.py`, insert this regex and function directly above `def heading_outside_fences(body):`

```python
GIT_ADD = re.compile(r"^\s*git add\s+(.+)$")


def git_add_args(src):
    """Argument strings of every `git add` command in a shell block, split on &&, || and ;."""
    out = []
    for line in src.splitlines():
        for seg in re.split(r"&&|\|\||;", line):
            m = GIT_ADD.match(seg)
            if m and m.group(1).strip():
                out.append(m.group(1).strip())
    return out
```

Then, inside `lint_body`, replace the whole `for info, src, line in blocks:` loop that checks `git add` (it ends right before `errs += syntax_errors(blocks, label)`) with:

```python
    for info, src, line in blocks:
        for args in git_add_args(src):
            try:
                toks = [t for t in shlex.split(args) if not t.startswith("-")]
            except ValueError:
                toks = args.split()
            bad = [t for t in toks if t in (".", "*", ":/") or "*" in t]
            if bad or re.search(r"(^|\s)(-A|--all|-u)\b", args):
                errs.append("%s: `git add %s` - stage explicit paths from Files only" % (label, args))
                continue
            for t in toks:
                t = norm_path(t)
                if t in contract:
                    continue
                if any(f.startswith(t.rstrip("/") + "/") for f in contract):
                    warns.append("%s: `git add %s` stages a directory - prefer explicit file paths" % (label, t))
                else:
                    errs.append("%s: `git add` path `%s` is not in the contract Files" % (label, t))
```

- [ ] **Step 12: Run test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_lint.py'`
Expected: PASS: `Ran 12 tests` followed by `OK`.

- [ ] **Step 13: Run the full suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: every `test_plan_lint` test passes, and the failure count is no higher than the recorded baseline of 11 stale-fixture failures (none of them in `test_plan_lint.py` or `test_adopt_plan.py`).

- [ ] **Step 14: Commit**

The commit runs from the git root because the Files paths are relative to it:

```bash
cd ..
git add glm-skills/writing-plans-glm/scripts/plan_tool.py glm-skills/_shared/tests/test_plan_lint.py
git commit -m "fix(writing-plans): lint skips fenced headings, keeps bare filenames, splits chained git add"
cd glm-skills
```

---

### T27: plan_tool.py OpenCode dispatch, agents and grouping [P]

**Depends:** T03

**Runs after:** T26 (same files)

**Interfaces:**
- Consumes: `def harness(script_path: str = "") -> str`; `def major(skill_dir: str = "", binary: str = "opencode") -> int`; `def dispatch_line(agent: str, prompt_path: str, description: str, major: int, background: bool = True) -> str`
- Produces: `plan-task-writer`; `steps: 24`; `plan-task-writer-deep`; `steps: 24`; `plan-reviewer`

**Files:**
- Modify: `glm-skills/writing-plans-glm/scripts/plan_tool.py`
- Modify: `glm-skills/writing-plans-glm/opencode/agents/plan-task-writer.md:8`
- Create: `glm-skills/writing-plans-glm/opencode/agents/plan-task-writer-deep.md`
- Create: `glm-skills/writing-plans-glm/opencode/agents/plan-reviewer.md`
- Test: `glm-skills/_shared/tests/test_adopt_plan.py`

This task fixes WP4, WP6, WP7, WP8, WP9 and WP12. It ships three OpenCode agents and makes every OpenCode dispatch line come from `oc_harness.dispatch_line()`. It also changes writer grouping so no group holds more than 4 tasks. On OpenCode the group count is ceil(tasks / 4), and the lane width (`PLAN_LANE_WIDTH`, default 8) caps how many groups one dispatch message starts. With 32 tasks or fewer, that means at most 8 groups in one message. Beyond that the extra groups go into further messages, 8 at a time. T26 edits `plan_tool.py` before this task. Every edit below is anchored on a function name or a code line, not on line numbers. All commands run from `glm-skills/`.

- [ ] **Step 1: Add the test imports and shared helpers**

In `_shared/tests/test_adopt_plan.py`, add these three lines to the import block at the top of the file. Put them next to `import http.server`:

```python
import argparse
import contextlib
import io
```

Then add these helpers directly below the line `plan_tool = _load_plan_tool()`:

```python
AGENTS_DIR = os.path.join(HERE, "..", "..", "writing-plans-glm", "opencode", "agents")
NO_KEY = (None, "https://api.z.ai/api/coding/paas/v4", "openai", "-")


def _frontmatter(name):
    with open(os.path.join(AGENTS_DIR, name + ".md"), encoding="utf-8") as fh:
        text = fh.read()
    head = text.split("---\n")[1]
    fields = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, text


def _plan_text(n, deep=()):
    rows = ["# Demo Plan", "", "**Goal:** demo.", "", "## Global Constraints", "", "- none", "",
            "## Contracts", ""]
    for i in range(1, n + 1):
        tid = "T%02d" % i
        rows += ["#### %s: part %d" % (tid, i), "- Depends: none", "- Files: `src/p%02d.py`" % i,
                 "- Produces: `def f%02d() -> int`" % i, "- Spec: L1-1",
                 "- Tier: %s" % ("deep" if tid in deep else "std"), ""]
    return "\n".join(rows) + "\n"
```

- [ ] **Step 2: Write the failing agent-file and setup tests**

Add these classes to `_shared/tests/test_adopt_plan.py`, directly above `if __name__ == "__main__":`:

```python
class OpenCodeAgentFileTests(unittest.TestCase):
    def test_writer_runs_24_steps_on_flash(self):
        fm, _ = _frontmatter("plan-task-writer")
        self.assertEqual(fm["model"], "flash")
        self.assertEqual(fm["steps"], "24")

    def test_deep_writer_is_glm53_max_24_steps(self):
        fm, text = _frontmatter("plan-task-writer-deep")
        self.assertEqual(fm["model"], "glm-5.3")
        self.assertEqual(fm["effort"], "max")
        self.assertEqual(fm["steps"], "24")
        self.assertEqual(fm["access"], "write")
        self.assertEqual(fm["bash"], "true")
        self.assertIn("T07 OK", text)

    def test_reviewer_is_glm53_high(self):
        fm, text = _frontmatter("plan-reviewer")
        self.assertEqual(fm["model"], "glm-5.3")
        self.assertEqual(fm["effort"], "high")
        self.assertEqual(fm["access"], "write")
        self.assertIn("APPROVED", text)

    def test_render_uses_major_not_detect(self):
        real = plan_tool.oc_harness.render_agent
        with mock.patch.object(plan_tool.oc_harness, "major", return_value=2), \
             mock.patch.object(plan_tool.oc_harness, "detect", side_effect=AssertionError("detect() called")), \
             mock.patch.object(plan_tool.oc_harness, "render_agent", side_effect=real) as ren:
            text = plan_tool.agent_file("opencode", "plan-task-writer-deep")
        self.assertEqual(ren.call_args[0][1], 2)
        self.assertIn("mode: subagent", text)
        self.assertIn("zai-coding-plan/glm-5.3", text)
        self.assertNotIn("glm-5.3-flash", text)


class OpenCodeSetupTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.home, True)
        for p in (mock.patch.dict(os.environ, {"HOME": self.home}),
                  mock.patch.object(plan_tool, "find_credentials", return_value=NO_KEY)):
            p.start()
            self.addCleanup(p.stop)

    def run_setup(self, major):
        buf = io.StringIO()
        with mock.patch.object(plan_tool.oc_harness, "major", return_value=major), \
             mock.patch.object(plan_tool.oc_harness, "detect", return_value=major), \
             contextlib.redirect_stdout(buf):
            rc = plan_tool.cmd_setup(argparse.Namespace(harness="opencode", apply=True))
        self.assertEqual(rc, 0, buf.getvalue())
        return buf.getvalue()

    def test_setup_installs_all_three_agents(self):
        self.run_setup(2)
        adir = os.path.join(self.home, ".config", "opencode", "agents")
        for name in ("plan-task-writer", "plan-task-writer-deep", "plan-reviewer"):
            self.assertTrue(os.path.isfile(os.path.join(adir, name + ".md")), name)

    def test_v2_setup_drops_background_env_hint(self):
        self.assertNotIn("OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS", self.run_setup(2))

    def test_v1_setup_keeps_background_env_hint(self):
        self.assertIn("OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS", self.run_setup(1))
```

- [ ] **Step 3: Run the agent tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_plan.py' -k OpenCodeAgentFileTests -k OpenCodeSetupTests`
Expected: FAIL. `test_writer_runs_24_steps_on_flash` fails with `AssertionError: '16' != '24'`. The deep writer and reviewer tests fail with `FileNotFoundError` naming `plan-task-writer-deep.md` and `plan-reviewer.md`. The other tests fail with `AttributeError: module 'plan_tool_under_test' has no attribute 'oc_harness'`.

- [ ] **Step 4: Raise the writer's step budget to 24**

In `writing-plans-glm/opencode/agents/plan-task-writer.md`, change line 8 from `steps: 16` to `steps: 24`. The whole file then reads:

```markdown
---
description: Writes implementation-plan task bodies from a writing-plans brief file. Use only when given a writing-plans brief path.
model: flash
effort: high
access: write
bash: true
web: false
steps: 24
---

You write implementation-plan task bodies. Read the brief file named in your task message and
follow it exactly. Rules: no repository exploration, no extra file reads beyond those the brief
names, minimal turns, and reply with one line per task (`T07 OK` or `T07 FAIL: <first error>`).
Never echo the body.

When writing a task body, follow these rules exactly:

1. Start with **Files:** listing every contract file (Create, Modify, Test) with optional line ranges.
2. Write numbered `- [ ] **Step N: ...**` checkboxes in TDD order: failing test → run (fail) → implement → run (pass) → commit.
3. Every Run: must be followed by Expected: (exact output or error message).
4. Code blocks must be complete and runnable - the reader has no other context.
5. Git add stage only the contract files by explicit path - never use `.`, `-A`, or globs.
6. No unwritten placeholders. No bare descriptions like "add validation" or "consider alternatives".
7. No mentions of AI tools, skills, harnesses, or vendor products.

Respect the tier and the contract signatures exactly, using only what the brief provides.
```

- [ ] **Step 5: Create the deep writer agent**

Create `writing-plans-glm/opencode/agents/plan-task-writer-deep.md`:

```markdown
---
description: Writes deep-tier implementation-plan task bodies from a writing-plans brief file. Use only when given a writing-plans brief path whose group holds a deep-tier task.
model: glm-5.3
effort: max
access: write
bash: true
web: false
steps: 24
---

You write implementation-plan task bodies for deep-tier tasks. Read the brief file named in your
task message and follow it exactly. Rules: no repository exploration, no extra file reads beyond
those the brief names, minimal turns, and reply with one line per task (`T07 OK` or
`T07 FAIL: <first error>`). Never echo the body.

When writing a task body, follow these rules exactly:

1. Start with **Files:** listing every contract file (Create, Modify, Test) with optional line ranges.
2. Write numbered `- [ ] **Step N: ...**` checkboxes in TDD order: failing test → run (fail) → implement → run (pass) → commit.
3. Every Run: must be followed by Expected: (exact output or error message).
4. Code blocks must be complete and runnable - the reader has no other context.
5. Git add stage only the contract files by explicit path - never use `.`, `-A`, or globs.
6. No unwritten placeholders. No bare descriptions like "add validation" or "consider alternatives".
7. No mentions of AI tools, skills, harnesses, or vendor products.
8. Deep tier: check every consumed signature against its contract, and every edge case the spec excerpt names, before you write.

Respect the tier and the contract signatures exactly, using only what the brief provides.
```

- [ ] **Step 6: Create the reviewer agent**

Create `writing-plans-glm/opencode/agents/plan-reviewer.md`:

```markdown
---
description: Reviews implementation-plan task bodies from a writing-plans reviewer brief file. Use only when given a writing-plans review brief path.
model: glm-5.3
effort: high
access: write
bash: true
web: false
steps: 24
---

You review implementation-plan task bodies. Read the reviewer brief named in your task message and
follow it exactly. Rules: no repository exploration, no extra file reads beyond those the brief
names, minimal turns, and reply with one line per task (`T07 APPROVED`, `T07 FIXED` or
`T07 FAIL: <first error>`). Never echo the body.

When reviewing a task body, follow these rules exactly:

1. Judge only what a linter cannot see: spec alignment, correctness, buildability, contract use.
2. Ignore wording and style. If nothing would break implementation, leave the file unchanged and report APPROVED.
3. When you fix a body, keep the **Files:** list and every contract signature unchanged.
4. After every edit, run the LINT command from the brief and fix each ERR it prints.
5. No mentions of AI tools, skills, harnesses, or vendor products.
```

- [ ] **Step 7: Import the shared harness module and render agents with `major()`**

In `writing-plans-glm/scripts/plan_tool.py`, directly below the line `import zai_client  # vendored by skills/glm/_shared/sync.sh, see T05`, add:

```python
import oc_harness  # vendored by _shared/sync.sh
```

Directly below the line `AGENT_BODY = """...` block (the constant that ends with `Never echo the body.` and `"""`), add:

```python
WRITER_AGENTS = ("plan-task-writer", "plan-task-writer-deep", "plan-reviewer")
```

Replace the whole `def agent_file(harness):` function with:

```python
def agent_file(harness, name="plan-task-writer"):
    if harness == "opencode":
        neutral = os.path.join(SKILL_DIR, "opencode", "agents", name + ".md")
        if os.path.exists(neutral):
            return oc_harness.render_agent(load(neutral), oc_harness.major(SKILL_DIR))
        if name != "plan-task-writer":
            return None
        fm = ("---\n"
              "description: Writes implementation-plan task bodies from a writing-plans brief file. "
              "Use only when given a writing-plans brief path.\n"
              "mode: subagent\n"
              "model: zai-coding-plan/glm-5.3-flash\n"
              "temperature: 0.3\n"
              "steps: 24\n"
              "permission:\n"
              "  read: allow\n"
              "  edit: allow\n"
              "  bash: allow\n"
              "  task: deny\n"
              "  webfetch: deny\n"
              "---\n\n")
        return fm + AGENT_BODY
    if harness == "zcode":
        fm = ("---\n"
              "name: plan-task-writer\n"
              "description: Writes implementation-plan task bodies from a writing-plans brief file. "
              "Use only when given a writing-plans brief path.\n"
              "model: glm-5.3-flash\n"
              "thinking: low\n"
              "tools: Read, Write, Edit, Bash\n"
              "---\n\n")
        return fm + AGENT_BODY
    fm = ("---\n"
          "name: plan-task-writer\n"
          "description: Writes implementation-plan task bodies from a writing-plans brief file. "
          "Use only when given a writing-plans brief path.\n"
          "tools: Read, Write, Edit, Bash\n"
          "model: haiku\n"
          "maxTurns: 16\n"
          "omitClaudeMd: true\n"
          "hooks:\n"
          "  PostToolUse:\n"
          "    - matcher: \"Write|Edit\"\n"
          "      hooks:\n"
          "        - type: command\n"
          "          command: \"%s hook-lint\"\n"
          "---\n\n") % qtool()
    return fm + AGENT_BODY
```

- [ ] **Step 8: Install all three agents in setup and drop the v2 background hint**

In `writing-plans-glm/scripts/plan_tool.py`, replace the whole `def cmd_setup(a):` function with:

```python
def cmd_setup(a):
    home = os.path.expanduser("~")
    harness = a.harness if a.harness != "auto" else detect_harness()[0]
    if harness == "unknown":
        harness = "opencode"
    paths = {"opencode": os.path.join(home, ".config", "opencode", "agents", "plan-task-writer.md"),
             "zcode": os.path.join(home, ".zcode", "agents", "plan-task-writer.md"),
             "claude": os.path.join(home, ".claude", "agents", "plan-task-writer.md")}
    agent_path = paths[harness]
    targets = [(agent_path, agent_file(harness))]
    if harness == "opencode":
        adir = os.path.dirname(agent_path)
        for name in WRITER_AGENTS[1:]:
            text = agent_file("opencode", name)
            if text is not None:
                targets.append((os.path.join(adir, name + ".md"), text))
    changes = []
    for path, text in targets:
        if not os.path.exists(path) or load(path) != text:
            changes.append("write subagent %s" % path)
    settings = os.path.join(home, ".claude", "settings.json")
    new = None
    if harness == "claude":
        try:
            cur = json.loads(load(settings)) if os.path.exists(settings) else {}
        except ValueError as e:
            print("ERR  %s is not valid JSON (%s); nothing changed" % (settings, e))
            return 1
        new = json.loads(json.dumps(cur))
        env = new.setdefault("env", {})
        for k, v in (("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", "64"),
                     ("CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS", "64"),
                     ("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "1000000"),
                     ("API_TIMEOUT_MS", "3000000")):
            if str(env.get(k, "")) != v:
                env[k] = v
                changes.append("env.%s = %s" % (k, v))
        allow = new.setdefault("permissions", {}).setdefault("allow", [])
        for rule in ("Bash(%s *)" % qtool(), "Edit(**/docs/plans/**)"):
            if rule not in allow:
                allow.append(rule)
                changes.append("permissions.allow += %s" % rule)
    key, base, proto, src = find_credentials()
    print("harness: %s | api key: %s (%s)" % (harness, mask(key), src))
    if not changes:
        print("OK setup already complete")
    else:
        print(("APPLY" if a.apply else "DRY-RUN") + ":")
        for c in changes:
            print("  - " + c)
    if changes and a.apply:
        if new is not None:
            if os.path.exists(settings):
                shutil.copy2(settings, settings + ".bak")
            save(settings, json.dumps(new, indent=2) + "\n")
        for path, text in targets:
            save(path, text)
        print("OK written")
    elif changes:
        print("Re-run with --apply to write them.")
    print("")
    print("Fastest lane (recommended) - script-side fan-out, no subagents:")
    print("  export ZAI_API_KEY=<GLM Coding Plan key>")
    print("  export ZAI_BASE_URL=%s" % DEFAULT_BASE)
    if harness == "opencode" and oc_harness.major(SKILL_DIR) < 2:
        print("Agent-lane fallback on OpenCode v1 dispatches subagents one at a time;")
        print("  export OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true   # lets them overlap")
    if harness == "zcode":
        print("ZCode runs foreground subagents in parallel; the agent lane works without extra flags.")
    print("Verify with: %s doctor --ping" % qtool())
    return 0
```

- [ ] **Step 9: Run the agent tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_plan.py' -k OpenCodeAgentFileTests -k OpenCodeSetupTests -k AgentFileTests`
Expected: PASS. The run ends with `Ran 8 tests` and `OK`.

- [ ] **Step 10: Write the failing grouping tests**

Add this class to `_shared/tests/test_adopt_plan.py`, directly above `if __name__ == "__main__":`:

```python
class WriterGroupingTests(unittest.TestCase):
    def test_group_count_on_lanes_is_ceil_of_quarter(self):
        for n, want in ((1, 1), (4, 1), (5, 2), (10, 3), (32, 8), (40, 10)):
            self.assertEqual(plan_tool.writer_group_count(n, True, 8), want, n)

    def test_group_count_elsewhere_is_one_per_task_up_to_cap(self):
        self.assertEqual(plan_tool.writer_group_count(5, False, 20), 5)
        self.assertEqual(plan_tool.writer_group_count(30, False, 20), 20)
        self.assertEqual(plan_tool.writer_group_count(100, False, 20), 25)
        self.assertEqual(plan_tool.writer_group_count(0, False, 20), 0)

    def test_cap_groups_splits_oversized_groups(self):
        self.assertEqual(plan_tool.cap_groups([[1, 2, 3, 4, 5, 6], [7]]), [[1, 2, 3, 4], [5, 6], [7]])

    def test_lane_width_default_and_env(self):
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": ""}):
            self.assertEqual(plan_tool.lane_width(), 8)
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "3"}):
            self.assertEqual(plan_tool.lane_width(), 3)
        with mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "x"}):
            self.assertEqual(plan_tool.lane_width(), 8)

    def test_on_opencode_asks_shared_harness_with_script_path(self):
        with mock.patch.object(plan_tool.oc_harness, "harness", return_value="opencode") as h:
            self.assertTrue(plan_tool.on_opencode())
        h.assert_called_once_with(plan_tool.TOOL)
        with mock.patch.object(plan_tool.oc_harness, "harness", return_value="claude"):
            self.assertFalse(plan_tool.on_opencode())
        with mock.patch.object(plan_tool.oc_harness, "harness", side_effect=OSError("boom")):
            self.assertFalse(plan_tool.on_opencode())
```

- [ ] **Step 11: Run the grouping tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_plan.py' -k WriterGroupingTests`
Expected: FAIL. All 5 tests fail with `AttributeError: module 'plan_tool_under_test' has no attribute 'writer_group_count'`, and likewise for `cap_groups`, `lane_width` and `on_opencode`.

- [ ] **Step 12: Implement the grouping helpers**

In `writing-plans-glm/scripts/plan_tool.py`, directly below the line `DEFAULT_AGENT_CAP = 20`, add:

```python
WRITER_GROUP_MAX = 4      # tasks per writer group (fits the 24-step agent budget)
DEFAULT_LANE_WIDTH = 8    # background lanes one OpenCode dispatch message starts
```

Directly below the end of `def agent_cap():` (after its `return DEFAULT_AGENT_CAP, ""` line), add:

```python
def on_opencode():
    """True when this script runs under OpenCode (v1 or v2); never raises."""
    try:
        return oc_harness.harness(TOOL) == "opencode"
    except Exception:
        return False


def lane_width():
    """Groups one OpenCode dispatch message may start (PLAN_LANE_WIDTH, default 8)."""
    v = os.environ.get("PLAN_LANE_WIDTH", "").strip()
    return min(MAX_WORKERS, int(v)) if v.isdigit() and int(v) > 0 else DEFAULT_LANE_WIDTH


def writer_group_count(n_tasks, opencode, cap):
    """Writer groups for n_tasks; every group holds at most WRITER_GROUP_MAX tasks.
    OpenCode: ceil(n / 4), so up to 32 tasks fit the default lane width of 8 in one
    message; the lane width caps each dispatch message and extra groups go into
    further messages. Elsewhere: one task per writer up to cap, never more than 4 per writer."""
    if n_tasks <= 0:
        return 0
    need = -(-n_tasks // WRITER_GROUP_MAX)
    if opencode:
        return need
    return max(need, min(cap, n_tasks))
```

Directly below the end of `def partition(cs, k):` (after its final `return out` line), add:

```python
def cap_groups(parts, size=WRITER_GROUP_MAX):
    """Split any group longer than `size` into consecutive chunks of at most `size`."""
    out = []
    for g in parts:
        out += [g[i:i + size] for i in range(0, len(g), size)]
    return out
```

- [ ] **Step 13: Run the grouping tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_plan.py' -k WriterGroupingTests`
Expected: PASS. The run ends with `Ran 5 tests` and `OK`.

- [ ] **Step 14: Write the failing dispatch tests**

Add this class to `_shared/tests/test_adopt_plan.py`, directly above `if __name__ == "__main__":`:

```python
class OpenCodeDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.major = 2
        patches = [mock.patch.object(plan_tool, "on_opencode", return_value=True),
                   mock.patch.object(plan_tool, "agent_installed", return_value="/fake/agents"),
                   mock.patch.object(plan_tool, "find_credentials", return_value=NO_KEY),
                   mock.patch.object(plan_tool.oc_harness, "major", side_effect=lambda *a, **k: self.major),
                   mock.patch.dict(os.environ, {"PLAN_LANE_WIDTH": "8"})]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.plan = os.path.join(self.tmp, "plan.md")

    def contracts(self, n, deep=()):
        with open(self.plan, "w", encoding="utf-8") as fh:
            fh.write(_plan_text(n, deep))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = plan_tool.cmd_contracts(argparse.Namespace(plan=self.plan, spec=None, allow=[], workers=None))
        out = buf.getvalue()
        self.assertEqual(rc, 0, out)
        work = plan_tool.default_work(self.plan)
        with open(os.path.join(work, "work.json"), encoding="utf-8") as fh:
            info = json.load(fh)
        return out, work, info

    def expected(self, agent, work, sub, gid, description):
        return plan_tool.oc_harness.dispatch_line(agent, os.path.join(work, sub, gid + ".md"),
                                                  description, self.major)

    def test_ten_tasks_make_three_groups_of_at_most_four(self):
        _, _, info = self.contracts(10)
        sizes = [len(v) for v in info["groups"].values()]
        self.assertEqual(len(sizes), 3)
        self.assertTrue(all(s <= 4 for s in sizes), sizes)
        self.assertEqual(info["groups"]["W01"], ["T01", "T02", "T03", "T04"])

    def test_v2_dispatch_uses_writer_agent_and_no_foreign_fallback(self):
        out, work, _ = self.contracts(10)
        self.assertIn(self.expected("plan-task-writer", work, "briefs", "W01", "plan T01-T04"), out)
        self.assertIn(self.expected("plan-task-writer", work, "briefs", "W03", "plan T09-T10"), out)
        self.assertNotIn("general-purpose", out)
        self.assertNotIn("subagent_type=", out)
        self.assertNotIn("haiku", out)
        self.assertNotIn("sonnet", out)

    def test_deep_group_goes_to_deep_writer(self):
        out, work, info = self.contracts(5, deep=("T05",))
        self.assertEqual(info["groups"]["W02"], ["T04", "T05"])
        self.assertIn(self.expected("plan-task-writer-deep", work, "briefs", "W02", "plan T04-T05"), out)
        self.assertIn(self.expected("plan-task-writer", work, "briefs", "W01", "plan T01-T03"), out)

    def test_missing_agents_fall_back_to_general(self):
        with mock.patch.object(plan_tool, "agent_installed", return_value=None):
            out, work, _ = self.contracts(10)
        self.assertIn(self.expected("general", work, "briefs", "W01", "plan T01-T04"), out)
        self.assertNotIn("general-purpose", out)

    def test_v1_dispatch_line_rendered_for_major_one(self):
        self.major = 1
        out, work, _ = self.contracts(10)
        self.assertIn(self.expected("plan-task-writer", work, "briefs", "W01", "plan T01-T04"), out)

    def test_forty_tasks_split_into_messages_of_lane_width(self):
        out, work, info = self.contracts(40)
        self.assertEqual(len(info["groups"]), 10)
        self.assertTrue(all(len(v) == 4 for v in info["groups"].values()))
        self.assertIn("MESSAGE 1 (8 calls", out)
        self.assertIn("MESSAGE 2 (2 calls", out)
        self.assertIn(self.expected("plan-task-writer", work, "briefs", "W10", "plan T37-T40"), out)

    def test_review_dispatches_plan_reviewer(self):
        _, work, _ = self.contracts(2, deep=("T01",))
        with open(os.path.join(work, "tasks", "T01.md"), "w", encoding="utf-8") as fh:
            fh.write("**Files:**\n- Create: `src/p01.py`\n")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = plan_tool.cmd_review(argparse.Namespace(plan=self.plan, all=False, size=None, agents=None))
        out = buf.getvalue()
        self.assertEqual(rc, 0, out)
        self.assertIn(self.expected("plan-reviewer", work, "review-briefs", "R01", "review T01"), out)
        self.assertNotIn("general-purpose", out)
        self.assertNotIn("sonnet", out)
```

- [ ] **Step 15: Run the dispatch tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_plan.py' -k OpenCodeDispatchTests`
Expected: FAIL. `test_ten_tasks_make_three_groups_of_at_most_four` fails with `AssertionError: 10 != 3`, because every task still gets its own writer. The dispatch tests fail with `AssertionError: '...' not found in '...'`, because the output still says `subagent_type=general-purpose` or `subagent_type=plan-task-writer`.

- [ ] **Step 16: Render one agent per row through `dispatch_line()`**

In `writing-plans-glm/scripts/plan_tool.py`, replace the whole `def dispatch_lines(groups, work, kind):` function with:

```python
def row_agent(g, kind, installed, opencode):
    """Agent (OpenCode) or model alias (other harnesses) for one dispatch row."""
    tier = max((c["tier"] for c in g), key=lambda t: TIER_RANK[t])
    if not opencode:
        return model_for("deep" if kind == "review" else tier, api=False)[0]
    if not installed:
        return "general"
    if kind == "review":
        return "plan-reviewer"
    return "plan-task-writer-deep" if tier == "deep" else "plan-task-writer"


def group_span(g):
    return g[0]["id"] if len(g) == 1 else "%s-%s" % (g[0]["id"], g[-1]["id"])


def dispatch_lines(groups, work, kind, installed=True, opencode=False):
    rows = []
    sub = "review-briefs" if kind == "review" else "briefs"
    fmt = "%-4s %-21s %-9s %s" if opencode else "%-4s %-7s %-9s %s"
    for gid, g in groups:
        rows.append(fmt % (gid, row_agent(g, kind, installed, opencode), group_span(g),
                           os.path.join(work, sub, gid + ".md")))
    return rows


def oc_dispatch(groups, work, kind, installed, width):
    """OpenCode dispatch calls, at most `width` per message, one agent per row, never a model alias."""
    sub = "review-briefs" if kind == "review" else "briefs"
    verb = "review" if kind == "review" else "plan"
    major = oc_harness.major(SKILL_DIR)
    rows = []
    for b in range(0, len(groups), width):
        batch = groups[b:b + width]
        rows.append("MESSAGE %d (%d calls, ALL in ONE message):" % (b // width + 1, len(batch)))
        for gid, g in batch:
            rows.append("  " + oc_harness.dispatch_line(row_agent(g, kind, installed, True),
                                                        os.path.join(work, sub, gid + ".md"),
                                                        "%s %s" % (verb, group_span(g)), major))
    return rows
```

Replace the whole `def agent_installed(repo):` function with:

```python
def agent_installed(repo, name="plan-task-writer"):
    home = os.path.expanduser("~")
    for base in (os.path.join(repo, ".opencode", "agents"), os.path.join(home, ".config", "opencode", "agents"),
                 os.path.join(home, ".zcode", "agents"),
                 os.path.join(repo, ".claude", "agents"), os.path.join(home, ".claude", "agents")):
        if os.path.isfile(os.path.join(base, name + ".md")):
            return base
    return None
```

- [ ] **Step 17: Group writers by at most 4 and dispatch per lane width**

In `writing-plans-glm/scripts/plan_tool.py`, replace the whole `def build_agent_lane(a, plan_path, plan, cs, repo, work, spec, warns, key, src):` function with:

```python
def build_agent_lane(a, plan_path, plan, cs, repo, work, spec, warns, key, src):
    opencode = on_opencode()
    cap, capenv = agent_cap()
    width = max(1, min(MAX_WORKERS, a.workers or lane_width()))
    if opencode:
        k = writer_group_count(len(cs), True, width)
    else:
        k = writer_group_count(len(cs), False, max(1, min(MAX_WORKERS, a.workers or cap)))
    shutil.rmtree(os.path.join(work, "briefs"), ignore_errors=True)
    cmap = {c["id"]: c for c in cs}
    parts = cap_groups(partition(cs, k))
    groups = [((g[0]["id"] if len(parts) == len(cs) else "W%02d" % (i + 1)), g) for i, g in enumerate(parts)]
    for gid, g in groups:
        save(os.path.join(work, "briefs", gid + ".md"),
             writer_brief(plan_path, plan, g, cmap, work, spec, repo, a.allow))
    info = json.loads(load(os.path.join(work, "work.json")))
    info["groups"] = {gid: [c["id"] for c in g] for gid, g in groups}
    info["agents"] = width if opencode else k
    save(os.path.join(work, "work.json"), json.dumps(info, indent=1))
    _, n, wave_width = waves_block(cs)
    installed = agent_installed(repo)
    lane = ("LANE agent (no API key found - script-side fan-out unavailable)" if not key
            else "LANE agent (forced)")
    if opencode:
        nmsg = -(-len(groups) // width)
        head = [lane,
                "WORK %s" % work,
                "DISPATCH %d writers in %d message(s) of at most %d background calls | one agent per row"
                % (len(groups), nmsg, width),
                "Send each MESSAGE below verbatim; send the next MESSAGE after every writer of the previous one replied.",
                "ID   AGENT                 TASKS     BRIEF"]
        rows = dispatch_lines(groups, work, "write", installed, True) + oc_dispatch(groups, work, "write", installed, width)
    else:
        agent = "plan-task-writer" if installed else "general-purpose"
        head = [lane,
                "WORK %s" % work,
                "DISPATCH %d writers, ALL in ONE message | subagent_type=%s | description 'plan <ID>'" % (len(groups), agent),
                "prompt (verbatim): Read <brief path> and follow it exactly.",
                "ID   MODEL   TASKS     BRIEF"]
        rows = dispatch_lines(groups, work, "write")
    tail = ["THEN: %s wait %s" % (qtool(), shlex.quote(plan_path)),
            "THEN: %s review %s" % (qtool(), shlex.quote(plan_path)),
            "THEN: %s assemble %s --clean" % (qtool(), shlex.quote(plan_path))]
    if not capenv and not opencode:
        tail.append("NOTE subagent cap assumed %d; `%s setup --apply` raises it where the harness supports it" % (cap, qtool()))
    return report([], warns, "OK contracts: %d tasks | %d waves | max wave width %d | %d writers"
                  % (len(cs), n, wave_width, len(groups)), head + rows + tail)
```

- [ ] **Step 18: Dispatch `plan-reviewer` from review on OpenCode**

In `def cmd_review(a):`, replace the statement that starts with `rows = ["REVIEW %d tasks: %s"` and ends with `"ID   MODEL   TASKS     BRIEF"] + dispatch_lines(groups, work, "review")` with:

```python
    summary = "REVIEW %d tasks: %s" % (len(picked), ", ".join("%s(%s)" % (c["id"], "+".join(w)) for c, w in picked))
    if on_opencode():
        installed = agent_installed(info.get("repo") or repo_root(plan_path), "plan-reviewer")
        width = max(1, min(MAX_WORKERS, a.agents or lane_width()))
        rows = [summary,
                "DISPATCH %d reviewers in %d message(s) of at most %d background calls | one agent per row"
                % (len(groups), -(-len(groups) // width), width),
                "ID   AGENT                 TASKS     BRIEF"] \
            + dispatch_lines(groups, work, "review", installed, True) \
            + oc_dispatch(groups, work, "review", installed, width)
    else:
        rows = [summary,
                "DISPATCH %d reviewers in ONE message | subagent_type=general-purpose | model sonnet | description 'review <ID>'" % len(groups),
                "prompt (verbatim): Read <brief path> and follow it exactly.",
                "ID   MODEL   TASKS     BRIEF"] + dispatch_lines(groups, work, "review")
```

Keep the lines that follow unchanged (`rows.append("THEN run: ...` and the print loop).

- [ ] **Step 19: Run the dispatch tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_plan.py' -k OpenCodeDispatchTests`
Expected: PASS. The run ends with `Ran 7 tests` and `OK`.

- [ ] **Step 20: Run the whole test module and the full suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_adopt_plan.py'`
Expected: PASS. The run ends with `OK`, with no failures or errors.

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no new failures. The failure count is at most the baseline in Global Constraints (11 red from stale fixture paths, fewer if earlier tasks fixed them), and none of the failures is in `test_adopt_plan.py`.

- [ ] **Step 21: Commit**

```bash
cd ..
git add glm-skills/writing-plans-glm/scripts/plan_tool.py glm-skills/writing-plans-glm/opencode/agents/plan-task-writer.md glm-skills/writing-plans-glm/opencode/agents/plan-task-writer-deep.md glm-skills/writing-plans-glm/opencode/agents/plan-reviewer.md glm-skills/_shared/tests/test_adopt_plan.py
git commit -m "feat(writing-plans): OpenCode dispatch_line, deep writer and reviewer agents, writer groups of at most 4"
```

---

### T28: plan_tool.py speed optimizations [P]

**Depends:** —

**Runs after:** T27 (same files)

**Files:**
- Modify: `glm-skills/writing-plans-glm/scripts/plan_tool.py`
- Test: `glm-skills/_shared/tests/test_plan_perf.py`

This task covers spec items WP11, WP13 and WP14. WP12 (writer group count = ceil(tasks / 4), capped at the lane width) is implemented by T27 through `writer_group_count()`, `lane_width()` and its rewritten `build_agent_lane`, so this task does not touch writer grouping. T26 and T27 edit `plan_tool.py` first, so every Modify step below anchors on a code line quoted verbatim, not on a line number. The harness name `detect_harness()` returns for OpenCode is the literal string `"opencode"`.

- [ ] **Step 1: Write the failing test for WP11 (pick_patterns skips the read of low-score candidates)**

Create `glm-skills/_shared/tests/test_plan_perf.py`:

```python
"""Speed optimizations in writing-plans-glm/scripts/plan_tool.py (spec WP11, WP13, WP14)."""
import argparse
import contextlib
import importlib.util
import io
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
PLAN_TOOL = os.path.join(ROOT, "writing-plans-glm", "scripts", "plan_tool.py")
CAP_ENV = ("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", "OPENCODE_MAX_CONCURRENT_SUBAGENTS",
           "ZCODE_MAX_CONCURRENT_SUBAGENTS")


def load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_perf", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pt = load_plan_tool()


def clean_env(**extra):
    """os.environ without any concurrency-cap variable, plus `extra`."""
    env = {k: v for k, v in os.environ.items() if k not in CAP_ENV}
    env.update(extra)
    return mock.patch.dict(os.environ, env, clear=True)


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


class TmpDirCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="plan-perf-")
        os.makedirs(os.path.join(self.tmp, ".git"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class PickPatternsTest(TmpDirCase):
    def test_low_score_candidate_is_not_read(self):
        ten = "".join("line %d\n" % i for i in range(10))
        write(os.path.join(self.tmp, "src", "zzz.py"), ten)
        write(os.path.join(self.tmp, "tests", "test_widget.py"), ten)
        reads = []
        real_load = pt.load

        def counting_load(path):
            reads.append(os.path.relpath(path, self.tmp))
            return real_load(path)

        with mock.patch.object(pt, "load", counting_load), mock.patch.object(pt, "sh", return_value=""):
            got = pt.pick_patterns(["src/zzz.py", "tests/test_widget.py"], self.tmp, "the widget spec")
        self.assertEqual(got, ["tests/test_widget.py"])
        self.assertEqual(reads, [os.path.join("tests", "test_widget.py")])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_perf.py' -k PickPatterns`
Expected: FAIL: `test_low_score_candidate_is_not_read` with `AssertionError: Lists differ: ['src/zzz.py', 'tests/test_widget.py'] != ['tests/test_widget.py']`

- [ ] **Step 3: Skip the read when the score cannot pass the cut**

In `glm-skills/writing-plans-glm/scripts/plan_tool.py`, function `pick_patterns`, find these lines:

```python fragment
        hits = sum(1 for t in toks if t in base or t in f.lower())
        s += min(4.0, 1.2 * hits)
        try:
            n = len(load(os.path.join(repo, f)).splitlines())
```

Replace them with:

```python fragment
        hits = sum(1 for t in toks if t in base or t in f.lower())
        s += min(4.0, 1.2 * hits)
        if s <= 1.5:
            continue  # the size check below can only lower the score: skip the full read
        try:
            n = len(load(os.path.join(repo, f)).splitlines())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_perf.py' -k PickPatterns`
Expected: PASS (`Ran 1 test` ... `OK`)

- [ ] **Step 5: Write the failing tests for WP13 (brief does not inline the convention file OpenCode already loads)**

Append this class to `glm-skills/_shared/tests/test_plan_perf.py`, above the `if __name__ == "__main__":` line:

```python
class BriefConventionsTest(TmpDirCase):
    def run_brief(self, harness):
        write(os.path.join(self.tmp, "AGENTS.md"), "# Rules\nMARKER-RULE-42 always use tabs\n")
        ns = argparse.Namespace(rest=[], spec_lines=900, patterns=4, pattern_lines=700)
        out = io.StringIO()
        old = os.getcwd()
        os.chdir(self.tmp)
        try:
            with clean_env(), \
                    mock.patch.object(pt, "detect_harness", return_value=(harness, "-")), \
                    mock.patch.object(pt, "find_credentials", return_value=("", pt.DEFAULT_BASE, "openai", "-")), \
                    mock.patch.object(pt, "sh", return_value=""), \
                    contextlib.redirect_stdout(out):
                rc = pt.cmd_brief(ns)
        finally:
            os.chdir(old)
        self.assertEqual(rc, 0)
        self.assertNotIn("brief partial", out.getvalue())
        return out.getvalue()

    def test_oc_harness_skips_inlining(self):
        text = self.run_brief("opencode")
        self.assertNotIn("MARKER-RULE-42", text)
        self.assertIn("conventions AGENTS.md (2 lines) - already in the agent context", text)

    def test_oc_harness_inlines_files_it_does_not_load(self):
        # OpenCode loads only the first root match of AGENTS.md / CLAUDE.md, never .claude/CLAUDE.md
        write(os.path.join(self.tmp, "CLAUDE.md"), "MARKER-CLAUDE-7 root rule\n")
        write(os.path.join(self.tmp, ".claude", "CLAUDE.md"), "MARKER-NESTED-9 nested rule\n")
        text = self.run_brief("opencode")
        self.assertNotIn("MARKER-RULE-42", text)
        self.assertIn("MARKER-CLAUDE-7", text)
        self.assertIn("MARKER-NESTED-9", text)

    def test_other_harness_still_inlines(self):
        text = self.run_brief("unknown")
        self.assertIn("MARKER-RULE-42", text)
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_perf.py' -k BriefConventions`
Expected: FAIL: `test_oc_harness_skips_inlining` and `test_oc_harness_inlines_files_it_does_not_load` with `AssertionError: 'MARKER-RULE-42' unexpectedly found in ...` (reported as `FAILED (failures=2)`)

- [ ] **Step 7: Skip the inline of the file OpenCode already loads**

In `glm-skills/writing-plans-glm/scripts/plan_tool.py`, function `cmd_brief`, find this block inside the `for md in (...)` conventions loop:

```python fragment
            if os.path.isfile(p):
                conv.append(md)
                out.append("conventions %s (%d lines) - copy binding rules into Global Constraints:" % (md, len(load(p).splitlines())))
                out.append("  " + "\n  ".join(load(p).splitlines()[:60]))
```

Replace it with (the file is read once; OpenCode loads the first root match of `AGENTS.md` / `CLAUDE.md` into the agent context itself, so only that file is not inlined):

```python fragment
            if os.path.isfile(p):
                conv.append(md)
                md_lines = load(p).splitlines()
                if harness == "opencode" and md in ("AGENTS.md", "CLAUDE.md") and conv[0] == md:
                    out.append("conventions %s (%d lines) - already in the agent context; copy binding rules into Global Constraints"
                               % (md, len(md_lines)))
                    continue
                out.append("conventions %s (%d lines) - copy binding rules into Global Constraints:" % (md, len(md_lines)))
                out.append("  " + "\n  ".join(md_lines[:60]))
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_perf.py' -k BriefConventions`
Expected: PASS (`Ran 3 tests` ... `OK`)

- [ ] **Step 9: Write the failing test for WP14 (`--resume` trusts `.ok` only when it is newer than the body)**

Append this class to `glm-skills/_shared/tests/test_plan_perf.py`, above the `if __name__ == "__main__":` line:

```python
class ResumeTodoTest(TmpDirCase):
    def setUp(self):
        super().setUp()
        self.work = os.path.join(self.tmp, "work")
        self.body = os.path.join(self.work, "tasks", "T01.md")
        write(self.body, "**Files:**\n")
        write(self.body + ".ok", "1")
        self.cs = [{"id": "T01"}, {"id": "T02"}]

    def ids(self, resume):
        return [c["id"] for c in pt.resume_todo(self.cs, self.work, resume)]

    def test_stale_ok_is_rewritten(self):
        now = time.time()
        os.utime(self.body + ".ok", (now - 60, now - 60))
        os.utime(self.body, (now, now))
        self.assertEqual(self.ids(True), ["T01", "T02"])

    def test_fresh_ok_is_skipped(self):
        now = time.time()
        os.utime(self.body, (now - 60, now - 60))
        os.utime(self.body + ".ok", (now, now))
        self.assertEqual(self.ids(True), ["T02"])

    def test_without_resume_everything_is_written(self):
        self.assertEqual(self.ids(False), ["T01", "T02"])
```

- [ ] **Step 10: Run the tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_perf.py' -k ResumeTodo`
Expected: FAIL with `AttributeError: module 'plan_tool_perf' has no attribute 'resume_todo'` (reported as `FAILED (errors=3)`)

- [ ] **Step 11: Compare mtimes on resume**

In `glm-skills/writing-plans-glm/scripts/plan_tool.py`, insert this function right after `def lint_one(cs, c, body, allow, repo):` and its two-line body (just above the `# ---- build (API lane)` comment line):

```python
def resume_todo(cs, work, resume):
    """Tasks the build still has to write. With resume, a task is skipped only when its
    .ok mark is at least as new as its body (done_state), so an edited body is re-linted."""
    if not resume:
        return list(cs)
    return [c for c in cs if done_state(task_path(work, c["id"]), "ok") != "done"]
```

Then in `cmd_build`, replace the line:

```python fragment
    todo = [c for c in cs if not (a.resume and os.path.exists(task_path(work, c["id"]) + ".ok"))]
```

with:

```python fragment
    todo = resume_todo(cs, work, a.resume)
```

- [ ] **Step 12: Run the tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_plan_perf.py'`
Expected: PASS (`Ran 7 tests` ... `OK`)

- [ ] **Step 13: Run the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: no failure or error comes from `test_plan_perf.py` or from any existing `plan_tool` test. The final line is `OK`, or it lists only the pre-existing stale-fixture failures from the baseline.

- [ ] **Step 14: Commit**

```bash
cd ..
git add glm-skills/writing-plans-glm/scripts/plan_tool.py glm-skills/_shared/tests/test_plan_perf.py
git commit -m "feat(writing-plans): skip low-score pattern reads, skip in-context conventions, mtime-checked resume"
cd glm-skills
```

---

### T29: writing-plans SKILL.md bootstrap and CHANGELOG [P]

**Depends:** T27

**Interfaces:**
- Consumes: `plan-task-writer`; `steps: 24`; `plan-task-writer-deep`; `steps: 24`; `plan-reviewer`

**Files:**
- Modify: `glm-skills/writing-plans-glm/SKILL.md:26-34`
- Modify: `glm-skills/writing-plans-glm/CHANGELOG.md:1-1`

- [ ] **Step 1: Replace bootstrap snippet in SKILL.md**

Replace lines 26-34 in SKILL.md. The problematic `ls -d ... | head -1` must be replaced with the shared bootstrap pattern that respects `$OPENCODE_CONFIG_DIR` and checks directories in order without sorting:

```bash
for d in "${OPENCODE_CONFIG_DIR:-}/skills/writing-plans" \
  .opencode/skills/writing-plans \
  ~/.config/opencode/skills/writing-plans \
  .agents/skills/writing-plans \
  ~/.agents/skills/writing-plans \
  .claude/skills/writing-plans \
  ~/.claude/skills/writing-plans \
  ~/.zcode/skills/writing-plans; do
  [ -f "$d/scripts/plan_tool.py" ] && T="$d/scripts/plan_tool.py" && break
done
[ -z "$T" ] && echo "writing-plans skill not found in any standard location" >&2 && exit 1
python3 "$T" brief SPEC
```

This change:
- Checks `$OPENCODE_CONFIG_DIR` first (v2 standard location)
- Respects `.opencode/skills` before user homes (project scope before user scope)
- Includes all six OpenCode/ZCode/Claude directories in the correct order
- Exits with a clear error message on miss instead of running `python3 "" brief`
- Uses `[ -z "$T" ]` check instead of `ls` and `head`, eliminating alphabetical sorting

The pattern mirrors `systematic-debugging-glm/SKILL.md:18` for consistency across GLM skills.

- [ ] **Step 2: Update CHANGELOG.md frontmatter**

After line 1 (the main heading), insert a blank line and a new "Fixes:" section before the "Target:" line. The section should read:

```
**Fixes:** (WP5) Bootstrap now respects `$OPENCODE_CONFIG_DIR`, checks locations in project-first order, and exits with a clear error on miss (no `python3 "" brief`).

```

This documents the fix for defect WP5 (shared bootstrap snippet adoption) as specified in the hardening spec. The section goes between the heading and "Target:" (currently line 3).

- [ ] **Step 3: Verify SKILL.md renders correctly**

Run: `head -40 glm-skills/writing-plans-glm/SKILL.md`

Expected: The new bootstrap snippet spans lines 26-34, properly indented, no syntax errors, exits with a message on file miss.

- [ ] **Step 4: Commit**

```bash
git add glm-skills/writing-plans-glm/SKILL.md glm-skills/writing-plans-glm/CHANGELOG.md
git commit -m "fix(writing-plans): adopt shared bootstrap snippet for OpenCode v1/v2 compatibility (WP5)"
```

---

### T30: brainstorming context.sh OpenCode detection [P]

**Depends:** T03

**Interfaces:**
- Consumes: `python3 oc_harness.py harness [--script PATH]`; `<harness> <major>`

**Files:**
- Modify: `glm-skills/brainstorming-glm/scripts/context.sh:12-38`
- Modify: `glm-skills/_shared/tests/test_brainstorm_oc.py`

This task fixes BR1 and BR11 (spec 5.7). `context.sh` is a preload, so it must stay read-only, print at most 55 lines and always exit 0. Detection prefers the vendored CLI `python3 oc_harness.py harness [--script PATH]`, which prints `<harness> <major>`. If that CLI is missing, fails, or prints `unknown`, the script falls back to a POSIX sh mirror of `harness()`: `OPENCODE_TERMINAL` (the only variable v2 sets), `OPENCODE`/`OPENCODE_BIN`, a `.oc-major` file in the skill dir (written by the installer), or a skill dir that sits under an `opencode/` or `.opencode/` directory. All commands run from `glm-skills/`.

- [ ] **Step 1: Write the failing detection tests**

In `_shared/tests/test_brainstorm_oc.py`, add these imports next to the existing `import re` / `import sys` lines (keep the list alphabetical):

```python
import shutil
import subprocess
import tempfile
```

Then insert the following block just above the final `if __name__ == "__main__":` line:

```python
CONTEXT_SH = os.path.join(SKILL_DIR, "scripts", "context.sh")

FAKE_CLI = (
    "import sys\n"
    "with open(__file__ + '.args', 'w') as f:\n"
    "    f.write(' '.join(sys.argv[1:]))\n"
    "sys.stdout.write(%r)\n"
    "sys.exit(%d)\n"
)


def make_skill(root, cli_output=None, cli_exit=0, oc_major=None):
    scripts = os.path.join(root, "scripts")
    os.makedirs(scripts)
    shutil.copy(CONTEXT_SH, os.path.join(scripts, "context.sh"))
    if cli_output is not None:
        with open(os.path.join(scripts, "oc_harness.py"), "w") as f:
            f.write(FAKE_CLI % (cli_output, cli_exit))
    if oc_major is not None:
        with open(os.path.join(root, ".oc-major"), "w") as f:
            f.write(oc_major)
    return root


def run_context(skill_root, home, extra_env=None):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": home}
    env.update(extra_env or {})
    return subprocess.run(
        ["sh", os.path.join(skill_root, "scripts", "context.sh")],
        cwd=home,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


class ContextCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)

    def plain_root(self):
        return os.path.join(self.tmp, "plain", "brainstorming")

    def line_starting(self, out, prefix):
        for line in out.splitlines():
            if line.startswith(prefix):
                return line
        self.fail("no %r line in:\n%s" % (prefix, out))


class TestBrainstormContextHarness(ContextCase):
    def test_cli_result_sets_harness_and_major(self):
        root = make_skill(self.plain_root(), cli_output="opencode 2\n")
        proc = run_context(root, self.home)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "),
            "harness: opencode oc_major=2",
        )

    def test_cli_receives_harness_subcommand_and_script(self):
        root = make_skill(self.plain_root(), cli_output="opencode 2\n")
        run_context(root, self.home)
        with open(os.path.join(root, "scripts", "oc_harness.py.args")) as f:
            args = f.read()
        self.assertTrue(args.startswith("harness --script "), args)
        self.assertTrue(args.endswith("/scripts/context.sh"), args)

    def test_opencode_terminal_env_without_cli(self):
        root = make_skill(self.plain_root())
        proc = run_context(root, self.home, {"OPENCODE_TERMINAL": "1"})
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "),
            "harness: opencode oc_major=unknown",
        )

    def test_oc_major_file_without_cli(self):
        root = make_skill(self.plain_root(), oc_major="1\n")
        proc = run_context(root, self.home)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "),
            "harness: opencode oc_major=1",
        )

    def test_install_location_without_cli(self):
        root = make_skill(
            os.path.join(self.home, ".config", "opencode", "skills", "brainstorming")
        )
        proc = run_context(root, self.home)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "),
            "harness: opencode oc_major=unknown",
        )

    def test_failing_cli_falls_back_to_sh_mirror(self):
        root = make_skill(self.plain_root(), cli_output="", cli_exit=1)
        proc = run_context(root, self.home, {"OPENCODE_TERMINAL": "1"})
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "),
            "harness: opencode oc_major=unknown",
        )

    def test_cli_unknown_without_signals_stays_unknown(self):
        root = make_skill(self.plain_root(), cli_output="unknown 0\n")
        proc = run_context(root, self.home)
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "), "harness: unknown"
        )

    def test_claude_code_env_wins_over_cli(self):
        root = make_skill(self.plain_root(), cli_output="opencode 2\n")
        proc = run_context(root, self.home, {"CLAUDECODE": "1"})
        self.assertEqual(
            self.line_starting(proc.stdout, "harness: "), "harness: claude-code"
        )
```

- [ ] **Step 2: Run the detection tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_brainstorm_oc.py' -k TestBrainstormContextHarness`
Expected: FAIL. The output ends with `FAILED (failures=5, errors=1)`. The five failures are `AssertionError: 'harness: unknown' != 'harness: opencode oc_major=...'`, and the error is `FileNotFoundError` for `oc_harness.py.args` in `test_cli_receives_harness_subcommand_and_script`. `test_cli_unknown_without_signals_stays_unknown` and `test_claude_code_env_wins_over_cli` pass.

- [ ] **Step 3: Implement OpenCode detection in context.sh**

Make three edits in `brainstorming-glm/scripts/context.sh`. The existing comment line above `harness=unknown` and the non-OpenCode `elif` lines stay as they are.

First, replace the line `harness=unknown` (line 13) with this block. It asks the vendored CLI first, and the result is applied after the env chain:

```sh
harness=unknown
oc_major=unknown
oc_line=
if [ -f "$skill_dir/scripts/oc_harness.py" ] && command -v python3 >/dev/null 2>&1; then
  oc_line=$(python3 "$skill_dir/scripts/oc_harness.py" harness --script "$skill_dir/scripts/context.sh" 2>/dev/null | head -n 1)
fi
```

Second, replace the line `elif [ -n "$OPENCODE" ] || [ -n "$OPENCODE_BIN" ]; then harness=opencode` (line 16) with these two lines. They are the POSIX sh mirror of `harness()`: v2 sets only `OPENCODE_TERMINAL`, the installer writes `.oc-major`, and OpenCode installs live under an `opencode/` or `.opencode/` directory:

```sh fragment
elif [ -n "$OPENCODE_TERMINAL" ] || [ -n "$OPENCODE" ] || [ -n "$OPENCODE_BIN" ] || [ -f "$skill_dir/.oc-major" ]; then harness=opencode
elif case "$skill_dir" in */opencode/*|*/.opencode/*) true ;; *) false ;; esac; then harness=opencode
```

Third, replace the line `echo "harness: $harness"` (line 22, right after the chain's closing `fi`) with this block. A CLI answer other than `unknown` wins over the sh mirror, but never over a Claude Code env:

```sh
set -- $oc_line
if [ "$harness" != claude-code ] && [ -n "${1:-}" ] && [ "$1" != unknown ]; then
  harness=$1
  [ -n "${2:-}" ] && oc_major=$2
fi
if [ "$harness" = opencode ] && [ "$oc_major" = unknown ] && [ -f "$skill_dir/.oc-major" ]; then
  oc_major=$(head -n 1 "$skill_dir/.oc-major" 2>/dev/null | tr -cd '0-9')
  [ -n "$oc_major" ] || oc_major=unknown
fi
if [ "$harness" = opencode ]; then
  echo "harness: opencode oc_major=$oc_major"
else
  echo "harness: $harness"
fi
```

Leave the rest of the file unchanged, including the final `exit 0`.

- [ ] **Step 4: Run the detection tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_brainstorm_oc.py' -k TestBrainstormContextHarness`
Expected: PASS. The output ends with `Ran 8 tests` and `OK`.

- [ ] **Step 5: Write the failing caps tests**

Insert this class in `_shared/tests/test_brainstorm_oc.py` right after `TestBrainstormContextHarness`, above `if __name__ == "__main__":`:

```python
class TestBrainstormContextCaps(ContextCase):
    def test_opencode_caps_default_width_is_8(self):
        root = make_skill(self.plain_root())
        proc = run_context(root, self.home, {"OPENCODE_TERMINAL": "1"})
        caps = self.line_starting(proc.stdout, "caps: ")
        self.assertIn("lanes=8", caps)
        self.assertIn("--width", caps)
        self.assertNotIn("subagents=", caps)

    def test_opencode_caps_honours_oc_max_lanes(self):
        root = make_skill(self.plain_root())
        proc = run_context(
            root, self.home, {"OPENCODE_TERMINAL": "1", "OC_MAX_LANES": "4"}
        )
        self.assertIn("lanes=4", self.line_starting(proc.stdout, "caps: "))

    def test_opencode_caps_prints_oc_major(self):
        root = make_skill(self.plain_root(), oc_major="2\n")
        proc = run_context(root, self.home)
        self.assertIn("oc_major=2", self.line_starting(proc.stdout, "caps: "))

    def test_claude_caps_unchanged(self):
        root = make_skill(self.plain_root())
        proc = run_context(root, self.home, {"CLAUDECODE": "1"})
        self.assertIn("subagents=20", self.line_starting(proc.stdout, "caps: "))

    def test_opencode_output_is_bounded_and_exits_zero(self):
        root = make_skill(self.plain_root(), oc_major="2\n")
        proc = run_context(root, self.home, {"OPENCODE_TERMINAL": "1"})
        self.assertEqual(proc.returncode, 0)
        self.assertLessEqual(len(proc.stdout.splitlines()), 55)
```

- [ ] **Step 6: Run the caps tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_brainstorm_oc.py' -k TestBrainstormContextCaps`
Expected: FAIL. The output ends with `FAILED (failures=3)`: `AssertionError: 'lanes=8' not found in 'caps: subagents=20 ...'`, `'lanes=4' not found` and `'oc_major=2' not found`. `test_claude_caps_unchanged` and `test_opencode_output_is_bounded_and_exits_zero` pass.

- [ ] **Step 7: Print OpenCode caps in context.sh**

In `brainstorming-glm/scripts/context.sh`, replace the single line that starts with `echo "caps: subagents=` (line 38 before Step 3) with:

```sh
if [ "$harness" = opencode ]; then
  echo "caps: lanes=${OC_MAX_LANES:-8} (set OC_MAX_LANES or pass oc_harness run --width N; default 8) oc_major=$oc_major"
else
  echo "caps: subagents=${CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS:-20} workflow=${CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS:-16} compact_window=${CLAUDE_CODE_AUTO_COMPACT_WINDOW:-default}"
fi
```

- [ ] **Step 8: Run both test classes and the shell syntax check**

Run: `sh -n brainstorming-glm/scripts/context.sh && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_brainstorm_oc.py' -k TestBrainstormContext`
Expected: PASS. `sh -n` prints nothing, and the unittest output ends with `Ran 13 tests` and `OK`.

- [ ] **Step 9: Run the full suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: the 13 new tests pass, and the suite shows no failures beyond the red tests already listed in the baseline (11 red from stale fixture paths, fewer if earlier tasks fixed them).

- [ ] **Step 10: Commit**

```bash
cd ..
git add glm-skills/brainstorming-glm/scripts/context.sh glm-skills/_shared/tests/test_brainstorm_oc.py
git commit -m "fix(brainstorming): detect OpenCode v1/v2 in context.sh and print OpenCode lane caps"
```

---

### T31: brainstorming visual-companion scripts [P]

**Depends:** —

**Files:**
- Modify: `glm-skills/brainstorming-glm/scripts/start-server.sh:74-82`
- Modify: `glm-skills/brainstorming-glm/scripts/server.cjs:639-645`
- Modify: `glm-skills/brainstorming-glm/scripts/helper.js:160-164`
- Test: `glm-skills/_shared/tests/test_brainstorm_server.py`

This task fixes three visual-companion defects: a relative `--project-dir` breaks startup (BR3), SIGTERM/SIGHUP leave a stale `server-info` that still reads as alive (BR5), and `brainstorm.choice()` sends no `choice` key, so the server drops the event (BR7). All commands run from `glm-skills/` (`cd glm-skills` first). The tests need `node` and `bash` on PATH and skip otherwise.

- [ ] **Step 1: Write the failing test for a relative `--project-dir` (BR3)**

Create `_shared/tests/test_brainstorm_server.py` with this content:

```python
"""Tests for the brainstorming visual-companion scripts (start-server.sh, server.cjs, helper.js)."""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "brainstorming-glm" / "scripts"
START = SCRIPTS / "start-server.sh"
SERVER = SCRIPTS / "server.cjs"
HELPER = SCRIPTS / "helper.js"

HAVE_NODE = shutil.which("node") is not None
HAVE_BASH = shutil.which("bash") is not None


def _clean_env():
    env = dict(os.environ)
    for name in ("CODEX_CI", "BRAINSTORM_PORT", "BRAINSTORM_TOKEN", "BRAINSTORM_OPEN",
                 "BRAINSTORM_PORT_FILE", "BRAINSTORM_TOKEN_FILE", "BRAINSTORM_DIR"):
        env.pop(name, None)
    return env


def _stop_pid(pid):
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


@unittest.skipUnless(HAVE_NODE and HAVE_BASH, "node and bash required")
class StartServerProjectDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bs-start-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_relative_project_dir_starts_and_is_absolutized(self):
        proc = subprocess.run(
            ["bash", str(START), "--project-dir", "proj", "--background"],
            cwd=self.tmp, env=_clean_env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=30,
        )
        out = proc.stdout.strip()
        self.assertIn("server-started", out, out + proc.stderr)
        info = json.loads(out.splitlines()[-1])
        pid_file = Path(info["state_dir"]) / "server.pid"
        if pid_file.exists():
            self.addCleanup(_stop_pid, int(pid_file.read_text().strip()))
        self.assertTrue(os.path.isabs(info["screen_dir"]), info["screen_dir"])
        expected_root = os.path.realpath(os.path.join(self.tmp, "proj", ".brainstorm", "brainstorm"))
        self.assertTrue(
            os.path.realpath(info["screen_dir"]).startswith(expected_root + os.sep),
            info["screen_dir"],
        )
        self.assertEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_brainstorm_server.py' -k StartServerProjectDirTest`
Expected: FAIL with `AssertionError: 'server-started' not found in '{"error": "Server failed to start within 5 seconds"}'`

- [ ] **Step 3: Absolutize `--project-dir` before any `cd`**

In `brainstorming-glm/scripts/start-server.sh`, find the block that ends the idle-timeout validation (`export BRAINSTORM_IDLE_TIMEOUT_MS=...` followed by `fi`). Directly after that `fi` and before `is_windows_like_shell() {`, insert:

```bash
if [[ -n "$PROJECT_DIR" ]]; then
  # Absolutize now: the script later does `cd "$SCRIPT_DIR"`, and a relative
  # path would then resolve against the scripts folder (log redirect fails).
  mkdir -p "$PROJECT_DIR" 2>/dev/null
  if ! PROJECT_DIR="$(cd "$PROJECT_DIR" 2>/dev/null && pwd)"; then
    echo "{\"error\": \"--project-dir is not a usable directory\"}"
    exit 1
  fi
fi
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_brainstorm_server.py' -k StartServerProjectDirTest`
Expected: PASS (`Ran 1 test`, `OK`)

- [ ] **Step 5: Write the failing test for the SIGTERM/SIGHUP handler (BR5)**

Append this class to `_shared/tests/test_brainstorm_server.py`, above the `if __name__ == "__main__":` line:

```python
@unittest.skipUnless(HAVE_NODE, "node required")
class ServerSignalTest(unittest.TestCase):
    def _start(self):
        tmp = tempfile.mkdtemp(prefix="bs-sig-")
        self.addCleanup(shutil.rmtree, tmp, True)
        env = _clean_env()
        env["BRAINSTORM_DIR"] = tmp
        proc = subprocess.Popen(
            ["node", str(SERVER)], env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(_stop_pid, proc.pid)
        info = Path(tmp) / "state" / "server-info"
        deadline = time.time() + 10
        while time.time() < deadline and not info.exists():
            time.sleep(0.05)
        self.assertTrue(info.exists(), "server never wrote server-info")
        return proc, Path(tmp) / "state"

    def _assert_stops_cleanly(self, sig, name):
        proc, state = self._start()
        proc.send_signal(sig)
        proc.wait(timeout=10)
        stopped = state / "server-stopped"
        self.assertTrue(stopped.exists(), "server-stopped not written")
        self.assertFalse((state / "server-info").exists(), "stale server-info left behind")
        self.assertEqual(json.loads(stopped.read_text())["reason"], name)
        self.assertEqual(proc.returncode, 0)

    def test_sigterm_writes_server_stopped(self):
        self._assert_stops_cleanly(signal.SIGTERM, "SIGTERM")

    def test_sighup_writes_server_stopped(self):
        self._assert_stops_cleanly(signal.SIGHUP, "SIGHUP")
```

- [ ] **Step 6: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_brainstorm_server.py' -k ServerSignalTest`
Expected: FAIL with `AssertionError: False is not true : server-stopped not written` (both tests)

- [ ] **Step 7: Add the signal handlers in `server.cjs`**

In `brainstorming-glm/scripts/server.cjs`, inside `startServer()`, find the line `lifecycleCheck.unref();` and insert directly after it:

```javascript
  // SIGTERM/SIGHUP (harness stop, start-server.sh restart, terminal close) must
  // go through shutdown() so server-info is removed and server-stopped is
  // written; otherwise a stale server-info reads as a live server.
  let stopping = false;
  function onSignal(signalName) {
    if (stopping) return;
    stopping = true;
    // server.close() waits for keep-alive HTTP sockets; do not hang on them.
    setTimeout(() => process.exit(0), 2000).unref();
    shutdown(signalName);
  }
  process.on('SIGTERM', () => onSignal('SIGTERM'));
  process.on('SIGHUP', () => onSignal('SIGHUP'));
```

- [ ] **Step 8: Check the syntax of `server.cjs`**

Run: `node --check brainstorming-glm/scripts/server.cjs`
Expected: no output, exit status 0

- [ ] **Step 9: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_brainstorm_server.py' -k ServerSignalTest`
Expected: PASS (`Ran 2 tests`, `OK`)

- [ ] **Step 10: Write the failing test for `brainstorm.choice()` (BR7)**

Append this class to `_shared/tests/test_brainstorm_server.py`, above the `if __name__ == "__main__":` line:

```python
HELPER_DRIVER = """
const sent = [];
class FakeWS {
  constructor(url) { this.url = url; this.readyState = 1; }
  send(s) { sent.push(JSON.parse(s)); }
  close() {}
}
FakeWS.OPEN = 1;
global.WebSocket = FakeWS;
global.window = {
  location: { host: 'localhost:1', reload() {}, replace() {} },
  sessionStorage: { getItem() { return null; } }
};
global.document = {
  addEventListener() {},
  querySelector() { return null; },
  createElement() { return { style: {} }; },
  body: null
};
require(%s);
window.brainstorm.choice('b', { text: 'Option B' });
process.stdout.write(JSON.stringify(sent));
"""


@unittest.skipUnless(HAVE_NODE, "node required")
class HelperChoiceTest(unittest.TestCase):
    def test_choice_sends_choice_key(self):
        script = HELPER_DRIVER % json.dumps(str(HELPER))
        proc = subprocess.run(
            ["node", "-e", script],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=30,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        sent = json.loads(proc.stdout)
        self.assertEqual(len(sent), 1, sent)
        event = sent[0]
        self.assertEqual(event["type"], "choice")
        self.assertEqual(event.get("choice"), "b", event)
        self.assertEqual(event["value"], "b")
        self.assertEqual(event["text"], "Option B")
```

- [ ] **Step 11: Run the test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_brainstorm_server.py' -k HelperChoiceTest`
Expected: FAIL with `AssertionError: None != 'b'`

- [ ] **Step 12: Send the `choice` key from `brainstorm.choice()`**

In `brainstorming-glm/scripts/helper.js`, inside the `window.brainstorm = { ... }` object, replace the line

```javascript fragment
    choice: (value, metadata = {}) => sendEvent({ type: 'choice', value, ...metadata })
```

with

```javascript fragment
    // server.cjs records only events that carry a `choice` key; send it too.
    choice: (value, metadata = {}) => sendEvent({ type: 'choice', value, choice: value, ...metadata })
```

- [ ] **Step 13: Run the test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_brainstorm_server.py' -k HelperChoiceTest`
Expected: PASS (`Ran 1 test`, `OK`)

- [ ] **Step 14: Run the whole module and check the helper syntax**

Run: `node --check brainstorming-glm/scripts/helper.js && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_brainstorm_server.py'`
Expected: PASS (`Ran 4 tests`, `OK`)

- [ ] **Step 15: Commit**

```bash
cd "$(git rev-parse --show-toplevel)"
git add glm-skills/brainstorming-glm/scripts/start-server.sh glm-skills/brainstorming-glm/scripts/server.cjs glm-skills/brainstorming-glm/scripts/helper.js glm-skills/_shared/tests/test_brainstorm_server.py
git commit -m "fix(brainstorming): absolutize --project-dir, SIGTERM/SIGHUP write server-stopped, choice() sends choice key"
```

---

### T32: brainstorming SKILL.md, playbooks and researcher agent [P]

**Depends:** T04, T30

**Interfaces:**
- Consumes: `python3 oc_harness.py result OUT_DIR`

**Files:**
- Modify: `glm-skills/brainstorming-glm/SKILL.md`
- Modify: `glm-skills/brainstorming-glm/architectural.md`
- Modify: `glm-skills/brainstorming-glm/visual-companion.md:73-80`
- Modify: `glm-skills/brainstorming-glm/opencode/agents/researcher.md:16`
- Modify: `glm-skills/brainstorming-glm/CHANGELOG.md`

This task changes documentation only (spec items BR2, BR4, BR6, BR8, BR9 agent side, BR10, BR12, BR13, BR14, BR16). The "test" is a grep-based doc check kept in a temp file outside the repo. All commands run from `glm-skills/` (`cd glm-skills`).

- [ ] **Step 1: Write the failing doc check**

Create the check script in a temp location (not part of the repo):

```bash
cat > /tmp/t32-doc-check.sh <<'EOF'
fail=0
has() { grep -qF -- "$2" "$1" || { echo "MISSING in $1: $2"; fail=1; }; }
hasnt() { if grep -qF -- "$2" "$1"; then echo "STALE in $1: $2"; fail=1; fi; }
S=brainstorming-glm/SKILL.md
A=brainstorming-glm/architectural.md
V=brainstorming-glm/visual-companion.md
R=brainstorming-glm/opencode/agents/researcher.md
C=brainstorming-glm/CHANGELOG.md
has "$S" 'Architectural: `architectural.md` in round 1.'
hasnt "$S" '1. `research-playbook.md`'
has "$S" 'sh <Base directory>/scripts/context.sh'
hasnt "$S" 'OpenCode v1: lanes become direct calls'
has "$S" '**OpenCode lane rule**'
has "$S" 'never `general-purpose` or `Explore`'
has "$S" '${OPENCODE_CONFIG_DIR:+$OPENCODE_CONFIG_DIR/skills/brainstorming}'
has "$S" '.zcode/skills/brainstorming'
has "$S" 'brainstorming: oc_harness.py not found'
has "$S" '`background: true` and a `timeout`'
has "$S" 'python3 "$H/oc_harness.py" result "$OUT"'
has "$S" 'python3 oc_harness.py result OUT_DIR'
hasnt "$S" 'read `<id>.jsonl`'
has "$S" '.brainstorm/drafts/lanes.json'
has "$S" 'Tool-name map, v1:'
has "$S" 'Tool-name map, v2:'
has "$A" 'the main session writes the pre-draft'
has "$A" 'OpenCode has no TaskStop'
has "$A" 'pass the committed spec path'
has "$V" 'OpenCode v2 —'
has "$R" 'never wait on a prompt'
has "$C" '# 9.3-glm'
if [ "$fail" -eq 0 ]; then echo "T32 doc check: OK"; else echo "T32 doc check: FAIL"; exit 1; fi
EOF
```

- [ ] **Step 2: Run the check to verify it fails**

Run: `sh /tmp/t32-doc-check.sh`
Expected: FAIL. The last line is `T32 doc check: FAIL`, preceded by lines such as `MISSING in brainstorming-glm/SKILL.md: Architectural: \`architectural.md\` in round 1.` and `STALE in brainstorming-glm/SKILL.md: OpenCode v1: lanes become direct calls`. Exit status 1.

- [ ] **Step 3: Fix the raw `!` fallback text in SKILL.md (BR10)**

In `brainstorming-glm/SKILL.md`, under `## Live context`, replace the paragraph that starts `Trust this block.` and ends `run that script in round 1.` with:

```text
Trust this block. Never re-run `ls`, `find`, `git status`, or `cat` on
manifests. Reference files live in `skill_dir`; read by absolute path. A
raw `!` line above instead of output (OpenCode ignores `!` preloads and
leaves `${CLAUDE_SKILL_DIR}` empty): if a context block with a `harness:`
line is already in the conversation (the `/brainstorm` command injects
one), use it and skip the script. Otherwise run
`sh <Base directory>/scripts/context.sh` as a round-1 call, with the
"Base directory for this skill" path in place of `<Base directory>`.
```

- [ ] **Step 4: Join the split R9 rule in SKILL.md (BR6)**

In `## R9 — Load only what the path needs`, replace the body (from `Spike/Bounded: this file only.` through `` `visual-companion.md` only if accepted.``, including the stray `1. \`research-playbook.md\`` list line) with:

```text
Spike/Bounded: this file only. Architectural: `architectural.md` in round 1.
`research-playbook.md` for >3 web lanes or conflicting evidence.
`glm-tuning.md` only when configuring the runtime or hitting a
GLM-specific failure. `visual-companion.md` only if accepted.
```

- [ ] **Step 5: Rewrite the Harness fallbacks section in SKILL.md (BR2, BR4, BR8, BR14, BR16, bootstrap)**

Keep the `Harness fallbacks` heading line. Replace everything below it, down to (not including) the `Visual companion` heading line, with the block below. It removes the contradictory v1 "direct calls" row, the old three-path loop, the raw `.jsonl` read and the single-version tool map.

````text
Live context prints a `harness:` line (and `oc_major:` on OpenCode).
Missing capability → substitute, never stall.

| Missing | Substitute |
| --- | --- |
| Agent / subagents | OpenCode: follow the OpenCode lane rule below. |
| AskUserQuestion | v2 `question`; otherwise plain text, numbered, approval as question 1. |
| ToolSearch | Tools are already live; skip it. |
| Workflow | Run waves of lanes. |
| `!` preprocessing (raw `!` above) | Context block already present → use it. Else run `sh <Base directory>/scripts/context.sh` as your first round-1 call. |
| TaskCreate | v1 `todowrite`; v2 track state in the message per R5. |

**OpenCode lane rule** (one rule, picked by `oc_major`):

1. v2 → dispatch each lane as a background `subagent` call: `agent:
   "explorer"` (Code lane) or `"researcher"` (Web lane), a short
   `description`, `prompt` = the filled R11 template, `background: true`,
   no `model` override (effort comes from the agent's own `variant`).
   Fire them one after another without waiting. Background `subagent`
   unavailable → rule 2.
2. v1 → run the lanes as processes with `oc_harness.py run` (below).
3. `task` (v1) or a foreground `subagent` (v2) ONLY as the fallback when
   rule 1 or 2 fails. Agent `explorer`, `researcher` or `general`, never
   `general-purpose` or `Explore`: those do not exist on OpenCode.

Running `oc_harness.py run`. `CLAUDE_SKILL_DIR` is not set on OpenCode.
Put the "Base directory for this skill" path in `BASE` when the skill
header shows it, then resolve the scripts directory in this order:

```bash
BASE=""
H=""
for d in "$BASE" \
  "${OPENCODE_CONFIG_DIR:+$OPENCODE_CONFIG_DIR/skills/brainstorming}" \
  .opencode/skills/brainstorming \
  ~/.config/opencode/skills/brainstorming \
  .agents/skills/brainstorming ~/.agents/skills/brainstorming \
  .claude/skills/brainstorming ~/.claude/skills/brainstorming \
  .zcode/skills/brainstorming; do
  if [ -n "$d" ] && [ -f "$d/scripts/oc_harness.py" ]; then H="$d/scripts"; break; fi
done
[ -n "$H" ] || { echo "brainstorming: oc_harness.py not found in any skills dir; run install-opencode.sh"; exit 1; }
OUT=".brainstorm/drafts/lanes"
mkdir -p "$OUT"
python3 "$H/oc_harness.py" run .brainstorm/drafts/lanes.json --out "$OUT"
python3 "$H/oc_harness.py" result "$OUT"
```

Write `.brainstorm/drafts/lanes.json` before the call (R0 allows writes
under `.brainstorm/drafts/`). It is a JSON array of lane objects. Each
lane needs `id` (unique string), `agent` (`explorer` or `researcher`, the
neutral read-only/web agents installed from `opencode/agents/`), `model`
(`flash` or `pro`), `effort` (`low` for these lanes), `dir` (working
directory for that lane) and `brief` (the per-lane user message: task,
root/stack, today's date, this lane's slice or angle, the siblings it
must stay out of, and its one question; the same fields the Code/Web
lane templates in R11 fill per lane). The brief goes to each lane on
stdin.

The run takes minutes, longer than a shell call's default limit: v2 kills
a foreground shell call after 120 s and orphans the web lanes. On v2 make
the call through `shell` with `background: true` and a `timeout` that
covers the slowest lane; on v1 give the `bash` tool a `timeout` that
covers the slowest lane. Stopping the call stops every lane (the harness
kills each lane's process group).

Read results with `python3 oc_harness.py result OUT_DIR` (the last line
of the block above): it prints each lane's final FINDINGS/CLAIMS text.
Never open the raw `<id>.jsonl` stream. `<id>.done` holds the status
JSON and `<id>.err` the lane error.

Tool-name map, v1: `task` (lane fallback only), `todowrite` (TaskCreate),
`webfetch` (WebFetch), `bash` (Bash). v1 has no web search tool: use
`webfetch` on the R10.2 fetch-friendly endpoints. No AskUserQuestion:
plain-text numbered questions with approval as item 1.

Tool-name map, v2: `subagent` (lane), `shell` (Bash), `websearch`
(WebSearch), `webfetch` (WebFetch), `question` (AskUserQuestion). No
TaskCreate equivalent: carry state per R5.
````

- [ ] **Step 6: Fix the OpenCode gaps in architectural.md (BR12)**

In `brainstorming-glm/architectural.md` §3, replace the `- **Spec pre-draft**` bullet (from `- **Spec pre-draft** — one lane` through `A rejected design is overwritten later.`) with:

```text
- **Spec pre-draft** — one lane, only when file writes will not raise a
  permission prompt (acceptEdits, auto, or bypass mode). Use a `fork` if
  the harness offers one (it inherits the conversation); otherwise
  `general-purpose` with the design pasted. It writes to
  `.brainstorm/drafts/<topic>-design.md` (never the specs path), does not
  commit, and returns only the path. A rejected design is overwritten later.
  On OpenCode the lane agents (`explorer`, `researcher`) are `edit: deny`,
  so no lane can write it: the main session writes the pre-draft itself
  to the same path as the last call of the design turn.
```

In §4 step 1, replace the first sentence `If a pre-draft lane is still running, stop it (TaskStop) and write the spec yourself.` with:

```text
1. If a pre-draft lane is still running, stop it (TaskStop) and write the
   spec yourself. OpenCode has no TaskStop and no pre-draft lane: skip
   straight to the move below.
```

Keep the rest of step 1 (`Otherwise move the draft to` … `if available.`) unchanged.

Replace the §5 body `Invoke \`writing-plans\`. No other skill, no code, no scaffolding.` with:

```text
Invoke `writing-plans` and pass the committed spec path
(`docs/specs/YYYY-MM-DD-<topic>-design.md`, or the path user
preferences chose) as its input. No other skill, no code, no scaffolding.
```

- [ ] **Step 7: Add the OpenCode platform note to visual-companion.md (BR13)**

In `brainstorming-glm/visual-companion.md`, in the `Platform notes:` paragraph, insert this text right after the sentence ending `via its background shell mechanism.` and before `Any harness that`:

```text
OpenCode v2 — add `--foreground` and run it through `shell` with
`background: true` (a foreground shell call is killed after 120 s, which
takes the server with it); read `server-info` next turn. OpenCode v1 —
run as above (the script backgrounds itself).
```

- [ ] **Step 8: Harden the researcher agent against a missing websearch provider (BR9)**

In `brainstorming-glm/opencode/agents/researcher.md`, replace rule line 16 `3 Web search and web fetch only. Never shell commands or scripts.` with this single line (keep the numbering, the other rules and the frontmatter unchanged; the websearch permission itself is rendered by `oc_harness.py`):

```text
3 Web search and web fetch only. Never shell commands or scripts. Web search missing, failing, or asking for input → switch to web fetch on primary URLs (registries, raw READMEs, changelogs); never wait on a prompt.
```

- [ ] **Step 9: Record the changes in CHANGELOG.md**

If the first line of `brainstorming-glm/CHANGELOG.md` already starts with the `9.3-glm` entry heading (added by an earlier task), append the bullets below to that entry. Otherwise insert, at the very top of the file above the `9.2-glm (from 9.1)` heading, a level-1 heading line whose text is `9.3-glm (from 9.2) — OpenCode v1/v2 hardening` (one `#`, a space, then that text), a blank line, then the bullets below, then a blank line:

```text
- SKILL.md: one OpenCode lane rule. v2 dispatches background `subagent`
  lanes (`explorer`/`researcher`), v1 runs `oc_harness.py run`, and
  `task` is only the fallback. The fallback agent is `general`, never
  `general-purpose` or `Explore`.
- SKILL.md: `oc_harness.py run` is never a foreground call. On v2 it goes
  through `shell` with `background: true` and a `timeout`, because v2
  kills a foreground shell call after 120 s and orphans web lanes.
- SKILL.md: results come from `oc_harness.py result <out>` instead of
  the raw `<id>.jsonl`. `lanes.json` and the lane output live under
  `.brainstorm/drafts/`.
- SKILL.md: the scripts dir is resolved by one ordered loop (Base
  directory, `$OPENCODE_CONFIG_DIR/skills`, `.opencode/skills`,
  `~/.config/opencode/skills`, `.agents`, `~/.agents`, `.claude`,
  `~/.claude`, `.zcode`) that exits with a clear message on a miss.
- SKILL.md: per-version tool-name map (v2 has `subagent`, `shell`,
  `question`, no `task`/`todowrite`). A raw `!` line is skipped when a
  context block is present, else `sh <Base directory>/scripts/context.sh`
  runs. R9 is one sentence again.
- architectural.md: on OpenCode the main session writes the spec
  pre-draft (lane agents are `edit: deny`), TaskStop is skipped, and the
  hand-off passes the spec path to `writing-plans`.
- visual-companion.md: OpenCode note (v2: `--foreground` plus
  `background: true`).
- researcher agent: falls back to web fetch when web search has no
  provider, and never waits on an interactive prompt.
```

- [ ] **Step 10: Run the check to verify it passes**

Run: `sh /tmp/t32-doc-check.sh`
Expected: PASS. Single output line `T32 doc check: OK`, exit status 0.

- [ ] **Step 11: Run the skill frontmatter tests**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_all_skills.py'`
Expected: PASS. Output ends with `OK` (SKILL.md `name` is still `brainstorming`, description unchanged).

- [ ] **Step 12: Commit**

```bash
cd ..
git add glm-skills/brainstorming-glm/SKILL.md glm-skills/brainstorming-glm/architectural.md glm-skills/brainstorming-glm/visual-companion.md glm-skills/brainstorming-glm/opencode/agents/researcher.md glm-skills/brainstorming-glm/CHANGELOG.md
git commit -m "fix(brainstorming): one OpenCode lane rule, background run, result reader, per-version tool map"
```

---

### T33: install-opencode.sh clash and stale-install warnings [P]

**Depends:** T05

**Interfaces:**
- Consumes: `def config_snippet(major: int, deny: list) -> str`; `variants`; `reasoningEffort`; `glm-5.3`; `glm-5.3-flash`; `zai-coding-plan`; `web-search-prime`; `def render_agent(text: str, major: int) -> str`; `execute: deny`; `websearch`; `hidden`

**Files:**
- Modify: `glm-skills/install-opencode.sh:54-55`
- Modify: `glm-skills/_shared/tests/test_oc_install.py`

All commands run from `glm-skills/` (`cd glm-skills`). The installer only warns. It never deletes anything. Every test runs the real `install-opencode.sh` with `--major` and `--home` pointing at a temp dir, so `opencode` is never started.

- [ ] **Step 1: Write the failing test for the per-major hints**

In `glm-skills/_shared/tests/test_oc_install.py`, add `import subprocess` to the import block, after `import shutil`:

```python fragment
import shutil
import subprocess
import sys
```

Then add this module constant and test class just above the final `if __name__ == "__main__":` block:

```python
INSTALLER = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "install-opencode.sh"))


class InstallerWarningTests(unittest.TestCase):
    """install-opencode.sh against a temp home: hints, clashes, stale installs."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-installer-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.claude_skills = os.path.join(self.home, ".claude", "skills")
        self.config_skills = os.path.join(self.home, ".config", "opencode", "skills")

    def run_installer(self, major):
        env = dict(os.environ, HOME=self.home, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.run(
            ["sh", INSTALLER, "--major", str(major), "--home", self.home],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, env=env, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return proc.stdout

    def make_skill_dir(self, parent, folder):
        path = os.path.join(parent, folder)
        os.makedirs(path)
        with open(os.path.join(path, "SKILL.md"), "w") as fh:
            fh.write("---\nname: %s\ndescription: old copy\n---\nbody\n" % folder)
        return path

    def test_v2_drops_disable_hint_and_prints_websearch_note(self):
        out = self.run_installer(2)
        self.assertNotIn("OPENCODE_DISABLE_CLAUDE_CODE_SKILLS", out)
        self.assertIn("web-search-prime", out)
        self.assertIn("websearch", out)

    def test_v1_keeps_disable_hint(self):
        out = self.run_installer(1)
        self.assertIn("OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1", out)

    def test_clean_home_prints_no_warnings(self):
        out = self.run_installer(2)
        self.assertNotIn("WARN:", out)
        self.assertNotIn("rm -rf", out)
```

- [ ] **Step 2: Run the hint tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_install.py' -k InstallerWarningTests`
Expected: FAIL: `test_v2_drops_disable_hint_and_prints_websearch_note` fails with `AssertionError: 'OPENCODE_DISABLE_CLAUDE_CODE_SKILLS' unexpectedly found in ...`. The other two tests pass.

- [ ] **Step 3: Print the disable hint on v1 only**

The websearch provider note and the `web-search-prime` MCP option already come from the `snippet` line above it (T05's `config_snippet` prints them for both majors), so the installer adds no websearch text of its own.

In `glm-skills/install-opencode.sh`, replace the last line (`echo "# Also export OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 so OpenCode skips the Claude-tuned originals in ~/.claude/skills"`) with:

```bash
if [ "$MAJOR" = "1" ]; then
    echo "# Also export OPENCODE_DISABLE_CLAUDE_CODE_SKILLS=1 so OpenCode skips the Claude-tuned originals in ~/.claude/skills"
fi
```

- [ ] **Step 4: Run the hint tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_install.py' -k InstallerWarningTests`
Expected: PASS (`Ran 3 tests`, `OK`)

- [ ] **Step 5: Write the failing test for clash warnings**

Add this method to `InstallerWarningTests`:

```python fragment
    def test_lists_clashes_with_claude_skills_without_deleting(self):
        original = self.make_skill_dir(self.claude_skills, "doc-generator")
        suffixed = self.make_skill_dir(self.claude_skills, "requirements-code-audit-glm")
        out = self.run_installer(2)
        self.assertIn("WARN: clash: %s" % original, out)
        self.assertIn("WARN: clash: %s" % suffixed, out)
        self.assertIn("config-dir copy wins", out)
        self.assertNotIn("rm -rf", out)
        self.assertTrue(os.path.isfile(os.path.join(original, "SKILL.md")))
        self.assertTrue(os.path.isfile(os.path.join(suffixed, "SKILL.md")))
```

- [ ] **Step 6: Run the clash test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_install.py' -k test_lists_clashes_with_claude_skills_without_deleting`
Expected: FAIL with `AssertionError: 'WARN: clash: .../home/.claude/skills/doc-generator' not found in ...`

- [ ] **Step 7: Warn about clashes with `~/.claude/skills`**

In `glm-skills/install-opencode.sh`, append this block after the `if [ "$MAJOR" = "1" ] ... fi` block from Step 3:

```bash
CLAUDE_SKILLS="$HOME_DIR/.claude/skills"
CONFIG_SKILLS="$HOME_DIR/.config/opencode/skills"

for folder in $SKILLS dev-team-glm; do
    name="${folder%-glm}"
    for path in "$CLAUDE_SKILLS/$name" "$CLAUDE_SKILLS/$folder"; do
        if [ -e "$path" ] || [ -L "$path" ]; then
            echo "WARN: clash: $path carries the same skill name as the installed $name; OpenCode scans ~/.claude/skills too, and $CONFIG_SKILLS/$name is used (the config-dir copy wins). Leave it in place if Claude Code uses it."
        fi
    done
done
```

- [ ] **Step 8: Run the clash test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_install.py' -k test_lists_clashes_with_claude_skills_without_deleting`
Expected: PASS (`Ran 1 test`, `OK`)

- [ ] **Step 9: Write the failing test for stale `*-glm` installs**

Add this method to `InstallerWarningTests`:

```python fragment
    def test_lists_stale_glm_installs_and_prints_removal_command(self):
        writing = self.make_skill_dir(self.config_skills, "writing-plans-glm")
        brainstorm = self.make_skill_dir(self.config_skills, "brainstorming-glm")
        out = self.run_installer(2)
        self.assertIn("WARN: stale: %s" % brainstorm, out)
        self.assertIn("WARN: stale: %s" % writing, out)
        self.assertIn('To remove the stale installs, run: rm -rf "%s" "%s"' % (brainstorm, writing), out)
        self.assertTrue(os.path.isfile(os.path.join(brainstorm, "SKILL.md")))
        self.assertTrue(os.path.isfile(os.path.join(writing, "SKILL.md")))
        self.assertTrue(os.path.isfile(os.path.join(self.config_skills, "writing-plans", "SKILL.md")))
```

- [ ] **Step 10: Run the stale test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_install.py' -k test_lists_stale_glm_installs_and_prints_removal_command`
Expected: FAIL with `AssertionError: 'WARN: stale: .../home/.config/opencode/skills/brainstorming-glm' not found in ...`

- [ ] **Step 11: Warn about stale `*-glm` folders and print one removal command**

In `glm-skills/install-opencode.sh`, append this block after the clash loop from Step 7 (it must stay the last block of the file):

```bash
STALE=""
for path in "$CONFIG_SKILLS"/*-glm; do
    if [ -e "$path" ] || [ -L "$path" ]; then
        base="${path##*/}"
        echo "WARN: stale: $path is an old *-glm install; OpenCode loads it next to $CONFIG_SKILLS/${base%-glm}"
        STALE="$STALE \"$path\""
    fi
done
if [ -n "$STALE" ]; then
    echo "To remove the stale installs, run: rm -rf$STALE"
fi
```

Nothing is deleted. The line only prints the command for the user to run.

- [ ] **Step 12: Run the whole installer test class to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_install.py' -k InstallerWarningTests`
Expected: PASS (`Ran 5 tests`, `OK`)

- [ ] **Step 13: Run the full test file and the full suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_install.py' && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: the first run ends in `OK`. The full suite has no failures in `test_oc_install.py`, and no test outside that file changes status compared with the run before this task.

- [ ] **Step 14: Commit**

Run from the git root (`cd ..` from `glm-skills/`):

```bash
git add glm-skills/install-opencode.sh glm-skills/_shared/tests/test_oc_install.py
git commit -m "fix(shared): install-opencode.sh warns about skill clashes and stale -glm installs, drops the v2 disable hint, adds the websearch note"
```

---

### T34: doc-generator OpenCode agent names and command [P]

**Depends:** —

**Files:**
- Modify: `glm-skills/doc-generator-glm/SKILL.md`
- Modify: `glm-skills/doc-generator-glm/opencode/commands/docs.md`
- Modify: `glm-skills/_shared/tests/test_all_skills.py`

- [ ] **Step 1: Write test to reject unknown OpenCode agent names in doc-generator SKILL.md**

```python
def test_doc_generator_no_unknown_agents(self):
    """doc-generator SKILL.md must not reference 'general-purpose' or 'Explore' agents;
    only 'doc-writer', 'doc-reviewer', and 'general' are valid on OpenCode v2."""
    skill_md = os.path.join(GLM_ROOT, "doc-generator-glm", "SKILL.md")
    with open(skill_md, encoding="utf-8") as fh:
        content = fh.read()
    
    for line_num, line in enumerate(content.split("\n"), 1):
        # Skip code fences and commented examples
        if line.strip().startswith("```") or line.strip().startswith("#"):
            continue
        self.assertNotIn("general-purpose", line,
                        "SKILL.md:%d contains deprecated agent name 'general-purpose'" % line_num)
        if "Explore" in line and "agent" in line.lower():
            self.fail("SKILL.md:%d references unknown agent 'Explore'" % line_num)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/yamazaki-ethan/Documents/Projects/skillz/glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest _shared.tests.test_all_skills.TestSkillMdHygiene.test_doc_generator_no_unknown_agents -v`
Expected: FAIL with "AssertionError: SKILL.md:219 contains deprecated agent name 'general-purpose'"

- [ ] **Step 3: Replace 'general-purpose' with 'doc-writer' in writer task template**

In `glm-skills/doc-generator-glm/SKILL.md` line 219, change from:

```markdown
**≤ 10 writer Tasks**, subagent type `general-purpose`, one per non-cached doc,
```

to:

```markdown
**≤ 10 writer Tasks**, subagent type `doc-writer`, one per non-cached doc,
```

- [ ] **Step 4: Replace 'general-purpose' with 'doc-reviewer' in reviewer task template**

In `glm-skills/doc-generator-glm/SKILL.md` line 364, change from:

```markdown
subagent type `general-purpose`.
```

to:

```markdown
subagent type `doc-reviewer`.
```

- [ ] **Step 5: Replace skill tool command to use skill ID instead of absolute path**

In `glm-skills/doc-generator-glm/opencode/commands/docs.md` line 4, change from:

```markdown
Load skill {{SKILL_DIR}} with $ARGUMENTS
```

to:

```markdown
Load skill doc-generator with $ARGUMENTS
```

- [ ] **Step 6: Replace sed instruction with edit tool in writer template**

In `glm-skills/doc-generator-glm/SKILL.md` line 168, within the WRITE section instructions for writers, change any reference from:

```
using sed to modify the doc
```

to:

```
using the edit tool to modify the doc
```

(Find and replace the exact sed instruction mentioning it in the context of writer edits.)

- [ ] **Step 7: Fix stale sync path reference in OpenCode lane section**

In `glm-skills/doc-generator-glm/SKILL.md` lines 310-312, change from:

```markdown
`sh skills/glm/_shared/sync.sh`
```

to:

```markdown
`sh _shared/sync.sh`
```

(Fix any references showing `skills/glm/` prefix which is stale; the correct relative path from glm-skills root is `_shared/sync.sh`.)

- [ ] **Step 8: Fix GLM model and effort references for consistency**

In `glm-skills/doc-generator-glm/SKILL.md` line 395 and surrounding context, ensure writer lanes use `model: "flash"` (GLM-5.3-Flash) and reviewer lanes use `model: "pro"` (GLM-5.3). Change any line that says:

```
writers use GLM-5.3
```

to:

```
writers use GLM-5.3-Flash
```

- [ ] **Step 9: Run test to verify it passes**

Run: `cd /Users/yamazaki-ethan/Documents/Projects/skillz/glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest _shared.tests.test_all_skills.TestSkillMdHygiene.test_doc_generator_no_unknown_agents -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add glm-skills/doc-generator-glm/SKILL.md glm-skills/doc-generator-glm/opencode/commands/docs.md glm-skills/_shared/tests/test_all_skills.py
git commit -m "fix(doc-generator): OpenCode v2 agent names and skill command"
```

---

### T35: Real-binary contract tests and sandbox discovery check [P]

**Depends:** T04, T05, T09, T33

**Runs after:** T34 (same files)

**Interfaces:**
- Consumes: `def build_run_cmd(lane: dict, major: int, binary: str = "opencode") -> list`; `def config_snippet(major: int, deny: list) -> str`; `def render_agent(text: str, major: int) -> str`
- Produces: `OC_CONTRACT=1`; `render_agent`; `hidden`; `subagent`; `/docs`; ` !`; ` `

**Files:**
- Test: `glm-skills/_shared/tests/test_oc_contract.py`
- Create: `glm-skills/_shared/tests/fake_provider.py`
- Modify: `glm-skills/_shared/oc_harness.py`
- Modify: `glm-skills/brainstorming-glm/scripts/oc_harness.py`
- Modify: `glm-skills/dev-team-glm/scripts/oc_harness.py`
- Modify: `glm-skills/doc-generator-glm/scripts/oc_harness.py`
- Modify: `glm-skills/requirements-code-audit-glm/scripts/oc_harness.py`
- Modify: `glm-skills/systematic-debugging-glm/scripts/oc_harness.py`
- Modify: `glm-skills/writing-plans-glm/scripts/oc_harness.py`
- Modify: `glm-skills/doc-generator-glm/opencode/commands/docs.md`

This task adds a stdlib fake OpenAI-compatible provider and an opt-in real-binary contract module. The module drives `opencode` in a sandboxed `HOME`/`XDG_*` tree, with non-localhost network blocked by macOS `sandbox-exec`. Two probe tests then decide two conditional changes:

- `render_agent` stops emitting `hidden` on v2 only if `test_probe_hidden_agent_dispatch` proves that a hidden agent cannot be dispatched by the `subagent` tool.
- `/docs` gains a `` !`cmd` `` recon line only if `test_probe_command_bang_expansion` proves that v2 expands it.

The fake-provider self-tests always run. Every real-binary test runs only with `OC_CONTRACT=1`. All commands run from `glm-skills/` (`cd glm-skills`).

- [ ] **Step 1: Write the failing fake-provider self-tests**

Create `_shared/tests/test_oc_contract.py` with exactly this content. The imports cover the later steps too.

```python
"""OpenCode real-binary contract tests (opt-in: OC_CONTRACT=1) plus fake-provider self-tests.

The fake-provider self-tests always run. The real-binary classes run only with OC_CONTRACT=1:
they drive `opencode` against fake_provider.py inside a sandboxed HOME/XDG_* tree and block all
non-localhost network with macOS sandbox-exec (skipped without it unless
OC_CONTRACT_NO_SANDBOX=1). v2 is the `opencode` on PATH, v1 comes from OC_V1_BIN.
"""

import json
import os
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.dirname(HERE)
ROOT = os.path.dirname(SHARED)
for _path in (HERE, SHARED):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import oc_harness  # noqa: E402
from fake_provider import FakeProvider, fill_args, message_texts, tool_names  # noqa: E402

SHELL_TOOL = [{
    "type": "function",
    "function": {
        "name": "shell",
        "parameters": {
            "type": "object",
            "properties": {"command": {"type": "string"}, "timeout": {"type": "number"}},
            "required": ["command"],
        },
    },
}]


def _post(url: str, body: dict) -> tuple:
    req = urllib.request.Request(url + "/chat/completions", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read().decode("utf-8")


class FakeProviderTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeProvider()
        self.url = self.fake.start()

    def tearDown(self):
        self.fake.stop()

    def test_default_json_reply_and_log(self):
        status, text = _post(self.url, {"model": "fake-model",
                                        "messages": [{"role": "user", "content": "hi there"}]})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["choices"][0]["message"]["content"], "ok")
        self.assertEqual(message_texts(self.fake.bodies()[0], "user"), ["hi there"])

    def test_stream_tool_call_picks_offered_name(self):
        self.fake.rules = [{"fresh": True, "tool": ["bash", "shell"], "args": {"command": "echo hi"}}]
        status, text = _post(self.url, {
            "model": "fake-model", "stream": True, "tools": SHELL_TOOL,
            "messages": [{"role": "user", "content": [{"type": "text", "text": "run"}]}],
        })
        self.assertEqual(status, 200)
        chunks = [json.loads(line[6:]) for line in text.splitlines() if line.startswith("data: {")]
        call = chunks[0]["choices"][0]["delta"]["tool_calls"][0]["function"]
        self.assertEqual(call["name"], "shell")
        self.assertEqual(json.loads(call["arguments"]), {"command": "echo hi"})
        self.assertEqual(chunks[-1]["choices"][0]["finish_reason"], "tool_calls")
        self.assertTrue(text.rstrip().endswith("data: [DONE]"))
        self.assertEqual(tool_names(self.fake.bodies()[0]), ["shell"])

    def test_fresh_rule_skipped_after_tool_result(self):
        self.fake.rules = [{"fresh": True, "tool": ["shell"], "args": {"command": "x"}}, {"text": "done"}]
        status, text = _post(self.url, {
            "model": "fake-model", "tools": SHELL_TOOL,
            "messages": [
                {"role": "user", "content": "run"},
                {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "c1", "type": "function", "function": {"name": "shell", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "c1", "content": "x"},
            ],
        })
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(text)["choices"][0]["message"]["content"], "done")

    def test_auto_fill_from_schema(self):
        schema = {
            "type": "object",
            "properties": {"subagent_type": {"type": "string"}, "prompt": {"type": "string"},
                           "description": {"type": "string"}, "background": {"type": "boolean"}},
            "required": ["subagent_type", "prompt", "description", "background"],
        }
        args = fill_args(schema, {"agent": "contract-hidden", "prompt": "Reply with sub-done."})
        self.assertEqual(args, {"subagent_type": "contract-hidden", "prompt": "Reply with sub-done.",
                                "description": "contract", "background": False})

    def test_status_rule_returns_error(self):
        self.fake.rules = [{"match": "THROTTLE", "status": 429,
                            "body": {"error": {"code": "1302", "message": "rate limited"}}}]
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            _post(self.url, {"model": "fake-model", "messages": [{"role": "user", "content": "THROTTLE me"}]})
        self.assertEqual(ctx.exception.code, 429)
        self.assertIn("1302", ctx.exception.read().decode("utf-8"))
        ctx.exception.close()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the self-tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_contract.py' -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'fake_provider'"

- [ ] **Step 3: Write the fake provider**

Create `_shared/tests/fake_provider.py` with exactly this content.

```python
"""Stdlib fake OpenAI-compatible chat provider for the OpenCode contract tests.

Serves GET <base>/models and POST <base>/chat/completions (SSE when "stream" is true, JSON
otherwise) and logs every request body. Rules are matched in order against each chat request;
the first match wins. Rule keys:
  match   substring that must occur in the JSON-encoded request body
  unless  substring that must not occur in it
  fresh   true: only when the request carries no role=tool message
  status  HTTP error status to return, with `body` as the JSON error payload
  delay   seconds to wait after the response headers are sent
  text    assistant text to return
  tool    candidate tool names; the first one offered in the request is called
  args    tool-call arguments; when absent they are filled from the tool schema via `fill`
  fill    {property-name substring: value} used to fill tool-call arguments
The default reply is the text "ok".
"""

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

MODEL = "fake-model"
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def tool_names(body: dict) -> list:
    names = []
    for tool in body.get("tools") or []:
        fn = tool.get("function") if isinstance(tool, dict) else None
        if isinstance(fn, dict) and fn.get("name"):
            names.append(fn["name"])
    return names


def message_texts(body: dict, role: str) -> list:
    texts = []
    for msg in body.get("messages") or []:
        if not isinstance(msg, dict) or msg.get("role") != role:
            continue
        content = msg.get("content")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    texts.append(part["text"])
    return texts


def _schema(body: dict, name: str) -> dict:
    for tool in body.get("tools") or []:
        fn = tool.get("function") if isinstance(tool, dict) else None
        if isinstance(fn, dict) and fn.get("name") == name:
            return fn.get("parameters") or {}
    return {}


def fill_args(schema: dict, fill: dict) -> dict:
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    args = {}
    for key, spec in props.items():
        value = None
        for needle, candidate in (fill or {}).items():
            if needle.lower() in key.lower():
                value = candidate
                break
        if value is None and key in required:
            kind = spec.get("type") if isinstance(spec, dict) else None
            if kind == "boolean":
                value = False
            elif kind in ("integer", "number"):
                value = 1
            elif kind == "array":
                value = []
            elif kind == "object":
                value = {}
            else:
                value = "contract"
        if value is not None:
            args[key] = value
    return args


def choose(rules: list, body: dict) -> dict:
    raw = json.dumps(body)
    has_tool_msg = any(isinstance(m, dict) and m.get("role") == "tool" for m in body.get("messages") or [])
    offered = tool_names(body)
    for rule in rules:
        if rule.get("match") and rule["match"] not in raw:
            continue
        if rule.get("unless") and rule["unless"] in raw:
            continue
        if rule.get("fresh") and has_tool_msg:
            continue
        delay = rule.get("delay", 0)
        if rule.get("tool"):
            name = next((n for n in rule["tool"] if n in offered), None)
            if name is None:
                continue
            args = rule.get("args")
            if args is None:
                args = fill_args(_schema(body, name), rule.get("fill") or {})
            return {"tool": name, "args": args, "delay": delay}
        if rule.get("status"):
            return {"status": int(rule["status"]),
                    "body": rule.get("body") or {"error": {"message": "fake error"}}, "delay": delay}
        return {"text": rule.get("text", "ok"), "delay": delay}
    return {"text": "ok", "delay": 0}


def _call(reply: dict, cid: str) -> dict:
    return {"id": cid + "-call", "type": "function",
            "function": {"name": reply["tool"], "arguments": json.dumps(reply["args"])}}


def stream_chunks(reply: dict, cid: str) -> list:
    base = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL}

    def chunk(delta, finish=None, usage=None):
        item = dict(base, choices=[{"index": 0, "delta": delta, "finish_reason": finish}])
        if usage:
            item["usage"] = usage
        return item

    if "tool" in reply:
        call = dict(_call(reply, cid), index=0)
        return [chunk({"role": "assistant", "content": None, "tool_calls": [call]}),
                chunk({}, "tool_calls", USAGE)]
    return [chunk({"role": "assistant", "content": reply["text"]}), chunk({}, "stop", USAGE)]


def completion(reply: dict, cid: str) -> dict:
    message = {"role": "assistant", "content": reply.get("text")}
    finish = "stop"
    if "tool" in reply:
        message["content"] = None
        message["tool_calls"] = [_call(reply, cid)]
        finish = "tool_calls"
    return {"id": cid, "object": "chat.completion", "created": int(time.time()), "model": MODEL,
            "choices": [{"index": 0, "message": message, "finish_reason": finish}], "usage": USAGE}


class _Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _Handler(BaseHTTPRequestHandler):
    server_version = "FakeProvider/1.0"

    def log_message(self, fmt, *args):
        pass

    def _read_body(self) -> bytes:
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            parts = []
            while True:
                size_line = self.rfile.readline().strip().split(b";")[0]
                size = int(size_line or b"0", 16)
                if size == 0:
                    self.rfile.readline()
                    break
                parts.append(self.rfile.read(size))
                self.rfile.readline()
            return b"".join(parts)
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _headers(self, status, content_type, length=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.flush()

    def _json(self, status, payload, delay=0.0):
        data = json.dumps(payload).encode("utf-8")
        self._headers(status, "application/json", len(data))
        if delay:
            time.sleep(delay)
        self.wfile.write(data)
        self.wfile.flush()

    def do_GET(self):
        try:
            if self.path.rstrip("/").endswith("/models"):
                self._json(200, {"object": "list",
                                 "data": [{"id": MODEL, "object": "model", "owned_by": "fake"}]})
            else:
                self._json(404, {"error": {"message": "not found: " + self.path}})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        provider = self.server.provider
        try:
            body = json.loads(self._read_body().decode("utf-8") or "{}")
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}
        cid = provider.record(self.path, body)
        try:
            if not self.path.rstrip("/").endswith("/chat/completions"):
                self._json(404, {"error": {"message": "not found: " + self.path}})
                return
            reply = choose(provider.rules, body)
            delay = float(reply.get("delay") or 0)
            if "status" in reply:
                self._json(reply["status"], reply["body"], delay)
                return
            if body.get("stream"):
                self._headers(200, "text/event-stream")
                if delay:
                    time.sleep(delay)
                for item in stream_chunks(reply, cid):
                    self.wfile.write(("data: %s\n\n" % json.dumps(item)).encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            else:
                self._json(200, completion(reply, cid), delay)
        except (BrokenPipeError, ConnectionResetError):
            pass


class FakeProvider:
    def __init__(self, rules: list = None, host: str = "127.0.0.1", port: int = 0):
        self.rules = list(rules or [])
        self.requests = []
        self._lock = threading.Lock()
        self._counter = 0
        self._server = _Server((host, port), _Handler)
        self._server.provider = self
        self._thread = None

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def url(self) -> str:
        return "http://127.0.0.1:%d/v1" % self.port

    def start(self) -> str:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.url

    def stop(self) -> None:
        if self._thread is not None:
            self._server.shutdown()
            self._thread.join(5)
            self._thread = None
        self._server.server_close()

    def record(self, path: str, body: dict) -> str:
        with self._lock:
            self._counter += 1
            self.requests.append({"path": path, "body": body})
            return "chatcmpl-fake-%d" % self._counter

    def bodies(self) -> list:
        with self._lock:
            return [r["body"] for r in self.requests if r["path"].rstrip("/").endswith("/chat/completions")]


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(prog="fake_provider.py", description="fake OpenAI-compatible provider")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--rules", default="", help="JSON file holding a list of rules")
    a = parser.parse_args(argv)
    rules = []
    if a.rules:
        with open(a.rules) as fh:
            rules = json.load(fh)
    fake = FakeProvider(rules, port=a.port)
    print("FAKE_PROVIDER %s" % fake.url)
    print("NEXT: set an openai-compatible provider baseURL to %s; Ctrl-C stops the server" % fake.url)
    sys.stdout.flush()
    try:
        fake._server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        fake._server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the self-tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_contract.py' -v`
Expected: PASS, with `Ran 5 tests` and a final line `OK`

- [ ] **Step 5: Append the opt-in real-binary contract classes**

Append this block to `_shared/tests/test_oc_contract.py`. Put it after `class FakeProviderTest` and before the `if __name__ == "__main__":` block.

```python
ENABLED = os.environ.get("OC_CONTRACT") == "1"
NO_SANDBOX = os.environ.get("OC_CONTRACT_NO_SANDBOX") == "1"
SANDBOX_EXEC = shutil.which("sandbox-exec") or ""
SKIP_MSG = "set OC_CONTRACT=1 to run the real-binary OpenCode contract tests"
SANDBOX_PROFILE = (
    "(version 1)\n"
    "(allow default)\n"
    '(deny network-outbound (remote ip "*:*"))\n'
    '(allow network-outbound (remote ip "localhost:*"))\n'
)
V2_TOOLS = {"edit", "glob", "grep", "question", "read", "shell", "skill", "subagent",
            "webfetch", "websearch", "write", "execute"}
V1_TOOLS = {"bash", "edit", "glob", "grep", "read", "skill", "task", "todowrite", "webfetch", "write"}
V1_ONLY_TOOLS = {"bash", "task", "todowrite", "apply_patch"}
V2_EVENT_TYPES = {"step_start", "tool_use", "step_finish", "text", "error"}
V2_HOOK_KEYS = {"tool", "sessionID", "agent", "messageID", "id", "input"}
SKILLS = {"brainstorming", "dev-team", "doc-generator", "requirements-code-audit",
          "systematic-debugging", "writing-plans"}
AGENT_PATHS = ("/agent", "/api/agent")
COMMAND_PATHS = ("/command", "/api/command")
SKILL_PATHS = ("/skill", "/api/skill", "/experimental/skill")
HIDDEN_MARKER = "HIDDEN-AGENT-MARKER-7F3A"
PROBE_AGENT_SRC = (
    "---\n"
    "description: contract probe agent\n"
    "model: flash\n"
    "effort: high\n"
    "access: write\n"
    "bash: true\n"
    "web: true\n"
    "---\n"
    "You are a contract probe. Call the tools you are offered, then answer briefly.\n"
)
HIDDEN_AGENT_SRC = (
    "---\n"
    "description: contract hidden subagent\n"
    "model: flash\n"
    "effort: high\n"
    "access: read\n"
    "bash: false\n"
    "web: false\n"
    "---\n"
    "%s Reply with sub-done.\n" % HIDDEN_MARKER
)
BANG_COMMAND = "---\ndescription: contract bang probe\n---\nMarker: !`echo BANG-$((40+2))`\n"
PLUGIN_JS = r"""import { appendFileSync } from "node:fs";

const LOG = process.env.CONTRACT_HOOK_LOG || "";
const DENY = (process.env.CONTRACT_DENY || "").split(",").filter(Boolean);

function record(entry) {
  if (LOG) appendFileSync(LOG, JSON.stringify(entry) + "\n");
  if (DENY.includes(entry.tool)) throw new Error("contract-deny: " + entry.tool);
}

export const ContractProbe = async () => ({
  "tool.execute.before": async (input, output) => {
    record({ hook: "tool.execute.before", tool: input && input.tool,
             args: (output && output.args) || {}, keys: Object.keys(input || {}).sort() });
  },
  "execute.before": async (event) => {
    record({ hook: "execute.before", tool: event && event.tool,
             args: (event && event.input) || {}, keys: Object.keys(event || {}).sort() });
  },
});

export default ContractProbe;
"""


def _xdg(home: str) -> dict:
    return {
        "HOME": home,
        "XDG_CONFIG_HOME": os.path.join(home, ".config"),
        "XDG_DATA_HOME": os.path.join(home, ".local", "share"),
        "XDG_CACHE_HOME": os.path.join(home, ".cache"),
        "XDG_STATE_HOME": os.path.join(home, ".local", "state"),
    }


def _binary_for(major: int) -> str:
    candidates = []
    if major == 1 and os.environ.get("OC_V1_BIN"):
        candidates.append(os.environ["OC_V1_BIN"])
    if shutil.which("opencode"):
        candidates.append(shutil.which("opencode"))
    with tempfile.TemporaryDirectory(prefix="oc-detect-") as scratch:
        with mock.patch.dict(os.environ, _xdg(scratch)):
            for cand in candidates:
                path = os.path.abspath(shutil.which(cand) or cand)
                if os.path.isfile(path) and oc_harness.detect(path) == major:
                    return path
    return ""


def sandbox_env(home: str, bindir: str, tmp: str) -> dict:
    env = _xdg(home)
    env.update({
        "PATH": bindir + os.pathsep + os.environ.get("PATH", "/usr/bin:/bin"),
        "TMPDIR": tmp,
        "LANG": "en_US.UTF-8",
        "TERM": "dumb",
    })
    return env


def write_wrapper(bindir: str, real_bin: str, tmp: str) -> str:
    path = os.path.join(bindir, "opencode")
    if SANDBOX_EXEC:
        profile = os.path.join(tmp, "sandbox.sb")
        with open(profile, "w") as fh:
            fh.write(SANDBOX_PROFILE)
        line = 'exec %s -f %s %s "$@"\n' % (shlex.quote(SANDBOX_EXEC), shlex.quote(profile), shlex.quote(real_bin))
    else:
        line = 'exec %s "$@"\n' % shlex.quote(real_bin)
    with open(path, "w") as fh:
        fh.write("#!/bin/sh\n" + line)
    os.chmod(path, 0o755)
    return path


def fake_config(url: str, major: int) -> dict:
    snippet = json.loads(oc_harness.config_snippet(major, ["contract-denied-*"]))
    return {
        "$schema": snippet["$schema"],
        "enabled_providers": ["fake"],
        "permission": snippet["permission"],
        "provider": {
            "fake": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "Fake",
                "options": {"baseURL": url, "apiKey": "fake-key"},
                "models": {
                    "fake-model": {
                        "name": "fake-model",
                        "variants": {"low": {"reasoningEffort": "low"}, "high": {"reasoningEffort": "high"}},
                    }
                },
            }
        },
    }


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _names(data) -> set:
    if isinstance(data, dict):
        for key in ("data", "items", "agents", "commands", "skills"):
            if isinstance(data.get(key), list):
                return _names(data[key])
        return set(str(k) for k in data)
    names = set()
    for item in data or []:
        if isinstance(item, dict):
            name = item.get("name") or item.get("id")
            if name:
                names.add(str(name))
        elif isinstance(item, str):
            names.add(item)
    return names


class ContractCases:
    MAJOR = 0
    SHELL = ""
    WRITE_PATH_KEY = ""
    TOOLS = set()

    @classmethod
    def setUpClass(cls):
        if not SANDBOX_EXEC and not NO_SANDBOX:
            raise unittest.SkipTest("no sandbox-exec network sandbox; set OC_CONTRACT_NO_SANDBOX=1 to run unsandboxed")
        cls.real_bin = _binary_for(cls.MAJOR)
        if not cls.real_bin:
            raise unittest.SkipTest("no opencode v%d binary (opencode on PATH or OC_V1_BIN)" % cls.MAJOR)

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-contract-")
        self.home = os.path.join(self.tmp, "home")
        self.work = os.path.join(self.tmp, "work")
        self.bindir = os.path.join(self.tmp, "bin")
        self.config_dir = os.path.join(self.home, ".config", "opencode")
        for path in (self.work, self.bindir, os.path.join(self.config_dir, "agents"),
                     os.path.join(self.config_dir, "commands"), os.path.join(self.config_dir, "plugins")):
            os.makedirs(path)
        self.hook_log = os.path.join(self.tmp, "hook.jsonl")
        self.fake = FakeProvider()
        self.fake.start()
        self._write(os.path.join(self.config_dir, "opencode.json"),
                    json.dumps(fake_config(self.fake.url, self.MAJOR), indent=2))
        self._write(os.path.join(self.config_dir, "plugins", "contract-probe.js"), PLUGIN_JS)
        self._write_agent("contract-probe", self._rendered(PROBE_AGENT_SRC))
        self._write_agent("contract-hidden", self._rendered(HIDDEN_AGENT_SRC))
        self.wrapper = write_wrapper(self.bindir, self.real_bin, self.tmp)
        self.env = sandbox_env(self.home, self.bindir, self.tmp)
        self.env["CONTRACT_HOOK_LOG"] = self.hook_log

    def tearDown(self):
        self.fake.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, path, text):
        with open(path, "w") as fh:
            fh.write(text)

    def _rendered(self, src):
        text = oc_harness.render_agent(src, self.MAJOR)
        return re.sub(r"(?m)^model: .*$", "model: fake/fake-model", text, count=1)

    def _write_agent(self, name, text):
        self._write(os.path.join(self.config_dir, "agents", name + ".md"), text)

    def _lane(self, brief, effort="", agent="contract-probe"):
        return {"id": "contract", "agent": agent, "model": "fake/fake-model", "effort": effort,
                "dir": self.work, "brief": brief}

    def _exec(self, cmd, brief, extra_env=None, timeout=300):
        env = dict(self.env)
        env["PWD"] = self.work
        env.update(extra_env or {})
        stdin_text = "" if brief in cmd else brief
        proc = subprocess.run(cmd, input=stdin_text, capture_output=True, text=True, timeout=timeout,
                              cwd=self.work, env=env)
        events = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return proc, events

    def _run(self, brief, effort="", agent="contract-probe", extra_env=None, timeout=300):
        cmd = oc_harness.build_run_cmd(self._lane(brief, effort, agent), self.MAJOR, self.wrapper)
        return self._exec(cmd, brief, extra_env, timeout)

    def _tool_bodies(self):
        return [b for b in self.fake.bodies() if tool_names(b)]

    def _hooks(self):
        if not os.path.isfile(self.hook_log):
            return []
        with open(self.hook_log) as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def _shell_rule(self, command):
        return {"fresh": True, "tool": [self.SHELL],
                "fill": {"command": command, "workdir": self.work, "timeout": 60000,
                         "background": False, "description": "contract marker"}}

    def _tail(self, proc):
        return "stdout: %s\nstderr: %s" % (proc.stdout[-1500:], proc.stderr[-1500:])

    def test_model_sees_expected_tools(self):
        proc, _ = self._run("List your tools, then answer ok.")
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        bodies = self._tool_bodies()
        self.assertTrue(bodies, "no request carried tools")
        seen = set(tool_names(bodies[0]))
        self.assertTrue(self.TOOLS <= seen, "missing %s; seen %s" % (sorted(self.TOOLS - seen), sorted(seen)))
        if self.MAJOR == 2:
            self.assertFalse(V1_ONLY_TOOLS & seen, sorted(seen))

    def test_hook_sees_shell_tool_and_args(self):
        target = os.path.join(self.work, "shell-marker")
        command = "touch " + shlex.quote(target)
        self.fake.rules = [self._shell_rule(command), {"text": "done"}]
        proc, events = self._run("Run the marker command.")
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        self.assertTrue(os.path.exists(target), self._tail(proc))
        hooks = [h for h in self._hooks() if h.get("tool") == self.SHELL]
        self.assertTrue(hooks, "plugin hook never saw %s: %s" % (self.SHELL, self._hooks()))
        self.assertEqual(hooks[0]["args"].get("command"), command)
        if self.MAJOR == 2:
            v2_hooks = [h for h in hooks if h["hook"] == "execute.before"]
            self.assertTrue(v2_hooks, hooks)
            self.assertTrue(V2_HOOK_KEYS <= set(v2_hooks[0]["keys"]), v2_hooks[0]["keys"])
        self.assertIn("tool_use", [e.get("type") for e in events])

    def test_write_tool_args(self):
        target = os.path.join(self.work, "written.txt")
        self.fake.rules = [{"fresh": True, "tool": ["write"],
                            "args": {self.WRITE_PATH_KEY: target, "content": "contract-write\n"}},
                           {"text": "done"}]
        proc, _ = self._run("Write the file.")
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        with open(target) as fh:
            self.assertEqual(fh.read(), "contract-write\n")
        hooks = [h for h in self._hooks() if h.get("tool") == "write"]
        self.assertTrue(hooks, self._hooks())
        self.assertIn(self.WRITE_PATH_KEY, hooks[0]["args"])

    def test_plugin_deny_blocks_tool(self):
        target = os.path.join(self.work, "denied-marker")
        self.fake.rules = [self._shell_rule("touch " + shlex.quote(target)), {"text": "done"}]
        proc, _ = self._run("Run the marker command.", extra_env={"CONTRACT_DENY": self.SHELL})
        self.assertFalse(os.path.exists(target), "deny did not block the tool")
        self.assertTrue(any(h.get("tool") == self.SHELL for h in self._hooks()), self._hooks())
        if self.MAJOR == 2:
            self.assertEqual(proc.returncode, 0, self._tail(proc))

    def test_reasoning_effort_reaches_request(self):
        # v2: the lane's #low suffix must beat the agent's `variant: high`; v1: frontmatter reasoningEffort.
        expected = "low" if self.MAJOR == 2 else "high"
        proc, _ = self._run("Answer ok.", effort=expected)
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        efforts = [b.get("reasoning_effort") for b in self._tool_bodies()]
        self.assertIn(expected, efforts)

    def test_json_event_schema(self):
        self.fake.rules = [self._shell_rule("echo schema"), {"text": "done"}]
        proc, events = self._run("Run the schema command.")
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        types = [e.get("type") for e in events]
        self.assertTrue(types and all(types), types)
        self.assertTrue({"tool_use", "text"} <= set(types), types)
        if self.MAJOR == 2:
            self.assertTrue(set(types) <= V2_EVENT_TYPES, types)
            self.assertIn("step_start", types)
            self.assertEqual(types[-1], "text", types)

    def test_brief_arrives_verbatim_via_stdin(self):
        brief = 'Contract brief "quoted" $HOME `tick`\n  indented\tline\nünïcode ✓ end'
        cmd = oc_harness.build_run_cmd(self._lane(brief), self.MAJOR, self.wrapper)
        self.assertNotIn(brief, cmd)
        proc, _ = self._run(brief)
        self.assertEqual(proc.returncode, 0, self._tail(proc))
        texts = [t for b in self._tool_bodies() for t in message_texts(b, "user")]
        self.assertIn(brief, texts)

    def test_rate_limit_error_and_governor(self):
        # The slow lane outlives the throttled lane's built-in retries (v2 ~86 s, v1 ~77 s), so
        # the third lane starts only after the governor has halved the width from 2 to 1.
        self.fake.rules = [
            {"match": "THROTTLE-LANE", "status": 429,
             "body": {"error": {"code": "1302", "message": "rate limit reached for requests"}}},
            {"match": "SLOW-LANE", "delay": 130, "text": "slow-done"},
            {"text": "ok"},
        ]
        lanes = [{"id": "throttle", "brief": "THROTTLE-LANE answer ok"},
                 {"id": "slow", "brief": "SLOW-LANE answer ok"},
                 {"id": "after", "brief": "AFTER-LANE answer ok"}]
        for lane in lanes:
            lane.update({"agent": "contract-probe", "model": "fake/fake-model", "dir": self.work, "timeout": 600})
        out_dir = os.path.join(self.tmp, "lanes")
        with mock.patch.dict(os.environ, self.env, clear=True):
            rows = oc_harness.run_lanes(lanes, out_dir, width=2, stall=300, binary=self.wrapper, major=self.MAJOR)
        throttled, slow, after = rows
        with open(throttled["out"]) as fh:
            out = fh.read()
        self.assertGreaterEqual(throttled["throttles"], 1, out[-1500:])
        if self.MAJOR == 2:
            self.assertEqual(throttled["status"], "FAIL")
            self.assertIn("provider.rate-limit", out)
        else:
            self.assertIn("APIError", out)
            self.assertIn("1302", out)
        self.assertEqual(slow["status"], "OK", slow["error"])
        self.assertEqual(after["width"], 1)

    def _get_first(self, base, paths):
        tried = []
        for path in paths:
            try:
                with urllib.request.urlopen(base + path, timeout=15) as resp:
                    return json.loads(resp.read().decode("utf-8", "replace"))
            except (urllib.error.HTTPError, ValueError) as exc:
                tried.append("%s: %s" % (path, exc))
        self.fail("no endpoint answered: " + "; ".join(tried))

    def _wait_port(self, port, proc, log_path, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                with open(log_path) as fh:
                    self.fail("opencode serve exited %s: %s" % (proc.returncode, fh.read()[-2000:]))
            try:
                socket.create_connection(("127.0.0.1", port), 1).close()
                return
            except OSError:
                time.sleep(0.5)
        self.fail("opencode serve did not listen on %d within %ds" % (port, timeout))

    def _logs(self, serve_log):
        chunks = []
        log_dir = os.path.join(self.env["XDG_DATA_HOME"], "opencode", "log")
        paths = [serve_log]
        if os.path.isdir(log_dir):
            paths += [os.path.join(log_dir, f) for f in sorted(os.listdir(log_dir))]
        for path in paths:
            if os.path.isfile(path):
                with open(path, errors="replace") as fh:
                    chunks.append(fh.read())
        return "\n".join(chunks)

    def test_install_discovery(self):
        install = subprocess.run(["sh", os.path.join(ROOT, "install-opencode.sh"), "--home", self.home],
                                 cwd=ROOT, env=self.env, capture_output=True, text=True, timeout=300)
        self.assertEqual(install.returncode, 0, install.stdout[-1500:] + install.stderr[-1500:])
        port = _free_port()
        serve_log = os.path.join(self.tmp, "serve.log")
        with open(serve_log, "w") as log:
            server = subprocess.Popen([self.wrapper, "serve", "--port", str(port), "--hostname", "127.0.0.1"],
                                      cwd=self.work, env=dict(self.env, PWD=self.work), stdout=log,
                                      stderr=subprocess.STDOUT, start_new_session=True)
        try:
            self._wait_port(port, server, serve_log)
            base = "http://127.0.0.1:%d" % port
            agents = _names(self._get_first(base, AGENT_PATHS))
            commands = _names(self._get_first(base, COMMAND_PATHS))
            skills = _names(self._get_first(base, SKILL_PATHS))
        finally:
            try:
                os.killpg(server.pid, signal.SIGTERM)
                server.wait(10)
            except (OSError, subprocess.TimeoutExpired):
                os.killpg(server.pid, signal.SIGKILL)
                server.wait(10)
        agents_dir = os.path.join(self.config_dir, "agents")
        installed_agents = {f[:-3] for f in os.listdir(agents_dir)
                            if f.endswith(".md") and not f.startswith("contract-")}
        self.assertGreaterEqual(len(installed_agents), 13, sorted(installed_agents))
        self.assertFalse(installed_agents - agents, "agents not discovered: %s" % sorted(installed_agents - agents))
        commands_dir = os.path.join(self.config_dir, "commands")
        installed_commands = {f[:-3] for f in os.listdir(commands_dir) if f.endswith(".md")}
        self.assertEqual(len(installed_commands), 6, sorted(installed_commands))
        self.assertFalse(installed_commands - commands,
                         "commands not discovered: %s" % sorted(installed_commands - commands))
        self.assertTrue(SKILLS <= skills, "skills not discovered: %s" % sorted(SKILLS - skills))
        self.assertFalse([n for n in skills if n.endswith("-glm")], sorted(skills))
        self.assertTrue(os.path.isfile(os.path.join(self.config_dir, "plugins", "devteam-guard.js")))
        lines = self._logs(serve_log).splitlines()
        load_errors = [l for l in lines if re.search(r"(?i)(failed to load|load error|parse error|invalid config)", l)]
        clashes = [l for l in lines if re.search(r"(?i)(clash|duplicate|conflict)", l)]
        self.assertFalse(load_errors, "\n".join(load_errors[:20]))
        self.assertFalse(clashes, "\n".join(clashes[:20]))


@unittest.skipUnless(ENABLED, SKIP_MSG)
class V2ContractTest(ContractCases, unittest.TestCase):
    MAJOR = 2
    SHELL = "shell"
    WRITE_PATH_KEY = "path"
    TOOLS = V2_TOOLS

    def _dispatch(self, name):
        self.fake.rules = [
            {"match": HIDDEN_MARKER, "text": "sub-done"},
            {"fresh": True, "tool": ["subagent"],
             "fill": {"agent": name, "prompt": "Reply with sub-done.", "message": "Reply with sub-done.",
                      "description": "contract dispatch"}},
            {"text": "done"},
        ]
        proc, _ = self._run("Dispatch the contract subagent.")
        hits = [b for b in self.fake.bodies() if any(HIDDEN_MARKER in t for t in message_texts(b, "system"))]
        self.assertTrue(hits, "subagent %s was never dispatched; %s" % (name, self._tail(proc)))

    def test_missing_variant_reports_no_route(self):
        proc, _ = self._run("Answer ok.", effort="max")
        combined = proc.stdout + proc.stderr
        self.assertTrue("provider.no-route" in combined or "Variant unavailable" in combined, combined[-2000:])

    def test_rendered_agent_dispatchable_by_subagent(self):
        self._dispatch("contract-hidden")

    def test_probe_hidden_agent_dispatch(self):
        text = self._rendered(HIDDEN_AGENT_SRC)
        if "\nhidden: true\n" not in text:
            text = text.replace("\nmode: ", "\nhidden: true\nmode: ", 1)
        self._write_agent("contract-hidden-forced", text)
        self._dispatch("contract-hidden-forced")

    def test_probe_command_bang_expansion(self):
        self._write(os.path.join(self.config_dir, "commands", "contract-bang.md"), BANG_COMMAND)
        proc, _ = self._run("/contract-bang")
        texts = "\n".join(t for b in self.fake.bodies() for t in message_texts(b, "user"))
        self.assertIn("BANG-42", texts, "not expanded; user text: %s; %s" % (texts[-800:], self._tail(proc)))


@unittest.skipUnless(ENABLED, SKIP_MSG)
class V1ContractTest(ContractCases, unittest.TestCase):
    MAJOR = 1
    SHELL = "bash"
    WRITE_PATH_KEY = "filePath"
    TOOLS = V1_TOOLS

    def test_effort_suffix_rejected(self):
        brief = "Answer ok."
        cmd = oc_harness.build_run_cmd(self._lane(brief), 1, self.wrapper)
        i = cmd.index("-m") if "-m" in cmd else cmd.index("--model")
        cmd[i + 1] = cmd[i + 1] + "#high"
        proc, _ = self._exec(cmd, brief)
        self.assertNotEqual(proc.returncode, 0, self._tail(proc))


@unittest.skipUnless(ENABLED, SKIP_MSG)
@unittest.skipUnless(SANDBOX_EXEC, "no sandbox-exec on this host")
class SandboxProfileTest(unittest.TestCase):
    def test_blocks_remote_allows_localhost(self):
        tmp = tempfile.mkdtemp(prefix="oc-sandbox-")
        fake = FakeProvider()
        fake.start()
        try:
            profile = os.path.join(tmp, "sandbox.sb")
            with open(profile, "w") as fh:
                fh.write(SANDBOX_PROFILE)
            probe = "import socket, sys; socket.create_connection((sys.argv[1], int(sys.argv[2])), 5).close()"
            remote = subprocess.run([SANDBOX_EXEC, "-f", profile, sys.executable, "-c", probe, "1.1.1.1", "443"],
                                    capture_output=True, text=True, timeout=30)
            local = subprocess.run([SANDBOX_EXEC, "-f", profile, sys.executable, "-c", probe, "127.0.0.1",
                                    str(fake.port)], capture_output=True, text=True, timeout=30)
        finally:
            fake.stop()
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertNotEqual(remote.returncode, 0, "sandbox let a remote connection through")
        self.assertEqual(local.returncode, 0, local.stderr)
```

- [ ] **Step 6: Run the module without the opt-in to verify the real-binary classes skip**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_contract.py'`
Expected: PASS, with `Ran 29 tests` and a final line `OK (skipped=24)`

- [ ] **Step 7: Run the contract module against the real v2 and v1 binaries**

Put the v2.0.18 `opencode` first on `PATH`. Then export `OC_V1_BIN` as the absolute path of the v1.18.33 binary, for example `export OC_V1_BIN="$HOME/opt/opencode-1.18.33/bin/opencode"`. The run takes about 10 minutes, because each `test_rate_limit_error_and_governor` waits out the built-in 429 retries.

Run: `OC_CONTRACT=1 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_contract.py' -v`
Expected: Every test prints `ok`, except possibly `test_probe_hidden_agent_dispatch` and `test_probe_command_bang_expansion`. Note which of those two print `FAIL`, because Steps 8 to 16 depend on that result. Any other failure is a contract break, so fix it before you continue.

- [ ] **Step 8: Decide the hidden-agent outcome**

If `test_probe_hidden_agent_dispatch` passed in Step 7, a hidden agent can be dispatched, so `render_agent` keeps `hidden: true` on v2. Confirm this with the command below, then skip to Step 13.

Run: `grep -n 'hidden: true' _shared/oc_harness.py`
Expected: one line that reads `lines.append("hidden: true")` and sits under no `if major` guard. If an earlier task guarded it so v2 emits no `hidden`, remove that guard so both majors append it again. Then run `sh _shared/sync.sh`.

If the probe failed, continue with Step 9.

- [ ] **Step 9: Write the failing render test (only if the hidden probe failed)**

Append this class to `_shared/tests/test_oc_contract.py`, before the `if __name__ == "__main__":` block. It always runs, because it needs no binary.

```python
class RenderHiddenTest(unittest.TestCase):
    def test_v2_agents_are_not_hidden(self):
        frontmatter = oc_harness.render_agent(PROBE_AGENT_SRC, 2).split("\n---\n")[0]
        self.assertNotIn("hidden:", frontmatter)

    def test_v1_agents_stay_hidden(self):
        self.assertIn("\nhidden: true\n", oc_harness.render_agent(PROBE_AGENT_SRC, 1))
```

The probe stays in the module as a record of the finding. Mark it as an expected failure by editing its definition in `class V2ContractTest` so it reads:

```python fragment
    @unittest.expectedFailure  # v2 cannot dispatch a hidden agent via `subagent`; render_agent drops `hidden` on v2
    def test_probe_hidden_agent_dispatch(self):
```

- [ ] **Step 10: Run the render test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_contract.py' -k test_v2_agents_are_not_hidden`
Expected: FAIL with "AssertionError: 'hidden:' unexpectedly found in"

- [ ] **Step 11: Stop emitting `hidden` on v2 and sync the vendored copies**

In `_shared/oc_harness.py`, inside `render_agent`, replace the single line

```python fragment
    lines.append("hidden: true")
```

with

```python fragment
    # v2 cannot dispatch a hidden agent through the `subagent` tool
    # (test_oc_contract.V2ContractTest.test_probe_hidden_agent_dispatch), so only v1 hides them.
    if major == 1:
        lines.append("hidden: true")
```

Then copy the source of truth into every skill.

Run: `sh _shared/sync.sh && for d in brainstorming-glm dev-team-glm doc-generator-glm requirements-code-audit-glm systematic-debugging-glm writing-plans-glm; do cmp _shared/oc_harness.py "$d/scripts/oc_harness.py"; done`
Expected: exit 0 with no `cmp` output (all six copies byte-identical)

- [ ] **Step 12: Run the render test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_contract.py' -k RenderHiddenTest -v`
Expected: PASS, with `Ran 2 tests` and a final line `OK`

- [ ] **Step 13: Decide the `/docs` recon outcome**

If `test_probe_command_bang_expansion` failed in Step 7, v2 does not expand `` !`cmd` ``, so `/docs` stays unchanged. Mark the probe as an expected failure by editing its definition in `class V2ContractTest` so it reads as shown below. Then skip to Step 17.

```python fragment
    @unittest.expectedFailure  # v2 does not expand !`cmd` in commands; /docs keeps its Turn-1 recon
    def test_probe_command_bang_expansion(self):
```

If the probe passed, continue with Step 14.

- [ ] **Step 14: Write the failing `/docs` test (only if the bang probe passed)**

Append this block to `_shared/tests/test_oc_contract.py`, before the `if __name__ == "__main__":` block.

```python
DOCS_MD = os.path.join(ROOT, "doc-generator-glm", "opencode", "commands", "docs.md")
DOCS_RECON = "!`(git ls-files 2>/dev/null || find . -type f -not -path './.git/*') | head -n 200`"


class DocsCommandTest(unittest.TestCase):
    def test_docs_command_preexpands_recon(self):
        with open(DOCS_MD) as fh:
            text = fh.read()
        self.assertIn(DOCS_RECON, text)
        self.assertIn(DOCS_RECON, oc_harness.render_command(text, 2, "/tmp/doc-generator"))
```

- [ ] **Step 15: Run the `/docs` test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_contract.py' -k test_docs_command_preexpands_recon`
Expected: FAIL with "AssertionError: \"!`(git ls-files 2>/dev/null" (the recon line is not in docs.md)

- [ ] **Step 16: Add the recon line to `/docs` and verify it passes**

In `doc-generator-glm/opencode/commands/docs.md`, add this line as the new last line of the file. It goes directly after the existing `Load skill ...` line, whatever that line reads after earlier tasks.

```text
Pre-expanded file list (use it instead of spending a turn on recon): !`(git ls-files 2>/dev/null || find . -type f -not -path './.git/*') | head -n 200`
```

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_contract.py' -k test_docs_command_preexpands_recon -v`
Expected: PASS, with `Ran 1 test` and a final line `OK`

- [ ] **Step 17: Run the full suites and the contract module again**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: the final line is `OK (skipped=24)`, with every existing test still green

Run: `env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS bash dev-team-glm/scripts/selftest.sh`
Expected: `passed=` ≥ 324 and `failed=` ≤ 5 (only the 5 known macOS failures)

Run: `OC_CONTRACT=1 PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_oc_contract.py' -v`
Expected: PASS. The final line starts with `OK`. It carries `expected failures=N` only for the probes that Steps 9 and 13 marked.

- [ ] **Step 18: Commit**

```bash
cd ..
git add glm-skills/_shared/tests/test_oc_contract.py glm-skills/_shared/tests/fake_provider.py glm-skills/_shared/oc_harness.py glm-skills/brainstorming-glm/scripts/oc_harness.py glm-skills/dev-team-glm/scripts/oc_harness.py glm-skills/doc-generator-glm/scripts/oc_harness.py glm-skills/requirements-code-audit-glm/scripts/oc_harness.py glm-skills/systematic-debugging-glm/scripts/oc_harness.py glm-skills/writing-plans-glm/scripts/oc_harness.py glm-skills/doc-generator-glm/opencode/commands/docs.md
git commit -m "feat(shared): opt-in real-binary OpenCode contract tests with fake provider and sandbox discovery check"
```

---

### T36: glm-skills CLAUDE.md harness facts

**Depends:** T05, T35

**Interfaces:**
- Consumes: `OC_CONTRACT=1`; `render_agent`; `hidden`; `subagent`; `/docs`; ` !`; ` `

**Files:**
- Modify: `glm-skills/CLAUDE.md`

All commands run from `glm-skills/` (`cd glm-skills` first); `git` commands run from the git root.

- [ ] **Step 1: Add the OpenCode version facts section to CLAUDE.md**

Insert the block below as a new `###` section at the end of `## Architecture: the shared GLM design`, i.e. after the last `### Per-skill engines` bullet (`doc-generator-glm`) and directly before the `## Conventions and gotchas` heading, with one blank line on each side. The section starts with a level-3 heading (three `#` characters, same level as `Per-skill engines`) reading `OpenCode version facts (v1.18.x and v2.0.x)`, followed by one blank line and the body below. Add only facts listed here; do not add claims about v1 behaviour that are not below.

```markdown
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
```

- [ ] **Step 2: Correct the stale dev-team OpenCode facts in the same file**

In the `**dev-team on OpenCode:**` and `**Plugin role mapping:**` text under `### Per-skill engines`, make exactly these replacements (the old text may be wrapped across lines; keep the surrounding wording):

1. `(env `DEVTEAM_HARNESS=opencode` or `OPENCODE` set)` → `(`is_opencode()`: `DEVTEAM_HARNESS` decides when set, else `OPENCODE`, else `oc_harness.harness()`, since v2 never sets `OPENCODE`)`.
2. `are set in env `DEVTEAM_ROLE` per lane.` → `are set in env `DEVTEAM_ROLE` per lane; when it is unset, the v2 plugin uses `event.agent` if it names a dev-team role.`
3. The plugin path `skills/glm/dev-team-glm/opencode/ plugins/` (split across two lines) → `dev-team-glm/opencode/plugins/`.
4. `whose event carries `tool` and `input`` → `whose event carries `{tool, sessionID, agent, messageID, id, input}``.
5. `on receipt of `edit`, `write`, `patch`/`apply_patch`, or `bash` tools` → `on receipt of `write`, `edit`, `patch`, `apply_patch`, `multiedit`, `shell`, `bash`, `execute` or `batch` tools`.

- [ ] **Step 3: Verify the section and the corrections**

Run: `cd glm-skills && grep -c 'OpenCode version facts' CLAUDE.md && grep -c 'OPENCODE_DISABLE_CLAUDE_CODE_SKILLS' CLAUDE.md && grep -c 'multiedit' CLAUDE.md && ! grep -n 'skills/glm/' CLAUDE.md && echo OK`
Expected: three lines `1`, `1`, `1`, then `OK` (no `skills/glm/` line printed).

Then read the new section once against the spec Evidence list: every tools, hook, effort, flags, brief, events, 429, skills, agent and env fact above is present, and nothing claims v1 behaviour beyond it.

- [ ] **Step 4: Commit**

```bash
git add glm-skills/CLAUDE.md
git commit -m "feat(shared): record OpenCode v1.18.x/v2.0.x harness facts in CLAUDE.md"
```
