from __future__ import annotations

from typing import Any

from adapters.live_replay.workflow_bindings import applied_response_binding_count, declared_response_binding_count


AUTH_HEADER_NAMES = {"authorization", "cookie", "x-api-key", "x-token", "x-sign"}
REVIEW_GAP_REASONS = {"missing_auth_context", "missing_write_context", "binding_review_required"}
CONTEXT_CONTRACT_REASONS = {
    "auth_header_family_mismatch",
    "host_continuity_mismatch",
    "target_env_mismatch",
    "prior_step_missing",
    "response_binding_missing",
    "response_binding_target_missing",
}
RUNTIME_FAILURE_REASONS = {"url_error", "http_error", "timeout", "stream_open_partial_read"}


def summarize_workflow_requirements(workflows: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    class_counts: dict[str, int] = {}
    required_header_families: dict[str, int] = {}
    for workflow in workflows:
        context = workflow.get("workflow_context_requirements", {})
        workflow_class = str(context.get("workflow_class", "unknown"))
        class_counts[workflow_class] = class_counts.get(workflow_class, 0) + 1
        for family in context.get("required_header_families", []):
            name = str(family)
            required_header_families[name] = required_header_families.get(name, 0) + 1
    return {
        "workflow_class_counts": class_counts,
        "same_host_continuity_required_count": _count(workflows, "workflow_context_requirements", "same_host_continuity_required"),
        "same_target_env_required_count": _count(workflows, "workflow_context_requirements", "same_target_env_required"),
        "shared_auth_context_required_count": _count(workflows, "session_context_requirements", "shared_auth_context_required"),
        "same_auth_context_required_count": _count(workflows, "session_context_requirements", "same_auth_context_required"),
        "approved_auth_context_required_count": _count(workflows, "session_context_requirements", "approved_auth_context_required"),
        "shared_write_context_required_count": _count(workflows, "session_context_requirements", "shared_write_context_required"),
        "same_write_context_required_count": _count(workflows, "session_context_requirements", "same_write_context_required"),
        "approved_write_context_required_count": _count(workflows, "session_context_requirements", "approved_write_context_required"),
        "auth_header_contract_required_count": sum(1 for workflow in workflows if workflow.get("session_context_requirements", {}).get("required_auth_header_names")),
        "declared_response_binding_count": declared_response_binding_count(workflows),
        "applied_response_binding_count": applied_response_binding_count(results),
        "inferred_response_binding_count": _review_count(workflows, "inferred_response_binding_count"),
        "approved_response_binding_count": _review_count(workflows, "approved_response_binding_count"),
        "pending_review_response_binding_count": _review_count(workflows, "pending_review_response_binding_count"),
        "rejected_response_binding_count": _review_count(workflows, "rejected_response_binding_count"),
        "replaced_response_binding_count": _review_count(workflows, "replaced_response_binding_count"),
        "required_header_family_counts": required_header_families,
        "context_contract_failure_counts": _failure_counts(results),
        "failure_class_counts": _failure_class_counts(results),
    }


def validate_workflow_context(
    workflow: dict[str, Any],
    auth_payload: dict[str, Any] | None,
    write_payload: dict[str, Any] | None,
    cases: dict[str, dict[str, Any]],
) -> tuple[str, str] | None:
    session = workflow.get("session_context_requirements", {})
    context = workflow.get("workflow_context_requirements", {})
    if session.get("approved_auth_context_required") and not bool(auth_payload and auth_payload.get("approved")):
        return ("missing_auth_context", workflow.get("workflow_id", "unknown"))
    if session.get("approved_write_context_required") and not bool(write_payload and write_payload.get("approved")):
        return ("missing_write_context", workflow.get("workflow_id", "unknown"))
    auth_header_check = _validate_auth_header_contract(session, context, auth_payload)
    if auth_header_check is not None:
        return auth_header_check
    if context.get("same_host_continuity_required"):
        expected_hosts = [str(host) for host in context.get("expected_hosts", []) if str(host).strip()]
        actual_hosts = sorted({step_host(step, cases) for step in workflow.get("steps", []) if step_host(step, cases)})
        if actual_hosts != expected_hosts:
            return ("host_continuity_mismatch", f"expected={expected_hosts};actual={actual_hosts}")
    if context.get("same_target_env_required"):
        expected_envs = [str(env) for env in context.get("expected_target_envs", []) if str(env).strip()]
        actual_envs = sorted({_step_env(step, cases) for step in workflow.get("steps", []) if _step_env(step, cases)})
        if actual_envs != expected_envs:
            return ("target_env_mismatch", f"expected={expected_envs};actual={actual_envs}")
    return None


def step_block_reason(step: dict[str, Any]) -> str:
    requirements = step.get("step_context_requirements", {})
    if requirements.get("auth_context_required"):
        return "missing_auth_context"
    if requirements.get("write_context_required"):
        return "missing_write_context"
    return "step_not_executable"


def step_host(step: dict[str, Any], cases: dict[str, dict[str, Any]]) -> str:
    case = cases.get(str(step.get("case_id")), {})
    step_expected = str(step.get("step_context_requirements", {}).get("expected_host", "")).strip()
    return step_expected or str(case.get("request_blueprint", {}).get("host", "")).strip()


def _step_env(step: dict[str, Any], cases: dict[str, dict[str, Any]]) -> str:
    case = cases.get(str(step.get("case_id")), {})
    return str(step.get("target_env") or case.get("target_env") or "").strip()


def _validate_auth_header_contract(
    session: dict[str, Any],
    context: dict[str, Any],
    auth_payload: dict[str, Any] | None,
) -> tuple[str, str] | None:
    if "auth" not in {str(name) for name in context.get("required_header_families", [])}:
        return None
    required_names = {str(name).lower() for name in session.get("required_auth_header_names", []) if str(name).strip()}
    if not required_names or not auth_payload or not auth_payload.get("approved"):
        return None
    allowed_names = {str(name).lower() for name in auth_payload.get("allowed_header_names", []) if str(name).strip()}
    if required_names.issubset(allowed_names):
        return None
    return ("auth_header_family_mismatch", f"required={sorted(required_names)};allowed={sorted(allowed_names)}")


def _count(workflows: list[dict[str, Any]], section: str, key: str) -> int:
    return sum(1 for workflow in workflows if workflow.get(section, {}).get(key))


def _review_count(workflows: list[dict[str, Any]], key: str) -> int:
    return sum(int(step.get("binding_review_summary", {}).get(key, 0)) for workflow in workflows for step in workflow.get("steps", []))


def _failure_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        reason = str(result.get("failure_reason_code", "")).strip()
        if reason not in REVIEW_GAP_REASONS | CONTEXT_CONTRACT_REASONS:
            continue
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def summarize_failure_classes(results: list[dict[str, Any]]) -> dict[str, int]:
    return _failure_class_counts(results)


def _failure_class_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"review_gap": 0, "context_contract_failure": 0, "runtime_failure": 0, "other_failure": 0}
    for result in results:
        reason = str(result.get("failure_reason_code", "")).strip()
        if not reason:
            continue
        if reason in REVIEW_GAP_REASONS:
            counts["review_gap"] += 1
        elif reason in CONTEXT_CONTRACT_REASONS:
            counts["context_contract_failure"] += 1
        elif reason in RUNTIME_FAILURE_REASONS or reason.startswith("http_status_"):
            counts["runtime_failure"] += 1
        else:
            counts["other_failure"] += 1
    return {key: value for key, value in counts.items() if value > 0}
