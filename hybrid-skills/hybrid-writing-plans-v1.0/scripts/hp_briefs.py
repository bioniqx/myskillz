#!/usr/bin/env python3
"""hp_briefs.py - opencode writer brief head, body markers and repair message (stdlib only)."""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_tool  # noqa: E402

MARK_BEGIN = "@@@ BEGIN "
MARK_END = "@@@ END "
MAX_ERR_LINES = 25
HEAD_FILE = "oc-writer-prompt.md"
RULE_TITLES = ("Body format", "Rules")
PLAN_HEADER = "\n\n## Plan header\n\n"
WRAP_FENCE = re.compile(r"^(`{3,}|~{3,})\s*(markdown|md)?\s*$")


def rules_text() -> str:
    """The "Body format" and "Rules" sections of task-writer-prompt.md, verbatim."""
    text = plan_tool.load(os.path.join(plan_tool.SKILL_DIR, "task-writer-prompt.md"))
    out, on = [], False
    for line in text.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            on = m.group(1).startswith(RULE_TITLES)
        if on:
            out.append(line)
    return "\n".join(out).strip() + "\n"


def marker_pairs(task_ids: list) -> str:
    """One BEGIN/END pair per task, showing the exact reply format."""
    return "\n".join("%s%s\n<full body of %s>\n%s%s" % (MARK_BEGIN, t, t, MARK_END, t) for t in task_ids)


def oc_head(task_ids: list) -> str:
    """oc-writer-prompt.md with {TASKS}, {MARKERS} and {RULES} filled (no trailing newline)."""
    tmpl = plan_tool.load(os.path.join(plan_tool.SKILL_DIR, HEAD_FILE))
    head = tmpl.replace("{TASKS}", ", ".join(task_ids)).replace("{MARKERS}", marker_pairs(task_ids))
    return head.replace("{RULES}", rules_text().rstrip("\n")).rstrip("\n")


def oc_brief(plan_path: str, plan: str, cs_group: list, cmap: dict, work: str, spec_path: str, repo: str, allow: list) -> str:
    """The Claude writer brief with its head (OUT/LINT/procedure) swapped for the oc head."""
    full = plan_tool.writer_brief(plan_path, plan, cs_group, cmap, work, spec_path, repo, allow)
    i = full.find(PLAN_HEADER)
    rest = full[i + 2:] if i >= 0 else full
    return oc_head([c["id"] for c in cs_group]) + "\n\n" + rest


def unwrap(body_lines: list) -> str:
    """Trim blank edge lines and drop one markdown fence wrapped around the whole body."""
    lines = list(body_lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if len(lines) >= 2:
        m = WRAP_FENCE.match(lines[0].strip())
        if m and lines[-1].strip() == m.group(1):
            lines = lines[1:-1]
    return "\n".join(lines).strip("\n")


def split_bodies(text: str, task_ids: list) -> dict:
    """{Txx: body} for every task of task_ids with a complete, non-empty BEGIN/END pair.

    Text outside markers and foreign IDs are ignored; a BEGIN without its END (or
    interrupted by another BEGIN) is dropped; the last complete copy of an ID wins.
    """
    wanted = set(task_ids)
    found = {}
    cur, buf = None, []
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith(MARK_BEGIN):
            cur, buf = s[len(MARK_BEGIN):].strip(), []
            continue
        if s.startswith(MARK_END):
            if cur is not None and s[len(MARK_END):].strip() == cur:
                body = unwrap(buf)
                if cur in wanted and body.strip():
                    found[cur] = body + "\n"
                cur, buf = None, []
            continue
        if cur is not None:
            buf.append(line)
    return {t: found[t] for t in task_ids if t in found}


def repair_message(errors: dict, missing: list) -> str:
    """Message for a repair turn: per failing task its ERR lines (max 25) or 'missing'; '' if none."""
    miss = list(dict.fromkeys(missing or []))
    bad = {t: list(e) for t, e in (errors or {}).items() if e and t not in miss}
    ids = sorted(set(miss) | set(bad), key=plan_tool.num)
    if not ids:
        return ""
    parts = ["Lint rejected part of your last reply. Reply with the corrected full bodies of only these tasks: %s." % ", ".join(ids),
             "Use the same format: each body between a line `%sTxx` and a line `%sTxx`, one pair per task, nothing else. "
             "Do not write files or run commands." % (MARK_BEGIN, MARK_END)]
    for t in ids:
        if t in miss:
            parts.append("%s: missing from your reply" % t)
            continue
        errs = bad[t]
        rows = ["%s: %d lint error(s) - fix every one:" % (t, len(errs))]
        rows += ["ERR  " + e for e in errs[:MAX_ERR_LINES]]
        if len(errs) > MAX_ERR_LINES:
            rows.append("(+%d more errors not shown)" % (len(errs) - MAX_ERR_LINES))
        parts.append("\n".join(rows))
    parts.append("Output now, for each task above, its full corrected body:\n\n" + marker_pairs(ids))
    return "\n\n".join(parts) + "\n"
