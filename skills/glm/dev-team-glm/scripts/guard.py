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
  guard.py oc       OpenCode plugin bridge: {"tool", "args", "cwd", "role"} on stdin. edit/write/patch map to
                    tool_input.file_path, bash to tool_input.command. Role programmer -> edit/bash, any other
                    role -> edit-ro/bash-ro with agent_type = role, no role -> silent allow.

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


BASH_DENY = [
    (r"\bgit\s+(push|rebase|filter-branch|worktree|merge|stash|switch|cherry-pick|revert)\b", "integration/history commands are the Conductor's"),
    (r"\bgit\s+reset\s+(--hard|--merge|--soft)\b", "history rewriting is forbidden in a slice worktree"),
    (r"\bgit\s+branch\s+(-[dDmM]\b|--delete|--move|--force)", "branch surgery is forbidden in a slice worktree"),
    (r"\bgit\s+commit\b[^|;&]*--amend", "--amend would rewrite the RED audit trail; make a new commit"),
    (r"\bgit\s+(reflog\s+expire|update-ref|symbolic-ref|gc\s+--prune)\b", "history rewriting is forbidden"),
    (r"(^|[\s;&|])rm\s+-[a-zA-Z]*r[a-zA-Z]*\s+[^\s]*\.slice\b", "`.slice/` is dev-team metadata"),
    (r"(^|[\s;&|/])(sed\s+-i|tee|>>?)\s*[^\s]*\.slice/", "`.slice/` is dev-team metadata"),
    # any write-shaped mention of .slice/ at all: it is the record the integrator and the Stop gate
    # read, so an agent that can rewrite it can claim a RED commit it never made
    (r"\.slice/(red|red_files|base|mode|kind|footprint|allow|id|notest|criteria|root)\b[^\n]*"
     r"(>|>>|\bwrite\b|\bopen\s*\(|\bmv\b|\bcp\b|\brm\b)", "`.slice/` is dev-team metadata"),
    (r"(>|>>|\bmv\b|\bcp\b|\btee\b|\bwrite\s*\()[^\n]*\.slice/", "`.slice/` is dev-team metadata"),
    # the done/blocked markers are how `next` finds finished lanes: only the Stop gate writes them
    (r"(>|>>|\bmv\b|\bcp\b|\btee\b|\btouch\b|\bwrite\s*\()[^\n]*\.claude/dev-team/", "`.claude/dev-team/` is the Conductor's run state"),
]


def guard_bash(inp):
    raw = (inp.get("tool_input") or {}).get("command", "") or ""
    cmd, redirected = normalize_git(raw)
    if redirected:
        deny(f"Blocked `{raw[:80]}`: it points git at another checkout (`-C` / `--git-dir` / "
             "`--work-tree` / `GIT_DIR`). Every git command must act on YOUR worktree only.")
    for pat, why in BASH_DENY:
        if re.search(pat, cmd):
            deny(f"Blocked `{raw[:80]}`: {why}. Use commit-red / commit-green / commit-work for commits; "
                 "the Conductor merges.")
    if re.search(r"\bgit\s+checkout\b", cmd) and not re.search(r"\bgit\s+checkout\b[^|;&]*\s--(\s|$)", cmd):
        deny("`git checkout <ref>` would leave your slice branch. Only `git checkout [<ref>] -- <file>` (restore a file) is allowed.")
    if re.search(r"\bgit\s+reset\b", cmd) and not re.search(r"\bgit\s+reset\b[^|;&]*\s--(\s|$)", cmd):
        deny("`git reset <ref>` would drop commits (the RED audit trail). Only `git reset -- <file>` (unstage) is allowed.")
    wt = find_slice_root(inp.get("cwd") or os.getcwd())
    reason = bash_allow_reason(raw, wt, footprint=read_lines(wt / ".slice" / "footprint") if wt else [],
                               pinned=read_lines(wt / ".slice" / "allow") if wt else [])
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


def segment_allowed(argv, footprint, pinned, readonly=False, wt=None):
    """Why this single argv is pre-approved, or None."""
    if not argv:
        return None
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
        if head in ("npm", "pnpm", "yarn", "bun", "poetry", "uv", "cargo", "go", "bundle", "composer",
                    "mix", "dotnet", "flutter", "dart"):
            if not sub or sub in PKG_MANAGER_DENY_SUB:
                return None      # a bare `npm`/`yarn` is `install`; installs race the shared node_modules
        if head == "npx":
            # npx fetches and runs anything not installed: approve only a bin that already exists locally
            if not sub or any(a in ("-p", "--package", "-y", "--yes", "-c", "--call") for a in argv[1:]):
                return None
            base = Path(wt) if wt else Path.cwd()
            if not (base / "node_modules" / ".bin" / sub).exists():
                return None
        if head == "deno" and (sub not in ("test", "lint", "fmt", "check", "task") or any(a.startswith("--allow") for a in argv[1:])):
            return None
        if head in ("python", "python3", "node", "ruby", "php", "bash", "sh", "elixir"):
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

# Reports and memory only. `.claude/dev-team/` as a whole is NOT writable by a read-only role:
# state.json, briefs/ and slices/ are what the scheduler and the integrator trust. plan.md is the
# team-leader's deliverable (PLANNING / PLAN ADOPTION), so that one role may write it.
RO_WRITE_ALLOW = ("/.claude/dev-team/reviews/", "/.claude/dev-team/research/",
                  "/.claude/agent-memory/", "/.claude/agent-memory-local/")
LEADER_WRITE_ALLOW = ("/.claude/dev-team/plan.md", "/.claude/dev-team/plan-", "/.claude/dev-team/plan_")


def guard_edit_ro(inp):
    path = tool_path(inp)
    if not path:
        allow()
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
    root = find_state_root(inp.get("cwd") or os.getcwd())
    allow(bash_allow_reason(raw, None, footprint=[], pinned=plan_commands(root), readonly=True))


OC_PATCH_PATH = re.compile(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)$", re.M)


def oc_patch_paths(text):
    return [p.strip() for p in OC_PATCH_PATH.findall(text or "") if p.strip()]


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
    args = inp.get("args") or {}
    prog = role == "programmer"
    cwd = inp.get("cwd") or os.getcwd()
    base = {"cwd": cwd, "agent_type": role}
    if tool == "bash":
        check = guard_bash if prog else guard_bash_ro
        out = oc_capture(check, dict(base, tool_input={"command": args.get("command") or ""}))
        if not out.strip():
            deny("dev-team: OpenCode has no interactive fallback, so a bash command that isn't "
                 "explicitly pre-approved is denied instead of silently allowed.")
        sys.stdout.write(out)
        sys.exit(0)
    if tool in ("edit", "write"):
        paths = [args.get("filePath") or ""]
    elif tool in ("patch", "apply_patch"):
        paths = oc_patch_paths(args.get("patchText"))
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
