#!/usr/bin/env python3
"""plan_tool.py v8 - deterministic engine for writing-plans (stdlib only, Python 3.8+).

  context   [SPEC] [--thorough]                  repo/spec/parallelism snapshot (skill-load injection; never fails)
  contracts PLAN [--spec S] [--agents K] [--preset claude|hybrid|opencode]  validate contracts, route groups, write briefs, print DISPATCH/OPENCODE
  oc-write  PLAN                                 run the opencode writer groups (background; always exit 0)
  doctor    [--ping]                             check opencode and tier models, write the doctor cache
  stats     [--repo PATH]                        opencode lane telemetry per tier
  lint-task PLAN TASKFILE [--mark ok|rev]        lint one task body; on success touch TASKFILE.<mark>
  hook-lint                                      PostToolUse hook: lint a written task file -> additionalContext
  wait      PLAN [--review] [--timeout S] [--idle S] [--include-held]   block until every task (or review) file lints OK
  review    PLAN [--all] [--size N] [--agents K] pick risky tasks, write reviewer briefs, print DISPATCH
  assemble  PLAN [--clean]                       full check, render canonical plan, splice task bodies
  check     PLAN [--spec S]                      same as assemble for a plan with inline tasks (<= 3 tasks)
  setup     [--scope user|project] [--apply]     raise subagent cap to 16 (if set and lower than 12), pre-approve tools, install writer agent
Common: --allow WORD (repeatable) exempts a placeholder/portability hit. Exit 0 = OK, 1 = errors.
"""
import argparse, ast, concurrent.futures, hashlib, json, os, re, shlex, shutil, subprocess, sys, tempfile, textwrap, time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
TOOL = os.path.abspath(__file__)
MAX_AGENTS = 12  # soft ceiling for agent fan-out
WRITER_MIN_TASKS = 3  # target tasks per writer/reviewer (fixed per-agent token overhead)
RECOMMENDED_CAP = 16  # value `setup --apply` writes when the cap is set and below MAX_AGENTS
DEFAULT_CAP = 20
ID_RE = r"T\d{2,3}"
CONTRACT_HEAD = re.compile(r"^####\s+(%s)\s*[:·—-]\s*(.+?)\s*$" % ID_RE)
FIELD = re.compile(r"^-\s+(Depends|Parallel|Files|Produces|Consumes|Read|Spec|Tier):\s*(.*)$")
TASK_HEAD = re.compile(r"^###\s+(%s)\s*:\s*(.+?)\s*$" % ID_RE)
TASK_HEADING_ANYWHERE = re.compile(r"^\s*###\s*%s\s*:" % ID_RE)
TICK = re.compile(r"`([^`\n]+)`")
TASKS_MARK = "<!-- TASKS -->"
WAVES_OPEN, WAVES_CLOSE = "<!-- WAVES -->", "<!-- /WAVES -->"
TIER_MODEL = {"light": "sonnet", "std": "sonnet", "deep": "sonnet"}
TIER_RANK = {"light": 0, "std": 1, "deep": 2}

PLACEHOLDERS_CS = [r"\bTBD\b", r"\bTODO\b", r"\bFIXME\b", r"\bXXX\b"]
PLACEHOLDERS = [r"implement(ed)? later",
    r"fill in (the )?details", r"add appropriate (error handling|validation)",
    r"handle (the )?edge cases", r"similar to (task\s*|T)\d+", r"same as (task\s*|T)\d+",
    r"write tests for the above", r"\.\.\.\s*(rest|remaining) of", r"your code here"]
PORTABILITY = [r"\bsub-?skills?\b", r"\bsubagents?\b", r"\bslash commands?\b",
    r"\b(Task|Agent|Edit|Write|Read|Bash) tool\b", r"\bClaude\b", r"\bAnthropic\b",
    r"\bCopilot\b", r"\bCursor (IDE|editor|agent)\b", r"\binvoke (the |a )?skill\b"]
PH_RE = [re.compile(p) for p in PLACEHOLDERS_CS] + [re.compile(p, re.I) for p in PLACEHOLDERS]
PO_RE = [re.compile(p, re.I) for p in PORTABILITY]
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
URL_RE = re.compile(r"https?://\S+")

PROTOCOL = """## Execution Protocol (for any AI agent or human engineer)

1. A task may start only when every task in its **Depends** and **Runs after**
   lists is complete. Single worker: run tasks in ID order.
2. Parallel workers: follow **Execution Waves**. Tasks in the same wave touch
   disjoint files and MAY run concurrently (marked `[P]`). Never run two tasks
   that modify the same file at once.
3. Within a task, execute steps top to bottom and mark each checkbox `- [x]`
   when done. To resume, continue from the first unchecked step.
4. Run every command exactly as written and compare with **Expected**. On
   mismatch, stop and fix before continuing.
5. Code blocks are the implementation - copy them verbatim. Signatures under
   **Interfaces** are contracts with other tasks: never rename, reorder
   parameters, or change types.
6. Commit exactly where the plan says, with the given message, staging only the
   listed paths. Never batch commits across tasks.
7. **Global Constraints** apply to every task.
8. If anything is ambiguous, missing, or contradicts the codebase, STOP and ask
   the requester. Do not invent behavior.
"""
NOTE = """> **Execution note:** This plan is self-contained and tool-agnostic. Any AI
> agent or human engineer can execute it with only a shell, a code editor, and
> git. Follow the Execution Protocol below."""


# ------------------------------------------------------------------ utils
def num(tid):
    return int(tid[1:])


def norm_path(p):
    p = re.sub(r":\d+(-\d+)?$", "", p.strip())
    while p.startswith("./"):
        p = p[2:]
    return p


def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def save(path, text):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def touch(path):
    with open(path, "w") as f:
        f.write(str(time.time()))


def repo_root(start):
    d = os.path.abspath(start if os.path.isdir(start) else os.path.dirname(os.path.abspath(start)))
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        nd = os.path.dirname(d)
        if nd == d:
            return os.getcwd()
        d = nd


def qtool():
    return "python3 " + shlex.quote(TOOL)


def default_work(plan):
    p = os.path.abspath(plan)
    return os.path.join(os.path.dirname(p), ".hybrid-work", os.path.splitext(os.path.basename(p))[0])


def load_work(plan):
    w = default_work(plan)
    try:
        return w, json.loads(load(os.path.join(w, "work.json")))
    except (OSError, ValueError):
        return w, {}


def report(errs, warns, ok_msg, extra=None):
    for w in warns:
        print("WARN " + w)
    for e in errs:
        print("ERR  " + e)
    if errs:
        print("FAIL: %d error(s)" % len(errs))
        return 1
    print(ok_msg)
    for line in extra or []:
        print(line)
    return 0


def cap_from_env():
    v = os.environ.get("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", "").strip()
    return (int(v), True) if v.isdigit() and int(v) > 0 else (DEFAULT_CAP, False)


# ------------------------------------------------------------------ parsing
def section(text, title):
    """Body of '## <title>' up to the next level-2 heading or marker."""
    out, on = [], False
    for l in text.splitlines():
        if re.match(r"^##\s+%s\b" % re.escape(title), l):
            on = True
            continue
        if on and (re.match(r"^##\s", l) or l.strip() in (TASKS_MARK, WAVES_OPEN)):
            break
        if on:
            out.append(l)
    return "\n".join(out).strip() if on else None


def parse_contracts(text):
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if re.match(r"^##\s+Contracts\b", l)), None)
    if start is None:
        return None, ["no '## Contracts' section"]
    cs, errs, cur, field = [], [], None, None
    for i in range(start + 1, len(lines)):
        l = lines[i]
        if re.match(r"^##\s", l) or l.strip() in (TASKS_MARK, WAVES_OPEN) or TASK_HEAD.match(l):
            break
        m = CONTRACT_HEAD.match(l)
        if m:
            cur = {"id": m.group(1), "name": m.group(2), "line": i + 1, "raw": {}, "text": [l]}
            cs.append(cur)
            field = None
            continue
        if cur is None:
            continue
        if l.strip():
            cur["text"].append(l)
        f = FIELD.match(l)
        if f:
            field = f.group(1)
            if field in cur["raw"]:
                errs.append("%s: duplicate field %s" % (cur["id"], field))
            cur["raw"][field] = f.group(2)
            continue
        if field and l.strip():
            cur["raw"][field] += "\n" + l
    for c in cs:
        r = c["raw"]
        c["text"] = "\n".join(c["text"])
        c["deps"] = re.findall(ID_RE, r.get("Depends", ""))
        c["files"] = [norm_path(x) for x in TICK.findall(r.get("Files", ""))]
        c["produces"] = TICK.findall(r.get("Produces", ""))
        c["reads"] = [norm_path(x) for x in TICK.findall(r.get("Read", ""))]
        cons, ext = [], []
        s = r.get("Consumes", "")
        for m in TICK.finditer(s):
            tail = s[m.end():m.end() + 40].lower()
            (ext if "existing" in tail.split("`")[0] else cons).append(m.group(1))
        c["consumes"], c["external"], c["consumes_explicit"] = cons, ext, "Consumes" in r
        c["spec"] = [(int(a), int(b or a)) for a, b in re.findall(r"L(\d+)(?:\s*-\s*L?(\d+))?", r.get("Spec", ""))]
        t = r.get("Tier", "").strip().lower()
        c["tier"] = t if t in TIER_RANK else "std"
        if t and t not in TIER_RANK:
            errs.append("%s: Tier must be light|deep (got %r)" % (c["id"], t))
        if not c["files"]:
            errs.append("%s: '- Files:' needs at least one `backticked` path" % c["id"])
    return cs, errs


def fence_mask(lines):
    """True for each line lexically inside (or opening/closing) a ``` / ~~~ fence,
    length-threshold aware like code_blocks(); an unterminated fence marks every
    following line as inside, so it is never scanned or heading-checked twice."""
    mask, open_n = [], 0
    for l in lines:
        m = re.match(r"^\s*(`{3,}|~{3,})(.*)$", l)
        if open_n:
            mask.append(True)
            if m and len(m.group(1)) >= open_n and not m.group(2).strip():
                open_n = 0
            continue
        mask.append(bool(m))
        if m:
            open_n = len(m.group(1))
    return mask


def allow_hit(hit, allow):
    """True when an --allow entry exempts `hit`: `re:<pattern>` must match the whole hit,
    any other entry is a case-insensitive stem (`subagent` also exempts `subagents`)."""
    low = hit.lower()
    for a in allow:
        if a.startswith("re:"):
            try:
                if re.fullmatch(a[3:], hit, re.I):
                    return True
            except re.error:
                continue
        elif a and low.startswith(a.lower()):
            return True
    return False


