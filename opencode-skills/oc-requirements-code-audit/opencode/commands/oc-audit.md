---
description: Audit whether a codebase implements a requirements document and produce a traceability report plus a prioritized fix plan.
---

Load the oc-requirements-code-audit skill and audit against: $ARGUMENTS

First step: run `python3 {{SKILL_DIR}}/scripts/oc_audit.py brief --spec $ARGUMENTS` to build the checklist,
then follow the skill's plan -> status -> queue -> adjudicate -> finalize flow.
