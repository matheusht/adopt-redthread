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
    parser = argparse.ArgumentParser(description="Prototype pre-publish gate based on replay-pack composition.")
    parser.add_argument("input", help="Path to replay-pack JSON")
    parser.add_argument("output", help="Path to write gate verdict JSON")
    parser.add_argument("--allow-sandbox-only", action="store_true", help="Allow sandbox-only items to pass without blocking")
    args = parser.parse_args()

    replay_pack = json.loads(Path(args.input).read_text())
    verdict = build_gate_verdict(replay_pack, allow_sandbox_only=args.allow_sandbox_only)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(verdict, indent=2) + "\n")

    print(f"gate verdict: {verdict['decision']} -> {output_path}")


def build_gate_verdict(replay_pack: dict[str, Any], *, allow_sandbox_only: bool) -> dict[str, Any]:
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

    decision = "approve"
    if blockers:
        decision = "block"
    elif warnings:
        decision = "review"

    return {
        "decision": decision,
        "input_summary": replay_pack.get("summary", {}),
        "blockers": blockers,
        "warnings": warnings,
        "notes": _build_notes(
            safe_read_count=len(safe_reads),
            write_review_count=len(write_reviews),
            sandbox_count=len(sandbox_items),
            allow_sandbox_only=allow_sandbox_only,
        ),
    }


def _build_notes(*, safe_read_count: int, write_review_count: int, sandbox_count: int, allow_sandbox_only: bool) -> list[str]:
    notes = [
        f"safe_read_count={safe_read_count}",
        f"write_review_count={write_review_count}",
        f"sandbox_only_count={sandbox_count}",
    ]
    if allow_sandbox_only:
        notes.append("sandbox_only_items_waived_for_this_run")
    else:
        notes.append("sandbox_only_items_block_publish_by_default")
    return notes


if __name__ == "__main__":
    main()
