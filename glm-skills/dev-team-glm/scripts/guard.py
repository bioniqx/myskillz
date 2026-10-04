#!/usr/bin/env python3
"""dev-team hook guards (Claude Code hooks; JSON on stdin).

  guard.py edit     PreToolUse Edit|Write|NotebookEdit  (programmer): footprint + frozen tests; a kind:refactor
                    slice may not touch ANY test file. A write that passes every check is returned as an
                    explicit `allow`, so it never prompts (the programmer runs in `dontAsk` mode).
  guard.py bash     PreToolUse Bash                     (programmer): deny history rewriting / integration git /
                    writes to `.slice/`; then `allow` the commands the briefing pinned (`.slice/allow`),
                    read-only git, the project toolchain, footprint-scoped file ops and simple pipelines
                    of those. Anything else is left to the normal flow (denied in dontAsk, classified in
                    auto mode) — a background agent must never wait on a prompt nobody will answer.
  guard.py stop     Stop → SubagentStop                 (programmer): RED committed, GREEN after RED, tree clean,
                    real evidence under `## Gate:` for evidence-gated kinds. When the gate passes it writes a
                    `<root>/.claude/dev-team/slices/<id>.done` marker (or `.blocked`), which is how `devteam
                    next` finds finished programmers without the Conductor relaying ids.
  guard.py edit-ro  PreToolUse Edit|Write|NotebookEdit  (reviewer/leader/investigator): writes only under
                    reviews/, research/, agent memory — and plan.md for the team-leader.
  guard.py bash-ro  PreToolUse Bash                     (reviewer/leader/investigator): read-only shell; the plan's
                    test/lint commands are `allow`ed so a reviewer can gather evidence without a prompt.
  guard.py perm     PermissionRequest (settings.json only, optional): same allow-list as `bash`, in the
                    PermissionRequest output schema. Not needed when the PreToolUse hooks are installed.
  guard.py oc       OpenCode plugin bridge: {"tool", "args", "cwd", "role"} on stdin. edit/write/multiedit/
                    patch map to tool_input.file_path, bash to tool_input.command. Role programmer ->
                    edit/bash, any other role -> edit-ro/bash-ro with agent_type = role, no role -> silent
                    allow.

Fail-open by design: any internal error allows the action (the integrator re-checks at merge time).
Deny/allow = JSON on stdout (exit 0). Stop-block = exit 2 with the reason on stderr.
"""
import fnmatch
import io
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

TEST_DIR_NAMES = {"test", "tests", "__tests__", "spec", "specs", "testing", "e2e", "integration_tests"}
TEST_FILE_PATTERNS = [
    "test_*.py", "*_test.py", "*_test.go", "*_test.rb", "*_spec.rb", "*.test.*", "*.spec.*",
    "*Test.java", "*Tests.java", "*Test.kt", "*Tests.kt", "*Test.cs", "*Tests.cs", "*Spec.scala",
    "*_test.rs", "*.t", "*_test.exs", "*Test.php", "*test.dart", "*_test.ts", "*_test.js",
]
MAX_STOP_BLOCKS = 2
STATE_DIRNAME = ".claude/dev-team"


def deny_json(reason):
    """The hookSpecificOutput JSON for a deny, without exiting — `deny()` prints-and-exits with it;
    `guard_oc` also needs it as a string to compare across candidate paths before choosing one."""
    return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                              "permissionDecision": "deny",
                                              "permissionDecisionReason": reason}})


def deny(reason):
    print(deny_json(reason))
    sys.exit(0)


def allow(reason=None):
    """Silent exit = normal permission flow. With a reason = explicit pre-approval: no prompt, no
    classifier round-trip, and no auto-deny under `permissionMode: dontAsk`."""
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "permissionDecision": "allow",
                                                 "permissionDecisionReason": reason}}))
    sys.exit(0)


def git(args, cwd, raw=False):
    r = subprocess.run(["git"] + args, cwd=cwd, text=True, capture_output=True)
    if r.returncode != 0:
        return ""
    return r.stdout.rstrip("\n") if raw else r.stdout.strip()


def porcelain(cwd):
    """[(xy, path)] from `git status --porcelain` (leading spaces are significant). A rename is
    `R  old -> new`: both halves are real paths, so split them rather than reporting one bogus path."""
    out_ = []
    for ln in git(["status", "--porcelain"], cwd, raw=True).splitlines():
        if len(ln) <= 3:
            continue
        xy, path = ln[:2], ln[3:]
        if xy and xy[0] in ("R", "C") and " -> " in path:
            a, _, b = path.partition(" -> ")
            out_ += [(xy, a.strip('"')), (xy, b.strip('"'))]
        else:
            out_.append((xy, path.strip('"')))
    return out_


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
    rel = rel.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    entry = entry.replace("\\", "/")
    while entry.startswith("./"):
        entry = entry[2:]
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
    # Only this slice's own commits: an older run may have reused the same slice id.
    base = (read_lines(sd / "base") or [""])[0]
    rng = [f"{base}..HEAD"] if base else ["-n", "200"]
    log = git(["log", "--format=%H%x1f%s", *rng], wt)
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
    path = os.path.realpath(path)  # a symlinked worktree/project dir must resolve to the same real path
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
    kind = (read_lines(sd / "kind") or ["code"])[0]
    globs0 = read_lines(sd / "test_globs")
    if kind == "refactor" and is_test_path(rel, globs0):
        deny(f"`{rel}` is a test file and this is a REFACTOR slice: behaviour must not change, and the tests "
             "are the proof. Never create, edit or delete a test here. If a test must change, that is a code "
             "change, not a refactor — report `Status: Blocked` with the reason.")
    fp = read_lines(sd / "footprint")
    if fp and not any(path_matches(rel, e) for e in fp):
        deny(f"`{rel}` is outside your slice footprint ({', '.join(fp)}). Other programmers may own it. "
             "Do not touch it: finish what you can inside the footprint and report `Status: Blocked` naming this file and why.")
    sid = read_lines(sd / "id")[0] if read_lines(sd / "id") else ""
    globs = read_lines(sd / "test_globs")
    mode = (read_lines(sd / "mode") or ["slice"])[0]
    # RED/WORK/FAST never have a frozen-RED-commit to discover before their one commit exists, so
    # probing for it on every Edit would spawn `git log` for nothing; the Stop gate checks once, later.
    if mode not in ("red", "work", "fast"):
        ensure_red_cache(wt, sd, sid, globs)
    frozen = read_lines(sd / "red_files")
    if rel in frozen:
        deny(f"`{rel}` is a test committed in the RED commit and is FROZEN. Make the implementation satisfy it. "
             "If the test itself is wrong, report `Status: Blocked` explaining why — never edit it.")
    # Every check passed: pre-approve so the write never prompts (dontAsk would otherwise auto-deny it).
    allow(f"dev-team: `{rel}` is inside the slice footprint" if fp else None)


GIT_GLOBAL_OPT = re.compile(
    r"\bgit\s+((?:-C\s+\S+|--git-dir(?:=|\s+)\S+|--work-tree(?:=|\s+)\S+|-c\s+\S+|--no-pager|-P|"
    r"--exec-path(?:=\S*)?|--namespace(?:=|\s+)\S+)\s+)+")


def normalize_git(cmd):
    """`git -C ../repo merge x` and `git --git-dir=../.git push` both aim git at ANOTHER checkout.
    Collapse those global options away so the verb rules below actually see the verb, and keep a
    marker so redirecting git out of this worktree can be refused outright."""
    redirected = bool(re.search(r"\bgit\s+(-C\s|--git-dir|--work-tree|--namespace)", cmd)) or \
        bool(re.search(r"\b(GIT_DIR|GIT_WORK_TREE)\s*=", cmd))
    return GIT_GLOBAL_OPT.sub("git ", cmd), redirected


_QUOTED_RE = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")

_UNWRAP_BEFORE_RE = re.compile(r"(?:>>?|\b(?:bash|sh|zsh|dash)\s+(?:-\w+\s+)*-\w*c|\beval)\s*$")


def strip_quoted(cmd, meta=False):
    """Drop single/double-quoted spans so a `>` or `->` inside a quoted argument (a grep pattern,
    a --format string) is never mistaken for a shell metacharacter or a redirect. Two exceptions:
    a double-quoted span holding `$` or a backtick is kept for the metachar scan (`"$(cmd)"` still
    substitutes), and for the deny scan the payload of `sh -c`/`eval` and a redirect target is
    unwrapped (`bash -c "git push"`, `> ".slice/red"` are what they look like)."""
    def repl(m):
        s = m.group(0)
        if meta:
            return s if s[0] == '"' and ("$" in s or "`" in s) else ""
        if _UNWRAP_BEFORE_RE.search(cmd[:m.start()]):
            return " " + s[1:-1] + " "
        return s if s[0] == '"' and ("$(" in s or "`" in s) else ""
    return _QUOTED_RE.sub(repl, cmd)


