# Root Cause Tracing

Bugs manifest deep in the call stack (git init in wrong dir, file in wrong location, DB opened with wrong path). Fixing where the error appears treats a symptom.

**Core principle:** Trace backward through the call chain until you find the original trigger, then fix at the source. NEVER fix just where the error appears.

**Use when:** error happens deep in execution · long call chain · unclear where invalid data originated · need to find which test/code triggers the problem.

## The Tracing Process

1. **Observe symptom:** `Error: git init failed in ~/project/packages/core`
2. **Immediate cause:** `execFileAsync('git', ['init'], { cwd: projectDir })`
3. **What called this?** `WorktreeManager.createSessionWorktree(projectDir)` ← `Session.initializeWorkspace()` ← `Session.create()` ← test
4. **What value was passed?** `projectDir = ''` — empty cwd resolves to `process.cwd()` = source dir!
5. **Original trigger:** `setupCoreTest()` returns `{ tempDir: '' }`; test accessed it before `beforeEach` ran.

Repeat "can I trace one level up?" until the answer is no — that's the source. Fix there, then add defense-in-depth at every layer passed through (see `defense-in-depth.md`).

## Stack Instrumentation (when manual tracing stalls)

```typescript
async function gitInit(directory: string) {
  console.error('DEBUG git init:', {
    directory,
    cwd: process.cwd(),
    nodeEnv: process.env.NODE_ENV,
    stack: new Error().stack,   // full call chain
  });
  await execFileAsync('git', ['init'], { cwd: directory });
}
```

Tips: use `console.error` in tests (loggers may be suppressed) · log BEFORE the dangerous operation · include directory, cwd, env, timestamps · capture with `npm test 2>&1 | grep 'DEBUG git init'` · in stack traces look for test filenames + line numbers, then the shared pattern.

## Finding Which Test Pollutes

Use the parallel bisection script:

```bash
# All independent polluters, one round, ≤64 concurrent isolated worktrees:
scripts/find-polluter.sh -j 64 '.git' 'src/**/*.test.ts'

# Order-dependent pollution (only appears when tests run in sequence):
scripts/find-polluter.sh -m bisect '.git' 'src/**/*.test.ts'

# Custom runner:
scripts/find-polluter.sh -c 'npx vitest run' '.git' 'src/**/*.test.ts'
```

## Worked Example

Symptom: `.git` created in `packages/core/` (source code). Trace: git init with empty cwd ← WorktreeManager got empty projectDir ← Session.create passed '' ← test read `context.tempDir` before beforeEach ← setup returns `{ tempDir: '' }` initially.

Fix at source: made `tempDir` a getter that throws if accessed before `beforeEach`. Plus 4 defense layers (validate at create / validate non-empty / NODE_ENV tmpdir guard / stack logging). Result: 1847 tests passed, zero pollution.
