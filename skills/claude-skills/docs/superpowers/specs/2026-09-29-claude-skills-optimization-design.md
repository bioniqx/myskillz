# Claude-skills optimization and bug-fix pass — Design

- Date: 2026-09-29
- Status: approved. The user delegated approval of the spec and plan in the request ("tự duyệt spec và plan").
- Scope: every skill under `claude-skills/`. Only files under `claude-skills/` change.
- Priorities: (1) performance, meaning script runtime and skill wall-clock (fewer model tool rounds, permission
  prompts and context tokens); (2) quality, meaning correctness, safety and contract fidelity.

## 1. Approaches

**A. Surgical, evidence-driven fix pass per skill (chosen).** Fix only defects and slow paths that the 13-lane
audit confirmed, with a repro or measurement for each. Each skill is its own workstream with disjoint files, so
the work parallelises cleanly. A new top-level `claude-skills/tests/` suite gives every fix a regression test
without adding files to the installed skill folders.
- Pros: every change traces to a confirmed finding, the risk is low, and the work is highly parallel.
- Cons: no structural rework, so duplicated guard/engine constants stay duplicated (they are kept in sync by
  hand, as today).

**B. Structural consolidation.** Move shared code into a common module, move the dev-team guard into
skill-scoped `hooks:`, and adopt `context: fork`.
- Rejected. Skills are installed by copying single folders, so a shared module breaks installation.
- Rejected. Skill-scoped hooks fire on the Conductor's own tool calls, not only on programmers.
- Rejected. The change is large, so the regression risk is high.

**C. Prompt-only compaction.**
- Rejected. The high-severity defects are in scripts: data loss, skill-cancelling preload exits, false denials.

## 2. Architecture of the change

- There are 12 workstreams, W1–W12. Each maps to one skill or one engine file (§3). Workstreams share no files
  except where §3 says so explicitly, so the dev-team slices can run in parallel.
- **Test home:** `claude-skills/tests/`, stdlib `unittest` only.
  - The run command is `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t tests`, run from
    `claude-skills/`.
  - There is one test file per engine: `test_devteam.py`, `test_guard.py`, `test_audit.py`,
    `test_audit_guard.py`, `test_plan_tool.py`, `test_brainstorm_scripts.py`, `test_debug_scripts.py` and
    `test_gather.py`. Test files must not share state.
  - Tests build fixtures in `tempfile.mkdtemp()` and invoke the real scripts via `subprocess` with
    `sys.executable`/`bash`/`sh`/`node`. Temp paths must go through `os.path.realpath`, because macOS maps
    `/var` to `/private/var`.
  - Tests must not touch the network, `$HOME` or the repo working tree.
  - Each test file stays under ~60 s. Shared fixture repos are built once per `setUpClass`.
- `dev-team-v3.2/scripts/selftest.sh` remains dev-team's end-to-end suite. It must reach **0 failures on macOS**
  (§3 W3).
- Portability rules stay as they are: stdlib-only Python 3.8+ (no 3.9+ syntax evaluated at runtime), POSIX `sh`
  or bash 3.2, and Node without dependencies.
- **Behaviour changes are recorded** in the skill's own CHANGELOG/README:
  - `brainstorming-6.3/CHANGELOG.md` (English)
  - `writing-plans-6.2/CHANGELOG.md` (Vietnamese)
  - `dev-team-v3.2/README.md` (Vietnamese)
  - `systematic-debugging-6.3/README.md`
  - `requirements-code-audit/SETUP.md`

## 3. Workstreams (confirmed findings → required fix)

Line numbers are the audit's and are approximate. The implementer must locate the code by content. Severity:
H = data loss, a cancelled skill or a security bypass; M = wrong result or a wasted round; L = minor.

### W1 — dev-team engine `dev-team-v3.2/scripts/devteam.py`
1. (H) `remove_worktree` can `rmtree` the integration checkout when a claim's worktree is the root, for example
   after `claim --force` in the root or `bind`. Guard: return without doing anything when
   `realpath(wt) == realpath(root)`.
2. (H) `git diff --name-only` follows renames, so a `git mv` from outside the footprint deletes the original
   file unseen, and a test can be dropped by renaming it. Add `--no-renames` to every name-only diff used for
   footprint, frozen-test and stray checks (~1328, 1367, 1397, 2678).
