#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_har_evidence_batch import marker_audit

CONTEXT_SCHEMA_VERSION = "adopt_redthread.sanitized_intent_review_context.v0"
REVIEW_SCHEMA_VERSION = "adopt_redthread.sanitized_intent_review.v0"
EXPORT_SCHEMA_VERSION = "adopt_redthread.redthread_evidence_export.v0"
CONTRACT_PREVIEW_SCHEMA_VERSION = "redthread.evidence_contract_preview.v0"
ADVANCEMENT_SCHEMA_VERSION = "adopt_redthread.intent_review_advancement.v0"
BUSINESS_VALIDATION_SCHEMA_VERSION = "adopt_redthread.intent_review_business_validation.v0"
BOUNDARY_RUBRIC_SCHEMA_VERSION = "adopt_redthread.boundary_context_intake.v0"
REVIEWER_OBSERVATIONS_SCHEMA_VERSION = "adopt_redthread.reviewer_observations.v0"
EXECUTION_HANDOFF_SCHEMA_VERSION = "adopt_redthread.execution_handoff.v0"
INTENT_EVIDENCE_SCHEMA_VERSION = "redthread.intent_evidence.v1"
INTENT_EVIDENCE_VALIDATION_SCHEMA_VERSION = "redthread.intent_evidence_validation.v1"
IMPORTABILITY_REPORT_SCHEMA_VERSION = "redthread.importability_report.v1"
CANDIDATE_WORKFLOW_IMPORT_SCHEMA_VERSION = "redthread.candidate_workflow_import.v1"
PRODUCT_PROOF_SCHEMA_VERSION = "redthread.intent_evidence_product_proof.v1"

ALLOWED_SUBJECT_ARTIFACTS = {
    "workflow_summary.json",
    "subject_summary.json",
    "evidence_report.md",
    "privacy_audit.json",
}

FORBIDDEN_CLAIM_LANGUAGE = ("critical severity", "high severity", "confirmed vulnerability", "exploitable")
HANDOFF_RECOMMENDED_ACTIONS = {
    "collect_boundary_context",
    "collect_reviewer_observation",
    "evaluate_sanitized_export",
    "prepare_reviewed_replay_plan",
    "redthread_triage",
}
HANDOFF_REQUIRED_CANDIDATE_KEYS = {
    "candidate_id",
    "subject_id",
    "rank",
    "candidate_workflow_intent",
    "evidence_strength",
    "execution_readiness",
    "recommended_redthread_action",
    "operator_summary",
    "supporting_sanitized_observations",
    "missing_context",
    "execution_constraints",
    "redthread_decides",
    "forbidden_interpretation",
}
HANDOFF_FORBIDDEN_LANGUAGE = (
    "confirmed finding",
    "confirmed vulnerability",
    "critical severity",
    "high severity",
    "exploit confirmed",
    "scanner result",
    "release approved",
    "live execution allowed",
    "is vulnerable",
)
INTENT_EVIDENCE_FORBIDDEN_LANGUAGE = HANDOFF_FORBIDDEN_LANGUAGE + (
    "severity",
    "exploit proof",
    "scanner finding",
    "regression ready",
    "finding confirmed",
)
INTENT_EVIDENCE_REQUIRED_PRIVACY_FALSE_FLAGS = {
    "raw_har_included",
    "raw_urls_included",
    "raw_headers_included",
    "raw_cookies_included",
    "raw_bodies_included",
    "secrets_included",
    "raw_payloads_included",
}

REVIEW_REQUIRED_KEYS = {
    "schema_version",
    "review_id",
    "source_batch",
    "privacy_attestation",
    "subjects",
    "batch_summary",
}
EXPORT_REQUIRED_KEYS = {
    "schema_version",
    "export_id",
    "source",
    "evidence_envelope",
    "workflow_evidence",
    "intent_context",
    "execution_requirements",
    "promotion_semantics",
    "privacy_attestation",
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return _read_json(path)


def _safe_report_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"present": False, "audited": False, "marker_audit_passed": True}
    text = path.read_text(encoding="utf-8")
    audit = marker_audit(text)
    return {
        "present": True,
        "audited": True,
        "marker_audit_passed": bool(audit["passed"]),
        "marker_hit_count": int(audit["marker_hit_count"]),
        "raw_field_hit_count": int(audit["raw_field_hit_count"]),
    }


def _review_workflow_inventory(batch_dir: Path) -> list[dict[str, Any]]:
    review_dir = batch_dir / "review_workflow"
    if not review_dir.exists():
        return []
    artifacts: list[dict[str, Any]] = []
    for path in sorted(review_dir.iterdir()):
        if path.suffix not in {".json", ".md"} or not path.name.startswith("phase_"):
            continue
        artifacts.append({"artifact_name": path.name, "artifact_role": "sanitized_phase_review_artifact"})
    return artifacts


