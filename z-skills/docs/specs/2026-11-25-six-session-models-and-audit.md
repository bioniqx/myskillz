# Six session models: GLM 5.4 joins the matrix, then a full audit of the non-video skills

Date: 2026-11-25. Status: approved in FAST mode (pick A). Scope: the nine non-video z-* skill
folders, _shared, the installers, the tests and AGENTS.md. Work happens on main; commit happens
once at the end of the chain, after z-dev-team's own checks. The two video skills, the sibling
repos, the vendored gamedev bundle and the .audit folder are not touched.

## Architecture

Goal: every non-video skill works correctly with six session models - GLM 5.3 Flash, GLM 5.3,
GLM 5.4, DeepSeek V4.1 Flash, DeepSeek V4 Pro and Claude Sonnet 5.5 - on both harnesses, and
carries no stale or false statement. Two existing flows are widened; no new subsystem.

1. Model layer. The five-model vocabulary of the 2026-11-19 spec becomes six: GLM 5.4 (id
   glm-5.4, pro tier). The contract does not change: agents follow the session model, no lane is
   promoted, decisions close in scripts. Every enumeration learns the sixth id, and every sentence
   that addresses the session model by tier is true for all six.
2. Pin layer. glm-5.4 becomes a GLM pro pin word with the same meaning as glm-5.3.
3. Audit layer. One pass over every non-video skill against docs/skill-criteria.md, AGENTS.md and
   the six-model matrix, with a fixed rule for what is fixed and what is only reported.

## Components

Model layer:
- The nine non-video SKILL.md frontmatter models lines (all six ids on one flat line).
- _shared/handoff.py GUARD flash line, re-vendored into eight skills by _shared/sync.sh.
- _shared/zai_client.py module docstring, re-vendored into three skills.
- z-tuning.md, four copies: a six-row Session models table, a GLM 5.4 row with dated vendor facts
  only, and titles that no longer name two models.
- z-systematic-debugging/README.md, z-dev-team/SKILL.md lane sentence, z-writing-plans/SKILL.md
  pro-pin clause, z-systematic-debugging/SKILL.md keeps-own-model clause, AGENTS.md target
  paragraph.
- z-brainstorming/visual-companion.md screenshot read-back paragraph.
- CHANGELOG.md of z-brainstorming and z-writing-plans: one dated entry each.

Pin layer:
- _shared/flash_pin.py: _name accepts glm-5.4; PRO_API maps it to the api id glm-5.4. Re-vendored
  into four skills.
- install-zcode.sh: the saved-pin case learns glm-5.4.
- _shared/tests/test_flash_pin_pro.py: the new pin word under an env pin and a file pin.

Truthful addressing (stale statements verified this session, fixed in this run):
- z-dev-team/scripts/devteam.py: the docstring and the INIT line that name GLM-5.3-Flash lanes
  with a model and effort pinned in the agent frontmatter.
- z-writing-plans/scripts/plan_tool.py: the doctor line that prints the light tier as low effort.
- z-brainstorming/z-tuning.md: section 2, one failure-table row and the install count.
- z-requirements-code-audit/references/z-tuning.md: two sentences that say agent files pin a model.
- z-brainstorming/agents/z-drafter.md and z-design-breaker.md: the "Flash lane" descriptions.
- z-requirements-code-audit/SKILL.md: "GLM requests" in the description, inside the 1024 limit.

Tests that move with the requirement (each edited assertion is listed with its reason):
- _shared/tests/test_all_skills.py, test_model_terms_bodies.py, test_model_terms_tuning.py,
  test_flash_pin_pro.py and, for the saved pin word, test_install_zcode.py.

