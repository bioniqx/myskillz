# OpenCode + GLM-5.3 Phase 2 Implementation Plan (dev-team port)

> **Execution note:** This plan is self-contained and tool-agnostic. Any AI
> agent or human engineer can execute it with only a shell, a code editor, and
> git. Follow the Execution Protocol below.

**Goal:** Make dev-team-glm run on OpenCode 1.18.x and v2: devteam.py launches every lane itself as an `opencode run` process in its own git worktree, a thin OpenCode plugin enforces the existing guard.py rules, and the governor and doctor read OpenCode-side signals, while the Claude Code path stays byte-for-byte unchanged.

**Architecture:** One seam in devteam.py (`emit_agent`) decides per harness: on Claude Code it prints the `Agent →` instruction exactly as today; on OpenCode it launches a detached `devteam.py lane-run <id>` process that creates/claims the worktree, runs the lane through the vendored `oc_harness.run_lanes`, then runs the existing `guard.py stop` gate with a synthesized payload so `.done`/`.blocked` markers and integration work unchanged. Tool-call enforcement moves into a new `guard.py oc` mode that translates OpenCode tool calls into the existing Claude-shaped checks; two tiny JS plugins (v1 and v2 plugin APIs) only forward calls to it.

**Tech Stack:** Python 3 standard library, POSIX sh, JavaScript (OpenCode plugin, Bun/Node runtime, `node:child_process`), git worktrees, OpenCode 1.18.x and v2, Z.ai GLM-5.3 / GLM-5.3-Flash.

## Execution Protocol (for any AI agent or human engineer)

1. A task may start only when every task in its **Depends** and **Runs after**
   lists is complete. Single worker: run tasks in ID order.
2. Parallel workers: follow **Execution Waves**. Tasks in the same wave touch
   disjoint files and MAY run concurrently (marked `[P]`). Never run two tasks
   that modify the same file at once.
3. Within a task, execute steps top to bottom and mark each checkbox `- [x]`
   when done. To resume, continue from the first unchecked step.
4. Run every command exactly as written and compare with **Expected**. On
   mismatch, stop and fix before continuing.
5. Code blocks are the implementation - copy them verbatim. Signatures under
   **Interfaces** are contracts with other tasks: never rename, reorder
   parameters, or change types.
6. Commit exactly where the plan says, with the given message, staging only the
   listed paths. Never batch commits across tasks.
7. **Global Constraints** apply to every task.
8. If anything is ambiguous, missing, or contradicts the codebase, STOP and ask
   the requester. Do not invent behavior.

## Global Constraints

