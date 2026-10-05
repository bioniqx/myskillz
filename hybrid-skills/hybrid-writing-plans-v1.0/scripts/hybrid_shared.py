"""Shared opencode config, run modes, failure kinds and OC lines for the hybrid skills.

Vendored byte-identical into each hybrid skill's scripts/ folder; the canonical
copy lives in hybrid-brainstorming. Stdlib only, Python 3.8+. The shared models
come from $HYBRID_OPENCODE_STD and $HYBRID_OPENCODE_LITE (provider/model[#variant];
LITE defaults to STD). Run it as a script for the config/check/mode commands (see cli()).

Opencode concurrency is bounded twice: each tier (std, lite) runs at most its max_parallel lanes
(default 4, $HYBRID_OPENCODE_MAX_PARALLEL), AND all tiers together run at most the shared pool
($HYBRID_OPENCODE_POOL, default 6, at most 8 = the provider's concurrent-call limit). The pool is
shared across tiers; Claude subagents are not counted in either bound.
"""
import argparse
import copy
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

MODES = ("hybrid", "claude", "opencode")
STD_ENV = "HYBRID_OPENCODE_STD"
LITE_ENV = "HYBRID_OPENCODE_LITE"
MAX_PARALLEL_ENV = "HYBRID_OPENCODE_MAX_PARALLEL"
MAX_PARALLEL_LIMIT = 8  # concurrent opencode (non-Claude) API calls per tier; Claude subagents are not capped here
OC_POOL_ENV = "HYBRID_OPENCODE_POOL"
OC_POOL_DEFAULT = 6  # opencode lanes in flight across ALL tiers at once
OC_POOL_LIMIT = MAX_PARALLEL_LIMIT
SHARED_SOURCE = "$%s/$%s" % (STD_ENV, LITE_ENV)
DOCTOR_TTL_S = 600
NON_RETRYABLE = ("auth", "quota", "model", "config")
CONNECTION_KINDS = ("spawn", "stall", "throttle", "crash")
OC_RETRIES = 3
RETRY_DELAYS_S = (10, 30, 60)
RETRY_DELAY_ENV = "HYBRID_OC_RETRY_DELAY_S"
MODELS_EMPTY_RETRIES = 2  # `models` re-runs while it lists nothing (a cold service)
FALLBACK_MODEL = "sonnet"
SWITCH_FILE = "oc-switched.json"
SESSION_ENV = "CLAUDE_CODE_SESSION_ID"  # run state written in another Claude Code session is stale
TIERS = ("std", "lite")
MODEL_RE = re.compile(r"[^/\s]+/[^\s#]+")
VARIANT_RE = re.compile(r"[^\s#]+")
DETAIL_MAX = 200
BREAKER_DIR = "oc-breaker"


def _one_line(text) -> str:
    return " ".join(str("" if text is None else text).split())


def _parse_spec(text: str) -> dict:
    model, _, variant = text.partition("#")
    tier = {"model": model}
    if variant:
        tier["variant"] = variant
    return tier


def max_parallel_from_env(env: dict = None) -> tuple:
    """Read the opencode slot cap from $HYBRID_OPENCODE_MAX_PARALLEL; never raises.

    Returns (value, problem): value is an int from 1 to MAX_PARALLEL_LIMIT (8), or None when the variable is
    unset or invalid; problem is "" unless it is set to something invalid.
    """
    env = os.environ if env is None else env
    text = (env.get(MAX_PARALLEL_ENV) or "").strip()
    if not text:
        return None, ""
    if re.fullmatch(r"[0-9]+", text) and 1 <= int(text) <= MAX_PARALLEL_LIMIT:
        return int(text), ""
    return None, "%s must be an integer from 1 to %d, got %r" % (MAX_PARALLEL_ENV, MAX_PARALLEL_LIMIT, text)


def pool_from_env(env: dict = None) -> tuple:
    """Read the cross-tier opencode pool size from $HYBRID_OPENCODE_POOL; never raises.

    Returns (value, problem): value is an int from 1 to OC_POOL_LIMIT (8), OC_POOL_DEFAULT (6) when the variable
    is unset, or None when it is invalid; problem is "" unless it is set to something invalid.
    """
    env = os.environ if env is None else env
    text = (env.get(OC_POOL_ENV) or "").strip()
    if not text:
        return OC_POOL_DEFAULT, ""
    if re.fullmatch(r"[0-9]+", text) and 1 <= int(text) <= OC_POOL_LIMIT:
        return int(text), ""
    return None, "%s must be an integer from 1 to %d, got %r" % (OC_POOL_ENV, OC_POOL_LIMIT, text)


