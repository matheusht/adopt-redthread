from __future__ import annotations

from typing import Any

from adapters.bridge.workflow_review_candidates import (
    candidate_summary,
    discover_all_candidates,
    discover_header_binding_pairs,
    enrich_manifest_candidates,
    session_note,
)
from adapters.bridge.workflow_review_insights import (
    build_body_template_gaps,
    build_open_questions,
    build_required_contexts,
)


def build_workflow_review_manifest(
    workflow_plan: dict[str, Any],
    live_workflow_summary: dict[str, Any] | None,
    cases: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    resolved_cases = cases or {}
    results = _results_by_workflow(live_workflow_summary)
    review_artifacts = _artifacts_by_workflow(live_workflow_summary)
    candidate_pairs_by_workflow = discover_all_candidates(workflow_plan)
    header_pairs_by_workflow = discover_header_binding_pairs(workflow_plan)
    manifest_workflows = [
        _manifest_workflow(
            workflow,
            resolved_cases,
            results.get(str(workflow.get("workflow_id", "unknown"))),
            review_artifacts.get(str(workflow.get("workflow_id", "unknown"))),
            candidate_pairs_by_workflow.get(str(workflow.get("workflow_id", "unknown")), []),
            header_pairs_by_workflow.get(str(workflow.get("workflow_id", "unknown")), []),
        )
        for workflow in workflow_plan.get("workflows", [])
    ]
    all_candidates = [
        candidate
        for workflow_pairs in candidate_pairs_by_workflow.values()
        for pair in workflow_pairs
        for candidate in pair.get("candidate_bindings", []) + pair.get("candidate_path_bindings", [])
    ]
    all_header_candidates = [
        candidate
        for workflow_candidates in header_pairs_by_workflow.values()
        for candidate in workflow_candidates
    ]
    required_contexts = _aggregate_required_contexts(manifest_workflows)
    body_template_gaps = [gap for workflow in manifest_workflows for gap in workflow.get("body_template_gaps", [])]
    open_questions = [question for workflow in manifest_workflows for question in workflow.get("open_questions", [])]
    return {
        "plan_id": workflow_plan.get("plan_id", "unknown"),
        "workflow_count": workflow_plan.get("workflow_count", len(workflow_plan.get("workflows", []))),
        "approved_binding_alias_count": workflow_plan.get("approved_binding_alias_count", 0),
        "approved_binding_alias_summary": workflow_plan.get("approved_binding_alias_summary", {}),
        "workflow_requirement_summary": {} if live_workflow_summary is None else live_workflow_summary.get("workflow_requirement_summary", {}),
        "workflow_failure_class_summary": {} if live_workflow_summary is None else live_workflow_summary.get("workflow_failure_class_summary", {}),
        "reason_counts": {} if live_workflow_summary is None else live_workflow_summary.get("reason_counts", {}),
        "required_contexts": required_contexts,
        "body_template_gaps": body_template_gaps,
        "open_questions": open_questions,
        "review_recommended_before_live_execution": bool(manifest_workflows),
        "candidate_binding_summary": candidate_summary(all_candidates + all_header_candidates),
        "workflows": manifest_workflows,
    }


def _manifest_workflow(
    workflow: dict[str, Any],
    cases: dict[str, dict[str, Any]],
    result: dict[str, Any] | None,
    review_artifact: dict[str, Any] | None,
    candidate_pairs: list[dict[str, Any]],
    header_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    required_contexts = build_required_contexts(workflow, cases)
    body_template_gaps = build_body_template_gaps(workflow, cases)
    open_questions = build_open_questions(workflow, body_template_gaps, candidate_pairs, header_candidates)
    return {
        "workflow_id": workflow.get("workflow_id", "unknown"),
        "step_count": workflow.get("step_count", len(workflow.get("steps", []))),
        "workflow_context_requirements": workflow.get("workflow_context_requirements", {}),
        "session_context_requirements": workflow.get("session_context_requirements", {}),
        "required_contexts": required_contexts,
        "response_binding_contract": workflow.get("response_binding_contract", {}),
        "replay_status": None if result is None else result.get("status"),
        "failure_reason_code": None if result is None else result.get("failure_reason_code"),
        "failure_detail": None if result is None else result.get("failure_detail"),
        "failure_narrative": None if result is None else result.get("failure_narrative"),
        "binding_review_artifact": review_artifact or {"workflow_id": workflow.get("workflow_id", "unknown"), "steps": []},
        "approved_binding_alias_used_count": workflow.get("approved_binding_alias_used_count", 0),
        "approved_binding_alias_usages": workflow.get("approved_binding_alias_usages", []),
        "candidate_binding_pairs": candidate_pairs,
        "candidate_header_binding_pairs": header_candidates,
        "session_continuity_note": session_note(header_candidates),
        "body_template_gaps": body_template_gaps,
        "open_questions": open_questions,
        "review_recommended_before_live_execution": True,
        "steps": [
            {
                "case_id": step.get("case_id"),
                "workflow_step_index": step.get("workflow_step_index", 0),
                "step_context_requirements": step.get("step_context_requirements", {}),
                "response_bindings": step.get("response_bindings", []),
                "binding_review_summary": step.get("binding_review_summary", {}),
                "binding_review_decisions": step.get("binding_review_decisions", []),
            }
            for step in workflow.get("steps", [])
        ],
    }


def _results_by_workflow(live_workflow_summary: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if live_workflow_summary is None:
        return {}
    return {
        str(result.get("workflow_id", "unknown")): result
        for result in live_workflow_summary.get("results", [])
    }


def _artifacts_by_workflow(live_workflow_summary: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if live_workflow_summary is None:
        return {}
    return {
        str(artifact.get("workflow_id", "unknown")): artifact
        for artifact in live_workflow_summary.get("workflow_binding_review_artifacts", [])
    }


def _aggregate_required_contexts(workflows: list[dict[str, Any]]) -> dict[str, Any]:
    auth_case_ids = [
        case_id
        for workflow in workflows
        for case_id in workflow.get("required_contexts", {}).get("auth_context_case_ids", [])
    ]
    write_case_ids = [
        case_id
        for workflow in workflows
        for case_id in workflow.get("required_contexts", {}).get("write_context_case_ids", [])
    ]
    return {
        "auth_context_required": any(workflow.get("required_contexts", {}).get("auth_context_required") for workflow in workflows),
        "write_context_required": any(workflow.get("required_contexts", {}).get("write_context_required") for workflow in workflows),
        "auth_context_case_ids": auth_case_ids,
        "write_context_case_ids": write_case_ids,
        "same_auth_context_required": any(workflow.get("required_contexts", {}).get("same_auth_context_required") for workflow in workflows),
        "same_write_context_required": any(workflow.get("required_contexts", {}).get("same_write_context_required") for workflow in workflows),
    }


_candidate_summary = candidate_summary

__all__ = ["build_workflow_review_manifest", "enrich_manifest_candidates", "_candidate_summary"]
