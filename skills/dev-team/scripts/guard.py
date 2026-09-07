#!/usr/bin/env python3
"""dev-team hook guards (Claude Code hooks; JSON on stdin).

  guard.py edit     PreToolUse Edit|Write|MultiEdit|NotebookEdit  (programmer): footprint + frozen tests
  guard.py bash     PreToolUse Bash                               (programmer): no history rewriting / integration git
  guard.py stop     Stop → SubagentStop                           (programmer): RED committed, GREEN after RED, tree clean
  guard.py edit-ro  PreToolUse Edit|Write|...                     (reviewer/leader): writes only under .claude/dev-team/ or agent memory
  guard.py bash-ro  PreToolUse Bash                               (reviewer/leader): read-only shell

Fail-open by design: any internal error allows the action (the integrator re-checks at merge time).
Deny = JSON permissionDecision on stdout (exit 0). Stop-block = exit 2 with the reason on stderr.
"""
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs", "testing", "e2e", "integration_tests"}
TEST_FILE_PATTERNS = [
    "test_*.py", "*_test.py", "*_test.go", "*_test.rb", "*_spec.rb", "*.test.*", "*.spec.*",
    "*Test.java", "*Tests.java", "*Test.kt", "*Tests.kt", "*Test.cs", "*Tests.cs", "*Spec.scala",
    "*_test.rs", "*.t", "*_test.exs", "*Test.php", "*test.dart", "*_test.ts", "*_test.js",
]
MAX_STOP_BLOCKS = 2


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                             "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))
    sys.exit(0)


def allow():
    sys.exit(0)


def git(args, cwd, raw=False):
    r = subprocess.run(["git"] + args, cwd=cwd, text=True, capture_output=True)
    if r.returncode != 0:
        return ""
    return r.stdout.rstrip("\n") if raw else r.stdout.strip()


def porcelain(cwd):
    """[(xy, path)] from `git status --porcelain` (leading spaces are significant)."""
    return [(ln[:2], ln[3:]) for ln in git(["status", "--porcelain"], cwd, raw=True).splitlines() if len(ln) > 3]


def is_test_path(rel, extra_globs=()):
    rel = rel.replace("\\", "/")
    parts = rel.split("/")
    if any(p.lower() in TEST_DIR_NAMES for p in parts[:-1]):
        return True
    base = parts[-1]
    if any(fnmatch.fnmatch(base, pat) for pat in TEST_FILE_PATTERNS):
        return True
    return any(fnmatch.fnmatch(rel, g) for g in extra_globs)


def path_matches(rel, entry):
    rel = rel.replace("\\", "/").lstrip("./")
    entry = entry.replace("\\", "/").lstrip("./")
    if entry.endswith("/"):
        return rel.startswith(entry)
    if any(ch in entry for ch in "*?["):
        return fnmatch.fnmatch(rel, entry) or fnmatch.fnmatch(rel, entry + "/*")
    return rel == entry or rel.startswith(entry + "/")


def find_slice_root(start):
    p = Path(start).resolve()
    for _ in range(20):
        if (p / ".slice" / "id").exists():
            return p
        if p.parent == p:
            return None
        p = p.parent
    return None


def read_lines(p):
    try:
        return [ln for ln in Path(p).read_text().splitlines() if ln.strip()]
    except OSError:
        return []


def ensure_red_cache(wt, sd, sid, globs):
    """If commit-red wasn't used, discover the RED commit by subject and cache its frozen files."""
    if (sd / "red").exists():
        return
    log = git(["log", "--format=%H%x1f%s", "-n", "200"], wt)
    red = None
    for line in log.splitlines():
        h, _, subj = line.partition("\x1f")
        if subj.startswith(f"test({sid})"):
            red = h
    if red:
        files = git(["show", "--name-only", "--format=", red], wt).splitlines()
        frozen = [f for f in files if f and is_test_path(f, globs)]
        try:
            (sd / "red").write_text(red)
            (sd / "red_files").write_text("\n".join(frozen) + "\n")
        except OSError:
            pass


def tool_path(inp):
    ti = inp.get("tool_input") or {}
    return ti.get("file_path") or ti.get("notebook_path") or ti.get("path") or ""


# ----------------------------------------------------------------------------- programmer guards

