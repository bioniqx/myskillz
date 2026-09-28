# Report format

`audit.py report` renders `.audit/requirements-code-audit.md` from the checklist, merged findings, verdicts,
adjudications and `plan.jsonl`. Headings are localised (`en`, `vi` built in; `--headings my-lang.json` overrides any key
of the `HEADINGS` table in `scripts/audit.py` for other languages). The free text the lead writes (plan entries,
adjudication notes, checklist text) must already be in the spec's language.

```markdown
# Requirements ↔ Code Audit

- Source of truth: `<file(s)>`
- Codebase: `<root>`
- Date: <date>
- Constraints honored: no git history; no documentation other than the source of truth; codebase not modified.

## Summary
- Total requirements: N
- ✅ Matched: a   ⚠️ Partial: b   ❌ Missing: c   ⛔ Conflict: d   ❓ Unverifiable: e
- Alignment: a / N

## Traceability
| ID | Requirement | Strength | Status | Evidence (path:lines) | Notes |

## Discrepancies (detail)
### ⚠️ Partial REQ-007 — <short title>
- Requirement: …
- Finding: path:lines — what the code does (or "MISSING — searched: …")
- Why it diverges: adjudication note / verifier reason / investigator note

## Remediation plan
### P0
1. **<title>** (REQ-007) — Effort S
   - Current: …
   - Target: …
   - Fix: …
   - Depends on: …
   - Risk: …
### P1 … ### P2 …

## Needs product decision
- REQ-xxx: <question>              (items tagged `ambiguous`)

## Needs runtime verification
- REQ-xxx: <what to measure, how> (items tagged `static-limit`; uses `question` or `evidence_expected`)

## Appendix — undocumented behavior (informational, not failures)
<contents of .audit/appendix.md if the lead wrote one; else "(none)">
```

Also written: `traceability.csv` (id, requirement, strength, category, stakes, status, evidence, notes, source) for
spreadsheets and ticketing.

In chat, after `audit.py finish`: the headline numbers, the P0 count and the report path. Do not paste the report.
