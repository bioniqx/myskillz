#!/usr/bin/env python3
"""debug_tool.py - one call per debugging phase, parallelism outside the model turn.

Subcommands
  probe       whole evidence phase in ONE call (snapshot + frames + grep + repro + triage)
  run         N shell commands in parallel, capped output, exit codes kept
  experiment  N hypotheses tested control-vs-treatment in isolated worktrees (up to 64)
  scan        N judgment workers fanned out to the model API directly (at most 8 at once)
  doctor      environment / key / harness check
  setup       print or apply harness config

Stdlib only. Python 3.8+. Every subcommand supports -h.
"""

import argparse
import concurrent.futures as cf
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SKILL = SCRIPTS.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import zai_client
import oc_harness
WORKER_AGENT = "glm-debug-worker"
MAXJ = 64  # local CPU jobs (run/probe/experiment)
MAX_API = 8  # concurrent model/API calls (scan workers, subagent lanes)
AGENT_LANES = 8  # default agent-lane wave width: the provider's full concurrent-call budget; OC_MAX_LANES overrides, clamped to MAX_API
BASH = shutil.which("bash") or "/bin/sh"
try:  # survive `| head`
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError, OSError):
    pass

# ---------------------------------------------------------------- shell utils


def cpus():
    try:
        return os.cpu_count() or 4
    except Exception:
        return 4


def agent_lanes():
    """Agent-lane wave width: OC_MAX_LANES, default 8, ceiling MAX_API, 0 gives 1, bad value gives 8."""
    v = os.environ.get("OC_MAX_LANES", "").strip()
    return max(1, min(MAX_API, int(v))) if v.isdigit() else AGENT_LANES


def clamp(j, default, cap=MAXJ):
    """Parse a -j value. 0, negative or unparseable means `default`."""
    try:
        j = int(j)
    except (TypeError, ValueError):
        j = default
    if j <= 0:
        j = default
    return max(1, min(cap, int(j)))


def sh(cmd, cwd=None, timeout=None, env=None):
    """Run a shell command. Returns (rc, combined output)."""
    e = dict(os.environ)
    if env:
        e.update({k: str(v) for k, v in env.items()})
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, env=e, timeout=timeout,
                           executable=BASH, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return p.returncode, p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as ex:
        out = ex.stdout.decode("utf-8", "replace") if ex.stdout else ""
        return 124, out + "\n[timed out after %ss]" % timeout
    except Exception as ex:  # pragma: no cover
        return 127, "[failed to run: %s]" % ex


def tail(text, n):
    lines = text.rstrip("\n").split("\n")
    if len(lines) <= n:
        return "\n".join(lines)
    return "[... %d lines cut ...]\n" % (len(lines) - n) + "\n".join(lines[-n:])


def head(text, n):
    lines = text.rstrip("\n").split("\n")
    if len(lines) <= n:
        return "\n".join(lines)
    return "\n".join(lines[:n]) + "\n[... %d more lines ...]" % (len(lines) - n)


def repo_root(d="."):
    rc, out = sh("git rev-parse --show-toplevel", cwd=d)
    return out.strip() if rc == 0 and out.strip() else None


def pmap(fn, items, j):
    """Ordered parallel map."""
    if not items:
        return []
    with cf.ThreadPoolExecutor(max_workers=clamp(j, 8)) as ex:
        return list(ex.map(fn, items))


# ------------------------------------------------------------ error parsing

FRAME_RES = [
    # /path/file.ts:12:3  |  path/file.py:12  |  at fn (path/file.js:12:3)
    re.compile(r'(?:^|[\s(\'"@])((?:[A-Za-z]:)?[./\w@+-]*[\w+-]+\.[A-Za-z]{1,6}):(\d+)(?::(\d+))?'),
    # python:  File "path/x.py", line 12
    re.compile(r'File "([^"]+)", line (\d+)'),
    # msbuild / C#:  path\file.cs(12,3)
    re.compile(r'((?:[A-Za-z]:)?[\\/\w.+-]+\.[A-Za-z]{1,6})\((\d+),\d+\)'),
    # java:  at com.x.Y(File.java:12)
    re.compile(r'\(([\w$.+-]+\.(?:java|kt|scala|groovy)):(\d+)\)'),
]

SKIP_FRAME = re.compile(
    r'node_modules|site-packages|/dist/|/build/|\.min\.|internal/|<anonymous>|'
    r'/usr/lib|/usr/local/lib|runtime/|vendor/|\.pyenv|/go/pkg/|target/glm-debug/deps')

SYMBOL_RES = [
    re.compile(r"Property '([\w$]+)' does not exist"),
    re.compile(r"Cannot find name '([\w$]+)'"),
    re.compile(r"Cannot find module '([^']+)'"),
    re.compile(r"NameError: name '([\w]+)'"),
    re.compile(r"AttributeError: .*has no attribute '([\w]+)'"),
    re.compile(r"ImportError: cannot import name '([\w]+)'"),
    re.compile(r"ModuleNotFoundError: No module named '([^']+)'"),
    re.compile(r"undefined: ([\w.]+)"),
    re.compile(r"'([\w$]+)' is not defined"),
    re.compile(r"([\w$]+) is not a function"),
    re.compile(r"cannot find symbol\s+symbol:\s+\w+ ([\w$]+)"),
    re.compile(r"unresolved reference: ?'?([\w$]+)"),
    re.compile(r"no field or method `([\w$]+)`"),
    re.compile(r"reading '([\w$]+)'"),
    re.compile(r"KeyError: '([^']+)'"),
    re.compile(r"key not found: ?\"?([\w$.-]+)"),
    re.compile(r"no attribute '([\w]+)'"),
    re.compile(r"has no field or method [`'\"]([\w$]+)"),
    re.compile(r"column [\"']?([\w$]+)[\"']? does not exist"),
    re.compile(r"AssertionError: ([\w$ ]{4,40})$", re.M),
]

# deterministic-and-local: the cause is fully visible at the named line
COMPILE_RE = re.compile(
    r'\bTS\d{3,5}\b|SyntaxError|IndentationError|ImportError|ModuleNotFoundError|'
    r'cannot find (?:module|name|symbol)|is not defined|NameError|^undefined: |'
    r'does not exist on type|error\[E\d+\]|unexpected token|unresolved reference|'
    r'expected .{0,30}(?:found|but got)|Parse error|no such file or directory|'
    r'declared and not used|missing return|cannot use .* as .* value|'
    r'Module .* has no exported member|Expected \d+ arguments', re.I | re.M)

# the bad value was created elsewhere -> never FAST
NULLISH_RE = re.compile(
    r"Cannot read propert(?:y|ies)|of undefined|of null|NoneType|nil pointer|"
    r"NullPointerException|unwrap\(\) on an? `None`|index out of range|"
    r"KeyError|IndexError|undefined is not|null is not|segmentation fault|"
    r"Maximum call stack|out of memory|ECONNREFUSED|ETIMEDOUT|deadlock", re.I)

SWARM_RE = re.compile(
    r"flak|intermittent|sometimes|randomly|\brace\b|\braces\b|\bracy\b|timeout|timed out|hangs?\b|"
    r"only in CI|passes locally|slow|performance|regress|worked before|"
    r"used to work|non-?deterministic|multi-?component|multiple (?:components|services|layers)|"
    r"(?:many|several) (?:plausible |possible )?causes|culprit unknown|unknown culprit", re.I)


def parse_frames(text, root, limit=8):
    """Return [(relpath, line)] for in-repo frames, in order, deduped."""
    rootp = Path(root) if root else Path.cwd()
    seen, out = set(), []
    for line in text.split("\n"):
        if SKIP_FRAME.search(line):
            continue
        for rx in FRAME_RES:
            for m in rx.finditer(line):
                raw, ln = m.group(1), m.group(2)
                cands = []
                p = Path(raw)
                if p.is_absolute():
                    cands.append(p)
                else:
                    cands += [rootp / raw, Path.cwd() / raw]
                hit = next((c for c in cands if c.is_file()), None)
                if hit is None and "/" not in raw and "\\" not in raw:
                    # bare filename (java/kotlin): locate it
                    rc, o = sh("git ls-files '*%s' 2>/dev/null | head -3" % raw, cwd=str(rootp))
                    for cand in [x for x in o.split("\n") if x.strip()]:
                        c = rootp / cand
                        if c.is_file():
                            hit = c
                            break
                if hit is None:
                    continue
                try:
                    rel = str(hit.resolve().relative_to(rootp.resolve()))
                except Exception:
                    rel = str(hit)
                key = (rel, ln)
                if key in seen:
                    continue
                seen.add(key)
                out.append((rel, int(ln)))
                if len(out) >= limit:
                    return out
    return out


def parse_symbols(text, limit=4):
    out, seen = [], set()
    for rx in SYMBOL_RES:
        for m in rx.finditer(text):
            s = m.group(1)
            if len(s) < 2 or s in seen:
                continue
            seen.add(s)
            out.append(s)
            if len(out) >= limit:
                return out
    return out


def error_signature(text):
    """The most greppable single line of the error."""
    for line in text.split("\n"):
        s = line.strip()
        if len(s) < 8 or SKIP_FRAME.search(s):
            continue
        if re.search(r"error|fail|exception|panic|assert|expected", s, re.I):
            s = re.sub(r'(?:[A-Za-z]:)?[./\w-]*/[\w./-]+:\d+(:\d+)?', '', s)
            s = re.sub(r'\b0x[0-9a-f]+\b|\b\d{4,}\b', '', s)
            s = re.sub(r'\s+', ' ', s).strip(' -:')
            if len(s) > 12:
                return s[:90]
    return text.strip().split("\n")[0][:90]


# ------------------------------------------------------------------- probe

def read_window(root, rel, line, ctx):
    p = Path(root) / rel if not Path(rel).is_absolute() else Path(rel)
    try:
        lines = p.read_text("utf-8", "replace").split("\n")
    except Exception as e:
        return "-- %s:%d  [unreadable: %s]" % (rel, line, e)
    a = max(0, line - 1 - ctx)
    b = min(len(lines), line + ctx)
    w = ["-- %s:%d  (lines %d-%d)" % (rel, line, a + 1, b)]
    for i in range(a, b):
        mark = ">>" if i == line - 1 else "  "
        w.append("%s%5d| %s" % (mark, i + 1, lines[i][:220]))
    return "\n".join(w)


def grep(root, pattern, literal, cap):
    q = shlex.quote(pattern)
    flag = "-nF" if literal else "-nE"
    in_git = root and Path(root, ".git").exists()
    if in_git:
        cmd = "git grep -I %s %s -- . | head -%d" % (flag, q, cap)
    else:
        cmd = ("grep -rI %s %s . --exclude-dir=node_modules --exclude-dir=.git "
               "--exclude-dir=dist --exclude-dir=build --exclude-dir=venv "
               "--exclude-dir=.venv --exclude-dir=target | head -%d" % (flag, q, cap))
    rc, out = sh(cmd, cwd=root or ".", timeout=60)
    return out.strip()


