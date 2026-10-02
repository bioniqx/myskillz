# Report format

`audit.py report` (and `finalize`) renders `.audit/requirements-code-audit.md` from the checklist, findings,
verdicts, adjudications and `plan.jsonl`. Headings are localised (`en`, `vi` built in; `--headings my-lang.json`
overrides any key for other languages). The free text you write — plan entries, adjudication notes, checklist
text — must already be in the spec's language.

```markdown
# Requirements ↔ Code Audit

- Source of truth: `<file(s)>`
- Codebase: `<root>`
- Date: <date>
- Method: <lane, models, threads, retrieval engine, size of the second pass>
- Constraints honored: no git history; no documentation other than the source of truth; codebase not modified.

## Summary
- Total requirements: N
- ✅ Matched: a · ⚠️ Partial: b · ❌ Missing: c · ⛔ Conflict: d · ❓ Unverifiable: e
- Alignment: a / N

## Traceability
| ID | Requirement | Strength | Status | Evidence (path:lines) | Notes |

## Discrepancies (detail)
### ⚠️ PARTIAL REQ-007 — <short title>
- Requirement: …
- Finding: `path:lines` — what the code does  (or: MISSING — Searched: <the queries actually run>)
- Why it diverges: adjudication note / verifier reason / first-pass note

## Remediation plan
### P0
1. **<title>** (REQ-007) — Effort S
   - Current: … / Target: … / Fix: … / Depends on: … / Risk: …
### P1 … ### P2 …

## Needs product decision
- REQ-xxx: <question>              (items tagged `ambiguous`)

## Needs runtime verification
- REQ-xxx: <what to measure, how>  (items tagged `static-limit`)

## Appendix — undocumented behavior (informational, not failures)
<contents of .audit/appendix.md if you wrote one; else "(none)">
```

Also written: `traceability.csv` (id, requirement, strength, category, stakes, status, evidence, notes, source),
UTF-8 with BOM so Excel opens Vietnamese text correctly.

The `Method` line is generated from `state.json`, so the report states how the audit was actually run — which
models, how many threads, which retrieval engine, and how many items went through the adversarial pass. Keep it:
it is what makes the numbers auditable later.

In chat after `finalize`: the headline numbers, the P0 count and the report path. Do not paste the report.
