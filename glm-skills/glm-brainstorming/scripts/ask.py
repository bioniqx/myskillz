#!/usr/bin/env python3
"""Wait for a brainstorming answer, or start FAST and continue the chain.

`mode` asks once unless the request already names FAST or refuses it.
`fast` writes chain.json with mode fast and picks the scored leader even
when decide would ask or stop. The 15-minute wait is unchanged: a stop or
an unattacked leader is not a pick there. The chain file tells
glm-writing-plans to hand the plan to glm-dev-team without another question.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

import check
import decide

DEFAULT_TIMEOUT = 900


def auto_decision(options, atoms, ledger, deps, reports):
    """The engine's own ranking. ask=<id> means that id already won the score."""
    line = decide.decide(options, atoms, ledger, deps, reports)
    if line.startswith("DECISION ask=") and not line.endswith("unattacked"):
        return "DECISION pick=%s auto=1" % line.split("=", 1)[1]
    return line


def _load(ledger_path, options_path):
    ledger = decide.load_ledger(ledger_path)
    options = json.loads(Path(options_path).read_text(encoding="utf-8") or "[]")
    breaks = Path(ledger_path).parent / "breaks.json"
    reports = []
    if breaks.is_file():
        reports = json.loads(breaks.read_text(encoding="utf-8")).get("breaks") or []
    return options, list(ledger.get("atoms") or []), ledger, [], reports


def _pick_id(line):
    if not line.startswith("DECISION pick="):
        return ""
    return line.split("=", 1)[1].split()[0]


def write_chain(path, pick, source, mode=None):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "continue": True,
        "source": source,
        "pick": pick,
        "next": ["spec", "glm-writing-plans", "glm-dev-team"],
    }
    if mode:
        body["mode"] = mode
    dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


_FAST_PHRASE = re.compile(
    r"(\bfast[\s-]*mode\b"
    r"|\bmode\s*[:=]?\s*fast\b"
    r"|che\s*do\s*fast"
    r"|\b(?:dung|use|using|bat|chay|lam)\s+(?:che\s*do\s+)?fast\b"
    r"|--fast\b"
    r"|/fast\b)")
_FAST_CAPS = re.compile(r"(?<![A-Za-z])FAST(?![A-Za-z])")
_FAST_REFUSE = re.compile(
    r"(\b(?:khong|no|without|don't|dont|do not)\b.{0,30}\bfast\b"
    r"|\bnot\s+fast\b"
    r"|\bno\s*fast\b)")
_REPLY_FAST = re.compile(r"^\s*(?:1\b|fast\b|yes\b|co\b|dung\b)")
_REPLY_NORMAL = re.compile(r"^\s*(?:2\b|no\b|khong\b|thuong\b|normal\b)")


def names_fast(text):
    if _FAST_CAPS.search(text):
        return True
    return _FAST_PHRASE.search(check.fold_ascii(text)) is not None


def refuses_fast(text):
    return _FAST_REFUSE.search(check.fold_ascii(text)) is not None


def classify_request(text):
    """fast, normal, or ask. A refusal wins over a FAST phrase."""
    if refuses_fast(text):
        return "normal"
    if names_fast(text):
        return "fast"
    return "ask"


def classify_reply(text):
    """The answer to the startup question. Anything else stays ask."""
    if not text.strip():
        return "ask"
    if names_fast(text) and not refuses_fast(text):
        return "fast"
    if refuses_fast(text):
        return "normal"
    folded = check.fold_ascii(text)
    if _REPLY_FAST.search(folded):
        return "fast"
    if _REPLY_NORMAL.search(folded):
        return "normal"
    return "ask"


def _read_mode(path):
    try:
        kind = json.loads(Path(path).read_text(encoding="utf-8") or "{}").get("mode")
    except (OSError, json.JSONDecodeError):
        return ""
    return kind if kind in ("fast", "normal") else ""


def _write_mode(path, kind):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"mode": kind}) + "\n", encoding="utf-8")


def cmd_mode(a):
    text = sys.stdin.read()
    if text.strip():
        kind = classify_reply(text) if a.reply else classify_request(text)
    else:
        kind = _read_mode(a.file) or "ask"
    if kind in ("fast", "normal"):
        _write_mode(a.file, kind)
    print("MODE %s" % kind)
    if kind == "fast":
        print("NEXT: read fast.md and follow it. Do not ask which mode.")
    elif kind == "normal":
        print("NEXT: follow this skill's gates. Do not ask which mode.")
    else:
        print("ASK: Use FAST mode?")
        print("1. FAST - pick the best option, write the spec, write the plan, "
              "run glm-dev-team until the code is done, and do not ask again.")
        print("2. Normal - keep the approval gates.")
        print("NEXT: show the ASK block and end the turn. Do not launch lanes.")
    return 0


def _ranked(options, atoms, ledger, deps, reports):
    facts = decide._fact_map(ledger)
    return sorted(options, key=lambda o: (
        -decide.score_option(o, atoms, facts, deps, reports),
        o.get("id") or "",
    ))


