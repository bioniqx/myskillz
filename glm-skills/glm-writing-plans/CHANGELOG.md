# glm-writing-plans v9 (GLM edition) - what changed from v8

**Parity repair:** the linter functions scan, fence_mask, files_block, commit_errors, allow_hit, apply_marks, cmd_wait and contract_hashes are re-synced from the original; the inline threshold is N <= 1; the handoff restores the glm-dev-team adoption offer and "(recommended)"; the reviewer prompt holds one format block with a consuming step for "Unfixable (needs contract change)".

**Concurrency:** every model-call fan-out (script threads, writer and reviewer dispatch, `PLAN_MAX_WORKERS`, `PLAN_LANE_WIDTH`, `--workers`, `--agents`, subagent-cap env vars) is capped at 8, the provider limit on concurrent API calls; the 4-task writer group size is unchanged.

**Fixes:** (WP5) Bootstrap checks the skill locations in a fixed order and exits with a clear error on a miss (no `python3 "" brief`).

**ZCode hardening:** the zcode dispatch headers name the `glm-plan-task-writer` agent (or the `general-purpose` fallback) with no `subagent_type=`/model-alias jargon and real ids only where a model must be named; `agent_file("zcode")` gains `maxTurns: 16`; SKILL.md R9 scopes `ANTHROPIC_BASE_URL` to Claude-compatible harnesses; the glm-tuning key list includes the v2 credentials file and the body-cap claim is labeled unverified.

**Post-v9 (2026-10-08):** `setup --harness zcode` no longer renders `glm-plan-task-writer` from an inline template — it copies all three `agents/*.md` (`glm-plan-task-writer`, `glm-plan-task-writer-deep`, `glm-plan-reviewer`) verbatim; the files carry final ZCode frontmatter and are the single source of truth, and `install-zcode.sh` installs them the same plain-copy way.

**thoughtLevel (2026-10-08):** `glm-plan-reviewer` moves `high` → `max` — review dispatches route to the deep lane (`glm-5.3` + `max`), so the reviewer vets deep-tier task bodies at the depth they were written; the writers keep their tier efforts (`std` high, `deep` max).

**Parallel recon (2026-10-10):** `brief` runs its read-only recon steps (git log / ls-files / status, conventions reads, inline pattern-file reads, spec read, `pick_patterns` candidate reads) through the shared `pmap` pool via a new `run_recon` helper; the cap stays 8 and the printed output is byte-identical.

Target: GLM-5.3 and GLM-5.3-Flash, running in ZCode.

## The structural change: parallelism moved out of the model's turn

v8 asked the orchestrator to emit up to 64 subagent calls in one message. Two
facts break that on this target:

1. GLM emits far fewer parallel tool calls per turn than Claude - two is a
   commonly observed ceiling. A 64-call message quietly becomes a trickle.
2. Every agent dispatch is a full model turn, so a wide subagent fan-out
   spends exactly the turns the tools were built to remove.

v9 puts the fan-out inside `plan_tool.py`: one `build` call opens up to 8
threads and sends one request per task straight to the coding endpoint. No
subagent, no per-writer system prompt, no tool round trips, and lint plus repair
run in Python. The agent lane is kept as an automatic fallback for anyone
without a key, and ZCode's parallel foreground subagents still serve it well.

## Pipeline: 10+ calls -> 3

| | v8 | v9 |
|---|---|---|
| Load context | skill-load `!` injection + a message of parallel reads | one `brief` call, spec body and pattern files already inlined |
| Contracts | 1 write + `contracts` + fix loop | 1 write |
| Bodies | dispatch + `wait` + re-dispatch + `review` + `wait` + `assemble` | one `build` call |

`brief` replaces Phase 0 entirely: it prints the repo snapshot, the spec heading
map, the numbered spec body, the conventions file and three or four
auto-selected pattern files ranked by recency, test-ness and spec-keyword
overlap. No harness injects `!` commands into a skill, so call 1 is an
explicit shell call that also resolves the tool path across the skill dirs.

## GLM-specific tuning

- Tier routing rewritten for the real z.ai model map: `light` and default go to
  glm-5.3-flash at effort low and high, `deep` to glm-5.3 at effort max. `opus`
  is never requested - the route maps it to the same model as `sonnet`.
- Effort, not model choice, is the latency dial on an always-thinking model, so
  `Tier` is documented as the main speed control.
- Every writer request in one build shares a byte-identical system prefix
  (rules, plan header, Global Constraints, References, inlined reference files)
  so prefix caching hits from the second request onward.
- Prompts are numbered plain-text rules: no XML ceremony, no behavior tables.
- Writer output is bounded by explicit start and end markers, because Flash runs
  verbose.
- Retries handle 429 and 5xx with jittered backoff, and a shared failure budget
  aborts the whole fan-out fast when the endpoint is down instead of every
  worker retrying slowly.

## Quality kept, and slightly raised

- The deterministic linter is unchanged and still the backbone: structure,
  placeholders, portability, file ownership, produced signatures, step
  numbering, Run/Expected pairing, `git add` scope, and Python/JSON/TOML/bash/JS
  syntax checks.
- Each writer now gets up to two automatic repair rounds inside the script,
  with the exact lint errors fed back - failures that used to need a
  re-dispatch turn are gone.
- Risk-based review still runs (deep tier, long body, many consumers, lint
  warnings), also 8-wide, and a rewritten body is accepted only if it lints at
  least as well as the one it replaces.
- Portability scan now also rejects harness and vendor names (ZCode, GLM, …)
  inside a plan.

## New commands

- `brief` - everything Phase 0 used to need, in one call.
- `build` - validate, fan out, lint, repair, review, assemble, clean.
- `doctor [--ping]` - lane, key source, base URL, protocol, models, concurrency,
  live probe.
- `setup [--harness zcode|claude] [--apply]` - installs the fallback
  subagent in the right place for the detected harness.

`contracts`, `wait`, `review`, `assemble`, `check`, `lint-task` and `hook-lint`
are unchanged in behavior and still drive the agent lane.

## Install

1. Unzip into one of:
   - `~/.zcode/skills/glm-writing-plans/`
   - `~/.claude/skills/glm-writing-plans/`
2. `export ZAI_API_KEY=<key>` and
   `export ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`
3. `python3 <skill>/scripts/plan_tool.py doctor --ping`
4. Optional: `python3 <skill>/scripts/plan_tool.py setup --apply` for the
   agent-lane fallback subagent. Invoke the skill with `$glm-writing-plans`.
