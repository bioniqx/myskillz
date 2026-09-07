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

# Documentation Generator — Max-Throughput Pipeline

Turns a codebase into correct, readable Markdown docs in **2 concurrent waves + 1 finish turn**:

- **Turn 1 — Recon + Load**: ONE message = one batched bash (cache check + recon + spec reads) **plus** parallel Reads of all `references/*.md` briefs. After this turn, nothing else is ever read on the main thread.
- **Gate — Select** (skipped whenever possible; speculated through when not).
- **Wave 1 — Write + Index**: up to 64 parallel writer subagents **plus the indexer**, one message.
- **Wave 2 — Review**: HIGH-risk reviewers + any retries only, one message.
- **Finish**: one bash (verify + persist state) → one summary message.

## Speed contract (read first — this governs every decision)

Wall-clock time ≈ (serial main-thread turns × turn latency) + (longest subagent per wave). Optimize both:

1. **Serial-turn budget: ≤ 5 main-thread turns end-to-end** (≤ 3 on a full cache hit). Never add a turn that a wave, a batched message, or a script could absorb. Never narrate between phases.
2. **Batch everything independent into one message.** Multiple tool calls with no data dependency (bash + several Reads; 64 Task launches) always go in a single message so they run simultaneously. A tool call that could have shared a message with another is a bug.
3. **Concurrency budget: 64 subagents per wave**, all launched in one message. More than 64 → consecutive waves of 64, longest/HIGH-risk docs first.
4. **One bash call per shell step.** Chain with `;`, `&&`, heredocs, `2>/dev/null`. Recon, spec-reading, verification, and state persistence are never split into separate calls when they can chain.
5. **Zero cold-start reads for subagents.** The main agent inlines the (condensed) writer/reviewer brief text and the scoped file list directly into each Task prompt. A subagent's first tool call is on its target files, never on a brief or the manifest file.
6. **Model routing.** Writers and HIGH reviewers → default (strong) model. Recon shards and the indexer → fastest available model (e.g. Haiku) via the Task `model` field. Mechanical work never runs on the strong model.
7. **Never redo work.** Manifest cache + per-doc scope diffing make re-runs incremental: a doc whose input files are unchanged is skipped entirely.
8. **Context diet.** Manifest ≤ 150 lines (slice per doc for huge repos). Docs live on disk; each subagent returns **≤ 5 lines**. Never paste doc bodies into the main thread.

**Quality floor (non-negotiable even at max speed):** every doc containing verifiable technical claims (commands, paths, endpoints, signatures, schemas, config — i.e. HIGH tier) was either (a) reviewed against real code this run by a fresh subagent, or (b) skipped because its previously-reviewed scope is byte-identical. LOW-tier docs (pure narrative, zero technical claims) ship on writer self-verification + the mechanical finish checks; the finish script auto-detects a LOW doc that actually contains code or commands and escalates it to review before shipping.

## Global rules (every phase)

- **Read-only inputs.** Requirements/spec documents are sources, never targets. **NEVER edit, overwrite, or output into them.** Generated docs go to `<output dir>` — default `docs/generated/` if requirements live in `docs/`, else `docs/`. Rename any output that would collide with a read-only input. Record read-only paths in the manifest.
- **No secrets in docs.** Never copy credentials, API keys, tokens, passwords, or real internal hostnames/IPs/URLs into any doc. Use placeholders (`<API_KEY>`, `https://api.example.com`). A leaked secret is a blocking issue at any tier.
- **Failure handling.** If a subagent fails, times out, or returns nothing usable, retry it once **bundled into the next wave's message** (never a dedicated turn). If it fails again, report the gap explicitly — never silently ship a missing or unreviewed doc.

## Turn 1 — Recon + Load (one message)

Send in a **single message**: the recon bash call below **and** parallel Read calls for `references/doc-catalog.md`, `references/writer-brief.md`, `references/reviewer-brief.md`. All briefs are in context before any decision is needed; condensed versions get inlined into subagent prompts later.

**Cache check runs inside the same bash call.** If `.claude/doc-generator/recon.md` exists and its `HEAD:` equals `git rev-parse HEAD` → reuse the manifest and jump straight to the Gate (the bash call prints the cached manifest and exits early). If HEAD differs → the call also emits `git diff --name-only <old HEAD>..HEAD`; refresh only affected manifest sections and keep the changed-file list for diff-skip. Full re-recon only if the diff is large.