Verified locations (read this session; F-numbers are this session's ledger facts):
- _shared/handoff.py:281 "or Claude Sonnet 5.5." - the guard names five session models (F-58).
- _shared/zai_client.py:7 "Session models served through this client" - the docstring names five (F-59).
- AGENTS.md:9 "These skills target four session models" - the project rules lag one sweep behind (F-60).
- _shared/flash_pin.py:40 "glm-5.3-flash" - the glm words of the pin vocabulary carry no glm-5.4 (F-61).
- _shared/flash_pin.py:20 "glm-5.3" - the pro table has one GLM id (F-62).
- install-zcode.sh:368 "FLASH=glm" - the saved-pin mapping has no glm-5.4 (F-63).
- install-zcode.sh:387 "z-flash" - the installer writes the provider word back (F-64).
- _shared/tests/test_install_zcode.py:167 "deepseek" - a test pins that write-back (F-65).
- _shared/tests/test_all_skills.py:194 "claude-sonnet-5.5" - five ids pinned flat (F-73).
- _shared/tests/test_model_terms_bodies.py:18 "FIVE_ID_LINE" - five ids pinned again (F-74).
- _shared/tests/test_model_terms_tuning.py:28 "Claude tier" - the three tier words (F-75).
- _shared/tests/test_flash_pin_pro.py:164 "test_names_all_five_session_models" - five in the guard test (F-76).
- z-dev-team/scripts/devteam.py:1730 "GLM-5.3-Flash" - the INIT line still names flash lanes (F-77).
- z-dev-team/scripts/devteam.py:1731 "pinned in the agents' frontmatter" - no agent file carries a model id (F-78).
- z-dev-team/scripts/devteam.py:73 "effort is max on every agent" - the lite agent file sits at thoughtLevel high (F-79, F-96).
- z-writing-plans/scripts/plan_tool.py:2160 "light=%s/low" - the tier table sets high for light (F-81, F-82).
- z-brainstorming/z-tuning.md:51 "Model and effort live only in the agent frontmatter" - the opposite of the skill rule (F-83).
- z-brainstorming/SKILL.md:169 "The session supplies both." - the rule the tuning doc contradicts (F-85).
- z-brainstorming/z-tuning.md:104 "Install all eight skills" - eleven z-* folders exist (F-84).
- z-requirements-code-audit/references/z-tuning.md:31 "The agent files pin the same Flash id." - stale since the sweep (F-86).
- z-brainstorming/agents/z-drafter.md:3 "Flash lane for z-brainstorming" - flash-only wording in an agent description (F-88).
- z-brainstorming/visual-companion.md:74 "glm-5.3 is text-only" - true for GLM 5.3, silent on GLM 5.4 (F-90).
- No agent file of the non-video skills carries a model line; all eighteen carry a thoughtLevel (grep this session).
- The host model list read this session has rows for GLM-5.4 (levels low, high, max) and the two
  DeepSeek models, and no Claude Sonnet 5.5 row (ListModels; ledger-unverified).

## Data flow

The session model never changes: a lane runs on whatever model the session uses. The HTTP
fan-out keeps two providers. A pin file or GLM_FLASH value of glm-5.4 resolves to provider glm
and sends every fan-out call to the api id glm-5.4; glm, flash and glm-5.3-flash keep today's
behavior; an unknown word still resolves to glm. The installer maps a saved glm-5.4 word to the
glm provider the way it maps the other pro words. After the shared edits, _shared/sync.sh
re-vendors the scripts so each skill copy stays byte-identical to _shared.

## Error handling

A pin word outside the vocabulary keeps resolving to glm. A glm-5.4 pin that the endpoint does
not serve fails loudly at the provider with the provider's own error; nothing falls back to a
smaller model in silence. Audit findings that cannot be reproduced by a test or a grep are
reported, not fixed.

## Testing

Acceptance:
- Full suite green (baseline this session: 795 tests, OK) and the hygiene suite green.
- sh _shared/sync.sh leaves no diff.
- Grep proof that no non-video file enumerates five session models or says four, and that every
  file which names the other five ids names glm-5.4 too.
- New unit test: the glm-5.4 pin word under an env pin and a file pin, plus resolve_http_model.
- A findings list in the final report: each audit finding, its disposition (fixed or reported),
  the check that reproduces it, and every test assertion edited with its reason.

## Evidence

- GLM-5.4: cards state Context Length 1M and Maximum Output Tokens 128K; input modality "Video / Image / Text / File"; "The Model API will be made available upon completion of the security assessment." - https://docs.z.ai/guides/llm/glm-5.4 (2026-11-25, read by web fetch this session; ledger fetcher offline)
- GLM-5.3: model id "glm-5.3" in the request examples; "GLM-5.3 currently supports text-only inputs, with a 1M-token context window and a maximum output length of 128K tokens."; reasoning_effort low, high, max with default max - https://docs.z.ai/guides/llm/glm-5.3 (2026-11-25, read by web fetch this session)

## Assumptions

- Whether the fan-out endpoint serves glm-5.4 is unverified: one probe this session returned
  HTTP 429 code 1113 "Insufficient balance or no resource package. Please recharge." from the
  first key the client finds (in ~/.claude/settings.json). Inferred: with that key first in the
  lookup order, the api lane of every fan-out skill fails on this machine until the key is fixed.
- Claude Sonnet 5.5 cannot be exercised on this host; its tier is checked statically only.
- No per-model benchmark is run. Behavioural rules stay conditional on the model in session and
  keep their dated sources; no speed or price number is added for GLM 5.4.
- Nothing is installed into ~/.zcode or the dsh home by this run; the change takes effect after
  the installers are run again.

## Out of scope

- z-video-shotcraft and z-viral-video-studio; the sibling repos claude-skills, opencode-skills
  and hybrid-skills; awesome-gamedev-agent-skills-1.1.0 and .audit.
- A new provider route (none for Claude); a benchmark harness; decide.py scoring, check.py gates
  and the dev-team guard hooks; any new feature or redesign surfaced by the audit (reported with
  a recommendation instead).
