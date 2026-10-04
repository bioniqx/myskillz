---

## Handoff: 2026-10-04T08:12:22Z (auto-saved before compaction)

### Compaction Metadata
- Trigger: auto
- Custom instructions: (none)
- Transcript: /Users/yamazaki-ethan/.claude/projects/-Users-yamazaki-ethan-Documents-Projects-skillz/e5c41901-b2ac-4249-8214-8c67b4177eff.jsonl
- CWD: /Users/yamazaki-ethan/Documents/Projects/skillz

### Last User Message (transcript tail)
(unavailable)

### Last Assistant Message (transcript tail)
(unavailable)

### Git Snapshot
- Branch: main
- Status:
 M claude-skills/CLAUDE.md
 M glm-skills/CLAUDE.md
 M hybrid-skills/CLAUDE.md
 M opencode-skills/AGENTS.md
?? .claude/
?? CLAUDE.md
?? claude-skills/docs/superpowers/plans/2026-10-04-variant-parity-repair.md
?? claude-skills/docs/superpowers/specs/2026-10-04-variant-parity-repair-design.md
?? docs/
?? opencode-skills/CLAUDE.md
- Recent commits:
4a3bbfd commit
747e316 commit
d54683a commit
6fe4ec4 commit
0675707 commit

### Model Summary
- Goal: make glm-skills, hybrid-skills and opencode-skills variants keep the same core as the originals in claude-skills, differing only by harness mechanics; plus port the opencode v2.0.22 `shell` permission key.
- Spec and plan (untracked, never commit): claude-skills/docs/superpowers/specs/2026-10-04-variant-parity-repair-design.md and .../plans/2026-10-04-variant-parity-repair.md (50 tasks T01–T50).
- Execution: claude-dev-team-v3.2 with PLAN ADOPTION, profile balanced, in a separate integration worktree on branch parity-repair (scratchpad/skillz-parity), so the user's dirty tree on main stays untouched.
- Progress at this point: 25/50 slices merged (T01–T09, T11, T12, T16, T18, T20, T22, T24, T26, T30, T32, T34, T36, T39–T42); checkpoints 1–2 pass (vacuous: no gate commands configured).
- In flight: F1 (hybrid audit stale frozen tests); reviewers r3-1..r3-5 running. Review verdicts so far: r1-3 and r2-4 CHANGES_REQUIRED (1 MAJOR each), r2-1 and r2-5 APPROVED; the engine harvests fix slices on the next `devteam next`.
- Pending: F2, T10, T13, T14, T15, T17, T19, T21, T23, T25, T27–T29, T31, T33, T35, T37, T38, T43, T45–T49, T50 (Conductor-only verification).
- Engine currently limits programmers to about 1 free slot at a time (API rate limits); lanes die on 429 and are resumed via SendMessage.
- Binding constraints: never stash/reset/stage/commit the six user guide files (root CLAUDE.md, claude-skills/CLAUDE.md, glm-skills/CLAUDE.md, hybrid-skills/CLAUDE.md, opencode-skills/AGENTS.md, opencode-skills/CLAUDE.md); edit nothing outside the repo; never push or merge into main; commit only on parity-repair.
- Guide-file edits (T02 CLAUDE.md part, T43–T46, T50 baselines) must be applied by hand on the main working tree, uncommitted, at the end.
- Done criteria: spec section 5 — all suites (claude 561, glm 671, oc 470, hybrid four suites) plus four selftests pass; quote failing lines verbatim.

### Handoff Context (paste into next session)
1. Integration worktree: /private/tmp/claude-501/-Users-yamazaki-ethan-Documents-Projects-skillz/e5c41901-b2ac-4249-8214-8c67b4177eff/scratchpad/skillz-parity (branch parity-repair). Run everything from there.
2. Event loop: `python3 ~/.claude/skills/claude-dev-team-v3.2/scripts/devteam.py next` on every completion notification; act on each printed DISPATCH/REVIEW/CHECKPOINT block verbatim, then end the turn. `devteam status` shows the DAG.
3. Dispatch a DISPATCH line as Agent(subagent_type claude-programmer, prompt `python3 ~/.claude/skills/claude-dev-team-v3.2/scripts/devteam.py claim <ID>`, run_in_background); reviewers as the printed claude-code-reviewer prompts.
4. Slot limit is small right now; READY slices are dispatched one at a time as lanes finish. If a lane dies (429), resume it with SendMessage to its agent id, else `devteam retry <id>`.
5. Review reports land in .claude/dev-team/reviews/*.report.md; the engine harvests fix slices itself. Anything UNKNOWN: read the report, then `devteam add-fixes <report>`.
6. Known caveats to disclose in the final report: vacuous checkpoint gate, only part of the plan tasks got a plan-level review, T39 deviation (quote-aware chain split), lanes branch from main HEAD rather than parity-repair, F1/F2 follow-up slices, selftest FAILs in glm/oc possibly from macOS /var vs /private/var.
7. After DAG exhausted: final sharded review + checkpoint, then conductor T50: run all suites and the four selftests in the worktree, apply the six guide-file edits by hand on main (uncommitted), record real baselines.
8. `devteam finish` only when reviews are APPROVED (loop cap 2; leftovers to the user). Never push or merge to main; never commit docs/superpowers or the six user guide files.
9. Memory note saved: opencode-shell-permission-unported (project memory) — update it once the shell-key port is merged.
10. Final output: short Vietnamese report (persona Thảo to anh Châu): what passed, failures with exact error lines, deferred tasks and why, branch name parity-repair and commit list.

---