def pool_free(pool: int, in_flight_by_tier: dict) -> int:
    """Pool slots still free given the opencode lanes in flight per tier (never negative)."""
    return max(0, pool - sum(in_flight_by_tier.values()))


def load_shared(env: dict = None) -> tuple:
    """Read the shared models from $HYBRID_OPENCODE_STD / $HYBRID_OPENCODE_LITE; never raises.

    Returns (tiers, problems): tiers maps "std"/"lite" to {model, variant?}. LITE
    defaults to STD. tiers is {} whenever problems is non-empty, so an invalid
    value behaves exactly like a missing one. An invalid $HYBRID_OPENCODE_MAX_PARALLEL
    is a problem too, so a typo fails loud instead of silently keeping the shipped cap.
    """
    env = os.environ if env is None else env
    _, cap_problem = max_parallel_from_env(env)
    cap_problems = [cap_problem] if cap_problem else []
    std = (env.get(STD_ENV) or "").strip()
    if not std:
        return {}, ["%s is not set" % STD_ENV] + cap_problems
    specs = {"std": (STD_ENV, std), "lite": (LITE_ENV, (env.get(LITE_ENV) or "").strip() or std)}
    tiers, problems = {}, []
    for name in TIERS:
        var, text = specs[name]
        tier = _parse_spec(text)
        if not MODEL_RE.fullmatch(tier["model"]) or not VARIANT_RE.fullmatch(tier.get("variant", "x")):
            problems.append("%s must be provider/model[#variant], got %r" % (var, text))
        tiers[name] = tier
    problems.extend(cap_problems)
    return ({} if problems else tiers), problems


def resolve_tiers(routing: dict, shared_tiers: dict, user_routing: dict, env: dict = None) -> dict:
    """Return a copy of routing with each tier's model resolved: per-skill file first, shared file second.

    A tier whose per-skill user file sets `model` keeps that model and only that file's
    variant; otherwise model and variant come from the shared tier. result["model_sources"]
    maps each tier to "skill", "shared" or "none". `max_parallel` follows the same order:
    the per-skill file's tier value wins, else $HYBRID_OPENCODE_MAX_PARALLEL when it is set
    and valid, else the value already in routing (the shipped default). The result is
    clamped to MAX_PARALLEL_LIMIT.
    """
    result = copy.deepcopy(routing)
    cap, _ = max_parallel_from_env(env)
    target = result.setdefault("tiers", {})
    user_tiers = user_routing.get("tiers") if isinstance(user_routing, dict) else None
    user_tiers = user_tiers if isinstance(user_tiers, dict) else {}
    sources = {}
    for name in ("std", "lite"):
        if not isinstance(target.get(name), dict):
            target[name] = {}
        dest = target[name]
        user_tier = user_tiers.get(name) if isinstance(user_tiers.get(name), dict) else {}
        shared_tier = shared_tiers.get(name) or {}
        dest.pop("model", None)
        dest.pop("variant", None)
        if cap is not None and "max_parallel" not in user_tier:
            dest["max_parallel"] = cap
        mp = dest.get("max_parallel")
        if isinstance(mp, int) and not isinstance(mp, bool) and mp > MAX_PARALLEL_LIMIT:
            dest["max_parallel"] = MAX_PARALLEL_LIMIT  # a routing file can lower the cap, never exceed it
        if user_tier.get("model"):
            source, pick = "skill", user_tier
        elif shared_tier.get("model"):
            source, pick = "shared", shared_tier
        else:
            source, pick = "none", {}
        for key in ("model", "variant"):
            if key in pick:
                dest[key] = pick[key]
        sources[name] = source
    result["model_sources"] = sources
    return result


def mode_to_preset(mode: str) -> tuple:
    """Map a run mode to a router preset; returns (preset, note).

    A known mode gives (mode, ""). The legacy alias "max" gives ("opencode",
    warning): print the note as OC-WARN kind=config. Anything else gives
    ("", error): print the note as OC-ERROR kind=config and exit non-zero.
    """
    name = _one_line(mode).lower()
    if name in MODES:
        return name, ""
    if name == "max":
        return "opencode", "preset 'max' is deprecated; running as 'opencode' (held units never fall back)"
    return "", "unknown mode %r (expected hybrid, claude or opencode)" % (mode,)


