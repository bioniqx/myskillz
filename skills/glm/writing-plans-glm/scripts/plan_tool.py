#!/usr/bin/env python3
"""plan_tool.py v9 GLM - deterministic engine + in-process 64-way fan-out.
Stdlib only, Python 3.8+. Tuned for GLM-5.3 / GLM-5.3-Flash on OpenCode and ZCode.

  brief     [SPEC] [--thorough]        repo+spec+patterns in ONE call (replaces Phase 0)
  build     PLAN --spec S [opts]       validate -> fan out writers -> lint+repair -> review -> assemble
  contracts PLAN [--spec S]            validate only; agent lane: write briefs + print DISPATCH
  wait      PLAN [--review]            agent lane: block until every task file lints OK
  review    PLAN [--all]               agent lane: pick risky tasks, write reviewer briefs
  assemble  PLAN [--clean]             full check + render canonical plan
  check     PLAN [--spec S]            inline path (<= 3 tasks): check + render
  lint-task PLAN TASKFILE [--mark ok|rev]
  hook-lint                            PostToolUse hook -> additionalContext
  doctor                               lane / key / model / connectivity report
  setup     [--apply]                  configure harness (opencode | zcode | claude | auto)
Common: --allow WORD exempts a placeholder/portability hit. Exit 0 = OK, 1 = errors.
"""
import argparse, ast, json, os, random, re, shlex, shutil, subprocess, sys, tempfile, textwrap, threading, time
import urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
TOOL = os.path.abspath(__file__)
MAX_WORKERS = 64
DEFAULT_AGENT_CAP = 20

# ---- GLM routing -------------------------------------------------------
# tier -> (api model id, reasoning effort, agent-lane alias that z.ai maps to it)
GLM = {
    "light": ("glm-5.3-flash", "low",  "haiku"),
    "std":   ("glm-5.3-flash", "high", "haiku"),
    "deep":  ("glm-5.3",       "max",  "sonnet"),
}
EFFORT_BUDGET = {"low": 2048, "high": 8192, "max": 24576}
TIER_RANK = {"light": 0, "std": 1, "deep": 2}
DEFAULT_BASE = "https://api.z.ai/api/anthropic"
KEY_ENV = ("PLAN_API_KEY", "ZAI_API_KEY", "Z_AI_API_KEY", "ZHIPUAI_API_KEY", "GLM_API_KEY",
           "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY")

ID_RE = r"T\d{2,3}"
CONTRACT_HEAD = re.compile(r"^####\s+(%s)\s*[:·—-]\s*(.+?)\s*$" % ID_RE)
FIELD = re.compile(r"^-\s+(Depends|Parallel|Files|Produces|Consumes|Read|Spec|Tier):\s*(.*)$")
TASK_HEAD = re.compile(r"^###\s+(%s)\s*:\s*(.+?)\s*$" % ID_RE)
TICK = re.compile(r"`([^`\n]+)`")
TASKS_MARK = "<!-- TASKS -->"
WAVES_OPEN, WAVES_CLOSE = "<!-- WAVES -->", "<!-- /WAVES -->"

PLACEHOLDERS = [r"\bTBD\b", r"\bTODO\b", r"\bFIXME\b", r"\bXXX\b", r"implement(ed)? later",
    r"fill in (the )?details", r"add appropriate (error handling|validation)",
    r"handle (the )?edge cases", r"similar to (task\s*|T)\d+", r"same as (task\s*|T)\d+",
    r"write tests for the above", r"\.\.\.\s*(rest|remaining) of", r"your code here"]
PORTABILITY = [r"superpowers", r"\bsub-?skills?\b", r"\bsubagents?\b", r"\bslash commands?\b",
    r"\b(Task|Agent|Edit|Write|Read|Bash) tool\b", r"\bClaude\b", r"\bAnthropic\b",
    r"\bOpenCode\b", r"\bZCode\b", r"\bGLM\b", r"\bCopilot\b", r"\bCursor (IDE|editor|agent)\b",
    r"\binvoke (the |a )?skill\b"]
PH_RE = [re.compile(p, re.I) for p in PLACEHOLDERS]
PO_RE = [re.compile(p, re.I) for p in PORTABILITY]

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
    return os.path.join(os.path.dirname(p), ".work", os.path.splitext(os.path.basename(p))[0])


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
    if ok_msg:
        print(ok_msg)
    for line in extra or []:
        print(line)
    return 0


def sh(cmd, cwd=None, timeout=8):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.stdout if p.returncode == 0 else ""
    except Exception:
        return ""


# ------------------------------------------------------------------ harness + credentials
def detect_harness():
    """('opencode'|'zcode'|'claude'|'unknown', evidence)."""
    ev = []
    for k in os.environ:
        if k.startswith("OPENCODE"):
            ev.append(("opencode", k))
        elif k.startswith("ZCODE") or k.startswith("Z_CODE"):
            ev.append(("zcode", k))
        elif k.startswith("CLAUDE_CODE") or k == "CLAUDECODE":
            ev.append(("claude", k))
    if ev:
        return ev[0][0], ev[0][1]
    home = os.path.expanduser("~")
    for name, path in (("zcode", os.path.join(home, ".zcode")),
                       ("opencode", os.path.join(home, ".config", "opencode")),
                       ("claude", os.path.join(home, ".claude"))):
        if os.path.isdir(path) and SKILL_DIR.startswith(os.path.realpath(path)):
            return name, path
    for name, path in (("zcode", os.path.join(home, ".zcode")),
                       ("opencode", os.path.join(home, ".config", "opencode")),
                       ("claude", os.path.join(home, ".claude"))):
        if os.path.isdir(path):
            return name, path
    return "unknown", "-"


def _json_or_none(path):
    try:
        return json.loads(load(path))
    except Exception:
        return None


KEY_FIELDS = ("apiKey", "api_key", "apikey", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY",
              "ZAI_API_KEY", "Z_AI_API_KEY", "ZHIPUAI_API_KEY", "GLM_API_KEY", "token", "key")


def _looks_like_key(s):
    s = (s or "").strip()
    return bool(re.fullmatch(r"[A-Za-z0-9_\-]{20,200}(\.[A-Za-z0-9_\-]{6,64})?", s)) and any(c.isdigit() for c in s)


def _walk_for_key(obj, depth=0):
    """Find an api key in a nested config, only under an explicitly named key field."""
    if depth > 6:
        return None
    if isinstance(obj, dict):
        for k in KEY_FIELDS:
            v = obj.get(k)
            if isinstance(v, str) and _looks_like_key(v):
                return v.strip()
        for k, v in obj.items():
            if isinstance(v, (dict, list)) and re.search(r"z\.?ai|zhipu|bigmodel|anthropic|glm|coding", str(k), re.I):
                r = _walk_for_key(v, depth + 1)
                if r:
                    return r
        for v in obj.values():
            if isinstance(v, (dict, list)):
                r = _walk_for_key(v, depth + 1)
                if r:
                    return r
        return None
    if isinstance(obj, list):
        for v in obj:
            r = _walk_for_key(v, depth + 1)
            if r:
                return r
    return None