def cmd_probe(a):
    root = repo_root(a.dir) or os.path.abspath(a.dir)
    err = ""
    if a.error_file:
        err = Path(a.error_file).read_text("utf-8", "replace")
    if a.error:
        err = (err + "\n" + a.error).strip()
    if not err and not a.cmd:
        print("probe needs --error/--error-file and/or --cmd. See -h.", file=sys.stderr)
        return 2

    j = clamp(a.jobs, min(MAXJ, cpus() * 4))
    jobs = {}

    # 1. repro runs (first one measures duration, then auto flake-check)
    repro = []

    def run_repro(_i):
        t0 = time.time()
        rc, out = sh("set -o pipefail; " + a.cmd, cwd=root, timeout=a.timeout)
        return {"rc": rc, "out": out, "sec": round(time.time() - t0, 1)}

    with cf.ThreadPoolExecutor(max_workers=j) as ex:
        if a.cmd:
            fut_first = ex.submit(run_repro, 0)
        jobs["snapshot"] = ex.submit(
            sh, "bash %s %s" % (shlex.quote(str(SCRIPTS / "snapshot.sh")), shlex.quote(root)),
            None, 120)
        symbols = list(a.symbol or []) + [s for s in parse_symbols(err) if s not in (a.symbol or [])]
        symbols = symbols[:5]
        sig = error_signature(err) if err else ""
        if sig:
            jobs["grep_error"] = ex.submit(grep, root, sig, True, a.max_grep)
        for s in symbols:
            jobs["grep_" + s] = ex.submit(grep, root, s, True, a.max_grep)
            jobs["hist_" + s] = ex.submit(
                sh, "git log --oneline -S%s -6 -- . 2>/dev/null" % shlex.quote(s), root, 60)
        if a.since:
            jobs["diffstat"] = ex.submit(
                sh, "git diff %s..HEAD --stat 2>/dev/null | tail -25" % shlex.quote(a.since), root, 60)
            jobs["difflog"] = ex.submit(
                sh, "git log --oneline %s..HEAD 2>/dev/null | head -20" % shlex.quote(a.since), root, 60)
        frames = parse_frames(err, root, a.max_frames) if err else []
        for rel, ln in frames:
            jobs["frame_%s_%d" % (rel, ln)] = ex.submit(read_window, root, rel, ln, a.ctx)

        if a.cmd:
            first = fut_first.result()
            repro.append(first)
            extra = 0
            if a.flake_check == "auto":
                extra = 2 if (first["sec"] < 20 and first["rc"] != 0) else 0
            else:
                extra = max(0, clamp(a.flake_check, 1) - 1)
            if extra:
                # serial on purpose: parallel runs in one tree fake flakiness
                repro += [run_repro(i) for i in range(1, extra + 1)]

    # ------------------------------------------------------------ triage
    rcs = [r["rc"] for r in repro]
    sigs = set((r["rc"], error_signature(r["out"])) for r in repro)
    deterministic = (len(sigs) <= 1)
    corpus = err + "\n" + "\n".join(r["out"][-4000:] for r in repro)
    if not deterministic:
        lane, why = "SWARM", "repro is not reproducible: %d distinct outcomes in %d runs (exit codes %s)" % (
            len(sigs), len(repro), rcs)
    elif NULLISH_RE.search(corpus):
        lane, why = "STANDARD", "bad value / resource error: it was created upstream of the crash site"
    elif SWARM_RE.search(corpus):
        lane, why = "SWARM", "text names flakiness, timing, performance or a regression"
    elif COMPILE_RE.search(corpus) and frames:
        lane, why = "FAST", "deterministic compile/name error with a resolved in-repo frame"
    elif COMPILE_RE.search(corpus):
        lane, why = "STANDARD", "compile-class error but no in-repo frame resolved"
    else:
        lane, why = "STANDARD", "reproducible, cause not visible at the error site"

    # ------------------------------------------------------------ output
    o = []
    o.append("S=%s" % SCRIPTS)
    o.append("ROOT=%s" % root)
    o.append("LANE: %s  -- %s" % (lane, why))
    if symbols:
        o.append("SYMBOLS: %s" % ", ".join(symbols))
    if sig:
        o.append("SIGNATURE: %s" % sig)
    o.append("")

    if repro:
        o.append("== REPRO (%d run%s) ==" % (len(repro), "s" if len(repro) > 1 else ""))
        o.append("cmd: %s" % a.cmd)
        o.append("exit codes: %s   seconds: %s" % (rcs, [r["sec"] for r in repro]))
        o.append(tail(repro[0]["out"], a.max_out))
        if not deterministic:
            base_sig = (repro[0]["rc"], error_signature(repro[0]["out"]))
            for r in repro[1:]:
                if (r["rc"], error_signature(r["out"])) != base_sig:
                    o.append("-- differing run (rc=%d) --" % r["rc"])
                    o.append(tail(r["out"], 25))
                    break
        o.append("")

    if frames:
        o.append("== IN-REPO FRAMES (%d, deepest first as printed) ==" % len(frames))
        for rel, ln in frames:
            o.append(jobs["frame_%s_%d" % (rel, ln)].result())
            o.append("")
    elif err:
        o.append("== IN-REPO FRAMES ==")
        o.append("none resolved. Pass --error-file with the full trace, or --symbol <name>.")
        o.append("")

    hits = []
    if sig and jobs.get("grep_error"):
        v = jobs["grep_error"].result()
        if v:
            hits.append(("error text: %s" % sig, v))
    for s in symbols:
        v = jobs["grep_" + s].result()
        if v:
            hits.append(("symbol: %s" % s, v))
    if hits:
        o.append("== GREP ==")
        for title, v in hits:
            o.append("-- %s" % title)
            o.append(head(v, a.max_grep))
        o.append("")

    hist = []
    for s in symbols:
        v = jobs["hist_" + s].result()[1].strip()
        if v:
            hist.append("-- commits touching '%s'\n%s" % (s, v))
    if a.since:
        ds = jobs["diffstat"].result()[1].strip()
        dl = jobs["difflog"].result()[1].strip()
        if dl:
            hist.append("-- commits %s..HEAD\n%s" % (a.since, dl))
        if ds:
            hist.append("-- diffstat %s..HEAD\n%s" % (a.since, ds))
    if hist:
        o.append("== HISTORY ==")
        o.extend(hist)
        o.append("")

    o.append("== SNAPSHOT ==")
    o.append(head(jobs["snapshot"].result()[1], 45))
    o.append("")

    o.append("== NEXT ==")
    if lane == "FAST":
        o.append("1. Write ROOT CAUSE: <X> causes <Y> because <Z>, citing a line printed above.")
        o.append("2. Apply the minimal fix at that line.")
        o.append("3. One call: python3 %s/debug_tool.py run -- %s"
                 % (SCRIPTS, shlex.quote(a.cmd) if a.cmd else "<build/test cmd>"))
    elif lane == "STANDARD":
        o.append("1. If a bad value crashed downstream, trace it to where it is CREATED (references/root-cause-tracing.md).")
        o.append("2. Write 2-4 hypotheses, each with a control command and a one-variable treatment.")
        o.append("3. One call proves them all:")
        o.append("   python3 %s/debug_tool.py experiment --template > /tmp/exp.json   # fill it in" % SCRIPTS)
        o.append("   python3 %s/debug_tool.py experiment --spec /tmp/exp.json -j 8" % SCRIPTS)
    else:
        o.append("1. Read references/parallel-playbook.md in the SAME call as the first command below.")
        o.append("2. Measure, do not eyeball:")
        o.append("   bash %s/stress.sh -n 200 -- %s" % (SCRIPTS, a.cmd or "<single failing test>"))
        o.append("   (regression, culprit unknown) bash %s/bisect-parallel.sh -j 15 <good> HEAD -- <repro>" % SCRIPTS)
        o.append("3. Then one experiment call for all hypotheses (see experiment --template).")
    print("\n".join(o))
    return 0


