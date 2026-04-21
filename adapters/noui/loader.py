from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.zapi.schema import RedThreadFixture

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DESTRUCTIVE_HINTS = {"delete", "remove", "cancel", "disable", "revoke"}
SENSITIVE_HINTS = {"email", "phone", "token", "cookie", "session", "profile", "account", "user"}


def load_noui_server(path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = Path(path)
    if manifest_path.is_dir():
        server_dir = manifest_path
        manifest_path = server_dir / "manifest.json"
        tools_path = server_dir / "tools.json"
    else:
        server_dir = manifest_path.parent
        tools_path = server_dir / "tools.json"
    manifest = json.loads(manifest_path.read_text())
    tools = json.loads(tools_path.read_text())
    return manifest, tools


def tool_to_fixture(tool: dict[str, Any], manifest: dict[str, Any]) -> RedThreadFixture:
    method = str(tool.get("method", "GET")).upper()
    path = str(tool.get("path", "/"))
    auth = manifest.get("auth", {})
    params = tool.get("params", [])
    response_fields = tool.get("response_fields", [])
    haystack = " ".join(
        [
            tool.get("name", ""),
            tool.get("description", ""),
            path,
            auth.get("strategy", ""),
            auth.get("notes", ""),
            *(item.get("name", "") for item in params if isinstance(item, dict)),
            *(item.get("name", "") for item in response_fields if isinstance(item, dict)),
        ]
    ).lower()

    reasons: list[str] = []
    if method in WRITE_METHODS:
        reasons.append("mutating_http_method")
    if auth.get("requires_auth"):
        reasons.append("authenticated_surface")
    if any(word in haystack for word in DESTRUCTIVE_HINTS):
        reasons.append("destructive_semantics")
    if tool.get("execution_strategy") == "cdp_browser_fetch":
        reasons.append("browser_session_runtime")
    if any(word in haystack for word in SENSITIVE_HINTS):
        reasons.append("sensitive_data_surface")

    endpoint_family = _endpoint_family(path, manifest)
    data_sensitivity = _data_sensitivity(haystack, auth_required=bool(auth.get("requires_auth")))
    candidate_attack_types = _candidate_attack_types(
        method=method,
        auth_required=bool(auth.get("requires_auth")),
        reasons=reasons,
        data_sensitivity=data_sensitivity,
    )
    risk_level, replay_class = _policy(method=method, reasons=reasons, auth_required=bool(auth.get("requires_auth")))

    return RedThreadFixture(
        name=str(tool.get("name", "noui_tool")),
        method=method,
        path=path,
        summary=str(tool.get("description", "")),
        query_params=[item.get("name", "") for item in params if item.get("source") == "query"],
        body_fields=[item.get("name", "") for item in params if item.get("source") != "query"],
        auth_hints=[auth.get("strategy", "none"), tool.get("execution_strategy", "http")],
        workflow_group=str(manifest.get("workflow", {}).get("name", manifest.get("server_id", "default"))),
        risk_level=risk_level,
        replay_class=replay_class,
        approval_required=method in WRITE_METHODS or auth.get("requires_auth", False),
        tenant_scope="single_tenant",
        data_sensitivity=data_sensitivity,
        endpoint_family=endpoint_family,
        candidate_attack_types=candidate_attack_types,
        reasons=reasons,
        source="noui_mcp",
    )


def build_noui_fixture_bundle(path: str | Path) -> dict[str, Any]:
    manifest, tools = load_noui_server(path)
    fixtures = [tool_to_fixture(tool, manifest) for tool in tools]
    return {
        "source": "noui_mcp",
        "ingestion_mode": "mcp_server",
        "input_file": str(path),
        "server_id": manifest.get("server_id", "unknown"),
        "fixture_count": len(fixtures),
        "fixtures": [fixture.to_dict() for fixture in fixtures],
    }


def _endpoint_family(path: str, manifest: dict[str, Any]) -> str:
    parts = [part for part in path.strip("/").split("/") if part]
    if parts:
        return parts[0].lower().replace("-", "_")
    return str(manifest.get("app", {}).get("slug", "general")).replace("-", "_")


def _data_sensitivity(haystack: str, *, auth_required: bool) -> str:
    if any(word in haystack for word in {"token", "cookie", "session"}):
        return "secret"
    if any(word in haystack for word in {"email", "phone", "profile", "account", "user"}):
        return "pii"
    return "internal" if auth_required else "public"


def _candidate_attack_types(*, method: str, auth_required: bool, reasons: list[str], data_sensitivity: str) -> list[str]:
    attack_types: list[str] = []
    if method in WRITE_METHODS:
        attack_types.append("unsafe_write_activation")
    if auth_required:
        attack_types.append("authorization_bypass")
        attack_types.append("sensitive_workflow_access")
    if data_sensitivity in {"pii", "secret"}:
        attack_types.append("data_exfiltration")
    if "destructive_semantics" in reasons:
        attack_types.append("destructive_action_abuse")
    if method == "GET":
        attack_types.append("overbroad_data_access")
    if "browser_session_runtime" in reasons:
        attack_types.append("action_selection_confusion")
    return list(dict.fromkeys(attack_types or ["overbroad_data_access"]))


def _policy(*, method: str, reasons: list[str], auth_required: bool) -> tuple[str, str]:
    if "destructive_semantics" in reasons:
        return "high", "sandbox_only"
    if method in WRITE_METHODS:
        return "medium", "manual_review"
    if auth_required:
        return "medium", "safe_read_with_review"
    return "low", "safe_read"
