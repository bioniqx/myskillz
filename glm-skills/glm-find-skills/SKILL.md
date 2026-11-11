---
name: glm-find-skills
description: >-
  Use when the user asks to find, discover, install, or add an agent skill for
  ZCode ("find a skill for X", "is there a skill that can...", "how do I do X"
  when an existing skill likely covers it, "install a skill"), or has
  hand-downloaded a skill archive instead of using the CLI. Searches the open
  skills ecosystem with npx skills find, vets candidates by installs and
  source, installs with npx skills add <pkg> -a zcode, validates the result,
  and reminds that a new ZCode session loads it. Do NOT use for MCP servers,
  plugins, or skills already loaded in this session.
---

# Find Skills (ZCode / GLM port)

Discover and install skills from the open agent skills ecosystem into ZCode.
The skills CLI (`npx skills`, needs Node 22.20+) is the package manager, and
ZCode is a first-class agent target (`-a zcode`). CLI flags were verified
against vercel-labs/skills docs in 2026-11; if a command errors, re-check with
`npx skills add --help` before improvising.

## Flow

Work through the five steps in order; each step is one command or one script.

### 1. Understand the need

Identify the domain (React, testing, Godot, deployment) and the specific task.
If a built-in tool, a loaded skill, or an MCP server already covers it, do not
search - say so and use that instead.

### 2. Discover

Keyword search (non-interactive; prints install counts and skills.sh links):

    npx skills find <query>

Try 2-3 keyword variants ("react testing", "vitest", "frontend test"); a
specific pair beats one generic word. To see which skills a package contains
before installing anything:

    npx skills add <owner/repo> -l

### 3. Vet before recommending

Never recommend from the search line alone. Check:

- Install count: prefer 1K+; treat under 100 with caution.
- Source reputation: official orgs (vercel-labs, anthropics, microsoft) and
  known publishers over unknown authors.
- Recency: skills for fast-moving libraries go stale; check the repo's recent
  activity.

Present 1-3 candidates: what each does, its install count, and the exact
install command. Install counts change daily - present them as approximate.

### 4. Install into ZCode

    npx skills add <owner/repo@skill> -a zcode -g -y

- `-a zcode` targets ZCode specifically. Without it the CLI may prompt to
  pick an agent, or install for a different agent it auto-detected.
- `-g` installs user-level into `~/.zcode/skills` (the recommended default).
  Drop it for project-level `.zcode/skills` when the skill should be versioned
  with the repo and shared with the team.
- `-y` skips confirmation prompts. Add `-s <name>` to install one skill from
  a multi-skill repo; add `--copy` to copy files instead of symlinks.

Never download a skill archive by hand into the workspace. A hand-placed
folder lands outside both skill scopes, skips every frontmatter check, and
pollutes version control; the CLI installs the same package in one command.

### 5. Validate and reload

Run the validator (relative to this skill's folder; no args scans both
scopes):

    python3 scripts/validate_install.py [skill-dirs...]

Fix every FAIL it reports - rename the installed folder or trim its
description - before telling the user anything is installed. Then tell the
user to start a NEW ZCode session: skills load at session start, so a skill
installed mid-session will not trigger in the current one.

## When no skill matches

Say so plainly, offer to do the task directly with current capabilities, and
mention `npx skills init <name>` if the user wants to author their own skill.

## References

Read `references/zcode-skill-loading.md` when the user asks where skills
live, why an installed skill is not loading or looks shadowed, or whether to
choose user- or project-scope.
