#!/usr/bin/env python3
"""Fail a spec that states a money figure with no source.

GLM-5.3 invents market sizes, prices, and growth rates. A money token on a
line with no URL and no ASSUMPTION, ESTIMATE, or UNVERIFIED label is a FAIL.
The file must also contain a BUILD verdict. Exit 0 when clean, 1 on FAIL,
2 on usage. Stdlib only. Read-only.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MONEY_RE = re.compile(
    r"(\$\s?\d|\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?\s*(?:k|m|b|thousand|million|billion)\b)",
    re.I,
)
SOURCE_RE = re.compile(r"(https?://|\bASSUMPTION\b|\bESTIMATE\b|\bUNVERIFIED\b)", re.I)
VERDICT_RE = re.compile(r"\b(DON'T BUILD|DO NOT BUILD|BUILD WITH CHANGES|BUILD)\b")
PLACEHOLDER_RE = re.compile(r"(\bTODO\b|\bTBD\b|\bFIXME\b|\?\?\?)")


def lint(text):
    fails = []
    if not VERDICT_RE.search(text):
        fails.append("FAIL verdict - no BUILD, BUILD WITH CHANGES, or DON'T BUILD line")
    for n, line in enumerate(text.splitlines(), 1):
        if PLACEHOLDER_RE.search(line):
            fails.append("FAIL placeholder - line %d still has a placeholder" % n)
        if MONEY_RE.search(line) and not SOURCE_RE.search(line):
            fails.append("FAIL money - line %d states a figure with no source or label: %s"
                         % (n, line.strip()[:70]))
    return fails


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        print("usage: check_spec.py SPEC.md", file=sys.stderr)
        return 2
    path = Path(argv[0])
    if not path.is_file():
        print("FAIL file - not found: %s" % path)
        print("RESULT spec fail=1")
        return 1
    fails = lint(path.read_text(encoding="utf-8", errors="replace"))
    for item in fails:
        print(item)
    print("RESULT spec fail=%d" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