**Small/medium repo (≤ ~3000 files): exactly ONE batched bash call** — note spec/requirements reading is folded in (no second call):

```bash
{ C=.claude/doc-generator/recon.md;
  if [ -f "$C" ] && [ "$(sed -n 's/^HEAD: //p' "$C")" = "$(git rev-parse HEAD)" ]; then
    echo "=== CACHE HIT ==="; cat "$C"; exit 0; fi;
  [ -f "$C" ] && { echo "=== DIFF since cached HEAD ==="; git diff --name-only "$(sed -n 's/^HEAD: //p' "$C")"..HEAD; };
  echo "HEAD: $(git rev-parse HEAD)";
  echo "FILES: $(git ls-files | wc -l)";
  git ls-files | cut -d/ -f1-2 | sort | uniq -c | sort -rn | head -40;
  for m in package.json pyproject.toml requirements.txt go.mod Cargo.toml pom.xml composer.json; do
    [ -f "$m" ] && echo "== $m ==" && head -80 "$m"; done;
  for r in README* readme*; do [ -f "$r" ] && echo "== $r ==" && sed -n '1,150p' "$r"; done;
  for s in requirements/*.md specs/*.md spec/*.md docs/*.md; do
    [ -f "$s" ] && echo "== SPEC(READ-ONLY): $s ==" && sed -n '1,250p' "$s"; done;
  rg -n --no-heading -m 300 \
     -e 'app\.(get|post|put|delete)' -e '@app\.route' -e '@(Get|Post|Put|Delete)Mapping' \
     -e 'func .*Handler' -e 'export (async )?function' \
     -e 'class .*(Model|Entity)' -e 'CREATE TABLE' -e 'interface .*\{' ;
} 2>/dev/null
```

Signatures over bodies: never read full source files during recon.

**Large repo / monorepo (> ~3000 files or workspace manifests): sharded parallel recon.** Spawn up to 16 recon subagents on the **fast model** — one per package or high-signal top-level directory — in a single message (the reference Reads ride in the same message). Each shard runs the batched command scoped to its directory and returns a ≤ 40-line manifest fragment; concatenate into the manifest. For monorepos, ask which package(s) to document *inside the Gate message* — never a separate turn.

Write `.claude/doc-generator/recon.md` (dense, factual — it feeds every subagent) **in the same turn as the Gate/Wave-1 action, never alone**:

