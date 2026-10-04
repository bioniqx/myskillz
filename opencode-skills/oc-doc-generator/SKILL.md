---
name: oc-doc-generator
description: >-
  Generate accurate Markdown documentation for an existing codebase: one recon
  scan, then up to 10 parallel writer subagents, then targeted review. Use when
  the user wants to document a project, write or update a README, API reference,
  architecture overview, setup/onboarding guide, user guide, data model, testing
  or deployment doc, handover documentation, or says "document this repo",
  "write docs for my code", "explain this codebase in markdown", "generate
  project documentation", or "the docs are out of date". Trigger for any request
  to produce Markdown docs derived from source code.
---

# Doc Generator — 10-lane parallel pipeline

Codebase in, correct Markdown docs out, in **≤ 4 main-thread turns**. This file is
self-contained: every brief, template and script you need is below. **Never read any other file of this skill.** (A vendored `scripts/oc_harness.py` may sit in the folder; this skill never runs or reads it.)

---

## 0. EXECUTION CONTRACT — obey literally, do not re-derive

| # | Rule | Violation = bug |
|---|------|-----------------|
| R1 | **Turn budget ≤ 4** (cache hit: ≤ 2). Turn = one main-thread message. The Gate question (§3.0) belongs to Turn 2 and the answer starts Turn 3; a changed selection may add one review turn, nothing else may add one. | Adding a turn a batch could absorb |
| R2 | **One message = all independent calls.** 1 bash + 10 `subagent` calls go in ONE message. | Sending calls one at a time |
| R3 | **Concurrency = 10 subagents max per wave.** More docs → consecutive waves of 10, biggest doc first. | 11+ at once, or 1-at-a-time |
| R4 | **One bash call per phase.** Chain with `;` `&&` `2>/dev/null`. | Two bash calls in one phase |
| R5 | **Zero cold-start reads for subagents.** Inline the facts + brief + file list into every subagent prompt. Its first tool call hits target code, never a brief or manifest file. | Subagent reading this skill or the manifest |
| R6 | **No narration.** No "Let me…", no phase summaries, no pasting doc bodies into the main thread. Docs live on disk. | Any prose between tool calls |
| R7 | **Subagents follow a checklist; they must not deliberate.** Say so in every subagent prompt. | Deliberation on mechanical work |
| R8 | **Never redo work.** Diff-skip via `.opencode/oc-doc-gen/state.json` before every wave. | Rewriting an unchanged doc |
| R9 | **Subagent returns ≤ 5 lines.** Never the doc body. | Long subagent returns |
| R10 | **Failure budget: 1 retry per doc, bundled into the next wave.** Never a dedicated retry turn, never a third attempt. | Retry loops |

R2's calls are `subagent` tool calls with `agent: "oc-doc-writer"` or `agent: "oc-doc-reviewer"` and
`background: true`, no model parameter — fire each without waiting, one per doc, then end the
turn (§8).

**Turn ledger (target):**

| Turn | Content (single message) |
|------|--------------------------|
| 1 | 1 bash: cache check + recon + fact pack |
| 2 | Gate list (§3.0), or 1 line of intent when the Gate is skipped + 1 bash (manifest + state scaffold + index + dirs) + ≤ 10 writer `subagent` calls (the ★ set, speculatively, while the Gate waits) |
| 3 | Delta writers only if the Gate answer changed the set + ≤ 10 reviewer `subagent` calls (HIGH-tier only) + any 1 retry |
| 4 | 1 bash (mechanical verify + update state) + final summary |

Skip Turn 3 entirely when no HIGH doc was written this run. Skip Turn 1's work on a cache hit.

---

## 1. DECISION TABLE — pick a row, act, do not deliberate

