# Fan-out Playbook — Claude width = min(live cap, 12)

Read when planning more than 8 T1 lanes, or when a fan-out fails. Goal:
the whole exploration costs one tool round plus background time that
overlaps the human's reading time.

## 0. Capacity facts (Claude Code, verified 2026-09)

- Subagents: 20 running at once by default; the 21st `Agent` call fails
  with "Concurrent subagent limit reached" and the error tells Claude not
  to retry. Raise with `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`.
- Workflow runtime: up to 16 concurrent agents (fewer when fewer CPUs are
  available); raise with `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS`
  (1-256, v2.1.269+). Needs explicit user opt-in; runs in the background.
  Only worth it when its cap exceeds the subagent cap.
- Subagents run in the background in interactive sessions; results return
  as completion notifications. Subagents have WebSearch/WebFetch, but not
  AskUserQuestion or Workflow. They may nest up to 3 levels — don't:
  flat fan-outs keep merging and cost under your control.
- Direct T0 calls (Read/Grep/Glob/WebSearch/WebFetch) are not subagents
  and don't count toward the subagent cap.

The cap in Live context (`caps: subagents=`) is the real limit; plan
Claude width as min(independent questions, that cap minus a reserve for
other running agents, 12). The soft ceiling of 12 holds even when the cap
is higher: each agent pays fixed token overhead, so fewer fuller lanes
beat many tiny ones. Anything over the ceiling runs in waves.

To let background web lanes run without permission stalls, the user adds
to `~/.claude/settings.json` (skill `allowed-tools` pre-approve only the
invoking turn; background lanes follow session permission rules):

```json
{ "permissions": { "allow": ["WebSearch", "WebFetch"] } }
```

Wide fan-outs multiply token use (multi-agent research ≈15× a chat) and
hit rate limits sooner; width must buy a saved human turn or a better
decision.

## 1. Width in 10 seconds

| Task | T0 calls | T1 code lanes | T1 web lanes |
| --- | --- | --- | --- |
| Spike | 2-6 (incl. 2-4 web) | 0 | 0-1 |
| Bounded, small repo | 3-10 | 0-2 | 0 (T0 web instead) |
| Bounded, large repo / unfamiliar flow | 5-10 | 2-4 | 0-2 |
| Architectural, single service | 5-10 | 4-8 | 2-4 |
| Architectural, monorepo / many subsystems | 5-10 | 8-12 | 4-8 |
| Broad web landscape (new domain) | 4-8 | 0-4 | 4-8 |

Lane counts are Claude and opencode lanes together; totals above 12 live
Claude `Agent` lanes (or above the cap) run in waves. opencode lanes are
bounded separately (per-tier `max_parallel` AND the shared pool).

Size bands from Live context (`tracked=`): <1k files small, 1k-20k medium,
>20k or several manifests = monorepo. Anthropic's own research scaling
rule: 1 agent with 3-10 calls for a simple fact, 2-4 agents with 10-15
calls for a comparison, 10+ only for genuinely broad questions. Its known
failure is spawning dozens of agents for a simple query — don't.

## 2. Partition — one axis per lane, no overlap

Code axes: by subsystem/package; by concern (auth, persistence,
messaging, config, errors, tests, CI/deploy, observability); by artifact
(README/ADRs/specs, migrations, API schemas, `git log --since=30.days
--stat`, TODOs); by open question from the scope check.

Web axes (pick only those the decision needs):
1. Official docs + changelog for the key tech at OUR version and at
   latest — breaking changes, deprecations, new built-ins that replace
   custom code.
2. Current recommended pattern for the problem (maintainer guides, RFCs,
   reference architectures).
3. Pitfalls: open/closed issues, security advisories/CVEs, migration
   reports.
4. Alternatives landscape: candidates, maintenance signals (last release
   date, release cadence, open-issue trend, license) — stars are not
   quality.
5. Performance/cost evidence: benchmarks with methodology, provider
   limits and pricing pages (always dated).

Every lane prompt names its slice AND the sibling slices so it stays out.
Vague boundaries are the main cause of duplicated work between lanes.

## 3. Dispatch

- One message: all T0 calls + all T1 `Agent` calls (≤ min(cap, 12)) + batched
  TaskCreate + all opencode-lane calls, dispatched as background
  shell commands (`bslane.py code|web --id <id> --role
  locate|explore|fact|research ...`, one call per lane). Shared prompt
  block first and byte-identical across lanes of the same type/model so
  siblings can reuse the prompt cache; the slice-specific lines go last.
- Deferred tools (WebSearch/WebFetch/AskUserQuestion/TaskCreate):
  ToolSearch them first. Call them in this message only if they are
  already loaded, otherwise in the next round.
- Model per lane: `haiku` locate/lookup and single-fact checks; `sonnet`
  judgment and multi-source research; never the most expensive model for
  workers.
- opencode lanes: never launch more than a tier's `max_parallel`
  lanes at once AND never more than the shared pool across all tiers
  together (default 6, `HYBRID_OPENCODE_POOL` up to 8; `bslane.py`
  holds a tier slot and a pool slot per running lane) (see the `opencode:` context line for the routed tier
  per role); these lanes are plain background shell processes, so they
  do not count toward the subagent cap or the workflow cap. A printed
  fallback line is acted on by launching exactly the named Claude
  lane, once.
- **Claude lanes > min(cap, 12):** waves. Dispatch the highest-value lanes first (the
  ones that can change the approach set), then refill in batches as
  completions arrive (each wake-up costs a main-model turn, so don't
  refill one at a time). Use one `Workflow` instead only when the workflow
  cap exceeds the subagent cap and the user explicitly opted in.
- **T2 Workflow pattern** (opt-in only; load the `workflow-authoring`
  skill first if available — it is the authoritative script reference):

```js
export const meta = { name: 'brainstorm-fanout', description: 'Parallel code + web lanes for a design decision', phases: [{ title: 'Explore' }] }
const LANE = { type: 'object', required: ['answer','claims','unknown'], properties: {
  answer: { type: 'string' }, claims: { type: 'array', items: { type: 'string' } },
  unknown: { type: 'array', items: { type: 'string' } } } }
const lanes = args.lanes  // [{ label, prompt, model }]
const results = await parallel(lanes.map(l => () =>
  agent(l.prompt, { label: l.label, phase: 'Explore', model: l.model, schema: LANE })))
return results.filter(Boolean)
```

Schema-shaped results merge mechanically and keep many outputs small.

## 4. Failure handling

- "Concurrent subagent limit reached" → don't retry the call; the cap in
  Live context was wrong or other agents are running — continue in waves.
- Web lane denied WebSearch/WebFetch (background permission rules) → do
  its 1-2 decisive fetches yourself as T0; suggest the settings above.
- Rate limit / 429 / empty result → halve the remaining wave; re-dispatch
  only lanes whose answer the design still needs; otherwise convert to an
  assumption.
- Lane stopped at its turn limit with partial output → continue it with
  `SendMessage` (keeps its context) instead of spawning a fresh lane.
- A lane that returns off-contract prose → take what's usable; don't
  re-run it for formatting.
- opencode lane fallback reasons: spawn, crash, stall, timeout,
  throttle, busy, format, grounding, cooldown, config → launch exactly
  the Claude lane printed on the line that follows, once; never retry
  the opencode call itself.
- throttle puts that tier into cooldown instead of halving the wave:
  every lane still queued for that tier during the cooldown window
  falls back to Claude immediately; lanes routed to other tiers keep
  dispatching normally.

## 5. Merge protocol (in your head, not a doc)

1. Read results in arrival order; keep a scratch list of `path:line`
   facts and `claim — URL — date`.
2. Conflicts between lanes or sources → one T0 check (Read or WebFetch
   with "quote the exact passage") batched into your next message. Prefer
   the newer primary source that matches our version.
3. UNKNOWN / UNVERIFIED → assumption or one of the ≤4 questions. New
   exploration round only if the design cannot be drafted without it.
4. Don't summarize the exploration to the user; show the design with
   inline citations.

## 6. Overlap with human wait

| Message you send | Leave running |
| --- | --- |
| Questions first (split) | all code + web lanes; unasked questions become assumptions |
| Design message | claim verifier; spec pre-draft |
| Spec review gate | nothing — the user's edits change the input |
