from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_evidence_report import build_evidence_report


class EvidenceReportTests(unittest.TestCase):
    def test_block_report_names_exact_workflow_blocker_plainly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "victoria"
            run_dir.mkdir()
            _write_json(
                run_dir / "workflow_summary.json",
                {
                    "ingestion": "zapi",
                    "input_file": "victoria_filtered.har",
                    "fixture_count": 3,
                    "live_workflow_count": 1,
                    "live_workflow_replay_executed": True,
                    "live_workflow_reason_counts": {"missing_write_context": 1},
                    "live_workflow_requirement_summary": {"workflow_class_counts": {"reviewed_write_workflow": 1}},
                    "live_workflow_failure_class_summary": {"review_gap": 1},
                    "live_workflow_binding_application_summary": {
                        "planned_response_binding_count": 0,
                        "applied_response_binding_count": 0,
                        "unapplied_response_binding_count": 0,
                        "binding_application_failure_counts": {},
                    },
                    "redthread_replay_passed": True,
                    "redthread_dryrun_executed": True,
                    "app_context_summary": {
                        "schema_version": "app_context.v1",
                        "operation_count": 3,
                        "tool_action_schema_count": 3,
                        "auth_mode": "cookie",
                        "auth_scope_hints": ["user_scoped"],
                        "requires_approved_context": True,
                        "data_sensitivity_tags": ["support_message_like", "user_data"],
                        "candidate_user_field_count": 1,
                        "candidate_tenant_field_count": 0,
                        "candidate_route_param_count": 0,
                    },
                    "gate_decision": "block",
                },
            )
            _write_json(
                run_dir / "gate_verdict.json",
                {
                    "decision": "block",
                    "warnings": ["manual_review_required_for_write_paths", "live_workflow_review_gap_present"],
                    "blockers": ["live_workflow_blocked_steps_present"],
                },
            )
            _write_json(
                run_dir / "live_workflow_replay.json",
                {
                    "successful_workflow_count": 0,
                    "blocked_workflow_count": 1,
                    "aborted_workflow_count": 0,
                    "reason_counts": {"missing_write_context": 1},
                },
            )
            _write_json(run_dir / "redthread_replay_verdict.json", {"passed": True})

            report = build_evidence_report(run_dir)

        self.assertIn("Exact decision reason", report)
        self.assertIn("missing_write_context:1", report)
        self.assertIn("Approved staging write context was required but was not supplied", report)
        self.assertIn("## App context for RedThread", report)
        self.assertIn("Context schema: `app_context.v1`", report)
        self.assertIn("Auth model: `cookie`", report)
        self.assertIn("Sensitivity tags: `support_message_like,user_data`", report)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
