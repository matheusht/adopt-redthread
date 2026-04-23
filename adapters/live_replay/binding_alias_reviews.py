from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SUPPORTED_TARGET_FIELDS = {"request_body_json"}
REVIEWED_PATTERN_TIER = "reviewed_pattern"


def build_approved_binding_aliases(
    candidate_payload: dict[str, Any] | str | Path,
    review_payload: dict[str, Any] | str | Path,
    *,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    candidates = _load_payload(candidate_payload)
    review = _load_payload(review_payload)
    approved_keys = {
        _review_key(item)
        for item in review.get("approved_candidates", [])
        if isinstance(item, dict)
    }
    aliases = [
        {
            "source_key": candidate["source_key"],
            "target_path": candidate["target_locator"],
            "tier": REVIEWED_PATTERN_TIER,
            "review_source": "binding_pattern_candidates",
        }
        for candidate in candidates.get("candidates", [])
        if _candidate_key(candidate) in approved_keys and _candidate_promotable(candidate)
    ]
    payload = {
        "candidate_count": len(candidates.get("candidates", [])),
        "review_approval_count": len(approved_keys),
        "approved_alias_count": len(aliases),
        "aliases": aliases,
    }
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def load_approved_binding_aliases(value: dict[str, Any] | str | Path | None) -> list[dict[str, str]]:
    if value is None:
        return []
    payload = _load_payload(value)
    aliases = payload.get("aliases", [])
    return [alias for alias in aliases if isinstance(alias, dict)]


def _load_payload(value: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return json.loads(Path(value).read_text())


def _candidate_promotable(candidate: dict[str, Any]) -> bool:
    return (
        bool(candidate.get("promotion_ready"))
        and str(candidate.get("target_field", "")) in SUPPORTED_TARGET_FIELDS
        and bool(str(candidate.get("target_locator", "")).strip())
        and bool(str(candidate.get("source_key", "")).strip())
    )


def _candidate_key(candidate: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(candidate.get("source_key", "")).strip(),
        str(candidate.get("target_field", "")).strip(),
        str(candidate.get("target_locator", "")).strip(),
    )


def _review_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("source_key", "")).strip(),
        str(item.get("target_field", "")).strip(),
        str(item.get("target_locator", "")).strip(),
    )
