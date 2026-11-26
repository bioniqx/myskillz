# Audit report: lane 3 - six skills

Base directory for every path below: /Users/yamazaki-ethan/Documents/Projects/mine/skillz/ (paths are
written as z-skills/<skill>/...). Line numbers were re-verified against the working tree at 12:13 on
2026-11-25 (HEAD eb8dabe). Sibling lanes committed to this repo during the audit; the last changes
inside the six folders were the two references/z-tuning.md files (11:55:58) and the re-synced
vendored scripts (12:03:18, one docstring line of zai_client.py). Grep the quoted text again
before editing.

Quotes are verbatim with non-ASCII characters folded to ASCII: -> for the right arrow, -- for the
em dash, <= and >= for the inequality signs, ~ for the approximately sign, ... for the ellipsis,
"section" for the section sign. Reproduce commands ran from inside z-skills/ with
PYTHONDONTWRITEBYTECODE=1. Short names used below: AUD = python3
z-requirements-code-audit/scripts/audit.py; DBG = python3
z-systematic-debugging/scripts/debug_tool.py; K = the fake key zai-0123456789abcdef0123456789.
"no output" means the command printed nothing.

Result: 26 findings, 0 BLOCKER, 17 MAJOR, 9 MINOR.

## Findings

### F-1 MAJOR
- Where: z-skills/z-requirements-code-audit/scripts/audit.py:2297 (consumer: scripts/handoff.py:1245, a vendored copy of _shared/handoff.py)
- Quote: "No API key -> `brief` reports `lane agent` and the pipeline becomes `A plan`" (SKILL.md:199)
- Other side: audit.py:2297 prints `print("lane      %s  (%s)" % (lane, why))`; handoff.py:1245 tests `agent_lane = "lane agent" in (out or "")`
- Criterion: 6 Script defect reachable from the skill's own steps; 7 Internal contradiction
- Why it is a defect: `brief` pads the label to `lane      agent` (six spaces), so the substring test is always False. On the no-key lane with a spec of at most 120 lines the last, binding NEXT line is then the api-lane one (handoff.py:1252-1257: "Then one run call ... Do not dispatch a subagent"), although SKILL.md R9 requires `A plan` and a subagent dispatch. `run` falls through to `plan` (audit.py:2738-2741), so the call is not lost, but the binding instruction contradicts the dispatch list it prints.
- Reproduce: `python3 -c "lane,why='agent','no API key found -- falling back to subagents'; line='lane      %s  (%s)'%(lane,why); print(repr(line)); print('agent_lane =', 'lane agent' in line)"` -> `'lane      agent  (no API key found -- falling back to subagents)'` and `agent_lane = False`
- Fix: audit.py:2297 -> `print(("lane      %s" if lane == "api" else "lane %s") % lane + "  (%s)" % why)`. Alternative for lane 2, in _shared/handoff.py:1245: `re.search(r"(?m)^lane\s+agent\b", out or "")`.
- Files the fix touches: z-skills/z-requirements-code-audit/scripts/audit.py

### F-2 MAJOR
- Where: z-skills/z-requirements-code-audit/SKILL.md:63-64
- Quote: "`audit.py run` opens up to 8 threads, each one request straight at the GLM endpoint."
- Criterion: 4 Truthfulness; 2 AGENTS.md ("never hardcode one provider or one harness")
- Why it is a defect: under a `deepseek` pin every request goes to https://api.deepseek.com (zai_client.py:40-51, flash_pin.py:17), so the sentence is false for a deepseek-flash and a DeepSeek V4 Pro session.
- Reproduce: `env HOME=/nonexistent GLM_FLASH=deepseek ZAI_API_KEY=$K AUD doctor | sed -n 4,6p` -> `api key     NOT FOUND -- set DEEPSEEK_API_KEY; without it the skill uses the subagent lane`, `base url    https://api.deepseek.com  (deepseek)`, `route       openai -> https://api.deepseek.com/chat/completions`
- Fix: "each one request straight at the GLM endpoint" -> "each one request straight at the session model's provider endpoint (z.ai or DeepSeek, by the flash pin)"
- Files the fix touches: z-skills/z-requirements-code-audit/SKILL.md

### F-3 MAJOR
- Where: z-skills/z-requirements-code-audit/SETUP.md:27 (also SETUP.md:1; scripts/audit.py:3821-3823 `SETUP_ENV`, :2198, :3872)
- Quote: "export ZAI_API_KEY=<your GLM Coding Plan key>"
- Criterion: 4 Truthfulness; 2 AGENTS.md ("never hardcode one provider or one harness")
- Why it is a defect: the frontmatter declares `deepseek-flash`, but under a `deepseek` pin `find_key()` reads only `DEEPSEEK_API_KEY`, `DEEPSEEK_KEY` or the deepseek block of ~/.zcode/v2/provider_config.json (zai_client.py:138-146). A DeepSeek session that follows SETUP.md, or the block `audit.py setup` prints, stays on the agent lane.
- Reproduce: `env HOME=/nonexistent ZAI_API_KEY=$K AUD doctor | sed -n 4p` -> `api key     found (env:ZAI_API_KEY)`; the same command with `GLM_FLASH=deepseek` added -> `api key     NOT FOUND -- set DEEPSEEK_API_KEY; without it the skill uses the subagent lane`
- Fix: SETUP.md, after line 29, add: "`deepseek` pin in `~/.zcode/z-flash`: `export DEEPSEEK_API_KEY=<your DeepSeek key>` instead; the client ignores `ZAI_API_KEY` there. `audit.py doctor` names the key it needs." SETUP.md:1 "(GLM edition)" -> "(z.ai and DeepSeek)". audit.py:3821-3823 `SETUP_ENV`: add the comment line `# deepseek pin: export DEEPSEEK_API_KEY=<your DeepSeek key> instead`. audit.py:2198 "Set ZAI_API_KEY (GLM Coding Plan)" -> "Set ZAI_API_KEY (GLM Coding Plan) or DEEPSEEK_API_KEY (deepseek pin)". audit.py:3872 "(GLM edition)" -> "(z.ai and DeepSeek)".
- Files the fix touches: z-skills/z-requirements-code-audit/SETUP.md, z-skills/z-requirements-code-audit/scripts/audit.py

### F-4 MAJOR
- Where: z-skills/z-requirements-code-audit/SETUP.md:47; references/z-tuning.md:67-69; references/z-tuning.md:35
- Quote: "a live ping to both models, and the request shape the gateway accepted."
- Other side: z-tuning.md:67 "**Request-shape discovery.** If the gateway refuses `reasoning_effort`, `thinking` or `cache_control`, the"; z-tuning.md:35 "z.ai recommends `thinking.clear_thinking: false` | sent on every request"
- Criterion: 4 Truthfulness
- Why it is a defect: no script implements request-shape discovery or sends `clear_thinking`. The client always posts `reasoning_effort` (zai_client.py:309) and `doctor` prints no shape line (audit.py:3786-3818; output under F-2 and F-6). Three statements describe behaviour the code does not have.
- Reproduce: `grep -n -i 'clear_thinking\|cache_control\|request.shape' z-requirements-code-audit/scripts/audit.py z-requirements-code-audit/scripts/zai_client.py z-requirements-code-audit/scripts/decide.py` -> no output
- Fix: SETUP.md:47 delete ", and the request shape the gateway accepted". z-tuning.md:67-69 -> "5. **Transport.** Retries, 429 backoff and the shared request width live in the vendored `zai_client.py`; `audit.py` only re-asks a reply that stopped at the token cap, with a larger cap." (audit.py:1174-1178, 1214-1216). z-tuning.md:35 delete the `clear_thinking` row.
- Files the fix touches: z-skills/z-requirements-code-audit/SETUP.md, z-skills/z-requirements-code-audit/references/z-tuning.md

