# SLOW is fully automatic: quality first, nobody is asked, the summary lands in .done-slow

Date: 2026-11-27. Status: designed and built in FAST mode (pick A, approved by `ask.py fast`
inside `open`). Scope: the seven skills that have a SLOW branch (z-brainstorming, z-dev-team,
z-writing-plans, z-requirements-code-audit, z-systematic-debugging, z-doc-generator,
z-git-diff-summary), `_shared/handoff.py`, `z-brainstorming/scripts/ask.py` and `check.py`, the
SLOW wording of the four engine scripts, their tests and two changelogs. Work happens on main.
FAST branches, `fast.md`, the mode classifier, the router, the 2026-11-17 engine caps (falsifier,
claim, mutant), z-idea-to-spec, z-find-skills, the two video skills and the sibling repos are not
touched. Nothing is installed into the ZCode or dsh home by this run.

This spec supersedes the user gate of `2026-11-26-slow-asks-and-waits.md` and keeps every
oracle of `2026-11-17-slow-mode.md`.

The request, verbatim:

- Chinh sua tat ca skill trong thu muc nay, ngoai tru cac skill lien quan video.
- Chinh sua SLOW mode cac skill. Muc tieu la tu dong hoan toan.
- Khi o SLOW mode: chat luong dau ra phai duoc uu tien hang dau.
- doc code hien tai + tu dong tim kiem thong tin tren mang (neu can, tu nguon uy tin), sau do suy
  nghi nhieu buoc thau dao, sau xa de tim ra phan an tot nhat, toi uu nhat, hoan hao nhat.
- tu dong chon va trien khai theo phuong an tot nhat, khong can su dong y tu user.
- code xong thi tu ra soat tat ca van de phat sinh, tu sua tat ca.
- ket qua cuoi cung la da code xong hoan toan khong co bat cu loi nao, khong de lai hau qua gi,
  kem 1 bang tom tat y tuong va mo ta da lam gi trong file markdown o thu muc .done-slow trong
  du an.
- de tang toc do: co the tao agent hoac luong khong gioi han, hop ly la duoc.

The original text is Vietnamese; this copy is folded to ASCII so the file stays plain ASCII.

## Architecture

SLOW becomes the autonomy of FAST plus the oracles SLOW already has. Nobody is asked: the
engine names the pick, the chain continues on it, the change is reviewed and fixed until a review
is clean, and `handoff.py slow-done` files the summary table and commits. Three decisions bind
the design:

1. One contract sentence, defined once in `_shared/handoff.py` (`SLOW_AUTO`, replacing
   `SLOW_ASK`) and appended to every SLOW NEXT line the prelude prints. Each of the seven
   `SKILL.md` files keeps one pointer sentence with the same meaning.
2. The engine gates that enforced asking flip in place; none is deleted and no gate is added
   that FAST can reach. FAST branch strings stay byte for byte.
3. Quality is not a longer prompt. It is the 2026-11-17 oracles, plus a research lane for every
   load-bearing fact, no round or lane budget, and a closing review loop on the whole change.

## Components

Clause layer, `_shared/handoff.py`:
- `SLOW_AUTO` replaces `SLOW_ASK`; `slow_next()` appends it to every SLOW NEXT line.
- `_slow_ship(when, check=True)` is the SLOW twin of `_ship`: the binding `slow-done` ending.
  Every SLOW NEXT line that ends a task now carries it, as FAST lines carry `_ship`.
- The SLOW NEXT lines of all seven skills are reworded: decide and continue, the review loop,
  then `slow-done`. Under SLOW an invalid `--base` falls back to the default base and a missing
  spec path is found, not asked for.

Engine layer:
- `z-brainstorming/scripts/check.py`: `approve` accepts an AUTO block under a slow stamp.
  `send` fails any question mark under a slow stamp, the `Approve this design?` line included.
  The draft sent with `--pick` is the SLOW design note: still an Out of scope line, an
  assumptions line and (Architectural) 2-3 APPROACH lines. Any other slow-stamp draft needs
  no design shape.
- `z-brainstorming/scripts/ask.py`: `chain` without `--pick` takes the decision from the engine.
  A `pick`, or an `ask` whose leader won the score, is chained and prints `RESULT approve yes`.
  `ask=unattacked` and `DECISION stop` are refused with the one repair to run. `--pick` keeps
  working. `wait` and `cancel` are unchanged; no SLOW flow starts them.
- `handoff.py slow-done --summary-file MD [--check CMD] [--message-file MSG --gitlab-file NOTE]
  [-- PATHS...]`: validates the summary, runs the check, files the summary, commits. It reuses
  the `fast-done` commit code through three defaulted parameters, so FAST output is unchanged.
- `_shared/decide.py`: `atoms --check --ledger LEDGER` stores the frozen atoms. Nothing stored
  them before, so `score`, `close` and `chain` credited every option with covering every atom;
  the pick's atom term was inert. Without `--ledger` the command prints what it always printed.

Prose layer: every SLOW-only sentence that says ask, wait for the reply, human approve stays or
do not commit is rewritten in place: seven `SKILL.md` files, `z-brainstorming/architectural.md`,
`fanout-playbook.md`, `research-playbook.md`, `spec-document-reviewer-prompt.md`, and the
`z-dev-team` agent files where a lane reports a blocking question. The engine scripts
(`plan_tool.py`, `devteam.py`, `debug_tool.py`, `audit.py`) keep their oracles; only SLOW wording
that hands a decision to the user changes.

