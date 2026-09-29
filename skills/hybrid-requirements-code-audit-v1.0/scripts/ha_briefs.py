"""opencode brief head, marker block extraction and repair turn message."""
import re
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parent))

MARK_BEGIN = "@@@ BEGIN "
MARK_END = "@@@ END "


def oc_head(name: str) -> str:
    return (
        "Output the JSONL for this batch between a line `%s%s` and a line `%s%s`, nothing else. "
        "You cannot write files; the runner writes them. "
        "Wherever the brief below says to write an output file or reply with one line, "
        "put those JSON lines in the marker block instead." % (MARK_BEGIN, name, MARK_END, name)
    )


def split_block(text: str, name: str) -> str:
    begin = (MARK_BEGIN + name).strip()
    end = (MARK_END + name).strip()
    lines = (text or "").splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == begin:
            start = i + 1
            break
    if start is None:
        return ""
    out: List[str] = []
    for line in lines[start:]:
        if line.strip() == end:
            break
        out.append(line)
    return "\n".join(out)


_DROP_RE = re.compile(
    r"^\s*(?:[-*]\s+|\d+[.)]\s+)?(?:\*\*)?(?:Write\s+(?:[\w-]+\s+){0,3}to\b|Final reply\b)"
)

REPAIR_ERROR_LINES = 25


def to_oc_brief(body: str, name: str) -> str:
    # Drop lines only in the head (before the first blank line): later text, such as a parser's
    # verbatim spec section, may legitimately contain "Write ... to" or "Final reply" lines.
    lines = body.splitlines()
    head_end = next((i for i, line in enumerate(lines) if not line.strip()), len(lines))
    kept = [line for line in lines[:head_end] if not _DROP_RE.match(line)] + lines[head_end:]
    return oc_head(name) + "\n\n" + "\n".join(kept).strip("\n") + "\n"


def repair_message(name: str, missing: list, errors: list) -> str:
    parts: List[str] = []
    if missing:
        parts.append("Missing ids: %s." % ", ".join(str(i) for i in missing))
    if errors:
        lines: List[str] = []
        for err in errors:
            lines.extend(str(err).splitlines() or [""])
        lines = lines[:REPAIR_ERROR_LINES]
        parts.append("The previous block had parse errors:\n" + "\n".join(lines))
    if missing:
        ask = "Output the JSONL rows of only those ids"
    else:
        ask = "Output the corrected JSONL rows, one valid JSON object per line,"
    parts.append(
        "%s between a line `%s%s` and a line `%s%s`, nothing else. "
        "You cannot write files; the runner writes them." % (ask, MARK_BEGIN, name, MARK_END, name)
    )
    return "\n\n".join(parts) + "\n"
