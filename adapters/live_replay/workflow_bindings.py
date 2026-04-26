from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urlsplit, urlunsplit


SUPPORTED_BINDING_SOURCES = {"response_json", "response_header"}
SUPPORTED_BINDING_TARGETS = {"request_url", "request_path", "request_body_json", "request_header"}


def extract_response_binding_values(
    workflow: dict[str, Any],
    source_case_id: str,
    result: dict[str, Any],
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    values: dict[str, str] = {}
    extracted: list[dict[str, Any]] = []
    for step in workflow.get("steps", []):
        for binding in step.get("response_bindings", []):
            if str(binding.get("source_case_id")) != source_case_id:
                continue
            binding_id = str(binding.get("binding_id", "")).strip()
            value = _extract_binding_value(binding, result)
            if not binding_id or value is None:
                continue
            values[binding_id] = value
            extracted.append(
                {
                    "binding_id": binding_id,
                    "source_case_id": source_case_id,
                    "source_type": binding.get("source_type"),
                    "source_key": binding.get("source_key"),
                    "value_preview": value[:120],
                }
            )
    return values, extracted


def apply_response_bindings(
    case: dict[str, Any],
    step: dict[str, Any],
    workflow_state: dict[str, Any],
    approved_write_body_json: dict[str, Any] | None = None,
    approved_write_headers: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], tuple[str, str] | None]:
    bindings = step.get("response_bindings", [])
    if not bindings:
        return case, [], None
    bound_case = deepcopy(case)
    request_blueprint = bound_case.setdefault("request_blueprint", {})
    request_url = str(step.get("request_url_template") or request_blueprint.get("url", ""))
    request_path = str(bound_case.get("path", ""))
    request_body_json = deepcopy(request_blueprint.get("body_json"))
    if request_body_json is None and isinstance(approved_write_body_json, dict):
        request_body_json = deepcopy(approved_write_body_json)
        
    request_headers = deepcopy(request_blueprint.get("headers", {}))
    if isinstance(approved_write_headers, dict):
        for k, v in approved_write_headers.items():
            if k not in request_headers:
                request_headers[k] = v
    request_blueprint["headers"] = request_headers
    applied: list[dict[str, Any]] = []
    binding_values = workflow_state.get("response_binding_values", {})
    for binding in bindings:
        binding_id = str(binding.get("binding_id", "")).strip()
        target_field = str(binding.get("target_field", "")).strip()
        placeholder = str(binding.get("placeholder", "")).strip()
        required = bool(binding.get("required", True))
        if target_field not in SUPPORTED_BINDING_TARGETS:
            continue
        value = str(binding_values.get(binding_id, "")).strip()
        if not value:
            if required:
                return None, applied, ("response_binding_missing", binding_id)
            continue
        if target_field == "request_url":
            if placeholder not in request_url:
                if required:
                    return None, applied, ("response_binding_target_missing", binding_id)
                continue
            request_url = request_url.replace(placeholder, value)
        elif target_field == "request_path":
            request_url, request_path, error = _apply_request_path_binding(request_url, request_path, placeholder, value, required, binding_id)
            if error is not None:
                return None, applied, error
        elif target_field == "request_body_json":
            target_path = str(binding.get("target_path", "")).strip()
            if not target_path or not _set_json_path_value(request_body_json, target_path, value):
                if required:
                    return None, applied, ("response_binding_target_missing", binding_id)
                continue
        elif target_field == "request_header":
            target_path = str(binding.get("target_path", "")).strip().lower()
            if not target_path:
                continue
            request_blueprint.setdefault("headers", {})
            header_value = request_blueprint["headers"].get(target_path, "")
            if placeholder and placeholder in header_value:
                request_blueprint["headers"][target_path] = header_value.replace(placeholder, value)
            else:
                request_blueprint["headers"][target_path] = value
        applied.append(
            {
                "binding_id": binding_id,
                "source_case_id": binding.get("source_case_id"),
                "source_type": binding.get("source_type"),
                "source_key": binding.get("source_key"),
                "target_field": target_field,
                "placeholder": placeholder,
                "target_path": binding.get("target_path"),
                "required": bool(binding.get("required", True)),
                "inferred": bool(binding.get("inferred", False)),
                "confidence": binding.get("confidence"),
                "inference_reason": binding.get("inference_reason"),
                "review_status": binding.get("review_status"),
                "value_preview": value[:120],
            }
        )
    bound_case["path"] = request_path
    request_blueprint["url"] = request_url
    if request_body_json is not None:
        request_blueprint["body_json"] = request_body_json
    return bound_case, applied, None


def binding_review_required(step: dict[str, Any]) -> bool:
    return any(str(binding.get("review_status", "approved")) != "approved" for binding in step.get("response_bindings", []))


def planned_response_binding_records(step: dict[str, Any]) -> list[dict[str, Any]]:
    return [_binding_contract_record(binding) for binding in step.get("response_bindings", [])]


