# GLM Tuning — runtime setup, model economics, failure modes

Read when configuring the runtime, when a GLM-specific failure appears,
or when you want the numbers behind SKILL.md's R2/R3/R4. Not needed on a
normal run.

## 1. Models

Two models serve the whole skill:

| Model | Out speed | $/M in | $/M out | Use |
| --- | --- | --- | --- | --- |
| GLM-5.3-Flash | 113.7 tok/s | 0.15 | 0.50 | every lane and the main thread |
| GLM-5.3 | 63.4 tok/s | 1.40 | 4.40 | not used |

A GLM-5.3 call is the same family at about 9× the price. It does not
close a decision. `decide.py score` does. Flash is 1.8× the output
speed and 3× the coding-plan quota per point.

Time to first token: GLM-5.3 3.43 s, Flash 2.34 s. Both carry a 1M
context window and 128K max output, so "read everything plausible in
round 1" is cheap in context and expensive only in rounds.

Judgment lanes on Flash. Approach drafts and escalated spec reviewers
run on Flash (R2). A claim verifier and a spec pre-draft are not
dispatched (SKILL.md R8): each completion wakes a full thinking pass.
Flash and GLM-5.3 are one model family, so a lane shares the main
thread's blind spots. Force different lenses on drafts. `decide.py
score` picks the approach. Do not promote a lane to GLM-5.3 to make
that pick.

## 2. Model and effort

Model and effort live only in the agent frontmatter. This file is the
economics and the failure table.

## 3. Known failure modes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Only 1-2 of the round's calls were made | GLM emits fewer parallel calls per turn than Claude unless given a count | R4: state the count, re-issue the remainder as one batch, or push the work into Flash lanes |
| Lane ignores half the prompt | Rigid XML-tag ceremony and delegation tables are mishandled | Numbered imperative rules; tables only for reference data, never for behaviour |
| Lane returns 400 words of prose | Flash is verbose by default (≈1.3× the median output on public index runs) | Word cap plus exact output labels in the prompt; take what is usable rather than re-running for formatting |
| Every lane feels slow | Lanes running on GLM-5.3 instead of Flash | Lanes dispatch the installed Flash agent files (R2). The main thread renders `DECISION` |
| Accuracy drifts late in a long task | Long-horizon chains compound errors | R5: wide-and-shallow lanes, ≤4 tool calls per lane, restate state before each gate |
| Cache hit rate collapses across siblings | Prefix-based caching; one changed character upstream invalidates the rest | Byte-identical shared block, slice lines last |
| Tool-call parse errors on a self-hosted server | Known GLM tool-parser bugs on some vLLM/SGLang builds | Update the serving stack; do not work around it in the prompt |
| Fabricated `path:line`, URL or quote in lane output | Flash fills gaps with plausible text and shares the main model's blind spots | Lane rules require copied paths and verbatim snippets; `check.py cites` / `check.py web` (R14) verify before citing |
| A lane hit its turn limit and returned nothing | The report was written after the last allowed turn | `maxTurns` has slack over the tool-call cap, and the lane rule says "write the report now" after 3-4 turns |
| A casual reply was treated as approval | A "sounds good" to a side question or a lane result read as a yes | Hard rule 1 (only a human reply to the design message counts) plus the "Approve this design?" item in every ask |
| Lane output cited without a check | Lane text looks authoritative once merged | R14: run `check.py` in round 2, before anything is cited |
| The design message cites a path the lane never proved | The model rewrites citations after the check | `check.py send` re-verifies every path:line in the draft |
| "sounds good" started implementation | Soft agreement read as a yes | `check.py approve`; only an approval token at the start of the reply passes |
| A bug report got a design | Misroute | `check.py route` in round 1; `ROUTE` other than `none` is binding |
| A lane invented findings to hit a minimum count | "3-6 lines" forces fabrication | The agent file says up to 6, and zero is valid |
| The path was forgotten by message 3 | Long-horizon drift; private restatement does not hold | Every message line 1 is Path or Path unchanged; `send` enforces it |
| Lanes ran on the session model at effort max | Agent frontmatter had no model id, so thoughtLevel was ignored | Model and effort live only in the agent frontmatter |

## 4. Evidence

- GLM-5.3: 1M context, 128K max output, always-on reasoning,
  `reasoning_effort` low/high/max default max, `max` recommended for
  coding — [Z.AI docs, GLM-5.3](https://docs.z.ai/guides/llm/glm-5.3) (2026-09)
- GLM-5.3-Flash: 1M context, 128K output, `temperature: 1`, `top_p:
  0.95`, `tool_stream: true`, 3× coding-plan quota, 320B total / 18B
  active, native multimodal — [Z.AI docs, GLM-5.3-Flash](https://docs.z.ai/guides/vlm/glm-5.3-flash) (2026-09)
- Speed and price: GLM-5.3 63.4 tok/s, TTFT 3.43 s, $1.40/$4.40 per M;
  Flash 113.7 tok/s, TTFT 2.34 s, $0.15/$0.50 per M, and Flash's above-median
  output volume — [Artificial Analysis](https://artificialanalysis.ai/models/glm-5-3) (2026-08)
- Reasoning cannot be disabled; `off` maps to `low` —
  [OpenClaw Z.AI provider notes](https://docs.openclaw.ai/providers/zai) (2026)
- Trained for brevity, rule-lists beat prose, tool schemas auto-injected
  ahead of your prompt, prefix-based caching, weaker on long-horizon
  chained tasks — [GLM system-prompt research](https://gist.github.com/apnea/e9dd7a650bdc3300375fffc54592f48d) (2026-05-12)
- "GLM-5.3 mis-handles several prompt conventions (e.g. rigid XML-tag
  ceremony, delegation-table adherence, tool-call formatting quirks)" —
  [oh-my-openagent issue #6923](https://github.com/code-yeongyu/oh-my-openagent/issues/6923) (2026)
- Tool-call parsing failures with GLM on Anthropic-compatible endpoints
  in some vLLM builds — [vllm issue #42400](https://github.com/vllm-project/vllm/issues/42400) (2026)

UNVERIFIED: the exact ceiling on parallel tool calls per GLM-5.3 turn.
Public reports observe as few as two in one turn without an explicit
instruction; R4 is written to hold either way.

## 5. ZCode runtime

Install all eight skills with `sh install-zcode.sh` (add `--home DIR` to target another home); it
copies each `glm-<name>/` folder to `~/.zcode/skills/glm-<name>/`, the bundled agents verbatim to
`~/.zcode/agents/`, and slash commands to `~/.zcode/commands/` with the skill path filled in
(/glm-brainstorm runs context.sh from the installed skill; ZCode has no `!` preload support and rejects a dynamic-shell preload). Model and effort live only in the agent frontmatter (section 2). When a model
must be named yourself, use the real ids `glm-5.3` / `glm-5.3-flash`. Installed skills, agents and
commands load only in a NEW ZCode session, not on a restart. Invoke the skill with `$glm-brainstorming`. Per-turn trigger metadata is the skill name plus a description excerpt of up to 250
characters, and a description over 1024 characters makes ZCode drop the skill — which is why the
WHEN clause sits at the front of this skill's description. Agents launched together run in parallel
and cannot spawn nested subagents, so keep the fan-out flat: width cap 8, default 8 (Live context
prints `harness: zcode` with the lane cap in force). Lane economics (R2) are unchanged: every lane
Flash. `decide.py score` prints the pick.

## 6. Mechanical verification

`scripts/check.py` is a stdlib-only, read-only checker. The main thread
pastes lane output into it on stdin through a heredoc, so a check costs
one Bash call and no file write. It has three modes (SKILL.md R14):

- `check.py cites [--root DIR]` verifies Code-lane FINDINGS: the file
  exists, the line exists, and the quoted snippet appears within 3 lines
  of it. Exit 1 if any cite is BAD.
- `check.py web` lints Web-lane CLAIMS: https URL, valid and recent date,
  version, quote of 25 words or less, known tier. Prints OK, WEAK or
  DROP per claim. Exit 1 if any claim is DROPped.
- `check.py spec PATH` lints a written spec: required headings, no
  placeholders or empty sections, dated https Evidence lines. Exit 1 if
  any FAIL.
- `check.py route` classifies an obvious misroute. Always exit 0.
- `check.py send` lints the draft before it is shown. Exit 1 on any FAIL.
- `check.py approve --asked design` accepts only an approval token.
  Exit 1 on no.

It does not decide whether a source supports a design. `decide.py` closes
that from the ledger. `cites`, `web`, and `send` never open a socket.
`prove` delegates the fetch to `decide.py`.