def find_credentials():
    """-> (key, base_url, protocol, source) ; key may be None."""
    base = (os.environ.get("PLAN_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
            or os.environ.get("ZAI_BASE_URL") or "").strip().rstrip("/")
    for e in KEY_ENV:
        v = os.environ.get(e, "").strip()
        if v:
            return v, base or DEFAULT_BASE, protocol_for(base or DEFAULT_BASE), "env:" + e
    home = os.path.expanduser("~")
    cands = [os.path.join(home, ".claude", "settings.json"),
             os.path.join(home, ".claude", "settings.local.json"),
             os.path.join(os.getcwd(), ".claude", "settings.local.json"),
             os.path.join(home, ".config", "opencode", "opencode.json"),
             os.path.join(home, ".config", "opencode", "auth.json"),
             os.path.join(os.getcwd(), "opencode.json"),
             os.path.join(home, ".zcode", "settings.json"),
             os.path.join(home, ".zcode", "config.json"),
             os.path.join(home, ".zcode", "auth.json")]
    for p in cands:
        data = _json_or_none(p)
        if not data:
            continue
        env = data.get("env") if isinstance(data, dict) else None
        if isinstance(env, dict):
            b = (env.get("ANTHROPIC_BASE_URL") or base or "").strip().rstrip("/")
            for e in KEY_ENV:
                if env.get(e):
                    return str(env[e]).strip(), b or DEFAULT_BASE, protocol_for(b or DEFAULT_BASE), p
        k = _walk_for_key(data)
        if k:
            b = base or DEFAULT_BASE
            return k, b, protocol_for(b), p
    return None, base or DEFAULT_BASE, protocol_for(base or DEFAULT_BASE), "-"


def protocol_for(base):
    b = (base or "").lower()
    if os.environ.get("PLAN_PROTOCOL"):
        return os.environ["PLAN_PROTOCOL"]
    if "/anthropic" in b:
        return "anthropic"
    if "paas/v4" in b or "/coding" in b or "openai" in b or "/v1" in b:
        return "openai"
    return "anthropic"


def model_for(tier, api=True):
    m, effort, alias = GLM.get(tier, GLM["std"])
    m = os.environ.get("PLAN_MODEL_DEEP" if tier == "deep" else "PLAN_MODEL_STD", m)
    return (m, effort) if api else (alias, effort)


def workers_cap(requested=None):
    v = os.environ.get("PLAN_MAX_WORKERS", "").strip()
    cap = int(v) if v.isdigit() and int(v) > 0 else MAX_WORKERS
    return max(1, min(MAX_WORKERS, requested or cap))


def agent_cap():
    for e in ("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", "OPENCODE_MAX_CONCURRENT_SUBAGENTS",
              "ZCODE_MAX_CONCURRENT_SUBAGENTS"):
        v = os.environ.get(e, "").strip()
        if v.isdigit() and int(v) > 0:
            return min(MAX_WORKERS, int(v)), e
    return DEFAULT_AGENT_CAP, ""


# ------------------------------------------------------------------ http fan-out
class Budget:
    """Shared failure budget so a dead endpoint aborts fast instead of 64x retrying."""
    def __init__(self, limit=8):
        self.lock = threading.Lock()
        self.left = limit
        self.reason = ""

    def blown(self):
        with self.lock:
            return self.left <= 0

    def hit(self, why):
        with self.lock:
            self.left -= 1
            if not self.reason:
                self.reason = why


def _post(url, headers, payload, timeout):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def call_model(cfg, system_blocks, user_text, tier, budget, max_tokens=16000, timeout=900):
    """One completion. Returns (text, error). Retries on 429/5xx with jitter."""
    model, effort = model_for(tier)
    key, base, proto = cfg["key"], cfg["base"], cfg["protocol"]
    last = "unknown"
    for attempt in range(4):
        if budget.blown():
            return "", "aborted: %s" % budget.reason
        try:
            if proto == "anthropic":
                url = base + "/v1/messages"
                head = {"content-type": "application/json", "x-api-key": key,
                        "authorization": "Bearer " + key, "anthropic-version": "2023-06-01"}
                body = {"model": model, "max_tokens": max_tokens,
                        "system": [{"type": "text", "text": system_blocks[0],
                                    "cache_control": {"type": "ephemeral"}}],
                        "messages": [{"role": "user", "content": user_text}]}
                if cfg.get("thinking", True):
                    body["thinking"] = {"type": "enabled", "budget_tokens": EFFORT_BUDGET[effort]}
                r = _post(url, head, body, timeout)
                parts = [b.get("text", "") for b in r.get("content", []) if b.get("type") == "text"]
                out = "".join(parts).strip()
            else:
                url = base + ("/chat/completions" if not base.endswith("/chat/completions") else "")
                head = {"content-type": "application/json", "authorization": "Bearer " + key}
                body = {"model": model, "max_tokens": max_tokens, "reasoning_effort": effort,
                        "messages": [{"role": "system", "content": system_blocks[0]},
                                     {"role": "user", "content": user_text}]}
                r = _post(url, head, body, timeout)
                ch = (r.get("choices") or [{}])[0]
                out = ((ch.get("message") or {}).get("content") or "").strip()
            if out:
                return out, ""
            last = "empty response"
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", "replace")[:300]
            except Exception:
                detail = ""
            last = "HTTP %s %s" % (e.code, detail)
            if e.code == 400 and cfg.get("thinking", True) and re.search(r"thinking|reasoning", detail, re.I):
                cfg["thinking"] = False
                continue
            if e.code in (401, 403, 404):
                budget.hit(last)
                return "", last
            if e.code not in (408, 409, 429, 500, 502, 503, 504, 529):
                budget.hit(last)
                return "", last
        except urllib.error.URLError as e:
            last = "URLError: %s" % str(e.reason)[:160]
            if re.search(r"refused|not known|Name or service|unreachable|certificate", last, re.I):
                budget.hit(last)
                return "", last
        except Exception as e:
            last = "%s: %s" % (type(e).__name__, str(e)[:200])
        time.sleep(min(20, (2 ** attempt) + random.random() * 1.5))
    budget.hit(last)
    return "", last


def pmap(fn, items, workers):
    if not items:
        return []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(items)))) as ex:
        return list(ex.map(fn, items))
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


def scan(text, allow, label, skip_contracts=False):
    errs, inside = [], False
    allow = {a.lower() for a in allow}
    for n, l in enumerate(text.splitlines(), 1):
        if skip_contracts:
            if re.match(r"^##\s+Contracts\b", l):
                inside = True
            elif re.match(r"^##\s", l) or l.strip() in (TASKS_MARK, WAVES_OPEN):
                inside = False
        if inside:
            continue
        for kind, pats in (("placeholder", PH_RE), ("portability", PO_RE)):
            for p in pats:
                for m in p.finditer(l):
                    if m.group(0).lower() not in allow:
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
    heads = [(i + 1, l.strip()) for i, l in enumerate(lines) if re.match(r"^#{1,6}\s", l)]
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
        paths += [norm_path(x) for x in TICK.findall(l) if "/" in x or "." in x]  # skip `Symbol` mentions
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


