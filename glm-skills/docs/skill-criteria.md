# Skill Quality Criteria for ZCode

Authoritative checklist for writing and reviewing skills that target the ZCode harness. Every new
skill and every edit to an existing SKILL.md in `glm-skills/` must satisfy this document before it
is committed. Sources: the open Agent Skills standard (agentskills.io), Anthropic's skill-authoring
best practices, and ZCode-verified behavior (3.14.4, recorded in `../CLAUDE.md` under "ZCode facts").

## 1. Hard limits (a violation drops or degrades the skill)

- `description` must be **1024 characters or fewer**. A longer description makes ZCode drop the
  whole skill at load time. Re-check the length after every frontmatter edit.
- Only the **first ~250 characters** of the description are shown to the model each turn when it
  decides whether to trigger the skill. The WHEN clause must sit inside that window.
- The SKILL.md body is **truncated at 100KB** when loaded. Target **under 500 lines**; push detail
  into `references/` instead.
- `name` is 1-64 chars, lowercase kebab-case, and **must equal the directory name**
  (`test_all_skills.py` enforces this for glm skills).
- Frontmatter is flat top-level `key: value` lines. ZCode recognizes `name`, `description`,
  `when_to_use`, `license`, `metadata`; unknown keys and indented keys are ignored. Multi-line
  values need `>` or `|`.

## 2. Triggering: description and when_to_use

- State both **what** the skill does and **when** to use it, in third person.
- Be slightly pushy: models under-trigger skills. Enumerate user phrasings, synonyms and adjacent
  intents ("even if they don't explicitly say X").
- Put the WHEN clause at the front so it survives the ~250-character excerpt.
- `when_to_use` is a second ZCode trigger surface; use it when the description is already dense.

## 3. Body

- Imperative voice ("Read the file before editing").
- Explain **why** a rule exists instead of shouting MUST/NEVER; models follow reasoned guidance
  better than louder enforcement.
- Examples beat rules: any structured output or required tool call ships with a literal example.
- Progressive disclosure: SKILL.md is the routing table. Domain detail lives in `references/`, and
  the body says exactly when to read each reference file.
- Freedom levels: fragile or destructive tasks (migrations, deploys, deletions) get exact steps or
  scripts; judgment tasks (review, research) get goals and constraints, not procedures.
- Multi-step work is a checklist the model can track, with validate-then-fix loops before
  destructive or batch operations.

## 4. Bundled files

- `scripts/`: deterministic work the model would otherwise re-generate each run. Scripts solve
  their own errors (no punting to the model), declare their dependencies, and are executed, not
  read, unless the logic itself is the reference.
- `references/`: split by domain so unrelated content is never loaded; one level deep (no reference
  chains); files past ~100 lines get a table of contents.
- `assets/`: templates and fixtures, loaded on demand.

## 5. Anti-patterns

- Too many options: give one default plus an escape hatch.
- Inconsistent terminology: one term per concept, used everywhere.
- Backslash paths or syntax that does not port across harnesses.
- Layering more rules after a failed run: if the model does busywork (re-reading files, throwaway
  scripts, circling), the skill is over-prescribed. Cut rules; do not add.
- Time-sensitive facts without a staleness note.

## 6. Verification before committing a skill change

1. Name/frontmatter hygiene plus SKILL.md checks across all skills:
   `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v`
2. `description` length at or under 1024 chars and the WHEN clause inside the first 250.
3. Two or three realistic test prompts in a fresh ZCode session, including casual phrasing and
   typos; inspect both the result and the trace.
4. Iterate: generalize from feedback rather than overfitting, keep the prompt lean, and promote
   repeated helper code into `scripts/`.

## Sources

- [Agent Skills overview and specification (open standard)](https://agentskills.io)
- [Equipping agents for the real world with Agent Skills (Anthropic Engineering)](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- Anthropic skill-authoring best practices (mirrored in [obra/superpowers](https://github.com/obra/superpowers))
- ZCode verified facts: `../CLAUDE.md` "ZCode facts (3.14.4)" and the `zcode-guide` /
  `skill-creator` skills bundled with the app