def scan(text, allow, label, skip_contracts=False, fenced_placeholders=False):
    errs, inside = [], False
    lines = text.splitlines()
    fmask = fence_mask(lines)
    for n, l in enumerate(lines, 1):
        if skip_contracts:
            if re.match(r"^##\s+Contracts\b", l):
                inside = True
            elif re.match(r"^##\s", l) or l.strip() in (TASKS_MARK, WAVES_OPEN):
                inside = False
        if inside:
            continue
        if fmask[n - 1]:
            # fenced code: placeholders still count (opt-in), portability never does
            if not fenced_placeholders:
                continue
            checks, clean = (("placeholder", PH_RE),), l
        else:
            checks, clean = (("placeholder", PH_RE), ("portability", PO_RE)), URL_RE.sub(" ", INLINE_CODE_RE.sub(" ", l))
        for kind, pats in checks:
            for p in pats:
                for m in p.finditer(clean):
                    if not allow_hit(m.group(0), allow):
                        errs.append("%s:%d %s %r: %s" % (label, n, kind, m.group(0), l.strip()[:100]))
    return errs


def code_blocks(text):
    """[(info, body, start_line)] ; None if a fence is unbalanced."""
    blocks, open_n, info, buf, start = [], 0, "", [], 0
    for n, l in enumerate(text.splitlines(), 1):
        m = re.match(r"^\s*(`{3,}|~{3,})(.*)$", l)
        if m and open_n == 0:
            open_n, info, buf, start = len(m.group(1)), m.group(2).strip(), [], n
            continue
        if m and len(m.group(1)) >= open_n and not m.group(2).strip():
            blocks.append((info, "\n".join(buf), start))
            open_n = 0
            continue
        if open_n:
            buf.append(l)
    return None if open_n else blocks


# ------------------------------------------------------------------ analysis
def analyze(cs, spec_path=None, repo=None):
    errs, warns = [], []
    if not cs:
        return ["Contracts section has no '#### TNN: Name' entries"], warns
    width = 3 if len(cs) > 99 else 2
    for i, c in enumerate(cs, 1):
        want = "T%0*d" % (width, i)
        if c["id"] != want:
            errs.append("%s: expected id %s (sequential, zero-padded, no gaps)" % (c["id"], want))
    cmap = {c["id"]: c for c in cs}
    if len(cmap) != len(cs):
        errs.append("duplicate task ids")
    producers = {}
    for c in cs:
        for s in c["produces"]:
            if s in producers:
                warns.append("%s and %s both produce `%s`" % (producers[s], c["id"], s))
            producers.setdefault(s, c["id"])
    for c in cs:
        deps = set()
        for d in c["deps"]:
            if d not in cmap:
                errs.append("%s: depends on unknown %s" % (c["id"], d))
            elif num(d) >= num(c["id"]):
                errs.append("%s: depends on later/self task %s (deps must have lower ids)" % (c["id"], d))
            else:
                deps.add(d)
        if not c["consumes_explicit"]:
            c["consumes"] = [s for d in sorted(deps, key=num) for s in cmap[d]["produces"]]
        for s in c["consumes"]:
            src = producers.get(s)
            if src is None:
                errs.append("%s: consumes `%s` which no task produces verbatim (fix signature or mark '(existing)')" % (c["id"], s))
            elif src == c["id"]:
                continue
            elif num(src) > num(c["id"]):
                errs.append("%s: consumes `%s` from later task %s - renumber so producers come first" % (c["id"], s, src))
            else:
                deps.add(src)
        c["deps_all"] = sorted(deps, key=num)
        c["consumers"] = []
    for c in cs:
        for s in c["consumes"]:
            src = producers.get(s)
            if src and src != c["id"] and src in cmap:
                cmap[src]["consumers"].append((c["id"], s))
    # ancestors over declared + derived deps
    anc = {}
    for c in cs:
        a = set()
        for d in c["deps_all"]:
            a.add(d)
            a |= anc.get(d, set())
        anc[c["id"]] = a
    # same-file ordering: each file forms an ID-ordered chain
    owners = {}
    for c in cs:
        c["after"] = []
        for f in dict.fromkeys(c["files"]):
            owners.setdefault(f, []).append(c["id"])
    for f, ts in owners.items():
        for prev, cur in zip(ts, ts[1:]):
            if prev not in anc[cur] and prev not in cmap[cur]["after"]:
                cmap[cur]["after"].append(prev)
        if len(ts) >= 4:
            warns.append("hot file `%s` is touched by %d tasks (%s) - it serializes them; split it or wire it in one final task" % (f, len(ts), ", ".join(ts)))
    wave = {}
    for c in cs:
        preds = c["deps_all"] + c["after"]
        wave[c["id"]] = 1 + max([wave[p] for p in preds if p in wave] or [0])
    by = {}
    for c in cs:
        c["wave"] = wave[c["id"]]
        by.setdefault(c["wave"], []).append(c["id"])
    for c in cs:
        c["p"] = len(by[c["wave"]]) > 1
    if repo:
        for c in cs:
            for r in c["reads"]:
                if not os.path.isfile(os.path.join(repo, r)):
                    warns.append("%s: Read path `%s` not found" % (c["id"], r))
    if spec_path:
        warns += spec_coverage(cs, spec_path)
    return errs, warns


def spec_coverage(cs, spec_path):
    try:
        lines = load(spec_path).splitlines()
    except OSError as e:
        return ["spec unreadable: %s" % e]
    out = ["%s: no 'Spec: L<a>-<b>' pointer" % c["id"] for c in cs if not c["spec"]]
    ranges = [r for c in cs for r in c["spec"]]
    for c in cs:
        for a, b in c["spec"]:
            if a < 1 or b > len(lines) or a > b:
                out.append("%s: Spec range L%d-%d outside spec (1-%d)" % (c["id"], a, b, len(lines)))
    fmask = fence_mask(lines)
    heads = [(i + 1, l.strip()) for i, l in enumerate(lines) if not fmask[i] and re.match(r"^#{1,6}\s", l)]
    for k, (ln, h) in enumerate(heads):
        end = (heads[k + 1][0] - 1) if k + 1 < len(heads) else len(lines)
        body = [x for x in range(ln + 1, end + 1) if lines[x - 1].strip()]
        if body and not any(a <= x <= b for x in body for a, b in ranges):
            out.append("spec uncovered L%d-%d %s" % (ln, end, h[:70]))
    return out


def waves_block(cs):
    by = {}
    for c in cs:
        by.setdefault(c["wave"], []).append(c)
    rows = ["## Execution Waves", "",
            "Every task in a wave has all its Depends/Runs-after tasks in earlier waves. Tasks in the",
            "same wave touch disjoint files, so a wave's `[P]` tasks may all run at once.", ""]
    for k in sorted(by):
        rows.append("- **Wave %d:** %s" % (k, ", ".join(c["id"] + (" [P]" if c["p"] else "") for c in by[k])))
    width = max(len(v) for v in by.values())
    return "\n".join(rows), len(by), width


# ------------------------------------------------------------------ task bodies
GEN_LINE = re.compile(r"^\*\*(Depends|Runs after):\*\*")


def strip_generated(section_text):
    """Remove heading / Depends / Runs after / Interfaces that precede **Files:** (script regenerates them)."""
    lines = section_text.strip("\n").splitlines()
    fi = next((i for i, l in enumerate(lines) if l.strip().startswith("**Files:**")), None)
    head, rest = (lines[:fi], lines[fi:]) if fi is not None else ([], lines)
    out, i = [], 0
    while i < len(head):
        l = head[i]
        if TASK_HEAD.match(l) or GEN_LINE.match(l):
            i += 1
            continue
        if l.strip() == "**Interfaces:**":
            i += 1
            while i < len(head) and (not head[i].strip() or head[i].lstrip().startswith("- ") or head[i].startswith("  ")):
                i += 1
            continue
        out.append(l)
        i += 1
    body = "\n".join(out + rest).strip()
    body = re.sub(r"\n-{3,}\s*$", "", body).strip()
    return body + "\n"


def render_task(c, body):
    rows = ["### %s: %s%s" % (c["id"], c["name"], " [P]" if c["p"] else ""), "",
            "**Depends:** %s" % (", ".join(c["deps_all"]) or "—")]
    if c["after"]:
        rows += ["", "**Runs after:** %s (same files)" % ", ".join(c["after"])]
    iface = []
    if c["consumes"]:
        iface.append("- Consumes: " + "; ".join("`%s`" % s for s in c["consumes"]))
    if c["external"]:
        iface.append("- Uses existing: " + "; ".join("`%s`" % s for s in c["external"]))
    if c["produces"]:
        iface.append("- Produces: " + "; ".join("`%s`" % s for s in c["produces"]))
    if iface:
        rows += ["", "**Interfaces:**"] + iface
    return "\n".join(rows) + "\n\n" + body.strip() + "\n"


BARE_FILENAMES = {"Makefile", "Dockerfile", "LICENSE"}


def files_block(body):
    lines = body.splitlines()
    fi = next((i for i, l in enumerate(lines) if l.strip().startswith("**Files:**")), None)
    if fi is None:
        return None
    paths = []
    for l in lines[fi + 1:]:
        if not l.strip():
            if paths:
                break
            continue
        if not l.lstrip().startswith("- ") or l.lstrip().startswith("- ["):
            break
        toks = TICK.findall(l)
        if toks:
            first = toks[0]  # the path; a later `span` on the same line is just an annotation
            if "/" in first or "." in first or first in BARE_FILENAMES:
                paths.append(norm_path(first))
    return paths


def syntax_errors(blocks, label):
    errs = []
    for info, src, line in blocks:
        words = info.lower().replace("{", " ").replace("}", " ").split()
        if not words or "fragment" in words or not src.strip():
            continue
        lang = words[0]
        where = "%s: code block at body L%d (%s)" % (label, line, lang)
        hint = " - fix it, or open the fence as ```%s fragment if intentionally partial" % lang
        try:
            if lang in ("python", "py", "python3"):
                flags = getattr(ast, "PyCF_ALLOW_TOP_LEVEL_AWAIT", 0)
                compile(textwrap.dedent(src), "<block>", "exec", flags=flags, dont_inherit=True)
            elif lang == "json":
                json.loads(src)
            elif lang == "toml":
                try:
                    import tomllib
                except ImportError:
                    continue
                tomllib.loads(src)
            elif lang in ("bash", "sh") and shutil.which("bash"):
                p = subprocess.run(["bash", "-n"], input=src, capture_output=True, text=True, timeout=10)
                if p.returncode:
                    errs.append("%s: %s%s" % (where, p.stderr.strip().splitlines()[-1][:160], hint))
            elif lang in ("js", "javascript", "mjs", "cjs") and shutil.which("node"):
                ext = ".mjs" if re.search(r"^\s*(import|export)\s", src, re.M) else ".cjs"
                with tempfile.NamedTemporaryFile("w", suffix=ext, delete=False) as tf:
                    tf.write(src)
                try:
                    p = subprocess.run(["node", "--check", tf.name], capture_output=True, text=True, timeout=15)
                finally:
                    os.unlink(tf.name)
                if p.returncode:
                    msg = [x for x in p.stderr.splitlines() if "Error" in x] or p.stderr.splitlines() or ["syntax error"]
                    errs.append("%s: %s%s" % (where, msg[0][:160], hint))
        except SyntaxError as e:
            errs.append("%s: python syntax line %s: %s%s" % (where, e.lineno, e.msg, hint))
        except ValueError as e:
            errs.append("%s: %s%s" % (where, str(e)[:160], hint))
        except Exception as e:  # tomllib.TOMLDecodeError, timeouts
            errs.append("%s: %s%s" % (where, str(e)[:160], hint))
    return errs