def lint_body(c, body, allow, label, repo=None, earlier_files=()):
    errs, warns = [], []
    if re.search(r"^#{1,3}\s", body, re.M):
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
            try:
                toks = [t for t in shlex.split(m.group(1)) if not t.startswith("-")]
            except ValueError:
                toks = m.group(1).split()
            bad = [t for t in toks if t in (".", "*", ":/") or "*" in t]
            if bad or re.search(r"(^|\s)(-A|--all|-u)\b", m.group(1)):
                errs.append("%s: `git add %s` - stage explicit paths from Files only" % (label, m.group(1).strip()))
                continue
            for t in toks:
                t = norm_path(t)
                if t in contract:
                    continue
                if any(f.startswith(t.rstrip("/") + "/") for f in contract):
                    warns.append("%s: `git add %s` stages a directory - prefer explicit file paths" % (label, t))
                else:
                    errs.append("%s: `git add` path `%s` is not in the contract Files" % (label, t))
    errs += syntax_errors(blocks, label)
    errs += scan(body, allow, label)
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


def partition(cs, k):
    if len(cs) <= k:
        return [[c] for c in cs]
    w = [2.0 + sum(b - a + 1 for a, b in c["spec"]) / 30.0 + 0.5 * len(c["files"]) + 0.5 * len(c["produces"]) for c in cs]

    def groups(limit):
        out, cur, acc = [], [], 0.0
        for c, x in zip(cs, w):
            if cur and acc + x > limit:
                out.append(cur)
                cur, acc = [], 0.0
            cur.append(c)
            acc += x
        return out + ([cur] if cur else [])

    lo, hi = max(w), sum(w)
    for _ in range(50):
        mid = (lo + hi) / 2
        if len(groups(mid)) <= k:
            hi = mid
        else:
            lo = mid
    out = groups(hi)
    weight = {id(c): x for c, x in zip(cs, w)}
    while len(out) < k:  # use every free slot: split the heaviest multi-task group
        cand = [g for g in out if len(g) > 1]
        if not cand:
            break
        g = max(cand, key=lambda g: sum(weight[id(c)] for c in g))
        i = out.index(g)
        half, acc, total = 1, 0.0, sum(weight[id(c)] for c in g)
        for j, c in enumerate(g[:-1], 1):
            acc += weight[id(c)]
            if acc >= total / 2:
                half = j
                break
        out[i:i + 1] = [g[:half], g[half:]]
    return out


def plan_header(plan):
    lines = plan.splitlines()
    first = next((i for i, l in enumerate(lines) if re.match(r"^##\s", l)), len(lines))
    return "\n".join(l for l in lines[:first] if not l.startswith(">")).strip()


def ref_path(*parts):
    return os.path.join(SKILL_DIR, *parts)


def body_rules():
    try:
        return load(ref_path("references", "body-rules.md")).strip()
    except OSError:
        return "Write the task body: **Files:** list, then numbered `- [ ] **Step N:**` TDD steps with real code, every Run: followed by Expected:, final git commit staging only the contract files."


def shared_prefix(plan, repo):
    """Byte-identical for every writer of one plan -> the cacheable prompt prefix."""
    parts = ["# Task-body writing rules (binding)", "", body_rules(),
             "", "# Plan header", "", plan_header(plan)]
    for title in ("Global Constraints", "References", "File Structure"):
        s = section(plan, title)
        if s:
            parts += ["", "# " + title, "", s]
    ref = section(plan, "References")
    if ref:
        inl, _ = inline_files([norm_path(x) for x in TICK.findall(ref)], repo, budget_lines=900)
        if inl:
            parts += ["", "# Shared reference files (with line numbers)", ""] + inl
    return "\n".join(parts).strip() + "\n"


def task_block(c, spec_path, repo, with_files=True):
    """Per-task part of a brief: contract, wiring, spec excerpt, inlined files."""
    blk = ["# Contract %s (locked - do not change signatures or file list)" % c["id"], "", c["text"], "",
           "- Resolved Depends: %s" % (", ".join(c["deps_all"]) or "none")]
    if c["after"]:
        blk.append("- Runs after (same files): %s - write steps that stay valid after their edits" % ", ".join(c["after"]))
    for s in c["consumes"]:
        blk.append("- Consumes `%s` - call it exactly like this" % s)
    for t, s in c["consumers"]:
        blk.append("- %s will call your `%s` - make it complete and exact" % (t, s))
    parts = ["\n".join(blk)]
    if spec_path and c["spec"]:
        ex = [numbered(spec_path, a, b) or "" for a, b in merge_ranges(c["spec"])]
        parts.append("# Spec excerpt for %s\n\n````text\n%s\n````" % (c["id"], "\n  ...\n".join(ex)))
    if with_files:
        inl, refs = inline_files(list(c["files"]) + list(c["reads"]), repo, budget_lines=1200)
        if inl:
            parts.append("# Existing files for %s (line numbers are real - use them for Modify ranges)\n\n%s"
                         % (c["id"], "\n\n".join(inl)))
        if refs:
            parts.append("# Not inlined (too large) - assume nothing about their contents\n\n"
                         + "\n".join("- `%s`" % r for r in refs))
    return "\n\n".join(parts)


API_WRITER_TAIL = """# Your output

Write the body of task {ID} now.

1. Output the body and nothing else: no greeting, no explanation, no summary, no
   fenced wrapper around the whole answer.
2. Start with the line `**Files:**`. End with the final commit step.
3. Between these exact markers:

<<<BODY {ID}>>>
...body...
<<<END {ID}>>>
"""

API_REPAIR = """The body you wrote for {ID} failed the deterministic linter.

{ERRORS}

Rewrite the COMPLETE corrected body of {ID}. Same markers, same rules. Change
only what the errors require; keep everything that was already correct.

<<<BODY {ID}>>>
...body...
<<<END {ID}>>>
"""

API_REVIEW_TAIL = """# Your job

Below is the current body of {ID}. The deterministic linter already enforces
structure, placeholders, portability, file ownership, signatures, Run/Expected,
git-add scope and code-block syntax. Judge only what a script cannot see:

1. Spec alignment - a requirement in the excerpt is missing or contradicted.
2. Correctness - the test would not fail first or pass after; wrong command or
   expected output; code that cannot run (bad import, wrong API, missing fixture).
3. Buildability - an engineer following the steps literally gets stuck or builds
   the wrong thing.
4. Contract use - a consumed signature is called differently from its contract.

Ignore wording and style. If nothing would break implementation, reply with the
single line `APPROVED` and nothing else. Otherwise output the complete corrected
body between the markers (contract signatures and the Files list unchanged).

# Current body of {ID}

{BODY}

<<<BODY {ID}>>>
...corrected body...
<<<END {ID}>>>
"""


FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def extract_body(text, tid):
    """Pull the task body out of a model reply: markers first, then tolerant fallbacks."""
    m = re.search(r"<<<BODY\s+%s>>>\s*\n(.*?)\n?<<<END\s+%s>>>" % (tid, tid), text, re.S)
    body = (m.group(1) if m else text).strip()
    lines = body.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    # a whole-answer wrapper fence: first line opens it, last non-empty line closes it
    if lines and FENCE_RE.match(lines[0]):
        j = len(lines) - 1
        while j > 0 and not lines[j].strip():
            j -= 1
        if j > 0 and FENCE_RE.match(lines[j]):
            lines = lines[1:j]
    body = "\n".join(lines)
    i = body.find("**Files:**")
    if i > 0:
        body = body[i:]
    return body.strip() + "\n"


def writer_brief(plan_path, plan, cs_group, cmap, work, spec_path, repo, allow):
    """Agent-lane brief file: invariant prefix first (cache), then the assignment."""
    ids = [c["id"] for c in cs_group]
    outs = {c["id"]: os.path.join(work, "tasks", c["id"] + ".md") for c in cs_group}
    lint = "; ".join("%s lint-task %s %s" % (qtool(), shlex.quote(plan_path), shlex.quote(outs[t])) for t in ids)
    try:
        tmpl = load(ref_path("task-writer-prompt.md"))
    except OSError:
        tmpl = "# Writer brief: {TASKS}\n\nWrite each OUT file, then run LINT.\n\nOUT:\n{OUT}\n\nLINT: `{LINT}`\n"
    head = tmpl.replace("{TASKS}", ", ".join(ids)).replace("{LINT}", lint) \
               .replace("{OUT}", "\n".join("- %s -> `%s`" % (t, outs[t]) for t in ids))
    parts = [shared_prefix(plan, repo), head] + [task_block(c, spec_path, repo) for c in cs_group]
    return "\n\n".join(parts) + "\n"


def reviewer_brief(plan_path, plan, cs_group, work, spec_path, repo):
    try:
        tmpl = load(ref_path("plan-reviewer-prompt.md"))
    except OSError:
        tmpl = "# Reviewer brief: {TASKS}\n\nFiles:\n{FILES}\n\nLINT: `{LINT}`\n"
    files = [os.path.join(work, "tasks", c["id"] + ".md") for c in cs_group]
    lint = "; ".join("%s lint-task %s %s --mark rev" % (qtool(), shlex.quote(plan_path), shlex.quote(f)) for f in files)
    parts = [tmpl.replace("{TASKS}", ", ".join(c["id"] for c in cs_group)).replace("{LINT}", lint)
             .replace("{FILES}", "\n".join("- `%s`" % f for f in files))]
    gc = section(plan, "Global Constraints")
    if gc:
        parts.append("# Global Constraints\n\n" + gc)
    parts += [task_block(c, spec_path, repo, with_files=False) for c in cs_group]
    return "\n\n".join(parts) + "\n"


def dispatch_lines(groups, work, kind):
    rows = []
    for gid, g in groups:
        tier = max((c["tier"] for c in g), key=lambda t: TIER_RANK[t])
        alias = model_for("deep" if kind == "review" else tier, api=False)[0]
        span = g[0]["id"] if len(g) == 1 else "%s-%s" % (g[0]["id"], g[-1]["id"])
        sub = "review-briefs" if kind == "review" else "briefs"
        rows.append("%-4s %-7s %-9s %s" % (gid, alias, span, os.path.join(work, sub, gid + ".md")))
    return rows


def agent_installed(repo):
    home = os.path.expanduser("~")
    for base in (os.path.join(repo, ".opencode", "agents"), os.path.join(home, ".config", "opencode", "agents"),
                 os.path.join(home, ".zcode", "agents"),
                 os.path.join(repo, ".claude", "agents"), os.path.join(home, ".claude", "agents")):
        if os.path.isfile(os.path.join(base, "plan-task-writer.md")):
            return base
    return None


# ------------------------------------------------------------------ shared prep
def prepare(plan_path, spec, allow):
    plan = load(plan_path)
    cs, errs = parse_contracts(plan)
    if cs is None:
        return plan, None, None, errs, []
    repo = repo_root(plan_path)
    e2, warns = analyze(cs, spec, repo)
    errs += e2 + scan(plan.split(TASKS_MARK, 1)[0], allow, os.path.basename(plan_path), skip_contracts=True)
    return plan, cs, repo, errs, warns


def task_path(work, tid):
    return os.path.join(work, "tasks", tid + ".md")


def lint_one(cs, c, body, allow, repo):
    earlier = {f for x in cs if num(x["id"]) < num(c["id"]) for f in x["files"]}
    return lint_body(c, strip_generated(body), allow, c["id"], repo, earlier)


