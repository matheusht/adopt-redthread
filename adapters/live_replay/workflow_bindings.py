from __future__ import annotations

from copy import deepcopy
from typing import Any


SUPPORTED_BINDING_SOURCES = {"response_json", "response_header"}
SUPPORTED_BINDING_TARGETS = {"request_url", "request_body_json"}


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
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], tuple[str, str] | None]:
    bindings = step.get("response_bindings", [])
    if not bindings:
        return case, [], None
    bound_case = deepcopy(case)
    request_blueprint = bound_case.setdefault("request_blueprint", {})
    request_url = str(step.get("request_url_template") or request_blueprint.get("url", ""))
    request_body_json = deepcopy(request_blueprint.get("body_json"))
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
        elif target_field == "request_body_json":
            target_path = str(binding.get("target_path", "")).strip()
            if not target_path or not _set_json_path_value(request_body_json, target_path, value):
                if required:
                    return None, applied, ("response_binding_target_missing", binding_id)
                continue
        applied.append(
            {
                "binding_id": binding_id,
                "source_case_id": binding.get("source_case_id"),
                "target_field": target_field,
                "placeholder": placeholder,
                "target_path": binding.get("target_path"),
                "review_status": binding.get("review_status"),
                "value_preview": value[:120],
            }
        )
    request_blueprint["url"] = request_url
    if request_body_json is not None:
        request_blueprint["body_json"] = request_body_json
    return bound_case, applied, None


def binding_review_required(step: dict[str, Any]) -> bool:
    return any(str(binding.get("review_status", "approved")) != "approved" for binding in step.get("response_bindings", []))


def declared_response_binding_count(workflows: list[dict[str, Any]]) -> int:
    return sum(len(step.get("response_bindings", [])) for workflow in workflows for step in workflow.get("steps", []))


def applied_response_binding_count(results: list[dict[str, Any]]) -> int:
    return sum(len(step.get("workflow_evidence", {}).get("applied_response_bindings", [])) for result in results for step in result.get("results", []))


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
