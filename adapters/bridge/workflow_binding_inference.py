from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from adapters.bridge.binding_alias_table import alias_lookup


def infer_step_bindings(case: dict[str, Any], source_case: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    request_url_template, query_bindings = infer_query_bindings(case, source_case)
    body_bindings = infer_body_json_bindings(case, source_case)
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


def infer_body_json_bindings(case: dict[str, Any], source_case: dict[str, Any]) -> list[dict[str, Any]]:
    body_json = case.get("request_blueprint", {}).get("body_json")
    if not isinstance(body_json, dict):
        return []
    bindings: list[dict[str, Any]] = []
    for dotted_path, field_name, sample in body_json_field_candidates(body_json):
        if not looks_like_binding_key(field_name, sample):
            continue
        bindings.append(
            inferred_binding(
                binding_id=f"{field_name}_body_from_{source_case.get('case_id')}",
                source_case_id=str(source_case.get("case_id")),
                source_key=field_name,
                target_field="request_body_json",
                target_path=dotted_path,
                inference_reason=f"body_json_field:{dotted_path}:previous_step_json",
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
        "review_status": "pending_review",
    }
    if placeholder:
        binding["placeholder"] = placeholder
    if target_path:
        binding["target_path"] = target_path
    return binding


def looks_like_binding_key(name: str, value: str) -> bool:
    lowered = str(name).lower()
    raw = str(value).strip()
    if lowered not in {"id"} and not lowered.endswith("_id"):
        return False
    if not raw or "{{" in raw or len(raw) < 3:
        return False
    return any(char.isdigit() for char in raw) or "-" in raw or "_" in raw


def encoded_placeholder(placeholder: str) -> str:
    return urlencode({"x": placeholder}).removeprefix("x=")


# ---------------------------------------------------------------------------
# Phase A1 — Response-to-Request Field Matching
# ---------------------------------------------------------------------------

def discover_candidate_bindings(
    step_n_response_json: dict[str, Any] | None,
    step_n1_case: dict[str, Any],
    source_case_id: str,
    target_case_id: str,
) -> list[dict[str, Any]]:
    """Propose candidate bindings from step N response JSON into step N+1 request.

    Candidates are proposals only — they go into the review manifest, never
    into response_bindings of any step.

    Confidence tiers (in priority order):
      exact_name_match  — source leaf key == target field name
      alias_match       — curated alias table hit
      heuristic_match   — source ends with ".id", derive target by camel-casing parent
    """
    if not isinstance(step_n_response_json, dict):
        return []

    response_paths = _flatten_json_paths(step_n_response_json)
    if not response_paths:
        return []

    body_json = step_n1_case.get("request_blueprint", {}).get("body_json")
    body_paths: set[str] = set()
    if isinstance(body_json, dict):
        body_paths = {leaf for _, leaf, _ in body_json_field_candidates(body_json)}

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()  # (source_key, target_field, target_path)

    for source_key, _value in response_paths:
        for target_path, tier in alias_lookup(source_key):
            # Determine the target field and whether this target is reachable.
            # When body_json is None (e.g. enrichment from a stripped manifest step
            # that has no request_blueprint), we still emit candidates — the operator
            # reviews them regardless.
            if target_path.startswith("query."):
                target_field = "request_url"
                actual_target_path = target_path[len("query."):]
            else:
                # Default to request_body_json \u2014 operator reviews and decides
                target_field = "request_body_json"
                actual_target_path = target_path

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
    """Propose candidate bindings from step N response JSON into {placeholder} URL slots.

    Inspects the URL template at step N+1 for curly-brace placeholders (e.g.
    /api/chats/{chatId}) and checks whether any prior response JSON field matches
    by exact leaf name or alias table lookup.

    Candidates go into the review manifest only — never applied automatically.
    When response_json is None (plan-time, before live execution), all slots are
    emitted as "unmatched" candidates so the operator can see what will need filling.
    """
    slots = _SLOT_PATTERN.findall(step_n1_url_template)
    if not slots:
        return []

    # If no live response JSON yet, emit all slots as unmatched (structural discovery)
    if not isinstance(step_n_response_json, dict):
        return [
            {
                "source_case_id": source_case_id,
                "source_key": None,
                "target_case_id": target_case_id,
                "target_field": "request_path",
                "slot": slot,
                "placeholder": "{" + slot + "}",
                "confidence_tier": "unmatched",
                "reason": f"unmatched:no_response_json_available_for_{{{slot}}}",
                "candidate_type": "path_slot_match",
            }
            for slot in slots
        ]

    response_paths = _flatten_json_paths(step_n_response_json)
    if not response_paths:
        return [
            {
                "source_case_id": source_case_id,
                "source_key": None,
                "target_case_id": target_case_id,
                "target_field": "request_path",
                "slot": slot,
                "placeholder": "{" + slot + "}",
                "confidence_tier": "unmatched",
                "reason": f"unmatched:empty_response_json_for_{{{slot}}}",
                "candidate_type": "path_slot_match",
            }
            for slot in slots
        ]

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()  # (slot, source_key)

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
            candidates.append(
                {
                    "source_case_id": source_case_id,
                    "source_key": None,
                    "target_case_id": target_case_id,
                    "target_field": "request_path",
                    "slot": slot,
                    "placeholder": "{" + slot + "}",
                    "confidence_tier": "unmatched",
                    "reason": f"unmatched:no_source_found_for_{{{slot}}}",
                    "candidate_type": "path_slot_match",
                }
            )

    return candidates


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _flatten_json_paths(payload: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Walk a JSON payload and return (dot_path, value) for every scalar leaf."""
    if not isinstance(payload, dict):
        return []
    results: list[tuple[str, Any]] = []
    for key, value in payload.items():
        dotted = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            results.extend(_flatten_json_paths(value, dotted))
        elif isinstance(value, list):
            pass  # Lists are not traversed — too much ambiguity
        elif isinstance(value, (str, int, float, bool)) or value is None:
            results.append((dotted, value))
    return results
