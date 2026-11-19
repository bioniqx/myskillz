# Five Session Models and Four Install Targets — Implementation Plan

> **Execution note:** This plan is self-contained and tool-agnostic. Any AI
> agent or human engineer can execute it with only a shell, a code editor, and
> git. Follow the Execution Protocol below.

**Goal:** Make every skill folder's model layer name and correctly address the five session models (`GLM-5.3-Flash`, `DeepSeek V4.1 Flash`, `GLM 5.3`, `DeepSeek V4 Pro`, `Claude Sonnet 5.5`), and install all eleven skills completely into the four harness targets (`~/.agents/skills`, `~/.claude/skills`, `~/.config/opencode/skills`, `~/.zcode/skills`).

**Architecture:** Three wording/pin edits inside the existing model layer (the shared GUARD line, the pin vocabulary, four tuning docs, the model-naming lines in bodies and agents) plus one new front-end installer (`install-all.sh`) that delegates the first target to `install-zcode.sh` and adds three copy targets. No engine, scoring, gate or hook behavior changes; agents keep following the session model.

**Tech Stack:** stdlib Python 3, POSIX sh, unittest.

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

- stdlib-only Python 3 + POSIX sh; no new dependencies, no package managers.
- Touch ONLY paths under `glm-skills/`; never `../claude-skills/`, `../hybrid-skills/`, `../opencode-skills/`. Installer RUNS may write to the four home targets (T05); installer TESTS write only under a temp HOME.
- Work on main; never create branches.
- Every `SKILL.md` edit keeps frontmatter `name` equal to the directory name, `description` at 1024 characters or fewer with the WHEN clause inside the first ~250, and the body under 500 lines. Re-run the hygiene suite after every frontmatter edit.
- Agent files keep no model id and their `thoughtLevel` lines stay untouched.
- No numeric speed, price or quota claim for the non-flash session models is added anywhere; their rows and notes stay qualitative. Existing cited numbers stay as they are.
- After any edit to `_glm-skills/_shared/handoff.py`, `_shared/flash_pin.py`, `_shared/zai_client.py` or `_shared/decide.py`, run `sh _shared/sync.sh` from `glm-skills/` and commit the vendored copies in the same task; `test_vendored.py` enforces byte identity.
- `install-zcode.sh` keeps its own contract unchanged except the two saved-pin case arms T04 widens; `install-all.sh` only fronts it.
- Never touch, delete or overwrite a folder that is not `glm-*` inside any target directory.
- Full test suite, run from `glm-skills/`: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
- Files in English; plain ASCII (no emoji, arrows or decorative glyphs) outside `.md` files; `.md` files exempt.
- Changelog entries only where the folder already keeps a `CHANGELOG.md` (`glm-brainstorming`, `glm-writing-plans`; check with `ls` before writing, skip silently when absent).

## References

- `glm-skills/_shared/tests/test_install_zcode.py` - the installer-test idiom: temp HOME, an `install()` helper, assert on the installed tree. `test_install_all.py` follows this style.
- `glm-skills/install-zcode.sh` - discovery loop, preflight python block, junk-exclusion find command, and the `run()` dry-run wrapper that `install-all.sh` mirrors.
- `glm-skills/_shared/flash_pin.py` - the pin vocabulary and resolve path T01 widens.

## File Structure

- `glm-skills/_shared/` — `handoff.py`, `flash_pin.py`, `zai_client.py` (T01)
- `glm-skills/_shared/tests/` — `test_flash_pin_pro.py` (T01), `test_model_terms_tuning.py` (T02), `test_model_terms_bodies.py` (T03), `test_install_all.py` (T04), `test_install_zcode.py` (T04, one added method)
- Vendored copies refreshed by `sync.sh` in T01 — `scripts/handoff.py` in `glm-brainstorming`, `glm-dev-team`, `glm-doc-generator`, `glm-git-diff-summary`, `glm-idea-to-spec`, `glm-requirements-code-audit`, `glm-systematic-debugging`, `glm-writing-plans`; `scripts/flash_pin.py` in `glm-dev-team`, `glm-systematic-debugging`, `glm-writing-plans`, `glm-requirements-code-audit`; `scripts/zai_client.py` in `glm-systematic-debugging`, `glm-writing-plans`, `glm-requirements-code-audit`
- Tuning docs (T02): `glm-skills/glm-brainstorming/glm-tuning.md`, `glm-skills/glm-writing-plans/references/glm-tuning.md`, `glm-skills/glm-requirements-code-audit/references/glm-tuning.md`, `glm-skills/glm-systematic-debugging/references/glm-tuning.md`
- Bodies and agents (T03): `glm-skills/glm-brainstorming/SKILL.md`, `glm-skills/glm-brainstorming/visual-companion.md`, `glm-skills/glm-brainstorming/research-playbook.md`, `glm-skills/glm-brainstorming/fanout-playbook.md`, `glm-skills/glm-brainstorming/CHANGELOG.md`, `glm-skills/glm-dev-team/SKILL.md`, `glm-skills/glm-dev-team/agents/glm-team-leader.md`, `glm-skills/glm-writing-plans/SKILL.md`, `glm-skills/glm-writing-plans/CHANGELOG.md`, `glm-skills/glm-systematic-debugging/SKILL.md`, `glm-skills/glm-systematic-debugging/README.md`, `glm-skills/glm-requirements-code-audit/SKILL.md`
- `glm-skills/install-all.sh` (new), `glm-skills/install-zcode.sh` (T04)
- `glm-skills/docs/specs/2026-11-19-five-models-four-targets.md`, `glm-skills/docs/plans/2026-11-19-five-models-four-targets.md` (T05 commits them)

## Contracts

#### T01: shared model layer — five-model GUARD line and pro pin words
- Files: `glm-skills/_shared/handoff.py`, `glm-skills/_shared/flash_pin.py`, `glm-skills/_shared/zai_client.py`, `glm-skills/_shared/tests/test_flash_pin_pro.py`, `glm-skills/glm-brainstorming/scripts/handoff.py`, `glm-skills/glm-dev-team/scripts/handoff.py`, `glm-skills/glm-dev-team/scripts/flash_pin.py`, `glm-skills/glm-doc-generator/scripts/handoff.py`, `glm-skills/glm-git-diff-summary/scripts/handoff.py`, `glm-skills/glm-idea-to-spec/scripts/handoff.py`, `glm-skills/glm-requirements-code-audit/scripts/handoff.py`, `glm-skills/glm-requirements-code-audit/scripts/flash_pin.py`, `glm-skills/glm-requirements-code-audit/scripts/zai_client.py`, `glm-skills/glm-systematic-debugging/scripts/handoff.py`, `glm-skills/glm-systematic-debugging/scripts/flash_pin.py`, `glm-skills/glm-systematic-debugging/scripts/zai_client.py`, `glm-skills/glm-writing-plans/scripts/handoff.py`, `glm-skills/glm-writing-plans/scripts/flash_pin.py`, `glm-skills/glm-writing-plans/scripts/zai_client.py`
- Produces: rewritten `GUARD flash` line in `handoff.py` naming all five session models; widened `_name` accepting `deepseek-v4-pro` and `glm-5.3`; `pin_word(home=None)` returning the raw pin word; `PRO_API` mapping the pro words to their API ids; `resolve_http_model` returning the pro id under a pro pin
- Consumes: `provider` (existing), `API_REMAP` (existing), `_payload` (existing, unchanged behavior)
- Read: `glm-skills/_shared/flash_pin.py`, `glm-skills/_shared/handoff.py` (GUARDS tuple), `glm-skills/_shared/zai_client.py` (docstring only)
- Spec: L1-20, L23-29, L56-58
- Tier: std

