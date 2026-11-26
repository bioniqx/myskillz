# Audit report: lane 2 - z-dev-team, _shared, installers, AGENTS.md, CI

Date 2026-11-25. Read-only. Paths are relative to z-skills/ unless written <git root>
(/Users/yamazaki-ethan/Documents/Projects/mine/skillz). Commands ran from z-skills/ with
PYTHONDONTWRITEBYTECODE=1; nothing was written to the repo or to the home directory.

Severity follows the briefing's rubric. A false statement or a broken reference is MAJOR even when it
sits in a comment or a docstring that nothing prints; those are marked "inert at run time".

Concurrent work: while this lane ran, another workstream left uncommitted edits in tracked files.
Inside this lane's scope that is devteam.py:4028, handoff.py:848, :963-964 and :978, and decide.py:527.
No line count changed, so every line number below holds for the current tree (re-checked at the end).
Every other in-scope file is unchanged, and the vendored copies still match _shared/.

## Findings

### F-1 MAJOR
- Where: .github/workflows/skills.yml:18 (file location, lines 1 to 18)
- Quote: "run: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests"
- Criterion: 5 Broken reference (also 4 Truthfulness)
- Why it is a defect: The workflow sits at z-skills/.github/workflows/, but the git root is the parent
  folder (remote github.com/bioniqx/myskillz) and GitHub loads workflows only from
  <git root>/.github/workflows. This CI has no effect today, and its `-s _shared/tests` path does not
  exist from a repository root either.
- Reproduce: `git rev-parse --show-toplevel; git rev-parse --show-prefix; ls -la /Users/yamazaki-ethan/Documents/Projects/mine/skillz/.github` ->
  `/Users/yamazaki-ethan/Documents/Projects/mine/skillz`, `z-skills/`,
  `ls: /Users/yamazaki-ethan/Documents/Projects/mine/skillz/.github: No such file or directory`.
  The run step from that root: `cd .. && python3.12 -m unittest discover -s _shared/tests -t _shared/tests -p "test_*.py"` ->
  `ImportError: Start directory is not importable: '_shared/tests'`.
- Fix: From <git root> run `git mv z-skills/.github/workflows/skills.yml .github/workflows/skills.yml`,
  then insert after the `pull_request:` line:
  `defaults:` / `  run:` / `    working-directory: z-skills`. Everything else stays.
  GitHub workflow-syntax page (read 2026-11-25): "You must store workflow files in the `.github/workflows`
  directory of your repository." The suite itself is green on Python 3.12.16 from z-skills/
  (`Ran 795 tests in 131.599s`, `OK`), and `git check-ignore` does not ignore the target path.
- Files the fix touches: z-skills/.github/workflows/skills.yml (moved to <git root>/.github/workflows/skills.yml; outside z-skills/)

