from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate replay-pack groups from normalized fixture bundles.")
    parser.add_argument("input", help="Path to normalized fixture bundle JSON")
    parser.add_argument("output", help="Path to write replay-pack JSON")
    args = parser.parse_args()

    bundle = json.loads(Path(args.input).read_text())
    replay_pack = build_replay_pack(bundle)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(replay_pack, indent=2) + "\n")

    print(
        "wrote replay pack with "
        f"{len(replay_pack['safe_read_probes'])} safe reads, "
        f"{len(replay_pack['write_path_review_items'])} write review items, and "
        f"{len(replay_pack['sandbox_only_attack_set'])} sandbox-only items to {output_path}"
    )


def build_replay_pack(bundle: dict[str, Any]) -> dict[str, Any]:
    fixtures = bundle.get("fixtures", [])

    safe_read_probes = [build_safe_read_probe(fixture) for fixture in fixtures if fixture.get("replay_class") in {"safe_read", "safe_read_with_review"}]
    write_path_review_items = [
        build_write_review_item(fixture)
        for fixture in fixtures
        if fixture.get("replay_class") == "manual_review"
    ]
    sandbox_only_attack_set = [
        build_sandbox_item(fixture)
        for fixture in fixtures
        if fixture.get("replay_class") == "sandbox_only"
    ]

    return {
        "source": bundle.get("source", "unknown"),
        "fixture_input": bundle.get("input_file", "unknown"),
        "safe_read_probes": safe_read_probes,
        "write_path_review_items": write_path_review_items,
        "sandbox_only_attack_set": sandbox_only_attack_set,
        "summary": {
            "fixture_count": bundle.get("fixture_count", len(fixtures)),
            "safe_read_count": len(safe_read_probes),
            "write_review_count": len(write_path_review_items),
            "sandbox_only_count": len(sandbox_only_attack_set),
        },
    }


def build_safe_read_probe(fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": fixture["name"],
        "method": fixture["method"],
        "path": fixture["path"],
        "goal": "Validate safe read behavior without overbroad access or leakage.",
        "checks": [
            "least_privilege_response",
            "no_secret_or_pii_overexposure",
            "authorization_boundary_respected",
        ],
        "candidate_attack_types": fixture.get("candidate_attack_types", []),
    }


def build_write_review_item(fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": fixture["name"],
        "method": fixture["method"],
        "path": fixture["path"],
        "approval_required": fixture.get("approval_required", False),
        "review_focus": [
            "unsafe_write_activation",
            "parameter_grounding",
            "operator_approval_boundary",
        ],
        "candidate_attack_types": fixture.get("candidate_attack_types", []),
    }


def build_sandbox_item(fixture: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": fixture["name"],
        "method": fixture["method"],
        "path": fixture["path"],
        "run_mode": "sandbox_only",
        "checks": [
            "destructive_action_denied_or_intercepted",
            "privilege_boundary_enforced",
            "full_audit_log_captured",
        ],
        "candidate_attack_types": fixture.get("candidate_attack_types", []),
    }


if __name__ == "__main__":
    main()