def strip_for_scan(cmd):
    """`cmd`, with quoted spans and safe stderr/stdout-to-null redirects removed, for running the
    BASH_DENY/BASH_RO_DENY regexes over, so `cat .slice/base 2>/dev/null` or `git log
    --format='%h -> %s'` aren't mistaken for a write just because a `>` appears somewhere in them."""
    cmd = strip_quoted(cmd)
    for r in SAFE_REDIRECTS:
        cmd = cmd.replace(r, " ")
    return cmd


BASH_DENY = [
    (r"\bgit\s+(push|rebase|filter-branch|switch|cherry-pick|revert)\b", "integration/history commands are the Conductor's"),
    (r"\bgit\s+merge\b(?!-)", "integration/history commands are the Conductor's"),
    (r"\bgit\s+worktree\b(?!\s+list\b)", "integration/history commands are the Conductor's"),
    (r"\bgit\s+stash\b(?!\s+(list|show)\b)", "integration/history commands are the Conductor's"),
    (r"\bgit\s+reset\s+(--hard|--merge|--soft)\b", "history rewriting is forbidden in a slice worktree"),
    (r"\bgit\s+branch\s+(-[dDmM]\b|--delete|--move|--force)", "branch surgery is forbidden in a slice worktree"),
    (r"\bgit\s+commit\b[^|;&]*--amend", "--amend would rewrite the RED audit trail; make a new commit"),
    (r"\bgit\s+(reflog\s+expire|update-ref|symbolic-ref|gc\s+--prune)\b", "history rewriting is forbidden"),
    (r"(^|[\s;&|])rm\s+-[a-zA-Z]*r[a-zA-Z]*\s+[^\s]*\.slice\b", "`.slice/` is dev-team metadata"),
    (r"(^|[\s;&|/])(sed\s+-i|tee|>>?)\s*[^\s]*\.slice/", "`.slice/` is dev-team metadata"),
    # any write-shaped mention of .slice/ at all: it is the record the integrator and the Stop gate
    # read, so an agent that can rewrite it can claim a RED commit it never made
    (r"\.slice/(red|red_files|base|mode|kind|footprint|allow|id|notest|criteria|root)\b[^\n]*"
     r"(>|>>|\bwrite(?:_text|_bytes)?\b|\bopen\s*\(|\bmv\b|\bcp\b|\brm\b)", "`.slice/` is dev-team metadata"),
    (r"(>|>>|\bmv\b|\bcp\b|\btee\b|\bwrite(?:_text|_bytes)?\s*\()[^\n]*\.slice/", "`.slice/` is dev-team metadata"),
    # the done/blocked markers are how `next` finds finished lanes: only the Stop gate writes them
    (r"(>|>>|\bmv\b|\bcp\b|\btee\b|\btouch\b|\bwrite(?:_text|_bytes)?\s*\()[^\n]*\.claude/dev-team/", "`.claude/dev-team/` is the Conductor's run state"),
    (r"\.claude/dev-team/[^\n]*\bwrite(?:_text|_bytes)?\s*\(", "`.claude/dev-team/` is the Conductor's run state"),
    (r"\bopen\s*\(\s*['\"][^'\"]*\.claude/dev-team/[^'\"]*['\"]\s*,\s*['\"][wax+]", "`.claude/dev-team/` is the Conductor's run state"),
    (r"\bopen\s*\(\s*['\"][^'\"]*\.slice/[^'\"]*['\"]\s*,\s*['\"][wax+]", "`.slice/` is dev-team metadata"),
]


# Only patterns naming dev-team metadata run over the quote-KEPT command (`python3 -c "open('.slice/x','w')"`
# must match); git/history verbs run over strip_for_scan so `grep "git push"` is not a push.
def _is_meta_pat(pat):
    return ".slice" in pat or ".claude/dev-team" in pat


DEVTEAM_LANE_SUBS = {"claim", "commit-red", "commit-green", "commit-work", "commit-fast"}

_PY_INTERPRETER_RE = re.compile(r"^python[0-9.]*$")


def _is_devteam_script(tok):
    return tok.replace("\\", "/").rstrip("/").split("/")[-1] == "devteam.py"


def devteam_subcommand(cmd):
    """If `cmd` actually EXECUTES .../devteam.py (directly, or via a python interpreter, optionally
    with interpreter flags like `-B`), its subcommand; else None. `devteam.py` appearing only as a
    plain ARGUMENT to some other program (`grep ... scripts/devteam.py`, `git diff -- .../devteam.py`,
    `wc -l .../devteam.py`) must never be mistaken for invoking the engine. Only a simple (non-piped,
    non-shell-meta) command is inspected."""
    argv = argv_of(cmd)
    if not argv:
        return None
    argv = strip_env_prefix(argv)
    if not argv:
        return None
    head, rest = argv[0], argv[1:]
    if _is_devteam_script(head):
        script_rest = rest
    elif _PY_INTERPRETER_RE.match(os.path.basename(head)):
        i = 0
        while i < len(rest) and rest[i].startswith("-"):
            i += 1
        if i >= len(rest) or not _is_devteam_script(rest[i]):
            return None
        script_rest = rest[i + 1:]
    else:
        return None
    return next((x for x in script_rest if not x.startswith("-")), "")


_WRAPPERS = {"timeout", "env", "nice", "nohup", "time", "command", "exec", "sudo", "ionice", "stdbuf", "setsid"}


def wrapped_engine_subcommand(cmd):
    """The devteam.py subcommand run by ANY segment of a compound command (`;`, `&&`, `||`, `|`,
    newline) or behind wrappers like `timeout 600` / `env` / `nice`: the first one that is NOT a lane
    helper if there is one, else the first found, else None. Deny-side only."""
    segs = []
    # an unquoted newline separates commands; a quoted one (multi-line -m message) must not split
    flat, q, esc = [], "", False
    for ch in cmd:
        if esc:
            esc = False
        elif ch == "\\" and q != "'":
            esc = True
        elif q:
            q = "" if ch == q else q
        elif ch in "'\"":
            q = ch
        elif ch == "\n":
            ch = " ; "
        flat.append(ch)
    for line in (cmd.split("\n") if q else ["".join(flat)]):
        try:
            lex = shlex.shlex(line, posix=True, punctuation_chars=True)
            lex.whitespace_split = True
            toks = list(lex)
        except ValueError:
            continue
        cur = []
        for t in toks:
            if t and all(c in ";&|()" for c in t):
                segs.append(cur)
                cur = []
            else:
                cur.append(t)
        segs.append(cur)
    found = []
    for seg in segs:
        for j, tok in enumerate(seg):
            if not all(re.fullmatch(r"[A-Za-z_]\w*=.*|-.*|\d+[smhd]?", p) or os.path.basename(p) in _WRAPPERS
                       for p in seg[:j]):
                break
            rest = seg[j + 1:]
            if _is_devteam_script(tok):
                found.append(next((x for x in rest if not x.startswith("-")), ""))
                break
            if _PY_INTERPRETER_RE.match(os.path.basename(tok)):
                k = 0
                while k < len(rest) and rest[k].startswith("-"):
                    k += 1
                if k < len(rest) and _is_devteam_script(rest[k]):
                    found.append(next((x for x in rest[k + 1:] if not x.startswith("-")), ""))
                    break
    return next((f for f in found if f not in DEVTEAM_LANE_SUBS), found[0] if found else None)


def guard_bash(inp):
    raw = (inp.get("tool_input") or {}).get("command", "") or ""
    sub = devteam_subcommand(raw)
    denied = sub if sub is not None else wrapped_engine_subcommand(raw)
    if denied is not None and denied not in DEVTEAM_LANE_SUBS:
        deny(f"`devteam.py {denied}` drives the engine (integrate/finish/reset/next/dispatch and everything "
             "else are the Conductor's); a lane may only run claim / commit-red / commit-green / "
             "commit-work / commit-fast.")
    if sub is not None:
        wt0 = find_slice_root(inp.get("cwd") or os.getcwd())
        pinned0 = read_lines(wt0 / ".slice" / "allow") if wt0 else []
        argv0 = argv_of(raw)
        match = prefix_match(argv0, pinned0) if argv0 else None
        allow(f"dev-team: pinned command from the briefing — {match}" if match else None)
    cmd, redirected = normalize_git(raw)
    if redirected:
        deny(f"Blocked `{raw[:80]}`: it points git at another checkout (`-C` / `--git-dir` / "
             "`--work-tree` / `GIT_DIR`). Every git command must act on YOUR worktree only.")
    scan = cmd      # quotes kept: `python3 -c "open('.slice/red','w')"` must still match; only safe redirects go
    for r in SAFE_REDIRECTS:
        scan = scan.replace(r, " ")
    scan_hist = strip_for_scan(cmd)
    for pat, why in BASH_DENY:
        if re.search(pat, scan if _is_meta_pat(pat) else scan_hist):
            deny(f"Blocked `{raw[:80]}`: {why}. Use commit-red / commit-green / commit-work for commits; "
                 "the Conductor merges.")
    if re.search(r"\bgit\s+checkout\b", scan_hist) and not re.search(r"\bgit\s+checkout\b[^|;&]*\s--(\s|$)", scan_hist):
        deny("`git checkout <ref>` would leave your slice branch. Only `git checkout [<ref>] -- <file>` (restore a file) is allowed.")
    if re.search(r"\bgit\s+reset\b", scan_hist) and not re.search(r"\bgit\s+reset\b[^|;&]*\s--(\s|$)", scan_hist):
        deny("`git reset <ref>` would drop commits (the RED audit trail). Only `git reset -- <file>` (unstage) is allowed.")
    wt = find_slice_root(inp.get("cwd") or os.getcwd())
    reason = bash_allow_reason(raw, wt, footprint=read_lines(wt / ".slice" / "footprint") if wt else [],
                               pinned=read_lines(wt / ".slice" / "allow") if wt else [])
    allow(reason)


