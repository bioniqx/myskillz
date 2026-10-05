# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Role in the skillz monorepo

`claude-skills/` holds the **original (source-of-truth) skills**. The other three sibling folders are
variants derived from these originals:

- `../glm-skills/` — variants for ZCode / GLM (`*-glm`).
- `../hybrid-skills/` — variants that combine Claude + opencode to save cost (`hybrid-*`).
- `../opencode-skills/` — variants built specifically for opencode (`oc-*`).

Make behaviour changes here first, then port them to the variants; never treat a variant as the reference.

## What this repo is

A collection of **Claude Code skills** — each top-level directory is a self-contained, installable
skill (some packaged as full plugins) that changes how Claude Code behaves for a class of task
(brainstorming a design, running a multi-agent dev pipeline, debugging, auditing a codebase against
a spec, writing implementation plans, summarizing a git diff, documenting a codebase, frontend design
taste). There is no application code here — the "product" is the `SKILL.md` instructions plus the
Python/Bash scripts, subagent definitions, and hooks that back them.

Skills in this repo:

| Directory | Skill | What it does |
|---|---|---|
| `claude-brainstorming-6.3/` | `claude-brainstorming` | Turns a vague request into an approved design via parallel code+web research lanes, gated by one human approval before any implementation. |
| `claude-dev-team-v3.2/` | `claude-dev-team` | Event-driven multi-agent implementation pipeline: a deterministic Python scheduler (`devteam.py`) dispatches parallel (live cap, programmers ≤16) `claude-programmer`/`claude-code-reviewer`/`claude-spot-reviewer`/`claude-investigator`/`claude-team-leader` subagents, each in its own git worktree, gated by hooks (`guard.py`). |
| `claude-requirements-code-audit/` | `claude-requirements-code-audit` | Audits a codebase against a requirements/spec document using parallel investigator + adversarial verifier subagents, driven by `scripts/audit.py`. Ships as a full Claude Code plugin (`.claude-plugin/plugin.json`) with its own agents and `hooks/audit_guard.py`. |
| `claude-writing-plans-6.2/` | `claude-writing-plans` | Generates a portable, TDD-oriented implementation plan (Markdown checkboxes) from a spec, fanning task-body writing out to parallel subagents via `scripts/plan_tool.py` and a deterministic linter. |
| `claude-systematic-debugging-6.3/` | `claude-systematic-debugging` | Root-cause-first debugging workflow (FAST / STANDARD / SWARM lanes) with shell helpers (`stress.sh`, `bisect-parallel.sh`, `find-polluter.sh`, `snapshot.sh`) for parallelized repro, bisection, and flake-hunting. |
| `claude-doc-generator/` | `claude-doc-generator` | Generates/updates Markdown documentation for a codebase in two parallel waves (write, then risk-tiered review), with caching via `.claude/doc-generator/`. |
| `claude-git-diff-summary/` | `claude-git-diff-summary` | Summarizes the working branch's diff vs. a base branch: Vietnamese non-technical description + English commit message, via `scripts/gather.sh`. |
| `claude-frontend-design-Jun18/` | `claude-frontend-design` | Pure guidance skill (no scripts) for distinctive, non-templated visual/UI design decisions. |
| `tests/` | — | Black-box test suite (Python `unittest`) covering the scripts behind the skills above — not a skill itself. |

Several skills have `hybrid-*` counterparts referenced in their descriptions/commit history (offloading
work to a local `opencode` CLI) — those live in `../hybrid-skills/` (see its `CLAUDE.md`), not in this folder.

## Commands

No package manager, no `package.json`/`pyproject.toml`/`pytest.ini` — scripts are dependency-free
Python 3 (stdlib only) and POSIX shell. `pytest` is **not** installed in this environment; use the
stdlib `unittest` runner.

**Run the full test suite:**
```bash
python3 -m unittest discover -s tests -v
```

**Run one test file:**
```bash
python3 -m unittest tests.test_plan_lint -v
```

**Run one test case / one test method:**
```bash
python3 -m unittest tests.test_plan_lint.PortabilityScanTests -v
python3 -m unittest tests.test_plan_lint.PortabilityScanTests.test_todo_tbd_fixme_xxx_are_case_sensitive -v
```

Test-file-to-script mapping (tests live centrally under `tests/`, not next to the script they cover):
- `test_devteam_*.py`, `test_guard_*.py` → `claude-dev-team-v3.2/scripts/devteam.py` + `guard.py`
- `test_audit_*.py` → `claude-requirements-code-audit/scripts/audit.py`
- `test_agent_hooks.py` → `claude-requirements-code-audit/hooks/audit_guard.py`
- `test_plan_tool.py`, `test_plan_lint.py` → `claude-writing-plans-6.2/scripts/plan_tool.py`
- `test_brainstorm_*.py` → `claude-brainstorming-6.3/scripts/`
- `test_debug_scripts.py` → `claude-systematic-debugging-6.3/scripts/`
- `test_gather.py` → `claude-git-diff-summary/scripts/gather.sh`

