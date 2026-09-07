---
name: systematic-debugging
description: Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes. Root-cause-first debugging accelerated by parallel evidence gathering — fan out up to 64 concurrent read-only probes/agents. Never fix symptoms.
---

# Systematic Debugging — Parallel Edition

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

Symptom fixes are failure. Non-negotiable under time pressure, emergencies, or "obvious" one-liners.

**Speed doctrine:** Go fast by running the investigation *in parallel*, never by skipping it.
- Phases 0–2 are **read-only** → fan out aggressively (up to 64 concurrent subagents / shell jobs).
- Phases 3–4 **mutate state** → strictly serial. One variable at a time.

## When to Use

Any technical issue: test failures, production bugs, build failures, perf problems, integration issues. ESPECIALLY when under time pressure, when a "quick fix" looks obvious, or after a fix already failed — parallel systematic debugging is faster than serial guess-and-check thrashing.

## Phase 0 — Triage (≤60s, zero code changes)

Read the complete error output once. Pick the fan-out plan:

| Signal | Plan |
|---|---|
| Error names exact file/line, single component | Dispatch P1–P3 (3 probes) |
| Multi-component chain (CI→build→sign, API→service→DB) | P1–P6 + one boundary probe per layer (8–16 probes) |
| Flaky / intermittent | P1–P6 + `references/condition-based-waiting.md` |
| Test pollution / artifacts in wrong directory | `scripts/find-polluter.sh` (scan mode, ≤64 workers) + `references/root-cause-tracing.md` |

## Phase 1 — Root Cause Investigation (parallel, read-only)

Dispatch ALL applicable probes in ONE message (parallel subagents or parallel shell jobs). Each probe is read-only, timeboxed, and returns ≤10 lines of findings + raw evidence.

- **P1 Error forensics** — full stack traces, error codes, line numbers. Errors often contain the exact answer; read them completely.
- **P2 Reproduction** — find minimal repro command; run 3× to detect flakiness. Not reproducible → gather more data, don't guess.
- **P3 Recent changes** — `git log` / `git diff` since last-known-good; new dependencies; config/env deltas.
- **P4 Boundary evidence** (multi-component) — for EACH boundary, log what enters/exits and whether env/config propagates. One probe per layer. Output reveals WHICH layer breaks.
- **P5 Data-flow trace** — where does the bad value originate? Trace backward to the source → `references/root-cause-tracing.md`.
- **P6 Environment diff** — versions, platform, env vars vs a working environment.

**Merge gate:** State in one sentence WHERE it breaks and WHY, citing probe evidence (e.g. "P4: secrets reach workflow ✓ but not build script ✗"). Can't state it? Widen the fan-out or add instrumentation — still no fixes.

## Phase 2 — Pattern Analysis (parallel, read-only)

Concurrent searches (use read-only Explore subagents):
1. **Working examples** of the same pattern elsewhere in the codebase.
2. **Reference implementation** — read COMPLETELY, every line. No skimming, no "adapting" a half-read pattern.
3. **Diff working vs broken** — list EVERY difference, however small. Never assume "that can't matter."
4. **Dependencies & assumptions** — required config, environment, versions.

## Phase 3 — Hypothesis & Test (SERIAL)

1. ONE explicit hypothesis: "X is the root cause because Y (evidence: P#)." Write it down.
2. SMALLEST possible change to test it. One variable. Never batch candidate fixes.
   - Parallelism is allowed ONLY for read-only investigation of rival hypotheses. Any state-mutating experiment runs alone.
3. Confirmed → Phase 4. Refuted → form a NEW hypothesis from evidence. DON'T stack fixes on top.
4. Don't understand something? Say "I don't understand X" and investigate more — never pretend.

## Phase 4 — Implementation (serial fix, parallel verification)

1. **Failing test first** — simplest automated reproduction. MUST exist before fixing. Use superpowers:test-driven-development.
2. **ONE fix, at the root cause** — no "while I'm here" improvements, no bundled refactoring.
3. **Verify in parallel:** full test suite sharded across workers + lint + build + original repro — all concurrent.
4. **Make the bug impossible:** add validation at every layer → `references/defense-in-depth.md`.
5. Run superpowers:verification-before-completion before claiming success.

**Fix failed?** Count attempts.
- < 3 → return to Phase 1 with the new evidence.
- **≥ 3 → STOP. This is an architecture problem, not a hypothesis problem.** Signs: each fix reveals new coupling elsewhere; fixes require massive refactoring. Question the pattern's fundamentals with your human partner before ANY further fix.

## Red Flags — any of these = STOP, return to Phase 1

"Quick fix for now, investigate later" · "Just try changing X and see" · multiple changes at once · "skip the test, I'll verify manually" · "it's probably X" without a trace · proposing fixes before tracing data flow · adapting a reference you haven't fully read · "one more fix attempt" after 2+ failures · each fix reveals a new problem elsewhere.

Partner signals meaning the same: "Is that not happening?" · "Will it show us…?" · "Stop guessing" · visible frustration.

## Rationalizations vs Reality

| Excuse | Reality |
|---|---|
| "Emergency — no time for process" | Fan Phase 1 out across parallel probes: minutes, not hours. Guess-and-check thrashing is slower and burns the incident window. |
| "Issue is simple, skip the process" | Simple bugs have root causes too; for them the process compresses to minutes. |
| "Multiple fixes at once saves time" | You can't isolate what worked. Parallelize probes, never fixes. |
| "I see the problem, let me fix it" | Seeing a symptom ≠ understanding the root cause. Trace first. |
| "One more attempt" (after 2+) | 3+ failures = wrong architecture. Question the pattern, don't fix again. |

## If Investigation Finds No Root Cause

Truly environmental/timing/external issues are rare — 95% of "no root cause" is incomplete investigation. If genuinely external: document what you ruled out, implement handling (retry/timeout/clear error), add monitoring. For timing flakiness, replace arbitrary sleeps with condition polling → `references/condition-based-waiting.md` (real case: 60%→100% pass rate, 40% faster suite).

## Toolbox (load on demand only)

- `scripts/find-polluter.sh` — parallel polluter hunt. `scan`: every test in its own isolated git worktree, ≤64 concurrent workers, finds ALL independent polluters in one round. `bisect`: k-ary prefix bisection for order-dependent pollution.
- `references/root-cause-tracing.md` — backward tracing + stack instrumentation.
- `references/defense-in-depth.md` — 4-layer validation after the fix.
- `references/condition-based-waiting.md` + `condition-based-waiting-example.ts` — kill flaky sleeps.
