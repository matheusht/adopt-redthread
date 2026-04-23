from __future__ import annotations

import re
from typing import Any

from adapters.bridge.binding_alias_table import alias_lookup


# ---------------------------------------------------------------------------
# Phase A1 — Response-to-Request Field Matching
# ---------------------------------------------------------------------------

def discover_candidate_bindings(
    step_n_response_json: dict[str, Any] | None,
    step_n1_case: dict[str, Any],
    source_case_id: str,
    target_case_id: str,
) -> list[dict[str, Any]]:
    if not isinstance(step_n_response_json, dict):
        return []

    response_paths = _flatten_json_paths(step_n_response_json)
    if not response_paths:
        return []

    body_json = step_n1_case.get("request_blueprint", {}).get("body_json")
    body_paths: set[str] = set()
    if isinstance(body_json, dict):
        body_paths = _body_json_leaf_names(body_json)

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for source_key, _value in response_paths:
        for target_path, tier in alias_lookup(source_key):
            if target_path.startswith("query."):
                target_field = "request_url"
                actual_target_path = target_path[len("query."):]
            else:
                target_field = "request_body_json"
                actual_target_path = target_path
            if body_paths and target_field == "request_body_json" and actual_target_path not in body_paths:
                continue
            dedup_key = (source_key, target_field, actual_target_path)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)
            candidates.append(
                {
                    "source_case_id": source_case_id,
                    "source_key": source_key,
                    "target_case_id": target_case_id,
                    "target_field": target_field,
                    "target_path": actual_target_path,
                    "confidence_tier": tier,
                    "reason": f"{tier}:{source_key}->{actual_target_path}",
                    "candidate_type": "response_to_request_body",
                }
            )
    return candidates


# ---------------------------------------------------------------------------
# Phase A3 — Path Slot Matching
# ---------------------------------------------------------------------------

_SLOT_PATTERN = re.compile(r"\{([^}]+)\}")


def discover_candidate_path_bindings(
    step_n_response_json: dict[str, Any] | None,
    step_n1_url_template: str,
    source_case_id: str,
    target_case_id: str,
) -> list[dict[str, Any]]:
    slots = _SLOT_PATTERN.findall(step_n1_url_template)
    if not slots:
        return []
    if not isinstance(step_n_response_json, dict):
        return [_unmatched_slot(slot, source_case_id, target_case_id, "no_response_json_available") for slot in slots]

    response_paths = _flatten_json_paths(step_n_response_json)
    if not response_paths:
        return [_unmatched_slot(slot, source_case_id, target_case_id, "empty_response_json") for slot in slots]

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for slot in slots:
        matched = False
        for source_key, _value in response_paths:
            for target_path, tier in alias_lookup(source_key):
                if target_path != slot:
                    continue
                dedup = (slot, source_key)
                if dedup in seen:
                    continue
                seen.add(dedup)
                candidates.append(
                    {
                        "source_case_id": source_case_id,
                        "source_key": source_key,
                        "target_case_id": target_case_id,
                        "target_field": "request_path",
                        "slot": slot,
                        "placeholder": "{" + slot + "}",
                        "confidence_tier": tier,
                        "reason": f"{tier}:{source_key}->{{{slot}}}",
                        "candidate_type": "path_slot_match",
                    }
                )
                matched = True
                break
            if matched:
                break
        if not matched:
            candidates.append(_unmatched_slot(slot, source_case_id, target_case_id, "no_source_found"))
    return candidates


def _unmatched_slot(slot: str, source_case_id: str, target_case_id: str, reason_suffix: str) -> dict[str, Any]:
    return {
        "source_case_id": source_case_id,
        "source_key": None,
        "target_case_id": target_case_id,
        "target_field": "request_path",
        "slot": slot,
        "placeholder": "{" + slot + "}",
        "confidence_tier": "unmatched",
        "reason": f"unmatched:{reason_suffix}_for_{{{slot}}}",
        "candidate_type": "path_slot_match",
    }


def _body_json_leaf_names(payload: dict[str, Any], prefix: str = "") -> set[str]:
    names: set[str] = set()
    for key, value in payload.items():
        dotted = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            names.update(_body_json_leaf_names(value, dotted))
        elif isinstance(value, (str, int, float, bool)):
            names.add(str(key))
            names.add(dotted)
    return names


def _flatten_json_paths(payload: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if not isinstance(payload, dict):
        return []
    results: list[tuple[str, Any]] = []
    for key, value in payload.items():
        dotted = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            results.extend(_flatten_json_paths(value, dotted))
        elif isinstance(value, list):
            continue
        elif isinstance(value, (str, int, float, bool)) or value is None:
            results.append((dotted, value))
    return results


__all__ = ["discover_candidate_bindings", "discover_candidate_path_bindings", "_flatten_json_paths"]
