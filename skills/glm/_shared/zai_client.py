#!/usr/bin/env python3
"""zai_client -- one stdlib client for the Z.ai GLM API.

Canonical copy lives in skills/glm/_shared/; sync.sh vendors it into each
skill's scripts/. Reads keys and base URLs, never writes them anywhere.
"""

import http.client
import json
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASE = "https://api.z.ai/api/coding/paas/v4"
EFFORTS = ("low", "high", "max")
THROTTLE_CODES = ("1302", "1305")
BACKOFF_BASE = 1.0
BACKOFF_CAP = 30.0


def find_base(explicit: str = "") -> str:
    for v in (explicit, os.environ.get("ZAI_BASE_URL"), os.environ.get("GLM_BASE_URL")):
        v = (v or "").strip().rstrip("/")
        if v:
            return v
    return DEFAULT_BASE


def route_of(base: str) -> str:
    return "anthropic" if "/anthropic" in (base or "").lower() else "openai"


def endpoint_of(base: str, route: str) -> str:
    base = (base or "").rstrip("/")
    if route == "anthropic":
        return base if base.endswith("/messages") else base + "/v1/messages"
    return base if base.endswith("/chat/completions") else base + "/chat/completions"


KEY_ENV = ("ZAI_API_KEY", "Z_AI_API_KEY", "GLM_API_KEY", "ZHIPUAI_API_KEY",
           "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY")
KEY_FIELDS = ("ZAI_API_KEY", "GLM_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY",
              "apiKey", "api_key", "key")
KEY_FILES = ("~/.local/share/opencode/auth.json", "~/.config/opencode/auth.json",
             "~/.config/opencode/opencode.json", "./opencode.json",
             "~/.claude/settings.json", "~/.claude/settings.local.json",
             "~/.zcode/settings.json", "~/.zcode/auth.json", "~/.zcode/config.json")


def _walk_for_key(obj, depth=0):
    """Take a key only from a field whose name says it is one."""
    if depth > 6:
        return None
    if isinstance(obj, dict):
        for f in KEY_FIELDS:
            v = obj.get(f)
            if isinstance(v, str) and len(v) >= 16 and " " not in v:
                return v
        items = list(obj.values())
    elif isinstance(obj, list):
        items = obj
    else:
        return None
    for v in items:
        got = _walk_for_key(v, depth + 1)
        if got:
            return got
    return None


def find_key(extra_env: tuple = ()) -> tuple:
    """Return (key, source) or (None, None)."""
    for name in tuple(extra_env) + KEY_ENV:
        v = (os.environ.get(name) or "").strip()
        if v:
            return v, "env:" + name
    for p in KEY_FILES:
        path = os.path.expanduser(p) if p.startswith("~") else os.path.join(os.getcwd(), p[2:])
        try:
            with open(path, encoding="utf-8") as f:
                obj = json.load(f)
        except (OSError, ValueError):
            continue
        got = _walk_for_key(obj)
        if got:
            return got, path
    return None, None


