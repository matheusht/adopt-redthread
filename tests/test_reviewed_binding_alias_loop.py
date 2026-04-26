from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.live_replay.binding_alias_reviews import build_approved_binding_aliases
from adapters.live_replay.binding_patterns import build_binding_pattern_candidates
from adapters.live_replay.workflow_executor import execute_live_workflow_replay
from tests.reviewed_alias_test_support import reviewed_alias_server


class ReviewedBindingAliasLoopTests(unittest.TestCase):
    def test_history_to_reviewed_alias_to_next_run_success_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, reviewed_alias_server() as base_url:
            history_path = Path(tmp) / "binding_history.jsonl"
            candidate_path = Path(tmp) / "binding_pattern_candidates.json"
            approved_path = Path(tmp) / "approved_binding_aliases.json"
            history_rows = [
                {
                    "workflow_id": "wf-1",
                    "source_type": "response_json",
                    "source_key": "profile.id",
                    "target_field": "request_body_json",
                    "target_path": "profileKey",
                    "outcome": "success",
                    "app_host": "one.example",
                },
                {
                    "workflow_id": "wf-2",
                    "source_type": "response_json",
                    "source_key": "profile.id",
                    "target_field": "request_body_json",
                    "target_path": "profileKey",
                    "outcome": "success",
                    "app_host": "two.example",
                },
                {
                    "workflow_id": "wf-3",
                    "source_type": "response_json",
                    "source_key": "profile.id",
                    "target_field": "request_body_json",
                    "target_path": "profileKey",
                    "outcome": "success",
                    "app_host": "three.example",
                },
            ]
            history_path.write_text("\n".join(json.dumps(row) for row in history_rows) + "\n")
            candidates = build_binding_pattern_candidates(history_path, output_path=candidate_path)
            approved_aliases = build_approved_binding_aliases(
                candidates,
                {
                    "approved_candidates": [
                        {
                            "source_key": "profile.id",
                            "target_field": "request_body_json",
                            "target_locator": "profileKey",
                        }
                    ]
                },
                output_path=approved_path,
            )
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

            workflow_plan = build_live_workflow_plan(attack_plan, approved_binding_aliases=approved_path)
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

        self.assertEqual(candidates["promotion_ready_count"], 1)
        self.assertEqual(approved_aliases["approved_alias_count"], 1)
        self.assertEqual(summary["successful_workflow_count"], 1)
        self.assertEqual(summary["binding_application_summary"]["planned_response_binding_count"], 1)
        self.assertEqual(summary["binding_application_summary"]["applied_response_binding_count"], 1)


if __name__ == "__main__":
    unittest.main()
