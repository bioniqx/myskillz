# Setup — requirements-code-audit (GLM edition)

Two lanes. The **api lane** is the fast one and needs a key; the **agent lane** needs nothing and is picked
automatically when no key is found.

## 1. Install

```bash
# ZCode
python3 requirements-code-audit/scripts/audit.py setup --harness zcode
# OpenCode
python3 requirements-code-audit/scripts/audit.py setup --harness opencode
```

That copies the skill to the harness's skills directory and the matching agent files to its agents directory
(`--dry-run` prints what it would do). By hand instead:

| Harness | Skill | Agents (fallback lane) |
|---|---|---|
| ZCode | `~/.zcode/skills/requirements-code-audit/` | `~/.zcode/agents/rca-*.md` from `agents/zcode/` |
| OpenCode | `~/.config/opencode/skills/requirements-code-audit/` (also reads `~/.claude/skills/` and `~/.agents/skills/`) | `~/.config/opencode/agents/rca-*.md` from `opencode/agents/` |

Invoke it in ZCode with `$requirements-code-audit <spec file>`; in OpenCode the agent loads it through its
`skill` tool by name.

## 2. Environment

```bash
export ZAI_API_KEY=<your GLM Coding Plan key>
export ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic
export ANTHROPIC_AUTH_TOKEN=$ZAI_API_KEY      # for the harness itself
```

`audit.py` also reads the key from `~/.zcode/*.json`, `~/.config/opencode/auth.json`,
`~/.config/opencode/opencode.json` and `~/.claude/settings.json` — only from fields whose name says they hold
one (`apiKey`, `ANTHROPIC_AUTH_TOKEN`, `token`, …), never by scanning strings.

The OpenAI-compatible route works too: point `ZAI_BASE_URL` at `https://api.z.ai/api/paas/v4` and the client
switches to `chat/completions` with a `Bearer` header.

Verify:

```bash
python3 <skill>/scripts/audit.py doctor --ping
```

It prints python and ripgrep versions, where the key came from, the resolved endpoint and route, the thread
count, the tier table, a live ping to both models, and the request shape the gateway accepted.

## 3. ripgrep

Strongly recommended — it is the retrieval engine. Without it the script falls back to a pure-Python scanner,
which is correct but much slower on large repositories.

```bash
brew install ripgrep   #  macOS
apt install ripgrep    #  Debian/Ubuntu
```

## 4. Threads

64 by default. Override with `run --threads N`, or `AUDIT_THREADS=N`. Lower it if the endpoint rate-limits you
(the client already backs off on 429/5xx); raise nothing above 64.

## 5. Permissions

The skill needs to run one script and write under one directory:

- Bash: `python3 <skill>/scripts/audit.py …`
- Writes: `<cwd>/.audit/**` only. The codebase is never modified.
- On the api lane the workers are HTTPS requests, not agents, so no per-agent tool permissions apply.
- OpenCode: allow the script in your `permission` config if you run in a mode that asks. ZCode: the agent files
  already deny `edit`/`bash` for the fallback workers.

## 6. Where things go

- `<cwd>/.audit/` — everything the audit writes: `index.json`, `repo-map.txt`, `spec/`, `checklist.jsonl`,
  `findings.jsonl`, `verdicts.jsonl`, `adjudications.jsonl`, `plan.jsonl`, `requirements-code-audit.md`,
  `traceability.csv`, `state.json`, `config.json`. Added to `.git/info/exclude` automatically (local and
  untracked — the repository itself is not touched).
- `brief --force` archives a previous audit to `.audit.prev-<timestamp>/`.
- Uninstall: delete the skill folder and the two agent files. Nothing is written outside audit dirs.

## 7. Windows

Use `python` instead of `python3`. Everything else is stdlib and portable; install ripgrep for speed.
