# Skill Quality Criteria for ZCode

Authoritative checklist for writing and reviewing skills that target the ZCode harness. Every new
skill and every edit to an existing SKILL.md in `glm-skills/` must satisfy this document before it
is committed. Sources: the open Agent Skills standard (agentskills.io), Anthropic's skill-authoring
best practices, ZCode-verified behavior (3.14.4, recorded in `../CLAUDE.md` under "ZCode facts"),
and the 2025-2026 performance research linked under "Sources" (Red Hat Applied AI, LangChain,
arXiv skill-compression papers).

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

## 7. Execution speed without quality loss

Speed comes from three levers - load fewer tokens, move mechanical work out of the model, and
parallelize plus cache - and every lever pairs with a verification gate so output quality stays
flat. A skill that violates these is slower than it needs to be at equal quality.

### 7.1 Token intake (the biggest lever)

- Gate every bundled resource (references, examples, assets) so it loads only for the sub-task
  that needs it. Ungated resources are the single largest token sink - tens of thousands of tokens
  per invocation (Red Hat).
- Treat the 500-line body target as a performance threshold, not just a hygiene limit: measured
  skill performance degrades past it (Red Hat). Move rarely co-used or mutually exclusive content
  into separate files so two variants never load together (Anthropic).
- Compress before hand-cutting. Automated compression kept task quality at a 90.4% size reduction
  (SkillOpt, Red Hat) and at a 3.46x ratio with 99.2% of dependencies intact, with no evaluation
  runs needed (SkillZip, arXiv 2026). Run the compression pass, then re-run the eval set.
- The frontmatter description is the discoverability bottleneck. Write it as a search-optimized
  abstract: inputs, outputs, when to use, plus a negative constraint ("do NOT use for X"). A wrong
  trigger restarts the whole run - the most expensive slowdown of all (Red Hat).

### 7.2 Determinism over inference

- Token generation is far more expensive than running an algorithm (Anthropic). Fetching,
  formatting, validation, and fixed sequential procedures belong in `scripts/`; instructions cover
  only subjective analysis and edge-case judgment.
- Evidence: Red Hat's root-cause agent moved file-fetching from inference to scripted GitHub API
  calls and cut cost 26% while accuracy improved.
- Hardcode sequential steps inside one script instead of letting the model chain them turn by
  turn: fewer model turns and no dependence on harness chaining (Red Hat).
- Every punted error is an extra model round-trip; scripts solve their own errors ("solve, don't
  defer"), as section 4 already requires.

### 7.3 Execution architecture

- Fan out to sub-agents: each burns tens of thousands of tokens in its own context and returns a
  1,000-2,000 token summary, keeping the lead agent clean; this beats single-agent runs on complex
  tasks and avoids context rot (Anthropic).
- Retrieve just in time: keep lightweight identifiers (paths, queries, links) instead of
  pre-loading whole files; pair a small stable map with targeted grep/read at run time.
- Keep the cacheable prefix stable: cache reads bill at 0.1x input price and cut time-to-first-
  token up to 85% on long prompts (Anthropic). Churning skill content between runs defeats the
  cache.
- Route routine sub-tasks to faster or cheaper models when the harness allows it (over 75% of
  production teams multi-route; LangChain).
- Cap density at roughly 1-3 skills per task (Red Hat): distractor skills lower trigger accuracy
  and actively mislead the agent.

### 7.4 Quality gates that make speed-ups safe

- Evaluate before and after any speed change: with-skill vs without-skill runs, LLM-judge plus
  human spot review, on a set that includes boundary cases and red herrings (Red Hat, Anthropic).
- Cost gate in CI: regression-test skills and fail merges that silently raise tokens per
  invocation; use step-level tracing to locate the slow step before optimizing (62% of production
  teams trace per step; LangChain).
- No speed-up counts until the section 6 verification re-passes on the same prompts.

## Sources

- [Agent Skills overview and specification (open standard)](https://agentskills.io)
- [Equipping agents for the real world with Agent Skills (Anthropic Engineering)](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Effective context engineering for AI agents (Anthropic Engineering)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Agent Skills best practices (Claude Platform Docs)](https://platform.claude.com/en/docs/agents-and-tools/agent-skills/best-practices)
- [Prompt caching (Claude Platform Docs)](https://platform.claude.com/en/docs/build-with-claude/prompt-caching)
- [Building skills for AI agents: pitfalls and best practices (Red Hat, Jul 2026)](https://next.redhat.com/blog/building-skills-for-ai-agents-pitfalls-and-best-practices)
- [State of Agent Engineering (LangChain)](https://www.langchain.com/state-of-agent-engineering)
- [SkillZip: contract-preserving skill compression (arXiv 2608.05604)](https://arxiv.org/abs/2608.05604)
- Anthropic skill-authoring best practices (mirrored in [obra/superpowers](https://github.com/obra/superpowers))
- ZCode verified facts: `../CLAUDE.md` "ZCode facts (3.14.4)" and the `zcode-guide` /
  `skill-creator` skills bundled with the app
