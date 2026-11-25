# Six Session Models and Full Audit Implementation Plan

> **Execution note:** This plan is self-contained and tool-agnostic. Any AI
> agent or human engineer can execute it with only a shell, a code editor, and
> git. Follow the Execution Protocol below.

**Goal:** Make every non-video skill name and address six session models - GLM 5.4 (id glm-5.4, pro tier) joins the five - with no stale or false statement, and fix the defects the audit of those skills found.

**Out of scope:** The two video skills, the sibling repos, the vendored gamedev bundle and .audit, a new provider route for Claude, a benchmark harness, decide.py scoring, check.py gates and the dev-team guard hooks; any new feature or redesign (reported with a recommendation instead).

**Rollback:** git revert the task commits in reverse order; no migration, no data change, no install step.

**Architecture:** Two existing layers are widened. The shared model layer (handoff GUARD line, pin vocabulary, client docstring) learns glm-5.4 and is re-vendored by _shared/sync.sh. The vocabulary pivot changes every enumeration, every pinned sentence and the three test modules that pin them in one commit, because each of those tests reads files across several skills. Per-skill defects (installer pin write-back, engine and doctor output, broken references, audit findings) are separate tasks, each with a reproducing test.

**Tech Stack:** Python 3 standard library only, POSIX sh, unittest, Markdown.

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

- stdlib-only Python 3 + POSIX sh; no new dependency, no package manager; pytest is not installed, use unittest.
- Run every suite command from inside z-skills; work on main; never create a branch.
- `git add` names exact paths from the task's Files list only, never `.` or `-A`; exactly one `git commit` per task.
- Every SKILL.md edit keeps frontmatter `name` equal to the directory name, `description` at 1024 characters or fewer with the WHEN clause inside the first 250 characters, and the body under 500 lines.
- Agent files carry no model id and keep their `thoughtLevel` line; no lane is ever promoted to another model.
- No speed or price number is added for GLM 5.4, DeepSeek V4 Pro or Claude Sonnet 5.5.
- After any edit to _shared/handoff.py, _shared/flash_pin.py or _shared/zai_client.py, run `sh _shared/sync.sh` from z-skills and commit the vendored copies in the same task.
- A test assertion is edited only where a task says so, and the reason is always the changed requirement (five ids became six); no test is deleted, skipped or loosened.
- New text in non-Markdown files is plain ASCII English; Markdown files keep the characters they already use.
- Full suite, run from z-skills: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
- Hygiene suite, run from z-skills: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py`

## References

- `z-skills/_shared/tests/test_flash_pin_pro.py` - the pin-test idiom: the `z-skills/_env` context manager, the `z-skills/_pin_home` helper, assertions on provider and resolve.
- `z-skills/_shared/tests/test_install_zcode.py` - the installer-test idiom: a temp HOME per test, `z-skills/self.install(*args)`, assertions on the installed tree and the pin file.

## File Structure

- `z-skills/_shared/` — handoff.py (T01), flash_pin.py (T01), zai_client.py (T01)
- `z-skills/_shared/tests/` — test_flash_pin_pro.py (T01), test_all_skills.py (T02), test_model_terms_bodies.py (T02), test_model_terms_tuning.py (T02), test_install_zcode.py (T03), test_devteam_wording.py (T04), test_plan_doctor.py (T05), test_skill_references.py (T06)
- `z-skills/z-brainstorming/scripts/` — handoff.py (T01)
- `z-skills/z-dev-team/scripts/` — handoff.py (T01), flash_pin.py (T01), devteam.py (T04), selftest.sh (T04)
- `z-skills/z-doc-generator/scripts/` — handoff.py (T01)
- `z-skills/z-git-diff-summary/scripts/` — handoff.py (T01)
- `z-skills/z-idea-to-spec/scripts/` — handoff.py (T01)
- `z-skills/z-requirements-code-audit/scripts/` — handoff.py (T01), flash_pin.py (T01), zai_client.py (T01)
- `z-skills/z-systematic-debugging/scripts/` — handoff.py (T01), flash_pin.py (T01), zai_client.py (T01)
- `z-skills/z-writing-plans/scripts/` — handoff.py (T01), flash_pin.py (T01), zai_client.py (T01), plan_tool.py (T05)
- `z-skills/` — AGENTS.md (T02), install-zcode.sh (T03)
- `z-skills/z-brainstorming/` — SKILL.md (T02), z-tuning.md (T02), visual-companion.md (T02), CHANGELOG.md (T02)
- `z-skills/z-dev-team/` — SKILL.md (T02)
- `z-skills/z-doc-generator/` — SKILL.md (T02)
- `z-skills/z-find-skills/` — SKILL.md (T02)
- `z-skills/z-git-diff-summary/` — SKILL.md (T02)
- `z-skills/z-idea-to-spec/` — SKILL.md (T02)
- `z-skills/z-requirements-code-audit/` — SKILL.md (T02)
- `z-skills/z-systematic-debugging/` — SKILL.md (T02), README.md (T02)
- `z-skills/z-writing-plans/` — SKILL.md (T02), CHANGELOG.md (T02)
- `z-skills/z-writing-plans/references/` — z-tuning.md (T02)
- `z-skills/z-requirements-code-audit/references/` — z-tuning.md (T02)
- `z-skills/z-systematic-debugging/references/` — z-tuning.md (T02)
- `z-skills/z-brainstorming/agents/` — z-drafter.md (T02), z-design-breaker.md (T02)

## Contracts

#### T01: shared model layer - six-model GUARD line and the glm-5.4 pro pin word
- Files: `z-skills/_shared/handoff.py`, `z-skills/_shared/flash_pin.py`, `z-skills/_shared/zai_client.py`, `z-skills/_shared/tests/test_flash_pin_pro.py`, `z-skills/z-brainstorming/scripts/handoff.py`, `z-skills/z-dev-team/scripts/handoff.py`, `z-skills/z-dev-team/scripts/flash_pin.py`, `z-skills/z-doc-generator/scripts/handoff.py`, `z-skills/z-git-diff-summary/scripts/handoff.py`, `z-skills/z-idea-to-spec/scripts/handoff.py`, `z-skills/z-requirements-code-audit/scripts/handoff.py`, `z-skills/z-requirements-code-audit/scripts/flash_pin.py`, `z-skills/z-requirements-code-audit/scripts/zai_client.py`, `z-skills/z-systematic-debugging/scripts/handoff.py`, `z-skills/z-systematic-debugging/scripts/flash_pin.py`, `z-skills/z-systematic-debugging/scripts/zai_client.py`, `z-skills/z-writing-plans/scripts/handoff.py`, `z-skills/z-writing-plans/scripts/flash_pin.py`, `z-skills/z-writing-plans/scripts/zai_client.py`
- Produces: `"glm-5.4": "glm-5.4",`; `"flash", "glm-5.3", "glm-5.4"):`; `GLM 5.3, GLM 5.4, DeepSeek V4 Pro, or Claude Sonnet 5.5.`; `DeepSeek V4.1 Flash, GLM 5.3, GLM 5.4, DeepSeek V4 Pro, Claude Sonnet 5.5.`; `def test_glm_5_4_pro_pin_resolves_the_glm_5_4_api_id_for_every_model(self):`
- Consumes: `from_env` (existing), `from_file` (existing), `resolve_http_model` (existing), `GUARDS` (existing)
- Read: `z-skills/_shared/flash_pin.py`, `z-skills/_shared/handoff.py`, `z-skills/_shared/zai_client.py`
- Spec: L1-7, L18, L26-27, L37-38, L40, L56-57, L59-60, L82-90, L98-102, L105, L109-125
- Tier: std

#### T02: vocabulary pivot - every enumeration, pinned sentence and its tests
- Files: `z-skills/AGENTS.md`, `z-skills/z-brainstorming/SKILL.md`, `z-skills/z-dev-team/SKILL.md`, `z-skills/z-doc-generator/SKILL.md`, `z-skills/z-find-skills/SKILL.md`, `z-skills/z-git-diff-summary/SKILL.md`, `z-skills/z-idea-to-spec/SKILL.md`, `z-skills/z-requirements-code-audit/SKILL.md`, `z-skills/z-systematic-debugging/SKILL.md`, `z-skills/z-writing-plans/SKILL.md`, `z-skills/z-brainstorming/z-tuning.md`, `z-skills/z-writing-plans/references/z-tuning.md`, `z-skills/z-requirements-code-audit/references/z-tuning.md`, `z-skills/z-systematic-debugging/references/z-tuning.md`, `z-skills/z-systematic-debugging/README.md`, `z-skills/z-brainstorming/visual-companion.md`, `z-skills/z-brainstorming/agents/z-drafter.md`, `z-skills/z-brainstorming/agents/z-design-breaker.md`, `z-skills/z-brainstorming/CHANGELOG.md`, `z-skills/z-writing-plans/CHANGELOG.md`, `z-skills/_shared/tests/test_all_skills.py`, `z-skills/_shared/tests/test_model_terms_bodies.py`, `z-skills/_shared/tests/test_model_terms_tuning.py`
- Produces: `SIX_ID_LINE = ("glm-5.3-flash | deepseek-flash | glm-5.3 | glm-5.4"`; `PRO_PIN_CLAUSE = "the pin names a pro id (glm-5.3, glm-5.4, deepseek-v4-pro)"`; `KEEPS_OWN_MODEL_CLAUSE = "a glm-5.3, glm-5.4, deepseek-v4-pro or Claude Sonnet 5.5 session keeps its own model"`; `| GLM 5.4 | pro tier |`; `def test_every_skill_doc_names_glm_5_4_where_it_lists_the_other_models(self):`
- Read: `z-skills/_shared/tests/test_model_terms_bodies.py`, `z-skills/_shared/tests/test_model_terms_tuning.py`, `z-skills/_shared/tests/test_all_skills.py`
- Spec: L8-17, L21-25, L28-35, L46-55, L58, L64-67, L72-81, L103-104, L106-108
- Tier: light

#### T03: installer keeps a saved pro pin word and learns glm-5.4
- Files: `z-skills/install-zcode.sh`, `z-skills/_shared/tests/test_install_zcode.py`
- Produces: `PIN="$FLASH"`; `glm|glm-5.3-flash|flash|glm-5.3|glm-5.4) FLASH=glm ;;`; `def test_saved_glm_5_4_pin_word_keeps_the_glm_provider_and_the_word(self):`
- Read: `z-skills/install-zcode.sh`, `z-skills/_shared/tests/test_install_zcode.py`
- Spec: L39, L61-63, L91-94
- Tier: std

#### T04: dev-team engine prints routing that follows the session model
- Files: `z-skills/z-dev-team/scripts/devteam.py`, `z-skills/z-dev-team/scripts/selftest.sh`, `z-skills/_shared/tests/test_devteam_wording.py`
- Produces: `class EngineRoutingText(unittest.TestCase):`; `every lane follows the session model`
- Read: `z-skills/z-dev-team/scripts/devteam.py`
- Spec: L41-44, L68-70
- Tier: light

#### T05: plan tool doctor prints the effort each tier sets
- Files: `z-skills/z-writing-plans/scripts/plan_tool.py`, `z-skills/_shared/tests/test_plan_doctor.py`
- Produces: `class DoctorModelsRow(unittest.TestCase):`; `"models    : light=%s/%s  std=%s/%s  deep=%s/%s" % (`
- Read: `z-skills/z-writing-plans/scripts/plan_tool.py`
- Spec: L45, L71
- Tier: std

#### T06: guard against broken bundled-path references in every skill
- Files: `z-skills/_shared/tests/test_skill_references.py`
- Produces: `def missing_references(skill_root, text):`; `class TreeTests(unittest.TestCase):`
- Spec: L19-20, L95-97
- Tier: std

<!-- WAVES -->
## Execution Waves

Every task in a wave has all its Depends/Runs-after tasks in earlier waves. Tasks in the
same wave touch disjoint files, so a wave's `[P]` tasks may all run at once.

- **Wave 1:** T01 [P], T02 [P], T03 [P], T04 [P], T05 [P], T06 [P]
<!-- /WAVES -->

<!-- TASKS -->

### T01: shared model layer - six-model GUARD line and the glm-5.4 pro pin word [P]

**Depends:** —

**Interfaces:**
- Uses existing: `from_env`; `from_file`; `resolve_http_model`; `GUARDS`
- Produces: `"glm-5.4": "glm-5.4",`; `"flash", "glm-5.3", "glm-5.4"):`; `GLM 5.3, GLM 5.4, DeepSeek V4 Pro, or Claude Sonnet 5.5.`; `DeepSeek V4.1 Flash, GLM 5.3, GLM 5.4, DeepSeek V4 Pro, Claude Sonnet 5.5.`; `def test_glm_5_4_pro_pin_resolves_the_glm_5_4_api_id_for_every_model(self):`

**Files:**
- Modify: `z-skills/_shared/handoff.py`
- Modify: `z-skills/_shared/flash_pin.py`
- Modify: `z-skills/_shared/zai_client.py`
- Test: `z-skills/_shared/tests/test_flash_pin_pro.py`
- Modify: `z-skills/z-brainstorming/scripts/handoff.py`
- Modify: `z-skills/z-dev-team/scripts/handoff.py`
- Modify: `z-skills/z-dev-team/scripts/flash_pin.py`
- Modify: `z-skills/z-doc-generator/scripts/handoff.py`
- Modify: `z-skills/z-git-diff-summary/scripts/handoff.py`
- Modify: `z-skills/z-idea-to-spec/scripts/handoff.py`
- Modify: `z-skills/z-requirements-code-audit/scripts/handoff.py`
- Modify: `z-skills/z-requirements-code-audit/scripts/flash_pin.py`
- Modify: `z-skills/z-requirements-code-audit/scripts/zai_client.py`
- Modify: `z-skills/z-systematic-debugging/scripts/handoff.py`
- Modify: `z-skills/z-systematic-debugging/scripts/flash_pin.py`
- Modify: `z-skills/z-systematic-debugging/scripts/zai_client.py`
- Modify: `z-skills/z-writing-plans/scripts/handoff.py`
- Modify: `z-skills/z-writing-plans/scripts/flash_pin.py`
- Modify: `z-skills/z-writing-plans/scripts/zai_client.py`

Every edit script in this plan reads a file, requires the old text to appear exactly once, replaces it and writes the file back; it stops with a message when an anchor is missing. Run a script from the repository root with `cd z-skills && python3 - <<'PY'`, paste the block, and close it with a line that holds only `PY`.

- [x] **Step 1: Move the pin tests to six models**

```python
import io

EDITED = 0


def edit(path, old, new):
    global EDITED
    with io.open(path, encoding="utf-8") as fh:
        text = fh.read()
    found = text.count(old)
    if found != 1:
        raise SystemExit("%s: expected exactly one match, found %d: %r" % (path, found, old[:60]))
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(text.replace(old, new))
    EDITED += 1


T = "_shared/tests/test_flash_pin_pro.py"
edit(T, '"""S1: five-model GUARD line, pro pin words, pro API id, zai_client docstring."""',
     '"""S1: six-model GUARD line, pro pin words, pro API id, zai_client docstring."""')
edit(T, '    "GLM 5.3",\n    "DeepSeek V4 Pro",\n',
     '    "GLM 5.3",\n    "GLM 5.4",\n    "DeepSeek V4 Pro",\n')
edit(T, "def test_names_all_five_session_models(self):",
     "def test_names_all_six_session_models(self):")
edit(T, "def test_names_five_session_models_and_both_providers(self):",
     "def test_names_six_session_models_and_both_providers(self):")
edit(T, "    def test_pro_api_maps_both_pro_words_to_their_api_ids(self):",
     "    def test_pro_api_maps_every_pro_word_to_its_api_id(self):")
edit(T, '        self.assertEqual(pro_api.get("glm-5.3"), "glm-5.3")',
     '        self.assertEqual(pro_api.get("glm-5.3"), "glm-5.3")\n'
     '        self.assertEqual(pro_api.get("glm-5.4"), "glm-5.4")')
NEW_WORDS = "\n".join([
    "    def test_glm_5_4_env_word_selects_glm(self):",
    '        with _env({"GLM_FLASH": "glm-5.4"}):',
    '            self.assertEqual(flash_pin.from_env(), "glm")',
    "",
    "    def test_glm_5_4_pin_file_word_selects_glm(self):",
    '        home = _pin_home(self, "glm-5.4\\n")',
    "        with _env({}):",
    '            self.assertEqual(flash_pin.from_file(home), "glm")',
    "",
    "",
])
edit(T, "class PinWord(unittest.TestCase):", NEW_WORDS + "class PinWord(unittest.TestCase):")
NEW_RESOLVE = "\n".join([
    "    def test_glm_5_4_pro_pin_resolves_the_glm_5_4_api_id_for_every_model(self):",
    '        for model in ("glm-5.3-flash", "some-other-model"):',
    '            with self.subTest(model=model), _env({"GLM_FLASH": "glm-5.4"}):',
    '                self.assertEqual(flash_pin.resolve_http_model(model), "glm-5.4")',
    "",
    "",
])
edit(T, "class FlashTierUnchanged(unittest.TestCase):",
     NEW_RESOLVE + "class FlashTierUnchanged(unittest.TestCase):")
print("edited %d test anchors" % EDITED)
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 8 test anchors`

- [x] **Step 2: Run the tests to verify they fail**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_flash_pin_pro.py`
Expected: FAILED (failures=6) - the two new word tests read `''` instead of `glm`, the resolve test reads the flash id instead of `glm-5.4`, the pro table has no `glm-5.4`, and both six-model name tests miss `GLM 5.4`

- [x] **Step 3: Teach the shared layer the sixth model**

```python
import io

EDITED = 0


def edit(path, old, new):
    global EDITED
    with io.open(path, encoding="utf-8") as fh:
        text = fh.read()
    found = text.count(old)
    if found != 1:
        raise SystemExit("%s: expected exactly one match, found %d: %r" % (path, found, old[:60]))
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(text.replace(old, new))
    EDITED += 1


edit("_shared/flash_pin.py",
     "The pro pin words glm-5.3 and deepseek-v4-pro name the non-flash",
     "The pro pin words glm-5.3, glm-5.4 and deepseek-v4-pro name the non-flash")
edit("_shared/flash_pin.py", '    "glm-5.3": "glm-5.3",\n    "deepseek-v4-pro": "deepseek-v4-pro",',
     '    "glm-5.3": "glm-5.3",\n    "glm-5.4": "glm-5.4",\n    "deepseek-v4-pro": "deepseek-v4-pro",')
edit("_shared/flash_pin.py", 'if word in ("glm", "glm-5.3-flash", "flash", "glm-5.3"):',
     'if word in ("glm", "glm-5.3-flash", "flash", "glm-5.3", "glm-5.4"):')
edit("_shared/handoff.py", "GLM 5.3, DeepSeek V4 Pro, or Claude Sonnet 5.5.",
     "GLM 5.3, GLM 5.4, DeepSeek V4 Pro, or Claude Sonnet 5.5.")
edit("_shared/zai_client.py", "DeepSeek V4.1 Flash, GLM 5.3, DeepSeek V4 Pro, Claude Sonnet 5.5.",
     "DeepSeek V4.1 Flash, GLM 5.3, GLM 5.4, DeepSeek V4 Pro, Claude Sonnet 5.5.")
print("edited %d shared sources" % EDITED)
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 5 shared sources`

