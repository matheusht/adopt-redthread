from __future__ import annotations

import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from adapters.live_replay.executor import execute_live_case
from adapters.live_replay.workflow_executor import execute_live_workflow_replay


class _StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/v1/json"):
            self._send_json({"ok": True, "kind": "json"})
            return
        if self.path.startswith("/api/v1/stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.write(b"data: hello-stream\n\n")
            self.wfile.flush()
            time.sleep(0.05)
            return
        if self.path.startswith("/api/v1/idle-stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            self.wfile.flush()
            time.sleep(0.2)
            return
        self.send_response(404)
        self.end_headers()

    def _send_json(self, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


class LiveStreamReplayTests(unittest.TestCase):
    def test_normal_json_response_still_completes(self) -> None:
        with _server() as base_url:
            result = execute_live_case(_case("json_step", f"{base_url}/api/v1/json"), 1, None, False, None, False)

            self.assertTrue(result["success"])
            self.assertEqual(result["status_code"], 200)
            self.assertEqual(result["response_json"], {"ok": True, "kind": "json"})
            self.assertNotIn("stream_opened", result)

    def test_stream_response_records_first_chunk_evidence(self) -> None:
        with _server() as base_url:
            result = execute_live_case(
                _case("stream_step", f"{base_url}/api/v1/stream"),
                1,
                None,
                False,
                None,
                False,
                stream_max_bytes=8,
            )

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "stream_open_partial_read")
            self.assertTrue(result["stream_opened"])
            self.assertEqual(result["first_chunk_bytes"], 8)
            self.assertEqual(result["first_chunk_preview"], "data: he")
            self.assertEqual(result["stream_read_budget_bytes"], 8)

    def test_workflow_replay_surfaces_stream_partial_read_narrative(self) -> None:
        with _server() as base_url:
            attack_plan = {
                "cases": [_case("stream_step", f"{base_url}/api/v1/stream")],
            }
            workflow_plan = {
                "plan_id": "stream-demo",
                "workflow_count": 1,
                "workflows": [
                    {
                        "workflow_id": "stream-flow",
                        "step_count": 1,
                        "workflow_context_requirements": {"workflow_class": "safe_read_workflow", "required_header_families": []},
                        "session_context_requirements": {},
                        "steps": [{"case_id": "stream_step", "depends_on_previous_step": False}],
                    }
                ],
            }

            summary = execute_live_workflow_replay(workflow_plan, attack_plan, timeout_seconds=1, stream_max_bytes=8)

            self.assertEqual(summary["aborted_workflow_count"], 1)
            self.assertEqual(summary["reason_counts"], {"stream_open_partial_read": 1})
            self.assertEqual(summary["workflow_failure_class_summary"], {"runtime_failure": 1})
            self.assertEqual(summary["stream_max_bytes"], 8)
            result = summary["results"][0]
            self.assertEqual(result["failure_reason_code"], "stream_open_partial_read")
            self.assertIn("opened a streaming response", result["failure_narrative"])
            evidence = result["results"][0]["workflow_evidence"]
            self.assertTrue(evidence["stream_opened"])
            self.assertEqual(evidence["first_chunk_preview"], "data: he")

    def test_timeout_still_happens_when_stream_never_sends_first_chunk(self) -> None:
        with _server() as base_url:
            result = execute_live_case(
                _case("idle_stream_step", f"{base_url}/api/v1/idle-stream"),
                0.05,
                None,
                False,
                None,
                False,
                stream_max_bytes=8,
            )

            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "timeout")
            self.assertNotIn("stream_opened", result)


class _server:
    def __enter__(self) -> str:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _StreamHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)


def _case(case_id: str, url: str) -> dict[str, object]:
    return {
        "case_id": case_id,
        "method": "GET",
        "path": "/ignored",
        "workflow_group": "stream",
        "workflow_step_index": 0,
        "execution_mode": "live_safe_read",
        "approval_mode": "auto",
        "allowed": True,
        "request_blueprint": {"url": url, "host": urlparse(url).netloc},
    }


if __name__ == "__main__":
    unittest.main()
