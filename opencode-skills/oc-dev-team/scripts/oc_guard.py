#!/usr/bin/env python3
"""dev-team tool-call guards for OpenCode lanes (JSON on stdin).

  oc_guard.py oc    Tool bridge: {"tool", "args", "cwd", "role"} on stdin; role is the lane's agent
                 name. A lane runs from the main checkout with no working directory of its own, so
                 the slice comes from the tool input: an edit path or a shell `workdir` inside
                 `<root>/.opencode/oc-dev-team/wt/<id>/` selects slice <id>. Role programmer ->
                 footprint, frozen-test and command checks; a write outside every worktree or a
                 shell call without `workdir` is denied naming the worktree, and an allowed write or
                 command is returned as an explicit `allow`. Any other role -> read-only checks with
                 agent_type = role, so it may write only under reviews/, research/ (and plan.md for
                 the team-leader) and run read-only commands. No role -> silent allow. The per-role
                 check functions below are reached only through this mode.
  oc_guard.py stop  Completion gate for a programmer (`oc_devteam.py report` feeds it the report): RED
                 committed, GREEN after RED, tree clean, real evidence under `## Gate:` for
                 evidence-gated kinds. When the gate passes it writes a
                 `<root>/.opencode/oc-dev-team/slices/<id>.done` marker (or `.blocked`), which is how
                 `devteam next` finds finished programmers.

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
STATE_DIRNAME = ".opencode/oc-dev-team"


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
        if (p / ".oc-slice" / "id").exists():
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
    # find_slice_root() resolve()s the worktree, so resolve the path too: a symlinked cwd or a
    # /var -> /private/var alias must not turn an in-footprint edit into `../…` and deny it
    path = str(Path(path if os.path.isabs(path) else os.path.join(inp.get("cwd") or os.getcwd(), path)).resolve())
    wt = find_slice_root(os.path.dirname(path))
    own = find_slice_root(inp.get("cwd") or "")
    if wt is None:
        allow()  # not a claimed worktree (fail-open; native isolation still protects the main checkout)
    if own is not None and own != wt:
        deny(f"`{path}` belongs to another slice's worktree ({wt}); you may only edit inside your own worktree {own}.")
    sd = wt / ".oc-slice"
    rel = os.path.relpath(path, wt).replace("\\", "/")
    if rel.startswith(".oc-slice/") or rel == ".oc-slice":
        deny("`.oc-slice/` is dev-team metadata; never edit it.")
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
    a double-quoted span holding `$` or a backtick is kept for the metachar scan, and for the deny
    scan the payload of `sh -c`/`eval` and a redirect target is unwrapped."""
    def repl(m):
        s = m.group(0)
        if meta:
            return s if s[0] == '"' and ("$" in s or "`" in s) else ""
        if _UNWRAP_BEFORE_RE.search(cmd[:m.start()]):
            return " " + s[1:-1] + " "
        return s if s[0] == '"' and ("$(" in s or "`" in s) else ""
    return _QUOTED_RE.sub(repl, cmd)


def strip_for_scan(cmd):
    """`cmd` with quoted spans and safe redirects removed, for the BASH_DENY regexes."""
    cmd = strip_quoted(cmd)
    for r in SAFE_REDIRECTS:
        cmd = cmd.replace(r, " ")
    return cmd


def _is_meta_pat(pat):
    return ".oc-slice" in pat or ".opencode/oc-dev-team" in pat


DEVTEAM_LANE_SUBS = {"claim", "report", "commit-red", "commit-green", "commit-work", "commit-fast"}

_PY_INTERPRETER_RE = re.compile(r"^python[0-9.]*$")


def _is_devteam_script(tok):
    return tok.replace("\\", "/").rstrip("/").split("/")[-1] == "oc_devteam.py"


def devteam_subcommand(cmd):
    """If `cmd` actually EXECUTES .../oc_devteam.py (directly, or via a python interpreter), its
    subcommand; else None. The script name as a plain ARGUMENT to another program (grep, git diff,
    wc) is never an invocation."""
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
    """The engine subcommand run by ANY segment of a compound command (`;`, `&&`, `||`, `|`,
    newline) or behind wrappers like `timeout 600` / `env` / `nice`: the first one that is NOT a lane
    helper if there is one, else the first found, else None. Deny-side only."""
    segs = []
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


