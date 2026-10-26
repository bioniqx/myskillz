#!/usr/bin/env python3
"""Deterministic verifier for glm-brainstorming.

GLM invents path:line citations, URLs, dates and quotes, drops rules in a long
prompt, and reads soft agreement as approval. This script checks what a machine
can check, in one Bash call.

  check.py cites [--root DIR]          stdin: FINDINGS lines
  check.py web                         stdin: CLAIMS lines
  check.py spec PATH                   lint a written spec
  check.py route                       stdin: the user request. Always exit 0.
  check.py send [--root DIR] [--approved]
                                       stdin: the draft about to be shown
  check.py approve --asked design|other
                                       stdin: the human reply

Read-only, stdlib only. Exit 0 = nothing wrong, 1 = a BAD / DROP / FAIL / no, 2 = usage error.
"""
import argparse
import datetime
import re
import sys
import unicodedata
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
DASH = "(?:\u2014|--|-)"
HAND_OFFS = (
    "glm-idea-to-spec", "glm-systematic-debugging", "glm-requirements-code-audit",
    "glm-doc-generator", "glm-git-diff-summary", "glm-writing-plans", "glm-dev-team",
)
CODE_LANGS = {
    "python", "py", "javascript", "js", "typescript", "ts", "tsx", "jsx", "go",
    "rust", "rs", "java", "ruby", "rb", "php", "bash", "sh", "zsh", "sql",
    "csharp", "cs", "cpp", "c", "swift", "kotlin",
}
FENCE_MAX = 40
FEATURE_RE = re.compile(r"\b(add|build|implement|create|design)\b")
ROUTE_RULES = (
    ("glm-idea-to-spec", re.compile(
        r"\b(is (?:it|this)(?: \w+){0,4} viable|business model|make money|product idea|y tuong san pham)\b")),
    ("glm-systematic-debugging", re.compile(
        r"\b(traceback|stack ?trace|stacktrace|failing tests?|tests? fails?|flaky|regression|bugs?|bi loi)\b")),
    ("glm-requirements-code-audit", re.compile(
        r"\b(match the spec|match this spec|requirements traceability|gaps between spec|doi chieu spec)\b")),
    ("glm-doc-generator", re.compile(
        r"\b(write|update|draft) (the |a )?(readme|api reference|api docs|user guide|onboarding guide)\b")),
    ("glm-git-diff-summary", re.compile(
        r"\b(commit message|pr message|pull request message|what did this branch|"
        r"summarize (the |this )?branch|tom tat thay doi|so sanh voi main)\b")),
    ("glm-writing-plans", re.compile(
        r"\b(write the (implementation )?plan|approved design|design is approved|thiet ke da duyet|viet plan)\b")),
    ("glm-dev-team", re.compile(
        r"\b(implement the (approved )?plan|plan is approved|just implement)\b")),
)
SUPPRESS_IF_FEATURE = {"glm-doc-generator", "glm-git-diff-summary"}
APPROVE_START = re.compile(
    r"^(?:please |i |ok |okay |da |vang |anh )*"
    r"(approved|approve with my answers below|approve|yes|dong y|duyet|"
    r"lam di|trien khai di|trien khai|go ahead|ship it)\b")
REJECT_RE = re.compile(
    r"\b(revise|not yet|khong duyet|khong dong y|do not implement|don't implement|chua duyet)\b"
    r"|^wait\b|^stop\b|^khoan\b|^chua\b")
SOFT_RE = re.compile(
    r"^(sounds good|looks good|lgtm|ok|okay|on|on roi|duoc|tot|hay|nice|great|"
    r"sure|good|nghe duoc|ok luon|fine|on do|duoc do)[.! ]*$")


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

