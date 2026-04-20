from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from adapters.adopt_actions.schema import AdoptAction
from adapters.zapi.schema import RedThreadFixture

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def load_action_catalog(path: str | Path) -> list[AdoptAction]:
    raw = json.loads(Path(path).read_text())
    actions = raw.get("actions", [])
    return [parse_action(item) for item in actions]


def parse_action(item: dict[str, Any]) -> AdoptAction:
    return AdoptAction(
        name=str(item.get("name", "unnamed_action")),
        description=str(item.get("description", "")),
        method=str(item.get("method", "POST")).upper(),
        path=str(item.get("path", "/")),
        approval_required=bool(item.get("approval_required", False)),
        scopes=_as_string_list(item.get("scopes", [])),
        input_fields=_as_string_list(item.get("input_fields", [])),
        tags=_as_string_list(item.get("tags", [])),
        workflow_group=str(item.get("workflow_group", "default")),
    )


def action_to_fixture(action: AdoptAction) -> RedThreadFixture:
    haystack = " ".join([action.name, action.description, action.path, *action.input_fields, *action.tags]).lower()
    reasons: list[str] = []

    if action.method in WRITE_METHODS:
        reasons.append("mutating_http_method")
    if any(word in haystack for word in {"delete", "remove", "disable", "revoke"}):
        reasons.append("destructive_semantics")
    if any(word in haystack for word in {"admin", "role", "permission", "access"}):
        reasons.append("privileged_action_surface")
    if any(word in haystack for word in {"email", "phone", "token", "secret"}):
        reasons.append("sensitive_data_surface")

    endpoint_family = _infer_endpoint_family(action.path, action.tags)
    data_sensitivity = _infer_data_sensitivity(haystack)
    tenant_scope = "cross_tenant_risk" if "admin" in haystack else "single_tenant"
    approval_required = action.approval_required or action.method in WRITE_METHODS or "destructive_semantics" in reasons
    candidate_attack_types = _candidate_attack_types(action=action, reasons=reasons, data_sensitivity=data_sensitivity)
    risk_level, replay_class = _decide_policy(action=action, reasons=reasons)

    return RedThreadFixture(
        name=action.name,
        method=action.method,
        path=action.path,
        summary=action.description,
        query_params=[],
        body_fields=action.input_fields,
        auth_hints=action.scopes,
        workflow_group=action.workflow_group,
        risk_level=risk_level,
        replay_class=replay_class,
        approval_required=approval_required,
        tenant_scope=tenant_scope,
        data_sensitivity=data_sensitivity,
        endpoint_family=endpoint_family,
        candidate_attack_types=candidate_attack_types,
        reasons=reasons,
        source="adopt_actions",
    )


def build_action_fixture_bundle(path: str | Path) -> dict[str, Any]:
    actions = load_action_catalog(path)
    fixtures = [action_to_fixture(action) for action in actions]
    return {
        "source": "adopt_actions",
        "input_file": str(path),
        "fixture_count": len(fixtures),
        "fixtures": [fixture.to_dict() for fixture in fixtures],
    }


def _infer_endpoint_family(path: str, tags: list[str]) -> str:
    if tags:
        return tags[0]
    parts = [part for part in path.strip("/").split("/") if part and not part.startswith("{")]
    return parts[1] if len(parts) > 1 and parts[0] == "api" else (parts[0] if parts else "general")


def _infer_data_sensitivity(haystack: str) -> str:
    if any(word in haystack for word in {"token", "secret"}):
        return "secret"
    if any(word in haystack for word in {"email", "phone"}):
        return "pii"
    return "internal"


def _candidate_attack_types(*, action: AdoptAction, reasons: list[str], data_sensitivity: str) -> list[str]:
    attack_types: list[str] = []
    if action.method in WRITE_METHODS:
        attack_types.append("unsafe_write_activation")
    if action.approval_required:
        attack_types.append("approval_bypass")
    if "privileged_action_surface" in reasons:
        attack_types.append("privilege_escalation")
    if data_sensitivity in {"pii", "secret"}:
        attack_types.append("data_exfiltration")
    if "destructive_semantics" in reasons:
        attack_types.append("destructive_action_abuse")
    if not attack_types:
        attack_types.append("action_selection_confusion")
    return attack_types


def _decide_policy(*, action: AdoptAction, reasons: list[str]) -> tuple[str, str]:
    if "destructive_semantics" in reasons:
        return "high", "sandbox_only"
    if action.approval_required or action.method in WRITE_METHODS:
        return "medium", "manual_review"
    if "sensitive_data_surface" in reasons:
        return "medium", "safe_read_with_review"
    return "low", "safe_read"


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []
