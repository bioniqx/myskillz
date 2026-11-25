# FAST

The human-readable FAST contract. Nothing reads it at runtime: the `open`
prelude already printed the binding `NEXT: PACE fast`. It does not replace
`check.py`, `commit-red`, or a high-risk review. Do not change a model id or
a thoughtLevel. `PACE: direct` and `PACE: short` are already faster than this
file; if the prelude printed either, follow that `NEXT` and stop reading.

## 1. open already picked, approved, and chained

`open` ran `ask.py fast --request <the request>` inside itself: the single
option (the request) is written, the scored leader is picked, `chain.json`
records `"mode": "fast"` and `"continue": true`, and the printed `RESULT
approve yes` satisfies the approval gate. Do not re-run `ask.py fast`, run
`check.py approve`, ask a question, read `architectural.md`, or dispatch
explorer, researcher, drafter, or breaker. A missing preference is one line
in the spec.

Three stops are not choices. Say each in one line, then keep going on
everything else:

- `git stash push -m z-fast` was already tried once and init still refuses the dirty checkout.
- The harness says the agents were installed this session and cannot load until a new session.
- The next action would force-push, deploy, rewrite history, migrate production, or delete data.

## 2. Draft, send, short spec

Write the design draft (Path line, assumptions, out of scope, no question
mark) and run `check.py send --ledger .brainstorm/drafts/ledger.json --pick
<the pick>` until it prints `fail=0`. Do not show it. Then write the spec
with the eight headings `check.py spec` requires (Architecture, Components,
Data flow, Error handling, Testing, Evidence, Assumptions, Out of scope), one
or two lines each, and run `check.py spec <path>`;
fix every FAIL. Do not run the five-lens review. On `fail=0` with the fast
chain active, `spec` itself prints the `HANDOFF z-writing-plans` block: run
its `NEXT-EXTRA` command in the same turn. A design-only request stops after
the spec.

## 3. Plan, build, finish

z-writing-plans takes the inline path: one write of the plan including
every task body, then `check`; no `build`. On a clean check it prints
`HANDOFF z-dev-team` naming the start command; follow it in that same turn.

z-dev-team runs `devteam start` (init reads the fast chain) and loops
`devteam next` until `devteam finish`. Each code slice that is not high-risk
is one programmer lane: tests committed first, then the code, tests frozen
after `commit-red`. No reviewer lane for those slices. A high-risk slice
keeps RED, GREEN, and review. Do not add a reviewer the engine did not
print. Do not weaken a test, a gate, or a footprint.

After `devteam finish` succeeds, commit from the repo root. Do not commit
before that. Run `handoff.py fast-done --message-file <msg> --gitlab-file
<note> -- <paths this task changed>`. Both files are English. `<msg>` is the
git commit subject plus a short body. `<note>` is the GitLab description, 4
to 8 lines: what changed, why, and how to tell it works. Show the printed
`COMMIT` and `GITLAB` blocks in the chat, each in its own fence, so the user
can copy them. Do not push. Do not amend. A path the engine already committed
is not a second commit.

Answer a `BLOCKED` lane from the plan and SendMessage it. If init refuses a
dirty checkout, `git stash push -m z-fast` once and retry init once.
