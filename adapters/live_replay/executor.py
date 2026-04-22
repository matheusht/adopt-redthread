from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ALLOWED_METHODS = {"GET"}
ALLOWED_AUTH_HEADER_NAMES = {"authorization", "cookie", "x-api-key", "x-token", "x-sign"}


def execute_live_safe_replay(
    plan: dict[str, Any] | str | Path,
    *,
    auth_context: dict[str, Any] | str | Path | None = None,
    allow_reviewed_auth: bool = False,
    output_path: str | Path | None = None,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    payload = _load_jsonish(plan)
    context = _load_auth_context(auth_context)
    results = [
        _execute_case(case, timeout_seconds, context, allow_reviewed_auth)
        for case in payload.get("cases", [])
        if _is_executable(case, context, allow_reviewed_auth)
    ]
    summary = {
        "plan_id": payload.get("plan_id", "unknown"),
        "allowed_case_count": payload.get("allowed_case_count", len(results)),
        "executed_case_count": len(results),
        "success_count": sum(1 for result in results if result["success"]),
        "auth_context_used": bool(context),
        "results": results,
    }
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def _execute_case(case: dict[str, Any], timeout_seconds: int, context: dict[str, Any] | None, allow_reviewed_auth: bool) -> dict[str, Any]:
    method = str(case.get("method", "GET")).upper()
    blueprint = case.get("request_blueprint", {})
    url = blueprint.get("url")
    if method not in ALLOWED_METHODS or not url:
        return {"case_id": case.get("case_id", "unknown"), "success": False, "error": "case_not_executable"}

    headers = _approved_headers(case, context, allow_reviewed_auth)
    request = Request(url=url, method=method, headers=headers)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            body = response.read(2000).decode("utf-8", errors="replace")
            return {
                "case_id": case.get("case_id", "unknown"),
                "success": True,
                "status_code": response.status,
                "content_type": response.headers.get("Content-Type"),
                "auth_applied": bool(headers),
                "auth_header_names_sent": sorted(headers.keys()),
                "body_preview": body,
            }
    except HTTPError as exc:
        return {
            "case_id": case.get("case_id", "unknown"),
            "success": False,
            "status_code": exc.code,
            "auth_applied": bool(headers),
            "auth_header_names_sent": sorted(headers.keys()),
            "error": "http_error",
        }
    except URLError as exc:
        return {
            "case_id": case.get("case_id", "unknown"),
            "success": False,
            "auth_applied": bool(headers),
            "auth_header_names_sent": sorted(headers.keys()),
            "error": f"url_error: {exc.reason}",
        }


def _is_executable(case: dict[str, Any], context: dict[str, Any] | None, allow_reviewed_auth: bool) -> bool:
    if case.get("allowed"):
        return True
    if case.get("execution_mode") != "live_safe_read_with_approved_auth":
        return False
    if not allow_reviewed_auth or not context or not context.get("approved"):
        return False
    return _host_allowed(case, context)


def _approved_headers(case: dict[str, Any], context: dict[str, Any] | None, allow_reviewed_auth: bool) -> dict[str, str]:
    if case.get("execution_mode") != "live_safe_read_with_approved_auth":
        return {}
    if not allow_reviewed_auth or not context or not context.get("approved") or not _host_allowed(case, context):
        return {}

    observed = {str(name).lower() for name in case.get("request_blueprint", {}).get("header_names", [])}
    allowed_names = {str(name).lower() for name in context.get("allowed_header_names", [])} or ALLOWED_AUTH_HEADER_NAMES
    headers = context.get("headers", {})
    approved: dict[str, str] = {}
    for key, value in headers.items():
        name = str(key).lower()
        if name not in ALLOWED_AUTH_HEADER_NAMES:
            continue
        if name not in allowed_names or name not in observed:
            continue
        approved[name] = str(value)
    return approved


def _host_allowed(case: dict[str, Any], context: dict[str, Any]) -> bool:
    host = str(case.get("request_blueprint", {}).get("host", "")).lower()
    if not host:
        url = str(case.get("request_blueprint", {}).get("url", ""))
        host = urlparse(url).netloc.lower()
    allowed_hosts = [str(item).lower() for item in context.get("target_hosts", [])]
    return bool(host and allowed_hosts and host in allowed_hosts)


def _load_auth_context(auth_context: dict[str, Any] | str | Path | None) -> dict[str, Any] | None:
    if auth_context is None:
        return None
    payload = _load_jsonish(auth_context)
    return payload if isinstance(payload, dict) else None


def _load_jsonish(value: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return json.loads(Path(value).read_text())
