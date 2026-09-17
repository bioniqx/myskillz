# Speed Test 2: Flaky regression across many commits

You have the systematic-debugging skill, a 16-core machine, and Claude Code with default settings.

`tests/checkout.test.ts` fails in CI about 1 run in 10 since "sometime in the last two weeks" (≈ 800 commits on main). It passed reliably at tag `v2.3.0`. Locally one run takes 40 s. The team lead wants the culprit commit and the root cause today.

Describe exactly what you do, round by round: commands (with `-n` / `-j` values and why), what runs in background, what runs in parallel, and how you decide the fix is proven.
