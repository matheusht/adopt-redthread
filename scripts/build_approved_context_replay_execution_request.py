from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.live_replay.approved_context_replay import build_execution_approval_request


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Build a sanitized approval request for a future approved-context replay execution. "
            "This emits a false-by-default local approval template and does not execute any endpoint."
        )
    )
    parser.add_argument("--replay-plan", required=True, help="Path to approved_context_replay_plan.json")
    parser.add_argument("--replay-result", required=True, help="Path to approved_context_replay_result.json")
    parser.add_argument("--output-dir", default="runs/approved_context_replay", help="Directory for execution_approval_request artifacts")
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true", help="Exit non-zero if generated artifacts hit configured sensitive markers (default)")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false", help="Write artifacts even when configured marker audit fails")
    parser.set_defaults(fail_on_marker_hit=True)
    args = parser.parse_args()

    payload = build_execution_approval_request(
        args.replay_plan,
        args.replay_result,
        output_dir=args.output_dir,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(json.dumps({
        "request_status": payload["request_status"],
        "case_id": payload["case_evidence"]["case_id"],
        "context_ready": payload["current_execution_state"]["context_ready"],
        "execution_approved": payload["current_execution_state"]["execution_approved"],
        "executed": payload["current_execution_state"]["executed"],
        "output_dir": args.output_dir,
    }, indent=2))


if __name__ == "__main__":
    main()
