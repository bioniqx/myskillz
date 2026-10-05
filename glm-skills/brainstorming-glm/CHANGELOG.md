# 9.3-glm (from 9.2) — OpenCode v1/v2 hardening

- Path rename: scratch/session dirs are `.brainstorm/` (was a tool-branded dir), specs go to
  `docs/specs/`. The visual-companion header is a plain `Brainstorming` label: no version
  lookup, no telemetry env handling, no outbound link.
- `/brainstorm` command: when the `!` line arrives raw (`opencode run`
  does not expand it), the model runs `context.sh` itself as its first call.
- SKILL.md: one OpenCode lane rule. v2 dispatches background `subagent`
  lanes (`explorer`/`researcher`), v1 runs `oc_harness.py run`, and
  `task` is only the fallback. The fallback agent is `general`, never
  `general-purpose` or `Explore`.
- SKILL.md: `oc_harness.py run` is never a foreground call. On v2 it goes
  through `shell` with `background: true` and a `timeout`, because v2
  kills a foreground shell call after 120 s and orphans web lanes.
- SKILL.md: results come from `oc_harness.py result <out>` instead of
  the raw `<id>.jsonl`. `lanes.json` lives under `.brainstorm/drafts/`,
  and lane output goes to a fresh dir per run under `.brainstorm/drafts/`
  (`mktemp -d`), so a rerun never reads stale lane results.
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
- Parity repair against the original brainstorming 6.3: the spec commit is
  conditional (skipped when the user or a loaded instruction file forbids
  committing self-initiated files, with the "not committed" review-gate
  text); the hand-off passes the committed or untracked spec path and
  checks the installed `writing-plans` name first; R0 allows visual
  companion screens; round 1 loads deferred tools first; `allowed-tools`
  gains `start-server.sh`, `stop-server.sh` and `kill -0`; red flag
  "Spawn 64 because I can"; `glm-tuning.md` states the weaker independence
  of Flash judgment lanes and fixes the install path.
- Visual companion scripts, `helper.js`, `frame-template.html`, `context.sh`
  and `visual-companion.md` re-synced from the original.

# 9.2-glm (from 9.1) — OpenCode effort correction

Corrects the 9.1 claim that OpenCode process lanes always run at `max`.
Live end-to-end runs against the real v1.18.32 and v2.0.16 binaries (a mock
OpenAI-compatible provider logging every request body) showed the actual
cause was different: a `mode: subagent` agent makes `opencode run --agent`
on v1 silently fall back to the built-in `build` agent, so the agent's
`reasoningEffort` frontmatter was never applied. Rendering v1 agents with
`mode: all` fixes that, and `reasoningEffort` then reaches the wire
verbatim as `reasoning_effort`. On v2, agent-frontmatter effort (any form)
is never sent; the only working lever is a `#<effort>` variant suffix on
the explicit `--model` flag, so `oc_harness.py` now appends it when a lane
carries an `effort` field. `lanes.json` lane dicts may now carry an
optional `effort: low|high|max` key for this purpose.

