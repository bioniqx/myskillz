# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

A working copy of the user's own Claude Code skills. The live, loaded copies sit in `~/.claude/skills/<same folder>`,
which is tracked by the git repo at `~/.claude`. This folder is **not** a git repo, and edits here do nothing until the
folder is copied back there. Third-party and synced skills (`graphify`, `find-skills`, `grill-*`, `synced/`) exist only
in `~/.claude/skills` and are out of scope.

Each folder is one skill: `SKILL.md` (frontmatter + instructions), plus optional `scripts/`, `agents/`, `references/`
and prompt/playbook `.md` files. `glm-skills/` holds GLM-5.3 ports of these skills for OpenCode/ZCode/Z.ai and has
its own `glm-skills/CLAUDE.md`. Read that one before touching anything under it.

There is no build and nothing to install. Scripts are stdlib-only Python 3.8+, POSIX `sh`, or bash 3.2 (the macOS
default), plus one Node server in brainstorming.

## The pipeline and the standalone skills

`brainstorming` → spec at `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` → `writing-plans` → plan at
`docs/superpowers/plans/YYYY-MM-DD-<feature>.md` → `dev-team` (adopts the plan as authoritative). Changing an output
path or format in one stage breaks the next.

Standalone skills: `systematic-debugging`, `requirements-code-audit`, `doc-generator` (SKILL.md only),
`git-diff-summary` (`scripts/gather.sh` prints `MODE=` markers that SKILL.md branches on) and
`frontend-design` (SKILL.md only).

## Commands (verification — there is no other test suite)

```bash
# dev-team: isolated end-to-end self-test (copies itself into mktemp -d, no network/HOME writes, ~40s)
bash dev-team-v3.2/scripts/selftest.sh

# Syntax checks
for f in */scripts/*.py requirements-code-audit/hooks/*.py; do python3 -m py_compile "$f"; done
bash -n systematic-debugging-6.3/scripts/*.sh       # bisect-parallel.sh is bash-only: never `sh -n` or `sh` it
node --check brainstorming-6.3/scripts/server.cjs

# Subcommand lists (each engine documents itself)
python3 dev-team-v3.2/scripts/devteam.py -h
python3 writing-plans-6.2/scripts/plan_tool.py --help
python3 requirements-code-audit/scripts/audit.py --help

# GLM ports: see glm-skills/CLAUDE.md (run from glm-skills/)
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests
```

Known red on macOS, not regressions:
- `selftest.sh` reports 241/247. One failure comes from GNU-only `sed -i` in the harness. Four come from
  `Path.resolve()` turning `/var` into `/private/var`, which breaks footprint/allow-list prefix matching. One is a
  bash 3.2 word-split in the harness.
- The `glm-skills` unittest suite has 12 failures. Eleven come from fixtures that still hardcode the old
  `skills/glm/...` path (the folder is now `glm-skills`). One needs a git repo.

## Skill mechanics that span files

- **Folder name ≠ skill name.** Versioned folders (`dev-team-v3.2`, `writing-plans-6.2`, …) declare the unversioned
  `name:` in frontmatter. In-file version numbers (CHANGELOG, SKILL.md headings) do not match the folder suffix.
  Record behaviour changes in the skill's CHANGELOG/README where one exists. The writing-plans CHANGELOG and the
  dev-team README are in Vietnamese.
- **`!` preload blocks** (brainstorming `context.sh`, writing-plans `plan_tool.py context`) run before the model reads
  SKILL.md. They must stay read-only and bounded (~55 lines), and must **always exit 0**, because a non-zero exit
  cancels the skill. Only `${CLAUDE_SKILL_DIR}` substitution works inside them; shell expansions like `${X:-y}` are
  rejected by the permission check.
- **`allowed-tools` pins exact script paths** under `${CLAUDE_SKILL_DIR}`. Renaming or moving a script silently drops
  its pre-approval.
- **SKILL.md and its script are coupled.** SKILL.md tells the model to run the script and trust its output (often a
  `NEXT:` line), and never to hand-write what the script generates. Change both together:
  - dev-team: CLI subcommands vs the Conductor's `allowed-tools`.
  - writing-plans: the Contracts template vs `plan_tool.py` rendering.
  - requirements-code-audit: `references/schemas.md` and the three `agents/rca-*.md` prompts, which restate the JSONL
    schema inline.
