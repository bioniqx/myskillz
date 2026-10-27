# 10.2 (from 10.1) — one router for every sibling

`scripts/handoff.py` (vendored from `_shared/handoff.py`) is the binding
misroute and exit check. Round 1 runs `route --self glm-brainstorming`.
`HANDOFF` means read that sibling's SKILL.md and stop. `next --event` is
how an approved design leaves. The chain stops at 3 skills. `check.py route`
uses the same table.

# 10.1 (from 10.0) — gates the model was dropping, checked by script

GLM-5.3 drops rules that sit in the middle of a long prompt, treats a
private restatement as optional, and fabricates lines to satisfy a minimum
count. The checks that used to be prose now fail closed in `check.py`:

- `route` catches an obvious misroute (bug, viability, commit message,
  approved plan) and is binding when it names a skill.
- `send` rejects a draft whose first line is not the Path line, a design
  that omits assumptions or out of scope, an Architectural draft with
  fewer than two `APPROACH N:` lines, a citation that does not match the
  file, an undated URL, or a code fence over 40 lines.
- `approve --asked design` returns yes only for an approval token at the
  start of the reply. "sounds good", "ok", and a reply to a side question
  return no.
- Lane templates no longer demand 3-6 findings or 2-6 claims. Zero is valid.
- `glm-explorer`, `glm-researcher` and new `glm-drafter` pin Flash at
  `thoughtLevel: high`. Approach drafts, the claim verifier and the runner-up
  use `glm-drafter` instead of the session model. `context.sh` prints the
  three gates at the top of the block the model just received.
- Lane rules have one home, the agent file. The dispatch prompt is only
  the slice (task, root, date, angle, question). A missing agent is the
  one case that pastes the agent body in front of that slice.
- R14 no longer restates the checker. `check.py` prints the repair, and
  the skill only says when to run each mode, so the body stays under the
  500-line point where GLM starts dropping rules in the middle.

# 10.0 (from 9.9) — mechanical verification, hard-rule header, tables to rules

New `scripts/check.py` (stdlib-only, read-only) and R14, "Verify before you
cite". Three modes read lane output on stdin through a heredoc: `cites`
checks each `path:line — fact — "snippet"` against the repo, `web` lints
`claim — tier — URL — date — "quote"` lines (OK, WEAK, DROP), `spec` lints
the written spec. The main thread runs the first two in round 2 and the third
in the spec turn; BAD and DROP items are never cited, WEAK and unchecked items
are labelled unverified. SKILL.md opens with eight numbered hard rules (the
approval gate, the Path line, round-1 batch, no unseen citations, check.py,
at most 4 questions, judgment vs lanes, no downgrade) and closes with a
six-line "Before you send" checklist. The R1 hand-off table, the R11 sibling
lane table and the harness fallback table became numbered rules, since GLM
mishandles delegation tables. The Code lane gains rules for copied paths and
line numbers, a verbatim snippet on every FINDINGS line and a "write the
report now" turn limit (cap 150 words); the Web lane gains copied-URL and
quote-only-from-fetch rules (the explorer and researcher agent files carry
the same text, and `maxTurns` rises to 6 and 7). Three new red flags. The
architectural spec turn lints the spec before self-review and Evidence lines
come from `check.py web`. glm-tuning.md gains four failure rows and section 7.

# 9.9 (from 9.8) — orchestrate every sibling skill and agent

R1 triage now covers all seven sibling skills: `glm-requirements-code-audit`
(code vs spec), `glm-doc-generator` (document existing code) and
`glm-git-diff-summary` (branch summary, commit/PR message) join the table, and
`glm-dev-team` also takes settled tasks the user asks to just implement,
review, refactor or migrate. Mixed requests hand off the first step only; a
missing sibling is reported with the install command. R11 adds a sibling-lane
table: `glm-debug-worker` for a claim about current behavior that only a
command settles, `glm-investigator` (max 2, Spike/Architectural) for surveys
needing a shell or more than 4 hops, `glm-spot-reviewer` after an approved
Bounded change touching more than one file or a sensitive surface. Briefings
go to `.brainstorm/drafts/`, reports to the paths the dev-team guard allows.
Every other sibling agent is reached only through its owner skill. New R13
fixes the post-approval exits (Architectural to glm-writing-plans, small
Bounded implemented here plus spot review, larger Bounded to glm-dev-team,
optional glm-git-diff-summary at the end). Two
new red flags.

