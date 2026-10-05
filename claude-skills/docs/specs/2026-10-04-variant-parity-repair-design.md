# Variant Parity Repair — Design

Date: 2026-10-04 · Status: approved by the user as proposed (2026-10-04), spec pending review.

## 1. Goal and scope

Every variant skill (`glm-skills/`, `hybrid-skills/`, `opencode-skills/`) must keep the SAME core as its
original in `claude-skills/`: purpose, phases and their order, gates, hard rules, outputs, script behaviour and
quality bar. Only harness mechanics may differ (tool names, dispatch syntax, model names, install paths,
frontmatter, lane caps forced by a provider).

Two audit passes (6 family audits, then 12 lanes: test runs, function-level script diffs, rule matrices, adversarial
reproduction, infra, originals) found that the variants' text layers are mostly faithful but their script layers
are stale forks of the originals, which were hardened on 2026-10-02. Every finding below was either reproduced by
running code or read at the cited location.

In scope: all findings in section 4. Out of scope (legitimate harness differences, do not touch): Flash/Pro model
routing and the AIMD governor in glm, the 8-lane ceiling in oc, `oc-`/`-glm` naming and frontmatter differences,
oc's no-model-settings rule, doc-generator's inlined ≤4-turn design (only its dropped content rules are restored),
`Backends:`/`Method` report lines, CSV BOM, hybrid's opencode offload design.

## 2. Approach

Port bottom-up from the originals, one unit per (variant × skill), units independent so they run in parallel:

- Wave 0 fixes the originals first (they are the reference and have their own inconsistencies).
- Wave 1 ports safety, gate and data-loss fixes (scripts).
- Wave 2 restores dropped content rules, fixes stale text, tests and infrastructure.
- Wave 3 verifies: all suites and selftests, hunk-by-hunk review of guard and gate diffs, `/code-review`.

Rejected: ad-hoc per-file patching without a reference (drift returns); rebuilding variants from a shared core via
a generator (scope far beyond the problem).

Each ported guard, gate or linter behaviour gets one small runnable test in the variant (today the variants have
almost none). No new frameworks; stdlib `unittest`.

## 3. Constraints

- Reference is always the original after Wave 0. A variant is never the reference.
- Do not normalise intentional differences (names, frontmatter) back to the original's form.
- Descriptions stay ≤1024 characters (ZCode drops longer ones); recheck any frontmatter edit.
- Keep `-glm`/`oc-`/`hybrid-` renames: a port is a rename-normalised copy of the original change.
- No commits unless the user asks. The user's existing uncommitted edits to the five CLAUDE.md/AGENTS.md files and
  the untracked `CLAUDE.md` files are preserved.
- Spec and plan files are never committed by the assistant (user rule).

## 4. Findings and required changes

Severity: P0 = safety, data loss, or a gate that no longer gates; P1 = dropped core rule or wrong behaviour;
P2 = stale text, tests, hygiene.

### 4.0 Wave 0 — originals (`claude-skills/`)

P1/P2:
- writing-plans: `SKILL.md` and `CHANGELOG` say tier maps light→haiku/deep→opus, but `plan_tool.py` and two tests pin
  all tiers to sonnet. Decision: keep sonnet; fix the two docs (tier only influences review picking).
- writing-plans: docstring says `check` is for "≤3 tasks" and the script header says inline up to 3; SKILL says N=1
  inline. Decision: N=1 inline, parallel writers from N=2; fix docstring and header.
- writing-plans handoff names bare `claude-dev-team`; use versioned name first, bare name as fallback (the pattern
  brainstorming already uses). Reviewer prompt line "Read all task files" contradicts the brief that inlines them.
- requirements-code-audit: `SETUP.md` and `references/workflow-mode.md` say haiku, code and agents say sonnet; `SETUP.md`
  names local-mode agents `rca-*`, real names are `claude-rca-*`.
- Version labels disagree (brainstorming dir 6.3 vs CHANGELOG 9.0; writing-plans dir 6.2 vs internal v8): add a
  dir-to-internal-version note.
- `claude-skills/CLAUDE.md` says hybrid counterparts live in sibling repos; they are in `../hybrid-skills`.
- dev-team and systematic-debugging both claim bug-fix triggers: add one-line routing rule to each.
- Brainstorming `helper.js`: `brainstorm.choice()` omits the `choice:` key so `server.cjs` drops the event. glm and oc
  already fixed this; port the fix back to the original, then to hybrid.
- Flaky test `test_debug_scripts.py` (`sd_kill_tree` trap): fails under parallel load only; reset SIGINT in the test
  subprocess.
- Missing tests for critical paths: guard denials (other-slice worktree, outside-footprint edit, `git -C`/`--git-dir`,
  `git checkout <ref>`, read-only roles), finish gate, plan-lint rules (contract IDs/Consumes, Files subset, steps,
  Run/Expected, syntax) and `check`, audit `finish`/`abort`. Add one test per path.
- Variant scope: root `CLAUDE.md` and the three variant guides state that `claude-frontend-design-Jun18` and
  `claude-git-diff-summary` have no variants by design (prose-only / `!`-injection specific), and that hybrid has no
  debugging or doc-generator fork by design (judgment skills; opencode only executes low-judgment units).
- Parity-marker tests per variant folder are covered in section 6 (included by default).

### 4.1 dev-team (glm, oc, hybrid) — engine and guard

Original: `claude-dev-team-v3.2/scripts/{devteam.py,guard.py}`. glm and oc are older (v3.1-era) forks; hybrid is close.
Verified by running code; selftests: original 251/0, hybrid 255/0, glm 350/4, oc 206/2.

P0, glm + oc (hybrid noted where it also applies):
- `path_matches` uses `lstrip("./")`, which strips every leading dot and slash: footprint `env` matches `.env`,
  `claude/` matches `.claude/x`. Strip only a literal `./`. (devteam.py and guard.py, both variants.)
- No finish gate: `finish` succeeds with no review and no checkpoint. Port `finish_gate_problems` (pending, absent
  or failed checkpoint; merges after the last checkpoint; verification CHANGES_REQUIRED). Hybrid lacks it too.
- Guard does not deny engine subcommands from lanes (`reset --yes`, `finish --force`): port `devteam_subcommand`
  deny. glm falls through to the normal permission flow; oc relies only on default-deny.
- `salvage_worktree` missing: uncommitted lane work is lost on `fail`, `retry`, `finish` (`git worktree remove --force`).
- `red-done` slices do not hold their footprint (`ready_slices` counts only inflight); research slices lose their
  footprint exemption; `plan_fp` missing.
- `cmd_commit_red` no longer discards non-test stubs and `integrate_one` lacks the `red-touches-source` reject, so
  stubs ride in the frozen RED commit; matching briefing text dropped; `--no-renames` missing everywhere.
- `init --force` leaves stale `reviews/`, `logs/`, `research/`, stale `.report.md` and checkpoint logs, so an old
  PASS can be read as fresh.
- `validate_slice_types` missing (malformed plan crashes); `next_fix_id` (id collision), spec-object checks, fix
  auto-kind (docs/chore), "code fix without test path" NOTE missing; `cmd_doctor` returns no `written`
  (`doctor_fixed`, `dirty_excluding` missing) so `start` fails on dirt doctor wrote.
- `cmd_finish`: "merged slices never sent to review" check missing (glm); `shard_verdicts` missing so all shards of a
  CHANGES_REQUIRED review are reserved.
- `remove_worktree`: no guard against removing the integration checkout; no double `--force` for locked worktrees.
- Guard: `git merge-base` / `git worktree list` denied for read-only roles; no `strip_quoted` (so
  `grep 'git push' README` is denied); `write_capable` hardening (awk, `sed w`, abbreviated flags) replaced by a
  weaker check; `.claude/dev-team` and `.slice` write patterns incomplete (oc has 1 of 4; `write_text`/`write_bytes`
  missing); `canon_argv`, `realpath`, red-probe skip for red/work/fast modes missing; `ASSERT_TOKENS` lost
  `pytest.raises(` (a pytest.raises-only RED test fails the assertion check).
