#!/usr/bin/env python3
"""Close design and plan decisions from facts, atoms, and re-run commands.

The model may propose. This script picks, rejects, or asks. Stdlib only.
Imported by check.py, plan_tool.py, devteam.py, and audit.py. It does not import them
at load time. The lazy, optional `import check` inside cite_status exists
only to call eval_cite for file-fact validation. In vendored copies without
a sibling check.py the import misses by design, and file facts degrade
accordingly.
"""
import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import urllib.request
from pathlib import Path

REQ_WORD = re.compile(r"(?i)^(must|shall|need to|needs to)\b")
BULLET = re.compile(r"^[ \t]*(?:[-*][ \t]*)?(?:\[[ xX]\][ \t]*)?")
QUOTED = re.compile(r'"([^"\n]{2,})"')
SINGLE = re.compile(r"'([^'\n]{2,})'")
INTEGER = re.compile(r"(?<!\d)(\d{2,})(?!\d)")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
VERSION_SPAN = re.compile(r"\d+(?:\.\d+)+")
FACT_ID = re.compile(r"\b(F-\d+)\b")
PATH_TOKEN = re.compile(r"(?:[\w.@+-]+/)+[\w.@+-]+\.[A-Za-z0-9]+")
URL_TOKEN = re.compile(r"https://[^\s<>\"')\]]+")
VER_TOKEN = re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b")
ATOM_LINE = re.compile(r"^ATOM:\s*(.*)$")
OPTION_LINE = re.compile(r"^OPTION\s+(\S+)\s*$")
LOC_LINE = re.compile(r"^(.+):(\d+)$")
MAX_WEB = 4
MAX_BODY = 1_000_000
MAX_QUOTE_WORDS = 25


def extract_atoms(text):
    """Mechanical atoms, in order, de-duplicated. No model call."""
    found, seen = [], set()

    def add(span):
        span = (span or "").strip()
        if len(span) < 2 or span in seen:
            return
        seen.add(span)
        found.append(span)

    for line in text.splitlines():
        body = BULLET.sub("", line).strip()
        if REQ_WORD.match(body):
            add(body)
        for rx in (QUOTED, SINGLE):
            for m in rx.finditer(line):
                add(m.group(1))
        covered = [(m.start(), m.end()) for m in DATE.finditer(line)]
        covered += [(m.start(), m.end()) for m in VERSION_SPAN.finditer(line)]
        for m in INTEGER.finditer(line):
            if any(a <= m.start() < b for a, b in covered):
                continue
            add(m.group(1))
    return found


def check_model_atoms(source, model_output):
    """Keep ATOM lines whose span is a substring of source. Everything else is dropped."""
    kept, dropped = [], []
    for raw in model_output.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = ATOM_LINE.match(line)
        span = m.group(1).strip() if m else ""
        if m and span and span in source:
            if span not in kept:
                kept.append(span)
        else:
            dropped.append(line)
    frozen = list(extract_atoms(source))
    for span in kept:
        if span not in frozen:
            frozen.append(span)
    return frozen, dropped


def coverage(atoms, homes):
    """homes: atom -> owner id, or 'out-of-scope'. Fail lines for zero or two homes."""
    fails = []
    for atom in atoms:
        owners = [name for name, text in homes.items() if atom in text]
        if len(owners) == 0:
            fails.append("FAIL atom - no home: %s" % atom)
        elif len(owners) > 1:
            fails.append("FAIL atom - %s homes (%s): %s" % (len(owners), ", ".join(owners), atom))
    return fails


def _empty_ledger():
    return {"facts": [], "atoms": []}


def load_ledger(path):
    p = Path(path)
    if not p.is_file():
        return _empty_ledger()
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("facts", [])
    data.setdefault("atoms", [])
    return data