- Keep `description` ≤ 1024 chars. The current maximum is ~930, in requirements-code-audit.

## Per-skill engines

- **dev-team** (`devteam.py` scheduler/integrator + `guard.py` hooks):
  - Flow: `start <plan.md>` runs doctor, init and dispatch. After that, call `next` on every wake-up.
  - Programmers work in `.claude/worktrees/<id>`. They run `claim`, then the `commit-red`/`commit-green`/
    `commit-work`/`commit-fast` helpers. The Stop hook then writes a `.claude/dev-team/slices/<id>.done` or
    `.blocked` marker.
  - `guard.py` modes: `edit`/`bash` for programmers (footprint, frozen tests, deny-list), `edit-ro`/`bash-ro` for
    reviewers, investigators and the leader (only the leader may write `plan.md`), and `stop`. All are fail-open;
    the real enforcement is the merge-time re-check in `integrate`.
  - Profiles: `strict`/`balanced`/`turbo`/`spike`. Slice kinds map to programmer modes SLICE/RED/GREEN/WORK/FAST.
  - `guard.py` and `devteam.py` duplicate constants (`TEST_DIR_NAMES`, `TEST_FILE_PATTERNS`, `STATE_DIRNAME`).
    Keep them in sync by hand.
- **Agent install gotcha (dev-team).** The shipped `agents/*.md` hooks look for `guard.py` only under
  `.claude/skills/dev-team` or `~/.claude/skills/dev-team`, and the installed folder here is `dev-team-v3.2`. As a
  result, the copies in `~/.claude/agents/` (unpinned) exit 0 and enforce nothing. Enforcement happens only after
  `doctor --fix` runs in a project: it writes `.claude/agents/` with `pin_hooks()` absolute paths, plus
  `.claude/settings.local.json`. In `~/.claude/agents/team-leader.md`, `effort: xhigh` is a deliberate local tweak
  (the source says `high`).
- **writing-plans** (`plan_tool.py`):
  - Subcommands: `context` → `contracts` (writes writer briefs under `<plan-dir>/.work/<plan>/`) → `wait`/`review`
    → `assemble --clean`. `setup --apply` installs the `plan-task-writer` agent, whose PostToolUse hook runs
    `hook-lint`.
  - The linter enforces sequential `T01..` IDs, with producers numbered before consumers.
  - A portability scan bans tool/vendor words (`Claude`, `Anthropic`, `subagents`, tool names, …) from plan bodies.
- **brainstorming**: `context.sh` preload, plus an optional visual companion: `start-server.sh`/`stop-server.sh` →
  `server.cjs`, a hand-rolled HTTP+WebSocket server.
  - Session state lives under `.superpowers/brainstorm/`. Token files are `chmod 600`; keep them that way.
  - The server wraps HTML fragments in `frame-template.html`.
  - The HARD-GATE means no implementation before human approval. Drafts go to `.superpowers/drafts/`.
- **requirements-code-audit**:
  - Also packaged as plugin `req-audit` (`.claude-plugin/plugin.json`). Its agents are named
    `req-audit:rca-*` as a plugin, `rca-*` when copied locally, or `general-purpose` in generic mode.
  - Pipeline: `audit.py init` → parse/plan → investigator wave → `status` (the state-machine hub, prints `NEXT:`)
    → verifier wave → `adjudicate` → `report`/`check`/`finish`.
  - Writes only under `<cwd>/.audit/`.
  - `hooks/audit_guard.sh` exits fast unless `.audit/ACTIVE` exists. When active, it blocks git history, prose docs
    and writes outside `.audit/`. It is fail-open.
  - The audit must never read git; systematic-debugging's SWARM scripts depend on git worktrees and bisect. Don't
    port conventions between them.
- **systematic-debugging**:
  - Tiers: FAST → STANDARD → SWARM. Escalation only, with a hard stop after 3 failed fixes.
  - `scripts/*.sh` all source `_lib.sh`, which provides job clamping (1–64), a `timeout`/`gtimeout` fallback and
    worktree helpers.
  - `evals/*.md` are manual grading scenarios and are never loaded at runtime.
