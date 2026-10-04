# Hybrid skills: principles and porting guide

This folder holds **hybrid** forks of Claude-only skills. A hybrid skill runs the same workflow as its
original, but hands the low-judgment units of work to the local `opencode` CLI, which runs cheaper
models, while Claude keeps every judgment step. Use this file when you change a hybrid skill or turn
another skill into one.

## Role in the skillz monorepo

`hybrid-skills/` holds the **variants that combine Claude + opencode to save cost**, derived from the
original skills in `../claude-skills/` (the source of truth). Sibling variants: `../glm-skills/` (ZCode /
GLM) and `../opencode-skills/` (opencode-only). Port behaviour changes from the original.


| Hybrid fork | Original (`../claude-skills/`) | Offloaded to opencode | Oracle (machine check) |
|---|---|---|---|
| `hybrid-brainstorming-v1.0` | `claude-brainstorming-6.3` | exploration lanes: locate, explore, fact and research; plus draft in mode opencode | `hb_ground.py` grounding check |
| `hybrid-writing-plans-v1.0` | `claude-writing-plans-6.2` | plan task bodies, tiers light and std (Claude reviews only risky ones); plus deep in mode opencode | the plan linter (`plan_tool.lint_file`) |
| `hybrid-requirements-code-audit-v1.0` | `claude-requirements-code-audit` | investigator and parser batches; plus verifiers in mode opencode | `ha_oracle.py` evidence oracle + id coverage |
| `hybrid-team-v1.0` | `claude-dev-team-v3.2` | GREEN/WORK of slices that have an oracle, any size; plus `risk: high` in mode opencode | `guard.py stop` gate + merge-time re-check |

## 1. Invariants (never break these)

1. **Judgment stays on Claude.** Planning, classification, synthesis, contracts, review, adjudication,
   verification, RED tests and final reports are Claude's in every mode. opencode only *executes*.
   "Offloading changes who executes a unit, never who decides it is right."
   - **80/20 target.** In mode hybrid, Claude keeps only the ~20% of units with the most judgment,
     value and impact: design decisions and synthesis, contracts, deep/`risk: high` work, RED tests,
     risk-based review, adversarial verification, adjudication and final reports. Every other unit that
     has an oracle goes to opencode by default (~80%), whatever its size or volume. A routing default
     that keeps an oracle-backed execution unit on Claude needs a stated reason (no oracle, the unit
     decides the design, or it is the independent check on opencode output).
2. **No oracle, no offload.** Only a unit whose output a deterministic check can accept or reject may go
   to opencode. If you cannot name the check, the unit stays on Claude.
3. **Every opencode output passes the oracle before it counts.**
   - When the oracle's complaint is actionable (lint errors, a blocked gate, missing markers), the
     engine may send up to `max_repairs` (usually 2) repair turns in the *same* opencode session
     (`--session <id>`). After that it counts as a failure.
   - Output must also carry a machine-readable envelope (marker blocks, a sentinel line). A missing or
     empty envelope is a failure (`OC-WARN kind=empty|format`), never a silent pass.
4. **Fail loud, at once.**
   - Every failure prints exactly one `OC-ERROR` or `OC-WARN` line.
   - The line is appended to the run's `oc-errors.jsonl`.
   - The process that failed exits non-zero, so a background task notification wakes Claude.
   - SKILL.md's relay rule makes Claude start its next message with that line.
   - Nothing is "informational" and nothing is swallowed by a fallback.
5. **The user picks the mode at Step 0** (hybrid / Claude only / opencode only). The mode is frozen in run
   state; resumed runs never ask again.
6. **Scripts own the mechanics.** SKILL.md tells the model to run a script and trust its output (`NEXT:`,
   `FALLBACK`, `HELD` and dispatch lines). The model never hand-writes opencode briefs or outputs, never
   runs `opencode` itself, never retries an opencode unit in place and never dispatches a held unit on its
   own.
