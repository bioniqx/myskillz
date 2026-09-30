# Plan: claude-skills optimization and bug-fix pass (dev-team)

## Understanding

This run executes the approved spec
`claude-skills/docs/superpowers/specs/2026-09-29-claude-skills-optimization-design.md`.

- There are 12 workstreams (W1–W12), all under `claude-skills/`.
- Each slice names the spec items it owns, for example "W1-1". The spec text for an item is authoritative:
  read §2 and your W-section before coding.
- Line numbers in the spec are approximate. Locate code by content.

## Open questions

None. The user delegated approval of the spec and plan.

## Assumptions

**Safe:**
- Every edit stays under `claude-skills/`.
- Tests are stdlib `unittest` files in `claude-skills/tests/`, one file per slice, with fixtures in the system
  temp dir.
- The installed engine running this session (`~/.claude/skills/dev-team-v3.2`) is a different copy. Lanes
  edit only the working copy.

**High-risk:** K01 (worktree deletion and rename bypass), K04 (guard security), K09 (audit state machine) and
K14 (skill-cancelling preload). Each gets split RED/GREEN and a verification pass.

## Dispatch DAG

- Ready at start: K01, K04, K06, K09, K11, K13, K15, K16, K17, K19, K20, K21.
- K02 and K03 follow K01, because all three touch `devteam.py`.
- K05 follows K04 (`guard.py`).
- K10 follows K09 (`audit.py`).
- K14 follows K13 (`plan_tool.py`).
- K07 runs after K01 and K05; K08 after K01–K06.
- K12 runs after K09–K11; K18 after K15–K17.

