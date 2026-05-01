from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from adapters.bridge.workflow import run_bridge_workflow


class BridgeWorkflowTests(unittest.TestCase):
    def test_full_bridge_workflow_runs_from_sample_har(self) -> None:
        output_dir = Path("runs/test_sample_har_bridge")
        if output_dir.exists():
            for path in sorted(output_dir.glob("**/*"), reverse=True):
                if path.is_file():
                    path.unlink()
            for path in sorted(output_dir.glob("**/*"), reverse=True):
                if path.is_dir():
                    path.rmdir()

        summary = run_bridge_workflow(
            "fixtures/zapi_samples/sample_filtered_har.json",
            ingestion="zapi",
            output_dir=output_dir,
            redthread_python="../redthread/.venv/bin/python",
            redthread_src="../redthread/src",
        )

        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["fixture_count"], 4)
        self.assertTrue(summary["redthread_replay_passed"])
        self.assertTrue(summary["redthread_dryrun_executed"])

        workflow_summary = json.loads((output_dir / "workflow_summary.json").read_text())
        workflow_review_manifest = json.loads((output_dir / "workflow_review_manifest.json").read_text())
        live_attack_plan = json.loads((output_dir / "live_attack_plan.json").read_text())
        gate_verdict = json.loads((output_dir / "gate_verdict.json").read_text())
        self.assertEqual(workflow_summary["gate_decision"], "review")
        self.assertIn("live_attack_allowed_count", workflow_summary)
        self.assertIn("live_workflow_requirement_summary", workflow_summary)
        self.assertIn("live_workflow_failure_class_summary", workflow_summary)
        self.assertIn("live_workflow_binding_application_summary", workflow_summary)
        self.assertIn("live_workflow_binding_review_artifacts", workflow_summary)
        self.assertIn("live_workflow_review_manifest_ready", workflow_summary)
        self.assertIn("approved_binding_alias_count", workflow_summary)
        self.assertIn("approved_binding_alias_summary", workflow_summary)
        self.assertIn("binding_pattern_candidate_count", workflow_summary)
        self.assertIn("binding_pattern_promotion_ready_count", workflow_summary)
        self.assertIn("app_context_summary", workflow_summary)
        self.assertIn("decision_reason_summary", workflow_summary)
        self.assertIn("coverage_summary", workflow_summary)
        self.assertIn("attack_brief_summary", workflow_summary)
        self.assertEqual(workflow_summary["decision_reason_summary"]["category"], "manual_review_required_for_write_paths")
        self.assertEqual(workflow_summary["coverage_summary"]["label"], "weak_fixture_or_dryrun_only")
        self.assertIn("tenant_user_boundary_unproven", workflow_summary["coverage_summary"]["coverage_gaps"])
        self.assertIn("top_targeted_probe", workflow_summary["attack_brief_summary"])
        self.assertEqual(workflow_summary["app_context_summary"]["operation_count"], 4)
        self.assertEqual(workflow_summary["app_context_summary"]["auth_mode"], "api_key")
        self.assertEqual(workflow_summary["app_context_summary"]["action_class_counts"], {"write": 4})
        self.assertTrue(workflow_summary["app_context_summary"]["requires_approved_auth_context"])
        self.assertTrue(workflow_summary["app_context_summary"]["requires_approved_write_context"])
        self.assertEqual(workflow_summary["live_workflow_requirement_summary"], {})
        self.assertEqual(workflow_summary["live_workflow_failure_class_summary"], {})
        self.assertEqual(workflow_summary["live_workflow_binding_application_summary"], {})
        self.assertEqual(workflow_summary["live_workflow_binding_review_artifacts"], [])
        self.assertFalse(workflow_summary["live_workflow_review_manifest_ready"])
        self.assertEqual(workflow_summary["approved_binding_alias_summary"]["loaded_alias_count"], 0)
        self.assertEqual(workflow_review_manifest["workflow_count"], 0)
        self.assertEqual(workflow_review_manifest["workflows"], [])
        self.assertEqual(live_attack_plan["fixture_count"], 4)
        self.assertTrue(gate_verdict["evidence_summary"]["redthread_replay_verdict"]["passed"])

    def test_cli_bridge_pipeline_emits_summary_json(self) -> None:
        output_dir = Path("runs/test_cli_bridge")
        subprocess.run(
            [
                "python3",
                "scripts/run_bridge_pipeline.py",
                "fixtures/zapi_samples/sample_filtered_har.json",
                str(output_dir),
                "--ingestion",
                "zapi",
                "--redthread-python",
                "../redthread/.venv/bin/python",
                "--redthread-src",
                "../redthread/src",
            ],
            check=True,
        )
        summary = json.loads((output_dir / "workflow_summary.json").read_text())
        self.assertEqual(summary["status"], "completed")
        self.assertTrue(summary["redthread_replay_passed"])
        self.assertIn("live_attack_allowed_count", summary)
        self.assertIn("live_workflow_review_manifest_ready", summary)
        self.assertIn("approved_binding_alias_count", summary)
        self.assertIn("approved_binding_alias_summary", summary)
        self.assertIn("binding_pattern_candidate_count", summary)
        self.assertIn("app_context_summary", summary)
        self.assertIn("decision_reason_summary", summary)
        self.assertIn("coverage_summary", summary)
        self.assertIn("attack_brief_summary", summary)
        self.assertEqual(summary["app_context_summary"]["schema_version"], "app_context.v1")
        self.assertIn("workflow_review_manifest", summary["artifacts"])


if __name__ == "__main__":
    unittest.main()
