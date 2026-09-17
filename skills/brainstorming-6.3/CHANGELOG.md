# 8.0 (from 7.0) — research-first, lane tiers, verified harness limits

## Setup for 64-wide fan-outs (optional)
Claude Code runs 20 subagents at once by default and the Workflow runtime 16.
For the full 64 lanes without permission stalls, add to `~/.claude/settings.json`:

    { "env": { "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "64",
               "CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS": "64" },
      "permissions": { "allow": ["WebSearch", "WebFetch"] },
      "workflowSizeGuideline": "unrestricted" }

Without it the skill reads the real caps from Live context and runs waves.

## Speed
- Live context injected before the model reads the skill (`scripts/context.sh`,
  ~5-20 lines, <50 ms): date, skill dir, concurrency caps, git state, recent
  commits, hot dirs, full file list for small repos / tree counts for large ones,
  manifests + pinned dependency versions, docs, recent specs. Removes the usual
  "ls / find / cat pyproject" round. Read-only (GIT_OPTIONAL_LOCKS=0), skips
  scanning $HOME, always exits 0.
  Tested on Claude Code 2.1.274: a failing `!` command cancels the whole skill;
  shell env expansions such as `${FOO:-x}` inside `!` are rejected by the
  permission check (the harness's own `${CLAUDE_SKILL_DIR}` substitution works),
  and an un-approved script is refused — hence one script, pre-approved in
  `allowed-tools`.
- `allowed-tools` also pre-approves Read/Grep/Glob/WebSearch/WebFetch for the
  invoking turn, so round 1 never stalls on a permission prompt.
- Round discipline: round 1 = everything nameable now (all plausible reads,
  greps, all searches, ToolSearch for deferred tools, lanes); round 2 = fetches
  and follow-ups; round 3 = conflicts. Targets: ≤3 main rounds (Spike/Bounded),
  ≤4 (Architectural). Never retry denied/failed calls; web only via
  WebSearch/WebFetch, with registry-JSON/raw-README endpoints.
- Lane tiers: T0 direct parallel calls → T1 background subagents → T2 Workflow
  (explicit opt-in and only when its cap beats the subagent cap).
- Explicit model tiering (Explore inherits the main model): haiku lookups,
  sonnet judgment/research, main model synthesis only.
- Architectural 3-4 → 2-3 human turns (merged design message by default; send
  once the decisive lanes are back). AskUserQuestion carries the approval item.
- Spec review: 4 parallel reviewer subagents → 5-lens inline self-review
  (Superpowers v5.0.6: reviewer loop ~25 min, identical quality over 5 versions ×
  5 trials). Parallel reviewers only for security/migration/money/public-API.
- Claim verifier, spec pre-draft (`.superpowers/drafts/`, only when writes won't
  prompt), and runner-up approach run during the human's reading time.
- Worker prompts inlined in SKILL.md with a byte-identical shared prefix.

## Quality
- Research-before-recommending rules in SKILL.md + research-playbook.md:
  research-or-skip test, version-pinned queries (repo version AND latest), source
  tiers A/B/C/reject, recency, load-bearing claim verification (1 A or 2
  independent B + verbatim quote), budgets/stopping, query privacy, Evidence block.
- `Path: …` classification line opens the first message.
- Forced-diversity approach lanes (reuse / best practice / minimal change).
- fanout-playbook.md: verified caps, waves with batched refill, Workflow template,
  failure handling (cap error, denied web lane, 429, partial → SendMessage).

## Unchanged
- HARD-GATE, three paths, one-way ratchet, writing-plans hand-off, spec path.
- scripts/ server, helper, frame template (visual companion).

# 7.0 (from 6.3) — speed-first rewrite

- Hard turn budgets; "assume, don't ask"; merge rules; fanout-playbook.md;
  progressive disclosure; bounded worker outputs; model tiering.
