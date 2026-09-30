# Writer brief template

Condense this (drop what doesn't apply to the doc at hand) and inline it directly into each
writer subagent's Task prompt in Wave 1 — the subagent's first tool call must land on its
scoped target files, never on this file or the manifest file. One brief per doc.

```
You are writing ONE documentation file. Be correct, concrete, and easy to read.

Context (inlined above, do not re-read): the recon manifest (or its slice)
Doc to write: <title>
Tag: <create | update>
Audience: <audience> — pitch depth and vocabulary to them.
Scope — read ONLY these files, nothing else: <explicit file list from manifest, ≤ 12>
Output file: <output dir>/<slug>.md   (never write into a READ-ONLY requirements path)
Language: <language — default English>

Rules:
- If Tag is "update": read the existing doc at the output path FIRST. Preserve
  content that is still accurate and anything a human added that the code
  cannot reveal (business rationale, decisions, external links). Rewrite only
  stale or wrong parts, and note what you removed or heavily rewrote.
- Some scoped files may be READ-ONLY requirements docs — read them for
  intended behavior, but document what the CODE actually does; if code and
  requirements disagree, describe the code and flag the mismatch.
- Verify every technical claim against the files you read. Never invent
  endpoints, flags, function names, or behavior. If the code is unclear,
  say so rather than guessing.
- Never copy secrets into the doc: no credentials, API keys, tokens,
  passwords, or real internal hostnames/IPs/URLs. Use placeholders such as
  <API_KEY> or https://api.example.com.
- Show, don't just tell: include real commands, real signatures, short
  runnable examples taken from the actual code.
- For architecture, flow, or data-model docs, include a small Mermaid
  diagram (flowchart / sequenceDiagram / erDiagram) when it clarifies
  structure — keep it accurate to the code.
- Structure with clear headings; keep prose tight. Non-technical docs lead
  with outcomes and avoid jargon; technical docs can assume the audience.
- Do NOT read files outside the scope list — if you think you need one,
  note it at the end instead of reading it.

Self-verify before returning (this is what lets your doc skip review if it's LOW,
and cuts review work if it's HIGH):
- every quoted command matches the manifest's Commands: line or a real script name
- every quoted path exists in the manifest's file index
- no secrets anywhere in the doc
- every relative link points at a planned output path

Tier your own doc by its FINAL content, not your intent: if it contains any
command, endpoint, signature, schema, config value, code fence, or file path
→ HIGH. Only a doc with zero such content → LOW.

Return ONLY these ≤ 5 lines — do not paste the doc back:
title: <title>
path: <output path>
tier: <HIGH | LOW>
flags: <gaps, assumptions, or "none">
```
