# GLM skills — OpenCode v1/v2 hardening and optimization

Status: approved by the user on 2026-09-28 (approach 1, full scope, no reinstall into the user's real OpenCode config)
Date: 2026-09-28
Scope root: `glm-skills/` (edits stay inside this folder)

## 1. Goal and scope

Make every GLM port (`brainstorming-glm`, `dev-team-glm`, `doc-generator-glm`,
`requirements-code-audit-glm`, `systematic-debugging-glm`, `writing-plans-glm`) plus `_shared/` and
`install-opencode.sh` work correctly on OpenCode v1 stable (1.18.x) and v2 beta (2.0.x). Fix every
verified CRITICAL/MAJOR defect and every OpenCode gap found by the 2026-09-28 audit, fix cheap MINORs in
files already being touched, and take the listed optimizations.

In scope: code, SKILL.md instructions, OpenCode agent/command/plugin files, tests, the installer, each
skill's CHANGELOG/README, and `glm-skills/CLAUDE.md` harness facts.

Out of scope: resuming lanes via `--session`, a writing-plans `export-slices` subcommand, using the v2
`question` tool for approval gates, the Claude originals one level up, and the user's real
`~/.config/opencode` (never reinstalled or cleaned by this work).

## 2. Approaches

1. **Shared compatibility layer + parallel per-skill fixes (recommended).** Put harness detection,
   dispatch-line rendering, run-command building, event parsing, throttle detection and lane lifecycle
   in `_shared/oc_harness.py` (already vendored into every skill by `_shared/sync.sh`). Skills call it
   instead of re-deriving OpenCode facts.
   - Pro: one fix per OpenCode fact. Today's drift, where 5 skills each detect the harness from
     `$OPENCODE` and all miss v2, cannot recur.
   - Pro: per-skill slices get disjoint footprints and run in parallel after wave 0.
   - Con: wave 0 is on the critical path, and a sync step touches every skill's `scripts/`.
2. **Per-skill fixes only.** Every skill patches its own detection and dispatch.
   - Rejected: it copies the same logic into 5 places, which is how the drift happened in the first
     place.
3. **Bugs only, no optimizations.**
   - Rejected: the user asked for optimization. Several "optimizations" are also correctness fixes on
     OpenCode, such as the serial fan-out on v1 and the 180 s stall kills.

## 3. Architecture

- **Wave 0 — `_shared` (serial, on the critical path).**
  - Change `oc_harness.py` and `zai_client.py`.
  - Fix the paths in `sync.sh`.
  - Make `tests/stub_opencode.py` match real v1/v2 output.
  - Repair the stale `skills/glm/...` fixture paths.
  - Run `sh _shared/sync.sh`, then the vendored-identity test.
- **Wave 1 — parallel per-skill slices with disjoint footprints.** No slice edits a vendored
  `scripts/oc_harness.py` or `scripts/zai_client.py`. Each slice owns its test files under
  `_shared/tests/`, so no two slices touch the same file. A slice's agent-render checks go in its own
  test file, not in the wave-0 `test_oc_render.py`.

  | Slice | Source footprint | Test files |
  | --- | --- | --- |
  | A. dev-team guard | `guard.py`, `opencode/plugins/*`, `agents/*`, `opencode/agents/*`, `opencode/commands/*` | `test_guard_oc.py`, `test_devteam_plugins.py` |
  | B. dev-team engine | `devteam.py`, `selftest.sh`, `SKILL.md`, `README.md` | `test_devteam_oc_lanes.py`, `test_devteam_oc_doctor.py` |
  | C | `systematic-debugging-glm/**` | `test_adopt_debug.py` |
  | D | `requirements-code-audit-glm/**` | `test_adopt_audit.py`, `test_audit_command.py`, `test_audit_setup_oc.py` |
  | E | `writing-plans-glm/**` | `test_adopt_plan.py` |
  | F | `brainstorming-glm/**` | `test_brainstorm_oc.py` |
  | G | `doc-generator-glm/**`, `install-opencode.sh` | `test_oc_install.py`, `test_all_skills.py` |

  Wave 0 owns `test_oc_run.py`, `test_oc_render.py`, `test_zai_client.py`, `test_vendored.py`,
  `test_oc_env_plugins.py`, the new `test_oc_contract.py`, `stub_opencode.py` and `fakeapi.py`.
  Slice A's selftest checks (DG4, DG5) are written by slice B, which owns `selftest.sh`. The dev-team
  `SKILL.md` belongs to slice B because its CLI changes (DE6 `resume`) drive the instructions. DG12
  therefore moves to slice B.
- **Wave 2 — verification and docs.**
  - The full unittest suite, the dev-team selftest, and the new real-binary contract tests.
  - A sandbox install plus an `opencode serve` API discovery check.
  - Updates to `glm-skills/CLAUDE.md` and to each skill's CHANGELOG/README.

## 4. Components — shared layer contract (`_shared/oc_harness.py`)

| Function / change | Contract |
| --- | --- |
| `harness()` | Returns `opencode` if any of these holds: `OPENCODE` or `OPENCODE_TERMINAL` is set; `DEVTEAM_HARNESS=opencode`; the script path is under an OpenCode skills dir (`.opencode/skills`, `.config/opencode/skills`, `$OPENCODE_CONFIG_DIR`); or a sibling `.oc-major` exists. Otherwise it returns `claude`, `zcode` or `unknown`. v2.0.18 sets only `OPENCODE_TERMINAL=1` in the shell. |
| `major()` | Read from `.oc-major` first, then cached `detect()`. |
| `dispatch_line(agent, prompt_path, background)` | On v1: `task(subagent_type=<agent>, …)`. On v2: `subagent(agent=<agent>, description, prompt, background=true)`. Never emits a model alias (v2 rejects a `model` not written `provider/model`). The fallback agent is `general`, never `general-purpose` or `Explore`. |
| `build_run_cmd` | Sends the brief on **stdin** and closes it, instead of passing it in argv. v2 wraps whitespace argv in literal quotes and parses a leading `-` as a flag; argv also hits E2BIG over 128 KiB on Linux. On v2, effort goes through `--model provider/model#effort` (`--agent` ignores the agent's model and variant). On v1, effort comes from the agent frontmatter `reasoningEffort` plus `--agent`, never a `#` suffix (v1 exits 1). |
| Setup snippet | Defines `variants` `low`/`high`/`max` (`reasoningEffort`) for `glm-5.3` and `glm-5.3-flash` under `zai-coding-plan`. Without this, `#max` fails with "Variant unavailable". It also carries a websearch note: v2 needs a provider, and without one a headless lane opens an interactive form that times out. |
| Throttle detection | Reads **error events only**. v2: `type=error`, `error.type=provider.rate-limit` or `status 429`. v1: `APIError` with `statusCode 429` or a `responseBody` code of `1302` or `1305`. Tool output never counts. |
| `aborted` event | Recorded as the lane error. |
| Stall | A per-lane `stall` value, with a default per role: about 900 s for programmer and team-leader, 600 s for reviewers. v2 emits JSON only at step and part boundaries. |
| Lifecycle | A SIGTERM/SIGINT handler kills every lane's process group. The opencode pgid is written to `lanes/<id>.pgid` so callers can `killpg` it. No orphans. |
| `result <out>` | Prints each lane's final assistant text, so models don't read the raw `.jsonl`. |
| Caching | Cache `detect()` and `check_run_flags()` per process. Each costs a spawn of the 179 MB binary. |
| `render_agent` | Agents the model dispatches are not `hidden` on v2 (hidden agents drop out of the subagent list). Emits `execute: deny` and an explicit `websearch` permission. |
| `check()` | Honours `--home`. |
| `zai_client` | Never sends `ANTHROPIC_API_KEY` to Z.ai. Looks up v2 credentials in `opencode.db` (v2 has no `auth.json`). It opens the database read-only (`file:…?mode=ro` URI), finds the table and column that hold provider credentials by introspecting the schema, and reads only an entry for `zai-coding-plan` or `zai`. Any error, missing table or unexpected shape skips the lookup silently. Never writes. |

**Shared bootstrap snippet (SKILL.md).** One ordered `for` loop, copied from
`systematic-debugging-glm/SKILL.md:18`. It looks, in order, at:
1. the "Base directory for this skill" line;
2. `$OPENCODE_CONFIG_DIR/skills`;
3. `.opencode/skills`;
4. `~/.config/opencode/skills`;
5. `.agents`, `~/.agents`, `.claude`, `~/.claude`, `.zcode`.

It exits with a clear message on a miss, never `python3 "" …`.

## 5. Per-skill fix inventory

Severity: C = CRITICAL, M = MAJOR, G = OpenCode gap, m = MINOR, O = optimization. The "test" column names
the proof: a unit test (U), a selftest check (S), a contract test against the real binary (K), or a doc
check (D).

### 5.1 `_shared` and installer (wave 0; IN* go to slice G)

| ID | File | Defect | Sev | Fix | Test |
| --- | --- | --- | --- | --- | --- |
| SH1 | `_shared/sync.sh:5-6,16` | Paths `../../..` and `skills/glm/_shared` don't exist; `mkdir -p` makes stray dirs outside the repo | M | Resolve paths relative to the script; no `mkdir` outside the repo | U `test_vendored` |
| SH2 | `tests/test_devteam_plugins.py:12`, `tests/test_vendored.py:11,36` | Hardcoded `skills/glm/...` causes 11 red tests; plugin JS is untested | M | Derive paths from `__file__` | U |
| SH3 | `oc_harness.py:234` | `THROTTLE_RE` matches tool output (`"1302"`, "429 Too Many Requests") and halves the wave for good | M | Look at error events only (§4) | U + K 429 |
| SH4 | `oc_harness.py:220-221` | Brief in argv: quote-wrapped on v2, leading `-` read as a flag, E2BIG on Linux; open stdin hangs | M | Brief on stdin, stdin closed | U + K |
| SH5 | `oc_harness.py:201` + setup snippet | `#max` fails on v2 unless the provider defines a `max` variant | M | Snippet defines variants; doctor checks them | K |
| SH6 | `oc_harness.py:331,361` | 180 s stall kills long bash calls or long thinking (v2 emits events only at boundaries) | M | Per-lane or per-role `stall` | U |
| SH7 | `oc_harness.py:240` | v2 `{"type":"aborted"}` ignored | m | Record it as the lane error | U |
| SH8 | `oc_harness.py:465` | `check()` ignores `--home` | m | Honour it | U |
| SH9 | `oc_harness.py` lane start | `start_new_session` lanes are orphaned when the parent is killed | M | Signal handler + pgid file | U |
| SH10 | `oc_harness.render_agent` | `hidden: true` on v2 hides the agent from the subagent list; GLM passes the name as a model | G | Don't hide dispatchable agents | U render |
| SH11 | `oc_harness.render_agent` | v2 exposes the `execute` (code-mode) tool; no websearch permission is emitted | G | `execute: deny`, explicit `websearch` | U render |
| SH12 | `oc_harness.py:333-337` | `detect()` and `check_run_flags()` respawn the binary on every `run_lanes` | O | Cache them | U |
| SH13 | new | Models read the raw lane `.jsonl` | O | `result <out>` subcommand | U |
| SH14 | new | No shared harness detection or dispatch rendering | G | `harness()`, `major()`, `dispatch_line()` | U |
| SH15 | `zai_client.py:51-52` | `ANTHROPIC_API_KEY` is used before the OpenCode files and sent to Z.ai (401) | M | Never use an Anthropic key for Z.ai | U |
| SH16 | `zai_client.py:55` | v2 keeps credentials in `opencode.db`, so no key is found | G | Read-only sqlite lookup, fail-soft | U |
| SH17 | `tests/stub_opencode.py:9,25,62` | Stub doesn't match v2 (version string, `--dir`, unknown flags, event fields `timestamp`/`sessionID`, `step_finish`, `aborted`, error shapes) | O | Two modes matching real v1.18 and v2.0 | U |
| SH18 | `oc_harness.py` stats | The final v2 text step has no `step_finish`, so token stats are incomplete | m | Tolerate the missing event; count what is present | U |
| IN1 | `install-opencode.sh:55` | Hints `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS`, which 2.0.18 lacks. v2 always scans `~/.claude/skills`, so `doc-generator` and `requirements-code-audit` clash with the originals; stale `*-glm` installs remain | G | Drop the hint on v2; list clashes and stale `*-glm` folders and print a removal command; never delete. The config-dir copy wins (verified) | U `test_oc_install` |
| IN2 | installer snippet | No websearch provider, so v2 headless websearch opens a form that times out | G | Print the provider note plus the `web-search-prime` MCP option | D |

### 5.2 dev-team guard, plugins, agents (slice A)

| ID | File | Defect | Sev | Fix | Test |
| --- | --- | --- | --- | --- | --- |
| DG1 | `guard.py:747,807` | `args` given as a JSON string (v2 `input.repair`) makes `.get` raise, and the call is allowed | C | `json.loads` a str; deny unparseable input in lane mode | U `test_guard_oc` |
| DG2 | `guard.py:716,771-776` | The patch-header regex anchors at column 0, but v2 trims lines, so an indented header bypasses read-only and footprint checks | C | Strip each line; check every header | U |
| DG3 | `guard.py:633,769` | Edit/write with no path is allowed in `edit-ro` | M | Deny | U |
| DG4 | `guard.py:253-259,346` | Read-only allow-list permits writes and exec: `git diff/log --output`, `git grep --open-files-in-pager`, `rg --pre`, `uniq in out`, `sed w/e`, `sort --compress-program` | M | Deny those flags and forms | U + S |
| DG5 | `guard.py:390-394` | Read-only roles run rewriting formatters (`black`, `ruff --fix/format`, `prettier --write`, `gofmt -w`, `go fmt`, `cargo fmt`, `isort`) | M | Deny for read-only roles | U + S |
| DG6 | `guard.py:167,175` | `abspath` vs `resolve()` symlink mismatch denies an in-footprint edit | m | Resolve both sides | U |
| DG7 | `guard.py:775` | `batch`, `question` and `execute` are silently allowed in lane mode | G | Deny in lane mode (headless `question` blocks) | U |
| DG8 | `plugins/devteam-guard.v2.js:12` | No role when `DEVTEAM_ROLE` is unset (agents started by the `subagent` tool) | G | Fall back to `event.agent` when it names a dev-team role | U plugins |
| DG9 | both plugins | Fail-open is silent per call | G | Keep fail-open (integrate re-checks); warn loudly once per lane and record it in the lane log | U |
| DG10 | `v1.js:8`, `v2.js:11-12` | Blocking `spawnSync` (~32 ms) on every tool; `api.tool.hook` not awaited | O | Spawn only for write/shell/patch/execute; async spawn; `await` registration | U + K |
| DG11 | `guard.py:764` | Deny message omits the pinned `.slice/allow` forms | O | Include them | U |
| DG12 | `SKILL.md:20` (slice B) | `${CLAUDE_SKILL_DIR}` is never set on OpenCode | G | Shared bootstrap snippet (§4) | D |
| DG13 | `programmer.md:20` (OpenCode) | Programmer re-runs `claim` though the prompt already is the claim output | O | Say so in the OpenCode agent | D |
| DG14 | `team-leader.md:23,68,78` + `guard.py` bash-ro | Memory path never given; `devteam.py status/probe` denied to read-only roles | G | Give the path; allow `status`/`probe` in bash-ro | U |
| DG15 | `README.md:58` | List items 3 and 4 joined on one line | m | Split them | D |

### 5.3 dev-team engine (slice B)

| ID | File | Defect | Sev | Fix | Test |
| --- | --- | --- | --- | --- | --- |
| DE1 | `devteam.py:1791` | Detection relies on `OPENCODE`, so v2 takes the Claude path (Claude doctor, `Agent →` lines, no lanes) | M | Use `oc_harness.harness()` | U + S |
| DE2 | `devteam.py:1857` | `killpg(lane pid)` misses opencode (own session); the orphan keeps editing the recreated worktree | M | `killpg` via the `lanes/<id>.pgid` file (SH9) | U |
| DE3 | `devteam.py:1975,1996` | No `stall=`, so the 180 s default kills tests/builds and burns stop-gate reruns | M | Stall per role | U |
| DE4 | `devteam.py:2653` | Checkpoint relies on `run_in_background`; v1 bash has none, so a >120 s suite is killed and `checkpoint_pending` sticks | G | Detached launch like `launch_lane`, then `wait` | U + S |
| DE5 | `devteam.py:3033,3080` | `review-pr` and `brief-debug` skip `emit_agent`, so lanes run without `DEVTEAM_ROLE` and are unguarded | G | Route through `emit_agent` | U |
| DE6 | `devteam.py:2160-2260,2798` | Rejected/BLOCKED says "SendMessage" after the lane exited; slot held forever | G | `resume <id> --note` relaunches a fresh lane in the same worktree and resets `.slice/stop_blocks` | U + S |
| DE7 | `devteam.py:1785` | v1 runs programmer-lite as programmer (effort high, not low) | G | Map to the lite agent | U |
| DE8 | `devteam.py:406` | The Claude cap of 20 also bounds OpenCode, so the 40/64 ceilings are unreachable | O | Apply the cap only on Claude | U |
| DE9 | `devteam.py:2894` | Tells OpenCode users to "Launch every Agent call" | m | Point to `wait` | U |
| DE10 | `devteam.py:2040-2055` | `wait` has no "no live lanes" exit and sleeps the whole timeout | m | Return when nothing is live | U |
| DE11 | `devteam.py:868-870` | `verify-intent` lane maps to rid `verify`, never in `open_reviews`, so a dead verify lane is unreported | m | Map correctly | U |
| DE12 | `devteam.py:733-751` | Scan offsets keyed by stem skip lines after a relaunch or truncation | m | Key by inode+size or reset on truncation | U |
| DE13 | `devteam.py:879` | Relaunch hint: no `python3` prefix, not detached, stale `.done` left | m | Fix the hint; clear the marker | U |
| DE14 | `devteam.py:1997` | Status not OK and HEAD == base still gets 3 doomed reruns | O | Write `.blocked` with the lane error | U |
| DE15 | `next`/`wait` | A signal-killed lane is silent | O | Report LANE DOWN when the pid is dead and there is no `.end` or marker | U |
| DE16 | `devteam.py:1996` | ResourceWarning: unclosed pipe | m | Close it | U |

### 5.4 systematic-debugging (slice C)

| ID | File | Defect | Sev | Fix | Test |
| --- | --- | --- | --- | --- | --- |
| SD1 | `debug_tool.py:53-58` (defaults `:894/:901/:910/:929`) | `clamp(0, default)` returns 1, so probe/run/experiment/scan run serially; scan's 64 workers are serial | C | Treat 0 as the default; keep the extra repros at `:322` serial (parallel runs in one tree fake flakiness) | U |
| SD2 | `debug_tool.py:160-163` | `race` has no word boundary, so "Traceback"/"backtrace" route to SWARM | M | `\brace\b` plus a traceback test | U |
| SD3 | `debug_tool.py:419` | FAST `NEXT` prints `run -- <cmd>` unquoted | M | `shlex.quote` | U |
| SD4 | `debug_tool.py:496-501,600` | Worktrees miss untracked and ignored files, so both arms fail and the result reads REFUTED | M | Copy untracked files, link configured ignored dirs; control not reproducing → INCONCLUSIVE | U |
| SD5 | `debug_tool.py:554`, `glm-tuning.md:43` | WIP applied before `patch_file`, so a patch containing WIP fails; relative path resolves in the worktree | M | Resolve against the caller's cwd; skip WIP when the patch already contains it | U |
| SD6 | `debug_tool.py:693-704` | Scan workers get only file names; keywords are the first 3 words; no code reaches the worker | M | Stopword filter, area-scoped grep once, capped code windows | U |
| SD7 | `debug_tool.py:458` | "wall" is the max single-command time | m | Measure real wall time | U |
| SD8 | `SKILL.md:55` | `'<its test file>'` placeholder gets run | m | Reword | D |
| SD9 | `bisect-parallel.sh:60` | `-t` silently ignored without `timeout`/`gtimeout` | m | Warn | S-style shell check |
| SD10 | `stress.sh:26` | Reusing `-o DIR` counts old results | m | Clear or refuse | shell check |
| SD11 | `debug_tool.py:67-72` | Timeout kills only bash; test processes survive | m | Kill the process group | U |
| SD12 | `debug_tool.py:828-847` | Setup provider `zai` vs agent `zai-coding-plan`; no variants; v1-only serial note; mentions an unused `oc_harness run` | G | Use the shared snippet | U |
| SD13 | `debug_tool.py:729-741`, `SKILL.md:83` | Agent lane never names `debug-worker` (v1 picks `general` at max); prompts in a mkdtemp dir outside the project trigger external_directory prompts | G | Name the agent; write prompts to `<root>/.debug/` | U |
| SD14 | `opencode/agents/debug-worker.md:22` | `<scripts>` placeholder never filled | G | Put `S=` in the prompts | U |
| SD15 | `SKILL.md:18` | Ignores the "Base directory" line, `$OPENCODE_CONFIG_DIR` and `--home` installs | G | Shared bootstrap snippet | D |
| SD16 | `debug_tool.py:729` | Agent lane on OpenCode is serial on v1 | O | Write `lanes.json`; `NEXT: python3 $S/oc_harness.py run` | U |
| SD17 | `opencode/commands/debug.md:5` | `/debug` re-runs the bootstrap | O | Add `S={{SKILL_DIR}}/scripts` | U render |
| SD18 | `debug_tool.py:221` | Greps the altered signature | O | Grep the longest quoted literal | U |

### 5.5 requirements-code-audit (slice D)

| ID | File | Defect | Sev | Fix | Test |
| --- | --- | --- | --- | --- | --- |
| RA1 | `audit.py:273-278,295` | `is_doc` substring match drops `security.py`, `todo.ts`, `history.py`, `support.go`, `requirements.txt`, `blog/`, `site/`, `design/`, `book/`, giving false MISSING | C | Classify prose by extension plus explicit doc dirs only | U |
| RA2 | `audit.py:1153` | `lstrip("./")` mangles `.eslintrc.json` and absolute paths | M | Strip the `./` prefix only | U |
| RA3 | `audit.py:607` | rg glob `*.ya?ml` matches nothing; `tests/**` and `migrations/**` match only at the root | M | `*.{yml,yaml}`, `**/tests/**`, `**/migrations/**` | U |
| RA4 | `audit.py:1330-1335` | Pass-1 errors stamped onto a clean pass-2 answer force UNSEARCHED | M | Clear errors on success | U |
| RA5 | `audit.py:1367,1434` | A verdict the checker rejected still wins; `check` falls back to pass-1 evidence, so an unproven MATCHED passes the gate | M | Rejected verdict → no verdict | U |
| RA6 | `audit.py:2467` | `status` re-dispatches verifiers for ids dispatched but unreported (duplicated work on v2 background) | M | Track dispatched ids | U |
| RA7 | `audit.py:1531-1546` | `--spec-text` written before the `--force` archive (empty spec); without `--force` it overwrites the old spec | M | Archive first, then write | U |
| RA8 | `audit.py:1844` | `run --resume` on the agent lane rebuilds every batch | m | Skip finished batches | U |
| RA9 | `audit.py:2710` | `main` ignores the return value, so `setup` exits 0 without opencode | m | `sys.exit(rc)` | U |
| RA10 | `SKILL.md:137` vs `audit.py:2281` | Doc says an unplanned CONFLICT fails the gate; code warns | m | Align the doc with the code | D |
| RA11 | `audit.py:2449,2503` | Dispatch prints `subagent_type=… model=haiku`; v2 wants `agent` and rejects aliases | G | `dispatch_line()` | U |
| RA12 | `opencode/agents/*.md` | `write_paths: .audit/**` is relative to the session dir, so a relocated `--out` or a subdir run is denied | G | Add `**/.audit/**` | U render |
| RA13 | `opencode/agents/*.md` | No `steps:` limit (ZCode uses 30/25) | G | Add matching `steps` | U render |
| RA14 | `audit.py:2585` | `setup` claims the agent lane runs through `oc_harness run`; it doesn't, so v1 stays serial | G | Route v1 through `oc_harness run`; v2 through background `subagent` | U |
| RA15 | `SETUP.md:10,12,28` | Paths lack the `-glm` suffix | m | Fix | D |
| RA16 | `SKILL.md:78` | Parallel `Read` loads the spec twice (`brief` prints it) | O | Drop the Read | D |
| RA17 | `audit.py:2418` | 64 one-item batches, serial on v1 | O | API lane keeps cap 64. The agent lane caps the batch count at the OpenCode lane width (`OC_MAX_LANES`, default 8) and groups items evenly into those batches | U |
| RA18 | `audit.py:1253` | Warm-up runs a whole `judge_one` (up to 4 calls) | O | One call | U |
| RA19 | `audit.py:51-59` | `max_tokens` 900-1600 with thinking may truncate | O | Check `finish_reason == length`; retry with a larger cap | U |
| RA20 | `audit.py:1889,1907` | `--resume` re-verifies settled items and overwrites `verdicts.jsonl` | O | Limit to new ids | U |

### 5.6 writing-plans (slice E)

| ID | File | Defect | Sev | Fix | Test |
| --- | --- | --- | --- | --- | --- |
| WP1 | `plan_tool.py:617` | Heading regex scans inside code fences, so a column-0 `# comment` fails lint | M | Skip fenced blocks | U |
| WP2 | `plan_tool.py:566` | `files_block` drops paths without `/` or `.` (`Makefile`, `Dockerfile`, `Gemfile`) | M | Accept bare known filenames | U |
| WP3 | `plan_tool.py:679-693` | `git add a b && git commit -m x` flags `&&`, `git`, `commit` and the message | M | Split on `&&`, `;`, `\|\|` before `shlex` | U |
| WP4 | `plan_tool.py:1145,1304` | Fallback is `general-purpose`; review is `general-purpose \| model sonnet`; OpenCode needs `general` | M | `dispatch_line()` | U |
| WP5 | `SKILL.md:27-32` | `ls -d … \| head -1` sorts alphabetically; misses `.agents/skills`; a miss runs `python3 "" brief` | m | Shared bootstrap snippet | D |
| WP6 | `plan_tool.py:1149` | Prints `subagent_type=` on v2 | G | `dispatch_line()` | U |
| WP7 | `plan_tool.py:953` | MODEL column says haiku/sonnet; subagent has no model param | G | Ship `plan-task-writer-deep` (glm-5.3, max) and `plan-reviewer`; one agent per row | U render |
| WP8 | `opencode/agents/plan-task-writer.md:8` | `steps: 16` too few for multi-task groups | G | Raise `steps` to 24 and cap each writer group at 4 tasks | U |
| WP9 | `plan_tool.py:1654,1756` | Tells v2 to set `OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS`; `detect() or 1` renders v1 frontmatter when opencode is absent | G | Drop the hint on v2; use `major()` | U |
| WP11 | `plan_tool.py:1467` | `pick_patterns` reads every candidate fully | O | Skip the read when score ≤ 1.5 | U |
| WP12 | `plan_tool.py:224` | Agent cap 20 on serial v1 | O | Group count = ceil(tasks / 4), capped at the lane width (default 8) on OpenCode | U |
| WP13 | `plan_tool.py:1548` | Inlines AGENTS.md/CLAUDE.md already in context on OpenCode | O | Skip on OpenCode | U |
| WP14 | `plan_tool.py:1017` | `--resume` trusts `.ok` without checking it is newer than the body | O | Compare mtimes | U |

(WP10 — dev-team adoption needs a ```json `slices` block — is out of scope; see §1.)

### 5.7 brainstorming (slice F)

| ID | File | Defect | Sev | Fix | Test |
| --- | --- | --- | --- | --- | --- |
| BR1 | `scripts/context.sh:16` | Detects only `$OPENCODE`/`$OPENCODE_BIN`, so v2 prints `harness: unknown` | M | `OPENCODE_TERMINAL`, `.oc-major`, install location (POSIX sh mirror of `harness()`) | U `test_brainstorm_oc` |
| BR2 | `SKILL.md:300` vs `307-337` | Contradictory lane rules | M | One rule: v2 → background `subagent` (explorer/researcher); v1 → `oc_harness run`; `task` only as fallback | D |
| BR3 | `scripts/start-server.sh:117,151,180` | Relative `--project-dir` never made absolute, so start fails | M | Absolutize before `cd` | shell check |
| BR4 | `SKILL.md:335-337` | Tool map names `task`/`todowrite`, missing on v2 | m | Per-version map | D |
| BR5 | `scripts/server.cjs` | No SIGTERM/SIGHUP handler; stale `server-info` reads as alive | m | Handler writes `server-stopped` | `node --check` + U |
| BR6 | `SKILL.md:157-159` | R9 split by a stray list item | m | Join | D |
| BR7 | `scripts/helper.js:163` | `brainstorm.choice()` sends no `choice` key, so the event is dropped | m | Send it | U |
| BR8 | `SKILL.md:320` | Foreground `oc_harness run` hits v2's 120 s shell timeout; web lanes killed and orphaned | G | Pass `timeout`/`background: true`; SH9 handler | D + U |
| BR9 | researcher agent (v2) | `websearch` needs a provider; headless lanes time out on the form | G | Snippet provider note or `web-search-prime` MCP; render the websearch permission | U render |
| BR10 | `SKILL.md:21-25` | Raw `!` line re-run; `${CLAUDE_SKILL_DIR}` empty | G | Skip when the context block is present, else `sh <Base directory>/scripts/context.sh` | D |
| BR11 | `scripts/context.sh:38` | Prints Claude subagent caps | G | Print `OC_MAX_LANES`/`--width` (default 8) and `oc_major` | U |
| BR12 | `architectural.md:102-107,119,142` | Pre-draft lane needs a writer but explorer/researcher are `edit: deny`; no TaskStop on OpenCode; hand-off omits the spec path | G | Main session writes the pre-draft on OpenCode; drop TaskStop there; pass the spec path | D |
| BR13 | `visual-companion.md:73-80` | No OpenCode note | G | v2 `background: true` plus `--foreground` | D |
| BR14 | `SKILL.md:333` | Lanes read raw `.jsonl` | O | Use `oc_harness result` | D |
| BR16 | lanes.json location | Scattered scratch files | O | Put it under `.superpowers/drafts/` | D |

(BR15, `oc_major` in context.sh, is folded into BR11.)

### 5.8 doc-generator (slice G)

| ID | File | Defect | Sev | Fix | Test |
| --- | --- | --- | --- | --- | --- |
| DOC1 | `opencode/commands/docs.md:4` | v2 skill tool needs the skill ID, not an absolute path | G | Use the ID | U render |
| DOC2 | `SKILL.md:63,162,219` | `general-purpose` and `Explore` are "Unknown agent" on v2 | M | `doc-writer`/`doc-reviewer`/`general` | U `test_all_skills` |
| DOC3 | `SKILL.md:168` | Tells the writer to use `sed`, but doc-writer has bash denied | m | Use the edit tool | D |
| DOC4 | `SKILL.md:310-312,395` | Stale sync path; says writers use GLM-5.3 but the agent uses flash | m | Fix both | D |
| DOC5 | `opencode/commands/docs.md` | `/docs` spends Turn 1 on recon | O | `` !`cmd` `` injection, only if the contract test proves v2 expands it | K |

## 6. Data flow

1. The skill runs its script.
2. The script calls `oc_harness.harness()` and `major()`.
3. It prints `NEXT:` and dispatch lines in the detected harness's syntax.
4. On OpenCode:
   - Wide fan-out goes through `oc_harness run lanes.json`: one `opencode run` per lane, brief on stdin,
     effort on v2 via `#effort` and on v1 via agent frontmatter.
   - Or v2 background `subagent` for model-side lanes.
5. Each lane's events stream to `lanes/<id>.jsonl`. Throttles and errors are read from error events
   only.
6. `result` prints the lanes' final text.
7. dev-team adds the guard plugin, which runs `guard.py oc` on write/shell/patch/execute tools, then the
   Stop gate and the integrate re-check.

## 7. Error handling

- The guard stays fail-open, per the repo convention (the integrate re-check is the real enforcement).
  Every fail-open is logged once per lane to stderr and to the lane log.
- Lane errors surface as one line: `LANE <id>: <status> <error.type> <message>`. `provider.rate-limit`
  (v2) and `APIError 429` (v1) feed the governor. `aborted` and `provider.no-route` (a missing variant)
  are reported with the fix to apply.
- A missed bootstrap prints what it searched and exits non-zero, never with an empty path. `!` preload
  scripts still always exit 0.
- No orphans: signal handlers plus process-group kills in `oc_harness` and `debug_tool`.

## 8. Testing

- **Baseline:**
  - `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests` runs 276
    tests with 11 red. SH2 and SH1 repair them, which makes the suite green.
  - `dev-team-glm/scripts/selftest.sh` passes 324 with 5 known macOS failures. It must stay at ≥ 324
    passed and ≤ 5 failed; new checks are added for DG4, DG5, DE1, DE4 and DE6.
- **Per fix:** a RED test first via the dev-team TDD flow (U/S rows above). Doc-only rows (D) are
  checked by `test_all_skills` hygiene where it applies, and otherwise by review.
- **New real-binary contract tests** in `_shared/tests/test_oc_contract.py`:
  - They use a stdlib fake OpenAI-compatible provider (SSE + JSON, request log) and a sandboxed
    `HOME`/`XDG_*`.
  - They set `enabled_providers: ["fake"]` and block the network with macOS `sandbox-exec` (localhost
    only), so nothing reaches a hosted model.
  - v2 runs with `--standalone`. The module is opt-in: it runs only with `OC_CONTRACT=1`, because the
    429 case alone takes about 90 s of built-in retries. It is skipped when the binary is absent, and
    also when no network sandbox is available (no `sandbox-exec`), unless
    `OC_CONTRACT_NO_SANDBOX=1` is set. v1 runs via the `OC_V1_BIN` env var. Wave 2 runs it against
    v2.0.18 and v1.18.33.
  - The SH10 unhide change is kept only if the contract test shows a `subagent` dispatch of the
    rendered agent works; otherwise `hidden` stays.
  - Coverage:
    - the tool names seen by the model and by the plugin hook;
    - `reasoning_effort` reaching the request (v2 `#effort`, v1 frontmatter);
    - a plugin deny blocking the tool;
    - the JSON event schema (`step_start`/`tool_use`/`step_finish`/`text`/`error`);
    - 429 → a `provider.rate-limit`/`APIError` event and the governor halving;
    - the brief via stdin arriving verbatim;
    - a missing variant → `provider.no-route` reported.
- **Final check:**
  - `sh install-opencode.sh --home <sandbox>`, then `opencode serve` plus `api --server` queries.
  - These must discover 6 skills (names without `-glm`), 13+ agents (plus the new writing-plans
    agents), 6 commands, and the `devteam-guard` plugin active.
  - They must also show no load errors and no clash warnings beyond the expected ones.
- **Syntax:** `py_compile` on every script; `bash -n`/`sh -n` (`bisect-parallel.sh` is bash-only);
  `node --check` on `server.cjs`, `helper.js` and both plugins.

## 9. Evidence

- v2.0.18 exposes these tools to the model: `edit, glob, grep, question, read, shell, skill, subagent,
  webfetch, websearch, write, execute`. There is no `bash`, `apply_patch`, `task` or `todowrite`. Shell
  input is `{command, workdir, timeout, background}`; write is `{path, content}`. — local fake-provider
  probe (2026-09-28)
- v1.18.33 tools are `bash, edit, glob, grep, read, skill, task, todowrite, webfetch, write`. The hook
  gets `input.tool` plus `output.args` (`command`; `filePath` and `content`). Throwing blocks the tool.
  — local probe (2026-09-28)
- v2 `--model p/m#high` sends `"reasoning_effort":"high"`. `#max` fails with "Variant unavailable"
  unless the config defines `variants.max`. `run --agent` ignores the agent's model and variant;
  `subagent` dispatch honours `variant`. — local probe (2026-09-28). This contradicts "The V2 session
  runner preserves these values but does not yet send them with model requests" —
  [opencode v2 agents](https://opencode.ai/v2/docs/agents/) (fetched 2026-09-28).
- v1: a `#high` suffix exits 1 with UnknownError, and `--agent` honours frontmatter `reasoningEffort`.
  — local probe (2026-09-28)
- v2 plugin `execute.before` events carry `{tool, sessionID, agent, messageID, id, input}`. Throwing
  blocks the tool and the run still exits 0. — local probe (2026-09-28)
- On 429, v2 retries 12 times over about 86 s, then emits `provider.rate-limit` (status 429) and drops
  the body, including code 1302. v1 retries 7 times over about 77 s, then emits `APIError statusCode
  429` with the `responseBody`. — local probe (2026-09-28)
- v2 wraps an argv message containing whitespace in literal quotes. stdin arrives verbatim, and an open
  stdin pipe hangs the run. — local probe (2026-09-28)
- v2 renames permissions: "`bash` is now `shell`, `task` is now `subagent`, and `write` and `patch` are
  now `edit`" — [opencode v2 migrate](https://opencode.ai/v2/docs/migrate-v1/) (fetched 2026-09-28).
- v2 always scans `~/.claude/skills`, and `OPENCODE_DISABLE_CLAUDE_CODE_SKILLS` is absent. On a name
  clash the config-dir copy wins. Skill frontmatter honours only name, description and metadata. —
  sandbox `opencode serve` probe (2026-09-28)
- Version gap: the latest stable release is v1.18.33 (2026-09-28). v2 is a beta line (local 2.0.18). —
  GitHub releases via web lane (2026-09-28)
- Unverified: v2 shell tool default timeout is 120000 ms; v2.0.18 sets only `OPENCODE_TERMINAL=1` in
  shells. — both from reading the binary during the audit lanes; the contract tests confirm them.

## 10. Assumptions

- Support both v1 stable 1.18.x and v2 beta 2.0.x.
- No live Z.ai calls, because the GLM plan is not assumed active. Verification uses the fake provider;
  a live GLM smoke test is left to the user.
- Edit only inside `glm-skills/`: never the Claude originals, never the real `~/.config/opencode`. The
  installer only warns about name clashes and stale `*-glm` installs. At the end, the final report
  prints the install command for the user to run; this work does not run it.
- Skill names stay without the `-glm` suffix (`test_all_skills` enforces this).
- The spec and plan live under `glm-skills/docs/superpowers/{specs,plans}/`.
- The guard stays fail-open.
- Behaviour changes are recorded in each skill's CHANGELOG/README where one exists, and harness facts in
  `glm-skills/CLAUDE.md`.
