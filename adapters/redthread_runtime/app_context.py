from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

AUTH_HEADER_NAMES = {"authorization", "cookie", "x-api-key", "x-token", "x-sign"}
USER_FIELD_HINTS = {"user", "profile", "account", "owner", "member", "customer", "actor"}
TENANT_FIELD_HINTS = {"tenant", "org", "organization", "workspace", "company", "business"}
SECRET_FIELD_HINTS = {"token", "secret", "password", "cookie", "session", "key", "credential"}
PII_FIELD_HINTS = {"email", "phone", "ssn", "name", "address", "profile"}
FINANCIAL_FIELD_HINTS = {"payment", "billing", "invoice", "price", "subscription", "product", "card"}
MESSAGE_FIELD_HINTS = {"message", "msg", "chat", "prompt", "content", "body", "comment", "conversation"}
SAFE_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.\-\[\]]{0,79}$")
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
HEX_RE = re.compile(r"^[0-9a-fA-F]{16,}$")


def build_app_context(bundle: dict[str, Any], workflow_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build sanitized structural app context for RedThread-facing evidence.

    The context intentionally keeps only operation order, field names, auth classes,
    sensitivity tags, and boundary hints. It must not include request/response values,
    auth values, cookies, tokens, or raw path identifiers.
    """

    fixtures = [fixture for fixture in bundle.get("fixtures", []) if isinstance(fixture, dict)]
    operations = [_operation_record(index, fixture) for index, fixture in enumerate(fixtures)]
    dependencies = _workflow_dependencies(operations, workflow_plan)
    workflow_order = [
        {
            "operation_id": operation["operation_id"],
            "step_index": operation["step_index"],
            "workflow_group": operation["workflow_group"],
            "method": operation["method"],
            "path_template": operation["path_template"],
            "depends_on": dependencies.get(operation["operation_id"], []),
        }
        for operation in operations
    ]
    tool_action_schema = [_tool_action_schema(operation, fixture) for operation, fixture in zip(operations, fixtures, strict=False)]
    field_inventory = _field_inventory(fixtures)
    boundary = _tenant_user_boundary(fixtures)
    approved_context = _approved_context_requirements(fixtures, workflow_plan)
    return {
        "schema_version": "app_context.v1",
        "source": str(bundle.get("source", "unknown")),
        "ingestion_mode": str(bundle.get("ingestion_mode", "unknown")),
        "workflow_order": workflow_order,
        "tool_action_schema": tool_action_schema,
        "auth_model": _auth_model(fixtures, boundary, approved_context),
        "data_sensitivity": _data_sensitivity(fixtures, field_inventory, boundary),
        "tenant_user_boundary": boundary,
    }


def summarize_app_context(app_context: dict[str, Any]) -> dict[str, Any]:
    auth_model = app_context.get("auth_model", {}) if isinstance(app_context.get("auth_model"), dict) else {}
    sensitivity = app_context.get("data_sensitivity", {}) if isinstance(app_context.get("data_sensitivity"), dict) else {}
    boundary = app_context.get("tenant_user_boundary", {}) if isinstance(app_context.get("tenant_user_boundary"), dict) else {}
    tool_schemas = app_context.get("tool_action_schema", [])
    action_class_counts = _count_values(
        schema.get("action_class")
        for schema in tool_schemas
        if isinstance(schema, dict)
    )
    return {
        "schema_version": app_context.get("schema_version", "app_context.v1"),
        "operation_count": len(app_context.get("workflow_order", [])),
        "tool_action_schema_count": len(tool_schemas),
        "action_class_counts": action_class_counts,
        "auth_mode": auth_model.get("mode", "unknown"),
        "auth_scope_hints": auth_model.get("scope_hints", []),
        "requires_approved_context": bool(auth_model.get("requires_approved_context", False)),
        "requires_approved_auth_context": bool(auth_model.get("requires_approved_auth_context", False)),
        "requires_approved_write_context": bool(auth_model.get("requires_approved_write_context", False)),
        "data_sensitivity_tags": sensitivity.get("tags", []),
        "candidate_user_field_count": len(boundary.get("candidate_user_fields", [])),
        "candidate_tenant_field_count": len(boundary.get("candidate_tenant_fields", [])),
        "candidate_route_param_count": len(boundary.get("candidate_route_params", [])),
    }


def _operation_record(index: int, fixture: dict[str, Any]) -> dict[str, Any]:
    method = str(fixture.get("method", "GET")).upper()
    path_template = _path_template(str(fixture.get("path", "/")))
    workflow_group = _safe_identifier(str(fixture.get("workflow_group", "default"))) or "default"
    return {
        "operation_id": _operation_id(index, method, path_template),
        "case_id": str(fixture.get("name", "")),
        "step_index": index,
        "workflow_group": workflow_group,
        "method": method,
        "path_template": path_template,
    }


def _workflow_dependencies(operations: list[dict[str, Any]], workflow_plan: dict[str, Any] | None) -> dict[str, list[str]]:
    by_case_id = {operation["case_id"]: operation["operation_id"] for operation in operations if operation.get("case_id")}
    dependencies: dict[str, list[str]] = {operation["operation_id"]: [] for operation in operations}
    if workflow_plan:
        for workflow in workflow_plan.get("workflows", []):
            for step in workflow.get("steps", []):
                case_id = str(step.get("case_id", ""))
                operation_id = by_case_id.get(case_id)
                if not operation_id:
                    continue
                predecessors = [
                    by_case_id[item]
                    for item in step.get("depends_on", [])
                    if item in by_case_id and by_case_id[item] != operation_id
                ]
                if predecessors:
                    dependencies[operation_id] = sorted(dict.fromkeys(predecessors))
    previous_by_group: dict[str, str] = {}
    for operation in operations:
        operation_id = operation["operation_id"]
        if not dependencies[operation_id]:
            previous = previous_by_group.get(operation["workflow_group"])
            if previous:
                dependencies[operation_id] = [previous]
        previous_by_group[operation["workflow_group"]] = operation_id
    return dependencies


def _tool_action_schema(operation: dict[str, Any], fixture: dict[str, Any]) -> dict[str, Any]:
    query_params = _safe_names(fixture.get("query_params", []))
    body_fields = _safe_names(fixture.get("body_fields", []))
    response_fields = _safe_names(fixture.get("response_fields", []))
    return {
        "operation_id": operation["operation_id"],
        "method": operation["method"],
        "path_template": operation["path_template"],
        "action_class": _action_class(fixture),
        "request_fields": sorted(dict.fromkeys([*query_params, *body_fields])),
        "response_fields": response_fields,
        "field_locations": {
            "query_params": query_params,
            "body_fields": body_fields,
            "response_fields": response_fields,
        },
    }


def _auth_model(fixtures: list[dict[str, Any]], boundary: dict[str, Any], approved_context: dict[str, bool]) -> dict[str, Any]:
    hints = {str(hint).lower() for fixture in fixtures for hint in fixture.get("auth_hints", [])}
    mode = "anonymous"
    if any("bearer" in hint for hint in hints) or "authorization" in hints:
        mode = "bearer"
    elif any(hint in {"x-api-key", "x-token", "x-sign"} or "api" in hint and "key" in hint for hint in hints):
        mode = "api_key"
    elif "cookie" in hints:
        mode = "cookie"
    elif any("basic" in hint for hint in hints):
        mode = "basic"
    elif any("session" in hint for hint in hints):
        mode = "session"
    elif hints:
        mode = "unknown"

    scope_hints: list[str] = []
    if boundary.get("candidate_user_fields") or any(str(fixture.get("tenant_scope", "")) == "single_tenant" for fixture in fixtures):
        scope_hints.append("user_scoped")
    if boundary.get("candidate_tenant_fields") or any("tenant" in str(fixture.get("tenant_scope", "")) for fixture in fixtures):
        scope_hints.append("tenant_scoped")
    if any(_has_hint(str(fixture.get("endpoint_family", "")), {"admin"}) or "/admin/" in str(fixture.get("path", "")) for fixture in fixtures):
        scope_hints.append("admin_scoped")

    requires_approved_auth_context = approved_context["auth"] or any(
        fixture.get("auth_hints") or fixture.get("replay_class") == "safe_read_with_review"
        for fixture in fixtures
    )
    requires_approved_write_context = approved_context["write"] or any(
        _action_class(fixture) in {"write", "destructive"}
        and (fixture.get("approval_required") or fixture.get("replay_class") in {"manual_review", "sandbox_only"})
        for fixture in fixtures
    )
    requires_context = requires_approved_auth_context or requires_approved_write_context
    return {
        "mode": mode,
        "scope_hints": sorted(dict.fromkeys(scope_hints)),
        "requires_approved_context": bool(requires_context),
        "requires_approved_auth_context": bool(requires_approved_auth_context),
        "requires_approved_write_context": bool(requires_approved_write_context),
        "auth_header_families": sorted({hint for hint in hints if hint in AUTH_HEADER_NAMES}),
    }


def _approved_context_requirements(fixtures: list[dict[str, Any]], workflow_plan: dict[str, Any] | None) -> dict[str, bool]:
    auth_required = False
    write_required = False
    if isinstance(workflow_plan, dict):
        for workflow in workflow_plan.get("workflows", []):
            if not isinstance(workflow, dict):
                continue
            session_requirements = workflow.get("session_context_requirements", {})
            if isinstance(session_requirements, dict):
                auth_required = auth_required or bool(session_requirements.get("approved_auth_context_required"))
                write_required = write_required or bool(session_requirements.get("approved_write_context_required"))
            for step in workflow.get("steps", []):
                if not isinstance(step, dict):
                    continue
                step_requirements = step.get("step_context_requirements", {})
                if isinstance(step_requirements, dict):
                    auth_required = auth_required or bool(step_requirements.get("auth_context_required"))
                    write_required = write_required or bool(step_requirements.get("write_context_required"))
    if not auth_required:
        auth_required = any(fixture.get("auth_hints") for fixture in fixtures)
    if not write_required:
        write_required = any(_action_class(fixture) in {"write", "destructive"} for fixture in fixtures)
    return {"auth": bool(auth_required), "write": bool(write_required)}


def _action_class(fixture: dict[str, Any]) -> str:
    method = str(fixture.get("method", "GET")).upper()
    attack_types = {str(value) for value in fixture.get("candidate_attack_types", [])}
    replay_class = str(fixture.get("replay_class", ""))
    if method in {"DELETE", "PATCH"} or "destructive_action_abuse" in attack_types:
        return "destructive"
    if method in {"POST", "PUT"} or replay_class in {"manual_review", "sandbox_only"}:
        return "write"
    return "read"


def _count_values(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        if value is None:
            continue
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _data_sensitivity(fixtures: list[dict[str, Any]], field_inventory: list[str], boundary: dict[str, Any]) -> dict[str, Any]:
    tags: list[str] = []
    haystack = " ".join(
        [
            *field_inventory,
            *(str(fixture.get("path", "")) for fixture in fixtures),
            *(str(fixture.get("endpoint_family", "")) for fixture in fixtures),
        ]
    ).lower()
    fixture_sensitivities = {str(fixture.get("data_sensitivity", "")).lower() for fixture in fixtures}
    if "secret" in fixture_sensitivities or any(_has_hint(field, SECRET_FIELD_HINTS) for field in field_inventory):
        tags.append("secret_like")
    if "pii" in fixture_sensitivities or any(_has_hint(field, PII_FIELD_HINTS) for field in field_inventory):
        tags.extend(["pii_like", "user_data"])
    if any(_has_hint(field, FINANCIAL_FIELD_HINTS) for field in field_inventory) or any(word in haystack for word in FINANCIAL_FIELD_HINTS):
        tags.append("financial_like")
    if any(_has_hint(field, MESSAGE_FIELD_HINTS) for field in field_inventory) or any(word in haystack for word in {"chat", "conversation", "support"}):
        tags.append("support_message_like")
    if boundary.get("candidate_tenant_fields"):
        tags.append("tenant_data")
    if not tags:
        tags.append("unknown")
    return {
        "tags": sorted(dict.fromkeys(tags)),
        "field_hints": field_inventory[:50],
    }


def _tenant_user_boundary(fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    fields = _field_inventory(fixtures)
    paths = [str(fixture.get("path", "")) for fixture in fixtures]
    return {
        "candidate_user_fields": [field for field in fields if _has_hint(field, USER_FIELD_HINTS)],
        "candidate_tenant_fields": [field for field in fields if _has_hint(field, TENANT_FIELD_HINTS)],
        "candidate_route_params": sorted(dict.fromkeys(param for path in paths for param in _route_param_hints(path))),
    }


def _field_inventory(fixtures: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for fixture in fixtures:
        fields.extend(_safe_names(fixture.get("query_params", [])))
        fields.extend(_safe_names(fixture.get("body_fields", [])))
        fields.extend(_safe_names(fixture.get("response_fields", [])))
    return sorted(dict.fromkeys(fields))


def _safe_names(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    names: list[str] = []
    for value in values:
        safe = _safe_field_name(str(value))
        if safe:
            names.append(safe)
    return sorted(dict.fromkeys(names))


def _safe_field_name(value: str) -> str | None:
    name = value.strip().replace(" ", "_")
    if not name or len(name) > 80:
        return None
    if not SAFE_FIELD_RE.match(name):
        return None
    lowered = name.lower()
    if lowered in {"authorization", "cookie"}:
        return None
    return lowered


def _path_template(path: str) -> str:
    parsed_path = urlparse(path).path or "/"
    segments = [segment for segment in parsed_path.split("/") if segment]
    templated = [_template_segment(segment) for segment in segments]
    return "/" + "/".join(templated) if templated else "/"


def _template_segment(segment: str) -> str:
    clean = segment.strip()
    if not clean:
        return ""
    if clean.startswith("{") and clean.endswith("}"):
        return "{" + (_safe_identifier(clean[1:-1]) or "id") + "}"
    lowered = clean.lower()
    if re.fullmatch(r"v\d+", lowered):
        return lowered
    if clean.isdigit() or UUID_RE.match(clean) or HEX_RE.match(clean) or (any(char.isdigit() for char in clean) and len(clean) > 24):
        return "{id}"
    safe = _safe_identifier(clean)
    return safe or "{id}"


def _operation_id(index: int, method: str, path_template: str) -> str:
    slug = path_template.strip("/").replace("{", "").replace("}", "").replace("/", "_").replace("-", "_")
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", slug).strip("_").lower() or "root"
    return f"op_{index + 1:03d}_{method.lower()}_{slug[:72]}"


def _route_param_hints(path: str) -> list[str]:
    hints: list[str] = []
    for segment in _path_template(path).split("/"):
        if segment.startswith("{") and segment.endswith("}"):
            hints.append(segment[1:-1])
    return hints


def _safe_identifier(value: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9_\-]+", "_", value.strip()).strip("_").lower()
    if len(identifier) > 80:
        return ""
    return identifier


def _has_hint(value: str, hints: set[str]) -> bool:
    lowered = value.lower()
    return any(hint in lowered for hint in hints)
