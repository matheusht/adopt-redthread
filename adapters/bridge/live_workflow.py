from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from adapters.bridge.workflow_binding_plan import build_step, load_approved_aliases, load_binding_overrides


SUPPORTED_WORKFLOW_MODES = {
    "live_safe_read",
    "live_safe_read_with_approved_auth",
    "live_reviewed_write_staging",
}


def build_live_workflow_plan(
    live_attack_plan: dict[str, Any],
    binding_overrides: dict[str, Any] | str | Path | None = None,
    approved_binding_aliases: dict[str, Any] | str | Path | None = None,
) -> dict[str, Any]:
    overrides = load_binding_overrides(binding_overrides)
    approved_aliases = load_approved_aliases(approved_binding_aliases)
    workflows = [
        _build_workflow(group, cases, overrides, approved_aliases)
        for group, cases in _group_cases(live_attack_plan).items()
        if len(cases) > 1
    ]
    return {
        "plan_id": f"{live_attack_plan.get('plan_id', 'unknown')}-workflows",
        "source": live_attack_plan.get("source", "unknown"),
        "input_file": live_attack_plan.get("input_file", "unknown"),
        "workflow_count": len(workflows),
        "state_model": "bounded_evidence_carry_forward",
        "approved_binding_alias_count": len(approved_aliases),
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


def _build_workflow(
    group: str,
    cases: list[dict[str, Any]],
    overrides: dict[str, Any],
    approved_aliases: list[dict[str, Any]],
) -> dict[str, Any]:
    executable_step_count = sum(1 for case in cases if case.get("execution_mode") in SUPPORTED_WORKFLOW_MODES)
    review_required = any(not case.get("allowed") for case in cases)
    hosts = sorted({host for host in (_case_host(case) for case in cases) if host})
    target_envs = sorted({str(case.get("target_env", "")).strip() for case in cases if str(case.get("target_env", "")).strip()})
    required_header_families = _required_header_families(cases)
    steps = [build_step(case, cases, overrides, _case_host(case), approved_aliases) for case in cases]
    return {
        "workflow_id": group,
        "step_count": len(cases),
        "executable_step_count": executable_step_count,
        "review_required": review_required,
        "abort_rule": "stop_on_first_failure",
        "workflow_context_requirements": {
            "workflow_class": _workflow_class(cases),
            "same_host_continuity_required": len(hosts) == 1,
            "expected_hosts": hosts,
            "same_target_env_required": len(target_envs) == 1 and len(cases) > 1,
            "expected_target_envs": target_envs,
            "required_header_families": required_header_families,
            "prior_step_success_required": any(int(case.get("workflow_step_index", 0)) > 0 for case in cases),
            "response_binding_contract": {
                "mode": "declared_allowlist",
                "supported_sources": ["response_json", "response_header"],
                "supported_targets": ["request_url", "request_path", "request_body_json"],
                "declared_binding_count": sum(len(step.get("response_bindings", [])) for step in steps),
            },
            "dependency_contract": {
                "mode": "linear_previous_step_success",
                "required_predecessor_case_ids": _required_predecessors(cases),
            },
        },
        "session_context_requirements": {
            "shared_auth_context_required": any(case.get("execution_mode") == "live_safe_read_with_approved_auth" for case in cases),
            "same_auth_context_required": any(case.get("execution_mode") == "live_safe_read_with_approved_auth" for case in cases),
            "approved_auth_context_required": any(case.get("execution_mode") == "live_safe_read_with_approved_auth" for case in cases),
            "shared_write_context_required": any(case.get("execution_mode") == "live_reviewed_write_staging" for case in cases),
            "same_write_context_required": any(case.get("execution_mode") == "live_reviewed_write_staging" for case in cases),
            "approved_write_context_required": any(case.get("execution_mode") == "live_reviewed_write_staging" for case in cases),
            "required_auth_header_names": _required_auth_header_names(cases),
        },
        "state_contract": {
            "carry_forward": [
                "completed_case_ids",
                "observed_hosts",
                "response_json_keys",
                "last_case_id",
                "last_status_code",
                "auth_applied_any",
                "response_binding_values",
                "binding_source_case_ids",
            ],
            "evidence_capture": ["status_code", "content_type", "auth_applied", "response_json_keys", "extracted_response_bindings", "applied_response_bindings"],
        },
        "steps": steps,
    }


def _workflow_class(cases: list[dict[str, Any]]) -> str:
    modes = {str(case.get("execution_mode", "")) for case in cases}
    if "live_reviewed_write_staging" in modes:
        return "reviewed_write_workflow"
    if "live_safe_read_with_approved_auth" in modes:
        return "auth_safe_read_workflow"
    return "safe_read_workflow"


def _required_predecessors(cases: list[dict[str, Any]]) -> dict[str, list[str]]:
    predecessors: dict[str, list[str]] = {}
    ordered = sorted(cases, key=lambda case: int(case.get("workflow_step_index", 0)))
    for index, case in enumerate(ordered):
        if index == 0:
            continue
        predecessors[str(case.get("case_id"))] = [str(ordered[index - 1].get("case_id"))]
    return predecessors


def _required_header_families(cases: list[dict[str, Any]]) -> list[str]:
    families = set()
    for case in cases:
        headers = {str(name).lower() for name in case.get("request_blueprint", {}).get("header_names", [])}
        if headers & {"authorization", "cookie", "x-api-key", "x-token", "x-sign"}:
            families.add("auth")
    return sorted(families)


def _required_auth_header_names(cases: list[dict[str, Any]]) -> list[str]:
    names = set()
    for case in cases:
        for name in case.get("request_blueprint", {}).get("header_names", []):
            lowered = str(name).lower()
            if lowered in {"authorization", "cookie", "x-api-key", "x-token", "x-sign"}:
                names.add(lowered)
    return sorted(names)


def _case_host(case: dict[str, Any]) -> str:
    blueprint = case.get("request_blueprint", {})
    host = str(blueprint.get("host", "")).strip()
    if host:
        return host
    return urlparse(str(blueprint.get("url", "")).strip()).netloc