def guard_edit(inp):
    path = tool_path(inp)
    if not path:
        allow()
    path = os.path.abspath(os.path.join(inp.get("cwd", ""), path)) if not os.path.isabs(path) else path
    wt = find_slice_root(os.path.dirname(path))
    own = find_slice_root(inp.get("cwd") or "")
    if wt is None:
        allow()  # not a claimed worktree (fail-open; native isolation still protects the main checkout)
    if own is not None and own != wt:
        deny(f"`{path}` belongs to another slice's worktree ({wt}); you may only edit inside your own worktree {own}.")
    sd = wt / ".slice"
    rel = os.path.relpath(path, wt).replace("\\", "/")
    if rel.startswith(".slice/") or rel == ".slice":
        deny("`.slice/` is dev-team metadata; never edit it.")
    fp = read_lines(sd / "footprint")
    if fp and not any(path_matches(rel, e) for e in fp):
        deny(f"`{rel}` is outside your slice footprint ({', '.join(fp)}). Other programmers may own it. "
             "Do not touch it: finish what you can inside the footprint and report `Status: Blocked` naming this file and why.")
    sid = read_lines(sd / "id")[0] if read_lines(sd / "id") else ""
    globs = read_lines(sd / "test_globs")
    ensure_red_cache(wt, sd, sid, globs)
    frozen = read_lines(sd / "red_files")
    if rel in frozen:
        deny(f"`{rel}` is a test committed in the RED commit and is FROZEN. Make the implementation satisfy it. "
             "If the test itself is wrong, report `Status: Blocked` explaining why — never edit it.")
    allow()


BASH_DENY = [
    (r"\bgit\s+(push|rebase|filter-branch|worktree|merge|stash|switch|cherry-pick|revert)\b", "integration/history commands are the Conductor's"),
    (r"\bgit\s+reset\s+(--hard|--merge|--soft)\b", "history rewriting is forbidden in a slice worktree"),
    (r"\bgit\s+branch\s+(-[dDmM]\b|--delete|--move|--force)", "branch surgery is forbidden in a slice worktree"),
    (r"\bgit\s+commit\b[^|;&]*--amend", "--amend would rewrite the RED audit trail; make a new commit"),
    (r"\bgit\s+(reflog\s+expire|update-ref|symbolic-ref|gc\s+--prune)\b", "history rewriting is forbidden"),
    (r"(^|[\s;&|])rm\s+-[a-zA-Z]*r[a-zA-Z]*\s+[^\s]*\.slice\b", "`.slice/` is dev-team metadata"),
    (r"(^|[\s;&|/])(sed\s+-i|tee|>>?)\s*[^\s]*\.slice/", "`.slice/` is dev-team metadata"),
]


def guard_bash(inp):
    cmd = (inp.get("tool_input") or {}).get("command", "") or ""
    for pat, why in BASH_DENY:
        if re.search(pat, cmd):
            deny(f"Blocked `{cmd[:80]}`: {why}. Use commit-red / commit-green for commits; the Conductor merges.")
    if re.search(r"\bgit\s+checkout\b", cmd) and not re.search(r"\bgit\s+checkout\b[^|;&]*\s--(\s|$)", cmd):
        deny("`git checkout <ref>` would leave your slice branch. Only `git checkout [<ref>] -- <file>` (restore a file) is allowed.")
    if re.search(r"\bgit\s+reset\b", cmd) and not re.search(r"\bgit\s+reset\b[^|;&]*\s--(\s|$)", cmd):
        deny("`git reset <ref>` would drop commits (the RED audit trail). Only `git reset -- <file>` (unstage) is allowed.")
    allow()


