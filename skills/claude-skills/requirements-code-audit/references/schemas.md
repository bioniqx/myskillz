# Data schemas (all JSON Lines: one object per line, UTF-8)

Everything lives under the audit dir (default `<cwd>/.audit/`). `audit.py` reads and writes these; the lead writes
only `checklist.jsonl`, `adjudications.jsonl` (usually via `audit.py adjudicate`) and `plan.jsonl`.

## `checklist.jsonl` — written by the lead (or drafted by parsers, accepted by the lead)

| key | required | meaning |
|---|---|---|
| `id` | yes | `REQ-001`, `REQ-002`, … unique, document order |
| `text` | yes | faithful restatement in the spec's language; quote load-bearing phrases |
| `strength` | yes | `MUST` / `SHOULD` / `MAY` (RFC 2119; inferred conservatively when absent — say so in `text`) |
| `category` | no | short area label (`auth`, `orders`, `api`, …) — batches are grouped by it |
| `stakes` | no | `high` (security, auth, permissions, payments, data integrity, privacy, safety) or `normal` (default). High → always verified twice |
| `evidence_expected` | no | what code would prove it (endpoint, validation, migration, test…) |
| `search_hints` | yes (may be empty) | identifiers, endpoint paths, field/table names, error codes **and English synonyms** |
| `tags` | no | `static-limit` (needs runtime verification) / `ambiguous` (needs product decision). Tagged items skip the waves |
| `source` | no | section/page reference in the spec |
| `question` | required if `ambiguous` | the question for the product owner |

## `findings/batch-NN.jsonl` — written by investigators (hedges: `batch-NN.r2.jsonl`, retries: `batch-NN.rK.jsonl`)

```json
{"id":"REQ-001","status":"MATCHED|PARTIAL|MISSING|CONFLICT|UNVERIFIABLE|UNSEARCHED","confidence":"high|medium|low",
 "evidence":[{"path":"src/auth/login.py","lines":"41-58","note":"what the code does re: the requirement"}],
 "excerpt":"","searched":["term","glob","path"],"notes":"≤200 chars"}
```

Rules enforced downstream: `MISSING` must list `searched` (and `check` warns when a `search_hint` never appears in it);
`confidence: high` only when evidence directly implements the wording; `UNSEARCHED` means "ran out of budget" and is
re-investigated by a verifier. Paths are relative to the repo root (absolute also accepted).

## `verify/batch-VNN.jsonl` — written by verifiers

```json
{"id":"REQ-001","verified_status":"MATCHED|PARTIAL|MISSING|CONFLICT|UNVERIFIABLE","agree":true,"confidence":"high|medium|low",
 "evidence":[{"path":"…","lines":"10-20","note":"…"}],"searched":["new strategies tried"],"reason":"≤200 chars"}
```

## `adjudications.jsonl` — lead decisions (append-only; last entry per id wins)

```json
{"id":"REQ-007","final_status":"MISSING","note":"both passes searched hints + synonyms; no lockout logic anywhere","by":"lead","at":"2026-09-07 10:12:00"}
```

## `plan.jsonl` — remediation plan (one entry per discrepancy or group)

| key | meaning |
|---|---|
| `ids` | list of requirement ids covered (or `id` for one) |
| `title` | short imperative title |
| `priority` | `P0` (CONFLICT, or unmet MUST on a core/high-stakes flow) / `P1` (other unmet/partial MUST, user-visible SHOULD gaps) / `P2` (rest) |
| `effort` | `S` / `M` / `L` |
| `current` | current state, with `path:lines` |
| `target` | target state, faithful to the spec (cite the section) |
| `fix` | files/functions to touch, tests to add |
| `depends` | ids/titles this depends on (sequencing) |
| `risk` | regression or design risk |

## Final status precedence (computed by `audit.py`)

`adjudication` > `verifier verdict` > `investigator finding` > `UNSEARCHED`; items tagged `static-limit`/`ambiguous`
are always `UNVERIFIABLE`. A `MISSING` that was never verified fails `audit.py check`.

## `state.json` (internal)

Batches with their ids, wave, dispatch and hedge timestamps; verifier batches and assignments; spot-check bookkeeping;
failed batches. Safe to inspect, no need to edit — `status --failed/--redispatch/--undispatch` maintain it.

## `config.json` (internal, also read by the guard hook)

`active`, `repo_root`, `out_dir`, `spec_files`, `lang`, `cap`, `agents` (plugin/local/generic/solo), `models`, `scripts_dir`.
The `ACTIVE` marker next to it arms the hook; `audit.py finish` removes it.
