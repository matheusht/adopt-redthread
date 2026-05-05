from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.live_replay.executor import execute_live_case, is_live_case_executable
from adapters.live_replay.request_context import WRITE_METHODS
from adapters.live_replay.stream_capture import DEFAULT_STREAM_MAX_BYTES

SENSITIVE_MARKERS = (
    "value_preview",
    "set-cookie",
    "authorization:",
    "cookie:",
    "bearer ",
    "acct-123",
)

SCHEMA_PLAN_VERSION = "adopt_redthread.approved_context_replay_plan.v1"
SCHEMA_RESULT_VERSION = "adopt_redthread.approved_context_replay_result.v1"
SCHEMA_APPROVAL_VERSION = "adopt_redthread.approved_context_replay_execution_approval.v1"
SCHEMA_EXECUTION_REQUEST_VERSION = "adopt_redthread.approved_context_replay_execution_request.v1"

RESULT_CLASSES = {"not_run", "blocked", "safe_success", "safe_rejection", "potential_finding"}
HTTP_STATUS_FAMILIES = {"2xx", "3xx", "4xx", "5xx", "not_applicable", "unknown"}
RAW_FIELD_KEYS = {
    "actor_id",
    "tenant_id",
    "resource_id",
    "credential_value",
    "session_value",
    "request_body",
    "response_body",
    "auth_header",
    "authorization",
    "cookie",
    "set_cookie",
    "raw_value",
    "value_preview",
    "body_preview",
    "first_chunk_preview",
    "response_json",
    "response_headers",
    "headers",
    "json_body",
    "url",
    "target_base_url",
}


