# OpenCode (v1 + v2) + GLM-5.3 Optimization — Design

Date: 2026-09-25 · Status: approved design · Scope: every skill and agent under `skills/glm/`

## Goal

Make all six GLM ports (`brainstorming-glm`, `dev-team-glm`, `doc-generator-glm`,
`requirements-code-audit-glm`, `systematic-debugging-glm`, `writing-plans-glm`) run at their best on
**OpenCode 1.18.x and OpenCode v2** with **Z.ai GLM-5.3 / GLM-5.3-Flash**. Success means:

- Real parallelism on OpenCode for both text-only jobs and tool-using jobs, without depending on
  OpenCode's serial `task` tool or its flag-gated background subagents.
- `reasoning_effort` reaches the model on every path our code controls, and `doctor` reports whether it
  reaches the model on the paths OpenCode controls.
- One Z.ai client instead of three drifted copies.
- Zero wasted bootstrap turns: OpenCode commands inject context the way `!` preload does in Claude Code.
- One source per agent/command, rendered into the v1 or v2 dialect detected at install time.
- `dev-team-glm` works on OpenCode (today it is Claude-Code-only).

## Decisions (user-approved 2026-09-25)

1. **Harness scope:** OpenCode first (v1 and v2). Claude Code and ZCode paths keep working unchanged but get
   no new optimization.
2. **dev-team parallelism:** process lane (one `opencode run` per slice in its own git worktree).
3. **Phasing:** Phase 1 = shared core + OpenCode layer + five skills; Phase 2 = dev-team port.
4. **OpenCode v2 is supported alongside v1** (added after approval).

## Approaches considered

1. **Python-orchestrated fan-out everywhere (chosen).** Keep the v9 doctrine ("fan-out lives in the
   script, not the model turn"): the existing **api lane** for text-only jobs plus a new **process lane**
   that runs one headless `opencode run` per tool-using worker. Add a thin OpenCode layer (commands,
   agents, plugin, config snippet) rendered per OpenCode major version.
   - Pros: true parallelism on both versions; effort set by our code on the api lane; per-lane worktree
     isolation via `--dir`; JSON events give governor telemetry; testable offline with a stub `opencode`.
   - Cons: one OpenCode process per lane (RAM, startup); the conductor polls; process-lane effort depends
     on OpenCode passing it through (see Effort below).
2. **OpenCode-native background subagents** (`OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS`). Least code,
   but the flag is still required on v2, v2 marks the parent completed while background work is still
   running (open bug), GLM emits ~2 tool calls per turn, and subagents get no worktree isolation.
3. **Minimal port** (frontmatter and tool names only). dev-team stays unusable on OpenCode; brainstorming
   and doc-generator stay serial.

## Architecture

```
_shared/ (canonical, not installed)          each skill/scripts/ (vendored byte-identical copies)
  zai_client.py   ──sync.sh──▶ zai_client.py   api lane: text jobs, up to 64 threads
  oc_harness.py   ──sync.sh──▶ oc_harness.py   OpenCode: version detect, render, install, process lane
each skill/opencode/ (neutral sources, rendered at install)
  commands/<cmd>.md     one command per skill
  agents/<role>.md      neutral agent header + body
dev-team-glm/opencode/plugins/guard.v1.js, guard.v2.js   (Phase 2)
```

Skill folders stay self-contained after install: shared code is vendored, never imported across folders.
`sync.sh` copies `_shared/*.py` into every skill that uses it; the selftest fails if any copy differs.
`zai_client.py` goes to debugging, writing-plans and audit; `oc_harness.py` goes to all six skills (it
is also the installer).

## Components

### zai_client.py (shared, vendored)
- One stdlib client for every script. Default route: OpenAI-compatible coding endpoint
  `https://api.z.ai/api/coding/paas/v4/chat/completions` with native `reasoning_effort` (`low|high|max`).
  Anthropic route (`/api/anthropic`) stays as an explicit opt-in (`--protocol anthropic`), never an
  automatic fallback, because its effort control is undocumented.
- Key discovery: union of today's lists (env vars, `~/.claude/settings.json`, OpenCode `auth.json` and
  config, `~/.zcode/*.json`). Never writes keys or URLs.
- Retries 429/1302/1305/5xx with jittered exponential backoff, honoring `Retry-After`; one AIMD width per
  process shared by all threads (halve on throttle, +1 after a clean window).
