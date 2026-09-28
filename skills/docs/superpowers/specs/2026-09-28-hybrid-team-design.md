# hybrid-team — Design Spec

Date: 2026-09-28 · Status: design approved by the user (2026-09-28); spec under review.
User decisions: new skill (approach A); tiers `std` = GLM 5.3 `#high`, `lite` = GLM 5.3
Flash `#low`; offloaded code slices split RED on Claude → GREEN on opencode.

## 1. Goal

A dev-team-style skill that keeps every judgment-heavy step on Claude and offloads
low-judgment execution to the `opencode` CLI, where the model and thinking level are
configurable per tier. Target: cut Claude token spend on implementation lanes without
lowering the merge bar that dev-team-v3.2 enforces today.

**Core principle.** Claude decides WHAT to build and WHETHER it is right. The cheap model
only EXECUTES a precise spec against a machine oracle: frozen tests, a `verify` command,
or an existing suite that must stay green. A slice with no oracle is never offloaded.

## 2. Non-goals

- No change to `dev-team-v3.2`. It stays the default dev skill.
- No new profiles. `strict`/`balanced`/`turbo`/`spike` keep their meaning; routing is a
  separate axis.
- No opencode for planning, review, verification, debugging investigators or research.
- No HTTP server/SDK integration (`opencode serve`). One CLI process per lane is enough
  for ≤ ~8 parallel lanes; revisit only if probes show per-process startup dominates.
- No automatic model benchmarking. Telemetry exposes numbers; the user tunes routing.

## 3. Approaches

| | Approach | Trade-offs | Verdict |
|---|---|---|---|
| **A** | Fork dev-team-v3.2 into `hybrid-team`, add a backend router + an opencode lane runner in the engine | + zero risk to dev-team; + preset `claude` reproduces dev-team exactly, so hybrid-team can later replace it; − duplicated engine (~3k lines) to keep in sync | **Chosen** |
| B | Add an opencode backend inside dev-team-v3.2 behind a flag | + no duplication; − edits a working skill; − not the new skill that was asked for | Rejected |
| C | Claude wrapper subagent (or MCP server) that shells out to opencode | + reuses Agent-tool plumbing (native worktree, SendMessage); − pays Claude tokens for the wrapper; − foreground Bash caps at 10 min; − extra hop and failure surface | Rejected |

## 4. Architecture

```
Claude Code session (Conductor, Opus)
 ├─ engine  hybrid-team-v1.0/scripts/devteam.py   (forked, + router, + `lane`)
 ├─ guard   hybrid-team-v1.0/scripts/guard.py     (forked; Stop gate reused for opencode lanes)
 ├─ Claude workers (Agent tool, background)
 │    ht-team-leader · ht-code-reviewer · ht-spot-reviewer · ht-investigator · ht-programmer
 └─ opencode workers (Bash run_in_background → `devteam.py lane <id>`)
      opencode run --standalone --agent ht-programmer --model <provider/model>#<variant> …
```

- **Skill**: folder `hybrid-team-v1.0`, frontmatter `name: hybrid-team`. Opt-in trigger:
  "hybrid", "opencode", "save tokens/cost", `/hybrid-team`. The description must not
  compete with dev-team's generic trigger.
- **Namespace**: Claude agents are prefixed `ht-` so both skills can be installed side by
  side. State dir is `.claude/hybrid-team/`. `guard.py` and `devteam.py` duplicate
  `STATE_DIRNAME` (and the test-path constants); keep them in sync by hand, as in dev-team.
- **Merge path unchanged.** `integrate` re-derives everything from git (claim file, RED
  commit by subject, footprint diff, frozen-test diff, refactor-no-test-touch), so it is
  worker-agnostic by construction. Opencode lanes produce the same branch, commits and
  `.done`/`.blocked` marker as a Claude programmer.

## 5. Components

### 5.1 Router (engine)

`route(slice, preset, routing) → "claude" | "oc:<tier>"`. Order:
1. Slice field `backend` (`claude` | `oc:<tier>`) wins.
2. Preset table (§7).
3. Tier missing, opencode unavailable, or tier disabled → `claude` + one-line NOTE.