def save_ledger(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


def _next_id(facts):
    n = 0
    for fact in facts:
        m = re.match(r"F-(\d+)$", fact.get("id") or "")
        if m:
            n = max(n, int(m.group(1)))
    return "F-%d" % (n + 1)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cite_status(root, loc, text):
    """OK when the sibling check.eval_cite accepts loc plus text. None if check.py is absent."""
    m = LOC_LINE.match(loc or "")
    if not m or not text:
        return False
    try:
        import check as brainstorm_check
    except ImportError:
        return None
    path, lo = m.group(1), int(m.group(2))
    status, _msg = brainstorm_check.eval_cite(
        Path(root).resolve(), {}, path, lo, lo, False, text, True)
    return status == "ok"


def add_fact(ledger, fields, root=".", stdout="", source=""):
    """Assign the next id. The caller's id, if any, is ignored."""
    kind = (fields.get("kind") or "").strip()
    loc = (fields.get("loc") or "").strip()
    text = (fields.get("text") or "").strip()
    if kind not in ("file", "command", "user", "web"):
        return None, "FAIL kind - file|command|user|web"
    if not text:
        return None, "FAIL text - empty"
    status, reason = "UNPROVEN", ""
    if kind == "file":
        ok = cite_status(root, loc, text)
        if ok is None:
            return None, "FAIL cite - check.py is not beside decide.py"
        status = "OK" if ok else "UNPROVEN"
        if not ok:
            reason = "cite"
    elif kind == "command":
        status = "OK" if text in stdout else "UNPROVEN"
        if status != "OK":
            reason = "stdout"
    elif kind == "user":
        status = "OK" if text in source else "UNPROVEN"
        if status != "OK":
            reason = "source"
    fact = {
        "id": _next_id(ledger["facts"]),
        "kind": kind,
        "loc": loc,
        "sha256": _sha(text),
        "text": text,
        "status": status,
    }
    if reason:
        fact["reason"] = reason
    ledger["facts"].append(fact)
    return fact, ""


def _fact_map(ledger):
    return {f["id"]: f for f in ledger.get("facts") or []}


def prove_ledger(ledger, offline=False, fetch=None):
    """Mark web facts. Offline never opens a socket. At most four fetches per call."""
    web = [f for f in ledger.get("facts") or [] if f.get("kind") == "web"]
    if offline:
        for fact in web:
            fact["status"] = "UNPROVEN"
            fact["reason"] = "offline"
        return
    fetch = fetch or _fetch
    for i, fact in enumerate(web):
        if i >= MAX_WEB:
            fact["status"] = "UNPROVEN"
            fact["reason"] = "cap"
            continue
        body, err = fetch(fact.get("loc") or "")
        text = fact.get("text") or ""
        if err or not body or text not in body or len(text.split()) > MAX_QUOTE_WORDS:
            fact["status"] = "UNPROVEN"
            fact["reason"] = err or "quote"
        else:
            fact["status"] = "OK"
            fact.pop("reason", None)


class _OneHop(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if getattr(req, "hop", 0) >= 1:
            return None
        nxt = super().redirect_request(req, fp, code, msg, headers, newurl)
        if nxt is not None:
            nxt.hop = getattr(req, "hop", 0) + 1
        return nxt


def _fetch(url):
    if not url.startswith("https://"):
        return "", "url"
    opener = urllib.request.build_opener(_OneHop)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "glm-decide"})
        req.hop = 0
        with opener.open(req, timeout=15) as resp:
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if ctype and not ctype.startswith("text/") and "json" not in ctype and "xml" not in ctype:
                return "", "type"
            raw = resp.read(MAX_BODY + 1)
    except Exception as exc:
        return "", exc.__class__.__name__
    if len(raw) > MAX_BODY:
        return "", "size"
    return raw.decode("utf-8", "replace"), ""