#### T02: four tuning docs — session-model tier block
- Files: `glm-skills/glm-brainstorming/glm-tuning.md`, `glm-skills/glm-writing-plans/references/glm-tuning.md`, `glm-skills/glm-requirements-code-audit/references/glm-tuning.md`, `glm-skills/glm-systematic-debugging/references/glm-tuning.md`, `glm-skills/_shared/tests/test_model_terms_tuning.py`
- Produces: a "Session models" block naming the five models and their tiers at the top of each tuning doc; the economics table's pro row re-marked for pro-tier sessions instead of "not used"; the runtime "do not name" sentence in each copy reworded to the no-promotion rule
- Read: each of the four files (their tables and idioms differ; only the named edits apply)
- Spec: L30-33
- Tier: light

#### T03: bodies and agents — tier wording sweep
- Files: `glm-skills/glm-brainstorming/SKILL.md`, `glm-skills/glm-brainstorming/visual-companion.md`, `glm-skills/glm-brainstorming/research-playbook.md`, `glm-skills/glm-brainstorming/fanout-playbook.md`, `glm-skills/glm-brainstorming/CHANGELOG.md`, `glm-skills/glm-dev-team/SKILL.md`, `glm-skills/glm-dev-team/agents/glm-team-leader.md`, `glm-skills/glm-writing-plans/SKILL.md`, `glm-skills/glm-writing-plans/CHANGELOG.md`, `glm-skills/glm-systematic-debugging/SKILL.md`, `glm-skills/glm-systematic-debugging/README.md`, `glm-skills/glm-requirements-code-audit/SKILL.md`, `glm-skills/_shared/tests/test_model_terms_bodies.py`
- Produces: model-naming lines that address a flash, pro or Claude-tier session truthfully; the brainstorming frontmatter `description` naming the tuning scope within 1024 characters; the `models` metadata lines in the debugging and audit skills listing all five model ids
- Read: the grep anchor lines quoted in the task body
- Spec: L34-37
- Tier: std

#### T04: install-all.sh — four-target installer front end
- Files: `glm-skills/install-all.sh`, `glm-skills/install-zcode.sh`, `glm-skills/_shared/tests/test_install_all.py`, `glm-skills/_shared/tests/test_install_zcode.py`
- Produces: `install-all.sh [--home DIR] [--dry-run] [--only zcode,agents,claude,opencode]`; first-target delegation to the delegated installer; as-is copy for the other two plain targets; the third target's layout with `opencode/agents/`, preserved `opencode/commands` bodies and a bumped `.oc-major` per skill; widened saved-pin case arms in the delegated installer
- Consumes: preflight and copy behavior of `install-zcode.sh` (existing)
- Read: `glm-skills/install-zcode.sh`
- Spec: L17-19, L38-41, L45-53, L59-61
- Tier: deep

#### T05: integration — suites, real install, final commit
- Depends: T01, T02, T03, T04
- Files: `glm-skills/docs/specs/2026-11-19-five-models-four-targets.md`, `glm-skills/docs/plans/2026-11-19-five-models-four-targets.md`
- Produces: green full suite and engine self-test; `install-all.sh` run for real against the four home targets with printed counts; verified target trees; the final commit. Every Evidence line in the spec is re-checked against the merged tree; every Assumption is restated in the final report.
- Spec: L63-98
- Tier: std

<!-- WAVES -->
## Execution Waves

Every task in a wave has all its Depends/Runs-after tasks in earlier waves. Tasks in the
same wave touch disjoint files, so a wave's `[P]` tasks may all run at once.

- **Wave 1:** T01 [P], T02 [P], T03 [P], T04 [P]
- **Wave 2:** T05
<!-- /WAVES -->

<!-- TASKS -->

### T01: shared model layer — five-model GUARD line and pro pin words [P]

**Depends:** —

**Interfaces:**
- Uses existing: `provider`; `API_REMAP`; `_payload`
- Produces: `GUARD flash`; `handoff.py`; `_name`; `deepseek-v4-pro`; `glm-5.3`; `pin_word(home=None)`; `PRO_API`; `resolve_http_model`

**Files:**
- Modify: `glm-skills/_shared/handoff.py`
- Modify: `glm-skills/_shared/flash_pin.py`
- Modify: `glm-skills/_shared/zai_client.py`
- Test: `glm-skills/_shared/tests/test_flash_pin_pro.py`
- Refresh: `glm-skills/glm-brainstorming/scripts/handoff.py`
- Refresh: `glm-skills/glm-dev-team/scripts/handoff.py`
- Refresh: `glm-skills/glm-dev-team/scripts/flash_pin.py`
- Refresh: `glm-skills/glm-doc-generator/scripts/handoff.py`
- Refresh: `glm-skills/glm-git-diff-summary/scripts/handoff.py`
- Refresh: `glm-skills/glm-idea-to-spec/scripts/handoff.py`
- Refresh: `glm-skills/glm-requirements-code-audit/scripts/handoff.py`
- Refresh: `glm-skills/glm-requirements-code-audit/scripts/flash_pin.py`
- Refresh: `glm-skills/glm-requirements-code-audit/scripts/zai_client.py`
- Refresh: `glm-skills/glm-systematic-debugging/scripts/handoff.py`
- Refresh: `glm-skills/glm-systematic-debugging/scripts/flash_pin.py`
- Refresh: `glm-skills/glm-systematic-debugging/scripts/zai_client.py`
- Refresh: `glm-skills/glm-writing-plans/scripts/handoff.py`
- Refresh: `glm-skills/glm-writing-plans/scripts/flash_pin.py`
- Refresh: `glm-skills/glm-writing-plans/scripts/zai_client.py`

- [ ] **Step 1: Write the failing tests**

Create `glm-skills/_shared/tests/test_flash_pin_pro.py`:

```python
import importlib.util
import os
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SHARED = os.path.join(HERE, "..")


def _load(name):
    spec = importlib.util.spec_from_file_location(
        name + "_under_test", os.path.join(SHARED, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


flash_pin = _load("flash_pin")
handoff = _load("handoff")


class ProPinWordTests(unittest.TestCase):
    def test_pro_words_resolve_to_their_providers(self):
        for word, provider in (("deepseek-v4-pro", "deepseek"), ("glm-5.3", "glm")):
            with mock.patch.dict(os.environ, {"GLM_FLASH": word}):
                self.assertEqual(flash_pin.from_env(), provider)

    def test_pin_word_returns_the_raw_vocabulary_word(self):
        for word in ("deepseek-v4-pro", "glm-5.3", "deepseek", "glm", "flash", ""):
            with mock.patch.dict(os.environ, {"GLM_FLASH": word}):
                self.assertEqual(flash_pin.pin_word(), word)

    def test_unknown_words_still_resolve_to_no_pin(self):
        with mock.patch.dict(os.environ, {"GLM_FLASH": "nonsense"}):
            self.assertEqual(flash_pin.from_env(), "")
            self.assertEqual(flash_pin.pin_word(), "nonsense")


class ResolveHttpModelTests(unittest.TestCase):
    def test_pro_pin_resolves_every_model_to_the_pro_api_id(self):
        for word in ("deepseek-v4-pro", "glm-5.3"):
            with mock.patch.dict(os.environ, {"GLM_FLASH": word}):
                self.assertEqual(flash_pin.resolve_http_model("glm-5.3-flash"), word)

    def test_flash_pins_keep_today_behavior(self):
        with mock.patch.dict(os.environ, {"GLM_FLASH": "deepseek"}):
            self.assertEqual(flash_pin.resolve_http_model("glm-5.3-flash"), "deepseek-flash")
        with mock.patch.dict(os.environ, {"GLM_FLASH": "glm"}):
            self.assertEqual(flash_pin.resolve_http_model("glm-5.3-flash"), "glm-5.3-flash")


class GuardLineTests(unittest.TestCase):
    def test_guard_flash_names_all_five_session_models(self):
        text = " ".join(handoff.GUARDS)
        for needle in ("GLM-5.3-Flash", "DeepSeek V4.1 Flash", "GLM 5.3",
                       "DeepSeek V4 Pro", "Claude Sonnet 5.5"):
            self.assertIn(needle, text)

    def test_guard_flash_keeps_the_no_promotion_rule(self):
        text = " ".join(handoff.GUARDS)
        self.assertIn("never promote a lane", text)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_flash_pin_pro.py -v`