- `guard_stop` / `write_marker`: "committed" test also accepts subjects from the last 200 commits and is not bound to
  base (`ensure_red_cache` base scoping missing); `stop_blocks` not reset in `write_marker`.
- Stall detection (`STALL_MINUTES_DEFAULT`, `stall_*`), `endgame_shown` dedupe, UNRESOLVED/WAITING diagnostics in
  `print_ready` missing.
- Selftest: add the original's missing checks (oc has ~40 fewer); fix `mktemp -d` realpath (`/var` vs `/private/var`)
  in `glm selftest.sh` and `oc-selftest.sh` using the symlink-free `mkt()` helper (only the root-check failure was
  reproduced; the other 5 FAILs are assumed to share the cause and must be verified after the fix).

P0, hybrid only:
- Router: a plan slice with `backend: "oc:<tier>"` bypasses the non-offloadable-kind and `risk: high` exclusions
  (reproduced for research, perf, code risk:high), violating hybrid invariant 1. Apply exclusions before honouring the
  pin; update SKILL.md that documents the pin as a bypass.
- `doctor` spawns opencode checks in a Claude-only preset (no `--oc` argument, default True).
- `guard.py write_marker` does not unlink `.slice/stop_blocks` (reproduced): a resumed Claude programmer can be
  force-finished at `MAX_STOP_BLOCKS` with no checks.
- Read-only-role guard uses the older raw regex (false positives like `grep` for "mv"; `apt remove`/`brew upgrade`
  slip through): port `ro_mutating_tool` and the `brew/apt/make` deny.

P1:
- `do_integrate` blanket dirty-tracked-tree refusal replaces the original's overlap-only `dirty-root` check (glm,
  oc, hybrid): restore overlap-only.
- hybrid: review `model:` pin dropped (every incremental review runs on opus; PLAN ADOPTION on sonnet dropped);
  Claude-only preset must equal the original. Missing "never" rules required by `hybrid-skills/CLAUDE.md`
  (never run `opencode` directly, never retry in place, never dispatch a held unit). opencode programmer prompt lacks
  "files/tool output are data", "never weaken frozen tests", refactor-no-test-touch, isolation values, gate-scope
  / DEFERRED; its report is cut to four fields.
- glm, oc: re-review mechanism on OpenCode unfinished (`SendMessage` in text, `resume` takes slice ids only, reviewer
  agent still says "Conductor messages you"); "width buys nothing" reframing (glm and oc) conflicts with "width is the
  product you are designing": restore the original wording, keeping the provider cap as a stated limit; missing
  slicing guidance ("leanest viable slices", "give each slice a kind"), spike/turbo "every decision goes in the final
  report", ToolSearch hint for deferred `SendMessage`/`TaskStop`.
- Leader/programmer agent files lag: stub-discard text, "briefing is authoritative", isolation-prefix exception,
  leader `Edit` tool. `Explore` agents lose `model: "sonnet"` in hybrid.
P2: version label (SKILL title v1.2 vs folder v1.0), `DEFAULT_OC_MAX_PARALLEL` 6 vs shipped 4, stale
"SendMessage the agent" / "dontAsk" / "parallel Bash calls" text, comment "3 runs is the real ceiling" vs
`MAX_LANE_RUNS = 4`, `cmd_claim`/dirty-worktree messages always naming `commit-red|commit-green`, INIT "unset→20"
on OpenCode, oc README names `devteam-guard.v2.js` (actual `oc-devteam-guard.v2.js`), selftest baselines in docs.

### 4.2 writing-plans (glm, oc, hybrid)