- Callers keep a byte-identical system/prefix block per wave (Z.ai prefix caching is automatic).
- Replaces `debug_tool.api_call`, `plan_tool.call_model` and the audit client. Removes the
  `thinking.budget_tokens` path.

### oc_harness.py (shared, vendored)
- `detect()`: runs `opencode --version`, returns major `1` or `2`, or `none` when the binary is missing.
- `render_agent(src, major)`: reads a neutral agent file and emits the dialect for that major. Neutral
  header fields: `description`, `model` (`flash` | `pro`), `effort` (`low` | `high` | `max`),
  `temperature` (optional), `access` (`read` | `write`), `bash` (bool), `web` (bool), `steps`.
  - v1 output: `mode: subagent`, `hidden: true`, `model: zai-coding-plan/glm-5.3[-flash]`,
    `temperature`, `steps`, `permission: {edit, bash, webfetch}`, `reasoningEffort` (forwarded to the
    provider; currently dropped by OpenCode for `glm-*`, kept so it works once fixed).
  - v2 output: `mode: subagent`, `hidden: true`, `model: zai-coding-plan/glm-5.3[-flash]`, `steps`,
    `permissions:` rule list, `request.body: {reasoning_effort, temperature}`.
  - Never emits Claude-only keys: on v1, unknown agent keys are sent to the provider as model options.
- `render_command(src, major)`: commands use only the fields both versions share (`description`, body
  with `!` shell injection and `$ARGUMENTS`); no `subtask`/`subagent` field.
- `install(skill_dir, major)`: copies the skill to `~/.config/opencode/skills/<name>/` (frontmatter `name`
  equals the directory, which v1 requires and v2 accepts), writes rendered agents and commands, records
  the installed major in a marker file, and prints the `opencode.json` snippet for that major. Never
  writes keys.
- `run(lanes_json)` — the process lane:
  - Input: lanes JSON (`id`, `agent`, `model`, `dir`, `brief`, `timeout`). Output: one result file per
    lane, a summary table and a `NEXT:` line.
  - Builds the command per major. v1: `opencode run --dir <dir> --agent <a> -m <provider/model>
    --format json --auto "<brief>"`. v2: same intent, but the flags are checked once against
    `opencode run --help`; a missing flag stops the run with the flag named (no silent fallback).
  - Default: one standalone process per lane. A shared `opencode serve` + `--attach` is used only when
    the startup probe proves that `--dir` applies per attached session.
  - Width: `--width` or `OC_MAX_LANES`, default 8, capped at 64; halved on 429/1302/1305 seen in JSON
    events. dev-team passes its governor width instead.
  - A lane is done when its process exits. The runner then writes `<lane>.done` with exit code and last
    error, so completion never depends on plugin session events.
  - Stall: no JSON event for 180 s (`--stall`) → kill the lane, report `LANE STALL` with the last event.

### OpenCode layer (per skill, installed by `oc_harness.py install <skill_dir>`)
- **Commands** `/brainstorm`, `/debug`, `/plan`, `/audit`, `/docs` (Phase 1), `/devteam` (Phase 2):
  `!` injection of the resolved skill path plus `doctor` output (`context.sh` for brainstorming), then
  "load skill X with $ARGUMENTS". SKILL.md keeps its R0 bootstrap as the fallback when no injected block
  is present.
- **Skill hygiene:** frontmatter `name` = install directory; descriptions ≤1024 chars. The config snippet
  denies the Claude-tuned originals OpenCode also discovers under `~/.claude/skills/`
  (`permission.skill` deny patterns hide them from the agent).
- **Config snippet (per major):** `zai-coding-plan` provider, Flash for worker agents and GLM-5.3 for
  judgment agents, skill deny list, and Z.ai Web Search + Web Reader MCP servers for research lanes
  (endpoint form taken from `docs.z.ai/devpack/mcp/*` during implementation).
- **Root installer** `install-opencode.sh`: runs `oc_harness.py install` for every skill. Each tool's
  existing `setup --harness opencode` delegates to the same code.

### Effort handling
- api lane: always explicit `reasoning_effort` per tier (unchanged tier tables).
- Process lanes and the main OpenCode session: v1 drops `reasoning_effort` for `glm-*` (open issue);
  v2 overlays go under `request.body`, but the v2 agent docs say overlays are not yet sent. `doctor
  --probe-effort` sends the same small prompt at `low` and `max` through one rendered agent and compares
  reasoning tokens (or latency when usage is absent), then prints `EFFORT honored|ignored` per major.
