# ZCode hardening Implementation Plan

> **Execution note:** This plan is self-contained and tool-agnostic. Any AI
> agent or human engineer can execute it with only a shell, a code editor, and
> git. Follow the Execution Protocol below.

**Goal:** Make all eight `glm-*` skills install and run perfectly on ZCode 3.14.4 via `install-zcode.sh`, per the approved spec.

**Architecture:** Mirror the existing OpenCode integration pattern: a shared-key fix, a new `zcode` hook-bridge mode in the dev-team guard, a `zcode` harness mode in the dev-team engine (dispatch + doctor that installs agents and merges user-level hook config), installer conversion fixes with doctor delegation, and per-skill guidance/doc corrections from the completed audit.

**Tech Stack:** stdlib-only Python 3 (`unittest`, no pytest), POSIX `sh`, no build step.

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

- Work directly on `main`, one commit per task, existing git identity, no co-author trailers. Never stage the uncommitted root `AGENTS.md`/`CLAUDE.md` edits.
- Everything stays inside `glm-skills/`. All tests live under `_shared/tests/` (new file or extend an existing one); the full suite `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests` run from `glm-skills/` must stay green after every task.
- Never edit a vendored `scripts/zai_client.py` copy by hand: edit `_shared/zai_client.py`, then run `sh _shared/sync.sh` and commit the regenerated copies in the same task.
- SKILL.md frontmatter: `name` equals the folder name; `description` ≤ 1024 chars with the WHEN-to-use clause inside the first 250 chars.
- ZCode agent frontmatter accepts only: `name`, `description`, `model`, `thoughtLevel`, `color`, `tools`, `disallowedTools`, `maxTurns`, `injectAgentsMd`, `mcpServers`, `background`. No `effort`, `hooks`, `mode`, `permissionMode`, `steps`, `omitClaudeMd`, `isolation`, `memory`, `temperature`, `variant`. No `haiku`/`sonnet`/`opus` aliases anywhere ZCode reads — real ids `glm-5.3` / `glm-5.3-flash` only, and `thoughtLevel` only honored next to a specific `model`.
- ZCode hook config is written only to `~/.zcode/cli/config.json` as a key-preserving merge (existing user keys survive, `.bak` before rewrite, re-run is a no-op), and the hook commands point at the absolute `guard.py` path of the installed skill.
- Files are English; the dev-team `README.md` section for this feature is Vietnamese like the rest of that file. Record behavior changes in the skill's CHANGELOG/README where one exists.
- Harness facts are exactly the spec's "Verified ZCode facts" (spec L13-38): never invent ZCode behavior beyond them; where the spec says something is unverified, keep it labeled unverified.

## References

- `glm-skills/_shared/tests/test_install_zcode.py` - temp-home installer test exemplar: how every installer/doctor behavior here is proven end to end.

## File Structure

- `glm-skills/_shared/` — zai_client.py (T01)
- `glm-skills/_shared/tests/` — test_zai_client.py (T01), test_guard_zcode.py (T02), test_devteam_zcode.py (T03), test_devteam_zcode_doctor.py (T04), test_install_zcode.py (T06), test_brainstorm_oc.py (T07), test_adopt_audit.py (T09), test_glm_docgen_snippets.py (T10), test_all_skills.py (T10), test_adopt_plan.py (T13)
- `glm-skills/glm-systematic-debugging/scripts/` — zai_client.py (T01), debug_tool.py (T12)
- `glm-skills/glm-writing-plans/scripts/` — zai_client.py (T01), plan_tool.py (T13)
- `glm-skills/glm-requirements-code-audit/scripts/` — zai_client.py (T01), audit.py (T09)
- `glm-skills/glm-dev-team/scripts/` — guard.py (T02), devteam.py (T03, T04), selftest.sh (T03)
- `glm-skills/glm-dev-team/` — SKILL.md (T05), README.md (T05)
- `glm-skills/` — install-zcode.sh (T06), CLAUDE.md (T14)
- `glm-skills/glm-brainstorming/` — SKILL.md (T07), glm-tuning.md (T07), fanout-playbook.md (T07), architectural.md (T07), visual-companion.md (T07), CHANGELOG.md (T07)
- `glm-skills/glm-brainstorming/scripts/` — context.sh (T07)
- `glm-skills/glm-idea-to-spec/` — SKILL.md (T08)
- `glm-skills/glm-requirements-code-audit/` — SKILL.md (T09), SETUP.md (T09)
- `glm-skills/glm-requirements-code-audit/agents/zcode/` — glm-rca-investigator.md (T09), glm-rca-verifier.md (T09)
- `glm-skills/glm-requirements-code-audit/references/` — glm-tuning.md (T09)
- `glm-skills/glm-doc-generator/` — SKILL.md (T10)
- `glm-skills/glm-doc-generator/agents/zcode/` — glm-doc-writer.md (T10), glm-doc-reviewer.md (T10)
- `glm-skills/glm-git-diff-summary/` — SKILL.md (T11)
- `glm-skills/glm-systematic-debugging/references/` — glm-tuning.md (T12)
- `glm-skills/glm-systematic-debugging/` — README.md (T12)
- `glm-skills/glm-writing-plans/` — SKILL.md (T13), CHANGELOG.md (T13)
- `glm-skills/glm-writing-plans/references/` — glm-tuning.md (T13)

## Contracts

#### T01: ZCode credentials in shared key discovery
- Files: `glm-skills/_shared/zai_client.py`, `glm-skills/_shared/tests/test_zai_client.py`, `glm-skills/glm-systematic-debugging/scripts/zai_client.py`, `glm-skills/glm-writing-plans/scripts/zai_client.py`, `glm-skills/glm-requirements-code-audit/scripts/zai_client.py`
- Produces: `KEY_FILES = (..., "~/.zcode/v2/credentials.json", "~/.zcode/settings.json", "~/.zcode/auth.json", "~/.zcode/config.json")` with the v2 entry first among zcode paths; `KEY_FIELDS = ("ZAI_API_KEY", "GLM_API_KEY", "ANTHROPIC_AUTH_TOKEN", "apiKey", "api_key", "key", "api-key")`; `class TestZcodeCredentialsKey(unittest.TestCase)` proving: a nested `account-provider → coding-plan → account → <plan> → <uuid> → api-key` value is found from `~/.zcode/v2/credentials.json`; sibling `oauth`/`zcodejwttoken`/`access_token` fields are never picked; env vars still win over the file
- Consumes: `def _walk_for_key(obj, depth=0):` (existing); `def find_key(extra_env: tuple = ()) -> tuple:` (existing)
- Spec: L36-38, L51-57, L143-145

#### T02: guard zcode hook mode
- Files: `glm-skills/glm-dev-team/scripts/guard.py`, `glm-skills/_shared/tests/test_guard_zcode.py`
- Produces: `def guard_zcode(inp):` wired into `main()` as `"zcode": guard_zcode`; `class TestGuardZcode(unittest.TestCase)` proving: a missing or non-dev-team `agent_type` silently allows; a programmer-role `agent_type` with `tool_name` Write/Edit routes to the edit check and with Bash routes to the bash check (a check that would return silent-allow returns an explicit deny instead, mirroring the oc mode); reviewer/leader/investigator roles route to the read-only checks; `hook_event_name: Stop` routes to the stop gate only for programmer roles and always allows otherwise; malformed stdin/JSON fails open to allow
- Consumes: `def guard_edit(inp):` (existing); `def guard_bash(inp):` (existing); `def guard_edit_ro(inp):` (existing); `def guard_bash_ro(inp):` (existing); `def guard_stop(inp):` (existing); `def allow(reason=None):` (existing); `def deny(reason):` (existing)
- Read: `glm-skills/_shared/tests/test_guard_oc.py`
- Spec: L29-35, L73-84, L143-150
- Tier: deep

#### T03: engine zcode core
- Files: `glm-skills/glm-dev-team/scripts/devteam.py`, `glm-skills/glm-dev-team/scripts/selftest.sh`, `glm-skills/_shared/tests/test_devteam_zcode.py`
- Produces: `def is_zcode() -> bool:` (DEVTEAM_HARNESS=zcode, else the vendored harness check returning "zcode"); `detect_provider(root=None, st=None)` returning "glm" by default on zcode; `dispatch_route(st, s, mode)` returning `glm-programmer-strong` for strong slices on zcode and an Agent line with no `model:` segment; argparse doctor `--harness` choices `["claude", "opencode", "zcode"]`; `class TestDevteamZcodeCore(unittest.TestCase)` proving is_zcode by env and by path, the glm provider default, strong/lite routing, and the model-less Agent line; `selftest.sh` gains the zcode-dispatch checks
- Consumes: `def is_opencode() -> bool:` (existing); `_oc_harness().harness(path)` (existing); `def dispatch_route(st, s, mode):` (existing, modified in place)
- Read: `glm-skills/_shared/tests/test_devteam_oc_harness.py`
- Spec: L23-28, L85-91, L143-150

#### T04: doctor zcode
- Depends: T02, T03
- Files: `glm-skills/glm-dev-team/scripts/devteam.py`, `glm-skills/_shared/tests/test_devteam_zcode_doctor.py`
- Produces: `def doctor_zcode(a, root):` with `doctor --harness zcode [--fix] [--flash ID] [--main ID]`; `def render_agent_zcode(agents_src, name, flash, main) -> str:` converting the five agent files plus rendered `glm-programmer-lite` (model flash, thoughtLevel low) and `glm-programmer-strong` (model main, thoughtLevel high) from `glm-programmer.md`, mapping `steps: N` to `maxTurns: N`, `omitClaudeMd: true` to `injectAgentsMd: false`, `effort` to `thoughtLevel`, aliases to real ids, dropping effort/isolation/memory/omitClaudeMd/hooks/mode/temperature/steps/permissionMode/variant and keeping name/description/model/thoughtLevel/color/tools/disallowedTools/maxTurns/background; a key-preserving merge writing the PreToolUse (`Write|Edit`, `Bash`) and Stop hook entries plus `hooks.enabled: true` into `~/.zcode/cli/config.json` (`type: process`, absolute `guard.py` path, `.bak` before rewrite, idempotent, prints how to disable); `cmd_doctor` and `cmd_start` routing to it on zcode; `class TestDevteamZcodeDoctor(unittest.TestCase)` in a temp HOME proving: the seven agents land in `~/.zcode/agents/` with exactly the ZCode key set (no `model:` alias, no `effort:`/`hooks:`/`mode:`/`permissionMode:` line), the hooks merge preserves a pre-existing user `plugins` config, re-run is a no-op, a changed file earns `.bak`, and no `.claude/settings.local.json` is written
- Consumes: `def is_zcode() -> bool:`; `def guard_zcode(inp):`; `def agent_source(agents_src, name):` (existing)
- Read: `glm-skills/_shared/tests/test_devteam_oc_doctor.py`
- Spec: L18-22, L29-35, L92-99, L143-150
- Tier: deep

#### T05: dev-team protocol docs
- Depends: T03, T04
- Files: `glm-skills/glm-dev-team/SKILL.md`, `glm-skills/glm-dev-team/README.md`
- Produces: a "ZCode protocol" section in SKILL.md mirroring "OpenCode protocol": the Task-style tool takes `subagent_type` + `run_in_background` and no per-dispatch model; wake-up is a lane completion notification → `devteam next [<id>]` (no stop-hook marker dependency; the engine-side integrate re-check is the gate); `SendMessage`/`TaskStop` exist; installs need a new session; and a matching Vietnamese section in README.md
- Spec: L23-28, L100-104

#### T06: installer conversion and delegation
- Depends: T04
- Files: `glm-skills/install-zcode.sh`, `glm-skills/_shared/tests/test_install_zcode.py`
- Produces: `convert()` mapping `steps: N` → `maxTurns: N` and `omitClaudeMd: true` → `injectAgentsMd: false`, dropping `permissionMode`, keeping `background`; the seven dev-team ZCode agents delegated to `devteam.py doctor --harness zcode --fix` with `--flash/--main` passed through (same pattern as the existing plan-tool delegation); `glm-debug-worker.md` conversion gaining `thoughtLevel: low`; the closing message corrected (ZCode has hooks installable via doctor, body >100KB truncates rather than drops, installs need a new session); `InstallZcodeTests` extended: lite and strong present with model and thoughtLevel after install, an end-to-end mapping test that copies the tree to a temp dir, adds a fixture agent with `steps:`/`omitClaudeMd:`, runs the installer from the copy and asserts the converted output, and message assertions (no "ZCode does not have" claim; mentions doctor for guards)
- Spec: L58-72, L145-147, L151-152

#### T07: brainstorming zcode surface
- Files: `glm-skills/glm-brainstorming/SKILL.md`, `glm-skills/glm-brainstorming/glm-tuning.md`, `glm-skills/glm-brainstorming/fanout-playbook.md`, `glm-skills/glm-brainstorming/architectural.md`, `glm-skills/glm-brainstorming/visual-companion.md`, `glm-skills/glm-brainstorming/scripts/context.sh`, `glm-skills/glm-brainstorming/CHANGELOG.md`, `glm-skills/_shared/tests/test_brainstorm_oc.py`
- Produces: a zcode branch in `context.sh` harness detection (no CLAUDE_CODE_* caps line; width cap 8) with its test; the bootstrap/`oc_harness.py` path loop gaining `~/.zcode/skills/glm-brainstorming`; the TaskCreate row naming `TodoWrite`; the OpenCode-only tool-name maps and Claude-Code-only env/Workflow facts scoped to their harnesses; AskUserQuestion fallback wording that does not assume a question tool; SendMessage/TaskStop notes covering ZCode; a ZCode entry in the visual-companion platform notes; a ZCode runtime section in `glm-tuning.md`
- Spec: L108-114, L143-152

#### T08: idea-to-spec trigger front-load
- Files: `glm-skills/glm-idea-to-spec/SKILL.md`
- Produces: `description` reordered so the WHEN-to-use clause sits inside the first 250 chars, total still ≤ 1024; the Phase-2 question line gains a plain-text fallback (no question tool assumed)
- Spec: L115-116, L13-17
- Tier: light

#### T09: requirements-code-audit zcode surface
- Files: `glm-skills/glm-requirements-code-audit/SKILL.md`, `glm-skills/glm-requirements-code-audit/agents/zcode/glm-rca-investigator.md`, `glm-skills/glm-requirements-code-audit/agents/zcode/glm-rca-verifier.md`, `glm-skills/glm-requirements-code-audit/scripts/audit.py`, `glm-skills/glm-requirements-code-audit/SETUP.md`, `glm-skills/glm-requirements-code-audit/references/glm-tuning.md`, `glm-skills/_shared/tests/test_adopt_audit.py`
- Produces: `description` reordered with the WHEN-clause inside the first 250 chars (≤ 1024); the standard bootstrap path loop (including the `~/.zcode/skills/<name>` candidate) with the explicit `A=` first call; CamelCase `tools: Read, Grep, Glob, Write` values in both zcode agents; the zcode dispatch line naming the agent without `subagent_type=` jargon and no alias; `setup --harness zcode` stripping `opencode/` and `SETUP.md` from the copied tree; SETUP.md/glm-tuning.md claims corrected (hooks exist user-level, key paths include the v2 credentials file, char count recomputed); tests updated to the new outputs
- Spec: L117-122, L151-152

#### T10: doc-generator zcode fixes
- Files: `glm-skills/glm-doc-generator/SKILL.md`, `glm-skills/glm-doc-generator/agents/zcode/glm-doc-writer.md`, `glm-skills/glm-doc-generator/agents/zcode/glm-doc-reviewer.md`, `glm-skills/_shared/tests/test_glm_docgen_snippets.py`, `glm-skills/_shared/tests/test_all_skills.py`
- Produces: the recon row corrected (Explore is a ZCode built-in; `general` is the OpenCode one); Appendix A frontmatters gaining `model: glm-5.3-flash` so `thoughtLevel` is honored, with the text pointing at the auto-installed `agents/zcode/` files; `agents/zcode/glm-doc-reviewer.md` switched to `model: glm-5.3` + `thoughtLevel: high`; the `OC_MAX_LANES` mention scoped to OpenCode; the hygiene and snippet tests updated to the corrected rows and agent files
- Spec: L123-127, L151-152

#### T11: git-diff-summary fan-out row
- Files: `glm-skills/glm-git-diff-summary/SKILL.md`
- Produces: the FAN_OUT ZCode row without `model: haiku` — `subagent_type: general-purpose` with the real-id recovery text only
- Spec: L128-129, L23-28
- Tier: light

#### T12: systematic-debugging zcode text
- Files: `glm-skills/glm-systematic-debugging/scripts/debug_tool.py`, `glm-skills/glm-systematic-debugging/references/glm-tuning.md`, `glm-skills/glm-systematic-debugging/README.md`
- Produces: `SETUP["zcode"]` text pointing at `install-zcode.sh` (frontmatter rewrite plus `thoughtLevel: low` for the debug worker) instead of a raw copy; glm-tuning.md corrected (key discovery paths including the v2 credentials file; the turn-budget failure mode says `maxTurns`, not `steps`, for the zcode install); the README ZCode row aligned with the installer
- Spec: L130-132, L143-152

#### T13: writing-plans zcode dispatch
- Files: `glm-skills/glm-writing-plans/scripts/plan_tool.py`, `glm-skills/glm-writing-plans/SKILL.md`, `glm-skills/glm-writing-plans/references/glm-tuning.md`, `glm-skills/glm-writing-plans/CHANGELOG.md`, `glm-skills/_shared/tests/test_adopt_plan.py`
- Produces: the zcode dispatch headers naming the agent (`glm-plan-task-writer` or the fallback) with no `subagent_type=`/`model sonnet` jargon and real ids where a model must be named; `agent_file("zcode")` gaining `maxTurns: 16`; SKILL.md R9 scoping `ANTHROPIC_BASE_URL` to Claude-compatible harnesses; glm-tuning.md key/truncation claims corrected; CHANGELOG entry; tests updated to the new agent file and headers
- Spec: L133-136, L151-152

#### T14: folder guide zcode facts
- Files: `glm-skills/CLAUDE.md`
- Produces: the ZCode facts in the folder guide updated — hooks exist user-level via `~/.zcode/cli/config.json` (no SubagentStop), the dispatch tool schema (`subagent_type`, `run_in_background`, no model), the credentials path, body >100KB truncation, the lite/strong agent split, and the new-session reload rule; commands section gains the doctor delegation note for `install-zcode.sh`
- Spec: L13-38, L137-141
- Tier: light

<!-- WAVES -->
## Execution Waves

Every task in a wave has all its Depends/Runs-after tasks in earlier waves. Tasks in the
same wave touch disjoint files, so a wave's `[P]` tasks may all run at once.

- **Wave 1:** T01 [P], T02 [P], T03 [P], T07 [P], T08 [P], T09 [P], T10 [P], T11 [P], T12 [P], T13 [P], T14 [P]
- **Wave 2:** T04
- **Wave 3:** T05 [P], T06 [P]
<!-- /WAVES -->

<!-- TASKS -->

### T01: ZCode credentials in shared key discovery [P]

**Depends:** —

**Interfaces:**
- Uses existing: `def _walk_for_key(obj, depth=0):`; `def find_key(extra_env: tuple = ()) -> tuple:`
- Produces: `KEY_FILES = (..., "~/.zcode/v2/credentials.json", "~/.zcode/settings.json", "~/.zcode/auth.json", "~/.zcode/config.json")`; `KEY_FIELDS = ("ZAI_API_KEY", "GLM_API_KEY", "ANTHROPIC_AUTH_TOKEN", "apiKey", "api_key", "key", "api-key")`; `class TestZcodeCredentialsKey(unittest.TestCase)`; `account-provider → coding-plan → account → <plan> → <uuid> → api-key`; `~/.zcode/v2/credentials.json`; `oauth`; `zcodejwttoken`; `access_token`

**Files:**
- Modify: `glm-skills/_shared/zai_client.py`
- Modify: `glm-skills/_shared/tests/test_zai_client.py`
- Modify: `glm-skills/glm-systematic-debugging/scripts/zai_client.py`
- Modify: `glm-skills/glm-writing-plans/scripts/zai_client.py`
- Modify: `glm-skills/glm-requirements-code-audit/scripts/zai_client.py`

- [ ] **Step 1: Write the failing tests**

Add the block below to the very end of `glm-skills/_shared/tests/test_zai_client.py`; if the file ends with an `if __name__ == "__main__":` block, place it just above that block. The block is self-contained and safe to add next to existing imports: re-imports are cached and a duplicate `sys.path` entry is harmless.

```python
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import zai_client  # noqa: E402


class TestZcodeCredentialsKey(unittest.TestCase):
    """The v2 credentials file: the api-key field under account-provider → coding-plan → account → <plan> → <uuid> → api-key is found; sibling OAuth/JWT fields are never picked; env vars still win."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def write_credentials(self, api_key):
        d = os.path.join(self.home, ".zcode", "v2")
        os.makedirs(d, exist_ok=True)
        payload = {
            "account-provider": {
                "coding-plan": {
                    "account": {
                        "contribute": {
                            "00000000-1111-2222-3333-444444444444": {
                                "api-key": api_key,
                                "oauth": "oauth-sibling-not-a-key",
                                "zcodejwttoken": "jwt-sibling-not-a-key",
                                "access_token": "access-sibling-not-a-key",
                            }
                        }
                    }
                }
            }
        }
        with open(os.path.join(d, "credentials.json"), "w", encoding="utf-8") as fh:
            json.dump(payload, fh)

    def test_v2_credentials_walk_finds_api_key_and_ignores_siblings(self):
        self.write_credentials("sk-zcode-plan-key")
        with mock.patch.dict(os.environ, {"HOME": self.home}, clear=True):
            result = zai_client.find_key()
        self.assertIn("sk-zcode-plan-key", result,
                      "zcode v2 credentials api-key not found by find_key()")
        for sibling in ("oauth-sibling-not-a-key", "jwt-sibling-not-a-key",
                        "access-sibling-not-a-key"):
            self.assertNotIn(sibling, result,
                             "sibling OAuth/JWT field picked instead of api-key: " + sibling)

    def test_env_var_wins_over_zcode_credentials_file(self):
        self.write_credentials("sk-file-key")
        with mock.patch.dict(os.environ, {"HOME": self.home, "ZAI_API_KEY": "sk-env-key"},
                             clear=True):
            result = zai_client.find_key()
        self.assertIn("sk-env-key", result, "env var must win over the zcode credentials file")
        self.assertNotIn("sk-file-key", result, "zcode file key must lose to the env var")
        with mock.patch.dict(os.environ, {"HOME": self.home}, clear=True):
            result = zai_client.find_key()
        self.assertIn("sk-file-key", result,
                      "without env vars the zcode file key must be found by find_key()")
```

