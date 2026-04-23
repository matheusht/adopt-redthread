from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from adapters.bridge.binding_alias_table import reverse_alias_lookup
from adapters.bridge.workflow_binding_candidates import (
    _flatten_json_paths,
    discover_candidate_bindings,
    discover_candidate_path_bindings,
)


def infer_step_bindings(
    case: dict[str, Any],
    source_case: dict[str, Any],
    approved_aliases: list[dict[str, Any]] | None = None,
) -> tuple[str | None, list[dict[str, Any]]]:
    request_url_template, query_bindings = infer_query_bindings(case, source_case)
    body_bindings = infer_body_json_bindings(case, source_case, approved_aliases)
    return request_url_template, query_bindings + body_bindings


def infer_query_bindings(case: dict[str, Any], source_case: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    url = str(case.get("request_blueprint", {}).get("url", "")).strip()
    if not url:
        return None, []
    parsed = urlsplit(url)
    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    if not query_pairs:
        return None, []
    bindings: list[dict[str, Any]] = []
    next_pairs: list[tuple[str, str]] = []
    for name, value in query_pairs:
        if not looks_like_binding_key(name, value):
            next_pairs.append((name, value))
            continue
        binding_id = f"{name}_from_{source_case.get('case_id')}"
        placeholder = "{{" + binding_id + "}}"
        bindings.append(
            inferred_binding(
                binding_id=binding_id,
                source_case_id=str(source_case.get("case_id")),
                source_key=name,
                target_field="request_url",
                placeholder=placeholder,
                inference_reason=f"query_param:{name}:previous_step_json",
            )
        )
        next_pairs.append((name, placeholder))
    if not bindings:
        return None, []
    query = urlencode(next_pairs, doseq=True)
    for binding in bindings:
        placeholder = str(binding["placeholder"])
        query = query.replace(encoded_placeholder(placeholder), placeholder)
    template = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))
    return template, bindings


def infer_body_json_bindings(
    case: dict[str, Any],
    source_case: dict[str, Any],
    approved_aliases: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    body_json = case.get("request_blueprint", {}).get("body_json")
    if not isinstance(body_json, dict):
        return []
    bindings: list[dict[str, Any]] = []
    for dotted_path, field_name, sample in body_json_field_candidates(body_json):
        source_key, reason, review_status = inferred_body_source_key(field_name, sample, approved_aliases)
        if not source_key or not reason:
            continue
        bindings.append(
            inferred_binding(
                binding_id=f"{field_name}_body_from_{source_case.get('case_id')}",
                source_case_id=str(source_case.get("case_id")),
                source_key=source_key,
                target_field="request_body_json",
                target_path=dotted_path,
                inference_reason=f"body_json_field:{dotted_path}:{reason}",
                review_status=review_status,
            )
        )
    return bindings


def body_json_field_candidates(payload: dict[str, Any], prefix: str = "") -> list[tuple[str, str, str]]:
    candidates: list[tuple[str, str, str]] = []
    for key, value in payload.items():
        dotted = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            candidates.extend(body_json_field_candidates(value, dotted))
            continue
        if isinstance(value, (str, int, float, bool)):
            candidates.append((dotted, str(key), str(value)))
    return candidates


def inferred_binding(
    *,
    binding_id: str,
    source_case_id: str,
    source_key: str,
    target_field: str,
    inference_reason: str,
    placeholder: str | None = None,
    target_path: str | None = None,
    review_status: str = "pending_review",
) -> dict[str, Any]:
    binding = {
        "binding_id": binding_id,
        "source_case_id": source_case_id,
        "source_type": "response_json",
        "source_key": source_key,
        "target_field": target_field,
        "required": True,
        "inference_reason": inference_reason,
        "confidence": "low",
        "inferred": True,
        "review_status": review_status,
    }
    if placeholder:
        binding["placeholder"] = placeholder
    if target_path:
        binding["target_path"] = target_path
    return binding


def looks_like_binding_key(name: str, value: str) -> bool:
    lowered = str(name).lower()
    if lowered not in {"id"} and not lowered.endswith("_id"):
        return False
    return looks_like_binding_sample(value)


def looks_like_binding_sample(value: str) -> bool:
    raw = str(value).strip()
    if not raw or "{{" in raw or len(raw) < 3:
        return False
    return any(char.isdigit() for char in raw) or "-" in raw or "_" in raw


def inferred_body_source_key(
    field_name: str,
    sample: str,
    approved_aliases: list[dict[str, Any]] | None = None,
) -> tuple[str | None, str | None, str]:
    if looks_like_binding_key(field_name, sample):
        return field_name, "previous_step_json", "pending_review"
    if not looks_like_binding_sample(sample):
        return None, None, "pending_review"
    candidates = reverse_alias_lookup(field_name, approved_aliases)
    if not candidates:
        return None, None, "pending_review"
    source_key, tier = candidates[0]
    if source_key == field_name and tier == "exact_name_match":
        return None, None, "pending_review"
    review_status = "approved" if tier == "reviewed_pattern" else "pending_review"
    return source_key, f"previous_step_json:{tier}", review_status


def encoded_placeholder(placeholder: str) -> str:
    return urlencode({"x": placeholder}).removeprefix("x=")


__all__ = [
    "_flatten_json_paths",
    "body_json_field_candidates",
    "discover_candidate_bindings",
    "discover_candidate_path_bindings",
    "infer_step_bindings",
]