3. (H) `validate_plan` does no type checks.
   - String `files`/`criteria` are iterated character by character.
   - Numeric `id`/`deps` break matching after the JSON round-trip, and `init` saves state and then crashes.
   - Fix: require str `id`, a list of str for `deps`/`files`/`criteria`, and a clean `DevteamError`
     otherwise. Apply the same check in the `retry` plan refresh.
4. (M) `init --force` / `start --force` keep the old `reviews/`, `logs/` and `research/` files.
   - As a result a stale `r1.report.md` gets harvested and a stale `checkpoint-N.log` counts as PASS.
   - Fix: wipe those dirs on `--force`, and delete the target report or log before writing each new brief or
     starting each checkpoint.
5. (M) `start` runs `doctor --fix`, which rewrites tracked `.claude/agents/*.md`, so `init` then refuses because
   the tree has uncommitted tracked changes. Exclude exactly the paths doctor just wrote from `init`'s dirty
   check.
6. (M) Research (read-only) slices currently hold footprints and reject `files: []`. They should occupy no
   footprint and accept an empty `files`, which fulfils SKILL.md's promise "research ∥ wide fan".
7. (M) A slice in `red-done` state does not mark its footprint busy, so an overlapping slice can be dispatched
   between RED and GREEN. Treat `red-done` as busy.
8. (M) Stall is silent. With nothing in flight and nothing ready but slices still waiting (for example after a
   dependency failed), `next` must print an `UNRESOLVED`/stuck line naming the blocked slices and the failed
   dependency, plus the recovery command.
9. (M) `finish` ignores merges that were never reviewed. Count `merges[reviewed_upto:]` as open work in the
   warning.
10. (L) `print_ready` ignores the slots reserved for review shards, so the free-slot count it advertises is too
    high. Pass the reserved count through.
11. (L) `lstrip("./")` strips characters, not a prefix, so `.env` matches `env` and `.github/` matches `github/`.
    Strip only a leading `./` prefix, in both `path_matches` copies (here and W2), with identical bodies.
12. (L) Strict `add-fixes` with a non-dict spec raises a traceback. Raise a clean `DevteamError` instead.
13. (L) The claim header always advertises `commit-red | commit-green`, and the "dirty" rejection always says
    `commit-green`. Print the helpers of the claimed mode: SLICE/RED/GREEN → red/green, WORK → `commit-work`,
    FAST → `commit-fast`.
14. (L) `hooks_resolve()` probes only `.claude/skills/dev-team`. Also probe `dev-team-*` (see W4).
- Perf:
  - (a) Hoist `git rev-parse HEAD` out of the per-slice loop in `do_dispatch`. Measured: `next` with 62 lanes went
    from 1.02 s to 0.29 s.
  - (b) Compute `ready_slices` once per `next`. For footprint overlap, precompute literal-path sets (set
    intersection plus an ancestor-prefix check) and call `path_matches` only for directory/glob entries. The
    output must stay byte-identical. Measured: `start` went from 0.70 s to 0.50 s.
  - (c) Only non-APPROVED review shards reserve slots.
  - (d) Remove the dead `in_linked_worktree` check and the duplicate `ensure_repo`/`find_root` calls.
  - (e) In integrate: use one `rev-parse --verify <branch>^{commit}`, use `worktree remove --force --force`
    instead of unlock + remove, and run `git worktree prune` once per batch.

### W2 — dev-team guard `dev-team-v3.2/scripts/guard.py`
1. (M) The edit path is not resolved while the worktree is.
   - Any symlink in the path (`/tmp`, `/var`, a symlinked project dir) makes every in-footprint edit get
     denied. This is the real cause of the selftest failure "an edit inside the footprint is pre-approved".
   - Fix: `os.path.realpath` the joined path before `relpath`.
2. (M) Commands pre-approved as read-only can write:
   - `git diff/log --output=…`
   - `git grep -O<cmd>` / `--open-files-in-pager`
   - `sort -o` / `--output`
   - `sed` with a `w` command
   - `rg --pre`
   
   None of these may be pre-approved, for programmers or read-only roles.
3. (M) Lanes can run engine control subcommands. The only `devteam.py` subcommands a lane may run are `claim`,
   `commit-red`, `commit-green`, `commit-work` and `commit-fast`. Deny all others (integrate, finish, reset, …)
   from lanes.
