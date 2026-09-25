---
name: doc-generator
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
self-contained: every brief, template and script you need is below. **Never read any
other file of this skill — there are none.** (Under the OpenCode harness, §8's
`scripts/oc_harness.py` is the one exception: it is executed as a subprocess, never read.)

---

## 0. EXECUTION CONTRACT — obey literally, do not re-derive

| # | Rule | Violation = bug |
|---|------|-----------------|
| R1 | **Turn budget ≤ 4** (cache hit: ≤ 2). Turn = one main-thread message. | Adding a turn a batch could absorb |
| R2 | **One message = all independent calls.** 1 bash + 10 Tasks go in ONE message. | Sending calls one at a time |
| R3 | **Concurrency = 10 subagents max per wave.** More docs → consecutive waves of 10, biggest doc first. | 11+ at once, or 1-at-a-time |
| R4 | **One bash call per phase.** Chain with `;` `&&` `2>/dev/null`. | Two bash calls in one phase |
| R5 | **Zero cold-start reads for subagents.** Inline the facts + brief + file list into every Task prompt. Its first tool call hits target code, never a brief or manifest file. | Subagent reading this skill or the manifest |
| R6 | **No narration.** No "Let me…", no phase summaries, no pasting doc bodies into the main thread. Docs live on disk. | Any prose between tool calls |
| R7 | **Reasoning effort: main thread `high`, subagents `low`.** Subagents follow a checklist; they must not deliberate. Say so in every Task prompt. | Deep reasoning on mechanical work |
| R8 | **Never redo work.** Diff-skip via `.zcode/doc-gen/state.json` before every wave. | Rewriting an unchanged doc |
| R9 | **Subagent returns ≤ 5 lines.** Never the doc body. | Long subagent returns |
| R10 | **Failure budget: 1 retry per doc, bundled into the next wave.** Never a dedicated retry turn, never a third attempt. | Retry loops |

**Turn ledger (target):**

| Turn | Content (single message) |
|------|--------------------------|
| 1 | 1 bash: cache check + recon + fact pack + state scaffold |
| 2 | 1 line of intent + 1 bash (index + dirs) + ≤ 10 writer Tasks |
| 3 | ≤ 10 reviewer Tasks (HIGH-tier only) + any 1 retry |
| 4 | 1 bash (mechanical verify + persist state) + final summary |

Skip Turn 3 entirely when no HIGH doc was written this run. Skip Turn 1's work on a cache hit.

---

## 1. DECISION TABLE — pick a row, act, do not deliberate

| Situation | Play |
|---|---|
| Cache hit (`HEAD` unchanged) + all scopes unchanged | Report `[cached]` list, ask nothing, stop at Turn 2 |
| User named specific docs | Use exactly those. Confirm in one clause inside Turn 2 |
| User said nothing specific | Auto-select the ★ set (§3.1). State it in one line, do not wait for approval |
| > 10 docs selected | Waves of 10, longest/HIGH first |
| Repo > 3000 files or monorepo | Turn 1 becomes: 1 bash (root recon) + up to 9 `Explore` shards, one per package — same message |
| No git repo | Recon script auto-falls back to a mtime hash; everything else identical |
| Requirements/spec docs found | Read-only sources. **Never** write into them. Rename any colliding output |
| Subagents unavailable in this harness | §6 sequential fallback |
| Subagent fails/returns junk | Retry once in the next wave's message. Fails twice → report the gap, never ship silently |

---

## 2. TURN 1 — RECON (exactly one bash call, nothing else)

Run this verbatim from the repo root. It checks cache, builds the manifest AND the fact
pack in one pass, and degrades gracefully with no git / no ripgrep.

```bash
S=.zcode/doc-gen; mkdir -p "$S"; {
H=$(git rev-parse --short HEAD 2>/dev/null); [ -z "$H" ] && H=$( (find . -path ./.git -prune -o -type f -print0 2>/dev/null | xargs -0 ls -la 2>/dev/null) | cksum | tr -d ' ' | cut -c1-12);
if [ -f "$S/recon.md" ] && [ "$(sed -n 's/^HEAD: //p' "$S/recon.md")" = "$H" ]; then echo "=== CACHE HIT ==="; cat "$S/recon.md"; cat "$S/state.json" 2>/dev/null; exit 0; fi
O=$(sed -n 's/^HEAD: //p' "$S/recon.md" 2>/dev/null); [ -n "$O" ] && { echo "=== CHANGED SINCE $O ==="; git diff --name-only "$O"..HEAD 2>/dev/null | head -200; }
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
You will paste slices of it into Task prompts; it never needs to be written to disk before Turn 2.

```
# Recon: <project>
HEAD: <hash>          Stack: <langs, frameworks>     Files: <n>
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

