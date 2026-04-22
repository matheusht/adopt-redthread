from __future__ import annotations

from typing import Any


def build_failure_narrative(
    reason_code: str,
    reason_detail: str,
    *,
    case: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    approved_write_body_json_present: bool = False,
) -> str:
    if reason_code == "missing_auth_context":
        return "Replay blocked: this workflow needs approved auth context before the protected step can run."
    if reason_code == "missing_write_context":
        return "Replay blocked: this workflow needs approved write context before the reviewed write step can run."
    if reason_code == "binding_review_required":
        return "Replay blocked: one or more inferred bindings are still pending operator review."
    if reason_code == "prior_step_missing":
        return "Replay blocked: a step depends on a prior workflow step that did not complete."
    if reason_code == "host_continuity_mismatch":
        return "Replay blocked: supplied host context does not match the workflow host continuity contract."
    if reason_code == "target_env_mismatch":
        return "Replay blocked: supplied target environment does not match the workflow contract."
    if reason_code == "auth_header_family_mismatch":
        return "Replay blocked: approved auth headers do not match the captured auth header family required by this workflow."
    if reason_code == "response_binding_missing":
        return f"Replay blocked: required binding value '{reason_detail}' was not extracted from a prior step response."
    if reason_code == "response_binding_target_missing":
        if case and case.get("execution_mode") == "live_reviewed_write_staging" and not approved_write_body_json_present:
            return (
                "Replay blocked: a request_body_json binding target could not be updated because the HAR body blueprint was stripped "
                "and no approved fallback body template was available."
            )
        return f"Replay blocked: target request field for binding '{reason_detail}' was not present in the request blueprint/template."
    if reason_code == "timeout":
        return "Request was sent, but no useful response bytes arrived before the timeout budget ended. This can happen when a streaming endpoint never produces its first chunk."
    if reason_code == "stream_open_partial_read":
        bytes_read = None if result is None else result.get("first_chunk_bytes")
        if bytes_read is not None:
            return f"Request reached the server and opened a streaming response. Engine captured the first {bytes_read} bytes only, then stopped because stream reading is intentionally bounded."
        return "Request reached the server and opened a streaming response. Engine captured only the first bounded chunk, then stopped on purpose."
    if reason_code == "url_error":
        return f"Network/URL failure prevented the request from completing: {reason_detail}."
    if reason_code == "http_error":
        status_code = "unknown"
        if result is not None and result.get("status_code") is not None:
            status_code = str(result.get("status_code"))
        return f"Request reached the server but returned HTTP {status_code}. Review body, header, and session contracts for this step."
    if reason_code.startswith("http_status_"):
        return f"Request reached the server and failed with {reason_code.replace('http_status_', 'HTTP ')}."
    return f"Workflow failed with {reason_code}: {reason_detail}."


def summarize_failure_narratives(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    narratives: list[dict[str, Any]] = []
    for result in results:
        reason_code = str(result.get("failure_reason_code", "")).strip()
        if not reason_code:
            continue
        narratives.append(
            {
                "workflow_id": result.get("workflow_id", "unknown"),
                "status": result.get("status"),
                "failure_reason_code": reason_code,
                "failure_detail": result.get("failure_detail"),
                "failure_narrative": result.get("failure_narrative") or build_failure_narrative(reason_code, str(result.get('failure_detail', ''))),
            }
        )
    return narratives