# --------------------------------------------------------------------- run

def cmd_run(a):
    cmds = list(a.cmds)
    if a.file:
        cmds += [l.strip() for l in Path(a.file).read_text().split("\n") if l.strip() and not l.startswith("#")]
    if not cmds:
        print("run needs at least one command. See -h.", file=sys.stderr)
        return 2
    j = clamp(a.jobs, min(MAXJ, len(cmds)))
    root = a.dir

    def one(idx_cmd):
        i, c = idx_cmd
        t0 = time.time()
        rc, out = sh("set -o pipefail; " + c, cwd=root, timeout=a.timeout)
        return {"i": i, "cmd": c, "rc": rc, "sec": round(time.time() - t0, 1), "out": out}

    t_start = time.time()
    res = pmap(one, list(enumerate(cmds)), j)
    wall = time.time() - t_start
    bad = [r for r in res if r["rc"] != 0]
    print("S=%s" % SCRIPTS)
    print("RESULT: %d/%d exited non-zero (%d parallel, %.1fs wall)"
          % (len(bad), len(res), j, wall))
    for r in res:
        print("\n== [%d] rc=%d %.1fs :: %s" % (r["i"], r["rc"], r["sec"], r["cmd"]))
        print(tail(r["out"], a.max_out if r["rc"] != 0 else min(a.max_out, 20)))
    print("\nVERIFIED BY: " + " ; ".join("%s -> rc=%d" % (r["cmd"], r["rc"]) for r in res))
    return 1 if bad else 0


# -------------------------------------------------------------- experiment

TEMPLATE = [
    {
        "id": "h1",
        "hypothesis": "TZ is unset in CI so the date parser falls back to local time",
        "cmd": "npx vitest run src/date.test.ts",
        "env": {"TZ": "UTC"},
        "expect": "treatment_passes",
        "runs": 1
    },
    {
        "id": "h2",
        "hypothesis": "the cache is never invalidated after write",
        "cmd": "npx vitest run src/cache.test.ts",
        "patch_file": "/tmp/h2.diff",
        "expect": "treatment_passes",
        "runs": 1
    },
    {
        "id": "h3",
        "hypothesis": "the failure needs the seed from the full suite",
        "cmd": "npx vitest run src/queue.test.ts",
        "treatment_cmd": "npx vitest run --sequence.shuffle --sequence.seed=1 src/queue.test.ts",
        "expect": "treatment_fails",
        "runs": 5
    }
]


DEFAULT_LINKS = ("node_modules", ".venv", "venv", "vendor/bundle")


def default_links(root):
    """Ignored dependency dirs that exist in root: linked into every worktree."""
    out = []
    for d in DEFAULT_LINKS:
        if os.path.isdir(os.path.join(root, d)):
            rc, _ = sh("git check-ignore -q %s" % shlex.quote(d), cwd=root, timeout=30)
            if rc == 0:
                out.append(d)
    return out


def copy_untracked(root, path):
    """Copy untracked, non-ignored files: HEAD plus the WIP diff misses them."""
    rc, out = sh("git ls-files --others --exclude-standard -z", cwd=root, timeout=120)
    if rc != 0:
        return 0
    n = 0
    for rel in out.split("\0"):
        if not rel:
            continue
        src, dst = os.path.join(root, rel), os.path.join(path, rel)
        if not (os.path.isfile(src) or os.path.islink(src)) or os.path.lexists(dst):
            continue
        os.makedirs(os.path.dirname(dst) or path, exist_ok=True)
        try:
            shutil.copy2(src, dst, follow_symlinks=False)
            n += 1
        except OSError:
            pass
    return n


def make_worktree(root, path, links, wip_patch):
    rc, out = sh("git worktree add --detach --force %s HEAD" % shlex.quote(path), cwd=root, timeout=300)
    if rc != 0:
        return "worktree add failed: " + tail(out, 5)
    if wip_patch and os.path.getsize(wip_patch) > 0:
        sh("git apply %s" % shlex.quote(wip_patch), cwd=path, timeout=120)
    copy_untracked(root, path)
    for d in links or []:
        src, dst = os.path.join(root, d), os.path.join(path, d)
        if os.path.exists(src) and not os.path.lexists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                os.symlink(src, dst)
            except OSError:
                pass
    return None


def apply_treatment_patch(wt, patch, wip_patch):
    """Apply patch on top of the WIP. If it does not apply there but applies on
    HEAD once the WIP is reversed, the patch already contains the WIP.
    Returns (ok, note)."""
    rc, out = sh("git apply %s" % shlex.quote(patch), cwd=wt, timeout=120)
    if rc == 0:
        return True, ""
    if wip_patch and os.path.getsize(wip_patch) > 0:
        rrc, _ = sh("git apply -R %s" % shlex.quote(wip_patch), cwd=wt, timeout=120)
        if rrc == 0:
            rc2, _ = sh("git apply %s" % shlex.quote(patch), cwd=wt, timeout=120)
            if rc2 == 0:
                return True, "patch already contains the WIP: applied on HEAD"
            sh("git apply %s" % shlex.quote(wip_patch), cwd=wt, timeout=120)
    return False, "patch did not apply: " + tail(out, 4)


