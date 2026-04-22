from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

ALLOWED_AUTH_HEADER_NAMES = {"authorization", "cookie", "x-api-key", "x-token", "x-sign"}
WRITE_METHODS = {"POST", "PUT", "PATCH"}


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
        return bool(allow_reviewed_auth and auth_payload and auth_payload.get("approved") and host_allowed(case, auth_payload))
    if case.get("execution_mode") == "live_reviewed_write_staging":
        return write_case_approved(case, write_payload, allow_reviewed_writes)
    return False


def approved_headers(case: dict[str, Any], auth_payload: dict[str, Any] | None, allow_reviewed_auth: bool) -> dict[str, str]:
    if case.get("execution_mode") != "live_safe_read_with_approved_auth":
        return {}
    if not allow_reviewed_auth or not auth_payload or not auth_payload.get("approved") or not host_allowed(case, auth_payload):
        return {}
    observed = {str(name).lower() for name in case.get("request_blueprint", {}).get("header_names", [])}
    allowed_names = {str(name).lower() for name in auth_payload.get("allowed_header_names", [])} or ALLOWED_AUTH_HEADER_NAMES
    approved: dict[str, str] = {}
    for key, value in auth_payload.get("headers", {}).items():
        name = str(key).lower()
        if name in ALLOWED_AUTH_HEADER_NAMES and name in allowed_names and name in observed:
            approved[name] = str(value)
    return approved


def approved_write_request(case: dict[str, Any], write_payload: dict[str, Any] | None, allow_reviewed_writes: bool) -> tuple[dict[str, str], bytes | None]:
    if not write_case_approved(case, write_payload, allow_reviewed_writes):
        return {}, None
    assert write_payload is not None
    case_approval = write_payload.get("case_approvals", {}).get(case.get("case_id"), {})
    headers = {str(key).lower(): str(value) for key, value in case_approval.get("headers", {}).items()}
    if case_approval.get("use_bound_headers") and case.get("request_blueprint", {}).get("headers"):
        headers.update({str(key).lower(): str(value) for key, value in case.get("request_blueprint", {}).get("headers", {}).items()})
    body = case_approval.get("json_body")
    if case_approval.get("use_bound_body_json") and case.get("request_blueprint", {}).get("body_json") is not None:
        body = case.get("request_blueprint", {}).get("body_json")
    if body is None:
        return headers, None
    headers.setdefault("content-type", "application/json")
    return headers, json.dumps(body).encode("utf-8")


def write_case_approved(case: dict[str, Any], write_payload: dict[str, Any] | None, allow_reviewed_writes: bool) -> bool:
    if case.get("execution_mode") != "live_reviewed_write_staging":
        return False
    if not allow_reviewed_writes or not write_payload or not write_payload.get("approved"):
        return False
    if str(write_payload.get("target_env", "")).lower() != "staging" or not write_host_allowed(case, write_payload):
        return False
    case_approval = write_payload.get("case_approvals", {}).get(case.get("case_id"), {})
    if not case_approval:
        return False
    return str(case_approval.get("method", "")).upper() == str(case.get("method", "")).upper() and str(case_approval.get("path", "")) == str(case.get("path", ""))


def host_allowed(case: dict[str, Any], context: dict[str, Any]) -> bool:
    host = str(case.get("request_blueprint", {}).get("host", "")).lower() or urlparse(str(case.get("request_blueprint", {}).get("url", ""))).netloc.lower()
    allowed_hosts = [str(item).lower() for item in context.get("target_hosts", [])]
    return bool(host and allowed_hosts and host in allowed_hosts)


def write_host_allowed(case: dict[str, Any], context: dict[str, Any]) -> bool:
    target_base_url = str(context.get("target_base_url", "")).strip()
    if target_base_url:
        host = urlparse(target_base_url).netloc.lower()
        allowed_hosts = [str(item).lower() for item in context.get("target_hosts", [])]
        return bool(host and allowed_hosts and host in allowed_hosts)
    return host_allowed(case, context)


def request_url(case: dict[str, Any], write_payload: dict[str, Any] | None) -> str:
    if case.get("execution_mode") == "live_reviewed_write_staging" and write_payload:
        base = str(write_payload.get("target_base_url", "")).rstrip("/")
        path = str(case.get("path", ""))
        if base and path:
            return f"{base}{path}"
    return str(case.get("request_blueprint", {}).get("url", ""))
