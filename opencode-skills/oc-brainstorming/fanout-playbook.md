# Fan-out Playbook — wide parallel lanes on OpenCode

Read when planning more than 8 lanes, or when a fan-out fails. Goal: the
whole exploration costs one tool round plus background time that overlaps
the human's reading time.

## 0. Capacity facts

- Lanes are background `subagent` calls (`background: true`) to the agents
  `oc-explorer` (code), `oc-researcher` (web) and `general`. They run on the
  model selected in this window; no model argument is ever passed.
- Live context prints `caps: lanes=N` (default and hard max 8; `OC_MAX_LANES` can only
  lower it). Treat it as the ceiling on lanes in flight, claim verifier and
  reviewer lanes included, and trust it over this page.
- Lanes cannot ask the user questions and must not spawn lanes. Flat
  fan-outs keep merging and cost under your control.
- Direct `read`/`grep`/`glob`/`websearch`/`webfetch` calls are not lanes
  and do not count toward the cap.
- A `shell` call that can run longer than 120 s needs `background: true`
  and a `timeout`.

## 1. Width in 10 seconds

| Task | Direct calls | Code lanes (total) | Web lanes (total) |
| --- | --- | --- | --- |
| Spike | 2-6 (incl. 2-4 web) | 0 | 0-1 |
| Bounded, small repo | 3-10 | 0-2 | 0 (direct web instead) |
| Bounded, large or unfamiliar repo | 5-10 | 2-6 | 0-2 |
| Architectural, single service | 5-10 | 4-12 | 2-6 |
| Architectural, monorepo | 5-10 | 12-40 | 4-16 |

Lane counts are totals, never concurrency: run them in waves of at most 8
in flight (section 3). Size bands from Live
context (`tracked=`): under 1k files small, 1k-20k medium, over 20k or
several manifests is a monorepo. Published research scaling rule: one
agent with 3-10 calls for a simple fact, 2-4 agents with 10-15 calls for a
comparison, 10+ only for genuinely broad questions. The known failure is
spawning dozens of agents for a simple query. Do not.

Wide fan-outs multiply token use and hit quota sooner. Width must still
buy a saved human turn or a better decision.

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

Every lane brief names its slice AND the sibling slices so it stays out.
Vague boundaries are the main cause of duplicated work between lanes.

## 3. Dispatch

- One message: all direct calls + all lane `subagent` calls (≤ cap). State
  the call count first (SKILL.md R4) and then make every one of them.
- Tools not loaded yet (`websearch`, `webfetch`, `question`): load them
  first. Call them in this message only if they are already available,
  otherwise in the next round, never as a serial chain.
- The agent body is the shared prefix and is byte-identical across lanes of
  the same agent. Keep the brief short and put slice-specific lines last.
- Every agent names its output labels and a word cap, so eight or more
  outputs stay small enough to merge in one turn.
- **Lanes over the cap → waves.** Dispatch the highest-value lanes first
  (the ones that can change the approach set), then refill in batches as
  completions arrive. Each wake-up costs a main-model turn, so never
  refill one at a time.

## 4. Failure handling

- A rejected dispatch → do not retry the call unchanged. The cap in Live
  context was wrong or other lanes are running; continue in waves.
- Background `subagent` unavailable → run the briefs as foreground
  `subagent` calls to `general`, a few per message.
- Lane denied `websearch`/`webfetch` → do its 1-2 decisive fetches
  yourself.
- Rate limit (HTTP 429 or `provider.rate-limit`) or empty result →
  re-dispatch once, only the lanes whose answer the design still needs.
  A lane that fails again is down: convert its question to an assumption.
- Lane stopped at its step limit with partial output → use what it
  returned; re-dispatch a narrower slice only if the design needs it.
- Lane returns off-contract prose → take what is usable. Do not re-run it
  for formatting.

## 5. Merge protocol (in your head, not a doc)

1. Read results in arrival order; keep a scratch list of `path:line` facts
   and `claim — URL — date`.
2. Conflicts between lanes or sources → one direct check (`read`, or
   `webfetch` asking for the exact passage) batched into your next
   message. Prefer the newer primary source that matches our version.
3. UNKNOWN or UNVERIFIED → an assumption, or one of the ≤4 questions. A
   new exploration round only if the design cannot be drafted without it.
4. Do not summarize the exploration to the user. Show the design with
   inline citations.

## 6. Overlap with human wait

| Message you send | Leave running |
| --- | --- |
| Questions first (split) | all code + web lanes; unasked questions become assumptions |
| Design message | claim verifier; runner-up approach |
| Spec review gate | nothing — the user's edits change the input |