| Situation | Play |
|---|---|
| Cache hit (`HEAD` unchanged) + all scopes unchanged | Report `[cached]` list, ask nothing, stop at Turn 2 |
| User named specific docs | Use exactly those. Confirm in one clause inside Turn 2 |
| User said nothing specific, interactive run | Run the Gate (§3.0): adapted numbered list with `[create]`/`[update]` tags, a bare "ok" selects the ★ set |
| Non-interactive run (nobody to answer) | Use the ★ set (§3.1), state it in one line, skip the Gate |
| > 10 docs selected | Waves of 10, longest/HIGH first |
| Repo > 3000 files or monorepo | Turn 1 becomes: 1 bash (root recon) + up to 9 read-only shards, one per package — same message. Shards run as `agent: "general"`. Ask which packages to document inside the Gate message |
| No git repo | Recon script auto-falls back to a mtime hash; everything else identical |
| Requirements/spec docs found | Read-only sources. **Never** write into them. Rename any colliding output |
| `subagent` tool unavailable | §6 sequential fallback |
| Subagent fails/returns junk | Retry once in the next wave's message. Fails twice → report the gap, never ship silently |

---

## 2. TURN 1 — RECON (exactly one bash call, nothing else)

Run this verbatim from the repo root. It checks cache, builds the manifest AND the fact
pack in one pass, and degrades gracefully with no git / no ripgrep.

```bash
S=.opencode/oc-doc-gen; mkdir -p "$S"; {
H=$(git rev-parse --short HEAD 2>/dev/null); [ -z "$H" ] && H=$( (find . -path ./.git -prune -o -type f -print0 2>/dev/null | xargs -0 ls -la 2>/dev/null) | cksum | tr -d ' ' | cut -c1-12);
if [ -f "$S/recon.md" ] && [ "$(sed -n 's/^HEAD: //p' "$S/recon.md" | head -n 1)" = "$H" ]; then echo "=== CACHE HIT ==="; cat "$S/recon.md"; cat "$S/state.json" 2>/dev/null; exit 0; fi
O=$(sed -n 's/^HEAD: //p' "$S/recon.md" 2>/dev/null | head -n 1); [ -n "$O" ] && { echo "=== CHANGED SINCE $O ==="; git diff --name-only "$O"..HEAD 2>/dev/null | head -200; }
echo "HEAD: $H"; echo "ROOT: $(pwd)"
FL=$(git ls-files 2>/dev/null); [ -z "$FL" ] && FL=$(find . -type f -not -path '*/.git/*' -not -path '*/node_modules/*' -not -path '*/.venv/*' -not -path '*/venv/*' -not -path '*/dist/*' -not -path '*/build/*' -not -path '*/target/*' -not -path '*/vendor/*' -not -path '*/.next/*' 2>/dev/null | sed 's|^\./||')
echo "FILES: $(printf '%s\n' "$FL" | wc -l)"
echo "== TREE =="; printf '%s\n' "$FL" | awk -F/ 'NF>1{print $1"/"$2} NF==1{print $1}' | sort | uniq -c | sort -rn | head -40
echo "== EXT =="; printf '%s\n' "$FL" | sed -n 's/.*\.\([A-Za-z0-9]\{1,6\}\)$/\1/p' | sort | uniq -c | sort -rn | head -12
for m in package.json pyproject.toml requirements.txt go.mod Cargo.toml pom.xml build.gradle composer.json Gemfile Makefile Dockerfile docker-compose.yml .env.example; do [ -f "$m" ] && { echo "== $m =="; head -60 "$m"; }; done
for r in README.md README.rst readme.md CONTRIBUTING.md; do [ -f "$r" ] && { echo "== $r =="; sed -n '1,120p' "$r"; }; done
for d in requirements specs spec docs doc design; do for s in "$d"/*.md "$d"/*.txt; do [ -f "$s" ] && { echo "== SPEC(READ-ONLY): $s =="; sed -n '1,120p' "$s"; }; done; done
echo "== FACTPACK =="
P='app\.(get|post|put|patch|delete)\(|@app\.route|@(Get|Post|Put|Patch|Delete)Mapping|router\.(get|post|put|patch|delete)\(|func \(.*\) [A-Z][A-Za-z]*\(|http\.HandleFunc|export (default |async )?(function|class|const) [A-Za-z]|^[[:space:]]*(public|private) [A-Za-z<>\[\]]+ [a-zA-Z]+\(|class [A-Za-z]+(Model|Entity|Service|Controller|Repository)|CREATE TABLE|^[[:space:]]*(interface|type) [A-Z][A-Za-z]*|@(Entity|Table|Column)|models\.[A-Z][a-zA-Z]*Field|process\.env\.[A-Z_]+|os\.getenv\('
if command -v rg >/dev/null 2>&1; then rg -n --no-heading -m 500 --max-filesize 512K -g '!*.min.*' -g '!*.lock' -e "$P" . 2>/dev/null | head -400; else grep -rnE --exclude-dir=.git --exclude-dir=node_modules --exclude-dir=dist --exclude-dir=vendor "$P" . 2>/dev/null | head -400; fi
echo "== TESTS =="; printf '%s\n' "$FL" | grep -iE '(^|/)(tests?|spec|__tests__)/|\.(test|spec)\.[a-z]+$|_test\.[a-z]+$' | head -25
echo "== CI =="; ls .github/workflows/*.y*ml Jenkinsfile .gitlab-ci.yml 2>/dev/null | head -10
echo "== EXISTING DOCS =="; printf '%s\n' "$FL" | grep -iE '\.(md|rst|adoc)$' | head -40
} 2>/dev/null | head -900
```