# ----------------------------------------------------------------------------- the allow-list

ALLOW_GIT_READ = ("git status", "git diff", "git log", "git show", "git rev-parse", "git ls-files",
                  "git grep", "git blame", "git branch --list", "git stash list", "git describe",
                  "git merge-base", "git worktree list")
# Pure filters/readers: safe anywhere in a pipeline (they only read stdin/files and print).
FILTERS = {"tail", "head", "grep", "rg", "wc", "sort", "uniq", "cat", "cut", "tr", "awk", "jq",
           "tac", "nl", "column", "true", "false", "echo", "printf", "ls", "pwd", "diff",
           "find", "stat", "du", "which", "file", "basename", "dirname", "realpath", "sleep", "date",
           "printenv", "test", "seq"}
# `xargs`, `env`, `tee`, `less`/`more` (shell escapes), `docker`, `bash -c` and friends can launch
# anything or write anywhere: they are never pre-approved (normal flow decides). A "filter" that
# owns a write-to-file flag loses its approval as soon as that flag appears.
FILTER_WRITE_FLAGS = {
    "sort": re.compile(r"^(-o|--output)"),                                     # sort -o FILE / -oFILE
    "find": re.compile(r"^-(delete|exec\w*|ok\w*|fprint0?|fprintf|fls)$"),       # find writers/executors
    "awk": re.compile(r"^(-i|-f|--file|-e|--source|-v)"),                       # awk -f prog.awk can system()
    "grep": re.compile(r"^(-f|--file)"),                                        # reads patterns from a file: fine, but keep it simple
    "file": re.compile(r"^(-m|--magic-file|-f|--files-from)"),
}
# `-m <module>` targets that install, serve or write outside the tree
PY_MODULE_DENY = {"pip", "venv", "ensurepip", "http.server", "uv", "poetry", "pipx", "site"}
NODE_LOADER_FLAGS = {"--import", "--require", "-r", "--loader", "--experimental-loader", "-i", "--interactive"}
# Project toolchains: they run inside the worktree and are what every gate is made of. Subcommands
# that install, publish or touch a shared cache are excluded — 64 lanes share `node_modules` via a
# symlink, so a stray `npm install` in one lane would race every other.
TOOLCHAIN = {"node", "npx", "npm", "pnpm", "yarn", "bun", "deno", "tsc", "eslint", "prettier", "vitest",
             "jest", "mocha", "playwright", "cypress", "python", "python3", "pytest", "ruff", "mypy", "black",
             "flake8", "isort", "pyright", "poetry", "uv", "go", "gofmt", "golangci-lint", "cargo", "rustc",
             "rustfmt", "clippy-driver", "make", "cmake", "ctest", "ninja", "mvn", "gradle", "./gradlew",
             "./mvnw", "bundle", "rspec", "rubocop", "ruby", "rake", "dotnet", "swift", "xcodebuild",
             "mix", "elixir", "php", "phpunit", "composer", "gcc", "g++", "clang", "clang++", "javac", "java",
             "kotlinc", "dart", "flutter", "zig", "bash", "sh"}
PKG_MANAGER_DENY_SUB = {"install", "i", "add", "remove", "rm", "uninstall", "un", "update", "up", "upgrade",
                        "publish", "link", "unlink", "ci", "create", "init", "login", "logout", "dlx",
                        "download", "get", "fetch", "sync", "lock", "push", "pull", "deploy", "login"}
INTERPRETER_EVAL_FLAGS = {"-c", "-e", "-p", "--eval", "--print", "-E", "--exec"}
FS_OPS = {"mkdir", "touch", "cp", "mv", "rm", "chmod"}
SHELL_META = re.compile(r"[;&<>`$(){}\n\\]|\|\|")
SAFE_REDIRECTS = ("2>&1", "2>/dev/null", ">/dev/null", "> /dev/null", "</dev/null", "2> /dev/null", "&>/dev/null")


def argv_of(cmd):
    """The command's argv, or None when it is not a single simple command we can vouch for."""
    if SHELL_META.search(strip_quoted(cmd, meta=True)):
        return None
    try:
        parts = shlex.split(cmd)
    except ValueError:
        return None
    return parts or None


def strip_env_prefix(argv):
    i = 0
    while i < len(argv) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", argv[i]):
        i += 1
    return argv[i:]


def _canon_tok(tok):
    """Resolve an absolute path token to its real path (symlinks collapsed); leave anything else
    (a bare word, a relative path we have no cwd to resolve against) untouched."""
    if tok.startswith("/"):
        try:
            return os.path.realpath(tok)
        except OSError:
            return tok
    return tok


def canon_argv(argv):
    return [_canon_tok(a) for a in argv]


def prefix_match(argv, prefixes):
    """`argv` matches a pinned prefix even when one side spells a script path literally and the
    other through a symlink (canonical `.slice/allow` match); every other token must still match exactly."""
    cargv = canon_argv(argv)
    for pfx in prefixes:
        pargv = argv_of(pfx.strip())
        if not pargv or len(pargv) > len(argv):
            continue
        cpargv = canon_argv(pargv)
        if cargv[:len(cpargv)] == cpargv:
            return pfx.strip()
    return None


def inside_worktree(arg):
    """A relative path that cannot escape the worktree."""
    return not (arg.startswith("/") or arg.startswith("~") or arg.startswith("..") or "/../" in arg
                or arg.startswith("$"))


def path_args(argv):
    return [a for a in argv[1:] if not a.startswith("-")]


def _has(rest, *flags):
    """True when any argument is one of `flags` (a `--flag=value` form counts as `--flag`)."""
    return any(a.split("=", 1)[0] in flags for a in rest)


SED_WRITE_EXEC = re.compile(  # sed w/W FILE, e CMD, s///w FILE, s///e (a false match only costs the pre-approval)
    r"(?:^|[;{}\n/!,$0-9\s])\s*[wWe](?:\s|$|;|})"
    r"|s(.)(?:\\.|(?!\1).)*\1(?:\\.|(?!\1).)*\1[gpiImM0-9]*[we]"
    r"|\\([^\\\n])(?:\\.|(?!\2).)*\2[\s!]*[wWe](?:\s|$|;|})")  # \cREGEXc address, then w/W/e


def sed_scripts(argv):
    """The sed program texts of one sed argv, or None when a program comes from a file (`-f`)."""
    if "--sandbox" in argv:
        return []                # GNU sed rejects w/W/e/r in sandbox mode
    scripts, positional, i = [], [], 1
    while i < len(argv):
        a = argv[i]
        i += 1
        if a == "--":
            positional += argv[i:]
            break
        if a.startswith("--"):
            name, eq, val = a.partition("=")
            if name == "--file":
                return None
            if name == "--expression":
                if eq:
                    scripts.append(val)
                elif i < len(argv):
                    scripts.append(argv[i])
                    i += 1
            elif name == "--line-length" and not eq:
                i += 1
            continue
        if a.startswith("-") and len(a) > 1:
            for j, ch in enumerate(a[1:], start=1):
                if ch == "f":
                    return None
                if ch in ("e", "l"):
                    tail = a[j + 1:]
                    if ch == "e":
                        if tail:
                            scripts.append(tail)
                        elif i < len(argv):
                            scripts.append(argv[i])
                    if not tail and i < len(argv):
                        i += 1
                    break
            continue
        positional.append(a)
    if not scripts and positional:
        scripts.append(positional[0])
    return scripts


SHELLS = ("sh", "bash", "zsh", "dash", "ksh", "fish")


def command_strings(head, rest):
    """The shell lines a runner (`exec -c '…'`, `-c=…`, `--call …`) or a shell (`sh -c '…'`) runs."""
    out = []
    for i, a in enumerate(rest):
        if a == "--":
            break
        name, eq, val = a.partition("=")
        if eq and name in ("-c", "--call"):
            out.append(val)
        elif (a in ("-c", "--call") or (head in SHELLS and re.fullmatch(r"-[A-Za-z]*c", a))) and i + 1 < len(rest):
            out.append(rest[i + 1])
    # `$'a\tb'` reaches us as `$a\tb`: decode the ANSI-C escapes the shell would expand
    return [s[1:].encode("latin-1", "backslashreplace").decode("unicode_escape", "ignore")
            if s.startswith("$") else s for s in out]


