# Condition-Based Waiting

Flaky tests guess at timing with arbitrary delays; they pass on fast machines and fail under load/CI — and they're slow, because every sleep waits the full duration even when the condition is already true.

**Core principle:** Wait for the actual condition, not a guess about how long it takes. This is both a reliability AND a speed optimization (real case: 60%→100% pass rate, 40% faster suite) — essential when running tests in parallel across many workers.

**Use when:** tests contain `setTimeout`/`sleep`/`time.sleep()` · flaky under load · timeouts when run in parallel · waiting for async completion.
**Don't use when:** testing actual timing behavior (debounce/throttle) — then document WHY the timeout is needed.

## Core Pattern

```typescript
// ❌ BEFORE: guess timing (slow AND racy)
await new Promise(r => setTimeout(r, 50));
expect(getResult()).toBeDefined();

// ✅ AFTER: wait for the condition (fast AND deterministic)
await waitFor(() => getResult() !== undefined, 'result available');
expect(getResult()).toBeDefined();
```

```typescript
async function waitFor<T>(
  condition: () => T | undefined | null | false,
  description: string,
  timeoutMs = 5000
): Promise<T> {
  const start = Date.now();
  while (true) {
    const result = condition();
    if (result) return result;
    if (Date.now() - start > timeoutMs)
      throw new Error(`Timeout waiting for ${description} after ${timeoutMs}ms`);
    await new Promise(r => setTimeout(r, 10)); // 10ms poll: fast without wasting CPU
  }
}
```

| Scenario | Pattern |
|---|---|
| Event | `waitFor(() => events.find(e => e.type === 'DONE'))` |
| State | `waitFor(() => machine.state === 'ready')` |
| Count | `waitFor(() => items.length >= 5)` |
| File | `waitFor(() => fs.existsSync(path))` |
| Complex | `waitFor(() => obj.ready && obj.value > 10)` |

Full domain-specific helpers (`waitForEvent`, `waitForEventCount`, `waitForEventMatch`): see `condition-based-waiting-example.ts` in this directory.

## Common Mistakes

- Polling every 1ms → wastes CPU; use 10ms.
- No timeout → infinite hang; always include timeout + descriptive error.
- Caching state before the loop → stale data; call the getter inside the loop.

## When an Arbitrary Timeout IS Correct

```typescript
await waitForEvent(manager, 'TOOL_STARTED');  // 1) first wait for the trigger condition
await new Promise(r => setTimeout(r, 200));   // 2) 200ms = 2 ticks @100ms — known timing, documented
```

Requirements: condition first · based on known timing, not a guess · comment explaining WHY.
