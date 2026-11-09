#!/usr/bin/env python3
"""Wait for a brainstorming answer, then continue the chain.

A chat reply cancels the wait. After the timeout the highest-scored option
that was already attacked is the pick. A stop or an unattacked leader is
not a pick. The chain file tells glm-writing-plans to hand the plan to
glm-dev-team without another question.
"""
import argparse
import json
import sys
import time
from pathlib import Path

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


def write_chain(path, pick, source):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({
        "continue": True,
        "source": source,
        "pick": pick,
        "next": ["spec", "glm-writing-plans", "glm-dev-team"],
    }, indent=2) + "\n", encoding="utf-8")


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
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