# ------------------------------------------------------------------ build (API lane)
def cmd_build(a):
    t0 = time.time()
    plan_path = os.path.abspath(a.plan)
    spec = os.path.abspath(a.spec) if a.spec else None
    plan, cs, repo, errs, warns = prepare(plan_path, spec, a.allow)
    if errs:
        return report(errs, warns, "")
    work = default_work(plan_path)
    os.makedirs(os.path.join(work, "tasks"), exist_ok=True)
    save(os.path.join(work, "work.json"), json.dumps({
        "plan": plan_path, "spec": spec, "repo": repo, "allow": a.allow,
        "tasks": [c["id"] for c in cs], "review": []}, indent=1))

    key, base, proto, src = find_credentials()
    if a.lane == "agent" or (a.lane == "auto" and not key):
        return build_agent_lane(a, plan_path, plan, cs, repo, work, spec, warns, key, src)
    if not key:
        return report(["no API key found (checked %s and harness config files); "
                       "run `%s doctor`, or use --lane agent" % (", ".join(KEY_ENV), qtool())], warns, "")

    cfg = {"key": key, "base": base, "protocol": proto, "thinking": not a.no_thinking}
    workers = workers_cap(a.workers)
    prefix = shared_prefix(plan, repo)
    budget = Budget(limit=max(4, workers // 4))
    allow = list(a.allow)
    todo = [c for c in cs if not (a.resume and os.path.exists(task_path(work, c["id"]) + ".ok"))]
    print("LANE api | %s | %s | key %s | %d writers | %d/%d tasks"
          % (proto, base, src, min(workers, len(todo) or 1), len(todo), len(cs)))
    sys.stdout.flush()

    results = {}

    def write_one(c):
        tid = c["id"]
        user = task_block(c, spec, repo) + "\n\n" + API_WRITER_TAIL.replace("{ID}", tid)
        text, err = call_model(cfg, [prefix], user, c["tier"], budget, max_tokens=a.max_tokens)
        if err:
            return (tid, "FAIL", err, 0)
        body = extract_body(text, tid)
        rounds = 0
        while True:
            e, w = lint_one(cs, c, body, allow, repo)
            if not e or rounds >= a.repairs or budget.blown():
                break
            rounds += 1
            fix = API_REPAIR.replace("{ID}", tid).replace("{ERRORS}", "\n".join("- " + x for x in e[:20]))
            text2, err2 = call_model(cfg, [prefix], user + "\n\n---\n\n" + body + "\n\n---\n\n" + fix,
                                     c["tier"], budget, max_tokens=a.max_tokens)
            if err2:
                break
            body = extract_body(text2, tid)
        save(task_path(work, tid), body)
        if not e:
            touch(task_path(work, tid) + ".ok")
            if w:
                save(task_path(work, tid) + ".warn", "\n".join(w))
        return (tid, "OK" if not e else "LINT", "; ".join(e[:2]), rounds)

    for tid, st, msg, rounds in pmap(write_one, todo, workers):
        results[tid] = (st, msg, rounds)
    bad = [t for t, (st, _, _) in results.items() if st != "OK"]
    fixed = sum(1 for _, (_, _, r) in results.items() if r)
    print("WRITE %d ok, %d repaired, %d failing (%.0fs)"
          % (len(results) - len(bad), fixed, len(bad), time.time() - t0))
    for t in sorted(bad):
        print("  %s %s: %s" % (results[t][0], t, results[t][1][:180]))
    if bad:
        print("Re-run `%s build %s --spec %s --resume` to retry only these, or fix them with an editor and run assemble."
              % (qtool(), shlex.quote(plan_path), shlex.quote(spec or "")))
        return 1

    if not a.no_review:
        nrev = run_review(a, cfg, cs, plan, repo, work, spec, allow, budget, workers, prefix)
        print("REVIEW %d task(s) judged (%.0fs total)" % (nrev, time.time() - t0))

    ns = argparse.Namespace(plan=plan_path, spec=spec, clean=not a.keep_work, allow=allow)
    rc = cmd_assemble(ns)
    if rc == 0:
        print("TIME %.0fs total" % (time.time() - t0))
    return rc


def pick_risky(cs, work, everything=False):
    picked = []
    for c in cs:
        p = task_path(work, c["id"])
        if not os.path.exists(p):
            continue
        body = load(p)
        why = []
        if everything:
            why.append("all")
        if c["tier"] == "deep":
            why.append("deep")
        if len(body.splitlines()) > 250:
            why.append("long")
        if len(c["consumes"]) >= 3:
            why.append("consumes%d" % len(c["consumes"]))
        if c["consumers"]:
            why.append("producer")
        if os.path.exists(p + ".warn"):
            why.append("warn")
        if why:
            picked.append((c, why))
    return picked


def run_review(a, cfg, cs, plan, repo, work, spec, allow, budget, workers, prefix):
    picked = pick_risky(cs, work, a.thorough)
    if not picked:
        return 0

    def review_one(item):
        c, _ = item
        tid = c["id"]
        p = task_path(work, tid)
        body = load(p)
        user = (task_block(c, spec, repo, with_files=False) + "\n\n"
                + API_REVIEW_TAIL.replace("{ID}", tid).replace("{BODY}", body))
        text, err = call_model(cfg, [prefix], user, "deep", budget, max_tokens=a.max_tokens)
        if err or text.strip().upper().startswith("APPROVED"):
            return 0
        new = extract_body(text, tid)
        if len(new.strip()) < 80:
            return 0
        e_new, _ = lint_one(cs, c, new, allow, repo)
        e_old, _ = lint_one(cs, c, body, allow, repo)
        if len(e_new) <= len(e_old):
            save(p, new)
            touch(p + ".ok")
            return 1
        return 0

    changed = sum(pmap(review_one, picked, workers))
    print("REVIEW %d risky, %d rewritten" % (len(picked), changed))
    return len(picked)


def build_agent_lane(a, plan_path, plan, cs, repo, work, spec, warns, key, src):
    cap, capenv = agent_cap()
    k = max(1, min(MAX_WORKERS, a.workers or cap))
    shutil.rmtree(os.path.join(work, "briefs"), ignore_errors=True)
    cmap = {c["id"]: c for c in cs}
    parts = partition(cs, k)
    groups = [((g[0]["id"] if len(parts) == len(cs) else "W%02d" % (i + 1)), g) for i, g in enumerate(parts)]
    for gid, g in groups:
        save(os.path.join(work, "briefs", gid + ".md"),
             writer_brief(plan_path, plan, g, cmap, work, spec, repo, a.allow))
    info = json.loads(load(os.path.join(work, "work.json")))
    info["groups"] = {gid: [c["id"] for c in g] for gid, g in groups}
    info["agents"] = k
    save(os.path.join(work, "work.json"), json.dumps(info, indent=1))
    _, n, width = waves_block(cs)
    agent = "plan-task-writer" if agent_installed(repo) else "general-purpose"
    head = ["LANE agent (no API key found - script-side fan-out unavailable)" if not key
            else "LANE agent (forced)",
            "WORK %s" % work,
            "DISPATCH %d writers, ALL in ONE message | subagent_type=%s | description 'plan <ID>'" % (len(groups), agent),
            "prompt (verbatim): Read <brief path> and follow it exactly.",
            "ID   MODEL   TASKS     BRIEF"]
    tail = ["THEN: %s wait %s" % (qtool(), shlex.quote(plan_path)),
            "THEN: %s review %s" % (qtool(), shlex.quote(plan_path)),
            "THEN: %s assemble %s --clean" % (qtool(), shlex.quote(plan_path))]
    if not capenv:
        tail.append("NOTE subagent cap assumed %d; `%s setup --apply` raises it where the harness supports it" % (cap, qtool()))
    return report([], warns, "OK contracts: %d tasks | %d waves | max wave width %d | %d writers"
                  % (len(cs), n, width, len(groups)), head + dispatch_lines(groups, work, "write") + tail)




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


def cmd_lint_task(a):
    e, w, c = lint_file(os.path.abspath(a.plan), a.task, a.allow)
    rc = report(e, w, "OK %s" % (c["id"] if c else ""))
    if rc == 0:
        touch(a.task + "." + a.mark)
        if w:
            with open(a.task + ".warn", "w") as f:
                f.write("\n".join(w))
    return rc


def cmd_hook_lint(a):
    try:
        data = json.load(sys.stdin)
        path = (data.get("tool_input") or {}).get("file_path") or ""
        m = re.search(r"[\\/]\.work[\\/][^\\/]+[\\/]tasks[\\/]T\d{2,3}\.md$", path)
        if not m:
            return 0
        work = os.path.dirname(os.path.dirname(path))
        info = json.loads(load(os.path.join(work, "work.json")))
        e, w, c = lint_file(info["plan"], path)
        if not e:
            touch(path + ".ok")
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


def cmd_wait(a):
    plan_path = os.path.abspath(a.plan)
    work, info = load_work(plan_path)
    if not info:
        return report(["no work.json - run contracts first"], [], "")
    ids = info.get("review", []) if a.review else info.get("tasks", [])
    mark = "rev" if a.review else "ok"
    t0 = last = time.time()
    seen = -1
    while True:
        st = {t: done_state(os.path.join(work, "tasks", t + ".md"), mark) for t in ids}
        ndone = sum(1 for v in st.values() if v == "done")
        if ndone != seen:
            seen, last = ndone, time.time()
        if ndone == len(ids):
            print("DONE %d/%d %s in %.0fs" % (ndone, len(ids), "reviews" if a.review else "tasks", time.time() - t0))
            return 0
        if time.time() - t0 > a.timeout or time.time() - last > a.idle:
            pend = ["%s:%s" % (t, v) for t, v in st.items() if v != "done"]
            print("PENDING %d/%d after %.0fs (%s) -> %s" % (ndone, len(ids), time.time() - t0,
                  "timeout" if time.time() - t0 > a.timeout else "no progress for %ds" % a.idle, " ".join(pend)))
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
    picked = []
    for c in cs:
        body = tasks.get(c["id"], "")
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
        if why and body:
            picked.append((c, why))
    shutil.rmtree(os.path.join(work, "review-briefs"), ignore_errors=True)
    if not picked:
        info["review"] = []
        save(os.path.join(work, "work.json"), json.dumps(info, indent=1))
        print("NONE - no risky tasks; skip review and run assemble")
        return 0
    k = max(1, min(MAX_WORKERS, a.agents or info.get("agents") or DEFAULT_AGENT_CAP))
    size = a.size or max(1, -(-len(picked) // k))  # default: spread over every free slot
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
    for c in cs:
        if c["id"] not in bodies:
            errs.append("%s: task body missing" % c["id"])
            continue
        earlier = {f for x in cs if num(x["id"]) < num(c["id"]) for f in x["files"]}
        e, w = lint_body(c, bodies[c["id"]], allow, c["id"], repo, earlier)
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
    if a.clean:
        shutil.rmtree(work, ignore_errors=True)
        parent = os.path.dirname(work)
        if os.path.isdir(parent) and not os.listdir(parent):
            os.rmdir(parent)
    return report([], warns, "OK assembled %d tasks -> %s | %d waves | max wave width %d%s"
                  % (len(cs), plan_path, n, width, " | workdir removed" if a.clean else ""))


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



# ------------------------------------------------------------------ contracts (validate / agent lane)
def cmd_contracts(a):
    plan_path = os.path.abspath(a.plan)
    spec = os.path.abspath(a.spec) if a.spec else None
    plan, cs, repo, errs, warns = prepare(plan_path, spec, a.allow)
    if errs:
        return report(errs, warns, "")
    work = default_work(plan_path)
    os.makedirs(os.path.join(work, "tasks"), exist_ok=True)
    save(os.path.join(work, "work.json"), json.dumps({
        "plan": plan_path, "spec": spec, "repo": repo, "allow": a.allow,
        "tasks": [c["id"] for c in cs], "review": []}, indent=1))
    key, _, _, _ = find_credentials()
    ns = argparse.Namespace(workers=a.workers, allow=a.allow)
    return build_agent_lane(ns, plan_path, plan, cs, repo, work, spec, warns, key, "")


# ------------------------------------------------------------------ brief (replaces Phase 0)
STACK_MARKS = {"pyproject.toml": "python", "setup.py": "python", "requirements.txt": "python",
    "package.json": "node", "go.mod": "go", "Cargo.toml": "rust", "pom.xml": "java/maven",
    "build.gradle": "java/gradle", "build.gradle.kts": "kotlin/gradle", "Gemfile": "ruby",
    "composer.json": "php", "mix.exs": "elixir", "CMakeLists.txt": "c/c++", "Makefile": "make",
    "deno.json": "deno", "pubspec.yaml": "dart"}
SKIP_RE = re.compile(r"(^|/)(node_modules|vendor|dist|build|\.venv|venv|__pycache__|target|\.next|\.git)/"
                     r"|\.(lock|min\.js|map|png|jpg|jpeg|gif|svg|ico|pdf|woff2?|ttf|zip|gz)$")
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|(_test|\.test|\.spec|test_)[^/]*$")


DOC_EXT = re.compile(r"\.(md|markdown|rst|txt|adoc|csv|json|ya?ml|lock)$", re.I)


def pick_patterns(files, repo, spec_text, limit=4, exclude=()):
    """Rank existing CODE files as pattern exemplars for the spec."""
    toks = {w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", spec_text or "")}
    skip = {norm_path(x) for x in exclude}
    recent = []
    for l in sh(["git", "log", "-n", "40", "--name-only", "--pretty=format:"], repo).splitlines():
        if l.strip() and l not in recent:
            recent.append(l)
    rank = {f: i for i, f in enumerate(recent)}
    scored = []
    for f in files:
        if SKIP_RE.search(f) or norm_path(f) in skip or not os.path.isfile(os.path.join(repo, f)):
            continue
        if DOC_EXT.search(f) or f.startswith("docs/"):
            continue
        base = os.path.basename(f).lower()
        s = 0.0
        s += 3.0 if TEST_RE.search(f) else 0.0
        if f in rank:
            s += 2.5 * (1.0 - rank[f] / max(1, len(recent)))
        hits = sum(1 for t in toks if t in base or t in f.lower())
        s += min(4.0, 1.2 * hits)
        try:
            n = len(load(os.path.join(repo, f)).splitlines())
        except Exception:
            continue
        if n < 5 or n > 400:
            s -= 2.0
        if s > 1.5:
            scored.append((s, f))
    scored.sort(reverse=True)
    out, seen_test = [], False
    for _, f in scored:
        istest = bool(TEST_RE.search(f))
        if istest and seen_test and len(out) >= 2:
            continue
        seen_test = seen_test or istest
        out.append(f)
        if len(out) >= limit:
            break
    return out


def cmd_brief(a):
    out = []
    try:
        cwd = os.getcwd()
        repo = repo_root(cwd)
        harness, hev = detect_harness()
        key, base, proto, src = find_credentials()
        args = a.rest or []
        spec = next((x for x in args if not x.startswith("--") and os.path.isfile(x)), None)
        spec_abs = os.path.abspath(spec) if spec else None
        out.append("date %s | cwd %s | repo %s" % (time.strftime("%Y-%m-%d"), cwd, repo))
        out.append("TOOL: %s" % qtool())
        out.append("harness: %s (%s)" % (harness, hev))
        if key:
            out.append("lane: api | %s | %s | key %s | writers %d (script-side, no subagents)"
                       % (proto, base, src, workers_cap()))
        else:
            cap, capenv = agent_cap()
            out.append("lane: agent | no API key (checked %s) | subagent cap %s -> run `%s doctor`"
                       % (KEY_ENV[0] + "..", "%d%s" % (cap, "" if capenv else " assumed"), qtool()))
        out.append("models: light/std=%s(effort low/high) deep=%s(effort max)" % (GLM["std"][0], GLM["deep"][0]))
        if "--thorough" in args:
            out.append("mode: THOROUGH -> review every task")
        branch = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo).strip()
        files = sh(["git", "ls-files"], repo).splitlines()
        if not files:
            for root, dirs, fs in os.walk(repo):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                           ("node_modules", "venv", ".venv", "dist", "build", "__pycache__", "target")]
                files += [os.path.relpath(os.path.join(root, f), repo) for f in fs]
                if len(files) > 20000:
                    break
        dirty = len(sh(["git", "status", "--porcelain"], repo).splitlines())
        out.append("git: branch %s | %d dirty | %d files" % (branch or "-", dirty, len(files)))
        plans = os.path.join(repo, "docs", "superpowers", "plans")
        out.append("plan path: docs/superpowers/plans/%s-<feature>.md (%d existing)" % (
            time.strftime("%Y-%m-%d"),
            len([f for f in os.listdir(plans) if f.endswith(".md")]) if os.path.isdir(plans) else 0))
        found = [f for f in STACK_MARKS if os.path.isfile(os.path.join(repo, f))]
        out.append("stack: %s | markers: %s" % (", ".join(sorted({STACK_MARKS[f] for f in found})) or "?",
                                                ", ".join(found) or "-"))
        tests = []
        pj = os.path.join(repo, "package.json")
        if os.path.isfile(pj):
            try:
                scr = json.loads(load(pj)).get("scripts", {})
                tests += ["npm run %s -> %s" % (k, v) for k, v in scr.items()
                          if re.search(r"test|lint|check|typecheck", k)][:6]
            except ValueError:
                pass
        pp = os.path.join(repo, "pyproject.toml")
        if os.path.isfile(pp) and "pytest" in load(pp):
            tests.append("pytest (pyproject.toml)")
        if any(STACK_MARKS[f] == "go" for f in found):
            tests.append("go test ./...")
        if any(STACK_MARKS[f] == "rust" for f in found):
            tests.append("cargo test")
        if tests:
            out.append("test/check cmds: " + " ; ".join(tests))
        conv = []
        for md in ("AGENTS.md", "CLAUDE.md", ".opencode/AGENTS.md", ".zcode/AGENTS.md", ".claude/CLAUDE.md"):
            p = os.path.join(repo, md)
            if os.path.isfile(p):
                conv.append(md)
                out.append("conventions %s (%d lines) - copy binding rules into Global Constraints:" % (md, len(load(p).splitlines())))
                out.append("  " + "\n  ".join(load(p).splitlines()[:60]))
        if not conv:
            out.append("conventions file: none")
        dirs = {}
        for f in files:
            d = f.split("/", 1)[0] if "/" in f else "."
            dirs[d] = dirs.get(d, 0) + 1
        out.append("top-level: " + ", ".join("%s(%d)" % (d, n) for d, n in sorted(dirs.items(), key=lambda x: -x[1])[:25]))
        shown = [f for f in files if not SKIP_RE.search(f)]
        out.append("files (%d of %d):" % (min(250, len(shown)), len(files)))
        out.append("  " + "\n  ".join(shown[:250]))
        spec_text = ""
        if spec_abs:
            sl = load(spec_abs).splitlines()
            spec_text = "\n".join(sl)
            rel = os.path.relpath(spec_abs, repo)
            heads = [(i + 1, l.strip()) for i, l in enumerate(sl) if re.match(r"^#{1,6}\s", l)]
            out.append("")
            out.append("=== SPEC %s (%d lines) - heading map for `Spec: L<a>-L<b>` ===" % (rel, len(sl)))
            for j, (ln, h) in enumerate(heads[:100]):
                end = heads[j + 1][0] - 1 if j + 1 < len(heads) else len(sl)
                out.append("  L%d-%d %s" % (ln, end, h[:90]))
            cut = a.spec_lines
            out.append("")
            out.append("=== SPEC BODY (numbered; do NOT re-read this file) ===")
            out.append(numbered(spec_abs, 1, min(cut, len(sl))) or "")
            if len(sl) > cut:
                out.append("  ... %d more lines - read `%s` from L%d if a contract needs them" % (len(sl) - cut, rel, cut + 1))
        ex = [os.path.relpath(spec_abs, repo)] if spec_abs else []
        pats = pick_patterns(shown, repo, spec_text, a.patterns, ex)
        if pats:
            inl, refs = inline_files(pats, repo, budget_lines=a.pattern_lines, per_file=300)
            out.append("")
            out.append("=== PATTERN FILES (auto-selected; imports, test framework, naming) ===")
            out += inl or ["  (all candidates too large: %s)" % ", ".join(refs)]
            if inl and refs:
                out.append("  not inlined: " + ", ".join(refs))
        out.append("")
        out.append("NEXT: write the Contracts file, then run: %s build <plan> --spec %s"
                   % (qtool(), shlex.quote(spec or "<spec>")))
    except Exception as ex:
        out.append("brief partial: %s: %s" % (type(ex).__name__, ex))
    print("\n".join(out))
    return 0


# ------------------------------------------------------------------ doctor
def mask(k):
    return (k[:6] + "..." + k[-4:]) if k and len(k) > 14 else ("set" if k else "-")


def cmd_doctor(a):
    harness, hev = detect_harness()
    key, base, proto, src = find_credentials()
    cap, capenv = agent_cap()
    print("harness   : %s (%s)" % (harness, hev))
    print("python    : %s" % sys.version.split()[0])
    print("tool      : %s" % qtool())
    print("api key   : %s (%s)" % (mask(key), src))
    print("base url  : %s" % base)
    print("protocol  : %s" % proto)
    print("models    : light=%s/low  std=%s/high  deep=%s/max" % (GLM["light"][0], GLM["std"][0], GLM["deep"][0]))
    print("workers   : %d (script-side threads; PLAN_MAX_WORKERS to change)" % workers_cap())
    print("agent cap : %d%s" % (cap, " (%s)" % capenv if capenv else " assumed - agent lane only"))
    print("lane      : %s" % ("api - one tool call fans out %d writers" % workers_cap() if key
                              else "agent - no key; falls back to subagent dispatch"))
    if not key:
        print("")
        print("To enable the api lane, export one of: %s" % ", ".join(KEY_ENV[:5]))
        print("  export ZAI_API_KEY=<your GLM Coding Plan key>")
        print("  export ANTHROPIC_BASE_URL=%s   # optional, this is the default" % DEFAULT_BASE)
        return 1
    if not a.ping:
        print("\nRun with --ping to send a 1-token probe to the endpoint.")
        return 0
    cfg = {"key": key, "base": base, "protocol": proto, "thinking": False}
    t0 = time.time()
    txt, err = call_model(cfg, ["You reply with one word."], "Reply with the single word: ready",
                          "light", Budget(limit=1), max_tokens=64, timeout=90)
    if err:
        print("ping      : FAIL %s" % err)
        return 1
    print("ping      : OK %.1fs -> %r" % (time.time() - t0, txt[:40]))
    return 0


# ------------------------------------------------------------------ setup
AGENT_BODY = """You write implementation-plan task bodies. Read the brief file named in your
task message and follow it exactly. Rules: no repository exploration, no extra
file reads beyond those the brief names, minimal turns, and reply with one line
per task (`T07 OK` or `T07 FAIL: <first error>`). Never echo the body.
"""


def agent_file(harness):
    if harness == "opencode":
        fm = ("---\n"
              "description: Writes implementation-plan task bodies from a writing-plans brief file. "
              "Use only when given a writing-plans brief path.\n"
              "mode: subagent\n"
              "model: zai-coding-plan/glm-5.3-flash\n"
              "temperature: 0.3\n"
              "top_p: 0.95\n"
              "steps: 16\n"
              "permission:\n"
              "  read: allow\n"
              "  edit: allow\n"
              "  bash: allow\n"
              "  task: deny\n"
              "  webfetch: deny\n"
              "---\n\n")
        return fm + AGENT_BODY
    if harness == "zcode":
        fm = ("---\n"
              "name: plan-task-writer\n"
              "description: Writes implementation-plan task bodies from a writing-plans brief file. "
              "Use only when given a writing-plans brief path.\n"
              "model: glm-5.3-flash\n"
              "thinking: low\n"
              "tools: Read, Write, Edit, Bash\n"
              "---\n\n")
        return fm + AGENT_BODY
    fm = ("---\n"
          "name: plan-task-writer\n"
          "description: Writes implementation-plan task bodies from a writing-plans brief file. "
          "Use only when given a writing-plans brief path.\n"
          "tools: Read, Write, Edit, Bash\n"
          "model: haiku\n"
          "maxTurns: 16\n"
          "omitClaudeMd: true\n"
          "hooks:\n"
          "  PostToolUse:\n"
          "    - matcher: \"Write|Edit\"\n"
          "      hooks:\n"
          "        - type: command\n"
          "          command: \"%s hook-lint\"\n"
          "---\n\n") % qtool()
    return fm + AGENT_BODY


def cmd_setup(a):
    home = os.path.expanduser("~")
    harness = a.harness if a.harness != "auto" else detect_harness()[0]
    if harness == "unknown":
        harness = "opencode"
    paths = {"opencode": os.path.join(home, ".config", "opencode", "agents", "plan-task-writer.md"),
             "zcode": os.path.join(home, ".zcode", "agents", "plan-task-writer.md"),
             "claude": os.path.join(home, ".claude", "agents", "plan-task-writer.md")}
    agent_path = paths[harness]
    text = agent_file(harness)
    changes = []
    if not os.path.exists(agent_path) or load(agent_path) != text:
        changes.append("write subagent %s" % agent_path)
    settings = os.path.join(home, ".claude", "settings.json")
    new = None
    if harness == "claude":
        try:
            cur = json.loads(load(settings)) if os.path.exists(settings) else {}
        except ValueError as e:
            print("ERR  %s is not valid JSON (%s); nothing changed" % (settings, e))
            return 1
        new = json.loads(json.dumps(cur))
        env = new.setdefault("env", {})
        for k, v in (("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", "64"),
                     ("CLAUDE_CODE_WORKFLOW_MAX_CONCURRENT_AGENTS", "64"),
                     ("CLAUDE_CODE_AUTO_COMPACT_WINDOW", "1000000"),
                     ("API_TIMEOUT_MS", "3000000")):
            if str(env.get(k, "")) != v:
                env[k] = v
                changes.append("env.%s = %s" % (k, v))
        allow = new.setdefault("permissions", {}).setdefault("allow", [])
        for rule in ("Bash(%s *)" % qtool(), "Edit(**/docs/superpowers/plans/**)"):
            if rule not in allow:
                allow.append(rule)
                changes.append("permissions.allow += %s" % rule)
    key, base, proto, src = find_credentials()
    print("harness: %s | api key: %s (%s)" % (harness, mask(key), src))
    if not changes:
        print("OK setup already complete")
    else:
        print(("APPLY" if a.apply else "DRY-RUN") + ":")
        for c in changes:
            print("  - " + c)
    if changes and a.apply:
        if new is not None:
            if os.path.exists(settings):
                shutil.copy2(settings, settings + ".bak")
            save(settings, json.dumps(new, indent=2) + "\n")
        save(agent_path, text)
        print("OK written")
    elif changes:
        print("Re-run with --apply to write them.")
    print("")
    print("Fastest lane (recommended) - script-side fan-out, no subagents:")
    print("  export ZAI_API_KEY=<GLM Coding Plan key>")
    print("  export ANTHROPIC_BASE_URL=%s" % DEFAULT_BASE)
    if harness == "opencode":
        print("Agent-lane fallback on OpenCode dispatches subagents one at a time;")
        print("  export OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true   # lets them overlap")
    if harness == "zcode":
        print("ZCode runs foreground subagents in parallel; the agent lane works without extra flags.")
    print("Verify with: %s doctor --ping" % qtool())
    return 0


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.required = True

    def common(p):
        p.add_argument("--allow", action="append", default=[], help="exempt a scan hit, e.g. TODO")
        return p

    p = sub.add_parser("brief")
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.add_argument("--spec-lines", type=int, default=900)
    p.add_argument("--patterns", type=int, default=4)
    p.add_argument("--pattern-lines", type=int, default=700)
    p.set_defaults(fn=cmd_brief)

    p = common(sub.add_parser("build"))
    p.add_argument("plan"); p.add_argument("--spec")
    p.add_argument("--lane", choices=["auto", "api", "agent"], default="auto")
    p.add_argument("--workers", type=int)
    p.add_argument("--repairs", type=int, default=2)
    p.add_argument("--max-tokens", type=int, default=16000)
    p.add_argument("--thorough", action="store_true", help="review every task, not only risky ones")
    p.add_argument("--no-review", action="store_true")
    p.add_argument("--no-thinking", action="store_true", help="omit the thinking/effort field")
    p.add_argument("--resume", action="store_true", help="skip tasks that already lint OK")
    p.add_argument("--keep-work", action="store_true")
    p.set_defaults(fn=cmd_build)

    p = common(sub.add_parser("contracts"))
    p.add_argument("plan"); p.add_argument("--spec"); p.add_argument("--workers", type=int)
    p.set_defaults(fn=cmd_contracts)

    p = common(sub.add_parser("lint-task"))
    p.add_argument("plan"); p.add_argument("task")
    p.add_argument("--mark", default="ok", choices=["ok", "rev"]); p.set_defaults(fn=cmd_lint_task)

    p = sub.add_parser("hook-lint"); p.set_defaults(fn=cmd_hook_lint)

    p = sub.add_parser("wait"); p.add_argument("plan"); p.add_argument("--review", action="store_true")
    p.add_argument("--timeout", type=int, default=900); p.add_argument("--idle", type=int, default=300)
    p.set_defaults(fn=cmd_wait)

    p = sub.add_parser("review"); p.add_argument("plan"); p.add_argument("--all", action="store_true")
    p.add_argument("--size", type=int); p.add_argument("--agents", type=int); p.set_defaults(fn=cmd_review)

    p = common(sub.add_parser("assemble")); p.add_argument("plan"); p.add_argument("--spec")
    p.add_argument("--clean", action="store_true"); p.set_defaults(fn=cmd_assemble)

    p = common(sub.add_parser("check")); p.add_argument("plan"); p.add_argument("--spec")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("doctor"); p.add_argument("--ping", action="store_true"); p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("setup")
    p.add_argument("--harness", choices=["auto", "opencode", "zcode", "claude"], default="auto")
    p.add_argument("--apply", action="store_true"); p.set_defaults(fn=cmd_setup)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except KeyboardInterrupt:
        print("ERR  interrupted")
        return 1
    except OSError as e:
        print("ERR  %s" % e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