SHELL_LANGS = ("", "bash", "sh", "shell", "zsh", "console")
COMMIT_ALL = re.compile(r"^-[^-mFCcS]*a")


def commit_errors(blocks, label):
    """Flag `git commit -a/--all` and a `git commit` with no earlier `git add` in the
    body's shell code blocks (a prose mention of a commit is not checked)."""
    errs, added = [], False
    for info, src, line in blocks:
        lang = (info.lower().split() or [""])[0]
        if lang not in SHELL_LANGS:
            continue
        for l in src.splitlines():
            for seg in re.split(r"\s*(?:&&|;|\|\|?)\s*", l.strip()):
                if seg.startswith("git add"):
                    added = True
                elif seg.startswith("git commit"):
                    try:
                        toks = shlex.split(seg)[2:]
                    except ValueError:
                        toks = seg.split()[2:]
                    if "--all" in toks or any(COMMIT_ALL.match(t) for t in toks):
                        errs.append("%s: `%s` stages every tracked change - drop -a/--all and `git add` the Files paths" % (label, seg.strip()[:80]))
                    if not added:
                        errs.append("%s: `git commit` has no earlier `git add` of the Files paths" % label)
                        added = True
    return errs


def lint_body(c, body, allow, label, repo=None, earlier_files=()):
    errs, warns = [], []
    body_lines = body.splitlines()
    body_fmask = fence_mask(body_lines)
    # A real '### Tnn:' task heading is still an error inside a fence (e.g. a writer
    # pasting a fake next-task marker into an example); other headings stay fence-exempt.
    if any((not body_fmask[i] and re.match(r"^#{1,3}\s", l)) or TASK_HEADING_ANYWHERE.match(l)
           for i, l in enumerate(body_lines)):
        errs.append("%s: '#', '##' or '###' heading inside a task body breaks plan structure (use '####' or bold)" % label)
    paths = files_block(body)
    if paths is None:
        errs.append("%s: body must start with a '**Files:**' list" % label)
        paths = []
    contract = set(c["files"])
    for p in paths:
        if p not in contract:
            errs.append("%s: Files lists `%s` which is not in the contract Files (breaks parallel safety)" % (label, p))
    for f in c["files"]:
        if f not in paths:
            errs.append("%s: contract file `%s` missing from the **Files:** list" % (label, f))
    if repo:
        for l in body.splitlines():
            m = re.match(r"^\s*-\s+(Create|Modify)\s*:\s*`([^`]+)`", l)
            if not m:
                continue
            p = norm_path(m.group(2))
            exists = os.path.exists(os.path.join(repo, p))
            if m.group(1) == "Create" and exists:
                warns.append("%s: Create `%s` already exists - should it be Modify?" % (label, p))
            if m.group(1) == "Modify" and not exists and p not in earlier_files:
                warns.append("%s: Modify `%s` does not exist and no earlier task creates it" % (label, p))
    for s in c["produces"]:
        if s not in body:
            errs.append("%s: produced signature not written verbatim in the body: `%s`" % (label, s))
    steps = [int(x) for x in re.findall(r"^- \[[ x]\] \*\*Step (\d+)", body, re.M)]
    if not steps:
        errs.append("%s: no '- [ ] **Step N: ...**' checkboxes" % label)
    elif steps != list(range(1, len(steps) + 1)):
        errs.append("%s: steps must be numbered 1..%d in order (got %s)" % (label, len(steps), steps))
    blocks = code_blocks(body)
    if blocks is None:
        errs.append("%s: unbalanced code fence" % label)
        blocks = []
    elif not blocks:
        errs.append("%s: no code block" % label)
    if "git commit" not in body:
        errs.append("%s: no commit step" % label)
    lines = body.splitlines()
    in_fence = False
    for i, l in enumerate(lines):
        if re.match(r"^\s*(`{3,}|~{3,})", l):
            in_fence = not in_fence
        if in_fence or not re.match(r"^\s*(\*\*)?Run:", l):
            continue
        ok = False
        for m in lines[i + 1:]:
            if re.match(r"^\s*(\*\*)?Expected:", m):
                ok = True
                break
            if re.match(r"^\s*(\*\*)?Run:", m) or re.match(r"^- \[[ x]\] \*\*Step", m):
                break
        if not ok and not re.search(r"Expected:", l):
            errs.append("%s: 'Run:' at body L%d has no 'Expected:' before the next Run/Step" % (label, i + 1))
    for info, src, line in blocks:
        for l in src.splitlines():
            m = re.match(r"^\s*git add\s+(.+)$", l)
            if not m:
                continue
            add_args = re.split(r"\s*(?:&&|;|\|)\s*", m.group(1), maxsplit=1)[0]
            try:
                toks = [t for t in shlex.split(add_args) if not t.startswith("-")]
            except ValueError:
                toks = add_args.split()
            bad = [t for t in toks if t in (".", "*", ":/") or "*" in t]
            if bad or re.search(r"(^|\s)(-A|--all|-u)\b", add_args):
                errs.append("%s: `git add %s` - stage explicit paths from Files only" % (label, add_args.strip()))
                continue
            for t in toks:
                t = norm_path(t)
                if t in contract:
                    continue
                if any(f.startswith(t.rstrip("/") + "/") for f in contract):
                    warns.append("%s: `git add %s` stages a directory - prefer explicit file paths" % (label, t))
                else:
                    errs.append("%s: `git add` path `%s` is not in the contract Files" % (label, t))
    errs += commit_errors(blocks, label)
    errs += syntax_errors(blocks, label)
    errs += scan(body, allow, label, fenced_placeholders=True)
    return errs, warns


# ------------------------------------------------------------------ briefs
def numbered(path, a, b, width=5):
    try:
        lines = load(path).splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    a, b = max(1, a), min(len(lines), b)
    return "\n".join("%*d| %s" % (width, i, lines[i - 1]) for i in range(a, b + 1))


def merge_ranges(rs):
    out = []
    for a, b in sorted(rs):
        if out and a <= out[-1][1] + 1:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def inline_files(paths, repo, budget_lines=1500, per_file=400):
    inl, refs, used = [], [], 0
    for p in dict.fromkeys(paths):
        full = os.path.join(repo, p)
        if not os.path.isfile(full):
            continue
        try:
            if os.path.getsize(full) > 250000:
                refs.append("%s (large)" % p)
                continue
            text = load(full)
        except (OSError, UnicodeDecodeError):
            continue
        n = len(text.splitlines())
        if n <= per_file and used + n <= budget_lines:
            used += n
            inl.append("#### `%s` (%d lines)\n\n````text\n%s\n````" % (p, n, numbered(full, 1, n)))
        else:
            refs.append("%s (%d lines)" % (p, n))
    return inl, refs


def weight(c):
    return 2.0 + sum(b - a + 1 for a, b in c["spec"]) / 30.0 + 0.5 * len(c["files"]) + 0.5 * len(c["produces"])


def partition(cs, k):
    if len(cs) <= k:
        return [[c] for c in cs]
    w = [weight(c) for c in cs]

    def groups(limit):
        out, cur, acc = [], [], 0.0
        for c, x in zip(cs, w):
            if cur and acc + x > limit:
                out.append(cur)
                cur, acc = [], 0.0
            cur.append(c)
            acc += x
        return out + ([cur] if cur else [])

    lo, hi = max(w), 0.0
    for x in w:  # not sum(w): Python >= 3.12 sums floats with compensation, which can undershoot groups()'s running total
        hi += x
    for _ in range(50):
        mid = (lo + hi) / 2
        if len(groups(mid)) <= k:
            hi = mid
        else:
            lo = mid
    out = groups(hi)
    wt = {id(c): x for c, x in zip(cs, w)}
    while len(out) < k:  # use every free slot: split the heaviest multi-task group
        cand = [g for g in out if len(g) > 1]
        if not cand:
            break
        g = max(cand, key=lambda g: sum(wt[id(c)] for c in g))
        i = out.index(g)
        half, acc, total = 1, 0.0, sum(wt[id(c)] for c in g)
        for j, c in enumerate(g[:-1], 1):
            acc += wt[id(c)]
            if acc >= total / 2:
                half = j
                break
        out[i:i + 1] = [g[:half], g[half:]]
    return out


def plan_header(plan):
    lines = plan.splitlines()
    first = next((i for i, l in enumerate(lines) if re.match(r"^##\s", l)), len(lines))
    return "\n".join(l for l in lines[:first] if not l.startswith(">")).strip()


def writer_brief(plan_path, plan, cs_group, cmap, work, spec_path, repo, allow):
    ids = [c["id"] for c in cs_group]
    outs = {c["id"]: os.path.join(work, "tasks", c["id"] + ".md") for c in cs_group}
    lint = "; ".join("%s lint-task %s %s" % (qtool(), shlex.quote(plan_path), shlex.quote(outs[t])) for t in ids)
    tmpl = load(os.path.join(SKILL_DIR, "task-writer-prompt.md"))
    parts = [tmpl.replace("{TASKS}", ", ".join(ids)).replace("{LINT}", lint)
             .replace("{OUT}", "\n".join("- %s -> `%s`" % (t, outs[t]) for t in ids))]
    parts.append("## Plan header\n\n" + plan_header(plan))
    for title in ("Global Constraints", "References", "File Structure"):
        s = section(plan, title)
        if s:
            parts.append("## %s\n\n%s" % (title, s))
    for c in cs_group:
        blk = ["## Contract %s (locked)" % c["id"], "", c["text"], "",
               "- Resolved Depends: %s" % (", ".join(c["deps_all"]) or "—")]
        if c["after"]:
            blk.append("- Runs after (same files): %s - code against the file state AFTER those tasks" % ", ".join(c["after"]))
        for s in c["consumes"]:
            blk.append("- Consumes `%s` (from contract of its producer - call it exactly like this)" % s)
        for t, s in c["consumers"]:
            blk.append("- %s will call your `%s` - make it complete and exact" % (t, s))
        parts.append("\n".join(blk))
        if spec_path and c["spec"]:
            ex = [numbered(spec_path, a, b) or "" for a, b in merge_ranges(c["spec"])]
            parts.append("## Spec excerpt for %s (`%s`)\n\n````text\n%s\n````" % (c["id"], os.path.relpath(spec_path, repo), "\n  ...\n".join(ex)))
    paths = [f for c in cs_group for f in c["files"]] + [r for c in cs_group for r in c["reads"]]
    ref = section(plan, "References")
    if ref:
        paths += [norm_path(x) for x in TICK.findall(ref)]
    inl, refs = inline_files(paths, repo)
    if inl:
        parts.append("## Existing files (inlined, with line numbers - use them for Modify ranges and patterns)\n\n" + "\n\n".join(inl))
    if refs:
        parts.append("## Read before writing (ONE message of parallel Reads, repo root `%s`)\n\n" % repo + "\n".join("- `%s`" % r for r in refs))
    return "\n\n".join(parts) + "\n"


