from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from adapters.live_replay.request_context import approved_headers, approved_write_request, is_live_case_executable, request_url, WRITE_METHODS
from adapters.live_replay.stream_capture import DEFAULT_STREAM_MAX_BYTES, build_response_result


def execute_live_safe_replay(
    plan: dict[str, Any] | str | Path,
    *,
    auth_context: dict[str, Any] | str | Path | None = None,
    allow_reviewed_auth: bool = False,
    write_context: dict[str, Any] | str | Path | None = None,
    allow_reviewed_writes: bool = False,
    output_path: str | Path | None = None,
    timeout_seconds: int = 10,
    stream_max_bytes: int = DEFAULT_STREAM_MAX_BYTES,
) -> dict[str, Any]:
    payload = _load_jsonish(plan)
    auth_payload = _load_optional_context(auth_context)
    write_payload = _load_optional_context(write_context)
    results = [
        execute_live_case(
            case,
            timeout_seconds,
            auth_payload,
            allow_reviewed_auth,
            write_payload,
            allow_reviewed_writes,
            stream_max_bytes=stream_max_bytes,
        )
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
        "stream_max_bytes": max(int(stream_max_bytes), 1),
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
    *,
    stream_max_bytes: int = DEFAULT_STREAM_MAX_BYTES,
) -> dict[str, Any]:
    method = str(case.get("method", "GET")).upper()
    url = request_url(case, write_payload)
    if not url:
        return {"case_id": case.get("case_id", "unknown"), "success": False, "error": "case_not_executable"}
    if method == "GET":
        headers, data = approved_headers(case, auth_payload, allow_reviewed_auth), None
    elif method in WRITE_METHODS:
        headers, data = approved_write_request(case, write_payload, allow_reviewed_writes)
    else:
        return {"case_id": case.get("case_id", "unknown"), "success": False, "error": "case_not_executable"}
    request = Request(url=url, method=method, headers=headers, data=data)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            return build_response_result(
                response,
                case_id=str(case.get("case_id", "unknown")),
                method=method,
                headers_sent=headers,
                stream_max_bytes=stream_max_bytes,
            )
    except HTTPError as exc:
        return {
            "case_id": case.get("case_id", "unknown"),
            "method": method,
            "success": False,
            "status_code": exc.code,
            "response_headers": {str(key).lower(): str(value) for key, value in exc.headers.items()},
            "response_json": None,
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
    except TimeoutError:
        return {
            "case_id": case.get("case_id", "unknown"),
            "method": method,
            "success": False,
            "auth_applied": bool(headers),
            "header_names_sent": sorted(headers.keys()),
            "error": "timeout",
        }


def _load_optional_context(value: dict[str, Any] | str | Path | None) -> dict[str, Any] | None:
    payload = None if value is None else _load_jsonish(value)
    return payload if isinstance(payload, dict) else None


def _load_jsonish(value: dict[str, Any] | str | Path) -> dict[str, Any]:
    return value if isinstance(value, dict) else json.loads(Path(value).read_text())