def parse_breaks(text):
    """Breaker reports. reproduced is not accepted from the model."""
    reports, cur = [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = OPTION_LINE.match(line)
        if m:
            cur = {"option": m.group(1), "kind": "", "payload": "", "reproduced": False}
            reports.append(cur)
            continue
        if cur is None:
            continue
        if line == "COUNTEREXAMPLE":
            cur["kind"] = "COUNTEREXAMPLE"
        elif line == "NO-BREAK":
            cur["kind"] = "NO-BREAK"
        elif line.startswith("cmd:") or line.startswith("check:") or line.startswith("cite:"):
            cur["payload"] = line.split(":", 1)[1].strip()
            if line.startswith("cite:"):
                cur["kind"] = cur["kind"] or "COUNTEREXAMPLE"
                cur["via"] = "cite"
            elif line.startswith("check:"):
                cur["via"] = "check"
            else:
                cur["via"] = "cmd"
    return reports


def _run_cmd(cmd, root, timeout=60):
    try:
        argv = shlex.split(cmd)
    except ValueError:
        return 1
    if not argv:
        return 1
    try:
        proc = subprocess.run(argv, cwd=root, timeout=timeout, capture_output=True, text=True)
    except (OSError, subprocess.TimeoutExpired):
        return 1
    return proc.returncode


def _cite_reproduces(root, payload, option):
    m = re.match(r'^(\S+:\d+)\s+"(.*)"\s*$', payload)
    if not m:
        return False
    loc, snippet = m.group(1), m.group(2)
    ok = cite_status(root, loc, snippet)
    if not ok:
        return False
    blob = (option.get("text") or "") + "\n" + "\n".join(option.get("atoms_hit") or [])
    return any(tok and tok in blob for tok in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", snippet))


def apply_breaks(reports, options, root):
    by_id = {o.get("id"): o for o in options}
    for report in reports:
        option = by_id.get(report.get("option")) or {}
        via = report.get("via")
        if via == "cite":
            report["reproduced"] = bool(
                report.get("kind") == "COUNTEREXAMPLE" and _cite_reproduces(root, report.get("payload") or "", option))
        elif via in ("cmd", "check"):
            code = _run_cmd(report.get("payload") or "", root)
            if report.get("kind") == "COUNTEREXAMPLE":
                report["reproduced"] = code != 0
            elif report.get("kind") == "NO-BREAK":
                report["reproduced"] = code == 0
            else:
                report["reproduced"] = False
        else:
            report["reproduced"] = False
    return reports


def _attacked(option_id, reports):
    own = [r for r in reports if r.get("option") == option_id and r.get("reproduced")]
    return any(r.get("kind") in ("COUNTEREXAMPLE", "NO-BREAK") for r in own)


def _breaks(option_id, reports):
    return sum(1 for r in reports
               if r.get("option") == option_id and r.get("kind") == "COUNTEREXAMPLE" and r.get("reproduced"))


def score_option(option, atoms, facts, deps, reports):
    score = 0
    blob = (option.get("out_of_scope") or "") + "\n" + "\n".join(option.get("atoms_hit") or [])
    if all(atom in blob for atom in atoms):
        score += 3
    ids = option.get("fact_ids") or []
    if ids and all(facts.get(fid, {}).get("status") == "OK" for fid in ids):
        score += 2
    score -= 5 * _breaks(option.get("id"), reports)
    known = set(deps)
    for name in option.get("new_deps") or []:
        if name not in known:
            score -= 2
    for assumption in option.get("assumptions") or []:
        fid = assumption.get("fact") if isinstance(assumption, dict) else ""
        if facts.get(fid, {}).get("status") != "OK":
            score -= 1
    return score


def _rescore_without(option, fact_id, atoms, facts, deps, reports):
    clone = dict(option)
    clone["fact_ids"] = [fid for fid in (option.get("fact_ids") or []) if fid != fact_id]
    return score_option(clone, atoms, facts, deps, reports)


def decide(options, atoms, ledger, deps, reports):
    """One DECISION line. The model does not vote."""
    facts = _fact_map(ledger)
    if not options:
        return "DECISION stop"
    ranked = sorted(options, key=lambda o: (-score_option(o, atoms, facts, deps, reports), o.get("id") or ""))
    best = ranked[0]
    best_score = score_option(best, atoms, facts, deps, reports)
    second = score_option(ranked[1], atoms, facts, deps, reports) if len(ranked) > 1 else 0
    if not _attacked(best.get("id"), reports):
        return "DECISION ask=unattacked"
    broken = [o for o in options if _breaks(o.get("id"), reports)]
    if best_score < 0 or len(broken) == len(options):
        return "DECISION stop"
    margin = best_score - second
    if margin < 3:
        return "DECISION ask=%s" % best.get("id")
    if margin in (3, 4):
        ok_facts = [facts[fid] for fid in (best.get("fact_ids") or [])
                    if facts.get(fid, {}).get("status") == "OK"]
        if ok_facts:
            drop = max(ok_facts, key=lambda f: len(f.get("text") or ""))
            rescored = _rescore_without(best, drop["id"], atoms, facts, deps, reports)
            new_margin = rescored - second
            winner_changed = len(ranked) > 1 and rescored < second
            if winner_changed or new_margin < 3:
                return "DECISION ask=%s" % best.get("id")
            margin = new_margin
    return "DECISION pick=%s margin=%d" % (best.get("id"), margin)


def bind_text(draft, ledger, pick=None):
    """Fail factual lines that do not cite an OK fact. pick must appear when set."""
    fails = []
    facts = _fact_map(ledger)
    for raw in draft.splitlines():
        line = raw.strip()
        if not line:
            continue
        if not (PATH_TOKEN.search(line) or URL_TOKEN.search(line) or VER_TOKEN.search(line)):
            continue
        if "unverified" in line.lower():
            continue
        ids = FACT_ID.findall(line)
        if any(facts.get(fid, {}).get("status") == "OK" for fid in ids):
            continue
        fails.append("FAIL fact - %s" % line[:80])
    if pick and pick not in draft:
        fails.append("FAIL pick - draft does not name %s" % pick)
    return fails


def _parse_kv(text):
    fields = {}
    for raw in text.splitlines():
        if ":" not in raw:
            continue
        key, value = raw.split(":", 1)
        fields[key.strip().lower()] = value.strip()
    return fields


def _print_decision_inputs(ns):
    ledger = load_ledger(ns.ledger)
    options = json.loads(sys.stdin.read() or "[]")
    deps = []
    if ns.deps:
        deps = [ln.strip() for ln in Path(ns.deps).read_text(encoding="utf-8").splitlines() if ln.strip()]
    atoms = list(ledger.get("atoms") or [])
    if ns.atoms:
        atoms = [ln.strip() for ln in Path(ns.atoms).read_text(encoding="utf-8").splitlines() if ln.strip()]
    breaks_path = Path(ns.ledger).parent / "breaks.json"
    reports = []
    if breaks_path.is_file():
        reports = json.loads(breaks_path.read_text(encoding="utf-8")).get("breaks") or []
    return options, atoms, ledger, deps, reports


def main(argv=None):
    p = argparse.ArgumentParser(prog="decide.py")
    sp = p.add_subparsers(dest="cmd", required=True)

    sp.add_parser("atoms")

    pc = sp.add_parser("atoms-check")
    pc.add_argument("--source", required=True)

    pa = sp.add_parser("add")
    pa.add_argument("--ledger", required=True)
    pa.add_argument("--root", default=".")
    pa.add_argument("--stdout")
    pa.add_argument("--source")

    pp = sp.add_parser("prove")
    pp.add_argument("--ledger", required=True)
    pp.add_argument("--offline", action="store_true")

    pb = sp.add_parser("break")
    pb.add_argument("--root", required=True)
    pb.add_argument("--ledger", required=True)
    pb.add_argument("--options")

    ps = sp.add_parser("score")
    ps.add_argument("--ledger", required=True)
    ps.add_argument("--deps")
    ps.add_argument("--atoms")

    pn = sp.add_parser("bind")
    pn.add_argument("--ledger", required=True)
    pn.add_argument("--pick")

    # `atoms --check` is the spec's spelling. argparse would eat --check as a
    # global flag, so the CLI accepts both `atoms --check --source` via a
    # pre-pass below.
    ns, extra = p.parse_known_args(argv)
    if ns.cmd == "atoms" and extra:
        if extra[0] != "--check":
            p.error("unrecognized arguments: %s" % " ".join(extra))
        chk = argparse.ArgumentParser(prog="decide.py atoms --check")
        chk.add_argument("--source", required=True)
        ns = chk.parse_args(extra[1:])
        ns.cmd = "atoms-check"
    if ns.cmd == "atoms":
        text = sys.stdin.read()
        for atom in extract_atoms(text):
            print("ATOM: %s" % atom)
        print("NEXT: one Flash call, no other context. Prompt is the request text plus: "
              "Emit only ATOM: lines, each span copied verbatim. Then run atoms --check --source <file>.")
        return 0
    if ns.cmd == "atoms-check":
        source = Path(ns.source).read_text(encoding="utf-8")
        frozen, dropped = check_model_atoms(source, sys.stdin.read())
        for atom in frozen:
            print("ATOM: %s" % atom)
        for line in dropped:
            print("DROP: %s" % line)
        print("FROZEN n=%d" % len(frozen))
        return 0
    if ns.cmd == "add":
        ledger = load_ledger(ns.ledger)
        raw = sys.stdin.read().strip()
        fields = json.loads(raw) if raw.startswith("{") else _parse_kv(raw)
        stdout = Path(ns.stdout).read_text(encoding="utf-8") if ns.stdout else ""
        source = Path(ns.source).read_text(encoding="utf-8") if ns.source else ""
        fact, err = add_fact(ledger, fields, root=ns.root, stdout=stdout, source=source)
        if err:
            print(err)
            return 1
        save_ledger(ns.ledger, ledger)
        print("%s status=%s" % (fact["id"], fact["status"]))
        return 0
    if ns.cmd == "prove":
        ledger = load_ledger(ns.ledger)
        prove_ledger(ledger, offline=ns.offline)
        save_ledger(ns.ledger, ledger)
        for fact in ledger["facts"]:
            if fact.get("kind") == "web":
                print("%s status=%s%s" % (fact["id"], fact["status"],
                                          (" reason=%s" % fact["reason"]) if fact.get("reason") else ""))
        return 0
    if ns.cmd == "break":
        opt_path = Path(ns.options) if ns.options else Path(ns.ledger).parent / "options.json"
        if ns.options and not opt_path.is_file():
            print("FAIL options - %s" % opt_path)
            return 1
        options = json.loads(opt_path.read_text(encoding="utf-8")) if opt_path.is_file() else []
        reports = apply_breaks(parse_breaks(sys.stdin.read()), options, ns.root)
        path = Path(ns.ledger).parent / "breaks.json"
        path.write_text(json.dumps({"breaks": reports}, indent=1) + "\n", encoding="utf-8")
        for report in reports:
            print("BREAK %s reproduced=%s" % (report.get("option"), "yes" if report.get("reproduced") else "no"))
        return 0
    if ns.cmd == "score":
        options, atoms, ledger, deps, reports = _print_decision_inputs(ns)
        print(decide(options, atoms, ledger, deps, reports))
        return 0
    if ns.cmd == "bind":
        fails = bind_text(sys.stdin.read(), load_ledger(ns.ledger), pick=ns.pick)
        for line in fails:
            print(line)
        print("RESULT bind fail=%d" % len(fails))
        return 1 if fails else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