7. **Each skill folder is self-contained.**
   - Shared logic is *vendored*: `scripts/hybrid_shared.py` is byte-identical in every hybrid skill, and
     `tests/test_hybrid_shared_sync.py` enforces that.
   - Never import across skill folders; each skill is installed separately into `~/.claude/skills/`.
8. **opencode workers are sandboxed.**
   - Each skill injects its own opencode agent through `OPENCODE_CONFIG_CONTENT` (`*_config.py`), and
     sets `OPENCODE_DISABLE_PROJECT_CONFIG=1` so the audited or edited repo cannot inject its own
     `opencode.json`, plugins or MCP servers.
   - Research and writer agents are read-only.
   - The team programmer agent gets `"*": "deny"` plus an exact allowlist: the pinned
     test/lint/typecheck commands, the commit helpers, read-only git and a few read-only inspection
     commands. Default-allow with a deny list is never enough: opencode allows anything unmatched.
   - Every agent denies reads of secrets (`*.env`, keys, `.ssh`), even when reads are otherwise open.
     Verified on v2.0.20: `read` of `settings.env` → `Permission denied: read`. Limit: opencode's `grep`
     permission matches the search *pattern*, not the file, so `grep` can still print lines of a secret file
     that is not gitignored (the grep tool is ripgrep and skips gitignored files, so a gitignored `.env` stayed
     hidden in the same probe). Keep secrets gitignored; only an OS sandbox closes this fully.
   - Residual risk: test commands execute model-written code with the user's rights. Permissions cannot
     stop that; only an OS sandbox can.
9. **Tests are hermetic.** A fake `opencode` binary replays scripted event streams. The real user
   environment has `HYBRID_OPENCODE_STD` set, so every test sets or removes the `HYBRID_OPENCODE_*` vars
   explicitly and points every path (routing, doctor cache, telemetry, `HOME`, `XDG_DATA_HOME`) at temp
   dirs.

10. **Every shared name carries the `hybrid` prefix**, so a hybrid skill installs beside its Claude-only original
    without a collision: skill names (`hybrid-<original>`), Claude agents (`hybrid-team-*`, `hybrid-plan-task-writer`),
    opencode agents (`hybrid-team-programmer`, `hybrid-plan-writer`, `hybrid-brainstorm-lane`, `hybrid-audit-*`), env
    vars (`HYBRID_TEAM_*`, `HYBRID_WRITING_PLANS_*`, `HYBRID_BRAINSTORMING_*`, `HYBRID_AUDIT_*`), project state dirs
    (`.claude/hybrid-team`, `.hybrid-work`, `.hybrid-audit`, `.hybrid-superpowers`), and git worktree/branch names
    (`hybrid-oc-<id>`, `hybrid-checkpoint-<n>`, `hybrid-attempt/*`). Script file names inside a skill folder are
    namespaced by the folder and stay as they are. `docs/superpowers/specs|plans/` stays shared on purpose: it is the
    hand-off format between pipeline stages. `install.sh` (next to this file) installs skills and agents.

## 2. Modes and failure policy

| Mode (preset) | Routing | On an opencode failure |
|---|---|---|
| `claude` | opencode is never spawned; the doctor is not required | n/a |
| `hybrid` (default) | the skill's routing table sends low-judgment units to opencode | **connection failure** (`spawn`, `stall`, `throttle`, `crash`): retry up to 3 times, waiting 10/30/60 s. If it still fails, or at once when an opencode run fails with `auth`/`quota`/`model`/`config` (a config problem caught before spawning stays a per-unit fallback), **switch the whole rest of the run to Claude Sonnet 5.5** (Agent `model: sonnet`) and print one `kind=switch` line. **Other failures** (`timeout`, `context`, gate kinds): relay the line, then fall back to Claude **once per unit** |
| `opencode` | every unit that has an opencode runner goes to opencode (`max_roles`) | same retries, then the unit is **HELD**, with no fallback and no switch. Ask once per root cause (AskUserQuestion): retry on opencode / run this unit on Claude / switch to hybrid / abort |

