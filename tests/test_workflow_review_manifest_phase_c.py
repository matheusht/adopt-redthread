from __future__ import annotations

import unittest

from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.bridge.workflow_review_manifest import build_workflow_review_manifest
from adapters.live_replay.workflow_executor import execute_live_workflow_replay


class WorkflowReviewManifestPhaseCTests(unittest.TestCase):
    def test_manifest_surfaces_required_contexts_body_gaps_and_questions(self) -> None:
        attack_plan = {
            "plan_id": "demo",
            "cases": [
                {
                    "case_id": "step_a",
                    "method": "GET",
                    "path": "/api/chats",
                    "workflow_group": "chat",
                    "workflow_step_index": 0,
                    "execution_mode": "live_safe_read_with_approved_auth",
                    "approval_mode": "human_review",
                    "allowed": False,
                    "request_blueprint": {
                        "url": "https://example.com/api/chats",
                        "host": "example.com",
                        "header_names": ["cookie"],
                    },
                },
                {
                    "case_id": "step_b",
                    "method": "POST",
                    "path": "/api/chat/{chatId}",
                    "workflow_group": "chat",
                    "workflow_step_index": 1,
                    "execution_mode": "live_reviewed_write_staging",
                    "approval_mode": "human_review",
                    "allowed": False,
                    "request_blueprint": {
                        "url": "https://example.com/api/chat/{chatId}",
                        "host": "example.com",
                        "body_json": {"id": "pending", "message": "hello"},
                    },
                    "response_bindings": [
                        {
                            "binding_id": "chat_id_from_step_a",
                            "source_case_id": "step_a",
                            "source_type": "response_json",
                            "source_key": "chat.id",
                            "target_field": "request_body_json",
                            "target_path": "chatId",
                        }
                    ],
                },
            ],
        }
        workflow_plan = build_live_workflow_plan(attack_plan)
        cases = {str(case["case_id"]): case for case in attack_plan["cases"]}

        manifest = build_workflow_review_manifest(workflow_plan, None, cases)

        self.assertTrue(manifest["review_recommended_before_live_execution"])
        self.assertTrue(manifest["required_contexts"]["auth_context_required"])
        self.assertTrue(manifest["required_contexts"]["write_context_required"])
        self.assertEqual(manifest["required_contexts"]["auth_context_case_ids"], ["step_a"])
        self.assertEqual(manifest["required_contexts"]["write_context_case_ids"], ["step_b"])
        self.assertEqual(manifest["workflows"][0]["body_template_gaps"][0]["gap_type"], "static_id_like_field")
        self.assertIn("Step step_b body field 'id' is still static.", manifest["open_questions"][0])
        self.assertEqual(manifest["workflows"][0]["candidate_binding_pairs"][0]["candidate_path_bindings"][0]["confidence_tier"], "unmatched")

    def test_replay_summary_and_manifest_surface_failure_narrative(self) -> None:
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
                    "request_blueprint": {"url": "http://one.example/api/v1/account/profile", "host": "one.example"},
                },
                {
                    "case_id": "step_b",
                    "method": "GET",
                    "path": "/api/v1/account/private",
                    "workflow_group": "account",
                    "workflow_step_index": 1,
                    "execution_mode": "live_safe_read_with_approved_auth",
                    "approval_mode": "human_review",
                    "allowed": False,
                    "request_blueprint": {
                        "url": "http://one.example/api/v1/account/private",
                        "host": "one.example",
                        "header_names": ["authorization"],
                    },
                },
            ]
        }
        workflow_plan = build_live_workflow_plan(attack_plan)
        summary = execute_live_workflow_replay(workflow_plan, attack_plan)
        cases = {str(case["case_id"]): case for case in attack_plan["cases"]}
        manifest = build_workflow_review_manifest(workflow_plan, summary, cases)

        self.assertEqual(summary["workflow_failure_narratives"][0]["failure_reason_code"], "missing_auth_context")
        self.assertIn("approved auth context", summary["workflow_failure_narratives"][0]["failure_narrative"])
        self.assertIn("approved auth context", summary["results"][0]["failure_narrative"])
        self.assertIn("approved auth context", manifest["workflows"][0]["failure_narrative"])


if __name__ == "__main__":
    unittest.main()