def reviewer_brief(plan_path, plan, cs_group, work, spec_path, repo):
    tmpl = load(os.path.join(SKILL_DIR, "plan-reviewer-prompt.md"))
    files = [os.path.join(work, "tasks", c["id"] + ".md") for c in cs_group]
    lint = "; ".join("%s lint-task %s %s --mark rev" % (qtool(), shlex.quote(plan_path), shlex.quote(f)) for f in files)
    parts = [tmpl.replace("{TASKS}", ", ".join(c["id"] for c in cs_group)).replace("{LINT}", lint)
             .replace("{FILES}", "\n".join("- `%s`" % f for f in files))]
    parts.append("## Portability (hybrid)\n\nA task body must not name opencode: remove any mention of it by editing the task file.")
    gc = section(plan, "Global Constraints")
    if gc:
        parts.append("## Global Constraints\n\n" + gc)
    for c, f in zip(cs_group, files):
        parts.append("## Contract %s\n\n%s\n\n- Resolved Depends: %s" % (c["id"], c["text"], ", ".join(c["deps_all"]) or "—"))
        if spec_path and c["spec"]:
            ex = [numbered(spec_path, a, b) or "" for a, b in merge_ranges(c["spec"])]
            parts.append("## Spec excerpt for %s\n\n````text\n%s\n````" % (c["id"], "\n  ...\n".join(ex)))
        body = numbered(f, 1, 10 ** 9)
        if body:
            parts.append("## Task body %s (`%s`, line-numbered; fix it by editing that file)\n\n````text\n%s\n````" % (c["id"], f, body))
    paths = [f for c in cs_group for f in c["files"]]
    inl, refs = inline_files(paths, repo)
    if inl:
        parts.append("## Existing files (inlined, with line numbers - the target files as written by the writer)\n\n" + "\n\n".join(inl))
    if refs:
        parts.append("## Read before writing (ONE message of parallel Reads, repo root `%s`)\n\n" % repo + "\n".join("- `%s`" % r for r in refs))
    return "\n\n".join(parts) + "\n"


def dispatch_lines(groups, work, kind):
    rows = []
    for gid, g in groups:
        tier = max((c["tier"] for c in g), key=lambda t: TIER_RANK[t])
        model = "sonnet" if kind == "review" else TIER_MODEL[tier]
        span = g[0]["id"] if len(g) == 1 else "%s-%s" % (g[0]["id"], g[-1]["id"])
        rows.append("%-4s %-7s %-9s %s" % (gid, model, span, os.path.join(work, kind + "-briefs" if kind == "review" else "briefs", gid + ".md")))
    return rows


def agent_installed(repo):
    for base in (os.path.join(repo, ".claude", "agents"), os.path.join(os.path.expanduser("~"), ".claude", "agents")):
        p = os.path.join(base, "hybrid-plan-task-writer.md")
        if os.path.isfile(p):
            return p
    return None


def span_of(g):
    return g[0]["id"] if len(g) == 1 else "%s-%s" % (g[0]["id"], g[-1]["id"])


def oc_dispatch_lines(oc, work):
    return ["%-4s %-7s %-9s %s" % (gid, backend, span_of(g), os.path.join(work, "briefs", gid + ".oc.md"))
            for gid, backend, g in oc]


SKILL_NAME = "hybrid-writing-plans"
PRESETS = ("claude", "hybrid", "opencode")


def use_here():
    """Make the sibling hp_*/hybrid_shared modules importable (once, however often it is called)."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)


def shared():
    use_here()
    import hybrid_shared
    return hybrid_shared


def emit_oc(level, unit, kind, text, tier="-", model="-"):
    if text.startswith("OC-"):
        print(text)
    else:
        print(shared().oc_line(level, SKILL_NAME, unit, tier, model, kind, text))


def run_mode(args):
    """The raw value of `mode=X`, `--preset X` or `--preset=X` in the arguments ('' when absent).

    `args` is the argument list or one string (the preload passes a single quoted "$ARGUMENTS"
    that may hold spaces, an apostrophe and `mode=...`); a string is split on whitespace only.
    """
    toks = (args if isinstance(args, str) else " ".join(args)).split()
    mode = ""
    for i, x in enumerate(toks):
        if x.startswith("mode="):
            mode = x.split("=", 1)[1]
        elif x == "--preset" and i + 1 < len(toks):
            mode = toks[i + 1]
        elif x.startswith("--preset="):
            mode = x.split("=", 1)[1]
    return mode.strip("'\"")


def preset_from_args(args):
    """The canonical preset named in the arguments, or '' when absent or invalid."""
    raw = run_mode(args)
    if not raw:
        return ""
    try:
        preset, _ = shared().mode_to_preset(raw)
    except ValueError:
        return ""
    return preset if preset in PRESETS else ""


def resolve_preset(raw):
    """Canonical preset for a --preset value: '' when unset, None (after an OC-ERROR line) when unknown."""
    if not raw:
        return ""
    try:
        preset, note = shared().mode_to_preset(raw)
    except ValueError as e:
        preset, note = "", str(e)
    if preset not in PRESETS:
        emit_oc("OC-ERROR", "preset", "config", note or "unknown preset %r (use claude, hybrid or opencode)" % raw)
        return None
    if note:
        emit_oc("OC-WARN", "preset", "config", note)
    return preset


def report_opencode_state(preset, routing, doctor, cs):
    """Print every reason opencode cannot serve this run, at the moment contracts sees it."""
    for w in routing.get("config_warnings") or []:
        emit_oc("OC-WARN", "config", "config", w)
    if preset == "claude":
        return
    problems = routing.get("config_problems") or []
    for p in problems:
        emit_oc("OC-ERROR", "config", "config", p)
    tiers = routing.get("tiers") or {}
    entries = doctor.get("tiers") or {}
    roles = dict(routing.get("roles") or {})
    if preset == "opencode":
        roles.update(routing.get("max_roles") or {})
    used = set(roles.get(c["tier"]) for c in cs) - {None, "claude"}
    now = time.time()
    for name in sorted(set(entries) | used):
        entry = entries.get(name)
        tier = tiers.get(name) or {}
        spec = shared().model_spec(tier) or "-"
        if tier.get("disabled") and name in used:
            emit_oc("OC-ERROR", "doctor", "config", "tier %s is disabled in the routing file" % name, name, spec)
            continue
        fresh = isinstance(entry, dict) and shared().cache_fresh(entry, tier, now)  # same model#variant, within the TTL
        if fresh and entry.get("ok") is False:
            emit_oc("OC-ERROR", "doctor", entry.get("kind") or "config", entry.get("detail") or "tier check failed",
                    name, spec)
        elif name in used and not problems and not (fresh and entry.get("ok") is True):
            emit_oc("OC-ERROR", "doctor", "config",
                    "no fresh doctor entry for this model; run plan_tool.py doctor --ping", name, spec)


def agent_is_stale(agent_path):
    """True if the installed writer agent still has the __PLAN_TOOL__ placeholder (setup never ran/applied)."""
    try:
        return "__PLAN_TOOL__" in load(agent_path)
    except OSError:
        return False


def written_ids(cs, work, allow, repo):
    """Tasks whose body file exists and lints clean now (it survived a contracts re-run: contract unchanged)."""
    out = set()
    for c in cs:
        path = os.path.join(work, "tasks", c["id"] + ".md")
        if not os.path.isfile(path):
            continue
        earlier = {f for x in cs if num(x["id"]) < num(c["id"]) for f in x["files"]}
        try:
            errs, _ = lint_body(c, strip_generated(load(path)), allow, c["id"], repo, earlier)
        except (OSError, UnicodeDecodeError):
            continue
        if not errs:
            out.add(c["id"])
    return out


def keep_run_tiers(doctor, routing, old_info, now):
    """A doctor entry that went stale in the middle of a run must not downgrade a tier the run already routes to
    opencode. Returns a copy of `doctor` (never written back) whose entries for those tiers are re-stamped: the
    entry was ok, and the model#variant is the one the run started with. A real failure (ok false) still counts."""
    sh_ = shared()
    old_tiers = ((old_info or {}).get("oc") or {}).get("tiers") or {}
    used = {str(b)[3:] for b in ((old_info or {}).get("backend") or {}).values() if str(b).startswith("oc:")}
    entries = dict(doctor.get("tiers") or {})
    tiers = routing.get("tiers") or {}
    changed = False
    for name in used:
        entry, tier = entries.get(name), tiers.get(name) or {}
        key = sh_.cache_key(tier)
        if (isinstance(entry, dict) and entry.get("ok") is True and key and entry.get("key") == key
                and sh_.cache_key(old_tiers.get(name) or {}) == key and not sh_.cache_fresh(entry, tier, now)):
            entries[name] = dict(entry, checked_at=now)
            changed = True
    return dict(doctor, tiers=entries) if changed else doctor


# ------------------------------------------------------------------ commands
def contract_hashes(cs):
    """Hash of each task's own contract text plus the text of every producer it depends on (deps_all)."""
    text = {c["id"]: c["text"] for c in cs}
    out = {}
    for c in cs:
        blob = "\n".join([c["text"]] + [text[d] for d in c["deps_all"] if d in text])
        out[c["id"]] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return out