Expected: FAILED (errors and failures): `pin_word` does not exist (AttributeError), the pro `from_env` words return `""`, the resolve test gets `"deepseek-flash"` instead of the pro id, and both GuardLineTests fail on the missing model names.

- [ ] **Step 3: Widen the pin vocabulary in _shared/flash_pin.py**

In `glm-skills/_shared/flash_pin.py`:

1. Update the module docstring's first paragraph to:

```python
"""Flash pin for the GLM and DeepSeek model tiers.

Session models this layer knows: GLM-5.3-Flash and DeepSeek V4.1 Flash
(flash tier), GLM 5.3 and DeepSeek V4 Pro (pro tier), Claude Sonnet 5.5
(Claude tier - session only, never an HTTP provider). ~/.zcode/glm-flash
holds one pin word; the HTTP fan-out follows it. GLM_FLASH overrides that
file for one process. A missing HOME is "no pin file": unit tests that
clear the environment stay on GLM even when the developer has a pin
installed.
"""
```

2. Below `API_REMAP`, add:

```python
PRO_API = {
    "deepseek-v4-pro": "deepseek-v4-pro",
    "glm-5.3": "glm-5.3",
}
```

3. Extend `_name` so the pro words map to their providers. The two arms become:

```python
def _name(word):
    if word in ("deepseek", "ds", "deepseek-flash", "deepseek-v4-pro"):
        return "deepseek"
    if word in ("glm", "glm-5.3-flash", "flash", "glm-5.3"):
        return "glm"
    return ""
```

4. Add `pin_word` directly above `provider`:

```python
def pin_word(home=None):
    """The raw pin word: GLM_FLASH, then the pin file, else ""."""
    word = _word(os.environ.get("GLM_FLASH"))
    if word:
        return word
    home = _home(home)
    if not home:
        return ""
    path = os.path.join(home, ".zcode", "glm-flash")
    try:
        with open(path, encoding="utf-8") as fh:
            return _word(fh.read())
    except OSError:
        return ""
```

5. Replace `resolve_http_model` with:

```python
def resolve_http_model(model):
    word = pin_word()
    if word in PRO_API:
        return PRO_API[word]
    if http_provider() != "deepseek":
        return model
    return API_REMAP.get(model, model)
```

`from_env`, `from_file`, `provider`, `agent_provider`, `http_provider`, `stamp_agent` and `stamp_tree` keep their signatures and behavior.

- [ ] **Step 4: Rewrite the GUARD flash line in _shared/handoff.py**

In the `GUARDS` tuple of `glm-skills/_shared/handoff.py`, replace the single line:

```python
    "GUARD flash: the session model is GLM-5.3-Flash or DeepSeek V4.1 Flash (deepseek-flash). Do not switch to GLM-5.3 or deepseek-v4-pro.",
```

with:

```python
    "GUARD flash: the session model is one of GLM-5.3-Flash, DeepSeek V4.1 Flash, GLM 5.3, DeepSeek V4 Pro or Claude Sonnet 5.5. Follow the session model, never switch it, and never promote a lane to another model.",
```

No other GUARDS entry changes.

- [ ] **Step 5: Note the five models in _shared/zai_client.py**

In `glm-skills/_shared/zai_client.py`, extend the module docstring (the paragraph that starts `Canonical copy lives in skills/glm/_shared/`) by appending this one sentence at its end:

```text
Session models the skills address: GLM-5.3-Flash and DeepSeek V4.1 Flash (flash tier), GLM 5.3 and DeepSeek V4 Pro (pro tier), Claude Sonnet 5.5 (session only); this client fans out over the glm and deepseek providers only.
```

No payload, key or retry logic changes.

- [ ] **Step 6: Run the new tests to verify they pass**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_flash_pin_pro.py -v`
Expected: OK — Ran 7 tests.

- [ ] **Step 7: Re-vendor the shared scripts and run the full suite**

Run: `cd glm-skills && sh _shared/sync.sh && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: sync prints one `synced` line per vendored copy (22 lines: 8 handoff, 4 flash_pin, 3 zai_client, 7 decide), then the full suite ends OK — zero failures, zero errors.

- [ ] **Step 8: Commit**

From the repository root, on main:

```bash
git add glm-skills/_shared/handoff.py glm-skills/_shared/flash_pin.py glm-skills/_shared/zai_client.py glm-skills/_shared/tests/test_flash_pin_pro.py glm-skills/glm-brainstorming/scripts/handoff.py glm-skills/glm-dev-team/scripts/handoff.py glm-skills/glm-dev-team/scripts/flash_pin.py glm-skills/glm-doc-generator/scripts/handoff.py glm-skills/glm-git-diff-summary/scripts/handoff.py glm-skills/glm-idea-to-spec/scripts/handoff.py glm-skills/glm-requirements-code-audit/scripts/handoff.py glm-skills/glm-requirements-code-audit/scripts/flash_pin.py glm-skills/glm-requirements-code-audit/scripts/zai_client.py glm-skills/glm-systematic-debugging/scripts/handoff.py glm-skills/glm-systematic-debugging/scripts/flash_pin.py glm-skills/glm-systematic-debugging/scripts/zai_client.py glm-skills/glm-writing-plans/scripts/handoff.py glm-skills/glm-writing-plans/scripts/flash_pin.py glm-skills/glm-writing-plans/scripts/zai_client.py
git commit -m "feat: address the five session models in the shared model layer"
```

---

### T02: four tuning docs — session-model tier block [P]

**Depends:** —

**Files:**
- Modify: `glm-skills/glm-brainstorming/glm-tuning.md`
- Modify: `glm-skills/glm-writing-plans/references/glm-tuning.md`
- Modify: `glm-skills/glm-requirements-code-audit/references/glm-tuning.md`
- Modify: `glm-skills/glm-systematic-debugging/references/glm-tuning.md`
- Test: `glm-skills/_shared/tests/test_model_terms_tuning.py`

- [ ] **Step 1: Write the failing test**

Create `glm-skills/_shared/tests/test_model_terms_tuning.py`:

```python
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

DOCS = [
    os.path.join(HERE, "..", "..", "glm-brainstorming", "glm-tuning.md"),
    os.path.join(HERE, "..", "..", "glm-writing-plans", "references", "glm-tuning.md"),
    os.path.join(HERE, "..", "..", "glm-requirements-code-audit", "references", "glm-tuning.md"),
    os.path.join(HERE, "..", "..", "glm-systematic-debugging", "references", "glm-tuning.md"),
]

NEEDLES = ("GLM-5.3-Flash", "DeepSeek V4.1 Flash", "GLM 5.3", "DeepSeek V4 Pro",
           "Claude Sonnet 5.5", "flash tier", "pro tier", "Claude tier")


class TuningDocModelTerms(unittest.TestCase):
    def test_every_tuning_doc_names_the_five_session_models_by_tier(self):
        for path in DOCS:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            for needle in NEEDLES:
                self.assertIn(needle, "%s: %s" % (os.path.basename(path), needle))

    def test_brainstorming_table_no_longer_marks_the_pro_row_unused(self):
        with open(DOCS[0], encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("| not used |", text)
        self.assertIn("pro tier", text)

    def test_no_numeric_table_rows_for_the_new_tiers(self):
        with open(DOCS[0], encoding="utf-8") as fh:
            rows = [ln for ln in fh.read().splitlines() if ln.startswith("| ")]
        for ln in rows:
            for name in ("DeepSeek V4 Pro", "Claude Sonnet 5.5", "DeepSeek V4.1 Flash"):
                self.assertFalse(
                    ln.startswith("| " + name),
                    "numeric table row added for %s: %s" % (name, ln))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_model_terms_tuning.py -v`