**Then, in your own head only** (no extra tool call), compress the output into this manifest.
You will paste slices of it into subagent prompts; it is written to `.opencode/oc-doc-gen/recon.md` in Turn 2, before any writer starts, as a `HEAD: <hash>` line followed by the manifest (the manifest never repeats the HEAD line).

```
# Recon: <project>
Stack: <langs, frameworks>     Files: <n>
Purpose: <1-2 lines>
Commands: install=<...> build=<...> run=<...> test=<...> lint=<...>
Read-only specs (NEVER write): <paths>
Output dir: <docs/ or docs/generated/>
Entry points: <file:line …>
Dirs: <dir> — <role>   (≤ 12 lines)
API surface: <METHOD /path or Symbol()> — <file:line>   (≤ 25 lines)
Data models: <Name> — <file:line>                       (≤ 15 lines)
Config/env: <VAR> — <where>                             (≤ 12 lines)
Existing docs: <path> — current|stale|missing
```

Rules: signatures over bodies — never read a full source file on the main thread. Manifest ≤ 150
lines; for huge repos keep per-doc slices only. **Output dir** = `docs/generated/` if user spec
docs already live in `docs/`, else `docs/`.

---

## 3. TURN 2 — GATE + WRITE WAVE (one message: Gate list or 1 line of intent + 1 bash + ≤ 10 `subagent` calls)

### 3.0 Gate — select the docs (Turn 2)

Skip the Gate only when the user already named the docs (map each to its title and file, confirm in one clause) or the run is non-interactive (use the ★ set, say so in one line). Otherwise:

1. Adapt §3.1 to this repo from the manifest, with no new reading: drop rows whose condition fails, dedupe against EXISTING DOCS, and tag each row `[create]` (the doc does not exist yet) or `[update]` (it exists).
2. Send ONE tight numbered list, ★ rows first and marked. A bare "ok" selects the ★ set, numbers select those rows, and the user may also name a language (default English). In a monorepo add the question "which packages should be documented?" to the same message.

```
★ rows are the default. Reply "ok", or the numbers you want (for example "1,3,6").
 ★1. [create] Project overview (overview.md) — covers: <scope>
 ★2. [create] Setup & run (setup-guide.md) — covers: <scope>
  3. [update] Configuration (configuration.md) — covers: <scope>
```

3. In the same message run the bash call of §3.3 for the ★ set and launch the ★-set writers now with `background: true` (speculation). End the turn. On "ok" the wave is already running; on a changed selection keep the writers whose doc is still selected, delete the rest, re-run the bash call with the final list and launch only the delta in Turn 3. Never speculate reviews.

### 3.1 Catalog — include a row only when its condition holds

