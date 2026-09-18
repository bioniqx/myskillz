# Fan-out Playbook — up to 64 concurrent lanes on GLM

Read when planning more than 8 lanes, or when a fan-out fails. Goal: the
whole exploration costs one tool round plus background time that overlaps
the human's reading time.

## 0. Capacity facts

- Subagents: 20 running at once by default. The 21st `Agent` call fails
  with "Concurrent subagent limit reached" and tells you not to retry.
  Raise with `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`.
- Workflow runtime: up to 16 concurrent agents by default (fewer on fewer
  CPUs); raise with `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS`. Needs
  explicit user opt-in. Worth it only when its cap beats the subagent cap.
- Subagents run in the background in interactive sessions; results arrive
  as completion notifications. They have WebSearch/WebFetch but not
  AskUserQuestion or Workflow. They may nest three levels — do not. Flat
  fan-outs keep merging and cost under your control.
- Direct Read/Grep/Glob/WebSearch/WebFetch calls are not subagents and do
  not count toward the cap.
- Live context prints the caps actually in force. Trust it over this page.

Settings for a true 64-wide fan-out are in `glm-tuning.md` §2. Skill
`allowed-tools` pre-approve only the invoking turn; background lanes
follow session permission rules, which is why WebSearch/WebFetch belong
in the settings allow-list.

## 1. Width in 10 seconds

All counts assume Flash lanes (SKILL.md R2). Halve them for any lane you
put on GLM-5.3, and never run more than 2 of those.

| Task | Direct calls | Code lanes | Web lanes |
| --- | --- | --- | --- |
| Spike | 2-6 (incl. 2-4 web) | 0 | 0-1 |
| Bounded, small repo | 3-10 | 0-2 | 0 (direct web instead) |
| Bounded, large or unfamiliar repo | 5-10 | 2-6 | 0-2 |
| Architectural, single service | 5-10 | 4-12 | 2-6 |
| Architectural, monorepo | 5-10 | 12-40 | 4-16 |

Size bands from Live context (`tracked=`): under 1k files small, 1k-20k
medium, over 20k or several manifests is a monorepo. Published research
scaling rule: one agent with 3-10 calls for a simple fact, 2-4 agents with
10-15 calls for a comparison, 10+ only for genuinely broad questions. The
known failure is spawning dozens of agents for a simple query. Do not.

Wide fan-outs multiply token use and hit quota sooner. Flash's 3× quota
and ~9× lower price is what makes 20-40 lanes affordable — the same
fan-out on GLM-5.3 lanes is not. Width must still buy a saved human turn
or a better decision.

## 2. Partition — one axis per lane, no overlap

Code axes: by subsystem or package; by concern (auth, persistence,
messaging, config, errors, tests, CI/deploy, observability); by artifact
(README/ADRs/specs, migrations, API schemas, `git log --since=30.days
--stat`, TODOs); by open question from the scope check.

Web axes — pick only those the decision needs:

1. Official docs + changelog for the key tech at OUR version and at
   latest: breaking changes, deprecations, new built-ins that replace
   custom code.
2. The current recommended pattern for the problem (maintainer guides,
   RFCs, reference architectures).
3. Pitfalls: open and closed issues, security advisories and CVEs,
   migration reports.
4. Alternatives landscape: candidates and maintenance signals — last
   release date, release cadence, open-issue trend, license. Stars are
   not quality.
5. Performance and cost evidence: benchmarks with methodology, provider
   limits and pricing pages, always dated.

Every lane prompt names its slice AND the sibling slices so it stays out.
Vague boundaries are the main cause of duplicated work between lanes.

## 3. Dispatch

- One message: all direct calls + all `Agent` calls (≤ cap) + batched
  TaskCreate. State the call count first (SKILL.md R4) and then make
  every one of them.
- Shared prompt block first and byte-identical across lanes of the same
  type and model, so siblings hit the prefix cache. Slice-specific lines
  last.
- Model per lane: `haiku` (Flash) by default; `sonnet` (GLM-5.3) for at
  most 2 lanes whose conclusion picks the approach.
- **Lanes over the cap → waves.** Dispatch the highest-value lanes first
  (the ones that can change the approach set), then refill in batches as
  completions arrive. Each wake-up costs a main-model turn, so never
  refill one at a time. Use `Workflow` instead only when the workflow cap
  exceeds the subagent cap and the user explicitly opted in.
- **Workflow pattern** (opt-in only; load the `workflow-authoring` skill
  first if available — it is the authoritative script reference):

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

Schema-shaped results merge mechanically and keep 64 outputs small —
worth more on GLM than on Claude, because Flash is verbose by default.

## 4. Failure handling

- "Concurrent subagent limit reached" → do not retry the call. The cap in
  Live context was wrong or other agents are running; continue in waves.
- Lane denied WebSearch/WebFetch (background permission rules) → do its
  1-2 decisive fetches yourself; suggest the settings in `glm-tuning.md`.
- Rate limit, 429, or empty result → halve the remaining wave; re-dispatch
  only lanes whose answer the design still needs; otherwise convert to an
  assumption.
- Lane stopped at its turn limit with partial output → continue it with
  `SendMessage`, which keeps its context, instead of spawning a fresh one.
- Lane returns off-contract prose (common on Flash) → take what is usable.
  Do not re-run it for formatting.
- Tool-call parse errors from a self-hosted GLM server → a serving-stack
  bug, not a prompt bug. See `glm-tuning.md` §4.

## 5. Merge protocol (in your head, not a doc)

1. Read results in arrival order; keep a scratch list of `path:line` facts
   and `claim — URL — date`.
2. Conflicts between lanes or sources → one direct check (Read, or
   WebFetch asking for the exact passage) batched into your next message.
   Prefer the newer primary source that matches our version.
3. UNKNOWN or UNVERIFIED → an assumption, or one of the ≤4 questions. A
   new exploration round only if the design cannot be drafted without it.
4. Do not summarize the exploration to the user. Show the design with
   inline citations.

## 6. Overlap with human wait

| Message you send | Leave running |
| --- | --- |
| Questions first (split) | all code + web lanes; unasked questions become assumptions |
| Design message | claim verifier; spec pre-draft; runner-up approach |
| Spec review gate | nothing — the user's edits change the input |
