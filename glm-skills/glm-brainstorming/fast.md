# FAST

Read this only after `ask.py mode` printed `MODE fast`. It replaces the lane
rounds and the human gates in SKILL.md. It does not replace `check.py`,
`commit-red`, or a high-risk review. Do not change a model id or a thoughtLevel.

`PACE: direct` and `PACE: short` are already faster than this file. If the
prelude printed either, follow that `NEXT` and stop reading.

## 1. Do not pause, and do not launch a lane

Do not ask a question. Do not show `Approve this design?`. Do not arm
`ask.py wait`. Do not offer the visual companion. Do not read
`architectural.md`. Do not dispatch explorer, researcher, drafter, or breaker.
A missing preference is one line in the spec.

Three stops are not choices. Say each in one line, then keep going on
everything else:

- `git stash push -m glm-fast` was already tried once and init still refuses the dirty checkout.
- The harness says the agents were installed this session and cannot load until a new session.
- The next action would force-push, deploy, rewrite history, migrate production, or delete data.

## 2. One option, then the script picks

In the same message as `open`:

1. Write `.brainstorm/drafts/options.json`: one object, `id` `A`, `text` the user request.
2. Run `ask.py fast --ledger .brainstorm/drafts/ledger.json --options .brainstorm/drafts/options.json`.
3. Pass the printed `AUTO` block to `check.py approve --asked design`.
4. `check.py send` on the draft that names the pick. The draft has a Path line, assumptions, and out of scope, and it has no question mark. Repair until `fail=0`. Do not show it.

Exit 2 means the options file was empty. Write the one option and re-run `fast`. Do not launch an attack lane.

## 3. Short spec, inline plan, one lane

Write one short spec: goal, files, acceptance, out of scope. Run `check.py spec` and fix every FAIL. Do not run the five-lens review.

```bash
python3 <skill_dir>/scripts/handoff.py next --self glm-brainstorming --event architectural-approved
```

`ask.py fast` already wrote `.brainstorm/drafts/chain.json` with `"continue": true` and `"mode": "fast"`.

glm-writing-plans writes the plan in one file and runs `check`. It does not call `build`. On a clean check it hands off in that same turn.

glm-dev-team runs `devteam start` and loops `devteam next` until `devteam finish`. Each code slice that is not high-risk is one programmer lane: tests committed first, then the code, tests frozen after `commit-red`. No reviewer lane for those slices. A high-risk slice keeps RED, GREEN, and review. Do not add a reviewer the engine did not print. Do not weaken a test, a gate, or a footprint.

Answer a `BLOCKED` lane from the plan and SendMessage it. If init refuses a dirty checkout, `git stash push -m glm-fast` once and retry init once.
