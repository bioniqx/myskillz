#!/usr/bin/env python3
"""Route a glm-* skill to a sibling, or keep the work here.

GLM-5.3 drops rules that sit in the middle of a long skill file, follows the
last copy it saw, and treats a soft "ok" as approval. This script is the
binding copy: every skill runs it, and the printed NEXT and GUARD lines win
over the model's guess.

  handoff.py route --self NAME     stdin: the user request. Always exit 0.
  handoff.py next  --self NAME --event EVENT
                                   stdin ignored. Always exit 0.

A line "From: glm-a,glm-b" at the start of stdin is the chain so far. The
script refuses a cycle and stops at 3 skills. Exit 2 is a usage error.
Stdlib only. No network. No writes.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata

SKILLS = (
    "glm-idea-to-spec",
    "glm-systematic-debugging",
    "glm-requirements-code-audit",
    "glm-doc-generator",
    "glm-git-diff-summary",
    "glm-writing-plans",
    "glm-dev-team",
    "glm-brainstorming",
)

# Skills check.py send accepts as a brainstorming hand-off target.
HANDOFF_TARGETS = tuple(name for name in SKILLS if name != "glm-brainstorming")

MAX_CHAIN = 3

FEATURE_RE = re.compile(r"\b(add|build|implement|create|design)\b")
FIX_RE = re.compile(r"\b(fix|implement|patch|sua loi|sua)\b")
FROM_RE = re.compile(r"(?m)^[ \t>*-]*From:\s*([a-z0-9,.-]+)\s*$", re.I)

# Order is priority. The first match wins. Feature words suppress the two
# skills a feature request mentions only in passing (docs, commit message).
ROUTE_RULES = (
    ("glm-idea-to-spec", re.compile(
        r"\b(is (?:it|this)(?: \w+){0,4} viable|business model|make money|product idea|y tuong san pham)\b")),
    ("glm-systematic-debugging", re.compile(
        r"\b(traceback|stack ?trace|stacktrace|failing tests?|tests? fails?|flaky|regression|bugs?|bi loi)\b")),
    ("glm-requirements-code-audit", re.compile(
        r"\b(match the spec|match this spec|requirements traceability|gaps between spec|doi chieu spec)\b")),
    ("glm-doc-generator", re.compile(
        r"\b(write|update|draft) (the |a )?(readme|api reference|api docs|user guide|onboarding guide)\b"
        r"|\b(document (this|the) (repo|code|codebase|project)|write docs)\b")),
    ("glm-git-diff-summary", re.compile(
        r"\b(commit message|pr message|pull request message|what did this branch|"
        r"summarize (the |this )?branch|tom tat thay doi|so sanh voi main)\b")),
    ("glm-writing-plans", re.compile(
        r"\b(write the (implementation )?plan|approved design|design is approved|thiet ke da duyet|viet plan)\b")),
    ("glm-dev-team", re.compile(
        r"\b(implement the (approved )?plan|plan is approved|just implement)\b")),
)
SUPPRESS_IF_FEATURE = {"glm-doc-generator", "glm-git-diff-summary"}

BECAUSE = {
    "glm-idea-to-spec": "the request is a product idea or a viability question",
    "glm-systematic-debugging": "the request is a bug, failing test, or unexpected behavior",
    "glm-requirements-code-audit": "the request asks whether the code matches a spec",
    "glm-doc-generator": "the request asks for documentation of existing code",
    "glm-git-diff-summary": "the request asks for a branch summary or a commit message",
    "glm-writing-plans": "an approved design needs an implementation plan",
    "glm-dev-team": "an approved plan needs implementation",
    "glm-brainstorming": "the request is a feature or design change and no plan is approved yet",
}

# A feature request ("add X") is design work. These skills do not own it.
FEATURE_BOUNCE = {
    "glm-doc-generator",
    "glm-git-diff-summary",
    "glm-requirements-code-audit",
    "glm-systematic-debugging",
}

EXITS = {
    "glm-idea-to-spec": (
        ("spec-ready", "glm-brainstorming", "the spec is approved and the build shape is not settled"),
        ("plan", "glm-writing-plans", "the user wants an implementation plan from the spec"),
        ("implement", "glm-dev-team", "the user wants the approved spec built"),
    ),
    "glm-brainstorming": (
        ("architectural-approved", "glm-writing-plans", "the architectural design was approved"),
        ("bounded-large", "glm-dev-team", "the approved change needs more than 3 files or parallel slices"),
        ("commit-message", "glm-git-diff-summary", "the user wants a commit or PR message"),
    ),
    "glm-writing-plans": (
        ("plan-ready", "glm-dev-team", "the plan is assembled and the user wants it implemented"),
        ("design-missing", "glm-brainstorming", "there is no approved design to plan from"),
        ("bug", "glm-systematic-debugging", "the request is a failure, not a plan"),
    ),
    "glm-dev-team": (
        ("root-cause", "glm-systematic-debugging", "the cause is not obvious"),
        ("needs-plan", "glm-writing-plans", "the work needs a written plan before slices"),
        ("needs-design", "glm-brainstorming", "the approach is not settled"),
        ("audit", "glm-requirements-code-audit", "the user wants the result checked against a spec"),
        ("docs", "glm-doc-generator", "the user wants docs for the code that now exists"),
        ("commit-message", "glm-git-diff-summary", "the user wants a commit or PR message"),
    ),
    "glm-systematic-debugging": (
        ("fix-large", "glm-dev-team", "the root cause is known and the fix is multi-file work"),
        ("fix-needs-plan", "glm-writing-plans", "the fix needs a plan before code"),
        ("design", "glm-brainstorming", "the symptom is a design choice, not a defect"),
    ),
    "glm-requirements-code-audit": (
        ("fix-gaps", "glm-writing-plans", "the gaps need a plan before implementation"),
        ("implement-gaps", "glm-dev-team", "the user asked to implement the fix plan"),
        ("bug", "glm-systematic-debugging", "a requirement fails because of a defect"),
    ),
    "glm-doc-generator": (
        ("commit-message", "glm-git-diff-summary", "the user wants a commit message for the docs"),
        ("code-wrong", "glm-systematic-debugging", "the docs turned up a defect to investigate"),
    ),
    "glm-git-diff-summary": (
        ("bug", "glm-systematic-debugging", "the diff review found a regression to investigate"),
        ("implement", "glm-dev-team", "the user wants the reviewed changes built or fixed"),
    ),
}

GUARDS = (
    "GUARD cite: do not state a path, line, number, URL, version, or command result you did not see in a tool result this session. Label the rest unverified or delete it.",
    "GUARD batch: if you planned several independent tool calls and only 1 or 2 ran, re-issue the rest in one message. Do not continue one call per turn.",
    "GUARD approve: ok, sounds good, and a reply to a side question are not approval. Do not write code, a spec, or a plan the user has not explicitly approved when this skill requires approval.",
    "GUARD tests: do not edit a test, a gate, or an assertion so that wrong code passes.",
    "GUARD done: say done only when this skill's own script printed its success line. A confident summary is not evidence.",
    "GUARD last: the HANDOFF, STAY, STOP, NEXT, and GUARD lines are binding. Do not override them with a guess.",
)


def fold_ascii(text):
    text = text.replace("\u0111", "d").replace("\u0110", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower()


def opening_hits(text):
    """Skill names the request clearly belongs to, highest priority first.

    Empty means the brainstorming feature path: nothing more specific matched.
    Same decisions as the historical check.py route table.
    """
    folded = fold_ascii(text)
    feature = FEATURE_RE.search(folded)
    strong_debug = re.compile(
        r"\b(traceback|stack ?trace|stacktrace|failing tests?|tests? fails?|flaky|regression|bi loi)\b")
    bug_denied = re.search(r"\bno\b.{0,24}\bbugs?\b", folded) and not strong_debug.search(folded)
    hits = []
    for name, rx in ROUTE_RULES:
        if name in SUPPRESS_IF_FEATURE and feature:
            continue
        if name == "glm-systematic-debugging" and bug_denied:
            continue
        if rx.search(folded):
            hits.append(name)
    return hits


def chain_from(text, extra):
    found = []
    for match in FROM_RE.finditer(text or ""):
        for part in match.group(1).split(","):
            name = part.strip().lower()
            if name in SKILLS and name not in found:
                found.append(name)
    for part in extra or []:
        name = part.strip().lower()
        if name in SKILLS and name not in found:
            found.append(name)
    return found


def _with_self(chain, self_name):
    if self_name in chain:
        return list(chain)
    return list(chain) + [self_name]


def decide(text, self_name, seen=None):
    """Return (action, name, because, seen_out).

    action is stay, handoff, or stop. seen_out includes self and, on a
    handoff, the target.
    """
    if self_name not in SKILLS:
        return "stop", "usage", "unknown skill", []
    chain = list(seen or [])
    owned = _with_self(chain, self_name)
    hits = opening_hits(text)
    target = hits[0] if hits else None
    because = BECAUSE.get(target, "")
    folded = fold_ascii(text or "")

    # Dev-team already owns a fix. A bare failure still belongs to debugging.
    if (self_name == "glm-dev-team" and target == "glm-systematic-debugging"
            and FIX_RE.search(folded)):
        target = None
        because = ""

    if target is None and self_name in FEATURE_BOUNCE and FEATURE_RE.search(folded):
        target = "glm-brainstorming"
        because = BECAUSE["glm-brainstorming"]

    if target is None or target == self_name:
        return "stay", self_name, "this skill owns the request", owned

    if target in owned:
        return ("stay", self_name,
                "%s is already in this chain" % target, owned)

    if len(owned) >= MAX_CHAIN:
        return "stop", "cap", "three skills already ran in this task", owned

    return "handoff", target, because, owned + [target]


def exit_target(self_name, event):
    """Return (event, target, because) or None when the event is not legal."""
    for name, target, because in EXITS.get(self_name, ()):
        if name == event:
            return name, target, because
    return None


def exits_line(self_name):
    pairs = ["%s=%s" % (event, target) for event, target, _why in EXITS.get(self_name, ())]
    return "EXITS: " + (" ".join(pairs) if pairs else "none")


def read_hint(name):
    roots = (
        "~/.zcode/skills/%s/SKILL.md",
        ".zcode/skills/%s/SKILL.md",
        ".agents/skills/%s/SKILL.md",
        "~/.agents/skills/%s/SKILL.md",
    )
    paths = ", ".join(root % name for root in roots)
    return (
        "stop this skill. Read the first of these files that exists and follow it from the top: %s. "
        "Its rules replace this skill. On that skill's handoff command, stdin starts with the "
        "FROM-LINE printed below, then the user request. Show the user one line that contains $%s. "
        "Subagents do not load skills."
    ) % (paths, name)


def emit(action, name, because, seen, self_name):
    lines = []
    if action == "handoff":
        lines.append("HANDOFF %s" % name)
        lines.append("BECAUSE: %s" % because)
        lines.append("TELL: $%s" % name)
        lines.append("NEXT: %s" % read_hint(name))
    elif action == "stop":
        lines.append("STOP cap")
        lines.append("BECAUSE: %s" % because)
        lines.append("NEXT: three skills already ran. Finish in this skill or ask the user. Do not load another skill.")
    else:
        lines.append("STAY %s" % name)
        lines.append("BECAUSE: %s" % because)
        lines.append("NEXT: this skill owns the request. Continue its own procedure.")
    lines.append("FROM-LINE: From: %s" % ",".join(seen))
    lines.append("SEEN: %s" % ",".join(seen))
    lines.append(exits_line(self_name if action != "handoff" else name))
    lines.extend(GUARDS)
    lines.append("RESULT route action=%s name=%s" % (action, name))
    return lines


def cmd_route(args):
    if args.self not in SKILLS:
        print("RESULT route action=stop name=usage")
        return 2
    text = sys.stdin.read()
    extra = [p for p in (args.seen or "").split(",") if p]
    seen = chain_from(text, extra)
    action, name, because, seen_out = decide(text, args.self, seen)
    for line in emit(action, name, because, seen_out, args.self):
        print(line)
    return 0


def cmd_next(args):
    if args.self not in SKILLS:
        print("RESULT next action=stop name=usage")
        return 2
    text = sys.stdin.read()
    extra = [p for p in (args.seen or "").split(",") if p]
    seen = chain_from(text, extra)
    found = exit_target(args.self, args.event)
    if found is None:
        legal = " ".join(event for event, _target, _why in EXITS.get(args.self, ())) or "none"
        print("STAY %s" % args.self)
        print("BECAUSE: unknown event %s" % (args.event or ""))
        print("EVENTS: %s" % legal)
        print("NEXT: stay. Pick an event from EVENTS and run next again, or finish here.")
        print("FROM-LINE: From: %s" % ",".join(_with_self(seen, args.self)))
        print(exits_line(args.self))
        lines_guard = list(GUARDS)
        for line in lines_guard:
            print(line)
        print("RESULT next action=stay name=%s" % args.self)
        return 0
    _event, target, because = found
    # The event table picks the target. The chain can still refuse it.
    if target in _with_self(seen, args.self):
        action, name, because2, seen_out = (
            "stay", args.self, "%s is already in this chain" % target,
            _with_self(seen, args.self))
    elif len(_with_self(seen, args.self)) >= MAX_CHAIN:
        action, name, because2, seen_out = (
            "stop", "cap", "three skills already ran in this task",
            _with_self(seen, args.self))
    else:
        action, name, because2, seen_out = (
            "handoff", target, because, _with_self(seen, args.self) + [target])
    # Reuse the route wording, but mark the result as next.
    lines = emit(action, name, because2, seen_out, args.self)
    lines[-1] = "RESULT next action=%s name=%s" % (action, name)
    for line in lines:
        print(line)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="handoff.py")
    sub = parser.add_subparsers(dest="cmd")
    route = sub.add_parser("route")
    route.add_argument("--self", required=True)
    route.add_argument("--seen", default="")
    nxt = sub.add_parser("next")
    nxt.add_argument("--self", required=True)
    nxt.add_argument("--event", required=True)
    nxt.add_argument("--seen", default="")
    args = parser.parse_args(argv)
    if args.cmd == "route":
        return cmd_route(args)
    if args.cmd == "next":
        return cmd_next(args)
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