**Run switch (hybrid).**
- `hybrid_shared.switch_to_claude()` writes `oc-switched.json` in the run's state dir; the first caller prints `switch_line()`.
- From then on, every unit the router would send to opencode goes to Claude with `FALLBACK_MODEL` (`sonnet`). Nothing new is spawned, and no per-unit OC line is printed.
- Units already running on opencode finish and are harvested normally.
- A new run starts unswitched: `init` (brainstorming `bslane.py init`, audit, team) and `contracts` (writing-plans) clear the
  switch, the breakers and the cooldowns, and each new skill invocation (a new agent or flow) begins with that.
- Switch and breaker records carry `CLAUDE_CODE_SESSION_ID`; a record written in another Claude Code session counts as
  stale (`hybrid_shared._stale`), is ignored and is replaced on the next trip, so a new session starts on opencode again.
  Subagents share their parent's session id, so they keep the run's switch until the flow is re-initialised.
- Each retry prints one `OC-WARN ... kind=<kind> :: retry n/3 in Ns`.
- Retries always start a fresh opencode run, never a `--session` continuation.
- Tests set `HYBRID_OC_RETRY_DELAY_S=0`.

- `max` is a legacy alias for `opencode`: accepted, and it prints one `OC-WARN kind=config`.
- An unknown mode is an `OC-ERROR kind=config` with a non-zero exit, never a silent fallback to claude.
- The preset is frozen for the run, so switching mode later must never strand a unit. Two examples: audit
  refuses `status --mode claude` while opencode units are held or unharvested, and team maps "run on
  Claude" to `retry <id> --claude`.

**Circuit breaker.**
- `auth`, `quota`, `model` and `config` are non-retryable (`NON_RETRYABLE`). They trip a breaker keyed
  by tier and `model#variant` in the run's state dir.
- While it is open, the tier counts as unavailable: hybrid routes to Claude, opencode mode holds.
- At phase end one `OC-ERROR ... kind=breaker :: N units skipped` summary is printed, so there is one
  alert per root cause, not one per unit.
- The breaker is per run: it is reset at init.
- `throttle` does not trip the breaker. It halves the slot cap or waits `throttle_cooldown_s` instead.

## 3. OC lines and failure kinds

```
OC-ERROR <skill> <unit> tier=<tier> model=<provider/model#variant> kind=<kind> :: <detail> [log=<path>]
OC-WARN  <skill> <unit> tier=<tier> model=<spec> kind=<kind> :: <detail> [log=<path>]
```

Build lines only with `hybrid_shared.oc_line()`. It collapses the detail to one line, capped at 200
chars; the full stderr stays at `log=`.

- **OC-ERROR (the run failed)**, from `hybrid_shared.classify()`:
  - `auth`, `quota`, `model`, `config`, `throttle` and `context` come from the error events and the
    stderr tail.
  - `timeout`, `stall` and `spawn` come from the runner's watchdog.
  - `crash` is anything else.
  - `breaker` is the summary line (mode opencode).
  - `switch` is the one line that says a hybrid run moved to Claude sonnet.
- **OC-WARN (opencode answered, but a gate rejected the answer, or it recovered)**:
  - `empty` and `format` come from the output envelope.
  - The oracle-specific kinds are `grounding`, `lint`, `oracle` and `gate`.
  - `recovered` means the process exited 1 but the run finished (a completed final `text` part, or a
    `step_finish reason=stop` in v1) and the gates pass. The result is accepted and the warning is
    still reported.

Make an error reach Claude immediately by combining the parts below:
- The worker runs as a background process that exits non-zero on failure.
- Every resume command (`next`, `status`, `wait`) first prints unreported lines via
  `hybrid_shared.take_unreported()`.
- In writing-plans, `wait` also exits 2 on a new OC-ERROR and exits 3 when only held tasks remain.

## 4. Configuration layers