### F-5 MAJOR
- Where: z-skills/z-requirements-code-audit/references/schemas.md:41-45
- Quote: `"searched":["second-pass queries"],"reason":"<=200 chars"}`
- Criterion: 4 Truthfulness; 7 Internal contradiction
- Why it is a defect: the documented verdict object has no `attack` key, while `VERIFY_SCHEMA` (audit.py:1032-1039), prompt rule 8 ("attack is required", audit.py:1054) and agents/z-rca-verifier.md:23 all require it; `check` fails such an item with "has no reproduced attack" (audit.py:3353).
- Reproduce: `grep -c '"attack"' z-requirements-code-audit/references/schemas.md` -> `0`; `grep -n '"attack":{"kind"' z-requirements-code-audit/scripts/audit.py` -> `1037:    '"attack":{"kind":"COUNTEREXAMPLE|NO-BREAK","path":"<excerpt path>","lines":"10-12",'`
- Fix: schemas.md:44 -> `  "searched":["second-pass queries"],"reason":"<=200 chars",` and a new line 45 `  "attack":{"kind":"COUNTEREXAMPLE|NO-BREAK","path":"...","lines":"10-12","quote":"<verbatim substring of those lines>"}}`. After the block add: "`attack` is required: a status closes only when its quote reproduces in the cited lines, otherwise the item stays open for `adjudicate --set`."
- Files the fix touches: z-skills/z-requirements-code-audit/references/schemas.md

### F-6 MINOR
- Where: z-skills/z-requirements-code-audit/SETUP.md:34 (also SETUP.md:3, :37-38, :47)
- Quote: "(`apiKey`, `ANTHROPIC_AUTH_TOKEN`, `token`, `api-key`, ...), never by"
- Criterion: 5 Broken reference; 4 Truthfulness
- Why it is a defect: four SETUP.md sentences do not match the scripts. (a) `token` is not a key field: `KEY_FIELDS` (zai_client.py:68-69) lists `ZAI_API_KEY, GLM_API_KEY, ANTHROPIC_AUTH_TOKEN, apiKey, api_key, key, api-key`. (b) Line 47 "a live ping to both models": a `deepseek` pin pings one (audit.py:3810). (c) Line 3 "Two lanes.": `brief` accepts `--lane {api,agent,solo}` and the audit.py docstring lists three. (d) Lines 37-38 say the client "switches to `chat/completions`" when `ZAI_BASE_URL` is set; the default route already is chat/completions.
- Reproduce: `awk 'NR>=68 && NR<=69' z-requirements-code-audit/scripts/zai_client.py` -> `KEY_FIELDS = ("ZAI_API_KEY", "GLM_API_KEY", "ANTHROPIC_AUTH_TOKEN",` and `"apiKey", "api_key", "key", "api-key")`; `env HOME=/nonexistent ZAI_API_KEY=$K AUD doctor | sed -n 6p` -> `route       openai -> https://api.z.ai/api/coding/paas/v4/chat/completions`
- Fix: line 34 drop "`token`, ". Line 47 "a live ping to both models" -> "a live ping to each model the pin allows (two on z.ai, one on DeepSeek)". Line 3 "Two lanes." -> "Two automatic lanes (a third, `--lane solo`, only labels a run the lead does by hand)." Lines 37-38 -> "The default route is already OpenAI-compatible (`chat/completions` with a `Bearer` header); `ZAI_BASE_URL` overrides the base URL, and a base that contains `/anthropic` switches to the Messages route."
- Files the fix touches: z-skills/z-requirements-code-audit/SETUP.md

### F-7 MINOR
- Where: z-skills/z-requirements-code-audit/SETUP.md:87 (against SETUP.md:84 and :86)
- Quote: "Nothing is written outside audit dirs."
- Criterion: 7 Internal contradiction
- Why it is a defect: three lines earlier the same file says the audit dir is "Added to `.git/info/exclude` automatically", and `_git_exclude` (audit.py:2330-2346) appends to that file, which is outside every audit dir; `brief --force` also writes the sibling `.audit.prev-<timestamp>/` (SETUP.md:86, audit.py:2238).
- Reproduce: `awk 'NR>=2338 && NR<=2346' z-requirements-code-audit/scripts/audit.py` -> `ex = os.path.join(gd, "info", "exclude")` ... `with io.open(ex, "a", encoding="utf-8") as fh:`
- Fix: "Nothing is written outside audit dirs." -> "Nothing else is written outside audit dirs, except the `.git/info/exclude` lines."
- Files the fix touches: z-skills/z-requirements-code-audit/SETUP.md

### F-8 MINOR
- Where: z-skills/z-requirements-code-audit/SKILL.md:40; z-skills/z-systematic-debugging/SKILL.md:59; z-skills/z-doc-generator/SKILL.md:41; z-skills/z-git-diff-summary/SKILL.md:24
- Quote: "follow that `NEXT` and do not read `fast.md`"
- Criterion: 5 Broken reference
- Why it is a defect: `fast.md` exists only in z-brainstorming, and the slow-mode NEXT lines handoff.py prints for these four skills (lines 986-1306) never name it. The clause is a leftover of the z-brainstorming, z-writing-plans and z-dev-team text (handoff.py:838, 941, 947, 955, 972).
- Reproduce: `find . -name 'fast.md'` -> `./z-brainstorming/fast.md`
- Fix: in each of the four files delete " and do not read `fast.md`".
- Files the fix touches: z-skills/z-requirements-code-audit/SKILL.md, z-skills/z-systematic-debugging/SKILL.md, z-skills/z-doc-generator/SKILL.md, z-skills/z-git-diff-summary/SKILL.md

### F-9 MAJOR
- Where: z-skills/z-systematic-debugging/evals/README.md:15 (also evals/README.md:13; evals/test-academic.md:7)
- Quote: "`bisect-parallel.sh` from `v2.3.0`"
- Criterion: 5 Broken reference; 7 Internal contradiction
- Why it is a defect: the pass criterion for test-swarm requires a script the skill no longer has, and a bisect across 800 commits, while SKILL.md:90 and parallel-playbook.md:90-92 say "git history is not read" and _shared/tests/test_debug_slow.py:107-118 asserts that the probe names no bisect. Line 13 ("the bootstrap + `probe`", `--error`) and test-academic.md:7 ("Phase 1") use the pre-9.0 vocabulary: SKILL.md has no bootstrap (its `H=` loop, SKILL.md:18) and no numbered phases (R1 to R11).
- Reproduce: `grep -rn 'bisect-parallel' z-systematic-debugging _shared/tests` -> `z-systematic-debugging/evals/README.md:15:...` and `_shared/tests/test_debug_slow.py:118:        self.assertNotIn("bisect-parallel.sh", out)`
- Fix: evals/README.md:15, replace the text from "`bisect-parallel.sh`" up to "= 3 rounds;" with "No bisect and no git history: candidate causes from the current code, each as an `experiment` entry (`treatment_cmd`, `runs` at least 3/p),". evals/README.md:13 "Round 1 is the bootstrap + `probe` in ONE call (with `--error` or `--error-file`, and `--cmd 'npm run build'`)." -> "Round 1 is `handoff.py open --cmd 'npm run build'` in ONE call (it runs `probe --cmd`)." (handoff.py:1184-1185 passes only `--cmd`). test-academic.md:7 "during Phase 1" -> "when you compare, hypothesize and run the experiment".
- Files the fix touches: z-skills/z-systematic-debugging/evals/README.md, z-skills/z-systematic-debugging/evals/test-academic.md