def cmd_experiment(a):
    if a.template:
        print(json.dumps(TEMPLATE, indent=2))
        return 0
    root = repo_root(a.dir)
    if not root:
        print("experiment needs a git repository (isolation uses worktrees).", file=sys.stderr)
        return 2
    spec = json.loads(Path(a.spec).read_text()) if a.spec else json.load(sys.stdin)
    if isinstance(spec, dict):
        spec = [spec]
    for i, h in enumerate(spec):
        h.setdefault("id", "h%d" % (i + 1))
        if not h.get("cmd"):
            print("hypothesis %s has no 'cmd'." % h["id"], file=sys.stderr)
            return 2
        if h.get("patch_file"):
            # resolve against the caller's cwd, never the arm's worktree
            pf = os.path.abspath(os.path.expanduser(str(h["patch_file"])))
            if not os.path.isfile(pf):
                print("hypothesis %s: patch_file %s not found (relative paths resolve "
                      "against %s)." % (h["id"], pf, os.getcwd()), file=sys.stderr)
                return 2
            h["patch_file"] = pf
    work =tempfile.mkdtemp(prefix="sdexp.", dir=os.environ.get("TMPDIR", "/tmp"))
    wip = os.path.join(work, "wip.patch")
    with open(wip, "wb") as f:
        subprocess.run("git diff HEAD --binary", shell=True, cwd=root, stdout=f, executable=BASH)

    # Every arm gets its OWN worktree: no state (caches, .pyc, build dirs, DBs) leaks
    # between control and treatment, and both arms run at the same time.
    arms = [(h, side) for h in spec for side in ("control", "treatment")]
    auto_links = default_links(root)
    j = clamp(a.jobs, min(MAXJ, max(2, len(arms))))
    cpu_budget = max(2, cpus())
    if j > cpu_budget * 2:
        print("note: -j %d on %d CPUs; CPU-bound test commands will contend."
              % (j, cpus()), file=sys.stderr)
    print("S=%s\nexperiment: %d hypotheses x 2 arms, %d parallel, work dir %s"
          % (SCRIPTS, len(spec), j, work), file=sys.stderr)

    def run_arm(job):
        h, side = job
        hid = re.sub(r"\W+", "_", str(h["id"]))
        wt = os.path.join(work, "w_%s_%s" % (hid, side))
        r = {"id": h["id"], "side": side, "wt": wt, "fails": None, "out": "", "note": ""}
        links = list(h.get("link") or [])
        links += [d for d in auto_links if d not in links]
        err = make_worktree(root, wt, links, wip)
        if err:
            r["note"] = err
            return r
        if side == "treatment" and h.get("patch_file"):
            ok, note = apply_treatment_patch(wt, h["patch_file"], wip)
            r["note"] = note
            if not ok:
                return r
        if side == "treatment" and h.get("setup"):
            sh(h["setup"], cwd=wt, timeout=h.get("timeout", a.timeout))
        cmd = h.get("treatment_cmd", h["cmd"]) if side == "treatment" else h["cmd"]
        env = dict(h.get("env") or {}) if side == "treatment" else {}
        sub = h.get("cwd", "")
        cwd = os.path.join(wt, sub) if sub else wt
        runs = max(1, int(h.get("runs", 1)))
        fails, last = 0, ""
        for k in range(runs):
            e = dict(env)
            e["SD_EXPERIMENT"] = str(h["id"])
            e["SD_ARM"] = side
            e["SD_RUN"] = str(k)
            e["TMPDIR"] = os.path.join(wt, ".sdtmp%d" % k)
            os.makedirs(e["TMPDIR"], exist_ok=True)
            rc, out = sh(cmd, cwd=cwd, timeout=h.get("timeout", a.timeout), env=e)
            if rc != 0:
                fails += 1
                last = out
            elif not last:
                last = out
        r["fails"], r["runs"], r["out"], r["cmd"] = fails, runs, last, cmd
        return r

    def is_serial(job):
        return int(job[0].get("runs", 1)) > 1

    armres = pmap(run_arm, [job for job in arms if not is_serial(job)], j)
    armres += [run_arm(job) for job in arms if is_serial(job)]
    by = {}
    for r in armres:
        by.setdefault(r["id"], {})[r["side"]] = r

    res = []
    for h in spec:
        c, t = by[h["id"]]["control"], by[h["id"]]["treatment"]
        r = {"id": h["id"], "hypothesis": h.get("hypothesis", ""), "wts": [c["wt"], t["wt"]]}
        if c["fails"] is None or t["fails"] is None:
            r["verdict"] = "INCONCLUSIVE"
            r["note"] = (c["note"] or t["note"] or "arm did not run")
            res.append(r)
            continue
        r["control"] = "%d/%d failed" % (c["fails"], c["runs"])
        r["treatment"] = "%d/%d failed" % (t["fails"], t["runs"])
        arm_note = t.get("note", "")
        expect = h.get("expect", "treatment_passes")
        if expect == "treatment_passes" and c["fails"] == 0:
            r["verdict"], r["note"] = "INCONCLUSIVE", (
                "the control did not reproduce the failure in its worktree; the repro likely "
                "needs a file the worktree lacks - list it under \"link\" or commit it")
        elif c["fails"] == t["fails"]:
            r["verdict"], r["note"] = "REFUTED", "the variable changed nothing"
        elif expect == "treatment_passes" and t["fails"] == 0:
            r["verdict"] = "CONFIRMED"
        elif expect == "treatment_fails" and c["fails"] == 0 and t["fails"] > 0:
            r["verdict"] = "CONFIRMED"
        elif (expect == "treatment_passes" and t["fails"] < c["fails"]) or \
                (expect == "treatment_fails" and t["fails"] > c["fails"]):
            r["verdict"], r["note"] = "INCONCLUSIVE", (
                "the failure rate moved the predicted way but one arm did not pass every run while "
                "the other failed; prove it with stress.sh -b F/N (Fisher p < 0.05)")
        else:
            r["verdict"], r["note"] = "REFUTED", "the outcome moved opposite to the prediction"
        if max(c["runs"], t["runs"]) > 1 and abs(c["fails"] - t["fails"]) < 2:
            r["note"] = (r.get("note", "") + " (difference of 1 run over %d is not significant - "
                         "prove a flaky fix with stress.sh -b F/N, Fisher p < 0.05)" % max(c["runs"], t["runs"])).strip()
        if arm_note:
            r["note"] = (r.get("note", "") + " (" + arm_note + ")").strip()
        log =os.path.join(work, "log.%s.txt" % re.sub(r"\W+", "_", str(h["id"])))
        Path(log).write_text("== control: %s ==\n%s\n\n== treatment: %s ==\n%s\n"
                             % (c.get("cmd", ""), tail(c["out"], 150), t.get("cmd", ""), tail(t["out"], 150)))
        r["log"] = log
        r["evidence"] = tail(t["out"] if t["fails"] else c["out"], 18)
        res.append(r)

    confirmed = [r for r in res if r["verdict"] == "CONFIRMED"]
    print("\n== EXPERIMENTS ==")
    for r in res:
        print("\n[%s] %s" % (r["verdict"], r["id"]))
        print("  hypothesis: %s" % r["hypothesis"])
        if "control" in r:
            print("  control: %s   treatment: %s" % (r["control"], r["treatment"]))
        if r.get("note"):
            print("  note: %s" % r["note"])
        if r.get("log"):
            print("  log: %s" % r["log"])
        if r.get("evidence"):
            print("  evidence tail:")
            print("\n".join("    " + x for x in r["evidence"].split("\n")[-12:]))
    print("\nSUMMARY: %d CONFIRMED, %d REFUTED, %d INCONCLUSIVE of %d"
          % (len(confirmed), len([r for r in res if r["verdict"] == "REFUTED"]),
             len([r for r in res if r["verdict"] == "INCONCLUSIVE"]), len(res)))
    if len(confirmed) > 1:
        print("More than one CONFIRMED -> one upstream cause or an interaction. Test the combination "
              "or trace upstream before fixing.")
    if not confirmed:
        print("None confirmed -> get new evidence, do not widen the guessing. A candidate FIX that "
              "failed counts toward the 3-fix stop; a diagnostic toggle does not.")
    if not a.keep:
        for r in res:
            for w in r["wts"]:
                sh("git worktree remove --force %s" % shlex.quote(w), cwd=root)
        sh("git worktree prune", cwd=root)
        print("(worktrees removed; logs kept in %s)" % work)
    else:
        print("(worktrees kept in %s)" % work)
    return 0 if confirmed else 1