4. (L) False denials, each of which costs a round:
   - `git merge-base` is caught by the `\b` in the verb regex. End the verb group with `(?![\w-])`.
   - `git stash list` and `git worktree list` are denied.
   - `2>/dev/null` and other safe redirects are denied. Strip them before the redirect scan.
   - `>` inside quoted strings (`grep "=>"`, `--format='%h -> %s'`) is denied for read-only roles. Strip quoted
     strings before the `>` scan.
5. (L) The `committed` check scans the last 200 commits of the whole history, so a reused slice id passes.
   When `.slice/base` is known, decide by `HEAD != base` only.
6. (L) The `lstrip("./")` prefix bug, as in W1-11.
7. `--no-renames` on guard's name-only diff (~551), as in W1-2.
- Perf:
  - (a) Drop `ensure_red_cache`'s `git log` from the Edit path, which costs 46 ms per Edit during RED/WORK/FAST;
    the Stop gate and integrate re-check anyway.
  - (b) Import `subprocess` lazily inside `git()`.
- Constants duplicated with devteam.py (`TEST_DIR_NAMES`, `TEST_FILE_PATTERNS`, `STATE_DIRNAME`, `is_test_path`,
  `path_matches`) must stay identical. `test_guard.py` asserts that by AST or text comparison.

### W3 — dev-team selftest harness `dev-team-v3.2/scripts/selftest.sh`
- Fix the harness-only failures so that selftest reports 0 failures on macOS (bash 3.2, BSD sed):
  - Replace GNU-only `sed -i` with a portable form (`sed -i.bak … && rm ….bak`, or a temp file).
  - Compare physical paths: `pwd -P` for the script path and the repo root, because git returns physical paths.
  - Fix the bash 3.2 word-split/quoting error in the "worktree clean afterwards" check.
- Also apply the harness fixes found by the selftest lane (§8, addendum).
- Keep the run isolated: mktemp only, no network, no `$HOME` writes. Keep the runtime at or below today's
  (~40 s).

### W4 — dev-team prompts `dev-team-v3.2/agents/*.md`, `SKILL.md`, `README.md`
1. (H) The shipped hook commands in all 5 agents probe only `$CLAUDE_PROJECT_DIR/.claude/skills/dev-team` and
   `$HOME/.claude/skills/dev-team`, while the installed folder is `dev-team-v3.2`, so unpinned installs enforce
   nothing.
   - Fix: also try the glob `…/.claude/skills/dev-team*`, first match wins. The command must still exit 0 when
     nothing matches, and must still be matched and rewritten by `devteam.py`'s `HOOK_LOOP_RE`/`pin_hooks()`.
   - Verified by the audit: the glob form works under bash and dash, and the regex still rewrites it.
2. `SKILL.md` "Speed ceiling": drop the opening enumeration that restates "Why this is fast". Keep the
   "Remaining dials" list and the closing sentence (~110 tokens per load).
3. README (Vietnamese): record W1–W4 behaviour changes.

### W5 — requirements-code-audit engine `requirements-code-audit/scripts/audit.py`
1. (H) The spot-check sample re-rolls on every adjudication, so the queue never drains. Build the pool from
   investigator status (MATCHED, no verifier verdict) without looking at adjudications, seed it on the item
   count only, and filter adjudicated ids after sampling.
2. (M) Wrong `NEXT:` states, where the script says "wait" with nothing running:
   - After a partial SubagentStop, NOTE says redispatch but NEXT says wait. After `--redispatch`, the stale
     `events/<b>.json` keeps the batch flagged as stuck. Retry events (`batch-NN-rNNN`) are never mapped back
     to `batch-NN`.
   - `--undispatch batch-VNN` only re-lists investigator batches.
   - Solo mode lists verifier batches once and then says wait.
   - `--redispatch batch-VNN` does nothing.
   - `--failed batch-VNN` leaves its ids in `verify_assigned`.
   - Fix all of these. Ignore events older than the batch's dispatch time. Re-list undispatched and solo
     batches on every `status`. Clear a failed verifier batch's ids. Print a concrete `NEXT:` whenever nothing
     is running.
3. (M) Re-runs are not idempotent:
   - `plan` leaves the old findings, verify and events files in place.
   - `parse-plan` keeps stale `section-*.jsonl`.
   - Clear those on re-run, and have `parse-merge` read only sections `1..expected`.