Tests write all fixtures under the **system temp dir**, never inside this repo/worktree — this is
deliberate, so `guard.py`'s/`devteam.py`'s parent-directory walk for `.slice/`/`.claude/dev-team` never
mistakes a test fixture for a real run. Preserve this when adding tests.

**Invoking a skill's engine script directly** (useful when debugging, mirroring what the skill tells
the model to run):
```bash
python3 claude-dev-team-v3.2/scripts/devteam.py <cmd>              # e.g. doctor --fix, start <plan.md>, next, status
python3 claude-requirements-code-audit/scripts/audit.py <cmd>      # e.g. init, plan, status, report, finish
python3 claude-writing-plans-6.2/scripts/plan_tool.py <cmd>         # e.g. context, contracts, wait, assemble
bash   claude-git-diff-summary/scripts/gather.sh [base-branch]
bash   claude-systematic-debugging-6.3/scripts/stress.sh -n 200 -- <cmd>
```
Every script supports `-h`/`--help`.

**Linting/typechecking:** none configured for this repo; there is no build step.

## Architecture

### The skill format

Every skill directory is a Claude Code "skill": a `SKILL.md` with YAML frontmatter (`name`,
`description`, `when_to_use`, `allowed-tools`, sometimes `argument-hint`/`compatibility`) followed by
Markdown instructions that *are* the behavior — this is prompt-as-program, not a library that gets
imported. `claude-requirements-code-audit/` additionally ships as a full plugin via
`.claude-plugin/plugin.json`, bundling its own agents and hooks so it installs standalone.

Common subdirectories across skills:
- `scripts/` — stdlib Python or POSIX shell "engines" that do all deterministic/mechanical work
  (state machines, parsing, linting, git plumbing, scheduling) so the model never has to re-derive or
  hand-track it. The model's job is to run one script command, read its machine-readable output
  (often an explicit `NEXT:`/`DISPATCH:` line), and act on exactly what it printed.
- `agents/*.md` — subagent persona definitions (model tier, tool restrictions, hooks, isolation mode)
  that the orchestrating skill dispatches by name.
- `hooks/` — `PreToolUse`/`Stop`/`SubagentStop` guard scripts (e.g. `guard.py`, `audit_guard.py`) that
  mechanically enforce invariants the instructions alone can't guarantee: disjoint file footprints
  between parallel workers, "tests committed before implementation and frozen after," read-only roles
  not writing code, no `git` history/log/blame access for audit workers, no writes outside a scoped
  output directory, no destructive git operations.
- `references/` — longer reference docs loaded only on demand (large specs, parallel-fanout
  playbooks, report/schema formats) to keep the main `SKILL.md` lean.

### The recurring design pattern: deterministic engine + parallel subagent swarm

`claude-dev-team`, `claude-requirements-code-audit`, and `claude-writing-plans` share one architecture, visible across
`devteam.py`, `audit.py`, and `plan_tool.py`:

1. A Python script is the **only** source of mutable state (plan/checklist/contracts as JSON/JSONL
   under a scoped dir like `.claude/dev-team/`, `.audit/`, or the plan's scratch dir) and the only
   thing that decides what runs next, enforces caps, and merges results.
2. The orchestrating model (the "Conductor"/"Lead") never does legwork a script or subagent can do:
   each turn is *read what a script/notification printed → make exactly the calls it named → end the
   turn*. Width (parallel dispatch, up to the `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` cap, soft ceiling 12 for
   most skills; fewer, fuller agents beat many tiny ones) is the main lever for wall-clock speed, not model cleverness.
3. Workers (subagents) are stateless, scoped to one unit of work, communicate back through a file the
   engine reads (a `.done` marker, a JSONL batch result, a report file) rather than through chat, so
   dispatching dozens of them doesn't blow up the orchestrator's context.
4. Hooks catch what the prompt can't guarantee: disjoint footprints so two workers never touch the
   same file, frozen/un-skippable tests, read-only roles that can't become write-capable, and (for the
   audit skill) a structural block on reading git history or prose docs so the spec stays the single
   source of truth.
5. Each of these skills supports multiple "fidelity levels" depending on what's installed in the host
   environment (plugin with hooks > local agents > generic `general-purpose` subagents > solo/no-agent
   fallback) — see each skill's `SETUP.md`/`README.md` for the detection logic.

### Testing convention

Tests under `tests/` are black-box: they invoke the scripts as subprocesses (`subprocess.run`) against
fixtures in a system temp directory and assert on stdout/exit codes/on-disk state, not on internal
Python objects. When changing a script's CLI output format, grep `tests/` for the exact strings it
asserts on (e.g. `NEXT:`, status markers) before assuming a refactor is safe.

The repo's own commit history follows a strict RED→GREEN convention for script changes (visible via
`git log`): `test(FNN): RED — <behavior>` adds a failing test first, `feat(FNN): GREEN — <behavior>`
makes it pass, `merge(FNN): <behavior>` lands the pair — mirroring the TDD discipline the `claude-dev-team`
and `claude-writing-plans` skills themselves enforce on their subagents. Follow the same pattern for changes
to the scripts in this repo.
