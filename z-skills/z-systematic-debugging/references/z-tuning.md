# Session-model tuning — why this skill is shaped the way it is

Read this when something is slow, when `scan` falls back to the agent lane, or when you are porting the skill to another harness.

## Session models

Six display names cover the three tiers a session can run on. The
flash tier carries every lane and the main thread, the pro tier runs
only when the session is pinned to it, and the Claude tier is the
harness default when no GLM model is configured.

| Model | Tier |
| --- | --- |
| GLM-5.3-Flash | flash tier |
| DeepSeek V4.1 Flash | flash tier |
| GLM 5.3 | pro tier |
| GLM 5.4 | pro tier |
| DeepSeek V4 Pro | pro tier |
| Claude Sonnet 5.5 | Claude tier |

No speed or price numbers are claimed for GLM 5.4, the DeepSeek models or Claude Sonnet 5.5.

GLM 5.4 (api id glm-5.4), from the vendor model page read on
2026-11-25: 1M context, 128K max output, thinking mode, tool calling,
JSON output, image and video input; the general Model API was still
pending at that date. Nothing else is claimed for it here.

## Model facts this design depends on

| Fact | Consequence in the skill |
|---|---|
| Thinking cannot be disabled. `thinking.type` only accepts `enabled`; a request to disable it is treated as `low`. | No "turn thinking off" advice anywhere. Only the effort level is tuned. |
| `reasoning_effort` = `low` \| `high` \| `max`, default `max`. | R7 effort ladder; `scan` sets it per worker so mechanical fan-out never pays for `max`. |
| GLM 5.3 and GLM-5.3-Flash: 1M context, 128K output. | Long `probe` output is affordable; verbosity, not context, is the risk — every tool caps its output. |
| GLM-5.3 and GLM-5.3-Flash: few tool calls per model turn (2 observed in public testing), even where the API advertises parallel tool calls. | R1: never rely on batching tool calls. Width lives inside one call. |
| Automatic prompt caching, keyed on the prefix (`cached_tokens` / `cache_read_input_tokens`). | `scan` sends a byte-identical system prompt and shared-context block to every worker (at most 8 at once), so every worker after the first reads from cache. |
| GLM-5.3-Flash is faster per token but more verbose than median. | Every worker prompt caps the answer at 12 lines in a fixed shape. |
| GLM-5.3 is weaker over long horizons; error accumulates. | R8 state carry (5 lines) and a hard round budget per lane. |
| GLM is trained toward brevity; long ceremony-heavy prompts work against it. | Numbered rules instead of behavior tables and XML scaffolding. Tables are reference data only. |

## API surface used by `scan`

| Protocol | Base URL | Notes |
|---|---|---|
| OpenAI chat completions (default) | `https://api.z.ai/api/coding/paas/v4` | `reasoning_effort` accepted; reply in `choices[0].message.content` |
| Anthropic messages | `https://api.z.ai/api/anthropic` | auto-detected from `/anthropic` in the base URL |
| DeepSeek (pin `deepseek`) | `https://api.deepseek.com` | `DEEPSEEK_BASE_URL` overrides |

`scan` finds its key with `zai_client.find_key()`: under a `deepseek` pin `DEEPSEEK_API_KEY`, `DEEPSEEK_KEY`, or the deepseek block of `~/.zcode/v2/provider_config.json`; otherwise `ZAI_API_KEY`, `Z_AI_API_KEY`, `GLM_API_KEY`, `ZHIPUAI_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, or a named key field in `~/.claude/settings.json`, `~/.zcode/v2/credentials.json` (its `api-key` field), `~/.zcode/settings.json`, `~/.zcode/auth.json` and `~/.zcode/config.json`. Override the endpoint with `--base` or `ZAI_BASE_URL`. It backs off and retries up to 4 times on 429, 5xx and network errors (`zai_client.py` `Client.call`); any other API error makes the worker answer `VERDICT: INCONCLUSIVE`.

Tiers live only in `debug_tool.py` `TIERS`: every tier names `glm-5.3-flash`, which `flash_pin.resolve_http_model` turns into `deepseek-flash` under a `deepseek` pin and into the pro id under a pro pin; `light` and `std` use effort `high`; `deep` uses effort `max`. A root cause is whatever `debug_tool.py close` prints from `.debug/experiments.json`.

On Anthropic-style routing, `haiku` maps to Flash while **both** `sonnet` and `opus` map to `glm-5.3` — so asking for `opus` over `sonnet` buys nothing and the skill never does.

## Harness notes

**ZCode.** Skill at `~/.zcode/skills/z-systematic-debugging/SKILL.md`, invoked as `$z-systematic-debugging`; agents at `~/.zcode/agents/` (user-level, no nested subagents). Foreground subagents do run in parallel, so the agent-lane fallback of `scan` is a real option here — `sh install-zcode.sh` installs the skill and copies `agents/z-debug-worker.md` verbatim into `~/.zcode/agents/` (`thoughtLevel: max`). Thinking effort is chosen per model in Settings → Model Settings.

## Failure modes and what to do

1. **The first command prints `z-systematic-debugging: handoff.py not found`.** None of the five install locations has `scripts/handoff.py`. Ask for the install dir; never guess a path.
2. **`scan` prints "no API key found".** Expected without a key. Export `ZAI_API_KEY` (or `DEEPSEEK_API_KEY` under a `deepseek` pin), or use the agent lane it prints — on ZCode, dispatch the agent-lane briefs through the `Agent` tool in ONE message (foreground subagents launched together run in parallel); or prefer narrowing the search with `probe --symbol` and `run` instead.
3. **`experiment` says "patch did not apply".** The diff was written against a different tree state. Regenerate it with `git diff > /tmp/h.diff` from the current HEAD, or use `treatment_cmd`/`env` instead of a patch.
4. **`experiment` says INCONCLUSIVE / worktree add failed.** Uncommitted submodules, a locked index, or a worktree left behind by an interrupted run. `git worktree prune`, then retry.
5. **Verdicts flip between runs.** The command is flaky. Set `runs` to at least 3/p and confirm with `stress.sh -b`. Arms with `runs` above 1 run one after another (control first), so the call takes the sum of both arms' time, not the longer one; CONFIRMED needs one arm to pass every run while the other fails.
6. **The suite is slower under `-j 64`.** The command is CPU-bound and you oversubscribed. Total processes ≤ CPU count; `probe` prints the CPU count.
7. **You are writing a fix before a `ROOT CAUSE` line exists.** Stop. That is the one rule no amount of speed buys out.
8. **A `z-debug-worker` stops before it answers.** Its turn cap ran out. The zcode install copies the agent verbatim — `thoughtLevel: max`, `maxTurns: 8`. That is enough for one command and the 12-line answer. Narrow the question or split the area into two briefs instead of asking one worker to cover both.