| ★ | Doc | File | Audience | Tier | Include when |
|---|-----|------|----------|------|--------------|
| ★ | Project overview | `overview.md` | mixed | HIGH | always |
| ★ | Setup & run | `setup-guide.md` | dev | HIGH | always |
| ★ | Architecture | `architecture.md` | dev | HIGH | ≥ 2 modules/services |
| ★ | API reference | `api-reference.md` | dev | HIGH | FACTPACK has routes/handlers/public SDK symbols |
| ★ | Data model | `data-model.md` | dev | HIGH | models/entities/CREATE TABLE found |
| ★ | User guide | `user-guide.md` | non-tech | LOW | app has a UI/CLI end users touch |
| ★ | Test plan & cases | `test-plan.md` | QA | HIGH | test dirs or requirement docs found |
| ★ | Installation & deployment | `deployment.md` | ops | HIGH | Dockerfile/compose/CI/IaC found |
| | Configuration | `configuration.md` | dev/ops | HIGH | ≥ 5 env vars or a config schema |
| | Contributing | `contributing.md` | dev | HIGH | user asks, or repo is open source |
| | Feature / functional spec | `feature-spec.md` | BA/PO | HIGH | requirement docs describe per-feature behaviour |
| | Requirements traceability | `traceability.md` | BA/PO | HIGH | requirement docs exist and map to code or endpoints |
| | Technical overview | `technical-overview.md` | PM/leader | LOW | user asks for a status or roadmap-level summary |
| | Admin guide | `admin-guide.md` | ops | HIGH | admin or config endpoints found |
| | Handover / ops | `handover.md` | mixed | HIGH | user says handover/onboarding/takeover |
| | Dependency & licence inventory | `dependencies.md` | mixed | LOW | user asks, or lockfiles are extensive |
| | QA checklist & bug-report flow | `qa-checklist.md` | QA | LOW | user asks |
| | FAQ / glossary | `faq.md` | non-tech | LOW | user asks |

Default run = the ★ rows whose condition holds (typically 4–8 docs → one wave).

`<output dir>/README.md` is reserved for this index: it is written by the §3.3 bash call, no catalog row and no writer uses it, and the project overview is `overview.md`. A repo-root README refresh is a separate `[update]` row whose target is the repo's own `README.md` (give the repo-root path directly, never a guessed `../README.md`); propose it only when the repo already has a README worth updating.

Docs that need business context beyond the code (roadmap, rationale, parts of BA intent) can only be drafted structurally: propose them and tell the user business-specific content needs their input.

### 3.2 Diff-skip (apply before launching anything)

For each selected doc with an entry in `state.json`: if the doc file exists **and**
`changed-files ∩ its scope = ∅` → mark `[cached]`, launch no writer and no reviewer.
If the recon printed no usable `CHANGED SINCE` list (shallow clone, rewritten history, no git),
treat every scope as changed — correctness beats the cache.

### 3.3 The one message

Send together, in this order, in a **single message**:

1. **The Gate list (§3.0) or, when the Gate was skipped, one line of intent** — e.g. `Writing 5 docs to docs/: overview, setup-guide, architecture, api-reference, user-guide (say "stop" to change the set).` Do not wait for a reply to the intent line; the Gate list ends the turn.
2. **One bash call** — writes the manifest and the state scaffold, creates the output dir and the index, deterministically, with no subagent. `[cached]` docs keep their previous `scope` and `head` in `state.json`. If the Gate answer changes the set, Turn 3 runs this call again with the final list:

```bash
S=.opencode/oc-doc-gen; D=<output dir>; mkdir -p "$D" "$S"
{ printf 'HEAD: %s\n' "<HEAD>"; cat <<'EOF'
<the manifest from §2, without a HEAD line>
EOF
} > "$S/recon.md"
cat > "$S/state.json" <<'EOF'
{"head":"<HEAD>","docs":{"<file>":{"scope":["<paths>"],"tier":"<HIGH|LOW>","head":"<HEAD>"}}}
EOF
{ echo "# Documentation"; echo; echo "_Generated $(date +%Y-%m-%d) from commit <HEAD>._"; echo; echo "## Technical"; for f in <HIGH files>; do echo "- [<title>](./$f)"; done; echo; echo "## Non-technical"; for f in <LOW files>; do echo "- [<title>](./$f)"; done; } > "$D/README.md"
```
   `$D/README.md` belongs to this index alone: no writer writes it and it links the overview (`overview.md`).
