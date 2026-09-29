#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
requirements-code-audit guard (Claude Code PreToolUse / SubagentStop hook).

Structural enforcement of the audit's non-negotiables while an audit is ACTIVE
(i.e. <project>/.audit/ACTIVE exists — created by `audit.py init`, removed by `audit.py finish`):

  Bash   deny git-history and git-mutating commands for everyone; deny write-ish shell for workers;
         auto-allow the skill's own `audit.py` so the lead is never interrupted by permission prompts.
  Write/Edit/MultiEdit/NotebookEdit
         allow inside the audit dir (no prompts), deny anywhere else (the audit never modifies the codebase).
  Read   deny `.git/` internals for everyone; deny prose documentation inside the repo for audit workers
         and for the lead (except the spec files and the audit dir).
  Grep/Glob
         deny searches rooted in `.git/`.
  SubagentStop
         record which batch finished (and whether it reported success) → straggler/failure detection.

Fail-open by design: any internal error exits 0 without a decision, so a bug here can never wedge a session.
"""
import json
import os
import re
import sys
from pathlib import Path

WORKER_SUFFIXES = ("rca-investigator", "rca-verifier", "rca-parser")
GIT_HISTORY = re.compile(
    r"\bgit\b(?:\s+-C\s+\S+)?(?:\s+--?\S+)*\s+(log|blame|show|reflog|shortlog|whatchanged|rev-list|describe|bisect|annotate|"
    r"cherry|range-diff|notes|tag|branch|for-each-ref|stash\s+(list|show))\b|"
    r"\bgit\b.*\bdiff\b.*(HEAD[~^]|@\{|(?<![\w/.-])[0-9a-f]{7,40}(?![\w/.-]))|"
    r"\bgh\s+(pr|issue|api|release|run|search)\b|\bglab\b|\btig\b", re.I)
GIT_MUTATE = re.compile(
    r"\bgit\b(?:\s+-C\s+\S+)?(?:\s+--?\S+)*\s+(commit|checkout|switch|reset|stash|rebase|merge|push|pull|fetch|clean|rm|mv|add|"
    r"restore|cherry-pick|revert|am|apply|worktree|submodule|filter-branch|gc|prune)\b", re.I)
WORKER_WRITEISH = re.compile(
    r"(^|[;&|]\s*)(rm|mv|cp|tee|dd|truncate|chmod|chown|touch|mkdir|ln|patch|sed\s+-i|perl\s+-i|npm|pnpm|yarn|pip3?|poetry|cargo|go\s+(build|run|generate|mod)|make|gradle|mvn|dotnet|bundle|composer)\b|"
    r"(?<![<>|&])>(?!&)|>>", re.I)
DOC_EXTS = r"md|mdx|markdown|rst|adoc|asciidoc|textile|org"
DOC_BASENAME_EXTS = DOC_EXTS + r"|txt"
DOC_BASENAME = re.compile(
    r"(^|/)(README|CHANGELOG|CHANGES|HISTORY|CONTRIBUTING|CODE_OF_CONDUCT|LICENSE|NOTICE)(\.(" + DOC_BASENAME_EXTS + r"))?$", re.I)
DOC_EXT = re.compile(r"\.(" + DOC_EXTS + r")$", re.I)
DOC_DIR = re.compile(r"(^|/)(docs?|documentation|wiki|adrs?|design[-_]docs?|rfcs?)(/|$)", re.I)
# .txt basenames that are build/dependency files, not prose, even inside a doc directory.
NON_DOC_TXT_BASENAMES = frozenset(("requirements.txt", "cmakelists.txt"))
# Commands that take a literal pattern/script argument rather than executing it: their whole
# quoted tokens (grep 'git log', grep -e '=>' -e x, awk 'NF > 100', sed 'p') get stripped
# entirely below so they don't look like git or writes.
PATTERN_CMD_RE = re.compile(r"^\s*(?:grep|egrep|fgrep|zgrep|zegrep|zfgrep|rg|ag|ack|awk|sed)\b")
# A single quoted token. Single quotes never support escaping or substitution in the shell;
# double quotes support backslash-escaping AND still run $(...)/`...` inside them.
TOKEN_QUOTE_RE = re.compile(r"\\.|'[^']*'|\"(?:[^\"\\]|\\.)*\"")   # leading \\. = escaped char outside quotes
SUBSHELL_IN_QUOTE_RE = re.compile(r"\$\(|`")
# awk/sed scripts that execute or write, not just match: they must stay visible to the scans.
AWK_LIVE_RE = re.compile(r"\bsystem\s*\(|\bgetline\b|\bprintf?\b[^;}]*(?:>|(?<!\|)\|(?!\|))|(?<!\|)\|(?!\|)\s*\"")
SED_LIVE_RE = re.compile(r"(?:^|[\s;{}!\d$])[wWe](?:\s|$)|/[gpiI\d]*[wWe](?:\s|$)|(?:^|[;{}!\d$])[wWe]\s*\S|"
                         r"\bs(.)(?:(?!\1).)*\1(?:(?!\1).)*\1[gpiI\d]*[wWe]\S")
AWK_CMD_RE = re.compile(r"^\s*awk\b")
SED_CMD_RE = re.compile(r"^\s*sed\b")
# Everything else: drop the quote *characters* but keep the content, so a real command hidden
# behind quoting (`bash -c 'git log -p'`, `git 'log' -p`, `"git" log -p`) is still detected.
QUOTE_CHARS_RE = re.compile(r"\\.|'([^']*)'|\"((?:[^\"\\]|\\.)*)\"")
SAFE_REDIRECT_RE = re.compile(r"[012]?>>?\s*/dev/null\b", re.I)
CHAIN_RE = re.compile(r"[;&|<>`\n]|\$\(")


def is_doc_path(p):
    """True when p is prose documentation, not source code that merely resembles one."""
    pp = p.replace("\\", "/")
    if DOC_BASENAME.search(pp):
        return True
    if DOC_EXT.search(pp):
        return True
    if DOC_DIR.search(pp):
        name = pp.rsplit("/", 1)[-1]
        if "." not in name:
            return True
        if name.lower().endswith(".txt") and name.lower() not in NON_DOC_TXT_BASENAMES:
            return True
    return False


def _split_top_level(cmd):
    """Split cmd into (segment, following-separator) pairs on unquoted ; & | newline."""
    parts = []
    buf = []
    quote = None
    i, n = 0, len(cmd)
    while i < n:
        c = cmd[i]
        if quote:
            buf.append(c)
            if quote == '"' and c == "\\" and i + 1 < n:
                buf.append(cmd[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(cmd[i:i + 2])
            i += 2
            continue
        if c in "'\"":
            quote = c
            buf.append(c)
            i += 1
            continue
        if c in ";&|\n":
            parts.append(("".join(buf), c))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    parts.append(("".join(buf), ""))
    return parts


def _strip_pattern_cmd_quotes(segment):
    """Within a command segment that starts with grep/awk/sed & co, drop each quoted token
    entirely (it's a literal pattern/script, not code) UNLESS it's a double-quoted token that
    still hides a live $(...)/`...` substitution the shell would actually execute."""
    if not PATTERN_CMD_RE.match(segment):
        return segment

    live = AWK_LIVE_RE if AWK_CMD_RE.match(segment) else SED_LIVE_RE if SED_CMD_RE.match(segment) else None

    def repl(m):
        s = m.group(0)
        if s[0] == "\\":
            return s
        if s[0] == '"' and SUBSHELL_IN_QUOTE_RE.search(s[1:-1]):
            return s
        if live and live.search(s[1:-1]):
            if live is SED_LIVE_RE:   # split glued commands ('1egit log') so the scans see them
                s = re.sub(r"(?<=[wWe])(?=(?:git|gh|glab|tig)\b)", " ", s, flags=re.I)
            return s + " >"   # keep the script visible; ' >' also flags it as a write for workers
        return " "

    return TOKEN_QUOTE_RE.sub(repl, segment)


def scan_text(cmd):
    """Quote-aware normalisation before pattern-matching a command: drop pattern-taking
    commands' quoted tokens (grep 'git log', grep '=>', awk 'NF > 100') and safe (/dev/null)
    redirects entirely, but only remove the *quote characters* elsewhere so a real command
    hidden behind quoting (bash -c 'git log -p', git 'log' -p, "git" log -p) is still visible."""
    segments = _split_top_level(cmd)
    t = "".join(_strip_pattern_cmd_quotes(seg) + sep for seg, sep in segments)
    t = QUOTE_CHARS_RE.sub(
        lambda m: m.group(0) if m.group(0)[0] == "\\" else m.group(1) if m.group(1) is not None else m.group(2), t)
    t = SAFE_REDIRECT_RE.sub(" ", t)
    return t


def out(decision, reason=None, extra=None):
    o = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": decision}}
    if reason:
        o["hookSpecificOutput"]["permissionDecisionReason"] = reason
    if extra:
        o["hookSpecificOutput"].update(extra)
    sys.stdout.write(json.dumps(o))
    sys.exit(0)


def allow(reason=None):
    out("allow", reason)


def deny(reason):
    out("deny", reason)


def under(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except Exception:
        return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    cfg_path = Path(root) / ".audit" / "config.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not cfg.get("active"):
        return
    out_dir = cfg.get("out_dir") or str(Path(root) / ".audit")
    repo = cfg.get("repo_root") or root
    specs = [str(Path(s).resolve()) for s in cfg.get("spec_files", [])]
    scripts_dir = cfg.get("scripts_dir", "")
    event = data.get("hook_event_name", "")
    agent_type = (data.get("agent_type") or "").lower()
    is_worker = agent_type.endswith(WORKER_SUFFIXES)
    is_subagent = bool(data.get("agent_id"))
    cwd = data.get("cwd") or root

    if event == "SubagentStop":
        msg = str(data.get("last_assistant_message") or "")
        m = re.search(r"\b(batch-V?\d+(?:-r\d+)?|section-\d+)\b", msg)
        if m:
            name = m.group(1)
            ok = bool(re.search(r"\bdone\b", msg, re.I)) and not re.search(r"\b(partial|failed|could not|unable|error)\b", msg, re.I)
            edir = Path(out_dir) / "events"
            edir.mkdir(parents=True, exist_ok=True)
            (edir / (name + ".json")).write_text(json.dumps({"batch": name, "ok": ok, "agent_type": agent_type,
                                                              "agent_id": data.get("agent_id"), "msg": msg[:300]}), encoding="utf-8")
        return

    if event != "PreToolUse":
        return
    tool = data.get("tool_name", "")
    ti = data.get("tool_input") or {}

    if tool == "Bash":
        cmd = str(ti.get("command") or "")
        scan = scan_text(cmd)
        if GIT_HISTORY.search(scan):
            deny("requirements-code-audit: git history / PR history is off-limits — the requirements document is the only source of truth. "
                 "Use Grep/Glob/Read on the working tree instead.")
        if GIT_MUTATE.search(scan):
            deny("requirements-code-audit: the audit must not change git state. Finish the audit first (`audit.py finish`).")
        if scripts_dir:
            m = re.match(r"^\s*(python3?|py)\s+\"?" + re.escape(scripts_dir), cmd)
            if m and not CHAIN_RE.search(cmd[m.end():]):
                allow("bundled audit script")
        if is_subagent and WORKER_WRITEISH.search(scan) and out_dir not in cmd:
            deny("requirements-code-audit: workers are read-only; write only your findings file (use the Write tool) inside " + out_dir)
        return

    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        p = ti.get("file_path") or ti.get("notebook_path") or ""
        if p and not Path(p).is_absolute():
            p = str(Path(cwd) / p)
        if p and under(p, out_dir):
            allow("audit output")
        deny("requirements-code-audit: an audit is active and must not modify the codebase. Only files under %s may be written. "
             "If the user explicitly asked for code changes, run `audit.py finish` first." % out_dir)

    if tool == "Read":
        p = ti.get("file_path") or ""
        if p and not Path(p).is_absolute():
            p = str(Path(cwd) / p)
        if not p or under(p, out_dir):
            return
        parts = Path(p).parts
        if ".git" in parts:
            deny("requirements-code-audit: `.git/` internals are git history — off-limits during the audit.")
        rp = str(Path(p).resolve())
        if rp in specs or ".claude" in parts or (scripts_dir and under(p, Path(scripts_dir).parent)):
            return   # the spec itself, Claude config/skills/plugins, or this skill's own reference files
        if under(p, repo) and is_doc_path(p):
            who = "workers" if is_worker else "this audit"
            deny("requirements-code-audit: prose documentation is not a source of truth for %s (only the requirements file is). "
                 "Read source, tests, schemas, migrations and config instead. If this file IS part of the spec: `audit.py spec --add %s`." % (who, p))
        return

    if tool in ("Grep", "Glob"):
        p = ti.get("path") or ""
        if p and ".git" in Path(p).parts:
            deny("requirements-code-audit: searching `.git/` is git history — off-limits during the audit.")
        return


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # fail open
        sys.exit(0)