4. (M) A findings file written as pretty-printed JSON yields 0 rows silently. Fall back to a whole-file JSON
   parse or `raw_decode` stream, and surface parse errors in `status`.
5. (M) `FINDINGS_SCHEMA`'s status enum omits `UNSEARCHED`, which the agents are told to use. Add it.
6. (L) Plan entries whose `ids` field is a string are iterated character by character. Normalise with
   `as_list` everywhere plan ids are read.
7. (L) `adjudicate --accept` / `--accept-queue` can record UNSEARCHED. Reject that.
8. (L) `check` raises an unfixable PROBLEM for an adjudicated MISSING that has no `searched` terms. Skip that
   check when the id is adjudicated.
9. (L) `git_exclude` writes to a linked worktree's private `info/exclude`. Follow `commondir`.
10. (L) `check` rejects evidence `lines` written as `L41-L58` or with an en-dash. Accept both.
- Perf:
  - (a) `Merged(c)` is rebuilt per queued id in `adjudicate`, which took 4.0 s for 323 queued ids. Build it
    once.
  - (b) Fewer lead turns:
    - `status` prints the adjudication queue itself once the waves are complete.
    - `adjudicate` prints the next step instead of "run status".
    - `report` runs the `check` logic inline and prints its verdict.

### W6 — requirements-code-audit hooks `requirements-code-audit/hooks/*`
1. (H) `DOC_PATH` blocks source files such as `src/orders/history.ts`, `src/license/validator.go` and
   `src/notices.py`, which leads to false MISSING.
   - Match `HISTORY|LICENSE|NOTICE|CHANGES|CHANGELOG|README…` only as whole file names, with an optional
     doc/text extension.
   - Apply the `docs/`, `wiki/`, `rfc/`, `adr/` folder rule only to non-code extensions.
2. (M) The lead's auto-allow checks only the command prefix, so `audit.py status && rm -rf src` is
   auto-approved. Refuse auto-allow when `; & | < > \`` `$(` or a newline appears after the prefix.
3. (L) Worker Bash false blocks (generic mode): `2>/dev/null`, `grep '=>'`, and quoted text such as
   `grep 'git log'`. Strip safe redirects and quoted strings before scanning.
4. Perf: invoke the Python guard with `python3 -S` in `audit_guard.sh` (active path: 30.7 ms to 24 ms).

### W7 — requirements-code-audit prompts `SKILL.md`, `references/*.md`, `agents/*.md`, `SETUP.md`
1. Align the docs with W5:
   - `--failed`/`--redispatch`/`--undispatch` now work for verifier batches.
   - The spot-check is truly deterministic.
   - The new `status`/`adjudicate`/`report` outputs save turns; remove any "run status" or "run check" steps
     they made redundant.
   - `workflow-mode.md` must describe the real coverage rule for `verify/batch-V*.jsonl`.
2. `rca-investigator.md` `maxTurns` 40 → 80. A full batch of 12 requirements at the documented budget of ~6
   calls each cannot finish in 40 turns.
3. `SETUP.md`: note that `permissionMode` is ignored for plugin subagents, and give the one-line allow rule the
   user can add so worker writes under `.audit/` never prompt.

### W8 — writing-plans `writing-plans-6.2/scripts/plan_tool.py`, `SKILL.md`, `agents/plan-task-writer.md`, `CHANGELOG.md`
1. (H) The `context` preload exits non-zero, which cancels the skill:
   - on a leading flag (`--thorough`, because REMAINDER does not capture it);
   - on free text, because `$ARGUMENTS` is pasted unescaped (`let's …`, `(see spec)`).
   
   Fix: the SKILL.md preload passes `"$ARGUMENTS"` as one quoted argument. `context` accepts any argv via
   `parse_known_args`, splits it by whitespace itself, and catches every exception including `SystemExit`,
   so it always exits 0 and prints a one-line degradation note.
2. (H) The heading lint ignores code fences, so `# comment` lines in python/bash blocks and `# Title` inside
   markdown blocks fail. Check headings outside fences only, but still reject `### T\d+` anywhere.
3. (M) The portability scan flags code, backticked spans and URLs, such as `.claude/…`, `CLAUDE.md`,
   `import anthropic` and the pipeline's own `docs/superpowers/specs/…`. Skip fenced and backticked text.
   Match `TODO|TBD|FIXME|XXX` case-sensitively.
