# GLM Tuning — runtime setup, model economics, failure modes

Read when configuring the runtime, when a GLM-specific failure appears,
or when you want the numbers behind SKILL.md's R2/R3/R4. Not needed on a
normal run.

## 1. Models

Two models serve the whole skill:

| Model | Out speed | $/M in | $/M out | Use |
| --- | --- | --- | --- | --- |
| GLM-5.3-Flash | 113.7 tok/s | 0.15 | 0.50 | every worker lane |
| GLM-5.3 | 63.4 tok/s | 1.40 | 4.40 | main thread |

A GLM-5.3 lane is not smarter than the main thread — it is the main
model billed again. That is why R2 defaults every lane to Flash: 1.8×
the output speed, ~9× cheaper, and 3× the coding-plan quota per point.

Time to first token: GLM-5.3 3.43 s, Flash 2.34 s. Both carry a 1M
context window and 128K max output, so "read everything plausible in
round 1" is cheap in context and expensive only in rounds.

Judgment lanes on Flash. The claim verifier, the approach drafts, the
spec pre-draft and any escalated spec reviewers also run on Flash (R2):
a cost-justified choice we keep, with weaker independence. Flash and
GLM-5.3 are one model family, so a lane shares the main thread's blind
spots, and Flash is less likely to catch a subtle contradiction. Treat a
Flash verifier or reviewer as a cheap second look, not an independent
audit: check only the claims that decide the design, force different
lenses on drafts, and promote at most one lane to GLM-5.3 when its
verdict picks the approach.

## 2. Runtime setup

`glm-explorer`, `glm-researcher` and `glm-drafter` pin
`model: "account:zai-individual-coding-plan/GLM-5.3-Flash"` and
`thoughtLevel: high`. ZCode honors `thoughtLevel` only together with a
model id; without both, a lane inherits the session model and effort
`max` (the failure behind slow, over-thought lanes). Recent ZCode
sessions on this machine use the individual plan, so that prefix is the
pin. The team-plan account is a second login, not the lane default.

Calling the GLM API directly: `temperature: 1`, `top_p: 0.95`, `reasoning_effort`
per R3, `thinking.clear_thinking: false` for agent use, and `stream: true`
with `tool_stream: true`. A long request timeout covers always-on
thinking at effort `max`. R7's 8-lane hard max is the provider's
concurrent-call limit, not a client default.

## 3. Reasoning effort

`thinking.type` accepts only `"enabled"`; disabling reasoning is no
longer supported. `reasoning_effort` is `low | high | max`, default
`max`. Clients that expose an `off` setting map it to `low`.

The cost is real: thinking tokens are generated before any tool call at
the model's output rate, so `max` on a dispatch round adds seconds of
pure latency and buys nothing. Follow R3's ladder. Keep `max` for the
implementation work that follows approval — z.ai recommends it for
coding tasks.

## 4. Known failure modes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Only 1-2 of the round's calls were made | GLM emits fewer parallel calls per turn than Claude unless given a count | R4: state the count, re-issue the remainder as one batch, or push the work into Flash lanes |
| Lane ignores half the prompt | Rigid XML-tag ceremony and delegation tables are mishandled | Numbered imperative rules; tables only for reference data, never for behaviour |
| Lane returns 400 words of prose | Flash is verbose by default (≈1.3× the median output on public index runs) | Word cap plus exact output labels in the prompt; take what is usable rather than re-running for formatting |
| Every lane feels slow | Lanes running on GLM-5.3 instead of Flash | Lanes dispatch the installed Flash agent files (R2); judgment stays on the main thread |
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
| Lanes ran on the session model at effort max | Agent frontmatter had no model id, so thoughtLevel was ignored | The three lane files pin Flash and `thoughtLevel: high` |

## 5. Evidence

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

## 6. ZCode runtime

Install all eight skills with `sh install-zcode.sh` (add `--home DIR` to target another home); it
copies each `glm-<name>/` folder to `~/.zcode/skills/glm-<name>/`, the bundled agents verbatim to
`~/.zcode/agents/`, and slash commands to `~/.zcode/commands/` with the skill path filled in
(/glm-brainstorm runs context.sh from the installed skill; ZCode rejects a dynamic-shell preload). The three
brainstorming lane files pin Flash and `thoughtLevel: high` (section 2). When a model
must be named yourself, use the real ids `glm-5.3` / `glm-5.3-flash`. Installed skills, agents and
commands load only in a NEW ZCode session, not on a restart. Invoke the skill with `$glm-brainstorming`. Per-turn trigger metadata is the skill name plus a description excerpt of up to 250
characters, and a description over 1024 characters makes ZCode drop the skill — which is why the
WHEN clause sits at the front of this skill's description. Agents launched together run in parallel
and cannot spawn nested subagents, so keep the fan-out flat: width cap 8, default 8 (Live context
prints `harness: zcode` with the lane cap in force). Lane economics (R2) are unchanged: every lane
Flash, judgment on the main thread.

## 7. Mechanical verification

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

It cannot judge whether a source supports its claim; that stays on the
main thread. It never writes files and never touches the network.
