from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def build_live_attack_plan(bundle: dict[str, Any]) -> dict[str, Any]:
    request_map = _request_map(bundle)
    cases = [build_live_attack_case(fixture, request_map) for fixture in bundle.get("fixtures", [])]
    return {
        "plan_id": _plan_id(bundle),
        "source": bundle.get("source", "unknown"),
        "input_file": bundle.get("input_file", "unknown"),
        "fixture_count": len(cases),
        "allowed_case_count": sum(1 for case in cases if case["allowed"]),
        "review_case_count": sum(1 for case in cases if case["approval_mode"] == "human_review"),
        "blocked_case_count": sum(1 for case in cases if case["approval_mode"] == "blocked"),
        "cases": cases,
    }


def build_live_attack_case(fixture: dict[str, Any], request_map: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    request = request_map.get((fixture["method"], fixture["path"]), {})
    execution_mode = _execution_mode(fixture)
    approval_mode = _approval_mode(execution_mode)
    allowed = execution_mode == "live_safe_read"
    return {
        "case_id": fixture["name"],
        "method": fixture["method"],
        "path": fixture["path"],
        "execution_mode": execution_mode,
        "approval_mode": approval_mode,
        "target_env": "captured_target",
        "auth_context_required": bool(fixture.get("auth_hints")),
        "max_replay_attempts": 1 if allowed else 0,
        "side_effect_risk": _side_effect_risk(fixture),
        "allowed": allowed,
        "reasons": fixture.get("reasons", []),
        "request_blueprint": {
            "url": request.get("url"),
            "host": request.get("host"),
            "header_names": request.get("header_names", []),
            "query_params": fixture.get("query_params", []),
            "body_fields": fixture.get("body_fields", []),
        },
    }


def build_execution_policy(fixture: dict[str, Any]) -> dict[str, Any]:
    execution_mode = _execution_mode(fixture)
    allowed = execution_mode == "live_safe_read"
    return {
        "execution_mode": execution_mode,
        "approval_mode": _approval_mode(execution_mode),
        "target_env": "captured_target",
        "auth_context_required": bool(fixture.get("auth_hints")),
        "max_replay_attempts": 1 if allowed else 0,
        "side_effect_risk": _side_effect_risk(fixture),
        "allowed": allowed,
    }


def _request_map(bundle: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    input_file = Path(str(bundle.get("input_file", "")))
    if not input_file.exists():
        return {}
    try:
        raw = json.loads(input_file.read_text())
    except json.JSONDecodeError:
        return {}
    entries = raw.get("log", {}).get("entries", [])
    mapping: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in entries:
        request = entry.get("request", {})
        method = str(request.get("method", "GET")).upper()
        url = str(request.get("url", ""))
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            continue
        key = (method, parsed.path or "/")
        mapping.setdefault(
            key,
            {
                "url": f"{parsed.scheme}://{parsed.netloc}{parsed.path or '/'}",
                "host": parsed.netloc,
                "header_names": sorted(
                    {
                        str(header.get("name", "")).lower()
                        for header in request.get("headers", [])
                        if header.get("name")
                    }
                ),
            },
        )
    return mapping


def _execution_mode(fixture: dict[str, Any]) -> str:
    if fixture.get("replay_class") == "safe_read" and fixture.get("method") == "GET":
        return "live_safe_read"
    if fixture.get("replay_class") == "safe_read_with_review" and fixture.get("method") == "GET":
        return "live_safe_read_with_review"
    if fixture.get("replay_class") == "sandbox_only":
        return "sandbox_only"
    return "manual_review"


def _approval_mode(execution_mode: str) -> str:
    if execution_mode == "live_safe_read":
        return "auto"
    if execution_mode in {"live_safe_read_with_review", "manual_review"}:
        return "human_review"
    return "blocked"


def _side_effect_risk(fixture: dict[str, Any]) -> str:
    if fixture.get("replay_class") == "sandbox_only":
        return "high"
    if fixture.get("method") in {"POST", "PUT", "PATCH", "DELETE"}:
        return "medium"
    return "low"


def _plan_id(bundle: dict[str, Any]) -> str:
    input_name = str(bundle.get("input_file", "bundle")).split("/")[-1].replace(".", "-")
    return f"live-plan-{bundle.get('source', 'unknown')}-{input_name}"
