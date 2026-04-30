from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.bridge.workflow import DEFAULT_REDTHREAD_PYTHON, DEFAULT_REDTHREAD_SRC, run_bridge_workflow
from scripts.build_evidence_report import build_evidence_report

CHAT_ID = "chat-ref-123"
SESSION_ID = "session-ref-456"


def run_reviewed_write_reference(
    output_dir: str | Path = "runs/reviewed_write_reference",
    *,
    redthread_python: str | Path = DEFAULT_REDTHREAD_PYTHON,
    redthread_src: str | Path = DEFAULT_REDTHREAD_SRC,
    run_dryrun: bool = True,
) -> dict[str, Any]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    with reviewed_write_reference_server() as base_url:
        input_har = output_root / "reviewed_write_reference.har"
        input_har.write_text(json.dumps(_reference_har(base_url), indent=2) + "\n")
        host = base_url.replace("http://", "")
        summary = run_bridge_workflow(
            input_har,
            ingestion="zapi",
            output_dir=output_root,
            run_dryrun=run_dryrun,
            run_live_workflow_replay=True,
            auth_context=_auth_context(host),
            allow_reviewed_auth=True,
            write_context=_write_context(base_url, host),
            allow_reviewed_writes=True,
            binding_overrides=_binding_overrides(),
            redthread_python=redthread_python,
            redthread_src=redthread_src,
        )

    build_evidence_report(output_root, output_root / "evidence_report.md")
    return summary


class ReviewedWriteReferenceHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/chats":
            self._send_json({"chats": []}, status=200, headers={"Set-Cookie": f"tennisbot_session={SESSION_ID}; Path=/; HttpOnly"})
            return
        if self.path in {"/api/chats/history-ref-001", "/api/chats/history-ref-002"}:
            self._send_json({"chat": {"id": self.path.rsplit("/", 1)[-1], "messages": []}})
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        payload = self._read_json_body()
        if self.path == "/api/chats":
            if payload.get("title") != "ATP Tennis reference":
                self._send_json({"error": "unexpected_create_payload"}, status=400)
                return
            self._send_json(
                {"chat": {"id": CHAT_ID, "sessionId": SESSION_ID}},
                status=201,
                headers={"Set-Cookie": f"tennisbot_session={SESSION_ID}; Path=/; HttpOnly"},
            )
            return
        if self.path == "/api/chat":
            cookie = self.headers.get("cookie", "")
            if payload.get("chatId") != CHAT_ID or payload.get("id") != CHAT_ID or SESSION_ID not in cookie:
                self._send_json({"error": "binding_not_applied"}, status=400)
                return
            self._send_json({"ok": True, "chatId": payload.get("chatId"), "message_count": len(payload.get("messages", []))})
            return
        self.send_response(404)
        self.end_headers()

    def _read_json_body(self) -> dict[str, Any]:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if not body:
            return {}
        return json.loads(body.decode("utf-8"))

    def _send_json(self, payload: dict[str, Any], *, status: int = 200, headers: dict[str, str] | None = None) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


class reviewed_write_reference_server:
    def __enter__(self) -> str:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ReviewedWriteReferenceHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)


def _reference_har(base_url: str) -> dict[str, Any]:
    return {
        "log": {
            "entries": [
                _entry("GET", f"{base_url}/api/chats", headers=[{"name": "cookie", "value": "tennisbot_session=seed"}]),
                _entry(
                    "POST",
                    f"{base_url}/api/chats",
                    headers=[{"name": "cookie", "value": "tennisbot_session=seed"}],
                    body={"title": "ATP Tennis reference"},
                    status=201,
                ),
                _entry("GET", f"{base_url}/api/chats/history-ref-001", headers=[{"name": "cookie", "value": "tennisbot_session=seed"}]),
                _entry(
                    "POST",
                    f"{base_url}/api/chat",
                    headers=[{"name": "cookie", "value": "tennisbot_session=seed"}],
                    body={
                        "chatId": "captured-chat-id",
                        "id": "captured-message-id",
                        "messages": [{"id": "captured-message-id", "role": "user", "parts": ["Who won the ATP final?"]}],
                        "trigger": "submit-message",
                    },
                ),
                _entry("GET", f"{base_url}/api/chats/history-ref-002", headers=[{"name": "cookie", "value": "tennisbot_session=seed"}]),
            ]
        }
    }


