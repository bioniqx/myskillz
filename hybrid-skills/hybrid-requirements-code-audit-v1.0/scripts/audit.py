#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit.py — deterministic plumbing for the `requirements-code-audit` skill.

The lead model spends its tokens on judgment only. Everything mechanical lives here:

  init          create .hybrid-audit/, build the repo map, detect the environment, arm the guard hooks
  spec          add / list requirement files (the only source of truth)
  parse-plan    split a large spec into sections for parallel parser agents
  parse-merge   merge parser output into a checklist draft (lead still does the faithfulness pass)
  plan          checklist.jsonl -> investigator batch files + the exact dispatch list
  status        merge findings, pack verifier batches, detect stragglers, print NEXT
  queue         adjudication queue: disagreements + a deterministic spot-check sample
  adjudicate    record the lead's final decisions
  report        assemble the final report (+ traceability CSV)
  check         mechanical quality gate (every id decided, evidence exists, MISSING double-searched ...)
  finish/abort  disarm the hooks and close the audit

Python 3.8+, standard library only. Every command is idempotent and safe to re-run.
"""
import argparse
import csv
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path

AUDIT_DIR = ".hybrid-audit"
CONFIG = "config.json"
STATE = "state.json"
ACTIVE = "ACTIVE"
SKILL_DIR = Path(__file__).resolve().parents[1]

STATUSES = ("MATCHED", "PARTIAL", "MISSING", "CONFLICT", "UNVERIFIABLE", "UNSEARCHED")
DISCREPANT = {"PARTIAL", "MISSING", "CONFLICT"}
CONFIDENCES = ("high", "medium", "low")
STRENGTHS = ("MUST", "SHOULD", "MAY")
SKIP_TAGS = {"static-limit", "ambiguous"}

DEFAULT_CAP = 20            # Claude Code default concurrent-subagent cap (v2.1.217+)
TARGET_CAP = 64             # what this skill is designed for (CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=64)
MAX_BATCH = 12              # never give one investigator more than this many requirements
SOLO_BATCH = 8
VERIFY_MAX_PER_AGENT = 3
VERIFY_TRIGGER = 4          # dispatch a verifier wave once this many items are pending (or wave A is done)
HEDGE_MIN_SECONDS = 180     # never hedge (duplicate) a straggler younger than this
PARSE_WORDS_PER_SECTION = 1500
PARSE_THRESHOLD_WORDS = 800             # the original's value: preset claude must equal it
OFFLOAD_PARSE_THRESHOLD_WORDS = 2500    # only presets that offload parse work use the larger threshold
MAX_PARSERS = 16

PLUGIN_NAME = "claude-req-audit"
AGENT_NAMES = {"investigator": "claude-rca-investigator", "verifier": "claude-rca-verifier", "parser": "claude-rca-parser"}
MODELS = {"investigator": "sonnet", "verifier": "sonnet", "parser": "sonnet"}
OFFLOAD_MODELS = {"investigator": "haiku"}  # overrides MODELS in presets that offload (cheaper Claude investigators)

STATUS_ICON = {"MATCHED": "✅", "PARTIAL": "⚠️", "MISSING": "❌", "CONFLICT": "⛔",
               "UNVERIFIABLE": "❓", "UNSEARCHED": "🔍"}

# --------------------------------------------------------------------------- helpers

def now():
    return time.time()


def ts_iso(t=None):
    return datetime.fromtimestamp(t or now()).strftime("%Y-%m-%d %H:%M:%S")


def read_json(p, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(p, obj):
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:  # called on every save
        sys.path.insert(0, here)
    import ha_run
    ha_run.atomic_write(p, json.dumps(obj, ensure_ascii=False, indent=1))


def read_jsonl(p):
    """Tolerant JSONL reader: returns (rows, errors). Skips blank lines and // comments.

    Falls back to a whole-file JSON parse (or a raw_decode stream of concatenated
    values) when nothing parses line-by-line, so a pretty-printed / multi-line
    JSON file is not silently read as zero rows. Strips a leading BOM.
    """
    rows, line_errors = [], []
    path = Path(p)
    if not path.exists():
        return rows, line_errors
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    whole = raw.strip()
    if not whole:
        return rows, line_errors
    try:
        obj = json.loads(whole)
        if isinstance(obj, dict):
            return [obj], []
        if isinstance(obj, list):
            return [o for o in obj if isinstance(o, dict)], []
    except json.JSONDecodeError:
        pass
    for n, line in enumerate(raw.splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("//") or s.startswith("#"):
            continue
        # tolerate a trailing comma or a JSON array wrapper
        s = s.rstrip(",")
        if s in ("[", "]"):
            continue
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                rows.append(obj)
            elif isinstance(obj, list):
                rows.extend(o for o in obj if isinstance(o, dict))
        except json.JSONDecodeError as e:
            line_errors.append("%s:%d: %s" % (path.name, n, e.msg))
    if rows and not line_errors:
        return rows, []
    text = whole
    decoder = json.JSONDecoder()
    idx, n_chars, stream_rows, stream_errors = 0, len(text), [], []
    while idx < n_chars:
        while idx < n_chars and text[idx] in " \t\r\n,":
            idx += 1
        if idx >= n_chars:
            break
        try:
            obj, end = decoder.raw_decode(text, idx)
        except json.JSONDecodeError as e:
            stream_errors.append("%s: %s" % (path.name, e.msg))
            break
        if isinstance(obj, dict):
            stream_rows.append(obj)
        elif isinstance(obj, list):
            stream_rows.extend(o for o in obj if isinstance(o, dict))
        idx = end
    if stream_rows and not stream_errors:
        return stream_rows, []
    if rows:
        return rows, line_errors
    return stream_rows, (stream_errors or line_errors)


def write_text(p, text):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(text, encoding="utf-8")


def die(msg, code=1):
    print("ERROR: " + msg)
    sys.exit(code)


def fmt_dur(seconds):
    seconds = int(max(0, seconds))
    return "%dm%02ds" % (seconds // 60, seconds % 60) if seconds >= 60 else "%ds" % seconds


def is_under(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except Exception:
        return False


def batch_key(name):
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else 0


def base_batch(name):
    """'batch-01-r7' -> 'batch-01' (a retry's SubagentStop event counts toward its base batch)."""
    m = re.match(r"^(.*)-r\d+$", name)
    return m.group(1) if m else name


def routing_context(c):
    """(routing, preset, doctor) for this audit: config.json values, falling back to the routing files."""
    use_scripts()
    import ha_router
    routing = c.cfg.get("routing") or ha_router.load_routing(SKILL_DIR / "routing.default.json",
                                                             ha_router.user_routing_path())
    preset = ha_router.effective_preset(routing, c.cfg.get("preset") or "")
    freeze_health(c, routing, preset)
    return routing, preset, run_health(c)


SKILL_NAME = "hybrid-requirements-code-audit"
ERRORS_FILE = "oc-errors.jsonl"
HOLD_REASON = "no usable opencode tier; preset opencode does not fall back to Claude on its own"
HELD_NEXT = ("NEXT: %d unit(s) are held: preset opencode never runs them on Claude by itself. Follow SKILL.md "
             "\"Held units\": ask the user once, then `audit.py status --retry all` (after fixing opencode), "
             "`audit.py status --to-claude investigator|verifier` (parsers: `audit.py parse-merge --to-claude`) "
             "or `audit.py status --mode hybrid`.")


def use_scripts():
    """Put scripts/ on sys.path so the ha_* modules and hybrid_shared import."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)


def shared():
    use_scripts()
    import hybrid_shared
    return hybrid_shared


def fail_config(unit, detail):
    """Print one OC-ERROR kind=config line and exit non-zero."""
    print(shared().oc_line("OC-ERROR", SKILL_NAME, unit, "none", "none", "config", detail))
    sys.exit(2)


def note_oc(c, level, unit, kind, detail, tier="none", spec="none"):
    """Append one OC line to the run's oc-errors.jsonl; flush_oc prints it."""
    hs = shared()
    hs.log_line(c.out / ERRORS_FILE, hs.oc_line(level, SKILL_NAME, unit, tier, spec, kind, detail))


def flush_oc(c):
    """Print the OC lines nobody has shown yet, oldest first."""
    for line in shared().take_unreported(c.out / ERRORS_FILE):
        print(line)


def resolve_mode(raw, unit):
    """(preset, note) for a --preset/--mode value: ("", "") when empty; note is the max-alias warning the
    caller logs with note_oc once the audit dir exists; OC-ERROR and exit when the mode is unknown."""
    if not raw:
        return "", ""
    preset, note = shared().mode_to_preset(raw)
    if not preset:
        fail_config(unit, note)
    return preset, note


def report_config(c, routing, preset):
    """Log the shared-config problems and config warnings (preset claude never needs the config), then print."""
    if preset != "claude":
        for problem in routing.get("config_problems") or []:
            note_oc(c, "OC-ERROR", "config", "config", problem)
        for warning in routing.get("config_warnings") or []:
            note_oc(c, "OC-WARN", "config", "config", warning)
    flush_oc(c)


def run_health(c):
    """The run's frozen tier health (freeze_health), else the live doctor cache for an audit that has none."""
    use_scripts()
    import ha_doctor
    return c.state.get("health") or ha_doctor.load_doctor(ha_doctor.doctor_cache_path())


def doctor_problems(routing, data, names=None):
    """[(tier, spec, kind, detail)] for each checked tier the doctor found unusable."""
    hs = shared()
    tiers = routing.get("tiers") or {}
    out = []
    for name, entry in sorted((data.get("tiers") or {}).items()):
        if (names is None or name in names) and not entry.get("ok"):
            out.append((name, hs.cache_key(tiers.get(name) or {}) or "none", entry.get("kind") or "config",
                        entry.get("detail") or "tier is not usable"))
    return out


def clear_breakers(c, names):
    """Close the run's circuit breaker for these tiers (an explicit retry pinged them ok)."""
    for path in (c.out / shared().BREAKER_DIR).glob("*.json"):
        if (read_json(path) or {}).get("tier") in names:
            for f in (path, path.with_suffix(".skip")):
                try:
                    f.unlink()
                except OSError:
                    pass
    c.state.pop("breaker_lines", None)


def freeze_health(c, routing, preset, force=False):
    """Freeze tier health for the run. Pings once when the doctor cache is missing or stale for the tiers
    this preset uses (always with force, the explicit retry); only this and no TTL may change a run's tiers."""
    if preset == "claude" or c.cfg.get("agents") == "solo":
        return
    use_scripts()
    import ha_doctor
    import ha_router
    hs = shared()
    names = sorted(set(ha_router.role_tier(r, routing, preset) for r in ha_router.ROLES) - {"claude"})
    tiers = routing.get("tiers") or {}
    cache = ha_doctor.doctor_cache_path()
    data = ha_doctor.load_doctor(cache)
    t = now()
    stale = [n for n in names if not hs.cache_fresh((data.get("tiers") or {}).get(n), tiers.get(n) or {}, t)]
    if names and (force or stale or not data.get("ok")):
        data = ha_doctor.run_doctor(os.environ.get("HYBRID_AUDIT_OC_BIN", "opencode"), routing, True, c.repo, data,
                                    names=names, logdir=cache.parent)
        ha_doctor.write_doctor(cache, data)
        for name, spec, kind, detail in doctor_problems(routing, data, names):
            note_oc(c, "OC-ERROR", "doctor", kind, detail, name, spec)
        if force:
            clear_breakers(c, [n for n in names if ((data.get("tiers") or {}).get(n) or {}).get("ok")])
    c.state["health"] = dict(data, frozen=True)
    c.save_state()


def held_units(c):
    return c.state.get("held") or {}


def mark_held(c, name, role, reason=HOLD_REASON):
    c.state.setdefault("held", {})[name] = {"role": role, "reason": reason}


def switched(c):
    """True once a hybrid run moved to Claude sonnet after an opencode failure (ha_run writes the record)."""
    return c.cfg.get("preset") == "hybrid" and bool(shared().run_switched(c.out))


def allow_claude(c, roles):
    """Record that the user let these roles run on Claude in a preset opencode run."""
    have = c.state.setdefault("claude_roles", [])
    have.extend(r for r in roles if r not in have)


def route_for(c, role, routing, doctor, preset, t):
    """ha_router.route with the run's breaker dir; a role the user moved to Claude always routes to claude."""
    if role in c.state.get("claude_roles", []):
        return "claude"
    use_scripts()
    import ha_router
    return ha_router.route(role, routing, doctor, preset, c.state.get("cooldown", {}), t, c.out)


def refresh_routing(c):
    """Re-read the routing file and the shared env vars, so a fix made after `init` takes effect in this run."""
    use_scripts()
    import ha_router
    c.cfg["routing"] = ha_router.load_routing(SKILL_DIR / "routing.default.json", ha_router.user_routing_path())
    c.save_cfg()


def release_held(c, roles=None, names=None):
    """Drop held marks so the next routing pass may dispatch those units again; names="all" drops every mark."""
    held = held_units(c)
    for name in list(held):
        if names == "all" or (names and name in names) or (roles and held[name].get("role") in roles):
            del held[name]


def hold_unit(c, m, fb):
    """Preset opencode: a failed opencode unit waits for the user instead of falling back to Claude."""
    name = fb["name"]
    meta = m.batches.get(name) or m.vbatches.get(name) or {}
    meta["backend"] = "held"
    meta["dispatched"] = None
    c.state.get("fallbacks", {}).pop(name, None)
    backends = (c.state.get("parse") or {}).get("backends")
    if isinstance(backends, dict) and name in backends:
        backends[name] = "held"
    mark_held(c, name, fb["role"], fb["reason"])


def opencode_stranded(c):
    """Names of held verifier batches and of opencode units whose ids are not all covered or whose last event failed."""
    m = Merged(c)
    done = dict(m.batch_done)
    done.update(m.vdone)
    units = dict(c.state.get("batches") or {})
    units.update(c.state.get("verify") or {})
    return sorted(n for n, meta in units.items()
                  if (meta.get("backend") == "held" and n in c.state.get("verify", {}))
                  or (str(meta.get("backend", "")).startswith("oc:")
                      and (not done.get(n) or (n in m.events and not m.events[n].get("ok")))))


def apply_run_flags(c, a):
    """The user's answer to held units: --mode, --to-claude and --retry."""
    if a.mode:
        preset, note = resolve_mode(a.mode, "status")
        if note:
            note_oc(c, "OC-WARN", "status", "config", note)
        stranded = opencode_stranded(c) if preset == "claude" and c.cfg.get("preset") != "claude" else []
        if stranded:
            fail_config("status", "--mode claude would strand opencode units (%s): run `audit.py status` first "
                        "(it harvests finished units), wait for the running ones, or use --to-claude"
                        % ", ".join(stranded))
        c.cfg["preset"] = preset
        c.save_cfg()
        release_held(c, names="all")
    if a.to_claude:
        roles = ["investigator", "verifier"] if "all" in a.to_claude else list(a.to_claude)
        allow_claude(c, roles)
        release_held(c, roles=roles)
    if a.retry:
        refresh_routing(c)
        # an explicit retry re-pings; a tier whose ping is ok gets its breaker closed
        freeze_health(c, c.cfg["routing"], c.cfg.get("preset") or "", force=True)
        release_held(c, names="all" if "all" in a.retry else a.retry)
    if a.mode or a.to_claude or a.retry:
        c.save_state()


def breaker_lines(c):
    """Log the breaker summary once per distinct content, so each phase reports it a single time."""
    hs = shared()
    lines = hs.breaker_summary(c.out, SKILL_NAME)
    if lines == c.state.get("breaker_lines", []):
        return
    c.state["breaker_lines"] = lines
    for line in lines:
        hs.log_line(c.out / ERRORS_FILE, line)


class Ctx(object):
    """Everything a command needs: paths, config, state."""

    def __init__(self, cwd=None):
        self.cwd = Path(cwd or os.getcwd()).resolve()
        self.cfg_dir = self.cwd / AUDIT_DIR
        self.cfg_path = self.cfg_dir / CONFIG
        self.cfg = read_json(self.cfg_path)
        if not self.cfg:
            die("no audit here (%s missing). Run `audit.py init --spec <file>` first." % self.cfg_path)
        self.out = Path(self.cfg["out_dir"])
        self.repo = Path(self.cfg["repo_root"])
        self.state_path = self.out / STATE
        self.state = read_json(self.state_path, {})
        self.lang = self.cfg.get("lang", "en")

    def save_state(self):
        write_json(self.state_path, self.state)

    def save_cfg(self):
        write_json(self.cfg_path, self.cfg)

    # ---- agent dispatch strings
    def agent_type(self, role):
        mode = self.cfg.get("agents", "generic")
        if mode == "plugin":
            return "%s:%s" % (PLUGIN_NAME, AGENT_NAMES[role])
        if mode == "local":
            return AGENT_NAMES[role]
        if mode == "solo":
            return "SOLO (the lead does this itself)"
        return "general-purpose"

    def model(self, role):
        return self.cfg.get("models", MODELS).get(role, MODELS[role])

    def dispatch_model(self, role):
        """The model a Claude worker is dispatched with: sonnet for the rest of a switched hybrid run."""
        return shared().FALLBACK_MODEL if switched(self) else self.model(role)

    def rel(self, p):
        try:
            return str(Path(p).resolve().relative_to(self.cwd))
        except Exception:
            return str(p)

    # ---- checklist
    def checklist(self):
        rows, errors = read_jsonl(self.out / "checklist.jsonl")
        return rows, errors


# --------------------------------------------------------------------------- language + spec text

VI_CHARS = set("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
               "ĂÂĐÊÔƠƯÀÁẢÃẠẰẮẲẴẶẦẤẨẪẬÈÉẺẼẸỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌỒỐỔỖỘỜỚỞỠỢÙÚỦŨỤỪỨỬỮỰỲÝỶỸỴ")


def detect_lang(text):
    letters = sum(1 for c in text if c.isalpha())
    if not letters:
        return "en"
    vi = sum(1 for c in text if c in VI_CHARS)
    return "vi" if vi / float(letters) > 0.004 else "en"


def docx_text(path):
    """Verbatim paragraph text from a .docx (stdlib only)."""
    with zipfile.ZipFile(str(path)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    xml = re.sub(r"<w:br[^>]*/>", "\n", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def load_spec_text(paths):
    parts = []
    for p in paths:
        try:
            parts.append(Path(p).read_text(encoding="utf-8", errors="replace"))
        except Exception:
            parts.append("")
    return "\n\n".join(parts)


def materialize_spec(path, out_spec_dir):
    """Return a readable text path for a spec file, extracting binary formats verbatim when possible."""
    p = Path(path).resolve()
    if not p.exists():
        die("spec file not found: %s" % p)
    suffix = p.suffix.lower()
    if suffix == ".docx":
        target = out_spec_dir / (p.stem + ".md")
        write_text(target, docx_text(p))
        return target, "extracted verbatim from %s (docx paragraphs); tables/images are flattened — spot-check it" % p.name
    if suffix == ".pdf":
        target = out_spec_dir / (p.stem + ".txt")
        if shutil.which("pdftotext"):
            subprocess.run(["pdftotext", "-layout", str(p), str(target)], check=False)
            if target.exists() and target.stat().st_size > 0:
                return target, "extracted with pdftotext -layout; verify columns/tables"
        return p, "PDF: extract the text yourself (pdf skill / Read tool), save it under %s and add it with `audit.py spec --add`" % out_spec_dir
    if suffix in (".xlsx", ".xlsm", ".pptx"):
        return p, "%s: extract the text with the matching skill, save it under %s and add it with `audit.py spec --add`" % (suffix, out_spec_dir)
    return p, None


# --------------------------------------------------------------------------- repo map

IGNORE_DIRS = {".git", ".hg", ".svn", "node_modules", "vendor", "dist", "build", "target", "out",
               ".venv", "venv", "env", "__pycache__", ".next", ".nuxt", ".cache", "coverage",
               ".idea", ".vscode", AUDIT_DIR, "bin", "obj", "Pods", "DerivedData", ".gradle",
               ".terraform", ".tox", ".mypy_cache", ".pytest_cache", "site-packages",
               ".svelte-kit", ".turbo", ".parcel-cache", "third_party", "external", ".dart_tool",
               "Carthage", ".serverless", "tmp", "temp", "logs"}
MANIFESTS = ["package.json", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile",
             "go.mod", "Cargo.toml", "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
             "composer.json", "Gemfile", "mix.exs", "pubspec.yaml", "Package.swift", "CMakeLists.txt",
             "Makefile", "Dockerfile", "docker-compose.yml", "docker-compose.yaml", "serverless.yml",
             "tsconfig.json", "angular.json", "next.config.js", "nuxt.config.ts", "vite.config.ts",
             "manage.py", "app.py", "main.py", "wsgi.py", "asgi.py", "prisma/schema.prisma", "schema.graphql"]
ENTRY_RE = re.compile(r"^(main|index|app|server|cli|program|application|bootstrap|entry|startup|manage|wsgi|asgi)\.[a-z]+$", re.I)
ROUTE_DIRS = re.compile(r"^(routes?|routers?|controllers?|handlers?|api|endpoints?|views?|resolvers?|graphql|grpc|pages|app/api|rest|web)$", re.I)
MODEL_DIRS = re.compile(r"^(models?|entities|entity|schemas?|domain|prisma|migrations?|db|database|repositor(y|ies)|dao|orm|store)$", re.I)
CONFIG_DIRS = re.compile(r"^(config|configs|settings|conf|env|environments)$", re.I)
TEST_DIRS = re.compile(r"^(tests?|spec|specs|__tests__|e2e|integration|cypress|playwright)$", re.I)
SERVICE_DIRS = re.compile(r"^(services?|usecases?|use_cases|application|core|lib|internal|pkg|src|app|cmd|features?|modules?|middlewares?|auth|security|jobs?|workers?|tasks?|events?|queues?|utils?|helpers?|components?|hooks|infra|infrastructure)$", re.I)
LANG_BY_EXT = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript/React", ".js": "JavaScript", ".jsx": "JavaScript/React",
               ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".swift": "Swift", ".rb": "Ruby", ".php": "PHP",
               ".cs": "C#", ".cpp": "C++", ".cc": "C++", ".c": "C", ".h": "C/C++ header", ".scala": "Scala", ".ex": "Elixir",
               ".exs": "Elixir", ".dart": "Dart", ".vue": "Vue", ".svelte": "Svelte", ".sql": "SQL", ".proto": "Protobuf",
               ".graphql": "GraphQL", ".prisma": "Prisma", ".tf": "Terraform", ".yaml": "YAML", ".yml": "YAML", ".json": "JSON",
               ".sh": "Shell", ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".m": "Objective-C", ".r": "R", ".lua": "Lua"}


def build_repo_map(repo, max_files=60000):
    repo = Path(repo)
    ext_counts, top_dirs, manifests = {}, {}, []
    entries, routes, models, configs, tests, services, shallow = [], [], [], [], [], [], []
    scanned = 0
    for root, dirs, files in os.walk(str(repo)):
        rel_root = Path(root).relative_to(repo)
        depth = len(rel_root.parts)
        dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".") or d in (".github",))
        if depth >= 5:
            dirs[:] = []
        for d in dirs:
            rp = str(rel_root / d) if depth else d
            if depth <= 1 and len(shallow) < 40:
                shallow.append(rp)
            if ROUTE_DIRS.match(d):
                routes.append(rp)
            elif MODEL_DIRS.match(d):
                models.append(rp)
            elif CONFIG_DIRS.match(d):
                configs.append(rp)
            elif TEST_DIRS.match(d):
                tests.append(rp)
            elif depth <= 2 and SERVICE_DIRS.match(d):
                services.append(rp)
        for f in files:
            scanned += 1
            if scanned > max_files:
                break
            ext = Path(f).suffix.lower()
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
            top = rel_root.parts[0] if depth else "(root)"
            top_dirs[top] = top_dirs.get(top, 0) + 1
            rp = str(rel_root / f) if depth else f
            if rp in MANIFESTS or f in MANIFESTS:
                manifests.append(rp)
            elif depth <= 3 and ENTRY_RE.match(f) and ext in LANG_BY_EXT:
                entries.append(rp)
            elif f.endswith(("_test.go", ".test.ts", ".test.js", ".spec.ts", ".spec.js", "_test.py", "_spec.rb")) and len(tests) < 40:
                tests.append(rp)
        if scanned > max_files:
            break
    lines = []
    langs = sorted(((LANG_BY_EXT.get(e, e), c) for e, c in ext_counts.items() if e in LANG_BY_EXT), key=lambda x: -x[1])[:8]
    lines.append("Languages (files): " + ", ".join("%s %d" % (n, c) for n, c in langs) if langs else "Languages: (none detected)")
    for m in manifests[:6]:
        lines.append("Manifest: %s%s" % (m, manifest_hint(repo / m)))
    td = sorted(top_dirs.items(), key=lambda x: -x[1])[:14]
    lines.append("Top-level: " + ", ".join("%s/(%d)" % (d, c) if d != "(root)" else "root(%d)" % c for d, c in td))
    if shallow:
        lines.append("Dirs (depth ≤ 2): " + ", ".join(shallow[:40]))
    if entries:
        lines.append("Entry points: " + ", ".join(entries[:8]))
    if routes:
        lines.append("Routes/handlers: " + ", ".join(routes[:8]))
    if models:
        lines.append("Models/schema/migrations: " + ", ".join(models[:8]))
    if configs:
        lines.append("Config: " + ", ".join(configs[:6]))
    if services:
        lines.append("Service/feature dirs: " + ", ".join(sorted(set(services))[:12]))
    if tests:
        lines.append("Tests: " + ", ".join(tests[:6]) + (" …" if len(tests) > 6 else ""))
    lines.append("Excluded from scans: " + ", ".join(sorted(d for d in IGNORE_DIRS if (repo / d).exists())[:10] or ["-"]))
    return "\n".join(lines[:30]) + "\n"