### F-10 MAJOR
- Where: z-skills/z-systematic-debugging/references/parallel-playbook.md:44
- Quote: "The scripts export `STRESS_RUN` / `BISECT_JOB` / `POLLUTER_JOB`"
- Criterion: 5 Broken reference
- Why it is a defect: no script in the skill sets `BISECT_JOB`. stress.sh exports `STRESS_RUN` (lines 12, 39-40), find-polluter.sh exports `POLLUTER_JOB` (lines 11, 78) and `experiment` exports `SD_EXPERIMENT`, `SD_ARM`, `SD_RUN` (debug_tool.py:645-647); the bisect script that exported it is gone (F-9).
- Reproduce: `grep -rn 'BISECT_JOB' z-systematic-debugging/scripts` -> no output (the name occurs only twice, on parallel-playbook.md:44)
- Fix: "`STRESS_RUN` / `BISECT_JOB` / `POLLUTER_JOB`" -> "`STRESS_RUN` / `POLLUTER_JOB`"; the example -> `PORT=$((20000 + ${POLLUTER_JOB:-0} * 100 + ${STRESS_RUN:-0}))`
- Files the fix touches: z-skills/z-systematic-debugging/references/parallel-playbook.md

### F-11 MAJOR
- Where: z-skills/z-systematic-debugging/scripts/debug_tool.py:4-10; z-skills/z-systematic-debugging/README.md:48
- Quote: "scripts/debug_tool.py            probe | run | experiment | scan | doctor | setup" (README.md:48; middle dot folded)
- Criterion: 4 Truthfulness (wrong help text)
- Why it is a defect: both lists omit `close`, the subcommand SKILL.md R3 (line 64) and R11 (line 140) depend on. `debug_tool.py -h` prints the six-name docstring right above a usage line that names seven.
- Reproduce: `DBG -h | head -1` -> `usage: debug_tool.py [-h] {probe,run,experiment,scan,close,doctor,setup} ...`, against the docstring lines 5-10 that end with `  setup       print the ZCode config block` and never list `close`
- Fix: debug_tool.py, after line 8, add `  close       accept a root cause only from .debug/experiments.json`. README.md:48 insert `close | ` before `doctor`.
- Files the fix touches: z-skills/z-systematic-debugging/scripts/debug_tool.py, z-skills/z-systematic-debugging/README.md

### F-12 MAJOR
- Where: z-skills/z-systematic-debugging/scripts/debug_tool.py:1133
- Quote: "copies agents/z-debug-worker.md verbatim into ~/.zcode/agents/ (real model ids, `thoughtLevel: max`)."
- Criterion: 4 Truthfulness; 3 Six-model matrix
- Why it is a defect: agents/z-debug-worker.md:1-8 has no `model` line (name, description, color, thoughtLevel, maxTurns, injectAgentsMd), by design; `audit.py setup` says the opposite in the same repo ("Agent files do not set a model id", audit.py:3862).
- Reproduce: `DBG setup --harness zcode` (prints only) -> the fourth line ends `(real model ids, `thoughtLevel: max`).`; `awk 'NR<=8' z-systematic-debugging/agents/z-debug-worker.md` -> frontmatter with no `model:` line
- Fix: "(real model ids, `thoughtLevel: max`)" -> "(no model id: it follows the session model; `thoughtLevel: max`)"
- Files the fix touches: z-skills/z-systematic-debugging/scripts/debug_tool.py

### F-13 MAJOR
- Where: z-skills/z-systematic-debugging/references/z-tuning.md:50
- Quote: "Tiers live only in `debug_tool.py` `TIERS`: every tier is `glm-5.3-flash`;"
- Criterion: 3 Six-model matrix; 7 Internal contradiction
- Why it is a defect: `scan` passes every tier id through `flash_pin.resolve_http_model` (debug_tool.py:894, 1099-1102), so the tier model is `deepseek-flash` under a `deepseek` pin and the pro id under a pro pin. SKILL.md:101 says the same; this sentence tells every non-flash session that it runs on glm-5.3-flash.
- Reproduce: `GLM_FLASH=deepseek python3 -c "import sys; sys.path.insert(0,'z-requirements-code-audit/scripts'); import flash_pin; print(flash_pin.resolve_http_model('glm-5.3-flash'))"` -> `deepseek-flash`
- Fix: "every tier is `glm-5.3-flash`;" -> "every tier names `glm-5.3-flash`, which `flash_pin.resolve_http_model` turns into `deepseek-flash` under a `deepseek` pin and into the pro id under a pro pin;"
- Files the fix touches: z-skills/z-systematic-debugging/references/z-tuning.md

### F-14 MAJOR
- Where: z-skills/z-systematic-debugging/references/z-tuning.md:48
- Quote: "It retries once on 429/5xx, and retries once without `reasoning_effort` if the gateway rejects that field."
- Criterion: 4 Truthfulness
- Why it is a defect: `scan` calls `zai_client.Client.call` with its default `retries=4` (zai_client.py:361; debug_tool.py:785) and has no code that drops `reasoning_effort`; any API error becomes the worker's answer "VERDICT: INCONCLUSIVE" (debug_tool.py:784-787).
- Reproduce: `grep -n 'retries\|reasoning_effort' z-systematic-debugging/scripts/debug_tool.py` -> no output
- Fix: -> "It backs off and retries up to 4 times on 429, 5xx and network errors (`zai_client.py` `Client.call`); any other API error makes the worker answer `VERDICT: INCONCLUSIVE`."
- Files the fix touches: z-skills/z-systematic-debugging/references/z-tuning.md

