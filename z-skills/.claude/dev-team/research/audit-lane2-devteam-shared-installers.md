# Audit briefing: lane 2 of 3 - z-dev-team, _shared, installers, AGENTS.md, CI

Date: 2026-11-25. Read-only. You edit nothing and create nothing except the one report file
named in your prompt.

## Goal

The folder z-skills/ holds agent skills that must work with six session models on two harnesses
(ZCode and DeepSeek Harness): GLM 5.3 Flash (id glm-5.3-flash), GLM 5.3 (glm-5.3), GLM 5.4
(glm-5.4, new, pro tier), DeepSeek V4.1 Flash (deepseek-flash), DeepSeek V4 Pro
(deepseek-v4-pro) and Claude Sonnet 5.5 (claude-sonnet-5.5). Agents follow the session model:
no agent file may pin a model id.

The owner asked for a full check of every non-video skill: find real problems, each with a
reproducing check and a minimal fix. Other work already owns the items under "Already owned";
stay out of those.

## Scope (yours)

- z-skills/z-dev-team/ - every file (SKILL.md, the six agents, references/, scripts/devteam.py,
  scripts/guard.py, scripts/selftest.sh, commands/).
- z-skills/_shared/handoff.py, decide.py, zai_client.py, flash_pin.py and sync.sh.
- z-skills/install-zcode.sh and z-skills/install-dsh.sh.
- z-skills/AGENTS.md and z-skills/.github/workflows/skills.yml.

Sibling lanes cover (stay out): z-brainstorming and z-writing-plans (lane 1);
z-requirements-code-audit, z-systematic-debugging, z-doc-generator, z-find-skills,
z-git-diff-summary, z-idea-to-spec (lane 3).

## Criteria (a finding must violate one of these)

1. z-skills/docs/skill-criteria.md sections 1 to 5. Read the file first.
2. z-skills/AGENTS.md. Read it first.
3. Six-model matrix: an enumeration of session models must list all six or say it is partial; no
   sentence may tell a non-flash session that it is flash; every agents/*.md file carries no
   model line; a rule justified by one model's weakness must say which model it applies to.
4. Truthfulness: a statement that is false or stale today, proven by another file in the repo, by
   a command you ran, or by a document you actually read.
5. Broken reference: a file, script, agent, command, flag, path or environment variable named in
   prose or in a printed line that does not exist or is not what the text says.
6. Script defect reachable from the skill's own steps, reproduced by a read-only command.
7. Internal contradiction: two sentences, or a sentence and the code it describes, that cannot
   both be true.

## What is NOT a finding

- Style, wording taste, hypothetical redesigns, missing features, "could be improved".
- Anything inside z-video-shotcraft/, z-viral-video-studio/, .audit/,
  awesome-gamedev-agent-skills-1.1.0/.
- Model behaviour claims you cannot check: list them under "Not verified", labelled UNVERIFIED.

## Already owned by other work (stay out)

- Every enumeration of five session models: the frontmatter models lines, the shared GUARD flash
  line in _shared/handoff.py (line 281), the four z-tuning.md "Session models" tables and
  titles, z-systematic-debugging/README.md line 3, the z-dev-team lane sentence in
  z-dev-team/SKILL.md line 67, the z-writing-plans pro-pin clause, the debugging keeps-own-model
  clause, the AGENTS.md target paragraph (lines 9 to 14).
- The pin vocabulary in _shared/flash_pin.py (lines 37 to 42 and 19 to 22) and the saved-pin case
  in install-zcode.sh (lines 365 to 369).
- z-dev-team/scripts/devteam.py lines 3-5, 71-75, 168-172 and 1730-1731.
- z-writing-plans/scripts/plan_tool.py line 2160.
- z-brainstorming/z-tuning.md lines 51-52, 74 and 104.
- z-requirements-code-audit/references/z-tuning.md lines 31 and 41.
- The "Flash lane" descriptions of two z-brainstorming agents.
- z-brainstorming/visual-companion.md lines 72-75.
- The "GLM requests" phrase in the z-requirements-code-audit description.
- install-zcode.sh line 387 (a saved pro pin word is rewritten to its provider word).

## Method

- Read every prose file in scope in full.
- For scripts: read the module docstring, the argparse or help text, and every user-visible
  string (print, out, echo, NEXT lines) that names a model, a harness, a path, a count or
  another skill. Run each script with --help, and any read-only subcommand that the SKILL.md
  steps name (for example `devteam.py doctor --harness zcode` without --fix). Never run a
  command with --fix, --apply, start, init, reset or anything that writes. Do not attempt a
  line-by-line logic review of a file over 500 lines.
- A printed line that names a file, a count, an agent or a flag is checked against the tree.
- Prove a broken reference with a grep or a listing before you call it broken.
- Quote verbatim and give the line number you read. If you did not open a file, do not cite it.

## Report format (write exactly this)

The report is plain ASCII English.

# Audit report: lane 2 - z-dev-team, _shared, installers, AGENTS.md, CI

## Findings

One block per finding:

### F-<n> <BLOCKER | MAJOR | MINOR>
- Where: <path>:<line>
- Quote: "<verbatim, 25 words or fewer>"
- Criterion: <number and name from the Criteria list>
- Why it is a defect: <one or two sentences>
- Reproduce: <one read-only command and the output that shows the defect>
- Fix: <the exact edit: the text to replace and the text to put there, minimal>
- Files the fix touches: <paths>

Severity: BLOCKER = the skill fails, or misleads a session model into a wrong action; MAJOR = a
false or stale statement, a broken reference, a wrong help text, a contradiction; MINOR = a
hygiene limit or a small inconsistency.

## Ready-to-dispatch fix slices

Group the findings into the smallest sets that touch disjoint files. One block per slice: the
files, the finding ids, and the test or grep that proves each fix.

## Not verified

Claims you could not check, each labelled UNVERIFIED, with what would check it.

## Checked and clean

Every file you read in full and found no finding in, one line each, so a zero-findings result is
auditable.

Zero findings is a valid result. Never invent a finding to fill a count.
