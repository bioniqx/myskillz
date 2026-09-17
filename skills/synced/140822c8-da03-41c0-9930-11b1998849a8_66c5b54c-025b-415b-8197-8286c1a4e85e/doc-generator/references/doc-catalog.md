# Doc catalog — Phase 2 proposal template

Starting point for the proposal. **Adapt it to the actual repo:** drop rows the code doesn't support, add stack-specific ones, dedupe against existing docs (tag `[create]`/`[update]`), and order the groups by what this project most needs. Only propose docs the code + requirements actually justify. For each item give: tag, title, one-line purpose, and scope.

Present it like this, then stop and wait for the user:

```
Recommended starter set marked ★. Reply with the numbers you want
(e.g. "1,2,6" or "all ★").

For developers — BE / FE / DevOps
 ★1. [create] Architecture Overview — how components fit · covers: src/app, src/services
 ★2. [update] API Integration Guide — endpoints, auth, payloads, examples · covers: src/routes/*
  3. [create] Setup & Local Dev — clone → run → test · covers: package.json, .env.example
  4. [create] Deployment & CI/CD Runbook (DevOps) — build, deploy, rollback · covers: Dockerfile, .github/, infra/
  5. [create] Coding Conventions & Contributing — add code safely · covers: repo layout, lint config

For QC / QA
 ★6. [create] Test Plan & Cases — what to test, expected results · covers: tests/, requirements docs
  7. [create] QA Checklist & Bug-Reporting Flow — release gate + how to file bugs

For BA / PO
 ★8. [create] Feature / Functional Spec — implemented behavior per feature · covers: src/features/*, requirements docs
  9. [create] Requirements Traceability — requirement ↔ code/endpoint map · covers: requirements docs ↔ src

For PM / Leader
 10. [create] Technical Overview (non-deep) — modules, status, risks · covers: directory map

For customer handover
 ★11. [create] Installation & Deployment Guide — stand it up from scratch · covers: infra, config
 ★12. [create] User Manual — task-based how-to for end users · covers: src/features/*
  13. [create] Admin Guide — configuration & operations · covers: config, admin endpoints
  14. [create] Maintenance & Ops Guide — monitor, back up, troubleshoot
  15. [create] Dependency & License Inventory — what ships, under which license · covers: lockfiles
```

**Coverage note:** docs that require business context beyond the code (PM roadmap, PO rationale, parts of BA intent) can only be drafted *structurally* from code + requirements. Propose them, but tell the user that business-specific content needs their input — never invent it.
