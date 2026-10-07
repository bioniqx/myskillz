---
description: Audit whether a codebase implements a requirements document and produce a traceability report plus a prioritized fix plan.
---

Load the glm-requirements-code-audit skill and audit against: $ARGUMENTS

First step: run `python3 {{SKILL_DIR}}/scripts/audit.py brief --spec $ARGUMENTS`, write the checklist it asks for,
then follow the skill's flow: `audit.py run`, `audit.py queue`, `audit.py adjudicate`, write plan.jsonl,
`audit.py finalize`.
