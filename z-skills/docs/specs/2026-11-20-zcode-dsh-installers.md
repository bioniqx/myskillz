# Two installer targets: verify zCode, add DeepSeek Harness (dsh)

Date: 2026-11-20. Status: approved in FAST mode (pick A). Scope: the z-skills install
scripts and _shared tests only. Work on main; one commit at the end of the chain.

## Architecture

Two installer flows already exist here: install-zcode.sh, pinned end to end by
_shared/tests/test_install_zcode.py (F-50), and the removed four-target front end whose
test file still pins its missing script (F-56, F-57). This change adds one sibling script,
install-dsh.sh, that installs the eleven z-* skill folders (F-55) into the DeepSeek
Harness user skills root; install-zcode.sh is verified unchanged; the dead test file is
removed. No new subsystem.

## Components

- install-dsh.sh (new): discovery of z-* folders with a root SKILL.md (eleven today,
  F-55; z-* folders without SKILL.md are reported as skipped); a preflight python3 block
  before any copy (description non-empty and at most 1024 chars, SKILL.md at most 100KB,
  frontmatter name present and kebab-case); per-skill rm -rf then cp into the target; junk
  exclusion (.DS_Store, __pycache__, *.pyc, .idea, opencode); full inventory print with
  counts; --dry-run; pause trap; set -eu POSIX sh.
- Target resolution: --home DIR wins, else $DSH_HOME, else $HOME/.dsh - the dsh user root
  at rank 400.
- Skills only: no agents, commands, manifest or flash pin; dsh documents no subagent or
  slash-command directory.
- _shared/tests/test_install_dsh.py (new): end-to-end against a temp HOME.
- _shared/tests/test_install_all.py: removed (F-56, F-57).
- install-zcode.sh: unchanged.

## Data flow

install-dsh.sh discovers the z-* folders, runs the preflight, resolves the dsh home
(--home, then $DSH_HOME, then $HOME/.dsh), then per skill rm -rf and cp the folder minus
junk, then prints the inventory and per-skill file counts. dsh discovers skills in that
root as directory bundles or top-level .md files; nested SKILL.md files are deliberately
not discovered, so each z-* folder lands as one top-level bundle. Frontmatter name must
be kebab-case and description is required - the preflight rejects violations before the
first copy.

## Error handling

Preflight violations abort non-zero before the first copy; --dry-run writes nothing; a
tree with no installable skills fails loudly; unknown flags are usage errors; foreign
folders are never touched.

## Testing

- z-skills suite green before and after.
- New test_install_dsh.py: dry-run writes nothing; every skill lands under the temp
  home's .dsh/skills; junk pruned; foreign folders untouched; --home and $DSH_HOME
  overrides; over-1024 description aborts before any copy; a tree with no installable
  skills fails loudly; rerun is idempotent and replaces changed files; inventory and
  counts printed.
- Real runs of both installers into the user home as the end-to-end proof.

## Evidence

- https://raw.githubusercontent.com/deepseek-ai/deepseek-harness/HEAD/packages/skill/skill-filesystem/README.md (2026-11-20, ledger-verified F-51, F-52, F-53): the rank-400 user root under the dsh home ($DSH_HOME or ~/.dsh), the two on-disk bundle formats, nested discovery off, kebab-case name, required description.
- https://raw.githubusercontent.com/deepseek-ai/deepseek-harness/HEAD/README.md (2026-11-20): the harness itself installs via npx @deepseek-ai/dsh web (ledger fetcher capped; unverified there, read via web fetch this session).
- https://github.com/deepseek-ai/deepseek-harness (2026-11-20): the harness project root and its docs tree.

## Assumptions

- The dsh target is ~/.dsh/skills, the dsh-owned root; the ~/.agents/skills root (rank
  500, shared with other harnesses) stays untouched.
- Folders are copied verbatim; dsh's optional frontmatter keys need no rewriting.
- The four-target front end stays removed; its test file is removed, not retargeted.

## Out of scope

The sibling repos (claude-skills, opencode-skills, hybrid-skills); root CLAUDE.md; skill
bodies and frontmatter; install-zcode.sh behavior; dsh plugin or profile setup; writes to
the shared agents root.
