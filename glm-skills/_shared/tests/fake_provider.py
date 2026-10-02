"""Stdlib fake OpenAI-compatible chat provider for the OpenCode contract tests.

Serves GET <base>/models and POST <base>/chat/completions (SSE when "stream" is true, JSON
otherwise) and logs every request body. Rules are matched in order against each chat request;
the first match wins. Rule keys:
  match   substring that must occur in the JSON-encoded request body
  unless  substring that must not occur in it
  fresh   true: only when the request carries no role=tool message
  status  HTTP error status to return, with `body` as the JSON error payload
  delay   seconds to wait after the response headers are sent
  text    assistant text to return
  tool    candidate tool names; the first one offered in the request is called
  args    tool-call arguments; when absent they are filled from the tool schema via `fill`
  fill    {property-name substring: value} used to fill tool-call arguments
The default reply is the text "ok".
"""

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

MODEL = "fake-model"
USAGE = {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


def tool_names(body: dict) -> list:
    names = []
    for tool in body.get("tools") or []:
        fn = tool.get("function") if isinstance(tool, dict) else None
        if isinstance(fn, dict) and fn.get("name"):
            names.append(fn["name"])
    return names


def message_texts(body: dict, role: str) -> list:
    texts = []
    for msg in body.get("messages") or []:
        if not isinstance(msg, dict) or msg.get("role") != role:
            continue
        content = msg.get("content")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    texts.append(part["text"])
    return texts


def _schema(body: dict, name: str) -> dict:
    for tool in body.get("tools") or []:
        fn = tool.get("function") if isinstance(tool, dict) else None
        if isinstance(fn, dict) and fn.get("name") == name:
            return fn.get("parameters") or {}
    return {}


def fill_args(schema: dict, fill: dict) -> dict:
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    args = {}
    for key, spec in props.items():
        value = None
        for needle, candidate in (fill or {}).items():
            if needle.lower() in key.lower():
                value = candidate
                break
        if value is None and key in required:
            kind = spec.get("type") if isinstance(spec, dict) else None
            if kind == "boolean":
                value = False
            elif kind in ("integer", "number"):
                value = 1
            elif kind == "array":
                value = []
            elif kind == "object":
                value = {}
            else:
                value = "contract"
        if value is not None:
            args[key] = value
    return args


def choose(rules: list, body: dict) -> dict:
    raw = json.dumps(body)
    has_tool_msg = any(isinstance(m, dict) and m.get("role") == "tool" for m in body.get("messages") or [])
    offered = tool_names(body)
    for rule in rules:
        if rule.get("match") and rule["match"] not in raw:
            continue
        if rule.get("unless") and rule["unless"] in raw:
            continue
        if rule.get("fresh") and has_tool_msg:
            continue
        delay = rule.get("delay", 0)
        if rule.get("tool"):
            name = next((n for n in rule["tool"] if n in offered), None)
            if name is None:
                continue
            args = rule.get("args")
            if args is None:
                args = fill_args(_schema(body, name), rule.get("fill") or {})
            return {"tool": name, "args": args, "delay": delay}
        if rule.get("status"):
            return {"status": int(rule["status"]),
                    "body": rule.get("body") or {"error": {"message": "fake error"}}, "delay": delay}
        return {"text": rule.get("text", "ok"), "delay": delay}
    return {"text": "ok", "delay": 0}


def _call(reply: dict, cid: str) -> dict:
    return {"id": cid + "-call", "type": "function",
            "function": {"name": reply["tool"], "arguments": json.dumps(reply["args"])}}


def stream_chunks(reply: dict, cid: str) -> list:
    base = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": MODEL}

    def chunk(delta, finish=None, usage=None):
        item = dict(base, choices=[{"index": 0, "delta": delta, "finish_reason": finish}])
        if usage:
            item["usage"] = usage
        return item

    if "tool" in reply:
        call = dict(_call(reply, cid), index=0)
        return [chunk({"role": "assistant", "content": None, "tool_calls": [call]}),
                chunk({}, "tool_calls", USAGE)]
    return [chunk({"role": "assistant", "content": reply["text"]}), chunk({}, "stop", USAGE)]


def completion(reply: dict, cid: str) -> dict:
    message = {"role": "assistant", "content": reply.get("text")}
    finish = "stop"
    if "tool" in reply:
        message["content"] = None
        message["tool_calls"] = [_call(reply, cid)]
        finish = "tool_calls"
    return {"id": cid, "object": "chat.completion", "created": int(time.time()), "model": MODEL,
            "choices": [{"index": 0, "message": message, "finish_reason": finish}], "usage": USAGE}


class _Server(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _Handler(BaseHTTPRequestHandler):
    server_version = "FakeProvider/1.0"

    def log_message(self, fmt, *args):
        pass

    def _read_body(self) -> bytes:
        if "chunked" in (self.headers.get("Transfer-Encoding") or "").lower():
            parts = []
            while True:
                size_line = self.rfile.readline().strip().split(b";")[0]
                size = int(size_line or b"0", 16)
                if size == 0:
                    self.rfile.readline()
                    break
                parts.append(self.rfile.read(size))
                self.rfile.readline()
            return b"".join(parts)
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def _headers(self, status, content_type, length=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.flush()

    def _json(self, status, payload, delay=0.0):
        data = json.dumps(payload).encode("utf-8")
        self._headers(status, "application/json", len(data))
        if delay:
            time.sleep(delay)
        self.wfile.write(data)
        self.wfile.flush()

    def do_GET(self):
        try:
            if self.path.rstrip("/").endswith("/models"):
                self._json(200, {"object": "list",
                                 "data": [{"id": MODEL, "object": "model", "owned_by": "fake"}]})
            else:
                self._json(404, {"error": {"message": "not found: " + self.path}})
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        provider = self.server.provider
        try:
            body = json.loads(self._read_body().decode("utf-8") or "{}")
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}
        cid = provider.record(self.path, body)
        try:
            if not self.path.rstrip("/").endswith("/chat/completions"):
                self._json(404, {"error": {"message": "not found: " + self.path}})
                return
            reply = choose(provider.rules, body)
            delay = float(reply.get("delay") or 0)
            if "status" in reply:
                self._json(reply["status"], reply["body"], delay)
                return
            if body.get("stream"):
                self._headers(200, "text/event-stream")
                if delay:
                    time.sleep(delay)
                for item in stream_chunks(reply, cid):
                    self.wfile.write(("data: %s\n\n" % json.dumps(item)).encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            else:
                self._json(200, completion(reply, cid), delay)
        except (BrokenPipeError, ConnectionResetError):
            pass


class FakeProvider:
    def __init__(self, rules: list = None, host: str = "127.0.0.1", port: int = 0):
        self.rules = list(rules or [])
        self.requests = []
        self._lock = threading.Lock()
        self._counter = 0
        self._server = _Server((host, port), _Handler)
        self._server.provider = self
        self._thread = None

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def url(self) -> str:
        return "http://127.0.0.1:%d/v1" % self.port

    def start(self) -> str:
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self.url

    def stop(self) -> None:
        if self._thread is not None:
            self._server.shutdown()
            self._thread.join(5)
            self._thread = None
        self._server.server_close()

    def record(self, path: str, body: dict) -> str:
        with self._lock:
            self._counter += 1
            self.requests.append({"path": path, "body": body})
            return "chatcmpl-fake-%d" % self._counter

    def bodies(self) -> list:
        with self._lock:
            return [r["body"] for r in self.requests if r["path"].rstrip("/").endswith("/chat/completions")]


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(prog="fake_provider.py", description="fake OpenAI-compatible provider")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--rules", default="", help="JSON file holding a list of rules")
    a = parser.parse_args(argv)
    rules = []
    if a.rules:
        with open(a.rules) as fh:
            rules = json.load(fh)
    fake = FakeProvider(rules, port=a.port)
    print("FAKE_PROVIDER %s" % fake.url)
    print("NEXT: set an openai-compatible provider baseURL to %s; Ctrl-C stops the server" % fake.url)
    sys.stdout.flush()
    try:
        fake._server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        fake._server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
