# Running this skill on GLM-5.3 / GLM-5.3-Flash

Read this only when the skill misbehaves or you are tuning it. The skill itself
does not need it.

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

| Tier | API model | Effort | Agent-lane alias |
|---|---|---|---|
| `light` | glm-5.3-flash | low | haiku |
| (default) | glm-5.3-flash | high | haiku |
| `deep` | glm-5.3 | max | sonnet |

The z.ai Anthropic-compatible route maps `haiku` to Flash and both `sonnet` and
`opus` to GLM-5.3, so ask the agent lane for `opus` only never: it costs the same as
`sonnet`, and the provider cap on parallel requests is a stated limit of this
route, not a design goal. Width stays the product you are designing.

Override with `PLAN_MODEL_STD` and `PLAN_MODEL_DEEP`.

## Lanes

1. **api** (default when a key is found). One `build` call opens up to 8
   threads, one request per task, no subagent, no per-writer system prompt, no
   tool round trips. Lint and repair happen in Python. This is the fast path on
   every harness.
2. **agent** (fallback). The script writes one brief per writer and prints a
   DISPATCH table. On ZCode, foreground subagents run in parallel and this lane
   is respectable. On OpenCode v1, the task tool dispatches subagents one at a
   time unless `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true` is set, so
   expect roughly serial behavior without it. On OpenCode v2, the `subagent`
   tool takes `background: true`: dispatch each DISPATCH row that way, one
   after another with no wait, for real parallelism from one tool call per
   turn. The agent lane starts 6 background lanes per message by default (up to
   8 with `PLAN_LANE_WIDTH` or `OC_MAX_LANES`; the api lane keeps 8 threads),
   and each writer takes up to 4 tasks, because batching beats more workers.

Force a lane with `build --lane api|agent`.

## Environment

```bash
export ZAI_API_KEY=<GLM Coding Plan key>          # or ANTHROPIC_AUTH_TOKEN
export ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic
# China / BigModel: https://open.bigmodel.cn/api/paas/v4  (protocol auto-detects as openai)
export PLAN_MAX_WORKERS=8         # optional, 8 is the default and the cap (provider limit)
export PLAN_PROTOCOL=anthropic    # optional override: anthropic | openai
```

The script also reads keys out of `~/.claude/settings.json`,
`~/.config/opencode/opencode.json`, `~/.config/opencode/auth.json` and
`~/.zcode/*.json` when no environment variable is set. `doctor` prints which
source won; `doctor --ping` sends a one-token probe.

The coding endpoint is for coding scenarios only and is not interchangeable
with the general endpoint.

## Harness notes

**OpenCode.** Skills live in `.opencode/skills/<name>/`,
`~/.config/opencode/skills/<name>/`, or any `~/.claude/skills/` or
`~/.agents/skills/` directory. Only `name`, `description`, `license`,
`compatibility` and `metadata` are read from the frontmatter; everything else is
ignored, not an error. The skill frontmatter `name` field (with the `glm-`
prefix) is used for command and agent discovery. There is no `!` command
injection in skills, which is why call 1 is an explicit shell call; the `/glm-plan`
command injects the skill directory and argument string, then loads the skill.
The `glm-plan-task-writer` agent provides the fallback when an API key is not
available; `oc_harness.py run` starts a subprocess for tool-using agent lanes.
Subagents live in `~/.config/opencode/agents/`, rendered with `mode: all` on v1 (a `mode: subagent`
agent is silently swapped for the default `build` agent by `opencode run --agent`) and `mode:
subagent` on v2. Rendering also writes `reasoningEffort:` into v1 agents and `variant: <effort>` into
v2 agents, so the `subagent` tool honors an agent's own model and effort when dispatched without an
explicit `model` override. Headless
runs are `opencode run -m <provider>/<model> --auto "<prompt>"`.

**ZCode.** Skills live in `~/.zcode/skills/<name>/SKILL.md` and are invoked with
`$glm-writing-plans`. The description is capped at 1024 characters and the body at
100 KB. Subagents live in `~/.zcode/agents/` (user level only, created from
Settings), cannot spawn further subagents, and run in parallel in the
foreground. ZCode can import a Claude Code or Codex skill directory directly
from Settings, by symlink or copy.

**Claude Code.** Unchanged from v8: `setup --apply` sets
`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` to 8 and installs the auto-lint hook.

## Failure modes seen in practice

| Symptom | Cause | Fix |
|---|---|---|
| `LANE agent` when you expected api | no key found | `doctor`, then export `ZAI_API_KEY` |
| Many `LINT` rows after the fan-out | contracts too vague - signatures or Files under-specified | tighten `Produces` and `Files`, re-run with `--resume` |
| Writers invent symbols | `Spec` ranges miss the section | widen the ranges from the heading map |
| Bodies truncated mid-code | `--max-tokens` too low for a huge task | raise it, or split the contract |
| Slow despite the api lane | most tasks marked `deep` | reserve `deep` for genuinely hard work |
