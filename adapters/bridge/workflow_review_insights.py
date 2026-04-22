from __future__ import annotations

from typing import Any


def build_required_contexts(
    workflow: dict[str, Any],
    cases: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    session = workflow.get("session_context_requirements", {})
    step_case_ids = [str(step.get("case_id", "")) for step in workflow.get("steps", [])]
    auth_cases = [case_id for case_id in step_case_ids if cases.get(case_id, {}).get("execution_mode") == "live_safe_read_with_approved_auth"]
    write_cases = [case_id for case_id in step_case_ids if cases.get(case_id, {}).get("execution_mode") == "live_reviewed_write_staging"]
    return {
        "auth_context_required": bool(session.get("approved_auth_context_required") or auth_cases),
        "write_context_required": bool(session.get("approved_write_context_required") or write_cases),
        "auth_context_case_ids": auth_cases,
        "write_context_case_ids": write_cases,
        "same_auth_context_required": bool(session.get("same_auth_context_required", False)),
        "same_write_context_required": bool(session.get("same_write_context_required", False)),
        "required_auth_header_names": list(session.get("required_auth_header_names", [])),
    }


def build_body_template_gaps(
    workflow: dict[str, Any],
    cases: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for step in workflow.get("steps", []):
        case_id = str(step.get("case_id", ""))
        case = cases.get(case_id, {})
        body_json = case.get("request_blueprint", {}).get("body_json")
        body_bindings = [b for b in step.get("response_bindings", []) if b.get("target_field") == "request_body_json"]
        if body_bindings and not isinstance(body_json, dict):
            gaps.append(
                {
                    "case_id": case_id,
                    "gap_type": "missing_body_template",
                    "reason": "response bindings target request_body_json but no request blueprint body template is present",
                    "binding_ids": [str(b.get("binding_id", "")) for b in body_bindings],
                }
            )
            continue
        for field in _static_id_fields_without_binding(case, step):
            gaps.append(
                {
                    "case_id": case_id,
                    "gap_type": "static_id_like_field",
                    "target_path": field,
                    "reason": f"body field '{field}' is id-like but has no declared response binding",
                }
            )
    return gaps


def build_open_questions(
    workflow: dict[str, Any],
    body_template_gaps: list[dict[str, Any]],
    candidate_pairs: list[dict[str, Any]],
    header_candidates: list[dict[str, Any]],
) -> list[str]:
    questions: list[str] = []
    for gap in body_template_gaps:
        if gap.get("gap_type") == "missing_body_template":
            questions.append(
                f"Step {gap['case_id']} needs a reviewed body template before request_body_json bindings can apply."
            )
        elif gap.get("gap_type") == "static_id_like_field":
            questions.append(
                f"Step {gap['case_id']} body field '{gap['target_path']}' is still static. Is a response binding missing?"
            )
    for pair in candidate_pairs:
        for candidate in pair.get("candidate_path_bindings", []):
            if candidate.get("confidence_tier") == "unmatched":
                questions.append(
                    f"Step {pair.get('target_case_id')} path slot '{candidate.get('slot')}' has no candidate source yet."
                )
    for candidate in header_candidates:
        if candidate.get("confidence_tier") == "unmatched":
            questions.append(
                f"Step {candidate.get('source_case_id')} sets cookie '{candidate.get('cookie_name')}', but no downstream cookie user was found."
            )
    return _dedupe(questions)


def _static_id_fields_without_binding(case: dict[str, Any], step: dict[str, Any]) -> list[str]:
    body_json = case.get("request_blueprint", {}).get("body_json")
    if not isinstance(body_json, dict):
        return []
    bound_paths = {
        str(binding.get("target_path", ""))
        for binding in step.get("response_bindings", [])
        if binding.get("target_field") == "request_body_json"
    }
    gaps: list[str] = []
    for path, field_name, value in _body_fields(body_json):
        lowered = field_name.lower()
        if lowered != "id" and not lowered.endswith("_id") and not lowered.endswith("id"):
            continue
        if path in bound_paths:
            continue
        raw = str(value).strip()
        if not raw or raw.startswith("{{") or raw.lower() in {"pending", "placeholder", "todo", "example"}:
            gaps.append(path)
    return gaps


def _body_fields(payload: dict[str, Any], prefix: str = "") -> list[tuple[str, str, str]]:
    fields: list[tuple[str, str, str]] = []
    for key, value in payload.items():
        dotted = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            fields.extend(_body_fields(value, dotted))
        elif isinstance(value, (str, int, float, bool)):
            fields.append((dotted, str(key), str(value)))
    return fields


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out