1. **Models, shared by all hybrid skills:** environment variables, usually set in the `"env"` block of
   `~/.claude/settings.json`; restart Claude Code after editing it.
   - `HYBRID_OPENCODE_STD` is required, as `provider/model[#variant]`. The `#variant` part is the thinking
     level; opencode has no `--variant` flag.
   - `HYBRID_OPENCODE_LITE` is optional and defaults to STD.
   - `HYBRID_OPENCODE_MAX_PARALLEL` is optional: an integer from 1 to 64, the slot cap of every tier (opencode
     runs at once per tier). Without it the shipped `max_parallel` (4) applies. A tier whose per-skill
     `routing.json` sets `max_parallel` keeps that value. Applied by `hybrid_shared.resolve_tiers()`.
   - Loaded by `hybrid_shared.load_shared()`. A missing or invalid STD, or an invalid MAX_PARALLEL, makes the
     hybrid and opencode modes unavailable, and the preload line says so.
2. **Per-skill overrides:** `<skill dir>/routing.json`, next to `routing.default.json` (env override
   `HB_ROUTING` / `HP_ROUTING` / `HA_ROUTING` / `HT_ROUTING`).
   - The file is deep-merged over the defaults.
   - A tier that sets `model` here uses this file's `model` and `variant`; variants are never mixed with
     the env value. Other tiers use the env vars.
   - `hybrid_shared.resolve_tiers()` records each tier's source as `skill`, `shared` or `none`.
   - The file is lost if the skill folder is deleted and re-copied; deploy with `rsync` without
     `--delete`.
3. **Shipped defaults:** `routing.default.json`. It **never contains `model` or `variant`**. Common keys:
   - `preset` sets the default mode.
   - `tiers.{std,lite}` holds `max_parallel` (slot cap, 4; `$HYBRID_OPENCODE_MAX_PARALLEL` overrides it),
     `stall_s` (no-output watchdog) and `timeout_s`
     (wall-clock limit; team keys it by slice size). An optional `disabled` exists.
   - `roles` or `rows` map a unit type to `std`, `lite` or `claude`. `max_roles` is the same table for
     mode opencode.
   - Tuning keys: `max_repairs`, `throttle_cooldown_s`, and a batch size (`oc_batch_max`,
     `oc_group_max`).
4. **Doctor cache:**
   - Entries are keyed by `model#variant` (`cache_key`) with a 600 s TTL (`cache_fresh`), so a model edit
     invalidates them at once.
   - The first hybrid or opencode run per key does a one-token ping, which catches auth, quota and model
     errors before any work is dispatched.
   - A failure in one tier never disables the other.
   - A stale cache entry must never *downgrade* a tier in the middle of a run.

## 5. Anatomy of a hybrid skill

Each skill uses its own file prefix (`hb_`, `hp_`, `ha_`; team uses `oc_` and `router.py`). Copy the
nearest sibling's version of each part instead of writing it fresh.

| Part | Job | Examples |
|---|---|---|
| `scripts/hybrid_shared.py` | env config, modes, `classify`, `oc_line`, error log, breaker, `config`/`check`/`mode` CLI | vendored; edit one copy, `cp` it to all four, and run the sync test |
| router | load routing (defaults, then skill file, then env models), map unit + preset to `claude` / `oc:<tier>` / `held` | `hb_router.py`, `hp_router.py`, `ha_router.py`, `router.py` |
| partition (optional) | group units into opencode batches vs Claude batches, capped by slots and batch size | `hp_partition.py`, `ha_partition.py` |
| agent config | the injected read-only or allowlisted opencode agent (`OPENCODE_CONFIG_CONTENT`) | `hb_config.py`, `hp_config.py`, `ha_config.py`, `oc_config.py` |
| briefs / prompts | self-contained prompt files (the worker has no other context), the output marker format, repair messages | `hb_prompts.py`, `hp_briefs.py`, `ha_briefs.py`, `oc_brief.py` |
| runner | spawn `opencode run`, parse the JSON event stream, stall/timeout watchdog, kill the process group | `oc_run.py` (brainstorming, writing-plans, audit), `oc_lane.py` (team) |
| engine | runs units in parallel, applies the oracle and repair turns, prints OC/FALLBACK/HELD lines, trips the breaker | `bslane.py`, `hp_write.py` + `hp_wait.py`, `ha_run.py` + `ha_dispatch.py`, `devteam.py lane` |
| oracle | the deterministic acceptance check | `hb_ground.py`, the plan linter, `ha_oracle.py`, `guard.py stop` + `integrate` |
| doctor | `opencode --version`, `opencode models`, ping, cache, status line | `hb_doctor.py`, `hp_doctor.py`, `ha_doctor.py`, `oc_doctor.py` |
| telemetry (optional) | per-backend usage and cost stats | `hp_telemetry.py`, `ha_telemetry.py`, `bslane.py` |
| `routing.default.json` | defaults, no models | see section 4 |
| `tests/fake_opencode.py` | answers `--version`, `models`, `run`; driven by `<P>_FAKE_SCRIPT` / `<P>_FAKE_LOG`; scripted scenarios (auth, model_not_found, throttle, recovered, empty, …) | one per skill |
| `tests/test_hybrid_shared*.py` | shared-module tests + byte-identity check | vendored like the module |

