# Red flags and rationalizations

Read when tempted to skip a step. Any item below means: return to Phase 1 of the debugging procedure.

## Red flags

"Quick fix now, investigate later" · "just try X" · several changes then run tests · skipping the failing test · "probably X" with no evidence · adapting a pattern you have not read fully · listing fixes before tracing data flow · bumping a sleep/timeout/retry as the fix · a null check at the crash site · "one more attempt" after 2 failures · the user says "stop guessing", "is that actually happening?", "we're stuck".

## Rationalizations

| Rationalization | Reality |
|---|---|
| "Simple / urgent, no time" | FAST lane costs 2 rounds; guessing costs more. |
| "Prod is down" | Mitigate first with a reversible, cause-agnostic action (rollback, feature flag, failover, degrade the feature) — that is not a fix — while ONE parallel round gathers evidence (change timeline vs error onset, DNS/TLS/egress from the host, provider status). Root cause still precedes the code change. |
| "Several fixes at once saves time" | Parallelize isolated experiments, never fixes in one tree. |
| "Senior/author says it's X" | That is a hypothesis; one experiment confirms it. |
| "4 hours of sleeps can't be wasted" | Sunk cost. Delete them; a timing guess is not a root cause. |
| "I'll write the test after" | Untested fixes regress; the failing test is the proof. |
