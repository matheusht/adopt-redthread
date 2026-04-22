from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.live_replay.executor import execute_live_case, is_live_case_executable
from adapters.live_replay.workflow_state import initial_workflow_state, snapshot_workflow_state, step_evidence, update_workflow_state, workflow_reason_code


def execute_live_workflow_replay(
    workflow_plan: dict[str, Any] | str | Path,
    live_attack_plan: dict[str, Any] | str | Path,
    *,
    auth_context: dict[str, Any] | str | Path | None = None,
    allow_reviewed_auth: bool = False,
    write_context: dict[str, Any] | str | Path | None = None,
    allow_reviewed_writes: bool = False,
    output_path: str | Path | None = None,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    workflow_payload = _load_jsonish(workflow_plan)
    attack_payload = _load_jsonish(live_attack_plan)
    auth_payload = _load_optional_context(auth_context)
    write_payload = _load_optional_context(write_context)
    cases = {str(case.get("case_id")): case for case in attack_payload.get("cases", [])}
    results = [
        _execute_workflow(
            workflow,
            cases,
            timeout_seconds,
            auth_payload,
            allow_reviewed_auth,
            write_payload,
            allow_reviewed_writes,
        )
        for workflow in workflow_payload.get("workflows", [])
    ]
    summary = {
        "plan_id": workflow_payload.get("plan_id", "unknown"),
        "workflow_count": workflow_payload.get("workflow_count", len(results)),
        "executed_workflow_count": sum(1 for result in results if result.get("executed_step_count", 0) > 0),
        "successful_workflow_count": sum(1 for result in results if result["status"] == "completed"),
        "blocked_workflow_count": sum(1 for result in results if result["status"] == "blocked"),
        "aborted_workflow_count": sum(1 for result in results if result["status"] == "aborted"),
        "total_executed_step_count": sum(int(result.get("executed_step_count", 0)) for result in results),
        "reason_counts": _reason_counts(results),
        "auth_context_used": bool(auth_payload),
        "write_context_used": bool(write_payload),
        "results": results,
    }
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def _execute_workflow(
    workflow: dict[str, Any],
    cases: dict[str, dict[str, Any]],
    timeout_seconds: int,
    auth_payload: dict[str, Any] | None,
    allow_reviewed_auth: bool,
    write_payload: dict[str, Any] | None,
    allow_reviewed_writes: bool,
) -> dict[str, Any]:
    step_results: list[dict[str, Any]] = []
    workflow_state = initial_workflow_state()
    for step in workflow.get("steps", []):
        case = cases.get(str(step.get("case_id")))
        if not case:
            return _blocked_workflow(workflow, step_results, workflow_state, "missing_case", str(step.get("case_id")))
        if not is_live_case_executable(case, auth_payload, allow_reviewed_auth, write_payload, allow_reviewed_writes):
            return _blocked_workflow(workflow, step_results, workflow_state, "step_not_executable", str(case.get("case_id")))
        state_before = snapshot_workflow_state(workflow_state)
        result = execute_live_case(case, timeout_seconds, auth_payload, allow_reviewed_auth, write_payload, allow_reviewed_writes)
        if result.get("success"):
            workflow_state = update_workflow_state(workflow_state, case, result)
            result["workflow_evidence"] = step_evidence(case, result, state_before, snapshot_workflow_state(workflow_state))
        else:
            result["workflow_evidence"] = step_evidence(case, result, state_before)
        step_results.append(result)
        if not result.get("success"):
            return {
                "workflow_id": workflow.get("workflow_id", "unknown"),
                "status": "aborted",
                "executed_step_count": len(step_results),
                "step_count": workflow.get("step_count", len(workflow.get("steps", []))),
                "failed_step": case.get("case_id"),
                "failure_reason_code": workflow_reason_code(result),
                "final_state": snapshot_workflow_state(workflow_state),
                "results": step_results,
            }
    return {
        "workflow_id": workflow.get("workflow_id", "unknown"),
        "status": "completed",
        "executed_step_count": len(step_results),
        "step_count": workflow.get("step_count", len(workflow.get("steps", []))),
        "final_state": snapshot_workflow_state(workflow_state),
        "results": step_results,
    }


def _blocked_workflow(
    workflow: dict[str, Any],
    step_results: list[dict[str, Any]],
    workflow_state: dict[str, Any],
    reason_code: str,
    reason_detail: str,
) -> dict[str, Any]:
    return {
        "workflow_id": workflow.get("workflow_id", "unknown"),
        "status": "blocked",
        "executed_step_count": len(step_results),
        "step_count": workflow.get("step_count", len(workflow.get("steps", []))),
        "failure_reason_code": reason_code,
        "failure_detail": reason_detail,
        "error": f"{reason_code}:{reason_detail}",
        "final_state": snapshot_workflow_state(workflow_state),
        "results": step_results,
    }


def _reason_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        reason = str(result.get("failure_reason_code", "")).strip()
        if not reason:
            continue
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _load_optional_context(value: dict[str, Any] | str | Path | None) -> dict[str, Any] | None:
    if value is None:
        return None
    payload = _load_jsonish(value)
    return payload if isinstance(payload, dict) else None


def _load_jsonish(value: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return json.loads(Path(value).read_text())
