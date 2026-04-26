from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.live_replay.binding_history import append_binding_history
from adapters.live_replay.executor import execute_live_case, is_live_case_executable
from adapters.live_replay.stream_capture import DEFAULT_STREAM_MAX_BYTES
from adapters.live_replay.workflow_bindings import (
    apply_response_bindings,
    binding_application_summary,
    binding_review_required,
    extract_response_binding_values,
    planned_response_binding_records,
)
from adapters.live_replay.workflow_narrative import build_failure_narrative
from adapters.live_replay.workflow_requirements import step_block_reason, validate_workflow_context
from adapters.live_replay.workflow_results import aborted_workflow, blocked_workflow, build_workflow_summary
from adapters.live_replay.workflow_state import initial_workflow_state, snapshot_workflow_state, step_evidence, update_workflow_state, workflow_reason_code
from adapters.live_replay.workflow_support import approved_write_body_json, approved_write_headers, binding_review_artifact


def execute_live_workflow_replay(
    workflow_plan: dict[str, Any] | str | Path,
    live_attack_plan: dict[str, Any] | str | Path,
    *,
    auth_context: dict[str, Any] | str | Path | None = None,
    allow_reviewed_auth: bool = False,
    write_context: dict[str, Any] | str | Path | None = None,
    allow_reviewed_writes: bool = False,
    output_path: str | Path | None = None,
    binding_history_path: str | Path | None = None,
    timeout_seconds: int = 10,
    stream_max_bytes: int = DEFAULT_STREAM_MAX_BYTES,
) -> dict[str, Any]:
    workflow_payload = _load_jsonish(workflow_plan)
    attack_payload = _load_jsonish(live_attack_plan)
    auth_payload = _load_optional_context(auth_context)
    write_payload = _load_optional_context(write_context)
    cases = {str(case.get("case_id")): case for case in attack_payload.get("cases", [])}
    workflows = workflow_payload.get("workflows", [])
    results = [
        _execute_workflow(
            workflow,
            cases,
            timeout_seconds,
            auth_payload,
            allow_reviewed_auth,
            write_payload,
            allow_reviewed_writes,
            stream_max_bytes,
        )
        for workflow in workflows
    ]
    summary = build_workflow_summary(
        workflow_payload,
        workflows,
        results,
        auth_context_used=bool(auth_payload),
        write_context_used=bool(write_payload),
        stream_max_bytes=stream_max_bytes,
    )
    if binding_history_path is not None:
        summary["binding_history_rows_written"] = append_binding_history(summary, workflows, cases, binding_history_path)
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
    stream_max_bytes: int,
) -> dict[str, Any]:
    review_artifact = binding_review_artifact(workflow)
    precheck = validate_workflow_context(workflow, auth_payload, write_payload, cases)
    if precheck is not None:
        return blocked_workflow(workflow, [], initial_workflow_state(), precheck[0], precheck[1], review_artifact)

    step_results: list[dict[str, Any]] = []
    workflow_state = initial_workflow_state()
    for index, step in enumerate(workflow.get("steps", [])):
        case = cases.get(str(step.get("case_id")))
        if not case:
            return blocked_workflow(workflow, step_results, workflow_state, "missing_case", str(step.get("case_id")), review_artifact)
        if step.get("depends_on_previous_step") and len(workflow_state.get("completed_case_ids", [])) != index:
            return blocked_workflow(workflow, step_results, workflow_state, "prior_step_missing", str(case.get("case_id")), review_artifact)
        if binding_review_required(step):
            return blocked_workflow(workflow, step_results, workflow_state, "binding_review_required", str(case.get("case_id")), review_artifact)
        if not is_live_case_executable(case, auth_payload, allow_reviewed_auth, write_payload, allow_reviewed_writes):
            return blocked_workflow(workflow, step_results, workflow_state, step_block_reason(step), str(case.get("case_id")), review_artifact)
        planned_bindings = planned_response_binding_records(step)
        approved_body = approved_write_body_json(case, write_payload, allow_reviewed_writes)
        bound_case, applied_bindings, binding_error = apply_response_bindings(
            case,
            step,
            workflow_state,
            approved_body,
            approved_write_headers(case, write_payload, allow_reviewed_writes),
        )
        if binding_error is not None:
            binding_failure = {
                "failure_reason_code": binding_error[0],
                "binding_id": binding_error[1],
                "planned_response_bindings": planned_bindings,
                "applied_response_bindings": applied_bindings,
                "binding_application_summary": binding_application_summary(planned_bindings, applied_bindings),
            }
            return blocked_workflow(
                workflow,
                step_results,
                workflow_state,
                binding_error[0],
                binding_error[1],
                review_artifact,
                build_failure_narrative(
                    binding_error[0],
                    binding_error[1],
                    case=case,
                    approved_write_body_json_present=isinstance(approved_body, dict),
                ),
                binding_failure,
            )
        assert bound_case is not None
        state_before = snapshot_workflow_state(workflow_state)
        result = execute_live_case(
            bound_case,
            timeout_seconds,
            auth_payload,
            allow_reviewed_auth,
            write_payload,
            allow_reviewed_writes,
            stream_max_bytes=stream_max_bytes,
        )
        extracted_binding_values, extracted_bindings = extract_response_binding_values(workflow, str(case.get("case_id")), result)
        if result.get("success"):
            workflow_state = update_workflow_state(workflow_state, case, result, extracted_binding_values)
            result["workflow_evidence"] = step_evidence(
                case,
                result,
                state_before,
                snapshot_workflow_state(workflow_state),
                extracted_response_bindings=extracted_bindings,
                applied_response_bindings=applied_bindings,
                planned_response_bindings=planned_bindings,
            )
        else:
            result["workflow_evidence"] = step_evidence(
                case,
                result,
                state_before,
                extracted_response_bindings=extracted_bindings,
                applied_response_bindings=applied_bindings,
                planned_response_bindings=planned_bindings,
            )
        step_results.append(result)
        if not result.get("success"):
            return aborted_workflow(
                workflow,
                workflow_state,
                step_results,
                case,
                review_artifact,
                workflow_reason_code(result),
                result,
            )
    return {
        "workflow_id": workflow.get("workflow_id", "unknown"),
        "status": "completed",
        "executed_step_count": len(step_results),
        "step_count": workflow.get("step_count", len(workflow.get("steps", []))),
        "binding_review_artifact": review_artifact,
        "final_state": snapshot_workflow_state(workflow_state),
        "results": step_results,
    }


def _load_optional_context(value: dict[str, Any] | str | Path | None) -> dict[str, Any] | None:
    payload = None if value is None else _load_jsonish(value)
    return payload if isinstance(payload, dict) else None


def _load_jsonish(value: dict[str, Any] | str | Path) -> dict[str, Any]:
    return value if isinstance(value, dict) else json.loads(Path(value).read_text())