- [x] **Step 4: Run the tests to verify they pass**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_flash_pin_pro.py`
Expected: `Ran 22 tests` and `OK`

- [x] **Step 5: Re-vendor the shared scripts and run the full suite**

Run: `cd z-skills && sh _shared/sync.sh && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: 22 lines that start with `synced`, then `OK`

- [x] **Step 6: Commit**

```bash
git add z-skills/_shared/handoff.py z-skills/_shared/flash_pin.py z-skills/_shared/zai_client.py z-skills/_shared/tests/test_flash_pin_pro.py z-skills/z-brainstorming/scripts/handoff.py z-skills/z-dev-team/scripts/handoff.py z-skills/z-dev-team/scripts/flash_pin.py z-skills/z-doc-generator/scripts/handoff.py z-skills/z-git-diff-summary/scripts/handoff.py z-skills/z-idea-to-spec/scripts/handoff.py z-skills/z-requirements-code-audit/scripts/handoff.py z-skills/z-requirements-code-audit/scripts/flash_pin.py z-skills/z-requirements-code-audit/scripts/zai_client.py z-skills/z-systematic-debugging/scripts/handoff.py z-skills/z-systematic-debugging/scripts/flash_pin.py z-skills/z-systematic-debugging/scripts/zai_client.py z-skills/z-writing-plans/scripts/handoff.py z-skills/z-writing-plans/scripts/flash_pin.py z-skills/z-writing-plans/scripts/zai_client.py
git commit -m "feat: name six session models in the shared model layer"
```

---

### T02: vocabulary pivot - every enumeration, pinned sentence and its tests [P]

**Depends:** —

**Interfaces:**
- Produces: `SIX_ID_LINE = ("glm-5.3-flash | deepseek-flash | glm-5.3 | glm-5.4"`; `PRO_PIN_CLAUSE = "the pin names a pro id (glm-5.3, glm-5.4, deepseek-v4-pro)"`; `KEEPS_OWN_MODEL_CLAUSE = "a glm-5.3, glm-5.4, deepseek-v4-pro or Claude Sonnet 5.5 session keeps its own model"`; `| GLM 5.4 | pro tier |`; `def test_every_skill_doc_names_glm_5_4_where_it_lists_the_other_models(self):`

**Files:**
- Modify: `z-skills/AGENTS.md`
- Modify: `z-skills/z-brainstorming/SKILL.md`
- Modify: `z-skills/z-dev-team/SKILL.md`
- Modify: `z-skills/z-doc-generator/SKILL.md`
- Modify: `z-skills/z-find-skills/SKILL.md`
- Modify: `z-skills/z-git-diff-summary/SKILL.md`
- Modify: `z-skills/z-idea-to-spec/SKILL.md`
- Modify: `z-skills/z-requirements-code-audit/SKILL.md`
- Modify: `z-skills/z-systematic-debugging/SKILL.md`
- Modify: `z-skills/z-writing-plans/SKILL.md`
- Modify: `z-skills/z-brainstorming/z-tuning.md`
- Modify: `z-skills/z-writing-plans/references/z-tuning.md`
- Modify: `z-skills/z-requirements-code-audit/references/z-tuning.md`
- Modify: `z-skills/z-systematic-debugging/references/z-tuning.md`
- Modify: `z-skills/z-systematic-debugging/README.md`
- Modify: `z-skills/z-brainstorming/visual-companion.md`
- Modify: `z-skills/z-brainstorming/agents/z-drafter.md`
- Modify: `z-skills/z-brainstorming/agents/z-design-breaker.md`
- Modify: `z-skills/z-brainstorming/CHANGELOG.md`
- Modify: `z-skills/z-writing-plans/CHANGELOG.md`
- Test: `z-skills/_shared/tests/test_all_skills.py`
- Test: `z-skills/_shared/tests/test_model_terms_bodies.py`
- Test: `z-skills/_shared/tests/test_model_terms_tuning.py`

Run every script from the repository root with `cd z-skills && python3 - <<'PY'`, paste the block, and close it with a line that holds only `PY`.

- [x] **Step 1: Move the vocabulary tests to six models**

Reason for each edited assertion: the requirement changed from five session ids to six.

```python
import io

EDITED = 0


def edit(path, old, new):
    global EDITED
    with io.open(path, encoding="utf-8") as fh:
        text = fh.read()
    found = text.count(old)
    if found != 1:
        raise SystemExit("%s: expected exactly one match, found %d: %r" % (path, found, old[:60]))
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(text.replace(old, new))
    EDITED += 1


T = "_shared/tests/"
ALL = T + "test_all_skills.py"
edit(ALL, "metadata.models (all five", "metadata.models (all six")
edit(ALL, '"glm-5.3-flash | deepseek-flash | glm-5.3 | deepseek-v4-pro | claude-sonnet-5.5",',
     '"glm-5.3-flash | deepseek-flash | glm-5.3 | glm-5.4 | deepseek-v4-pro | claude-sonnet-5.5",')
edit(ALL, "models line must list all five ids flat", "models line must list all six ids flat")

TUNING = T + "test_model_terms_tuning.py"
edit(TUNING, "Authoritative vocabulary: five session models",
     "Authoritative vocabulary: six session models")
edit(TUNING, '    "GLM 5.3",\n    "DeepSeek V4 Pro",\n',
     '    "GLM 5.3",\n    "GLM 5.4",\n    "DeepSeek V4 Pro",\n')
edit(TUNING, 'NEW_TIER_MODELS = ["DeepSeek V4 Pro", "Claude Sonnet 5.5"]',
     'NEW_TIER_MODELS = ["GLM 5.4", "DeepSeek V4 Pro", "Claude Sonnet 5.5"]')
edit(TUNING, '"""Criterion: five model names in each of the four docs."""',
     '"""Criterion: six model names in each of the four docs."""')
ROW_TEST = "\n".join([
    "class Glm54RowTests(unittest.TestCase):",
    '    """Criterion: the GLM 5.4 row sits in every table and its facts are dated."""',
    "",
    "    def test_every_doc_carries_the_glm_5_4_row_and_a_dated_note(self):",
    "        for rel in DOCS:",
    "            with self.subTest(doc=rel):",
    "                text = _read(rel)",
    '                self.assertIn("| GLM 5.4 | pro tier |", text)',
    '                self.assertIn("glm-5.4", text)',
    '                self.assertIn("2026-11-25", text)',
    "",
    "",
])
edit(TUNING, "class NewTierNumericRowTests(unittest.TestCase):",
     ROW_TEST + "class NewTierNumericRowTests(unittest.TestCase):")

BODIES = T + "test_model_terms_bodies.py"
edit(BODIES, "the two metadata `models:` lines list all five ids on one flat",
     "the two metadata `models:` lines list all six ids on one flat")
edit(BODIES, 'FIVE_ID_LINE = ("glm-5.3-flash | deepseek-flash | glm-5.3 | deepseek-v4-pro"\n'
             '                " | claude-sonnet-5.5")',
     'SIX_ID_LINE = ("glm-5.3-flash | deepseek-flash | glm-5.3 | glm-5.4"\n'
     '                " | deepseek-v4-pro | claude-sonnet-5.5")')
edit(BODIES, "self.assertIn(FIVE_ID_LINE, lines[0],", "self.assertIn(SIX_ID_LINE, lines[0],")
edit(BODIES, "%s models: line must list all five ids on one\"\n"
             "                          \" flat line\" % rel)",
     "%s models: line must list all six ids on one\"\n"
     "                          \" flat line\" % rel)")
edit(BODIES, "\"%s models: line must end at the fifth id\"\n"
             "                             \" (stay flat)\" % rel)",
     "\"%s models: line must end at the sixth id\"\n"
     "                             \" (stay flat)\" % rel)")
edit(BODIES, 'PRO_PIN_CLAUSE = "the pin names a pro id (glm-5.3, deepseek-v4-pro)"',
     'PRO_PIN_CLAUSE = "the pin names a pro id (glm-5.3, glm-5.4, deepseek-v4-pro)"\n'
     '    PRO_PIN_CLAUSE_DELIVERED_2026_11_19 = "the pin names a pro id (glm-5.3, deepseek-v4-pro)"')
edit(BODIES, "        self.assertIn(self.PRO_PIN_CLAUSE, entry,",
     "        self.assertIn(self.PRO_PIN_CLAUSE_DELIVERED_2026_11_19, entry,")
edit(BODIES, 'KEEPS_OWN_MODEL_CLAUSE = "a glm-5.3, deepseek-v4-pro or Claude Sonnet 5.5 session keeps its own model"',
     'KEEPS_OWN_MODEL_CLAUSE = "a glm-5.3, glm-5.4, deepseek-v4-pro or Claude Sonnet 5.5 session keeps its own model"')
edit(BODIES, "a GLM 5.3, DeepSeek V4 Pro or Claude Sonnet 5.5 session runs its own model under the same effort rules.\"",
     "a GLM 5.3, GLM 5.4, DeepSeek V4 Pro or Claude Sonnet 5.5 session runs its own model under the same effort rules.\"")
NEW_TESTS = "\n".join([
    "    def test_brainstorming_lane_agents_do_not_call_themselves_flash(self):",
    '        for rel in ("z-brainstorming/agents/z-drafter.md",',
    '                    "z-brainstorming/agents/z-design-breaker.md"):',
    "            content = read(rel)",
    '            self.assertNotIn("Flash lane", content,',
    '                             "%s still calls itself a flash lane" % rel)',
    '            self.assertIn("on the session model", content,',
    '                          "%s must say it runs on the session model" % rel)',
    "",
    "    def test_every_skill_doc_names_glm_5_4_where_it_lists_the_other_models(self):",
    '        docs = [os.path.join(GLM_ROOT, "AGENTS.md")]',
    '        for folder in ("z-brainstorming", "z-dev-team", "z-doc-generator",',
    '                       "z-find-skills", "z-git-diff-summary", "z-idea-to-spec",',
    '                       "z-requirements-code-audit", "z-systematic-debugging",',
    '                       "z-writing-plans"):',
    "            for dirpath, dirnames, filenames in os.walk(os.path.join(GLM_ROOT, folder)):",
    '                dirnames[:] = [d for d in dirnames if d != "__pycache__"]',
    "                docs += [os.path.join(dirpath, name) for name in filenames",
    '                         if name.endswith(".md") and name != "CHANGELOG.md"]',
    "        for path in docs:",
    '            with open(path, encoding="utf-8") as fh:',
    "                text = fh.read()",
    "            relative = os.path.relpath(path, GLM_ROOT)",
    '            if "DeepSeek V4 Pro" in text and "Claude Sonnet 5.5" in text:',
    '                self.assertTrue("GLM 5.4" in text or "glm-5.4" in text,',
    '                                "%s lists the other models but not GLM 5.4" % relative)',
    '            for stale in ("five session models", "Five display names",',
    '                          "four session models"):',
    '                self.assertNotIn(stale, text, "%s still says %r" % (relative, stale))',
    "",
    "",
])
edit(BODIES, "    def test_changelog_records_sweep_skipping_folders_without_one(self):",
     NEW_TESTS + "    def test_changelog_records_sweep_skipping_folders_without_one(self):")
print("edited %d test anchors" % EDITED)
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 18 test anchors`

