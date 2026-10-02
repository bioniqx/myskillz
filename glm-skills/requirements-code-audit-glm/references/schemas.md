# Data schemas (all JSON Lines: one object per line, UTF-8)

Everything lives under the audit dir (default `<cwd>/.audit/`). `audit.py` reads and writes these. You write
only `checklist.jsonl`, `plan.jsonl` and `adjudications.jsonl` (the last one via `audit.py adjudicate`).

## `checklist.jsonl` — yours

| key | required | meaning |
|---|---|---|
| `id` | yes | `REQ-001`, `REQ-002`, … unique, document order |
| `text` | yes | faithful restatement in the spec's language; quote load-bearing phrases |
| `strength` | yes | `MUST` / `SHOULD` / `MAY` (RFC 2119; inferred conservatively when absent — say so in `text`) |
| `category` | no | short area label (`auth`, `orders`, `api`, …). Biases retrieval ranking toward matching directories |
| `stakes` | no | `high` (security, auth, permissions, payments, data integrity, privacy, safety) or `normal` (default). High → always verified twice |
| `evidence_expected` | no | what code would prove it (endpoint, validation, migration, test…). Feeds retrieval keywords |
| `search_hints` | yes | 4-10 identifiers, endpoint paths, field/table names, config keys, error codes **and English synonyms**. Fewer than 2 makes `run` refuse the checklist |
| `tags` | no | `static-limit` (needs runtime verification) / `ambiguous` (needs product decision). Tagged items skip the waves |
| `source` | no | section/page reference in the spec |
| `question` | required if `ambiguous` | the question for the product owner |

## `findings.jsonl` — written by the first pass (`run`), or by investigators into `findings/batch-NN.jsonl`

```json
{"id":"REQ-001","status":"MATCHED|PARTIAL|MISSING|CONFLICT|UNVERIFIABLE|UNSEARCHED","confidence":"high|medium|low",
 "evidence":[{"path":"src/auth/login.py","lines":"41-58","note":"what the code does re: the requirement"}],
 "searched":["every query actually run, both passes"],"passes":2,"notes":"<=200 chars",
 "more_queries":["terms the model asked for"],
 "retrieval":{"engine":"ripgrep","files":["ranked files"],"layers":["strategies used"]}}
```

Enforced by the checker before the row is kept: every `path` exists and is not prose documentation; every line
range is inside the file; `MATCHED`/`PARTIAL`/`CONFLICT` carry at least one evidence entry; a citation outside
the excerpts downgrades `confidence`. `searched` and `passes` are filled by the script from the real queries,
never taken from the model. `UNSEARCHED` means the answer was rejected or the request failed — `run --resume`
re-asks it.

## `verdicts.jsonl` — written by the adversarial pass, or by verifiers into `verify/batch-VNN.jsonl`

```json
{"id":"REQ-001","verified_status":"MATCHED|PARTIAL|MISSING|CONFLICT|UNVERIFIABLE","agree":true,
 "confidence":"high|medium|low","evidence":[{"path":"…","lines":"10-20","note":"…"}],
 "searched":["second-pass queries"],"reason":"<=200 chars"}
```

`agree` is recomputed by the script: it is false whenever `verified_status` differs from the preliminary status.

## `adjudications.jsonl` — your decisions (append-only; last entry per id wins)

```json
{"id":"REQ-007","final_status":"MISSING","note":"both passes searched hints + synonyms; no lockout logic anywhere","by":"lead","at":"2026-09-18 10:12:00"}
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

`adjudication` > `verifier verdict` > `first-pass finding` > `UNSEARCHED`; items tagged
`static-limit`/`ambiguous` are always `UNVERIFIABLE`. A `MISSING` that never had a second pass fails
`audit.py check`.

## `index.json` (internal)

The repo index built by `brief`: candidate file list (prose documentation already excluded), per-file line
counts, a symbol index (`def`/`class`/`function`/`fn`/`func`/`interface`/`type`/`CREATE TABLE`/prisma `model`)
and a route index (Flask/Express/Gin/Spring-style route literals). Rebuilt only by `brief`; delete the file and
re-run `brief` if the repository changed substantially mid-audit.

## `state.json` / `config.json` (internal)

`state.json`: the run summary (duration, wave sizes, api calls, token and cached-token counts, peak threads),
agent-lane batch bookkeeping, the spot-check sample. `config.json`: `active`, `repo_root`, `out_dir`,
`spec_files`, `lang`, `lane`, `tier`, `threads`, `base_url`, `route`, `models`, `retrieval`. Safe to inspect.
