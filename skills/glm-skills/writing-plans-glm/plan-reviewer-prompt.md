# Reviewer assignment: {TASKS}

You review and FIX task bodies of an implementation plan, in place. A
deterministic linter already enforces structure, placeholders, portability, file
ownership, signatures, step numbering, Run/Expected, git-add scope and
code-block syntax. Spend judgment only on what a script cannot see.

Files you own (edit only these; never touch the plan file or another task):

{FILES}

LINT (also marks the review done - run it at the end even if you changed
nothing): `{LINT}`

# Procedure - 3 turns

1. Read all the files above in ONE message. Contracts and spec excerpts follow
   below.
2. Judge each task against four questions only:
   - Spec alignment: is a requirement in the excerpt missing or contradicted?
   - Correctness: would the test really fail first and pass after? Is any
     command, expected output, import, API call or fixture wrong?
   - Buildability: would an engineer following the steps literally get stuck or
     build the wrong thing?
   - Contract use: is a consumed signature called differently from its contract?
   Ignore wording and style. Fix only what would break implementation.
3. Apply every fix with edits (all in ONE message where possible; leave contract
   signatures and the Files list unchanged), then run LINT once. On `ERR`, fix
   and re-run.
4. Return only:

```
Status: Approved | Fixed
- TXX: <what you fixed, <= 15 words>
Unfixable (needs contract change): TXX: <issue>
```
