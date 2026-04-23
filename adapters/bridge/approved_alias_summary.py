from __future__ import annotations

from typing import Any


def summarize_approved_aliases(approved_aliases: list[dict[str, Any]], workflows: list[dict[str, Any]]) -> dict[str, Any]:
    aliases = [_alias_record(item) for item in approved_aliases if _alias_record(item) is not None]
    usages = [
        usage
        for workflow in workflows
        for usage in _workflow_alias_usages(str(workflow.get("workflow_id", "unknown")), workflow.get("steps", []), aliases)
    ]
    return {
        "loaded_alias_count": len(aliases),
        "loaded_aliases": aliases,
        "used_alias_count": len(usages),
        "used_workflow_count": len({usage["workflow_id"] for usage in usages}),
        "used_aliases": usages,
    }


def workflow_alias_usage_summary(workflow: dict[str, Any], aliases: list[dict[str, str]]) -> dict[str, Any]:
    usages = _workflow_alias_usages(str(workflow.get("workflow_id", "unknown")), workflow.get("steps", []), aliases)
    return {
        "approved_binding_alias_used_count": len(usages),
        "approved_binding_alias_usages": usages,
    }


def _workflow_alias_usages(
    workflow_id: str,
    steps: list[dict[str, Any]],
    aliases: list[dict[str, str]],
) -> list[dict[str, Any]]:
    alias_keys = {
        (item["source_key"], item["target_path"]): item
        for item in aliases
    }
    usages: list[dict[str, Any]] = []
    for step in steps:
        for binding in step.get("response_bindings", []):
            key = (str(binding.get("source_key", "")), str(binding.get("target_path", "")))
            alias = alias_keys.get(key)
            if alias is None:
                continue
            usages.append(
                {
                    "workflow_id": workflow_id,
                    "case_id": str(step.get("case_id", "")),
                    "binding_id": str(binding.get("binding_id", "")),
                    "source_key": alias["source_key"],
                    "target_field": str(binding.get("target_field", "")),
                    "target_path": alias["target_path"],
                    "tier": alias["tier"],
                    "review_status": str(binding.get("review_status", "")),
                }
            )
    return usages


def _alias_record(item: dict[str, Any]) -> dict[str, str] | None:
    source_key = str(item.get("source_key", "")).strip()
    target_path = str(item.get("target_path", "")).strip()
    if not source_key or not target_path:
        return None
    return {
        "source_key": source_key,
        "target_path": target_path,
        "tier": str(item.get("tier", "reviewed_pattern")).strip() or "reviewed_pattern",
        "review_source": str(item.get("review_source", "manual")).strip() or "manual",
    }