def binding_application_summary(
    planned_response_bindings: list[dict[str, Any]] | None,
    applied_response_bindings: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    planned = planned_response_bindings or []
    applied = applied_response_bindings or []
    applied_ids = {str(binding.get("binding_id", "")) for binding in applied if str(binding.get("binding_id", "")).strip()}
    planned_ids = [str(binding.get("binding_id", "")) for binding in planned if str(binding.get("binding_id", "")).strip()]
    return {
        "planned_response_binding_count": len(planned),
        "approved_planned_response_binding_count": sum(1 for binding in planned if str(binding.get("review_status", "")) == "approved"),
        "pending_review_planned_response_binding_count": sum(1 for binding in planned if str(binding.get("review_status", "")) == "pending_review"),
        "applied_response_binding_count": len(applied),
        "unapplied_response_binding_count": len([binding_id for binding_id in planned_ids if binding_id not in applied_ids]),
        "applied_binding_ids": sorted(applied_ids),
        "unapplied_binding_ids": [binding_id for binding_id in planned_ids if binding_id not in applied_ids],
    }


def summarize_binding_applications(
    workflows: list[dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    planned = declared_response_binding_count(workflows)
    applied = applied_response_binding_count(results)
    workflows_with_planned = {
        str(workflow.get("workflow_id", "unknown"))
        for workflow in workflows
        if any(step.get("response_bindings") for step in workflow.get("steps", []))
    }
    workflows_with_applied = {
        str(result.get("workflow_id", "unknown"))
        for result in results
        if any(step.get("workflow_evidence", {}).get("applied_response_bindings") for step in result.get("results", []))
    }
    failure_counts: dict[str, int] = {}
    failed_binding_ids: list[str] = []
    for result in results:
        reason = str(result.get("failure_reason_code", "")).strip()
        if not reason.startswith("response_binding_"):
            continue
        failure_counts[reason] = failure_counts.get(reason, 0) + 1
        failed_binding_id = str(result.get("failure_detail", "")).strip()
        if failed_binding_id:
            failed_binding_ids.append(failed_binding_id)
    return {
        "planned_response_binding_count": planned,
        "applied_response_binding_count": applied,
        "unapplied_response_binding_count": max(planned - applied, 0),
        "workflow_count_with_planned_bindings": len(workflows_with_planned),
        "workflow_count_with_applied_bindings": len(workflows_with_applied),
        "binding_application_failure_counts": failure_counts,
        "failed_binding_ids": failed_binding_ids,
    }


def declared_response_binding_count(workflows: list[dict[str, Any]]) -> int:
    return sum(len(step.get("response_bindings", [])) for workflow in workflows for step in workflow.get("steps", []))


def applied_response_binding_count(results: list[dict[str, Any]]) -> int:
    return sum(len(step.get("workflow_evidence", {}).get("applied_response_bindings", [])) for result in results for step in result.get("results", []))


def _binding_contract_record(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "binding_id": binding.get("binding_id"),
        "source_case_id": binding.get("source_case_id"),
        "source_type": binding.get("source_type"),
        "source_key": binding.get("source_key"),
        "target_field": binding.get("target_field"),
        "placeholder": binding.get("placeholder"),
        "target_path": binding.get("target_path"),
        "required": bool(binding.get("required", True)),
        "inferred": bool(binding.get("inferred", False)),
        "confidence": binding.get("confidence"),
        "inference_reason": binding.get("inference_reason"),
        "review_status": binding.get("review_status"),
    }


def _apply_request_path_binding(
    request_url: str,
    request_path: str,
    placeholder: str,
    value: str,
    required: bool,
    binding_id: str,
) -> tuple[str, str, tuple[str, str] | None]:
    path_target = request_path
    if placeholder in path_target:
        path_target = path_target.replace(placeholder, value)
        return _replace_url_path(request_url, placeholder, value), path_target, None
    if placeholder in request_url:
        replaced_url = _replace_url_path(request_url, placeholder, value)
        replaced_path = urlsplit(replaced_url).path or request_path
        return replaced_url, replaced_path, None
    if required:
        return request_url, request_path, ("response_binding_target_missing", binding_id)
    return request_url, request_path, None


def _replace_url_path(request_url: str, placeholder: str, value: str) -> str:
    parsed = urlsplit(request_url)
    replaced_path = parsed.path.replace(placeholder, value)
    return urlunsplit((parsed.scheme, parsed.netloc, replaced_path, parsed.query, parsed.fragment))


def _set_json_path_value(payload: Any, dotted_path: str, value: str) -> bool:
    if not isinstance(payload, dict):
        return False
    current = payload
    parts = dotted_path.split(".")
    for part in parts[:-1]:
        nested = current.get(part)
        if not isinstance(nested, dict):
            return False
        current = nested
    leaf = parts[-1]
    if leaf not in current:
        return False
    current[leaf] = value
    return True


def _extract_binding_value(binding: dict[str, Any], result: dict[str, Any]) -> str | None:
    source_type = str(binding.get("source_type", "")).strip()
    source_key = str(binding.get("source_key", "")).strip()
    if source_type not in SUPPORTED_BINDING_SOURCES or not source_key:
        return None
    if source_type == "response_json":
        return _json_path_value(result.get("response_json"), source_key)
    response_headers = result.get("response_headers", {})
    value = response_headers.get(source_key.lower())
    return None if value is None else str(value)


def _json_path_value(payload: Any, dotted_path: str) -> str | None:
    current = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if isinstance(current, (str, int, float, bool)):
        return str(current)
    return None
