# Root-Cause Tracing

Use when the error surfaces deep in a call chain, far from where the bad value was created. Fixing where it surfaces treats a symptom.

## Procedure

1. **Symptom:** exact error + location. `Error: git init failed in ~/project/packages/core`
2. **Immediate cause:** the line that fails. `execFileAsync('git', ['init'], { cwd: projectDir })`
3. **Who called it, with what value?** Walk up the frames, recording the value at each hop:
   `WorktreeManager.create(projectDir='')` ← `Session.init()` ← `Session.create()` ← test `Project.create()`
4. **Keep going until the value is created, not just passed.** Here `setupCoreTest()` returned `{ tempDir: '' }` and the test read it before `beforeEach` ran. `cwd: ''` silently means `process.cwd()` → the source tree.
5. **Fix at the origin** (tempDir getter throws if read before setup), then consider guards on the path (`defense-in-depth.md`).

Parallel shortcut: in ONE round, Read all in-repo frames of the trace and Grep every call site of the suspicious function; the origin is usually visible without further rounds.

## When you cannot trace statically, instrument once

Log right BEFORE the dangerous operation, with the full stack and context:

```ts
console.error('DEBUG gitInit', { directory, cwd: process.cwd(), env: process.env.NODE_ENV, stack: new Error().stack });
```
```python
import traceback, sys, os; print('DEBUG', directory, os.getcwd(), ''.join(traceback.format_stack()), file=sys.stderr)
```
```go
log.Printf("DEBUG dir=%q\n%s", dir, debug.Stack())
```

- Use stderr / `console.error` in tests — loggers are often silenced.
- Capture filtered: `npm test 2>&1 | grep -A30 'DEBUG gitInit'`.
- In the stacks, look for the test file name, the first frame where the value is already wrong, and what the failing calls share (same test, same parameter, same order).
- Remove the instrumentation after the fix (or keep it behind a debug flag if it guards a dangerous operation).

## Which test triggers it?

Unknown test creates files/dirs → `bash $S/find-polluter.sh` (parallel, isolated worktrees; `$S` = absolute scripts path from SKILL.md). State in DBs/globals → order-dependent recipe in parallel-playbook §6.

## Rules

- Never stop at the frame where the error appears if you can go one frame up.
- The origin is where the value is **created or first becomes wrong**, not where it is first used.
- Dead end (value comes from outside: user input, network, OS)? Then the fix is validation at the boundary where it enters.
