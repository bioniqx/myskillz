---
description: Audit whether a codebase implements a requirements document and produce a traceability report plus a prioritized fix plan.
---

Load the requirements-code-audit skill and audit against: $ARGUMENTS

First step: run `python3 {{SKILL_DIR}}/scripts/audit.py brief --spec $ARGUMENTS` to build the checklist,
then follow the skill's run -> finalize flow.
