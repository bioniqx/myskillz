"""Grounding gate for hybrid-brainstorming lanes.

Code lanes: each FINDINGS line `path:line[-line][:col] — fact` (the `—`/`-` separator is
optional; a plain space works too) is checked against the repo. The sentinel line
`HB-LANE-OK` is dropped from every section and never counts as a finding or claim.
Web lanes: each CLAIMS line `claim — tier — URL — date — "quote"` is checked against the
fetched pages (webfetch, or read/grep of a saved fetch) of the lane's own opencode session; search results are not evidence.
Stdlib only, Python 3.8.
"""
import re
from pathlib import Path

SECTIONS = ("FINDINGS", "PATTERNS", "RISKS", "UNKNOWN", "ANSWER", "CLAIMS", "CONFLICTS", "VERSION_NOTES", "UNVERIFIED")

CODE_PASSTHROUGH = ("PATTERNS", "RISKS", "UNKNOWN")
WEB_PASSTHROUGH = ("CONFLICTS", "VERSION_NOTES")
WEB_TOOLS = ("webfetch", "websearch", "read", "grep")
IDENT_WINDOW = 5
MIN_QUOTE_WORDS = 3
_STOP = frozenset(
    "the and for with that this from into are was were has have had its not but can will would should could "
    "been being than then them they their there here when where which what who how why also only any all each "
    "some such via per use uses used using set get gets one two out".split())

_HEADER_RE = re.compile(r"^[\s#>*_]*(" + "|".join(SECTIONS) + r")[*_]*\s*:[*_]*\s*(.*)$")
_BULLET_RE = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
_EMPTY = {"none", "(none)", "n/a", "-", "—"}
_SENTINEL = "HB-LANE-OK"


def normalize(text: str) -> str:
    """Case-fold and collapse every whitespace run to one space."""
    return " ".join(str(text or "").split()).casefold()


def _clean(line):
    s = line.strip()
    s = _BULLET_RE.sub("", s, count=1).strip()
    norm = normalize(s)
    if norm in _EMPTY or norm == normalize(_SENTINEL):
        return ""
    return s


def parse_sections(text: str) -> dict:
    """Split lane output into {SECTION: [item, ...]}.

    Only sections whose header appears are keys. A header is an upper-case section name
    followed by a colon, optionally wrapped in markdown (`**FINDINGS:**`, `### RISKS:`).
    Text after the colon is the first item. Items are non-empty lines with one leading
    bullet removed; placeholder items such as `none` are dropped. Lines before the first
    header are ignored.
    """
    out = {}
    current = None
    bulleted = False  # the last item started with a bullet, so an unbulleted line continues it
    for raw in str(text or "").splitlines():
        m = _HEADER_RE.match(raw)
        if m:
            current = m.group(1)
            out.setdefault(current, [])
            bulleted = False
            rest = _clean(m.group(2))
            if rest:
                out[current].append(rest)
            continue
        if current is None:
            continue
        item = _clean(raw)
        if not item:
            bulleted = bulleted and bool(raw.strip())  # a blank line ends the item; a dropped placeholder does not
            continue
        if bulleted and out[current] and not _BULLET_RE.match(raw.strip()):
            out[current][-1] += " " + item
            continue
        bulleted = bool(_BULLET_RE.match(raw.strip()))
        out[current].append(item)
    return out


def _render(blocks):
    out = []
    for title, items in blocks:
        if items:
            out.append(title + ":")
            out.extend("- " + item for item in items)
    return "\n".join(out)


_FINDING_RE = re.compile(
    r"^`?(?P<path>[^\s`:]+)`?:(?P<lines>\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*)(?::\d+)?`?"
    r"(?:\s*(?:—|–|--|-|:)\s*|\s+)(?P<fact>.+)$"
)
_IDENT_RE = re.compile(r"`([^`]+)`")


def _boundary_hit(name, window):
    """True when `name` appears in `window` as a whole identifier (word-boundary match)."""
    return re.search(r"(?<!\w)" + re.escape(name) + r"(?!\w)", window) is not None