Choose the sibling that matches the shape of the work:
- independent research lanes → brainstorming (`bslane.py`)
- fan-out writers checked by a linter → writing-plans (`hp_write.py`)
- batch jobs checked for id coverage and evidence → audit (`ha_run.py`)
- coding slices in git worktrees with commit gates → team (`oc_lane.py`)

## 6. opencode CLI facts (v2.0.x)

- **Command:** `opencode run --standalone --agent <name> --model <provider/model#variant> --format json
  --auto [--session <id>] [-f <brief>] <message>`.
  - The repo root is the cwd (there is no `--dir`).
  - Attach large briefs with `-f` rather than argv.
- **Success is not the exit code.**
  - v2 can exit 1 after a recovered step error, and exit 0 with no answer.
  - v2.0.20 success streams contain only `step_start` and `text` events, with no `step_finish`. Success
    means no error events, a completed final `text` part (v1: `step_finish reason: "stop"`) and output
    that passes the gate.
  - Errors arrive as `type: "error"` events.
  - Classify with `hybrid_shared.classify(rc, errors, stderr_tail, killed, finished)`, never by exit code
    alone.
- **Events to use:**
  - `text` gives the answer.
  - `tool_use` gives tool inputs and outputs. A large tool output is saved to a file under
    `$XDG_DATA_HOME/opencode/tool-output/`; read it back from there.
  - `step_finish` gives tokens and cost when present; on v2.0.20 usage is only a lower bound.
  - The first `sessionID` seen is the session to continue for repairs.
- **Classification traps:**
  - HTTP codes 401/402/403 must not match stack-trace `line:col` numbers; see the lookarounds in
    `_KIND_PATTERNS`.
  - Throttle text can appear in stdout, stderr or JSON fields.
- **Watchdog:** spawn with `start_new_session=True`. A stall is no growth in the stdout file for
  `stall_s`. On timeout or stall, SIGTERM the process group, wait a grace period, then SIGKILL.
- **Read opencode output through a file, never a pipe (verified on v2.0.20).** The CLI exits before it
  flushes a pipe: `opencode models` over a pipe returned 0–3072 of 3467 bytes (empty, or cut mid-line), so a
  doctor saw "listed nothing" or "model not found" and routed everything to Claude. `hybrid_shared.run_captured`
  (temp-file stdout, stdin closed) and `run_models` (re-runs an empty answer) are the only way to call it; the
  runners already stream `run` events to a file. Never pass `--standalone` to `models`: it always lists nothing.
- **Doctor:** `opencode models` returning rc 0 with an empty list even after the retries means the providers
  are not authenticated. Report it as `OC-ERROR kind=config`.