def model_spec(tier: dict) -> str:
    """Return provider/model#variant, or "" when the tier has no model."""
    if not isinstance(tier, dict):
        return ""
    model = str(tier.get("model") or "")
    variant = str(tier.get("variant") or "")
    return model + "#" + variant if model and variant else model


def config_summary(tiers: dict, problems: list) -> str:
    """One line for preloads, doctors and the mode question."""
    if problems:
        more = " (+%d more)" % (len(problems) - 3) if len(problems) > 3 else ""
        return "opencode config UNUSABLE %s :: %s%s (hybrid and opencode modes unavailable)" % (
            SHARED_SOURCE, "; ".join(problems[:3]), more)
    parts = [name + "=" + model_spec(tiers[name]) for name in TIERS if name in tiers]
    return "opencode config ok %s :: %s" % (SHARED_SOURCE, ", ".join(parts))


def cache_key(tier: dict) -> str:
    """Doctor cache key: model#variant, so a model edit invalidates the entry at once."""
    return model_spec(tier)


def cache_fresh(entry: dict, tier: dict, now: float) -> bool:
    """True when a doctor cache entry checked this exact model#variant less than DOCTOR_TTL_S ago.

    The entry's "ok" flag is not looked at: a tier is usable only when this is
    True and entry["ok"] is True.
    """
    if not isinstance(entry, dict):
        return False
    key = cache_key(tier)
    checked = entry.get("checked_at")
    if not key or entry.get("key") != key:
        return False
    if isinstance(checked, bool) or not isinstance(checked, (int, float)):
        return False
    return 0 <= now - checked < DOCTOR_TTL_S


def _http(*codes):
    """Regex for HTTP status codes that skips stack-trace numbers: index.js:12:401, :401:9 and "line 401".

    HTTP 403: / "statusCode":401 / (HTTP 403) still match.
    """
    return r"(?<!\d:)(?<!line )\b(?:%s)\b(?!:\d)" % "|".join(codes)


THROTTLE_RE = re.compile(_http("429") + r"|too many requests|rate.?limit", re.I)

# The first matching pattern decides. opencode v2 error events arrive as "type: message" or
# "type (HTTP status): message" (see error_note): provider.auth, provider.quota, provider.no-route,
# provider.rate-limit and type unknown ("Agent not found"). provider.timeout has no pattern on
# purpose: it is a crash, a retryable connection failure.
_KIND_PATTERNS = (
    ("config", re.compile(r"agent not found", re.I)),
    ("quota", re.compile(
        r"provider\.quota|credit balance|insufficient[ _]?(balance|quota)|billing|" + _http("402"), re.I)),
    ("auth", re.compile(
        r"provider\.auth|unauthori[sz]ed|authori[sz]ation failed|invalid api key|ProviderAuthError|"
        + _http("401", "403") + r"|expired|renew", re.I)),
    ("model", re.compile(
        r"provider\.no-route|model unavailable|variant unavailable|model.*not found|unknown model|"
        r"ProviderModelNotFound|no such model", re.I)),
    ("throttle", THROTTLE_RE),
    ("context", re.compile(r"context[ _](length|window)|maximum context|prompt is too long|too many tokens", re.I)),
)


def error_note(err) -> str:
    """One line for an opencode error event's `error` object: "type: message" or "type (HTTP status): message".

    The status is v2's error.status; keeping it lets classify() see 401/402/403/429.
    """
    err = err if isinstance(err, dict) else {}
    note = str(err.get("type") or "error")
    status = str(err.get("status")).strip()
    if status.isdigit():
        note += " (HTTP %s)" % status
    message = str(err.get("message") or "")
    return note + ": " + message if message else note


def classify(rc, errors: list, stderr_tail: str, killed: str = "", finished: bool = False) -> str:
    """Return the failure kind of one opencode run, or "" for a clean run.

    rc is the exit code (None when the spawn failed), errors the parsed error
    events (error_note lines), killed "timeout"/"stall" when the runner's watchdog
    killed the process, finished whether the run completed: a step_finish with
    reason "stop" (v1) or, on v2.0.20, which emits no terminal step_finish, a stream
    that ends in a fully streamed text part after the last error event.
    rc 0/1 with finished is "recovered": accept it when the output passes the
    skill's gate, and report it as OC-WARN. Otherwise the first matching
    pattern over errors + stderr decides, and anything unmatched is "crash".
    """
    if rc is None:
        return "spawn"
    if killed in ("timeout", "stall"):
        return killed
    errors = [str(error) for error in errors or []]
    if rc == 0 and not errors:
        return ""
    if finished and rc in (0, 1):
        return "recovered"
    text = "\n".join(errors + [stderr_tail or ""])
    for kind, pattern in _KIND_PATTERNS:
        if pattern.search(text):
            return kind
    return "crash"


