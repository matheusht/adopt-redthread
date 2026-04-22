from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


from adapters.bridge.gate_evidence import apply_live_safe_replay_rules, apply_live_workflow_rules, apply_redthread_replay_rules, evidence_counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Prototype pre-publish gate based on replay-pack composition and optional live evidence.")
    parser.add_argument("input", help="Path to replay-pack JSON")
    parser.add_argument("output", help="Path to write gate verdict JSON")
    parser.add_argument("--allow-sandbox-only", action="store_true", help="Allow sandbox-only items to pass without blocking")
    parser.add_argument("--live-safe-replay", help="Optional path to live_safe_replay.json")
    parser.add_argument("--live-workflow-replay", help="Optional path to live_workflow_replay.json")
    parser.add_argument("--redthread-replay-verdict", help="Optional path to redthread_replay_verdict.json")
    args = parser.parse_args()

    replay_pack = json.loads(Path(args.input).read_text())
    verdict = build_gate_verdict(
        replay_pack,
        allow_sandbox_only=args.allow_sandbox_only,
        live_safe_replay=_load_optional_json(args.live_safe_replay),
        live_workflow_replay=_load_optional_json(args.live_workflow_replay),
        redthread_replay_verdict=_load_optional_json(args.redthread_replay_verdict),
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(verdict, indent=2) + "\n")

    print(f"gate verdict: {verdict['decision']} -> {output_path}")


def build_gate_verdict(
    replay_pack: dict[str, Any],
    *,
    allow_sandbox_only: bool,
    live_safe_replay: dict[str, Any] | None = None,
    live_workflow_replay: dict[str, Any] | None = None,
    redthread_replay_verdict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    safe_reads = replay_pack.get("safe_read_probes", [])
    write_reviews = replay_pack.get("write_path_review_items", [])
    sandbox_items = replay_pack.get("sandbox_only_attack_set", [])

    blockers: list[str] = []
    warnings: list[str] = []

    if write_reviews:
        warnings.append("manual_review_required_for_write_paths")
    if sandbox_items and not allow_sandbox_only:
        blockers.append("sandbox_only_items_present")
    if not safe_reads and not write_reviews and not sandbox_items:
        blockers.append("empty_replay_pack")

    apply_live_safe_replay_rules(live_safe_replay, blockers, warnings)
    apply_live_workflow_rules(live_workflow_replay, blockers, warnings)
    apply_redthread_replay_rules(redthread_replay_verdict, blockers)

    decision = "approve"
    if blockers:
        decision = "block"
    elif warnings:
        decision = "review"

    return {
        "decision": decision,
        "input_summary": replay_pack.get("summary", {}),
        "evidence_summary": {
            "live_safe_replay": evidence_counts(live_safe_replay),
            "live_workflow_replay": evidence_counts(live_workflow_replay),
            "redthread_replay_verdict": evidence_counts(redthread_replay_verdict),
        },
        "blockers": blockers,
        "warnings": warnings,
        "notes": _build_notes(
            safe_read_count=len(safe_reads),
            write_review_count=len(write_reviews),
            sandbox_count=len(sandbox_items),
            allow_sandbox_only=allow_sandbox_only,
            live_safe_replay=live_safe_replay,
            live_workflow_replay=live_workflow_replay,
            redthread_replay_verdict=redthread_replay_verdict,
        ),
    }


def _build_notes(
    *,
    safe_read_count: int,
    write_review_count: int,
    sandbox_count: int,
    allow_sandbox_only: bool,
    live_safe_replay: dict[str, Any] | None,
    live_workflow_replay: dict[str, Any] | None,
    redthread_replay_verdict: dict[str, Any] | None,
) -> list[str]:
    notes = [
        f"safe_read_count={safe_read_count}",
        f"write_review_count={write_review_count}",
        f"sandbox_only_count={sandbox_count}",
    ]
    if allow_sandbox_only:
        notes.append("sandbox_only_items_waived_for_this_run")
    else:
        notes.append("sandbox_only_items_block_publish_by_default")
    if live_safe_replay is not None:
        notes.append(f"live_safe_replay_executed_case_count={live_safe_replay.get('executed_case_count', 0)}")
        notes.append(f"live_safe_replay_success_count={live_safe_replay.get('success_count', 0)}")
    if live_workflow_replay is not None:
        notes.append(f"live_workflow_replay_executed_workflow_count={live_workflow_replay.get('executed_workflow_count', 0)}")
        notes.append(f"live_workflow_replay_successful_workflow_count={live_workflow_replay.get('successful_workflow_count', 0)}")
        notes.extend(
            _workflow_requirement_notes(
                live_workflow_replay.get("workflow_requirement_summary", {}),
                live_workflow_replay.get("workflow_failure_class_summary", {}),
            )
        )
    if redthread_replay_verdict is not None:
        notes.append(f"redthread_replay_passed={bool(redthread_replay_verdict.get('passed'))}")
    return notes



def _workflow_requirement_notes(summary: dict[str, Any], failure_classes: dict[str, Any]) -> list[str]:
    if not summary and not failure_classes:
        return []
    class_counts = summary.get("workflow_class_counts", {})
    failure_counts = summary.get("context_contract_failure_counts", {})
    return [
        f"live_workflow_classes={_flat_counts(class_counts)}",
        f"live_workflow_same_host_required_count={summary.get('same_host_continuity_required_count', 0)}",
        f"live_workflow_same_target_env_required_count={summary.get('same_target_env_required_count', 0)}",
        f"live_workflow_shared_auth_context_required_count={summary.get('shared_auth_context_required_count', 0)}",
        f"live_workflow_same_auth_context_required_count={summary.get('same_auth_context_required_count', 0)}",
        f"live_workflow_approved_auth_context_required_count={summary.get('approved_auth_context_required_count', 0)}",
        f"live_workflow_shared_write_context_required_count={summary.get('shared_write_context_required_count', 0)}",
        f"live_workflow_same_write_context_required_count={summary.get('same_write_context_required_count', 0)}",
        f"live_workflow_approved_write_context_required_count={summary.get('approved_write_context_required_count', 0)}",
        f"live_workflow_auth_header_contract_required_count={summary.get('auth_header_contract_required_count', 0)}",
        f"live_workflow_declared_response_binding_count={summary.get('declared_response_binding_count', 0)}",
        f"live_workflow_applied_response_binding_count={summary.get('applied_response_binding_count', 0)}",
        f"live_workflow_inferred_response_binding_count={summary.get('inferred_response_binding_count', 0)}",
        f"live_workflow_approved_response_binding_count={summary.get('approved_response_binding_count', 0)}",
        f"live_workflow_pending_review_response_binding_count={summary.get('pending_review_response_binding_count', 0)}",
        f"live_workflow_rejected_response_binding_count={summary.get('rejected_response_binding_count', 0)}",
        f"live_workflow_replaced_response_binding_count={summary.get('replaced_response_binding_count', 0)}",
        f"live_workflow_required_header_families={_flat_counts(summary.get('required_header_family_counts', {}))}",
        f"live_workflow_context_contract_failures={_flat_counts(failure_counts)}",
        f"live_workflow_failure_classes={_flat_counts(failure_classes)}",
    ]



def _flat_counts(payload: dict[str, Any]) -> str:
    if not payload:
        return "none"
    return ",".join(f"{key}:{payload[key]}" for key in sorted(payload))



def _load_optional_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text())


if __name__ == "__main__":
    main()