def _load_optional_intake(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {"present": False}
    payload = _read_json(Path(path))
    payload["present"] = True
    return payload


def _observation_by_subject(observations: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_subject: dict[str, dict[str, Any]] = {}
    for item in observations.get("observations", []):
        if not isinstance(item, dict):
            continue
        enriched = dict(item)
        enriched["present"] = True
        by_subject[str(enriched.get("subject_id", "unknown_subject"))] = enriched
    return by_subject


def build_intent_review_context(
    batch_dir: str | Path,
    *,
    boundary_rubric: str | Path | None = None,
    reviewer_observations: str | Path | None = None,
) -> dict[str, Any]:
    batch_dir = Path(batch_dir)
    boundary_context = _load_optional_intake(boundary_rubric)
    observations = _load_optional_intake(reviewer_observations)
    observations_by_subject = _observation_by_subject(observations)
    manifest = _read_json(batch_dir / "batch_manifest.json")
    aggregate = _read_json(batch_dir / "aggregate_blockers.json")
    subject_index = _read_json(batch_dir / "subject_index.json")

    subjects: list[dict[str, Any]] = []
    for index_subject in subject_index.get("subjects", []):
        subject_id = str(index_subject.get("subject_id", "unknown_subject"))
        subject_dir = batch_dir / "subjects" / subject_id
        subject_summary = _optional_json(subject_dir / "subject_summary.json")
        workflow_summary = _optional_json(subject_dir / "workflow_summary.json")
        privacy_audit = _optional_json(subject_dir / "privacy_audit.json")
        subjects.append({
            "subject_id": subject_id,
            "batch_status": index_subject.get("batch_status", subject_summary.get("batch_status", "unknown")),
            "gate_decision": index_subject.get("gate_decision", subject_summary.get("gate_decision", "unknown")),
            "fixture_count": int(index_subject.get("fixture_count") or subject_summary.get("fixture_count") or 0),
            "auth_surface_present": bool(subject_summary.get("auth_surface_present", False)),
            "write_surface_present": bool(subject_summary.get("write_surface_present", False)),
            "boundary_evidence_present": bool(subject_summary.get("boundary_evidence_present", False)),
            "redthread_replay_passed": bool(subject_summary.get("redthread_replay_passed", False)),
            "dryrun_executed": bool(subject_summary.get("dryrun_executed", workflow_summary.get("redthread_dryrun_executed", False))),
            "live_execution_performed": bool(subject_summary.get("live_execution_performed", False)),
            "confirmed_security_finding": bool(subject_summary.get("confirmed_security_finding", False)),
            "primary_blocker_categories": list(subject_summary.get("primary_blocker_categories", [])),
            "next_evidence_needed": list(subject_summary.get("next_evidence_needed", [])),
            "subject_artifacts": [
                name for name in index_subject.get("subject_artifacts", subject_summary.get("subject_artifacts", []))
                if name in ALLOWED_SUBJECT_ARTIFACTS
            ],
            "workflow_summary": {
                "fixture_count": int(workflow_summary.get("fixture_count") or 0),
                "gate_decision": workflow_summary.get("gate_decision", "unknown"),
                "redthread_replay_passed": bool(workflow_summary.get("redthread_replay_passed", False)),
                "redthread_dryrun_executed": bool(workflow_summary.get("redthread_dryrun_executed", False)),
                "live_execution_performed": bool(workflow_summary.get("live_execution_performed", False)),
                "raw_input_values_persisted": bool(workflow_summary.get("raw_input_values_persisted", False)),
            },
            "privacy_audit": {
                "passed": bool(privacy_audit.get("passed", True)),
                "marker_hit_count": int(privacy_audit.get("marker_hit_count", 0)),
                "raw_field_hit_count": int(privacy_audit.get("raw_field_hit_count", 0)),
            },
            "evidence_report_summary": _safe_report_summary(subject_dir / "evidence_report.md"),
            "reviewer_observation": observations_by_subject.get(subject_id, {"present": False}),
            "boundary_context": boundary_context,
        })

    context = {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "source_batch": {
            "batch_status": manifest.get("batch_status", "unknown"),
            "artifact_family": "offline_har_evidence_batch",
            "raw_input_paths_persisted": bool(manifest.get("raw_input_paths_persisted", False)),
            "llm_raw_artifact_access": False,
            "subject_count": int(manifest.get("subject_count") or len(subjects)),
            "processed_subject_count": sum(1 for s in subjects if s["batch_status"] == "processed"),
            "privacy_blocked_subject_count": sum(1 for s in subjects if s["batch_status"] == "privacy_blocked" or not s["privacy_audit"]["passed"]),
        },
        "aggregate": {
            "followup_required": bool(aggregate.get("followup_required", False)),
            "followup_subject_count": int(aggregate.get("followup_subject_count", 0)),
            "evidence_review_subject_count": int(aggregate.get("evidence_review_subject_count", 0)),
            "remediation_subject_count": int(aggregate.get("remediation_subject_count", 0)),
            "missing_boundary_evidence_subject_count": int(aggregate.get("missing_boundary_evidence_subject_count", 0)),
            "confirmed_security_finding_count": int(aggregate.get("confirmed_security_finding_count", 0)),
            "recommended_batch_next_step": aggregate.get("recommended_batch_next_step", "unknown"),
        },
        "review_context_intake": {
            "boundary_context_present": bool(boundary_context.get("present", False)),
            "reviewer_observation_subject_count": len(observations_by_subject),
            "outcome_labels": [
                "more_context_needed",
                "reviewer_confidence_increased",
                "change_required_before_release",
                "block_should_be_considered_by_redthread",
                "not_enough_evidence_to_advance",
            ],
            "redthread_final_gate": True,
        },
        "review_workflow_artifacts": _review_workflow_inventory(batch_dir),
        "subjects": subjects,
        "privacy_attestation": _privacy_attestation(),
    }
    return context


def _privacy_attestation() -> dict[str, bool]:
    return {
        "sanitized_inputs_only": True,
        "raw_har_accessed_by_agent": False,
        "raw_urls_included": False,
        "raw_headers_included": False,
        "raw_cookies_included": False,
        "raw_bodies_included": False,
        "raw_ids_included": False,
        "secrets_included": False,
        "marker_audit_passed": True,
        "forbidden_key_audit_passed": True,
    }


def _workflow_class(subject: dict[str, Any]) -> str:
    if subject["write_surface_present"] and subject["auth_surface_present"]:
        return "mixed"
    if subject["write_surface_present"]:
        return "write_capable"
    if subject["auth_surface_present"]:
        return "auth_required"
    if not subject["boundary_evidence_present"]:
        return "boundary_relevant"
    if subject["fixture_count"] > 0:
        return "read_only"
    return "unknown"


def _relevance(present: bool, fallback: str = "none") -> str:
    return "high" if present else fallback


def _intent_label(subject: dict[str, Any], workflow_class: str) -> str:
    if workflow_class == "write_capable":
        return "content_management"
    if workflow_class == "auth_required":
        return "auth_session_management"
    if workflow_class == "mixed":
        return "account_management"
    if workflow_class == "read_only":
        return "search_or_discovery"
    return "unknown"


def _missing_evidence(subject: dict[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    boundary_context_present = bool(subject.get("boundary_context", {}).get("present", False))
    reviewer_observation_present = bool(subject.get("reviewer_observation", {}).get("present", False))
    for i, item in enumerate(subject.get("next_evidence_needed", []), start=1):
        text = str(item)
        if "boundary" in text:
            category = "missing_boundary_context"
            if boundary_context_present:
                continue
        elif "auth" in text:
            category = "missing_auth_context"
        elif "write" in text:
            category = "missing_write_context"
        elif "reviewer" in text or "observation" in text:
            category = "missing_reviewer_observation"
            if reviewer_observation_present:
                continue
        else:
            category = "unknown"
        gaps.append({
            "id": f"evidence_gap_{i:03d}",
            "category": category,
            "impact": "requires_review" if category == "missing_reviewer_observation" else "limits_confidence",
            "next_action": text,
        })
    if subject["batch_status"] != "processed":
        gaps.append({
            "id": f"evidence_gap_{len(gaps) + 1:03d}",
            "category": "privacy_blocked" if not subject["privacy_audit"]["passed"] else "unknown",
            "impact": "blocks_export",
            "next_action": "resolve_sanitized_batch_subject_status_before_export",
        })
    return gaps


def _review_outcome(subject: dict[str, Any], missing: list[dict[str, Any]], export_status: str) -> dict[str, Any]:
    categories = {gap["category"] for gap in missing}
    observation = subject.get("reviewer_observation", {})
    if export_status == "ready":
        label = "reviewer_confidence_increased" if observation.get("present") else "more_context_needed"
        next_action = "send_sanitized_packet_to_redthread_final_gate"
    elif "missing_boundary_context" in categories or "missing_reviewer_observation" in categories:
        label = "more_context_needed"
        next_action = "collect_sanitized_boundary_context_and_reviewer_observation"
    else:
        label = "not_enough_evidence_to_advance"
        next_action = "resolve_sanitized_evidence_gaps_before_redthread_evaluation"
    return {
        "label": label,
        "next_action": next_action,
        "redthread_final_gate_required": True,
        "not_a_confirmed_finding": True,
        "decision_support_only": True,
    }


def _local_model_observations(subject: dict[str, Any], missing: list[dict[str, Any]], boundary_proof_required: bool) -> dict[str, Any]:
    return {
        "useful_delta": False,
        "why_this_is_boundary_relevant": "not_provided_by_deterministic_review",
        "strongest_supporting_signal": "not_provided_by_deterministic_review",
        "remaining_uncertainty": "RedThread evaluation is required before any security conclusion.",
        "redthread_first_check": "not_provided_by_deterministic_review",
        "not_a_finding": True,
    }


def _review_subject(subject: dict[str, Any]) -> dict[str, Any]:
    workflow_class = _workflow_class(subject)
    missing = _missing_evidence(subject)
    approved_replay_required = subject["write_surface_present"] or subject["auth_surface_present"]
    boundary_proof_required = not subject["boundary_evidence_present"]
    export_status = "blocked" if subject["batch_status"] != "processed" else ("ready_with_gaps" if missing else "ready")
    outcome = _review_outcome(subject, missing, export_status)
    boundary_context = subject.get("boundary_context", {})
    reviewer_observation = subject.get("reviewer_observation", {})
    local_observations = _local_model_observations(subject, missing, boundary_proof_required)
    return {
        "subject_id": subject["subject_id"],
        "input_quality": {
            "status": "usable" if subject["batch_status"] == "processed" else "blocked",
            "blocker_categories": list(subject.get("primary_blocker_categories", [])),
            "evidence_gap_categories": [gap["category"] for gap in missing],
        },
        "review_support_outcome": outcome,
        "context_signals": {
            "boundary_context_present": bool(boundary_context.get("present", False)),
            "boundary_area": boundary_context.get("boundary_area", reviewer_observation.get("boundary_area", "unknown")),
            "reviewer_observation_present": bool(reviewer_observation.get("present", False)),
            "reviewer_selection_reason": reviewer_observation.get("selection_reason", "not_provided"),
            "reviewer_observed_behavior_summary": reviewer_observation.get("observed_behavior_summary", "not_provided"),
            "reviewer_uncertainty_remaining": reviewer_observation.get("uncertainty_remaining", "not_provided"),
        },
        "intent_hypotheses": [{
            "id": "intent_hypothesis_001",
            "label": reviewer_observation.get("likely_intent", _intent_label(subject, workflow_class)),
            "confidence": reviewer_observation.get("confidence", "medium" if subject["fixture_count"] else "low"),
            "basis": ["sanitized_workflow_summary", "sanitized_subject_summary"] + (["sanitized_reviewer_observation"] if reviewer_observation.get("present") else []) + (["sanitized_boundary_context"] if boundary_context.get("present") else []),
            "not_proven": True,
        }],
        "workflow_classification": {
            "workflow_class": workflow_class,
            "read_relevance": "medium" if subject["fixture_count"] else "none",
            "write_relevance": _relevance(subject["write_surface_present"]),
            "auth_relevance": _relevance(subject["auth_surface_present"]),
            "boundary_relevance": "low" if subject["boundary_evidence_present"] else "medium",
            "side_effect_risk": "possible" if subject["write_surface_present"] else "none",
        },
        "endpoint_role_categories": [{
            "role": "update" if subject["write_surface_present"] else "list_or_search",
            "method_class": "write_like" if subject["write_surface_present"] else "safe_read",
            "path_shape_label": "sanitized_template_only",
            "raw_url_present": False,
            "raw_app_value_present": False,
        }],
        "test_hypotheses": [{
            "id": "test_hypothesis_001",
            "type": "write_side_effect" if subject["write_surface_present"] else ("boundary_selector" if boundary_proof_required else "workflow_ordering"),
            "statement": "Sanitized hypothesis only; RedThread evaluation is required before any security conclusion.",
            "required_evidence": [gap["category"] for gap in missing],
            "requires_approved_execution": approved_replay_required,
            "requires_boundary_proof": boundary_proof_required,
            "redthread_candidate": export_status != "blocked",
            "not_proven": True,
        }],
        "missing_evidence": missing,
        "reviewer_questions": [{
            "id": "reviewer_question_001",
            "question": reviewer_observation.get("reviewer_question", "Does this sanitized workflow require approved non-production replay or boundary proof before RedThread evaluation?"),
            "answer_required_for": "approved_replay" if approved_replay_required else ("boundary_proof" if boundary_proof_required else "confidence"),
        }],
        "redthread_export_readiness": {
            "status": export_status,
            "ready_evidence_count": int(subject["fixture_count"]),
            "blocking_gap_count": sum(1 for gap in missing if gap["impact"] == "blocks_export"),
            "reason_categories": [gap["category"] for gap in missing],
        },
        "approved_execution_requirements": {
            "approved_replay_required": approved_replay_required,
            "boundary_proof_required": boundary_proof_required,
            "non_production_required": True,
            "explicit_approval_required": True,
            "default_live_execution_allowed": False,
        },
        "finding_semantics": {
            "confirmed_finding_claimed": False,
            "severity_claimed": False,
            "scanner_claimed": False,
        },
        "local_model_observations": local_observations,
    }


def build_intent_review(context: dict[str, Any]) -> dict[str, Any]:
    subjects = [_review_subject(subject) for subject in context.get("subjects", [])]
    return {
        "schema_version": REVIEW_SCHEMA_VERSION,
        "review_id": "intent_review_001",
        "source_batch": context["source_batch"],
        "privacy_attestation": context["privacy_attestation"],
        "subjects": subjects,
        "batch_summary": {
            "likely_workflow_classes": sorted({s["workflow_classification"]["workflow_class"] for s in subjects}),
            "common_gap_categories": sorted({gap["category"] for s in subjects for gap in s["missing_evidence"]}),
            "redthread_ready_subject_count": sum(1 for s in subjects if s["redthread_export_readiness"]["status"] == "ready"),
            "approved_replay_required_subject_count": sum(1 for s in subjects if s["approved_execution_requirements"]["approved_replay_required"]),
            "boundary_proof_required_subject_count": sum(1 for s in subjects if s["approved_execution_requirements"]["boundary_proof_required"]),
            "review_support_outcomes": sorted({s["review_support_outcome"]["label"] for s in subjects}),
            "subjects_with_boundary_context_count": sum(1 for s in subjects if s["context_signals"]["boundary_context_present"]),
            "subjects_with_reviewer_observation_count": sum(1 for s in subjects if s["context_signals"]["reviewer_observation_present"]),
        },
    }


def validate_intent_review_contract(review: dict[str, Any], export: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if review.get("schema_version") != REVIEW_SCHEMA_VERSION:
        errors.append("intent_review.schema_version")
    if export.get("schema_version") != EXPORT_SCHEMA_VERSION:
        errors.append("redthread_evidence_export.schema_version")
    for key in sorted(REVIEW_REQUIRED_KEYS - set(review)):
        errors.append(f"intent_review.missing.{key}")
    for key in sorted(EXPORT_REQUIRED_KEYS - set(export)):
        errors.append(f"redthread_evidence_export.missing.{key}")
    review_subject_ids = [str(subject.get("subject_id")) for subject in review.get("subjects", [])]
    export_subject_ids = [str(item.get("subject_id")) for item in export.get("workflow_evidence", [])]
    if sorted(review_subject_ids) != sorted(export_subject_ids):
        errors.append("subject_id_set_mismatch")
    promotion = export.get("promotion_semantics", {})
    if not promotion.get("redthread_evaluation_required"):
        errors.append("promotion_semantics.redthread_evaluation_required")
    forbidden_true_fields = [
        "adopt_redthread_final_decision_claimed",
        "confirmed_security_finding_claimed",
        "severity_claimed",
        "release_gate_override",
    ]
    for field in forbidden_true_fields:
        if promotion.get(field):
            errors.append(f"promotion_semantics.forbidden_true.{field}")
    for subject in review.get("subjects", []):
        finding = subject.get("finding_semantics", {})
        if finding.get("confirmed_finding_claimed") or finding.get("severity_claimed") or finding.get("scanner_claimed"):
            errors.append(f"subject.{subject.get('subject_id')}.finding_semantics")
        if subject.get("approved_execution_requirements", {}).get("default_live_execution_allowed"):
            errors.append(f"subject.{subject.get('subject_id')}.default_live_execution_allowed")
    return {
        "schema_version": "adopt_redthread.sanitized_intent_review_schema_validation.v0",
        "passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "validated_artifacts": ["intent_review.json", "redthread_evidence_export.json"],
        "redthread_evaluation_required": bool(promotion.get("redthread_evaluation_required")),
    }


def _advancement_state(subject: dict[str, Any]) -> str:
    categories = set(subject["redthread_export_readiness"].get("reason_categories", []))
    if subject["redthread_export_readiness"].get("status") == "ready":
        return "ready_for_redthread_evaluation"
    if "missing_boundary_context" in categories:
        return "needs_boundary_context"
    if "missing_reviewer_observation" in categories:
        return "needs_reviewer_observation"
    if subject["redthread_export_readiness"].get("status") == "blocked":
        return "blocked_by_sanitized_input_quality"
    return "not_enough_evidence_to_advance"


def build_advancement_summary(review: dict[str, Any]) -> dict[str, Any]:
    subjects = []
    for subject in review.get("subjects", []):
        blockers = list(subject["redthread_export_readiness"].get("reason_categories", []))
        state = _advancement_state(subject)
        subjects.append({
            "subject_id": subject["subject_id"],
            "advancement_state": state,
            "review_support_outcome": subject["review_support_outcome"],
            "blockers": blockers,
            "can_advance_to_redthread_evaluation": state == "ready_for_redthread_evaluation",
            "not_a_confirmed_finding": True,
            "redthread_final_gate_required": True,
            "next_action": subject["review_support_outcome"].get("next_action"),
            "explanation": "Ready for RedThread-owned evaluation." if state == "ready_for_redthread_evaluation" else f"Cannot advance yet because sanitized context still has: {', '.join(blockers) or 'unresolved evidence gaps'}.",
        })
    return {
        "schema_version": ADVANCEMENT_SCHEMA_VERSION,
        "summary": {
            "subject_count": len(subjects),
            "ready_for_redthread_evaluation_count": sum(1 for s in subjects if s["can_advance_to_redthread_evaluation"]),
            "needs_boundary_context_count": sum(1 for s in subjects if s["advancement_state"] == "needs_boundary_context"),
            "needs_reviewer_observation_count": sum(1 for s in subjects if "missing_reviewer_observation" in s["blockers"]),
            "confirmed_finding_claimed": False,
            "redthread_final_gate_required": True,
        },
        "subjects": subjects,
    }


def build_business_validation_plan(review: dict[str, Any], advancement: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": BUSINESS_VALIDATION_SCHEMA_VERSION,
        "objective": "prove_structured_context_changes_release_review_usefulness_without_changing_final_gate_ownership",
        "recommended_sample_size": 3,
        "candidate_subject_ids": [s["subject_id"] for s in advancement.get("subjects", []) if s.get("can_advance_to_redthread_evaluation")][:3],
        "decision_questions": [
            "Did reviewer confidence increase from the sanitized packet?",
            "Did the packet create a concrete change request?",
            "Did missing boundary context block advancement?",
            "Did the report reduce ambiguity compared with the baseline cautious review?",
            "Would the team want this before each release?",
        ],
        "metrics": {
            "clear_next_action_subject_count": len(advancement.get("subjects", [])),
            "ready_for_redthread_evaluation_count": advancement.get("summary", {}).get("ready_for_redthread_evaluation_count", 0),
            "needs_boundary_context_count": advancement.get("summary", {}).get("needs_boundary_context_count", 0),
            "needs_reviewer_observation_count": advancement.get("summary", {}).get("needs_reviewer_observation_count", 0),
        },
        "ownership": {
            "adopt_redthread": "sanitized evidence packaging, hypotheses, gaps, questions, and decision-support outcomes",
            "reviewers": "sanitized human confidence signals",
            "redthread": "final evaluation, confirmed findings, severity, promotion gates, and release decisions",
        },
        "forbidden_interpretations": [
            "confirmed finding",
            "severity rating",
            "scanner result",
            "live execution proof",
            "release override",
        ],
    }


def render_advancement_markdown(advancement: dict[str, Any]) -> str:
    lines = [
        "# Intent Review Advancement Summary",
        "",
        f"- Subjects: {advancement['summary']['subject_count']}",
        f"- Ready for RedThread evaluation: {advancement['summary']['ready_for_redthread_evaluation_count']}",
        f"- Need boundary context: {advancement['summary']['needs_boundary_context_count']}",
        f"- Need reviewer observation: {advancement['summary']['needs_reviewer_observation_count']}",
        "- Confirmed findings claimed: No",
        "- RedThread final gate required: Yes",
        "",
        "| Subject | State | Next action | Blockers |",
        "|---|---|---|---|",
    ]
    for s in advancement.get("subjects", []):
        lines.append(f"| `{s['subject_id']}` | `{s['advancement_state']}` | `{s['next_action']}` | `{', '.join(s['blockers']) or 'none'}` |")
    lines.append("")
    return "\n".join(lines)


def _subject_observations(subject: dict[str, Any]) -> list[dict[str, Any]]:
    subject_id = str(subject["subject_id"])
    observations = [
        {
            "observation_id": f"{subject_id}_obs_001",
            "type": "workflow_classification",
            "summary": f"Sanitized workflow classified as {subject['workflow_classification']['workflow_class']} with boundary relevance {subject['workflow_classification']['boundary_relevance']}.",
            "source_fields": ["workflow_classification.workflow_class", "workflow_classification.boundary_relevance"],
        },
        {
            "observation_id": f"{subject_id}_obs_002",
            "type": "operation_role_counts",
            "summary": f"Sanitized role categories include {len(subject.get('endpoint_role_categories', []))} operation role record(s).",
            "source_fields": ["endpoint_role_categories"],
        },
        {
            "observation_id": f"{subject_id}_obs_003",
            "type": "execution_requirement",
            "summary": f"Approved replay required is {subject['approved_execution_requirements']['approved_replay_required']}; boundary proof required is {subject['approved_execution_requirements']['boundary_proof_required']}.",
            "source_fields": ["approved_execution_requirements"],
        },
        {
            "observation_id": f"{subject_id}_obs_004",
            "type": "export_readiness",
            "summary": f"RedThread export readiness is {subject['redthread_export_readiness']['status']}.",
            "source_fields": ["redthread_export_readiness.status", "redthread_export_readiness.reason_categories"],
        },
    ]
    if subject.get("missing_evidence"):
        observations.append({
            "observation_id": f"{subject_id}_obs_005",
            "type": "missing_evidence",
            "summary": "Sanitized review identified missing context: " + ", ".join(gap["category"] for gap in subject["missing_evidence"]),
            "source_fields": ["missing_evidence"],
        })
    if subject.get("context_signals", {}).get("boundary_context_present"):
        observations.append({
            "observation_id": f"{subject_id}_obs_006",
            "type": "boundary_context",
            "summary": f"Sanitized boundary context is present for {subject['context_signals']['boundary_area']}.",
            "source_fields": ["context_signals.boundary_context_present", "context_signals.boundary_area"],
        })
    if subject.get("context_signals", {}).get("reviewer_observation_present"):
        observations.append({
            "observation_id": f"{subject_id}_obs_007",
            "type": "reviewer_observation",
            "summary": "Sanitized reviewer observation is present.",
            "source_fields": ["context_signals.reviewer_observation_present"],
        })
    return observations


def _execution_candidate(subject: dict[str, Any], observations: list[dict[str, Any]]) -> dict[str, Any]:
    subject_id = str(subject["subject_id"])
    missing_categories = [gap["category"] for gap in subject.get("missing_evidence", [])]
    approved = subject["approved_execution_requirements"]
    boundary_required = bool(approved["boundary_proof_required"])
    boundary_context_present = bool(subject["context_signals"]["boundary_context_present"])
    reviewer_observation_present = bool(subject["context_signals"]["reviewer_observation_present"])
    if boundary_required and not boundary_context_present:
        intent = "authorization_boundary_read_review"
        strength = "partial"
        readiness = "needs_context"
        action = "collect_boundary_context"
        summary = "This appears to be a boundary-relevant workflow with insufficient sanitized boundary context for RedThread execution planning."
    elif boundary_required and boundary_context_present:
        intent = "authorization_boundary_review_candidate"
        strength = "medium" if reviewer_observation_present else "partial"
        readiness = "ready_for_redthread_review"
        action = "evaluate_sanitized_export"
        summary = "This is a boundary-relevant workflow candidate with sanitized boundary context ready for RedThread-owned evaluation."
    elif approved["approved_replay_required"]:
        intent = "reviewed_replay_candidate"
        strength = "partial"
        readiness = "needs_approval"
        action = "prepare_reviewed_replay_plan"
        summary = "This sanitized workflow may require approved non-production replay planning before RedThread evaluation."
    else:
        intent = "workflow_triage_candidate"
        strength = "low" if missing_categories else "partial"
        readiness = "needs_context" if missing_categories else "ready_for_redthread_review"
        action = "collect_reviewer_observation" if missing_categories else "redthread_triage"
        summary = "This sanitized workflow is suitable for RedThread triage, with any missing context resolved before execution."
    return {
        "candidate_id": f"{subject_id}_candidate_001",
        "subject_id": subject_id,
        "rank": 1,
        "candidate_workflow_intent": intent,
        "evidence_strength": strength,
        "execution_readiness": readiness,
        "recommended_redthread_action": action,
        "operator_summary": summary,
        "supporting_sanitized_observations": observations,
        "missing_context": [
            {"category": gap["category"], "next_action": gap["next_action"], "source_gap_id": gap["id"]}
            for gap in subject.get("missing_evidence", [])
        ],
        "execution_constraints": {
            "live_execution_allowed": False,
            "approved_context_required": True,
            "redthread_final_gate_required": True,
        },
        "redthread_decides": [
            "whether sanitized context is sufficient",
            "whether replay is approved",
            "whether any finding exists",
        ],
        "forbidden_interpretation": [
            "not a finding",
            "not severity",
            "not exploit proof",
            "not release approval",
        ],
    }


def build_redthread_execution_handoff(review: dict[str, Any]) -> dict[str, Any]:
    candidates = [_execution_candidate(subject, _subject_observations(subject)) for subject in review.get("subjects", [])]
    return {
        "schema_version": EXECUTION_HANDOFF_SCHEMA_VERSION,
        "source": {
            "artifact_family": "sanitized_intent_review",
            "raw_artifacts_included": False,
            "source_review_id": review.get("review_id"),
        },
        "summary": {
            "candidate_count": len(candidates),
            "ready_for_redthread_review_count": sum(1 for c in candidates if c["execution_readiness"] == "ready_for_redthread_review"),
            "needs_context_count": sum(1 for c in candidates if c["execution_readiness"] == "needs_context"),
            "live_execution_allowed": False,
            "redthread_final_gate_required": True,
        },
        "execution_candidates": candidates,
    }


def _candidate_text_forbidden_scan(candidate: dict[str, Any]) -> str:
    scan_payload = {
        key: value
        for key, value in candidate.items()
        if key not in {"forbidden_interpretation", "redthread_decides"}
    }
    return json.dumps(scan_payload, sort_keys=True).casefold()


def validate_execution_handoff(handoff: dict[str, Any], review: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if handoff.get("schema_version") != EXECUTION_HANDOFF_SCHEMA_VERSION:
        errors.append("redthread_execution_handoff.schema_version")
    if handoff.get("source", {}).get("raw_artifacts_included"):
        errors.append("redthread_execution_handoff.source.raw_artifacts_included")
    summary = handoff.get("summary", {})
    if summary.get("live_execution_allowed"):
        errors.append("redthread_execution_handoff.summary.live_execution_allowed")
    if not summary.get("redthread_final_gate_required"):
        errors.append("redthread_execution_handoff.summary.redthread_final_gate_required")
    subject_ids = {str(subject.get("subject_id")) for subject in review.get("subjects", [])}
    candidate_ids: set[str] = set()
    for candidate in handoff.get("execution_candidates", []):
        candidate_id = str(candidate.get("candidate_id", "unknown_candidate"))
        if candidate_id in candidate_ids:
            errors.append(f"candidate.{candidate_id}.duplicate_candidate_id")
        candidate_ids.add(candidate_id)
        missing_keys = HANDOFF_REQUIRED_CANDIDATE_KEYS - set(candidate)
        for key in sorted(missing_keys):
            errors.append(f"candidate.{candidate_id}.missing.{key}")
        if str(candidate.get("subject_id")) not in subject_ids:
            errors.append(f"candidate.{candidate_id}.subject_id")
        constraints = candidate.get("execution_constraints", {})
        if constraints.get("live_execution_allowed"):
            errors.append(f"candidate.{candidate_id}.live_execution_allowed")
        if not constraints.get("redthread_final_gate_required"):
            errors.append(f"candidate.{candidate_id}.redthread_final_gate_required")
        if not constraints.get("approved_context_required"):
            errors.append(f"candidate.{candidate_id}.approved_context_required")
        if candidate.get("recommended_redthread_action") not in HANDOFF_RECOMMENDED_ACTIONS:
            errors.append(f"candidate.{candidate_id}.recommended_redthread_action")
        if not candidate.get("supporting_sanitized_observations"):
            errors.append(f"candidate.{candidate_id}.supporting_sanitized_observations")
        for obs in candidate.get("supporting_sanitized_observations", []):
            if not obs.get("observation_id"):
                errors.append(f"candidate.{candidate_id}.observation_id")
        lower = _candidate_text_forbidden_scan(candidate)
        for phrase in HANDOFF_FORBIDDEN_LANGUAGE:
            if phrase in lower:
                errors.append(f"candidate.{candidate_id}.forbidden_language.{phrase.replace(' ', '_')}")
    audit = marker_audit(json.dumps(handoff, sort_keys=True))
    if not audit.get("passed"):
        errors.append("redthread_execution_handoff.privacy_audit")
    return {
        "schema_version": "adopt_redthread.execution_handoff_validation.v0",
        "passed": not errors,
        "error_count": len(errors),
        "errors": errors,
        "candidate_count": len(handoff.get("execution_candidates", [])),
        "privacy_audit_passed": bool(audit.get("passed")),
        "raw_field_hit_count": int(audit.get("raw_field_hit_count", 0)),
        "marker_hit_count": int(audit.get("marker_hit_count", 0)),
        "allowed_recommended_actions": sorted(HANDOFF_RECOMMENDED_ACTIONS),
        "validated_rules": [
            "schema_version",
            "summary_safety_flags",
            "subject_id_set",
            "candidate_required_keys",
            "recommended_action_enum",
            "observation_citations_required",
            "execution_constraints",
            "forbidden_language",
            "privacy_marker_audit",
        ],
    }


def render_execution_handoff_markdown(handoff: dict[str, Any]) -> str:
    summary = handoff["summary"]
    lines = [
        "# RedThread Execution Handoff",
        "",
        "## Summary",
        f"- Candidates: {summary['candidate_count']}",
        f"- Ready for RedThread review: {summary['ready_for_redthread_review_count']}",
        f"- Need context: {summary['needs_context_count']}",
        "- Live execution allowed: No",
        "- RedThread final gate required: Yes",
        "",
    ]
    for candidate in handoff.get("execution_candidates", []):
        lines.extend([
            f"## Candidate {candidate['rank']} — {candidate['subject_id']}",
            "",
            "### Operator summary",
            candidate["operator_summary"],
            "",
            "### Recommended RedThread action",
            candidate["recommended_redthread_action"],
            "",
            "### Why",
        ])
        for observation in candidate.get("supporting_sanitized_observations", []):
            lines.append(f"- `{observation['observation_id']}`: {observation['summary']}")
        lines.extend(["", "### Missing context"])
        if candidate.get("missing_context"):
            for gap in candidate["missing_context"]:
                lines.append(f"- `{gap['category']}`: {gap['next_action']}")
        else:
            lines.append("- none")
        lines.extend(["", "### RedThread decides"])
        for item in candidate.get("redthread_decides", []):
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines)


def _intent_evidence_strength(candidate: dict[str, Any]) -> str:
    return {
        "low": "weak",
        "partial": "weak",
        "medium": "moderate",
        "high": "strong",
    }.get(str(candidate.get("evidence_strength", "weak")), "weak")


def _intent_evidence_items(candidate: dict[str, Any], package_rank: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, observation in enumerate(candidate.get("supporting_sanitized_observations", []), start=1):
        items.append({
            "id": f"ev_{package_rank:03d}_{index:03d}",
            "source_observation_id": observation.get("observation_id"),
            "subject_id": candidate.get("subject_id"),
            "type": "behavioral_signal",
            "strength": _intent_evidence_strength(candidate),
            "summary": observation.get("summary", "sanitized observation available"),
            "supports": [f"step_{package_rank:03d}_001"],
            "limitations": [
                "sanitized observation only",
                "RedThread JudgeAgent must evaluate before any finding",
            ] + [gap.get("category", "missing_context") for gap in candidate.get("missing_context", [])],
        })
    return items


def _intent_attack_step(candidate: dict[str, Any], package_rank: int) -> dict[str, Any]:
    action = "evaluate sanitized workflow evidence inside RedThread before any replay planning"
    if candidate.get("recommended_redthread_action") == "collect_boundary_context":
        action = "collect approved boundary context before RedThread-owned authorization-boundary evaluation"
    elif candidate.get("recommended_redthread_action") == "collect_reviewer_observation":
        action = "collect reviewer observation summary before RedThread-owned evaluation"
    elif candidate.get("recommended_redthread_action") == "evaluate_sanitized_export":
        action = "evaluate authorization-boundary read behavior using RedThread-controlled replay planning after approved context is supplied"
    elif candidate.get("recommended_redthread_action") == "prepare_reviewed_replay_plan":
        action = "prepare a RedThread-reviewed replay plan without authorizing live execution"
    return {
        "id": f"step_{package_rank:03d}_001",
        "subject_id": candidate.get("subject_id"),
        "action": action,
        "expected_signal": "RedThread determines whether the sanitized workflow evidence is meaningful enough for JudgeAgent evaluation",
        "success_condition": "JudgeAgent completes final evaluation; adopt-redthread makes no finding claim",
        "requires_raw_payload": False,
        "requires_live_execution": False,
        "supporting_evidence_ids": [item["id"] for item in _intent_evidence_items(candidate, package_rank)],
        "redthread_decides": candidate.get("redthread_decides", []),
    }


def build_redthread_intent_evidence(review: dict[str, Any], handoff: dict[str, Any]) -> dict[str, Any]:
    candidates = handoff.get("execution_candidates", [])
    evidence = [item for package_rank, candidate in enumerate(candidates, start=1) for item in _intent_evidence_items(candidate, package_rank)]
    steps = [_intent_attack_step(candidate, package_rank) for package_rank, candidate in enumerate(candidates, start=1)]
    needs_context = any(candidate.get("execution_readiness") != "ready_for_redthread_review" for candidate in candidates)
    return {
        "schema_version": INTENT_EVIDENCE_SCHEMA_VERSION,
        "source": {
            "tool": "adopt-redthread",
            "input_type": "sanitized_intent_review",
            "source_review_id": review.get("review_id"),
            "source_handoff_schema_version": handoff.get("schema_version"),
            "raw_artifacts_included": False,
        },
        "privacy": {
            "sanitized": True,
            "raw_har_included": False,
            "raw_urls_included": False,
            "raw_headers_included": False,
            "raw_cookies_included": False,
            "raw_bodies_included": False,
            "raw_payloads_included": False,
            "secrets_included": False,
        },
        "intent": {
            "target_behavior": candidates[0].get("candidate_workflow_intent", "redthread_sanitized_evidence_review") if candidates else "redthread_sanitized_evidence_review",
            "risk_hypothesis": "hypothesis_only",
            "authority_boundary": "unknown_or_sanitized_boundary_area" if needs_context else "sanitized_boundary_context_supplied",
            "not_a_finding": True,
        },
        "evidence": evidence,
        "attack_plan": {
            "objective": "prepare_redthread_owned_boundary_evaluation",
            "steps": steps,
            "payloads_included": False,
            "live_execution_allowed": False,
        },
        "redthread_import": {
            "recommended_workflow_type": "attack_judge_defend_validate",
            "requires_human_review": True,
            "judge_agent_required": True,
            "eligible_for_regression": False,
            "candidate_workflow_count": len(steps),
            "import_as": "candidate_evidence_not_finding",
        },
        "forbidden_interpretation": [
            "not a finding",
            "not severity",
            "not exploit proof",
            "not release approval",
            "not live execution authorization",
        ],
    }


def validate_redthread_intent_evidence(package: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if package.get("schema_version") != INTENT_EVIDENCE_SCHEMA_VERSION:
        errors.append("redthread_intent_evidence.schema_version")
    if package.get("source", {}).get("raw_artifacts_included"):
        errors.append("source.raw_artifacts_included")
    privacy = package.get("privacy", {})
    if not privacy.get("sanitized"):
        errors.append("privacy.sanitized")
    for flag in sorted(INTENT_EVIDENCE_REQUIRED_PRIVACY_FALSE_FLAGS):
        if privacy.get(flag):
            errors.append(f"privacy.{flag}")
    intent = package.get("intent", {})
    if not intent.get("authority_boundary"):
        errors.append("intent.authority_boundary")
    if not intent.get("not_a_finding"):
        errors.append("intent.not_a_finding")
    evidence_ids: set[str] = set()
    for item in package.get("evidence", []):
        item_id = str(item.get("id", "unknown_evidence"))
        if item_id in evidence_ids:
            errors.append(f"evidence.{item_id}.duplicate_id")
        evidence_ids.add(item_id)
        if not item.get("source_observation_id"):
            errors.append(f"evidence.{item_id}.source_observation_id")
        if item.get("strength") not in {"weak", "moderate", "strong"}:
            errors.append(f"evidence.{item_id}.strength")
        if not item.get("limitations"):
            errors.append(f"evidence.{item_id}.limitations")
    import_block = package.get("redthread_import", {})
    if not import_block.get("judge_agent_required"):
        errors.append("redthread_import.judge_agent_required")
    if import_block.get("eligible_for_regression"):
        errors.append("redthread_import.eligible_for_regression")
    if import_block.get("import_as") != "candidate_evidence_not_finding":
        errors.append("redthread_import.import_as")
    attack_plan = package.get("attack_plan", {})
    if attack_plan.get("live_execution_allowed"):
        errors.append("attack_plan.live_execution_allowed")
    if attack_plan.get("payloads_included"):
        errors.append("attack_plan.payloads_included")
    for step in attack_plan.get("steps", []):
        step_id = str(step.get("id", "unknown_step"))
        if not step.get("expected_signal"):
            errors.append(f"attack_plan.{step_id}.expected_signal")
        if not step.get("success_condition"):
            errors.append(f"attack_plan.{step_id}.success_condition")
        if step.get("requires_raw_payload"):
            errors.append(f"attack_plan.{step_id}.requires_raw_payload")
        if step.get("requires_live_execution"):
            errors.append(f"attack_plan.{step_id}.requires_live_execution")
        if not step.get("supporting_evidence_ids"):
            errors.append(f"attack_plan.{step_id}.supporting_evidence_ids")
        for evidence_id in step.get("supporting_evidence_ids", []):
            if evidence_id not in evidence_ids:
                errors.append(f"attack_plan.{step_id}.unknown_evidence_id.{evidence_id}")
    scan_payload = {
        key: value
        for key, value in package.items()
        if key != "forbidden_interpretation"
    }
    lower = json.dumps(scan_payload, sort_keys=True).casefold()
    for phrase in INTENT_EVIDENCE_FORBIDDEN_LANGUAGE:
        if phrase in lower:
            errors.append(f"forbidden_language.{phrase.replace(' ', '_')}")
    audit = marker_audit(json.dumps(package, sort_keys=True))
    if not audit.get("passed"):
        errors.append("privacy_marker_audit")
    importable = not errors
    execution_ready = importable and bool(package.get("attack_plan", {}).get("steps"))
    if not package.get("evidence"):
        warnings.append("no_evidence_items")
    return {
        "schema_version": INTENT_EVIDENCE_VALIDATION_SCHEMA_VERSION,
        "valid": importable,
        "importable": importable,
        "privacy_safe": bool(audit.get("passed")) and not any(privacy.get(flag) for flag in INTENT_EVIDENCE_REQUIRED_PRIVACY_FALSE_FLAGS),
        "execution_ready": execution_ready,
        "finding_claim_detected": any(error.startswith("forbidden_language") for error in errors),
        "regression_ready": False,
        "judge_agent_required": bool(import_block.get("judge_agent_required")),
        "candidate_workflow_created": bool(package.get("attack_plan", {}).get("steps")),
        "blocked_reason": None if importable else errors[0],
        "error_count": len(errors),
        "errors": errors,
        "warnings": warnings,
        "raw_field_hit_count": int(audit.get("raw_field_hit_count", 0)),
        "marker_hit_count": int(audit.get("marker_hit_count", 0)),
    }


def build_redthread_importability_report(package: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": IMPORTABILITY_REPORT_SCHEMA_VERSION,
        "source_schema_version": package.get("schema_version"),
        "importable": bool(validation.get("importable")),
        "privacy_safe": bool(validation.get("privacy_safe")),
        "execution_ready": bool(validation.get("execution_ready")),
        "judge_required": bool(validation.get("judge_agent_required")),
        "candidate_workflow_created": bool(validation.get("candidate_workflow_created")),
        "blocked_reason": validation.get("blocked_reason"),
        "redthread_consumption_contract": {
            "import_as": package.get("redthread_import", {}).get("import_as"),
            "recommended_workflow_type": package.get("redthread_import", {}).get("recommended_workflow_type"),
            "redthread_owns_execution": True,
            "redthread_owns_findings": True,
            "judge_agent_required": True,
        },
        "metrics": {
            "evidence_count": len(package.get("evidence", [])),
            "attack_step_count": len(package.get("attack_plan", {}).get("steps", [])),
            "validation_error_count": int(validation.get("error_count", 0)),
        },
    }


def render_redthread_intent_evidence_markdown(package: dict[str, Any], validation: dict[str, Any], report: dict[str, Any]) -> str:
    lines = [
        "# RedThread Intent Evidence Package",
        "",
        "## Importability",
        f"- Importable: {report['importable']}",
        f"- Privacy safe: {report['privacy_safe']}",
        f"- Execution ready: {report['execution_ready']}",
        f"- JudgeAgent required: {report['judge_required']}",
        f"- Candidate workflow created: {report['candidate_workflow_created']}",
        f"- Blocked reason: {report['blocked_reason'] or 'none'}",
        "",
        "## Intent",
        f"- Target behavior: `{package['intent']['target_behavior']}`",
        f"- Risk hypothesis: `{package['intent']['risk_hypothesis']}`",
        f"- Authority boundary: `{package['intent']['authority_boundary']}`",
        "- Finding claimed: No",
        "- Severity claimed: No",
        "- Live execution authorized: No",
        "",
        "## Evidence",
    ]
    for item in package.get("evidence", []):
        lines.append(f"- `{item['id']}` from `{item['source_observation_id']}` ({item['strength']}): {item['summary']}")
        lines.append(f"  - Limitations: {', '.join(item.get('limitations', []))}")
    lines.extend(["", "## RedThread attack-plan candidates"])
    for step in package.get("attack_plan", {}).get("steps", []):
        lines.append(f"- `{step['id']}`: {step['action']}")
        lines.append(f"  - Expected signal: {step['expected_signal']}")
        lines.append(f"  - Success condition: {step['success_condition']}")
        lines.append(f"  - Supporting evidence: {', '.join(step.get('supporting_evidence_ids', []))}")
    lines.extend(["", "## Validation", f"- Passed: {validation['valid']}", f"- Errors: {validation['error_count']}"])
    return "\n".join(lines) + "\n"


def render_importability_report_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# RedThread Importability Report",
        "",
        f"- Importable: {report['importable']}",
        f"- Privacy safe: {report['privacy_safe']}",
        f"- Execution ready: {report['execution_ready']}",
        f"- Judge required: {report['judge_required']}",
        f"- Candidate workflow created: {report['candidate_workflow_created']}",
        f"- Blocked reason: {report['blocked_reason'] or 'none'}",
        f"- Evidence count: {report['metrics']['evidence_count']}",
        f"- Attack step count: {report['metrics']['attack_step_count']}",
        "",
    ])


def build_redthread_candidate_workflow_import(package: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    importable = bool(validation.get("importable"))
    workflows = []
    for index, step in enumerate(package.get("attack_plan", {}).get("steps", []), start=1):
        workflows.append({
            "workflow_id": f"candidate_workflow_{index:03d}",
            "source_step_id": step.get("id"),
            "subject_id": step.get("subject_id"),
            "status": "candidate_created" if importable else "blocked",
            "workflow_type": package.get("redthread_import", {}).get("recommended_workflow_type"),
            "import_as": "candidate_evidence_not_finding",
            "source_evidence_ids": step.get("supporting_evidence_ids", []),
            "expected_signal": step.get("expected_signal"),
            "success_condition": step.get("success_condition"),
            "requires_human_review": True,
            "judge_agent_required": True,
            "live_execution_allowed": False,
            "finding_created": False,
            "severity_assigned": False,
            "regression_promoted": False,
            "blocked_reason": None if importable else validation.get("blocked_reason"),
        })
    return {
        "schema_version": CANDIDATE_WORKFLOW_IMPORT_SCHEMA_VERSION,
        "source_schema_version": package.get("schema_version"),
        "import_status": "imported_as_candidate_workflows" if importable and workflows else "blocked",
        "candidate_workflow_count": len(workflows) if importable else 0,
        "blocked_reason": None if importable else validation.get("blocked_reason"),
        "redthread_ownership": {
            "execution": True,
            "judgment": True,
            "findings": True,
            "severity": True,
            "regression_promotion": True,
        },
        "adopt_redthread_claims": {
            "finding_created": False,
            "severity_assigned": False,
            "live_execution_authorized": False,
            "regression_promoted": False,
        },
        "candidate_workflows": workflows if importable else [],
    }


def build_product_proof_report(
    package: dict[str, Any],
    validation: dict[str, Any],
    importability: dict[str, Any],
    workflow_import: dict[str, Any],
) -> dict[str, Any]:
    metrics = {
        "importable": bool(importability.get("importable")),
        "privacy_safe": bool(importability.get("privacy_safe")),
        "execution_ready": bool(importability.get("execution_ready")),
        "judge_required": bool(importability.get("judge_required")),
        "candidate_workflow_created": bool(workflow_import.get("candidate_workflow_count", 0)),
        "evidence_count": len(package.get("evidence", [])),
        "attack_step_count": len(package.get("attack_plan", {}).get("steps", [])),
        "validation_error_count": int(validation.get("error_count", 0)),
        "raw_field_hit_count": int(validation.get("raw_field_hit_count", 0)),
        "marker_hit_count": int(validation.get("marker_hit_count", 0)),
        "finding_claimed": False,
        "severity_claimed": False,
        "live_execution_authorized": False,
    }
    passed = all([
        metrics["importable"],
        metrics["privacy_safe"],
        metrics["execution_ready"],
        metrics["judge_required"],
        metrics["candidate_workflow_created"],
        metrics["evidence_count"] > 0,
        metrics["attack_step_count"] > 0,
        metrics["validation_error_count"] == 0,
        metrics["raw_field_hit_count"] == 0,
        metrics["marker_hit_count"] == 0,
        not metrics["finding_claimed"],
        not metrics["severity_claimed"],
        not metrics["live_execution_authorized"],
    ])
    return {
        "schema_version": PRODUCT_PROOF_SCHEMA_VERSION,
        "passed": passed,
        "status": "redthread_import_contract_proven" if passed else "blocked_before_redthread_import",
        "metrics": metrics,
        "success_criteria": [
            "privacy_safe_importable_evidence_package",
            "candidate_workflow_created_without_finding",
            "sanitized_evidence_citations_preserved",
            "judge_agent_required",
            "no_live_execution_authorization",
        ],
        "blocked_reason": None if passed else importability.get("blocked_reason") or validation.get("blocked_reason"),
    }


def render_candidate_workflow_import_markdown(workflow_import: dict[str, Any]) -> str:
    lines = [
        "# RedThread Candidate Workflow Import",
        "",
        f"- Import status: {workflow_import['import_status']}",
        f"- Candidate workflows: {workflow_import['candidate_workflow_count']}",
        f"- Blocked reason: {workflow_import['blocked_reason'] or 'none'}",
        "- Imported as findings: No",
        "- Severity assigned: No",
        "- Live execution authorized: No",
        "",
    ]
    for workflow in workflow_import.get("candidate_workflows", []):
        lines.extend([
            f"## {workflow['workflow_id']}",
            f"- Source step: `{workflow['source_step_id']}`",
            f"- Subject: `{workflow['subject_id']}`",
            f"- Workflow type: `{workflow['workflow_type']}`",
            f"- Source evidence: {', '.join(workflow.get('source_evidence_ids', []))}",
            f"- Expected signal: {workflow['expected_signal']}",
            f"- Success condition: {workflow['success_condition']}",
            "- JudgeAgent required: Yes",
            "",
        ])
    return "\n".join(lines)


def render_operator_handoff_markdown(
    package: dict[str, Any],
    importability: dict[str, Any],
    workflow_import: dict[str, Any],
    proof: dict[str, Any],
) -> str:
    first_step = (package.get("attack_plan", {}).get("steps") or [{}])[0]
    evidence_ids = [item.get("id") for item in package.get("evidence", [])]
    return "\n".join([
        "# RedThread Operator Handoff",
        "",
        "## 1. What should RedThread try next?",
        first_step.get("action", "No candidate workflow available."),
        "",
        "## 2. Why?",
        f"The sanitized package is importable={importability['importable']}, privacy_safe={importability['privacy_safe']}, and candidate_workflow_created={workflow_import.get('candidate_workflow_count', 0) > 0}.",
        "",
        "## 3. What evidence supports it?",
        ", ".join(evidence_ids) if evidence_ids else "No sanitized evidence items available.",
        "",
        "## 4. What context or approval is missing?",
        package.get("intent", {}).get("authority_boundary", "unknown_or_sanitized_boundary_area"),
        "",
        "## 5. What is explicitly not claimed?",
        "No finding, severity, exploit proof, release approval, regression promotion, or live execution authorization is claimed by adopt-redthread.",
        "",
        "## Product proof",
        f"- Passed: {proof['passed']}",
        f"- Status: {proof['status']}",
        "",
    ])


def render_product_proof_markdown(proof: dict[str, Any]) -> str:
    lines = ["# RedThread Intent Evidence Product Proof", "", f"- Passed: {proof['passed']}", f"- Status: {proof['status']}", f"- Blocked reason: {proof['blocked_reason'] or 'none'}", "", "## Metrics"]
    for key, value in proof.get("metrics", {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def build_redthread_evidence_export(review: dict[str, Any]) -> dict[str, Any]:
    subjects = review.get("subjects", [])
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "export_id": "redthread_export_001",
        "source": {
            "adapter": "adopt-redthread",
            "source_artifact_family": "offline_har_evidence_batch",
            "sanitized_only": True,
        },
        "evidence_envelope": {
            "subject_count": len(subjects),
            "workflow_count": len(subjects),
            "operation_count": sum(s["redthread_export_readiness"]["ready_evidence_count"] for s in subjects),
            "artifact_manifest": [
                {"artifact_name": "workflow_summary.json", "artifact_role": "sanitized_workflow_summary", "raw_source_included": False},
                {"artifact_name": "subject_summary.json", "artifact_role": "sanitized_subject_summary", "raw_source_included": False},
                {"artifact_name": "intent_review.json", "artifact_role": "sanitized_intent_review", "raw_source_included": False},
            ],
        },
        "workflow_evidence": [
            {
                "subject_id": s["subject_id"],
                "workflow_class": s["workflow_classification"]["workflow_class"],
                "operation_role_counts": {
                    "safe_read": sum(1 for r in s["endpoint_role_categories"] if r["method_class"] == "safe_read"),
                    "write_like": sum(1 for r in s["endpoint_role_categories"] if r["method_class"] == "write_like"),
                    "auth_like": sum(1 for r in s["endpoint_role_categories"] if r["method_class"] == "auth_like"),
                    "boundary_relevant": 1 if s["approved_execution_requirements"]["boundary_proof_required"] else 0,
                    "unknown": 0,
                },
                "ordered_operation_roles": [
                    {
                        "sequence": i + 1,
                        "operation_ref": f"{s['subject_id']}_operation_{i + 1:03d}",
                        "role": role["role"],
                        "method_class": role["method_class"],
                        "raw_url_present": False,
                    }
                    for i, role in enumerate(s["endpoint_role_categories"])
                ],
                "response_binding_summary": {
                    "binding_evidence_present": False,
                    "binding_gap_categories": [gap["category"] for gap in s["missing_evidence"] if "binding" in gap["category"]],
                },
            }
            for s in subjects
        ],
        "intent_context": [
            {
                "subject_id": s["subject_id"],
                "intent_hypotheses": s["intent_hypotheses"],
                "test_hypotheses": s["test_hypotheses"],
                "review_support_outcome": s["review_support_outcome"],
                "context_signals": s["context_signals"],
                "local_model_observations": s.get("local_model_observations", {}),
                "reviewer_questions": s["reviewer_questions"],
                "missing_evidence": s["missing_evidence"],
            }
            for s in subjects
        ],
        "execution_handoff": {
            "artifact_name": "redthread_execution_handoff.json",
            "schema_version": EXECUTION_HANDOFF_SCHEMA_VERSION,
            "candidate_count": len(subjects),
            "redthread_final_gate_required": True,
            "live_execution_allowed": False,
            "raw_artifacts_included": False,
            "status": "deterministic_handoff_generated_after_review_validation",
        },
        "intent_evidence_package": {
            "artifact_name": "redthread_intent_evidence.json",
            "schema_version": INTENT_EVIDENCE_SCHEMA_VERSION,
            "validation_artifact_name": "redthread_intent_evidence_validation.json",
            "importability_report_artifact_name": "redthread_importability_report.json",
            "redthread_import_contract": "candidate_evidence_not_finding",
            "judge_agent_required": True,
            "live_execution_allowed": False,
            "raw_artifacts_included": False,
        },
        "execution_requirements": [
            {
                "subject_id": s["subject_id"],
                "approved_replay_required": s["approved_execution_requirements"]["approved_replay_required"],
                "boundary_proof_required": s["approved_execution_requirements"]["boundary_proof_required"],
                "approved_non_production_context_required": True,
                "live_execution_performed": False,
            }
            for s in subjects
        ],
        "promotion_semantics": {
            "adopt_redthread_final_decision_claimed": False,
            "redthread_evaluation_required": True,
            "confirmed_security_finding_claimed": False,
            "severity_claimed": False,
            "release_gate_override": False,
        },
        "privacy_attestation": {
            "sanitized_only": True,
            "raw_har_included": False,
            "raw_urls_included": False,
            "raw_headers_included": False,
            "raw_cookies_included": False,
            "raw_bodies_included": False,
            "raw_ids_included": False,
            "secrets_included": False,
        },
    }


def build_redthread_contract_preview(export: dict[str, Any]) -> dict[str, Any]:
    promotion = export.get("promotion_semantics", {})
    envelope = export.get("evidence_envelope", {})
    workflow_evidence = export.get("workflow_evidence", [])
    execution_requirements = export.get("execution_requirements", [])
    intent_context = export.get("intent_context", [])
    return {
        "schema_version": CONTRACT_PREVIEW_SCHEMA_VERSION,
        "status": "proposal_preview_not_upstreamed",
        "evidence_envelope": {
            "schema_version": CONTRACT_PREVIEW_SCHEMA_VERSION,
            "run_id": export.get("export_id"),
            "input_family": export.get("source", {}).get("source_artifact_family"),
            "operation_count": envelope.get("operation_count", 0),
            "workflow_count": envelope.get("workflow_count", 0),
            "artifact_manifest": envelope.get("artifact_manifest", []),
        },
        "workflow_evidence": {
            "ordered_operations": [op for workflow in workflow_evidence for op in workflow.get("ordered_operation_roles", [])],
            "workflow_classes": sorted({workflow.get("workflow_class", "unknown") for workflow in workflow_evidence}),
            "successful_workflow_count": 0,
            "blocked_workflow_count": sum(1 for req in execution_requirements if req.get("approved_replay_required") or req.get("boundary_proof_required")),
            "response_binding_summary": [workflow.get("response_binding_summary", {}) for workflow in workflow_evidence],
        },
        "attack_context_summary": {
            "tool_action_schemas": [],
            "action_class_counts": {},
            "targeted_missing_context_questions": [question for item in intent_context for question in item.get("reviewer_questions", [])],
        },
        "replay_and_auth_diagnostics": {
            "replay_passed": False,
            "dry_run_executed": False,
            "approved_auth_context_required": any(req.get("approved_replay_required") for req in execution_requirements),
            "approved_write_context_required": any(req.get("approved_replay_required") for req in execution_requirements),
            "replay_failure_category": "not_executed_by_intent_review_agent",
        },
        "promotion_recommendation": {
            "recommendation": "review",
            "decision_reason_category": "redthread_evaluation_required",
            "confirmed_security_finding": False,
            "coverage_label": "sanitized_intent_hypotheses_only",
            "coverage_gaps": [gap for item in intent_context for gap in item.get("missing_evidence", [])],
            "trusted_evidence": False,
            "not_proven": True,
            "redthread_evaluation_required": bool(promotion.get("redthread_evaluation_required")),
        },
        "next_evidence_guidance": {
            "top_targeted_probe": "redthread_review_of_sanitized_export",
            "next_evidence_needed": [gap.get("next_action") for item in intent_context for gap in item.get("missing_evidence", [])],
            "rerun_triggers": ["approved_context_added", "reviewer_observation_summary_added"],
            "reviewer_action": "evaluate_sanitized_export_in_redthread_owned_gate",
        },
        "privacy_attestation": export.get("privacy_attestation", {}),
    }


def render_intent_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Sanitized Intent Review",
        "",
        "## Summary",
        f"- Subjects reviewed: {len(review.get('subjects', []))}",
        f"- RedThread-ready subjects: {review['batch_summary']['redthread_ready_subject_count']}",
        f"- Subjects with boundary context: {review['batch_summary'].get('subjects_with_boundary_context_count', 0)}",
        f"- Subjects with reviewer observations: {review['batch_summary'].get('subjects_with_reviewer_observation_count', 0)}",
        "- Confirmed findings claimed: No",
        "- Live execution performed: No",
        "",
        "## Subject reviews",
    ]
    for subject in review.get("subjects", []):
        intent = subject["intent_hypotheses"][0]
        workflow = subject["workflow_classification"]
        lines.extend([
            "",
            f"### {subject['subject_id']}",
            f"- Likely intent: {intent['label']} ({intent['confidence']} confidence; hypothesis only)",
            f"- Workflow class: {workflow['workflow_class']}",
            f"- Relevance: read={workflow['read_relevance']}, write={workflow['write_relevance']}, auth={workflow['auth_relevance']}, boundary={workflow['boundary_relevance']}",
            f"- Review-support outcome: {subject['review_support_outcome']['label']} — next action: {subject['review_support_outcome']['next_action']}",
            f"- Boundary context present: {subject['context_signals']['boundary_context_present']} ({subject['context_signals']['boundary_area']})",
            f"- Reviewer observation present: {subject['context_signals']['reviewer_observation_present']}",
            f"- Export readiness: {subject['redthread_export_readiness']['status']}",
            f"- Approved replay required: {subject['approved_execution_requirements']['approved_replay_required']}",
            f"- Boundary proof required: {subject['approved_execution_requirements']['boundary_proof_required']}",
            f"- Missing evidence: {', '.join(subject['redthread_export_readiness']['reason_categories']) or 'none'}",
            f"- Reviewer question: {subject['reviewer_questions'][0]['question']}",
        ])
        observations = subject.get("local_model_observations", {})
        if observations:
            lines.extend([
                f"- Local model observation delta: {observations.get('useful_delta', False)}",
                f"- Why boundary-relevant: {observations.get('why_this_is_boundary_relevant', 'not_provided')}",
                f"- Strongest supporting signal: {observations.get('strongest_supporting_signal', 'not_provided')}",
                f"- Remaining uncertainty: {observations.get('remaining_uncertainty', 'not_provided')}",
                f"- RedThread first check: {observations.get('redthread_first_check', 'not_provided')}",
            ])
    lines.extend([
        "",
        "## Safety notes",
        "- The review uses sanitized batch artifacts only.",
        "- It does not execute endpoints or authorize replay.",
        "- It produces hypotheses, evidence gaps, reviewer questions, and RedThread export context only.",
        "- RedThread evaluation is required before any security conclusion.",
        "",
    ])
    return "\n".join(lines)


def _assert_safe_artifacts(payloads: list[dict[str, Any] | str], fail_on_marker_hit: bool) -> dict[str, Any]:
    text = "\n".join(json.dumps(p, sort_keys=True) if isinstance(p, dict) else p for p in payloads)
    audit = marker_audit(text)
    lower = text.casefold()
    language_hits = [term for term in FORBIDDEN_CLAIM_LANGUAGE if term in lower]
    audit["forbidden_claim_language_hits"] = language_hits
    audit["forbidden_claim_language_hit_count"] = len(language_hits)
    audit["passed"] = bool(audit["passed"])
    if fail_on_marker_hit and not audit["passed"]:
        raise ValueError(f"sanitized intent review privacy audit failed: {audit}")
    return audit


def _validate_llm_review(review: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if review.get("schema_version") != REVIEW_SCHEMA_VERSION:
        raise ValueError("LLM review output used an unsupported schema_version")
    expected_subject_ids = {str(subject["subject_id"]) for subject in context.get("subjects", [])}
    actual_subject_ids = {str(subject.get("subject_id")) for subject in review.get("subjects", [])}
    if actual_subject_ids != expected_subject_ids:
        raise ValueError("LLM review output subject set does not match sanitized context")
    required_subject_keys = {
        "subject_id",
        "workflow_classification",
        "endpoint_role_categories",
        "intent_hypotheses",
        "test_hypotheses",
        "missing_evidence",
        "reviewer_questions",
        "redthread_export_readiness",
        "approved_execution_requirements",
        "finding_semantics",
    }
    required_workflow_keys = {"workflow_class", "read_relevance", "write_relevance", "auth_relevance", "boundary_relevance", "side_effect_risk"}
    for subject in review.get("subjects", []):
        missing_subject_keys = required_subject_keys - set(subject)
        if missing_subject_keys:
            raise ValueError(f"LLM review subject missing required keys: {sorted(missing_subject_keys)}")
        workflow = subject.get("workflow_classification", {})
        missing_workflow_keys = required_workflow_keys - set(workflow)
        if missing_workflow_keys:
            raise ValueError(f"LLM review workflow_classification missing required keys: {sorted(missing_workflow_keys)}")
        finding = subject.get("finding_semantics", {})
        if finding.get("confirmed_finding_claimed") or finding.get("severity_claimed") or finding.get("scanner_claimed"):
            raise ValueError("LLM review output attempted to claim finding, severity, or scanner semantics")
        execution = subject.get("approved_execution_requirements", {})
        if execution.get("default_live_execution_allowed"):
            raise ValueError("LLM review output attempted to allow default live execution")
    return review


def _load_llm_review(path: str | Path, context: dict[str, Any]) -> dict[str, Any]:
    return _validate_llm_review(_read_json(Path(path)), context)


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return json.loads(stripped)


def _run_local_llm_review(output_dir: Path, context: dict[str, Any], command: str | None) -> dict[str, Any]:
    prompt_path = output_dir / "llm_intent_review_prompt.json"
    raw_output_path = output_dir / "local_llm_raw_output.txt"
    status: dict[str, Any] = {
        "schema_version": "adopt_redthread.local_intent_review_runner.v0",
        "backend": "local_command",
        "command_configured": bool(command),
        "used": False,
        "fallback_to_deterministic": True,
        "raw_artifact_access_allowed": False,
    }
    if not command:
        status["status"] = "unavailable"
        status["reason"] = "INTENT_REVIEW_LOCAL_LLM_CMD not configured"
        return {"status": status}
    try:
        timeout = int(os.environ.get("INTENT_REVIEW_LOCAL_LLM_TIMEOUT_SECONDS", "120"))
        completed = subprocess.run(
            command,
            input=prompt_path.read_text(encoding="utf-8"),
            text=True,
            shell=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        raw_output_path.write_text(completed.stdout, encoding="utf-8")
        status["returncode"] = completed.returncode
        status["raw_output_path"] = str(raw_output_path)
        if completed.returncode != 0:
            status["status"] = "failed"
            status["reason"] = "local command returned non-zero exit status"
            return {"status": status}
        review = _validate_llm_review(_extract_json_object(completed.stdout), context)
        status["status"] = "accepted"
        status["used"] = True
        status["fallback_to_deterministic"] = False
        return {"status": status, "review": review}
    except Exception as exc:
        status["status"] = "failed"
        status["reason"] = exc.__class__.__name__
        status["detail"] = str(exc)[:500]
        return {"status": status}


def _write_llm_prompt(output_dir: Path, context: dict[str, Any]) -> None:
    output_template = build_intent_review(context)
    prompt = {
        "role": "Sanitized Intent Review Agent",
        "task": "Return one JSON object matching required_output_template. Use sanitized_context only to improve advisory intent labels, local_model_observations, gaps, and reviewer questions when evidence supports it. RedThread execution handoff candidates are generated deterministically after this review is validated.",
        "output_rules": [
            "Return ONLY JSON. Do not wrap in markdown fences.",
            "The top-level schema_version must be adopt_redthread.sanitized_intent_review.v0.",
            "Do not return sanitized_context as the top-level object.",
            "Keep the same subject IDs as sanitized_context.subjects.",
            "If unsure, preserve the template's cautious values rather than inventing facts.",
            "Replace not_provided_by_deterministic_review values in local_model_observations when sanitized_context supports a specific advisory observation.",
            "Set local_model_observations.useful_delta=true only when you add a materially useful observation beyond the template; otherwise keep false.",
            "Keep RedThread as the final evaluator; do not approve, block, or claim release decisions.",
            "Do not author redthread_execution_handoff or execution_candidates in this response; use local_model_observations only for bounded advisory reasoning.",
        ],
        "forbidden": [
            "raw HAR access",
            "raw URLs, paths, headers, cookies, bodies, auth values, IDs, secrets, or app field names",
            "live endpoint execution",
            "finding, severity, exploit, scanner, or release-gate claims",
        ],
        "required_schema_version": REVIEW_SCHEMA_VERSION,
        "required_output_template": output_template,
        "execution_handoff_policy": {
            "generated_by": "adopt-redthread deterministic builder after review validation",
            "local_model_may_author_candidates": False,
            "local_model_allowed_enrichment_field": "subjects[].local_model_observations",
            "candidate_requirements": [
                "candidate recommendations must cite sanitized observation IDs",
                "live execution remains false",
                "RedThread final gate remains required",
                "no finding, severity, exploit proof, scanner, or release decision claims"
            ],
        },
        "sanitized_context": context,
    }
    _write_json(output_dir / "llm_intent_review_prompt.json", prompt)


def build_sanitized_intent_review(
    batch_dir: str | Path,
    output_dir: str | Path | None = None,
    *,
    fail_on_marker_hit: bool = True,
    agent_mode: str = "deterministic",
    llm_review_output: str | Path | None = None,
    prepare_llm_prompt: bool = False,
    boundary_rubric: str | Path | None = None,
    reviewer_observations: str | Path | None = None,
) -> dict[str, Any]:
    batch_dir = Path(batch_dir)
    output_dir = Path(output_dir) if output_dir else batch_dir / "intent_review"
    context = build_intent_review_context(
        batch_dir,
        boundary_rubric=boundary_rubric,
        reviewer_observations=reviewer_observations,
    )
    local_llm_status: dict[str, Any] | None = None
    if agent_mode not in {"auto", "deterministic", "llm"}:
        raise ValueError("agent_mode must be auto, deterministic, or llm")
    if agent_mode in {"auto", "llm"}:
        _write_llm_prompt(output_dir, context)
    if agent_mode == "llm":
        if prepare_llm_prompt and not llm_review_output:
            _write_json(output_dir / "intent_review_context.json", context)
            return {
                "output_dir": str(output_dir),
                "agent_mode": agent_mode,
                "status": "llm_prompt_prepared",
                "prompt_path": str(output_dir / "llm_intent_review_prompt.json"),
                "context_path": str(output_dir / "intent_review_context.json"),
                "subject_count": len(context.get("subjects", [])),
            }
        if not llm_review_output:
            raise ValueError("--agent-mode llm requires --llm-review-output with a schema-valid offline model output")
        review = _load_llm_review(llm_review_output, context)
    elif agent_mode == "auto":
        local_result = _run_local_llm_review(output_dir, context, os.environ.get("INTENT_REVIEW_LOCAL_LLM_CMD"))
        local_llm_status = local_result["status"]
        review = local_result.get("review") or build_intent_review(context)
    else:
        review = build_intent_review(context)
    export = build_redthread_evidence_export(review)
    advancement = build_advancement_summary(review)
    handoff = build_redthread_execution_handoff(review)
    handoff_validation = validate_execution_handoff(handoff, review)
    if not handoff_validation["passed"]:
        raise ValueError(f"redthread execution handoff validation failed: {handoff_validation}")
    intent_evidence = build_redthread_intent_evidence(review, handoff)
    intent_evidence_validation = validate_redthread_intent_evidence(intent_evidence)
    if not intent_evidence_validation["importable"]:
        raise ValueError(f"redthread intent evidence validation failed: {intent_evidence_validation}")
    importability_report = build_redthread_importability_report(intent_evidence, intent_evidence_validation)
    candidate_workflow_import = build_redthread_candidate_workflow_import(intent_evidence, intent_evidence_validation)
    product_proof = build_product_proof_report(intent_evidence, intent_evidence_validation, importability_report, candidate_workflow_import)
    business_validation = build_business_validation_plan(review, advancement)
    schema_validation = validate_intent_review_contract(review, export)
    if not schema_validation["passed"]:
        raise ValueError(f"sanitized intent review schema validation failed: {schema_validation}")
    contract_preview = build_redthread_contract_preview(export)
    markdown = render_intent_review_markdown(review)
    advancement_markdown = render_advancement_markdown(advancement)
    handoff_markdown = render_execution_handoff_markdown(handoff)
    intent_evidence_markdown = render_redthread_intent_evidence_markdown(intent_evidence, intent_evidence_validation, importability_report)
    importability_markdown = render_importability_report_markdown(importability_report)
    candidate_workflow_markdown = render_candidate_workflow_import_markdown(candidate_workflow_import)
    product_proof_markdown = render_product_proof_markdown(product_proof)
    operator_handoff_markdown = render_operator_handoff_markdown(intent_evidence, importability_report, candidate_workflow_import, product_proof)
    safety_payloads: list[dict[str, Any] | str] = [context, review, export, advancement, handoff, handoff_validation, intent_evidence, intent_evidence_validation, importability_report, candidate_workflow_import, product_proof, business_validation, schema_validation, contract_preview, markdown, advancement_markdown, handoff_markdown, intent_evidence_markdown, importability_markdown, candidate_workflow_markdown, product_proof_markdown, operator_handoff_markdown]
    if local_llm_status:
        safety_payloads.append(local_llm_status)
    audit = _assert_safe_artifacts(safety_payloads, fail_on_marker_hit)
    context["privacy_attestation"]["marker_audit_passed"] = audit["passed"]
    review["privacy_attestation"]["marker_audit_passed"] = audit["passed"]

    _write_json(output_dir / "intent_review_context.json", context)
    _write_json(output_dir / "intent_review.json", review)
    _write_text(output_dir / "intent_review.md", markdown)
    _write_json(output_dir / "redthread_evidence_export.json", export)
    _write_json(output_dir / "advancement_summary.json", advancement)
    _write_text(output_dir / "advancement_summary.md", advancement_markdown)
    _write_json(output_dir / "redthread_execution_handoff.json", handoff)
    _write_text(output_dir / "redthread_execution_handoff.md", handoff_markdown)
    _write_json(output_dir / "redthread_execution_handoff_validation.json", handoff_validation)
    _write_json(output_dir / "redthread_intent_evidence.json", intent_evidence)
    _write_text(output_dir / "redthread_intent_evidence.md", intent_evidence_markdown)
    _write_json(output_dir / "redthread_intent_evidence_validation.json", intent_evidence_validation)
    _write_json(output_dir / "redthread_importability_report.json", importability_report)
    _write_text(output_dir / "redthread_importability_report.md", importability_markdown)
    _write_json(output_dir / "redthread_candidate_workflow_import.json", candidate_workflow_import)
    _write_text(output_dir / "redthread_candidate_workflow_import.md", candidate_workflow_markdown)
    _write_json(output_dir / "redthread_product_proof.json", product_proof)
    _write_text(output_dir / "redthread_product_proof.md", product_proof_markdown)
    _write_text(output_dir / "redthread_operator_handoff.md", operator_handoff_markdown)
    _write_json(output_dir / "business_validation_plan.json", business_validation)
    _write_json(output_dir / "schema_validation.json", schema_validation)
    _write_json(output_dir / "redthread_evidence_contract_preview.json", contract_preview)
    if local_llm_status:
        _write_json(output_dir / "local_llm_status.json", local_llm_status)
    _write_json(output_dir / "privacy_audit.json", audit)
    result = {
        "output_dir": str(output_dir),
        "privacy_audit": audit,
        "subject_count": len(review["subjects"]),
        "agent_mode": agent_mode,
        "execution_handoff_path": str(output_dir / "redthread_execution_handoff.json"),
        "execution_candidate_count": handoff["summary"]["candidate_count"],
        "ready_for_redthread_review_count": handoff["summary"]["ready_for_redthread_review_count"],
        "redthread_intent_evidence_path": str(output_dir / "redthread_intent_evidence.json"),
        "redthread_importable": importability_report["importable"],
        "candidate_workflow_created": importability_report["candidate_workflow_created"],
        "candidate_workflow_import_path": str(output_dir / "redthread_candidate_workflow_import.json"),
        "product_proof_passed": product_proof["passed"],
    }
    if local_llm_status:
        result["local_llm_status"] = local_llm_status
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build sanitized intent review artifacts from an offline HAR evidence batch.")
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--fail-on-marker-hit", action="store_true")
    parser.add_argument("--agent-mode", choices=("auto", "deterministic", "llm"), default="auto")
    parser.add_argument("--llm-review-output")
    parser.add_argument("--prepare-llm-prompt", action="store_true", help="Write sanitized LLM prompt/context and exit without requiring model output.")
    parser.add_argument("--boundary-rubric", help="Optional sanitized boundary context/rubric intake JSON.")
    parser.add_argument("--reviewer-observations", help="Optional sanitized reviewer observations intake JSON.")
    args = parser.parse_args()
    result = build_sanitized_intent_review(
        args.batch_dir,
        args.output_dir,
        fail_on_marker_hit=args.fail_on_marker_hit,
        agent_mode=args.agent_mode,
        llm_review_output=args.llm_review_output,
        prepare_llm_prompt=args.prepare_llm_prompt,
        boundary_rubric=args.boundary_rubric,
        reviewer_observations=args.reviewer_observations,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