def rewrites_files(head, rest):
    """True when a formatter/fixer call rewrites files in place instead of only checking them."""
    sub = next((a for a in rest if not a.startswith("-")), "")
    if head in ("npm", "pnpm", "yarn", "bun", "npx", "bunx", "pnpx") + SHELLS:
        # a command string is re-checked as the shell line it runs
        for s in command_strings(head, rest):
            if any(rewrites_files(os.path.basename(g[0]), g[1:]) for g in shell_segments(s)):
                return True
    if head in ("npm", "pnpm", "yarn", "bun"):
        # option values (`--cwd .`, `-C .`, `--filter a`) and runner verbs (`exec`, `x`, `workspace a`)
        # can sit before the bin, so any positional that starts a rewriting call counts
        return any(rewrites_files(os.path.basename(a), rest[i + 1:])
                   for i, a in enumerate(rest) if not a.startswith("-"))
    runners = ("npx", "bunx", "pnpx")
    if sub and (head in runners or (head in ("poetry", "uv", "bundle") and sub in ("run", "exec"))):
        tail = rest[rest.index(sub) + (0 if head in runners else 1):]
        inner = next((a for a in tail if not a.startswith("-")), "")
        return bool(inner) and rewrites_files(os.path.basename(inner), tail[tail.index(inner) + 1:])
    if head == "black":
        return not _has(rest, "--check", "--diff")
    if head == "isort":
        return not _has(rest, "--check-only", "--check", "-c", "--diff")
    if head == "ruff":
        return _has(rest, "--fix", "--fix-only") or (sub == "format" and not _has(rest, "--check", "--diff"))
    if head == "prettier":
        return _has(rest, "--write", "-w")
    if head == "gofmt":
        return _has(rest, "-w")
    if head == "go":
        return sub in ("fmt", "fix", "generate") or (sub == "mod" and _has(rest, "tidy", "edit", "vendor"))
    if head == "cargo":
        return (sub == "fix" or (sub == "fmt" and not _has(rest, "--check"))
                or (sub == "clippy" and _has(rest, "--fix")))
    if head == "rustfmt":
        return not _has(rest, "--check")
    if head == "eslint":
        return _has(rest, "--fix")
    if head == "rubocop":
        return _has(rest, "-a", "-A", "--autocorrect", "--autocorrect-all", "--auto-correct",
                    "--auto-correct-all", "-x", "--fix-layout")
    if head == "deno":
        return sub == "fmt" and not _has(rest, "--check")
    if head == "dotnet":
        return sub == "format" and not _has(rest, "--verify-no-changes")
    return False


def _has_long_flag(tok, full):
    """`--output`/`--out=F` both mean `--output=F`: getopt_long accepts any unambiguous prefix of a
    long option, so a 3+ char prefix of `full` (with or without `=value`) counts as that flag."""
    if not tok.startswith("--"):
        return False
    name = tok[2:].split("=", 1)[0]
    return len(name) >= 3 and full.startswith(name)


def _has_short_flag(tok, letter):
    """`letter` present anywhere in a bundled single-dash cluster (`-nOtouch` carries `-O`, `-uo`
    carries `-o`); short flags combine, and one taking an argument may have it glued on directly."""
    return tok.startswith("-") and not tok.startswith("--") and letter in tok[1:]


def write_capable(argv):
    """A command that LOOKS read-only but carries a flag/script that writes to an arbitrary file or
    runs an arbitrary program: `git show/diff/log --output(=)`, `git grep -O`/`--open...`
    (any unambiguous abbreviation or bundled short form), `sort -o`/`--output`/`--out`, a sed `w`
    command (with or without a space before the filename), awk `system`/`getline`/pipes/`-f`,
    `rg --pre`. Never pre-approved, pinned or not."""
    head, rest = argv[0], argv[1:]
    if head == "git":
        sub = rest[0] if rest else ""
        args = rest[1:]
        if sub in ("diff", "log", "show") and any(_has_long_flag(a, "output") for a in args):
            return True
        if sub == "grep" and any(_has_long_flag(a, "open-files-in-pager") or _has_short_flag(a, "O")
                                  for a in args):
            return True
    if head == "sort" and any(_has_long_flag(a, "output") or _has_short_flag(a, "o") for a in rest):
        return True
    if head == "sed":
        scripts, pos, i = [], [], 0
        while i < len(rest):
            a = rest[i]
            long_name = a[2:].split("=", 1)[0] if a.startswith("--") else ""
            if (long_name in ("fi", "fil", "file")) or (not a.startswith("--") and a.startswith("-") and "f" in a[1:]):
                return True
            if long_name and "expression".startswith(long_name):
                if "=" in a:
                    scripts.append(a.split("=", 1)[1])
                else:
                    i += 1
                    scripts.append(rest[i] if i < len(rest) else "")
            elif a.startswith("-") and not a.startswith("--") and "e" in a[1:]:
                glued = a[a.index("e", 1) + 1:]
                if glued:
                    scripts.append(glued)
                else:
                    i += 1
                    scripts.append(rest[i] if i < len(rest) else "")
            elif not a.startswith("-"):
                pos.append(a)
            i += 1
        if not scripts and pos:
            scripts = pos[:1]
        for s in scripts:
            # only a WHOLE, unambiguous plain `s/pat/rep/flags` (no backslash, no w/e flag) is just text
            if re.fullmatch(r"s([^\\\s\w;])(?:(?!\1)[^\\])*\1(?:(?!\1)[^\\])*\1[gpiImM0-9]*", s):
                continue
            if (re.search(r"(?<![a-zA-Z])[wW]\s*\S", s) or re.search(r"(?<![a-zA-Z])e(?![a-zA-Z])", s)
                    or re.search(r"s(.).*\1.*\1[a-zA-Z0-9]*e", s)
                    or re.search(r"\\([^\\\n])(?:\\.|(?!\1).)*\1[\s!]*[wWe](?:\s|$|;|})", s)):
                return True
    if head == "awk":
        prog, i = None, 0
        while i < len(rest) and prog is None:
            a = rest[i]
            if a in ("-f", "--file") or a.startswith(("-f", "--file=")):
                return True                      # program from a file: cannot be inspected
            if a.startswith("--") or a in ("-E", "-l", "-i", "-e"):
                return True                      # --assign/--include/-E/-l...: cannot be inspected
            if a in ("-v", "-F"):
                i += 1                           # skip the option's value
            elif not a.startswith("-"):
                prog = a
            i += 1
        if prog is not None and (re.search(r"system|getline|\|", prog)
                                 or re.search(r"\bprintf?\b[^;}]*>", prog)):
            return True
    if head == "rg" and any(a == "--pre" or a.startswith("--pre=") or a.startswith("--pre-glob") for a in rest):
        return True
    return False


def write_exec_form(argv, readonly=False):
    """Why one argv writes a file or runs another program although its command looks read-only
    (`git diff --output`, `git grep -O`, `rg --pre`, `uniq IN OUT`, sed `w`/`e`,
    `sort --compress-program`), or None."""
    argv = strip_env_prefix(argv)
    if not argv:
        return None
    if write_capable(argv):
        return "writes a file or runs another program (output flag, sed w/e, awk program, rg --pre)"
    head, rest = os.path.basename(argv[0]), argv[1:]
    sub = rest[0] if rest else ""
    if head == "git":
        if sub in ("diff", "log", "show", "whatchanged") and _has(rest, "--output"):
            return f"`git {sub} --output` writes a file"
        if sub == "grep" and any(a.startswith("--op") or re.match(r"-[A-Za-z0-9]*O", a) for a in rest):
            return "`git grep --open-files-in-pager` / `-O` runs a program"
    if head == "rg" and _has(rest, "--pre"):
        return "`rg --pre` runs a preprocessor program on every file"
    if head == "sort" and any(a.startswith("--com") or a.startswith("--o") or re.match(r"-[A-Za-z]*o", a)
                              for a in rest):
        return "`sort --compress-program` / `-o` runs a program or writes a file"
    if head == "uniq":
        pos, i = [], 0
        while i < len(rest):
            a = rest[i]
            i += 1
            if a in ("-f", "-s", "-w", "--skip-fields", "--skip-chars", "--check-chars"):
                i += 1
            elif a == "-" or not a.startswith("-"):
                pos.append(a)
        if len(pos) >= 2 and pos[1] != "-":
            return "`uniq INPUT OUTPUT` writes OUTPUT"
    if head == "sed":
        scripts = sed_scripts(argv)
        if scripts is None:
            return "`sed -f` runs a program file that cannot be checked here"
        if any(SED_WRITE_EXEC.search(s) for s in scripts):
            return "a sed `w`/`W`/`e` command or `s///w`/`s///e` flag writes a file or runs a command"
    if readonly and rewrites_files(head, rest):
        return (f"`{head}` rewrites files in place; a read-only role may run a formatter only in its "
                "check mode (`--check` / `--diff`)")
    return None


