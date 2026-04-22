from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def build_step(case: dict[str, Any], cases: list[dict[str, Any]], overrides: dict[str, Any], case_host: str) -> dict[str, Any]:
    request_url_template, response_bindings = step_response_binding_contract(case, cases)
    request_url_template, response_bindings, review_decisions = apply_binding_override(case, request_url_template, response_bindings, overrides)
    review_summary = binding_review_summary(response_bindings, review_decisions)
    step = {
        "case_id": case.get("case_id"),
        "workflow_step_index": case.get("workflow_step_index", 0),
        "method": case.get("method"),
        "path": case.get("path"),
        "execution_mode": case.get("execution_mode"),
        "approval_mode": case.get("approval_mode"),
        "target_env": case.get("target_env"),
        "allowed": case.get("allowed", False),
        "depends_on_previous_step": int(case.get("workflow_step_index", 0)) > 0,
        "step_context_requirements": {
            "auth_context_required": case.get("execution_mode") == "live_safe_read_with_approved_auth",
            "write_context_required": case.get("execution_mode") == "live_reviewed_write_staging",
            "expected_host": case_host,
        },
        "response_bindings": response_bindings,
        "binding_review_required": review_summary["pending_review_response_binding_count"] > 0,
        "binding_review_summary": review_summary,
        "binding_review_decisions": review_decisions,
    }
    if request_url_template:
        step["request_url_template"] = request_url_template
    return step


def load_binding_overrides(value: dict[str, Any] | str | Path | None) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return json.loads(Path(value).read_text())


def step_response_binding_contract(case: dict[str, Any], cases: list[dict[str, Any]]) -> tuple[str | None, list[dict[str, Any]]]:
    explicit_bindings = [normalized_binding(binding, inferred=False) for binding in case.get("response_bindings", [])]
    if explicit_bindings:
        return str(case.get("request_blueprint", {}).get("url", "")).strip() or None, explicit_bindings
    index = int(case.get("workflow_step_index", 0))
    if index <= 0:
        return None, []
    source_case = next((item for item in cases if int(item.get("workflow_step_index", 0)) == index - 1), None)
    if source_case is None:
        return None, []
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
        if not looks_like_binding_query(name, value):
            next_pairs.append((name, value))
            continue
        binding_id = f"{name}_from_{source_case.get('case_id')}"
        placeholder = "{{" + binding_id + "}}"
        bindings.append(
            normalized_binding(
                {
                    "binding_id": binding_id,
                    "source_case_id": source_case.get("case_id"),
                    "source_type": "response_json",
                    "source_key": name,
                    "target_field": "request_url",
                    "placeholder": placeholder,
                    "required": True,
                    "inference_reason": f"query_param:{name}:previous_step_json",
                    "confidence": "low",
                },
                inferred=True,
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


def apply_binding_override(
    case: dict[str, Any],
    request_url_template: str | None,
    response_bindings: list[dict[str, Any]],
    overrides: dict[str, Any],
) -> tuple[str | None, list[dict[str, Any]], list[dict[str, Any]]]:
    case_override = overrides.get("case_bindings", {}).get(str(case.get("case_id")), {})
    inferred_bindings = [binding for binding in response_bindings if binding.get("inferred")]
    if not case_override:
        return request_url_template, response_bindings, pending_review_decisions(inferred_bindings)
    if case_override.get("review_status") == "rejected":
        return None, [], decision_records(inferred_bindings, "rejected")
    if case_override.get("replace_response_bindings") is not None:
        replaced_bindings = [normalized_binding(binding, inferred=False) for binding in case_override.get("replace_response_bindings", [])]
        return _override_template(case_override, request_url_template), replaced_bindings, decision_records(inferred_bindings, "replaced")
    review_status = str(case_override.get("review_status", "")).strip()
    if review_status:
        updated = [{**binding, "review_status": review_status} for binding in response_bindings]
        if review_status == "approved":
            return _override_template(case_override, request_url_template), updated, decision_records(inferred_bindings, "approved")
        return _override_template(case_override, request_url_template), updated, decision_records(inferred_bindings, review_status)
    return _override_template(case_override, request_url_template), response_bindings, pending_review_decisions(inferred_bindings)


def normalized_binding(binding: dict[str, Any], *, inferred: bool) -> dict[str, Any]:
    normalized = dict(binding)
    normalized.setdefault("required", True)
    normalized["inferred"] = bool(normalized.get("inferred", inferred))
    normalized.setdefault("confidence", "manual" if not inferred else "low")
    normalized.setdefault("inference_reason", "manual_declared" if not inferred else "auto_query_param_previous_step")
    normalized.setdefault("review_status", "pending_review" if normalized["inferred"] else "approved")
    return normalized


def binding_review_summary(bindings: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "inferred_response_binding_count": sum(1 for decision in decisions if decision.get("decision") in {"pending_review", "approved", "rejected", "replaced"}),
        "approved_response_binding_count": sum(1 for decision in decisions if decision.get("decision") == "approved"),
        "pending_review_response_binding_count": sum(1 for decision in decisions if decision.get("decision") == "pending_review"),
        "rejected_response_binding_count": sum(1 for decision in decisions if decision.get("decision") == "rejected"),
        "replaced_response_binding_count": sum(1 for decision in decisions if decision.get("decision") == "replaced"),
        "active_declared_response_binding_count": len(bindings),
    }


def pending_review_decisions(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return decision_records(bindings, "pending_review")


def decision_records(bindings: list[dict[str, Any]], decision: str) -> list[dict[str, Any]]:
    return [
        {
            "binding_id": binding.get("binding_id"),
            "source_case_id": binding.get("source_case_id"),
            "target_field": binding.get("target_field"),
            "inference_reason": binding.get("inference_reason"),
            "confidence": binding.get("confidence"),
            "decision": decision,
        }
        for binding in bindings
    ]


def _override_template(case_override: dict[str, Any], request_url_template: str | None) -> str | None:
    override_template = str(case_override.get("request_url_template", "")).strip()
    return override_template or request_url_template


def looks_like_binding_query(name: str, value: str) -> bool:
    lowered = str(name).lower()
    raw = str(value).strip()
    if lowered not in {"id"} and not lowered.endswith("_id"):
        return False
    if not raw or "{{" in raw or len(raw) < 3:
        return False
    return any(char.isdigit() for char in raw) or "-" in raw or "_" in raw


def encoded_placeholder(placeholder: str) -> str:
    return urlencode({"x": placeholder}).removeprefix("x=")