For `kind: code` slices routed to opencode, the router splits the slice into RED (Claude
`ht-programmer`, sonnet) and GREEN (opencode). The RED commit is frozen before GREEN
starts; that frozen test file is the oracle.

### 5.2 `devteam.py lane <id>` (new subcommand)

One opencode lane end to end, always exits:
1. `git worktree add` under `.claude/worktrees/oc-<id>` at the base `claim` expects (for
   GREEN: the accepted RED commit). `finish` cleans these like native worktrees.
2. Run `claim <id>` inside it (claim already asserts it is not the integration checkout).
3. Build the brief (§5.5) and spawn
   `opencode run --standalone --agent ht-programmer --model <provider/model>#<variant> --format json --auto <brief>`
   with `cwd` = worktree, `PWD` = worktree, stdin = `/dev/null`, own process group.
4. Watchdog: no JSON event for `stall` seconds, or wall time > `timeout` → kill the group.
5. Feed `{cwd, last_assistant_message}` (last text part of the event stream) to the
   existing `guard.py stop` gate.
6. Gate blocks (exit 2) → continue the SAME opencode session (`-s <sessionID>`) with the
   gate's stderr as the message; max 2 continuations.
7. Write `.claude/hybrid-team/slices/<id>.done|.blocked` exactly as the Claude Stop hook
   does; `.blocked` carries a machine-readable `reason` (`gate`, `stall`, `timeout`,
   `throttle`, `crash`, `spawn`).
8. Append a lane record (tier, model, variant, duration, tokens, cost, outcome) to
   `.claude/hybrid-team/lanes.jsonl`.

Event stream contract (v2.0.18, probed): every event carries top-level `sessionID`; final
text = `.part.text` of the last `type: "text"` event; usage = sum over `step_finish`
events of `.part.tokens.{input,output,reasoning,cache.read,cache.write}` and `.part.cost`
(`step_finish` can be absent on tool-less runs → usage 0); failures emit
`{"type":"error","error":{"type":…,"message":…}}` with exit 1 and empty stderr.

### 5.3 Dispatch (engine → Conductor)

For an opencode slice, `next`/`dispatch` prints:

```
=== LANE <id> oc:<tier> — run in the BACKGROUND: python3 <skill>/scripts/devteam.py lane <id>
```

The Conductor runs it with Bash `run_in_background: true` — the same mechanism dev-team
checkpoints already use. Process exit = completion notification; the next `next`
harvests the marker. Opencode lanes have their own slot cap (`max_parallel` per tier,
default 6), independent of the Claude subagent cap.

### 5.4 opencode agent `ht-programmer`

- Prompt rewritten for weaker models: numbered imperative rules, one fixed command
  sequence per mode (GREEN / WORK / FAST), no exploration outside the footprint, report
  shape identical to dev-team's (`## Status:`, `## Gate:`).
- `permission`: `edit: allow`; `bash`: allowlist (engine commit helpers, the plan's
  test/lint/typecheck commands, read-only git); explicit `deny` for push, reset, rebase,
  manual `git commit`, package installers, network tools; `external_directory` deny.
  Rules must be `deny`, never `ask`: `--auto` approves anything not explicitly denied.
- Injected per lane through the `OPENCODE_CONFIG_CONTENT` env var (agent definition +
  prompt + permission). Nothing is written to `~/.config/opencode` or the repo. Reasons
  (probe, §11): project agent files are not discovered inside linked worktrees, and an
  unknown `--agent` silently falls back to the default agent.
- Defence against that silent fallback: the injected config also sets the same `deny`
  rules at top-level `permission`, so a fallback agent is still fenced; `doctor --ping`
  checks that the injected agent really resolves (its prompt makes it answer a sentinel
  token); a failed check routes everything to Claude.

### 5.5 Brief pre-chewing

Weaker models explore badly, so the engine does the exploration: the opencode brief
inlines the slice goal, criteria, contracts, footprint, the frozen RED test (GREEN), the
exact commands to run, and the contents of `context` files (cap ~40 KB, truncated with a
marker). The brief file is written under `.claude/hybrid-team/briefs/<id>.oc.md`.

### 5.6 Telemetry