def fold_ascii(text):
    text = text.replace("\u0111", "d").replace("\u0110", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower()


def eval_cite(root, cache, path, lo, hi, ranged, snippet, sole):
    """Return (status, message). status is ok, bad, unchecked, or skip."""
    ref = f"{path}:{lo}" + (f"-{hi}" if ranged else "")
    target = (root / path).resolve()
    if path.rsplit(".", 1)[-1].lower() in TLD_LIKE and not target.exists():
        return "skip", None
    try:
        inside = target.is_relative_to(root)
    except ValueError:
        inside = False
    if not inside:
        return "bad", f"BAD {ref} - path leaves the repository root"
    if not target.is_file():
        return "bad", f"BAD {ref} - file not found"
    if target not in cache:
        try:
            cache[target] = target.read_text(errors="replace").splitlines()
        except OSError as e:
            cache[target] = None
            return "bad", f"BAD {ref} - unreadable ({e.__class__.__name__})"
    lines = cache[target]
    if lines is None:
        return "bad", None
    if lo < 1 or hi < lo or hi > len(lines):
        return "bad", f"BAD {ref} - line out of range (file has {len(lines)} lines)"
    if not sole or not snippet:
        return "unchecked", (f"NOQUOTE {ref} - exists, but no single quoted snippet to verify; "
                             "label it unverified")
    want = norm(snippet.rstrip(".").rstrip("\u2026")).strip()
    window = norm(" ".join(lines[max(0, lo - 4):hi + 3]))
    if want and want in window:
        return "ok", f"OK {ref}"
    elsewhere = next((i + 1 for i, ln in enumerate(lines) if want and want in norm(ln)), None)
    extra = f" (it appears at line {elsewhere}: use that line)" if elsewhere else " (not found in the file)"
    return "bad", f"BAD {ref} - snippet not within 3 lines of it" + extra


def walk_cites(text, root):
    """Yield (line, status, message) for each citation. status skip is omitted."""
    cache = {}
    seen = set()
    for raw in text.splitlines():
        cites = [m for m in CITE_RE.finditer(raw)]
        snippet = last_quote(raw)
        sole = len(cites) == 1
        for m in cites:
            path, lo = m.group(1), int(m.group(2))
            hi = int(m.group(3)) if m.group(3) else lo
            key = (path, lo, hi, snippet if sole else "")
            if key in seen:
                continue
            seen.add(key)
            status, msg = eval_cite(root, cache, path, lo, hi, bool(m.group(3)), snippet, sole)
            if status == "skip":
                continue
            yield raw, status, msg


def check_cites(a):
    root = Path(a.root).resolve()
    ok = bad = unchecked = 0
    for _raw, status, msg in walk_cites(sys.stdin.read(), root):
        if msg:
            print(msg)
        if status == "ok":
            ok += 1
        elif status == "unchecked":
            unchecked += 1
        elif status == "bad":
            bad += 1
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


# ----------------------------------------------------------------------------- route, send, approve

def visible_lines(text):
    """Lines outside fenced blocks, plus (lang, non-empty-count) for each fence."""
    visible, fences = [], []
    fence = False
    lang, buf = "", []
    for ln in text.splitlines():
        stripped = ln.strip()
        if stripped.startswith("```"):
            if not fence:
                fence = True
                lang = stripped[3:].strip().split()[0].lower() if stripped[3:].strip() else ""
                buf = []
            else:
                fence = False
                fences.append((lang, sum(1 for x in buf if x.strip())))
            continue
        if fence:
            buf.append(ln)
        else:
            visible.append(ln)
    if fence:
        fences.append((lang, sum(1 for x in buf if x.strip())))
    return visible, fences


def line_kind(first):
    """(kind, path_or_skill). kind is path, unchanged, handoff, or bad."""
    m = re.match(r"Path: (Spike|Bounded|Architectural) " + DASH + r" \S", first)
    if m:
        return "path", m.group(1)
    m = re.match(r"Path unchanged: (Spike|Bounded|Architectural)\b", first)
    if m:
        return "unchanged", m.group(1)
    m = re.match(r"Not a design task " + DASH + r" handing to (glm-[a-z0-9-]+) because \S", first)
    if m:
        return "handoff", m.group(1)
    return "bad", ""


def url_problem(line, today):
    if not URL_RE.search(line):
        return None
    low = line.lower()
    if "unverified" in low or "repo-internal" in low:
        return None
    urls = URL_RE.findall(line)
    if not urls[0].lower().startswith("https://"):
        return "evidence URL is not https; use https or label the line unverified"
    dm = DATE_RE.search(line)
    if not dm:
        return "evidence URL has no YYYY-MM-DD date and is not labelled unverified"
    try:
        when = datetime.date(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
    except ValueError:
        return f"{dm.group(0)} is not a real date"
    if when > today:
        return f"date {when} is in the future"
    return None


def check_route(a):
    text = fold_ascii(sys.stdin.read())
    feature = FEATURE_RE.search(text)
    strong_debug = re.compile(
        r"\b(traceback|stack ?trace|stacktrace|failing tests?|tests? fails?|flaky|regression|bi loi)\b")
    bug_denied = re.search(r"\bno\b.{0,24}\bbugs?\b", text) and not strong_debug.search(text)
    hits = []
    for name, rx in ROUTE_RULES:
        if name in SUPPRESS_IF_FEATURE and feature:
            continue
        if name == "glm-systematic-debugging" and bug_denied:
            continue
        if rx.search(text):
            hits.append(name)
    if not hits:
        print("ROUTE none")
        print("RESULT route name=none")
        return 0
    print(f"ROUTE {hits[0]}")
    for extra in hits[1:]:
        print(f"ALSO {extra}")
    print(f"RESULT route name={hits[0]}")
    return 0


def check_send(a):
    text = sys.stdin.read()
    fails = []
    if not text.strip():
        fails.append("FAIL draft - empty; write the message first")
    else:
        first = text.splitlines()[0].strip()
        kind, value = line_kind(first)
        if kind == "bad":
            fails.append(
                "FAIL path - line 1 must be 'Path: Spike|Bounded|Architectural - reason', "
                "'Path unchanged: <path>', or 'Not a design task - handing to glm-<skill> because <reason>'")
            value = ""
        elif kind == "handoff" and value not in HAND_OFFS:
            fails.append(f"FAIL path - unknown hand-off target {value}")
        visible, fences = visible_lines(text)
        body = "\n".join(visible)
        questions = URL_RE.sub(" ", re.sub(r"(?i)approve this design\?", " ", body)).count("?")
        if questions > 4:
            fails.append(f"FAIL questions - {questions} question marks (max 4); merge the rest into assumptions")
        design = re.search(r"(?i)approve this design\?", body) is not None
        if design:
            low = body.lower()
            if not re.search(r"out of scope|out-of-scope|non-goal", low):
                fails.append("FAIL scope - a design message needs an Out of scope line")
            if not re.search(r"assum(e|ing|ption)", low):
                fails.append("FAIL assumptions - a design message needs an assumption line")
            if value == "Architectural":
                n = len(re.findall(r"(?m)^APPROACH\s+[1-3]\s*:", text))
                if n < 2:
                    fails.append(
                        f"FAIL approaches - {n} APPROACH line(s); Architectural needs 2 or 3, "
                        "each 'APPROACH 1: ...' on its own line")
            scrub = re.sub(r"not (?:a |an )?new (?:project|subsystem)\b", " ", low)
            if value == "Bounded" and re.search(r"new (project|subsystem)\b", scrub):
                fails.append("FAIL class - Bounded draft says 'new project' or 'new subsystem'; "
                             "upgrade the path to Architectural")
        root = Path(a.root).resolve()
        for raw, status, msg in walk_cites("\n".join(visible), root):
            if "unverified" in raw.lower():
                continue
            if status == "ok":
                continue
            if status == "unchecked":
                fails.append(f"FAIL cite {msg.split(' - ', 1)[0].replace('NOQUOTE ', '')} "
                             "- no quote; re-read it or label the line unverified")
            elif status == "bad" and msg:
                fails.append("FAIL cite " + msg[4:])
            elif status == "bad":
                fails.append("FAIL cite - unreadable file")
        today = today_of(a)
        for ln in visible:
            why = url_problem(ln, today)
            if why:
                fails.append(f"FAIL evidence - {why}: {ln.strip()[:70]}")
        if not a.approved:
            for lang, count in fences:
                if lang in CODE_LANGS and count > FENCE_MAX:
                    fails.append(
                        f"FAIL fence - {count}-line {lang} block is implementation; "
                        "remove it until approve prints yes")
    for item in fails:
        print(item)
    print(f"RESULT send fail={len(fails)}")
    return 1 if fails else 0


def check_approve(a):
    if a.asked != "design":
        print("RESULT approve no - a reply to a side question is not approval")
        return 1
    folded = fold_ascii(sys.stdin.read()).strip()
    if not folded:
        print("RESULT approve no - empty reply")
        return 1
    if REJECT_RE.search(folded):
        print("RESULT approve no - the reply asks for a revision")
        return 1
    if SOFT_RE.fullmatch(folded):
        print("RESULT approve no - soft agreement is not approval")
        return 1
    if re.fullmatch(r"1[.)]?", folded) or APPROVE_START.match(folded):
        print("RESULT approve yes")
        return 0
    print("RESULT approve no - no approval token at the start of the reply")
    return 1


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
    pr = sp.add_parser("route")
    pr.set_defaults(fn=check_route)
    pe = sp.add_parser("send")
    pe.add_argument("--root", default=".")
    pe.add_argument("--approved", action="store_true")
    pe.set_defaults(fn=check_send)
    pa = sp.add_parser("approve")
    pa.add_argument("--asked", required=True, choices=("design", "other"))
    pa.set_defaults(fn=check_approve)
    for q in (pc, pw, ps, pr, pe, pa):
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