4. (M) `files_block` drops extension-less paths (`Makefile`, `Dockerfile`, `LICENSE`) and counts annotations such
   as `app.run()`. Take the first backtick span after `Create|Modify|Test:`.
5. (M) `git add a b && git commit -m "…"` yields 4 false ERRs. Split the command on `&&`, `;` and `||` before
   `shlex.split`.
6. (M) Re-running `contracts` after a contract change keeps stale task bodies and `.ok` marks. Store a hash per
   contract in `work.json` and drop `tasks/<ID>.md*` for every changed hash.
7. (M) `hook-lint` never writes `.warn`, and `lint-task` never clears a stale one. Use one shared helper that
   writes the mark and writes or unlinks `.warn`.
8. (M) An installed agent that still contains the `__PLAN_TOOL__` placeholder counts as installed. Treat it as
   stale and print the `setup --apply` hint regardless of cap.
9. (L) Spec heading map counts `#` lines inside code fences → false `WARN spec uncovered`. Fence-aware scan.
10. (L) The preload runs plain `git status`, which takes `index.lock`. Use `git --no-optional-locks status`.
11. (L) CHANGELOG install path says `~/.claude/skills/writing-plans/`. The folder is `writing-plans-6.2`.
- Perf:
  - (a) `context` printed 278 lines (~4.5k tokens), 13.8 KB of which is the file list. Keep counts, test samples
    and recent files, and cap the list at ~30 entries so the preload stays at ~55 lines or fewer.
  - (b) Run `node --check` for JS blocks in parallel with a `ThreadPoolExecutor` (`assemble` of 70 tasks takes
    6.5 s today).
  - (c) `wait` idles the full 240 s after a writer FAILs. Write a `.fail` mark on a lint failure, and return
    PENDING early once every pending task is failing and has been unchanged for 45 s.
  - (d) Inline the existing target files into reviewer briefs, as writer briefs already do.
- SKILL.md contract:
  - Move the `--allow` advice to Phase 1 (contracts).
  - Hand off to `dev-team` rather than disabled `superpowers:*` skills.
  - Drop the "ultracode" mention, since the context never prints it.
  - Make the setup trigger include the stale-agent case.

### W9 — brainstorming scripts `brainstorming-6.3/scripts/*`
1. (H) `start-server.sh --project-dir .` (relative) never starts, because the script `cd`s before its
   redirects. Canonicalise `PROJECT_DIR` right after parsing.
2. (M) `server.cjs` `.replace('<!-- CONTENT -->', content)` interprets `$&`, `$$` and `$'`. Use function
   replacers, here and at the helper injection.
3. (M) `server.cjs` has no try/catch in the request and message handlers and no signal handlers, so a crash or
   SIGTERM leaves `server-info` without `server-stopped`. Fix: a try/catch that returns 500, plus
   `SIGTERM`/`SIGINT`/`SIGHUP` → `shutdown('signal')`.
4. (M) The server-started JSON lacks `session_dir`, which `stop-server.sh` needs (the doc's `$SESSION_DIR` is
   never defined, so stop silently no-ops). Add `session_dir` to the JSON.
5. (L) `start-server.sh`'s "kill existing server" block never runs, because the pid file lives in the new
   session dir. Stop prior sessions of the same project dir via `stop-server.sh`, which checks the instance
   id.
6. (L) Owner-PID detection assumes exactly one shell in between. Walk up the ppid chain, skipping
   `sh/bash/zsh/dash/env/time/timeout/nohup`.
7. (L) `/files/` does not URL-decode names. Use `decodeURIComponent` in a try block, then the basename. The
   realpath traversal check stays.
8. (L) The watcher treats symlinked or non-regular `*.html` files as new screens. Ignore anything the server
   would refuse to serve.
9. (L) Bytes in the upgrade `head` are dropped. Seed the frame buffer with `head`.
10. (L) `stop-server.sh` overwrites the real exit reason with `stale_pid` and skips cleanup of the `/tmp`
    session dir when the server already exited.
11. (L) The version lookup never finds a manifest (the brand shows "vunknown"), and every screen loads an image
    from an external host. Serve no external assets: drop the remote image, and read the version from the
    skill's CHANGELOG heading or omit it.
12. (L) `context.sh` `npm_deps` breaks on one-line dependency objects. `hot_dirs` is not scoped to cwd. Fix
    with `--relative … -- .`.