`stats` adds: slices per backend/tier, escalation rate per tier, median lane time per
tier, opencode tokens and cost (summed from `step_finish` events; cost reads 0 on the
subscription coding plan, so tokens are the main number). Purpose: tune routing from real
numbers instead of guesses.

## 6. Data flow

```
plan.md ─► init ─► route every slice ─► next
                                        ├─ claude  → "Agent → ht-programmer …"  (as dev-team)
                                        └─ oc:tier → "LANE <id> … background"
Conductor runs Bash(bg) devteam.py lane <id>
  worktree → claim → opencode run (json) → watchdog → Stop gate ─┬─ ok      → .done
                                                                  ├─ block≤2 → resume session
                                                                  └─ fail    → .blocked{reason}
exit → notification → next → integrate (git-only checks) → MERGED
                           └─ .blocked → escalate to Claude ht-programmer (once)
```

## 7. Routing table (preset `hybrid`, default)

| Work | Backend |
|---|---|
| Conductor, planning (`ht-team-leader`), all reviews (cross-model), verification | Claude |
| Investigators / `brief-debug`, `research`, `perf` | Claude |
| `risk: high`, `size: large` | Claude |
| RED phase of every `code` slice | Claude (sonnet) |
| GREEN of `size: trivial`/`small` code slices | oc:`std` |
| `refactor`, `test` backfill, `chore` (`size` ≠ `large`) | oc:`std` |
| `docs`, `size: trivial` chore/refactor | oc:`lite` |

Presets (`--route` / plan `routing.preset`):
- `claude` — nothing offloaded; behaviour identical to dev-team-v3.2.
- `hybrid` — table above.
- `max` — `hybrid` + GREEN of `size: large` code slices on oc:`std`.

A `test` slice routed to opencode still passes the "must really add tests" and
vacuous-test checks; a `chore`/`docs` slice still needs its `verify` output. No oracle
(e.g. a `chore` without `verify`) → router forces `claude`. Reviewer fix-slices are routed
by the same table (their `kind`/`size`/`risk`); there is no separate rule for them.

## 8. Config

- **Shipped defaults**: `hybrid-team-v1.0/routing.default.json`.
- **User file**: `~/.config/hybrid-team/routing.json`, created by `doctor --fix` from the
  defaults if missing; the user edits it.
- **Per run**: plan JSON `routing` block overrides keys for that run.
- **Per slice**: `backend` field.

```json
{"preset": "hybrid",
 "tiers": {
   "std":  {"model": "zai-coding-plan/glm-5.3",       "variant": "high", "max_parallel": 6,
            "stall_s": 180, "timeout_s": {"trivial": 600, "small": 1200, "large": 2400}},
   "lite": {"model": "zai-coding-plan/glm-5.3-flash", "variant": "low",  "max_parallel": 6,
            "stall_s": 120, "timeout_s": {"trivial": 300, "small": 600, "large": 1200}}},
 "escalate_to": "claude", "max_escalations": 1}
```

Users may add tiers (e.g. `kimi` → `moonshotai/kimi-k2.7-code`) and point preset rows or
slices at them. `variant` is the thinking level, passed as the `#<variant>` model suffix.
Defaults above are the user's choice (2026-09-28).

## 9. Error handling

| Failure | Handling |
|---|---|
| Gate blocks twice | `.blocked{reason: gate}` → escalate |
| Stall / timeout | kill process group → `.blocked{reason: stall|timeout}` → escalate |
| 429 / quota throttle in event stream | `.blocked{reason: throttle}` → escalate; halve that tier's live slot cap for the run |
| opencode crash / non-zero exit / spawn error | `.blocked{reason: crash|spawn}` → escalate; the `error.type`/`message` of the error event goes into the note |
| Escalation | engine re-dispatches the slice to Claude `ht-programmer` (fresh native worktree); brief carries the failure notes + last gate stderr; max 1 escalation, then normal dev-team BLOCKED flow |
| opencode missing or auth broken at `doctor` | everything routes to Claude; one-line NOTE; run continues |
| Lane writes outside footprint / touches frozen test | caught by Stop gate (warm) and again by `integrate` (hard) |
| Stale lane process from a previous run | `lane <id>` kills the recorded pid's group (exact argv match) before starting |

The opencode side has no PreToolUse hook: the permission allowlist is the live guard,
the Stop gate + `integrate` are the enforcement.

