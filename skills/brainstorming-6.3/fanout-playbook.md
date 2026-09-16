# Fan-out Playbook — up to 64 concurrent workers

Read this when you reach the exploration step of an architectural task
(or a large bounded one). It tells you how to partition, dispatch,
budget, and merge parallel work so the whole exploration costs one
tool round instead of dozens.

## 1. Decide the width in 10 seconds

| Task | Direct reads | Explore subagents |
| --- | --- | --- |
| Spike | 1-5 | 0 |
| Bounded, small repo | 3-10 | 0-2 |
| Bounded, large repo / unfamiliar flow | 5-10 | 2-6 |
| Architectural, single service | 5-10 | 6-16 |
| Architectural, monorepo / many subsystems | 5-10 | 16-64 |

Rule: one worker per **independent question whose answer you will
use**. Never pad to a number. Never dispatch a worker for something a
single `Read`/`Grep` in the same message answers.

## 2. Partition — one axis per worker

Pick the axis that gives non-overlapping slices; mix axes when useful:

- **By subsystem/package:** `apps/web`, `services/auth`, `packages/db`…
- **By concern across the repo:** auth, persistence, messaging, config,
  error handling, testing conventions, CI/deploy, observability.
- **By artifact type:** README/ADRs/specs, migrations, API schemas,
  recent git history (`git log --since=30.days --stat`), open TODOs.
- **By open question:** each unresolved question from your scope check
  gets a worker that looks for the repo's implicit answer.

Every worker prompt names its slice AND lists the sibling slices, so it
stays out of them.

## 3. Dispatch — one message, all calls

Use the `Agent` tool with `subagent_type: "Explore"` for read-only
lookup (fastest, cheapest), `"general-purpose"` only when the worker
must run commands (tests, build, git bisect). All calls go in the SAME
message as your direct `Read`/`Grep`/`Glob` calls. Where the harness
supports `run_in_background`, use it so results stream in while you
compose the question batch; otherwise the calls still run concurrently
inside the one message.

Model tiering (when the harness accepts `model`): shallow lookups
("where is X, how is Y done") → `haiku`; judgment lookups ("is this
pattern safe to extend, what are the hidden couplings") → `sonnet`;
competing-approach drafts and spec reviewers → `sonnet`. Keep the
expensive model for your own synthesis.

## 4. Worker prompt template

Paste, fill the brackets, keep it under 120 words. Bounded output is
what makes 64 results mergeable.

```
You are exploring ONE slice of this repo: [SLICE]. Sibling workers
cover [SIBLINGS] — do not read those areas.

Question: [ONE precise question, e.g. "How does the web app currently
authenticate API calls, and where would a new scoped token be minted?"]

Search breadth: [medium | very thorough]. Read excerpts, not whole
files, unless a file is the answer.

Return EXACTLY this, ≤150 words, no preamble:
FINDINGS: 3-6 bullets, each `path:line — fact`.
PATTERNS: conventions a new change must follow (or "none").
RISKS: couplings/gotchas for [TASK] (or "none").
UNKNOWN: what you could not determine.
```

Competing-approach workers (architectural, large repo) get instead:
"Draft approach [A|B|C] for [TASK] under constraints [...]; return
architecture (≤120 words), 3 components with one-line responsibilities,
top 3 trade-offs, what it would break." Dispatch 2-3, one per approach,
in the same message as any remaining exploration.

## 5. Merge protocol (do this in your head, not in a doc)

1. Read all results in arrival order; keep a scratch list of
   `path:line` facts you will cite in the design.
2. Conflicts between workers → resolve with one direct `Read` in your
   next message, batched with anything else that message needs.
3. Every `UNKNOWN` becomes either an assumption stated in the design
   or one of the ≤4 forking questions — never a follow-up exploration
   round unless the design cannot be drafted without it.
4. Do not summarize the exploration to the user. Show only the design
   and cite files inline.

## 6. Overlapping with human wait

Human turns are where the time goes, so each message you send should
leave machine work running:

- With the **first question batch**: background workers for the
  questions you have NOT asked (their answers become assumptions).
- With the **approaches + design** message: background approach
  workers for the runner-up option, so a "use B instead" reply costs
  one re-present, not a new exploration.
- With the **spec review gate**: nothing — the user's edits will change
  the input. Wait.
- If the harness cannot background, dispatch anyway in the same message
  as the question: the user reads and types while the calls finish,
  and their reply is queued behind your results.

## 7. Limits and hygiene

- Hard cap 64 concurrent calls per message. Above ~24, group workers
  by axis in the prompt descriptions so the task list stays readable.
- Every worker returns ≤150 words; 64 workers ≈ 10k tokens in, which
  is the price of one saved human turn. Do not raise the cap.
- Read-only always. Workers never write, never install, never commit.
- Never dispatch a worker whose result you would not cite or act on.
