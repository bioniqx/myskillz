#!/usr/bin/env python3
"""Route a glm-* skill to a sibling, or keep the work here.

GLM-5.3 drops rules that sit in the middle of a long skill file, follows the
last copy it saw, and treats a soft "ok" as approval. This script is the
binding copy: every skill runs it, and the printed NEXT and GUARD lines win
over the model's guess.

  handoff.py route --self NAME     stdin: the user request. Always exit 0.
  handoff.py next  --self NAME --event EVENT
                                   stdin ignored. Always exit 0.
  handoff.py call  --self NAME --to SKILL [--why TEXT]
                                   explicit hand-off inside the seven-skill ring.
  handoff.py agents                list borrowable agents and engine-only agents.
  handoff.py borrow --self NAME --agent AGENT
                                   AGENT: dispatch that subagent. HANDOFF: the
                                   agent needs its owner skill. Always exit 0.

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

# The seven skills that may call each other and borrow each other's agents.
# glm-idea-to-spec stays on route/next only.
RING = (
    "glm-brainstorming",
    "glm-dev-team",
    "glm-doc-generator",
    "glm-git-diff-summary",
    "glm-requirements-code-audit",
    "glm-systematic-debugging",
    "glm-writing-plans",
)

# Direct Agent dispatch. The agent file holds the rules. prompt is the user
# message, with [BRACKETS] for the caller to fill. write "none" means no file.
# agent, owner, write, job, prompt
BORROW = (
    ("glm-explorer", "glm-brainstorming", "none",
     "read-only code question in one repo slice",
     "Task: [ONE LINE]. Root: [ROOT]. Today: [DATE].\n"
     "Slice: [SLICE]. Siblings cover (stay out): [SIBLINGS].\n"
     "Question: [ONE precise question]"),
    ("glm-researcher", "glm-brainstorming", "none",
     "cited web evidence for one question",
     "Task: [ONE LINE]. Today: [DATE].\n"
     "Our stack and versions: [STACK].\n"
     "Angle: [ANGLE]. Sibling angles (skip): [SIBLINGS].\n"
     "Question: [ONE precise question]"),
    ("glm-drafter", "glm-brainstorming", "none",
     "one approach draft for one lens, no repo writes",
     "Lens: [ONE LENS].\n"
     "Facts: [cited facts only].\n"
     "Question: [draft one approach for this lens]"),
    ("glm-design-breaker", "glm-brainstorming", "none",
     "attack one option; counterexample or NO-BREAK",
     "Option: [option text].\n"
     "Facts: [fact ids and atoms].\n"
     "Question: break this option, or reply NO-BREAK"),
    ("glm-debug-worker", "glm-systematic-debugging", "none",
     "one hypothesis, one command, 12-line verdict, no edits",
     "Hypothesis: [ONE].\n"
     "Command: [exact command].\n"
     "FIX: n/a"),
    ("glm-investigator", "glm-dev-team", ".claude/dev-team/research/",
     "read-only survey or one root-cause angle",
     "Briefing: [PATH under .claude/dev-team/research/]. Read it first.\n"
     "Question: [ONE]. Angle: [ANGLE]. Sibling angles (stay out): [SIBLINGS].\n"
     "Report: [same directory]/[slug].md"),
    ("glm-spot-reviewer", "glm-dev-team", ".claude/dev-team/reviews/",
     "read-only correctness and security review of a diff",
     "Briefing: [PATH under .claude/dev-team/reviews/]. Read it first.\n"
     "It names the request, acceptance criteria, file scope, git diff command, "
     "test command, and the report path in that same directory."),
    ("glm-code-reviewer", "glm-dev-team", ".claude/dev-team/reviews/",
     "read-only full review of a diff against acceptance criteria",
     "Briefing: [PATH under .claude/dev-team/reviews/]. Read it first.\n"
     "It names the request, acceptance criteria, file scope, git diff command, "
     "test command, and the report path in that same directory."),
    ("glm-doc-writer", "glm-doc-generator", "the one markdown path in the prompt",
     "one markdown file from facts inlined in the prompt",
     "ROLE: Technical writer.\n"
     "GOAL: Write [PATH] - [TITLE] for [AUDIENCE].\n"
     "FACTS: [inlined facts]. SCOPE: [paths].\n"
     "Return exactly 5 lines: title, path, tier, todos, risk."),
    ("glm-doc-reviewer", "glm-doc-generator", "the one target markdown file",
     "fact-check one markdown file and fix it in place",
     "ROLE: Technical fact-checker with edit rights.\n"
     "TARGET: [PATH]. FACTS: [same slice]. CODE TO CHECK AGAINST: [paths].\n"
     "Return exactly 5 lines: path, verdict, fixes, unresolved, human."),
)

# These agents need the owner skill's engine. Dispatching them raw skips
# worktrees, claim, or script-built briefs. agent, owner, job
ENGINE = (
    ("glm-programmer-lite", "glm-dev-team",
     "one slice in a git worktree; devteam.py claims it"),
    ("glm-programmer-strong", "glm-dev-team",
     "a high-risk slice in a git worktree; devteam.py claims it"),
    ("glm-team-leader", "glm-dev-team",
     "planning writes plan.md through the dev-team engine"),
    ("glm-plan-task-writer", "glm-writing-plans",
     "plan_tool.py builds the writer brief"),
    ("glm-plan-task-writer-deep", "glm-writing-plans",
     "plan_tool.py builds the deep writer brief"),
    ("glm-plan-reviewer", "glm-writing-plans",
     "plan_tool.py builds the review brief"),
    ("glm-rca-investigator", "glm-requirements-code-audit",
     "audit.py builds the evidence batch"),
    ("glm-rca-verifier", "glm-requirements-code-audit",
     "audit.py builds the verifier batch"),
)

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


def one_line(text):
    text = " ".join((text or "").split())
    text = "".join(c for c in text if 32 <= ord(c) < 127)
    return text[:160]


def borrow_row(agent):
    for row in BORROW:
        if row[0] == agent:
            return row
    return None


def engine_row(agent):
    for row in ENGINE:
        if row[0] == agent:
            return row
    return None


def _ring_handoff(self_name, target, because, seen):
    """Explicit hand-off. Returns (action, name, because, seen_out)."""
    owned = _with_self(seen, self_name)
    if target == self_name or target in owned:
        why = ("%s is already in this chain" % target) if target != self_name else (
            "you are already running %s" % self_name)
        return "stay", self_name, why, owned
    if len(owned) >= MAX_CHAIN:
        return "stop", "cap", "three skills already ran in this task", owned
    return "handoff", target, because, owned + [target]


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


def _print_emit(action, name, because, seen_out, self_name, result_prefix):
    lines = emit(action, name, because, seen_out, self_name)
    lines[-1] = "RESULT %s action=%s name=%s" % (result_prefix, action, name)
    for line in lines:
        print(line)


def cmd_call(args):
    if args.self not in RING:
        print("RESULT call action=stop name=usage")
        return 2
    text = sys.stdin.read()
    extra = [p for p in (args.seen or "").split(",") if p]
    seen = chain_from(text, extra)
    if args.to not in RING:
        print("STAY %s" % args.self)
        print("BECAUSE: %s is outside the seven-skill ring" % (args.to or ""))
        print("RING: %s" % " ".join(RING))
        print("NEXT: pick a skill from RING and run call again, or finish here.")
        print("FROM-LINE: From: %s" % ",".join(_with_self(seen, args.self)))
        print(exits_line(args.self))
        for line in GUARDS:
            print(line)
        print("RESULT call action=stay name=%s" % args.self)
        return 0
    because = one_line(args.why) or "this skill needs that skill's procedure"
    action, name, because, seen_out = _ring_handoff(args.self, args.to, because, seen)
    _print_emit(action, name, because, seen_out, args.self, "call")
    return 0


def cmd_agents(_args):
    for agent, owner, write, job, _prompt in BORROW:
        print("BORROW %s owner=%s write=%s job=%s" % (agent, owner, write, job))
    for agent, owner, job in ENGINE:
        print("ENGINE %s owner=%s job=%s" % (agent, owner, job))
    print("NEXT: borrow --agent NAME prints the Agent prompt. "
          "An ENGINE row is a skill call, not an Agent call.")
    print("RESULT agents borrow=%d engine=%d" % (len(BORROW), len(ENGINE)))
    return 0


def cmd_borrow(args):
    if args.self not in RING:
        print("RESULT borrow action=stop name=usage")
        return 2
    brow = borrow_row(args.agent)
    erow = engine_row(args.agent)
    if brow is None and erow is None:
        names = " ".join([row[0] for row in BORROW] + [row[0] for row in ENGINE])
        print("STAY %s" % args.self)
        print("BECAUSE: unknown agent %s" % (args.agent or ""))
        print("AGENTS: %s" % names)
        print("NEXT: pick a name from AGENTS and run borrow again, or finish here.")
        print("RESULT borrow action=stay name=%s" % args.self)
        return 0
    owner = brow[1] if brow else erow[1]
    if owner == args.self:
        print("STAY %s" % args.self)
        print("BECAUSE: you own %s. Dispatch it with this skill's own procedure." % args.agent)
        print("NEXT: do not switch skills.")
        print("RESULT borrow action=stay name=%s" % args.self)
        return 0
    if brow:
        _agent, owner, write, job, prompt = brow
        print("AGENT %s" % _agent)
        print("OWNER %s" % owner)
        print("SUBAGENT_TYPE %s" % _agent)
        print("WRITE %s" % write)
        print("BECAUSE: %s" % job)
        print("PROMPT:")
        print(prompt)
        print("NEXT: one Agent call. subagent_type is SUBAGENT_TYPE. "
              "The user message is the PROMPT block with the brackets filled. "
              "Do not add a model parameter. Do not load the owner skill. "
              "If WRITE is not none, the caller writes only that path and names it in the prompt. "
              "Subagents do not load skills and do not borrow.")
        for line in GUARDS:
            print(line)
        print("RESULT borrow action=agent name=%s" % _agent)
        return 0
    text = sys.stdin.read()
    extra = [p for p in (args.seen or "").split(",") if p]
    seen = chain_from(text, extra)
    _agent, owner, job = erow
    action, name, because, seen_out = _ring_handoff(args.self, owner, job, seen)
    _print_emit(action, name, because, seen_out, args.self, "borrow")
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
    call = sub.add_parser("call")
    call.add_argument("--self", required=True)
    call.add_argument("--to", required=True)
    call.add_argument("--why", default="")
    call.add_argument("--seen", default="")
    sub.add_parser("agents")
    borrow = sub.add_parser("borrow")
    borrow.add_argument("--self", required=True)
    borrow.add_argument("--agent", required=True)
    borrow.add_argument("--seen", default="")
    args = parser.parse_args(argv)
    if args.cmd == "route":
        return cmd_route(args)
    if args.cmd == "next":
        return cmd_next(args)
    if args.cmd == "call":
        return cmd_call(args)
    if args.cmd == "agents":
        return cmd_agents(args)
    if args.cmd == "borrow":
        return cmd_borrow(args)
    parser.print_help(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
