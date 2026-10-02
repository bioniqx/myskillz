# Doc catalog and manifest format

Starting point for the Gate proposal, plus the format of the recon manifest. Adapt the catalog to the actual repo from the manifest: drop rows whose "Include when" condition does not hold, add stack-specific rows, dedupe against existing docs (tag `[create]` or `[update]`), and order groups by what this project most needs. Only propose docs the code and requirements actually justify.

**Starred rows are the starter set**: what a non-interactive run or a bare "ok" selects. **Tier** is the default guess used to size the review wave before writing; the real tier is always re-decided per doc by its final content (the tiering rule in the writer brief) once the doc is written.

| Star | Doc | File | Audience | Tier | Include when |
|---|-----|------|----------|------|--------------|
| * | Project overview | `overview.md` | mixed | HIGH | always |
| * | Setup & Local Dev | `setup-guide.md` | dev | HIGH | always |
| * | Architecture Overview | `architecture.md` | dev | HIGH | at least 2 modules or services |
| * | API Integration Guide | `api-reference.md` | dev | HIGH | manifest API surface has routes, handlers or public SDK symbols |
| * | Data Model | `data-model.md` | dev | HIGH | models, entities or `CREATE TABLE` found in manifest |
| * | User Manual | `user-guide.md` | non-tech | LOW | app has a UI or CLI end users touch |
| * | Test Plan & Cases | `test-plan.md` | QA | HIGH | tests/ dir or requirements docs found |
| * | Installation & Deployment Guide | `deployment.md` | ops | HIGH | Dockerfile, compose, CI or IaC found |
|   | Configuration Reference | `configuration.md` | dev/ops | HIGH | at least 5 env vars or a config schema |
|   | Coding Conventions & Contributing | `contributing.md` | dev | HIGH | user asks, or repo is open source |
|   | Feature / Functional Spec | `feature-spec.md` | BA/PO | HIGH | requirements docs describe per-feature behavior |
|   | Requirements Traceability | `traceability.md` | BA/PO | HIGH | requirements docs exist and map to code or endpoints |
|   | Technical Overview (non-deep) | `technical-overview.md` | PM/Leader | LOW | user asks for a status or roadmap-level summary |
|   | Admin Guide | `admin-guide.md` | ops | HIGH | admin or config endpoints found |
|   | Maintenance & Ops Guide | `maintenance.md` | ops | HIGH | user says handover, onboarding or takeover |
|   | Dependency & License Inventory | `dependencies.md` | mixed | LOW | user asks, or lockfiles are extensive |
|   | QA Checklist & Bug-Reporting Flow | `qa-checklist.md` | QA | LOW | user asks |
|   | FAQ / Glossary | `faq.md` | non-tech | LOW | user asks |

Default run = the starred rows whose condition holds (typically 4 to 8 docs, one wave).

**README.md is reserved:** `<output dir>/README.md` is written by the indexer, not by any catalog row, so no row's File may be `README.md`. A repo-root README refresh is a separate `[update]` row that targets the repo-root `README.md`, never a fixed `../README.md`: the relative path depends on the output dir's depth (`docs/` gives `../README.md`, `docs/generated/` gives `../../README.md`). When the output dir is not one of those defaults, give the repo-root path directly instead of guessing a relative one. Propose it only when the repo already has a README worth updating.

**Coverage note:** docs that need business context beyond the code (PM roadmap, PO rationale, parts of BA intent) can only be drafted structurally from code and requirements. Propose them, but tell the user business-specific content needs their input. Never invent it.

## Gate message format

Present the adapted list like the example below, then stop and wait for the user (skip the wait per the Gate skip conditions):

    Recommended starter set marked with *. Reply with the numbers you want
    (for example "1,2,6" or "all *").

     *1. [create] Project overview (overview.md) - covers: <scope>
     *2. [create] Setup & Local Dev - covers: <scope>
     *3. [create] Architecture Overview - covers: <scope>
      4. [update] API Integration Guide - covers: <scope>

## Recon manifest format

Save this to `.claude/doc-generator/recon.md`. Keep it dense and factual: every worker reads it, so it stays at or under 150 lines (slice per doc for huge repos).

    # Recon: <project name>
    HEAD: <git rev-parse HEAD>
    Purpose: <1-2 lines>
    Stack: <languages, frameworks>
    Commands: build=<...> run=<...> test=<...>
    Requirements docs (READ-ONLY, never edit): <path - what it specifies>
    Entry points: <file:line list>
    Directory map:
      <dir>/ - <one-line role>
    API surface:
      <METHOD path or symbol> - <file:line>
    Data models:
      <name> - <file:line>
    Existing docs: <path - status (current, stale or missing)>
    File index (relevant only):
      <path> - <one-line role>
