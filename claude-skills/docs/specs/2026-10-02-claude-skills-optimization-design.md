# claude-skills: bug fixes, token and speed optimization, tier rebalancing — Design

Date: 2026-10-02 · Status: approved by the user in the brainstorming session (decisions in §9) · Scope: `claude-skills/` only

## 1. Goal

Make every skill in this repo run correctly on Claude Code, with fewer tokens loaded and fewer
tool rounds, with about 20% of the work (decisions, security review, integration) on the main
model (Opus/Fable) and about 80% on Sonnet 5.5 subagents.

Baseline (measured 2026-10-02): `python3 -m unittest discover -s tests` = 406 tests, OK, 1 skipped,
~128 s. SKILL.md sizes: dev-team 24.9 KB, brainstorming 14.9 KB, requirements-code-audit 14.4 KB,
doc-generator 14.2 KB, writing-plans 9.3 KB, systematic-debugging 9.0 KB, frontend-design 8.3 KB,
git-diff-summary 5.4 KB.

## 2. Approach

Three waves, one Sonnet worker per workstream (disjoint file footprints, own git worktree), RED→GREEN
commits per this repo's convention for script changes. The main model owns the decisions in §5, reviews
every hook/engine diff in full, spot-checks mechanical diffs, and does final integration.

- Wave 1 — bug fixes with tests (§4). Highest value, independent per skill.
- Wave 2 — token and tier changes (§6, §7). Starts per workstream after that workstream's wave 1 lands.
- Wave 3 — integration (§8): concurrency docs, cross-skill consistency, full-suite run, size report.

Rejected: (A) bugs only — misses the token/speed goal; (C) shared-conventions-first — adds a serial
step for little gain.

## 3. Workstreams and footprints

Each workstream is one worker that does its wave 1 fixes, then its wave 2 token/tier changes, on the
same files (so no two workers ever share a file). W3 starts after W1 and W2 land because its wording
depends on the engine's output (model lines, stall hint) and guard behavior.

| WS | Footprint | Tests |
|---|---|---|
| W1 dev-team engine | `dev-team-v3.2/scripts/devteam.py` | `tests/test_devteam_*.py` |
| W2 dev-team guard | `dev-team-v3.2/scripts/guard.py` | `tests/test_guard_*.py` |
| W3 dev-team prompts | `dev-team-v3.2/SKILL.md`, `agents/*.md`, `README.md`, `references/` (after W1, W2) | none (size check) |
| W4 requirements-code-audit | whole dir | `tests/test_audit_*.py`, `tests/test_agent_hooks.py` |
| W5 writing-plans | `writing-plans-6.2/` | `tests/test_plan_*.py` |
| W6 systematic-debugging | `systematic-debugging-6.3/` | `tests/test_debug_scripts.py` |
| W7 brainstorming | `brainstorming-6.3/` | `tests/test_brainstorm_*.py` |
| W8 doc-generator | `doc-generator/` | none (see §4 W8) |
| W9 git-diff-summary + frontend-design | `git-diff-summary/`, `frontend-design-Jun18/` | `tests/test_gather.py` |

## 4. Wave 1 — bug fixes (status: C = reproduced or code-confirmed in this session, U = reported by an audit lane, not yet verified)

**W1 devteam.py**
- C: `finish` ignores checkpoint state, pending checkpoints, merges after the last pass, and a CHANGES_REQUIRED verification verdict. Fix per D5.
- C: `do_integrate` aborts the whole `next` on any dirty tracked file in the root. Reuse the dirty-check that excludes files `doctor --fix` rewrites (as `init` does); block only on paths the slice touches.
- U→design: no stall detection for lanes that crash without a `.done`/`.blocked` marker. Per D2.
- U: a CHANGES_REQUIRED review keeps its non-APPROVED shards reserved for the rest of the run (verify whether the Conductor resumes them; if not, release when fix slices are queued).
- Per D1: `next` prints `model: sonnet` on incremental REVIEW dispatch lines and `model: opus` for the final review (today it prints no model, so every review runs on Opus at high effort).

**W2 guard.py**
- C: read-only roles are denied harmless commands (`grep -rn install src`, `rg -n touch src`, `ls | grep -i dd`, `cat x | grep ln`); quoted forms pass. Per D3.
- C: `stop_blocks` is never reset on claim/resume, so after `MAX_STOP_BLOCKS` over a slice's lifetime the Stop gate is a no-op. Reset on claim and on resume after REJECTED.

