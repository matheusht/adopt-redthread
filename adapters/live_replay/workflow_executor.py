from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.live_replay.executor import execute_live_case, is_live_case_executable


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
    for step in workflow.get("steps", []):
        case = cases.get(str(step.get("case_id")))
        if not case:
            return _blocked_workflow(workflow, step_results, f"missing_case:{step.get('case_id')}")
        if not is_live_case_executable(case, auth_payload, allow_reviewed_auth, write_payload, allow_reviewed_writes):
            return _blocked_workflow(workflow, step_results, f"step_not_executable:{case.get('case_id')}")
        result = execute_live_case(case, timeout_seconds, auth_payload, allow_reviewed_auth, write_payload, allow_reviewed_writes)
        step_results.append(result)
        if not result.get("success"):
            return {
                "workflow_id": workflow.get("workflow_id", "unknown"),
                "status": "aborted",
                "executed_step_count": len(step_results),
                "step_count": workflow.get("step_count", len(workflow.get("steps", []))),
                "failed_step": case.get("case_id"),
                "results": step_results,
            }
    return {
        "workflow_id": workflow.get("workflow_id", "unknown"),
        "status": "completed",
        "executed_step_count": len(step_results),
        "step_count": workflow.get("step_count", len(workflow.get("steps", []))),
        "results": step_results,
    }


def _blocked_workflow(workflow: dict[str, Any], step_results: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    return {
        "workflow_id": workflow.get("workflow_id", "unknown"),
        "status": "blocked",
        "executed_step_count": len(step_results),
        "step_count": workflow.get("step_count", len(workflow.get("steps", []))),
        "error": reason,
        "results": step_results,
    }


def _load_optional_context(value: dict[str, Any] | str | Path | None) -> dict[str, Any] | None:
    if value is None:
        return None
    payload = _load_jsonish(value)
    return payload if isinstance(payload, dict) else None


def _load_jsonish(value: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return json.loads(Path(value).read_text())
