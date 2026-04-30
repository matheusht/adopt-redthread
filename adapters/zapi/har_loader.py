from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from adapters.zapi.schema import ZapiEndpoint

DEFAULT_DENYLIST = {
    "google-analytics.com",
    "googletagmanager.com",
    "googleapis.com",
    "agora.io",
    "imsdks.com",
    "easemob.com",
    "google.com",
}
STATIC_HINTS = {".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".woff", ".woff2"}
TELEMETRY_PATH_HINTS = {"/event/report", "/collect", "/firelog", "/analytics"}
API_PATH_HINTS = {"/api/", "/weaver/api/", "/graphql"}
AUTH_HEADER_HINTS = {"authorization", "cookie", "x-token", "x-api-key", "x-sign"}


def load_har_export(path: str | Path) -> list[ZapiEndpoint]:
    raw = json.loads(Path(path).read_text())
    entries = raw.get("log", {}).get("entries", [])
    candidates = [_entry_to_endpoint(entry) for entry in entries]
    kept = [candidate for candidate in candidates if candidate is not None]
    return _dedupe_endpoints(kept)


def _entry_to_endpoint(entry: dict[str, Any]) -> ZapiEndpoint | None:
    request = entry.get("request", {})
    response = entry.get("response", {})
    url = str(request.get("url", ""))
    method = str(request.get("method", "GET")).upper()
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path or "/"

    if not host or not _looks_like_app_api(host=host, path=path, response=response):
        return None
    if _is_telemetry_noise(path):
        return None

    query_params = sorted({item.get("name", "") for item in request.get("queryString", []) if item.get("name")})
    body_fields = sorted(_extract_json_field_names(request.get("postData", {}).get("text")))
    response_fields = sorted(_extract_json_field_names(response.get("content", {}).get("text")))
    auth_hints = sorted(
        {
            header.get("name", "").lower()
            for header in request.get("headers", [])
            if header.get("name", "").lower() in AUTH_HEADER_HINTS
        }
    )

    return ZapiEndpoint(
        method=method,
        path=path,
        summary=f"HAR discovered endpoint: {path}",
        description=f"Observed in HAR capture against {host} with status {response.get('status', 'unknown')}",
        query_params=query_params,
        body_fields=body_fields,
        response_fields=response_fields,
        auth_hints=auth_hints,
        source="zapi_har",
        workflow_group=_infer_workflow_group(path),
    )


def _looks_like_app_api(*, host: str, path: str, response: dict[str, Any]) -> bool:
    if any(blocked in host for blocked in DEFAULT_DENYLIST):
        return False
    if any(path.endswith(suffix) for suffix in STATIC_HINTS):
        return False
    if not any(hint in path for hint in API_PATH_HINTS):
        return False

    mime_type = str(response.get("content", {}).get("mimeType", "")).lower()
    if mime_type and any(asset in mime_type for asset in {"image/", "text/css", "javascript", "font/", "audio/", "video/"}):
        return False
    return True


def _is_telemetry_noise(path: str) -> bool:
    return any(hint in path for hint in TELEMETRY_PATH_HINTS)


def _extract_json_field_names(raw_text: str | None) -> set[str]:
    if not raw_text:
        return set()
    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return set()
    names: set[str] = set()
    _collect_field_names(payload, names)
    return names


def _collect_field_names(value: Any, names: set[str], prefix: str = "", depth: int = 0) -> None:
    if depth > 2:
        return
    if isinstance(value, dict):
        for key, nested in value.items():
            label = f"{prefix}.{key}" if prefix else str(key)
            names.add(label)
            _collect_field_names(nested, names, label, depth + 1)
    elif isinstance(value, list) and value:
        _collect_field_names(value[0], names, prefix, depth + 1)


def _dedupe_endpoints(endpoints: list[ZapiEndpoint]) -> list[ZapiEndpoint]:
    deduped: dict[tuple[str, str], ZapiEndpoint] = {}
    for endpoint in endpoints:
        key = (endpoint.method, endpoint.path)
        current = deduped.get(key)
        if current is None:
            deduped[key] = endpoint
            continue
        deduped[key] = ZapiEndpoint(
            method=endpoint.method,
            path=endpoint.path,
            summary=current.summary,
            description=current.description,
            query_params=sorted(set(current.query_params + endpoint.query_params)),
            body_fields=sorted(set(current.body_fields + endpoint.body_fields)),
            response_fields=sorted(set(current.response_fields + endpoint.response_fields)),
            auth_hints=sorted(set(current.auth_hints + endpoint.auth_hints)),
            source=current.source,
            workflow_group=current.workflow_group,
        )
    return list(deduped.values())


def _infer_workflow_group(path: str) -> str:
    parts = [part for part in path.strip("/").split("/") if part]
    if "api" in parts:
        api_index = parts.index("api")
        if len(parts) > api_index + 2:
            return parts[api_index + 2]
    if len(parts) >= 2:
        return parts[-2]
    return "default"