- [x] **Step 2: Run the tests to verify they fail**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p "test_model_terms_*.py"`
Expected: FAILED - every failure names a missing GLM 5.4 row, a five-id line, a sentence without the third pro id, or an agent that still calls itself a flash lane

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py`
Expected: FAILED (failures=1) with `models line must list all six ids flat`

- [x] **Step 3: Apply the vocabulary edits**

The audit skill keeps its description length: `API` replaces `GLM`, three characters for three characters, so its tuning doc still states the measured length.

```python
import io

EDITED = 0


def edit(path, old, new):
    global EDITED
    with io.open(path, encoding="utf-8") as fh:
        text = fh.read()
    found = text.count(old)
    if found != 1:
        raise SystemExit("%s: expected exactly one match, found %d: %r" % (path, found, old[:60]))
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(text.replace(old, new))
    EDITED += 1


SKILLS = ("z-brainstorming", "z-dev-team", "z-doc-generator", "z-find-skills",
          "z-git-diff-summary", "z-idea-to-spec", "z-requirements-code-audit",
          "z-systematic-debugging", "z-writing-plans")
for skill in SKILLS:
    edit(skill + "/SKILL.md", "glm-5.3 | deepseek-v4-pro | claude-sonnet-5.5",
         "glm-5.3 | glm-5.4 | deepseek-v4-pro | claude-sonnet-5.5")
edit("z-dev-team/SKILL.md",
     "a GLM 5.3, DeepSeek V4 Pro or Claude Sonnet 5.5 session runs its own model under the same effort rules.",
     "a GLM 5.3, GLM 5.4, DeepSeek V4 Pro or Claude Sonnet 5.5 session runs its own model under the same effort rules.")
edit("z-writing-plans/SKILL.md",
     "the pin names a pro id (glm-5.3, deepseek-v4-pro)",
     "the pin names a pro id (glm-5.3, glm-5.4, deepseek-v4-pro)")
edit("z-systematic-debugging/SKILL.md",
     "a glm-5.3, deepseek-v4-pro or Claude Sonnet 5.5 session keeps its own model",
     "a glm-5.3, glm-5.4, deepseek-v4-pro or Claude Sonnet 5.5 session keeps its own model")
edit("z-requirements-code-audit/SKILL.md",
     "fans out up to 8 parallel GLM requests",
     "fans out up to 8 parallel API requests")
edit("z-systematic-debugging/README.md",
     "its five session models \u2014 glm-5.3-flash, deepseek-flash (DeepSeek), glm-5.3, deepseek-v4-pro, and claude-sonnet-5.5 (Claude).",
     "its six session models \u2014 glm-5.3-flash, deepseek-flash (DeepSeek), glm-5.3, glm-5.4, deepseek-v4-pro, and claude-sonnet-5.5 (Claude).")
TUNING = ("z-brainstorming/z-tuning.md", "z-writing-plans/references/z-tuning.md",
          "z-requirements-code-audit/references/z-tuning.md",
          "z-systematic-debugging/references/z-tuning.md")
NOTE = "\n".join([
    "",
    "GLM 5.4 (api id glm-5.4), from the vendor model page read on",
    "2026-11-25: 1M context, 128K max output, thinking mode, tool calling,",
    "JSON output, image and video input; the general Model API was still",
    "pending at that date. Nothing else is claimed for it here.",
    "",
])
for path in TUNING:
    edit(path, "Five display names cover the three tiers a session can run on.",
         "Six display names cover the three tiers a session can run on.")
    edit(path, "| GLM 5.3 | pro tier |\n| DeepSeek V4 Pro | pro tier |\n",
         "| GLM 5.3 | pro tier |\n| GLM 5.4 | pro tier |\n| DeepSeek V4 Pro | pro tier |\n")
    edit(path, "No speed or price numbers are pinned for these tiers.\n",
         "No speed or price numbers are pinned for these tiers.\n" + NOTE)
edit("z-writing-plans/references/z-tuning.md",
     "# Running this skill on GLM-5.3 / GLM-5.3-Flash",
     "# Running this skill on the six session models")
edit("z-requirements-code-audit/references/z-tuning.md",
     "# GLM-5.3 tuning \u2014 what was verified, what it changed",
     "# Session-model tuning \u2014 what was verified, what it changed")
edit("z-systematic-debugging/references/z-tuning.md",
     "# GLM-5.3 / GLM-5.3-Flash tuning \u2014 why this skill is shaped the way it is",
     "# Session-model tuning \u2014 why this skill is shaped the way it is")
B = "z-brainstorming/z-tuning.md"
edit(B, "Model and effort live only in the agent frontmatter. This file is the\neconomics and the failure table.",
     "The session supplies the model. The only per-lane effort setting is the\nthoughtLevel line of each agent file, and no dispatch names a model\n(SKILL.md R2 and R3). This file is the economics and the failure table.")
edit(B, "| Lanes ran on the session model at effort max | Agent frontmatter had no model id, so thoughtLevel was ignored | Model and effort live only in the agent frontmatter |",
     "| A lane ran at an effort other than its agent file's thoughtLevel | A lane follows the session model; the agent file's thoughtLevel line is its only effort setting | Keep the thoughtLevel line and no model line in the agent file; never add a model id (SKILL.md R2) |")
edit(B, "Install all eight skills with", "Install all eleven skills with")
edit(B, "Model and effort live only in the agent frontmatter (section 2).",
     "The session supplies the model; each agent file carries only a thoughtLevel line (section 2).")
A = "z-requirements-code-audit/references/z-tuning.md"
edit(A, "The agent files pin the same Flash id.",
     "The agent files carry no model id; a lane follows the session model.")
edit(A, "`agents/*.md` uses real GLM ids + `thoughtLevel`",
     "`agents/*.md` carries `thoughtLevel` and no model id")
edit("z-brainstorming/visual-companion.md",
     "Reading screenshots back: glm-5.3-flash reads images natively, so a\n"
     "flash-tier lane can look at a screenshot of the rendered page if you need\n"
     "a visual check; glm-5.3 is text-only \u2014 do not send it images. On any other\n"
     "session model, confirm it takes images before sending one; the lane always\n"
     "follows the session model.",
     "Reading screenshots back: glm-5.3-flash reads images natively, and glm-5.4\n"
     "takes image input too (vendor model page, 2026-11-25), so a flash-tier or\n"
     "GLM 5.4 lane can look at a screenshot of the rendered page if you need a\n"
     "visual check; glm-5.3 is text-only \u2014 do not send it images. On any other\n"
     "session model, confirm it takes images before sending one; the lane always\n"
     "follows the session model.")
for rel in ("z-brainstorming/agents/z-drafter.md", "z-brainstorming/agents/z-design-breaker.md"):
    edit(rel, 'description: "Flash lane for z-brainstorming:',
         'description: "Lane for z-brainstorming, on the session model:')
edit("AGENTS.md", "These skills target four session models - GLM-5.3-Flash, DeepSeek-V4.1-Flash (model id",
     "These skills target six session models - GLM-5.3-Flash, DeepSeek-V4.1-Flash (model id")
edit("AGENTS.md", "`deepseek-flash`), GLM-5.3 and DeepSeek-V4-Pro - and two harnesses: ZCode and DeepSeek Harness",
     "`deepseek-flash`), GLM-5.3, GLM-5.4, DeepSeek-V4-Pro and Claude-Sonnet-5.5 - and two harnesses: ZCode and DeepSeek Harness")
edit("AGENTS.md", "`glm-5.3` / `deepseek-v4-pro` pin the pro lane",
     "`glm-5.3` / `glm-5.4` / `deepseek-v4-pro` pin the pro lane")
edit("AGENTS.md", "Every change must keep all four models and both harnesses",
     "Every change must keep all six models and both harnesses")
edit("z-writing-plans/CHANGELOG.md", "**Five session models in R6 (2026-11-19):**",
     "**Six session models in R6 (2026-11-25):** R6 names the third pro id, glm-5.4, next to "
     "glm-5.3 and deepseek-v4-pro; the metadata models line and the tuning table list six ids. "
     "The lane still follows the session model; no agent file names a model.\n\n"
     "**Five session models in R6 (2026-11-19):**")
PATH = "z-brainstorming/CHANGELOG.md"
with io.open(PATH, encoding="utf-8") as fh:
    TEXT = fh.read()
HEAD = "# 10.11 (from 10.10)"
if TEXT.count(HEAD) != 1:
    raise SystemExit("%s: expected exactly one match, found %d: %r" % (PATH, TEXT.count(HEAD), HEAD))
ENTRY = "\n".join([
    "# 10.12 (from 10.11) - 2026-11-25: six session models in the wording",
    "",
    "The model layer names six session models: GLM 5.4 (id glm-5.4, pro tier)",
    "joins the five of the previous sweep. The tuning table and the metadata",
    "models line list six ids. The tuning doc no longer says model and effort",
    "live in the agent frontmatter: the session supplies the model and each",
    "agent file carries only a thoughtLevel line. It counts eleven installed",
    "skills. The drafter and design-breaker agents no longer call themselves",
    "flash lanes. The visual companion lets a GLM 5.4 lane read a screenshot",
    "(vendor model page, 2026-11-25). No lane is promoted.",
    "",
    "",
])
with io.open(PATH, "w", encoding="utf-8") as fh:
    fh.write(ENTRY + TEXT)
EDITED += 1
print("edited %d text blocks" % EDITED)
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 44 text blocks`

- [x] **Step 4: Run the vocabulary tests to verify they pass**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p "test_model_terms_*.py"`
Expected: `Ran 29 tests` and `OK`

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py`
Expected: `Ran 6 tests` and `OK`

- [x] **Step 5: Run the full suite**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: `OK` (the test count depends on which other tasks are already merged)

- [x] **Step 6: Commit**

```bash
git add z-skills/AGENTS.md z-skills/z-brainstorming/SKILL.md z-skills/z-dev-team/SKILL.md z-skills/z-doc-generator/SKILL.md z-skills/z-find-skills/SKILL.md z-skills/z-git-diff-summary/SKILL.md z-skills/z-idea-to-spec/SKILL.md z-skills/z-requirements-code-audit/SKILL.md z-skills/z-systematic-debugging/SKILL.md z-skills/z-writing-plans/SKILL.md z-skills/z-brainstorming/z-tuning.md z-skills/z-writing-plans/references/z-tuning.md z-skills/z-requirements-code-audit/references/z-tuning.md z-skills/z-systematic-debugging/references/z-tuning.md z-skills/z-systematic-debugging/README.md z-skills/z-brainstorming/visual-companion.md z-skills/z-brainstorming/agents/z-drafter.md z-skills/z-brainstorming/agents/z-design-breaker.md z-skills/z-brainstorming/CHANGELOG.md z-skills/z-writing-plans/CHANGELOG.md z-skills/_shared/tests/test_all_skills.py z-skills/_shared/tests/test_model_terms_bodies.py z-skills/_shared/tests/test_model_terms_tuning.py
git commit -m "feat: six-model vocabulary across every skill"
```

---

### T03: installer keeps a saved pro pin word and learns glm-5.4 [P]

**Depends:** —

**Interfaces:**
- Produces: `PIN="$FLASH"`; `glm|glm-5.3-flash|flash|glm-5.3|glm-5.4) FLASH=glm ;;`; `def test_saved_glm_5_4_pin_word_keeps_the_glm_provider_and_the_word(self):`

**Files:**
- Modify: `z-skills/install-zcode.sh`
- Test: `z-skills/_shared/tests/test_install_zcode.py`

- [x] **Step 1: Write the failing tests**

Run the script from the repository root with `cd z-skills && python3 - <<'PY'`, paste the block, and close it with a line that holds only `PY`. It replaces one test with four. Reason for the edited assertion: a re-install used to rewrite a saved pro pin word to its provider word, which silently dropped an explicit setting; the requirement is now that a saved word the runtime knows is kept.

```python
import io

PATH = "_shared/tests/test_install_zcode.py"
OLD = "\n".join([
    "    def test_saved_pro_pin_word_keeps_deepseek_provider(self):",
    '        pin = os.path.join(self.home, ".zcode", "z-flash")',
    "        os.makedirs(os.path.dirname(pin))",
    '        with open(pin, "w", encoding="utf-8") as fh:',
    '            fh.write("deepseek-v4-pro\\n")',
    "        r = self.install()",
    "        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)",
    '        self.assertIn("pin: deepseek", r.stdout)',
    '        with open(pin, encoding="utf-8") as fh:',
    '            self.assertEqual(fh.read().strip(), "deepseek")',
    "        again = self.install()",
    "        self.assertEqual(again.returncode, 0, again.stderr + again.stdout)",
    '        self.assertIn("pin: deepseek", again.stdout)',
])
NEW = "\n".join([
    "    def _saved_pin(self, word):",
    '        pin = os.path.join(self.home, ".zcode", "z-flash")',
    "        os.makedirs(os.path.dirname(pin))",
    '        with open(pin, "w", encoding="utf-8") as fh:',
    "            fh.write(word)",
    "        return pin",
    "",
    "    @staticmethod",
    "    def _pin_word(pin):",
    '        with open(pin, encoding="utf-8") as fh:',
    "            return fh.read().strip()",
    "",
    "    def test_saved_pro_pin_word_keeps_the_deepseek_provider_and_the_word(self):",
    '        pin = self._saved_pin("deepseek-v4-pro\\n")',
    "        r = self.install()",
    "        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)",
    '        self.assertIn("pin: deepseek", r.stdout)',
    '        self.assertEqual(self._pin_word(pin), "deepseek-v4-pro")',
    "        again = self.install()",
    "        self.assertEqual(again.returncode, 0, again.stderr + again.stdout)",
    '        self.assertIn("pin: deepseek", again.stdout)',
    '        self.assertEqual(self._pin_word(pin), "deepseek-v4-pro")',
    "",
    "    def test_saved_glm_5_4_pin_word_keeps_the_glm_provider_and_the_word(self):",
    '        pin = self._saved_pin("glm-5.4\\n")',
    "        r = self.install()",
    "        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)",
    '        self.assertIn("pin: glm", r.stdout)',
    '        self.assertEqual(self._pin_word(pin), "glm-5.4")',
    "",
    "    def test_explicit_flash_flag_replaces_a_saved_pro_word(self):",
    '        pin = self._saved_pin("glm-5.3\\n")',
    '        r = self.install("--flash", "deepseek")',
    "        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)",
    '        self.assertEqual(self._pin_word(pin), "deepseek")',
    "",
    "    def test_unknown_saved_pin_word_falls_back_to_glm(self):",
    '        pin = self._saved_pin("nonsense\\n")',
    "        r = self.install()",
    "        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)",
    '        self.assertEqual(self._pin_word(pin), "glm")',
])
with io.open(PATH, encoding="utf-8") as fh:
    text = fh.read()
found = text.count(OLD)
if found != 1:
    raise SystemExit("expected exactly one match, found %d" % found)
with io.open(PATH, "w", encoding="utf-8") as fh:
    fh.write(text.replace(OLD, NEW))
print("replaced 1 test with 4")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `replaced 1 test with 4`

- [x] **Step 2: Run the tests to verify two of them fail**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_install_zcode.py`
Expected: `Ran 26 tests`, FAILED (failures=2) - the two saved-word tests read `deepseek` and `glm` where they expect the saved pro word; the explicit-flag test and the unknown-word test already pass and must keep passing

- [x] **Step 3: Keep the saved word and learn glm-5.4**

```python
import io

EDITED = 0


def edit(path, old, new):
    global EDITED
    with io.open(path, encoding="utf-8") as fh:
        text = fh.read()
    found = text.count(old)
    if found != 1:
        raise SystemExit("%s: expected exactly one match, found %d: %r" % (path, found, old[:60]))
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(text.replace(old, new))
    EDITED += 1


S = "install-zcode.sh"
edit(S, '    *) echo "Error: --flash must be glm or deepseek, got $FLASH" >&2; exit 1 ;;\nesac\n',
     '    *) echo "Error: --flash must be glm or deepseek, got $FLASH" >&2; exit 1 ;;\nesac\n'
     '\n'
     '# The word written back to the pin file: the provider, unless a saved word is kept below.\n'
     'PIN="$FLASH"\n')
edit(S, '    # The pro words deepseek-v4-pro and glm-5.3 map to their providers.\n'
        '    case "$saved" in\n'
        '        deepseek|ds|deepseek-flash|deepseek-v4-pro) FLASH=deepseek ;;\n'
        '        glm|glm-5.3-flash|flash|glm-5.3) FLASH=glm ;;\n'
        '    esac\n'
        'fi\n',
        '    # The pro words deepseek-v4-pro, glm-5.3 and glm-5.4 map to their providers.\n'
        '    case "$saved" in\n'
        '        deepseek|ds|deepseek-flash|deepseek-v4-pro) FLASH=deepseek ;;\n'
        '        glm|glm-5.3-flash|flash|glm-5.3|glm-5.4) FLASH=glm ;;\n'
        '        *) saved="" ;;\n'
        '    esac\n'
        '    # A saved word the runtime knows is kept: a re-install must not drop a pro pin.\n'
        '    if [ -n "$saved" ]; then PIN="$saved"; fi\n'
        'fi\n')
edit(S, 'printf \'%s\\n\' "$FLASH" > "$HOME_DIR/.zcode/z-flash"',
     'printf \'%s\\n\' "$PIN" > "$HOME_DIR/.zcode/z-flash"')
print("edited %d installer blocks" % EDITED)
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 3 installer blocks`

- [x] **Step 4: Run the tests to verify they pass**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_install_zcode.py`
Expected: `Ran 26 tests` and `OK`

- [x] **Step 5: Commit**

```bash
git add z-skills/install-zcode.sh z-skills/_shared/tests/test_install_zcode.py
git commit -m "fix: installer keeps a saved pro pin word and knows glm-5.4"
```

---

### T04: dev-team engine prints routing that follows the session model [P]

**Depends:** —

**Interfaces:**
- Produces: `class EngineRoutingText(unittest.TestCase):`; `every lane follows the session model`

**Files:**
- Modify: `z-skills/z-dev-team/scripts/devteam.py`
- Modify: `z-skills/z-dev-team/scripts/selftest.sh`
- Test: `z-skills/_shared/tests/test_devteam_wording.py`

- [x] **Step 1: Write the failing test**

Create `_shared/tests/test_devteam_wording.py`:

```python
"""Spec 2026-11-25: the dev-team engine's routing text follows the session model.

Source-text guards. No agent file pins a model, so the engine must neither
print nor document a pinned model. The behavior behind the text is covered by
the other dev-team modules and by scripts/selftest.sh."""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "..", "..", "z-dev-team", "scripts", "devteam.py")
SELFTEST = os.path.join(HERE, "..", "..", "z-dev-team", "scripts", "selftest.sh")

STALE = (
    "tuned for ZCode on Z.ai GLM-5.3-Flash",
    "pinned in the agents' own frontmatter",
    "pinned in the agents' frontmatter",
    "effort is max on every agent",
    "thoughtLevel is ignored unless that model id is present",
    "(GLM-5.3-Flash, thoughtLevel max)",
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class EngineRoutingText(unittest.TestCase):
    def test_engine_carries_no_stale_pinned_model_wording(self):
        text = _read(ENGINE)
        for stale in STALE:
            with self.subTest(stale=stale):
                self.assertNotIn(stale, text)

    def test_provider_line_names_the_session_model_and_no_pinned_model(self):
        lines = _read(ENGINE).splitlines()
        starts = [i for i, ln in enumerate(lines) if 'out(f"PROVIDER {PROVIDERS[provider]' in ln]
        self.assertEqual(len(starts), 1, "expected exactly one PROVIDER line")
        statement = "\n".join(lines[starts[0]:starts[0] + 2])
        self.assertIn("every lane follows the session model", statement)
        self.assertNotIn("GLM-5.3-Flash", statement)
        self.assertNotIn("frontmatter", statement)


class SelftestLabels(unittest.TestCase):
    def test_selftest_check_labels_name_no_pinned_model(self):
        text = _read(SELFTEST)
        self.assertNotIn("(GLM-5.3-Flash, thoughtLevel max)", text)
        self.assertNotIn("strong lane (GLM-5.3-Flash)", text)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run the test to verify it fails**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_wording.py`
Expected: `Ran 3 tests`, FAILED (failures=3) - every stale phrase is still in the engine, the provider line still names a flash model, and the check labels still name one

- [x] **Step 3: Rewrite the routing text**

Run the script from the repository root with `cd z-skills && python3 - <<'PY'`, paste the block, and close it with a line that holds only `PY`.

```python
import io

EDITED = 0


def edit(path, old, new):
    global EDITED
    with io.open(path, encoding="utf-8") as fh:
        text = fh.read()
    found = text.count(old)
    if found != 1:
        raise SystemExit("%s: expected exactly one match, found %d: %r" % (path, found, old[:60]))
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(text.replace(old, new))
    EDITED += 1


E = "z-dev-team/scripts/devteam.py"
edit(E, "tuned for ZCode on Z.ai GLM-5.3-Flash (strong) + GLM-5.3-Flash (fast). The provider is auto-detected from",
     "tuned for ZCode. Every lane follows the session model; no agent file pins a model. The provider is auto-detected from")
edit(E, "(z-programmer-strong / z-programmer-lite, pinned in the agents' own frontmatter).",
     "(z-programmer-strong / z-programmer-lite, each with the thoughtLevel in its own frontmatter).")
edit(E, "every lane rides z-programmer-lite (GLM-5.3-Flash, thoughtLevel max); high-risk,",
     "every lane rides z-programmer-lite (thoughtLevel high); high-risk,")
edit(E, "large and RETRIED slices escalate to z-programmer-strong (GLM-5.3-Flash, thoughtLevel max). Model",
     "large and RETRIED slices escalate to z-programmer-strong (thoughtLevel max). Both follow")
edit(E, "ids stay as pinned; effort is max on every agent. Both are pinned in the agents' own",
     "the session model: no agent file pins a model id, the Agent tool takes no")
edit(E, "frontmatter \u2014 the Agent tool takes no per-dispatch model, and `doctor --fix` installs the",
     "per-dispatch model, and `doctor --fix` installs the")
edit(E, "agents verbatim. thoughtLevel is ignored unless that model id is present.",
     "agents verbatim.")
edit(E, "# per-dispatch model, so each agents/<name>.md file pins its own model id + thoughtLevel",
     "# per-dispatch model, so each agents/<name>.md file follows the session model and carries only a")
edit(E, "# (z-programmer-strong = GLM-5.3-Flash/max, z-programmer-lite = GLM-5.3-Flash/max, reviewer/leader likewise).",
     "# thoughtLevel (z-programmer-strong max, z-programmer-lite high, reviewer/leader per their own files).")
edit(E, "lanes on z-programmer-lite (GLM-5.3-Flash); high-risk, large \"",
     "lanes on z-programmer-lite; high-risk, large \"")
edit(E, "\"and retried slices on z-programmer-strong (GLM-5.3-Flash); model + effort pinned in the agents' frontmatter\")",
     "\"and retried slices on z-programmer-strong; every lane follows the session model\")")
S = "z-dev-team/scripts/selftest.sh"
edit(S, 'check "a trivial slice rides the lite lane (GLM-5.3-Flash, thoughtLevel max)"',
     'check "a trivial slice rides the lite lane"')
edit(S, 'check "a normal slice rides the lite lane (GLM-5.3-Flash, thoughtLevel max) with no model override"',
     'check "a normal slice rides the lite lane with no model override"')
edit(S, 'check "a high-risk slice escalates to the strong lane (GLM-5.3-Flash)"',
     'check "a high-risk slice escalates to the strong lane"')
print("edited %d routing text blocks" % EDITED)
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 14 routing text blocks`

- [x] **Step 4: Run the test and the self-test to verify they pass**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_devteam_wording.py`
Expected: `Ran 3 tests` and `OK`

Run: `cd z-skills && bash z-dev-team/scripts/selftest.sh`
Expected: the last line ends with `failed=0` and the exit code is 0

- [x] **Step 5: Commit**

```bash
git add z-skills/z-dev-team/scripts/devteam.py z-skills/z-dev-team/scripts/selftest.sh z-skills/_shared/tests/test_devteam_wording.py
git commit -m "fix: dev-team engine prints routing that follows the session model"
```

---

### T05: plan tool doctor prints the effort each tier sets [P]

**Depends:** —

**Interfaces:**
- Produces: `class DoctorModelsRow(unittest.TestCase):`; `"models    : light=%s/%s  std=%s/%s  deep=%s/%s" % (`

**Files:**
- Modify: `z-skills/z-writing-plans/scripts/plan_tool.py`
- Test: `z-skills/_shared/tests/test_plan_doctor.py`

- [x] **Step 1: Write the failing test**

Create `_shared/tests/test_plan_doctor.py`:

```python
"""Spec 2026-11-25: plan_tool.py doctor prints the effort each tier sets."""
import argparse
import contextlib
import importlib.util
import io
import os
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
PLAN_TOOL = os.path.join(HERE, "..", "..", "z-writing-plans", "scripts", "plan_tool.py")


def _load_plan_tool():
    spec = importlib.util.spec_from_file_location("plan_tool_doctor_under_test", PLAN_TOOL)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


plan_tool = _load_plan_tool()


class DoctorModelsRow(unittest.TestCase):
    def _row(self):
        buf = io.StringIO()
        fake = mock.patch.object(plan_tool, "find_credentials", return_value=(None, "", "", ""))
        with fake, contextlib.redirect_stdout(buf):
            code = plan_tool.cmd_doctor(argparse.Namespace(ping=False))
        self.assertEqual(code, 1, "no key means doctor exits 1")
        rows = [ln for ln in buf.getvalue().splitlines() if ln.startswith("models")]
        self.assertEqual(len(rows), 1, buf.getvalue())
        return rows[0]

    def test_row_prints_the_effort_each_tier_sets(self):
        row = self._row()
        for tier in ("light", "std", "deep"):
            model, effort = plan_tool.GLM[tier][0], plan_tool.GLM[tier][1]
            with self.subTest(tier=tier):
                self.assertIn("%s=%s/%s" % (tier, model, effort), row)

    def test_row_does_not_hardcode_a_low_light_tier(self):
        self.assertEqual(plan_tool.GLM["light"][1], "high")
        self.assertNotIn("light=%s/low" % plan_tool.GLM["light"][0], self._row())


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run the test to verify it fails**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_plan_doctor.py`
Expected: `Ran 2 tests`, FAILED (failures=2) - the row reads `light=glm-5.3-flash/low` while the light tier sets `high`

- [x] **Step 3: Print the effort from the tier table**

Run the script from the repository root with `cd z-skills && python3 - <<'PY'`, paste the block, and close it with a line that holds only `PY`.

```python
import io

PATH = "z-writing-plans/scripts/plan_tool.py"
OLD = 'print("models    : light=%s/low  std=%s/high  deep=%s/max" % (GLM["light"][0], GLM["std"][0], GLM["deep"][0]))'
NEW = ('print("models    : light=%s/%s  std=%s/%s  deep=%s/%s" % (\n'
       '        GLM["light"][0], GLM["light"][1], GLM["std"][0], GLM["std"][1],\n'
       '        GLM["deep"][0], GLM["deep"][1]))')
with io.open(PATH, encoding="utf-8") as fh:
    text = fh.read()
found = text.count(OLD)
if found != 1:
    raise SystemExit("expected exactly one match, found %d" % found)
with io.open(PATH, "w", encoding="utf-8") as fh:
    fh.write(text.replace(OLD, NEW))
print("replaced 1 doctor line")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `replaced 1 doctor line`

- [x] **Step 4: Run the test to verify it passes**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_plan_doctor.py`
Expected: `Ran 2 tests` and `OK`

- [x] **Step 5: Commit**

```bash
git add z-skills/z-writing-plans/scripts/plan_tool.py z-skills/_shared/tests/test_plan_doctor.py
git commit -m "fix: plan tool doctor prints the effort each tier sets"
```

---

### T06: guard against broken bundled-path references in every skill [P]

**Depends:** —

**Interfaces:**
- Produces: `def missing_references(skill_root, text):`; `class TreeTests(unittest.TestCase):`

**Files:**
- Test: `z-skills/_shared/tests/test_skill_references.py`

- [x] **Step 1: Write the scanner test with a stub**

Create `_shared/tests/test_skill_references.py`:

```python
"""Spec 2026-11-25: every bundled path a skill names in prose must exist.

A skill body that points at a missing reference file, script or agent is a
broken reference: the reader loads nothing and the step silently degrades.
The scanner is exercised on a temporary fixture first, then run over the tree."""
import os
import re
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
SKILLS = sorted(name for name in os.listdir(ROOT)
                if name.startswith("z-") and os.path.isfile(os.path.join(ROOT, name, "SKILL.md"))
                and "video" not in name)
REFERENCE = re.compile(
    r"(?<![A-Za-z0-9_./-])((?:z-[a-z-]+/)?(?:scripts|references|agents|commands)/[A-Za-z0-9_.\-/]+[A-Za-z0-9_])")


def missing_references(skill_root, text):
    return []


class ScannerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.skill = os.path.join(self._tmp.name, "z-sample")

    def _write(self, rel):
        path = os.path.join(self.skill, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("x")

    def test_an_existing_path_is_not_reported(self):
        self._write("references/rules.md")
        self.assertEqual(missing_references(self.skill, "Read `references/rules.md` first."), [])

    def test_a_broken_reference_is_reported_once_per_path(self):
        self._write("references/rules.md")
        text = "Read `references/missing.md`, then references/other.py."
        self.assertEqual(missing_references(self.skill, text),
                         ["references/missing.md", "references/other.py"])

    def test_a_bare_word_pair_before_a_comma_is_prose(self):
        text = "After it installs or changes agents/hooks, tell the user."
        self.assertEqual(missing_references(self.skill, text), [])

    def test_another_skill_is_resolved_from_the_repository_root(self):
        present = "Run `z-writing-plans/scripts/plan_tool.py doctor`."
        self.assertEqual(missing_references(self.skill, present), [])
        absent = "Run `z-no-such-skill/scripts/tool.py doctor`."
        self.assertEqual(missing_references(self.skill, absent),
                         ["z-no-such-skill/scripts/tool.py"])

    def test_an_empty_text_reports_nothing(self):
        self.assertEqual(missing_references(self.skill, ""), [])


class TreeTests(unittest.TestCase):
    def _prose_files(self, skill):
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, skill)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for filename in filenames:
                if filename.endswith(".md"):
                    yield os.path.join(dirpath, filename)

    def test_every_skill_prose_file_names_only_existing_paths(self):
        broken = []
        for skill in SKILLS:
            for path in self._prose_files(skill):
                with open(path, encoding="utf-8") as fh:
                    lines = fh.read().splitlines()
                for line_number, line in enumerate(lines, 1):
                    for missing in missing_references(os.path.join(ROOT, skill), line):
                        broken.append("%s:%d %s" % (os.path.relpath(path, ROOT), line_number, missing))
        self.assertEqual(broken, [], "\n".join(broken))


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run the test to verify the scanner tests fail**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_skill_references.py`
Expected: `Ran 6 tests`, FAILED (failures=2) - the stub reports nothing, so the broken-reference test and the other-skill test read `[]`

- [x] **Step 3: Implement the scanner**

In `_shared/tests/test_skill_references.py`, replace the stub body of `missing_references` so the function reads:

```python
def missing_references(skill_root, text):
    """Paths named in `text` that do not exist under `skill_root`, or under the
    repository root when the path names another skill. A token followed by a
    comma is a word pair in prose, not a path."""
    missing = []
    for match in REFERENCE.finditer(text):
        path = match.group(1)
        if text[match.end():match.end() + 1] == ",":
            continue
        base = ROOT if path.startswith("z-") else skill_root
        if not os.path.exists(os.path.join(base, path)):
            missing.append(path)
    return missing
```

- [x] **Step 4: Run the test to verify it passes**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_skill_references.py`
Expected: `Ran 6 tests` and `OK`

- [x] **Step 5: Commit**

```bash
git add z-skills/_shared/tests/test_skill_references.py
git commit -m "test: guard against broken bundled-path references in skills"
```

```json
{
 "request": "Optimize every non-video skill in z-skills to work best with six session models - GLM 5.3 Flash, GLM 5.3, GLM 5.4, DeepSeek V4.1 Flash, DeepSeek V4 Pro and Claude Sonnet 5.5 - on both harnesses, then re-check every non-video skill for problems and fix what is found. Spec: docs/specs/2026-11-25-six-session-models-and-audit.md",
 "profile": "balanced",
 "glm": {
  "tier": "api"
 },
 "commands": {
  "build": "none",
  "test": "cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests",
  "test_file": "cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests",
  "lint": "none",
  "lint_file": "none",
  "typecheck": "none",
  "typecheck_file": "none"
 },
 "contracts": [
  "C1 six-id models line: glm-5.3-flash | deepseek-flash | glm-5.3 | glm-5.4 | deepseek-v4-pro | claude-sonnet-5.5 - written by S2 into every non-video SKILL.md frontmatter",
  "C2 pin vocabulary: glm-5.4 is a GLM pro pin word (provider glm, API id glm-5.4) - established in S1, relied on by S3",
  "C3 every lane follows the session model; no agent file pins a model id - binds every slice"
 ],
 "notes": "Work happens inside z-skills (suites run from there, never the repo root). The plan file is /Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-25-six-session-models-and-audit.md: each slice follows its own T body there, step by step. The bodies hold the exact edit scripts: run those script blocks with the heredoc they show instead of retyping their content, and run the test commands they list. Every path except that plan file is git-root-relative, so prefix it with z-skills/ when you cd there. Code slices commit the failing tests before the implementation: the RED commit message starts test(SLICEID): and contains only test files; the GREEN commit follows with commit-green. Never add a model id to an agent file, never loosen, skip or delete a test, never touch a file outside the slice footprint, stdlib only.",
 "test_globs": [
  "_shared/tests/test_*.py"
 ],
 "slices": [
  {
   "id": "S1",
   "title": "shared model layer - six-model GUARD line and the glm-5.4 pro pin word",
   "goal": "Follow the T01 body in the plan file step by step. Step 1 (the test edits) is the RED side: commit it with commit-red as test(S1): six-model pin tests. Steps 3 to 5 are the GREEN side: apply the shared-source edits, run sh _shared/sync.sh from z-skills, confirm the vendored copies, then commit every path in the T01 Files list with commit-green as feat(S1): name six session models in the shared model layer.",
   "kind": "code",
   "size": "small",
   "deps": [],
   "files": [
    "z-skills/_shared/handoff.py",
    "z-skills/_shared/flash_pin.py",
    "z-skills/_shared/zai_client.py",
    "z-skills/_shared/tests/test_flash_pin_pro.py",
    "z-skills/z-brainstorming/scripts/handoff.py",
    "z-skills/z-dev-team/scripts/handoff.py",
    "z-skills/z-dev-team/scripts/flash_pin.py",
    "z-skills/z-doc-generator/scripts/handoff.py",
    "z-skills/z-git-diff-summary/scripts/handoff.py",
    "z-skills/z-idea-to-spec/scripts/handoff.py",
    "z-skills/z-requirements-code-audit/scripts/handoff.py",
    "z-skills/z-requirements-code-audit/scripts/flash_pin.py",
    "z-skills/z-requirements-code-audit/scripts/zai_client.py",
    "z-skills/z-systematic-debugging/scripts/handoff.py",
    "z-skills/z-systematic-debugging/scripts/flash_pin.py",
    "z-skills/z-systematic-debugging/scripts/zai_client.py",
    "z-skills/z-writing-plans/scripts/handoff.py",
    "z-skills/z-writing-plans/scripts/flash_pin.py",
    "z-skills/z-writing-plans/scripts/zai_client.py"
   ],
   "risk": "low",
   "isolation": false,
   "criteria": [
    "test_flash_pin_pro.py reports OK, and from_env and from_file both return glm for the pin word glm-5.4",
    "resolve_http_model returns glm-5.4 for every model under a glm-5.4 pin, and PRO_API maps glm-5.4 to glm-5.4",
    "the single GUARD flash line names GLM 5.4 next to the other five session models and keeps the words never promote a lane to another model",
    "sh _shared/sync.sh re-vendors the shared scripts, and test_vendored.py and test_all_skills.py both report OK afterwards"
   ],
   "edge_cases": [
    "an unknown pin word such as nonsense still resolves to glm",
    "the flash words glm, flash, glm-5.3-flash and deepseek keep their behavior: the FlashTierUnchanged tests still pass"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-25-six-session-models-and-audit.md",
    "z-skills/_shared/flash_pin.py",
    "z-skills/_shared/handoff.py",
    "z-skills/_shared/zai_client.py",
    "z-skills/_shared/tests/test_flash_pin_pro.py"
   ]
  },
  {
   "id": "S2",
   "title": "vocabulary pivot - every enumeration, pinned sentence and its tests",
   "goal": "Follow the T02 body in the plan file step by step. Step 1 (the three test modules) is the RED side: commit it with commit-red as test(S2): six-model vocabulary tests. Step 3 (the prose edits) is the GREEN side: commit every other path in the T02 Files list with commit-green as feat(S2): six-model vocabulary across every skill.",
   "kind": "code",
   "size": "large",
   "deps": [],
   "files": [
    "z-skills/AGENTS.md",
    "z-skills/z-brainstorming/SKILL.md",
    "z-skills/z-dev-team/SKILL.md",
    "z-skills/z-doc-generator/SKILL.md",
    "z-skills/z-find-skills/SKILL.md",
    "z-skills/z-git-diff-summary/SKILL.md",
    "z-skills/z-idea-to-spec/SKILL.md",
    "z-skills/z-requirements-code-audit/SKILL.md",
    "z-skills/z-systematic-debugging/SKILL.md",
    "z-skills/z-writing-plans/SKILL.md",
    "z-skills/z-brainstorming/z-tuning.md",
    "z-skills/z-writing-plans/references/z-tuning.md",
    "z-skills/z-requirements-code-audit/references/z-tuning.md",
    "z-skills/z-systematic-debugging/references/z-tuning.md",
    "z-skills/z-systematic-debugging/README.md",
    "z-skills/z-brainstorming/visual-companion.md",
    "z-skills/z-brainstorming/agents/z-drafter.md",
    "z-skills/z-brainstorming/agents/z-design-breaker.md",
    "z-skills/z-brainstorming/CHANGELOG.md",
    "z-skills/z-writing-plans/CHANGELOG.md",
    "z-skills/_shared/tests/test_all_skills.py",
    "z-skills/_shared/tests/test_model_terms_bodies.py",
    "z-skills/_shared/tests/test_model_terms_tuning.py"
   ],
   "risk": "low",
   "isolation": false,
   "criteria": [
    "test_all_skills.py, test_model_terms_bodies.py and test_model_terms_tuning.py all report OK",
    "the models line of each of the nine non-video SKILL.md files reads glm-5.3-flash | deepseek-flash | glm-5.3 | glm-5.4 | deepseek-v4-pro | claude-sonnet-5.5",
    "each of the four z-tuning.md tables carries the row | GLM 5.4 | pro tier | and a note dated 2026-11-25, and no table row for a new tier model carries a price or a speed number",
    "AGENTS.md says six session models, and no non-CHANGELOG Markdown file under the nine skills says five session models, Five display names or four session models",
    "each edit script stops without writing when an anchor is not found exactly once, and both scripts report their edited counts",
    "the description of z-requirements-code-audit/SKILL.md keeps its measured length because GLM requests became API requests"
   ],
   "edge_cases": [
    "the z-writing-plans CHANGELOG entry dated 2026-11-19 stays as history and still matches the pro-pin wording delivered that day",
    "agent files keep their thoughtLevel line and gain no model line",
    "the brainstorming tuning doc keeps the phrases ZCode runtime, NEW ZCode session and no `!` preload support"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-25-six-session-models-and-audit.md",
    "z-skills/_shared/tests/test_all_skills.py",
    "z-skills/_shared/tests/test_model_terms_bodies.py",
    "z-skills/_shared/tests/test_model_terms_tuning.py",
    "z-skills/AGENTS.md"
   ]
  },
  {
   "id": "S3",
   "title": "installer keeps a saved pro pin word and learns glm-5.4",
   "goal": "Follow the T03 body in the plan file step by step. Step 1 (the test replacement) is the RED side: commit it with commit-red as test(S3): installer keeps a saved pro pin word. Step 3 (the three installer edits) is the GREEN side: commit it with commit-green as fix(S3): installer keeps a saved pro pin word and knows glm-5.4.",
   "kind": "code",
   "size": "small",
   "deps": [],
   "files": [
    "z-skills/install-zcode.sh",
    "z-skills/_shared/tests/test_install_zcode.py"
   ],
   "risk": "low",
   "isolation": true,
   "criteria": [
    "test_install_zcode.py reports OK",
    "a pin file that holds deepseek-v4-pro or glm-5.4 still holds that word after a re-install without --flash, and the output still says pin: deepseek or pin: glm",
    "an explicit --flash flag replaces a saved pro word, and an unknown saved word falls back to glm"
   ],
   "edge_cases": [
    "the installer still refuses an unknown --flash value and still writes nothing on --dry-run"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-25-six-session-models-and-audit.md",
    "z-skills/install-zcode.sh",
    "z-skills/_shared/tests/test_install_zcode.py"
   ]
  },
  {
   "id": "S4",
   "title": "dev-team engine prints routing that follows the session model",
   "goal": "Follow the T04 body in the plan file step by step. Step 1 (the new test file) is the RED side: commit it with commit-red as test(S4): engine routing text follows the session model. Step 3 (the fourteen text edits) is the GREEN side: commit it with commit-green as fix(S4): dev-team engine prints routing that follows the session model.",
   "kind": "code",
   "size": "small",
   "deps": [],
   "files": [
    "z-skills/z-dev-team/scripts/devteam.py",
    "z-skills/z-dev-team/scripts/selftest.sh",
    "z-skills/_shared/tests/test_devteam_wording.py"
   ],
   "risk": "low",
   "isolation": false,
   "criteria": [
    "test_devteam_wording.py reports OK and the engine carries no stale pinned-model wording",
    "the engine PROVIDER line ends with every lane follows the session model and names no model id",
    "bash z-dev-team/scripts/selftest.sh ends with failed=0 and exits 0"
   ],
   "edge_cases": [
    "the engine keeps its provider labels and its routing behavior: only the wording of docstrings, comments and printed lines changes"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-25-six-session-models-and-audit.md",
    "z-skills/z-dev-team/scripts/devteam.py",
    "z-skills/z-dev-team/scripts/selftest.sh"
   ]
  },
  {
   "id": "S5",
   "title": "plan tool doctor prints the effort each tier sets",
   "goal": "Follow the T05 body in the plan file step by step. Step 1 (the new test file) is the RED side: commit it with commit-red as test(S5): doctor models row follows the tier table. Step 3 (the doctor line) is the GREEN side: commit it with commit-green as fix(S5): plan tool doctor prints the effort each tier sets.",
   "kind": "code",
   "size": "small",
   "deps": [],
   "files": [
    "z-skills/z-writing-plans/scripts/plan_tool.py",
    "z-skills/_shared/tests/test_plan_doctor.py"
   ],
   "risk": "low",
   "isolation": false,
   "criteria": [
    "test_plan_doctor.py reports Ran 2 tests and OK",
    "the doctor models row prints light=glm-5.3-flash/high, the effort the tier table sets, instead of a hardcoded low"
   ],
   "edge_cases": [
    "doctor without a key still exits 1 after printing its rows"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-25-six-session-models-and-audit.md",
    "z-skills/z-writing-plans/scripts/plan_tool.py"
   ]
  },
  {
   "id": "S6",
   "title": "guard against broken bundled-path references in every skill",
   "goal": "Follow the T06 body in the plan file step by step: the stub file and its failing scanner tests first, then the real scanner. This slice is tests only, so make one commit with commit-work as test(S6): guard against broken bundled-path references in skills.",
   "kind": "test",
   "size": "small",
   "deps": [],
   "files": [
    "z-skills/_shared/tests/test_skill_references.py"
   ],
   "risk": "low",
   "isolation": true,
   "criteria": [
    "test_skill_references.py reports Ran 6 tests and OK",
    "the scanner reports a missing bundled path and a path into a skill that does not exist, and ignores a word pair followed by a comma",
    "every Markdown file under the nine non-video skills names only bundled paths that exist"
   ],
   "edge_cases": [
    "an empty text reports nothing",
    "a path into another skill is resolved from the repository root"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-25-six-session-models-and-audit.md"
   ]
  }
 ]
}
```