def approved_context_replay(
    live_attack_plan: dict[str, Any] | str | Path,
    *,
    case_id: str,
    auth_context: dict[str, Any] | str | Path | None = None,
    write_context: dict[str, Any] | str | Path | None = None,
    execution_approval: dict[str, Any] | str | Path | None = None,
    allow_reviewed_auth: bool = False,
    allow_reviewed_writes: bool = False,
    execute: bool = False,
    output_dir: str | Path | None = None,
    timeout_seconds: int = 10,
    stream_max_bytes: int = DEFAULT_STREAM_MAX_BYTES,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Plan or execute one approved-context endpoint replay and emit sanitized proof.

    This is intentionally a narrow executor wrapper. It never persists raw auth,
    cookie, request body, response body, or target URL values in the generated
    plan/result artifacts. Without ``execute=True`` and a sanitized execution
    approval artifact, it writes a not-run/blocked result.
    """

    attack_payload = _load_jsonish(live_attack_plan)
    case = _case_by_id(attack_payload, case_id)
    auth_payload = _load_optional(auth_context)
    write_payload = _load_optional(write_context)
    approval_payload = _load_optional(execution_approval)
    if approval_payload:
        approval_audit = _marker_audit(json.dumps(approval_payload, sort_keys=True))
        if fail_on_marker_hit and not approval_audit["passed"]:
            raise RuntimeError(
                "approved-context replay execution approval audit failed "
                f"with markers={approval_audit['marker_hit_count']} raw_fields={approval_audit['raw_field_hit_count']}"
            )
    else:
        approval_audit = _marker_audit("")

    plan = build_sanitized_replay_plan(attack_payload, case)
    context_ready = _context_ready(case, auth_payload, write_payload, allow_reviewed_auth, allow_reviewed_writes)
    approval_ready, approval_blockers = _approval_ready(case, approval_payload)
    approval_scope = _approval_scope_summary(case, approval_payload)
    blockers = []
    if not context_ready:
        blockers.append("approved_runtime_context_not_ready")
    if not approval_ready:
        blockers.extend(approval_blockers)
    if not execute:
        blockers.append("execution_not_requested")

    raw_result: dict[str, Any] | None = None
    if execute and not blockers:
        raw_result = execute_live_case(
            case,
            timeout_seconds,
            auth_payload,
            allow_reviewed_auth,
            write_payload,
            allow_reviewed_writes,
            stream_max_bytes=stream_max_bytes,
        )
    elif execute and context_ready and approval_ready and not is_live_case_executable(case, auth_payload, allow_reviewed_auth, write_payload, allow_reviewed_writes):
        blockers.append("case_not_executable_under_policy")

    result = _sanitized_result(
        plan,
        case,
        raw_result=raw_result,
        execute_requested=execute,
        context_ready=context_ready,
        approval_ready=approval_ready,
        blockers=blockers,
        approval_audit=approval_audit,
        approval_scope=approval_scope,
    )
    output_audit = _marker_audit(json.dumps({"plan": plan, "result": result}, sort_keys=True))
    result["output_marker_audit"] = output_audit
    if fail_on_marker_hit and not output_audit["passed"]:
        raise RuntimeError(
            "approved-context replay output audit failed "
            f"with markers={output_audit['marker_hit_count']} raw_fields={output_audit['raw_field_hit_count']}"
        )

    if output_dir is not None:
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        (root / "approved_context_replay_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        (root / "approved_context_replay_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        (root / "approved_context_replay.md").write_text(_markdown(plan, result), encoding="utf-8")
    return result


def build_sanitized_replay_plan(attack_payload: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    blueprint = case.get("request_blueprint", {}) if isinstance(case.get("request_blueprint"), dict) else {}
    method = str(case.get("method", "GET")).upper()
    return {
        "schema_version": SCHEMA_PLAN_VERSION,
        "plan_id": f"approved-context-replay-{case.get('case_id', 'unknown')}",
        "source_live_plan_id": str(attack_payload.get("plan_id", "unknown")),
        "artifact_policy": (
            "Approved-context replay plans contain only structural endpoint labels and execution guard states. "
            "They do not contain raw target URLs, auth values, cookies, request bodies, response bodies, or write-context values."
        ),
        "case_evidence": {
            "case_id": str(case.get("case_id", "unknown")),
            "method_class": _method_class(method),
            "method": method,
            "path_template": str(case.get("path", "unknown")),
            "workflow_group": str(case.get("workflow_group", "unknown")),
            "execution_mode": str(case.get("execution_mode", "unknown")),
            "approval_mode": str(case.get("approval_mode", "unknown")),
            "side_effect_risk": str(case.get("side_effect_risk", "unknown")),
            "query_param_count": len([item for item in blueprint.get("query_params", []) if str(item)]),
            "body_field_count": len([item for item in blueprint.get("body_fields", []) if str(item)]),
            "has_body_fields": bool([item for item in blueprint.get("body_fields", []) if str(item)]),
        },
        "required_approvals": _required_approvals(case),
        "state_model": {
            "context_ready_is_not_execution": True,
            "execution_approved_is_not_executed": True,
            "executed_is_not_validated": True,
            "validated_is_not_release_approved": True,
            "release_gate_override": False,
        },
        "non_claims": [
            "This plan is not execution proof.",
            "This plan is not external validation.",
            "This plan does not approve release.",
            "This plan does not authorize production or staging writes by itself.",
        ],
    }


def _sanitized_result(
    plan: dict[str, Any],
    case: dict[str, Any],
    *,
    raw_result: dict[str, Any] | None,
    execute_requested: bool,
    context_ready: bool,
    approval_ready: bool,
    blockers: list[str],
    approval_audit: dict[str, Any],
    approval_scope: dict[str, Any],
) -> dict[str, Any]:
    executed = raw_result is not None
    status_family = _status_family(raw_result.get("status_code") if raw_result else None)
    result_class = _result_class(case, raw_result, blockers)
    replay_failure_category = _failure_category(raw_result, blockers)
    return {
        "schema_version": SCHEMA_RESULT_VERSION,
        "plan_id": plan["plan_id"],
        "artifact_policy": (
            "Approved-context replay results contain only execution-state booleans, result classes, status families, "
            "failure categories, and sanitized endpoint labels. They must not contain raw auth, cookie, target URL, "
            "request-body, response-body, source, session, credential, actor, tenant, resource, or write-context values."
        ),
        "case_evidence": plan["case_evidence"],
        "execution_state": {
            "context_ready": bool(context_ready),
            "execution_approved": bool(approval_ready),
            "execute_requested": bool(execute_requested),
            "executed": executed,
            "validated": False,
            "release_approved": False,
        },
        "result_class": result_class,
        "http_status_family": status_family,
        "replay_failure_category": replay_failure_category,
        "blocked_reasons": blockers,
        "approval_scope": approval_scope,
        "confirmed_security_finding": False,
        "security_signal": _security_signal(result_class, status_family),
        "release_gate_override": False,
        "decision_semantics_changed": False,
        "raw_value_persistence": {
            "raw_auth_values_persisted": False,
            "raw_cookie_values_persisted": False,
            "raw_target_url_persisted": False,
            "raw_request_body_persisted": False,
            "raw_response_body_persisted": False,
            "raw_write_context_persisted": False,
        },
        "approval_marker_audit": approval_audit,
        "non_claims": [
            "Safe success is endpoint execution evidence, not release approval.",
            "Safe HTTP 4xx rejection is rejection evidence, not approval.",
            "Potential findings require separate confirmation before becoming confirmed security findings.",
            "This result does not override the local bridge approve/review/block gate.",
        ],
    }


def _case_by_id(attack_payload: dict[str, Any], case_id: str) -> dict[str, Any]:
    for case in attack_payload.get("cases", []):
        if isinstance(case, dict) and str(case.get("case_id")) == str(case_id):
            return case
    raise ValueError(f"case_id not found in live attack plan: {case_id}")


def _context_ready(
    case: dict[str, Any],
    auth_payload: dict[str, Any] | None,
    write_payload: dict[str, Any] | None,
    allow_reviewed_auth: bool,
    allow_reviewed_writes: bool,
) -> bool:
    if case.get("allowed"):
        return True
    return is_live_case_executable(case, auth_payload, allow_reviewed_auth, write_payload, allow_reviewed_writes)


def _approval_ready(case: dict[str, Any], approval: dict[str, Any] | None) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if not approval:
        return False, ["execution_approval_missing"]
    if approval.get("schema_version") != SCHEMA_APPROVAL_VERSION:
        blockers.append("invalid_execution_approval_schema")
    if approval.get("approved") is not True:
        blockers.append("execution_not_approved")
    if approval.get("approved_non_production_scope") is not True:
        blockers.append("non_production_scope_not_approved")
    if approval.get("operator_execution_approval_present") is not True:
        blockers.append("operator_execution_approval_missing")
    allowed_case_ids = [str(item) for item in approval.get("allowed_case_ids", [])] if isinstance(approval.get("allowed_case_ids"), list) else []
    if not allowed_case_ids:
        blockers.append("execution_approval_case_scope_missing")
    elif "*" in allowed_case_ids:
        blockers.append("wildcard_case_scope_not_allowed")
    elif str(case.get("case_id")) not in allowed_case_ids:
        blockers.append("case_not_in_execution_approval")
    allowed_modes = [str(item) for item in approval.get("allowed_execution_modes", [])] if isinstance(approval.get("allowed_execution_modes"), list) else []
    if not allowed_modes:
        blockers.append("execution_approval_mode_scope_missing")
    elif "*" in allowed_modes:
        blockers.append("wildcard_execution_mode_not_allowed")
    elif str(case.get("execution_mode")) not in allowed_modes:
        blockers.append("execution_mode_not_in_approval")
    if not str(approval.get("approval_label", "")).strip():
        blockers.append("execution_approval_label_missing")
    return not blockers, blockers


def _approval_scope_summary(case: dict[str, Any], approval: dict[str, Any] | None) -> dict[str, Any]:
    allowed_case_ids = [str(item) for item in approval.get("allowed_case_ids", [])] if approval and isinstance(approval.get("allowed_case_ids"), list) else []
    allowed_modes = [str(item) for item in approval.get("allowed_execution_modes", [])] if approval and isinstance(approval.get("allowed_execution_modes"), list) else []
    return {
        "approval_supplied": approval is not None,
        "schema_valid": bool(approval and approval.get("schema_version") == SCHEMA_APPROVAL_VERSION),
        "approved_flag": bool(approval and approval.get("approved") is True),
        "non_production_scope_approved": bool(approval and approval.get("approved_non_production_scope") is True),
        "operator_execution_approval_present": bool(approval and approval.get("operator_execution_approval_present") is True),
        "approval_label_present": bool(approval and str(approval.get("approval_label", "")).strip()),
        "allowed_case_count": len(allowed_case_ids),
        "allowed_execution_mode_count": len(allowed_modes),
        "explicit_case_scope_present": bool(allowed_case_ids) and "*" not in allowed_case_ids,
        "explicit_execution_mode_scope_present": bool(allowed_modes) and "*" not in allowed_modes,
        "wildcard_case_scope_requested": "*" in allowed_case_ids,
        "wildcard_execution_mode_requested": "*" in allowed_modes,
        "requested_case_in_scope": str(case.get("case_id")) in allowed_case_ids,
        "requested_execution_mode_in_scope": str(case.get("execution_mode")) in allowed_modes,
        "raw_approval_values_persisted": False,
    }


def _required_approvals(case: dict[str, Any]) -> list[str]:
    requirements = ["approved_non_production_scope", "operator_execution_approval"]
    if case.get("execution_mode") == "live_safe_read_with_approved_auth":
        requirements.append("approved_auth_context")
    if case.get("execution_mode") == "live_reviewed_write_staging" or str(case.get("method", "GET")).upper() in WRITE_METHODS:
        requirements.extend(["approved_write_context", "reviewed_write_case_approval"])
    return requirements


def _method_class(method: str) -> str:
    if method == "GET":
        return "safe_read"
    if method in WRITE_METHODS:
        return "reviewed_write"
    return "unsupported"


def _status_family(status_code: Any) -> str:
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        return "not_applicable"
    if 200 <= code <= 299:
        return "2xx"
    if 300 <= code <= 399:
        return "3xx"
    if 400 <= code <= 499:
        return "4xx"
    if 500 <= code <= 599:
        return "5xx"
    return "unknown"


def _result_class(case: dict[str, Any], raw_result: dict[str, Any] | None, blockers: list[str]) -> str:
    if blockers:
        return "not_run" if "execution_not_requested" in blockers else "blocked"
    if raw_result is None:
        return "not_run"
    status_family = _status_family(raw_result.get("status_code"))
    if status_family in {"2xx", "3xx"} and raw_result.get("success"):
        return "safe_success"
    if status_family == "4xx":
        return "safe_rejection"
    return "blocked"


def _failure_category(raw_result: dict[str, Any] | None, blockers: list[str]) -> str:
    if blockers:
        return blockers[0]
    if raw_result is None:
        return "not_run"
    if raw_result.get("success"):
        return "none"
    error = str(raw_result.get("error", "unknown"))
    if error == "http_error":
        return "http_error"
    if error.startswith("url_error"):
        return "network_error"
    if error == "timeout":
        return "timeout"
    return error or "unknown"


def _security_signal(result_class: str, status_family: str) -> str:
    if result_class == "potential_finding":
        return "potential_finding_unconfirmed"
    if result_class == "safe_rejection":
        return "safe_rejection_observed"
    if result_class == "safe_success":
        return "safe_success_observed"
    if status_family == "5xx":
        return "replay_or_server_failure_unconfirmed"
    return "none"


def _load_optional(value: dict[str, Any] | str | Path | None) -> dict[str, Any] | None:
    if value is None:
        return None
    loaded = _load_jsonish(value)
    return loaded if isinstance(loaded, dict) else None


def _load_jsonish(value: dict[str, Any] | str | Path) -> dict[str, Any]:
    return value if isinstance(value, dict) else json.loads(Path(value).read_text(encoding="utf-8"))


def _marker_audit(text: str) -> dict[str, Any]:
    lowered = text.casefold()
    marker_hits = [marker for marker in SENSITIVE_MARKERS if marker.casefold() in lowered]
    raw_field_hits = [field for field in RAW_FIELD_KEYS if f'"{field}"' in lowered or f"'{field}'" in lowered]
    return {
        "marker_set": "configured_sensitive_marker_set_plus_approved_context_raw_field_keys",
        "marker_count": len(SENSITIVE_MARKERS),
        "marker_hit_count": len(marker_hits),
        "raw_field_key_count": len(RAW_FIELD_KEYS),
        "raw_field_hit_count": len(raw_field_hits),
        "passed": len(marker_hits) == 0 and len(raw_field_hits) == 0,
        "markers": sorted(set(marker_hits)),
        "raw_field_keys": sorted(set(raw_field_hits)),
    }


def build_execution_approval_request(
    replay_plan: dict[str, Any] | str | Path,
    replay_result: dict[str, Any] | str | Path,
    *,
    output_dir: str | Path | None = None,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Build a sanitized operator request for a future replay execution approval."""

    plan = _load_jsonish(replay_plan)
    result = _load_jsonish(replay_result)
    case = result.get("case_evidence") if isinstance(result.get("case_evidence"), dict) else plan.get("case_evidence", {})
    state = result.get("execution_state", {}) if isinstance(result.get("execution_state"), dict) else {}
    template = {
        "schema_version": SCHEMA_APPROVAL_VERSION,
        "approved": False,
        "approved_non_production_scope": False,
        "operator_execution_approval_present": False,
        "allowed_case_ids": [str(case.get("case_id", "unknown"))],
        "allowed_execution_modes": [str(case.get("execution_mode", "unknown"))],
        "approval_label": "REVIEW_AND_REPLACE_SANITIZED_APPROVAL_LABEL",
        "scope_note": "Template only. Set booleans true only after explicit operator approval for a non-production execution window.",
    }
    request_status = _execution_request_status(state)
    payload = {
        "schema_version": SCHEMA_EXECUTION_REQUEST_VERSION,
        "request_status": request_status,
        "artifact_policy": (
            "Approved-context replay execution requests contain only sanitized case labels, execution state, "
            "approval checklists, and a false-by-default approval template. They must not contain raw target URLs, "
            "auth values, cookies, request bodies, response bodies, or write-context values."
        ),
        "source_plan_id": str(plan.get("plan_id", "unknown")),
        "case_evidence": {
            "case_id": str(case.get("case_id", "unknown")),
            "method_class": str(case.get("method_class", "unknown")),
            "method": str(case.get("method", "unknown")),
            "path_template": str(case.get("path_template", "unknown")),
            "execution_mode": str(case.get("execution_mode", "unknown")),
            "side_effect_risk": str(case.get("side_effect_risk", "unknown")),
        },
        "current_execution_state": {
            "context_ready": bool(state.get("context_ready", False)),
            "execution_approved": bool(state.get("execution_approved", False)),
            "execute_requested": bool(state.get("execute_requested", False)),
            "executed": bool(state.get("executed", False)),
            "validated": bool(state.get("validated", False)),
            "release_approved": bool(state.get("release_approved", False)),
        },
        "approval_checklist": [
            "Confirm the target is approved non-production scope.",
            "Confirm the case ID and execution mode match the intended endpoint replay.",
            "Confirm approved runtime context exists locally and remains ignored/unshared.",
            "Confirm no raw values will be copied into generated artifacts.",
            "Confirm the operator explicitly approves this single execution window.",
        ],
        "approval_template": template,
        "blocked_until": _blocked_until(state),
        "execution_command_shape": (
            "make evidence-approved-context-replay APPROVED_REPLAY_CASE=<case_id> "
            "APPROVED_REPLAY_EXECUTION_APPROVAL=<local_approval_json> APPROVED_REPLAY_EXECUTE=1"
        ),
        "non_claims": [
            "This request is not execution approval.",
            "This request is not execution proof.",
            "This request does not approve release.",
            "This request does not override local bridge approve/review/block semantics.",
        ],
    }
    audit = _marker_audit(json.dumps(payload, sort_keys=True))
    payload["output_marker_audit"] = audit
    if fail_on_marker_hit and not audit["passed"]:
        raise RuntimeError(
            "approved-context replay execution request audit failed "
            f"with markers={audit['marker_hit_count']} raw_fields={audit['raw_field_hit_count']}"
        )
    if output_dir is not None:
        root = Path(output_dir)
        root.mkdir(parents=True, exist_ok=True)
        (root / "execution_approval_request.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (root / "execution_approval.local.template.json").write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")
        (root / "execution_approval_request.md").write_text(_approval_request_markdown(payload), encoding="utf-8")
    return payload


def _execution_request_status(state: dict[str, Any]) -> str:
    if state.get("executed"):
        return "already_executed"
    if not state.get("context_ready"):
        return "blocked_until_runtime_context_ready"
    if state.get("execution_approved"):
        return "execution_approval_present_not_executed"
    return "ready_to_request_execution_approval"


def _blocked_until(state: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not state.get("context_ready"):
        blockers.append("approved_runtime_context_ready")
    if not state.get("execution_approved"):
        blockers.append("sanitized_execution_approval_supplied")
    if not state.get("executed"):
        blockers.append("explicit_execute_flag_requested")
    return blockers


def _approval_request_markdown(payload: dict[str, Any]) -> str:
    case = payload["case_evidence"]
    state = payload["current_execution_state"]
    lines = [
        "# Approved Context Replay Execution Approval Request",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Request status: `{payload['request_status']}`",
        f"- Case: `{case['case_id']}`",
        f"- Method class: `{case['method_class']}`",
        f"- Path template: `{case['path_template']}`",
        f"- Execution mode: `{case['execution_mode']}`",
        f"- Context ready: `{state['context_ready']}`",
        f"- Execution approved: `{state['execution_approved']}`",
        f"- Executed: `{state['executed']}`",
        f"- Validated: `{state['validated']}`",
        f"- Release approved: `{state['release_approved']}`",
        "",
        "## Approval checklist",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["approval_checklist"])
    lines.extend(["", "## Blocked until", ""])
    lines.extend(f"- `{item}`" for item in payload["blocked_until"]) if payload["blocked_until"] else lines.append("- none")
    lines.extend([
        "",
        "## Execution command shape",
        "",
        "```bash",
        payload["execution_command_shape"],
        "```",
        "",
        "## Non-claims",
        "",
    ])
    lines.extend(f"- {claim}" for claim in payload["non_claims"])
    lines.append("")
    return "\n".join(lines)


def _markdown(plan: dict[str, Any], result: dict[str, Any]) -> str:
    case = result["case_evidence"]
    state = result["execution_state"]
    lines = [
        "# Approved Context Replay v1",
        "",
        result["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Case: `{case['case_id']}`",
        f"- Method class: `{case['method_class']}`",
        f"- Path template: `{case['path_template']}`",
        f"- Execution mode: `{case['execution_mode']}`",
        f"- Context ready: `{state['context_ready']}`",
        f"- Execution approved: `{state['execution_approved']}`",
        f"- Execute requested: `{state['execute_requested']}`",
        f"- Executed: `{state['executed']}`",
        f"- Validated: `{state['validated']}`",
        f"- Release approved: `{state['release_approved']}`",
        f"- Result class: `{result['result_class']}`",
        f"- HTTP status family: `{result['http_status_family']}`",
        f"- Replay failure category: `{result['replay_failure_category']}`",
        f"- Approval supplied: `{result['approval_scope']['approval_supplied']}`",
        f"- Explicit case scope present: `{result['approval_scope']['explicit_case_scope_present']}`",
        f"- Explicit execution-mode scope present: `{result['approval_scope']['explicit_execution_mode_scope_present']}`",
        f"- Requested case in scope: `{result['approval_scope']['requested_case_in_scope']}`",
        f"- Requested execution mode in scope: `{result['approval_scope']['requested_execution_mode_in_scope']}`",
        f"- Confirmed security finding: `{result['confirmed_security_finding']}`",
        f"- Release gate override: `{result['release_gate_override']}`",
        "",
        "## Blocked reasons",
        "",
    ]
    lines.extend(f"- `{reason}`" for reason in result["blocked_reasons"]) if result["blocked_reasons"] else lines.append("- none")
    lines.extend([
        "",
        "## Required approvals",
        "",
    ])
    lines.extend(f"- `{item}`" for item in plan["required_approvals"])
    lines.extend([
        "",
        "## State model",
        "",
        "- `context_ready` is not execution proof.",
        "- `execution_approved` is not execution proof.",
        "- `executed` is not validation.",
        "- `validated` is not release approval.",
        "",
        "## Non-claims",
        "",
    ])
    lines.extend(f"- {claim}" for claim in result["non_claims"])
    lines.append("")
    return "\n".join(lines)
