from __future__ import annotations

from typing import Any


SUPPORTED_WORKFLOW_MODES = {
    "live_safe_read",
    "live_safe_read_with_approved_auth",
    "live_reviewed_write_staging",
}


def build_live_workflow_plan(live_attack_plan: dict[str, Any]) -> dict[str, Any]:
    workflows = [_build_workflow(group, cases) for group, cases in _group_cases(live_attack_plan).items() if len(cases) > 1]
    return {
        "plan_id": f"{live_attack_plan.get('plan_id', 'unknown')}-workflows",
        "source": live_attack_plan.get("source", "unknown"),
        "input_file": live_attack_plan.get("input_file", "unknown"),
        "workflow_count": len(workflows),
        "workflows": workflows,
    }


def _group_cases(live_attack_plan: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for case in live_attack_plan.get("cases", []):
        group = str(case.get("workflow_group", "default"))
        grouped.setdefault(group, []).append(case)
    for group, cases in grouped.items():
        grouped[group] = sorted(cases, key=lambda case: int(case.get("workflow_step_index", 0)))
    return grouped


def _build_workflow(group: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    executable_step_count = sum(1 for case in cases if case.get("execution_mode") in SUPPORTED_WORKFLOW_MODES)
    review_required = any(not case.get("allowed") for case in cases)
    return {
        "workflow_id": group,
        "step_count": len(cases),
        "executable_step_count": executable_step_count,
        "review_required": review_required,
        "abort_rule": "stop_on_first_failure",
        "steps": [
            {
                "case_id": case.get("case_id"),
                "workflow_step_index": case.get("workflow_step_index", 0),
                "method": case.get("method"),
                "path": case.get("path"),
                "execution_mode": case.get("execution_mode"),
                "approval_mode": case.get("approval_mode"),
                "target_env": case.get("target_env"),
                "allowed": case.get("allowed", False),
            }
            for case in cases
        ],
    }
