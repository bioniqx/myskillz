# Audit report: lane 1 - z-brainstorming and z-writing-plans

## Verdict: ROOT CAUSE FOUND - at 12:04 on 2026-11-25, 9 findings are OPEN (1 found in the last pass) and 22 were FIXED by parallel work while the audit ran.

Read this first. The target moved three times during the audit. Other work committed changes to files in
this lane at 11:41-11:45 (the owned model-layer work), at 11:55-11:56 and at 11:59-12:01 (fixes that
match the findings of the first version of this report). So this report is a status snapshot, not the
state at the start: every finding below was re-checked against the files as they are at 12:04, and the
proof commands were re-run at that time. Before dispatching anything, re-run the proof commands, because
the fix work is live.

How this was checked. All 30 prose files of z-brainstorming/ and z-writing-plans/ were read in full (the
16 files that changed were read again). Scripts were read by module docstring, help text and user-visible
strings; every Python script and subcommand was run with --help. All commands ran from the repository
root with PYTHONDONTWRITEBYTECODE=1 and `python3 -B`, so nothing was written; the `check.py` and
`decide.py` reproductions read their input through stdin or /dev/stdin. The SKILL.md hygiene suite from
AGENTS.md passed on the current files: `python3 -B -m unittest discover -s _shared/tests -t _shared/tests
-p test_all_skills.py` -> "Ran 6 tests in 0.268s / OK".

Severity follows the briefing's table literally: any false or stale statement, broken reference, wrong
help text or contradiction is MAJOR; small inconsistencies are MINOR. Format change, forced by the moving
target: open findings get the full block the briefing asks for; fixed findings get one auditable table
row each (the defect as found, where it was, the line that now holds the fix, and the proof).

## Status at 12:04

| Id | Sev | Status | What | Where now |
| --- | --- | --- | --- | --- |
| F-1 | MAJOR | FIXED | FAST spec named four parts, gate needs eight | fast.md:30-33; handoff.py:848, :963-964, :978 |
| F-2 | MAJOR | PARTLY OPEN | only ZAI_API_KEY named on a deepseek pin | z-writing-plans/references/z-tuning.md:94, :121 |
| F-3 | MAJOR | PARTLY OPEN | tier "never selects a model other than Flash"; pro pin left out | z-writing-plans/references/z-tuning.md:63 |
| F-4 | MAJOR | FIXED | `atoms --check` without the required --source | z-brainstorming/SKILL.md:416 |
| F-5 | MAJOR | FIXED | "do not read fast.md" in a skill with no fast.md | z-writing-plans/SKILL.md |
| F-6 | MAJOR | FIXED | lanes called Flash although they follow the session model | 10 lines in 5 files |
| F-7 | MAJOR | FIXED | settings pointers into a z-tuning.md that holds none | fanout-playbook.md:24, :102 |
| F-8 | MAJOR | FIXED | claims gate attributed to `check.py close` | spec-document-reviewer-prompt.md:9; architectural.md:96 |
| F-9 | MAJOR | FIXED | "Write screens at reasoning_effort: low" against GUARD effort | visual-companion.md:41 |
| F-10 | MAJOR | FIXED | "It has three modes" over six bullets and ten subcommands | z-brainstorming/z-tuning.md:131 |
| F-11 | MAJOR | FIXED | agent z-programmer does not exist | z-brainstorming/SKILL.md:454 |
| F-12 | MAJOR | FIXED | "may nest three levels" against "cannot spawn nested subagents" | fanout-playbook.md |
| F-13 | MAJOR | OPEN | drafter description offers "claim check, or runner-up" | z-brainstorming/agents/z-drafter.md:3 |
| F-14 | MAJOR | FIXED | fallback list names a "verifier" | z-brainstorming/SKILL.md:476 |
| F-15 | MAJOR | FIXED | gate line says round 1 runs `check.py route` | context.sh:14; z-tuning.md |
| F-16 | MAJOR | FIXED | help says inline path is "<= 3 tasks" | plan_tool.py:11 |
| F-17 | MAJOR | FIXED | "No speed or price numbers are pinned" over a table of them | z-brainstorming/z-tuning.md:27 |
| F-18 | MAJOR | OPEN | "a body-size cap is unverified" | z-writing-plans/references/z-tuning.md:111 |
| F-19 | MAJOR | PARTLY OPEN | two-model enumerations; one log line left | z-writing-plans/CHANGELOG.md:47 |
| F-20 | MAJOR | FIXED | "deep-research command" does not exist | research-playbook.md |
| F-21 | MINOR | FIXED | "did not print PACE: fast" where PACE full is meant | z-brainstorming/SKILL.md:416 |
| F-22 | MINOR | FIXED | send example lacks --ledger for a design message | z-brainstorming/SKILL.md:405 |
| F-23 | MINOR | FIXED | "four questions" over five bullets | z-plan-reviewer-prompt.md:20 |
| F-24 | MINOR | FIXED | "report APPROVED" against "Status: Approved" | z-plan-reviewer.md:22 |
| F-25 | MINOR | FIXED | "2-5 pattern files"; the limit is 4 | z-writing-plans/SKILL.md:56 |
| F-26 | MINOR | FIXED | main thread told to keep "the effort pinned in the agent file" | architectural.md:104 |
| F-27 | MINOR | OPEN | CHANGELOG: setup --harness, ANTHROPIC_BASE_URL | z-writing-plans/CHANGELOG.md:117, :128-129 |
| F-28 | MINOR | FIXED | five docs over 100 lines without a contents list | all five |
| F-29 | MINOR | OPEN | speed, credit and alias-map facts without a date | z-writing-plans/references/z-tuning.md:35-40, :68-70 |
| F-30 | MINOR | OPEN | "`~/.zcode/*.json`" for three named files | z-writing-plans/references/z-tuning.md:101 |
| F-31 | MAJOR | OPEN (new) | Evidence "none" or "n/a" fails as "section is empty" | z-brainstorming/scripts/check.py:407-408, :413 |

