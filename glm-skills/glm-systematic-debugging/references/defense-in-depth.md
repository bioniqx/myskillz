# Defense in Depth (after the root cause is fixed)

A single check gets bypassed by other code paths, mocks, or refactors. When invalid data traveled through several layers before failing, add a guard at each layer it crosses so the bug class becomes structurally impossible. Do this only after the root-cause fix — guards never replace it.

## Layers

| Layer | Purpose | Example |
|---|---|---|
| 1. Entry point | Reject bad input at the API boundary | `if (!dir?.trim()) throw new Error('workingDirectory cannot be empty')`; exists; is a directory |
| 2. Business logic | Ensure the value makes sense for this operation | `initializeWorkspace` requires non-empty `projectDir` |
| 3. Environment guard | Refuse dangerous operations in the wrong context | in tests, refuse `git init` outside `os.tmpdir()` |
| 4. Instrumentation | Leave forensics for next time | debug log with value + `cwd` + stack before the dangerous call |

```ts
async function gitInit(directory: string) {
  if (process.env.NODE_ENV === 'test') {
    const d = path.resolve(directory), tmp = path.resolve(os.tmpdir());
    if (d !== tmp && !d.startsWith(tmp + path.sep)) throw new Error(`Refusing git init outside tmpdir during tests: ${directory}`);
  }
  logger.debug('git init', { directory, cwd: process.cwd(), stack: new Error().stack });
  await execFileAsync('git', ['init'], { cwd: directory });
}
```

## Procedure

1. Map the path the bad value took (you have it from root-cause tracing).
2. Add the cheapest meaningful check at each layer; error messages name the value and the layer.
3. Test each guard in isolation: bypass layer 1 (call layer 2 directly, or through a mock) and confirm layer 2 catches it. These tests are independent → `python3 $S/debug_tool.py run -j 8 '<t1>' '<t2>' '<t3>'` in one call.
4. Keep guards proportional: public boundaries and destructive operations get guards; internal pure helpers usually do not.
