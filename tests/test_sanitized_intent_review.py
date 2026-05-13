from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.build_sanitized_intent_review import (
    build_intent_review,
    build_intent_review_context,
    build_redthread_evidence_export,
    build_redthread_execution_handoff,
    build_product_proof_report,
    build_pentest_agent_handoff,
    build_pentest_context_package,
    build_redthread_candidate_workflow_import,
    build_redthread_importability_report,
    build_redthread_intent_evidence,
    build_sanitized_intent_review,
    validate_execution_handoff,
    validate_redthread_intent_evidence,
    validate_intent_review_contract,
    validate_pentest_context_package,
    validate_approved_auth_bundle,
    validate_approved_write_bundle,
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

    def _valid_auth_bundle(self) -> dict[str, object]:
        return {
            "schema_version": "adopt_redthread.approved_auth_bundle.v0",
            "bundle_id": "auth_bundle_test_001",
            "approved": True,
            "approval": {
                "approved_by_role": "security_reviewer",
                "approved_at": "2026-05-05T00:00:00Z",
                "expires_at": "2026-05-06T00:00:00Z",
                "environment": "non_production",
                "scope": {
                    "subject_ids": ["subject_001"],
                    "workflow_ids": ["workflow_subject_001_candidate_001"],
                    "endpoint_ids": ["endpoint_subject_001_candidate_001"],
                    "allowed_actions": ["authenticated_read_probe"],
                },
            },
            "credential_references": {
                "storage": "external_reference_only",
                "values_included": False,
                "references": [
                    {
                        "reference_id": "credential_ref_001",
                        "reference_type": "env_var",
                        "handle": "ADOPT_REDTHREAD_TEST_AUTH_HANDLE",
                        "purpose": "approved_runtime_credential_reference",
                    }
                ],
            },
            "rendering_policy": {
                "markdown_rendering_allowed": False,
                "llm_prompt_inclusion_allowed": False,
                "log_value_allowed": False,
            },
            "safety": {
                "judge_agent_required": True,
                "state_changing_actions_allowed": False,
                "write_bundle_required_for_state_change": True,
            },
        }

    def _valid_write_bundle(self) -> dict[str, object]:
        return {
            "schema_version": "adopt_redthread.approved_write_bundle.v0",
            "bundle_id": "write_bundle_test_001",
            "approved": True,
            "auth_bundle_embedded": False,
            "approval": {
                "approved_by_role": "security_reviewer",
                "approved_at": "2026-05-05T00:00:00Z",
                "expires_at": "2026-05-06T00:00:00Z",
                "environment": "non_production",
                "scope": {
                    "subject_ids": ["subject_001"],
                    "workflow_ids": ["workflow_subject_001_candidate_001"],
                },
            },
            "write_policy": {
                "allowed_operation_classes": ["idempotent_check", "reversible_non_destructive_write"],
                "forbidden_operation_classes": [
                    "bulk_export",
                    "delete",
                    "external_notification",
                    "payment",
                    "privilege_change",
                    "production_mutation",
                ],
            },
            "rendering_policy": {
                "markdown_rendering_allowed": False,
                "llm_prompt_inclusion_allowed": False,
                "log_value_allowed": False,
            },
            "safety": {
                "dry_run_required_by_default": True,
                "destructive_operations_allowed": False,
                "live_execution_authorized_by_bundle": False,
                "requires_runtime_confirmation": True,
                "rollback_or_cleanup_notes": "Downstream operator must document cleanup before any approved runtime action.",
            },
        }

    def _pentest_package_for_validation(self, root: Path) -> dict[str, object]:
        batch = self._write_batch(root)
        context = build_intent_review_context(batch)
        review = build_intent_review(context)
        handoff = build_redthread_execution_handoff(review)
        intent_evidence = build_redthread_intent_evidence(review, handoff)
        intent_validation = validate_redthread_intent_evidence(intent_evidence)
        workflow_import = build_redthread_candidate_workflow_import(intent_evidence, intent_validation)
        return build_pentest_context_package(review, handoff, intent_evidence, workflow_import)

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
            self.assertIn("local_model_observations", subject)
            self.assertFalse(subject["local_model_observations"]["useful_delta"])
            self.assertIn("RedThread first check", markdown)
            self.assertTrue(export["promotion_semantics"]["redthread_evaluation_required"])
            self.assertEqual(export["execution_handoff"]["artifact_name"], "redthread_execution_handoff.json")
            self.assertEqual(export["execution_handoff"]["candidate_count"], 1)
            self.assertFalse(export["execution_handoff"]["live_execution_allowed"])
            package_dir = out / "pentest_context_package_v0"
            self.assertTrue(package_dir.exists())
            package = json.loads((package_dir / "pentest_context_package.json").read_text(encoding="utf-8"))
            handoff = json.loads((package_dir / "pentest_agent_handoff.json").read_text(encoding="utf-8"))
            validation = json.loads((package_dir / "pentest_context_package_validation.json").read_text(encoding="utf-8"))
            self.assertTrue(validation["valid"])
            self.assertEqual(package["schema_version"], "adopt_redthread.pentest_context_package.v0")
            self.assertFalse(package["privacy"]["auth_values_included"])
            self.assertTrue(package["safety_policy"]["judge_agent_required"])
            self.assertTrue(package["attack_surface_hypotheses"][0]["not_a_finding"])
            self.assertTrue(handoff["candidate_objectives"][0]["requires_judge_confirmation"])
            self.assertFalse(export["promotion_semantics"]["confirmed_security_finding_claimed"])
            self.assertFalse(export["promotion_semantics"]["release_gate_override"])
            advancement = json.loads((out / "advancement_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(advancement["schema_version"], "adopt_redthread.intent_review_advancement.v0")
            self.assertEqual(advancement["summary"]["needs_boundary_context_count"], 1)
            self.assertTrue(advancement["summary"]["redthread_final_gate_required"])
            business_validation = json.loads((out / "business_validation_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(business_validation["schema_version"], "adopt_redthread.intent_review_business_validation.v0")
            self.assertIn("redthread", business_validation["ownership"])
            schema_validation = json.loads((out / "schema_validation.json").read_text(encoding="utf-8"))
            self.assertTrue(schema_validation["passed"])
            contract_preview = json.loads((out / "redthread_evidence_contract_preview.json").read_text(encoding="utf-8"))
            self.assertEqual(contract_preview["status"], "proposal_preview_not_upstreamed")
            self.assertTrue(contract_preview["promotion_recommendation"]["redthread_evaluation_required"])
            self.assertTrue(contract_preview["promotion_recommendation"]["not_proven"])
            self.assertIn("RedThread evaluation is required", markdown)
            handoff = json.loads((out / "redthread_execution_handoff.json").read_text(encoding="utf-8"))
            handoff_markdown = (out / "redthread_execution_handoff.md").read_text(encoding="utf-8")
            handoff_validation = json.loads((out / "redthread_execution_handoff_validation.json").read_text(encoding="utf-8"))
            intent_evidence = json.loads((out / "redthread_intent_evidence.json").read_text(encoding="utf-8"))
            intent_evidence_validation = json.loads((out / "redthread_intent_evidence_validation.json").read_text(encoding="utf-8"))
            importability_report = json.loads((out / "redthread_importability_report.json").read_text(encoding="utf-8"))
            workflow_import = json.loads((out / "redthread_candidate_workflow_import.json").read_text(encoding="utf-8"))
            product_proof = json.loads((out / "redthread_product_proof.json").read_text(encoding="utf-8"))
            operator_handoff = (out / "redthread_operator_handoff.md").read_text(encoding="utf-8")
            candidate = handoff["execution_candidates"][0]
            self.assertEqual(handoff["schema_version"], "adopt_redthread.execution_handoff.v0")
            self.assertEqual(handoff["summary"]["candidate_count"], 1)
            self.assertEqual(candidate["candidate_workflow_intent"], "authorization_boundary_read_review")
            self.assertEqual(candidate["execution_readiness"], "needs_context")
            self.assertEqual(candidate["recommended_redthread_action"], "collect_boundary_context")
            self.assertTrue(candidate["supporting_sanitized_observations"])
            self.assertFalse(candidate["execution_constraints"]["live_execution_allowed"])
            self.assertTrue(candidate["execution_constraints"]["redthread_final_gate_required"])
            self.assertTrue(handoff_validation["passed"])
            self.assertTrue(handoff_validation["privacy_audit_passed"])
            self.assertIn("observation_citations_required", handoff_validation["validated_rules"])
            self.assertIn("Recommended RedThread action", handoff_markdown)
            self.assertEqual(intent_evidence["schema_version"], "redthread.intent_evidence.v1")
            self.assertFalse(intent_evidence["source"]["raw_artifacts_included"])
            self.assertTrue(intent_evidence["privacy"]["sanitized"])
            self.assertFalse(intent_evidence["privacy"]["raw_har_included"])
            self.assertTrue(intent_evidence["intent"]["not_a_finding"])
            self.assertTrue(intent_evidence["evidence"])
            self.assertTrue(intent_evidence["evidence"][0]["source_observation_id"])
            self.assertTrue(intent_evidence["evidence"][0]["limitations"])
            self.assertTrue(intent_evidence["attack_plan"]["steps"])
            self.assertFalse(intent_evidence["attack_plan"]["steps"][0]["requires_raw_payload"])
            self.assertFalse(intent_evidence["attack_plan"]["steps"][0]["requires_live_execution"])
            self.assertTrue(intent_evidence_validation["importable"])
            self.assertTrue(importability_report["candidate_workflow_created"])
            self.assertEqual(importability_report["redthread_consumption_contract"]["import_as"], "candidate_evidence_not_finding")
            self.assertEqual(workflow_import["schema_version"], "redthread.candidate_workflow_import.v1")
            self.assertEqual(workflow_import["import_status"], "imported_as_candidate_workflows")
            self.assertEqual(workflow_import["candidate_workflow_count"], 1)
            self.assertFalse(workflow_import["adopt_redthread_claims"]["finding_created"])
            self.assertFalse(workflow_import["candidate_workflows"][0]["live_execution_allowed"])
            self.assertTrue(workflow_import["candidate_workflows"][0]["judge_agent_required"])
            self.assertEqual(product_proof["schema_version"], "redthread.intent_evidence_product_proof.v1")
            self.assertTrue(product_proof["passed"])
            self.assertTrue(product_proof["metrics"]["candidate_workflow_created"])
            self.assertIn("What should RedThread try next?", operator_handoff)
            self.assertIn("What is explicitly not claimed?", operator_handoff)

    def test_context_intake_makes_proof_subject_more_specific(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)
            rubric = root / "boundary.json"
            observations = root / "observations.json"
            rubric.write_text(json.dumps({
                "schema_version": "adopt_redthread.boundary_context_intake.v0",
                "boundary_area": "authorization_boundary",
                "final_evaluator": "redthread",
            }), encoding="utf-8")
            observations.write_text(json.dumps({
                "schema_version": "adopt_redthread.reviewer_observations.v0",
                "observations": [{
                    "subject_id": "subject_001",
                    "selection_reason": "Representative sanitized proof subject.",
                    "observed_behavior_summary": "Read-oriented boundary-sensitive workflow.",
                    "uncertainty_remaining": "RedThread final evaluation still required.",
                    "boundary_area": "authorization_boundary",
                    "likely_intent": "authorization_sensitive_record_review",
                    "confidence": "medium",
                    "reviewer_question": "Is this ready for RedThread-owned boundary evaluation?",
                }],
            }), encoding="utf-8")

            result = build_sanitized_intent_review(
                batch,
                root / "out",
                boundary_rubric=rubric,
                reviewer_observations=observations,
            )
            out = Path(result["output_dir"])
            review = json.loads((out / "intent_review.json").read_text(encoding="utf-8"))
            markdown = (out / "intent_review.md").read_text(encoding="utf-8")
            subject = review["subjects"][0]

            self.assertEqual(review["batch_summary"]["subjects_with_boundary_context_count"], 1)
            self.assertEqual(review["batch_summary"]["subjects_with_reviewer_observation_count"], 1)
            self.assertEqual(subject["intent_hypotheses"][0]["label"], "authorization_sensitive_record_review")
            self.assertTrue(subject["context_signals"]["boundary_context_present"])
            self.assertTrue(subject["context_signals"]["reviewer_observation_present"])
            self.assertNotIn("missing_boundary_context", subject["redthread_export_readiness"]["reason_categories"])
            self.assertNotIn("missing_reviewer_observation", subject["redthread_export_readiness"]["reason_categories"])
            advancement = json.loads((out / "advancement_summary.json").read_text(encoding="utf-8"))
            business_validation = json.loads((out / "business_validation_plan.json").read_text(encoding="utf-8"))
            self.assertTrue(subject["review_support_outcome"]["redthread_final_gate_required"])
            self.assertTrue(subject["review_support_outcome"]["not_a_confirmed_finding"])
            self.assertEqual(advancement["subjects"][0]["advancement_state"], "ready_for_redthread_evaluation")
            self.assertTrue(advancement["subjects"][0]["can_advance_to_redthread_evaluation"])
            self.assertEqual(business_validation["metrics"]["ready_for_redthread_evaluation_count"], 1)
            self.assertIn("Review-support outcome", markdown)
            handoff = json.loads((out / "redthread_execution_handoff.json").read_text(encoding="utf-8"))
            candidate = handoff["execution_candidates"][0]
            self.assertEqual(candidate["candidate_workflow_intent"], "authorization_boundary_review_candidate")
            self.assertEqual(candidate["execution_readiness"], "ready_for_redthread_review")
            self.assertEqual(candidate["recommended_redthread_action"], "evaluate_sanitized_export")

    def test_execution_handoff_validation_rejects_unsafe_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)
            context = build_intent_review_context(batch)
            review = build_intent_review(context)
            handoff = build_redthread_execution_handoff(review)
            candidate = handoff["execution_candidates"][0]
            candidate["execution_constraints"]["live_execution_allowed"] = True
            candidate["recommended_redthread_action"] = "execute_live_attack"
            candidate["operator_summary"] = "confirmed vulnerability with high severity"

            validation = validate_execution_handoff(handoff, review)

            self.assertFalse(validation["passed"])
            self.assertIn("candidate.subject_001_candidate_001.live_execution_allowed", validation["errors"])
            self.assertIn("candidate.subject_001_candidate_001.recommended_redthread_action", validation["errors"])
            self.assertIn("candidate.subject_001_candidate_001.forbidden_language.confirmed_vulnerability", validation["errors"])
            self.assertIn("candidate.subject_001_candidate_001.forbidden_language.high_severity", validation["errors"])

    def test_execution_handoff_validation_requires_observation_citations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)
            context = build_intent_review_context(batch)
            review = build_intent_review(context)
            handoff = build_redthread_execution_handoff(review)
            handoff["execution_candidates"][0]["supporting_sanitized_observations"] = []

            validation = validate_execution_handoff(handoff, review)

            self.assertFalse(validation["passed"])
            self.assertIn("candidate.subject_001_candidate_001.supporting_sanitized_observations", validation["errors"])

    def test_redthread_intent_evidence_validation_rejects_unsafe_import_package(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)
            context = build_intent_review_context(batch)
            review = build_intent_review(context)
            handoff = build_redthread_execution_handoff(review)
            package = build_redthread_intent_evidence(review, handoff)
            package["privacy"]["raw_har_included"] = True
            package["intent"]["not_a_finding"] = False
            package["evidence"][0]["limitations"] = []
            package["attack_plan"]["steps"][0]["success_condition"] = ""
            package["redthread_import"]["judge_agent_required"] = False
            package["redthread_import"]["eligible_for_regression"] = True

            validation = validate_redthread_intent_evidence(package)
            report = build_redthread_importability_report(package, validation)

            self.assertFalse(validation["importable"])
            self.assertFalse(report["importable"])
            self.assertIn("privacy.raw_har_included", validation["errors"])
            self.assertIn("intent.not_a_finding", validation["errors"])
            self.assertIn("evidence.ev_001_001.limitations", validation["errors"])
            self.assertIn("attack_plan.step_001_001.success_condition", validation["errors"])
            self.assertIn("redthread_import.judge_agent_required", validation["errors"])
            self.assertIn("redthread_import.eligible_for_regression", validation["errors"])

    def test_candidate_workflow_import_blocks_invalid_intent_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)
            context = build_intent_review_context(batch)
            review = build_intent_review(context)
            handoff = build_redthread_execution_handoff(review)
            package = build_redthread_intent_evidence(review, handoff)
            package["attack_plan"]["steps"][0]["requires_live_execution"] = True

            validation = validate_redthread_intent_evidence(package)
            importability = build_redthread_importability_report(package, validation)
            workflow_import = build_redthread_candidate_workflow_import(package, validation)
            proof = build_product_proof_report(package, validation, importability, workflow_import)

            self.assertFalse(validation["importable"])
            self.assertEqual(workflow_import["import_status"], "blocked")
            self.assertEqual(workflow_import["candidate_workflow_count"], 0)
            self.assertFalse(proof["passed"])
            self.assertFalse(workflow_import["adopt_redthread_claims"]["finding_created"])
            self.assertFalse(workflow_import["adopt_redthread_claims"]["live_execution_authorized"])

    def test_pentest_context_package_preserves_bridge_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = self._write_batch(Path(tmp))
            context = build_intent_review_context(batch)
            review = build_intent_review(context)
            handoff = build_redthread_execution_handoff(review)
            intent_evidence = build_redthread_intent_evidence(review, handoff)
            intent_validation = validate_redthread_intent_evidence(intent_evidence)
            workflow_import = build_redthread_candidate_workflow_import(intent_evidence, intent_validation)
            package = build_pentest_context_package(review, handoff, intent_evidence, workflow_import)
            agent_handoff = build_pentest_agent_handoff(package)
            validation = validate_pentest_context_package(package, agent_handoff)

            self.assertTrue(validation["valid"])
            self.assertEqual(package["package_summary"]["endpoint_count"], 1)
            self.assertFalse(package["safety_policy"]["default_live_execution_allowed"])
            self.assertFalse(package["privacy"]["raw_har_included"])
            self.assertFalse(package["privacy"]["auth_values_included"])
            self.assertEqual(agent_handoff["auth_bundle_policy"]["approved_auth_bundle_schema_version"], "adopt_redthread.approved_auth_bundle.v0")
            self.assertIn("execute_live_without_opt_in_bundle", agent_handoff["forbidden_actions"])
            self.assertTrue(agent_handoff["candidate_objectives"][0]["evidence_ids"])

    def test_pentest_context_validation_rejects_overclaim_and_auth_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            batch = self._write_batch(Path(tmp))
            context = build_intent_review_context(batch)
            review = build_intent_review(context)
            handoff = build_redthread_execution_handoff(review)
            intent_evidence = build_redthread_intent_evidence(review, handoff)
            intent_validation = validate_redthread_intent_evidence(intent_evidence)
            workflow_import = build_redthread_candidate_workflow_import(intent_evidence, intent_validation)
            package = build_pentest_context_package(review, handoff, intent_evidence, workflow_import)
            agent_handoff = build_pentest_agent_handoff(package)
            package["privacy"]["auth_values_included"] = True
            package["manifest"]["auth_bundle_included"] = True
            package["approved_auth_bundle"] = {}
            package["safety_policy"]["judge_agent_required"] = False
            package["attack_surface_hypotheses"][0]["summary"] = "confirmed vulnerability in sanitized workflow"
            agent_handoff["candidate_objectives"][0]["summary"] = "high severity issue"

            validation = validate_pentest_context_package(package, agent_handoff)

            self.assertFalse(validation["valid"])
            self.assertIn("privacy.auth_values_included", validation["errors"])
            self.assertIn("manifest.auth_bundle_included", validation["errors"])
            self.assertIn("package.auth_bundle_embedded", validation["errors"])
            self.assertIn("safety_policy.judge_agent_required", validation["errors"])
            self.assertTrue(any("forbidden_language" in error for error in validation["errors"]))

    def test_approved_auth_bundle_validation_accepts_references_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self._pentest_package_for_validation(Path(tmp) / "pkg")

            validation = validate_approved_auth_bundle(self._valid_auth_bundle(), package)

            self.assertTrue(validation["valid"])
            self.assertTrue(validation["privacy_safe"])
            self.assertEqual(validation["credential_reference_count"], 1)
            self.assertFalse(validation["bundle_values_renderable"])
            self.assertFalse(validation["live_execution_authorized"])
            self.assertFalse(validation["state_changing_actions_allowed"])

    def test_approved_auth_bundle_validation_rejects_literals_and_unbounded_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self._pentest_package_for_validation(Path(tmp) / "pkg")
            bundle = self._valid_auth_bundle()
            bundle["approval"]["scope"]["subject_ids"] = ["*"]  # type: ignore[index]
            bundle["approval"]["expires_at"] = ""  # type: ignore[index]
            bundle["credential_references"]["references"][0]["value"] = "Bearer example-token"  # type: ignore[index]

            validation = validate_approved_auth_bundle(bundle, package)

            self.assertFalse(validation["valid"])
            self.assertIn("auth_bundle.approval.expires_at", validation["errors"])
            self.assertIn("auth_bundle.scope.subject_ids.unbounded", validation["errors"])
            self.assertTrue(any("forbidden_auth_value_key" in error for error in validation["errors"]))
            self.assertGreater(validation["marker_hit_count"], 0)

    def test_approved_write_bundle_validation_accepts_bounded_non_destructive_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self._pentest_package_for_validation(Path(tmp) / "pkg")

            validation = validate_approved_write_bundle(self._valid_write_bundle(), package)

            self.assertTrue(validation["valid"])
            self.assertTrue(validation["privacy_safe"])
            self.assertEqual(validation["allowed_operation_class_count"], 2)
            self.assertTrue(validation["dry_run_required_by_default"])
            self.assertTrue(validation["requires_runtime_confirmation"])
            self.assertFalse(validation["destructive_operations_allowed"])
            self.assertFalse(validation["live_execution_authorized"])

    def test_approved_write_bundle_validation_rejects_destructive_or_embedded_auth_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            package = self._pentest_package_for_validation(Path(tmp) / "pkg")
            bundle = self._valid_write_bundle()
            bundle["auth_bundle_embedded"] = True
            bundle["approval"]["scope"]["workflow_ids"] = ["all"]  # type: ignore[index]
            bundle["write_policy"]["allowed_operation_classes"] = ["delete"]  # type: ignore[index]
            bundle["write_policy"]["forbidden_operation_classes"] = []  # type: ignore[index]
            bundle["safety"]["destructive_operations_allowed"] = True  # type: ignore[index]
            bundle["credential_references"] = {"references": []}

            validation = validate_approved_write_bundle(bundle, package)

            self.assertFalse(validation["valid"])
            self.assertIn("write_bundle.auth_bundle_embedded", validation["errors"])
            self.assertIn("write_bundle.auth_material_embedded", validation["errors"])
            self.assertIn("write_bundle.scope.workflow_ids.unbounded", validation["errors"])
            self.assertIn("write_bundle.write_policy.allowed_operation_classes.unsupported.delete", validation["errors"])
            self.assertIn("write_bundle.safety.destructive_operations_allowed", validation["errors"])

    def test_build_validates_opt_in_bundles_without_copying_values_into_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root / "source")
            auth_path = root / "approved_auth_bundle.json"
            write_path = root / "approved_write_bundle.json"
            auth_path.write_text(json.dumps(self._valid_auth_bundle()), encoding="utf-8")
            write_path.write_text(json.dumps(self._valid_write_bundle()), encoding="utf-8")

            result = build_sanitized_intent_review(
                batch,
                root / "out",
                approved_auth_bundle=auth_path,
                approved_write_bundle=write_path,
            )

            self.assertTrue(result["approved_auth_bundle_valid"])
            self.assertTrue(result["approved_write_bundle_valid"])
            bundle_dir = root / "out" / "opt_in_bundle_validations"
            summary = json.loads((bundle_dir / "auth_write_bundle_validation_summary.json").read_text(encoding="utf-8"))
            auth_validation = json.loads((bundle_dir / "approved_auth_bundle_validation.json").read_text(encoding="utf-8"))
            self.assertTrue(summary["ready_for_downstream_opt_in_review"])
            self.assertTrue(auth_validation["valid"])
            output_text = "\n".join(path.read_text(encoding="utf-8") for path in (root / "out").rglob("*.json"))
            output_text += "\n" + "\n".join(path.read_text(encoding="utf-8") for path in (root / "out").rglob("*.md"))
            self.assertNotIn("ADOPT_REDTHREAD_TEST_AUTH_HANDLE", output_text)
            self.assertFalse((root / "out" / "pentest_context_package_v0" / "approved_auth_bundle.json").exists())
            self.assertFalse((root / "out" / "pentest_context_package_v0" / "approved_write_bundle.json").exists())

    def test_schema_validation_rejects_release_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)
            context = build_intent_review_context(batch)
            review = build_intent_review(context)
            export = build_redthread_evidence_export(review)
            export["promotion_semantics"]["release_gate_override"] = True

            validation = validate_intent_review_contract(review, export)

            self.assertFalse(validation["passed"])
            self.assertIn("promotion_semantics.forbidden_true.release_gate_override", validation["errors"])

    def test_llm_prompt_prepare_mode_writes_sanitized_prompt_without_model_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)

            result = build_sanitized_intent_review(
                batch,
                root / "out",
                agent_mode="llm",
                prepare_llm_prompt=True,
            )

            self.assertEqual(result["status"], "llm_prompt_prepared")
            self.assertTrue((root / "out" / "intent_review_context.json").exists())
            self.assertTrue((root / "out" / "llm_intent_review_prompt.json").exists())
            prompt = json.loads((root / "out" / "llm_intent_review_prompt.json").read_text(encoding="utf-8"))
            self.assertEqual(prompt["required_output_template"]["schema_version"], "adopt_redthread.sanitized_intent_review.v0")
            self.assertIn("local_model_observations", prompt["required_output_template"]["subjects"][0])
            self.assertIn("Do not return sanitized_context as the top-level object.", prompt["output_rules"])
            self.assertFalse(prompt["execution_handoff_policy"]["local_model_may_author_candidates"])
            self.assertEqual(prompt["execution_handoff_policy"]["local_model_allowed_enrichment_field"], "subjects[].local_model_observations")
            self.assertFalse((root / "out" / "intent_review.json").exists())

    def test_auto_mode_falls_back_to_deterministic_when_local_llm_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)

            with patch.dict(os.environ, {}, clear=True):
                result = build_sanitized_intent_review(batch, root / "out", agent_mode="auto")

            self.assertEqual(result["agent_mode"], "auto")
            self.assertEqual(result["local_llm_status"]["status"], "unavailable")
            self.assertTrue(result["local_llm_status"]["fallback_to_deterministic"])
            self.assertTrue((root / "out" / "llm_intent_review_prompt.json").exists())
            self.assertTrue((root / "out" / "local_llm_status.json").exists())
            review = json.loads((root / "out" / "intent_review.json").read_text(encoding="utf-8"))
            self.assertEqual(review["subjects"][0]["intent_hypotheses"][0]["label"], "account_management")

    def test_auto_mode_accepts_valid_local_llm_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)
            context = build_intent_review_context(batch)
            llm_review = build_intent_review(context)
            llm_review["subjects"][0]["intent_hypotheses"][0]["label"] = "local_model_advisory_intent"
            llm_path = root / "llm_review.json"
            llm_path.write_text(json.dumps(llm_review), encoding="utf-8")

            with patch.dict(os.environ, {"INTENT_REVIEW_LOCAL_LLM_CMD": f"cat {llm_path}"}, clear=True):
                result = build_sanitized_intent_review(batch, root / "out", agent_mode="auto")

            self.assertEqual(result["local_llm_status"]["status"], "accepted")
            self.assertFalse(result["local_llm_status"]["fallback_to_deterministic"])
            review = json.loads((root / "out" / "intent_review.json").read_text(encoding="utf-8"))
            self.assertEqual(review["subjects"][0]["intent_hypotheses"][0]["label"], "local_model_advisory_intent")

    def test_auto_mode_rejects_structurally_incomplete_local_llm_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)
            context = build_intent_review_context(batch)
            llm_review = build_intent_review(context)
            del llm_review["subjects"][0]["workflow_classification"]["workflow_class"]
            llm_path = root / "llm_review.json"
            llm_path.write_text(json.dumps(llm_review), encoding="utf-8")

            with patch.dict(os.environ, {"INTENT_REVIEW_LOCAL_LLM_CMD": f"cat {llm_path}"}, clear=True):
                result = build_sanitized_intent_review(batch, root / "out", agent_mode="auto")

            self.assertEqual(result["local_llm_status"]["status"], "failed")
            self.assertTrue(result["local_llm_status"]["fallback_to_deterministic"])
            review = json.loads((root / "out" / "intent_review.json").read_text(encoding="utf-8"))
            self.assertEqual(review["subjects"][0]["workflow_classification"]["workflow_class"], "mixed")
            self.assertTrue((root / "out" / "redthread_execution_handoff.json").exists())

    def test_llm_mode_accepts_schema_valid_offline_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)
            context = build_intent_review_context(batch)
            llm_review = build_intent_review(context)
            llm_path = root / "llm_review.json"
            llm_path.write_text(json.dumps(llm_review), encoding="utf-8")

            result = build_sanitized_intent_review(
                batch,
                root / "out",
                agent_mode="llm",
                llm_review_output=llm_path,
            )

            self.assertEqual(result["agent_mode"], "llm")
            self.assertTrue((root / "out" / "llm_intent_review_prompt.json").exists())
            export = json.loads((root / "out" / "redthread_evidence_export.json").read_text(encoding="utf-8"))
            self.assertTrue(export["promotion_semantics"]["redthread_evaluation_required"])

    def test_llm_mode_rejects_claimed_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            batch = self._write_batch(root)
            context = build_intent_review_context(batch)
            llm_review = build_intent_review(context)
            llm_review["subjects"][0]["finding_semantics"]["confirmed_finding_claimed"] = True
            llm_path = root / "llm_review.json"
            llm_path.write_text(json.dumps(llm_review), encoding="utf-8")

            with self.assertRaises(ValueError):
                build_sanitized_intent_review(
                    batch,
                    root / "out",
                    agent_mode="llm",
                    llm_review_output=llm_path,
                )

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
