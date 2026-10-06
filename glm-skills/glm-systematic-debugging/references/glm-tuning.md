# GLM-5.3 / GLM-5.3-Flash tuning — why this skill is shaped the way it is

Read this when something is slow, when `scan` falls back to the agent lane, or when you are porting the skill to another harness.

## Model facts this design depends on

| Fact | Consequence in the skill |
|---|---|
| Thinking cannot be disabled. `thinking.type` only accepts `enabled`; a request to disable it is treated as `low`. | No "turn thinking off" advice anywhere. Only the effort level is tuned. |
| `reasoning_effort` = `low` \| `high` \| `max`, default `max`. | R7 effort ladder; `scan` sets it per worker so mechanical fan-out never pays for `max`. |
| Both models: 1M context, 128K output. | Long `probe` output is affordable; verbosity, not context, is the risk — every tool caps its output. |
| Few tool calls per model turn (2 observed in public testing), even where the API advertises parallel tool calls. | R1: never rely on batching tool calls. Width lives inside one call. |
| Automatic prompt caching, keyed on the prefix (`cached_tokens` / `cache_read_input_tokens`). | `scan` sends a byte-identical system prompt and shared-context block to every worker (at most 8 at once), so every worker after the first reads from cache. |
| Flash is faster per token but more verbose than median. | Every worker prompt caps the answer at 12 lines in a fixed shape. |
| Weaker over long horizons; error accumulates. | R8 state carry (5 lines) and a hard round budget per lane. |
| Trained toward brevity; long ceremony-heavy prompts work against it. | Numbered rules instead of behavior tables and XML scaffolding. Tables are reference data only. |

## API surface used by `scan`

| Protocol | Base URL | Notes |
|---|---|---|
| OpenAI chat completions (default) | `https://api.z.ai/api/coding/paas/v4` | `reasoning_effort` accepted; reply in `choices[0].message.content` |
| Anthropic messages | `https://api.z.ai/api/anthropic` | auto-detected from `/anthropic` in the base URL |

`scan` finds a key from `ZAI_API_KEY`, `GLM_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, or from a named key field in `~/.claude/settings.json`, `~/.config/opencode/opencode.json`, `~/.config/opencode/auth.json`, `~/.zcode/v2/credentials.json` (v2; its `api-key` field), `~/.zcode/*.json`. Override the endpoint with `--base` or `ZAI_BASE_URL`. It retries once on 429/5xx, and retries once without `reasoning_effort` if the gateway rejects that field.

Tiers: `--tier light` → `glm-5.3-flash` / `low`; `--tier std` (default) → `glm-5.3-flash` / `high`; `--tier deep` → `glm-5.3` / `max`.

On Anthropic-style routing, `haiku` maps to Flash while **both** `sonnet` and `opus` map to `glm-5.3` — so asking for `opus` over `sonnet` buys nothing and the skill never does.

## Harness notes

**OpenCode.** Skills are read from `.opencode/skills/`, `~/.config/opencode/skills/`, `.claude/skills/`, `~/.claude/skills/`, `.agents/skills/`, `~/.agents/skills/`; only `name`, `description`, `license`, `compatibility` and `metadata` are parsed and unknown keys are ignored; `description` must be 1–1024 characters. The skill installs as `glm-systematic-debugging` (the `name:` field carries the `glm-` prefix). The R0 bootstrap also checks `$OPENCODE_CONFIG_DIR/skills/`. `/glm-debug` sets `S={{SKILL_DIR}}/scripts` and loads the skill with `$ARGUMENTS`; the neutral `glm-debug-worker` agent (`opencode/agents/glm-debug-worker.md`) is the agent-lane fallback investigator, and SKILL.md names it for every agent-lane dispatch. On v1, subagent tasks are dispatched one at a time, so a request for 64 parallel agents becomes 64 sequential runs — this is the single biggest reason the fan-out in this skill lives inside `debug_tool.py` instead of in subagents. On v2, the `subagent` tool takes `background: true`; dispatching each worker that way, one call after another without waiting, gives real parallelism from a single turn (interactive sessions only — a headless `opencode run` can exit before background children report). Detect v2 by checking whether your `subagent` tool has a `background` param. `python3 $S/debug_tool.py setup --harness opencode` prints a `zai-coding-plan` provider block with `variants` `low`/`high`/`max` for `glm-5.3` and `glm-5.3-flash`; without it `#max` fails with "Variant unavailable".

**ZCode.** Skill at `~/.zcode/skills/glm-systematic-debugging/SKILL.md`, invoked as `$glm-systematic-debugging`; agents at `~/.zcode/agents/` (user-level, no nested subagents). Foreground subagents do run in parallel, so the agent-lane fallback of `scan` is a real option here — `sh install-zcode.sh` installs the skill and rewrites the `glm-debug-worker` frontmatter (`thoughtLevel: low`, `maxTurns` instead of `steps`) into `~/.zcode/agents/`. Thinking effort is chosen per model in Settings → Model Settings.

**Claude-compatible harnesses.** `setup --harness claude` prints the settings block: z.ai base URL, Flash as the small model, and a concurrent-subagent limit of 8 (the most the provider allows at once).

## Failure modes and what to do

1. **Every command says `S=` is empty.** The bootstrap loop found no `debug_tool.py`. Run `find ~ -name debug_tool.py -path '*glm-systematic-debugging*' 2>/dev/null | head -1` once and use that path.
2. **`scan` prints "no API key found".** Expected without a key. Export `ZAI_API_KEY`, or use the agent lane it prints — on OpenCode v1 (subagents serialize), prefer narrowing the search with `probe --symbol` and `run` instead; on OpenCode v2 in an interactive session, dispatch the agent-lane briefs through the `subagent` tool with `background: true` for real parallelism instead.
3. **`experiment` says "patch did not apply".** The diff was written against a different tree state. Regenerate it with `git diff > /tmp/h.diff` from the current HEAD, or use `treatment_cmd`/`env` instead of a patch.
4. **`experiment` says INCONCLUSIVE / worktree add failed.** Uncommitted submodules, a locked index, or a worktree left behind by an interrupted run. `git worktree prune`, then retry.
5. **Verdicts flip between runs.** The command is flaky. Set `runs` to at least 3/p and confirm with `stress.sh -b`. Arms with `runs` above 1 run one after another (control first), so the call takes the sum of both arms' time, not the longer one; CONFIRMED needs one arm to pass every run while the other fails.
6. **The suite is slower under `-j 64`.** The command is CPU-bound and you oversubscribed. Total processes ≤ CPU count; `probe` prints the CPU count.
7. **You are writing a fix before a `ROOT CAUSE` line exists.** Stop. That is the one rule no amount of speed buys out.
8. **A `glm-debug-worker` stops before it answers.** Its turn budget ran out. The zcode install carries it as `maxTurns: 12` (ZCode has no `steps` agent key; the OpenCode agent file sets `steps: 12`). Enough for a 12-line investigation plus one `stress.sh` arm. Narrow the question or split the area into two briefs instead of asking one worker to cover both.
