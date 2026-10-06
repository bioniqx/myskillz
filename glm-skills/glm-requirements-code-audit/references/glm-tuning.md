# GLM-5.3 tuning — what was verified, what it changed

Verified 2026-09-18 against z.ai's own model pages, the ZCode docs and the OpenCode docs.

## Model facts this design rests on

| Fact | Consequence in this skill |
|---|---|
| `glm-5.3` and `glm-5.3-flash`: 1M context, 128K max output | retrieval can be generous; context is never the binding constraint, latency is |
| Reasoning is **always on**; `thinking.type` accepts only `enabled` | no "thinking off" path exists; there is nothing to disable |
| `reasoning_effort` is `low` \| `high` \| `max`, default `max` | **there is no `medium`** — the old agent files pinned `effort: medium`, which is not a GLM value. Tiers use low/high/max only |
| z.ai recommends `thinking.clear_thinking: false` | sent on every request |
| Context caching is supported | one byte-identical prefix per wave; the `cache_read_input_tokens` figure is printed by `run` |
| On the Anthropic-compatible route, `haiku` → `glm-5.3-flash` and **both `sonnet` and `opus`** → `glm-5.3` | asking for `opus` costs more for the same model. The api lane names models outright; the agent lane uses `haiku`/`sonnet` only where a harness demands an alias |
| GLM emits few parallel tool calls per turn | an agentic search loop is the wrong place for this work → retrieval moved into Python |
| Flash is more verbose than median | `max_tokens` is capped per tier and every prompt demands JSON only |
| GLM is trained toward brevity; long prompts fight the training | SKILL.md and every system block are numbered rules, no XML ceremony, no behaviour tables |

## Harness facts