def cmd_contracts(a):
    preset_arg = resolve_preset(a.preset)
    if preset_arg is None:
        return 1
    plan_path = os.path.abspath(a.plan)
    plan = load(plan_path)
    cs, errs = parse_contracts(plan)
    if cs is None:
        return report(errs, [], "")
    repo = repo_root(plan_path)
    spec = os.path.abspath(a.spec) if a.spec else None
    e2, warns = analyze(cs, spec, repo)
    errs += e2 + scan(plan.split(TASKS_MARK, 1)[0], a.allow, os.path.basename(plan_path), skip_contracts=True)
    if errs:
        return report(errs, warns, "")
    use_here()
    import hp_briefs
    import hp_doctor
    import hp_partition
    import hp_router
    from pathlib import Path
    cap, from_env = cap_from_env()
    cap = max(1, min(MAX_AGENTS, a.agents or cap))  # Claude writers: min(cap, ceil(Claude-routed tasks / WRITER_MIN_TASKS)), see hp_partition
    work = default_work(plan_path)
    _, old_info = load_work(plan_path)
    old_hashes = old_info.get("contract_hash", {}) if old_info else {}
    new_hashes = contract_hashes(cs)
    tasks_dir = os.path.join(work, "tasks")
    for tid, h in new_hashes.items():
        if tid in old_hashes and old_hashes[tid] != h:
            for suffix in ("", ".ok", ".rev", ".warn", ".fail", ".oc"):
                p = os.path.join(tasks_dir, tid + ".md" + suffix)
                if os.path.exists(p):
                    os.remove(p)
    shutil.rmtree(os.path.join(work, "briefs"), ignore_errors=True)
    shutil.rmtree(os.path.join(work, "oc"), ignore_errors=True)
    os.makedirs(tasks_dir, exist_ok=True)
    for name in os.listdir(tasks_dir):  # an .oc marker stays as long as the opencode-written body it describes
        if name.endswith(".md.oc") and not os.path.exists(os.path.join(tasks_dir, name[:-3])):
            os.remove(os.path.join(tasks_dir, name))
    cmap = {c["id"]: c for c in cs}
    routing = hp_router.load_routing(Path(SKILL_DIR) / "routing.default.json", hp_router.user_routing_path())
    try:  # the mode is frozen in work.json: a re-run without --preset keeps it
        preset = hp_router.effective_preset(routing, preset_arg or str((old_info or {}).get("preset") or ""))
    except ValueError as e:
        emit_oc("OC-ERROR", "preset", "config", str(e))
        return 1
    doctor = keep_run_tiers(hp_doctor.load_doctor(hp_doctor.doctor_cache_path()), routing, old_info, time.time())
    routed = hp_partition.route_groups(cs, routing, doctor, preset, cap)
    report_opencode_state(preset, routing, doctor, cs)
    claude = [(gid, g) for gid, backend, g in routed if backend == "claude"]
    oc = [(gid, backend, g) for gid, backend, g in routed if backend.startswith("oc:")]
    held = [(gid, g) for gid, backend, g in routed if backend == "held"]
    claude_todo = [(gid, g) for gid, g in claude
                   if not all(os.path.exists(os.path.join(tasks_dir, c["id"] + ".md.ok")) for c in g)]
    for gid, g in claude + held:
        save(os.path.join(work, "briefs", gid + ".md"), writer_brief(plan_path, plan, g, cmap, work, spec, repo, a.allow))
    # A re-run keeps every opencode task whose body survived (contract unchanged, lints clean, e.g. a reviewer fixed it):
    # only groups with a pending or invalidated task get a brief, and the brief names just those tasks.
    written = written_ids(cs, work, a.allow, repo)
    oc_todo = []
    for gid, backend, g in oc:
        for c in g:
            body = os.path.join(tasks_dir, c["id"] + ".md")
            if c["id"] in written and done_state(body, "ok") != "done":
                touch(body + ".ok")
        todo = [c for c in g if c["id"] not in written]
        if todo:
            oc_todo.append((gid, backend, todo))
            save(os.path.join(work, "briefs", gid + ".oc.md"), hp_briefs.oc_brief(plan_path, plan, todo, cmap, work, spec, repo, a.allow))
    ordered = sorted(routed, key=lambda r: num(r[2][0]["id"]))
    save(os.path.join(work, "work.json"), json.dumps({
        "plan": plan_path, "spec": spec, "repo": repo, "allow": a.allow, "agents": cap,
        "tasks": [c["id"] for c in cs], "groups": {gid: [c["id"] for c in g] for gid, backend, g in ordered}, "review": [],
        "contract_hash": new_hashes,
        "preset": preset, "backend": {gid: backend for gid, backend, g in ordered},
        "oc": {"tiers": routing.get("tiers", {}), "max_repairs": routing.get("max_repairs", 2),
               "throttle_cooldown_s": routing.get("throttle_cooldown_s", 120),
               "review_oc": hp_router.review_policy(routing, preset)}}, indent=1))
    _, n, width = waves_block(cs)
    agent = "hybrid-plan-task-writer" if agent_installed(repo) else "general-purpose"
    extra = [] if a.agents or cap >= MAX_AGENTS else ["NOTE parallel cap = %d (default); run `%s setup` once to set it to %d" % (DEFAULT_CAP, qtool(), RECOMMENDED_CAP)]
    extra.append("WORK %s" % work)
    if claude_todo:
        extra += ["DISPATCH %d writers in ONE message | subagent_type=%s | model per row | description 'plan <ID>'" % (len(claude_todo), agent),
                  "prompt (verbatim): Read <brief path> and follow it exactly.",
                  "ID   MODEL   TASKS     BRIEF"] + dispatch_lines(claude_todo, work, "write")
    elif claude:
        extra.append("NOTHING TO DISPATCH: every Claude task already has a fresh .ok mark")
    if oc_todo:
        extra.append("OPENCODE %d groups (%s) | run in the BACKGROUND in the SAME message: %s oc-write %s" % (
            len(oc_todo), ", ".join(span_of(g) for _, _, g in oc_todo), qtool(), shlex.quote(plan_path)))
        extra += oc_dispatch_lines(oc_todo, work)
        for tier in sorted({b[3:] for _, b, _ in oc_todo}):
            n = sum(1 for _, b, _ in oc_todo if b == "oc:" + tier)
            mp = hp_partition._max_parallel(routing, tier)
            if n > mp:
                extra.append("NOTE %d of the %d %s groups queue for a free slot (max_parallel %d); wait covers them" % (n - mp, n, tier, mp))
    elif oc:
        extra.append("OPENCODE none to run: every opencode task body is already written (kept from the earlier run)")
    if held:
        extra += ["HELD %d groups (%s) | preset opencode has no usable opencode tier for them: NOT dispatched, no fallback to Claude on its own" % (
                      len(held), ", ".join(span_of(g) for _, g in held)),
                  "Relay the OC-ERROR lines above, then ask the user what to do (SKILL.md, Failure policy). Claude writer briefs, only if the user picks Claude:",
                  "ID   MODEL   TASKS     BRIEF"] + dispatch_lines(held, work, "write")
    if claude or oc:
        extra.append("THEN run: %s wait %s" % (qtool(), shlex.quote(plan_path)))
    else:
        extra.append("NOTHING dispatched: every group is held")
    ok = "OK contracts: %d tasks | %d waves | max wave width %d | %d writers (cap %d)" % (len(cs), n, width, len(claude_todo), cap)
    if oc:
        ok += " | %d opencode groups" % len(oc_todo)
    if held:
        ok += " | %d held" % len(held)
    return report([], warns, ok, extra)


def task_label(path):
    m = re.search(r"(T\d{2,3})\.md$", os.path.basename(path))
    return m.group(1) if m else None


def lint_file(plan_path, task_path, allow_extra=()):
    plan = load(plan_path)
    cs, errs = parse_contracts(plan)
    tid = task_label(task_path)
    c = next((x for x in (cs or []) if tid and x["id"] == tid), None)
    if c is None:
        return errs + ["no contract matches %s" % os.path.basename(task_path)], [], None
    _, work = load_work(plan_path)
    analyze(cs, None, None)
    allow = list(work.get("allow", [])) + list(allow_extra)
    repo = work.get("repo") or repo_root(plan_path)
    earlier = {f for x in cs if num(x["id"]) < num(c["id"]) for f in x["files"]}
    e, w = lint_body(c, strip_generated(load(task_path)), allow, c["id"], repo, earlier)
    return e, w, c


def apply_marks(task_path, mark, errs, warns):
    """Shared by lint-task and hook-lint: .fail on error, .warn on a clean-but-warned
    lint, and a stale .warn/.fail is removed as soon as it no longer applies."""
    fail_path, warn_path = task_path + ".fail", task_path + ".warn"
    if errs:
        with open(fail_path, "w") as f:
            f.write("\n".join(errs))
        return
    if os.path.exists(fail_path):
        os.remove(fail_path)
    touch(task_path + "." + mark)
    if warns:
        with open(warn_path, "w") as f:
            f.write("\n".join(warns))
    elif os.path.exists(warn_path):
        os.remove(warn_path)


def cmd_lint_task(a):
    e, w, c = lint_file(os.path.abspath(a.plan), a.task, a.allow)
    rc = report(e, w, "OK %s" % (c["id"] if c else ""))
    apply_marks(a.task, a.mark, e, w)
    return rc


def cmd_hook_lint(a):
    try:
        data = json.load(sys.stdin)
        path = (data.get("tool_input") or {}).get("file_path") or ""
        m = re.search(r"[\\/]\.hybrid-work[\\/][^\\/]+[\\/]tasks[\\/]T\d{2,3}\.md$", path)
        if not m:
            return 0
        work = os.path.dirname(os.path.dirname(path))
        info = json.loads(load(os.path.join(work, "work.json")))
        e, w, c = lint_file(info["plan"], path)
        apply_marks(path, "ok", e, w)
        if not e:
            msg = "plan-lint: OK %s%s" % (c["id"], "".join("\nWARN " + x for x in w))
        else:
            msg = "plan-lint: FAIL %d error(s) - fix with Edit (re-linted automatically):\n%s" % (len(e), "\n".join("ERR  " + x for x in e[:25]))
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))
    except Exception as ex:  # never break the writer
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "plan-lint: unavailable (%s) - run LINT with Bash" % ex}}))
    return 0


def done_state(path, mark):
    if not os.path.exists(path):
        return "absent"
    mk = path + "." + mark
    if os.path.exists(mk) and os.stat(mk).st_mtime_ns >= os.stat(path).st_mtime_ns:
        return "done"
    return "not-reviewed" if mark == "rev" else "unlinted-or-failing"


def log_review(plan_path, work, info):
    hashes = info.get("review_hash") or {}
    if not hashes or info.get("review_logged"):
        return
    use_here()
    import hp_telemetry
    t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    repo = info.get("repo") or repo_root(plan_path)
    for tid in sorted(hashes, key=num):
        path = os.path.join(work, "tasks", tid + ".md")
        try:
            meta = json.loads(load(path + ".oc"))
        except (OSError, ValueError):
            meta = {}
        tier = meta.get("tier", "") if isinstance(meta, dict) else ""
        hp_telemetry.record({"t": t, "kind": "review", "repo": repo, "plan": plan_path, "task": tid, "tier": tier,
                             "fixed_by_review": hp_telemetry.file_sha(path) != hashes[tid]})
    info["review_logged"] = True
    save(os.path.join(work, "work.json"), json.dumps(info, indent=1))


