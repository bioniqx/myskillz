# SLOW Asks and Waits Implementation Plan

> **Execution note:** This plan is self-contained and tool-agnostic. Any AI
> agent or human engineer can execute it with only a shell, a code editor, and
> git. Follow the Execution Protocol below.

**Goal:** Under SLOW the seven skills ask the user instead of deciding: nothing is assumed, no 15-minute pick exists, and a question ends the turn. FAST is unchanged.

**Out of scope:** FAST (fast.md, every FAST branch string, `ask.py fast`, `force_pick`, the FAST timeout pick of `ask.py wait`), the `mode` subcommand of ask.py, the engine caps (falsifier, claim, mutant), z-idea-to-spec and z-find-skills behavior, the two video skills, the vendored gamedev bundle, the sibling repos, installing into a harness home.

**Rollback:** git revert the task commits in reverse order; no migration, no data change, no install step.

**Architecture:** One sentence (SLOW_ASK) is defined once in the shared prelude. It is appended at the single point where `open` prints the prelude line, when the stamp of one of the seven SLOW skills is slow, so no SLOW branch can be missed; the sync script re-vendors the file into eight copies. One shared reader, `brainstorm_mode()`, feeds three gates in the z-brainstorming scripts: the wait has no deadline under SLOW, `approve` refuses an AUTO block, and `send` has no four-question cap. The rule text is rewritten in place, tests first.

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
- Run every test and script command from inside z-skills; work on main; never create a branch.
- `git add` names exact paths from the task's Files list only, never `.` or `-A`; exactly one `git commit` per task, staged from the repository root with `cd ..`.
- Every SKILL.md edit keeps frontmatter `name` equal to the directory name and `description` at 1024 characters or fewer; z-brainstorming/SKILL.md is 504 lines today and must not grow.
- FAST branch strings, fast.md, and the `fast` and `mode` subcommands of ask.py are not edited.
- After any edit to _shared/handoff.py, run `sh _shared/sync.sh` from z-skills and commit the vendored copies in the same task.
- A test assertion is edited only where a task says so, and the reason is always the changed requirement or a test that read the real repository's stamp; no test is deleted, skipped or loosened.
- New text in non-Markdown files is plain ASCII English; Markdown files keep the characters they already use.
- Every edit script in this plan reads a file, requires the old text to appear exactly once, replaces it and writes the file back; it stops with a message when an anchor is missing. Run a script from inside z-skills with `cd z-skills && python3 - <<'PY'`, paste the block, and close it with a line that holds only `PY`.
- Full suite, run from z-skills: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
- Hygiene suite, run from z-skills: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py`

## References

- `z-skills/_shared/tests/test_decide.py` - the patch seam for a test that must not read the real repository: `mock.patch.object(decide.urllib.request, "urlopen")` replaces a name inside the module under test.
- `z-skills/_shared/tests/test_handoff.py` - the in-process import idiom for the shared prelude: `sys.path.insert(0, os.path.join(HERE, ".."))`, then `import handoff` inside the test.

## File Structure

- `z-skills/_shared/` — handoff.py (T01)
- `z-skills/_shared/tests/` — test_handoff.py (T01), test_z_brainstorm_check.py (T02), test_brainstorm_ask.py (T03)
- `z-skills/z-brainstorming/scripts/` — handoff.py (T01), check.py (T02), ask.py (T03)
- `z-skills/z-dev-team/scripts/` — handoff.py (T01)
- `z-skills/z-doc-generator/scripts/` — handoff.py (T01)
- `z-skills/z-git-diff-summary/scripts/` — handoff.py (T01)
- `z-skills/z-idea-to-spec/scripts/` — handoff.py (T01)
- `z-skills/z-requirements-code-audit/scripts/` — handoff.py (T01)
- `z-skills/z-systematic-debugging/scripts/` — handoff.py (T01)
- `z-skills/z-writing-plans/scripts/` — handoff.py (T01)
- `z-skills/z-brainstorming/` — SKILL.md (T04), architectural.md (T05), fanout-playbook.md (T05), research-playbook.md (T05), spec-document-reviewer-prompt.md (T05), CHANGELOG.md (T06)
- `z-skills/z-dev-team/` — SKILL.md (T06)
- `z-skills/z-writing-plans/` — SKILL.md (T06), CHANGELOG.md (T06)
- `z-skills/z-systematic-debugging/` — SKILL.md (T06)
- `z-skills/z-requirements-code-audit/` — SKILL.md (T06)
- `z-skills/z-doc-generator/` — SKILL.md (T06)
- `z-skills/z-git-diff-summary/` — SKILL.md (T06)

## Contracts

#### T01: shared prelude - SLOW_ASK on every SLOW NEXT line and one stamp reader
- Files: `z-skills/_shared/handoff.py`, `z-skills/_shared/tests/test_handoff.py`, `z-skills/z-brainstorming/scripts/handoff.py`, `z-skills/z-dev-team/scripts/handoff.py`, `z-skills/z-doc-generator/scripts/handoff.py`, `z-skills/z-git-diff-summary/scripts/handoff.py`, `z-skills/z-idea-to-spec/scripts/handoff.py`, `z-skills/z-requirements-code-audit/scripts/handoff.py`, `z-skills/z-systematic-debugging/scripts/handoff.py`, `z-skills/z-writing-plans/scripts/handoff.py`
- Produces: `SLOW_ASK = (`; `def slow_next(text):`; `def brainstorm_mode():`; `def test_brainstorm_mode_reads_the_brainstorm_stamp_first(self):`
- Consumes: `def read_mode_stamp():` (existing), `def _brainstorm_stamped():` (existing)
- Read: `z-skills/_shared/handoff.py`, `z-skills/_shared/tests/test_handoff.py`, `z-skills/_shared/tests/test_mode_of.py`
- Spec: L24-51, L54-61, L73-75, L91-94, L135-138, L212-213, L219-220, L223-232
- Tier: std

#### T02: z-brainstorming gate script - approve and send read the stamp
- Files: `z-skills/z-brainstorming/scripts/check.py`, `z-skills/_shared/tests/test_z_brainstorm_check.py`
- Produces: `from handoff import brainstorm_mode`; `class StampGateTests(unittest.TestCase):`
- Consumes: `def brainstorm_mode():`
- Read: `z-skills/z-brainstorming/scripts/check.py`, `z-skills/_shared/tests/test_z_brainstorm_check.py`
- Spec: L69-72, L141-143, L186, L216-218
- Tier: std

#### T03: z-brainstorming wait script - no deadline under SLOW
- Files: `z-skills/z-brainstorming/scripts/ask.py`, `z-skills/_shared/tests/test_brainstorm_ask.py`
- Produces: `from handoff import brainstorm_mode, mode_of, read_mode_stamp`; `def wait_deadline(timeout, mode):`; `def test_a_slow_wait_never_picks(self):`; `def test_the_auto_block_is_refused_under_a_slow_stamp(self):`
- Consumes: `def brainstorm_mode():`, `from handoff import brainstorm_mode`
- Read: `z-skills/z-brainstorming/scripts/ask.py`, `z-skills/_shared/tests/test_brainstorm_ask.py`
- Spec: L64-68, L139-140, L172-181, L184-185, L192-194, L200-208, L214-215
- Tier: std

#### T04: z-brainstorming body - nine sentences and one deletion
- Files: `z-skills/z-brainstorming/SKILL.md`
- Produces: `## R6 — Ask, then wait (SLOW)`; `Under SLOW nothing is assumed: ask, then end the turn and wait for the reply.`
- Spec: L1-23, L78-79, L95-96, L101-127, L144-158, L230
- Tier: light

#### T05: z-brainstorming references - the split path, the playbooks and the review prompt
- Files: `z-skills/z-brainstorming/architectural.md`, `z-skills/z-brainstorming/fanout-playbook.md`, `z-skills/z-brainstorming/research-playbook.md`, `z-skills/z-brainstorming/spec-document-reviewer-prompt.md`
- Produces: `Send the questions right away and end the`; `Assumptions — none under SLOW; every open point is a question in the`
- Spec: L80-84, L128-130, L159-165
- Tier: light

#### T06: six pointer sentences, the dev-team stop and two changelogs
- Files: `z-skills/z-dev-team/SKILL.md`, `z-skills/z-writing-plans/SKILL.md`, `z-skills/z-systematic-debugging/SKILL.md`, `z-skills/z-requirements-code-audit/SKILL.md`, `z-skills/z-doc-generator/SKILL.md`, `z-skills/z-git-diff-summary/SKILL.md`, `z-skills/z-brainstorming/CHANGELOG.md`, `z-skills/z-writing-plans/CHANGELOG.md`
- Produces: `Under SLOW this step is a stop: ask every blocking question and every assumption the`; `# 10.14 (from 10.13) — 2026-11-26: SLOW asks and waits`; `**SLOW asks and waits (2026-11-26):**`
- Spec: L85-87, L97-100, L166-175, L187-191, L224-229, L233-271
- Tier: light

#### T07: z-brainstorming chain - a SLOW run is recorded as slow
- Files: `z-skills/z-brainstorming/scripts/ask.py`, `z-skills/_shared/tests/test_brainstorm_ask.py`, `z-skills/z-brainstorming/CHANGELOG.md`
- Produces: `def test_a_slow_stamp_writes_a_slow_chain(self):`
- Read: `z-skills/z-brainstorming/scripts/ask.py`, `z-skills/_shared/tests/test_brainstorm_ask.py`
- Spec: L63-78
- Tier: std

<!-- WAVES -->
## Execution Waves

Every task in a wave has all its Depends/Runs-after tasks in earlier waves. Tasks in the
same wave touch disjoint files, so a wave's `[P]` tasks may all run at once.

- **Wave 1:** T01 [P], T04 [P], T05 [P], T06 [P]
- **Wave 2:** T02
- **Wave 3:** T03
- **Wave 4:** T07
<!-- /WAVES -->

<!-- TASKS -->

### T01: shared prelude - SLOW_ASK on every SLOW NEXT line and one stamp reader [P]

**Depends:** —

**Interfaces:**
- Uses existing: `def read_mode_stamp():`; `def _brainstorm_stamped():`
- Produces: `SLOW_ASK = (`; `def slow_next(text):`; `def brainstorm_mode():`; `def test_brainstorm_mode_reads_the_brainstorm_stamp_first(self):`

**Files:**
- Modify: `z-skills/_shared/handoff.py`
- Modify: `z-skills/_shared/tests/test_handoff.py`
- Modify: `z-skills/z-brainstorming/scripts/handoff.py`
- Modify: `z-skills/z-dev-team/scripts/handoff.py`
- Modify: `z-skills/z-doc-generator/scripts/handoff.py`
- Modify: `z-skills/z-git-diff-summary/scripts/handoff.py`
- Modify: `z-skills/z-idea-to-spec/scripts/handoff.py`
- Modify: `z-skills/z-requirements-code-audit/scripts/handoff.py`
- Modify: `z-skills/z-systematic-debugging/scripts/handoff.py`
- Modify: `z-skills/z-writing-plans/scripts/handoff.py`

- [ ] **Step 1: Write the failing tests**

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


T = "_shared/tests/test_handoff.py"
edit(T, '        self.assertIn("PACE: slow", nxt)\n        self.assertNotIn("read fast.md", nxt)\n',
     '        self.assertIn("PACE: slow", nxt)\n'
     '        self.assertIn("never an assumption", nxt)\n'
     '        self.assertNotIn("read fast.md", nxt)\n')
edit(T, '        self.assertIn("route-first rule", self.binding_next(out))\n'
        '        self.assertNotIn("PACE: slow", out)\n',
     '        self.assertIn("route-first rule", self.binding_next(out))\n'
     '        self.assertNotIn("PACE: slow", out)\n'
     '        self.assertNotIn("never an assumption", self.binding_next(out))\n')
NEW = '''class BrainstormModeTests(unittest.TestCase):
    """brainstorm_mode: mode.json wins, else the repo stamp, else an empty string."""

    def chdir_repo(self, *stamps):
        root = tempfile.mkdtemp(prefix="stamp-")
        self.addCleanup(shutil.rmtree, root, True)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(root)
        for rel, body in stamps:
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)

    def mode(self):
        sys.path.insert(0, os.path.join(HERE, ".."))
        import handoff
        return handoff.brainstorm_mode()

    def test_no_stamp_is_empty(self):
        self.chdir_repo()
        self.assertEqual(self.mode(), "")

    def test_brainstorm_mode_reads_the_brainstorm_stamp_first(self):
        self.chdir_repo((".brainstorm/drafts/mode.json", '{"mode": "fast"}\\n'),
                        (".claude/dev-team/mode", "slow 1\\n"))
        self.assertEqual(self.mode(), "fast")

    def test_the_repo_stamp_is_read_when_mode_json_is_absent(self):
        self.chdir_repo((".claude/dev-team/mode", "slow 1795679871\\n"))
        self.assertEqual(self.mode(), "slow")

    def test_a_stored_normal_is_empty(self):
        self.chdir_repo((".brainstorm/drafts/mode.json", '{"mode": "normal"}\\n'))
        self.assertEqual(self.mode(), "")


'''
edit(T, "def _note_files():", NEW + "def _note_files():")
print("edited 3 test anchors")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 3 test anchors`

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_handoff.py -k SlowModeTests -k BrainstormModeTests`
Expected: FAILED (failures=8, errors=4) - every SLOW branch lacks the sentence `never an assumption`, and `handoff` has no `brainstorm_mode`

- [ ] **Step 3: Add the sentence and the stamp reader**

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


S = "_shared/handoff.py"
NEW_BLOCK = '''# --- SLOW human gate: ask, then wait ------------------------------------------
# One sentence, printed at the end of every SLOW NEXT line the prelude returns.
SLOW_ASK = ("SLOW asks: anything a tool result in this session or the user's own "
            "words has not settled is a question for the user, never an assumption, "
            "and there is no cap of four. Ask, then end the turn and wait for the "
            "reply: no timer, no default, no pick.")


def slow_next(text):
    """A SLOW NEXT line ends with SLOW_ASK. FAST lines never pass through here."""
    return "%s %s" % (text, SLOW_ASK)


def brainstorm_mode():
    """The brainstorming stamp: fast, slow, or empty.

    mode.json wins over the repo stamp, the order the mode subcommand of
    ask.py reads them in.
    """
    kind = _brainstorm_stamped() or read_mode_stamp()
    return kind if kind in ("fast", "slow") else ""


'''
edit(S, "def _slow_fit_next(width, scripts, self_name):",
     NEW_BLOCK + "def _slow_fit_next(width, scripts, self_name):")
edit(S, '    rc, nxt = _prelude(args, text)\n    print("PRELUDE-RC %d" % rc)\n',
     '    rc, nxt = _prelude(args, text)\n'
     '    if args.self in RING and read_mode_stamp() == "slow":\n'
     '        nxt = slow_next(nxt)\n'
     '    print("PRELUDE-RC %d" % rc)\n')
print("edited 2 source anchors")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 2 source anchors`

- [ ] **Step 4: Re-vendor the shared file**

Run: `cd z-skills && sh _shared/sync.sh`
Expected: 22 lines, each starting with `synced z-`

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_handoff.py -k SlowModeTests -k BrainstormModeTests`
Expected: OK

- [ ] **Step 6: Prove the copies match and the suite is green**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_vendored.py`
Expected: OK

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK

- [ ] **Step 7: Commit**

```bash
cd .. && git add z-skills/_shared/handoff.py z-skills/_shared/tests/test_handoff.py z-skills/z-brainstorming/scripts/handoff.py z-skills/z-dev-team/scripts/handoff.py z-skills/z-doc-generator/scripts/handoff.py z-skills/z-git-diff-summary/scripts/handoff.py z-skills/z-idea-to-spec/scripts/handoff.py z-skills/z-requirements-code-audit/scripts/handoff.py z-skills/z-systematic-debugging/scripts/handoff.py z-skills/z-writing-plans/scripts/handoff.py
git commit -m "feat(handoff): SLOW NEXT lines end with the ask-then-wait sentence"
```

---

### T02: z-brainstorming gate script - approve and send read the stamp

**Depends:** T01

**Interfaces:**
- Consumes: `def brainstorm_mode():`
- Produces: `from handoff import brainstorm_mode`; `class StampGateTests(unittest.TestCase):`

**Files:**
- Modify: `z-skills/z-brainstorming/scripts/check.py`
- Modify: `z-skills/_shared/tests/test_z_brainstorm_check.py`

- [ ] **Step 1: Write the failing tests**

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


T = "_shared/tests/test_z_brainstorm_check.py"
edit(T, "import os\nimport subprocess\n", "import os\nimport shutil\nimport subprocess\n")
NEW = '''class StampGateTests(unittest.TestCase):
    """Under a slow stamp the gate never picks for the user: SLOW asks and waits."""

    AUTO = "AUTO\\nDECISION pick=A auto=1\\n"

    def repo(self, mode):
        """A temporary git repo whose brainstorming stamp is `mode`; None writes no stamp."""
        root = tempfile.mkdtemp(prefix="bs_stamp_")
        self.addCleanup(shutil.rmtree, root, True)
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        if mode is not None:
            os.makedirs(os.path.join(root, ".brainstorm", "drafts"))
            with open(os.path.join(root, ".brainstorm", "drafts", "mode.json"), "w",
                      encoding="utf-8") as fh:
                fh.write(json.dumps({"mode": mode}) + "\\n")
        return root

    def draft(self, count):
        return "Path unchanged: Architectural\\n\\n" + " ".join(
            "Q%d?" % number for number in range(1, count + 1)) + "\\n"

    def test_an_auto_block_is_refused_under_a_slow_stamp(self):
        rc, out = run(["approve", "--asked", "design"], self.AUTO, cwd=self.repo("slow"))
        self.assertEqual(rc, 1, out)
        self.assertIn("SLOW does not pick for the user", out)

    def test_an_auto_block_still_approves_under_a_fast_stamp(self):
        rc, out = run(["approve", "--asked", "design"], self.AUTO, cwd=self.repo("fast"))
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT approve yes", out)

    def test_an_auto_block_still_approves_with_no_stamp(self):
        rc, out = run(["approve", "--asked", "design"], self.AUTO, cwd=self.repo(None))
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT approve yes", out)

    def test_send_takes_six_questions_under_a_slow_stamp(self):
        rc, out = run(["send", "--root", "."], self.draft(6), cwd=self.repo("slow"))
        self.assertEqual(rc, 0, out)
        self.assertIn("RESULT send fail=0", out)

    def test_send_still_fails_five_questions_with_no_stamp(self):
        rc, out = run(["send", "--root", "."], self.draft(5), cwd=self.repo(None))
        self.assertEqual(rc, 1, out)
        self.assertIn("FAIL questions", out)


'''
edit(T, "class ApproveTests(unittest.TestCase):", NEW + "class ApproveTests(unittest.TestCase):")
print("edited 2 test anchors")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 2 test anchors`

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_z_brainstorm_check.py -k StampGateTests`
Expected: FAILED (failures=2) - under a slow stamp approve still prints `approve yes` for an AUTO block, and send still fails six question marks

- [ ] **Step 3: Teach the two gates the stamp**

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


C = "z-brainstorming/scripts/check.py"
edit(C, "import decide\n", "import decide\nfrom handoff import brainstorm_mode\n")
edit(C, "        if questions > 4:\n", '        if questions > 4 and brainstorm_mode() != "slow":\n')
edit(C, '    if re.search(r"(?m)^auto$", folded) and re.search(r"(?m)^decision pick=\\S+", folded):\n'
        '        print("RESULT approve yes")\n'
        '        return 0\n',
     '    if re.search(r"(?m)^auto$", folded) and re.search(r"(?m)^decision pick=\\S+", folded):\n'
     '        if brainstorm_mode() == "slow":\n'
     '            print("RESULT approve no - SLOW does not pick for the user; wait for the reply")\n'
     '            return 1\n'
     '        print("RESULT approve yes")\n'
     '        return 0\n')
print("edited 3 source anchors")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 3 source anchors`

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_z_brainstorm_check.py`
Expected: OK

- [ ] **Step 5: Commit**

```bash
cd .. && git add z-skills/z-brainstorming/scripts/check.py z-skills/_shared/tests/test_z_brainstorm_check.py
git commit -m "feat(z-brainstorming): approve and send read the SLOW stamp"
```

---

### T03: z-brainstorming wait script - no deadline under SLOW

**Depends:** T01, T02

**Interfaces:**
- Consumes: `def brainstorm_mode():`; `from handoff import brainstorm_mode`
- Produces: `from handoff import brainstorm_mode, mode_of, read_mode_stamp`; `def wait_deadline(timeout, mode):`; `def test_a_slow_wait_never_picks(self):`; `def test_the_auto_block_is_refused_under_a_slow_stamp(self):`

**Files:**
- Modify: `z-skills/z-brainstorming/scripts/ask.py`
- Modify: `z-skills/_shared/tests/test_brainstorm_ask.py`

- [ ] **Step 1: Write the failing test and isolate the two stamp-dependent tests**

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


T = "_shared/tests/test_brainstorm_ask.py"
edit(T, "import unittest\n\nHERE =", "import unittest\nfrom unittest import mock\n\nHERE =")
edit(T, '            self.ledger, self.options, self.reply, self.cancel, self.chain, now=5, deadline=1)\n'
        '        self.assertEqual(kind, "CANCEL")\n',
     '            self.ledger, self.options, self.reply, self.cancel, self.chain, now=5, deadline=1)\n'
     '        self.assertEqual(kind, "CANCEL")\n'
     '\n'
     '    def test_a_slow_wait_never_picks(self):\n'
     '        self.assertIsNone(ask.wait_deadline(900, "slow"))\n'
     '        self.assertEqual(ask.wait_deadline(900, "fast"), 900)\n'
     '        self.assertEqual(ask.wait_deadline(900, ""), 900)\n'
     '        kind = ask.resolve_once(\n'
     '            self.ledger, self.options, self.reply, self.cancel, self.chain,\n'
     '            now=10 ** 12, deadline=ask.wait_deadline(900, "slow"))\n'
     '        self.assertIsNone(kind)\n'
     '        self.assertFalse(os.path.exists(self.chain))\n')
edit(T, '        sys.stdout = buf\n'
        '        try:\n'
        '            rc = ask.cmd_mode(ns)\n'
        '        finally:\n'
        '            sys.stdin = old\n'
        '            sys.stdout = old_out\n'
        '        self.assertEqual(rc, 0)\n'
        '        self.assertEqual(json.load(open(dest))["mode"], "fast")\n',
     '        with mock.patch.object(ask, "read_mode_stamp", return_value=""):\n'
     '            sys.stdout = buf\n'
     '            try:\n'
     '                rc = ask.cmd_mode(ns)\n'
     '            finally:\n'
     '                sys.stdin = old\n'
     '                sys.stdout = old_out\n'
     '        self.assertEqual(rc, 0)\n'
     '        self.assertEqual(json.load(open(dest))["mode"], "fast")\n')
edit(T, '        sys.stdin = _In("AUTO\\nDECISION pick=A auto=1\\n")\n'
        '        try:\n'
        '            self.assertEqual(check.check_approve(ns), 0)\n'
        '        finally:\n'
        '            sys.stdin = old\n',
     '        sys.stdin = _In("AUTO\\nDECISION pick=A auto=1\\n")\n'
     '        try:\n'
     '            with mock.patch.object(check, "brainstorm_mode", return_value=""):\n'
     '                self.assertEqual(check.check_approve(ns), 0)\n'
     '        finally:\n'
     '            sys.stdin = old\n'
     '\n'
     '    def test_the_auto_block_is_refused_under_a_slow_stamp(self):\n'
     '        ns = type("N", (), {"asked": "design"})()\n'
     '        old = sys.stdin\n'
     '        sys.stdin = _In("AUTO\\nDECISION pick=A auto=1\\n")\n'
     '        try:\n'
     '            with mock.patch.object(check, "brainstorm_mode", return_value="slow"):\n'
     '                self.assertEqual(check.check_approve(ns), 1)\n'
     '        finally:\n'
     '            sys.stdin = old\n')
print("edited 4 test anchors")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 4 test anchors`

- [ ] **Step 2: Run the tests to verify the new one fails**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_brainstorm_ask.py`
Expected: FAILED (errors=1) - `ask` has no `wait_deadline`; the slow-stamp approve test already passes because T02 taught the gate the stamp

- [ ] **Step 3: Remove the deadline under SLOW**

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


A = "z-brainstorming/scripts/ask.py"
edit(A, "15-minute wait is unchanged: a stop or an unattacked leader is not a pick\nthere.",
     "Under SLOW the wait has no deadline and never picks. Under FAST the\n"
     "15-minute wait is unchanged: a stop or an unattacked leader is not a pick\nthere.")
edit(A, "from handoff import mode_of, read_mode_stamp\n",
     "from handoff import brainstorm_mode, mode_of, read_mode_stamp\n")
edit(A, "def resolve_once(ledger, options, reply, cancel, chain, now, deadline):",
     'def wait_deadline(timeout, mode):\n'
     '    """None under SLOW: the wait never ends on its own."""\n'
     '    return None if mode == "slow" else timeout\n'
     '\n'
     '\n'
     'def resolve_once(ledger, options, reply, cancel, chain, now, deadline):')
edit(A, "    if now < deadline:\n", "    if deadline is None or now < deadline:\n")
edit(A, "    deadline = clock() + timeout\n",
     "    deadline = None if timeout is None else clock() + timeout\n")
edit(A, "    kind, text = wait_loop(a.ledger, a.options, a.reply, a.cancel, a.chain, a.timeout)\n",
     "    timeout = wait_deadline(a.timeout, brainstorm_mode())\n"
     "    kind, text = wait_loop(a.ledger, a.options, a.reply, a.cancel, a.chain, timeout)\n")
print("edited 6 source anchors")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 6 source anchors`

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_brainstorm_ask.py`
Expected: OK

- [ ] **Step 5: Run the full suite**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK

- [ ] **Step 6: Commit**

```bash
cd .. && git add z-skills/z-brainstorming/scripts/ask.py z-skills/_shared/tests/test_brainstorm_ask.py
git commit -m "feat(z-brainstorming): the wait has no deadline under SLOW"
```

---

### T04: z-brainstorming body - nine sentences and one deletion [P]

**Depends:** —

**Interfaces:**
- Produces: `## R6 — Ask, then wait (SLOW)`; `Under SLOW nothing is assumed: ask, then end the turn and wait for the reply.`

**Files:**
- Modify: `z-skills/z-brainstorming/SKILL.md`

- [ ] **Step 1: Rewrite the sentences that turned a question into an assumption**

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


B = "z-brainstorming/SKILL.md"
POINTER = " Under SLOW nothing is assumed: ask, then end the turn and wait for the reply."
edit(B, "The default is FAST; SLOW starts only when the user says SLOW.",
     "The default is FAST; SLOW starts only when the user says SLOW." + POINTER)
edit(B, "   stdin is the human reply, or the `AUTO` block `ask.py` prints (R6, or the FAST pick inside `open`).\n",
     "   stdin is the human reply, or the AUTO block of the FAST pick inside `open`.\n")
edit(B, "6. Ask at most 4 forking questions; everything else is a vetoable\n   assumption.\n",
     "6. Under SLOW ask every unsettled point: there is no cap and nothing is\n   an assumption (R6).\n")
OLD_R6 = '''## R6 — Assume, do not ask

Human round-trips dominate wall-clock. An answer ≥80% likely from the
repo, conventions, research, or the request becomes a vetoable assumption
inside the design ("Assuming Postgres like the rest of `/services` — say
otherwise"). Ask only questions whose answer forks the design — and a decision
the whole design rests on, with no ≥80% answer in sight, IS a fork: ask it,
never pick silently. Batch ≤4. Whether a later reply is approval is
decided by `check.py approve`, not by how agreeable it sounds.
With AskUserQuestion make item 1 "Approve this design?" (Approve /
Approve with my answers below / Revise) so one reply both answers and
approves; otherwise ask in plain text.
Name the recommended option id in that message. In the same message
start `python3 <skill_dir>/scripts/ask.py wait --ledger .brainstorm/drafts/ledger.json --options .brainstorm/drafts/options.json --timeout 900`
with `run_in_background: true`, then end the turn. A chat reply before
it finishes: first call `ask.py cancel`, then `approve` on that reply.
The wait's `AUTO` block is the reply when 15 minutes pass with none:
pass that block to `approve`, render its pick, write the spec, and take
the R13 exit. `DECISION stop` or `ask=unattacked` is not a pick.
'''
NEW_R6 = '''## R6 — Ask, then wait (SLOW)

Nothing is assumed. A point is settled when a tool result in this session
or the user's own words decides it; anything else is a question, with no
cap of four. More than four questions: one numbered plain-text message.
Whether a reply is approval is decided by `check.py approve`, not by how
agreeable it sounds.
With AskUserQuestion make item 1 "Approve this design?" (Approve /
Approve with my answers below / Revise) so one reply both answers and
approves; otherwise ask in plain text.
Name the recommended option id in that message. In the same message
start `python3 <skill_dir>/scripts/ask.py wait --ledger .brainstorm/drafts/ledger.json --options .brainstorm/drafts/options.json`
with `run_in_background: true`, then end the turn. A chat reply before
it finishes: first call `ask.py cancel`, then `approve` on that reply.
The wait never picks: it returns REPLY or CANCEL only. `DECISION stop` or
`ask=unattacked` is not a pick.
'''
edit(B, OLD_R6, NEW_R6)
edit(B, "Unasked questions become assumptions (R6). Late results from the lanes",
     "Unasked questions are asked, not assumed (R6). Late results from the lanes")
edit(B, "becomes an assumption or one of the ≤4 questions, never a new exploration\n",
     "becomes a question for the user (R6), never a new exploration\n")
edit(B, "- \"I'll ask to be safe\" → a vetoable assumption costs zero turns; a\n  question costs one.\n",
     "- \"I'll assume to be safe\" → under SLOW the assumption is the cost; ask\n  (R6).\n")
edit(B, "  `ask.py chain --pick <id>` first. An automatic pick already wrote\n"
        "  `.brainstorm/drafts/chain.json`. Nothing else.\n",
     "  `ask.py chain --pick <id>` first. Nothing else.\n")
edit(B, "`ask` asks that one fork and arms `ask.py wait` (R6).",
     "`ask` asks that one fork and ends the turn (R6).")
edit(B, "3. A design message contains `Approve this design?`, an assumption, and Out of scope.",
     "3. A design message contains `Approve this design?`, an Assumptions section (none\n"
     "   under SLOW), and Out of scope.")
edit(B, "  out-of-scope line + Evidence if researched + assumptions + ≤4 forking\n  questions. Explicit\n",
     "  out-of-scope line + Evidence if researched, plus a question for every\n"
     "  unsettled point (R6).\n")
print("edited 11 anchors")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 11 anchors`

- [ ] **Step 2: Prove the file did not grow and the old wording is gone**

Run: `cd z-skills && wc -l z-brainstorming/SKILL.md`
Expected: `501 z-brainstorming/SKILL.md`

Run: `cd z-skills && grep -c "Under SLOW nothing is assumed" z-brainstorming/SKILL.md`
Expected: `1`

Run: `cd z-skills && ! grep -q -e "Assume, do not ask" -e "--timeout 900" -e "automatic pick" -e "≤4 forking" z-brainstorming/SKILL.md`
Expected: no output, exit status 0

- [ ] **Step 3: Run the hygiene suite**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py`
Expected: OK

- [ ] **Step 4: Commit**

```bash
cd .. && git add z-skills/z-brainstorming/SKILL.md
git commit -m "docs(z-brainstorming): R6 asks, then waits"
```

---

### T05: z-brainstorming references - the split path, the playbooks and the review prompt [P]

**Depends:** —

**Interfaces:**
- Produces: `Send the questions right away and end the`; `Assumptions — none under SLOW; every open point is a question in the`

**Files:**
- Modify: `z-skills/z-brainstorming/architectural.md`
- Modify: `z-skills/z-brainstorming/fanout-playbook.md`
- Modify: `z-skills/z-brainstorming/research-playbook.md`
- Modify: `z-skills/z-brainstorming/spec-document-reviewer-prompt.md`

- [ ] **Step 1: Ask instead of assume in every SLOW-only reference**

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


A = "z-brainstorming/architectural.md"
edit(A, "hard max 8) and must run in waves. Send questions + assumptions right away while lanes\n"
        "keep running; the user thinks while machines work. Next message is the\n",
     "hard max 8) and must run in waves. Send the questions right away and end the\n"
     "turn: under SLOW no lane runs while the user thinks. Next message is the\n")
edit(A, "7. Assumptions — every ≥80%-likely answer you did not ask about, one line\n"
        "   each, phrased so one \"yes\" confirms all of them.\n",
     "7. Assumptions — none under SLOW; every open point is a question in the\n"
     "   message.\n")
F = "z-brainstorming/fanout-playbook.md"
edit(F, "  only lanes whose answer the design still needs; otherwise convert to an\n"
        "  assumption.\n",
     "  only lanes whose answer the design still needs; otherwise ask the user\n"
     "  instead of assuming (SLOW).\n")
edit(F, "3. UNKNOWN or UNVERIFIED → an assumption, or one of the ≤4 questions. A\n",
     "3. UNKNOWN or UNVERIFIED → a question for the user (SLOW). A\n")
edit(F, "| Questions first (split) | all code + web lanes; unasked questions become assumptions |\n",
     "| Questions (SLOW) | nothing; the turn ends until the reply |\n")
R = "z-brainstorming/research-playbook.md"
edit(R, "a question cannot be asked without them, make it an assumption or ask the\nuser.\n",
     "a question cannot be asked without them, ask the user instead.\n")
edit(R, "items appear as assumptions the user can veto.\n",
     "items appear as open questions for the user.\n")
P = "z-brainstorming/spec-document-reviewer-prompt.md"
edit(P, "   unverified items are labeled as assumptions.\n",
     "   unverified items are labeled and asked.\n")
print("edited 8 anchors")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 8 anchors`

- [ ] **Step 2: Prove no reference turns a question into an assumption**

Run: `cd z-skills && ! grep -q "assumption" z-brainstorming/architectural.md z-brainstorming/fanout-playbook.md z-brainstorming/research-playbook.md z-brainstorming/spec-document-reviewer-prompt.md`
Expected: no output, exit status 0

Run: `cd z-skills && grep -c "SLOW" z-brainstorming/architectural.md z-brainstorming/fanout-playbook.md z-brainstorming/research-playbook.md z-brainstorming/spec-document-reviewer-prompt.md`
Expected: four lines; architectural.md and fanout-playbook.md count 2 or more, research-playbook.md and spec-document-reviewer-prompt.md may count 0

- [ ] **Step 3: Run the full suite**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK

- [ ] **Step 4: Commit**

```bash
cd .. && git add z-skills/z-brainstorming/architectural.md z-skills/z-brainstorming/fanout-playbook.md z-skills/z-brainstorming/research-playbook.md z-skills/z-brainstorming/spec-document-reviewer-prompt.md
git commit -m "docs(z-brainstorming): SLOW references ask instead of assuming"
```

---

### T06: six pointer sentences, the dev-team stop and two changelogs [P]

**Depends:** —

**Interfaces:**
- Produces: `Under SLOW this step is a stop: ask every blocking question and every assumption the`; `# 10.14 (from 10.13) — 2026-11-26: SLOW asks and waits`; `**SLOW asks and waits (2026-11-26):**`

**Files:**
- Modify: `z-skills/z-dev-team/SKILL.md`
- Modify: `z-skills/z-writing-plans/SKILL.md`
- Modify: `z-skills/z-systematic-debugging/SKILL.md`
- Modify: `z-skills/z-requirements-code-audit/SKILL.md`
- Modify: `z-skills/z-doc-generator/SKILL.md`
- Modify: `z-skills/z-git-diff-summary/SKILL.md`
- Modify: `z-skills/z-brainstorming/CHANGELOG.md`
- Modify: `z-skills/z-writing-plans/CHANGELOG.md`

- [ ] **Step 1: Extend the six pointers, add the dev-team stop, write the changelogs**

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


SENTENCE = " Under SLOW nothing is assumed: ask, then end the turn and wait for the reply."
STOP = "   Under SLOW this step is a stop: ask every blocking question and every assumption the plan lists in one message, start no lane before the reply, and stop the run the same way when a lane reports a blocking question.\n"
D = "z-dev-team/SKILL.md"
edit(D, "When the prelude prints `PACE: slow`, follow that `NEXT`; the slow branch replaces this routing.",
     "When the prelude prints `PACE: slow`, follow that `NEXT`; the slow branch replaces this routing." + SENTENCE)
edit(D, "   Launch everything `start` printed except slices the open questions would change.\n",
     "   Launch everything `start` printed except slices the open questions would change.\n" + STOP)
edit("z-writing-plans/SKILL.md",
     "`PACE: slow` never takes this inline path: when the prelude prints `PACE: slow`, follow that `NEXT`.",
     "`PACE: slow` never takes this inline path: when the prelude prints `PACE: slow`, follow that `NEXT`." + SENTENCE)
edit("z-systematic-debugging/SKILL.md",
     "When the prelude prints `PACE: slow`, follow that `NEXT`; the slow branch replaces this lane routing.",
     "When the prelude prints `PACE: slow`, follow that `NEXT`; the slow branch replaces this lane routing." + SENTENCE)
edit("z-requirements-code-audit/SKILL.md",
     "When the prelude prints `PACE: slow`, follow that `NEXT`; the short path is off and the four calls stay.",
     "When the prelude prints `PACE: slow`, follow that `NEXT`; the short path is off and the four calls stay." + SENTENCE)
edit("z-doc-generator/SKILL.md",
     "When the prelude prints `PACE: slow`, follow that `NEXT`. |",
     "When the prelude prints `PACE: slow`, follow that `NEXT`." + SENTENCE + " |")
edit("z-git-diff-summary/SKILL.md",
     "When the prelude prints `PACE: slow`, follow that `NEXT`. After the summary",
     "When the prelude prints `PACE: slow`, follow that `NEXT`." + SENTENCE + " After the summary")
ENTRY = '''# 10.14 (from 10.13) — 2026-11-26: SLOW asks and waits

Under SLOW nothing is assumed: every SLOW `NEXT` line the prelude prints
ends with one sentence that sends each unsettled point to the user and ends
the turn until the reply, with no cap of four. `ask.py wait` has no deadline
under SLOW and never picks; `check.py approve` refuses an AUTO block and
`check.py send` has no four-question cap under a slow stamp. R6 is retitled
"Ask, then wait", and R8, R11, the red flag and R13 no longer turn a question
into an assumption. Two tests that read the real repository's mode stamp now
state their own stamp. FAST is unchanged.

'''
edit("z-brainstorming/CHANGELOG.md", "# 10.13 (from 10.12) — 2026-11-25: audit fixes\n",
     ENTRY + "# 10.13 (from 10.12) — 2026-11-25: audit fixes\n")
edit("z-writing-plans/CHANGELOG.md",
     "# z-writing-plans v9 (GLM edition) - what changed from v8\n\n**Audit fixes (2026-11-25):**",
     "# z-writing-plans v9 (GLM edition) - what changed from v8\n\n"
     "**SLOW asks and waits (2026-11-26):** the R7 pointer says that under SLOW "
     "nothing is assumed: the run asks, then ends the turn and waits for the "
     "reply. No command changes.\n\n**Audit fixes (2026-11-25):**")
print("edited 10 anchors")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 10 anchors`

- [ ] **Step 2: Prove every pointer carries the sentence and no body grew past its limit**

Run: `cd z-skills && grep -c "Under SLOW nothing is assumed" z-dev-team/SKILL.md z-writing-plans/SKILL.md z-systematic-debugging/SKILL.md z-requirements-code-audit/SKILL.md z-doc-generator/SKILL.md z-git-diff-summary/SKILL.md`
Expected: six lines, each `z-<name>/SKILL.md:1`

Run: `cd z-skills && wc -l z-dev-team/SKILL.md z-writing-plans/SKILL.md z-systematic-debugging/SKILL.md z-requirements-code-audit/SKILL.md z-doc-generator/SKILL.md z-git-diff-summary/SKILL.md z-brainstorming/SKILL.md`
Expected: `260`, `240`, `140`, `221`, `405`, `112` and `501`, in that order, each followed by its path

- [ ] **Step 3: Run the hygiene suite, the full suite and the dev-team selftest**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py`
Expected: OK

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests`
Expected: OK

Run: `cd z-skills && bash z-dev-team/scripts/selftest.sh`
Expected: exit status 0 and no failed check line

Run: `cd z-skills && sh _shared/sync.sh && git status --short z-*/scripts/`
Expected: no line that starts with ` M`

- [ ] **Step 4: Commit**

```bash
cd .. && git add z-skills/z-dev-team/SKILL.md z-skills/z-writing-plans/SKILL.md z-skills/z-systematic-debugging/SKILL.md z-skills/z-requirements-code-audit/SKILL.md z-skills/z-doc-generator/SKILL.md z-skills/z-git-diff-summary/SKILL.md z-skills/z-brainstorming/CHANGELOG.md z-skills/z-writing-plans/CHANGELOG.md
git commit -m "docs(skills): SLOW pointer sentences, the dev-team stop, changelogs"
```

---

### T07: z-brainstorming chain - a SLOW run is recorded as slow

**Depends:** —

**Runs after:** T03, T06 (same files)

**Interfaces:**
- Produces: `def test_a_slow_stamp_writes_a_slow_chain(self):`

**Files:**
- Modify: `z-skills/z-brainstorming/scripts/ask.py`
- Modify: `z-skills/_shared/tests/test_brainstorm_ask.py`
- Modify: `z-skills/z-brainstorming/CHANGELOG.md`

- [ ] **Step 1: Write the failing test**

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


T = "_shared/tests/test_brainstorm_ask.py"
NEW = '''    def test_a_slow_stamp_writes_a_slow_chain(self):
        home = tempfile.mkdtemp(prefix="chain-slow-")
        cases = ((json.dumps({"mode": "slow"}), None), (None, "slow 1\\n"))
        for mode_file, stamp in cases:
            with self.subTest(stamp=stamp):
                mode = os.path.join(home, "mode.json")
                if mode_file is not None:
                    with open(mode, "w", encoding="utf-8") as fh:
                        fh.write(mode_file + "\\n")
                repo = tempfile.mkdtemp(prefix="chain-repo-")
                subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
                if stamp is not None:
                    os.makedirs(os.path.join(repo, ".claude", "dev-team"))
                    with open(os.path.join(repo, ".claude", "dev-team", "mode"), "w",
                              encoding="utf-8") as fh:
                        fh.write(stamp)
                dest = os.path.join(home, "chain.json")
                rc = subprocess.call(
                    [sys.executable, os.path.join(SCRIPTS, "ask.py"), "chain",
                     "--pick", "A", "--chain", dest, "--mode", mode],
                    stdout=subprocess.DEVNULL, cwd=repo)
                self.assertEqual(rc, 0)
                self.assertEqual(json.load(open(dest))["mode"], "slow")
'''
edit(T, '        self.assertTrue(json.load(open(dest))["continue"])\n',
     '        self.assertTrue(json.load(open(dest))["continue"])\n\n' + NEW)
print("edited 1 test anchor")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 1 test anchor`

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_brainstorm_ask.py`
Expected: FAILED (failures=2) - one per stamp case: under a mode.json stamp and under a repository stamp, chain records fast

- [ ] **Step 3: Read the stamps without the empty-text shortcut**

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


edit("z-brainstorming/scripts/ask.py",
     '    kind = mode_of("", _read_mode(a.mode) or read_mode_stamp())\n',
     "    kind = _read_mode(a.mode) or read_mode_stamp()\n")
edit("z-brainstorming/CHANGELOG.md", "state their own stamp. FAST is unchanged.\n",
     "state their own stamp. `ask.py chain` records a SLOW run as mode slow; it used to\n"
     "write fast. FAST is unchanged.\n")
print("edited 2 anchors")
```

Run: `cd z-skills && python3 - <<'PY'` with the block above
Expected: `edited 2 anchors`

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd z-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_brainstorm_ask.py`
Expected: OK

- [ ] **Step 5: Commit**

```bash
cd .. && git add z-skills/z-brainstorming/scripts/ask.py z-skills/_shared/tests/test_brainstorm_ask.py z-skills/z-brainstorming/CHANGELOG.md
git commit -m "fix(z-brainstorming): chain records a SLOW run as mode slow"
```

```json
{
 "request": "Under SLOW the seven z-skills that have a SLOW branch ask the user instead of deciding: nothing is assumed, no 15-minute pick exists, and a question ends the turn. FAST stays unchanged. Spec: docs/specs/2026-11-26-slow-asks-and-waits.md",
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
  "C1 SLOW_ASK: handoff.SLOW_ASK in z-skills/_shared/handoff.py, printed by slow_next(text) at the end of every SLOW NEXT line - established in S1, quoted word for word by S4 and S6",
  "C2 stamp reader: def brainstorm_mode(): in z-skills/_shared/handoff.py returns fast, slow or an empty string - established in S1, consumed by S2 and S3",
  "C3 wait deadline: def wait_deadline(timeout, mode): in z-skills/z-brainstorming/scripts/ask.py returns None under a slow stamp - established in S3",
  "C4 FAST is unchanged: no FAST branch string, fast.md, or the fast, mode and chain subcommands of ask.py is edited - binds every slice"
 ],
 "notes": "Work happens inside z-skills (suites run from there, never the repo root). The plan file is /Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-26-slow-asks-and-waits.md: each slice follows its own T body there, step by step. The bodies hold the exact edit scripts: run those scripts instead of retyping the edits. A script stops without writing when its anchor is not found exactly once. Git paths are staged from the repository root. A test assertion changes only where the T body says so. The SLOW branches are checked by tests that set their own stamp, so the run does not depend on the repository stamp.",
 "test_globs": [
  "_shared/tests/test_*.py"
 ],
 "slices": [
  {
   "id": "S1",
   "title": "shared prelude - SLOW_ASK on every SLOW NEXT line and one stamp reader",
   "goal": "Follow the T01 body in the plan file step by step. Step 1 (the test edits) is the RED side: commit it with commit-red as test(S1): SLOW NEXT lines end with the ask-then-wait sentence. The later steps are the GREEN side: apply the source edits, run the proof commands, then commit every other path in the T01 Files list with commit-green as feat(S1): SLOW NEXT lines end with the ask-then-wait sentence.",
   "kind": "code",
   "size": "small",
   "deps": [],
   "files": [
    "z-skills/_shared/handoff.py",
    "z-skills/_shared/tests/test_handoff.py",
    "z-skills/z-brainstorming/scripts/handoff.py",
    "z-skills/z-dev-team/scripts/handoff.py",
    "z-skills/z-doc-generator/scripts/handoff.py",
    "z-skills/z-git-diff-summary/scripts/handoff.py",
    "z-skills/z-idea-to-spec/scripts/handoff.py",
    "z-skills/z-requirements-code-audit/scripts/handoff.py",
    "z-skills/z-systematic-debugging/scripts/handoff.py",
    "z-skills/z-writing-plans/scripts/handoff.py"
   ],
   "risk": "low",
   "isolation": false,
   "criteria": [
    "test_handoff.py reports OK: every SLOW branch NEXT line contains never an assumption, the FAST branch line does not, and BrainstormModeTests pass",
    "SLOW_ASK reads word for word: SLOW asks: anything a tool result in this session or the user's own words has not settled is a question for the user, never an assumption, and there is no cap of four. Ask, then end the turn and wait for the reply: no timer, no default, no pick.",
    "brainstorm_mode returns fast when mode.json says fast and the repository stamp says slow, slow when only the repository stamp exists, and an empty string with no stamp or a stored normal",
    "sh _shared/sync.sh re-vendors the shared file, and test_vendored.py and the full suite report OK afterwards"
   ],
   "edge_cases": [
    "a skill without a SLOW branch never receives the sentence, because the append is guarded by RING",
    "the FAST branch strings are byte for byte unchanged"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-26-slow-asks-and-waits.md",
    "z-skills/_shared/handoff.py",
    "z-skills/_shared/tests/test_handoff.py",
    "z-skills/z-brainstorming/scripts/handoff.py",
    "z-skills/z-dev-team/scripts/handoff.py",
    "z-skills/z-doc-generator/scripts/handoff.py",
    "z-skills/z-git-diff-summary/scripts/handoff.py",
    "z-skills/z-idea-to-spec/scripts/handoff.py",
    "z-skills/z-requirements-code-audit/scripts/handoff.py",
    "z-skills/z-systematic-debugging/scripts/handoff.py",
    "z-skills/z-writing-plans/scripts/handoff.py"
   ]
  },
  {
   "id": "S2",
   "title": "z-brainstorming gate script - approve and send read the stamp",
   "goal": "Follow the T02 body in the plan file step by step. Step 1 (the test edits) is the RED side: commit it with commit-red as test(S2): approve and send read the SLOW stamp. The later steps are the GREEN side: apply the source edits, run the proof commands, then commit every other path in the T02 Files list with commit-green as feat(S2): approve and send read the SLOW stamp.",
   "kind": "code",
   "size": "small",
   "deps": [
    "S1"
   ],
   "files": [
    "z-skills/z-brainstorming/scripts/check.py",
    "z-skills/_shared/tests/test_z_brainstorm_check.py"
   ],
   "risk": "low",
   "isolation": false,
   "criteria": [
    "test_z_brainstorm_check.py reports OK, including the five StampGateTests",
    "under a slow stamp approve answers an AUTO block with RESULT approve no - SLOW does not pick for the user; wait for the reply and exits 1; under a fast stamp or no stamp it still answers approve yes",
    "under a slow stamp send accepts six question marks; with no stamp five question marks still fail"
   ],
   "edge_cases": [
    "the Vietnamese approval token and the bare 1 still approve, because only the AUTO branch changed"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-26-slow-asks-and-waits.md",
    "z-skills/z-brainstorming/scripts/check.py",
    "z-skills/_shared/tests/test_z_brainstorm_check.py"
   ]
  },
  {
   "id": "S3",
   "title": "z-brainstorming wait script - no deadline under SLOW",
   "goal": "Follow the T03 body in the plan file step by step. Step 1 (the test edits) is the RED side: commit it with commit-red as test(S3): the wait has no deadline under SLOW. The later steps are the GREEN side: apply the source edits, run the proof commands, then commit every other path in the T03 Files list with commit-green as feat(S3): the wait has no deadline under SLOW.",
   "kind": "code",
   "size": "small",
   "deps": [
    "S1",
    "S2"
   ],
   "files": [
    "z-skills/z-brainstorming/scripts/ask.py",
    "z-skills/_shared/tests/test_brainstorm_ask.py"
   ],
   "risk": "low",
   "isolation": false,
   "criteria": [
    "under a slow stamp the 15-minute pick is gone: the wait returns REPLY or CANCEL only and writes no chain",
    "test_brainstorm_ask.py reports OK, including test_a_slow_wait_never_picks",
    "wait_deadline returns None for slow and the given timeout for fast and for an empty stamp",
    "resolve_once with a None deadline returns None and writes no chain, however far the clock has moved",
    "the FAST timeout pick is unchanged: WaitTests and FastPickTests pass without an edit to their assertions",
    "test_cmd_mode_never_asks and test_the_auto_block_approves pass with no repository stamp, because each states its own stamp"
   ],
   "edge_cases": [
    "--timeout passed under a slow stamp is ignored",
    "an unreadable ledger or options file is no longer read by the wait under a slow stamp"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-26-slow-asks-and-waits.md",
    "z-skills/z-brainstorming/scripts/ask.py",
    "z-skills/_shared/tests/test_brainstorm_ask.py"
   ]
  },
  {
   "id": "S4",
   "title": "z-brainstorming body - nine sentences and one deletion",
   "goal": "Follow the T04 body in the plan file step by step: run the edit script, run the proof commands and the hygiene suite, then commit the one path in the T04 Files list with commit-work as docs(S4): R6 asks, then waits.",
   "kind": "docs",
   "size": "small",
   "deps": [],
   "files": [
    "z-skills/z-brainstorming/SKILL.md"
   ],
   "risk": "low",
   "isolation": false,
   "criteria": [
    "z-brainstorming/SKILL.md is 501 lines",
    "the R6 heading reads ## R6 — Ask, then wait (SLOW) and its body carries no --timeout 900 and no AUTO reply",
    "the strings Assume, do not ask, --timeout 900, automatic pick and ≤4 forking no longer occur in the file",
    "the pointer sentence Under SLOW nothing is assumed: ask, then end the turn and wait for the reply. occurs once",
    "the hygiene suite reports OK"
   ],
   "edge_cases": [
    "frontmatter name and description are untouched"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-26-slow-asks-and-waits.md",
    "z-skills/z-brainstorming/SKILL.md"
   ],
   "verify": "cd z-skills && grep -c \"Under SLOW nothing is assumed\" z-brainstorming/SKILL.md"
  },
  {
   "id": "S5",
   "title": "z-brainstorming references - the split path, the playbooks and the review prompt",
   "goal": "Follow the T05 body in the plan file step by step: run the edit script, run the proof commands and the full suite, then commit the four paths in the T05 Files list with commit-work as docs(S5): SLOW references ask instead of assuming.",
   "kind": "docs",
   "size": "small",
   "deps": [],
   "files": [
    "z-skills/z-brainstorming/architectural.md",
    "z-skills/z-brainstorming/fanout-playbook.md",
    "z-skills/z-brainstorming/research-playbook.md",
    "z-skills/z-brainstorming/spec-document-reviewer-prompt.md"
   ],
   "risk": "low",
   "isolation": false,
   "criteria": [
    "none of the four reference files contains the lowercase word assumption",
    "architectural.md says Send the questions right away and end the turn and Assumptions — none under SLOW; every open point is a question in the message",
    "the full suite reports OK"
   ],
   "edge_cases": [
    "fast.md is not edited"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-26-slow-asks-and-waits.md",
    "z-skills/z-brainstorming/architectural.md",
    "z-skills/z-brainstorming/fanout-playbook.md",
    "z-skills/z-brainstorming/research-playbook.md",
    "z-skills/z-brainstorming/spec-document-reviewer-prompt.md"
   ],
   "verify": "cd z-skills && ! grep -q assumption z-brainstorming/architectural.md z-brainstorming/fanout-playbook.md z-brainstorming/research-playbook.md z-brainstorming/spec-document-reviewer-prompt.md"
  },
  {
   "id": "S6",
   "title": "six pointer sentences, the dev-team stop and two changelogs",
   "goal": "Follow the T06 body in the plan file step by step: run the edit script, run the proof commands, the two suites and the dev-team selftest, then commit the eight paths in the T06 Files list with commit-work as docs(S6): SLOW pointer sentences, the dev-team stop, changelogs.",
   "kind": "docs",
   "size": "small",
   "deps": [],
   "files": [
    "z-skills/z-dev-team/SKILL.md",
    "z-skills/z-writing-plans/SKILL.md",
    "z-skills/z-systematic-debugging/SKILL.md",
    "z-skills/z-requirements-code-audit/SKILL.md",
    "z-skills/z-doc-generator/SKILL.md",
    "z-skills/z-git-diff-summary/SKILL.md",
    "z-skills/z-brainstorming/CHANGELOG.md",
    "z-skills/z-writing-plans/CHANGELOG.md"
   ],
   "risk": "low",
   "isolation": false,
   "criteria": [
    "each of the six SKILL.md files contains the pointer sentence exactly once",
    "z-dev-team/SKILL.md carries the sentence Under SLOW this step is a stop at the end of Pipeline step 4",
    "both changelogs carry an entry dated 2026-11-26",
    "the six body line counts are 259, 240, 140, 221, 405 and 112, and z-brainstorming/SKILL.md is 501 lines",
    "the full suite, the hygiene suite and the dev-team selftest report green, and sh _shared/sync.sh leaves no diff"
   ],
   "edge_cases": [
    "fast.md and the two skills without a SLOW branch are not edited"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-26-slow-asks-and-waits.md",
    "z-skills/z-dev-team/SKILL.md",
    "z-skills/z-writing-plans/SKILL.md",
    "z-skills/z-systematic-debugging/SKILL.md",
    "z-skills/z-requirements-code-audit/SKILL.md",
    "z-skills/z-doc-generator/SKILL.md",
    "z-skills/z-git-diff-summary/SKILL.md",
    "z-skills/z-brainstorming/CHANGELOG.md",
    "z-skills/z-writing-plans/CHANGELOG.md"
   ],
   "verify": "cd z-skills && grep -c \"Under SLOW nothing is assumed\" z-dev-team/SKILL.md z-writing-plans/SKILL.md z-systematic-debugging/SKILL.md z-requirements-code-audit/SKILL.md z-doc-generator/SKILL.md z-git-diff-summary/SKILL.md"
  },
  {
   "id": "S7",
   "title": "z-brainstorming chain - a SLOW run is recorded as slow",
   "goal": "Follow the T07 body in the plan file step by step. Step 1 (the new test) is the RED side: commit it with commit-red as test(S7): chain records a SLOW stamp. Steps 3 and 4 are the GREEN side: apply the two edits, then commit every other path in the T07 Files list with commit-green as fix(S7): chain records a SLOW run as mode slow.",
   "kind": "code",
   "size": "small",
   "deps": [
    "S3"
   ],
   "files": [
    "z-skills/z-brainstorming/scripts/ask.py",
    "z-skills/_shared/tests/test_brainstorm_ask.py",
    "z-skills/z-brainstorming/CHANGELOG.md"
   ],
   "risk": "low",
   "isolation": false,
   "criteria": [
    "test_brainstorm_ask.py reports OK, including test_a_slow_stamp_writes_a_slow_chain",
    "ask.py chain writes mode slow when mode.json or the repository stamp says slow"
   ],
   "edge_cases": [
    "no stamp and a stored normal still write no mode"
   ],
   "context": [
    "/Users/yamazaki-ethan/Documents/Projects/mine/skillz/z-skills/docs/plans/2026-11-26-slow-asks-and-waits.md",
    "z-skills/z-brainstorming/scripts/ask.py",
    "z-skills/_shared/tests/test_brainstorm_ask.py",
    "z-skills/z-brainstorming/CHANGELOG.md"
   ]
  }
 ]
}
```
