# Data schemas (all JSON Lines: one object per line, UTF-8)

Everything lives under the audit dir (default `<cwd>/.audit/`). `audit.py` reads and writes these; the lead writes
only `checklist.jsonl`, `adjudications.jsonl` (usually via `audit.py adjudicate`) and `plan.jsonl`. Batches and
sections routed to opencode are written by `audit.py oc-run` (output file, event file and `oc/` scratch), never by hand.

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

**opencode rows.** A batch routed to opencode is written by `audit.py oc-run` from the model's marker block, and every
row it keeps also carries `"backend":"oc:<tier>"` (for example `"backend":"oc:std"`). Claude investigators, hedges and
retries never write the key; a row without it counts as `claude`. This row key, not the batch's `backend` in
`state.json`, says which backend investigated an item (the report's `Backends:` line and the `finish` telemetry use
it). Before writing, the oracle drops rows whose `id` is not in the batch, turns an invalid `status` into
`UNSEARCHED`, removes each citation that lies outside the repo, under `.git/`, in a doc path, or names a missing file
or line range (appending `oracle: dropped <path>:<lines> — <reason>` to `notes`), and sets `confidence: low` on a row
that lost a citation or is `MATCHED` with none left.

## `verify/batch-VNN.jsonl` — written by verifiers

```json
{"id":"REQ-001","verified_status":"MATCHED|PARTIAL|MISSING|CONFLICT|UNVERIFIABLE","agree":true,"confidence":"high|medium|low",
 "evidence":[{"path":"…","lines":"10-20","note":"…"}],"searched":["new strategies tried"],"reason":"≤200 chars"}
```

In preset `max` a verifier batch may be routed to opencode. `audit.py oc-run` then writes it through the same oracle
(an invalid `verified_status` becomes `UNSEARCHED`, oracle notes go to `reason`) and adds `"backend":"oc:<tier>"` to
every row. Claude verifiers never write the key.

## `parse/section-NN.jsonl` — written by parsers (large specs, `parse-plan` / `parse-merge`)

Each row is one checklist item with the `checklist.jsonl` keys above. In preset `max` a section may be routed to
opencode; `audit.py oc-run` then writes the rows parsed from the marker block unchanged apart from
`"backend":"oc:<tier>"`, after running the checklist validation on them. The lead's faithfulness pass and
`parse-merge --accept` stay mandatory in every preset.

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

Added by hybrid-requirements-code-audit:

- `backend` on every entry of `batches` and `verify`: `"claude"` or `"oc:<tier>"`, the backend the batch was
  dispatched to. A fallback sets it to `"claude"`.
- `parse.backends`: `{"section-NN": "claude" or "oc:<tier>"}`.
- `cooldown`: `{"<tier>": <epoch seconds>}`. After a `throttle` fallback `status` sets it to now +
  `throttle_cooldown_s`; until then that tier's queued batches go to Claude.
- `fallbacks`: `{"<name>": "<reason>"}` for every opencode batch, verifier batch or section that fell back to Claude;
  each name is handled once.

`cooldown` and `fallbacks` appear only once needed. `oc-run` never writes `state.json`; `status` (and `plan`,
`parse-plan`, `parse-merge`) do.

## `config.json` (internal, also read by the guard hook)

`active`, `repo_root`, `out_dir`, `spec_files`, `lang`, `cap`, `agents` (plugin/local/generic/solo), `models`, `scripts_dir`.
The `ACTIVE` marker next to it arms the hook; `audit.py finish` removes it.

Added by hybrid-requirements-code-audit: `preset` (the effective preset: `init --preset`, else the routing file's
`preset`) and `routing` (the user routing file deep-merged over `routing.default.json`: `tiers`, `roles`, `max_roles`,
`oc_batch_max`, `max_repairs`, `throttle_cooldown_s`), both recorded at `init`.

## `events/<name>.json` — completion events

The req-audit guard hook writes one per Claude worker on `SubagentStop` (`batch`, `ok`, `agent_type`, `agent_id`,
`msg`). `audit.py oc-run` writes one per opencode batch, verifier batch or section:

```json
{"batch":"batch-07","ok":false,"agent_type":"opencode:ha-investigator","backend":"oc:std","reason":"format",
 "message":"ids still missing after 3 rounds","rounds":3,"written":3,"total":4,"t":1790000000.0}
```

| key | meaning |
|---|---|
| `batch` | batch, verifier batch or section name |
| `ok` | true only when every id was written (sections: a non-empty block with no parse errors) |
| `agent_type` | `opencode:ha-<role>` (`investigator`, `verifier` or `parser`) |
| `backend` | `oc:<tier>` |
| `reason` | `null` on success, else `spawn`, `crash`, `stall`, `timeout`, `unavailable`, `throttle`, `format`, `down` or `cooldown` |
| `message` | provider or runner message |
| `rounds` | opencode turns spent (first turn plus repair turns; 0 when it never spawned) |
| `written` / `total` | ids written / ids in the batch (`total` is 0 for sections) |
| `t` | epoch seconds |

A batch that ends with some ids written keeps them. On a failed event `status` marks an `unavailable` tier down in the
doctor cache, starts the tier's cooldown on `throttle`, moves the event to `oc/<name>.event.json`, records the fallback
and re-dispatches the uncovered ids to Claude; `parse-merge` prints a Claude parser line for a failed section.

## `oc/` — opencode scratch (internal)

Per turn: `<name>.<round>.jsonl` (the raw opencode event stream) and `<name>.<round>.err` (stderr); plus
`<name>.event.json` for each event set aside after a fallback. For debugging only; the lead never reads them.
