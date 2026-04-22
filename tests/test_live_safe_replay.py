from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from adapters.bridge.live_attack import build_live_attack_plan
from adapters.bridge.workflow import run_bridge_workflow
from adapters.live_replay.executor import execute_live_safe_replay
from adapters.zapi.loader import build_fixture_bundle


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        auth = self.headers.get("Authorization")
        if self.path.startswith("/api/v1/public/profile"):
            body = b'{"ok":true,"profile":"demo"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/api/v1/private/profile") and auth == "Bearer demo-token":
            body = b'{"ok":true,"profile":"private"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(401 if self.path.startswith("/api/v1/private/profile") else 404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        auth = self.headers.get("Authorization")
        content_type = self.headers.get("Content-Type")
        if self.path.startswith("/api/v1/user/preferences") and auth == "Bearer stage-token" and content_type == "application/json":
            body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            payload = json.loads(body.decode("utf-8")) if body else {}
            if payload.get("theme") == "dark":
                response = b'{"ok":true,"saved":true}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)
                return
        self.send_response(400 if self.path.startswith("/api/v1/user/preferences") else 404)
        self.end_headers()

    def log_message(self, *_args: object) -> None:
        return


class LiveSafeReplayTests(unittest.TestCase):
    def test_executor_runs_only_allowed_safe_read_case(self) -> None:
        with _server() as base_url, tempfile.TemporaryDirectory() as tmp:
            har_path = _write_har(Path(tmp) / "safe_read.har", base_url)
            bundle = build_fixture_bundle(har_path)
            plan = build_live_attack_plan(bundle)
            summary = execute_live_safe_replay(plan)

            self.assertEqual(plan["allowed_case_count"], 1)
            self.assertEqual(summary["executed_case_count"], 1)
            self.assertEqual(summary["success_count"], 1)
            self.assertEqual(summary["results"][0]["status_code"], 200)

    def test_reviewed_auth_case_needs_approved_auth_context(self) -> None:
        with _server() as base_url, tempfile.TemporaryDirectory() as tmp:
            har_path = _write_har(Path(tmp) / "auth_safe_read.har", base_url, include_auth=True)
            bundle = build_fixture_bundle(har_path)
            plan = build_live_attack_plan(bundle)

            without_auth = execute_live_safe_replay(plan, allow_reviewed_auth=True)
            self.assertEqual(without_auth["executed_case_count"], 0)

            auth_context = {
                "approved": True,
                "target_hosts": [base_url.replace("http://", "")],
                "allowed_header_names": ["authorization"],
                "headers": {"authorization": "Bearer demo-token"},
            }
            with_auth = execute_live_safe_replay(plan, auth_context=auth_context, allow_reviewed_auth=True)

            self.assertEqual(with_auth["executed_case_count"], 1)
            self.assertEqual(with_auth["success_count"], 1)
            self.assertTrue(with_auth["results"][0]["auth_applied"])
            self.assertIn("authorization", with_auth["results"][0]["header_names_sent"])

    def test_reviewed_write_case_needs_staging_write_context(self) -> None:
        with _server() as base_url, tempfile.TemporaryDirectory() as tmp:
            har_path = _write_har(Path(tmp) / "write_review.har", base_url, write_mode=True)
            bundle = build_fixture_bundle(har_path)
            plan = build_live_attack_plan(bundle)

            without_write_context = execute_live_safe_replay(plan, allow_reviewed_writes=True)
            self.assertEqual(without_write_context["executed_case_count"], 0)

            write_context = {
                "approved": True,
                "target_env": "staging",
                "target_hosts": [base_url.replace("http://", "")],
                "case_approvals": {
                    "post_api_v1_user_preferences": {
                        "method": "POST",
                        "path": "/api/v1/user/preferences",
                        "headers": {"authorization": "Bearer stage-token"},
                        "json_body": {"theme": "dark"},
                    }
                },
            }
            with_write_context = execute_live_safe_replay(
                plan,
                write_context=write_context,
                allow_reviewed_writes=True,
            )

            self.assertEqual(with_write_context["executed_case_count"], 1)
            self.assertEqual(with_write_context["success_count"], 1)
            self.assertEqual(with_write_context["results"][0]["method"], "POST")
            self.assertIn("authorization", with_write_context["results"][0]["header_names_sent"])

    def test_workflow_can_emit_live_safe_replay_artifact(self) -> None:
        with _server() as base_url, tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            har_path = _write_har(root / "safe_read.har", base_url)
            output_dir = root / "workflow"
            summary = run_bridge_workflow(
                har_path,
                ingestion="zapi",
                output_dir=output_dir,
                run_dryrun=False,
                run_live_safe_replay=True,
                redthread_python="../redthread/.venv/bin/python",
                redthread_src="../redthread/src",
            )

            replay = json.loads((output_dir / "live_safe_replay.json").read_text())
            self.assertTrue(summary["live_safe_replay_executed"])
            self.assertEqual(summary["live_safe_replay_count"], 1)
            self.assertEqual(replay["success_count"], 1)

    def test_workflow_can_run_reviewed_auth_safe_read(self) -> None:
        with _server() as base_url, tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            har_path = _write_har(root / "auth_safe_read.har", base_url, include_auth=True)
            auth_context = {
                "approved": True,
                "target_hosts": [base_url.replace("http://", "")],
                "allowed_header_names": ["authorization"],
                "headers": {"authorization": "Bearer demo-token"},
            }
            auth_path = root / "auth_context.json"
            auth_path.write_text(json.dumps(auth_context, indent=2) + "\n")
            output_dir = root / "workflow"
            summary = run_bridge_workflow(
                har_path,
                ingestion="zapi",
                output_dir=output_dir,
                run_dryrun=False,
                run_live_safe_replay=True,
                auth_context=auth_path,
                allow_reviewed_auth=True,
                redthread_python="../redthread/.venv/bin/python",
                redthread_src="../redthread/src",
            )

            replay = json.loads((output_dir / "live_safe_replay.json").read_text())
            self.assertTrue(summary["live_safe_replay_executed"])
            self.assertTrue(summary["live_safe_replay_used_auth_context"])
            self.assertEqual(summary["live_safe_replay_count"], 1)
            self.assertEqual(replay["success_count"], 1)

    def test_workflow_can_run_reviewed_staging_write(self) -> None:
        with _server() as base_url, tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            har_path = _write_har(root / "write_review.har", base_url, write_mode=True)
            write_context = {
                "approved": True,
                "target_env": "staging",
                "target_hosts": [base_url.replace("http://", "")],
                "case_approvals": {
                    "post_api_v1_user_preferences": {
                        "method": "POST",
                        "path": "/api/v1/user/preferences",
                        "headers": {"authorization": "Bearer stage-token"},
                        "json_body": {"theme": "dark"},
                    }
                },
            }
            write_path = root / "write_context.json"
            write_path.write_text(json.dumps(write_context, indent=2) + "\n")
            output_dir = root / "workflow"
            summary = run_bridge_workflow(
                har_path,
                ingestion="zapi",
                output_dir=output_dir,
                run_dryrun=False,
                run_live_safe_replay=True,
                write_context=write_path,
                allow_reviewed_writes=True,
                redthread_python="../redthread/.venv/bin/python",
                redthread_src="../redthread/src",
            )

            replay = json.loads((output_dir / "live_safe_replay.json").read_text())
            self.assertTrue(summary["live_safe_replay_executed"])
            self.assertTrue(summary["live_safe_replay_used_write_context"])
            self.assertEqual(summary["live_safe_replay_count"], 1)
            self.assertEqual(replay["success_count"], 1)

    
