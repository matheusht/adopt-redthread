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


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []
