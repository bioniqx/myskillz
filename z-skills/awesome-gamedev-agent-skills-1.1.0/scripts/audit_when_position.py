#!/usr/bin/env python3
"""WHEN-position audit for awesome-gamedev-agent-skills.

ZCode-class agents surface only the first ~250 characters of a skill's
``description`` on each turn, so the Use-when trigger clause must start
inside that window or the skill never fires on the words a developer
types. This script audits every ``skills/**/SKILL.md`` and
``router/SKILL.md`` and reports descriptions whose first Use-when clause
(``Use when ...``, ``Use to ...``, or ``Use for ...`` — the three lead
forms used in this package) is missing entirely or starts after the
~250-character preview window.

Self-contained and deterministic; no network access, no third-party deps.
The minimal frontmatter parser is the same one used by
``scripts/validate-skills.py`` (supports folded ``>`` / ``>-`` and literal
``|`` / ``|-`` block scalars).

Usage:
    python scripts/audit_when_position.py            # offenders + summary
    python scripts/audit_when_position.py --verbose  # every file, with lengths

Output: one line per offender (or every file with ``--verbose``), then a
summary line ``TOTAL <n> OFFENDERS <m>``. Exits 0 when there are no
offenders, 1 otherwise, so it can gate commits.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# ZCode previews only the first ~250 chars of a description each turn.
WINDOW = 250
# The when-clause lead: "Use when ...", "Use to ...", or "Use for ..." — the
# three forms this package uses. A description is an offender when it has no
# such clause, or when the first one starts after the preview window.
WHEN_RE = re.compile(r"Use (?:when|to|for)\b")

REPO_ROOT = Path(__file__).resolve().parent.parent


def find_skill_files() -> list[Path]:
    """Same file set as scripts/validate-skills.py: skills/**/SKILL.md + router."""
    files: list[Path] = []
    skills_dir = REPO_ROOT / "skills"
    if skills_dir.is_dir():
        files.extend(sorted(skills_dir.rglob("SKILL.md")))
    router = REPO_ROOT / "router" / "SKILL.md"
    if router.is_file():
        files.append(router)
    return files


def split_frontmatter(text: str) -> tuple[dict, int] | tuple[None, int]:
    """Return (frontmatter_dict, body_start_line) or (None, 0) if missing/malformed.

    Minimal YAML, shared with validate-skills.py: supports ``key: value`` and
    a folded/literal block scalar (``key: >`` or ``key: |``) whose value is
    the following more-indented lines.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, 0

    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, 0

    fm: dict[str, str] = {}
    i = 1
    key_line_re = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
    while i < end:
        raw = lines[i]
        if not raw.strip() or raw.lstrip().startswith("#"):
            i += 1
            continue
        if raw[:1] in (" ", "\t"):
            i += 1
            continue
        m = key_line_re.match(raw)
        if not m:
            i += 1
            continue
        key, inline = m.group(1), m.group(2).strip()
        if inline in (">", "|", ">-", "|-", ">+", "|+"):
            block: list[str] = []
            j = i + 1
            while j < end:
                bl = lines[j]
                if bl.strip() == "":
                    block.append("")
                    j += 1
                    continue
                if bl[:1] in (" ", "\t"):
                    block.append(bl.strip())
                    j += 1
                else:
                    break
            fm[key] = " ".join(p for p in block if p != "").strip()
            i = j
        else:
            fm[key] = inline.strip().strip('"').strip("'")
            i += 1
    return fm, end + 1


def when_position(description: str) -> int | None:
    """Char offset of the first Use-when clause, or None if absent."""
    m = WHEN_RE.search(description)
    return m.start() if m else None


def main() -> int:
    verbose = "--verbose" in sys.argv[1:]
    files = find_skill_files()
    if not files:
        print("TOTAL 0 OFFENDERS 0")
        return 0

    offenders: list[str] = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        fm, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        description = (fm or {}).get("description", "")
        pos = when_position(description)
        if verbose:
            pos_str = "MISSING" if pos is None else str(pos)
            print(f"{rel} use_when={pos_str} len={len(description)}")
        if pos is None:
            offenders.append(
                f"{rel}: description has no Use-when clause ('Use when'/'Use to'/'Use for')"
            )
        elif pos > WINDOW:
            offenders.append(
                f"{rel}: Use-when clause starts at char {pos}, after the {WINDOW}-char preview window"
            )

    print(f"TOTAL {len(files)} OFFENDERS {len(offenders)}")
    for line in offenders:
        print(f"  - {line}")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main())
