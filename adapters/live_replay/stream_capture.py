from __future__ import annotations

from http.client import HTTPResponse
from typing import Any


DEFAULT_STREAM_MAX_BYTES = 512
_STREAM_CONTENT_TYPE_PREFIXES = (
    "text/event-stream",
    "application/x-ndjson",
    "application/stream+json",
)


def build_response_result(
    response: HTTPResponse,
    *,
    case_id: str,
    method: str,
    headers_sent: dict[str, str],
    stream_max_bytes: int,
) -> dict[str, Any]:
    response_headers = {str(key).lower(): str(value) for key, value in response.headers.items()}
    content_type = response.headers.get("Content-Type")
    result = {
        "case_id": case_id,
        "method": method,
        "status_code": response.status,
        "content_type": content_type,
        "response_headers": response_headers,
        "auth_applied": bool(headers_sent),
        "header_names_sent": sorted(headers_sent.keys()),
    }
    if is_streaming_response(response_headers):
        return _stream_result(response, result, stream_max_bytes)
    body = response.read(2000).decode("utf-8", errors="replace")
    return {
        **result,
        "success": True,
        "response_json": response_json(body),
        "body_preview": body,
    }


def is_streaming_response(headers: dict[str, str]) -> bool:
    content_type = str(headers.get("content-type", "")).lower()
    transfer_encoding = str(headers.get("transfer-encoding", "")).lower()
    if "chunked" in transfer_encoding:
        return True
    return any(content_type.startswith(prefix) for prefix in _STREAM_CONTENT_TYPE_PREFIXES)


def response_json(body: str) -> dict[str, Any] | None:
    import json

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _stream_result(response: HTTPResponse, result: dict[str, Any], stream_max_bytes: int) -> dict[str, Any]:
    budget = max(int(stream_max_bytes), 1)
    first_chunk = response.read(budget)
    preview = first_chunk.decode("utf-8", errors="replace")
    if not first_chunk:
        return {
            **result,
            "success": True,
            "response_json": None,
            "body_preview": "",
            "stream_opened": False,
            "first_chunk_bytes": 0,
            "first_chunk_preview": "",
            "stream_content_type": result.get("content_type"),
            "stream_read_budget_bytes": budget,
        }
    return {
        **result,
        "success": False,
        "error": "stream_open_partial_read",
        "response_json": None,
        "body_preview": preview,
        "stream_opened": True,
        "first_chunk_bytes": len(first_chunk),
        "first_chunk_preview": preview,
        "stream_content_type": result.get("content_type"),
        "stream_read_budget_bytes": budget,
    }
