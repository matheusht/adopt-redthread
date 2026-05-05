from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.live_replay.approved_context_replay import approved_context_replay


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or execute one approval-gated endpoint replay and emit sanitized proof. "
            "Default mode is plan/not-run only. Live execution requires --execute plus a sanitized --execution-approval artifact."
        )
    )
    parser.add_argument("--live-attack-plan", required=True, help="Path to live_attack_plan.json containing the target case")
    parser.add_argument("--case-id", required=True, help="Case ID to replay from the live attack plan")
    parser.add_argument("--output-dir", default="runs/approved_context_replay", help="Directory for approved_context_replay_plan/result artifacts")
    parser.add_argument("--auth-context", help="Local ignored approved auth context JSON; raw values are never copied to output artifacts")
    parser.add_argument("--write-context", help="Local ignored approved write context JSON; raw values are never copied to output artifacts")
    parser.add_argument("--execution-approval", help="Sanitized approved-context replay execution approval JSON")
    parser.add_argument("--allow-reviewed-auth", action="store_true", help="Allow reviewed auth-safe-read cases when approved auth context is supplied")
    parser.add_argument("--allow-reviewed-writes", action="store_true", help="Allow reviewed staging write cases when approved write context is supplied")
    parser.add_argument("--execute", action="store_true", help="Attempt live execution only when context and execution approval both pass")
    parser.add_argument("--timeout-seconds", type=int, default=10)
    parser.add_argument("--stream-max-bytes", type=int, default=512)
    parser.add_argument("--fail-on-marker-hit", dest="fail_on_marker_hit", action="store_true", help="Exit non-zero if generated sanitized artifacts hit configured markers (default)")
    parser.add_argument("--allow-marker-hits", dest="fail_on_marker_hit", action="store_false", help="Write artifacts even when configured marker audit fails")
    parser.set_defaults(fail_on_marker_hit=True)
    args = parser.parse_args()

    result = approved_context_replay(
        args.live_attack_plan,
        case_id=args.case_id,
        auth_context=args.auth_context,
        write_context=args.write_context,
        execution_approval=args.execution_approval,
        allow_reviewed_auth=args.allow_reviewed_auth,
        allow_reviewed_writes=args.allow_reviewed_writes,
        execute=args.execute,
        output_dir=args.output_dir,
        timeout_seconds=args.timeout_seconds,
        stream_max_bytes=args.stream_max_bytes,
        fail_on_marker_hit=args.fail_on_marker_hit,
    )
    print(json.dumps({
        "result_class": result["result_class"],
        "execution_state": result["execution_state"],
        "http_status_family": result["http_status_family"],
        "replay_failure_category": result["replay_failure_category"],
        "blocked_reasons": result["blocked_reasons"],
        "output_dir": args.output_dir,
    }, indent=2))


if __name__ == "__main__":
    main()