Original: `claude-writing-plans-6.2/scripts/plan_tool.py`. Reproduced by running `lint_body` on all four.

P0/P1 (all three): `commit_errors` (rejects `git commit -a` and a commit with no earlier `git add`) and `allow_hit`
(`--allow` stem and `re:` matching) missing; `contract_hashes` covers own text only in hybrid (dependents are not
invalidated); `cmd_contracts` re-dispatches Claude groups that already have `.ok`; reviewer brief no longer inlines
task bodies; `cmd_setup` never refreshes an existing agent file (hybrid).

glm + oc only: `scan()` ignores fences/inline code/URLs and is case-insensitive (lowercase "todo" in prose and
"Claude" in a code span are flagged; a todo-app plan fails); `heading_outside_fences` replaces
`TASK_HEADING_ANYWHERE` (a fake `### Tnn:` inside a fence passes); `files_block` takes every backtick span;
`spec_coverage` has no fence mask; `sh` lacks `--no-optional-locks`; no `contract_hash` invalidation, no `.fail` marks,
no stale-`.warn` clearing (`apply_marks`), no stuck-wait detection in `wait` (a dead writer hangs it); the reviewer's
`Unfixable (needs contract change)` has no consuming step; `WARN spec uncovered` instruction and `--allow` guidance
dropped; inline threshold N≤3; handoff drops the dev-team adoption offer and "(recommended)"; `pick_risky` adds a
`producer` trigger (over-review); `brief` pattern-file heuristic replaces the model-picked 2-5 files and optional
Explore agents; glm `plan-reviewer-prompt.md` holds two contradictory format blocks (oc does not).
Fix: re-sync `scan`, `fence_mask`, `files_block`, `commit_errors`, `allow_hit`, `apply_marks`, `cmd_wait`,
`contract_hashes` from the original with rename normalisation; keep the portability additions for the harness.

hybrid P2: its tests `test_lint_parity.py`, `test_fork.py`, `test_golden.py` point at the nonexistent
`claude-skills/writing-plans-6.2` (6 of 10 skipped; CHANGELOG says fixed); `hybrid-skills/CLAUDE.md` sync tests use
`hybrid/...` instead of `hybrid-skills/...` (always skip); stale external-skill (`<name>:*`) and "ultracode" handoff text; the
portability claim "linter enforces no opencode mention" is false (add `opencode` to `PORTABILITY` or drop the claim);
SKILL says Claude-only mode is "identical to 6.2" which is only true after the port.

### 4.3 requirements-code-audit (glm, oc, hybrid)

Original: `claude-requirements-code-audit/scripts/audit.py`. Hybrid in preset `claude` produces a byte-identical report
and CSV to the original on a synthetic audit; glm and oc do not.

