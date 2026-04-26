from __future__ import annotations

from typing import Any

from adapters.live_replay.workflow_bindings import summarize_binding_applications
from adapters.live_replay.workflow_narrative import build_failure_narrative, summarize_failure_narratives
from adapters.live_replay.workflow_requirements import summarize_failure_classes, summarize_workflow_requirements
from adapters.live_replay.workflow_state import snapshot_workflow_state
from adapters.live_replay.workflow_support import binding_review_artifact


def build_workflow_summary(
    workflow_payload: dict[str, Any],
    workflows: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    auth_context_used: bool,
    write_context_used: bool,
    stream_max_bytes: int,
) -> dict[str, Any]:
    return {
        "plan_id": workflow_payload.get("plan_id", "unknown"),
        "workflow_count": workflow_payload.get("workflow_count", len(results)),
        "executed_workflow_count": sum(1 for result in results if result.get("executed_step_count", 0) > 0),
        "successful_workflow_count": sum(1 for result in results if result["status"] == "completed"),
        "blocked_workflow_count": sum(1 for result in results if result["status"] == "blocked"),
        "aborted_workflow_count": sum(1 for result in results if result["status"] == "aborted"),
        "total_executed_step_count": sum(int(result.get("executed_step_count", 0)) for result in results),
        "reason_counts": reason_counts(results),
        "workflow_requirement_summary": summarize_workflow_requirements(workflows, results),
        "workflow_failure_class_summary": summarize_failure_classes(results),
        "binding_application_summary": summarize_binding_applications(workflows, results),
        "workflow_binding_review_artifacts": [binding_review_artifact(workflow) for workflow in workflows],
        "workflow_failure_narratives": summarize_failure_narratives(results),
        "auth_context_used": auth_context_used,
        "write_context_used": write_context_used,
        "stream_max_bytes": max(int(stream_max_bytes), 1),
        "results": results,
    }


def blocked_workflow(
    workflow: dict[str, Any],
    step_results: list[dict[str, Any]],
    workflow_state: dict[str, Any],
    reason_code: str,
    reason_detail: str,
    review_artifact: dict[str, Any],
    narrative: str | None = None,
    binding_application_failure: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocked = {
        "workflow_id": workflow.get("workflow_id", "unknown"),
        "status": "blocked",
        "executed_step_count": len(step_results),
        "step_count": workflow.get("step_count", len(workflow.get("steps", []))),
        "failure_reason_code": reason_code,
        "failure_detail": reason_detail,
        "error": f"{reason_code}:{reason_detail}",
        "binding_review_artifact": review_artifact,
        "failure_narrative": narrative or build_failure_narrative(reason_code, reason_detail),
        "final_state": snapshot_workflow_state(workflow_state),
        "results": step_results,
    }
    if binding_application_failure:
        blocked["binding_application_failure"] = binding_application_failure
    return blocked


def aborted_workflow(
    workflow: dict[str, Any],
    workflow_state: dict[str, Any],
    step_results: list[dict[str, Any]],
    case: dict[str, Any],
    review_artifact: dict[str, Any],
    reason_code: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    case_id = str(case.get("case_id", ""))
    return {
        "workflow_id": workflow.get("workflow_id", "unknown"),
        "status": "aborted",
        "executed_step_count": len(step_results),
        "step_count": workflow.get("step_count", len(workflow.get("steps", []))),
        "failed_step": case.get("case_id"),
        "failure_reason_code": reason_code,
        "failure_detail": case_id,
        "failure_narrative": build_failure_narrative(reason_code, case_id, case=case, result=result),
        "binding_review_artifact": review_artifact,
        "final_state": snapshot_workflow_state(workflow_state),
        "results": step_results,
    }


def reason_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        reason = str(result.get("failure_reason_code", "")).strip()
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return counts