def run_captured(cmd: list, timeout: float):
    """subprocess.run with stdout captured through a temp file, stdin closed; a CompletedProcess.

    Verified on opencode v2.0.20: the CLI exits before it has flushed a pipe, so `opencode models`
    read through a pipe came back empty or cut mid-line (0-3072 of 3467 bytes) while the same call
    written to a file was complete every time. Read every opencode answer through this.
    TimeoutExpired/OSError propagate.
    """
    import subprocess
    import tempfile
    with tempfile.TemporaryFile() as out:
        proc = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                              timeout=timeout)
        out.seek(0)
        stdout = out.read().decode("utf-8", errors="replace")
    return subprocess.CompletedProcess(cmd, proc.returncode, stdout,
                                       (proc.stderr or b"").decode("utf-8", errors="replace"))


def run_models(binary: str, timeout: float):
    """`<binary> models` through run_captured, re-run while it lists nothing (a cold service).

    Never pass `--standalone`: a private server always lists nothing on v2.0.20.
    """
    try:
        delay = float(os.environ.get(RETRY_DELAY_ENV, "2"))
    except ValueError:
        delay = 2.0
    proc = None
    for attempt in range(MODELS_EMPTY_RETRIES + 1):
        proc = run_captured([binary, "models"], timeout)
        if proc.returncode != 0 or proc.stdout.strip():
            return proc
        if attempt < MODELS_EMPTY_RETRIES:
            time.sleep(delay)
    return proc


def first_error(errors: list, stderr_tail: str) -> str:
    """Return the first non-empty error event, else the end of the stderr tail, as one line."""
    for error in errors or []:
        line = _one_line(error)
        if line:
            return line
    return _one_line(stderr_tail)[-DETAIL_MAX:]


def oc_line(level: str, skill: str, unit: str, tier: str, spec: str, kind: str, detail: str, log: str = "") -> str:
    """Build one OC-ERROR/OC-WARN line; the detail is collapsed to one line of at most 200 chars.

    level is "OC-ERROR" or "OC-WARN" ("error"/"warn" are accepted too). Empty
    fields print as "-" and spaces inside the five fields become "_", so every
    line has the same grep-able shape.
    """
    level = _one_line(level).upper()
    if not level.startswith("OC-"):
        level = "OC-" + level
    fields = [_one_line(value).replace(" ", "_") or "-" for value in (skill, unit, tier, spec, kind)]
    text = _one_line(detail) or "-"
    if len(text) > DETAIL_MAX:
        text = text[:DETAIL_MAX - 3] + "..."
    line = "%s %s %s tier=%s model=%s kind=%s :: %s" % tuple([level] + fields + [text])
    if log:
        line += " log=" + _one_line(log)
    return line


