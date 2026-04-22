from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ALLOWED_METHODS = {"GET"}


def execute_live_safe_replay(
    plan: dict[str, Any] | str | Path,
    *,
    output_path: str | Path | None = None,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    payload = _load_plan(plan)
    results = [_execute_case(case, timeout_seconds) for case in payload.get("cases", []) if case.get("allowed")]
    summary = {
        "plan_id": payload.get("plan_id", "unknown"),
        "allowed_case_count": payload.get("allowed_case_count", len(results)),
        "executed_case_count": len(results),
        "success_count": sum(1 for result in results if result["success"]),
        "results": results,
    }
    if output_path is not None:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def _execute_case(case: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    method = str(case.get("method", "GET")).upper()
    url = case.get("request_blueprint", {}).get("url")
    if method not in ALLOWED_METHODS or not url:
        return {
            "case_id": case.get("case_id", "unknown"),
            "success": False,
            "error": "case_not_executable",
        }

    request = Request(url=url, method=method)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            body = response.read(2000).decode("utf-8", errors="replace")
            return {
                "case_id": case.get("case_id", "unknown"),
                "success": True,
                "status_code": response.status,
                "content_type": response.headers.get("Content-Type"),
                "body_preview": body,
            }
    except HTTPError as exc:
        return {
            "case_id": case.get("case_id", "unknown"),
            "success": False,
            "status_code": exc.code,
            "error": "http_error",
        }
    except URLError as exc:
        return {
            "case_id": case.get("case_id", "unknown"),
            "success": False,
            "error": f"url_error: {exc.reason}",
        }


def _load_plan(plan: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(plan, dict):
        return plan
    return json.loads(Path(plan).read_text())
