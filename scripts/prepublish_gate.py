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

    _apply_live_safe_replay_rules(live_safe_replay, blockers, warnings)
    _apply_live_workflow_rules(live_workflow_replay, blockers, warnings)
    _apply_redthread_replay_rules(redthread_replay_verdict, blockers)

    decision = "approve"
    if blockers:
        decision = "block"
    elif warnings:
        decision = "review"

    return {
        "decision": decision,
        "input_summary": replay_pack.get("summary", {}),
        "evidence_summary": {
            "live_safe_replay": _evidence_counts(live_safe_replay),
            "live_workflow_replay": _evidence_counts(live_workflow_replay),
            "redthread_replay_verdict": _evidence_counts(redthread_replay_verdict),
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
    if redthread_replay_verdict is not None:
        notes.append(f"redthread_replay_passed={bool(redthread_replay_verdict.get('passed'))}")
    return notes


def _apply_live_safe_replay_rules(
    live_safe_replay: dict[str, Any] | None,
    blockers: list[str],
    warnings: list[str],
) -> None:
    if live_safe_replay is None:
        return
    executed = int(live_safe_replay.get("executed_case_count", 0))
    success = int(live_safe_replay.get("success_count", 0))
    allowed = int(live_safe_replay.get("allowed_case_count", executed))
    if executed == 0 and allowed > 0:
        warnings.append("live_safe_replay_not_executed")
    if success < executed:
        blockers.append("live_safe_replay_failures_present")


def _apply_live_workflow_rules(
    live_workflow_replay: dict[str, Any] | None,
    blockers: list[str],
    warnings: list[str],
) -> None:
    if live_workflow_replay is None:
        return
    workflow_count = int(live_workflow_replay.get("workflow_count", 0))
    executed = int(live_workflow_replay.get("executed_workflow_count", 0))
    successful = int(live_workflow_replay.get("successful_workflow_count", 0))
    if executed == 0 and workflow_count > 0:
        warnings.append("live_workflow_replay_not_executed")
    if successful < executed:
        blockers.append("live_workflow_replay_failures_present")
    if any(result.get("status") == "blocked" for result in live_workflow_replay.get("results", [])):
        blockers.append("live_workflow_blocked_steps_present")


def _apply_redthread_replay_rules(redthread_replay_verdict: dict[str, Any] | None, blockers: list[str]) -> None:
    if redthread_replay_verdict is None:
        return
    if not redthread_replay_verdict.get("passed", False):
        blockers.append("redthread_replay_verdict_failed")


def _evidence_counts(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if payload is None:
        return None
    summary: dict[str, Any] = {}
    for key in (
        "allowed_case_count",
        "executed_case_count",
        "success_count",
        "workflow_count",
        "executed_workflow_count",
        "successful_workflow_count",
        "passed",
    ):
        if key in payload:
            summary[key] = payload[key]
    return summary


def _load_optional_json(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text())


if __name__ == "__main__":
    main()
