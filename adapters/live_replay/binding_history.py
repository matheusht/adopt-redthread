from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_binding_history(summary: dict[str, Any], workflows: list[dict[str, Any]], cases: dict[str, dict[str, Any]], output_path: str | Path) -> int:
    rows = binding_history_rows(summary, workflows, cases)
    if not rows:
        return 0
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def binding_history_rows(summary: dict[str, Any], workflows: list[dict[str, Any]], cases: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    workflow_map = {str(workflow.get("workflow_id", "")): workflow for workflow in workflows}
    rows: list[dict[str, Any]] = []
    for result in summary.get("results", []):
        if result.get("status") != "completed":
            continue
        workflow = workflow_map.get(str(result.get("workflow_id", "")))
        if workflow is None:
            continue
        binding_specs = _binding_spec_map(workflow)
        for step_result in result.get("results", []):
            for applied in step_result.get("workflow_evidence", {}).get("applied_response_bindings", []):
                binding_id = str(applied.get("binding_id", "")).strip()
                spec = binding_specs.get(binding_id, {})
                source_case_id = str(applied.get("source_case_id") or spec.get("source_case_id") or "")
                case = cases.get(source_case_id, {})
                rows.append(
                    {
                        "workflow_id": result.get("workflow_id"),
                        "source_case_id": source_case_id,
                        "source_type": spec.get("source_type"),
                        "source_key": spec.get("source_key"),
                        "target_field": applied.get("target_field") or spec.get("target_field"),
                        "target_path": applied.get("target_path") or spec.get("target_path"),
                        "placeholder": applied.get("placeholder") or spec.get("placeholder"),
                        "binding_id": binding_id,
                        "outcome": "success",
                        "app_host": _app_host(case),
                    }
                )
    return rows


def _binding_spec_map(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(binding.get("binding_id", "")).strip(): binding
        for step in workflow.get("steps", [])
        for binding in step.get("response_bindings", [])
        if str(binding.get("binding_id", "")).strip()
    }


def _app_host(case: dict[str, Any]) -> str | None:
    host = str(case.get("request_blueprint", {}).get("host", "")).strip()
    return host or None