# -------------------------------------------------------------------- scan

TIERS = {
    "light": ("glm-5.3-flash", "low"),
    "std": ("glm-5.3-flash", "high"),
    "deep": ("glm-5.3", "max"),
}

SYS_PROMPT = (
    "You are a debugging glm-investigator. Root cause before fix. Evidence means output, traces, "
    "diffs or code you were shown - never a guess. Answer in at most 12 lines, no preamble, "
    "in exactly this shape:\n"
    "VERDICT: CONFIRMED | REFUTED | INCONCLUSIVE\n"
    "EVIDENCE: <file:line or exact output lines>\n"
    "ROOT CAUSE: <X causes Y because Z> (only if CONFIRMED)\n"
    "FIX: <at most 10 lines of diff, or n/a>\n"
    "NEW LEADS: <at most 2, or n/a>"
)

def find_key():
    return zai_client.find_key()


def api_call(key, base, model, effort, system, user, max_tokens, anthropic, client=None):
    if client is None:
        route = "anthropic" if anthropic else "openai"
        client = zai_client.Client(key, base=base, route=route)
    try:
        return client.call(model, effort, system, user, max_tokens)
    except Exception as e:
        return "VERDICT: INCONCLUSIVE\nEVIDENCE: %s" % e


SCAN_STOPWORDS = frozenset(
    "about after also because been before being cause caused causes could does doesn each "
    "error errors every fail failing fails failure from have here into just like made make "
    "makes more most only other over same should some such than that their them then there "
    "they this under used using very were what when where which while will with would wrong "
    "happen happens work works working".split())
SCAN_KEYWORDS = 5
SCAN_WINDOWS = 4
SCAN_WINDOW_CTX = 8
SCAN_CODE_CHARS = 6000


def question_keywords(question, limit=SCAN_KEYWORDS):
    """Content words of the question, stopwords dropped, first-seen order, deduped."""
    out, seen = [], set()
    for w in re.findall(r"[A-Za-z_][\w.]{3,}", question or ""):
        lw = w.lower()
        if lw in SCAN_STOPWORDS or lw in seen:
            continue
        seen.add(lw)
        out.append(w)
        if len(out) >= limit:
            break
    return out


def grep_area(root, area, words, cap):
    """ONE case-insensitive literal grep for all words, scoped to the area."""
    if not words:
        return ""
    pats = " ".join("-e %s" % shlex.quote(w) for w in words)
    if root and Path(root, ".git").exists():
        cmd = "git grep -I -n -i -F %s -- %s | head -%d" % (pats, shlex.quote(area), cap)
    else:
        cmd = ("grep -rIn -H -i -F %s %s --exclude-dir=node_modules --exclude-dir=.git "
               "--exclude-dir=dist --exclude-dir=build --exclude-dir=venv "
               "--exclude-dir=.venv --exclude-dir=target | head -%d"
               % (pats, shlex.quote(area), cap))
    rc, out = sh(cmd, cwd=root or ".", timeout=60)
    return out.strip()


def code_windows(root, hits, limit=SCAN_WINDOWS, ctx=SCAN_WINDOW_CTX, budget=SCAN_CODE_CHARS):
    """Numbered code around the first grep hits; overlapping hits share one window."""
    out, taken, used = [], [], 0
    for line in hits.split("\n"):
        m = re.match(r"([^:]+):(\d+):", line)
        if not m:
            continue
        rel, ln = m.group(1), int(m.group(2))
        if any(r == rel and abs(l - ln) <= ctx for r, l in taken):
            continue
        w = read_window(root, rel, ln, ctx)
        if used + len(w) > budget:
            break
        taken.append((rel, ln))
        out.append(w)
        used += len(w)
        if len(out) >= limit:
            break
    return "\n".join(out)


def build_tasks(a, root):
    if a.tasks:
        t = json.loads(Path(a.tasks).read_text())
        return [{"id": x.get("id", "t%d" % i), "prompt": x["prompt"]} for i, x in enumerate(t)]
    if not a.area:
        return []
    kw = question_keywords(a.question)
    out = []
    for area in a.area:
        rc, files = sh("git ls-files %s 2>/dev/null | head -60" % shlex.quote(area), cwd=root)
        if not files.strip():
            rc, files = sh("find %s -type f | head -60" % shlex.quote(area), cwd=root)
        hits = grep_area(root, area, kw, 30) if kw else ""
        code = code_windows(root, hits) if hits else ""
        out.append({"id": area, "prompt":
                    "AREA: %s\nFILES:\n%s\nMATCHES:\n%s\nCODE:\n%s\nQUESTION: %s\n"
                    "Read only what you were given. Name file:line for anything you claim."
                    % (area, head(files, 60), head(hits, 30), code or "(no match)",
                       a.question or "what here could cause the failure?")})
    return out