P0/P1 (glm + oc, reproduced): `Merged.final` returns UNVERIFIABLE for a tagged item before considering
adjudications (original adjudicates first; the queue also skips tagged items); `check` gate drops: PARTIAL/CONFLICT/
untagged-UNVERIFIABLE never verified, investigator/verifier disagreement, MATCHED low-confidence/high-stakes never
verified, MISSING without `searched`, effort S/M/L and P0 warnings; the "no second pass ran" check is only a warning;
Wave-B verifiers are not independent (they reuse pass-1 retrieval layers; oc's `round2` is dead code and the verifier
budget drops to 6); report evidence ignores which pass decided the status.
glm only: agent-lane rows are never linted — string evidence crashes `report` and `check`; `plan.jsonl` `ids` as a
string splits per character; re-running `plan` does not clear stale findings/`vbatches` (verifiers skipped); retrieval
excludes dot-dirs and `.erb/.sol/.cshtml` (false MISSING on CI/template requirements); ids like `FR.2`/`1` rejected and
≥2 search hints required; failed parse sections only print WARN; parse dedupes identical text; `read_jsonl` lost
whole-file/trailing-comma/`#` tolerance; PDF/xlsx specs not extracted; `adjudicate` has one `--set`, no
`--accept-queue`, no UNSEARCHED guard; agent-lane schema has no `searched`; error points to parser subagents that do
not exist; verify batch up to 6 items (original 3, `VERIFY_MAX_PER_AGENT`); report text cut to 160 chars and
UNSEARCHED omitted; `.git/` citations not rejected.
oc only: `JUDGE_SCHEMA`/`VERIFY_SCHEMA` have no `searched` and nothing writes `searched`/`passes`, so "every MISSING
lists the searches run" is unenforceable; lost investigator output never reaches Wave B and `status` cannot recover it
(`plan --resume` is not documented); no hedging/`--failed`/`--undispatch`; parse has no failure detection; re-running
`plan` does not clear stale artifacts; `status` text claims reprints that the code does not do.
Both: stale `run`/`finalize`/"write guard disarmed" text, `schemas.md` lists keys never written, `--no-verify` doc
claim, "deterministic 5%" spot-check claim vs stride-based; queue adds every MISSING and drops untagged
worker-UNVERIFIABLE (restore original queue rule, keep any addition only if justified in CHANGELOG).
hybrid: guard hook never arms (`audit_guard.py` hardcodes `.audit/config.json`; hybrid writes `.hybrid-audit/`),
agent names `req-audit`/`rca-*` stale (real `claude-req-audit:claude-rca-*`, also fail the guard's suffix match;
tests bake the old name in); `VERIFY_SPEED_RULES` and `SEARCH_GLOB_RULE` missing; `LEAN_BATCH`/`lean_agents` removed;
parse threshold 2500 vs 800 and Claude investigators haiku vs sonnet — in preset `claude` these must equal the
original (cheaper values only in presets that offload); opencode MATCHED+high on normal stakes is never verified
(add to the verify set or document the ≥5% spot-check as the accepted ceiling); text claims structural guard and
SubagentStop events that do not exist.

### 4.4 doc-generator (glm, oc)

Original has no scripts; the variants are one inlined `SKILL.md` redesign. User decision (2026-10-04): restore the
selection gate.
- Restore the doc-selection gate: numbered adapted list with `[create]/[update]` tags, "ok" selects the starred set,
  skipped only when docs are named or the run is non-interactive; monorepo "ask which packages".
- Restore update mode in the writer template (read the existing doc first, preserve human-added content, note
  removals) — the template currently says "Do not read this project's docs" and can overwrite hand-written rationale;
  restore requirements fidelity (document what the code does, flag code-vs-requirement mismatches) in writer and
  reviewer; reviewer completeness check, Mermaid-matches-code check, `BROADLY_WRONG` rule; surface reviewer
  `unresolved=` and `human=` in the final summary.
- Restore a `Language:` slot defaulting to English; star Test Plan and Installation & Deployment again and add the six
  dropped catalog rows (feature spec, traceability, technical overview, admin guide, dependency inventory, QA checklist)
  as selectable; restore README index rule (`README.md` reserved for the indexer; overview becomes `overview.md`;
  repo-root README refresh).