BASH_DENY = [
    (r"\bgit\s+(push|rebase|filter-branch|switch|cherry-pick|revert)\b", "integration/history commands are the Conductor's"),
    (r"\bgit\s+merge\b(?!-)", "integration/history commands are the Conductor's"),
    (r"\bgit\s+worktree\b(?!\s+list\b)", "integration/history commands are the Conductor's"),
    (r"\bgit\s+stash\b(?!\s+(list|show)\b)", "integration/history commands are the Conductor's"),
    (r"\bgit\s+reset\s+(--hard|--merge|--soft)\b", "history rewriting is forbidden in a slice worktree"),
    (r"\bgit\s+branch\s+(-[dDmM]\b|--delete|--move|--force)", "branch surgery is forbidden in a slice worktree"),
    (r"\bgit\s+commit\b[^|;&]*--amend", "--amend would rewrite the RED audit trail; make a new commit"),
    (r"\bgit\s+(reflog\s+expire|update-ref|symbolic-ref|gc\s+--prune)\b", "history rewriting is forbidden"),
    (r"(^|[\s;&|])rm\s+-[a-zA-Z]*r[a-zA-Z]*\s+[^\s]*\.oc-slice\b", "`.oc-slice/` is dev-team metadata"),
    (r"(^|[\s;&|/])(sed\s+-i|tee|>>?)\s*[^\s]*\.oc-slice/", "`.oc-slice/` is dev-team metadata"),
    # any write-shaped mention of .oc-slice/ at all: it is the record the integrator and the Stop gate
    # read, so an agent that can rewrite it can claim a RED commit it never made
    (r"\.oc-slice/(red|red_files|base|mode|kind|footprint|allow|id|notest|criteria|root)\b[^\n]*"
     r"(>|>>|\bwrite(?:_text|_bytes)?\b|\bopen\s*\(|\bmv\b|\bcp\b|\brm\b)", "`.oc-slice/` is dev-team metadata"),
    (r"(>|>>|\bmv\b|\bcp\b|\btee\b|\bwrite(?:_text|_bytes)?\s*\()[^\n]*\.oc-slice/", "`.oc-slice/` is dev-team metadata"),
    # the done/blocked markers are how `next` finds finished lanes: only the Stop gate writes them
    (r"(>|>>|\bmv\b|\bcp\b|\btee\b|\btouch\b|\bwrite(?:_text|_bytes)?\s*\()[^\n]*\.opencode/oc-dev-team/", "`.opencode/oc-dev-team/` is the Conductor's run state"),
    (r"\.opencode/oc-dev-team/[^\n]*\bwrite(?:_text|_bytes)?\s*\(", "`.opencode/oc-dev-team/` is the Conductor's run state"),
]


def guard_bash(inp):
    raw = (inp.get("tool_input") or {}).get("command", "") or ""
    sub = devteam_subcommand(raw)
    denied = sub if sub is not None else wrapped_engine_subcommand(raw)
    if denied is not None and denied not in DEVTEAM_LANE_SUBS:
        deny(f"`oc_devteam.py {denied}` drives the engine (integrate/finish/reset/next/dispatch and everything "
             "else are the Conductor's); a lane may only run claim / report / commit-red / commit-green / "
             "commit-work / commit-fast.")
    if sub is not None:
        wt0 = find_slice_root(inp.get("cwd") or os.getcwd())
        pinned0 = read_lines(wt0 / ".oc-slice" / "allow") if wt0 else []
        argv0 = argv_of(raw)
        match = prefix_match(argv0, pinned0) if argv0 else None
        allow(f"dev-team: pinned command from the briefing — {match}" if match else None)
    cmd, redirected = normalize_git(raw)
    if redirected:
        deny(f"Blocked `{raw[:80]}`: it points git at another checkout (`-C` / `--git-dir` / "
             "`--work-tree` / `GIT_DIR`). Every git command must act on YOUR worktree only.")
    scan = cmd      # quotes kept: `python3 -c "open('.oc-slice/red','w')"` must still match; only safe redirects go
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
    reason = bash_allow_reason(raw, wt, footprint=read_lines(wt / ".oc-slice" / "footprint") if wt else [],
                               pinned=read_lines(wt / ".oc-slice" / "allow") if wt else [])
    allow(reason)


