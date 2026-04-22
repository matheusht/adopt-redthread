from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from adapters.bridge.live_workflow import build_live_workflow_plan
from adapters.bridge.workflow import run_bridge_workflow
from adapters.live_replay.workflow_executor import execute_live_workflow_replay
from tests.test_live_workflow_replay import _server, _write_workflow_har


class LiveWorkflowContractTests(unittest.TestCase):
    def test_executor_blocks_on_auth_header_family_mismatch(self) -> None:
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
                    "request_blueprint": {
                        "url": "http://one.example/api/v1/account/profile",
                        "host": "one.example",
                    },
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
        summary = execute_live_workflow_replay(
            workflow_plan,
            attack_plan,
            auth_context={"approved": True, "allowed_header_names": ["cookie"]},
            allow_reviewed_auth=True,
        )

        self.assertEqual(summary["blocked_workflow_count"], 1)
        self.assertEqual(summary["reason_counts"], {"auth_header_family_mismatch": 1})
        self.assertEqual(summary["workflow_requirement_summary"]["auth_header_contract_required_count"], 1)
        self.assertEqual(summary["workflow_requirement_summary"]["same_auth_context_required_count"], 1)
        self.assertEqual(summary["workflow_requirement_summary"]["approved_auth_context_required_count"], 1)
        self.assertEqual(summary["workflow_requirement_summary"]["context_contract_failure_counts"], {"auth_header_family_mismatch": 1})
        self.assertEqual(summary["workflow_failure_class_summary"], {"context_contract_failure": 1})
        self.assertEqual(summary["results"][0]["failure_reason_code"], "auth_header_family_mismatch")

    def test_bridge_summary_surfaces_workflow_requirement_summary_when_replay_runs(self) -> None:
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

            workflow_summary = json.loads((output_dir / "workflow_summary.json").read_text())
            self.assertTrue(summary["live_workflow_replay_executed"])
            self.assertEqual(
                workflow_summary["live_workflow_requirement_summary"]["workflow_class_counts"],
                {"safe_read_workflow": 1},
            )
            self.assertEqual(
                workflow_summary["live_workflow_requirement_summary"]["same_host_continuity_required_count"],
                1,
            )
            self.assertIn("live_workflow_failure_class_summary", workflow_summary)


if __name__ == "__main__":
    unittest.main()
