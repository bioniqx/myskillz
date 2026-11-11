## Review verdict: APPROVED

## Summary
The glm-find-skills ZCode port meets all three approved acceptance criteria: SKILL.md has the exact install command, five-step flow, anti-pattern, staleness note and a 569-char WHEN-first description (measured); validate_install.py implements every specified check with correct exit codes and a green 9-assert selftest; the reference doc's loading mechanics match the bundled zcode-guide plugin and its CLI facts match the live vercel-labs/skills docs fetched during this review.

## Evidence
Commands run (all from repo root /Users/yamazaki-ethan/Documents/Projects/mine/skillz/glm-skills):
- `git status --short glm-find-skills` → `?? glm-find-skills/` (untracked, full-content review as briefed)
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests -p test_all_skills.py -v` → `Ran 5 tests in 0.203s` / `OK`. Note: `test_all_scripts_compile` walks GLM_ROOT recursively, so glm-find-skills/scripts/validate_install.py is compile-covered; the hygiene/vendored tests sweep `ALL_SKILLS` (test_all_skills.py:25-35) which intentionally excludes glm-find-skills — the approved criteria give this slice its own --selftest instead.
- `PYTHONDONTWRITEBYTECODE=1 python3 glm-find-skills/scripts/validate_install.py --selftest` → `SELFTEST ok=9`
- `PYTHONDONTWRITEBYTECODE=1 python3 glm-find-skills/scripts/validate_install.py glm-find-skills` → `PASS glm-find-skills - name=glm-find-skills description=569 chars` / `RESULT fail=0 warn=0` / exit=0
- grep zcode-guide plugin cache → diagnosing-skills/SKILL.md:27,31,42,47 confirms the 1024-char drop rule and ~250-char trigger truncation cited by the reference doc; nothing contradicting it.
- grep scoped files for `TODO|FIXME|not implemented|XXX|skip|xfail|.only` → only prose hits ("skips confirmation prompts", "skipping entries without SKILL.md"); no placeholders, no skipped tests.

Files read in full: glm-find-skills/SKILL.md (95 lines), glm-find-skills/scripts/validate_install.py (203 lines), glm-find-skills/references/zcode-skill-loading.md (49 lines); plus _shared/tests/test_all_skills.py:20-59,95-119 and the bundled zcode-guide/zcode-configuration-guide SKILL.md (100 lines).
External verification (web fetch, 2026-11-10): github.com/vercel-labs/skills README + docs/commands.md + docs/agents.md confirm `-a zcode` → `.zcode/skills/` / `~/.zcode/skills/`, `-g`, `-y`, `-s`, `-l/--list`, `--copy`, `find [query]`, `init [name]`, and "Requires Node.js 22.20 or later". No fabricated CLI flags found in SKILL.md.

Acceptance criteria, checked item by item:
1. SKILL.md: name glm-find-skills == folder (validated by run); description WHEN-first ("Use when the user asks..."), 569 chars < 1024 (validator-measured), negative constraint present ("Do NOT use for MCP servers, plugins, or skills already loaded in this session."); body 95 lines < 150, imperative; staleness note at SKILL.md:18-20 dated 2026-11 with re-check advice; five-step flow (Understand → Discover → Vet → Install → Validate/reload) with the new-session reminder at SKILL.md:82-83; install command `npx skills add <owner/repo@skill> -a zcode -g -y` at SKILL.md:59 with user/project scope explanation at 63-65; hand-download anti-pattern at SKILL.md:69-71.
2. validate_install.py: stdlib only (os, re, sys, tempfile); args = skill dirs, no args scans ~/.zcode/skills and <cwd>/.zcode/skills (lines 126-128); SKILL.md presence (54-55), kebab name + equals dir (61-67), description present and <=1024 (68-73), trigger text in first 250 chars WARN (74-76), 100KB FAIL (77-79) and >500 lines WARN (80-82), cross-scope shadowing WARN (114-118) with shadow direction (earlier root = user scope wins) matching the bundled guide's discovery order; exit 0 pass / 1 any FAIL (139-141) / 2 no skills (130-132); --selftest covers pass, name!=dir, >1024 desc, non-kebab name, big-body FAIL+WARN, missing SKILL.md, fail count, shadowing, and direct skill-dir arg.
3. references/zcode-skill-loading.md: scope table, discovery order 1-6, path-identity shadowing with user-over-project priority, and 1024/250-char limits all match the bundled zcode-configuration-guide SKILL.md (lines 30, 53-62) and diagnosing-skills SKILL.md; staleness note at lines 3-5; referenced from SKILL.md:90-94 only for off-happy-path questions.

Explicit check classes (all clear): placeholders — none; swallowed errors — no try/except in the script, no empty catch, unreadable/missing roots skip by design with an exit-2 fallback; tautological/skipped/empty tests — none, selftest asserts real failure modes and ran green; hard-coded expected values — the constants (1024, 250, 100KB, 500, kebab 1-64) are exactly the approved spec values; fabricated symbols — all stdlib usages exist, all CLI flags verified against upstream docs.

Unverified: nothing material. The `owner/repo@skill` shorthand in the install command is the form pinned by the approved design itself (and matches skills.sh-generated install commands); the 100KB-truncation and kebab-1-64 claims in the reference doc are not stated in the bundled plugin docs but are mandated verbatim by the approved acceptance criteria, and the doc's staleness note covers drift.

Considered and rejected as below the reporting bar: (a) a CRLF-ended SKILL.md would falsely FAIL the frontmatter parse (FM_RE is LF-anchored) — exotic input, safe-direction failure with a clear message, not in the criteria; (b) the no-skills branch prints `RESULT fail=2` where "2" is the exit code, not a fail count — cosmetic, exit code itself is correct; (c) `--selftest` anywhere in argv overrides positional dirs — usage nuance, self-documented.

## Findings
No issues found.
