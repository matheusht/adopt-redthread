from __future__ import annotations

from typing import Any


def build_bridge_workflow_context(workflow_plan: dict[str, Any] | None) -> dict[str, Any]:
    if not workflow_plan:
        return {}
    alias_summary = workflow_plan.get("approved_binding_alias_summary", {})
    return {
        "workflow_count": workflow_plan.get("workflow_count", 0),
        "approved_binding_alias_count": workflow_plan.get("approved_binding_alias_count", 0),
        "approved_binding_alias_used_count": alias_summary.get("used_alias_count", 0),
        "approved_binding_aliases": alias_summary.get("loaded_aliases", []),
        "approved_binding_alias_usages": alias_summary.get("used_aliases", []),
    }
