from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_PATTERN_MIN_DISTINCT_APPS = 3


def build_binding_pattern_candidates(
    history_path: str | Path,
    *,
    output_path: str | Path | None = None,
    min_distinct_apps: int = DEFAULT_PATTERN_MIN_DISTINCT_APPS,
) -> dict[str, Any]:
    rows = _load_history_rows(history_path)
    grouped = _group_rows(rows)
    candidates = [_candidate_payload(key, values, min_distinct_apps) for key, values in grouped.items()]
    candidates.sort(key=lambda item: (-item["distinct_app_count"], -item["success_count"], item["source_key"], item["target_field"]))
    payload = {
        "history_path": str(history_path),
        "history_row_count": len(rows),
        "candidate_count": len(candidates),
        "promotion_ready_count": sum(1 for candidate in candidates if candidate["promotion_ready"]),
        "min_distinct_apps": min_distinct_apps,
        "candidates": candidates,
    }
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def _load_history_rows(history_path: str | Path) -> list[dict[str, Any]]:
    path = Path(history_path)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        value = json.loads(stripped)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _group_rows(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("source_type") or ""),
            str(row.get("source_key") or ""),
            str(row.get("target_field") or ""),
            str(row.get("target_path") or row.get("placeholder") or ""),
        )
        if not any(key):
            continue
        grouped[key].append(row)
    return grouped


def _candidate_payload(key: tuple[str, str, str, str], rows: list[dict[str, Any]], min_distinct_apps: int) -> dict[str, Any]:
    source_type, source_key, target_field, target_locator = key
    apps = sorted({str(row.get("app_host") or "") for row in rows if str(row.get("app_host") or "")})
    workflows = sorted({str(row.get("workflow_id") or "") for row in rows if str(row.get("workflow_id") or "")})
    return {
        "source_type": source_type,
        "source_key": source_key,
        "target_field": target_field,
        "target_locator": target_locator,
        "success_count": len(rows),
        "distinct_app_count": len(apps),
        "distinct_workflow_count": len(workflows),
        "apps": apps,
        "workflows": workflows,
        "proposal_status": "review_required",
        "promotion_ready": len(apps) >= min_distinct_apps,
        "promotion_reason": _promotion_reason(len(apps), min_distinct_apps),
    }


def _promotion_reason(distinct_app_count: int, min_distinct_apps: int) -> str:
    if distinct_app_count >= min_distinct_apps:
        return f"Observed in {distinct_app_count} distinct apps; ready for human review before alias-table promotion"
    return f"Observed in {distinct_app_count} distinct apps; need {min_distinct_apps} before human review for promotion"
