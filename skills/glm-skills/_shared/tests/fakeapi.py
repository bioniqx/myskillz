"""fakeapi -- scripted Z.ai stand-in on 127.0.0.1 for tests (no network)."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def chat(text, prompt_tokens=10, completion_tokens=5):
    return {"status": 200,
            "body": {"choices": [{"message": {"role": "assistant", "content": text}}],
                     "usage": {"prompt_tokens": prompt_tokens,
                               "completion_tokens": completion_tokens}}}


def messages(text, input_tokens=10, output_tokens=5):
    return {"status": 200,
            "body": {"type": "message", "content": [{"type": "text", "text": text}],
                     "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}}}


def fail(status, code="", message="error", headers=None):
    return {"status": status, "body": {"error": {"code": code, "message": message}},
            "headers": headers or {}}


class FakeApi:
    """Answers each POST with the next script entry
    ({"status", "body", "headers", "delay"}); the last entry repeats.
    Records every request and the peak number of concurrent requests."""

    def __init__(self, script: list):
        self.script = list(script)
        self.requests = []
        self.live = 0
        self.peak = 0
        self.lock = threading.Lock()
        self.server = None
        self.thread = None
        self.root = ""
        self.base = ""

    def next_reply(self):
        with self.lock:
            if len(self.script) > 1:
                return self.script.pop(0)
            return self.script[0] if self.script else fail(500, "", "script empty")

    def start(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(n).decode("utf-8", "replace")
                try:
                    body = json.loads(raw)
                except ValueError:
                    body = raw
                with fake.lock:
                    fake.requests.append({"path": self.path, "body": body,
                                          "headers": {k.lower(): v for k, v in self.headers.items()}})
                    fake.live += 1
                    fake.peak = max(fake.peak, fake.live)
                try:
                    reply = fake.next_reply()
                    if reply.get("delay"):
                        time.sleep(reply["delay"])
                    data = reply.get("body", {})
                    data = (data if isinstance(data, str) else json.dumps(data)).encode("utf-8")
                    self.send_response(reply.get("status", 200))
                    self.send_header("Content-Type", "application/json")
                    for k, v in (reply.get("headers") or {}).items():
                        self.send_header(k, v)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                finally:
                    with fake.lock:
                        fake.live -= 1

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.root = "http://127.0.0.1:%d" % self.server.server_address[1]
        self.base = self.root + "/api/coding/paas/v4"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stop()
        return False


def start_fake(script: list) -> FakeApi:
    return FakeApi(script).start()