**W3 dev-team prompts**
- U: `SKILL.md` relies on `SendMessage`/`TaskStop` without loading them where they are deferred tools. Add: "if the call fails because the tool is not available, load it with ToolSearch `select:SendMessage,TaskStop`" in the Phase 1 first-turn batch.
- U: `programmer.md` contradicts itself on the pinned `PORT=… DB_SUFFIX=…` env prefix. Reword to "except the pinned prefix".
- U: `team-leader.md` frontmatter omits `Edit`; confirm against its body and fix.
- U: `experimental: cacheTtl` frontmatter key looks inert; verify against the sub-agents doc, remove if unsupported.

**W4 requirements-code-audit**
- C: `audit_guard.py` Grep/Glob branch only blocks `.git` paths, so repo-wide Grep returns `.md` prose hits into the evidence. Per D4.
- C(corrected): `write_verify_file` does pass the investigator `SPEED_RULES` into verifier briefs (a verify lane reported this "refuted", but its own evidence shows the text is included); it says "~6 calls" and "a second verifier re-checks every non-MATCHED item", contradicting the verifier stance. Give verify briefs their own budget line.
- U: `out_dir not in cmd` substring check and the any-path-containing-`.claude` Read allowance are too loose. Anchor to redirect targets; narrow the allowance.
- U: parser `effort high` for a mechanical one-section decomposition → medium. Parse threshold 2,500 words → ~800 words so parsers (Sonnet) do the decomposition instead of the main model.

**W5 writing-plans**
- U: task hash covers only the task's own contract text; a changed producer leaves dependents (implicit Consumes) with stale bodies. Include producers' text for `deps_all`.
- U: `--allow` needs the exact matched text (`subagent` vs `subagents`, `Task tool`). Allow by stem/regex.
- U: re-running `contracts` re-prints DISPATCH rows for groups whose tasks all have a fresh `.ok` mark. Skip them.
- U: linter does not catch `git commit -a` or a commit without `git add`.
- U: add tests for `partition`, review picking, `assemble`, `setup`, `spec_coverage` (currently uncovered).

**W6 systematic-debugging**
- C: `find-polluter.sh` blames the first test when a leftover untracked, non-ignored pollution file is copied into the isolated worktrees via the untracked tar. Exclude/reject the pollution path before the tar and remove it after `reset_tree`.
- U: `find-polluter.sh` find excludes only `node_modules`/`.git`; also exclude the `--link` dirs, `dist`, `.venv`, `.claude`.
- U: `snapshot.sh` does `cd "$1"` before sourcing `_lib.sh` (relative `$0` breaks, CPU count silently lost). Source first.
- U: `bisect-parallel.sh` between-round `clean -fdq` lacks `-x` (stale ignored build output → false good/bad); use `-fdxq` then relink deps.
- U: `stress.sh` `-b 0/0` divides by zero; stale `rc.*`/`FAIL.*` in a reused `-o` dir inflate counts.
- Add black-box tests (RED first) for find-polluter detection, snapshot, and the Fisher/Wilson output. Keep bash 3.2 compatibility.

**W7 brainstorming**
- U: hand-off names `writing-plans`; the installed skill is `writing-plans-6.2`. Name it exactly, with a fallback to the unversioned name.
- U: `research-playbook.md` cites the claim-verifier at the wrong `architectural.md` section (§4 vs §3).
- U: Round 1 batches ToolSearch with calls to deferred tools (WebSearch/WebFetch). Make round 1 = ToolSearch + reads + Agent lanes; deferred-tool calls follow once loaded, or note "load first, call in the same round only if already available".
- U: the spec turn always runs `git add/commit`, which conflicts with a user rule against committing self-initiated `.md` files (§9 decision 2). Make the commit step conditional: commit only when neither the user nor a loaded CLAUDE.md says not to; otherwise leave the spec untracked and say so in the review-gate message. Also add `Bash(git add:*)`/`Bash(git commit:*)` to `allowed-tools` only if `allowed-tools` pre-approval is confirmed to cover later turns (unverified; otherwise leave unchanged).