Three sentences carry what a second review found. Hard rule 1 of z-brainstorming scopes the SLOW
approval: `ask.py chain` where the NEXT line starts the chain, and the `Width direct` or
`Width short` NEXT line itself where it orders the edit. No prose keys a wait on `PACE: full`:
the FAST prelude prints that pace line, and no pace starts `ask.py wait`. The design-only stop
stands before every order to chain, in R6, R13, `architectural.md` and the reviewer prompt.

## Data flow

`open` classifies the mode and writes the stamp, as today. Under SLOW every NEXT line ends with
`SLOW_AUTO`. On z-brainstorming at full pace: atoms, fact lanes (code and web), three drafters
and three breakers, `check.py close`, the extra breaker on the leader, `prove --cap 8`, then
`ask.py chain` chains the engine's leader and prints the approval; the design note passes
`check.py send`, the spec passes `check.py spec`. A Spike or a design-only request stops after
its answer or its spec; only a request that asks to build runs `handoff.py next` and moves to
z-writing-plans. The plan and the z-dev-team run proceed with their SLOW oracles and no
question. The last skill
runs one reviewer pass on the whole change, fixes every BLOCKER and MAJOR, repeats until clean
(cap 3), then calls `slow-done`. A read-only SLOW run (a summary, an audit report, a Spike)
calls `slow-done` with no check and no notes: the summary is filed and left untracked.

`slow-done`, in order: read the summary and fail on a missing table, a missing `Leftovers:` or
`Rollback:` line, or non-ASCII text; resolve the named paths against `git status -z`, so a
name is never quoted and a folder covers every dirty file under it; when any of them is
dirty, check the two note files, require `--check` and run it with `sh -c` in the repo root
(1800 seconds); move the summary into `.done-slow/` under a name built from the date, the time
and a slug taken from its first heading; commit the dirty files with the summary through the
`fast-done` code. A named path that is clean because the engine already committed it (a
z-dev-team run merges its slices itself) gets the summary as its own commit and is printed
under `ALREADY`. Then `SUMMARY`, `COMMIT` and `GITLAB` are printed. It never pushes and never
amends.

## Error handling

- A failing or missing check: `FAIL check`, nothing is filed or committed, NEXT says fix every
  failure and run `slow-done` again.
- An invalid summary: `FAIL summary` names each problem; nothing is filed.
- No dirty named path: `SLOW-DONE clean`; the summary is filed and stays untracked. A folder
  that is not a git repository is always that case, so the summary lands under its
  `.done-slow/` and nothing is committed.
- A named path that is neither tracked nor on disk, or a missing note file while files
  changed: `FAIL` before anything is filed, so a re-run files no second copy of the summary.
- The summary's own path is never a changed path, and a summary written over a tracked file
  is refused: filing moves the file, which would delete a tracked one.
- A secret path among the named ones: `FAIL secret` before anything is filed.
- The named paths are read again after the check runs, so a path the check changed is judged
  before anything is filed. Running `slow-done` again with the already filed summary keeps
  its name: no second copy.
- A name collision in `.done-slow`: the second file gets `-2`, the third `-3`.
- `ask.py chain` on `ask=unattacked` or `DECISION stop`: exit 2, chain.json is not written,
  NEXT names the one repair. A human reply is never waited for under SLOW.
- Three stops stay, one line each: a second dirty-checkout refusal after one stash, agents
  installed this session, an irreversible action.

## Testing

Commands: the full suite, the hygiene suite, `sh _shared/sync.sh` then `test_vendored.py`, and
`bash z-dev-team/scripts/selftest.sh`. Tests that pinned the old gates flip with the changed
requirement and each is named in the report: every SLOW NEXT line contains `SLOW_AUTO` and no
FAST line does; `approve` accepts AUTO under a slow stamp; `send` fails one question mark under a
slow stamp; `chain` without `--pick` chains the leader, refuses unattacked and stop, and writes
mode slow. New tests: `slow-done` in a temporary git repository (summary validation, the check
gate, filing, the commit, the clean path, a named folder, a non-ASCII file name, notes and
missing paths refused before filing, no push) and in a folder that is not a repository. The
oracle tests
(`test_plan_slow.py`, `test_debug_slow.py`, `test_devteam_slow.py`, `test_audit_slow.py`) keep
every oracle assertion; only an assertion that pinned the old asking wording changes, and each
is named in the report. One shared sentence changes for both modes: the chain-cap NEXT drops
"or ask the user", which FAST already forbade.

## Evidence

None - repo-internal. The requirement is the user's request above; the behavior is pinned by
this repo's own suite and by `selftest.sh`. No external fact decides the design.

## Assumptions

- SLOW commits locally like FAST: no push, no amend. A summary joins the commit only when the
  task changed files; a read-only run leaves it untracked under `.done-slow/`.
- The scope is the seven skills that have a SLOW branch. z-idea-to-spec and z-find-skills have
  none and are not changed.
- A cap the engine reaches (falsifier, claim, mutant) is finished on the main thread, not handed
  to the user; what is still open after that is named in the summary.
- "No bug" is enforced the only way this harness can: the check command must exit 0 before
  `slow-done` commits, and one reviewer pass must come back clean. Anything left after three
  rounds is stated, not hidden.

## Out of scope

FAST branches and `fast.md`; the mode classifier and the router; the 2026-11-17 engine caps; the
video skills; z-idea-to-spec and z-find-skills; the `claude-skills/` originals; installing into
a harness home; pushing.