def _subwords(text):
    """Case-folded identifiers of text plus their snake_case and camelCase parts."""
    out = set()
    for word in re.findall(r"[A-Za-z0-9_]+", text):
        out.add(word.casefold())
        out.update(p.casefold() for p in re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", word))
    return out


def _within(root, target):
    try:
        target.relative_to(root)
        return True
    except ValueError:
        return False


def _check_finding(item, root):
    """Return "" when the finding is grounded, else the failure reason."""
    m = _FINDING_RE.match(item)
    if not m:
        return "not path:line — fact"
    p = Path(m.group("path"))
    target = p if p.is_absolute() else root / p
    try:
        target = target.resolve()
    except (OSError, RuntimeError):
        return "outside repo root"
    if not _within(root, target):
        return "outside repo root"
    if not target.is_file():
        return "missing file"
    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "missing file"
    windows = []
    start = None
    for part in m.group("lines").split(","):
        lo_s, _, hi_s = part.partition("-")
        n = int(lo_s)
        k = int(hi_s) if hi_s else n
        if k < n or n < 1 or n > len(lines):
            return "line out of range"
        k = min(k, len(lines))  # a range that runs past EOF is clamped, not rejected
        if start is None:
            start = n
        lo = max(0, n - 1 - IDENT_WINDOW)
        hi = min(len(lines), k + IDENT_WINDOW)
        windows.append("\n".join(lines[lo:hi]))
    idents = [i for i in _IDENT_RE.findall(m.group("fact")) if i.strip()]
    if not idents:  # no backticked identifier: some word of the claim must be near the cited line
        words = _subwords("\n".join(windows))
        keys = [w for w in (t.casefold() for t in re.findall(r"[A-Za-z0-9_]+", m.group("fact")))
                if len(w) >= 3 and w not in _STOP]
        if not any(w in words or (w.endswith("s") and w[:-1] in words) for w in keys):
            return "no word of the claim near line %d" % start
    for ident in idents:
        ident = ident.strip()
        if not ident:
            continue
        check = ident[:-2] if ident.endswith("()") else ident
        if not check:
            continue
        if any(_ident_hits(check, window) for window in windows):
            continue
        return "`%s` not near line %d" % (ident, start)
    return ""


def _ident_hits(check, window):
    if "." in check:
        if _boundary_hit(check, window):
            return True
        if check in window:
            return False
        # Fallback: the last segment as a bare name, not the tail of another dotted chain.
        last = check.rsplit(".", 1)[-1]
        return bool(last) and re.search(r"(?<![\w.])" + re.escape(last) + r"(?!\w)", window) is not None
    return _boundary_hit(check, window)


def ground_code(text: str, repo_root: Path) -> dict:
    """Grounding gate for code lanes (locate, explore).

    Accepted when at least one finding and at least half of all findings are grounded.
    PATTERNS, RISKS and UNKNOWN pass through unchecked, labelled lane-reported.
    """
    root = Path(repo_root).resolve()
    sections = parse_sections(text)
    findings = sections.get("FINDINGS", [])
    items = []
    unverified = []
    for item in findings:
        why = _check_finding(item, root)
        if why:
            unverified.append("%s (%s)" % (item, why))
        else:
            items.append(item)
    unverified.extend(sections.get("UNVERIFIED", []))
    grounded = len(items)
    total = len(findings)
    passthrough = {name: sections.get(name, []) for name in CODE_PASSTHROUGH}
    blocks = [("FINDINGS (grounded)", items)]
    blocks += [("%s (lane-reported)" % name, passthrough[name]) for name in CODE_PASSTHROUGH]
    return {
        "ok": grounded >= 1 and grounded * 2 >= total,
        "grounded": grounded,
        "total": total,
        "items": items,
        "unverified": unverified,
        "passthrough": passthrough,
        "result": _render(blocks),
    }


_URL_RE = re.compile(r"https?://[^\s`\"'<>\]]+")
_QUOTE_RE = re.compile("[\"“]([^\"“”]+)[\"”]")


def _trim_url(u):
    """Drop trailing punctuation and any `)` that has no `(` in the URL (a wrapping paren, not part of it)."""
    while u and (u[-1] in ".,;:!?" or (u[-1] == ")" and u.count(")") > u.count("("))):
        u = u[:-1]
    return u


def _norm_url(url):
    u = _trim_url(url.strip()).split("#", 1)[0]
    u = u.rstrip("/.,;:")
    u = re.sub(r"^https?://", "", u, flags=re.IGNORECASE)
    return u.casefold()


def _evidence(tools):
    """Normalized outputs of completed calls: {fetched url: [webfetch outputs]}, plus the outputs of
    read/grep calls (opencode re-reads a saved fetch result that way). Search results never count."""
    pages = {}
    saved = []
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        name = str(t.get("tool") or "")
        if name not in WEB_TOOLS or str(t.get("status") or "") != "completed":
            continue
        output = normalize(t.get("output"))
        inp = t.get("input") if isinstance(t.get("input"), dict) else {}
        if name == "webfetch" and inp.get("url"):
            pages.setdefault(_norm_url(str(inp["url"])), []).append(output)
        elif name in ("read", "grep"):
            saved.append(output)
    return pages, saved


def _check_claim(item, pages, saved):
    """Return "" when the claim is grounded, else the failure reason."""
    quotes = _QUOTE_RE.findall(item)
    quote = normalize(quotes[-1]) if quotes else ""
    if not quote:
        return "no quote"
    if len(quote) < 8 or len(quote.split()) < MIN_QUOTE_WORDS:
        return "quote too short"
    found = _URL_RE.search(item)
    if not found:
        return "no URL"
    key = _norm_url(_trim_url(found.group(0)))
    docs = pages.get(key, []) + saved
    if key not in pages:
        anywhere = any(quote in d for d in saved + [d for ds in pages.values() for d in ds])
        return "URL not fetched" if anywhere else "quote not in session tool output"
    if not any(quote in doc for doc in docs):
        return "quote not in session tool output"
    return ""


def ground_web(text: str, tools: list) -> dict:
    """Grounding gate for web lanes (fact, research).

    `tools` is the `tools` list from oc_run.parse_events / run_once. Accepted when ANSWER
    is present and at least one claim is grounded. Failed claims go to `unverified`, never
    dropped. CONFLICTS and VERSION_NOTES pass through unchecked, labelled lane-reported.
    """
    sections = parse_sections(text)
    pages, saved = _evidence(tools)
    claims = sections.get("CLAIMS", [])
    answer = sections.get("ANSWER", [])
    items = []
    unverified = []
    for item in claims:
        why = _check_claim(item, pages, saved)
        if why:
            unverified.append("%s (%s)" % (item, why))
        else:
            items.append(item)
    unverified.extend(sections.get("UNVERIFIED", []))
    passthrough = {name: sections.get(name, []) for name in WEB_PASSTHROUGH}
    blocks = [("ANSWER", answer), ("CLAIMS (grounded)", items)]
    blocks += [("%s (lane-reported)" % name, passthrough[name]) for name in WEB_PASSTHROUGH]
    return {
        "ok": bool(answer) and len(items) >= 1,
        "grounded": len(items),
        "total": len(claims),
        "answer": answer,
        "items": items,
        "unverified": unverified,
        "passthrough": passthrough,
        "result": _render(blocks),
    }
