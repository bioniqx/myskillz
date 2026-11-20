# How ZCode loads skills

Facts verified against ZCode 3.14.4 and the bundled zcode-guide plugin
(zcode-configuration-guide 0.3.0) in 2026-11. Re-check after a ZCode upgrade;
loading rules are harness behavior and can change between versions.

## Where skills live

| Scope | Path | Use when |
|---|---|---|
| User | `~/.zcode/skills/<name>/` | Personal skills available in every workspace (the `-g` default to recommend) |
| Project | `<repo>/.zcode/skills/<name>/` | Team-shared, versioned with the repository |
| User fallback | `~/.agents/skills/` | Sharing one install across other coding agents |
| Project fallback | `<repo>/.agents/skills/` | Same, project-level |

## Discovery order and shadowing

1. Explicitly configured roots
2. User `~/.zcode/skills`
3. User `~/.agents/skills`
4. Workspace `.zcode/skills` (each level from cwd up to the repo root)
5. Workspace `.agents/skills`
6. Enabled plugin roots

Identity is the file path, so same-named skills at different paths are all
discovered, but only the first in this order loads: a user-scope skill
shadows a project-scope skill of the same name. The `validate_install.py`
script reports this case as a WARN.

## Hard limits and triggers

- A frontmatter `description` over 1024 characters makes ZCode drop the whole
  skill at load time.
- The loaded body is truncated above 100KB.
- Each turn the model sees only the skill name plus the first ~250 characters
  of the description when deciding to trigger, so the WHEN clause must sit at
  the front.
- `name` must be lowercase kebab-case, 1-64 chars, and equal to the directory
  name.
- Unknown frontmatter keys are ignored; there is no `!` preload.

## Session reload

Skills are read at session start. Anything installed or reconfigured
mid-session - including via `npx skills add` - takes effect only in a NEW
ZCode session. When a user reports a just-installed skill "not working",
the first check is whether they restarted the session; the second is
Settings -> Skills to confirm discovery.