The temp home contains only the v2 credentials file and the env is cleared, so any found value can only come from that file; the sibling fields sit next to `api-key` inside the uuid object, exactly where real OAuth/JWT fields live.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_zai_client.py -v`
Expected: FAIL — the two new tests fail with `AssertionError: without env vars the zcode file key must be found by find_key()` and `AssertionError: zcode v2 credentials api-key not found by find_key()`; every pre-existing test in the file behaves exactly as before; the summary line reads `FAILED (failures=2)`.

- [ ] **Step 3: Extend the key constants**

Open `glm-skills/_shared/zai_client.py`. Only the two constant tuples near the top of the module change; the walk functions are consumed exactly as they are — the existing `def _walk_for_key(obj, depth=0):` and `def find_key(extra_env: tuple = () -> tuple:` keep their current behavior: env vars first, then the files in `KEY_FILES` order, each walked by field name at depth ≤ 6.

First, find the `KEY_FILES = (` tuple (the list of `~/...` credential paths, in precedence order). Keep every existing entry and its order, and append these four entries as the final elements of the tuple, so the v2 entry is the first of the `zcode` paths and the root-level files follow it. The produced tail of the tuple is exactly `KEY_FILES = (..., "~/.zcode/v2/credentials.json", "~/.zcode/settings.json", "~/.zcode/auth.json", "~/.zcode/config.json")`, where the leading ellipsis is the existing tail kept in its current order. Concretely, the appended entries are:

```python fragment
    "~/.zcode/v2/credentials.json",
    "~/.zcode/settings.json",
    "~/.zcode/auth.json",
    "~/.zcode/config.json",
)
```

Second, make the `KEY_FIELDS` assignment read exactly (the existing entries keep their order; `api-key` is appended last):

```python
KEY_FIELDS = ("ZAI_API_KEY", "GLM_API_KEY", "ANTHROPIC_AUTH_TOKEN", "apiKey", "api_key", "key", "api-key")
```

Nothing else in the module changes: the named-field walk already finds the coding-plan key once the file and field are listed, and the env-vars-first precedence is untouched.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_zai_client.py -v`
Expected: PASS — the two `TestZcodeCredentialsKey` tests report `ok`; the run ends with `OK`.

- [ ] **Step 5: Verify the constants**

Run: `cd glm-skills && python3 -c "import sys; sys.path.insert(0, '_shared'); import zai_client as z; assert z.KEY_FIELDS == ('ZAI_API_KEY', 'GLM_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'apiKey', 'api_key', 'key', 'api-key'), z.KEY_FIELDS; assert z.KEY_FILES[-4:] == ('~/.zcode/v2/credentials.json', '~/.zcode/settings.json', '~/.zcode/auth.json', '~/.zcode/config.json'), z.KEY_FILES; print('key constants ok')"`
Expected: `key constants ok`

- [ ] **Step 6: Regenerate the vendored copies**

Edit `_shared/zai_client.py` only — the three vendored copies are regenerated, never hand-edited. Run the sync, then prove all four files carry the new entry:

Run: `cd glm-skills && sh _shared/sync.sh > /dev/null && grep -c '~/.zcode/v2/credentials.json' _shared/zai_client.py glm-systematic-debugging/scripts/zai_client.py glm-writing-plans/scripts/zai_client.py glm-requirements-code-audit/scripts/zai_client.py`
Expected: exactly these four count lines:

```text
_shared/zai_client.py:1
glm-systematic-debugging/scripts/zai_client.py:1
glm-writing-plans/scripts/zai_client.py:1
glm-requirements-code-audit/scripts/zai_client.py:1
```

- [ ] **Step 7: Run the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: PASS — the run ends with `OK`. If a pre-existing assertion in `test_zai_client.py` pins the exact old `KEY_FILES` or `KEY_FIELDS` tuples, update that expectation to the new tuples from Step 3 — the test module is in this task's file list — and re-run until green.

- [ ] **Step 8: Commit**

```bash
git add glm-skills/_shared/zai_client.py glm-skills/_shared/tests/test_zai_client.py glm-skills/glm-systematic-debugging/scripts/zai_client.py glm-skills/glm-writing-plans/scripts/zai_client.py glm-skills/glm-requirements-code-audit/scripts/zai_client.py
git commit -m "feat: discover zcode credentials in the shared key lookup"
```

---

### T02: guard zcode hook mode [P]

**Depends:** —

**Interfaces:**
- Uses existing: `def guard_edit(inp):`; `def guard_bash(inp):`; `def guard_edit_ro(inp):`; `def guard_bash_ro(inp):`; `def guard_stop(inp):`; `def allow(reason=None):`; `def deny(reason):`
- Produces: `def guard_zcode(inp):`; `main()`; `"zcode": guard_zcode`; `class TestGuardZcode(unittest.TestCase)`; `agent_type`; `agent_type`; `tool_name`; `hook_event_name: Stop`

**Files:**
- Modify: `glm-skills/glm-dev-team/scripts/guard.py`
- Test: `glm-skills/_shared/tests/test_guard_zcode.py`

- [ ] **Step 1: Write the failing tests**

Create `glm-skills/_shared/tests/test_guard_zcode.py` with exactly this content:

```python
import os
import subprocess
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(os.path.dirname(os.path.dirname(HERE)), "glm-dev-team", "scripts", "guard.py")
sys.path.insert(0, os.path.dirname(GUARD))

import guard  # noqa: E402


class TestGuardZcode(unittest.TestCase):
    """zcode hook mode: foreign or missing roles silently allow; lane roles
    route to the shared checks with silent allows turned into explicit denies;
    Stop gates only programmer roles; malformed payloads fail open."""

    def payload(self, **over):
        base = {"hook_event_name": "PreToolUse", "cwd": "/repo"}
        base.update(over)
        return base

    def run_zcode(self, inp):
        """What guard_zcode printed (it always ends in sys.exit), stdout captured."""
        return guard.oc_capture(guard.guard_zcode, inp)

    def test_missing_or_foreign_agent_type_silently_allows(self):
        payloads = [
            {},
            {"agent_type": ""},
            {"agent_type": "general-purpose"},
            {"agent_type": "some-other-agent", "tool_name": "Write",
             "tool_input": {"file_path": "/tmp/notes.txt", "content": "x"}},
            {"agent_type": "glm-doc-writer", "tool_name": "Write",
             "tool_input": {"file_path": "docs/x.md", "content": "x"}},
        ]
        for inp in payloads:
            with mock.patch.object(guard, "guard_edit") as ge, \
                    mock.patch.object(guard, "guard_bash") as gb, \
                    mock.patch.object(guard, "guard_edit_ro") as gro, \
                    mock.patch.object(guard, "guard_bash_ro") as bro, \
                    mock.patch.object(guard, "guard_stop") as stop:
                self.assertEqual(self.run_zcode(inp), "", inp)
            for patched in (ge, gb, gro, bro, stop):
                patched.assert_not_called()

    def test_programmer_write_and_edit_route_to_edit_check(self):
        for tool in ("Write", "Edit"):
            inp = self.payload(agent_type="glm-programmer", tool_name=tool,
                               tool_input={"file_path": "src/app.py", "content": "print('hi')"})
            with mock.patch.object(guard, "guard_edit",
                                   side_effect=lambda i: guard.deny("outside the repo")) as ge:
                out = self.run_zcode(inp)
            ge.assert_called_once_with(inp)
            self.assertIn('"permissionDecision": "deny"', out, tool)
            self.assertIn("outside the repo", out, tool)

    def test_programmer_bash_routes_to_bash_check(self):
        inp = self.payload(agent_type="glm-programmer", tool_name="Bash",
                           tool_input={"command": "python3 -m unittest"})
        with mock.patch.object(guard, "guard_bash",
                               side_effect=lambda i: guard.deny("dangerous command")) as gb:
            out = self.run_zcode(inp)
        gb.assert_called_once_with(inp)
        self.assertIn('"permissionDecision": "deny"', out)
        self.assertIn("dangerous command", out)

    def test_silent_allow_from_edit_check_becomes_explicit_deny(self):
        inp = self.payload(agent_type="glm-programmer", tool_name="Write",
                           tool_input={"file_path": "src/app.py", "content": "x"})
        with mock.patch.object(guard, "guard_edit",
                               side_effect=lambda i: guard.allow()) as ge:
            out = self.run_zcode(inp)
        ge.assert_called_once_with(inp)
        self.assertIn("zcode lane cannot defer to the ask flow: Write", out)
        self.assertIn('"permissionDecision": "deny"', out)

    def test_silent_allow_from_bash_check_becomes_explicit_deny(self):
        inp = self.payload(agent_type="glm-programmer", tool_name="Bash",
                           tool_input={"command": "python3 -m unittest"})
        with mock.patch.object(guard, "guard_bash",
                               side_effect=lambda i: guard.allow()) as gb:
            out = self.run_zcode(inp)
        gb.assert_called_once_with(inp)
        self.assertIn("zcode lane cannot defer to the ask flow: Bash", out)

    def test_read_only_roles_route_to_read_only_checks(self):
        for role in ("glm-code-reviewer", "glm-team-leader", "glm-investigator"):
            inp = self.payload(agent_type=role, tool_name="Write",
                               tool_input={"file_path": "src/app.py"})
            with mock.patch.object(guard, "guard_edit_ro",
                                   side_effect=lambda i: guard.deny("read-only lane")) as gro, \
                    mock.patch.object(guard, "guard_bash_ro") as bro:
                out = self.run_zcode(inp)
            gro.assert_called_once_with(inp)
            bro.assert_not_called()
            self.assertIn("read-only lane", out, role)
        inp = self.payload(agent_type="glm-investigator", tool_name="Bash",
                           tool_input={"command": "grep -rn needle src"})
        with mock.patch.object(guard, "guard_bash_ro",
                               side_effect=lambda i: guard.allow("investigator bash ok")) as bro:
            out = self.run_zcode(inp)
        bro.assert_called_once_with(inp)
        self.assertIn('"permissionDecision": "allow"', out)
        self.assertIn("investigator bash ok", out)

    def test_stop_gates_only_programmer_roles(self):
        inp = self.payload(agent_type="glm-programmer", hook_event_name="Stop")
        with mock.patch.object(guard, "guard_stop",
                               side_effect=lambda i: guard.deny("lane not finished")) as stop:
            out = self.run_zcode(inp)
        stop.assert_called_once_with(inp)
        self.assertIn("lane not finished", out)
        for role in ("glm-team-leader", "glm-investigator", "general-purpose"):
            inp = self.payload(agent_type=role, hook_event_name="Stop")
            with mock.patch.object(guard, "guard_stop") as stop:
                self.assertEqual(self.run_zcode(inp), "", role)
            stop.assert_not_called()
        with mock.patch.object(guard, "guard_stop") as stop:
            self.assertEqual(self.run_zcode({"hook_event_name": "Stop"}), "")
        stop.assert_not_called()

    def test_non_dict_payloads_fail_open_to_allow(self):
        for bad in ([], ["x"], "not-a-dict", 42, None):
            with mock.patch.object(guard, "guard_edit") as ge, \
                    mock.patch.object(guard, "guard_bash") as gb:
                self.assertEqual(self.run_zcode(bad), "", bad)
            ge.assert_not_called()
            gb.assert_not_called()

    def test_malformed_stdin_fails_open_through_the_cli(self):
        r = subprocess.run([sys.executable, GUARD, "zcode"], input="{not json",
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
```

The CLI test assumes the mode token reaches `guard.py` as its first argument, matching how the dispatch dict keys in `main()` are used. While writing Step 3, open `main()` and the existing `test_guard_oc.py` in the same tests directory, confirm how they spawn `guard.py` for the `oc` mode, and if the mode token is passed differently, adjust only the argument list — the assertion (exit 0 for unparsable stdin) is the contract.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_guard_zcode.py -v`
Expected: ERROR — the eight function-level tests error with `AttributeError: module 'guard' has no attribute 'guard_zcode'`; the malformed-stdin CLI test may already pass (it guards the wiring added in Step 3) or fail on the unknown mode, depending on how `main()` handles it today; the summary line reads `FAILED (errors=8)` (or `FAILED (errors=8, failures=1)`).

- [ ] **Step 3: Add the mode function and wire it into main()**

Open `glm-skills/glm-dev-team/scripts/guard.py`. The helpers `allow(reason=None)`, `deny(reason)`, `guard_edit(inp)`, `guard_bash(inp)`, `guard_edit_ro(inp)`, `guard_bash_ro(inp)`, `guard_stop(inp)` and `oc_capture(check, inp)` (the stdout-capturing trampoline `guard_oc` already runs its checks through) are consumed exactly as they are. Add the role tuple and the new mode function immediately after the existing `guard_oc` function, so the two non-`claude` mode mirrors sit together:

```python
ZCODE_READ_ONLY_ROLES = (
    "glm-code-reviewer",
    "glm-investigator",
    "glm-spot-reviewer",
    "glm-team-leader",
)


def guard_zcode(inp):
    """zcode hook mode: route on agent_type over the shared checks.

    Foreign or missing roles silently allow, so the user-level hooks never
    affect ordinary sessions - including every other glm-* agent of this
    repo's other skills, which are not dev-team lanes. Lane roles never
    defer to the ask flow (a background lane would hang on a prompt nobody
    answers): a check whose capture comes back empty - the silent allow that
    would defer to the ask flow - is made an explicit deny instead. A
    hook_event_name: Stop payload routes to the stop gate only for
    programmer roles - the Conductor's own Stop always allows. Anything
    unparsable fails open, as everywhere in this guard.
    """
    if not isinstance(inp, dict):
        return allow()
    agent = inp.get("agent_type") or inp.get("agentType") or ""
    event = inp.get("hook_event_name") or inp.get("hookEventName") or ""
    tool = inp.get("tool_name") or inp.get("toolName") or ""
    programmer = isinstance(agent, str) and agent.startswith("glm-programmer")
    read_only = isinstance(agent, str) and agent in ZCODE_READ_ONLY_ROLES
    if not programmer and not read_only:
        return allow()
    if event == "Stop":
        return guard_stop(inp) if programmer else allow()
    if tool in ("Write", "Edit"):
        check = guard_edit if programmer else guard_edit_ro
    elif tool == "Bash":
        check = guard_bash if programmer else guard_bash_ro
    else:
        return allow()
    out = oc_capture(check, inp)
    if not out.strip():
        deny("zcode lane cannot defer to the ask flow: " + tool)
    sys.stdout.write(out)
    allow()
```

Two alignment facts while you are in the file. First, `allow()` / `deny()` are not pure decision builders: they print and `sys.exit(0)`, and every check (`guard_edit`, `guard_bash`, `guard_edit_ro`, `guard_bash_ro`) ends in one of them — which is why `guard_oc` never inspects a return value and instead runs each check through `oc_capture(check, inp)` (stdout swapped, `SystemExit` swallowed, the printed decision returned as text); `guard_zcode` mirrors that exactly, and an empty capture — the silent "defer to the ask flow" allow — becomes the explicit deny above (`guard_stop` is the one exception: it is called directly, because its silent allow means the lane is genuinely finished). Second, there is no equivalent role set to reuse (`guard_oc` tests its programmer roles inline), so the tuple above is new: keep it to the four glm-dev-team read-only roles only — every other `glm-*` name (glm-doc-writer, glm-debug-worker, glm-rca-investigator, ...) belongs to another skill's ZCode session, and the user-level hooks must silently allow there.

Then wire the mode into `main()`: find the mode dispatch dict — the literal mapping mode strings to guard functions that already maps the `oc` mode (`"oc": guard_oc`) — and add this entry beside it:

```python fragment
        "zcode": guard_zcode,
```

If `main()` selects modes with if/elif arms instead of a dict, add the equivalent `zcode` arm; the dict entry above is the produced form.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_guard_zcode.py -v`
Expected: PASS — all nine `TestGuardZcode` tests report `ok`; the run ends with `OK`.

- [ ] **Step 5: Run the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: PASS — the run ends with `OK`. The guard changes are additive (one constant, one function, one dispatch entry), so every pre-existing test stays green.

- [ ] **Step 6: Commit**

```bash
git add glm-skills/glm-dev-team/scripts/guard.py glm-skills/_shared/tests/test_guard_zcode.py
git commit -m "feat: add zcode hook mode to the dev-team guard"
```

---

### T03: engine zcode core [P]

**Depends:** —

**Interfaces:**
- Uses existing: `def is_opencode() -> bool:`; `_oc_harness().harness(path)`; `def dispatch_route(st, s, mode):`
- Produces: `def is_zcode() -> bool:`; `detect_provider(root=None, st=None)`; `dispatch_route(st, s, mode)`; `glm-programmer-strong`; `model:`; `--harness`; `["claude", "opencode", "zcode"]`; `class TestDevteamZcodeCore(unittest.TestCase)`; `selftest.sh`

**Files:**
- Modify: `glm-skills/glm-dev-team/scripts/devteam.py`
- Modify: `glm-skills/glm-dev-team/scripts/selftest.sh`
- Test: `glm-skills/_shared/tests/test_devteam_zcode.py`

- [ ] **Step 1: Write the failing tests**

Create `glm-skills/_shared/tests/test_devteam_zcode.py` with exactly this content (the layout mirrors `test_devteam_oc_harness.py` in the same directory):

```python
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "glm-dev-team", "scripts")
sys.path.insert(0, SCRIPTS)

import devteam  # noqa: E402


class TestDevteamZcodeCore(unittest.TestCase):
    """zcode engine core: harness detection (env override + path detector),
    the glm provider default, strong/lite dispatch routing and the
    model-less Agent line."""

    def test_is_zcode_by_env_override(self):
        oc = devteam._oc_harness()
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "zcode"}, clear=True), \
                mock.patch.object(oc, "harness", return_value="claude"):
            self.assertTrue(devteam.is_zcode())
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "claude"}, clear=True), \
                mock.patch.object(oc, "harness", return_value="zcode"):
            self.assertFalse(devteam.is_zcode())
        with mock.patch.dict(os.environ, {"DEVTEAM_HARNESS": "opencode"}, clear=True), \
                mock.patch.object(oc, "harness", return_value="zcode"):
            self.assertFalse(devteam.is_zcode())

    def test_is_zcode_by_path_detector(self):
        oc = devteam._oc_harness()
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(oc, "harness", return_value="zcode") as h:
            self.assertTrue(devteam.is_zcode())
        h.assert_called_once_with(str(Path(devteam.__file__).resolve()))
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(oc, "harness", return_value="claude"):
            self.assertFalse(devteam.is_zcode())

    def test_detect_provider_defaults_to_glm_on_zcode(self):
        with mock.patch.object(devteam, "is_zcode", return_value=True):
            self.assertEqual(devteam.detect_provider(), "glm")
        with mock.patch.object(devteam, "is_zcode", return_value=False), \
                mock.patch.object(devteam, "is_opencode", return_value=False):
            self.assertEqual(devteam.detect_provider(), "anthropic")

    def test_strong_slices_route_to_programmer_strong_on_zcode(self):
        strong_cases = [
            {"id": "S1", "title": "risky slice", "risk": "high", "size": "small", "attempt": 1},
            {"id": "S2", "title": "large slice", "risk": "low", "size": "large", "attempt": 1},
            {"id": "S3", "title": "retry slice", "risk": "low", "size": "small", "attempt": 2},
        ]
        with mock.patch.object(devteam, "is_zcode", return_value=True):
            for s in strong_cases:
                line = devteam.dispatch_route({}, s, "zcode")
                self.assertIn("glm-programmer-strong", line, s)
                self.assertNotIn("model:", line, s)

    def test_lite_slices_route_to_programmer_lite_on_zcode(self):
        lite = {"id": "S4", "title": "easy slice", "risk": "low", "size": "small", "attempt": 1}
        with mock.patch.object(devteam, "is_zcode", return_value=True):
            line = devteam.dispatch_route({}, lite, "zcode")
        self.assertIn("glm-programmer-lite", line)
        self.assertNotIn("model:", line)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode.py -v`
Expected: ERROR — every test in the new class fails with an `AttributeError` naming `is_zcode` (`module 'devteam' has no attribute 'is_zcode'` for the two direct calls; mock's `does not have the attribute 'is_zcode'` for the three that patch it); the summary line reads `FAILED (errors=5)`.

- [ ] **Step 3: Add the zcode core to the engine**

Open `glm-skills/glm-dev-team/scripts/devteam.py` and make four edits. The consumed helpers keep their contracts: `is_opencode() -> bool` is called as `is_opencode()` (never on the detector path — see below), `_oc_harness().harness(path)` is called with the module path exactly as the existing detection helpers call it, and `def dispatch_route(st, s, mode):` keeps its signature, modified in place.

**Edit A — the detector.** Add `is_zcode` immediately after the existing `is_opencode` definition, mirroring its structure: the `DEVTEAM_HARNESS` override wins over the detector, and the detector is called exactly once on the clean path (the pass-through test asserts `assert_called_once_with`):

```python
def is_zcode() -> bool:
    """True under the zcode harness: a DEVTEAM_HARNESS=zcode override wins,
    any other DEVTEAM_HARNESS value wins against the detector, the v1
    OpenCode marker wins against the detector too, and otherwise the
    vendored harness detector decides by path/env (it returns "zcode"
    there)."""
    override = os.environ.get("DEVTEAM_HARNESS", "")
    if override:
        return override == "zcode"
    if os.environ.get("OPENCODE") == "1" and is_opencode():
        return False
    return _oc_harness().harness(str(Path(__file__).resolve())) == "zcode"
```

**Edit B — the provider default.** Search the file for `def detect_provider`. If it exists, keep its whole body and change only the fallback default: the path that yields the `anthropic` default when nothing explicit wins must yield `glm` when `is_zcode()` is true — put the `zcode` branch ahead of the existing default, and make the signature read `def detect_provider(root=None, st=None):` if the defaults are not there yet. If no such function exists, add this one directly below `is_zcode`:

```python
def detect_provider(root=None, st=None):
    """Provider for lanes: an explicit state provider wins; the default is
    glm under the zcode harness (the glm route caps lanes at 8) and
    anthropic otherwise."""
    st = st or {}
    if st.get("provider"):
        return st["provider"]
    if is_zcode():
        return "glm"
    return "anthropic"
```

**Edit C — the dispatch branch.** Find `def dispatch_route(st, s, mode):` and read its body first: it already branches per harness for the Agent line and already knows the slice-strength rule (risk high, size large, attempt ≥ 2) from the lite routing. Insert this branch at the top of the body, before the existing handling:

```python fragment
def dispatch_route(st, s, mode):
    if is_zcode():
        strong = (s.get("risk") == "high" or s.get("size") == "large"
                  or int(s.get("attempt") or 1) >= 2)
        agent = "glm-programmer-strong" if strong else "glm-programmer-lite"
        description = s.get("title") or s.get("id") or "slice"
        return "Agent(subagent_type=" + agent + ", description=" + repr(description) + ")"
    # the existing claude/opencode handling stays below, unchanged
```

Two rules are locked, the line's wording is not: strong slices route to `glm-programmer-strong`, every other slice to `glm-programmer-lite`, and the returned `Agent` line carries `subagent_type` plus the description with no `model:` segment. If the existing non-`claude` branch already has an Agent-line builder, return that builder's line with the agent chosen above instead of the literal line in the fragment. While reading the body, match the slice-dict field names the file's existing strength check reads (the fixtures use `risk` / `size` / `attempt`) and the `mode` value its callers pass; the tests pass `"zcode"` and mock `is_zcode`, so both mechanisms trigger either way.

**Edit D — the doctor choices.** Search the file for the doctor subcommand's `--harness` argument and make its choices exactly the list below, keeping every other property of the argument (default, help text) as is:

```python fragment
choices=["claude", "opencode", "zcode"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode.py -v`
Expected: PASS — all five `TestDevteamZcodeCore` tests report `ok`; the run ends with `OK`.

- [ ] **Step 5: Verify the doctor choices on the CLI**

Run: `cd glm-skills/glm-dev-team/scripts && python3 devteam.py doctor --help 2>&1 | grep -o '{claude,opencode,zcode}'`
Expected: `{claude,opencode,zcode}`

If the doctor's `--harness` lives on the main parser rather than the doctor subcommand, run the help command that reaches it — the expected text is the same.

- [ ] **Step 6: Add the zcode-dispatch checks to selftest.sh**

Append this block at the end of `glm-skills/glm-dev-team/scripts/selftest.sh`, after the last existing check. The block is linear and needs nothing from the surrounding script: it locates `devteam.py` next to itself, sets the harness override, and exercises the dispatch through the real env path.

```sh
# zcode dispatch: strong slices pick glm-programmer-strong, lite stays
# glm-programmer-lite, and the Agent line carries no model: segment.
if ! DEVTEAM_HARNESS=zcode python3 - "$(cd "$(dirname "$0")" && pwd)" <<'PY'
import sys

sys.path.insert(0, sys.argv[1])
import devteam

strong_cases = [
    {"id": "S1", "title": "risky slice", "risk": "high", "size": "small", "attempt": 1},
    {"id": "S2", "title": "large slice", "risk": "low", "size": "large", "attempt": 1},
    {"id": "S3", "title": "retry slice", "risk": "low", "size": "small", "attempt": 2},
]
lite = {"id": "S4", "title": "easy slice", "risk": "low", "size": "small", "attempt": 1}
for s in strong_cases:
    line = devteam.dispatch_route({}, s, "zcode")
    assert "glm-programmer-strong" in line, line
    assert "model:" not in line, line
line = devteam.dispatch_route({}, lite, "zcode")
assert "glm-programmer-lite" in line, line
assert "model:" not in line, line
PY
then
  echo "FAIL: zcode dispatch checks" >&2
  exit 1
fi
echo "zcode dispatch ok"
```

Run: `cd glm-skills/glm-dev-team/scripts && sh selftest.sh 2>&1 | grep -c "zcode dispatch ok"`
Expected: `1`

The selftest's own earlier checks must pass as they did before this task; the count is 1 only when the new block runs and passes (an earlier abort or a failed assertion leaves it 0).

- [ ] **Step 7: Run the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: PASS — the run ends with `OK`. The new branches only activate under `is_zcode` and `--harness` merely gains a choice, so every pre-existing test stays green; if an unexpected pre-existing test still breaks, stop and re-check that no non-`zcode` behavior changed.

- [ ] **Step 8: Commit**

```bash
git add glm-skills/glm-dev-team/scripts/devteam.py glm-skills/glm-dev-team/scripts/selftest.sh glm-skills/_shared/tests/test_devteam_zcode.py
git commit -m "feat: add zcode harness core to the dev-team engine"
```

---

### T04: doctor zcode

**Depends:** T02, T03

**Interfaces:**
- Consumes: `def is_zcode() -> bool:`; `def guard_zcode(inp):`
- Uses existing: `def agent_source(agents_src, name):`
- Produces: `def doctor_zcode(a, root):`; `doctor --harness zcode [--fix] [--flash ID] [--main ID]`; `def render_agent_zcode(agents_src, name, flash, main) -> str:`; `glm-programmer-lite`; `glm-programmer-strong`; `glm-programmer.md`; `steps: N`; `maxTurns: N`; `omitClaudeMd: true`; `injectAgentsMd: false`; `effort`; `thoughtLevel`; `Write|Edit`; `Bash`; `hooks.enabled: true`; `~/.zcode/cli/config.json`; `type: process`; `guard.py`; `.bak`; `cmd_doctor`; `cmd_start`; `class TestDevteamZcodeDoctor(unittest.TestCase)`; `~/.zcode/agents/`; `model:`; `effort:`; `hooks:`; `mode:`; `permissionMode:`; `plugins`; `.bak`; `.claude/settings.local.json`

**Files:**
- Modify: `glm-skills/glm-dev-team/scripts/devteam.py`
- Test: `glm-skills/_shared/tests/test_devteam_zcode_doctor.py`

- [ ] **Step 1: Write the failing test for the agent-frontmatter converter**

Create `glm-skills/_shared/tests/test_devteam_zcode_doctor.py` with exactly this content:

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
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
GLM = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(GLM, "glm-dev-team", "scripts")
sys.path.insert(0, SCRIPTS)


def load_devteam():
    spec = importlib.util.spec_from_file_location("devteam_zc", os.path.join(SCRIPTS, "devteam.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


dt = load_devteam()

ZCODE_AGENTS = ("glm-code-reviewer", "glm-investigator", "glm-programmer",
                "glm-programmer-lite", "glm-programmer-strong",
                "glm-spot-reviewer", "glm-team-leader")
ALLOWED_KEYS = {"name", "description", "model", "thoughtLevel", "color", "tools",
                "disallowedTools", "maxTurns", "background", "injectAgentsMd", "mcpServers"}
BAD_KEYS = ("effort:", "hooks:", "mode:", "permissionMode:", "steps:",
            "omitClaudeMd:", "variant:", "memory:", "isolation:", "temperature:")
AGENTS_SRC = os.path.join(os.path.dirname(SCRIPTS), "agents")
GUARD_CMD = "python3 " + os.path.join(SCRIPTS, "guard.py") + " zcode"


def frontmatter(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().split("\n---\n")[0]


def fm_keys(fm):
    keys = set()
    for line in fm.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or line[:1] in (" ", "\t"):
            continue
        if ":" in line:
            keys.add(line.split(":", 1)[0].strip())
    return keys


class TestDevteamZcodeDoctor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.home = os.path.join(self.tmp, "home")
        self.repo = os.path.join(self.tmp, "repo")
        for d in (self.home, self.repo):
            os.makedirs(d)
        for args in (["init", "-q"],
                     ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false",
                      "commit", "-q", "--allow-empty", "-m", "init"]):
            subprocess.run(["git"] + args, cwd=self.repo, check=True, capture_output=True)
        self.old = os.getcwd()
        os.chdir(self.repo)
        self.env = mock.patch.dict(os.environ, {"HOME": self.home})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        os.chdir(self.old)
        shutil.rmtree(self.tmp)

    def zfix(self, flash=None, main=None):
        ns = argparse.Namespace(fix=True, harness="zcode", flash=flash, main=main)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dt.doctor_zcode(ns, self.repo)
        return buf.getvalue()

    def cdoctor(self, fix=False, flash=None, main=None):
        ns = argparse.Namespace(fix=fix, harness="zcode", flash=flash, main=main)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dt.cmd_doctor(ns)
        return buf.getvalue()

    def test_render_agent_zcode_converts_frontmatter(self):
        flash, main = "acct/Flash", "acct/Main"
        cases = {
            "glm-programmer": ("model: " + flash, "thoughtLevel: high"),
            "glm-programmer-lite": ("model: " + flash, "thoughtLevel: low"),
            "glm-programmer-strong": ("model: " + main, "thoughtLevel: high"),
            "glm-code-reviewer": ("model: " + main, "thoughtLevel: high"),
            "glm-spot-reviewer": ("model: " + flash, "thoughtLevel: high"),
            "glm-investigator": ("model: " + flash, "thoughtLevel: high"),
            "glm-team-leader": ("model: " + main, "thoughtLevel: max"),
        }
        for name, (model_line, tl_line) in cases.items():
            text = dt.render_agent_zcode(AGENTS_SRC, name, flash, main)
            self.assertTrue(text.startswith("---\n"), name)
            fm, body = text.split("\n---\n", 1)
            self.assertTrue(body.strip(), name)
            self.assertIn("name: " + name, fm.splitlines(), name)
            self.assertIn(model_line, fm.splitlines(), name)
            self.assertIn(tl_line, fm.splitlines(), name)
            self.assertTrue(fm_keys(fm) <= ALLOWED_KEYS, (name, sorted(fm_keys(fm) - ALLOWED_KEYS)))
            for bad in BAD_KEYS:
                self.assertNotIn("\n" + bad, "\n" + fm, (name, bad))
            for alias in ("haiku", "sonnet", "opus"):
                self.assertNotIn("\nmodel: " + alias, "\n" + fm, (name, alias))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode_doctor.py -v`
Expected: `FAILED (errors=1)` — the traceback shows `AttributeError: module 'devteam_zc' has no attribute 'render_agent_zcode'`

- [ ] **Step 3: Implement the converter in `glm-skills/glm-dev-team/scripts/devteam.py`**

Add the block below immediately above the `if __name__ == "__main__":` line near the end of `glm-skills/glm-dev-team/scripts/devteam.py` (the functions only use `os`, `Path` — both already imported at the top of this file — and the module-level `agent_source` helper, which joins with `/` and so must be handed a `Path`, never a plain string):

```python
ZCODE_FLASH_DEFAULT = "glm-5.3-flash"
ZCODE_MAIN_DEFAULT = "glm-5.3"
_ZCODE_RENDERED_FROM = {"glm-programmer-lite": "glm-programmer",
                        "glm-programmer-strong": "glm-programmer"}
_ZCODE_EFFORT_MAP = {"low": "low", "medium": "high", "high": "high", "max": "max"}


def _zcode_fm_split(text):
    """Split an agent file into (frontmatter lines, body); ([], text) if absent."""
    lines = text.split("\n")
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    if i >= len(lines) or lines[i].strip() != "---":
        return [], text
    for j in range(i + 1, len(lines)):
        if lines[j].strip() == "---":
            return lines[i + 1:j], "\n".join(lines[j + 1:])
    return [], text


def _zcode_fm_scalar(value):
    return str(value or "").strip().strip('"').strip("'").strip()


def _zcode_fm_bool(value):
    return _zcode_fm_scalar(value).lower() in ("true", "yes", "1", "on")


def _zcode_fm_model(src_model, flash, main):
    m = _zcode_fm_scalar(src_model).lower()
    if m in ("haiku", "glm-5.3-flash"):
        return _zcode_fm_scalar(flash)
    if m in ("sonnet", "opus", "glm-5.3"):
        return _zcode_fm_scalar(main)
    if m:
        return _zcode_fm_scalar(src_model)
    return _zcode_fm_scalar(flash)


def render_agent_zcode(agents_src, name, flash, main) -> str:
    """Render the `zcode` agent markdown for `name` from the Claude-format source.

    The five dev-team agent files convert in place; `glm-programmer-lite` (model
    flash, thoughtLevel low) and `glm-programmer-strong` (model main,
    thoughtLevel high) render from `glm-programmer.md`. Mapping: `steps: N` to
    `maxTurns: N`, `omitClaudeMd: true` to `injectAgentsMd: false`, `effort` to
    `thoughtLevel`, model aliases to the real ids; effort/isolation/memory/
    omitClaudeMd/hooks/mode/temperature/steps/permissionMode/variant are
    dropped (a dropped block key swallows its indented lines too);
    name/description/color/tools/disallowedTools/background/mcpServers - and
    an existing `maxTurns`, which is how the shipped agent files pin their
    turn limit (they carry no `steps:` line) - pass through unchanged.
    """
    agents_src = Path(agents_src)  # agent_source joins with `/`: it needs a Path, callers may pass a str
    src_name = _ZCODE_RENDERED_FROM.get(name, name)
    src = agent_source(agents_src, src_name)
    if os.path.isfile(src):
        # agent_source may hand back a path instead of the text; read it either way
        with open(src, encoding="utf-8") as fh:
            src = fh.read()
    fm, body = _zcode_fm_split(src)
    out = []
    seen = set()
    skip_block = False
    for line in fm:
        if skip_block:
            if not line.strip() or line[:1] in (" ", "\t"):
                continue
            skip_block = False
        if not line.strip() or line.lstrip().startswith("#") or line[:1] in (" ", "\t"):
            out.append(line)
            continue
        key, sep, rest = line.partition(":")
        if not sep:
            out.append(line)
            continue
        key = key.strip()
        if key == "effort":
            if name == "glm-programmer-lite":
                level = "low"
            elif name == "glm-programmer-strong":
                level = "high"
            else:
                level = _ZCODE_EFFORT_MAP.get(_zcode_fm_scalar(rest).lower(), "high")
            out.append("thoughtLevel: " + level)
            seen.add("thoughtLevel")
        elif key == "steps":
            out.append("maxTurns: " + _zcode_fm_scalar(rest))
            seen.add("maxTurns")
        elif key == "omitClaudeMd":
            out.append("injectAgentsMd: " + ("false" if _zcode_fm_bool(rest) else "true"))
            seen.add("injectAgentsMd")
        elif key == "model":
            if name == "glm-programmer-lite":
                model = _zcode_fm_scalar(flash)
            elif name == "glm-programmer-strong":
                model = _zcode_fm_scalar(main)
            else:
                model = _zcode_fm_model(rest, flash, main)
            out.append("model: " + model)
            seen.add("model")
        elif key == "name":
            out.append("name: " + name)
            seen.add("name")
        elif key in ("description", "color", "tools", "disallowedTools",
                     "background", "mcpServers", "maxTurns"):
            out.append(line)
            seen.add(key)
        else:
            skip_block = True
    if "name" not in seen:
        out.append("name: " + name)
    if "model" not in seen:
        out.append("model: " + (_zcode_fm_scalar(main) if name == "glm-programmer-strong"
                                else _zcode_fm_scalar(flash)))
    if "thoughtLevel" not in seen:
        out.append("thoughtLevel: " + ("low" if name == "glm-programmer-lite" else "high"))
    return "---\n" + "\n".join(out) + "\n---\n" + body
```

- [ ] **Step 4: Run the test to verify it passes**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode_doctor.py -v`
Expected: `Ran 1 test` and the run ends with `OK`

- [ ] **Step 5: Write the failing test for the doctor's agent install**

Append this method to `class TestDevteamZcodeDoctor(unittest.TestCase)` in `glm-skills/_shared/tests/test_devteam_zcode_doctor.py`, after the last test method:

```python
    def test_fix_installs_seven_agents_with_zcode_frontmatter(self):
        out = self.zfix()
        self.assertIn("harness zcode", out)
        agents_dir = os.path.join(self.home, ".zcode", "agents")
        installed = sorted(os.listdir(agents_dir))
        self.assertEqual(installed, [name + ".md" for name in ZCODE_AGENTS])
        flash_agents = {"glm-programmer", "glm-programmer-lite",
                        "glm-spot-reviewer", "glm-investigator"}
        thought = {"glm-programmer": "high", "glm-programmer-lite": "low",
                   "glm-programmer-strong": "high", "glm-code-reviewer": "high",
                   "glm-spot-reviewer": "high", "glm-investigator": "high",
                   "glm-team-leader": "max"}
        for name in ZCODE_AGENTS:
            fm = frontmatter(os.path.join(agents_dir, name + ".md"))
            self.assertTrue(fm_keys(fm) <= ALLOWED_KEYS, (name, sorted(fm_keys(fm) - ALLOWED_KEYS)))
            self.assertNotIn("\nmodel: haiku", "\n" + fm, name)
            self.assertNotIn("\nmodel: sonnet", "\n" + fm, name)
            self.assertNotIn("\nmodel: opus", "\n" + fm, name)
            for bad in BAD_KEYS:
                self.assertNotIn("\n" + bad, "\n" + fm, (name, bad))
            model_lines = [ln for ln in fm.splitlines() if ln.startswith("model:")]
            expected = "glm-5.3-flash" if name in flash_agents else "glm-5.3"
            self.assertEqual(model_lines, ["model: " + expected], name)
            tl_lines = [ln for ln in fm.splitlines() if ln.startswith("thoughtLevel:")]
            self.assertEqual(tl_lines, ["thoughtLevel: " + thought[name]], name)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".claude", "settings.local.json")))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude", "settings.local.json")))
```

- [ ] **Step 6: Run the test to verify it fails**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode_doctor.py -v`
Expected: `FAILED (errors=1)` — the traceback shows `AttributeError: module 'devteam_zc' has no attribute 'doctor_zcode'`

- [ ] **Step 7: Implement the doctor's agent-install part**

Add the block below to `glm-skills/glm-dev-team/scripts/devteam.py`, directly under `render_agent_zcode` (same placement rule as Step 3). `guard_zcode` is the mode function the guard work added to the sibling `guard.py`, not to this engine file — the smoke check below imports it lazily (`from guard import guard_zcode` inside its own `try`, so a context without the scripts directory on `sys.path` still imports this module and only skips the check). `is_zcode()`, used in Step 23, comes from the engine task: call it directly if it landed in this file beside `is_opencode()`, or import it from wherever it landed:

```python
ZCODE_AGENTS = ("glm-programmer", "glm-programmer-lite", "glm-programmer-strong",
                "glm-code-reviewer", "glm-spot-reviewer", "glm-investigator",
                "glm-team-leader")


def _zcode_write(path, text):
    """Write a rendered agent file, creating parent directories."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def doctor_zcode(a, root):
    """Check and install the seven `zcode` agents into `~/.zcode/agents/` (user level).

    CLI: `doctor --harness zcode [--fix] [--flash ID] [--main ID]` (routed from
    `cmd_doctor`/`cmd_start`). Unlike the claude doctor, nothing is written
    under the project root: no `.claude/settings.local.json` (`root` is accepted
    only for signature parity with the other harness doctors).
    """
    fix = bool(getattr(a, "fix", False))
    flash = _zcode_fm_scalar(getattr(a, "flash", None)) or ZCODE_FLASH_DEFAULT
    main = _zcode_fm_scalar(getattr(a, "main", None)) or ZCODE_MAIN_DEFAULT
    home = os.path.expanduser("~")
    agents_dir = os.path.join(home, ".zcode", "agents")
    scripts = os.path.dirname(os.path.abspath(__file__))
    agents_src = os.path.join(os.path.dirname(scripts), "agents")
    print("harness zcode")
    missing = []
    for name in ZCODE_AGENTS:
        path = os.path.join(agents_dir, name + ".md")
        want = render_agent_zcode(agents_src, name, flash, main)
        cur = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                cur = fh.read()
        if cur == want:
            print("INSTALLED: %s" % name)
            continue
        if cur is None:
            print("MISSING: agent %s not installed" % name)
        else:
            print("STALE: agent %s does not match the rendered file" % name)
        missing.append(name)
        if fix:
            _zcode_write(path, want)
            print("installed %s" % name)
    # smoke-check the in-process guard bridge: a foreign-role PreToolUse event
    # must answer like the hook itself - by exiting, never by raising
    try:
        from guard import guard_zcode    # the sibling scripts dir is on sys.path here
        guard_zcode({"hook_event_name": "PreToolUse", "tool_name": "Read",
                     "tool_input": {}, "agent_type": "glm-outside"})
    except SystemExit:
        print("guard: zcode bridge answered a foreign-role event")
    except Exception as exc:
        print("WARN: guard bridge raised on a foreign-role event: %s" % exc)
    if missing:
        if fix:
            print("DOCTOR fixed: %d problem(s)" % len(missing))
        else:
            print("DOCTOR found: %d problem(s)" % len(missing))
            print("run `doctor --harness zcode --fix`")
    else:
        print("DOCTOR: all ZCode agents installed")
    return 0
```

- [ ] **Step 8: Run the test to verify it passes**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode_doctor.py -v`
Expected: `Ran 2 tests` and the run ends with `OK`

- [ ] **Step 9: Write the failing test for the hooks merge**

Append this method to `class TestDevteamZcodeDoctor(unittest.TestCase)` in `glm-skills/_shared/tests/test_devteam_zcode_doctor.py`, after the last test method:

```python
    def test_hooks_merge_preserves_user_config(self):
        cli = os.path.join(self.home, ".zcode", "cli")
        os.makedirs(cli, exist_ok=True)
        cfg_path = os.path.join(cli, "config.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({"plugins": {"theme": {"enabled": True}}, "model": "acct/Main"}, f)
        self.zfix()
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        self.assertEqual(cfg["plugins"], {"theme": {"enabled": True}})
        self.assertEqual(cfg["model"], "acct/Main")
        hooks = cfg.get("hooks") or {}
        self.assertIn("enabled", hooks)
        self.assertTrue(hooks["enabled"])
        self.assertEqual(hooks.get("PreToolUse"), [
            {"matcher": "Write|Edit", "hooks": [{"type": "process", "command": GUARD_CMD}]},
            {"matcher": "Bash", "hooks": [{"type": "process", "command": GUARD_CMD}]},
        ])
        self.assertEqual(hooks.get("Stop"), [{"hooks": [{"type": "process", "command": GUARD_CMD}]}])
```

- [ ] **Step 10: Run the test to verify it fails**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode_doctor.py -v`
Expected: `FAILED (failures=1)` — the traceback shows `AssertionError: 'enabled' not found in {}`

- [ ] **Step 11: Implement the user-level hooks merge**

In `glm-skills/glm-dev-team/scripts/devteam.py`, add the three helpers below directly under `_zcode_write` (they use `json` from the module's existing imports; add it to the import block if missing):

```python
def _zcode_add_hooks(cfg, hook_cmd):
    """Add the dev-team hook entries to a parsed user config dict (in place)."""
    hooks = cfg.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        cfg["hooks"] = hooks
    hooks["enabled"] = True

    def ensure(event, entry):
        entries = hooks.get(event)
        if not isinstance(entries, list):
            entries = []
            hooks[event] = entries
        for cur in entries:
            if not isinstance(cur, dict) or cur.get("matcher") != entry.get("matcher"):
                continue
            for h in cur.get("hooks") or []:
                if isinstance(h, dict) and h.get("type") == "process" \
                        and h.get("command") == hook_cmd:
                    return
        entries.append(entry)

    def process_entry(matcher=None):
        entry = {"hooks": [{"type": "process", "command": hook_cmd}]}
        if matcher is not None:
            entry["matcher"] = matcher
        return entry

    ensure("PreToolUse", process_entry("Write|Edit"))
    ensure("PreToolUse", process_entry("Bash"))
    ensure("Stop", process_entry())


def _zcode_has_entry(entries, matcher, hook_cmd):
    for cur in entries:
        if not isinstance(cur, dict) or cur.get("matcher") != matcher:
            continue
        for h in cur.get("hooks") or []:
            if isinstance(h, dict) and h.get("type") == "process" \
                    and h.get("command") == hook_cmd:
                return True
    return False


def _zcode_hooks_present(cfg_path, hook_cmd):
    """True when the enabled user config already carries all three hook entries."""
    if not os.path.exists(cfg_path):
        return False
    try:
        with open(cfg_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
    except ValueError:
        return False
    if not isinstance(cfg, dict):
        return False
    hooks = cfg.get("hooks")
    if not isinstance(hooks, dict) or not hooks.get("enabled"):
        return False
    for event, matcher in (("PreToolUse", "Write|Edit"), ("PreToolUse", "Bash"), ("Stop", None)):
        entries = hooks.get(event)
        if not isinstance(entries, list) or not _zcode_has_entry(entries, matcher, hook_cmd):
            return False
    return True


def _zcode_merge_hooks(cfg_path, hook_cmd):
    """Merge the PreToolUse/Stop hook entries into the user-level zcode config.

    Returns True (the config was rewritten); the doctor prints from that.
    """
    cfg = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding="utf-8") as fh:
            try:
                cfg = json.load(fh)
            except ValueError:
                cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    _zcode_add_hooks(cfg, hook_cmd)
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return True
```

Then replace the whole `doctor_zcode` function (added in Step 7) with the version below, which adds the hooks section and updates the docstring:

```python
def doctor_zcode(a, root):
    """Check and install the seven `zcode` agents plus the user-level hook config.

    CLI: `doctor --harness zcode [--fix] [--flash ID] [--main ID]` (routed from
    `cmd_doctor`/`cmd_start`). Agents land in `~/.zcode/agents/`; the
    PreToolUse (`Write|Edit`, `Bash`) and Stop hooks merge into
    `~/.zcode/cli/config.json` (`hooks.enabled: true`, `type: process`,
    absolute `guard.py` path). Unlike the claude doctor nothing is written
    under the project root: no `.claude/settings.local.json` (`root` exists
    only for signature parity with the other harness doctors).
    """
    fix = bool(getattr(a, "fix", False))
    flash = _zcode_fm_scalar(getattr(a, "flash", None)) or ZCODE_FLASH_DEFAULT
    main = _zcode_fm_scalar(getattr(a, "main", None)) or ZCODE_MAIN_DEFAULT
    home = os.path.expanduser("~")
    agents_dir = os.path.join(home, ".zcode", "agents")
    scripts = os.path.dirname(os.path.abspath(__file__))
    agents_src = os.path.join(os.path.dirname(scripts), "agents")
    print("harness zcode")
    missing = []
    for name in ZCODE_AGENTS:
        path = os.path.join(agents_dir, name + ".md")
        want = render_agent_zcode(agents_src, name, flash, main)
        cur = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                cur = fh.read()
        if cur == want:
            print("INSTALLED: %s" % name)
            continue
        if cur is None:
            print("MISSING: agent %s not installed" % name)
        else:
            print("STALE: agent %s does not match the rendered file" % name)
        missing.append(name)
        if fix:
            _zcode_write(path, want)
            print("installed %s" % name)
    cfg_path = os.path.join(home, ".zcode", "cli", "config.json")
    hook_cmd = "python3 " + os.path.join(scripts, "guard.py") + " zcode"
    if fix:
        # always refresh on --fix: a config that drifted (a user key added by
        # hand, a file rewritten another way) is normalized again here,
        # key-preserving, .bak kept; the merge itself is a no-op once the
        # rendered text already matches the file exactly
        if _zcode_merge_hooks(cfg_path, hook_cmd):
            print("hooks: merged PreToolUse (Write|Edit, Bash) and Stop into %s" % cfg_path)
        else:
            print("hooks: PreToolUse (Write|Edit, Bash) and Stop already configured in %s" % cfg_path)
    elif _zcode_hooks_present(cfg_path, hook_cmd):
        print("hooks: PreToolUse (Write|Edit, Bash) and Stop configured in %s" % cfg_path)
    else:
        print("MISSING: hooks not configured in %s" % cfg_path)
        missing.append("hooks")
    print("hooks: disable by setting hooks.enabled=false in %s" % cfg_path)
    # smoke-check the in-process guard bridge: a foreign-role PreToolUse event
    # must answer like the hook itself - by exiting, never by raising
    try:
        from guard import guard_zcode    # the sibling scripts dir is on sys.path here
        guard_zcode({"hook_event_name": "PreToolUse", "tool_name": "Read",
                     "tool_input": {}, "agent_type": "glm-outside"})
    except SystemExit:
        print("guard: zcode bridge answered a foreign-role event")
    except Exception as exc:
        print("WARN: guard bridge raised on a foreign-role event: %s" % exc)
    if missing:
        if fix:
            print("DOCTOR fixed: %d problem(s)" % len(missing))
        else:
            print("DOCTOR found: %d problem(s)" % len(missing))
            print("run `doctor --harness zcode --fix`")
    else:
        print("DOCTOR: all ZCode agents and hooks installed")
    return 0
```

- [ ] **Step 12: Run the test to verify it passes**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode_doctor.py -v`
Expected: `Ran 3 tests` and the run ends with `OK`

- [ ] **Step 13: Write the failing test for `.bak` on changed files**

Append this method to `class TestDevteamZcodeDoctor(unittest.TestCase)` in `glm-skills/_shared/tests/test_devteam_zcode_doctor.py`, after the last test method:

```python
    def test_changed_files_earn_bak_and_restore_content(self):
        agents_dir = os.path.join(self.home, ".zcode", "agents")
        cfg_path = os.path.join(self.home, ".zcode", "cli", "config.json")
        self.zfix()
        agent = os.path.join(agents_dir, "glm-programmer.md")
        want = dt.render_agent_zcode(AGENTS_SRC, "glm-programmer", "glm-5.3-flash", "glm-5.3")
        with open(agent, "a", encoding="utf-8") as f:
            f.write("my edit\n")
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["userKey"] = "keep me"
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        self.zfix()
        self.assertTrue(os.path.isfile(agent + ".bak"))
        with open(agent, encoding="utf-8") as f:
            self.assertEqual(f.read(), want)
        with open(agent + ".bak", encoding="utf-8") as f:
            self.assertTrue(f.read().endswith("my edit\n"))
        self.assertTrue(os.path.isfile(cfg_path + ".bak"))
        with open(cfg_path, encoding="utf-8") as f:
            self.assertEqual(json.load(f)["userKey"], "keep me")
```

- [ ] **Step 14: Run the test to verify it fails**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode_doctor.py -v`
Expected: `FAILED (failures=1)` — the traceback shows `AssertionError: False is not true`

- [ ] **Step 15: Keep a `.bak` before overwriting**

In `glm-skills/glm-dev-team/scripts/devteam.py`, replace `_zcode_write` with:

```python
def _zcode_write(path, text):
    """Write a rendered agent file; keep a `.bak` of the previous copy."""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = fh.read()
        with open(path + ".bak", "w", encoding="utf-8") as bh:
            bh.write(old)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
```

and replace `_zcode_merge_hooks` with:

```python
def _zcode_merge_hooks(cfg_path, hook_cmd):
    """Merge the hook entries into the user-level zcode config, keeping a `.bak`."""
    old_text = None
    cfg = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding="utf-8") as fh:
            old_text = fh.read()
        try:
            cfg = json.loads(old_text)
        except ValueError:
            cfg = {}
        with open(cfg_path + ".bak", "w", encoding="utf-8") as bh:
            bh.write(old_text)
    if not isinstance(cfg, dict):
        cfg = {}
    _zcode_add_hooks(cfg, hook_cmd)
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return True
```

- [ ] **Step 16: Run the test to verify it passes**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode_doctor.py -v`
Expected: `Ran 4 tests` and the run ends with `OK`

- [ ] **Step 17: Write the failing test for the idempotent re-run**

Append this method to `class TestDevteamZcodeDoctor(unittest.TestCase)` in `glm-skills/_shared/tests/test_devteam_zcode_doctor.py`, after the last test method:

```python
    def test_rerun_is_a_noop(self):
        agents_dir = os.path.join(self.home, ".zcode", "agents")
        cli_dir = os.path.join(self.home, ".zcode", "cli")
        self.zfix()
        cfg_path = os.path.join(cli_dir, "config.json")
        agent = os.path.join(agents_dir, "glm-programmer.md")
        with open(agent, encoding="utf-8") as f:
            agent_before = f.read()
        with open(cfg_path, encoding="utf-8") as f:
            cfg_before = f.read()
        self.zfix()
        with open(agent, encoding="utf-8") as f:
            self.assertEqual(f.read(), agent_before)
        with open(cfg_path, encoding="utf-8") as f:
            self.assertEqual(f.read(), cfg_before)
        baks = sorted([f for f in os.listdir(agents_dir) if f.endswith(".bak")] +
                      [f for f in os.listdir(cli_dir) if f.endswith(".bak")])
        self.assertFalse(baks, baks)
```

- [ ] **Step 18: Run the test to verify it fails**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode_doctor.py -v`
Expected: `FAILED (failures=1)` — the traceback shows `AssertionError: ['config.json.bak']`

- [ ] **Step 19: Make an identical hooks merge a no-op**

In `glm-skills/glm-dev-team/scripts/devteam.py`, replace `_zcode_merge_hooks` with the final version:

```python
def _zcode_merge_hooks(cfg_path, hook_cmd):
    """Key-preserving merge of the hook entries into the user-level zcode config.

    Existing user keys survive; a changed file is rewritten with a `.bak`
    kept, and an identical merge is a no-op.
    """
    old_text = None
    cfg = {}
    if os.path.exists(cfg_path):
        with open(cfg_path, encoding="utf-8") as fh:
            old_text = fh.read()
        try:
            cfg = json.loads(old_text)
        except ValueError:
            cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    _zcode_add_hooks(cfg, hook_cmd)
    new_text = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
    if old_text == new_text:
        return False
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    if old_text is not None:
        with open(cfg_path + ".bak", "w", encoding="utf-8") as bh:
            bh.write(old_text)
    with open(cfg_path, "w", encoding="utf-8") as fh:
        fh.write(new_text)
    return True
```

- [ ] **Step 20: Run the test to verify it passes**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode_doctor.py -v`
Expected: `Ran 5 tests` and the run ends with `OK`

- [ ] **Step 21: Write the failing test for the `cmd_doctor` routing**

Append this method to `class TestDevteamZcodeDoctor(unittest.TestCase)` in `glm-skills/_shared/tests/test_devteam_zcode_doctor.py`, after the last test method:

```python
    def test_cmd_doctor_routes_zcode(self):
        agents_dir = os.path.join(self.home, ".zcode", "agents")
        out = self.cdoctor(fix=True)
        installed = sorted(os.listdir(agents_dir)) if os.path.isdir(agents_dir) else []
        self.assertIn("glm-programmer.md", installed)
        self.assertIn("harness zcode", out)
        self.assertFalse(os.path.exists(os.path.join(self.repo, ".claude", "settings.local.json")))
        report = self.cdoctor(fix=False)
        self.assertIn("harness zcode", report)
        self.assertNotIn("MISSING:", report)
        out2 = self.cdoctor(fix=True, flash="acct/Flash", main="acct/Main")
        self.assertIn("STALE: agent glm-programmer does not match the rendered file", out2)
        self.assertIn("\nmodel: acct/Flash",
                      "\n" + frontmatter(os.path.join(agents_dir, "glm-programmer.md")))
        self.assertIn("\nmodel: acct/Main",
                      "\n" + frontmatter(os.path.join(agents_dir, "glm-team-leader.md")))
```

- [ ] **Step 22: Run the test to verify it fails**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode_doctor.py -v`
Expected: `FAILED (failures=1)` — the traceback shows `AssertionError: 'glm-programmer.md' not found in []`

- [ ] **Step 23: Route `cmd_doctor`, `cmd_start` and the parser flags**

Three anchored edits in `glm-skills/glm-dev-team/scripts/devteam.py`.

**Route `cmd_doctor`.** Find `def cmd_doctor(`. It resolves the harness value (the `--harness` argument, falling back to the detected harness) and dispatches to the harness doctors. Beside the branch that handles the opencode harness, insert:

```python fragment
if h == "zcode" or (h is None and is_zcode()):
    return doctor_zcode(a, root)
```

adapting `h` (the resolved harness value) and `root` (the project root the opencode branch passes to its doctor) to the surrounding variable names: an explicit `zcode` routes to the new doctor, and so does an unresolved harness when `is_zcode()` is true. That second arm needs the resolution above to still be able to yield `zcode`/`None` at this point: if the resolution line collapses an unset harness through an `or` chain (today's is `... or ("opencode" if is_opencode() else "claude")`) and no earlier task already added zcode to it, make `is_zcode()` part of that fallback instead (resolve to `"zcode"` when it is true, ahead of the opencode/claude defaults) — `cmd_start` calls `cmd_doctor` with no `--harness` at all, so an unset harness on a zcode machine must land here too.

**Route `cmd_start`.** Find `def cmd_start(`. Locate where it runs the doctor fix before the plan is validated (the code path that installs agents/env for the claude and opencode harnesses at the start of a run). If it funnels through `cmd_doctor` or a shared dispatch that now routes zcode, the routing already holds and no change is needed. Otherwise insert beside the existing harness branches:

```python
if getattr(a, "harness", None) == "zcode" or is_zcode():
    doctor_zcode(argparse.Namespace(fix=True, harness="zcode",
                                    flash=getattr(a, "flash", None),
                                    main=getattr(a, "main", None)), root)
```

adapting the harness/root names to the surrounding code (the `start` namespace has no `--flash`/`--main`; `getattr` supplies `None` and the doctor falls back to its defaults).

**Declare the model-id flags.** Find the argument-parser block for the `doctor` subcommand (the `sp.add_parser("doctor")` line that declares `--fix` and `--harness`). First make the `--harness` choices accept `zcode` — they are `["claude", "opencode"]` today, so add `"zcode"` unless an earlier task already did (argparse rejects a value outside the choices, and the doctor CLI above is `doctor --harness zcode ...`). Then add beside those arguments, adapting the parser variable name (`pr`):

```python
p.add_argument("--flash", default=ZCODE_FLASH_DEFAULT, metavar="ID",
               help="flash model id for the zcode doctor (default glm-5.3-flash)")
p.add_argument("--main", default=ZCODE_MAIN_DEFAULT, metavar="ID",
               help="main model id for the zcode doctor (default glm-5.3)")
```

- [ ] **Step 24: Run the test to verify it passes**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_zcode_doctor.py -v`
Expected: `Ran 6 tests` and the run ends with `OK`

- [ ] **Step 25: Run the full suite**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: the run reports no failures and ends with `OK`

- [ ] **Step 26: Commit**

```bash
git add glm-skills/glm-dev-team/scripts/devteam.py glm-skills/_shared/tests/test_devteam_zcode_doctor.py
git commit -m "feat(glm-dev-team): zcode doctor installs agents and merges user hooks"
```

---

### T05: dev-team protocol docs [P]

**Depends:** T03, T04

**Interfaces:**
- Consumes: `def is_zcode() -> bool:`; `detect_provider(root=None, st=None)`; `dispatch_route(st, s, mode)`; `glm-programmer-strong`; `model:`; `--harness`; `["claude", "opencode", "zcode"]`; `class TestDevteamZcodeCore(unittest.TestCase)`; `selftest.sh`; `def doctor_zcode(a, root):`; `doctor --harness zcode [--fix] [--flash ID] [--main ID]`; `def render_agent_zcode(agents_src, name, flash, main) -> str:`; `glm-programmer-lite`; `glm-programmer-strong`; `glm-programmer.md`; `steps: N`; `maxTurns: N`; `omitClaudeMd: true`; `injectAgentsMd: false`; `effort`; `thoughtLevel`; `Write|Edit`; `Bash`; `hooks.enabled: true`; `~/.zcode/cli/config.json`; `type: process`; `guard.py`; `.bak`; `cmd_doctor`; `cmd_start`; `class TestDevteamZcodeDoctor(unittest.TestCase)`; `~/.zcode/agents/`; `model:`; `effort:`; `hooks:`; `mode:`; `permissionMode:`; `plugins`; `.bak`; `.claude/settings.local.json`
- Produces: `subagent_type`; `run_in_background`; `devteam next [<id>]`; `SendMessage`; `TaskStop`

**Files:**
- Modify: `glm-skills/glm-dev-team/SKILL.md:54-90`
- Modify: `glm-skills/glm-dev-team/README.md:52-111`

- [ ] **Step 1: Insert the protocol section into `glm-skills/glm-dev-team/SKILL.md`**

Insert the block below (English, like the rest of the file) between the last item of the numbered list under the existing harness-phases heading (`Phases 2-4 on OpenCode`) — the item ending with `The loop cap of 2 still applies.` — and the `## Route first (one line to the user, then act)` heading:

```markdown
#### ZCode protocol

The engine detects ZCode itself (`is_zcode()`); the provider then defaults to glm (`detect_provider(root=None, st=None)`). Agents live at `~/.zcode/agents/<name>.md` (user level only, no nesting); several launched together in the foreground run in parallel. `doctor --harness zcode [--fix] [--flash ID] [--main ID]` — run automatically by `start` — installs the seven rendered agents into `~/.zcode/agents/` and merges the PreToolUse (`Write|Edit`, `Bash`) and Stop hooks into `~/.zcode/cli/config.json` (`hooks.enabled: true`, `type: process`, absolute `guard.py` path, `.bak` before rewrite, idempotent, prints how to disable; project-level hooks are ignored). `render_agent_zcode(agents_src, name, flash, main)` renders `glm-programmer-lite` (model = the `--flash ID`, `thoughtLevel: low`) and `glm-programmer-strong` (model = the `--main ID`, `thoughtLevel: high`) from `glm-programmer.md`, maps `steps: N` to `maxTurns: N`, `omitClaudeMd: true` to `injectAgentsMd: false`, `effort` to `thoughtLevel` and aliases to the real ids, and never writes `.claude/settings.local.json`. **After it installs anything, start a new session: agents and hooks load at startup.**

1. **Dispatch:** the Task-style tool takes `{description, prompt, subagent_type, run_in_background}` and has **no `model:` parameter** — never add one; omitting `subagent_type` defaults to `general-purpose`. The engine's `dispatch_route(st, s, mode)` drops the per-dispatch model and picks `glm-programmer-strong` wherever the table above says `glm-programmer` + `model: opus` (`risk: high`, `size: large`, every retried slice). `general-purpose` and `Explore` exist as built-ins.
2. **Wake-up:** a lane completion notification is the wake-up → run `devteam next` (no arguments) on every one; `devteam next [<id>]` only for a lane whose notification never arrived. No stop-hook marker dependency: the engine-side integrate re-check is the gate. Background Bash results wake you the same way (`run_in_background` and `timeout` both exist).
3. **`SendMessage` / `TaskStop` exist** and are Claude-Code-compatible: answer a `BLOCKED` question, or push the exact `REJECTED` / `NOT READY` / `MERGE ERROR` fix, with `SendMessage`; `TaskStop` a stuck lane before `devteam retry <id>`.
4. **Guards:** `guard.py` answers from the user-level config only; the event carries snake_case and camelCase fields including `agent_type` (the calling agent's name), exit 2 blocks and stdout `hookSpecificOutput.permissionDecision` = allow/ask/deny. Bridge failures fail open — the integrate re-check is the real enforcement; foreign roles are a no-op.
```

- [ ] **Step 2: Verify the section landed**

From the repo root, run:

Run: `grep -c "^#### ZCode protocol" glm-skills/glm-dev-team/SKILL.md`
Expected: `1`

- [ ] **Step 3: Insert the matching section into `glm-skills/glm-dev-team/README.md`**

Insert the block below (Vietnamese, like the rest of that file) between item 12 of the existing install list (the bullet beginning `12. **Chỉ dispatch qua engine:**`) and the `## Biến môi trường` heading:

```markdown
### ZCode

Trên ZCode, engine tự nhận harness qua `is_zcode()` và provider mặc định là glm (`detect_provider(root=None, st=None)`). Agent nằm ở `~/.zcode/agents/<tên>.md` (chỉ cấp user, không lồng nhau); nhiều agent chạy nền cùng lúc sẽ chạy song song.

1. **Cài đặt:** chạy `python3 devteam.py doctor --harness zcode --fix` (lệnh nhận `--harness` với các giá trị `["claude", "opencode", "zcode"]`, cùng `--fix`, `--flash ID`, `--main ID`; `start` tự chạy qua `cmd_start` → `cmd_doctor` → hàm `doctor_zcode(a, root)`). Lệnh cài 7 agent vào `~/.zcode/agents/`: `render_agent_zcode(agents_src, name, flash, main)` render `glm-programmer-lite` (model `--flash ID`, `thoughtLevel: low`) và `glm-programmer-strong` (model `--main ID`, `thoughtLevel: high`) từ `glm-programmer.md`, map `steps: N` → `maxTurns: N`, `omitClaudeMd: true` → `injectAgentsMd: false`, `effort` → `thoughtLevel`, alias → id thật; bỏ `effort:` / `hooks:` / `mode:` / `permissionMode:` và mọi key Claude không dùng. Không bao giờ ghi `.claude/settings.local.json`.
2. **Hook:** PreToolUse (`Write|Edit`, `Bash`) và Stop được merge vào `~/.zcode/cli/config.json` với `hooks.enabled: true`, `type: process`, đường dẫn `guard.py` tuyệt đối; merge giữ nguyên mọi key khác của user (ví dụ `plugins`), ghi `.bak` trước khi ghi lại và chạy lại là no-op. Hook cấp project bị bỏ qua. **Sau khi cài bất cứ thứ gì phải mở session mới** — agent và hook chỉ được nạp lúc khởi động.
3. **Dispatch:** tool kiểu Task nhận `{description, prompt, subagent_type, run_in_background}` và không có tham số `model:`. `dispatch_route(st, s, mode)` tự bỏ model và chọn `glm-programmer-strong` cho `risk: high`, `size: large` và mọi slice phải retry (thay cho `glm-programmer` + `model: opus` của Claude). Bỏ `subagent_type` thì mặc định `general-purpose`; `general-purpose` và `Explore` là built-in.
4. **Đánh thức:** thông báo hoàn tất của lane là tín hiệu đánh thức → chạy `devteam next` không tham số; `devteam next [<id>]` chỉ dành cho lane mà thông báo không bao giờ đến. Không phụ thuộc marker của stop hook — integrate re-check phía engine mới là cổng kiểm tra. Kết quả Bash nền đánh thức như Claude Code (`run_in_background` và `timeout` đều có).
5. **Tin nhắn:** `SendMessage` và `TaskStop` tồn tại, tương thích Claude Code. Trả lời câu hỏi `BLOCKED`, hoặc đẩy đúng cách sửa `REJECTED` / `NOT READY` / `MERGE ERROR`, qua `SendMessage`; `TaskStop` lane bị treo trước khi `devteam retry <id>`.
6. **Guard:** `guard.py` chạy từ config cấp user; sự kiện mang trường snake_case + camelCase, gồm cả `agent_type` (tên agent đang gọi); exit 2 chặn, stdout `hookSpecificOutput.permissionDecision` = allow/ask/deny. Lỗi phía cầu nối thì cho qua (fail-open) — integrate re-check phía engine mới là tầng đảm bảo thật; role lạ là no-op.
```

- [ ] **Step 4: Verify the section landed**

From the repo root, run:

Run: `grep -c "^### ZCode" glm-skills/glm-dev-team/README.md`
Expected: `1`

- [ ] **Step 5: Record the new test coverage in the README's tested section**

In the `## Đã kiểm thử` section of `glm-skills/glm-dev-team/README.md`, insert the bullet below immediately before the `- **Mutation test**:` bullet:

```markdown
- Phần ZCode được kiểm thử bằng `class TestDevteamZcodeCore` (engine/guard chế độ zcode: dispatch bỏ model, chọn strong, provider mặc định glm; guard định tuyến, fail-open, no-op với role lạ) và `class TestDevteamZcodeDoctor` (doctor: cài 7 agent vào `~/.zcode/agents/`, merge hook giữ nguyên key user, re-run no-op, `.bak` khi file đổi, không ghi `.claude/settings.local.json`), tách khỏi `bash scripts/selftest.sh`.
```

- [ ] **Step 6: Add the feature's history entry to the README**

In the `## Lịch sử ngắn` section of `glm-skills/glm-dev-team/README.md`, insert the bullet below immediately above the existing `- **OpenCode hardening (2026-09-28)**` bullet:

```markdown
- **ZCode hardening (2026-10-06)** — thêm chế độ harness `zcode`: `is_zcode()` tự nhận, provider mặc định glm; `doctor --harness zcode [--fix] [--flash ID] [--main ID]` cài 7 agent render đúng frontmatter ZCode vào `~/.zcode/agents/` và merge hook PreToolUse/Stop vào `~/.zcode/cli/config.json` (giữ key user, `.bak`, chạy lại là no-op); dispatch bỏ model và chọn strong.
```

- [ ] **Step 7: Verify the history entry landed**

From the repo root, run:

Run: `grep -c "ZCode hardening" glm-skills/glm-dev-team/README.md`
Expected: `1`

- [ ] **Step 8: Verify the tested-section entry landed**

From the repo root, run:

Run: `grep -c "TestDevteamZcodeDoctor" glm-skills/glm-dev-team/README.md`
Expected: `1`

- [ ] **Step 9: Run the full suite**

From the `glm-skills/` directory, run:

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: the run reports no failures and ends with `OK`

- [ ] **Step 10: Commit**

From the repository root (the parent of `glm-skills/`), so the paths match the Files list:

```bash
git add glm-skills/glm-dev-team/SKILL.md glm-skills/glm-dev-team/README.md
git commit -m "docs(glm-dev-team): document the zcode protocol in SKILL.md and README"
```

---

### T06: installer conversion and delegation [P]

**Depends:** T03, T04

**Interfaces:**
- Consumes: `def doctor_zcode(a, root):`; `doctor --harness zcode [--fix] [--flash ID] [--main ID]`; `def render_agent_zcode(agents_src, name, flash, main) -> str:`; `glm-programmer-lite`; `glm-programmer-strong`; `glm-programmer.md`; `steps: N`; `maxTurns: N`; `omitClaudeMd: true`; `injectAgentsMd: false`; `effort`; `thoughtLevel`; `Write|Edit`; `Bash`; `hooks.enabled: true`; `~/.zcode/cli/config.json`; `type: process`; `guard.py`; `.bak`; `cmd_doctor`; `cmd_start`; `class TestDevteamZcodeDoctor(unittest.TestCase)`; `~/.zcode/agents/`; `model:`; `effort:`; `hooks:`; `mode:`; `permissionMode:`; `plugins`; `.bak`; `.claude/settings.local.json`
- Produces: `convert()`; `steps: N`; `maxTurns: N`; `omitClaudeMd: true`; `injectAgentsMd: false`; `permissionMode`; `background`; `devteam.py doctor --harness zcode --fix`; `--flash/--main`; `glm-debug-worker.md`; `thoughtLevel: low`; `InstallZcodeTests`; `steps:`; `omitClaudeMd:`

**Files:**
- Modify: `glm-skills/install-zcode.sh`
- Test: `glm-skills/_shared/tests/test_install_zcode.py`

- [ ] **Step 1: Write the failing tests for the frontmatter mapping and the debug worker level**

Both edits go into `glm-skills/_shared/tests/test_install_zcode.py`. Run every `Run:` command in this task from the `glm-skills/` folder.

First, extend the import block at the top of the file with `shutil`:

```python
import os
import shutil
import subprocess
import tempfile
import unittest
```

Second, add these two methods inside `InstallZcodeTests`, after `test_dry_run_writes_nothing`. The fixture agent rides the `glm-doc-generator` agents glob, which the installer already converts, so the end-to-end run exercises the real `convert()` on a temp copy of the tree:

```python fragment
    def test_convert_maps_steps_and_omitclaudemd_end_to_end(self):
        copy_root = os.path.join(self.home, "tree")
        shutil.copytree(GLM_ROOT, copy_root,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        agents_src = os.path.join(copy_root, "glm-doc-generator", "agents", "zcode")
        os.makedirs(agents_src, exist_ok=True)
        with open(os.path.join(agents_src, "glm-fixture-agent.md"), "w", encoding="utf-8") as fh:
            fh.write(
                "---\n"
                "name: glm-fixture-agent\n"
                "description: Fixture agent for the frontmatter mapping.\n"
                "model: glm-5.3-flash\n"
                "effort: high\n"
                "steps: 12\n"
                "omitClaudeMd: true\n"
                "permissionMode: acceptEdits\n"
                "background: true\n"
                "---\n"
                "Fixture body.\n"
            )
        r = subprocess.run(["sh", os.path.join(copy_root, "install-zcode.sh"), "--home", self.home],
                           capture_output=True, text=True, timeout=180)
        self.assertEqual(r.returncode, 0, r.stderr)
        fm = frontmatter(self.agent("glm-fixture-agent"))
        self.assertIn("maxTurns: 12", fm)
        self.assertIn("injectAgentsMd: false", fm)
        self.assertIn("background: true", fm)
        self.assertIn("thoughtLevel: high", fm)
        self.assertNotIn("steps:", fm)
        self.assertNotIn("omitClaudeMd:", fm)
        self.assertNotIn("permissionMode:", fm)
        self.assertNotIn("effort:", fm)

    def test_debug_worker_gains_thoughtlevel_low(self):
        self.assertEqual(self.install().returncode, 0)
        self.assertIn("thoughtLevel: low", frontmatter(self.agent("glm-debug-worker")))
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 _shared/tests/test_install_zcode.py InstallZcodeTests.test_convert_maps_steps_and_omitclaudemd_end_to_end InstallZcodeTests.test_debug_worker_gains_thoughtlevel_low -v`
Expected: FAIL — the mapping test fails with `AssertionError: 'maxTurns: 12' not found` (today `convert()` drops `steps:` outright and keeps `permissionMode:`), and the debug-worker test fails with `AssertionError: 'thoughtLevel: low' not found`.

- [ ] **Step 3: Implement the mapping and the level fallback in `convert()`**

Two edits to `glm-skills/install-zcode.sh`.

Replace the whole `convert()` function — the one introduced by the comment `# convert SRC DEST: rewrite one agent file to ZCode frontmatter (real GLM ids, thoughtLevel, no Claude/OpenCode-only keys).` — with:

```sh fragment
# convert SRC DEST [LEVEL]: rewrite one agent file to ZCode frontmatter (real GLM ids, thoughtLevel,
# steps: N -> maxTurns: N and omitClaudeMd: true -> injectAgentsMd: false instead of dropping them,
# drop permissionMode and the other Claude/OpenCode-only keys, keep background; LEVEL is a thoughtLevel
# applied only when the source has neither thoughtLevel nor effort).
convert() {
    if [ "$DRY" -eq 1 ]; then echo "[dry-run] agent $1 -> $2"; return 0; fi
    python3 - "$1" "$2" "$FLASH" "$MAIN" "${3:-}" <<'PY' || { echo "could not install agent $2" >&2; exit 1; }
import os, re, shutil, sys
src, dest, flash, main, level = sys.argv[1:6]
DROP = {"effort", "isolation", "memory", "hooks", "mode", "temperature", "permission", "permissionMode", "variant"}
text = open(src, encoding="utf-8").read()
m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
if not m:
    sys.exit("no frontmatter in " + src)
blocks, cur = [], None  # (key, lines): a key starts at column 0, its continuation lines are indented or blank
for line in m.group(1).split("\n"):
    k = re.match(r"([A-Za-z][\w-]*):(.*)", line)
    if k:
        cur = [k.group(1), [line]]
        blocks.append(cur)
    elif cur:
        cur[1].append(line)
out, effort, has_level = [], None, False
for key, lines in blocks:
    val = lines[0].split(":", 1)[1].strip().strip("\"'")
    if key == "effort":
        effort = val
    if key == "thoughtLevel":
        has_level = True
    if key in DROP:
        continue
    if key == "steps":
        out.append("maxTurns: " + val)
        continue
    if key == "omitClaudeMd":
        out.append("injectAgentsMd: " + ("false" if val == "true" else "true"))
        continue
    if key == "model":
        val = {"haiku": flash, "sonnet": main, "opus": main, "glm-5.3-flash": flash, "glm-5.3": main}.get(val, val)
        lines = ["model: " + val]
    out.extend(lines)
if not has_level:
    if effort:
        out.append("thoughtLevel: " + effort)
    elif level:
        out.append("thoughtLevel: " + level)
new = "---\n" + "\n".join(out) + "\n---\n" + m.group(2)
if os.path.exists(dest):
    if open(dest, encoding="utf-8").read() == new:
        print("  %s (unchanged)" % os.path.basename(dest))
        sys.exit(0)
    if os.path.abspath(src) != os.path.abspath(dest):
        shutil.copy2(dest, dest + ".bak")
    print("  %s (updated%s)" % (os.path.basename(dest), "" if os.path.abspath(src) == os.path.abspath(dest) else "; previous copy kept as %s.bak" % os.path.basename(dest)))
else:
    print("  " + os.path.basename(dest))
with open(dest, "w", encoding="utf-8") as fh:
    fh.write(new)
PY
}
```

Then restructure the agents loop so the debug worker passes `low` as its level (keep the `glm-dev-team` glob for now — Step 7 replaces it with the delegation). Replace the block that currently reads:

```sh fragment
for f in "$SCRIPT_DIR"/glm-requirements-code-audit/agents/zcode/*.md "$SCRIPT_DIR"/glm-doc-generator/agents/zcode/*.md \
         "$SCRIPT_DIR"/glm-systematic-debugging/agents/glm-debug-worker.md "$SCRIPT_DIR"/glm-dev-team/agents/*.md; do
    [ -f "$f" ] && convert "$f" "$AGENTS_DIR/$(basename "$f")"
done
```

with:

```sh fragment
for f in "$SCRIPT_DIR"/glm-requirements-code-audit/agents/zcode/*.md "$SCRIPT_DIR"/glm-doc-generator/agents/zcode/*.md \
         "$SCRIPT_DIR"/glm-dev-team/agents/*.md; do
    [ -f "$f" ] && convert "$f" "$AGENTS_DIR/$(basename "$f")"
done
# glm-debug-worker is a mechanical worker; it never pays for max thinking.
[ -f "$SCRIPT_DIR/glm-systematic-debugging/agents/glm-debug-worker.md" ] && \
    convert "$SCRIPT_DIR/glm-systematic-debugging/agents/glm-debug-worker.md" "$AGENTS_DIR/glm-debug-worker.md" low
```

- [ ] **Step 4: Run the two tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 _shared/tests/test_install_zcode.py InstallZcodeTests.test_convert_maps_steps_and_omitclaudemd_end_to_end InstallZcodeTests.test_debug_worker_gains_thoughtlevel_low -v`
Expected: PASS — Ran 2 tests, ends with OK.

- [ ] **Step 5: Write the failing tests for the doctor delegation and the closing message**

Both edits go into `glm-skills/_shared/tests/test_install_zcode.py`.

Extend the `AGENTS` list — it currently reads:

```python
AGENTS = ["glm-code-reviewer", "glm-debug-worker", "glm-doc-reviewer", "glm-doc-writer", "glm-investigator", "glm-plan-task-writer",
          "glm-programmer", "glm-rca-investigator", "glm-rca-verifier", "glm-spot-reviewer", "glm-team-leader"]
```

and becomes:

```python
AGENTS = ["glm-code-reviewer", "glm-debug-worker", "glm-doc-reviewer", "glm-doc-writer", "glm-investigator", "glm-plan-task-writer",
          "glm-programmer", "glm-programmer-lite", "glm-programmer-strong", "glm-rca-investigator", "glm-rca-verifier",
          "glm-spot-reviewer", "glm-team-leader"]
```

Then add these two methods inside `InstallZcodeTests`, after `test_debug_worker_gains_thoughtlevel_low`:

```python fragment
    def test_devteam_doctor_installs_programmer_lite_and_strong(self):
        r = self.install("--flash", "acct/Flash", "--main", "acct/Main")
        self.assertEqual(r.returncode, 0, r.stderr)
        for name in ("glm-programmer-lite", "glm-programmer-strong"):
            fm = frontmatter(self.agent(name))
            for key in ("effort:", "hooks:", "isolation:", "memory:", "mode:", "temperature:"):
                self.assertNotIn("\n" + key, "\n" + fm, (name, key))
            self.assertIn("\nmodel: ", "\n" + fm, name)
            self.assertIn("\nthoughtLevel: ", "\n" + fm, name)

    def test_closing_message_claims(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("ZCode does not have", r.stdout)
        self.assertNotIn("Restart ZCode", r.stdout)
        self.assertIn("NEW ZCode session", r.stdout)
        self.assertIn("devteam.py doctor --harness zcode", r.stdout)
        self.assertIn("~/.zcode/cli/config.json", r.stdout)
        self.assertIn("truncated when loaded", r.stdout)
```

- [ ] **Step 6: Run them to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 _shared/tests/test_install_zcode.py InstallZcodeTests.test_agents_use_zcode_frontmatter InstallZcodeTests.test_devteam_doctor_installs_programmer_lite_and_strong InstallZcodeTests.test_closing_message_claims -v`
Expected: FAIL — `test_agents_use_zcode_frontmatter` and `test_devteam_doctor_installs_programmer_lite_and_strong` both error with `FileNotFoundError` on `glm-programmer-lite.md` (nothing installs it yet), and `test_closing_message_claims` fails with `AssertionError: 'ZCode does not have' unexpectedly found` (the closing message still claims `ZCode` has no hooks).

- [ ] **Step 7: Delegate the dev-team agents to the engine doctor and correct the closing message**

Two boundaries hold while making these edits. The delegation only shells out to the engine's doctor subcommand — its CLI is `doctor --harness zcode [--fix] [--flash ID] [--main ID]`, routed by `cmd_doctor` in `devteam.py` to `def doctor_zcode(a, root):`; the engine's other subcommands (`cmd_start` and the rest) are untouched. And nothing moves into the installer: key discovery stays in the engine (env vars first, then files such as `.claude/settings.local.json`), and the doctor's own write behavior — an unchanged re-run is a no-op, a changed file keeps a `.bak`, and every user key already in `~/.zcode/cli/config.json` (a `plugins` block, providers, anything else the user put there) survives the merge — is pinned by `class TestDevteamZcodeDoctor(unittest.TestCase)` in the engine test file, not re-tested here.

Five edits to `glm-skills/install-zcode.sh`.

**Edit 1 — the header comment (lines 6-8).** Replace:

```sh fragment
#   agents  <skill>/agents/zcode/*.md, glm-systematic-debugging's glm-debug-worker and glm-dev-team's agents
#           ->  <home>/.zcode/agents/   (rewritten to ZCode frontmatter; a changed file is kept as <name>.md.bak first)
#           plus glm-plan-task-writer, written by plan_tool.py setup --harness zcode --apply
```

with:

```sh fragment
#   agents  <skill>/agents/zcode/*.md and glm-systematic-debugging's glm-debug-worker
#           ->  <home>/.zcode/agents/   (rewritten to ZCode frontmatter; a changed file is kept as <name>.md.bak first)
#           glm-dev-team's seven ZCode agents (five file agents plus rendered glm-programmer-lite and
#           glm-programmer-strong) via devteam.py doctor --harness zcode --fix, which also merges the
#           guard hooks into ~/.zcode/cli/config.json; plus glm-plan-task-writer, written by
#           plan_tool.py setup --harness zcode --apply
```

**Edit 2 — the skill-check comment above the validation heredoc (line 40).** Replace:

```sh fragment
# ZCode silently drops a skill whose description is over 1024 characters or whose body is over 100KB.
```

with:

```sh fragment
# ZCode drops a skill whose description is over 1024 characters; a body over 100KB is truncated when loaded.
```

**Edit 3 — the agents loop.** Replace:

```sh fragment
for f in "$SCRIPT_DIR"/glm-requirements-code-audit/agents/zcode/*.md "$SCRIPT_DIR"/glm-doc-generator/agents/zcode/*.md \
         "$SCRIPT_DIR"/glm-dev-team/agents/*.md; do
    [ -f "$f" ] && convert "$f" "$AGENTS_DIR/$(basename "$f")"
done
```

with:

```sh fragment
for f in "$SCRIPT_DIR"/glm-requirements-code-audit/agents/zcode/*.md "$SCRIPT_DIR"/glm-doc-generator/agents/zcode/*.md; do
    [ -f "$f" ] && convert "$f" "$AGENTS_DIR/$(basename "$f")"
done
```

**Edit 4 — the delegation, next to the plan-tool delegation.** Replace:

```sh fragment
if [ "$DRY" -eq 1 ]; then
    echo "[dry-run] glm-plan-task-writer via plan_tool.py setup --harness zcode --apply"
else
    HOME="$HOME_DIR" python3 "$SKILLS_DIR/glm-writing-plans/scripts/plan_tool.py" setup --harness zcode --apply >/dev/null
    convert "$AGENTS_DIR/glm-plan-task-writer.md" "$AGENTS_DIR/glm-plan-task-writer.md"
fi
```

with:

```sh fragment
if [ "$DRY" -eq 1 ]; then
    echo "[dry-run] glm-plan-task-writer via plan_tool.py setup --harness zcode --apply"
    echo "[dry-run] glm-dev-team zcode agents via devteam.py doctor --harness zcode --fix --flash $FLASH --main $MAIN"
else
    HOME="$HOME_DIR" python3 "$SKILLS_DIR/glm-writing-plans/scripts/plan_tool.py" setup --harness zcode --apply >/dev/null
    convert "$AGENTS_DIR/glm-plan-task-writer.md" "$AGENTS_DIR/glm-plan-task-writer.md"
    # The seven glm-dev-team ZCode agents are delegated to the engine's doctor subcommand (cmd_doctor
    # in devteam.py routes to def doctor_zcode(a, root):), same pattern as the plan_tool.py setup
    # delegation above: the doctor converts the five file agents (glm-team-leader, glm-code-reviewer,
    # glm-investigator, glm-spot-reviewer, glm-programmer.md), renders glm-programmer-lite and
    # glm-programmer-strong via def render_agent_zcode(agents_src, name, flash, main) -> str:,
    # installs all seven into ~/.zcode/agents/, and merges the guard hooks into
    # ~/.zcode/cli/config.json. --flash/--main pass through, so a custom plan id reaches the agents.
    HOME="$HOME_DIR" python3 "$SKILLS_DIR/glm-dev-team/scripts/devteam.py" doctor --harness zcode --fix --flash "$FLASH" --main "$MAIN" >/dev/null
fi
```

**Edit 5 — the closing message.** Replace the whole `cat <<MSG ... MSG` block, which currently reads:

```sh fragment
cat <<MSG

Done. Restart ZCode, then invoke a skill with \$glm-brainstorming, \$glm-dev-team, \$glm-doc-generator, \$glm-git-diff-summary or
\$glm-idea-to-spec, \$glm-requirements-code-audit, \$glm-systematic-debugging, \$glm-writing-plans.
Next: export ZAI_API_KEY (GLM Coding Plan key) and check it with
  python3 $SKILLS_DIR/glm-writing-plans/scripts/plan_tool.py doctor --ping
The Z.ai plan allows 8 concurrent API calls: the skills cap their fan-out at 8 (default width 6).
glm-dev-team needs hook-based guards that ZCode does not have, so its footprint and frozen-test rules are prompt-enforced only.
MSG
```

with:

```sh fragment
cat <<MSG

Done. Start a NEW ZCode session to load the installed skills and agents (a restart is not enough), then invoke a skill with \$glm-brainstorming, \$glm-dev-team, \$glm-doc-generator, \$glm-git-diff-summary or
\$glm-idea-to-spec, \$glm-requirements-code-audit, \$glm-systematic-debugging, \$glm-writing-plans.
Next: export ZAI_API_KEY (GLM Coding Plan key) and check it with
  python3 $SKILLS_DIR/glm-writing-plans/scripts/plan_tool.py doctor --ping
The Z.ai plan allows 8 concurrent API calls: the skills cap their fan-out at 8 (default width 6).
glm-dev-team guards (frozen tests, footprint) are ZCode hooks on Write|Edit and Bash tool events.
The install above already ran
  python3 $SKILLS_DIR/glm-dev-team/scripts/devteam.py doctor --harness zcode --fix
which installs the seven glm-dev-team agents into ~/.zcode/agents/ and merges the guard hooks
(type: process, hooks.enabled: true, commands pointing at the installed skill's guard.py) into
~/.zcode/cli/config.json — a key-preserving merge: .bak before rewrite, a re-run is a no-op, and
every user key already in the file survives.
A frontmatter description over 1024 characters makes ZCode drop the whole skill; a body over 100KB is truncated when loaded, not dropped.
MSG
```

- [ ] **Step 8: Run the three tests to verify they pass**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 _shared/tests/test_install_zcode.py InstallZcodeTests.test_agents_use_zcode_frontmatter InstallZcodeTests.test_devteam_doctor_installs_programmer_lite_and_strong InstallZcodeTests.test_closing_message_claims -v`
Expected: PASS — Ran 3 tests, ends with OK.

- [ ] **Step 9: Run the whole installer test file**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 _shared/tests/test_install_zcode.py -v`
Expected: PASS — Ran 9 tests, ends with OK.

- [ ] **Step 10: Run the full `_shared` suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK — the run ends with the OK status line, 0 failures, 0 errors.

- [ ] **Step 11: Commit**

From the repository root (the parent of `glm-skills/`), so the paths match the Files list:

```bash
git add glm-skills/install-zcode.sh glm-skills/_shared/tests/test_install_zcode.py
git commit -m "fix(install-zcode): map steps/omitClaudeMd, delegate dev-team agents to the doctor"
```

---

### T07: brainstorming zcode surface [P]

**Depends:** —

**Interfaces:**
- Produces: `context.sh`; `oc_harness.py`; `~/.zcode/skills/glm-brainstorming`; `TodoWrite`; `glm-tuning.md`

**Files:**
- Modify: `glm-skills/glm-brainstorming/SKILL.md`
- Modify: `glm-skills/glm-brainstorming/glm-tuning.md`
- Modify: `glm-skills/glm-brainstorming/fanout-playbook.md`
- Modify: `glm-skills/glm-brainstorming/architectural.md:122-124`
- Modify: `glm-skills/glm-brainstorming/visual-companion.md:76-87`
- Modify: `glm-skills/glm-brainstorming/scripts/context.sh`
- Modify: `glm-skills/glm-brainstorming/CHANGELOG.md`
- Test: `glm-skills/_shared/tests/test_brainstorm_oc.py`

- [ ] **Step 1: Write the failing `context.sh` zcode-branch tests**

Append this block to `glm-skills/_shared/tests/test_brainstorm_oc.py` — before the trailing `if __name__ == "__main__":` block when the file ends with one, otherwise at the very end. The block carries its own imports; duplicates of imports the file already has are harmless. Run every `Run:` command in this task from the `glm-skills/` folder.

```python
import os
import shutil
import subprocess
import tempfile
import unittest


class ZcodeSurfaceTests(unittest.TestCase):
    """The zcode surface: the context.sh harness branch and the harness-scoped skill docs."""

    SKILL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "glm-brainstorming")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = self._tmp.name

    def read(self, *parts):
        with open(os.path.join(self.SKILL, *parts), encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    @staticmethod
    def prose_lines(text):
        out, fence = [], False
        for line in text.splitlines():
            if line.lstrip().startswith("```"):
                fence = not fence
            elif not fence:
                out.append(line)
        return out

    def run_context(self, rel_scripts, env_extra=None):
        scripts = os.path.join(self.home, rel_scripts)
        os.makedirs(scripts)
        shutil.copy(os.path.join(self.SKILL, "scripts", "context.sh"),
                    os.path.join(scripts, "context.sh"))
        env = {"HOME": self.home, "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
        env.update(env_extra or {})
        return subprocess.run(["sh", os.path.join(scripts, "context.sh")],
                              capture_output=True, text=True, timeout=60, env=env)

    def test_context_sh_detects_zcode_with_width_cap_8(self):
        r = self.run_context(".zcode/skills/glm-brainstorming/scripts")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("harness: zcode", r.stdout)
        self.assertIn("caps: lanes=6 (default 6, hard max 8)", r.stdout)
        self.assertNotIn("subagents=", r.stdout)
        self.assertNotIn("workflow=", r.stdout)

    def test_context_sh_claude_code_caps_still_printed(self):
        r = self.run_context("plain/scripts", {"CLAUDECODE": "1"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("harness: claude-code", r.stdout)
        self.assertIn("subagents=8", r.stdout)
        self.assertIn("workflow=8", r.stdout)
```

- [ ] **Step 2: Run the zcode-detection test to verify it fails**

Run: `cd _shared/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_brainstorm_oc.ZcodeSurfaceTests.test_context_sh_detects_zcode_with_width_cap_8 -v`
Expected: FAIL — `AssertionError: 'harness: zcode' not found` (an install under `~/.zcode/skills/` reports `harness: unknown` today).

- [ ] **Step 3: Add the zcode branch to `context.sh` harness detection**

Three edits to `glm-skills/glm-brainstorming/scripts/context.sh`.

**Edit 1 — the detection chain.** Replace the block that currently reads:

```sh fragment
if [ -n "$CLAUDECODE" ] || [ -n "$CLAUDE_CODE_ENTRYPOINT" ] || [ -n "$CLAUDE_SKILL_DIR" ]; then
  harness=claude-code
elif [ -n "$OPENCODE_TERMINAL" ] || [ -n "$OPENCODE" ] || [ -n "$OPENCODE_BIN" ] || [ -f "$skill_dir/.oc-major" ]; then harness=opencode
elif case "$skill_dir" in */opencode/*|*/.opencode/*) true ;; *) false ;; esac; then harness=opencode
elif [ -n "$CODEX_CI" ] || [ -n "$CODEX_HOME" ]; then harness=codex
```

with:

```sh fragment
if [ -n "$CLAUDECODE" ] || [ -n "$CLAUDE_CODE_ENTRYPOINT" ] || [ -n "$CLAUDE_SKILL_DIR" ]; then
  harness=claude-code
elif [ -n "$OPENCODE_TERMINAL" ] || [ -n "$OPENCODE" ] || [ -n "$OPENCODE_BIN" ] || [ -f "$skill_dir/.oc-major" ]; then harness=opencode
elif case "$skill_dir" in */opencode/*|*/.opencode/*) true ;; *) false ;; esac; then harness=opencode
elif case "$skill_dir" in */.zcode/*) true ;; *) false ;; esac; then harness=zcode
elif [ -n "$CODEX_CI" ] || [ -n "$CODEX_HOME" ]; then harness=codex
```

**Edit 2 — keep zcode sticky against the `oc_harness.py` override.** Replace:

```sh fragment
set -- $oc_line
if [ "$harness" != claude-code ] && [ "${1:-}" = opencode ]; then
```

with:

```sh fragment
set -- $oc_line
if [ "$harness" != claude-code ] && [ "$harness" != zcode ] && [ "${1:-}" = opencode ]; then
```

**Edit 3 — the caps line: no `CLAUDE_CODE_*` caps on zcode, width capped at 8.** Replace:

```sh fragment
if [ "$harness" = opencode ]; then
  echo "caps: lanes=$(c8 "${OC_MAX_LANES:-6}" 6) (set OC_MAX_LANES or pass oc_harness run --width N; default 6, hard max 8) oc_major=$oc_major"
else
  echo "caps: subagents=$(c8 "${CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS:-8}") workflow=$(c8 "${CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS:-8}") compact_window=${CLAUDE_CODE_AUTO_COMPACT_WINDOW:-default}"
fi
```

with:

```sh fragment
if [ "$harness" = opencode ]; then
  echo "caps: lanes=$(c8 "${OC_MAX_LANES:-6}" 6) (set OC_MAX_LANES or pass oc_harness run --width N; default 6, hard max 8) oc_major=$oc_major"
elif [ "$harness" = zcode ]; then
  echo "caps: lanes=$(c8 "${OC_MAX_LANES:-6}" 6) (default 6, hard max 8)"
else
  echo "caps: subagents=$(c8 "${CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS:-8}") workflow=$(c8 "${CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS:-8}") compact_window=${CLAUDE_CODE_AUTO_COMPACT_WINDOW:-default}"
fi
```

- [ ] **Step 4: Run both context tests to verify they pass**

Run: `cd _shared/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_brainstorm_oc.ZcodeSurfaceTests.test_context_sh_detects_zcode_with_width_cap_8 test_brainstorm_oc.ZcodeSurfaceTests.test_context_sh_claude_code_caps_still_printed -v`
Expected: PASS — Ran 2 tests, ends with OK.

- [ ] **Step 5: Write the failing doc-surface tests**

Add these six methods inside `ZcodeSurfaceTests` in `glm-skills/_shared/tests/test_brainstorm_oc.py`, after `test_context_sh_claude_code_caps_still_printed`:

```python fragment
    def test_skill_md_zcode_surface(self):
        text = self.read("SKILL.md")
        lines = self.prose_lines(text)
        self.assertIn("~/.zcode/skills/glm-brainstorming", self.flat(text))
        self.assertTrue(any("TaskCreate" in ln and "TodoWrite" in ln for ln in lines),
                        "the TaskCreate fallback row must name TodoWrite")
        self.assertTrue(any("AskUserQuestion" in ln and "ZCode" in ln for ln in lines),
                        "the AskUserQuestion fallback must cover ZCode (no question tool documented)")
        self.assertTrue(any("Workflow" in ln and "Claude Code" in ln for ln in lines),
                        "Workflow facts must be scoped to Claude Code")
        for ln in lines:
            if "CLAUDE_CODE_" in ln:
                self.assertIn("Claude Code", ln, ln)
            if "todowrite" in ln or "webfetch" in ln:
                self.assertIn("OpenCode", ln, ln)

    def test_fanout_playbook_scopes_claude_code_facts_and_covers_zcode(self):
        text = self.read("fanout-playbook.md")
        for ln in self.prose_lines(text):
            if "CLAUDE_CODE_" in ln or "Workflow" in ln:
                self.assertIn("Claude Code", ln, ln)
        self.assertIn("On ZCode no continue tool is documented", self.flat(text))

    def test_architectural_taskstop_note_covers_zcode(self):
        self.assertIn("On ZCode no stop tool is documented", self.flat(self.read("architectural.md")))

    def test_visual_companion_platform_notes_gain_zcode(self):
        self.assertIn("ZCode — no ZCode-specific server behavior is documented",
                      self.flat(self.read("visual-companion.md")))

    def test_glm_tuning_gains_zcode_runtime_section(self):
        flat = self.flat(self.read("glm-tuning.md"))
        self.assertIn("ZCode runtime", flat)
        self.assertIn("NEW ZCode session", flat)
        self.assertIn("no `!` preload support", flat)

    def test_changelog_records_the_zcode_surface(self):
        text = self.read("CHANGELOG.md")
        self.assertIn("9.4 (from 9.3)", text)
        self.assertLess(text.find("9.4 (from 9.3)"), text.find("9.3 (from 9.2)"))
```

- [ ] **Step 6: Run the class to verify the doc tests fail**

Run: `cd _shared/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_brainstorm_oc.ZcodeSurfaceTests -v`
Expected: FAIL — the two `test_context_sh_*` tests pass; the six doc tests fail on their pinned strings, starting with `test_architectural_taskstop_note_covers_zcode`: `AssertionError: 'On ZCode no stop tool is documented' not found`.

- [ ] **Step 7: Make the doc changes**

**a. `glm-skills/glm-brainstorming/SKILL.md`** — not inlined here; locate each spot by its anchor and keep the file's own wording style. Five changes:

1. The bootstrap scripts-dir loop: `SKILL.md` documents one ordered candidate loop for resolving its scripts dir — the loop whose candidate roots are the Base directory, `$OPENCODE_CONFIG_DIR/skills`, `.opencode/skills`, `~/.config/opencode/skills`, `.agents`, `~/.agents`, `.claude`, `~/.claude`, `.zcode`, and which exits with a clear message on a miss. Add the full candidate `~/.zcode/skills/glm-brainstorming` to the end of that list, right after the existing project-relative `.zcode/skills/glm-brainstorming` candidate (today the loop's only zcode candidate; every other root in the loop already carries both a project-relative and a home-absolute candidate, and a `ZCode` install lives under `~/.zcode/skills/`, which none of today's candidates can reach).
2. The harness fallback table's `TaskCreate` row: the substitute becomes `TodoWrite`, and the `todowrite` tool-name map stays labeled `OpenCode`. The row reads, in the table's own column shape:

```markdown
| TaskCreate missing | use TodoWrite for the checklist write; on OpenCode the tool name is `todowrite` |
```

3. The same table's `AskUserQuestion` row must not assume a question tool anywhere. The row reads, in the table's own column shape:

```markdown
| AskUserQuestion missing (or on ZCode, where no question tool is documented) | ask in plain text: numbered questions in chat, approval ask as item 1 |
```

4. Scope the harness-specific facts: every prose line that mentions a `CLAUDE_CODE_*` env var or the `Workflow` runtime says `Claude Code`; every prose line that names an `OpenCode` tool-name map (`todowrite`, `webfetch`, `task` for a lane) says `OpenCode`. Label only — nothing is deleted.
5. If `SKILL.md` itself carries a `SendMessage` or `TaskStop` note, extend it the same way the notes below are extended: state that no such tool is documented for `ZCode`, then give the fallback (for `SendMessage`: re-dispatch a fresh Flash lane with the partial output pasted in; for `TaskStop`: let the lane finish and ignore its output).

**b. `glm-skills/glm-brainstorming/fanout-playbook.md`** — five edits.

Edit 1 — scope the two cap bullets (§0). Replace:

```markdown
- Subagents: 8 running at once (the provider's concurrent-call limit). The 9th `Agent` call fails
  with "Concurrent subagent limit reached" and tells you not to retry.
  Never raise `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` above 8.
- Workflow runtime: keep `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS` at 8
  (fewer on fewer CPUs). Needs explicit user opt-in. It never beats the
  subagent cap, so prefer plain subagents.
```

with:

```markdown
- Subagents: 8 running at once (the provider's concurrent-call limit). The 9th `Agent` call fails
  with "Concurrent subagent limit reached" and tells you not to retry.
  Never raise Claude Code's `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS` above 8.
- Claude Code `Workflow` runtime: keep `CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS` at 8
  (fewer on fewer CPUs). Needs explicit user opt-in. It never beats the
  subagent cap, so prefer plain subagents.
```

Edit 2 — scope the `Workflow` mention in the subagents bullet (§0). Replace:

```markdown
- Subagents run in the background in interactive sessions; results arrive
  as completion notifications. They have WebSearch/WebFetch but not
  AskUserQuestion or Workflow. They may nest three levels — do not. Flat
  fan-outs keep merging and cost under your control.
```

with:

```markdown
- Subagents run in the background in interactive sessions; results arrive
  as completion notifications. They have WebSearch/WebFetch but not
  AskUserQuestion or Claude Code's `Workflow`. They may nest three levels — do not. Flat
  fan-outs keep merging and cost under your control.
```

Edit 3 — the waves bullet (§3). Replace:

```markdown
- **Lanes over the cap → waves.** Dispatch the highest-value lanes first
  (the ones that can change the approach set), then refill in batches as
  completions arrive. Each wake-up costs a main-model turn, so never
  refill one at a time. Use `Workflow` instead only when the workflow cap
  exceeds the subagent cap and the user explicitly opted in.
```

with:

```markdown
- **Lanes over the cap → waves.** Dispatch the highest-value lanes first
  (the ones that can change the approach set), then refill in batches as
  completions arrive. Each wake-up costs a main-model turn, so never
  refill one at a time. Use Claude Code's `Workflow` instead only when the workflow cap
  exceeds the subagent cap and the user explicitly opted in.
```

Edit 4 — the pattern bullet (§3). Replace:

```markdown
- **Workflow pattern** (opt-in only; load the `workflow-authoring` skill
  first if available — it is the authoritative script reference):
```

with:

```markdown
- **Claude Code `Workflow` pattern** (opt-in only; load the `workflow-authoring` skill
  first if available — it is the authoritative script reference):
```

Edit 5 — the `SendMessage` note (§4). Replace:

```markdown
- Lane stopped at its turn limit with partial output → continue it with
  `SendMessage`, which keeps its context, instead of spawning a fresh one.
```

with:

```markdown
- Lane stopped at its turn limit with partial output → continue it with
  `SendMessage`, which keeps its context, instead of spawning a fresh one.
  On ZCode no continue tool is documented: re-dispatch a fresh Flash lane
  with the partial output pasted in and the remaining budget stated.
```

**c. `glm-skills/glm-brainstorming/architectural.md`** — one edit (lines 122-124). Replace:

```markdown
1. If a pre-draft lane is still running, stop it (TaskStop) and write the
   spec yourself. OpenCode has no TaskStop and no pre-draft lane: skip
   straight to the move below. Otherwise move the draft to
```

with:

```markdown
1. If a pre-draft lane is still running, stop it (TaskStop) and write the
   spec yourself. OpenCode has no TaskStop and no pre-draft lane: skip
   straight to the move below. On ZCode no stop tool is documented: let the
   lane finish, ignore its output, and write the spec yourself. Otherwise
   move the draft to
```

**d. `glm-skills/glm-brainstorming/visual-companion.md`** — one edit (the platform notes paragraph, lines 76-87). Replace the paragraph tail that currently reads:

```markdown
OpenCode v2 — add `--foreground` and run it through `shell` with
`background: true` (a foreground shell call is killed after 120 s, which
takes the server with it); read `server-info` next turn. OpenCode v1 —
run as above (the script backgrounds itself). Any harness that
reaps detached processes → `--foreground` + its background mechanism.
Unreachable URL in containers → `--host 0.0.0.0 --url-host localhost`.
```

with the same paragraph plus a `ZCode` entry, inserted between the `OpenCode v1` sentence and the `Any harness` sentence:

```markdown
OpenCode v2 — add `--foreground` and run it through `shell` with
`background: true` (a foreground shell call is killed after 120 s, which
takes the server with it); read `server-info` next turn. OpenCode v1 —
run as above (the script backgrounds itself). ZCode — no ZCode-specific
server behavior is documented: run as above (the script backgrounds
itself), and if the harness reaps detached processes, switch to
`--foreground` plus its background mechanism and read `server-info`
next turn. Any harness that
reaps detached processes → `--foreground` + its background mechanism.
Unreachable URL in containers → `--host 0.0.0.0 --url-host localhost`.
```

**e. `glm-skills/glm-brainstorming/glm-tuning.md`** — append this section at the end of the file (after the §6 paragraph that ends the file today):

```markdown

## 7. ZCode runtime

Install all eight skills with `sh install-zcode.sh` (add `--home DIR` to target another home); it
copies each `glm-<name>/` folder to `~/.zcode/skills/glm-<name>/` and rewrites the bundled agents to
`~/.zcode/agents/` with real model ids and `thoughtLevel` — ZCode has no `haiku`/`sonnet` aliases, so
use the real ids `glm-5.3` / `glm-5.3-flash`. Installed skills and agents load only in a NEW ZCode
session, not on a restart. Invoke the skill with `$glm-brainstorming`; there is no `!` preload
support. Per-turn trigger metadata is the skill name plus a description excerpt of up to 250
characters, and a description over 1024 characters makes ZCode drop the skill — which is why the
WHEN clause sits at the front of this skill's description. Agents launched together run in parallel
and cannot spawn nested subagents, so keep the fan-out flat: width cap 8, default 6 (Live context
prints `harness: zcode` with the lane cap in force). Lane economics (R2) are unchanged: every lane
Flash, at most 2 GLM-5.3 lanes.
```

**f. `glm-skills/glm-brainstorming/CHANGELOG.md`** — prepend this entry at the very top of the file, above the current `# 9.3 (from 9.2) — OpenCode v1/v2 hardening` heading:

```markdown
# 9.4 (from 9.3) — ZCode surface

- context.sh: new zcode branch in harness detection (skill dir under `*/.zcode/*`); the zcode caps
  line prints the lane width (default 6, hard max 8) with no CLAUDE_CODE_* caps line, and the
  oc_harness.py opencode override no longer wins once zcode is detected.
- SKILL.md: the bootstrap scripts-dir loop gains the `~/.zcode/skills/glm-brainstorming` candidate;
  the TaskCreate fallback row names `TodoWrite`; the OpenCode tool-name maps (`task`, `todowrite`,
  `webfetch`) and the Claude Code env/`Workflow` facts are scoped to their harnesses; the
  AskUserQuestion fallback no longer assumes a question tool (none is documented for ZCode).
- fanout-playbook.md: Claude Code env/`Workflow` facts scoped to their harness; the `SendMessage`
  note covers ZCode.
- architectural.md: the `TaskStop` note covers ZCode.
- visual-companion.md: platform notes gain a ZCode entry.
- glm-tuning.md: new ZCode runtime section (§7).
```

- [ ] **Step 8: Run the class to verify everything passes**

Run: `cd _shared/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_brainstorm_oc.ZcodeSurfaceTests -v`
Expected: PASS — Ran 8 tests, ends with OK.

- [ ] **Step 9: Run the full `_shared` suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK — the run ends with the OK status line, 0 failures, 0 errors.

- [ ] **Step 10: Commit**

From the repository root (the parent of `glm-skills/`), so the paths match the Files list:

```bash
git add glm-skills/glm-brainstorming/SKILL.md glm-skills/glm-brainstorming/glm-tuning.md glm-skills/glm-brainstorming/fanout-playbook.md glm-skills/glm-brainstorming/architectural.md glm-skills/glm-brainstorming/visual-companion.md glm-skills/glm-brainstorming/scripts/context.sh glm-skills/glm-brainstorming/CHANGELOG.md glm-skills/_shared/tests/test_brainstorm_oc.py
git commit -m "feat(glm-brainstorming): zcode surface (context.sh branch, scoped harness facts)"
```

---

### T08: idea-to-spec trigger front-load [P]

**Depends:** —

**Interfaces:**
- Produces: `description`

**Files:**
- Modify: `glm-skills/glm-idea-to-spec/SKILL.md`

- [ ] **Step 1: Run the description check to verify it fails**

The check parses the `description` frontmatter the way the repo-level installer does — fold continuation lines into single spaces, strip the folded-block head — then demands the WHEN clause inside the first sentence and a total under 1024 characters. Run every `Run:` command in this task from the `glm-skills/` folder.

```bash
python3 - <<'PY'
import re
text = open("glm-idea-to-spec/SKILL.md", encoding="utf-8").read()
m = re.match(r"---\n(.*?)\n---\n", text, re.S)
fm = m.group(1)
d = re.search(r"^description:[ \t]*(.*?)(?=^\S|\Z)", fm, re.S | re.M)
desc = " ".join(l.strip() for l in d.group(1).splitlines())
head, _, rest = desc.partition(" ")
if head in (">-", ">", "|-", "|"):
    desc = rest
assert len(desc) <= 1024, "description is %d chars" % len(desc)
first = desc.split(". ", 1)[0] + "."
assert "WHENEVER" in first, "no WHEN clause up front"
assert len(first) <= 250, "WHEN clause is %d chars" % len(first)
print("description ok: %d chars, WHEN clause %d chars" % (len(desc), len(first)))
PY
```

Run: the bash block above, from the `glm-skills/` folder.
Expected: FAIL — `AssertionError: no WHEN clause up front` (the WHEN sentence currently sits at the end of the description, past character 500, far outside the first 250 characters that per-turn trigger metadata shows).

- [ ] **Step 2: Front-load the WHEN clause in the description**

`glm-skills/glm-idea-to-spec/SKILL.md` line 3 currently reads:

```markdown
description: Turns a raw software idea (app, SaaS, web tool, AI agent, bot, extension, marketplace, game) into a complete, build-ready markdown spec whose purpose is to make money. Researches the latest market, competitor, pricing, tech and legal data on the web with cited sources; interviews the user in rounds to deepen the idea; gives a blunt, evidence-based verdict on whether the idea can earn money and how to make it succeed; then writes a PRD/technical spec detailed enough for any AI coding agent or developer to build without guessing. Use this skill WHENEVER the user describes a product or software idea, says "I have an idea", asks to write a PRD, spec, product doc or build plan, asks whether an idea is good, viable or profitable, wants market or competitor analysis for an app, or wants to plan a software business — even if they never say "document" or "spec".
```

Replace that line with:

```markdown
description: Use this skill WHENEVER the user describes a product or software idea, says "I have an idea", asks to write a PRD, spec, product doc or build plan, or asks whether an idea is good, viable or profitable. Trigger the same way when they want market or competitor analysis for an app, or want to plan a software business — even if they never say "document" or "spec". Turns a raw software idea (app, SaaS, web tool, AI agent, bot, extension, marketplace, game) into a complete, build-ready markdown spec whose purpose is to make money. Researches the latest market, competitor, pricing, tech and legal data on the web with cited sources; interviews the user in rounds to deepen the idea; gives a blunt, evidence-based verdict on whether the idea can earn money and how to make it succeed; then writes a PRD/technical spec detailed enough for any AI coding agent or developer to build without guessing.
```

The WHEN sentence (202 characters) now opens the description, so the 250-character per-turn excerpt carries the trigger; the total stays 897 characters, under the 1024-character drop line.

- [ ] **Step 3: Run the description check to verify it passes**

Run: the bash block from Step 1, from the `glm-skills/` folder.
Expected: PASS — prints `description ok: 897 chars, WHEN clause 202 chars`.

- [ ] **Step 4: Run the Phase-2 question-line check to verify it fails**

```bash
python3 - <<'PY'
text = open("glm-idea-to-spec/SKILL.md", encoding="utf-8").read()
lines = [ln for ln in text.splitlines() if "Ask 3" in ln and "questions per round" in ln]
assert len(lines) == 1, "expected exactly one Phase-2 round line, found %d" % len(lines)
ln = lines[0]
assert "plain-text" in ln, "Phase-2 line must offer a plain-text fallback"
assert "never assume a question tool" in ln, "Phase-2 line must not assume a question tool"
assert "AskUserQuestion" in ln, "Phase-2 line keeps the AskUserQuestion path"
print("phase-2 question line ok")
PY
```

Run: the bash block above, from the `glm-skills/` folder.
Expected: FAIL — `AssertionError: Phase-2 line must offer a plain-text fallback` (the line today assumes an `AskUserQuestion` tool exists in every harness).

- [ ] **Step 5: Add the plain-text fallback to the Phase-2 line**

The Phase-2 round line (`glm-skills/glm-idea-to-spec/SKILL.md` line 56) currently reads:

```markdown
- Ask 3–4 questions per round (AskUserQuestion supports up to 4 questions with multiple-choice options; there is always a free-text "Other").
```

Replace it with:

```markdown
- Ask 3–4 questions per round: via AskUserQuestion where the harness has a question tool, otherwise as plain-text numbered questions in chat answered by number or free text — never assume a question tool is present.
```

- [ ] **Step 6: Run the Phase-2 check to verify it passes**

Run: the bash block from Step 4, from the `glm-skills/` folder.
Expected: PASS — prints `phase-2 question line ok`.

- [ ] **Step 7: Run the full `_shared` suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK — the run ends with the OK status line, 0 failures, 0 errors.

- [ ] **Step 8: Commit**

From the repository root (the parent of `glm-skills/`), so the path matches the Files list:

```bash
git add glm-skills/glm-idea-to-spec/SKILL.md
git commit -m "fix(glm-idea-to-spec): front-load the WHEN clause, plain-text question fallback"
```

---

### T09: requirements-code-audit zcode surface [P]

**Depends:** —

**Interfaces:**
- Produces: `description`; `~/.zcode/skills/<name>`; `A=`; `tools: Read, Grep, Glob, Write`; `subagent_type=`; `setup --harness zcode`; `opencode/`; `SETUP.md`

**Files:**
- Modify: `glm-skills/glm-requirements-code-audit/SKILL.md`
- Modify: `glm-skills/glm-requirements-code-audit/agents/zcode/glm-rca-investigator.md:6-6`
- Modify: `glm-skills/glm-requirements-code-audit/agents/zcode/glm-rca-verifier.md:6-6`
- Modify: `glm-skills/glm-requirements-code-audit/scripts/audit.py`
- Modify: `glm-skills/glm-requirements-code-audit/SETUP.md:39-41`
- Modify: `glm-skills/glm-requirements-code-audit/references/glm-tuning.md:29-31`
- Test: `glm-skills/_shared/tests/test_adopt_audit.py`

- [ ] **Step 1: Write the failing SKILL.md surface tests**

Two edits to `glm-skills/_shared/tests/test_adopt_audit.py` (run every `Run:` command in this task from the `glm-skills/` folder).

Extend the import block at the top of the file with `re` (after `import os`):

```python
import re
```

Append this class at the end of the file:

```python
class ZcodeDocSurface(unittest.TestCase):
    SKILL_DIR = os.path.normpath(os.path.join(SCRIPTS, ".."))
    SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")
    TUNING = os.path.join(SKILL_DIR, "references", "glm-tuning.md")
    SETUP_MD = os.path.join(SKILL_DIR, "SETUP.md")

    def read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    @classmethod
    def folded_description(cls):
        with open(cls.SKILL_MD, encoding="utf-8") as fh:
            text = fh.read()
        m = re.match(r"---\n(.*?)\n---\n", text, re.S)
        d = re.search(r"^description:[ \t]*(.*?)(?=^\S|\Z)", m.group(1), re.S | re.M)
        desc = " ".join(l.strip() for l in d.group(1).splitlines())
        head, _, rest = desc.partition(" ")
        if head in (">-", ">", "|-", "|"):
            desc = rest
        return desc

    def test_description_when_clause_sits_up_front_under_1024(self):
        desc = self.folded_description()
        self.assertLessEqual(len(desc), 1024, "description is %d chars" % len(desc))
        first = desc.split(". ", 1)[0] + "."
        self.assertTrue(first.startswith("Use whenever"), "WHEN clause is not up front")
        self.assertLessEqual(len(first), 250, "WHEN clause is %d chars" % len(first))

    def test_skill_md_has_the_bootstrap_path_loop_with_zcode(self):
        flat = self.flat(self.read(self.SKILL_MD))
        self.assertIn("A=", flat)
        self.assertIn("$OPENCODE_CONFIG_DIR/skills/glm-requirements-code-audit", flat)
        self.assertIn("~/.zcode/skills/glm-requirements-code-audit", flat)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `cd _shared/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_adopt_audit.ZcodeDocSurface.test_description_when_clause_sits_up_front_under_1024 test_adopt_audit.ZcodeDocSurface.test_skill_md_has_the_bootstrap_path_loop_with_zcode -v`
Expected: FAIL — the description test fails with `AssertionError: WHEN clause is not up front`, and the bootstrap test fails with `AssertionError: 'A=' not found`.

- [ ] **Step 3: Front-load the description and add the bootstrap path loop to SKILL.md**

Two edits to `glm-skills/glm-requirements-code-audit/SKILL.md`.

First, the description block (lines 3-12). Replace:

```markdown
description: >-
  Audit whether a codebase implements a requirements/spec document and produce a traceability report plus a
  prioritized fix plan. The requirements file is the only source of truth (no git history, no README/docs).
  A bundled script does the retrieval and fans out up to 8 parallel GLM requests, then an adversarial second
  pass, then scripted merging and reporting. Use whenever the user wants to verify, audit, cross-check or trace
  an implementation against a spec, PRD, SRS, user stories or requirements list: "does the code match the
  requirements", "find gaps between spec and code", "requirement traceability", "conformance/compliance check",
  "what is missing vs the spec and how do I fix it", "compare my doc to my code", or Vietnamese requests like
  "kiểm tra code có đúng tài liệu yêu cầu không", "đối chiếu spec với code", "code còn thiếu gì so với yêu cầu".
  Trigger even when the user does not say "audit".
```

with:

```markdown
description: >-
  Use whenever the user wants to verify, audit, cross-check or trace an implementation against a spec, PRD,
  SRS, user stories or requirements list — even when the user does not say "audit". Audit whether a codebase
  implements a requirements/spec document and produce a traceability report plus a prioritized fix plan. The
  requirements file is the only source of truth (no git history, no README/docs). A bundled script does the
  retrieval and fans out up to 8 parallel GLM requests, then an adversarial second pass, then scripted
  merging and reporting. Trigger phrases: "does the code match the requirements", "find gaps between spec
  and code", "requirement traceability", "conformance/compliance check", "what is missing vs the spec and
  how do I fix it", "compare my doc to my code", or Vietnamese requests like "kiểm tra code có đúng tài liệu
  yêu cầu không", "đối chiếu spec với code", "code còn thiếu gì so với yêu cầu".
```

The folded description is 920 characters (under the 1024-character drop line) and its first sentence — the WHEN clause — is 187 characters, inside the 250-character per-turn excerpt.

Second, the `A=` bootstrap (lines 25-27). Replace:

```markdown
Write `A` for `python3 SKILL_DIR/scripts/audit.py`, where `SKILL_DIR` is the directory holding this file
(`python` instead of `python3` on Windows). Every command prints a `NEXT:` line — follow it and do not
deliberate about plumbing.
```

with:

```markdown
Write `A` for the audit script, pinned as your first call of the run:
`A=python3 <dir>/scripts/audit.py` for the first `<dir>` that has `scripts/audit.py`, trying in order the
directory holding this file, `$OPENCODE_CONFIG_DIR/skills/glm-requirements-code-audit`,
`.opencode/skills/glm-requirements-code-audit`, `~/.config/opencode/skills/glm-requirements-code-audit`,
`.agents/skills/glm-requirements-code-audit`, `~/.agents/skills/glm-requirements-code-audit`,
`.claude/skills/glm-requirements-code-audit`, `~/.claude/skills/glm-requirements-code-audit`,
`~/.zcode/skills/glm-requirements-code-audit` (`python` instead of `python3` on Windows). No candidate
exists → say so and ask for the install dir; never guess a path. Every command prints a `NEXT:` line —
follow it and do not deliberate about plumbing.
```

- [ ] **Step 4: Run the two tests to verify they pass**

Run: `cd _shared/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_adopt_audit.ZcodeDocSurface.test_description_when_clause_sits_up_front_under_1024 test_adopt_audit.ZcodeDocSurface.test_skill_md_has_the_bootstrap_path_loop_with_zcode -v`
Expected: PASS — Ran 2 tests, ends with OK.

- [ ] **Step 5: Write the failing agent-surface and setup tests**

Append this class at the end of `glm-skills/_shared/tests/test_adopt_audit.py`:

```python
class ZcodeAuditBehavior(unittest.TestCase):
    SKILL_DIR = os.path.normpath(os.path.join(SCRIPTS, ".."))

    @staticmethod
    def flat(text):
        return " ".join(text.split())

    def test_zcode_agents_use_camelcase_tool_names(self):
        agents = os.path.join(self.SKILL_DIR, "agents", "zcode")
        for name in ("glm-rca-investigator.md", "glm-rca-verifier.md"):
            with open(os.path.join(agents, name), encoding="utf-8") as fh:
                fm = fh.read().split("\n---\n")[0]
            self.assertIn("tools: Read, Grep, Glob, Write", fm, name)
            self.assertNotIn("tools: read, grep, glob, write", fm, name)

    def test_zcode_dispatch_line_names_agents_with_real_ids(self):
        with open(os.path.join(SCRIPTS, "audit.py"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("ZCode: dispatch each worker as agent glm-rca-investigator", self.flat(text))
        self.assertNotIn("subagent_type", text)

    def test_setup_zcode_strips_opencode_and_setup_md_from_the_copy(self):
        home = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, home, True)
        buf = io.StringIO()
        with mock.patch.dict(os.environ, clean_env(HOME=home), clear=True), redirect_stdout(buf):
            audit.main(["setup", "--harness", "zcode"])
        skill = os.path.join(home, ".zcode", "skills", "glm-requirements-code-audit")
        self.assertTrue(os.path.isfile(os.path.join(skill, "SKILL.md")))
        self.assertTrue(os.path.isfile(os.path.join(skill, "scripts", "audit.py")))
        self.assertFalse(os.path.exists(os.path.join(skill, "opencode")))
        self.assertFalse(os.path.exists(os.path.join(skill, "SETUP.md")))
        self.assertTrue(os.path.isfile(os.path.join(home, ".zcode", "agents", "glm-rca-investigator.md")))
        self.assertTrue(os.path.isfile(os.path.join(home, ".zcode", "agents", "glm-rca-verifier.md")))
```

- [ ] **Step 6: Run them to verify they fail**

Run: `cd _shared/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_adopt_audit.ZcodeAuditBehavior -v`
Expected: FAIL — `test_zcode_agents_use_camelcase_tool_names` fails with `AssertionError: 'tools: Read, Grep, Glob, Write' not found`, `test_zcode_dispatch_line_names_agents_with_real_ids` fails with `AssertionError: 'ZCode: dispatch each worker as agent glm-rca-investigator' not found`, and `test_setup_zcode_strips_opencode_and_setup_md_from_the_copy` fails with `AssertionError: True is not false` (the copied tree still contains `opencode/`).

- [ ] **Step 7: CamelCase the tools, fix the dispatch line, strip the zcode copy**

Three edits.

**The two `agents/zcode/*.md` files — the `tools` values (line 6 of each).** In `glm-skills/glm-requirements-code-audit/agents/zcode/glm-rca-investigator.md`, the frontmatter block around it reads:

```markdown
model: glm-5.3-flash
thoughtLevel: high
tools: read, grep, glob, write
maxTurns: 30
```

and becomes:

```markdown
model: glm-5.3-flash
thoughtLevel: high
tools: Read, Grep, Glob, Write
maxTurns: 30
```

In `glm-skills/glm-requirements-code-audit/agents/zcode/glm-rca-verifier.md`, the same block reads:

```markdown
model: glm-5.3
thoughtLevel: high
tools: read, grep, glob, write
maxTurns: 25
```

and becomes:

```markdown
model: glm-5.3
thoughtLevel: high
tools: Read, Grep, Glob, Write
maxTurns: 25
```

**The zcode dispatch lines in `glm-skills/glm-requirements-code-audit/scripts/audit.py`.** Two lines in the agent-lane dispatch code. In `_dispatch`, the non-OpenCode return line — the file's only `subagent_type=` occurrence, printed once per batch file by `_print_dispatch` — drops the jargon but keeps the payload: the line must still name the agent and the batch file, e.g. `agent %s — prompt: read %s and follow it exactly`. Then the wave-level ZCode hint — the `ZCode: subagents launched together run in parallel.` line `_print_dispatch` prints above the per-batch lines — is replaced with this sentence, kept as one string:

```python fragment
ZCODE_DISPATCH = "ZCode: dispatch each worker as agent glm-rca-investigator (judge batches) or glm-rca-verifier (verify batches), all in one message — agents launched together run in parallel; use real model ids only (glm-5.3-flash / glm-5.3)."
```

The constant name is not what matters — the sentence is; inline it or keep it as a module constant the way the surrounding code organizes its hint strings. The per-batch lines must keep naming each batch file path: that path is the only thing that tells the dispatcher what prompt to give each worker, so dropping it breaks the agent lane. Then remove every other `subagent_type` occurrence in the file: that parameter belongs to neither harness this skill supports, so any survivor is stale jargon.

**The zcode branch of `setup` in `audit.py`.** The zcode branch is the code behind `setup --harness zcode`, which copies the skill folder to `~/.zcode/skills/glm-requirements-code-audit/` and `agents/zcode/*.md` to `~/.zcode/agents/`. Exclude the `opencode/` directory and the `SETUP.md` file from the copied skill tree — with `shutil.copytree` that is `ignore=shutil.ignore_patterns("opencode", "SETUP.md")`, with a hand-rolled copy loop, skip those two names. Everything else (`SKILL.md`, `scripts/`, `references/`, `agents/`) keeps copying, and the agent copies are unchanged. If the dry-run zcode output asserted by `test_zcode_output_is_unchanged` lists the copied files and now fails, update that assertion to the new output — the copied-file list is the only thing that may change.

- [ ] **Step 8: Run the three tests to verify they pass**

Run: `cd _shared/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_adopt_audit.ZcodeAuditBehavior -v`
Expected: PASS — Ran 3 tests, ends with OK.

- [ ] **Step 9: Write the failing doc-correction tests**

Add these three methods inside `ZcodeDocSurface` in `glm-skills/_shared/tests/test_adopt_audit.py`, after `test_skill_md_has_the_bootstrap_path_loop_with_zcode`:

```python fragment
    def test_glm_tuning_char_count_matches_the_new_description(self):
        desc = self.folded_description()
        tuning = self.flat(self.read(self.TUNING))
        self.assertIn("description measured at %d chars" % len(desc), tuning)
        self.assertNotIn("description measured at 911 chars", tuning)

    def test_setup_md_key_paths_include_the_v2_credentials_file(self):
        self.assertIn("credentials.json", self.flat(self.read(self.SETUP_MD)))

    def test_glm_tuning_admits_user_level_zcode_hooks(self):
        tuning = self.flat(self.read(self.TUNING))
        self.assertNotIn("no Claude Code hook system", tuning)
        self.assertIn("user-level hooks", tuning)
        self.assertIn("~/.zcode/cli/config.json", tuning)
```

- [ ] **Step 10: Run them to verify they fail**

Run: `cd _shared/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_adopt_audit.ZcodeDocSurface.test_glm_tuning_char_count_matches_the_new_description test_adopt_audit.ZcodeDocSurface.test_setup_md_key_paths_include_the_v2_credentials_file test_adopt_audit.ZcodeDocSurface.test_glm_tuning_admits_user_level_zcode_hooks -v`
Expected: FAIL — the count test fails with `AssertionError: 'description measured at 920 chars' not found`, the key-paths test fails with `AssertionError: 'credentials.json' not found`, and the hooks test fails with `AssertionError: 'no Claude Code hook system' unexpectedly found`.

- [ ] **Step 11: Correct the stale claims in SETUP.md and glm-tuning.md**

Two edits.

**`glm-skills/glm-requirements-code-audit/SETUP.md` (lines 39-41).** Replace:

```markdown
`audit.py` also reads the key from `~/.zcode/*.json`, `~/.config/opencode/auth.json`,
`~/.config/opencode/opencode.json` and `~/.claude/settings.json` — only from fields whose name says they hold
one (`apiKey`, `ANTHROPIC_AUTH_TOKEN`, `token`, …), never by scanning strings.
```

with:

```markdown
`audit.py` also reads the key from `~/.zcode/*.json`, `~/.config/opencode/auth.json`,
`~/.config/opencode/opencode.json`, the OpenCode v2 credentials file
`~/.local/share/opencode/credentials.json` (its `api-key` field) and `~/.claude/settings.json` — only from
fields whose name says they hold one (`apiKey`, `ANTHROPIC_AUTH_TOKEN`, `token`, `api-key`, …), never by
scanning strings.
```

**`glm-skills/glm-requirements-code-audit/references/glm-tuning.md` (lines 29-31).** Replace the three table rows that currently read:

```markdown
| ZCode | agents at `~/.zcode/agents/<name>.md`; fields `name`, `description`, `model`, `thoughtLevel`, `tools`/`disallowedTools`, `maxTurns`, `injectAgentsMd`, `mcpServers`, `color`. **No `effort`, no `permissionMode`, no haiku/sonnet aliases** | `agents/zcode/*.md` uses real GLM ids + `thoughtLevel` |
| ZCode | skills at `~/.zcode/skills/<name>/SKILL.md`, invoked `$glm-requirements-code-audit`; description ≤1024 chars or the skill is **dropped entirely**; body ≤100KB | description measured at 911 chars |
| Both | no Claude Code hook system | the guard hooks and `.claude-plugin/` were removed. On the api lane the enforcement is structural instead: the retriever cannot return `*.md`, `docs/`, README-like files or anything under `.git/`, and the model has no tools at all |
```

with these four rows (the agents row is unchanged; the skills row gains the excerpt and truncation facts plus the recomputed count; and the `Both` row splits into an `OpenCode` row and a `ZCode` row — user-level hooks exist there, merged into `~/.zcode/cli/config.json`):

```markdown
| ZCode | agents at `~/.zcode/agents/<name>.md`; fields `name`, `description`, `model`, `thoughtLevel`, `tools`/`disallowedTools`, `maxTurns`, `injectAgentsMd`, `mcpServers`, `color`. **No `effort`, no `permissionMode`, no haiku/sonnet aliases** | `agents/zcode/*.md` uses real GLM ids + `thoughtLevel` |
| ZCode | skills at `~/.zcode/skills/<name>/SKILL.md`, invoked `$glm-requirements-code-audit`; a description over 1024 chars **drops the skill**; per-turn trigger metadata is a description excerpt of up to 250 chars (the WHEN-clause sits up front); a body over 100KB is truncated when loaded, not dropped | description reordered with the WHEN-clause first; description measured at 920 chars |
| OpenCode | no hook system | the guard hooks and `.claude-plugin/` were removed. On the api lane the enforcement is structural instead: the retriever cannot return `*.md`, `docs/`, README-like files or anything under `.git/`, and the model has no tools at all |
| ZCode | user-level hooks exist, merged into `~/.zcode/cli/config.json` | this skill installs none; the api lane's structural enforcement carries the rules here anyway |
```

- [ ] **Step 12: Run the three tests to verify they pass**

Run: `cd _shared/tests && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_adopt_audit.ZcodeDocSurface.test_glm_tuning_char_count_matches_the_new_description test_adopt_audit.ZcodeDocSurface.test_setup_md_key_paths_include_the_v2_credentials_file test_adopt_audit.ZcodeDocSurface.test_glm_tuning_admits_user_level_zcode_hooks -v`
Expected: PASS — Ran 3 tests, ends with OK.

- [ ] **Step 13: Run the full `_shared` suite**

Run: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK — the run ends with the OK status line, 0 failures, 0 errors.

- [ ] **Step 14: Commit**

From the repository root (the parent of `glm-skills/`), so the paths match the Files list:

```bash
git add glm-skills/glm-requirements-code-audit/SKILL.md glm-skills/glm-requirements-code-audit/agents/zcode/glm-rca-investigator.md glm-skills/glm-requirements-code-audit/agents/zcode/glm-rca-verifier.md glm-skills/glm-requirements-code-audit/scripts/audit.py glm-skills/glm-requirements-code-audit/SETUP.md glm-skills/glm-requirements-code-audit/references/glm-tuning.md glm-skills/_shared/tests/test_adopt_audit.py
git commit -m "feat(glm-requirements-code-audit): zcode surface (bootstrap loop, camelcase tools, corrected docs)"
```

---

### T10: doc-generator zcode fixes [P]

**Depends:** —

**Interfaces:**
- Produces: `general`; `model: glm-5.3-flash`; `thoughtLevel`; `agents/zcode/`; `agents/zcode/glm-doc-reviewer.md`; `model: glm-5.3`; `thoughtLevel: high`; `OC_MAX_LANES`

**Files:**
- Modify: `glm-skills/glm-doc-generator/SKILL.md`
- Test: `glm-skills/glm-doc-generator/agents/zcode/glm-doc-writer.md`
- Modify: `glm-skills/glm-doc-generator/agents/zcode/glm-doc-reviewer.md:4-5`
- Modify: `glm-skills/_shared/tests/test_glm_docgen_snippets.py`
- Modify: `glm-skills/_shared/tests/test_all_skills.py:103-142`

- [ ] **Step 1: Write the failing test for the `agents/zcode/` files**

In `glm-skills/_shared/tests/test_glm_docgen_snippets.py`, add these two module constants directly under the `HUMAN_MARK` line:

```python
ZWRITER = SKILL_DIR / "agents" / "zcode" / "glm-doc-writer.md"
ZREVIEWER = SKILL_DIR / "agents" / "zcode" / "glm-doc-reviewer.md"
```

Then add this class before the `if __name__ == "__main__":` guard:

```python
class ZcodeAgentFileTests(unittest.TestCase):
    def test_zcode_agent_files(self):
        writer, reviewer = read(ZWRITER), read(ZREVIEWER)
        self.assertIn("model: glm-5.3-flash\n", writer, "zcode writer frontmatter lacks model: glm-5.3-flash")
        self.assertIn("thoughtLevel: low\n", writer, "zcode writer frontmatter lacks thoughtLevel: low")
        self.assertIn("model: glm-5.3\n", reviewer, "zcode reviewer frontmatter lacks model: glm-5.3")
        self.assertNotIn("glm-5.3-flash", reviewer, "zcode reviewer still runs glm-5.3-flash")
        self.assertIn("thoughtLevel: high\n", reviewer, "zcode reviewer frontmatter lacks thoughtLevel: high")
        self.assertNotIn("thoughtLevel: low", reviewer, "zcode reviewer still sits at thoughtLevel: low")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_glm_docgen_snippets.py -v`
Expected: FAIL — `test_zcode_agent_files` raises `AssertionError: zcode reviewer frontmatter lacks model: glm-5.3`

- [ ] **Step 3: Switch the reviewer to `glm-5.3` at `thoughtLevel: high`**

Rewrite `glm-skills/glm-doc-generator/agents/zcode/glm-doc-reviewer.md` with exactly this content (only the `model:` and `thoughtLevel:` lines change):

```markdown
---
name: glm-doc-reviewer
description: Fact-checks one generated Markdown doc against real source code and fixes it in place.
model: glm-5.3
thoughtLevel: high
maxTurns: 22
---
You verify one Markdown file against the code and edit it in place — you never write a report
instead of a fix. Check commands, paths, endpoints, signatures, env vars, schema fields,
invented behaviour, secrets, links, clarity — in that order, until the budget runs out. Return
the 5-line block requested, nothing else.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_glm_docgen_snippets.py -v`
Expected: PASS — the module summary ends `OK`

- [ ] **Step 5: Write the failing tests for the `SKILL.md` corrections**

In `glm-skills/_shared/tests/test_all_skills.py`, replace the whole `test_doc_generator_no_unknown_agents` method of `TestSkillMdHygiene` with this version (shown unindented; keep its four-space indent inside the class). The docstring, the harness-name loop and the recon-row checks change; everything else stays byte-identical:

````python
def test_doc_generator_no_unknown_agents(self):
    """glm-doc-generator SKILL.md names glm-doc-writer/glm-doc-reviewer for OpenCode/ZCode;
    'general-purpose' and 'Explore' are built-ins on Claude Code and ZCode, so they may
    appear only on lines that name one of those harnesses (OpenCode's read-only agent is
    `general`)."""
    skill_md = os.path.join(GLM_ROOT, "glm-doc-generator", "SKILL.md")
    with open(skill_md, encoding="utf-8") as fh:
        content = fh.read()
    lines = content.split("\n")

    self.assertIn("glm-doc-writer", content)
    self.assertIn("glm-doc-reviewer", content)

    for line_num, line in enumerate(lines, 1):
        if line.strip().startswith("```") or line.strip().startswith("#"):
            continue
        for name in ("general-purpose", "Explore"):
            if name in line and "Claude Code" not in line and "ZCode" not in line:
                self.fail("SKILL.md:%d names '%s' without Claude Code or ZCode" % (line_num, name))

    # Writer (§3 step 3) and reviewer (§4) dispatch lines name both harness choices.
    type_lines = [l for l in lines if "subagent type" in l]
    writer = [l for l in type_lines if "glm-doc-writer" in l]
    reviewer = [l for l in type_lines if "glm-doc-reviewer" in l]
    self.assertTrue(writer, "no writer 'subagent type' line")
    self.assertTrue(reviewer, "no reviewer 'subagent type' line")
    for l in writer + reviewer:
        for needle in ("OpenCode", "ZCode", "Appendix A", "general-purpose", "Claude Code"):
            self.assertIn(needle, l, "dispatch line lacks %r: %s" % (needle, l))

    # Large-repo recon row: `general` on OpenCode; Explore is a ZCode and Claude Code built-in.
    recon = [l for l in lines if "read-only shards" in l]
    self.assertTrue(recon, "no large-repo recon row")
    for l in recon:
        self.assertIn("`general` on OpenCode", l)
        if "Claude Code harness only" in l:
            self.fail("recon row still claims Explore is Claude Code only")
        if "Explore" in l:
            self.assertIn("ZCode", l, "recon row does not name ZCode for Explore")

    # §8: <skill_dir> comes from the 'Base directory for this skill' line, not /glm-docs.
    self.assertIsNone(re.search(r"/glm-docs[^\n]*inject", content, re.IGNORECASE),
                      "SKILL.md claims /glm-docs injects the skill path")
    self.assertIn("Base directory for this skill", content)
````

Then, in `glm-skills/_shared/tests/test_glm_docgen_snippets.py`, add this class before the `if __name__ == "__main__":` guard:

```python
class ZcodeFactTests(unittest.TestCase):
    def setUp(self):
        self.text = read(SKILL)

    def test_recon_row_explore_is_a_zcode_builtin(self):
        rows = [l for l in self.text.splitlines() if "read-only shards" in l]
        self.assertTrue(rows, "no large-repo recon row")
        for row in rows:
            self.assertIn("`general` on OpenCode", row)
            if "`Explore` is for the Claude Code harness only" in row:
                self.fail("recon row still claims Explore is Claude Code only")
            if "Explore" in row:
                self.assertIn("ZCode", row, "recon row does not name ZCode for Explore")

    def test_appendix_a_frontmatters_carry_real_models(self):
        lines = self.text.split("\n")
        seen = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("thoughtLevel:"):
                seen += 1
                self.assertTrue(i > 0 and lines[i - 1].strip().startswith("model:"),
                                "a thoughtLevel line has no model: line above it")
        self.assertGreater(seen, 0, "no thoughtLevel lines in SKILL.md")
        self.assertIn("model: glm-5.3-flash\n", self.text,
                      "Appendix A writer frontmatter lacks model: glm-5.3-flash")
        self.assertIn("model: glm-5.3\n", self.text,
                      "Appendix A reviewer frontmatter lacks model: glm-5.3")
        self.assertIn("thoughtLevel: high\n", self.text,
                      "Appendix A reviewer frontmatter lacks thoughtLevel: high")

    def test_appendix_a_points_at_the_auto_installed_zcode_agents(self):
        self.assertIn("agents/zcode/", self.text, "no pointer to the agents/zcode/ files")
        self.assertIn("auto-installed", self.text, "no auto-installed wording")

    def test_oc_max_lanes_mention_is_scoped_to_opencode(self):
        mentions = [l for l in self.text.splitlines() if "OC_MAX_LANES" in l]
        self.assertTrue(mentions, "no OC_MAX_LANES mention in SKILL.md")
        for line in mentions:
            self.assertIn("OpenCode", line, "OC_MAX_LANES mention is not scoped to OpenCode")
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_glm_docgen_snippets.py -v`
Expected: FAIL — `test_recon_row_explore_is_a_zcode_builtin` raises `AssertionError: recon row still claims Explore is Claude Code only`; `test_appendix_a_frontmatters_carry_real_models` raises `AssertionError: a thoughtLevel line has no model: line above it`; `test_appendix_a_points_at_the_auto_installed_zcode_agents` raises `AssertionError: no pointer to the agents/zcode/ files`; `test_oc_max_lanes_mention_is_scoped_to_opencode` raises `AssertionError: OC_MAX_LANES mention is not scoped to OpenCode`

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v`
Expected: FAIL — `test_doc_generator_no_unknown_agents` raises `AssertionError: recon row still claims Explore is Claude Code only`

- [ ] **Step 7: Correct the four stale claims in `SKILL.md`**

Run this script from the repository root. It asserts every anchor it needs, so a wrong assumption fails loudly instead of writing a broken file:

````bash
python3 - <<'PYEOF'
import re
from pathlib import Path

path = Path("glm-skills/glm-doc-generator/SKILL.md")
text = path.read_text(encoding="utf-8")

# 1. Recon row: Explore is a ZCode built-in too; `general` is the OpenCode one.
wrong = "`Explore` is for the Claude Code harness only"
assert text.count(wrong) == 1, "recon row phrase not found exactly once"
text = text.replace(wrong, "`Explore` is a ZCode and Claude Code built-in", 1)

# 2. Appendix A frontmatters: gain the model line thoughtLevel needs; the
#    reviewer block moves to glm-5.3 at thoughtLevel high.
lines = text.split("\n")
out = []
for i, line in enumerate(lines):
    stripped = line.strip()
    if not stripped.startswith("thoughtLevel:"):
        out.append(line)
        continue
    above = lines[max(0, i - 10):i]
    owner = ""
    for cand in reversed(above):
        m = re.match(r"^\s*name:\s*(glm-doc-writer|glm-doc-reviewer)\s*$", cand)
        if m:
            owner = m.group(1)
            break
    indent = line[:len(line) - len(line.lstrip())]
    if owner == "glm-doc-writer":
        if not any(c.strip().startswith("model:") for c in above[-4:]):
            out.append(indent + "model: glm-5.3-flash")
        out.append(line)
    elif owner == "glm-doc-reviewer":
        if not any(c.strip() == "model: glm-5.3" for c in above[-4:]):
            fixed = False
            for j in range(len(out) - 1, max(-1, len(out) - 5), -1):
                if out[j].strip().startswith("model:"):
                    out[j] = indent + "model: glm-5.3"
                    fixed = True
                    break
            if not fixed:
                out.append(indent + "model: glm-5.3")
        out.append(indent + "thoughtLevel: high")
    else:
        out.append(line)
text = "\n".join(out)

# 3. Appendix A text points at the auto-installed agents/zcode/ files.
m = re.search(r"^#+[^\n]*Appendix A[^\n]*$", text, re.M)
assert m, "no Appendix A heading"
if "agents/zcode/" not in text[m.end():m.end() + 500]:
    pointer = ("Both agents are auto-installed from `agents/zcode/` into `~/.zcode/agents/` by "
               "the installer; this appendix documents what lands there - never hand-copy it.")
    text = text[:m.end()] + "\n\n" + pointer + text[m.end():]

# 4. The OC_MAX_LANES mention is scoped to OpenCode.
fixed_lines = []
fence = False
for line in text.split("\n"):
    if line.strip().startswith("```"):
        fence = not fence
    elif not fence and "OC_MAX_LANES" in line and "OpenCode" not in line:
        line = line.replace("`OC_MAX_LANES`", "OpenCode's `OC_MAX_LANES`")
        if "OpenCode" not in line:
            line = line.replace("OC_MAX_LANES", "OpenCode's OC_MAX_LANES")
    fixed_lines.append(line)
text = "\n".join(fixed_lines)
for line in text.split("\n"):
    assert "OC_MAX_LANES" not in line or "OpenCode" in line, "unscoped OC_MAX_LANES line: %r" % line

# 5. Every thoughtLevel line now sits directly under a model line.
final_lines = text.split("\n")
for i, line in enumerate(final_lines):
    if line.strip().startswith("thoughtLevel:"):
        assert i > 0 and final_lines[i - 1].strip().startswith("model:"), \
            "thoughtLevel without a model line above at line %d" % (i + 1)

path.write_text(text, encoding="utf-8")
print("SKILL.md zcode facts corrected")
PYEOF
````

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_glm_docgen_snippets.py -v`
Expected: PASS — the module summary ends `OK`

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v`
Expected: PASS — the module summary ends `OK`

- [ ] **Step 9: Run the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: `OK` — no FAILED line

- [ ] **Step 10: Commit**

```bash
git add glm-skills/glm-doc-generator/SKILL.md glm-skills/glm-doc-generator/agents/zcode/glm-doc-writer.md glm-skills/glm-doc-generator/agents/zcode/glm-doc-reviewer.md glm-skills/_shared/tests/test_glm_docgen_snippets.py glm-skills/_shared/tests/test_all_skills.py
git commit -m "fix: correct glm-doc-generator zcode facts and reviewer tuning"
```

---

### T11: git-diff-summary fan-out row [P]

**Depends:** —

**Interfaces:**
- Produces: `model: haiku`; `subagent_type: general-purpose`

**Files:**
- Modify: `glm-skills/glm-git-diff-summary/SKILL.md:39-39`

- [ ] **Step 1: Run the defect check on the FAN_OUT row**

Run: `grep -c "model: haiku" glm-skills/glm-git-diff-summary/SKILL.md`
Expected: `1` — the FAN_OUT row passes `model: haiku`, a parameter the harness rejects

- [ ] **Step 2: Rewrite the FAN_OUT row**

Run this script from the repository root. It rewrites line 39 only — `subagent_type: general-purpose` stays, the `model: haiku` parameter and the alias-mapping note go, and the real-id recovery text stays:

```bash
python3 - <<'PYEOF'
from pathlib import Path

path = Path("glm-skills/glm-git-diff-summary/SKILL.md")
text = path.read_text(encoding="utf-8")
old = "- Claude Code / ZCode — `Task` tool: `subagent_type: general-purpose`, `model: haiku` (on the Z.ai coding plan `haiku` = GLM-5.3-Flash; if the harness rejects the alias, use `glm-5.3-flash`), description `diff chunk NNN`."
assert old in text, "FAN_OUT row anchor not found"
new = "- Claude Code / ZCode — `Task` tool: `subagent_type: general-purpose`, description `diff chunk NNN` (ZCode's `Agent` tool takes no `model` parameter; if a model must be named, use the real id `glm-5.3-flash`)."
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("FAN_OUT row rewritten")
PYEOF
```

- [ ] **Step 3: Verify the alias is gone and the row is rewritten**

Run: `grep -c "haiku" glm-skills/glm-git-diff-summary/SKILL.md`
Expected: `0` (no matches; grep exits 1)

Run: `grep -q "if a model must be named" glm-skills/glm-git-diff-summary/SKILL.md && echo "row rewritten"`
Expected: `row rewritten`

- [ ] **Step 4: Run the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: `OK` — no FAILED line

- [ ] **Step 5: Commit**

```bash
git add glm-skills/glm-git-diff-summary/SKILL.md
git commit -m "fix: drop the haiku model from the glm-git-diff-summary FAN_OUT row"
```

---

### T12: systematic-debugging zcode text [P]

**Depends:** —

**Interfaces:**
- Produces: `SETUP["zcode"]`; `install-zcode.sh`; `thoughtLevel: low`; `maxTurns`; `steps`

**Files:**
- Modify: `glm-skills/glm-systematic-debugging/scripts/debug_tool.py`
- Modify: `glm-skills/glm-systematic-debugging/references/glm-tuning.md:25-48`
- Modify: `glm-skills/glm-systematic-debugging/README.md:30-30`

- [ ] **Step 1: Run the defect check on the setup text**

Run: `grep -c "install-zcode.sh" glm-skills/glm-systematic-debugging/scripts/debug_tool.py`
Expected: `0` (no matches; grep exits 1 — the setup text for `zcode` still tells the user to copy the worker raw)

- [ ] **Step 2: Point the `zcode` setup text at `install-zcode.sh`**

Run this script from the repository root. It finds the raw-copy instruction for the debug worker, replaces it with the installer pointer (frontmatter rewrite plus `thoughtLevel: low`), and parse-checks the file before writing:

```bash
python3 - <<'PYEOF'
import ast
import re
from pathlib import Path

path = Path("glm-skills/glm-systematic-debugging/scripts/debug_tool.py")
text = path.read_text(encoding="utf-8")

# SETUP["zcode"] must point at install-zcode.sh (frontmatter rewrite plus
# thoughtLevel: low) instead of telling the user to copy the worker raw.
pattern = re.compile(
    r"[^\n]*(?:copy|paste|cp)[^\n]*glm-debug-worker[^\n]*(?:\n[^\n]*~/.zcode/agents[^\n]*)?")
assert pattern.search(text), "no raw-copy instruction for the zcode debug worker found"
replacement = (
    "Run `sh install-zcode.sh` from the glm-skills checkout instead of copying the file raw: "
    "it installs this skill to ~/.zcode/skills/ and rewrites the glm-debug-worker frontmatter "
    "into ~/.zcode/agents/ (real model ids, `thoughtLevel: low`, `maxTurns` instead of `steps`).")
text = pattern.sub(replacement, text)
assert "install-zcode.sh" in text, "setup text still lacks the installer pointer"
ast.parse(text)
path.write_text(text, encoding="utf-8")
print("zcode setup text points at install-zcode.sh")
PYEOF
```

- [ ] **Step 3: Verify the setup text**

Run: `grep -q "install-zcode.sh" glm-skills/glm-systematic-debugging/scripts/debug_tool.py && echo "setup points at install-zcode.sh"`
Expected: `setup points at install-zcode.sh`

- [ ] **Step 4: Run the defect checks on `glm-tuning.md`**

Run: `grep -c "credentials.json" glm-skills/glm-systematic-debugging/references/glm-tuning.md`
Expected: `0` (no matches; grep exits 1 — the key-discovery list lacks the v2 credentials file)

Run: `grep -c "steps: 12" glm-skills/glm-systematic-debugging/references/glm-tuning.md`
Expected: `1` — the turn-budget failure mode still speaks of a `steps` budget

- [ ] **Step 5: Correct `glm-tuning.md`**

Run this script from the repository root. It derives the v2 credentials path from `_shared/zai_client.py` — the file whose key-discovery behavior this reference documents — and fixes the three stale claims:

```bash
python3 - <<'PYEOF'
import re
from pathlib import Path

zai = Path("glm-skills/_shared/zai_client.py").read_text(encoding="utf-8")
m = (re.search(r'"([^"\n]*/[^"\n]*credentials\.json[^"\n]*)"', zai)
     or re.search(r'"([^"\n]*credentials\.json[^"\n]*)"', zai))
assert m, "no credentials.json walk found in _shared/zai_client.py"
v2 = m.group(1)

path = Path("glm-skills/glm-systematic-debugging/references/glm-tuning.md")
text = path.read_text(encoding="utf-8")

old = "`~/.config/opencode/auth.json`, `~/.zcode/*.json`"
assert old in text, "key-discovery list anchor missing"
text = text.replace(
    old,
    "`~/.config/opencode/auth.json`, `%s` (v2; its `api-key` field), `~/.zcode/*.json`" % v2, 1)

old = "copy `agents/glm-debug-worker.md` into `~/.zcode/agents/`."
assert old in text, "zcode-note copy instruction missing"
text = text.replace(
    old,
    "`sh install-zcode.sh` installs the skill and rewrites the `glm-debug-worker` frontmatter "
    "(`thoughtLevel: low`, `maxTurns` instead of `steps`) into `~/.zcode/agents/`.", 1)

old = ("Its `steps` budget ran out. `opencode/agents/glm-debug-worker.md` sets `steps: 12`, "
       "enough for a 12-line investigation plus one `stress.sh` arm.")
assert old in text, "turn-budget failure-mode anchor missing"
text = text.replace(
    old,
    "Its turn budget ran out. The zcode install carries it as `maxTurns: 12` (ZCode has no "
    "`steps` agent key; the OpenCode agent file sets `steps: 12`). Enough for a 12-line "
    "investigation plus one `stress.sh` arm.", 1)

path.write_text(text, encoding="utf-8")
print("glm-tuning.md corrected")
PYEOF
```

- [ ] **Step 6: Verify `glm-tuning.md`**

Run: `grep -c "credentials.json" glm-skills/glm-systematic-debugging/references/glm-tuning.md`
Expected: `1`

Run: `grep -c "maxTurns: 12" glm-skills/glm-systematic-debugging/references/glm-tuning.md`
Expected: `1`

Run: `grep -c "install-zcode.sh" glm-skills/glm-systematic-debugging/references/glm-tuning.md`
Expected: `1`

- [ ] **Step 7: Run the defect check on the README row**

Run: `grep -c "install-zcode.sh" glm-skills/glm-systematic-debugging/README.md`
Expected: `0` (no matches; grep exits 1 — the row still tells the user to copy the worker)

- [ ] **Step 8: Align the README row with the installer**

Run this script from the repository root:

```bash
python3 - <<'PYEOF'
from pathlib import Path

path = Path("glm-skills/glm-systematic-debugging/README.md")
text = path.read_text(encoding="utf-8")
old = "| ZCode | `~/.zcode/skills/glm-systematic-debugging/` — invoke with `$glm-systematic-debugging`; copy `agents/glm-debug-worker.md` to `~/.zcode/agents/` |"
assert old in text, "README zcode row anchor not found"
new = "| ZCode | `~/.zcode/skills/glm-systematic-debugging/` — invoke with `$glm-systematic-debugging`; `sh install-zcode.sh` installs the skill and the `glm-debug-worker` agent (frontmatter rewritten, `thoughtLevel: low`) into `~/.zcode/agents/` |"
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("README zcode row aligned with the installer")
PYEOF
```

- [ ] **Step 9: Verify the README row**

Run: `grep -c "install-zcode.sh" glm-skills/glm-systematic-debugging/README.md`
Expected: `1`

- [ ] **Step 10: Run the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: `OK` — no FAILED line

- [ ] **Step 11: Commit**

```bash
git add glm-skills/glm-systematic-debugging/scripts/debug_tool.py glm-skills/glm-systematic-debugging/references/glm-tuning.md glm-skills/glm-systematic-debugging/README.md
git commit -m "fix: point glm-systematic-debugging zcode setup at the installer, correct stale tuning claims"
```

---

### T13: writing-plans zcode dispatch [P]

**Depends:** —

**Interfaces:**
- Produces: `glm-plan-task-writer`; `subagent_type=`; `model sonnet`; `agent_file("zcode")`; `maxTurns: 16`; `ANTHROPIC_BASE_URL`

**Files:**
- Modify: `glm-skills/glm-writing-plans/scripts/plan_tool.py`
- Modify: `glm-skills/glm-writing-plans/SKILL.md:210-215`
- Modify: `glm-skills/glm-writing-plans/references/glm-tuning.md:78-106`
- Modify: `glm-skills/glm-writing-plans/CHANGELOG.md:7-9`
- Modify: `glm-skills/_shared/tests/test_adopt_plan.py`

- [ ] **Step 1: Write the failing tests for the `zcode` agent block and dispatch headers**

Append this class to the end of `glm-skills/_shared/tests/test_adopt_plan.py` (the file is a `unittest` module, so `unittest` is already imported there):

```python
class ZcodeAgentAndDispatchTests(unittest.TestCase):
    """The zcode agent block and the dispatch headers inside plan_tool.py."""

    @staticmethod
    def plan_tool_text():
        import os
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(root, "glm-writing-plans", "scripts", "plan_tool.py"),
                  encoding="utf-8") as fh:
            return fh.read()

    def test_zcode_agent_block_carries_maxturns_16(self):
        lines = self.plan_tool_text().split("\n")
        blocks = []
        for i, line in enumerate(lines):
            if line.strip().startswith("name: glm-plan-task-writer"):
                end = next((j for j in range(i + 1, min(i + 20, len(lines)))
                           if lines[j].strip() == "---"), None)
                if end is not None and any("thoughtLevel:" in w for w in lines[i + 1:end]):
                    blocks.append("\n".join(lines[i:end + 1]))
        self.assertTrue(blocks, "no zcode agent block for glm-plan-task-writer")
        for block in blocks:
            self.assertIn("maxTurns: 16", block, "zcode agent block lacks maxTurns: 16")

    def test_dispatch_headers_carry_no_jargon(self):
        text = self.plan_tool_text()
        self.assertNotIn("sonnet", text, "plan_tool.py still names the sonnet alias")
        self.assertNotIn("subagent_type=", text, "dispatch headers still carry subagent_type= jargon")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_adopt_plan.py -v`
Expected: FAIL — `test_dispatch_headers_carry_no_jargon` raises `AssertionError: plan_tool.py still names the sonnet alias`; `test_zcode_agent_block_carries_maxturns_16` raises `AssertionError: zcode agent block lacks maxTurns: 16`

- [ ] **Step 3: Fix the `zcode` agent block and the dispatch headers in `plan_tool.py`**

Run this script from the repository root. The agent block anchored on `name: glm-plan-task-writer` plus `thoughtLevel:` is the `zcode` one; it gains `maxTurns: 16` right before its closing `---`. The dispatch-header jargon tokens are rewritten in place, and the file is parse-checked before writing:

```bash
python3 - <<'PYEOF'
import ast
import re
from pathlib import Path

path = Path("glm-skills/glm-writing-plans/scripts/plan_tool.py")
text = path.read_text(encoding="utf-8")

# 1. agent_file("zcode"): the glm-plan-task-writer frontmatter gains maxTurns: 16.
lines = text.split("\n")
out = []
i = 0
inserted = 0
while i < len(lines):
    line = lines[i]
    out.append(line)
    if line.strip().startswith("name: glm-plan-task-writer"):
        end = next((j for j in range(i + 1, min(i + 20, len(lines)))
                   if lines[j].strip() == "---"), None)
        block = lines[i + 1:end] if end is not None else []
        if block and any("thoughtLevel:" in w for w in block) \
                and not any(w.strip().startswith("maxTurns:") for w in block):
            indent = line[:len(line) - len(line.lstrip())]
            out.extend(block)
            out.append(indent + "maxTurns: 16")
            inserted += 1
            i = end
            continue
    i += 1
assert inserted >= 1, "no zcode agent block found for glm-plan-task-writer"
text = "\n".join(out)

# 2. The zcode dispatch headers: name the agent, drop the subagent_type= and
#    model-alias jargon, real ids only where a model must be named.
jargon = [
    (re.compile(r"subagent_type=([^\s,;`'\"]+)"), r"the `\1` agent"),
    (re.compile(r"subagent_type:\s*([^\s,;`'\"]+)"), r"the `\1` agent"),
    (re.compile(r"model\s*=\s*sonnet"),
     "real ids `glm-5.3` / `glm-5.3-flash` where a model must be named"),
    (re.compile(r"model:\s*sonnet"),
     "real ids `glm-5.3` / `glm-5.3-flash` where a model must be named"),
    (re.compile(r"\bmodel sonnet\b"),
     "real ids `glm-5.3` / `glm-5.3-flash` where a model must be named"),
]
touched = 0
for pat, repl in jargon:
    text, n = pat.subn(repl, text)
    touched += n
assert touched > 0, "no subagent_type= or model-sonnet jargon found in the dispatch headers"
assert "sonnet" not in text, "a sonnet alias is still present"
assert "subagent_type=" not in text, "subagent_type= jargon is still present"
ast.parse(text)
path.write_text(text, encoding="utf-8")
print("plan_tool.py zcode agent block and dispatch headers updated")
PYEOF
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_adopt_plan.py -v`
Expected: PASS — the module summary ends `OK`

If a pre-existing test in the module now fails because its expected string still names the old header form, update that expectation to the new header wording — the agent written as the `glm-plan-task-writer` agent or the `general-purpose` fallback, plus `real ids glm-5.3 / glm-5.3-flash where a model must be named` — then re-run the same command until the module is green.

- [ ] **Step 5: Scope `ANTHROPIC_BASE_URL` in `SKILL.md` R9**

Run this script from the repository root. The single export block becomes two: the key export stays general, the base URL moves under a harness-scoped sentence:

````bash
python3 - <<'PYEOF'
from pathlib import Path

path = Path("glm-skills/glm-writing-plans/SKILL.md")
text = path.read_text(encoding="utf-8")
old = ("Never run `--apply` without the user's consent. The fast lane needs one export:\n\n"
       "```bash\nexport ZAI_API_KEY=<GLM Coding Plan key>\n"
       "export ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic\n```")
assert old in text, "R9 export block anchor not found"
new = ("Never run `--apply` without the user's consent. The fast lane needs one export:\n\n"
       "```bash\nexport ZAI_API_KEY=<GLM Coding Plan key>\n```\n\n"
       "On a Claude-compatible harness, also export the z.ai Anthropic route:\n\n"
       "```bash\nexport ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic\n```")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
print("R9 export scoped to Claude-compatible harnesses")
PYEOF
````

- [ ] **Step 6: Verify the R9 scoping**

Run: `grep -c "ANTHROPIC_BASE_URL" glm-skills/glm-writing-plans/SKILL.md`
Expected: `1`

Run: `grep -q "On a Claude-compatible harness, also export the z.ai Anthropic route" glm-skills/glm-writing-plans/SKILL.md && echo "R9 scoped"`
Expected: `R9 scoped`

- [ ] **Step 7: Correct the key and truncation claims in `glm-tuning.md`**

Run this script from the repository root. The key-discovery list gains the v2 credentials path exactly as `_shared/zai_client.py` walks it, and the body-size cap claim is labeled unverified instead of asserting an unverified figure:

```bash
python3 - <<'PYEOF'
import re
from pathlib import Path

zai = Path("glm-skills/_shared/zai_client.py").read_text(encoding="utf-8")
m = (re.search(r'"([^"\n]*/[^"\n]*credentials\.json[^"\n]*)"', zai)
     or re.search(r'"([^"\n]*credentials\.json[^"\n]*)"', zai))
assert m, "no credentials.json walk found in _shared/zai_client.py"
v2 = m.group(1)

path = Path("glm-skills/glm-writing-plans/references/glm-tuning.md")
text = path.read_text(encoding="utf-8")

old = "`~/.config/opencode/auth.json` and\n`~/.zcode/*.json` when no environment variable is set."
assert old in text, "key-discovery list anchor missing"
text = text.replace(
    old,
    "`~/.config/opencode/auth.json`, `%s` (v2; its `api-key` field) and\n"
    "`~/.zcode/*.json` when no environment variable is set." % v2, 1)

old = "The description is capped at 1024 characters and the body at 100 KB."
assert old in text, "body-cap claim anchor missing"
text = text.replace(
    old,
    "The description is capped at 1024 characters; a body-size cap is unverified.", 1)

path.write_text(text, encoding="utf-8")
print("glm-tuning.md key and truncation claims corrected")
PYEOF
```

- [ ] **Step 8: Verify the `glm-tuning.md` corrections**

Run: `grep -c "credentials.json" glm-skills/glm-writing-plans/references/glm-tuning.md`
Expected: `1`

Run: `grep -q "api-key" glm-skills/glm-writing-plans/references/glm-tuning.md && echo "v2 api-key field documented"`
Expected: `v2 api-key field documented`

Run: `grep -c "body at 100 KB" glm-skills/glm-writing-plans/references/glm-tuning.md`
Expected: `0` (no matches; grep exits 1)

Run: `grep -c "body-size cap is unverified" glm-skills/glm-writing-plans/references/glm-tuning.md`
Expected: `1`

- [ ] **Step 9: Record the behavior changes in `CHANGELOG.md`**

Run this script from the repository root. It inserts one entry right after the `Fixes` paragraph:

```bash
python3 - <<'PYEOF'
from pathlib import Path

path = Path("glm-skills/glm-writing-plans/CHANGELOG.md")
text = path.read_text(encoding="utf-8")
anchor = ('**Fixes:** (WP5) Bootstrap now respects `$OPENCODE_CONFIG_DIR`, checks locations '
          'in project-first order, and exits with a clear error on miss (no `python3 "" brief`).')
assert anchor in text, "Fixes paragraph anchor not found"
entry = ("\n\n**ZCode hardening:** the zcode dispatch headers name the `glm-plan-task-writer` "
         "agent (or the `general-purpose` fallback) with no `subagent_type=`/model-alias "
         "jargon and real ids only where a model must be named; `agent_file(\"zcode\")` gains "
         "`maxTurns: 16`; SKILL.md R9 scopes `ANTHROPIC_BASE_URL` to Claude-compatible "
         "harnesses; the glm-tuning key list includes the v2 credentials file and the "
         "body-cap claim is labeled unverified.")
path.write_text(text.replace(anchor, anchor + entry, 1), encoding="utf-8")
print("CHANGELOG entry added")
PYEOF
```

- [ ] **Step 10: Verify the `CHANGELOG.md` entry**

Run: `grep -c "ZCode hardening" glm-skills/glm-writing-plans/CHANGELOG.md`
Expected: `1`

- [ ] **Step 11: Run the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: `OK` — no FAILED line

- [ ] **Step 12: Commit**

```bash
git add glm-skills/glm-writing-plans/scripts/plan_tool.py glm-skills/glm-writing-plans/SKILL.md glm-skills/glm-writing-plans/references/glm-tuning.md glm-skills/glm-writing-plans/CHANGELOG.md glm-skills/_shared/tests/test_adopt_plan.py
git commit -m "fix: glm-writing-plans zcode dispatch headers, agent maxTurns and R9 scoping"
```

---

### T14: folder guide zcode facts [P]

**Depends:** —

**Interfaces:**
- Produces: `~/.zcode/cli/config.json`; `subagent_type`; `run_in_background`; `install-zcode.sh`

**Files:**
- Modify: `glm-skills/CLAUDE.md:45-205`

- [ ] **Step 1: Verify the delegation note is absent (the failing check)**

The `## Commands` section documents `install-zcode.sh` with a single comment line today. Run the check from the repository root (the folder that contains `glm-skills/`):

Run: `grep -cF 'delegated to devteam.py doctor' glm-skills/CLAUDE.md`
Expected: `0` (grep exits 1 — the guide does not yet record the delegation).

- [ ] **Step 2: Add the doctor delegation note to the Commands block**

In the bash block inside the `## Commands` section, find these two consecutive lines:

```text
# Install all eight skills into ZCode: skills to ~/.zcode/skills/<name>, agents rewritten to ZCode frontmatter into ~/.zcode/agents
sh install-zcode.sh [--home DIR] [--flash MODEL_ID] [--main MODEL_ID] [--dry-run]
```

Replace both lines with:

```text
# Install all eight skills into ZCode: skills to ~/.zcode/skills/<name>, agents rewritten to ZCode
# frontmatter into ~/.zcode/agents. The agent install and the user-level hook merge into
# ~/.zcode/cli/config.json are delegated to devteam.py doctor in its zcode harness mode: a
# key-preserving merge (existing user keys survive, .bak before rewrite, re-run is a no-op) whose
# hook commands point at the installed skill's absolute guard.py path.
sh install-zcode.sh [--home DIR] [--flash MODEL_ID] [--main MODEL_ID] [--dry-run]
```

- [ ] **Step 3: Verify the delegation note is present**

Run: `grep -cF 'delegated to devteam.py doctor' glm-skills/CLAUDE.md`
Expected: `1` (exit 0 — the new comment line matches).

- [ ] **Step 4: Verify the facts subsection is absent (the failing check)**

Run: `grep -cF -e '### ZCode facts (3.14.4)' -e 'no SubagentStop' -e '{description, prompt, subagent_type, run_in_background}' -e 'v2/credentials.json' -e 'over 100KB is truncated' -e 'lite/strong' -e 'only in a new session' -e 'hooks.enabled: true' glm-skills/CLAUDE.md`
Expected: `0` (grep exits 1 — none of the eight fact strings exists in the guide yet).

- [ ] **Step 5: Insert the verified facts subsection**

Insert the subsection below directly above the `## Conventions and gotchas` heading: it goes right after the blank line that follows the `120000 ms.` line ending the `### OpenCode version facts (v1.18.x and v2.0.x)` subsection, and it keeps exactly one blank line between its last bullet and that heading.

```text
### ZCode facts (3.14.4)

All facts were verified against the local 3.14.4 binary unless marked otherwise.

- **Skills.** Skills live at `~/.zcode/skills/<name>/SKILL.md`, invoked as `$<name>`. A frontmatter
  `description` over 1024 characters makes ZCode drop the whole skill; a body over 100KB is truncated when
  loaded. Per-turn trigger metadata is the name plus a description excerpt of up to 250 characters, so the
  WHEN-clause must sit at the front of every description. There is no `!` preload support; unknown
  frontmatter keys are ignored.
- **Agents.** Custom subagents live at `~/.zcode/agents/<name>.md`, user level only, no nesting; several
  launched together in the foreground run in parallel. Frontmatter keys: `name`, `description`, `model`,
  `thoughtLevel` (honored only together with a specific `model`), `color`, `tools`/`disallowedTools`,
  `maxTurns`, `injectAgentsMd`, `mcpServers`; no haiku/sonnet/opus aliases exist. The installed agents
  split lite/strong — lite workers run on `glm-5.3-flash` (the `--flash` default), strong judgment agents
  on `glm-5.3` (the `--main` default).
- **Dispatch.** Subagents are dispatched through the `Agent` tool (Task alias) whose input schema is
  `{description, prompt, subagent_type, run_in_background}` with `subagent_type` omitted defaulting to
  `general-purpose` — the Claude Code Task shape minus the `model` parameter (binary-verified; the web
  docs confirm the tool and the `general-purpose` + `Explore` built-ins but do not document the schema).
  `SendMessage`, `TaskStop`, and Bash `run_in_background` + `timeout` all exist and are
  Claude-Code-compatible.
- **Hooks.** A full Claude-Code-compatible hook system — SessionStart, UserPromptSubmit, PreToolUse,
  PermissionRequest, PostToolUse, PostToolUseFailure, Stop — with no SubagentStop. Hooks are configured at
  user level only, in `~/.zcode/cli/config.json` (`hooks.enabled: true`); project/workspace-level hooks
  are ignored. Hook stdin JSON carries snake_case + camelCase fields including `agent_type` (the calling
  agent's name); exit code 2 blocks; stdout `hookSpecificOutput.permissionDecision` = allow/ask/deny —
  the exact shapes `guard.py` already prints.
- **Credentials.** There is no public headless CLI. Credentials live at `~/.zcode/v2/credentials.json`
  under `account-provider → coding-plan → account → <plan> → <uuid> → api-key` (field name `api-key`,
  hyphenated; OAuth/JWT fields keep distinct names and are never picked).
- **Session reload.** Skills, agents and hook config are read at session start; anything installed or
  reconfigured mid-session — including a fresh hook merge — takes effect only in a new session.
```

- [ ] **Step 6: Verify the subsection facts are present**

Run: `grep -cF -e '### ZCode facts (3.14.4)' -e 'no SubagentStop' -e '{description, prompt, subagent_type, run_in_background}' -e 'v2/credentials.json' -e 'over 100KB is truncated' -e 'lite/strong' -e 'only in a new session' -e 'hooks.enabled: true' glm-skills/CLAUDE.md`
Expected: `8` (exit 0 — one matching line per fact string: the subsection heading, the hook list with no SubagentStop, the dispatch schema, the credentials path, the body-size truncation, the lite/strong split, the new-session rule and the hook-enable flag).

- [ ] **Step 7: Run the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: `OK` as the run's final line (zero failures, zero errors — a guide edit must not break any test).

- [ ] **Step 8: Commit**

```bash
git add glm-skills/CLAUDE.md
git commit -m "docs: record ZCode facts and doctor delegation in the glm folder guide"
```
