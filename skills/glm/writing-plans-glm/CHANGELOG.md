# writing-plans v9 (GLM edition) - what changed from v8

Target: GLM-5.3 and GLM-5.3-Flash, running in OpenCode or ZCode.

## The structural change: parallelism moved out of the model's turn

v8 asked the orchestrator to emit up to 64 subagent calls in one message. Two
facts break that on this target:

1. GLM emits far fewer parallel tool calls per turn than Claude - two is a
   commonly observed ceiling. A 64-call message quietly becomes a trickle.
2. OpenCode's task tool dispatches subagents one at a time. Background
   dispatch exists only behind `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true`.

v9 puts the fan-out inside `plan_tool.py`: one `build` call opens up to 64
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
overlap. Neither OpenCode nor ZCode supports `!` command injection in a skill,
so call 1 is an explicit shell call that also resolves the tool path across all
six skill directories.

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
  aborts the whole fan-out fast when the endpoint is down instead of 64 slow
  retries.

## Quality kept, and slightly raised

- The deterministic linter is unchanged and still the backbone: structure,
  placeholders, portability, file ownership, produced signatures, step
  numbering, Run/Expected pairing, `git add` scope, and Python/JSON/TOML/bash/JS
  syntax checks.
- Each writer now gets up to two automatic repair rounds inside the script,
  with the exact lint errors fed back - failures that used to need a
  re-dispatch turn are gone.
- Risk-based review still runs (deep tier, long body, many consumers, lint
  warnings), also 64-wide, and a rewritten body is accepted only if it lints at
  least as well as the one it replaces.
- Portability scan now also rejects the words OpenCode, ZCode and GLM inside a
  plan.

## New commands

- `brief` - everything Phase 0 used to need, in one call.
- `build` - validate, fan out, lint, repair, review, assemble, clean.
- `doctor [--ping]` - lane, key source, base URL, protocol, models, concurrency,
  live probe.
- `setup [--harness opencode|zcode|claude] [--apply]` - installs the fallback
  subagent in the right place for the detected harness.

`contracts`, `wait`, `review`, `assemble`, `check`, `lint-task` and `hook-lint`
are unchanged in behavior and still drive the agent lane.

## Install

1. Unzip into one of:
   - `~/.zcode/skills/writing-plans/`
   - `~/.config/opencode/skills/writing-plans/` (or `.opencode/skills/` in a project)
   - `~/.claude/skills/writing-plans/` (read by all three harnesses)
2. `export ZAI_API_KEY=<key>` and
   `export ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`
3. `python3 <skill>/scripts/plan_tool.py doctor --ping`
4. Optional: `python3 <skill>/scripts/plan_tool.py setup --apply` for the
   agent-lane fallback subagent.
5. On OpenCode: the skill is discoverable as `writing-plans` (the `name:` field in
   SKILL.md without the `-glm` suffix). Use `/plan <spec-path>` in any OpenCode
   session with the zai-coding-plan provider enabled.
