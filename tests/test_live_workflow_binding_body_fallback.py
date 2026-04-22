from __future__ import annotations

import unittest

from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.live_replay.workflow_executor import execute_live_workflow_replay
from tests.live_workflow_binding_support import binding_server


class LiveWorkflowBindingBodyFallbackTests(unittest.TestCase):
    def test_declared_body_json_binding_uses_write_context_fallback_body(self) -> None:
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
                        "method": "POST",
                        "path": "/api/v1/account/preferences",
                        "workflow_group": "account",
                        "workflow_step_index": 1,
                        "execution_mode": "live_reviewed_write_staging",
                        "approval_mode": "human_review",
                        "allowed": False,
                        "target_env": "staging",
                        "request_blueprint": {
                            "url": f"{base_url}/api/v1/account/preferences",
                            "host": base_url.replace("http://", ""),
                        },
                        "response_bindings": [
                            {
                                "binding_id": "account_id",
                                "source_case_id": "step_a",
                                "source_type": "response_json",
                                "source_key": "account_id",
                                "target_field": "request_body_json",
                                "target_path": "account_id",
                            }
                        ],
                    },
                ]
            }
            workflow_plan = build_live_workflow_plan(attack_plan)
            summary = execute_live_workflow_replay(
                workflow_plan,
                attack_plan,
                write_context={
                    "approved": True,
                    "target_env": "staging",
                    "target_hosts": [base_url.replace("http://", "")],
                    "target_base_url": base_url,
                    "case_approvals": {
                        "step_b": {
                            "method": "POST",
                            "path": "/api/v1/account/preferences",
                            "use_bound_body_json": True,
                            "json_body": {"account_id": "pending", "theme": "dark"},
                            "headers": {"x-approved": "1"},
                        }
                    },
                },
                allow_reviewed_writes=True,
            )

        self.assertEqual(summary["successful_workflow_count"], 1)
        evidence = summary["results"][0]["results"][1]["workflow_evidence"]
        self.assertEqual(evidence["applied_response_bindings"][0]["target_field"], "request_body_json")

    def test_missing_fallback_body_still_blocks_with_response_binding_target_missing(self) -> None:
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
                        "method": "POST",
                        "path": "/api/v1/account/preferences",
                        "workflow_group": "account",
                        "workflow_step_index": 1,
                        "execution_mode": "live_reviewed_write_staging",
                        "approval_mode": "human_review",
                        "allowed": False,
                        "target_env": "staging",
                        "request_blueprint": {
                            "url": f"{base_url}/api/v1/account/preferences",
                            "host": base_url.replace("http://", ""),
                        },
                        "response_bindings": [
                            {
                                "binding_id": "account_id",
                                "source_case_id": "step_a",
                                "source_type": "response_json",
                                "source_key": "account_id",
                                "target_field": "request_body_json",
                                "target_path": "account_id",
                            }
                        ],
                    },
                ]
            }
            workflow_plan = build_live_workflow_plan(attack_plan)
            summary = execute_live_workflow_replay(
                workflow_plan,
                attack_plan,
                write_context={
                    "approved": True,
                    "target_env": "staging",
                    "target_hosts": [base_url.replace("http://", "")],
                    "target_base_url": base_url,
                    "case_approvals": {
                        "step_b": {
                            "method": "POST",
                            "path": "/api/v1/account/preferences",
                            "use_bound_body_json": True,
                            "headers": {"x-approved": "1"},
                        }
                    },
                },
                allow_reviewed_writes=True,
            )

        self.assertEqual(summary["blocked_workflow_count"], 1)
        self.assertEqual(summary["reason_counts"], {"response_binding_target_missing": 1})


if __name__ == "__main__":
    unittest.main()
