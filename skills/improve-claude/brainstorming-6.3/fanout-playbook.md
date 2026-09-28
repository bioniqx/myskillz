# Fan-out Playbook — up to 64 concurrent lanes

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

To run true 64-wide fan-outs without permission stalls, the user sets in
`~/.claude/settings.json` (skill `allowed-tools` pre-approve only the
invoking turn; background lanes follow session permission rules):

```json
{ "env": { "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "64",
           "CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS": "64" },
  "permissions": { "allow": ["WebSearch", "WebFetch"] },
  "workflowSizeGuideline": "unrestricted" }
```

Wide fan-outs multiply token use (multi-agent research ≈15× a chat) and
hit rate limits sooner; width must buy a saved human turn or a better
decision.

## 1. Width in 10 seconds

| Task | T0 calls | T1 code lanes | T1 web lanes |
| --- | --- | --- | --- |
| Spike | 2-6 (incl. 2-4 web) | 0 | 0-1 |
| Bounded, small repo | 3-10 | 0-2 | 0 (T0 web instead) |
| Bounded, large repo / unfamiliar flow | 5-10 | 2-6 | 0-2 |
| Architectural, single service | 5-10 | 4-12 | 2-6 |
| Architectural, monorepo / many subsystems | 5-10 | 12-40 | 4-16 |

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

- One message: all T0 calls + all T1 `Agent` calls (≤ cap) + batched
  TaskCreate. Shared prompt block first and byte-identical across lanes
  of the same type/model so siblings can reuse the prompt cache; the
  slice-specific lines go last.
- Model per lane: `haiku` locate/lookup and single-fact checks; `sonnet`
  judgment and multi-source research; never the most expensive model for
  workers.
- **Lanes > cap:** waves. Dispatch the highest-value lanes first (the
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

Schema-shaped results merge mechanically and keep 64 outputs small.

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