def held_task_ids(info, work=None):
    """Tasks that are held: routed to `held` at contracts time, or (with `work`) from a group that
    failed while running in preset opencode - its <gid>.fallback marker says held, sent or not."""
    groups = info.get("groups") or {}
    out = {t for gid, b in (info.get("backend") or {}).items() if b == "held" for t in groups.get(gid, [])}
    folder = os.path.join(work, "oc") if work else ""
    for name in sorted(os.listdir(folder)) if folder and os.path.isdir(folder) else []:
        if name.endswith(".fallback"):
            try:
                marker = json.loads(load(os.path.join(folder, name)))
            except (OSError, ValueError):
                continue
            if isinstance(marker, dict) and marker.get("held"):
                out.update(str(t) for t in marker.get("tasks") or [])
    return out


def print_unreported(work):
    """Print OC lines nobody has seen yet (oc/oc-errors.jsonl) and return them."""
    use_here()
    import hp_write
    fresh = shared().take_unreported(hp_write.errors_log(work))
    for line in fresh:
        print(line)
    return fresh


def clean_work(work):
    """Remove the scratch dir but keep oc/oc-errors.jsonl; return True when the log was kept."""
    log = os.path.join(work, "oc", "oc-errors.jsonl")
    kept = load(log) if os.path.isfile(log) else None
    shutil.rmtree(work, ignore_errors=True)
    if kept is not None:
        save(log, kept)
    return kept is not None


def task_mtime(task_path):
    """Latest mtime of the body and its .fail mark; 0.0 when neither exists."""
    m = 0.0
    for p in (task_path, task_path + ".fail"):
        if os.path.exists(p):
            m = max(m, os.stat(p).st_mtime)
    return m


def task_stuck(task_path, quiet, min_age=45):
    """A pending task is 'stuck' once its body and .fail mark both exist and have not
    changed for min_age seconds of wait time (quiet = seconds since wait observed the
    last change; starts at wait start) - its agent is gone, not just slow."""
    return os.path.exists(task_path) and os.path.exists(task_path + ".fail") and quiet >= min_age


def cmd_wait(a):
    plan_path = os.path.abspath(a.plan)
    work, info = load_work(plan_path)
    if not info:
        return report(["no work.json - run contracts first"], [], "")
    ids = info.get("review", []) if a.review else info.get("tasks", [])
    mark = "rev" if a.review else "ok"
    oc_groups = [g for g, b in (info.get("backend") or {}).items() if str(b).startswith("oc:")]
    hp_wait = None
    if oc_groups and not a.review:
        use_here()
        import hp_wait
    try:
        min_age = int(os.environ.get("PLAN_TOOL_WAIT_MIN_AGE", "45"))
    except ValueError:
        min_age = 45
    t0 = last = time.time()
    seen = -1
    changed = {}  # task -> (last seen mtime, time the change was observed)
    for t in ids:
        changed[t] = (task_mtime(os.path.join(work, "tasks", t + ".md")), t0)
    while True:
        fresh = print_unreported(work)
        st = {t: done_state(os.path.join(work, "tasks", t + ".md"), mark) for t in ids}
        ndone = sum(1 for v in st.values() if v == "done")
        if ndone != seen:
            seen, last = ndone, time.time()
        if ndone == len(ids):
            print("DONE %d/%d %s in %.0fs" % (ndone, len(ids), "reviews" if a.review else "tasks", time.time() - t0))
            if a.review:
                log_review(plan_path, work, info)
            return 0
        alive = False
        if hp_wait is not None:
            alive = hp_wait.oc_alive(work)
            if alive:
                last = time.time()
            lines = hp_wait.pending_fallback_lines(work)
            if not lines and not alive:
                died = hp_wait.runner_died(plan_path, work, info, time.time() - t0)
                lines = (hp_wait.pending_fallback_lines(work) if died else []) or died  # marks them sent
            if lines:
                for l in lines:
                    print(l)
                if any(l.startswith("FALLBACK ") for l in lines):
                    print("Launch every FALLBACK Agent call above in ONE message, then run wait again.")
                if any(l.startswith("HELD ") for l in lines):
                    print("Do not dispatch the HELD groups above. Relay the OC-ERROR lines, then ask the user (SKILL.md, Failure policy).")
                if not any(l.startswith(("FALLBACK ", "HELD ")) for l in lines):
                    print("Relay the OC lines above, then run wait again.")
                return 2
        if any(l.startswith("OC-ERROR") for l in fresh):
            print("Relay the OC-ERROR lines above to the user first, then run wait again.")
            return 2
        held = set() if (a.review or a.include_held) else held_task_ids(info, work)  # re-read: a group can be held while we wait
        if held and not [t for t, v in st.items() if v != "done" and t not in held]:
            pend = " ".join(sorted(t for t in held if st.get(t) != "done"))
            print("HELD %s not written: preset opencode has no usable tier for them and never falls back on its own." % pend)
            print("Ask the user (SKILL.md, Failure policy). To write them with Claude, dispatch their HELD briefs, then run wait --include-held.")
            return 3
        now = time.time()
        elapsed = now - t0
        pend_ids = [t for t, v in st.items() if v != "done"]
        for t in pend_ids:
            m = task_mtime(os.path.join(work, "tasks", t + ".md"))
            if m != changed[t][0]:
                changed[t] = (m, now)
        if not alive and pend_ids and all(task_stuck(os.path.join(work, "tasks", t + ".md"), now - changed[t][1], min_age)
                                          for t in pend_ids):
            print("PENDING %d/%d after %.0fs (all pending are failing and unchanged for >=%ds) -> %s"
                  % (ndone, len(ids), elapsed, min_age, " ".join("%s:%s" % (t, st[t]) for t in pend_ids)))
            print("If an agent for these IDs is still running, run wait again; otherwise re-dispatch only these IDs.")
            return 1
        if time.time() - t0 > a.timeout or time.time() - last > a.idle:
            pend = ["%s:%s" % (t, v) for t, v in st.items() if v != "done"]
            print("PENDING %d/%d after %.0fs (%s) -> %s" % (ndone, len(ids), time.time() - t0,
                  "timeout" if time.time() - t0 > a.timeout else "no progress for %ds" % a.idle, " ".join(pend)))
            if alive:
                print("oc-write is still running (groups beyond a tier's max_parallel wait for a free slot): run wait again.")
            print("If their agents are still running, run wait again; if they returned FAIL or stopped, re-dispatch only these IDs.")
            return 1
        time.sleep(0.5)


def collect_tasks(work):
    tdir = os.path.join(work, "tasks")
    out = {}
    for f in sorted(os.listdir(tdir)) if os.path.isdir(tdir) else []:
        m = re.match(r"^(T\d{2,3})\.md$", f)
        if m:
            out[m.group(1)] = load(os.path.join(tdir, f))
    return out


