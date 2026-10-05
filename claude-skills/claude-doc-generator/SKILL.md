---
name: claude-doc-generator
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

Turns a codebase into correct, readable Markdown docs in 2 concurrent waves plus 1 finish turn. The main thread selects and dispatches; workers read the manifest and their brief from disk, then write or review. `<brief dir>` is the absolute path of the `references/` directory next to this file.

Turn 1 (Recon + Load, one message) then Gate (Select; skipped or speculated through) then Wave 1 (writers plus indexer, one message) then Wave 2 (HIGH-tier reviewers and retries only, one message) then Finish (one bash call, one summary message).

## Speed contract (governs every decision)

1. At most 5 main-thread turns end to end (3 on a full cache hit). Never narrate between phases.
2. Batch independent calls (bash, Reads, launches) into one message.
3. At most min(live cap, 12) workers per wave, one message; more means consecutive waves, longest and HIGH-risk docs first. Read env `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` (default 20) as the live cap; never exceed it (extra launches fail, no retry).
4. One bash call per shell step; chain with `;`, `&&` and heredocs.
5. Short dispatch: never paste a brief or the manifest into a worker prompt. A worker prompt is about 5 lines (see Wave 1) telling it to read `.claude/doc-generator/recon.md` and its brief itself.
6. Models: writers, reviewers and the indexer run with `model: sonnet`; recon shards run with `model: haiku`. Set `model` explicitly on every launch.
7. Never redo work: the manifest cache and per-doc scope diffing skip docs whose inputs are unchanged.
8. Docs live on disk; each worker returns at most 5 lines. Never paste a doc body here.

**Quality floor:** every HIGH-tier doc (it makes verifiable technical claims) is reviewed against real code this run by a fresh worker, or skipped because its reviewed scope is byte-identical. LOW-tier docs ship on writer self-verification plus the finish checks, which escalate any LOW doc containing code or commands.

## Global rules

- **Read-only inputs.** Requirements and spec documents are sources: never edit or output into them. Generated docs go to `<output dir>`: `docs/generated/` if requirements live in `docs/`, else `docs/`. Rename any output that would collide with a read-only input.
- **No secrets in docs.** Use placeholders (`<API_KEY>`, `https://api.example.com`) for credentials, keys, tokens, passwords and real internal hosts or IPs. A leak is blocking at any tier.
- **Failures.** A failed worker is retried once, bundled into the next wave's message; a second failure is reported as a gap.

## Turn 1: Recon + Load

Send one message: the recon bash call below plus a Read of `references/doc-catalog.md` (manifest format and Gate template). Workers read the briefs.

The cache check runs inside the same bash call: a cached `HEAD:` equal to the current HEAD prints the manifest and exits (go straight to the Gate). A different HEAD also prints `git diff --name-only <old HEAD>..HEAD`: refresh only affected manifest sections and keep the list for diff-skip.

