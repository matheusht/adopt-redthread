from __future__ import annotations

import unittest

from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.live_replay.workflow_executor import execute_live_workflow_replay
from tests.live_workflow_binding_support import binding_server


class LiveWorkflowBindingBodyInferenceTests(unittest.TestCase):
    def test_builder_auto_emits_body_json_response_bindings(self) -> None:
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
                            "body_json": {"account_id": "acct-123", "theme": "dark"},
                        },
                    },
                ]
            }
            workflow_plan = build_live_workflow_plan(attack_plan)
            step_b = workflow_plan["workflows"][0]["steps"][1]
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

        self.assertEqual(step_b["response_bindings"][0]["target_field"], "request_body_json")
        self.assertEqual(step_b["response_bindings"][0]["target_path"], "account_id")
        self.assertEqual(step_b["response_bindings"][0]["source_key"], "account_id")
        self.assertEqual(step_b["response_bindings"][0]["review_status"], "pending_review")
        self.assertEqual(summary["blocked_workflow_count"], 1)
        self.assertEqual(summary["reason_counts"], {"binding_review_required": 1})

    def test_approved_inferred_body_json_binding_can_execute_reviewed_write(self) -> None:
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
                            "body_json": {"account_id": "acct-123", "theme": "dark"},
                        },
                    },
                ]
            }
            workflow_plan = build_live_workflow_plan(attack_plan, {"case_bindings": {"step_b": {"review_status": "approved"}}})
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

        self.assertEqual(summary["successful_workflow_count"], 1)
        self.assertEqual(summary["workflow_requirement_summary"]["approved_response_binding_count"], 1)
        self.assertEqual(summary["workflow_requirement_summary"]["pending_review_response_binding_count"], 0)
        evidence = summary["results"][0]["results"][1]["workflow_evidence"]
        self.assertEqual(evidence["applied_response_bindings"][0]["target_field"], "request_body_json")


if __name__ == "__main__":
    unittest.main()
