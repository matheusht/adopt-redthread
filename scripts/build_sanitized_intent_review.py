#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
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

ALLOWED_SUBJECT_ARTIFACTS = {
    "workflow_summary.json",
    "subject_summary.json",
    "evidence_report.md",
    "privacy_audit.json",
}

FORBIDDEN_CLAIM_LANGUAGE = ("critical severity", "high severity", "confirmed vulnerability", "exploitable")

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


def build_intent_review_context(batch_dir: str | Path) -> dict[str, Any]:
    batch_dir = Path(batch_dir)
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
    for i, item in enumerate(subject.get("next_evidence_needed", []), start=1):
        text = str(item)
        if "boundary" in text:
            category = "missing_boundary_context"
        elif "auth" in text:
            category = "missing_auth_context"
        elif "write" in text:
            category = "missing_write_context"
        elif "reviewer" in text or "observation" in text:
            category = "missing_reviewer_observation"
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


def _review_subject(subject: dict[str, Any]) -> dict[str, Any]:
    workflow_class = _workflow_class(subject)
    missing = _missing_evidence(subject)
    approved_replay_required = subject["write_surface_present"] or subject["auth_surface_present"]
    boundary_proof_required = not subject["boundary_evidence_present"]
    export_status = "blocked" if subject["batch_status"] != "processed" else ("ready_with_gaps" if missing else "ready")
    return {
        "subject_id": subject["subject_id"],
        "input_quality": {
            "status": "usable" if subject["batch_status"] == "processed" else "blocked",
            "blocker_categories": list(subject.get("primary_blocker_categories", [])),
            "evidence_gap_categories": [gap["category"] for gap in missing],
        },
        "intent_hypotheses": [{
            "id": "intent_hypothesis_001",
            "label": _intent_label(subject, workflow_class),
            "confidence": "medium" if subject["fixture_count"] else "low",
            "basis": ["sanitized_workflow_summary", "sanitized_subject_summary"],
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
            "question": "Does this sanitized workflow require approved non-production replay or boundary proof before RedThread evaluation?",
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
                "reviewer_questions": s["reviewer_questions"],
                "missing_evidence": s["missing_evidence"],
            }
            for s in subjects
        ],
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
            f"- Export readiness: {subject['redthread_export_readiness']['status']}",
            f"- Approved replay required: {subject['approved_execution_requirements']['approved_replay_required']}",
            f"- Boundary proof required: {subject['approved_execution_requirements']['boundary_proof_required']}",
            f"- Missing evidence: {', '.join(subject['redthread_export_readiness']['reason_categories']) or 'none'}",
            f"- Reviewer question: {subject['reviewer_questions'][0]['question']}",
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


def _load_llm_review(path: str | Path, context: dict[str, Any]) -> dict[str, Any]:
    review = _read_json(Path(path))
    if review.get("schema_version") != REVIEW_SCHEMA_VERSION:
        raise ValueError("LLM review output used an unsupported schema_version")
    expected_subject_ids = {str(subject["subject_id"]) for subject in context.get("subjects", [])}
    actual_subject_ids = {str(subject.get("subject_id")) for subject in review.get("subjects", [])}
    if actual_subject_ids != expected_subject_ids:
        raise ValueError("LLM review output subject set does not match sanitized context")
    for subject in review.get("subjects", []):
        finding = subject.get("finding_semantics", {})
        if finding.get("confirmed_finding_claimed") or finding.get("severity_claimed") or finding.get("scanner_claimed"):
            raise ValueError("LLM review output attempted to claim finding, severity, or scanner semantics")
        execution = subject.get("approved_execution_requirements", {})
        if execution.get("default_live_execution_allowed"):
            raise ValueError("LLM review output attempted to allow default live execution")
    return review


def _write_llm_prompt(output_dir: Path, context: dict[str, Any]) -> None:
    prompt = {
        "role": "Sanitized Intent Review Agent",
        "task": "Classify sanitized context into the adopt_redthread.sanitized_intent_review.v0 schema only.",
        "forbidden": [
            "raw HAR access",
            "raw URLs, paths, headers, cookies, bodies, auth values, IDs, secrets, or app field names",
            "live endpoint execution",
            "finding, severity, exploit, scanner, or release-gate claims",
        ],
        "required_schema_version": REVIEW_SCHEMA_VERSION,
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
) -> dict[str, Any]:
    batch_dir = Path(batch_dir)
    output_dir = Path(output_dir) if output_dir else batch_dir / "intent_review"
    context = build_intent_review_context(batch_dir)
    if agent_mode not in {"deterministic", "llm"}:
        raise ValueError("agent_mode must be deterministic or llm")
    if agent_mode == "llm":
        _write_llm_prompt(output_dir, context)
        if not llm_review_output:
            raise ValueError("--agent-mode llm requires --llm-review-output with a schema-valid offline model output")
        review = _load_llm_review(llm_review_output, context)
    else:
        review = build_intent_review(context)
    export = build_redthread_evidence_export(review)
    schema_validation = validate_intent_review_contract(review, export)
    if not schema_validation["passed"]:
        raise ValueError(f"sanitized intent review schema validation failed: {schema_validation}")
    contract_preview = build_redthread_contract_preview(export)
    markdown = render_intent_review_markdown(review)
    audit = _assert_safe_artifacts([context, review, export, schema_validation, contract_preview, markdown], fail_on_marker_hit)
    context["privacy_attestation"]["marker_audit_passed"] = audit["passed"]
    review["privacy_attestation"]["marker_audit_passed"] = audit["passed"]

    _write_json(output_dir / "intent_review_context.json", context)
    _write_json(output_dir / "intent_review.json", review)
    _write_text(output_dir / "intent_review.md", markdown)
    _write_json(output_dir / "redthread_evidence_export.json", export)
    _write_json(output_dir / "schema_validation.json", schema_validation)
    _write_json(output_dir / "redthread_evidence_contract_preview.json", contract_preview)
    _write_json(output_dir / "privacy_audit.json", audit)
    return {"output_dir": str(output_dir), "privacy_audit": audit, "subject_count": len(review["subjects"]), "agent_mode": agent_mode}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build sanitized intent review artifacts from an offline HAR evidence batch.")
    parser.add_argument("--batch-dir", required=True)
    parser.add_argument("--output-dir")
    parser.add_argument("--fail-on-marker-hit", action="store_true")
    parser.add_argument("--agent-mode", choices=("deterministic", "llm"), default="deterministic")
    parser.add_argument("--llm-review-output")
    args = parser.parse_args()
    result = build_sanitized_intent_review(
        args.batch_dir,
        args.output_dir,
        fail_on_marker_hit=args.fail_on_marker_hit,
        agent_mode=args.agent_mode,
        llm_review_output=args.llm_review_output,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