- Consequence while ignored: every OpenCode-side call runs at `max`, so skills keep pushing tool-free
  work into the api lane.

### Per-skill changes
- **systematic-debugging-glm:** swap to `zai_client`; `/debug`; neutral `debug-worker` agent; agent-lane
  fallback on OpenCode uses `oc_harness run` instead of a serial DISPATCH table.
- **writing-plans-glm:** swap to `zai_client` (fixes effort); `/plan`; neutral task-writer agent (replaces
  the frontmatter `plan_tool.py` hard-codes); agent-lane fallback via `oc_harness run`; auto-lint runs
  inside `build` (the Claude-only PostToolUse hook stays for Claude Code).
- **requirements-code-audit-glm:** swap to `zai_client`; `/audit`; `agents/opencode/*` move to
  `opencode/agents/` as neutral sources; agent-lane fallback via `oc_harness run`.
- **brainstorming-glm:** `/brainstorm` injects `context.sh`; T1 code/web lanes run through
  `oc_harness run` with neutral `explorer` (read-only) and `researcher` (web) agents; OpenCode tool-name
  map in SKILL.md (`task`, `todowrite`, `webfetch`, plain-text questions).
- **doc-generator-glm:** gains vendored `oc_harness.py` (no longer "no scripts"); parallel writers via
  `oc_harness run`; `/docs`; neutral writer agent.
- **dev-team-glm (Phase 2):** programmers/reviewers dispatched through `oc_harness run`, one worktree per
  slice via `--dir`; `guard.v1.js` (v1 plugin export, `tool.execute.before`) and `guard.v2.js`
  (`Plugin.define`, `tool.execute.before`) both pipe the Claude-hook-shaped JSON to `guard.py` and throw
  on deny; `.done` markers come from the runner; the governor reads runner JSON events instead of
  `~/.claude/projects` transcripts; `doctor --harness opencode` checks agents, plugin, config and the
  installed-vs-detected major; SKILL.md dispatch vocabulary rewritten for the runner flow.

## Data flow

1. User runs `/cmd args` → command injects skill path + doctor/context → model loads the skill.
2. Script call 1 (`brief`/`probe`/`start`) writes work items.
3. Text-only items → `zai_client` api lane (up to 64 threads). Tool-using items → `oc_harness run`
   (governor-sized width; one worktree per writer when writes happen).
4. Results land as files; the script merges, lints/verifies and prints a `NEXT:` line.
5. Model reads the summary, acts, and repeats only `next`/`finalize`.

## Error handling

- API: retry/backoff on throttle and 5xx; every failure printed with its HTTP/Z.ai code and message.
- Process lane: exit code, last JSON error event and stall timeouts reported per lane (`LANE FAIL`,
  `LANE STALL`); partial results kept; `--resume` reruns failed lanes only.
- `opencode` missing → skills fall back to today's agent lane and say so in one line.
- Installed dialect ≠ detected major (e.g. after upgrading v1 → v2, whose installer replaces the v1
  binary) → `doctor` fails with "re-run install-opencode.sh".
- Guard plugin: same deny/fail-open semantics as `guard.py` today; a plugin load error surfaces in
  `doctor`.

## Testing

- `selftest.sh` with a stub `opencode` on `PATH` that answers `--version` as 1.18.32 or 2.x and emits
  canned JSON events (success, 1302 throttle, stall):
  - rendered agents per major: required keys present, no Claude-only keys, v1 `permission` map vs v2
    `permissions` list;
  - rendered commands identical across majors;
  - runner command line per major, width halving on 1302, stall kill, `.done` markers;
  - Phase 2: guard plugin shim round-trip through `guard.py` for both plugin files.
- Vendored-copy identity check (`_shared/*` vs every copy); `py_compile` on all scripts; name = dir and
  description ≤1024 checks for every SKILL.md.
- Fix the BSD `sed -i` call so the suite runs green on macOS.
- Live (manual, costs quota): `doctor --ping` per skill; `doctor --probe-effort` on each major; one
  end-to-end run of each command on a toy repo in OpenCode 1.18.32, and again on v2 in a throwaway
  environment (the v2 installer replaces the v1 binary).

## Phasing

- **Phase 1:** `_shared/` (`zai_client.py`, `oc_harness.py`, `sync.sh`), neutral agent/command sources,
  root installer, and adoption in debugging, writing-plans, audit, brainstorming, doc-generator, for
  v1 and v2.