def shell_segments(cmd):
    """Each simple command of a shell line as an argv (split at ; & | && || and newlines, quotes respected)."""
    segs = []
    for line in cmd.split("\n"):
        lex = shlex.shlex(line, posix=True, punctuation_chars=";&|")
        lex.whitespace_split = True
        lex.commenters = ""
        cur = []
        try:
            for tok in lex:
                if tok and not tok.strip(";&|"):
                    segs.append(cur)
                    cur = []
                else:
                    cur.append(tok)
        except ValueError:
            pass
        segs.append(cur)
    return [s for s in segs if s]


def ro_forbidden_form(cmd):
    """The first write/exec form or rewriting formatter in any command of a shell line, or None."""
    for argv in shell_segments(cmd):
        why = write_exec_form(argv, readonly=True)
        if why:
            return why
    return None


def pm_positionals(argv):
    """Indexes of a package manager's positionals before `--`, skipping the values of
    `--filter` / `-C` / `--dir` / `--cwd`."""
    out, i = [], 1
    while i < len(argv) and argv[i] != "--":
        if argv[i] in ("--filter", "-C", "--dir", "--cwd"):
            i += 1
        elif not argv[i].startswith("-"):
            out.append(i)
        i += 1
    return out


RUNNER_FLAGS = ("--prefix", "-p", "--package", "-y", "--yes", "-c", "--call", "--dir", "-C", "--cwd",
                "--workspace", "-w", "--ws")


def runner_flag(arg):
    """True when `arg` is a runner-level flag (also `--flag=value` or an npm abbreviation like `--pref`)."""
    name = arg.split("=", 1)[0]
    return name in RUNNER_FLAGS or (name.startswith("--") and len(name) > 2
                                    and any(f.startswith(name) for f in RUNNER_FLAGS))


def location_escapes(argv):
    """True when a package manager's `--prefix` / `-C` / `--dir` / `--cwd` (before `--`) names a path outside
    the repo (absolute, `~`, a `..` segment) or one the shell expands (`$`, backticks)."""
    args = argv[1:argv.index("--")] if "--" in argv else argv[1:]
    for i, a in enumerate(args):
        name, eq, val = a.partition("=")
        if not (name == "-C" or (name.startswith("--") and len(name) > 2
                                 and any(f.startswith(name) for f in ("--prefix", "--dir", "--cwd")))):
            continue
        if not eq:
            val = args[i + 1] if i + 1 < len(args) else ""
        if val.startswith(("/", "~")) or ".." in val.split("/") or "$" in val or "`" in val:
            return True
    return False


def _sed_in_place(args):
    """sed edits in place via `-i[SUF]` anywhere in a short cluster (`-ni`, `-nI`) or any `--in-place`
    abbreviation; a cluster's `e`/`f` ends option parsing (the rest is its script/file)."""
    for a in args:
        if a.startswith("--"):
            if len(a) > 2 and "in-place".startswith(a[2:].split("=", 1)[0]):
                return True
        elif a.startswith("-"):
            for ch in a[1:]:
                if ch in "iI":
                    return True
                if ch in "ef":
                    break
    return False


def segment_allowed(argv,footprint, pinned, readonly=False, wt=None):
    """Why this single argv is pre-approved, or None."""
    if not argv:
        return None
    if write_exec_form(argv, readonly=readonly):
        return None          # writes a file or runs another program: never pre-approved, not even when pinned
    if prefix_match(argv, pinned):
        return "pinned command from the briefing"
    if prefix_match(argv, ALLOW_GIT_READ):
        return "read-only git"
    if strip_env_prefix(argv) != argv:
        return None          # PATH=./x pytest, PYTHONPATH=…, LD_PRELOAD=… — the env changes what runs
    head = argv[0]
    if head in FILTERS:
        pat = FILTER_WRITE_FLAGS.get(head)
        if pat and any(pat.search(a) for a in argv[1:]):
            return None
        return "read-only command"
    if head == "sed" and not _sed_in_place(argv[1:]):
        return "read-only command"
    if head in TOOLCHAIN:
        sub = next((a for a in argv[1:] if not a.startswith("-")), "")
        if any("://" in a for a in argv[1:]):
            return None          # nothing that names a URL is a local build/test step
        verb = 0
        if head in ("npm", "pnpm", "yarn", "bun"):
            if location_escapes(argv):
                return None      # `pnpm -C /tmp exec …`, `npm --prefix=../x test`: runs another project
            pos = pm_positionals(argv)
            sub = argv[pos[0]] if pos else ""
            if pos and argv[pos[0]] in ("exec", "x"):
                verb = pos[0]
            elif any(argv[i] in ("exec", "x") for i in pos):
                return None      # `npm --prefix /tmp exec …`: an option value hides the runner verb
        if head in ("npm", "pnpm", "yarn", "bun", "poetry", "uv", "cargo", "go", "bundle", "composer",
                    "mix", "dotnet", "flutter", "dart"):
            if not sub or sub in PKG_MANAGER_DENY_SUB:
                return None      # a bare `npm`/`yarn` is `install`; installs race the shared node_modules
        if head == "npx" or verb:
            # a runner fetches and runs anything not installed: approve only a bin that already exists
            # locally, and a toolchain bin only when the command it runs would be approved on its own.
            # Only a bare `--` may precede the bin, so an option value is never taken for it.
            tail = argv[verb + 1:] if verb else argv[1:]
            dashdash = tail[:1] == ["--"]
            if dashdash:
                tail = tail[1:]
            bin_ = tail[0] if tail else ""
            # without a `--` before the bin, the runner still parses its own flags up to a bare `--`
            after = [] if dashdash else tail[1:tail.index("--")] if "--" in tail else tail[1:]
            if not re.fullmatch(r"[A-Za-z0-9@._+-]+", bin_) or bin_ in (".", "..") or bin_.startswith("-") \
                    or any(runner_flag(a) for a in after):
                return None
            base = Path(wt) if wt else Path.cwd()
            if not (base / "node_modules" / ".bin" / bin_).exists():
                return None
            if bin_ in TOOLCHAIN and not segment_allowed(tail, footprint, pinned, readonly=readonly, wt=wt):
                return None
        if head == "deno" and (sub not in ("test", "lint", "fmt", "check", "task") or any(a.startswith("--allow") for a in argv[1:])):
            return None
        if head in ("python", "python3", "node", "ruby", "php", "bash", "sh", "elixir"):
            if readonly and head in ("python", "python3") and len(argv) >= 3 and \
                    (argv[1] == "devteam.py" or argv[1].endswith("/devteam.py")) and argv[2] in ("status", "probe"):
                return "dev-team engine status/probe (read-only)"
            if any(a in INTERPRETER_EVAL_FLAGS for a in argv[1:]):
                return None
            if any(a.endswith("devteam.py") or a.endswith("guard.py") for a in argv[1:]):
                return None      # the engine is pre-approved ONLY through the pinned slice helpers
            if head in ("python", "python3"):
                for i, a in enumerate(argv[1:-1], start=1):
                    if a == "-m" and argv[i + 1].split(".")[0] in PY_MODULE_DENY:
                        return None
                if any(a.startswith("-m") and len(a) > 2 and a[2:].split(".")[0] in PY_MODULE_DENY for a in argv[1:]):
                    return None
            if head == "node" and any(a in NODE_LOADER_FLAGS or a.startswith("--import=") or a.startswith("--require=")
                                      or a.startswith("--loader=") for a in argv[1:]):
                return None
            if head in ("bash", "sh"):
                target = next((a for a in argv[1:] if not a.startswith("-")), "")
                if not target or not inside_worktree(target) or not re.search(r"\.(sh|bash)$", target):
                    return None
            if readonly:
                # a read-only role may run the test runner, never an arbitrary in-repo script
                if head in ("python", "python3"):
                    if not any(argv[i] == "-m" and argv[i + 1] in ("pytest", "unittest") for i in range(1, len(argv) - 1)):
                        return None
                else:
                    return None
        if readonly and head == "make" and (not sub or sub not in ("test", "check", "lint", "typecheck", "build", "bench")):
            return None
        if readonly and head in ("pip", "pip3"):
            return None
        return f"project toolchain ({head})"
    if head in ("pip", "pip3"):
        return None
    if head in FS_OPS and not readonly:
        paths = path_args(argv)
        if head == "chmod":      # `chmod +x src/run.sh`: the mode token is not a path
            paths = [p for p in paths if not re.fullmatch(r"[ugoa]*[+\-=][rwxXst]*|[0-7]{3,4}", p)]
        if not paths or not all(inside_worktree(p) for p in paths):
            return None
        if head in ("rm", "mv", "chmod"):
            if head == "rm" and any(a.startswith("-") and "r" in a.lower() for a in argv[1:]):
                return None
            src = paths if head != "mv" else paths[:-1]
            if not all(any(path_matches(p, e) for e in footprint) for p in src):
                return None
            if head == "mv" and not any(path_matches(paths[-1], e) for e in footprint):
                return None
        elif head in ("cp", "touch"):
            dst = paths[-1:] if head == "cp" else paths
            if not all(any(path_matches(p, e) for e in footprint) for p in dst):
                return None
        elif head == "mkdir":
            if not all(any(e.startswith(p.rstrip("/") + "/") or path_matches(p, e) for e in footprint)
                       or p.startswith(".slice/tmp") for p in paths):
                return None
        return "file operation inside the slice footprint"
    if head == "git" and not readonly:
        sub = argv[1] if len(argv) > 1 else ""
        if sub in ("add", "rm", "mv", "restore"):
            paths = [a for a in argv[2:] if not a.startswith("-")]
            if sub == "restore" and "--staged" not in argv:
                return None
            if paths and all(any(path_matches(p, e) for e in footprint) for p in paths):
                return f"git {sub} inside the slice footprint"
            return None
        if sub == "checkout" and "--" in argv:
            paths = argv[argv.index("--") + 1:]
            if paths and all(any(path_matches(p, e) for e in footprint) for p in paths):
                return "git checkout -- <footprint file>"
    return None


