#!/usr/bin/env python3
"""hp_telemetry: group and review telemetry records for hybrid-writing-plans, and their stats."""
import datetime
import hashlib
import json
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_TELEMETRY = "~/.cache/hybrid-writing-plans/lanes.jsonl"
TOKEN_KEYS = ("input", "output", "reasoning", "cache_read", "cache_write")


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def telemetry_path() -> Path:
    """HYBRID_WRITING_PLANS_TELEMETRY when set, else ~/.cache/hybrid-writing-plans/lanes.jsonl."""
    return Path(os.environ.get("HYBRID_WRITING_PLANS_TELEMETRY") or DEFAULT_TELEMETRY).expanduser()


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


def file_sha(path: str) -> str:
    """sha256 hex digest of the file's bytes; "" when the file cannot be read."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return ""
    return hashlib.sha256(data).hexdigest()


def _norm(path) -> str:
    return os.path.normpath(str(path)) if path else ""


def _rate(num: int, den: int) -> str:
    if not den:
        return "-"
    return "{:.0f}% ({}/{})".format(100.0 * num / den, num, den)


def stats_lines(records: list, repo: str = "") -> list:
    """Per-tier summary lines of group and review records, optionally only for one repo."""
    want = _norm(repo)
    groups = {}
    reviews = {}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        if want and _norm(rec.get("repo")) != want:
            continue
        tier = str(rec.get("tier") or "-")
        if rec.get("kind") == "group":
            groups.setdefault(tier, []).append(rec)
        elif rec.get("kind") == "review":
            reviews.setdefault(tier, []).append(rec)
    suffix = " for repo {}".format(want) if want else ""
    if not groups and not reviews:
        return ["telemetry: no records" + suffix]
    lines = ["telemetry: {} groups, {} reviewed tasks{}".format(
        sum(len(v) for v in groups.values()), sum(len(v) for v in reviews.values()), suffix)]
    for tier in sorted(set(groups) | set(reviews)):
        recs = groups.get(tier, [])
        revs = reviews.get(tier, [])
        tasks = sum(len(r.get("tasks") or []) for r in recs)
        round1 = sum(int(r.get("round1_ok") or 0) for r in recs)
        rounds = [int(r.get("rounds") or 0) for r in recs]
        failed = [r for r in recs if r.get("outcome") != "ok"]
        reasons = {}
        for r in failed:
            key = str(r.get("reason") or "unknown")
            reasons[key] = reasons.get(key, 0) + 1
        fixed = sum(1 for r in revs if r.get("fixed_by_review") is True)
        durations = [float(r.get("duration_s") or 0.0) for r in recs]
        tokens = {k: 0 for k in TOKEN_KEYS}
        for r in recs:
            used = r.get("tokens")
            if not isinstance(used, dict):
                continue
            for k in TOKEN_KEYS:
                tokens[k] += int(used.get(k) or 0)
        mean_rounds = "{:.1f}".format(sum(rounds) / len(rounds)) if rounds else "-"
        reason_text = ",".join("{}:{}".format(k, v) for k, v in sorted(reasons.items())) or "-"
        median_s = "{:.1f}".format(statistics.median(durations)) if durations else "-"
        lines.append("tier={} groups={} tasks={} round1_pass={} mean_rounds={} fallback={} reasons={} "
                     "review_fix={} median_s={} tokens=in:{} out:{} reasoning:{}".format(
                         tier, len(recs), tasks, _rate(round1, tasks), mean_rounds,
                         _rate(len(failed), len(recs)), reason_text, _rate(fixed, len(revs)), median_s,
                         tokens["input"], tokens["output"], tokens["reasoning"]))
    return lines