def cmd_review(a):
    plan_path = os.path.abspath(a.plan)
    plan = load(plan_path)
    work, info = load_work(plan_path)
    cs, errs = parse_contracts(plan)
    if cs is None or not info:
        return report(errs or ["no work.json - run contracts first"], [], "")
    analyze(cs, None, None)
    tasks = collect_tasks(work)
    review_oc = (info.get("oc") or {}).get("review_oc", "risky")
    picked, oc_ids = [], set()
    for c in cs:
        body = tasks.get(c["id"], "")
        is_oc = os.path.exists(os.path.join(work, "tasks", c["id"] + ".md.oc"))
        if is_oc:
            oc_ids.add(c["id"])
        why = []
        if a.all:
            why.append("all")
        if c["tier"] == "deep":
            why.append("tier deep")
        if len(body.splitlines()) > 250:
            why.append("long body")
        if len(c["consumes"]) >= 3:
            why.append("consumes %d" % len(c["consumes"]))
        if os.path.exists(os.path.join(work, "tasks", c["id"] + ".md.warn")):
            why.append("lint warnings")
        if is_oc and review_oc == "all":
            why.append("oc")
        if why and body:
            picked.append((c, why))
    shutil.rmtree(os.path.join(work, "review-briefs"), ignore_errors=True)
    info.pop("review_logged", None)
    if not picked:
        info["review"] = []
        info["review_hash"] = {}
        save(os.path.join(work, "work.json"), json.dumps(info, indent=1))
        print("NONE - no risky tasks; skip review and run assemble")
        return 0
    hashes = {}
    oc_picked = [c["id"] for c, _ in picked if c["id"] in oc_ids]
    if oc_picked:
        use_here()
        import hp_telemetry
        for tid in oc_picked:
            hashes[tid] = hp_telemetry.file_sha(os.path.join(work, "tasks", tid + ".md"))
    info["review_hash"] = hashes
    k = max(1, min(MAX_AGENTS, a.agents or info.get("agents") or DEFAULT_CAP, -(-len(picked) // WRITER_MIN_TASKS)))
    size = a.size or max(1, -(-len(picked) // k))  # default: ~WRITER_MIN_TASKS reviews per agent
    chunks = [[c for c, _ in picked[i:i + size]] for i in range(0, len(picked), size)]
    while len(chunks) > k:
        chunks = [chunks[i] + (chunks[i + 1] if i + 1 < len(chunks) else []) for i in range(0, len(chunks), 2)]
    groups = [("R%02d" % (i + 1), g) for i, g in enumerate(chunks)]
    spec = info.get("spec")
    for gid, g in groups:
        save(os.path.join(work, "review-briefs", gid + ".md"), reviewer_brief(plan_path, plan, g, work, spec, info.get("repo") or repo_root(plan_path)))
    info["review"] = [c["id"] for c, _ in picked]
    save(os.path.join(work, "work.json"), json.dumps(info, indent=1))
    rows = ["REVIEW %d tasks: %s" % (len(picked), ", ".join("%s(%s)" % (c["id"], "+".join(w)) for c, w in picked)),
            "DISPATCH %d reviewers in ONE message | subagent_type=general-purpose | model sonnet | description 'review <ID>'" % len(groups),
            "prompt (verbatim): Read <brief path> and follow it exactly.",
            "ID   MODEL   TASKS     BRIEF"] + dispatch_lines(groups, work, "review")
    rows.append("THEN run: %s wait %s --review" % (qtool(), shlex.quote(plan_path)))
    for r in rows:
        print(r)
    return 0


def render_plan(plan_head, cs, bodies):
    head = plan_head.rstrip() + "\n"
    if "Execution note" not in head:
        head = re.sub(r"^(# .*\n)", lambda m: m.group(1) + "\n" + NOTE + "\n", head, count=1, flags=re.M)
    if not re.search(r"^## Execution Protocol", head, re.M):
        m = re.search(r"^## ", head, re.M)
        head = head[:m.start()] + PROTOCOL + "\n" + head[m.start():] if m else head + "\n" + PROTOCOL
    if not re.search(r"^## File Structure", head, re.M):
        dirs = {}
        for c in cs:
            for f in c["files"]:
                d, b = os.path.split(f)
                dirs.setdefault(d, {}).setdefault(b, []).append(c["id"])
        fs = "## File Structure\n\n" + "\n".join("- `%s/` \u2014 %s" % (d or ".", ", ".join(
            "%s (%s)" % (b, ", ".join(t)) for b, t in fl.items())) for d, fl in dirs.items()) + "\n\n"
        m = re.search(r"^## Contracts", head, re.M)
        head = head[:m.start()] + fs + head[m.start():]
    block, n, width = waves_block(cs)
    wv = WAVES_OPEN + "\n" + block + "\n" + WAVES_CLOSE
    if WAVES_OPEN in head:
        head = re.sub(re.escape(WAVES_OPEN) + r".*?(" + re.escape(WAVES_CLOSE) + r"|\Z)", lambda m: wv, head, count=1, flags=re.S)
    else:
        head = head.rstrip() + "\n\n" + wv + "\n"
    tasks = "\n---\n\n".join(render_task(c, bodies[c["id"]]) for c in cs)
    return head.rstrip() + "\n\n" + TASKS_MARK + "\n\n" + tasks, n, width


def full_check(plan_path, plan, cs, bodies, spec, allow):
    repo = repo_root(plan_path)
    errs, warns = analyze(cs, spec, repo)
    if errs:
        return errs, warns

    def _lint_one(c):
        if c["id"] not in bodies:
            return ["%s: task body missing" % c["id"]], []
        earlier = {f for x in cs if num(x["id"]) < num(c["id"]) for f in x["files"]}
        return lint_body(c, bodies[c["id"]], allow, c["id"], repo, earlier)

    # I/O-bound (each task's code blocks may spawn `node --check`/`bash -n`) -> threads help.
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, max(1, len(cs)))) as ex:
        for e, w in ex.map(_lint_one, cs):
            errs += e
            warns += w
    ids = {c["id"] for c in cs}
    errs += ["%s: task body has no contract" % t for t in sorted(set(bodies) - ids)]
    head = plan.split(TASKS_MARK, 1)[0]
    errs += scan(head, allow, "header", skip_contracts=True)
    return errs, warns


def cmd_assemble(a):
    plan_path = os.path.abspath(a.plan)
    plan = load(plan_path)
    work, info = load_work(plan_path)
    cs, errs = parse_contracts(plan)
    if cs is None:
        return report(errs, [], "")
    bodies = {t: strip_generated(x) for t, x in collect_tasks(work).items()}
    spec = a.spec or info.get("spec")
    allow = list(info.get("allow", [])) + a.allow
    e2, warns = full_check(plan_path, plan, cs, bodies, spec, allow)
    if errs + e2:
        return report(errs + e2, warns, "")
    head = re.split(r"^" + re.escape(TASKS_MARK) + r"\s*$", plan, maxsplit=1, flags=re.M)[0]
    head = re.sub(re.escape(WAVES_OPEN) + r".*?" + re.escape(WAVES_CLOSE) + r"\s*", "", head, flags=re.S)
    out, n, width = render_plan(head, cs, bodies)
    save(plan_path, out)
    kept = False
    if a.clean:
        kept = clean_work(work)
        parent = os.path.dirname(work)
        if os.path.isdir(parent) and not os.listdir(parent):
            os.rmdir(parent)
    removed = (" | workdir removed" + (" (oc/oc-errors.jsonl kept)" if kept else "")) if a.clean else ""
    return report([], warns, "OK assembled %d tasks -> %s | %d waves | max wave width %d%s"
                  % (len(cs), plan_path, n, width, removed))


def cmd_check(a):
    plan_path = os.path.abspath(a.plan)
    plan = load(plan_path)
    cs, errs = parse_contracts(plan)
    if cs is None:
        return report(errs, [], "")
    lines = plan.splitlines(True)
    first = next((i for i, l in enumerate(lines) if TASK_HEAD.match(l) or l.strip() == TASKS_MARK), len(lines))
    head, rest = "".join(lines[:first]), "".join(lines[first:])
    bodies, cur = {}, None
    for l in rest.splitlines(True):
        m = TASK_HEAD.match(l)
        if m:
            cur = m.group(1)
            bodies[cur] = ""
        if cur:
            bodies[cur] += l
    bodies = {k: strip_generated(v) for k, v in bodies.items()}
    e2, warns = full_check(plan_path, plan, cs, bodies, a.spec, a.allow)
    if errs + e2:
        return report(errs + e2, warns, "")
    head = re.sub(re.escape(WAVES_OPEN) + r".*?" + re.escape(WAVES_CLOSE) + r"\s*", "", head, flags=re.S)
    out, n, width = render_plan(head, cs, bodies)
    save(plan_path, out)
    return report([], warns, "OK plan: %d tasks | %d waves | max wave width %d -> %s" % (len(cs), n, width, plan_path))


def cmd_oc_write(a):
    use_here()
    import hp_write
    hp_write.oc_write(os.path.abspath(a.plan))
    return 0  # oc-write always exits 0; results live in the task and fallback files


def cmd_doctor(a):
    use_here()
    import hp_doctor
    import hp_router
    from pathlib import Path
    user = hp_router.user_routing_path()
    routing = hp_router.load_routing(Path(SKILL_DIR) / "routing.default.json", user)
    cache = hp_doctor.doctor_cache_path()
    binary = os.environ.get("HYBRID_WRITING_PLANS_OC_BIN", "opencode")
    scratch = tempfile.mkdtemp(prefix="hybrid-plan-doctor-")
    try:
        data = hp_doctor.run_doctor(binary, routing, a.ping, Path(scratch), hp_doctor.load_doctor(cache))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    hp_doctor.write_doctor(cache, data)
    tiers = routing.get("tiers") or {}
    sources = routing.get("model_sources") or {}
    problems = routing.get("config_problems") or []
    print("routing: %s" % (user if os.path.exists(str(user)) else "none (shipped defaults)"))
    print(shared().config_summary(tiers, problems))
    for w in routing.get("config_warnings") or []:
        emit_oc("OC-WARN", "config", "config", w)
    for p in problems:
        emit_oc("OC-ERROR", "config", "config", p)
    if data.get("ok"):
        print("opencode: v%s (%s)" % (data.get("version", "?"), data.get("binary") or binary))
    else:
        print("opencode: unavailable (%s)" % binary)
    failed = 0
    for name, t in sorted((data.get("tiers") or {}).items()):
        spec = tiers.get(name) or {}
        model = spec.get("model", "") + ("#" + spec["variant"] if spec.get("variant") else "")
        if t.get("ok"):
            print("tier %-6s %s (%s) ok" % (name, model, sources.get(name, "shared")))
        else:
            failed += 1
            emit_oc("OC-ERROR", "doctor", t.get("kind") or "config", t.get("detail") or "tier check failed",
                    name, shared().model_spec(spec) or "-")
    print("doctor cache: %s" % cache)
    print(hp_doctor.status_line(routing, data, "", time.time()))
    return 0 if data.get("ok") and not problems and not failed else 1


def cmd_stats(a):
    use_here()
    import hp_telemetry
    records = hp_telemetry.load_records(hp_telemetry.telemetry_path())
    for line in hp_telemetry.stats_lines(records, os.path.abspath(a.repo) if a.repo else ""):
        print(line)
    return 0


# ------------------------------------------------------------------ context (never fails)
def sh(cmd, cwd=None, timeout=8):
    if cmd and cmd[0] == "git" and "--no-optional-locks" not in cmd:
        cmd = [cmd[0], "--no-optional-locks"] + list(cmd[1:])
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.stdout if p.returncode == 0 else ""
    except Exception:
        return ""


OC_UNAVAILABLE = "opencode: unavailable (status unreadable; run plan_tool.py doctor --ping)"


def opencode_line(args):
    preset = preset_from_args(args)
    try:
        use_here()
        from pathlib import Path
        import hp_doctor
        import hp_router
        routing = hp_router.load_routing(Path(SKILL_DIR) / "routing.default.json", hp_router.user_routing_path())
        doctor = hp_doctor.load_doctor(hp_doctor.doctor_cache_path())
        return hp_doctor.status_line(routing, doctor, preset, time.time())
    except Exception:
        return OC_UNAVAILABLE


def config_line():
    try:
        use_here()
        from pathlib import Path
        import hp_router
        routing = hp_router.load_routing(Path(SKILL_DIR) / "routing.default.json", hp_router.user_routing_path())
        line = shared().config_summary(routing.get("tiers") or {}, routing.get("config_problems") or [])
        sources = routing.get("model_sources") or {}
        marks = ["%s (%s)" % (n, sources[n]) for n in ("std", "lite") if sources.get(n) in ("skill", "shared")]
        return line + (" | model from: " + ", ".join(marks) if marks else "")
    except Exception:
        return "shared config: $HYBRID_OPENCODE_STD/$HYBRID_OPENCODE_LITE (unreadable)"


def mode_line(args):
    preset = preset_from_args(args)
    if preset:
        return "mode: %s (from arguments)" % preset
    raw = run_mode(args)
    if raw:
        return "mode: %r is not valid -> ask the user which mode to run (hybrid, claude or opencode)" % raw
    return "mode: unset -> ask the user which mode to run (hybrid, claude or opencode)"


def cmd_context(a):
    out = []
    try:
        cwd = os.getcwd()
        repo = repo_root(cwd)
        out.append("date %s | cwd %s | repo %s" % (time.strftime("%Y-%m-%d"), cwd, repo))
        out.append("tool: %s" % qtool())
        cap, env = cap_from_env()
        k = min(MAX_AGENTS, cap)
        out.append("parallel: subagent cap %d%s -> writers per wave <= min(%d, ceil(tasks/%d))%s" % (
            cap, "" if env else " (default; CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS unset)", k, WRITER_MIN_TASKS,
            "" if cap >= MAX_AGENTS else " | one-time set to %d: %s setup --apply (then restart)" % (RECOMMENDED_CAP, qtool())))
        ag = agent_installed(repo)
        if ag and agent_is_stale(ag):
            out.append("writer agent: hybrid-plan-task-writer at %s is STALE (still has __PLAN_TOOL__ placeholder) - re-run %s setup --apply" % (ag, qtool()))
        else:
            out.append("writer agent: %s" % ("hybrid-plan-task-writer (%s) - auto-lint hook on" % ag if ag else "not installed -> use general-purpose"))
        raw = " ".join(a.rest or [])
        out.append(opencode_line(raw))
        out.append(config_line())
        out.append(mode_line(raw))
        if "--thorough" in raw:
            out.append("mode: THOROUGH -> review every task (review --all)")
        rest_tokens = raw.replace("--thorough", " ").split()
        spec = next((x for x in rest_tokens if not x.startswith("--") and os.path.isfile(x)), None)
        branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo).strip()
        files = sh(["git", "ls-files"], repo).splitlines()
        if not files:
            for root, dirs, fs in os.walk(repo):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "venv", ".venv", "dist", "build", "__pycache__", "target")]
                files += [os.path.relpath(os.path.join(root, f), repo) for f in fs]
                if len(files) > 20000:
                    break
        dirty = len(sh(["git", "status", "--porcelain"], repo).splitlines())
        out.append("git: branch %s | %d dirty | %d files" % (branch or "-", dirty, len(files)))
        plans = os.path.join(repo, "docs", "plans")
        specs_dir = os.path.join(repo, "docs", "specs")
        out.append("plan path: docs/plans/%s-<feature>.md (%d existing plans)" % (
            time.strftime("%Y-%m-%d"), len([f for f in os.listdir(plans) if f.endswith(".md")]) if os.path.isdir(plans) else 0))
        if not spec and os.path.isdir(specs_dir):
            recent = sorted((os.path.join(specs_dir, f) for f in os.listdir(specs_dir) if f.endswith(".md")), key=os.path.getmtime, reverse=True)[:5]
            if recent:
                out.append("recent specs: " + ", ".join(os.path.relpath(p, repo) for p in recent))
        if spec:
            sl = load(spec).splitlines()
            out.append("spec: %s (%d lines) - heading map (use for Spec: L ranges):" % (os.path.relpath(os.path.abspath(spec), repo), len(sl)))
            sfmask = fence_mask(sl)
            heads = [(i + 1, l.strip()) for i, l in enumerate(sl) if not sfmask[i] and re.match(r"^#{1,6}\s", l)]
            for j, (ln, h) in enumerate(heads[:80]):
                end = heads[j + 1][0] - 1 if j + 1 < len(heads) else len(sl)
                out.append("  L%d-%d %s" % (ln, end, h[:90]))
        marks = {"pyproject.toml": "python", "setup.py": "python", "requirements.txt": "python", "package.json": "node",
                 "go.mod": "go", "Cargo.toml": "rust", "pom.xml": "java/maven", "build.gradle": "java/gradle",
                 "build.gradle.kts": "kotlin/gradle", "Gemfile": "ruby", "composer.json": "php", "mix.exs": "elixir",
                 "CMakeLists.txt": "c/c++", "Makefile": "make", "deno.json": "deno", "pubspec.yaml": "dart"}
        found = [f for f in marks if os.path.isfile(os.path.join(repo, f))]
        stack = sorted(set(marks[f] for f in found))
        tests = []
        pj = os.path.join(repo, "package.json")
        if os.path.isfile(pj):
            try:
                scr = json.loads(load(pj)).get("scripts", {})
                tests += ["npm run %s -> %s" % (k2, v) for k2, v in scr.items() if re.search(r"test|lint|check|typecheck", k2)][:6]
            except ValueError:
                pass
        pp = os.path.join(repo, "pyproject.toml")
        if os.path.isfile(pp) and "pytest" in load(pp):
            tests.append("pytest (configured in pyproject.toml)")
        if "go" in stack:
            tests.append("go test ./...")
        if "rust" in stack:
            tests.append("cargo test")
        out.append("stack: %s | markers: %s" % (", ".join(stack) or "?", ", ".join(found) or "-"))
        if tests:
            out.append("test/check cmds: " + " ; ".join(tests))
        for md in ("CLAUDE.md", "AGENTS.md", ".claude/CLAUDE.md"):
            if os.path.isfile(os.path.join(repo, md)):
                out.append("conventions file: %s (%d lines) - copy binding rules into Global Constraints" % (md, len(load(os.path.join(repo, md)).splitlines())))
        testf = [f for f in files if re.search(r"(^|/)(tests?|__tests__|spec)/|(_test|\.test|\.spec|test_)[^/]*$", f)]
        out.append("test files: %d (e.g. %s)" % (len(testf), ", ".join(testf[:4]) or "-"))
        recent = []
        for l in sh(["git", "log", "-n", "40", "--name-only", "--pretty=format:"], repo).splitlines():
            if l.strip() and l not in recent and os.path.exists(os.path.join(repo, l)):
                recent.append(l)
        if recent:
            out.append("recently changed (pattern candidates): " + ", ".join(recent[:15]))
        dirs = {}
        for f in files:
            d = f.split("/", 1)[0] if "/" in f else "."
            dirs[d] = dirs.get(d, 0) + 1
        out.append("top-level: " + ", ".join("%s(%d)" % (d, n) for d, n in sorted(dirs.items(), key=lambda x: -x[1])[:25]))
        skip = re.compile(r"(^|/)(node_modules|vendor|dist|build|\.venv|venv|__pycache__|target|\.next)/|\.(lock|min\.js|map|png|jpg|svg|ico|woff2?)$")
        shown = [f for f in files if not skip.search(f)]
        out.append("files (%d of %d):" % (min(30, len(shown)), len(files)))
        out.append("  " + "\n  ".join(shown[:30]))
    except Exception as ex:
        out.append("context partial: %s" % ex)
    print("\n".join(out))
    return 0