## 10. Testing

- **Selftest**: fork `selftest.sh`; add a fake `opencode` stub selected via `HT_OC_BIN`
  that replays scripted JSON event streams. Cases: route table per preset + `backend`
  override; lane OK → `.done` → MERGED; gate block → session resume (`-s`) → OK; stall →
  group killed → escalate; 429 → escalate + cap halved; crash → `.blocked{crash}`;
  opencode missing → all-Claude degrade; `claude` preset produces dev-team's dispatch
  lines byte for byte.
- **Syntax**: `py_compile` on both scripts; `bash -n selftest.sh`.
- **Live**: `doctor --ping` sends one tiny prompt per tier and checks model, variant and
  JSON parsing; one real run on a 3-slice toy repo (one slice per backend/tier).

## 11. Evidence

- opencode v2.0.18 (local `opencode run --help`): `--model` "format provider/model#variant",
  `--standalone`, `--format json`, `--auto`, `--session`; no `--dir`/`--variant` flags —
  local CLI, 2026-09-28.
- Docs list `--variant`, `--dir`, `--attach` — [CLI docs](https://opencode.ai/docs/cli/)
  (2026-09-28) → version gap; follow the local CLI.
- `--auto` "Auto-approve permissions that are not explicitly denied" — local help +
  [CLI docs](https://opencode.ai/docs/cli/) (2026-09-28).
- Permission rules resolve last-match-wins — [Permissions](https://opencode.ai/docs/permissions/) (2026-09-28).
- Agent frontmatter: `model`, `permission`, `steps`, provider passthrough such as
  `reasoningEffort` — [Agents](https://opencode.ai/docs/agents/) (2026-09-28).
- Prior art spawns opencode as a CLI subprocess with async task ids —
  [opencode-mcp](https://github.com/alejandro-technology/opencode-mcp) (undated).
- Verifier-gated cascade: 88.0% vs 93.5% strong-only at a fraction of the cost —
  [cascade](https://github.com/darrshangovender/cascade) (undated; directional only).
- Local models available: `zai-coding-plan/glm-5.3`, `-flash`, `-highspeed`;
  `moonshotai/kimi-k2.7-code`, `kimi-k3` (`opencode models`, 2026-09-28).
- dev-team-v3.2 `integrate_one` checks only git state (footprint, frozen tests, RED
  commit), never the worker's identity (code read, 2026-09-28).
- Local probe of opencode v2.0.18 (2026-09-28, throwaway repo, 15 runs):
  - event schema and error shape as in §5.2; exit 0 on success, 1 on invalid model or
    variant ("Variant unavailable for …");
  - `run --standalone -s <sessionID>` resumes with full memory (warm continuation works);
  - 3 parallel `--standalone` runs in one repo and 3 in separate repos: all exit 0, no
    lock errors;
  - an agent-level `bash` deny beats the user's global `bash "*": allow`
    ("Permission denied: shell");
  - `OPENCODE_CONFIG_CONTENT` and `OPENCODE_CONFIG=<file>` both define usable agents;
  - project agents load from `.opencode/agent/` (singular) only in a normal checkout; in a
    linked git worktree they are not found, committed or not, and `--agent <unknown>`
    silently falls back to the default agent.

## 12. Assumptions

- hybrid-team is a new, opt-in skill; dev-team-v3.2 is not modified.
- Preset `hybrid` is the default; `claude` must reproduce dev-team behaviour.
- RED of offloaded code slices stays on Claude sonnet.
- Reviews stay on Claude (cross-model review is a feature).
- One `opencode run` process per lane; no `opencode serve`.
- Opencode lane cap defaults to 6 per tier.
- Escalation goes straight to Claude after one opencode lane (with ≤2 in-session
  continuations), max 1 escalation per slice.
- Stdlib-only Python 3.8+, bash 3.2, macOS-first, like dev-team.

## 13. Open questions

- Parallel safety was probed at 3 lanes, not 6+; the throttle rule in §9 covers
  provider limits, but lock behaviour at the default cap is checked in the live run (§10).
- Whether the event stream names the resolved agent (would make fallback detection
  per-lane instead of only at `doctor --ping`) — check during implementation.