def guard_stop(inp):
    cwd = inp.get("cwd") or os.getcwd()
    wt = find_slice_root(cwd)
    if wt is None:
        allow()
    sd = wt / ".slice"
    last = inp.get("last_assistant_message") or ""
    if re.search(r"Status:\s*Blocked", last, re.I):
        allow()
    blocks_file = sd / "stop_blocks"
    blocks = int(read_lines(blocks_file)[0]) if read_lines(blocks_file) else 0
    if blocks >= MAX_STOP_BLOCKS:
        allow()  # never loop forever; the integrator re-checks everything at merge time
    sid = read_lines(sd / "id")[0]
    mode = (read_lines(sd / "mode") or ["slice"])[0]
    globs = read_lines(sd / "test_globs")
    fp = read_lines(sd / "footprint")
    problems = []
    status = [p for _, p in porcelain(wt) if not p.startswith(".slice")]
    if status:
        inside = [p for p in status if any(path_matches(p, e) for e in fp)]
        outside = [p for p in status if p not in inside]
        if inside:
            problems.append("uncommitted changes in your footprint: " + ", ".join(inside[:8]) +
                            (" → run `commit-red \"<title>\"` (tests) or `commit-green \"<title>\"` (implementation)"))
        if outside:
            problems.append("stray changes outside your footprint: " + ", ".join(outside[:8]) +
                            " → revert them (`git checkout -- <file>` / delete untracked) or report Status: Blocked naming them")
    ensure_red_cache(wt, sd, sid, globs)
    red = (read_lines(sd / "red") or [""])[0]
    head = git(["rev-parse", "HEAD"], wt)
    if not red:
        problems.append(f"no RED commit `test({sid}): RED — …` on this branch → write failing tests for every criterion, "
                        "run only them, then `commit-red \"<title>\"` BEFORE any implementation")
    else:
        frozen = read_lines(sd / "red_files")
        if frozen:
            changed = git(["diff", "--name-only", red, "HEAD", "--"] + frozen, wt)
            if changed:
                problems.append("frozen test files changed after RED: " + changed.replace("\n", ", ") +
                                " → restore them (`git checkout " + red[:9] + " -- <file>`) and commit; a wrong test = Status: Blocked")
        if mode in ("slice", "green") and head == red:
            problems.append("no implementation commit after the RED commit → implement the minimum to pass, run the gate, `commit-green \"<title>\"`")
    if not re.search(r"##\s*Status:", last):
        problems.append("your final message must use the report format from the briefing (## Slice / ## Status / ## Commits / ## Changes / ## Criteria / ## Gate / ## Notes)")
    if problems:
        try:
            blocks_file.write_text(str(blocks + 1))
        except OSError:
            pass
        sys.stderr.write("dev-team gate — you are not done yet:\n- " + "\n- ".join(problems) +
                         "\nIf something makes this impossible, end with `## Status: Blocked` and the exact reason.\n")
        sys.exit(2)
    allow()


# ----------------------------------------------------------------------------- read-only roles

RO_WRITE_ALLOW = ("/.claude/dev-team/", "/.claude/agent-memory/", "/.claude/agent-memory-local/")


def guard_edit_ro(inp):
    path = tool_path(inp)
    if not path:
        allow()
    norm = os.path.abspath(path).replace("\\", "/")
    if any(seg in norm for seg in RO_WRITE_ALLOW):
        allow()
    deny(f"This role is read-only. `{os.path.basename(path)}` is outside .claude/dev-team/ (reports/plans) and agent memory. "
         "Report findings; a programmer applies fixes.")


BASH_RO_DENY = [
    r"(^|[\s;&|])(rm|mv|cp|chmod|chown|mkdir|touch|truncate|dd|ln|rsync|tee|install)\b",
    r"\bsed\s+-[a-zA-Z]*i",
    r"\bperl\s+-[a-zA-Z]*i",
    r"(^|[^&<>])>{1,2}(?!\s*/dev/null\b|&)",
    r"\bgit\s+(add|commit|checkout|switch|reset|merge|rebase|push|pull|fetch|stash|clean|rm|mv|tag|apply|cherry-pick|revert|worktree|branch\s+-[dDmM]|filter-branch)\b",
    r"\b(npm|pnpm|yarn|bun)\s+(install|i|add|remove|uninstall|update|publish|link)\b",
    r"\b(pip|pip3|poetry|uv|conda|cargo|go|gem|composer)\s+(install|add|remove|uninstall|update|publish)\b",
    r"\bpython[0-9.]*\s+-c\s+.*open\([^)]*['\"][wa]",
]


def guard_bash_ro(inp):
    cmd = (inp.get("tool_input") or {}).get("command", "") or ""
    for pat in BASH_RO_DENY:
        if re.search(pat, cmd):
            deny(f"Read-only role: `{cmd[:80]}` looks like it modifies files/packages/git state. "
                 "Use Read/Grep/Glob, run tests/linters/diffs only, and report instead of changing anything.")
    allow()


def main():
    if len(sys.argv) < 2:
        allow()
    mode = sys.argv[1]
    try:
        inp = json.load(sys.stdin)
    except Exception:
        allow()
    try:
        {"edit": guard_edit, "bash": guard_bash, "stop": guard_stop,
         "edit-ro": guard_edit_ro, "bash-ro": guard_bash_ro}.get(mode, lambda i: allow())(inp)
    except SystemExit:
        raise
    except Exception:
        allow()  # fail-open


if __name__ == "__main__":
    main()
