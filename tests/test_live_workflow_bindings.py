from __future__ import annotations

import unittest

from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.live_replay.workflow_executor import execute_live_workflow_replay
from tests.live_workflow_binding_support import binding_server


class LiveWorkflowBindingTests(unittest.TestCase):
    def test_executor_applies_declared_response_bindings(self) -> None:
        with binding_server() as base_url:
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
            summary = execute_live_workflow_replay(workflow_plan, attack_plan)

        self.assertEqual(summary["successful_workflow_count"], 1)
        self.assertEqual(summary["workflow_requirement_summary"]["declared_response_binding_count"], 2)
        self.assertEqual(summary["workflow_requirement_summary"]["applied_response_binding_count"], 2)
        self.assertEqual(
            summary["results"][0]["final_state"]["response_binding_values"],
            {"account_id": "acct-123", "trace_id": "trace-abc"},
        )

    def test_executor_applies_request_path_response_bindings(self) -> None:
        with binding_server() as base_url:
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
                        "path": "/api/v1/account/items/{{account_id}}",
                        "workflow_group": "account",
                        "workflow_step_index": 1,
                        "execution_mode": "live_safe_read",
                        "approval_mode": "auto",
                        "allowed": True,
                        "request_blueprint": {
                            "url": f"{base_url}/api/v1/account/items/{{{{account_id}}}}",
                            "host": base_url.replace("http://", ""),
                        },
                        "response_bindings": [
                            {
                                "binding_id": "account_id",
                                "source_case_id": "step_a",
                                "source_type": "response_json",
                                "source_key": "account_id",
                                "target_field": "request_path",
                                "placeholder": "{{account_id}}",
                            }
                        ],
                    },
                ]
            }
            workflow_plan = build_live_workflow_plan(attack_plan)
            summary = execute_live_workflow_replay(workflow_plan, attack_plan)

        self.assertEqual(summary["successful_workflow_count"], 1)
        evidence = summary["results"][0]["results"][1]["workflow_evidence"]
        self.assertEqual(evidence["applied_response_bindings"][0]["target_field"], "request_path")

    def test_executor_blocks_when_required_response_binding_is_missing(self) -> None:
        with binding_server() as base_url:
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
            summary = execute_live_workflow_replay(workflow_plan, attack_plan)

        self.assertEqual(summary["blocked_workflow_count"], 1)
        self.assertEqual(summary["reason_counts"], {"response_binding_missing": 1})
        self.assertEqual(summary["results"][0]["failure_reason_code"], "response_binding_missing")
        self.assertEqual(summary["results"][0]["binding_application_failure"]["binding_id"], "missing_id")
        self.assertEqual(summary["binding_application_summary"]["planned_response_binding_count"], 1)
        self.assertEqual(summary["binding_application_summary"]["applied_response_binding_count"], 0)
        self.assertEqual(summary["binding_application_summary"]["unapplied_response_binding_count"], 1)
        self.assertEqual(summary["binding_application_summary"]["binding_application_failure_counts"], {"response_binding_missing": 1})
        self.assertEqual(summary["binding_application_summary"]["failed_binding_ids"], ["missing_id"])


if __name__ == "__main__":
    unittest.main()