Every open item sits in one of four files: z-brainstorming/agents/z-drafter.md, z-brainstorming/scripts/check.py,
z-writing-plans/references/z-tuning.md, z-writing-plans/CHANGELOG.md.

## Findings

### Open findings

#### F-2 (rest) MAJOR
- Where: z-writing-plans/references/z-tuning.md:94 and :121 (the SKILL.md and plan_tool.py parts are fixed)
- Quote: "export ZAI_API_KEY=<GLM Coding Plan key>          # or ANTHROPIC_AUTH_TOKEN"
- Criterion: 7 Internal contradiction; 4 Truthfulness
- Why it is a defect: On a lane pinned to deepseek the client never reads ZAI_API_KEY (zai_client.py:138-146). SKILL.md:230-235 now names both keys and `doctor` now prints DEEPSEEK_API_KEY on a deepseek pin, so the tuning file contradicts both the skill and the script's own hint, and its failure row still sends a deepseek user to export the wrong key.
- Reproduce: `grep -n -E 'export ZAI_API_KEY|then export' z-writing-plans/references/z-tuning.md` -> "94:export ZAI_API_KEY=<GLM Coding Plan key>          # or ANTHROPIC_AUTH_TOKEN" and "121:| `LANE agent` when you expected api | no key found | `doctor`, then export `ZAI_API_KEY` |". `env -i PATH="$PATH" HOME=/nonexistent GLM_FLASH=deepseek python3 -B z-writing-plans/scripts/plan_tool.py doctor` -> "export DEEPSEEK_API_KEY=<your DeepSeek key>"
- Fix: after :94 add the line `export DEEPSEEK_API_KEY=<DeepSeek key>   # when ~/.zcode/z-flash says deepseek`. :121 "then export `ZAI_API_KEY`" -> "then export `ZAI_API_KEY` (glm pin) or `DEEPSEEK_API_KEY` (deepseek pin)".
- Files the fix touches: z-writing-plans/references/z-tuning.md