### F-2 MAJOR
- Where: z-dev-team/references/plan.md:9 (also :30 and :57)
- Quote: "one lane: RED tests committed, then GREEN"
- Criterion: 7 Internal contradiction
- Why it is a defect: SKILL.md:129 ("runs RED then GREEN as two dispatches: RED on the strong lane, a
  first GREEN on the default lane") and the engine run every strict and balanced code slice as two
  dispatches. plan.md:30 ("write tests inside the same lane") and :57 ("still one dispatch", and `size`
  "is the scheduler weight and the model router") carry the same one-lane wording, and no lane has a
  model of its own.
- Reproduce (engine's own profile states, default environment):
  `PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'` ... `PY'` with the body
  `import importlib.util as u` / `s = u.spec_from_file_location("d", "z-dev-team/scripts/devteam.py"); m = u.module_from_spec(s); s.loader.exec_module(m)` /
  `for name in ("strict", "balanced", "turbo"):` / `    st = dict(m.POLICY[name]); st["profile"] = name` /
  `    x = {"id": "S1", "kind": "code", "size": "small", "risk": "low", "status": "pending", "attempt": 1}` /
  `    a = m.code_mode(st, x); r1 = m.dispatch_route(st, x, a).split(",")[0]` /
  `    x.update(status="red-done", attempt=2)` / `    b = m.code_mode(st, x); r2 = m.dispatch_route(st, x, b).split(",")[0]` /
  `    print("%-8s first dispatch: %-5s %s | after red-done: %-5s %s" % (name, a, r1, b, r2))` /
  `PY` -> three lines:
  `strict   first dispatch: red   Agent(subagent_type=z-programmer-strong | after red-done: green Agent(subagent_type=z-programmer-lite`
  `balanced first dispatch: red   Agent(subagent_type=z-programmer-strong | after red-done: green Agent(subagent_type=z-programmer-lite`
  `turbo    first dispatch: slice Agent(subagent_type=z-programmer-lite | after red-done: green Agent(subagent_type=z-programmer-lite`
  (the "after red-done" half of the turbo line is forced by the script and is not a real second dispatch).
  Source: devteam.py:2073-2084 (`if fast < 2: return "red"`, then `"green"`) and :2096 (`strong = (mode == "red" or ...)`).
  Quote lines: `grep -n -o 'one lane: RED tests committed, then GREEN' z-dev-team/references/plan.md` -> `9:one lane: RED tests committed, then GREEN`.
- Fix: Line 9: replace `one lane: RED tests committed, then GREEN` with
  `strict/balanced: two dispatches, RED on the strong lane then GREEN; turbo/spike: one lane, RED then GREEN`.
  Line 30: replace `High-risk slices write tests inside the same lane as every other `code` slice.` with
  `High-risk slices take the same path as every other `code` slice.`
  Line 57: replace `is the scheduler weight and the model router: `trivial` and `small` use the lite lane, `large` uses the strong lane. `risk: high` also uses the strong lane, still one dispatch.` with
  `is the scheduler weight and the lane router: every RED dispatch runs on the strong lane; the first GREEN of a `trivial` or `small` low-risk slice runs on the lite lane, `large` runs on the strong lane. `risk: high` also uses the strong lane.`
- Files the fix touches: z-dev-team/references/plan.md

### F-3 MAJOR
- Where: z-dev-team/agents/z-team-leader.md:63 (also :73)
- Quote: "every slice that is neither `large` nor `risk: high` runs on the lite lane"
- Criterion: 7 Internal contradiction
- Why it is a defect: By default every RED dispatch of a code slice, small and low-risk included, runs
  on z-programmer-strong (F-2 routing output; SKILL.md:129), and a slice is two dispatches, not
  "in one lane" (:73). The planner is told the opposite of what the engine does with the `size` it picks.
- Reproduce: `grep -n -o 'every slice that is neither `large`\|in one lane, and the engine still runs RED proof' z-dev-team/agents/z-team-leader.md` ->
  `63:every slice that is neither `large``, `73:in one lane, and the engine still runs RED proof`. The
  routing check under F-2 shows the first dispatch on z-programmer-strong.
- Fix: Lines 63-65: replace `every slice that is neither `large` nor `risk: high` runs on the lite lane (session model, high effort); `large`, `risk: high` and anything the engine retries run on the strong lane (session model, max effort).` with
  `every RED dispatch, `large`, `risk: high` and anything the engine retries run on the strong lane (session model, max effort); the first GREEN of a slice that is none of those runs on the lite lane (session model, high effort).`
  Line 73: replace `session model at max effort, in one lane, and the engine still runs` with
  `session model at max effort (RED then GREEN on strict/balanced, one lane on turbo/spike), and the engine still runs`.
- Files the fix touches: z-dev-team/agents/z-team-leader.md

### F-4 MAJOR
- Where: z-dev-team/SKILL.md:63 (also :105)
- Quote: "`risk: high`, `size: large`, and any **retried** slice"
- Criterion: 7 Internal contradiction
- Why it is a defect: SKILL.md:63 and :105 define the strong lane as risk high, size large or retried and
  send "all others" to z-programmer-lite, while SKILL.md:129 sends every RED dispatch to the strong
  lane. One file states two different lane rules.
- Reproduce: `grep -n -o 'any \*\*retried\*\* slice\|all others to `z-programmer-lite`\.\|runs RED then GREEN as two dispatches' z-dev-team/SKILL.md` ->
  `63:any **retried** slice`, `105:all others to `z-programmer-lite`.`,
  `129:runs RED then GREEN as two dispatches`.
- Fix: Line 63: replace `| `risk: high`, `size: large`, and any **retried** slice |` with
  `| every RED dispatch, `risk: high`, `size: large`, and any **retried** slice |`.
  Line 105: replace `strong slices (risk high / size large / retried) route to `z-programmer-strong`, all others to `z-programmer-lite`.` with
  `every RED dispatch and every strong slice (risk high / size large / retried) route to `z-programmer-strong`, the other GREEN dispatches to `z-programmer-lite`.`
- Files the fix touches: z-dev-team/SKILL.md

### F-5 MAJOR
- Where: z-dev-team/scripts/devteam.py:895
- Quote: "(default small; drives scheduling order and model)"
- Criterion: 4 Truthfulness (also 7 Internal contradiction)
- Why it is a defect: `devteam plan-template`, which plan.md:34 names, prints this help string. No lane
  has a model of its own (SKILL.md:57-58; no agent file carries a `model:` line), and `size` does not
  even pick the lane of the RED dispatch. It is a wrong help text.
- Reproduce: `python3 z-dev-team/scripts/devteam.py plan-template | grep -n '"size"'` prints the line
  `"size": "trivial | small | large   (default small; drives scheduling order and model)",` (line 36 of
  the output); `grep -n -o 'drives scheduling order and model' z-dev-team/scripts/devteam.py` -> `895:drives scheduling order and model`.
- Fix: In devteam.py:895 replace `(default small; drives scheduling order and model)` with
  `(default small; drives scheduling order and the lane)`.
- Files the fix touches: z-dev-team/scripts/devteam.py

### F-6 MAJOR
- Where: z-dev-team/SKILL.md:248-249
- Quote: "Effort and model live in each agent file."
- Criterion: 7 Internal contradiction (also 3 Six-model matrix)
- Why it is a defect: SKILL.md:57 says "no agent pins a model so every lane follows the session model",
  and none of the six agent files has a `model:` line. The sentence tells the Conductor a model id sits
  in the agent files, the opposite of the rule the file enforces two sections earlier.
- Reproduce: `grep -n -E '^model:' z-dev-team/agents/*.md; echo "exit=$?"` -> `exit=1` (no match).
  The sentence: SKILL.md:248 ends "Effort and model live in each", :249 starts "agent file."
- Fix: Replace `Effort and model live in each` (line 248) with `Effort lives in each`.
- Files the fix touches: z-dev-team/SKILL.md

### F-7 MAJOR
- Where: z-dev-team/scripts/devteam.py:62-63 (module docstring, printed by `devteam.py --help`)
- Quote: "one final sharded review on the fast model (z-spot-reviewer), correctness/security only."
- Criterion: 3 Six-model matrix (also 4 Truthfulness)
- Why it is a defect: z-spot-reviewer has no model line and follows the session model (SKILL.md:64-65).
  In a GLM 5.3, DeepSeek V4 Pro or Claude Sonnet 5.5 session the help text calls that lane "the fast
  model", which is false. The owned range is lines 71-75; lines 62-63 are a separate sentence.
- Reproduce: `python3 z-dev-team/scripts/devteam.py --help | grep -n 'fast model'` ->
  `65:            the fast model (z-spot-reviewer), correctness/security only. Tests are still written first.`
- Fix: In devteam.py:63 replace `the fast model (z-spot-reviewer), correctness/security only.` with
  `z-spot-reviewer (session model), correctness/security only.`
- Files the fix touches: z-dev-team/scripts/devteam.py

### F-8 MAJOR
- Where: z-dev-team/agents/z-code-reviewer.md:88 (also :127; z-spot-reviewer.md:61 and :97)
- Quote: "The engine treats an `APPROVED` verdict with no `## Evidence` section as `CHANGES_REQUIRED`."
- Criterion: 7 Internal contradiction
- Why it is a defect: The engine records that case as `UNKNOWN`, prints "counted as NOT approved" and
  asks the Conductor to message the reviewer (devteam.py:3631-3646); plan.md:71 says the same
  ("APPROVED or PASS with no `## Evidence` is UNKNOWN"). Four sentences in the two reviewer files state
  a different verdict than the code they describe.
- Reproduce: `grep -n 'as `CHANGES_REQUIRED`\.' z-dev-team/agents/z-code-reviewer.md z-dev-team/agents/z-spot-reviewer.md` ->
  `z-dev-team/agents/z-spot-reviewer.md:61:5. The engine treats an `APPROVED` verdict with no `## Evidence` section as `CHANGES_REQUIRED`.`
  `z-dev-team/agents/z-spot-reviewer.md:97:`## Evidence` is mandatory: the engine treats an `APPROVED` verdict without it as `CHANGES_REQUIRED`.`
  `z-dev-team/agents/z-code-reviewer.md:88:5. The engine treats ...` (same sentence), `z-dev-team/agents/z-code-reviewer.md:127:`## Evidence` is mandatory: ...`;
  `grep -n 'rubber stamp' z-dev-team/scripts/devteam.py` -> `3632:                v = "UNKNOWN"                       # an approval that shows no evidence is a rubber stamp`.
- Fix: In all four places replace `as `CHANGES_REQUIRED`.` with `as `UNKNOWN` (counted as not approved).`
- Files the fix touches: z-dev-team/agents/z-code-reviewer.md, z-dev-team/agents/z-spot-reviewer.md

### F-9 MAJOR
- Where: z-dev-team/SKILL.md:187 (also :186; devteam.py:42, :79-80 and :3879)
- Quote: "`RUNTIME LIMIT` / `THROTTLED`"
- Criterion: 4 Truthfulness
- Why it is a defect: The engine reads spawn failures, rate-limit signals and dead lanes only from
  Claude Code's transcript folder (devteam.py:557-569 and :599-602). ZCode writes nothing there on this
  machine, although SKILL.md:18 and :103 declare ZCode as the harness. So `LANE DOWN`, `SPAWN FAILED`,
  `RUNTIME LIMIT` and `THROTTLED` cannot print under ZCode, and the halving described in `--help`
  (devteam.py:79-80) and `stats` (devteam.py:42, advertised at :3879) stay empty. A dropped launch still
  shows as `UNCLAIMED` (devteam.py:1434) and a silent lane as `STALLED?` after 20 minutes (devteam.py:1388, :143).
- Reproduce: With the module loaded as under F-2:
  `print("transcript_dirs:", m.transcript_dirs(pathlib.Path(".").resolve()), "is_zcode:", m.is_zcode())` ->
  `transcript_dirs: [] is_zcode: True`. On the machine where the skill is installed:
  `ls -d ~/.claude/projects/*mine-skillz*` -> `zsh:25: no matches found: /Users/yamazaki-ethan/.claude/projects/*mine-skillz*`;
  no `.jsonl` file under ~/.claude/projects was written today, the newest entry is dated Nov 2, and the
  skill was installed Nov 20 15:32.
- Fix (text only): devteam.py:42 replace `read from Claude Code's transcripts (tune with evidence)` with
  `read from Claude Code transcripts only (DEVTEAM_TRANSCRIPTS_DIR or ~/.claude/projects); ZCode writes none, so this is empty under ZCode`.
  devteam.py:3879 replace `; `stats` shows measured tokens/effort/errors per role.` with `.`.
  SKILL.md:187 append ` These lines and `LANE DOWN` come from harness transcripts (`DEVTEAM_TRANSCRIPTS_DIR` or `~/.claude/projects`); ZCode writes none, so there a dropped launch shows as `UNCLAIMED` and a silent lane as `STALLED?`.`
  The code remedy (teach `transcript_dirs()` ZCode's own session store) is larger and is the owner's call.
- Files the fix touches: z-dev-team/SKILL.md, z-dev-team/scripts/devteam.py

### F-10 MAJOR
- Where: _shared/zai_client.py:4
- Quote: "Canonical copy lives in skills/glm/_shared/; sync.sh vendors it into each"
- Criterion: 5 Broken reference
- Why it is a defect: The canonical copy lives in z-skills/_shared/ (AGENTS.md:32-33); skills/glm/_shared/
  does not exist. A maintainer of a vendored copy is sent to a stale path. Inert at run time (module docstring, not printed).
- Reproduce: `grep -n 'skills/glm' _shared/zai_client.py; ls -d skills/glm/_shared` ->
  `4:Canonical copy lives in skills/glm/_shared/; sync.sh vendors it into each`,
  `ls: skills/glm/_shared: No such file or directory` (also absent from <git root> and two levels up).
- Fix: Replace `Canonical copy lives in skills/glm/_shared/;` with `Canonical copy lives in z-skills/_shared/;`,
  then refresh the three vendored copies with `sh _shared/sync.sh`.
- Files the fix touches: _shared/zai_client.py, z-systematic-debugging/scripts/zai_client.py, z-writing-plans/scripts/zai_client.py, z-requirements-code-audit/scripts/zai_client.py

### F-11 MAJOR
- Where: install-zcode.sh:7-8 (header comment)
- Quote: "z-viral-video-studio has its own installer"
- Criterion: 4 Truthfulness
- Why it is a defect: The header gives z-viral-video-studio as a z-* folder without a root SKILL.md
  that this installer skips. It has a root SKILL.md, no installer in its folder, and the installer
  copies it (and z-video-shotcraft) like any other skill; no folder is skipped today. Inert at run time (comment).
- Reproduce: `sh install-zcode.sh --dry-run --home /nonexistent-home-lane2-audit | grep -E 'skills/z-viral-video-studio|skill folders|^== skipped|Dry run'` ->
  `[dry-run] rm -rf /nonexistent-home-lane2-audit/.zcode/skills/z-viral-video-studio`,
  `[dry-run] mkdir -p /nonexistent-home-lane2-audit/.zcode/skills/z-viral-video-studio`,
  `  /nonexistent-home-lane2-audit/.zcode/skills/z-viral-video-studio/   invoke $z-viral-video-studio`,
  `  1495 files in 11 skill folders -> /nonexistent-home-lane2-audit/.zcode/skills`, `== skipped`,
  `Dry run. Nothing written.` (the skipped section lists only cli/config.json).
- Fix: Lines 7-8: replace `Folders matching z-* without a root SKILL.md are skipped (they are not` /
  `ZCode skill packs; z-viral-video-studio has its own installer).` with
  `Folders matching z-* without a root SKILL.md are skipped. None exist today: all 11` /
  `z-* folders, the two video skills included, are installed.`
- Files the fix touches: install-zcode.sh

### F-12 MAJOR
- Where: z-dev-team/SKILL.md:49
- Quote: "install the skill first (README)"
- Criterion: 5 Broken reference
- Why it is a defect: No README documents installing this skill: none at the z-skills root, in
  z-dev-team/, or at <git root>; the only non-video README is z-systematic-debugging/README.md. The real
  instruction is the usage line of install-zcode.sh and install-dsh.sh. Reachable only when the skill
  text is loaded but its scripts are missing.
- Reproduce: `grep -n -o 'install the skill first (README)' z-dev-team/SKILL.md; ls README.md z-dev-team/README.md` ->
  `49:install the skill first (README)`, `ls: README.md: No such file or directory`,
  `ls: z-dev-team/README.md: No such file or directory`.
- Fix: Replace `install the skill first (README)` with
  `install the skill first (run `sh install-zcode.sh` or `sh install-dsh.sh` inside the z-skills folder)`.
- Files the fix touches: z-dev-team/SKILL.md

### F-13 MINOR
- Where: z-dev-team/scripts/devteam.py:3643 (also z-dev-team/SKILL.md:193)
- Quote: "no verdict line found in the report"
- Criterion: 7 Internal contradiction
- Why it is a defect: The suffix is added whenever the verdict is `UNKNOWN`, which also covers an
  `APPROVED` line without `## Evidence` (devteam.py:3631-3632); there a verdict line was found. The same
  printed line then names the real reason, and SKILL.md:193 describes only the first case.
- Reproduce: `grep -n -o 'no verdict line found in the report\|if verdict == "UNKNOWN" else ""' z-dev-team/scripts/devteam.py; grep -n -o 'Review `UNKNOWN` (no verdict line)' z-dev-team/SKILL.md` ->
  `3643:no verdict line found in the report`, `3643:if verdict == "UNKNOWN" else ""`, `193:Review `UNKNOWN` (no verdict line)`.
- Fix: devteam.py:3643 replace `if verdict == "UNKNOWN" else ""` with
  `if verdict == "UNKNOWN" and not no_evidence else ""`.
  SKILL.md:193 replace `Review `UNKNOWN` (no verdict line)` with
  `Review `UNKNOWN` (no verdict line, or `APPROVED` with no `## Evidence`; the printed line says which)`.
- Files the fix touches: z-dev-team/scripts/devteam.py, z-dev-team/SKILL.md

## Ready-to-dispatch fix slices

No slice depends on another. Slices 3 and 4 change agent files: after they land,
`python3 z-dev-team/scripts/devteam.py doctor --harness zcode` prints `STALE` until `--fix` is run.

1. CI placement - F-1
   - Files: z-skills/.github/workflows/skills.yml, moved to <git root>/.github/workflows/skills.yml.
   - Proof: `cd <git root> && test -f .github/workflows/skills.yml && test ! -f z-skills/.github/workflows/skills.yml && grep -n 'working-directory: z-skills' .github/workflows/skills.yml`;
     `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p "test_*.py"` passes (795 tests OK on 3.12.16 today);
     the final proof is the check that appears on the next push to main or pull request.
2. Plan reference - F-2
   - Files: z-dev-team/references/plan.md.
   - Proof: `grep -c 'still one dispatch\|model router\|write tests inside the same lane' z-dev-team/references/plan.md` prints 0;
     `grep -c 'two dispatches' z-dev-team/references/plan.md` prints 1.
3. Leader agent - F-3
   - Files: z-dev-team/agents/z-team-leader.md.
   - Proof: `grep -c 'in one lane' z-dev-team/agents/z-team-leader.md` prints 0;
     `grep -c 'every RED dispatch' z-dev-team/agents/z-team-leader.md` prints 1.
4. Reviewer agents - F-8
   - Files: z-dev-team/agents/z-code-reviewer.md, z-dev-team/agents/z-spot-reviewer.md.
   - Proof: `grep -c 'as `UNKNOWN` (counted as not approved)' z-dev-team/agents/z-code-reviewer.md z-dev-team/agents/z-spot-reviewer.md` prints 2 per file;
     `grep -c 'as `CHANGES_REQUIRED`' ` on the same two files prints 0.
5. SKILL.md - F-4, F-6, F-9 (SKILL.md lines), F-12, F-13 (SKILL.md line)
   - Files: z-dev-team/SKILL.md.
   - Proof: `grep -c 'every RED dispatch' z-dev-team/SKILL.md` prints 2; `grep -c 'Effort and model live\|(README)' z-dev-team/SKILL.md` prints 0;
     `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v` passes (description still 659 characters, name equals the folder).
6. devteam.py strings - F-5, F-7, F-9 (devteam.py lines), F-13 (devteam.py line)
   - Files: z-dev-team/scripts/devteam.py.
   - Proof: `python3 z-dev-team/scripts/devteam.py --help | grep -c 'fast model'` prints 0;
     `python3 z-dev-team/scripts/devteam.py plan-template | grep -c 'drives scheduling order and the lane'` prints 1;
     `grep -c 'and not no_evidence' z-dev-team/scripts/devteam.py` prints 1;
     the full `_shared/tests` suite passes after the edit.
   - Optional in the same edit: the comment at devteam.py:2075-2077 still says "# One lane." above the code that returns "red" and then "green".
7. Shared client docstring - F-10
   - Files: _shared/zai_client.py and its three vendored copies (z-systematic-debugging, z-writing-plans, z-requirements-code-audit `scripts/zai_client.py`).
   - Proof: `grep -rn 'skills/glm' _shared/zai_client.py z-*/scripts/zai_client.py` prints nothing;
     `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_vendored.py -v` passes.
   - Note: the copies sit in folders lanes 1 and 3 audit. They are byte-identical vendors; copy the one line into _shared/zai_client.py and run `sh _shared/sync.sh` only after the other lanes' `_shared` edits have landed, since sync.sh re-copies every vendored file.
8. Installer header - F-11
   - Files: install-zcode.sh.
   - Proof: `sh -n install-zcode.sh`; `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_install_zcode.py -v` passes;
     the dry run still prints `1495 files in 11 skill folders`.

## Not verified

- UNVERIFIED: z-dev-team on DeepSeek Harness. SKILL.md:18 declares `harness: zcode | dsh`, but the skill
  needs its six subagents. install-dsh.sh installs skills only, and the two dsh documents I read
  (packages/skill/skill-filesystem/README.md and README.md at deepseek-ai/deepseek-harness HEAD, fetched
  2026-11-25) state no subagent or slash-command mechanism. If a dsh session cannot dispatch
  `subagent_type: z-programmer-lite`, z-dev-team fails there. Check: one `devteam start` in a dsh session.
- UNVERIFIED: install-dsh.sh:86-87 and :107 say dsh truncates a body over 100KB and drops a description
  over 1024 characters; the dsh skill README states no size limit. Check: the dsh skill loader source.
- UNVERIFIED: SKILL.md:12-15 `allowed-tools` in the SKILL.md frontmatter. skill-criteria.md:20-21 says
  ZCode ignores unknown keys, and the bundled zcode-guide lists `allowed-tools` only for command files
  (diagnosing-commands/SKILL.md:34). If it is ignored, the three rules do nothing. Check: ZCode's skill loader.
- UNVERIFIED: SKILL.md:105 lists the `Agent` tool's parameters (`subagent_type`, `description`, `prompt`,
  `run_in_background`, no `model`). I ran as a subagent without that tool.
- UNVERIFIED: SKILL.md:106 assumes ZCode fires the `Stop` event for a background subagent, so guard.py
  writes the `.done`/`.blocked` marker. zcode-guide diagnosing-hooks/SKILL.md:26 confirms only that
  `SubagentStop` is unsupported. This repo holds no marker to show it. Check: one slice run, then
  `ls .claude/dev-team/slices/`.
- UNVERIFIED: SKILL.md:117, :150 and :227 name a built-in `Explore` agent type. The string `"Explore"`
  occurs 4 times in ZCode's zcode.cjs; I could not confirm it is a built-in subagent type.
- UNVERIFIED: SKILL.md:107 and :141 name `SendMessage` and `TaskStop`. `TaskStop` is in my own
  deferred-tool list; `SendMessage` is not, because I am a subagent.
- UNVERIFIED: install-zcode.sh:201 and :220 print "invoke $<name>"; I found no ZCode document for that syntax.
- UNVERIFIED: install-zcode.sh:428-429 and SKILL.md:108: skills, agents and commands load only in a new session.
- UNVERIFIED: handoff.py:282 "GUARD effort: keep high or max. low and disabled invent APIs and citations."
  The repo records that weakness for Flash lanes only (docs/specs/2026-11-05-flash-opus-quality.md:72-74:
  "the brainstorming lanes are Flash at low effort" ... "Low effort fabricates APIs."). If it is
  Flash-specific, criterion 3 needs the line to name the model. Whether GLM 5.3, DeepSeek V4 Pro or
  Claude Sonnet 5.5 also invent APIs at low effort is a model-behaviour claim I cannot check.
- UNVERIFIED: the Z.ai peak hours at devteam.py:80, :188, :501 and :3879 (source named at :501, no date) are still current.
- UNVERIFIED: whether any ZCode setup writes ~/.claude/projects (bears on F-9; on this machine it does not).
- UNVERIFIED: the default working directory of a GitHub `run` step. The workflow-syntax page I read does
  not state it; the actions/checkout README says "This action checks-out your repository under
  $GITHUB_WORKSPACE". The F-1 fix sets `working-directory`, so it holds either way.

Not graded here (outside this lane, or already owned by other work):

- [OUT-OF-SCOPE] AGENTS.md:15 "all four models" is in the same paragraph as the owned lines 9-14 but outside the quoted range.
- [OUT-OF-SCOPE] _shared/zai_client.py:7-8 enumerates five session models (no glm-5.4): the same class as the owned enumerations, but not in the named list.
- [OUT-OF-SCOPE] _shared/tests/test_all_skills.py:4 docstring says "skills/glm": the same stale path as F-10.
- [OUT-OF-SCOPE] z-dev-team/scripts/guard.py:3-25 docstring lists six hook modes and omits `zcode`, the only mode `doctor --fix` installs (guard.py:1610, devteam.py:5511).
- [OUT-OF-SCOPE] z-viral-video-studio/README.md:6 points at `./install.sh`, which is not in that folder.

## Checked and clean

Read in full, no finding:

- z-dev-team/agents/z-investigator.md - turn cap 24 matches SKILL.md:98; `handoff.py agents` lists it with write=.claude/dev-team/research/.
- z-dev-team/agents/z-programmer-lite.md, z-dev-team/agents/z-programmer-strong.md - they differ only in name, thoughtLevel (high / max) and maxTurns (40 / 48), both as SKILL.md:60-63 and :97-98 state; the isolation prefix at :88 equals devteam.py:1759.
- z-dev-team/commands/z-devteam.md - `$ARGUMENTS` is the documented placeholder (zcode-guide diagnosing-commands/SKILL.md:36); the installer fills `{{SKILL_DIR}}` itself.
- _shared/sync.sh - its four lists match the 22 vendored copies in the tree, and every copy is byte-identical to _shared/ (`cmp`).
- _shared/flash_pin.py - nothing outside the owned pin vocabulary.
- install-dsh.sh - usage line matches the parser; `--dry-run` prints `1495 files in 11 skill folders`; the home rule, bundle shape, nested-discovery rule, kebab-case name and required description match the dsh skill README I read.
- AGENTS.md - nothing outside the owned target paragraph: `../CLAUDE.md`, the docs/ entries, `test_vendored.py` and both commands exist, and the full suite passes on Python 3.12.16.
- z-dev-team/SKILL.md frontmatter and size - description 659 characters with the WHEN clause inside the first 250, 259 lines, 22023 bytes, name equals the folder.
- The six agent files - none carries a `model:` line; `thoughtLevel`, `maxTurns` and `injectAgentsMd` all occur in ZCode's zcode.cjs.
- Engine and handoff strings SKILL.md cites, each found by grep: `LAUNCH N`, `=== DISPATCH`, `=== REVIEW`, `=== INVESTIGATE`, `CHECKPOINT ... run in the BACKGROUND`, `RESEARCH RECORDED`, `REVIEW: programmers fill the window`, `BLOCKED <id>`, `NOT READY`, `MERGE ERROR`, `UNCLAIMED`, `PROOF FAILED`, `RED PROOF FAILED`, `LANE DOWN`, `SPAWN FAILED`, `RUNTIME LIMIT`, `THROTTLED`, `NOT INTEGRATED ... no claim recorded`, `CONFLICT`, `fix specs refused`, `DAG EXHAUSTED`, `FAST-DONE:`, `COMMIT and GITLAB`, `attempt/`, `verification.md`, `verification.report.md`, `atoms.json`, `probe.txt`, `DEVTEAM_PEAK`, `DEVTEAM_MAX_PARALLEL`, `DEVTEAM_PROOF_TIMEOUT`, `review_batch`, `checkpoint_every`, the `--tier`, `--files`, `--force`, `--shards` and `-n` flags; handoff `OPEN: routed`, `OPEN: stay`, `D=`, `AGENT`, `PROMPT`, `HANDOFF`, and the six exit names. The "seven-skill ring" is correct: RING has seven members.

Read in part (docstring, help, user-visible strings, the regions a check needed), no further finding:

- z-dev-team/scripts/devteam.py - `--help` and every subcommand `--help`; `plan-template`, `leader-prompt` and `doctor --harness zcode` ran read-only and printed what SKILL.md says (all six agents INSTALLED, hooks configured).
- _shared/handoff.py - docstring, lines 180-200, 742-850, 1100-1165, 1286-1340, 1665-1691; `call` and `agents` ran read-only.
- _shared/decide.py - docstring and `--help`; the four importers it names exist and import it.
- _shared/zai_client.py - docstring and `--help` (finding F-10 only).
- z-dev-team/scripts/guard.py - docstring, `guard_zcode`, `main`; routes on `agent_type` as SKILL.md:110 says.
- z-dev-team/scripts/selftest.sh - header and `bash -n` only (not run: it writes); no bash-4-only construct found.
- .github/workflows/skills.yml, install-zcode.sh, install-dsh.sh `--dry-run` against a non-existent home (nothing written).