class Gate:
    """AIMD concurrency width shared by every thread of one process."""

    def __init__(self, width: int):
        self.max = max(1, int(width))
        self.width = self.max
        self.live = 0
        self.clean = 0
        self.cond = threading.Condition()

    def __enter__(self):
        with self.cond:
            while self.live >= self.width:
                self.cond.wait()
            self.live += 1
        return self

    def __exit__(self, *exc):
        with self.cond:
            self.live -= 1
            self.cond.notify_all()
        return False

    def throttled(self) -> int:
        with self.cond:
            self.width = max(1, self.width // 2)
            self.clean = 0
            return self.width

    def ok(self) -> int:
        with self.cond:
            self.clean += 1
            if self.clean >= self.width:
                self.clean = 0
                if self.width < self.max:
                    self.width += 1
                    self.cond.notify_all()
            return self.width


class ApiError(Exception):
    """HTTP or Z.ai business failure; status 0 means no HTTP response."""

    def __init__(self, status, code="", message="", retry_after=None):
        self.status = int(status or 0)
        self.code = str(code or "")
        self.message = str(message or "")
        self.retry_after = retry_after
        Exception.__init__(self, "HTTP %d code %s: %s"
                           % (self.status, self.code or "-", self.message[:300]))

    @property
    def throttle(self):
        return self.status == 429 or self.code in THROTTLE_CODES


def _error_of(text):
    """(Z.ai code, message) from a response body; code is "" when there is none."""
    try:
        obj = json.loads(text)
    except ValueError:
        return "", text.strip()[:300]
    if not isinstance(obj, dict):
        return "", ""
    err = obj.get("error") if isinstance(obj.get("error"), dict) else obj
    code = err.get("code")
    code = "" if code in (None, 0, 200, "0", "200") else str(code)
    return code, str(err.get("message") or err.get("msg") or "")


_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_PROXIED = urllib.request.build_opener()


def _delay(attempt, retry_after=None):
    """Seconds to wait before retry number `attempt`; Retry-After wins."""
    if retry_after is not None:
        try:
            return min(BACKOFF_CAP, max(0.0, float(retry_after)))
        except (TypeError, ValueError):
            pass
    return min(BACKOFF_CAP, BACKOFF_BASE * (2 ** attempt)) * (0.5 + random.random())


class Client:
    """Thread-safe; share one instance (and its Gate) across a whole fan-out."""

    def __init__(self, key: str, base: str = "", route: str = "", timeout: int = 900, gate: Gate = None, user_agent: str = "glm-skill"):
        self.key = key
        self.base = find_base(base)
        self.route = route or route_of(self.base)
        self.url = endpoint_of(self.base, self.route)
        self.timeout = timeout
        self.gate = gate if gate is not None else Gate(64)
        self.user_agent = user_agent
        host = urllib.parse.urlsplit(self.url).hostname or ""
        self._opener = _DIRECT if host in ("127.0.0.1", "localhost") else _PROXIED
        self._lock = threading.Lock()
        self._stats = {"calls": 0, "ok": 0, "retries": 0, "throttles": 0, "errors": 0,
                       "in_tok": 0, "out_tok": 0, "cache_read": 0}

    def _bump(self, name):
        with self._lock:
            self._stats[name] += 1

    def _headers(self):
        h = {"Content-Type": "application/json", "Accept": "application/json",
             "User-Agent": self.user_agent, "Authorization": "Bearer " + self.key}
        if self.route == "anthropic":
            h["x-api-key"] = self.key
            h["anthropic-version"] = "2023-06-01"
        return h

    def _payload(self, model, effort, system, user, max_tokens, temperature):
        if self.route == "anthropic":
            p = {"model": model, "max_tokens": max_tokens,
                 "messages": [{"role": "user", "content": user}]}
            if system:
                p["system"] = system
        else:
            msgs = [{"role": "system", "content": system}] if system else []
            msgs.append({"role": "user", "content": user})
            p = {"model": model, "max_tokens": max_tokens, "messages": msgs}
        p["reasoning_effort"] = effort
        if temperature is not None:
            p["temperature"] = temperature
        return p

    def _post(self, payload):
        self._bump("calls")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, headers=self._headers(), method="POST")
        try:
            with self._opener.open(req, timeout=self.timeout) as r:
                text = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")
            code, msg = _error_of(text)
            ra = e.headers.get("Retry-After") if e.headers is not None else None
            raise ApiError(e.code, code, msg or str(e.reason), ra)
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            raise ApiError(0, "", str(e))
        code, msg = _error_of(text)
        if code:
            raise ApiError(200, code, msg)
        try:
            obj = json.loads(text)
        except ValueError:
            raise ApiError(200, "", "invalid JSON: " + text[:200])
        if not isinstance(obj, dict):
            raise ApiError(200, "", "unexpected response: " + text[:200])
        return obj

    def _done(self, obj):
        u = obj.get("usage") or {}
        det = u.get("prompt_tokens_details") or {}
        with self._lock:
            s = self._stats
            s["ok"] += 1
            s["in_tok"] += int(u.get("prompt_tokens") or u.get("input_tokens") or 0)
            s["out_tok"] += int(u.get("completion_tokens") or u.get("output_tokens") or 0)
            s["cache_read"] += int(det.get("cached_tokens") or u.get("cache_read_input_tokens") or 0)
        if self.route == "anthropic":
            return "".join(b.get("text") or "" for b in obj.get("content") or []
                           if isinstance(b, dict) and b.get("type") == "text")
        try:
            return obj["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ApiError(200, "", "response has no choices")

    def call(self, model: str, effort: str, system: str, user: str, max_tokens: int, temperature: float = None, retries: int = 4) -> str:
        if effort not in EFFORTS:
            raise ValueError("effort must be low, high or max, got %r" % (effort,))
        payload = self._payload(model, effort, system, user, max_tokens, temperature)
        attempt = 0
        while True:
            try:
                with self.gate:
                    obj = self._post(payload)
            except ApiError as e:
                if e.throttle:
                    self.gate.throttled()
                    self._bump("throttles")
                if not (e.throttle or e.status == 0 or e.status >= 500) or attempt >= retries:
                    self._bump("errors")
                    raise
                attempt += 1
                self._bump("retries")
                time.sleep(_delay(attempt, e.retry_after))
                continue
            self.gate.ok()
            return self._done(obj)

    def stats(self) -> dict:
        with self._lock:
            out = dict(self._stats)
        out["width"] = self.gate.width
        return out