| Harness | Fact | Consequence |
|---|---|---|
| OpenCode v1 | dispatches subagents **sequentially** (`tasks.pop()` + await; issues #14195 / #29638 open, PR #47107 proposes a parallel task tool); no `background` param | an 8-subagent fan-out is nearly worthless there → the api lane is the fast path |
| OpenCode v2 | `subagent` tool takes `background: true`; live probe (2026-09-25) ran two background children concurrently — real parallelism even at one call per turn, detectable by a `background` param on your subagent tool; interactive sessions only, since headless `opencode run` can exit before children report | the api lane stays the fast path for this skill's own fan-out, but the agent lane's fallback dispatch is no longer serial here |
| OpenCode | reads only `name`, `description`, `license`, `compatibility`, `metadata` from skill frontmatter; ignores the rest; no `allowed-tools`, no command injection | no `allowed-tools` field; permissions are configured in the harness, not the skill |
| OpenCode | finds skills in `.opencode/skills/`, `~/.config/opencode/skills/`, `.claude/skills/`, `~/.claude/skills/`, `.agents/skills/`, `~/.agents/skills/` | drop-in anywhere; `setup --harness opencode` uses the global path |
| OpenCode | agents in `~/.config/opencode/agents/`, `mode: all` on v1 (a `mode: subagent` agent is silently swapped for the default `build` agent by `opencode run --agent`), `mode: subagent` + `variant: <effort>` on v2 (honored when the agent is dispatched through the `subagent` tool; `opencode run --agent` still gets effort from the `--model <id>#<effort>` suffix, since an explicit `--model` overrides the agent's own model), `model: provider/model-id` | `opencode/agents/*.md` holds neutral sources rendered into that dialect at install time |
| ZCode | subagents launched **together run in parallel**; they cannot spawn nested subagents | the agent lane is a real fallback here |
| ZCode | agents at `~/.zcode/agents/<name>.md`; fields `name`, `description`, `model`, `thoughtLevel`, `tools`/`disallowedTools`, `maxTurns`, `injectAgentsMd`, `mcpServers`, `color`. **No `effort`, no `permissionMode`, no haiku/sonnet aliases** | `agents/zcode/*.md` uses real GLM ids + `thoughtLevel` |
| ZCode | skills at `~/.zcode/skills/<name>/SKILL.md`, invoked `$glm-requirements-code-audit`; a description over 1024 chars **drops the skill**; per-turn trigger metadata is a description excerpt of up to 250 chars (the WHEN-clause sits up front); a body over 100KB is truncated when loaded, not dropped | description reordered with the WHEN-clause first; description measured at 920 chars |
| OpenCode | no hook system | the guard hooks and `.claude-plugin/` were removed. On the api lane the enforcement is structural instead: the retriever cannot return `*.md`, `docs/`, README-like files or anything under `.git/`, and the model has no tools at all |
| ZCode | user-level hooks exist, merged into `~/.zcode/cli/config.json` | this skill installs none; the api lane's structural enforcement carries the rules here anyway |

## What changed from the Claude Code edition

1. **Parallelism moved out of the model's turn.** `audit.py run` opens up to 8 threads and issues one request
   per requirement. Capped at **8 concurrent requests** (the provider limit): 80 requirements take 10 rounds
   of 8 (about 4 s at 0.4 s latency, computed, not re-measured), with **2 unique prompt prefixes** for the whole run (one judge, one verify).
2. **Retrieval became deterministic.** Six independent strategies in pass 1 (literal hints, identifier case
   variants, symbol index, route index, path match, spec keywords) and four disjoint ones in pass 2
   (model-suggested queries, symbol prefix, tests-only, config/migrations/schemas). Every query is recorded, so
   "two independent search passes" is a fact in the file rather than a claim in a prompt.
3. **A deterministic checker sits between the model and the report.** Invented paths, line ranges past end of
   file, a MATCHED with no evidence, prose documentation cited as evidence — each is rejected and handed back as
   the repair prompt, up to twice. In testing, a hallucinated `src/auth/totp.py:900-950` was caught and repaired
   without the lead seeing it.
4. **Pipeline: 10+ lead turns → 4.** `brief` (init + index + map + spec + schema), your checklist, `run`
   (retrieve + judge + repair + second pass + verify + merge), `queue`/`adjudicate` + `finalize`
   (report + gate + close).
5. **Request-shape discovery.** If the gateway refuses `reasoning_effort`, `thinking` or `cache_control`, the
   client drops that one field, retries without spending a retry, and remembers the working shape for the rest
   of the run. `doctor --ping` prints the shape that was accepted.

6. **Gate parity with the Claude Code edition.** `check` applies the original gate: a non-MATCHED item must be
   verified or adjudicated, a verifier disagreement must be adjudicated, a MISSING needs a second pass and
   recorded searches, citations must exist and must not be prose or `.git/`, and the plan must cover every
   discrepancy (warnings: effort, P0 anchors, MATCHED with low confidence or high stakes never verified). The
   adjudication queue and the seeded spot-check follow the original rule; the checker-rejected rows stay in the
   queue because only this edition has a checker. A verify batch holds at most 3 items on the agent lane.

## Failure modes seen with GLM on this task

1. **Fabricated `path:lines`.** The most common bad answer, and the reason the checker verifies every citation
   against the real file before it can reach the report.
2. **Answering MISSING when the retrieval simply looked in the wrong place.** Countered by `more_queries`: a
   MISSING or low-confidence answer must propose search terms, which the script then actually runs.
3. **Prose around the JSON.** Handled by brace-scanning extraction, not by asking more firmly.
4. **Verbosity on Flash.** Handled by a per-tier `max_tokens` cap and "JSON only" in the system block.
5. **Effort inheritance.** Not possible on the api lane — effort is set per request by the tier, never inherited
   from the session.

## Not verified

- GLM-5.3's real per-turn parallel-tool-call ceiling. It does not matter here: the api lane never asks the model
  to make more than one call.
- Whether the z.ai gateway honours Anthropic-style `cache_control` breakpoints or applies its own automatic
  caching. Either way the prefix is byte-identical, which is what caching needs; `run` prints the cached-token
  count so the effect is observable.
- ZCode has no public headless CLI, so its agent lane was reviewed against the documented frontmatter rather
  than executed in CI.