```
# Recon: <project name>
HEAD: <git rev-parse HEAD>
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

## Gate — Propose & select (eliminate or hide this pause)

**Skip conditions (zero extra turns):**
- User already named the docs → map to title + output path, confirm in one line **inside the Wave-1 launch turn**, go.
- Non-interactive run → use the ★ starter set immediately.

Otherwise: from the manifest + the already-loaded catalog (no new reading), adapt the catalog (drop unsupported rows, add stack-specific ones, tag `[create]`/`[update]`, mark the ★ starter set). Send **one tight message**: numbered list + defaults acceptable with one word (Language: default **English**; ask about audience only if it materially changes a doc). Phrase it so a bare "ok" selects the ★ set.

**Prefetch in the same turn:** compute each candidate doc's scoped file list (from the manifest, no reads) and write `.claude/doc-generator/state.json` as `{doc: {path, scope: [...], head: <HEAD>}}` (bash call batched into the proposal turn). When the user replies, Wave 1 launches with zero prep.

**Speculate through the wait (when the environment supports background subagents):** in the same turn as the proposal, launch the ★-set writers in the **background**. If the user accepts the defaults, Wave 1 is already done or nearly done — harvest and go straight to Wave 2. If they pick a different set, keep the intersecting docs, discard the rest (delete unwanted files), and launch only the delta. Speculation trades tokens for wall-clock time — exactly the priority here. Never speculate the review wave.

## Wave 1 — Write + Index (up to 64 parallel, one message)

**Diff-skip first.** For each selected doc with an entry in `state.json`: if (changed files since its recorded `head`) ∩ scope = ∅ and the doc exists on disk → mark `[cached]`, skip write *and* review. The biggest re-run speedup — apply it always.

Launch in **one single message** (≤ 64; overflow → next wave, longest docs first):

- **One writer per remaining doc.** Prompt contains, inlined: the manifest (or its slice), its scoped file list (cap ~12 files; read internals only where the doc requires them, else signatures), and the condensed writer brief plus:
  - **Self-verify before returning** (kills most review work): every quoted command matches the manifest `Commands:` line or a real script name; every quoted path exists in the file index; no secrets; every relative link points at a planned output path.
  - **Tier by final content, not intent:** after writing, if the doc contains any command, endpoint, signature, schema, config value, code fence, or file path → `HIGH`; only a doc with zero such content is `LOW`.
  - **Return ≤ 5 lines:** title, output path, risk tier, flags.
- **The indexer (fast model), in this same wave** — it needs only titles, paths, and one-line purposes, all known at selection time from the catalog + `state.json`, so it never waits for writers: writes `<output dir>/README.md` linking every doc (grouped technical / non-technical).

The doc lives on disk — never paste doc bodies into the main thread.

## Wave 2 — Review (HIGH only, one message)

Launch simultaneously, total ≤ 64:

- **One reviewer per HIGH-tier doc** — a fresh subagent on the **strong model**, never the writer. Inlined condensed reviewer brief. Full check against actual code (scoped reads only): commands, signatures, endpoints, schemas, drift vs. requirements — and **rewrite weak parts in place** (check + fix in one shot; no report-then-fix round trip).
- **LOW-tier docs get no reviewer.** They are covered by writer self-verification plus the mechanical finish checks; the finish script escalates any misclassified one.
- **Any Wave-1 retries** (see Failure handling).

If Wave 2 is empty (all docs LOW or `[cached]`) skip straight to Finish — a whole turn saved.

Default to a single review pass. Only if a reviewer reports a doc *broadly wrong*: re-run one writer + one fresh reviewer for that doc together in one small wave. Never loop further.

## Finish — one script, one message

1. **One bash call** verifies everything *and* persists state (no execution of project commands):

```bash
cd <output dir> && {
  for f in <selected files>; do [ -s "$f" ] || echo "EMPTY_OR_MISSING: $f"; done;
  grep -RhoE '\]\((\.?/?[^)#:]+\.md[^)]*)\)' *.md 2>/dev/null | tr -d '()' | sed 's/^]//' | sort -u | \
    while read l; do [ -e "${l%%#*}" ] || echo "BROKEN_LINK: $l"; done;
  grep -RhoE '^\s*(npm|yarn|pnpm|pip|python|go|cargo|make|mvn) [a-z:-]+' *.md 2>/dev/null | sort -u;
  for f in <LOW-tier files>; do
    grep -qE '```|(^|[[:space:]])(npm|yarn|pnpm|pip|python|go|cargo|make|mvn) ' "$f" && echo "LOW_HAS_CODE: $f"; done;
} 2>/dev/null; \
cat > <repo root>/.claude/doc-generator/state.json <<'EOF'
{ "<current HEAD>": per-doc {path, scope, head} entries }
EOF
```

2. Cross-check listed commands against the manifest `Commands:` line (existence only). Fix trivial breakage directly in this turn. Any `LOW_HAS_CODE` hit → launch one strong-model reviewer for that doc (bundled with nothing else; this is the only path that may add a turn, and only on misclassification).
3. **One summary message:** created / updated / `[cached]` docs with paths; reviewer-flagged gaps needing a human (e.g. business rules code can't reveal); anything that still failed after its retry. Note `.claude/doc-generator/` can be deleted or gitignored.

## Environment fallback (no subagents)

Some environments (e.g. the Claude.ai chat interface) cannot spawn subagents. Run the same pipeline **sequentially in the main thread** with the same inlined briefs, keeping every speed rule that still applies: batched single bash calls, diff-skip via `state.json`, self-verify while writing, review only HIGH-tier docs (with fresh scoped reads), docs written to disk and summarized — never pasted into the conversation. Process one doc at a time to keep context small. No speculation in this mode.

## Output language rule

Generated docs default to **English** — the usual language for stakeholder and handover documentation — regardless of the language of code comments. Use another language only when the user requests or confirms it in the Gate. The skill's own instructions stay English.