#### F-3 (rest) MAJOR
- Where: z-writing-plans/references/z-tuning.md:63 (the SKILL.md part is fixed)
- Quote: "Every tier is GLM-5.3-Flash, or deepseek-flash when `~/.zcode/z-flash` says deepseek"
- Criterion: 7 Internal contradiction; 4 Truthfulness
- Why it is a defect: SKILL.md:131-132 and :203-204 now say the lane is the pinned flash model or the pinned pro id, and the script does that: resolve_http_model returns the pro id for every tier under a pro pin. The tuning file still says every tier is a flash model.
- Reproduce: a `python3 -B` heredoc with GLM_FLASH=glm-5.3 that imports plan_tool and prints flash_pin.resolve_http_model(GLM[t][0]) -> "{'light': 'glm-5.3', 'std': 'glm-5.3', 'deep': 'glm-5.3'}" (run at 11:53, before the 11:55 edit; flash_pin.py did not change in that edit)
- Fix: append " A pro pin word (glm-5.3, glm-5.4, deepseek-v4-pro) sends every tier to that model."
- Files the fix touches: z-writing-plans/references/z-tuning.md

#### F-13 MAJOR
- Where: z-brainstorming/agents/z-drafter.md:3
- Quote: "one assigned lens, approach draft, claim check, or runner-up"
- Criterion: 7 Internal contradiction
- Why it is a defect: SKILL.md:161-162 says "Do not dispatch a claim verifier, a runner-up, or a spec pre-draft (R8)" and :239 repeats it, but the agent's own description offers the drafter for a "claim check" and a "runner-up". The owned rewrite at 11:41 removed "Flash lane" from this line and left this phrase.
- Reproduce: `grep -n 'claim check' z-brainstorming/agents/z-drafter.md` -> "3:description: \"Lane for z-brainstorming, on the session model: one assigned lens, approach draft, claim check, or runner-up. No repo writes.\""
- Fix: "one assigned lens, approach draft, claim check, or runner-up." -> "one assigned lens or approach draft."
- Files the fix touches: z-brainstorming/agents/z-drafter.md

#### F-18 MAJOR
- Where: z-writing-plans/references/z-tuning.md:111
- Quote: "a body-size cap is unverified."
- Criterion: 4 Truthfulness (stale)
- Why it is a defect: docs/skill-criteria.md:16 states the verified limit: "The SKILL.md body is **truncated at 100KB** when loaded."
- Reproduce: `sed -n '16p' docs/skill-criteria.md` -> "- The SKILL.md body is **truncated at 100KB** when loaded. Target **under 500 lines**; push detail"
- Fix: "a body-size cap is unverified." -> "the body is truncated at 100KB (docs/skill-criteria.md section 1)."
- Files the fix touches: z-writing-plans/references/z-tuning.md

#### F-19 (rest) MAJOR, lowest value of the open items
- Where: z-writing-plans/CHANGELOG.md:47 (plan_tool.py:3 and z-brainstorming/z-tuning.md are fixed)
- Quote: "Target: GLM-5.3 and GLM-5.3-Flash, running in ZCode."
- Criterion: 3 Six-model matrix; 4 Truthfulness
- Why it is a defect: It names two models and one harness where the skill declares six and two. It is a log line for the v9 release, so leaving it as a historical statement is defensible.
- Reproduce: `grep -n 'Target' z-writing-plans/CHANGELOG.md` -> "47:Target: GLM-5.3 and GLM-5.3-Flash, running in ZCode."
- Fix: "Target: GLM-5.3 and GLM-5.3-Flash, running in ZCode." -> "Target at the v9 release: GLM-5.3 and GLM-5.3-Flash, running in ZCode."
- Files the fix touches: z-writing-plans/CHANGELOG.md