## 3. TURN 2 — PLAN + WRITE WAVE (one message: 1 line + 1 bash + ≤ 10 Tasks)

### 3.1 Catalog — include a row only when its condition holds

| ★ | Doc | File | Audience | Tier | Include when |
|---|-----|------|----------|------|--------------|
| ★ | Project overview | `README.md` | mixed | HIGH | always |
| ★ | Setup & run | `setup-guide.md` | dev | HIGH | always |
| ★ | Architecture | `architecture.md` | dev | HIGH | ≥ 2 modules/services |
| ★ | API reference | `api-reference.md` | dev | HIGH | FACTPACK has routes/handlers/public SDK symbols |
| ★ | Data model | `data-model.md` | dev | HIGH | models/entities/CREATE TABLE found |
| ★ | User guide | `user-guide.md` | non-tech | LOW | app has a UI/CLI end users touch |
| | Configuration | `configuration.md` | dev/ops | HIGH | ≥ 5 env vars or a config schema |
| | Deployment | `deployment.md` | ops | HIGH | Dockerfile/compose/CI/IaC found |
| | Testing guide | `testing.md` | dev | HIGH | test dirs found |
| | Contributing | `contributing.md` | dev | HIGH | user asks, or repo is open source |
| | Handover / ops | `handover.md` | mixed | HIGH | user says handover/onboarding/takeover |
| | FAQ / glossary | `faq.md` | non-tech | LOW | user asks |

Default run = the ★ rows whose condition holds (typically 4–6 docs → one wave).

### 3.2 Diff-skip (apply before launching anything)

For each selected doc with an entry in `state.json`: if the doc file exists **and**
`changed-files ∩ its scope = ∅` → mark `[cached]`, launch no writer and no reviewer.
If the recon printed no usable `CHANGED SINCE` list (shallow clone, rewritten history, no git),
treat every scope as changed — correctness beats the cache.

### 3.3 The one message

Send together, in this order, in a **single message**:

1. **One line of intent** — e.g. `Writing 5 docs to docs/: README, setup-guide, architecture, api-reference, user-guide (say "stop" to change the set).` Do not wait for a reply.
2. **One bash call** — creates the output dir and the index, deterministically, with no subagent:

```bash
D=<output dir>; mkdir -p "$D" .zcode/doc-gen; { echo "# Documentation"; echo; echo "_Generated $(date +%Y-%m-%d) from commit <HEAD>._"; echo; echo "## Technical"; for f in <HIGH files>; do echo "- [<title>](./$f)"; done; echo; echo "## Non-technical"; for f in <LOW files>; do echo "- [<title>](./$f)"; done; } > "$D/README_INDEX.md"
```
   (If the project overview itself lands at `$D/README.md`, name the index `README_INDEX.md` as
   above and link it from the overview; never overwrite a doc a writer owns.)
3. **≤ 10 writer Tasks**, subagent type `general-purpose`, one per non-cached doc, **each using this exact template**:

```
ROLE: Technical writer. Effort: low — follow the checklist, do not deliberate, no plan step.
GOAL: Write <output dir>/<file> — "<title>" for <audience>.

BUDGET (hard): ≤ 12 file reads, ≤ 15 tool calls, one write. Read ranges (sed -n '1,120p'),
never whole large files. Do not read this project's docs. Do not run project commands.

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
- Language: English.
- Never modify any file outside <output dir>. Read-only specs: <paths>.

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

### 3.4 Per-doc outlines (paste the matching one into the Task)

- **README.md** — one-paragraph what/why · key features (≤ 6 bullets) · quickstart (install→run→test, copy-pasteable) · project layout table · links to the other docs · license/support.
- **setup-guide.md** — prerequisites w/ versions · install · configuration (env table: var, required?, default, meaning) · run dev · run tests · common errors → fixes · verifying it works.
- **architecture.md** — 1 paragraph overview · component table (component, responsibility, path) · one ASCII/Mermaid diagram of request or data flow · key flows numbered end-to-end w/ `file:line` · design decisions & trade-offs · known limitations.
- **api-reference.md** — grouped by resource · per endpoint/function: signature, purpose, params table, returns, errors, one minimal example · auth section · versioning/stability note.
- **data-model.md** — entity table (name, table/collection, purpose, path) · per entity: field table (name, type, constraints, meaning) · relationships (list or Mermaid ER) · migrations/indexes if present.
- **user-guide.md** — who it's for · what it lets you do · task-oriented walkthroughs ("To do X: 1…2…3") · plain language, zero jargon, no code unless the user really types it · troubleshooting.
- **configuration.md** — full env/config table · per-environment differences · secrets handling policy (placeholders only) · precedence order.
- **deployment.md** — target environments · build artifact · deploy steps · rollback · health checks/monitoring · scaling notes.
- **testing.md** — test types & where they live · how to run each · how to write a new one · fixtures/mocks · coverage expectations · CI behaviour.
- **handover.md** — system in 1 page · access/accounts checklist (names only, never secrets) · routine operations · incident playbook · open risks & TODOs · who/what to ask next.

---

## 4. TURN 3 — REVIEW WAVE (HIGH tier only, one message, ≤ 10 Tasks)

Skip this turn entirely if every doc is LOW or `[cached]`. Reviewer ≠ the writer, fresh context,
subagent type `general-purpose`.

```
ROLE: Technical fact-checker with edit rights. Effort: low-to-medium. No report-then-fix —
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
7. Secrets — replace any real key/token/host with a placeholder. Blocking.
8. Links — relative links resolve inside <output dir>.
9. Clarity — rewrite any paragraph that is vague, duplicated, or padding. Keep it shorter.