def bash_allow_reason(raw, wt, footprint, pinned, readonly=False):
    """Pre-approve one simple command, or a pipeline whose every stage is individually approved and
    that redirects nothing to a file. `cd <inside> && cmd` is accepted for a relative, in-tree cd."""
    cmd = raw.strip()
    for r in SAFE_REDIRECTS:
        cmd = cmd.replace(r, " ")
    # `cd sub && <cmd>` — the classic. Accept only a relative in-tree cd with a single &&.
    m = re.fullmatch(r"cd\s+([^\s;&|<>`$]+)\s*&&\s*(.+)", cmd, flags=re.S)
    if m and inside_worktree(m.group(1)):
        cmd = m.group(2)
    if SHELL_META.search(strip_quoted(cmd, meta=True)):
        return None
    reasons = []
    for seg in cmd.split("|"):
        argv = argv_of(seg.strip())
        if not argv:
            return None
        why = segment_allowed(argv, footprint, pinned, readonly=readonly, wt=wt)
        if not why:
            return None
        reasons.append(why)
    return "dev-team: pre-approved — " + "; ".join(dict.fromkeys(reasons))[:120]


def perm_allow(reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PermissionRequest",
                                             "decision": {"behavior": "allow", "reason": reason}}}))
    sys.exit(0)


def guard_perm(inp):
    """Optional settings-level PermissionRequest hook (matcher Bash): same allow-list as `bash`."""
    if (inp.get("tool_name") or "") != "Bash":
        allow()
    cmd = ((inp.get("tool_input") or {}).get("command") or "").strip()
    if not cmd:
        allow()
    norm, redirected = normalize_git(cmd)
    if redirected:
        allow()
    for pat, _why in BASH_DENY:            # never widen what guard_bash forbids
        if re.search(pat, norm):
            allow()
    wt = find_slice_root(inp.get("cwd") or os.getcwd())
    reason = bash_allow_reason(cmd, wt, footprint=read_lines(wt / ".slice" / "footprint") if wt else [],
                               pinned=read_lines(wt / ".slice" / "allow") if wt else [])
    if reason:
        perm_allow(reason)
    allow()


# ----------------------------------------------------------------------------- stop gate

def write_marker(wt, sd, sid, kind, note=""):
    """Tell the Conductor's engine this lane is finished: `<root>/.claude/dev-team/slices/<id>.done`
    (or `.blocked`). Best effort — `devteam next <id>` remains the manual fallback."""
    try:
        (sd / "stop_blocks").unlink()   # the lane is finished: a resume after a rejection is gated afresh
    except OSError:
        pass
    root = (read_lines(sd / "root") or [""])[0]
    if not root:
        return
    try:
        d = Path(root) / STATE_DIRNAME / "slices"
        d.mkdir(parents=True, exist_ok=True)
        other = d / f"{sid}.{'blocked' if kind == 'done' else 'done'}"
        if other.exists():
            other.unlink()
        (d / f"{sid}.{kind}").write_text(json.dumps({"t": int(time.time()), "worktree": str(wt),
                                                       "branch": git(["rev-parse", "--abbrev-ref", "HEAD"], wt),
                                                       "note": note[:600]}))
    except OSError:
        pass


def notes_of(last):
    m = re.search(r"##\s*Notes:(.*?)(?=\n##\s|\Z)", last, re.S)
    return (m.group(1).strip() if m else last[-400:]).strip()


def guard_stop(inp):
    cwd = inp.get("cwd") or os.getcwd()
    wt = find_slice_root(cwd)
    if wt is None:
        allow()
    sd = wt / ".slice"
    last = inp.get("last_assistant_message") or ""
    sid = read_lines(sd / "id")[0]
    if re.search(r"Status:\s*Blocked", last, re.I):
        write_marker(wt, sd, sid, "blocked", notes_of(last))
        allow()
    blocks_file = sd / "stop_blocks"
    blocks = int(read_lines(blocks_file)[0]) if read_lines(blocks_file) else 0
    if blocks >= MAX_STOP_BLOCKS:
        write_marker(wt, sd, sid, "done", "stop gate gave up after repeated blocks; integrate re-checks")
        allow()  # never loop forever; the integrator re-checks everything at merge time
    mode = (read_lines(sd / "mode") or ["slice"])[0]
    kind = (read_lines(sd / "kind") or ["code"])[0]
    globs = read_lines(sd / "test_globs")
    fp = read_lines(sd / "footprint")
    spike = (sd / "notest").exists() or mode in ("fast", "work")
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
    head = git(["rev-parse", "HEAD"], wt)
    if spike:
        # Evidence-gated slice (spike / chore / docs / refactor / perf / test): no RED-GREEN split.
        # Three gates remain: something was committed, any tests it wrote are still frozen, and the
        # report shows real command output — the evidence IS the safety net here.
        base = (read_lines(sd / "base") or [""])[0]
        helper = "commit-fast" if mode == "fast" else "commit-work"
        if base:
            # HEAD != base is the whole test: an old commit from a previous run that
            # reused this slice id must never count as "committed" for THIS run.
            committed = bool(head) and head != base
        else:
            subjects = [ln.partition("\x1f")[2] for ln in git(["log", "--format=%H%x1f%s", "-n", "200"], wt).splitlines()]
            committed = any(s.startswith(f"{pfx}({sid})") for s in subjects
                            for pfx in ("feat", "test", "chore", "docs", "perf", "refactor"))
        if not committed:
            problems.append(f"nothing committed yet → finish the slice and run "
                            f"`{helper} \"<title>\"` (no RED/GREEN split for this kind)")
        if kind == "refactor":
            changed_tests = [f for f in git(["diff", "--no-renames", "--name-only", base, "HEAD"], wt).splitlines()
                             if f and is_test_path(f, globs)] if base else []
            if changed_tests:
                problems.append("a REFACTOR slice changed test files: " + ", ".join(changed_tests[:6]) +
                                f" → restore them (`git checkout {base[:9]} -- <file>`) and commit; the "
                                "untouched tests are what proves behaviour did not change")
        ensure_red_cache(wt, sd, sid, globs)
        red = (read_lines(sd / "red") or [""])[0]
        frozen = read_lines(sd / "red_files")
        if red and frozen:
            changed = git(["diff", "--no-renames", "--name-only", red, "HEAD", "--"] + frozen, wt)
            if changed:
                problems.append("tests you committed in " + red[:9] + " were changed afterwards: " +
                                changed.replace("\n", ", ") + " → a spike slice needs no tests, but may not weaken "
                                "the ones it wrote; restore them (`git checkout " + red[:9] + " -- <file>`) and commit")
        gate_m = re.search(r"##\s*Gate:(.*?)(?=\n##\s|\Z)", last, re.S)
        if not gate_m or len(gate_m.group(1).strip()) < 20:
            problems.append("this slice has no RED/GREEN split protecting it, so your report MUST show real "
                            "evidence under `## Gate:` — the command you ran AND its output, not "
                            "\"should work\" and not an empty heading")
        elif kind in ("refactor", "perf") and len(
                [ln for ln in gate_m.group(1).splitlines() if ln.strip()]) < 3:
            problems.append(f"a {kind.upper()} slice needs BOTH runs under `## Gate:` — the before result and "
                            "the after result — so the reviewer can see that nothing regressed")
        if not re.search(r"##\s*Status:", last):
            problems.append("your final message must use the report format from the briefing "
                            "(## Slice / ## Status / ## Worktree / ## Commits / ## Changes / ## Criteria / ## Gate / ## Notes)")
        if problems:
            block(blocks_file, blocks, problems)
        write_marker(wt, sd, sid, "done", notes_of(last))
        allow()
    ensure_red_cache(wt, sd, sid, globs)
    red = (read_lines(sd / "red") or [""])[0]
    if not red:
        problems.append(f"no RED commit `test({sid}): RED — …` on this branch → write failing tests for every criterion, "
                        "run only them, then `commit-red \"<title>\"` BEFORE any implementation")
    else:
        frozen = read_lines(sd / "red_files")
        if frozen:
            changed = git(["diff", "--no-renames", "--name-only", red, "HEAD", "--"] + frozen, wt)
            if changed:
                problems.append("frozen test files changed after RED: " + changed.replace("\n", ", ") +
                                " → restore them (`git checkout " + red[:9] + " -- <file>`) and commit; a wrong test = Status: Blocked")
        if mode in ("slice", "green") and head == red:
            problems.append("no implementation commit after the RED commit → implement the minimum to pass, run the gate, `commit-green \"<title>\"`")
    if not re.search(r"##\s*Status:", last):
        problems.append("your final message must use the report format from the briefing (## Slice / ## Status / ## Commits / ## Changes / ## Criteria / ## Gate / ## Notes)")
    if problems:
        block(blocks_file, blocks, problems)
    write_marker(wt, sd, sid, "done", notes_of(last))
    allow()


