#!/usr/bin/env python3
"""serve.py — Local server for comparison pages: static files + decision read/write API.

  cd shot-polish && python3 serve.py [port, default 8765]  → http://localhost:8765/

Endpoints:
GET  /api/decisions     Read shot-polish/decisions.json (returns empty list if missing)
POST /api/decisions     Write shot-polish/decisions.json (auto-saved on selection click)
GET/POST /api/final-review  Read/write shot-polish/final-review.json (final confirmation page results)
"""

import http.server
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DECISIONS_FILE = ROOT / "decisions.json"
FINAL_FILE = ROOT / "final-review.json"


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path == "/api/decisions":
            self.send_json(self.read_file(DECISIONS_FILE))
        elif self.path == "/api/final-review":
            self.send_json(self.read_file(FINAL_FILE))
        else:
            super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception as e:
            self.send_error(400, f"invalid json: {e}")
            return

        if self.path == "/api/decisions":
            DECISIONS_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self.send_json({"ok": True, "saved": "decisions.json"})
        elif self.path == "/api/final-review":
            FINAL_FILE.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            self.send_json({"ok": True, "saved": "final-review.json"})
        else:
            self.send_error(404, "unknown api endpoint")

    def read_file(self, path: Path):
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def send_json(self, data):
        blob = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Comparison server running at http://localhost:{port}/ (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