def force_pick(options, atoms, ledger, deps, reports):
    """The scored leader, even when decide would ask or stop. ('', line) when empty."""
    line = auto_decision(options, atoms, ledger, deps, reports)
    pick = _pick_id(line)
    if pick:
        return pick, ""
    if not options:
        return "", line
    best = (_ranked(options, atoms, ledger, deps, reports)[0].get("id") or "")
    if not best:
        return "", line
    if "unattacked" in line:
        risk = "unattacked"
    elif line.strip() == "DECISION stop":
        risk = "all-broken"
    else:
        risk = "forced"
    return best, risk


def cmd_fast(a):
    try:
        options, atoms, led, deps, reports = _load(a.ledger, a.options)
    except (OSError, json.JSONDecodeError) as exc:
        print("NEXT: options or ledger is not readable (%s). "
              "Write them and re-run fast. Do not ask the user." % exc)
        return 2
    pick, risk = force_pick(options, atoms, led, deps, reports)
    if not pick:
        print("DECISION stop")
        print("NEXT: there is no option. Write one option from the request and the "
              "kept facts, attack it once, run close again, and re-run fast. "
              "Do not ask the user.")
        return 2
    write_chain(a.chain, pick, "fast", mode="fast")
    _write_mode(a.mode, "fast")
    print("AUTO")
    print("DECISION pick=%s auto=1" % pick)
    if risk:
        print("RISK %s" % risk)
    print("NEXT: pass the AUTO block to check.py approve --asked design. "
          "On RESULT approve yes, write the spec of this pick and hand off. "
          "Do not ask.")
    return 0


def _reply_text(path):
    p = Path(path)
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8").strip()


def resolve_once(ledger, options, reply, cancel, chain, now, deadline):
    """One observation. Returns (kind, text) or None while the wait should continue."""
    if Path(cancel).is_file():
        return "CANCEL", ""
    text = _reply_text(reply)
    if text:
        return "REPLY", text
    if now < deadline:
        return None
    options, atoms, led, deps, reports = _load(ledger, options)
    line = auto_decision(options, atoms, led, deps, reports)
    pick = _pick_id(line)
    if pick:
        write_chain(chain, pick, "auto")
    return "AUTO", line


def wait_loop(ledger, options, reply, cancel, chain, timeout, sleep=time.sleep, clock=time.monotonic):
    deadline = clock() + timeout
    while True:
        got = resolve_once(ledger, options, reply, cancel, chain, clock(), deadline)
        if got is not None:
            return got
        sleep(0.2)


def cmd_wait(a):
    kind, text = wait_loop(a.ledger, a.options, a.reply, a.cancel, a.chain, a.timeout)
    if kind == "CANCEL":
        print("CANCEL")
        print("NEXT: the user replied in chat. Pass that reply to check.py approve. Ignore a later AUTO.")
        return 0
    if kind == "REPLY":
        print("REPLY")
        print(text)
        print("NEXT: pass the REPLY body to check.py approve --asked design.")
        return 0
    print("AUTO")
    print(text)
    if text.startswith("DECISION pick="):
        print("APPROVE: approved")
        print("NEXT: render that option, write the spec, then handoff.py next "
              "--self glm-brainstorming --event architectural-approved. "
              "chain.json continues into the plan and glm-dev-team.")
        return 0
    print("NEXT: do not write a design. %s" % text)
    return 2


def cmd_chain(a):
    write_chain(a.chain, a.pick, "user")
    print("CHAIN %s" % a.pick)
    print("NEXT: handoff.py next --self glm-brainstorming --event architectural-approved")
    return 0


def cmd_cancel(a):
    Path(a.cancel).parent.mkdir(parents=True, exist_ok=True)
    Path(a.cancel).write_text("cancel\n", encoding="utf-8")
    print("CANCEL")
    print("NEXT: use the chat reply. Do not apply an AUTO from this wait.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="ask.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wait")
    w.add_argument("--ledger", required=True)
    w.add_argument("--options", required=True)
    w.add_argument("--reply", default=".brainstorm/drafts/reply.txt")
    w.add_argument("--cancel", default=".brainstorm/drafts/ask.cancel")
    w.add_argument("--chain", default=".brainstorm/drafts/chain.json")
    w.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    w.set_defaults(fn=cmd_wait)
    c = sub.add_parser("cancel")
    c.add_argument("--cancel", default=".brainstorm/drafts/ask.cancel")
    c.set_defaults(fn=cmd_cancel)
    k = sub.add_parser("chain")
    k.add_argument("--pick", required=True)
    k.add_argument("--chain", default=".brainstorm/drafts/chain.json")
    k.set_defaults(fn=cmd_chain)
    m = sub.add_parser("mode")
    m.add_argument("--file", default=".brainstorm/drafts/mode.json")
    m.add_argument("--reply", action="store_true")
    m.set_defaults(fn=cmd_mode)
    f = sub.add_parser("fast")
    f.add_argument("--ledger", required=True)
    f.add_argument("--options", required=True)
    f.add_argument("--chain", default=".brainstorm/drafts/chain.json")
    f.add_argument("--mode", default=".brainstorm/drafts/mode.json")
    f.set_defaults(fn=cmd_fast)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
