# Lane Templates and Moved Rules

Read when T1 lanes are planned. Every lane passes `model` explicitly.

## Lane prompts (fill brackets; keep the shared block first and identical across lanes so siblings reuse the prompt cache)

**Code lane** (`subagent_type: "Explore"` with `model: "haiku"` for
locate/lookup or `model: "sonnet"` for judgment; `general-purpose` only
if it must run commands):

```
Read-only exploration for: [TASK, one line]. Repo root: [ROOT]. Today: [DATE].
Rules: stay in your slice; read excerpts, not whole files; make all
independent searches in one parallel batch; never write, install, commit,
or spawn agents; stop once the question is answered.
Return ≤150 words, no preamble:
FINDINGS: 3-6 bullets `path:line — fact`
PATTERNS: conventions a change must follow | none
RISKS: couplings/gotchas for the task | none
UNKNOWN: what you could not determine
---
Slice: [SLICE]. Siblings cover (stay out): [SIBLINGS].
Question: [ONE precise question]
```

**Web lane** (`subagent_type: "general-purpose"`, `model: "sonnet"`;
`haiku` for single-fact checks):

```
Web research for a design decision: [TASK, one line]. Today: [DATE].
Our stack/versions: [FROM LIVE CONTEXT].
Rules: batch 1 = 2-4 query variants in parallel (broad); batch 2 = fetch
the best primary pages in parallel; ≤6 tool calls total (hard stop); stop when a
batch adds nothing new. Use only WebSearch/WebFetch for web content; on a
failed or denied fetch switch source, never retry it. Source tiers:
A = official docs, changelogs/release notes, specs/RFCs, maintainer
repos/issues, package registries, peer-reviewed papers; B = maintainer or
company engineering blogs, benchmarks with methodology; C = forums/Q&A
(signal only, never sole support). Skip undated pages, SEO/listicle
farms, AI-written summaries. Record date and applicable version for each
claim; flag claims older than 18 months on fast-moving tech or not
matching our version. A claim that could change the recommendation needs
1 A or 2 independent B sources with a ≤25-word verbatim quote. Generic
queries only — no proprietary code, internal names, secrets, customer
data. No writes, no agents.
Return ≤200 words, no preamble:
ANSWER: 1-2 sentences
CLAIMS: 2-6 lines `claim — tier — URL — date — "quote"`
CONFLICTS: where sources disagree | none
VERSION_NOTES: our version vs latest | n/a
UNVERIFIED: claims lacking support | none
---
Angle: [ANGLE]. Sibling angles (skip): [SIBLINGS].
Question: [ONE precise question]
```

**Merge:** keep a scratch list of `path:line` facts and cited claims.
Conflicts → one T0 check in your next round. Every UNKNOWN or UNVERIFIED
becomes an assumption or one of the ≤4 questions — never a new
exploration round unless the design can't be drafted without it. A lane
denied web access → do its 1-2 decisive fetches yourself as T0. Don't
narrate the exploration; show the design and cite inline.

## Red flags (continued)

| Thought | Reality |
| --- | --- |
| "Let me look around first, then decide what to read" | Live context already lists files and versions. Read everything plausible in round 1. |
| "I already know the best practice" | Training data is stale. Parallel searches cost seconds; a wrong library costs days. |
| "The fetch failed, let me try curl / gh" | Switch to a registry JSON or raw URL via WebFetch, or drop it. Never retry a denial. |
| "A blog says so" | Check tier, date, and version. One secondary source is not evidence. |
| "More sources = more accurate" | Accuracy drops as tool calls grow. Budget; verify only load-bearing claims. |
| "Spawn 64 because I can" | One lane per question you will act on. Respect the cap. |
| "A subagent for one search" | A T0 call in the same round is an order of magnitude faster. |
| "I'll ask to be safe" | A vetoable assumption costs zero turns; a question costs one. |
| "It grew, but I'm almost done" | Hidden complexity upgrades the path. Stop and say so. |
| "The spike worked, so I'll keep the code" | A spike's output is an answer. Keeping code is a new request — classify it. |

## Width and model tiering (full text)

4. **Width.** One lane per question whose answer you will cite or act on;
   never pad. Ceiling 64 concurrent lanes; T1 agents never exceed the
   subagent cap in Live context (the harness rejects the next one and
   says not to retry). More lanes than the cap → dispatch the lanes that
   can change the approach set first, then refill in batches as
   completions arrive. Details: `fanout-playbook.md` (read when planning
   >8 T1 lanes or after a fan-out failure).
5. **Model tiering** (pass `model` explicitly — Explore inherits the main
   model): `haiku` for locate/lookup and single-fact web checks; `sonnet`
   for judgment (hidden couplings, source quality, approach drafts, claim
   verification); the main model only for synthesis.
