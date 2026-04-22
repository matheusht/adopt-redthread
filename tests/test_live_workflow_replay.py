from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from adapters.bridge.live_attack import build_live_attack_plan
from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.bridge.workflow import run_bridge_workflow
from adapters.live_replay.workflow_executor import execute_live_workflow_replay
from adapters.zapi.loader import build_fixture_bundle


class _WorkflowHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/v1/account/profile"):
            self._send_json({"ok": True, "step": "profile"})
            return
        if self.path.startswith("/api/v1/account/preferences"):
            self._send_json({"ok": True, "step": "preferences"})
            return
        if self.path.startswith("/api/v1/account/private") and self.headers.get("Authorization") == "Bearer demo-token":
            self._send_json({"ok": True, "step": "private"})
            return
        self.send_response(401 if self.path.startswith("/api/v1/account/private") else 404)
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


class LiveWorkflowReplayTests(unittest.TestCase):
    def test_builder_groups_multi_step_cases_in_order(self) -> None:
        attack_plan = {
            "plan_id": "demo",
            "cases": [
                {"case_id": "step_b", "workflow_group": "account", "workflow_step_index": 1, "execution_mode": "live_safe_read", "approval_mode": "auto", "allowed": True},
                {"case_id": "step_a", "workflow_group": "account", "workflow_step_index": 0, "execution_mode": "live_safe_read", "approval_mode": "auto", "allowed": True},
                {"case_id": "solo", "workflow_group": "default", "workflow_step_index": 2, "execution_mode": "manual_review", "approval_mode": "human_review", "allowed": False},
            ],
        }
        workflow_plan = build_live_workflow_plan(attack_plan)

        self.assertEqual(workflow_plan["workflow_count"], 1)
        self.assertEqual([step["case_id"] for step in workflow_plan["workflows"][0]["steps"]], ["step_a", "step_b"])

    def test_executor_runs_two_step_safe_read_workflow(self) -> None:
        with _server() as base_url, tempfile.TemporaryDirectory() as tmp:
            har_path = _write_workflow_har(Path(tmp) / "workflow.har", base_url)
            bundle = build_fixture_bundle(har_path)
            attack_plan = build_live_attack_plan(bundle)
            workflow_plan = build_live_workflow_plan(attack_plan)
            summary = execute_live_workflow_replay(workflow_plan, attack_plan)

            self.assertEqual(workflow_plan["workflow_count"], 1)
            self.assertEqual(summary["executed_workflow_count"], 1)
            self.assertEqual(summary["successful_workflow_count"], 1)
            self.assertEqual(summary["results"][0]["status"], "completed")
            self.assertEqual(summary["results"][0]["executed_step_count"], 2)

    def test_executor_aborts_when_later_step_is_not_executable(self) -> None:
        with _server() as base_url:
            attack_plan = {
                "cases": [
                    {
                        "case_id": "get_api_v1_account_profile",
                        "method": "GET",
                        "path": "/api/v1/account/profile",
                        "workflow_group": "account",
                        "workflow_step_index": 0,
                        "execution_mode": "live_safe_read",
                        "approval_mode": "auto",
                        "allowed": True,
                        "request_blueprint": {"url": f"{base_url}/api/v1/account/profile", "host": base_url.replace("http://", "")},
                    },
                    {
                        "case_id": "get_api_v1_account_private",
                        "method": "GET",
                        "path": "/api/v1/account/private",
                        "workflow_group": "account",
                        "workflow_step_index": 1,
                        "execution_mode": "live_safe_read_with_approved_auth",
                        "approval_mode": "human_review",
                        "allowed": False,
                        "request_blueprint": {
                            "url": f"{base_url}/api/v1/account/private",
                            "host": base_url.replace("http://", ""),
                            "header_names": ["authorization"],
                        },
                    },
                ]
            }
            workflow_plan = build_live_workflow_plan(attack_plan)
            summary = execute_live_workflow_replay(workflow_plan, attack_plan)

            self.assertEqual(summary["executed_workflow_count"], 1)
            self.assertEqual(summary["successful_workflow_count"], 0)
            self.assertEqual(summary["results"][0]["status"], "blocked")
            self.assertEqual(summary["results"][0]["executed_step_count"], 1)
            self.assertIn("step_not_executable", summary["results"][0]["error"])

    def test_workflow_pipeline_emits_workflow_artifacts(self) -> None:
        with _server() as base_url, tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            har_path = _write_workflow_har(root / "workflow.har", base_url)
            output_dir = root / "workflow_run"
            summary = run_bridge_workflow(
                har_path,
                ingestion="zapi",
                output_dir=output_dir,
                run_dryrun=False,
                run_live_workflow_replay=True,
                redthread_python="../redthread/.venv/bin/python",
                redthread_src="../redthread/src",
            )

            workflow_plan = json.loads((output_dir / "live_workflow_plan.json").read_text())
            replay = json.loads((output_dir / "live_workflow_replay.json").read_text())
            self.assertEqual(workflow_plan["workflow_count"], 1)
            self.assertTrue(summary["live_workflow_replay_executed"])
            self.assertEqual(summary["live_workflow_replay_count"], 1)
            self.assertEqual(replay["successful_workflow_count"], 1)


class _server:
    def __enter__(self) -> str:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _WorkflowHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, *_args: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)


def _write_workflow_har(path: Path, base_url: str) -> str:
    payload = {
        "log": {
            "entries": [
                _entry(f"{base_url}/api/v1/account/profile?view=full"),
                _entry(f"{base_url}/api/v1/account/preferences?view=full"),
            ]
        }
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return str(path)


def _entry(url: str) -> dict[str, object]:
    return {
        "request": {
            "method": "GET",
            "url": url,
            "headers": [{"name": "accept", "value": "application/json"}],
            "queryString": [{"name": "view", "value": "full"}],
        },
        "response": {"status": 200, "content": {"mimeType": "application/json"}},
    }


if __name__ == "__main__":
    unittest.main()