- Bug fixes: cache never hits (manifest repeats its own `HEAD: <hash>` line, so the `sed` returns two lines); finish
  link regex lets `://` through (use the original's `[^)#:]+`); writer template says `sed -n` ranges while agent files
  set `bash: false`; manifest and `state.json` written only at finish (write the manifest before the wave).
- Keep: ≤4 turns, ≤10 lanes, inlined briefs, the extra secret scan and no-git fallback.
- glm: `CLAUDE.md` says "no scripts" but `scripts/oc_harness.py` ships; runtime SKILL text carries maintainer-only
  notes (`sync.sh`, "never edit the copy"); `.zcode/` hard-coded as state dir. oc: `AGENTS.md`/SKILL claim "no scripts"
  but `oc_harness.py` is vendored.

### 4.5 systematic-debugging (glm, oc)

Original: `claude-systematic-debugging-6.3`. No hybrid fork by design.
- P1 flaky arms run concurrently in `experiment` (CPU contention biases timing fixes); the original runs arms one after
  another. Make arms sequential for flaky/timing verdicts; update both `flaky-and-timing.md`.
- P1 shell scripts are an older snapshot: port the original `_lib.sh` (`sd_kill_tree`), `trap` in `stress.sh`, `-b F/N`
  validation, `find-polluter.sh` excludes (dist, .venv, .claude, linked dirs) and pollution-file strip,
  `bisect-parallel.sh` kill-before-worktree-removal and `clean -fdxq`.
- P1 `debug-worker` `steps: 5` (original none): raise to a value that fits stress arms; oc `scan` has no 64 cap and
  the frontmatter dropped "up to 64 workers": add the cap and the sentence.
- P1 CONFIRMED rule: R4.2 says "one arm passed and the other failed", the tool also confirms `t.fails < c.fails`; align
  code or text (code to text).
- P1 R2 restricts overrides to escalation and `SWARM_RE` is keyword-only: restore multi-component, performance,
  many-plausible-causes, regression-unknown-culprit and non-deterministic routing to SWARM; restore prod-down evidence
  list; restore "say I don't understand X", "A≠B or E not worth running", "read the reference completely", Phase 4
  step 4 (fix as a treatment arm / revert-and-fail proof), "beyond ~8 subagents merge cost exceeds gain".
- P2: stray "(fixes SD12)", "Setup snippet for OpenCode" block inside R4, R8 state-carry is benign, oc R1 "do not batch"
  premise is GLM-specific, oc lacks `evals/` (port from glm), glm `debug-worker` rule 1 "workspace path" has no value
  (oc passes `ROOT=`).

### 4.6 brainstorming (glm, oc, hybrid)

Original: `claude-brainstorming-6.3`.
- P0 all three: spec commit is unconditional; port the conditional rule (commit only when neither the user nor a loaded
  instruction file forbids committing self-initiated files; otherwise leave the spec untracked and use the
  "not committed, per your instructions" review-gate text). This is also the user's own global rule.
- P0 oc: hand-off names bare `writing-plans`; installed name is `oc-writing-plans`. Use the installed name first.
  glm hand-off to `writing-plans-glm` must be checked the same way; hand-off passes the committed spec path (wrong when
  the commit is skipped).
- P0 glm + oc: stale visual-companion — external `primeradiant.com` logo (violates "no external assets"; the original
  test asserts it is absent), `$&`/`$'` corruption from `.replace(x, content)` (original uses a function replacer),
  `events` unlinked instead of rotated to `events.prev`, no `/files` URL-decode, no `handleRequest` try/catch, no
  SIGINT, WS head bytes dropped, no symlink guard; `start-server.sh` single-hop owner PID with no instance cleanup or
  fail-fast; old `stop-server.sh`; `helper.js` `choice:` key (already fixed here, port back to original); loop writes the
  screen and reads `events` in the same batch (clicks lost); `$SESSION_DIR` used but never saved (`server-started` lacks
  `session_dir`); `visual-companion.md` is the older loop; glm `allowed-tools` lacks start/stop/`kill -0`; R0 forbids
  touching files outside `drafts/`, conflicting with companion screens. Re-sync scripts and `visual-companion.md` from
  the original with the rename mapping.
- P1 glm + oc: `context.sh` has the old unscoped `hot_dirs_30d` (no `--relative -- .`, no `head -n 20000`) and a
  looser `npm_deps` fallback; round-1/2 text lacks "load deferred tools first" (also hybrid); red-flag "Spawn 64 because
  I can" missing; glm judgment lanes (claim verifier, drafts, reviewers) on Flash — keep (cost-justified) but state the
  weaker independence in `glm-tuning.md`.
- P1 hybrid: `research-playbook.md` cites claim verifier at §4 (it is §3); `SKILL.md` says per-tier cap 6 vs 4
  everywhere else; spec pre-draft lane drops `model: "sonnet"`; round-1 wording is the older 8.0 form; README claims
  preset claude reproduces 6.3 exactly and `hybrid-skills/CLAUDE.md` claims a 09-30 resync — update to match reality
  after the port; 6 tracked runtime files under `scripts/.hybrid-<name>/.../doctor/` to untrack.
- P2: glm `CLAUDE.md` says 9.0-glm, CHANGELOG says 9.3-glm; `glm-tuning.md` uses a nonexistent `skills/glm/...` path;
  oc has no CHANGELOG or README.

### 4.7 opencode permission key (new, from the game-repo session)

opencode v2.0.22 names its shell tool `shell`. Every permission builder that sets only `"bash"` with `"*": "deny"`
denies every shell command, so lanes fail their gate and escalate. The installed copy
`~/.claude/skills/hybrid-team-v1.0/scripts/oc_config.py` was patched on 2026-10-03; the repo source was not.
- P0 hybrid-team: copy the patch verbatim from the installed copy into
  `hybrid-skills/hybrid-team-v1.0/scripts/oc_config.py`: `"shell": bash_block(engine, commands)` next to `"bash"`
  (same rules, nothing widened), and `bash_block` splits each pinned command on `&&`, `||`, `;`, `|` and allows every
  part with its own tail (`stylua --check {files} && selene {files}` must allow `selene <file>`); add `import re`.
- P0 other builders with the same `"bash"`-only pattern: `hybrid-writing-plans/scripts/hp_config.py`,
  `hybrid-brainstorming/scripts/hb_config.py`, `hybrid-requirements-code-audit/scripts/ha_config.py`, and
  `glm-skills/_shared/oc_harness.py` plus its vendored copies in glm-skills (6) and opencode-skills (6). Its comment
  ("permission key is still bash") was verified only against v2.0.16. Verify against opencode ≥ 2.0.22 (installed:
  2.0.22) before changing; where the key is needed, emit both keys with identical rules. `oc-devteam-guard.v2.js`
  already lists both tool ids; confirm the agent frontmatter path for oc-dev-team.
- Tests: assert the `shell` block equals the `bash` block and that every part of a pinned chain is allowed (existing
  `test_oc_config.py` checks only `bash`).
- A user memory note records this pending port (project memory `opencode-shell-permission-unported`).

### 4.8 Infrastructure and documentation (P2 unless noted)

- P1 `opencode-skills/_shared/tests/test_no_foreign_refs.py` fails: stale allowlist key
  `writing-plans/scripts/oc_plan_tool.py` (folder is `oc-writing-plans/`; hits at `oc_plan_tool.py` lines 49, 1309,
  1314). Once the untracked `opencode-skills/CLAUDE.md` is tracked it adds hits (names `claude-skills`, `glm-skills`,
  `ZCode`); extend the allowlist for that file deliberately or reword it.
- Hybrid tests that never run because they look for the original at wrong paths: `hybrid-writing-plans` (`test_fork`,
  `test_golden`, `test_lint_parity`), `hybrid-requirements-code-audit` (`test_fork`, `test_golden`), `hybrid-team`
  (`test_dispatch_flow`), and all four `test_hybrid_shared_sync.py` (`hybrid/...` vs `hybrid-skills/...`). Fix paths so
  the parity tests actually run; the four `hybrid_shared.py` copies are in fact identical.
- Wrong statements in guides: `glm-skills/CLAUDE.md` ("git root is `~/.claude`", "one level up in
  `~/.claude/skills/`", selftest baseline 324/5 vs actual 350/4, `agents/opencode/` vs `opencode/agents/`, "no scripts"
  for doc-generator, ZCode listed but no `agents/zcode/` and installer only installs OpenCode, brainstorming 9.0 vs 9.3);
  `opencode-skills/AGENTS.md` ("5 known failures" vs actual 2, "no scripts"); `hybrid-skills/CLAUDE.md` (originals
  named without `claude-` prefix, path `hybrid/hybrid-<skill>-v1.0`, nonexistent fork base `e7295d4`, selftest 247/8 vs
  255/0); `claude-skills/CLAUDE.md` (sibling repos, strict RED/GREEN convention vs last commits all "commit");
  `glm-skills/dev-team-glm/README.md` baseline; root `CLAUDE.md` "six-or-so workflows in four flavours" while
  `claude-skills` has 8 skills and `hybrid-skills` 4.
- Hygiene: tracked root `.DS_Store`, `claude-skills/claude-dev-team-v3.2/.idea/*` (the `.gitignore` entry is root-only),
  6 runtime files under hybrid-brainstorming (see 4.6), `claude-skills/config/` holds a copy of the personal
  `CLAUDE.md` and `settings.json` (no secrets found; keep, but note it is a snapshot), stale
  `claude-skills/.claude/agent-memory/.../project_skills_verification.md` and the two `docs/handoff/HANDOFF.md`
  snapshots with local transcript paths (leave, flag in the report).
- Description lengths: `oc-requirements-code-audit` is 1017 characters (limit 1024); shorten to ≤900. Others near the
  limit: glm rca 911, claude rca 882.
- `claude-skills/install-skill.sh` usage says `./install.sh`; `--help` cuts off the plugin note. Installers otherwise
  copy every needed file.
- Vendored copies (`oc_harness.py`, `zai_client.py`, `hybrid_shared.py`) are byte-identical to their sources today;
  after any change to a source, run its `sync.sh` and recheck.

## 5. Verification

- After each unit: that variant's own suite (command per `CLAUDE.md`), plus the one new test per ported behaviour.
- After Wave 1/2: full run of all suites (`claude-skills` 561, glm 671, oc 470, hybrid 475+564+548+474) and the four
  selftests (target: original 251/0, hybrid 255/0+, glm and oc 0 failures). Known pre-existing: oc
  `test_no_foreign_refs` failure and glm/oc selftest FAILs; each must end green or have a documented, reproduced cause.
- Claim-by-claim re-run of the reproduced findings (path_matches, finish gate, guard denials, stop_blocks, router pin,
  doctor, linter probes, audit merge/check, doc-gen regexes, visual-companion `$&`) against the ported variants.
- Guard, gate and linter diffs are reviewed hunk by hunk by the lead; then `/code-review`.
- Opencode lanes: smoke-run one hybrid-team lane gate on opencode 2.0.22 after 4.7.

## 6. Decisions and assumptions (approved as proposed)

- Full scope, no cut. Order: Wave 0, then Wave 1 and 2 in parallel per unit, then Wave 3.
- Hybrid mode "Claude only" must reproduce the original exactly (sonnet investigators, parse threshold 800, opus review
  pin); cheaper values stay only in presets that offload.
- doc-generator selection gate is restored (user choice); the inlined ≤4-turn design stays.
- Writing-plans: tier stays all-sonnet; inline only for N=1.
- Frontend-design and git-diff-summary have no variants by design; hybrid has no debugging/doc-generator fork by design.
- Optional, small: one parity-marker test per variant folder that asserts the key symbols exist (for example
  `finish_gate_problems`, `commit_errors`, `salvage_worktree`, the shell permission key), so future originals cannot
  silently outrun forks. Include it unless the user objects.
- No commits. Existing user edits to the CLAUDE.md/AGENTS.md files are preserved.

## 7. Risks

- Porting guard and gate changes can regress working lanes: mitigated by selftests, one test per behaviour and the
  hunk-by-hunk review.
- glm/oc selftest FAILs are attributed to the macOS `/var` symlink from one reproduction; if any survive the `mkt()`
  fix, treat them as real defects.
- The opencode `shell` key is verified only on 2.0.22; older opencode versions must keep working, hence both keys.
- Units that touch the same vendored source (`_shared`) must not run in parallel with each other.
