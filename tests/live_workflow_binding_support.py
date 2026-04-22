from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class BindingHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/v1/account/profile":
            body = json.dumps({"account": {"id": "acct-123"}, "account_id": "acct-123"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Trace-Id", "trace-abc")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/v1/account/preferences/acct-123?trace=trace-abc":
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/v1/account/preferences?account_id=acct-123":
            body = json.dumps({"ok": True, "mode": "query_binding"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/api/v1/account/preferences/"):
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/v1/account/preferences":
            self.send_response(404)
            self.end_headers()
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        payload = json.loads(body.decode("utf-8"))
        if payload.get("account_id") != "acct-123":
            self.send_response(400)
            self.end_headers()
            return
        response = json.dumps({"ok": True, "saved": payload.get("account_id")}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *_args: object) -> None:
        return


class binding_server:
    def __enter__(self) -> str:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), BindingHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)
