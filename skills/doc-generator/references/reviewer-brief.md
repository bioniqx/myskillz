# Reviewer brief template

Only for HIGH-tier docs (LOW-tier docs get no reviewer per SKILL.md). Condense this and inline
it directly into each reviewer subagent's Task prompt in Wave 2 — a **fresh** subagent that did
NOT write the doc, never the writer. One brief per doc.

```
You are reviewing and, where needed, fixing ONE doc. Fresh, skeptical eyes.

Doc under review: <output dir>/<slug>.md (read it)
Verify against code — read ONLY the files this doc references/claims about:
  <same scoped file list given to the writer>
Manifest for context (inlined above, do not re-read): the recon manifest

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

Fix by editing <output dir>/<slug>.md directly in this same pass — check and
fix in one shot, never report-then-fix. Fix only the flagged sections,
in place. If most of the doc is wrong, do NOT rewrite it yourself — return
BROADLY_WRONG with your reasons instead. Preserve what's good.
Never edit READ-ONLY requirements paths.

Return ONLY one of: PASS, FIXED, or BROADLY_WRONG (with reasons), plus a
short list of issues found and what you changed. Max 5 lines. Do not paste
the doc.
```
