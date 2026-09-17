---
name: doc-generator
description: >-
  Generate accurate, readable documentation (both technical and non-technical)
  for an existing codebase by reading its code and docs, proposing a doc list,
  writing the selected docs in parallel, and code-checking them. Use this
  skill whenever the user wants to document a project, write or update a README,
  API reference, architecture overview, setup/onboarding guide, user guide,
  test plan, handover documentation, or any project docs — even if they just
  say "document this repo," "write docs for my code," "explain this codebase
  in markdown," or "the docs are out of date." Trigger it for any request to
  produce Markdown documentation derived from source code.
---

# Documentation Generator

A 5-phase pipeline that turns a codebase into correct, readable Markdown docs:

1. **Recon** — map the repo cheaply, write a shared manifest.
2. **Propose & select** — list candidate docs (technical + non-technical); user picks.
3. **Write** — parallel writer subagents, one per doc.
4. **Review & fix** — separate reviewer subagents check each doc against the code and rewrite weak parts.
5. **Finalize & verify** — index, verify links/commands, report.

## Core design constraint: token discipline

Every phase is built to minimize tokens while maximizing quality. Follow these levers — they are the whole point of the skill:

- **Subagent isolation is the biggest lever.** Heavy file-reading happens inside subagents. Only a short summary returns to the main thread, so the main context stays small even for large repos. Always push reading into subagents.
- **One shared manifest, derived once.** Recon output (`.claude/doc-generator/recon.md`) is the single source of truth. Every later subagent is pointed at it instead of re-scanning the repo. Never re-derive what the manifest already holds.
- **Scoped reads.** Each writer/reviewer is given an explicit, minimal file list (only what its doc covers). Never hand a subagent "the whole repo."
- **Signatures over bodies.** During recon, prefer `git ls-files`, `rg`, `head`, and grepping for definitions (routes, classes, exported functions) over reading full files. Read a file in full only when its internals are the subject.
- **No redundant passes.** The reviewer both checks *and* fixes in one shot (no report-then-fix round trip). Default to a single review pass.

## Environment fallback (no subagents)

Some environments (e.g., the Claude.ai chat interface) cannot spawn subagents. In that case run the same pipeline **sequentially in the main thread**: handle one doc at a time following the exact same briefs, keep the scoped-read rule, write every doc to disk, and never paste a full doc into the conversation — summarize instead. All other rules are unchanged.

## Global rules (every phase)

- **Read-only inputs.** Requirements/spec documents are sources, never targets. **NEVER edit, overwrite, or output into them.** Generated docs always go to a separate output location — default `docs/generated/` if the requirements live in `docs/`, else `docs/`; call this `<output dir>` below. If any planned output path would collide with a read-only input, rename the output. Record read-only paths in the manifest.
- **No secrets in docs.** Never copy credentials, API keys, tokens, passwords, or real internal hostnames/IPs/URLs from code or config into any doc. Use placeholders (`<API_KEY>`, `https://api.example.com`). A leaked secret is a blocking review issue.
- **Failure handling.** If a writer or reviewer fails, times out, or returns nothing usable, retry it once. If it fails again, report the gap to the user explicitly — never silently ship a missing or unreviewed doc.

## Phase 1 — Recon (main agent, cheap)

**Reuse check first.** If `.claude/doc-generator/recon.md` already exists, compare its `HEAD:` line to `git rev-parse HEAD`. Same commit → reuse the manifest and jump to Phase 2. Different → run `git diff --name-only <old HEAD>..HEAD` and refresh only the affected manifest sections; redo recon in full only if the diff is large.

Goal: understand the project without reading everything. Prefer shell over full-file reads.

Do, in order:

1. **Gauge size before listing.** `git ls-files | wc -l` (fallback: `find . -type f -not -path '*/node_modules/*' -not -path '*/.git/*'`).
   - ≤ ~300 files: list them all and note the directory shape.
   - Larger: aggregate per directory (`git ls-files | cut -d/ -f1-2 | sort | uniq -c | sort -rn`) and list individual files only for high-signal directories.
   - Monorepo signals (`pnpm-workspace.yaml`, `lerna.json`, `go.work`, several `package.json`/`pyproject.toml`): ask the user which package(s) to document, or recon each package into its own manifest section.