#### F-27 MINOR
- Where: z-writing-plans/CHANGELOG.md:117 and :128-129 (and :35)
- Quote: "`setup [--harness zcode|claude] [--apply]`"
- Criterion: 5 Broken reference (flag and environment variable)
- Why it is a defect: `setup` has no `--harness` flag, and the script never reads ANTHROPIC_BASE_URL (plan_tool.py "Never reads ANTHROPIC_BASE_URL."; the base URL comes from PLAN_BASE_URL, ZAI_BASE_URL or GLM_BASE_URL). :35 says SKILL.md R9 scopes ANTHROPIC_BASE_URL, and R9 does not mention it. MINOR because the file is a dated log, though :123-132 reads as present-tense instructions.
- Reproduce: `python3 -B z-writing-plans/scripts/plan_tool.py setup --help | head -1` -> "usage: plan_tool.py setup [-h] [--apply]"; `grep -n -E '\[--harness|export ANTHROPIC_BASE_URL' z-writing-plans/CHANGELOG.md` -> :117 and :129 (the historical mentions at :35 and :37 are left alone)
- Fix: :117 -> "`setup [--apply]`"; :128-129 drop "and / `export ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`".
- Files the fix touches: z-writing-plans/CHANGELOG.md

#### F-29 MINOR
- Where: z-writing-plans/references/z-tuning.md:35-40 and :68-70
- Quote: "| Throughput, TTFT | ~63 tok/s, ~3.4 s | ~114 tok/s, ~2.3 s |"
- Criterion: 1 Hard limits, body (docs/skill-criteria.md section 5 "Time-sensitive facts without a staleness note")
- Why it is a defect: Throughput, TTFT, credit multipliers, quota and the z.ai alias map carry no date and no source. The z-brainstorming twin dates the same numbers (its section 4, "(2026-08)"). The only dated line in this file (:25) is the GLM 5.4 note.
- Reproduce: `grep -n -E '20[0-9][0-9]' z-writing-plans/references/z-tuning.md` -> "25:2026-11-25: 1M context, 128K max output, thinking mode, tool calling," (one line)
- Fix: under the table at :40 add "Measured 2026-08; sources in z-brainstorming/z-tuning.md section 4. Re-check before tuning."; after :70 add "(z.ai route as of 2026-10.)"
- Files the fix touches: z-writing-plans/references/z-tuning.md

#### F-30 MINOR
- Where: z-writing-plans/references/z-tuning.md:101
- Quote: "(its `api-key` field) and `~/.zcode/*.json`"
- Criterion: 5 Broken reference (path is not what the prose says)
- Why it is a defect: The client reads three named files under ~/.zcode (settings.json, auth.json, config.json), plus two under ~/.claude and ~/.zcode/v2/credentials.json; it does not read every *.json there.
- Reproduce: `sed -n '70,72p' z-writing-plans/scripts/zai_client.py` -> "KEY_FILES = (\"~/.claude/settings.json\", \"~/.claude/settings.local.json\",", "\"~/.zcode/v2/credentials.json\", \"~/.zcode/settings.json\",", "\"~/.zcode/auth.json\", \"~/.zcode/config.json\")"
- Fix: "`~/.zcode/*.json`" -> "`~/.zcode/settings.json`, `~/.zcode/auth.json` and `~/.zcode/config.json`".
- Files the fix touches: z-writing-plans/references/z-tuning.md

#### F-31 MAJOR (found in the last pass, after the F-1 fix)
- Where: z-brainstorming/scripts/check.py:407-408 against :413
- Quote: "if len(re.sub(r"\\s", "", body)) < 6:" against "re.search(r"\\b(none|n/a|repo-internal)\\b", body, re.I)"
- Criterion: 6 Script defect reachable from the skill's own steps; 7 Internal contradiction
- Why it is a defect: `check.py spec` exempts an Evidence section that says none, n/a or repo-internal from the URL and date rules, but the emptiness test runs first and needs 6 non-space characters; "none" has 4 and "n/a" has 3. A FAST spec does no research, so its Evidence section is naturally "none", and the gate answers "FAIL Evidence - section is empty", a repair line that points at the wrong problem. The FAST step now names the eight headings, so this is the next likely FAIL on that path.
- Reproduce: `python3 -B z-brainstorming/scripts/check.py spec /dev/stdin <<'EOF'` with an eight-heading spec whose Evidence body is `none` -> "FAIL Evidence - section is empty", "RESULT spec fail=1 warn=0", exit 1. Same spec with `n/a` -> the same. With `repo-internal`, or with `None: no external claim.`, -> "RESULT spec fail=0 warn=0" and the HANDOFF block.
- Fix: check.py:407 `if len(re.sub(r"\s", "", body)) < 6:` -> `if len(re.sub(r"\s", "", body)) < 6 and not (name == "Evidence" and re.search(r"\b(none|n/a|repo-internal)\b", body, re.I)):`
- Files the fix touches: z-brainstorming/scripts/check.py