**W8 doc-generator**
- U: `rg -m 300` caps per file, not total; pipe to `head -300`, fall back to `git grep` when `rg` is missing.
- U: `state.json` shape contradicts itself between the two places it is described; use the per-doc form.
- U: cache/diff-skip compare only committed HEAD; add `git status --porcelain` to the cache key; exclude the output dir from READ-ONLY spec reads on re-run.
- No existing tests: add one small black-box check only for any script logic touched; prompt-only changes verified by size/lint of frontmatter.

**W9 git-diff-summary + frontend-design**
- U: `"$ARGUMENTS"` unescaped in the `!` block; base given as SHA/tag yields `NO_BASE` (only `refs/heads` checked). Validate and check via `rev-parse`.
- U: `READ_MAX=200000` can put ~55k tokens of diff in the main context → ~80000; cap total FAN_OUT with a top-N-files summary.
- `frontend-design-Jun18` has the same name/description as the `frontend-design:frontend-design` plugin skill; trim the body (writing section → on-demand reference) and change the description so the two do not compete for the same triggers. Do not delete.

## 5. Decisions owned by the main model (settled here; workers implement, main reviews)

- **D1 Tier policy.** Main model: classification, design, synthesis, security review of hooks/engine, final verification. Sonnet: all lanes, writers, investigators (including requirements-code-audit investigators, user decision), reviewers of incremental batches, hypothesis-experiment agents, doc-generator writers/reviewers/indexer, team-leader PLAN ADOPTION, plan-reviewer. Opus retained only for: dev-team final review, team-leader PLANNING and VERIFICATION, audit adjudication by the lead. Haiku stays only where it is today for single-fact locate/lookups. Every lane prompt template and agent frontmatter states its `model` explicitly (Explore inherits the main model since v2.1.198). `Tier: deep` writers → sonnet; `light` → sonnet (haiku causes lint churn).
- **D2 Stall detection.** `next`/`status` print `STALLED?` for in-flight lanes with no `.done`/`.blocked` marker older than N minutes (default 20, env override), with the exact `retry` command. Print only; never auto-act.
- **D3 Read-only Bash policy in guard.** Parse with `shlex` per pipeline segment (`|`, `&&`, `||`, `;`); deny mutating tools only at command position, including through `sh -c`, `xargs`, `env`, `sudo`, `time` wrappers; keep redirect/`tee`/in-place flag detection; on parse failure fall back to the current conservative deny. All existing deny tests must still pass; add the allow cases above as tests. Main model reads this diff fully.
- **D4 Audit Grep/Glob policy.** Deny Grep/Glob whose scope can include prose docs unless the call excludes them (`glob` containing `!*.md` and the other doc extensions the Read branch's `is_doc_path` blocks); the deny message states the exact allowed form; worker prompts include it. Add tests.
- **D5 `finish` gate.** Raise unless: last checkpoint passed, none pending, no merges since it, no CHANGES_REQUIRED verification verdict. `--force` stays and prints exactly which conditions it bypassed.

## 6. Wave 2 — token reduction

- Targets: every `SKILL.md` ≤ ~14 KB (≈ ≤ 4k tokens, so the whole file survives post-compaction re-attachment, which keeps only the first 5,000 tokens per skill); dev-team ≤ ~12 KB, brainstorming/audit/doc-generator ≤ ~10 KB. Critical routing and hard rules first, rationale and rarely-used tables to `references/` read on demand.
- dev-team: move the task-type table, plan format (duplicates `devteam plan-template` and team-leader.md), "why it is fast" and profile rationale out of SKILL.md; trim `programmer.md` Modes to one-liners (the `claim` briefing is authoritative).
- brainstorming: move lane prompts to `lanes.md` (read only when T1 lanes are planned); drop Merge rules and Checklist that repeat earlier text; cut the "Why inline" history in the reviewer prompt.
- requirements-code-audit: move "Why this design is fast" out; in plugin/local mode skip the rules block in batch files (the agent files already carry it) and target 2–3 items per batch.
- systematic-debugging: move the red-flags table to `references/`; split playbook recipes per tool so SWARM loads one.
- doc-generator: main model stops hand-writing N full prompts; subagents read `recon.md` and the brief files themselves; the dispatch prompt is ~5 lines. Writers/reviewers get `model: sonnet` (D1).
- devteam.py output: print counts instead of the full WAITING list unless stuck; print the endgame block once; use a short script path in launch lines; programmer final message = Status + Worktree only, detail in a report file the engine does not need to read (verify the Conductor never needs it first).
- writing-plans: reviewer brief inlines the task bodies; reviewers use the lightweight writer agent when installed; fan out writers from N ≥ 2 tasks.
- Descriptions (`description` + `when_to_use`) ≤ 1,024 characters for portability (Claude Code truncates at 1,536).

## 7. Wave 2 — speed

- Fewer tool rounds and no failed first calls (deferred-tool loading in W3/W7).
- Lower serial work on the main model (D1, doc-generator prompts, parser threshold).
- `gather.sh` READ_MAX and FAN_OUT caps (W9).

## 8. Wave 3 — integration and verification

- Concurrency: Claude Code's default cap is 20 concurrent subagents (needs v2.1.217+); a 64-wide design must set `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`. Ensure each skill's docs/doctor output says so; do not assume 64.
- Plugin agents ignore their own `hooks`/`mcpServers`/`permissionMode` frontmatter; confirm requirements-code-audit's enforcement lives in plugin-level `hooks/`, and that no agent file in this repo depends on frontmatter `hooks` when shipped as a plugin.
- Verification: per-workstream targeted test module after each worker; full suite once at the end in the background (~128 s) — must be ≥ 406 tests, all passing; before/after `wc -c` table for every `SKILL.md`, agent file and playbook; a frontmatter sanity check (YAML parses, required fields, description length).
- Review: main model reads W1/W2/W4 diffs fully (engine and hooks, security-sensitive); other diffs by risk.
- Self-modification: workers use git worktrees; the installed dev-team copy in `~/.claude/skills` runs the work while the repo copy is edited.

## 9. User decisions and assumptions

1. Approved the three-wave design as-is.
2. Spec and plan files are NOT committed; they stay untracked in `docs/` (overrides the skill's mandatory commit; the repo's RED→GREEN commits for script changes are unaffected).
3. Do NOT sync to the installed copies (`~/.claude/skills`, `~/.claude/agents`, settings). Known leftover: the installed `plan-task-writer` still contains the unreplaced `__PLAN_TOOL__` placeholder (verified), so the writing-plans auto-lint hook fails there until the user runs `plan_tool.py setup --apply`. Report this at the end; do not run it.
4. requirements-code-audit investigators move to Sonnet (instead of Haiku with extra MATCHED verification).
5. Assumptions: only files under `claude-skills/` change; the sibling `hybrid`, `glm-skills` dirs and the pending deletions in the parent repo are untouched; existing observable CLI output formats stay stable except where a finding requires a change (grep `tests/` for asserted strings first); `frontend-design-Jun18` is trimmed and re-described, not deleted; `effort` and `omitClaudeMd` frontmatter are not relied on for savings (honored-ness unverified).

## 10. Evidence

- Default concurrent-subagent cap is 20, override via env, needs v2.1.217+ — [sub-agents](https://code.claude.com/docs/en/sub-agents) (2026-10-02) — verified (verify lane quote: "when 20 subagents are running… set CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS").
- Plugin subagents ignore `hooks`, `mcpServers`, `permissionMode`; settings/plugin-level hooks still run inside subagents with `agent_id`/`agent_type` — [sub-agents](https://code.claude.com/docs/en/sub-agents), [hooks](https://code.claude.com/docs/en/hooks) (2026-10-02) — verified.
- Skill listing truncates `description`+`when_to_use` at 1,536 chars; post-compaction re-attach keeps the first 5,000 tokens per skill within a shared 25,000 — [skills](https://code.claude.com/docs/en/skills) (2026-10-02) — verified.
- Model resolution: invocation param → frontmatter → `CLAUDE_CODE_SUBAGENT_MODEL` → main; Explore inherits the main model since v2.1.198 — [sub-agents](https://code.claude.com/docs/en/sub-agents) (2026-10-02) — verified.
- A failing `!`command`` aborts the whole skill invocation; exit 1 from search/compare commands is treated as normal, exit ≥ 2 fails — [skills](https://code.claude.com/docs/en/skills) (2026-10-02) — verified.
- That built-in tools such as WebSearch/SendMessage/TaskStop are deferred and need ToolSearch — unverified in official docs (MCP tools are documented as deferred); observed in this environment, so instructions use "if the call is unavailable, load it" wording.
- Repo findings C-marked above were reproduced or code-confirmed on 2026-10-02 by a read-only lane; U-marked ones come from per-skill audit lanes and must be re-confirmed by the owning worker's RED test before the fix.
