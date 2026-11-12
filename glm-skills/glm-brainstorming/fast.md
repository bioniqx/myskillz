# FAST

Read this only after `ask.py mode` printed `MODE fast`. It replaces the human
gates in SKILL.md (R0's pause, R6, R12, R13's "only when the user wants the
next job", the conductor's ask branch) and the question and review gate in
`architectural.md` §2 and §4. It does not replace `check.py`, the lane agent
files, or a sibling skill's engine. Do not change a model id or a thoughtLevel.

## 1. Do not pause for a choice

Do not ask a question. Do not show `Approve this design?`. Do not arm
`ask.py wait`. Do not offer the visual companion. Do not wait for a spec
review. A missing preference is an assumption in the spec. Repair every
`FAIL` and continue.

Three stops are not choices. Say each in one line, then keep going on
everything else:

- `git stash push -m glm-fast` was already tried once and init still refuses the dirty checkout.
- The harness says the agents were installed this session and cannot load until a new session.
- The next action would force-push, deploy, rewrite history, migrate production, or delete data.

## 2. Same evidence, then the script's pick

Run the conductor through `check.py close`. Do not show the draft.

```bash
python3 <skill_dir>/scripts/ask.py fast --ledger .brainstorm/drafts/ledger.json --options .brainstorm/drafts/options.json
```

- It prints `DECISION pick=<id>`. That id is the option. Record a `RISK` line in the spec. Do not pick a different id.
- Exit 2 means there is no option. Write one option from the request and the kept facts, attack it once, run `close` again, and re-run `fast`. Do not ask.

Pass this stdin to `check.py approve --asked design`, with the printed id:

```
AUTO
DECISION pick=<id> auto=1
```

`RESULT approve yes` is hard rule 1. Then `check.py send` on the draft that names the id. The draft has a Path line, assumptions, and out of scope, and it has no question mark. Repair until `fail=0`. Do not show it as a question.

## 3. Spec, then the plan, then the code

Write the spec the way `architectural.md` §4 steps 1-3 say. Skip the review gate in §4.4. Run `check.py spec` and fix every FAIL. Commit only when that section's commit rule already allows it.

The hand-off event is always `architectural-approved`, including Spike and Bounded of any size. Do not implement in this skill.

```bash
python3 <skill_dir>/scripts/handoff.py next --self glm-brainstorming --event architectural-approved
```

`ask.py fast` already wrote `.brainstorm/drafts/chain.json` with `"continue": true` and `"mode": "fast"`. Read the sibling `SKILL.md` that `NEXT:` names and follow it in this same session. Do not end the turn between a passing spec and the plan tool's first call except to wait for a script.

glm-writing-plans asks nothing. On `OK assembled`, hand off in that same turn.

glm-dev-team runs `devteam start` on the plan and does not ask whether to begin. Answer a `BLOCKED` lane from the plan and SendMessage it. If init refuses a dirty integration checkout, `git stash push -m glm-fast` once and retry init once. Loop `devteam next` until `devteam finish`. Do not weaken a test, a gate, a footprint, or a review.

A request that only asked a question is still specified and built. The spec is the chosen way to satisfy it.