- **Phase 2:** dev-team-glm OpenCode port (runner dispatch, guard plugins v1+v2, governor telemetry,
  doctor, SKILL.md rewrite). Separate plan, started after Phase 1 lands and the effort probe results are
  known.

## Evidence

- OpenCode v1 skills: only name/description/license/compatibility/metadata read; `name` must match the
  directory; `permission.skill` deny hides a skill —
  [opencode.ai/docs/skills](https://opencode.ai/docs/skills/) (2026-09-24)
- v1 task tool dispatches subagents sequentially; parallel request closed "not planned" —
  [issue #29638](https://github.com/anomalyco/opencode/issues/29638) (2026-05-28); `task-parallel` PR still
  open — [PR #47107](https://github.com/anomalyco/opencode/pull/47107) (2026-09-16)
- v1 `opencode run` supports `--agent`, `-m`, `--dir`, `--format json`, `--attach`, `--auto`; `--dir` is
  "path on remote server when attaching" — [opencode.ai/docs/cli](https://opencode.ai/docs/cli/)
  (2026-09-25); older [issue #7376](https://github.com/anomalyco/opencode/issues/7376) says attach lacked
  it → shared serve is probe-gated.
- v1 plugins: `tool.execute.before` can throw to block; context has `directory`, `worktree` —
  [opencode.ai/docs/plugins](https://opencode.ai/docs/plugins/) (2026-09-24)
- v1 agents: unknown frontmatter keys are passed to the provider as model options —
  [opencode.ai/docs/agents](https://opencode.ai/docs/agents/) (2026-09-24)
- v1 drops `reasoning_effort` for `glm-*` ids (open, v1.18.31) —
  [issue #49551](https://github.com/anomalyco/opencode/issues/49551) (2026-09-17); GLM excluded from
  variants — [issue #18598](https://github.com/anomalyco/opencode/issues/18598) (2026-03-22)
- v2: plugins from v1 do not run; model `provider/model#variant`; per-agent overlays move under
  `request.body`; the v2 installer replaces the v1 binary —
  [opencode.ai/v2/docs/migrate-v1](https://opencode.ai/v2/docs/migrate-v1/) (2026-09-25)
- v2: skills no longer enforce name = directory; commands keep `!` injection and `$ARGUMENTS`; plugins keep
  `tool.execute.before` — [v2 skills](https://opencode.ai/v2/docs/skills/),
  [v2 commands](https://opencode.ai/v2/docs/commands/),
  [v2 plugins](https://opencode.ai/v2/docs/build/plugins/) (2026-09-25)
- v2 background subagents still flag-gated; parent reported completed while background work runs (open) —
  [issue #48826](https://github.com/anomalyco/opencode/issues/48826) (2026-09-13)
- GLM-5.3: thinking always on, `reasoning_effort` `low|high|max` default `max`, 1M/128K, coding endpoint
  `api.z.ai/api/coding/paas/v4` — [docs.z.ai/guides/llm/glm-5.3](https://docs.z.ai/guides/llm/glm-5.3)
  (2026-09-25)
- All GLM Coding Plans include Web Search, Web Reader, Zread and Vision MCP —
  [docs.z.ai/devpack](https://docs.z.ai/devpack) (2026-09-25)
- Versions: npm `opencode-ai` latest 1.18.32; v2 has migration docs but no explicit "stable" label.

Unverified (handled by probes or assumptions): v2 `opencode run` flags and JSON event shape; whether v2
sends `request.body` overlays; v2 command/skill/agent global directories match v1; `--attach` + `--dir`
per-session directory; Anthropic-route `budget_tokens` handling (a third-party report says it is ignored);
Z.ai MCP endpoint form.

## Assumptions

- Provider `zai-coding-plan` with a GLM Coding Plan key is the primary route on both majors.
- v2 global directories are the same as v1 (`~/.config/opencode/{skills,agents,commands,plugins}`);
  `doctor` verifies after install.
- Skill triggers and descriptions keep their current meaning; only `name` is normalized to the install
  directory. Repo folders keep the `-glm` suffix.
- Sampling stays as today: Z.ai publishes no temperature/top_p recommendation for GLM-5.3.
- Instruction style stays numbered imperative rules: Z.ai publishes no prompt-format guidance.
- The Claude-tuned originals in `~/.claude/skills/` are not modified, only denied inside OpenCode.
- Fixing the macOS `sed` failure in `selftest.sh` is in scope because verification needs a green suite.
