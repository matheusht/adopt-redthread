from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from adapters.live_replay.workflow_narrative import build_failure_narrative


def initial_workflow_state() -> dict[str, Any]:
    return {
        "completed_case_ids": [],
        "observed_hosts": [],
        "response_json_keys": [],
        "last_case_id": None,
        "last_status_code": None,
        "auth_applied_any": False,
        "response_binding_values": {},
        "binding_source_case_ids": [],
    }


def snapshot_workflow_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "completed_case_ids": list(state.get("completed_case_ids", [])),
        "observed_hosts": list(state.get("observed_hosts", [])),
        "response_json_keys": list(state.get("response_json_keys", [])),
        "last_case_id": state.get("last_case_id"),
        "last_status_code": state.get("last_status_code"),
        "auth_applied_any": bool(state.get("auth_applied_any", False)),
        "response_binding_values": dict(state.get("response_binding_values", {})),
        "binding_source_case_ids": list(state.get("binding_source_case_ids", [])),
    }


def update_workflow_state(
    state: dict[str, Any],
    case: dict[str, Any],
    result: dict[str, Any],
    extracted_binding_values: dict[str, str] | None = None,
) -> dict[str, Any]:
    next_state = snapshot_workflow_state(state)
    case_id = str(case.get("case_id", "unknown"))
    next_state["completed_case_ids"] = list(next_state.get("completed_case_ids", [])) + [case_id]
    next_state["last_case_id"] = case_id
    next_state["last_status_code"] = result.get("status_code")
    next_state["auth_applied_any"] = bool(next_state.get("auth_applied_any") or result.get("auth_applied"))
    host = _case_host(case)
    if host and host not in next_state["observed_hosts"]:
        next_state["observed_hosts"] = list(next_state.get("observed_hosts", [])) + [host]
    for key in _response_json_keys(result):
        if key not in next_state["response_json_keys"]:
            next_state["response_json_keys"] = list(next_state.get("response_json_keys", [])) + [key]
    if extracted_binding_values:
        merged = dict(next_state.get("response_binding_values", {}))
        merged.update(extracted_binding_values)
        next_state["response_binding_values"] = merged
        if case_id not in next_state["binding_source_case_ids"]:
            next_state["binding_source_case_ids"] = list(next_state.get("binding_source_case_ids", [])) + [case_id]
    return next_state


def workflow_reason_code(result: dict[str, Any]) -> str:
    error = str(result.get("error", "")).strip()
    if error.startswith("url_error"):
        return "url_error"
    if error:
        return error
    if result.get("status_code"):
        return f"http_status_{result['status_code']}"
    return "unknown_error"


def step_evidence(
    case: dict[str, Any],
    result: dict[str, Any],
    state_before: dict[str, Any],
    state_after: dict[str, Any] | None = None,
    extracted_response_bindings: list[dict[str, Any]] | None = None,
    applied_response_bindings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    evidence = {
        "case_id": case.get("case_id", "unknown"),
        "workflow_step_index": case.get("workflow_step_index", 0),
        "execution_mode": case.get("execution_mode"),
        "approval_mode": case.get("approval_mode"),
        "state_before": state_before,
        "response_json_keys": _response_json_keys(result),
        "host": _case_host(case),
    }
    if state_after is not None:
        evidence["state_after"] = state_after
    if extracted_response_bindings:
        evidence["extracted_response_bindings"] = extracted_response_bindings
    if applied_response_bindings:
        evidence["applied_response_bindings"] = applied_response_bindings
    if result.get("success"):
        evidence["result_narrative"] = "Step completed successfully."
    else:
        evidence["result_narrative"] = build_failure_narrative(workflow_reason_code(result), str(case.get("case_id", "")), case=case, result=result)
    return evidence


def _response_json_keys(result: dict[str, Any]) -> list[str]:
    body = str(result.get("body_preview", "")).strip()
    if not body:
        return []
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        return sorted(str(key) for key in payload.keys())
    return []


def _case_host(case: dict[str, Any]) -> str:
    blueprint = case.get("request_blueprint", {})
    host = str(blueprint.get("host", "")).strip()
    if host:
        return host
    url = str(blueprint.get("url", "")).strip()
    return urlparse(url).netloc