# ------------------------------------------------------------------ setup
AGENT_TEMPLATE = os.path.join(SKILL_DIR, "agents", "hybrid-plan-task-writer.md")


def cmd_setup(a):
    home = os.path.expanduser("~")
    if a.scope == "user":
        settings = os.path.join(home, ".claude", "settings.json")
        agents = os.path.join(home, ".claude", "agents")
        edit_rule = "Edit(**/docs/plans/**)"
    else:
        root = repo_root(os.getcwd())
        settings = os.path.join(root, ".claude", "settings.local.json")
        agents = os.path.join(root, ".claude", "agents")
        edit_rule = "Edit(/docs/plans/**)"
    try:
        cur = json.loads(load(settings)) if os.path.exists(settings) else {}
    except ValueError as e:
        print("ERR  %s is not valid JSON (%s) - fix it first; nothing changed" % (settings, e))
        return 1
    new = json.loads(json.dumps(cur))
    changes = []
    env = new.setdefault("env", {})
    v = str(env.get("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", ""))
    if v and not (v.isdigit() and int(v) >= MAX_AGENTS):  # unset = Claude Code default 20, already enough; never lower a higher value
        env["CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS"] = str(RECOMMENDED_CAP)
        changes.append("env.CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS = %d (was %s)" % (RECOMMENDED_CAP, v or "unset -> 20"))
    allow = new.setdefault("permissions", {}).setdefault("allow", [])
    for rule in ("Bash(%s *)" % qtool(), edit_rule):
        if rule not in allow:
            allow.append(rule)
            changes.append("permissions.allow += %s" % rule)
    agent_path = os.path.join(agents, "hybrid-plan-task-writer.md")
    agent_text = load(AGENT_TEMPLATE).replace("__PLAN_TOOL__", qtool())
    agent_stale = not os.path.exists(agent_path) or load(agent_path) != agent_text
    if agent_stale:
        changes.append("write agent %s (sonnet, effort medium, auto-lint PostToolUse hook)" % agent_path)
    if not changes:
        print("OK setup already complete (%s scope)" % a.scope)
        return 0
    print(("APPLY" if a.apply else "DRY-RUN") + " %s scope:" % a.scope)
    for c in changes:
        print("  - " + c)
    if not a.apply:
        print("Re-run with --apply to write these changes.")
        return 0
    if any(c.startswith(("env.", "permissions.")) for c in changes):
        if os.path.exists(settings):
            shutil.copy2(settings, settings + ".bak")
        save(settings, json.dumps(new, indent=2) + "\n")
    if agent_stale:
        save(agent_path, agent_text)
    print("OK written (backup: %s.bak). Restart Claude Code so the env and agent load." % settings)
    return 0


# ------------------------------------------------------------------ main
def main(argv=None):
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    if raw_argv and raw_argv[0] == "context":
        # Bypass argparse's REMAINDER (mishandles a leading "--..." token after subparsers)
        # so a single quoted $ARGUMENTS token, however it starts, always reaches cmd_context.
        class _Ns(object):
            pass
        ns = _Ns()
        ns.rest = raw_argv[1:]
        return cmd_context(ns)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True

    def common(p):
        p.add_argument("--allow", action="append", default=[], help="exempt a scan hit: a case-insensitive stem (subagent also exempts subagents) or re:PATTERN matching the whole hit")
        return p
    p = sub.add_parser("context"); p.add_argument("rest", nargs=argparse.REMAINDER); p.set_defaults(fn=cmd_context)
    p = common(sub.add_parser("contracts")); p.add_argument("plan"); p.add_argument("--spec"); p.add_argument("--agents", type=int)
    p.add_argument("--preset", default=""); p.set_defaults(fn=cmd_contracts)
    p = common(sub.add_parser("lint-task")); p.add_argument("plan"); p.add_argument("task"); p.add_argument("--mark", default="ok", choices=["ok", "rev"]); p.set_defaults(fn=cmd_lint_task)
    p = sub.add_parser("hook-lint"); p.set_defaults(fn=cmd_hook_lint)
    p = sub.add_parser("wait"); p.add_argument("plan"); p.add_argument("--review", action="store_true")
    p.add_argument("--timeout", type=int, default=560); p.add_argument("--idle", type=int, default=240)
    p.add_argument("--include-held", action="store_true"); p.set_defaults(fn=cmd_wait)
    p = sub.add_parser("review"); p.add_argument("plan"); p.add_argument("--all", action="store_true"); p.add_argument("--size", type=int)
    p.add_argument("--agents", type=int); p.set_defaults(fn=cmd_review)
    p = common(sub.add_parser("assemble")); p.add_argument("plan"); p.add_argument("--spec"); p.add_argument("--clean", action="store_true"); p.set_defaults(fn=cmd_assemble)
    p = common(sub.add_parser("check")); p.add_argument("plan"); p.add_argument("--spec"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("setup"); p.add_argument("--scope", choices=["user", "project"], default="user"); p.add_argument("--apply", action="store_true"); p.set_defaults(fn=cmd_setup)
    p = sub.add_parser("oc-write"); p.add_argument("plan"); p.set_defaults(fn=cmd_oc_write)
    p = sub.add_parser("doctor"); p.add_argument("--ping", action="store_true"); p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("stats"); p.add_argument("--repo", default=""); p.set_defaults(fn=cmd_stats)
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv[:1] == ["context"]:
        return cmd_context(argparse.Namespace(rest=argv[1:]))
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except OSError as e:
        print("ERR  %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
