from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from adapters.live_replay.workflow_executor import execute_live_workflow_replay


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Execute grouped live workflow replay cases from workflow and attack plans. "
            "This uses bounded workflow/session context requirements only. "
            "It does not do browser orchestration or session repair."
        )
    )
    parser.add_argument("workflow_plan", help="Path to live_workflow_plan.json")
    parser.add_argument("live_attack_plan", help="Path to live_attack_plan.json")
    parser.add_argument("output", help="Path to write live workflow replay summary")
    parser.add_argument("--auth-context", help="Path to approved auth context JSON for reviewed auth-safe-read steps")
    parser.add_argument("--allow-reviewed-auth", action="store_true", help="Allow reviewed auth-safe-read workflow steps when approved auth context is supplied")
    parser.add_argument("--write-context", help="Path to approved staging write context JSON for reviewed write workflow steps")
    parser.add_argument("--allow-reviewed-writes", action="store_true", help="Allow reviewed staging write workflow steps when approved write context is supplied")
    parser.add_argument("--timeout-seconds", type=int, default=10)
    args = parser.parse_args()

    payload = execute_live_workflow_replay(
        args.workflow_plan,
        args.live_attack_plan,
        auth_context=args.auth_context,
        allow_reviewed_auth=args.allow_reviewed_auth,
        write_context=args.write_context,
        allow_reviewed_writes=args.allow_reviewed_writes,
        output_path=args.output,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