# 9.8 (from 9.7) — sibling triage: route misrouted tasks instead of designing them

R1 gains a triage step before the Path line: a request that is actually a raw
product idea or viability question (`glm-idea-to-spec`), a bug, failing test or
unexpected behavior (`glm-systematic-debugging`), an already-approved design
(`glm-writing-plans`) or an already-approved plan (`glm-dev-team`) is announced
in one line and handed off via the Skill tool with a 2-3 line summary, instead
of being brainstormed. Guards: routing is not implementation (R0 unchanged), at
most 3 skills per task counting this one, one hand-off direction per task (the
target skill owns it and never routes back), lanes and subagents never invoke
skills, and mid-task the only hand-off point is a path upgrade that reveals the
task belongs to a sibling. New red flag: "It's misrouted, but I can design it
anyway."

# 9.7 (from 9.6) — protocol alignment: out-of-scope + costly ambiguity

Design output now always names what it will NOT do: the Bounded message carries a
one-line out-of-scope, the architectural design message gains an "Out of scope"
section (§2 item 8), and the spec carries it forward alongside Evidence and
Assumptions (§4). R6 names the costly-ambiguity case explicitly: a decision the
whole design rests on with no ≥80% answer in sight is a forking question — ask
it, never pick silently. Maps the skill onto the user's GLM coding protocol
(clarify phase: restate, assumptions, out-of-scope, ask when two readings are
both plausible and the wrong one is expensive).

# 9.6 (from 9.5) — context.sh git block concurrency

context.sh: `git ls-files` output is captured once and reused for the tracked
count, the `files:` line and the `tree:` aggregation (it ran two to three times
before); the hot-dir `git log` runs in the background behind a mktemp file
while the quick git calls execute and is joined with `wait` before emit, so the
stdout block keeps its content and order. Still read-only, still bounded, still
always exits 0: the backgrounded job is guarded with `|| true` and `wait`
cannot propagate a failure into the script exit.

# 9.5 (from 9.4) — ZCode only

OpenCode support removed: the `oc_harness.py` lane machinery, the SKILL.md
OpenCode lane rule and tool-name maps, the `glm-tuning.md` OpenCode harness
section, and the `opencode/`-era history entries (9.1-9.3; see git history).
context.sh resolves the harness on its own, and lanes dispatch through the
ZCode Agent tool with the installed `glm-explorer`/`glm-researcher` agents.

# 9.4 — ZCode surface

- context.sh: zcode branch in harness detection (skill dir under `*/.zcode/*`);
  the zcode caps line prints the lane width (default 8, hard max 8) with no
  CLAUDE_CODE_* caps line.
- SKILL.md: the bootstrap scripts-dir loop names `~/.zcode/skills/glm-brainstorming`;
  the TaskCreate fallback row names `TodoWrite`; Claude Code env/`Workflow`
  facts are scoped to Claude Code; the AskUserQuestion fallback covers ZCode.
- fanout-playbook.md: the `SendMessage` note covers ZCode.
- architectural.md: the `TaskStop` note covers ZCode.
- visual-companion.md: platform notes gain a ZCode entry.
- glm-tuning.md: ZCode runtime section.

# 9.0 (from 8.0) — tuned for GLM-5.3 and GLM-5.3-Flash

The uploaded folder was named `glm-brainstorming-6.3` but its SKILL.md and
CHANGELOG were the 8.0 content, so this build is numbered 9.0. Drop-in
replacement: same skill `name: glm-brainstorming`, same hand-off to
`glm-writing-plans`, same spec path.

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
research rules and source tiers, `glm-writing-plans` hand-off, spec path
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