- Prerequisite: the Phase 1 plan `docs/superpowers/plans/2026-09-25-opencode-glm-phase1.md` is fully implemented (`skills/glm/_shared/zai_client.py`, `skills/glm/_shared/oc_harness.py`, `skills/glm/_shared/sync.sh`, vendored copies, `skills/glm/install-opencode.sh` exist and the suite passes).
- Run every command from the git root `/Users/yamazaki-ethan/.claude`; every path in this plan is relative to it.
- Python test suite: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -v`. dev-team end-to-end suite: `bash skills/glm/dev-team-glm/scripts/selftest.sh` (exit 0 = all pass).
- Python 3 standard library only; shell is POSIX `sh`/`bash` as the existing selftest uses; plugins use only `node:child_process` and `node:path` (both available in Bun); no network access in tests.
- All file content is English. Code is minimal and readable; comments few and short; match the surrounding style of devteam.py and guard.py.
- The Claude Code path must not change behaviour or output: every existing selftest check keeps passing and `print_dispatch` output is byte-identical when the harness is not OpenCode.
- The OpenCode path is active only when env `DEVTEAM_HARNESS` equals `opencode`, or when `DEVTEAM_HARNESS` is unset and env `OPENCODE` is set to a non-empty value.
- OpenCode agent names equal the existing dev-team agent names: `programmer`, `code-reviewer`, `spot-reviewer`, `investigator`, `team-leader`. Model aliases map `haiku` → neutral `flash` (`glm-5.3-flash`) and `sonnet`/`opus` → neutral `pro` (`glm-5.3`); provider id is `zai-coding-plan`.
- Every OpenCode lane process gets env `DEVTEAM_ROLE=<agent name>` and `DEVTEAM_SLICE=<lane id>` through the lane dict key `env`.
- OpenCode worktrees live at `<root>/.claude/dev-team/wt/<lane id>` on branch `devteam/<lane id>`, created from the slice's recorded base with `git worktree add`; the programmer's brief is the stdout of `python3 <devteam.py> claim <lane id>` run inside that worktree.
- Lane outputs go to `<root>/.claude/dev-team/lanes/` (`<id>.jsonl`, `<id>.err`, `<id>.done` as written by `oc_harness.run_lanes`); the dev-team completion markers stay where they are today (`<root>/.claude/dev-team/slices/<id>.done|.blocked`, written only by `guard.py stop`).
- Stop gate on OpenCode: after a programmer lane process exits, `lane-run` pipes `{"cwd": <worktree>, "last_assistant_message": <final assistant text>}` into `python3 guard.py stop`; exit 2 means blocked, so the lane is re-run once per block with the gate's stderr appended to the brief, until guard.py writes `.done` or `.blocked` (it force-finishes after `MAX_STOP_BLOCKS = 2`).
- `devteam.py wait` blocks at most `--timeout` seconds (default 100, below OpenCode's 120 s bash-tool default) until a new marker or lane result appears, then prints `NEXT: devteam next`.
- OpenCode tool calls seen by the plugin (v1 names): `edit` args `{filePath, oldString, newString}`, `write` `{filePath, content}`, `patch` or `apply_patch` `{patchText}` whose paths are the lines `*** Add File: <p>`, `*** Update File: <p>`, `*** Delete File: <p>`, `bash` `{command}`. `guard.py oc` maps edit/write/patch to the Claude `tool_input.file_path` shape and bash to `tool_input.command`; any other tool is allowed silently.
- `guard.py oc` mode choice: role `programmer` → existing `edit`/`bash` checks; any other role → `edit-ro`/`bash-ro` with `agent_type` set to the role; no role → silent allow. Output format is the existing `hookSpecificOutput` JSON (silent allow prints nothing).
- Plugins are a no-op unless `process.env.DEVTEAM_ROLE` is set; they call `python3 <skill>/scripts/guard.py oc` with JSON on stdin (`{{SKILL_DIR}}` replaced at install) and throw `new Error(reason)` when the printed decision is `deny`; any plugin-side failure allows the call (same fail-open rule as guard.py).
- v1 plugin shape: `export const DevteamGuard = async ({ directory }) => ({ "tool.execute.before": async (input, output) => { ... } })` with `input.tool` and `output.args`. v2 plugin shape (from opencode.ai/v2/docs/build/plugins, unverified until the manual v2 run): `import { Plugin } from "@opencode/plugin"` and `export default Plugin.define({ id: "devteam-guard", setup: (ctx) => ({ "tool.execute.before": async (input, output) => { ... } }) })`, with the working directory from `ctx.location.directory`.
- Plugin sources live in `skills/glm/dev-team-glm/opencode/plugins/<base>.v1.js` and `<base>.v2.js`; `oc_harness.install` copies the one matching the major to `<home>/.config/opencode/plugins/<base>.js`.
- Edit shared code only in `skills/glm/_shared/`, then run `sh skills/glm/_shared/sync.sh`; never edit a vendored copy directly.
- Neutral agent source format and install rules are the Phase 1 ones (frontmatter keys `description`, `model`, `effort`, `temperature`, `access`, `bash`, `web`, `steps`; commands with `description` only and `{{SKILL_DIR}}`/`$ARGUMENTS`).
- `skills/glm/dev-team-glm/SKILL.md` frontmatter `name` becomes `dev-team`; keep its `allowed-tools` and every Claude Code section.
- Do not edit anything outside `skills/glm/` except this plan; never touch `skills/dev-team-v3.2/`.
- Commit per task with `git add` of that task's files only (the working tree has unrelated changes).

## File Structure

- `skills/glm/_shared/` — oc_harness.py (T01)
- `skills/glm/_shared/tests/` — test_oc_env_plugins.py (T01), test_guard_oc.py (T02), test_devteam_plugins.py (T03), test_devteam_oc_lanes.py (T05), test_devteam_oc_doctor.py (T06), test_all_skills.py (T09)
- `skills/glm/systematic-debugging-glm/scripts/` — oc_harness.py (T01)
- `skills/glm/writing-plans-glm/scripts/` — oc_harness.py (T01)
- `skills/glm/requirements-code-audit-glm/scripts/` — oc_harness.py (T01)
- `skills/glm/brainstorming-glm/scripts/` — oc_harness.py (T01)
- `skills/glm/doc-generator-glm/scripts/` — oc_harness.py (T01)
- `skills/glm/dev-team-glm/scripts/` — oc_harness.py (T01), guard.py (T02), devteam.py (T05, T06), selftest.sh (T08)
- `skills/glm/dev-team-glm/opencode/plugins/` — devteam-guard.v1.js (T03), devteam-guard.v2.js (T03)
- `skills/glm/dev-team-glm/opencode/agents/` — programmer.md (T04), code-reviewer.md (T04), spot-reviewer.md (T04), investigator.md (T04), team-leader.md (T04)
- `skills/glm/dev-team-glm/opencode/commands/` — devteam.md (T04)
- `skills/glm/dev-team-glm/` — SKILL.md (T07), README.md (T07)
- `skills/glm/` — install-opencode.sh (T09), CLAUDE.md (T09)

## Contracts

#### T01: Lane env and plugin install in oc_harness
- Files: `skills/glm/_shared/oc_harness.py`, `skills/glm/_shared/tests/test_oc_env_plugins.py`, `skills/glm/systematic-debugging-glm/scripts/oc_harness.py`, `skills/glm/writing-plans-glm/scripts/oc_harness.py`, `skills/glm/requirements-code-audit-glm/scripts/oc_harness.py`, `skills/glm/brainstorming-glm/scripts/oc_harness.py`, `skills/glm/doc-generator-glm/scripts/oc_harness.py`, `skills/glm/dev-team-glm/scripts/oc_harness.py`
- Produces: `def run_lanes(lanes: list, out_dir: str, width: int = 8, stall: int = 180, binary: str = "opencode", major: int = 0) -> list` (a lane may carry `env: dict`, merged over `os.environ` for that process); `def install(skill_dir: str, major: int, home: str = "") -> list` (also installs `opencode/plugins/<base>.v<major>.js` as `<home>/.config/opencode/plugins/<base>.js` with `{{SKILL_DIR}}` replaced)
- Read: `docs/superpowers/plans/2026-09-25-opencode-glm-phase1.md`
- Spec: L89-105, L143-148
- Tier: light

#### T02: guard.py oc mode
- Files: `skills/glm/dev-team-glm/scripts/guard.py`, `skills/glm/_shared/tests/test_guard_oc.py`
- Read: `skills/glm/dev-team-glm/agents/programmer.md`
- Produces: `def guard_oc(inp)`; CLI `python3 guard.py oc` reading `{"tool": str, "args": dict, "cwd": str, "role": str}` on stdin
- Spec: L143-148, L159-169
- Tier: deep

#### T03: OpenCode guard plugins (v1 and v2)
- Depends: T02
- Files: `skills/glm/dev-team-glm/opencode/plugins/devteam-guard.v1.js`, `skills/glm/dev-team-glm/opencode/plugins/devteam-guard.v2.js`, `skills/glm/_shared/tests/test_devteam_plugins.py`
- Produces: `devteam-guard.v1.js` exporting `DevteamGuard`; `devteam-guard.v2.js` default-exporting `Plugin.define({ id: "devteam-guard", setup })`; both call `guard.py oc` and throw on deny
- Spec: L143-148, L159-169

#### T04: Neutral dev-team agents and /devteam command
- Files: `skills/glm/dev-team-glm/opencode/agents/programmer.md`, `skills/glm/dev-team-glm/opencode/agents/code-reviewer.md`, `skills/glm/dev-team-glm/opencode/agents/spot-reviewer.md`, `skills/glm/dev-team-glm/opencode/agents/investigator.md`, `skills/glm/dev-team-glm/opencode/agents/team-leader.md`, `skills/glm/dev-team-glm/opencode/commands/devteam.md`
- Produces: five neutral agent sources whose bodies are the matching `skills/glm/dev-team-glm/agents/*.md` prompts without Claude-only frontmatter; `/devteam` command source
- Read: `skills/glm/dev-team-glm/agents/programmer.md`, `skills/glm/dev-team-glm/agents/code-reviewer.md`, `skills/glm/dev-team-glm/agents/spot-reviewer.md`, `skills/glm/dev-team-glm/agents/investigator.md`, `skills/glm/dev-team-glm/agents/team-leader.md`
- Spec: L107-120, L143-148
- Tier: light

#### T05: devteam.py OpenCode lane launcher
- Depends: T01, T02, T04
- Files: `skills/glm/dev-team-glm/scripts/devteam.py`, `skills/glm/_shared/tests/test_devteam_oc_lanes.py`
- Read: `docs/superpowers/plans/2026-09-25-opencode-glm-phase1.md`, `skills/glm/dev-team-glm/scripts/guard.py`
- Produces: `def is_opencode() -> bool`; `def emit_agent(root, st, agent, model, prompt, label) -> str`; `def launch_lane(root, st, lane_id, agent, model, prompt) -> int`; `def cmd_lane_run(a)`; `def cmd_wait(a)`; CLI `devteam.py lane-run <lane_id>` and `devteam.py wait [--timeout 100]`
- Spec: L93-105, L143-148, L150-169
- Tier: deep

#### T06: devteam.py governor signals and doctor for OpenCode
- Depends: T05
- Files: `skills/glm/dev-team-glm/scripts/devteam.py`, `skills/glm/_shared/tests/test_devteam_oc_doctor.py`
- Read: `docs/superpowers/plans/2026-09-25-opencode-glm-phase1.md`
- Produces: `def lane_signals(root, st) -> dict`; `def cmd_doctor(a)` gains `--harness opencode` checks and `--fix` via `oc_harness.install`
- Spec: L121-129, L143-148, L159-169
- Tier: deep

#### T07: dev-team SKILL.md and README for OpenCode
- Depends: T05, T06
- Files: `skills/glm/dev-team-glm/SKILL.md`, `skills/glm/dev-team-glm/README.md`
- Produces: SKILL.md `name: dev-team` with an OpenCode protocol section (`start` → loop `wait`/`next`, `retry`, stuck-lane handling); README (Vietnamese, matching its current language) section for OpenCode install and flow
- Spec: L107-120, L143-148
- Tier: light

#### T08: selftest end-to-end checks for the OpenCode path
- Depends: T03, T05, T06
- Files: `skills/glm/dev-team-glm/scripts/selftest.sh`
- Produces: selftest checks that run `start`/`wait`/`next` with `DEVTEAM_HARNESS=opencode` against a stub `opencode` on `PATH` (worktree created and claimed, lane-run writes `.done` through `guard.py stop`, integration merges, a 1302 throttle row shrinks the governor window, `guard.py oc` denies an out-of-footprint edit)
- Read: `docs/superpowers/plans/2026-09-25-opencode-glm-phase1.md`, `skills/glm/dev-team-glm/scripts/selftest.sh`
- Spec: L170-185

#### T09: Installer, all-skill test and repo guide include dev-team
- Depends: T01, T04, T07
- Files: `skills/glm/install-opencode.sh`, `skills/glm/_shared/tests/test_all_skills.py`, `skills/glm/CLAUDE.md`
- Produces: `install-opencode.sh` also installs `dev-team-glm` (agents, command and the plugin for the detected major); `test_all_skills.py` covers dev-team; CLAUDE.md documents the OpenCode flow and plugin
- Spec: L107-120, L186-194
- Tier: light

<!-- WAVES -->
## Execution Waves

Every task in a wave has all its Depends/Runs-after tasks in earlier waves. Tasks in the
same wave touch disjoint files, so a wave's `[P]` tasks may all run at once.

- **Wave 1:** T01 [P], T02 [P], T04 [P]
- **Wave 2:** T03 [P], T05 [P]
- **Wave 3:** T06
- **Wave 4:** T07 [P], T08 [P]
- **Wave 5:** T09
<!-- /WAVES -->

<!-- TASKS -->

### T01: Lane env and plugin install in oc_harness [P]

**Depends:** —

**Interfaces:**
- Produces: `def run_lanes(lanes: list, out_dir: str, width: int = 8, stall: int = 180, binary: str = "opencode", major: int = 0) -> list`; `env: dict`; `os.environ`; `def install(skill_dir: str, major: int, home: str = "") -> list`; `opencode/plugins/<base>.v<major>.js`; `<home>/.config/opencode/plugins/<base>.js`; `{{SKILL_DIR}}`

**Files:**
- Modify: `skills/glm/_shared/oc_harness.py`
- Create: `skills/glm/_shared/tests/test_oc_env_plugins.py`
- Modify: `skills/glm/systematic-debugging-glm/scripts/oc_harness.py`
- Modify: `skills/glm/writing-plans-glm/scripts/oc_harness.py`
- Modify: `skills/glm/requirements-code-audit-glm/scripts/oc_harness.py`
- Modify: `skills/glm/brainstorming-glm/scripts/oc_harness.py`
- Modify: `skills/glm/doc-generator-glm/scripts/oc_harness.py`
- Modify: `skills/glm/dev-team-glm/scripts/oc_harness.py`

The six `scripts/oc_harness.py` files are vendored copies: they change only through `sh skills/glm/_shared/sync.sh` in Step 7, never by hand.

After this task a lane may carry `env: dict`, merged over `os.environ` for that process, and `install` also installs `opencode/plugins/<base>.v<major>.js` as `<home>/.config/opencode/plugins/<base>.js` with `{{SKILL_DIR}}` replaced.

- [ ] **Step 1: Write the failing tests for lane env and plugin install**

Create `skills/glm/_shared/tests/test_oc_env_plugins.py`:

```python
import os
import shutil
import stat
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import oc_harness

FAKE_OPENCODE = """#!/bin/sh
if [ "$1" = "--version" ]; then echo 1.18.32; exit 0; fi
printf '%s' "$DEVTEAM_ROLE" > "$ENV_OUT"
echo '{"type":"text","part":{"text":"done"}}'
"""


class LaneEnvTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-env-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.binary = os.path.join(self.tmp, "opencode")
        with open(self.binary, "w") as fh:
            fh.write(FAKE_OPENCODE)
        os.chmod(self.binary, os.stat(self.binary).st_mode | stat.S_IEXEC)

    def test_lane_env_reaches_the_process(self):
        env_out = os.path.join(self.tmp, "role.txt")
        lane = {"id": "a", "agent": "programmer", "model": "flash", "dir": self.tmp, "brief": "go",
                "env": {"DEVTEAM_ROLE": "programmer", "ENV_OUT": env_out}}
        rows = oc_harness.run_lanes([lane], os.path.join(self.tmp, "out"), binary=self.binary, major=1)
        self.assertEqual(rows[0]["status"], "OK")
        with open(env_out) as fh:
            self.assertEqual(fh.read(), "programmer")
        self.assertNotIn("DEVTEAM_ROLE", os.environ)


class PluginInstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="oc-plugin-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.skill = os.path.join(self.tmp, "dev-team-glm")
        os.makedirs(os.path.join(self.skill, "opencode", "plugins"))
        with open(os.path.join(self.skill, "SKILL.md"), "w") as fh:
            fh.write("---\nname: dev-team\ndescription: test\n---\nbody\n")
        for major in (1, 2):
            path = os.path.join(self.skill, "opencode", "plugins", "devteam-guard.v%d.js" % major)
            with open(path, "w") as fh:
                fh.write("// v%d\nconst GUARD = '{{SKILL_DIR}}/scripts/guard.py'\n" % major)
        self.home = os.path.join(self.tmp, "home")
        self.plugins = os.path.join(self.home, ".config", "opencode", "plugins")
        self.skill_dst = os.path.join(self.home, ".config", "opencode", "skills", "dev-team")

    def installed_plugin(self):
        with open(os.path.join(self.plugins, "devteam-guard.js")) as fh:
            return fh.read()

    def test_installs_the_plugin_matching_the_major(self):
        written = oc_harness.install(self.skill, 2, self.home)
        self.assertIn(os.path.join(self.plugins, "devteam-guard.js"), written)
        text = self.installed_plugin()
        self.assertIn("// v2", text)
        self.assertIn(self.skill_dst + "/scripts/guard.py", text)
        self.assertNotIn("{{SKILL_DIR}}", text)
        self.assertEqual(os.listdir(self.plugins), ["devteam-guard.js"])

    def test_v1_install_uses_the_v1_source(self):
        oc_harness.install(self.skill, 1, self.home)
        self.assertIn("// v1", self.installed_plugin())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_oc_env_plugins.py -v`
Expected: FAIL: `test_lane_env_reaches_the_process` errors with `FileNotFoundError` for `role.txt` (the fake binary's `$ENV_OUT` is empty, so nothing is written there) and both plugin tests error with `FileNotFoundError` for `devteam-guard.js`

- [ ] **Step 3: Pass the lane env to the lane process**

`run_lanes` keeps its signature `def run_lanes(lanes: list, out_dir: str, width: int = 8, stall: int = 180, binary: str = "opencode", major: int = 0) -> list`; only its helper `_start_lane` changes. In `skills/glm/_shared/oc_harness.py`, inside `def _start_lane(lane, out_dir, major, binary, width):`, replace:

```python fragment
    proc = subprocess.Popen(build_run_cmd(lane, major, binary), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=err_file, text=True, bufsize=1)
```

with:

```python fragment
    env = dict(os.environ)
    env.update({k: str(v) for k, v in (lane.get("env") or {}).items()})
    proc = subprocess.Popen(build_run_cmd(lane, major, binary), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=err_file, text=True, bufsize=1, env=env)
```

- [ ] **Step 4: Install the plugin that matches the major**

In `def install(skill_dir: str, major: int, home: str = "") -> list:`, insert this block directly before the line `    marker = os.path.join(skill_dst, ".oc-major")`:

```python fragment
    plugins_src = os.path.join(skill_dir, "opencode", "plugins")
    suffix = ".v%d.js" % major
    if os.path.isdir(plugins_src):
        plugins_dst = os.path.join(root, "plugins")
        os.makedirs(plugins_dst, exist_ok=True)
        for fname in sorted(os.listdir(plugins_src)):
            if not fname.endswith(suffix):
                continue
            with open(os.path.join(plugins_src, fname)) as fh:
                text = fh.read().replace("{{SKILL_DIR}}", skill_dst)
            path = os.path.join(plugins_dst, fname[:-len(suffix)] + ".js")
            with open(path, "w") as fh:
                fh.write(text)
            written.append(path)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_oc_env_plugins.py -v`
Expected: PASS, `Ran 3 tests` and `OK`

- [ ] **Step 6: Run the whole suite**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -v`
Expected: FAIL only in `test_vendored` (the vendored copies still hold the old `oc_harness.py`); every other test passes

- [ ] **Step 7: Refresh the vendored copies and re-run the suite**

Run: `sh skills/glm/_shared/sync.sh && python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -v`
Expected: one `synced <path>` line per vendored copy, then PASS with `OK`

- [ ] **Step 8: Commit**

```bash
git add skills/glm/_shared/oc_harness.py skills/glm/_shared/tests/test_oc_env_plugins.py skills/glm/systematic-debugging-glm/scripts/oc_harness.py skills/glm/writing-plans-glm/scripts/oc_harness.py skills/glm/requirements-code-audit-glm/scripts/oc_harness.py skills/glm/brainstorming-glm/scripts/oc_harness.py skills/glm/doc-generator-glm/scripts/oc_harness.py skills/glm/dev-team-glm/scripts/oc_harness.py
git commit -m "feat: lane env and plugin install in oc_harness"
```

---

### T02: guard.py oc mode [P]

**Depends:** —

**Interfaces:**
- Produces: `def guard_oc(inp)`; `python3 guard.py oc`; `{"tool": str, "args": dict, "cwd": str, "role": str}`

**Files:**
- Modify: `skills/glm/dev-team-glm/scripts/guard.py`
- Test: `skills/glm/_shared/tests/test_guard_oc.py`

`python3 guard.py oc` is the bridge between the OpenCode plugins and the existing Claude-shaped checks. It reads `{"tool": str, "args": dict, "cwd": str, "role": str}` on stdin, maps OpenCode tool calls to the `tool_input` shape the existing guards read, and prints the existing `hookSpecificOutput` JSON (a silent allow prints nothing). Role `programmer` uses `guard_edit`/`guard_bash`. Any other role uses `guard_edit_ro`/`guard_bash_ro`, with `agent_type` set to the role. No role means a silent allow. A patch can touch several files, so each file is checked and the first deny wins.

- [ ] **Step 1: Write the failing tests**

Create `skills/glm/_shared/tests/test_guard_oc.py`:

```python
import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[2] / "dev-team-glm" / "scripts" / "guard.py"


def run_oc(payload):
    r = subprocess.run([sys.executable, str(GUARD), "oc"], input=json.dumps(payload),
                       capture_output=True, text=True)
    return r.returncode, r.stdout


def decision(out):
    if not out.strip():
        return "", ""
    hso = json.loads(out)["hookSpecificOutput"]
    return hso["permissionDecision"], hso["permissionDecisionReason"]


class GuardOcTest(unittest.TestCase):
    def setUp(self):
        self.wt = Path(tempfile.mkdtemp()).resolve()
        sd = self.wt / ".slice"
        sd.mkdir()
        (sd / "id").write_text("S1\n")
        (sd / "footprint").write_text("src/\n")

    def tearDown(self):
        shutil.rmtree(self.wt, ignore_errors=True)

    def oc(self, tool, args, role="programmer"):
        return run_oc({"tool": tool, "args": args, "cwd": str(self.wt), "role": role})

    def test_no_role_is_silent_allow(self):
        rc, out = self.oc("write", {"filePath": "docs/x.md", "content": "x"}, role="")
        self.assertEqual((rc, out), (0, ""))

    def test_unknown_tool_is_silent_allow(self):
        rc, out = self.oc("read", {"filePath": "docs/x.md"})
        self.assertEqual((rc, out), (0, ""))

    def test_bad_json_is_silent_allow(self):
        r = subprocess.run([sys.executable, str(GUARD), "oc"], input="not json",
                           capture_output=True, text=True)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_programmer_edit_inside_footprint_allows(self):
        rc, out = self.oc("edit", {"filePath": "src/a.py", "oldString": "a", "newString": "b"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out), ("allow", "dev-team: `src/a.py` is inside the slice footprint"))

    def test_programmer_write_outside_footprint_denies(self):
        rc, out = self.oc("write", {"filePath": str(self.wt / "docs" / "x.md"), "content": "x"})
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("`docs/x.md` is outside your slice footprint", reason)

    def test_programmer_patch_first_deny_wins(self):
        patch = ("*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n"
                 "*** Add File: docs/b.md\n+hi\n*** End Patch\n")
        rc, out = self.oc("apply_patch", {"patchText": patch})
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("docs/b.md", reason)

    def test_programmer_patch_inside_footprint_allows(self):
        patch = ("*** Begin Patch\n*** Update File: src/a.py\n@@\n-x\n+y\n"
                 "*** Delete File: src/old.py\n*** End Patch\n")
        rc, out = self.oc("patch", {"patchText": patch})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "allow")

    def test_programmer_bash_push_denies(self):
        rc, out = self.oc("bash", {"command": "git push origin main"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out)[0], "deny")

    def test_programmer_bash_read_only_git_allows(self):
        rc, out = self.oc("bash", {"command": "git status"})
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out), ("allow", "dev-team: pre-approved — read-only git"))

    def test_reviewer_write_source_denies(self):
        rc, out = self.oc("write", {"filePath": "src/a.py", "content": "x"}, role="code-reviewer")
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("This role is read-only", reason)

    def test_reviewer_write_review_allows(self):
        path = self.wt / ".claude" / "dev-team" / "reviews" / "r.md"
        rc, out = self.oc("write", {"filePath": str(path), "content": "x"}, role="code-reviewer")
        self.assertEqual(rc, 0)
        self.assertEqual(decision(out), ("allow", "dev-team: this role's own report / memory file"))

    def test_leader_role_becomes_agent_type(self):
        path = str(self.wt / ".claude" / "dev-team" / "plan.md")
        _, out = self.oc("write", {"filePath": path, "content": "x"}, role="team-leader")
        self.assertEqual(decision(out), ("allow", "dev-team: the team-leader's plan"))
        _, out = self.oc("write", {"filePath": path, "content": "x"}, role="spot-reviewer")
        self.assertEqual(decision(out)[0], "deny")

    def test_reviewer_bash_rm_denies(self):
        rc, out = self.oc("bash", {"command": "rm -rf src"}, role="investigator")
        self.assertEqual(rc, 0)
        verdict, reason = decision(out)
        self.assertEqual(verdict, "deny")
        self.assertIn("Read-only role", reason)

    def test_guard_oc_function_no_role(self):
        spec = importlib.util.spec_from_file_location("devteam_guard", GUARD)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), self.assertRaises(SystemExit) as cm:
            mod.guard_oc({"tool": "bash", "args": {"command": "git push"}, "cwd": str(self.wt), "role": ""})
        self.assertIn(cm.exception.code, (0, None))
        self.assertEqual(buf.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_guard_oc.py -v`
Expected: FAIL. The summary line is `FAILED (failures=10, errors=1)`. The error is `AttributeError: module 'devteam_guard' has no attribute 'guard_oc'`. The failures are the allow/deny assertions, because the unknown `oc` mode currently allows every call silently.

- [ ] **Step 3: Add the `io` import**

In `skills/glm/dev-team-glm/scripts/guard.py`, change the import block at the top of the file (lines 26-34) so that it reads:

```python
import fnmatch
import io
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
```

- [ ] **Step 4: Add the OpenCode bridge**

In `skills/glm/dev-team-glm/scripts/guard.py`, insert this block directly above `def main():`, after the end of `guard_bash_ro`:

```python
OC_PATCH_PATH = re.compile(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)$", re.M)


def oc_patch_paths(text):
    return [p.strip() for p in OC_PATCH_PATH.findall(text or "") if p.strip()]


def oc_capture(check, inp):
    """Run one Claude-shaped check and return what it printed (it always ends in sys.exit)."""
    buf = io.StringIO()
    old, sys.stdout = sys.stdout, buf
    try:
        check(inp)
    except SystemExit:
        pass
    finally:
        sys.stdout = old
    return buf.getvalue()


def guard_oc(inp):
    """OpenCode plugin bridge: {"tool", "args", "cwd", "role"} -> the existing check for that role."""
    role = (inp.get("role") or "").strip()
    if not role:
        allow()
    tool = (inp.get("tool") or "").lower()
    args = inp.get("args") or {}
    prog = role == "programmer"
    base = {"cwd": inp.get("cwd") or os.getcwd(), "agent_type": role}
    if tool == "bash":
        (guard_bash if prog else guard_bash_ro)(dict(base, tool_input={"command": args.get("command") or ""}))
    if tool in ("edit", "write"):
        paths = [args.get("filePath") or ""]
    elif tool in ("patch", "apply_patch"):
        paths = oc_patch_paths(args.get("patchText"))
    else:
        allow()
    check = guard_edit if prog else guard_edit_ro
    out = ""
    for p in paths:
        out = oc_capture(check, dict(base, tool_input={"file_path": p}))
        if '"permissionDecision": "deny"' in out:
            break
    if out:
        sys.stdout.write(out)
    allow()
```

- [ ] **Step 5: Register the `oc` mode and document it**

In `skills/glm/dev-team-glm/scripts/guard.py`, replace the whole `def main():` function with:

```python
def main():
    if len(sys.argv) < 2:
        allow()
    mode = sys.argv[1]
    try:
        inp = json.load(sys.stdin)
    except Exception:
        allow()
    try:
        {"edit": guard_edit, "bash": guard_bash, "stop": guard_stop, "perm": guard_perm,
         "edit-ro": guard_edit_ro, "bash-ro": guard_bash_ro, "oc": guard_oc}.get(mode, lambda i: allow())(inp)
    except SystemExit:
        raise
    except Exception:
        allow()  # fail-open
```

In the module docstring, insert these lines directly after the two `guard.py perm` lines and before the blank line that precedes `Fail-open by design`:

```text
  guard.py oc       OpenCode plugin bridge: {"tool", "args", "cwd", "role"} on stdin. edit/write/patch map to
                    tool_input.file_path, bash to tool_input.command. Role programmer -> edit/bash, any other
                    role -> edit-ro/bash-ro with agent_type = role, no role -> silent allow.
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_guard_oc.py -v`
Expected: PASS. The output ends with `Ran 14 tests` followed by `OK`.

- [ ] **Step 7: Run the full suites to confirm the Claude Code path did not change**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -v && bash skills/glm/dev-team-glm/scripts/selftest.sh`
Expected: PASS. The unittest output ends with `OK`, and the selftest exits 0 with every check passing.

- [ ] **Step 8: Commit**

```bash
git add skills/glm/dev-team-glm/scripts/guard.py skills/glm/_shared/tests/test_guard_oc.py
git commit -m "feat(dev-team-glm): guard.py oc mode bridging OpenCode tool calls to the existing checks"
```

---

### T03: OpenCode guard plugins (v1 and v2) [P]

**Depends:** T02

**Interfaces:**
- Consumes: `def guard_oc(inp)`; `python3 guard.py oc`; `{"tool": str, "args": dict, "cwd": str, "role": str}`
- Produces: `devteam-guard.v1.js`; `DevteamGuard`; `devteam-guard.v2.js`; `Plugin.define({ id: "devteam-guard", setup })`; `guard.py oc`

**Files:**
- Create: `skills/glm/dev-team-glm/opencode/plugins/devteam-guard.v1.js`
- Create: `skills/glm/dev-team-glm/opencode/plugins/devteam-guard.v2.js`
- Test: `skills/glm/_shared/tests/test_devteam_plugins.py`

- [ ] **Step 1: Write the failing tests**

```python
import json
import os
import subprocess
import tempfile
import textwrap
import unittest

REPO_ROOT = os.getcwd()
PLUGIN_DIR = os.path.join(REPO_ROOT, "skills/glm/dev-team-glm/opencode/plugins")
V1_PATH = os.path.join(PLUGIN_DIR, "devteam-guard.v1.js")
V2_PATH = os.path.join(PLUGIN_DIR, "devteam-guard.v2.js")


def _write_guard_stub(skill_dir, decision):
    scripts_dir = os.path.join(skill_dir, "scripts")
    os.makedirs(scripts_dir, exist_ok=True)
    guard_path = os.path.join(scripts_dir, "guard.py")
    with open(guard_path, "w") as f:
        f.write(
            "import json\nimport sys\n\nsys.stdin.read()\nprint(json.dumps(%s))\n"
            % json.dumps(decision)
        )
    return guard_path


def _load_plugin_source(path, skill_dir):
    with open(path) as f:
        source = f.read()
    return source.replace("{{SKILL_DIR}}", skill_dir)


def _run_v1(tmp_dir, skill_dir, role, tool, args):
    source = _load_plugin_source(V1_PATH, skill_dir)
    plugin_path = os.path.join(tmp_dir, "plugin.mjs")
    with open(plugin_path, "w") as f:
        f.write(source)
    driver_path = os.path.join(tmp_dir, "driver.mjs")
    driver = textwrap.dedent(
        """\
        import { DevteamGuard } from "%s";
        const hooks = await DevteamGuard({ directory: "/tmp/work" });
        try {
          await hooks["tool.execute.before"](
            { tool: "%s" },
            { args: %s }
          );
          process.stdout.write("ALLOWED");
        } catch (err) {
          process.stdout.write("DENIED:" + err.message);
        }
        """
    ) % (plugin_path, tool, json.dumps(args))
    with open(driver_path, "w") as f:
        f.write(driver)
    env = dict(os.environ)
    if role is None:
        env.pop("DEVTEAM_ROLE", None)
    else:
        env["DEVTEAM_ROLE"] = role
    return subprocess.run(
        ["node", driver_path], capture_output=True, text=True, env=env, timeout=30
    )


def _run_v2(tmp_dir, skill_dir, role, tool, args):
    source = _load_plugin_source(V2_PATH, skill_dir)
    node_modules = os.path.join(tmp_dir, "node_modules", "@opencode", "plugin")
    os.makedirs(node_modules, exist_ok=True)
    with open(os.path.join(node_modules, "package.json"), "w") as f:
        f.write(
            json.dumps(
                {
                    "name": "@opencode/plugin",
                    "version": "0.0.0",
                    "type": "module",
                    "main": "index.mjs",
                }
            )
        )
    with open(os.path.join(node_modules, "index.mjs"), "w") as f:
        f.write("export const Plugin = { define: (config) => config };\n")
    plugin_path = os.path.join(tmp_dir, "plugin.mjs")
    with open(plugin_path, "w") as f:
        f.write(source)
    driver_path = os.path.join(tmp_dir, "driver.mjs")
    driver = textwrap.dedent(
        """\
        import plugin from "%s";
        const hooks = plugin.setup({ location: { directory: "/tmp/work" } });
        try {
          await hooks["tool.execute.before"](
            { tool: "%s" },
            { args: %s }
          );
          process.stdout.write("ALLOWED");
        } catch (err) {
          process.stdout.write("DENIED:" + err.message);
        }
        """
    ) % (plugin_path, tool, json.dumps(args))
    with open(driver_path, "w") as f:
        f.write(driver)
    env = dict(os.environ)
    if role is None:
        env.pop("DEVTEAM_ROLE", None)
    else:
        env["DEVTEAM_ROLE"] = role
    return subprocess.run(
        ["node", driver_path], capture_output=True, text=True, env=env, timeout=30
    )


class TestDevteamPlugins(unittest.TestCase):
    def test_v1_denies_and_throws(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_guard_stub(
                skill_dir,
                {
                    "hookSpecificOutput": {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "blocked command",
                    }
                },
            )
            result = _run_v1(
                tmp_dir, skill_dir, "programmer", "bash", {"command": "rm -rf /"}
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "DENIED:blocked command")

    def test_v1_allows_when_decision_is_allow(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_guard_stub(skill_dir, {})
            result = _run_v1(tmp_dir, skill_dir, "programmer", "bash", {"command": "ls"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED")

    def test_v1_fails_open_without_role(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            guard_path = _write_guard_stub(
                skill_dir,
                {
                    "hookSpecificOutput": {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "should never run",
                    }
                },
            )
            os.remove(guard_path)
            result = _run_v1(tmp_dir, skill_dir, None, "bash", {"command": "ls"})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "ALLOWED")

    def test_v2_denies_and_throws(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            skill_dir = os.path.join(tmp_dir, "skill")
            _write_guard_stub(
                skill_dir,
                {
                    "hookSpecificOutput": {
                        "permissionDecision": "deny",
                        "permissionDecisionReason": "blocked edit",
                    }
                },
            )
            result = _run_v2(
                tmp_dir,
                skill_dir,
                "code-reviewer",
                "edit",
                {"filePath": "a.py", "oldString": "x", "newString": "y"},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "DENIED:blocked edit")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p "test_devteam_plugins.py" -v`
Expected: FAIL - each test errors with `FileNotFoundError: [Errno 2] No such file or directory: '.../skills/glm/dev-team-glm/opencode/plugins/devteam-guard.v1.js'` (or the `.v2.js` counterpart), because neither plugin file exists yet.

- [ ] **Step 3: Write the v1 plugin**

```javascript
// Calls: python3 guard.py oc
import { spawnSync } from "node:child_process";
import path from "node:path";

export const DevteamGuard = async ({ directory }) => {
  return {
    "tool.execute.before": async (input, output) => {
      if (!process.env.DEVTEAM_ROLE) return;
      let decision = null;
      try {
        const payload = JSON.stringify({
          tool: input.tool,
          args: output.args,
          cwd: directory,
          role: process.env.DEVTEAM_ROLE,
        });
        const guardScript = path.join("{{SKILL_DIR}}", "scripts", "guard.py");
        const result = spawnSync("python3", [guardScript, "oc"], {
          input: payload,
          encoding: "utf8",
        });
        const stdout = (result.stdout || "").trim();
        if (stdout) decision = JSON.parse(stdout);
      } catch (err) {
        decision = null;
      }
      if (
        decision &&
        decision.hookSpecificOutput &&
        decision.hookSpecificOutput.permissionDecision === "deny"
      ) {
        throw new Error(
          decision.hookSpecificOutput.permissionDecisionReason || "denied by devteam guard"
        );
      }
    },
  };
};
```

- [ ] **Step 4: Write the v2 plugin**

```javascript
// Shape: Plugin.define({ id: "devteam-guard", setup })
import { Plugin } from "@opencode/plugin";
import { spawnSync } from "node:child_process";
import path from "node:path";

export default Plugin.define({
  id: "devteam-guard",
  setup: (ctx) => ({
    "tool.execute.before": async (input, output) => {
      if (!process.env.DEVTEAM_ROLE) return;
      let decision = null;
      try {
        const payload = JSON.stringify({
          tool: input.tool,
          args: output.args,
          cwd: ctx.location.directory,
          role: process.env.DEVTEAM_ROLE,
        });
        const guardScript = path.join("{{SKILL_DIR}}", "scripts", "guard.py");
        const result = spawnSync("python3", [guardScript, "oc"], {
          input: payload,
          encoding: "utf8",
        });
        const stdout = (result.stdout || "").trim();
        if (stdout) decision = JSON.parse(stdout);
      } catch (err) {
        decision = null;
      }
      if (
        decision &&
        decision.hookSpecificOutput &&
        decision.hookSpecificOutput.permissionDecision === "deny"
      ) {
        throw new Error(
          decision.hookSpecificOutput.permissionDecisionReason || "denied by devteam guard"
        );
      }
    },
  }),
});
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p "test_devteam_plugins.py" -v`
Expected: PASS - `Ran 4 tests in ...s` with `OK`.

- [ ] **Step 6: Commit**

```bash
git add skills/glm/dev-team-glm/opencode/plugins/devteam-guard.v1.js skills/glm/dev-team-glm/opencode/plugins/devteam-guard.v2.js skills/glm/_shared/tests/test_devteam_plugins.py
git commit -m "feat: add v1 and v2 OpenCode guard plugins with tests"
```

---

### T04: Neutral dev-team agents and /devteam command [P]

**Depends:** —

**Interfaces:**
- Produces: `skills/glm/dev-team-glm/agents/*.md`; `/devteam`

**Files:**
- Create: `skills/glm/dev-team-glm/opencode/agents/programmer.md`
- Create: `skills/glm/dev-team-glm/opencode/agents/code-reviewer.md`
- Create: `skills/glm/dev-team-glm/opencode/agents/spot-reviewer.md`
- Create: `skills/glm/dev-team-glm/opencode/agents/investigator.md`
- Create: `skills/glm/dev-team-glm/opencode/agents/team-leader.md`
- Create: `skills/glm/dev-team-glm/opencode/commands/devteam.md`

Transform five neutral agent sources: the bodies match `skills/glm/dev-team-glm/agents/*.md` prompts without Claude-only frontmatter, creating OpenCode agents with new frontmatter structure. Each agent frontmatter: `name`, `description` (unchanged from original), `model`, `effort`, `temperature: 1.0`, `access: internal`, `bash` (true/false per tools), `web` (true/false per WebSearch/WebFetch), and `steps` (replaces maxTurns). Also create `/devteam` command source.

- [ ] **Step 1: Create neutral programmer agent source**

Read the programmer agent at `skills/glm/dev-team-glm/agents/programmer.md` (lines 1-156 provided in the plan brief), extract its body starting from line 44, and create `skills/glm/dev-team-glm/opencode/agents/programmer.md` with OpenCode frontmatter. The frontmatter has: name=programmer, description=the existing one (lines 3-10), model=haiku, effort=high, temperature=1.0, access=internal, bash=true, web=false, steps=150.

Example OpenCode frontmatter structure:

```yaml
---
name: programmer
description: >-
  Implementation engineer for the dev-team workflow...
model: haiku
effort: high
temperature: 1.0
access: internal
bash: true
web: false
steps: 150
---
```

- [ ] **Step 2: Create neutral code-reviewer agent source**

Read the code-reviewer agent at `skills/glm/dev-team-glm/agents/code-reviewer.md` (lines 1-137), extract its body starting from line 34, and create `skills/glm/dev-team-glm/opencode/agents/code-reviewer.md` with frontmatter: name=code-reviewer, description from lines 3-8, model=opus, effort=high, temperature=1.0, access=internal, bash=true, web=false, steps=80.

- [ ] **Step 3: Create neutral spot-reviewer agent source**

Read `skills/glm/dev-team-glm/agents/spot-reviewer.md` (lines 1-105), extract body from line 33, and create `skills/glm/dev-team-glm/opencode/agents/spot-reviewer.md` with frontmatter: name=spot-reviewer, description from lines 3-7, model=haiku, effort=high, temperature=1.0, access=internal, bash=true, web=false, steps=50.

- [ ] **Step 4: Create neutral investigator agent source**

Read `skills/glm/dev-team-glm/agents/investigator.md` (lines 1-99), extract body from line 34, and create `skills/glm/dev-team-glm/opencode/agents/investigator.md` with frontmatter: name=investigator, description from lines 3-8, model=haiku, effort=high, temperature=1.0, access=internal, bash=true, web=true (has WebSearch/WebFetch), steps=60.

- [ ] **Step 5: Create neutral team-leader agent source**

Read `skills/glm/dev-team-glm/agents/team-leader.md` (lines 1-208), extract body from line 38, and create `skills/glm/dev-team-glm/opencode/agents/team-leader.md` with frontmatter: name=team-leader, description from lines 3-12, model=opus, effort=max, temperature=1.0, access=internal, bash=true, web=true (has WebSearch/WebFetch), steps=120.

- [ ] **Step 6: Create /devteam command source**

Create `skills/glm/dev-team-glm/opencode/commands/devteam.md` with two-line YAML frontmatter (description and a simple separator line) followed by "Load skill from {{SKILL_DIR}} with $ARGUMENTS."

- [ ] **Step 7: Validate YAML syntax for all agent sources**

Run: `python3 -c "import yaml; f = open('skills/glm/dev-team-glm/opencode/agents/programmer.md'); yaml.safe_load(f.read().split('---')[1]); print('OK')" && echo "programmer validated"`

Expected: OK and "programmer validated"

- [ ] **Step 8: Commit all neutral agents and command**

Run: `git add skills/glm/dev-team-glm/opencode/agents/programmer.md skills/glm/dev-team-glm/opencode/agents/code-reviewer.md skills/glm/dev-team-glm/opencode/agents/spot-reviewer.md skills/glm/dev-team-glm/opencode/agents/investigator.md skills/glm/dev-team-glm/opencode/agents/team-leader.md skills/glm/dev-team-glm/opencode/commands/devteam.md && git commit -m "feat: neutral dev-team agents and /devteam command for OpenCode"`

Expected: Commit succeeds with message about neutral agents and devteam command

---

### T05: devteam.py OpenCode lane launcher [P]

**Depends:** T01, T02, T04

**Interfaces:**
- Consumes: `def run_lanes(lanes: list, out_dir: str, width: int = 8, stall: int = 180, binary: str = "opencode", major: int = 0) -> list`; `env: dict`; `os.environ`; `def install(skill_dir: str, major: int, home: str = "") -> list`; `opencode/plugins/<base>.v<major>.js`; `<home>/.config/opencode/plugins/<base>.js`; `{{SKILL_DIR}}`; `def guard_oc(inp)`; `python3 guard.py oc`; `{"tool": str, "args": dict, "cwd": str, "role": str}`; `skills/glm/dev-team-glm/agents/*.md`; `/devteam`
- Produces: `def is_opencode() -> bool`; `def emit_agent(root, st, agent, model, prompt, label) -> str`; `def launch_lane(root, st, lane_id, agent, model, prompt) -> int`; `def cmd_lane_run(a)`; `def cmd_wait(a)`; `devteam.py lane-run <lane_id>`; `devteam.py wait [--timeout 100]`

**Files:**
- Modify: `skills/glm/dev-team-glm/scripts/devteam.py`
- Test: `skills/glm/_shared/tests/test_devteam_oc_lanes.py`

- [ ] **Step 1: Write the failing tests for `is_opencode` and `emit_agent`**

Create `skills/glm/_shared/tests/test_devteam_oc_lanes.py`:

```python
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "dev-team-glm", "scripts")
sys.path.insert(0, SCRIPTS)

import devteam  # noqa: E402

DEVTEAM = os.path.join(SCRIPTS, "devteam.py")


class HarnessTest(unittest.TestCase):
    def test_is_opencode(self):
        cases = [({}, False), ({"OPENCODE": "1"}, True), ({"DEVTEAM_HARNESS": "opencode"}, True),
                 ({"DEVTEAM_HARNESS": "claude", "OPENCODE": "1"}, False), ({"OPENCODE": ""}, False)]
        for env, want in cases:
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(devteam.is_opencode(), want, env)

    def test_claude_line_is_unchanged(self):
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "claude"}):
            line = devteam.emit_agent(Path("/r"), {}, "programmer", "opus", "python3 x claim S1", "S1")
            bare = devteam.emit_agent(Path("/r"), {}, "investigator", "", "Read b.md and follow it exactly.", "S2")
        self.assertEqual(line, 'Agent → subagent_type: programmer, description: "S1", model: opus, '
                               'prompt: "python3 x claim S1"')
        self.assertEqual(bare, 'Agent → subagent_type: investigator, description: "S2", '
                               'prompt: "Read b.md and follow it exactly."')

    def test_opencode_launches_a_lane(self):
        st = {"provider": "glm"}
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "opencode"}), \
                mock.patch.object(devteam, "launch_lane", return_value=4242) as launch:
            line = devteam.emit_agent(Path("/r"), st, "code-reviewer", "", "Read r1.md", "review r1")
        launch.assert_called_once_with(Path("/r"), st, "review-r1", "code-reviewer", "", "Read r1.md")
        self.assertIn("LANE review-r1", line)
        self.assertIn("pid 4242", line)
        self.assertNotIn("Agent →", line)

    def test_model_aliases_map_to_neutral_models(self):
        st = {"provider": "glm"}
        self.assertEqual(devteam.oc_model(st, "programmer", ""), "flash")
        self.assertEqual(devteam.oc_model(st, "code-reviewer", ""), "pro")
        self.assertEqual(devteam.oc_model(st, "programmer", "opus"), "pro")
        self.assertEqual(devteam.oc_model(st, "programmer", "sonnet"), "pro")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_devteam_oc_lanes.py -v`
Expected: FAIL with "AttributeError: module 'devteam' has no attribute 'is_opencode'" (and matching errors for `emit_agent`, `launch_lane` and `oc_model`), ending in `FAILED (errors=4)`

- [ ] **Step 3: Add `is_opencode`, `oc_model`, `launch_lane` and `emit_agent`**

In `skills/glm/dev-team-glm/scripts/devteam.py`, insert this block directly above `def print_dispatch(st, blocks, skipped):` (below `def dispatch_model`):

```python
OC_AGENTS = {"programmer-lite": "programmer"}          # OpenCode has one programmer agent
OC_MODELS = {"haiku": "flash", "sonnet": "pro", "opus": "pro"}
WRITER_AGENTS = ("programmer", "programmer-lite")
MAX_LANE_RUNS = 4          # guard.py force-finishes after MAX_STOP_BLOCKS = 2, so 3 runs is the real ceiling


def is_opencode() -> bool:
    """OpenCode path: DEVTEAM_HARNESS=opencode, or DEVTEAM_HARNESS unset and OPENCODE non-empty."""
    harness = os.environ.get("DEVTEAM_HARNESS")
    if harness is not None:
        return harness == "opencode"
    return bool(os.environ.get("OPENCODE"))


def oc_model(st, agent, model):
    """Neutral OpenCode model (`flash` / `pro`) for a Claude alias or the role's default alias."""
    alias = model or PROVIDERS[provider_of(st)]["agents"].get(agent, ("opus", ""))[0]
    return OC_MODELS.get(alias, alias)


def lanes_dir(root):
    return state_dir(Path(root)) / "lanes"


def launch_lane(root, st, lane_id, agent, model, prompt) -> int:
    """Start `devteam.py lane-run <lane_id>` as a detached process; return its pid."""
    d = lanes_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    for ext in (".done", ".jsonl", ".err"):
        try:
            (d / f"{lane_id}{ext}").unlink()
        except OSError:
            pass
    spec = {"id": lane_id, "agent": OC_AGENTS.get(agent, agent), "model": oc_model(st, agent, model),
            "prompt": prompt, "writer": agent in WRITER_AGENTS}
    write_atomic(d / f"{lane_id}.lane.json", json.dumps(spec))
    with open(d / f"{lane_id}.log", "w") as log:
        proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "lane-run", lane_id],
                                cwd=str(root), stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True)
    return proc.pid


def emit_agent(root, st, agent, model, prompt, label) -> str:
    """The launch line for one agent: the Claude Code `Agent →` instruction, or on OpenCode a lane
    process started right now (the Conductor then only waits)."""
    if not is_opencode():
        return (f"Agent → subagent_type: {agent}, description: \"{label}\"" + (f", model: {model}" if model else "")
                + f", prompt: \"{prompt}\"")
    lane_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip("-") or "lane"
    pid = launch_lane(root, st, lane_id, agent, model, prompt)
    return f"LANE {lane_id} → {agent} (pid {pid}) running; `devteam wait` wakes you when a lane finishes"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_devteam_oc_lanes.py -v`
Expected: PASS, ending in `Ran 4 tests` and `OK`

- [ ] **Step 5: Write the failing end-to-end tests for dispatch and `lane-run`**

In `skills/glm/_shared/tests/test_devteam_oc_lanes.py`, add this block directly above the final `if __name__ == "__main__":` line:

```python
FAKE_OC = '''#!/usr/bin/env python3
import json, os, sys
argv = sys.argv[1:]
if argv[:1] == ["--version"]:
    print("1.18.0")
    sys.exit(0)
if "--help" in argv:
    print("--dir --agent --model --format --auto")
    sys.exit(0)
with open(os.environ["FAKE_OC_LOG"], "a") as f:
    f.write(json.dumps({"brief": argv[-1], "dir": argv[argv.index("--dir") + 1],
                        "agent": argv[argv.index("--agent") + 1], "model": argv[argv.index("-m") + 1],
                        "role": os.environ.get("DEVTEAM_ROLE"), "slice": os.environ.get("DEVTEAM_SLICE")}) + "\\n")
print(json.dumps({"type": "text", "part": {"type": "text", "text": os.environ.get("FAKE_OC_REPLY", "")}}))
'''

PLAN = {"request": "r", "commands": {"test": "true"},
        "slices": [{"id": "S1", "title": "one", "deps": [], "files": ["src/a.py", "tests/test_a.py"],
                    "risk": "low", "criteria": ["works"]}]}


class RepoCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = os.path.join(self.tmp, "repo")
        os.makedirs(os.path.join(self.repo, "src"))
        os.makedirs(os.path.join(self.tmp, "home"))
        fake = os.path.join(self.tmp, "fake_opencode")
        with open(fake, "w") as f:
            f.write(FAKE_OC)
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)
        self.log = os.path.join(self.tmp, "oc.log")
        drop = ("OPENCODE", "DEVTEAM_HARNESS", "ANTHROPIC_BASE_URL", "DEVTEAM_GLM_TIER",
                "DEVTEAM_MAX_PARALLEL", "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS")
        self.env = {k: v for k, v in os.environ.items() if k not in drop}
        self.env.update({"DEVTEAM_PROVIDER": "glm", "DEVTEAM_GOVERNOR": "off", "DEVTEAM_PEAK": "off",
                         "DEVTEAM_TRANSCRIPTS_DIR": os.path.join(self.tmp, "none"),
                         "HOME": os.path.join(self.tmp, "home"), "DEVTEAM_OC_BIN": fake,
                         "FAKE_OC_LOG": self.log})
        for cmd in (["git", "init", "-q", "-b", "main"], ["git", "config", "user.email", "t@t"],
                    ["git", "config", "user.name", "t"], ["git", "config", "commit.gpgsign", "false"]):
            self.run_ok(cmd)
        Path(self.repo, "src", "a.py").write_text("x = 1\n")
        Path(self.tmp, "plan.json").write_text(json.dumps(PLAN))
        self.run_ok(["git", "add", "-A"])
        self.run_ok(["git", "commit", "-qm", "init"])
        self.devteam("init", os.path.join(self.tmp, "plan.json"))

    def run_ok(self, cmd, env=None):
        r = subprocess.run(cmd, cwd=self.repo, env=env or self.env, text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r.stdout

    def devteam(self, *args, **env):
        return self.run_ok([sys.executable, DEVTEAM] + list(args), env=dict(self.env, **env))

    def state(self, *parts):
        return Path(self.repo, ".claude", "dev-team", *parts)

    def lane_log(self):
        p = self.state("lanes", "S1.log")
        return p.read_text() if p.exists() else "(no lane log)"

    def wait_for(self, path, limit=60):
        end = time.monotonic() + limit
        while time.monotonic() < end:
            if path.exists():
                return True
            time.sleep(0.2)
        return False

    def calls(self):
        with open(self.log) as f:
            return [json.loads(line) for line in f]


class LaneRunTest(RepoCase):
    def test_claude_dispatch_prints_agent_line(self):
        out = self.devteam("dispatch", "S1")
        self.assertIn('Agent → subagent_type: programmer, description: "S1"', out)
        self.assertIn("claim S1", out)
        self.assertFalse(self.state("lanes").exists())

    def test_opencode_blocked_lane_writes_marker(self):
        out = self.devteam("dispatch", "S1", DEVTEAM_HARNESS="opencode",
                           FAKE_OC_REPLY="## Status: Blocked\nneed the schema")
        self.assertIn("LANE S1", out)
        self.assertNotIn("Agent →", out)
        self.assertTrue(self.wait_for(self.state("slices", "S1.blocked")), self.lane_log())
        wt = self.state("wt", "S1")
        branch = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=wt,
                                text=True, capture_output=True).stdout.strip()
        self.assertEqual(branch, "devteam/S1")
        calls = self.calls()
        self.assertEqual(len(calls), 1)
        self.assertIn("CLAIMED S1", calls[0]["brief"])
        self.assertEqual(os.path.realpath(calls[0]["dir"]), os.path.realpath(str(wt)))
        self.assertEqual((calls[0]["agent"], calls[0]["model"]), ("programmer", "zai-coding-plan/glm-5.3-flash"))
        self.assertEqual((calls[0]["role"], calls[0]["slice"]), ("programmer", "S1"))

    def test_opencode_gate_block_reruns_lane(self):
        self.devteam("dispatch", "S1", DEVTEAM_HARNESS="opencode", FAKE_OC_REPLY="still working")
        self.assertTrue(self.wait_for(self.state("slices", "S1.done")), self.lane_log())
        calls = self.calls()
        self.assertEqual(len(calls), 3)
        self.assertNotIn("dev-team gate", calls[0]["brief"])
        self.assertIn("dev-team gate — you are not done yet", calls[1]["brief"])
        note = json.loads(self.state("slices", "S1.done").read_text())["note"]
        self.assertIn("gave up", note)
```

- [ ] **Step 6: Run the new tests to verify they fail**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_devteam_oc_lanes.py -k LaneRunTest -v`
Expected: FAIL with "AssertionError: 'LANE S1' not found in" for `test_opencode_blocked_lane_writes_marker` and `test_opencode_gate_block_reruns_lane` (dispatch still prints the `Agent →` line), ending in `FAILED (failures=2)`; `test_claude_dispatch_prints_agent_line` passes

- [ ] **Step 7: Add `cmd_lane_run` and its helpers**

In `skills/glm/dev-team-glm/scripts/devteam.py`, insert this block directly below the `emit_agent` function added in Step 3 (still above `def print_dispatch`):

```python
def lane_worktree(root, st, lane_id):
    """`<root>/.claude/dev-team/wt/<id>` on branch `devteam/<id>`, created from the slice's base."""
    wt = state_dir(Path(root)) / "wt" / lane_id
    if not (wt / ".git").exists():
        wt.parent.mkdir(parents=True, exist_ok=True)
        git(["worktree", "prune"], root, check=False)
        base = slice_state(st, lane_id)["base_sha"]
        git(["worktree", "add", "-f", "-B", f"devteam/{lane_id}", str(wt), base], root)
    return wt


def lane_text(path):
    """Final assistant text of a lane: the last `text` part in its JSON event stream."""
    try:
        lines = Path(path).read_text(errors="replace").splitlines()
    except OSError:
        return ""
    text = ""
    for ln in lines:
        try:
            ev = json.loads(ln)
        except ValueError:
            continue
        part = ev.get("part") if isinstance(ev, dict) else None
        if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
            text = part["text"]
    return text


def cmd_lane_run(a):
    """One OpenCode lane, end to end: worktree + claim for a programmer, `opencode run` through
    oc_harness, then the guard.py Stop gate (re-run once per block) so `.done`/`.blocked` markers
    appear exactly as on Claude Code."""
    root = find_root()
    d = lanes_dir(root)
    spec = json.loads((d / f"{a.lane_id}.lane.json").read_text())
    here = Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    import oc_harness
    binary = os.environ.get("DEVTEAM_OC_BIN") or "opencode"
    lane = {"id": spec["id"], "agent": spec["agent"], "model": spec["model"], "dir": str(root),
            "brief": spec["prompt"], "env": {"DEVTEAM_ROLE": spec["agent"], "DEVTEAM_SLICE": spec["id"]}}
    if not spec.get("writer"):
        r = oc_harness.run_lanes([lane], str(d), width=1, binary=binary)[0]
        out(f"LANE {spec['id']}: {r['status']} (exit {r['exit']})")
        return
    st = load_state(root)
    wt = lane_worktree(root, st, spec["id"])
    lane["dir"] = str(wt)
    claim = subprocess.run([sys.executable, str(here / "devteam.py"), "claim", spec["id"]],
                           cwd=str(wt), text=True, capture_output=True)
    if claim.returncode != 0:
        raise DevteamError(f"claim {spec['id']} failed: {claim.stderr.strip() or claim.stdout.strip()}")
    brief, note = claim.stdout, ""
    for _ in range(MAX_LANE_RUNS):
        lane["brief"] = brief + note
        r = oc_harness.run_lanes([lane], str(d), width=1, binary=binary)[0]
        payload = json.dumps({"cwd": str(wt), "last_assistant_message": lane_text(r["out"])})
        gate = subprocess.run([sys.executable, str(here / "guard.py"), "stop"], input=payload,
                              text=True, capture_output=True)
        out(f"LANE {spec['id']}: {r['status']} (exit {r['exit']}), stop gate exit {gate.returncode}")
        if gate.returncode != 2:
            return
        note = "\n\n" + gate.stderr
```

- [ ] **Step 8: Route dispatch, review and verification through `emit_agent`; register `lane-run`**

In `skills/glm/dev-team-glm/scripts/devteam.py`, replace the whole `def print_dispatch(st, blocks, skipped):` function with this version (the output on Claude Code is byte-identical: `emit_agent` returns the same `Agent →` line):

```python
def print_dispatch(st, blocks, skipped):
    """One Agent call per line-block, as short as the agent files allow: the Conductor's OUTPUT
    tokens for 64 launches sit on the critical path, and the briefing file already holds everything.
    The programmer/investigator system prompts say 'your prompt is the command — run it first'.
    On OpenCode `emit_agent` starts each lane itself and prints a LANE line instead."""
    sp = q(st["script"])
    root = Path(st["root"])
    for sid, s, mode in blocks:
        kind = slice_kind(s)
        if mode == "research":
            brief = state_dir(root) / "briefs" / f"{sid}.md"
            strong = (PROVIDERS[provider_of(st)]["escalate"] and not s.get("model")
                      and (s.get("size") == "large" or int(s.get("attempt") or 0) >= 2))
            model = (s.get("model") or "").strip() or (PROVIDERS[provider_of(st)]["strong"] if strong else "")
            out(f"=== DISPATCH {sid} [RESEARCH] — {s['title'][:50]}",
                emit_agent(root, st, "investigator", model, f"Read {brief} and follow it exactly.", sid),
                "")
            continue
        agent, model, label = dispatch_route(st, s, mode)
        out(f"=== DISPATCH {sid} [{kind.upper()}/{mode.upper()}] — {s['title'][:50]}   ({label})",
            emit_agent(root, st, agent, model, f"python3 {sp} claim {sid}", sid),
            "")
    if skipped:
        out("SKIPPED: " + "; ".join(skipped))
```

The spec (L143-148) names reviewers alongside programmers, and `do_review_batch`/`cmd_verify_brief` are the two review/verification dispatchers `cmd_next` calls on its own (the automated `wait`/`next` loop), so they must go through the same seam or an OpenCode review batch never launches anything and `wait` blocks forever. `do_review_range`/`cmd_review_pr` and `cmd_brief_debug` run with no plan or state (`root = toplevel()`, no `st`) and stay on the Claude-only `Agent →` line for now.

In `skills/glm/dev-team-glm/scripts/devteam.py`, inside `do_review_batch`, replace:

```python fragment
        out(f"=== REVIEW {name}: {len(take)} slices, {len(scope)} files",
            f"Agent → subagent_type: {'spot-reviewer' if spot else 'code-reviewer'}, description: \"review {name}\", "
            f"prompt: \"Read {state_dir(root) / 'reviews' / (name + '.md')} and follow it exactly.\"",
            "")
```

with:

```python fragment
        out(f"=== REVIEW {name}: {len(take)} slices, {len(scope)} files",
            emit_agent(root, st, 'spot-reviewer' if spot else 'code-reviewer', "",
                      f"Read {state_dir(root) / 'reviews' / (name + '.md')} and follow it exactly.", f"review {name}"),
            "")
```

Then, inside `cmd_verify_brief`, replace:

```python fragment
    out(f"Agent → subagent_type: team-leader, description: \"verify intent\", prompt: \"MODE: VERIFICATION. Read {p} and follow it.\"")
```

with:

```python fragment
    out(emit_agent(root, st, "team-leader", "", f"MODE: VERIFICATION. Read {p} and follow it.", "verify intent"))
```

In `main()`, directly below the line `pr.add_argument("--context"); pr.set_defaults(fn=cmd_brief_debug)` and above `a = p.parse_args(argv)`, add:

```python fragment
    pr = sp.add_parser("lane-run"); pr.add_argument("lane_id"); pr.set_defaults(fn=cmd_lane_run)
```

- [ ] **Step 9: Run the lane tests to verify they pass**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_devteam_oc_lanes.py -v`
Expected: PASS, ending in `Ran 7 tests` and `OK`

- [ ] **Step 10: Write the failing tests for `wait`**

In `skills/glm/_shared/tests/test_devteam_oc_lanes.py`, add this class directly above the final `if __name__ == "__main__":` line:

```python
class WaitTest(RepoCase):
    def test_times_out_with_next_line(self):
        start = time.monotonic()
        out = self.devteam("wait", "--timeout", "1")
        self.assertGreaterEqual(time.monotonic() - start, 1)
        self.assertIn("NEXT: devteam next", out)

    def test_returns_when_a_marker_appears(self):
        marker = self.state("slices", "S9.done")
        timer = threading.Timer(0.5, marker.write_text, args=("{}",))
        timer.start()
        self.addCleanup(timer.cancel)
        start = time.monotonic()
        out = self.devteam("wait", "--timeout", "30")
        self.assertLess(time.monotonic() - start, 10)
        self.assertIn("NEXT: devteam next", out)

    def test_opencode_dispatch_then_wait(self):
        self.devteam("dispatch", "S1", DEVTEAM_HARNESS="opencode", FAKE_OC_REPLY="## Status: Blocked\nno schema")
        out = self.devteam("wait", "--timeout", "60")
        self.assertIn("NEXT: devteam next", out)
        self.assertTrue(self.state("slices", "S1.blocked").exists(), self.lane_log())
```

- [ ] **Step 11: Run the wait tests to verify they fail**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_devteam_oc_lanes.py -k WaitTest -v`
Expected: FAIL with "AssertionError: 2 != 0" and "invalid choice: 'wait'" in the message for all three tests, ending in `FAILED (failures=3)`

- [ ] **Step 12: Add `cmd_wait` and register `wait`**

In `skills/glm/dev-team-glm/scripts/devteam.py`, insert this block directly below `cmd_lane_run` (still above `def print_dispatch`):

```python
def lane_marks(root):
    """{path: mtime} of every completion signal: slice markers, plus lane results of non-writer
    lanes (a programmer lane is finished only when its Stop gate writes the slice marker)."""
    sd = state_dir(Path(root))
    paths = glob.glob(str(sd / "slices" / "*.done")) + glob.glob(str(sd / "slices" / "*.blocked"))
    for p in glob.glob(str(sd / "lanes" / "*.done")):
        try:
            spec = json.loads(Path(p[:-len(".done")] + ".lane.json").read_text())
        except (OSError, ValueError):
            spec = {}
        if not spec.get("writer"):
            paths.append(p)
    seen = {}
    for p in paths:
        try:
            seen[p] = os.path.getmtime(p)
        except OSError:
            pass
    return seen


def cmd_wait(a):
    """Block up to --timeout seconds until a lane finishes, then point the Conductor at `next`."""
    root = find_root()
    try:
        st = load_state(root)
    except DevteamError:
        st = None
    start = lane_marks(root)
    deadline = time.monotonic() + max(0, a.timeout)
    found = bool(st and any(finished_lanes(root, st)))
    while not found and time.monotonic() < deadline:
        time.sleep(0.5)
        cur = lane_marks(root)
        found = any(start.get(k) != v for k, v in cur.items())
    out("WAIT: a lane finished" if found else f"WAIT: nothing finished in {a.timeout}s (lanes keep running)",
        "NEXT: devteam next")
```

In `main()`, directly below the `lane-run` parser line added in Step 8, add the parser for the CLI `devteam.py wait [--timeout 100]` (next to `devteam.py lane-run <lane_id>`):

```python fragment
    pr = sp.add_parser("wait"); pr.add_argument("--timeout", type=int, default=100); pr.set_defaults(fn=cmd_wait)
```

- [ ] **Step 13: Run the task tests to verify they pass**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_devteam_oc_lanes.py -v`
Expected: PASS, ending in `Ran 10 tests` and `OK`

- [ ] **Step 14: Run the whole Python suite and the dev-team selftest**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -v`
Expected: PASS, ending in `OK`

Run: `bash skills/glm/dev-team-glm/scripts/selftest.sh`
Expected: exit 0 with no `FAIL` line (the Claude Code dispatch output is unchanged)

- [ ] **Step 15: Commit**

```bash
git add skills/glm/dev-team-glm/scripts/devteam.py skills/glm/_shared/tests/test_devteam_oc_lanes.py
git commit -m "feat(dev-team): launch OpenCode lanes from devteam.py with stop gate and wait"
```

---

### T06: devteam.py governor signals and doctor for OpenCode

**Depends:** T05

**Interfaces:**
- Consumes: `def is_opencode() -> bool`; `def emit_agent(root, st, agent, model, prompt, label) -> str`; `def launch_lane(root, st, lane_id, agent, model, prompt) -> int`; `def cmd_lane_run(a)`; `def cmd_wait(a)`; `devteam.py lane-run <lane_id>`; `devteam.py wait [--timeout 100]`
- Produces: `def lane_signals(root, st) -> dict`; `def cmd_doctor(a)`; `--harness opencode`; `--fix`; `oc_harness.install`

**Files:**
- Modify: `skills/glm/dev-team-glm/scripts/devteam.py`
- Test: `skills/glm/_shared/tests/test_devteam_oc_doctor.py`

On OpenCode there are no Claude Code transcripts: the governor must read the lane runner's own output in `<root>/.claude/dev-team/lanes/` (`<id>.jsonl` JSON events, `<id>.done` result written by `oc_harness.run_lanes` with keys `id`, `status` in `OK|FAIL|STALL|TIMEOUT`, `exit`, `error`, `last_event`, `throttles`, `width`, `out`). `lane_signals` returns exactly the dict shape `scan_transcripts` returns, so `govern` only swaps the source. `doctor --harness opencode` checks the OpenCode side and `--fix` re-installs through `oc_harness.install`. The Claude Code path (`scan_transcripts`, the existing doctor body, every printed line) is untouched.

- [ ] **Step 1: Write the failing tests for `lane_signals`**

Create `skills/glm/_shared/tests/test_devteam_oc_doctor.py`:

```python
import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
GLM = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(GLM, "dev-team-glm", "scripts")
SKILL_DIR = os.path.join(GLM, "dev-team-glm")
STUB = os.path.join(HERE, "stub_opencode.py")
GUARD = os.path.join(SCRIPTS, "guard.py")
sys.path.insert(0, SCRIPTS)

import oc_harness  # noqa: E402  (the vendored copy next to devteam.py)


def load_devteam():
    spec = importlib.util.spec_from_file_location("devteam_oc", os.path.join(SCRIPTS, "devteam.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dt = load_devteam()

THROTTLE_EVENT = json.dumps({"type": "error", "error": {"name": "APIError", "data": {
    "message": json.dumps({"error": {"code": "1302", "message": "High concurrency"}})}}})
TEXT_EVENT = json.dumps({"type": "text", "part": {"type": "text", "text": "the docs mention 429 and rate limits"}})
EMPTY_SIG = {"throttle": [], "down": [], "spawn_fail": [], "spawned": {}}


class _LaneCase(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.lanes = self.root / ".claude" / "dev-team" / "lanes"
        now = int(time.time())
        self.st = {
            "created": now - 10, "provider": "glm",
            "reviews": {"r1": {"status": "dispatched", "shards": 2}},
            "slices": {
                "S1": {"status": "inflight", "mode": "slice", "dispatched": now - 5, "history": []},
                "R1": {"status": "inflight", "mode": "research", "dispatched": now - 5, "history": []},
            },
            "gov": dt.new_gov("glm", "pro"),
        }

    def tearDown(self):
        shutil.rmtree(self.root)

    def write(self, name, text, mode="a"):
        self.lanes.mkdir(parents=True, exist_ok=True)
        with open(self.lanes / name, mode) as f:
            f.write(text)
        return self.lanes / name


class LaneSignalsTest(_LaneCase):
    def test_no_lanes_dir(self):
        self.assertEqual(dt.lane_signals(self.root, self.st), EMPTY_SIG)

    def test_throttle_counted_once(self):
        self.write("S1.jsonl", TEXT_EVENT + "\n" + THROTTLE_EVENT + "\n")
        self.assertEqual(len(dt.lane_signals(self.root, self.st)["throttle"]), 1)
        self.assertEqual(dt.lane_signals(self.root, self.st)["throttle"], [])
        self.write("S1.jsonl", THROTTLE_EVENT + "\n")
        self.assertEqual(len(dt.lane_signals(self.root, self.st)["throttle"]), 1)

    def test_old_lane_files_ignored(self):
        path = self.write("S1.jsonl", THROTTLE_EVENT + "\n")
        old = self.st["created"] - 600
        os.utime(path, (old, old))
        self.write("S1.done", json.dumps({"id": "S1", "status": "FAIL", "error": "old"}))
        os.utime(self.lanes / "S1.done", (old, old))
        sig = dt.lane_signals(self.root, self.st)
        self.assertEqual((sig["throttle"], sig["down"]), ([], []))
        self.write("S1.jsonl", THROTTLE_EVENT + "\n")
        self.assertEqual(len(dt.lane_signals(self.root, self.st)["throttle"]), 1)

    def test_failed_lanes_reported_once(self):
        self.write("S1.done", json.dumps({"id": "S1", "status": "FAIL", "exit": 3, "error": "boom"}))
        self.write("r1-2.done", json.dumps({"id": "r1-2", "status": "STALL", "error": "no event for 180s"}))
        self.write("R1.done", json.dumps({"id": "R1", "status": "TIMEOUT", "error": "timeout after 60s"}))
        sig = dt.lane_signals(self.root, self.st)
        self.assertEqual(sorted((k, n, t) for k, n, t, _, _ in sig["down"]), [
            ("research", "R1", "TIMEOUT: timeout after 60s"),
            ("review", "r1-2", "STALL: no event for 180s"),
            ("slice", "S1", "FAIL: boom"),
        ])
        self.assertEqual(dt.lane_signals(self.root, self.st)["down"], [])

    def test_ok_lane_not_down(self):
        self.write("S1.done", json.dumps({"id": "S1", "status": "OK", "exit": 0, "error": ""}))
        self.assertEqual(dt.lane_signals(self.root, self.st)["down"], [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_devteam_oc_doctor.py -v`
Expected: FAIL with "AttributeError: module 'devteam_oc' has no attribute 'lane_signals'", ending in `FAILED (errors=5)`

- [ ] **Step 3: Implement `lane_signals`**

T05 named its `cmd_wait` helper `lane_marks(root)`, so the name `lane_signals` is free.
In `skills/glm/dev-team-glm/scripts/devteam.py`, insert directly above `def mark_utilization(st, inflight_n, cap):`:

```python
def _oc_harness():
    """The vendored oc_harness.py next to this script."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import oc_harness
    return oc_harness


def _lane_kind(st, name):
    s = st["slices"].get(name)
    if s is None:
        return "review"
    return "research" if s.get("mode") == "research" else "slice"


def lane_signals(root, st) -> dict:
    """OpenCode counterpart of scan_transcripts: the same signal dict, read from what the lane runner
    wrote to .claude/dev-team/lanes/ (`<id>.jsonl` events, `<id>.done` results). Throttling = a JSON
    error event carrying 429/1302/1305; a lane that ended FAIL/STALL/TIMEOUT is reported as down.
    Incremental (offsets live in the governor state) and tolerant: an odd file or line is skipped."""
    g = st.setdefault("gov", new_gov(provider_of(st), resolve_tier()))
    seen = g.setdefault("lanes", {})
    created = float(st.get("created") or 0)
    sig = {"throttle": [], "down": [], "spawn_fail": [], "spawned": {}}
    d = state_dir(root) / "lanes"
    if not d.is_dir():
        return sig
    throttle_re = _oc_harness().THROTTLE_RE
    for f in sorted(d.glob("*.jsonl")):
        try:
            size, mtime = f.stat().st_size, f.stat().st_mtime
        except OSError:
            continue
        rec = seen.setdefault(f.stem, {})
        if "off" not in rec and mtime + 2 < created:
            rec["off"] = size                         # a previous run's lane: start at its end
            continue
        off = rec.get("off", 0)
        if size < off:
            off = 0
        if size == off:
            continue
        try:
            with f.open("rb") as fh:
                fh.seek(off)
                chunk = fh.read(SCAN_MAX_BYTES)
        except OSError:
            continue
        end = chunk.rfind(b"\n")
        if end < 0:
            rec["off"] = off + (len(chunk) if len(chunk) >= SCAN_MAX_BYTES else 0)
            continue
        rec["off"] = off + end + 1
        t = time.time()
        for ln in chunk[:end].split(b"\n"):
            if b'"error"' in ln and throttle_re.search(ln.decode("utf-8", "replace")):
                sig["throttle"].append(t)
    for f in sorted(d.glob("*.done")):
        try:
            mtime = f.stat().st_mtime
        except OSError:
            continue
        rec = seen.setdefault(f.stem, {})
        if mtime + 2 < created or rec.get("done") == mtime:
            continue
        rec["done"] = mtime
        try:
            res = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(res, dict) or res.get("status") in (None, "OK"):
            continue
        text = f"{res.get('status')}: {res.get('error') or res.get('last_event') or 'no error event'}"[:240]
        sig["down"].append((_lane_kind(st, f.stem), f.stem, text, str(int(mtime)), mtime))
    return sig
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_devteam_oc_doctor.py -v`
Expected: PASS, ending in `Ran 5 tests` and `OK`

- [ ] **Step 5: Write the failing tests for the governor's signal source**

In `skills/glm/_shared/tests/test_devteam_oc_doctor.py`, insert directly above the final `if __name__ == "__main__":` line:

```python
class GovernHarnessTest(_LaneCase):
    ENV = {"DEVTEAM_PEAK": "off", "DEVTEAM_GOVERNOR": "on",
           "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "20", "DEVTEAM_MAX_PARALLEL": ""}

    def test_opencode_reads_lane_files(self):
        self.write("S1.jsonl", THROTTLE_EVENT + "\n")
        self.write("S1.done", json.dumps({"id": "S1", "status": "FAIL", "exit": 3, "error": "boom"}))
        env = dict(self.ENV, DEVTEAM_HARNESS="opencode")
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(dt, "scan_transcripts", side_effect=AssertionError("transcripts read")):
            lines = dt.govern(self.root, self.st, 0)
        throttled = [ln for ln in lines if ln.startswith("THROTTLED: 1 ")]
        self.assertEqual(len(throttled), 1)
        self.assertIn("window 6 → 3", throttled[0])
        self.assertEqual(self.st["gov"]["cap"], 3)
        down = [ln for ln in lines if ln.startswith("LANE DOWN S1 (slice)")]
        self.assertEqual(len(down), 1)
        self.assertIn("FAIL: boom", down[0])
        self.assertIn("`retry S1`", down[0])
        self.assertNotIn("SendMessage", down[0])

    def test_claude_reads_transcripts(self):
        self.write("S1.jsonl", THROTTLE_EVENT + "\n")
        env = dict(self.ENV, DEVTEAM_HARNESS="claude")
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(dt, "scan_transcripts", return_value=dict(EMPTY_SIG, spawned={})) as scan, \
                mock.patch.object(dt, "lane_signals", side_effect=AssertionError("lane files read")):
            lines = dt.govern(self.root, self.st, 0)
        scan.assert_called_once()
        self.assertEqual(lines, [])
        self.assertEqual(self.st["gov"]["cap"], 6)
```

- [ ] **Step 6: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_devteam_oc_doctor.py -k GovernHarnessTest -v`
Expected: FAIL with "AssertionError: transcripts read" in `test_opencode_reads_lane_files`, ending in `FAILED (failures=1)`

- [ ] **Step 7: Switch the governor's signal source on OpenCode**

In `skills/glm/dev-team-glm/scripts/devteam.py`, inside `def govern(root, st, successes):`, replace this line:

```python fragment
    sig = scan_transcripts(root, st)                 # always: re-queue / LANE DOWN are correctness, not throttling
```

with:

```python fragment
    oc = is_opencode()
    sig = lane_signals(root, st) if oc else scan_transcripts(root, st)   # always: re-queue / LANE DOWN are correctness
```

Then, in the same function, replace the `LANE DOWN` append at the end of the lane-down loop:

```python fragment
        lines.append(f"LANE DOWN {name} ({kind}): the API failed after retries — {text[:120]}"
                     f"\n  → SendMessage that agent \"continue\" (warm: same context"
                     + (", same worktree); cold alternative: `retry " + name + "`" if kind == "slice" else ")"))
```

with:

```python fragment
        if oc:
            lines.append(f"LANE DOWN {name} ({kind}): the lane process ended {text[:120]}"
                         + (f"\n  → `fail {name}` then `retry {name}` (the worktree is kept for salvage)"
                            if kind == "slice" else f"\n  → relaunch it: `lane-run {name}`"))
            continue
        lines.append(f"LANE DOWN {name} ({kind}): the API failed after retries — {text[:120]}"
                     f"\n  → SendMessage that agent \"continue\" (warm: same context"
                     + (", same worktree); cold alternative: `retry " + name + "`" if kind == "slice" else ")"))
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_devteam_oc_doctor.py -v`
Expected: PASS, ending in `Ran 7 tests` and `OK`

- [ ] **Step 9: Write the failing tests for `doctor --harness opencode`**

In `skills/glm/_shared/tests/test_devteam_oc_doctor.py`, insert directly above the final `if __name__ == "__main__":` line:

```python
V1_PLUGIN = ('import { spawnSync } from "node:child_process";\n'
             'export const DevteamGuard = async ({ directory }) => ({\n'
             '  "tool.execute.before": async (input, output) => {\n'
             '    spawnSync("python3", ["%s", "oc"], { cwd: directory });\n'
             '  },\n'
             '});\n')
V2_PLUGIN = ('import { Plugin } from "@opencode/plugin";\n'
             'export default Plugin.define({ id: "devteam-guard", setup: (ctx) => ({\n'
             '  "tool.execute.before": async (input, output) => {},\n'
             '}) });\n'
             '// python3 %s oc\n')


class DoctorOpenCodeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.bin = os.path.join(self.tmp, "bin")
        self.repo = os.path.join(self.tmp, "repo")
        for d in (self.home, self.bin, self.repo):
            os.makedirs(d)
        opencode = os.path.join(self.bin, "opencode")
        with open(opencode, "w") as f:
            f.write('#!/bin/sh\nexec "%s" "%s" "$@"\n' % (sys.executable, STUB))
        os.chmod(opencode, 0o755)
        for args in (["init", "-q"],
                     ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                      "commit", "-q", "--allow-empty", "-m", "init"]):
            subprocess.run(["git"] + args, cwd=self.repo, check=True, capture_output=True)
        self.old = os.getcwd()
        os.chdir(self.repo)
        self.env = mock.patch.dict(os.environ, {
            "HOME": self.home, "PATH": self.bin + os.pathsep + os.environ.get("PATH", ""),
            "DEVTEAM_HARNESS": "opencode", "STUB_OC_VERSION": "1.18.32", "STUB_OC_MISSING": ""})
        self.env.start()
        self.name = oc_harness.skill_name(SKILL_DIR)
        self.oc = os.path.join(self.home, ".config", "opencode")

    def tearDown(self):
        self.env.stop()
        os.chdir(self.old)
        shutil.rmtree(self.tmp)

    def doctor(self, fix=False, harness="opencode"):
        ns = argparse.Namespace(fix=fix) if harness is None else argparse.Namespace(fix=fix, harness=harness)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dt.cmd_doctor(ns)
        return buf.getvalue()

    def plugin(self, text):
        d = os.path.join(self.oc, "plugins")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "guard.js"), "w") as f:
            f.write(text)

    def test_reports_missing_install(self):
        out = self.doctor()
        self.assertIn("harness opencode", out)
        self.assertIn("DOCTOR found:", out)
        self.assertIn("MISSING: %s is not installed for OpenCode" % self.name, out)
        self.assertIn("agent programmer not installed", out)
        self.assertIn("agent team-leader not installed", out)
        self.assertIn("guard plugin not installed", out)
        self.assertIn("no opencode.json names the zai-coding-plan provider", out)
        self.assertIn("run `doctor --harness opencode --fix`", out)
        self.assertNotIn("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", out)

    def test_fix_installs_detected_major(self):
        out = self.doctor(fix=True)
        self.assertIn("harness opencode", out)
        self.assertIn("installed ", out)
        self.assertIn("updated git info/exclude", out)
        with open(os.path.join(self.oc, "skills", self.name, ".oc-major")) as f:
            self.assertEqual(f.read().strip(), "1")
        again = self.doctor()
        self.assertNotIn("MISSING: %s" % self.name, again)
        self.assertIn("INSTALLED: %s (major 1)" % self.name, again)

    def test_major_mismatch(self):
        d = os.path.join(self.oc, "skills", self.name)
        os.makedirs(d)
        with open(os.path.join(d, ".oc-major"), "w") as f:
            f.write("2")
        out = self.doctor()
        self.assertIn("installed major 2 != detected major 1, re-run install-opencode.sh", out)

    def test_opencode_missing(self):
        os.environ["STUB_OC_VERSION"] = "none"
        out = self.doctor()
        self.assertIn("harness opencode", out)
        self.assertIn("opencode not found on PATH", out)

    def test_plugin_wrong_dialect(self):
        self.plugin(V2_PLUGIN % GUARD)
        out = self.doctor()
        self.assertIn("plugin guard.js is written for OpenCode v2 but opencode is v1", out)
        self.assertIn("re-run install-opencode.sh", out)

    def test_plugin_ok(self):
        self.plugin(V1_PLUGIN % GUARD)
        out = self.doctor()
        self.assertIn("harness opencode", out)
        self.assertNotIn("guard plugin not installed", out)
        self.assertNotIn("plugin guard.js", out)

    def test_plugin_unresolved(self):
        self.plugin(V1_PLUGIN % "{{SKILL_DIR}}/scripts/guard.py")
        out = self.doctor()
        self.assertIn("plugin guard.js: its guard.py path does not resolve", out)

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_plugin_load_error(self):
        self.plugin("export const DevteamGuard = async ({ directory }) => ({ // python3 %s oc\n" % GUARD)
        out = self.doctor()
        self.assertIn("plugin guard.js fails to load", out)

    def test_provider_config_found(self):
        os.makedirs(self.oc, exist_ok=True)
        with open(os.path.join(self.oc, "opencode.json"), "w") as f:
            json.dump({"provider": {"zai-coding-plan": {}}}, f)
        out = self.doctor()
        self.assertIn("harness opencode", out)
        self.assertNotIn("names the zai-coding-plan provider", out)

    def test_default_harness_from_env(self):
        self.assertIn("harness opencode", self.doctor(harness=None))
        os.environ["DEVTEAM_HARNESS"] = "claude"
        out = self.doctor(harness=None)
        self.assertNotIn("harness opencode", out)
        self.assertIn("run `doctor --fix`", out)

    def test_claude_harness_unchanged(self):
        out = self.doctor(harness="claude")
        self.assertNotIn("harness opencode", out)
        self.assertIn("DOCTOR found:", out)
        self.assertIn("run `doctor --fix`", out)
```

- [ ] **Step 10: Run the tests to verify they fail**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_devteam_oc_doctor.py -k DoctorOpenCodeTest -v`
Expected: FAIL with "AssertionError: 'harness opencode' not found in" (the Claude Code doctor still runs for every harness), ending in `FAILED (failures=`

- [ ] **Step 11: Add the OpenCode doctor**

In `skills/glm/dev-team-glm/scripts/devteam.py`, insert directly above `def cmd_doctor(a):`:

```python
OC_AGENT_NAMES = ("programmer", "code-reviewer", "spot-reviewer", "investigator", "team-leader")
OC_GUARD_PATH_RE = re.compile(r"""([^\s"'`]+/scripts/guard\.py)""")


def oc_plugin_problems(home, major):
    """The installed guard plugin: present, guard.py path resolved, dialect = detected major, loads."""
    pdir = Path(home) / ".config" / "opencode" / "plugins"
    found = [p for p in sorted(pdir.glob("*.js")) if "guard.py" in p.read_text(errors="replace")] \
        if pdir.is_dir() else []
    if not found:
        return [f"guard plugin not installed in {pdir} (OpenCode tool calls would run unchecked)"]
    p = found[0]
    text = p.read_text(errors="replace")
    problems = []
    m = OC_GUARD_PATH_RE.search(text)
    if "{{SKILL_DIR}}" in text or (m and not Path(m.group(1)).exists()):
        problems.append(f"plugin {p.name}: its guard.py path does not resolve (every tool call would fail open)")
    v2 = "Plugin.define" in text
    if major and v2 != (major >= 2):
        problems.append(f"plugin {p.name} is written for OpenCode v{2 if v2 else 1} but opencode is v{major} — "
                        "re-run install-opencode.sh")
    node = shutil.which("node")
    if node:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            probe = Path(td) / "plugin.mjs"
            probe.write_text(text)
            r = sh([node, "--check", str(probe)], check=False)
        if r.returncode != 0:
            err = [ln for ln in (r.stderr or r.stdout).splitlines() if ln.strip()]
            why = next((ln for ln in err if "Error" in ln), err[0] if err else "node --check failed")
            problems.append(f"plugin {p.name} fails to load: {why.strip()[:160]}")
    return problems


def doctor_opencode(a, root):
    """`doctor --harness opencode`: OpenCode binary, installed skill and major, agents, guard plugin,
    provider config and git excludes. `--fix` re-installs through oc_harness.install for the detected
    major; the provider config is never written (it holds the user's own settings)."""
    oc = _oc_harness()
    home = str(Path.home())
    skill_dir = Path(__file__).resolve().parent.parent
    problems, notes, reinstall = [], [], False
    gv = git(["--version"]).split()[-1]
    notes.append(f"git {gv}, python {sys.version.split()[0]}, root {root}, harness opencode")
    if git(["status", "--porcelain", "--untracked-files=no"], root):
        problems.append("uncommitted tracked changes in the integration checkout (commit/stash before a run)")
    major = oc.detect()
    if not major:
        problems.append("opencode not found on PATH — install OpenCode 1.18.x or v2 first (not auto-fixed)")
    else:
        notes.append(f"opencode v{major}, provider {oc.PROVIDER}")
        for ln in oc.check(str(skill_dir)):
            if ln.startswith(("FAIL", "MISSING")):
                problems.append(ln)
                reinstall = True
            else:
                notes.append(ln)
    adir = Path(home) / ".config" / "opencode" / "agents"
    for name in OC_AGENT_NAMES:
        if not (adir / f"{name}.md").exists():
            problems.append(f"agent {name} not installed in {adir}")
            reinstall = True
    plugin = oc_plugin_problems(home, major)
    problems += plugin
    reinstall = reinstall or bool(plugin)
    cfgs = [Path(home) / ".config" / "opencode" / n for n in ("opencode.json", "opencode.jsonc")] \
        + [root / "opencode.json", root / "opencode.jsonc"]
    if not any(p.exists() and oc.PROVIDER in p.read_text(errors="replace") for p in cfgs):
        snippet = f"python3 {q(Path(__file__).resolve().parent / 'oc_harness.py')} snippet {major or 1}"
        problems.append(f"no opencode.json names the {oc.PROVIDER} provider — merge the output of `{snippet}` "
                        "into ~/.config/opencode/opencode.json (not auto-fixed)")
    excl = common_dir(root) / "info" / "exclude"
    have_excl = excl.read_text() if excl.exists() else ""
    fix_excl = any(ln not in have_excl for ln in EXCLUDE_LINES)
    if fix_excl:
        problems.append("git info/exclude lacks dev-team entries (.claude/dev-team/, .slice/, dep dirs)")
    notes.append(f"governor tier {resolve_tier()} (start/ceiling {TIERS[resolve_tier()]}); lane signals from "
                 f"{state_dir(root) / 'lanes'}")
    out(*[f"- {n}" for n in notes])
    if not problems:
        out("DOCTOR: all good")
        return
    out("DOCTOR found:", *[f"  ✗ {p}" for p in problems])
    if not a.fix:
        out("run `doctor --harness opencode --fix` to install the dev-team agents, guard plugin and skill "
            "for the detected OpenCode major and update git excludes")
        return
    if reinstall and major:
        for path in oc.install(str(skill_dir), major, home):
            out(f"installed {path}")
    elif reinstall:
        out("opencode not found — install it, then run `doctor --harness opencode --fix` again")
    if fix_excl:
        ensure_excludes(root)
        out("updated git info/exclude")
    if reinstall and major:
        out("RESTART OpenCode so it loads the new agents and plugin.")
```

- [ ] **Step 12: Route `cmd_doctor` by harness**

In `skills/glm/dev-team-glm/scripts/devteam.py`, replace the first lines of `cmd_doctor`:

```python fragment
def cmd_doctor(a):
    root = toplevel()
    problems, notes, fixes = [], [], {}
```

with:

```python fragment
def cmd_doctor(a):
    root = toplevel()
    harness = getattr(a, "harness", None) or ("opencode" if is_opencode() else "claude")
    if harness == "opencode":
        return doctor_opencode(a, root)
    problems, notes, fixes = [], [], {}
```

Everything below that line in `cmd_doctor` stays as it is, so the Claude Code report is byte-identical.

- [ ] **Step 13: Add the `--harness` flag to the parser**

In `main()` of `skills/glm/dev-team-glm/scripts/devteam.py`, replace:

```python fragment
    pr = sp.add_parser("doctor"); pr.add_argument("--fix", action="store_true"); pr.set_defaults(fn=cmd_doctor)
```

with:

```python fragment
    pr = sp.add_parser("doctor"); pr.add_argument("--fix", action="store_true"); pr.add_argument("--harness", choices=["claude", "opencode"]); pr.set_defaults(fn=cmd_doctor)
```

- [ ] **Step 14: Run the tests to verify they pass**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -p test_devteam_oc_doctor.py -v`
Expected: PASS, ending in `Ran 18 tests` and `OK` (`test_plugin_load_error` shows `skipped 'node not installed'` when node is absent)

- [ ] **Step 15: Check the CLI flag**

Run: `python3 skills/glm/dev-team-glm/scripts/devteam.py doctor --help`
Expected: usage line `usage: devteam.py doctor [-h] [--fix] [--harness {claude,opencode}]`

- [ ] **Step 16: Run the whole Python suite and the dev-team selftest**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -v`
Expected: PASS, ending in `OK`

Run: `DEVTEAM_HARNESS=claude bash skills/glm/dev-team-glm/scripts/selftest.sh; echo "exit=$?"`
Expected: every check passes and the last line is `exit=0`

- [ ] **Step 17: Commit**

```bash
git add skills/glm/dev-team-glm/scripts/devteam.py skills/glm/_shared/tests/test_devteam_oc_doctor.py
git commit -m "feat(dev-team): governor reads OpenCode lane events; doctor --harness opencode with --fix via oc_harness.install"
```

---

### T07: dev-team SKILL.md and README for OpenCode [P]

**Depends:** T05, T06

**Interfaces:**
- Consumes: `def is_opencode() -> bool`; `def emit_agent(root, st, agent, model, prompt, label) -> str`; `def launch_lane(root, st, lane_id, agent, model, prompt) -> int`; `def cmd_lane_run(a)`; `def cmd_wait(a)`; `devteam.py lane-run <lane_id>`; `devteam.py wait [--timeout 100]`; `def lane_signals(root, st) -> dict`; `def cmd_doctor(a)`; `--harness opencode`; `--fix`; `oc_harness.install`
- Produces: `name: dev-team`; `start`; `wait`; `next`; `retry`

**Files:**
- Modify: `skills/glm/dev-team-glm/SKILL.md:1-2`
- Modify: `skills/glm/dev-team-glm/SKILL.md:42-44`
- Modify: `skills/glm/dev-team-glm/README.md:32-48`

- [ ] **Step 1: Change SKILL.md frontmatter name**

Replace the frontmatter `name` field from `dev-team-glm` to `dev-team`:

```yaml
---
name: dev-team
```

- [ ] **Step 2: Add OpenCode protocol section to SKILL.md**

After line 44 ("end the turn."), insert a new section describing the OpenCode dispatch flow:

```markdown

#### OpenCode protocol

On OpenCode, when `DEVTEAM_HARNESS=opencode` or `OPENCODE` is set, the Conductor routes every lane through worktrees:

| Command | Purpose |
| --- | --- |
| `devteam start <plan.md>` | Initialize the run: `doctor --fix` installs agents, creates git worktrees at `.claude/dev-team/wt/<id>`, checks the plan, and prints ready lanes. Each lane process gets `env DEVTEAM_ROLE=<agent>` and `DEVTEAM_SLICE=<id>`. |
| `devteam wait [--timeout 100]` | Block up to `--timeout` seconds (default 100, below OpenCode's 120s bash-tool limit) for a new lane result or completion marker in `.claude/dev-team/lanes/`. Print `NEXT: devteam next` when a marker arrives. |
| `devteam next` | Read all lane JSON output and markers (`.done`/`.blocked`), merge results, queue fixes, dispatch ready lanes and any retries, print the endgame. Stop gate runs after each programmer lane: `lane-run` pipes `{"cwd": <worktree>, "last_assistant_message": <text>}` to `guard.py stop`; exit 2 means blocked, re-run once per block with gate stderr appended to brief, force-finish after 2 blocks. The governor reads lane files instead of Claude Code transcripts: a lane ending `FAIL`/`STALL`/`TIMEOUT` in `.claude/dev-team/lanes/<id>.done` prints `LANE DOWN <id> (<kind>): the lane process ended <error>` — a stuck slice retries cold (`fail <id>` then `retry <id>`, worktree kept for salvage); a stuck review/research lane just relaunches (`lane-run <id>`). |
| `devteam retry <id> [--files ...]` | Cold retry: create a fresh worktree, switch to a stronger model (GLM-5.3), re-dispatch with optional file scope. |

Lanes run `python3 <devteam.py> lane-run <id>` in their worktree; it claims the slice, runs through vendored `oc_harness.run_lanes`, and pipes stop-gate JSON. Markers go to `.claude/dev-team/slices/<id>.done|.blocked` (stop gate only). Lane outputs go to `.claude/dev-team/lanes/<id>.jsonl|.err|.done` (runner only). Tools: `edit`/`write`/`patch` (file operations) and `bash` (shell commands) are checked by `guard.py oc` mode (programmer → existing checks; other roles → read-only with role in agent_type; no role → silent allow). Plugins (v1 and v2) forward calls to `python3 guard.py oc` on stdin and throw `Error(reason)` on deny; allow on any plugin-side failure.

```

- [ ] **Step 3: Add Vietnamese OpenCode section to README.md**

After line 48 ("Yêu cầu: Claude Code ≥ 2.1.267, git ≥ 2.31, python3. Phải trust đúng thư mục repo (hook trong frontmatter agent chỉ nạp khi thư mục đó được trust)."), add a new section:

```markdown

#### OpenCode

Trên OpenCode (khi `DEVTEAM_HARNESS=opencode` hoặc `OPENCODE` được set), devteam chạy mỗi lane trong một git worktree riêng qua `oc_harness run`:

1. **Cài đặt:** `oc_harness.install` sao chép plugin guard (v1 hoặc v2 tùy major version) và các agent vào home OpenCode.
2. **Start:** `devteam start` tạo worktree tại `.claude/dev-team/wt/<id>` từ branch `devteam/<id>`, chạy `doctor --fix`, ghi env `DEVTEAM_ROLE`/`DEVTEAM_SLICE`.
3. **Vòng lặp:** `devteam wait` chặn tối đa 100s đợi kết quả lane → `devteam next` đọc output JSON, chạy stop gate (kiểm tra qua `guard.py oc`), dispatch lane mới + retry.
4. **Stop gate:** Sau mỗi programmer lane, `lane-run` gọi `guard.py stop` với `{"cwd": <worktree>, "last_assistant_message": <text>}`; exit 2 = blocked, retry tối đa 2 lần với stderr gate thêm vào brief.
5. **Markers:** `.done` và `.blocked` ghi vào `.claude/dev-team/slices/<id>.*` (stop gate); lane output ghi `.claude/dev-team/lanes/<id>.jsonl|.err|.done` (runner).
6. **Tool guards:** Plugin v1/v2 pipe JSON (tương tự Claude hook) đến `guard.py oc`; programmer dùng kiểm tra hiện tại, role khác → read-only, không role → im lặng. Lỗi plugin → allow (fail-open).
7. **Retry:** `devteam retry <id>` tạo worktree mới, nâng lên GLM-5.3, có thể mở rộng file scope.
8. **Lane chết:** Governor đọc file lane (`.claude/dev-team/lanes/<id>.done`) thay vì transcript; lane kết thúc `FAIL`/`STALL`/`TIMEOUT` → in `LANE DOWN <id> (<kind>)` kèm cách sửa: slice thì `fail <id>` rồi `retry <id>` (giữ worktree để cứu dữ liệu); review/research thì chạy lại bằng `lane-run <id>`.
9. **Doctor:** `python3 devteam.py doctor --harness opencode` kiểm tra agent, plugin, config, major version match.

```

- [ ] **Step 4: Commit**

```bash
git add skills/glm/dev-team-glm/SKILL.md skills/glm/dev-team-glm/README.md
git commit -m "docs: OpenCode protocol for dev-team SKILL.md and README"
```

---

### T08: selftest end-to-end checks for the OpenCode path [P]

**Depends:** T03, T05, T06

**Interfaces:**
- Consumes: `devteam-guard.v1.js`; `DevteamGuard`; `devteam-guard.v2.js`; `Plugin.define({ id: "devteam-guard", setup })`; `guard.py oc`; `def is_opencode() -> bool`; `def emit_agent(root, st, agent, model, prompt, label) -> str`; `def launch_lane(root, st, lane_id, agent, model, prompt) -> int`; `def cmd_lane_run(a)`; `def cmd_wait(a)`; `devteam.py lane-run <lane_id>`; `devteam.py wait [--timeout 100]`; `def lane_signals(root, st) -> dict`; `def cmd_doctor(a)`; `--harness opencode`; `--fix`; `oc_harness.install`
- Produces: `start`; `wait`; `next`; `DEVTEAM_HARNESS=opencode`; `opencode`; `PATH`; `.done`; `guard.py stop`; `guard.py oc`

**Files:**
- Modify: `skills/glm/dev-team-glm/scripts/selftest.sh:1043-1045`

- [ ] **Step 1: Add the OpenCode end-to-end selftest section**

Insert the block below into `skills/glm/dev-team-glm/scripts/selftest.sh` immediately before the closing summary (the `echo`, `echo "passed=$pass failed=$fail"`, `[ "$fail" -eq 0 ]` lines at the end of the file). It reuses the file's existing `D`, `check`, `newrepo`, `$S`, `$G` and `$TMP` helpers, which are already defined earlier in the script.

~~~~bash
echo "== OpenCode harness: start/wait/next against a stub opencode on PATH"
ROC="$(newrepo rocx)"; cd "$ROC"
cat > plan.md <<'EOF'
```json
{"request":"oc port","commands":{"test":"true"},"slices":[{"id":"O1","title":"oc slice","deps":[],"files":["src/o1.js","tests/o1.test.js"],"risk":"low","criteria":["works"]}]}
```
EOF
OCBIN="$(mktemp -d)"
export DEVTEAM_PY="$S/devteam.py"
cat > "$OCBIN/opencode" <<'SH'
#!/usr/bin/env bash
set -u
if [ "${1:-}" = "--version" ]; then echo "1.18.32"; exit 0; fi
DIR=""; prev=""
for a in "$@"; do
  [ "$prev" = "--dir" ] && DIR="$a"
  prev="$a"
done
if [ "${DEVTEAM_SLICE:-}" = "O1" ] && [ "${DEVTEAM_ROLE:-}" = "programmer" ] && [ -n "$DIR" ]; then
  ( cd "$DIR" \
    && mkdir -p tests \
    && printf 'test("o1", () => { assert.equal(1, 1); });\n' > tests/o1.test.js \
    && python3 "$DEVTEAM_PY" commit-red o1 >/dev/null 2>&1 \
    && echo "impl o1" > src/o1.js \
    && python3 "$DEVTEAM_PY" commit-green o1 >/dev/null 2>&1 )
fi
printf '%s\n' '{"type":"text","part":{"type":"text","text":"## Status: Complete -- ## Gate: node -e 1 -> ok"}}'
exit 0
SH
chmod +x "$OCBIN/opencode"
OLDPATH="$PATH"
export PATH="$OCBIN:$PATH"
export DEVTEAM_HARNESS=opencode
OUT=$(D start plan.md 2>&1)
check "opencode start dispatches O1 through the OpenCode seam" '[[ "$OUT" == *"DISPATCH O1"* ]]'
WAITOUT=$(D wait --timeout 30 2>&1)
check "devteam.py wait blocks until the lane result appears then tells the Conductor what to run next" '[[ "$WAITOUT" == *"NEXT: devteam next"* ]]'
check "opencode worktree created at wt/<lane> and claimed" '[ -d "$ROC/.claude/dev-team/wt/O1" ] && [ -d "$ROC/.claude/dev-team/wt/O1/.slice" ] && [ -f "$ROC/.claude/dev-team/lanes/O1.jsonl" ]'
check "lane-run writes .done through guard.py stop" '[ -f "$ROC/.claude/dev-team/slices/O1.done" ]'
NEXTOUT=$(D next 2>&1)
check "opencode next integrates the finished lane" '[[ "$NEXTOUT" == *"O1: MERGED"* ]]'
printf '{"type":"assistant","text":"working"}\n{"type":"system","subtype":"api_error","level":"error","error":{"status":429,"error":{"code":"1302","message":"rate limit"}},"timestamp":"2026-01-01T00:00:00.000Z"}\n' > "$ROC/.claude/dev-team/lanes/O1.jsonl"
GOVOUT=$(DEVTEAM_GOVERNOR=on D status 2>&1)
check "a 1302 throttle row shrinks the governor window (opencode lanes)" '[[ "$GOVOUT" == *"THROTTLED"* && "$GOVOUT" == *"window"*"→"* ]]'
DENYOUT=$(printf '{"cwd":"%s","tool":"edit","args":{"filePath":"%s/outside.js","oldString":"a","newString":"b"}}' "$ROC/.claude/dev-team/wt/O1" "$ROC/.claude/dev-team/wt/O1" | DEVTEAM_ROLE=programmer python3 "$G" oc)
check "guard.py oc denies an out-of-footprint edit" '[[ "$DENYOUT" == *deny* ]]'
export PATH="$OLDPATH"
unset DEVTEAM_HARNESS DEVTEAM_PY

echo "== OpenCode plugin shim round-trip through guard.py for both plugin files"
PLUGDIR="$S/../opencode/plugins"
check "v1 plugin file devteam-guard.v1.js exists" '[ -f "$PLUGDIR/devteam-guard.v1.js" ]'
check "v2 plugin file devteam-guard.v2.js exists" '[ -f "$PLUGDIR/devteam-guard.v2.js" ]'
check "v1 plugin exports DevteamGuard with the tool.execute.before hook" 'grep -q "DevteamGuard" "$PLUGDIR/devteam-guard.v1.js" && grep -q "tool.execute.before" "$PLUGDIR/devteam-guard.v1.js" && grep -q "guard.py" "$PLUGDIR/devteam-guard.v1.js"'
check "v2 plugin exports Plugin.define({ id: \"devteam-guard\", setup }) with the tool.execute.before hook" 'grep -q "devteam-guard" "$PLUGDIR/devteam-guard.v2.js" && grep -q "tool.execute.before" "$PLUGDIR/devteam-guard.v2.js" && grep -q "guard.py" "$PLUGDIR/devteam-guard.v2.js"'
cp "$PLUGDIR/devteam-guard.v1.js" "$TMP/v1.mjs"
cp "$PLUGDIR/devteam-guard.v2.js" "$TMP/v2.mjs"
cat > "$TMP/v1check.js" <<'JS'
const path = require("path");
(async () => {
  const mod = await import(process.argv[2]);
  const hooks = await mod.DevteamGuard({ directory: process.cwd() });
  try {
    await hooks["tool.execute.before"]({ tool: "edit" }, { args: { filePath: path.join(process.cwd(), "outside.js"), oldString: "a", newString: "b" } });
    console.log("ALLOWED");
  } catch (e) {
    console.log("DENIED: " + e.message);
  }
})();
JS
V1RES=$(cd "$ROC/.claude/dev-team/wt/O1" && DEVTEAM_ROLE=programmer node "$TMP/v1check.js" "$TMP/v1.mjs" 2>&1)
check "DevteamGuard (v1 plugin) denies an out-of-footprint edit via guard.py oc" '[[ "$V1RES" == *"DENIED"* ]]'
cat > "$TMP/v2check.js" <<'JS'
const path = require("path");
(async () => {
  const mod = await import(process.argv[2]);
  const plugin = mod.default;
  const hooks = await plugin.setup({ location: { directory: process.cwd() } });
  try {
    await hooks["tool.execute.before"]({ tool: "edit" }, { args: { filePath: path.join(process.cwd(), "outside.js"), oldString: "a", newString: "b" } });
    console.log("ALLOWED");
  } catch (e) {
    console.log("DENIED: " + e.message);
  }
})();
JS
V2RES=$(cd "$ROC/.claude/dev-team/wt/O1" && DEVTEAM_ROLE=programmer node "$TMP/v2check.js" "$TMP/v2.mjs" 2>&1)
check "Plugin.define({ id: \"devteam-guard\", setup }) (v2 plugin) denies an out-of-footprint edit via guard.py oc" '[[ "$V2RES" == *"DENIED"* ]]'
cd "$ROC"
~~~~

- [ ] **Step 2: Run the suite and verify the new checks pass**

Run: `bash skills/glm/dev-team-glm/scripts/selftest.sh`
Expected: the output includes the lines `ok   opencode worktree created at wt/<lane> and claimed`, `ok   lane-run writes .done through guard.py stop`, `ok   opencode next integrates the finished lane`, `ok   a 1302 throttle row shrinks the governor window (opencode lanes)`, `ok   guard.py oc denies an out-of-footprint edit`, `ok   DevteamGuard (v1 plugin) denies an out-of-footprint edit via guard.py oc`, `ok   Plugin.define({ id: "devteam-guard", setup }) (v2 plugin) denies an out-of-footprint edit via guard.py oc`, and the final line is `passed=<N> failed=0` with exit code 0.

- [ ] **Step 3: Commit**

```bash
git add skills/glm/dev-team-glm/scripts/selftest.sh
git commit -m "test: add OpenCode end-to-end selftest checks against a stub opencode CLI"
```

---

### T09: Installer, all-skill test and repo guide include dev-team

**Depends:** T01, T04, T07

**Interfaces:**
- Consumes: `def run_lanes(lanes: list, out_dir: str, width: int = 8, stall: int = 180, binary: str = "opencode", major: int = 0) -> list`; `env: dict`; `os.environ`; `def install(skill_dir: str, major: int, home: str = "") -> list`; `opencode/plugins/<base>.v<major>.js`; `<home>/.config/opencode/plugins/<base>.js`; `{{SKILL_DIR}}`; `skills/glm/dev-team-glm/agents/*.md`; `/devteam`; `name: dev-team`; `start`; `wait`; `next`; `retry`
- Produces: `install-opencode.sh`; `dev-team-glm`; `test_all_skills.py`

**Files:**
- Modify: `skills/glm/install-opencode.sh`
- Modify: `skills/glm/_shared/tests/test_all_skills.py`
- Modify: `skills/glm/CLAUDE.md`

- [ ] **Step 1: Add dev-team-glm to root installer script**

The `install-opencode.sh` script must call `oc_harness.install()` for dev-team-glm alongside the other skills. Edit the script to add a call after the other skill installations that passes the dev-team-glm path, major version, and home directory to the `install()` function (imported from `oc_harness`), which returns the list of installed paths.

- [ ] **Step 2: Commit installer change**

```bash
git add skills/glm/install-opencode.sh
git commit -m "feat: add dev-team-glm to root OpenCode installer"
```

- [ ] **Step 3: Add dev-team test to all-skills test suite**

The `test_all_skills.py` test suite must verify that `dev-team-glm` is installed and callable on OpenCode. Add a `test_dev_team_glm_installed` method to the existing `TestAllSkills` class that:
1. Imports `sys` and `subprocess`
2. Sets `os.environ["OPENCODE"] = "1"` (restoring the previous value in a `finally` block) to activate the OpenCode path (per Global Constraints line 96)
3. Checks that `skills/glm/dev-team-glm/scripts/devteam.py` exists
4. Runs `python3 skills/glm/dev-team-glm/scripts/devteam.py doctor` with no arguments to verify the script's environment check passes
5. Asserts the return code is 0

```python
    def test_dev_team_glm_installed(self):
        """Verify dev-team-glm is installed and its doctor check passes on OpenCode."""
        import sys
        import subprocess

        old_opencode = os.environ.get("OPENCODE")
        os.environ["OPENCODE"] = "1"
        try:
            dev_team_path = "skills/glm/dev-team-glm/scripts/devteam.py"
            self.assertTrue(os.path.exists(dev_team_path), f"dev-team-glm script not found at {dev_team_path}")

            result = subprocess.run([sys.executable, dev_team_path, "doctor"], capture_output=True)
            self.assertEqual(result.returncode, 0, f"devteam.py doctor failed: {result.stderr.decode()}")
        finally:
            if old_opencode is None:
                os.environ.pop("OPENCODE", None)
            else:
                os.environ["OPENCODE"] = old_opencode
```

- [ ] **Step 4: Run new dev-team test to verify it passes**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -v -k test_dev_team_glm_installed`
Expected: PASS with output `test_dev_team_glm_installed ... ok`

- [ ] **Step 5: Commit test suite change**

```bash
git add skills/glm/_shared/tests/test_all_skills.py
git commit -m "test: add dev-team-glm to all-skills test suite"
```

- [ ] **Step 6: Document dev-team OpenCode flow in CLAUDE.md**

Edit the "Per-skill engines" section of CLAUDE.md (after the existing dev-team entry) to add documentation of how dev-team runs on OpenCode. Insert the following after the existing dev-team note about README.md being in Vietnamese:

```markdown
**dev-team on OpenCode:** When running on OpenCode (env `DEVTEAM_HARNESS=opencode` or `OPENCODE` set), `devteam.py` dispatches each lane to a separate `oc_harness.run_lanes()` call in its own git worktree under `.claude/dev-team/wt/<lane id>`. The programmer's brief is read from stdout of `devteam.py claim <lane id>`. Tool-call enforcement moves from the PreToolUse hook into plugins (`plugins/<base>.v1.js` and `<base>.v2.js`) that run `python3 guard.py oc` mode; a guard rule enforces programmer edit/bash and read-only roles via agent type. Worktrees are created from the slice's recorded base on branch `devteam/<lane id>`. Lane outputs go to `.claude/dev-team/lanes/<id>.jsonl` (handled by `oc_harness`); completion markers stay in `.claude/dev-team/slices/<id>.done|.blocked` (written by `guard.py stop`). The stop gate blocks after each programmer exits, pipes `{"cwd": worktree, "last_assistant_message": final_text}` to `guard.py stop`, and re-runs the lane up to 2 times if blocked (appending stderr to the brief).
```

- [ ] **Step 7: Document plugin setup and role mapping**

Edit CLAUDE.md after the new dev-team OpenCode section to add plugin documentation. Insert after the dev-team documentation:

```markdown
**Plugin role mapping:** OpenCode agent names (programmer, code-reviewer, spot-reviewer, investigator, team-leader) are set in env `DEVTEAM_ROLE` per lane. The plugins (`skills/glm/dev-team-glm/opencode/plugins/`) define v1 and v2 shapes; at install time, `oc_harness.install()` copies the matching major version to `<home>/.config/opencode/plugins/`. v1 plugin exports `DevteamGuard` hook; v2 exports a `Plugin.define` with id `devteam-guard` (from opencode.ai/v2/docs/build/plugins). Both hooks run before tool execution: on receipt of `edit`, `write`, `patch`/`apply_patch`, or `bash` tools, they call `python3 guard.py oc` with JSON on stdin and throw `Error(reason)` if the decision is `deny`. Guard mode choice: programmer role gets `edit`/`bash` checks; any other role gets read-only (`edit-ro`/`bash-ro`) with `agent_type` set to the role; no role prints nothing (silent allow). Plugin failures allow calls (same fail-open as Python-side guard).
```

- [ ] **Step 8: Verify CLAUDE.md syntax and structure**

Read the modified sections of `CLAUDE.md` to confirm:
1. The new documentation is valid Markdown with no heading levels (no `#`, `##`, `###`)
2. References to files and functions match the contract (plugin paths, function names, env vars)
3. Text flows naturally and fits the existing style (concise, code-centric, complete and clear)

- [ ] **Step 9: Commit CLAUDE.md changes**

```bash
git add skills/glm/CLAUDE.md
git commit -m "docs: add dev-team OpenCode flow and plugin documentation to CLAUDE.md"
```

- [ ] **Step 10: Run full test suite to verify no regressions**

Run: `python3 -m unittest discover -s skills/glm/_shared/tests -t skills/glm/_shared/tests -v`
Expected: All tests pass (exit 0)