RETURN EXACTLY 5 LINES:
path=<…>
verdict=<clean|fixed|broadly-wrong>
fixes=<n>
unresolved=<claims you could not verify within budget, or "none">
human=<questions only a human can answer, or "none">
```

`broadly-wrong` → rerun one writer + one fresh reviewer for that doc **together in one small
wave**. Never loop a third time.

---

## 5. TURN 4 — FINISH (one bash + one summary)

```bash
D=<output dir>; cd "$D" && { for f in <all selected files>; do [ -s "$f" ] || echo "EMPTY: $f"; done
grep -RhoE '\]\(\.?/?[^)#? ]+\.md[^)]*\)' *.md 2>/dev/null | tr -d '()' | sed 's/^\]//;s/#.*//' | sort -u | while read -r l; do [ -e "$l" ] || echo "BROKEN_LINK: $l"; done
grep -RhoE '(npm|pnpm|yarn|pip|python3?|go|cargo|make|mvn|docker|uv)( [a-z][a-zA-Z0-9:._-]*){1,3}' *.md 2>/dev/null | sort -u
grep -RnoE '(sk-[A-Za-z0-9]{12,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY|password[[:space:]]*[:=][[:space:]]*["'"'"'][^"'"'"']{6,})' *.md 2>/dev/null | head -20 | sed 's/^/SECRET_SUSPECT: /'
grep -c 'TODO(human)' *.md 2>/dev/null | grep -v ':0$' | sed 's/^/TODOS: /'
BT=$(printf '\140'); for f in <LOW files>; do grep -qE "$BT$BT$BT|(^|[[:space:]$BT])(npm|pnpm|yarn|pip|python3?|go|cargo|make|mvn|docker) " "$f" 2>/dev/null && echo "LOW_HAS_CODE: $f"; done; } 2>/dev/null; cd - >/dev/null; mkdir -p .zcode/doc-gen; cat > .zcode/doc-gen/state.json <<'EOF'
{"head":"<HEAD>","docs":{"<file>":{"scope":["<paths>"],"tier":"<HIGH|LOW>","head":"<HEAD>"}}}
EOF
printf 'HEAD: %s\n' "<HEAD>" > .zcode/doc-gen/recon.md; cat >> .zcode/doc-gen/recon.md <<'EOF'
<the manifest from §2>
EOF
```

Then:

- Cross-check the printed command list against `Commands:` — existence only, never execute.
- Fix trivial breakage (`BROKEN_LINK`, stray path) yourself in this same turn with direct edits.
- `SECRET_SUSPECT` → fix immediately, blocking.
- `LOW_HAS_CODE` → one reviewer Task for that doc only (the sole path allowed to add a turn).
- **Final summary message** (compact): created / updated / `[cached]` docs with paths · index path ·
  `TODO(human)` questions that need a human · anything still failing after its one retry ·
  note that `.zcode/doc-gen/` is a cache and can be gitignored or deleted.

---

## 6. FALLBACK — harness without subagents

Same pipeline, sequential, same inlined briefs. Keep: one batched bash per phase, diff-skip,
self-verify while writing, review HIGH docs only with fresh scoped reads, docs to disk, ≤ 5-line
progress notes. One doc at a time, clearing scope between docs to keep context small. No
speculation. Expect ~1 turn per doc — state that up front and do not add extra passes.

---

## 7. ANTI-PATTERNS (each one costs a turn or a wave)

Reading this skill's non-existent `references/` · one tool call per message · sequential Tasks
· subagents re-reading the manifest from disk · pasting doc bodies into the main thread ·
reviewing LOW docs · a second review pass "to be sure" · asking the user a question the ★ set
already answers · regenerating an unchanged doc · running the project's build/test commands
just to document them · writing into a requirements/spec file · a plan step inside a writer
subagent.

---

## 8. OPENCODE LANE (harness = opencode)

`sh skills/glm/_shared/sync.sh` copies `_shared/oc_harness.py` into this skill's `scripts/`
directory, printing `synced <path>` for the copy — never edit the copy, only
`skills/glm/_shared/oc_harness.py`. This skill has no tool-free text-only fan-out, so it does not
get a `zai_client.py` copy. Once installed, `opencode/agents/doc-writer.md`,
`opencode/agents/doc-reviewer.md` and `opencode/commands/docs.md` are rendered into this OpenCode
major's dialect and the `/docs` command is available.

Under the OpenCode harness, Turn 2's writer wave and Turn 3's review wave replace each Task call
with one lane dict per doc (keys `id`, `agent: "doc-writer"`, `model: "flash"`, `dir`, `brief`),
the same fact packs and briefs as §3.3 and §4 inlined as `brief`. Write the lanes to a JSON file,
then run:

```
python3 <skill_dir>/scripts/oc_harness.py run <lanes.json> --out <out_dir> --width 10
```

`<skill_dir>` is the path `/docs` injects for this skill. This runs the whole wave concurrently
and writes `<out_dir>/<id>.jsonl`, `.err` and `.done` per lane.

Set `model` on every lane — `oc_harness.MODELS` maps `"flash"` to `glm-5.3-flash` and `"pro"` to
`glm-5.3`; omitting it makes `build_run_cmd` default the lane to `glm-5.3`, silently overriding
doc-writer's flash. Writer lanes use `model: "flash"`; reviewer lanes use `agent: "doc-reviewer"`
with `model: "pro"`, same pattern otherwise.

Effort is not controllable on process lanes: v1 drops `reasoning_effort` for `glm-*` models, and
v2 does not yet send `request.body` overlays either, so every writer and reviewer lane runs at
GLM's default `max` regardless of the `effort` key in `doc-writer.md`/`doc-reviewer.md`
frontmatter. Once the `run` command exits, read each lane's 5-line return from
`<out_dir>/<id>.jsonl` — never every doc body back — before reporting. Everything else in §§1-7
(turn budget, decision table, catalog, diff-skip, finish checks) stays identical.

---

## Appendix A — optional ZCode subagents (paste once, then reference by name)

Cuts per-Task prompt size and forces low thinking effort. `~/.zcode/agents/doc-writer.md`:

```markdown
---
name: doc-writer
description: Writes one Markdown doc from an inlined fact pack and a scoped file list. Never plans, never deliberates.
thoughtLevel: low
maxTurns: 18
---
You write exactly one Markdown file to the path given. Read only the files listed in SCOPE, in
ranges. Every technical claim must trace to FACTS or a file you read; anything else becomes
`TODO(human): …`. Never copy secrets. Never touch files outside the output dir. Return the
5-line block requested, nothing else.
```

`~/.zcode/agents/doc-reviewer.md`:

```markdown
---
name: doc-reviewer
description: Fact-checks one generated Markdown doc against real source code and fixes it in place.
thoughtLevel: low
maxTurns: 22
---
You verify one Markdown file against the code and edit it in place — you never write a report
instead of a fix. Check commands, paths, endpoints, signatures, env vars, schema fields,
invented behaviour, secrets, links, clarity — in that order, until the budget runs out. Return
the 5-line block requested, nothing else.
```

## Appendix B — harness settings that matter for this pipeline

GLM-5.3 and GLM-5.3-Flash keep reasoning always on (it cannot be disabled) and expose
`reasoning_effort` at `low | high | max`; both carry a 1M-token context and 128K max output.
For this skill: **main thread `high`** (routing and batching decisions), **subagents `low`**
(they execute a checklist), `max` only for a `broadly-wrong` rewrite. Z.ai's own recommended
sampling for these models is `temperature: 1`, `top_p: 0.95`, with streaming and `tool_stream`
enabled — tool streaming is what lets a 10-Task wave start moving immediately. GLM-5.3-Flash is
the right model for recon shards and any mechanical pass; keep writers and reviewers on GLM-5.3.