def block(blocks_file, blocks, problems):
    try:
        blocks_file.write_text(str(blocks + 1))
    except OSError:
        pass
    sys.stderr.write("dev-team gate — you are not done yet:\n- " + "\n- ".join(problems) +
                     "\nIf something makes this impossible, end with `## Status: Blocked` and the exact reason.\n")
    sys.exit(2)


# ----------------------------------------------------------------------------- read-only roles

# Reports and memory only. `.claude/dev-team/` as a whole is NOT writable by a read-only role:
# state.json, briefs/ and slices/ are what the scheduler and the integrator trust. plan.md is the
# team-leader's deliverable (PLANNING / PLAN ADOPTION), so that one role may write it.
RO_WRITE_ALLOW = ("/.claude/dev-team/reviews/", "/.claude/dev-team/research/",
                  "/.claude/agent-memory/", "/.claude/agent-memory-local/")
LEADER_WRITE_ALLOW = ("/.claude/dev-team/plan.md", "/.claude/dev-team/plan-", "/.claude/dev-team/plan_")


def guard_edit_ro(inp):
    path = tool_path(inp)
    if not path:
        deny("This role is read-only, and this write names no file, so it cannot be checked against the "
             "report / memory paths it may write. Report findings instead.")
    if not os.path.isabs(path):
        path = os.path.join(inp.get("cwd") or os.getcwd(), path)
    norm = os.path.abspath(path).replace("\\", "/")
    if any(seg in norm for seg in RO_WRITE_ALLOW):
        allow("dev-team: this role's own report / memory file")
    agent = (inp.get("agent_type") or "").lower()
    if any(seg in norm for seg in LEADER_WRITE_ALLOW) and agent == "team-leader":
        allow("dev-team: the team-leader's plan")
    deny(f"This role is read-only, and may write only its own report under .claude/dev-team/reviews/ "
         f"or .claude/dev-team/research/ (plus its memory dir; the team-leader also writes plan.md). "
         f"`{os.path.basename(path)}` is neither — the run state and other agents' briefings are off limits. "
         "Report findings; a programmer applies fixes.")


# Mutating tools are denied at command position only (see ro_mutating_tool below). RO_MUTATING_RE is the
# plain substring scan kept as the fallback for a command whose quoting shlex cannot parse.
RO_MUTATING_TOOLS = ("rm", "mv", "cp", "chmod", "chown", "mkdir", "touch", "truncate", "dd", "ln", "rsync",
                     "tee", "install")
RO_MUTATING_RE = r"(^|[\s;&|])(" + "|".join(RO_MUTATING_TOOLS) + r")\b"

BASH_RO_DENY = [
    r"\bsed\s+-[a-zA-Z]*i",
    r"\bperl\s+-[a-zA-Z]*i",
    r"(^|[^&<>])>{1,2}(?!\s*/dev/null\b|&)",
    r"\bgit\s+(add|commit|checkout|switch|reset|rebase|push|pull|fetch|clean|rm|mv|tag|apply|cherry-pick|revert|branch\s+-[dDmM]|filter-branch)\b",
    r"\bgit\s+merge\b(?!-)",
    r"\bgit\s+worktree\b(?!\s+list\b)",
    r"\bgit\s+stash\b(?!\s+(list|show)\b)",
    r"\b(npm|pnpm|yarn|bun)\s+(install|i|add|remove|uninstall|update|publish|link)\b",
    r"\b(pip|pip3|poetry|uv|conda|cargo|go|gem|composer)\s+(install|add|remove|uninstall|update|publish)\b",
    r"\b(brew|apt|apt-get|dnf|yum|apk|pacman|snap|pipx|bundle|make)\s+(install|remove|uninstall|upgrade)\b",
    r"\bpython[0-9.]*\s+-c\s+.*open\([^)]*['\"][wa]",
]

_RO_WRAPPER_FLAGS = {       # wrapper -> its options that consume the next token
    "env": {"-u", "-C", "--unset", "--chdir"},
    "sudo": {"-u", "-g", "-C", "-h", "-p", "-r", "-t", "-U", "-D", "-R", "--user", "--group", "--host"},
    "time": {"-f", "-o", "--format", "--output"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "-P", "-u"},
    "stdbuf": {"-i", "-o", "-e"},
    "xargs": {"-I", "-n", "-P", "-L", "-d", "-E", "-s", "-a", "-J"},
    "exec": {"-a"},
    "nohup": set(), "command": set(), "setsid": set(), "busybox": set(), "builtin": set(),
}
_RO_SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
_RO_KEYWORDS = {"{", "}", "!", "if", "then", "else", "elif", "do", "while", "until"}
_RO_FIND_EXEC = {"-exec", "-execdir", "-ok", "-okdir"}
_RO_REDIRECT = re.compile(r"[<>&]*[<>][<>&]*")
_RO_ASSIGN = re.compile(r"[A-Za-z_]\w*=.*")


def _ro_segments(cmd):
    """Token lists of the simple commands in `cmd`, split on unquoted `;` `&` `|` `(` `)`, newline and
    backtick. Raises ValueError when the quoting cannot be parsed."""
    flat, q, esc = [], "", False
    for ch in cmd:
        if esc:
            esc = False
        elif ch == "\\" and q != "'":
            esc = True
        elif q:
            q = "" if ch == q else q
        elif ch in "'\"":
            q = ch
        elif ch in "\n`":
            ch = " ; "
        flat.append(ch)
    if q:
        raise ValueError("unterminated quote")
    lex = shlex.shlex("".join(flat), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""         # `ls a#b; rm x` has no comment: `#` only starts one at the start of a word
    segs, cur = [], []
    for t in lex:
        if all(c in ";&|()" for c in t):
            if cur:
                segs.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        segs.append(cur)
    return segs


def _ro_skip_wrapper(seg, i, base):
    """Index of the command a wrapper (`env`, `sudo`, `timeout 5`, `xargs -I {}` ...) runs; `i` is the
    index just after the wrapper word."""
    takes_arg = _RO_WRAPPER_FLAGS[base]
    while i < len(seg):
        t = seg[i]
        if t == "--":
            return i + 1
        if t in takes_arg:
            i += 2
        elif t.startswith("-") or _RO_ASSIGN.fullmatch(t):
            i += 1
        else:
            break
    return i + 1 if base == "timeout" else i       # timeout's first operand is the duration


def _ro_seg_tool(seg, depth):
    """The RO_MUTATING_TOOLS name that one simple command runs, else ''."""
    if depth > 5:
        raise ValueError("nesting too deep")
    i = 0
    while i < len(seg):
        tok = seg[i]
        base = os.path.basename(tok)
        if _RO_REDIRECT.fullmatch(tok):
            i += 2                                  # the operator and its target are not the command
        elif _RO_ASSIGN.fullmatch(tok) or tok in _RO_KEYWORDS or tok.isdigit():
            i += 1
        elif base in RO_MUTATING_TOOLS:
            return base
        elif base in _RO_WRAPPER_FLAGS:
            if base == "command" and seg[i + 1:i + 2] in (["-v"], ["-V"]):
                return ""                           # `command -v rm` only looks the name up
            i = _ro_skip_wrapper(seg, i + 1, base)
        elif base in _RO_SHELLS:
            for j in range(i + 1, len(seg) - 1):
                if seg[j].startswith("-") and not seg[j].startswith("--") and "c" in seg[j]:
                    return ro_mutating_tool(seg[j + 1], depth + 1)
            return ""
        elif base == "eval":
            return ro_mutating_tool(" ".join(seg[i + 1:]), depth + 1)
        elif base == "find":
            for j in range(i + 1, len(seg)):
                if seg[j] in _RO_FIND_EXEC:
                    hit = _ro_seg_tool(seg[j + 1:], depth + 1)
                    if hit:
                        return hit
            return ""
        else:
            return ""
    return ""


def ro_mutating_tool(cmd, depth=0):
    """The mutating tool `cmd` runs at command position, else ''. Command position means the start of
    any `;` `&&` `||` `|` newline segment, after env/sudo/time/timeout/nice/nohup/command wrappers,
    after `xargs` and `find -exec`, and inside an `sh -c` / `eval` payload. A tool name that is only an
    argument (`grep -rn install src`, `ls | grep dd`) is not a hit. Raises ValueError when `cmd`
    cannot be parsed; the caller then falls back to RO_MUTATING_RE."""
    for seg in _ro_segments(cmd):
        hit = _ro_seg_tool(seg, depth)
        if hit:
            return hit
    return ""


def deny_ro(raw):
    deny(f"Read-only role: `{raw[:80]}` looks like it modifies files/packages/git state. "
         "Use Read/Grep/Glob, run tests/linters/diffs only, and report instead of changing anything.")


def find_state_root(start):
    """The integration checkout, seen from a reviewer's cwd (or the pointer in the shared .git dir)."""
    p = Path(start).resolve()
    for _ in range(20):
        if (p / STATE_DIRNAME / "state.json").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    ptr = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], str(start))
    if ptr and (Path(ptr) / "dev-team-root").exists():
        try:
            root = Path((Path(ptr) / "dev-team-root").read_text().strip())
            if (root / STATE_DIRNAME / "state.json").exists():
                return root
        except OSError:
            pass
    return None


