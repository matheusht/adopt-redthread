from __future__ import annotations


def build_canary_report(fixture: dict[str, object]) -> dict[str, object]:
    if fixture.get("replay_class") in {"safe_read", "safe_read_with_review"}:
        return {}
    return {
        "injection_point": "tool_return",
        "crossed_boundaries": ["tool_return", "shared_state"],
        "stage_count": 2,
        "reached_execution_boundary": False,
        "contained": True,
        "canary_tags": [canary_tag(fixture)],
    }


def canary_tag(fixture: dict[str, object]) -> str:
    return f"CANARY_{str(fixture['name']).upper()[:32]}"