3. **≤ 10 writer `subagent` calls** with `agent: "oc-doc-writer"`, one per non-cached doc, **each using this exact template**:

```
ROLE: Technical writer. Follow the checklist, do not deliberate, no plan step.
GOAL: Write <output dir>/<file> — "<title>" for <audience>.
TAG: <create|update> (update = the file already exists).

BUDGET (hard): ≤ 12 file reads, ≤ 15 tool calls, one write. Read ranges with the read tool's offset and limit (for example lines 1-120),
never whole large files. Read no project doc except the existing doc of an update and any read-only spec listed in SCOPE. Do not run project commands.

FACTS (authoritative — do not re-derive):
<manifest slice: purpose, stack, commands, entry points, dirs, and the API/model/config lines relevant to THIS doc>

SCOPE (read only these, only as needed):
<≤ 12 paths chosen for this doc>

WRITE:
- Structure: <per-doc outline from §3.4>
- Length: README ≤ 150 lines; others ≤ 400 lines. Short sentences, active voice, no filler.
- Every command, path, endpoint, signature, env var, schema MUST come from FACTS or from a
  file you actually read. Never invent. Unknown but needed → a line `TODO(human): <question>`.
- Secrets: never copy keys/tokens/passwords/internal hosts. Use `<API_KEY>`, `https://api.example.com`.
- Links: relative, inside <output dir>. Code fences tagged with a language.
- Language: <language> (English unless the Gate named another).
- TAG update: read the existing <output dir>/<file> FIRST. Keep content that is still accurate and anything a human added that code cannot reveal (business rationale, decisions, external links); rewrite only stale or wrong parts, and say in `risk` what you removed or heavily rewrote.
- Read-only specs in SCOPE: read them for intended behaviour, but document what the CODE actually does; where code and requirement disagree, describe the code and flag the mismatch in `risk`.
- Architecture, flow and data-model docs: include a small Mermaid diagram (flowchart, sequenceDiagram or erDiagram) that matches the code.
- Never modify any file outside <output dir> (the one exception is a repo-root README refresh row, whose target file is the one file you write). Read-only specs: <paths>.

SELF-VERIFY before returning (cheap, no re-reads):
1. Every command appears in FACTS `Commands:` or in a script/Makefile target you read.
2. Every path you quote exists in SCOPE or FACTS.
3. No secrets. 4. Every relative link targets a file in <output dir>'s planned set.

