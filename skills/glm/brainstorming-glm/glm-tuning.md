# GLM Tuning — runtime setup, model economics, failure modes

Read when configuring the runtime, when a GLM-specific failure appears,
or when you want the numbers behind SKILL.md's R2/R3/R4. Not needed on a
normal run.

## 1. Model slots

The GLM coding plan serves an Anthropic-compatible endpoint, so every
Claude model alias resolves to a GLM model:

| Alias | Resolves to | Out speed | $/M in | $/M out | Use |
| --- | --- | --- | --- | --- | --- |
| `haiku` | GLM-5.3-Flash | 113.7 tok/s | 0.15 | 0.50 | every worker lane |
| `sonnet` | GLM-5.3 | 63.4 tok/s | 1.40 | 4.40 | ≤2 judgment lanes |
| `opus` | GLM-5.3 | 63.4 tok/s | 1.40 | 4.40 | main thread |

`sonnet` and `opus` are the SAME model. A "sonnet" lane is not a cheaper
or dumber GLM-5.3 — it is the main model billed again. That is why R2
defaults every lane to Flash: 1.8× the output speed, ~9× cheaper, and 3×
the coding-plan quota per point.

Time to first token: GLM-5.3 3.43 s, Flash 2.34 s. Both carry a 1M
context window and 128K max output, so "read everything plausible in
round 1" is cheap in context and expensive only in rounds.

## 2. Runtime setup

Claude Code against the coding plan (`~/.claude/settings.json` env, or
a `claude-glm` launcher):

```json
{ "env": {
    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "<your key, from the environment>",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.3",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.3",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5.3-flash",
    "API_TIMEOUT_MS": "3000000",
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "1000000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "64",
    "CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS": "64" },
  "permissions": { "allow": ["WebSearch", "WebFetch"] },
  "workflowSizeGuideline": "unrestricted" }
```

Why each matters here: the long `API_TIMEOUT_MS` covers always-on
thinking at effort `max`; the 1M auto-compact window stops Claude Code
compacting at Claude-sized thresholds and throwing away the round-1
reads; the two concurrency vars are what let R7's 64-lane ceiling be
real (default is 20 subagents / 16 workflow agents); disabling
non-essential traffic drops telemetry and update calls that the z.ai
route cannot serve anyway; and pre-allowing WebSearch/WebFetch stops
background lanes stalling on a permission prompt, which skill
`allowed-tools` cannot do because it only covers the invoking turn.

Direct API instead of a Claude-compatible harness: `temperature: 1`,
`top_p: 0.95`, `reasoning_effort` per R3, `thinking.clear_thinking:
false` for agent use, and `stream: true` with `tool_stream: true`.

## 3. Reasoning effort

`thinking.type` accepts only `"enabled"`; disabling reasoning is no
longer supported. `reasoning_effort` is `low | high | max`, default
`max`. Clients that expose an `off` setting map it to `low`.

The cost is real: thinking tokens are generated before any tool call at
the model's output rate, so `max` on a dispatch round adds seconds of
pure latency and buys nothing. Follow R3's ladder. Keep `max` for the
implementation work that follows approval — z.ai recommends it for
coding tasks.

## 4. Known failure modes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Only 1-2 of the round's calls were made | GLM emits fewer parallel calls per turn than Claude unless given a count | R4: state the count, re-issue the remainder as one batch, or push the work into Flash lanes |
| Lane ignores half the prompt | Rigid XML-tag ceremony and delegation tables are mishandled | Numbered imperative rules; tables only for reference data, never for behaviour |
| Lane returns 400 words of prose | Flash is verbose by default (≈1.3× the median output on public index runs) | Word cap plus exact output labels in the prompt; take what is usable rather than re-running for formatting |
| Every lane feels slow | Lanes running on `sonnet` = GLM-5.3 | Switch to `haiku`; keep ≤2 GLM-5.3 lanes |
| Accuracy drifts late in a long task | Long-horizon chains compound errors | R5: wide-and-shallow lanes, ≤4 tool calls per lane, restate state before each gate |
| Cache hit rate collapses across siblings | Prefix-based caching; one changed character upstream invalidates the rest | Byte-identical shared block, slice lines last |
| Tool-call parse errors on a self-hosted server | Known GLM tool-parser bugs on some vLLM/SGLang builds | Update the serving stack; do not work around it in the prompt |

## 5. Evidence

- GLM-5.3: 1M context, 128K max output, always-on reasoning,
  `reasoning_effort` low/high/max default max, `max` recommended for
  coding — [Z.AI docs, GLM-5.3](https://docs.z.ai/guides/llm/glm-5.3) (2026-09)
- GLM-5.3-Flash: 1M context, 128K output, `temperature: 1`, `top_p:
  0.95`, `tool_stream: true`, 3× coding-plan quota, 320B total / 18B
  active, native multimodal — [Z.AI docs, GLM-5.3-Flash](https://docs.z.ai/guides/vlm/glm-5.3-flash) (2026-09)
- Claude Code slot mapping opus/sonnet → `glm-5.3`, haiku →
  `glm-5.3-flash`, base URL, timeout and compact-window values —
  [Z.AI Claude Code guide](https://docs.z.ai/devpack/tool/claude) (2026-09)
- Speed and price: GLM-5.3 63.4 tok/s, TTFT 3.43 s, $1.40/$4.40 per M;
  Flash 113.7 tok/s, TTFT 2.34 s, $0.15/$0.50 per M, and Flash's above-median
  output volume — [Artificial Analysis](https://artificialanalysis.ai/models/glm-5-3) (2026-08)
- Reasoning cannot be disabled; `off` maps to `low` —
  [OpenClaw Z.AI provider notes](https://docs.openclaw.ai/providers/zai) (2026)
- Trained for brevity, rule-lists beat prose, tool schemas auto-injected
  ahead of your prompt, prefix-based caching, weaker on long-horizon
  chained tasks — [GLM system-prompt research for opencode](https://gist.github.com/apnea/e9dd7a650bdc3300375fffc54592f48d) (2026-05-12)
- "GLM-5.3 mis-handles several prompt conventions (e.g. rigid XML-tag
  ceremony, delegation-table adherence, tool-call formatting quirks)" —
  [oh-my-openagent issue #6923](https://github.com/code-yeongyu/oh-my-openagent/issues/6923) (2026)
- Tool-call parsing failures with GLM as a Claude Code backend on some
  vLLM builds — [vllm issue #42400](https://github.com/vllm-project/vllm/issues/42400) (2026)

UNVERIFIED: the exact ceiling on parallel tool calls per GLM-5.3 turn.
Public reports observe as few as two in one turn without an explicit
instruction; R4 is written to hold either way.

## 6. OpenCode harness

Install with `python3 skills/glm/_shared/oc_harness.py install
skills/glm/brainstorming-glm`, which renders `opencode/agents/explorer.md`
and `opencode/agents/researcher.md` plus `opencode/commands/brainstorm.md`
into the detected v1 or v2 dialect and writes `.oc-major` under the installed
skill folder. Tool-name map: `task` for a lane, `todowrite` for TaskCreate,
`webfetch` for WebFetch; AskUserQuestion becomes plain-text numbered
questions with approval as item 1.

OpenCode process lanes: v1 drops `reasoning_effort` for `glm-*` models, so
every lane launched through `oc_harness.py run` executes at `max` regardless
of the `effort` frontmatter key; keep tool-free work in the api lane via
`zai_client.py` when a lower effort matters.