### F-15 MAJOR
- Where: z-skills/z-systematic-debugging/README.md:32; references/z-tuning.md:45-48 and :61; scripts/debug_tool.py:1134
- Quote: "export ZAI_API_KEY=<GLM Coding Plan key>       # optional: enables the scan lane (at most 8 API workers at once)"
- Criterion: 4 Truthfulness; 2 AGENTS.md ("never hardcode one provider or one harness")
- Why it is a defect: `scan` finds its key with `zai_client.find_key()` (debug_tool.py:776-777), which under a `deepseek` pin ignores every name these lines give. The "API surface used by `scan`" table (z-tuning.md:43-46) lists only z.ai URLs, although the default base is then https://api.deepseek.com (flash_pin.py:17).
- Reproduce: `env HOME=/nonexistent GLM_FLASH=deepseek ZAI_API_KEY=$K python3 -c "import sys; sys.path.insert(0,'z-systematic-debugging/scripts'); import debug_tool; print(debug_tool.find_key())"` -> `(None, None)`; with `GLM_FLASH=glm` -> `('zai-0123456789abcdef0123456789', 'env:ZAI_API_KEY')`
- Fix: README.md:32, add below it: `export DEEPSEEK_API_KEY=<your DeepSeek key>   # instead of the line above, for a `deepseek` pin in ~/.zcode/z-flash`. z-tuning.md:48 -> "`scan` finds its key with `zai_client.find_key()`: under a `deepseek` pin `DEEPSEEK_API_KEY`, `DEEPSEEK_KEY`, or the deepseek block of `~/.zcode/v2/provider_config.json`; otherwise `ZAI_API_KEY`, `Z_AI_API_KEY`, `GLM_API_KEY`, `ZHIPUAI_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, or a named key field in `~/.claude/settings.json`, `~/.zcode/v2/credentials.json` (its `api-key` field) and `~/.zcode/*.json`." Add the table row `| DeepSeek (pin `deepseek`) | `https://api.deepseek.com` | `DEEPSEEK_BASE_URL` overrides |`. z-tuning.md:61 "Export `ZAI_API_KEY`" -> "Export `ZAI_API_KEY` (or `DEEPSEEK_API_KEY` under a `deepseek` pin)". debug_tool.py:1134, add the comment line `# export DEEPSEEK_API_KEY=<your DeepSeek key>   # instead, for a deepseek pin in ~/.zcode/z-flash`.
- Files the fix touches: z-skills/z-systematic-debugging/README.md, z-skills/z-systematic-debugging/references/z-tuning.md, z-skills/z-systematic-debugging/scripts/debug_tool.py

### F-16 MINOR
- Where: z-skills/z-systematic-debugging/README.md:42
- Quote: "SKILL.md                         12 numbered rules, loaded on use"
- Criterion: 4 Truthfulness
- Why it is a defect: SKILL.md has eleven numbered sections, R1 to R11 (SKILL.md:26, 46, 57, 66, 85, 95, 99, 103, 121, 134, 138).
- Reproduce: `grep -c '^## R[0-9]' z-systematic-debugging/SKILL.md` -> `11`
- Fix: "12 numbered rules" -> "11 numbered rules (R1-R11)"
- Files the fix touches: z-skills/z-systematic-debugging/README.md

### F-17 MINOR
- Where: z-skills/z-systematic-debugging/SKILL.md:64
- Quote: "python3 $S/debug_tool.py run '<the failing command>' <path/to/test/file>"
- Criterion: 5 Broken reference; 6 Script defect reachable from the skill's own steps
- Why it is a defect: `run` executes every positional as a shell command (debug_tool.py:461) and has no file operand, so a path there can only exit non-zero. The script's own NEXT line uses `run -- <quoted repro>` (debug_tool.py:425).
- Reproduce: `DBG run z-systematic-debugging/README.md | sed -n 2,5p` -> `RESULT: 1/1 exited non-zero (1 parallel, 0.0s wall)`, `== [0] rc=126 0.0s :: z-systematic-debugging/README.md`, `/bin/bash: z-systematic-debugging/README.md: Permission denied`
- Fix: `run '<the failing command>' <path/to/test/file>` -> `run -- '<the failing command>'`
- Files the fix touches: z-skills/z-systematic-debugging/SKILL.md

### F-18 MINOR
- Where: z-skills/z-systematic-debugging/references/z-tuning.md:60
- Quote: "**Every command says `S=` is empty.** The bootstrap loop found no `debug_tool.py`."
- Criterion: 4 Truthfulness; 5 Broken reference
- Why it is a defect: no tool can print an empty `S=` (each prints `S=%s` with the absolute scripts dir: debug_tool.py:364, 468, 616, 907, 923, 1104), and SKILL.md has no bootstrap loop: its `H=` loop looks for `handoff.py` and prints "z-systematic-debugging: handoff.py not found" (SKILL.md:18).
- Reproduce: `grep -rn -i 'bootstrap' z-systematic-debugging/SKILL.md z-systematic-debugging/scripts/*.py z-systematic-debugging/scripts/*.sh` -> no output
- Fix: -> "1. **The first command prints `z-systematic-debugging: handoff.py not found`.** None of the five install locations has `scripts/handoff.py`. Ask for the install dir; never guess a path."
- Files the fix touches: z-skills/z-systematic-debugging/references/z-tuning.md