RETURN EXACTLY 5 LINES:
title=<…>
path=<…>
tier=<HIGH if the final text contains any command, endpoint, signature, schema, config value,
code fence or file path; else LOW>
todos=<count of TODO(human) lines>
risk=<one clause: what you were least sure about, or "none">
```

### 3.4 Per-doc outlines (paste the matching one into the subagent prompt)

- **overview.md** — one-paragraph what/why · key features (≤ 6 bullets) · quickstart (install→run→test, copy-pasteable) · project layout table · links to the other docs · license/support.
- **setup-guide.md** — prerequisites w/ versions · install · configuration (env table: var, required?, default, meaning) · run dev · run tests · common errors → fixes · verifying it works.
- **architecture.md** — 1 paragraph overview · component table (component, responsibility, path) · one ASCII/Mermaid diagram of request or data flow · key flows numbered end-to-end w/ `file:line` · design decisions & trade-offs · known limitations.
- **api-reference.md** — grouped by resource · per endpoint/function: signature, purpose, params table, returns, errors, one minimal example · auth section · versioning/stability note.
- **data-model.md** — entity table (name, table/collection, purpose, path) · per entity: field table (name, type, constraints, meaning) · relationships (list or Mermaid ER) · migrations/indexes if present.
- **user-guide.md** — who it's for · what it lets you do · task-oriented walkthroughs ("To do X: 1…2…3") · plain language, zero jargon, no code unless the user really types it · troubleshooting.
- **configuration.md** — full env/config table · per-environment differences · secrets handling policy (placeholders only) · precedence order.
- **deployment.md** — installation prerequisites · target environments · build artifact · install and deploy steps · rollback · health checks/monitoring · scaling notes.
- **test-plan.md** — test types & where they live · how to run each · how to write a new one · fixtures/mocks · coverage expectations · CI behaviour · one test case per requirement when requirement docs exist (id, steps, expected result).
- **handover.md** — system in 1 page · access/accounts checklist (names only, never secrets) · routine operations · incident playbook · open risks & TODOs · who/what to ask next.
- **feature-spec.md** — one section per feature: purpose · behaviour as the code implements it · inputs/outputs · rules and limits · requirement ids covered, with code-versus-requirement mismatches flagged.
- **traceability.md** — table of requirement id · requirement text · implementing file:line · test file:line · status (covered, partial, missing); mismatches flagged, never hidden.
- **technical-overview.md** — status and roadmap-level summary for a PM/leader: what exists · what is in flight · risks · dependencies on people or systems; no code, business content marked as needing the owner's input.
- **admin-guide.md** — admin tasks (user and role management, config switches, jobs) · where each lives in the code or UI · safe operating limits · audit and logging points.
- **dependencies.md** — table of dependency · version · purpose · licence (only when a manifest or lockfile states it) · where it is used.
- **qa-checklist.md** — pre-release checklist grouped by area · how to report a bug (template: steps, expected, actual, environment) · where logs live.

---

## 4. TURN 3 — REVIEW WAVE (HIGH tier only, one message, ≤ 10 `subagent` calls)

Skip this turn entirely if every doc is LOW or `[cached]`. Reviewer ≠ the writer, fresh context,
`agent: "oc-doc-reviewer"`.

```
ROLE: Technical fact-checker with edit rights. No report-then-fix —
you FIX in place, in the same run.
TARGET: <output dir>/<file>
BUDGET: ≤ 10 reads, ≤ 6 edits, ≤ 18 tool calls. Never run project commands. Never touch
any file but the target.

FACTS: <same manifest slice>
CODE TO CHECK AGAINST: <the writer's scope list>

CHECK EVERY VERIFIABLE CLAIM, in this order (stop at budget, hardest-hitting first):
1. Commands — each exists as a script/Makefile target/CLI entry point. Wrong → fix to the real one.
2. Paths & file names — exist. Wrong → fix or delete the claim.
3. Endpoints/signatures/params/return types — match the source exactly (method, path, name, arity, types).
4. Env vars & config keys — real names, real defaults.
5. Schema/field names & types — match the model definitions.
6. Invented behaviour — any feature, flag or guarantee not present in code: delete it or convert
   to `TODO(human): <question>`.
7. Requirements fidelity (docs that cite read-only requirement files) — the doc says what the CODE does, and every code-versus-requirement mismatch is flagged, not hidden.
8. Completeness — the doc covers its stated scope for its audience; add what is missing from the scope files, or list what you could not cover in `unresolved`.
9. Mermaid diagrams — every node, actor, entity and arrow matches the code; fix or delete the diagram.
10. Secrets — replace any real key/token/host with a placeholder. Blocking.
11. Links — relative links resolve inside <output dir>.
12. Clarity — rewrite any paragraph that is vague, duplicated, or padding. Keep it shorter.

If most of the doc is wrong, do NOT rewrite it: return verdict=broadly-wrong with the reasons in `unresolved`.

