# Doc catalog — Gate proposal template

Starting point for the Gate proposal. Adapt it to the actual repo from the recon manifest:
drop rows whose "Include when" condition doesn't hold, add stack-specific rows, dedupe against
existing docs (tag `[create]`/`[update]`), and order groups by what this project most needs.
Only propose docs the code + requirements actually justify.

**★ = starter set** — what a non-interactive run or a bare "ok" selects. **Tier** is the
default guess used to size the review wave *before* writing; the real tier is always
re-decided per SKILL.md's rule ("Tier by final content, not intent") once the doc is written.

| ★ | Doc | File | Audience | Tier | Include when |
|---|-----|------|----------|------|--------------|
| ★ | Project overview | `overview.md` | mixed | HIGH | always |
| ★ | Setup & Local Dev | `setup-guide.md` | dev | HIGH | always |
| ★ | Architecture Overview | `architecture.md` | dev | HIGH | ≥ 2 modules/services |
| ★ | API Integration Guide | `api-reference.md` | dev | HIGH | manifest API surface has routes/handlers/public SDK symbols |
| ★ | Data Model | `data-model.md` | dev | HIGH | models/entities/`CREATE TABLE` found in manifest |
| ★ | User Manual | `user-guide.md` | non-tech | LOW | app has a UI/CLI end users touch |
| ★ | Test Plan & Cases | `test-plan.md` | QA | HIGH | tests/ dir or requirements docs found |
| ★ | Installation & Deployment Guide | `deployment.md` | ops | HIGH | Dockerfile/compose/CI/IaC found |
|  | Configuration Reference | `configuration.md` | dev/ops | HIGH | ≥ 5 env vars or a config schema |
|  | Coding Conventions & Contributing | `contributing.md` | dev | HIGH | user asks, or repo is open source |
|  | Feature / Functional Spec | `feature-spec.md` | BA/PO | HIGH | requirements docs describe per-feature behavior |
|  | Requirements Traceability | `traceability.md` | BA/PO | HIGH | requirements docs exist and map to code/endpoints |
|  | Technical Overview (non-deep) | `technical-overview.md` | PM/Leader | LOW | user asks for a status/roadmap-level summary |
|  | Admin Guide | `admin-guide.md` | ops | HIGH | admin/config endpoints found |
|  | Maintenance & Ops Guide | `maintenance.md` | ops | HIGH | user says handover/onboarding/takeover |
|  | Dependency & License Inventory | `dependencies.md` | mixed | LOW | user asks, or lockfiles are extensive |
|  | QA Checklist & Bug-Reporting Flow | `qa-checklist.md` | QA | LOW | user asks |
|  | FAQ / Glossary | `faq.md` | non-tech | LOW | user asks |

Default run = the ★ rows whose condition holds (typically 4–8 docs → one wave).

**README.md is reserved:** `<output dir>/README.md` is written by the indexer, not by any
catalog row — no row's File may be `README.md`. A repo-root README refresh is a separate
`[update]` row that targets the repo-root `README.md`, never a fixed `../README.md` — the
relative path depends on the output dir's depth (`docs/` → `../README.md`, `docs/generated/`
→ `../../README.md`); when the output dir isn't one of those defaults, give the repo-root path
directly instead of guessing a relative one. Proposed only when the repo already has one worth
updating.

**Coverage note:** docs that need business context beyond the code (PM roadmap, PO rationale,
parts of BA intent) can only be drafted *structurally* from code + requirements. Propose them,
but tell the user business-specific content needs their input — never invent it.

Present the adapted list like this, then stop and wait for the user (skip the wait per the
Gate's skip conditions):

```
Recommended starter set marked ★. Reply with the numbers you want
(e.g. "1,2,6" or "all ★").

 ★1. [create] Project overview (overview.md) — · covers: <scope>
 ★2. [create] Setup & Local Dev — · covers: <scope>
 ★3. [create] Architecture Overview — · covers: <scope>
  4. [update] API Integration Guide — · covers: <scope>
  ...
```