Small or medium repo (up to about 3000 files), exactly one bash call:

    { C=.claude/doc-generator/recon.md;
      if [ -f "$C" ] && [ "$(sed -n 's/^HEAD: //p' "$C")" = "$(git rev-parse HEAD)" ]; then
        echo "=== CACHE HIT ==="; cat "$C"; exit 0; fi;
      [ -f "$C" ] && { echo "=== DIFF since cached HEAD ==="; git diff --name-only "$(sed -n 's/^HEAD: //p' "$C")"..HEAD; };
      echo "HEAD: $(git rev-parse HEAD)"; echo "FILES: $(git ls-files | wc -l)";
      git ls-files | cut -d/ -f1-2 | sort | uniq -c | sort -rn | head -40;
      for m in package.json pyproject.toml requirements.txt go.mod Cargo.toml pom.xml composer.json; do
        [ -f "$m" ] && echo "== $m ==" && head -80 "$m"; done;
      for r in README* readme*; do [ -f "$r" ] && echo "== $r ==" && sed -n '1,150p' "$r"; done;
      for s in requirements/*.md specs/*.md spec/*.md docs/*.md; do
        [ -f "$s" ] && echo "== SPEC(READ-ONLY): $s ==" && sed -n '1,250p' "$s"; done;
      rg -n --no-heading -m 300 -e 'app\.(get|post|put|delete)' -e '@app\.route' \
         -e '@(Get|Post|Put|Delete)Mapping' -e 'func .*Handler' -e 'export (async )?function' \
         -e 'class .*(Model|Entity)' -e 'CREATE TABLE' -e 'interface .*\{';
    } 2>/dev/null

Signatures over bodies in recon.

Large repo or monorepo (over about 3000 files, or workspace manifests): launch up to 8 recon workers with `model: haiku`, one per package or top-level directory, in one message. Each runs the command scoped to its directory and returns a manifest fragment of at most 40 lines. For monorepos, ask which packages to document inside the Gate message.

Save the manifest to `.claude/doc-generator/recon.md` (format in `references/doc-catalog.md`) before any worker launches: in the Gate turn, or as the first call of the Wave 1 message. Never in its own turn.

## Gate: select

Skip when the user already named the docs (map to title and path, confirm in one line inside the Wave 1 turn) or the run is non-interactive (starred set).

Otherwise adapt the catalog from the manifest (no new reading) and send one tight numbered list where a bare "ok" selects the starred set. Default language is English.

In the same turn, compute each candidate doc's scope file list (from the manifest, no reads) and write `.claude/doc-generator/state.json` as `{doc: {path, scope: [...], head: <HEAD>}}`. When background workers are available, also launch the starred-set writers in the background (speculation): on "ok" Wave 1 is already done; otherwise keep the intersecting docs, delete the rest and launch only the delta. Never speculate reviews.

## Wave 1: Write + Index (one message, at most min(live cap, 12))

Diff-skip first: a selected doc in `state.json` whose scope has no file changed since its recorded `head`, and which exists, is `[cached]`: skip write and review.

Launch each with `model: sonnet`:

- One writer per remaining doc, with this prompt (the scope list is capped at about 12 files):

        Read .claude/doc-generator/recon.md, then <brief dir>/writer-brief.md, and follow the brief.
        Doc: <title> (<create|update>) for <audience>, language <language>.
        Output file: <output dir>/<slug>.md
        Scope (read only these files): <file list>
        Return the 4-line result the brief specifies.

- The indexer, same wave (it needs only titles, paths and purposes): "Read .claude/doc-generator/recon.md. Write <output dir>/README.md linking each of these docs, grouped technical and non-technical: <title, path, purpose list>. Return one line."

The writer brief carries the self-verification rules, the tiering rule (tier by final content: any command, endpoint, signature, schema, config value, code fence or file path means HIGH) and the return format.

## Wave 2: Review (HIGH only, one message)

Launch together (at most min(live cap, 12), each `model: sonnet`): one fresh reviewer per HIGH-tier doc (never its writer) plus any Wave 1 retries. Reviewer prompt:

    Read .claude/doc-generator/recon.md, then <brief dir>/reviewer-brief.md, and follow the brief.
    Doc under review: <output dir>/<slug>.md
    Scope (verify against these files only): <the writer's file list>
    Return PASS, FIXED or BROADLY_WRONG as the brief specifies.

LOW-tier docs get no reviewer; if every doc is LOW or `[cached]`, skip to Finish. One review pass only: on BROADLY_WRONG, re-run one writer plus one fresh reviewer for that doc in one small wave, never further.

## Finish: one script, one message

1. One bash call verifies and persists state (it runs no project commands):

        cd <output dir> && {
          for f in <selected files>; do [ -s "$f" ] || echo "EMPTY_OR_MISSING: $f"; done;
          grep -RhoE '\]\((\.?/?[^)#:]+\.md[^)]*)\)' *.md | tr -d '()' | sed 's/^]//' | sort -u |
            while read l; do [ -e "${l%%#*}" ] || echo "BROKEN_LINK: $l"; done;
          grep -RhoE '^\s*(npm|yarn|pnpm|pip|python|go|cargo|make|mvn) [a-z:-]+' *.md | sort -u;
          for f in <LOW-tier files>; do
            grep -qE '[`]{3}|(^|[[:space:]])(npm|yarn|pnpm|pip|python|go|cargo|make|mvn) ' "$f" && echo "LOW_HAS_CODE: $f"; done;
        } 2>/dev/null; cat > <repo root>/.claude/doc-generator/state.json <<'EOF'
        { "<current HEAD>": per-doc {path, scope, head} entries }
        EOF

2. Cross-check listed commands against the manifest `Commands:` line (existence only) and fix trivial breakage directly. Any `LOW_HAS_CODE` hit gets one reviewer (`model: sonnet`): the only path that may add a turn.
3. One summary message: created, updated and `[cached]` docs with paths; reviewer-flagged gaps needing a human (business rules code cannot reveal); anything that failed after its retry. Note `.claude/doc-generator/` can be deleted or gitignored.

## Environment fallback (no workers)

Where workers cannot be launched (for example a chat-only interface), run the same pipeline sequentially in the main thread with the same brief files, one doc at a time, reviewing only HIGH-tier docs with fresh scoped reads. No speculation; paste nothing into the conversation.

## Output language

Generated docs default to English regardless of code-comment language; use another language only when the user requests or confirms it in the Gate.