# ----------------------------------------------------------------------------- the allow-list

ALLOW_GIT_READ = ("git status", "git diff", "git log", "git show", "git rev-parse", "git ls-files",
                  "git grep", "git blame", "git branch --list", "git stash list", "git describe")
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
    if SHELL_META.search(cmd):
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


def prefix_match(argv, prefixes):
    for pfx in prefixes:
        pargv = argv_of(pfx.strip())
        if not pargv or len(pargv) > len(argv):
            continue
        if argv[:len(pargv)] == pargv:
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
    r"|s(.)(?:\\.|(?!\1).)*\1(?:\\.|(?!\1).)*\1[gpiImM0-9]*[we]")


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


def write_exec_form(argv, readonly=False):
    """Why one argv writes a file or runs another program although its command looks read-only
    (`git diff --output`, `git grep -O`, `rg --pre`, `uniq IN OUT`, sed `w`/`e`,
    `sort --compress-program`), or None."""
    argv = strip_env_prefix(argv)
    if not argv:
        return None
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


def segment_allowed(argv, footprint, pinned, readonly=False, wt=None):
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
    if head == "sed" and not any(a.startswith("-i") or a == "--in-place" for a in argv[1:]):
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
                    (argv[1] == "oc_devteam.py" or argv[1].endswith("/oc_devteam.py")) and argv[2] in ("status", "probe"):
                return "dev-team engine status/probe (read-only)"
            if any(a in INTERPRETER_EVAL_FLAGS for a in argv[1:]):
                return None
            if any(a.endswith("oc_devteam.py") or a.endswith("oc_guard.py") for a in argv[1:]):
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
                       or p.startswith(".oc-slice/tmp") for p in paths):
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
    if SHELL_META.search(cmd):
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


# ----------------------------------------------------------------------------- stop gate

