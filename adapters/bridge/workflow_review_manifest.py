from __future__ import annotations

from typing import Any


def build_workflow_review_manifest(
    workflow_plan: dict[str, Any],
    live_workflow_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    results = _results_by_workflow(live_workflow_summary)
    review_artifacts = _artifacts_by_workflow(live_workflow_summary)
    return {
        "plan_id": workflow_plan.get("plan_id", "unknown"),
        "workflow_count": workflow_plan.get("workflow_count", len(workflow_plan.get("workflows", []))),
        "workflow_requirement_summary": {} if live_workflow_summary is None else live_workflow_summary.get("workflow_requirement_summary", {}),
        "workflow_failure_class_summary": {} if live_workflow_summary is None else live_workflow_summary.get("workflow_failure_class_summary", {}),
        "reason_counts": {} if live_workflow_summary is None else live_workflow_summary.get("reason_counts", {}),
        "workflows": [
            _manifest_workflow(workflow, results.get(str(workflow.get("workflow_id", "unknown"))), review_artifacts.get(str(workflow.get("workflow_id", "unknown"))))
            for workflow in workflow_plan.get("workflows", [])
        ],
    }


def _manifest_workflow(
    workflow: dict[str, Any],
    result: dict[str, Any] | None,
    review_artifact: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "workflow_id": workflow.get("workflow_id", "unknown"),
        "step_count": workflow.get("step_count", len(workflow.get("steps", []))),
        "workflow_context_requirements": workflow.get("workflow_context_requirements", {}),
        "session_context_requirements": workflow.get("session_context_requirements", {}),
        "response_binding_contract": workflow.get("response_binding_contract", {}),
        "replay_status": None if result is None else result.get("status"),
        "failure_reason_code": None if result is None else result.get("failure_reason_code"),
        "failure_detail": None if result is None else result.get("failure_detail"),
        "binding_review_artifact": review_artifact or {"workflow_id": workflow.get("workflow_id", "unknown"), "steps": []},
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
