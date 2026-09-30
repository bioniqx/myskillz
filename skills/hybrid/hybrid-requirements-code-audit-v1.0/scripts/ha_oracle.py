"""Evidence oracle: mechanical gate for rows written by opencode workers.

It removes bad citations and lowers confidence so a doubtful row reaches a Claude
verifier through the existing needs_verification rule. A row whose status is not
valid for its role is rejected (its id stays uncovered, so the runner asks for it
again in a repair turn); every rejection is a problem line for that repair turn.

is_doc_path and its patterns are copied verbatim from requirements-code-audit/hooks/audit_guard.py.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit  # noqa: E402

DOC_EXTS = r"md|mdx|markdown|rst|adoc|asciidoc|textile|org"
DOC_BASENAME_EXTS = DOC_EXTS + r"|txt"
DOC_BASENAME = re.compile(
    r"(^|/)(README|CHANGELOG|CHANGES|HISTORY|CONTRIBUTING|CODE_OF_CONDUCT|LICENSE|NOTICE)(\.(" + DOC_BASENAME_EXTS + r"))?$", re.I)
DOC_EXT = re.compile(r"\.(" + DOC_EXTS + r")$", re.I)
DOC_DIR = re.compile(r"(^|/)(docs?|documentation|wiki|adrs?|design[-_]docs?|rfcs?)(/|$)", re.I)
# .txt basenames that are build/dependency files, not prose, even inside a doc directory.
NON_DOC_TXT_BASENAMES = frozenset(("requirements.txt", "cmakelists.txt"))
VERIFIER_STATUSES = audit.STATUSES[:-1]  # a verdict must settle the item: UNSEARCHED is not a verdict


def is_doc_path(p):
    """True when p is prose documentation, not source code that merely resembles one."""
    pp = p.replace("\\", "/")
    if DOC_BASENAME.search(pp):
        return True
    if DOC_EXT.search(pp):
        return True
    if DOC_DIR.search(pp):
        name = pp.rsplit("/", 1)[-1]
        if "." not in name:
            return True
        if name.lower().endswith(".txt") and name.lower() not in NON_DOC_TXT_BASENAMES:
            return True
    return False


def _ev_path(ev: dict) -> str:
    return str(ev.get("path") or ev.get("file") or "")


def _audit_part(part: str) -> bool:
    low = part.lower()
    return low == audit.AUDIT_DIR or low.startswith(audit.AUDIT_DIR + ".prev-")


def check_citation(repo: Path, ev: dict, audit_dir: Path = None) -> str:
    """Return "" for a good citation, else the single reason it fails.

    audit_dir (the run's output folder) and any `.audit`/`.audit.prev-*` folder are audit output, not code.
    """
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
    parts = rel.parts + Path(raw).parts
    if any(part.lower() == ".git" for part in parts):  # .GIT on a case-insensitive file system too
        return ".git path"
    if any(_audit_part(part) for part in parts) or (audit_dir and audit.is_under(p, audit_dir)):
        return "audit output"
    if is_doc_path(rel.as_posix()):
        return "doc path"
    if p.is_dir():
        return "directory, not a file"
    problem = audit.check_evidence(repo, ev)
    if problem:
        return str(problem)
    mm = audit.LINES_RE.match(str(ev.get("lines") or ""))
    start, end = int(mm.group(1)), int(mm.group(2) or mm.group(1))
    if start < 1 or end < start:
        return "invalid line range %s" % ev.get("lines")
    return ""


def _valid_status(value, allowed=audit.STATUSES):
    """Return the normalized status, or None when it is not one of `allowed`.

    audit.norm_status maps unknown values to UNSEARCHED, so a real UNSEARCHED
    (or its alias SKIPPED) is told apart from an invalid value by the raw text.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    norm = audit.norm_status(value)
    raw = value.strip().upper().replace(" ", "_")
    if norm == "UNSEARCHED" and raw not in ("UNSEARCHED", "SKIPPED"):
        return None
    return norm if norm in allowed else None


def _confidence(value) -> str:
    """high/medium/low; anything else (a number, an unknown word, missing) is low."""
    text = value.strip().lower() if isinstance(value, str) else ""
    return text if text in audit.CONFIDENCES else "low"


def apply_oracle(rows: list, ids: list, repo: Path, role: str, audit_dir: Path = None) -> tuple:
    """Gate opencode rows. Returns (kept_rows, stats); input rows are not mutated.

    stats["problems"] lists what the worker must fix (checklist problems for a parser, rejected rows
    otherwise); a non-empty list means the output does not pass yet.
    """
    stats = {"foreign": 0, "dropped": 0, "demoted": 0, "invalid_status": 0, "problems": []}
    if role == "parser":
        stats["problems"] = list(audit.validate_checklist(rows) or [])
        return list(rows), stats
    wanted = set(str(i).strip() for i in ids)
    field = "verified_status" if role == "verifier" else "status"
    allowed = VERIFIER_STATUSES if role == "verifier" else audit.STATUSES
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
        status = _valid_status(value, allowed)
        if status is None:
            stats["invalid_status"] += 1
            stats["problems"].append("%s: %s must be one of %s, got %r" % (row["id"], field, "|".join(allowed), value))
            continue
        row[field] = status
        row["confidence"] = _confidence(row.get("confidence"))
        evidence = row.get("evidence") or []
        if not isinstance(evidence, list):
            evidence = [evidence]
        good, msgs = [], []
        for ev in evidence:
            reason = check_citation(repo, ev, audit_dir)
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
