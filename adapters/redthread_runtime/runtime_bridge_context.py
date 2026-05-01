from __future__ import annotations

from typing import Any


def build_bridge_workflow_context(
    workflow_plan: dict[str, Any] | None,
    live_workflow_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not workflow_plan:
        return {}
    alias_summary = workflow_plan.get("approved_binding_alias_summary", {})
    binding_summary = _binding_application_summary(workflow_plan, live_workflow_summary)
    binding_audit_summary = _binding_audit_summary(live_workflow_summary)
    return {
        "workflow_count": workflow_plan.get("workflow_count", 0),
        "approved_binding_alias_count": workflow_plan.get("approved_binding_alias_count", 0),
        "approved_binding_alias_used_count": alias_summary.get("used_alias_count", 0),
        "approved_binding_aliases": alias_summary.get("loaded_aliases", []),
        "approved_binding_alias_usages": alias_summary.get("used_aliases", []),
        "planned_response_binding_count": binding_summary.get("planned_response_binding_count", 0),
        "applied_response_binding_count": binding_summary.get("applied_response_binding_count", 0),
        "unapplied_response_binding_count": binding_summary.get("unapplied_response_binding_count", 0),
        "workflow_count_with_planned_bindings": binding_summary.get("workflow_count_with_planned_bindings", 0),
        "workflow_count_with_applied_bindings": binding_summary.get("workflow_count_with_applied_bindings", 0),
        "binding_application_failure_counts": binding_summary.get("binding_application_failure_counts", {}),
        "failed_binding_ids": binding_summary.get("failed_binding_ids", []),
        "binding_application_summary": binding_summary,
        "binding_audit_summary": binding_audit_summary,
    }


def _binding_audit_summary(live_workflow_summary: dict[str, Any] | None) -> dict[str, Any]:
    if live_workflow_summary is not None and isinstance(live_workflow_summary.get("binding_audit_summary"), dict):
        return dict(live_workflow_summary["binding_audit_summary"])
    return {}



def _binding_application_summary(
    workflow_plan: dict[str, Any],
    live_workflow_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    if live_workflow_summary is not None and isinstance(live_workflow_summary.get("binding_application_summary"), dict):
        return dict(live_workflow_summary["binding_application_summary"])
    workflows = workflow_plan.get("workflows", [])
    planned = sum(len(step.get("response_bindings", [])) for workflow in workflows for step in workflow.get("steps", []))
    workflow_count_with_planned = sum(1 for workflow in workflows if any(step.get("response_bindings") for step in workflow.get("steps", [])))
    return {
        "planned_response_binding_count": planned,
        "applied_response_binding_count": 0,
        "unapplied_response_binding_count": planned,
        "workflow_count_with_planned_bindings": workflow_count_with_planned,
        "workflow_count_with_applied_bindings": 0,
        "binding_application_failure_counts": {},
        "failed_binding_ids": [],
    }