def write_marker(wt, sd, sid, kind, note=""):
    """Tell the Conductor's engine this lane is finished: `<root>/.opencode/oc-dev-team/slices/<id>.done`
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
    """Completion gate for a programmer lane: exit 2 with the reasons on stderr until the slice is committed and reported."""
    cwd = inp.get("cwd") or os.getcwd()
    wt = find_slice_root(cwd)
    if wt is None:
        allow()
    sd = wt / ".oc-slice"
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
    status = [p for _, p in porcelain(wt) if not p.startswith(".oc-slice")]
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
        subjects = [ln.partition("\x1f")[2] for ln in git(["log", "--format=%H%x1f%s", "-n", "200"], wt).splitlines()]
        committed = any(s.startswith(f"{pfx}({sid})") for s in subjects
                        for pfx in ("feat", "test", "chore", "docs", "perf", "refactor"))
        helper = "commit-fast" if mode == "fast" else "commit-work"
        if not committed and not (base and head and head != base):
            problems.append(f"nothing committed yet → finish the slice and run "
                            f"`{helper} \"<title>\"` (no RED/GREEN split for this kind)")
        if kind == "refactor":
            changed_tests = [f for f in git(["diff", "--name-only", base, "HEAD"], wt).splitlines()
                             if f and is_test_path(f, globs)] if base else []
            if changed_tests:
                problems.append("a REFACTOR slice changed test files: " + ", ".join(changed_tests[:6]) +
                                f" → restore them (`git checkout {base[:9]} -- <file>`) and commit; the "
                                "untouched tests are what proves behaviour did not change")
        ensure_red_cache(wt, sd, sid, globs)
        red = (read_lines(sd / "red") or [""])[0]
        frozen = read_lines(sd / "red_files")
        if red and frozen:
            changed = git(["diff", "--name-only", red, "HEAD", "--"] + frozen, wt)
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
            changed = git(["diff", "--name-only", red, "HEAD", "--"] + frozen, wt)
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

# Reports and memory only. `.opencode/oc-dev-team/` as a whole is NOT writable by a read-only role:
# state.json, briefs/ and slices/ are what the scheduler and the integrator trust. plan.md is the
# team-leader's deliverable (PLANNING / PLAN ADOPTION), so that one role may write it.
RO_WRITE_ALLOW = ("/.opencode/oc-dev-team/reviews/", "/.opencode/oc-dev-team/research/",
                  "/.opencode/agent-memory/", "/.opencode/agent-memory-local/")
LEADER_WRITE_ALLOW = ("/.opencode/oc-dev-team/plan.md", "/.opencode/oc-dev-team/plan-", "/.opencode/oc-dev-team/plan_")


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
    deny(f"This role is read-only, and may write only its own report under .opencode/oc-dev-team/reviews/ "
         f"or .opencode/oc-dev-team/research/ (plus its memory dir; the team-leader also writes plan.md). "
         f"`{os.path.basename(path)}` is neither — the run state and other agents' briefings are off limits. "
         "Report findings; a programmer applies fixes.")


BASH_RO_DENY = [
    r"(^|[\s;&|])(rm|mv|cp|chmod|chown|mkdir|touch|truncate|dd|ln|rsync|tee|install)\b",
    r"\bsed\s+-[a-zA-Z]*i",
    r"\bperl\s+-[a-zA-Z]*i",
    r"(^|[^&<>])>{1,2}(?!\s*/dev/null\b|&)",
    r"\bgit\s+(add|commit|checkout|switch|reset|merge|rebase|push|pull|fetch|stash(?!\s+(?:list|show)\b)|clean|rm|mv|tag|apply|cherry-pick|revert|worktree|branch\s+-[dDmM]|filter-branch)\b",
    r"\b(npm|pnpm|yarn|bun)\s+(install|i|add|remove|uninstall|update|publish|link)\b",
    r"\b(pip|pip3|poetry|uv|conda|cargo|go|gem|composer)\s+(install|add|remove|uninstall|update|publish)\b",
    r"\bpython[0-9.]*\s+-c\s+.*open\([^)]*['\"][wa]",
]


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
    for pat in BASH_RO_DENY:
        if re.search(pat, cmd):
            deny(f"Read-only role: `{raw[:80]}` looks like it modifies files/packages/git state. "
                 "Use Read/Grep/Glob, run tests/linters/diffs only, and report instead of changing anything.")
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
    """Run one check function and return what it printed (every check ends in sys.exit)."""
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
    "question": "`question` is disabled in dev-team lanes: a background lane has nobody to answer it, so "
                "the run would block. Decide from the brief, or end with `## Status: Blocked` and the question.",
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
    `.oc-slice/allow` for a programmer, the plan's gate commands for a read-only role."""
    try:
        if prog:
            wt = find_slice_root(cwd)
            pinned = read_lines(wt / ".oc-slice" / "allow") if wt else []
            src = "`.oc-slice/allow`"
        else:
            pinned = plan_commands(find_state_root(cwd))
            src = "the plan's gate commands"
    except Exception:
        return ""
    forms = [p.strip() for p in pinned if p.strip()][:12]
    if not forms:
        return f" No commands are pinned for this lane ({src} is empty)."
    return f" Pinned forms from {src}: " + ", ".join(f"`{f}`" for f in forms) + "."


def oc_worktree_hint(cwd):
    """The worktree a programmer's deny message names: the claimed worktree `cwd` sits in, else
    `<root>/.opencode/oc-dev-team/wt/<slice id>` under the run's integration checkout."""
    try:
        own = find_slice_root(cwd)
        if own is not None:
            return str(own)
        root = find_state_root(cwd) or Path(cwd).resolve()
        return str(root / STATE_DIRNAME / "wt") + "/<slice id>"
    except Exception:
        return STATE_DIRNAME + "/wt/<slice id>"


