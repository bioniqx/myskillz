# ZCode hardening for the glm-skills ports — design

Date: 2026-10-06 · Status: approved by the user (full ZCode mode, real user-level hooks,
installer run against the real `~/.zcode` after green tests) · Scope: `glm-skills/` only.
Goal: every one of the eight `glm-*` skills installs and runs perfectly on ZCode 3.14.4
(`sh install-zcode.sh`), verified by the `_shared` suite, `selftest.sh` and temp-home installs.

## Verified ZCode facts this design rests on

Sources: official docs (fetched and claim-verified 2026-10-06) + `zcode.cjs` binary probes +
local `~/.zcode` install state.

- Skills live at `~/.zcode/skills/<name>/SKILL.md`, invoked `$<name>`. A frontmatter
  `description` over 1024 chars makes ZCode drop the whole skill; a body over 100KB is
  truncated when loaded; per-turn trigger metadata is the name plus a description excerpt of
  up to 250 characters, so the WHEN-clause must sit at the front of every description. No `!`
  preload support; unknown frontmatter keys are ignored.
- Custom subagents live at `~/.zcode/agents/<name>.md`, user level only, no nesting; several
  launched together in the foreground run in parallel. Frontmatter keys: `name`,
  `description`, `model`, `thoughtLevel` (honored only together with a specific `model`),
  `color`, `tools`/`disallowedTools`, `maxTurns`, `injectAgentsMd`, `mcpServers`. No
  haiku/sonnet/opus aliases exist.
- Subagents are dispatched through the `Agent` tool (Task alias) whose input schema is
  `{description, prompt, subagent_type, run_in_background}` with `subagent_type` omitted
  defaulting to `general-purpose` — the Claude Code Task shape minus the `model` parameter
  (binary-verified; the web docs confirm the tool and built-ins `general-purpose` + `Explore`
  but do not document the schema). `SendMessage`, `TaskStop`, and Bash `run_in_background` +
  `timeout` all exist and are Claude-Code-compatible.
