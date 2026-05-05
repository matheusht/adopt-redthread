from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_sanitized_intent_review import (
    build_intent_review_context,
    build_sanitized_intent_review,
)


class SanitizedIntentReviewTests(unittest.TestCase):
    def _write_batch(self, root: Path) -> Path:
        batch = root / "batch"
        subject_dir = batch / "subjects" / "subject_001"
        review_dir = batch / "review_workflow"
        subject_dir.mkdir(parents=True)
        review_dir.mkdir(parents=True)
        (batch / "batch_manifest.json").write_text(json.dumps({
            "batch_status": "complete",
            "subject_count": 1,
            "raw_input_paths_persisted": False,
        }), encoding="utf-8")
        (batch / "aggregate_blockers.json").write_text(json.dumps({
            "followup_required": True,
            "followup_subject_count": 1,
            "evidence_review_subject_count": 1,
            "remediation_subject_count": 0,
            "missing_boundary_evidence_subject_count": 1,
            "confirmed_security_finding_count": 0,
            "recommended_batch_next_step": "collect_sanitized_review_evidence",
        }), encoding="utf-8")
        (batch / "subject_index.json").write_text(json.dumps({
            "subjects": [{
                "subject_id": "subject_001",
                "batch_status": "processed",
                "gate_decision": "review",
                "fixture_count": 3,
                "subject_artifacts": ["workflow_summary.json", "subject_summary.json", "evidence_report.md", "unsafe.raw"],
            }]
        }), encoding="utf-8")
        (subject_dir / "subject_summary.json").write_text(json.dumps({
            "schema_version": "adopt_redthread.har_evidence_batch_subject.v1",
            "subject_id": "subject_001",
            "batch_status": "processed",
            "gate_decision": "review",
            "fixture_count": 3,
            "auth_surface_present": True,
            "write_surface_present": True,
            "boundary_evidence_present": False,
            "redthread_replay_passed": True,
            "dryrun_executed": True,
            "live_execution_performed": False,
            "confirmed_security_finding": False,
            "primary_blocker_categories": [],
            "next_evidence_needed": [
                "boundary_context_or_boundary_execution_evidence_if_release_requires_it",
                "formal_reviewer_observation_summary",
            ],
            "subject_artifacts": ["workflow_summary.json", "subject_summary.json", "evidence_report.md"],
        }), encoding="utf-8")
        (subject_dir / "workflow_summary.json").write_text(json.dumps({
            "fixture_count": 3,
            "gate_decision": "review",
            "redthread_replay_passed": True,
            "redthread_dryrun_executed": True,
            "live_execution_performed": False,
            "raw_input_values_persisted": False,
        }), encoding="utf-8")
        (subject_dir / "privacy_audit.json").write_text(json.dumps({
            "passed": True,
            "marker_hit_count": 0,
            "raw_field_hit_count": 0,
        }), encoding="utf-8")
        (subject_dir / "evidence_report.md").write_text("# Sanitized evidence report\n\nNo raw capture values included.\n", encoding="utf-8")
        (review_dir / "phase_1_reviewer_packet.json").write_text(json.dumps({"phase": "phase_1_reviewer_validation"}), encoding="utf-8")
        return batch

    def test_context_builder_uses_sanitized_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = self._write_batch(Path(tmp))
            context = build_intent_review_context(batch)

            self.assertEqual(context["schema_version"], "adopt_redthread.sanitized_intent_review_context.v0")
            self.assertFalse(context["source_batch"]["llm_raw_artifact_access"])
            self.assertFalse(context["source_batch"]["raw_input_paths_persisted"])
            self.assertEqual(context["subjects"][0]["subject_artifacts"], ["workflow_summary.json", "subject_summary.json", "evidence_report.md"])
            self.assertEqual(context["review_workflow_artifacts"][0]["artifact_name"], "phase_1_reviewer_packet.json")

    def test_builds_review_and_redthread_export_without_claiming_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)
            result = build_sanitized_intent_review(batch, root / "out")
            out = Path(result["output_dir"])

            review = json.loads((out / "intent_review.json").read_text(encoding="utf-8"))
            export = json.loads((out / "redthread_evidence_export.json").read_text(encoding="utf-8"))
            markdown = (out / "intent_review.md").read_text(encoding="utf-8")
            audit = json.loads((out / "privacy_audit.json").read_text(encoding="utf-8"))

            self.assertTrue(audit["passed"])
            subject = review["subjects"][0]
            self.assertEqual(subject["workflow_classification"]["workflow_class"], "mixed")
            self.assertTrue(subject["approved_execution_requirements"]["approved_replay_required"])
            self.assertTrue(subject["approved_execution_requirements"]["boundary_proof_required"])
            self.assertFalse(subject["finding_semantics"]["confirmed_finding_claimed"])
            self.assertFalse(subject["finding_semantics"]["severity_claimed"])
            self.assertIn("missing_boundary_context", subject["redthread_export_readiness"]["reason_categories"])
            self.assertTrue(export["promotion_semantics"]["redthread_evaluation_required"])
            self.assertFalse(export["promotion_semantics"]["confirmed_security_finding_claimed"])
            self.assertFalse(export["promotion_semantics"]["release_gate_override"])
            self.assertIn("RedThread evaluation is required", markdown)

    def test_privacy_audit_fails_on_forbidden_raw_field_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = self._write_batch(Path(tmp))
            summary_path = batch / "subjects" / "subject_001" / "subject_summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["next_evidence_needed"] = ["authorization: not allowed"]
            summary_path.write_text(json.dumps(summary), encoding="utf-8")

            with self.assertRaises(ValueError):
                build_sanitized_intent_review(batch, Path(tmp) / "out", fail_on_marker_hit=True)


if __name__ == "__main__":
    unittest.main()
