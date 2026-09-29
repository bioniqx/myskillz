"""Evidence oracle: mechanical gate for rows written by opencode workers.

It never discards a row of the batch: it removes bad citations, resets invalid
statuses to UNSEARCHED and lowers confidence so a doubtful row reaches a Claude
verifier through the existing needs_verification rule.

DOC_PATH is copied verbatim from requirements-code-audit/hooks/audit_guard.py.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit  # noqa: E402

DOC_PATH = re.compile(
    r"(^|/)(README[^/]*|CHANGELOG[^/]*|CHANGES[^/]*|HISTORY[^/]*|CONTRIBUTING[^/]*|CODE_OF_CONDUCT[^/]*|LICENSE[^/]*|NOTICE[^/]*|"
    r"docs?|documentation|wiki|adrs?|design[-_]docs?|rfcs?)(/|$)|\.(md|mdx|markdown|rst|adoc|asciidoc|textile|org)$", re.I)


def _ev_path(ev: dict) -> str:
    return str(ev.get("path") or ev.get("file") or "")


def check_citation(repo: Path, ev: dict) -> str:
    """Return "" for a good citation, else the single reason it fails."""
    if not isinstance(ev, dict):
        ev = {}
    raw = _ev_path(ev)
    root = Path(repo).resolve()
    p = Path(raw)
    if not p.is_absolute():
        p = root / p
    try:
        rel = p.resolve().relative_to(root)
    except (ValueError, OSError, RuntimeError):
        return "outside repo"
    if ".git" in rel.parts or ".git" in Path(raw).parts:
        return ".git path"
    if DOC_PATH.search(rel.as_posix()):
        return "doc path"
    if p.is_dir():
        return "directory, not a file"
    problem = audit.check_evidence(repo, ev)
    if problem:
        return str(problem)
    mm = re.match(r"^\s*(\d+)\s*(?:-\s*(\d+))?\s*$", str(ev.get("lines") or ""))
    start, end = int(mm.group(1)), int(mm.group(2) or mm.group(1))
    if start < 1 or end < start:
        return "invalid line range %s" % ev.get("lines")
    return ""


def _valid_status(value):
    """Return the normalized status, or None when it is not a valid status.

    audit.norm_status maps unknown values to UNSEARCHED, so a real UNSEARCHED
    (or its alias SKIPPED) is told apart from an invalid value by the raw text.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    norm = audit.norm_status(value)
    raw = value.strip().upper().replace(" ", "_")
    if norm == "UNSEARCHED" and raw not in ("UNSEARCHED", "SKIPPED"):
        return None
    return norm


def apply_oracle(rows: list, ids: list, repo: Path, role: str) -> tuple:
    """Gate opencode rows. Returns (kept_rows, stats); input rows are not mutated."""
    stats = {"foreign": 0, "dropped": 0, "demoted": 0, "invalid_status": 0, "problems": []}
    if role == "parser":
        stats["problems"] = list(audit.validate_checklist(rows) or [])
        return list(rows), stats
    wanted = set(str(i).strip() for i in ids)
    field = "verified_status" if role == "verifier" else "status"
    note_key = "reason" if role == "verifier" else "notes"
    kept = []
    for src in rows:
        if not isinstance(src, dict) or str(src.get("id", "")).strip() not in wanted:
            stats["foreign"] += 1
            continue
        row = dict(src)
        row["id"] = str(src.get("id", "")).strip()
        value = row.get(field)
        if role == "verifier" and not value:
            value = row.get("status")
        status = _valid_status(value)
        if status is None:
            row[field] = "UNSEARCHED"
            stats["invalid_status"] += 1
        else:
            row[field] = status
        evidence = row.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = [evidence]
        good, msgs = [], []
        for ev in evidence:
            reason = check_citation(repo, ev)
            if reason:
                stats["dropped"] += 1
                path = _ev_path(ev) if isinstance(ev, dict) else str(ev)
                lines = ev.get("lines", "") if isinstance(ev, dict) else ""
                msgs.append("oracle: dropped %s:%s — %s" % (path, lines, reason))
            else:
                good.append(ev)
        if "evidence" in row or evidence:
            row["evidence"] = good
        if msgs:
            existing = str(row.get(note_key) or "")
            row[note_key] = "; ".join([m for m in [existing] + msgs if m])
        if msgs or (row[field] == "MATCHED" and not good):
            row["confidence"] = "low"
            stats["demoted"] += 1
        kept.append(row)
    return kept, stats
