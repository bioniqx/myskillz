# Speed Test 2: Flaky regression across 800 commits

You have the systematic-debugging skill.

`npx vitest run src/queue.test.ts` fails roughly 1 run in 10 on CI and "almost never" locally.
It passed reliably at tag `v2.3.0`; `HEAD` is 800 first-parent commits later. Each run takes ~40 s
on a 16-core machine. `package-lock.json` changed twice inside that range.

Act. Show every tool call you would make, grouped by message (round), with the exact flags.