- **Free tier trap (verified on v2.0.20):** the free `opencode/*-free` models answer 403
  `provider.auth` "free tier can only be used from within OpenCode" whenever the agent's `bash`
  permission is `"deny"` or `{"*":"deny"}`. A read-only agent uses `{"*":"deny","ls":"allow"}`.
- **The free tier trap checks `read` too, independently of `bash` (verified live on v2.0.21).** A role
  with `read` fully denied (the bare string `"deny"`) still gets the same 403 even with the `bash` fix
  applied — confirmed by isolating each tool permission one at a time against a live free-tier model:
  only un-denying `read` flipped it, not `grep`, `glob` or `edit` alone. Found in
  `hybrid-requirements-code-audit-v1.0/scripts/ha_config.py`'s `parser` role, which must never read
  repo files by design. Fix: give `read` the same structural-no-op shape as `READ_ONLY_BASH`'s `"ls"`
  exception, but with an allow pattern that matches no real path (`ha_config.NO_REAL_READ`:
  `{"*":"deny","*.__hybrid-parser-no-match__":"allow"}`) — passes the gate, grants zero real
  capability. Check every read-only role's `read` block for a bare `"deny"` before shipping it against
  a free-tier model; `{"*":"allow", ...secret/doc deny patterns}` (open with exceptions) is unaffected
  and does not need this.
- **Error events (v2.0.20):** `{"type":"error","error":{"type":"provider.auth|provider.quota|
  provider.no-route|provider.timeout|unknown","message":...}}`. Map them by `type` first, message text
  second (`classify`).

## 7. SKILL.md requirements

- **Frontmatter:**
  - `name: hybrid-<original>`.
  - `description` is *opt-in*: trigger only on "hybrid", "opencode", "save tokens/cost/usage limits", or
    the literal `/hybrid-<name>`. Say what goes to opencode and what stays on Claude. Keep it at most
    1024 chars.
  - `allowed-tools` pins exact script paths under `${CLAUDE_SKILL_DIR}`, so renaming a script silently
    drops its pre-approval.
- **Preload (`!` block):**
  - Must stay read-only and bounded, and always exit 0.
  - Adds an `opencode:` status line, a config line with `std=<spec> (skill|shared) lite=<spec> (...)`
    or `no config (...)`, and (writing-plans) a `mode:` line.
  - Only `${CLAUDE_SKILL_DIR}` substitution works inside the `!` line itself.
- **Step 0 (the first action):**
  - If the args contain `mode=hybrid|claude|opencode`, use it without asking. Hand-offs between hybrid
    skills pass it along.
  - Otherwise the first tool call is AskUserQuestion "Run this skill in which mode?" with these options:
    - **Hybrid (Recommended)**: judgment on Claude, <offloaded units> on opencode, every opencode error
      reported at once, automatic Claude fallback.
    - **Claude only**: opencode is never called; behaves exactly like the original skill.
    - **opencode only**: every unit the routing table can send to opencode goes there, with no silent
      Claude fallback.
  - Put the `std`/`lite` specs from the preload into the option descriptions, or "no config".
  - Persist the choice through the script (`--preset`, `--route`), never in prose.
- **Relay rule, verbatim in spirit:** "Any `OC-ERROR` or `OC-WARN` line in tool output means your next
  message to the user starts with that line, verbatim, before any other work. Deduplicate identical
  `kind` + `tier` pairs: relay the first line and say how many more matched. Never treat these lines as
  informational and never skip one."
- **A routing section:**
  - a table of unit → backend per mode;
  - the list of what stays on Claude in every mode;
  - the failure handling per mode (section 2);
  - the answers to a HELD question, mapped to exact commands (`--retry`, `--to-claude`, `retry <id>
    --claude`, `--include-held`, …).
- **Never-rules:**
  - never hand-write or edit opencode briefs, outputs or fallback briefs;
  - never run `opencode` directly;
  - never retry an opencode unit in place;
  - never dispatch a held unit yourself;
  - never exceed the printed slot caps;
  - never call the hybrid engine in mode claude.

## 8. Porting checklist (Claude-only skill → hybrid)

