from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.live_replay.workflow_executor import execute_live_workflow_replay
from tests.live_workflow_binding_support import binding_server


class BindingHistoryTests(unittest.TestCase):
    def test_completed_workflow_appends_binding_history_rows(self) -> None:
        with binding_server() as base_url, tempfile.TemporaryDirectory() as tmp:
            attack_plan = {
                "cases": [
                    {
                        "case_id": "step_a",
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
                        "case_id": "step_b",
                        "method": "GET",
                        "path": "/api/v1/account/preferences/acct-123",
                        "workflow_group": "account",
                        "workflow_step_index": 1,
                        "execution_mode": "live_safe_read",
                        "approval_mode": "auto",
                        "allowed": True,
                        "request_blueprint": {
                            "url": f"{base_url}/api/v1/account/preferences/{{{{account_id}}}}?trace={{{{trace_id}}}}",
                            "host": base_url.replace("http://", ""),
                        },
                        "response_bindings": [
                            {
                                "binding_id": "account_id",
                                "source_case_id": "step_a",
                                "source_type": "response_json",
                                "source_key": "account.id",
                                "target_field": "request_url",
                                "placeholder": "{{account_id}}",
                            },
                            {
                                "binding_id": "trace_id",
                                "source_case_id": "step_a",
                                "source_type": "response_header",
                                "source_key": "x-trace-id",
                                "target_field": "request_url",
                                "placeholder": "{{trace_id}}",
                            },
                        ],
                    },
                ]
            }
            workflow_plan = build_live_workflow_plan(attack_plan)
            history_path = Path(tmp) / "binding_history.jsonl"

            summary = execute_live_workflow_replay(workflow_plan, attack_plan, binding_history_path=history_path)

            self.assertEqual(summary["binding_history_rows_written"], 2)
            rows = [json.loads(line) for line in history_path.read_text().splitlines()]
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["binding_id"] for row in rows}, {"account_id", "trace_id"})
            self.assertEqual({row["outcome"] for row in rows}, {"success"})
            self.assertEqual({row["app_host"] for row in rows}, {base_url.replace("http://", "")})

    def test_blocked_workflow_does_not_append_binding_history_rows(self) -> None:
        with binding_server() as base_url, tempfile.TemporaryDirectory() as tmp:
            attack_plan = {
                "cases": [
                    {
                        "case_id": "step_a",
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
                        "case_id": "step_b",
                        "method": "GET",
                        "path": "/api/v1/account/preferences/missing",
                        "workflow_group": "account",
                        "workflow_step_index": 1,
                        "execution_mode": "live_safe_read",
                        "approval_mode": "auto",
                        "allowed": True,
                        "request_blueprint": {
                            "url": f"{base_url}/api/v1/account/preferences/{{{{missing_id}}}}",
                            "host": base_url.replace("http://", ""),
                        },
                        "response_bindings": [
                            {
                                "binding_id": "missing_id",
                                "source_case_id": "step_a",
                                "source_type": "response_json",
                                "source_key": "account.missing",
                                "target_field": "request_url",
                                "placeholder": "{{missing_id}}",
                            }
                        ],
                    },
                ]
            }
            workflow_plan = build_live_workflow_plan(attack_plan)
            history_path = Path(tmp) / "binding_history.jsonl"

            summary = execute_live_workflow_replay(workflow_plan, attack_plan, binding_history_path=history_path)

            self.assertEqual(summary["binding_history_rows_written"], 0)
            self.assertFalse(history_path.exists())


if __name__ == "__main__":
    unittest.main()
