#!/usr/bin/env python3
"""Deterministic verifier for glm-brainstorming: lane output and specs.

GLM (Flash above all) invents plausible path:line citations, URLs, dates and quotes. This script
checks what a machine can check, in one Bash call, so the main thread cites only what survived.

  check.py cites [--root DIR]   stdin: explorer FINDINGS lines `path:line - fact - "snippet"`
  check.py web                  stdin: researcher CLAIMS lines `claim - tier - URL - date - "quote"`
  check.py spec PATH            lint a written spec (headings, placeholders, evidence format)

Read-only, stdlib only. Exit 0 = nothing wrong, 1 = at least one BAD / DROP / FAIL, 2 = usage error.
"""
import argparse
import datetime
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

STALE_DAYS = 548            # 18 months
MAX_QUOTE_WORDS = 25
MAX_SECTION_WORDS = 450
TLD_LIKE = {"com", "org", "net", "io", "dev", "ai", "app", "co", "me", "so", "sh"}
CITE_RE = re.compile(r"(?<![\w/:.])((?:[\w.@+-]+/)*[\w.@+-]+\.[A-Za-z0-9]+):(\d+)(?:-(\d+))?(?![\w/])")
QUOTE_RE = re.compile(r'"([^"\n]+)"|“([^”\n]+)”')
URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
TIER_RE = re.compile(r"(?:^|[\s|—-])(?:Tier\s*)?([ABC])(?=\s*(?:[|—]|--|-\s|$))")
BAD_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "bing.com", "www.bing.com", "duckduckgo.com",
             "html.duckduckgo.com", "twitter.com", "x.com", "facebook.com", "linkedin.com"}
PLACEHOLDER_RE = re.compile(
    r"(\bTODO\b|\bTBD\b|\bFIXME\b|\?\?\?|\bto be decided\b|\bfigure out later\b|\blorem ipsum\b|"
    r"<[A-Z][A-Z _-]{2,}>|\[(?:PLACEHOLDER|INSERT|TBD)[^\]]*\])", re.I)
REQUIRED = [("Architecture", r"architecture"), ("Components", r"components?"), ("Data flow", r"data[ -]?flow"),
            ("Error handling", r"error[ -]?handling|failure modes?"), ("Testing", r"testing|test plan|verification"),
            ("Evidence", r"evidence|sources?"), ("Assumptions", r"assumptions?"),
            ("Out of scope", r"out[ -]of[ -]scope|non-goals?")]
HEADING_RE = re.compile(r"^(#{1,4})\s*(?:\d+[.)]?\s*)?(.+?)\s*#*\s*$")
LABELS = ("ANSWER:", "CONFLICTS:", "VERSION_NOTES:", "UNVERIFIED:", "FINDINGS:", "PATTERNS:", "RISKS:", "UNKNOWN:")


def today_of(a):
    if getattr(a, "today", None):
        return datetime.date.fromisoformat(a.today)
    return datetime.date.today()


def norm(text):
    return " ".join(text.split())


def last_quote(line):
    found = [m.group(1) or m.group(2) for m in QUOTE_RE.finditer(line)]
    return found[-1].strip() if found else ""


# ----------------------------------------------------------------------------- cites

def check_cites(a):
    root = Path(a.root).resolve()
    cache = {}
    ok = bad = unchecked = 0
    seen = set()
    for raw in sys.stdin.read().splitlines():
        cites = [m for m in CITE_RE.finditer(raw)]
        snippet = last_quote(raw)
        for m in cites:
            path, lo = m.group(1), int(m.group(2))
            hi = int(m.group(3)) if m.group(3) else lo
            key = (path, lo, hi, snippet if len(cites) == 1 else "")
            if key in seen:
                continue
            seen.add(key)
            ref = f"{path}:{lo}" + (f"-{hi}" if m.group(3) else "")
            target = (root / path).resolve()
            if path.rsplit(".", 1)[-1].lower() in TLD_LIKE and not target.exists():
                continue                       # `example.com:443` is a host, not a citation
            try:
                inside = target.is_relative_to(root)
            except ValueError:
                inside = False
            if not inside:
                bad += 1
                print(f"BAD {ref} - path leaves the repository root")
                continue
            if not target.is_file():
                bad += 1
                print(f"BAD {ref} - file not found")
                continue
            if target not in cache:
                try:
                    cache[target] = target.read_text(errors="replace").splitlines()
                except OSError as e:
                    cache[target] = None
                    print(f"BAD {ref} - unreadable ({e.__class__.__name__})")
            lines = cache[target]
            if lines is None:
                bad += 1
                continue
            if lo < 1 or hi < lo or hi > len(lines):
                bad += 1
                print(f"BAD {ref} - line out of range (file has {len(lines)} lines)")
                continue
            if len(cites) != 1 or not snippet:
                unchecked += 1
                print(f"NOQUOTE {ref} - exists, but no single quoted snippet to verify; label it unverified")
                continue
            want = norm(snippet.rstrip(".").rstrip("…")).strip()
            window = norm(" ".join(lines[max(0, lo - 4):hi + 3]))
            if want and want in window:
                ok += 1
                print(f"OK {ref}")
                continue
            elsewhere = next((i + 1 for i, ln in enumerate(lines) if want and want in norm(ln)), None)
            bad += 1
            print(f"BAD {ref} - snippet not within 3 lines of it"
                  + (f" (it appears at line {elsewhere}: use that line)" if elsewhere else " (not found in the file)"))
    print(f"RESULT cites ok={ok} bad={bad} unchecked={unchecked}")
    return 1 if bad else 0


# ----------------------------------------------------------------------------- web

