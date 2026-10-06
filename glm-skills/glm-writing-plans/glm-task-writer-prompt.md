# Assignment: write task bodies {TASKS}

Everything above is the binding rule set and the shared plan context. Everything
below is your specific job. The contract blocks that follow this section carry
your spec excerpt and your inlined files.

Write one file per task:

{OUT}

LINT: `{LINT}`

# Procedure - 3 turns, no exploration

1. HARD RULE: your only inputs are this brief. Do not open the plan, the spec,
   the lint script or any other file. Do not search the repository. The rules
   above are the complete lint specification and every file you need is already
   inlined with real line numbers.
2. Write every output file. Several tasks -> put all the writes in ONE message.
3. Lint. If the write result already shows a `plan-lint:` note, that note IS the
   lint result - do not run the command again. Otherwise run LINT in one shell
   call. On `ERR`, edit the file and lint again; at most 3 rounds. Fix `WARN`
   lines that are real problems.
4. Reply with exactly one line per task: `T07 OK` or `T07 FAIL: <first error>`.
   Never echo the body. No summary, no preamble.