def oc_fresh_lane(cwd, wd, command):
    """A programmer's shell `workdir` with no `.oc-slice/` yet: if it is `<root>/.opencode/oc-dev-team/wt/<id>`,
    allow exactly `python3 <state script> claim <id> --worktree <wd>` and deny everything else with a
    "run claim first" message. Returns (to the caller's own deny) when `wd` is not such a directory."""
    try:
        root = find_state_root(cwd)
        if root is None:
            return
        wtdir = (root / STATE_DIRNAME / "wt").resolve()
        wdp = Path(wd).resolve()
        if wdp.parent != wtdir:
            return
        script = json.loads((root / STATE_DIRNAME / "state.json").read_text()).get("script")
        argv = shlex.split(command)
    except Exception:
        return
    if (len(argv) == 6 and script and os.path.basename(argv[0]).startswith("python")
            and argv[1] == script and argv[2] == "claim" and argv[3] == wdp.name
            and argv[4] == "--worktree" and Path(argv[5]).resolve() == wdp):
        allow("dev-team: claiming this lane's worktree")
    deny(f"dev-team: this worktree ({wd}) is not claimed yet. Run `python3 <script> claim {wdp.name} "
         f"--worktree {wd}` first (the exact command is in your prompt); nothing else may run before it.")


def guard_oc(inp):
    """OpenCode tool-call bridge: {"tool", "args", "cwd", "role"} -> the check for that role.

    A lane has no working directory of its own, so the slice comes from the tool input: an edit
    path or a shell `workdir` inside `<root>/.opencode/oc-dev-team/wt/<id>/` selects slice <id>. A
    programmer's write outside every worktree, or its shell call without `workdir`, is denied
    naming the worktree. A lane has no interactive human to fall through to either, so anything a
    check leaves silent (its "defer to the normal ask-flow" signal) is made an explicit deny here,
    except the one silence that check already means as a real allow (a footprint-free edit inside
    a claimed worktree)."""
    role = (inp.get("role") or "").strip()
    if not role:
        allow()
    tool = (inp.get("tool") or "").lower()
    args = oc_args(inp.get("args"))
    if args is None:
        deny(f"dev-team: the `{tool}` arguments could not be parsed as a JSON object, so the call cannot "
             "be checked. Retry it with well-formed arguments.")
    prog = role == "programmer"
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
        if prog and not workdir:
            deny(f"dev-team: a programmer's `{tool}` call must pass `workdir` set to its slice worktree "
                 f"({oc_worktree_hint(cwd)}, the path in your brief). A lane has no working directory "
                 "of its own, so without `workdir` the command would run in the main checkout.")
        if workdir:
            wd = workdir if os.path.isabs(workdir) else os.path.abspath(os.path.join(cwd, workdir))
            if prog and find_slice_root(wd) is None:
                oc_fresh_lane(cwd, wd, command)
                deny(f"`workdir` {workdir} is outside your slice worktree ({oc_worktree_hint(cwd)}); "
                     "set `workdir` to the worktree path in your brief.")
            base["cwd"] = wd
        check = guard_bash if prog else guard_bash_ro
        out = oc_capture(check, dict(base, tool_input={"command": command}))
        if not out.strip():
            deny("dev-team: a lane has no interactive fallback, so a shell command that isn't "
                 "explicitly pre-approved is denied instead of silently allowed."
                 + oc_pinned_hint(base["cwd"], prog))
        sys.stdout.write(out)
        sys.exit(0)
    if tool in ("edit", "write", "multiedit"):
        p0 = args.get("path") or args.get("filePath") or ""
        if not isinstance(p0, str) or not p0.strip():
            deny(f"`{tool}` names no file (no `path` / `filePath`), so it cannot be checked. "
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
        wt = find_slice_root(os.path.dirname(ap)) if prog else None
        if wt is not None and os.path.relpath(ap, wt) == os.path.join(".oc-slice", "report.md"):
            out = json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                     "permissionDecision": "allow",
                                                     "permissionDecisionReason": "dev-team: the lane's own report file"}})
            continue
        if prog and wt is None:
            out = deny_json(f"`{p}` is outside any slice worktree. A programmer writes only inside its own "
                            f"worktree ({oc_worktree_hint(cwd)}), using absolute paths: a lane has no "
                            "working directory of its own.")
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
        {"stop": guard_stop, "oc": guard_oc}.get(mode, lambda i: allow())(inp)
    except SystemExit:
        raise
    except Exception:
        allow()  # fail-open


if __name__ == "__main__":
    main()
