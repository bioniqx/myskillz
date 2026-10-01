#!/usr/bin/env python3
"""ha_telemetry: opencode run and checklist item records for hybrid-requirements-code-audit, and their stats."""
import datetime
import json
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_TELEMETRY = "~/.cache/hybrid-requirements-code-audit/lanes.jsonl"
TOKEN_KEYS = ("input", "output", "reasoning", "cache_read", "cache_write")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def telemetry_path() -> Path:
    """HYBRID_AUDIT_TELEMETRY when set, else ~/.cache/hybrid-requirements-code-audit/lanes.jsonl."""
    return Path(os.environ.get("HYBRID_AUDIT_TELEMETRY") or DEFAULT_TELEMETRY).expanduser()


def record(rec: dict) -> None:
    """Append one JSON line to telemetry_path(); add "t" when missing. Every failure is swallowed."""
    try:
        data = dict(rec)
        data.setdefault("t", _now_iso())
        line = json.dumps(data, sort_keys=True)
        path = telemetry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        return


def load_records(path: Path) -> list:
    """Every JSON object line of path; unreadable file -> [], bad or non-object lines are skipped."""
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _norm(path) -> str:
    return os.path.normpath(str(path)) if path else ""


def _rate(num: int, den: int) -> str:
    if not den:
        return "-"
    return "{:.0f}% ({}/{})".format(100.0 * num / den, num, den)


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _run_line(role: str, tier: str, recs: list) -> str:
    items = sum(_int(r.get("items")) for r in recs)
    round1 = sum(_int(r.get("round1_valid")) for r in recs)
    fallbacks = [r for r in recs if r.get("outcome") == "fallback"]
    reasons = {}
    for r in fallbacks:
        key = str(r.get("reason") or "unknown")
        reasons[key] = reasons.get(key, 0) + 1
    dropped = 0
    demoted = 0
    for r in recs:
        oracle = r.get("oracle")
        if isinstance(oracle, dict):
            dropped += _int(oracle.get("dropped"))
            demoted += _int(oracle.get("demoted"))
    per_item = [_float(r.get("duration_s")) / max(1, _int(r.get("items"))) for r in recs]
    tokens = {k: 0 for k in TOKEN_KEYS}
    for r in recs:
        used = r.get("tokens")
        if not isinstance(used, dict):
            continue
        for k in TOKEN_KEYS:
            tokens[k] += _int(used.get(k))
    reason_text = ",".join("{}:{}".format(k, v) for k, v in sorted(reasons.items())) or "-"
    median_s = "{:.1f}".format(statistics.median(per_item)) if per_item else "-"
    return ("run role={} backend=oc:{} runs={} items={} round1_valid={} fallback={} reasons={} "
            "oracle_dropped={} oracle_demoted={} median_s_per_item={} tokens=in:{} out:{} reasoning:{}".format(
                role, tier, len(recs), items, _rate(round1, items), _rate(len(fallbacks), len(recs)),
                reason_text, dropped, _rate(demoted, items), median_s,
                tokens["input"], tokens["output"], tokens["reasoning"]))


def _item_line(backend: str, recs: list) -> str:
    verified = [r for r in recs if r.get("ver") not in (None, "")]
    ver_over = sum(1 for r in verified if r.get("verifier_overturned") is True)
    lead_over = sum(1 for r in recs if r.get("lead_overturned") is True)
    return "items backend={} n={} verifier_overturn={} lead_overturn={}".format(
        backend, len(recs), _rate(ver_over, len(verified)), _rate(lead_over, len(recs)))


def stats_lines(records: list, repo: str = "") -> list:
    """Summary lines comparing opencode runs (per role and tier) and checklist items (per investigating backend)."""
    want = _norm(repo)
    runs = {}
    items = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if want and _norm(rec.get("repo")) != want:
            continue
        if rec.get("kind") == "run":
            key = (str(rec.get("role") or "-"), str(rec.get("tier") or "-"))
            runs.setdefault(key, []).append(rec)
        elif rec.get("kind") == "item":
            backend = str(rec.get("backend") or "claude")
            items.setdefault(backend, []).append(rec)
    suffix = " for repo {}".format(want) if want else ""
    if not runs and not items:
        return ["telemetry: no records" + suffix]
    lines = ["telemetry: {} runs, {} items{}".format(
        sum(len(v) for v in runs.values()), sum(len(v) for v in items.values()), suffix)]
    for role, tier in sorted(runs):
        lines.append(_run_line(role, tier, runs[(role, tier)]))
    for backend in sorted(items):
        lines.append(_item_line(backend, items[backend]))
    return lines
