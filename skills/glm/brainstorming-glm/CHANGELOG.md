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
`docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`, the visual-companion
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