def log_line(path: Path, line: str) -> None:
    """Append one OC line to the run's oc-errors.jsonl as {"ts": ..., "line": ...}."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = json.dumps({"ts": round(time.time(), 3), "line": _one_line(line)})
    with open(str(path), "a", encoding="utf-8") as fh:
        fh.write(record + "\n")


def take_unreported(path: Path) -> list:
    """Return the OC lines logged since the previous call and mark them reported.

    The read offset lives next to the log in <name>.seen. A partly written last
    record is left for the next call; a log shorter than the offset is re-read
    from the start.
    """
    path = Path(path)
    seen = path.with_name(path.name + ".seen")
    try:
        size = path.stat().st_size
    except OSError:
        return []
    try:
        offset = int(seen.read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        offset = 0
    if offset > size:
        offset = 0
    with open(str(path), "rb") as fh:
        fh.seek(offset)
        data = fh.read(size - offset)
    end = data.rfind(b"\n") + 1
    lines = []
    for raw in data[:end].decode("utf-8", errors="replace").splitlines():
        try:
            record = json.loads(raw)
        except ValueError:
            continue
        if isinstance(record, dict) and isinstance(record.get("line"), str):
            lines.append(record["line"])
    if end:
        tmp = seen.with_name("%s.%d.tmp" % (seen.name, os.getpid()))
        tmp.write_text(str(offset + end), encoding="utf-8")
        os.replace(str(tmp), str(seen))
    return lines


def _breaker_file(state_dir, tier, spec) -> Path:
    digest = hashlib.sha1((str(tier) + "\n" + str(spec)).encode("utf-8")).hexdigest()[:16]
    return Path(state_dir) / BREAKER_DIR / (digest + ".json")


def _skip_count(entry_path) -> int:
    try:
        return len(entry_path.with_suffix(".skip").read_text(encoding="utf-8").splitlines())
    except OSError:
        return 0


def _read_entry(entry_path) -> dict:
    try:
        entry = json.loads(entry_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        entry = None
    return entry if isinstance(entry, dict) else {}


def _session() -> str:
    return os.environ.get(SESSION_ENV, "").strip()


def _stale(entry: dict) -> bool:
    """True for a switch or breaker record written by another Claude Code session.

    A new session (or a new flow, which resets the run state at init) starts on opencode again.
    Records without a session, and runs outside Claude Code, never go stale.
    """
    mine, theirs = _session(), str(entry.get("session") or "")
    return bool(mine and theirs and mine != theirs)


def _create_exclusive(path: Path, entry: dict) -> bool:
    """O_EXCL create of a JSON record; a stale record from another session is replaced. True when created."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            if not _stale(_read_entry(path)):
                return False
            for old in (path, path.with_suffix(".skip")):
                try:
                    old.unlink()
                except OSError:
                    pass
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(dict(entry, session=_session()), fh)
        return True
    return False


def reset_run_state(state_dir: Path) -> None:
    """Forget the switch to Claude, every open breaker and every throttle cooldown of this run."""
    state_dir = Path(state_dir)
    for path in [state_dir / SWITCH_FILE] + list(state_dir.glob("cooldown-*")):
        try:
            path.unlink()
        except OSError:
            pass
    folder = state_dir / BREAKER_DIR
    if folder.is_dir():
        for path in folder.iterdir():
            try:
                path.unlink()
            except OSError:
                pass


def breaker_trip(state_dir: Path, tier: str, spec: str, kind: str, detail: str) -> bool:
    """Open the run's breaker for tier+spec after a non-retryable failure.

    Returns True only for the call that opened it (that caller prints the
    OC-ERROR line); False when it was already open or kind is retryable.
    The O_EXCL create keeps this correct across parallel runner processes.
    """
    if kind not in NON_RETRYABLE:
        return False
    entry = {"tier": tier, "spec": spec, "kind": kind, "detail": _one_line(detail)[:DETAIL_MAX],
             "tripped_at": round(time.time(), 3)}
    return _create_exclusive(_breaker_file(state_dir, tier, spec), entry)


def breaker_open(state_dir: Path, tier: str, spec: str) -> dict:
    """Return {tier, spec, kind, detail, tripped_at, skipped} while the breaker is open, else {}."""
    path = _breaker_file(state_dir, tier, spec)
    if not path.exists():
        return {}
    read = _read_entry(path)
    if _stale(read):
        return {}
    entry = dict({"tier": tier, "spec": spec, "kind": "", "detail": ""}, **read)
    entry["skipped"] = _skip_count(path)
    return entry


def breaker_skip(state_dir: Path, tier: str, spec: str) -> int:
    """Count one unit skipped because the breaker is open; returns the new count (0 when closed)."""
    path = _breaker_file(state_dir, tier, spec)
    if not path.exists() or _stale(_read_entry(path)):
        return 0
    with open(str(path.with_suffix(".skip")), "a", encoding="utf-8") as fh:
        fh.write("1\n")
    return _skip_count(path)


def breaker_summary(state_dir: Path, skill: str) -> list:
    """One OC-ERROR kind=breaker line per open breaker that skipped units; print them at phase end."""
    folder = Path(state_dir) / BREAKER_DIR
    lines = []
    if not folder.is_dir():
        return lines
    for path in sorted(folder.glob("*.json")):
        entry = _read_entry(path)
        count = 0 if _stale(entry) else _skip_count(path)
        if count:
            detail = "%d units skipped after kind=%s: %s" % (count, entry.get("kind", ""), entry.get("detail", ""))
            lines.append(oc_line("OC-ERROR", skill, "breaker", entry.get("tier", ""), entry.get("spec", ""),
                                 "breaker", detail))
    return lines


