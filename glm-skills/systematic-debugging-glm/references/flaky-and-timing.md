# Flaky Tests and Timing Bugs

Arbitrary sleeps guess at timing: they pass on a fast laptop and fail under CI load, and they make suites slow. Wait for the condition you actually need.

## First: measure, don't eyeball

```bash
bash $S/stress.sh -n 200 -- <single test command>      # $S = the path printed as S= by every tool output
```
A failure rate plus failing logs is your evidence. Test a candidate timing fix with `debug_tool.py experiment` using `runs: <3/p>` on both arms, never by rerunning it a few times by hand. Raising `-j` above the CPU count adds load so races surface more often — but keep the same `-j` for before/after comparisons, and rule out runs interfering with each other (shared ports/DB/files) by checking `-j 1`. Prove the fix with `-b F/N` (Fisher p < 0.05) — see parallel-playbook §6.

## Replace sleeps with condition waits

```ts
// before: await new Promise(r => setTimeout(r, 300)); expect(getResult()).toBeDefined();
await waitFor(() => getResult() !== undefined, 'result available');

export async function waitFor<T>(cond: () => T | false | null | undefined, what: string, timeoutMs = 5000, everyMs = 10): Promise<T> {
  const start = Date.now();
  for (;;) {
    const v = cond();                       // re-read fresh state every poll
    if (v) return v;
    if (Date.now() - start > timeoutMs) throw new Error(`Timeout after ${timeoutMs}ms waiting for ${what}`);
    await new Promise(r => setTimeout(r, everyMs));
  }
}
```
```python
def wait_for(cond, what, timeout=5.0, every=0.01):
    deadline = time.monotonic() + timeout
    while True:
        v = cond()
        if v: return v
        if time.monotonic() > deadline: raise TimeoutError(f"timeout after {timeout}s waiting for {what}")
        time.sleep(every)
```

Prefer framework-native waits when they exist: Testing Library `waitFor`/`findBy*`, Playwright auto-waiting `expect(locator).toHaveText()`, `vi.waitFor`, Awaitility (JVM), `Eventually` (Go testify / Gomega). Prefer fake timers (`vi.useFakeTimers`, `jest.useFakeTimers`, `freezegun`) when the code under test is itself time-based.

| Wait for | Condition |
|---|---|
| event | `events.find(e => e.type === 'DONE')` |
| state | `machine.state === 'ready'` |
| count | `items.length >= 5` |
| file | `fs.existsSync(p)` |
| event by id | `events.find(e => e.type === 'TOOL_RESULT' && e.data.id === id)` |

## Mistakes

- Polling every 1 ms burns CPU → 10 ms is plenty.
- No timeout → hangs forever; always throw with a message naming what was awaited.
- Caching state outside the loop → always re-read inside.
- Bumping the timeout as "the fix" → that is a guess, not a root cause.

## When a fixed delay is legitimate

Only when testing timed behavior itself (debounce, throttle, tick intervals), and then: first wait for the triggering condition, then delay a duration derived from the known interval, with a comment:

```ts
await waitForEvent(mgr, 'TOOL_STARTED');  // condition first
await sleep(200);                           // 2 ticks × 100 ms tick interval — timed behavior under test
```

## Common flake root causes (check these first)

Shared state between tests (globals, singletons, DB rows, temp files) · test-order dependence · unawaited promises / missing `await` · real clock or timezone · ports in use · network calls not mocked · randomness without a seed · resource exhaustion under parallel runs.
