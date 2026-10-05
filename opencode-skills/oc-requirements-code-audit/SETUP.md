# Setup — requirements-code-audit (OpenCode v2)

One kind of worker: a background `subagent` dispatched from an interactive OpenCode session. Every worker uses
the model selected in the OpenCode window. Nothing here sets a provider, a model or a key.

## 1. Install

Requires OpenCode v2 (2.0.20 or later), python3 and, recommended, ripgrep.

    python3 oc-requirements-code-audit/scripts/oc_audit.py setup --harness opencode

That copies the folder to `~/.config/opencode/skills/oc-requirements-code-audit/` and renders the worker agents
`oc-rca-investigator`, `oc-rca-verifier` and `oc-rca-parser` into `~/.config/opencode/agents/` (`--dry-run` prints what
it would do). The agents are rendered from the neutral sources in `opencode/agents/` (`mode: subagent`, read
access, edits limited to `.oc-audit/`, no shell, no `model` field). Never copy those sources by hand, since the raw files omit
fields OpenCode requires. To install the agents alone:

    python3 oc-requirements-code-audit/scripts/oc_harness.py install oc-requirements-code-audit 2

The agent loads the instructions through its `skill` tool by name.

## 2. Check the environment

    python3 oc-requirements-code-audit/scripts/oc_audit.py doctor

It prints the python version, the ripgrep path, the OpenCode version and the lane width (workers per wave). It
makes no network call. To confirm the three `oc-rca-*` agents are installed, run:

    python3 oc-requirements-code-audit/scripts/oc_harness.py check oc-requirements-code-audit

Concurrency: at most 8 workers run at once (the provider allows 8 concurrent calls). `OC_MAX_LANES` sets the wave
width, default 8; a lower value narrows it and a higher one is clamped to 8. `--threads` and `AUDIT_THREADS` are clamped
to 8 the same way.

## 3. ripgrep

Strongly recommended — it is the retrieval engine. Without it the script falls back to a pure-Python scanner,
which is correct but much slower on large repositories.

    brew install ripgrep   #  macOS
    apt install ripgrep    #  Debian/Ubuntu

## 4. Permissions

The audit needs to run one script and write under one directory:

- Shell: `python3 <skill>/scripts/oc_audit.py …`.
- Writes: `<cwd>/.oc-audit/**` only. The codebase is never modified.
- The worker agents may edit only files under `.oc-audit/` and have no shell.
- Allow the script in your `permission` config if you run in a mode that asks.

## 5. Where things go

- `<cwd>/.oc-audit/` — everything the audit writes: `index.json`, `repo-map.txt`, `spec/`, `checklist.jsonl`,
  `findings/`, `verify/`, `findings.jsonl`, `verdicts.jsonl`, `adjudications.jsonl`, `plan.jsonl`,
  `requirements-code-audit.md`, `traceability.csv`, `state.json`, `config.json`, and the worker briefs. Added to
  `.git/info/exclude` automatically (local and untracked — the repository itself is not touched).
- `brief --force` archives a previous audit to `.oc-audit.prev-<timestamp>/`.
- Uninstall: delete the installed folder and the three `oc-rca-*.md` agent files. Nothing is written outside audit
  dirs.

## 6. Windows

Use `python` instead of `python3`. Everything else is stdlib and portable; install ripgrep for speed.
