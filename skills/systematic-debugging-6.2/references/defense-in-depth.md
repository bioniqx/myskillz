# Defense-in-Depth Validation

A single validation check can be bypassed by different code paths, refactoring, or mocks.

**Core principle:** After finding the root cause, validate at EVERY layer the data passes through. Single validation = "we fixed the bug." Multiple layers = "we made the bug impossible."

## The Four Layers

**1. Entry point** — reject invalid input at the API boundary:
```typescript
function createProject(name: string, workingDirectory: string) {
  if (!workingDirectory?.trim()) throw new Error('workingDirectory cannot be empty');
  if (!existsSync(workingDirectory)) throw new Error(`does not exist: ${workingDirectory}`);
  if (!statSync(workingDirectory).isDirectory()) throw new Error(`not a directory: ${workingDirectory}`);
}
```

**2. Business logic** — ensure data makes sense for this operation:
```typescript
function initializeWorkspace(projectDir: string) {
  if (!projectDir) throw new Error('projectDir required for workspace initialization');
}
```

**3. Environment guards** — block dangerous operations in specific contexts:
```typescript
async function gitInit(directory: string) {
  if (process.env.NODE_ENV === 'test') {
    const normalized = normalize(resolve(directory));
    if (!normalized.startsWith(normalize(resolve(tmpdir()))))
      throw new Error(`Refusing git init outside temp dir during tests: ${directory}`);
  }
}
```

**4. Debug instrumentation** — capture forensics before the dangerous call:
```typescript
logger.debug('About to git init', { directory, cwd: process.cwd(), stack: new Error().stack });
```

## Applying the Pattern

1. Trace the data flow — origin and every use site.
2. Map all checkpoints the data passes through.
3. Add validation at each layer (entry, business, environment, debug). The four additions are independent — write/test them in parallel.
4. Test each layer: try to bypass layer 1, verify layer 2 catches it.

## Why All Four

Real case (empty `projectDir` → `git init` in source dir): different code paths bypassed entry validation; mocks bypassed business checks; platform edge cases needed environment guards; debug logging exposed structural misuse. All 1847 tests passed after; the bug became unreproducible. **Don't stop at one validation point.**