def manifest_hint(path):
    try:
        if path.name == "package.json":
            j = json.loads(path.read_text(encoding="utf-8"))
            deps = list((j.get("dependencies") or {}).keys())
            fw = [d for d in deps if d in ("express", "fastify", "koa", "next", "nuxt", "react", "vue", "@nestjs/core",
                                            "hono", "@angular/core", "svelte", "prisma", "@prisma/client", "typeorm",
                                            "sequelize", "mongoose", "drizzle-orm", "knex", "jest", "vitest")]
            return " — %s; main=%s; scripts=%s; deps=%d%s" % (j.get("name", "?"), j.get("main", "-"),
                                                            ",".join(list((j.get("scripts") or {}).keys())[:6]),
                                                            len(deps), (" [" + ",".join(fw) + "]") if fw else "")
        if path.name == "go.mod":
            first = path.read_text(encoding="utf-8").splitlines()[0]
            return " — " + first
        if path.name == "pyproject.toml":
            t = path.read_text(encoding="utf-8")
            m = re.search(r'^name\s*=\s*"([^"]+)"', t, re.M)
            fw = [f for f in ("fastapi", "django", "flask", "sqlalchemy", "pydantic", "celery", "pytest") if f in t.lower()]
            return " — %s%s" % (m.group(1) if m else "?", (" [" + ",".join(fw) + "]") if fw else "")
        if path.name == "Cargo.toml":
            m = re.search(r'^name\s*=\s*"([^"]+)"', path.read_text(encoding="utf-8"), re.M)
            return " — " + (m.group(1) if m else "?")
    except Exception:
        pass
    return ""


# --------------------------------------------------------------------------- git exclude

def git_exclude(out_dir):
    """Add the audit dir to .git/info/exclude (local, untracked) so the codebase stays untouched."""
    d = Path(out_dir).resolve()
    cur = d.parent
    while True:
        g = cur / ".git"
        if g.exists():
            break
        if cur.parent == cur:
            return None
        cur = cur.parent
    gitdir = g
    if g.is_file():
        m = re.search(r"gitdir:\s*(.+)", g.read_text(encoding="utf-8"))
        if not m:
            return None
        gitdir = Path(m.group(1).strip())
        if not gitdir.is_absolute():
            gitdir = (cur / gitdir).resolve()
        # a linked worktree's own gitdir is private; the shared info/exclude lives
        # in the COMMON dir named by its `commondir` file (relative to gitdir).
        commondir_file = gitdir / "commondir"
        if commondir_file.exists():
            common = commondir_file.read_text(encoding="utf-8").strip()
            common_path = Path(common)
            if not common_path.is_absolute():
                common_path = (gitdir / common_path).resolve()
            gitdir = common_path
    try:
        rel = "/" + str(d.relative_to(cur)).replace(os.sep, "/") + "/"
    except Exception:
        return None
    ex = gitdir / "info" / "exclude"
    try:
        ex.parent.mkdir(parents=True, exist_ok=True)
        existing = ex.read_text(encoding="utf-8") if ex.exists() else ""
        if rel not in existing.splitlines():
            with open(str(ex), "a", encoding="utf-8") as f:
                f.write(("\n" if existing and not existing.endswith("\n") else "") + rel + "\n")
        return str(ex)
    except Exception:
        return None


# --------------------------------------------------------------------------- init