class _server:
    def __enter__(self) -> str:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)


def _write_har(path: Path, base_url: str, *, include_auth: bool = False, write_mode: bool = False) -> str:
    headers = [{"name": "accept", "value": "application/json"}]
    url = f"{base_url}/api/v1/public/profile?view=summary"
    method = "GET"
    query_string = [{"name": "view", "value": "summary"}]
    post_data: dict[str, object] | None = None
    if include_auth:
        headers.append({"name": "authorization", "value": "Bearer captured-token"})
        url = f"{base_url}/api/v1/private/profile?view=summary"
    if write_mode:
        method = "POST"
        headers = [
            {"name": "accept", "value": "application/json"},
            {"name": "authorization", "value": "Bearer captured-stage-token"},
            {"name": "content-type", "value": "application/json"},
        ]
        url = f"{base_url}/api/v1/user/preferences"
        query_string = []
        post_data = {"text": json.dumps({"theme": "captured"})}
    payload = {
        "log": {
            "entries": [
                {
                    "request": {
                        "method": method,
                        "url": url,
                        "headers": headers,
                        "queryString": query_string,
                        **({"postData": post_data} if post_data else {}),
                    },
                    "response": {"status": 200, "content": {"mimeType": "application/json"}},
                }
            ]
        }
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return str(path)


if __name__ == "__main__":
    unittest.main()