def _entry(
    method: str,
    url: str,
    *,
    headers: list[dict[str, str]] | None = None,
    body: dict[str, Any] | None = None,
    status: int = 200,
) -> dict[str, Any]:
    request: dict[str, Any] = {
        "method": method,
        "url": url,
        "headers": headers or [],
        "queryString": [],
    }
    if body is not None:
        request["postData"] = {"mimeType": "application/json", "text": json.dumps(body)}
    return {
        "request": request,
        "response": {"status": status, "content": {"mimeType": "application/json"}},
    }


def _auth_context(host: str) -> dict[str, Any]:
    return {
        "approved": True,
        "target_hosts": [host],
        "allowed_header_names": ["cookie"],
        "headers": {"cookie": "tennisbot_session=seed"},
    }


def _write_context(base_url: str, host: str) -> dict[str, Any]:
    return {
        "approved": True,
        "target_env": "staging",
        "target_hosts": [host],
        "target_base_url": base_url,
        "case_approvals": {
            "post_api_chats": {
                "method": "POST",
                "path": "/api/chats",
                "json_body": {"title": "ATP Tennis reference"},
                "headers": {"cookie": "tennisbot_session=seed"},
            },
            "post_api_chat": {
                "method": "POST",
                "path": "/api/chat",
                "json_body": {
                    "chatId": "pending-chat-id",
                    "id": "pending-message-id",
                    "messages": [{"id": "pending-message-id", "role": "user", "parts": ["Who won the ATP final?"]}],
                    "trigger": "submit-message",
                },
                "headers": {"cookie": "tennisbot_session={{SESSION_ID}}"},
                "use_bound_body_json": True,
                "use_bound_headers": True,
            },
        },
    }


def _binding_overrides() -> dict[str, Any]:
    return {
        "case_bindings": {
            "post_api_chat": {
                "replace_response_bindings": [
                    {
                        "binding_id": "chat_id_from_post_api_chats",
                        "source_case_id": "post_api_chats",
                        "source_type": "response_json",
                        "source_key": "chat.id",
                        "target_field": "request_body_json",
                        "target_path": "chatId",
                    },
                    {
                        "binding_id": "msg_id_from_post_api_chats",
                        "source_case_id": "post_api_chats",
                        "source_type": "response_json",
                        "source_key": "chat.id",
                        "target_field": "request_body_json",
                        "target_path": "id",
                    },
                    {
                        "binding_id": "session_id_from_post_api_chats",
                        "source_case_id": "post_api_chats",
                        "source_type": "response_json",
                        "source_key": "chat.sessionId",
                        "target_field": "request_header",
                        "target_path": "cookie",
                        "placeholder": "{{SESSION_ID}}",
                    },
                ]
            }
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deterministic reviewed-write reference demo with one operator command.")
    parser.add_argument("--output-dir", default="runs/reviewed_write_reference", help="Directory to write generated artifacts")
    parser.add_argument("--redthread-python", default=str(DEFAULT_REDTHREAD_PYTHON))
    parser.add_argument("--redthread-src", default=str(DEFAULT_REDTHREAD_SRC))
    parser.add_argument("--skip-dryrun", action="store_true", help="Skip RedThread dry-run; replay evaluation still runs")
    args = parser.parse_args()

    summary = run_reviewed_write_reference(
        args.output_dir,
        redthread_python=args.redthread_python,
        redthread_src=args.redthread_src,
        run_dryrun=not args.skip_dryrun,
    )
    print(json.dumps(summary, indent=2))
    print(f"evidence report -> {Path(args.output_dir) / 'evidence_report.md'}")


if __name__ == "__main__":
    main()
