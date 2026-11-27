#!/usr/bin/env python3
"""Wait for a brainstorming answer, or start FAST or SLOW and continue the chain.

`mode` classifies FAST vs SLOW through handoff.mode_of and never asks: a
request that names neither mode is FAST. `fast` writes chain.json with mode
fast and picks the scored leader even when decide would ask or stop.
`chain` without --pick is the SLOW form: nobody approves, so the engine names
the pick (a narrow margin chains its leader), writes chain.json with the
stamped mode and prints the approval; an unattacked leader or a stop is
refused with its one repair. Under SLOW the wait stops at --timeout and picks
nothing. Under FAST the 15-minute wait is unchanged: a stop or an unattacked
leader is not a pick there. The chain file tells z-writing-plans to hand the
plan to z-dev-team without another question.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import decide
from handoff import brainstorm_mode, mode_of, read_mode_stamp

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
        "next": ["spec", "z-writing-plans", "z-dev-team"],
    }
    if mode:
        body["mode"] = mode
    dest.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")


def _read_mode(path):
    try:
        kind = json.loads(Path(path).read_text(encoding="utf-8") or "{}").get("mode")
    except (OSError, json.JSONDecodeError):
        return ""
    return kind if kind in ("fast", "slow", "normal") else ""


def _write_mode(path, kind):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"mode": kind}) + "\n", encoding="utf-8")


def cmd_mode(a):
    text = sys.stdin.read()
    kind = mode_of(text, _read_mode(a.file) or read_mode_stamp())
    _write_mode(a.file, kind)
    print("MODE %s" % kind)
    if kind == "fast":
        print("NEXT: follow the PACE fast NEXT. Do not ask which mode.")
    else:
        print("NEXT: follow this skill's gates. Do not ask which mode.")
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
    if (a.request or "").strip():
        # FAST has exactly one option: the request itself. Writing it here
        # saves the model the options.json write.
        dest = Path(a.options)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(
            json.dumps([{"id": "A", "text": a.request}], ensure_ascii=False,
                       indent=1) + "\n",
            encoding="utf-8")
    try:
        options, atoms, led, deps, reports = _load(a.ledger, a.options)
    except (OSError, json.JSONDecodeError) as exc:
        print("NEXT: options or ledger is not readable (%s). "
              "Write them and re-run fast. Do not ask the user." % exc)
        return 2
    pick, risk = force_pick(options, atoms, led, deps, reports)
    if not pick:
        print("DECISION stop")
        print("NEXT: there is no option. Write one option from the request, "
              "id A, and re-run fast. Do not launch an attack lane. "
              "Do not ask the user.")
        return 2
    write_chain(a.chain, pick, "fast", mode="fast")
    _write_mode(a.mode, "fast")
    print("AUTO")
    print("DECISION pick=%s auto=1" % pick)
    if risk:
        print("RISK %s" % risk)
    # The AUTO block always satisfies approve's auto rule; recording it here
    # keeps the gate while removing the separate approve call.
    print("RESULT approve yes")
    print("NEXT: the pick is approved and chain.json is written. Write the "
          "design draft (Path line, assumptions, out of scope, no question "
          "mark) and run check.py send --ledger %s --pick %s until it prints "
          "fail=0. Then write the short spec (goal, files, acceptance, out "
          "of scope), run check.py spec <path>, and on fail=0 follow the "
          "HANDOFF it prints. Do not read architectural.md. Do not launch "
          "a lane. Do not ask." % (a.ledger, pick))
    return 0


def _reply_text(path):
    p = Path(path)
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8").strip()


def resolve_once(ledger, options, reply, cancel, chain, now, deadline, allow_pick=True):
    """One observation. Returns (kind, text) or None while the wait should continue.

    allow_pick=False is the SLOW wait: the deadline ends it with TIMEOUT, before
    the ledger or the options are read.
    """
    if Path(cancel).is_file():
        return "CANCEL", ""
    text = _reply_text(reply)
    if text:
        return "REPLY", text
    if deadline is None or now < deadline:
        return None
    if not allow_pick:
        return "TIMEOUT", ""
    options, atoms, led, deps, reports = _load(ledger, options)
    line = auto_decision(options, atoms, led, deps, reports)
    pick = _pick_id(line)
    if pick:
        write_chain(chain, pick, "auto")
    return "AUTO", line


def wait_loop(ledger, options, reply, cancel, chain, timeout, allow_pick=True, sleep=time.sleep,
              clock=time.monotonic):
    deadline = None if timeout is None else clock() + timeout
    while True:
        got = resolve_once(ledger, options, reply, cancel, chain, clock(), deadline, allow_pick)
        if got is not None:
            return got
        sleep(0.2)


def cmd_wait(a):
    slow = brainstorm_mode() == "slow"
    kind, text = wait_loop(a.ledger, a.options, a.reply, a.cancel, a.chain, a.timeout,
                           allow_pick=not slow)
    if kind == "CANCEL":
        print("CANCEL")
        print("NEXT: the user replied in chat. Pass that reply to check.py approve. Ignore a later AUTO.")
        return 0
    if kind == "REPLY":
        print("REPLY")
        print(text)
        print("NEXT: pass the REPLY body to check.py approve --asked design.")
        return 0
    if kind == "TIMEOUT":
        print("TIMEOUT")
        print("NEXT: no reply within the limit. Nothing is approved: do not pick, "
              "do not write, do not restart the wait. Tell the user in one line "
              "and end the turn; a later reply goes to check.py approve --asked design.")
        return 0
    print("AUTO")
    print(text)
    if text.startswith("DECISION pick="):
        print("APPROVE: approved")
        print("NEXT: render that option, write the spec, then handoff.py next "
              "--self z-brainstorming --event architectural-approved. "
              "chain.json continues into the plan and z-dev-team.")
        return 0
    print("NEXT: do not write a design. %s" % text)
    return 2


def _chain_repair(line, options, atoms, ledger, deps, reports):
    """The one repair a refused chain names. SLOW never hands it to the user."""
    if line == "DECISION ask=unattacked":
        ranked = _ranked(options, atoms, ledger, deps, reports)
        leader = " %s" % ranked[0].get("id") if ranked else ""
        return ("the score leader%s has no reproduced break: run one breaker on it, "
                "then chain again." % leader)
    if line == "DECISION stop":
        return ("every option is broken or scores under zero: rewrite the options once "
                "from what survived the breakers, attack them, then chain again.")
    return "re-run check.py close with ## BREAKERS, then chain again."


def cmd_chain(a):
    kind = _read_mode(a.mode) or read_mode_stamp()
    mode = kind if kind in ("fast", "slow") else None
    pick = a.pick
    source = "user"
    if not pick:
        # SLOW has nobody to approve, so the engine names the pick: a narrow
        # margin chains its leader; an unattacked leader or a stop is refused.
        try:
            options, atoms, led, deps, reports = _load(a.ledger, a.options)
        except (OSError, json.JSONDecodeError) as exc:
            print("NEXT: options or ledger is not readable (%s). Fix them and re-run "
                  "chain. Do not ask the user." % exc)
            return 2
        line = auto_decision(options, atoms, led, deps, reports)
        pick = _pick_id(line)
        if not pick:
            print(line)
            print("NEXT: %s Do not ask the user."
                  % _chain_repair(line, options, atoms, led, deps, reports))
            return 2
        source = "auto"
        print("AUTO")
        print("DECISION pick=%s auto=1" % pick)
        # The AUTO block satisfies approve's auto rule; recording it here keeps
        # that gate without a separate approve call, as `fast` does.
        print("RESULT approve yes")
    write_chain(a.chain, pick, source, mode=mode)
    print("CHAIN %s" % pick)
    if source == "auto":
        print("NEXT: write the design note and run check.py send --ledger %s --pick %s "
              "until it prints fail=0; write the spec and run check.py spec <path>. "
              "A Spike or a design-only request stops after its answer or its spec and "
              "ends with handoff.py slow-done. Only when the request asks to build, run "
              "handoff.py next --self z-brainstorming --event architectural-approved."
              % (a.ledger, pick))
    else:
        print("NEXT: handoff.py next --self z-brainstorming --event architectural-approved")
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
    m = sub.add_parser("mode")
    m.add_argument("--file", default=".brainstorm/drafts/mode.json")
    m.set_defaults(fn=cmd_mode)
    f = sub.add_parser("fast")
    f.add_argument("--ledger", required=True)
    f.add_argument("--options", required=True)
    f.add_argument("--request", default="",
                   help="the user request; writes it as the single option")
    f.add_argument("--chain", default=".brainstorm/drafts/chain.json")
    f.add_argument("--mode", default=".brainstorm/drafts/mode.json")
    f.set_defaults(fn=cmd_fast)
    c = sub.add_parser("chain")
    c.add_argument("--pick", default="",
                   help="omit it and the engine names the pick (the SLOW form)")
    c.add_argument("--ledger", default=".brainstorm/drafts/ledger.json")
    c.add_argument("--options", default=".brainstorm/drafts/options.json")
    c.add_argument("--chain", default=".brainstorm/drafts/chain.json")
    c.add_argument("--mode", default=".brainstorm/drafts/mode.json")
    c.set_defaults(fn=cmd_chain)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