2. **Find and read the requirements/spec document(s)** — the input that describes what the software is *supposed* to do (look in `requirements/`, `specs/`, `docs/`, a linked file, or ask the user to point to it). Treat as **read-only reference** (see Global rules): they tell you intended behavior and vocabulary, and let the reviewer later spot drift between what was required and what the code does.
3. Read other high-signal files in full: `README*`, and the manifest for the stack — `package.json`, `pyproject.toml`/`requirements.txt`, `go.mod`, `Cargo.toml`, `pom.xml`, `composer.json`, etc. These give name, purpose, dependencies, and build/run/test commands.
4. Locate the API/interface surface with grep, not reads. Examples: `rg -n "app\.(get|post|put|delete)|@app\.route|@(Get|Post)Mapping|func .*Handler|export (async )?function"`. Capture `file:line` for each hit.
5. Locate data models/schemas similarly (`rg -n "class .*Model|CREATE TABLE|@Entity|struct .* \{|interface .*\{"`).
6. Inventory existing output docs (a `docs/` folder, inline `.md` files) and note what's stale or missing. Keep this list separate from the read-only requirements docs above.

Write findings to `.claude/doc-generator/recon.md` in this compact shape (this file feeds every later subagent, so keep it dense and factual):

```
# Recon: <project name>
HEAD: <output of git rev-parse HEAD>
Purpose: <1–2 lines>
Stack: <languages, frameworks>
Commands: build=<...> run=<...> test=<...>
Requirements docs (READ-ONLY — never edit): <path — what it specifies>
Entry points: <file:line list>
Directory map:
  <dir>/ — <one-line role>
API surface:
  <METHOD path or symbol> — <file:line>
Data models:
  <name> — <file:line>
Existing docs: <path — status (current/stale/missing)>
File index (relevant only):
  <path> — <one-line role>
```

## Phase 2 — Propose & select

**Skip conditions.** If the user already named exactly which docs they want, map each to a title + output path, confirm in one line, and go straight to Phase 3. In a non-interactive run (no user available to answer), use the ★ starter set.

Otherwise, from the manifest alone (no new reading): read `references/doc-catalog.md` and adapt its template to this repo — drop rows the code doesn't support (e.g. no CI folder → no CI/CD runbook), add stack-specific ones, dedupe against existing docs (tag `[create]`/`[update]`), and mark a recommended ★ starter set. The user usually does **not** know which docs they need, so propose a sensible, fairly complete set spanning the development lifecycle *and* customer handover. Present the numbered list, then stop and wait for the user.

In the same message, confirm two settings so the user can accept each with one word:

- **Language** — default **English** (see Output language rule).
- **Audience** — ask only when it materially changes a doc (e.g. an API reference for external integrators vs. internal callers), and offer a default.

Keep the whole exchange to a single tight message — don't interrogate.

## Phase 3 — Write (parallel writers)

Spawn **one writer subagent per selected doc, all launched in a single turn** so they run concurrently. If more than ~5 docs are selected, run in waves of ~5 to avoid overload.

Each writer is a fresh subagent given the manifest plus a scoped file list — never the whole repo. Build each brief from `references/writer-brief.md`: read it once, fill the placeholders per doc.

The "return only a summary" rule in the brief is what keeps the main context small — the doc lives on disk, not in the transcript.

## Phase 4 — Review & fix (parallel reviewers)

For each doc just written, spawn a **separate** reviewer subagent (fresh eyes — never the same agent that wrote it), again all in one turn. The reviewer checks against the *actual code* and rewrites weak parts in place. Build each brief from `references/reviewer-brief.md`.

Default to one review pass. Offer the user a second pass only if a reviewer reports a doc was broadly wrong; if so, re-run a single writer for that one doc, then review again. Don't loop indefinitely.

## Phase 5 — Finalize & verify

1. Write/refresh `<output dir>/README.md` as an index linking every generated doc (title + one-line purpose), grouped technical / non-technical.
2. **Verify (cheap, no execution):**
   - every selected doc exists on disk and is non-empty;
   - every relative link in the index and between generated docs resolves;
   - commands quoted in docs match the manifest `Commands:` line / real script names (existence check only — don't run them).
   Fix trivial breakage directly; report anything else.
3. Tell the user the scratch dir `.claude/doc-generator/` can be deleted or gitignored.
4. Give a concise summary: which docs were created/updated and their paths, reviewer-flagged gaps that need a human (e.g. business rules the code can't reveal), and any item that still failed after its retry.

## Output language rule

Generated docs default to **English** — the usual language for stakeholder and handover documentation — regardless of the language of the code comments. Use another language only when the user requests it or confirms it in Phase 2. The skill's own instructions stay English.
