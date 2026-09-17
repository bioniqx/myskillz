# Writer brief template

Fill every `<placeholder>`, then hand the complete brief to one writer subagent (or follow it yourself in sequential mode). One brief per doc.

```
You are writing ONE documentation file. Be correct, concrete, and easy to read.

Context (read first): .claude/doc-generator/recon.md
Doc to write: <title>
Tag: <create | update>
Audience: <audience> — pitch depth and vocabulary to them.
Scope — read ONLY these files, nothing else: <explicit file list from manifest>
Output file: <output dir>/<slug>.md   (never write into a READ-ONLY requirements path)
Language: <language — default English>

Rules:
- If Tag is "update": read the existing doc at the output path FIRST. Preserve
  content that is still accurate and anything a human added that the code
  cannot reveal (business rationale, decisions, external links). Rewrite only
  stale or wrong parts, and list what you removed or heavily rewrote in your
  summary.
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
  structure — keep it accurate to the code. GitHub/GitLab render Mermaid
  natively.
- Structure with clear headings; keep prose tight. Non-technical docs lead
  with outcomes and avoid jargon; technical docs can assume the audience.
- Do NOT read files outside the scope list — if you think you need one,
  note it at the end instead of reading it.

Return only: the output path and a 3–5 line summary (what you wrote, any
gaps or assumptions). Do not paste the doc back.
```
