#!/usr/bin/env python3
"""Validator for awesome-gamedev-agent-skills.

Checks every ``skills/**/SKILL.md`` and ``router/SKILL.md`` against the authoring
standard in ``docs/SKILL-FORMAT.md``:

* valid YAML frontmatter delimited by ``---`` lines;
* ``name`` present, <=64 chars, lowercase ``a-z``/``0-9``/hyphens, no leading or
  trailing hyphen, and equal to the containing folder name;
* ``description`` present, non-empty, <=1024 chars;
* the file is shorter than 500 lines;
* every internal ``references/`` link in the body resolves to a real file;
* no forbidden agent-specific frontmatter key is present (docs/SKILL-FORMAT.md
  §2.2) — any of them fails the run;
* ``allowed-tools`` is absent — its presence is reported as a warning.

Exits 0 when everything passes, 1 when any skill fails. Warnings never change
the exit code. No third-party deps.

Usage:
    python scripts/validate-skills.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024
MAX_LINES = 500

# docs/SKILL-FORMAT.md §2.2: agent-specific keys that must never appear in a
# committed SKILL.md (hard reject), and keys the open standard allows but this
# repo deliberately omits (warning only).
FORBIDDEN_FRONTMATTER_KEYS = (
    "when_to_use",
    "argument-hint",
    "disable-model-invocation",
    "user-invocable",
    "model",
    "paths",
    "hooks",
    "shell",
    "context",
    "globs",
    "alwaysApply",
    "trigger",
)
WARNED_FRONTMATTER_KEYS = ("allowed-tools",)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Markdown links: [text](target)  and  inline-code paths: `references/foo.md`
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
CODE_PATH_RE = re.compile(r"`([^`]*references/[^`]+?\.md)`")


def find_skill_files() -> list[Path]:
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

    Minimal YAML: supports ``key: value`` and a folded/literal block scalar
    (``key: >`` or ``key: |``) whose value is the following more-indented lines.
    Sufficient for the ``name`` and ``description`` fields we validate.
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
        # only treat top-level (non-indented) keys as fields
        if raw[:1] in (" ", "\t"):
            i += 1
            continue
        m = key_line_re.match(raw)
        if not m:
            i += 1
            continue
        key, inline = m.group(1), m.group(2).strip()
        if inline in (">", "|", ">-", "|-", ">+", "|+"):
            # block scalar: collect following indented lines
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


def validate_file(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    rel = path.relative_to(REPO_ROOT).as_posix()
    text = path.read_text(encoding="utf-8")

    # line count
    line_count = len(text.splitlines())
    if line_count >= MAX_LINES:
        errors.append(f"file is {line_count} lines (must be < {MAX_LINES})")

    fm, _ = split_frontmatter(text)
    if fm is None:
        errors.append("missing or malformed YAML frontmatter (need opening and closing '---')")
        return [f"{rel}: {e}" for e in errors], []

    # name
    name = fm.get("name", "")
    folder = path.parent.name
    if not name:
        errors.append("frontmatter 'name' is missing or empty")
    else:
        if len(name) > MAX_NAME:
            errors.append(f"'name' is {len(name)} chars (max {MAX_NAME})")
        if not NAME_RE.match(name):
            errors.append(
                f"'name' = {name!r} must be lowercase a-z/0-9/hyphens with no leading/trailing hyphen"
            )
        # router/SKILL.md lives in 'router'; skills live in their own folder
        if name != folder:
            errors.append(f"'name' = {name!r} must equal folder name {folder!r}")

    # description
    desc = fm.get("description", "")
    if not desc:
        errors.append("frontmatter 'description' is missing or empty")
    elif len(desc) > MAX_DESCRIPTION:
        errors.append(f"'description' is {len(desc)} chars (max {MAX_DESCRIPTION})")

    # forbidden / discouraged frontmatter keys (docs/SKILL-FORMAT.md §2.2)
    for key in fm:
        if key in FORBIDDEN_FRONTMATTER_KEYS:
            errors.append(f"forbidden frontmatter key {key!r} (docs/SKILL-FORMAT.md §2.2)")
        elif key in WARNED_FRONTMATTER_KEYS:
            warnings.append(
                f"frontmatter key {key!r} is present (the open standard allows it but this repo omits it)"
            )

    # internal references/ links resolve
    targets = set(MD_LINK_RE.findall(text)) | set(CODE_PATH_RE.findall(text))
    for target in targets:
        link = target.strip()
        # ignore external links and pure anchors
        if link.startswith(("http://", "https://", "#", "mailto:")):
            continue
        link = link.split("#", 1)[0].split("?", 1)[0]
        if not link:
            continue
        if "references/" not in link:
            continue
        resolved = (path.parent / link).resolve()
        if not resolved.exists():
            errors.append(f"reference link does not resolve: {target!r}")

    return [f"{rel}: {e}" for e in errors], [f"{rel}: {w}" for w in warnings]


def main() -> int:
    files = find_skill_files()
    if not files:
        print("No SKILL.md files found yet (skills/** and router/ are empty). OK.")
        return 0

    all_errors: list[str] = []
    all_warnings: list[str] = []
    for path in files:
        errors, warnings = validate_file(path)
        all_errors.extend(errors)
        all_warnings.extend(warnings)

    print(f"Validated {len(files)} skill file(s).")
    if all_warnings:
        print(f"\nWarnings — {len(all_warnings)}:")
        for w in all_warnings:
            print(f"  - {w}")
    if all_errors:
        print(f"\nFAILED — {len(all_errors)} problem(s):")
        for e in all_errors:
            print(f"  - {e}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
