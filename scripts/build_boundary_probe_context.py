from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_boundary_execution_design import DEFAULT_OUTPUT_DIR as DEFAULT_DESIGN_DIR
from scripts.build_boundary_probe_plan import DEFAULT_OUTPUT_DIR as DEFAULT_PLAN_DIR
from scripts.build_boundary_probe_plan import SENSITIVE_MARKERS

DEFAULT_PROBE_PLAN = DEFAULT_PLAN_DIR / "tenant_user_boundary_probe_plan.json"
DEFAULT_EXECUTION_DESIGN = DEFAULT_DESIGN_DIR / "tenant_user_boundary_execution_design.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "runs" / "boundary_probe_context"
SCHEMA_VERSION = "adopt_redthread.boundary_probe_context.v1"

ALLOWED_EXECUTION_MODES = {"safe_read_replay", "reviewed_non_production_workflow"}
ALLOWED_SCOPE_CLASSES = {
    "cross_user_same_tenant",
    "cross_tenant",
    "cross_resource_same_tenant",
    "other_approved_non_production_boundary",
}
FORBIDDEN_RAW_FIELD_KEYS = {
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
}


def build_boundary_probe_context(
    *,
    probe_plan: str | Path = DEFAULT_PROBE_PLAN,
    execution_design: str | Path = DEFAULT_EXECUTION_DESIGN,
    context: str | Path | None = None,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    fail_on_marker_hit: bool = True,
) -> dict[str, Any]:
    """Write a sanitized boundary context template/intake validation artifact.

    This is not a boundary executor and does not resolve context references. It
    validates only packet-safe approval metadata needed before a future executor
    may consume local ignored context.
    """

    plan_path = Path(probe_plan)
    design_path = Path(execution_design)
    context_path = Path(context) if context else None
    plan = _load_optional(plan_path)
    design = _load_optional(design_path)
    supplied = _load_optional(context_path) if context_path else None

    input_text = json.dumps(supplied, sort_keys=True) if supplied else ""
    input_audit = _marker_audit(input_text) if supplied else _empty_audit()
    if fail_on_marker_hit and supplied and not input_audit["passed"]:
        raise RuntimeError(
            "boundary probe context input audit failed "
            f"with markers={input_audit['marker_hit_count']} raw_fields={input_audit['raw_field_hit_count']}"
        )

    validation = _validate_supplied_context(supplied, design) if supplied else _missing_context_validation()
    status = _context_status(validation, input_audit)
    template = _context_template(plan, design)
    normalized = _normalize_context(supplied, template) if supplied else template

    payload = {
        "schema_version": SCHEMA_VERSION,
        "context_status": status,
        "source_probe_plan": _display_path(plan_path),
        "source_execution_design": _display_path(design_path),
        "source_context": _display_path(context_path) if context_path else "not_supplied",
        "artifact_policy": (
            "Boundary context intake artifacts contain only approval metadata, environment labels, actor-scope labels, "
            "selector labels, and value-reference labels. They must not contain raw actor, tenant, resource, session, "
            "credential, auth-header, request, response, or write-context values."
        ),
        "boundary_probe_execution_authorized": status == "ready_for_boundary_probe",
        "boundary_probe_executed": False,
        "confirmed_security_finding": False,
        "gate_decision": "review",
        "verdict_semantics_changed": False,
        "context_template": template,
        "normalized_context": normalized,
        "validation": validation,
        "input_marker_audit": input_audit,
        "non_claims": [
            "Boundary context intake is not boundary execution proof.",
            "A ready context authorizes a future approved non-production probe path only; it does not execute that probe.",
            "Missing or invalid context is blocked setup state, not a confirmed vulnerability.",
            "This artifact does not change local bridge approve/review/block verdict semantics.",
        ],
    }

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "tenant_user_boundary_probe_context.template.json"
    md_path = output_root / "tenant_user_boundary_probe_context.template.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")

    output_audit = _marker_audit(json.dumps(payload, sort_keys=True) + "\n" + _markdown(payload))
    if fail_on_marker_hit and not output_audit["passed"]:
        raise RuntimeError(
            "boundary probe context output audit failed "
            f"with markers={output_audit['marker_hit_count']} raw_fields={output_audit['raw_field_hit_count']}"
        )
    payload["output_marker_audit"] = output_audit
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return payload