def cmd_scan(a):
    root = repo_root(a.dir) or os.path.abspath(a.dir)
    tasks = build_tasks(a, root)
    if not tasks:
        print("scan needs --tasks FILE or one or more --area PATH. See -h.", file=sys.stderr)
        return 2
    shared = ""
    for f in a.context_file or []:
        shared += "\n== %s ==\n%s\n" % (f, head(Path(f).read_text("utf-8", "replace"), 400))
    if a.context:
        shared += "\n== context ==\n" + a.context + "\n"
    shared = shared.strip()

    key, src = find_key()
    model, effort = TIERS[a.tier]
    if a.model:
        model = a.model
    if a.effort:
        effort = a.effort

    if not key or a.print_prompts:
        # inside the project: no external_directory prompts for the workers
        d = Path(a.out) if a.out else Path(root) / ".debug" / "scan"
        d.mkdir(parents=True, exist_ok=True)
        # byte-identical prefix across workers; S= fills the agent's <scripts> placeholder
        prefix = SYS_PROMPT + "\n\nS=%s\n\n" % SCRIPTS + shared
        briefs = []
        for t in tasks:
            p = d / ("%s.txt" % re.sub(r"\W+", "_", t["id"]))
            p.write_text(prefix + "\n---\nTASK: " + t["prompt"])
            briefs.append((t["id"], str(p.resolve())))
        print("S=%s" % SCRIPTS)
        print("no API key found -- agent lane." if not key else "prompt files written.")
        if oc_harness.harness(str(Path(__file__).resolve())) == "opencode":
            mj = oc_harness.major(str(SKILL))
            lanes_file = d / "lanes.json"
            lanes_file.write_text(json.dumps(
                [{"id": tid, "agent": WORKER_AGENT, "brief": p, "model": model, "effort": effort,
                  "dir": root} for tid, p in briefs], indent=2) + "\n")
            print("lanes: %s (%d x %s)" % (lanes_file, len(briefs), WORKER_AGENT))
            if mj >= 2:
                print("Or dispatch them as background subagents, at most %d per message (waves):" % agent_lanes())
                for tid, p in briefs:
                    print("  " + oc_harness.dispatch_line(WORKER_AGENT, p, "scan " + tid, mj,
                                                          background=True))
            print("Each worker answers in the VERDICT shape written at the top of its file.")
            print("NEXT: python3 %s/oc_harness.py run %s" % (SCRIPTS, shlex.quote(str(lanes_file))))
            return 0
        print("Dispatch these %d prompts as %s subagents, at most %d per message, in waves "
              "(they are independent):" % (len(briefs), WORKER_AGENT, agent_lanes()))
        for tid, p in briefs:
            print("  %s: %s" % (WORKER_AGENT, p))
        print("Model for each worker: the cheap/fast tier. Each must answer in the VERDICT shape "
              "written at the top of its file.")
        print("NEXT: dispatch the %d %s subagents above in waves of at most %d, then read their "
              "VERDICTs." % (len(briefs), WORKER_AGENT, agent_lanes()))
        return 0

    base = a.base or os.environ.get("ZAI_BASE_URL") or "https://api.z.ai/api/coding/paas/v4"
    anthropic = "/anthropic" in base
    j = clamp(a.jobs, min(MAX_API, len(tasks)), MAX_API)
    t0 = time.time()
    print("S=%s\nscan: %d workers, %d parallel, model=%s effort=%s key=%s"
          % (SCRIPTS, len(tasks), j, model, effort, src), file=sys.stderr)

    # one Client shared across the whole pmap -> one AIMD gate actually throttles
    route = "anthropic" if anthropic else "openai"
    client = zai_client.Client(key, base=base, route=route)

    def one(t):
        # byte-identical prefix across workers -> prompt cache hit from request 2
        user = shared + "\n---\nTASK: " + t["prompt"]
        txt = api_call(key, base, model, effort, SYS_PROMPT, user, a.max_tokens, anthropic, client=client)
        return {"id": t["id"], "text": txt.strip()}

    res = pmap(one, tasks, j)
    print("\n== SCAN (%d workers, %.1fs wall) ==" % (len(res), time.time() - t0))
    conf = 0
    for r in res:
        print("\n[%s]" % r["id"])
        print(head(r["text"], 14))
        if r["text"].upper().startswith("VERDICT: CONFIRMED"):
            conf += 1
    print("\nSUMMARY: %d/%d CONFIRMED. Confirm any claimed root cause with one experiment "
          "(debug_tool.py experiment) before writing a fix." % (conf, len(res)))
    return 0


# ------------------------------------------------------------ doctor/setup

def detect_harness():
    h = []
    if os.environ.get("OPENCODE") or Path(".opencode").exists() or (Path.home() / ".config/opencode").exists():
        h.append("opencode")
    if (Path.home() / ".zcode").exists() or os.environ.get("ZCODE"):
        h.append("zcode")
    if os.environ.get("CLAUDE_SKILL_DIR") or (Path.home() / ".claude").exists():
        h.append("claude-compatible")
    return ",".join(h) or "unknown"


def cmd_doctor(a):
    key, src = find_key()
    root = repo_root(".")
    rows = [
        ("scripts dir", str(SCRIPTS)),
        ("skill dir", str(SKILL)),
        ("python", sys.version.split()[0]),
        ("cpus", str(cpus())),
        ("git repo", root or "NOT IN A GIT REPO (experiment/bisect need one)"),
        ("git", sh("git --version")[1].strip() or "MISSING"),
        ("timeout bin", shutil.which("timeout") or shutil.which("gtimeout") or "missing (-t flags ignored)"),
        ("harness", detect_harness()),
        ("api key", ("%s (...%s)" % (src, key[-4:])) if key else "none -> scan falls back to the agent lane"),
        ("base url", a.base or os.environ.get("ZAI_BASE_URL") or "https://api.z.ai/api/coding/paas/v4"),
        ("tiers", "light=%s/%s  std=%s/%s  deep=%s/%s" % (TIERS["light"] + TIERS["std"] + TIERS["deep"])),
    ]
    print("S=%s" % SCRIPTS)
    for k, v in rows:
        print("%-12s %s" % (k + ":", v))
    for s in ("snapshot.sh", "stress.sh", "bisect-parallel.sh", "find-polluter.sh", "_lib.sh"):
        p = SCRIPTS / s
        print("%-12s %s" % (s + ":", "ok" if p.exists() else "MISSING"))
    if root:
        wt = tempfile.mkdtemp(prefix="sdwt.")
        rc, out = sh("git worktree add --detach --force %s HEAD" % shlex.quote(wt + "/w"), cwd=root)
        print("%-12s %s" % ("worktrees:", "ok" if rc == 0 else "FAILED: " + tail(out, 2)))
        sh("git worktree remove --force %s/w" % shlex.quote(wt), cwd=root)
        sh("git worktree prune", cwd=root)
        shutil.rmtree(wt, ignore_errors=True)
    if a.ping:
        if not key:
            print("ping: skipped, no key")
            return 1
        base = a.base or os.environ.get("ZAI_BASE_URL") or "https://api.z.ai/api/coding/paas/v4"
        t0 = time.time()
        txt = api_call(key, base, TIERS["light"][0], "low", "Reply with the single word: ok", "ping", 32,
                       "/anthropic" in base)
        print("ping: %.1fs -> %s" % (time.time() - t0, txt.strip()[:80]))
    return 0


SETUP = {
    "opencode": (
        "# export ZAI_API_KEY=<GLM Coding Plan key>\n"
        "# Skill goes in ~/.config/opencode/skills/glm-systematic-debugging/ (or .opencode/skills/ per project).\n"
        "# Agent lane: without a key, `debug_tool.py scan` writes <root>/.debug/scan/lanes.json"
        " for the glm-debug-worker agent.\n"
        "# Run every lane in parallel with: python3 <scripts>/oc_harness.py run"
        " <root>/.debug/scan/lanes.json"),
    "zcode": """# ZCode
# Settings -> Model Settings -> Z.ai account or API key; thinking effort is per-model in the UI.
# Skill:  ~/.zcode/skills/glm-systematic-debugging/SKILL.md
Run `sh install-zcode.sh` from the glm-skills checkout instead of copying the file raw: it installs this skill to ~/.zcode/skills/ and rewrites the glm-debug-worker frontmatter into ~/.zcode/agents/ (real model ids, `thoughtLevel: low`, `maxTurns` instead of `steps`).
# export ZAI_API_KEY=<GLM Coding Plan key>   # so debug_tool.py scan can fan out by itself
# Foreground subagents run truly in parallel here: the agent lane of `scan` is fine on ZCode.""",
    "claude": """# ~/.claude/settings.json  (merge)
{
  "env": {
    "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5.3-flash",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.3",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.3",
    "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "8",
    "API_TIMEOUT_MS": "3000000"
  },
  "permissions": { "allow": ["Bash(git worktree *)"] }
}
# export ANTHROPIC_AUTH_TOKEN=<GLM Coding Plan key>""",
}


def cmd_setup(a):
    if a.harness == "opencode":
        mj = getattr(a, "major", None) or oc_harness.major(str(SKILL))
        print(oc_harness.config_snippet(mj, []))
        print(SETUP["opencode"])
        return 0
    print(SETUP[a.harness])
    return 0


# -------------------------------------------------------------------- main

def main(argv=None):
    p = argparse.ArgumentParser(prog="debug_tool.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd")

    q = sp.add_parser("probe", help="whole evidence phase in ONE call")
    q.add_argument("--error", help="error/stack text")
    q.add_argument("--error-file", help="file containing the error/stack text")
    q.add_argument("--cmd", help="minimal repro command (run filtered, with timeout)")
    q.add_argument("--symbol", action="append", help="extra symbol to grep and trace; repeatable")
    q.add_argument("--since", help="last-known-good rev for 'it used to work'")
    q.add_argument("--flake-check", default="auto", help="auto (default) or N repro runs")
    q.add_argument("--ctx", type=int, default=30, help="lines around each frame (default 30)")
    q.add_argument("--max-frames", type=int, default=6)
    q.add_argument("--max-grep", type=int, default=12)
    q.add_argument("--max-out", type=int, default=60, help="lines of repro output kept")
    q.add_argument("--timeout", type=int, default=600)
    q.add_argument("-j", "--jobs", default=0)
    q.add_argument("--dir", default=".")
    q.set_defaults(fn=cmd_probe)

    q = sp.add_parser("run", help="N shell commands in parallel, one call")
    q.add_argument("cmds", nargs="*")
    q.add_argument("--file", help="file with one command per line")
    q.add_argument("-j", "--jobs", default=0)
    q.add_argument("--timeout", type=int, default=1800)
    q.add_argument("--max-out", type=int, default=60)
    q.add_argument("--dir", default=".")
    q.set_defaults(fn=cmd_run)

    q = sp.add_parser("experiment", help="control-vs-treatment hypotheses in isolated worktrees")
    q.add_argument("--spec", help="JSON file (default: stdin)")
    q.add_argument("--template", action="store_true", help="print a fill-in spec and exit")
    q.add_argument("-j", "--jobs", default=0)
    q.add_argument("--timeout", type=int, default=900)
    q.add_argument("--keep", action="store_true")
    q.add_argument("--dir", default=".")
    q.set_defaults(fn=cmd_experiment)

    q = sp.add_parser("scan", help="judgment workers fanned out to the model API")
    q.add_argument("--tasks", help="JSON [{id,prompt}]")
    q.add_argument("--area", action="append", help="path to investigate; repeatable")
    q.add_argument("--question", help="the question each worker answers")
    q.add_argument("--context-file", action="append", help="shared context, byte-identical across workers")
    q.add_argument("--context", help="shared context string")
    q.add_argument("--tier", choices=list(TIERS), default="std")
    q.add_argument("--model")
    q.add_argument("--effort", choices=["low", "high", "max"])
    q.add_argument("--base", help="API base url")
    q.add_argument("--max-tokens", type=int, default=1200)
    q.add_argument("--print-prompts", action="store_true", help="write prompts for the agent lane instead")
    q.add_argument("--out", help="dir for prompt files")
    q.add_argument("-j", "--jobs", default=0)
    q.add_argument("--dir", default=".")
    q.set_defaults(fn=cmd_scan)

    q = sp.add_parser("doctor", help="environment check")
    q.add_argument("--ping", action="store_true")
    q.add_argument("--base")
    q.set_defaults(fn=cmd_doctor)

    q = sp.add_parser("setup", help="print harness config")
    q.add_argument("--harness", choices=list(SETUP), required=True)
    q.add_argument("--major", type=int, choices=[1, 2],
                   help="OpenCode major version (default: detected)")
    q.set_defaults(fn=cmd_setup)

    a = p.parse_args(argv)
    if not getattr(a, "fn", None):
        p.print_help()
        return 2
    return a.fn(a)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
        os._exit(0)
    except KeyboardInterrupt:
        sys.exit(130)