### Fixed findings (record)

Each row: the defect as found, the criterion it broke, where the fix is now, and the proof run at 12:03.

| Id | Defect as found | Criterion | Fix now | Proof at 12:03 |
| --- | --- | --- | --- | --- |
| F-1 | FAST spec "(goal, files, acceptance, out of scope)" failed `check.py spec` with 7 FAILs; FAST is the default mode | 7, 6 | fast.md:30-33; handoff.py:848, :963-964, :978 name the eight headings | eight-heading spec -> "RESULT spec fail=0" (Evidence as a sentence; see F-31) |
| F-4 | "then `atoms --check`" exits 2: --source is required | 5, 6 | z-brainstorming/SKILL.md:416 "`atoms --check --source <the request file>`" | grep shows the new text |
| F-5 | "do not read `fast.md`" in z-writing-plans, which has none | 5 | z-writing-plans/SKILL.md | `grep -n 'fast\.md'` -> no output |
| F-6 | "Flash lanes" and "every lane Flash" against "follow the session model" | 3, 7 | SKILL.md:137, :177, :416; z-tuning.md:124-125; fanout, research, visual docs | `grep -n -E 'Flash lanes?\|on Flash \(R2\)\|instead of Flash'` -> no output |
| F-7 | "settings in `z-tuning.md`": the file holds none | 5 | fanout-playbook.md:24 (OC_MAX_LANES), :102 (ZCode permission settings) | grep shows the new text |
| F-8 | "`check.py close` already gated the claims": intake does | 4, 7 | spec-document-reviewer-prompt.md:9; architectural.md:96 | grep shows intake |
| F-9 | "Write screens at `reasoning_effort: low`" against GUARD effort | 7 | visual-companion.md:41 "Keep the session effort for screens." | grep shows the new text |
| F-10 | "It has three modes" over six bullets and ten subcommands | 7, 4 | z-tuning.md:131 "Its modes (SKILL.md R14):" | grep shows the new text |
| F-11 | agent "z-programmer" is unknown to borrow | 5 | SKILL.md:454 "z-programmer-lite" | grep shows the new text |
| F-12 | "They may nest three levels" against "cannot spawn nested subagents" | 7 | fanout-playbook.md (sentence removed); z-tuning.md:123 stays | `grep -n 'nest'` -> one line, z-tuning.md:123 |
| F-14 | fallback list "(Web, drafts, verifier)" against R2 and R8 | 7 | SKILL.md:476 "(Web, drafts)" | `grep -n -i verifier` -> :161, :239 only |
| F-15 | gate line "round 1 includes check.py route" | 7, 4 | context.sh:14 "gate: open already ran route; ..." | grep shows the new text |
| F-16 | help "inline path (<= 3 tasks)"; the threshold is N <= 1 and unenforced | 5, 7 | plan_tool.py:11 "inline path (N <= 1 task, or PACE short / fast)" | --help shows the new text |
| F-17 | "No speed or price numbers are pinned for these tiers" over a table of them | 7 | z-tuning.md:27 | grep shows the new text |
| F-20 | "run a deep-research command": no such command anywhere | 5 | research-playbook.md | `grep -n 'deep-research'` -> no output |
| F-21 | "when the prelude did not print `PACE: fast`" where PACE full is meant | 7 | SKILL.md:416 "printed `PACE: full`" | grep shows the new text |
| F-22 | send example without --ledger fails on a design message | 5 | SKILL.md:405 with --ledger and --pick | grep shows the new text |
| F-23 | "four questions only" over five bullets | 7 | z-plan-reviewer-prompt.md:20 "five questions only" | grep shows the new text |
| F-24 | "report APPROVED" against "Status: Approved" | 1 | z-plan-reviewer.md:22 "reply `Status: Approved`" | grep shows the new text |
| F-25 | "2-5 pattern files"; the default limit is 4 | 4 | z-writing-plans/SKILL.md:56 "up to 4 pattern files" | grep shows the new text |
| F-26 | "effort pinned in the agent file" for the main thread | 7, 1 | architectural.md:104 "pinned for this session" | grep shows the new text |
| F-28 | five docs over 100 lines without a contents list | 1 | contents lists in architectural.md, fanout-playbook.md, research-playbook.md, visual-companion.md, z-tuning.md | each list matches its headings in name and order |