13. `helper.js`: normalise whitespace in the event `text` (`.replace(/\s+/g,' ').slice(0,120)`) and add
    `selected` for multiselect clicks.
- Perf:
  - (a) `start-server.sh` polls the full 5 s even when node died at once. Check `kill -0` in the loop and put
    the last 3 log lines in the error JSON (saves ~6 s and a round).
  - (b) The fixed 0.5 s alive-check becomes 4 × 0.05 s.
  - (c) `context.sh` puts `head -n 20000` before awk in the hot_dirs pipeline.
  - (d) `server.cjs` renames `events` to `events.prev` on a new screen instead of deleting it, so clicks are
    never lost to write/read ordering.

### W10 — brainstorming prompts `brainstorming-6.3/SKILL.md`, `visual-companion.md`, `research-playbook.md`, `CHANGELOG.md`
1. `visual-companion.md`:
   - Save `session_dir` from the JSON and stop with it.
   - Liveness check: `kill -0 $(cat <state_dir>/server.pid)`.
   - Read `events` before writing a new screen, or read `events.prev`.
   - Document the `/files/<name>` image route and the multiselect `selected` field.
2. SKILL.md: add `allowed-tools` entries for `start-server.sh` and `stop-server.sh` (pinned under
   `${CLAUDE_SKILL_DIR}`), so starting and stopping never prompts. Move the literal registry URL list out of
   SKILL.md into `research-playbook.md`, where it already exists, and keep one sentence (~45 tokens per load).
3. CHANGELOG: record W9–W10.

### W11 — systematic-debugging `systematic-debugging-6.3/scripts/*`, `SKILL.md`, `references/parallel-playbook.md`, `README.md`
1. (H) `stress.sh` has no trap. A killed script orphans the `xargs -P` workers and leaves `$OUT`. Add
   INT/TERM/EXIT traps that kill the workers (TERM, then KILL after a short grace period) and then remove
   `$OUT`.
2. (H) `bisect-parallel.sh` and `find-polluter.sh` `cleanup()` remove worktrees and `$WORK` before killing the
   in-flight workers. Kill the collected pids first, then remove.
3. (M) `bisect-parallel.sh` silently ignores `-t` without `timeout`/`gtimeout`. Warn, as `stress.sh` does.
4. Perf: `status_of()` forks `cat` per lookup. Use the builtin `read -r v < file`.
5. Docs say `-j` defaults to CPUs. The real default is `min(64, CPUs)` (`bisect`: that minus 1). Fix the
   wording.
- Scripts stay bash 3.2-safe: no `mapfile`, `declare -A`, `${x,,}` or `wait -n`.

### W12 — small skills
- `git-diff-summary`:
  - (H) A `mktemp` failure exits 1 inside the `!` preload, which cancels the skill. Print `GATHER_FAILED
    (mktemp)` and exit 0, and add a `GATHER_FAILED` row to SKILL.md's marker table: fall back to a manual
    `git diff`.
  - Perf: reuse the first merge-base when no fetch ran, and derive the sorted untracked list from the single
    `-z` listing.
  - Pin `allowed-tools` to `Bash(bash ${CLAUDE_SKILL_DIR}/scripts/gather.sh*)`, keeping whatever invocation
    form SKILL.md's preload uses, byte-identical.
- `doc-generator` (H): SKILL.md requires `references/doc-catalog.md`, `writer-brief.md` and
  `reviewer-brief.md`, which do not exist.
  - Recreate them from the original anthropic-skills doc-generator references (a copy exists at
    `~/.claude/skills/synced/*/doc-generator/references/`), adapted to the local SKILL.md.
  - The catalog needs the ★ starter-set column and the HIGH/LOW tier column that SKILL.md's decision table
    uses.
  - The briefs need to be condensable for inlining into Task prompts.
  - Every name SKILL.md cites must exist in these files.
- `frontend-design-Jun18`: the frontmatter `license:` points at a missing `LICENSE.txt`. Copy the upstream
  plugin's `LICENSE.txt` into the folder.

## 4. Data flow and contracts preserved

- The pipeline paths do not change: `docs/superpowers/specs/…-design.md` → writing-plans →
  `docs/superpowers/plans/…md` → dev-team.
