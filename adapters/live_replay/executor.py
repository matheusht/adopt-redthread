from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ALLOWED_AUTH_HEADER_NAMES = {"authorization", "cookie", "x-api-key", "x-token", "x-sign"}
WRITE_METHODS = {"POST", "PUT", "PATCH"}


def execute_live_safe_replay(
    plan: dict[str, Any] | str | Path,
    *,
    auth_context: dict[str, Any] | str | Path | None = None,
    allow_reviewed_auth: bool = False,
    write_context: dict[str, Any] | str | Path | None = None,
    allow_reviewed_writes: bool = False,
    output_path: str | Path | None = None,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    payload = _load_jsonish(plan)
    auth_payload = _load_optional_context(auth_context)
    write_payload = _load_optional_context(write_context)
    results = [
        execute_live_case(case, timeout_seconds, auth_payload, allow_reviewed_auth, write_payload, allow_reviewed_writes)
        for case in payload.get("cases", [])
        if is_live_case_executable(case, auth_payload, allow_reviewed_auth, write_payload, allow_reviewed_writes)
    ]
    summary = {
        "plan_id": payload.get("plan_id", "unknown"),
        "allowed_case_count": payload.get("allowed_case_count", len(results)),
        "executed_case_count": len(results),
        "success_count": sum(1 for result in results if result["success"]),
        "auth_context_used": bool(auth_payload),
        "write_context_used": bool(write_payload),
        "results": results,
    }
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def execute_live_case(
    case: dict[str, Any],
    timeout_seconds: int,
    auth_payload: dict[str, Any] | None,
    allow_reviewed_auth: bool,
    write_payload: dict[str, Any] | None,
    allow_reviewed_writes: bool,
) -> dict[str, Any]:
    method = str(case.get("method", "GET")).upper()
    blueprint = case.get("request_blueprint", {})
    url = _request_url(case, write_payload)
    if not url:
        return {"case_id": case.get("case_id", "unknown"), "success": False, "error": "case_not_executable"}

    headers: dict[str, str] = {}
    data: bytes | None = None

    if method == "GET":
        headers = _approved_headers(case, auth_payload, allow_reviewed_auth)
    elif method in WRITE_METHODS:
        headers, data = _approved_write_request(case, write_payload, allow_reviewed_writes)
    else:
        return {"case_id": case.get("case_id", "unknown"), "success": False, "error": "case_not_executable"}

    request = Request(url=url, method=method, headers=headers, data=data)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            body = response.read(2000).decode("utf-8", errors="replace")
            return {
                "case_id": case.get("case_id", "unknown"),
                "method": method,
                "success": True,
                "status_code": response.status,
                "content_type": response.headers.get("Content-Type"),
                "auth_applied": bool(headers),
                "header_names_sent": sorted(headers.keys()),
                "body_preview": body,
            }
    except HTTPError as exc:
        return {
            "case_id": case.get("case_id", "unknown"),
            "method": method,
            "success": False,
            "status_code": exc.code,
            "auth_applied": bool(headers),
            "header_names_sent": sorted(headers.keys()),
            "error": "http_error",
        }
    except URLError as exc:
        return {
            "case_id": case.get("case_id", "unknown"),
            "method": method,
            "success": False,
            "auth_applied": bool(headers),
            "header_names_sent": sorted(headers.keys()),
            "error": f"url_error: {exc.reason}",
        }


def is_live_case_executable(
    case: dict[str, Any],
    auth_payload: dict[str, Any] | None,
    allow_reviewed_auth: bool,
    write_payload: dict[str, Any] | None,
    allow_reviewed_writes: bool,
) -> bool:
    if case.get("allowed"):
        return True
    if case.get("execution_mode") == "live_safe_read_with_approved_auth":
        if not allow_reviewed_auth or not auth_payload or not auth_payload.get("approved"):
            return False
        return _host_allowed(case, auth_payload)
    if case.get("execution_mode") == "live_reviewed_write_staging":
        return _write_case_approved(case, write_payload, allow_reviewed_writes)
    return False


def _approved_headers(case: dict[str, Any], auth_payload: dict[str, Any] | None, allow_reviewed_auth: bool) -> dict[str, str]:
    if case.get("execution_mode") != "live_safe_read_with_approved_auth":
        return {}
    if not allow_reviewed_auth or not auth_payload or not auth_payload.get("approved") or not _host_allowed(case, auth_payload):
        return {}

    observed = {str(name).lower() for name in case.get("request_blueprint", {}).get("header_names", [])}
    allowed_names = {str(name).lower() for name in auth_payload.get("allowed_header_names", [])} or ALLOWED_AUTH_HEADER_NAMES
    headers = auth_payload.get("headers", {})
    approved: dict[str, str] = {}
    for key, value in headers.items():
        name = str(key).lower()
        if name not in ALLOWED_AUTH_HEADER_NAMES:
            continue
        if name not in allowed_names or name not in observed:
            continue
        approved[name] = str(value)
    return approved


def _approved_write_request(
    case: dict[str, Any],
    write_payload: dict[str, Any] | None,
    allow_reviewed_writes: bool,
) -> tuple[dict[str, str], bytes | None]:
    if not _write_case_approved(case, write_payload, allow_reviewed_writes):
        return {}, None
    assert write_payload is not None
    approvals = write_payload.get("case_approvals", {})
    case_approval = approvals.get(case.get("case_id"), {})
    headers = {str(key).lower(): str(value) for key, value in case_approval.get("headers", {}).items()}
    body = case_approval.get("json_body")
    if body is None:
        return headers, None
    headers.setdefault("content-type", "application/json")
    return headers, json.dumps(body).encode("utf-8")


def _write_case_approved(case: dict[str, Any], write_payload: dict[str, Any] | None, allow_reviewed_writes: bool) -> bool:
    if case.get("execution_mode") != "live_reviewed_write_staging":
        return False
    if not allow_reviewed_writes or not write_payload or not write_payload.get("approved"):
        return False
    if str(write_payload.get("target_env", "")).lower() != "staging":
        return False
    if not _write_host_allowed(case, write_payload):
        return False
    approvals = write_payload.get("case_approvals", {})
    case_approval = approvals.get(case.get("case_id"), {})
    if not case_approval:
        return False
    if str(case_approval.get("method", "")).upper() != str(case.get("method", "")).upper():
        return False
    if str(case_approval.get("path", "")) != str(case.get("path", "")):
        return False
    return True


def _host_allowed(case: dict[str, Any], context: dict[str, Any]) -> bool:
    host = str(case.get("request_blueprint", {}).get("host", "")).lower()
    if not host:
        url = str(case.get("request_blueprint", {}).get("url", ""))
        host = urlparse(url).netloc.lower()
    allowed_hosts = [str(item).lower() for item in context.get("target_hosts", [])]
    return bool(host and allowed_hosts and host in allowed_hosts)


def _write_host_allowed(case: dict[str, Any], context: dict[str, Any]) -> bool:
    target_base_url = str(context.get("target_base_url", "")).strip()
    if target_base_url:
        host = urlparse(target_base_url).netloc.lower()
        allowed_hosts = [str(item).lower() for item in context.get("target_hosts", [])]
        return bool(host and allowed_hosts and host in allowed_hosts)
    return _host_allowed(case, context)


def _request_url(case: dict[str, Any], write_payload: dict[str, Any] | None) -> str:
    if case.get("execution_mode") == "live_reviewed_write_staging" and write_payload:
        base = str(write_payload.get("target_base_url", "")).rstrip("/")
        path = str(case.get("path", ""))
        if base and path:
            return f"{base}{path}"
    return str(case.get("request_blueprint", {}).get("url", ""))


def _load_optional_context(value: dict[str, Any] | str | Path | None) -> dict[str, Any] | None:
    if value is None:
        return None
    payload = _load_jsonish(value)
    return payload if isinstance(payload, dict) else None


def _load_jsonish(value: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return json.loads(Path(value).read_text())
