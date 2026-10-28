# Running this skill on GLM-5.3 / GLM-5.3-Flash

Read this only when the skill misbehaves or you are tuning it. The skill itself
does not need it.

## Contents

Model facts the design is built on · Tier routing · Lanes · Environment · Harness notes · Failure modes seen in practice

## Model facts the design is built on

| | GLM-5.3 | GLM-5.3-Flash |
|---|---|---|
| Context / max output | 1M / 128K | 1M / 128K |
| Throughput, TTFT | ~63 tok/s, ~3.4 s | ~114 tok/s, ~2.3 s |
| Coding-plan credits in/out | 6.9x / 24x | 2.3x / 8x |
| Coding-plan quota | 1x | 3x |

- Thinking is always on. `thinking.type` accepts only `enabled`; a request for
  `disabled` is silently downgraded to the `low` effort level.
- `reasoning_effort` is `low | high | max`, default `max`. Effort, not model
  choice, is the real latency dial - which is why every contract carries a
  `Tier`.
- Parallel tool calls are supported but GLM emits far fewer per turn than
  Claude does (2 is a commonly observed ceiling in the wild). Any design that
  needs 20+ tool calls in one assistant message will quietly serialize. That is
  the reason the fan-out lives inside the script, not in the model's turn.
- Prefix caching is by exact prefix. Every writer request in one build shares a
  byte-identical system block (rules + plan header + Global Constraints +
  References + inlined reference files) so the cache hits from the second
  request onward.
- GLM is trained toward brevity and handles numbered plain-text rules better
  than XML ceremony or behavior tables. Flash is more verbose than median, so
  the writer prompt caps output shape explicitly with start and end markers.
- Long-horizon chains accumulate error. Three orchestrator turns is not just a
  speed choice; it is an accuracy choice.

## Tier routing

| Tier | API model | Effort (api lane) | Agent-lane model | Agent-lane effort |
|---|---|---|---|---|
| `light` | glm-5.3-flash | low | glm-5.3-flash | high |
| (default) | glm-5.3-flash | high | glm-5.3-flash | high |
| `deep` | glm-5.3 | max | glm-5.3 | max |

On the api lane the tier's effort column applies. On the agent lane every tier
runs the installed agents' pinned efforts: `glm-plan-task-writer` pins
`thoughtLevel: max`, so `light` and `std` groups both run at high, and the
deep writer and reviewer pin `max`. The `low` effort applies to the api lane
only.

The z.ai Anthropic-compatible route maps the `haiku` alias to Flash and both
`sonnet` and `opus` to GLM-5.3, so never ask for `opus`: it costs the same as
`sonnet`. The provider cap on parallel requests is a stated limit of this
route, not a design goal. Width stays the product you are designing.

Override with `PLAN_MODEL_STD` and `PLAN_MODEL_DEEP`.

## Lanes

1. **api** (default when a key is found). One `build` call opens up to 8
   threads, one request per task, no subagent, no per-writer system prompt, no
   tool round trips. Lint and repair happen in Python. This is the fast path.
2. **agent** (fallback). The script writes one brief per writer and prints a
   DISPATCH table. On ZCode, foreground subagents launched together run in
   parallel and this lane is respectable: dispatch each row as one `Agent`
   call in a single message. The agent lane starts up to 8 lanes in ONE
   message (`PLAN_LANE_WIDTH`, clamped 1..8, lowers it; the api lane keeps 8
   threads), and each writer takes up to 4 tasks, because batching beats more
   workers.

Force a lane with `build --lane api|agent`.

## Environment

```bash
export ZAI_API_KEY=<GLM Coding Plan key>          # or ANTHROPIC_AUTH_TOKEN
# China / BigModel: https://open.bigmodel.cn/api/paas/v4  (protocol auto-detects as openai)
export PLAN_MAX_WORKERS=8         # optional, 8 is the default and the cap (provider limit)
export PLAN_PROTOCOL=anthropic    # optional override: anthropic | openai
```

The script also reads keys out of `~/.claude/settings.json`,
`~/.zcode/v2/credentials.json` (its `api-key` field) and `~/.zcode/*.json`
when no environment variable is set. `doctor` prints which
source won; `doctor --ping` sends a one-token probe.

The coding endpoint is for coding scenarios only and is not interchangeable
with the general endpoint.

## Harness notes

**ZCode.** Skills live in `~/.zcode/skills/<name>/SKILL.md` and are invoked with
`$glm-writing-plans`. The description is capped at 1024 characters; a body-size cap is unverified.
Subagents live in `~/.zcode/agents/` (user level only, created from
Settings), cannot spawn further subagents, and run in parallel in the
foreground. ZCode can import a Claude- or Codex-format skill directory directly
from Settings, by symlink or copy.

## Failure modes seen in practice

| Symptom | Cause | Fix |
|---|---|---|
| `LANE agent` when you expected api | no key found | `doctor`, then export `ZAI_API_KEY` |
| Many `LINT` rows after the fan-out | contracts too vague - signatures or Files under-specified | tighten `Produces` and `Files`, re-run with `--resume` |
| Writers invent symbols | `Spec` ranges miss the section | widen the ranges from the heading map |
| Bodies truncated mid-code | `--max-tokens` too low for a huge task | raise it, or split the contract |
| Slow despite the api lane | most tasks marked `deep` | reserve `deep` for genuinely hard work |
