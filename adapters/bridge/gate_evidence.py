from __future__ import annotations

from typing import Any


REVIEW_GAP_REASONS = {"step_not_executable", "missing_auth_context", "missing_write_context", "binding_review_required"}
CONTEXT_MISMATCH_REASONS = {
    "auth_header_family_mismatch",
    "host_continuity_mismatch",
    "target_env_mismatch",
    "prior_step_missing",
    "response_binding_missing",
    "response_binding_target_missing",
}
RUNTIME_FAILURE_REASONS = {"url_error"}


def apply_live_safe_replay_rules(
    live_safe_replay: dict[str, Any] | None,
    blockers: list[str],
    warnings: list[str],
) -> None:
    if live_safe_replay is None:
        return
    executed = int(live_safe_replay.get("executed_case_count", 0))
    success = int(live_safe_replay.get("success_count", 0))
    allowed = int(live_safe_replay.get("allowed_case_count", executed))
    if executed == 0 and allowed > 0:
        warnings.append("live_safe_replay_not_executed")
    if success < executed:
        blockers.append("live_safe_replay_failures_present")


def apply_live_workflow_rules(
    live_workflow_replay: dict[str, Any] | None,
    blockers: list[str],
    warnings: list[str],
) -> None:
    if live_workflow_replay is None:
        return
    workflow_count = int(live_workflow_replay.get("workflow_count", 0))
    executed = int(live_workflow_replay.get("executed_workflow_count", 0))
    successful = int(live_workflow_replay.get("successful_workflow_count", 0))
    reason_counts = live_workflow_replay.get("reason_counts", {})
    reasons = {str(key) for key in reason_counts}
    if executed == 0 and workflow_count > 0:
        warnings.append("live_workflow_replay_not_executed")
    if successful < executed:
        blockers.append("live_workflow_replay_failures_present")
    if int(live_workflow_replay.get("blocked_workflow_count", 0)) > 0:
        blockers.append("live_workflow_blocked_steps_present")
    if reasons & REVIEW_GAP_REASONS:
        warnings.append("live_workflow_review_gap_present")
    if reasons & CONTEXT_MISMATCH_REASONS:
        blockers.append("live_workflow_context_mismatch_present")
    if any(key.startswith("http_status_") or key in RUNTIME_FAILURE_REASONS for key in reasons):
        blockers.append("live_workflow_runtime_failures_present")


def apply_redthread_replay_rules(redthread_replay_verdict: dict[str, Any] | None, blockers: list[str]) -> None:
    if redthread_replay_verdict is None:
        return
    if not redthread_replay_verdict.get("passed", False):
        blockers.append("redthread_replay_verdict_failed")


def evidence_counts(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    summary: dict[str, Any] = {}
    for key in (
        "allowed_case_count",
        "executed_case_count",
        "success_count",
        "workflow_count",
        "executed_workflow_count",
        "successful_workflow_count",
        "blocked_workflow_count",
        "aborted_workflow_count",
        "total_executed_step_count",
        "reason_counts",
        "workflow_requirement_summary",
        "workflow_failure_class_summary",
        "binding_application_summary",
        "binding_audit_summary",
        "workflow_binding_review_artifacts",
        "planned_response_binding_count",
        "applied_response_binding_count",
        "passed",
    ):
        if key in payload:
            summary[key] = payload[key]
    return summary