def should_retry(kind: str, retries_done: int) -> bool:
    """True when a failed opencode run of this kind gets another attempt (at most OC_RETRIES)."""
    return kind in CONNECTION_KINDS and retries_done < OC_RETRIES


def retry_delay(retries_done: int) -> int:
    """Seconds to wait before retry number retries_done + 1; $HYBRID_OC_RETRY_DELAY_S overrides every delay (tests)."""
    override = os.environ.get(RETRY_DELAY_ENV, "").strip()
    if override.isdigit():
        return int(override)
    return RETRY_DELAYS_S[min(retries_done, len(RETRY_DELAYS_S) - 1)]


def switches_run(kind: str) -> bool:
    """True when a final failure of this kind moves the rest of a hybrid run to Claude."""
    return kind in CONNECTION_KINDS or kind in NON_RETRYABLE


def switch_to_claude(state_dir: Path, unit: str, tier: str, spec: str, kind: str, detail: str) -> bool:
    """Record that this run stops using opencode.

    Returns True only for the call that created the record (that caller prints
    switch_line); False when the run was already switched. The O_EXCL create
    keeps this correct across parallel runner processes. The record carries the
    Claude Code session id: a new session starts on opencode again, and so does
    every new flow (init calls reset_run_state).
    """
    entry = {"unit": unit, "tier": tier, "spec": spec, "kind": kind, "detail": _one_line(detail)[:DETAIL_MAX],
             "switched_at": round(time.time(), 3)}
    return _create_exclusive(Path(state_dir) / SWITCH_FILE, entry)


def run_switched(state_dir: Path) -> dict:
    """The switch record {unit, tier, spec, kind, detail, switched_at} once this run moved to Claude, else {}."""
    entry = _read_entry(Path(state_dir) / SWITCH_FILE)
    return {} if _stale(entry) else entry


def switch_line(skill: str, entry: dict) -> str:
    """The one OC-ERROR kind=switch line announcing that the rest of the run uses Claude FALLBACK_MODEL."""
    detail = "opencode %s: %s; the rest of this run uses Claude %s" % (
        entry.get("kind", ""), entry.get("detail", ""), FALLBACK_MODEL)
    return oc_line("OC-ERROR", skill, entry.get("unit", ""), entry.get("tier", ""), entry.get("spec", ""),
                   "switch", detail)


def cli(argv: list) -> int:
    """Command line; returns the exit code instead of exiting.

    config  print the config summary line; always exit 0 (safe for preloads)
    check   print the summary plus an OC-ERROR kind=config line; exit 1 when unusable
    mode M  print preset=<preset>; OC-WARN for "max", OC-ERROR and exit 2 when unknown
    reset D forget the switch to Claude, the breakers and the cooldowns in state dir D (a new flow)
    Every command takes --skill NAME for the skill field of its OC lines.
    """
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--skill", default="hybrid-skills", help="skill name printed in OC lines")
    parser = argparse.ArgumentParser(prog="hybrid_shared.py", description="Shared opencode config for the hybrid skills.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("config", parents=[common], help="print the config summary; always exit 0")
    sub.add_parser("check", parents=[common], help="print the summary; exit 1 when the config is unusable")
    mode_p = sub.add_parser("mode", parents=[common], help="map a run mode to a router preset")
    mode_p.add_argument("mode")
    reset_p = sub.add_parser("reset", parents=[common], help="start a new flow: clear the run's switch and breakers")
    reset_p.add_argument("state_dir")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    if args.cmd == "reset":
        reset_run_state(Path(args.state_dir))
        print("run state reset: switch to Claude, breakers and cooldowns cleared in %s" % args.state_dir)
        return 0

    if args.cmd == "mode":
        preset, note = mode_to_preset(args.mode)
        if not preset:
            print(oc_line("OC-ERROR", args.skill, "config", "", "", "config", note))
            return 2
        if note:
            print(oc_line("OC-WARN", args.skill, "config", "", "", "config", note))
        print("preset=" + preset)
        return 0

    tiers, problems = load_shared()
    print(config_summary(tiers, problems))
    if problems and args.cmd == "check":
        print(oc_line("OC-ERROR", args.skill, "config", "", "", "config", "; ".join(problems[:3])))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]))
