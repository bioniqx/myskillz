# Five session models, four install targets

Date: 2026-11-19. Status: approved in FAST mode (pick A). Scope: the eleven z-* skill
folders in this repo, _shared, and the installers. Work happens on main; commit happens once
at the end of the chain, after z-dev-team's own checks. The sibling repos claude-skills,
opencode-skills and hybrid-skills are not touched.

## Architecture

Two existing flows are widened; no new subsystem.

1. Model layer. Every place that names the session model or the HTTP fan-out model learns the
   five session models: GLM 5.3 Flash and DeepSeek V4.1 Flash (flash tier), GLM 5.3 and
   DeepSeek V4 Pro (pro tier), Claude Sonnet 5.5 (Claude tier). The contract does not change:
   agents follow the session model, no lane is promoted, decisions close in scripts. A pro or
   Claude session is addressed truthfully instead of being told it is GLM flash.
2. Install layer. A new install-all.sh fronts the existing install-zcode.sh and adds three
   targets: ~/.agents/skills, ~/.claude/skills and ~/.config/opencode/skills. The zcode target
   keeps its richer installer (agents, commands, manifest, flash pin) unchanged.

## Components

- _shared/handoff.py: rewrite the GUARD flash line to name the five session models and keep
  the no-promotion rule; sync.sh vendors it into the eight skills that carry handoff.py.
- _shared/flash_pin.py: the pin vocabulary gains the pro words; provider mapping stays glm or
  deepseek; resolve_http_model returns the pro API id when the pin says pro. Vendored into
  four skills.
- _shared/zai_client.py: module docstring and model-note updates only; payload logic
  unchanged.
- z-tuning.md, four copies (the root copy in z-brainstorming; references/ copies in
  z-writing-plans, z-requirements-code-audit and z-systematic-debugging): a five-row
  tier table replaces the two-row table; the cited GLM numbers stay; DeepSeek and Sonnet rows
  stay qualitative.
- Model-naming lines in SKILL bodies and agents: z-dev-team SKILL.md and
  agents/z-team-leader.md, z-writing-plans SKILL.md, z-systematic-debugging SKILL.md
  and README, z-requirements-code-audit SKILL.md, z-brainstorming SKILL.md,
  visual-companion.md and the two playbooks. Tier wording sweep only; no rule changes.
- install-all.sh (new): discovery, preflight and junk exclusion reused from install-zcode.sh;
  per-target copy rules; the opencode target reproduces the on-disk convention.
- _shared/tests: extend the flash_pin unit coverage for the pro pin words; the vendored map in
  test_vendored.py changes only if a sync.sh list changes.

## Data flow

install-all.sh discovers every z-* folder with a root SKILL.md (eleven today), runs the
same preflight as install-zcode.sh, then per target: zcode delegates to install-zcode.sh
unchanged; .agents and .claude take each skill folder as-is minus junk (.DS_Store,
__pycache__, *.pyc, .idea, opencode); opencode takes each skill folder with repo agents/
placed under opencode/agents/, preserves any existing opencode/commands/*.md bodies
verbatim (they are opencode-specific prose, not derivable from the repo commands), and
writes a .oc-major marker per skill (bump the existing number when present, write 1 when
absent). After the model-layer edits, sync.sh re-vendors the shared scripts so each skill
copy stays byte-identical to _shared.

## Error handling

A pin word outside the vocabulary resolves to glm today, silently; after the change every pro
word resolves to its provider and an unknown word still resolves to glm. install-all.sh keeps
the preflight failure mode of install-zcode.sh: any frontmatter, agent or command violation
aborts before the first copy; --dry-run prints the plan and writes nothing. Missing target
directories are created; existing z-* folders in a target are replaced with rm -rf then
copy; folders that are not z-* in a target are never touched.

## Testing

- Existing suites first: the hygiene suite (unittest discover on _shared/tests) and the
  vendored test green before any edit, and green after.
- New unit test for flash_pin: each pro word maps to its provider; resolve_http_model returns
  the pro API id under a pro pin and the flash id under a flash pin; unknown words still
  resolve to glm.
- Installer: --dry-run lists every skill for every target and writes nothing; after the real
  run, a recursive diff between each target folder and the repo shows only the expected
  layout differences (the opencode subdir moves and its command bodies stay); the script
  prints per-target file counts.

## Evidence

Repo-internal; every claim was read this session.

- _shared/handoff.py:281 - the guard names only GLM-5.3-Flash and DeepSeek V4.1 Flash and
  forbids glm-5.3 and deepseek-v4-pro as switches.
- _shared/flash_pin.py:29 - the pin vocabulary accepts only deepseek, ds, deepseek-flash,
  glm, glm-5.3-flash and flash words.
- z-brainstorming/z-tuning.md:14 - the model table lists GLM-5.3 as "not used".
- install-zcode.sh:61 - SKILLS_DIR under .zcode is the only skills destination.
- _shared/sync.sh:19 - handoff.py vendors into eight skills.
- The eight z-* folders under the opencode target each carry .oc-major holding 2, and the
  skills with repo agents carry them under opencode/agents; the brainstorming copy there
  predates z-drafter and z-design-breaker. unverified: who last wrote those markers.

## Assumptions

- The claude-*, oc-* and hybrid-* folders in ~/.claude/skills and ~/.config/opencode/skills
  belong to sibling repos and stay untouched.
- The vendored gamedev bundle and the .audit folder are neither edited nor installed.
- No numeric speed or price claim for DeepSeek or Sonnet models is added anywhere.
- Claude Sonnet 5.5 is a session model only; it gains no HTTP fan-out provider.

## Out of scope

- The sibling repos claude-skills, opencode-skills and hybrid-skills.
- decide.py scoring, check.py gates and the devteam guard hooks.
- Skill bodies beyond model wording; no behavioral rewrite of any workflow.
- z-video-shotcraft and z-viral-video-studio carry no session-model lines today; they are
  installed like the rest and otherwise untouched.
