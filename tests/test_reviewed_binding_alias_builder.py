from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.live_replay.binding_alias_reviews import build_approved_binding_aliases
from adapters.live_replay.workflow_executor import execute_live_workflow_replay
from tests.reviewed_alias_test_support import reviewed_alias_server


class ReviewedBindingAliasBuilderTests(unittest.TestCase):
    def test_review_builder_only_promotes_reviewed_ready_body_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            candidates = {
                "candidates": [
                    {
                        "source_key": "profile.id",
                        "target_field": "request_body_json",
                        "target_locator": "profileKey",
                        "promotion_ready": True,
                    },
                    {
                        "source_key": "session.id",
                        "target_field": "request_url",
                        "target_locator": "{{session_id}}",
                        "promotion_ready": True,
                    },
                    {
                        "source_key": "chat.id",
                        "target_field": "request_body_json",
                        "target_locator": "chatKey",
                        "promotion_ready": False,
                    },
                ]
            }
            review = {
                "approved_candidates": [
                    {"source_key": "profile.id", "target_field": "request_body_json", "target_locator": "profileKey"},
                    {"source_key": "session.id", "target_field": "request_url", "target_locator": "{{session_id}}"},
                    {"source_key": "chat.id", "target_field": "request_body_json", "target_locator": "chatKey"},
                ]
            }
            output_path = Path(tmp) / "approved_binding_aliases.json"

            payload = build_approved_binding_aliases(candidates, review, output_path=output_path)

            self.assertEqual(payload["review_approval_count"], 3)
            self.assertEqual(payload["approved_alias_count"], 1)
            self.assertEqual(payload["aliases"][0]["source_key"], "profile.id")
            self.assertEqual(payload["aliases"][0]["target_path"], "profileKey")
            self.assertEqual(json.loads(output_path.read_text())["approved_alias_count"], 1)

    def test_reviewed_alias_can_auto_approve_body_binding_for_next_run(self) -> None:
        with reviewed_alias_server() as base_url:
            attack_plan = {
                "cases": [
                    {
                        "case_id": "step_a",
                        "method": "GET",
                        "path": "/api/v1/profile",
                        "workflow_group": "profile",
                        "workflow_step_index": 0,
                        "execution_mode": "live_safe_read",
                        "approval_mode": "auto",
                        "allowed": True,
                        "request_blueprint": {"url": f"{base_url}/api/v1/profile", "host": base_url.replace("http://", "")},
                    },
                    {
                        "case_id": "step_b",
                        "method": "POST",
                        "path": "/api/v1/widgets",
                        "workflow_group": "profile",
                        "workflow_step_index": 1,
                        "execution_mode": "live_reviewed_write_staging",
                        "approval_mode": "human_review",
                        "allowed": False,
                        "target_env": "staging",
                        "request_blueprint": {
                            "url": f"{base_url}/api/v1/widgets",
                            "host": base_url.replace("http://", ""),
                            "body_json": {"profileKey": "prof-123", "name": "demo"},
                        },
                    },
                ]
            }
            approved_aliases = {
                "aliases": [
                    {
                        "source_key": "profile.id",
                        "target_path": "profileKey",
                        "tier": "reviewed_pattern",
                    }
                ]
            }

            workflow_plan = build_live_workflow_plan(attack_plan, approved_binding_aliases=approved_aliases)
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
                            "path": "/api/v1/widgets",
                            "use_bound_body_json": True,
                            "headers": {"x-approved": "1"},
                        }
                    },
                },
                allow_reviewed_writes=True,
            )

        self.assertEqual(workflow_plan["approved_binding_alias_count"], 1)
        self.assertEqual(step_b["response_bindings"][0]["source_key"], "profile.id")
        self.assertEqual(step_b["response_bindings"][0]["review_status"], "approved")
        self.assertFalse(step_b["binding_review_required"])
        self.assertEqual(summary["successful_workflow_count"], 1)
        self.assertEqual(summary["workflow_requirement_summary"]["approved_response_binding_count"], 1)
        evidence = summary["results"][0]["results"][1]["workflow_evidence"]
        self.assertEqual(evidence["applied_response_bindings"][0]["target_path"], "profileKey")


if __name__ == "__main__":
    unittest.main()
