# Why the audit is built this way

This file holds the rationale and the schema examples that used to sit in the main skill file. Read it only when asked.

## Why this design is fast (and still trustworthy)

The wall-clock of an audit is dominated by the lead's own output tokens plus the slowest agent in each wave, not by the
number of agents. So:

- **The lead does judgment only.** Repo map, batch planning, prompt assembly, merging 64 findings files, packing
  verifier batches, straggler detection, report assembly and the quality gate are all `audit.py`, not tokens.
- **Workers write files, not chat.** Each agent writes a small JSONL file and replies with one line, so 64 results cost
  the lead about 64 lines of context and nothing is ever retyped.
- **One message per wave, batch size 1 when the cap allows.** All Agent calls of a wave go out in a single message;
  smaller batches shorten the slowest worker. Batch count adapts to the concurrency cap automatically.
- **Tiny, identical delegation prompts.** Every worker gets "read <batch file> and follow it exactly"; the rules live in
  the agent definition, so per-agent prompt tokens are minimal and the system-prompt prefix is shared across the wave
  (prompt cache). In plugin and local mode the batch files do not repeat the rules block.
- **Sonnet for legwork, judgment stays with the lead.** Investigators run on `sonnet` at effort medium (never the lead's
  high effort), verifiers on `sonnet` at effort high, adjudication by the lead. Wave B is what makes the tiering safe.
- **Event-driven Wave B.** Verifiers are packed and dispatched as investigators finish, so verification overlaps the
  investigation tail instead of waiting for the last straggler; stragglers get a hedged duplicate.
- **Bounded workers.** `maxTurns` plus a per-requirement search budget cap the worst case; incomplete batches are
  re-dispatched or absorbed by verifiers, never awaited forever.
- **Parsers do the decomposition.** Specs over about 800 words are split into section files and parsed by `claude-rca-parser`
  workers in parallel at effort medium; the lead only reads the merged draft next to the original for faithfulness.

## Schema examples

Checklist line (`.audit/checklist.jsonl`, one object per line):

{"id":"REQ-001","text":"faithful restatement; quote load-bearing phrases","strength":"MUST","category":"auth","stakes":"high","evidence_expected":"what code would prove it","search_hints":["login","password","bcrypt","lockout"],"tags":[],"source":"2.1","question":""}

Plan line (`.audit/plan.jsonl`, one object per discrepancy or group of related ones):

{"ids":["REQ-007"],"title":"Add login lockout","priority":"P0","effort":"S","current":"login.py:41-58 validates password only","target":"lock account after 5 failed attempts for 15 min (spec 2.3)","fix":"add attempt counter in auth/service.py; test","depends":"","risk":"lockout DoS - rate-limit by IP too"}

## Where enforcement lives

Agent files installed from a plugin ignore their own `hooks`, `mcpServers` and `permissionMode` frontmatter. The audit
therefore never relies on agent frontmatter for enforcement: the guard (no git history, no prose docs, writes only under
`.audit/`, read-only workers) is registered in the plugin-level `hooks/hooks.json` for PreToolUse and SubagentStop and
runs `hooks/audit_guard.sh`. The `permissionMode` line in the agent files only matters in local mode, where it avoids
permission prompts for the findings file.