```json
{"request": "Optimize and fix bugs in every skill under claude-skills/ so they work flawlessly (priority 1 performance = script runtime + fewer model rounds/prompts/tokens; priority 2 quality), by executing the approved spec claude-skills/docs/superpowers/specs/2026-09-29-claude-skills-optimization-design.md workstream by workstream. Only files under claude-skills/ change.",
 "profile": "balanced",
 "commands": {"build": "none",
              "test": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s claude-skills/tests -t claude-skills/tests",
              "test_file": "PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s claude-skills/tests -t claude-skills/tests -p {files}",
              "lint": "none", "lint_file": "none", "typecheck": "none", "typecheck_file": "none"},
 "contracts": [
   "C1 session_dir: the server-started JSON line printed by brainstorming start-server.sh and written to <state_dir>/server-info gains key \"session_dir\" = absolute path of the session dir (the parent of state_dir); all existing keys unchanged — established in K15, consumed by K16, K18",
   "C2 path_matches: in BOTH claude-skills/dev-team-v3.2/scripts/devteam.py and guard.py, path normalisation strips only repeated leading \"./\" prefixes (while p.startswith(\"./\"): p = p[2:]) — never lstrip(\"./\"); the two function bodies stay textually identical — established in K01 (devteam.py) and K05 (guard.py), checked by K07",
   "C3 hook candidates: every dev-team agent hook command probes, in order, \"$CLAUDE_PROJECT_DIR/.claude/skills/dev-team\" \"$CLAUDE_PROJECT_DIR\"/.claude/skills/dev-team-* \"$HOME/.claude/skills/dev-team\" \"$HOME\"/.claude/skills/dev-team-* and execs the first <d>/scripts/guard.py that exists, else exit 0; devteam.py hooks_resolve() probes the same list; pin_hooks()/HOOK_LOOP_RE must still rewrite the loop to the absolute pinned path — established in K06 (agents) and K02 (hooks_resolve)",
   "C4 no-renames: every `git diff --name-only`/`--name-status` used for footprint, frozen-test, stray or committed checks in devteam.py and guard.py passes --no-renames — established in K01 (devteam.py) and K05 (guard.py)"
 ],
 "notes": "THE SPEC IS AUTHORITATIVE: claude-skills/docs/superpowers/specs/2026-09-29-claude-skills-optimization-design.md. Read its §2 (test home, portability) and the W-items your slice goal lists (e.g. 'W1-1'); follow them exactly, do not redesign, do not fix items owned by other slices. The worktree root is the git root (the folder that CONTAINS claude-skills/); all paths and commands are relative to it. Tests: stdlib unittest, exactly the test file(s) in your footprint, no shared helper modules; build fixtures with tempfile.mkdtemp() in the SYSTEM temp dir and os.path.realpath() them — never under the repo or a worktree (guard.py/devteam.py walk up parent dirs looking for .slice/ and .claude/dev-team/, so a fixture nested inside a worktree is contaminated); run the skill scripts via subprocess (sys.executable / bash / sh / node) with timeouts; set HOME to a temp dir for any script that could write under $HOME; no network; never touch the repo working tree or real state; each test file under ~60 s (share fixture repos via setUpClass). test_file's {files} is ONE test file basename, e.g. -p test_guard_security.py (run once per test file). Scripts stay stdlib-only Python 3.8+ (no runtime 3.9+ features: no list[str]/dict[str,int] annotations evaluated at runtime, no match, no str.removeprefix), POSIX sh or bash 3.2 (no mapfile, declare -A, ${x,,}, wait -n; bisect-parallel.sh is bash-only), Node with no dependencies. `!` preload scripts (brainstorming scripts/context.sh, writing-plans plan_tool.py context, git-diff-summary scripts/gather.sh) must stay read-only, bounded and ALWAYS exit 0. Never rename or move a script (allowed-tools pins exact paths). guard.py and devteam.py duplicate TEST_DIR_NAMES, TEST_FILE_PATTERNS, STATE_DIRNAME, is_test_path, path_matches — keep them identical. The working copy under claude-skills/dev-team-v3.2 is NOT the engine running this session; exercise it only against temp fixture repos, never against the real .claude/dev-team/ state. Perf items: paste before/after timings in your report. CHANGELOG/README edits only in the slice whose footprint owns that file. Representative test style: subprocess-driven black-box tests of the real script in a temp git repo.",
 "review_batch": 8,
 "checkpoint_every": 8,
 "slices": [
  {"id": "K01", "title": "devteam.py safety: worktree-root guard, --no-renames, plan type checks, mode-aware claim hints",
   "goal": "Spec W1-1, W1-2 (devteam.py side of C4), W1-3, W1-11 (devteam.py side of C2), W1-12, W1-13.",
   "kind": "code", "size": "large", "deps": [], "risk": "high", "isolation": false,
   "files": ["claude-skills/dev-team-v3.2/scripts/devteam.py", "claude-skills/tests/test_devteam_safety.py"],
   "criteria": [
     "remove_worktree(root, wt) is a no-op when realpath(wt) == realpath(root): integrating a slice whose claim points at the integration checkout leaves the repo and .git intact",
     "a slice that `git mv`s a file from outside its footprint into its footprint is rejected at integrate (the deleted original is detected); renaming a frozen test is rejected",
     "validate_plan rejects with a clean DevteamError (no traceback, no state written): non-str id, non-list or non-str-element deps/files/criteria; the same check runs on the retry plan refresh",
     "path_matches strips only leading './' prefixes: '.env' does not match 'env', '.github/x' does not match 'github/'",
     "strict add-fixes with a non-dict spec exits with a clean DevteamError message",
     "the claim header and the dirty-tree rejection name the helpers of the claimed mode (SLICE/RED/GREEN: commit-red/commit-green; WORK: commit-work; FAST: commit-fast)"],
   "edge_cases": ["claim worktree path given via a symlinked parent", "numeric id 1 with deps [1]", "rename with similarity < 50%"],
   "context": ["claude-skills/dev-team-v3.2/scripts/devteam.py#remove_worktree", "claude-skills/dev-team-v3.2/scripts/devteam.py#validate_plan", "claude-skills/dev-team-v3.2/scripts/devteam.py#integrate_one", "claude-skills/dev-team-v3.2/scripts/selftest.sh (how the engine is driven end-to-end)"]},

  {"id": "K02", "title": "devteam.py scheduling correctness: --force wipe, doctor/init, research footprints, red-done busy, stall hint, finish, reservations, hook candidates",
   "goal": "Spec W1-4, W1-5, W1-6, W1-7, W1-8, W1-9, W1-10, W1-14 (devteam.py side of C3) and W1 perf (c).",
   "kind": "code", "size": "large", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/dev-team-v3.2/scripts/devteam.py", "claude-skills/tests/test_devteam_sched.py"],
   "criteria": [
     "init --force / start --force leave no stale reviews/, logs/ or research/ files; a new brief or checkpoint deletes its own target report/log first, so a stale r1.report.md is never harvested and a stale checkpoint log never counts as PASS",
     "start succeeds in a repo that tracks .claude/agents/*.md which doctor --fix rewrites (only the paths doctor wrote are excluded from init's dirty check)",
     "research slices hold no footprint (never serialize code slices) and accept files: []",
     "a slice in red-done state marks its footprint busy",
     "when nothing is in flight, nothing is ready and slices still wait, next prints a stuck/UNRESOLVED line naming each blocked slice, its failed dependency and the recovery command",
     "finish counts merges[reviewed_upto:] as unreviewed in its warning",
     "print_ready's advertised free slots subtract review-shard reservations; a CHANGES_REQUIRED review reserves slots only for its non-APPROVED shards",
     "hooks_resolve() probes the C3 candidate list including dev-team-* folders"],
   "edge_cases": ["failed slice with two dependents", "research slice with files: []", "review with all shards APPROVED"],
   "context": ["claude-skills/dev-team-v3.2/scripts/devteam.py#cmd_init", "claude-skills/dev-team-v3.2/scripts/devteam.py#ready_slices", "claude-skills/dev-team-v3.2/scripts/devteam.py#print_ready", "claude-skills/dev-team-v3.2/scripts/devteam.py#cmd_finish", "claude-skills/dev-team-v3.2/scripts/devteam.py#hooks_resolve"]},

  {"id": "K03", "title": "devteam.py hot-path speedups (behaviour-preserving)",
   "goal": "Spec W1 perf (a), (b), (d), (e): hoist rev-parse out of do_dispatch, compute ready_slices once per next with literal-path set overlap, drop dead/duplicate git calls, fewer git calls per integrate.",
   "kind": "refactor", "size": "small", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/dev-team-v3.2/scripts/devteam.py"],
   "criteria": [
     "the full claude-skills test suite passes before and after with identical results (pasted)",
     "`next` on a 62-slice fixture plan prints byte-identical output before/after, and its wall time drops (before/after numbers pasted; target ≤ 0.35 s from ~1.0 s)",
     "integrate performs at least 3 fewer git subprocess calls per slice (count pasted)"],
   "edge_cases": ["footprints mixing literal files, directories and globs"],
   "context": ["claude-skills/dev-team-v3.2/scripts/devteam.py#do_dispatch", "claude-skills/dev-team-v3.2/scripts/devteam.py#ready_slices", "claude-skills/dev-team-v3.2/scripts/devteam.py#integrate_one"]},

  {"id": "K04", "title": "guard.py security: realpath edit paths, canonical allow match, no write-capable read-only commands, lanes cannot drive the engine",
   "goal": "Spec W2-1, W2-2, W2-3 and the §8 addendum item (canonical .slice/allow match).",
   "kind": "code", "size": "large", "deps": [], "risk": "high", "isolation": false,
   "files": ["claude-skills/dev-team-v3.2/scripts/guard.py", "claude-skills/tests/test_guard_security.py"],
   "criteria": [
     "an in-footprint edit reached through a symlinked path (e.g. /var vs /private/var, symlinked project dir) is allowed; an out-of-footprint edit is still denied",
     "a pinned commit helper typed with the literal (non-resolved) script path is pre-approved when .slice/allow holds the resolved path, and vice versa; no other devteam.py command becomes pre-approved",
     "none of these is pre-approved for programmers or read-only roles: git diff/log --output=…, git grep -O…/--open-files-in-pager, sort -o/--output, sed with a w command, rg --pre",
     "a lane running devteam.py integrate/finish/reset/next/dispatch (any subcommand other than claim, commit-red, commit-green, commit-work, commit-fast) is denied with a reason",
     "the guard stays fail-open on malformed hook input (exit 0, no traceback)"],
   "edge_cases": ["relative file_path with ..", "script path containing spaces", "sed -n 'p' (still read-only)"],
   "context": ["claude-skills/dev-team-v3.2/scripts/guard.py#guard_edit", "claude-skills/dev-team-v3.2/scripts/guard.py#guard_bash", "claude-skills/dev-team-v3.2/scripts/guard.py#script_path", "claude-skills/dev-team-v3.2/scripts/selftest.sh (guard invocation shape: JSON on stdin)"]},

  {"id": "K05", "title": "guard.py false denials, committed check, prefix/rename fixes, Edit-path speedup",
   "goal": "Spec W2-4, W2-5, W2-6 (guard.py side of C2), W2-7 (guard.py side of C4), W2 perf (a), (b).",
   "kind": "code", "size": "small", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/dev-team-v3.2/scripts/guard.py", "claude-skills/tests/test_guard_denials.py"],
   "criteria": [
     "not denied: git merge-base, git stash list, git worktree list, cat .slice/base 2>/dev/null, grep -rn \"=>\" src/ and git log --format='%h -> %s' for read-only roles",
     "still denied: git merge, git stash (push/pop), real > redirects to files outside the footprint",
     "with .slice/base known, the committed check is HEAD != base (an old commit reusing the slice id no longer counts)",
     "path_matches implements C2; name-only diffs pass --no-renames (C4)",
     "an Edit during RED/WORK/FAST no longer spawns git log (hook time before/after pasted); subprocess is imported lazily"],
   "edge_cases": ["2>&1 and >/dev/null variants", "quoted string containing both > and a real redirect after it"],
   "context": ["claude-skills/dev-team-v3.2/scripts/guard.py#ensure_red_cache", "claude-skills/dev-team-v3.2/scripts/guard.py#path_matches"]},

  {"id": "K06", "title": "dev-team agent hooks find dev-team-* installs; trim SKILL.md speed-ceiling duplication",
   "goal": "Spec W4-1 (agents side of C3) and W4-2.",
   "kind": "code", "size": "small", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/dev-team-v3.2/agents/team-leader.md", "claude-skills/dev-team-v3.2/agents/programmer.md", "claude-skills/dev-team-v3.2/agents/code-reviewer.md", "claude-skills/dev-team-v3.2/agents/spot-reviewer.md", "claude-skills/dev-team-v3.2/agents/investigator.md", "claude-skills/dev-team-v3.2/SKILL.md", "claude-skills/tests/test_agent_hooks.py"],
   "criteria": [
     "each hook command in all 5 agents, run under sh (and dash if present) with HOME pointing at a temp dir containing .claude/skills/dev-team-v3.2/scripts/guard.py (a stub that prints a marker), executes that stub with the right mode argument",
     "with no matching skill dir the command exits 0 silently",
     "devteam.py's pin_hooks() (imported read-only from the working copy) rewrites every hook command in all 5 files to the absolute pinned guard path (HOOK_LOOP_RE still matches)",
     "SKILL.md 'Speed ceiling' keeps the 'Remaining dials' list and the closing sentence and drops only the opening enumeration; frontmatter unchanged"],
   "edge_cases": ["CLAUDE_PROJECT_DIR unset", "two dev-team-* dirs present (first match wins)"],
   "context": ["claude-skills/dev-team-v3.2/scripts/devteam.py#pin_hooks", "claude-skills/dev-team-v3.2/scripts/devteam.py#HOOK_LOOP_RE"]},

  {"id": "K07", "title": "regression test: guard.py/devteam.py duplicated definitions stay identical; Python 3.8 grammar",
   "goal": "Lock C2 and the duplicated constants (spec W2 last bullet) with a test; also assert every claude-skills Python script parses with ast.parse(feature_version=(3, 8)).",
   "kind": "test", "size": "trivial", "deps": ["K01", "K05"], "risk": "low", "isolation": false,
   "files": ["claude-skills/tests/test_devteam_guard_sync.py"],
   "criteria": [
     "fails if TEST_DIR_NAMES, TEST_FILE_PATTERNS, STATE_DIRNAME, is_test_path or path_matches differ between devteam.py and guard.py (AST comparison)",
     "fails if any claude-skills/*/scripts/*.py or requirements-code-audit/hooks/*.py does not parse with ast.parse(src, feature_version=(3, 8))"],
   "edge_cases": [],
   "context": ["claude-skills/dev-team-v3.2/scripts/devteam.py", "claude-skills/dev-team-v3.2/scripts/guard.py"]},

  {"id": "K08", "title": "selftest.sh green on macOS + README changelog for dev-team",
   "goal": "Spec W3 (+ §8 addendum harness items) and W4-3: fix the harness-only failures, update checks only where K01–K06 intentionally changed output, record W1–W4 behaviour changes in README.md (Vietnamese).",
   "kind": "chore", "size": "small", "deps": ["K01", "K02", "K03", "K04", "K05", "K06"], "risk": "low", "isolation": false,
   "files": ["claude-skills/dev-team-v3.2/scripts/selftest.sh", "claude-skills/dev-team-v3.2/README.md"],
   "criteria": [
     "bash claude-skills/dev-team-v3.2/scripts/selftest.sh reports 0 failures on macOS bash 3.2 / BSD sed, run from a Claude Code shell (inherited CLAUDE_*/BASH_* env vars neutralised for the doctor checks)",
     "any check edited because of an intended K01–K06 output change is listed in the report with the spec item that changed it; a failure caused by a product regression is NOT papered over — report it as Blocked with the evidence",
     "runtime stays ≤ ~45 s (pasted); still isolated (mktemp, no network, no $HOME writes)",
     "README.md (Vietnamese) gains a changelog entry covering the W1–W4 behaviour changes"],
   "edge_cases": ["GNU sed present on PATH (portable form must work with both)"],
   "context": ["claude-skills/dev-team-v3.2/scripts/selftest.sh"],
   "verify": "bash claude-skills/dev-team-v3.2/scripts/selftest.sh"},

  {"id": "K09", "title": "audit.py: deterministic spot-check and a status state machine that never says wait with nothing running",
   "goal": "Spec W5-1 and W5-2.",
   "kind": "code", "size": "large", "deps": [], "risk": "high", "isolation": false,
   "files": ["claude-skills/requirements-code-audit/scripts/audit.py", "claude-skills/tests/test_audit_status.py"],
   "criteria": [
     "the spot-check sample is a fixed function of the item set: adjudicating queue items never changes which other items are sampled, and repeated `adjudicate --accept-queue` drains the queue to empty",
     "after a partial SubagentStop, status's NEXT names the redispatch command; after --redispatch the stale events file no longer flags the batch as stuck; retry events batch-NN-rNNN count for batch-NN",
     "--undispatch, --redispatch and --failed work for verifier batches (batch-VNN); a failed verifier batch's ids leave verify_assigned and reappear for verification",
     "solo mode re-lists undispatched verifier batches on every status",
     "whenever nothing is running, NEXT is a concrete command, never 'wait for completion notifications'"],
   "edge_cases": ["600-item fixture", "batch with zero findings", "events file older than the batch dispatch time"],
   "context": ["claude-skills/requirements-code-audit/scripts/audit.py#cmd_status", "claude-skills/requirements-code-audit/references/schemas.md", "claude-skills/requirements-code-audit/SKILL.md (pipeline order)"]},

  {"id": "K10", "title": "audit.py: idempotent re-runs, robust JSONL, schema/adjudication fixes, fewer lead turns",
   "goal": "Spec W5-3 … W5-10 and W5 perf (a), (b).",
   "kind": "code", "size": "large", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/requirements-code-audit/scripts/audit.py", "claude-skills/tests/test_audit_misc.py"],
   "criteria": [
     "re-running plan clears stale findings/verify/events; re-running parse-plan clears stale section files and parse-merge reads only sections 1..expected",
     "a pretty-printed (multi-line) JSON findings file is parsed; unparseable lines are reported by status",
     "FINDINGS_SCHEMA's status enum includes UNSEARCHED",
     "plan entries with ids as a string are treated as a one-element list everywhere",
     "adjudicate --accept/--accept-queue refuse UNSEARCHED; check skips the searched-terms rule for adjudicated ids; check accepts lines 'L41-L58' and en-dash ranges",
     "git_exclude writes the common-dir info/exclude from a linked worktree",
     "adjudicate with 323 queued ids of 600 runs in < 0.5 s (was 4.0 s; timings pasted)",
     "status prints the adjudication queue itself once waves are complete; adjudicate prints the next step; report runs the check logic inline and prints its verdict (state the exact new lines in the report for K12)"],
   "edge_cases": ["empty findings file", "BOM at file start"],
   "context": ["claude-skills/requirements-code-audit/scripts/audit.py#read_jsonl", "claude-skills/requirements-code-audit/scripts/audit.py#cmd_adjudicate", "claude-skills/requirements-code-audit/scripts/audit.py#cmd_check"]},

  {"id": "K11", "title": "audit guard hooks: no false doc blocks on source files, no chained-command auto-allow, faster hook",
   "goal": "Spec W6-1 … W6-4.",
   "kind": "code", "size": "small", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/requirements-code-audit/hooks/audit_guard.py", "claude-skills/requirements-code-audit/hooks/audit_guard.sh", "claude-skills/tests/test_audit_guard.py"],
   "criteria": [
     "with .audit/ACTIVE present, reads of src/orders/history.ts, src/license/validator.go, src/HistoryController.php, src/notices.py, src/changes_feed.py and docs/api/handler.py are allowed; README.md, CHANGELOG, HISTORY.md, docs/guide.md are still blocked",
     "`python3 <scripts>/audit.py status && rm -rf src` (and ; | ` $( newline variants) is not auto-allowed; the plain audit.py command still is",
     "worker Bash with 2>/dev/null, grep '=>' or grep 'git log' is not blocked; real git log/show history access still is",
     "audit_guard.sh invokes the Python guard with -S; inactive path still exits fast without starting Python (timings pasted)"],
   "edge_cases": ["Windows-style path separators ignored", "uppercase LICENSE.TXT"],
   "context": ["claude-skills/requirements-code-audit/hooks/hooks.json"]},

  {"id": "K12", "title": "requirements-code-audit docs match the fixed engine",
   "goal": "Spec W7-1 … W7-3.",
   "kind": "docs", "size": "small", "deps": ["K09", "K10", "K11"], "risk": "low", "isolation": false,
   "files": ["claude-skills/requirements-code-audit/SKILL.md", "claude-skills/requirements-code-audit/references/schemas.md", "claude-skills/requirements-code-audit/references/report-format.md", "claude-skills/requirements-code-audit/references/workflow-mode.md", "claude-skills/requirements-code-audit/agents/rca-investigator.md", "claude-skills/requirements-code-audit/SETUP.md"],
   "criteria": [
     "every subcommand/flag/NEXT behaviour the docs describe matches the merged audit.py (verified against --help and the K09/K10 output lines); steps made redundant by K10 are removed",
     "rca-investigator.md maxTurns is 80",
     "SETUP.md notes plugin subagents ignore permissionMode and gives the allow rule for worker writes under .audit/",
     "SKILL.md description stays ≤ 1024 chars"],
   "edge_cases": [],
   "context": ["claude-skills/requirements-code-audit/scripts/audit.py"],
   "verify": "python3 claude-skills/requirements-code-audit/scripts/audit.py --help && grep -n 'maxTurns' claude-skills/requirements-code-audit/agents/rca-investigator.md"},

  {"id": "K13", "title": "plan_tool.py lint: fence-aware headings/spec map, portability scan skips code, correct file and git parsing",
   "goal": "Spec W8-2, W8-3, W8-4, W8-5, W8-9.",
   "kind": "code", "size": "small", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/writing-plans-6.2/scripts/plan_tool.py", "claude-skills/tests/test_plan_lint.py"],
   "criteria": [
     "a task body with '# comment' lines inside ```python/```bash fences and '# Title' inside a ```markdown fence passes lint-task; a '### T05' line anywhere still fails",
     "the portability scan ignores fenced and backticked text and URLs (.claude/…, CLAUDE.md, import anthropic, docs/superpowers/specs/… pass) but still flags banned words in prose; TODO/TBD/FIXME/XXX match case-sensitively ('Todo', \"xxx\" pass)",
     "files_block accepts Makefile, Dockerfile, LICENSE and ignores annotations like app.run() after the first backtick span",
     "`git add a b && git commit -m \"msg\"` in a step yields no false errors",
     "the spec heading map ignores '#' lines inside code fences (no false 'WARN spec uncovered')"],
   "edge_cases": ["~~~ fences", "nested ```` fences", "unterminated fence"],
   "context": ["claude-skills/writing-plans-6.2/scripts/plan_tool.py", "claude-skills/writing-plans-6.2/task-writer-prompt.md"]},

  {"id": "K14", "title": "writing-plans preload never cancels the skill; bounded context; contract hashing; warn/fail marks; stale agent detection; faster assemble/wait",
   "goal": "Spec W8-1, W8-6, W8-7, W8-8, W8-10, W8-11, W8 perf (a)–(d) and the W8 SKILL.md contract items; CHANGELOG (Vietnamese) entry for W8.",
   "kind": "code", "size": "large", "deps": [], "risk": "high", "isolation": false,
   "files": ["claude-skills/writing-plans-6.2/scripts/plan_tool.py", "claude-skills/writing-plans-6.2/SKILL.md", "claude-skills/writing-plans-6.2/CHANGELOG.md", "claude-skills/tests/test_plan_tool.py"],
   "criteria": [
     "SKILL.md's preload passes \"$ARGUMENTS\" as one quoted argument; `context` exits 0 and prints a bounded context for: no args, '--thorough', '--thorough path/spec.md', \"let's plan (see spec)\", an empty string, a nonexistent path, outside any git repo",
     "context output is ≤ ~55 lines on a 300-file repo (file list capped ~30) and uses git --no-optional-locks (index mtime unchanged)",
     "re-running contracts after a contract change drops that task's body and .ok mark; unchanged contracts keep theirs",
     "hook-lint and lint-task share one mark helper: a warning writes .warn, a clean lint removes a stale .warn, a lint failure writes .fail; wait returns PENDING early once all pending tasks are failing and unchanged ≥ 45 s",
     "an installed agent file still containing __PLAN_TOOL__ is reported stale with the setup --apply hint regardless of cap",
     "assemble checks JS blocks with node --check in parallel (70-task timing before/after pasted); reviewer briefs inline existing target files like writer briefs",
     "SKILL.md: --allow advice in Phase 1, hand-off to dev-team, no 'ultracode', setup trigger covers the stale agent; description ≤ 1024 chars; CHANGELOG.md (Vietnamese) records W8 and fixes the install path"],
   "edge_cases": ["ARGUMENTS containing a double quote", "detached HEAD", "repo with no commits"],
   "context": ["claude-skills/writing-plans-6.2/scripts/plan_tool.py#cmd_context", "claude-skills/writing-plans-6.2/agents/plan-task-writer.md"]},

  {"id": "K15", "title": "brainstorming server.cjs/helper.js/frame-template: literal content injection, crash/signal safety, session_dir, safe files route, no external assets",
   "goal": "Spec W9-2, W9-3, W9-4 (C1), W9-7, W9-8, W9-9, W9-11, W9-13, W9 perf (d).",
   "kind": "code", "size": "large", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/brainstorming-6.3/scripts/server.cjs", "claude-skills/brainstorming-6.3/scripts/helper.js", "claude-skills/brainstorming-6.3/scripts/frame-template.html", "claude-skills/tests/test_brainstorm_server.py"],
   "criteria": [
     "a fragment containing $&, $$, $' and $` renders verbatim",
     "an exception in a request/message handler returns 500 and the server keeps serving; SIGTERM/SIGINT/SIGHUP write server-stopped and remove server-info",
     "the server-started JSON and server-info include session_dir (C1)",
     "/files/my%20image.png serves 'my image.png'; traversal attempts still 404",
     "symlinked or non-regular *.html files never trigger screen-added",
     "a WebSocket frame sent in the same packet as the upgrade handshake is processed",
     "a new screen renames events to events.prev instead of deleting it",
     "rendered pages reference no external host; version shows from the skill CHANGELOG heading or is omitted",
     "helper.js click events carry whitespace-normalised text (≤120 chars) and, for multiselect, a selected boolean; node --check passes for server.cjs and helper.js"],
   "edge_cases": ["fragment that is a full HTML document", "invalid percent-encoding in /files/"],
   "context": ["claude-skills/brainstorming-6.3/visual-companion.md", "claude-skills/brainstorming-6.3/scripts/start-server.sh (how the server is launched)"]},

  {"id": "K16", "title": "brainstorming start/stop scripts: relative project dir, stop prior sessions, robust owner pid, fast failure, clean stop",
   "goal": "Spec W9-1, W9-5, W9-6, W9-10, W9 perf (a), (b).",
   "kind": "code", "size": "small", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/brainstorming-6.3/scripts/start-server.sh", "claude-skills/brainstorming-6.3/scripts/stop-server.sh", "claude-skills/tests/test_brainstorm_start_stop.py"],
   "criteria": [
     "start-server.sh --project-dir . (run from the project dir) starts the server",
     "a second start for the same project dir stops the first session (checked via its instance id); an unrelated process is never signalled",
     "the owner pid survives wrappers (/usr/bin/time, env, nohup): the server does not self-stop while the real owner lives",
     "if node dies at once, start-server.sh fails within ~1 s with the last 3 server.log lines in the error JSON; a healthy start takes ≤ ~0.5 s (timings pasted)",
     "stop-server.sh on an already-exited server keeps the recorded exit reason and still cleans the /tmp session dir",
     "bash -n and sh -n pass; bash 3.2 compatible"],
   "edge_cases": ["project dir path with spaces", "stale pid file pointing at a reused pid"],
   "context": ["claude-skills/brainstorming-6.3/scripts/server.cjs (server-info/server-stopped files)", "claude-skills/brainstorming-6.3/visual-companion.md"]},

  {"id": "K17", "title": "brainstorming context.sh: inline npm deps, cwd-scoped hot_dirs, faster on huge commits",
   "goal": "Spec W9-12 and W9 perf (c).",
   "kind": "code", "size": "small", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/brainstorming-6.3/scripts/context.sh", "claude-skills/tests/test_brainstorm_context.py"],
   "criteria": [
     "package.json with \"dependencies\": {} or { \"react\": \"^18\" } on one line prints correct npm_deps",
     "run from a subdirectory of a repo, hot_dirs lists only dirs under cwd",
     "exits 0 with ≤ ~55 lines in: a non-git dir, an empty repo, a bare repo, $HOME-like dir, under dash",
     "a 150k-file commit fixture completes faster than before (timings pasted)"],
   "edge_cases": ["package.json without dependencies", "cwd with spaces"],
   "context": ["claude-skills/brainstorming-6.3/SKILL.md (preload line)"]},

  {"id": "K18", "title": "brainstorming docs match the fixed scripts; no permission prompts for start/stop; leaner SKILL.md",
   "goal": "Spec W10-1 … W10-3.",
   "kind": "docs", "size": "small", "deps": ["K15", "K16", "K17"], "risk": "low", "isolation": false,
   "files": ["claude-skills/brainstorming-6.3/SKILL.md", "claude-skills/brainstorming-6.3/visual-companion.md", "claude-skills/brainstorming-6.3/research-playbook.md", "claude-skills/brainstorming-6.3/CHANGELOG.md"],
   "criteria": [
     "visual-companion.md: saves session_dir and stops with it, liveness via kill -0 on server.pid, events read before writing a new screen (or events.prev), documents /files/<name> and multiselect selected",
     "SKILL.md allowed-tools pre-approves start-server.sh and stop-server.sh under ${CLAUDE_SKILL_DIR} in exactly the form the docs tell the model to run; the preload line is unchanged",
     "the literal registry URL list lives only in research-playbook.md; SKILL.md keeps one sentence; description ≤ 1024 chars",
     "CHANGELOG.md records W9–W10"],
   "edge_cases": [],
   "context": ["claude-skills/brainstorming-6.3/scripts/start-server.sh", "claude-skills/brainstorming-6.3/scripts/stop-server.sh", "claude-skills/brainstorming-6.3/scripts/server.cjs"],
   "verify": "sh claude-skills/brainstorming-6.3/scripts/context.sh >/dev/null; echo context_rc=$?; grep -n 'start-server.sh\\|stop-server.sh' claude-skills/brainstorming-6.3/SKILL.md"},

  {"id": "K19", "title": "systematic-debugging scripts: no orphaned workers, kill-before-cleanup, -t warning, fewer forks",
   "goal": "Spec W11-1 … W11-5.",
   "kind": "code", "size": "small", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/systematic-debugging-6.3/scripts/_lib.sh", "claude-skills/systematic-debugging-6.3/scripts/stress.sh", "claude-skills/systematic-debugging-6.3/scripts/bisect-parallel.sh", "claude-skills/systematic-debugging-6.3/scripts/find-polluter.sh", "claude-skills/systematic-debugging-6.3/SKILL.md", "claude-skills/systematic-debugging-6.3/references/parallel-playbook.md", "claude-skills/systematic-debugging-6.3/README.md", "claude-skills/tests/test_debug_scripts.py"],
   "criteria": [
     "SIGTERM to stress.sh mid-run leaves no worker processes alive after ~2 s and removes its temp dir",
     "SIGTERM to bisect-parallel.sh and find-polluter.sh kills in-flight workers before removing worktrees/work dirs: no late 'No such file' errors, no surviving children, git worktree list clean",
     "bisect-parallel.sh -t without timeout/gtimeout on PATH prints the same warning as stress.sh",
     "bisect-parallel.sh still finds the regression commit in a 40-commit fixture (and status_of forks no cat)",
     "docs say -j defaults to min(64, CPUs) (bisect: minus 1); README records the fixes; bash -n passes; bash 3.2 compatible"],
   "edge_cases": ["all runs exit 125 (stress keeps its 125 contract)", "worker that ignores TERM (KILL after grace)"],
   "context": ["claude-skills/systematic-debugging-6.3/scripts/_lib.sh"]},

  {"id": "K20", "title": "git-diff-summary: preload never cancels, fewer git calls, pinned allowed-tools",
   "goal": "Spec W12 git-diff-summary items.",
   "kind": "code", "size": "small", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/git-diff-summary/scripts/gather.sh", "claude-skills/git-diff-summary/SKILL.md", "claude-skills/tests/test_gather.py"],
   "criteria": [
     "with an unwritable TMPDIR gather.sh prints GATHER_FAILED (mktemp) and exits 0; SKILL.md's marker table handles GATHER_FAILED",
     "no-fetch runs compute merge-base once and list untracked files once (git call count before/after pasted); output unchanged on the existing scenarios (branch ahead, uncommitted only, untracked only, detached HEAD, not a repo)",
     "SKILL.md allowed-tools pins the script under ${CLAUDE_SKILL_DIR} and matches the preload invocation byte-for-byte; description ≤ 1024 chars"],
   "edge_cases": ["filenames with spaces/unicode"],
   "context": ["claude-skills/git-diff-summary/SKILL.md"]},

  {"id": "K21", "title": "doc-generator references restored; frontend-design LICENSE.txt",
   "goal": "Spec W12 doc-generator and frontend-design items.",
   "kind": "docs", "size": "small", "deps": [], "risk": "low", "isolation": false,
   "files": ["claude-skills/doc-generator/references/doc-catalog.md", "claude-skills/doc-generator/references/writer-brief.md", "claude-skills/doc-generator/references/reviewer-brief.md", "claude-skills/frontend-design-Jun18/LICENSE.txt"],
   "criteria": [
     "the three references exist, adapted from the originals at /Users/yamazaki-ethan/.claude/skills/synced/140822c8-da03-41c0-9930-11b1998849a8_66c5b54c-025b-415b-8197-8286c1a4e85e/doc-generator/references/ (read with the Read tool) to the LOCAL doc-generator/SKILL.md: the catalog has the ★ starter-set and HIGH/LOW tier columns the SKILL.md decision table uses, and every doc name, section or rule SKILL.md cites from them exists",
     "the briefs are short enough to condense into Task prompts as SKILL.md describes",
     "frontend-design-Jun18/LICENSE.txt is a verbatim copy of /Users/yamazaki-ethan/.claude/plugins/cache/claude-plugins-official/frontend-design/022b3c274938/skills/frontend-design/LICENSE.txt"],
   "edge_cases": [],
   "context": ["claude-skills/doc-generator/SKILL.md", "glm-skills/doc-generator-glm/SKILL.md (read-only: its inlined catalog table shows the ★/tier layout)"],
   "verify": "ls claude-skills/doc-generator/references && grep -c '★' claude-skills/doc-generator/references/doc-catalog.md && head -3 claude-skills/frontend-design-Jun18/LICENSE.txt"}
 ]}
```
