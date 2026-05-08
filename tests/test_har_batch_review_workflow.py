from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_har_batch_review_workflow import build_har_batch_review_workflow


class HarBatchReviewWorkflowTests(unittest.TestCase):
    def test_builds_phase_artifacts_without_promoting_review_subjects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = root / "batch"
            batch.mkdir()
            (batch / "batch_manifest.json").write_text(json.dumps({
                "batch_status": "complete",
                "gate_decision_counts": {"review": 2},
            }), encoding="utf-8")
            (batch / "aggregate_blockers.json").write_text(json.dumps({
                "followup_required": True,
                "followup_subject_count": 2,
                "evidence_review_subject_count": 2,
                "remediation_subject_count": 0,
                "recommended_batch_next_step": "review_repeated_missing_evidence_counts",
                "missing_boundary_evidence_subject_count": 2,
                "subject_privacy_failed_count": 0,
                "confirmed_security_finding_count": 0,
            }), encoding="utf-8")
            (batch / "subject_index.json").write_text(json.dumps({
                "subjects": [
                    {
                        "subject_id": "subject_small",
                        "batch_status": "processed",
                        "gate_decision": "review",
                        "fixture_count": 1,
                        "next_evidence_needed": ["formal_reviewer_observation_summary"],
                        "subject_artifact_count": 3,
                        "subject_artifacts": ["subject_summary.json", "workflow_summary.json", "unsafe.raw"],
                    },
                    {
                        "subject_id": "subject_large",
                        "batch_status": "processed",
                        "gate_decision": "review",
                        "fixture_count": 9,
                        "next_evidence_needed": ["formal_reviewer_observation_summary"],
                        "subject_artifact_count": 6,
                        "subject_artifacts": ["evidence_report.md", "gate_verdict.json", "workflow_summary.json"],
                    },
                ]
            }), encoding="utf-8")

            result = build_har_batch_review_workflow(batch)
            out = Path(result["output_dir"])

            phase1 = json.loads((out / "phase_1_reviewer_packet.json").read_text(encoding="utf-8"))
            self.assertEqual(phase1["reviewer_subjects"][0]["subject_id"], "subject_large")
            self.assertFalse(phase1["raw_har_review_allowed"])
            self.assertNotIn("unsafe.raw", phase1["reviewer_subjects"][1]["allowed_artifacts"])

            phase2 = json.loads((out / "phase_2_boundary_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(phase2["status"], "blocked_until_explicit_non_production_boundary_context")
            self.assertFalse(phase2["boundary_probe_executed"])

            phase3 = json.loads((out / "phase_3_approved_replay_plan.json").read_text(encoding="utf-8"))
            self.assertFalse(phase3["approved_replay_executed"])
            self.assertFalse(phase3["wildcard_scope_allowed"])

            phase5 = json.loads((out / "phase_5_readiness_gate.json").read_text(encoding="utf-8"))
            self.assertEqual(phase5["release_readiness"], "not_ready")
            self.assertIn("formal_reviewer_observation_summary", phase5["blocking_requirements"])

            phase6 = json.loads((out / "phase_6_sanitized_intent_review.json").read_text(encoding="utf-8"))
            self.assertEqual(phase6["status"], "complete_for_current_batch")
            self.assertTrue(phase6["redthread_evaluation_required"])
            self.assertFalse(phase6["confirmed_security_finding_claimed"])
            self.assertIn("advancement_summary.json", phase6["intent_review_artifacts"])
            self.assertIn("redthread_execution_handoff.json", phase6["intent_review_artifacts"])
            self.assertIn("redthread_execution_handoff_validation.json", phase6["intent_review_artifacts"])
            self.assertIn("redthread_intent_evidence.json", phase6["intent_review_artifacts"])
            self.assertIn("redthread_importability_report.json", phase6["intent_review_artifacts"])
            self.assertIn("redthread_candidate_workflow_import.json", phase6["intent_review_artifacts"])
            self.assertIn("redthread_product_proof.json", phase6["intent_review_artifacts"])
            self.assertIn("redthread_operator_handoff.md", phase6["intent_review_artifacts"])
            self.assertIn("business_validation_plan.json", phase6["intent_review_artifacts"])
            self.assertEqual(phase6["execution_candidate_count"], 2)
            self.assertEqual(phase6["execution_handoff_path"], "intent_review/redthread_execution_handoff.json")
            self.assertEqual(phase6["redthread_intent_evidence_path"], "intent_review/redthread_intent_evidence.json")
            self.assertTrue(phase6["redthread_importable"])
            self.assertTrue(phase6["candidate_workflow_created"])
            self.assertEqual(phase6["candidate_workflow_import_path"], "intent_review/redthread_candidate_workflow_import.json")
            self.assertTrue(phase6["product_proof_passed"])
            self.assertTrue((batch / "intent_review" / "redthread_evidence_export.json").exists())
            self.assertTrue((batch / "intent_review" / "advancement_summary.json").exists())
            self.assertTrue((batch / "intent_review" / "redthread_execution_handoff.json").exists())
            self.assertTrue((batch / "intent_review" / "redthread_intent_evidence.json").exists())
            self.assertTrue((batch / "intent_review" / "redthread_importability_report.json").exists())
            self.assertTrue((batch / "intent_review" / "redthread_candidate_workflow_import.json").exists())
            self.assertTrue((batch / "intent_review" / "redthread_product_proof.json").exists())
            self.assertTrue((batch / "intent_review" / "redthread_operator_handoff.md").exists())
            self.assertTrue((batch / "intent_review" / "business_validation_plan.json").exists())
            self.assertTrue((batch / "intent_review" / "schema_validation.json").exists())
            self.assertTrue((batch / "intent_review" / "redthread_evidence_contract_preview.json").exists())

            audit = json.loads((out / "privacy_audit.json").read_text(encoding="utf-8"))
            self.assertTrue(audit["passed"])


if __name__ == "__main__":
    unittest.main()
