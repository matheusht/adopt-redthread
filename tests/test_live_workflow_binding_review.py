from __future__ import annotations

import json
import tempfile
import unittest

from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.live_replay.workflow_executor import execute_live_workflow_replay
from tests.live_workflow_binding_support import binding_server


class LiveWorkflowBindingReviewTests(unittest.TestCase):
    def test_builder_auto_emits_query_response_bindings(self) -> None:
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
                        "path": "/api/v1/account/preferences",
                        "workflow_group": "account",
                        "workflow_step_index": 1,
                        "execution_mode": "live_safe_read",
                        "approval_mode": "auto",
                        "allowed": True,
                        "request_blueprint": {
                            "url": f"{base_url}/api/v1/account/preferences?account_id=acct-123",
                            "host": base_url.replace("http://", ""),
                        },
                    },
                ]
            }
            workflow_plan = build_live_workflow_plan(attack_plan)
            step_b = workflow_plan["workflows"][0]["steps"][1]
            summary = execute_live_workflow_replay(workflow_plan, attack_plan)

        self.assertEqual(step_b["request_url_template"], f"{base_url}/api/v1/account/preferences?account_id={{{{account_id_from_step_a}}}}")
        self.assertEqual(step_b["response_bindings"][0]["source_key"], "account_id")
        self.assertTrue(step_b["response_bindings"][0]["inferred"])
        self.assertEqual(step_b["response_bindings"][0]["review_status"], "pending_review")
        self.assertTrue(step_b["binding_review_required"])
        self.assertEqual(summary["blocked_workflow_count"], 1)
        self.assertEqual(summary["reason_counts"], {"binding_review_required": 1})
        self.assertEqual(summary["workflow_requirement_summary"]["pending_review_response_binding_count"], 1)
        self.assertEqual(summary["workflow_binding_review_artifacts"][0]["steps"][0]["binding_review_decisions"], [])
        self.assertEqual(summary["workflow_binding_review_artifacts"][0]["steps"][1]["binding_review_decisions"][0]["decision"], "pending_review")

    def test_binding_override_can_approve_inferred_binding(self) -> None:
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
                        "path": "/api/v1/account/preferences",
                        "workflow_group": "account",
                        "workflow_step_index": 1,
                        "execution_mode": "live_safe_read",
                        "approval_mode": "auto",
                        "allowed": True,
                        "request_blueprint": {
                            "url": f"{base_url}/api/v1/account/preferences?account_id=acct-123",
                            "host": base_url.replace("http://", ""),
                        },
                    },
                ]
            }
            override_path = f"{tmp}/binding_overrides.json"
            with open(override_path, "w", encoding="utf-8") as handle:
                json.dump({"case_bindings": {"step_b": {"review_status": "approved"}}}, handle)
            workflow_plan = build_live_workflow_plan(attack_plan, override_path)
            summary = execute_live_workflow_replay(workflow_plan, attack_plan)

        self.assertEqual(summary["successful_workflow_count"], 1)
        self.assertEqual(summary["workflow_requirement_summary"]["inferred_response_binding_count"], 1)
        self.assertEqual(summary["workflow_requirement_summary"]["approved_response_binding_count"], 1)
        self.assertEqual(summary["workflow_requirement_summary"]["pending_review_response_binding_count"], 0)
        self.assertEqual(summary["workflow_requirement_summary"]["rejected_response_binding_count"], 0)
        self.assertEqual(summary["workflow_requirement_summary"]["replaced_response_binding_count"], 0)
        self.assertEqual(summary["workflow_binding_review_artifacts"][0]["steps"][1]["binding_review_decisions"][0]["decision"], "approved")

    def test_binding_override_can_replace_with_bound_body_json(self) -> None:
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
                            "url": f"{base_url}/api/v1/account/preferences?account_id=acct-123",
                            "host": base_url.replace("http://", ""),
                            "body_json": {"account_id": "pending", "theme": "dark"},
                        },
                    },
                ]
            }
            workflow_plan = build_live_workflow_plan(
                attack_plan,
                {
                    "case_bindings": {
                        "step_b": {
                            "replace_response_bindings": [
                                {
                                    "binding_id": "account_id",
                                    "source_case_id": "step_a",
                                    "source_type": "response_json",
                                    "source_key": "account_id",
                                    "target_field": "request_body_json",
                                    "target_path": "account_id",
                                }
                            ]
                        }
                    }
                },
            )
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
        self.assertEqual(summary["workflow_requirement_summary"]["inferred_response_binding_count"], 1)
        self.assertEqual(summary["workflow_requirement_summary"]["replaced_response_binding_count"], 1)
        second_step = summary["results"][0]["results"][1]["workflow_evidence"]
        self.assertEqual(second_step["applied_response_bindings"][0]["target_field"], "request_body_json")
        self.assertEqual(summary["workflow_binding_review_artifacts"][0]["steps"][1]["binding_review_decisions"][0]["decision"], "replaced")


if __name__ == "__main__":
    unittest.main()
