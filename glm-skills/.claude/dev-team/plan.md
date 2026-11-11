# Plan — ZCode/GLM adaptation of awesome-gamedev-agent-skills 1.1.0

## Understanding

Approved Bounded design (glm-brainstorming, DECISION pick=A margin=5, breaker NO-BREAK with the
package validator as check). Four mechanical changes, all inside
`glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/` (paths below are git-root relative):

1. Front-load the WHEN clause into the first ~250 chars of the 7 offending descriptions
   (audit this session: TOTAL 67, OFFENDERS 7 — camera-systems 348, performance-optimization 337,
   game-ui-ux 337, game-feel 283, input-systems 287, godot-multiplayer 279, godot-export 251),
   plus "not for X" pointers for overlapping sibling pairs. Done via a deterministic script kept
   in the package (`scripts/audit_when_position.py`) so the audit is re-runnable.
2. Bare-skill-name dispatch in the 3 router files (no `skills/<category>/<name>/` path references).
3. Cap initial composition at 3 skills (engine skill + 1-2 most relevant; remainder on-demand via
   the existing pivot rule). Genre `composes` tables stay as the exhaustive reference.
4. ZCode row in `docs/COMPATIBILITY.md`.

Out of scope: no `when_to_use` key (package validator hard-rejects it), no engine subset, no
body/reference rewrites, no changes outside the package folder, no install into `~/.zcode/skills`.

## Open questions

- Resolved: baseline committed to main as 987dca0 (user approved) so programmer worktrees see the
  package.

## Assumptions

- Keep all 66 skills (user has not named an engine subset).
- Repo hygiene suite baseline: 5 tests, all OK (recorded before start).
- The sibling untracked folder `glm-find-skills/` belongs to another session — never staged.

## Dispatch DAG

S1 (refactor, 7 SKILL.md + new audit script) ∥ S2 (docs, 3 router files) ∥ S3 (docs, COMPATIBILITY.md).
No deps; disjoint footprints; 3 parallel lanes.

```json
{"request": "Adapt glm-awesome-gamedev-agent-skills-1.1.0 in place for ZCode + GLM 5.3 flash: WHEN-front-load 7 descriptions, bare-name router dispatch, cap-3 initial composition, ZCode row in COMPATIBILITY.md",
 "profile": "balanced",
 "glm": {"tier": "api"},
 "commands": {"build": "none",
              "test": "cd glm-skills && PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py",
              "test_file": "none",
              "lint": "none",
              "lint_file": "none",
              "typecheck": "none",
              "typecheck_file": "none"},
 "contracts": [],
 "notes": "All slice files are git-root relative and live under glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/. The package format is FROZEN (docs/SKILL-FORMAT.md): never add frontmatter keys such as when_to_use or allowed-tools; description <=1024 chars; body <500 lines; name==folder; references must resolve. ZCode shows only the first ~250 chars of a description each turn, so the WHEN clause must lead. Rewrites are length-neutral or shorter. Third-party package under Apache-2.0: keep upstream style, English, no marketing language. Do not touch anything outside the slice footprint.",
 "test_globs": [],
 "slices": [
  {"id": "S1", "title": "WHEN front-load 7 descriptions + audit script",
   "goal": "Move the Use-when trigger clause inside the first 250 chars of the 7 offending descriptions and add a re-runnable position audit script",
   "kind": "refactor", "size": "small", "deps": [],
   "files": ["glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/skills/disciplines/camera-systems/SKILL.md",
             "glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/skills/disciplines/performance-optimization/SKILL.md",
             "glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/skills/disciplines/game-ui-ux/SKILL.md",
             "glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/skills/disciplines/game-feel/SKILL.md",
             "glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/skills/disciplines/input-systems/SKILL.md",
             "glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/skills/godot/godot-multiplayer/SKILL.md",
             "glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/skills/godot/godot-export/SKILL.md",
             "glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/scripts/audit_when_position.py",
             "glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/skills/godot/godot-2d-movement/SKILL.md",
             "glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/skills/godot/godot-3d-essentials/SKILL.md"],
   "risk": "low", "isolation": false,
   "criteria": ["scripts/audit_when_position.py prints TOTAL 67 OFFENDERS 0",
                "package validator exits 0",
                "each rewritten description has a Use-when clause starting inside its first 250 chars, keeps the same trigger vocabulary, and is not longer than before",
                "overlapping sibling pairs gain a not-for pointer (godot-2d-movement vs godot-3d-essentials, phaser-core vs phaser-arcade-physics, threejs trio, roblox-luau vs roblox-datastores)"],
   "edge_cases": ["folded (> / >-) description block scalars", "description with no literal Use-when phrase must gain one", "keep <=1024 chars"],
   "context": ["glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/docs/SKILL-FORMAT.md"],
   "verify": "cd glm-skills/glm-awesome-gamedev-agent-skills-1.1.0 && python3 scripts/audit_when_position.py && python3 scripts/validate-skills.py"},
  {"id": "S2", "title": "Router bare-name dispatch + cap-3 initial composition",
   "goal": "Router references skills by bare unique name so it works flat-installed, and caps the initial load at 3 skills",
   "kind": "docs", "size": "small", "deps": [],
   "files": ["glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/router/SKILL.md",
             "glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/router/references/routing-table.md",
             "glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/router/references/engine-detection.md"],
   "risk": "low", "isolation": false,
   "criteria": ["no skills/<category>/ style path references remain in the 3 router files; dispatch uses bare skill names (names are unique repo-wide)",
                "read protocol and composition rules cap the initial load at 3 skills (engine skill + 1-2 most relevant), remainder loaded on demand via the existing pivot rule",
                "genre composes tables stay unchanged as the exhaustive reference",
                "package validator exits 0 (references still resolve)"],
   "edge_cases": ["routing-table header line claiming folder paths", "engine-detection skill-set-root column", "worked examples referencing paths"],
   "context": ["glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/router/SKILL.md"],
   "verify": "cd glm-skills/glm-awesome-gamedev-agent-skills-1.1.0 && python3 scripts/validate-skills.py && ! grep -rn 'skills/godot\\|skills/unity\\|skills/unreal\\|skills/web-engines\\|skills/other-engines\\|skills/disciplines\\|skills/genres\\|skills/workflows' router/"},
  {"id": "S3", "title": "ZCode row in docs/COMPATIBILITY.md",
   "goal": "Document ZCode as a supported agent with its skills directories and trigger style",
   "kind": "docs", "size": "small", "deps": [],
   "files": ["glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/docs/COMPATIBILITY.md"],
   "risk": "low", "isolation": false,
   "criteria": ["agent table gains a ZCode row: project skills dir .zcode/skills/, user dir ~/.zcode/skills/, auto-trigger by description plus $<name> invocation",
                "the row or a following note states the package stays portable-core (no when_to_use) and relies on WHEN-front-loaded descriptions for ZCode triggering"],
   "edge_cases": ["table column mismatch with the existing header"],
   "context": ["glm-skills/glm-awesome-gamedev-agent-skills-1.1.0/docs/COMPATIBILITY.md"],
   "verify": "cd glm-skills/glm-awesome-gamedev-agent-skills-1.1.0 && python3 scripts/validate-skills.py"}
 ]
}
```