- Correction (2026-09-25, live v2.0.16 probe): the "v2 never sends
  agent-frontmatter effort" claim above only holds for `opencode run
  --agent` lanes, whose explicit `--model` overrides the agent; dispatched
  directly through the `subagent` tool (`background: true` param, real
  per-lane parallelism), v2 *does* honor the agent's own `model:`+`variant:`.

# 9.1-glm (from 9.0) — OpenCode layer

Adds an OpenCode installation path alongside Claude Code, unchanged. New
neutral agent sources `opencode/agents/explorer.md` (read-only, mirrors the
Code lane rules) and `opencode/agents/researcher.md` (web, mirrors the Web
lane rules), plus command source `opencode/commands/brainstorm.md` that
injects `context.sh` output and the skill path, then loads the skill with
`$ARGUMENTS`. `oc_harness.py install` renders these into the detected v1 or
v2 dialect. SKILL.md frontmatter `name` changed to `brainstorming` (drop the
`-glm` suffix, matching the installed directory) and gained a note in the
harness fallback table: OpenCode's tool names are `task` for a lane,
`todowrite` for TaskCreate, `webfetch` for WebFetch, and AskUserQuestion
becomes plain-text numbered questions. `glm-tuning.md` gained a new
OpenCode harness section covering the install command and the v1 caveat
that `reasoning_effort` is dropped for `glm-*` process lanes, so every
OpenCode-side lane runs at `max`.

# 9.0-glm (from 8.0) — tuned for GLM-5.3 and GLM-5.3-Flash

The uploaded folder was named `brainstorming-6.3` but its SKILL.md and
CHANGELOG were the 8.0 content, so this build is numbered 9.0-glm. Drop-in
replacement: same skill `name: brainstorming`, same hand-off to
`writing-plans`, same spec path.

## What GLM changes (and why each edit exists)

**Lane economics rewritten — the single biggest speed win.** On the GLM
coding plan `haiku` → GLM-5.3-Flash while `sonnet` AND `opus` both →
GLM-5.3. The old `sonnet`-for-judgment tier was therefore paying main-model
price and main-model latency for every "cheap" lane. R2 now defaults every
lane to Flash (~1.8× output speed, ~9× cheaper, 3× coding-plan quota) and
caps GLM-5.3 lanes at 2 — the ones whose conclusion picks the approach.

**Effort ladder (R3), new.** GLM-5.3 cannot disable thinking;
`reasoning_effort` is low/high/max, default max, and thinking tokens are
emitted before any tool call at ~63 tok/s. Max on a dispatch or merge round
is pure latency. The ladder puts `low` on mechanical rounds, `high` on the
design draft, `max` only on the approach choice.

**Forced batching (R4), new.** GLM emits fewer parallel tool calls per turn
than Claude unless given a count. Round 1 now opens by stating the number of
calls, with a recovery rule when only some land — re-issue as one batch, or
push the work into Flash lanes that batch internally.

**Explicit state carry (R5), new.** GLM's accuracy drops on long chains and
errors compound. Wide-and-shallow over deep chains, ≤4 tool calls per lane,
and a 5-line state restatement before each gate.

**Prompt shape reworked for GLM's training.** GLM is trained for brevity and
mishandles rigid XML-tag ceremony and behaviour-as-table. So: the
`<HARD-GATE>` XML block is now plain "R0"; every section is a numbered
imperative rule; behavioural tables became rule lists; tables survive only
for reference data (speeds, prices, caps, fallbacks). The content carried
over from 8.0 is ~13% tighter with no rule dropped; SKILL.md still ends
~7% larger overall (14748 → 15789 characters), because R2-R5 and the
fallback table are new rules that must fire on every run.

The lane prompts stay inline on purpose. Moving them to their own file
would make SKILL.md ~10% smaller than 8.0, but lanes are dispatched in the
same message that reads `architectural.md`, so the prompts have to already
be in context — pulling them out would push every fan-out into a second
round, which costs far more than the bytes save.

**Lane prompts rebuilt.** Numbered rules instead of prose; no tool
inventory (the harness injects tool schemas ahead of your text); tighter
budgets (4 code / 5 web tool calls); explicit word caps and exact output
labels, because Flash is verbose by default. The shared block stays
byte-identical with slice lines last — GLM caching is prefix-based, so one
changed character upstream costs the whole cache.

**Harness auto-adapt.** `context.sh` now prints `harness:` and `route:`
lines, the resolved model slots, and whether GLM slots are mapped. SKILL.md ends with a
fallback table for a missing Agent tool, AskUserQuestion, ToolSearch,
Workflow, `!` preprocessing, or TaskCreate — substitute, never stall.

**New file `glm-tuning.md`.** Model slot table with measured speed and
price, the full `settings.json` for the z.ai route (including why each var
matters), the effort ladder rationale, a symptom → cause → fix table for GLM
failure modes, and the dated evidence behind all of it. Read only when
configuring the runtime or debugging a GLM-specific failure — it costs
nothing on a normal run.

**Reviewer and verifier lanes moved to Flash**, with the reviewer loop still
inline by default (a reviewer loop is a deep chain, which is exactly where
GLM degrades).

**Visual companion:** screens written at effort `low`; long mockup sets can
go to a Flash lane; note that Flash is natively multimodal and can read a
screenshot back, while GLM-5.3 is text-only.

**context.sh** also gained a single-line-`package.json` fallback for
`npm_deps`. Still read-only, still bounded, still always exits 0.

## Unchanged

R0 gate, the three paths and the one-way ratchet, the turn budgets, the
research rules and source tiers, `writing-plans` hand-off, spec path
`docs/specs/YYYY-MM-DD-<topic>-design.md`, the visual-companion
server, helper, and frame template.

## Setup

`glm-tuning.md` §2. The short version: point `ANTHROPIC_BASE_URL` at the
z.ai Anthropic route, map `ANTHROPIC_DEFAULT_HAIKU_MODEL=glm-5.3-flash`,
raise `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` to 64, set
`CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000`, and allow WebSearch/WebFetch in
`permissions` so background lanes do not stall.

# 8.0 (from 7.0) — research-first, lane tiers, verified harness limits

Live context preloaded via `scripts/context.sh`; round discipline (round 1 =
everything nameable now, round 2 = fetches, round 3 = conflicts); T0/T1/T2
lane tiers; model tiering; architectural path cut from 3-4 to 2-3 human
turns; spec review moved from 4 reviewer subagents to a 5-lens inline
self-review; claim verifier, spec pre-draft and runner-up approach run
during the human's reading time; research-before-recommending rules, source
tiers, version-pinned queries; `Path:` classification line;
forced-diversity approach lanes; fanout-playbook with verified caps, waves,
Workflow template and failure handling.

# 7.0 (from 6.3) — speed-first rewrite

Hard turn budgets; "assume, don't ask"; merge rules; fanout-playbook.md;
progressive disclosure; bounded worker outputs; model tiering.