def judge_claim(line, today):
    """(verdict, reason) for one CLAIMS line."""
    urls = URL_RE.findall(line)
    if not urls:
        return "DROP", "no URL"
    url = urls[0].rstrip(".,;")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return "DROP", "URL is not https"
    if host in BAD_HOSTS or "." not in host:
        return "DROP", f"{host or 'URL'} is not a citable source"
    if host.endswith("google.com") and parsed.path.startswith("/search"):
        return "DROP", "a search results page is not a source"
    rest = line.replace(url, " ")
    tm = TIER_RE.search(rest)
    if not tm:
        return "DROP", "no tier (A, B or C)"
    tier = tm.group(1)
    dm = DATE_RE.search(rest)
    if not dm:
        return "DROP", "no date (YYYY-MM-DD)"
    try:
        when = datetime.date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
    except ValueError:
        return "DROP", f"{dm.group(0)} is not a real date"
    if when > today:
        return "DROP", f"date {when} is in the future"
    quote = last_quote(line)
    if not quote:
        return "DROP", "no verbatim quote"
    words = len(quote.split())
    if words > MAX_QUOTE_WORDS:
        return "DROP", f"quote is {words} words (max {MAX_QUOTE_WORDS})"
    age = (today - when).days
    if tier == "C":
        return "WEAK", "tier C is signal only and cannot carry a recommendation"
    if age > STALE_DAYS:
        return "WEAK", f"{age // 30} months old: re-verify on fast-moving tech"
    return "OK", ""


def check_web(a):
    today = today_of(a)
    counts = {"OK": 0, "WEAK": 0, "DROP": 0}
    for raw in sys.stdin.read().splitlines():
        line = raw.strip().lstrip("-*0123456789.) ").strip()
        if line.upper().startswith("CLAIMS:"):
            line = line[7:].strip()
        if not line or line.upper().startswith(LABELS):
            continue
        looks_like_claim = URL_RE.search(line) or re.search(r"[—|]\s*(?:Tier\s*)?[ABC]\s*[—|]", line)
        if not looks_like_claim:
            continue
        verdict, why = judge_claim(line, today)
        counts[verdict] += 1
        head = line.split(" — ")[0].split(" | ")[0][:70]
        print(f"{verdict} {head}" + (f" - {why}" if why else ""))
    print(f"RESULT web ok={counts['OK']} weak={counts['WEAK']} drop={counts['DROP']}")
    return 1 if counts["DROP"] else 0


# ----------------------------------------------------------------------------- spec

def split_sections(text):
    """[(title, body_lines)] in order; text before the first heading is dropped."""
    out, cur = [], None
    fence = False
    for ln in text.splitlines():
        if ln.lstrip().startswith("```"):
            fence = not fence
        m = None if fence else HEADING_RE.match(ln)
        if m:
            cur = (m.group(2).strip(), [])
            out.append(cur)
        elif cur is not None:
            cur[1].append(ln)
    return out


def check_spec(a):
    path = Path(a.path)
    try:
        text = path.read_text(errors="replace")
    except OSError as e:
        print(f"check.py: cannot read {a.path}: {e}", file=sys.stderr)
        return 2
    today = today_of(a)
    fails, warns = [], []
    sections = split_sections(text)
    for name, pat in REQUIRED:
        hit = next(((t, b) for t, b in sections if re.fullmatch(r"(?:" + pat + r")(?:\b.*)?", t, re.I)), None)
        if hit is None:
            fails.append((name, "required section is missing"))
            continue
        body = "\n".join(hit[1]).strip()
        if len(re.sub(r"\s", "", body)) < 6:
            fails.append((name, "section is empty"))
        if len(body.split()) > MAX_SECTION_WORDS:
            warns.append((name, f"{len(body.split())} words: split it or cut it"))
        if name == "Evidence":
            lines = [x for x in body.splitlines() if x.strip().lstrip("-*0123456789.) ")]
            if not re.search(r"\b(none|n/a|repo-internal)\b", body, re.I):
                if not 2 <= len(lines) <= 7:
                    warns.append((name, f"{len(lines)} evidence lines (expected 2-7)"))
                for ln in lines:
                    urls = URL_RE.findall(ln)
                    dm = DATE_RE.search(ln)
                    if not urls or not urls[0].lower().startswith("https://"):
                        fails.append((name, f"line has no https URL: {ln.strip()[:60]}"))
                    elif not dm:
                        fails.append((name, f"line has no (YYYY-MM-DD) date: {ln.strip()[:60]}"))
                    else:
                        try:
                            when = datetime.date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
                            if when > today:
                                fails.append((name, f"date {when} is in the future: {ln.strip()[:50]}"))
                        except ValueError:
                            fails.append((name, f"{dm.group(0)} is not a real date"))
    in_fence = False
    for n, ln in enumerate(text.splitlines(), 1):
        if ln.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        m = None if in_fence else PLACEHOLDER_RE.search(ln)
        if m:
            fails.append(("placeholder", f"line {n}: `{m.group(0)}` - finish it or move it to Assumptions"))
    for sec, why in fails:
        print(f"FAIL {sec} - {why}")
    for sec, why in warns:
        print(f"WARN {sec} - {why}")
    print(f"RESULT spec fail={len(fails)} warn={len(warns)}")
    return 1 if fails else 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="check.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="mode", required=True)
    pc = sp.add_parser("cites")
    pc.add_argument("--root", default=".")
    pc.set_defaults(fn=check_cites)
    pw = sp.add_parser("web")
    pw.set_defaults(fn=check_web)
    ps = sp.add_parser("spec")
    ps.add_argument("path")
    ps.set_defaults(fn=check_spec)
    for q in (pc, pw, ps):
        q.add_argument("--today", help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    try:
        rc = a.fn(a)
        sys.stdout.flush()
        return rc
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