RETURN EXACTLY 5 LINES:
path=<…>
verdict=<clean|fixed|broadly-wrong>
fixes=<n>
unresolved=<claims you could not verify within budget, or "none">
human=<questions only a human can answer, or "none">
```

A reviewer does NOT rewrite a doc that is mostly wrong: it returns `verdict=broadly-wrong` with the reasons in `unresolved`. `broadly-wrong` → rerun one writer + one fresh reviewer for that doc **together in one small
wave**. Never loop a third time.

---

## 5. TURN 4 — FINISH (one bash + one summary)

```bash
D=<output dir>; cd "$D" && { for f in <all selected files>; do [ -s "$f" ] || echo "EMPTY: $f"; done
grep -RhoE '\]\(\.?/?[^)#:]+\.md[^)]*\)' *.md 2>/dev/null | tr -d '()' | sed 's/^\]//;s/#.*//' | sort -u | while read -r l; do [ -e "$l" ] || echo "BROKEN_LINK: $l"; done
grep -RhoE '(npm|pnpm|yarn|pip|python3?|go|cargo|make|mvn|docker|uv)( [a-z][a-zA-Z0-9:._-]*){1,3}' *.md 2>/dev/null | sort -u
grep -RnoE '(sk-[A-Za-z0-9]{12,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY|password[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{6,})' *.md 2>/dev/null | head -20 | sed 's/^/SECRET_SUSPECT: /'
grep -c 'TODO(human)' *.md 2>/dev/null | grep -v ':0$' | sed 's/^/TODOS: /'
BT=$(printf '\140'); for f in <LOW files>; do grep -qE "$BT$BT$BT|(^|[[:space:]$BT])(npm|pnpm|yarn|pip|python3?|go|cargo|make|mvn|docker) " "$f" 2>/dev/null && echo "LOW_HAS_CODE: $f"; done; } 2>/dev/null; cd - >/dev/null; mkdir -p .opencode/oc-doc-gen; cat > .opencode/oc-doc-gen/state.json <<'EOF'
{"head":"<HEAD>","docs":{"<file>":{"scope":["<paths>"],"tier":"<HIGH|LOW>","head":"<HEAD>"}}}
EOF
```

Then:

- Cross-check the printed command list against `Commands:` — existence only, never execute.
- Fix trivial breakage (`BROKEN_LINK`, stray path) yourself in this same turn with direct edits.
- `SECRET_SUSPECT` → fix immediately, blocking.
- `LOW_HAS_CODE` → one reviewer `subagent` call for that doc only (the sole path allowed to add a turn).
- **Final summary message** (compact): created / updated / `[cached]` docs with paths · index path ·
  `TODO(human)` questions that need a human · every reviewer `unresolved=` and `human=` value that is not "none" · anything still failing after its one retry ·
  note that `.opencode/oc-doc-gen/` is a cache and can be gitignored or deleted.

---

## 6. FALLBACK — no `subagent` tool

Only when the `subagent` tool is unavailable. Same pipeline, sequential, same inlined briefs.
Write each doc yourself, one at a time, in the order of the catalog. Keep: one batched bash
per phase, diff-skip, self-verify while writing, review HIGH docs only with fresh scoped
reads, docs to disk, ≤ 5-line progress notes. Clear scope between docs to keep context small.
No speculation. Expect ~1 turn per doc — state that up front and do not add extra passes.

---

## 7. ANTI-PATTERNS (each one costs a turn or a wave)

Reading this skill's non-existent `references/` · one tool call per message · sequential `subagent` calls
· subagents re-reading the manifest from disk · pasting doc bodies into the main thread ·
reviewing LOW docs · a second review pass "to be sure" · asking the user a question the ★ set
already answers · regenerating an unchanged doc · running the project's build/test commands
just to document them · writing into a requirements/spec file · a plan step inside a writer
subagent.

---

## 8. DISPATCH

Every wave of Turn 2 and Turn 3 is a set of `subagent` calls sent in ONE message. Each call
passes `agent` (`"oc-doc-writer"` or `"oc-doc-reviewer"`), a short `description` (the doc file
name), `prompt` (the filled template from §3.3 or §4) and `background: true`. Fire them all
without waiting, then end the turn. Each subagent's 5-line return arrives as it finishes, and
the next turn starts once every return of the wave is in. Read only those 5-line returns,
never a doc body, before reporting.

The agents `oc-doc-writer` and `oc-doc-reviewer` are installed from `opencode/agents/` next to this
file. They declare no model, so they run on the model selected in the OpenCode window.
Everything else in §§1-7 (turn budget, decision table, catalog, diff-skip, finish checks)
stays identical.