def plan_commands(root):
    """The plan's gate commands, as argv prefixes a read-only role may run for evidence."""
    if not root:
        return []
    try:
        st = json.loads((root / STATE_DIRNAME / "state.json").read_text())
    except (OSError, ValueError):
        return []
    out_ = []
    for k in ("build", "test", "test_file", "lint", "lint_file", "typecheck", "typecheck_file", "bench"):
        v = (st.get("commands") or {}).get(k)
        if v and str(v).strip().lower() not in ("none", "n/a", "-"):
            out_.append(str(v).split("{files}")[0].strip())
    for s in (st.get("slices") or {}).values():
        v = (s.get("verify") or "").strip()
        if v:
            out_.append(v.split("{files}")[0].strip())
    return [x for x in out_ if x]


def guard_bash_ro(inp):
    raw = (inp.get("tool_input") or {}).get("command", "") or ""
    cmd, redirected = normalize_git(raw)
    if redirected:
        deny(f"Read-only role: `{raw[:80]}` points git at another checkout (`-C` / `--git-dir` / "
             "`--work-tree`). Read this repository in place instead.")
    scan = strip_for_scan(cmd)
    try:
        mutating = ro_mutating_tool(raw)
    except ValueError:          # quoting shlex cannot parse: keep the conservative substring scan
        mutating = re.search(RO_MUTATING_RE, scan)
    if mutating:
        deny_ro(raw)
    for pat in BASH_RO_DENY:
        if re.search(pat, scan):
            deny_ro(raw)
    why = ro_forbidden_form(cmd)
    if why:
        deny(f"Read-only role: `{raw[:80]}` is blocked: {why}. Run checks in their read-only form "
             "(`--check` / `--diff`, no output file, no helper program) and report instead of changing anything.")
    root = find_state_root(inp.get("cwd") or os.getcwd())
    allow(bash_allow_reason(raw, None, footprint=[], pinned=plan_commands(root), readonly=True))


OC_PATCH_PATH = re.compile(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to):\s*(.+)$")


def oc_patch_paths(text):
    """Every file a patch names. Each line is stripped first: v2 trims lines before it applies a
    patch, so an indented `*** Update File:` header is live and must be checked like any other."""
    if not isinstance(text, str):
        return []
    out_ = []
    for ln in text.splitlines():
        m = OC_PATCH_PATH.match(ln.strip())
        if m and m.group(1).strip():
            out_.append(m.group(1).strip())
    return out_


def oc_capture(check, inp):
    """Run one Claude-shaped check and return what it printed (it always ends in sys.exit)."""
    buf = io.StringIO()
    old, sys.stdout = sys.stdout, buf
    try:
        check(inp)
    except SystemExit:
        pass
    finally:
        sys.stdout = old
    return buf.getvalue()


OC_LANE_DENY_TOOLS = {
    "execute": "OpenCode Code Mode (`execute`) is disabled in dev-team lanes so every tool call "
               "can be checked on its own. Call the tools directly.",
    "batch": "`batch` is disabled in dev-team lanes so every tool call can be checked on its own. "
             "Call the tools one at a time.",
    "question": "`question` is disabled in dev-team lanes: a headless lane has nobody to answer it, so the "
                "run would block. Decide from the brief, or end with `## Status: Blocked` and the question.",
}


def oc_args(raw):
    """The tool args as a dict, or None when they cannot be read. v2 may hand them over as a JSON
    string (`input.repair`); anything that is still not an object after decoding is unreadable."""
    if raw is None or raw == "":
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None
    return raw if isinstance(raw, dict) else None


def oc_pinned_hint(cwd, prog):
    """The command forms this lane may run without a prompt, for the unapproved-shell deny message:
    `.slice/allow` for a programmer, the plan's gate commands for a read-only role."""
    try:
        if prog:
            wt = find_slice_root(cwd)
            pinned = read_lines(wt / ".slice" / "allow") if wt else []
            src = "`.slice/allow`"
        else:
            pinned = plan_commands(find_state_root(cwd))
            src = "the plan's gate commands"
    except Exception:
        return ""
    forms = [p.strip() for p in pinned if p.strip()][:12]
    if not forms:
        return f" No commands are pinned for this lane ({src} is empty)."
    return f" Pinned forms from {src}: " + ", ".join(f"`{f}`" for f in forms) + "."


def guard_oc(inp):
    """OpenCode plugin bridge: {"tool", "args", "cwd", "role"} -> the existing check for that role.

    OC has no interactive human to fall through to, so anything a Claude-side check leaves silent
    (its "defer to the normal ask-flow" signal) is made an explicit deny here instead — except the
    one silence that check already means as a real allow (a footprint-free edit inside the agent's
    own claimed worktree)."""
    role = (inp.get("role") or "").strip()
    if not role:
        allow()
    tool = (inp.get("tool") or "").lower()
    args = oc_args(inp.get("args"))
    if args is None:
        deny(f"dev-team: the `{tool}` arguments could not be parsed as a JSON object, so the call cannot "
             "be checked. Retry it with well-formed arguments.")
    prog = role in ("programmer", "programmer-lite")
    cwd = inp.get("cwd") or os.getcwd()
    base = {"cwd": cwd, "agent_type": role}
    if tool in OC_LANE_DENY_TOOLS:
        deny("dev-team: " + OC_LANE_DENY_TOOLS[tool])
    if tool in ("bash", "shell"):
        workdir = args.get("workdir")
        command = args.get("command")
        if not isinstance(command, str) or (workdir is not None and not isinstance(workdir, str)):
            deny(f"dev-team: `{tool}` needs a string `command` (and a string `workdir` when one is given); "
                 "these arguments cannot be checked.")
        if workdir:
            wd = workdir if os.path.isabs(workdir) else os.path.abspath(os.path.join(cwd, workdir))
            if prog and find_slice_root(wd) != find_slice_root(cwd):
                deny(f"`workdir` {workdir} is outside your slice worktree; run commands from the worktree.")
            base["cwd"] = wd
        check = guard_bash if prog else guard_bash_ro
        out = oc_capture(check, dict(base, tool_input={"command": command}))
        if not out.strip():
            deny("dev-team: OpenCode has no interactive fallback, so a bash command that isn't "
                 "explicitly pre-approved is denied instead of silently allowed."
                 + oc_pinned_hint(base["cwd"], prog))
        sys.stdout.write(out)
        sys.exit(0)
    if tool in ("edit", "write", "multiedit"):
        p0 = args.get("filePath") or args.get("path") or ""  # v1 filePath, v2 path
        if not isinstance(p0, str) or not p0.strip():
            deny(f"`{tool}` names no file (no `filePath` / `path`), so it cannot be checked. "
                 "Retry it naming the file it writes.")
        paths = [p0]
    elif tool in ("patch", "apply_patch"):
        paths = oc_patch_paths(args.get("patchText"))
        if not paths:
            deny(f"`{tool}` names no file (no `*** Add/Update/Delete File:` header), so it cannot be checked "
                 "against your footprint. Rewrite it with a header naming each file it touches.")
    else:
        allow()
    check = guard_edit if prog else guard_edit_ro
    out = ""
    for p in paths:
        ap = p if os.path.isabs(p) else os.path.abspath(os.path.join(cwd, p))
        if prog and find_slice_root(os.path.dirname(ap)) is None:
            out = deny_json(f"`{p}` is outside any slice worktree. OpenCode has no interactive "
                            "fallback for an unclaimed path.")
            break
        out = oc_capture(check, dict(base, tool_input={"file_path": p}))
        if '"permissionDecision": "deny"' in out:
            break
    if out:
        sys.stdout.write(out)
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
        {"edit": guard_edit, "bash": guard_bash, "stop": guard_stop, "perm": guard_perm,
         "edit-ro": guard_edit_ro, "bash-ro": guard_bash_ro, "oc": guard_oc}.get(mode, lambda i: allow())(inp)
    except SystemExit:
        raise
    except Exception:
        allow()  # fail-open


if __name__ == "__main__":
    main()
