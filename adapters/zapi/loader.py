from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.zapi.schema import RedThreadFixture, ZapiEndpoint


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DESTRUCTIVE_HINTS = {"delete", "remove", "destroy", "purge"}
SENSITIVE_HINTS = {"token", "secret", "password", "ssn", "email", "phone", "key"}
AUTH_HINTS = {"authorization", "cookie", "session", "bearer", "x-api-key"}


def load_zapi_export(path: str | Path) -> list[ZapiEndpoint]:
    raw = json.loads(Path(path).read_text())
    endpoints = raw.get("endpoints", [])
    return [parse_endpoint(item) for item in endpoints]


def parse_endpoint(item: dict[str, Any]) -> ZapiEndpoint:
    return ZapiEndpoint(
        method=str(item.get("method", "GET")).upper(),
        path=str(item.get("path", "/")),
        summary=str(item.get("summary", "")),
        description=str(item.get("description", "")),
        query_params=_as_string_list(item.get("query_params", [])),
        body_fields=_as_string_list(item.get("body_fields", [])),
        auth_hints=_as_string_list(item.get("auth_hints", [])),
        workflow_group=str(item.get("workflow_group", "default")),
    )


def classify_fixture(endpoint: ZapiEndpoint) -> RedThreadFixture:
    reasons: list[str] = []
    method = endpoint.method.upper()
    haystack = " ".join(
        [endpoint.path, endpoint.summary, endpoint.description, *endpoint.body_fields, *endpoint.query_params]
    ).lower()
    auth_hints = [hint.lower() for hint in endpoint.auth_hints]

    if method in WRITE_METHODS:
        reasons.append("mutating_http_method")

    if any(word in haystack for word in DESTRUCTIVE_HINTS):
        reasons.append("destructive_semantics")

    if any(word in haystack for word in SENSITIVE_HINTS):
        reasons.append("sensitive_data_surface")

    if any(word in " ".join(auth_hints) for word in AUTH_HINTS):
        reasons.append("authenticated_surface")

    endpoint_family = _infer_endpoint_family(endpoint.path)
    data_sensitivity = _infer_data_sensitivity(haystack)
    tenant_scope = _infer_tenant_scope(endpoint.path, haystack)
    approval_required = _needs_approval(method=method, reasons=reasons, endpoint_family=endpoint_family)
    candidate_attack_types = _candidate_attack_types(
        method=method,
        reasons=reasons,
        endpoint_family=endpoint_family,
        data_sensitivity=data_sensitivity,
    )
    risk_level, replay_class = _decide_policy(method=method, reasons=reasons)

    return RedThreadFixture(
        name=_fixture_name(endpoint),
        method=endpoint.method,
        path=endpoint.path,
        summary=endpoint.summary or endpoint.description,
        query_params=endpoint.query_params,
        body_fields=endpoint.body_fields,
        auth_hints=endpoint.auth_hints,
        workflow_group=endpoint.workflow_group,
        risk_level=risk_level,
        replay_class=replay_class,
        approval_required=approval_required,
        tenant_scope=tenant_scope,
        data_sensitivity=data_sensitivity,
        endpoint_family=endpoint_family,
        candidate_attack_types=candidate_attack_types,
        reasons=reasons,
        source=endpoint.source,
    )


def build_fixture_bundle(path: str | Path) -> dict[str, Any]:
    endpoints = load_zapi_export(path)
    fixtures = [classify_fixture(endpoint) for endpoint in endpoints]
    return {
        "source": "zapi",
        "input_file": str(path),
        "fixture_count": len(fixtures),
        "fixtures": [fixture.to_dict() for fixture in fixtures],
    }


def _fixture_name(endpoint: ZapiEndpoint) -> str:
    clean_path = endpoint.path.strip("/").replace("/", "_").replace("{", "").replace("}", "") or "root"
    return f"{endpoint.method.lower()}_{clean_path}"


def _decide_policy(method: str, reasons: list[str]) -> tuple[str, str]:
    if "destructive_semantics" in reasons:
        return "high", "sandbox_only"
    if method in WRITE_METHODS:
        return "medium", "manual_review"
    if "sensitive_data_surface" in reasons or "authenticated_surface" in reasons:
        return "medium", "safe_read_with_review"
    return "low", "safe_read"


def _infer_endpoint_family(path: str) -> str:
    parts = [part for part in path.strip("/").split("/") if part and not part.startswith("{")]
    if not parts:
        return "general"
    if parts[0] == "api" and len(parts) > 1:
        return parts[1]
    return parts[0]


def _infer_data_sensitivity(haystack: str) -> str:
    if any(word in haystack for word in {"password", "token", "secret", "key"}):
        return "secret"
    if any(word in haystack for word in {"email", "phone", "ssn"}):
        return "pii"
    return "internal"


def _infer_tenant_scope(path: str, haystack: str) -> str:
    if any(word in haystack for word in {"tenant", "org", "organization"}):
        return "multi_tenant"
    if "/admin/" in path:
        return "cross_tenant_risk"
    return "single_tenant"


def _needs_approval(method: str, reasons: list[str], endpoint_family: str) -> bool:
    return method in WRITE_METHODS or "destructive_semantics" in reasons or endpoint_family == "admin"


def _candidate_attack_types(
    *,
    method: str,
    reasons: list[str],
    endpoint_family: str,
    data_sensitivity: str,
) -> list[str]:
    attack_types: list[str] = []

    if method in WRITE_METHODS:
        attack_types.append("unsafe_write_activation")
    if "authenticated_surface" in reasons:
        attack_types.append("authorization_bypass")
    if endpoint_family == "admin":
        attack_types.append("privilege_escalation")
    if data_sensitivity in {"pii", "secret"}:
        attack_types.append("data_exfiltration")
    if "destructive_semantics" in reasons:
        attack_types.append("destructive_action_abuse")

    if not attack_types:
        attack_types.append("overbroad_data_access")

    return attack_types


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []
