# Writer brief: {TASKS}

You write the body of plan task(s) {TASKS}. Contracts are locked. Your job: correct, complete, real content, in as few turns as possible. This brief contains everything you need (contract, spec excerpt, existing files).

OUT (one file per task):
{OUT}

LINT: `{LINT}`

**HARD RULE - speed:** your only reads are this brief and the files under "Read before writing" (if that section exists). Do not open the lint script, the plan, the spec or any other file, and do not run searches: the Rules section below is the complete lint specification and everything else you need is inlined here.

## Procedure (target: 3 turns)

1. If a "Read before writing" section exists below, Read all of those files in ONE message of parallel Reads. Otherwise go straight to step 2.
2. Write every OUT file (one Write per task; several tasks -> all Writes in ONE message).
3. Lint. If the Write result already shows a `plan-lint:` note, that note IS the lint result. Otherwise run LINT with one Bash call. On `ERR`: fix with Edit, lint again (max 3 rounds). Fix `WARN` lines too when they are real problems.
4. Reply with exactly one line per task: `T07 OK` or `T07 FAIL: <first error>`. Never echo the body.

## Body format (the script adds heading, Depends, Runs after and Interfaces - do NOT write them)

````markdown
**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test_file.py`

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/exact/path/to/test_file.py::test_specific_behavior -v`
Expected: FAIL with "NameError: name 'function' is not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/exact/path/to/test_file.py::test_specific_behavior -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/exact/path/to/test_file.py exact/path/to/file.py
git commit -m "feat: add specific behavior"
```
````

Several behaviors: repeat steps 1-4 per behavior, then one commit step. Number steps 1..N.

## Rules (the linter enforces the starred ones - get them right first time)

- * `**Files:**` lists every contract Files path and nothing else (another task may own other files): one path per line as `- Create|Modify|Test: \`path\``, optional `:start-end` range from the inlined line numbers. A file that does not exist yet is `Create`/`Test`, never `Modify`.
- * Every contract `Produces` signature appears verbatim in your code. Call consumed signatures exactly as written.
- * Every `Run:` is followed by `Expected:` (exact output or failure message).
- * `git add` names explicit paths from Files only - never `.`, `-A`, globs.
- * Code blocks must parse (Python, JSON, TOML, bash, JS are syntax-checked). A deliberately partial snippet opens its fence as ```` ```python fragment ````.
- * No `#`, `##` or `###` headings. Banned: `TBD`, `TODO`, `FIXME`, "implement later", "add appropriate error handling/validation", "handle edge cases", "similar to Task N", tests described but not written.
- * Portable: plain instructions and shell commands only. Never mention skills, subagents, plugins, slash commands, vendor tools, or any AI product.
- Real, complete code in every code step (full tests, full implementation). The implementer sees ONLY this task.
- TDD per behavior: failing test -> run (expected failure) -> minimal implementation -> run (expected pass) -> commit. Bite-sized steps (2-5 min, one action each).
- Follow the patterns in the inlined files (imports, test framework, naming). Global Constraints apply to every line.
- "Runs after" tasks edit the same files before you: write Modify steps that remain valid after their changes (anchor on code, not only line numbers).
- Use only symbols from your contract, consumed signatures, Global Constraints, or the files shown.