1. **Copy** `../claude-skills/claude-<skill>` (the original folder keeps its version suffix, for example `claude-writing-plans-6.2`) to `hybrid-skills/hybrid-<skill>-v1.0`. Start from the *current*
   original. The four existing forks were re-synced with their originals on 2026-09-30. Diff against the
   original (`git merge-file`, using the original's content at the commit the fork was last synced from as base; find that commit with `git log -- hybrid-skills/<fork>`) before porting a fix either way, so
   a fork never lags silently again.
2. **Classify every unit** of the workflow as judgment (stays on Claude) or execution. For each execution
   unit, name its oracle. No oracle → Claude.
3. **Vendor** `scripts/hybrid_shared.py`, `tests/test_hybrid_shared.py` and
   `tests/test_hybrid_shared_sync.py` from a sibling, unchanged. If the shared module needs a change, make
   it once and copy it byte-identical to every hybrid skill.
4. **Add the parts from section 5** by copying the closest sibling. Wire the router to
   `load_shared()` and `resolve_tiers()`. Write `routing.default.json` without models.
5. **Wire the failure flow:**
   - `classify` and `oc_line` for every failure;
   - `should_retry` / `retry_delay` around every opencode run;
   - `switches_run` / `switch_to_claude` / `run_switched` for the hybrid run switch, with the router
     checking `run_switched` first;
   - `log_line` to `oc-errors.jsonl`, with `take_unreported` at the top of every resume command;
   - a non-zero exit from background workers;
   - FALLBACK (hybrid) and HELD (opencode) markers;
   - `breaker_trip` / `breaker_open` / `breaker_summary`, with the breaker reset at run init.
6. **Edit SKILL.md** per section 7. Keep the Claude-only path byte-for-byte the original behaviour.
7. **Tests:**
   - fake opencode scenarios for every kind in section 3;
   - hybrid fallback and opencode hold paths;
   - breaker trip and summary;
   - mode switch without stranding units;
   - the routing precedence;
   - a hermeticity run of the whole suite with `HYBRID_OPENCODE_STD=zz/leak#x` exported.
8. **Docs:**
   - README: install, modes, config and precedence, env vars, troubleshooting, differences from the
     original;
   - a CHANGELOG entry;
   - update the table at the top of this file.
9. **Verify:**
   - `cd <skill> && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t tests -q` in every
     hybrid skill; a vendored change affects all four;
   - `python3 -m compileall -q .`;
   - for team, also `bash scripts/selftest.sh`, where the baseline is `passed=255 failed=0` on macOS.
10. **Deploy** only with the user's confirmation, using `rsync -a --exclude __pycache__ <skill>/
    ~/.claude/skills/<skill>/`, never `--delete`, so a user's `routing.json` survives.

## 9. Lessons already paid for

- **Capacity overflow queues on opencode; it never spills to Claude.** A slot cap (`max_parallel` ×
  batch size) that sends the excess to Claude in mode hybrid quietly moves most of a large run to Claude
  (audit: 60 items → 60% on Claude). Extra batches wait for a free opencode slot, as in mode opencode;
  `oc_overflow: "claude"` in the skill's `routing.json` restores the old split. A batch still waiting for
  a slot is never a straggler and never gets a Claude hedge.
- **A switch or a retry must never strand work.**
  - Decide "unit finished" from coverage and harvested events, not from an output file existing, because
    a partial file can exist for a failed unit.
  - A retry recomputes tier health, but may only *upgrade* tiers.
- **Keep the breaker per run.** A breaker that survives into the next run silently disables opencode.
- **Validate user routing types.** A wrong-typed nested key (such as `"tiers": [1]` or `"std": "x"`)
  must become a `config_problems` entry that names the file and key, never a crash and never a silent
  skip.
- **Frozen RED tests** (team) cannot be fixed later. Before `commit-red`, run the new tests against the
  unchanged code and confirm that only the intended assertions fail.
- **Preload scripts** run before the model reads SKILL.md. A non-zero exit cancels the skill.