- Hooks: a full Claude-Code-compatible system (SessionStart, UserPromptSubmit, PreToolUse,
  PermissionRequest, PostToolUse, PostToolUseFailure, Stop — no SubagentStop). User-level
  config at `~/.zcode/cli/config.json` must set `hooks.enabled: true`; project/workspace-level
  hooks are ignored. stdin JSON carries snake_case + camelCase fields including `agent_type`
  (the calling agent's name); exit code 2 blocks; stdout
  `hookSpecificOutput.permissionDecision` = allow/ask/deny — the exact shapes `guard.py`
  already prints.
- No public headless CLI. Credentials live at `~/.zcode/v2/credentials.json` under
  `account-provider → coding-plan → account → <plan> → <uuid> → api-key` (field name
  `api-key`, hyphenated; OAuth/JWT fields keep distinct names and are never picked).

## Chosen approach: full ZCode mode mirroring the OpenCode hardening pattern

Rejected: install-only hardening (engine stays in Claude mode) — the printed dispatch lines
carry `model: opus/haiku` which ZCode's Agent tool rejects, `glm-programmer-lite` is not
installed, `doctor --fix` writes Claude-only env into `.claude/settings.local.json`, and the
provider misdefaults to anthropic (cap 64 instead of 8) → 429 storms. Rejected: shipping
guards as a ZCode plugin — marketplace installation cannot be automated by doctor;
user-level `config.json` is simpler and doctor can merge it safely.

## Work items

### 1. Shared key discovery (`_shared/zai_client.py`, then `sync.sh` to all vendored copies)

- `KEY_FILES` gains `~/.zcode/v2/credentials.json` as the first zcode entry, before the
  root-level `~/.zcode/*.json` files; `KEY_FIELDS` gains `api-key`. The existing named-field
  walk (depth ≤ 6) then finds coding-plan keys; precedence stays env vars first, then files
  in `KEY_FILES` order.

### 2. `install-zcode.sh`

- `convert()`: map `steps: N` → `maxTurns: N` and `omitClaudeMd: true` → `injectAgentsMd:
  false` instead of dropping them; drop `permissionMode` (ZCode ignores it); keep
  `background` (the binary parses an agent `background` field; ignored-key risk is nil).
- Delegate the seven glm-dev-team ZCode agents (the five file agents plus rendered
  `glm-programmer-lite` and the new `glm-programmer-strong`) to `devteam.py doctor --harness
  zcode --fix`, same pattern as the existing `plan_tool.py setup --harness zcode --apply`
  delegation; `--flash/--main` pass through.
- `glm-debug-worker.md` conversion gains `thoughtLevel: low` (mechanical worker; never pays
  for max).
- Fix the stale closing message: ZCode now HAS hooks (guards installable via doctor); body
  over 100KB truncates (only description over 1024 drops); installed skills and agents need
  a NEW ZCODE SESSION (not an app restart) to load.

### 3. `guard.py` — new `zcode` mode

- stdin: the ZCode payload (`hook_event_name`, `tool_name`, `tool_input`, `cwd`,
  `agent_type`). Role = `agent_type`; roles outside glm-dev-team (or missing) → silent allow,
  so the user-level hooks never affect ordinary sessions. Programmer roles →
  `guard_edit`/`guard_bash`; reviewer/leader/investigator roles → `guard_edit_ro`/
  `guard_bash_ro`. Tool names: Write|Edit → edit check, Bash → bash check, others allow.
  Silent-allow leftovers (Claude's "defer to the ask flow") become explicit denies for lane
  roles, mirroring `guard_oc` (a background lane must never wait on a prompt nobody answers).
  `Stop` → `guard_stop` only for programmer roles (the Conductor's own Stop always allows).
  Fail-open unchanged.

### 4. `devteam.py` — zcode harness mode

- `is_zcode()`: `DEVTEAM_HARNESS=zcode` or `oc_harness.harness() == "zcode"` (path/env).
- `detect_provider`: zcode defaults to `glm` (cap 8) instead of anthropic.
- Dispatch: zcode prints `subagent_type` + description only (no `model:`); strong slices
  (risk high / size large / attempt ≥ 2) route to `glm-programmer-strong`; lite stays
  `glm-programmer-lite`.
- `doctor --harness zcode [--fix]`: checks and installs the seven ZCode agents into
  `~/.zcode/agents/` (rendered ZCode frontmatter: real GLM ids from `--flash/--main`,
  `thoughtLevel`, keep
  `tools`/`disallowedTools`/`maxTurns`/`color`, no hooks in agent files), merges the
  PreToolUse (`Write|Edit`, `Bash`) and Stop hooks into `~/.zcode/cli/config.json`
  (`hooks.enabled: true`, `type: process`, absolute `guard.py` path; `.bak` before rewrite;
  idempotent; prints how to disable), and writes no Claude env. `start` calls it
  automatically on zcode.
- SKILL.md gains a "ZCode protocol" section (mirror of "OpenCode protocol"): Agent tool =
  `subagent_type` + `run_in_background`, wake-up = a lane completion notification →
  `devteam next [<id>]` (no SubagentStop event; the engine-side integrate re-check is the
  gate), `SendMessage`/`TaskStop` exist, new-session requirement after installs.
- `README.md` (Vietnamese) gains the matching ZCode section.

### 5. Per-skill fixes (from the two audit lanes)

- **glm-brainstorming**: `context.sh` gains a zcode branch in harness detection (no
  CLAUDE_CODE_* caps line; width cap 8); the bootstrap/`oc_harness.py` path loop gains
  `~/.zcode/skills/glm-brainstorming`; `glm-tuning.md` gains a ZCode runtime section; the
  TaskCreate row names `TodoWrite`; the OpenCode-only tool-name maps and the Claude-Code-only
  env/`Workflow` facts are scoped to their harnesses; the AskUserQuestion fallback wording
  covers ZCode (no question tool documented); SendMessage/TaskStop notes cover ZCode; the
  visual-companion platform notes gain a ZCode entry.
- **glm-idea-to-spec**: description reordered so the WHEN-clause sits inside the first 250
  chars (kept ≤ 1024); the unguarded Phase-2 AskUserQuestion line gets a plain-text fallback.
- **glm-requirements-code-audit**: description reordered likewise; SKILL.md gains the
  standard bootstrap path loop (today it has none); `agents/zcode/*.md` `tools` values are
  CamelCased (Read, Grep, Glob, Write); `audit.py` zcode dispatch line drops `subagent_type=`
  jargon; `setup --harness zcode` strips `opencode/` + `SETUP.md` from the copy;
  `SETUP.md`/`glm-tuning.md` stale claims fixed (hooks exist; key paths; char count
  recomputed).
- **glm-doc-generator**: "Explore is Claude Code only" corrected (Explore is a ZCode built-in;
  `general` is the OpenCode one); Appendix A frontmatters gain `model:` so `thoughtLevel` is
  honored, and the text points at the auto-installed `agents/zcode/` files;
  `agents/zcode/glm-doc-reviewer.md` runs glm-5.3 + thoughtLevel high (today Flash@low
  contradicts the skill's own tuning); the `OC_MAX_LANES` mention is scoped to OpenCode.
- **glm-git-diff-summary**: the FAN_OUT ZCode row drops `model: haiku` (no model parameter on
  the Agent tool; the recovery text already names glm-5.3-flash).
- **glm-systematic-debugging**: `setup --harness zcode` text points at `install-zcode.sh`
  (frontmatter rewrite + thoughtLevel low); `glm-tuning.md` stale claims fixed (key discovery
  paths; `steps` → `maxTurns` failure mode); the README ZCode row aligned.
- **glm-writing-plans**: zcode dispatch headers drop `subagent_type=`/`model sonnet`/alias
  jargon (name the agent, real ids only where a model must be named);
  `agent_file("zcode")` gains `maxTurns: 16`; SKILL.md R9 scopes ANTHROPIC_BASE_URL to
  Claude-compatible harnesses; `glm-tuning.md` key/truncation claims fixed.
- **CLAUDE.md (glm-skills)**: ZCode facts updated (hooks user-level; no SubagentStop; Agent
  tool schema; credentials path; body truncation; lite/strong agents; new-session reload).

Convention: every behavior change is recorded in the skill's CHANGELOG/README where one
exists, per the folder's CLAUDE.md.

### 6. Tests

`test_zai_client` (v2/credentials.json walk, `api-key` field), `test_install_zcode`
(steps→maxTurns, omitClaudeMd→injectAgentsMd, permissionMode dropped, lite/strong installed
via the doctor delegation, message claims), new zcode-mode engine/guard tests mirroring
`test_devteam_oc_*` (temp HOME: doctor zcode writes agents and merges hooks into
`~/.zcode/cli/config.json`; dispatch drops model and picks strong; provider defaults to glm;
guard zcode routing, fail-open, no-op for foreign roles), `selftest.sh` coverage for new
engine behavior, and audit/doc-generator tests for their zcode agents. The full `_shared`
suite and temp-home installs stay green.

## Evidence

- Skill description drop / body truncation / 250-char trigger excerpt / `$` invocation —
  [ZCode docs, Skill](https://zcode.z.ai/en/docs/skill) (2026-10-06, claim-verified)
- Hook events, user-level config with `hooks.enabled`, permissionDecision, exit 2,
  project-level ignored — [ZCode docs, Hooks](https://zcode.z.ai/en/docs/hooks) (2026-10-06,
  claim-verified)
- Subagent frontmatter keys, thoughtLevel×model pairing, no nesting, foreground parallelism —
  [ZCode docs, Subagents](https://zcode.z.ai/en/docs/subagents) (2026-10-06, claim-verified)
- Agent tool schema `{description, prompt, subagent_type, run_in_background}` with no
  `model`, `agent_type` in the hook stdin payload, no SubagentStop event, agent `background`
  field — binary probes of `/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs`
  (2026-10-06; unverified by web docs — the docs pages confirm the tool and built-ins but not
  the schema)
- Credentials location and shape — local `~/.zcode/v2/credentials.json` probe (2026-10-06)

## Assumptions

- Work happens directly on `main` (repo AGENTS.md), inside `glm-skills/` only; the unrelated
  uncommitted root AGENTS.md/CLAUDE.md edits are left alone.
- `background: true` stays in converted agent frontmatter (the binary parses it; if the docs'
  key list is authoritative it is silently ignored — harmless either way).
- The 250-char description front-loading for glm-idea-to-spec and glm-requirements-code-audit
  is harness-universal, not ZCode-only.
- After implementation and green tests, `sh install-zcode.sh` runs against the real `~/.zcode`
  (idempotent; `.bak` for changed agents; a new ZCode session loads them — not an app
  restart).
