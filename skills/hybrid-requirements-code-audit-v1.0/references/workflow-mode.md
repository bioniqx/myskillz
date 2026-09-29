# Workflow mode (Claude Code dynamic workflows)

Use a dynamic workflow instead of Agent-tool fan-out when any of these hold:

- the subagent cap cannot be raised (stuck at 20) **and** N is large, or the lead's context is precious (N > ~300);
- the user asked for a workflow (`ultracode`, "use a workflow") or wants a rerunnable command (`/req-audit-run`);
- the environment refuses many concurrent Agent calls but allows workflows.

Trade-off: the workflow runtime caps concurrency at **16 agents** (fewer on small CPUs), so a wave of 64 batches runs
in ~4 rounds — slower per wave than 64 concurrent subagents, but intermediate results never enter the lead's context,
the run is pausable/resumable, and the verification pass is codified.

## How it plugs into the same pipeline

1. Steps 0–2 are unchanged: `audit.py init`, checklist, `audit.py plan` (batch files exist on disk).
2. Load the script-writing reference first: run `/workflow-authoring` (Claude Code v2.1.248+), then ask for a workflow
   built from the brief below. Do not hand-write the API from memory.
3. The workflow's agents write the same files the skill expects (`findings/batch-NN.jsonl`, `verify/batch-VNN.jsonl`)
   — so when it returns, `audit.py status` sees full coverage and the rest (queue → plan → report → check → finish)
   is identical.

## Brief for the workflow script

- **Phase "investigate"**: `pipeline` over every `.audit/batches/batch-*.md`; one agent per file, model `haiku`,
  prompt: `Investigator <name>: read <path> and follow it exactly.` Label each agent with the batch name.
  Use a `schema` that returns `{ "batch": string, "written": number, "total": number }` so the script can detect
  partial batches and re-run them once.
- **Phase "verify"**: the script cannot run `audit.py`, so it must compute the verify set itself: read every
  findings file through an agent step (or one agent that reads all of them and returns the list of ids whose status
  is not MATCHED, or MATCHED with confidence ≠ high, or whose checklist `stakes` is high). Then `pipeline` over
  chunks of ≤3 ids: one `sonnet` agent per chunk with the adversarial instructions from
  `scripts/audit.py::VERIFY_RULES` and the verdict schema from `references/schemas.md`, writing `verify/batch-VNN.jsonl`
  (NN starting at 01, unique per chunk).
- **Return** a short summary object (counts per status) — nothing else; the files are the real output.
- Agents must have only Read/Grep/Glob/Write; no shell; the same hard rules as the batch files (no docs, no git).
- Name the saved workflow `req-audit-run`; it accepts `args.auditDir` (default `.audit`).

Then: `audit.py status` → `audit.py queue` → adjudicate → `plan.jsonl` → `audit.py report` → `check` → `finish`.
