from __future__ import annotations

from typing import Any


def approved_write_body_json(
    case: dict[str, Any],
    write_payload: dict[str, Any] | None,
    allow_reviewed_writes: bool,
) -> dict[str, Any] | None:
    if case.get("execution_mode") != "live_reviewed_write_staging":
        return None
    if not allow_reviewed_writes or not write_payload or not write_payload.get("approved"):
        return None
    case_approval = write_payload.get("case_approvals", {}).get(str(case.get("case_id")), {})
    body = case_approval.get("json_body") if case_approval.get("use_bound_body_json") else None
    return body if isinstance(body, dict) else None


def binding_review_artifact(workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflow_id": workflow.get("workflow_id", "unknown"),
        "steps": [
            {
                "case_id": step.get("case_id"),
                "workflow_step_index": step.get("workflow_step_index", 0),
                "binding_review_summary": step.get("binding_review_summary", {}),
                "binding_review_decisions": step.get("binding_review_decisions", []),
            }
            for step in workflow.get("steps", [])
            if step.get("binding_review_summary") or step.get("binding_review_decisions")
        ],
    }