### F-19 MAJOR
- Where: z-skills/z-systematic-debugging/references/z-tuning.md:34 (also :35-39); z-skills/z-systematic-debugging/SKILL.md:28; z-skills/z-requirements-code-audit/references/z-tuning.md:33 and :39
- Quote: "Both models: 1M context, 128K output."
- Criterion: 7 Internal contradiction; 3 Six-model matrix
- Why it is a defect: line 7 of the same file says "Six display names cover the three tiers", so "Both models" names none of them. Rows 35 to 39 ("Few tool calls per model turn", "Flash is faster per token but more verbose", "Weaker over long horizons", "Trained toward brevity") justify R1, R7 and R8 without naming the model; they lost their only attribution when the title changed from "GLM-5.3 / GLM-5.3-Flash tuning" to "Session-model tuning" (the file's latest commit is 595bcc2). SKILL.md:28 "You emit few parallel tool calls per turn" says the same to every session model; README.md:11 names the models, SKILL.md does not. In the audit tuning file, rows 33 ("Reasoning is **always on**") and 39 ("Flash is more verbose than median") name no model either.
- Reproduce: `grep -n 'Six display names\|^| Both models\|Few tool calls per model turn\|Weaker over long horizons' z-systematic-debugging/references/z-tuning.md | cut -c1-90` -> `7:Six display names cover the three tiers a session can run on. The`, `34:| Both models: 1M context, 128K output. | Long `probe` output is affordable; verbosity,`, `35:| Few tool calls per model turn (2 observed in public testing), even where the API adve`, `38:| Weaker over long horizons; error accumulates. | R8 state carry (5 lines) and a hard r`
- Fix: z-tuning.md (debugging) :34 "Both models:" -> "GLM 5.3 and GLM-5.3-Flash:"; :35 -> "GLM-5.3 and GLM-5.3-Flash: few tool calls per model turn (2 observed in public testing), ..."; :37 "Flash is faster" -> "GLM-5.3-Flash is faster"; :38 -> "GLM-5.3 is weaker over long horizons; error accumulates."; :39 -> "GLM is trained toward brevity; ...". SKILL.md:28 -> "GLM-5.3 and the flash-tier models emit few parallel tool calls per turn, and each turn costs seconds of latency; every session model, DeepSeek V4 Pro and Claude Sonnet 5.5 included, uses the same one-call-per-phase plan." (the wording of README.md:11). z-tuning.md (audit) :33 -> "On the z.ai API reasoning is **always on**"; :39 -> "GLM-5.3-Flash is more verbose than median". Which model each fact was measured on is UNVERIFIED here; the old title is the only attribution.
- Files the fix touches: z-skills/z-systematic-debugging/references/z-tuning.md, z-skills/z-systematic-debugging/SKILL.md, z-skills/z-requirements-code-audit/references/z-tuning.md

### F-20 MAJOR
- Where: z-skills/z-doc-generator/SKILL.md:78-79 (against SKILL.md:132, :269, :82, :109)
- Quote: "| 3 | Writers for the known set (<= 8) + reviewer Tasks for api-reference, data-model, and configuration only + any 1 retry"
- Other side: SKILL.md:269 "## 4. TURN 3 -- REVIEW WAVE (api, data model, configuration only)"; SKILL.md:78 "Do not launch writers in this message"; SKILL.md:132 "## 3. TURN 2 -- GATE + WRITE WAVE (one message: Gate list or 1 line of intent + 1 bash + <= 8 Tasks)"
- Criterion: 7 Internal contradiction
- Why it is a defect: the turn ledger and the section headings use two turn numberings that cannot both hold. (a) Ledger row 2 forbids writers in Turn 2, but line 132 defines Turn 2 as the write wave and line 109 writes recon.md "in Turn 2, before any writer starts". (b) Ledger row 3 puts writers and reviewers in one message, but line 269 makes Turn 3 the review wave only, line 271 skips it "unless a doc written this run" exists, and the reviewer edits the writer's file (line 277), which does not exist while the writers run. (c) Line 82 "Skip Turn 1's work on a cache hit": the hit is known only from the Turn 1 call (handoff.py:1271 runs recon.sh; recon.sh:6 prints it).
- Reproduce: `grep -n '^| [234] |\|^## [345]\. TURN\|Skip Turn' z-doc-generator/SKILL.md | cut -c1-90` -> lines 78, 79, 80, 82, 132, 269, 313 with the texts quoted above
- Fix: ledger rows 2 to 4 -> `| 2 | Gate list (section 3.0) only; it ends the turn. Gate skipped: this is the write wave (1 line of intent + 1 bash + up to 8 writers) |`, `| 3 | Gate skipped: the review wave (section 4). Gate ran: the write wave of section 3.3 (1 bash + up to 8 writers) |`, `| 4 | 1 bash (mechanical verify + update state) + final summary. Gate ran: the review wave is Turn 4 and finish is Turn 5 |`. Line 82 -> "Skip the review wave when no HIGH doc was written this run. A cache hit is known only after the Turn 1 call: report `[cached]` and stop." R1 (line 42) "Turn budget <= 4" -> "Turn budget <= 4 without a Gate, <= 5 with one". The last edit changes a budget the owner set: it is flagged, not assumed.
- Files the fix touches: z-skills/z-doc-generator/SKILL.md

### F-21 MAJOR
- Where: z-skills/z-doc-generator/SKILL.md:48 (against SKILL.md:208, :365, :372, :404 and agents/z-doc-writer.md:5)
- Quote: "| R7 | **Reasoning effort: main thread `high`, writers `high`, reviewers `max`.**"
- Other side: SKILL.md:365 "effort is pinned in the agent file"; agents/z-doc-writer.md:5 `thoughtLevel: max`
- Criterion: 7 Internal contradiction
- Why it is a defect: R7, the writer template ("Effort: high", line 208) and Appendix B ("`high` for writers", line 404) put writers at `high`, while the pinned agent file says `max`. The ZCode app bundle maps an agent's `thoughtLevel` to the reasoning level of its calls (glm/zcode.cjs: `thoughtLevel` -> `options:{reasoningLevel:i}`), so the writer runs at `max` and R7's own violation row, "Deep reasoning on mechanical work", is what the skill ships.
- Reproduce: `grep -n 'writers `high`\|Effort: high\|effort is pinned\|^thoughtLevel' z-doc-generator/SKILL.md z-doc-generator/agents/z-doc-writer.md | cut -c1-100` -> `z-doc-generator/agents/z-doc-writer.md:5:thoughtLevel: max`, `z-doc-generator/SKILL.md:48:| R7 | **Reasoning effort: main thread `high`, writers `high`, reviewers`, `z-doc-generator/SKILL.md:208:ROLE: Technical writer. Effort: high ...`, `z-doc-generator/SKILL.md:365:Cuts per-Task prompt size; effort is pinned in the agent file. ...`, `z-doc-generator/SKILL.md:372:thoughtLevel: max`
- Fix (the owner picks one side): (A) prose follows the file: R7 "writers `high`" -> "writers `max`, pinned by the agent file"; line 208 "Effort: high" -> "Effort: max (pinned by your agent file)"; line 404 "`high` for writers" -> "`max` for writers". (B) file follows the prose: `thoughtLevel: high` in agents/z-doc-writer.md:5 and SKILL.md:372, plus the two assertions that pin `max` in _shared/tests/test_z_docgen_snippets.py:171 and :204 (lane 2).
- Files the fix touches: z-skills/z-doc-generator/SKILL.md (and z-skills/z-doc-generator/agents/z-doc-writer.md for option B)

### F-22 MAJOR
- Where: z-skills/z-doc-generator/SKILL.md:183 (also :181-182 and R8, :49)
- Quote: "If the recon printed no usable `CHANGED SINCE` list (shallow clone, rewritten history, no git),"
- Criterion: 5 Broken reference
- Why it is a defect: no doc-generator script prints a `CHANGED SINCE` list or any changed-file list (recon.sh prints HEAD, ROOT, FILES, TREE, EXT, manifests, FACTPACK, TESTS, CI, EXISTING DOCS; handoff.py:1271-1272 passes it through). By the skill's own rule every scope is therefore always "changed", and the per-doc `[cached]` test on line 182 (`changed-files` intersect `its scope` is empty) can never fire; only the all-or-nothing `=== CACHE HIT ===` of recon.sh:6 works.
- Reproduce: `grep -n -i 'changed' z-doc-generator/scripts/recon.sh z-doc-generator/scripts/claims.py` -> no output
- Fix (no code): line 183 -> "No script prints a changed-file list, so with `HEAD` changed treat every scope as changed; `state.json` serves the full cache hit only." Option that keeps R8's per-doc path, in recon.sh after line 7: `OLD=$(sed -n 's/^{"head":"\([0-9a-f]*\)".*/\1/p' "$S/state.json" 2>/dev/null | head -n 1); if [ -n "$OLD" ] && git cat-file -e "$OLD^{commit}" 2>/dev/null; then echo "== CHANGED SINCE $OLD =="; { git diff --name-only "$OLD" HEAD; git ls-files --others --exclude-standard; } | sort -u | head -400; fi`
- Files the fix touches: z-skills/z-doc-generator/SKILL.md (option: z-skills/z-doc-generator/scripts/recon.sh)

### F-23 MINOR
- Where: z-skills/z-find-skills/SKILL.md:85-86 (also :91-92)
- Quote: "folder lands outside both skill scopes, skips every frontmatter check, and pollutes version control"
- Criterion: 7 Internal contradiction
- Why it is a defect: the skill's own reference lists four skill locations (references/zcode-skill-loading.md:11-14), matching the ZCode guide (zcode-configuration-guide 0.3.0, line 30), so a hand-placed folder in `.agents/skills/` lands inside a skill scope. "no args scans both scopes" is true of the validator (validate_install.py:128 scans two roots) but not of the four scopes the reference documents.
- Reproduce: `awk 'NR>=11 && NR<=14' z-find-skills/references/zcode-skill-loading.md | cut -c1-80` -> `| User | `~/.zcode/skills/<name>/` | ...`, `| Project | `<repo>/.zcode/skills/<name>/` | ...`, `| User fallback | `~/.agents/skills/` | ...`, `| Project fallback | `<repo>/.agents/skills/` | ...`
- Fix: line 86 "lands outside both skill scopes" -> "lands outside the two scopes the CLI installs to"; lines 91-92 "no args scans both scopes" -> "no args scans `~/.zcode/skills` and `<cwd>/.zcode/skills`; pass a dir to check a `.agents/skills` install"
- Files the fix touches: z-skills/z-find-skills/SKILL.md

### F-24 MINOR
- Where: z-skills/z-git-diff-summary/scripts/gather.sh:72 (also :63, :148-153); SKILL.md:28
- Quote: `"+refs/heads/$B:refs/remotes/$REMOTE/$B" >/dev/null 2>&1 & fp=$!`
- Criterion: 6 Script defect reachable from the skill's own steps
- Why it is a defect: SKILL.md:24 invites `--base=<base>` for "a branch, tag or SHA" and line 28 says all three work, but gather.sh always fetches `refs/heads/<base>`. For a tag or SHA that ref cannot exist: the fetch fails and the header carries two false alarms, `WARN_STALE_BASE (fetch failed/timeout 6s)` (line 151) and `WARN_STALE_BASE_LOCAL` (line 153), which SKILL.md:39 makes the first line of the answer.
- Reproduce (dry run, no ref updated): `git fetch --dry-run --no-tags --no-write-fetch-head --no-recurse-submodules origin "+refs/heads/$(git rev-parse HEAD):refs/remotes/origin/$(git rev-parse HEAD)"` -> `fatal: couldn't find remote ref refs/heads/<40-hex sha>`
- Fix: after line 59 add `IMM=0; if [ $ARG_OK -eq 1 ] && has "$B^{commit}" && ! has "refs/heads/$B" && { [ -z "$REMOTE" ] || ! has "$REMOTE/$B"; }; then IMM=1; fi`. Line 63: prefix `[ "$IMM" = 0 ] && `. Line 148: `case "$FST:$FRC" in` -> `case "$IMM:$FST:$FRC" in 1:*) echo "BASE=immutable (tag or sha $B; not fetched)";;` and prefix the four existing patterns with `0:`. Line 153: prefix `[ "$IMM" = 0 ] && `.
- Files the fix touches: z-skills/z-git-diff-summary/scripts/gather.sh

### F-25 MAJOR
- Where: z-skills/z-idea-to-spec/scripts/check_spec.py:16; z-skills/z-idea-to-spec/references/spec-template.md:92
- Quote: "### 10.3 Hosting & monthly cost at 100 / 1k / 10k users"
- Criterion: 6 Script defect reachable from the skill's own steps
- Why it is a defect: the last branch of `MONEY_RE` matches any number followed by k, m or b, and its middle branch any percentage, so the skill's own template (which SKILL.md:122 tells the model to follow) fails the gate SKILL.md:149 makes mandatory ("repair every FAIL before showing it"). Non-money targets such as "99.9% uptime", "coverage 80%" or "10k users" are reported as unsourced money figures; the only repair the script accepts is a label or a URL.
- Reproduce: `python3 z-idea-to-spec/scripts/check_spec.py z-idea-to-spec/references/spec-template.md` -> `FAIL money - line 92 states a figure with no source or label: ### 10.3 Hosting & monthly cost at 100 / 1k / 10k users`, `RESULT spec fail=1`. Same gate on single lines through `check_spec.lint`: `| Availability | 99.9% uptime, RPO 5 min, RTO 30 min |` and `- Testing: pytest, minimum coverage 80%, run with `pytest -q`` each produce a `FAIL money` line.
- Fix: check_spec.py:16 -> `r"(\$\s?\d|\d+(?:\.\d+)?\s*%)",` (a bare count is not money); line 19 add `|\bTARGET\b` to `SOURCE_RE`; spec-template.md:79 `| Type | Requirement |` -> `| Type | Requirement (write TARGET before a target percentage) |`. After that the reproduce command ends with `RESULT spec fail=0`.
- Files the fix touches: z-skills/z-idea-to-spec/scripts/check_spec.py, z-skills/z-idea-to-spec/references/spec-template.md

### F-26 MINOR
- Where: z-skills/z-systematic-debugging/references/root-cause-tracing.md:12 (also :39); z-skills/z-systematic-debugging/references/flaky-and-timing.md:10; z-skills/z-idea-to-spec/references/spec-template.md:41
- Quote: "then consider guards on the path (`defense-in-depth.md`)"
- Criterion: 1 skill-criteria.md section 4 ("references/: ... one level deep (no reference chains)")
- Why it is a defect: each line sends the reader of one reference file to a second reference file. SKILL.md already routes to every one of them (debugging SKILL.md:68, :83, :87; z-idea-to-spec SKILL.md:106).
- Reproduce: `grep -n 'defense-in-depth.md\|parallel-playbook\|evaluation-framework.md' z-systematic-debugging/references/*.md z-idea-to-spec/references/*.md | cut -c1-80` -> `z-systematic-debugging/references/flaky-and-timing.md:10:...`, `z-systematic-debugging/references/root-cause-tracing.md:12:...`, `z-systematic-debugging/references/root-cause-tracing.md:39:...`, `z-idea-to-spec/references/spec-template.md:41:...`
- Fix: root-cause-tracing.md:12 "(`defense-in-depth.md`)" -> "(SKILL.md R4.3 opens `references/defense-in-depth.md` for that case)"; :39 "order-dependent recipe in parallel-playbook section 6" -> "order-dependent recipe of SKILL.md R5 (a shuffled-seed `experiment` with `treatment_cmd`)"; flaky-and-timing.md:10 "see parallel-playbook section 6" -> "see SKILL.md R4.3"; spec-template.md:41 "-- from evaluation-framework.md]" -> "-- paste the Phase 3 verdict]"
- Files the fix touches: z-skills/z-systematic-debugging/references/root-cause-tracing.md, z-skills/z-systematic-debugging/references/flaky-and-timing.md, z-skills/z-idea-to-spec/references/spec-template.md

[OUT-OF-SCOPE] _shared/handoff.py:13, :184, :859 and :1412 say "seven-skill ring" while `SKILLS` (lines 41-50) lists eight skills and line 1412 prints "outside the seven-skill ring" to the user. The fix belongs to lane 2 (_shared/handoff.py, then `sh _shared/sync.sh`). Every vendored copy in the six skills was byte-identical to _shared/ at 12:04 (`cmp`).

## Ready-to-dispatch fix slices

Each slice touches files no other slice touches. Numbers in brackets are finding ids.

### Slice 1: z-skills/z-requirements-code-audit/SKILL.md [F-2, F-8]
- Proof: `grep -c 'GLM endpoint\|fast.md' z-requirements-code-audit/SKILL.md` -> `0`.

### Slice 2: z-skills/z-requirements-code-audit/SETUP.md and references/z-tuning.md [F-3 (SETUP.md part), F-4, F-6, F-7, F-19 (audit tuning part)]
- Proof: `grep -c '`token`\|both models\|Two lanes\|OpenAI-compatible route works too\|request shape\|Nothing is written\|GLM edition' z-requirements-code-audit/SETUP.md` -> `0`; `grep -c 'clear_thinking\|Request-shape' z-requirements-code-audit/references/z-tuning.md` -> `0`.

### Slice 3: z-skills/z-requirements-code-audit/scripts/audit.py [F-1, F-3 (script part)]
- Proof: `env HOME=/nonexistent AUD brief --spec <a spec of at most 120 lines> --out <tmp dir> | grep -c '^lane agent'` -> `1` (writes only under `--out`); `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_audit*.py'` stays green. The handoff side is proven when `handoff.py open --self z-requirements-code-audit --spec=<the same spec>` prints "dispatch every printed batch in one message" in its last NEXT line (handoff.py:1247-1250).

### Slice 4: z-skills/z-requirements-code-audit/references/schemas.md [F-5]
- Proof: `grep -c '"attack"' z-requirements-code-audit/references/schemas.md` -> `1`.

### Slice 5: z-skills/z-systematic-debugging/SKILL.md [F-8, F-17, F-19 (SKILL.md part)]
- Proof: `grep -c 'fast.md\|<path/to/test/file>\|^You emit few parallel' z-systematic-debugging/SKILL.md` -> `0`.

### Slice 6: z-skills/z-systematic-debugging/README.md and references/z-tuning.md [F-11 (README line), F-13, F-14, F-15 (doc parts), F-16, F-18, F-19 (debugging tuning part)]
- Proof: `grep -c 'close' z-systematic-debugging/README.md` -> at least `1` (line 48); `grep -c 'every tier is `glm-5.3-flash`\|retries once\|bootstrap loop\|Both models\|^| Few tool calls\|^| Flash is faster\|^| Weaker over long' z-systematic-debugging/references/z-tuning.md` -> `0`; `grep -c '12 numbered rules' z-systematic-debugging/README.md` -> `0`; `grep -c 'DEEPSEEK_API_KEY' z-systematic-debugging/README.md z-systematic-debugging/references/z-tuning.md` -> one or more in each.

### Slice 7: z-skills/z-systematic-debugging/scripts/debug_tool.py [F-11 (docstring), F-12, F-15 (setup text)]
- Proof: `DBG -h | grep -c '^  close ' ` -> `1`; `DBG setup --harness zcode | grep -c 'real model ids'` -> `0`; `DBG setup --harness zcode | grep -c 'DEEPSEEK_API_KEY'` -> `1`; `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_debug*.py'` stays green (test_debug_flash_gate.py:75 pins `thoughtLevel: max` in the agent file, which does not change).

### Slice 8: z-skills/z-systematic-debugging/evals/README.md and evals/test-academic.md [F-9]
- Proof: `grep -c 'bisect-parallel\|bootstrap\|Phase 1' z-systematic-debugging/evals/README.md z-systematic-debugging/evals/test-academic.md` -> `0` for both.

### Slice 9: z-skills/z-systematic-debugging/references/parallel-playbook.md [F-10]
- Proof: `grep -rn 'BISECT_JOB' z-systematic-debugging | grep -v __pycache__` -> no output.

### Slice 10: z-skills/z-systematic-debugging/references/root-cause-tracing.md and references/flaky-and-timing.md [F-26 (debugging part)]
- Proof: `grep -n 'defense-in-depth.md\|parallel-playbook' z-systematic-debugging/references/root-cause-tracing.md z-systematic-debugging/references/flaky-and-timing.md` -> no output.

### Slice 11: z-skills/z-doc-generator/SKILL.md [F-8, F-20, F-21, F-22 (no-code option)]
- Proof: `grep -c 'fast.md\|CHANGED SINCE' z-doc-generator/SKILL.md` -> `0`; `grep -c 'Do not launch writers in this message\|Skip Turn 1' z-doc-generator/SKILL.md` -> `0`; for F-21 option A `grep -c 'writers `high`\|Effort: high\|`high` for writers' z-doc-generator/SKILL.md` -> `0`; `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p 'test_z_docgen_snippets.py'` stays green (lines 198-207 compare Appendix A with agents/*.md; lines 161-164 require `DOCGEN_STATE_DIR` next to `.zcode/doc-gen`, so keep that on any line that names the state dir).
- Depends on: the owner's choice for F-21 (A here, B adds agents/z-doc-writer.md and a lane-2 test) and for F-22 (no-code here, the recon.sh option is slice 12).

### Slice 12 (only if the owner keeps R8's per-doc path): z-skills/z-doc-generator/scripts/recon.sh [F-22 (code option)]
- Proof: run recon.sh twice in a scratch git repo with one commit between: the second run prints `== CHANGED SINCE <old head> ==` and the changed path. Depends on slice 11 for the SKILL.md:183 wording.

### Slice 13: z-skills/z-git-diff-summary/SKILL.md and scripts/gather.sh [F-8, F-24]
- Proof: `grep -c 'fast.md' z-git-diff-summary/SKILL.md` -> `0`; `bash z-git-diff-summary/scripts/gather.sh $(git rev-parse HEAD) | grep -c 'WARN_STALE_BASE'` -> `0` and `| grep -c '^BASE=immutable'` -> `1`; with a branch base the header still prints exactly one `BASE=` or `WARN_STALE_BASE` line. gather.sh fetches the base branch of the repo it runs in.

### Slice 14: z-skills/z-find-skills/SKILL.md [F-23]
- Proof: `grep -c 'both skill scopes\|scans both' z-find-skills/SKILL.md` -> `0`.

### Slice 15: z-skills/z-idea-to-spec/scripts/check_spec.py and references/spec-template.md [F-25, F-26 (idea-to-spec part)]
- Proof: `python3 z-idea-to-spec/scripts/check_spec.py z-idea-to-spec/references/spec-template.md | tail -1` -> `RESULT spec fail=0`; `python3 -c "import sys; sys.path.insert(0,'z-idea-to-spec/scripts'); import check_spec; print(check_spec.lint('| Availability | TARGET 99.9% uptime |'))"` -> only the verdict FAIL, no `FAIL money`; `check_spec.lint('- Price: $19/mo')` still reports `FAIL money`; `grep -c 'evaluation-framework.md' z-idea-to-spec/references/spec-template.md` -> `0`.

## Not verified

- UNVERIFIED: every model-behaviour claim in the two z-tuning.md files and in the READMEs: few parallel tool calls per turn (and for which of the six models), thinking cannot be disabled, 1M context and 128K output, `reasoning_effort` low/high/max with default max, Flash more verbose, "weaker over long horizons", z.ai alias routing (haiku, sonnet, opus), the 8-concurrent-calls provider limit for both providers, DeepSeek rejecting a temperature below 0.95 (zai_client.py:293). A vendor document or an API run would check them; none was read or run for this audit, except that z-tuning.md (audit) line 23 to 26 cites the GLM 5.4 model page.
- UNVERIFIED: ZCode runtime facts taken from prose: `Explore` and `general-purpose` as built-in agents (z-doc-generator SKILL.md:95, :205; z-git-diff-summary SKILL.md:49), `run_in_background: true` on the Agent tool, subagents launched together running in parallel, no nested subagents, the ~250-character description excerpt, Settings -> Skills and Settings -> Model Settings, "ZCode has no public headless CLI" (z-tuning.md, audit, :96). Evidence found but not exercised: the app bundle contains `GENERAL_PURPOSE_AGENT_TYPE` as the default subagent type and "Explore subagent spawned" log lines (browser-use 0.4.1 dist/mcp/server.js:107119, :113425), and the bundled diagnosing-skills guide states the 1024-character and ~250-character limits (lines 27, 31, 47). A live ZCode session would settle the rest.
- UNVERIFIED: whether an agent file's `thoughtLevel` wins over effort wording in the Task prompt at runtime (F-21). The bundle maps the field to `options.reasoningLevel` (glm/zcode.cjs, first `thoughtLevel` occurrence); no agent was launched.
- UNVERIFIED: how ZCode counts a turn when `run_in_background` agents wake the main thread, which decides whether z-doc-generator's "<= 4 main-thread turns" is reachable at all (F-20 only settles the textual contradiction).
- UNVERIFIED: that `https://api.z.ai/api/paas/v4` accepts a GLM Coding Plan key (SETUP.md:37); no request was made.
- UNVERIFIED: `npx skills find <query>` being non-interactive. The upstream help text says "Search for skills interactively" (vercel-labs/skills src/cli.ts, read through a fetch tool on 2026-11-25). The other z-find-skills claims were read the same way and hold: Node.js 22.20 or later, `-l, --list`, `-a, --agent`, `-g, --global`, `-y, --yes`, `-s, --skill`, `--copy`, `init [name]`, and `zcode` in docs/agents.md with `.zcode/skills/` and `~/.zcode/skills/`. The CLI itself was not run (`npx` installs into its cache).
- UNVERIFIED: "Law on Personal Data Protection No. 91/2025/QH15 (effective 2026-01-01)" (z-idea-to-spec references/question-bank.md:49); the line itself says to verify it during research. A legal database lookup would check it.
- UNVERIFIED: the measured numbers in z-systematic-debugging README.md:56-68 and z-tuning.md (audit) :55 ("about 4 s at 0.4 s latency, computed, not re-measured"). Not re-measured.
- Not run because it writes or costs: `debug_tool.py doctor` creates a detached worktree and runs `git worktree prune` (debug_tool.py:1110-1116) even without `--ping`; `audit.py doctor --ping` calls the API; `handoff.py open`, `audit.py brief`/`run`/`plan`/`finalize` and `recon.sh`/`gather.sh` write state or fetch; `audit.py setup` without `--dry-run` installs; `validate_install.py --selftest` writes temp skill folders. A `doctor` command that prunes worktrees in the user's repo is worth the owner's look; it matches no criterion in this briefing.

## Checked and clean

Read in full, no finding:

- z-requirements-code-audit/agents/z-rca-investigator.md (no model line; statuses match schemas.md and audit.py `STATUSES`)
- z-requirements-code-audit/agents/z-rca-verifier.md (no model line; requires `attack`, which is why F-5 is filed against schemas.md)
- z-requirements-code-audit/references/report-format.md (CSV columns and the 200-character note cut match audit.py:3231 and :3295-3296)
- z-requirements-code-audit/scripts/flash_pin.py (pin vocabulary is owned by other work; `~/.zcode/z-flash` and `GLM_FLASH` match AGENTS.md)
- z-requirements-code-audit/scripts/zai_client.py (KEY_ENV names match AGENTS.md; default base matches the debugging z-tuning table)
- z-systematic-debugging/agents/z-debug-worker.md (no model line; `thoughtLevel: max`, `maxTurns: 8` as z-tuning.md:67 says; identical to the installed copy)
- z-systematic-debugging/evals/test-fast-lane.md, test-swarm.md, test-tooling.md, test-pressure-1.md, test-pressure-2.md, test-pressure-3.md (prompts only; the pass criteria live in evals/README.md, F-9)
- z-systematic-debugging/references/defense-in-depth.md
- z-systematic-debugging/scripts/_lib.sh, snapshot.sh, stress.sh, find-polluter.sh (every flag the SKILL.md and parallel-playbook.md name exists: -n, -j, -t, -o, -k, -x, -b, --cmd, --link, --all; `STRESS_RUN` and `POLLUTER_JOB` are exported as documented)
- z-doc-generator/agents/z-doc-reviewer.md and agents/z-doc-writer.md (no model line; both identical to their Appendix A copies and to the installed files; the F-21 contradiction is between them and SKILL.md)
- z-doc-generator/scripts/claims.py, z-git-diff-summary/scripts/claims.py (differ by one byte, the skill name; `decide.py claim --root` exists)
- z-doc-generator/scripts/recon.sh (prints what SKILL.md section 2 says, except the `CHANGED SINCE` list, F-22)
- z-find-skills/references/zcode-skill-loading.md (four scopes and the six-step discovery order match zcode-configuration-guide 0.3.0 lines 30 and 51-62; "zcode-configuration-guide 0.3.0" is the installed version)
- z-find-skills/scripts/validate_install.py (ran on the six skill dirs: `RESULT fail=0 warn=0`)
- z-idea-to-spec/SKILL.md (`route` prints STAY or HANDOFF, NEXT, FROM-LINE and GUARD lines as line 45 says; the events `spec-ready`, `plan`, `implement` exist in handoff.py:142-144)
- z-idea-to-spec/references/evaluation-framework.md (9 criteria, weights sum to 100, verdict thresholds match SKILL.md:109 and :116)
- z-idea-to-spec/references/question-bank.md, z-idea-to-spec/references/research-playbook.md (shelf life matches SKILL.md:157)
- z-git-diff-summary/scripts/gather.sh apart from F-24 (all twelve markers in SKILL.md:36-44 are printed by gather.sh or handoff.py; 6 s fetch timeout, 300 s freshness window, at most 8 chunks, `TICKET=none`, `STYLE`, `INTENT`, `NUMSTAT` as documented)
- Frontmatter of all six skills: description 920, 522, 587, 569, 397 and 897 characters (limit 1024); WHEN clause at character 0, 181, 145, 0, 0 and 0 (limit 250); `name` equals the directory; bodies 203, 131, 390, 95, 102 and 154 lines. `python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py` -> `Ran 6 tests ... OK`.
- Read for docstring, help text and user-visible strings only (over 500 lines): audit.py, debug_tool.py, handoff.py, decide.py. Every audit.py, debug_tool.py, stress.sh and find-polluter.sh flag that the SKILL.md steps name exists in the `-h` output.

Two observations that match no criterion in this briefing, for the owner's convenience: z-systematic-debugging/SKILL.md:79 opens a ```bash fence that is never closed (the next lines render as code); z-systematic-debugging/references/z-tuning.md:52 and z-requirements-code-audit/references/z-tuning.md:37 still describe z.ai alias routing that `resolve_http_model` does not use.