def cmd_init(a):
    cwd = Path(a.cwd or os.getcwd()).resolve()
    requested, mode_note = resolve_mode(a.preset, "init")
    cfg_dir = cwd / AUDIT_DIR
    cfg_path = cfg_dir / CONFIG
    old = read_json(cfg_path)
    if old and not a.force:
        if old.get("active"):
            print("An audit is already active here (started %s). Resuming — run `audit.py status`." % old.get("created"))
            print("Use `audit.py init --force ...` to archive it and start over.")
            return
        print("A finished audit exists here. Use --force to archive it and start a new one.")
        return
    if old and a.force:
        archived = cwd / (AUDIT_DIR + ".prev-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
        shutil.move(str(cfg_dir), str(archived))
        print("Archived previous audit to %s" % archived.name)
    out = Path(a.out).resolve() if a.out else cfg_dir
    repo = Path(a.repo).resolve() if a.repo else cwd
    if not repo.exists():
        die("repo root not found: %s" % repo)
    for sub in ("", "batches", "findings", "verify", "parse", "spec", "events"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    # a new audit starts unswitched, with closed breakers and no events or OC lines of an earlier run
    # (`--force --out X` archives .hybrid-audit/ only, so X may still hold them)
    shutil.rmtree(str(out / shared().BREAKER_DIR), ignore_errors=True)
    for stale in [out / shared().SWITCH_FILE, out / ERRORS_FILE, out / (ERRORS_FILE + ".seen")] \
            + list((out / "events").glob("*.json")):
        try:
            stale.unlink()
        except OSError:
            pass  # nothing left by an earlier run
    cfg_dir.mkdir(parents=True, exist_ok=True)

    specs, notes = [], []
    for s in (a.spec or []):
        p, note = materialize_spec(s, out / "spec")
        specs.append(str(p))
        if note:
            notes.append("%s: %s" % (Path(s).name, note))
    if a.spec_text:
        target = out / "spec" / "pasted-requirements.md"
        write_text(target, Path(a.spec_text).read_text(encoding="utf-8", errors="replace"))
        specs.append(str(target))
    if not specs:
        die("no requirements input. Pass --spec <file> (repeatable) or --spec-text <file-with-pasted-text>. Without a spec there is nothing to audit — stop and ask the user.")

    text = load_spec_text(specs)
    words = len(text.split())
    lang = a.lang if a.lang and a.lang != "auto" else detect_lang(text)
    env_cap = os.environ.get("CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS", "").strip()
    cap = a.cap or (int(env_cap) if env_cap.isdigit() else DEFAULT_CAP)
    agents = a.agents or "generic"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ha_doctor
    import ha_router
    routing = ha_router.load_routing(SKILL_DIR / "routing.default.json", ha_router.user_routing_path())
    try:
        preset = "claude" if agents == "solo" else ha_router.effective_preset(routing, requested)
    except ValueError as exc:
        fail_config("init", str(exc))
    cfg = {
        "active": True,
        "created": ts_iso(),
        "cwd": str(cwd),
        "repo_root": str(repo),
        "out_dir": str(out),
        "spec_files": specs,
        "spec_words": words,
        "lang": lang,
        "cap": cap,
        "agents": agents,
        "models": models_for(preset),
        "scripts_dir": str(Path(__file__).resolve().parent),
        "preset": preset,
        "routing": routing,
    }
    write_json(cfg_path, cfg)
    (cfg_dir / ACTIVE).write_text("requirements-code-audit active since %s\n" % cfg["created"], encoding="utf-8")
    excl = git_exclude(out)
    repo_map = build_repo_map(repo)
    write_text(out / "repo_map.md", repo_map)
    write_json(out / STATE, {"created": now(), "cap": cap, "batches": {}, "verify": {}, "verify_assigned": {},
                             "spotchecked": [], "hedges": {}, "failed": []})

    print("requirements-code-audit initialised")
    print("  audit dir : %s  (guard marker: %s)" % (out, cfg_dir / ACTIVE))
    print("  repo root : %s" % repo)
    print("  spec      : %s  (~%d words, lang=%s)" % (", ".join(specs), words, lang))
    for n in notes:
        print("  NOTE      : " + n)
    print("  agents    : %s  -> investigator=%s (%s), verifier=%s (%s)" % (
        agents, Ctx(cwd).agent_type("investigator"), MODELS["investigator"], Ctx(cwd).agent_type("verifier"), MODELS["verifier"]))
    print("  cap       : %d concurrent subagents%s" % (
        cap, "" if cap >= TARGET_CAP else "  (raise to %d: settings.json → \"env\": {\"CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS\": \"%d\"} then restart; not blocking)" % (TARGET_CAP, TARGET_CAP)))
    print("  git       : %s" % ("excluded via " + excl if excl else "not a git checkout (nothing to exclude)"))
    print("  repo map  : %s (%d lines)" % (out / "repo_map.md", len(repo_map.splitlines())))
    c = Ctx(cwd)
    if mode_note:
        note_oc(c, "OC-WARN", "init", "config", mode_note)
    freeze_health(c, routing, preset)
    print(ha_doctor.status_line(routing, ha_doctor.load_doctor(ha_doctor.doctor_cache_path()), preset))
    report_config(c, routing, preset)
    print()
    if words > parse_threshold(preset) and agents != "solo":
        print("NEXT: large spec (%d words) → parallelise parsing: `audit.py parse-plan` then dispatch the parser agents it lists." % words)
        print("      (or write %s yourself if you prefer — see SKILL.md Step 1)" % (out / "checklist.jsonl"))
    else:
        print("NEXT: read the spec, write %s (one JSON object per atomic requirement — schema in SKILL.md Step 1)," % (out / "checklist.jsonl"))
        print("      then run `audit.py plan`.")


# --------------------------------------------------------------------------- spec

def cmd_spec(a):
    c = Ctx(a.cwd)
    if a.add:
        for s in a.add:
            p, note = materialize_spec(s, c.out / "spec")
            if str(p) not in c.cfg["spec_files"]:
                c.cfg["spec_files"].append(str(p))
            if note:
                print("NOTE: " + note)
        c.cfg["spec_words"] = len(load_spec_text(c.cfg["spec_files"]).split())
        c.save_cfg()
    print("Source of truth (%d file(s), ~%d words, lang=%s):" % (len(c.cfg["spec_files"]), c.cfg.get("spec_words", 0), c.lang))
    for s in c.cfg["spec_files"]:
        print("  - " + s)


# --------------------------------------------------------------------------- checklist schema

CHECKLIST_SCHEMA = (
    '{"id":"REQ-001","text":"faithful restatement, quote load-bearing phrases","strength":"MUST|SHOULD|MAY",'
    '"category":"auth","stakes":"high|normal","evidence_expected":"what code would prove it",'
    '"search_hints":["identifier","endpoint","English synonym"],"tags":[],"source":"§2.1","question":""}'
)
CHECKLIST_RULES = """Checklist rules:
- One line per atomic, independently verifiable requirement (split "A and B" into two items).
- text: faithful to the spec's meaning; keep the spec's language; quote load-bearing wording.
- strength: RFC 2119. If the spec doesn't say, infer conservatively from its own words
  (vi: phải/bắt buộc→MUST, nên→SHOULD, có thể→MAY; unclear→MUST + note the inference in text).
- stakes: "high" for security, auth, permissions, payments, data integrity/loss, privacy, safety — these are always verified twice.
- search_hints: identifiers, endpoint paths, field/table names, error codes AND English keywords/synonyms —
  the spec's language rarely appears in identifiers; missing hints are the #1 cause of false MISSING.
- tags: "static-limit" (latency/SLA/infra/external behaviour that static reading can't settle) or
  "ambiguous" (wording too vague; put the question in "question"). Tagged items skip the waves.
- source: section/page reference in the spec for traceability."""


def validate_checklist(rows):
    problems, seen = [], set()
    for i, r in enumerate(rows, 1):
        rid = r.get("id")
        if not rid or not isinstance(rid, str):
            problems.append("line %d: missing id" % i)
            continue
        if rid in seen:
            problems.append("%s: duplicate id" % rid)
        seen.add(rid)
        if not r.get("text"):
            problems.append("%s: missing text" % rid)
        if r.get("strength") not in STRENGTHS:
            problems.append("%s: strength must be one of %s" % (rid, "/".join(STRENGTHS)))
        if not isinstance(r.get("search_hints", []), list):
            problems.append("%s: search_hints must be a list" % rid)
        tags = r.get("tags") or []
        if not isinstance(tags, list):
            problems.append("%s: tags must be a list" % rid)
        elif "ambiguous" in tags and not r.get("question"):
            problems.append("%s: tagged ambiguous but no question" % rid)
    return problems


def checklist_md(rows):
    out = ["# Requirements checklist (%d items)\n" % len(rows),
           "| ID | Strength | Category | Stakes | Tags | Requirement | Search hints | Source |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        out.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r.get("id"), r.get("strength"), r.get("category", ""), r.get("stakes", "normal"),
            ",".join(r.get("tags") or []), (r.get("text") or "").replace("|", "\\|"),
            ", ".join(r.get("search_hints") or []).replace("|", "\\|"), r.get("source", "")))
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- parse-plan / parse-merge

HEADING_RE = re.compile(r"^\s*(#{1,6}\s+\S|\d+(\.\d+){0,3}[\.\)]?\s+\S|(Phần|Chương|Mục|Điều|Section|Chapter|Article|Part|Appendix|Phụ lục)\s+[\dIVX]+)", re.I)


def split_sections(text, k):
    lines = text.splitlines()
    heads = [i for i, l in enumerate(lines) if HEADING_RE.match(l)]
    if len(heads) < 2:
        step = max(1, math.ceil(len(lines) / float(k)))
        return ["\n".join(lines[i:i + step]) for i in range(0, len(lines), step)]
    if heads[0] != 0:
        heads = [0] + heads
    segs = [lines[heads[i]:(heads[i + 1] if i + 1 < len(heads) else len(lines))] for i in range(len(heads))]
    total = sum(len("\n".join(s)) for s in segs)
    target = total / float(k)
    chunks, cur, size = [], [], 0
    for s in segs:
        seg_text = "\n".join(s)
        if cur and size + len(seg_text) > target * 1.15 and len(chunks) < k - 1:
            chunks.append("\n".join(cur))
            cur, size = [], 0
        cur.append(seg_text)
        size += len(seg_text)
    if cur:
        chunks.append("\n".join(cur))
    return chunks


def parse_body(c, name, chunk, outp):
    """Parser brief text for one spec section (`section-NN`); item ids use the `SNN-` prefix."""
    return ("# Parser {name} — requirements↔code audit (spec parsing)\n"
            "Write your output to: {outp}\n"
            "Final reply: exactly one line: `{name} done: <n> items` — nothing else.\n"
            "\n"
            "## Task\n"
            "Decompose ONLY the section below into atomic, independently verifiable requirements.\n"
            "Use ids `{sid}-001`, `{sid}-002`, … in document order (they are renumbered later).\n"
            "Do not read any other file. Do not invent requirements that are not in the text. Do not summarise —\n"
            "each item must be faithful to the wording; quote load-bearing phrases verbatim.\n"
            "\n"
            "{rules}\n"
            "\n"
            "## Output: JSON Lines (one object per line, no prose)\n"
            "{schema}\n"
            "\n"
            "## SECTION TEXT (verbatim; language: {lang})\n"
            "{chunk}\n").format(name=name, outp=outp, sid="S%02d" % batch_key(name), rules=CHECKLIST_RULES, schema=CHECKLIST_SCHEMA,
           lang=c.lang, chunk=chunk)


def cmd_parse_plan(a):
    c = Ctx(a.cwd)
    text = load_spec_text(c.cfg["spec_files"])
    words = len(text.split())
    k = a.sections or max(2, min(MAX_PARSERS, math.ceil(words / float(PARSE_WORDS_PER_SECTION))))
    k = min(k, c.cfg.get("cap", DEFAULT_CAP))
    chunks = split_sections(text, k)
    pdir = c.out / "parse"
    for pat in ("section-*.md", "section-*.jsonl"):
        for old in pdir.glob(pat):
            old.unlink()
    if "held" in ((c.state.get("parse") or {}).get("backends") or {}).values():
        refresh_routing(c)
        held_units(c).clear()
    routing, preset, doctor = routing_context(c)
    use_scripts()
    import ha_briefs
    import ha_dispatch
    import ha_router
    backend = "claude"
    if c.cfg.get("agents") != "solo":
        backend = route_for(c, "parser", routing, doctor, preset, now())
    if backend.startswith("oc:"):
        at_once = ha_router.tier_parallel(routing["tiers"][backend[3:]])
        if len(chunks) > at_once:
            chunks = split_sections(text, at_once)
    lines_out, oc_rows, backends = [], [], {}
    for i, chunk in enumerate(chunks, 1):
        name = "section-%02d" % i
        outp = pdir / (name + ".jsonl")
        write_text(pdir / (name + ".md"), parse_body(c, name, chunk, outp))
        backends[name] = backend
        if backend == "claude":
            lines_out.append("  %s → prompt: Parser %s: read %s and follow it exactly." % (name, name, pdir / (name + ".md")))
        elif backend == "held":
            mark_held(c, name, "parser")
        else:
            write_text(pdir / (name + ".oc.md"),
                       ha_briefs.to_oc_brief((pdir / (name + ".md")).read_text(encoding="utf-8"), name))
            oc_rows.append((name, backend, 0, ha_dispatch.oc_command(c, name)))
    c.state["parse"] = {"sections": len(chunks), "dispatched": now(), "backends": backends}
    c.save_state()
    if backend == "held":
        note_oc(c, "OC-ERROR", "parser", "config", "%d sections held: %s" % (len(chunks), HOLD_REASON))
        flush_oc(c)
    print("parse-plan: %d words → %d sections (parser=%s, model=%s)" % (words, len(chunks), c.agent_type("parser"), c.dispatch_model("parser")))
    if lines_out:
        print("DISPATCH NOW — one message, all calls together; subagent_type=%s, model=%s; never pass `name`, never fork:" % (c.agent_type("parser"), c.dispatch_model("parser")))
        print("\n".join(lines_out))
    if oc_rows:
        print("\n".join(ha_dispatch.oc_block(oc_rows, "sections")))
    if backend == "held":
        print("NEXT: %d sections are held: ask the user once (SKILL.md \"Held units\"), then `audit.py parse-merge --to-claude`"
              " or fix opencode and run `audit.py parse-plan` again." % len(chunks))
    else:
        print("\nThen: `audit.py parse-merge` → review checklist.draft.jsonl against the original wording → `audit.py parse-merge --accept`.")


def parse_fallbacks(c, pdir):
    """Failed or held opencode sections go to Claude parsers, or (preset opencode) wait for the user."""
    parse = c.state.get("parse") or {}
    backends = parse.get("backends") or {}
    events = {name: d for name, _, d in load_events(c)}
    claude_ok = "parser" in c.state.get("claude_roles", []) or c.cfg.get("preset") != "opencode"
    out, changed = [], False
    for name in sorted(backends, key=batch_key):
        e = events.get(name)
        if backends[name] == "held":
            if not claude_ok:
                continue
            held_units(c).pop(name, None)
            backends[name] = "claude"
            c.state.setdefault("fallbacks", {})[name] = "held"
            out.append("FALLBACK %s (held) → Claude parser" % name)
            out.append(dispatch_line(c, "parser", name, pdir / (name + ".md")))
            changed = True
            continue
        if backends[name] == "claude" or not e or e.get("ok"):
            continue
        reason = e.get("reason") or "format"
        src = c.out / "events" / (name + ".json")
        aside = c.out / "oc" / (name + ".event.json")
        aside.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            os.replace(str(src), str(aside))
        partial = pdir / (name + ".jsonl")
        if partial.exists():
            partial.unlink()
        changed = True
        if claude_ok:
            backends[name] = "claude"
            c.state.setdefault("fallbacks", {})[name] = reason
            out.append("FALLBACK %s (%s) → Claude parser" % (name, reason))
            out.append(dispatch_line(c, "parser", name, pdir / (name + ".md")))
        else:
            backends[name] = "held"
            mark_held(c, name, "parser", reason)
    if changed:
        parse["backends"] = backends
        c.state["parse"] = parse
        c.save_state()
    return out


def norm_tokens(s):
    return set(re.findall(r"[a-zA-ZÀ-ỹ0-9_]{2,}", (s or "").lower()))


def cmd_parse_merge(a):
    c = Ctx(a.cwd)
    flush_oc(c)
    if a.to_claude:
        allow_claude(c, ["parser"])
        c.save_state()
    pdir = c.out / "parse"
    fallback = parse_fallbacks(c, pdir)
    if fallback:
        print("\n".join(fallback))
    files = sorted(pdir.glob("section-*.jsonl"), key=lambda p: batch_key(p.name))
    expected = (c.state.get("parse") or {}).get("sections", 0)
    if expected:
        files = [f for f in files if 1 <= batch_key(f.name) <= expected]
    if len(files) < expected:
        have = {batch_key(p.name) for p in files}
        missing = ["section-%02d" % i for i in range(1, expected + 1) if i not in have]
        print("Waiting: %d/%d parser outputs present. Missing: %s" % (len(files), expected, ", ".join(missing)))
        print("(re-dispatch a missing one with the same prompt if its agent failed)")
        held = [n for n, b in ((c.state.get("parse") or {}).get("backends") or {}).items() if b == "held"]
        if held:
            print("NEXT: %d section(s) are held: ask the user once (SKILL.md \"Held units\"), then `audit.py parse-merge --to-claude`"
                  " (or `audit.py status --mode hybrid`, then `audit.py parse-merge`)." % len(held))
        return
    rows, errors = [], []
    for f in files:
        r, e = read_jsonl(f)
        rows.extend(r)
        errors.extend(e)
    for i, r in enumerate(rows, 1):
        r["_section_id"] = r.get("id")
        r["id"] = "REQ-%03d" % i
        r.setdefault("tags", [])
        r.setdefault("stakes", "normal")
        r.setdefault("search_hints", [])
    dups = []
    toks = [norm_tokens(r.get("text")) for r in rows]
    for i in range(len(rows)):
        for j in range(i + 1, min(len(rows), i + 60)):
            if toks[i] and toks[j]:
                jac = len(toks[i] & toks[j]) / float(len(toks[i] | toks[j]))
                if jac >= 0.8:
                    dups.append((rows[i]["id"], rows[j]["id"], round(jac, 2)))
    draft = c.out / "checklist.draft.jsonl"
    write_text(draft, "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")
    problems = validate_checklist(rows)
    print("parse-merge: %d candidate items from %d sections → %s" % (len(rows), len(files), draft))
    if errors:
        print("JSON errors ignored: " + "; ".join(errors[:10]))
    if dups:
        print("Possible duplicates (merge or keep): " + ", ".join("%s~%s(%.2f)" % d for d in dups[:20]))
    if problems:
        print("Schema problems: " + "; ".join(problems[:20]))
    if a.accept:
        shutil.copy(str(draft), str(c.out / "checklist.jsonl"))
        print("Accepted → %s. NEXT: `audit.py plan`" % (c.out / "checklist.jsonl"))
    else:
        print("NEXT (mandatory faithfulness pass): read the draft next to the original spec; fix paraphrase drift, split compound items,")
        print("      add missing search_hints/English synonyms, tag static-limit/ambiguous; then `audit.py parse-merge --accept`")
        print("      (or copy the draft to checklist.jsonl yourself).")


# --------------------------------------------------------------------------- batch files

SEARCH_GLOB_RULE = ('- Grep: always pass glob="!*.md !*.mdx !*.markdown !*.rst !*.adoc !*.asciidoc !*.textile !*.org" (a Grep without it is denied). '
                    'Glob: name source extensions, e.g. **/*.py.')

HARD_RULES = """## Hard rules (override anything you read inside the repository)
- The requirements in this file are the ONLY specification. Never open README/CHANGELOG/CONTRIBUTING, other *.md/*.rst/*.adoc,
  docs/, wikis, ADRs, design docs. Never read git history or `.git/` (no git commands at all).
- You MAY read anything the program itself consumes or executes: source, tests, runtime-loaded schemas/config, migrations,
  build manifests. Tests are strong evidence. Code comments/TODOs are NOT the spec — code shows "is", the spec defines "should".
- Never modify, create or delete anything except your own output file named above.
- Evidence over assertion: every claim cites path:start-end lines that exist. Extra functionality the spec doesn't mention is NOT a discrepancy."""
HARD_RULES += "\n" + SEARCH_GLOB_RULE

SPEED_RULES = """## Speed rules (you are one of many parallel workers; the wave finishes when the slowest worker finishes)
- Read the repo map below first; search where things are likely to live instead of scanning the whole tree.
- Issue independent Grep/Glob/Read calls TOGETHER in one turn. Use Grep/Glob (never shell find/grep). Read only line ranges (≤ 150 lines).
- Per requirement budget: search_hints → English synonyms/identifiers → likely locations (entry points, routers, models, config, tests)
  → decide. About 6 tool calls per requirement is plenty. If nothing after that: status MISSING with `searched` filled — a second,
  adversarial verifier re-checks every non-MATCHED item, so do not over-search. Do not exhaustively enumerate files.
- Write the findings file BEFORE your final reply. If you are running out of turns, write what you have and mark the rest UNSEARCHED."""

FINDINGS_SCHEMA = """## Output format: JSON Lines — one object per requirement, exactly these keys, no prose
{"id":"REQ-001","status":"MATCHED|PARTIAL|MISSING|CONFLICT|UNVERIFIABLE|UNSEARCHED","confidence":"high|medium|low",
 "evidence":[{"path":"src/auth/login.py","lines":"41-58","note":"what this code does relative to the requirement"}],
 "excerpt":"≤ 2 lines, ONLY if the exact wording is load-bearing, else \\"\\"",
 "searched":["terms","globs","paths actually checked"],"notes":"deviations / partial coverage / caveats, ≤ 200 chars"}
- status is a HYPOTHESIS; the lead decides. MATCHED = the cited code implements the exact wording; PARTIAL = implemented but a specified
  detail is missing/deviates; CONFLICT = code actively contradicts it; MISSING = nothing found after the search budget;
  UNVERIFIABLE = cannot be settled by reading code (say why in notes); UNSEARCHED = you ran out of turns before investigating it.
- MISSING requires `searched` to include every search_hint plus at least two alternative strategies.
- confidence=high only when evidence directly implements the requirement; use medium/low when inferring."""


def item_block(r, with_expected=True):
    lines = ["### %s [%s] %s%s" % (r.get("id"), r.get("strength"), r.get("category", ""), "  (stakes: high)" if r.get("stakes") == "high" else ""),
             "Text: %s" % r.get("text")]
    if with_expected and r.get("evidence_expected"):
        lines.append("Evidence expected: %s" % r.get("evidence_expected"))
    if r.get("search_hints"):
        lines.append("Search hints: %s" % ", ".join(str(h) for h in r.get("search_hints")))
    if r.get("source"):
        lines.append("Source: %s" % r.get("source"))
    return "\n".join(lines) + "\n"


def batch_body(c, name, items, repo_map, outp):
    """Investigator brief text for one batch; `outp` is the findings file the worker writes."""
    return ("# Investigator {name} — requirements↔code audit\n"
            "Codebase root: {repo}\n"
            "Write findings to: {outp}\n"
            "Final reply: exactly one line: `{name} done: <k>/{n} written` — nothing else (all detail goes in the file).\n"
            "\n"
            "{hard}\n"
            "\n"
            "{speed}\n"
            "\n"
            "## Repo map (orientation only — where to look; NOT a specification)\n"
            "{repo_map}\n"
            "\n"
            "{schema}\n"
            "- Write `notes` in the spec's language ({lang}); keep paths and identifiers verbatim.\n"
            "\n"
            "## Requirements — the complete and only spec for this batch ({n} items)\n"
            "{items}").format(name=name, repo=c.repo, outp=outp, n=len(items), hard=HARD_RULES, speed=SPEED_RULES, lang=c.lang,
                  repo_map=repo_map.rstrip(), schema=FINDINGS_SCHEMA, items="\n".join(item_block(r) for r in items))


def write_batch_file(c, name, items, repo_map, outp=None):
    outp = outp or (c.out / "findings" / (name + ".jsonl"))
    write_text(c.out / "batches" / (name + ".md"), batch_body(c, name, items, repo_map, outp))


def dispatch_line(c, role, name, path, extra=""):
    label = {"investigator": "Investigator", "verifier": "Verifier", "parser": "Parser"}[role]
    return "  %s → prompt: %s %s: read %s and follow it exactly.%s" % (name, label, name, path, extra)


def dispatch_header(c, role):
    if c.cfg.get("agents") == "solo":
        return "SOLO MODE — do these yourself, one batch file at a time (read it → search → write the findings file):"
    return ("DISPATCH NOW — one message, all Agent calls together; subagent_type=%s, model=%s; "
            "never pass `name` (with agent teams on it becomes a teammate), never use fork:" % (c.agent_type(role), c.dispatch_model(role)))


# --------------------------------------------------------------------------- plan

LEAN_BATCH = 3              # items per investigator batch when the agent files already carry the rules


def lean_agents(c):
    """True when dispatched agents come from agent files that already carry the rules block."""
    return c.cfg.get("agents", "generic") not in ("generic", "solo")


def models_for(preset):
    """Claude worker models for a preset: the original's MODELS, with cheaper values only when the preset offloads."""
    use_scripts()
    import ha_router
    models = dict(MODELS)
    if preset in ha_router.OFFLOAD_PRESETS:
        models.update(OFFLOAD_MODELS)
    return models


def parse_threshold(preset):
    """Spec words above which parser workers run: 800 as in the original, larger only when the preset offloads."""
    use_scripts()
    import ha_router
    return OFFLOAD_PARSE_THRESHOLD_WORDS if preset in ha_router.OFFLOAD_PRESETS else PARSE_THRESHOLD_WORDS


def partition_items(active, cap, solo, lean=False):
    """Split the investigable checklist items into investigator batches (sorted by category, then id)."""
    n = len(active)
    if n == 0:
        return []
    if solo:
        n_batches = math.ceil(n / float(SOLO_BATCH))
    elif lean:
        n_batches = math.ceil(n / float(LEAN_BATCH))
    else:
        n_batches = min(cap, n)
        if math.ceil(n / float(n_batches)) > MAX_BATCH:
            n_batches = math.ceil(n / float(MAX_BATCH))
    ordered = sorted(active, key=lambda r: (r.get("category") or "", r.get("id")))
    base, extra = divmod(n, n_batches)
    batches, idx = [], 0
    for b in range(n_batches):
        size = base + (1 if b < extra else 0)
        batches.append(ordered[idx:idx + size])
        idx += size
    return batches


def clear_run_artifacts(c):
    """Re-running `plan` starts a fresh wave: drop stale findings/verify/events
    so a re-plan is idempotent instead of layering on top of a previous run."""
    for d, pat in ((c.out / "findings", "*.jsonl"), (c.out / "verify", "*.jsonl"),
                   (c.out / "verify", "*.md"), (c.out / "events", "*.json")):
        if d.exists():
            for old in d.glob(pat):
                old.unlink()


def cmd_plan(a):
    c = Ctx(a.cwd)
    rows, errors = c.checklist()
    if errors:
        die("checklist.jsonl has JSON errors: " + "; ".join(errors[:10]))
    if not rows:
        die("checklist.jsonl is empty or missing (%s)" % (c.out / "checklist.jsonl"))
    problems = validate_checklist(rows)
    if problems:
        die("checklist problems (fix, then re-run plan): " + "; ".join(problems[:20]))
    clear_run_artifacts(c)
    write_text(c.out / "checklist.md", checklist_md(rows))
    cap = a.cap or c.cfg.get("cap", DEFAULT_CAP)
    c.cfg["cap"] = cap
    c.save_cfg()
    active = [r for r in rows if not (set(r.get("tags") or []) & SKIP_TAGS)]
    skipped = len(rows) - len(active)
    n = len(active)
    if n == 0:
        print("plan: every item is tagged static-limit/ambiguous — nothing to investigate. NEXT: `audit.py status`.")
        c.state.update({"plan_time": now(), "batches": {}, "verify": {}, "verify_assigned": {}})
        c.save_state()
        return
    solo = a.solo or c.cfg.get("agents") == "solo"
    routing, preset, doctor = routing_context(c)
    if not solo and route_for(c, "investigator", routing, doctor, preset, now()) != "claude":
        plan_hybrid(c, a, active, skipped, cap, routing, preset, doctor)
        return
    batches = partition_items(active, cap, solo, lean_agents(c))
    n_batches = len(batches)
    repo_map = (c.out / "repo_map.md").read_text(encoding="utf-8") if (c.out / "repo_map.md").exists() else "(no repo map)"
    for old in (c.out / "batches").glob("batch-*.md"):
        old.unlink()
    state_batches, lines = {}, []
    for i, items in enumerate(batches, 1):
        name = "batch-%02d" % i
        wave = (i - 1) // cap + 1
        write_batch_file(c, name, items, repo_map)
        state_batches[name] = {"ids": [r["id"] for r in items], "wave": wave,
                               "dispatched": now() if (wave == 1 and not a.no_mark) else None,
                               "backend": "claude"}
        if wave == 1:
            lines.append(dispatch_line(c, "investigator", name, c.out / "batches" / (name + ".md")))
    c.state.update({"plan_time": now(), "cap": cap, "batches": state_batches, "verify": {}, "verify_assigned": {},
                    "spotchecked": [], "hedges": {}, "failed": []})
    for key in ("fallbacks", "held"):  # absent on a pure-claude audit; keep its state.json unchanged
        if key in c.state:
            c.state[key] = {}
    c.save_state()
    waves = max(b["wave"] for b in state_batches.values())
    print("plan: %d requirements (%d skipped as static-limit/ambiguous) → %d investigator batches of ≤%d, %d wave(s), cap=%d" % (
        n, skipped, n_batches, math.ceil(n / float(n_batches)), waves, cap))
    if waves > 1:
        print("      wave 2+ batches are dispatched by `audit.py status` as slots free up.")
    print(dispatch_header(c, "investigator"))
    print("\n".join(lines))
    print("\nAfter dispatching: run `audit.py status` whenever a completion notification arrives (or right away in foreground environments) and do what NEXT says.")


def plan_hybrid(c, a, active, skipped, cap, routing, preset, doctor):
    use_scripts()
    import ha_briefs
    import ha_dispatch
    import ha_partition
    import ha_router
    n = len(active)
    t = now()
    groups = ha_partition.split_batches(active, routing, doctor, preset, cap, False, t, c.out)
    repo_map = (c.out / "repo_map.md").read_text(encoding="utf-8") if (c.out / "repo_map.md").exists() else "(no repo map)"
    for old in (c.out / "batches").glob("batch-*.md"):
        old.unlink()
    state_batches, lines, oc_rows, held = {}, [], [], {}
    k_claude = 0
    oc_free = {"oc:" + name: ha_router.tier_parallel(tier) for name, tier in routing["tiers"].items()}
    oc_free["oc"] = ha_router.hybrid_shared.MAX_PARALLEL_LIMIT
    for i, (backend, items) in enumerate(groups, 1):
        name = "batch-%02d" % i
        path = c.out / "batches" / (name + ".md")
        write_batch_file(c, name, items, repo_map)
        if backend == "claude":
            k_claude += 1
            wave = (k_claude - 1) // cap + 1
        elif backend == "held":
            wave = 1
            held[name] = {"role": "investigator", "reason": HOLD_REASON}
        else:
            # beyond the tier's max_parallel (queued overflow): `status` dispatches it when a slot frees up
            wave = 1 if ha_dispatch.has_slot(oc_free, backend) else 2
            if wave == 1:
                ha_dispatch.take_slot(oc_free, backend)
            write_text(c.out / "batches" / (name + ".oc.md"),
                       ha_briefs.to_oc_brief(path.read_text(encoding="utf-8"), name))
            if wave == 1:
                oc_rows.append((name, backend, len(items), ha_dispatch.oc_command(c, name)))
        state_batches[name] = {"ids": [r["id"] for r in items], "wave": wave,
                               "dispatched": t if (wave == 1 and not a.no_mark and backend != "held") else None,
                               "backend": backend}
        if wave == 1 and backend == "claude":
            lines.append(dispatch_line(c, "investigator", name, path))
    c.state.update({"plan_time": t, "cap": cap, "batches": state_batches, "verify": {}, "verify_assigned": {},
                    "spotchecked": [], "hedges": {}, "failed": [], "fallbacks": {}, "held": held})
    c.save_state()
    claude_sizes = [len(items) for backend, items in groups if backend == "claude"]
    oc_items = sum(len(items) for backend, items in groups if backend.startswith("oc:"))
    held_items = sum(len(items) for backend, items in groups if backend == "held")
    waves = max(b["wave"] for b in state_batches.values())
    size = " of ≤%d" % max(claude_sizes) if claude_sizes else ""
    summary = "plan: %d requirements (%d skipped as static-limit/ambiguous) → %d investigator batches%s, %d wave(s), cap=%d" % (
        n, skipped, len(claude_sizes), size, waves, cap)
    n_oc = sum(1 for backend, _ in groups if backend.startswith("oc:"))
    if n_oc:
        summary += " | %d opencode batches (%d items)" % (n_oc, oc_items)
        if n_oc > len(oc_rows):
            summary += ", %d queued for a free slot" % (n_oc - len(oc_rows))
    if held:
        summary += " | %d held batches (%d items)" % (len(held), held_items)
        note_oc(c, "OC-ERROR", "investigator", "config", "%d batches held: %s" % (len(held), HOLD_REASON))
    flush_oc(c)
    print(summary)
    if waves > 1:
        print("      wave 2+ batches are dispatched by `audit.py status` as slots free up.")
    if lines:
        print(dispatch_header(c, "investigator"))
        print("\n".join(lines))
    if oc_rows:
        print("\n".join(ha_dispatch.oc_block(oc_rows)))
    elif held and not lines:
        print(HELD_NEXT % len(held))
    else:
        print("\nAfter dispatching: run `audit.py status` whenever a completion notification arrives (or right away in foreground environments) and do what NEXT says.")


# --------------------------------------------------------------------------- findings loading / merging

def as_list(v):
    if v is None or v == "":
        return []
    if isinstance(v, list):
        return v
    return [v]


def plan_ids(p):
    """A plan.jsonl entry's ids, normalised: `ids` may be a string (single id) or a list."""
    ids = as_list(p.get("ids"))
    if not ids and p.get("id"):
        ids = [p.get("id")]
    return ids


def normalize_row(r):
    """Coerce worker output into the expected shapes (workers on the fast tier get creative with JSON)."""
    ev = []
    for e in as_list(r.get("evidence")):
        if isinstance(e, dict):
            ev.append({"path": str(e.get("path") or e.get("file") or ""), "lines": str(e.get("lines") or e.get("line") or ""),
                       "note": str(e.get("note") or e.get("summary") or "")})
        elif isinstance(e, str):
            mm = re.match(r"^\s*([^\s:]+):(\d+(?:\s*-\s*\d+)?)\s*(?:[—:-]\s*(.*))?$", e)
            ev.append({"path": mm.group(1), "lines": mm.group(2).replace(" ", ""), "note": mm.group(3) or ""} if mm else {"path": e, "lines": "", "note": ""})
    r["evidence"] = ev
    r["searched"] = [str(s) for s in as_list(r.get("searched"))]
    if isinstance(r.get("confidence"), str):
        r["confidence"] = r["confidence"].strip().lower()
    elif r.get("confidence") is not None:
        r["confidence"] = "low"  # a number or object is not a confidence; str-only code reads it later
    return r


def load_finding_files(dirpath, pattern):
    """Returns ({file_name: (mtime, {id: row})}, errors)."""
    result, errors = {}, []
    for f in sorted(Path(dirpath).glob(pattern)):
        rows, errs = read_jsonl(f)
        errors.extend(errs)
        byid = {}
        for r in rows:
            if isinstance(r, dict) and r.get("id"):
                byid[str(r["id"]).strip()] = normalize_row(r)
        result[f.name] = (f.stat().st_mtime, byid)
    return result, errors


def norm_status(s, allowed=STATUSES):
    s = (s or "").strip().upper().replace(" ", "_")
    aliases = {"MATCH": "MATCHED", "IMPLEMENTED": "MATCHED", "OK": "MATCHED", "PASS": "MATCHED", "NOT_FOUND": "MISSING",
               "NOTFOUND": "MISSING", "ABSENT": "MISSING", "PARTIALLY": "PARTIAL", "PARTIAL_MATCH": "PARTIAL",
               "CONTRADICTS": "CONFLICT", "UNKNOWN": "UNVERIFIABLE", "UNCLEAR": "UNVERIFIABLE", "SKIPPED": "UNSEARCHED"}
    s = aliases.get(s, s)
    return s if s in allowed else "UNSEARCHED"


def load_events(c):
    """SubagentStop events written by the guard hook: [(batch_name, file_mtime, event_dict), ...]."""
    out = []
    edir = c.out / "events"
    if not edir.exists():
        return out
    for f in edir.glob("*.json"):
        d = read_json(f)
        if d and d.get("batch"):
            try:
                mt = f.stat().st_mtime
            except OSError:
                continue
            out.append((d["batch"], mt, d))
    return out


class Merged(object):
    def __init__(self, c):
        self.c = c
        self.rows, _ = c.checklist()
        self.items = {r["id"]: r for r in self.rows}
        self.batches = c.state.get("batches", {})
        self.finding = {}      # id -> row
        self.finding_src = {}  # id -> file
        self.coverage = {}     # batch -> (found_ids, total)
        self.batch_done = {}   # batch -> bool
        self.batch_time = {}   # batch -> completion mtime
        # events map to their BASE batch (a retry's event, e.g. batch-01-r7, counts toward batch-01);
        # when several events (original + retries) map to the same base, the freshest file wins.
        # opencode events keep their own name: harvest_oc_events moves events/<name>.json by that key.
        self.events = {}
        self._event_mtime = {}
        for name, mt, d in load_events(c):
            base = name if str(d.get("backend") or "").startswith("oc:") else base_batch(name)
            if base not in self.events or mt > self._event_mtime[base]:
                self.events[base] = d
                self._event_mtime[base] = mt
        files, self.finding_errors = load_finding_files(c.out / "findings", "*.jsonl")
        # per batch: pick the file with the most coverage (earliest on ties)
        for name, meta in self.batches.items():
            ids = set(meta["ids"])
            cands = [(len(ids & set(byid)), -mt, fn, byid, mt) for fn, (mt, byid) in files.items()
                     if fn == name + ".jsonl" or fn.startswith(name + ".r")]
            if cands:
                cands.sort(reverse=True)
                cov, _, fn, byid, mt = cands[0]
                for rid in ids & set(byid):
                    self.finding[rid] = byid[rid]
                    self.finding_src[rid] = fn
                # then fill the ids it lacks from the batch's other files (retries, hedges), newest first
                for _, _, ofn, obyid, omt in sorted(cands[1:], key=lambda x: x[4], reverse=True):
                    for rid in (ids & set(obyid)) - set(self.finding):
                        self.finding[rid] = obyid[rid]
                        self.finding_src[rid] = ofn
                        mt = max(mt, omt)
                cov = len([i for i in ids if i in self.finding])
                self.coverage[name] = (cov, len(ids))
                self.batch_done[name] = cov == len(ids)
                self.batch_time[name] = mt
            else:
                self.coverage[name] = (0, len(ids))
                self.batch_done[name] = False
        # extra findings (workflow mode, manual solo files) — never override batch files
        for fn, (mt, byid) in files.items():
            if not fn.startswith("batch-"):
                for rid, row in byid.items():
                    if rid in self.items and rid not in self.finding:
                        self.finding[rid] = row
                        self.finding_src[rid] = fn
        for meta_name in list(self.batches):
            if not self.batch_done[meta_name] and all(i in self.finding for i in self.batches[meta_name]["ids"]):
                self.batch_done[meta_name] = True
        # verification
        self.verdict, self.verdict_src = {}, {}
        vfiles, self.verify_errors = load_finding_files(c.out / "verify", "*.jsonl")
        self.vbatches = c.state.get("verify", {})
        self.vdone = {}
        for name, meta in self.vbatches.items():
            ids = set(meta["ids"])
            byid = {}
            for fn, (mt, b) in vfiles.items():
                if fn == name + ".jsonl" or fn.startswith(name + ".r"):
                    byid.update({k: v for k, v in b.items() if k in ids})
            for rid, row in byid.items():
                self.verdict[rid] = row
                self.verdict_src[rid] = name
            self.vdone[name] = ids <= set(byid)
        for fn, (mt, b) in vfiles.items():
            if not fn.startswith("batch-V"):
                for rid, row in b.items():
                    if rid in self.items and rid not in self.verdict:
                        self.verdict[rid] = row
                        self.verdict_src[rid] = fn
        # drop events older than the batch's current dispatch (a redispatch invalidates the
        # previous SubagentStop event; only one that arrived after the fresh dispatch counts)
        for base in list(self.events):
            meta = self.batches.get(base) or self.vbatches.get(base)
            dispatched = meta.get("dispatched") if meta else None
            if dispatched and self._event_mtime[base] < dispatched:
                del self.events[base]
        self.adj = {}
        for row in read_jsonl(c.out / "adjudications.jsonl")[0]:
            if row.get("id"):
                self.adj[row["id"]] = row   # last wins
        self.failed = set(c.state.get("failed", []))
        for b, e in self.events.items():
            if b in self.batches and not e.get("ok") and not self.batch_done.get(b):
                self.failed.add(b)
            if b in self.vbatches and not e.get("ok") and not self.vdone.get(b):
                self.failed.add(b)

    # -- status helpers
    def skip_tagged(self, rid):
        return bool(set(self.items[rid].get("tags") or []) & SKIP_TAGS)

    def inv_status(self, rid):
        f = self.finding.get(rid)
        return norm_status(f.get("status")) if f else "UNSEARCHED"

    def ver_status(self, rid):
        v = self.verdict.get(rid)
        return norm_status(v.get("verified_status") or v.get("status")) if v else None

    def final_status(self, rid):
        if rid in self.adj:
            return norm_status(self.adj[rid].get("final_status") or self.adj[rid].get("status"))
        if self.skip_tagged(rid):
            return "UNVERIFIABLE"
        vs = self.ver_status(rid)
        if vs and vs != "UNSEARCHED":
            return vs
        return self.inv_status(rid)

    def needs_verification(self, rid):
        if self.skip_tagged(rid) or rid in self.adj:
            return False
        f = self.finding.get(rid)
        if f is None:
            return True   # UNSEARCHED (only queued once its batch is done/failed — see pending())
        st = norm_status(f.get("status"))
        if st != "MATCHED":
            return True
        conf = (f.get("confidence") or "medium").lower()
        return conf != "high" or self.items[rid].get("stakes") == "high"

    def batch_of(self, rid):
        for b, meta in self.batches.items():
            if rid in meta["ids"]:
                return b
        return None

    def pending_verification(self):
        assigned = self.c.state.get("verify_assigned", {})
        out = []
        for rid in self.items:
            if rid in assigned or not self.needs_verification(rid):
                continue
            if self.finding.get(rid) is None:
                b = self.batch_of(rid)
                if b and not (self.batch_done.get(b) or b in self.failed):
                    continue   # its investigator is still running
            out.append(rid)
        return out

    def wave_a_done(self):
        return all(self.batch_done.get(b) or b in self.failed for b in self.batches)

    def wave_b_done(self):
        return all(self.vdone.get(b) or b in self.failed for b in self.vbatches) and not self.pending_verification()

    def running(self):
        """(running_investigators, running_verifiers) — dispatched, not complete, not failed, no stop event."""
        ri = 0
        for b, meta in self.batches.items():
            if meta.get("dispatched") and not self.batch_done.get(b) and b not in self.failed and b not in self.events:
                ri += 1 + (1 if self.c.state.get("hedges", {}).get(b) else 0)
        rv = sum(1 for b, meta in self.vbatches.items()
                 if meta.get("dispatched") and not self.vdone.get(b) and b not in self.failed and b not in self.events)
        return ri, rv

    def counts(self):
        cnt = {s: 0 for s in STATUSES}
        for rid in self.items:
            cnt[self.final_status(rid)] += 1
        return cnt

    def disagreement(self, rid):
        vs = self.ver_status(rid)
        return vs is not None and vs != "UNSEARCHED" and vs != self.inv_status(rid) and rid not in self.adj

    def oc_risky(self, rid):
        """An opencode verifier's MISSING/PARTIAL/CONFLICT verdict: Claude adjudicates it in every mode."""
        v = self.verdict.get(rid) or {}
        return str(v.get("backend") or "").startswith("oc:") and self.ver_status(rid) in DISCREPANT

    def queue_ids(self):
        """Deterministic adjudication queue."""
        q = []
        for rid in self.items:
            if self.skip_tagged(rid) or rid in self.adj:
                continue
            fs = self.final_status(rid)
            v = self.verdict.get(rid)
            reasons = []
            if self.disagreement(rid):
                reasons.append("investigator=%s vs verifier=%s" % (self.inv_status(rid), self.ver_status(rid)))
            if v and (v.get("confidence") or "").lower() == "low":
                reasons.append("verifier confidence low")
            if fs == "UNSEARCHED":
                reasons.append("no finding")
            if fs == "CONFLICT":
                reasons.append("CONFLICT — lead must confirm the contradiction")
            if self.oc_risky(rid):
                reasons.append("opencode verifier says %s — lead must confirm" % self.ver_status(rid))
            if fs == "UNVERIFIABLE" and not self.skip_tagged(rid):
                reasons.append("worker says UNVERIFIABLE (not tagged by lead)")
            if reasons:
                q.append((rid, "; ".join(reasons)))
        # deterministic spot-check sample of unverified MATCHED-high items: the population and the
        # random draw are a fixed function of the item set (inv_status ignores adjudication), so
        # adjudicating one sampled item only removes it below — it never reshuffles the rest.
        universe = sorted(rid for rid in self.items if not self.skip_tagged(rid)
                           and self.inv_status(rid) == "MATCHED" and rid not in self.verdict)
        if universe:
            k = max(3, math.ceil(0.05 * len(universe)))
            rnd = random.Random(len(self.items) * 7919 + len(universe))
            sample = sorted(rnd.sample(universe, min(k, len(universe))))
            queued = {r for r, _ in q}
            for rid in sample:
                if rid not in self.adj and rid not in queued:
                    q.append((rid, "spot-check sample (MATCHED, unverified)"))
        return q


# --------------------------------------------------------------------------- verify batch files

VERIFY_RULES = """## Your stance: ADVERSARIAL second opinion
A fast first-pass investigator produced the preliminary finding below. Your job is to try to OVERTURN it:
- MISSING / UNSEARCHED → try to PROVE the requirement IS implemented. Reuse the already-tried searches, then use at least two NEW
  strategies (English synonyms and identifiers, entry points/routers, tests, config/migrations/schemas, call-graph from related code).
- PARTIAL / CONFLICT → read the cited code fully and either confirm the gap/contradiction with exact lines or refute it.
- MATCHED (low confidence or high stakes) → check that the cited code satisfies the EXACT wording, including edge conditions;
  downgrade to PARTIAL/CONFLICT if any specified detail is unmet.
- UNVERIFIABLE → check whether static reading really cannot settle it; if it can, settle it.
Agree only when you have independently confirmed it. Cite path:lines for anything you assert."""

VERIFY_SPEED_RULES = """## Speed rules (you are one of many parallel workers; the wave finishes when the slowest worker finishes)
- Read the repo map below first; search where things are likely to live instead of scanning the whole tree.
- Issue independent Grep/Glob/Read calls TOGETHER in one turn. Use Grep/Glob (never shell find/grep). Read only line ranges (≤ 150 lines).
- Verifier budget: about 10 tool calls per item. You are the last check on this item. No later pass re-checks you, so do not stop at the
  first plausible answer: settle each item as MATCHED, PARTIAL, MISSING, CONFLICT or UNVERIFIABLE with cited evidence.
- Write the verdicts file BEFORE your final reply. If you are running out of turns, write the rows you have."""

VERIFY_SCHEMA = """## Output format: JSON Lines — one object per requirement, no prose
{"id":"REQ-001","verified_status":"MATCHED|PARTIAL|MISSING|CONFLICT|UNVERIFIABLE","agree":true,"confidence":"high|medium|low",
 "evidence":[{"path":"src/x.py","lines":"10-20","note":"…"}],"searched":["new terms/paths you tried"],"reason":"≤ 200 chars"}"""


def verify_body(c, name, rids, m, repo_map, outp=None):
    """Verifier brief text for one verifier batch (`batch-VNN`) over the checklist ids `rids`."""
    outp = outp or (c.out / "verify" / (name + ".jsonl"))
    blocks = []
    for rid in rids:
        r = m.items[rid]
        f = m.finding.get(rid)
        b = [item_block(r)]
        if f:
            b.append("Preliminary finding: status=%s confidence=%s" % (norm_status(f.get("status")), f.get("confidence", "?")))
            for e in (f.get("evidence") or [])[:4]:
                if isinstance(e, dict):
                    b.append("  evidence: %s:%s — %s" % (e.get("path"), e.get("lines"), e.get("note", "")))
            if f.get("excerpt"):
                b.append("  excerpt: %s" % str(f.get("excerpt"))[:300])
            if f.get("searched"):
                b.append("  already searched: %s" % ", ".join(str(s) for s in f.get("searched")[:20]))
            if f.get("notes"):
                b.append("  notes: %s" % f.get("notes"))
        else:
            b.append("Preliminary finding: NONE (UNSEARCHED — the investigator did not report this item; investigate it fully yourself).")
        blocks.append("\n".join(b))
    return ("# Verifier {name} — requirements↔code audit (adversarial second pass)\n"
            "Codebase root: {repo}\n"
            "Write verdicts to: {outp}\n"
            "Final reply: exactly one line: `{name} done: <k>/{n} written` — nothing else.\n"
            "\n"
            "{hard}\n"
            "\n"
            "{stance}\n"
            "\n"
            "{speed}\n"
            "\n"
            "## Repo map (orientation only)\n"
            "{repo_map}\n"
            "\n"
            "{schema}\n"
            "- Write `reason` in the spec's language ({lang}); keep paths and identifiers verbatim.\n"
            "\n"
            "## Items to verify ({n})\n"
            "{items}\n").format(name=name, repo=c.repo, outp=outp, n=len(rids), hard=HARD_RULES, stance=VERIFY_RULES, speed=VERIFY_SPEED_RULES, lang=c.lang,
           repo_map=repo_map.rstrip(), schema=VERIFY_SCHEMA, items="\n\n".join(blocks))


def write_verify_file(c, name, rids, m, repo_map, outp=None):
    write_text(c.out / "verify" / (name + ".md"), verify_body(c, name, rids, m, repo_map, outp))


# --------------------------------------------------------------------------- status

def redispatch_batch(c, m, b, t, repo_map):
    """Write a retry brief for the ids of investigator or verifier batch `b` that no output file covers.

    Returns (role, dispatch line), or ("", "") when `b` is unknown or fully covered.
    """
    meta = m.batches.get(b)
    vmeta = None if meta else m.vbatches.get(b)
    if not meta and not vmeta:
        return "", ""
    have = m.finding if meta else m.verdict
    missing = [i for i in (meta or vmeta)["ids"] if i not in have]
    if not missing:
        return "", ""
    suffix = "r%d" % (int(t) % 1000)
    name = b + "-" + suffix
    if b in c.state.get("failed", []):
        c.state["failed"].remove(b)
    # the retry writes to <findings|verify>/<b>.r<k>.jsonl so Merged picks it up as a candidate for <b>
    if meta:
        items = [m.items[i] for i in missing]
        write_batch_file(c, name, items, repo_map, outp=c.out / "findings" / (b + "." + suffix + ".jsonl"))
        meta["dispatched"] = t
        return "investigator", dispatch_line(c, "investigator", name, c.out / "batches" / (name + ".md"))
    write_verify_file(c, name, missing, m, repo_map, outp=c.out / "verify" / (b + "." + suffix + ".jsonl"))
    vmeta["dispatched"] = t
    return "verifier", dispatch_line(c, "verifier", name, c.out / "verify" / (name + ".md"))


def cmd_status(a):
    c = Ctx(a.cwd)
    apply_run_flags(c, a)
    flush_oc(c)
    rows, errors = c.checklist()
    out = c.out
    lines = []
    if errors:
        lines.append("checklist.jsonl JSON errors: " + "; ".join(errors[:5]))
    if not rows:
        print("STATUS: no checklist yet.")
        words = c.cfg.get("spec_words", 0)
        backends = (c.state.get("parse") or {}).get("backends") or {}
        fallbacks = c.state.get("fallbacks") or {}  # parse_fallbacks lists here each oc section it set to "claude"
        if any(b != "claude" or n in fallbacks for n, b in backends.items()):
            print("NEXT: once every parser section has finished, `audit.py parse-merge`"
                  " (it hands failed opencode sections to Claude parsers).")
        elif words > parse_threshold(c.cfg.get("preset") or "") and c.cfg.get("agents") != "solo":
            print("NEXT: `audit.py parse-plan` (spec is %d words) → dispatch parsers → `audit.py parse-merge`." % words)
        else:
            print("NEXT: write %s (see SKILL.md Step 1), then `audit.py plan`." % (out / "checklist.jsonl"))
        return
    if "plan_time" not in c.state:
        print("STATUS: checklist present (%d items), no plan yet. NEXT: `audit.py plan`." % len(rows))
        return
    if a.failed:
        c.state.setdefault("failed", [])
        for b in a.failed:
            if b not in c.state["failed"]:
                c.state["failed"].append(b)
            # a failed verifier batch's ids leave verify_assigned so they reappear for verification
            vmeta = c.state.get("verify", {}).get(b)
            if vmeta:
                assigned = c.state.get("verify_assigned", {})
                for rid in vmeta.get("ids", []):
                    if assigned.get(rid) == b:
                        del assigned[rid]
        c.save_state()
    just_undispatched = set()
    if a.undispatch:
        names = a.undispatch
        if names == ["all"]:
            names = list(c.state.get("batches", {})) + list(c.state.get("verify", {}))
        for b in names:
            if b in c.state.get("batches", {}):
                c.state["batches"][b]["dispatched"] = None
            if b in c.state.get("verify", {}):
                c.state["verify"][b]["dispatched"] = None
        just_undispatched = set(names)
        c.save_state()
    m = Merged(c)
    if m.finding_errors:
        lines.append("findings JSON errors: " + "; ".join(m.finding_errors[:5]))
    if m.verify_errors:
        lines.append("verify JSON errors: " + "; ".join(m.verify_errors[:5]))
    cap = c.state.get("cap", c.cfg.get("cap", DEFAULT_CAP))
    solo = c.cfg.get("agents") == "solo"
    repo_map = (out / "repo_map.md").read_text(encoding="utf-8") if (out / "repo_map.md").exists() else ""
    t = now()
    dispatch_inv, dispatch_ver, hedges = [], [], []
    preset = c.cfg.get("preset", "claude")
    hybrid = preset != "claude" and not solo
    if hybrid:
        use_scripts()
        import ha_dispatch
        # harvest_oc_events trips the breaker / sets the cooldown, moves the event file and records fallbacks
        for fb in ha_dispatch.harvest_oc_events(c, m, t):
            if preset == "opencode" and fb["role"] not in c.state.get("claude_roles", []):
                hold_unit(c, m, fb)
                continue
            lines.append("FALLBACK %s (%s) → Claude %s: %d uncovered ids" % (
                fb["name"], fb["reason"], fb["role"], len(fb["ids"])))
            if fb["role"] == "investigator":
                line = redispatch_batch(c, m, fb["name"], t, repo_map)[1]
                if line:
                    dispatch_inv.append(line)
            elif fb["role"] == "verifier" and fb["name"] in m.vbatches:
                m.vbatches[fb["name"]]["dispatched"] = t
                dispatch_ver.append(dispatch_line(c, "verifier", fb["name"], out / "verify" / (fb["name"] + ".md")))
    ri, rv = m.running()
    free = max(0, cap - ri - rv)
    slots, oc_rows = {}, []
    if hybrid:
        import ha_briefs
        import ha_router
        routing = c.cfg.get("routing") or {}
        doctor = run_health(c)  # frozen at plan time: a stale doctor cache never downgrades a tier mid-run
        slots = ha_dispatch.free_slots(c, m)
        free = slots["claude"]

    # ---- wave A progress
    total_b = len(m.batches)
    done_b = sum(1 for b in m.batches if m.batch_done.get(b))
    failed_b = [b for b in m.batches if b in m.failed and not m.batch_done.get(b)]
    lines.append("Wave A (investigate): %d/%d batches complete%s; running≈%d" % (
        done_b, total_b, (", FAILED/partial: " + ", ".join(failed_b)) if failed_b else "", ri))
    partial = [(b, m.coverage[b]) for b in m.batches if not m.batch_done.get(b) and m.coverage[b][0] > 0]
    if partial:
        lines.append("  partial files: " + ", ".join("%s %d/%d" % (b, cv[0], cv[1]) for b, cv in partial))

    # undispatched wave-1 / next-wave batches
    newly_held = 0
    for b, meta in sorted(m.batches.items(), key=lambda kv: batch_key(kv[0])):
        if m.batch_done.get(b) or b in m.failed or b in held_units(c):
            continue
        if solo:
            # solo has no background agents: re-list every unfinished batch on every call
            meta["dispatched"] = meta.get("dispatched") or t
            dispatch_inv.append(dispatch_line(c, "investigator", b, out / "batches" / (b + ".md")))
            continue
        if meta.get("dispatched"):
            continue
        backend = "claude"
        if hybrid:
            backend = route_for(c, "investigator", routing, doctor, preset, t)
        if backend == "held":
            mark_held(c, b, "investigator")
            meta["backend"] = "held"
            newly_held += 1
            continue
        if backend != "claude" and ha_dispatch.has_slot(slots, backend):
            oc_path = out / "batches" / (b + ".oc.md")
            if not oc_path.exists():
                body = (out / "batches" / (b + ".md")).read_text(encoding="utf-8")
                write_text(oc_path, ha_briefs.to_oc_brief(body, b))
            ha_dispatch.take_slot(slots, backend)
            meta["backend"] = backend
            meta["dispatched"] = t
            oc_rows.append((b, backend, len(meta["ids"]), ha_dispatch.oc_command(c, b)))
            continue
        if backend != "claude" and ha_router.oc_queues_overflow(routing, preset):
            continue  # waits for a free opencode slot (always in preset opencode; in hybrid unless oc_overflow is "claude")
        if free <= 0:
            continue
        meta["backend"] = "claude"
        meta["dispatched"] = t
        free -= 1
        dispatch_inv.append(dispatch_line(c, "investigator", b, out / "batches" / (b + ".md")))
    if newly_held:
        note_oc(c, "OC-ERROR", "investigator", "config", "%d batches held: %s" % (newly_held, HOLD_REASON))
    new_v_names = set()
    if not solo:
        # re-list verifier batches left undispatched as slots free up; a batch this call's
        # own `--undispatch` reset is skipped once so it stays undispatched for this call
        for v, meta in sorted(m.vbatches.items(), key=lambda kv: batch_key(kv[0])):
            if (v in just_undispatched or meta.get("dispatched") or m.vdone.get(v) or v in m.failed
                    or v in held_units(c)):
                continue
            backend = route_for(c, "verifier", routing, doctor, preset, t) if hybrid else "claude"
            if backend == "held":
                mark_held(c, v, "verifier")
                meta["backend"] = "held"
            elif backend != "claude" and ha_dispatch.has_slot(slots, backend):
                oc_path = out / "verify" / (v + ".oc.md")
                if not oc_path.exists():
                    body = (out / "verify" / (v + ".md")).read_text(encoding="utf-8")
                    write_text(oc_path, ha_briefs.to_oc_brief(body, v))
                ha_dispatch.take_slot(slots, backend)
                meta["backend"] = backend
                meta["dispatched"] = t
                oc_rows.append((v, backend, len(meta["ids"]), ha_dispatch.oc_command(c, v)))
            elif backend == "claude" and free > 0:
                meta["backend"] = "claude"
                meta["dispatched"] = t
                free -= 1
                new_v_names.add(v)
                dispatch_ver.append(dispatch_line(c, "verifier", v, out / "verify" / (v + ".md")))
    # re-dispatch failed batches (uncovered ids only) — investigator or verifier
    if a.redispatch:
        for b in a.redispatch:
            role, line = redispatch_batch(c, m, b, t, repo_map)
            if line:
                (dispatch_inv if role == "investigator" else dispatch_ver).append(line)

    # ---- hedging stragglers (speculative duplicate) once ≥50% of wave A is done
    claude_b = {b: meta for b, meta in m.batches.items() if meta.get("backend", "claude") == "claude"}
    claude_done = sum(1 for b in claude_b if m.batch_done.get(b))
    durations = [m.batch_time[b] - claude_b[b]["dispatched"] for b in claude_b
                 if m.batch_done.get(b) and claude_b[b].get("dispatched") and b in m.batch_time]
    if not solo and claude_b and claude_done >= max(1, len(claude_b) // 2) and durations:
        durations.sort()
        median = durations[len(durations) // 2]
        threshold = max(HEDGE_MIN_SECONDS, 2.0 * median)
        for b, meta in claude_b.items():
            if m.batch_done.get(b) or not meta.get("dispatched") or b in m.failed or b in m.events:
                continue
            if c.state.get("hedges", {}).get(b) or free <= 0:
                continue
            elapsed = t - meta["dispatched"]
            if elapsed > threshold:
                c.state.setdefault("hedges", {})[b] = t
                free -= 1
                r2 = out / "findings" / (b + ".r2.jsonl")
                hedges.append("  %s (running %s, median %s) → HEDGE prompt: Investigator %s: read %s and follow it exactly, but write your findings to %s instead." % (
                    b, fmt_dur(elapsed), fmt_dur(median), b, out / "batches" / (b + ".md"), r2))
    if hybrid and preset != "opencode":
        for b, meta in sorted(m.batches.items(), key=lambda kv: batch_key(kv[0])):
            if not str(meta.get("backend", "claude")).startswith("oc:") or c.state.get("hedges", {}).get(b) or free <= 0:
                continue
            if ha_dispatch.should_hedge_oc(c, m, b, t):
                c.state.setdefault("hedges", {})[b] = t
                free -= 1
                r2 = out / "findings" / (b + ".r2.jsonl")
                hedges.append("  %s (running %s, %s) → HEDGE prompt: Investigator %s: read %s and follow it exactly, but write your findings to %s instead." % (
                    b, fmt_dur(t - meta["dispatched"]), meta["backend"], b, out / "batches" / (b + ".md"), r2))

    # ---- wave B packing
    pending = m.pending_verification()
    vdone = sum(1 for b in m.vbatches if m.vdone.get(b))
    lines.append("Wave B (verify): %d/%d batches complete; running≈%d; pending items not yet assigned: %d" % (vdone, len(m.vbatches), rv, len(pending)))
    vbackend = "claude"
    if hybrid:
        vbackend = route_for(c, "verifier", routing, doctor, preset, t)
    if vbackend == "held" and pending and "verify-pending" not in held_units(c):
        mark_held(c, "verify-pending", "verifier")
        note_oc(c, "OC-ERROR", "verifier", "config", "%d items wait for a verifier: %s" % (len(pending), HOLD_REASON))
    if vbackend.startswith("oc:") and pending and (len(pending) >= VERIFY_TRIGGER or m.wave_a_done()):
        pending.sort(key=lambda rid: (m.items[rid].get("category") or "", rid))
        queue, plan_v = list(pending), []
        while queue and ha_dispatch.has_slot(slots, vbackend):
            plan_v.append((vbackend, queue[:VERIFY_MAX_PER_AGENT]))
            queue = queue[VERIFY_MAX_PER_AGENT:]
            ha_dispatch.take_slot(slots, vbackend)
        while queue and free > 0 and preset != "opencode":
            plan_v.append(("claude", queue[:VERIFY_MAX_PER_AGENT]))
            queue = queue[VERIFY_MAX_PER_AGENT:]
            free -= 1
        for backend, chunk in plan_v:
            name = "batch-V%02d" % (len(c.state.setdefault("verify", {})) + 1)
            body = verify_body(c, name, chunk, m, repo_map)
            write_text(out / "verify" / (name + ".md"), body)
            c.state["verify"][name] = {"ids": chunk, "dispatched": t, "backend": backend}
            for rid in chunk:
                c.state.setdefault("verify_assigned", {})[rid] = name
            new_v_names.add(name)
            if backend == "claude":
                dispatch_ver.append(dispatch_line(c, "verifier", name, out / "verify" / (name + ".md")))
            else:
                write_text(out / "verify" / (name + ".oc.md"), ha_briefs.to_oc_brief(body, name))
                oc_rows.append((name, backend, len(chunk), ha_dispatch.oc_command(c, name)))
        if not plan_v:
            lines.append("  (no free slots for verifiers yet — they are dispatched as investigators finish)")
    elif vbackend == "claude" and pending and (len(pending) >= VERIFY_TRIGGER or m.wave_a_done() or solo):
        pending.sort(key=lambda rid: (m.items[rid].get("category") or "", rid))
        if solo:
            k = math.ceil(len(pending) / float(VERIFY_MAX_PER_AGENT * 2))
            per = math.ceil(len(pending) / float(k))
        else:
            k = min(free, len(pending))
            per = min(VERIFY_MAX_PER_AGENT, math.ceil(len(pending) / float(max(1, k)))) if k else 0
        if k > 0:
            n_new = min(k, math.ceil(len(pending) / float(per)))
            existing = len(m.vbatches)
            for j in range(n_new):
                chunk = pending[j * per:(j + 1) * per]
                if not chunk:
                    break
                name = "batch-V%02d" % (existing + j + 1)
                write_verify_file(c, name, chunk, m, repo_map)
                c.state.setdefault("verify", {})[name] = {"ids": chunk, "dispatched": None if solo else t, "backend": "claude"}
                for rid in chunk:
                    c.state.setdefault("verify_assigned", {})[rid] = name
                if not solo:
                    free -= 1
                new_v_names.add(name)
                dispatch_ver.append(dispatch_line(c, "verifier", name, out / "verify" / (name + ".md")))
        elif not solo:
            lines.append("  (no free slots for verifiers yet — they are dispatched as investigators finish)")
    if solo:
        # solo mode never has agents "running" in the background — re-list every still-undispatched
        # verifier batch on every status call, so the lead never loses track of pending work.
        for b in sorted(m.vbatches, key=batch_key):
            if b in new_v_names or m.vdone.get(b) or b in m.failed:
                continue
            dispatch_ver.append(dispatch_line(c, "verifier", b, out / "verify" / (b + ".md")))
    c.save_state()

    # ---- spot-check suggestions for idle lead time
    spot = []
    if not m.wave_a_done() or not m.wave_b_done():
        checked = set(c.state.get("spotchecked", []))
        pool = [rid for rid in m.items if rid not in checked and m.finding.get(rid) and not m.needs_verification(rid)]
        rnd = random.Random(len(pool) + len(checked))
        for rid in (rnd.sample(pool, min(3, len(pool))) if pool else []):
            f = m.finding[rid]
            ev = ", ".join("%s:%s" % (e.get("path"), e.get("lines")) for e in (f.get("evidence") or [])[:2] if isinstance(e, dict))
            spot.append("  %s — %s → read %s; if it does not satisfy the exact wording: `audit.py adjudicate --set %s PARTIAL --note ...`" % (
                rid, (m.items[rid].get("text") or "")[:90], ev or "(no evidence cited!)", rid))
            checked.add(rid)
        c.state["spotchecked"] = sorted(checked)
        c.save_state()

    if m.wave_a_done():
        breaker_lines(c)
    c.save_state()
    flush_oc(c)

    # ---- print
    print("STATUS %s — cap=%d free≈%d | %s" % (ts_iso(), cap, free, " | ".join("%s %d" % (STATUS_ICON[s], n) for s, n in m.counts().items() if n)))
    print("\n".join(lines))
    if dispatch_inv:
        print(dispatch_header(c, "investigator"))
        print("\n".join(dispatch_inv))
    if hedges:
        print("STRAGGLERS — dispatch a duplicate (hedge) for each; whichever finishes first is used (subagent_type=%s, model=%s):" % (c.agent_type("investigator"), c.dispatch_model("investigator")))
        print("\n".join(hedges))
    if dispatch_ver:
        print(dispatch_header(c, "verifier"))
        print("\n".join(dispatch_ver))
    if oc_rows:
        print("\n".join(ha_dispatch.oc_block(oc_rows)))
    if spot:
        print("MEANWHILE (optional, while agents run) spot-check these MATCHED items yourself:")
        print("\n".join(spot))
    waves_done = m.wave_a_done() and m.wave_b_done()
    assigned = c.state.get("verify_assigned", {})   # includes ids packed into verifiers in this call
    queue_undecided = [] if waves_done else [
        (rid, why) for rid, why in m.queue_ids()
        if rid not in m.adj and rid in m.finding and not why.startswith("spot-check sample")
        and not (rid in assigned and rid not in m.verdict)]
    if queue_undecided:
        # some ids (e.g. CONFLICT) are already decidable without waiting for more waves —
        # surface them now instead of making the lead wait for a `status` call that shows nothing new.
        print("MEANWHILE — already queued for adjudication (%d), no need to wait for more waves on these:" % len(queue_undecided))
        for rid, why in queue_undecided:
            print("\n".join(queue_item_lines(m, rid, why)))
    # ---- NEXT
    oc_note = ""
    if any(str(v.get("backend", "")).startswith("oc:") for v in list(m.batches.values()) + list(m.vbatches.values())):
        oc_note = " (Agent or background Bash)"
    if dispatch_inv or dispatch_ver or hedges or oc_rows:
        if solo:
            print("NEXT: work through the batch files above yourself (read → search with two independent strategies → write the output file), then run `audit.py status`.")
        else:
            print("NEXT: dispatch everything above in ONE message, then run `audit.py status` again when the next completion notification%s arrives." % oc_note)
        return
    if not m.wave_a_done() or not m.wave_b_done():
        if held_units(c):
            print(HELD_NEXT % len(held_units(c)))
            return
        stuck = [b for b in m.batches if b in m.events and not m.batch_done.get(b) and b not in m.failed]
        stuck += [b for b in m.vbatches if b in m.events and not m.vdone.get(b) and b not in m.failed]
        if stuck:
            print("NOTE: agents finished without complete output: %s → `audit.py status --redispatch %s`" % (", ".join(stuck), " ".join(stuck)))
        if not solo and (ri or rv):
            print(("NEXT: wait for completion notifications%s (do not poll in a loop); on each one run `audit.py status`. "
                   "If an agent reported failure or partial output: `audit.py status --failed <batch>` (moves its items to verifiers) or `--redispatch <batch>`.") % oc_note)
        elif stuck:
            print("NEXT: `audit.py status --redispatch %s`" % " ".join(stuck))
        else:
            print("NEXT: nothing is currently running; if a batch stalled silently, mark it with "
                  "`audit.py status --failed <batch>` (moves its items to verifiers) or retry with `--redispatch <batch>`, then `audit.py status`.")
        return
    print("\n".join(next_after_waves(c, m)))


# --------------------------------------------------------------------------- queue / adjudicate

def queue_item_lines(m, rid, why):
    r = m.items[rid]
    f = m.finding.get(rid) or {}
    v = m.verdict.get(rid) or {}
    lines = ["%s [%s%s] — %s" % (rid, r.get("strength"), "/high-stakes" if r.get("stakes") == "high" else "", why),
              "  requirement: %s" % r.get("text")]
    if r.get("search_hints"):
        lines.append("  hints: %s" % ", ".join(str(h) for h in r.get("search_hints")))
    if f:
        lines.append("  investigator: %s (%s) %s" % (norm_status(f.get("status")), f.get("confidence", "?"), (f.get("notes") or "")[:160]))
        for e in (f.get("evidence") or [])[:3]:
            if isinstance(e, dict):
                lines.append("    %s:%s — %s" % (e.get("path"), e.get("lines"), e.get("note", "")))
        if f.get("searched"):
            lines.append("    searched: %s" % ", ".join(str(s) for s in f.get("searched")[:15]))
    if v:
        lines.append("  verifier: %s (%s, agree=%s) %s" % (norm_status(v.get("verified_status") or v.get("status")), v.get("confidence", "?"), v.get("agree"), (v.get("reason") or "")[:160]))
        for e in (v.get("evidence") or [])[:3]:
            if isinstance(e, dict):
                lines.append("    %s:%s — %s" % (e.get("path"), e.get("lines"), e.get("note", "")))
    lines.append("  current final: %s" % m.final_status(rid))
    lines.append("")
    return lines


def next_after_waves(c, m):
    """Lines describing what happens once wave A/B are complete: the adjudication
    queue itself (not just a pointer to `audit.py queue`), or the next concrete
    step once it is empty (write plan.jsonl, or go straight to `report`)."""
    q = m.queue_ids()
    undecided = [(rid, why) for rid, why in q if rid not in m.adj]
    if undecided:
        lines = ["Waves complete — ADJUDICATION QUEUE (%d):" % len(undecided),
                  "  audit.py adjudicate --set REQ-xxx STATUS --note \"why\"   |   audit.py adjudicate --accept REQ-xxx [REQ-yyy ...]   |   --accept-queue"]
        for rid, why in undecided:
            lines.extend(queue_item_lines(m, rid, why))
        lines.append("NEXT: read the cited lines above, decide, `audit.py adjudicate ...` for each; once the queue is empty, `audit.py status` again.")
        return lines
    disc = [rid for rid in m.items if m.final_status(rid) in DISCREPANT]
    plan_rows, _ = read_jsonl(c.out / "plan.jsonl")
    planned = {i for r in plan_rows for i in plan_ids(r) if i}
    unplanned = [rid for rid in disc if rid not in planned]
    if unplanned:
        lines = ["Adjudication complete. %d discrepancies need a remediation entry in %s (schema: references/schemas.md):" % (len(unplanned), c.out / "plan.jsonl")]
        for rid in unplanned:
            f = m.finding.get(rid) or {}
            ev = "; ".join("%s:%s" % (e.get("path"), e.get("lines")) for e in (f.get("evidence") or [])[:2] if isinstance(e, dict))
            lines.append("  %s %s [%s/%s] %s%s" % (STATUS_ICON[m.final_status(rid)], rid, m.items[rid].get("strength"), m.items[rid].get("stakes", "normal"),
                                                  (m.items[rid].get("text") or "")[:100], (" — " + ev) if ev else ""))
        lines.append("NEXT: write plan.jsonl (P0 = any CONFLICT or unmet MUST on a core/high-stakes flow; P1 = other MUST gaps + user-visible SHOULD gaps; P2 = rest), then `audit.py report`.")
        return lines
    return ["NEXT: `audit.py report` (runs the check and prints its verdict)."]


def cmd_queue(a):
    c = Ctx(a.cwd)
    m = Merged(c)
    q = [(rid, why) for rid, why in m.queue_ids() if rid not in m.adj]
    if not q:
        print("Adjudication queue is empty. NEXT: `audit.py status`.")
        return
    print("ADJUDICATION QUEUE (%d) — read the cited lines (batch the Reads in one turn), decide, record with:" % len(q))
    print("  audit.py adjudicate --set REQ-xxx STATUS --note \"why\"   |   audit.py adjudicate --accept REQ-xxx [REQ-yyy ...]")
    print("Your judgment is authoritative; keep MISSING only when both passes found nothing and you believe the searches were adequate.\n")
    for rid, why in q:
        print("\n".join(queue_item_lines(m, rid, why)))


def cmd_adjudicate(a):
    c = Ctx(a.cwd)
    m = Merged(c)
    entries = []
    for pair in (a.set or []):
        rid, st = pair
        st = norm_status(st)
        if rid not in m.items:
            die("unknown id %s" % rid)
        if st == "UNSEARCHED":
            die("%s: status must be one of %s" % (rid, "/".join(STATUSES[:-1])))
        entries.append({"id": rid, "final_status": st, "note": a.note or "", "by": "lead", "at": ts_iso()})
    for rid in (a.accept or []):
        if rid not in m.items:
            die("unknown id %s" % rid)
        fs = m.final_status(rid)
        if fs == "UNSEARCHED":
            die("%s: cannot accept UNSEARCHED (no finding yet) — investigate it first, or use --set %s STATUS" % (rid, rid))
        entries.append({"id": rid, "final_status": fs, "note": a.note or "", "by": "lead", "at": ts_iso()})
    skipped_unsearched = []
    if a.accept_queue:
        for rid, why in m.queue_ids():
            if rid in m.adj:
                continue
            fs = m.final_status(rid)
            if fs == "UNSEARCHED":
                skipped_unsearched.append(rid)
                continue
            entries.append({"id": rid, "final_status": fs, "note": a.note or "", "by": "lead", "at": ts_iso()})
    if not entries and not skipped_unsearched:
        die("nothing to record. Use --set ID STATUS [--note ...], --accept ID..., or --accept-queue")
    if entries:
        with open(str(c.out / "adjudications.jsonl"), "a", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        print("recorded %d adjudication(s): %s" % (len(entries), ", ".join("%s=%s" % (e["id"], e["final_status"]) for e in entries)))
    if skipped_unsearched:
        print("skipped (UNSEARCHED, needs investigation before it can be accepted): %s" % ", ".join(skipped_unsearched))
    m2 = Merged(c)  # rebuild ONCE to reflect the entries just written; never per queued id
    print("\n".join(next_after_waves(c, m2)))


# --------------------------------------------------------------------------- report

HEADINGS = {
    "en": {"title": "Requirements ↔ Code Audit", "sot": "Source of truth", "code": "Codebase", "date": "Date",
           "constraints": "Constraints honored: no git history; no documentation other than the source of truth; codebase not modified.",
           "summary": "Summary", "total": "Total requirements", "align": "Alignment", "trace": "Traceability",
           "cols": ["ID", "Requirement", "Strength", "Status", "Evidence (path:lines)", "Notes"],
           "disc": "Discrepancies (detail)", "req": "Requirement", "finding": "Finding", "why": "Why it diverges",
           "plan": "Remediation plan", "effort": "Effort", "current": "Current", "target": "Target", "fix": "Fix",
           "depends": "Depends on", "risk": "Risk", "decision": "Needs product decision", "runtime": "Needs runtime verification",
           "appendix": "Appendix — undocumented behavior (informational, not failures)", "none": "(none)",
           "noplan": "(no remediation plan written yet — see .hybrid-audit/plan.jsonl)",
           "status": {"MATCHED": "Matched", "PARTIAL": "Partial", "MISSING": "Missing", "CONFLICT": "Conflict", "UNVERIFIABLE": "Unverifiable", "UNSEARCHED": "Unsearched"}},
    "vi": {"title": "Kiểm toán Yêu cầu ↔ Mã nguồn", "sot": "Nguồn chân lý (tài liệu yêu cầu)", "code": "Mã nguồn", "date": "Ngày",
           "constraints": "Ràng buộc đã tuân thủ: không đọc lịch sử git; không đọc tài liệu nào ngoài nguồn chân lý; không sửa mã nguồn.",
           "summary": "Tóm tắt", "total": "Tổng số yêu cầu", "align": "Mức độ phù hợp", "trace": "Bảng truy vết",
           "cols": ["ID", "Yêu cầu", "Mức", "Trạng thái", "Bằng chứng (path:dòng)", "Ghi chú"],
           "disc": "Sai lệch (chi tiết)", "req": "Yêu cầu", "finding": "Phát hiện", "why": "Vì sao sai lệch",
           "plan": "Kế hoạch khắc phục", "effort": "Công sức", "current": "Hiện trạng", "target": "Mục tiêu", "fix": "Cách sửa",
           "depends": "Phụ thuộc", "risk": "Rủi ro", "decision": "Cần quyết định sản phẩm", "runtime": "Cần kiểm chứng lúc chạy",
           "appendix": "Phụ lục — hành vi không có trong tài liệu (chỉ tham khảo, không phải lỗi)", "none": "(không có)",
           "noplan": "(chưa có kế hoạch khắc phục — xem .hybrid-audit/plan.jsonl)",
           "status": {"MATCHED": "Đạt", "PARTIAL": "Một phần", "MISSING": "Thiếu", "CONFLICT": "Mâu thuẫn", "UNVERIFIABLE": "Không kiểm được", "UNSEARCHED": "Chưa tìm"}},
}


def evidence_str(rows, limit=3):
    out = []
    for e in (rows or [])[:limit]:
        if isinstance(e, dict) and e.get("path"):
            out.append("`%s:%s`" % (e.get("path"), e.get("lines", "")))
    return ", ".join(out)


def backend_parts(c, role, rows):
    counts = {}
    order = []
    for r in rows:
        b = r.get("backend") or "claude"
        if b not in counts:
            counts[b] = 0
            order.append(b)
        counts[b] += 1
    parts = []
    for b in order:
        label = ("claude %s" % c.model(role)) if b == "claude" else b
        parts.append("%s (%d items)" % (label, counts[b]))
    return " + ".join(parts) or "none"


def backends_line(c, finding_rows, verdict_rows):
    finding_rows = list(finding_rows)
    verdict_rows = list(verdict_rows)
    if not any(str(r.get("backend") or "").startswith("oc:") for r in finding_rows + verdict_rows):
        return ""
    return "- Backends: investigators %s; verifiers %s" % (
        backend_parts(c, "investigator", finding_rows),
        backend_parts(c, "verifier", verdict_rows),
    )


def cmd_report(a):
    c = Ctx(a.cwd)
    m = Merged(c)
    H = HEADINGS.get(a.lang or c.lang) or HEADINGS["en"]
    if a.headings:
        H = dict(H)
        H.update(read_json(a.headings, {}))
    cnt = m.counts()
    total = len(m.items)
    plan_rows, perr = read_jsonl(c.out / "plan.jsonl")
    L = []
    L.append("# %s\n" % H["title"])
    L.append("- %s: %s" % (H["sot"], ", ".join("`%s`" % s for s in c.cfg["spec_files"])))
    L.append("- %s: `%s`" % (H["code"], c.repo))
    L.append("- %s: %s" % (H["date"], datetime.now().strftime("%Y-%m-%d")))
    bl = backends_line(c, m.finding.values(), m.verdict.values())
    if bl:
        L.append(bl)
    L.append("- %s\n" % H["constraints"])
    L.append("## %s\n" % H["summary"])
    L.append("- %s: %d" % (H["total"], total))
    L.append("- " + "   ".join("%s %s: %d" % (STATUS_ICON[s], H["status"][s], cnt[s]) for s in STATUSES if cnt[s] or s != "UNSEARCHED"))
    L.append("- %s: %d / %d\n" % (H["align"], cnt["MATCHED"], total))
    L.append("## %s\n" % H["trace"])
    L.append("| " + " | ".join(H["cols"]) + " |")
    L.append("|" + "---|" * len(H["cols"]))
    csv_rows = []
    for r in m.rows:
        rid = r["id"]
        fs = m.final_status(rid)
        src = m.verdict.get(rid) if (m.ver_status(rid) == fs and rid in m.verdict) else m.finding.get(rid)
        ev = evidence_str((src or {}).get("evidence"))
        note = ((m.adj.get(rid) or {}).get("note") or (m.verdict.get(rid) or {}).get("reason")
                or (m.finding.get(rid) or {}).get("notes") or "")
        if m.skip_tagged(rid):
            note = ",".join(r.get("tags") or []) + (": " + note if note else "")
        L.append("| %s | %s | %s | %s %s | %s | %s |" % (rid, (r.get("text") or "").replace("|", "\\|").replace("\n", " "), r.get("strength"),
                                                        STATUS_ICON[fs], H["status"][fs], ev.replace("|", "\\|"), note.replace("|", "\\|").replace("\n", " ")[:200]))
        csv_rows.append([rid, r.get("text"), r.get("strength"), r.get("category", ""), r.get("stakes", "normal"), fs, ev.replace("`", ""), note, r.get("source", "")])
    L.append("")
    L.append("## %s\n" % H["disc"])
    disc = [r for r in m.rows if m.final_status(r["id"]) in DISCREPANT]
    if not disc:
        L.append(H["none"] + "\n")
    for r in disc:
        rid = r["id"]
        fs = m.final_status(rid)
        f = m.finding.get(rid) or {}
        v = m.verdict.get(rid) or {}
        src = v if (m.ver_status(rid) == fs and v) else f
        L.append("### %s %s %s — %s" % (STATUS_ICON[fs], H["status"][fs], rid, (r.get("text") or "")[:80]))
        L.append("- %s: %s" % (H["req"], r.get("text")))
        finding_txt = "; ".join("%s:%s — %s" % (e.get("path"), e.get("lines"), e.get("note", "")) for e in (src.get("evidence") or [])[:3] if isinstance(e, dict))
        if not finding_txt and fs == "MISSING":
            searched = list(f.get("searched") or []) + list(v.get("searched") or [])
            finding_txt = "MISSING — searched: " + ", ".join(str(s) for s in searched[:20])
        L.append("- %s: %s" % (H["finding"], finding_txt or H["none"]))
        why = (m.adj.get(rid) or {}).get("note") or v.get("reason") or f.get("notes") or ""
        L.append("- %s: %s\n" % (H["why"], why or H["none"]))
    L.append("## %s\n" % H["plan"])
    if perr:
        L.append("(plan.jsonl has JSON errors: %s)\n" % "; ".join(perr[:5]))
    if not plan_rows:
        L.append((H["none"] if not disc else H["noplan"]) + "\n")
    else:
        order = {"P0": 0, "P1": 1, "P2": 2}
        plan_rows.sort(key=lambda p: (order.get(str(p.get("priority", "P2")).upper(), 3), str(p.get("ids") or p.get("id"))))
        for pr in ("P0", "P1", "P2"):
            group = [p for p in plan_rows if str(p.get("priority", "")).upper() == pr]
            if not group:
                continue
            L.append("### %s\n" % pr)
            for i, p in enumerate(group, 1):
                ids = plan_ids(p)
                L.append("%d. **%s** (%s) — %s %s" % (i, p.get("title", ", ".join(ids)), ", ".join(ids), H["effort"], p.get("effort", "?")))
                for key, label in (("current", H["current"]), ("target", H["target"]), ("fix", H["fix"]), ("depends", H["depends"]), ("risk", H["risk"])):
                    if p.get(key):
                        L.append("   - %s: %s" % (label, p[key]))
            L.append("")
    amb = [r for r in m.rows if "ambiguous" in (r.get("tags") or [])]
    L.append("## %s\n" % H["decision"])
    L.extend(["- %s: %s" % (r["id"], r.get("question") or r.get("text")) for r in amb] or [H["none"]])
    L.append("")
    sl = [r for r in m.rows if "static-limit" in (r.get("tags") or [])]
    L.append("## %s\n" % H["runtime"])
    L.extend(["- %s: %s" % (r["id"], r.get("question") or r.get("evidence_expected") or r.get("text")) for r in sl] or [H["none"]])
    L.append("")
    L.append("## %s\n" % H["appendix"])
    app = c.out / "appendix.md"
    L.append(app.read_text(encoding="utf-8").strip() if app.exists() else H["none"])
    L.append("")
    report = c.out / "requirements-code-audit.md"
    write_text(report, "\n".join(L))
    with open(str(c.out / "traceability.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "requirement", "strength", "category", "stakes", "status", "evidence", "notes", "source"])
        w.writerows(csv_rows)
    print("report: %s  (+ traceability.csv)" % report)
    print("HEADLINE: total %d | %s | alignment %d/%d" % (total, " | ".join("%s %d" % (H["status"][s], cnt[s]) for s in STATUSES if cnt[s]), cnt["MATCHED"], total))
    probs, warns = run_check(c, m)
    print_check_verdict(probs, warns)
    if probs:
        print("NEXT: fix the problems (adjudicate / verify / plan), then `audit.py report` again.")
    else:
        print("NEXT: `audit.py finish`")


# --------------------------------------------------------------------------- check

def line_count(path):
    try:
        with open(str(path), "rb") as f:
            data = f.read()
        if b"\x00" in data[:4096]:
            return None
        return data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)
    except Exception:
        return None


LINES_RE = re.compile(r"^\s*[Ll]?(\d+)\s*(?:[-–]\s*[Ll]?(\d+))?\s*$")  # "41-58", "L41-L58", "41–58"


def check_evidence(repo, ev):
    """Return a problem string or None."""
    if not isinstance(ev, dict) or not ev.get("path"):
        return "evidence entry without path"
    p = Path(ev["path"])
    full = p if p.is_absolute() else repo / p
    if not full.exists():
        return "cited file does not exist: %s" % ev["path"]
    lines = str(ev.get("lines") or "")
    mm = LINES_RE.match(lines)
    if not mm:
        return "evidence lines missing/unparseable for %s (%r)" % (ev["path"], lines)
    n = line_count(full)
    if n is None:
        return None
    end = int(mm.group(2) or mm.group(1))
    if end > n + 1:
        return "cited line %d beyond end of %s (%d lines)" % (end, ev["path"], n)
    return None


def run_check(c, m):
    """The mechanical quality-gate logic, shared by `check` and inline by `report`."""
    probs, warns = [], []
    disc_ids = []
    for rid, r in m.items.items():
        fs = m.final_status(rid)
        if fs == "UNSEARCHED":
            probs.append("%s: no finding and no adjudication" % rid)
            continue
        if fs in DISCREPANT:
            disc_ids.append(rid)
        if m.skip_tagged(rid):
            continue
        f = m.finding.get(rid) or {}
        v = m.verdict.get(rid) or {}
        if fs == "MISSING":
            if rid not in m.verdict and rid not in m.adj:
                probs.append("%s: MISSING after one pass only — needs Wave B verification or an adjudication" % rid)
            # an adjudicated id is the lead's final call; the mechanical search-coverage
            # rule below is a HEURISTIC to catch it BEFORE adjudication, not a re-litigation.
            if rid not in m.adj:
                searched = [str(s).lower() for s in list(f.get("searched") or []) + list(v.get("searched") or [])]
                if not searched:
                    probs.append("%s: MISSING without any `searched` terms" % rid)
                else:
                    for h in (r.get("search_hints") or []):
                        hl = str(h).lower()
                        if not any(hl in s or s in hl for s in searched):
                            warns.append("%s: search hint %r never appears in searched terms" % (rid, h))
        if m.needs_verification(rid) and rid not in m.verdict and rid not in m.adj:
            if fs != "MATCHED":
                probs.append("%s: non-MATCHED item was never verified or adjudicated" % rid)
            else:
                warns.append("%s: MATCHED with low confidence or high stakes but never verified" % rid)
        if m.disagreement(rid):
            probs.append("%s: investigator (%s) and verifier (%s) disagree — adjudicate" % (rid, m.inv_status(rid), m.ver_status(rid)))
        elif m.oc_risky(rid) and rid not in m.adj:
            probs.append("%s: %s comes from an opencode verifier — adjudicate" % (rid, m.ver_status(rid)))
        if fs != "MISSING" and fs != "UNVERIFIABLE":
            src = v if (m.ver_status(rid) == fs and v) else f
            evs = src.get("evidence") or []
            if not evs and rid not in m.adj:
                probs.append("%s: status %s without evidence" % (rid, fs))
            for ev in evs[:5]:
                pr = check_evidence(m.c.repo, ev)
                if pr:
                    probs.append("%s: %s" % (rid, pr))
    plan_rows, perr = read_jsonl(c.out / "plan.jsonl")
    probs.extend("plan.jsonl: " + e for e in perr)
    planned = {}
    for p in plan_rows:
        for i in plan_ids(p):
            planned[i] = p
        if str(p.get("priority", "")).upper() not in ("P0", "P1", "P2"):
            probs.append("plan entry %s: priority must be P0/P1/P2" % (p.get("ids") or p.get("id")))
        if str(p.get("effort", "")).upper() not in ("S", "M", "L"):
            warns.append("plan entry %s: effort should be S/M/L" % (p.get("ids") or p.get("id")))
    for rid in disc_ids:
        if rid not in planned:
            probs.append("%s: discrepancy without a remediation entry" % rid)
        else:
            r = m.items[rid]
            pr = str(planned[rid].get("priority", "")).upper()
            if m.final_status(rid) == "CONFLICT" and pr != "P0":
                warns.append("%s: CONFLICT but priority %s (expected P0)" % (rid, pr))
            if r.get("strength") == "MUST" and r.get("stakes") == "high" and pr != "P0":
                warns.append("%s: unmet high-stakes MUST but priority %s (expected P0)" % (rid, pr))
            if r.get("strength") == "MAY" and pr == "P0":
                warns.append("%s: MAY requirement at P0" % rid)
    rep = c.out / "requirements-code-audit.md"
    if not rep.exists():
        probs.append("report not built yet (`audit.py report`)")
    return probs, warns


def print_check_verdict(probs, warns):
    print("CHECK: %d problem(s), %d warning(s)" % (len(probs), len(warns)))
    for p in probs:
        print("  PROBLEM: " + p)
    for w in warns[:40]:
        print("  warn: " + w)


def cmd_check(a):
    c = Ctx(a.cwd)
    m = Merged(c)
    probs, warns = run_check(c, m)
    print_check_verdict(probs, warns)
    if probs:
        print("Fix the problems (adjudicate / verify / plan), rebuild with `audit.py report`, re-run `audit.py check`.")
        sys.exit(1)
    print("OK — NEXT: `audit.py finish`")


# --------------------------------------------------------------------------- finish / abort

def item_records(repo, ids, findings, verdicts, adjudications, finals, now):
    recs = []
    for rid in ids:
        f = findings.get(rid) or {}
        v = verdicts.get(rid)
        inv = norm_status(f.get("status"))
        ver = norm_status(v.get("verified_status") or v.get("status")) if v else None
        if ver == "UNSEARCHED":
            ver = None
        final = finals.get(rid) or inv
        adj = adjudications.get(rid)
        base = ver if ver is not None else inv
        recs.append({
            "t": now,
            "kind": "item",
            "repo": str(repo),
            "id": rid,
            "backend": f.get("backend") or "claude",
            "inv": inv,
            "ver": ver,
            "final": final,
            "verifier_overturned": ver is not None and ver != inv,
            "lead_overturned": adj is not None and adj != base,
        })
    return recs


def emit_item_telemetry(recs):
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ha_telemetry
        for rec in recs:
            ha_telemetry.record(rec)
    except Exception:
        pass


def cmd_finish(a):
    c = Ctx(a.cwd)
    already = bool(c.cfg.get("finished"))
    c.cfg["active"] = False
    c.cfg["finished"] = ts_iso()
    c.save_cfg()
    marker = c.cfg_dir / ACTIVE
    if marker.exists():
        marker.unlink()
    m = Merged(c)
    if a.cmd == "finish" and not already:
        emit_item_telemetry(item_records(
            c.repo, [r["id"] for r in m.rows], m.finding, m.verdict,
            {rid: m.final_status(rid) for rid in m.adj},
            {rid: m.final_status(rid) for rid in m.items}, time.time()))
    cnt = m.counts()
    total = len(m.items)
    H = HEADINGS.get(c.lang) or HEADINGS["en"]
    print("Audit closed (guard hooks disarmed). Report: %s" % (c.out / "requirements-code-audit.md"))
    print("HEADLINE: %s %d | %s | %s %d/%d" % (H["total"], total, " | ".join("%s %d" % (H["status"][s], cnt[s]) for s in STATUSES if cnt[s]), H["align"], cnt["MATCHED"], total))
    disc = [rid for rid in m.items if m.final_status(rid) in DISCREPANT]
    p0 = [p for p in read_jsonl(c.out / "plan.jsonl")[0] if str(p.get("priority", "")).upper() == "P0"]
    print("Discrepancies: %d (P0 items in plan: %d). Tell the user the headline numbers + the report path; do not paste the whole report." % (len(disc), len(p0)))


def cmd_oc_run(a):
    use_scripts()
    import ha_run
    # run_named prints every OC line and the single `OC ...` summary line itself and never raises.
    result = ha_run.run_named(str(Path(a.cwd or os.getcwd()).resolve()), a.name)
    return 0 if result.get("ok") else 3


def cmd_doctor(a):
    use_scripts()
    import ha_doctor
    import ha_router
    hs = shared()
    routing = ha_router.load_routing(SKILL_DIR / "routing.default.json", ha_router.user_routing_path())
    cache = ha_doctor.doctor_cache_path()
    binary = os.environ.get("HYBRID_AUDIT_OC_BIN", "opencode")
    workdir = Path(a.cwd or os.getcwd()).resolve()
    data = ha_doctor.run_doctor(binary, routing, a.ping, workdir, ha_doctor.load_doctor(cache), logdir=cache.parent)
    ha_doctor.write_doctor(cache, data)
    print("doctor: opencode %s (%s) — %s" % ("v" + data["version"] if data.get("version") else "not found",
                                            binary, "ok" if data.get("ok") else "NOT ok"))
    tiers = routing.get("tiers") or {}
    sources = routing.get("model_sources") or {}
    for name, entry in sorted((data.get("tiers") or {}).items()):
        spec = hs.cache_key(tiers.get(name) or {})
        text = "  tier %s: %s (%s) ok=%s" % (name, spec or "no model", sources.get(name, "none"), bool(entry.get("ok")))
        if not entry.get("ok"):
            text += " — %s: %s" % (entry.get("kind") or "unknown", entry.get("detail") or "")
        print(text)
    print(ha_doctor.status_line(routing, data, ""))
    print("  cache   : %s" % cache)
    shared_tiers, _ = hs.load_shared()
    specs = ", ".join("%s=%s" % (name, hs.model_spec(tier)) for name, tier in shared_tiers.items())
    unset = not (os.environ.get(hs.STD_ENV) or "").strip()
    print("  shared  : %s = %s" % (hs.SHARED_SOURCE, specs or ("not set" if unset else "invalid")))
    for name, spec, kind, detail in doctor_problems(routing, data):
        print(hs.oc_line("OC-ERROR", SKILL_NAME, "doctor", name, spec, kind, detail))
    for problem in routing.get("config_problems") or []:
        print(hs.oc_line("OC-ERROR", SKILL_NAME, "config", "none", "none", "config", problem))
    for warning in routing.get("config_warnings") or []:
        print(hs.oc_line("OC-WARN", SKILL_NAME, "config", "none", "none", "config", warning))


def cmd_config(a):
    """Preload lines: each tier's effective model with its source, then the opencode status line.

    Read-only and bounded; always exits 0, because a failing preload cancels the skill.
    """
    try:
        use_scripts()
        import ha_doctor
        import ha_router
        hs = shared()
        routing = ha_router.load_routing(SKILL_DIR / "routing.default.json", ha_router.user_routing_path())
        sources = routing.get("model_sources") or {}
        parts = []
        for name in hs.TIERS:
            spec = hs.model_spec((routing.get("tiers") or {}).get(name) or {})
            parts.append("%s=%s (%s)" % (name, spec, sources.get(name)) if spec else "%s=no config" % name)
        print("opencode config: " + " ".join(parts))
        for problem in (routing.get("config_problems") or [])[:3]:
            print("  no config (%s)" % " ".join(str(problem).split())[:200])
        print(ha_doctor.status_line(routing, ha_doctor.load_doctor(ha_doctor.doctor_cache_path())))
    except Exception as exc:
        print("opencode config: unreadable (%s: %s)" % (type(exc).__name__, exc))
    return 0


def cmd_stats(a):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import ha_telemetry
    records = ha_telemetry.load_records(ha_telemetry.telemetry_path())
    for line in ha_telemetry.stats_lines(records, a.repo or ""):
        print(line)


# --------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(prog="audit.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cwd", help="working directory holding .hybrid-audit/ (default: current directory)")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("init", help="start an audit here")
    p.add_argument("--spec", action="append", help="requirements file (repeatable; .md/.txt/.docx; pdf via pdftotext)")
    p.add_argument("--spec-text", help="file containing pasted requirement text")
    p.add_argument("--repo", help="codebase root (default: cwd)")
    p.add_argument("--out", help="audit output dir (default: <cwd>/.hybrid-audit; keep it inside cwd to avoid permission prompts)")
    p.add_argument("--lang", default="auto", help="report language: auto|en|vi|<code>")
    p.add_argument("--agents", choices=["plugin", "local", "generic", "solo"], help="how workers are spawned (see SKILL.md Step 0)")
    p.add_argument("--cap", type=int, help="concurrent subagent cap (default: $CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS or 20)")
    p.add_argument("--force", action="store_true", help="archive an existing audit and start over")
    p.add_argument("--preset", help="run mode: claude|hybrid|opencode (max is a deprecated alias of opencode); "
                                    "default: the routing file's preset")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("spec", help="add/list requirement files")
    p.add_argument("--add", action="append")
    p.set_defaults(fn=cmd_spec)

    p = sub.add_parser("parse-plan", help="split a large spec into parser sections")
    p.add_argument("--sections", type=int)
    p.set_defaults(fn=cmd_parse_plan)

    p = sub.add_parser("parse-merge", help="merge parser outputs into checklist.draft.jsonl")
    p.add_argument("--accept", action="store_true", help="promote the draft to checklist.jsonl")
    p.add_argument("--to-claude", action="store_true", help="let held opencode sections run on Claude parsers")
    p.set_defaults(fn=cmd_parse_merge)

    p = sub.add_parser("plan", help="checklist.jsonl -> batch files + dispatch list")
    p.add_argument("--cap", type=int)
    p.add_argument("--solo", action="store_true")
    p.add_argument("--no-mark", action="store_true", help="print the dispatch list without marking batches as dispatched")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("status", help="merge findings, pack verifiers, print NEXT")
    p.add_argument("--failed", nargs="*", help="batches whose agent failed/partially finished")
    p.add_argument("--redispatch", nargs="*", help="re-dispatch the uncovered items of these batches")
    p.add_argument("--undispatch", nargs="*", help="mark batches as not dispatched (e.g. after 'Concurrent subagent limit reached'); `all` resets every batch")
    p.add_argument("--retry", nargs="+", metavar="UNIT",
                   help="release held units (names, or `all`) for another opencode attempt")
    p.add_argument("--to-claude", nargs="+", choices=["investigator", "verifier", "all"], dest="to_claude",
                   help="let these roles run on Claude in preset opencode")
    p.add_argument("--mode", help="switch the run to hybrid|claude|opencode (max is a deprecated alias for opencode)")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("queue", help="print the adjudication queue")
    p.set_defaults(fn=cmd_queue)

    p = sub.add_parser("adjudicate", help="record final decisions")
    p.add_argument("--set", nargs=2, action="append", metavar=("ID", "STATUS"))
    p.add_argument("--accept", nargs="*")
    p.add_argument("--accept-queue", action="store_true")
    p.add_argument("--note")
    p.set_defaults(fn=cmd_adjudicate)

    p = sub.add_parser("report", help="assemble the final report")
    p.add_argument("--lang")
    p.add_argument("--headings", help="JSON file overriding report headings (for other languages)")
    p.set_defaults(fn=cmd_report)

    p = sub.add_parser("check", help="mechanical quality gate")
    p.set_defaults(fn=cmd_check)

    p = sub.add_parser("finish", help="close the audit and disarm hooks")
    p.set_defaults(fn=cmd_finish)
    p = sub.add_parser("abort", help="close the audit without a report")
    p.set_defaults(fn=cmd_finish)

    p = sub.add_parser("oc-run", help="run one batch/section on opencode (dispatched as a background Bash command)")
    p.add_argument("name")
    p.set_defaults(fn=cmd_oc_run)

    p = sub.add_parser("doctor", help="check opencode and the routing tiers; works outside an audit")
    p.add_argument("--ping", action="store_true", help="send a tiny prompt through each tier")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("config", help="print the effective tier models and their sources (skill preload; always exits 0)")
    p.set_defaults(fn=cmd_config)

    p = sub.add_parser("stats", help="aggregate opencode telemetry")
    p.add_argument("--repo", help="only records for this repo")
    p.set_defaults(fn=cmd_stats)

    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 0
    return a.fn(a) or 0


if __name__ == "__main__":
    sys.exit(main())