The new contents lists omit the section numbers that other files cite (for example "architectural.md
section 4" in z-brainstorming/SKILL.md). The headings keep their numbers, so the citations still resolve;
this is noted, not counted as a finding.

## Ready-to-dispatch fix slices

Four slices cover everything that is open; their files are disjoint. The 22 fixed findings need no
slice; their proof commands are in the table above.

- Slice 1 - z-writing-plans/references/z-tuning.md - F-2 (rest), F-3 (rest), F-18, F-29, F-30.
  Proof: `grep -n -E 'then export .ZAI_API_KEY. \||body-size cap is unverified|zcode/\*\.json' z-writing-plans/references/z-tuning.md` -> no output; `grep -c 'DEEPSEEK_API_KEY' z-writing-plans/references/z-tuning.md` -> at least 2; `grep -n 'pro pin word' z-writing-plans/references/z-tuning.md` -> line 63; `grep -c -E 'Measured 20|as of 20' z-writing-plans/references/z-tuning.md` -> at least 1.
- Slice 2 - z-writing-plans/CHANGELOG.md - F-19 (rest), F-27.
  Proof: `grep -n -E '\[--harness|export ANTHROPIC_BASE_URL' z-writing-plans/CHANGELOG.md` -> no output; `grep -n 'Target at the v9 release' z-writing-plans/CHANGELOG.md` -> one line.
- Slice 3 - z-brainstorming/agents/z-drafter.md - F-13.
  Proof: `grep -c -E 'claim check|runner-up' z-brainstorming/agents/z-drafter.md` -> 0; `grep -c '^model:' z-brainstorming/agents/z-drafter.md` -> 0. Reinstall the agent copy afterwards (`setup --apply` or the installer).
- Slice 4 - z-brainstorming/scripts/check.py - F-31.
  Proof: the F-31 reproduction with Evidence `none` -> "RESULT spec fail=0 warn=0"; with Evidence empty (blank line) -> "FAIL Evidence - section is empty" still; the F-1 reproduction with the four-part spec -> "RESULT spec fail=7", so the gate is not weakened; the full suite from AGENTS.md passes.

## Not verified

- UNVERIFIED: model behaviour behind R4 and R5 of z-brainstorming/SKILL.md ("Flash emits fewer parallel tool calls per turn", "Flash loses accuracy on long chains") and the failure table in z-tuning.md. The dated evidence there is about GLM-5.3, not about DeepSeek V4.1 Flash or Claude Sonnet 5.5. A measurement on each of the six models would check it.
- UNVERIFIED: the facts the 11:41 commit added for GLM 5.4 (z-tuning.md in both skills, and the screenshot paragraph of visual-companion.md) and the sentence "the Claude tier is the harness default when no GLM model is configured" (both z-tuning.md files). Reading the vendor model page, and a ZCode session with no GLM model configured, would check them.
- UNVERIFIED: the capacity facts in fanout-playbook.md section 0 ("8 running at once", the ninth `Agent` call failing with "Concurrent subagent limit reached", subagents having WebSearch/WebFetch but not AskUserQuestion) and "width cap 8" in z-tuning.md section 5. A live nine-agent dispatch in a ZCode session would check it.
- UNVERIFIED: "Installed skills, agents and commands load only in a NEW ZCode session, not on a restart" (z-brainstorming/z-tuning.md section 5). An install followed by a restart in a running session would check it.
- UNVERIFIED: the invocation form `$z-brainstorming` (z-brainstorming/z-tuning.md section 5) and `$z-writing-plans` (z-writing-plans/references/z-tuning.md:111). Neither the ZCode guide (zcode-guide 0.3.0) nor a byte scan of the runtime showed a `$name` form; this session's own tool list offers the Skill tool and `/name`. A live ZCode session would check it.
- UNVERIFIED: "Subagents ... cannot spawn further subagents" (z-writing-plans/references/z-tuning.md:112-113) for general-purpose threads. The only observation is that this investigator thread's tool list has no Agent tool.
- UNVERIFIED: "ZCode can import a Claude- or Codex-format skill directory directly from Settings, by symlink or copy" (z-writing-plans/references/z-tuning.md:113-115).
- UNVERIFIED: the upstream numbers in spec-document-reviewer-prompt.md:5-8 ("identical quality scores", "~25 minutes", "3-5 real bugs per run").
- UNVERIFIED: body-rules.md rule 9 ("exactly one `git commit` per task") was not traced in plan_tool.py; rules 1-8 and the banned strings were.
- UNVERIFIED: the fixed findings were checked by their proof command only. The edits that fixed them were not reviewed line by line, and files in this lane were still changing at 12:01.
- [OUT-OF-SCOPE] docs/skill-criteria.md:20-21 lists only name, description, when_to_use, license and metadata as recognized keys, while ZCode's own guide documents `argument-hint` and `allowed-tools` for commands (zcode-guide 0.3.0, diagnosing-commands/SKILL.md:34). z-brainstorming/SKILL.md and commands/z-brainstorm.md rely on both.
- [OUT-OF-SCOPE], now closed: the two vendored-file items of the first report version are fixed in _shared (decide.py no longer prints "one Flash call"; the handoff.py NEXT strings name the eight headings). plan_tool.py:2160 (owned line) was not re-checked after the 11:55 edit.

## Checked and clean

Owned items of the briefing, verified as landed in the current files:

- Both `models:` lines list six ids (z-brainstorming/SKILL.md:21, z-writing-plans/SKILL.md:6); both z-tuning.md session-models tables list six rows; both titles say six.
- Both agent descriptions read "Lane for z-brainstorming, on the session model" (z-design-breaker.md:3, z-drafter.md:3).
- z-brainstorming/z-tuning.md counts eleven installed skills; its section 2 no longer says the agent frontmatter holds the model; the GUARD flash line lists six (handoff.py:281).
- The vendored copies are byte-identical to _shared/ on the current files (cmp on handoff.py and decide.py in both skills).

Prose files read in full with no finding of their own:

- z-brainstorming/agents/z-explorer.md - no model line; "Max 4 tool calls" matches SKILL.md R5.
- z-brainstorming/agents/z-researcher.md - no model line; "verbatim quote of 25 words or less" matches check.py MAX_QUOTE_WORDS = 25.
- z-brainstorming/agents/z-design-breaker.md - no model line.
- z-brainstorming/commands/z-brainstorm.md - `{{SKILL_DIR}}` is filled by install-zcode.sh:129; the named flags match `handoff.py open --help`.
- z-brainstorming/CHANGELOG.md - dated log; its 10.11 claim that the companions speak of the session model is true on the current files.
- z-writing-plans/agents/z-plan-task-writer.md - no model line; reply format matches z-task-writer-prompt.md:24.
- z-writing-plans/agents/z-plan-task-writer-deep.md - no model line; same reply format.
- z-writing-plans/commands/z-plan.md - `{{SKILL_DIR}}` is filled; sections R0 to R9 exist in SKILL.md.
- z-writing-plans/references/body-rules.md - its banned strings match the placeholder and portability lists in plan_tool.py.
- z-writing-plans/z-task-writer-prompt.md - loaded by plan_tool.py; its reply format matches the writer agent files.

Scripts, read by docstring, help text and user-visible strings, with no finding of their own:

- z-brainstorming/scripts/ask.py - subcommands wait, cancel, mode, fast, chain; flags and default paths (.brainstorm/drafts/mode.json, chain.json, ask.cancel; timeout 900) match SKILL.md R6, R13 and fast.md.
- z-brainstorming/scripts/start-server.sh, stop-server.sh, server.cjs, helper.js, frame-template.html - every flag (--project-dir, --host, --url-host, --idle-timeout-minutes, --open, --foreground, --background), path, JSON key, events rule and CSS class named in visual-companion.md exists.
- z-brainstorming/scripts/decide.py and handoff.py, z-writing-plans/scripts/decide.py, handoff.py, zai_client.py, flash_pin.py - byte-identical to _shared/; every subcommand the two SKILL.md files name exists.

Hard limits, both SKILL.md files: descriptions are 980 and 294 characters with the WHEN clause inside the first 250; `name` equals the directory name; the hygiene suite passes 6 of 6. The `__pycache__` folders under both scripts/ directories are untracked and ignored (.gitignore:2-3), so they are not a repository defect.

Ruled out during the audit:

- `brief [SPEC] [--thorough]` is a valid form: the brief parser takes `rest` as an argparse REMAINDER and the brief handler reads the flag from it.
- `plan_tool.py check` does print the `HANDOFF z-dev-team` block under a fast chain, through handoff.advance_block; `check.py spec` prints `HANDOFF z-writing-plans` with a `NEXT-EXTRA:` line (seen in the F-31 run).
- `setup --apply` "copied verbatim" is true today: the agent files carry no model line and stamp_agent only drops model lines.
- `close` "optional ## DRAFT" in the help against "Do not pass ## DRAFT here" in SKILL.md is not a contradiction: check.py states the same rule as SKILL.md.
- "`decide.py score` prints DECISION" against "`close` prints DECISION" is not a contradiction: close runs break plus score.
- `Explore`, `general-purpose`, `subagent_type`, `run_in_background`, `SendMessage`, `TaskCreate`, `thoughtLevel`, `maxTurns`, `disallowedTools`, `injectAgentsMd` and "Base directory for this skill" all occur in the ZCode runtime (/Applications/ZCode.app/Contents/Resources/glm/zcode.cjs, byte scan).
- `z-debug-worker`, `z-investigator` and `z-spot-reviewer`, their 12-line verdict and their report directories match the BORROW rows in handoff.py.
- z-researcher "Max 5 tool calls" against R5 "never let a lane chain more than 4 tool calls" was not counted: the five calls are two or three parallel batches, not a chain.

```json
{"fixes": [
  {"id": "S1", "title": "z-writing-plans z-tuning.md: DeepSeek key lines, pro pin, 100KB limit, dated numbers, key files", "files": ["z-writing-plans/references/z-tuning.md"], "criteria": ["grep -n -E 'then export .ZAI_API_KEY. \\||body-size cap is unverified|zcode/\\*\\.json' z-writing-plans/references/z-tuning.md prints nothing", "grep -c 'DEEPSEEK_API_KEY' z-writing-plans/references/z-tuning.md is at least 2", "grep -n 'pro pin word' z-writing-plans/references/z-tuning.md prints line 63", "grep -c -E 'Measured 20|as of 20' z-writing-plans/references/z-tuning.md is at least 1"], "deps": []},
  {"id": "S2", "title": "z-writing-plans CHANGELOG: stale setup flag, base-URL export, target line", "files": ["z-writing-plans/CHANGELOG.md"], "criteria": ["grep -n -E '\\[--harness|export ANTHROPIC_BASE_URL' z-writing-plans/CHANGELOG.md prints nothing", "grep -n 'Target at the v9 release' z-writing-plans/CHANGELOG.md prints one line"], "deps": []},
  {"id": "S3", "title": "z-drafter agent description drops claim check and runner-up", "files": ["z-brainstorming/agents/z-drafter.md"], "criteria": ["grep -c -E 'claim check|runner-up' z-brainstorming/agents/z-drafter.md prints 0", "grep -c '^model:' z-brainstorming/agents/z-drafter.md prints 0"], "deps": []},
  {"id": "S4", "title": "check.py spec: an exempt Evidence section is not 'empty'", "files": ["z-brainstorming/scripts/check.py"], "criteria": ["check.py spec on the eight-heading spec with Evidence 'none' prints RESULT spec fail=0", "check.py spec with an empty Evidence section still prints FAIL Evidence - section is empty", "check.py spec on the four-part spec still prints RESULT spec fail=7", "the full suite in AGENTS.md passes"], "deps": []}
]}
```