- Every `!` preload stays read-only and bounded, and exits 0 on every input.
- `allowed-tools` pins exact paths. Every command a SKILL.md tells the model to run matches a pinned rule.
- dev-team CLI subcommands and printed markers (`NEXT:`, `=== DISPATCH`, `MERGED`, …) keep their spelling.
  New output lines are additive.
- audit.py's JSONL schemas change only additively (`UNSEARCHED` enum).

## 5. Error handling principles

- Preloads degrade to a one-line note and exit 0; they never cancel the skill.
- Guards stay fail-open on internal errors. The real enforcement is the merge-time re-check. A guard must never
  pre-approve a command that can write.
- No silent no-ops: every "nothing to do" state prints a concrete next command.

## 6. Testing

- Every H/M fix gets a regression test in `claude-skills/tests/` that fails before the fix, or a selftest check
  for dev-team integration behaviour. L fixes get a test when one is cheap.
- Perf items are proven with before/after timings pasted in the slice report. Byte-identical output is checked
  where the item promises it.
- Final gate, from `claude-skills/`:
  - the unittest suite is green;
  - `bash dev-team-v3.2/scripts/selftest.sh` has 0 failures;
  - every `.py` passes `py_compile`, every `.sh` passes `bash -n` (and `sh -n` for POSIX ones), and
    `node --check` passes for `server.cjs` and `helper.js`;
  - every SKILL.md description is ≤ 1024 chars.

## 7. Evidence

- Plugin subagents ignore `permissionMode` —
  [sub-agents](https://code.claude.com/docs/en/sub-agents.md) (2026-09-29).
- `Bash(x:*)` ≡ `Bash(x *)` —
  [permissions](https://code.claude.com/docs/en/permissions.md) (2026-09-29).
- `$ARGUMENTS` is substituted without shell escaping — the Claude Code 2.1.284 binary text quoted by the
  writing-plans lane (2026-09-29).
- All other findings are code-level and repro-confirmed in scratch sandboxes by the audit lanes (2026-09-29).

## 8. Assumptions

- Only files under `claude-skills/` change. Installing into `~/.claude/skills` and updating the parent
  `skillz/CLAUDE.md` (its "known red" note becomes stale) are left to the user.
- `frontend-design-Jun18` keeps `name: frontend-design`, because the listing is keyed by folder and the
  collision is harmless.
- The `Red flags` table in brainstorming SKILL.md stays: it is a deliberate steering device.
- The dev-team run starts only after the concurrent `glm-skills` dev-team run in this repo has finished. Its
  state is archived to `.claude/dev-team-archive-glm-skills/`, following the existing archive convention.
- The plan is written in dev-team plan format directly from this spec, because the spec is execution-ready.
  writing-plans is not used for this run: its unfixed lint (W8-2, W8-3) rejects plan bodies about Claude Code
  skills.

### Addendum — selftest lane

The baseline is 242/250 with 8 consistent failures and ~45 s wall time. The suite has grown from the 247 checks
documented in the parent CLAUDE.md.

- **W3 harness** fixes:
  - `selftest.sh:~105`: `sed -i 's#…#…#' plan.md` is GNU-only; use the portable form.
  - `~543`: nested `\"` inside `"$( … )"` word-splits in bash 3.2 ("[: too many arguments"); build the JSON
    with single quotes.
  - `~709`: compare physical paths (`cd "$RM" && pwd -P`).
  - `~493/499`: `doctor` checks inherit `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS`, `BASH_DEFAULT_TIMEOUT_MS` and
    `BASH_MAX_TIMEOUT_MS` from a Claude Code shell. Run those checks under
    `env -u CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS -u BASH_DEFAULT_TIMEOUT_MS -u BASH_MAX_TIMEOUT_MS -u CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS -u CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY`.
- **W2 addition (H, product):** `.slice/allow` pins the realpath of the engine script, while agents type the
  literal path, so the commit helpers lose pre-approval whenever the skill path crosses a symlink. The
  selftest checks at ~555/769 fail for this reason.
  - Fix: when matching a command against `.slice/allow`, canonicalise the command's script token with
    `os.path.realpath` and compare canonical forms on both sides.
  - Do not widen the allow surface. Only the pinned slice helpers stay pre-approved.
- **Out of scope:** splitting devteam.py/guard.py into a CLI shim plus an importable module for bytecode caching.
  It would save ~35 ms per call, which is below 1 % of a model turn, and it would add a new module-import
  coupling to the hook commands.
