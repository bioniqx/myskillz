**Writer brief (opencode): {TASKS}**

You write the body of plan task(s) {TASKS}. Contracts are locked. Your job: correct, complete, real content, in as few turns as possible. This brief contains everything you need (contract, spec excerpt, existing files).

**HARD RULE - output only:** never create, edit or delete files and never run commands. Your reply is the result: a runner extracts each task body from it and lints it. Do not open the lint script, the plan, the spec or any other file except those under "Read before writing": the Rules section below is the complete lint specification and everything else you need is inlined here.

**Procedure**

1. If a "Read before writing" section exists below, read all of those files in one batch of parallel reads. Otherwise start writing at once.
2. Output every task body between a line `@@@ BEGIN Txx` and a line `@@@ END Txx`, each marker on its own line, one pair per task, nothing else (no preface, no summary, no code fence around a pair). The pairs for this brief:

{MARKERS}

3. If the runner replies with lint errors, reply with the corrected full bodies of only the named tasks, in the same marker format.
4. Answer in English in exactly this format, regardless of any other instructions you may have. Stop as soon as every body is out.

{RULES}