def _missing_context_validation() -> dict[str, Any]:
    return {
        "valid": False,
        "blocker_count": 1,
        "blockers": [
            {
                "code": "missing_context",
                "detail": "No sanitized boundary probe context was supplied.",
            }
        ],
        "missing_conditions": [
            "approved_non_production_target",
            "operator_approval",
            "actor_scope_separation",
            "tenant_user_scope_class",
            "selector_bindings",
            "expiration",
            "safe_execution_constraints",
        ],
    }


def _validate_supplied_context(context: dict[str, Any] | None, design: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    if not isinstance(context, dict):
        return _missing_context_validation()
    if context.get("schema_version") != SCHEMA_VERSION:
        blockers.append({"code": "invalid_schema", "detail": f"schema_version must be {SCHEMA_VERSION}"})

    target = context.get("target_environment") if isinstance(context.get("target_environment"), dict) else {}
    execution_mode = str(context.get("execution_mode", ""))
    actor_scopes = context.get("actor_scopes") if isinstance(context.get("actor_scopes"), dict) else {}
    selector_bindings = context.get("selector_bindings") if isinstance(context.get("selector_bindings"), list) else []
    approval = context.get("operator_approval") if isinstance(context.get("operator_approval"), dict) else {}
    constraints = context.get("safe_execution_constraints") if isinstance(context.get("safe_execution_constraints"), dict) else {}

    if not target:
        blockers.append({"code": "missing_target_environment", "detail": "target_environment is required"})
    else:
        if target.get("production") is not False:
            blockers.append({"code": "production_target", "detail": "target_environment.production must be false"})
        if target.get("approved_for_boundary_probe") is not True:
            blockers.append({"code": "unapproved_target", "detail": "approved_for_boundary_probe must be true"})
        classification = str(target.get("target_classification", target.get("environment_classification", "")))
        if classification != "non_production":
            blockers.append({"code": "invalid_target_classification", "detail": "target classification must be non_production"})
        for field in ("environment_label", "base_url_label"):
            if not _safe_label(target.get(field)):
                blockers.append({"code": f"invalid_{field}", "detail": f"{field} must be a non-raw label"})

    if execution_mode not in _allowed_execution_modes(design):
        blockers.append({"code": "invalid_execution_mode", "detail": "execution_mode is not allowed by the boundary context contract"})

    if not actor_scopes:
        blockers.append({"code": "missing_actor_scopes", "detail": "actor_scopes is required"})
    else:
        own = actor_scopes.get("own_scope") if isinstance(actor_scopes.get("own_scope"), dict) else {}
        cross = actor_scopes.get("cross_scope") if isinstance(actor_scopes.get("cross_scope"), dict) else {}
        own_label = str(own.get("actor_label", ""))
        cross_label = str(cross.get("actor_label", ""))
        if not _safe_label(own_label) or not _safe_label(cross_label):
            blockers.append({"code": "invalid_actor_scope_labels", "detail": "own_scope and cross_scope actor labels are required"})
        if own_label and cross_label and own_label == cross_label:
            blockers.append({"code": "actor_scope_not_separated", "detail": "own_scope and cross_scope actor labels must differ"})
        if actor_scopes.get("actor_separation_confirmed") is not True:
            blockers.append({"code": "actor_scope_separation_unconfirmed", "detail": "actor_separation_confirmed must be true"})
        scope_class = str(actor_scopes.get("scope_class", ""))
        if scope_class not in ALLOWED_SCOPE_CLASSES:
            blockers.append({"code": "invalid_scope_class", "detail": "scope_class must describe the approved tenant/user boundary relationship"})

    if not selector_bindings:
        blockers.append({"code": "missing_selector_bindings", "detail": "at least one selector binding is required"})
    for index, binding in enumerate(selector_bindings):
        if not isinstance(binding, dict):
            blockers.append({"code": "invalid_selector_binding", "detail": f"selector binding {index} must be an object"})
            continue
        for field in ("selector_name", "selector_class", "selector_location", "operation_id", "path_template", "own_scope_value_ref", "cross_scope_value_ref"):
            if not _safe_label(binding.get(field), allow_slash=field == "path_template"):
                blockers.append({"code": f"invalid_selector_{field}", "detail": f"selector binding {index} {field} must be a label/reference"})
        if binding.get("own_scope_value_ref") and binding.get("own_scope_value_ref") == binding.get("cross_scope_value_ref"):
            blockers.append({"code": "selector_scope_refs_not_separated", "detail": f"selector binding {index} own/cross refs must differ"})

    if not approval:
        blockers.append({"code": "missing_operator_approval", "detail": "operator_approval is required"})
    else:
        if not _safe_label(approval.get("approved_by_label")):
            blockers.append({"code": "missing_operator_label", "detail": "approved_by_label is required"})
        if not _safe_label(approval.get("scope_note"), allow_space=True):
            blockers.append({"code": "missing_scope_note", "detail": "scope_note is required"})
        if not _parse_time(approval.get("approved_at")):
            blockers.append({"code": "invalid_approved_at", "detail": "approved_at must be an ISO timestamp"})
        expires_at = _parse_time(approval.get("expires_at"))
        if not expires_at:
            blockers.append({"code": "invalid_expires_at", "detail": "expires_at must be an ISO timestamp"})
        elif expires_at <= datetime.now(timezone.utc):
            blockers.append({"code": "expired_context", "detail": "expires_at must be in the future"})

    for field in ("approved_non_production_only", "no_raw_values_in_generated_artifacts", "no_production_writes", "future_executor_must_not_persist_resolved_values"):
        if constraints.get(field) is not True:
            blockers.append({"code": f"missing_constraint_{field}", "detail": f"safe_execution_constraints.{field} must be true"})

    missing_conditions = _missing_conditions_from_blockers(blockers)
    return {
        "valid": not blockers,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "missing_conditions": missing_conditions,
    }


def _context_status(validation: dict[str, Any], audit: dict[str, Any]) -> str:
    if not audit.get("passed", True):
        return "privacy_blocked"
    if validation.get("valid") is True:
        return "ready_for_boundary_probe"
    blockers = validation.get("blockers", []) if isinstance(validation.get("blockers"), list) else []
    if any(isinstance(item, dict) and item.get("code") == "missing_context" for item in blockers):
        return "blocked_missing_context"
    return "blocked_invalid_context"


def _context_template(plan: dict[str, Any], design: dict[str, Any]) -> dict[str, Any]:
    selector = _select_selector(plan, design)
    return {
        "schema_version": SCHEMA_VERSION,
        "target_environment": {
            "environment_label": "non_production_environment_label",
            "base_url_label": "approved_non_production_base_url_label",
            "target_classification": "non_production",
            "production": False,
            "approved_for_boundary_probe": False,
        },
        "execution_mode": "safe_read_replay",
        "actor_scopes": {
            "scope_class": "cross_user_same_tenant",
            "actor_separation_confirmed": False,
            "own_scope": {
                "actor_label": "own_scope_actor_label",
                "tenant_scope_label": "own_scope_tenant_label",
            },
            "cross_scope": {
                "actor_label": "cross_scope_actor_label",
                "tenant_scope_label": "cross_scope_tenant_label",
            },
        },
        "selector_bindings": [
            {
                "selector_name": selector["selector_name"],
                "selector_class": selector["selector_class"],
                "selector_location": selector["selector_location"],
                "operation_id": selector["operation_id"],
                "path_template": selector["path_template"],
                "own_scope_value_ref": "context_ref.own_scope.selector_value_label",
                "cross_scope_value_ref": "context_ref.cross_scope.selector_value_label",
            }
        ],
        "operator_approval": {
            "approved_by_label": "operator_or_ticket_label",
            "approved_at": "YYYY-MM-DDTHH:MM:SSZ",
            "expires_at": "YYYY-MM-DDTHH:MM:SSZ",
            "scope_note": "why this non-production boundary probe is safe",
        },
        "safe_execution_constraints": {
            "approved_non_production_only": True,
            "no_raw_values_in_generated_artifacts": True,
            "no_production_writes": True,
            "future_executor_must_not_persist_resolved_values": True,
        },
    }


def _normalize_context(context: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(context, dict):
        return template
    normalized = _context_template({}, {})
    normalized["target_environment"] = _pick_dict(context.get("target_environment"), normalized["target_environment"], {
        "environment_label",
        "base_url_label",
        "target_classification",
        "environment_classification",
        "production",
        "approved_for_boundary_probe",
    })
    if "environment_classification" in normalized["target_environment"] and "target_classification" not in normalized["target_environment"]:
        normalized["target_environment"]["target_classification"] = normalized["target_environment"].pop("environment_classification")
    normalized["execution_mode"] = str(context.get("execution_mode", normalized["execution_mode"]))
    normalized["actor_scopes"] = _pick_actor_scopes(context.get("actor_scopes"), normalized["actor_scopes"])
    normalized["selector_bindings"] = _pick_selector_bindings(context.get("selector_bindings"), template.get("selector_bindings", normalized["selector_bindings"]))
    normalized["operator_approval"] = _pick_dict(context.get("operator_approval"), normalized["operator_approval"], {"approved_by_label", "approved_at", "expires_at", "scope_note", "approval_ticket_label"})
    if "scope_note" in normalized["operator_approval"]:
        normalized["operator_approval"]["scope_note"] = "provided_sanitized_scope_note"
    normalized["safe_execution_constraints"] = _pick_dict(context.get("safe_execution_constraints"), normalized["safe_execution_constraints"], set(normalized["safe_execution_constraints"].keys()))
    normalized["schema_version"] = str(context.get("schema_version", SCHEMA_VERSION))
    return normalized


def _pick_dict(value: Any, fallback: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return fallback
    return {key: value[key] for key in allowed if key in value}


def _pick_actor_scopes(value: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return fallback
    picked: dict[str, Any] = {}
    for key in ("scope_class", "actor_separation_confirmed"):
        if key in value:
            picked[key] = value[key]
    for scope in ("own_scope", "cross_scope"):
        picked[scope] = _pick_dict(value.get(scope), fallback.get(scope, {}), {"actor_label", "tenant_scope_label"})
    return picked


def _pick_selector_bindings(value: Any, fallback: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return fallback if isinstance(fallback, list) else []
    allowed = {"selector_name", "selector_class", "selector_location", "operation_id", "path_template", "own_scope_value_ref", "cross_scope_value_ref"}
    return [_pick_dict(item, {}, allowed) for item in value if isinstance(item, dict)][:10]


def _select_selector(plan: dict[str, Any], design: dict[str, Any]) -> dict[str, str]:
    candidates: list[dict[str, Any]] = []
    candidate_summary = plan.get("candidate_summary", {}) if isinstance(plan.get("candidate_summary"), dict) else {}
    if isinstance(candidate_summary.get("selectors"), list):
        candidates.extend(item for item in candidate_summary["selectors"] if isinstance(item, dict))
    selector_scope = design.get("selector_scope", {}) if isinstance(design.get("selector_scope"), dict) else {}
    if isinstance(selector_scope.get("example_selectors"), list):
        candidates.extend(item for item in selector_scope["example_selectors"] if isinstance(item, dict))
    selected = candidates[0] if candidates else {}
    return {
        "selector_name": str(selected.get("selector_name", selected.get("name", "boundary_selector_label"))),
        "selector_class": str(selected.get("selector_class", selected.get("class", "resource"))),
        "selector_location": str(selected.get("selector_location", selected.get("location", "body_field"))),
        "operation_id": str(selected.get("operation_id", "operation_label")),
        "path_template": str(selected.get("path_template", "path_template_label")),
    }


def _allowed_execution_modes(design: dict[str, Any]) -> set[str]:
    contract = design.get("approved_context_contract", {}) if isinstance(design.get("approved_context_contract"), dict) else {}
    mode_contract = contract.get("execution_mode", {}) if isinstance(contract.get("execution_mode"), dict) else {}
    values = mode_contract.get("allowed_values") if isinstance(mode_contract.get("allowed_values"), list) else []
    allowed = {str(item) for item in values if str(item)}
    return allowed or ALLOWED_EXECUTION_MODES


def _missing_conditions_from_blockers(blockers: list[dict[str, str]]) -> list[str]:
    categories: set[str] = set()
    for blocker in blockers:
        code = blocker.get("code", "")
        if "target" in code or "environment" in code or code == "invalid_schema":
            categories.add("approved_non_production_target")
        if "operator" in code or "approved_at" in code or "expires" in code or "scope_note" in code or "expired" in code:
            categories.add("operator_approval")
            categories.add("expiration")
        if "actor" in code:
            categories.add("actor_scope_separation")
        if "scope_class" in code:
            categories.add("tenant_user_scope_class")
        if "selector" in code:
            categories.add("selector_bindings")
        if "constraint" in code:
            categories.add("safe_execution_constraints")
        if "execution_mode" in code:
            categories.add("safe_execution_constraints")
    return sorted(categories)


def _safe_label(value: Any, *, allow_slash: bool = False, allow_space: bool = False) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    text = value.strip()
    lowered = text.casefold()
    if "://" in text or "?" in text or "@" in text:
        return False
    if not allow_slash and "/" in text:
        return False
    if not allow_space and any(ch.isspace() for ch in text):
        return False
    if any(marker.casefold() in lowered for marker in SENSITIVE_MARKERS):
        return False
    return True


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _marker_audit(text: str) -> dict[str, Any]:
    lowered = text.casefold()
    marker_hits = [marker for marker in SENSITIVE_MARKERS if marker.casefold() in lowered]
    raw_field_hits = [field for field in FORBIDDEN_RAW_FIELD_KEYS if f'"{field}"' in lowered or f"'{field}'" in lowered]
    return {
        "marker_set": "configured_sensitive_marker_set_plus_boundary_context_raw_field_keys",
        "marker_count": len(SENSITIVE_MARKERS),
        "marker_hit_count": len(marker_hits),
        "raw_field_key_count": len(FORBIDDEN_RAW_FIELD_KEYS),
        "raw_field_hit_count": len(raw_field_hits),
        "passed": len(marker_hits) == 0 and len(raw_field_hits) == 0,
        "markers": ["redacted_configured_marker"] if marker_hits else [],
        "raw_field_keys": ["redacted_raw_field_key"] if raw_field_hits else [],
    }


def _empty_audit() -> dict[str, Any]:
    audit = _marker_audit("")
    audit["passed"] = True
    return audit


def _markdown(payload: dict[str, Any]) -> str:
    validation = payload["validation"]
    template = payload["context_template"]
    normalized = payload["normalized_context"]
    output_audit = payload.get("output_marker_audit", _empty_audit())
    lines = [
        "# Tenant/User Boundary Probe Context Intake",
        "",
        payload["artifact_policy"],
        "",
        "## Status",
        "",
        f"- Context status: `{payload['context_status']}`",
        f"- Boundary probe execution authorized: `{payload['boundary_probe_execution_authorized']}`",
        f"- Boundary probe executed: `{payload['boundary_probe_executed']}`",
        f"- Gate decision interpretation: `{payload['gate_decision']}`",
        f"- Confirmed security finding: `{payload['confirmed_security_finding']}`",
        f"- Verdict semantics changed: `{payload['verdict_semantics_changed']}`",
        f"- Source context: `{payload['source_context']}`",
        "",
        "## Required context shape",
        "",
        f"- Schema: `{template['schema_version']}`",
        "- Target environment: non-production label, base URL label, production false, approved-for-boundary-probe true",
        "- Actor scopes: own-scope and cross-scope labels, separated and approved",
        "- Scope class: tenant/user boundary class label",
        "- Selector bindings: selector metadata plus own/cross value-reference labels",
        "- Operator approval: approver label, approval timestamp, expiration timestamp, and scope note",
        "- Safe execution constraints: non-production only, no raw values in generated artifacts, no production writes, no resolved-value persistence",
        "",
        "## Validation",
        "",
        f"- Valid: `{validation['valid']}`",
        f"- Blocker count: `{validation['blocker_count']}`",
        f"- Missing conditions: `{_join(validation.get('missing_conditions', []))}`",
        "",
        "### Blockers",
        "",
    ]
    blockers = validation.get("blockers", []) if isinstance(validation.get("blockers"), list) else []
    if blockers:
        lines.extend(f"- `{item.get('code', 'unknown')}` — {item.get('detail', '')}" for item in blockers if isinstance(item, dict))
    else:
        lines.append("- none")
    first_binding = (normalized.get("selector_bindings") or [{}])[0] if isinstance(normalized.get("selector_bindings"), list) else {}
    lines.extend([
        "",
        "## Sanitized selected context labels",
        "",
        f"- Environment label: `{normalized.get('target_environment', {}).get('environment_label', 'unknown')}`",
        f"- Target classification: `{normalized.get('target_environment', {}).get('target_classification', 'unknown')}`",
        f"- Execution mode: `{normalized.get('execution_mode', 'unknown')}`",
        f"- Scope class: `{normalized.get('actor_scopes', {}).get('scope_class', 'unknown')}`",
        f"- Selector name: `{first_binding.get('selector_name', 'unknown')}`",
        f"- Selector class: `{first_binding.get('selector_class', 'unknown')}`",
        f"- Selector location: `{first_binding.get('selector_location', 'unknown')}`",
        f"- Operation ID: `{first_binding.get('operation_id', 'unknown')}`",
        f"- Path template: `{first_binding.get('path_template', 'unknown')}`",
        "",
        "## Non-claims",
        "",
    ])
    lines.extend(f"- {item}" for item in payload.get("non_claims", []))
    lines.extend([
        "",
        "## Marker audit",
        "",
        f"- Input passed: `{payload['input_marker_audit']['passed']}`",
        f"- Input marker hits: `{payload['input_marker_audit']['marker_hit_count']}`",
        f"- Input raw field key hits: `{payload['input_marker_audit']['raw_field_hit_count']}`",
        f"- Output passed: `{output_audit['passed']}`",
        f"- Output marker hits: `{output_audit['marker_hit_count']}`",
        f"- Output raw field key hits: `{output_audit['raw_field_hit_count']}`",
        "",
    ])
    return "\n".join(lines)


def _load_optional(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded if isinstance(loaded, dict) else {}


def _join(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return "none"
    return ",".join(str(item) for item in items)


def _display_path(path: Path | None) -> str:
    if path is None:
        return "not_supplied"
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a sanitized tenant/user boundary probe context template and intake validation artifact without executing probes.")
    parser.add_argument("--probe-plan", default=str(DEFAULT_PROBE_PLAN))
    parser.add_argument("--execution-design", default=str(DEFAULT_EXECUTION_DESIGN))
    parser.add_argument("--context", default=None, help="Optional sanitized approved boundary context metadata JSON to validate; this script never resolves raw values")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--fail-on-marker-hit", action="store_true")
    args = parser.parse_args()

    payload = build_boundary_probe_context(
        probe_plan=args.probe_plan,
        execution_design=args.execution_design,
        context=args.context,
        output_dir=args.output_dir,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(f"tenant/user boundary probe context intake -> {Path(args.output_dir) / 'tenant_user_boundary_probe_context.template.md'}")
    print(json.dumps({
        "context_status": payload["context_status"],
        "boundary_probe_execution_authorized": payload["boundary_probe_execution_authorized"],
        "boundary_probe_executed": payload["boundary_probe_executed"],
        "blocker_count": payload["validation"]["blocker_count"],
        "input_marker_hits": payload["input_marker_audit"]["marker_hit_count"],
        "raw_field_key_hits": payload["input_marker_audit"]["raw_field_hit_count"],
    }, indent=2))


if __name__ == "__main__":
    main()