Expected: FAILED (failures) — every doc misses most NEEDLES today, and the economics table still carries `| not used |`.

- [ ] **Step 3: Insert the Session models block into each of the four files**

In each of the four tuning docs, directly under the file's own intro paragraph (the paragraph that says when to read the file), insert:

```markdown
## Session models

Five session models, three tiers: GLM-5.3-Flash and DeepSeek V4.1 Flash
(flash tier - the default lanes), GLM 5.3 and DeepSeek V4 Pro (pro tier - a
session the user pinned to a pro model), Claude Sonnet 5.5 (Claude tier).
Agents always follow the session model; no lane is promoted to another
model; decisions close in this skill's scripts, not in a model judgment.
Qualitative only for the pro and Claude tiers - no speed or price numbers
are claimed for them here.
```

- [ ] **Step 4: Fix the economics table and the runtime sentence in the brainstorming copy**

In `glm-skills/glm-brainstorming/glm-tuning.md`:

1. Replace the table row:

```markdown
| GLM-5.3 | 63.4 tok/s | 1.40 | 4.40 | not used |
```

with:

```markdown
| GLM-5.3 | 63.4 tok/s | 1.40 | 4.40 | pro tier: only when the session is pinned to it |
```

2. Replace the sentence `A GLM-5.3 call is the same family at about 9× the price. It does not close a decision.` with `A GLM-5.3 call is the same family at about 9× the price, and it still does not close a decision.` (the rest of that paragraph stays).
3. In section 5 (the runtime section), replace the two-line guidance:

```markdown
When a model
  must be named yourself, use `glm-5.3-flash` or `deepseek-flash`. Do not name `glm-5.3` or `deepseek-v4-pro`.
```

with:

```markdown
When a model
  must be named yourself, name the session's own tier id (`glm-5.3-flash`, `deepseek-flash`, or the pro id the pin file holds). Never promote a lane to another model.
```

- [ ] **Step 5: Reword the denylist guidance in the other three copies**

In each of `glm-writing-plans/references/glm-tuning.md`, `glm-requirements-code-audit/references/glm-tuning.md` and `glm-systematic-debugging/references/glm-tuning.md`, find each sentence that forbids naming `GLM-5.3` or `deepseek-v4-pro` (grep: `grep -n "deepseek-v4-pro" <file>`), and reword it to the no-promotion form: `Do not promote a lane above the session model; when an id must be named, name the session's own tier id.` Keep every other sentence in those sections unchanged.

- [ ] **Step 6: Run the new test and the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_model_terms_tuning.py -v`
Expected: OK — Ran 3 tests.

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK.

- [ ] **Step 7: Commit**

```bash
git add glm-skills/glm-brainstorming/glm-tuning.md glm-skills/glm-writing-plans/references/glm-tuning.md glm-skills/glm-requirements-code-audit/references/glm-tuning.md glm-skills/glm-systematic-debugging/references/glm-tuning.md glm-skills/_shared/tests/test_model_terms_tuning.py
git commit -m "feat: five-model tier block in every tuning doc"
```

---

### T03: bodies and agents — tier wording sweep [P]

**Depends:** —

**Interfaces:**
- Produces: `description`; `models`

**Files:**
- Modify: `glm-skills/glm-brainstorming/SKILL.md`
- Modify: `glm-skills/glm-brainstorming/visual-companion.md`
- Modify: `glm-skills/glm-brainstorming/research-playbook.md`
- Modify: `glm-skills/glm-brainstorming/fanout-playbook.md`
- Modify: `glm-skills/glm-brainstorming/CHANGELOG.md`
- Modify: `glm-skills/glm-dev-team/SKILL.md`
- Modify: `glm-skills/glm-dev-team/agents/glm-team-leader.md`
- Modify: `glm-skills/glm-writing-plans/SKILL.md`
- Modify: `glm-skills/glm-writing-plans/CHANGELOG.md`
- Modify: `glm-skills/glm-systematic-debugging/SKILL.md`
- Modify: `glm-skills/glm-systematic-debugging/README.md`
- Modify: `glm-skills/glm-requirements-code-audit/SKILL.md`
- Test: `glm-skills/_shared/tests/test_model_terms_bodies.py`

- [ ] **Step 1: Write the failing test**

Create `glm-skills/_shared/tests/test_model_terms_bodies.py`:

```python
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as fh:
        return fh.read()


class BodyModelTerms(unittest.TestCase):
    def test_brainstorming_description_names_the_scope_and_stays_under_1024(self):
        text = read("glm-brainstorming", "SKILL.md")
        desc = text.split('description: "', 1)[1].split('"', 1)[0]
        self.assertIn("Claude Sonnet 5.5", desc)
        self.assertIn("pro tiers", desc)
        self.assertLessEqual(len(desc), 1024)

    def test_brainstorming_r2_and_r4_name_the_flash_tier(self):
        text = read("glm-brainstorming", "SKILL.md")
        self.assertIn("biggest speed lever on the flash tier", text)
        self.assertIn("GLM-5.3-Flash and DeepSeek V4.1 Flash emit fewer parallel tool calls", text)

    def test_dev_team_lane_table_uses_the_session_model(self):
        text = read("glm-dev-team", "SKILL.md")
        self.assertIn("| `glm-programmer-lite` | session model |", text)
        self.assertNotIn("| GLM-5.3-Flash |", text)
        self.assertIn("Claude Sonnet 5.5", text)

    def test_team_leader_names_the_session_model(self):
        text = read("glm-dev-team", "agents", "glm-team-leader.md")
        self.assertIn("the session model at high effort", text)
        self.assertIn("the session model at max effort", text)

    def test_writing_plans_lane_line_covers_pro_pins(self):
        text = read("glm-writing-plans", "SKILL.md")
        self.assertIn("the pin names a pro id (glm-5.3, deepseek-v4-pro)", text)
        self.assertNotIn("Never GLM-5.3, never deepseek-v4-pro", text)

    def test_debugging_metadata_lists_five_model_ids(self):
        text = read("glm-systematic-debugging", "SKILL.md")
        self.assertIn('models: "glm-5.3-flash | deepseek-flash | glm-5.3 | deepseek-v4-pro | claude-sonnet-5.5"', text)
        self.assertIn("Claude Sonnet 5.5 session keeps its own model", text)

    def test_debugging_readme_names_the_five_models(self):
        text = read("glm-systematic-debugging", "README.md")
        self.assertIn("DeepSeek V4 Pro and Claude Sonnet 5.5", text)

    def test_audit_metadata_and_pin_lines(self):
        text = read("glm-requirements-code-audit", "SKILL.md")
        self.assertIn("models: glm-5.3-flash | deepseek-flash | glm-5.3 | deepseek-v4-pro | claude-sonnet-5.5", text)
        self.assertIn("Tier never promotes a lane above the session model", text)

    def test_visual_companion_and_playbooks_use_tier_wording(self):
        vc = read("glm-brainstorming", "visual-companion.md")
        self.assertIn("GLM-5.3 sessions are text-only", vc)
        fan = read("glm-brainstorming", "fanout-playbook.md")
        self.assertIn("on the flash tier", fan)
        self.assertIn("flash-tier lanes", fan)
        res = read("glm-brainstorming", "research-playbook.md")
        self.assertIn("Do not promote a lane above the session model", res)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_model_terms_bodies.py -v`
Expected: FAILED (failures=9) — none of the tier phrases exist yet.

- [ ] **Step 3: Apply the fifteen file edits**

Each item below is an exact replace. Apply them in order.

1. In `glm-brainstorming/SKILL.md` frontmatter, replace `Tuned for GLM-5.3-Flash and DeepSeek V4.1 Flash.` with `Tuned for the GLM and DeepSeek flash and pro tiers and Claude Sonnet 5.5.` — every other description sentence unchanged.
2. In `glm-brainstorming/SKILL.md`, replace the heading `## R2 — Lane economics (biggest speed lever on GLM)` with `## R2 — Lane economics (biggest speed lever on the flash tier)`.
3. In `glm-brainstorming/SKILL.md` (R4 body), replace `Flash emits fewer parallel tool calls per turn unless given a` with `GLM-5.3-Flash and DeepSeek V4.1 Flash emit fewer parallel tool calls per turn unless given a` — the following sentence stays.
4. In `glm-dev-team/SKILL.md`, replace the Model cell `GLM-5.3-Flash` in each of the five lane-table rows with `session model`, and add this sentence directly under the table:

```markdown
The lane model is the session model - GLM-5.3-Flash or DeepSeek V4.1 Flash by default; a GLM 5.3, DeepSeek V4 Pro or Claude Sonnet 5.5 session runs its own model under the same effort rules.
```

5. In `glm-dev-team/SKILL.md`, replace `the retry runs on GLM-5.3-Flash)` with `the retry runs on the session model)`.
6. In `glm-dev-team/agents/glm-team-leader.md`, replace `(GLM-5.3-Flash, high effort)` with `(the session model at high effort)` and `(GLM-5.3-Flash, max effort)` with `(the session model at max effort)`.
7. In `glm-dev-team/agents/glm-team-leader.md`, replace `GLM-5.3-Flash at max, in one lane` with `the session model at max, in one lane`.
8. In `glm-writing-plans/SKILL.md`, replace the two-line lane guidance:

```markdown
   conversation uncached. The lane follows `~/.zcode/glm-flash`: GLM-5.3-Flash, or
   deepseek-flash. `GLM_FLASH` overrides one process. Never GLM-5.3, never deepseek-v4-pro, never effort low.
```

with:

```markdown
   conversation uncached. The lane follows the session model and the `~/.zcode/glm-flash` HTTP pin: GLM-5.3-Flash, or deepseek-flash, or the pin names a pro id (glm-5.3, deepseek-v4-pro) when the user pinned pro. `GLM_FLASH` overrides one process. Never promote a lane to another model, never effort low.
```

9. In `glm-systematic-debugging/SKILL.md`, replace `models: "glm-5.3-flash | deepseek-flash"` with `models: "glm-5.3-flash | deepseek-flash | glm-5.3 | deepseek-v4-pro | claude-sonnet-5.5"`.
10. In `glm-systematic-debugging/SKILL.md`, replace the model-and-effort sentence (the one starting `Every tier is`) with:

```markdown
Every tier follows the session model - GLM-5.3-Flash, or deepseek-flash when `~/.zcode/glm-flash` says deepseek; a glm-5.3, deepseek-v4-pro or Claude Sonnet 5.5 session keeps its own model (`GLM_FLASH` overrides one process). `light` and `std` are effort high. `deep` is effort max. Do not promote a lane above the session model, and do not lower effort to low or disabled.
```

The original sentence carries the same effort clauses after the pin clause; keep them in the replacement as shown.

11. In `glm-systematic-debugging/README.md`, replace `rebuilt for **GLM-5.3 / GLM-5.3-Flash** on **ZCode**.` with `rebuilt for **GLM-5.3, GLM-5.3-Flash, DeepSeek V4.1 Flash, DeepSeek V4 Pro and Claude Sonnet 5.5** on **ZCode**.` — and replace `GLM-5.3 emits only a couple of tool calls per turn` with `GLM-5.3 and the flash-tier models emit only a couple of tool calls per turn`.
12. In `glm-requirements-code-audit/SKILL.md`, apply three replaces. First the metadata line:

```markdown
models: glm-5.3-flash | deepseek-flash | glm-5.3 | deepseek-v4-pro | claude-sonnet-5.5
```

replacing `models: glm-5.3-flash | deepseek-flash`. Second the pin sentence (the one starting `**Both passes use the flash pin.**`) becomes:

```markdown
**Both passes use the flash pin.** The session model - GLM-5.3-Flash, or deepseek-flash when `~/.zcode/glm-flash` says deepseek, or the pro id the pin holds.
```

keeping the rest of that numbered item unchanged. Third, `Tier never selects GLM-5.3 or deepseek-v4-pro.` becomes `Tier never promotes a lane above the session model.`
13. In `glm-brainstorming/visual-companion.md`, replace `GLM-5.3 is text-only — do not send it images.` with `GLM-5.3 sessions are text-only — do not send them images.`
14. In `glm-brainstorming/fanout-playbook.md`, replace `up to 8 concurrent lanes on GLM (hard max 8)` with `up to 8 concurrent lanes on the flash tier (hard max 8)` — and replace `fan-out on GLM-5.3 lanes is not.` with `fan-out on flash-tier lanes is not.`
15. In `glm-brainstorming/research-playbook.md`, replace `Do not promote a lane to GLM-5.3.` with `Do not promote a lane above the session model.`

- [ ] **Step 4: Run the new test, the hygiene suite and the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_model_terms_bodies.py -v`
Expected: OK — Ran 9 tests.

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v`
Expected: OK — the frontmatter edits keep every skill loadable (description length, name checks).

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK.

- [ ] **Step 5: Changelog entries where a CHANGELOG.md exists**

In `glm-brainstorming/CHANGELOG.md` add a new top section (same shape as the existing numbered headings):

```markdown
# 9.7 (from 9.6) — five session models

SKILL.md, visual-companion.md and the two playbooks address the five session
models (GLM-5.3-Flash, DeepSeek V4.1 Flash, GLM 5.3, DeepSeek V4 Pro, Claude
Sonnet 5.5) by tier; the lane rule stays "follow the session model, never
promote a lane".
```

In `glm-writing-plans/CHANGELOG.md` add one entry of the existing `**Name (date):** body` shape:

```markdown
**Five session models (2026-11-19):** the lane line names the session model and the pro pin ids; no-promotion wording replaces the model denylist.
```

If `ls glm-dev-team/CHANGELOG.md` or `ls glm-requirements-code-audit/CHANGELOG.md` shows no such file, skip them silently.

- [ ] **Step 6: Commit**

```bash
git add glm-skills/glm-brainstorming/SKILL.md glm-skills/glm-brainstorming/visual-companion.md glm-skills/glm-brainstorming/research-playbook.md glm-skills/glm-brainstorming/fanout-playbook.md glm-skills/glm-brainstorming/CHANGELOG.md glm-skills/glm-dev-team/SKILL.md glm-skills/glm-dev-team/agents/glm-team-leader.md glm-skills/glm-writing-plans/SKILL.md glm-skills/glm-writing-plans/CHANGELOG.md glm-skills/glm-systematic-debugging/SKILL.md glm-skills/glm-systematic-debugging/README.md glm-skills/glm-requirements-code-audit/SKILL.md glm-skills/_shared/tests/test_model_terms_bodies.py
git commit -m "feat: tier wording for the five session models across bodies and agents"
```

---

### T04: install-all.sh — four-target installer front end [P]

**Depends:** —

**Interfaces:**
- Uses existing: `install-zcode.sh`
- Produces: `install-all.sh [--home DIR] [--dry-run] [--only zcode,agents,claude,opencode]`; `opencode/agents/`; `opencode/commands`; `.oc-major`

**Files:**
- Create: `glm-skills/install-all.sh`
- Modify: `glm-skills/install-zcode.sh`
- Test: `glm-skills/_shared/tests/test_install_all.py`
- Test: `glm-skills/_shared/tests/test_install_zcode.py` (one added method)

- [ ] **Step 1: Write the failing installer tests**

Create `glm-skills/_shared/tests/test_install_all.py` (following the temp-HOME idiom of `test_install_zcode.py`):

```python
import os
import shutil
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "..", "install-all.sh")
SKILLS = ("glm-brainstorming", "glm-dev-team", "glm-doc-generator", "glm-find-skills",
          "glm-git-diff-summary", "glm-idea-to-spec", "glm-requirements-code-audit",
          "glm-systematic-debugging", "glm-video-shotcraft", "glm-viral-video-studio",
          "glm-writing-plans")


class InstallAllTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="install-all-")
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        self.env = dict(os.environ, HOME=self.home,
                        XDG_CONFIG_HOME=os.path.join(self.home, ".config"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_script(self, *args):
        return subprocess.run(["sh", SCRIPT, "--home", self.home] + list(args),
                              capture_output=True, text=True, timeout=300, env=self.env,
                              cwd=os.path.join(HERE, "..", ".."))

    def skill_dir(self, target, skill):
        return os.path.join(self.home, target, skill)

    def test_dry_run_writes_nothing(self):
        r = self.run_script("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".agents")))

    def test_plain_targets_get_every_skill_as_is(self):
        r = self.run_script("--only", "agents,claude")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for target in (".agents/skills", ".claude/skills"):
            for skill in SKILLS:
                d = self.skill_dir(target, skill)
                self.assertTrue(os.path.isfile(os.path.join(d, "SKILL.md")), d)
            self.assertTrue(os.path.isfile(os.path.join(self.skill_dir(target, "glm-brainstorming"),
                                                       "agents", "glm-explorer.md")))
            self.assertFalse(os.path.exists(os.path.join(self.home, target, "glm-brainstorming",
                                                         "__pycache__")))

    def test_opencode_target_moves_agents_and_bumps_oc_major(self):
        oc = os.path.join(self.home, ".config", "opencode", "skills", "glm-brainstorming")
        os.makedirs(oc)
        with open(os.path.join(oc, ".oc-major"), "w", encoding="utf-8") as fh:
            fh.write("2\n")
        cmds = os.path.join(oc, "opencode", "commands")
        os.makedirs(cmds)
        with open(os.path.join(cmds, "glm-brainstorm.md"), "w", encoding="utf-8") as fh:
            fh.write("preserved opencode body\n")
        r = self.run_script("--only", "opencode")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(oc, "opencode", "agents", "glm-explorer.md")))
        self.assertFalse(os.path.exists(os.path.join(oc, "agents")))
        with open(os.path.join(oc, ".oc-major"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "3")
        with open(os.path.join(cmds, "glm-brainstorm.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "preserved opencode body\n")
        for skill in SKILLS:
            self.assertTrue(os.path.isfile(os.path.join(self.home, ".config", "opencode",
                                                        "skills", skill, "SKILL.md")))

    def test_fresh_opencode_install_writes_oc_major_one(self):
        r = self.run_script("--only", "opencode")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(self.home, ".config", "opencode", "skills", "glm-dev-team",
                               ".oc-major"), encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "1")

    def test_non_glm_folders_are_untouched(self):
        keep = os.path.join(self.home, ".config", "opencode", "skills", "oc-brainstorming")
        os.makedirs(keep)
        with open(os.path.join(keep, "SKILL.md"), "w", encoding="utf-8") as fh:
            fh.write("keep me\n")
        r = self.run_script("--only", "opencode")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(keep, "SKILL.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "keep me\n")

    def test_first_target_delegation_installs_skills(self):
        r = self.run_script("--only", "zcode")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.home, ".zcode", "skills",
                                                    "glm-brainstorming", "SKILL.md")))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_install_all.py -v`
Expected: FAILED (errors) — `install-all.sh` does not exist (`No such file or directory`).

- [ ] **Step 3: Create install-all.sh**

Create `glm-skills/install-all.sh`:

```sh
#!/bin/sh
# Install every glm-* skill folder that has SKILL.md at its root into the
# four harness skill targets:
#   zcode    delegates to install-zcode.sh (skills, agents, commands,
#            manifest, flash pin) - unchanged
#   agents   <home>/.agents/skills/<name>/        folder as-is minus junk
#   claude   <home>/.claude/skills/<name>/        folder as-is minus junk
#   opencode ${XDG_CONFIG_HOME:-<home>/.config}/opencode/skills/<name>/
#            folder with agents/ placed under opencode/agents/, existing
#            opencode/commands/*.md bodies preserved verbatim (opencode
#            prose is not derivable from the repo commands), .oc-major
#            bumped per skill (1 when absent)
#
# Usage: sh install-all.sh [--home DIR] [--dry-run] [--only zcode,agents,claude,opencode]
# Non-glm-* folders inside a target are never touched.
set -eu

HOME_DIR="${HOME:-}"
DRY=0
ONLY="zcode,agents,claude,opencode"

while [ $# -gt 0 ]; do
    case "$1" in
        --home) [ $# -ge 2 ] || { echo "Error: --home needs a value" >&2; exit 1; }; HOME_DIR="$2"; shift 2 ;;
        --dry-run) DRY=1; shift ;;
        --only) [ $# -ge 2 ] || { echo "Error: --only needs a value" >&2; exit 1; }; ONLY="$2"; shift 2 ;;
        *) echo "Usage: $0 [--home DIR] [--dry-run] [--only zcode,agents,claude,opencode]" >&2; exit 1 ;;
    esac
done

case ",$ONLY," in
    *,zcode,*|*,agents,*|*,claude,*|*,opencode,*) ;;
    *) echo "Error: --only must name zcode, agents, claude, opencode or a comma list" >&2; exit 1 ;;
esac

[ -n "$HOME_DIR" ] || { echo "Error: HOME is unset; pass --home DIR" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OC_ROOT="${XDG_CONFIG_HOME:-$HOME_DIR/.config}/opencode/skills"

command -v python3 >/dev/null 2>&1 || { echo "Error: python3 not found" >&2; exit 1; }

run() { if [ "$DRY" -eq 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

has() { case ",$ONLY," in *,"$1",*) return 0 ;; *) return 1 ;; esac; }

FOLDERS=$(
    for d in "$SCRIPT_DIR"/glm-*; do
        [ -d "$d" ] || continue
        [ -f "$d/SKILL.md" ] || continue
        basename "$d"
    done | sort | tr '\n' ' '
)
FOLDERS=${FOLDERS%" "}
[ -n "$FOLDERS" ] || { echo "Error: no glm-*/SKILL.md folders under $SCRIPT_DIR" >&2; exit 1; }

clean_junk() {
    find "$1" \( -name opencode -o -name .DS_Store -o -name .idea -o -name __pycache__ -o -name '*.pyc' \) -prune -exec rm -rf {} +
}

# Preflight, and the first target: reuse install-zcode.sh end to end.
if has zcode; then
    echo "== zcode target (install-zcode.sh)"
    if [ "$DRY" -eq 1 ]; then
        sh "$SCRIPT_DIR/install-zcode.sh" --home "$HOME_DIR" --dry-run >/dev/null
        echo "[dry-run] delegated to install-zcode.sh"
    else
        sh "$SCRIPT_DIR/install-zcode.sh" --home "$HOME_DIR"
    fi
elif [ "$DRY" -eq 1 ]; then
    sh "$SCRIPT_DIR/install-zcode.sh" --home "$HOME_DIR" --dry-run >/dev/null
fi

# Two plain targets: the skill folder as-is, minus junk.
for T in agents:.agents/skills claude:.claude/skills; do
    LABEL=${T%%:*}
    DIR=${T#*:}
    has "$LABEL" || continue
    DEST_ROOT="$HOME_DIR/$DIR"
    echo "== $LABEL target: $DEST_ROOT"
    run mkdir -p "$DEST_ROOT"
    n=0
    for folder in $FOLDERS; do
        dest="$DEST_ROOT/$folder"
        run rm -rf "$dest"
        run mkdir -p "$dest"
        if [ "$DRY" -eq 0 ]; then
            cp -R "$SCRIPT_DIR/$folder/." "$dest/"
            clean_junk "$dest"
            n=$((n + 1))
        fi
        echo "  $folder/"
    done
    [ "$DRY" -eq 1 ] || echo "  $n skills -> $DEST_ROOT"
done

# opencode: agents under opencode/, preserved opencode/commands, bumped .oc-major.
if has opencode; then
    echo "== opencode target: $OC_ROOT"
    run mkdir -p "$OC_ROOT"
    n=0
    for folder in $FOLDERS; do
        dest="$OC_ROOT/$folder"
        old_cmds=""
        old_major=""
        if [ -d "$dest/opencode/commands" ]; then
            old_cmds=$(mktemp -d "${TMPDIR:-/tmp}/occmds.XXXXXX")
            cp -R "$dest/opencode/commands/." "$old_cmds/"
        fi
        if [ -f "$dest/.oc-major" ]; then
            old_major=$(awk 'NF { print ($1 ~ /^[0-9]+$/) ? $1 + 1 : 1; exit }' "$dest/.oc-major")
        fi
        if [ "$DRY" -eq 0 ]; then
            rm -rf "$dest"
            mkdir -p "$dest"
            cp -R "$SCRIPT_DIR/$folder/." "$dest/"
            clean_junk "$dest"
            mkdir -p "$dest/opencode/agents"
            if [ -d "$SCRIPT_DIR/$folder/agents" ]; then
                cp -R "$SCRIPT_DIR/$folder/agents/." "$dest/opencode/agents/"
            fi
            rm -rf "$dest/agents"
            if [ -n "$old_cmds" ]; then
                mkdir -p "$dest/opencode/commands"
                cp -R "$old_cmds/." "$dest/opencode/commands/"
                rm -rf "$old_cmds"
            fi
            printf '%s\n' "${old_major:-1}" > "$dest/.oc-major"
            n=$((n + 1))
        else
            echo "[dry-run] $folder/ (agents -> opencode/agents, major=${old_major:-1})"
        fi
    done
    [ "$DRY" -eq 1 ] || echo "  $n skills -> $OC_ROOT"
fi

echo "== done ($ONLY)"
[ "$DRY" -eq 1 ] && echo "Dry run. Nothing written."
exit 0
```

- [ ] **Step 4: Widen the saved-pin case in `install-zcode.sh`**

In `glm-skills/install-zcode.sh`, find the saved-pin case (the block reading `$HOME_DIR/.zcode/glm-flash` when `FLASH_EXPLICIT` is 0). Replace its two arms:

```sh fragment
        deepseek|ds|deepseek-flash) FLASH=deepseek ;;
        glm|glm-5.3-flash|flash) FLASH=glm ;;
```

with:

```sh fragment
        deepseek|ds|deepseek-flash|deepseek-v4-pro) FLASH=deepseek ;;
        glm|glm-5.3-flash|flash|glm-5.3) FLASH=glm ;;
```

- [ ] **Step 5: Add the saved-pro-pin test to test_install_zcode.py**

In `glm-skills/_shared/tests/test_install_zcode.py`, inside the class that holds `test_reinstall_keeps_deepseek_pin_and_glm_flag_reverts_it`, add one method in the same helper style as its neighbors (the requirement changed: the pin file may now hold a pro word):

```python
    def test_saved_pro_pin_word_keeps_its_provider(self):
        r = self.install()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        pin = os.path.join(self.home, ".zcode", "glm-flash")
        with open(pin, "w", encoding="utf-8") as fh:
            fh.write("deepseek-v4-pro\n")
        r2 = self.install()
        self.assertEqual(r2.returncode, 0, r2.stdout + r2.stderr)
        with open(pin, encoding="utf-8") as fh:
            self.assertEqual(fh.read().strip(), "deepseek")
        r3 = self.install()
        self.assertEqual(r3.returncode, 0, r3.stdout + r3.stderr)
        self.assertIn("pin: deepseek", r3.stdout)
```

- [ ] **Step 6: Run the installer tests and the full suite**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_install_all.py -v`
Expected: OK — Ran 6 tests.

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_install_zcode.py -v`
Expected: OK — the added method passes, no existing test changes outcome.

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK.

- [ ] **Step 7: Commit**

```bash
git add glm-skills/install-all.sh glm-skills/install-zcode.sh glm-skills/_shared/tests/test_install_all.py glm-skills/_shared/tests/test_install_zcode.py
git commit -m "feat: install-all.sh front end for the four harness targets"
```

---

### T05: integration — suites, real install, final commit

**Depends:** T01, T02, T03, T04

**Interfaces:**
- Consumes: `GUARD flash`; `handoff.py`; `_name`; `deepseek-v4-pro`; `glm-5.3`; `pin_word(home=None)`; `PRO_API`; `resolve_http_model`; `description`; `models`; `install-all.sh [--home DIR] [--dry-run] [--only zcode,agents,claude,opencode]`; `opencode/agents/`; `opencode/commands`; `.oc-major`
- Produces: `install-all.sh`

**Files:**
- Modify: `glm-skills/docs/specs/2026-11-19-five-models-four-targets.md`
- Modify: `glm-skills/docs/plans/2026-11-19-five-models-four-targets.md`

A T01-T04 repair may leave other files modified; those are added by exact path in Step 4.

- [ ] **Step 1: Full suite and engine self-test on merged main**

Run: `cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK — zero failures, zero errors.

Run: `cd glm-skills && bash glm-dev-team/scripts/selftest.sh`
Expected: the script's usual pass set with no new failures; any pre-existing failure is reported as-is and not fixed.

- [ ] **Step 2: Dry-run the installer, then run it for real**

Run: `cd glm-skills && sh install-all.sh --dry-run | tail -5`
Expected: `Dry run. Nothing written.` plus one dry-run line per skill per target; exit 0.

Run: `cd glm-skills && sh install-all.sh | tail -8`
Expected: `== done (zcode,agents,claude,opencode)` and per-target skill counts (11 per copy target; the delegated target prints its own summary); exit 0.

- [ ] **Step 3: Verify the four installed targets**

Run: `for t in ~/.agents/skills ~/.claude/skills ~/.config/opencode/skills ~/.zcode/skills; do echo "$t: $(ls -d $t/glm-* 2>/dev/null | wc -l | tr -d ' ') skills"; done`
Expected: `11` for each of the four targets.

Run: `ls ~/.config/opencode/skills/glm-brainstorming/opencode/agents/ && cat ~/.config/opencode/skills/glm-brainstorming/.oc-major`
Expected: four agent files (`glm-design-breaker`, `glm-drafter`, `glm-explorer`, `glm-researcher`) and the bumped major (3 if it was 2).

Run: `diff -rq glm-brainstorming ~/.agents/skills/glm-brainstorming | grep -v "Only in glm-brainstorming" | head`
Expected: no content differences other than repo-side junk entries (`.DS_Store`, `__pycache__`); the command bodies under `~/.zcode` differ by design (the skill-dir placeholder is filled there).

- [ ] **Step 4: Final commit of the design and plan documents**

From the repository root, with `git status` showing only this task's remaining files:

```bash
git add glm-skills/docs/specs/2026-11-19-five-models-four-targets.md glm-skills/docs/plans/2026-11-19-five-models-four-targets.md
git commit -m "docs: five-models four-targets spec and plan"
```

If `git status` lists any other modified tracked file left by a T01-T04 repair, add each by exact path in the same commit and name it in the commit body.

**Engine block**

```json
{"request": "Five session models in the skill model layer; install all eleven skills into the four harness targets",
 "profile": "balanced",
 "glm": {"tier": "api"},
 "commands": {"build": "none",
              "test": "cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests",
              "test_file": "cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest {files}",
              "lint": "none", "lint_file": "none", "typecheck": "none", "typecheck_file": "none",
              "bench": "none"},
 "contracts": ["C1 flash_pin pin vocabulary: pin_word(home=None) returns the raw pin word and the pro words deepseek-v4-pro and glm-5.3 map to their providers - established in S1, consumed by the S4 installer case arms"],
 "notes": "Work on main. stdlib-only. After editing _shared scripts run sh _shared/sync.sh from glm-skills and commit the vendored copies in the same slice. SKILL.md description stays at 1024 chars or fewer with the WHEN clause in the first 250; re-run test_all_skills.py after every frontmatter edit. No numeric speed or price claims for the non-flash session models. Installer tests use a temp HOME only; the real four-target install runs in S5. Full suite: cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests. BASELINE (2026-11-19): three pre-existing failures were repaired on main before this run (audit.py settled-row re-verify, architectural.md TaskStop note, test_team_leader_memory stale model key) so the full gate is green at the base commit; no known baseline failures remain.",
 "test_globs": ["glm-skills/_shared/tests/test_*.py"],
 "slices": [
   {"id": "S1", "title": "shared model layer: five-model GUARD line and pro pin words", "goal": "GUARD flash names the five session models; flash_pin accepts the pro pin words and resolves the pro API id; zai_client docstring notes the five models; vendored copies re-synced", "kind": "code",
    "size": "small", "deps": [], "files": ["glm-skills/_shared/handoff.py", "glm-skills/_shared/flash_pin.py", "glm-skills/_shared/zai_client.py", "glm-skills/_shared/tests/test_flash_pin_pro.py", "glm-skills/glm-brainstorming/scripts/handoff.py", "glm-skills/glm-dev-team/scripts/handoff.py", "glm-skills/glm-dev-team/scripts/flash_pin.py", "glm-skills/glm-doc-generator/scripts/handoff.py", "glm-skills/glm-git-diff-summary/scripts/handoff.py", "glm-skills/glm-idea-to-spec/scripts/handoff.py", "glm-skills/glm-requirements-code-audit/scripts/handoff.py", "glm-skills/glm-requirements-code-audit/scripts/flash_pin.py", "glm-skills/glm-requirements-code-audit/scripts/zai_client.py", "glm-skills/glm-systematic-debugging/scripts/handoff.py", "glm-skills/glm-systematic-debugging/scripts/flash_pin.py", "glm-skills/glm-systematic-debugging/scripts/zai_client.py", "glm-skills/glm-writing-plans/scripts/handoff.py", "glm-skills/glm-writing-plans/scripts/flash_pin.py", "glm-skills/glm-writing-plans/scripts/zai_client.py"],
    "risk": "low", "isolation": false,
    "criteria": ["test_flash_pin_pro.py green: pro words map to providers, pin_word returns raw word, pro pin resolves the pro API id, guard names all five models", "sh _shared/sync.sh leaves every vendored copy byte-identical (test_vendored green)", "full suite green"],
    "edge_cases": ["empty GLM_FLASH", "unknown pin word falls back to glm with no crash", "pin file absent", "flash pin keeps today behavior unchanged"],
    "context": ["glm-skills/_shared/flash_pin.py", "glm-skills/_shared/handoff.py"], "verify": ""},
   {"id": "S2", "title": "four tuning docs: session-model tier block", "goal": "Every tuning doc names the five session models by tier; the economics table stops marking the pro row not used; denylist sentences become no-promotion wording", "kind": "code",
    "size": "small", "deps": [], "files": ["glm-skills/glm-brainstorming/glm-tuning.md", "glm-skills/glm-writing-plans/references/glm-tuning.md", "glm-skills/glm-requirements-code-audit/references/glm-tuning.md", "glm-skills/glm-systematic-debugging/references/glm-tuning.md", "glm-skills/_shared/tests/test_model_terms_tuning.py"],
    "risk": "low", "isolation": false,
    "criteria": ["test_model_terms_tuning.py green: five model names and three tier words in each of the four docs, no numeric table rows for the new tiers", "full suite green"],
    "edge_cases": ["doc with a pre-existing table row that must not gain numbers", "denylist sentence appears more than once in a copy"],
    "context": ["glm-skills/glm-brainstorming/glm-tuning.md"], "verify": ""},
   {"id": "S3", "title": "bodies and agents: tier wording sweep", "goal": "Model-naming lines address flash, pro and Claude-tier sessions truthfully; description stays under 1024 chars; metadata models lines list all five ids", "kind": "code",
    "size": "small", "deps": [], "files": ["glm-skills/glm-brainstorming/SKILL.md", "glm-skills/glm-brainstorming/visual-companion.md", "glm-skills/glm-brainstorming/research-playbook.md", "glm-skills/glm-brainstorming/fanout-playbook.md", "glm-skills/glm-brainstorming/CHANGELOG.md", "glm-skills/glm-dev-team/SKILL.md", "glm-skills/glm-dev-team/agents/glm-team-leader.md", "glm-skills/glm-writing-plans/SKILL.md", "glm-skills/glm-writing-plans/CHANGELOG.md", "glm-skills/glm-systematic-debugging/SKILL.md", "glm-skills/glm-systematic-debugging/README.md", "glm-skills/glm-requirements-code-audit/SKILL.md", "glm-skills/_shared/tests/test_model_terms_bodies.py"],
    "risk": "low", "isolation": false,
    "criteria": ["test_model_terms_bodies.py green (9 tests)", "test_all_skills.py green after the frontmatter edits", "full suite green"],
    "edge_cases": ["description near the 1024 char ceiling", "frontmatter metadata lines stay flat", "CHANGELOG absent folders skipped silently"],
    "context": ["glm-skills/glm-dev-team/SKILL.md"], "verify": ""},
   {"id": "S4", "title": "install-all.sh four-target installer front end", "goal": "install-all.sh installs every skill into the four targets with per-target layout rules and dry-run; install-zcode.sh saved-pin case accepts the pro words", "kind": "code",
    "size": "small", "deps": [], "files": ["glm-skills/install-all.sh", "glm-skills/install-zcode.sh", "glm-skills/_shared/tests/test_install_all.py", "glm-skills/_shared/tests/test_install_zcode.py"],
    "risk": "low", "isolation": false,
    "criteria": ["test_install_all.py green (6 tests, temp HOME only)", "test_install_zcode.py green including the new saved-pro-pin method", "full suite green"],
    "edge_cases": ["dry-run writes nothing", "existing opencode command bodies preserved verbatim", ".oc-major bumped or written as 1", "non-glm folders untouched", "missing target dirs created"],
    "context": ["glm-skills/install-zcode.sh"], "verify": ""},
   {"id": "S5", "title": "integration: suites, real install, final commit", "goal": "Full suite plus engine self-test green on merged main; install-all.sh run for real against the four home targets and verified; design and plan documents committed", "kind": "chore",
    "size": "small", "deps": ["S1", "S2", "S3", "S4"], "files": ["glm-skills/docs/specs/2026-11-19-five-models-four-targets.md", "glm-skills/docs/plans/2026-11-19-five-models-four-targets.md"],
    "risk": "low", "isolation": false,
    "criteria": ["full suite green", "each of the four targets holds all eleven skills", "opencode brainstorming shows four agents and a bumped major", "final commit staged by exact path"],
    "edge_cases": ["pre-existing self-test failures reported, not fixed", "git status leftovers added by exact path"],
    "context": ["glm-skills/install-all.sh"],
    "verify": "cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests && sh install-all.sh --dry-run"}
]}
```
