# Reviewer brief template

Fill every `<placeholder>`, then hand the brief to a **fresh** subagent that did NOT write the doc. In sequential mode (no subagents), re-read the doc yourself with deliberately skeptical eyes and apply the same checklist. One brief per doc.

```
You are reviewing and, where needed, fixing ONE doc. Fresh, skeptical eyes.

Doc under review: <output dir>/<slug>.md (read it)
Verify against code — read ONLY the files this doc references/claims about:
  <same scoped file list given to the writer>
Manifest for context: .claude/doc-generator/recon.md

Check:
1. Correctness — do endpoints, signatures, commands, and described behavior
   match the code exactly? Flag anything invented or drifted.
2. Fidelity to requirements (for spec/traceability/test docs) — does the doc
   reflect the read-only requirements docs, and are code-vs-requirement
   mismatches flagged rather than hidden?
3. Completeness — does it cover its stated scope for its audience?
4. Clarity — can the target audience follow it? Fix confusing structure,
   undefined terms, missing examples. Check any Mermaid diagram matches
   the code.
5. Safety — no leaked secrets (credentials, keys, tokens, real internal
   hosts/IPs/URLs). A leak is a blocking issue: replace with placeholders.

Fix by editing <output dir>/<slug>.md directly: rewrite only the flagged
sections (rewrite the whole doc only if it is broadly wrong). Preserve
what's good. Never edit READ-ONLY requirements paths.

Return only: PASS or FIXED, plus a short list of issues found and what you
changed. Do not paste the doc.
```
